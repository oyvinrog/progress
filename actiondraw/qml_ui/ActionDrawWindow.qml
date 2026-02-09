import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "components"
ApplicationWindow {
    id: root
    visible: true
    width: 1100
    height: 800
    color: "#090f15"
    font.family: "Trebuchet MS"
    font.pixelSize: 13
    title: {
        if (projectManager && projectManager.currentFilePath) {
            var name = projectManager.currentFilePath.split("/").pop()
            if (name.endsWith(".progress"))
                name = name.slice(0, -9)
            return name
        }
        return "ActionDraw - Progress Tracker"
    }

    property var diagramModelRef: diagramModel
    property var taskModelRef: taskModel
    property var projectManagerRef: projectManager
    property var markdownNoteManagerRef: markdownNoteManager
    property var tabModelRef: tabModel

    menuBar: ActionMenuBar {
        root: root
        diagramModel: diagramModelRef
        taskModel: taskModelRef
        projectManager: projectManagerRef
        edgeCanvas: edgeCanvas
        viewport: viewport
        saveDialog: dialogs.saveDialog
        loadDialog: dialogs.loadDialog
        taskDialog: dialogs.taskDialog
    }

    Rectangle {
        anchors.fill: parent
        z: -20
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0a131c" }
            GradientStop { position: 1.0; color: "#111d29" }
        }
    }

    Rectangle {
        width: Math.min(root.width * 0.75, 780)
        height: width
        radius: width / 2
        x: -width * 0.28
        y: -height * 0.45
        z: -19
        color: "#1d4c66"
        opacity: 0.16
    }

    Rectangle {
        width: Math.min(root.width * 0.65, 640)
        height: width
        radius: width / 2
        x: root.width - width * 0.7
        y: root.height - height * 0.45
        z: -19
        color: "#2f6b54"
        opacity: 0.12
    }

    function showWindow() {
        root.visible = true
        root.requestActivate()
    }

    function drillToTask(taskIndex) {
        if (!diagramModel || taskIndex < 0)
            return
        if (diagramModel.focusTask) {
            diagramModel.focusTask(taskIndex)
        } else {
            diagramModel.setCurrentTask(taskIndex)
        }
        Qt.callLater(root.scrollToContent)
    }

    function formatTime(minutes) {
        if (minutes === 0) return "N/A"
        if (minutes < 1) return (minutes * 60).toFixed(0) + "s"
        return minutes.toFixed(1) + "m"
    }

    function performSave() {
        if (!projectManager) {
            return
        }
        if (projectManager.hasCurrentFile()) {
            projectManager.saveCurrentProject()
        } else {
            dialogs.saveDialog.open()
        }
    }

    function showSaveNotification(message) {
        saveNotification.text = message
        saveNotification.opacity = 1
        saveNotificationTimer.restart()
    }

    function showNextReminderAlert() {
        if (root.reminderPopupBusy)
            return
        if (!root.reminderQueue || root.reminderQueue.length === 0)
            return
        root.reminderPopupBusy = true
        var nextReminder = root.reminderQueue.shift()
        root.pendingReminderTabIndex = nextReminder.tabIndex
        root.pendingReminderTaskIndex = nextReminder.taskIndex
        root.pendingReminderTaskTitle = nextReminder.taskTitle
        reminderPopup.open()
    }

    function showReminderAlert(tabIndex, taskIndex, taskTitle) {
        var reminder = {
            tabIndex: tabIndex,
            taskIndex: taskIndex,
            taskTitle: taskTitle && taskTitle.length > 0 ? taskTitle : "Task",
        }
        root.reminderQueue.push(reminder)
        if (!reminderPopup.visible)
            root.showNextReminderAlert()
    }

    property int minBoardSize: 2000
    property int boardMargin: 500
    property real currentMinItemX: 0
    property real currentMinItemY: 0
    property real currentMaxItemX: 0
    property real currentMaxItemY: 0
    property var linkingTabsToCurrent: []
    property real boundMinItemX: Math.min(currentMinItemX, 0)
    property real boundMinItemY: Math.min(currentMinItemY, 0)
    property real originOffsetX: boardMargin - boundMinItemX
    property real originOffsetY: boardMargin - boundMinItemY
    property int boardWidth: Math.max(minBoardSize, (currentMaxItemX - boundMinItemX) + (boardMargin * 2))
    property int boardHeight: Math.max(minBoardSize, (currentMaxItemY - boundMinItemY) + (boardMargin * 2))

    function updateBoardBounds() {
        if (diagramModel) {
            currentMinItemX = diagramModel.minItemX
            currentMinItemY = diagramModel.minItemY
            currentMaxItemX = diagramModel.maxItemX
            currentMaxItemY = diagramModel.maxItemY
        } else {
            currentMinItemX = 0
            currentMinItemY = 0
            currentMaxItemX = 0
            currentMaxItemY = 0
        }
    }

    function refreshLinkingTabsPanel() {
        if (!tabModel || !tabModel.getTabsLinkingToCurrentTab) {
            linkingTabsToCurrent = []
            return
        }
        linkingTabsToCurrent = tabModel.getTabsLinkingToCurrentTab()
    }

    function scrollToContent() {
        if (!diagramModel)
            return
        if (diagramModel.count === 0) {
            root.resetView()
            return
        }
        // If there's a current task, center on it
        var taskPos = diagramModel.getCurrentTaskPosition()
        if (taskPos) {
            var centerX = taskPos.x + taskPos.width / 2
            var centerY = taskPos.y + taskPos.height / 2
            centerOnPoint(centerX, centerY)
            return
        }
        // Otherwise scroll to show content with some padding
        var minX = diagramModel.minItemX
        var minY = diagramModel.minItemY
        var padding = 50
        var targetX = Math.max(0, (minX - padding + root.originOffsetX) * root.zoomLevel)
        var targetY = Math.max(0, (minY - padding + root.originOffsetY) * root.zoomLevel)
        viewport.contentX = targetX
        viewport.contentY = targetY
    }

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
        "wish": { "text": "Wish", "title": "Add Wish" },
        "chatgpt": { "text": "Ask ChatGPT", "title": "Ask ChatGPT" }
    })

    // Pending edge drop state (for creating new items when dropping into empty space)
    property string pendingEdgeSourceId: ""
    property real pendingEdgeDropX: 0
    property real pendingEdgeDropY: 0
    property string selectedItemId: ""
    property string lastCreatedTaskId: ""
    property int pendingReminderTabIndex: 0
    property int pendingReminderTaskIndex: -1
    property string pendingReminderTaskTitle: ""
    property var reminderQueue: []
    property bool reminderPopupBusy: false

    Shortcut {
        sequence: "Ctrl+S"
        enabled: projectManager !== null
        onActivated: root.performSave()
    }

    Shortcut {
        sequence: "Ctrl+C"
        enabled: diagramModel !== null
        onActivated: root.copySelectionToClipboard()
    }

    Shortcut {
        sequence: "Ctrl+V"
        enabled: diagramModel !== null
        onActivated: {
            root.pasteFromClipboard()
        }
    }

    Shortcut {
        sequence: "F2"
        enabled: diagramModel !== null
        onActivated: root.renameSelectedItem()
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: diagramModel !== null && !dialogs.freeTextDialog.visible
        onActivated: root.addTaskOrConnectedTask()
    }

    Shortcut {
        sequence: "Ctrl+M"
        enabled: diagramModel !== null
        onActivated: root.openMarkdownNoteForSelection()
    }

    function addTaskOrConnectedTask() {
        if (!diagramModel)
            return
        var sourceId = ""
        var item = null
        if (root.selectedItemId && root.selectedItemId.length > 0) {
            item = diagramModel.getItemSnapshot(root.selectedItemId)
            if (item && (item.x || item.x === 0)) {
                sourceId = root.selectedItemId
            }
        }
        if (!sourceId && root.lastCreatedTaskId && root.lastCreatedTaskId.length > 0) {
            item = diagramModel.getItemSnapshot(root.lastCreatedTaskId)
            if (item && (item.x || item.x === 0)) {
                sourceId = root.lastCreatedTaskId
            } else {
                root.lastCreatedTaskId = ""
            }
        }
        if (sourceId) {
            // Add connected task from last-created task when available.
            var dropX = item.x + (item.width || 100) + 50
            var dropY = item.y
            dialogs.edgeDropTaskDialog.sourceId = sourceId
            dialogs.edgeDropTaskDialog.sourceType = "task"
            dialogs.edgeDropTaskDialog.dropX = dropX
            dialogs.edgeDropTaskDialog.dropY = dropY
            dialogs.edgeDropTaskDialog.open()
        } else {
            // No selection - add new task at center.
            addQuickTaskAtCenter()
        }
    }

    function openMarkdownNoteForSelection() {
        if (!diagramModel || !markdownNoteManager)
            return
        if (!root.selectedItemId || root.selectedItemId.length === 0)
            return
        markdownNoteManager.openNote(root.selectedItemId)
    }

    function showEdgeDropSuggestions(sourceId, dropX, dropY) {
        root.pendingEdgeSourceId = sourceId
        root.pendingEdgeDropX = dropX
        root.pendingEdgeDropY = dropY
        dialogs.edgeDropMenu.popup()
    }

    function openQuickTaskDialog(point) {
        dialogs.quickTaskDialog.targetX = point.x
        dialogs.quickTaskDialog.targetY = point.y
        dialogs.quickTaskDialog.open()
    }

    function addQuickTaskAtCenter() {
        openQuickTaskDialog(diagramCenterPoint())
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
        var cx = (viewport.contentX + viewport.width / 2) / root.zoomLevel - root.originOffsetX
        var cy = (viewport.contentY + viewport.height / 2) / root.zoomLevel - root.originOffsetY
        return snapPoint(Qt.point(cx, cy))
    }

    function copySelectionToClipboard() {
        if (!diagramModel)
            return
        if (edgeCanvas && edgeCanvas.selectedEdgeId && edgeCanvas.selectedEdgeId.length > 0) {
            diagramModel.copyEdgeToClipboard(edgeCanvas.selectedEdgeId)
            return
        }
        if (root.selectedItemId && root.selectedItemId.length > 0) {
            diagramModel.copyItemsToClipboard([root.selectedItemId])
        }
    }

    function pasteFromClipboard() {
        if (!diagramModel)
            return
        var center = root.diagramCenterPoint()
        if (diagramModel.hasClipboardDiagram()) {
            diagramModel.pasteDiagramFromClipboard(center.x, center.y)
            return
        }
        if (diagramModel.hasClipboardImage()) {
            diagramModel.pasteImageFromClipboard(center.x, center.y)
            return
        }
        if (diagramModel.hasClipboardTextLines()) {
            dialogs.clipboardPasteDialog.pasteX = center.x
            dialogs.clipboardPasteDialog.pasteY = center.y
            dialogs.clipboardPasteDialog.open()
        }
    }

    function renameItemById(itemId) {
        if (!diagramModel || !itemId)
            return
        var item = diagramModel.getItemSnapshot(itemId)
        if (!item || !item.id)
            return
        if (item.type === "task" && item.taskIndex < 0) {
            dialogs.newTaskDialog.openWithItem(item.id, item.text)
        } else if (item.type === "task" && item.taskIndex >= 0) {
            dialogs.taskRenameDialog.openWithItem(item.id, item.text)
        } else if (item.type === "freetext") {
            root.openFreeTextDialog(Qt.point(item.x, item.y), item.id, item.text)
        } else if (item.type !== "image") {
            root.openPresetDialog(item.type, Qt.point(item.x, item.y), item.id, item.text)
        }
    }

    function renameSelectedItem() {
        renameItemById(root.selectedItemId)
    }

    function openPresetDialog(preset, point, itemId, initialText) {
        if (!root.presetDefaults[preset])
            preset = "box"
        var defaults = root.presetDefaults[preset]
        dialogs.boxDialog.editingItemId = itemId || ""
        dialogs.boxDialog.presetName = preset
        dialogs.boxDialog.targetX = snapValue(point.x)
        dialogs.boxDialog.targetY = snapValue(point.y)
        dialogs.boxDialog.textValue = initialText !== undefined ? initialText : (defaults && defaults.text ? defaults.text : "")
        dialogs.boxDialog.open()
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
        dialogs.freeTextDialog.editingItemId = itemId || ""
        dialogs.freeTextDialog.targetX = snapValue(point.x)
        dialogs.freeTextDialog.targetY = snapValue(point.y)
        dialogs.freeTextDialog.textValue = initialText !== undefined ? initialText : ""
        dialogs.freeTextDialog.open()
    }

    function setZoomInternal(newZoom, focusX, focusY) {
        var clamped = clampZoom(newZoom)
        if (Math.abs(clamped - root.zoomLevel) < 0.0001)
            return
        var fx = focusX === undefined ? viewport.width / 2 : focusX
        var fy = focusY === undefined ? viewport.height / 2 : focusY
        var focusContentX = viewport.contentX + fx
        var focusContentY = viewport.contentY + fy
        var focusDiagramX = (focusContentX / root.zoomLevel) - root.originOffsetX
        var focusDiagramY = (focusContentY / root.zoomLevel) - root.originOffsetY
        root.zoomLevel = clamped
        var newContentX = (focusDiagramX + root.originOffsetX) * root.zoomLevel - fx
        var newContentY = (focusDiagramY + root.originOffsetY) * root.zoomLevel - fy
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
        var targetX = (x + root.originOffsetX) * root.zoomLevel - viewport.width / 2
        var targetY = (y + root.originOffsetY) * root.zoomLevel - viewport.height / 2
        var maxX = Math.max(0, viewport.contentWidth - viewport.width)
        var maxY = Math.max(0, viewport.contentHeight - viewport.height)
        viewport.contentX = Math.min(Math.max(targetX, 0), maxX)
        viewport.contentY = Math.min(Math.max(targetY, 0), maxY)
    }

    function resetView() {
        setZoomInternal(1.0)
        centerOnPoint((root.boardWidth / 2) - root.originOffsetX, (root.boardHeight / 2) - root.originOffsetY)
    }

    ActionDialogs {
        id: dialogs
        root: root
        diagramModel: diagramModelRef
        taskModel: taskModelRef
        projectManager: projectManagerRef
        markdownNoteManager: markdownNoteManagerRef
        tabModel: tabModelRef
        diagramLayer: diagramLayer
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        SidebarTabs {
            tabModel: tabModelRef
            projectManager: projectManagerRef
        }

        // Main content area (right side)
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            ProgressStatsRow {
                root: root
                taskModel: taskModelRef
                diagramModel: diagramModelRef
            }

            ToolbarRow {
                root: root
                diagramModel: diagramModelRef
                viewport: viewport
            }

            Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 14
            color: "#101a24"
            border.color: "#2f465b"
            border.width: 1

            Rectangle {
                id: linkingTabsPanel
                visible: root.linkingTabsToCurrent && root.linkingTabsToCurrent.length > 0
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.topMargin: 10
                anchors.rightMargin: 10
                width: Math.min(parent.width * 0.34, 280)
                height: linksColumn.implicitHeight + 18
                radius: 10
                color: "#13212d"
                border.color: "#34536a"
                border.width: 1
                z: 30

                Column {
                    id: linksColumn
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 6

                    Text {
                        text: "Linked From Tabs"
                        color: "#9ed1f2"
                        font.pixelSize: 10
                        font.bold: true
                    }

                    Repeater {
                        model: root.linkingTabsToCurrent

                        delegate: Rectangle {
                            width: linksColumn.width
                            height: linkActiveText.visible ? 40 : 24
                            radius: 6
                            color: linkMouse.containsMouse ? "#1f3547" : "#182b3a"
                            border.color: "#33546a"
                            border.width: 1

                            Column {
                                anchors.fill: parent
                                anchors.leftMargin: 7
                                anchors.rightMargin: 7
                                anchors.topMargin: 4
                                anchors.bottomMargin: 4
                                spacing: 1

                                Text {
                                    id: linkTitleText
                                    text: modelData.name + " (" + Math.round(modelData.completionPercent) + "%)"
                                    color: "#d9ebf8"
                                    font.pixelSize: 10
                                    font.bold: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    id: linkActiveText
                                    visible: modelData.activeTaskTitle && modelData.activeTaskTitle.length > 0
                                    text: "Active: " + modelData.activeTaskTitle
                                    color: "#8dc8a5"
                                    font.pixelSize: 9
                                    elide: Text.ElideRight
                                }
                            }

                            MouseArea {
                                id: linkMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (projectManager)
                                        projectManager.switchTab(modelData.tabIndex)
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                radius: 13
                color: "transparent"
                border.color: "#1a2d3d"
                border.width: 1
            }

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                hoverEnabled: true
                propagateComposedEvents: true
                z: 10
                onWheel: function(wheel) {
                    var zoomModifier = (wheel.modifiers & Qt.ControlModifier) || (wheel.modifiers & Qt.MetaModifier)
                    if (!zoomModifier) {
                        wheel.accepted = false
                        return
                    }
                    var steps = 0
                    if (wheel.angleDelta.y !== 0) {
                        steps = wheel.angleDelta.y / 120
                    } else if (wheel.pixelDelta.y !== 0) {
                        steps = wheel.pixelDelta.y / 50
                    }
                    if (steps === 0)
                        return
                    var factor = Math.pow(1.1, steps)
                    root.applyZoomFactor(factor, wheel.x, wheel.y)
                    wheel.accepted = true
                }
            }

            Flickable {
                id: viewport
                anchors.fill: parent
                contentWidth: root.boardWidth * root.zoomLevel
                contentHeight: root.boardHeight * root.zoomLevel
                clip: true
                interactive: !diagramModel || !diagramModel.drawingMode

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
                    x: root.originOffsetX
                    y: root.originOffsetY
                    width: root.boardWidth
                    height: root.boardHeight
                    transformOrigin: Item.TopLeft
                    scale: root.zoomLevel

                    property real contextMenuX: 0
                    property real contextMenuY: 0
                    property string contextMenuItemId: ""

                    Menu {
                        id: canvasContextMenu

                        MenuItem {
                            text: "Box"
                            icon.name: "insert-object"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                diagramModel.addBox(snapped.x, snapped.y, "")
                            }
                        }
                        MenuItem {
                            text: "Note (Markdown)"
                            icon.name: "document-edit"
                            onTriggered: {
                                if (!diagramModel) return
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                var newId = diagramModel.addPresetItem("note", snapped.x, snapped.y)
                                if (newId) {
                                    root.selectedItemId = newId
                                    if (markdownNoteManager)
                                        markdownNoteManager.openNote(newId)
                                }
                            }
                        }
                        MenuItem {
                            text: "New Task"
                            icon.name: "list-add"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openQuickTaskDialog(snapped)
                            }
                        }
                        MenuItem {
                            text: "Free Text"
                            icon.name: "accessories-text-editor"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openFreeTextDialog(snapped, "", "")
                            }
                        }
                        MenuItem {
                            text: "Obstacle"
                            icon.name: "dialog-warning"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openPresetDialog("obstacle", snapped, "", undefined)
                            }
                        }
                        MenuItem {
                            text: "Wish"
                            icon.name: "emblem-favorite"
                            onTriggered: {
                                var snapped = root.snapPoint({x: diagramLayer.contextMenuX, y: diagramLayer.contextMenuY})
                                root.openPresetDialog("wish", snapped, "", undefined)
                            }
                        }
                    }

                    Menu {
                        id: itemContextMenu

                        MenuItem {
                            id: renameNoteMenuItem
                            text: "Rename Label..."
                            icon.name: "edit-rename"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && (item.type === "note" || item.type === "wish" || item.type === "obstacle")
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: {
                                root.renameItemById(diagramLayer.contextMenuItemId)
                            }
                        }
                        MenuItem {
                            id: drillToTabMenuItem
                            text: "Drill to Tab"
                            icon.name: "go-next"
                            visible: {
                                if (!diagramModel || !projectManager || !tabModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.type === "task" && item.taskIndex >= 0
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: {
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                if (item && item.taskIndex >= 0 && projectManager)
                                    projectManager.drillToTab(item.taskIndex)
                            }
                        }
                        MenuItem {
                            id: openChatGptMenuItem
                            text: "Open ChatGPT"
                            icon.name: "help-contents"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.type === "chatgpt"
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: diagramModel.openChatGpt(diagramLayer.contextMenuItemId)
                        }
                        MenuItem {
                            text: "Link Folder..."
                            icon.name: "folder"
                            onTriggered: dialogs.folderDialog.open()
                        }
                        MenuItem {
                            id: openFolderMenuItem
                            text: "Open Folder"
                            icon.name: "folder-open"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.folderPath && item.folderPath !== ""
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: diagramModel.openFolder(diagramLayer.contextMenuItemId)
                        }
                        MenuItem {
                            id: clearFolderMenuItem
                            text: "Clear Folder"
                            icon.name: "edit-clear"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.folderPath && item.folderPath !== ""
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: diagramModel.clearFolderPath(diagramLayer.contextMenuItemId)
                        }
                        MenuItem {
                            id: breakDownMenuItem
                            text: "Break Down..."
                            icon.name: "view-list-details"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.type !== "image"
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                dialogs.breakdownDialog.sourceItemId = diagramLayer.contextMenuItemId
                                dialogs.breakdownDialog.sourceTypeLabel = item && item.type ? item.type : ""
                                dialogs.breakdownDialog.open()
                            }
                        }
                        MenuItem {
                            text: "Edit Note...\t\tCtrl+M"
                            icon.name: "document-edit"
                            enabled: diagramModel !== null && diagramLayer.contextMenuItemId.length > 0
                            onTriggered: {
                                root.selectedItemId = diagramLayer.contextMenuItemId
                                root.openMarkdownNoteForSelection()
                            }
                        }
                        MenuSeparator {}
                        Menu {
                            title: "Convert to..."
                            MenuItem {
                                text: "Box"
                                icon.name: "insert-object"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "box")
                            }
                            MenuItem {
                                text: "Task"
                                icon.name: "view-task"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "task")
                            }
                            MenuItem {
                                text: "Database"
                                icon.name: "server-database"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "database")
                            }
                            MenuItem {
                                text: "Server"
                                icon.name: "network-server"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "server")
                            }
                            MenuItem {
                                text: "Cloud"
                                icon.name: "network-workgroup"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "cloud")
                            }
                            MenuItem {
                                text: "Note"
                                icon.name: "document-edit"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "note")
                            }
                            MenuItem {
                                text: "Free Text"
                                icon.name: "accessories-text-editor"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "freetext")
                            }
                            MenuItem {
                                text: "Obstacle"
                                icon.name: "dialog-warning"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "obstacle")
                            }
                            MenuItem {
                                text: "Wish"
                                icon.name: "emblem-favorite"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "wish")
                            }
                            MenuItem {
                                text: "ChatGPT"
                                icon.name: "help-contents"
                                onTriggered: diagramModel.convertItemType(diagramLayer.contextMenuItemId, "chatgpt")
                            }
                        }
                        MenuItem {
                            text: "Delete"
                            icon.name: "edit-delete"
                            onTriggered: diagramModel.removeItem(diagramLayer.contextMenuItemId)
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
                                    root.selectedItemId = ""
                                    edgeCanvas.requestPaint()
                                }
                            }

                            onDoubleClicked: function(mouse) {
                                var edgeId = edgeCanvas.findEdgeAt(mouse.x, mouse.y)
                                if (edgeId !== "") {
                                    // Double-click to edit description
                                    dialogs.edgeDescriptionDialog.openWithEdge(edgeId)
                                } else {
                                    mouse.accepted = false
                                }
                            }
                        }
                    }

                    Connections {
                        target: diagramModel
                        function onEdgesChanged() { edgeCanvas.requestPaint() }
                        function onItemsChanged() { edgeCanvas.requestPaint(); root.updateBoardBounds() }
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
                            property bool taskCurrent: model.taskCurrent
                            property string folderPath: model.folderPath
                            property bool isTask: itemRect.itemType === "task" && itemRect.taskIndex >= 0
                            property real dragStartX: 0
                            property real dragStartY: 0
                            property real pinchStartWidth: model.width
                            property real pinchStartHeight: model.height
                            property bool isEdgeDropTarget: diagramModel && diagramModel.edgeHoverTargetId === itemRect.itemId
                            property bool hovered: itemHover.hovered
                            property bool resizing: false
                            property bool selected: root.selectedItemId === itemRect.itemId
                            property real taskCountdownRemaining: model.taskCountdownRemaining
                            property real taskCountdownProgress: model.taskCountdownProgress
                            property bool taskCountdownExpired: model.taskCountdownExpired
                            property bool taskCountdownActive: model.taskCountdownActive
                            property bool taskReminderActive: model.taskReminderActive
                            property string taskReminderAt: model.taskReminderAt
                            property real linkedSubtabCompletion: model.linkedSubtabCompletion
                            property string linkedSubtabActiveAction: model.linkedSubtabActiveAction
                            property bool hasLinkedSubtab: model.hasLinkedSubtab
                            property real labelLeftInset: {
                                var inset = 12
                                if (itemRect.itemType === "chatgpt")
                                    inset = Math.max(inset, 40)
                                return inset
                            }
                            property real labelRightInset: {
                                var inset = 12
                                if (linkedSubtabBadge.visible)
                                    inset = Math.max(inset, linkedSubtabBadge.width + linkedSubtabBadge.anchors.rightMargin + 6)
                                if (itemRect.itemType === "note")
                                    inset = Math.max(inset, 34)
                                return inset
                            }
                            property real labelTopInset: {
                                var inset = 12
                                if (itemRect.isTask)
                                    inset = Math.max(inset, 36)
                                if (noteBadge.visible && !itemRect.isTask)
                                    inset = Math.max(inset, noteBadge.height + noteBadge.anchors.topMargin + 4)
                                if (linkedSubtabBadge.visible)
                                    inset = Math.max(inset, linkedSubtabBadge.height + linkedSubtabBadge.anchors.topMargin + 4)
                                if (itemRect.itemType === "chatgpt")
                                    inset = Math.max(inset, 38)
                                if (itemRect.itemType === "note")
                                    inset = Math.max(inset, 32)
                                return inset
                            }
                            property real labelBottomInset: {
                                var inset = 12
                                if (folderBadge.visible)
                                    inset = Math.max(inset, folderBadge.height + folderBadge.anchors.bottomMargin + 4)
                                if (countdownBar.visible)
                                    inset = Math.max(inset, countdownBar.height + 18)
                                return inset
                            }
                            x: model.x
                            y: model.y
                            width: model.width
                            height: model.height
                            radius: itemRect.itemType === "cloud" ? Math.min(width, height) / 2 : 12
                            color: itemRect.itemType === "image" ? "transparent" : (itemRect.isTask && itemRect.taskCompleted ? Qt.darker(model.color, 1.5) : model.color)
                            border.width: itemRect.taskCountdownExpired ? 4 : (itemRect.taskCurrent ? 4 : (isEdgeDropTarget ? 3 : 1))
                            border.color: itemRect.taskCountdownExpired ? "#e74c3c" : (itemRect.taskCurrent ? "#ffcc00" : (isEdgeDropTarget ? "#74d9a0" : (itemDrag.active ? Qt.lighter(model.color, 1.4) : Qt.darker(model.color, 1.6))))
                            z: itemRect.taskCurrent ? 15 : (isEdgeDropTarget ? 10 : 5)
                            scale: isEdgeDropTarget ? 1.08 : 1.0
                            transformOrigin: Item.Center

                            // Glow effect for current task
                            Rectangle {
                                visible: itemRect.taskCurrent
                                anchors.centerIn: parent
                                width: parent.width + 12
                                height: parent.height + 12
                                radius: parent.radius + 6
                                color: "transparent"
                                border.width: 3
                                border.color: "#ffcc00"
                                opacity: 0.5
                                z: -1
                            }

                            // Folder icon badge
                            Rectangle {
                                id: folderBadge
                                visible: itemRect.folderPath !== ""
                                anchors.left: parent.left
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: 6
                                anchors.bottomMargin: 6
                                width: 24
                                height: 20
                                radius: 4
                                color: "#e8a838"
                                z: 25

                                Canvas {
                                    anchors.centerIn: parent
                                    width: 16
                                    height: 12
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        ctx.clearRect(0, 0, width, height)
                                        ctx.fillStyle = "#ffffff"
                                        // Folder tab
                                        ctx.beginPath()
                                        ctx.moveTo(0, 2)
                                        ctx.lineTo(0, height)
                                        ctx.lineTo(width, height)
                                        ctx.lineTo(width, 4)
                                        ctx.lineTo(7, 4)
                                        ctx.lineTo(5.5, 2)
                                        ctx.closePath()
                                        ctx.fill()
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (diagramModel)
                                            diagramModel.openFolder(itemRect.itemId)
                                    }
                                }
                            }

                            Rectangle {
                                id: linkedSubtabBadge
                                visible: itemRect.isTask && itemRect.hasLinkedSubtab
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.rightMargin: 8
                                anchors.topMargin: 8
                                width: Math.min(parent.width * 0.55, 148)
                                height: linkedSubtabAction.visible ? 34 : 20
                                radius: 6
                                color: "#12374d"
                                border.color: "#2f6d8f"
                                border.width: 1
                                z: 24

                                Column {
                                    anchors.fill: parent
                                    anchors.leftMargin: 6
                                    anchors.rightMargin: 6
                                    anchors.topMargin: 3
                                    anchors.bottomMargin: 3
                                    spacing: 1

                                    Text {
                                        id: linkedSubtabPercent
                                        text: Math.round(itemRect.linkedSubtabCompletion) + "% subtab"
                                        color: "#8fd9ff"
                                        font.pixelSize: 9
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        id: linkedSubtabAction
                                        visible: itemRect.linkedSubtabActiveAction !== ""
                                        text: "Active: " + itemRect.linkedSubtabActiveAction
                                        color: "#b6f1c5"
                                        font.pixelSize: 8
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                            Behavior on border.width { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }
                            Behavior on x { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }
                            Behavior on y { NumberAnimation { duration: 80; easing.type: Easing.OutQuad } }

                            Rectangle {
                                anchors.fill: parent
                                color: Qt.rgba(0, 0, 0, itemDrag.active ? 0.08 : 0)
                                radius: itemRect.radius
                            }

                            HoverHandler {
                                id: itemHover
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

                            // "Current" button - star icon to mark as current task
                            Rectangle {
                                id: currentButton
                                visible: itemRect.isTask
                                width: 20
                                height: 20
                                radius: 10
                                anchors.left: taskCheck.right
                                anchors.top: parent.top
                                anchors.leftMargin: 4
                                anchors.topMargin: 8
                                color: itemRect.taskCurrent ? "#ffcc00" : "#1a2230"
                                border.color: itemRect.taskCurrent ? "#e6b800" : "#4b5b72"
                                border.width: 2
                                z: 20

                                Text {
                                    anchors.centerIn: parent
                                    text: "★"
                                    color: itemRect.taskCurrent ? "#1b2028" : "#8a93a5"
                                    font.pixelSize: 11
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        if (diagramModel)
                                            diagramModel.setCurrentTask(itemRect.taskIndex)
                                    }
                                }
                            }

                            // Timer button - clock icon for countdown timer
                            Rectangle {
                                id: timerButton
                                visible: itemRect.isTask
                                width: 20
                                height: 20
                                radius: 10
                                anchors.left: currentButton.right
                                anchors.top: parent.top
                                anchors.leftMargin: 4
                                anchors.topMargin: 8
                                color: itemRect.taskCountdownActive ? "#3498db" : "#1a2230"
                                border.color: itemRect.taskCountdownActive ? "#2980b9" : "#4b5b72"
                                border.width: 2
                                z: 20

                                Text {
                                    anchors.centerIn: parent
                                    text: "⏱"
                                    color: itemRect.taskCountdownActive ? "#ffffff" : "#8a93a5"
                                    font.pixelSize: 10
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function(mouse) {
                                        if (itemRect.taskCountdownActive) {
                                            // Show context menu for active timer
                                            dialogs.timerContextMenu.taskIndex = itemRect.taskIndex
                                            dialogs.timerContextMenu.popup()
                                        } else {
                                            // Show timer dialog for new timer
                                            dialogs.timerDialog.taskIndex = itemRect.taskIndex
                                            dialogs.timerDialog.durationValue = ""
                                            dialogs.timerDialog.open()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                id: noteBadge
                                visible: model.noteMarkdown && model.noteMarkdown.trim().length > 0
                                width: 18
                                height: 18
                                radius: 4
                                anchors.left: itemRect.isTask ? reminderButton.right : parent.left
                                anchors.leftMargin: itemRect.isTask ? 6 : 8
                                anchors.top: parent.top
                                anchors.topMargin: 8
                                color: "#f5d96b"
                                border.color: "#d9b84f"
                                border.width: 1
                                z: 22

                                Text {
                                    anchors.centerIn: parent
                                    text: "N"
                                    color: "#1b2028"
                                    font.pixelSize: 11
                                    font.bold: true
                                }
                            }

                            // Reminder button - bell icon for date/time reminders
                            Rectangle {
                                id: reminderButton
                                visible: itemRect.isTask
                                width: 20
                                height: 20
                                radius: 10
                                anchors.left: timerButton.right
                                anchors.top: parent.top
                                anchors.leftMargin: 4
                                anchors.topMargin: 8
                                color: itemRect.taskReminderActive ? "#e67e22" : "#1a2230"
                                border.color: itemRect.taskReminderActive ? "#d35400" : "#4b5b72"
                                border.width: 2
                                z: 20

                                Text {
                                    anchors.centerIn: parent
                                    text: "⏰"
                                    color: itemRect.taskReminderActive ? "#ffffff" : "#8a93a5"
                                    font.pixelSize: 10
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function(mouse) {
                                        dialogs.reminderContextMenu.taskIndex = itemRect.taskIndex
                                        dialogs.reminderContextMenu.reminderAt = itemRect.taskReminderAt
                                        if (mouse.button === Qt.RightButton || itemRect.taskReminderActive) {
                                            dialogs.reminderContextMenu.popup()
                                        } else {
                                            dialogs.reminderDialog.taskIndex = itemRect.taskIndex
                                            dialogs.reminderDialog.dateValue = ""
                                            dialogs.reminderDialog.timeValue = ""
                                            dialogs.reminderDialog.open()
                                        }
                                    }
                                }
                            }

                            // Countdown progress bar at bottom of task
                            Item {
                                id: countdownBar
                                visible: itemRect.isTask && itemRect.taskCountdownActive
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                anchors.bottomMargin: 6
                                height: 16
                                z: 20

                                // Time remaining text
                                Text {
                                    id: countdownText
                                    anchors.right: parent.right
                                    anchors.bottom: countdownBarBg.top
                                    anchors.bottomMargin: 2
                                    text: {
                                        var remaining = itemRect.taskCountdownRemaining
                                        if (remaining < 0) return ""
                                        var mins = Math.floor(remaining / 60)
                                        var secs = Math.floor(remaining % 60)
                                        return mins + ":" + (secs < 10 ? "0" : "") + secs
                                    }
                                    color: itemRect.taskCountdownExpired ? "#e74c3c" : "#f5f6f8"
                                    font.pixelSize: 10
                                    font.bold: true
                                }

                                // Progress bar background
                                Rectangle {
                                    id: countdownBarBg
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    height: 4
                                    radius: 2
                                    color: "#1a2230"
                                }

                                // Progress bar fill
                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.bottom: parent.bottom
                                    height: 4
                                    radius: 2
                                    width: countdownBarBg.width * Math.max(0, itemRect.taskCountdownProgress)
                                    color: {
                                        var progress = itemRect.taskCountdownProgress
                                        if (progress > 0.5) return "#2ecc71"  // Green
                                        if (progress > 0.25) return "#f39c12"  // Orange
                                        return "#e74c3c"  // Red
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
                                visible: itemRect.itemType === "chatgpt"

                                Rectangle {
                                    width: 26
                                    height: 26
                                    radius: 13
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.leftMargin: 8
                                    anchors.topMargin: 8
                                    color: Qt.lighter(model.color, 1.25)
                                    border.color: Qt.darker(model.color, 1.4)
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: "GPT"
                                        color: model.textColor
                                        font.pixelSize: 9
                                        font.bold: true
                                    }
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.leftMargin: 40
                                    anchors.topMargin: 14
                                    width: parent.width * 0.5
                                    height: 6
                                    radius: 3
                                    color: Qt.lighter(model.color, 1.35)
                                    opacity: 0.8
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "freetext"
                                z: 35

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
                                    id: freetextResizeHandle
                                    anchors.bottom: parent.bottom
                                    anchors.right: parent.right
                                    anchors.bottomMargin: 2
                                    anchors.rightMargin: 2
                                    width: 24
                                    height: 24
                                    color: freetextResizeDrag.active || freetextResizeHover.containsMouse ? "#3a4555" : "transparent"
                                    radius: 3
                                    z: 100

                                    HoverHandler {
                                        id: freetextResizeHover
                                        cursorShape: Qt.SizeFDiagCursor
                                    }

                                    property real resizeStartWidth: 0
                                    property real resizeStartHeight: 0

                                    Canvas {
                                        anchors.fill: parent
                                        anchors.margins: 2
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

                                    DragHandler {
                                        id: freetextResizeDrag
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeFDiagCursor
                                        onActiveChanged: {
                                            if (active) {
                                                itemRect.resizing = true
                                                freetextResizeHandle.resizeStartWidth = model.width
                                                freetextResizeHandle.resizeStartHeight = model.height
                                            } else {
                                                itemRect.resizing = false
                                            }
                                        }
                                        onTranslationChanged: {
                                            if (!active || !diagramModel)
                                                return
                                            var deltaX = translation.x / root.zoomLevel
                                            var deltaY = translation.y / root.zoomLevel
                                            var newWidth = Math.max(60, freetextResizeHandle.resizeStartWidth + deltaX)
                                            var newHeight = Math.max(40, freetextResizeHandle.resizeStartHeight + deltaY)
                                            if (root.snapToGrid) {
                                                newWidth = Math.max(root.gridSpacing, Math.round(newWidth / root.gridSpacing) * root.gridSpacing)
                                                newHeight = Math.max(root.gridSpacing, Math.round(newHeight / root.gridSpacing) * root.gridSpacing)
                                            }
                                            diagramModel.resizeItem(itemRect.itemId, newWidth, newHeight)
                                            edgeCanvas.requestPaint()
                                        }
                                    }
                                }
                            }

                            Item {
                                anchors.fill: parent
                                visible: itemRect.itemType === "image" && model.imageData.length > 0

                                Image {
                                    id: pastedImage
                                    anchors.fill: parent
                                    anchors.margins: 4
                                    source: model.imageData.length > 0 ? "data:image/png;base64," + model.imageData : ""
                                    fillMode: Image.PreserveAspectFit
                                    smooth: true
                                    mipmap: true
                                }

                                // Resize handle for images
                                Rectangle {
                                    id: imageResizeHandle
                                    width: 16
                                    height: 16
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.rightMargin: 2
                                    anchors.bottomMargin: 2
                                    color: "#3a4555"
                                    border.color: "#5a6575"
                                    radius: 3
                                    visible: itemRect.itemType === "image" && (itemRect.hovered || itemRect.selected || itemRect.resizing)

                                    Canvas {
                                        anchors.fill: parent
                                        onPaint: {
                                            var ctx = getContext("2d")
                                            ctx.clearRect(0, 0, width, height)
                                            ctx.strokeStyle = "#8a93a5"
                                            ctx.lineWidth = 1.5
                                            ctx.beginPath()
                                            ctx.moveTo(4, height - 4)
                                            ctx.lineTo(width - 4, 4)
                                            ctx.moveTo(8, height - 4)
                                            ctx.lineTo(width - 4, 8)
                                            ctx.stroke()
                                        }
                                    }

                                    property real resizeStartWidth: 0
                                    property real resizeStartHeight: 0
                                    property point resizeStartPos: Qt.point(0, 0)
                                    property real resizeAspectRatio: 1.0

                                    DragHandler {
                                        id: imageResizeDrag
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeFDiagCursor
                                        onActiveChanged: {
                                            if (active) {
                                                itemRect.resizing = true
                                                imageResizeHandle.resizeStartWidth = model.width
                                                imageResizeHandle.resizeStartHeight = model.height
                                                imageResizeHandle.resizeAspectRatio = model.height > 0 ? model.width / model.height : 1.0
                                            } else {
                                                itemRect.resizing = false
                                            }
                                        }
                                        onTranslationChanged: {
                                            if (!active || !diagramModel)
                                                return
                                            var deltaX = translation.x / root.zoomLevel
                                            var deltaY = translation.y / root.zoomLevel
                                            var startWidth = Math.max(1, imageResizeHandle.resizeStartWidth)
                                            var startHeight = Math.max(1, imageResizeHandle.resizeStartHeight)
                                            var widthScale = (startWidth + deltaX) / startWidth
                                            var heightScale = (startHeight + deltaY) / startHeight
                                            var dominantByWidth = Math.abs(deltaX / startWidth) >= Math.abs(deltaY / startHeight)
                                            var uniformScale = dominantByWidth ? widthScale : heightScale
                                            var minScale = Math.max(60 / startWidth, 40 / startHeight)
                                            uniformScale = Math.max(uniformScale, minScale)

                                            var newWidth = Math.max(60, startWidth * uniformScale)
                                            var newHeight = Math.max(40, startHeight * uniformScale)
                                            if (root.snapToGrid) {
                                                var aspect = Math.max(0.01, imageResizeHandle.resizeAspectRatio)
                                                if (aspect >= 1.0) {
                                                    newWidth = Math.max(root.gridSpacing, Math.round(newWidth / root.gridSpacing) * root.gridSpacing)
                                                    newHeight = Math.max(40, newWidth / aspect)
                                                } else {
                                                    newHeight = Math.max(root.gridSpacing, Math.round(newHeight / root.gridSpacing) * root.gridSpacing)
                                                    newWidth = Math.max(60, newHeight * aspect)
                                                }
                                            }
                                            diagramModel.resizeItem(itemRect.itemId, newWidth, newHeight)
                                            edgeCanvas.requestPaint()
                                        }
                                    }
                                }
                            }

                            Item {
                                id: resizeHandles
                                anchors.fill: parent
                                visible: itemRect.itemType !== "image" && (itemRect.hovered || itemRect.selected || itemDrag.active || itemRect.resizing)
                                z: 30
                                property real startX: 0
                                property real startY: 0
                                property real startWidth: 0
                                property real startHeight: 0
                                property real minWidth: 40
                                property real minHeight: 30

                                function beginResize() {
                                    startX = model.x
                                    startY = model.y
                                    startWidth = model.width
                                    startHeight = model.height
                                }

                                function applyResize(deltaX, deltaY, handle) {
                                    if (!diagramModel)
                                        return
                                    var dx = deltaX / root.zoomLevel
                                    var dy = deltaY / root.zoomLevel
                                    var left = startX
                                    var top = startY
                                    var right = startX + startWidth
                                    var bottom = startY + startHeight

                                    var useLeft = handle.indexOf("Left") >= 0
                                    var useTop = handle.indexOf("Top") >= 0

                                    if (useLeft) {
                                        left = left + dx
                                    } else {
                                        right = right + dx
                                    }

                                    if (useTop) {
                                        top = top + dy
                                    } else {
                                        bottom = bottom + dy
                                    }

                                    var newWidth = right - left
                                    var newHeight = bottom - top

                                    if (newWidth < minWidth) {
                                        if (useLeft) {
                                            left = right - minWidth
                                        } else {
                                            right = left + minWidth
                                        }
                                    }

                                    if (newHeight < minHeight) {
                                        if (useTop) {
                                            top = bottom - minHeight
                                        } else {
                                            bottom = top + minHeight
                                        }
                                    }

                                    newWidth = right - left
                                    newHeight = bottom - top

                                    if (root.snapToGrid) {
                                        var snappedWidth = Math.max(minWidth, Math.round(newWidth / root.gridSpacing) * root.gridSpacing)
                                        var snappedHeight = Math.max(minHeight, Math.round(newHeight / root.gridSpacing) * root.gridSpacing)
                                        if (useLeft) {
                                            left = right - snappedWidth
                                        } else {
                                            right = left + snappedWidth
                                        }
                                        if (useTop) {
                                            top = bottom - snappedHeight
                                        } else {
                                            bottom = top + snappedHeight
                                        }
                                    }

                                    diagramModel.moveItem(itemRect.itemId, left, top)
                                    diagramModel.resizeItem(itemRect.itemId, right - left, bottom - top)
                                    edgeCanvas.requestPaint()
                                }

                                Rectangle {
                                    id: resizeTopLeft
                                    width: 12
                                    height: 12
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.leftMargin: -2
                                    anchors.topMargin: -2
                                    color: "#2b3646"
                                    border.color: "#5a6575"
                                    radius: 3

                                    DragHandler {
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeFDiagCursor
                                        onActiveChanged: {
                                            itemRect.resizing = active
                                            if (active) resizeHandles.beginResize()
                                        }
                                        onTranslationChanged: if (active) resizeHandles.applyResize(translation.x, translation.y, "TopLeft")
                                    }
                                }

                                Rectangle {
                                    id: resizeTopRight
                                    width: 12
                                    height: 12
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.rightMargin: -2
                                    anchors.topMargin: -2
                                    color: "#2b3646"
                                    border.color: "#5a6575"
                                    radius: 3

                                    DragHandler {
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeBDiagCursor
                                        onActiveChanged: {
                                            itemRect.resizing = active
                                            if (active) resizeHandles.beginResize()
                                        }
                                        onTranslationChanged: if (active) resizeHandles.applyResize(translation.x, translation.y, "TopRight")
                                    }
                                }

                                Rectangle {
                                    id: resizeBottomLeft
                                    width: 12
                                    height: 12
                                    anchors.left: parent.left
                                    anchors.bottom: parent.bottom
                                    anchors.leftMargin: -2
                                    anchors.bottomMargin: -2
                                    color: "#2b3646"
                                    border.color: "#5a6575"
                                    radius: 3

                                    DragHandler {
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeBDiagCursor
                                        onActiveChanged: {
                                            itemRect.resizing = active
                                            if (active) resizeHandles.beginResize()
                                        }
                                        onTranslationChanged: if (active) resizeHandles.applyResize(translation.x, translation.y, "BottomLeft")
                                    }
                                }

                                Rectangle {
                                    id: resizeBottomRight
                                    width: 12
                                    height: 12
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.rightMargin: -2
                                    anchors.bottomMargin: -2
                                    color: "#2b3646"
                                    border.color: "#5a6575"
                                    radius: 3

                                    DragHandler {
                                        target: null
                                        acceptedButtons: Qt.LeftButton
                                        cursorShape: Qt.SizeFDiagCursor
                                        onActiveChanged: {
                                            itemRect.resizing = active
                                            if (active) resizeHandles.beginResize()
                                        }
                                        onTranslationChanged: if (active) resizeHandles.applyResize(translation.x, translation.y, "BottomRight")
                                    }
                                }
                            }

                            Text {
                                id: itemLabel
                                visible: itemRect.itemType !== "freetext" && itemRect.itemType !== "obstacle" && itemRect.itemType !== "wish" && itemRect.itemType !== "image"
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                anchors.leftMargin: itemRect.labelLeftInset
                                anchors.rightMargin: itemRect.labelRightInset
                                anchors.topMargin: itemRect.labelTopInset
                                anchors.bottomMargin: itemRect.labelBottomInset
                                readonly property bool useMarkdown: {
                                    if (itemRect.itemType === "task")
                                        return false
                                    var editingThisItem = dialogs && dialogs.boxDialog
                                        && dialogs.boxDialog.visible
                                        && dialogs.boxDialog.editingItemId === itemRect.itemId
                                    if (editingThisItem)
                                        return true
                                    if (!diagramModel)
                                        return itemRect.selected || itemRect.hovered
                                    return diagramModel.count <= 80 || itemRect.selected || itemRect.hovered
                                }
                                text: model.text
                                color: itemRect.isTask && itemRect.taskCompleted ? "#c9d7ce" : model.textColor
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                textFormat: itemLabel.useMarkdown ? Text.MarkdownText : Text.PlainText
                                font.pixelSize: 14
                                font.bold: itemRect.itemType === "task"
                                font.strikeout: itemRect.isTask && itemRect.taskCompleted
                                maximumLineCount: itemLabel.useMarkdown ? 1000 : Math.max(1, Math.floor(height / (font.pixelSize * 1.3)))
                                elide: itemLabel.useMarkdown ? Text.ElideNone : Text.ElideRight
                                clip: true

                                ToolTip.visible: labelHover.containsMouse
                                ToolTip.delay: 400
                                ToolTip.timeout: 2000
                                ToolTip.text: {
                                    var text = model.text + (model.noteMarkdown ? "\n\n" + model.noteMarkdown : "")
                                    if (itemRect.hasLinkedSubtab) {
                                        text += "\n\nSubtab: " + Math.round(itemRect.linkedSubtabCompletion) + "%"
                                        if (itemRect.linkedSubtabActiveAction !== "")
                                            text += "\nActive: " + itemRect.linkedSubtabActiveAction
                                    }
                                    return text
                                }

                                MouseArea {
                                    id: labelHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
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
                                height: parent.height - (anchors.bottomMargin + 12)
                                maximumLineCount: Math.max(1, Math.floor(height / (font.pixelSize * 1.3)))
                                elide: Text.ElideRight
                                clip: true

                                ToolTip.visible: obstacleHover.containsMouse
                                ToolTip.delay: 400
                                ToolTip.timeout: 2000
                                ToolTip.text: model.text + (model.noteMarkdown ? "\n\n" + model.noteMarkdown : "")

                                MouseArea {
                                    id: obstacleHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
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
                                height: parent.height - (anchors.bottomMargin + 12)
                                maximumLineCount: Math.max(1, Math.floor(height / (font.pixelSize * 1.3)))
                                elide: Text.ElideRight
                                clip: true

                                ToolTip.visible: wishHover.containsMouse
                                ToolTip.delay: 400
                                ToolTip.timeout: 2000
                                ToolTip.text: model.text + (model.noteMarkdown ? "\n\n" + model.noteMarkdown : "")

                                MouseArea {
                                    id: wishHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
                            }

                            Text {
                                id: freeTextLabel
                                visible: itemRect.itemType === "freetext"
                                anchors.fill: parent
                                anchors.topMargin: 24
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                anchors.bottomMargin: 8
                                readonly property bool useMarkdown: {
                                    var editingThisItem = dialogs && dialogs.freeTextDialog
                                        && dialogs.freeTextDialog.visible
                                        && dialogs.freeTextDialog.editingItemId === itemRect.itemId
                                    if (editingThisItem)
                                        return true
                                    if (!diagramModel)
                                        return itemRect.selected || itemRect.hovered
                                    return diagramModel.count <= 80 || itemRect.selected || itemRect.hovered
                                }
                                text: model.text
                                color: model.textColor
                                wrapMode: Text.Wrap
                                horizontalAlignment: Text.AlignLeft
                                verticalAlignment: Text.AlignTop
                                textFormat: freeTextLabel.useMarkdown ? Text.MarkdownText : Text.PlainText
                                font.pixelSize: 13
                                maximumLineCount: freeTextLabel.useMarkdown ? 1000 : Math.max(1, Math.floor(height / (font.pixelSize * 1.35)))
                                elide: freeTextLabel.useMarkdown ? Text.ElideNone : Text.ElideRight
                                clip: true

                                ToolTip.visible: freeTextHover.containsMouse
                                ToolTip.delay: 400
                                ToolTip.timeout: 2000
                                ToolTip.text: model.text + (model.noteMarkdown ? "\n\n" + model.noteMarkdown : "")

                                MouseArea {
                                    id: freeTextHover
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                }
                            }

                            DragHandler {
                                id: itemDrag
                                target: null
                                enabled: !itemRect.resizing
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
                                onTapped: {
                                    root.selectedItemId = itemRect.itemId
                                    if (edgeCanvas)
                                        edgeCanvas.selectedEdgeId = ""
                                }
                                onDoubleTapped: function(eventPoint) {
                                    // Check if double-click is on the edge handle (26x26 button, 6px from top-right)
                                    var localPos = eventPoint.position
                                    var handleLeft = itemRect.width - 6 - 26
                                    var handleRight = itemRect.width - 6
                                    var handleTop = 6
                                    var handleBottom = 6 + 26
                                    var onEdgeHandle = (localPos.x >= handleLeft) && (localPos.x <= handleRight) &&
                                                       (localPos.y >= handleTop) && (localPos.y <= handleBottom)

                                    if (onEdgeHandle) {
                                        // Double-click on edge handle - create connected item of same type
                                        var newX = model.x + model.width + 40
                                        var newY = model.y
                                        dialogs.edgeDropTaskDialog.sourceId = itemRect.itemId
                                        dialogs.edgeDropTaskDialog.sourceType = itemRect.itemType
                                        dialogs.edgeDropTaskDialog.dropX = newX
                                        dialogs.edgeDropTaskDialog.dropY = newY
                                        dialogs.edgeDropTaskDialog.open()
                                    } else if (itemRect.itemType === "chatgpt") {
                                        diagramModel.openChatGpt(itemRect.itemId)
                                    } else if (itemRect.itemType === "note" || itemRect.itemType === "wish" || itemRect.itemType === "obstacle") {
                                        if (markdownNoteManager) {
                                            markdownNoteManager.openNote(itemRect.itemId)
                                        }
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex < 0) {
                                        // Task not yet linked to task list - create new task
                                        dialogs.newTaskDialog.openWithItem(itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex >= 0) {
                                        // Task linked to task list - rename it (syncs both ways)
                                        dialogs.taskRenameDialog.openWithItem(itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "freetext") {
                                        // Free text uses dedicated dialog with TextArea
                                        root.openFreeTextDialog(Qt.point(model.x, model.y), itemRect.itemId, model.text)
                                    } else if (itemRect.itemType !== "task") {
                                        root.openPresetDialog(itemRect.itemType, Qt.point(model.x, model.y), itemRect.itemId, model.text)
                                    }
                                }
                            }

                            TapHandler {
                                acceptedButtons: Qt.RightButton
                                onTapped: {
                                    root.selectedItemId = itemRect.itemId
                                    diagramLayer.contextMenuItemId = itemRect.itemId
                                    itemContextMenu.popup()
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
                                property bool hoverActive: false

                                Timer {
                                    id: edgeHoverMenuTimer
                                    interval: 250
                                    repeat: false
                                    onTriggered: {
                                        if (!diagramModel || !edgeHandle.hoverActive || edgeDrag.active || dialogs.edgeDropMenu.visible)
                                            return
                                        var dropX = model.x + model.width + 40
                                        var dropY = model.y
                                        root.showEdgeDropSuggestions(itemRect.itemId, dropX, dropY)
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    acceptedButtons: Qt.NoButton
                                    onEntered: {
                                        edgeHandle.hoverActive = true
                                        edgeHoverMenuTimer.restart()
                                    }
                                    onExited: {
                                        edgeHandle.hoverActive = false
                                        edgeHoverMenuTimer.stop()
                                    }
                                }

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
                                        var pos = edgeHandle.mapToItem(diagramLayer, centroid.position.x, centroid.position.y)
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

        // Keyboard shortcuts hint bar
        Rectangle {
            Layout.fillWidth: true
            height: 36
            color: "#121e2a"
            border.color: "#2a3e52"
            border.width: 1
            radius: 10

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 10

                Label {
                    text: "Shortcuts"
                    color: "#8ea6bc"
                    font.pixelSize: 11
                    font.bold: true
                }

                Repeater {
                    model: [
                        "Ctrl+Enter  New Task",
                        "Ctrl+V  Paste",
                        "Ctrl+S  Save",
                        "F2  Rename",
                        "Ctrl+Scroll  Zoom"
                    ]

                    delegate: Rectangle {
                        radius: 6
                        color: "#17283a"
                        border.color: "#324a60"
                        border.width: 1
                        implicitHeight: 22
                        implicitWidth: keyText.implicitWidth + 16

                        Text {
                            id: keyText
                            anchors.centerIn: parent
                            text: modelData
                            color: "#c4d3e2"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }

                Item { Layout.fillWidth: true }
            }
        }
        }  // Close main content ColumnLayout
    }  // Close outer RowLayout

    // Save notification toast
    Rectangle {
        id: saveNotification
        property alias text: saveNotificationText.text
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 40
        width: saveNotificationText.width + 32
        height: 40
        radius: 20
        color: "#1f6a83"
        border.color: "#56c9ee"
        border.width: 1
        opacity: 0
        z: 1000

        Text {
            id: saveNotificationText
            anchors.centerIn: parent
            text: ""
            color: "#ffffff"
            font.pixelSize: 14
            font.bold: true
        }

        Behavior on opacity {
            NumberAnimation { duration: 200 }
        }
    }

    Timer {
        id: saveNotificationTimer
        interval: 2000
        onTriggered: saveNotification.opacity = 0
    }

    Popup {
        id: reminderPopup
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        x: (root.width - width) / 2
        y: 70
        width: Math.min(root.width - 40, 420)

        background: Rectangle {
            radius: 10
            color: "#162536"
            border.color: "#e67e22"
            border.width: 2
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Text {
                text: "Reminder Due"
                color: "#ffd7b0"
                font.pixelSize: 14
                font.bold: true
            }

            Text {
                Layout.fillWidth: true
                text: root.pendingReminderTaskTitle && root.pendingReminderTaskTitle.length > 0 ? root.pendingReminderTaskTitle : "Task"
                color: "#f5f6f8"
                wrapMode: Text.WordWrap
            }

            RowLayout {
                spacing: 8

                Button {
                    text: "Open Task"
                    onClicked: {
                        var tabIndex = root.pendingReminderTabIndex
                        var taskIndex = root.pendingReminderTaskIndex
                        reminderPopup.close()
                        if (projectManager && projectManager.openReminderTask) {
                            projectManager.openReminderTask(tabIndex, taskIndex)
                        } else {
                            root.drillToTask(taskIndex)
                        }
                    }
                }

                Button {
                    text: "Dismiss"
                    onClicked: reminderPopup.close()
                }
            }
        }

        onClosed: {
            root.reminderPopupBusy = false
            root.showNextReminderAlert()
        }
    }

    Connections {
        target: projectManager
        enabled: projectManager !== null
        function onSaveCompleted(filePath) {
            root.showSaveNotification("Project saved")
        }
        function onLoadCompleted(filePath) {
            root.updateBoardBounds()
            root.refreshLinkingTabsPanel()
            Qt.callLater(root.scrollToContent)
        }
        function onTabSwitched() {
            root.updateBoardBounds()
            root.refreshLinkingTabsPanel()
            Qt.callLater(root.scrollToContent)
        }
        function onTaskDrillRequested(taskIndex) {
            root.showWindow()
            root.drillToTask(taskIndex)
        }
    }

    Connections {
        target: projectManager
        enabled: projectManager !== null
        function onTaskReminderDue(tabIndex, taskIndex, taskTitle) {
            root.showWindow()
            root.showReminderAlert(tabIndex, taskIndex, taskTitle)
        }
    }

    Connections {
        target: tabModel
        enabled: tabModel !== null
        function onTabsChanged() {
            root.refreshLinkingTabsPanel()
        }
        function onCurrentTabChanged() {
            root.refreshLinkingTabsPanel()
        }
        function onCurrentTabIndexChanged() {
            root.refreshLinkingTabsPanel()
        }
        function onDataChanged() {
            root.refreshLinkingTabsPanel()
        }
        function onRowsInserted() {
            root.refreshLinkingTabsPanel()
        }
        function onRowsRemoved() {
            root.refreshLinkingTabsPanel()
        }
        function onModelReset() {
            root.refreshLinkingTabsPanel()
        }
    }

    Component.onCompleted: {
        updateBoardBounds()
        refreshLinkingTabsPanel()
        Qt.callLater(resetView)
    }
}
