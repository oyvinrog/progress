"""Keyboard and lifecycle coverage for the project picker."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QMessageBox

from actiondraw.project_file_dialog import ProjectFileDialog


@pytest.fixture
def picker(app, tmp_path):
    manager = Mock(currentFilePath=str(tmp_path / "current.progress"))
    window = QQuickWindow()
    controller = ProjectFileDialog(manager)
    controller.set_window(window)
    controller.open()
    app.processEvents()
    yield controller, manager
    controller._dialog.reject()
    controller._dialog.deleteLater()
    controller.deleteLater()
    window.deleteLater()
    app.processEvents()


@pytest.mark.parametrize('absolute,paste,quoted', [
    (False, False, False), (True, False, False),
    (False, True, False), (True, True, False), (True, True, True),
])
def test_filename_entry(app, tmp_path, picker, absolute, paste, quoted):
    controller, manager = picker
    name = 'prosjekt ø space.progress' if paste else 'project space.progress'
    path = tmp_path / name
    path.write_text('{}')
    entry = controller._dialog.findChild(QLineEdit, 'fileNameEdit')
    assert entry.isVisible() and not entry.isReadOnly()
    assert controller._dialog.windowHandle().transientParent() == controller._window
    value = str(path) if absolute else name
    assert entry.hasFocus()
    if quoted:
        value = '"' + value + '"'
    if paste:
        app.clipboard().setText(value)
        QTest.keyClick(entry, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    else:
        QTest.keyClicks(entry, value)
    QTest.keyClick(entry, Qt.Key.Key_Return)
    app.processEvents()
    manager.loadProject.assert_called_once_with(str(path))
    assert not controller.visible


def test_cancel_and_reopen(app, picker):
    controller, manager = picker
    changes = []
    controller.visibleChanged.connect(lambda: changes.append(controller.visible))
    controller._dialog.reject()
    assert not controller.visible
    controller.open()
    controller.open()
    assert controller.visible
    QTest.keyClick(controller._dialog, Qt.Key.Key_Escape)
    app.processEvents()
    assert changes == [False, True, False]
    manager.loadProject.assert_not_called()


def test_project_directory_and_browsing_location(app, tmp_path, picker):
    controller, manager = picker
    dialog = controller._dialog
    assert dialog.directory().absolutePath() == str(tmp_path)
    browsed = tmp_path / 'browsed'
    browsed.mkdir()
    dialog.setDirectory(str(browsed))
    dialog.reject()
    controller.open()
    assert dialog.directory().absolutePath() == str(browsed)

    other = tmp_path / 'other project'
    other.mkdir()
    manager.currentFilePath = str(other / 'another.progress')
    dialog.reject()
    controller.open()
    assert dialog.directory().absolutePath() == str(other)

    # Deleted project folders must not prevent opening the picker.
    manager.currentFilePath = str(tmp_path / 'missing folder' / 'deleted.progress')
    dialog.reject()
    controller.open()
    assert dialog.directory().absolutePath() == str(other)


def test_reopen_selects_previous_text(app, picker):
    controller, manager = picker
    entry = controller._dialog.findChild(QLineEdit, 'fileNameEdit')
    entry.setText('previous.progress')
    controller._dialog.reject()
    controller.open()
    app.processEvents()
    assert entry.hasFocus()
    assert entry.selectedText() == 'previous.progress'
    QTest.keyClicks(entry, 'replacement.progress')
    assert entry.text() == 'replacement.progress'
    manager.loadProject.assert_not_called()


def test_directory_and_invalid_path(app, tmp_path, picker):
    controller, manager = picker
    folder = tmp_path / 'folder'
    folder.mkdir()
    entry = controller._dialog.findChild(QLineEdit, 'fileNameEdit')
    entry.setText(str(folder))
    QTest.keyClick(entry, Qt.Key.Key_Return)
    assert controller._dialog.directory().absolutePath() == str(folder)
    assert controller.visible

    # QFileDialog reports nonexistent files with a modal message box.
    timer = QTimer()
    timer.timeout.connect(lambda: [w.accept() for w in app.topLevelWidgets() if isinstance(w, QMessageBox)])
    timer.start(10)
    try:
        entry.setText(str(folder / 'missing.progress'))
        QTest.keyClick(entry, Qt.Key.Key_Return)
    finally:
        timer.stop()
    assert controller.visible
    manager.loadProject.assert_not_called()


def test_qml_load_dialog_interface(app, actiondraw_window):
    from PySide6.QtQml import QQmlEngine, QQmlExpression
    from actiondraw.model import DiagramModel
    from task_model import TaskModel

    tasks = TaskModel()
    model = DiagramModel(task_model=tasks)
    engine = actiondraw_window(model, tasks)
    root = engine.rootObjects()[0]
    context = QQmlEngine.contextForObject(root)

    def evaluate(expression):
        query = QQmlExpression(context, root, expression)
        value = query.evaluate()
        assert not query.hasError(), query.error().toString()
        return value[0] if isinstance(value, tuple) else value

    assert evaluate('dialogs.loadDialog.visible') is False
    evaluate('dialogs.loadDialog.open()')
    app.processEvents()
    assert evaluate('dialogs.loadDialog.visible') is True
    assert evaluate('dialogs.anyDialogVisible') is True
    engine._project_file_dialog._dialog.reject()
    app.processEvents()
    assert evaluate('dialogs.loadDialog.visible') is False
