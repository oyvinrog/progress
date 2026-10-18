pragma ComponentBehavior: Bound
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

FocusScope {
    id: pane
    signal assessmentRequested()
    signal actionPaintRequested()
    signal causalDiagramRequested()
    signal thoughtWanderingRequested()
    property var tabModel: null
    property int assessmentLevel: 0
    property bool toolDialogOpen: false
    function refreshAssessment() {
        assessmentLevel = tabModel && tabModel.currentTabIndex >= 0
            ? tabModel.getAssessmentLevel(tabModel.currentTabIndex) : 0
    }
    Component.onCompleted: {
        refreshAssessment()
        Qt.callLater(function() { if (pane.visible) pane.focusMap() })
    }
    Connections {
        target: pane.tabModel
        function onCurrentTabChanged() { pane.refreshAssessment() }
        function onCurrentTabIndexChanged() { pane.refreshAssessment() }
        function onAssessmentChanged(tabIndex) {
            if (tabIndex === pane.tabModel.currentTabIndex) pane.refreshAssessment()
        }
    }
    onToolDialogOpenChanged: if (!toolDialogOpen && visible) Qt.callLater(focusMap)
    component IconMenuItem: MenuItem {
        property string iconKey: ""
        icon.source: Qt.resolvedUrl("../icons/" + iconKey + ".svg")
        icon.width: 16
        icon.height: 16
        icon.color: enabled ? palette.text : palette.mid
    }
    component CompanionButton: ToolButton {
        id: companion
        property string label: ""
        property string iconKey: ""
        property bool assessment: false
        readonly property real labeledWidth: labelMetrics.width + 40
        implicitWidth: mindmapToolbar.compactTools ? 32 : labeledWidth
        implicitHeight: 32
        enabled: !!pane.tabModel && pane.tabModel.currentTabIndex >= 0
        Accessible.name: label
        ToolTip.visible: hovered
        readonly property string toolTipText: label + " — " + (pane.tabModel ? pane.tabModel.currentTabName : "")
        ToolTip.text: toolTipText
        contentItem: Row {
            spacing: 6
            AssessmentSmiley {
                visible: companion.assessment
                width: 20; height: 20
                anchors.verticalCenter: parent.verticalCenter
                level: pane.assessmentLevel
            }
            Image {
                visible: !companion.assessment
                width: 16; height: 16
                anchors.verticalCenter: parent.verticalCenter
                source: companion.iconKey ? "../icons/" + companion.iconKey + ".svg" : ""
            }
            Text {
                visible: !mindmapToolbar.compactTools
                text: companion.label
                font: companion.font
                color: "#d6e2ee"
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        TextMetrics { id: labelMetrics; font: companion.font; text: companion.label }
    }
    signal canvasRequested()
    signal branchOpmlExportRequested(string nodeId)
    signal reminderRequested(string nodeId)
    signal quickReminderRequested(string nodeId, int minutesFromNow)
    signal clearReminderRequested(string nodeId)
    property bool reminderDialogOpen: false
    property var controller
    // Read Python scene/selection properties once per notification, not per delegate.
    readonly property var sceneData: controller ? controller.scene : ({nodes: [], edges: []})
    readonly property var sceneNodes: sceneData.nodes
    readonly property var sceneEdges: sceneData.edges
    readonly property bool hasRunningDeadlines: sceneNodes.some(function(node) {
        return node.deadlineActive && node.deadlineStart + node.deadlineDuration > pane.deadlineNow
    })
    readonly property var selectedNodeSet: new Set(controller ? controller.selectedIds : [])
    readonly property var cutNodeSet: new Set(controller ? controller.cutNodeIds : [])
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool initialized: false
    property var viewPositions: ({})
    property string navigationHighlightId: ""
    property real navigationHighlightOpacity: 0
    property string hoveredNodeId: ""
    property bool nodePressed: false
    property double deadlineNow: Date.now() / 1000
    Timer {
        objectName: "mindmapDeadlineTimer"
        interval: 1000
        repeat: true
        running: pane.visible && pane.hasRunningDeadlines
            && pane.Window.window !== null && pane.Window.window.visible
            && pane.Window.window.visibility !== Window.Minimized
        onRunningChanged: if (running) pane.deadlineNow = Date.now() / 1000
        onTriggered: pane.deadlineNow = Date.now() / 1000
    }
    Timer {
        id: insertionHoverExit
        interval: 120
        onTriggered: {
            for (var i = 0; i < insertionButtons.count; ++i) {
                var button = insertionButtons.itemAt(i)
                if (button && button.hovered) return
            }
            pane.hoveredNodeId = ""
        }
    }
    readonly property bool shortcutsEnabled: visible && activeFocus && !toolDialogOpen && !editor.visible && !quickChildDialog.visible && !nodeMenu.visible && !actionsButton.activeFocus && !prioritySlider.activeFocus && !actionsMenu.visible && !helpDialog.visible && !deadlineDialog.visible && !tabReferenceDialog.visible && !nodeGoalRangeDialog.visible && !reminderDialogOpen
    readonly property bool searching: controller && controller.searchQuery.length > 0
    onSearchingChanged: if (searching) navigationHighlightId = ""
    onShortcutsEnabledChanged: if (!shortcutsEnabled && controller) controller.clearSearch()

    Keys.onPressed: function(event) {
        if (!shortcutsEnabled || !controller) return
        if (event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)) return
        if (searching && event.key === Qt.Key_Backspace) {
            controller.searchText(Array.from(controller.searchQuery).slice(0, -1).join(""))
            event.accepted = true
        } else if (event.text.length > 0 && !/[\u0000-\u001f\u007f]/.test(event.text)) {
            controller.searchText(controller.searchQuery + event.text)
            event.accepted = true
        }
    }

    function focusMap() {
        prioritySlider.focus = false
        forceActiveFocus()
    }

    function priorityColor(level) {
        return level === 3 ? "#246594" : level === 2 ? "#294f6b" : "#2b3e4c"
    }
    function priorityLabel(level) {
        return level === 3 ? "Higher" : level === 2 ? "Middle" : "Lower"
    }
    component PriorityBars: Row {
        id: priorityBars
        property int level: 0
        spacing: 2
        width: 22
        height: 14
        Repeater {
            model: 3
            Rectangle {
                required property int index
                width: 6
                height: 6 + index * 4
                y: 14 - height
                color: index < priorityBars.level ? "#e5f0fa" : "transparent"
                border.color: "#a9bfd1"
                radius: 1
            }
        }
    }

    function fitMap() {
        if (!controller || viewport.width <= 0 || viewport.height <= 0) return
        var nodes = pane.sceneNodes
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
    function jumpBookmark(nodeId) {
        var currentZoom = zoom
        controller.jumpToBookmark(nodeId)
        var occurrenceId = controller.selectedId
        zoom = currentZoom
        initialized = true
        forceActiveFocus()
        Qt.callLater(function() {
            if (!pane.visible || !pane.controller || pane.controller.selectedId !== occurrenceId) return
            var nodes = pane.sceneNodes
            for (var i = 0; i < nodes.length; ++i) {
                var n = nodes[i]
                if (n.id !== occurrenceId) continue
                pane.panX = -(n.x + n.width / 2) * pane.zoom
                pane.panY = -(n.y + n.height / 2) * pane.zoom
                pane.highlightDestination(occurrenceId)
                return
            }
        })
    }
    function highlightDestination(nodeId) {
        if (searching) return
        navigationFade.stop()
        navigationHighlightId = nodeId
        navigationHighlightOpacity = 1
        navigationHold.restart()
    }
    function revealNode(nodeId) {
        if (!visible || !controller) return
        var nodes = pane.sceneNodes
        for (var i = 0; i < nodes.length; ++i) {
            var n = nodes[i]
            if (n.id !== nodeId) continue
            highlightDestination(nodeId)
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
        deadlineNow = Date.now() / 1000
        forceActiveFocus()
        if (!initialized) Qt.callLater(function() { if (pane.visible && !pane.initialized) pane.fitMap() })
    }
    Timer {
        id: navigationHold
        interval: 1800
        onTriggered: navigationFade.restart()
    }
    NumberAnimation {
        id: navigationFade
        target: pane
        property: "navigationHighlightOpacity"
        to: 0
        duration: 600
    }
    Connections {
        target: pane.controller
        function onChanged() {
            if (pane.navigationHighlightId !== pane.controller.selectedId)
                pane.navigationHighlightId = ""
        }
        function onSceneChanged() { edges.requestPaint() }
        function onRevealNode(nodeId) { pane.revealNode(nodeId) }
        function onScopeChanging(oldScope, newScope) {
            pane.hoveredNodeId = ""
            pane.controller.clearSearch()
            pane.navigationHighlightId = ""
            pane.viewPositions[oldScope] = { zoom: pane.zoom, x: pane.panX, y: pane.panY, initialized: pane.initialized }
            var saved = pane.viewPositions[newScope]
            pane.zoom = saved ? saved.zoom : 1
            pane.panX = saved ? saved.x : 0
            pane.panY = saved ? saved.y : 0
            pane.initialized = saved ? saved.initialized : false
            editor.close()
            if (!pane.initialized) Qt.callLater(function() { if (pane.visible && !pane.initialized) pane.fitMap() })
        }
        function onResetView() {
            pane.hoveredNodeId = ""
            pane.controller.clearSearch()
            pane.navigationHighlightId = ""
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
        RowLayout {
            id: mindmapToolbar
            objectName: "mindmapToolbar"
            readonly property bool compactTools: width < assessmentTool.labeledWidth + paintTool.labeledWidth + causalTool.labeledWidth + wanderingTool.implicitWidth + 5 + actionsButton.implicitWidth + (canvasButton.visible ? canvasButton.implicitWidth + 5 : 0) + 490
            Layout.fillWidth: true
            spacing: 5
            Button {
                id: canvasButton
                objectName: "tabMindmapCanvas"
                text: "Canvas"
                visible: pane.controller && pane.controller.tabScoped
                onClicked: pane.canvasRequested()
            }
            ToolButton {
                id: actionsButton
                objectName: "mindmapActionsButton"
                text: "Mindmap ▾"
                Accessible.name: "Mindmap actions"
                enabled: !!pane.controller
                onClicked: actionsMenu.open()
                Keys.onDownPressed: actionsMenu.open()
                Keys.onReturnPressed: actionsMenu.open()
                Keys.onEnterPressed: actionsMenu.open()
                Menu {
                    id: actionsMenu
                    objectName: "mindmapActionsMenu"
                    y: actionsButton.height
                    enabled: !!pane.controller
                    MenuItem {
                        objectName: "mindmapComplete"
                        text: "Complete"
                        enabled: pane.controller && pane.controller.selectedIds.length > 0
                        onTriggered: { pane.controller.toggleCompleted(); pane.focusMap() }
                    }
                    MenuItem { text: "Add child"; onTriggered: pane.addThought(false) }
                    MenuItem { text: "Add sibling"; onTriggered: pane.addThought(true) }
                    MenuItem {
                        objectName: "mindmapReminder"
                        text: "Reminder"
                        enabled: pane.controller && pane.controller.selectedIds.length === 1
                        onTriggered: pane.reminderRequested(pane.controller.selectedId)
                    }
                    MenuItem { text: "Edit / Notes"; onTriggered: pane.editNode() }
                    MenuItem {
                        objectName: "mindmapBookmark"
                        text: pane.controller && pane.controller.selectedNode.bookmarked ? "Remove bookmark" : "Bookmark"
                        enabled: pane.controller && pane.controller.selectedId !== ""
                        onTriggered: { pane.controller.toggleBookmark(pane.controller.selectedId); pane.focusMap() }
                    }
                    MenuItem {
                        objectName: "mindmapMeasureProgress"
                        text: pane.controller && pane.controller.selectedNode.measureProgress
                              ? "Stop measuring progress" : "Measure progress"
                        enabled: pane.controller && pane.controller.selectedId !== ""
                        onTriggered: { pane.controller.toggleMeasureProgress(pane.controller.selectedId); pane.focusMap() }
                    }
                    MenuItem { text: "Fold / Unfold"; onTriggered: pane.controller.toggleFold() }
                    MenuSeparator {}
                    Menu {
                        title: "Edit"
                        MenuItem { text: "Toggle bold (Ctrl+B)"; onTriggered: pane.controller.toggleBold() }
                        MenuItem { text: "Cut"; enabled: pane.controller && pane.controller.canCut; onTriggered: pane.controller.cutSelected() }
                        MenuItem { objectName: "mindmapToolbarPaste"; text: "Paste"; enabled: pane.controller && (pane.controller.canPaste || pane.controller.canPasteClipboardText); onTriggered: pane.controller.pasteSelected() }
                        MenuSeparator {}
                        MenuItem { text: "Delete"; onTriggered: pane.controller.deleteSelected() }
                        MenuSeparator {}
                        MenuItem { text: "Undo"; enabled: pane.controller && pane.controller.canUndo; onTriggered: pane.controller.undo() }
                        MenuItem { text: "Redo"; enabled: pane.controller && pane.controller.canRedo; onTriggered: pane.controller.redo() }
                    }
                    Menu {
                        objectName: "mindmapTabsMenu"
                        title: "Goals"
                        MenuItem {
                            objectName: "mindmapCreateTab"
                            text: "Create goal"
                            enabled: pane.controller && pane.controller.canCreateTab
                            onTriggered: { pane.controller.createTabFromSelected(); pane.focusMap() }
                        }
                        MenuItem {
                            objectName: "mindmapCreateScheduledGoal"
                            text: "Create goal with time range…"
                            enabled: pane.controller && pane.controller.canCreateTab
                            onTriggered: nodeGoalRangeDialog.showForNode(pane.controller.selectedId, pane.controller.selectedNode.text)
                        }
                        MenuItem {
                            objectName: "mindmapEditGoalRange"
                            text: "Set/Edit time range…"
                            enabled: pane.controller && pane.controller.selectedNode.isTab === true
                            onTriggered: nodeGoalRangeDialog.showExistingGoal(pane.controller.selectedId)
                        }
                        MenuItem {
                            text: "Open goal"
                            enabled: pane.controller && pane.controller.selectedNode.isTab === true
                            onTriggered: pane.controller.activate(pane.controller.selectedId)
                        }
                    }
                    Menu {
                        objectName: "mindmapExportMenu"
                        title: "Export branch"
                        enabled: pane.controller && pane.controller.selectedId !== ""
                        MenuItem {
                            objectName: "mindmapSaveBranchOpml"
                            text: "Save as OPML…"
                            onTriggered: pane.branchOpmlExportRequested(pane.controller.selectedId)
                        }
                        MenuItem {
                            objectName: "mindmapCopyBranchOpml"
                            text: "Copy as OPML XML"
                            onTriggered: { pane.controller.copyBranchAsOpml(pane.controller.selectedId); pane.focusMap() }
                        }
                        MenuItem {
                            objectName: "mindmapCopyBranchText"
                            text: "Copy as indented text"
                            onTriggered: { pane.controller.copyBranchAsText(pane.controller.selectedId); pane.focusMap() }
                        }
                    }
                    MenuSeparator {}
                    MenuItem { objectName: "mindmapHelpAction"; text: "Shortcuts and legend…"; onTriggered: helpDialog.open() }
                    onClosed: Qt.callLater(function() {
                        if (!editor.visible && !helpDialog.visible && !deadlineDialog.visible && !nodeGoalRangeDialog.visible && !pane.reminderDialogOpen) pane.focusMap()
                    })
                }
            }
            CompanionButton {
                id: assessmentTool
                objectName: "mindmapAssessmentButton"
                label: "Assessment"
                assessment: true
                onClicked: pane.assessmentRequested()
            }
            CompanionButton {
                id: paintTool
                objectName: "mindmapActionPaintButton"
                label: "Action Paint"
                iconKey: "paint"
                onClicked: { pane.focusMap(); pane.actionPaintRequested() }
            }
            CompanionButton {
                id: causalTool
                objectName: "mindmapCausalDiagramButton"
                label: "Causal Diagram"
                iconKey: "causal"
                onClicked: { pane.focusMap(); pane.causalDiagramRequested() }
            }
            ToolButton {
                id: wanderingTool
                objectName: "mindmapThoughtWanderingButton"
                implicitWidth: 32
                implicitHeight: 32
                enabled: !!pane.tabModel && pane.tabModel.tabCount > 1
                Accessible.name: "Thought wandering"
                ToolTip.visible: hovered
                ToolTip.text: "Thought wandering"
                icon.source: "../icons/dice.svg"
                icon.width: 16
                icon.height: 16
                icon.color: enabled ? "#d6e2ee" : palette.mid
                display: AbstractButton.IconOnly
                onClicked: { pane.focusMap(); pane.thoughtWanderingRequested() }
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
        }
        RowLayout {
            objectName: "mindmapViewToolbar"
            Layout.fillWidth: true
            spacing: 5
            ToolButton {
                objectName: "mindmapFoldAll"
                text: "Fold all"
                palette.buttonText: "#e5f0fa"
                enabled: !!pane.controller
                onClicked: { pane.controller.foldAll(); pane.focusMap() }
            }
            ToolButton {
                objectName: "mindmapUnfoldAll"
                text: "Unfold all"
                palette.buttonText: "#e5f0fa"
                enabled: !!pane.controller
                onClicked: { pane.controller.unfoldAll(); pane.focusMap() }
            }
            Item { Layout.fillWidth: true; Layout.minimumWidth: 0 }
            ColumnLayout {
                spacing: 0
                Layout.preferredWidth: 190
                Layout.minimumWidth: 65
                Layout.fillWidth: true
                Layout.maximumWidth: 190
                Label {
                    text: "Top priority → All priorities"
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    color: "#a9bfd1"
                    font.pixelSize: 12
                }
                Slider {
                    id: prioritySlider
                    objectName: "mindmapPriorityFilter"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 24
                    from: 0
                    to: 1
                    stepSize: 0.01
                    value: pane.controller ? pane.controller.priorityFilter : 1
                    enabled: pane.controller && pane.controller.priorityFilterEnabled
                    Accessible.name: "Minimum mindmap priority, highest on the left, all on the right"
                    onMoved: pane.controller.setPriorityFilter(value)
                }
            }
            Label {
                objectName: "mindmapPriorityFilterText"
                text: pane.controller ? pane.controller.priorityFilterText : "All"
                color: "#a9bfd1"
                Layout.preferredWidth: mindmapToolbar.compactTools ? 45 : 105
                Layout.minimumWidth: 0
                elide: Text.ElideRight
            }
            ToolButton { text: "−"; Accessible.name: "Zoom out"; ToolTip.visible: hovered; ToolTip.text: "Zoom out"; onClicked: { pane.zoomBy(1 / 1.2); pane.focusMap() } }
            ToolButton { text: "+"; Accessible.name: "Zoom in"; ToolTip.visible: hovered; ToolTip.text: "Zoom in"; onClicked: { pane.zoomBy(1.2); pane.focusMap() } }
            ToolButton { text: "Fit"; Accessible.name: "Fit mindmap"; onClicked: { pane.fitMap(); pane.focusMap() } }
        }
        ScrollView {
            id: bookmarkScroll
            objectName: "mindmapBookmarks"
            Layout.fillWidth: true
            Layout.preferredHeight: bookmarkRow.height + 14
            visible: pane.controller && pane.controller.bookmarks.length > 0
            clip: true
            contentWidth: bookmarkRow.width
            contentHeight: bookmarkRow.height
            ScrollBar.horizontal.policy: ScrollBar.AsNeeded
            ScrollBar.vertical.policy: ScrollBar.AlwaysOff
            Row {
                id: bookmarkRow
                spacing: 6
                Repeater {
                    model: pane.controller ? pane.controller.bookmarks : []
                    Button {
                        required property var modelData
                        objectName: "mindmapBookmark_" + modelData.id
                        width: Math.min(220, Math.max(70, implicitWidth))
                        text: modelData.text
                        contentItem: Text {
                            text: parent.text
                            color: parent.palette.buttonText
                            font: parent.font
                            elide: Text.ElideRight
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                        }
                        ToolTip.visible: hovered
                        ToolTip.delay: 600
                        ToolTip.text: modelData.path
                        onClicked: pane.jumpBookmark(modelData.id)
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: pane.controller && pane.controller.canPaste
            text: "Branches cut: select a destination and press Ctrl+V · Escape cancels"
            wrapMode: Text.WordWrap
            color: "#a9bfd1"
        }
        Label {
            objectName: "mindmapSearchIndicator"
            Layout.fillWidth: true
            visible: pane.searching
            text: pane.controller ? "Find: " + pane.controller.searchQuery + " · "
                  + (pane.controller.searchMatchCount > 0
                     ? pane.controller.searchMatchPosition + "/" + pane.controller.searchMatchCount
                     : "No matches") + " · Enter / Shift+Enter: next / previous · Esc: clear" : ""
            elide: Text.ElideRight
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
                id: canvasMouse
                anchors.fill: parent
                property point lastPosition
                onDoubleClicked: function(mouse) {
                    if (!pane.controller || mouse.button !== Qt.LeftButton || mouse.modifiers !== Qt.NoModifier) return
                    var point = mapToItem(world, mouse.x, mouse.y)
                    if (pane.controller.addThoughtAt(point.x, point.y)) pane.editNode()
                }
                onPressed: function(mouse) {
                    pane.focusMap()
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
                    var lines = pane.sceneEdges
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
                    model: pane.sceneNodes
                    delegate: Loader {
                        id: nodeLoader
                        property bool dragging: false
                        required property var modelData
                        width: modelData.width; height: modelData.height
                        // Keep a margin for smooth panning and retain selected nodes
                        // so an in-progress drag cannot destroy its MouseArea.
                        active: pane.sceneNodes.length < 200
                                || pane.selectedNodeSet.has(modelData.id)
                                || dragging
                                || (world.x + (modelData.x + width) * pane.zoom >= -200
                                    && world.x + modelData.x * pane.zoom <= viewport.width + 200
                                    && world.y + (modelData.y + height) * pane.zoom >= -200
                                    && world.y + modelData.y * pane.zoom <= viewport.height + 200)
                        sourceComponent: Rectangle {
                            id: nodeItem
                            readonly property var modelData: nodeLoader.modelData
                            readonly property int leadingInset: modelData.showCompletionCheckbox || modelData.completed ? 45 : 18
                            objectName: "mindmapNode_" + modelData.id
                            x: modelData.x; y: modelData.y
                            width: modelData.width; height: modelData.height
                            radius: 8
                            color: modelData.priorityLevel > 0 ? pane.priorityColor(modelData.priorityLevel)
                                  : modelData.isTab ? "#254d6c" : "#223442"
                            readonly property bool selected: pane.selectedNodeSet.has(modelData.id)
                            readonly property bool currentSearchHit: pane.searching && selected
                                                                          && pane.controller.searchMatchPosition > 0
                            opacity: pane.cutNodeSet.has(modelData.id) ? 0.45 : 1
                            border.width: selected ? 2 : 1
                            border.color: selected ? "#a5d9ff" : "#557b98"
                            Rectangle {
                                objectName: "mindmapSearchHighlight_" + nodeItem.modelData.id
                                anchors.fill: parent
                                anchors.margins: -8 / pane.zoom
                                radius: nodeItem.radius + 8 / pane.zoom
                                color: "transparent"
                                border.color: "#ffbf47"
                                border.width: 4 / pane.zoom
                                opacity: nodeItem.currentSearchHit ? 1 : pane.navigationHighlightOpacity
                                visible: nodeItem.currentSearchHit
                                         || (nodeItem.selected && pane.navigationHighlightId === nodeItem.modelData.id
                                             && opacity > 0)
                            }
                            Text {
                                objectName: "mindmapNoteIcon_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.hasNote
                                anchors.left: parent.left; anchors.leftMargin: nodeItem.leadingInset
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: (nodeItem.modelData.reminderActive ? -12 : 0)
                                                              - (nodeItem.modelData.measureProgress ? 12 : 0)
                                                              - (nodeItem.modelData.deadlineActive ? 14 : 0)
                                text: "\uD83D\uDCDD"
                                font.pixelSize: 15
                                z: 2
                                Accessible.role: Accessible.Button
                                Accessible.name: "Edit note"
                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        pane.controller.select(nodeItem.modelData.id)
                                        pane.editNode()
                                    }
                                }
                            }
                            Text {
                                objectName: "mindmapBookmarkIcon_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.bookmarked
                                anchors.left: parent.left
                                anchors.leftMargin: nodeItem.leadingInset + (nodeItem.modelData.hasNote ? 20 : 0)
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: (nodeItem.modelData.reminderActive ? -12 : 0)
                                                              - (nodeItem.modelData.measureProgress ? 12 : 0)
                                                              - (nodeItem.modelData.deadlineActive ? 14 : 0)
                                text: "\uD83D\uDD16"
                                font.pixelSize: 15
                                Accessible.role: Accessible.StaticText
                                Accessible.name: "Bookmarked"
                            }
                            Rectangle {
                                objectName: "mindmapPlanBadge_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.planVisible
                                width: 16; height: 18; radius: 3
                                anchors.left: parent.left
                                anchors.leftMargin: nodeItem.leadingInset + (nodeItem.modelData.hasNote ? 20 : 0)
                                                       + (nodeItem.modelData.bookmarked ? 20 : 0)
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: (nodeItem.modelData.reminderActive ? -12 : 0)
                                                              - (nodeItem.modelData.measureProgress ? 12 : 0)
                                                              - (nodeItem.modelData.deadlineActive ? 14 : 0)
                                color: nodeItem.modelData.planState === "pending" ? "#806125" : "#315e7b"
                                z: 3
                                Image {
                                    anchors.centerIn: parent
                                    width: 14; height: 14
                                    source: Qt.resolvedUrl("../icons/calendar.svg")
                                }
                                Rectangle {
                                    visible: nodeItem.modelData.planState === "combined"
                                    anchors.right: parent.right; anchors.top: parent.top
                                    width: 5; height: 5; radius: 3; color: "#ffcc66"
                                }
                                Accessible.role: Accessible.StaticText
                                Accessible.name: nodeItem.modelData.planTooltip
                                ToolTip.visible: planHover.containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: nodeItem.modelData.planTooltip
                                MouseArea {
                                    id: planHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
                            }
                            Text {
                                objectName: "mindmapNodeText_" + nodeItem.modelData.id
                                anchors.fill: parent
                                anchors.bottomMargin: (nodeItem.modelData.reminderActive ? 24 : 0)
                                                      + (nodeItem.modelData.measureProgress ? 24 : 0)
                                                      + (nodeItem.modelData.deadlineActive ? 28 : 0)
                                anchors.leftMargin: nodeItem.leadingInset + (nodeItem.modelData.hasNote ? 20 : 0)
                                                       + (nodeItem.modelData.bookmarked ? 20 : 0)
                                                       + (nodeItem.modelData.planVisible ? 20 : 0)
                                anchors.rightMargin: (nodeItem.modelData.priorityLevel > 0 ? 48 : 18)
                                                     + (nodeItem.modelData.hasChildren ? 22 : 0)
                                                     + (nodeItem.modelData.priorityRank > 0 ? 30 : 0)
                                verticalAlignment: Text.AlignVCenter
                                text: (nodeItem.modelData.isReference ? "↗ " : nodeItem.modelData.isTab ? "▣ " : "") + nodeItem.modelData.text
                                font.pixelSize: 14
                                font.bold: nodeItem.modelData.bold
                                color: "#e5f0fa"; elide: Text.ElideRight
                            }
                            Rectangle {
                                objectName: "mindmapPriorityRank_" + nodeItem.modelData.id
                                readonly property int rank: nodeItem.modelData.priorityRank
                                visible: rank > 0
                                width: 24; height: 24; radius: 12
                                anchors.right: parent.right; anchors.rightMargin: 48 + (nodeItem.modelData.hasChildren ? 22 : 0)
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: (nodeItem.modelData.reminderActive ? -12 : 0)
                                                              - (nodeItem.modelData.measureProgress ? 12 : 0)
                                                              - (nodeItem.modelData.deadlineActive ? 14 : 0)
                                color: rank === 1 ? "#f2c75c" : rank === 2 ? "#c8d3df" : "#d99b6c"
                                border.color: "#e5f0fa"
                                Accessible.role: Accessible.StaticText
                                Accessible.name: "Priority rank " + rank
                                Text {
                                    anchors.centerIn: parent
                                    text: parent.rank
                                    font.pixelSize: 14
                                    font.bold: true
                                    color: "#1b2028"
                                }
                            }
                            PriorityBars {
                                objectName: "mindmapPriority_" + nodeItem.modelData.id
                                anchors.right: parent.right; anchors.rightMargin: 20 + (nodeItem.modelData.hasChildren ? 22 : 0)
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.verticalCenterOffset: (nodeItem.modelData.reminderActive ? -12 : 0)
                                                              - (nodeItem.modelData.measureProgress ? 12 : 0)
                                                              - (nodeItem.modelData.deadlineActive ? 14 : 0)
                                level: nodeItem.modelData.priorityLevel
                                visible: level > 0
                            }
                            ToolButton {
                                objectName: "mindmapComplete_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.showCompletionCheckbox
                                x: 3; y: 2; width: 38; height: 36; z: 4
                                text: nodeItem.modelData.completed ? "☑" : "☐"
                                font.pixelSize: 24
                                palette.buttonText: nodeItem.modelData.completed ? "#91d6b6" : "#a9bfd1"
                                Accessible.name: (nodeItem.modelData.completed ? "Mark incomplete: " : "Complete: ") + nodeItem.modelData.text
                                ToolTip.visible: hovered
                                ToolTip.text: nodeItem.modelData.completed ? "Mark incomplete" : "Mark complete"
                                onClicked: {
                                    pane.controller.select(nodeItem.modelData.id)
                                    pane.controller.toggleCompleted()
                                    pane.focusMap()
                                }
                            }
                            Text {
                                objectName: "mindmapCompletedMark_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.completed && !nodeItem.modelData.showCompletionCheckbox
                                x: 3; y: 2; width: 38; height: 36
                                text: "✓"
                                font.pixelSize: 24
                                color: "#91d6b6"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                Accessible.role: Accessible.StaticText
                                Accessible.name: "Completed"
                            }
                            ToolButton {
                                id: foldButton
                                objectName: "mindmapFold_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.hasChildren
                                anchors.right: parent.right
                                anchors.rightMargin: 3
                                anchors.top: parent.top
                                anchors.topMargin: 4
                                width: 32; height: 32
                                z: 3
                                text: nodeItem.modelData.folded ? "▸" : "▾"
                                font.pixelSize: 18
                                palette.buttonText: "#e5f0fa"
                                background: Rectangle {
                                    radius: 8
                                    color: foldButton.down ? "#42647c" : foldButton.hovered ? "#345265" : "#20394c"
                                    border.color: foldButton.activeFocus ? "#e5f0fa" : "#6288a5"
                                }
                                Accessible.name: (nodeItem.modelData.folded ? "Unfold " : "Fold ") + nodeItem.modelData.text
                                ToolTip.visible: hovered
                                ToolTip.text: nodeItem.modelData.folded ? "Unfold branch" : "Fold branch"
                                onClicked: {
                                    pane.controller.toggleNodeFold(nodeItem.modelData.id)
                                    pane.focusMap()
                                }
                            }
                            MouseArea {
                                id: nodeMouse
                                objectName: "mindmapNodeMouse_" + nodeItem.modelData.id
                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton | Qt.RightButton
                                hoverEnabled: true
                                onEntered: { insertionHoverExit.stop(); pane.hoveredNodeId = nodeItem.modelData.id }
                                onExited: insertionHoverExit.restart()
                                onPressedChanged: { pane.nodePressed = pressed; nodeLoader.dragging = pressed }
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
                                    pane.focusMap()
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
                                    var nodes = pane.sceneNodes
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
                                    }
                                }
                                onDoubleClicked: function(mouse) {
                                    if (wasDragged || mouse.button !== Qt.LeftButton || mouse.modifiers !== Qt.NoModifier) return
                                    var nodeId = nodeItem.modelData.id
                                    pane.controller.select(nodeId)
                                    if (nodeItem.modelData.isTab) {
                                        if (!(pane.controller.tabScoped && nodeItem.modelData.isViewRoot) && !pane.controller.canPaste)
                                            pane.controller.activate(nodeId)
                                    } else {
                                        pane.editNode()
                                    }
                                }
                                ToolTip {
                                    objectName: "mindmapTooltip_" + nodeItem.modelData.id
                                    y: nodeItem.height + 8
                                    delay: 800
                                    visible: nodeMouse.containsMouse && !nodeMouse.pressed
                                    text: nodeItem.modelData.text
                                          + (nodeItem.modelData.priorityRank > 0
                                             ? "\nPriority rank: " + nodeItem.modelData.priorityRank : "")
                                          + (nodeItem.modelData.priorityLevel > 0
                                             ? "\nRelative priority: " + pane.priorityLabel(nodeItem.modelData.priorityLevel)
                                               + " · Score: " + nodeItem.modelData.priorityScore.toFixed(2) : "")
                                          + (nodeItem.modelData.note ? "\n\n" + nodeItem.modelData.note : "")
                                }
                            }
                            Item {
                                id: deadlineBar
                                objectName: "mindmapDeadlineBar_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.deadlineActive
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 6
                                height: 22
                                readonly property real remaining: visible
                                    ? Math.max(0, Math.min(nodeItem.modelData.deadlineDuration,
                                        nodeItem.modelData.deadlineStart + nodeItem.modelData.deadlineDuration - pane.deadlineNow)) : 0
                                readonly property real progress: nodeItem.modelData.deadlineDuration > 0
                                    ? remaining / nodeItem.modelData.deadlineDuration : 0
                                readonly property color timerColor: progress > 0.5 ? "#2ecc71"
                                    : progress > 0.25 ? "#f39c12" : "#e74c3c"
                                Text {
                                    objectName: "mindmapDeadlineText_" + nodeItem.modelData.id
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    text: {
                                        var seconds = Math.ceil(deadlineBar.remaining)
                                        return Math.floor(seconds / 60) + ":" + (seconds % 60 < 10 ? "0" : "") + seconds % 60
                                    }
                                    color: deadlineBar.timerColor
                                    font.pixelSize: 12
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: "Deadline: " + text
                                }
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 4
                                    radius: 2
                                    color: "#1a2230"
                                    Rectangle {
                                        objectName: "mindmapDeadlineFill_" + nodeItem.modelData.id
                                        width: parent.width * deadlineBar.progress
                                        height: parent.height
                                        radius: 2
                                        color: deadlineBar.timerColor
                                    }
                                }
                            }
                            Rectangle {
                                objectName: "mindmapProgressBadge_" + nodeItem.modelData.id
                                visible: nodeItem.modelData.measureProgress
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.bottomMargin: 4 + (nodeItem.modelData.reminderActive ? 24 : 0)
                                                        + (nodeItem.modelData.deadlineActive ? 28 : 0)
                                anchors.leftMargin: 4
                                anchors.rightMargin: 4
                                height: 20
                                radius: 4
                                color: "#345265"
                                Text {
                                    objectName: "mindmapProgressText_" + nodeItem.modelData.id
                                    anchors.centerIn: parent
                                    text: "Progress: " + nodeItem.modelData.progressPercent + "%"
                                    color: "#e5f0fa"
                                    font.pixelSize: 12
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: text
                                }
                            }
                            Rectangle {
                                objectName: "mindmapReminderBadge_" + nodeItem.modelData.id
                                anchors.bottomMargin: 4 + (nodeItem.modelData.deadlineActive ? 28 : 0)
                                visible: nodeItem.modelData.reminderActive
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.margins: 4
                                height: 22
                                radius: 4
                                color: "#a94f0b"
                                border.color: "#f4a64f"
                                Text {
                                    anchors.centerIn: parent
                                    text: "\uD83D\uDD14 " + nodeItem.modelData.reminderAt
                                    color: "#fff4e4"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        pane.controller.select(nodeItem.modelData.id)
                                        nodeMenu.targetNodeId = nodeItem.modelData.id
                                        nodeMenu.popup()
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Item {
                id: insertionControls
                anchors.fill: parent
                readonly property var targetNode: {
                    if (!pane.controller) return null
                    var id = pane.hoveredNodeId || pane.controller.selectedId
                    var nodes = pane.sceneNodes
                    for (var i = 0; i < nodes.length; ++i)
                        if (nodes[i].id === id) return nodes[i]
                    return null
                }
                visible: !!targetNode && !pane.nodePressed && !canvasMouse.pressed
                         && !editor.visible && !quickChildDialog.visible && !nodeMenu.visible && !actionsMenu.visible
                         && !helpDialog.visible && !deadlineDialog.visible && !nodeGoalRangeDialog.visible && !pane.reminderDialogOpen
                Repeater {
                    model: 3
                    id: insertionButtons
                    delegate: ToolButton {
                        id: insertionButton
                        required property int index
                        readonly property bool child: index === 2
                        readonly property bool before: index === 0
                        visible: child || !insertionControls.targetNode || !insertionControls.targetNode.isViewRoot
                        objectName: child ? "mindmapAddChild" : before ? "mindmapAddAbove" : "mindmapAddBelow"
                        width: child ? 36 : 24
                        height: width
                        x: insertionControls.targetNode
                           ? viewport.width / 2 + pane.panX
                             + (insertionControls.targetNode.x + insertionControls.targetNode.width / 2) * pane.zoom
                             + (child ? (insertionControls.targetNode.x < 0 && !insertionControls.targetNode.isViewRoot ? -1 : 1)
                                * (insertionControls.targetNode.width * pane.zoom / 2 + 22) : 0) - width / 2 : 0
                        y: insertionControls.targetNode
                           ? viewport.height / 2 + pane.panY
                             + (insertionControls.targetNode.y + insertionControls.targetNode.height / 2) * pane.zoom
                             + (child ? 0 : before ? -1 : 1) * Math.max(insertionControls.targetNode.height * pane.zoom / 2, 14) - height / 2 : 0
                        focusPolicy: Qt.NoFocus
                        hoverEnabled: true
                        Accessible.name: child ? "Add child" : before ? "Add sibling above" : "Add sibling below"
                        ToolTip.text: child ? "Add child" : before ? "Add sibling above" : "Add sibling below"
                        ToolTip.visible: hovered
                        ToolTip.delay: 500
                        onHoveredChanged: {
                            if (hovered) insertionHoverExit.stop()
                            else insertionHoverExit.restart()
                        }
                        background: Rectangle {
                            radius: width / 2
                            color: insertionButton.hovered ? "#467da3" : "#254d6c"
                            border.color: "#a5d9ff"
                        }
                        contentItem: Text {
                            text: "+"
                            color: "#e5f0fa"
                            font.pixelSize: 20
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            var nodeId = insertionControls.targetNode.id
                            pane.hoveredNodeId = ""
                            pane.focusMap()
                            if (child) {
                                quickChildDialog.targetNodeId = nodeId
                                quickChildTitle.text = ""
                                quickChildDialog.open()
                            } else if (pane.controller.addSiblingRelative(nodeId, before)) pane.editNode()
                        }
                    }
                }
            }
        }
    }
    onZoomChanged: edges.requestPaint()
    onPanXChanged: edges.requestPaint()
    onPanYChanged: edges.requestPaint()
    Dialog {
        id: helpDialog
        objectName: "mindmapHelpDialog"
        title: "Mindmap shortcuts and legend"
        modal: true
        anchors.centerIn: parent
        width: Math.min(520, pane.width - 20)
        standardButtons: Dialog.Close
        onClosed: pane.focusMap()
        ColumnLayout {
            anchors.fill: parent
            spacing: 16
            Label {
                Layout.fillWidth: true
                text: "Drag the priority slider left for highest scores, right to include more; All restores every branch · Children of progress-measuring nodes have completion checkboxes · Select a node and click + beside it to add a child, or above/below to add a sibling · Type to find node titles, including folded branches · Enter / Shift+Enter cycles matches · Backspace edits search · Escape clears search · Double-click a goal node to open it · Double-click empty space to add a thought · Ctrl+B toggles bold · Ctrl+drag or Ctrl+Up/Down reorders · Ctrl+Left/Right moves branches to either side · Ctrl+click toggles selection · Shift+click selects a range · Ctrl+C / Ctrl+V copies branches · Ctrl+X / Ctrl+V moves branches · F4 or the Complete menu action toggles completion on any node · Arrows navigate · Tab adds a child · Ctrl+Enter opens a goal"
                wrapMode: Text.WordWrap
                color: "#a9bfd1"
            }
            Flow {
                Layout.fillWidth: true
                spacing: 12
                Label { text: "Relative priority:"; color: "#a9bfd1" }
                Repeater {
                    model: 3
                    delegate: Rectangle {
                        required property int index
                        width: legendContent.width + 12
                        height: 24
                        radius: 4
                        color: pane.priorityColor(index + 1)
                        Row {
                            id: legendContent
                            anchors.centerIn: parent
                            spacing: 6
                            PriorityBars { level: index + 1; anchors.verticalCenter: parent.verticalCenter }
                            Label { text: pane.priorityLabel(index + 1); color: "#e5f0fa" }
                        }
                    }
                }
            }
        }
    }
    Dialog {
        id: deadlineDialog
        objectName: "mindmapDeadlineDialog"
        title: "Set deadline"
        modal: true
        anchors.centerIn: parent
        width: Math.min(320, pane.width - 20)
        standardButtons: Dialog.Ok | Dialog.Cancel
        property string targetNodeId: ""
        onOpened: {
            deadlineMinutes.forceActiveFocus()
            deadlineMinutes.selectAll()
            standardButton(Dialog.Ok).enabled = deadlineMinutes.acceptableInput
        }
        onAccepted: {
            if (pane.controller && deadlineMinutes.acceptableInput) {
                pane.deadlineNow = Date.now() / 1000
                pane.controller.setDeadline(targetNodeId, Number(deadlineMinutes.text))
            }
        }
        onClosed: pane.focusMap()
        ColumnLayout {
            anchors.fill: parent
            Label { text: "Duration in minutes"; color: "#e5f0fa" }
            TextField {
                id: deadlineMinutes
                objectName: "mindmapDeadlineMinutes"
                Layout.fillWidth: true
                text: "25"
                validator: IntValidator { bottom: 1; top: 2147483647 }
                inputMethodHints: Qt.ImhDigitsOnly
                onAcceptableInputChanged: {
                    var button = deadlineDialog.standardButton(Dialog.Ok)
                    if (button) button.enabled = acceptableInput
                }
                Keys.onReturnPressed: if (acceptableInput) deadlineDialog.accept()
                Keys.onEnterPressed: if (acceptableInput) deadlineDialog.accept()
            }
        }
    }
    Menu {
        id: nodeMenu
        objectName: "mindmapNodeMenu"
        width: 280
        property string targetNodeId: ""
        property var reminderData: ({})
        property var deadlineData: ({})
        property bool canMoveUp: false
        property bool canMoveDown: false
        property bool measuringProgress: false
        onTargetNodeIdChanged: measuringProgress = pane.controller
                               ? pane.controller.measuresProgress(targetNodeId) : false
        onAboutToShow: {
            reminderData = pane.controller.reminderData(targetNodeId)
            deadlineData = pane.controller.deadlineData(targetNodeId)
            canMoveUp = pane.controller.canReorderNode(targetNodeId, -1)
            canMoveDown = pane.controller.canReorderNode(targetNodeId, 1)
            measuringProgress = pane.controller.measuresProgress(targetNodeId)
        }
        IconMenuItem { iconKey: "notes"; text: "Edit / Notes"; onTriggered: pane.editNode() }
        IconMenuItem { iconKey: "child"; text: "Add child"; onTriggered: pane.addThought(false) }
        IconMenuItem { iconKey: "sibling"; text: "Add sibling"; onTriggered: pane.addThought(true) }
        IconMenuItem { iconKey: "check"; text: "Complete"; enabled: pane.controller && pane.controller.selectedIds.length > 0; onTriggered: pane.controller.toggleCompleted() }
        IconMenuItem { iconKey: "fold"; text: "Fold / Unfold"; onTriggered: pane.controller.toggleFold() }
        MenuSeparator {}
        Menu {
            objectName: "mindmapAddToPlanMenu"
            title: "Add to plan"
            icon.source: Qt.resolvedUrl("../icons/calendar.svg")
            icon.width: 16
            icon.height: 16
            icon.color: palette.text
            enabled: pane.controller && pane.controller.selectedIds.length > 0
            IconMenuItem {
                iconKey: "calendar"
                objectName: "mindmapAddToPlanReady"
                text: pane.controller ? pane.controller.planReadyLabel : "Ready (0 tasks)"
                onTriggered: {
                    pane.controller.addSelectedToReady()
                    pane.focusMap()
                }
            }
            MenuSeparator {}
            Repeater {
                model: pane.controller ? pane.controller.planHourOptions : []
                delegate: IconMenuItem {
                    iconKey: "calendar"
                    required property var modelData
                    objectName: "mindmapAddToPlan_" + modelData.hour
                    text: modelData.label
                    onTriggered: {
                        pane.controller.addSelectedToPlan(modelData.hour)
                        pane.focusMap()
                    }
                }
            }
            MenuSeparator {}
            Repeater {
                model: pane.controller ? pane.controller.planWeekdayOptions : []
                delegate: IconMenuItem {
                    iconKey: "calendar"
                    required property var modelData
                    objectName: "mindmapAddToWeekday_" + modelData.weekday
                    text: modelData.label
                    onTriggered: {
                        pane.controller.scheduleSelectedToWeekday(modelData.weekday)
                        pane.focusMap()
                    }
                }
            }
        }
        Menu {
            objectName: "mindmapTimingMenu"
            title: "Reminders & deadline"
            width: 280
            icon.source: Qt.resolvedUrl("../icons/bell.svg")
            icon.width: 16
            icon.height: 16
            icon.color: palette.text
            IconMenuItem {
                iconKey: "bell"
                objectName: "mindmapSetReminder"
                text: nodeMenu.reminderData.reminderActive ? "Update Reminder" : "Set Reminder"
                onTriggered: pane.reminderRequested(nodeMenu.targetNodeId)
            }
            Menu {
                objectName: "mindmapQuickReminderMenu"
                title: "Quick reminder"
                icon.source: Qt.resolvedUrl("../icons/bell.svg")
                icon.width: 16
                icon.height: 16
                icon.color: palette.text
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder10Minutes"
                    text: "10 minutes"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 10)
                }
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder20Minutes"
                    text: "20 minutes"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 20)
                }
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder1Hour"
                    text: "1 hour"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 60)
                }
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder24Hours"
                    text: "24 hours"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 24 * 60)
                }
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder2Days"
                    text: "2 days"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 2 * 24 * 60)
                }
                IconMenuItem {
                    iconKey: "bell"
                    objectName: "mindmapQuickReminder7Days"
                    text: "7 days"
                    onTriggered: pane.quickReminderRequested(nodeMenu.targetNodeId, 7 * 24 * 60)
                }
            }
            IconMenuItem {
                iconKey: "bell"
                objectName: "mindmapClearReminder"
                text: "Clear Reminder"
                visible: !!nodeMenu.reminderData.reminderActive
                onTriggered: pane.clearReminderRequested(nodeMenu.targetNodeId)
            }
            MenuSeparator {}
            IconMenuItem {
                iconKey: "timer"
                objectName: "mindmapSetDeadline"
                text: nodeMenu.deadlineData.deadlineActive ? "Update deadline" : "Set deadline"
                onTriggered: {
                    deadlineDialog.targetNodeId = nodeMenu.targetNodeId
                    deadlineDialog.title = text
                    deadlineMinutes.text = nodeMenu.deadlineData.deadlineActive
                        ? String(Math.max(1, Math.ceil(nodeMenu.deadlineData.deadlineDuration / 60))) : "25"
                    deadlineDialog.open()
                }
            }
            IconMenuItem {
                iconKey: "timer"
                objectName: "mindmapClearDeadline"
                text: "Clear deadline"
                visible: !!nodeMenu.deadlineData.deadlineActive
                onTriggered: pane.controller.clearDeadline(nodeMenu.targetNodeId)
            }
        }
        Menu {
            objectName: "mindmapGoalsMenu"
            title: "Goals & progress"
            width: 280
            icon.source: Qt.resolvedUrl("../icons/tab.svg")
            icon.width: 16
            icon.height: 16
            icon.color: palette.text
            IconMenuItem {
                iconKey: "tab"
                objectName: "mindmapAddTab"
                text: "Add goal…"
                onTriggered: {
                    tabReferenceDialog.targetNodeId = nodeMenu.targetNodeId
                    tabReferenceDialog.open()
                }
            }
            IconMenuItem {
                iconKey: "tab"
                text: "Create goal"
                enabled: pane.controller && pane.controller.canCreateTab
                onTriggered: { pane.controller.createTabFromSelected(); pane.focusMap() }
            }
            IconMenuItem {
                iconKey: "tab"
                objectName: "mindmapContextCreateScheduledGoal"
                text: "Create goal with time range…"
                enabled: pane.controller && pane.controller.canCreateTab
                onTriggered: nodeGoalRangeDialog.showForNode(nodeMenu.targetNodeId, pane.controller.selectedNode.text)
            }
            IconMenuItem {
                iconKey: "tab"
                objectName: "mindmapContextEditGoalRange"
                text: "Set/Edit time range…"
                enabled: pane.controller && pane.controller.selectedNode.isTab === true
                onTriggered: nodeGoalRangeDialog.showExistingGoal(nodeMenu.targetNodeId)
            }
            MenuSeparator {}
            IconMenuItem {
                iconKey: "progress"
                objectName: "mindmapMeasureProgressMenuItem"
                text: nodeMenu.measuringProgress ? "Stop measuring progress" : "Measure progress"
                onTriggered: {
                    pane.controller.toggleMeasureProgress(nodeMenu.targetNodeId)
                    nodeMenu.measuringProgress = pane.controller.measuresProgress(nodeMenu.targetNodeId)
                    pane.focusMap()
                }
            }
        }
        Menu {
            objectName: "mindmapArrangeMenu"
            title: "Arrange branch"
            width: 280
            icon.source: Qt.resolvedUrl("../icons/sibling.svg")
            icon.width: 16
            icon.height: 16
            icon.color: palette.text
            IconMenuItem {
                iconKey: "up"
                objectName: "mindmapMoveUp"
                text: "Move up"
                enabled: nodeMenu.canMoveUp
                onTriggered: { pane.controller.reorderNode(nodeMenu.targetNodeId, -1); pane.focusMap() }
            }
            IconMenuItem {
                iconKey: "down"
                objectName: "mindmapMoveDown"
                text: "Move down"
                enabled: nodeMenu.canMoveDown
                onTriggered: { pane.controller.reorderNode(nodeMenu.targetNodeId, 1); pane.focusMap() }
            }
            MenuSeparator {}
            IconMenuItem { iconKey: "left"; text: "Branch on left"; onTriggered: pane.controller.setSide("left") }
            IconMenuItem { iconKey: "right"; text: "Branch on right"; onTriggered: pane.controller.setSide("right") }
        }
        IconMenuItem {
            iconKey: "bookmark"
            objectName: "mindmapBookmarkMenuItem"
            text: pane.controller && pane.controller.bookmarks.some(function(b) { return b.id === pane.controller.sourceNodeId(nodeMenu.targetNodeId) })
                  ? "Remove bookmark" : "Bookmark"
            onTriggered: { pane.controller.toggleBookmark(nodeMenu.targetNodeId); pane.focusMap() }
        }
        MenuSeparator {}
        IconMenuItem { iconKey: "cut"; text: "Cut branches"; enabled: pane.controller && pane.controller.canCut; onTriggered: pane.controller.cutSelected() }
        IconMenuItem { iconKey: "clipboard"; objectName: "mindmapContextPaste"; text: "Paste beneath selected node"; enabled: pane.controller && (pane.controller.canPaste || pane.controller.canPasteClipboardText); onTriggered: pane.controller.pasteSelected() }
        Menu {
            objectName: "mindmapContextExportMenu"
            title: "Export branch"
            icon.source: Qt.resolvedUrl("../icons/export.svg")
            icon.width: 16
            icon.height: 16
            icon.color: palette.text
            IconMenuItem {
                iconKey: "export"
                objectName: "mindmapContextSaveBranchOpml"
                text: "Save as OPML…"
                onTriggered: pane.branchOpmlExportRequested(nodeMenu.targetNodeId)
            }
            IconMenuItem {
                iconKey: "clipboard"
                objectName: "mindmapContextCopyBranchOpml"
                text: "Copy as OPML XML"
                onTriggered: { pane.controller.copyBranchAsOpml(nodeMenu.targetNodeId); pane.focusMap() }
            }
            IconMenuItem {
                iconKey: "clipboard"
                objectName: "mindmapContextCopyBranchText"
                text: "Copy as indented text"
                onTriggered: { pane.controller.copyBranchAsText(nodeMenu.targetNodeId); pane.focusMap() }
            }
        }
        MenuSeparator {}
        IconMenuItem { iconKey: "trash"; text: pane.controller && pane.controller.selectedNode.isReference ? "Remove goal reference" : "Delete branch"; onTriggered: pane.controller.deleteSelected() }
    }
    GoalRangeDialog {
        id: nodeGoalRangeDialog
        objectName: "mindmapGoalRangeDialog"
        nodeController: pane.controller
        goalModel: pane.tabModel
        function showExistingGoal(nodeId) {
            var goal = pane.controller.goalData(nodeId)
            if (goal.id) show(goal, "")
        }
        onClosed: pane.focusMap()
    }
    Dialog {
        id: tabReferenceDialog
        objectName: "mindmapTabReferenceDialog"
        title: "Add goal"
        modal: true
        anchors.centerIn: parent
        width: Math.min(600, pane.width - 20)
        height: Math.min(440, pane.height - 20)
        standardButtons: Dialog.Cancel
        property string targetNodeId: ""
        property var options: []
        property string errorText: ""
        function refresh() {
            options = pane.controller ? pane.controller.tabReferenceOptions(tabReferenceSearch.text) : []
            tabReferenceList.currentIndex = options.length ? 0 : -1
        }
        function insert(index) {
            if (index < 0 || index >= options.length) return
            if (pane.controller.addTabReference(targetNodeId, options[index].tabId)) close()
        }
        onOpened: {
            errorText = ""
            tabReferenceSearch.text = ""
            refresh()
            tabReferenceSearch.forceActiveFocus()
        }
        onClosed: pane.focusMap()
        Connections {
            target: pane.controller
            function onChanged() { if (tabReferenceDialog.visible) tabReferenceDialog.refresh() }
            function onErrorOccurred(message) {
                if (tabReferenceDialog.visible) tabReferenceDialog.errorText = message
            }
        }
        ColumnLayout {
            anchors.fill: parent
            TextField {
                id: tabReferenceSearch
                objectName: "mindmapTabReferenceSearch"
                Layout.fillWidth: true
                placeholderText: "Search goals…"
                onTextChanged: tabReferenceDialog.refresh()
                onAccepted: tabReferenceDialog.insert(tabReferenceList.currentIndex)
                Keys.onDownPressed: tabReferenceList.currentIndex = Math.min(tabReferenceList.count - 1, tabReferenceList.currentIndex + 1)
                Keys.onUpPressed: tabReferenceList.currentIndex = Math.max(0, tabReferenceList.currentIndex - 1)
            }
            ListView {
                id: tabReferenceList
                objectName: "mindmapTabReferenceList"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: tabReferenceDialog.options
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    objectName: "mindmapTabOption_" + modelData.tabId
                    width: tabReferenceList.width
                    highlighted: tabReferenceList.currentIndex === index
                    text: modelData.name + "\n" + modelData.path
                    onClicked: tabReferenceDialog.insert(index)
                }
                Label {
                    anchors.centerIn: parent
                    visible: tabReferenceList.count === 0
                    text: "No matching goals"
                }
            }
            Label {
                Layout.fillWidth: true
                visible: tabReferenceDialog.errorText.length > 0
                text: tabReferenceDialog.errorText
                wrapMode: Text.Wrap
                color: "#ffb4a9"
            }
        }
    }
    Dialog {
        id: quickChildDialog
        objectName: "mindmapQuickChildDialog"
        property string targetNodeId: ""
        title: "Add thought"
        modal: true
        anchors.centerIn: parent
        width: Math.min(360, pane.width - 20)
        standardButtons: Dialog.Ok | Dialog.Cancel
        TextField {
            id: quickChildTitle
            objectName: "mindmapQuickChildTitle"
            width: parent.width
            placeholderText: "New thought"
            onAccepted: if (text.trim().length) quickChildDialog.accept()
            onTextChanged: if (quickChildDialog.visible) quickChildDialog.standardButton(Dialog.Ok).enabled = text.trim().length > 0
        }
        onOpened: {
            standardButton(Dialog.Ok).text = "Add"
            standardButton(Dialog.Ok).enabled = false
            quickChildTitle.forceActiveFocus()
        }
        onAccepted: pane.controller.addChildNamed(targetNodeId, quickChildTitle.text)
        onClosed: pane.focusMap()
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
            pane.focusMap()
        }
        onRejected: { titleField.text = ""; noteField.text = ""; pane.focusMap() }
    }
    Shortcut { sequence: "Ctrl+B"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.toggleBold() }
    Shortcut { sequence: "Ctrl+C"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.copySelected() }
    Shortcut { sequence: "Ctrl+X"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.cutSelected() }
    Shortcut { sequence: "Ctrl+V"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.pasteSelected() }
    Shortcut { sequence: "Escape"; enabled: pane.shortcutsEnabled && (pane.searching || pane.controller.canPaste); onActivated: { if (pane.searching) pane.controller.clearSearch(); else pane.controller.cancelCut() } }
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
    Shortcut { sequence: "Ctrl+Left"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.setSide("left") }
    Shortcut { sequence: "Ctrl+Right"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.setSide("right") }
    Shortcut { sequences: ["Ctrl+Return", "Ctrl+Enter"]; enabled: pane.shortcutsEnabled; onActivated: pane.controller.activate(pane.controller.selectedId) }
    Shortcut { sequences: ["Return", "Enter"]; enabled: pane.shortcutsEnabled; onActivated: { if (pane.searching) pane.controller.navigateSearch(1); else pane.addThought(true) } }
    Shortcut { sequences: ["Shift+Return", "Shift+Enter"]; enabled: pane.shortcutsEnabled && pane.searching; onActivated: pane.controller.navigateSearch(-1) }
    Shortcut { sequence: "F4"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.toggleCompleted() }
    Shortcut { sequence: "F2"; enabled: pane.shortcutsEnabled; onActivated: pane.editNode() }
    Shortcut { sequence: "Delete"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.deleteSelected() }
    Shortcut { sequence: "Space"; enabled: pane.shortcutsEnabled; onActivated: { if (pane.searching) pane.controller.searchText(pane.controller.searchQuery + " "); else pane.controller.toggleFold() } }
    Shortcut { sequence: "Ctrl+Z"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.undo() }
    Shortcut { sequence: "Ctrl+Y"; enabled: pane.shortcutsEnabled; onActivated: pane.controller.redo() }
    Shortcut { sequence: "Ctrl++"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1.2) }
    Shortcut { sequence: "Ctrl+-"; enabled: pane.shortcutsEnabled; onActivated: pane.zoomBy(1/1.2) }
    Shortcut { sequence: "Ctrl+0"; enabled: pane.shortcutsEnabled; onActivated: pane.fitMap() }
}
