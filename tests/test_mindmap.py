"""Global mindmap integration, persistence and real QML interaction tests."""
import copy
import json
import math
import uuid

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QMetaObject, QObject, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtQml import QQmlProperty

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


def test_type_search_matches_cycles_and_reveals(project):
    m = project[0].mindmap
    branch = m.map.root.add_child('People')
    first = branch.add_child('Guest')
    second = branch.add_child('Invite guests')
    branch.add_child('Other', note='guest')
    branch.folded = True
    revealed = []
    m.revealNode.connect(revealed.append)
    history = len(m._undo)
    m.searchText('GUEST')
    assert m.selectedId == first.id
    assert not branch.folded
    assert revealed[-1] == first.id
    assert m.searchMatchCount == 2 and m.searchMatchPosition == 1
    m.navigateSearch(1)
    assert m.selectedId == second.id and m.searchMatchPosition == 2
    m.searchText('guests')
    assert m.selectedId == second.id and m.searchMatchCount == 1
    m.searchText('guest')
    assert m.selectedId == second.id
    m.navigateSearch(1)
    assert m.selectedId == first.id
    m.navigateSearch(-1)
    assert m.selectedId == second.id
    count = len(revealed)
    m.searchText('missing')
    assert m.searchMatchCount == 0 and m.searchMatchPosition == 0
    assert m.selectedId == second.id and len(revealed) == count
    m.clearSearch()
    assert m.searchQuery == '' and m.searchMatchCount == 0
    assert len(m._undo) == history
    assert 'searchQuery' not in m.to_dict()


def test_type_search_scope_and_reset(project):
    m = project[0].mindmap
    node_id, tab_id = next(iter(m.links.items()))
    scoped = m.map.find(node_id)
    inside = scoped.add_child('Guest inside')
    m.map.root.add_child('Guest outside')
    m.searchText('guest')
    assert m.searchMatchCount == 2
    m.set_scope(tab_id)
    assert m.searchQuery == ''
    m.searchText('guest')
    assert m.searchMatchCount == 1 and m.selectedId == inside.id
    m.searchText(scoped.text)
    assert m.selectedId == scoped.id
    m.load(m.to_dict())
    assert m.searchQuery == ''


def test_qml_type_search_keyboard_and_focus(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    branch = m.map.root.add_child('People')
    first = branch.add_child('Guest one')
    second = branch.add_child('Guest two')
    branch.folded = True
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)

    def type_text(text):
        for character in text:
            QTest.keyClick(window, character)

    pane = window.findChild(QObject, 'mindmapPane')
    indicator = window.findChild(QObject, 'mindmapSearchIndicator')
    pane.setProperty('zoom', 1.2)
    pane.setProperty('panX', -10000)
    type_text('guest')
    QTest.qWait(30)
    assert m.searchQuery == 'guest' and m.selectedId == first.id
    assert indicator.property('visible') and '1/2' in indicator.property('text')
    assert pane.property('zoom') == 1.2 and pane.property('panX') != -10000
    viewport = window.findChild(QObject, 'mindmapViewport')
    box = m._layout()[first]
    left = viewport.width() / 2 + pane.property('panX') + box.x * 1.2
    top = viewport.height() / 2 + pane.property('panY') + box.y * 1.2
    assert 0 <= left <= viewport.width() - box.width * 1.2
    assert 0 <= top <= viewport.height() - box.height * 1.2
    assert not branch.folded
    QTest.keyClick(window, Qt.Key_Return)
    assert m.selectedId == second.id
    QTest.keyClick(window, Qt.Key_Return, Qt.ShiftModifier)
    assert m.selectedId == first.id
    QTest.keyClick(window, Qt.Key_Space)
    assert m.searchQuery == 'guest '
    QTest.keyClick(window, Qt.Key_Backspace)
    assert m.searchQuery == 'guest'
    pan = (pane.property('panX'), pane.property('panY'))
    type_text('zzz')
    assert 'No matches' in indicator.property('text')
    assert m.selectedId == first.id
    assert (pane.property('panX'), pane.property('panY')) == pan
    QTest.keyClick(window, Qt.Key_Escape)
    assert not m.searchQuery and not indicator.property('visible')
    m.cutSelected()
    type_text('guest')
    QTest.keyClick(window, Qt.Key_Escape)
    assert m.canPaste
    QTest.keyClick(window, Qt.Key_Escape)
    assert not m.canPaste
    type_text('guest')
    QTest.keyClick(window, Qt.Key_B, Qt.ControlModifier)
    assert m.map.find(m.selectedId).style.bold and m.searchQuery == 'guest'
    QTest.keyClick(window, Qt.Key_F2)
    QTest.qWait(30)
    assert not m.searchQuery
    type_text('editing')
    assert not m.searchQuery
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(30)
    type_text('guest')
    window.findChild(QObject, 'mindmapActionsButton').forceActiveFocus()
    assert not m.searchQuery
    window.findChild(QObject, 'mindmapActionsButton').setProperty('focus', False)
    pane.forceActiveFocus()
    assert pane.property('shortcutsEnabled')
    type_text('x')
    QTest.keyClick(window, Qt.Key_Backspace)
    assert not m.searchQuery
    m.select(branch.id)
    QTest.keyClick(window, Qt.Key_Space)
    assert branch.folded
    before = len(list(m.map.walk()))
    QTest.keyClick(window, Qt.Key_Return)
    QTest.qWait(30)
    assert len(list(m.map.walk())) == before + 1
    assert window.findChild(QObject, 'mindmapNodeEditor').property('visible')
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(30)
    type_text('guest')
    m.set_scope(next(iter(m.links.values())))
    assert not m.searchQuery and not indicator.property('visible')
    type_text('guest')
    m.load(m.to_dict())
    assert not m.searchQuery and not indicator.property('visible')
    QTest.qWait(30)
    type_text('guest')
    pane.setProperty('visible', False)
    assert not m.searchQuery
    window.close()


def priority_tasks(tabs, values):
    while len(tabs.getAllTabs()) < len(values):
        tabs.addTab('Priority task ' + str(len(tabs.getAllTabs())))
    ids = [tab.id for tab in tabs.getAllTabs()]
    for tab_id, value in zip(ids, values):
        index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == tab_id)
        tabs.setPriorityPoint(index, math.e, value)
    return ids


@pytest.mark.parametrize('values,levels', [
    ([0, 1, 2, 3, 4, 5], [1, 1, 2, 2, 3, 3]),
    ([0, 0, 0, 1, 2, 3], [1, 1, 1, 2, 3, 3]),
    ([1, 1, 1, 1], [2, 2, 2, 2]),
    ([0], [2]),
    ([0, 5], [1, 3]),
])
def test_mindmap_priority_ranks(project, values, levels):
    pm, tabs, _, _ = project
    ids = priority_tasks(tabs, values)
    nodes = {pm.mindmap.links[n['id']]: n for n in pm.mindmap.nodes if n['isTab']}
    assert [nodes[key]['priorityLevel'] for key in ids] == levels
    assert [nodes[key]['priorityScore'] for key in ids] == pytest.approx(values)


@pytest.mark.parametrize('values', [[7], [2, 5], [1, 9, 3, 7, 5], [4, 4, 4, 4]])
def test_mindmap_top_three_badges_follow_priority_order(project, values):
    pm, tabs, _, _ = project
    priority_tasks(tabs, values)

    def ranks():
        return {pm.mindmap.links[n['id']]: n['priorityRank']
                for n in pm.mindmap.nodes if n['isTab']}

    order = [tab.id for tab in tabs.getAllTabs()]
    assert [ranks()[key] for key in order] == [1, 2, 3, 0, 0][:len(order)]
    tabs.setIncludeInPriorityPlot(0, False)
    assert ranks()[order[0]] == 0
    assert [ranks()[key] for key in order[1:]] == [1, 2, 3, 0][:len(order) - 1]


def test_mindmap_priority_scope_exclusion_and_updates(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    ids = priority_tasks(tabs, [0, 3, 6])
    linked = {tab_id: node_id for node_id, tab_id in m.links.items()}
    root = linked[ids[0]]
    m.moveNode(linked[ids[1]], root, 'child')
    m.select(root)
    note = thought(m)
    before = {n['id']: n['priorityLevel'] for n in m.nodes}
    ranks_before = {n['id']: n['priorityRank'] for n in m.nodes}
    assert before[note] == before[m.map.root.id] == 0
    assert ranks_before[note] == ranks_before[m.map.root.id] == 0
    m.set_scope(ids[0])
    assert all(n['priorityLevel'] == before[n['id']] for n in m.nodes)
    assert all(n['priorityRank'] == ranks_before[n['id']] for n in m.nodes)
    m.select(root)
    m.toggleFold()
    assert m.nodes[0]['priorityLevel'] == before[root]
    m.toggleFold()
    saved = m.to_dict()
    notifications = []
    m.sceneChanged.connect(lambda: notifications.append(True))
    index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == ids[0])
    tabs.setPriorityPoint(index, math.e, 9)
    assert notifications
    assert next(n for n in m.nodes if n['id'] == root)['priorityLevel'] == 3
    assert next(n for n in m.nodes if n['id'] == root)['priorityRank'] == 1
    assert tabs.getAllTabs()[0].id == ids[0]
    notifications.clear()
    tabs.setPriorityPoint(0, math.e, 10)  # Same ordering still refreshes the scene.
    assert notifications
    assert next(n for n in m.nodes if n['id'] == root)['priorityScore'] == pytest.approx(10)
    tabs.setIncludeInPriorityPlot(0, False)
    node = next(n for n in m.nodes if n['id'] == root)
    assert node['priorityLevel'] == 0 and node['priorityScore'] is None
    assert node['priorityRank'] == 0
    assert m.to_dict() == saved


def test_qml_plot_and_mindmap_share_score_ranks_after_load_and_moves(project, app):
    pm, tabs, tasks, diagram = project
    priority_tasks(tabs, [1, 9, 5, 3])
    # Saved and manually arranged tab orders need not be sorted by score.
    tabs.setTabs(list(reversed(tabs.getAllTabs())))
    assert tabs.priorityRanks == [4, 3, 2, 1]
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    QMetaObject.invokeMethod(window, 'openPriorityPlotWindow')
    plot = window.property('priorityPlotWindowRef')

    def find(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find(child, name)
            if found is not None:
                return found

    def check_ranks(expected):
        QTest.qWait(30)
        assert tabs.priorityRanks == expected
        nodes = {pm.mindmap.links[n['id']]: n for n in pm.mindmap.nodes if n['isTab']}
        for index, tab in enumerate(tabs.getAllTabs()):
            point = find(plot.contentItem(), 'priorityPlotPoint_' + str(index))
            rank = expected[index]
            assert point.property('priorityRank') == rank
            assert point.property('isTopPriority') == (1 <= rank <= 3)
            assert nodes[tab.id]['priorityRank'] == (rank if 1 <= rank <= 3 else 0)

    try:
        check_ranks([4, 3, 2, 1])
        tabs.moveTab(3, 0)
        check_ranks([1, 4, 3, 2])
        tabs.setIncludeInPriorityPlot(0, False)
        check_ranks([1, 2, 3, 0])
        tabs.setPriorityPoint(2, math.e, 10)
        check_ranks([1, 2, 3, 0])
        tabs.removeTab(0)
        check_ranks([1, 2, 0])
    finally:
        plot.close()
        window.close()


def test_qml_mindmap_priority_rendering(project, app):
    pm, tabs, tasks, diagram = project
    ids = priority_tasks(tabs, [0, 3, 6])
    m = pm.mindmap
    linked = {tab_id: node_id for node_id, tab_id in m.links.items()}
    high = linked[ids[2]]
    m.map.find(high).note = 'Keep this note'
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(message.toString() for message in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)

    def find(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find(child, name)
            if found is not None:
                return found

    try:
        for tab_id, level, color in zip(ids, [1, 2, 3], ['#2b3e4c', '#294f6b', '#246594']):
            node_id = linked[tab_id]
            node = find(window.contentItem(), 'mindmapNode_' + node_id)
            assert node.property('color').name() == color
            bars = find(node, 'mindmapPriority_' + node_id)
            assert bars.isVisible() and bars.property('level') == level
            badge = find(node, 'mindmapPriorityRank_' + node_id)
            assert badge.isVisible() and badge.property('rank') == 4 - level
            assert badge.x() + badge.width() <= bars.x()
            filled = [child for child in bars.childItems()
                      if child.property('color') is not None and child.property('color').alpha() > 0]
            assert len(filled) == level
        m.select(high)
        QTest.qWait(20)
        node = find(window.contentItem(), 'mindmapNode_' + high)
        assert node.property('selected')
        assert QQmlProperty.read(node, 'border.width') == 2
        assert QQmlProperty.read(node, 'border.color').name() == '#a5d9ff'
        tooltip = node.findChild(QObject, 'mindmapTooltip_' + high)
        assert 'Relative priority: Higher · Score: 6.00' in tooltip.property('text')
        assert 'Priority rank: 1' in tooltip.property('text')
        assert m.map.find(high).text in tooltip.property('text')
        assert 'Keep this note' in tooltip.property('text')
        m.toggleCompleted()
        m.cutSelected()
        QTest.qWait(20)
        node = find(window.contentItem(), 'mindmapNode_' + high)
        assert node.opacity() == pytest.approx(0.45)
        assert any(str(child.property('text')).startswith('✓ ') for child in node.childItems())
        index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == ids[2])
        tabs.setIncludeInPriorityPlot(index, False)
        QTest.qWait(20)
        node = find(window.contentItem(), 'mindmapNode_' + high)
        assert node.property('color').name() == '#254d6c'
        assert not find(node, 'mindmapPriority_' + high).isVisible()
        assert not find(node, 'mindmapPriorityRank_' + high).isVisible()
        assert not warnings
    finally:
        window.close()


def test_delete_linked_branch_restores_complete_tabs_and_preserves_survivor(project):
    pm, tabs, tasks, diagram = project
    tabs.addTab('Delete A')
    tabs.addTab('Delete B')
    pm.switchTab(1)
    tasks.addTask('Saved task')
    box = diagram.addBox(10, 20)
    # Materialize the editor's default note tabs before comparing saved content.
    diagram.from_dict(diagram.to_dict())
    deleted = tabs.getCurrentTabData()
    deleted.markdown_tabs = [{'name': 'Notes', 'text': 'Keep this text'}]
    deleted.goals = [{'title': 'A goal'}]
    deleted.icon = 'star'
    deleted.pinned = True
    deleted.kanban_status = 'ready'
    deleted.priority = 3
    pm.showMindmap()
    m = pm.mindmap
    a, b = [next(key for key, value in m.links.items() if value == tab.id)
            for tab in tabs.getAllTabs()[1:]]
    m.select(a)
    child = thought(m, 'Nested note')
    m.toggleCompleted()
    m.moveNode(b, child, 'child')
    m.select(a)
    m.select(b, 'toggle')  # An overlapping selection deletes each tab just once.
    m.cutSelected()
    before_map = m.to_dict()
    expected_tabs = copy.deepcopy(tabs.getAllTabs())
    m.deleteSelected()
    assert [tab.id for tab in tabs.getAllTabs()] == [expected_tabs[0].id]
    assert not m.canPaste and not m.cutNodeIds
    assert pm.mindmapVisible and m.selectedId == m.map.root.id
    assert m.map.find(a) is None and m.map.find(b) is None
    assert tasks.rowCount() == 0
    assert box not in {item['id'] for item in diagram.to_dict()['items']}
    tasks.addTask('Unrelated later edit')
    m.undo()
    assert m.to_dict() == before_map
    assert [tab.id for tab in tabs.getAllTabs()] == [tab.id for tab in expected_tabs]
    assert tabs.getAllTabs()[1:] == expected_tabs[1:]
    assert tabs.getAllTabs()[0].tasks['tasks'][0]['title'] == 'Unrelated later edit'
    assert tabs.getCurrentTabData().id == deleted.id
    assert tasks.to_dict()['tasks'][0]['title'] == 'Saved task'
    assert box in {item['id'] for item in diagram.to_dict()['items']}
    m.redo()
    assert tabs.tabCount == 1
    assert tasks.to_dict()['tasks'][0]['title'] == 'Unrelated later edit'
    m.undo()
    assert tabs.getAllTabs()[1:] == expected_tabs[1:]


def test_linked_deletion_last_tab_and_redo_are_atomic(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    tabs.addTab('Survivor')
    first = next(iter(m.links))
    m.select(first)
    m.deleteSelected()
    m.undo()
    tabs.removeTab(1)  # Redo would now delete the last remaining tab.
    before = m.to_dict()
    errors = []
    m.errorOccurred.connect(errors.append)
    m.redo()
    assert errors and 'at least one tab' in errors[-1]
    assert m.to_dict() == before and tabs.tabCount == 1 and m.canRedo
    m.select(first)
    m.deleteSelected()
    assert m.to_dict() == before and tabs.tabCount == 1


def test_linked_deletion_persists_and_load_clears_tab_history(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='mindmap-delete-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    tabs.addTab('Removed tab')
    removed_id = tabs.getAllTabs()[1].id
    m = pm.mindmap
    node_id = next(key for key, value in m.links.items() if value == removed_id)
    m.select(node_id)
    m.deleteSelected()
    path = tmp_path / 'deleted.progress'
    assert pm.saveProject(str(path))
    payload = decrypt_project_data(json.loads(path.read_text()), credentials)
    assert removed_id not in {tab['id'] for tab in payload['tabs']}
    assert node_id not in payload['mindmap']['tab_links']
    pm.loadProject(str(path))
    assert tabs.tabCount == 1 and m.map.find(node_id) is None
    assert not m.canUndo and not m.canRedo


def test_redo_removing_current_scope_returns_to_project_map(project):
    pm, tabs, _, _ = project
    tabs.addTab('Keep')
    m = pm.mindmap
    first = next(iter(m.links))
    m.select(first)
    m.deleteSelected()
    m.undo()
    pm.showTabMindmap()
    assert m.tabScoped
    m.redo()
    assert not m.tabScoped and pm.mindmapVisible
    assert m.view_root is m.map.root and m.selectedId == m.map.root.id


def test_qml_linked_delete_updates_sidebar_and_boards(project, app):
    pm, tabs, tasks, diagram = project
    name = 'Tab removed from every view'
    tabs.addTab(name)
    tab_id = tabs.getAllTabs()[1].id
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    QMetaObject.invokeMethod(window, 'openPriorityPlotWindow')
    QMetaObject.invokeMethod(window, 'openKanbanWindow')
    plot = window.property('priorityPlotWindowRef')
    board = window.property('kanbanWindowRef')
    pm.showMindmap()

    def contains(item, property_name):
        return (item.property(property_name) == name
                or any(contains(child, property_name) for child in item.childItems()))

    try:
        QTest.qWait(100)
        assert contains(window.contentItem(), 'dragTabName')
        assert contains(plot.contentItem(), 'text')
        assert contains(board.contentItem(), 'text')
        node_id = next(key for key, value in pm.mindmap.links.items() if value == tab_id)
        pm.mindmap.select(node_id)
        pm.mindmap.deleteSelected()
        QTest.qWait(100)
        assert not contains(window.contentItem(), 'dragTabName')
        assert not contains(plot.contentItem(), 'text')
        assert not contains(board.contentItem(), 'text')
        pm.mindmap.undo()
        QTest.qWait(100)
        assert contains(window.contentItem(), 'dragTabName')
        assert contains(plot.contentItem(), 'text')
        assert contains(board.contentItem(), 'text')
    finally:
        plot.close()
        board.close()
        plot.deleteLater()
        board.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        window.close()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


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


@pytest.mark.parametrize('tab_scoped', [False, True])
def test_qml_ctrl_left_right_moves_branch(project, app, tab_scoped):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    if tab_scoped:
        pm.showTabMindmap()
    else:
        pm.showMindmap()
    QTest.qWait(150)
    m.select(m.view_root.id)
    branch_id = thought(m, 'Moving branch')
    child_id = thought(m, 'Descendant')
    m.select(branch_id)
    QTest.qWait(150)
    window.findChild(QObject, 'mindmapPane').forceActiveFocus()
    revealed = []
    m.revealNode.connect(revealed.append)

    try:
        for key, side in ((Qt.Key_Left, 'left'), (Qt.Key_Right, 'right')):
            before = m.to_dict()
            QTest.keyClick(window, key, Qt.ControlModifier)
            branch = m.map.find(branch_id)
            child = m.map.find(child_id)
            assert branch.side == side
            assert branch.parent is m.view_root and child.parent is branch
            assert m.selectedIds == [branch_id]
            assert revealed[-1] == branch_id
            boxes = m._layout()
            assert (boxes[child].x < boxes[branch].x) == (side == 'left')
            after = m.to_dict()
            decoded, _ = m.decode(after)
            assert decoded.find(branch_id).side == side
            QTest.keyClick(window, Qt.Key_Z, Qt.ControlModifier)
            assert m.to_dict() == before and m.selectedId == branch_id
            QTest.keyClick(window, Qt.Key_Y, Qt.ControlModifier)
            assert m.to_dict() == after and m.selectedId == branch_id

        before = m.to_dict()
        QTest.keyClick(window, Qt.Key_Right)
        assert m.selectedId == child_id
        QTest.keyClick(window, Qt.Key_Left)
        assert m.selectedId == branch_id and m.to_dict() == before

        for node_id in (m.view_root.id, child_id):
            m.select(node_id)
            history_size = len(m._undo)
            for key in (Qt.Key_Left, Qt.Key_Right):
                QTest.keyClick(window, key, Qt.ControlModifier)
                assert m.to_dict() == before and len(m._undo) == history_size

        m.select(branch_id)
        QTest.keyClick(window, Qt.Key_F2)
        QTest.qWait(30)
        assert window.findChild(QObject, 'mindmapNodeEditor').property('visible')
        for key in (Qt.Key_Left, Qt.Key_Right):
            QTest.keyClick(window, key, Qt.ControlModifier)
            assert m.to_dict() == before
        QTest.keyClick(window, Qt.Key_Escape)
    finally:
        window.close()


def test_bookmark_history_and_navigation(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    root = m.map.root.id
    tab = next(iter(m.links))
    m.select(tab)
    child = thought(m, 'Child')
    m.toggleBookmark(child)
    m.toggleBookmark(root)
    assert [b['id'] for b in m.bookmarks] == [child, root]
    m.editSelected('Renamed', '')
    assert m.bookmarks[0]['path'].endswith('/ Renamed')
    m.moveNode(child, root, 'child')
    assert m.bookmarks[0]['path'] == 'Project / Renamed'
    m.toggleBookmark(child)
    assert [b['id'] for b in m.bookmarks] == [root]
    m.undo()
    assert [b['id'] for b in m.bookmarks] == [child, root]
    m.select(child)
    m.deleteSelected()
    assert [b['id'] for b in m.bookmarks] == [root]
    m.undo()
    assert [b['id'] for b in m.bookmarks] == [child, root]
    m.redo()
    assert [b['id'] for b in m.bookmarks] == [root]
    m.undo()
    pm.showTabMindmap()
    history = len(m._undo)
    m.jumpToBookmark(child)
    assert not m.tabScoped and m.selectedIds == [child]
    assert len(m._undo) == history
    m.toggleBookmark(tab)
    pm.showTabMindmap()
    m.jumpToBookmark(tab)
    assert m.tabScoped and m.selectedId == tab
    payload = m.to_dict()
    restored = MindMapController()
    restored.load(payload)
    assert restored.bookmarks == m.bookmarks
    payload.pop('bookmarks')
    restored.load(payload)
    assert restored.bookmarks == []
    m.load()
    assert m.bookmarks == []


@pytest.mark.parametrize('value', [None, {}, 'node', [42], [[]], ['missing'], 'duplicate'])
def test_bookmark_payload_validation(project, value):
    m = project[0].mindmap
    payload = m.to_dict()
    payload['bookmarks'] = [m.map.root.id] * 2 if value == 'duplicate' else value
    with pytest.raises(ValueError, match='bookmarks'):
        m.decode(payload)


def test_qml_bookmarks(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    tab = next(iter(m.links))
    m.select(tab)
    child = thought(m, 'Bookmarked child')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(x.toString() for x in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')

    def find_item(item, name):
        if item.objectName() == name:
            return item
        for nested in item.childItems():
            found = find_item(nested, name)
            if found is not None:
                return found

    def click(item):
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                         item.mapToScene(item.boundingRect().center()).toPoint())
        QTest.qWait(50)

    try:
        row = window.findChild(QObject, 'mindmapBookmarks')
        assert not row.property('visible')
        m.select(child)
        click(window.findChild(QObject, 'mindmapActionsButton'))
        click(window.findChild(QObject, 'mindmapBookmark'))
        assert m.selectedNode['bookmarked'] and row.property('visible')
        icon = find_item(window.contentItem(), 'mindmapBookmarkIcon_' + child)
        assert icon.isVisible() and icon.property('text') == '\U0001f516'
        click(window.findChild(QObject, 'mindmapActionsButton'))
        click(window.findChild(QObject, 'mindmapBookmark'))
        assert not m.bookmarks and not row.property('visible')
        assert not find_item(window.contentItem(), 'mindmapBookmarkIcon_' + child).isVisible()
        click(window.findChild(QObject, 'mindmapActionsButton'))
        click(window.findChild(QObject, 'mindmapBookmark'))
        assert find_item(window.contentItem(), 'mindmapBookmarkIcon_' + child).isVisible()
        m.select(tab)
        m.toggleFold()
        history = len(m._undo)
        click(find_item(window.contentItem(), 'mindmapBookmark_' + child))
        assert not m.map.find(tab).folded and m.selectedIds == [child]
        assert len(m._undo) == history and pane.hasActiveFocus()
        # Context action targets the clicked node even with another primary selection.
        m.select(tab, 'toggle')
        m.select(child, 'add')
        assert m.selectedId == child
        menu = window.findChild(QObject, 'mindmapNodeMenu')
        menu.setProperty('targetNodeId', tab)
        QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapBookmarkMenuItem'), 'triggered')
        assert [b['id'] for b in m.bookmarks] == [child, tab]
        m.toggleBookmark(m.map.root.id)
        pm.showTabMindmap()
        QTest.qWait(50)
        pane.setProperty('zoom', 0.7)
        click(find_item(window.contentItem(), 'mindmapBookmark_' + m.map.root.id))
        assert not m.tabScoped and m.selectedId == m.map.root.id
        assert pane.property('zoom') == pytest.approx(0.7)
        item = find_item(window.contentItem(), 'mindmapNode_' + m.selectedId)
        viewport = window.findChild(QObject, 'mindmapViewport')
        point = item.mapToItem(viewport, item.boundingRect().center())
        assert point.x() == pytest.approx(viewport.width() / 2)
        assert point.y() == pytest.approx(viewport.height() / 2)
        highlight = find_item(window.contentItem(), 'mindmapBookmarkHighlight_' + m.selectedId)
        assert highlight.isVisible() and highlight.opacity() == 1
        assert QQmlProperty.read(highlight, 'border.width') * pane.property('zoom') == pytest.approx(3)
        click(find_item(window.contentItem(), 'mindmapBookmark_' + tab))
        assert not m.tabScoped and m.selectedId == tab
        assert not highlight.isVisible()
        highlight = find_item(window.contentItem(), 'mindmapBookmarkHighlight_' + tab)
        assert highlight.isVisible()
        before = m.to_dict()
        QTest.qWait(2600)
        assert not highlight.isVisible()
        click(find_item(window.contentItem(), 'mindmapBookmark_' + tab))
        assert highlight.isVisible() and highlight.opacity() == 1
        assert m.to_dict() == before
        for i in range(12):
            m.select(m.map.root.id)
            node_id = thought(m, 'A long bookmark title ' + str(i))
            m.toggleBookmark(node_id)
        QTest.qWait(50)
        assert row.property('contentWidth') > row.width()
        assert not warnings, warnings
    finally:
        window.close()


def test_encrypted_roundtrip_dirty_and_scrub(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='mindmap-test-passphrase')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    tab_root = next(iter(pm.mindmap.links))
    pm.mindmap.select(tab_root)
    node_id = thought(pm.mindmap)
    pm.mindmap.toggleBookmark(node_id)
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
    assert payload['mindmap']['bookmarks'] == [node_id]
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
    assert pm.mindmap.bookmarks == []
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
    assert pm.mindmapVisible and m.selectedId == node_id
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, center(node_id))
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
    # Ctrl+click selects a tab for adding thoughts; double-click opens the tab.
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
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapActionsMenu'), 'open')
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapTabsMenu'), 'open')
    QTest.qWait(30)
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
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapActionsMenu'), 'open')
    QTest.qWait(30)
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


def reminder_date(minutes=60):
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M')


@pytest.mark.parametrize('node_kind', ['root', 'tab', 'thought'])
def test_node_reminder_crud_and_completion(project, node_kind):
    pm, _, tasks, _ = project
    m = pm.mindmap
    node_id = (m.map.root.id if node_kind == 'root' else
               next(iter(m.links)) if node_kind == 'tab' else thought(m))
    date = reminder_date()
    assert pm.setMindmapReminder(node_id, date, True)
    m.select(node_id)
    assert m.selectedNode['reminderAt'] == date
    assert m.selectedNode['reminderSendNotification']
    entries = pm.getActiveReminders()
    assert [(entry['kind'], entry['nodeId']) for entry in entries] == [('mindmap', node_id)]
    assert entries[0]['sendNotification']
    assert tasks.to_dict()['tasks'] == []
    assert not pm.setMindmapReminder(node_id, 'invalid', False)
    assert not pm.setMindmapReminder('missing-node', date, False)
    assert m.reminderData(node_id)['reminderAt'] == date
    updated = reminder_date(120)
    assert pm.setMindmapReminder(node_id, updated, False)
    assert m.reminderData(node_id)['reminderAt'] == updated
    m.toggleCompleted()
    assert not m.reminders and not pm.getActiveReminders()
    m.undo()
    assert m.reminderData(node_id)['reminderAt'] == updated
    m.redo()
    assert not m.reminders
    m.undo()
    pm.clearMindmapReminder(node_id)
    assert not m.reminders
    m.undo()
    assert m.reminderData(node_id)['reminderAt'] == updated


def test_node_reminders_persist_and_older_projects_load(project, tmp_path, monkeypatch):
    pm, _, _, _ = project
    m = pm.mindmap
    node_id = thought(m)
    date = reminder_date()
    assert pm.setMindmapReminder(node_id, date, True)
    credentials = EncryptionCredentials(passphrase='node-reminder-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'reminders.progress'
    assert pm.saveProject(str(path))
    pm.clearMindmapReminder(node_id)
    pm.loadProject(str(path))
    assert m.reminderData(node_id)['reminderAt'] == date
    assert m.reminderData(node_id)['reminderSendNotification']
    old_payload = m.to_dict()
    old_payload.pop('reminders')
    m.load(old_payload)
    assert not m.reminders


@pytest.mark.parametrize('value', [None, [], {'at': 'tomorrow', 'send_notification': False},
                                  {'at': float('nan'), 'send_notification': False},
                                  {'at': float('inf'), 'send_notification': False},
                                  {'at': 10**20, 'send_notification': False},
                                  {'at': 10**1000, 'send_notification': False},
                                  {'at': 123, 'send_notification': 'yes'}])
def test_node_reminder_payload_validation(project, value):
    m = project[0].mindmap
    payload = m.to_dict()
    payload['reminders'] = {m.map.root.id: value}
    with pytest.raises(ValueError, match='reminder'):
        m.decode(payload)
    payload['reminders'] = {'missing': {'at': 123, 'send_notification': False}}
    with pytest.raises(ValueError, match='reminder'):
        m.decode(payload)


def test_node_reminders_survive_move_conversion_and_delete_undo(project):
    pm, _, _, _ = project
    m = pm.mindmap
    parent = thought(m, 'Parent')
    child = thought(m, 'Child')
    assert pm.setMindmapReminder(child, reminder_date(), True)
    expected = copy.deepcopy(m.reminders)
    m.editSelected('Renamed', '')
    m.moveNode(child, m.map.root.id, 'child')
    assert m.reminders == expected
    m.select(child)
    m.createTabFromSelected()
    assert child in m.links and m.reminders == expected
    m.deleteSelected()
    assert child not in m.reminders
    m.undo()
    assert m.reminders == expected
    m.redo()
    assert child not in m.reminders
    assert m.map.find(parent) is not None


@pytest.mark.parametrize('send_notification', [False, True])
def test_node_reminder_due_once_across_history_and_renewal(project, monkeypatch, send_notification):
    pm, _, _, _ = project
    m = pm.mindmap
    node_id = thought(m, 'Call someone')
    due, published, saved = [], [], []
    pm.mindmapReminderDue.connect(lambda *args: due.append(args))
    monkeypatch.setattr(pm, '_publishReminderNotification', lambda *args, **kwargs: published.append((args, kwargs)))
    monkeypatch.setattr(pm, '_save_after_reminder', lambda: saved.append(True))
    assert pm.setMindmapReminder(node_id, reminder_date(-1), send_notification)
    m.editSelected('Current title', '')
    m.editSelected('Another title', '')
    m.undo()  # Both history stacks contain the schedule at delivery.
    pm.showTabCanvas()
    pm._processReminderTimers()
    assert due == [(node_id, 'Current title', send_notification)]
    assert len(published) == int(send_notification)
    if published:
        assert published[0] == ((0, 'Current title'), {'scope_label': 'Mindmap'})
    assert saved == [True]
    assert not m.reminders
    m.redo()
    pm._processReminderTimers()
    while m.canUndo:
        m.undo()
        pm._processReminderTimers()
    while m.canRedo:
        m.redo()
        pm._processReminderTimers()
    assert len(due) == 1
    assert pm.setMindmapReminder(node_id, reminder_date(60), send_notification)
    assert len(pm.getActiveReminders()) == 1


def test_open_node_reminder_unfolds_and_leaves_unrelated_scope(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    branch = thought(m, 'Branch')
    node_id = thought(m, 'Deep node')
    m.map.find(branch).folded = True
    m.map.root.folded = True
    m.set_scope(tabs.getAllTabs()[0].id)
    pm.showTabCanvas()
    pm.openMindmapReminder(node_id)
    assert pm.mindmapVisible and not m.tabScoped
    assert m.selectedId == node_id
    assert node_id in {node['id'] for node in m.nodes}
    assert not m.map.find(branch).folded and not m.map.root.folded


def test_qml_node_reminder_controls_and_overview(project, app, tmp_path):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    node_id = thought(m, 'Remember this thought')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(message.toString() for message in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)

    def find(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = find(child, name)
            if found is not None:
                return found

    def click(item):
        point = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.qWait(40)

    try:
        overview = find(window.contentItem(), 'reminderOverview')
        assert overview.isVisible()
        click(window.findChild(QObject, 'mindmapActionsButton'))
        button = window.findChild(QObject, 'mindmapReminder')
        click(button)
        dialog = window.findChild(QObject, 'reminderDialog')
        assert dialog.property('visible') and dialog.property('nodeId') == node_id
        date, clock = reminder_date().split(' ')
        dialog.setProperty('dateValue', date)
        dialog.setProperty('timeValue', clock)
        QMetaObject.invokeMethod(dialog, 'accept')
        QTest.qWait(80)
        assert m.reminderData(node_id)['reminderAt'] == date + ' ' + clock
        badge = find(window.contentItem(), 'mindmapReminderBadge_' + node_id)
        assert badge.isVisible()
        click(badge)
        menu = window.findChild(QObject, 'mindmapNodeMenu')
        assert menu.property('visible')
        update = window.findChild(QObject, 'mindmapSetReminder')
        assert update.property('text') == 'Update Reminder'
        QMetaObject.invokeMethod(menu, 'close')
        QTest.qWait(30)
        pm.showTabCanvas()
        QTest.qWait(40)
        assert overview.isVisible()
        click(find(window.contentItem(), 'openReminder_' + node_id))
        assert pm.mindmapVisible and m.selectedId == node_id
        click(find(window.contentItem(), 'editReminder_' + node_id))
        assert dialog.property('nodeId') == node_id
        assert dialog.property('dateValue') == date
        QMetaObject.invokeMethod(dialog, 'reject')
        QTest.qWait(40)
        # Narrow layouts and multiple zoom factors keep the badge inside its node.
        pane = window.findChild(QObject, 'mindmapPane')
        for width, zoom in [(800, 0.7), (800, 1.4), (1280, 1.0)]:
            window.setWidth(width)
            window.setHeight(800)
            QMetaObject.invokeMethod(pane, 'fitMap')
            pane.setProperty('zoom', zoom)
            pm.openMindmapReminder(node_id)
            QTest.qWait(80)
            badge = find(window.contentItem(), 'mindmapReminderBadge_' + node_id)
            node = find(window.contentItem(), 'mindmapNode_' + node_id)
            assert badge.x() >= 0 and badge.x() + badge.width() <= node.width()
            assert badge.y() >= 36 and badge.y() + badge.height() <= node.height()
            assert overview.height() < window.height() / 2
            window.grabWindow().save(str(tmp_path / f"mindmap-reminders-{width}-{zoom}.png"))
        window.grabWindow().save(str(tmp_path / 'mindmap-reminders.png'))
        click(find(window.contentItem(), 'clearReminder_' + node_id))
        assert not m.reminders
        m.select(next(iter(m.links)), 'toggle')
        QTest.qWait(30)
        assert not button.isEnabled()
        assert not warnings
    finally:
        window.close()


def test_qml_due_reminder_renewal_keeps_target_with_queued_alerts(project, app, monkeypatch):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    first = thought(m, 'First reminder')
    second = thought(m, 'Second reminder')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(message.toString() for message in messages))
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(100)
    monkeypatch.setattr(pm, '_save_after_reminder', lambda: None)
    try:
        pm.setMindmapReminder(first, reminder_date(-1), False)
        pm.setMindmapReminder(second, reminder_date(-1), False)
        pm._processReminderTimers()
        QTest.qWait(50)
        popup = window.findChild(QObject, 'reminderDuePopup')
        assert popup.property('visible')
        assert window.property('pendingReminderNodeId') == first
        renew = window.findChild(QObject, 'renewDueReminder')
        QMetaObject.invokeMethod(renew, 'clicked')
        QTest.qWait(50)
        dialog = window.findChild(QObject, 'reminderDialog')
        assert dialog.property('visible') and dialog.property('nodeId') == first
        assert not popup.property('visible')
        date, clock = reminder_date(120).split(' ')
        dialog.setProperty('dateValue', date)
        dialog.setProperty('timeValue', clock)
        QMetaObject.invokeMethod(dialog, 'accept')
        QTest.qWait(50)
        assert m.reminderData(first)['reminderAt'] == date + ' ' + clock
        assert second not in m.reminders
        assert popup.property('visible')
        assert window.property('pendingReminderNodeId') == second
        QMetaObject.invokeMethod(popup, 'close')
        QTest.qWait(30)
        assert not warnings
    finally:
        window.close()


@pytest.mark.parametrize('side', ['left', 'right'])
def test_add_thought_at_gap_history_and_sides(app, side):
    from actiondraw._vendor.pyplane.layout import assigned_sides
    m = MindMapController()
    a = m.map.root.add_child('A', side=side)
    other = m.map.root.add_child('Other', side='right' if side == 'left' else 'left')
    b = m.map.root.add_child('B', side=side)
    m.map.root.add_child('Automatic')
    m.select(other.id)
    before = m.to_dict()
    before_sides = {n.id: s for n, s in assigned_sides(m.map).items()}
    boxes = m._layout()
    x = boxes[a].x + boxes[a].width / 2
    y = (boxes[a].y + boxes[a].height + boxes[b].y) / 2
    assert m.addThoughtAt(x, y)
    created = m.map.find(m.selectedId)
    assert m.map.root.children == [a, other, created, b, m.map.root.children[-1]]
    assert created.side == side
    assert all(assigned_sides(m.map)[m.map.find(key)] == value for key, value in before_sides.items())
    assert len(m._undo) == 1
    after = m.to_dict()
    m.undo()
    assert m.to_dict() == before and m.selectedId == other.id
    m.redo()
    assert m.to_dict() == after and m.selectedIds == [created.id]
    m.load(after)
    assert m.to_dict() == after


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('placement', ['above', 'below', 'child', 'folded'])
def test_add_thought_at_nearest(app, side, placement):
    m = MindMapController()
    parent = m.map.root.add_child('Parent', side=side)
    a, b = [parent.add_child(t) for t in ('A', 'B')]
    if placement == 'folded':
        parent.folded = True
        target = parent
    else:
        target = a if placement == 'above' else b
    box = m._layout()[target]
    if placement in ('child', 'folded'):
        x = box.x - 30 if side == 'left' else box.x + box.width + 30
        y = box.center_y
    else:
        x = box.x + box.width / 2
        y = box.y - 15 if placement == 'above' else box.y + box.height + 15
    assert m.addThoughtAt(x, y)
    node = m.map.find(m.selectedId)
    assert node.parent is (target if placement in ('child', 'folded') else parent)
    assert not node.parent.folded
    if placement == 'above':
        assert parent.children == [node, a, b]
    elif placement == 'below':
        assert parent.children == [a, b, node]
    elif placement == 'folded':
        assert parent.children == [a, b, node]


@pytest.mark.parametrize('x,side', [(-10000, 'left'), (10000, 'right')])
def test_add_thought_at_root_and_invalid_points(app, x, side):
    m = MindMapController()
    before = m.to_dict()
    assert not m.addThoughtAt(0, 0)
    assert not m.addThoughtAt(float('nan'), 0)
    assert not m.addThoughtAt(0, float('inf'))
    assert m.to_dict() == before and not m.canUndo
    assert m.addThoughtAt(x, 0)
    node = m.map.find(m.selectedId)
    assert node.parent is m.map.root and node.side == side


def test_add_thought_at_scope_and_tie(project):
    m = project[0].mindmap
    tab = m.map.find(next(iter(m.links)))
    outside = m.map.root.add_child('Outside')
    m.set_scope(m.links[tab.id])
    a, b = [tab.add_child(t, side='right') for t in ('A', 'B')]
    boxes = m._layout()
    # Just beyond both outer edges: equal distance chooses A in visible order.
    assert m.addThoughtAt(boxes[a].x + boxes[a].width + 20,
                          (boxes[a].y + boxes[a].height + boxes[b].y) / 2)
    assert m.map.find(m.selectedId).parent is a
    assert outside.children == [] and tab.parent is m.map.root


@pytest.mark.parametrize('zoom,pan', [(1.0, 0), (0.55, 35)])
def test_qml_double_click_empty_canvas(project, app, zoom, pan):
    from PySide6.QtCore import QPointF
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    parent = m.map.find(next(iter(m.links)))
    a, b = [parent.add_child(t) for t in ('A', 'B')]
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    viewport = window.findChild(QObject, 'mindmapViewport')
    editor = window.findChild(QObject, 'mindmapNodeEditor')
    box = m._layout()[a]
    pane.setProperty('zoom', zoom)
    pane.setProperty('panX', pan - (box.x + box.width / 2) * zoom)
    pane.setProperty('panY', pan)
    QTest.qWait(30)

    def point(x, y):
        return viewport.mapToScene(QPointF(viewport.width() / 2 + pane.property('panX') + x * zoom,
                                          viewport.height() / 2 + pane.property('panY') + y * zoom)).toPoint()

    boxes = m._layout()
    gap = point(box.x + box.width / 2, (box.y + box.height + boxes[b].y) / 2)
    count = len(list(m.map.walk()))
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, gap)
    QTest.qWait(50)
    created = m.map.find(m.selectedId)
    assert len(list(m.map.walk())) == count + 1
    assert parent.children == [a, created, b]
    assert editor.property('visible')
    assert window.findChild(QObject, 'mindmapNodeTitle').property('text') == 'New thought'
    QMetaObject.invokeMethod(editor, 'reject')
    QTest.qWait(50)
    assert len(list(m.map.walk())) == count + 1
    box = m._layout()[created]
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, point(box.x + box.width / 2, box.center_y))
    QTest.qWait(50)
    assert editor.property('visible') and len(list(m.map.walk())) == count + 1
    QMetaObject.invokeMethod(editor, 'reject')
    QTest.qWait(50)
    start = viewport.mapToScene(QPointF(30, 30)).toPoint()
    previous_pan = pane.property('panX')
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, start + QPoint(30, 10), 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, start + QPoint(30, 10))
    assert pane.property('panX') != previous_pan
    assert len(list(m.map.walk())) == count + 1 and not editor.property('visible')
    QTest.mouseDClick(window, Qt.LeftButton, Qt.ControlModifier, start)
    assert len(list(m.map.walk())) == count + 1
    window.close()


def test_bold_selection_history_and_persistence(project):
    m = project[0].mindmap
    tab = m.map.find(next(iter(m.links)))
    child = tab.add_child('Medium length thought')
    untouched = tab.add_child('Untouched')
    m.select(tab.id)
    m.select(child.id, 'add')
    child.style.bold = True
    before = m.to_dict()
    m.toggleBold()
    assert tab.style.bold and child.style.bold and not untouched.style.bold
    assert all(n['bold'] for n in m.nodes if n['id'] in m.selectedIds)
    assert project[0].hasUnsavedChanges()
    assert len(m._undo) == 1
    after = m.to_dict()
    m.undo()
    assert m.to_dict() == before
    m.redo()
    assert m.to_dict() == after
    m.load(after)
    assert m.to_dict() == after
    m.select(tab.id)
    m.select(child.id, 'add')
    m.toggleBold()
    assert not m.map.find(tab.id).style.bold
    assert not m.map.find(child.id).style.bold


def test_qml_ctrl_b_toggles_node_font_and_respects_editor(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    node = m.map.root.add_child('Medium length thought')
    normal_width = m._layout()[node].width
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    m.select(node.id)

    def label(item):
        if item.objectName() == 'mindmapNodeText_' + node.id:
            return item
        for child in item.childItems():
            found = label(child)
            if found is not None:
                return found
        return None

    QTest.keyClick(window, Qt.Key_B, Qt.ControlModifier)
    QTest.qWait(30)
    assert node.style.bold
    assert label(window.contentItem()).property('font').bold()
    assert m._layout()[node].width > normal_width
    QTest.keyClick(window, Qt.Key_B, Qt.ControlModifier)
    QTest.qWait(30)
    assert not node.style.bold
    assert not label(window.contentItem()).property('font').bold()
    QTest.keyClick(window, Qt.Key_F2)
    QTest.qWait(30)
    before = m.to_dict()
    QTest.keyClick(window, Qt.Key_B, Qt.ControlModifier)
    assert m.to_dict() == before
    QTest.keyClick(window, Qt.Key_Escape)
    window.close()


def test_mindmap_compact_menu_keyboard_and_help(project, app):
    pm, tabs, tasks, diagram = project
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    toolbar = window.findChild(QObject, 'mindmapToolbar')
    viewport = window.findChild(QObject, 'mindmapViewport')
    button = window.findChild(QObject, 'mindmapActionsButton')
    menu = window.findChild(QObject, 'mindmapActionsMenu')
    help_dialog = window.findChild(QObject, 'mindmapHelpDialog')
    assert toolbar.height() < 60
    assert viewport.height() > pane.height() - 90
    button.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    QTest.qWait(40)
    assert menu.property('visible')
    assert not pane.property('shortcutsEnabled')
    QTest.keyClick(window, Qt.Key_Down)
    assert menu.property('currentIndex') >= 0
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(40)
    assert not menu.property('visible') and pane.hasActiveFocus()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     button.mapToScene(button.boundingRect().center()).toPoint())
    QTest.qWait(40)
    help_item = window.findChild(QObject, 'mindmapHelpAction')
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     help_item.mapToScene(help_item.boundingRect().center()).toPoint())
    QTest.qWait(40)
    assert help_dialog.property('visible') and not menu.property('visible')
    assert not pane.property('shortcutsEnabled')
    QTest.keyClick(window, Qt.Key_Escape)
    QTest.qWait(40)
    assert not help_dialog.property('visible') and pane.hasActiveFocus()
    window.close()


@pytest.mark.parametrize('side', ['left', 'right'])
@pytest.mark.parametrize('target_index,before', [(0, True), (1, True), (1, False)])
def test_add_sibling_relative_order_side_history(project, side, target_index, before):
    from actiondraw._vendor.pyplane.layout import assigned_sides
    m = project[0].mindmap
    parent = m.map.root
    a = parent.add_child('A', side=side)
    b = parent.add_child('B', side=side)
    target = [a, b][target_index]
    old_ids = [n.id for n in parent.children]
    old_sides = {n.id: s for n, s in assigned_sides(m.map).items()}
    original = m.to_dict()
    m.searchText('A')
    assert m.addSiblingRelative(target.id, before)
    new = m.map.find(m.selectedId)
    expected = old_ids[:]
    expected.insert(old_ids.index(target.id) + (0 if before else 1), new.id)
    assert [n.id for n in parent.children] == expected
    sides = {n.id: s for n, s in assigned_sides(m.map).items()}
    assert sides[new.id] == side
    assert all(sides[key] == value for key, value in old_sides.items())
    assert new.text == 'New thought' and not m.searchQuery
    after = m.to_dict()
    m.undo()
    assert m.to_dict() == original
    m.redo()
    assert m.to_dict() == after and m.selectedId == new.id


def test_add_sibling_relative_scope_validation(project):
    m = project[0].mindmap
    root_id, tab_id = next(iter(m.links.items()))
    root = m.map.find(root_id)
    child = root.add_child('Child')
    outside = m.map.root.add_child('Outside')
    m.set_scope(tab_id)
    original = m.to_dict()
    for node_id in [root_id, outside.id, m.map.root.id, 'missing']:
        assert not m.addSiblingRelative(node_id, True)
        assert m.to_dict() == original
    assert m.addSiblingRelative(child.id, False)
    assert root.children[-1].id == m.selectedId
    assert root.children[0] is child


@pytest.mark.parametrize('zoom,before', [(0.6, True), (1.5, False)])
def test_qml_sibling_insertion_controls(project, app, zoom, before):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    a = m.map.root.add_child('Alpha', side='right')
    b = m.map.root.add_child('Beta', side='right')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    viewport = window.findChild(QObject, 'mindmapViewport')
    def visual_item(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            found = visual_item(child, name)
            if found is not None:
                return found
        return None

    above = visual_item(window.contentItem(), 'mindmapAddAbove')
    below = visual_item(window.contentItem(), 'mindmapAddBelow')
    assert not above.property('visible')
    m.select(a.id)
    pane.setProperty('zoom', zoom)
    pane.setProperty('panX', -140)
    pane.setProperty('panY', 50)
    QTest.qWait(30)
    assert above.property('visible') and below.property('visible')
    assert above.width() == 24 and above.height() == 24
    pane.setProperty('zoom', 0.2)
    assert below.y() >= above.y() + above.height()
    pane.setProperty('zoom', zoom)
    # Hover the other node, then move onto its insertion button.
    box = m._layout()[b]
    from PySide6.QtCore import QPointF
    center = viewport.mapToScene(QPointF(viewport.width() / 2 - 140 + (box.x + box.width / 2) * zoom,
                                         viewport.height() / 2 + 50 + box.center_y * zoom)).toPoint()
    QTest.mouseMove(window, center)
    QTest.qWait(30)
    assert pane.property('hoveredNodeId') == b.id
    button = above if before else below
    expected_y = (viewport.height() / 2 + 50 + box.center_y * zoom
                  + (-1 if before else 1) * max(box.height * zoom / 2, 14))
    assert button.y() + button.height() / 2 == pytest.approx(expected_y)
    point = button.mapToScene(button.boundingRect().center()).toPoint()
    QTest.mouseMove(window, point)
    QTest.qWait(180)
    assert pane.property('hoveredNodeId') == b.id and button.property('visible')
    original_ids = [n.id for n in m.map.root.children]
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(40)
    new = m.map.find(m.selectedId)
    expected = original_ids[:]
    expected.insert(original_ids.index(b.id) + (0 if before else 1), new.id)
    assert [n.id for n in m.map.root.children] == expected
    assert new.text == 'New thought'
    editor = window.findChild(QObject, 'mindmapNodeEditor')
    assert editor.property('visible') and not above.property('visible')
    assert pane.property('panX') == -140 and pane.property('panY') == 50
    QMetaObject.invokeMethod(editor, 'reject')
    QTest.qWait(40)
    assert m.map.find(new.id) is new
    m.select(m.view_root.id)
    QTest.mouseMove(window, QPoint(5, 5))
    QTest.qWait(180)
    assert not above.property('visible')
    window.close()


def filter_tabs(project, scores):
    m, tabs = project[0].mindmap, project[1]
    while len(tabs.getAllTabs()) < len(scores):
        tabs.addTab('Priority ' + str(len(tabs.getAllTabs())))
    for tab, score in zip(tabs.getAllTabs(), scores):
        tab.priority_score = score
    m.reconcile()
    return [m.map.find(next(key for key, value in m.links.items() if value == tab.id))
            for tab in tabs.getAllTabs()]


def test_priority_filter_cutoffs_ties_and_persistence(project):
    m = project[0].mindmap
    low, middle, high, tied = filter_tabs(project, [-10, 0, 10, 10])
    loose = m.map.root.add_child('Unscored')
    detail = high.add_child('Detail')
    original = m.to_dict()
    history = len(m._undo)
    original_sides = {n.id: box.x > 0 for n, box in m._layout().items()}
    m.select(low.id)
    m.setPriorityFilter(0)
    assert m.priorityFilterEnabled and m.priorityFilterText == 'Score ≥ 10'
    assert set(m._layout()) == {m.view_root, high, tied, detail}
    assert m.selectedId == m.view_root.id
    assert all((box.x > 0) == original_sides[n.id] for n, box in m._layout().items())
    m.setPriorityFilter(0.5)
    assert set(m._layout()) == {m.view_root, middle, high, tied, detail}
    m.setPriorityFilter(0.99)
    assert low not in m._layout() and loose not in m._layout()
    m.setPriorityFilter(1)
    assert low in m._layout() and loose in m._layout()
    assert m.priorityFilterText == 'All'
    assert m.to_dict() == original and len(m._undo) == history
    m.setPriorityFilter(float('nan'))
    assert m.priorityFilter == 1


def test_priority_filter_nested_branches_search_and_scope(project):
    m = project[0].mindmap
    low, high, nested_low = filter_tabs(project, [0, 10, 1])
    high.move_to(low)
    nested_low.move_to(high)
    kept = high.add_child('Guest kept')
    hidden = low.add_child('Guest hidden')
    excluded = nested_low.add_child('Guest excluded')
    high.folded = True
    m.setPriorityFilter(0)
    assert set(m._layout()) == {m.view_root, low, high}
    assert m._priority_nodes() == {m.view_root, low, high, kept}
    m.searchText('Guest')
    assert m.searchMatchCount == 1 and m.selectedId == kept.id
    assert not high.folded and kept in m._layout()
    m.setPriorityFilter(1)
    assert m.searchMatchCount == 3
    m.select(hidden.id)
    m.setPriorityFilter(0)
    assert m.selectedId == low.id
    m.select(kept.id)
    m.select(excluded.id, 'add')
    m.setPriorityFilter(0)
    assert m.selectedIds == [kept.id]
    m.set_scope(m.links[high.id])
    assert m.priorityFilter == 1
    m.setPriorityFilter(0)
    assert set(m._layout()) == {high, kept}
    m.load(m.to_dict())
    assert m.priorityFilter == 1


def test_priority_filter_equal_missing_and_live_scores(project):
    m = project[0].mindmap
    a, b = filter_tabs(project, [0.1, 0.1])
    loose = m.view_root.add_child('Loose')
    m.setPriorityFilter(0)
    assert set(m._layout()) == {m.view_root, a, b}
    m.setPriorityFilter(0.3)
    assert set(m._layout()) == {m.view_root, a, b}
    m.setPriorityFilter(0)
    project[1].getAllTabs()[0].priority_score = -2
    project[1].priorityRanksChanged.emit()
    assert a not in m._layout() and b in m._layout()
    for tab in project[1].getAllTabs():
        tab.include_in_priority_plot = False
    project[1].priorityRanksChanged.emit()
    assert not m.priorityFilterEnabled and m.priorityFilter == 1
    assert loose in m._layout()
    m.setPriorityFilter(0)
    assert m.priorityFilter == 1


def test_priority_filter_creation_reveal_and_compaction(project):
    m = project[0].mindmap
    low, high = filter_tabs(project, [0, 10])
    low.side = high.side = 'right'
    for i in range(5):
        low.add_child(str(i))
    old_height = max(b.y + b.height for b in m._layout().values()) - min(b.y for b in m._layout().values())
    m.setPriorityFilter(0)
    boxes = m._layout()
    assert max(b.y + b.height for b in boxes.values()) - min(b.y for b in boxes.values()) < old_height
    m.select(high.id)
    m.addThought(False)
    assert m.priorityFilter == 0 and m.map.find(m.selectedId) in m._layout()
    m.addSiblingRelative(high.id, False)
    assert m.priorityFilter == 1 and m.map.find(m.selectedId) in m._layout()
    m.setPriorityFilter(0)
    m.toggleBookmark(low.id)
    m.jumpToBookmark(low.id)
    assert m.priorityFilter == 1 and m.selectedId == low.id
    m.setPriorityFilter(0)
    m.reveal_reminder(low.id)
    assert m.priorityFilter == 1 and m.selectedId == low.id


def test_qml_priority_filter_slider_and_creation(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    low, high = filter_tabs(project, [0, 10])
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    pane = window.findChild(QObject, 'mindmapPane')
    slider = window.findChild(QObject, 'mindmapPriorityFilter')
    label = window.findChild(QObject, 'mindmapPriorityFilterText')
    pane.setProperty('zoom', 0.8)
    pan = (pane.property('panX'), pane.property('panY'))
    start = slider.mapToScene(QPoint(int(slider.width()) - 8, int(slider.height() / 2))).toPoint()
    end = slider.mapToScene(QPoint(8, int(slider.height() / 2))).toPoint()
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(window, end, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end)
    assert m.priorityFilter < 0.1 and low not in m._layout()
    assert label.property('text').startswith('Score ≥')
    assert pane.property('zoom') == 0.8
    assert (pane.property('panX'), pane.property('panY')) == pan
    slider.forceActiveFocus()
    assert not pane.property('shortcutsEnabled')
    selection = m.selectedId
    QTest.keyClick(window, Qt.Key_Right)
    assert m.priorityFilter > 0 and m.selectedId == selection
    count = len(list(m.map.walk()))
    QTest.keyClick(window, Qt.Key_Return)
    assert len(list(m.map.walk())) == count
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, end)
    QTest.mouseMove(window, start, 30)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, start)
    assert m.priorityFilter == 1 and label.property('text') == 'All'
    m.setPriorityFilter(0)
    assert slider.property('value') == 0
    viewport = window.findChild(QObject, 'mindmapViewport')
    point = viewport.mapToScene(QPoint(10, 10)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    assert pane.property('shortcutsEnabled')
    m.select(high.id)
    QTest.keyClick(window, Qt.Key_Return)
    QTest.qWait(30)
    assert m.priorityFilter == 1 and slider.property('value') == 1
    assert window.findChild(QObject, 'mindmapNodeEditor').property('visible')
    QTest.keyClick(window, Qt.Key_Escape)
    window.close()


def test_qml_double_click_tab_safeguards(project, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    node_id, tab_id = next(iter(m.links.items()))
    ordinary = m.map.find(node_id).add_child('Thought')
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showMindmap()
    QTest.qWait(150)
    activated = []
    m.tabActivated.connect(activated.append)

    def center(node_id):
        def find(item):
            if item.objectName() == 'mindmapNode_' + node_id:
                return item
            for child in item.childItems():
                found = find(child)
                if found is not None:
                    return found
            return None
        item = find(window.contentItem())
        return item.mapToScene(item.boundingRect().center()).toPoint()

    for modifier in (Qt.ControlModifier, Qt.ShiftModifier, Qt.AltModifier, Qt.MetaModifier):
        QTest.mouseDClick(window, Qt.LeftButton, modifier, center(node_id))
        assert not activated and pm.mindmapVisible
    m.select(ordinary.id)
    m.cutSelected()
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, center(node_id))
    assert not activated and m.canPaste and m.selectedId == node_id
    m.cancelCut()
    m.set_scope(tab_id)
    QTest.qWait(50)
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, center(node_id))
    assert not activated and pm.mindmapVisible
    assert not window.findChild(QObject, 'mindmapNodeEditor').property('visible')
    QTest.mouseDClick(window, Qt.LeftButton, Qt.NoModifier, center(ordinary.id))
    QTest.qWait(30)
    assert window.findChild(QObject, 'mindmapNodeEditor').property('visible')
    assert m.selectedId == ordinary.id and not activated
    QTest.keyClick(window, Qt.Key_Escape)
    window.close()
