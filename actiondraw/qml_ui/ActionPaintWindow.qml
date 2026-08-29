import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: root
    width: 1220
    height: 780
    minimumWidth: 860
    minimumHeight: 560
    visible: true
    title: "Action Paint"
    color: "#0c151d"

    property var paintModel: actionPaintModel
    property var diagramModelRef: diagramModel
    property var hostRoot: null
    property string activeTool: "select"
    property string brushColor: "#263238"
    property real brushWidth: 4
    property real fontSize: 24
    property real eraserSize: 24
    property real pendingActionX: 0
    property real pendingActionY: 0
    property real pendingTextX: 0
    property real pendingTextY: 0
    property string editingActionId: ""
    property string statusText: ""
    property int draggedActionIndex: -1
    property int actionDropTargetIndex: -1

    onActiveToolChanged: updateCanvasInteraction()

    function updateCanvasInteraction() {
        if (canvasScroll && canvasScroll.contentItem
                && canvasScroll.contentItem.interactive !== undefined) {
            canvasScroll.contentItem.interactive = root.activeTool === "select"
        }
    }

    function chooseTool(name) {
        activeTool = name
        statusText = ""
    }

    function openNewAction(x, y) {
        pendingActionX = x
        pendingActionY = y
        editingActionId = ""
        actionTextField.text = ""
        actionDialog.title = "Add action"
        actionDialog.open()
        actionTextField.forceActiveFocus()
    }

    function openEditAction(actionId, text) {
        editingActionId = actionId
        actionTextField.text = text
        actionDialog.title = "Rename action"
        actionDialog.open()
        actionTextField.forceActiveFocus()
        actionTextField.selectAll()
    }

    function openNewText(x, y) {
        pendingTextX = x
        pendingTextY = y
        paintTextField.text = ""
        paintTextDialog.open()
        paintTextField.forceActiveFocus()
    }

    function actionDragHandleAt(index) {
        var row = actionList.itemAtIndex(index)
        return row ? row.dragHandle : null
    }

    function importActions() {
        if (!paintModel || paintModel.actionCount === 0 || paintModel.imported)
            return
        if (paintModel.demoMode) {
            if (paintModel.simulateImport())
                statusText = "Demo import complete"
            return
        }
        if (!diagramModelRef || !hostRoot) {
            statusText = "ActionDraw is not available"
            return
        }
        var point = hostRoot.actionPaintImportPosition()
        var created = diagramModelRef.createTaskChainAtPosition(
            paintModel.orderedTitles, Number(point.x), Number(point.y))
        if (created && created.length === paintModel.actionCount) {
            paintModel.markImported()
            statusText = "Added " + created.length + " actions to ActionDraw"
            hostRoot.showSaveNotification(statusText)
        } else {
            statusText = "Could not add every action"
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 54
            radius: 10
            color: "#142430"
            border.color: "#345166"

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 7

                Label { text: "Action Paint"; color: "#eef7ff"; font.pixelSize: 17; font.bold: true }

                ToolButton { text: "Select"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "select"; checkable: true; onClicked: root.chooseTool("select") }
                ToolButton { text: "Pencil"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "pencil"; checkable: true; onClicked: root.chooseTool("pencil") }
                ToolButton { text: "Line"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "line"; checkable: true; onClicked: root.chooseTool("line") }
                ToolButton { text: "Rectangle"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "rectangle"; checkable: true; onClicked: root.chooseTool("rectangle") }
                ToolButton { text: "Text"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "text"; checkable: true; onClicked: root.chooseTool("text") }
                ToolButton { text: "Eraser"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "eraser"; checkable: true; onClicked: root.chooseTool("eraser") }
                ToolButton { text: "+ Action"; palette.buttonText: "#d8e5ef"; checked: root.activeTool === "action"; checkable: true; onClicked: root.chooseTool("action") }

                ComboBox {
                    id: colorPicker
                    Layout.preferredWidth: 92
                    model: ["Black", "Blue", "Red", "Green", "Orange", "Purple"]
                    onCurrentIndexChanged: {
                        var colors = ["#263238", "#2962ff", "#d32f2f", "#2e7d32", "#ef6c00", "#7b1fa2"]
                        root.brushColor = colors[currentIndex]
                    }
                }

                Label { text: root.activeTool === "text" ? "Size" : (root.activeTool === "eraser" ? "Eraser" : "Width"); color: "#adc1d1" }
                Slider {
                    from: root.activeTool === "text" ? 10 : (root.activeTool === "eraser" ? 8 : 1)
                    to: root.activeTool === "text" ? 72 : (root.activeTool === "eraser" ? 60 : 20)
                    stepSize: 1
                    value: root.activeTool === "text" ? root.fontSize : (root.activeTool === "eraser" ? root.eraserSize : root.brushWidth)
                    Layout.preferredWidth: 90
                    onValueChanged: {
                        if (root.activeTool === "text")
                            root.fontSize = value
                        else if (root.activeTool === "eraser")
                            root.eraserSize = value
                        else
                            root.brushWidth = value
                    }
                }
                Label { text: Math.round(root.activeTool === "text" ? root.fontSize : (root.activeTool === "eraser" ? root.eraserSize : root.brushWidth)); color: "#e5f0f8"; Layout.preferredWidth: 18 }

                ToolButton { text: "Undo"; enabled: paintModel && paintModel.canUndo; palette.buttonText: enabled ? "#d8e5ef" : "#71818d"; onClicked: paintModel && paintModel.undoLastDrawing() }
                ToolButton { text: "Clear drawing"; palette.buttonText: "#d8e5ef"; onClicked: clearDialog.open() }

                Item { Layout.fillWidth: true }

                Label {
                    visible: root.statusText.length > 0
                    text: root.statusText
                    color: paintModel && paintModel.imported ? "#8ee3a1" : "#ffd180"
                    elide: Text.ElideRight
                    Layout.maximumWidth: 190
                }

                Button {
                    id: importButton
                    text: paintModel && paintModel.imported ? "✓ Added to ActionDraw" : "Add to ActionDraw"
                    enabled: paintModel && paintModel.actionCount > 0 && !paintModel.imported
                    highlighted: enabled
                    palette.buttonText: enabled ? "#102431" : "#8294a0"
                    onClicked: root.importActions()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#263743"
                border.color: "#456176"
                radius: 8
                clip: true

                ScrollView {
                    id: canvasScroll
                    anchors.fill: parent
                    anchors.margins: 2
                    contentWidth: 1600
                    contentHeight: 1000
                    // Do not let the Flickable steal a held pointer from paint tools.
                    // Panning remains available through wheel/trackpad and scrollbars.
                    Component.onCompleted: root.updateCanvasInteraction()
                    ScrollBar.horizontal.policy: ScrollBar.AsNeeded
                    ScrollBar.vertical.policy: ScrollBar.AsNeeded

                    Item {
                        id: paintSurface
                        width: 1600
                        height: 1000

                        Rectangle { anchors.fill: parent; color: "#fffdf8" }

                        Canvas {
                            id: drawingCanvas
                            anchors.fill: parent
                            renderTarget: Canvas.Image
                            Component.onCompleted: initialPaintTimer.start()
                            onAvailableChanged: {
                                if (available)
                                    requestPaint()
                            }
                            Timer {
                                id: initialPaintTimer
                                interval: 1
                                repeat: false
                                onTriggered: drawingCanvas.requestPaint()
                            }
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.clearRect(0, 0, width, height)
                                if (!paintModel)
                                    return
                                var items = paintModel.elements
                                for (var i = 0; i < items.length; ++i) {
                                    var item = items[i]
                                    if (item.type === "text") {
                                        ctx.fillStyle = item.color
                                        ctx.font = item.font_size + "px sans-serif"
                                        ctx.textBaseline = "top"
                                        ctx.fillText(item.text, item.x, item.y)
                                        continue
                                    }
                                    ctx.strokeStyle = item.color
                                    ctx.lineWidth = item.width
                                    ctx.lineCap = "round"
                                    ctx.lineJoin = "round"
                                    if (item.type === "pencil") {
                                        var points = item.points || []
                                        if (points.length < 1)
                                            continue
                                        ctx.beginPath()
                                        ctx.moveTo(points[0].x, points[0].y)
                                        for (var p = 1; p < points.length; ++p)
                                            ctx.lineTo(points[p].x, points[p].y)
                                        ctx.stroke()
                                    } else if (item.type === "line") {
                                        ctx.beginPath()
                                        ctx.moveTo(item.x1, item.y1)
                                        ctx.lineTo(item.x2, item.y2)
                                        ctx.stroke()
                                    } else if (item.type === "rectangle") {
                                        var left = Math.min(item.x1, item.x2)
                                        var top = Math.min(item.y1, item.y2)
                                        ctx.strokeRect(left, top, Math.abs(item.x2 - item.x1), Math.abs(item.y2 - item.y1))
                                    }
                                }
                            }
                        }

                        Connections {
                            target: paintModel
                            enabled: paintModel !== null
                            function onElementsChanged() { drawingCanvas.requestPaint() }
                        }

                        MouseArea {
                            id: drawingMouse
                            objectName: "actionPaintDrawingMouse"
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton
                            preventStealing: true
                            hoverEnabled: true
                            cursorShape: root.activeTool === "select" ? Qt.ArrowCursor : Qt.CrossCursor
                            onPressed: function(mouse) {
                                if (!paintModel)
                                    return
                                if (root.activeTool === "action") {
                                    root.openNewAction(mouse.x, mouse.y)
                                } else if (root.activeTool === "text") {
                                    root.openNewText(mouse.x, mouse.y)
                                } else if (root.activeTool === "eraser") {
                                    paintModel.beginErase()
                                    paintModel.eraseAt(mouse.x, mouse.y, root.eraserSize / 2)
                                } else if (root.activeTool !== "select") {
                                    paintModel.startDrawing(root.activeTool, mouse.x, mouse.y, root.brushColor, root.brushWidth)
                                }
                            }
                            onPositionChanged: function(mouse) {
                                if (drawingMouse.pressed && root.activeTool === "eraser")
                                    paintModel.eraseAt(mouse.x, mouse.y, root.eraserSize / 2)
                                else if (drawingMouse.pressed && root.activeTool !== "select" && root.activeTool !== "action" && root.activeTool !== "text")
                                    paintModel.continueDrawing(mouse.x, mouse.y)
                            }
                            onReleased: function(mouse) {
                                if (root.activeTool === "eraser")
                                    paintModel.endErase()
                                else if (root.activeTool !== "select" && root.activeTool !== "action" && root.activeTool !== "text")
                                    paintModel.endDrawing()
                            }
                            onCanceled: {
                                if (!paintModel)
                                    return
                                if (root.activeTool === "eraser")
                                    paintModel.endErase()
                                else
                                    paintModel.endDrawing()
                            }
                        }

                        Repeater {
                            model: paintModel ? paintModel.actions : []
                            delegate: Rectangle {
                                id: marker
                                required property var modelData
                                x: modelData.x - 18
                                y: modelData.y - 18
                                width: Math.max(36, markerText.implicitWidth + 20)
                                height: 36
                                radius: 18
                                color: "#ffca28"
                                border.color: "#9b6d00"
                                border.width: 2
                                z: 10

                                Text {
                                    id: markerText
                                    anchors.centerIn: parent
                                    text: modelData.order
                                    color: "#352600"
                                    font.bold: true
                                    font.pixelSize: 15
                                }

                                ToolTip.visible: markerMouse.containsMouse
                                ToolTip.text: modelData.order + ". " + modelData.text + (root.activeTool === "select" ? " — drag or double-click to edit" : "")

                                MouseArea {
                                    id: markerMouse
                                    anchors.fill: parent
                                    enabled: root.activeTool === "select"
                                    hoverEnabled: true
                                    drag.target: marker
                                    drag.minimumX: 0
                                    drag.minimumY: 0
                                    drag.maximumX: paintSurface.width - marker.width
                                    drag.maximumY: paintSurface.height - marker.height
                                    onReleased: paintModel.moveActionMarker(modelData.id, marker.x + 18, marker.y + 18)
                                    onDoubleClicked: root.openEditAction(modelData.id, modelData.text)
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 285
                Layout.fillHeight: true
                radius: 8
                color: "#13232f"
                border.color: "#365268"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Label { text: "Action order"; color: "#eff8ff"; font.pixelSize: 16; font.bold: true }
                    Label { text: "Drag rows to rearrange the chain."; color: "#9db5c7"; wrapMode: Text.WordWrap; Layout.fillWidth: true }

                    ListView {
                        id: actionList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 6
                        clip: true
                        model: paintModel ? paintModel.actions : []

                        delegate: Item {
                            id: actionRow
                            required property var modelData
                            required property int index
                            property alias dragHandle: rowDrag
                            width: actionList.width
                            height: 54

                            Rectangle {
                                id: rowCard
                                anchors.fill: parent
                                radius: 7
                                color: root.draggedActionIndex === actionRow.index
                                    ? "#30516a"
                                    : (root.actionDropTargetIndex === actionRow.index ? "#294b3c" : "#1c3445")
                                border.color: root.actionDropTargetIndex === actionRow.index ? "#72c596" : "#466a83"

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    spacing: 7
                                    Label { text: "☰"; color: "#8fb2ca"; font.pixelSize: 17 }
                                    Rectangle {
                                        width: 28; height: 28; radius: 14; color: "#ffca28"
                                        Label { anchors.centerIn: parent; text: modelData.order; color: "#352600"; font.bold: true }
                                    }
                                    Label { text: modelData.text; color: "#f1f7fb"; elide: Text.ElideRight; Layout.fillWidth: true }
                                    ToolButton { text: "✎"; onClicked: root.openEditAction(modelData.id, modelData.text) }
                                    ToolButton { text: "×"; onClicked: paintModel.removeAction(modelData.id) }
                                }

                                MouseArea {
                                    id: rowDrag
                                    objectName: "actionOrderDragHandle_" + actionRow.index
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 42
                                    preventStealing: true
                                    cursorShape: Qt.SizeAllCursor
                                    onPressed: {
                                        root.draggedActionIndex = actionRow.index
                                        root.actionDropTargetIndex = actionRow.index
                                    }
                                    onPositionChanged: function(mouse) {
                                        if (!rowDrag.pressed)
                                            return
                                        var point = rowDrag.mapToItem(actionList, mouse.x, mouse.y)
                                        var contentY = point.y + actionList.contentY
                                        var stride = actionRow.height + actionList.spacing
                                        root.actionDropTargetIndex = Math.max(
                                            0, Math.min(actionList.count - 1, Math.floor(contentY / stride)))
                                    }
                                    onReleased: function(mouse) {
                                        var fromIndex = root.draggedActionIndex
                                        var target = root.actionDropTargetIndex
                                        root.draggedActionIndex = -1
                                        root.actionDropTargetIndex = -1
                                        paintModel.moveAction(fromIndex, target)
                                    }
                                    onCanceled: {
                                        root.draggedActionIndex = -1
                                        root.actionDropTargetIndex = -1
                                    }
                                }
                            }
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: !paintModel || paintModel.actionCount === 0
                            text: "Choose + Action, then click\nthe painting to place a task."
                            color: "#829baa"
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: actionDialog
        modal: true
        anchors.centerIn: parent
        width: 390
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            if (root.editingActionId.length > 0)
                paintModel.renameAction(root.editingActionId, actionTextField.text)
            else
                paintModel.addAction(actionTextField.text, root.pendingActionX, root.pendingActionY)
        }
        contentItem: TextField {
            id: actionTextField
            placeholderText: "What needs to be done?"
            onAccepted: actionDialog.accept()
        }
    }

    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: paintModel && paintModel.canUndo
        onActivated: paintModel.undoLastDrawing()
    }

    Dialog {
        id: paintTextDialog
        title: "Add text"
        modal: true
        anchors.centerIn: parent
        width: 390
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: paintModel.addText(
            paintTextField.text,
            root.pendingTextX,
            root.pendingTextY,
            root.brushColor,
            root.fontSize)
        contentItem: TextField {
            id: paintTextField
            placeholderText: "Text to place on the painting"
            onAccepted: paintTextDialog.accept()
        }
    }

    Dialog {
        id: clearDialog
        width: 430
        title: "Clear drawing?"
        modal: true
        anchors.centerIn: parent
        standardButtons: Dialog.Yes | Dialog.No
        onAccepted: paintModel.clearDrawing()
        contentItem: Label {
            text: "Remove all pencil, line, rectangle, and text marks?\nAction markers will remain."
            color: "#e5edf3"
        }
    }
}
