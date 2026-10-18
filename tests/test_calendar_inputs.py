"""Sidebar calendar drops and priority-plot planning use existing goal identities."""
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest

from test_mindmap import project
from test_reminder_calendar import find


def click(window, item, button=Qt.LeftButton):
    QTest.mouseClick(window, button, Qt.NoModifier,
                     item.mapToScene(item.boundingRect().center()).toPoint())
    QTest.qWait(40)


@pytest.mark.parametrize('existing,cancel', [(False, False), (True, False), (False, True)])
def test_sidebar_pointer_drop_on_calendar(project, actiondraw_window, existing, cancel):
    pm, tabs, tasks, diagram = project
    tabs.addTab('Calendar drop')
    goal = tabs.getAllTabs()[1].id
    if existing:
        tabs.setGoalRange(goal, '2032-02-10', '2032-02-12')
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    window.setProperty('reminderOverviewExpanded', True)
    pm.showMindmap()
    calendar = find(window, 'reminderCalendar')
    calendar.setProperty('displayedYear', 2032)
    calendar.setProperty('displayedMonth', 1)
    QTest.qWait(100)
    source = find(window, 'sidebarGoal_1')
    day = find(window, 'reminderDay_2032-01-31')
    start = source.mapToScene(source.boundingRect().center()).toPoint()
    end = day.mapToScene(QPointF(day.width()/2, 10)).toPoint()
    changes = []
    tabs.scheduledGoalsChanged.connect(lambda: changes.append(True))
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, start + QPoint(12, 0), 30)
    QTest.mouseMove(window, end, 30)
    assert calendar.property('externalDropDate') == '2032-01-31'
    if cancel:
        QTest.keyClick(window, Qt.Key_Escape)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
    QTest.qWait(50)
    assert not calendar.property('externalDropDate')
    assert tabs.tabCount == 2
    if cancel:
        assert not changes
        assert not tabs.scheduledGoals
    else:
        assert len(changes) == 1
        summary = tabs.getTabSummary(tabs.goalIndex(goal))
        assert summary['goalStartDate'] == '2032-01-31'
        assert summary['goalEndDate'] == ('2032-02-02' if existing else '2032-01-31')
    window.close()


def test_goal_plan_api_targets_id_without_changing_selection(project):
    pm, tabs, _, _ = project
    tabs.addTab('Target')
    goal = tabs.getAllTabs()[1].id
    m = pm.mindmap
    selected = list(m.selectedIds)
    node = next(node for node, tab in m.links.items() if tab == goal)
    today = datetime.now().date().isoformat()
    assert m.addGoalToReady(goal)
    assert tabs.getTabSummary(tabs.goalIndex(goal))['kanbanStatus'] == 'ready'
    assert m.plan_ranges[node] == {'startDate': today, 'endDate': today}
    assert m.addGoalToPlan(goal, 10)
    assert tabs.getAllTabs()[tabs.goalIndex(goal)].kanban_slot_hour == 10
    assert m.scheduleGoalToWeekday(goal, (datetime.now().weekday() + 1) % 7)
    assert node in m.plan_schedules
    assert list(m.selectedIds) == selected
    assert not m.addGoalToReady('deleted')
    assert not m.addGoalToPlan(goal, 25)
    assert not m.scheduleGoalToWeekday(goal, 7)


def test_priority_plot_plan_menu_preserves_target_after_reorder(project, actiondraw_window):
    pm, tabs, tasks, diagram = project
    tabs.addTab('Target')
    goal = tabs.getAllTabs()[1].id
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.openPriorityPlotWindow()
    plot = window.property('priorityPlotWindowRef')
    QTest.qWait(80)
    selected = list(pm.mindmap.selectedIds)
    click(plot, find(plot, 'priorityAddToPlan_1'))
    menu = plot.findChild(QObject, 'priorityGoalPlanMenu')
    assert menu.property('visible')
    tabs.moveTab(1, 0)
    QTest.qWait(30)
    click(plot, find(plot, 'goalPlanReady'))
    assert tabs.getAllTabs()[tabs.goalIndex(goal)].kanban_status == 'ready'
    assert list(pm.mindmap.selectedIds) == selected
    # Right-click must open planning without moving the priority point.
    tabs.setPriorityPoint(tabs.goalIndex(goal), 3.0, 7.0)
    QTest.qWait(40)
    index = tabs.goalIndex(goal)
    tab = tabs.getAllTabs()[index]
    before = (tab.priority_time_hours, tab.priority_subjective_value)
    click(plot, find(plot, 'priorityPlotPoint_' + str(index)), Qt.RightButton)
    assert menu.property('visible')
    assert menu.property('goalId') == goal
    tab = tabs.getAllTabs()[tabs.goalIndex(goal)]
    assert (tab.priority_time_hours, tab.priority_subjective_value) == before
    weekday = (datetime.now().weekday() + 1) % 7
    click(plot, find(plot, 'goalPlanWeekday_' + str(weekday)))
    node = next(node for node, tab in pm.mindmap.links.items() if tab == goal)
    assert node in pm.mindmap.plan_schedules
    plot.close()
    window.close()


@pytest.mark.parametrize('target', ['header', 'drawing'])
def test_sidebar_drop_routes_calendar_and_drawing_separately(project, actiondraw_window, target):
    pm, tabs, tasks, diagram = project
    tabs.addTab('Drop target')
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    window.setProperty('reminderOverviewExpanded', True)
    pm.showTabCanvas()
    QTest.qWait(100)
    source = find(window, 'sidebarGoal_1')
    destination = find(window, 'diagramViewport' if target == 'drawing' else 'reminderOverview')
    local = destination.boundingRect().center() if target == 'drawing' else QPointF(15, 12)
    start = source.mapToScene(source.boundingRect().center()).toPoint()
    end = destination.mapToScene(local).toPoint()
    before = diagram.rowCount()
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, start + QPoint(12, 0), 30)
    QTest.mouseMove(window, end, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
    QTest.qWait(50)
    assert not tabs.scheduledGoals
    assert diagram.rowCount() == before + (1 if target == 'drawing' else 0)
    window.close()
