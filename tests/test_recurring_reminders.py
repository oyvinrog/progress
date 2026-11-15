"""Recurring delivery uses one future occurrence and preserves its anchor."""
import os
import time
from datetime import datetime

import pytest
from actiondraw.recurrence import repeat_rule, next_occurrence
from test_mindmap import project, thought


@pytest.mark.parametrize('unit,seconds', [('minutes', 60), ('hours', 3600), ('days', 86400), ('weeks', 604800)])
def test_intervals(unit, seconds, monkeypatch):
    monkeypatch.setenv('TZ', 'UTC')
    time.tzset()
    try:
        rule = repeat_rule(dict(interval=20, unit=unit), 1000000000)
        assert next_occurrence(rule, 1000000000 + 40 * seconds) == 1000000000 + 60 * seconds
    finally:
        monkeypatch.undo()
        time.tzset()


@pytest.mark.parametrize('value', [0, -1, True, 1.5, '2', 1000001])
def test_invalid_intervals(value):
    with pytest.raises(ValueError):
        repeat_rule(dict(interval=value, unit='minutes'), 1000)


@pytest.mark.parametrize('start,now,expected', [
    ('2026-03-28 02:30', '2026-03-28 02:30', '2026-03-29 03:30'),
    ('2026-03-28 02:30', '2026-03-29 04:00', '2026-03-30 02:30'),
    ('2026-10-24 02:30', '2026-10-24 02:30', '2026-10-25 02:30'),
])
@pytest.mark.parametrize('unit', ['days', 'weeks'])
def test_dst(start, now, expected, unit, monkeypatch):
    monkeypatch.setenv('TZ', 'Europe/Oslo')
    time.tzset()
    try:
        parse = lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M').timestamp()
        anchor = parse(start) - (6 * 86400 if unit == 'weeks' else 0)
        result = next_occurrence(repeat_rule(dict(interval=1, unit=unit), anchor), parse(now))
        if unit == 'weeks' and now == '2026-03-29 04:00':
            expected = '2026-04-05 02:30'
        assert datetime.fromtimestamp(result).strftime('%Y-%m-%d %H:%M') == expected
        if expected == '2026-10-25 02:30':
            assert time.localtime(result).tm_isdst == 1
    finally:
        monkeypatch.undo()
        time.tzset()


@pytest.mark.parametrize('kind', ['task', 'standalone', 'mindmap', 'background'])
def test_delivery_edit_move_reload_and_cancel(project, monkeypatch, kind):
    pm, tabs, tasks, _ = project
    pm._reminder_timer.stop()
    tasks._timer.stop()
    saves, events = [], []
    monkeypatch.setattr(pm, '_save_after_reminder', lambda: saves.append(True))
    pm.dueReminder.connect(events.append)
    now = time.time()
    stamp = datetime.fromtimestamp(now - 3600).strftime('%Y-%m-%d %H:%M')
    rule = dict(interval=20, unit='minutes')
    if kind == 'standalone':
        assert pm.addStandaloneReminder('Repeat', stamp, False, rule)
        check = pm._checkStandaloneReminders
    elif kind == 'mindmap':
        node = thought(pm.mindmap)
        assert pm.setMindmapReminder(node, stamp, False, rule)
        check = pm._checkMindmapReminders
    else:
        tasks.addTask('Repeat', -1)
        assert tasks.setReminderAt(0, stamp, False, rule)
        check = tasks._updateActiveTasks
        if kind == 'background':
            tabs.getAllTabs()[0].tasks = tasks.to_dict()
            tabs.addTab('Other')
            tabs.setCurrentTab(1)
            check = pm._checkBackgroundTabReminders
    check()
    check()
    assert len(events) == 1
    assert events[0]['repeat']['interval'] == 20
    assert saves
    entries = pm.getActiveReminders()
    entry, = entries
    assert now < entry['reminderAt'] <= now + 1200
    assert entry['repeatText'] == 'Every 20 minutes'
    assert pm.moveCalendarReminder(entry, '2099-01-02')
    moved, = pm.getActiveReminders()
    assert moved['repeat']['anchor'] == moved['reminderAt']
    if kind == 'standalone':
        pm._load_standalone_reminders(pm._serialize_standalone_reminders())
        assert pm.getActiveReminders()[0]['repeat'] == moved['repeat']
        pm.clearStandaloneReminder(0)
    elif kind == 'mindmap':
        pm.clearMindmapReminder(node)
        pm.mindmap.undo()
        assert pm.mindmap.reminders[node]['at'] > now
        pm.clearMindmapReminder(node)
    else:
        pm.clearReminder(entry['tabIndex'], 0)
    assert not pm.getActiveReminders()


@pytest.mark.parametrize('kind', ['task', 'mindmap', 'standalone'])
def test_dialog_round_trip(project, actiondraw_window, kind):
    from PySide6.QtCore import QObject, QMetaObject, Qt
    from PySide6.QtTest import QTest
    pm, tabs, tasks, diagram = project
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    dialog = window.findChild(QObject, 'reminderDialog')
    if kind == 'task':
        tasks.addTask('Task', -1)
        dialog.setProperty('taskIndex', 0)
    elif kind == 'mindmap':
        dialog.setProperty('nodeId', thought(pm.mindmap))
    else:
        dialog.setProperty('standaloneMode', True)
        dialog.setProperty('standaloneTitle', 'Repeat')
    dialog.setProperty('dateValue', '2099-01-01')
    dialog.setProperty('timeValue', '09:00')
    QMetaObject.invokeMethod(dialog, 'open', Qt.DirectConnection)
    QTest.qWait(30)
    mode = window.findChild(QObject, 'reminderRepeatMode')
    interval = window.findChild(QObject, 'reminderRepeatInterval')
    unit = window.findChild(QObject, 'reminderRepeatUnit')
    assert mode.property('currentIndex') == 0
    mode.setProperty('currentIndex', 1)
    interval.setProperty('value', 20)
    unit.setProperty('currentIndex', 0)
    QMetaObject.invokeMethod(dialog, 'accept', Qt.DirectConnection)
    QTest.qWait(30)
    entry, = pm.getActiveReminders()
    assert entry['repeat']['interval'] == 20
    assert entry['repeat']['unit'] == 'minutes'
    if kind == 'task':
        dialog.setProperty('taskIndex', 0)
    elif kind == 'mindmap':
        dialog.setProperty('nodeId', entry['nodeId'])
    else:
        dialog.setProperty('standaloneMode', True)
        dialog.setProperty('editStandaloneIndex', 0)
        dialog.setProperty('standaloneTitle', 'Repeat')
    QMetaObject.invokeMethod(dialog, 'open', Qt.DirectConnection)
    QTest.qWait(30)
    assert mode.property('currentIndex') == 1
    assert interval.property('value') == 20
    mode.setProperty('currentIndex', 0)
    QMetaObject.invokeMethod(dialog, 'accept', Qt.DirectConnection)
    QTest.qWait(30)
    assert pm.getActiveReminders()[0]['repeat'] == {}
    window.close()


def test_mindmap_delivery_history_and_conversion(project, monkeypatch):
    pm, tabs, tasks, _ = project
    pm._reminder_timer.stop()
    tasks._timer.stop()
    monkeypatch.setattr(pm, '_save_after_reminder', lambda: None)
    node = thought(pm.mindmap)
    stamp = datetime.fromtimestamp(time.time() - 60).strftime('%Y-%m-%d %H:%M')
    assert pm.setMindmapReminder(node, stamp, True, dict(interval=1, unit='hours'))
    notifications, alerts = [], []
    monkeypatch.setattr(pm, '_publishReminderNotification', lambda *a, **k: notifications.append(a))
    pm.dueReminder.connect(alerts.append)
    pm.mindmap.editSelected('Edited', '')
    pm._checkMindmapReminders()
    due = pm.mindmap.reminders[node]['at']
    pm.mindmap.undo()
    assert pm.mindmap.reminders[node]['at'] == due
    pm.mindmap.redo()
    pm._checkMindmapReminders()
    assert len(notifications) == 1
    assert pm.convertDueReminderToGoal(alerts[0]['conversionId'])
    assert pm.mindmap.reminders[node]['at'] == due
    payload = pm.mindmap.to_dict()
    pm.mindmap.load(payload)
    assert pm.mindmap.reminders[node]['repeat']['interval'] == 1


def test_quick_recurring_menu(project, actiondraw_window, monkeypatch):
    from PySide6.QtCore import QObject, QMetaObject, Qt
    pm, tabs, tasks, diagram = project
    node = thought(pm.mindmap)
    now = int(time.time())
    monkeypatch.setattr('task_model.time.time', lambda: now)
    pm.mindmap.set_reminder(node, now + 60, True)
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.findChild(QObject, 'mindmapNodeMenu').setProperty('targetNodeId', node)
    menu = window.findChild(QObject, 'mindmapRecurringReminderMenu')
    assert menu.property('title') == 'Recurring reminder'
    presets = [(10, 'minutes'), (20, 'minutes'), (30, 'minutes'),
               (1, 'hours'), (2, 'hours'), (4, 'hours'), (8, 'hours'),
               (12, 'hours'), (20, 'hours'), (1, 'days'), (2, 'days'), (1, 'weeks')]
    for interval, unit in presets:
        item = window.findChild(QObject, f'mindmapRecurringReminder{interval}{unit.title()}')
        assert item is not None
        assert QMetaObject.invokeMethod(item, 'triggered', Qt.DirectConnection)
        reminder = pm.mindmap.reminders[node]
        rule = repeat_rule(dict(interval=interval, unit=unit), now)
        assert reminder == dict(at=next_occurrence(rule, now), repeat=rule, send_notification=True)
    before = pm.mindmap.to_dict()
    assert not pm.setMindmapRecurringReminder(node, 0, 'minutes')
    assert not pm.setMindmapRecurringReminder(node, 1, 'months')
    assert not pm.setMindmapRecurringReminder('missing', 20, 'minutes')
    assert pm.mindmap.to_dict() == before
    window.close()


@pytest.mark.parametrize('kind', ['mindmap', 'task', 'standalone'])
def test_projected_calendar_occurrences(project, kind):
    pm, tabs, tasks, _ = project
    rule = dict(interval=20, unit='hours')
    if kind == 'mindmap':
        node = thought(pm.mindmap)
        pm.setMindmapReminder(node, '2099-01-01 09:00', False, rule)
    elif kind == 'task':
        tasks.addTask('Repeat', -1)
        tasks.setReminderAt(0, '2099-01-01 09:00', False, rule)
    else:
        pm.addStandaloneReminder('Repeat', '2099-01-01 09:00', False, rule)
    entries = pm.getActiveReminders()
    result = pm.projectCalendarReminders(entries, ['2099-01-01', '2099-01-02', '2099-01-03'], '2099-01-03')
    assert result['dayCounts'] == {'2099-01-01': 1, '2099-01-02': 1, '2099-01-03': 2}
    rows = result['reminders']
    assert [r['occurrenceText'] for r in rows] == ['2099-01-03 01:00', '2099-01-03 21:00']
    assert all(r['reminderAt'] == entries[0]['reminderAt'] for r in rows)
    assert pm.getActiveReminders() == entries
    # Moving a future projection still identifies and moves the live series.
    assert pm.moveCalendarReminder(rows[1], '2099-02-01')
    assert pm.getActiveReminders()[0]['reminderText'] == '2099-02-01 09:00'


def test_projected_daily_dst_and_dense_counts(project, monkeypatch):
    pm = project[0]
    monkeypatch.setenv('TZ', 'Europe/Oslo')
    time.tzset()
    try:
        for unit, interval, expected in [('days', 1, 1), ('minutes', 20, 69)]:
            anchor = datetime(2032, 3, 27, 9).timestamp()
            rule = repeat_rule(dict(interval=interval, unit=unit), anchor)
            entry = dict(reminderAt=anchor, repeat=rule)
            result = pm.projectCalendarReminders([entry], ['2032-03-28'], '2032-03-28')
            assert result['dayCounts']['2032-03-28'] == expected
            assert len(result['reminders']) == expected
            if unit == 'days':
                assert result['reminders'][0]['occurrenceText'] == '2032-03-28 09:00'
        assert pm.projectCalendarReminders([entry], ['2032-03-28'], '')['reminders'] == [entry]
    finally:
        monkeypatch.undo()
        time.tzset()


def test_calendar_ui_projects_week_and_month(project, actiondraw_window):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    from test_reminder_calendar import find, value
    pm, tabs, tasks, diagram = project
    pm.addStandaloneReminder('Daily', '2099-01-01 09:00', False, dict(interval=1, unit='days'))
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    overview = find(window, 'reminderOverview')
    overview.setProperty('weekStart', '2099-01-05')
    overview.setProperty('selectedDate', '2099-02-12')
    calendar = window.findChild(QObject, 'reminderCalendar')
    calendar.setProperty('displayedYear', 2099)
    calendar.setProperty('displayedMonth', 1)
    QTest.qWait(40)
    assert value(overview, 'dayCounts')['2099-01-07'] == 1
    assert value(overview, 'dayCounts')['2099-02-12'] == 1
    assert value(overview, 'filteredReminders')[0]['occurrenceText'] == '2099-02-12 09:00'
    calendar.setProperty('displayedMonth', 2)
    QTest.qWait(20)
    assert value(overview, 'dayCounts')['2099-03-20'] == 1
    pm.clearStandaloneReminder(0)
    QTest.qWait(20)
    assert value(overview, 'dayCounts')['2099-03-20'] == 0
    assert value(overview, 'filteredReminders') == []
    window.close()


@pytest.mark.parametrize('surface,action', [('month', 'title'), ('month', 'menu'), ('week', 'title'), ('week', 'menu')])
def test_open_projected_reminder_reveals_node(project, actiondraw_window, surface, action):
    from PySide6.QtCore import QObject, QMetaObject, Qt
    from PySide6.QtTest import QTest
    from test_reminder_calendar import find
    pm, tabs, tasks, diagram = project
    node = thought(pm.mindmap, 'Recurring destination')
    child = pm.mindmap.map.find(node).add_child('Inside destination')
    outside = pm.mindmap.map.root.add_child('Outside destination')
    pm.mindmap.reconcile()
    pm.setMindmapReminder(node, '2099-01-01 09:00', False, dict(interval=1, unit='days'))
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    overview = find(window, 'reminderOverview')
    overview.setProperty('selectedDate', '2099-01-07')
    overview.setProperty('weekStart', '2099-01-05')
    QTest.qWait(40)
    assert pm.mindmap.calendarFilterActive

    def click(name):
        item = find(window, name)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())
        QTest.qWait(50)

    if surface == 'month':
        click('openPlanningMonth')
    else:
        click('weekAgenda_2099-01-07')
    if action == 'title':
        click('reminderTitle_' + node)
    else:
        click('reminderActions_' + node)
        click('openReminder_' + node)
    assert not window.findChild(QObject, 'planningOverlay').property('visible')
    assert not window.findChild(QObject, 'weekAgendaPopup').property('visible')
    assert overview.property('selectedDate') == ''
    assert pm.mindmap.activityFilter == pm.mindmap.calendarActivityId(node)
    assert pm.mindmap.selectedId == node
    assert pm.mindmapVisible
    visible = {entry['id'] for entry in pm.mindmap.nodes}
    assert {node, child.id} <= visible
    assert outside.id not in visible
    window.close()
