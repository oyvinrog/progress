"""Due alerts retain their civil day and promote their own source exactly once."""
import os
import time
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt
from PySide6.QtTest import QTest

from progress_crypto import EncryptionCredentials
from task_model import StandaloneReminder
from test_mindmap import project, thought


@pytest.fixture
def alerts(project, monkeypatch):
    pm = project[0]
    pm._reminder_timer.stop()
    project[2]._timer.stop()
    monkeypatch.setattr(pm, '_save_after_reminder', lambda: None)
    events = []
    pm.dueReminder.connect(events.append)
    return events


def goal_for(tabs, goal_id):
    return next(g for g in tabs.scheduledGoals if g['id'] == goal_id)


@pytest.mark.parametrize('clock', ['2026-03-29 00:05', '2026-03-29 23:55',
                                    '2025-10-26 00:05', '2025-10-26 23:55'])
def test_standalone_original_local_day_and_idempotency(project, alerts, clock):
    previous = os.environ.get('TZ')
    os.environ['TZ'] = 'Europe/Oslo'
    time.tzset()
    try:
        pm, tabs, _, _ = project
        stamp = datetime.strptime(clock, '%Y-%m-%d %H:%M').timestamp()
        pm._standalone_reminders = [StandaloneReminder('Remember this', stamp)]
        pm._checkStandaloneReminders()
        event, = alerts
        assert event['scheduledDate'] == clock[:10]
        assert not pm._standalone_reminders
        goal_id = pm.convertDueReminderToGoal(event['conversionId'])
        goal = goal_for(tabs, goal_id)
        assert goal['startDate'] == goal['endDate'] == clock[:10]
        count = tabs.tabCount
        assert pm.convertDueReminderToGoal(event['conversionId']) == goal_id
        assert tabs.tabCount == count
        pm.releaseDueReminder(event['conversionId'])
        assert not pm.convertDueReminderToGoal(event['conversionId'])
        assert tabs.tabCount == count
    finally:
        if previous is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = previous
        time.tzset()


@pytest.mark.parametrize('background', [False, True])
@pytest.mark.parametrize('reuse', [False, True])
def test_task_conversion_survives_switch_and_tab_reordering(project, alerts, background, reuse):
    pm, tabs, tasks, _ = project
    stamp = datetime(2025, 1, 2, 23, 59).timestamp()
    tasks.from_dict({'tasks': [
        dict(title='Task goal', reminder_at=stamp),
        dict(title='Child', indent_level=1, parent_index=0, time_spent=12),
    ]})
    source = tabs.getAllTabs()[0]
    tabs.addTab('Elsewhere')
    if reuse:
        existing = tabs.createScheduledGoal('Task goal', '2025-02-01', '2025-02-10')
        tabs.setKanbanPlacement(tabs.goalIndex(existing), 'ready', -1)
    legacy = []
    pm.taskReminderDue.connect(lambda *args: legacy.append(args))
    if background:
        pm.switchTab(1)
        pm._checkBackgroundTabReminders()
    else:
        tasks._updateActiveTasks()
        pm.switchTab(1)
    event, = alerts
    assert len(legacy) == 1
    tabs.moveTab(0, 1)
    active = tabs.getAllTabs()[tabs.currentTabIndex]
    goal_id = pm.convertDueReminderToGoal(event['conversionId'])
    goal = goal_for(tabs, goal_id)
    assert goal['startDate'] == goal['endDate'] == '2025-01-02'
    assert tabs.getAllTabs()[tabs.currentTabIndex] is active
    assert source.tasks['tasks'][0]['title'] == 'Task goal'
    target = tabs.getAllTabs()[tabs.goalIndex(goal_id)]
    if reuse:
        assert goal_id == existing
        assert target.kanban_status == 'ready'
    else:
        assert target.tasks['tasks'][0]['title'] == 'Child'
        assert target.tasks['tasks'][0]['parent_index'] == -1
        assert target.tasks['tasks'][0]['time_spent'] == pytest.approx(12, abs=0.01)


@pytest.mark.parametrize('linked', [False, True])
def test_mindmap_promotion_preserves_branch_and_notes(project, alerts, linked):
    pm, tabs, _, _ = project
    node_id = thought(pm.mindmap, 'Mindmap goal', 'Keep these notes')
    node = pm.mindmap.map.find(node_id)
    child = node.add_child('Keep child')
    if linked:
        existing = pm.mindmap.createScheduledGoalFromNode(node_id, '2025-02-01', '2025-02-10')
    pm.mindmap.set_reminder(node_id, datetime(2025, 1, 2).timestamp())
    pm._checkMindmapReminders()
    goal_id = pm.convertDueReminderToGoal(alerts[0]['conversionId'])
    assert goal_for(tabs, goal_id)['startDate'] == '2025-01-02'
    assert pm.mindmap.links[node_id] == goal_id
    assert pm.mindmap.map.find(child.id) is not None
    assert pm.mindmap.map.find(node_id).note == 'Keep these notes'
    if linked:
        assert goal_id == existing
    assert node_id not in pm.mindmap.reminders


@pytest.mark.parametrize('change', ['deleted', 'ambiguous', 'tab_deleted', 'project_closed'])
def test_unavailable_source_does_not_create_goal(project, alerts, change):
    pm, tabs, tasks, _ = project
    tasks.from_dict({'tasks': [dict(title='Source', reminder_at=1)]})
    tasks._updateActiveTasks()
    if change == 'deleted':
        tasks.clear()
    elif change == 'ambiguous':
        tasks.addTask('Source')
    elif change == 'tab_deleted':
        tabs.addTab('Other')
        pm.switchTab(1)
        tabs.removeTab(0)
    else:
        pm.projectAccessEnding.emit()
    errors = []
    pm.errorOccurred.connect(errors.append)
    assert not pm.convertDueReminderToGoal(alerts[0]['conversionId'])
    assert not tabs.scheduledGoals
    assert errors


def test_converted_goal_save_load(project, alerts, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    monkeypatch.setattr(pm, '_prompt_encryption_credentials',
                        lambda *args: EncryptionCredentials(passphrase='test'))
    pm._standalone_reminders = [StandaloneReminder('Saved goal', 1)]
    pm._checkStandaloneReminders()
    goal_id = pm.convertDueReminderToGoal(alerts[0]['conversionId'])
    expected = goal_for(tabs, goal_id)
    path = tmp_path / 'converted.progress'
    assert pm.saveProject(str(path))
    pm.loadProject(str(path))
    assert goal_for(tabs, goal_id) == expected
    assert not pm._due_reminders


def test_popup_conversion_queue_failure_and_plan_notification(project, alerts, actiondraw_window):
    pm, tabs, tasks, diagram = project
    node_id = thought(pm.mindmap, 'First goal')
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    window = engine.rootObjects()[0]
    window.show()
    QTest.qWait(80)
    try:
        pm.mindmap.set_reminder(node_id, 1)
        pm._checkMindmapReminders()
        pm._standalone_reminders = [StandaloneReminder('Second goal', 2)]
        pm._checkStandaloneReminders()
        QTest.qWait(80)
        popup = window.findChild(QObject, 'reminderDuePopup')
        button = window.findChild(QObject, 'convertDueReminderToGoal')
        assert popup.property('visible') and button.isVisible()
        popup.setProperty('width', 240)
        QTest.qWait(30)
        assert button.width() <= 240
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                         button.mapToScene(button.boundingRect().center()).toPoint())
        QTest.qWait(100)
        assert window.property('pendingReminderTaskTitle') == 'Second goal'
        assert pm.mindmap.links[node_id]
        QMetaObject.invokeMethod(button, 'clicked')
        QTest.qWait(100)
        assert not popup.property('visible')
        assert len(tabs.scheduledGoals) == 2
        assert not pm._due_reminders

        # Missing source leaves the current popup available for Renew/Dismiss.
        pm._emitDueReminder('mindmap', 'Missing', False, 1, nodeId='missing')
        QTest.qWait(60)
        QMetaObject.invokeMethod(button, 'clicked')
        QTest.qWait(60)
        assert popup.property('visible')
        assert len(tabs.scheduledGoals) == 2
        QMetaObject.invokeMethod(popup, 'close')
        QTest.qWait(60)

        # Plan notifications still open a popup, without a conversion action.
        pm._emitDueReminder('mindmap', 'Plan ready', True, nodeId=node_id)
        QTest.qWait(60)
        assert popup.property('visible')
        assert not button.isVisible()
        QMetaObject.invokeMethod(popup, 'close')
        assert not warnings
    finally:
        window.close()
