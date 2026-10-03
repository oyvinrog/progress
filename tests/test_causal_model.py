"""Causal graph invariants, history, project integration, and companion UI."""
import copy
import json

import pytest
from PySide6.QtCore import QMetaObject, Qt, QObject, QPointF
from PySide6.QtTest import QTest

from actiondraw.causal_model import CausalModelModel, empty_causal_model_state, normalize_causal_model_state
from actiondraw.model import DiagramModel
from actiondraw.ui import create_actiondraw_window
from progress_crypto import EncryptionCredentials
from task_model import ProjectManager, Tab, TabModel, TaskModel


def graph():
    model = CausalModelModel()
    a = model.addNode('Raise concern', 'action', 50, 400)
    b = model.addNode('Decision changes', 'variable', 50, 150)
    c = model.addNode('Prepare evidence', 'action', 350, 350)
    d = model.addNode('Resolution', 'outcome', 650, 150)
    model.addEdge(a, b, '80', 'Estimate')
    model.addEdge(c, b, '90', '')
    model.addEdge(b, d, '', '')
    return model, a, b, c, d


def test_branching_graph_validation_and_weights(app):
    model, a, b, c, d = graph()
    assert len(model.edges) == 3
    assert model.edges[-1]['likelihood'] is None
    assert not model.addEdge(a, a, '', '')
    assert 'itself' in model.validationError
    assert not model.addEdge(a, b, '', '')
    assert 'already' in model.validationError
    assert not model.addEdge(d, a, '', '')
    assert 'cycle' in model.validationError
    for weight in ['-1', '101', 'nan', 'inf', 'not a number']:
        assert not model.addEdge(a, d, weight, '')
    for weight in ['0', '100', '']:
        edge = model.addEdge(a, d, weight, '')
        assert edge
        model.removeEdge(edge)
    edge = model.edges[0]['id']
    assert model.editEdge(edge, '30.5', 'Updated assumption')
    assert model.edges[0]['likelihood'] == 30.5
    assert not model.editEdge(edge, '101', '')
    assert model.edges[0]['likelihood'] == 30.5


def test_action_order_types_deletion_and_history(app):
    model, a, b, c, d = graph()
    edges = model.edges
    positions = model.nodes
    model.moveAction(1, 0)
    assert model.orderedTitles == ['Prepare evidence', 'Raise concern']
    assert model.edges == edges and model.nodes == positions
    model.undo()
    assert model.orderedTitles == ['Raise concern', 'Prepare evidence']
    model.redo()
    assert model.orderedTitles == ['Prepare evidence', 'Raise concern']
    assert model.editNode(c, 'Evidence', 'variable', 'Source')
    assert model.orderedTitles == ['Raise concern']
    model.undo()
    assert model.orderedTitles == ['Prepare evidence', 'Raise concern']
    model.removeNode(b)
    assert model.edges == []
    model.undo()
    assert model.edges == edges
    model.beginNodeDrag()
    model.moveNode(a, 100, 200)
    model.moveNode(a, 150, 250)
    model.endNodeDrag()
    model.undo()
    assert next(n for n in model.nodes if n['id'] == a)['x'] == 50
    model.redo()
    assert next(n for n in model.nodes if n['id'] == a)['x'] == 150


def test_import_signature_and_serialization(app):
    model, a, b, c, d = graph()
    model.markImported()
    assert model.imported
    model.moveNode(a, 200, 300)
    model.editEdge(model.edges[0]['id'], '40', '')
    model.setDescription('Hypothetical scenario')
    assert model.imported
    model.undo()
    assert model.imported
    model.editNode(a, 'Raise concern again', 'action', '')
    assert not model.imported
    model.undo()
    assert model.imported
    restored = CausalModelModel()
    restored.from_dict(model.to_dict())
    assert restored.to_dict() == model.to_dict()
    assert restored.imported and not restored.canUndo
    model.moveAction(1, 0)
    assert not model.imported


def test_normalization_handles_damaged_and_legacy_data(app):
    assert normalize_causal_model_state(None) == empty_causal_model_state()
    model, a, b, c, d = graph()
    data = model.to_dict()
    data['nodes'].extend([None, dict(id='bad', type='action', label='Bad', x=float('nan'))])
    data['edges'].extend([None, dict(id='cycle', source=d, target=a), dict(id='missing', source=a, target='missing')])
    data['action_order'] = [c, c, 'missing']
    state = normalize_causal_model_state(data)
    assert len(state['nodes']) == 4 and len(state['edges']) == 3
    assert state['action_order'] == [c, a]


def project():
    tasks = TaskModel()
    diagram = DiagramModel(task_model=tasks)
    tabs = TabModel()
    manager = ProjectManager(tasks, diagram, tabs)
    model = CausalModelModel(tab_model=tabs)
    return tasks, diagram, tabs, manager, model


@pytest.mark.parametrize('active_tab, expected_index', [(0, 0), (1, 1), (99, 0), (-1, 0)])
def test_reset_publishes_valid_current_tab_before_notifying_editors(app, active_tab, expected_index):
    tabs = TabModel()
    tabs.addTab('Old second')
    tabs.addTab('Old third')
    tabs.setCurrentTab(2)
    model = CausalModelModel(tab_model=tabs)
    model.addNode('Old action', 'action', 10, 20)
    replacement = []
    for title in ['New first', 'New second']:
        saved = CausalModelModel()
        saved.addNode(title, 'action', 30, 40)
        replacement.append(Tab(name=title, tasks={'tasks': []}, diagram={}, causal_model=saved.to_dict()))
    observed = []
    tabs.modelReset.connect(lambda: observed.append((tabs.currentTabIndex, model.orderedTitles)))

    tabs.setTabs(replacement, active_tab)

    assert observed == [(expected_index, [replacement[expected_index].name])]
    assert not model.canUndo
    model.setDescription('Saved to the new active tab')
    assert replacement[expected_index].causal_model['description'] == 'Saved to the new active tab'
    assert replacement[1 - expected_index].causal_model['description'] == ''
    tabs.clear()
    assert observed[-1] == (0, [])
    assert model.to_dict() == empty_causal_model_state()


@pytest.mark.parametrize('invalid_index', [-1, 5])
def test_causal_editor_tolerates_missing_current_tab_and_recovers(app, invalid_index):
    tabs = TabModel()
    model = CausalModelModel(tab_model=tabs)
    model.addNode('Keep on tab', 'action', 10, 20)
    saved = copy.deepcopy(tabs.getCurrentTabData().causal_model)
    tabs._current_tab_index = invalid_index
    model.loadCurrentTab()
    assert model.to_dict() == empty_causal_model_state()
    model.addNode('Unattached', 'action', 30, 40)
    assert tabs.getAllTabs()[0].causal_model == saved
    tabs.setCurrentTab(0)
    assert model.to_dict() == saved


@pytest.mark.parametrize('encrypted', [False, True])
def test_project_round_trip_tabs_and_dirty_detection(app, tmp_path, monkeypatch, encrypted):
    if encrypted:
        monkeypatch.setattr(ProjectManager, '_prompt_encryption_credentials',
                            lambda *args, **kwargs: EncryptionCredentials(passphrase='causal-test'))
    tasks, diagram, tabs, manager, model = project()
    assert tabs.getCurrentTabData().causal_model == empty_causal_model_state()
    manager._last_saved_snapshot = manager._serialize_project_payload(manager._build_project_data())
    assert not manager.hasUnsavedChanges()
    a = model.addNode('First', 'action', 20, 30)
    assert manager.hasUnsavedChanges()
    tabs.addTab('Other')
    manager.switchTab(1)
    assert model.nodes == []
    b = model.addNode('Second', 'action', 40, 50)
    model.addNode('Outcome', 'outcome', 100, 50)
    model.setDescription('Other assumptions')
    path = tmp_path / 'causal.progress'
    if encrypted:
        assert manager.saveProject(str(path))
    else:
        path.write_text(json.dumps(manager._build_project_data()), encoding="utf-8")
    _, _, loaded_tabs, loaded_manager, loaded = project()
    loaded_manager.loadProject(str(path))
    assert loaded.orderedTitles == ['Second']
    assert loaded.description == 'Other assumptions'
    loaded_manager.switchTab(0)
    assert loaded.orderedTitles == ['First']
    assert loaded.nodes[0]['id'] == a
    duplicate = copy.deepcopy(loaded_tabs.getCurrentTabData())
    duplicate.causal_model['nodes'][0]['label'] = 'Independent copy'
    assert loaded_tabs.getCurrentTabData().causal_model['nodes'][0]['label'] == 'First'
    # Loading replaces a longer tab list after scrubbing the old active tab.
    loaded_tabs.addTab('Third')
    loaded_manager.switchTab(2)
    loaded.addNode('Discard on reload', 'action', 10, 20)
    loaded_manager.loadProject(str(path))
    assert loaded.orderedTitles == ['Second']
    assert loaded_tabs.currentTabIndex == 1


def test_import_destinations_and_undo(app):
    tasks, diagram, tabs, manager, model = project()
    assert manager.addCausalModelToMindmap() == []
    model.addNode('One', 'action', 10, 20)
    model.addNode('Observation', 'variable', 20, 20)
    model.addNode('Two', 'action', 30, 20)
    model.moveAction(1, 0)
    created = diagram.createTaskChainAtPosition(model.orderedTitles, 200, 300)
    assert len(created) == 2
    assert [item['title'] for item in tasks.to_dict()['tasks']] == ['Two', 'One']
    model.markImported()
    ids = manager.addCausalModelToMindmap()
    assert [manager.mindmap.map.find(key).text for key in ids] == ['Two', 'One']
    assert len(manager.addCausalModelToMindmap()) == 2
    assert model.imported


def test_qml_companion_opens_and_tracks_tabs(app):
    tasks, diagram, tabs, manager, model = project()
    engine = create_actiondraw_window(diagram, tasks, manager, tab_model=tabs)
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(w.toString() for w in warnings))
    assert engine.rootObjects()
    root = engine.rootObjects()[0]
    assert QMetaObject.invokeMethod(root, 'openCausalModelWindow', Qt.DirectConnection)
    app.processEvents()
    window = root.property('causalModelWindowRef')
    assert window is not None
    controller = engine._causal_model
    controller.addNode('A', 'action', 30, 40)
    controller.addNode('B', 'outcome', 330, 40)
    QTest.qWait(60)
    first_id = controller.nodes[0]['id']
    second_id = controller.nodes[1]['id']

    def connect_drag(source, target_point, cancel=False):
        handle = window.connectionHandleById(source)
        start = handle.mapToScene(QPointF(13, 13)).toPoint()
        QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
        QTest.mouseMove(window, (start + target_point) / 2, 20)
        QTest.mouseMove(window, target_point, 20)
        assert window.property('connectSource') == source
        if cancel:
            QTest.keyClick(window, Qt.Key_Escape)
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, target_point)
        app.processEvents()
        assert window.property('connectSource') == ''

    target = window.nodeItemById(second_id).mapToScene(QPointF(80, 45)).toPoint()
    original_positions = controller.nodes
    connect_drag(first_id, target)
    assert len(controller.edges) == 1
    assert controller.edges[0]['source'] == first_id
    assert controller.edges[0]['target'] == second_id
    assert controller.edges[0]['likelihood'] is None
    assert controller.nodes == original_positions
    controller.undo()
    assert controller.edges == []
    controller.redo()
    connect_drag(first_id, target)
    assert len(controller.edges) == 1 and 'already' in controller.validationError
    source_center = window.nodeItemById(first_id).mapToScene(QPointF(80, 45)).toPoint()
    connect_drag(second_id, source_center)
    assert len(controller.edges) == 1 and 'cycle' in controller.validationError
    connect_drag(first_id, source_center)
    assert len(controller.edges) == 1 and 'itself' in controller.validationError
    connect_drag(first_id, target + QPointF(0, 200).toPoint())
    connect_drag(first_id, target, cancel=True)
    assert len(controller.edges) == 1 and controller.nodes == original_positions
    controller.editEdge(controller.edges[0]['id'], '80', '')

    # A double-click uses canvas coordinates, including the scroll offset.
    viewport = window.findChild(QObject, 'causalViewport')
    board = window.findChild(QObject, 'causalBoard')
    viewport.setProperty('contentX', 200)
    viewport.setProperty('contentY', 100)
    app.processEvents()
    point = board.mapToScene(QPointF(800, 500)).toPoint()
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(30)
    label = window.findChild(QObject, 'causalNodeLabel')
    assert label.property('activeFocus')
    label.setProperty('text', 'New variable')
    QTest.keyClick(window, Qt.Key_Return)
    app.processEvents()
    assert len(controller.nodes) == 3
    assert controller.nodes[-1]['label'] == 'New variable'
    assert controller.nodes[-1]['x'] == 720
    assert controller.nodes[-1]['y'] == 455
    controller.undo()
    assert len(controller.nodes) == 2
    controller.redo()
    window.openNode(controller.nodes[-1])
    QTest.qWait(30)
    assert label.property('activeFocus')
    label.setProperty('text', 'Renamed variable')
    QTest.keyClick(window, Qt.Key_Enter)
    app.processEvents()
    assert len(controller.nodes) == 3
    assert controller.nodes[-1]['label'] == 'Renamed variable'
    viewport.setProperty('contentX', 0)
    viewport.setProperty('contentY', 0)
    app.processEvents()
    node = window.nodeItemById(first_id)
    assert node is not None
    start = node.mapToScene(QPointF(80, 45)).toPoint()
    end = start + QPointF(100, 80).toPoint()
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    assert controller._drag is not None, (start, node.width(), node.height(), window.width(), window.height(), errors)
    QTest.mouseMove(window, start + QPointF(30, 20).toPoint(), 20)
    QTest.mouseMove(window, start + QPointF(60, 50).toPoint(), 20)
    QTest.mouseMove(window, end, 20)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    assert controller.nodes[0]['x'] == pytest.approx(130)
    assert controller.nodes[0]['y'] == pytest.approx(120)
    controller.undo()
    assert controller.nodes[0]['x'] == 30
    controller.redo()
    window.openEdge(controller.edges[0])
    QTest.qWait(30)
    weight = window.findChild(QObject, 'causalEdgeWeight')
    assert weight.property('activeFocus')
    weight.setProperty('text', '101')
    QTest.keyClick(window, Qt.Key_Return)
    app.processEvents()
    assert controller.edges[0]['likelihood'] == 80
    assert weight.property('activeFocus')
    weight.setProperty('text', '65')
    QTest.keyClick(window, Qt.Key_Return)
    app.processEvents()
    assert controller.edges[0]['likelihood'] == 65
    window.openEdge(controller.edges[0])
    QTest.qWait(30)
    notes = window.findChild(QObject, 'causalEdgeNotes')
    notes.forceActiveFocus()
    notes.setProperty('text', 'Explanation')
    notes.setProperty('cursorPosition', len('Explanation'))
    QTest.keyClick(window, Qt.Key_Return, Qt.ShiftModifier)
    assert notes.property('text') == 'Explanation\n'
    notes.setProperty('text', notes.property('text') + 'Assumption')
    QTest.keyClick(window, Qt.Key_Enter)
    app.processEvents()
    assert controller.edges[0]['notes'] == 'Explanation\nAssumption'

    # Existing diagram nodes can become actions without losing causal edges.
    target = window.nodeItemById(second_id).mapToScene(QPointF(80, 45)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, target)
    make_action = window.findChild(QObject, 'causalMakeAction')
    assert make_action.property('visible')
    make_action.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert controller.orderedTitles == ['A', 'B']
    assert len(controller.edges) == 1
    controller.undo()
    assert controller.orderedTitles == ['A']

    # The dedicated action button opens a task editor ready for Enter to save.
    add_action = window.findChild(QObject, 'causalAddAction')
    add_action.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    QTest.qWait(30)
    node_type = window.findChild(QObject, 'causalNodeType')
    assert node_type.property('currentText') == 'action'
    assert label.property('activeFocus')
    label.setProperty('text', 'C')
    QTest.keyClick(window, Qt.Key_Return)
    QTest.qWait(30)
    assert controller.orderedTitles == ['A', 'C']
    up = window.actionUpButtonAt(1)
    up.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert controller.orderedTitles == ['C', 'A']
    QTest.qWait(30)
    start = window.actionDragHandleAt(0).mapToScene(QPointF(18, 25)).toPoint()
    end = window.actionDragHandleAt(1).mapToScene(QPointF(18, 25)).toPoint()
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, end, 20)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    assert controller.orderedTitles == ['A', 'C']
    assert len(controller.edges) == 1
    controller.undo()
    assert controller.orderedTitles == ['C', 'A']
    add_draw = window.findChild(QObject, 'causalAddToActionDraw')
    add_draw.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert tasks.rowCount() == 2
    assert [task['title'] for task in tasks.to_dict()['tasks']] == ['C', 'A']
    assert controller.imported and not add_draw.property('enabled')
    add_map = window.findChild(QObject, 'causalAddToMindmap')
    assert add_map.property('enabled')
    add_map.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert [child.text for child in manager.mindmap.view_root.children] == ['C', 'A']

    # Delete removes the selected action and its edges in one undo step.
    before_delete = controller.to_dict()
    node_point = window.nodeItemById(first_id).mapToScene(QPointF(120, 70)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, node_point)
    assert window.property('selectedNode') == first_id
    assert window.property('selectedEdge') == ''
    QTest.keyClick(window, Qt.Key_Delete)
    app.processEvents()
    assert len(controller.nodes) == len(before_delete['nodes']) - 1
    assert controller.edges == []
    assert controller.orderedTitles == ['C']
    QTest.keyClick(window, Qt.Key_Z, Qt.ControlModifier)
    app.processEvents()
    assert controller.to_dict() == before_delete

    # An edge can be selected without opening its editor, then deleted alone.
    a = next(n for n in controller.nodes if n['id'] == first_id)
    b = next(n for n in controller.nodes if n['id'] == second_id)
    edge_point = board.mapToScene(QPointF((a['x'] + b['x']) / 2 + 80,
                                        (a['y'] + b['y']) / 2 + 45)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, edge_point)
    assert window.property('selectedEdge') == controller.edges[0]['id']
    assert window.property('selectedNode') == ''
    QTest.keyClick(window, Qt.Key_Delete)
    app.processEvents()
    assert controller.edges == []
    assert controller.nodes == before_delete['nodes']
    controller.undo()
    assert controller.to_dict() == before_delete

    # Delete inside either editor edits text, never the selected graph object.
    window.openNode(a)
    QTest.qWait(30)
    label.setProperty('cursorPosition', 0)
    QTest.keyClick(window, Qt.Key_Delete)
    assert label.property('text') == ''
    assert controller.to_dict() == before_delete
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, edge_point)
    QTest.qWait(30)
    assert weight.property('activeFocus')
    weight.setProperty('cursorPosition', 0)
    QTest.keyClick(window, Qt.Key_Delete)
    assert weight.property('text') == '5'
    assert controller.to_dict() == before_delete
    QTest.keyClick(window, Qt.Key_Escape)

    # The visible Delete button follows the same selection and undo behavior.
    node_point = window.nodeItemById(second_id).mapToScene(QPointF(80, 45)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, node_point)
    delete_button = window.findChild(QObject, 'causalDeleteSelection')
    assert delete_button.property('enabled')
    delete_button.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    app.processEvents()
    assert not any(n['id'] == second_id for n in controller.nodes)
    controller.undo()
    assert controller.to_dict() == before_delete
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     board.mapToScene(QPointF(600, 350)).toPoint())
    assert not delete_button.property('enabled')
    QTest.keyClick(window, Qt.Key_Delete)
    assert controller.to_dict() == before_delete
    tabs.addTab('Other')
    manager.switchTab(1)
    app.processEvents()
    assert controller.nodes == []
    manager.switchTab(0)
    app.processEvents()
    assert len(controller.edges) == 1
    assert not errors, '\n'.join(errors)
    window.close()
    root.setProperty("suppressClosePrompt", True)
    root.close()
    app.processEvents()
    # Destroy QML while all Python context objects are still alive.
    import shiboken6
    shiboken6.delete(engine._markdown_note_manager._editor._engine)
    shiboken6.delete(engine)
