"""Guard large-map work counts without relying on wall-clock thresholds."""
from unittest.mock import patch

import pytest

from actiondraw.mindmap import MindMapController


@pytest.mark.parametrize('references', [False, True])
def test_scene_does_not_find_each_node(app, references):
    m = MindMapController()
    branch = m.map.root.add_child('Target')
    m.links[branch.id] = 'target'
    for i in range(300):
        branch.add_child(f'Thought {i}')
    if references:
        ref = m.map.root.add_child('Reference')
        m.references[ref.id] = 'target'
    with patch.object(m.map, 'find', wraps=m.map.find) as find:
        nodes, edges = m.nodes, m.edges
    assert len(nodes) == (603 if references else 302)
    assert len(edges) == len(nodes) - 1
    # Resolving scope/reference targets is fine; looking up every badge isn't.
    assert find.call_count < 10


def test_search_only_rebuilds_when_unfolding(app):
    m = MindMapController()
    branch = m.map.root.add_child('Branch')
    first = branch.add_child('Match one')
    second = branch.add_child('Match two')
    events = []
    m.sceneChanged.connect(lambda: events.append(True))
    m.searchText('Match')
    assert m.selectedId == first.id
    m.navigateSearch(1)
    assert m.selectedId == second.id
    assert not events
    branch.folded = True
    m.navigateSearch(1)
    assert not branch.folded and len(events) == 1
    assert m.selectedId == first.id
    assert m.searchMatchCount == 2


def test_folded_branches_skip_node_measurement(app):
    m = MindMapController()
    branch = m.map.root.add_child('Branch')
    for i in range(300):
        branch.add_child(f'Hidden {i}')
    branch.folded = True
    with patch.object(m, '_plan_placement', wraps=m._plan_placement) as placement:
        boxes = m._layout()
    assert set(boxes) == {m.map.root, branch}
    assert placement.call_count == 2


def test_large_qml_map_loads_viewport_and_reveals_search(app, actiondraw_window, capfd):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    tasks, tabs = TaskModel(), TabModel()
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    m = project.mindmap
    branch = m.map.root.add_child('Large branch')
    children = [branch.add_child(f'Thought {i}') for i in range(300)]
    engine = actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    project.showMindmap()
    QTest.qWait(50)
    pane = window.findChild(QObject, 'mindmapPane')
    pane.setProperty('zoom', 1.0)
    QTest.qWait(20)

    def loaded_nodes(item):
        result = [item] if item.objectName().startswith('mindmapNode_') else []
        for child in item.childItems():
            result.extend(loaded_nodes(child))
        return result

    assert len(loaded_nodes(window.contentItem())) < 100
    target = children[-1]
    m.searchText(target.text)
    QTest.qWait(20)
    assert m.selectedId == target.id
    loaded = loaded_nodes(window.contentItem())
    assert any(item.objectName() == 'mindmapNode_' + target.id for item in loaded)
    assert len(loaded) < 100
    # Changing the viewport also loads nodes independently of selection.
    m.clearSearch()
    m.select(m.map.root.id)
    target_data = next(node for node in m.nodes if node['id'] == children[0].id)
    pane.setProperty('panX', -(target_data['x'] + target_data['width'] / 2))
    pane.setProperty('panY', -(target_data['y'] + target_data['height'] / 2))
    QTest.qWait(20)
    assert any(item.objectName() == 'mindmapNode_' + children[0].id
               for item in loaded_nodes(window.contentItem()))
    assert 'Binding loop detected' not in capfd.readouterr().err
