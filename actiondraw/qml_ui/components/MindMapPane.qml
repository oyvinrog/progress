pragma ComponentBehavior: Bound
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

FocusScope {
    id: pane
    signal canvasRequested()
    property var controller
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool initialized: false
    property var viewPositions: ({})
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
        function onScopeChanging(oldScope, newScope) {
            pane.viewPositions[oldScope] = { zoom: pane.zoom, x: pane.panX, y: pane.panY, initialized: pane.initialized }
            var saved = pane.viewPositions[newScope]
            pane.zoom = saved ? saved.zoom : 1
            pane.panX = saved ? saved.x : 0
            pane.panY = saved ? saved.y : 0
            pane.initialized = saved ? saved.initialized : false
            editor.close()
            if (!pane.initialized) Qt.callLater(function() { if (pane.visible) pane.fitMap() })
        }
        function onResetView() {
            pane.viewPositions = ({})
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
            Button {
                objectName: "tabMindmapCanvas"
                text: "Canvas"
                visible: pane.controller && pane.controller.tabScoped
                onClicked: pane.canvasRequested()
            }
            Button {
                objectName: "mindmapComplete"
                text: "Complete"
                enabled: pane.controller && pane.controller.selectedIds.length > 0
                onClicked: { pane.controller.toggleCompleted(); pane.forceActiveFocus() }
            }
            Button { text: "Add child"; onClicked: pane.addThought(false) }
            Button { text: "Sibling"; onClicked: pane.addThought(true) }
            Button {
                objectName: "mindmapCreateTab"
                text: "Create tab"
                enabled: pane.controller && pane.controller.canCreateTab
                onClicked: { pane.controller.createTabFromSelected(); pane.forceActiveFocus() }
            }
            Button {
                text: "Open tab"
                enabled: pane.controller && pane.controller.selectedNode.isTab === true
                onClicked: pane.controller.activate(pane.controller.selectedId)
            }
            Button { text: "Edit / Notes"; onClicked: pane.editNode() }
            Button { text: "Fold"; onClicked: pane.controller.toggleFold() }
            Button { text: "Cut"; enabled: pane.controller && pane.controller.canCut; onClicked: pane.controller.cutSelected() }
            Button { text: "Paste"; enabled: pane.controller && pane.controller.canPaste; onClicked: pane.controller.pasteSelected() }
            Button { text: "Delete"; onClicked: pane.controller.deleteSelected() }
            Button { text: "Undo"; enabled: pane.controller && pane.controller.canUndo; onClicked: pane.controller.undo() }
            Button { text: "Redo"; enabled: pane.controller && pane.controller.canRedo; onClicked: pane.controller.redo() }
            Button { text: "−"; onClicked: pane.zoomBy(1 / 1.2) }
            Button { text: "+"; onClicked: pane.zoomBy(1.2) }
            Button { text: "Fit"; onClicked: pane.fitMap() }
        }
        Label {
            Layout.fillWidth: true
            text: pane.controller && pane.controller.canPaste
                ? "Branches cut: click a destination and press Ctrl+V to move them beneath it · Escape cancels"
                : "Ctrl+drag or Ctrl+Up/Down reorders · Ctrl+click toggles selection · Shift+click selects a range · Ctrl+X / Ctrl+V moves branches · F4 completes · Arrows navigate · Tab adds a child · Ctrl+Enter opens a tab"
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
                        readonly property bool selected: pane.controller.selectedIds.indexOf(modelData.id) >= 0
                        opacity: pane.controller.cutNodeIds.indexOf(modelData.id) >= 0 ? 0.45 : 1
                        border.width: selected ? 2 : 1
                        border.color: selected ? "#a5d9ff" : "#557b98"
                        Text {
                            anchors.fill: parent
                            anchors.leftMargin: 9; anchors.rightMargin: 18
                            verticalAlignment: Text.AlignVCenter
                            text: (nodeItem.modelData.completed ? "✓ " : "") + (nodeItem.modelData.isTab ? "▣ " : "") + nodeItem.modelData.text
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
                            objectName: "mindmapNodeMouse_" + nodeItem.modelData.id
                            anchors.fill: parent
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            drag.target: pressedButtons === Qt.LeftButton ? nodeItem : null
                            drag.axis: reorderDrag ? Drag.YAxis : Drag.XAndYAxis
                            property bool wasDragged: false
                            property bool reorderDrag: false
                            function restorePosition() {
                                nodeItem.x = Qt.binding(function() { return nodeItem.modelData.x })
                                nodeItem.y = Qt.binding(function() { return nodeItem.modelData.y })
                            }
                            onPressed: function(mouse) {
                                pane.forceActiveFocus()
                                wasDragged = false
                                reorderDrag = mouse.button === Qt.LeftButton && !!(mouse.modifiers & Qt.ControlModifier)
                            }
                            onPositionChanged: if (drag.active) wasDragged = true
                            onCanceled: { restorePosition(); wasDragged = true; reorderDrag = false }
                            onReleased: function(mouse) {
                                if (!wasDragged) return
                                if (reorderDrag) {
                                    var reorderId = nodeItem.modelData.id
                                    var centerY = nodeItem.y + nodeItem.height / 2
                                    restorePosition()
                                    Qt.callLater(pane.controller.reorderNodeAt, reorderId, centerY)
                                    return
                                }
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
                                restorePosition()
                                if (targetId) Qt.callLater(pane.controller.moveNode, sourceId, targetId, placement)
                            }
                            onClicked: function(mouse) {
                                if (wasDragged) return
                                var nodeId = nodeItem.modelData.id
                                var tab = nodeItem.modelData.isTab
                                if (mouse.button === Qt.RightButton) {
                                    if (!nodeItem.selected) pane.controller.select(nodeId)
                                    nodeMenu.targetNodeId = nodeId
                                    nodeMenu.popup()
                                } else if (mouse.modifiers & Qt.ControlModifier) {
                                    pane.controller.select(nodeId, "toggle")
                                } else if (mouse.modifiers & Qt.ShiftModifier) {
                                    pane.controller.select(nodeId, "range")
                                } else {
                                    pane.controller.select(nodeId)
                                    if (tab && !(pane.controller.tabScoped && nodeItem.modelData.isViewRoot) && !pane.controller.canPaste) pane.controller.activate(nodeId)
                                }
                            }
                            onDoubleClicked: function(mouse) {
                                if (!nodeItem.modelData.isTab && !(mouse.modifiers & (Qt.ControlModifier | Qt.ShiftModifier))) pane.editNode()
                            }
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
        objectName: "mindmapNodeMenu"
        property string targetNodeId: ""
        property bool canMoveUp: false
        property bool canMoveDown: false
        onAboutToShow: {
            canMoveUp = pane.controller.canReorderNode(targetNodeId, -1)
            canMoveDown = pane.controller.canReorderNode(targetNodeId, 1)
        }
        MenuItem {
            objectName: "mindmapMoveUp"
            text: "Move up"
            enabled: nodeMenu.canMoveUp
            onTriggered: { pane.controller.reorderNode(nodeMenu.targetNodeId, -1); pane.forceActiveFocus() }
        }
        MenuItem {
            objectName: "mindmapMoveDown"
            text: "Move down"
            enabled: nodeMenu.canMoveDown
            onTriggered: { pane.controller.reorderNode(nodeMenu.targetNodeId, 1); pane.forceActiveFocus() }
        }
        MenuSeparator {}
        MenuItem { text: "Cut branches"; enabled: pane.controller && pane.controller.canCut; onTriggered: pane.controller.cutSelected() }
        MenuItem { text: "Paste beneath selected node"; enabled: pane.controller && pane.controller.canPaste; onTriggered: pane.controller.pasteSelected() }
        MenuSeparator {}
        MenuItem { text: "Add child"; onTriggered: pane.addThought(false) }
        MenuItem { text: "Add sibling"; onTriggered: pane.addThought(true) }
        MenuItem { text: "Edit / Notes"; onTriggered: pane.editNode() }
        MenuItem {
            text: "Create tab"
            enabled: pane.controller && pane.controller.canCreateTab
            onTriggered: { pane.controller.createTabFromSelected(); pane.forceActiveFocus() }
        }
        MenuItem { text: "Complete"; enabled: pane.controller && pane.controller.selectedIds.length > 0; onTriggered: pane.controller.toggleCompleted() }
        MenuItem { text: "Fold / Unfold"; onTriggered: pane.controller.toggleFold() }
        MenuItem { text: "Branch on left"; onTriggered: pane.controller.setSide("left") }
        MenuItem { text: "Branch on right"; onTriggered: pane.controller.setSide("right") }
        MenuItem { text: "Delete branch"; onTriggered: pane.controller.deleteSelected() }
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
    Shortcut { sequence: "Ctrl+X"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.cutSelected() }
    Shortcut { sequence: "Ctrl+V"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.pasteSelected() }
    Shortcut { sequence: "Escape"; enabled: pane.shortcutsEnabled && pane.controller.canPaste; onActivated: pane.controller.cancelCut() }
    Shortcut { sequence: "Shift+Left"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("left", true) }
    Shortcut { sequence: "Shift+Right"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("right", true) }
    Shortcut { sequence: "Shift+Up"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("up", true) }
    Shortcut { sequence: "Shift+Down"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("down", true) }
    Shortcut { sequence: "Tab"; enabled: pane.shortcutsEnabled; onActivated: pane.addThought(false) }
    Shortcut { sequence: "Left"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("left") }
    Shortcut { sequence: "Right"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("right") }
    Shortcut { sequence: "Up"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("up") }
    Shortcut { sequence: "Down"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.navigate("down") }
    Shortcut { sequence: "Ctrl+Up"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.reorderNode(pane.controller.selectedId, -1) }
    Shortcut { sequence: "Ctrl+Down"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.reorderNode(pane.controller.selectedId, 1) }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter"]; enabled: pane.shortcutsEnabled; onActivated: pane.controller.activate(pane.controller.selectedId) }
    Shortcut { sequence: "Return"; enabled: pane.shortcutsEnabled; onActivated: pane.addThought(true) }
    Shortcut { sequence: "F4"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.toggleCompleted() }
    Shortcut { sequence: "F2"; enabled: pane.shortcutsEnabled; onActivated: pane.editNode() }
    Shortcut { sequence: "Delete"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.deleteSelected() }
    Shortcut { sequence: "Space"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.toggleFold() }
    Shortcut { sequence: "Ctrl+Z"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.undo() }
    Shortcut { sequence: "Ctrl+Y"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.redo() }
    Shortcut { sequence: "Ctrl++"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1.2) }
    Shortcut { sequence: "Ctrl+-"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1/1.2) }
    Shortcut { sequence: "Ctrl+0"; enabled: pane.shortcutsEnabled; onActivated: pane.fitMap() }
}
