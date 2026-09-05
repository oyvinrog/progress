pragma ComponentBehavior: Bound
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

FocusScope {
    id: pane
    property var controller
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool initialized: false
    readonly property bool shortcutsEnabled: visible && activeFocus && !editor.visible && !nodeMenu.visible

    function fitMap() {
        if (!controller || viewport.width <= 0 || viewport.height <= 0) return
        var nodes = controller.nodes
        var left = 0, right = 0, top = 0, bottom = 0
        for (var i = 0; i < nodes.length; ++i) {
            var n = nodes[i]
            left = Math.min(left, n.x); right = Math.max(right, n.x + n.width)
            top = Math.min(top, n.y); bottom = Math.max(bottom, n.y + n.height)
        }
        zoom = Math.max(0.2, Math.min(1.4, (viewport.width - 80) / Math.max(1, right-left),
                                                   (viewport.height - 80) / Math.max(1, bottom-top)))
        panX = -(left + right) / 2 * zoom
        panY = -(top + bottom) / 2 * zoom
        initialized = true
    }
    function zoomBy(factor) { zoom = Math.max(0.2, Math.min(4, zoom * factor)) }
    function revealNode(nodeId) {
        if (!visible || !controller) return
        var nodes = controller.nodes
        for (var i = 0; i < nodes.length; ++i) {
            var n = nodes[i]
            if (n.id !== nodeId) continue
            var left = viewport.width / 2 + panX + n.x * zoom
            var top = viewport.height / 2 + panY + n.y * zoom
            var width = n.width * zoom, height = n.height * zoom
            var margin = 24
            if (width > viewport.width - margin * 2) panX += (viewport.width - width) / 2 - left
            else if (left < margin) panX += margin - left
            else if (left + width > viewport.width - margin) panX += viewport.width - margin - left - width
            if (height > viewport.height - margin * 2) panY += (viewport.height - height) / 2 - top
            else if (top < margin) panY += margin - top
            else if (top + height > viewport.height - margin) panY += viewport.height - margin - top - height
            return
        }
    }
    function editNode() {
        if (!controller) return
        var node = controller.selectedNode
        titleField.text = node.text || ""
        titleField.readOnly = !!node.isTab
        noteField.text = node.note || ""
        editor.open()
    }
    function addThought(sibling) {
        controller.addThought(sibling)
        editNode()
    }
    onVisibleChanged: if (visible) {
        forceActiveFocus()
        if (!initialized) Qt.callLater(fitMap)
    }
    Connections {
        target: pane.controller
        function onSceneChanged() { edges.requestPaint() }
        function onRevealNode(nodeId) { pane.revealNode(nodeId) }
        function onResetView() {
            pane.initialized = false
            pane.zoom = 1; pane.panX = 0; pane.panY = 0
            editor.close()
            titleField.text = ""; noteField.text = ""
            if (pane.visible) Qt.callLater(pane.fitMap)
        }
    }
    Rectangle { anchors.fill: parent; color: "#101b25"; radius: 10 }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8
        Flow {
            Layout.fillWidth: true
            spacing: 5
            Button { text: "Add child"; onClicked: pane.addThought(false) }
            Button { text: "Sibling"; onClicked: pane.addThought(true) }
            Button {
                text: "Open tab"
                enabled: pane.controller && pane.controller.selectedNode.isTab === true
                onClicked: pane.controller.activate(pane.controller.selectedId)
            }
            Button { text: "Edit / Notes"; onClicked: pane.editNode() }
            Button { text: "Fold"; onClicked: pane.controller.toggleFold() }
            Button { text: "Delete"; onClicked: pane.controller.deleteSelected() }
            Button { text: "Undo"; enabled: pane.controller && pane.controller.canUndo; onClicked: pane.controller.undo() }
            Button { text: "Redo"; enabled: pane.controller && pane.controller.canRedo; onClicked: pane.controller.redo() }
            Button { text: "−"; onClicked: pane.zoomBy(1 / 1.2) }
            Button { text: "+"; onClicked: pane.zoomBy(1.2) }
            Button { text: "Fit"; onClicked: pane.fitMap() }
        }
        Label {
            Layout.fillWidth: true
            text: "Arrows select · Tab adds a child · Ctrl+Enter opens a tab · Ctrl+click selects a tab; click opens it · Drag to nest or reorder"
            wrapMode: Text.WordWrap
            color: "#a9bfd1"
        }
        Item {
            id: viewport
            objectName: "mindmapViewport"
            onWidthChanged: if (pane.visible && !pane.initialized) Qt.callLater(pane.fitMap)
            onHeightChanged: if (pane.visible && !pane.initialized) Qt.callLater(pane.fitMap)
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            MouseArea {
                anchors.fill: parent
                property point lastPosition
                onPressed: function(mouse) {
                    pane.forceActiveFocus()
                    lastPosition = Qt.point(mouse.x, mouse.y)
                }
                onPositionChanged: function(mouse) {
                    if (pressed) {
                        pane.panX += mouse.x - lastPosition.x
                        pane.panY += mouse.y - lastPosition.y
                        lastPosition = Qt.point(mouse.x, mouse.y)
                    }
                }
                onWheel: function(wheel) {
                    var oldZoom = pane.zoom
                    pane.zoomBy(wheel.angleDelta.y > 0 ? 1.15 : 1 / 1.15)
                    var ratio = pane.zoom / oldZoom
                    pane.panX = (pane.panX - wheel.x + viewport.width / 2) * ratio + wheel.x - viewport.width / 2
                    pane.panY = (pane.panY - wheel.y + viewport.height / 2) * ratio + wheel.y - viewport.height / 2
                    wheel.accepted = true
                }
            }
            Canvas {
                id: edges
                anchors.fill: parent
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.clearRect(0, 0, width, height)
                    if (!pane.controller) return
                    ctx.save()
                    ctx.translate(viewport.width / 2 + pane.panX, viewport.height / 2 + pane.panY)
                    ctx.scale(pane.zoom, pane.zoom)
                    ctx.strokeStyle = "#658ba8"; ctx.lineWidth = 1.5
                    var lines = pane.controller.edges
                    for (var i = 0; i < lines.length; ++i) {
                        var e = lines[i], middle = (e.x1 + e.x2) / 2
                        ctx.beginPath(); ctx.moveTo(e.x1, e.y1)
                        ctx.bezierCurveTo(middle, e.y1, middle, e.y2, e.x2, e.y2)
                        ctx.stroke()
                    }
                    ctx.restore()
                }
            }
            Item {
                id: world
                x: viewport.width / 2 + pane.panX
                y: viewport.height / 2 + pane.panY
                scale: pane.zoom
                transformOrigin: Item.TopLeft
                Repeater {
                    model: pane.controller ? pane.controller.nodes : []
                    delegate: Rectangle {
                        id: nodeItem
                        required property var modelData
                        objectName: "mindmapNode_" + modelData.id
                        x: modelData.x; y: modelData.y
                        width: modelData.width; height: modelData.height
                        radius: 8
                        color: modelData.isTab ? "#254d6c" : "#223442"
                        border.width: pane.controller.selectedId === modelData.id ? 2 : 1
                        border.color: pane.controller.selectedId === modelData.id ? "#a5d9ff" : "#557b98"
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 9; anchors.rightMargin: 18
                            verticalAlignment: Text.AlignVCenter
                            text: (nodeItem.modelData.isTab ? "▣ " : "") + nodeItem.modelData.text
                            font.pixelSize: 14
                            color: "#e5f0fa"; elide: Text.ElideRight
                        }
                        Text {
                            anchors.right: parent.right; anchors.rightMargin: 5
                            anchors.verticalCenter: parent.verticalCenter
                            text: nodeItem.modelData.hasChildren ? (nodeItem.modelData.folded ? "+" : "−") : ""
                            color: "#a5d9ff"
                        }
                        MouseArea {
                            id: nodeMouse
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            drag.target: pressedButtons === Qt.LeftButton ? nodeItem : null
                            property bool wasDragged: false
                            onPressed: {
                                pane.forceActiveFocus()
                                wasDragged = false
                            }
                            onPositionChanged: if (drag.active) wasDragged = true
                            onReleased: function(mouse) {
                                if (!wasDragged) return
                                var point = nodeItem.mapToItem(world, mouse.x, mouse.y)
                                var nodes = pane.controller.nodes
                                var targetId = "", placement = "child"
                                for (var i = 0; i < nodes.length; ++i) {
                                    var n = nodes[i]
                                    if (n.id === nodeItem.modelData.id) continue
                                    if (point.x >= n.x && point.x <= n.x + n.width && point.y >= n.y && point.y <= n.y + n.height) {
                                        targetId = n.id
                                        var relativeY = (point.y - n.y) / n.height
                                        placement = relativeY < 0.25 ? "before" : relativeY > 0.75 ? "after" : "child"
                                        break
                                    }
                                }
                                var sourceId = nodeItem.modelData.id
                                nodeItem.x = Qt.binding(function() { return nodeItem.modelData.x })
                                nodeItem.y = Qt.binding(function() { return nodeItem.modelData.y })
                                if (targetId) Qt.callLater(pane.controller.moveNode, sourceId, targetId, placement)
                            }
                            onClicked: function(mouse) {
                                if (wasDragged) return
                                var nodeId = nodeItem.modelData.id
                                var tab = nodeItem.modelData.isTab
                                pane.controller.select(nodeId)
                                if (mouse.button === Qt.RightButton) nodeMenu.popup()
                                else if (tab && !(mouse.modifiers & Qt.ControlModifier)) pane.controller.activate(nodeId)
                            }
                            onDoubleClicked: if (!nodeItem.modelData.isTab) pane.editNode()
                            ToolTip {
                                y: nodeItem.height + 8
                                delay: 800
                                visible: nodeMouse.containsMouse && !nodeMouse.pressed
                                text: nodeItem.modelData.text + (nodeItem.modelData.note ? "\n\n" + nodeItem.modelData.note : "")
                            }
                        }
                    }
                }
            }
        }
    }
    onZoomChanged: edges.requestPaint()
    onPanXChanged: edges.requestPaint()
    onPanYChanged: edges.requestPaint()
    Menu {
        id: nodeMenu
        MenuItem { text: "Add child"; onTriggered: pane.addThought(false) }
        MenuItem { text: "Add sibling"; onTriggered: pane.addThought(true) }
        MenuItem { text: "Edit / Notes"; onTriggered: pane.editNode() }
        MenuItem { text: "Fold / Unfold"; onTriggered: pane.controller.toggleFold() }
        MenuItem { text: "Branch on left"; onTriggered: pane.controller.setSide("left") }
        MenuItem { text: "Branch on right"; onTriggered: pane.controller.setSide("right") }
        MenuItem { text: "Delete thought branch"; onTriggered: pane.controller.deleteSelected() }
    }
    Dialog {
        id: editor
        objectName: "mindmapNodeEditor"
        title: "Thought and notes"
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, pane.width - 20)
        standardButtons: Dialog.Ok | Dialog.Cancel
        ColumnLayout {
            anchors.fill: parent
            TextField {
                id: titleField
                objectName: "mindmapNodeTitle"
                Layout.fillWidth: true
                placeholderText: "Thought"
                onAccepted: editor.accept()
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 220
                TextArea { id: noteField; placeholderText: "Notes"; wrapMode: TextEdit.Wrap }
            }
        }
        onOpened: {
            if (titleField.readOnly) {
                noteField.forceActiveFocus()
            } else {
                titleField.forceActiveFocus()
                titleField.selectAll()
            }
        }
        onAccepted: {
            pane.controller.editSelected(titleField.text, noteField.text)
            titleField.text = ""; noteField.text = ""
            pane.forceActiveFocus()
        }
        onRejected: { titleField.text = ""; noteField.text = ""; pane.forceActiveFocus() }
    }
    Shortcut { sequence: "Tab"; enabled: pane.shortcutsEnabled; onActivated: pane.addThought(false) }
    Shortcut { sequence: "Left"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("left") }
    Shortcut { sequence: "Right"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("right") }
    Shortcut { sequence: "Up"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("up") }
    Shortcut { sequence: "Down"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("down") }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter"]; enabled: pane.shortcutsEnabled; onActivated: pane.controller.activate(pane.controller.selectedId) }
    Shortcut { sequence: "Return"; enabled: pane.shortcutsEnabled; onActivated: pane.addThought(true) }
    Shortcut { sequence: "F2"; enabled: pane.shortcutsEnabled; onActivated: pane.editNode() }
    Shortcut { sequence: "Delete"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.deleteSelected() }
    Shortcut { sequence: "Space"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.toggleFold() }
    Shortcut { sequence: "Ctrl+Z"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.undo() }
    Shortcut { sequence: "Ctrl+Y"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.redo() }
    Shortcut { sequence: "Ctrl++"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1.2) }
    Shortcut { sequence: "Ctrl+-"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1/1.2) }
    Shortcut { sequence: "Ctrl+0"; enabled: pane.shortcutsEnabled; onActivated: pane.fitMap() }
}
