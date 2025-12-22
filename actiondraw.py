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

    itemsChanged = Signal()
    edgesChanged = Signal()

    def __init__(self, task_model=None):
        super().__init__()
        self._items: List[DiagramItem] = []
        self._edges: List[DiagramEdge] = []
        self._task_model = task_model
        self._id_source = count()
        self._edge_source_id: Optional[str] = None
        self._renaming_in_progress = False  # Flag to prevent re-entrant rename calls
        
        # Connect to task model's taskRenamed signal for bidirectional sync
        if self._task_model is not None:
            self._task_model.taskRenamed.connect(self.onTaskRenamed)
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
        }

    # --- Properties exposed to QML -----------------------------------------
    @Property(list, notify=edgesChanged)
    def edges(self) -> List[Dict[str, str]]:
        return [
            {"id": edge.id, "fromId": edge.from_id, "toId": edge.to_id}
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

    @Property(int, notify=itemsChanged)
    def count(self) -> int:
        return len(self._items)

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

    # --- Utilities ----------------------------------------------------------
    def getItem(self, item_id: str) -> Optional[DiagramItem]:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

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
        if changed:
            self.itemsChanged.emit()


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
        "note": { "text": "Note", "title": "Create Note" }
    })

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
                onAccepted: boxDialogButtonBox.accept()
            }
        }

        footer: DialogButtonBox {
            id: boxDialogButtonBox
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
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
        }

        onClosed: {
            boxDialog.textValue = ""
            boxDialog.editingItemId = ""
            boxDialog.presetName = "box"
        }
    }

    Dialog {
        id: taskDialog
        modal: true
        title: "Add Task"
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            width: 320
            height: 360
            spacing: 12

            ListView {
                id: taskListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: taskModel
                clip: true

                delegate: Item {
                    width: taskListView.width
                    height: 40

                    Rectangle {
                        anchors.fill: parent
                        color: mouseArea.containsMouse ? "#283346" : "#1a2230"
                        border.color: "#30405a"
                    }

                    Text {
                        anchors.centerIn: parent
                        text: model.title
                        color: "#f5f6f8"
                        font.pixelSize: 14
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
                anchors.centerIn: parent
                text: taskModel ? "No tasks available. Add tasks in Progress Tracker." : "Task list unavailable. Open ActionDraw from the task app."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                width: parent.width - 32
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
                onAccepted: quickTaskButtons.accept()
            }
        }

        footer: DialogButtonBox {
            id: quickTaskButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
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
        }

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

            Button {
                text: "Add Box"
                onClicked: root.addBoxAtCenter()
            }

            Button {
                id: addNodeButton
                text: "Add Node"
                onClicked: nodeMenu.open()
            }

            Menu {
                id: nodeMenu
                parent: addNodeButton
                y: addNodeButton.height

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
            }

            Button {
                text: "Add Task"
                enabled: taskModel !== null
                onClicked: {
                    if (!taskModel)
                        return
                    var center = diagramCenterPoint()
                    taskDialog.targetX = center.x
                    taskDialog.targetY = center.y
                    taskDialog.open()
                }
            }

            Button {
                text: "New Task"
                enabled: diagramModel !== null
                onClicked: root.addQuickTaskAtCenter()
            }

            Button {
                text: "Connect All"
                onClicked: diagramModel && diagramModel.connectAllItems()
            }

            Button {
                text: "Clear"
                onClicked: {
                    if (!diagramModel)
                        return
                    for (var i = diagramModel.count - 1; i >= 0; --i) {
                        var idx = diagramModel.index(i, 0)
                        var itemId = diagramModel.data(idx, diagramModel.IdRole)
                        diagramModel.removeItem(itemId)
                    }
                    resetView()
                }
            }

            Item { Layout.fillWidth: true }

            CheckBox {
                text: "Grid"
                checked: root.showGrid
                onToggled: root.showGrid = checked
                indicator.width: 18
                indicator.height: 18
                palette.text: "#f5f6f8"
            }

            CheckBox {
                text: "Snap"
                checked: root.snapToGrid
                onToggled: root.snapToGrid = checked
                indicator.width: 18
                indicator.height: 18
                palette.text: "#f5f6f8"
            }

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

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            if (!diagramModel)
                                return

                            ctx.strokeStyle = "#7b88a8"
                            ctx.lineWidth = 2

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
                                ctx.fillStyle = "#7b88a8"
                                ctx.fill()
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
                    }

                    Connections {
                        target: diagramModel
                        function onEdgesChanged() { edgeCanvas.requestPaint() }
                        function onItemsChanged() { edgeCanvas.requestPaint() }
                    }

                    Connections {
                        target: root
                        function onShowGridChanged() { gridCanvas.requestPaint() }
                        function onGridSpacingChanged() { gridCanvas.requestPaint() }
                    }

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onDoubleClicked: function(mouse) {
                            var pos = mapToItem(diagramLayer, mouse.x, mouse.y)
                            var snapped = root.snapPoint(pos)
                            addDialog.targetX = snapped.x
                            addDialog.targetY = snapped.y
                            addDialog.open()
                        }
                    }

                    Repeater {
                        model: diagramModel

                        Rectangle {
                            id: itemRect
                            property string itemId: model.itemId
                            property string itemType: model.itemType
                            property int taskIndex: model.taskIndex
                            property real dragStartX: 0
                            property real dragStartY: 0
                            property real pinchStartWidth: model.width
                            property real pinchStartHeight: model.height
                            x: model.x
                            y: model.y
                            width: model.width
                            height: model.height
                            radius: itemRect.itemType === "cloud" ? Math.min(width, height) / 2 : 12
                            color: model.color
                            border.width: 1
                            border.color: itemDrag.active ? Qt.lighter(model.color, 1.4) : Qt.darker(model.color, 1.6)
                            z: 5

                            Behavior on x { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }
                            Behavior on y { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }

                            Rectangle {
                                anchors.fill: parent
                                color: Qt.rgba(0, 0, 0, itemDrag.active ? 0.08 : 0)
                                radius: itemRect.radius
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

                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 36
                                text: model.text
                                color: model.textColor
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                textFormat: Text.PlainText
                                font.pixelSize: 14
                                font.bold: itemRect.itemType === "task"
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
                                            var dropId = diagramModel.itemIdAt(edgeHandle.dragPoint.x, edgeHandle.dragPoint.y)
                                            if (dropId && dropId !== itemRect.itemId) {
                                                diagramModel.finishEdgeDrawing(dropId)
                                            } else {
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

