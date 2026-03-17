"""Bridge diagram items and the markdown editor window."""

from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from .markdown_note_editor_window import MarkdownNoteEditor
from .markdown_note_tabs import normalize_editor_tabs


class MarkdownNoteManager(QObject):
    """Open markdown notes tied to diagram items."""
    taskCreated = Signal(str)
    itemSaved = Signal(str)
    projectSaveRequested = Signal()
    editorStateChanged = Signal()

    def __init__(self, diagram_model) -> None:
        super().__init__()
        self._diagram_model = diagram_model
        self._editor_open = False
        self._active_editor_type = ""
        self._active_item_id = ""
        self._active_target_x = 0.0
        self._active_target_y = 0.0
        self._editor = MarkdownNoteEditor(diagram_model, self)
        self._editor.noteSaved.connect(self._save_note)
        self._editor.noteCanceled.connect(self._cancel_note)

    @Property(bool, notify=editorStateChanged)
    def editorOpen(self) -> bool:
        return self._editor_open

    @Property(str, notify=editorStateChanged)
    def activeEditorType(self) -> str:
        return self._active_editor_type

    @Property(str, notify=editorStateChanged)
    def activeItemId(self) -> str:
        return self._active_item_id

    @Slot(str)
    def openNote(self, item_id: str) -> None:
        item = self._diagram_model.getItem(item_id)
        if not item:
            return
        title_text = item.text.strip()
        title = f"{title_text} Note" if title_text else f"{item.item_type.value.title()} Note"
        self._set_editor_state("note", item_id, float(item.x), float(item.y), True)
        self._editor.open(
            item_id,
            self._diagram_model.getItemMarkdown(item_id),
            title,
            editor_type="note",
            target_x=float(item.x),
            target_y=float(item.y),
            tabs=self._diagram_model.getEditorTabs(item_id, "note"),
        )

    @Slot(str)
    def openObstacle(self, item_id: str) -> None:
        item = self._diagram_model.getItem(item_id)
        if not item:
            return
        title_text = item.text.strip()
        title = f"{title_text} Obstacle" if title_text else "Obstacle"
        self._set_editor_state("obstacle", item_id, float(item.x), float(item.y), True)
        self._editor.open(
            item_id,
            self._diagram_model.getItemObstacleMarkdown(item_id),
            title,
            editor_type="obstacle",
            target_x=float(item.x),
            target_y=float(item.y),
            tabs=self._diagram_model.getEditorTabs(item_id, "obstacle"),
        )

    @Slot(str, float, float, str)
    def openFreeText(self, item_id: str, x: float, y: float, initial_text: str) -> None:
        source_item_id = item_id or ""
        text_value = initial_text or ""
        target_x = float(x)
        target_y = float(y)

        if source_item_id:
            item = self._diagram_model.getItem(source_item_id)
            if not item:
                return
            text_value = item.text
            target_x = float(item.x)
            target_y = float(item.y)

        title = "Edit Free Text" if source_item_id else "Free Text"
        self._set_editor_state("freetext", source_item_id, target_x, target_y, True)
        self._editor.open(
            source_item_id,
            text_value,
            title,
            editor_type="freetext",
            target_x=target_x,
            target_y=target_y,
            tabs=self._diagram_model.getEditorTabs(source_item_id, "freetext") if source_item_id else normalize_editor_tabs([], fallback_text=text_value),
        )

    def _save_note(self, item_id: str, note_text: str, tabs: list | None = None) -> None:
        normalized_tabs = normalize_editor_tabs(tabs, fallback_text=note_text or "")
        canonical_text = normalized_tabs[0]["text"]
        saved_item_id = ""
        if self._active_editor_type == "freetext":
            if self._active_item_id:
                self._diagram_model.setEditorTabs(self._active_item_id, "freetext", normalized_tabs)
                saved_item_id = self._active_item_id
            else:
                saved_item_id = self._diagram_model.addPresetItemWithText(
                    "freetext",
                    self._active_target_x,
                    self._active_target_y,
                    canonical_text,
                )
                if saved_item_id:
                    self._diagram_model.setEditorTabs(saved_item_id, "freetext", normalized_tabs)
                    self._set_editor_state(
                        "freetext",
                        saved_item_id,
                        self._active_target_x,
                        self._active_target_y,
                        True,
                    )
                    self._editor.set_note_id(saved_item_id)
        elif self._active_editor_type == "obstacle":
            self._diagram_model.setEditorTabs(item_id, "obstacle", normalized_tabs)
            saved_item_id = item_id
        else:
            self._diagram_model.setEditorTabs(item_id, "note", normalized_tabs)
            saved_item_id = item_id

        if saved_item_id:
            self.itemSaved.emit(saved_item_id)
            if self._active_editor_type == "freetext" and self._active_item_id != saved_item_id:
                self._set_editor_state(
                    "freetext",
                    saved_item_id,
                    self._active_target_x,
                    self._active_target_y,
                    True,
                )
            self._editor.show_save_confirmation()

    def _cancel_note(self, _item_id: str) -> None:
        self._set_editor_state("", "", 0.0, 0.0, False)

    def _set_editor_state(
        self,
        editor_type: str,
        item_id: str,
        x: float,
        y: float,
        is_open: bool,
    ) -> None:
        changed = (
            self._editor_open != is_open
            or self._active_editor_type != editor_type
            or self._active_item_id != item_id
            or self._active_target_x != x
            or self._active_target_y != y
        )
        self._editor_open = is_open
        self._active_editor_type = editor_type
        self._active_item_id = item_id
        self._active_target_x = x
        self._active_target_y = y
        if changed:
            self.editorStateChanged.emit()

    @Slot(str, str, result=str)
    def createTaskFromNoteSelection(self, item_id: str, selected_text: str) -> str:
        task_id = self._diagram_model.createTaskFromMarkdownSelection(item_id, selected_text)
        if task_id:
            self.taskCreated.emit(task_id)
        return task_id

    @Slot(str, str, float, float, str, str, result=str)
    def createTaskFromEditorSelection(
        self,
        editor_type: str,
        item_id: str,
        x: float,
        y: float,
        current_text: str,
        selected_text: str,
    ) -> str:
        if not selected_text:
            return ""

        source_id = item_id or ""
        if editor_type == "freetext" and not source_id:
            source_id = self._diagram_model.addPresetItemWithText(
                "freetext",
                float(x),
                float(y),
                current_text or "",
            )
            if not source_id:
                return ""
            self._set_editor_state("freetext", source_id, float(x), float(y), True)
        if not source_id:
            return ""

        task_id = self._diagram_model.createTaskFromMarkdownSelection(source_id, selected_text)
        if task_id:
            self.taskCreated.emit(task_id)
        return task_id

    @Slot()
    def requestProjectSave(self) -> None:
        self.projectSaveRequested.emit()
