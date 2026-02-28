"""Standalone window for editing markdown and free-text content."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtQml import QQmlApplicationEngine

from .markdown_image_paster import MarkdownImagePaster
from .markdown_preview_formatter import MarkdownPreviewFormatter
from .markdown_syntax_highlighter import MarkdownHighlighterBridge
from .qml import MARKDOWN_NOTE_EDITOR_QML_PATH, QML_DIR


class MarkdownNoteEditor(QObject):
    """Standalone window for editing markdown notes and free text."""

    noteSaved = Signal(str, str)
    noteCanceled = Signal(str)

    def __init__(self, diagram_model=None, markdown_note_manager=None) -> None:
        super().__init__()
        self._engine = QQmlApplicationEngine()
        self._engine.addImportPath(str(QML_DIR))
        self._diagram_model = diagram_model
        self._markdown_note_manager = markdown_note_manager
        self._image_paster = MarkdownImagePaster()
        self._preview_formatter = MarkdownPreviewFormatter()
        self._highlighter_bridge = MarkdownHighlighterBridge()
        self._engine.rootContext().setContextProperty("markdownImagePaster", self._image_paster)
        self._engine.rootContext().setContextProperty("markdownPreviewFormatter", self._preview_formatter)
        self._engine.rootContext().setContextProperty("markdownHighlighterBridge", self._highlighter_bridge)
        self._engine.rootContext().setContextProperty("diagramModel", self._diagram_model)
        self._engine.rootContext().setContextProperty("markdownNoteManager", self._markdown_note_manager)
        self._engine.load(QUrl.fromLocalFile(str(MARKDOWN_NOTE_EDITOR_QML_PATH)))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError("Failed to load markdown note editor QML.")
        self._root = roots[0]
        self._root.saveRequested.connect(self._handle_save)
        self._root.cancelRequested.connect(self._handle_cancel)

    def open(
        self,
        note_id: str,
        note_text: str,
        note_title: str,
        editor_type: str = "note",
        target_x: float = 0.0,
        target_y: float = 0.0,
    ) -> None:
        self._root.setProperty("editorType", editor_type or "note")
        self._root.setProperty("noteId", note_id)
        self._root.setProperty("noteTitle", note_title)
        self._root.setProperty("targetX", float(target_x))
        self._root.setProperty("targetY", float(target_y))
        # Clear first to avoid stale editor state when reusing the same window instance.
        self._root.setProperty("noteText", "")
        self._root.setProperty("noteText", note_text or "")
        self._root.show()
        self._root.raise_()
        self._root.requestActivate()

    def set_note_id(self, note_id: str) -> None:
        self._root.setProperty("noteId", note_id or "")

    def _handle_save(self, note_id: str, note_text: str) -> None:
        self.noteSaved.emit(note_id, note_text)

    def _handle_cancel(self) -> None:
        note_id = self._root.property("noteId")
        self._root.hide()
        self.noteCanceled.emit(note_id)
