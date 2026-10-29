"""Parent context navigation and searchable, undoable branch assignment."""
import copy
import time

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt
from PySide6.QtTest import QTest

from test_mindmap import project
from test_reminder_calendar import find
from progress_crypto import EncryptionCredentials


@pytest.mark.parametrize('kind', ['goal', 'activity', 'top_level'])
def test_parent_navigation_and_back(project, kind):
    pm, tabs, _, _ = project
    m = pm.mindmap
    goal_id = tabs.getAllTabs()[0].id
    child = m.map.find(next(key for key, tab in m.links.items() if tab == goal_id))
    parent = m.map.root if kind == 'top_level' else m.map.root.add_child('Parent')
    if parent is not m.map.root:
        child.move_to(parent)
    if kind == 'activity':
        m.setActivityFilter('plan:' + child.id)
    else:
        pm.showTabMindmap()
    before = (m.tabScoped, m.activityFilter, m.view_root.id)
    m.select(child.id)
    assert m.canNavigateToParent
    m.navigateToParent(m.openedNodeId)
    assert m.selectedId == child.id
    assert not m.tabScoped
    assert m.activityFilter == ('' if parent is m.map.root else 'plan:' + parent.id)
    assert child.id in {n['id'] for n in m.nodes}
    pm.goBack()
    assert (m.tabScoped, m.activityFilter, m.view_root.id) == before
    assert m.selectedId == child.id


def test_parent_goal_scope_and_whole_project_root(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    first = next(iter(m.links))
    tabs.addTab('Nested goal')
    nested_tab = tabs.getAllTabs()[-1].id
    nested = next(key for key, tab in m.links.items() if tab == nested_tab)
    m.map.find(nested).move_to(m.map.find(first))
    pm.openMindmapTab(nested_tab)
    pm.openNodeParent(nested)
    assert m.view_root.id == first and m.selectedId == nested
    pm.goBack()
    assert m.view_root.id == nested
    pm.showMindmap()
    assert not m.canNavigateToParent
    assert not m.canAssignParent(m.map.root.id)


def test_reparent_opened_goal_metadata_undo_and_reload(project, tmp_path, monkeypatch):
    pm, tabs, tasks, _ = project
    m = pm.mindmap
    tasks.addTask('Saved task')
    goal = next(iter(m.links))
    child = m.map.find(goal).add_child('Child').id
    destination = m.map.root.add_child('Destination')
    destination.add_child('Existing first child')
    m.reminders[goal] = {'at': time.time() + 86400, 'send_notification': True}
    m.plan_ranges[goal] = {'startDate': '2032-01-01', 'endDate': '2032-01-03'}
    pm.showTabMindmap()
    before = copy.deepcopy(m.to_dict())
    assert m.assignParent(goal, destination.id)
    assert m.map.find(goal).parent.id == destination.id
    assert destination.children[-1].id == goal
    assert m.activityFilter == 'plan:' + destination.id and m.selectedId == goal
    assert m.map.find(child).parent.id == goal
    assert m.reminders == before['reminders'] and m.plan_ranges == before['plan_ranges']
    m.undo()
    assert m.map.find(goal).parent is m.map.root
    m.redo()
    assert m.map.find(goal).parent.id == destination.id
    credentials = EncryptionCredentials(passphrase='parent-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'parents.progress'
    assert pm.saveProject(str(path))
    pm.loadProject(str(path))
    assert m.map.find(goal).parent.id == destination.id
    assert m.map.find(child).parent.id == goal
    assert tasks.to_dict()['tasks'][0]['title'] == 'Saved task'


def test_parent_search_paths_and_invalid_targets(project):
    pm, _, _, _ = project
    m = pm.mindmap
    source = m.map.root.add_child('Source')
    descendant = source.add_child('Descendant')
    left = m.map.root.add_child('Left').add_child('Duplicate')
    right = m.map.root.add_child('Right').add_child('Duplicate')
    m.setActivityFilter('plan:' + source.id)
    options = m.parentOptions(source.id, 'duplicate')
    assert {o['nodeId'] for o in options} == {left.id, right.id}
    assert len({o['path'] for o in options}) == 2
    assert [o['nodeId'] for o in m.parentOptions(source.id, 'LEFT / dupl')] == [left.id]
    invalid = [source.id, descendant.id, m.map.root.id, 'missing']
    before = copy.deepcopy(m.to_dict())
    for target in invalid:
        assert not m.assignParent(source.id, target)
        assert m.to_dict() == before
    assert not m.assignParent('missing', left.id)
    assert not m.assignParent(m.map.root.id, left.id)
    # An option can become invalid between opening the dialog and submitting it.
    left.move_to(source)
    assert not m.assignParent(source.id, left.id)


def test_reference_cycle_exclusion_and_placement_move(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    original = next(iter(m.links))
    tab = tabs.getAllTabs()[0].id
    container = m.map.root.add_child('Container')
    other = m.map.root.add_child('Other')
    assert m.addTabReference(container.id, tab)
    ref = m.selectedId
    # The container already reaches the goal through a reference.
    assert original not in {o['nodeId'] for o in m.parentOptions(container.id, '')}
    before = copy.deepcopy(m.to_dict())
    assert not m.assignParent(container.id, original)
    assert m.to_dict() == before
    assert m.assignParent(ref, other.id)
    assert m.map.find(ref).parent.id == other.id
    assert m.map.find(original).parent is m.map.root
    assert m.references == {ref: tab}


def test_qml_parent_button_and_search_assignment(project, actiondraw_window, app):
    pm, tabs, tasks, diagram = project
    m = pm.mindmap
    opened = next(iter(m.links))
    source = m.map.find(opened).add_child('Move this')
    destination = m.map.root.add_child('Search destination')
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.show()
    pm.showTabMindmap()
    QTest.qWait(100)
    button = find(window, 'mindmapParentButton')
    assert button.isVisible()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, button.mapToScene(button.boundingRect().center()).toPoint())
    assert not m.tabScoped and m.selectedId == opened
    pm.goBack()
    assert m.tabScoped
    # The context target must win over the unrelated selected node.
    m.select(opened)
    menu = window.findChild(QObject, 'mindmapNodeMenu')
    menu.setProperty('targetNodeId', source.id)
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapAddParent'), 'triggered')
    QTest.qWait(30)
    dialog = window.findChild(QObject, 'mindmapParentDialog')
    assert dialog.property('visible')
    search = find(window, 'mindmapParentSearch')
    options = find(window, 'mindmapParentList')
    QTest.keyClick(window, Qt.Key_Down)
    assert options.property('currentIndex') == 1
    QTest.keyClick(window, Qt.Key_Up)
    assert options.property('currentIndex') == 0
    search.setProperty('text', 'Search destination')
    QTest.keyClick(window, Qt.Key_Return)
    QTest.qWait(30)
    assert not dialog.property('visible')
    assert m.map.find(source.id).parent.id == destination.id
    assert m.map.find(opened).parent is m.map.root
    assert m.selectedId == source.id and m.activityFilter == 'plan:' + destination.id
    # Cancel must not move anything or leave map typing shortcuts active.
    menu.setProperty('targetNodeId', source.id)
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapAddParent'), 'triggered')
    QTest.qWait(30)
    assert not find(window, 'mindmapPane').property('shortcutsEnabled')
    QTest.keyClick(window, Qt.Key_Escape)
    assert not dialog.property('visible')
    assert m.map.find(source.id).parent.id == destination.id
    temporary = m.map.root.add_child('Temporary destination')
    QMetaObject.invokeMethod(window.findChild(QObject, 'mindmapAddParent'), 'triggered')
    QTest.qWait(30)
    search.setProperty('text', 'Temporary destination')
    # Simulate a destination disappearing after the displayed results were read.
    temporary.remove()
    QTest.keyClick(window, Qt.Key_Return)
    assert dialog.property('visible') and dialog.property('errorText')
    assert m.map.find(source.id).parent.id == destination.id
    QTest.keyClick(window, Qt.Key_Escape)
    window.close()


def test_move_projected_child_uses_existing_shared_content_semantics(project):
    pm, tabs, _, _ = project
    m = pm.mindmap
    original = next(iter(m.links))
    child = m.map.find(original).add_child('Shared child')
    container = m.map.root.add_child('Container')
    destination = m.map.root.add_child('Destination')
    assert m.addTabReference(container.id, tabs.getAllTabs()[0].id)
    ref = m.selectedId
    projected = next(n['id'] for n in m.nodes if n['sourceId'] == child.id and '/' in n['id'])
    assert m.assignParent(projected, destination.id)
    assert m.map.find(child.id).parent.id == destination.id
    assert m.references == {ref: tabs.getAllTabs()[0].id}
    assert m.selectedId == child.id
    m.undo()
    assert m.map.find(child.id).parent.id == original
