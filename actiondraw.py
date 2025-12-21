"""ActionDraw module for creating diagrams with boxes, tasks, and edges.

Features:
- Draw boxes with text
- Add tasks from progress list to diagram
- Draw edges between items
- Drag and drop tasks
- Create new tasks that are added to progress tracker
"""

import sys
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
    Slot,
    Property,
    Signal,
    QPointF,
)
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine


class DiagramItemType(Enum):
    BOX = "box"
    TASK = "task"


@dataclass
class DiagramItem:
    """Represents an item in the diagram (box or task)."""
    id: str
    item_type: DiagramItemType
    x: float
    y: float
    width: float = 120.0
    height: float = 60.0
    text: str = ""
    task_index: int = -1  # -1 for boxes, >= 0 for tasks
    color: str = "#4a9eff"


@dataclass
class DiagramEdge:
    """Represents an edge between two diagram items."""
    id: str
    from_id: str
    to_id: str


class DiagramModel(QAbstractListModel):
    """Model for managing diagram items."""
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
        self._next_id = 0
        self._task_model = task_model
        self._selected_item_id: Optional[str] = None
        self._edge_drawing_from: Optional[str] = None

    def rowCount(self, parent: QModelIndex | None = QModelIndex()) -> int:
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = self._items[index.row()]
        if role == self.IdRole:
            return item.id
        elif role == self.TypeRole:
            return item.item_type.value
        elif role == self.XRole:
            return item.x
        elif role == self.YRole:
            return item.y
        elif role == self.WidthRole:
            return item.width
        elif role == self.HeightRole:
            return item.height
        elif role == self.TextRole:
            return item.text
        elif role == self.TaskIndexRole:
            return item.task_index
        elif role == self.ColorRole:
            return item.color
        return None

    def roleNames(self):
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

    @Property(list, notify=edgesChanged)
    def edges(self) -> List[dict]:
        """Get edges as list of dictionaries for QML."""
        return [
            {
                "id": edge.id,
                "fromId": edge.from_id,
                "toId": edge.to_id,
            }
            for edge in self._edges
        ]

    @Slot(float, float, str)
    def addBox(self, x: float, y: float, text: str = "") -> str:
        """Add a box to the diagram."""
        item_id = f"box_{self._next_id}"
        self._next_id += 1

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

    @Slot(int, float, float)
    def addTask(self, task_index: int, x: float, y: float) -> str:
        """Add a task from the progress list to the diagram."""
        if not self._task_model or task_index < 0 or task_index >= self._task_model.rowCount():
            return ""

        # Get task title
        task_idx = self._task_model.index(task_index, 0)
        task_title = self._task_model.data(task_idx, self._task_model.TitleRole) or "Task"

        item_id = f"task_{self._next_id}"
        self._next_id += 1

        item = DiagramItem(
            id=item_id,
            item_type=DiagramItemType.TASK,
            x=x,
            y=y,
            text=task_title,
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
        """Move an item to a new position."""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                item.x = x
                item.y = y
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx, [self.XRole, self.YRole])
                self.itemsChanged.emit()  # Notify canvas to repaint edges
                break

    @Slot(str, str)
    def setItemText(self, item_id: str, text: str) -> None:
        """Set the text of an item."""
        for i, item in enumerate(self._items):
            if item.id == item_id:
                item.text = text
                idx = self.index(i, 0)
                self.dataChanged.emit(idx, idx, [self.TextRole])
                self.itemsChanged.emit()
                break

    @Slot(str, str)
    def addEdge(self, from_id: str, to_id: str) -> None:
        """Add an edge between two items."""
        if from_id == to_id:
            return

        # Check if edge already exists
        for edge in self._edges:
            if edge.from_id == from_id and edge.to_id == to_id:
                return

        edge_id = f"edge_{len(self._edges)}"
        edge = DiagramEdge(id=edge_id, from_id=from_id, to_id=to_id)
        self._edges.append(edge)
        self.edgesChanged.emit()

    @Slot(str)
    def removeItem(self, item_id: str) -> None:
        """Remove an item and all its edges."""
        # Remove edges connected to this item
        self._edges = [e for e in self._edges if e.from_id != item_id and e.to_id != item_id]
        self.edgesChanged.emit()

        # Remove item
        for i, item in enumerate(self._items):
            if item.id == item_id:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._items.pop(i)
                self.endRemoveRows()
                self.itemsChanged.emit()
                break

    @Slot(str)
    def startEdgeDrawing(self, item_id: str) -> None:
        """Start drawing an edge from an item."""
        self._edge_drawing_from = item_id
        self.itemsChanged.emit()  # Notify QML to update canvas

    @Slot(str)
    def finishEdgeDrawing(self, item_id: str) -> None:
        """Finish drawing an edge to an item."""
        if self._edge_drawing_from and self._edge_drawing_from != item_id:
            self.addEdge(self._edge_drawing_from, item_id)
        self._edge_drawing_from = None
        self.itemsChanged.emit()  # Notify QML to update canvas

    @Slot()
    def cancelEdgeDrawing(self) -> None:
        """Cancel edge drawing."""
        self._edge_drawing_from = None
        self.itemsChanged.emit()  # Notify QML to update canvas

    @Property(str, notify=itemsChanged)
    def edgeDrawingFrom(self) -> str:
        """Get the item ID from which edge is being drawn."""
        return self._edge_drawing_from or ""
    
    @Property(int, notify=itemsChanged)
    def count(self) -> int:
        """Get the number of items in the model."""
        return len(self._items)

    @Slot(str, str)
    def createTaskFromText(self, text: str, item_id: str) -> None:
        """Create a new task from text and update the diagram item."""
        if not self._task_model:
            return

        # Add task to task model
        self._task_model.addTask(text, -1)

        # Find the newly added task (it will be the last one)
        task_count = self._task_model.rowCount()
        if task_count > 0:
            new_task_index = task_count - 1

            # Update the diagram item to reference this task
            for i, item in enumerate(self._items):
                if item.id == item_id:
                    item.task_index = new_task_index
                    item.item_type = DiagramItemType.TASK
                    item.color = "#82c3a5"
                    idx = self.index(i, 0)
                    self.dataChanged.emit(idx, idx, [self.TaskIndexRole, self.TypeRole, self.ColorRole])
                    break

    def getItem(self, item_id: str) -> Optional[DiagramItem]:
        """Get an item by ID."""
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    def getItemAt(self, x: float, y: float) -> Optional[str]:
        """Get the item ID at the given coordinates."""
        for item in reversed(self._items):  # Check from top to bottom
            if (item.x <= x <= item.x + item.width and
                item.y <= y <= item.y + item.height):
                return item.id
        return None


ACTIONDRAW_QML = r"""
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs

ApplicationWindow {
    id: root
    visible: false
    width: 1000
    height: 700
    title: "ActionDraw"
    color: "#0f1115"

    function showWindow() {
        root.visible = true
        root.requestActivate()
    }

    Dialog {
        id: doubleClickDialog
        title: "Add to Diagram"
        modal: true
        width: 300
        height: 150

        property real clickX: 0
        property real clickY: 0

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "What would you like to add?"
                color: "#f5f6f8"
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "Draw Box"
                    Layout.fillWidth: true
                    onClicked: {
                        boxTextDialog.boxX = doubleClickDialog.clickX
                        boxTextDialog.boxY = doubleClickDialog.clickY
                        boxTextDialog.itemId = ""  // Clear itemId for new box
                        boxTextInput.text = ""  // Clear text field
                        doubleClickDialog.close()
                        boxTextDialog.open()
                    }
                }

                Button {
                    text: "Add Action"
                    Layout.fillWidth: true
                    onClicked: {
                        doubleClickDialog.close()
                        taskSelectionDialog.taskX = doubleClickDialog.clickX
                        taskSelectionDialog.taskY = doubleClickDialog.clickY
                        taskSelectionDialog.open()
                    }
                }
            }

            Button {
                text: "Cancel"
                Layout.fillWidth: true
                onClicked: doubleClickDialog.close()
            }
        }
    }

    Dialog {
        id: boxTextDialog
        title: "Box Text"
        modal: true
        width: 300
        height: 150

        property real boxX: 0
        property real boxY: 0
        property string itemId: ""

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: boxTextDialog.itemId ? "Edit box text:" : "Enter box text:"
                color: "#f5f6f8"
            }

            TextField {
                id: boxTextInput
                Layout.fillWidth: true
                placeholderText: "Box label"
                color: "#f5f6f8"
                selectByMouse: true
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#4a5568"
                }
                onAccepted: {
                    if (diagramModel) {
                        if (boxTextDialog.itemId) {
                            diagramModel.setItemText(boxTextDialog.itemId, text)
                        } else {
                            diagramModel.addBox(boxTextDialog.boxX, boxTextDialog.boxY, text)
                        }
                    }
                    boxTextDialog.close()
                    boxTextDialog.itemId = ""  // Clear after closing
                    boxTextInput.text = ""  // Clear text field
                }
                Component.onCompleted: {
                    forceActiveFocus()
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                Button {
                    text: boxTextDialog.itemId ? "Update" : "Add"
                    onClicked: {
                        if (diagramModel) {
                            if (boxTextDialog.itemId) {
                                diagramModel.setItemText(boxTextDialog.itemId, boxTextInput.text)
                            } else {
                                diagramModel.addBox(boxTextDialog.boxX, boxTextDialog.boxY, boxTextInput.text)
                            }
                        }
                        boxTextDialog.close()
                        boxTextDialog.itemId = ""  // Clear after closing
                        boxTextInput.text = ""  // Clear text field
                    }
                }

                Button {
                    text: "Cancel"
                    onClicked: {
                        boxTextDialog.close()
                        boxTextDialog.itemId = ""  // Clear on cancel
                        boxTextInput.text = ""  // Clear text field
                    }
                }
            }
        }
    }

    Dialog {
        id: taskSelectionDialog
        title: "Select Task"
        modal: true
        width: 400
        height: 400

        property real taskX: 0
        property real taskY: 0

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "Select a task to add:"
                color: "#f5f6f8"
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true

                ListView {
                    id: taskListView
                    model: taskModel
                    delegate: Rectangle {
                        width: taskListView.width
                        height: 40
                        color: mouseArea.containsMouse ? "#2a3240" : "#1f2630"
                        border.color: "#2e3744"

                        required property int index
                        required property string title

                        Label {
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: parent.title
                            color: "#f5f6f8"
                        }

                        MouseArea {
                            id: mouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                if (diagramModel) {
                                    diagramModel.addTask(parent.index, taskSelectionDialog.taskX, taskSelectionDialog.taskY)
                                }
                                taskSelectionDialog.close()
                            }
                        }
                    }
                }
            }

            Button {
                text: "Cancel"
                Layout.fillWidth: true
                onClicked: taskSelectionDialog.close()
            }
        }
    }

    Dialog {
        id: newTaskDialog
        title: "Create New Task"
        modal: true
        width: 300
        height: 150

        property string itemId: ""

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "Enter task name:"
                color: "#f5f6f8"
            }

            TextField {
                id: newTaskInput
                Layout.fillWidth: true
                placeholderText: "Task name"
                color: "#f5f6f8"
                selectByMouse: true
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#4a5568"
                }
                onAccepted: {
                    if (diagramModel && newTaskDialog.itemId) {
                        diagramModel.createTaskFromText(text, newTaskDialog.itemId)
                    }
                    newTaskDialog.close()
                }
                Component.onCompleted: {
                    forceActiveFocus()
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                Button {
                    text: "Create"
                    onClicked: {
                        if (diagramModel && newTaskDialog.itemId) {
                            diagramModel.createTaskFromText(newTaskInput.text, newTaskDialog.itemId)
                        }
                        newTaskDialog.close()
                    }
                }

                Button {
                    text: "Cancel"
                    onClicked: newTaskDialog.close()
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            spacing: 8

            Label {
                text: "ActionDraw"
                font.pixelSize: 18
                color: "#f5f6f8"
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "Clear All"
                onClicked: {
                    if (diagramModel) {
                        for (var i = diagramModel.count - 1; i >= 0; i--) {
                            var itemId = diagramModel.data(diagramModel.index(i, 0), diagramModel.IdRole)
                            diagramModel.removeItem(itemId)
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: "#161a20"
            border.color: "#222832"

            Flickable {
                id: flickable
                anchors.fill: parent
                anchors.margins: 8
                contentWidth: Math.max(width, canvas.width)
                contentHeight: Math.max(height, canvas.height)
                clip: true

                property real canvasWidth: 2000
                property real canvasHeight: 2000

                Canvas {
                    id: canvas
                    width: flickable.canvasWidth
                    height: flickable.canvasHeight

                    property var edges: diagramModel ? diagramModel.edges : []

                    onEdgesChanged: requestPaint()
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.clearRect(0, 0, width, height)

                        if (!diagramModel) return

                        // Draw edges
                        ctx.strokeStyle = "#4a5568"
                        ctx.lineWidth = 2

                        for (var i = 0; i < edges.length; i++) {
                            var edge = edges[i]
                            var fromItem = getItemById(edge.fromId)
                            var toItem = getItemById(edge.toId)

                            if (fromItem && toItem) {
                                var fromX = fromItem.x + fromItem.width / 2
                                var fromY = fromItem.y + fromItem.height / 2
                                var toX = toItem.x + toItem.width / 2
                                var toY = toItem.y + toItem.height / 2

                                ctx.beginPath()
                                ctx.moveTo(fromX, fromY)
                                ctx.lineTo(toX, toY)
                                ctx.stroke()

                                // Draw arrowhead
                                var angle = Math.atan2(toY - fromY, toX - fromX)
                                var arrowLength = 10
                                var arrowAngle = Math.PI / 6

                                ctx.beginPath()
                                ctx.moveTo(toX, toY)
                                ctx.lineTo(
                                    toX - arrowLength * Math.cos(angle - arrowAngle),
                                    toY - arrowLength * Math.sin(angle - arrowAngle)
                                )
                                ctx.lineTo(
                                    toX - arrowLength * Math.cos(angle + arrowAngle),
                                    toY - arrowLength * Math.sin(angle + arrowAngle)
                                )
                                ctx.closePath()
                                ctx.fillStyle = "#4a5568"
                                ctx.fill()
                            }
                        }

                        // Draw temporary edge if drawing
                        if (diagramModel && diagramModel.edgeDrawingFrom) {
                            var fromItem = getItemById(diagramModel.edgeDrawingFrom)
                            if (fromItem) {
                                var fromX = fromItem.x + fromItem.width / 2
                                var fromY = fromItem.y + fromItem.height / 2
                                var toX = edgeDrawingMouseArea.mouseX + flickable.contentX
                                var toY = edgeDrawingMouseArea.mouseY + flickable.contentY

                                ctx.strokeStyle = "#82c3a5"
                                ctx.lineWidth = 2
                                ctx.setLineDash([5, 5])
                                ctx.beginPath()
                                ctx.moveTo(fromX, fromY)
                                ctx.lineTo(toX, toY)
                                ctx.stroke()
                                ctx.setLineDash([])
                            }
                        }
                    }

                    function getItemById(itemId) {
                        if (!diagramModel) return null
                        for (var i = 0; i < diagramModel.count; i++) {
                            var idx = diagramModel.index(i, 0)
                            if (diagramModel.data(idx, diagramModel.IdRole) === itemId) {
                                return {
                                    x: diagramModel.data(idx, diagramModel.XRole),
                                    y: diagramModel.data(idx, diagramModel.YRole),
                                    width: diagramModel.data(idx, diagramModel.WidthRole),
                                    height: diagramModel.data(idx, diagramModel.HeightRole)
                                }
                            }
                        }
                        return null
                    }

                    Connections {
                        target: diagramModel
                        function onEdgesChanged() {
                            canvas.requestPaint()
                        }
                        function onItemsChanged() {
                            canvas.requestPaint()
                        }
                    }

                    MouseArea {
                        id: canvasMouseArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton

                        onDoubleClicked: function(mouse) {
                            var globalX = mouse.x + flickable.contentX
                            var globalY = mouse.y + flickable.contentY
                            doubleClickDialog.clickX = globalX
                            doubleClickDialog.clickY = globalY
                            doubleClickDialog.open()
                        }
                    }

                    MouseArea {
                        id: edgeDrawingMouseArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        propagateComposedEvents: true
                        z: -1
                        enabled: diagramModel && diagramModel.edgeDrawingFrom
                        hoverEnabled: true

                        onPressed: function(mouse) {
                            if (diagramModel && diagramModel.edgeDrawingFrom) {
                                var globalX = mouse.x + flickable.contentX
                                var globalY = mouse.y + flickable.contentY
                                var itemId = getItemAt(globalX, globalY)
                                if (itemId && itemId !== diagramModel.edgeDrawingFrom) {
                                    diagramModel.finishEdgeDrawing(itemId)
                                } else {
                                    diagramModel.cancelEdgeDrawing()
                                }
                                canvas.requestPaint()
                            }
                        }

                        onPositionChanged: function(mouse) {
                            if (diagramModel && diagramModel.edgeDrawingFrom) {
                                canvas.requestPaint()
                            }
                        }

                        function getItemAt(x, y) {
                            if (!diagramModel) return ""
                            for (var i = diagramModel.count - 1; i >= 0; i--) {
                                var idx = diagramModel.index(i, 0)
                                var itemX = diagramModel.data(idx, diagramModel.XRole)
                                var itemY = diagramModel.data(idx, diagramModel.YRole)
                                var itemW = diagramModel.data(idx, diagramModel.WidthRole)
                                var itemH = diagramModel.data(idx, diagramModel.HeightRole)

                                if (x >= itemX && x <= itemX + itemW && y >= itemY && y <= itemY + itemH) {
                                    return diagramModel.data(idx, diagramModel.IdRole)
                                }
                            }
                            return ""
                        }
                    }

                    Repeater {
                        model: diagramModel

                        Rectangle {
                            id: itemRect
                            x: model.x
                            y: model.y
                            width: model.width
                            height: model.height
                            radius: 8
                            color: model.color
                            border.color: "#2e3744"
                            border.width: 1
                            opacity: 0.9

                            required property var model

                            Drag.active: dragMouseArea.drag.active
                            Drag.hotSpot.x: width / 2
                            Drag.hotSpot.y: height / 2

                            MouseArea {
                                id: dragMouseArea
                                anchors.fill: parent
                                drag.target: parent
                                acceptedButtons: Qt.LeftButton
                                cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor

                                onPressed: function(mouse) {
                                    // Check if clicking on edge button
                                    var edgeButtonX = width - 30
                                    var edgeButtonY = 5
                                    if (mouse.x >= edgeButtonX && mouse.x <= edgeButtonX + 25 &&
                                        mouse.y >= edgeButtonY && mouse.y <= edgeButtonY + 25) {
                                        // Start edge drawing
                                        if (diagramModel) {
                                            diagramModel.startEdgeDrawing(model.itemId)
                                            canvas.requestPaint()
                                        }
                                        mouse.accepted = false
                                        return
                                    }
                                }

                                onReleased: function(mouse) {
                                    if (drag.active) {
                                        // Update position in model
                                        var newX = itemRect.x
                                        var newY = itemRect.y
                                        if (diagramModel) {
                                            diagramModel.moveItem(model.itemId, newX, newY)
                                        }
                                    }
                                }

                                onDoubleClicked: function(mouse) {
                                    // Edit text
                                    var edgeButtonX = width - 30
                                    var edgeButtonY = 5
                                    var deleteButtonX = width - 30
                                    var deleteButtonY = height - 30
                                    if ((mouse.x >= edgeButtonX && mouse.x <= edgeButtonX + 25 &&
                                         mouse.y >= edgeButtonY && mouse.y <= edgeButtonY + 25) ||
                                        (mouse.x >= deleteButtonX && mouse.x <= deleteButtonX + 25 &&
                                         mouse.y >= deleteButtonY && mouse.y <= deleteButtonY + 25)) {
                                        return
                                    }

                                    if (model.itemType === "box") {
                                        // Edit box text
                                        boxTextDialog.itemId = model.itemId
                                        boxTextDialog.boxX = model.x
                                        boxTextDialog.boxY = model.y
                                        boxTextInput.text = model.text
                                        boxTextDialog.open()
                                    } else if (model.itemType === "task" && model.taskIndex < 0) {
                                        // Create new task
                                        newTaskDialog.itemId = model.itemId
                                        newTaskInput.text = model.text
                                        newTaskDialog.open()
                                    }
                                }
                            }

                            Text {
                                anchors.centerIn: parent
                                text: model.text
                                color: "#f5f6f8"
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                width: parent.width - 40
                                horizontalAlignment: Text.AlignHCenter
                            }

                            // Edge button
                            Rectangle {
                                x: parent.width - 30
                                y: 5
                                width: 25
                                height: 25
                                radius: 4
                                color: edgeButtonMouseArea.containsMouse ? "#384050" : "#28303d"
                                border.color: "#2e3744"

                                Text {
                                    anchors.centerIn: parent
                                    text: "→"
                                    color: "#9aa6b8"
                                    font.pixelSize: 14
                                }

                                MouseArea {
                                    id: edgeButtonMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        if (diagramModel) {
                                            diagramModel.startEdgeDrawing(model.itemId)
                                            canvas.requestPaint()
                                        }
                                    }
                                }
                            }

                            // Delete button
                            Rectangle {
                                x: parent.width - 30
                                y: parent.height - 30
                                width: 25
                                height: 25
                                radius: 4
                                color: deleteButtonMouseArea.containsMouse ? "#5a2020" : "#3a1010"
                                border.color: "#4a2020"

                                Text {
                                    anchors.centerIn: parent
                                    text: "×"
                                    color: "#ff6b6b"
                                    font.pixelSize: 16
                                }

                                MouseArea {
                                    id: deleteButtonMouseArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        if (diagramModel) {
                                            diagramModel.removeItem(model.itemId)
                                        }
                                    }
                                }
                            }

                            Connections {
                                target: diagramModel
                                function onItemsChanged() {
                                    itemRect.x = model.x
                                    itemRect.y = model.y
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
    """Create and return an ActionDraw window."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("diagramModel", diagram_model)
    engine.rootContext().setContextProperty("taskModel", task_model)
    # Convert string to bytes for loadData
    qml_bytes = ACTIONDRAW_QML.encode('utf-8')
    engine.loadData(qml_bytes)

    return engine

