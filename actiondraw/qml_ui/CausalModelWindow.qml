import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1250; height: 820
    title: "Causal Model"
    property var modelRef
    property var hostRoot
    property string selectedNode: ""
    property string selectedEdge: ""
    property string connectSource: ""
    property string connectTarget: ""
    property point connectPoint: Qt.point(0, 0)
    property point newNodePosition: Qt.point(80, 80)
    property int draggedActionIndex: -1
    property int actionDropTargetIndex: -1
    readonly property bool canDeleteSelection: (!!selectedNode || !!selectedEdge)
        && !nodeDialog.visible && !edgeDialog.visible && !descriptionDialog.visible
        && !connectSource && draggedActionIndex < 0
    onSelectedEdgeChanged: edgesCanvas.requestPaint()
    property string statusText: ""
    function nodeById(key) {
        var nodes = modelRef.nodes
        for (var i = 0; i < nodes.length; i++) if (nodes[i].id === key) return nodes[i]
        return null
    }
    function edgeById(key) {
        var edges = modelRef.edges
        for (var i = 0; i < edges.length; i++) if (edges[i].id === key) return edges[i]
        return null
    }
    function edgeAt(x, y) {
        var edges = modelRef.edges
        for (var i = edges.length - 1; i >= 0; i--) {
            var g = edgeGeometry(edges[i])
            if (!g) continue
            var dx = g.x2-g.x1, dy = g.y2-g.y1, den = dx*dx+dy*dy
            var t = den ? Math.max(0, Math.min(1, ((x-g.x1)*dx+(y-g.y1)*dy)/den)) : 0
            if (Math.hypot(x-g.x1-t*dx, y-g.y1-t*dy) < 12) return edges[i]
        }
        return null
    }
    function deleteSelection() {
        if (!canDeleteSelection) return
        modelRef.endNodeDrag()
        var node = selectedNode, edge = selectedEdge
        selectedNode = ""; selectedEdge = ""
        if (node) modelRef.removeNode(node)
        else if (edge) modelRef.removeEdge(edge)
        board.forceActiveFocus()
    }
    function nodeItemById(key) {
        for (var i=0; i<nodesRepeater.count; i++) {
            var item=nodesRepeater.itemAt(i)
            if(item && item.modelData.id===key) return item
        }
        return null
    }
    function actionUpButtonAt(index) { return actionList.itemAtIndex(index).upButton }
    function actionDragHandleAt(index) { return actionList.itemAtIndex(index).dragHandle }
    function connectionHandleById(key) { return nodeItemById(key).connectionHandle }
    function openNewNode(x, y, kind) {
        selectedNode = ""
        selectedEdge = ""
        newNodePosition = Qt.point(Math.max(0, x), Math.max(0, y))
        nodeLabel.text = ""
        nodeType.currentIndex = Math.max(0, ["variable", "action", "outcome"].indexOf(kind))
        nodeNotes.text = ""
        nodeDialog.open()
        nodeLabel.forceActiveFocus()
    }
    function cancelConnection() {
        connectSource = ""
        connectTarget = ""
        edgesCanvas.requestPaint()
    }
    function updateConnection(point) {
        connectPoint = point
        connectTarget = ""
        if (point.x < viewport.contentX || point.x > viewport.contentX + viewport.width
                || point.y < viewport.contentY || point.y > viewport.contentY + viewport.height) {
            edgesCanvas.requestPaint()
            return
        }
        var nodes = modelRef.nodes
        for (var i = nodes.length - 1; i >= 0; i--) {
            var node = nodes[i]
            var dx = (point.x - node.x - 80) / 80
            var dy = (point.y - node.y - 45) / 45
            if (dx * dx + dy * dy <= 1) {
                connectTarget = node.id
                break
            }
        }
        edgesCanvas.requestPaint()
    }
    function finishConnection(point) {
        if (!connectSource) return
        updateConnection(point)
        var source = connectSource, target = connectTarget
        cancelConnection()
        if (target) modelRef.addEdge(source, target, "", "")
    }
    function openNode(node) {
        selectedNode = node.id
        selectedEdge = ""
        nodeLabel.text = node.label
        nodeType.currentIndex = ["variable", "action", "outcome"].indexOf(node.type)
        nodeNotes.text = node.notes
        nodeDialog.open()
        nodeLabel.forceActiveFocus()
    }
    function saveNode() {
        var ok = selectedNode
            ? modelRef.editNode(selectedNode, nodeLabel.text, nodeType.currentText, nodeNotes.text)
            : modelRef.addNode(nodeLabel.text, nodeType.currentText, newNodePosition.x, newNodePosition.y, nodeNotes.text)
        if (ok) nodeDialog.close()
    }
    function openEdge(edge) {
        selectedEdge = edge.id
        selectedNode = ""
        edgeWeight.text = edge.likelihood === null ? "" : String(edge.likelihood)
        edgeNotes.text = edge.notes
        edgeDialog.open()
        edgeWeight.forceActiveFocus()
    }
    function saveEdge() {
        if (modelRef.editEdge(selectedEdge, edgeWeight.text, edgeNotes.text)) edgeDialog.close()
    }
    function edgeGeometry(edge) {
        var a = nodeById(edge.source), b = nodeById(edge.target)
        if (!a || !b) return null
        var dx = b.x-a.x, dy = b.y-a.y, d = Math.sqrt(dx*dx+dy*dy)
        if (d < 1) return null
        // Intersections with the elliptical node boundary.
        var scale = 1 / Math.sqrt(dx*dx/(80*80) + dy*dy/(45*45))
        return {x1:a.x+80+dx*scale, y1:a.y+45+dy*scale,
                x2:b.x+80-dx*scale, y2:b.y+45-dy*scale, angle:Math.atan2(dy,dx)}
    }
    Connections {
        target: modelRef
        function onChanged() {
            edgesCanvas.requestPaint()
            if (root.selectedNode && !root.nodeById(root.selectedNode)) root.selectedNode = ""
            if (root.selectedEdge && !root.edgeById(root.selectedEdge)) root.selectedEdge = ""
        }
        function onSceneChanged() { edgesCanvas.requestPaint() }
        function onResetView() {
            nodeDialog.close(); edgeDialog.close(); descriptionDialog.close()
            root.selectedNode = ""; root.selectedEdge = ""; root.connectSource = ""
            root.cancelConnection(); root.statusText = ""
            root.draggedActionIndex = -1; root.actionDropTargetIndex = -1
            viewport.contentX = 0; viewport.contentY = 0
        }
    }
    Shortcut { sequences: [StandardKey.Undo]; onActivated: modelRef.undo() }
    Shortcut { sequences: [StandardKey.Redo]; onActivated: modelRef.redo() }
    Shortcut { sequence: "Delete"; enabled: root.canDeleteSelection; onActivated: root.deleteSelection() }
    Shortcut { sequence: "Escape"; enabled: !!root.connectSource; onActivated: root.cancelConnection() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 10
        RowLayout {
            Button { text: "Add node"; onClicked: root.openNewNode(viewport.contentX + 80, viewport.contentY + 80) }
            Button {
                objectName: "causalAddAction"
                text: "+ Add action"
                onClicked: root.openNewNode(viewport.contentX + 80, viewport.contentY + 80, "action")
            }
            Button {
                objectName: "causalMakeAction"
                text: "Make action"
                visible: !!root.selectedNode && !!root.nodeById(root.selectedNode)
                         && root.nodeById(root.selectedNode).type !== "action"
                onClicked: {
                    var node = root.nodeById(root.selectedNode)
                    if (node) modelRef.editNode(node.id, node.label, "action", node.notes)
                }
            }
            Button { text: "Undo"; enabled: modelRef.canUndo; onClicked: modelRef.undo() }
            Button { text: "Redo"; enabled: modelRef.canRedo; onClicked: modelRef.redo() }
            Button { objectName: "causalDeleteSelection"; text: "Delete"; enabled: root.canDeleteSelection; onClicked: root.deleteSelection() }
            Button { text: "Assumptions / conclusions"; onClicked: { descriptionText.text = modelRef.description; descriptionDialog.open() } }
        }
        Label {
            text: root.connectSource ? "Drop on the effect node to connect. Esc cancels."
                : "Double-click to add or edit. Drag → to connect, or a node to move. Select a node or edge and press Delete to remove it."
            Layout.fillWidth: true
            wrapMode: Text.Wrap
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Flickable {
                id: viewport
                objectName: "causalViewport"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.minimumWidth: 200; Layout.preferredWidth: 900
                clip: true
                contentWidth: board.width; contentHeight: board.height
                ScrollBar.horizontal: ScrollBar {}
                ScrollBar.vertical: ScrollBar {}
                Item {
                    id: board
                    objectName: "causalBoard"
                    width: { var extent = 1600; var ns = modelRef.nodes; for(var i=0;i<ns.length;i++) extent=Math.max(extent,ns[i].x+400); return extent }
                    height: { var extent = 1000; var ns = modelRef.nodes; for(var i=0;i<ns.length;i++) extent=Math.max(extent,ns[i].y+300); return extent }
                    Canvas {
                        id: edgesCanvas
                        anchors.fill: parent
                        onWidthChanged: requestPaint()
                        onHeightChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d"); ctx.clearRect(0,0,width,height)
                            ctx.fillStyle = "#fafbfc"; ctx.fillRect(0,0,width,height)
                            ctx.strokeStyle = "#e8edf0"; ctx.lineWidth = 1; ctx.beginPath()
                            for(var x=0;x<width;x+=25) {ctx.moveTo(x,0);ctx.lineTo(x,height)}
                            for(var y=0;y<height;y+=25) {ctx.moveTo(0,y);ctx.lineTo(width,y)}
                            ctx.stroke()
                            var edges = modelRef.edges
                            for(var i=0;i<edges.length;i++) {
                                var e = edges[i], g = root.edgeGeometry(e); if(!g) continue
                                ctx.strokeStyle = e.id === root.selectedEdge ? "#1976d2" : "#37474f"
                                ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = 2
                                ctx.beginPath(); ctx.moveTo(g.x1,g.y1); ctx.lineTo(g.x2,g.y2); ctx.stroke()
                                ctx.beginPath(); ctx.moveTo(g.x2,g.y2)
                                ctx.lineTo(g.x2-12*Math.cos(g.angle-0.45),g.y2-12*Math.sin(g.angle-0.45))
                                ctx.lineTo(g.x2-12*Math.cos(g.angle+0.45),g.y2-12*Math.sin(g.angle+0.45));ctx.closePath();ctx.fill()
                                if(e.likelihood !== null) {
                                    var label = String(e.likelihood)+" %", mx=(g.x1+g.x2)/2, my=(g.y1+g.y2)/2
                                    ctx.font="14px sans-serif";var w=ctx.measureText(label).width
                                    ctx.fillStyle="#fafbfc";ctx.fillRect(mx-w/2-4,my-12,w+8,21)
                                    ctx.fillStyle="#263238";ctx.textAlign="center";ctx.fillText(label,mx,my+4)
                                }
                            }
                            if (root.connectSource) {
                                var source = root.nodeById(root.connectSource)
                                if (source) {
                                    var preview = root.connectTarget && root.connectTarget !== root.connectSource
                                        ? root.edgeGeometry({source: root.connectSource, target: root.connectTarget}) : null
                                    if (!preview) {
                                        var sx = source.x + 80, sy = source.y + 45
                                        preview = {x1: sx, y1: sy, x2: root.connectPoint.x, y2: root.connectPoint.y,
                                                   angle: Math.atan2(root.connectPoint.y - sy, root.connectPoint.x - sx)}
                                    }
                                    ctx.strokeStyle = "#1976d2"; ctx.fillStyle = "#1976d2"; ctx.lineWidth = 2
                                    ctx.beginPath(); ctx.moveTo(preview.x1, preview.y1); ctx.lineTo(preview.x2, preview.y2); ctx.stroke()
                                    ctx.beginPath(); ctx.moveTo(preview.x2, preview.y2)
                                    ctx.lineTo(preview.x2-12*Math.cos(preview.angle-0.45),preview.y2-12*Math.sin(preview.angle-0.45))
                                    ctx.lineTo(preview.x2-12*Math.cos(preview.angle+0.45),preview.y2-12*Math.sin(preview.angle+0.45))
                                    ctx.closePath(); ctx.fill()
                                }
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            onDoubleClicked: function(mouse) {
                                var edge = root.edgeAt(mouse.x, mouse.y)
                                if (edge) root.openEdge(edge)
                                else root.openNewNode(mouse.x - 80, mouse.y - 45)
                            }
                            onClicked: function(mouse) {
                                board.forceActiveFocus()
                                var edge = root.edgeAt(mouse.x, mouse.y)
                                root.selectedNode = ""
                                root.selectedEdge = edge ? edge.id : ""
                            }
                        }
                    }
                    Repeater {
                        id: nodesRepeater
                        model: modelRef.nodes
                        delegate: Rectangle {
                            id: nodeItem
                            objectName: "causalNode_" + modelData.id
                            required property var modelData
                            property alias connectionHandle: connectionHandle
                            x: modelData.x; y: modelData.y
                            width: 160; height: 90; radius: 45
                            color: modelData.type === "action" ? "#fff0bf" : modelData.type === "outcome" ? "#e2f3e5" : "white"
                            border.color: root.connectTarget === modelData.id ? "#2e7d32" : root.selectedNode === modelData.id ? "#1976d2" : "#455a64"; border.width: root.connectTarget === modelData.id ? 3 : 2
                            Text {
                                anchors.fill: parent; anchors.margins: 10
                                text: { var prefix="";var actions=modelRef.actions;for(var i=0;i<actions.length;i++)if(actions[i].id===modelData.id)prefix=actions[i].order+". ";return prefix+modelData.label }
                                wrapMode: Text.Wrap; elide: Text.ElideRight
                                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter; color: "#263238"
                            }
                            MouseArea {
                                anchors.fill: parent
                                preventStealing: true
                                property real startX
                                property real startY
                                property real downX
                                property real downY
                                property bool moved: false
                                onPressed: function(mouse) {
                                    board.forceActiveFocus()
                                    root.selectedNode=modelData.id
                                    root.selectedEdge=""
                                    startX=modelData.x;startY=modelData.y
                                    var point=mapToItem(board,mouse.x,mouse.y);downX=point.x;downY=point.y;moved=false
                                    modelRef.beginNodeDrag()
                                }
                                onPositionChanged: function(mouse) {
                                    if(!pressed) return
                                    var point=mapToItem(board,mouse.x,mouse.y)
                                    if(Math.abs(point.x-downX)+Math.abs(point.y-downY)>3) moved=true
                                    nodeItem.x = Math.max(0,startX+point.x-downX)
                                    nodeItem.y = Math.max(0,startY+point.y-downY)
                                    modelRef.moveNode(modelData.id,nodeItem.x,nodeItem.y)
                                }
                                onReleased: {
                                    modelRef.endNodeDrag()
                                }
                                onCanceled: modelRef.endNodeDrag()
                                onDoubleClicked: if(!moved) root.openNode(modelData)
                            }
                            Rectangle {
                                id: connectionHandle
                                x: parent.width - width / 2; y: (parent.height - height) / 2
                                width: 26; height: 26; radius: 5
                                color: connectionMouse.pressed ? "#1976d2" : "#e3effb"
                                border.color: "#1976d2"
                                Text { anchors.centerIn: parent; text: "→"; color: connectionMouse.pressed ? "white" : "#1565c0"; font.pixelSize: 18 }
                                ToolTip.visible: connectionMouse.containsMouse && !connectionMouse.pressed
                                ToolTip.text: "Drag to another node to connect"
                                MouseArea {
                                    id: connectionMouse
                                    anchors.fill: parent
                                    property point pressPoint
                                    property bool dragged: false
                                    hoverEnabled: true
                                    preventStealing: true
                                    cursorShape: Qt.CrossCursor
                                    onPressed: function(mouse) {
                                        pressPoint = mapToItem(board, mouse.x, mouse.y)
                                        dragged = false
                                        root.connectSource = modelData.id
                                        root.updateConnection(pressPoint)
                                    }
                                    onPositionChanged: function(mouse) {
                                        if (pressed && root.connectSource) {
                                            var point = mapToItem(board, mouse.x, mouse.y)
                                            if (Math.hypot(point.x - pressPoint.x, point.y - pressPoint.y) > 3) dragged = true
                                            root.updateConnection(point)
                                        }
                                    }
                                    onReleased: function(mouse) {
                                        if (dragged) root.finishConnection(mapToItem(board, mouse.x, mouse.y))
                                        else root.cancelConnection()
                                    }
                                    onCanceled: root.cancelConnection()
                                }
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.minimumWidth: 270; Layout.preferredWidth: 270; Layout.maximumWidth: 270; Layout.fillHeight: true
                Label { text: "Action order (" + modelRef.actions.length + ")"; font.bold: true }
                Label { text: "Drag the ≡ handles to reorder actions, then add the list to ActionDraw or the mindmap."; wrapMode: Text.Wrap; Layout.fillWidth: true }
                ListView {
                    id: actionList
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: modelRef.actions
                    spacing: 4
                    delegate: Rectangle {
                        id: actionRow
                        required property var modelData
                        required property int index
                        property alias upButton: upButton
                        property alias dragHandle: actionDrag
                        width: actionList.width
                        height: Math.max(54, actionContents.implicitHeight + 12)
                        radius: 6
                        color: root.actionDropTargetIndex === index ? "#e2f3e5" : "#fff0bf"
                        border.color: root.draggedActionIndex === index ? "#1976d2" : "#bf9b3d"
                        RowLayout {
                            id: actionContents
                            anchors.fill: parent; anchors.margins: 6
                            Label { text: "≡"; color: "#695115"; Layout.preferredWidth: 26; font.pixelSize: 22 }
                            Label { text: modelData.order + ". " + modelData.label; color: "#263238"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Button { id: upButton; Layout.preferredWidth: 32; Layout.maximumWidth: 32; objectName: "causalActionUp_" + index; text: "↑"; enabled: index>0; onClicked: modelRef.moveAction(index,index-1) }
                            Button { Layout.preferredWidth: 32; Layout.maximumWidth: 32; text: "↓"; enabled: index<actionList.count-1; onClicked: modelRef.moveAction(index,index+1) }
                        }
                        MouseArea {
                            id: actionDrag
                            anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                            width: 38
                            preventStealing: true
                            cursorShape: Qt.SizeAllCursor
                            onPressed: {
                                root.draggedActionIndex = index
                                root.actionDropTargetIndex = index
                            }
                            onPositionChanged: function(mouse) {
                                if (!pressed) return
                                var point = mapToItem(actionList.contentItem, mouse.x, mouse.y)
                                var target = actionList.indexAt(1, point.y)
                                if (target >= 0) root.actionDropTargetIndex = target
                            }
                            onReleased: {
                                var source = root.draggedActionIndex, target = root.actionDropTargetIndex
                                root.draggedActionIndex = -1; root.actionDropTargetIndex = -1
                                modelRef.moveAction(source, target)
                            }
                            onCanceled: { root.draggedActionIndex = -1; root.actionDropTargetIndex = -1 }
                        }
                    }
                    Label {
                        anchors.centerIn: parent
                        width: parent.width - 20
                        visible: actionList.count === 0
                        text: "Use + Add action, or select a diagram node and choose Make action."
                        wrapMode: Text.Wrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
                Button {
                    objectName: "causalAddToActionDraw"
                    text: "Add to ActionDraw"; Layout.fillWidth: true
                    enabled: modelRef.actions.length>0 && !modelRef.imported && !!hostRoot
                    onClicked: {
                        var point=hostRoot.actionPaintImportPosition()
                        var created=hostRoot.diagramModelRef.createTaskChainAtPosition(modelRef.orderedTitles,point.x,point.y)
                        if(created.length===modelRef.actions.length) {modelRef.markImported();root.statusText="Actions added to ActionDraw"}
                        else root.statusText="Could not add every action"
                    }
                }
                Button {
                    objectName: "causalAddToMindmap"
                    text: "Add to mindmap"; Layout.fillWidth: true
                    enabled: modelRef.actions.length>0 && !!hostRoot && !!hostRoot.projectManagerRef
                    onClicked: {
                        var created=hostRoot.projectManagerRef.addCausalModelToMindmap()
                        root.statusText=created.length===modelRef.actions.length ? "Actions added to mindmap" : "Could not add every action"
                    }
                }
            }
        }
        Label { text: modelRef.validationError || root.statusText; color: modelRef.validationError ? "#b71c1c" : palette.text; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Label { text: "Edge percentages are estimated likelihoods. They do not calculate outcome probabilities."; font.pixelSize: 12 }
    }
    Dialog {
        id: nodeDialog; title: root.selectedNode ? "Edit node" : "Add node"
        anchors.centerIn: parent; modal: true; width: 440
        ColumnLayout {
            anchors.fill: parent
            TextField {
                id: nodeLabel
                objectName: "causalNodeLabel"
                placeholderText: "Label"
                Layout.fillWidth: true
                onAccepted: root.saveNode()
            }
            Label { text: "Node type" }
            ComboBox { id: nodeType; objectName: "causalNodeType"; model: ["variable", "action", "outcome"] }
            Label {
                text: nodeType.currentText === "action"
                    ? "This node will be included in the action list for ActionDraw and the mindmap."
                    : "Choose action for a task you want to add to ActionDraw or the mindmap."
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
            TextArea { id: nodeNotes; placeholderText: "Notes"; Layout.fillWidth: true; Layout.preferredHeight: 130; wrapMode: TextEdit.Wrap }
            RowLayout {
                Button {
                    objectName: "causalNodeSave"
                    text: "Save"
                    onClicked: root.saveNode()
                }
                Button { text: "Delete"; visible: !!root.selectedNode; onClicked: {modelRef.removeNode(root.selectedNode);root.selectedNode="";nodeDialog.close()} }
                Button { text: "Cancel"; onClicked: nodeDialog.close() }
            }
            Label { text: modelRef.validationError; color: "#b71c1c"; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
    Dialog {
        id: edgeDialog; title: "Edit causal connection"; anchors.centerIn: parent; modal: true; width: 440
        ColumnLayout {
            anchors.fill: parent
            TextField {
                id: edgeWeight
                objectName: "causalEdgeWeight"
                placeholderText: "Likelihood 0–100% (optional)"
                Layout.fillWidth: true
                onAccepted: root.saveEdge()
            }
            TextArea {
                id: edgeNotes
                objectName: "causalEdgeNotes"
                placeholderText: "Explanation / assumptions (Shift+Enter for a new line)"
                Layout.fillWidth: true
                Layout.preferredHeight: 130
                wrapMode: TextEdit.Wrap
                Keys.onPressed: function(event) {
                    if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                            && !(event.modifiers & Qt.ShiftModifier)) {
                        event.accepted = true
                        root.saveEdge()
                    }
                }
            }
            RowLayout {
                Button { objectName: "causalEdgeSave"; text: "Save"; onClicked: root.saveEdge() }
                Button { text: "Delete"; onClicked: {modelRef.removeEdge(root.selectedEdge);root.selectedEdge="";edgeDialog.close()} }
                Button { text: "Cancel"; onClicked: edgeDialog.close() }
            }
            Label { text: modelRef.validationError; color: "#b71c1c"; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
    Dialog {
        id: descriptionDialog; title: "Assumptions and conclusions"; anchors.centerIn: parent; modal: true; width: 540
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: modelRef.setDescription(descriptionText.text)
        TextArea { id: descriptionText; width: parent.width; height: 240; wrapMode: TextEdit.Wrap }
    }
}
