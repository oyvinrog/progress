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
    assert not pm.mindmapVisible
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


def test_encrypted_roundtrip_dirty_and_scrub(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='mindmap-test-passphrase')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    node_id = thought(pm.mindmap)
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
    expected = pm.mindmap.to_dict()
    pm.loadProject(str(path))
    assert pm.mindmap.to_dict() == expected
    assert pm.mindmap.map.find(node_id).note == 'Secret note'
    assert tabs.getAllTabs()[0].id == tab_id
    assert not pm.hasUnsavedChanges()
    assert not pm.mindmapVisible
    pm.mindmap.select(node_id)
    pm.mindmap.editSelected('Changed', 'Changed note')
    assert pm.hasUnsavedChanges()
    pm.mindmap.undo()
    assert not pm.hasUnsavedChanges()
    pm.scrubProjectData()
    assert 'Secret' not in str(pm.mindmap.to_dict())
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
    assert not pm.mindmapVisible and tabs.getCurrentTabData().id == m.links[first_node]
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
