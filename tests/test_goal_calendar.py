"""Goal periods are civil dates and remain independent of reminders and Kanban."""
import json
import pytest
from task_model import TabModel, TaskModel, ProjectManager
from actiondraw.model import DiagramModel
from progress_crypto import EncryptionCredentials
from test_reminder_calendar import calendar_ui, find, value
from PySide6.QtCore import Qt, QPointF, QPoint, QObject
from PySide6.QtTest import QTest


def test_range_validation_stable_ids_and_signals(app):
    tabs = TabModel()
    tabs.addTab("Main")
    changes = []
    tabs.scheduledGoalsChanged.connect(lambda: changes.append(True))
    goal = tabs.createScheduledGoal("Launch", "2032-02-28", "2032-03-02")
    assert goal
    tabs.moveTab(1, 0)
    assert tabs.setGoalRange(goal, "2032-02-29", "2032-02-29")
    original = tabs.scheduledGoals
    for start, end in [("2033-02-29", "2033-03-01"), ("2032-03-03", "2032-03-02"),
                       ("", ""), ("20320301", "20320302")]:
        assert not tabs.setGoalRange(goal, start, end)
        assert tabs.scheduledGoals == original
        assert not tabs.createScheduledGoal("Invalid", start, end)
    tabs.renameTab(tabs.goalIndex(goal), "Renamed")
    assert tabs.scheduledGoals[0]["name"] == "Renamed"
    tabs.setKanbanPlacement(tabs.goalIndex(goal), "done", -1)
    assert tabs.scheduledGoals
    assert tabs.clearGoalRange(goal)
    assert not tabs.scheduledGoals
    assert tabs.goalIndex(goal) >= 0
    tabs.setGoalRange(goal, "2032-01-01", "2032-01-02")
    tabs.removeTab(tabs.goalIndex(goal))
    assert not tabs.scheduledGoals
    assert not tabs.setGoalRange(goal, "2032-01-01", "2032-01-02")
    assert len(changes) >= 7


def test_period_roundtrip_and_legacy(app, tmp_path, monkeypatch):
    monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials",
                        lambda *args: EncryptionCredentials(passphrase="test-passphrase"))
    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab("Main")
    diagram = DiagramModel(tasks)
    pm = ProjectManager(tasks, diagram, tabs)
    goal = tabs.createScheduledGoal("Range", "2032-12-31", "2033-01-02")
    path = tmp_path / "goals.progress"
    assert pm.saveProject(str(path))
    tabs.clearGoalRange(goal)
    pm.loadProject(str(path))
    assert tabs.scheduledGoals[0]["endDate"] == "2033-01-02"
    payload = pm._build_project_data()
    for raw in payload["tabs"]:
        raw.pop("goal_start_date", None)
        raw.pop("goal_end_date", None)
    path.write_text(json.dumps(payload))
    pm.loadProject(str(path))
    assert tabs.scheduledGoals == []
    payload["tabs"][0].update(goal_start_date="invalid", goal_end_date="2032-01-01")
    path.write_text(json.dumps(payload))
    pm.loadProject(str(path))
    assert tabs.scheduledGoals == []


def test_calendar_counts_overlap_and_week_segments(calendar_ui, app):
    root, _, _, calendar, _, _ = calendar_ui
    goals = [
        dict(id="a", name="Past and present", color="", startDate="2032-02-01", endDate="2032-03-02"),
        dict(id="b", name="Overlap", color="#ffffff", startDate="2032-02-28", endDate="2032-02-29"),
    ]
    calendar.setProperty("goals", goals)
    app.processEvents()
    assert find(root, "reminderDay_2032-02-28").property("goalsCount") == 2
    weeks = value(calendar, "weeks")
    assert sum(len(w["bars"]) for w in weeks) == 7
    assert len(weeks[4]["bars"]) == 2
    assert weeks[4]["bars"][0]["lane"] != weeks[4]["bars"][1]["lane"]


@pytest.mark.parametrize("mode,expected", [
    ("move", ("2032-03-01", "2032-03-03")),
    ("start", ("2032-03-01", "2032-03-01")),
    ("end", ("2032-02-28", "2032-03-03")),
])
def test_pointer_move_and_resize(calendar_ui, app, mode, expected):
    root, _, _, calendar, _, _ = calendar_ui
    goal = dict(id="a", name="Drag me", color="", startDate="2032-02-28", endDate="2032-03-01")
    calendar.setProperty("goals", [goal])
    app.processEvents()
    changes = []
    calendar.rangeEdited.connect(lambda gid, start, end: changes.append((gid, start, end)))
    # Start/end are separate visible week segments.
    bar = find(root, "goalBar_a_" + ("0" if mode == "end" else "5"))
    x = 3 if mode == "start" else bar.width()-3 if mode == "end" else bar.width()/4
    start = bar.mapToScene(QPointF(x, 11)).toPoint()
    target_day = find(root, "reminderDay_" + ("2032-03-03" if mode == "end" else "2032-03-01"))
    end = target_day.mapToScene(QPointF(target_day.width()/2, 15)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, end, 30)
    assert not changes
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    assert changes == [("a", *expected)]


def test_drag_cancel_and_civil_days(calendar_ui, app):
    root, _, _, calendar, _, _ = calendar_ui
    calendar.setProperty("goals", [dict(id="a", name="Cancel", color="", startDate="2032-02-28", endDate="2032-02-29")])
    app.processEvents()
    changes = []
    calendar.rangeEdited.connect(lambda *args: changes.append(args))
    bar = find(root, "goalBar_a_5")
    start = bar.mapToScene(QPointF(30,11)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, start + QPoint(-50,0), 20)
    QTest.keyClick(root, Qt.Key_Escape)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, start)
    assert not changes
    # Dates around the Oslo DST transition remain one civil day apart.
    assert calendar.dayNumber("2026-03-30") - calendar.dayNumber("2026-03-29") == 1
    assert calendar.dayKey(calendar.dayNumber("2026-03-29")+1) == "2026-03-30"


def test_cross_month_hover_and_outside_drop(calendar_ui, app):
    root, _, _, calendar, _, _ = calendar_ui
    calendar.setProperty("goals", [dict(id="a", name="Move across months", color="", startDate="2032-02-28", endDate="2032-02-29")])
    app.processEvents()
    changes = []
    calendar.rangeEdited.connect(lambda gid, a, b: changes.append((gid, a, b)))
    bar = find(root, "goalBar_a_5")
    start = bar.mapToScene(QPointF(30,11)).toPoint()
    next_month = find(root, "reminderNextMonth")
    arrow = next_month.mapToScene(next_month.boundingRect().center()).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, arrow, 20)
    QTest.qWait(700)
    assert calendar.property("displayedMonth") == 2
    target = find(root, "reminderDay_2032-03-08")
    end = target.mapToScene(QPointF(30,15)).toPoint()
    QTest.mouseMove(root, end, 20)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    assert changes == [("a", "2032-03-08", "2032-03-09")]
    # Outside the calendar cancels without creating a second mutation.
    calendar.setProperty("goals", [dict(id="a", name="Moved", color="", startDate="2032-03-08", endDate="2032-03-09")])
    app.processEvents()
    bar = find(root, "goalBar_a_0")
    start = bar.mapToScene(QPointF(30,11)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, QPoint(1,1), 20)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, QPoint(1,1))
    assert len(changes) == 1


@pytest.mark.parametrize("date", ["2032-02-10", "2032-01-31"])
@pytest.mark.parametrize("save", [False, True])
def test_day_double_click_creates_goal(calendar_ui, app, date, save):
    root, host, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab("Main")
    overview.setProperty("goalModel", tabs)
    dialog = overview.findChild(QObject, "goalRangeDialog")
    opened = []
    dialog.opened.connect(lambda: opened.append(True))
    day = find(root, "reminderDay_" + date)
    point = day.mapToScene(QPointF(day.width()/2, 15)).toPoint()
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    app.processEvents()
    assert overview.property("selectedDate") == date
    assert not dialog.property("visible")
    QTest.mouseDClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(200)
    assert dialog.property("visible")
    assert opened == [True]
    assert dialog.findChild(QObject, "goalRangeStart").property("text") == date
    assert dialog.findChild(QObject, "goalRangeEnd").property("text") == date
    name = dialog.findChild(QObject, "goalRangeName")
    assert name.property("activeFocus")
    assert name.property("text") == ""
    assert tabs.tabCount == 1
    name.setProperty("text", "Calendar goal")
    if save:
        dialog.findChild(QObject, "goalRangeEnd").setProperty("text", "2032-03-02")
    click("saveGoalRange" if save else "cancelGoalRange")
    assert not dialog.property("visible")
    assert tabs.tabCount == (2 if save else 1)
    if save:
        assert len(tabs.scheduledGoals) == 1
        assert tabs.scheduledGoals[0]["startDate"] == date
        assert tabs.scheduledGoals[0]["endDate"] == "2032-03-02"
        assert host.property("action") == "open-goal-1"
    overview.setProperty("goalModel", None)


def test_goal_bar_double_click_does_not_create_goal(calendar_ui, app):
    root, _, overview, calendar, _, _ = calendar_ui
    calendar.setProperty("goals", [dict(id="a", name="Existing", color="",
                                       startDate="2032-02-10", endDate="2032-02-12")])
    app.processEvents()
    requests = []
    calendar.dateDoubleClicked.connect(requests.append)
    bar = find(root, "goalBar_a_1")
    point = bar.mapToScene(QPointF(bar.width()/2, 11)).toPoint()
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.mouseDClick(root, Qt.LeftButton, Qt.NoModifier, point)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, point)
    app.processEvents()
    assert not requests
    assert not overview.findChild(QObject, "goalRangeDialog").property("visible")


def test_overview_goal_selection_dialog_and_open(calendar_ui, app):
    root, host, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab("Main")
    overview.setProperty("goalModel", tabs)
    goal = tabs.createScheduledGoal("Completed goal", "2032-02-01", "2032-02-29")
    tabs.setKanbanPlacement(tabs.goalIndex(goal), "done", -1)
    app.processEvents()
    click("reminderDay_2032-02-29")
    assert [g["id"] for g in value(overview, "filteredGoals")] == [goal]
    click("openGoal_" + goal)
    click("openCalendarActivity")
    assert host.property("action") == "open-goal-1"
    dialog = overview.findChild(QObject, "goalRangeDialog")
    dialog.show(None, "2032-02-29")
    app.processEvents()
    assert dialog.findChild(QObject, "goalRangeStart").property("text") == "2032-02-29"
    dialog.findChild(QObject, "goalRangeName").setProperty("text", "New dated goal")
    dialog.findChild(QObject, "goalRangeEnd").setProperty("text", "2032-02-28")
    click("saveGoalRange")
    assert dialog.property("visible")
    assert tabs.tabCount == 2
    dialog.findChild(QObject, "goalRangeEnd").setProperty("text", "2032-03-02")
    click("saveGoalRange")
    assert not dialog.property("visible")
    assert tabs.tabCount == 3
    assert len(value(overview, "filteredGoals")) == 2
    tabs.clearGoalRange(goal)
    app.processEvents()
    assert len(value(overview, "filteredGoals")) == 1
    # Detach before the Python QObject leaves scope.
    overview.setProperty("goalModel", None)


@pytest.mark.parametrize("enter_key", [Qt.Key_Return, Qt.Key_Enter])
def test_date_picker_and_enter_save(calendar_ui, app, enter_key):
    root, _, overview, _, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab("Main")
    overview.setProperty("goalModel", tabs)
    dialog = overview.findChild(QObject, "goalRangeDialog")
    dialog.show(None, "2032-02-28")
    QTest.qWait(30)
    # Enter uses validation and keeps an unnamed goal open.
    QTest.keyClick(root, enter_key)
    assert dialog.property("visible")
    assert tabs.tabCount == 1
    dialog.findChild(QObject, "goalRangeName").setProperty("text", "Picked dates")
    click("goalRangeStart")
    picker = dialog.findChild(QObject, "goalDatePicker")
    assert picker.property("visible")
    click("goalDateDay_29")
    assert not picker.property("visible")
    assert dialog.findChild(QObject, "goalRangeStart").property("text") == "2032-02-29"
    click("goalRangeEnd")
    click("goalDateNextMonth")
    assert picker.property("month") == 2
    # Enter inside the date popup activates its focused control, without saving the goal.
    day = find(root, "goalDateDay_2")
    day.forceActiveFocus()
    QTest.keyClick(root, enter_key)
    app.processEvents()
    assert dialog.property("visible")
    assert tabs.tabCount == 1
    assert not picker.property("visible")
    assert dialog.findChild(QObject, "goalRangeEnd").property("text") == "2032-03-02"
    QTest.keyClick(root, enter_key)
    app.processEvents()
    assert not dialog.property("visible")
    assert tabs.tabCount == 2
    assert tabs.scheduledGoals[0]["startDate"] == "2032-02-29"
    assert tabs.scheduledGoals[0]["endDate"] == "2032-03-02"
    # Editing also saves from the date button using Enter.
    dialog.show(tabs.scheduledGoals[0], "")
    QTest.qWait(30)
    QTest.keyClick(root, enter_key)
    assert not dialog.property("visible")
    assert tabs.tabCount == 2
    overview.setProperty("goalModel", None)


def test_mindmap_created_goal_appears_in_calendar(calendar_ui, app):
    from actiondraw.mindmap import MindMapController

    root, _, overview, calendar, _, _ = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    mindmap = MindMapController(tabs)
    mindmap.addThought(False)
    mindmap.editSelected('From mindmap', '')
    overview.setProperty('goalModel', tabs)
    goal = mindmap.createScheduledGoalFromNode(mindmap.selectedId, '2032-02-28', '2032-03-02')
    app.processEvents()
    assert [g['id'] for g in value(overview, 'filteredGoals')] == [goal]
    assert find(root, 'reminderDay_2032-02-28').property('goalsCount') == 1
    assert find(root, 'reminderDay_2032-02-29').property('goalsCount') == 1
    overview.setProperty('goalModel', None)


@pytest.mark.parametrize('count', [0, 2, 10, 50])
def test_dense_calendar_overflow_and_agenda(calendar_ui, app, count):
    root, _, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    overview.setProperty('goalModel', tabs)
    for i in range(count):
        tabs.createScheduledGoal('Goal %02d' % i, '2032-02-01', '2032-03-02')
    app.processEvents()
    weeks = value(calendar, 'weeks')
    assert calendar.property('gridHeight') == 600
    assert all(w['height'] == 100 for w in weeks)
    assert all(len(w['bars']) <= 2 for w in weeks)
    assert len(value(overview, 'filteredGoals')) == count
    more = find(root, 'calendarMore_2032-02-29')
    assert more.property('hiddenGoals') == max(0, count - 2)
    assert more.isVisible() == (count > 2)
    if count > 2:
        click('calendarMore_2032-02-29')
        popup = overview.findChild(QObject, 'calendarOverflow')
        assert popup.property('visible')
        assert len(value(popup, 'activities')) == count
        assert len(value(overview, 'filteredGoals')) == count
        tabs.clearGoalRange(tabs.scheduledGoals[-1]['id'])
        app.processEvents()
        assert more.property('hiddenGoals') == count - 3
        assert len(value(overview, 'filteredGoals')) == count - 1
    overview.setProperty('goalModel', None)


def test_calendar_lane_order_is_stable(calendar_ui, app):
    root, _, overview, calendar, _, _ = calendar_ui
    goals = [dict(id=key, name=key, color='', startDate='2032-02-10', endDate='2032-02-12')
             for key in ['c', 'b', 'a']]
    calendar.setProperty('goals', goals)
    app.processEvents()
    assert [b['goal']['id'] for b in value(calendar, 'weeks')[2]['bars']] == ['a', 'b']
    calendar.setProperty('goals', list(reversed(goals)))
    app.processEvents()
    assert [b['goal']['id'] for b in value(calendar, 'weeks')[2]['bars']] == ['a', 'b']
    # The hidden third lane cannot capture a background double-click on another day.
    day = find(root, 'reminderDay_2032-02-09')
    point = day.mapToScene(QPointF(day.width()/2, 63)).toPoint()
    QTest.mouseDClick(root, Qt.LeftButton, Qt.NoModifier, point)
    app.processEvents()
    assert overview.findChild(QObject, 'goalRangeDialog').property('visible')


def test_agenda_goal_actions_update_calendar(calendar_ui, app):
    root, _, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    overview.setProperty('goalModel', tabs)
    goal = tabs.createScheduledGoal('Release', '2032-02-28', '2032-02-29')
    app.processEvents()
    click('goalActions_' + goal)
    click('editGoalRange_' + goal)
    dialog = overview.findChild(QObject, 'goalRangeDialog')
    assert dialog.property('visible')
    dialog.findChild(QObject, 'goalRangeEnd').setProperty('text', '2032-03-02')
    click('saveGoalRange')
    assert find(root, 'reminderDay_2032-03-02').property('goalsCount') == 1
    click('goalActions_' + goal)
    click('clearGoalRange_' + goal)
    assert not value(overview, 'filteredGoals')
    assert find(root, 'reminderDay_2032-03-02').property('goalsCount') == 0
    assert tabs.tabCount == 2
    overview.setProperty('goalModel', None)
