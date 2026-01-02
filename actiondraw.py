"""ActionDraw diagramming module built with PySide6 and QML.

The implementation focuses on predictable coordinate handling so drawing
connections between items works reliably when dragging across the canvas.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
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
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication


class DiagramItemType(Enum):
    """Supported diagram item types."""

    BOX = "box"
    TASK = "task"
    DATABASE = "database"
    SERVER = "server"
    CLOUD = "cloud"
    NOTE = "note"
    FREETEXT = "freetext"
    OBSTACLE = "obstacle"
    WISH = "wish"


@dataclass
class DiagramItem:
    """A rectangular shape displayed on the canvas."""

    id: str
    item_type: DiagramItemType
    x: float
    y: float
    width: float = 120.0
    height: float = 60.0
    text: str = ""
    task_index: int = -1
    color: str = "#4a9eff"
    text_color: str = "#f5f6f8"


@dataclass
class DiagramEdge:
    """A directed connection between two diagram items."""

    id: str
    from_id: str
    to_id: str
    description: str = ""


@dataclass
class DrawingPoint:
    """A single point in a drawing stroke."""

    x: float
    y: float


@dataclass
class DrawingStroke:
    """A freehand drawing stroke on the canvas."""

    id: str
    points: List[DrawingPoint]
    color: str = "#ffffff"
    width: float = 3.0


ITEM_PRESETS: Dict[str, Dict[str, Any]] = {
    "box": {
        "type": DiagramItemType.BOX,
        "width": 120.0,
        "height": 60.0,
        "color": "#4a9eff",
        "text": "Box",
        "text_color": "#f5f6f8",
    },
    "database": {
        "type": DiagramItemType.DATABASE,
        "width": 160.0,
        "height": 90.0,
        "color": "#c18f5e",
        "text": "Database",
        "text_color": "#1b2028",
    },
    "server": {
        "type": DiagramItemType.SERVER,
        "width": 150.0,
        "height": 90.0,
        "color": "#3d495c",
        "text": "Server",
        "text_color": "#f5f6f8",
    },
    "cloud": {
        "type": DiagramItemType.CLOUD,
        "width": 170.0,
        "height": 100.0,
        "color": "#6a9ddb",
        "text": "Cloud",
        "text_color": "#1b2028",
    },
    "note": {
        "type": DiagramItemType.NOTE,
        "width": 160.0,
        "height": 110.0,
        "color": "#f7e07b",
        "text": "Note",
        "text_color": "#1b2028",
    },
    "freetext": {
        "type": DiagramItemType.FREETEXT,
        "width": 200.0,
        "height": 140.0,
        "color": "#f5f0e6",
        "text": "",
        "text_color": "#2d3436",
    },
    "obstacle": {
        "type": DiagramItemType.OBSTACLE,
        "width": 140.0,
        "height": 100.0,
        "color": "#e74c3c",
        "text": "Obstacle",
        "text_color": "#ffffff",
    },
    "wish": {
        "type": DiagramItemType.WISH,
        "width": 140.0,
        "height": 100.0,
        "color": "#f1c40f",
        "text": "Wish",
        "text_color": "#2d3436",
    },
}


class DiagramModel(QAbstractListModel):
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

    itemsChanged = Signal()
    edgesChanged = Signal()
    drawingChanged = Signal()
    drawingModeChanged = Signal()
    brushColorChanged = Signal()
    brushWidthChanged = Signal()

    def __init__(self, task_model=None):
        super().__init__()
        self._items: List[DiagramItem] = []
        self._edges: List[DiagramEdge] = []
        self._strokes: List[DrawingStroke] = []
        self._edge_hover_target_id: str = ""
        self._stroke_id_source = count()
        self._drawing_mode: bool = False
        self._brush_color: str = "#ffffff"
        self._brush_width: float = 3.0
        self._current_stroke: Optional[DrawingStroke] = None
        self._task_model = task_model
        self._id_source = count()
        self._edge_source_id: Optional[str] = None
        self._renaming_in_progress = False  # Flag to prevent re-entrant rename calls
        
        # Connect to task model's taskRenamed signal for bidirectional sync
        if self._task_model is not None:
            self._task_model.taskRenamed.connect(self.onTaskRenamed)
            self._task_model.taskCompletionChanged.connect(self.onTaskCompletionChanged)
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

    # --- Drawing properties exposed to QML ---------------------------------
    @Property(bool, notify=drawingModeChanged)
    def drawingMode(self) -> bool:
        return self._drawing_mode

    @drawingMode.setter  # type: ignore[no-redef]
    def drawingMode(self, value: bool) -> None:
        if self._drawing_mode != value:
            self._drawing_mode = value
            self.drawingModeChanged.emit()

    @Slot(bool)
    def setDrawingMode(self, enabled: bool) -> None:
        self.drawingMode = enabled

    @Property(str, notify=brushColorChanged)
    def brushColor(self) -> str:
        return self._brush_color

    @brushColor.setter  # type: ignore[no-redef]
    def brushColor(self, value: str) -> None:
        if self._brush_color != value:
            self._brush_color = value
            self.brushColorChanged.emit()

    @Slot(str)
    def setBrushColor(self, color: str) -> None:
        self.brushColor = color

    @Property(float, notify=brushWidthChanged)
    def brushWidth(self) -> float:
        return self._brush_width

    @brushWidth.setter  # type: ignore[no-redef]
    def brushWidth(self, value: float) -> None:
        clamped = max(1.0, min(50.0, value))
        if self._brush_width != clamped:
            self._brush_width = clamped
            self.brushWidthChanged.emit()

    @Slot(float)
    def setBrushWidth(self, width: float) -> None:
        self.brushWidth = width

    @Property(list, notify=drawingChanged)
    def strokes(self) -> List[Dict[str, Any]]:
        """Return all strokes as a list of dicts for QML consumption."""
        result = []
        for stroke in self._strokes:
            result.append({
                "id": stroke.id,
                "color": stroke.color,
                "width": stroke.width,
                "points": [{"x": pt.x, "y": pt.y} for pt in stroke.points],
            })
        return result

    # --- Drawing operations -------------------------------------------------
    @Slot(float, float)
    def startStroke(self, x: float, y: float) -> None:
        """Begin a new drawing stroke at the given position."""
        stroke_id = f"stroke_{next(self._stroke_id_source)}"
        self._current_stroke = DrawingStroke(
            id=stroke_id,
            points=[DrawingPoint(x, y)],
            color=self._brush_color,
            width=self._brush_width,
        )
        self.drawingChanged.emit()

    @Slot(float, float)
    def continueStroke(self, x: float, y: float) -> None:
        """Add a point to the current stroke."""
        if self._current_stroke is not None:
            self._current_stroke.points.append(DrawingPoint(x, y))
            self.drawingChanged.emit()

    @Slot()
    def endStroke(self) -> None:
        """Finish the current stroke and add it to the strokes list."""
        if self._current_stroke is not None and len(self._current_stroke.points) >= 2:
            self._strokes.append(self._current_stroke)
        self._current_stroke = None
        self.drawingChanged.emit()

    @Slot(result="QVariant")
    def getCurrentStroke(self) -> Dict[str, Any]:
        """Return current stroke being drawn, or empty dict."""
        if self._current_stroke is None:
            return {}
        return {
            "id": self._current_stroke.id,
            "color": self._current_stroke.color,
            "width": self._current_stroke.width,
            "points": [{"x": pt.x, "y": pt.y} for pt in self._current_stroke.points],
        }

    @Slot()
    def clearStrokes(self) -> None:
        """Remove all drawing strokes."""
        self._strokes.clear()
        self._current_stroke = None
        self.drawingChanged.emit()

    @Slot()
    def undoLastStroke(self) -> None:
        """Remove the most recent stroke."""
        if self._strokes:
            self._strokes.pop()
            self.drawingChanged.emit()

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
        removed = False
        filtered = [edge for edge in self._edges if edge.from_id != item_id and edge.to_id != item_id]
        if len(filtered) != len(self._edges):
            self._edges = filtered
            self.edgesChanged.emit()

        for row, item in enumerate(self._items):
            if item.id == item_id:
                self.beginRemoveRows(QModelIndex(), row, row)
                self._items.pop(row)
                self.endRemoveRows()
                self.itemsChanged.emit()
                removed = True
                break

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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize diagram to a dictionary for saving.

        Returns:
            Dictionary containing all diagram item and edge data.
        """
        items_data = []
        for item in self._items:
            items_data.append({
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
            })

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
        }

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load diagram from a dictionary.

        Args:
            data: Dictionary containing diagram data (from to_dict).
        """
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

        # Load items
        items_data = data.get("items", [])
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
            )
            self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
            self._items.append(item)
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


ACTIONDRAW_QML = r"""
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
ApplicationWindow {
    id: root
    visible: false
    width: 960
    height: 700
    color: "#10141c"
    title: "ActionDraw"

    menuBar: MenuBar {
        Menu {
            title: "File"

            MenuItem {
                text: "Close"
                onTriggered: root.close()
            }
        }

        Menu {
            title: "Edit"

            MenuItem {
                text: "Clear All Items"
                onTriggered: {
                    if (!diagramModel) return
                    for (var i = diagramModel.count - 1; i >= 0; --i) {
                        var idx = diagramModel.index(i, 0)
                        var itemId = diagramModel.data(idx, diagramModel.IdRole)
                        diagramModel.removeItem(itemId)
                    }
                    root.resetView()
                }
            }

            MenuItem {
                text: "Clear Drawings"
                onTriggered: diagramModel && diagramModel.clearStrokes()
            }

            MenuSeparator {}

            MenuItem {
                text: "Undo Drawing"
                onTriggered: diagramModel && diagramModel.undoLastStroke()
            }
        }

        Menu {
            title: "Insert"

            MenuItem {
                text: "Box"
                onTriggered: root.addPresetAtCenter("box")
            }

            MenuItem {
                text: "Database"
                onTriggered: root.addPresetAtCenter("database")
            }

            MenuItem {
                text: "Server"
                onTriggered: root.addPresetAtCenter("server")
            }

            MenuItem {
                text: "Cloud"
                onTriggered: root.addPresetAtCenter("cloud")
            }

            MenuItem {
                text: "Note"
                onTriggered: root.addPresetAtCenter("note")
            }

            MenuItem {
                text: "Obstacle"
                onTriggered: root.addPresetAtCenter("obstacle")
            }

            MenuItem {
                text: "Wish"
                onTriggered: root.addPresetAtCenter("wish")
            }

            MenuSeparator {}

            MenuItem {
                text: "Task from List..."
                enabled: taskModel !== null
                onTriggered: {
                    if (!taskModel) return
                    var center = root.diagramCenterPoint()
                    taskDialog.targetX = center.x
                    taskDialog.targetY = center.y
                    taskDialog.open()
                }
            }

            MenuItem {
                text: "New Task..."
                enabled: diagramModel !== null
                onTriggered: root.addQuickTaskAtCenter()
            }
        }

        Menu {
            title: "View"

            MenuItem {
                text: "Show Grid"
                checkable: true
                checked: root.showGrid
                onTriggered: root.showGrid = checked
            }

            MenuItem {
                text: "Snap to Grid"
                checkable: true
                checked: root.snapToGrid
                onTriggered: root.snapToGrid = checked
            }

            MenuSeparator {}

            MenuItem {
                text: "Zoom In"
                onTriggered: root.applyZoomFactor(1.2, viewport.width / 2, viewport.height / 2)
            }

            MenuItem {
                text: "Zoom Out"
                onTriggered: root.applyZoomFactor(0.8, viewport.width / 2, viewport.height / 2)
            }

            MenuItem {
                text: "Reset View"
                onTriggered: root.resetView()
            }
        }

        Menu {
            title: "Tools"

            MenuItem {
                text: "Connect All Items"
                onTriggered: diagramModel && diagramModel.connectAllItems()
            }

            MenuSeparator {}

            MenuItem {
                id: drawingModeMenuItem
                text: diagramModel && diagramModel.drawingMode ? "Exit Drawing Mode" : "Drawing Mode"
                checkable: true
                checked: diagramModel && diagramModel.drawingMode
                onTriggered: diagramModel && diagramModel.setDrawingMode(checked)
            }
        }
    }

    function showWindow() {
        root.visible = true
        root.requestActivate()
    }

    property int boardSize: 2000
    property bool showGrid: true
    property bool snapToGrid: true
    property real gridSpacing: 60
    property real zoomLevel: 1.0
    property real minZoom: 0.4
    property real maxZoom: 2.5
    readonly property var presetDefaults: ({
        "box": { "text": "Box", "title": "Create Box" },
        "database": { "text": "Database", "title": "Create Database" },
        "server": { "text": "Server", "title": "Create Server" },
        "cloud": { "text": "Cloud", "title": "Create Cloud" },
        "note": { "text": "Note", "title": "Create Note" },
        "freetext": { "text": "", "title": "Free Text" },
        "obstacle": { "text": "Obstacle", "title": "Add Obstacle" },
        "wish": { "text": "Wish", "title": "Add Wish" }
    })

    // Pending edge drop state (for creating new items when dropping into empty space)
    property string pendingEdgeSourceId: ""
    property real pendingEdgeDropX: 0
    property real pendingEdgeDropY: 0

    function showEdgeDropSuggestions(sourceId, dropX, dropY) {
        root.pendingEdgeSourceId = sourceId
        root.pendingEdgeDropX = dropX
        root.pendingEdgeDropY = dropY
        edgeDropMenu.popup()
    }

    function clampZoom(value) {
        if (value < root.minZoom)
            return root.minZoom
        if (value > root.maxZoom)
            return root.maxZoom
        return value
    }

    function snapValue(value) {
        if (!root.snapToGrid)
            return value
        return Math.round(value / root.gridSpacing) * root.gridSpacing
    }

    function snapPoint(point) {
        return Qt.point(snapValue(point.x), snapValue(point.y))
    }

    function diagramCenterPoint() {
        var cx = (viewport.contentX + viewport.width / 2) / root.zoomLevel
        var cy = (viewport.contentY + viewport.height / 2) / root.zoomLevel
        return snapPoint(Qt.point(cx, cy))
    }

    function openPresetDialog(preset, point, itemId, initialText) {
        if (!root.presetDefaults[preset])
            preset = "box"
        var defaults = root.presetDefaults[preset]
        boxDialog.editingItemId = itemId || ""
        boxDialog.presetName = preset
        boxDialog.targetX = snapValue(point.x)
        boxDialog.targetY = snapValue(point.y)
        boxDialog.textValue = initialText !== undefined ? initialText : (defaults && defaults.text ? defaults.text : "")
        boxDialog.open()
    }

    function addPresetAtCenter(preset) {
        openPresetDialog(preset, diagramCenterPoint(), "", undefined)
    }

    function addBoxAtCenter() {
        addPresetAtCenter("box")
    }

    function presetTitle(preset) {
        var defaults = root.presetDefaults[preset]
        if (defaults && defaults.title)
            return defaults.title
        return "Create Item"
    }

    function openFreeTextDialog(point, itemId, initialText) {
        freeTextDialog.editingItemId = itemId || ""
        freeTextDialog.targetX = snapValue(point.x)
        freeTextDialog.targetY = snapValue(point.y)
        freeTextDialog.textValue = initialText !== undefined ? initialText : ""
        freeTextDialog.open()
    }

    function setZoomInternal(newZoom, focusX, focusY) {
        var clamped = clampZoom(newZoom)
        if (Math.abs(clamped - root.zoomLevel) < 0.0001)
            return
        var fx = focusX === undefined ? viewport.width / 2 : focusX
        var fy = focusY === undefined ? viewport.height / 2 : focusY
        var focusContentX = viewport.contentX + fx
        var focusContentY = viewport.contentY + fy
        var focusDiagramX = focusContentX / root.zoomLevel
        var focusDiagramY = focusContentY / root.zoomLevel
        root.zoomLevel = clamped
        var newContentX = focusDiagramX * root.zoomLevel - fx
        var newContentY = focusDiagramY * root.zoomLevel - fy
        var maxX = Math.max(0, viewport.contentWidth - viewport.width)
        var maxY = Math.max(0, viewport.contentHeight - viewport.height)
        viewport.contentX = Math.min(Math.max(newContentX, 0), maxX)
        viewport.contentY = Math.min(Math.max(newContentY, 0), maxY)
        if (gridCanvas)
            gridCanvas.requestPaint()
        if (edgeCanvas)
            edgeCanvas.requestPaint()
    }

    function applyZoomFactor(factor, focusX, focusY) {
        setZoomInternal(root.zoomLevel * factor, focusX, focusY)
    }

    function setZoomDirect(value, focusX, focusY) {
        setZoomInternal(value, focusX, focusY)
    }

    function centerOnPoint(x, y) {
        var targetX = x * root.zoomLevel - viewport.width / 2
        var targetY = y * root.zoomLevel - viewport.height / 2
        var maxX = Math.max(0, viewport.contentWidth - viewport.width)
        var maxY = Math.max(0, viewport.contentHeight - viewport.height)
        viewport.contentX = Math.min(Math.max(targetX, 0), maxX)
        viewport.contentY = Math.min(Math.max(targetY, 0), maxY)
    }

    function resetView() {
        setZoomInternal(1.0)
        centerOnPoint(root.boardSize / 2, root.boardSize / 2)
    }

    Dialog {
        id: addDialog
        modal: true
        title: "Add to Diagram"
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Button {
                text: "Box"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("box", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Database"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("database", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Server"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("server", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Cloud"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("cloud", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Note"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("note", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Obstacle"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("obstacle", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Wish"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("wish", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Task from List"
                enabled: taskModel && taskModel.taskCount > 0
                onClicked: {
                    addDialog.close()
                    if (taskModel) {
                        taskDialog.targetX = snapValue(addDialog.targetX)
                        taskDialog.targetY = snapValue(addDialog.targetY)
                        taskDialog.open()
                    }
                }
            }

            Button {
                text: "New Task (freetext)"
                enabled: diagramModel !== null
                onClicked: {
                    addDialog.close()
                    root.openQuickTaskDialog(Qt.point(addDialog.targetX, addDialog.targetY))
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Cancel
            onRejected: addDialog.close()
        }
    }

    Dialog {
        id: boxDialog
        modal: true
        property real targetX: 0
        property real targetY: 0
        property string editingItemId: ""
        property string textValue: ""
        property string presetName: "box"
        title: boxDialog.editingItemId.length === 0 ? root.presetTitle(boxDialog.presetName) : "Edit Label"

        onOpened: boxTextField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: boxTextField
                Layout.fillWidth: true
                text: boxDialog.textValue
                placeholderText: "Label"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: boxDialog.textValue = text
                Keys.onReturnPressed: boxDialog.accept()
                Keys.onEnterPressed: boxDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: boxDialogButtonBox
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (!diagramModel)
                return
            if (boxDialog.editingItemId.length === 0) {
                diagramModel.addPresetItemWithText(
                    boxDialog.presetName,
                    snapValue(boxDialog.targetX),
                    snapValue(boxDialog.targetY),
                    boxDialog.textValue
                )
            } else {
                diagramModel.setItemText(boxDialog.editingItemId, boxDialog.textValue)
            }
            boxDialog.close()
        }
        onRejected: boxDialog.close()

        onClosed: {
            boxDialog.textValue = ""
            boxDialog.editingItemId = ""
            boxDialog.presetName = "box"
        }
    }

    Dialog {
        id: freeTextDialog
        modal: true
        property real targetX: 0
        property real targetY: 0
        property string editingItemId: ""
        property string textValue: ""
        title: freeTextDialog.editingItemId.length === 0 ? "Free Text" : "Edit Free Text"

        onOpened: freeTextArea.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 360
            spacing: 12

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 160

                TextArea {
                    id: freeTextArea
                    text: freeTextDialog.textValue
                    placeholderText: "Write your text here..."
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    color: "#f5f6f8"
                    font.pixelSize: 14
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 6
                        border.color: "#384458"
                    }
                    onTextChanged: freeTextDialog.textValue = text
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (!diagramModel)
                return
            if (freeTextDialog.editingItemId.length === 0) {
                diagramModel.addPresetItemWithText(
                    "freetext",
                    snapValue(freeTextDialog.targetX),
                    snapValue(freeTextDialog.targetY),
                    freeTextDialog.textValue
                )
            } else {
                diagramModel.setItemText(freeTextDialog.editingItemId, freeTextDialog.textValue)
            }
            freeTextDialog.close()
        }
        onRejected: freeTextDialog.close()

        onClosed: {
            freeTextDialog.textValue = ""
            freeTextDialog.editingItemId = ""
        }
    }

    Dialog {
        id: edgeDescriptionDialog
        modal: true
        title: "Edge Description"
        property string edgeId: ""
        property string descriptionValue: ""

        function openWithEdge(eId) {
            edgeId = eId
            descriptionValue = diagramModel ? diagramModel.getEdgeDescription(eId) : ""
            open()
        }

        onOpened: edgeDescriptionField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: edgeDescriptionField
                Layout.fillWidth: true
                text: edgeDescriptionDialog.descriptionValue
                placeholderText: "Description (optional)"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: edgeDescriptionDialog.descriptionValue = text
                Keys.onReturnPressed: edgeDescriptionDialog.accept()
                Keys.onEnterPressed: edgeDescriptionDialog.accept()
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && edgeDescriptionDialog.edgeId.length > 0) {
                diagramModel.setEdgeDescription(edgeDescriptionDialog.edgeId, edgeDescriptionDialog.descriptionValue)
            }
            close()
        }
        onRejected: close()

        onClosed: {
            edgeDescriptionDialog.edgeId = ""
            edgeDescriptionDialog.descriptionValue = ""
        }
    }

    Dialog {
        id: taskDialog
        modal: true
        title: "Add Task"
        width: 450
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            spacing: 12

            ListView {
                id: taskListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 420
                Layout.preferredHeight: 320
                model: taskModel
                clip: true

                delegate: Item {
                    width: taskListView.width
                    height: Math.max(40, taskText.implicitHeight + 16)

                    Rectangle {
                        anchors.fill: parent
                        color: mouseArea.containsMouse ? "#283346" : "#1a2230"
                        border.color: "#30405a"
                    }

                    Text {
                        id: taskText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 12
                        text: model.title
                        color: "#f5f6f8"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    MouseArea {
                        id: mouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (diagramModel) {
                                diagramModel.addTask(
                                    index,
                                    snapValue(taskDialog.targetX),
                                    snapValue(taskDialog.targetY)
                                )
                            }
                            taskDialog.close()
                        }
                    }
                }
            }

            Label {
                text: taskModel ? "No tasks available. Add tasks in Progress Tracker." : "Task list unavailable. Open ActionDraw from the task app."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
                visible: !taskModel || taskListView.count === 0
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Cancel
            onRejected: taskDialog.close()
        }
    }

    Dialog {
        id: newTaskDialog
        modal: true
        title: "Create Task"
        property string pendingItemId: ""
        property string textValue: ""

        function openWithItem(itemId, text) {
            pendingItemId = itemId
            textValue = text
            open()
        }

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: newTaskField
                Layout.fillWidth: true
                text: newTaskDialog.textValue
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: newTaskDialog.textValue = text
                onAccepted: newTaskButtons.accept()
            }
        }

        footer: DialogButtonBox {
            id: newTaskButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
            onAccepted: {
                if (diagramModel && newTaskDialog.pendingItemId.length > 0) {
                    diagramModel.createTaskFromText(newTaskDialog.textValue, newTaskDialog.pendingItemId)
                }
                newTaskDialog.close()
            }
            onRejected: newTaskDialog.close()
        }

        onClosed: {
            newTaskDialog.pendingItemId = ""
            newTaskDialog.textValue = ""
        }
    }

    Dialog {
        id: quickTaskDialog
        modal: true
        title: "New Task"
        property real targetX: 0
        property real targetY: 0

        onOpened: quickTaskField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: "Create a new task that will be added to both the diagram and your Progress List."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: quickTaskField
                Layout.fillWidth: true
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                Keys.onReturnPressed: quickTaskDialog.accept()
                Keys.onEnterPressed: quickTaskDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: quickTaskButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && quickTaskField.text.trim().length > 0) {
                diagramModel.addTaskFromText(
                    quickTaskField.text,
                    snapValue(quickTaskDialog.targetX),
                    snapValue(quickTaskDialog.targetY)
                )
            }
            quickTaskDialog.close()
        }
        onRejected: quickTaskDialog.close()

        onClosed: {
            quickTaskField.text = ""
        }
    }

    Dialog {
        id: taskRenameDialog
        modal: true
        title: "Rename Task"
        property string editingItemId: ""
        property string textValue: ""

        onOpened: taskRenameField.forceActiveFocus()

        function openWithItem(itemId, text) {
            editingItemId = itemId
            textValue = text
            open()
        }

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: "Rename this task. Changes will be synced to the Progress List."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: taskRenameField
                Layout.fillWidth: true
                text: taskRenameDialog.textValue
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: taskRenameDialog.textValue = text
                onAccepted: taskRenameButtons.accept()
            }
        }

        footer: DialogButtonBox {
            id: taskRenameButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
            onAccepted: {
                if (diagramModel && taskRenameDialog.editingItemId.length > 0 && taskRenameDialog.textValue.trim().length > 0) {
                    diagramModel.renameTaskItem(taskRenameDialog.editingItemId, taskRenameDialog.textValue)
                }
                taskRenameDialog.close()
            }
            onRejected: taskRenameDialog.close()
        }

        onClosed: {
            taskRenameDialog.editingItemId = ""
            taskRenameDialog.textValue = ""
        }
    }

    function openQuickTaskDialog(point) {
        quickTaskDialog.targetX = point.x
        quickTaskDialog.targetY = point.y
        quickTaskDialog.open()
    }

    function addQuickTaskAtCenter() {
        openQuickTaskDialog(diagramCenterPoint())
    }

    Menu {
        id: edgeDropMenu
        title: "Create & Connect"

        MenuItem {
            text: "→ Task"
            onTriggered: {
                // Copy pending state to dialog before menu closes
                edgeDropTaskDialog.sourceId = root.pendingEdgeSourceId
                edgeDropTaskDialog.dropX = root.pendingEdgeDropX
                edgeDropTaskDialog.dropY = root.pendingEdgeDropY
                edgeDropTaskDialog.open()
            }
        }

        MenuItem {
            text: "→ Obstacle"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "obstacle",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Obstacle"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "→ Wish"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "wish",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Wish"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "→ Box"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "box",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Box"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "→ Note"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "note",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Note"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "→ Database"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "database",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Database"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "→ Server"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "server",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Server"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "→ Cloud"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "cloud",
                        snapValue(root.pendingEdgeDropX),
                        snapValue(root.pendingEdgeDropY),
                        "Cloud"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        onClosed: {
            // Clear pending state if menu closed without action
            root.pendingEdgeSourceId = ""
        }
    }

    Dialog {
        id: edgeDropTaskDialog
        modal: true
        title: "Create Connected Task"

        // Store our own copy of pending state (menu clears root state on close)
        property string sourceId: ""
        property real dropX: 0
        property real dropY: 0

        onOpened: edgeDropTaskField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: taskModel ? "Create a new task connected from the source item." : "Create a box connected from the source item (no task list available)."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: edgeDropTaskField
                Layout.fillWidth: true
                placeholderText: taskModel ? "Task name" : "Box label"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                Keys.onReturnPressed: edgeDropTaskDialog.accept()
                Keys.onEnterPressed: edgeDropTaskDialog.accept()
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && edgeDropTaskDialog.sourceId && edgeDropTaskField.text.trim().length > 0) {
                if (taskModel) {
                    diagramModel.addTaskFromTextAndConnect(
                        edgeDropTaskDialog.sourceId,
                        snapValue(edgeDropTaskDialog.dropX),
                        snapValue(edgeDropTaskDialog.dropY),
                        edgeDropTaskField.text
                    )
                } else {
                    // Fallback to box when no task model
                    diagramModel.addPresetItemAndConnect(
                        edgeDropTaskDialog.sourceId,
                        "box",
                        snapValue(edgeDropTaskDialog.dropX),
                        snapValue(edgeDropTaskDialog.dropY),
                        edgeDropTaskField.text
                    )
                }
            }
            edgeDropTaskDialog.close()
        }
        onRejected: edgeDropTaskDialog.close()

        onClosed: {
            edgeDropTaskField.text = ""
            edgeDropTaskDialog.sourceId = ""
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label {
                text: "ActionDraw"
                color: "#f5f6f8"
                font.pixelSize: 20
            }

            Rectangle {
                width: 1
                height: 24
                color: "#3b485c"
            }

            Button {
                id: drawModeButton
                text: diagramModel && diagramModel.drawingMode ? "✏ Drawing" : "✏ Draw"
                highlighted: diagramModel && diagramModel.drawingMode
                onClicked: {
                    if (diagramModel)
                        diagramModel.setDrawingMode(!diagramModel.drawingMode)
                }
            }

            Button {
                id: colorPickerButton
                text: ""
                enabled: diagramModel !== null
                implicitWidth: 32
                implicitHeight: 32
                background: Rectangle {
                    color: diagramModel ? diagramModel.brushColor : "#ffffff"
                    border.color: "#5b6878"
                    border.width: 2
                    radius: 4
                }
                onClicked: colorMenu.open()

                Menu {
                    id: colorMenu
                    parent: colorPickerButton
                    y: colorPickerButton.height

                    MenuItem {
                        text: "White"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ffffff" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#ffffff")
                    }
                    MenuItem {
                        text: "Red"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff5555" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#ff5555")
                    }
                    MenuItem {
                        text: "Orange"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff9944" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#ff9944")
                    }
                    MenuItem {
                        text: "Yellow"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ffee55" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#ffee55")
                    }
                    MenuItem {
                        text: "Green"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#55ff55" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#55ff55")
                    }
                    MenuItem {
                        text: "Cyan"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#55ffff" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#55ffff")
                    }
                    MenuItem {
                        text: "Blue"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#5588ff" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#5588ff")
                    }
                    MenuItem {
                        text: "Purple"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#aa55ff" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#aa55ff")
                    }
                    MenuItem {
                        text: "Pink"
                        Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff55aa" }
                        onTriggered: diagramModel && diagramModel.setBrushColor("#ff55aa")
                    }
                }
            }

            RowLayout {
                spacing: 4

                Label {
                    text: "Size:"
                    color: "#a8b8c8"
                }

                Slider {
                    id: brushSizeSlider
                    Layout.preferredWidth: 80
                    from: 1
                    to: 20
                    stepSize: 1
                    value: diagramModel ? diagramModel.brushWidth : 3
                    onValueChanged: {
                        if (diagramModel && Math.abs(diagramModel.brushWidth - value) > 0.1)
                            diagramModel.setBrushWidth(value)
                    }
                }

                Label {
                    text: Math.round(brushSizeSlider.value)
                    color: "#f5f6f8"
                    Layout.preferredWidth: 20
                }
            }

            Item { Layout.fillWidth: true }

            RowLayout {
                spacing: 6
                Layout.alignment: Qt.AlignVCenter

                Label {
                    text: "Zoom"
                    color: "#f5f6f8"
                }

                Button {
                    text: "-"
                    onClicked: root.applyZoomFactor(0.9, viewport.width / 2, viewport.height / 2)
                }

                Slider {
                    id: zoomSlider
                    Layout.preferredWidth: 140
                    from: root.minZoom
                    to: root.maxZoom
                    stepSize: 0.01
                    value: root.zoomLevel
                    onValueChanged: {
                        if (Math.abs(root.zoomLevel - value) > 0.0001) {
                            root.setZoomDirect(value, viewport.width / 2, viewport.height / 2)
                        }
                    }
                }

                Button {
                    text: "+"
                    onClicked: root.applyZoomFactor(1.1, viewport.width / 2, viewport.height / 2)
                }

                Button {
                    text: "Reset"
                    onClicked: root.resetView()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: "#161c24"
            border.color: "#243040"

            Flickable {
                id: viewport
                anchors.fill: parent
                contentWidth: root.boardSize * root.zoomLevel
                contentHeight: root.boardSize * root.zoomLevel
                clip: true
                interactive: !diagramModel || !diagramModel.drawingMode

                WheelHandler {
                    target: null
                    acceptedModifiers: Qt.ControlModifier
                    onWheel: {
                        var delta = wheel.angleDelta.y / 120
                        if (delta === 0)
                            return
                        var factor = Math.pow(1.1, delta)
                        root.applyZoomFactor(factor, wheel.x, wheel.y)
                    }
                }

                PinchHandler {
                    id: viewportPinch
                    target: null
                    property real lastScale: 1.0
                    onActiveChanged: {
                        if (active)
                            lastScale = 1.0
                    }
                    onScaleChanged: {
                        if (!active)
                            return
                        var factor = scale / lastScale
                        root.applyZoomFactor(factor, centroid.position.x, centroid.position.y)
                        lastScale = scale
                    }
                }

                Item {
                    id: diagramLayer
                    width: root.boardSize
                    height: root.boardSize
                    transformOrigin: Item.TopLeft
                    scale: root.zoomLevel

                    property real contextMenuX: 0
                    property real contextMenuY: 0

                    Menu {
                        id: canvasContextMenu

                        MenuItem {
                            text: "Box"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                diagramModel.addBox(snapped.x, snapped.y, "")
                            }
                        }
                        MenuItem {
                            text: "New Task"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openQuickTaskDialog(snapped)
                            }
                        }
                        MenuItem {
                            text: "Free Text"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openFreeTextDialog(snapped, "", "")
                            }
                        }
                    }

                    Canvas {
                        id: gridCanvas
                        anchors.fill: parent
                        visible: root.showGrid
                        opacity: root.showGrid ? 1 : 0
                        z: 0

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            if (!root.showGrid)
                                return
                            var spacing = root.gridSpacing
                            ctx.strokeStyle = "rgba(255, 255, 255, 0.05)"
                            ctx.lineWidth = 1
                            ctx.beginPath()
                            for (var x = 0; x <= width; x += spacing) {
                                ctx.moveTo(x, 0)
                                ctx.lineTo(x, height)
                            }
                            for (var y = 0; y <= height; y += spacing) {
                                ctx.moveTo(0, y)
                                ctx.lineTo(width, y)
                            }
                            ctx.stroke()
                        }
                    }

                    Canvas {
                        id: edgeCanvas
                        anchors.fill: parent
                        z: 1
                        property string hoveredEdgeId: ""
                        property string selectedEdgeId: ""

                        function distanceToSegment(px, py, x1, y1, x2, y2) {
                            var dx = x2 - x1
                            var dy = y2 - y1
                            var lengthSq = dx * dx + dy * dy
                            if (lengthSq === 0)
                                return Math.sqrt((px - x1) * (px - x1) + (py - y1) * (py - y1))
                            var t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lengthSq))
                            var projX = x1 + t * dx
                            var projY = y1 + t * dy
                            return Math.sqrt((px - projX) * (px - projX) + (py - projY) * (py - projY))
                        }

                        function findEdgeAt(mx, my) {
                            if (!diagramModel)
                                return ""
                            var edges = diagramModel.edges
                            var threshold = 8
                            for (var i = edges.length - 1; i >= 0; --i) {
                                var edge = edges[i]
                                var fromItem = diagramModel.getItemSnapshot(edge.fromId)
                                var toItem = diagramModel.getItemSnapshot(edge.toId)
                                if ((!fromItem.x && fromItem.x !== 0) || (!toItem.x && toItem.x !== 0))
                                    continue
                                var fromX = fromItem.x + fromItem.width / 2
                                var fromY = fromItem.y + fromItem.height / 2
                                var toX = toItem.x + toItem.width / 2
                                var toY = toItem.y + toItem.height / 2
                                var dist = distanceToSegment(mx, my, fromX, fromY, toX, toY)
                                if (dist <= threshold)
                                    return edge.id
                            }
                            return ""
                        }

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            if (!diagramModel)
                                return

                            var edges = diagramModel.edges
                            for (var i = 0; i < edges.length; ++i) {
                                var edge = edges[i]
                                var fromItem = diagramModel.getItemSnapshot(edge.fromId)
                                var toItem = diagramModel.getItemSnapshot(edge.toId)
                                if (!fromItem.x && fromItem.x !== 0)
                                    continue
                                if (!toItem.x && toItem.x !== 0)
                                    continue

                                var fromX = fromItem.x + fromItem.width / 2
                                var fromY = fromItem.y + fromItem.height / 2
                                var toX = toItem.x + toItem.width / 2
                                var toY = toItem.y + toItem.height / 2

                                var isHovered = edgeCanvas.hoveredEdgeId === edge.id
                                var isSelected = edgeCanvas.selectedEdgeId === edge.id
                                if (isSelected) {
                                    ctx.strokeStyle = "#ff6b6b"
                                    ctx.lineWidth = 3
                                } else if (isHovered) {
                                    ctx.strokeStyle = "#a8b8d8"
                                    ctx.lineWidth = 3
                                } else {
                                    ctx.strokeStyle = "#7b88a8"
                                    ctx.lineWidth = 2
                                }

                                ctx.beginPath()
                                ctx.moveTo(fromX, fromY)
                                ctx.lineTo(toX, toY)
                                ctx.stroke()

                                var angle = Math.atan2(toY - fromY, toX - fromX)
                                var arrowSize = 10
                                var arrowAngle = Math.PI / 6

                                ctx.beginPath()
                                ctx.moveTo(toX, toY)
                                ctx.lineTo(
                                    toX - arrowSize * Math.cos(angle - arrowAngle),
                                    toY - arrowSize * Math.sin(angle - arrowAngle)
                                )
                                ctx.lineTo(
                                    toX - arrowSize * Math.cos(angle + arrowAngle),
                                    toY - arrowSize * Math.sin(angle + arrowAngle)
                                )
                                ctx.closePath()
                                if (isSelected) {
                                    ctx.fillStyle = "#ff6b6b"
                                } else if (isHovered) {
                                    ctx.fillStyle = "#a8b8d8"
                                } else {
                                    ctx.fillStyle = "#7b88a8"
                                }
                                ctx.fill()

                                // Draw edge description text at midpoint
                                if (edge.description && edge.description.length > 0) {
                                    var midX = (fromX + toX) / 2
                                    var midY = (fromY + toY) / 2
                                    ctx.font = "12px sans-serif"
                                    ctx.fillStyle = "#f5f6f8"
                                    ctx.textAlign = "center"
                                    ctx.textBaseline = "bottom"
                                    // Offset text slightly above the line
                                    var offsetY = -6
                                    ctx.fillText(edge.description, midX, midY + offsetY)
                                }
                            }

                            if (diagramModel.edgeDrawingFrom.length > 0 && diagramModel.isDraggingEdge) {
                                var origin = diagramModel.getItemSnapshot(diagramModel.edgeDrawingFrom)
                                if (origin.x || origin.x === 0) {
                                    var originX = origin.x + origin.width / 2
                                    var originY = origin.y + origin.height / 2
                                    ctx.setLineDash([6, 4])
                                    ctx.strokeStyle = "#82c3a5"
                                    ctx.beginPath()
                                    ctx.moveTo(originX, originY)
                                    ctx.lineTo(diagramModel.edgeDragX, diagramModel.edgeDragY)
                                    ctx.stroke()
                                    ctx.setLineDash([])
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            propagateComposedEvents: true
                            z: -1

                            onPositionChanged: function(mouse) {
                                var edgeId = edgeCanvas.findEdgeAt(mouse.x, mouse.y)
                                if (edgeCanvas.hoveredEdgeId !== edgeId) {
                                    edgeCanvas.hoveredEdgeId = edgeId
                                    edgeCanvas.requestPaint()
                                }
                            }

                            onExited: {
                                if (edgeCanvas.hoveredEdgeId !== "") {
                                    edgeCanvas.hoveredEdgeId = ""
                                    edgeCanvas.requestPaint()
                                }
                            }

                            onClicked: function(mouse) {
                                var edgeId = edgeCanvas.findEdgeAt(mouse.x, mouse.y)
                                if (edgeId === "") {
                                    if (edgeCanvas.selectedEdgeId !== "") {
                                        edgeCanvas.selectedEdgeId = ""
                                        edgeCanvas.requestPaint()
                                    }
                                    mouse.accepted = false
                                    return
                                }
                                if (mouse.button === Qt.RightButton) {
                                    // Right-click to delete immediately
                                    diagramModel.removeEdge(edgeId)
                                    edgeCanvas.selectedEdgeId = ""
                                    edgeCanvas.hoveredEdgeId = ""
                                } else {
                                    // Left-click to select/deselect
                                    if (edgeCanvas.selectedEdgeId === edgeId) {
                                        edgeCanvas.selectedEdgeId = ""
                                    } else {
                                        edgeCanvas.selectedEdgeId = edgeId
                                    }
                                    edgeCanvas.requestPaint()
                                }
                            }

                            onDoubleClicked: function(mouse) {
                                var edgeId = edgeCanvas.findEdgeAt(mouse.x, mouse.y)
                                if (edgeId !== "") {
                                    // Double-click to edit description
                                    edgeDescriptionDialog.openWithEdge(edgeId)
                                } else {
                                    mouse.accepted = false
                                }
                            }
                        }
                    }

                    Connections {
                        target: diagramModel
                        function onEdgesChanged() { edgeCanvas.requestPaint() }
                        function onItemsChanged() { edgeCanvas.requestPaint() }
                        function onDrawingChanged() { drawingCanvas.requestPaint() }
                    }

                    Connections {
                        target: root
                        function onShowGridChanged() { gridCanvas.requestPaint() }
                        function onGridSpacingChanged() { gridCanvas.requestPaint() }
                    }

                    Canvas {
                        id: drawingCanvas
                        anchors.fill: parent
                        z: 2

                        function drawStroke(ctx, stroke) {
                            if (!stroke.points || stroke.points.length < 1)
                                return
                            ctx.strokeStyle = stroke.color
                            ctx.lineWidth = stroke.width
                            ctx.lineCap = "round"
                            ctx.lineJoin = "round"
                            ctx.beginPath()
                            ctx.moveTo(stroke.points[0].x, stroke.points[0].y)
                            if (stroke.points.length === 1) {
                                // Single point - draw a dot
                                ctx.arc(stroke.points[0].x, stroke.points[0].y, stroke.width / 2, 0, 2 * Math.PI)
                                ctx.fillStyle = stroke.color
                                ctx.fill()
                            } else {
                                for (var i = 1; i < stroke.points.length; ++i) {
                                    ctx.lineTo(stroke.points[i].x, stroke.points[i].y)
                                }
                                ctx.stroke()
                            }
                        }

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            if (!diagramModel)
                                return

                            // Draw all completed strokes
                            var allStrokes = diagramModel.strokes
                            for (var i = 0; i < allStrokes.length; ++i) {
                                drawStroke(ctx, allStrokes[i])
                            }

                            // Draw current stroke being drawn
                            var current = diagramModel.getCurrentStroke()
                            if (current && current.points && current.points.length >= 1) {
                                drawStroke(ctx, current)
                            }
                        }

                        MouseArea {
                            id: drawingMouseArea
                            anchors.fill: parent
                            enabled: diagramModel && diagramModel.drawingMode
                            hoverEnabled: false
                            acceptedButtons: Qt.LeftButton
                            z: 100

                            property bool isDrawing: false

                            onPressed: function(mouse) {
                                if (!diagramModel || !diagramModel.drawingMode)
                                    return
                                isDrawing = true
                                diagramModel.startStroke(mouse.x, mouse.y)
                                drawingCanvas.requestPaint()
                            }

                            onPositionChanged: function(mouse) {
                                if (!diagramModel || !isDrawing)
                                    return
                                diagramModel.continueStroke(mouse.x, mouse.y)
                                drawingCanvas.requestPaint()
                            }

                            onReleased: function(mouse) {
                                if (!diagramModel)
                                    return
                                isDrawing = false
                                diagramModel.endStroke()
                                drawingCanvas.requestPaint()
                            }

                            onCanceled: {
                                isDrawing = false
                                if (diagramModel)
                                    diagramModel.endStroke()
                                drawingCanvas.requestPaint()
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        enabled: !diagramModel || !diagramModel.drawingMode
                        onDoubleClicked: function(mouse) {
                            if (mouse.button === Qt.LeftButton) {
                                var pos = mapToItem(diagramLayer, mouse.x, mouse.y)
                                var snapped = root.snapPoint(pos)
                                diagramModel.addBox(snapped.x, snapped.y, "")
                            }
                        }
                        onClicked: function(mouse) {
                            if (mouse.button === Qt.RightButton) {
                                var pos = mapToItem(diagramLayer, mouse.x, mouse.y)
                                diagramLayer.contextMenuX = pos.x
                                diagramLayer.contextMenuY = pos.y
                                canvasContextMenu.popup()
                            }
                        }
                    }

                    Repeater {
                        model: diagramModel

                        Rectangle {
                            id: itemRect
                            property string itemId: model.itemId
                            property string itemType: model.itemType
                            property int taskIndex: model.taskIndex
                            property bool taskCompleted: model.taskCompleted
                            property bool isTask: itemRect.itemType === "task" && itemRect.taskIndex >= 0
                            property real dragStartX: 0
                            property real dragStartY: 0
                            property real pinchStartWidth: model.width
                            property real pinchStartHeight: model.height
                            property bool isEdgeDropTarget: diagramModel && diagramModel.edgeHoverTargetId === itemRect.itemId
                            x: model.x
                            y: model.y
                            width: model.width
                            height: model.height
                            radius: itemRect.itemType === "cloud" ? Math.min(width, height) / 2 : 12
                            color: itemRect.isTask && itemRect.taskCompleted ? Qt.darker(model.color, 1.5) : model.color
                            border.width: isEdgeDropTarget ? 3 : 1
                            border.color: isEdgeDropTarget ? "#74d9a0" : (itemDrag.active ? Qt.lighter(model.color, 1.4) : Qt.darker(model.color, 1.6))
                            z: isEdgeDropTarget ? 10 : 5
                            scale: isEdgeDropTarget ? 1.08 : 1.0
                            transformOrigin: Item.Center

                            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                            Behavior on border.width { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                            Behavior on x { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }
                            Behavior on y { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }

                            Rectangle {
                                anchors.fill: parent
                                color: Qt.rgba(0, 0, 0, itemDrag.active ? 0.08 : 0)
                                radius: itemRect.radius
                            }

                            Rectangle {
                                id: taskCheck
                                visible: itemRect.isTask
                                width: 20
                                height: 20
                                radius: 10
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.leftMargin: 8
                                anchors.topMargin: 8
                                color: itemRect.taskCompleted ? "#82c3a5" : "#1a2230"
                                border.color: itemRect.taskCompleted ? "#6fbf9a" : "#4b5b72"
                                border.width: 2
                                z: 20

                                Text {
                                    anchors.centerIn: parent
                                    text: itemRect.taskCompleted ? "✓" : ""
                                    color: itemRect.taskCompleted ? "#1b2028" : "#8a93a5"
                                    font.pixelSize: 12
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        if (diagramModel)
                                            diagramModel.setTaskCompleted(itemRect.taskIndex, !itemRect.taskCompleted)
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "database"

                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    anchors.topMargin: 6
                                    width: parent.width - 12
                                    height: parent.height * 0.25
                                    radius: height / 2
                                    color: Qt.lighter(model.color, 1.3)
                                    opacity: 0.9
                                }

                                Rectangle {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 6
                                    width: parent.width - 12
                                    height: parent.height * 0.22
                                    radius: height / 2
                                    color: Qt.darker(model.color, 1.2)
                                    opacity: 0.7
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "server"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 8

                                    Rectangle {
                                        height: 6
                                        radius: 3
                                        color: Qt.darker(model.color, 1.4)
                                        opacity: 0.5
                                    }

                                    Row {
                                        spacing: 8
                                        anchors.horizontalCenter: parent.horizontalCenter

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: "#5af58a"
                                        }

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: "#ffe266"
                                        }

                                        Rectangle {
                                            width: 12
                                            height: 12
                                            radius: 6
                                            color: "#f66d5a"
                                        }
                                    }

                                    Rectangle {
                                        height: 6
                                        radius: 3
                                        color: Qt.lighter(model.color, 1.2)
                                        opacity: 0.5
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "cloud"

                                Rectangle {
                                    width: parent.width * 0.55
                                    height: parent.height * 0.55
                                    radius: height / 2
                                    anchors.centerIn: parent
                                    color: Qt.lighter(model.color, 1.25)
                                    opacity: 0.9
                                }

                                Rectangle {
                                    width: parent.width * 0.45
                                    height: parent.height * 0.45
                                    radius: height / 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: parent.width * 0.08
                                    color: Qt.lighter(model.color, 1.4)
                                    opacity: 0.85
                                }

                                Rectangle {
                                    width: parent.width * 0.45
                                    height: parent.height * 0.45
                                    radius: height / 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.right: parent.right
                                    anchors.rightMargin: parent.width * 0.08
                                    color: Qt.lighter(model.color, 1.4)
                                    opacity: 0.85
                                }
                            }

                            Rectangle {
                                width: 22
                                height: 22
                                anchors.top: parent.top
                                anchors.right: parent.right
                                anchors.topMargin: 8
                                anchors.rightMargin: 8
                                color: Qt.lighter(model.color, 1.3)
                                border.color: Qt.darker(model.color, 1.2)
                                rotation: 45
                                visible: itemRect.itemType === "note"
                                radius: 2
                                transformOrigin: Item.Center
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "obstacle"

                                Rectangle {
                                    id: flagPole
                                    anchors.left: parent.left
                                    anchors.leftMargin: 16
                                    anchors.top: parent.top
                                    anchors.topMargin: 10
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 10
                                    width: 4
                                    radius: 2
                                    color: Qt.darker(model.color, 1.5)
                                }

                                Rectangle {
                                    anchors.left: flagPole.right
                                    anchors.top: parent.top
                                    anchors.topMargin: 12
                                    width: parent.width * 0.55
                                    height: parent.height * 0.45
                                    color: Qt.lighter(model.color, 1.15)
                                    border.color: Qt.darker(model.color, 1.2)
                                    border.width: 1
                                    radius: 4

                                    Canvas {
                                        anchors.fill: parent
                                        onPaint: {
                                            var ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            ctx.strokeStyle = Qt.darker(model.color, 1.3)
                                            ctx.lineWidth = 1.5
                                            ctx.beginPath()
                                            ctx.moveTo(6, height * 0.3)
                                            ctx.lineTo(width - 6, height * 0.3)
                                            ctx.moveTo(6, height * 0.55)
                                            ctx.lineTo(width - 6, height * 0.55)
                                            ctx.moveTo(6, height * 0.8)
                                            ctx.lineTo(width * 0.6, height * 0.8)
                                            ctx.stroke()
                                        }
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "wish"

                                Item {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    anchors.top: parent.top
                                    anchors.topMargin: 8
                                    width: Math.min(parent.width, parent.height) * 0.5
                                    height: width

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: width / 2
                                        color: Qt.lighter(model.color, 1.2)
                                        border.color: Qt.darker(model.color, 1.3)
                                        border.width: 2

                                        Rectangle {
                                            x: parent.width * 0.28
                                            y: parent.height * 0.32
                                            width: parent.width * 0.12
                                            height: parent.height * 0.12
                                            radius: width / 2
                                            color: "#2d3436"
                                        }

                                        Rectangle {
                                            x: parent.width * 0.60
                                            y: parent.height * 0.32
                                            width: parent.width * 0.12
                                            height: parent.height * 0.12
                                            radius: width / 2
                                            color: "#2d3436"
                                        }

                                        Canvas {
                                            anchors.fill: parent
                                            onPaint: {
                                                var ctx = getContext("2d")
                                                ctx.clearRect(0, 0, width, height)
                                                ctx.strokeStyle = "#2d3436"
                                                ctx.lineWidth = 2.5
                                                ctx.lineCap = "round"
                                                ctx.beginPath()
                                                var smileY = height * 0.58
                                                var smileRadius = width * 0.25
                                                ctx.arc(width / 2, smileY, smileRadius, 0.15 * Math.PI, 0.85 * Math.PI, false)
                                                ctx.stroke()
                                            }
                                        }
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "freetext"

                                Rectangle {
                                    id: freeTextHeader
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    height: 8
                                    color: Qt.darker(model.color, 1.15)
                                    radius: itemRect.radius
                                    Rectangle {
                                        anchors.bottom: parent.bottom
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        height: parent.radius
                                        color: parent.color
                                    }
                                }

                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.topMargin: 12
                                    anchors.leftMargin: 10
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: "#e17055"
                                }

                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.topMargin: 12
                                    anchors.leftMargin: 22
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: "#fdcb6e"
                                }

                                Rectangle {
                                    anchors.top: parent.top
                                    anchors.left: parent.left
                                    anchors.topMargin: 12
                                    anchors.leftMargin: 34
                                    width: 6
                                    height: 6
                                    radius: 3
                                    color: "#00b894"
                                }

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    anchors.right: parent.right
                                    anchors.bottomMargin: 6
                                    anchors.rightMargin: 6
                                    width: 16
                                    height: 16
                                    color: "transparent"
                                    Canvas {
                                        anchors.fill: parent
                                        onPaint: {
                                            var ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            ctx.strokeStyle = Qt.darker(model.color, 1.25)
                                            ctx.lineWidth = 1.5
                                            ctx.beginPath()
                                            ctx.moveTo(0, height)
                                            ctx.lineTo(width, 0)
                                            ctx.moveTo(width * 0.4, height)
                                            ctx.lineTo(width, height * 0.4)
                                            ctx.stroke()
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: itemRect.itemType !== "freetext" && itemRect.itemType !== "obstacle" && itemRect.itemType !== "wish"
                                anchors.centerIn: parent
                                width: parent.width - 36
                                text: model.text
                                color: itemRect.isTask && itemRect.taskCompleted ? "#c9d7ce" : model.textColor
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                textFormat: Text.PlainText
                                font.pixelSize: 14
                                font.bold: itemRect.itemType === "task"
                                font.strikeout: itemRect.isTask && itemRect.taskCompleted
                            }

                            Text {
                                visible: itemRect.itemType === "obstacle"
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.rightMargin: 8
                                anchors.bottomMargin: 8
                                anchors.left: parent.left
                                anchors.leftMargin: 28
                                text: model.text
                                color: model.textColor
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignLeft
                                verticalAlignment: Text.AlignBottom
                                textFormat: Text.PlainText
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                visible: itemRect.itemType === "wish"
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                anchors.bottomMargin: 8
                                text: model.text
                                color: model.textColor
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignBottom
                                textFormat: Text.PlainText
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                visible: itemRect.itemType === "freetext"
                                anchors.fill: parent
                                anchors.topMargin: 24
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                anchors.bottomMargin: 8
                                text: model.text
                                color: model.textColor
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignLeft
                                verticalAlignment: Text.AlignTop
                                textFormat: Text.PlainText
                                font.pixelSize: 13
                                elide: Text.ElideRight
                            }

                            DragHandler {
                                id: itemDrag
                                target: null
                                acceptedButtons: Qt.LeftButton
                                cursorShape: Qt.ClosedHandCursor
                                onActiveChanged: {
                                    if (!diagramModel)
                                        return
                                    if (active) {
                                        itemRect.dragStartX = model.x
                                        itemRect.dragStartY = model.y
                                    }
                                }
                                onTranslationChanged: {
                                    if (!diagramModel || !active)
                                        return
                                    var newX = itemRect.dragStartX + translation.x / root.zoomLevel
                                    var newY = itemRect.dragStartY + translation.y / root.zoomLevel
                                    newX = root.snapValue(newX)
                                    newY = root.snapValue(newY)
                                    diagramModel.moveItem(itemRect.itemId, newX, newY)
                                    edgeCanvas.requestPaint()
                                }
                            }

                            PinchHandler {
                                id: itemPinch
                                target: null
                                onActiveChanged: {
                                    if (active) {
                                        itemRect.pinchStartWidth = model.width
                                        itemRect.pinchStartHeight = model.height
                                    }
                                }
                                onScaleChanged: {
                                    if (!active || !diagramModel)
                                        return
                                    var newWidth = Math.max(60, itemRect.pinchStartWidth * scale)
                                    var newHeight = Math.max(40, itemRect.pinchStartHeight * scale)
                                    if (root.snapToGrid) {
                                        newWidth = Math.max(root.gridSpacing, Math.round(newWidth / root.gridSpacing) * root.gridSpacing)
                                        newHeight = Math.max(root.gridSpacing, Math.round(newHeight / root.gridSpacing) * root.gridSpacing)
                                    }
                                    diagramModel.resizeItem(itemRect.itemId, newWidth, newHeight)
                                    edgeCanvas.requestPaint()
                                }
                            }

                            TapHandler {
                                acceptedButtons: Qt.LeftButton
                                gesturePolicy: TapHandler.DragThreshold
                                onDoubleTapped: {
                                    if (itemRect.itemType === "task" && itemRect.taskIndex < 0) {
                                        // Task not yet linked to task list - create new task
                                        newTaskDialog.openWithItem(itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex >= 0) {
                                        // Task linked to task list - rename it (syncs both ways)
                                        taskRenameDialog.openWithItem(itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "freetext") {
                                        // Free text uses dedicated dialog with TextArea
                                        root.openFreeTextDialog(Qt.point(model.x, model.y), itemRect.itemId, model.text)
                                    } else if (itemRect.itemType !== "task") {
                                        root.openPresetDialog(itemRect.itemType, Qt.point(model.x, model.y), itemRect.itemId, model.text)
                                    }
                                }
                            }

                            Rectangle {
                                id: edgeHandle
                                width: 26
                                height: 26
                                radius: 4
                                anchors.top: parent.top
                                anchors.topMargin: 6
                                anchors.right: parent.right
                                anchors.rightMargin: 6
                                color: edgeDrag.active ? "#4c627f" : "#2a3444"
                                border.color: edgeDrag.active ? "#74a0d9" : "#3b485c"
                                property point dragPoint: Qt.point(model.x, model.y)

                                Text {
                                    anchors.centerIn: parent
                                    text: "→"
                                    color: "#d2d9e7"
                                    font.pixelSize: 16
                                }

                                DragHandler {
                                    id: edgeDrag
                                    target: null
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.CrossCursor
                                    onActiveChanged: {
                                        if (!diagramModel)
                                            return
                                        if (active) {
                                            var startPos = edgeHandle.mapToItem(diagramLayer, edgeHandle.width / 2, edgeHandle.height / 2)
                                            edgeHandle.dragPoint = Qt.point(startPos.x, startPos.y)
                                            diagramModel.startEdgeDrawing(itemRect.itemId)
                                            diagramModel.updateEdgeDragPosition(edgeHandle.dragPoint.x, edgeHandle.dragPoint.y)
                                            edgeCanvas.requestPaint()
                                        } else {
                                            var dropId = diagramModel.edgeHoverTargetId
                                            if (dropId && dropId !== itemRect.itemId) {
                                                diagramModel.finishEdgeDrawing(dropId)
                                            } else {
                                                // Dropped into empty space - show suggestion menu
                                                root.showEdgeDropSuggestions(
                                                    itemRect.itemId,
                                                    edgeHandle.dragPoint.x,
                                                    edgeHandle.dragPoint.y
                                                )
                                                diagramModel.cancelEdgeDrawing()
                                            }
                                            edgeCanvas.requestPaint()
                                        }
                                    }
                                    onCentroidChanged: {
                                        if (!diagramModel || !active)
                                            return
                                        var pos = itemRect.mapToItem(diagramLayer, centroid.position.x, centroid.position.y)
                                        edgeHandle.dragPoint = Qt.point(pos.x, pos.y)
                                        diagramModel.updateEdgeDragPosition(edgeHandle.dragPoint.x, edgeHandle.dragPoint.y)
                                        edgeCanvas.requestPaint()
                                    }
                                }
                            }

                            Rectangle {
                                id: deleteButton
                                width: 24
                                height: 24
                                radius: 4
                                anchors.right: parent.right
                                anchors.rightMargin: 6
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 6
                                color: "#3a1010"
                                border.color: "#612020"

                                Text {
                                    anchors.centerIn: parent
                                    text: "×"
                                    color: "#ff7b7b"
                                    font.pixelSize: 16
                                }

                                TapHandler {
                                    acceptedButtons: Qt.LeftButton
                                    onTapped: {
                                        if (diagramModel) {
                                            diagramModel.removeItem(itemRect.itemId)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component.onCompleted: Qt.callLater(resetView)
}
"""


def create_actiondraw_window(diagram_model: DiagramModel, task_model) -> QQmlApplicationEngine:
    """Create and return a QQmlApplicationEngine hosting the ActionDraw UI."""

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("diagramModel", diagram_model)
    engine.rootContext().setContextProperty("taskModel", task_model)
    engine.loadData(ACTIONDRAW_QML.encode("utf-8"))
    return engine


def main() -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    model = DiagramModel()
    engine = create_actiondraw_window(model, None)
    if engine.rootObjects():
        engine.rootObjects()[0].showWindow()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
