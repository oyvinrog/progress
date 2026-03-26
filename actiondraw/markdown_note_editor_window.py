"""Standalone window for editing markdown and free-text content."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtQml import QJSValue, QQmlApplicationEngine

from .markdown_image_paster import MarkdownImagePaster
from .markdown_note_tabs import normalize_editor_tabs
from .markdown_preview_formatter import MarkdownPreviewFormatter
from .markdown_pdf_exporter import MarkdownPdfExporter
from .markdown_syntax_highlighter import MarkdownHighlighterBridge
from .qml import MARKDOWN_NOTE_EDITOR_QML_PATH, QML_DIR


class MarkdownNoteEditor(QObject):
    """Standalone window for editing markdown notes and free text."""

    noteSaved = Signal(str, str, list)
    noteSavedAndClosed = Signal(str, str, list)
    noteCanceled = Signal(str)

    def __init__(self, diagram_model=None, markdown_note_manager=None) -> None:
        super().__init__()
        self._engine = QQmlApplicationEngine()
        self._engine.addImportPath(str(QML_DIR))
        self._diagram_model = diagram_model
        self._markdown_note_manager = markdown_note_manager
        self._image_paster = MarkdownImagePaster()
        self._preview_formatter = MarkdownPreviewFormatter()
        self._pdf_exporter = MarkdownPdfExporter(self._image_paster)
        self._highlighter_bridge = MarkdownHighlighterBridge()
        self._engine.rootContext().setContextProperty("markdownImagePaster", self._image_paster)
        self._engine.rootContext().setContextProperty("markdownPreviewFormatter", self._preview_formatter)
        self._engine.rootContext().setContextProperty("markdownPdfExporter", self._pdf_exporter)
        self._engine.rootContext().setContextProperty("markdownHighlighterBridge", self._highlighter_bridge)
        self._engine.rootContext().setContextProperty("diagramModel", self._diagram_model)
        self._engine.rootContext().setContextProperty("markdownNoteManager", self._markdown_note_manager)
        self._engine.load(QUrl.fromLocalFile(str(MARKDOWN_NOTE_EDITOR_QML_PATH)))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError("Failed to load markdown note editor QML.")
        self._root = roots[0]
        self._root.saveRequested.connect(self._handle_save)
        self._root.saveAndCloseRequested.connect(self._handle_save_and_close)
        self._root.cancelRequested.connect(self._handle_cancel)

    def open(
        self,
        note_id: str,
        note_text: str,
        note_title: str,
        editor_type: str = "note",
        target_x: float = 0.0,
        target_y: float = 0.0,
        tabs: list[dict[str, str]] | None = None,
    ) -> None:
        normalized_tabs = normalize_editor_tabs(tabs, fallback_text=note_text or "")
        self._root.setProperty("editorType", editor_type or "note")
        self._root.setProperty("noteId", note_id)
        self._root.setProperty("noteTitle", note_title)
        self._root.setProperty("targetX", float(target_x))
        self._root.setProperty("targetY", float(target_y))
        self._root.setProperty("saveConfirmationVisible", False)
        self._root.setProperty("restoringState", True)
        self._root.setProperty("activeTabIndex", 0)
        self._root.setProperty("noteTabs", [])
        self._root.setProperty("noteText", "")
        if hasattr(self._root, "loadEditorState"):
            self._root.loadEditorState(normalized_tabs, normalized_tabs[0]["text"])
        else:
            self._root.setProperty("noteTabs", normalized_tabs)
            self._root.setProperty("noteText", normalized_tabs[0]["text"])
            self._root.setProperty("restoringState", False)
        self._root.show()
        self._root.raise_()
        self._root.requestActivate()

    def set_note_id(self, note_id: str) -> None:
        self._root.setProperty("noteId", note_id or "")

    def close(self) -> None:
        self._root.hide()

    def show_save_confirmation(self) -> None:
        self._root.showSaveConfirmation()

    def show_external_prompt(self, message: str) -> None:
        self._root.setProperty("externalPromptText", message or "Touch your YubiKey to continue.")
        self._root.setProperty("externalPromptVisible", True)
        self._root.show()
        self._root.raise_()
        self._root.requestActivate()

    def hide_external_prompt(self) -> None:
        self._root.setProperty("externalPromptVisible", False)

    def _handle_save(self, note_id: str, note_text: str, tabs: list) -> None:
        if isinstance(tabs, QJSValue):
            tabs = tabs.toVariant()
        self.noteSaved.emit(note_id, note_text, list(tabs or []))

    def _handle_save_and_close(self, note_id: str, note_text: str, tabs: list) -> None:
        if isinstance(tabs, QJSValue):
            tabs = tabs.toVariant()
        self._root.hide()
        self.noteSavedAndClosed.emit(note_id, note_text, list(tabs or []))

    def _handle_cancel(self) -> None:
        note_id = self._root.property("noteId")
        self._root.hide()
        self.noteCanceled.emit(note_id)
