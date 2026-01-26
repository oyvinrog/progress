"""Core DiagramModel class for ActionDraw.

This module provides the main Qt model for diagram items and edges.
"""

from __future__ import annotations

import urllib.parse
import webbrowser
from itertools import count
from typing import Any, Dict, List, Optional

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Property,
    Qt,
    Signal,
    Slot,
)

from .clipboard import ClipboardMixin
from .constants import ITEM_PRESETS
from .drawing import DrawingMixin
from .layout import LayoutMixin
from .subdiagram import SubDiagramMixin
from .types import DiagramEdge, DiagramItem, DiagramItemType, DrawingPoint, DrawingStroke


class DiagramModel(
    ClipboardMixin,
    DrawingMixin,
    LayoutMixin,
    SubDiagramMixin,
    QAbstractListModel,
):
    """Qt model exposing diagram items to QML."""

    IdRole = Qt.UserRole + 1
    TypeRole = Qt.UserRole + 2
    XRole = Qt.UserRole + 3
    YRole = Qt.UserRole + 4
    WidthRole = Qt.UserRole + 5
    HeightRole = Qt.UserRole + 6
    TextRole = Qt.UserRole + 7
    TaskIndexRole = Qt.UserRole + 8
    ColorRole = Qt.UserRole + 9
    TextColorRole = Qt.UserRole + 10
    TaskCompletedRole = Qt.UserRole + 11
    ImageDataRole = Qt.UserRole + 12
    TaskCurrentRole = Qt.UserRole + 13
    SubDiagramPathRole = Qt.UserRole + 14
    SubDiagramProgressRole = Qt.UserRole + 15
    NoteMarkdownRole = Qt.UserRole + 16
    TaskCountdownRemainingRole = Qt.UserRole + 17
    TaskCountdownProgressRole = Qt.UserRole + 18
    TaskCountdownExpiredRole = Qt.UserRole + 19
    TaskCountdownActiveRole = Qt.UserRole + 20

    itemsChanged = Signal()
    edgesChanged = Signal()
    drawingChanged = Signal()
    drawingModeChanged = Signal()
    brushColorChanged = Signal()
    brushWidthChanged = Signal()
    currentTaskChanged = Signal()

    def __init__(self, task_model=None):
        super().__init__()
        self._items: List[DiagramItem] = []
        self._edges: List[DiagramEdge] = []
        self._current_task_index: int = -1
        self._edge_hover_target_id: str = ""
        self._task_model = task_model
        self._id_source = count()
        self._edge_source_id: Optional[str] = None
        self._renaming_in_progress = False

        # Initialize mixins
        self._init_drawing()
        self._init_subdiagram()

        # Connect to task model's signals for bidirectional sync
        if self._task_model is not None:
            self._task_model.taskRenamed.connect(self.onTaskRenamed)
            self._task_model.taskCompletionChanged.connect(self.onTaskCompletionChanged)
            self._task_model.taskCountdownChanged.connect(self.onTaskCountdownChanged)

        self._edge_drag_x: float = 0.0
        self._edge_drag_y: float = 0.0
        self._is_dragging_edge: bool = False

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._id_source)}"

    def _build_item_from_preset(
        self,
        preset_name: str,
        x: float,
        y: float,
        text: Optional[str] = None,
    ) -> Optional[DiagramItem]:
        preset = ITEM_PRESETS.get(preset_name.lower())
        if not preset:
            return None

        label = text if text and text.strip() else preset["text"]
        item_id = self._next_id(preset_name.lower())
        return DiagramItem(
            id=item_id,
            item_type=preset["type"],
            x=x,
            y=y,
            width=float(preset["width"]),
            height=float(preset["height"]),
            text=label,
            color=str(preset["color"]),
            text_color=str(preset["text_color"]),
        )

    def _append_item(self, item: DiagramItem) -> None:
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()
        self.itemsChanged.emit()

    # --- Qt model overrides -------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = self._items[index.row()]
        if role == self.IdRole:
            return item.id
        if role == self.TypeRole:
            return item.item_type.value
        if role == self.XRole:
            return item.x
        if role == self.YRole:
            return item.y
        if role == self.WidthRole:
            return item.width
        if role == self.HeightRole:
            return item.height
        if role == self.TextRole:
            return item.text
        if role == self.TaskIndexRole:
            return item.task_index
        if role == self.ColorRole:
            return item.color
        if role == self.TextColorRole:
            return item.text_color
        if role == self.TaskCompletedRole:
            return self._is_task_completed(item.task_index)
        if role == self.ImageDataRole:
            return item.image_data
        if role == self.TaskCurrentRole:
            return item.task_index >= 0 and item.task_index == self._current_task_index
        if role == self.SubDiagramPathRole:
            return item.sub_diagram_path
        if role == self.SubDiagramProgressRole:
            return self._calculate_sub_diagram_progress(item.sub_diagram_path)
        if role == self.NoteMarkdownRole:
            return item.note_markdown
        if role == self.TaskCountdownRemainingRole:
            return self._getTaskCountdownRemaining(item.task_index)
        if role == self.TaskCountdownProgressRole:
            return self._getTaskCountdownProgress(item.task_index)
        if role == self.TaskCountdownExpiredRole:
            return self._isTaskCountdownExpired(item.task_index)
        if role == self.TaskCountdownActiveRole:
            return self._isTaskCountdownActive(item.task_index)
        return None

    def roleNames(self) -> Dict[int, bytes]:  # type: ignore[override]
        return {
            self.IdRole: b"itemId",
            self.TypeRole: b"itemType",
            self.XRole: b"x",
            self.YRole: b"y",
            self.WidthRole: b"width",
            self.HeightRole: b"height",
            self.TextRole: b"text",
            self.TaskIndexRole: b"taskIndex",
            self.ColorRole: b"color",
            self.TextColorRole: b"textColor",
            self.TaskCompletedRole: b"taskCompleted",
            self.ImageDataRole: b"imageData",
            self.TaskCurrentRole: b"taskCurrent",
            self.SubDiagramPathRole: b"subDiagramPath",
            self.SubDiagramProgressRole: b"subDiagramProgress",
            self.NoteMarkdownRole: b"noteMarkdown",
            self.TaskCountdownRemainingRole: b"taskCountdownRemaining",
            self.TaskCountdownProgressRole: b"taskCountdownProgress",
            self.TaskCountdownExpiredRole: b"taskCountdownExpired",
            self.TaskCountdownActiveRole: b"taskCountdownActive",
        }

    # --- Properties exposed to QML -----------------------------------------
    @Property(list, notify=edgesChanged)
    def edges(self) -> List[Dict[str, str]]:
        return [
            {"id": edge.id, "fromId": edge.from_id, "toId": edge.to_id, "description": edge.description}
            for edge in self._edges
        ]

    @Property(str, notify=itemsChanged)
    def edgeDrawingFrom(self) -> str:
        return self._edge_source_id or ""

    @Property(bool, notify=itemsChanged)
    def isDraggingEdge(self) -> bool:
        return self._is_dragging_edge

    @Property(float, notify=itemsChanged)
    def edgeDragX(self) -> float:
        return self._edge_drag_x

    @Property(float, notify=itemsChanged)
    def edgeDragY(self) -> float:
        return self._edge_drag_y

    @Property(str, notify=itemsChanged)
    def edgeHoverTargetId(self) -> str:
        return self._edge_hover_target_id

    @Property(int, notify=itemsChanged)
    def count(self) -> int:
        return len(self._items)

    @Property(float, notify=itemsChanged)
    def minItemX(self) -> float:
        """Return the leftmost x position of all items."""
        if not self._items:
            return 0.0
        return min(item.x for item in self._items)

    @Property(float, notify=itemsChanged)
    def minItemY(self) -> float:
        """Return the topmost y position of all items."""
        if not self._items:
            return 0.0
        return min(item.y for item in self._items)

    @Property(float, notify=itemsChanged)
    def maxItemX(self) -> float:
        """Return the rightmost edge of all items (x + width)."""
        if not self._items:
            return 0.0
        return max(item.x + item.width for item in self._items)

    @Property(float, notify=itemsChanged)
    def maxItemY(self) -> float:
        """Return the bottommost edge of all items (y + height)."""
        if not self._items:
            return 0.0
        return max(item.y + item.height for item in self._items)

    # --- Drawing properties (from DrawingMixin) ----------------------------
    @Property(bool, notify=drawingModeChanged)
    def drawingMode(self) -> bool:
        return self._get_drawing_mode()

    @drawingMode.setter  # type: ignore[no-redef]
    def drawingMode(self, value: bool) -> None:
        self._set_drawing_mode(value)

    @Property(str, notify=brushColorChanged)
    def brushColor(self) -> str:
        return self._get_brush_color()

    @brushColor.setter  # type: ignore[no-redef]
    def brushColor(self, value: str) -> None:
        self._set_brush_color(value)

    @Property(float, notify=brushWidthChanged)
    def brushWidth(self) -> float:
        return self._get_brush_width()

    @brushWidth.setter  # type: ignore[no-redef]
    def brushWidth(self, value: float) -> None:
        self._set_brush_width(value)

    @Property(list, notify=drawingChanged)
    def strokes(self) -> List[Dict[str, Any]]:
        return self._get_strokes()

    # --- Item management ----------------------------------------------------
    @Slot(float, float, str, result=str)
    def addBox(self, x: float, y: float, text: str = "") -> str:
        item = self._build_item_from_preset("box", x, y, text)
        if not item:
            return ""
        self._append_item(item)
        return item.id

    def _add_preset(self, preset: str, x: float, y: float, text: str = "") -> str:
        item = self._build_item_from_preset(preset, x, y, text)
        if not item:
            return ""
        self._append_item(item)
        return item.id

    @Slot(str, float, float, result=str)
    def addPresetItem(self, preset: str, x: float, y: float) -> str:
        return self._add_preset(preset, x, y, "")

    @Slot(str, float, float, str, result=str)
    def addPresetItemWithText(self, preset: str, x: float, y: float, text: str) -> str:
        return self._add_preset(preset, x, y, text)

    @Slot(str, str, float, float, str, result=str)
    def addPresetItemAndConnect(self, source_id: str, preset: str, x: float, y: float, text: str) -> str:
        """Create a new item of the given preset type and connect it with an edge from source_id."""
        new_id = self._add_preset(preset, x, y, text)
        if new_id and source_id:
            self.addEdge(source_id, new_id)
        return new_id

    @Slot(str, float, float, str, result=str)
    def addTaskFromTextAndConnect(self, source_id: str, x: float, y: float, text: str) -> str:
        """Create a new task in the task list, add it to the diagram, and connect with an edge."""
        new_id = self.addTaskFromText(text, x, y)
        if new_id and source_id:
            self.addEdge(source_id, new_id)
        return new_id

    @Slot(int, float, float, result=str)
    def addTask(self, task_index: int, x: float, y: float) -> str:
        if self._task_model is None:
            return ""
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return ""

        task_idx = self._task_model.index(task_index, 0)
        title = self._task_model.data(task_idx, getattr(self._task_model, "TitleRole", Qt.DisplayRole))
        if title is None:
            title = "Task"

        item_id = f"task_{next(self._id_source)}"
        item = DiagramItem(
            id=item_id,
            item_type=DiagramItemType.TASK,
            x=x,
            y=y,
            text=title,
            task_index=task_index,
            color="#82c3a5",
            text_color="#1b2028" if title else "#f5f6f8",
        )
        self._append_item(item)
        return item_id

    @Slot(str, float, float)
    def moveItem(self, item_id: str, x: float, y: float) -> None:
        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.x == x and item.y == y:
                    return
                item.x = x
                item.y = y
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.XRole, self.YRole])
                self.itemsChanged.emit()
                return

    @Slot(str, str)
    def setItemText(self, item_id: str, text: str) -> None:
        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.text == text:
                    return
                item.text = text
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TextRole])
                self.itemsChanged.emit()
                return

    @Slot(str, str)
    def setItemMarkdown(self, item_id: str, markdown: str) -> None:
        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.note_markdown == markdown:
                    return
                item.note_markdown = markdown
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.NoteMarkdownRole])
                self.itemsChanged.emit()
                return

    @Slot(str, result=str)
    def getItemMarkdown(self, item_id: str) -> str:
        for item in self._items:
            if item.id == item_id:
                return item.note_markdown
        return ""

    @Slot(str, result=bool)
    def openChatGpt(self, item_id: str) -> bool:
        """Open a ChatGPT browser tab with the item's text as the prompt."""
        item = self.getItem(item_id)
        if not item or item.item_type != DiagramItemType.CHATGPT:
            return False
        prompt = item.text.strip() if item.text else ""
        if not prompt:
            prompt = "Research question"
        query = urllib.parse.quote_plus(prompt)
        url = f"https://chatgpt.com/?q={query}"
        return webbrowser.open(url)

    @Slot(str, str)
    def renameTaskItem(self, item_id: str, new_text: str) -> None:
        """Rename a task item and sync to the task list."""
        new_text = new_text.strip()
        if not new_text:
            return
        if self._renaming_in_progress:
            return
        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.text == new_text:
                    return
                item.text = new_text
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TextRole])
                self.itemsChanged.emit()
                # Sync to task model if this is a task item
                if item.task_index >= 0 and self._task_model is not None:
                    self._renaming_in_progress = True
                    try:
                        self._task_model.renameTask(item.task_index, new_text)
                    finally:
                        self._renaming_in_progress = False
                return

    @Slot(int, str)
    def onTaskRenamed(self, task_index: int, new_title: str) -> None:
        """Handle task rename from the task list - update diagram items."""
        if self._renaming_in_progress:
            return
        for row, item in enumerate(self._items):
            if item.task_index == task_index:
                if item.text == new_title:
                    continue
                item.text = new_title
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TextRole])
        self.itemsChanged.emit()

    @Slot(int, bool)
    def onTaskCompletionChanged(self, task_index: int, completed: bool) -> None:
        """Handle task completion updates from the task list."""
        for row, item in enumerate(self._items):
            if item.task_index == task_index:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TaskCompletedRole])

    @Slot(int)
    def onTaskCountdownChanged(self, task_index: int) -> None:
        """Handle countdown timer updates from the task list."""
        for row, item in enumerate(self._items):
            if item.task_index == task_index:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [
                    self.TaskCountdownRemainingRole,
                    self.TaskCountdownProgressRole,
                    self.TaskCountdownExpiredRole,
                    self.TaskCountdownActiveRole
                ])

    def _getTaskCountdownRemaining(self, task_index: int) -> float:
        """Get seconds remaining on task countdown, or -1 if no timer."""
        if self._task_model is None:
            return -1.0
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return -1.0
        idx = self._task_model.index(task_index, 0)
        return float(self._task_model.data(idx, self._task_model.CountdownRemainingRole))

    def _getTaskCountdownProgress(self, task_index: int) -> float:
        """Get countdown progress as 0.0-1.0, or -1 if no timer."""
        if self._task_model is None:
            return -1.0
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return -1.0
        idx = self._task_model.index(task_index, 0)
        return float(self._task_model.data(idx, self._task_model.CountdownProgressRole))

    def _isTaskCountdownExpired(self, task_index: int) -> bool:
        """Return True if task countdown has expired."""
        if self._task_model is None:
            return False
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return False
        idx = self._task_model.index(task_index, 0)
        return bool(self._task_model.data(idx, self._task_model.CountdownExpiredRole))

    def _isTaskCountdownActive(self, task_index: int) -> bool:
        """Return True if task has an active countdown timer."""
        if self._task_model is None:
            return False
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return False
        idx = self._task_model.index(task_index, 0)
        return bool(self._task_model.data(idx, self._task_model.CountdownActiveRole))

    @Slot(int, str)
    def setTaskCountdownTimer(self, task_index: int, duration_str: str) -> None:
        """Set a countdown timer for a task from QML."""
        if self._task_model is not None:
            self._task_model.setCountdownTimer(task_index, duration_str)

    @Slot(int)
    def clearTaskCountdownTimer(self, task_index: int) -> None:
        """Clear the countdown timer for a task from QML."""
        if self._task_model is not None:
            self._task_model.clearCountdownTimer(task_index)

    @Slot(int)
    def restartTaskCountdownTimer(self, task_index: int) -> None:
        """Restart the countdown timer for a task from QML."""
        if self._task_model is not None:
            self._task_model.restartCountdownTimer(task_index)

    @Slot(str, float, float)
    def resizeItem(self, item_id: str, width: float, height: float) -> None:
        new_width = max(40.0, width)
        new_height = max(30.0, height)
        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.width == new_width and item.height == new_height:
                    return
                item.width = new_width
                item.height = new_height
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.WidthRole, self.HeightRole])
                self.itemsChanged.emit()
                return

    @Slot(str, str)
    def addEdge(self, from_id: str, to_id: str) -> None:
        if from_id == to_id:
            return
        for edge in self._edges:
            if edge.from_id == from_id and edge.to_id == to_id:
                return
        edge_id = f"edge_{len(self._edges)}"
        self._edges.append(DiagramEdge(edge_id, from_id, to_id))
        self.edgesChanged.emit()

    @Slot(str)
    def removeEdge(self, edge_id: str) -> None:
        """Remove an edge by its ID."""
        for idx, edge in enumerate(self._edges):
            if edge.id == edge_id:
                self._edges.pop(idx)
                self.edgesChanged.emit()
                return

    @Slot(str, str)
    def removeEdgeBetween(self, from_id: str, to_id: str) -> None:
        """Remove an edge between two items."""
        for idx, edge in enumerate(self._edges):
            if edge.from_id == from_id and edge.to_id == to_id:
                self._edges.pop(idx)
                self.edgesChanged.emit()
                return

    @Slot(str, str)
    def setEdgeDescription(self, edge_id: str, description: str) -> None:
        """Set description text for an edge."""
        for edge in self._edges:
            if edge.id == edge_id:
                if edge.description == description:
                    return
                edge.description = description
                self.edgesChanged.emit()
                return

    @Slot(str, result=str)
    def getEdgeDescription(self, edge_id: str) -> str:
        """Get description text for an edge."""
        for edge in self._edges:
            if edge.id == edge_id:
                return edge.description
        return ""

    @Slot(str)
    def removeItem(self, item_id: str) -> None:
        # Remove edges touching the item
        removed_task_index = -1
        filtered = [edge for edge in self._edges if edge.from_id != item_id and edge.to_id != item_id]
        if len(filtered) != len(self._edges):
            self._edges = filtered
            self.edgesChanged.emit()

        removed = False
        for row, item in enumerate(self._items):
            if item.id == item_id:
                removed_task_index = item.task_index
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                self.itemsChanged.emit()
                removed = True
                break

        # If the removed item was a task, also remove from TaskModel
        if removed_task_index >= 0 and self._task_model is not None:
            self._task_model.removeAt(removed_task_index)
            # Update task indices for all remaining items that referenced tasks after the deleted one
            for row, item in enumerate(self._items):
                if item.task_index > removed_task_index:
                    item.task_index -= 1
                    # Notify UI that this item's task reference changed
                    idx = self.index(row, 0)
                    self.dataChanged.emit(idx, idx, [self.TaskIndexRole])

        if removed and self._edge_source_id == item_id:
            self._reset_edge_state()

    @Slot(str)
    def startEdgeDrawing(self, item_id: str) -> None:
        item = self.getItem(item_id)
        self._edge_source_id = item_id if item else None
        if item:
            self._edge_drag_x = item.x + item.width / 2
            self._edge_drag_y = item.y + item.height / 2
        else:
            self._edge_drag_x = 0.0
            self._edge_drag_y = 0.0
        self._is_dragging_edge = False
        self.itemsChanged.emit()

    @Slot(float, float)
    def updateEdgeDragPosition(self, x: float, y: float) -> None:
        if not self._edge_source_id:
            return
        self._edge_drag_x = x
        self._edge_drag_y = y
        self._is_dragging_edge = True
        # Find hover target with enlarged margin (20px) for easier drops
        hover_id = self.getItemAtWithMargin(x, y, 20.0) or ""
        # Don't hover on source item
        if hover_id == self._edge_source_id:
            hover_id = ""
        self._edge_hover_target_id = hover_id
        self.itemsChanged.emit()

    @Slot(str)
    def finishEdgeDrawing(self, target_id: str) -> None:
        if self._edge_source_id and target_id and self._edge_source_id != target_id:
            self.addEdge(self._edge_source_id, target_id)
        self._reset_edge_state()

    @Slot()
    def cancelEdgeDrawing(self) -> None:
        self._reset_edge_state()

    @Slot(str, str)
    def createTaskFromText(self, text: str, item_id: str) -> None:
        if not self._task_model:
            return
        self._task_model.addTask(text, -1)
        task_count = self._task_model.rowCount()
        if task_count == 0:
            return
        new_index = task_count - 1
        for row, item in enumerate(self._items):
            if item.id == item_id:
                item.task_index = new_index
                item.item_type = DiagramItemType.TASK
                item.color = "#82c3a5"
                item.text = text
                item.text_color = "#1b2028"
                index = self.index(row, 0)
                self.dataChanged.emit(
                    index,
                    index,
                    [
                        self.TaskIndexRole,
                        self.TypeRole,
                        self.ColorRole,
                        self.TextRole,
                        self.TextColorRole,
                    ],
                )
                self.itemsChanged.emit()
                break

    @Slot(str, float, float, result=str)
    def addTaskFromText(self, text: str, x: float, y: float) -> str:
        """Create a new task in the task list and add it to the diagram."""
        text = text.strip()
        if not text or not self._task_model:
            return ""

        # Add to the task model first
        self._task_model.addTask(text, -1)
        task_count = self._task_model.rowCount()
        if task_count == 0:
            return ""

        new_index = task_count - 1

        # Create diagram item for the task
        item_id = self._next_id("task")
        item = DiagramItem(
            id=item_id,
            item_type=DiagramItemType.TASK,
            x=x,
            y=y,
            width=140.0,
            height=70.0,
            text=text,
            task_index=new_index,
            color="#82c3a5",
            text_color="#1b2028",
        )
        self._append_item(item)
        return item_id

    @Slot(int, bool)
    def setTaskCompleted(self, task_index: int, completed: bool) -> None:
        """Set a task's completion state via the task model."""
        if self._task_model is None:
            return
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return
        self._task_model.toggleComplete(task_index, completed)

    @Slot(int)
    def setCurrentTask(self, task_index: int) -> None:
        """Set the current (focused) task, clearing any previous."""
        old_index = self._current_task_index
        # Toggle off if same task
        if task_index == old_index:
            self._current_task_index = -1
        else:
            self._current_task_index = task_index
        self.currentTaskChanged.emit()
        # Notify all task items that their current state may have changed
        for row, item in enumerate(self._items):
            if item.task_index >= 0 and (item.task_index == old_index or item.task_index == self._current_task_index):
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TaskCurrentRole])

    @Property(int, notify=currentTaskChanged)
    def currentTaskIndex(self) -> int:
        """Return the currently focused task index, or -1 if none."""
        return self._current_task_index

    # --- Utilities ----------------------------------------------------------
    def getItem(self, item_id: str) -> Optional[DiagramItem]:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def _is_task_completed(self, task_index: int) -> bool:
        if self._task_model is None:
            return False
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return False
        idx = self._task_model.index(task_index, 0)
        return bool(self._task_model.data(idx, self._task_model.CompletedRole))

    @Slot(str, result="QVariant")
    def getItemSnapshot(self, item_id: str) -> Dict[str, Any]:
        item = self.getItem(item_id)
        if not item:
            return {}
        return {
            "id": item.id,
            "type": item.item_type.value,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "height": item.height,
            "text": item.text,
            "subDiagramPath": item.sub_diagram_path,
        }

    def getItemAt(self, x: float, y: float) -> Optional[str]:
        for item in reversed(self._items):
            if item.x <= x <= item.x + item.width and item.y <= y <= item.y + item.height:
                return item.id
        return None

    def getItemAtWithMargin(self, x: float, y: float, margin: float) -> Optional[str]:
        """Find item at position with enlarged hit area.

        Args:
            x: X coordinate in diagram space.
            y: Y coordinate in diagram space.
            margin: Extra pixels to extend hit area on each side.

        Returns:
            Item ID if found, None otherwise.
        """
        for item in reversed(self._items):
            if (item.x - margin <= x <= item.x + item.width + margin and
                    item.y - margin <= y <= item.y + item.height + margin):
                return item.id
        return None

    @Slot(float, float, result=str)
    def itemIdAt(self, x: float, y: float) -> str:
        return self.getItemAt(x, y) or ""

    @Slot()
    def connectAllItems(self) -> None:
        if len(self._items) < 2:
            return
        ordered = sorted(self._items, key=lambda item: (item.y, item.x))
        for idx in range(len(ordered) - 1):
            self.addEdge(ordered[idx].id, ordered[idx + 1].id)

    def _reset_edge_state(self) -> None:
        changed = self._edge_source_id is not None or self._is_dragging_edge
        self._edge_source_id = None
        self._edge_drag_x = 0.0
        self._edge_drag_y = 0.0
        self._is_dragging_edge = False
        self._edge_hover_target_id = ""
        if changed:
            self.itemsChanged.emit()

    # --- Serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialize diagram to a dictionary for saving.

        Returns:
            Dictionary containing all diagram item and edge data.
        """
        items_data = []
        for item in self._items:
            item_dict = {
                "id": item.id,
                "item_type": item.item_type.value,
                "x": item.x,
                "y": item.y,
                "width": item.width,
                "height": item.height,
                "text": item.text,
                "task_index": item.task_index,
                "color": item.color,
                "text_color": item.text_color,
            }
            # Only store image_data if it's an image item (to avoid bloating files)
            if item.item_type == DiagramItemType.IMAGE and item.image_data:
                item_dict["image_data"] = item.image_data
            # Only store sub_diagram_path if set
            if item.sub_diagram_path:
                item_dict["sub_diagram_path"] = item.sub_diagram_path
            if item.note_markdown:
                item_dict["note_markdown"] = item.note_markdown
            items_data.append(item_dict)

        edges_data = []
        for edge in self._edges:
            edges_data.append({
                "id": edge.id,
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "description": edge.description,
            })

        strokes_data = []
        for stroke in self._strokes:
            strokes_data.append({
                "id": stroke.id,
                "color": stroke.color,
                "width": stroke.width,
                "points": [{"x": pt.x, "y": pt.y} for pt in stroke.points],
            })

        return {
            "items": items_data,
            "edges": edges_data,
            "strokes": strokes_data,
            "current_task_index": self._current_task_index,
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load diagram from a dictionary.

        Args:
            data: Dictionary containing diagram data (from to_dict).
        """
        # Set current task index up front so new items render with correct state.
        self._current_task_index = int(data.get("current_task_index", -1))

        # Clear existing items, edges, and strokes
        if self._items:
            self.beginRemoveRows(QModelIndex(), 0, len(self._items) - 1)
            self._items.clear()
            self.endRemoveRows()
        self._edges.clear()
        self._strokes.clear()
        self._current_stroke = None

        # Track highest ID number to resume ID generation
        max_id = 0

        # Load items with batch insertion
        items_data = data.get("items", [])
        if items_data:
            new_items = []
            for item_data in items_data:
                item_id = item_data.get("id", "")
                # Extract numeric part from item ID to track max
                try:
                    id_parts = item_id.rsplit("_", 1)
                    if len(id_parts) == 2:
                        max_id = max(max_id, int(id_parts[1]) + 1)
                except (ValueError, IndexError):
                    pass

                item_type_str = item_data.get("item_type", "box")
                try:
                    item_type = DiagramItemType(item_type_str)
                except ValueError:
                    item_type = DiagramItemType.BOX

                item = DiagramItem(
                    id=item_id,
                    item_type=item_type,
                    x=float(item_data.get("x", 0.0)),
                    y=float(item_data.get("y", 0.0)),
                    width=float(item_data.get("width", 120.0)),
                    height=float(item_data.get("height", 60.0)),
                    text=item_data.get("text", ""),
                    task_index=int(item_data.get("task_index", -1)),
                    color=item_data.get("color", "#4a9eff"),
                    text_color=item_data.get("text_color", "#f5f6f8"),
                    image_data=item_data.get("image_data", ""),
                    sub_diagram_path=item_data.get("sub_diagram_path", ""),
                    note_markdown=item_data.get("note_markdown", ""),
                )
                new_items.append(item)

            # Batch insert all items at once
            self.beginInsertRows(QModelIndex(), 0, len(new_items) - 1)
            self._items.extend(new_items)
            self.endInsertRows()

        # Update ID source to avoid collisions
        self._id_source = count(max_id)

        # Load edges
        edges_data = data.get("edges", [])
        for edge_data in edges_data:
            edge = DiagramEdge(
                id=edge_data.get("id", ""),
                from_id=edge_data.get("from_id", ""),
                to_id=edge_data.get("to_id", ""),
                description=edge_data.get("description", ""),
            )
            self._edges.append(edge)

        # Load strokes
        self._strokes.clear()
        max_stroke_id = 0
        strokes_data = data.get("strokes", [])
        for stroke_data in strokes_data:
            stroke_id = stroke_data.get("id", "")
            # Track max stroke ID
            try:
                id_parts = stroke_id.rsplit("_", 1)
                if len(id_parts) == 2:
                    max_stroke_id = max(max_stroke_id, int(id_parts[1]) + 1)
            except (ValueError, IndexError):
                pass

            points = []
            for pt_data in stroke_data.get("points", []):
                points.append(DrawingPoint(
                    x=float(pt_data.get("x", 0.0)),
                    y=float(pt_data.get("y", 0.0)),
                ))

            stroke = DrawingStroke(
                id=stroke_id,
                points=points,
                color=stroke_data.get("color", "#ffffff"),
                width=float(stroke_data.get("width", 3.0)),
            )
            self._strokes.append(stroke)

        self._stroke_id_source = count(max_stroke_id)

        self.itemsChanged.emit()
        self.edgesChanged.emit()
        self.drawingChanged.emit()
        self.currentTaskChanged.emit()

        # Update file watcher for sub-diagrams
        self._update_sub_diagram_watches()
