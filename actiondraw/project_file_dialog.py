"""Project picker with an always-editable filename field."""

from pathlib import Path

from PySide6.QtCore import QObject, Property, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QLineEdit


class ProjectFileDialog(QObject):
    visibleChanged = Signal()

    def __init__(self, project_manager, parent=None):
        super().__init__(parent)
        self._project_manager = project_manager
        self._dialog = None
        self._window = None
        self._visible = False
        self._last_project_path = None
        self._focus_timer = QTimer(self)
        self._focus_timer.setSingleShot(True)
        self._focus_timer.timeout.connect(self._focus_filename)

    def set_window(self, window):
        self._window = window

    @Property(bool, notify=visibleChanged)
    def visible(self):
        return self._visible

    def _set_visible(self, visible):
        if self._visible != visible:
            self._visible = visible
            self.visibleChanged.emit()

    @Slot()
    def open(self):
        if self._dialog is None:
            dialog = QFileDialog()
            dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
            dialog.setWindowTitle("Load Project")
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilters(["Progress files (*.progress)", "All files (*)"])
            dialog.setLabelText(QFileDialog.DialogLabel.FileName, "Filename or path:")
            entry = dialog.findChild(QLineEdit, "fileNameEdit")
            if entry is not None:
                entry.setPlaceholderText("Type or paste a filename or full path")
                entry.setAccessibleName("Filename or path")
                entry.setToolTip("Enter a filename in this folder or paste a full path. Press Enter to open.")
            dialog.setWindowModality(Qt.WindowModality.WindowModal)
            dialog.accepted.connect(self._accepted)
            dialog.finished.connect(lambda _result: self._set_visible(False))
            self.destroyed.connect(dialog.deleteLater)
            self._dialog = dialog

        dialog = self._dialog
        if self._window is not None:
            dialog.winId()  # Create the handle before assigning its QQuickWindow owner.
            dialog.windowHandle().setTransientParent(self._window)
        if not dialog.isVisible():
            project_path = getattr(self._project_manager, "currentFilePath", "")
            # Keep the user's browsing location until a different project is loaded.
            if project_path != self._last_project_path:
                if project_path:
                    directory = Path(project_path).parent
                    if directory.is_dir():
                        dialog.setDirectory(str(directory))
                self._last_project_path = project_path
            dialog.open()
            self._set_visible(True)
            dialog.raise_()
            dialog.activateWindow()
            # Window activation can reset the selection; focus after it completes.
            self._focus_timer.start(0)
        else:
            dialog.raise_()
            dialog.activateWindow()

    def _focus_filename(self):
        if self._dialog is not None and self._dialog.isVisible():
            entry = self._dialog.findChild(QLineEdit, "fileNameEdit")
            if entry is not None:
                entry.setFocus(Qt.FocusReason.OtherFocusReason)
                entry.selectAll()

    def _accepted(self):
        # Restore QML shortcut state before loading can prompt for credentials.
        self._set_visible(False)
        files = self._dialog.selectedFiles()
        if files and self._project_manager is not None:
            self._project_manager.loadProject(files[0])
