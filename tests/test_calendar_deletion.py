"""Calendar ticks delete sources, including branches and background tasks."""
import time
from datetime import datetime, timedelta

import pytest
from PySide6.QtCore import QObject

from test_mindmap import project, thought
from test_reminder_calendar import calendar_ui, find, value
from progress_crypto import EncryptionCredentials


def future():
    return (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d %H:%M')


@pytest.mark.parametrize('background', [False, True])
def test_delete_task_branch_and_reindex(project, background):
    pm, tabs, tasks, diagram = project
    tasks.from_dict({'tasks': [
        dict(title='Parent', indent_level=0, reminder_at=time.time() + 86400),
        dict(title='Child', indent_level=1, parent_index=0),
        dict(title='Survivor', indent_level=0),
        dict(title='Surviving child', indent_level=1, parent_index=2),
    ]})
    for i in range(4):
        diagram.addTask(i, i * 100, 0)
    payload = diagram.to_dict()
    payload['current_task_index'] = 2
    payload['edges'] = [dict(id='edge', from_id=payload['items'][0]['id'], to_id=payload['items'][2]['id'])]
    diagram.from_dict(payload)
    goal_id = tabs.getAllTabs()[0].id
    entry = pm.getActiveReminders()[0]
    if background:
        tabs.addTab('Other')
        pm.switchTab(1)
    assert pm.deleteCalendarItem(entry)
    assert not pm.deleteCalendarItem(entry)
    if background:
        assert tabs.currentTabIndex == 1
        pm.switchTab(tabs.goalIndex(goal_id))
    assert [t['title'] for t in tasks.to_dict()['tasks']] == ['Survivor', 'Surviving child']
    assert tasks.to_dict()['tasks'][1]['parent_index'] == 0
    result = diagram.to_dict()
    assert [item['task_index'] for item in result['items']] == [0, 1]
    assert not result['edges']
    assert result['current_task_index'] == 0
    assert not pm.getActiveReminders()


@pytest.mark.parametrize('kind', ['mindmap', 'kanban_schedule', 'goal'])
def test_delete_node_all_calendar_representations(project, kind):
    pm, tabs, _, _ = project
    m = pm.mindmap
    node_id = thought(m)
    child = m.map.find(node_id).add_child('Child').id
    assert pm.setMindmapReminder(node_id, future(), False)
    assert m.setGoalRange('plan:' + node_id, '2032-02-28', '2032-03-02')
    m.plan_schedules[node_id] = {'at': time.time() + 86400}
    m.select(m.map.root.id)
    entry = dict(kind='goal', id='plan:' + node_id) if kind == 'goal' else next(e for e in pm.getActiveReminders() if e['kind'] == kind)
    assert pm.deleteCalendarItem(entry)
    assert not pm.deleteCalendarItem(entry)
    assert m.map.find(node_id) is None and m.map.find(child) is None
    assert not m.plannedGoals and not pm.getActiveReminders()


def test_standalone_duplicate_and_stale_indices(project):
    pm, _, _, _ = project
    for _ in range(2):
        assert pm.addStandaloneReminder('Same', future(), False)
    entries = pm.getActiveReminders()
    assert pm.deleteCalendarItem(entries[0])
    assert not pm.deleteCalendarItem(entries[0])
    assert len(pm.getActiveReminders()) == 1
    assert pm.deleteCalendarItem(entries[1])
    assert not pm.getActiveReminders()


@pytest.mark.parametrize('via_node', [False, True])
def test_last_goal_deleted_and_persisted(project, via_node, tmp_path, monkeypatch):
    pm, tabs, tasks, _ = project
    tasks.addTask('Saved task')
    goal_id = tabs.getAllTabs()[0].id
    tabs.setGoalRange(goal_id, '2032-02-28', '2032-03-02')
    node_id = next(k for k, v in pm.mindmap.links.items() if v == goal_id)
    entry = dict(kind='mindmap', nodeId=node_id) if via_node else dict(kind='goal', id=goal_id)
    assert pm.deleteCalendarItem(entry)
    assert not pm.deleteCalendarItem(entry)
    assert tabs.tabCount == 0 and tasks.rowCount() == 0
    assert pm.mindmap.map.find(node_id) is None
    credentials = EncryptionCredentials(passphrase='calendar-deletion-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'deleted.progress'
    assert pm.saveProject(str(path))
    pm.loadProject(str(path))
    assert tabs.tabCount == 0 and not pm.getActiveReminders()


def test_calendar_checkbox_keeps_popup_open(project, calendar_ui, app):
    pm, tabs, _, _ = project
    root, host, overview, calendar, refresh, click = calendar_ui
    overview.setProperty('projectManager', pm)
    overview.setProperty('goalModel', tabs)
    goal_id = tabs.createScheduledGoal('Delete me', '2032-02-28', '2032-03-02')
    click('closePlanningMonth')
    overview.setProperty('weekStart', '2032-02-23')
    click('weekAgenda_2032-02-28')
    click('deleteGoal_' + goal_id)
    assert tabs.goalIndex(goal_id) == -1
    assert overview.findChild(QObject, 'weekAgendaPopup').property('visible')
    assert find(root, 'reminderEmptyDay').isVisible()
    assert not value(overview, 'filteredGoals')
    assert not overview.deleteAgendaItem(dict(kind='goal', id='missing'))
    assert find(root, 'calendarDeletionError').isVisible()
    overview.setProperty('goalModel', None)
    overview.setProperty('projectManager', None)


@pytest.mark.parametrize('kind', ['task', 'standalone', 'mindmap', 'kanban_schedule'])
def test_reminder_checkbox_deletes_source(project, calendar_ui, app, kind):
    pm, tabs, tasks, _ = project
    root, host, overview, calendar, refresh, click = calendar_ui
    overview.setProperty('projectManager', pm)
    date = '2032-02-28 18:00'
    node_id = ''
    if kind == 'task':
        tasks.addTask('Delete me')
        tasks.setReminderAt(0, date)
    elif kind == 'standalone':
        pm.addStandaloneReminder('Delete me', date, False)
    else:
        node_id = thought(pm.mindmap)
        if kind == 'mindmap':
            pm.setMindmapReminder(node_id, date, False)
        else:
            pm.mindmap.plan_schedules[node_id] = {'at': datetime.fromisoformat(date).timestamp()}
    refresh(pm.getActiveReminders())
    click('closePlanningMonth')
    overview.setProperty('weekStart', '2032-02-23')
    click('weekAgenda_2032-02-28')
    suffix = ('plan_' if kind == 'kanban_schedule' else '') + (node_id or kind)
    click('deleteReminder_' + suffix)
    assert not pm.getActiveReminders()
    assert not overview.property('deletionError')
    if kind == 'task':
        assert tasks.rowCount() == 0
    elif node_id:
        assert pm.mindmap.map.find(node_id) is None
    assert host.property('action') == 'refresh'
    refresh(pm.getActiveReminders())
    assert overview.findChild(QObject, 'weekAgendaPopup').property('visible')
    assert find(root, 'reminderEmptyDay').isVisible()
    overview.setProperty('projectManager', None)


@pytest.mark.parametrize('kind', ['task', 'standalone', 'mindmap'])
def test_reminder_deletion_survives_reload(project, tmp_path, monkeypatch, kind):
    pm, _, tasks, _ = project
    if kind == 'task':
        tasks.addTask('Remove')
        tasks.setReminderAt(0, future())
    elif kind == 'standalone':
        pm.addStandaloneReminder('Remove', future(), False)
    else:
        node_id = thought(pm.mindmap)
        pm.setMindmapReminder(node_id, future(), False)
    assert pm.deleteCalendarItem(pm.getActiveReminders()[0])
    credentials = EncryptionCredentials(passphrase='calendar-delete-reload')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'deleted.progress'
    assert pm.saveProject(str(path))
    pm.loadProject(str(path))
    assert not pm.getActiveReminders()
    assert tasks.rowCount() == 0
    if kind == 'mindmap':
        assert pm.mindmap.map.find(node_id) is None


def test_stale_task_entry_cannot_delete_replacement(project):
    pm, _, tasks, _ = project
    tasks.addTask('Old')
    tasks.setReminderAt(0, future())
    entry = pm.getActiveReminders()[0]
    tasks.from_dict({'tasks': [dict(title='Replacement')]})
    assert not pm.deleteCalendarItem(entry)
    assert tasks.to_dict()['tasks'][0]['title'] == 'Replacement'
