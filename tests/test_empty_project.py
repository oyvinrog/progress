"""Empty projects are persisted state, not a temporary onboarding overlay."""
import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt
from PySide6.QtTest import QTest

from actiondraw.model import DiagramModel
from task_model import ProjectManager, TabModel, TaskModel
from progress_crypto import EncryptionCredentials


@pytest.fixture
def empty_project(app):
    tasks, tabs = TaskModel(), TabModel()
    diagram = DiagramModel(tasks)
    return ProjectManager(tasks, diagram, tabs), tabs, tasks, diagram


def test_empty_project_roundtrip(empty_project, tmp_path, monkeypatch):
    pm, tabs, tasks, diagram = empty_project
    assert tabs.tabCount == 0 and tabs.currentTabIndex == -1
    assert tabs.getCurrentTabData() is None
    assert not pm.hasUnsavedChanges()
    pm.showTabMindmap()
    pm.reloadCurrentTab()
    assert pm.addActionPaintToMindmap() == []
    assert pm.addCausalModelToMindmap() == []
    pm.mindmap.map.root.add_child('Project-level idea')
    monkeypatch.setattr(ProjectManager, '_prompt_encryption_credentials',
                        lambda *args: EncryptionCredentials(passphrase='empty-project-test'))
    path = tmp_path / 'empty.progress'
    assert pm.saveProject(str(path))
    tabs.addTab('Temporary')
    pm.loadProject(str(path))
    assert tabs.tabCount == 0 and tabs.currentTabIndex == -1
    assert pm.mindmap.map.root.children[0].text == 'Project-level idea'
    assert not pm.hasUnsavedChanges()
    assert pm._build_project_data()['tabs'] == []


def test_last_goal_deletion_and_recreation(empty_project):
    pm, tabs, tasks, diagram = empty_project
    tabs.addTab('First goal')
    pm.switchTab(0)
    tasks.addTask('Old task')
    assert pm.mindmap.tabScoped
    assert pm.mindmap.view_root.text == 'First goal'
    pm.removeTab(0)
    assert tabs.tabCount == 0 and tabs.currentTabIndex == -1
    assert tasks.rowCount() == 0
    assert diagram.count == 0
    tabs.addTab('Next goal')
    pm.switchTab(0)
    assert pm.mindmap.view_root.text == 'Next goal'
    assert tasks.rowCount() == 0


def test_last_goal_mindmap_undo_redo(empty_project):
    pm, tabs, tasks, diagram = empty_project
    tabs.addTab('Only goal')
    tasks.addTask('Remember this step')
    m = pm.mindmap
    node_id = next(iter(m.links))
    m.select(node_id)
    m.deleteSelected()
    assert tabs.tabCount == 0 and tabs.currentTabIndex == -1
    m.undo()
    assert tabs.tabCount == 1 and tabs.currentTabIndex == 0
    assert tabs.currentTabName == 'Only goal'
    assert tasks.to_dict()['tasks'][0]['title'] == 'Remember this step'
    m.redo()
    assert tabs.tabCount == 0 and tabs.currentTabIndex == -1
    assert tasks.rowCount() == 0


@pytest.mark.parametrize('size', [(1100, 800), (640, 480)])
def test_empty_page_first_goal_flow(empty_project, app, actiondraw_window, size):
    pm, tabs, tasks, diagram = empty_project
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]
    window.resize(*size)
    QTest.qWait(100)
    page = window.findChild(QObject, 'emptyProjectPage')
    button = window.findChild(QObject, 'emptyProjectAddGoal')
    dialog = window.findChild(QObject, 'goalNameDialog')
    field = window.findChild(QObject, 'goalNameField')
    assert page.property('visible')
    assert button.property('activeFocus')
    QTest.keyClick(window, Qt.Key_Space)
    QTest.qWait(50)
    assert dialog.property('visible')
    field.setProperty('text', '   ')
    QTest.keyClick(window, Qt.Key_Return)
    assert tabs.tabCount == 0 and dialog.property('visible')
    QMetaObject.invokeMethod(dialog, 'reject')
    QTest.qWait(100)
    assert page.property('visible') and tabs.tabCount == 0
    QMetaObject.invokeMethod(button, 'clicked')
    QTest.qWait(50)
    field.setProperty('text', 'Learn a language')
    QTest.keyClick(window, Qt.Key_Return)
    QTest.qWait(100)
    assert tabs.tabCount == 1
    assert not page.property('visible')
    assert pm.mindmap.tabScoped
    assert pm.mindmap.view_root.text == 'Learn a language'
    pm.removeTab(0)
    QTest.qWait(50)
    assert page.property('visible')


def test_empty_page_keyboard_undo_restores_goal(empty_project, app, actiondraw_window):
    pm, tabs, tasks, diagram = empty_project
    tabs.addTab('Recover me')
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]
    QTest.qWait(100)
    pm.mindmap.select(next(iter(pm.mindmap.links)))
    pm.mindmap.deleteSelected()
    QTest.qWait(100)
    assert window.property('emptyProject')
    QTest.keyClick(window, Qt.Key_Z, Qt.ControlModifier)
    QTest.qWait(100)
    assert tabs.currentTabName == 'Recover me'
    assert not window.property('emptyProject')


def test_empty_model_notifications_are_consistent(app):
    tabs = TabModel()
    observed = []
    def record(*args):
        current = tabs.getCurrentTabData()
        observed.append((tabs.tabCount, tabs.currentTabIndex, current.name if current else None))
    tabs.rowsInserted.connect(record)
    tabs.rowsRemoved.connect(record)
    tabs.modelReset.connect(record)
    tabs.addTab('First')
    tabs.removeTab(0)
    tabs.setTabs([], 99)
    assert observed == [(1, 0, 'First'), (0, -1, None), (0, -1, None)]


def test_empty_project_markdown_cannot_create_orphan_tasks(empty_project):
    pm, tabs, tasks, diagram = empty_project
    assert pm.createTaskFromWorkspaceMarkdownSelection('Task', 0, 0) == ''
    assert pm.createTasksFromWorkspaceMarkdownList('- Task', 0, 0) == []
    assert tasks.rowCount() == 0 and diagram.count == 0
