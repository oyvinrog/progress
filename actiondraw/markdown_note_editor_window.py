"""Standalone window for editing markdown notes."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine

from .markdown_image_paster import MarkdownImagePaster
from .qml import MARKDOWN_NOTE_EDITOR_QML_PATH, QML_DIR


class MarkdownNoteEditor(QObject):
    """Standalone window for editing markdown notes."""

    noteSaved = Signal(str, str)
    noteCanceled = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._engine = QQmlApplicationEngine()
        self._engine.addImportPath(str(QML_DIR))
        self._image_paster = MarkdownImagePaster()
        self._engine.rootContext().setContextProperty("markdownImagePaster", self._image_paster)
        self._engine.load(QUrl.fromLocalFile(str(MARKDOWN_NOTE_EDITOR_QML_PATH)))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError("Failed to load markdown note editor QML.")
        self._root = roots[0]
        self._root.saveRequested.connect(self._handle_save)
        self._root.cancelRequested.connect(self._handle_cancel)

    def open(self, note_id: str, note_text: str, note_title: str) -> None:
        self._root.setProperty("noteId", note_id)
        self._root.setProperty("noteText", note_text)
        self._root.setProperty("noteTitle", note_title)
        self._root.show()
        self._root.raise_()
        self._root.requestActivate()

    def _handle_save(self, note_id: str, note_text: str) -> None:
        self._root.hide()
        self.noteSaved.emit(note_id, note_text)

    def _handle_cancel(self) -> None:
        note_id = self._root.property("noteId")
        self._root.hide()
        self.noteCanceled.emit(note_id)
