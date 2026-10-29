"""Compact planning stays bounded and independent of map navigation."""
import pytest
from PySide6.QtCore import QObject, QPointF, Qt
from PySide6.QtTest import QTest, QSignalSpy

from test_mindmap import project
from test_reminder_calendar import calendar_ui, find, reminder, value


def test_week_navigation_selection_agenda_and_updates(calendar_ui, app):
    root, _, overview, calendar, refresh, click = calendar_ui
    click('closePlanningMonth')
    assert not overview.property('planningOpen')
    overview.setProperty('weekStart', '2031-12-29')
    click('nextWeek')
    assert overview.property('weekStart') == '2032-01-05'
    click('previousWeek')
    assert overview.property('weekStart') == '2031-12-29'
    click('weekToday')
    assert overview.property('weekStart') == '2032-02-23'
    refresh([reminder('2032-02-28T18:00:00')])
    assert not overview.property('planningOpen')
    click('weekAgenda_2032-02-28')
    popup = overview.findChild(QObject, 'weekAgendaPopup')
    assert popup.property('visible')
    assert find(root, 'reminderRow_task').isVisible()
    click('reminderActions_task')
    click('editReminder_task')
    assert popup.property('visible')
    QTest.keyClick(root, Qt.Key_Escape)
    click('clearWeekDate')
    assert overview.property('selectedDate') == ''
    day = find(root, 'weekDay_2032-02-29')
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, day.mapToScene(QPointF(day.width()/2, 10)).toPoint())
    assert overview.property('selectedDate') == '2032-02-29'
    click('openPlanningMonth')
    assert overview.property('planningOpen')
    assert calendar.property('displayedMonth') == 1
    click('closePlanningMonth')
    assert overview.property('selectedDate') == '2032-02-29'
    assert find(root, 'openPlanningMonth').hasActiveFocus()


@pytest.mark.parametrize('width,height', [(1200, 800), (600, 850), (1000, 420)])
def test_full_window_week_strip_preserves_map(project, actiondraw_window, app, tmp_path, width, height):
    pm, tabs, tasks, diagram = project
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.setWidth(width); window.setHeight(height)
    pm.showMindmap()
    window.show()
    QTest.qWait(120)
    overview = find(window, 'reminderOverview')
    pane = find(window, 'mindmapPane')
    assert not overview.property('planningOpen')
    expected = 88 if overview.property('availableContentHeight') < 600 else 104
    assert overview.height() == expected
    assert pane.height() > height * .5
    week = overview.property('weekStart')
    calendar = overview.findChild(QObject, 'reminderCalendar')
    n = calendar.dayNumber(week)
    for i in range(7):
        cell = find(window, 'weekDay_' + calendar.dayKey(n + i))
        p = cell.mapToScene(QPointF())
        assert p.x() >= 0 and p.x() + cell.width() <= width
        assert cell.width() > 30
    for i in range(50):
        tabs.createScheduledGoal('Scheduled activity %s' % i, week, calendar.dayKey(n + 6))
    QTest.qWait(60)
    assert overview.height() == expected
    assert not overview.property('planningOpen')
    assert window.grabWindow().save(str(tmp_path / ('week-%s-%s.png' % (width, height))))
    pane.setProperty('zoom', 0.5)
    before = (pane.x(), pane.y(), pane.width(), pane.height(), pane.property('panX'), pane.property('panY'), pane.property('zoom'))
    overview.openPlanning()
    QTest.qWait(60)
    assert window.grabWindow().save(str(tmp_path / ('month-%s-%s.png' % (width, height))))
    overlay = overview.findChild(QObject, 'planningOverlay')
    assert overlay.property('width') <= width - 32
    assert overlay.property('height') <= height - 32
    overlay.close()
    QTest.qWait(60)
    after = (pane.x(), pane.y(), pane.width(), pane.height(), pane.property('panX'), pane.property('panY'), pane.property('zoom'))
    assert after == before
    assert overview.height() == expected
    window.close()


def test_escape_cancels_drag_before_closing_month(calendar_ui, app):
    from task_model import TabModel
    root, _, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    tabs.createScheduledGoal('Move me', '2032-02-02', '2032-02-04')
    overview.setProperty('goalModel', tabs)
    app.processEvents()
    bar = find(root, 'goalBar_' + tabs.scheduledGoals[0]['id'] + '_0')
    p = bar.mapToScene(QPointF(40, 10)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, p)
    assert value(calendar, 'gesture') is not None
    QTest.keyClick(root, Qt.Key_Escape)
    assert value(calendar, 'gesture') is None
    assert overview.property('planningOpen')
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, p)
    QTest.keyClick(root, Qt.Key_Escape)
    QTest.qWait(30)
    assert not overview.property('planningOpen')
    overview.setProperty('goalModel', None)


def test_week_double_click_opens_bounded_goal_dialog(calendar_ui, app):
    from task_model import TabModel
    root, _, overview, _, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    overview.setProperty('goalModel', tabs)
    click('closePlanningMonth')
    day = find(root, 'weekDay_2032-02-29')
    p = day.mapToScene(QPointF(day.width()/2, 10)).toPoint()
    QTest.mouseDClick(root, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(40)
    dialog = overview.findChild(QObject, 'goalRangeDialog')
    assert dialog.property('visible')
    assert dialog.property('sourceStart') == '2032-02-29'
    assert dialog.property('y') >= 0
    assert dialog.property('y') + dialog.property('height') <= root.height()
    dialog.close()
    overview.setProperty('goalModel', None)


@pytest.mark.parametrize('dropdown_date', ['2032-02-28', '2032-02-29'])
def test_dropdown_browses_day_without_refreshing_map(project, calendar_ui, app, dropdown_date):
    pm, tabs, _, _ = project
    root, _, overview, _, refresh, click = calendar_ui
    overview.setProperty('planController', pm.mindmap)
    overview.setProperty('goalModel', tabs)
    goal_id = tabs.createScheduledGoal('Dropdown goal', dropdown_date, dropdown_date)
    refresh([reminder(dropdown_date + 'T18:00:00')])
    click('closePlanningMonth')
    overview.setProperty('weekStart', '2032-02-23')
    overview.selectDate('2032-02-28')
    scene = pm.mindmap.scene
    reset = QSignalSpy(pm.mindmap.resetView)
    changed = QSignalSpy(pm.mindmap.sceneChanged)
    click('weekAgenda_' + dropdown_date)
    assert overview.property('selectedDate') == '2032-02-28'
    assert pm.mindmap.dateFilter == '2032-02-28'
    assert pm.mindmap.scene == scene
    assert reset.count() == 0 and changed.count() == 0
    assert overview.property('agendaDate') == dropdown_date
    assert [g['id'] for g in value(overview, 'filteredGoals')] == [goal_id]
    assert len(value(overview, 'filteredReminders')) == 1
    assert find(root, 'reminderRow_task').isVisible()
    popup = overview.findChild(QObject, 'weekAgendaPopup')
    popup.close()
    app.processEvents()
    assert overview.property('agendaDate') == '2032-02-28'
    assert reset.count() == 0 and changed.count() == 0
    day = find(root, 'weekDay_' + dropdown_date)
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier,
                    day.mapToScene(QPointF(day.width()/2, 10)).toPoint())
    assert pm.mindmap.dateFilter == dropdown_date
    assert reset.count() == 1
    overview.setProperty('planController', None)
    overview.setProperty('goalModel', None)
