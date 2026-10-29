"""Daily-list dragging moves schedules without navigating the map."""
from datetime import datetime

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

from test_mindmap import project, thought
from test_reminder_calendar import calendar_ui, find, value


@pytest.mark.parametrize('kind', ['task', 'background', 'standalone', 'mindmap', 'kanban_schedule'])
def test_move_reminder_preserves_time_and_flags(project, kind):
    pm, tabs, tasks, _ = project
    when = '2032-02-28 18:35:12'
    if kind in ('task', 'background'):
        tasks.addTask('Move me')
        tasks.setReminderAt(0, when, True)
        if kind == 'background':
            tabs.addTab('Other')
            pm.switchTab(1)
    elif kind == 'standalone':
        pm.addStandaloneReminder('Move me', when, True)
    else:
        node = thought(pm.mindmap)
        if kind == 'mindmap':
            pm.setMindmapReminder(node, when, True)
        else:
            pm.mindmap.plan_schedules[node] = {'at': datetime.fromisoformat(when).timestamp()}
            pm.mindmap.setGoalRange('plan:' + node, '2032-02-28', '2032-03-01')
    entry = pm.getActiveReminders()[0]
    assert not pm.moveCalendarReminder(entry, '2000-01-01')
    assert not pm.moveCalendarReminder(entry, 'invalid')
    assert pm.moveCalendarReminder(entry, '2032-02-29')
    moved = pm.getActiveReminders()[0]
    assert datetime.fromtimestamp(moved['reminderAt']) == datetime(2032, 2, 29, 18, 35, 12)
    assert moved['sendNotification']
    assert not pm.moveCalendarReminder(entry, '2032-03-01')
    if kind == 'background':
        assert tabs.currentTabIndex == 1
    if kind == 'kanban_schedule':
        assert pm.mindmap.plan_ranges[node] == {'startDate': '2032-02-29', 'endDate': '2032-03-02'}


@pytest.mark.parametrize('outcome', ['move', 'outside', 'escape'])
def test_drag_goal_from_open_list(calendar_ui, project, app, outcome):
    pm, tabs, _, _ = project
    root, _, overview, _, _, click = calendar_ui
    overview.setProperty('goalModel', tabs)
    overview.setProperty('planController', pm.mindmap)
    goal = tabs.createScheduledGoal('Move me', '2032-02-28', '2032-03-01')
    click('closePlanningMonth')
    overview.setProperty('weekStart', '2032-02-23')
    overview.selectDate('2032-02-28')
    click('weekAgenda_2032-02-28')
    handle = find(root, 'dragGoal_' + goal)
    start = handle.mapToScene(handle.boundingRect().center()).toPoint()
    target = find(root, 'weekDay_2032-02-29')
    end = target.mapToScene(QPointF(target.width()/2, 10)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, start + QPointF(15, 0).toPoint(), 30)
    QTest.mouseMove(root, end, 30)
    assert value(overview, 'agendaDrag') is not None
    if outcome == 'escape':
        QTest.keyClick(root, Qt.Key_Escape)
    elif outcome == 'outside':
        end = QPointF(10, root.height() - 10).toPoint()
        QTest.mouseMove(root, end, 30)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    QTest.qWait(50)
    assert value(overview, 'agendaDrag') is None
    expected = '2032-02-29' if outcome == 'move' else '2032-02-28'
    assert tabs.scheduledGoals[0]['startDate'] == expected
    assert tabs.scheduledGoals[0]['endDate'] == ('2032-03-02' if outcome == 'move' else '2032-03-01')
    assert overview.property('selectedDate') == '2032-02-28'
    assert pm.mindmap.dateFilter == '2032-02-28'
    assert overview.property('agendaDate') == expected
    overview.setProperty('goalModel', None)
    overview.setProperty('planController', None)


@pytest.mark.parametrize('kind', ['task', 'standalone', 'mindmap', 'kanban_schedule'])
def test_drag_reminder_row(calendar_ui, project, app, kind):
    pm, _, tasks, _ = project
    root, _, overview, _, refresh, click = calendar_ui
    overview.setProperty('projectManager', pm)
    when = '2032-02-28 18:35:12'
    node = ''
    if kind == 'task':
        tasks.addTask('Move')
        tasks.setReminderAt(0, when, True)
    elif kind == 'standalone':
        pm.addStandaloneReminder('Move', when, True)
    else:
        node = thought(pm.mindmap)
        if kind == 'mindmap':
            pm.setMindmapReminder(node, when, True)
        else:
            pm.mindmap.plan_schedules[node] = {'at': datetime.fromisoformat(when).timestamp()}
    refresh(pm.getActiveReminders())
    click('closePlanningMonth')
    overview.setProperty('weekStart', '2032-02-23')
    click('weekAgenda_2032-02-28')
    suffix = ('plan_' if kind == 'kanban_schedule' else '') + (node or kind)
    handle = find(root, 'dragReminder_' + suffix)
    start = handle.mapToScene(handle.boundingRect().center()).toPoint()
    target = find(root, 'weekDay_2032-02-29')
    end = target.mapToScene(QPointF(target.width()/2, 10)).toPoint()
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, start + QPointF(15, 0).toPoint(), 20)
    QTest.mouseMove(root, end, 20)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    QTest.qWait(50)
    moved = pm.getActiveReminders()[0]
    assert datetime.fromtimestamp(moved['reminderAt']) == datetime(2032, 2, 29, 18, 35, 12)
    assert overview.property('agendaDate') == '2032-02-29'
    assert not overview.property('deletionError')
    refresh(pm.getActiveReminders())
    assert find(root, 'reminderRow_' + suffix).isVisible()
    overview.setProperty('projectManager', None)
