"""Bridge diagram items and the markdown editor window."""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from .markdown_note_editor_window import MarkdownNoteEditor


class MarkdownNoteManager(QObject):
    """Open markdown notes tied to diagram items."""

    def __init__(self, diagram_model) -> None:
        super().__init__()
        self._diagram_model = diagram_model
        self._editor = MarkdownNoteEditor()
        self._editor.noteSaved.connect(self._save_note)

    @Slot(str)
    def openNote(self, item_id: str) -> None:
        item = self._diagram_model.getItem(item_id)
        if not item:
            return
        title_text = item.text.strip()
        title = f"{title_text} Note" if title_text else f"{item.item_type.value.title()} Note"
        self._editor.open(item_id, item.note_markdown, title)

    def _save_note(self, item_id: str, note_text: str) -> None:
        self._diagram_model.setItemMarkdown(item_id, note_text)
