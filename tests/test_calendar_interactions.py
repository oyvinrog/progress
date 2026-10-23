"""Direct calendar editing, local overflow, and guarded one-step Undo."""
import pytest
from PySide6.QtCore import QObject, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from task_model import TabModel
from test_reminder_calendar import calendar_ui, find, value


@pytest.fixture
def scheduled_calendar(calendar_ui, app):
    root, host, overview, calendar, refresh, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    overview.setProperty('goalModel', tabs)
    yield root, host, overview, calendar, tabs, click
    overview.setProperty('goalModel', None)


def point(item, x=None, y=None):
    return item.mapToScene(QPointF(item.width()/2 if x is None else x,
                                  item.height()/2 if y is None else y)).toPoint()


@pytest.mark.parametrize('count', [10, 50])
def test_local_overflow_details_keyboard_and_open(scheduled_calendar, app, count):
    root, host, overview, calendar, tabs, click = scheduled_calendar
    for i in range(count):
        tabs.createScheduledGoal('Activity %02d' % i, '2032-02-28', '2032-03-02')
    app.processEvents()
    hidden = value(calendar, 'weeks')[4]['hiddenBars'][0]['goal']['id']
    click('calendarMore_2032-02-29')
    QTest.qWait(80)
    popup = overview.findChild(QObject, 'calendarOverflow')
    assert popup.property('visible')
    assert len(value(popup, 'activities')) == count
    # Opening overflow doesn't change the calendar's day filter or move focus to the agenda.
    assert overview.property('selectedDate') == '2032-02-28'
    row = find(root, 'overflowGoal_' + hidden)
    row.forceActiveFocus()
    QTest.keyClick(root, Qt.Key_Return)
    app.processEvents()
    click('calendarActivityDetails')
    card = overview.findChild(QObject, 'calendarActivityCard')
    assert card.property('visible')
    assert not popup.property('visible')
    assert card.property('goalId') == hidden
    assert host.property('action') == ''
    click('openCalendarActivity')
    assert host.property('action') == 'open-goal-' + str(tabs.goalIndex(hidden))


@pytest.mark.parametrize('mode', ['move', 'start', 'end'])
@pytest.mark.parametrize('outcome', ['save', 'escape', 'outside'])
def test_drag_hidden_activity_from_overflow(scheduled_calendar, app, outcome, mode):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    for i in range(10):
        tabs.createScheduledGoal('Activity %02d' % i, '2032-02-28', '2032-03-02')
    app.processEvents()
    hidden = value(calendar, 'weeks')[4]['hiddenBars'][0]['goal']['id']
    original = tabs.scheduledGoals
    changes = []
    tabs.scheduledGoalsChanged.connect(lambda: changes.append(True))
    click('calendarMore_2032-02-29')
    QTest.qWait(80)
    row = find(root, 'overflowGoal_' + hidden)
    start = point(row) if mode == 'move' else point(find(root, 'overflowHandle_' + mode + '_' + hidden))
    end = point(find(root, 'reminderDay_2032-02-20'), y=10)
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, start + QPoint(-12, 0), 30)
    QTest.mouseMove(root, end, 30)
    assert value(calendar, 'gesture')['id'] == hidden
    assert value(calendar, 'gesture')['mode'] == mode
    assert tabs.scheduledGoals == original
    if outcome == 'escape':
        QTest.keyClick(root, Qt.Key_Escape)
    if outcome == 'outside':
        end = QPoint(1, 1)
        QTest.mouseMove(root, end, 30)
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    assert value(calendar, 'gesture') is None
    if outcome == 'save':
        assert changes == [True]
        summary = tabs.getTabSummary(tabs.goalIndex(hidden))
        # The date grabbed in the overflow is Feb 29, one day after the activity starts.
        expected = {'move': ('2032-02-19', '2032-02-22'),
                    'start': ('2032-02-20', '2032-03-02'),
                    'end': ('2032-02-28', '2032-02-28')}[mode]
        assert (summary['goalStartDate'], summary['goalEndDate']) == expected
        click('calendarUndo')
        assert changes == [True, True]
        assert tabs.scheduledGoals == original
    else:
        assert not changes
        assert tabs.scheduledGoals == original


@pytest.mark.parametrize('mode,expected', [
    ('move', ('2032-03-01', '2032-03-04')),
    ('start', ('2032-03-01', '2032-03-02')),
    ('end', ('2032-02-28', '2032-03-03')),
])
def test_direct_drag_resize_preview_and_undo(scheduled_calendar, app, mode, expected):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    goal = tabs.createScheduledGoal('Activity', '2032-02-28', '2032-03-02')
    tabs.createScheduledGoal('Neighbor', '2032-02-28', '2032-03-02')
    app.processEvents()
    before = tabs.scheduledGoals
    bars_before = value(calendar, 'weeks')
    bar = find(root, 'goalBar_' + goal + ('_0' if mode == 'end' else '_5'))
    assert bar.height() == 28
    x = 20 if mode == 'start' else bar.width()-20 if mode == 'end' else 40
    start = point(bar, x, 24)
    destination = '2032-03-03' if mode == 'end' else '2032-03-01'
    end = point(find(root, 'reminderDay_' + destination), y=10)
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, end, 30)
    assert tabs.scheduledGoals == before
    assert value(calendar, 'weeks') == bars_before  # Neighbors don't jump lanes during a preview.
    assert (calendar.property('previewStart'), calendar.property('previewEnd')) == expected
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    summary = tabs.getTabSummary(tabs.goalIndex(goal))
    assert (summary['goalStartDate'], summary['goalEndDate']) == expected
    click('calendarUndo')
    assert tabs.scheduledGoals == before
    assert value(overview, 'undoChange') is None


def test_activity_card_date_picker_validation_and_undo(scheduled_calendar, app):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    goal = tabs.createScheduledGoal('Long activity', '2032-02-01', '2032-05-01')
    app.processEvents()
    bar = find(root, 'goalBar_' + goal + '_0')
    QTest.mouseClick(root, Qt.LeftButton, Qt.NoModifier, point(bar))
    app.processEvents()
    click('calendarActivityDetails')
    card = overview.findChild(QObject, 'calendarActivityCard')
    assert card.property('visible')
    click('goalRangeEnd')
    picker = card.findChild(QObject, 'goalDatePicker')
    assert picker.property('month') == 4
    click('goalDateDay_15')
    assert card.findChild(QObject, 'goalRangeEnd').property('text') == '2032-05-15'
    click('saveGoalRange')
    assert tabs.getTabSummary(tabs.goalIndex(goal))['goalEndDate'] == '2032-05-15'
    click('calendarUndo')
    assert tabs.getTabSummary(tabs.goalIndex(goal))['goalEndDate'] == '2032-05-01'
    click('openGoal_' + goal)
    click('calendarActivityDetails')
    card.findChild(QObject, 'goalRangeEnd').setProperty('text', '2032-01-31')
    click('saveGoalRange')
    assert card.property('visible')
    assert card.findChild(QObject, 'goalRangeError').property('visible')
    assert tabs.getTabSummary(tabs.goalIndex(goal))['goalEndDate'] == '2032-05-01'


def test_undo_external_updates_and_failed_save(scheduled_calendar, app):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    goal = tabs.createScheduledGoal('Activity', '2032-02-28', '2032-03-02')
    app.processEvents()
    assert not overview.saveCalendarRange(goal, '2032-03-05', '2032-03-01')
    assert value(overview, 'undoChange') is None
    assert 'Could not save' in overview.property('calendarMessage')
    assert overview.saveCalendarRange(goal, '2032-03-01', '2032-03-04')
    tabs.setGoalRange(goal, '2032-03-03', '2032-03-06')
    app.processEvents()
    assert value(overview, 'undoChange') is None
    overview.undoCalendarRange()
    assert tabs.getTabSummary(tabs.goalIndex(goal))['goalStartDate'] == '2032-03-03'
    assert overview.saveCalendarRange(goal, '2032-03-01', '2032-03-04')
    tabs.clearGoalRange(goal)
    app.processEvents()
    assert value(overview, 'undoChange') is None


def test_mindmap_plan_card_save_and_undo(calendar_ui, app):
    from actiondraw.mindmap import MindMapController
    root, _, overview, calendar, _, click = calendar_ui
    tabs = TabModel()
    tabs.addTab('Main')
    mindmap = MindMapController(tabs)
    node = mindmap.map.root.add_child('Planned activity')
    goal = 'plan:' + node.id
    assert mindmap.setGoalRange(goal, '2032-02-28', '2032-03-02')
    overview.setProperty('planController', mindmap)
    app.processEvents()
    click('openGoal_' + goal)
    click('calendarActivityDetails')
    card = overview.findChild(QObject, 'calendarActivityCard')
    card.findChild(QObject, 'goalRangeEnd').setProperty('text', '2032-03-10')
    click('saveGoalRange')
    assert mindmap.plan_ranges[node.id]['endDate'] == '2032-03-10'
    click('calendarUndo')
    assert mindmap.plan_ranges[node.id]['endDate'] == '2032-03-02'
    overview.setProperty('planController', None)


@pytest.mark.parametrize('width,height', [(1200, 800), (600, 850), (1000, 420)])
def test_overflow_and_card_layout(scheduled_calendar, app, tmp_path, width, height):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    root.setWidth(width); root.setHeight(height)
    for i in range(10):
        tabs.createScheduledGoal('Long activity title %02d across multiple calendar weeks' % i, '2032-01-26', '2032-03-02')
    app.processEvents()
    QTest.qWait(100)
    click('calendarMore_2032-01-26')
    popup = overview.findChild(QObject, 'calendarOverflow')
    assert popup.property('visible')
    assert popup.property('x') >= 0 and popup.property('y') >= 0
    assert popup.property('x') + popup.property('width') <= width
    assert popup.property('y') + popup.property('height') <= height
    assert root.grabWindow().save(str(tmp_path / ('overflow-%s-%s.png' % (width, height))))
    first = value(popup, 'activities')[0]['id']
    click('overflowGoal_' + first)
    click('calendarActivityDetails')
    card = overview.findChild(QObject, 'calendarActivityCard')
    assert card.property('visible')
    assert card.property('x') >= 0 and card.property('y') >= 0
    assert card.property('x') + card.property('width') <= width
    card_item = find(root, 'openCalendarActivity')
    assert point(card_item).y() < height
    assert root.grabWindow().save(str(tmp_path / ('activity-card-%s-%s.png' % (width, height))))


@pytest.mark.parametrize('mode,expected', [
    ('start', ('2032-03-12', '2032-05-01')),
    ('end', ('2032-01-01', '2032-03-12')),
])
def test_overflow_resize_offscreen_endpoints_across_months(scheduled_calendar, app, mode, expected):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    for i in range(10):
        tabs.createScheduledGoal('Long activity %02d' % i, '2032-01-01', '2032-05-01')
    app.processEvents()
    hidden = value(calendar, 'weeks')[4]['hiddenBars'][0]['goal']['id']
    original = tabs.scheduledGoals
    click('calendarMore_2032-02-29')
    QTest.qWait(80)
    handle = find(root, 'overflowHandle_' + mode + '_' + hidden)
    start = point(handle)
    QTest.mousePress(root, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(root, start + QPoint(-12, 0), 30)
    QTest.mouseMove(root, point(find(root, 'reminderNextMonth')), 30)
    QTest.qWait(700)
    assert calendar.property('displayedMonth') == 2
    end = point(find(root, 'reminderDay_2032-03-12'), y=10)
    QTest.mouseMove(root, end, 30)
    assert (calendar.property('previewStart'), calendar.property('previewEnd')) == expected
    assert tabs.scheduledGoals == original
    QTest.mouseRelease(root, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    summary = tabs.getTabSummary(tabs.goalIndex(hidden))
    assert (summary['goalStartDate'], summary['goalEndDate']) == expected
    click('calendarUndo')
    assert tabs.scheduledGoals == original


@pytest.mark.parametrize('entry', ['bar', 'agenda', 'overflow'])
def test_activity_entry_points_filter_complete_branch(scheduled_calendar, app, entry):
    from actiondraw.mindmap import MindMapController
    root, host, overview, calendar, tabs, click = scheduled_calendar
    mindmap = MindMapController(tabs)
    overview.setProperty('planController', mindmap)
    try:
        ids = [tabs.createScheduledGoal('Activity %02d' % i, '2032-02-28', '2032-03-02')
               for i in range(4)]
        app.processEvents()
        if entry == 'overflow':
            goal = value(calendar, 'weeks')[4]['hiddenBars'][0]['goal']['id']
        elif entry == 'bar':
            goal = value(calendar, 'weeks')[4]['bars'][0]['goal']['id']
        else:
            goal = ids[0]
        node_id = next(key for key, tab in mindmap.links.items() if tab == goal)
        child = mindmap.map.find(node_id).add_child('Unscheduled child')
        mindmap.map.find(node_id).folded = True
        calendar.dateSelected.emit('2032-02-28')
        if entry == 'bar':
            column = value(calendar, 'weeks')[4]['bars'][0]['column']
            click('goalBar_' + goal + '_' + str(column))
        elif entry == 'agenda':
            click('openGoal_' + goal)
        else:
            click('calendarMore_2032-02-29')
            QTest.qWait(80)
            row = find(root, 'overflowGoal_' + goal)
            row.forceActiveFocus()
            QTest.keyClick(root, Qt.Key_Return)
            app.processEvents()
        assert mindmap.activityFilter == goal
        assert child.id in {n['id'] for n in mindmap.nodes}
        card = overview.findChild(QObject, 'calendarActivityCard')
        assert not card.property('visible')
        mindmap.select(child.id)
        assert mindmap.activityFilter == goal
        assert {n['id'] for n in mindmap.nodes} == {node_id, child.id}
        click('calendarActivityDetails')
        assert card.property('visible')
        card.close()
        assert mindmap.activityFilter == goal
        assert overview.property('selectedDate') == '2032-02-28'
    finally:
        overview.setProperty('planController', None)


def test_open_card_rename_preserves_pending_dates(scheduled_calendar, app):
    root, _, overview, calendar, tabs, click = scheduled_calendar
    goal = tabs.createScheduledGoal('Activity', '2032-02-28', '2032-03-02')
    app.processEvents()
    click('openGoal_' + goal)
    click('calendarActivityDetails')
    card = overview.findChild(QObject, 'calendarActivityCard')
    card.findChild(QObject, 'goalRangeEnd').setProperty('text', '2032-03-10')
    tabs.renameTab(tabs.goalIndex(goal), 'Renamed activity')
    app.processEvents()
    assert card.findChild(QObject, 'goalRangeName').property('text') == 'Renamed activity'
    assert card.findChild(QObject, 'goalRangeEnd').property('text') == '2032-03-10'
    assert card.property('visible')
    tabs.removeTab(tabs.goalIndex(goal))
    app.processEvents()
    assert not card.property('visible')
