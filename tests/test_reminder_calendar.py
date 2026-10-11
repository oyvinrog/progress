"""Behavioral tests for the waiting-reminder calendar and its existing row actions."""
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest
from PySide6.QtQuick import QQuickWindow

COMPONENTS = Path(__file__).resolve().parents[1] / "actiondraw/qml_ui/components"
WRAPPER = '''
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "%s"
Window {
    width: 1000; height: 650; visible: true
    QtObject {
        id: host
        objectName: "host"
        property var activeReminders: []
        property bool reminderOverviewExpanded: true
        property bool reminderOverviewTouched: false
        property string action: ""
        property string savedReminder: ""
        function presetTitle(name) { return name }
        function refreshActiveReminders() { action = "refresh" }
    }
    QtObject {
        id: manager
        function addStandaloneReminder(title, date, notify) { host.savedReminder = date; return true }
        function openTabTask(tab, task) { host.action = "open-task" }
        function openMindmapReminder(node) { host.action = "open-node" }
        function clearReminder(tab, task) { host.action = "clear-task" }
        function clearMindmapReminder(node) { host.action = "clear-node" }
        function clearStandaloneReminder(index) { host.action = "clear-standalone" }
    }
    QtObject {
        id: dialogs
        function openTaskReminderEditDialog(tab, task, date, notify) { host.action = "edit-task" }
        function openStandaloneReminderEditDialog(index, title, date, notify) { host.action = "edit-standalone" }
        function openMindmapReminderDialog(node, date, notify) { host.action = "edit-node" }
    }
    QtObject {
        id: plan
        property var planWeekdayOptions: []
        function cancelPlanSchedule(node) { host.action = "cancel-plan" }
    }
    ReminderOverview {
        width: parent.width
        windowRoot: host; projectManager: manager; dialogs: dialogs; planController: plan
    }
}
''' % COMPONENTS.as_uri()


def find(root, name):
    pending = [root.contentItem()]
    while pending:
        item = pending.pop(0)
        if item.objectName() == name:
            return item
        pending.extend(item.childItems())
    raise AssertionError(f"Missing visual item: {name}")


def value(obj, name):
    result = obj.property(name)
    return result.toVariant() if hasattr(result, "toVariant") else result


def reminder(date, kind="task", node=""):
    return dict(kind=kind, title=kind, taskTitle=kind, tabName="Main", tabIndex=0,
                taskIndex=0, standaloneIndex=0, nodeId=node,
                reminderAt=datetime.fromisoformat(date).timestamp(),
                reminderText=date, countdownText="1:00", sendNotification=False)


@pytest.fixture
def calendar_ui(app, request, qml_cleanup):
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    wrapper = WRAPPER
    if getattr(request, "param", "mock") == "real":
        start = wrapper.index("    QtObject {\n        id: dialogs")
        end = wrapper.index("    QtObject {\n        id: plan", start)
        wrapper = wrapper[:start] + '    ActionDialogs { id: dialogs; objectName: "dialogs"; root: host; projectManager: manager }\n' + wrapper[end:]
    component.setData(wrapper.encode(), QUrl.fromLocalFile(str(COMPONENTS / "Test.qml")))
    root = component.create()
    qml_cleanup(engine, root)
    assert root is not None, component.errorString()
    host = root.findChild(QObject, "host")
    overview = find(root, "reminderOverview")
    calendar = find(root, "reminderCalendar")

    def refresh(entries):
        host.setProperty("activeReminders", entries)
        overview.setProperty("nowTimestamp", datetime(2032, 2, 28, 12).timestamp())
        for _ in range(3):
            app.processEvents()

    def click(name):
        QTest.qWait(30)
        item = find(root, name)
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
        app.processEvents()

    calendar.setProperty("displayedYear", 2032)
    calendar.setProperty("displayedMonth", 1)
    refresh([])
    yield root, host, overview, calendar, refresh, click
    root.close()


def test_counts_local_dates_future_only_and_all_kinds(calendar_ui):
    _, _, overview, calendar, refresh, _ = calendar_ui
    entries = [reminder("2032-02-28T23:59:00", kind, str(i)) for i, kind in enumerate(
        ["task", "standalone", "mindmap", "kanban_schedule"])]
    entries += [reminder("2032-02-29T00:01:00"), reminder("2032-02-28T12:00:00"),
                reminder("2032-02-27T23:59:00")]
    refresh(entries)
    assert value(overview, "dayCounts") == {"2032-02-28": 4, "2032-02-29": 1}
    assert len(value(overview, "filteredReminders")) == 5
    assert calendar.property("todayKey") == "2032-02-28"
    assert find(calendar.window(), "reminderDay_2032-02-28").property("reminderCount") == 4
    overview.setProperty("nowTimestamp", datetime(2032, 2, 29, 0, 0).timestamp())
    assert value(overview, "dayCounts") == {"2032-02-29": 1}


def test_selection_reset_and_live_updates(calendar_ui):
    root, _, overview, calendar, refresh, click = calendar_ui
    first = reminder("2032-02-28T18:00:00")
    second = reminder("2032-02-29T18:00:00", "standalone")
    refresh([first, second])
    click("reminderDay_2032-02-29")
    assert overview.property("selectedDate") == "2032-02-29"
    assert [e["kind"] for e in value(overview, "filteredReminders")] == ["standalone"]
    refresh([first, second, reminder("2032-02-29T20:00:00", "mindmap", "n")])
    assert len(value(overview, "filteredReminders")) == 2
    # Rescheduling/removing/firing replaces the shared active-reminder snapshot.
    refresh([first, reminder("2032-03-01T18:00:00", "standalone")])
    assert overview.property("selectedDate") == "2032-02-29"
    assert calendar.property("displayedMonth") == 1
    assert value(overview, "filteredReminders") == []
    assert find(root, "reminderEmptyDay").isVisible()
    assert find(root, "reminderEmptyDay").property("text") == "No reminders for this day"
    click("reminderAllDays")
    assert overview.property("selectedDate") == ""
    assert len(value(overview, "filteredReminders")) == 2
    refresh([])
    assert find(root, "reminderCalendar").isVisible()


def test_monday_grid_leap_year_and_month_navigation(calendar_ui):
    _, _, overview, calendar, _, click = calendar_ui
    days = value(calendar, "calendarDays")
    assert days[0]["key"] == "2032-01-26"  # Monday
    assert sum(d["inMonth"] for d in days) == 29
    click("reminderDay_2032-02-29")
    calendar.setProperty("displayedMonth", 11)
    click("reminderNextMonth")
    assert calendar.property("displayedYear") == 2033
    assert calendar.property("displayedMonth") == 0
    assert overview.property("selectedDate") == "2032-02-29"
    click("reminderPreviousMonth")
    assert calendar.property("displayedYear") == 2032
    assert calendar.property("displayedMonth") == 11
    click("reminderToday")
    assert calendar.property("displayedMonth") == 1
    assert overview.property("selectedDate") == "2032-02-29"
    calendar.setProperty("displayedYear", 2033)
    assert sum(d["inMonth"] for d in value(calendar, "calendarDays")) == 28


def test_responsive_layout_collapse_and_row_actions(calendar_ui, app):
    root, host, _, _, refresh, click = calendar_ui
    refresh([reminder("2032-02-29T18:00:00")])
    assert find(root, "reminderCalendarContent").property("columns") == 2
    click("openReminder_task")
    assert host.property("action") == "open-task"
    click("editReminder_task")
    assert host.property("action") == "edit-task"
    click("clearReminder_task")
    assert host.property("action") == "refresh"
    root.setWidth(600)
    app.processEvents()
    assert find(root, "reminderCalendarContent").property("columns") == 1
    click("toggleReminderOverview")
    assert not find(root, "reminderCalendar").isVisible()
    click("toggleReminderOverview")
    assert find(root, "reminderCalendar").isVisible()


@pytest.mark.parametrize("kind,node,open_action,edit_action", [
    ("mindmap", "n", "open-node", "edit-node"),
    ("standalone", "", None, "edit-standalone"),
    ("kanban_schedule", "n", "open-node", None),
])
def test_other_reminder_actions_preserved(calendar_ui, kind, node, open_action, edit_action):
    _, host, _, _, refresh, click = calendar_ui
    refresh([reminder("2032-02-29T18:00:00", kind, node)])
    suffix = ("plan_" if kind == "kanban_schedule" else "") + (node or kind)
    if open_action:
        click("openReminder_" + suffix)
        assert host.property("action") == open_action
    if edit_action:
        click("editReminder_" + suffix)
        assert host.property("action") == edit_action
    click("clearReminder_" + suffix)
    assert host.property("action") == "refresh"


@pytest.mark.parametrize("calendar_ui", ["real"], indirect=True)
def test_new_reminder_uses_selected_date_and_all_days_defaults(calendar_ui, app):
    root, host, overview, _, _, click = calendar_ui
    dialogs = root.findChild(QObject, "dialogs")
    dialog = dialogs.findChild(QObject, "reminderDialog")
    # A prior node reminder must not redirect the new project reminder to a node.
    dialog.setProperty("nodeId", "previous-node")
    click("reminderDay_2032-02-29")
    click("newStandaloneReminder")
    assert dialog.property("visible")
    assert dialog.property("dateValue") == "2032-02-29"
    assert dialog.property("timeValue")
    assert dialog.property("nodeId") == ""
    dialog.setProperty("standaloneTitle", "Future follow-up")
    dialog.accept()
    app.processEvents()
    assert host.property("savedReminder").startswith("2032-02-29 ")
    assert overview.property("selectedDate") == "2032-02-29"
    click("reminderAllDays")
    before = datetime.now().timestamp() + 3600
    click("newStandaloneReminder")
    after = datetime.now().timestamp() + 3600
    actual = datetime.fromisoformat(dialog.property("dateValue") + "T" + dialog.property("timeValue")).timestamp()
    assert before - 60 <= actual <= after
    dialog.reject()
