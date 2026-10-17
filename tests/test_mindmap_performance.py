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
    tabs.addTab("Main")
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


@pytest.mark.parametrize('navigation', ['reminder', 'kanban', 'keyboard'])
def test_large_map_navigation_uses_search_highlight(app, actiondraw_window, navigation):
    from PySide6.QtCore import QObject
    from PySide6.QtQml import QQmlProperty
    from PySide6.QtTest import QTest
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab("Main")
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    m = project.mindmap
    branch = m.map.root.add_child('Large branch')
    children = [branch.add_child(f'Thought {i}') for i in range(300)]
    target = children[-1]
    engine = actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    project.showMindmap()
    QTest.qWait(50)
    pane = window.findChild(QObject, 'mindmapPane')
    pane.setProperty('zoom', 0.7)

    def find(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find(child, name)
            if found is not None:
                return found

    if navigation == 'keyboard':
        m.select(children[-2].id)
        m.navigate('down')
    else:
        branch.folded = True
        project.showTabCanvas()
        if navigation == 'reminder':
            project.openMindmapReminder(target.id)
        else:
            project.openKanbanItem('node:' + target.id)
    QTest.qWait(50)
    assert m.selectedId == target.id and not m.searchQuery
    highlight = find(window.contentItem(), 'mindmapSearchHighlight_' + target.id)
    assert highlight is not None and highlight.isVisible()
    assert QQmlProperty.read(highlight, 'border.color').name() == '#ffbf47'
    assert QQmlProperty.read(highlight, 'border.width') * pane.property('zoom') == pytest.approx(4)
    assert highlight.opacity() == 1
    # A regular selection ends the jump highlight, including when selected again.
    m.select(branch.id)
    m.select(target.id)
    assert not highlight.isVisible()
    m.searchText('no matches')
    project.openMindmapReminder(target.id)
    assert not m.searchQuery
    QTest.qWait(20)
    highlight = find(window.contentItem(), 'mindmapSearchHighlight_' + target.id)
    assert highlight.isVisible()
    m.searchText('no matches')
    assert not highlight.isVisible()


def test_overview_timer_sleeps_when_empty_or_hidden(app, actiondraw_window):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab('Main')
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    engine = actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    QTest.qWait(20)
    timer = window.findChild(QObject, 'overviewRefreshTimer')
    assert not timer.property('running')
    # A first reminder must wake the overview through a signal, not polling.
    assert project.addStandaloneReminder('Reminder', '2099-01-01 12:00', False)
    QTest.qWait(20)
    assert timer.property('running')
    window.hide()
    QTest.qWait(20)
    assert not timer.property('running')
    window.show()
    QTest.qWait(20)
    assert timer.property('running')
    project.clearStandaloneReminder(0)
    QTest.qWait(20)
    assert not timer.property('running')
    project._reminder_timer.stop()


def test_scene_shares_layout_between_nodes_and_edges(app):
    m = MindMapController()
    branch = m.map.root.add_child('Branch')
    for i in range(300):
        branch.add_child(f'Thought {i}')
    expected_nodes, expected_edges = m.nodes, m.edges
    with patch.object(m, '_layout', wraps=m._layout) as layout:
        scene = m.scene
    assert layout.call_count == 1
    assert scene == {'nodes': expected_nodes, 'edges': expected_edges}


def test_contract_ticks_do_not_rebuild_mindmap(app):
    import time
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab('Main')
    project = ProjectManager(tasks, DiagramModel(tasks), tabs)
    tasks.addTask('Contract')
    assert tasks.setContractAt(0, '2099-01-01 12:00', 'Take a break')
    scenes, ticks, changes, breaches = [], [], [], []
    project.mindmap.sceneChanged.connect(lambda: scenes.append(True))
    tasks.taskContractTick.connect(ticks.append)
    tasks.taskContractChanged.connect(changes.append)
    tasks.taskContractBreached.connect(lambda *args: breaches.append(args))
    with patch.object(tasks, 'to_dict', wraps=tasks.to_dict) as serialize:
        for _ in range(60):
            tasks._updateActiveTasks()
        assert serialize.call_count == 0
    assert len(ticks) == 60 and not scenes and not changes
    tasks._tasks[0].contract_deadline_at = time.time() - 1
    tasks._updateActiveTasks()
    tasks._updateActiveTasks()
    assert len(breaches) == len(changes) == 1
    assert scenes  # A real breach still updates persisted state and the UI.
    tasks._timer.stop()
    project._reminder_timer.stop()


def test_map_deadline_timer_only_runs_when_needed(app, actiondraw_window):
    from PySide6.QtCore import QObject
    from PySide6.QtTest import QTest
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab('Main')
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    engine = actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    project.showMindmap()
    QTest.qWait(20)
    timer = window.findChild(QObject, 'mindmapDeadlineTimer')
    assert not timer.property('running')
    node = project.mindmap.map.root
    assert project.mindmap.setDeadline(node.id, 5)
    QTest.qWait(20)
    assert timer.property('running')
    window.hide()
    QTest.qWait(20)
    assert not timer.property('running')
    window.show()
    QTest.qWait(20)
    assert timer.property('running')
    project.mindmap.clearDeadline(node.id)
    QTest.qWait(20)
    assert not timer.property('running')
    # Expired countdowns must not keep waking the renderer indefinitely.
    assert project.mindmap.setDeadline(node.id, 5)
    project.mindmap.deadlines[node.id]['start'] -= 600
    project.mindmap.sceneChanged.emit()
    QTest.qWait(20)
    assert not timer.property('running')
    tasks._timer.stop()
    project._reminder_timer.stop()


def test_hidden_canvas_waits_for_geometry_without_busy_loop(app, actiondraw_window):
    from PySide6.QtCore import QObject, QEvent
    from PySide6.QtTest import QTest
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TabModel, TaskModel

    class PostedCalls(QObject):
        count = 0

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.MetaCall:
                self.count += 1
            return False

    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab('Main')
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    engine = actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    project.showMindmap()
    QTest.qWait(100)
    assert window.property('defaultViewPending') is True
    calls = PostedCalls()
    app.installEventFilter(calls)
    try:
        QTest.qWait(100)
        # Formerly thousands of self-posted applyDefaultView calls while idle.
        assert calls.count < 20
    finally:
        app.removeEventFilter(calls)
    project.showTabCanvas()
    QTest.qWait(100)
    assert window.property('defaultViewPending') is False
    assert window.property('zoomLevel') == pytest.approx(0.95)
    window.setProperty('zoomLevel', 1.4)
    window.setWidth(window.width() + 20)
    QTest.qWait(50)
    assert window.property('zoomLevel') == pytest.approx(1.4)
    tasks._timer.stop()
    project._reminder_timer.stop()
