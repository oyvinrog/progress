"""Shared tab branches: content identity, structural edges and graph integrity."""
import copy

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtTest import QTest

from actiondraw.mindmap import MindMapController
from actiondraw.model import DiagramModel
from actiondraw.ui import create_actiondraw_window
from task_model import ProjectManager, TabModel, TaskModel


@pytest.fixture
def project(app):
    tasks, tabs = TaskModel(), TabModel()
    diagram = DiagramModel(tasks)
    pm = ProjectManager(tasks, diagram, tabs)
    tabs.addTab('dagens oppgaver')
    daily = tabs.getAllTabs()[-1].id
    tabs.addTab('fikse matpakke til barna')
    lunch = tabs.getAllTabs()[-1].id
    m = pm.mindmap
    roots = {tab: key for key, tab in m.links.items()}
    m.select(roots[lunch])
    m.addThought(False)
    m.editSelected('Finn matbokser', 'Fra kjøkkenskapet')
    child = m.selectedId
    m.set_scope(daily)
    return pm, tabs, tasks, diagram, daily, lunch, roots, child


def reference(project):
    m = project[0].mindmap
    assert m.addTabReference(m.view_root.id, project[5])
    return m.selectedId


def occurrence(m, source, reference_id):
    return next(n['id'] for n in m.nodes if n['sourceId'] == source and n['id'].startswith(reference_id + '/'))


def test_shared_editing_and_reference_deletion(project):
    pm, tabs, tasks, diagram, daily, lunch, roots, child = project
    m = pm.mindmap
    ref = reference(project)
    assert m.selectedNode['isReference']
    projected_child = occurrence(m, child, ref)
    m.select(projected_child)
    m.editSelected('Pakk brødskiver', 'Husk ost')
    assert m.map.find(child).text == 'Pakk brødskiver'
    m.select(ref)
    m.addThought(False)
    added = m.selectedNode['sourceId']
    assert m.map.find(added).parent.id == roots[lunch]
    assert m.map.find(ref).children == []
    m.set_scope(lunch)
    assert {child, added} <= {n['id'] for n in m.nodes}
    m.select(child)
    m.editSelected('Smør brød', '')
    m.set_scope(daily)
    assert next(n for n in m.nodes if n['sourceId'] == child)['text'] == 'Smør brød'
    m.select(ref)
    m.deleteSelected()
    assert m.map.find(ref) is None
    assert m.map.find(child) and m.map.find(added)
    assert lunch in m.links.values()
    m.undo()
    assert ref in m.references
    m.redo()
    assert ref not in m.references


def test_duplicate_occurrences_metadata_and_child_delete(project):
    m = project[0].mindmap
    a, b = reference(project), reference(project)
    child = project[-1]
    first, second = occurrence(m, child, a), occurrence(m, child, b)
    m.select(first)
    m.select(second, 'add')
    m.toggleCompleted()
    assert m._completed == {child}
    assert all(n['completed'] for n in m.nodes if n['sourceId'] == child)
    m.toggleCompleted()
    assert not m._completed
    m.toggleBookmark(second)
    m.setDeadline(second, 20)
    m.set_reminder(second, 1900000000, True)
    assert list(m.deadlines) == list(m.reminders) == m._bookmarks == [child]
    m.deleteSelected()
    assert m.map.find(child) is None
    assert len(m.references) == 2
    m.undo()
    assert m.map.find(child)
    assert child in m.reminders


def test_cycles_and_move_rollback(project):
    m = project[0].mindmap
    daily, lunch, roots = project[4:7]
    before = m.to_dict()
    assert not m.addTabReference(m.view_root.id, daily)
    assert m.to_dict() == before
    ref = reference(project)
    m.set_scope(lunch)
    before = m.to_dict()
    assert not m.addTabReference(m.view_root.id, daily)
    assert m.to_dict() == before
    m.set_scope()
    before = m.to_dict()
    m.moveNode(ref, roots[lunch], 'child')
    assert m.to_dict() == before
    m.select(ref)
    m.cutSelected()
    m.select(roots[lunch])
    assert not m.pasteSelected()
    assert m.to_dict() == before


def test_nested_references_and_long_cycle(project):
    pm, tabs, _, _, daily, lunch, roots, child = project
    m = pm.mindmap
    outer = reference(project)
    tabs.addTab('Handle mat')
    shopping = tabs.getAllTabs()[-1].id
    assert m.addTabReference(outer, shopping)
    inner = m.selectedId
    assert inner.startswith(outer + '/')
    m.addThought(False)
    leaf = m.selectedNode['sourceId']
    assert m.map.find(leaf).parent.id == next(k for k, v in m.links.items() if v == shopping)
    m.set_scope(shopping)
    before = m.to_dict()
    assert not m.addTabReference(m.view_root.id, daily)
    assert m.to_dict() == before
    m.set_scope(daily)
    m.select(inner)
    m.deleteSelected()
    assert shopping in m.links.values() and m.map.find(leaf)
    assert len(m.references) == 1


def test_roundtrip_validation_original_delete_and_history(project):
    m = project[0].mindmap
    ref = reference(project)
    payload = copy.deepcopy(m.to_dict())
    m.load(payload)
    assert m.references == payload['tab_references']
    m.set_scope(project[4])
    assert occurrence(m, project[-1], ref)
    malformed = copy.deepcopy(payload)
    malformed['tab_references'][ref] = 'missing-tab'
    with pytest.raises(ValueError):
        m.load(malformed)
    assert m.references == payload['tab_references']
    malformed['tab_references'][ref] = project[4]
    with pytest.raises(ValueError, match='circular'):
        MindMapController.decode(malformed)
    m.set_scope()
    m.select(project[6][project[5]])
    m.deleteSelected()
    assert not m.references and m.map.find(ref) is None
    m.undo()
    assert ref in m.references and m.map.find(project[-1])
    m.redo()
    assert not m.references


def test_search_export_navigation_and_local_fold(project):
    m = project[0].mindmap
    a, b = reference(project), reference(project)
    child = project[-1]
    m.select(a)
    m.toggleFold()
    assert occurrence(m, child, b)
    assert not any(n['id'] == a + '/' + child for n in m.nodes)
    m.searchText('Finn matbokser')
    assert m.searchMatchCount == 2
    assert m.selectedNode['sourceId'] == child
    m.navigate('left')
    assert m.selectedNode['isReference']
    assert m.copyBranchAsText(a)
    from PySide6.QtGui import QGuiApplication
    assert 'Finn matbokser' in QGuiApplication.clipboard().text()
    m.toggleBookmark(b + '/' + child)
    m.jumpToBookmark(child)
    assert m.tabScoped and m.selectedNode['sourceId'] == child


def test_qml_add_tab_search_and_edit(project, app):
    pm, tabs, tasks, diagram, daily, lunch, roots, child = project
    m = pm.mindmap
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(x.toString() for x in messages))
    window = engine.rootObjects()[0]
    window.show()
    QTest.qWait(100)

    def find_item(item, name):
        if item.objectName() == name:
            return item
        for nested in item.childItems():
            found = find_item(nested, name)
            if found is not None:
                return found

    def click(item, button=Qt.LeftButton):
        assert item is not None
        QTest.mouseClick(window, button, Qt.NoModifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())
        QTest.qWait(40)

    try:
        click(find_item(window.contentItem(), 'mindmapNodeMouse_' + roots[daily]), Qt.RightButton)
        action = window.findChild(QObject, 'mindmapAddTab')
        click(action)
        dialog = window.findChild(QObject, 'mindmapTabReferenceDialog')
        assert dialog.property('visible')
        search = window.findChild(QObject, 'mindmapTabReferenceSearch')
        search.setProperty('text', 'matpakke')
        QTest.qWait(30)
        options = window.findChild(QObject, 'mindmapTabReferenceList')
        assert options.property('count') == 1
        click(find_item(window.contentItem(), 'mindmapTabOption_' + lunch))
        assert not dialog.property('visible')
        ref = m.selectedId
        projected = occurrence(m, child, ref)
        assert find_item(window.contentItem(), 'mindmapNode_' + projected)
        assert m.selectedNode['isReference']
        # QML receives distinct occurrence ids and opens the normal editor.
        m.select(projected)
        QTest.keyClick(window, Qt.Key_F2)
        QTest.qWait(30)
        editor = window.findChild(QObject, 'mindmapNodeEditor')
        assert editor.property('visible')
        title = window.findChild(QObject, 'mindmapNodeTitle')
        title.setProperty('text', 'Pakk eple')
        from PySide6.QtCore import QMetaObject
        QMetaObject.invokeMethod(editor, 'accept')
        QTest.qWait(30)
        assert m.map.find(child).text == 'Pakk eple'
        m.toggleBookmark(projected)
        m.select(ref)
        from PySide6.QtCore import Q_ARG
        pane = window.findChild(QObject, 'mindmapPane')
        assert QMetaObject.invokeMethod(pane, 'jumpBookmark', Q_ARG('QVariant', child))
        QTest.qWait(30)
        assert m.selectedId == projected
        assert pane.property('bookmarkHighlightId') == projected
        assert not warnings
    finally:
        window.close()
        engine.deleteLater()
        QTest.qWait(20)


def test_move_reorder_paste_and_convert_in_shared_branch(project):
    m = project[0].mindmap
    ref = reference(project)
    child = project[-1]
    m.select(ref)
    m.addThought(False)
    sibling = m.selectedId
    sibling_source = m.sourceNodeId(sibling)
    assert m.canReorderNode(sibling, -1)
    m.reorderNode(sibling, -1)
    assert m.map.find(project[6][project[5]]).children[0].id == sibling_source
    m.select(sibling)
    assert m.canCreateTab
    m.createTabFromSelected()
    assert sibling_source in m.links
    m.select(ref)
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setText('One\n  Two\nThree')
    assert m.pasteSelected()
    assert len(m.selectedIds) == 2
    assert all(m.map.find(m.sourceNodeId(key)).parent.id == project[6][project[5]] for key in m.selectedIds)
    moved = occurrence(m, child, ref)
    m.moveNode(moved, m.view_root.id, 'child')
    assert m.map.find(child).parent.id == project[6][project[4]]
    assert m.selectedId == child
    m.undo()
    assert m.map.find(child).parent.id == project[6][project[5]]


def test_reference_priorities_rename_plan_and_legacy(project):
    pm, tabs, _, _, daily, lunch, roots, child = project
    m = pm.mindmap
    ref = reference(project)
    tabs.renameTab(next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == lunch), 'Matpakker')
    assert next(n for n in m.nodes if n['id'] == ref)['text'] == 'Matpakker'
    assert m.tabReferenceOptions('matpakker')[0]['tabId'] == lunch
    before = m.to_dict()
    m.setPriorityFilter(0.5)
    assert m.nodes and m.edges
    assert m.to_dict() == before  # filtered layout never mutates shared nodes
    m.setPriorityFilter(1)
    m.select(ref)
    assert m.addSelectedToReady()
    assert next(tab for tab in tabs.getAllTabs() if tab.id == lunch).kanban_status == 'ready'
    assert not m._kanban
    m.set_scope()
    m.select(ref)
    m.deleteSelected()
    legacy = m.to_dict()
    del legacy['tab_references']
    m.load(legacy)
    assert not m.references


@pytest.mark.parametrize('encrypted', [False, True])
def test_project_file_roundtrip_and_invalid_load_is_atomic(project, tmp_path, monkeypatch, encrypted):
    import json
    from progress_crypto import EncryptionCredentials, decrypt_project_data, encrypt_project_data
    pm, tabs, _, _, daily, lunch, roots, child = project
    m = pm.mindmap
    ref = reference(project)
    credentials = EncryptionCredentials(passphrase='reference-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'references.progress'
    assert pm.saveProject(str(path))
    expected = m.to_dict()
    if not encrypted:
        payload = decrypt_project_data(json.loads(path.read_text()), credentials)
        path.write_text(json.dumps(payload))
    pm.loadProject(str(path))
    assert m.to_dict() == expected
    assert not pm.hasUnsavedChanges()
    m.set_scope(daily)
    assert occurrence(m, child, ref)
    data = json.loads(path.read_text())
    if encrypted:
        data = decrypt_project_data(data, credentials)
    data['tabs'] = [tab for tab in data['tabs'] if tab['id'] != lunch]
    path.write_text(json.dumps(encrypt_project_data(data, credentials) if encrypted else data))
    old_key = pm._cached_key_material
    old_key_bytes = bytes(old_key.key) if old_key is not None else None
    derived = []
    if encrypted:
        import task_model
        decrypt = task_model.decrypt_and_derive_key_material
        def capture_key(*args):
            result = decrypt(*args)
            derived.append(result[1])
            return result
        monkeypatch.setattr(task_model, 'decrypt_and_derive_key_material', capture_key)
    old_tabs = [tab.id for tab in tabs.getAllTabs()]
    errors = []
    pm.errorOccurred.connect(errors.append)
    pm.loadProject(str(path))
    assert errors and 'missing tab' in errors[-1]
    assert m.to_dict() == expected
    assert old_tabs == [tab.id for tab in tabs.getAllTabs()]
    assert pm._cached_key_material is old_key
    if encrypted:
        assert bytes(old_key.key) == old_key_bytes
        assert derived and not any(derived[0].key)


def test_reorder_between_two_occurrences_of_same_parent(project):
    m = project[0].mindmap
    first, second = reference(project), reference(project)
    m.select(first)
    m.addThought(False)
    middle = m.selectedNode['sourceId']
    m.select(first)
    m.addThought(False)
    last = m.selectedNode['sourceId']
    original = project[-1]
    m.moveNode(first + '/' + original, second + '/' + last, 'before')
    root = m.map.find(project[6][project[5]])
    assert [n.id for n in root.children] == [middle, original, last]
    assert m.selectedId == second + '/' + original


def test_reference_root_metadata_and_sidebar_removal(project):
    pm, tabs, _, _, daily, lunch, roots, child = project
    m = pm.mindmap
    ref = reference(project)
    m.select(ref)
    m.editSelected('Ignored title', 'Shared notes')
    m.toggleCompleted()
    m.toggleBookmark(ref)
    assert m.map.find(roots[lunch]).note == 'Shared notes'
    assert m._completed == {roots[lunch]}
    assert m._bookmarks == [roots[lunch]]
    tab_index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == lunch)
    tabs.removeTab(tab_index)
    assert not m.references
    assert m.map.find(ref) is None
    assert m.nodes
