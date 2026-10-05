"""Multi-hour scheduling and real timeline pointer interactions."""
import copy
import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtTest import QTest

from actiondraw.model import DiagramModel
from actiondraw.mindmap import MindMapController
from task_model import ProjectManager, TabModel, TaskModel
from progress_crypto import EncryptionCredentials


@pytest.fixture
def project(app, monkeypatch):
    monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials",
                        lambda *args: EncryptionCredentials(passphrase="test-passphrase"))
    tasks, tabs = TaskModel(), TabModel()
    diagram = DiagramModel(tasks)
    return ProjectManager(tasks, diagram, tabs), tabs, tasks, diagram


def add_item(project, source, hour=14):
    pm, tabs, _, _ = project
    if source == 'tab':
        item_id = 'tab:' + tabs.getAllTabs()[0].id
    else:
        pm.mindmap.addThought(False)
        item_id = 'node:' + pm.mindmap.selectedId
    assert pm.setKanbanItemPlacement(item_id, 'in_progress', hour)
    return item_id


def item(pm, item_id):
    return next(card for card in pm.getKanbanItems() if card['itemId'] == item_id)


@pytest.mark.parametrize('source', ['tab', 'node'])
def test_duration_roundtrip_moves_and_hour_actions(project, source, tmp_path):
    pm, tabs, _, _ = project
    item_id = add_item(project, source)
    assert pm.setKanbanItemDuration(item_id, 2)
    assert [entry['count'] for entry in pm.mindmap.planHourOptions if entry['hour'] in (14, 15)] == [1, 1]
    assert not pm.setKanbanItemPlacement(item_id, 'in_progress', 17)
    assert item(pm, item_id)['kanbanSlotHour'] == 14
    assert pm.setKanbanItemPlacement(item_id, 'in_progress', 15)
    assert pm.postponeKanbanItems(15)
    assert item(pm, item_id)['kanbanSlotHour'] == 16
    assert not pm.postponeKanbanItems(16)
    assert item(pm, item_id)['kanbanDurationHours'] == 2
    path = tmp_path / 'duration.progress'
    assert pm.saveProject(str(path))
    pm.loadProject(str(path))
    assert item(pm, item_id)['kanbanDurationHours'] == 2
    assert item(pm, item_id)['kanbanSlotHour'] == 16
    assert pm.moveKanbanItemsBack('in_progress', 17)
    assert item(pm, item_id)['kanbanStatus'] == 'ready'
    assert pm.setKanbanItemPlacement(item_id, 'done', -1)
    assert not pm.moveKanbanItemsBack('done', -1)
    assert item(pm, item_id)['kanbanStatus'] == 'done'
    assert pm.setKanbanItemPlacement(item_id, 'in_progress', 14)
    assert pm.clearKanbanItems('in_progress', 15)
    assert item(pm, item_id)['kanbanStatus'] == 'todo'
    assert item(pm, item_id)['kanbanDurationHours'] == 2


@pytest.mark.parametrize('source', ['tab', 'node'])
@pytest.mark.parametrize('duration', [0, -1, 11, 1.5, True, '2', None, 5])
def test_invalid_duration_does_not_mutate(project, source, duration):
    pm = project[0]
    item_id = add_item(project, source)
    assert not pm.setKanbanItemDuration(item_id, duration)
    assert item(pm, item_id)['kanbanDurationHours'] == 1


def test_mindmap_duration_undo_and_legacy_validation(project):
    pm, tabs, _, _ = project
    item_id = add_item(project, 'node')
    node_id = item_id[5:]
    legacy = pm.mindmap.to_dict()
    legacy['kanban'][node_id].pop('duration_hours')
    pm.mindmap.load(legacy)
    assert item(pm, item_id)['kanbanDurationHours'] == 1
    assert pm.setKanbanItemDuration(item_id, 2)
    pm.mindmap.undo()
    assert item(pm, item_id)['kanbanDurationHours'] == 1
    pm.mindmap.redo()
    assert item(pm, item_id)['kanbanDurationHours'] == 2
    for invalid in (0, True, '2', 5):
        payload = copy.deepcopy(legacy)
        payload['kanban'][node_id]['duration_hours'] = invalid
        with pytest.raises(ValueError, match='duration'):
            MindMapController.decode(payload)


@pytest.mark.parametrize('value', [None, 0, 11, True, '2', 1.5, 5])
def test_bad_tab_duration_load_defaults_to_one(project, tmp_path, value):
    pm = project[0]
    item_id = add_item(project, 'tab')
    payload = pm._build_project_data()
    if value is None:
        payload['tabs'][0].pop('kanban_duration_hours')
    else:
        payload['tabs'][0]['kanban_duration_hours'] = value
    path = tmp_path / 'legacy.progress'
    path.write_text(json.dumps(payload))
    pm.loadProject(str(path))
    assert item(pm, item_id)['kanbanDurationHours'] == 1


def test_fallback_tab_lane_actions_respect_duration(project):
    _, tabs, _, _ = project
    tabs.setKanbanPlacement(0, 'in_progress', 14)
    assert tabs.setKanbanDuration(0, 2)
    assert tabs.moveKanbanLaneBack('in_progress', 15)
    assert tabs.getTabSummary(0)['kanbanStatus'] == 'ready'
    tabs.setKanbanPlacement(0, 'in_progress', 16)
    assert not tabs.postponeInProgressFromSlot(16)
    assert tabs.clearKanbanLane('in_progress', 17)
    tabs.setKanbanPlacement(0, 'done', -1)
    assert not tabs.moveKanbanLaneBack('done', -1)


def find_visual(root, name):
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = find_visual(child, name)
        if found is not None:
            return found


@pytest.fixture
def board(project, app):
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(
        Path(__file__).parents[1] / 'actiondraw/qml_ui/KanbanWindow.qml')))
    root = component.createWithInitialProperties({'tabModel': project[1], 'projectManager': project[0]})
    assert root is not None, component.errorString()
    root.setWidth(1500)
    root.setHeight(950)
    root.requestActivate()
    QTest.qWait(30)
    yield root
    root.close()
    root.deleteLater()
    engine.deleteLater()
    app.processEvents()


@pytest.mark.parametrize('source', ['tab', 'node'])
def test_pointer_extend_shrink_cancel_and_boundary(project, board, app, source):
    pm = project[0]
    item_id = add_item(project, source)
    app.processEvents()
    timeline = find_visual(board.contentItem(), 'kanbanTimeline')
    timeline.setProperty('contentY', 5 * 154)
    app.processEvents()

    def resize(delta, cancel=False):
        handle = find_visual(board.contentItem(), 'kanbanResize_' + item_id)
        start = handle.mapToScene(QPointF(handle.width() / 2, 8)).toPoint()
        end = start + QPoint(0, delta)
        QTest.mousePress(board, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(board, end, 20)
        if cancel:
            QTest.keyClick(board, Qt.Key_Escape)
        QTest.mouseRelease(board, Qt.LeftButton, Qt.NoModifier, end)
        app.processEvents()

    resize(154)
    assert item(pm, item_id)['kanbanDurationHours'] == 2
    card_name = 'kanbanCard_0' if source == 'tab' else 'kanbanCard_' + item_id
    card = find_visual(board.contentItem(), card_name)
    assert card.height() == 2 * 154 - 8
    resize(154, cancel=True)
    assert item(pm, item_id)['kanbanDurationHours'] == 2
    resize(-154)
    assert item(pm, item_id)['kanbanDurationHours'] == 1
    resize(-154)
    assert item(pm, item_id)['kanbanDurationHours'] == 1
    resize(4 * 154)
    assert item(pm, item_id)['kanbanDurationHours'] == 4


def test_resize_autoscroll_keeps_pointer_time_mapping(project, board, app):
    pm = project[0]
    item_id = add_item(project, 'tab', 10)
    app.processEvents()
    timeline = find_visual(board.contentItem(), 'kanbanTimeline')
    handle = find_visual(board.contentItem(), 'kanbanResize_' + item_id)
    start = handle.mapToScene(QPointF(handle.width() / 2, 8)).toPoint()
    edge = timeline.mapToScene(QPointF(220, timeline.height() - 8)).toPoint()
    QTest.mousePress(board, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(board, edge, 20)
    QTest.qWait(400)
    scrolled = timeline.property('contentY')
    assert scrolled > 0
    expected = board.property('resizeHours')
    assert expected > 1
    QTest.mouseRelease(board, Qt.LeftButton, Qt.NoModifier, edge)
    app.processEvents()
    assert item(pm, item_id)['kanbanDurationHours'] == expected


def test_spanning_card_overlap_and_nonoverlap_reuse_columns(project, board, app):
    pm, tabs, _, _ = project
    first_id = add_item(project, 'tab')
    pm.setKanbanItemDuration(first_id, 2)
    tabs.addTab('Overlapping task')
    second_id = 'tab:' + tabs.getAllTabs()[1].id
    pm.setKanbanItemPlacement(second_id, 'in_progress', 15)
    tabs.addTab('Next task')
    third_id = 'tab:' + tabs.getAllTabs()[2].id
    pm.setKanbanItemPlacement(third_id, 'in_progress', 16)
    app.processEvents()
    first = find_visual(board.contentItem(), 'kanbanCard_0')
    second = find_visual(board.contentItem(), 'kanbanCard_1')
    third = find_visual(board.contentItem(), 'kanbanCard_2')
    a, b, c = [card.mapToScene(QPointF(0, 0)) for card in (first, second, third)]
    assert a.x() + first.width() <= b.x()
    assert a.x() == c.x()
    assert a.y() + first.height() < c.y()
    board.setWidth(1180)
    QTest.qWait(30)
    timeline = find_visual(board.contentItem(), 'kanbanTimeline')
    assert timeline.property('contentWidth') > timeline.width()
