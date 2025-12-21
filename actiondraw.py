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


@dataclass
class DiagramEdge:
    """A directed connection between two diagram items."""

    id: str
    from_id: str
    to_id: str


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

    itemsChanged = Signal()
    edgesChanged = Signal()

    def __init__(self, task_model=None):
        super().__init__()
        self._items: List[DiagramItem] = []
        self._edges: List[DiagramEdge] = []
        self._task_model = task_model
        self._id_source = count()
        self._edge_source_id: Optional[str] = None
        self._edge_drag_x: float = 0.0
        self._edge_drag_y: float = 0.0
        self._is_dragging_edge: bool = False

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
        item_id = f"box_{next(self._id_source)}"
        item = DiagramItem(
            id=item_id,
            item_type=DiagramItemType.BOX,
            x=x,
            y=y,
            text=text,
            color="#4a9eff",
        )
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()
        self.itemsChanged.emit()
        return item_id

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
        )
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()
        self.itemsChanged.emit()
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
                index = self.index(row, 0)
                self.dataChanged.emit(
                    index,
                    index,
                    [self.TaskIndexRole, self.TypeRole, self.ColorRole, self.TextRole],
                )
                self.itemsChanged.emit()
                break

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

    Dialog {
        id: addDialog
        modal: true
        title: "Add to Diagram"
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            width: 280
            spacing: 12

            Button {
                text: "Box"
                onClicked: {
                    addDialog.close()
                    boxDialog.editingItemId = ""
                    boxDialog.targetX = addDialog.targetX
                    boxDialog.targetY = addDialog.targetY
                    boxDialog.textValue = ""
                    boxDialog.open()
                }
            }

            Button {
                text: "Task from List"
                enabled: taskModel !== null
                onClicked: {
                    addDialog.close()
                    if (taskModel) {
                        taskDialog.targetX = addDialog.targetX
                        taskDialog.targetY = addDialog.targetY
                        taskDialog.open()
                    }
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
        title: editingItemId.length === 0 ? "Create Box" : "Edit Item"

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
                    diagramModel.addBox(boxDialog.targetX, boxDialog.targetY, boxDialog.textValue)
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
                                diagramModel.addTask(index, taskDialog.targetX, taskDialog.targetY)
                            }
                            taskDialog.close()
                        }
                    }
                }
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

            Item { Layout.fillWidth: true }

            Button {
                text: "Add Box"
                onClicked: {
                    var centerX = viewport.contentX + viewport.width / 2
                    var centerY = viewport.contentY + viewport.height / 2
                    boxDialog.editingItemId = ""
                    boxDialog.targetX = centerX
                    boxDialog.targetY = centerY
                    boxDialog.textValue = ""
                    boxDialog.open()
                }
            }

            Button {
                text: "Add Task"
                enabled: taskModel !== null
                onClicked: {
                    if (!taskModel)
                        return
                    var centerX = viewport.contentX + viewport.width / 2
                    var centerY = viewport.contentY + viewport.height / 2
                    taskDialog.targetX = centerX
                    taskDialog.targetY = centerY
                    taskDialog.open()
                }
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
                contentWidth: root.boardSize
                contentHeight: root.boardSize
                clip: true

                Item {
                    id: diagramLayer
                    width: root.boardSize
                    height: root.boardSize

                    Canvas {
                        id: edgeCanvas
                        anchors.fill: parent
                        z: 0

                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.clearRect(0, 0, width, height)
                            if (!diagramModel)
                                return

                            ctx.strokeStyle = "#4a5568"
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
                                ctx.fillStyle = "#4a5568"
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

                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        onDoubleClicked: function(mouse) {
                            var pos = mapToItem(diagramLayer, mouse.x, mouse.y)
                            addDialog.targetX = pos.x
                            addDialog.targetY = pos.y
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
                            x: model.x
                            y: model.y
                            width: model.width
                            height: model.height
                            radius: 8
                            color: model.color
                            border.color: "#2e3744"
                            border.width: 1
                            z: 5

                            DragHandler {
                                id: itemDrag
                                target: null
                                acceptedButtons: Qt.LeftButton
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
                                    var newX = itemRect.dragStartX + translation.x
                                    var newY = itemRect.dragStartY + translation.y
                                    diagramModel.moveItem(itemRect.itemId, newX, newY)
                                    edgeCanvas.requestPaint()
                                }
                            }

                            TapHandler {
                                acceptedButtons: Qt.LeftButton
                                gesturePolicy: TapHandler.DragThreshold
                                onDoubleTapped: {
                                    if (itemRect.itemType === "box") {
                                        boxDialog.editingItemId = itemRect.itemId
                                        boxDialog.textValue = model.text
                                        boxDialog.targetX = model.x
                                        boxDialog.targetY = model.y
                                        boxDialog.open()
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex < 0) {
                                        newTaskDialog.openWithItem(itemRect.itemId, model.text)
                                    }
                                }
                            }

                            Text {
                                anchors.centerIn: parent
                                width: parent.width - 32
                                text: model.text
                                color: "#f5f6f8"
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: 13
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

