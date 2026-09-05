"""Global mindmap integration, persistence and real QML interaction tests."""
import json
import uuid

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QPoint, Qt
from PySide6.QtTest import QTest

from actiondraw.model import DiagramModel
from actiondraw.mindmap import MindMapController
from actiondraw.ui import create_actiondraw_window
from progress_crypto import EncryptionCredentials, decrypt_project_data
from task_model import ProjectManager, TabModel, TaskModel


@pytest.fixture
def project(app):
    tasks = TaskModel()
    tabs = TabModel()
    diagram = DiagramModel(tasks)
    pm = ProjectManager(tasks, diagram, tabs)
    return pm, tabs, tasks, diagram


def thought(controller, text='Secret thought', note='Secret note'):
    controller.addThought(False)
    controller.editSelected(text, note)
    return controller.selectedId


def test_create_tab_preserves_thought_branch_and_history(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    parent = thought(m, 'Parent')
    node_id = thought(m, 'New workspace', 'Keep these notes')
    child = thought(m, 'Child')
    m.select(node_id)
    m.toggleFold()
    count = len(list(m.map.walk()))
    tab_count = tabs.tabCount
    current_tab = tabs.getCurrentTabData().id
    pm.showMindmap()
    assert m.canCreateTab
    m.createTabFromSelected()
    created = tabs.getAllTabs()[-1]
    assert tabs.tabCount == tab_count + 1
    assert created.name == 'New workspace'
    assert created.tasks == {'tasks': []}
    assert m.links[node_id] == created.id
    assert len(list(m.map.walk())) == count  # No automatic duplicate root node.
    assert m.map.find(node_id).parent.id == parent
    assert m.map.find(node_id).note == 'Keep these notes'
    assert m.map.find(child).parent.id == node_id
    assert m.map.find(node_id).folded
    assert m.selectedId == node_id and m.selectedNode['isTab']
    assert not m.canCreateTab
    assert pm.mindmapVisible and tabs.getCurrentTabData().id == current_tab
    assert pm.hasUnsavedChanges()
    m.undo()
    assert node_id not in m.links and m.canCreateTab
    assert tabs.tabCount == tab_count + 1  # Undo must not destroy project data.
    assert list(m.links.values()).count(created.id) == 1
    m.redo()
    assert m.links[node_id] == created.id
    assert len(list(m.map.walk())) == count
    payload = m.to_dict()
    m.load(payload)
    assert m.to_dict() == payload
    tabs.renameTab(tab_count, 'Renamed workspace')
    assert m.map.find(node_id).text == 'Renamed workspace'
    m.activate(node_id)
    assert tabs.getCurrentTabData().id == created.id
    assert pm.mindmapVisible and m.view_root.id == node_id


def test_create_tab_requires_one_unlinked_nonroot_node(project):
    m = project[0].mindmap
    tabs = project[1]
    count = tabs.tabCount
    assert not m.canCreateTab
    m.createTabFromSelected()
    m.select(next(iter(m.links)))
    assert not m.canCreateTab
    m.createTabFromSelected()
    first = thought(m, 'First')
    second = thought(m, 'Second')
    m.select(first, 'add')
    assert not m.canCreateTab
    m.createTabFromSelected()
    assert tabs.tabCount == count
    m.select(second)
    m.createTabFromSelected()
    m.createTabFromSelected()
    assert tabs.tabCount == count + 1
    standalone = MindMapController()
    thought(standalone)
    assert not standalone.canCreateTab
    standalone.createTabFromSelected()


@pytest.mark.parametrize('title', ['', '  Main  '])
def test_create_tab_uses_normal_tab_naming(project, title):
    m, tabs = project[0].mindmap, project[1]
    node_id = thought(m, title)
    m.createTabFromSelected()
    created = tabs.getAllTabs()[-1]
    assert created.name == (title.strip() or f'Tab {tabs.tabCount}')
    assert m.map.find(node_id).text == created.name
    assert m.links[node_id] == created.id
    assert len(set(m.links.values())) == tabs.tabCount


def test_tab_identity_reconciliation_and_history(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    first = tabs.getAllTabs()[0].id
    first_node = next(k for k, v in m.links.items() if v == first)
    m.select(first_node)
    child = thought(m)
    tabs.addTab('Main')
    second = tabs.getAllTabs()[1].id
    tabs.renameTab(0, 'Renamed')
    tabs.moveTab(0, 1)
    assert m.map.find(first_node).text == 'Renamed'
    assert m.map.find(child).parent.id == first_node
    pm.showMindmap()
    m.activate(first_node)
    assert tabs.getCurrentTabData().id == first
    assert pm.mindmapVisible and m.view_root.id == first_node
    pm.goBack()
    assert pm.mindmapVisible
    tabs.removeTab(1)
    assert first_node not in m.links
    assert m.map.find(first_node).text == 'Renamed'
    assert m.map.find(child).parent.id == first_node
    m.undo()
    m.redo()
    assert set(m.links.values()) == {second}
    assert m.map.find(child).note == 'Secret note'


def test_edit_move_fold_delete_and_cycle_guard(project):
    m = project[0].mindmap
    branch = thought(m, 'Branch')
    child = thought(m, 'Child')
    before = m.to_dict()
    errors = []
    m.errorOccurred.connect(errors.append)
    m.moveNode(branch, child, 'child')
    assert errors and m.to_dict() == before
    m.select(branch)
    m.toggleFold()
    assert child not in {n['id'] for n in m.nodes}
    m.undo()
    assert child in {n['id'] for n in m.nodes}
    tab_node = next(iter(m.links))
    m.moveNode(tab_node, branch, 'child')
    m.select(branch)
    m.deleteSelected()
    assert m.map.find(branch) is not None
    m.moveNode(tab_node, m.map.root.id, 'child')
    m.select(branch)
    m.deleteSelected()
    assert m.map.find(child) is None
    m.undo()
    assert m.map.find(child).parent.id == branch
    m.setSide('left')
    assert m.map.find(branch).side == 'left'


def test_reordering_and_tab_label_readonly(project):
    m = project[0].mindmap
    a = thought(m, 'A')
    m.select(m.map.root.id)
    b = thought(m, 'B')
    m.moveNode(b, a, 'before')
    assert m.map.root.children.index(m.map.find(b)) < m.map.root.children.index(m.map.find(a))
    m.moveNode(b, a, 'after')
    assert m.map.root.children.index(m.map.find(b)) > m.map.root.children.index(m.map.find(a))
    m.select(next(iter(m.links)))
    m.editSelected('Attempt to rename tab', 'Tab reasoning')
    assert m.selectedNode['text'] == 'Main'
    assert m.selectedNode['note'] == 'Tab reasoning'


def test_sibling_reorder_preserves_branch_and_history(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    tab_node = m.map.find(next(iter(m.links)))
    a, b, c = [tab_node.add_child(text) for text in ('A', 'B', 'C')]
    child = b.add_child('Child', note='Keep this')
    b.folded = True
    m.select(b.id)
    m.toggleCompleted()
    before = m.to_dict()
    history = len(m._undo)
    m.reorderNodeAt(b.id, -10000)
    assert [n.id for n in tab_node.children] == [b.id, a.id, c.id]
    assert len(m._undo) == history + 1
    assert m.map.find(child.id).parent.id == b.id
    assert b.folded and b.id in m._completed
    assert m.links[tab_node.id] == tabs.getAllTabs()[0].id
    assert pm.hasUnsavedChanges()
    after = m.to_dict()
    m.undo()
    assert m.to_dict() == before
    m.redo()
    assert m.to_dict() == after
    m.load(after)
    assert m.to_dict() == after
    m.reorderNodeAt(b.id, 10000)
    assert [n.id for n in m.map.find(tab_node.id).children] == [a.id, c.id, b.id]
    m.reorderNode(b.id, -1)
    assert [n.id for n in m.map.find(tab_node.id).children] == [a.id, b.id, c.id]


def test_reorder_boundaries_and_scope(project):
    m = project[0].mindmap
    tab_id = next(iter(m.links))
    tab = m.map.find(tab_id)
    a = tab.add_child('A', side='right')
    b = tab.add_child('B', side='right')
    outside = m.map.root.add_child('Outside')
    m.set_scope(m.links[tab_id])
    before = m.to_dict()
    for node_id, direction in [(a.id, -1), (b.id, 1), (tab_id, 1), (outside.id, -1), ('missing', 1)]:
        assert not m.canReorderNode(node_id, direction)
        m.reorderNode(node_id, direction)
        if node_id in (tab_id, outside.id, 'missing'):
            m.reorderNodeAt(node_id, 10000)
    m.reorderNodeAt(a.id, m._layout()[a].center_y)
    assert m.to_dict() == before and not m.canUndo
    assert m.canReorderNode(a.id, 1)
    m.reorderNode(a.id, 1)
    assert tab.children == [b, a]
    assert a.parent is tab and b.parent is tab


def test_reorder_keeps_automatic_and_explicit_sides(project):
    from actiondraw._vendor.pyplane.layout import assigned_sides
    m = project[0].mindmap
    for i in range(7):
        m.map.root.add_child(str(i))
    m.map.root.children[-1].side = 'left'
    sides = assigned_sides(m.map)
    before_sides = {n.id: side for n, side in sides.items()}
    for side in ('left', 'right'):
        siblings = [n for n in m.map.root.children if sides[n] == side]
        source = siblings[-1]
        m.reorderNodeAt(source.id, -10000)
        actual = [n for n in m.map.root.children if n.side == side]
        assert actual == [source] + siblings[:-1]
        assert {n.id: s for n, s in assigned_sides(m.map).items()} == before_sides


@pytest.mark.parametrize('zoom,pan', [(1.0, 0), (0.55, 35)])
def test_qml_ctrl_drag_reorder_and_context_target(project, app, zoom, pan):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    parent = m.map.find(next(iter(m.links)))
    siblings = [parent.add_child(text) for text in ('A', 'B', 'C')]
    a, b, c = siblings
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    pane.setProperty('zoom', zoom)
    pane.setProperty('panX', pan - m._layout()[a].x * zoom)
    pane.setProperty('panY', pan)
    QTest.qWait(30)

    def find_item(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find_item(child, name)
            if found is not None:
                return found
        return None

    def center(node_id):
        item = find_item(window.contentItem(), 'mindmapNode_' + node_id)
        return item.mapToScene(item.boundingRect().center()).toPoint()

    start = center(c.id)
    destination = center(a.id) - QPoint(0, 35)
    QTest.mousePress(window, Qt.LeftButton, Qt.ControlModifier, start)
    QTest.mouseMove(window, start - QPoint(0, 15), 30)
    QTest.mouseMove(window, destination, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.ControlModifier, destination)
    QTest.qWait(50)
    assert parent.children == [c, a, b]
    assert c.parent is parent and pm.mindmapVisible
    assert m.selectedIds == [c.id]
    # Ctrl+click still toggles, without moving anything.
    QTest.mouseClick(window, Qt.LeftButton, Qt.ControlModifier, center(a.id))
    assert set(m.selectedIds) == {c.id, a.id}
    assert m.selectedId == a.id
    # Right-click an already-selected node which is not the primary selection.
    QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, center(c.id))
    QTest.qWait(30)
    menu = window.findChild(QObject, 'mindmapNodeMenu')
    up = window.findChild(QObject, 'mindmapMoveUp')
    down = window.findChild(QObject, 'mindmapMoveDown')
    assert menu.property('targetNodeId') == c.id
    assert not up.property('enabled') and down.property('enabled')
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     down.mapToScene(down.boundingRect().center()).toPoint())
    QTest.qWait(50)
    assert parent.children == [a, c, b]
    assert m.selectedId == c.id
    # A downward drag ignores horizontal movement and can finish in empty space.
    start = center(a.id)
    destination = center(b.id) + QPoint(35, 35)
    QTest.mousePress(window, Qt.LeftButton, Qt.ControlModifier, start)
    QTest.mouseMove(window, start + QPoint(0, 15), 30)
    QTest.mouseMove(window, destination, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.ControlModifier, destination)
    QTest.qWait(50)
    assert parent.children == [c, b, a]
    # Losing the mouse grab cancels the drag and restores layout bindings.
    before = m.to_dict()
    start = center(a.id)
    QTest.mousePress(window, Qt.LeftButton, Qt.ControlModifier, start)
    QTest.mouseMove(window, start - QPoint(0, 15), 30)
    QTest.mouseMove(window, start - QPoint(0, 70), 30)
    item = find_item(window.contentItem(), 'mindmapNode_' + a.id)
    area = find_item(item, 'mindmapNodeMouse_' + a.id)
    assert item.y() != m._layout()[a].y
    area.ungrabMouse()
    QTest.mouseRelease(window, Qt.LeftButton, Qt.ControlModifier, start - QPoint(0, 70))
    QTest.qWait(30)
    assert m.to_dict() == before
    assert item.y() == m._layout()[a].y
    # A subsequent relayout must still update the cancelled delegate.
    m.reorderNode(a.id, -1)
    QTest.qWait(30)
    item = find_item(window.contentItem(), 'mindmapNode_' + a.id)
    assert item.y() == m._layout()[a].y
    window.close()


def test_qml_ctrl_arrows_reorder_and_editor_isolation(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    parent = m.map.find(next(iter(m.links)))
    a, b, c = [parent.add_child(text) for text in ('A', 'B', 'C')]
    parent_id = parent.id
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    m.select(b.id)

    def order():
        return [n.id for n in m.map.find(parent_id).children]

    QTest.keyClick(window, Qt.Key_Up, Qt.ControlModifier)
    assert order() == [b.id, a.id, c.id] and m.selectedId == b.id
    before = m.to_dict()
    QTest.keyClick(window, Qt.Key_Up, Qt.ControlModifier)
    assert m.to_dict() == before  # Already first: no change.
    QTest.keyClick(window, Qt.Key_Down, Qt.ControlModifier)
    assert order() == [a.id, b.id, c.id] and m.selectedId == b.id
    QTest.keyClick(window, Qt.Key_Z, Qt.ControlModifier)
    assert order() == [b.id, a.id, c.id]
    QTest.keyClick(window, Qt.Key_Y, Qt.ControlModifier)
    assert order() == [a.id, b.id, c.id]
    QTest.keyClick(window, Qt.Key_Down)
    assert order() == [a.id, b.id, c.id] and m.selectedId == c.id
    QTest.keyClick(window, Qt.Key_Up)
    assert order() == [a.id, b.id, c.id] and m.selectedId == b.id
    QTest.keyClick(window, Qt.Key_F2)
    QTest.qWait(30)
    editor = window.findChild(QObject, 'mindmapNodeEditor')
    assert editor.property('visible')
    before = m.to_dict()
    QTest.keyClick(window, Qt.Key_Up, Qt.ControlModifier)
    QTest.keyClick(window, Qt.Key_Down, Qt.ControlModifier)
    assert m.to_dict() == before
    QTest.keyClick(window, Qt.Key_Escape)
    window.close()


def test_encrypted_roundtrip_dirty_and_scrub(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='mindmap-test-passphrase')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    tab_root = next(iter(pm.mindmap.links))
    pm.mindmap.select(tab_root)
    node_id = thought(pm.mindmap)
    pm.mindmap.toggleCompleted()
    pm.mindmap.select(pm.mindmap.map.root.id)
    pm.mindmap.toggleFold()
    tab_id = tabs.getAllTabs()[0].id
    assert pm.hasUnsavedChanges()
    path = tmp_path / 'map.progress'
    assert pm.saveProject(str(path))
    assert not pm.hasUnsavedChanges()
    envelope = json.loads(path.read_text())
    assert 'Secret thought' not in path.read_text()
    payload = decrypt_project_data(envelope, credentials)
    assert payload['tabs'][0]['id'] == tab_id
    assert 'Secret thought' in payload['mindmap']['xml']
    assert payload['mindmap']['completed'] == [node_id]
    expected = pm.mindmap.to_dict()
    pm.loadProject(str(path))
    assert pm.mindmap.to_dict() == expected
    assert pm.mindmap.map.find(node_id).note == 'Secret note'
    assert tabs.getAllTabs()[0].id == tab_id
    assert not pm.hasUnsavedChanges()
    assert pm.mindmapVisible and pm.mindmap.view_root.id == tab_root
    pm.mindmap.select(node_id)
    pm.mindmap.editSelected('Changed', 'Changed note')
    assert pm.hasUnsavedChanges()
    pm.mindmap.undo()
    assert not pm.hasUnsavedChanges()
    pm.scrubProjectData()
    assert 'Secret' not in str(pm.mindmap.to_dict())
    assert pm.mindmap.to_dict()['completed'] == []
    assert not pm.mindmap._view_selections
    assert not pm.mindmap.canUndo and not pm.mindmap.canRedo
    assert pm.mindmap.selectedId == pm.mindmap.map.root.id


@pytest.mark.parametrize('payload', [
    {'version': '1.0', 'tasks': {'tasks': []}, 'diagram': {'items': []}},
    {'version': '1.1', 'tabs': [{'name': 'A'}, {'name': 'A'}], 'active_tab': 1},
])
def test_legacy_project_migration(project, tmp_path, payload):
    pm, tabs, _, _ = project
    path = tmp_path / 'old.progress'
    path.write_text(json.dumps(payload))
    pm.loadProject(str(path))
    ids = [tab.id for tab in tabs.getAllTabs()]
    assert all(uuid.UUID(value) for value in ids)
    assert len(set(ids)) == len(ids)
    assert set(pm.mindmap.links.values()) == set(ids)
    assert not pm.hasUnsavedChanges()
    assert tabs.currentTabIndex == payload.get('active_tab', 0)


@pytest.mark.parametrize('bad', [{}, {'version': 9}, {'version': 1, 'xml': '<bad>', 'tab_links': {}}, None])
def test_malformed_map_reports_load_error(project, tmp_path, bad):
    pm = project[0]
    errors, loaded = [], []
    pm.errorOccurred.connect(errors.append)
    pm.loadCompleted.connect(loaded.append)
    path = tmp_path / 'bad.progress'
    path.write_text(json.dumps({'version': '1.1', 'tabs': [{'name': 'A'}], 'mindmap': bad}))
    pm.loadProject(str(path))
    assert errors and not loaded


def test_payload_rejects_duplicate_links(project):
    m = project[0].mindmap
    child = thought(m)
    payload = m.to_dict()
    payload['tab_links'][child] = next(iter(m.links.values()))
    with pytest.raises(ValueError):
        MindMapController.decode(payload)


def test_qml_click_drag_back_and_shortcut_isolation(project, app):
    pm, tabs, tasks, diagram = project
    tabs.addTab('Second')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    assert pane is not None
    # Locate actual painted delegate through the visual tree (Repeater owns it visually).
    def find_item(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            result = find_item(child, name)
            if result is not None:
                return result
        return None
    def center(node_id):
        item = find_item(window.contentItem(), 'mindmapNode_' + node_id)
        assert item is not None
        return item.mapToScene(item.boundingRect().center()).toPoint()
    m = pm.mindmap
    tab_id = tabs.getAllTabs()[1].id
    node_id = next(k for k, v in m.links.items() if v == tab_id)
    # Drag into blank space must not drill.
    start = center(node_id)
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, start + QPoint(30, 50), 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, start + QPoint(30, 50))
    QTest.qWait(30)
    assert pm.mindmapVisible
    # Reparent a tab using the actual QML drag interaction.
    first_node = next(k for k, v in m.links.items() if v == tabs.getAllTabs()[0].id)
    start, destination = center(node_id), center(first_node)
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, start + QPoint(20, 0), 30)
    QTest.mouseMove(window, destination, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, destination)
    QTest.qWait(30)
    assert m.map.find(node_id).parent.id == first_node
    assert pm.mindmapVisible
    pane.setProperty('zoom', 0.55)
    pane.setProperty('panX', 35.0)
    QTest.qWait(30)
    QTest.mouseMove(window, center(node_id))
    QTest.qWait(900)  # A visible tooltip must not intercept tab activation.
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, center(node_id))
    QTest.qWait(30)
    assert not pm.mindmapVisible
    assert tabs.getCurrentTabData().id == tab_id
    pm.goBack()
    QTest.qWait(30)
    assert pm.mindmapVisible
    assert pane.property('zoom') == 0.55 and pane.property('panX') == 35.0
    assert m.selectedId == node_id
    # Keyboard selection does not drill; Tab adds a thought beneath a tab.
    QTest.keyClick(window, Qt.Key_Left)
    assert m.selectedId == first_node and pm.mindmapVisible
    QTest.keyClick(window, Qt.Key_Tab)
    created = m.selectedId
    assert m.map.find(created).parent.id == first_node
    assert created not in m.links
    editor = window.findChild(QObject, 'mindmapNodeEditor')
    assert editor.property('visible')
    title = window.findChild(QObject, 'mindmapNodeTitle')
    assert title.property('selectedText') == 'New thought'
    node_count = len(list(m.map.walk()))
    for character in 'first idea':
        QTest.keyClick(window, Qt.Key(ord(character.upper())))
    QTest.keyClick(window, Qt.Key_Return)
    assert not editor.property('visible')
    assert m.map.find(created).text == 'first idea'
    assert len(list(m.map.walk())) == node_count
    # Focus returns to the map for immediately creating and naming the next sibling.
    QTest.keyClick(window, Qt.Key_Return)
    created = m.selectedId
    assert editor.property('visible')
    assert m.map.find(created).parent.id == first_node
    assert title.property('selectedText') == 'New thought'
    for character in 'second idea':
        QTest.keyClick(window, Qt.Key(ord(character.upper())))
    QTest.keyClick(window, Qt.Key_Enter)
    assert not editor.property('visible')
    assert m.map.find(created).text == 'second idea'
    assert len(list(m.map.walk())) == node_count + 1
    QTest.keyClick(window, Qt.Key_F2)
    QTest.keyClick(window, Qt.Key_Left)
    QTest.keyClick(window, Qt.Key_Return, Qt.ControlModifier)
    assert m.selectedId == created and pm.mindmapVisible
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(50)
    assert not editor.property('visible')
    # Navigation pans the selected node back into view without changing zoom.
    m.select(m.map.root.id)
    pane.setProperty('panX', -2000.0)
    pane.setProperty('panY', -2000.0)
    QTest.keyClick(window, Qt.Key_Right)
    assert m.selectedId == first_node
    viewport = window.findChild(QObject, 'mindmapViewport')
    selected_item = find_item(window.contentItem(), 'mindmapNode_' + first_node)
    selected_center = selected_item.mapToItem(viewport, selected_item.boundingRect().center())
    assert 0 < selected_center.x() < viewport.width()
    assert 0 < selected_center.y() < viewport.height()
    assert pane.property('zoom') == 0.55
    QTest.keyClick(window, Qt.Key_Return, Qt.ControlModifier)
    assert pm.mindmapVisible and m.tabScoped and tabs.getCurrentTabData().id == m.links[first_node]
    pm.goBack()
    QTest.qWait(30)
    # Ctrl+click selects a tab for adding thoughts; ordinary clicks still drill.
    m.select(m.map.root.id)
    QTest.mouseClick(window, Qt.LeftButton, Qt.ControlModifier, center(first_node))
    assert pm.mindmapVisible and m.selectedId == first_node
    # Map Delete cannot remove a selected diagram item.
    item_id = diagram.addBox(0, 0)
    window.setProperty('selectedItemId', item_id)
    count = diagram.rowCount()
    deletable = thought(m, "Delete me")
    QTest.keyClick(window, Qt.Key_Delete)
    assert m.map.find(deletable) is None
    assert diagram.rowCount() == count
    # Convert the selected thought with the actual toolbar control, staying in
    # the map until Open tab (or ordinary activation) is explicitly used.
    create_button = window.findChild(QObject, 'mindmapCreateTab')
    m.select(m.map.root.id)
    assert not create_button.property('enabled')
    convertible = thought(m, 'Created from mindmap')
    QTest.qWait(30)
    assert create_button.property('enabled')
    tab_count = tabs.tabCount
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     create_button.mapToScene(create_button.boundingRect().center()).toPoint())
    QTest.qWait(30)
    assert tabs.tabCount == tab_count + 1
    assert m.selectedId == convertible and m.selectedNode['isTab']
    assert pm.mindmapVisible
    assert not create_button.property('enabled')
    pm.scrubProjectData()
    QTest.qWait(30)
    assert not warnings, warnings
    window.close()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_notes_preserve_whitespace_in_save_and_history(project):
    m = project[0].mindmap
    text = "  indented\n\n    code\n"
    node_id = thought(m, "Notes", text)
    payload = m.to_dict()
    m.load(payload)
    assert m.map.find(node_id).note == text
    m.select(node_id)
    m.editSelected("Notes", "other")
    m.undo()
    assert m.map.find(node_id).note == text


def test_keyboard_navigation_directions_and_folded_nodes(project):
    pm = project[0]
    m = pm.mindmap
    tab = m.map.find(next(iter(m.links)))
    tab.side = 'right'
    upper = tab.add_child('Upper')
    lower = tab.add_child('Lower')
    left = m.map.root.add_child('Left', side='left')
    m.reconcile()
    payload = m.to_dict()
    activated, revealed = [], []
    m.tabActivated.connect(activated.append)
    m.revealNode.connect(revealed.append)
    m.select(m.map.root.id)
    m.navigate('left')
    assert m.selectedId == left.id
    m.navigate('right')
    assert m.selectedId == m.map.root.id
    m.navigate('right')
    assert m.selectedId == tab.id
    m.navigate('right')
    assert m.selectedId == upper.id
    m.navigate('down')
    assert m.selectedId == lower.id
    m.navigate('up')
    assert m.selectedId == upper.id
    m.navigate('left')
    assert m.selectedId == tab.id
    assert not activated and revealed[-1] == tab.id
    assert m.to_dict() == payload and not m.canUndo
    m.toggleFold()
    m.navigate('right')
    assert m.selectedId == tab.id
    # A selection hidden by a folded ancestor returns to that visible ancestor.
    m.select(lower.id)
    m.navigate('down')
    assert m.selectedId == tab.id
    m.navigate('invalid')
    assert m.selectedId == tab.id


def test_multi_cut_paste_preserves_branches_tab_links_and_history(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    root = m.map.root
    tab = m.map.find(next(iter(m.links)))
    parent = root.add_child('Branch')
    child = parent.add_child('Nested', note='Keep this note')
    target = root.add_child('Destination')
    target.folded = True
    m.reconcile()
    m.select(parent.id)
    m.select(child.id, 'toggle')
    m.select(tab.id, 'toggle')
    selected = set(m.selectedIds)
    before = m.to_dict()
    m.cutSelected()
    assert m.canPaste and set(m.cutNodeIds) == selected
    assert m.to_dict() == before  # Pending cut never removes unsaved content.
    m.select(target.id)
    m.pasteSelected()
    assert not m.canPaste
    assert [node.id for node in target.children] == [tab.id, parent.id]
    assert child.parent is parent and child.note == 'Keep this note'
    assert not target.folded and len(m.links) == tabs.tabCount
    assert set(m.selectedIds) == {tab.id, parent.id}
    after = m.to_dict()
    m.undo()
    assert m.to_dict() == before
    assert m.selectedIds == [target.id]
    m.redo()
    assert m.to_dict() == after
    assert set(m.selectedIds) == {tab.id, parent.id}


def test_multi_paste_rejects_cycles_without_partial_moves(project):
    m = project[0].mindmap
    a = m.map.root.add_child('A')
    descendant = a.add_child('Inside A')
    b = m.map.root.add_child('B')
    m.reconcile()
    m.select(b.id)
    m.select(a.id, 'toggle')
    m.cutSelected()
    before = m.to_dict()
    errors = []
    m.errorOccurred.connect(errors.append)
    for destination in (a, descendant):
        m.select(destination.id)
        m.pasteSelected()
        assert errors and m.to_dict() == before and m.canPaste
    m.cancelCut()
    assert not m.canPaste and not m.cutNodeIds
    m.select(m.map.root.id)
    assert not m.canCut
    m.cutSelected()
    assert not m.canPaste
    m.select(a.id, 'toggle')
    assert m.selectedIds == [a.id] and m.canCut


def test_pending_cut_tracks_tab_changes_and_clears_on_scrub(project):
    pm, tabs, _, _ = project
    tabs.addTab('Delete this tab')
    m = pm.mindmap
    node_id = next(key for key, value in m.links.items() if value == tabs.getAllTabs()[1].id)
    m.select(node_id)
    m.cutSelected()
    tabs.renameTab(1, 'Renamed')
    assert m.map.find(node_id).text == 'Renamed'
    tabs.removeTab(1)
    assert node_id not in m.links and m.canPaste
    m.select(m.map.root.id)
    m.pasteSelected()
    assert m.map.find(node_id).text == 'Renamed'
    m.cutSelected()
    pm.scrubProjectData()
    assert not m.canPaste and not m.cutNodeIds
    assert m.selectedIds == [m.map.root.id]
    assert 'Renamed' not in str(m.to_dict())


def test_multiselection_toggle_range_and_keyboard_extension(project):
    m = project[0].mindmap
    a = m.map.root.add_child('A', side='right')
    hidden = a.add_child('Hidden')
    a.folded = True
    b = m.map.root.add_child('B', side='right')
    c = m.map.root.add_child('C', side='right')
    m.reconcile()
    m.select(a.id)
    m.select(c.id, 'range')
    assert m.selectedIds == [a.id, b.id, c.id]
    assert hidden.id not in m.selectedIds
    m.select(b.id, 'toggle')
    assert set(m.selectedIds) == {a.id, c.id}
    m.select(c.id, 'toggle')
    m.select(a.id, 'toggle')
    assert not m.selectedIds and not m.canCut
    m.select(a.id)
    before = m.to_dict()
    m.navigate('down', True)
    assert set(m.selectedIds) == {a.id, b.id}
    assert m.to_dict() == before


def test_multi_delete_is_atomic_and_undo_restores_selection(project):
    m = project[0].mindmap
    a = m.map.root.add_child('A')
    child = a.add_child('Child')
    b = m.map.root.add_child('B')
    m.reconcile()
    m.select(a.id)
    m.select(child.id, 'toggle')
    m.select(b.id, 'toggle')
    before = m.to_dict()
    selected = m.selectedIds
    m.deleteSelected()
    assert m.map.find(a.id) is None and m.map.find(b.id) is None
    m.undo()
    assert m.to_dict() == before and m.selectedIds == selected
    m.select(next(iter(m.links)), 'toggle')
    m.deleteSelected()
    assert m.to_dict() == before


def test_qml_multi_selection_cut_and_paste(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    tab_id = next(iter(m.links))
    m.map.find(tab_id).side = 'left'
    a, b, c = [m.map.root.add_child(label, side='right') for label in ('A', 'B', 'C')]
    m.reconcile()
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(message.toString() for message in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)

    def item_for(node_id):
        def find(item):
            if item.objectName() == 'mindmapNode_' + node_id:
                return item
            for child in item.childItems():
                found = find(child)
                if found is not None:
                    return found
            return None
        return find(window.contentItem())

    def click(node_id, modifier=Qt.NoModifier):
        item = item_for(node_id)
        QTest.mouseClick(window, Qt.LeftButton, modifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())

    try:
        click(a.id, Qt.ControlModifier)
        click(b.id, Qt.ControlModifier)
        assert set(m.selectedIds) == {a.id, b.id}
        click(c.id, Qt.ShiftModifier)
        assert set(m.selectedIds) == {b.id, c.id}
        click(a.id, Qt.ControlModifier)
        assert all(item_for(node.id).property('selected') for node in (a, b, c))
        QTest.keyClick(window, Qt.Key_X, Qt.ControlModifier)
        assert m.canPaste and item_for(a.id).opacity() < 1
        click(tab_id)
        assert pm.mindmapVisible and m.selectedId == tab_id
        QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
        assert not m.canPaste
        assert [node.id for node in m.map.find(tab_id).children] == [a.id, b.id, c.id]
        QTest.keyClick(window, Qt.Key_Z, Qt.ControlModifier)
        assert all(m.map.find(node.id).parent is m.map.root for node in (a, b, c))
        QTest.keyClick(window, Qt.Key_Y, Qt.ControlModifier)
        assert all(m.map.find(node.id).parent.id == tab_id for node in (a, b, c))
        QTest.keyClick(window, Qt.Key_X, Qt.ControlModifier)
        QTest.keyClick(window, Qt.Key_Escape)
        assert not m.canPaste
        assert not warnings, warnings
    finally:
        pm.scrubProjectData()
        QTest.qWait(30)
        window.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def test_tab_scope_shared_edits_and_boundaries(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    tab_root = next(iter(m.links))
    m.select(tab_root)
    child = thought(m, 'Child')
    descendant = thought(m, 'Descendant')
    m.select(m.map.root.id)
    outside = thought(m, 'Outside')
    pm.switchTab(0)
    assert pm.mindmapVisible and m.view_root.id == tab_root
    assert {n['id'] for n in m.nodes} == {tab_root, child, descendant}
    m.select(outside)
    assert m.selectedId == tab_root
    before = m.to_dict()
    m.moveNode(tab_root, child, 'child')
    m.moveNode(child, outside, 'child')
    m.deleteSelected()
    m.cutSelected()
    m.activate(tab_root)
    assert m.to_dict() == before and not m.canPaste and not pm.canGoBack
    m.addThought(True)  # A sibling of the view root becomes its child.
    added = m.selectedId
    assert m.map.find(added).parent.id == tab_root
    m.editSelected('Local edit', 'Local note')
    m.setSide('left')
    decoded, _ = m.decode(m.to_dict())
    assert decoded.find(added).side == 'left'
    m.toggleCompleted()
    pm.showMindmap()
    assert m.map.find(added).text == 'Local edit'
    m.select(added)
    assert m.selectedNode['completed']
    m.undo()
    assert not m.selectedNode['completed']
    m.redo()
    m.editSelected('Global edit', 'Updated note')
    pm.showTabMindmap()
    m.select(added)
    assert m.selectedNode['text'] == 'Global edit'
    assert m.selectedNode['note'] == 'Updated note'
    assert m.selectedNode['completed']
    m.deleteSelected()
    assert added not in m.to_dict()['completed']
    m.undo()
    assert added in m.to_dict()['completed']
    tabs.renameTab(0, 'Renamed')
    assert m.view_root.text == 'Renamed'


def test_tab_views_nested_navigation_and_canvas(project):
    pm, tabs, _, diagram = project
    item_id = diagram.addBox(10, 20)
    m = pm.mindmap
    first = next(iter(m.links))
    tabs.addTab('Nested')
    second = next(k for k, v in m.links.items() if v == tabs.getAllTabs()[1].id)
    m.moveNode(second, first, 'child')
    m.select(second)
    child = thought(m)
    pm.showMindmap()
    m.activate(first)
    assert m.view_root.id == first
    m.activate(second)
    assert m.view_root.id == second and pm.mindmapVisible
    pm.goBack()
    assert m.view_root.id == first and pm.mindmapVisible
    pm.goBack()
    assert not m.tabScoped and pm.mindmapVisible
    pm.switchTab(0)
    pm.showTabCanvas()
    assert not pm.mindmapVisible
    assert any(item['id'] == item_id for item in diagram.to_dict()['items'])
    pm.showTabMindmap()
    assert m.view_root.id == first
    pm.switchTab(1)
    m.select(child)
    m.deleteSelected()
    assert pm.mindmapVisible and m.view_root.id == second
    pm.switchTab(0)
    pm.switchTab(1)
    assert not pm.mindmapVisible
    pm.showTabMindmap()
    assert {n['id'] for n in m.nodes} == {second}
    pm.removeTab(1)
    assert m.view_root.id == first
    assert m.map.find(second) is not None and second not in m.links


def test_completion_selection_legacy_and_validation(project):
    m = project[0].mindmap
    parent = thought(m)
    child = thought(m)
    m.select(parent)
    m.toggleCompleted()
    assert m.to_dict()['completed'] == [parent]
    m.select(child, 'add')
    m.toggleCompleted()
    assert set(m.to_dict()['completed']) == {parent, child}
    m.toggleCompleted()
    assert not m.to_dict()['completed']
    m.undo()
    assert set(m.to_dict()['completed']) == {parent, child}
    payload = m.to_dict()
    m.load(payload)
    assert m.to_dict() == payload
    for invalid in (None, {}, ['missing'], [parent, parent], [1], [[]]):
        with pytest.raises(ValueError, match='completion'):
            m.decode(dict(payload, completed=invalid))
    del payload['completed']
    m.load(payload)
    assert not any(n['completed'] for n in m.nodes)


def test_qml_tab_switch_completion_and_editor_focus(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    root_id = next(iter(m.links))
    m.select(root_id)
    child = thought(m)
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(x.toString() for x in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.switchTab(0)
    QTest.qWait(100)
    pane = window.findChild(QObject, 'mindmapPane')
    m.select(child)
    pane.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_F4)
    assert m.selectedNode['completed']
    button = window.findChild(QObject, 'mindmapComplete')
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     button.mapToScene(button.boundingRect().center()).toPoint())
    assert not m.selectedNode['completed']
    QTest.keyClick(window, Qt.Key_F2)
    QTest.keyClick(window, Qt.Key_F4)
    assert not m.selectedNode['completed']
    QTest.keyClick(window, Qt.Key_Escape)
    canvas = window.findChild(QObject, 'tabMindmapCanvas')
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     canvas.mapToScene(canvas.boundingRect().center()).toPoint())
    assert not pm.mindmapVisible
    switch = window.findChild(QObject, 'tabMindmapSwitch')
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     switch.mapToScene(switch.boundingRect().center()).toPoint())
    assert pm.mindmapVisible and m.view_root.id == root_id
    assert not warnings
    window.close()
    engine.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
