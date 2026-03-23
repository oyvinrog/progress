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
        var tabName = activeTabDisplayName()
        var projectName = projectDisplayName()
        if (projectName !== "")
            return "ActionDraw - " + tabName + " - " + projectName
        return "ActionDraw - " + tabName
    }

    property var diagramModelRef: diagramModel
    property var taskModelRef: taskModel
    property var projectManagerRef: projectManager
    property var markdownNoteManagerRef: markdownNoteManager
    property var tabModelRef: tabModel
    property var priorityPlotWindowRef: null
    property var hierarchyWindowRef: null
    property real hierarchyFocusZoom: 1.2
    property bool yubiKeyPromptVisible: false
    property string yubiKeyPromptText: "Touch your YubiKey to continue."
    property bool suppressClosePrompt: false
    property bool closeAfterSaveAsRequested: false

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
        notificationSettingsDialog: dialogs.notificationSettingsDialog
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

    function activeTabDisplayName() {
        if (tabModelRef && tabModelRef.currentTabName) {
            var name = String(tabModelRef.currentTabName).trim()
            if (name.length > 0)
                return name
        }
        return "Main"
    }

    function projectDisplayName() {
        if (projectManagerRef && projectManagerRef.currentFilePath) {
            var path = String(projectManagerRef.currentFilePath)
            if (path.length > 0) {
                var name = path.split("/").pop()
                if (name.endsWith(".progress"))
                    name = name.slice(0, -9)
                return name
            }
        }
        return ""
    }

    function openPriorityPlotWindow() {
        if (!tabModelRef)
            return
        if (priorityPlotWindowRef) {
            priorityPlotWindowRef.show()
            priorityPlotWindowRef.raise()
            priorityPlotWindowRef.requestActivate()
            return
        }
        var component = Qt.createComponent(Qt.resolvedUrl("PriorityPlotWindow.qml"))
        if (component.status === Component.Error) {
            console.log("Failed to load PriorityPlotWindow:", component.errorString())
            return
        }
        var win = component.createObject(root, {
            "tabModel": tabModelRef,
            "projectManager": projectManagerRef
        })
        if (!win) {
            console.log("Failed to instantiate PriorityPlotWindow")
            return
        }
        priorityPlotWindowRef = win
        win.closing.connect(function() {
            priorityPlotWindowRef = null
        })
        win.show()
        win.raise()
        win.requestActivate()
    }

    function openHierarchyWindow(scopeTabIndex) {
        if (!tabModelRef || !projectManagerRef)
            return
        var resolvedScope = -1
        if (scopeTabIndex !== undefined && scopeTabIndex !== null) {
            resolvedScope = Number(scopeTabIndex)
        } else if (tabModelRef && tabModelRef.currentTabIndex !== undefined) {
            resolvedScope = Number(tabModelRef.currentTabIndex)
        }
        if (hierarchyWindowRef) {
            if (hierarchyWindowRef.setScopeTabIndex) {
                hierarchyWindowRef.setScopeTabIndex(resolvedScope)
            } else if (hierarchyWindowRef.scopeTabIndex !== undefined) {
                hierarchyWindowRef.scopeTabIndex = resolvedScope
            }
            hierarchyWindowRef.show()
            hierarchyWindowRef.raise()
            hierarchyWindowRef.requestActivate()
            return
        }
        var component = Qt.createComponent(Qt.resolvedUrl("HierarchyWindow.qml"))
        if (component.status === Component.Error) {
            console.log("Failed to load HierarchyWindow:", component.errorString())
            return
        }
        var win = component.createObject(root, {
            "tabModel": tabModelRef,
            "projectManager": projectManagerRef,
            "hostWindow": root,
            "scopeTabIndex": resolvedScope
        })
        if (!win) {
            console.log("Failed to instantiate HierarchyWindow")
            return
        }
        hierarchyWindowRef = win
        win.closing.connect(function() {
            hierarchyWindowRef = null
        })
        win.show()
        win.raise()
        win.requestActivate()
    }

    function focusHierarchyTarget(tabIndex, taskIndex, itemId, closeNavigator) {
        if (!projectManagerRef || !diagramModelRef)
            return

        var resolvedTabIndex = Number(tabIndex)
        var resolvedTaskIndex = Number(taskIndex)
        var resolvedItemId = itemId ? String(itemId) : ""
        var shouldClose = (closeNavigator === undefined) ? true : !!closeNavigator

        if (resolvedTaskIndex >= 0 && projectManagerRef.openTabTask) {
            projectManagerRef.openTabTask(resolvedTabIndex, resolvedTaskIndex)
        } else if (resolvedTabIndex >= 0 && projectManagerRef.switchTab) {
            projectManagerRef.switchTab(resolvedTabIndex)
        }

        var applyFocus = function() {
            root.setZoomDirect(root.hierarchyFocusZoom)

            if (resolvedItemId.length > 0 && diagramModelRef.getItemSnapshot) {
                var snapshot = diagramModelRef.getItemSnapshot(resolvedItemId)
                if (snapshot && (snapshot.x || snapshot.x === 0) && (snapshot.y || snapshot.y === 0)) {
                    var width = Number(snapshot.width || 0)
                    var height = Number(snapshot.height || 0)
                    root.centerOnPoint(snapshot.x + (width / 2), snapshot.y + (height / 2))
                    return
                }
            }

            if (resolvedTaskIndex >= 0) {
                root.drillToTask(resolvedTaskIndex)
                return
            }
            root.scrollToContent()
        }

        Qt.callLater(function() {
            Qt.callLater(applyFocus)
        })

        if (shouldClose && hierarchyWindowRef)
            hierarchyWindowRef.close()
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
            return false
        }
        if (projectManager.hasCurrentFile()) {
            return projectManager.saveCurrentProject()
        } else {
            dialogs.saveDialog.open()
            return false
        }
    }

    function forceCloseWithoutPrompt() {
        suppressClosePrompt = true
        root.close()
    }

    function handleSaveDialogAccepted(saved) {
        if (!closeAfterSaveAsRequested)
            return
        closeAfterSaveAsRequested = false
        if (saved)
            forceCloseWithoutPrompt()
    }

    function handleSaveDialogRejected() {
        closeAfterSaveAsRequested = false
    }

    function showSaveNotification(message) {
        saveNotification.text = message
        saveNotification.opacity = 1
        saveNotificationTimer.restart()
    }

    function showErrorDialog(message) {
        errorDialog.messageText = message
        errorDialog.open()
    }

    function showYubiKeyPrompt(message) {
        yubiKeyPromptText = (message && message.length > 0) ? message : "Touch your YubiKey to continue."
        yubiKeyPromptVisible = true
        yubiKeyTouchDialog.open()
    }

    function hideYubiKeyPrompt() {
        yubiKeyPromptVisible = false
        yubiKeyTouchDialog.close()
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

    function refreshActiveReminders() {
        if (!projectManager || !projectManager.getActiveReminders) {
            activeReminders = []
            return
        }
        var hadReminders = activeReminders && activeReminders.length > 0
        activeReminders = projectManager.getActiveReminders()
        if ((!hadReminders || !reminderOverviewTouched) && activeReminders.length > 0)
            reminderOverviewExpanded = true
        if (activeReminders.length === 0)
            reminderOverviewTouched = false
    }

    function refreshActiveContracts() {
        if (!projectManager || !projectManager.getActiveContracts) {
            activeContracts = []
            return
        }
        activeContracts = projectManager.getActiveContracts()
    }

    function refreshOverviewData() {
        refreshActiveReminders()
        refreshActiveContracts()
    }

    function formatRemainingTime(totalSeconds) {
        var totalSecs = Math.floor(Number(totalSeconds))
        if (totalSecs < 0)
            totalSecs = 0
        var hours = Math.floor(totalSecs / 3600)
        var mins = Math.floor((totalSecs % 3600) / 60)
        var secs = totalSecs % 60
        if (hours > 0)
            return hours + "h " + mins + "m " + secs + "s"
        return mins + "m " + secs + "s"
    }

    function showNextContractAlert() {
        if (root.contractPopupBusy)
            return
        if (!root.contractQueue || root.contractQueue.length === 0)
            return
        root.contractPopupBusy = true
        var nextContract = root.contractQueue.shift()
        root.pendingContractTabIndex = nextContract.tabIndex
        root.pendingContractTaskIndex = nextContract.taskIndex
        root.pendingContractTaskTitle = nextContract.taskTitle
        root.pendingContractPunishment = nextContract.punishment
        root.pendingContractDeadline = nextContract.deadlineText
        contractPopup.open()
    }

    function showContractAlert(tabIndex, taskIndex, taskTitle, punishment, deadlineText) {
        var contractAlert = {
            tabIndex: tabIndex,
            taskIndex: taskIndex,
            taskTitle: taskTitle && taskTitle.length > 0 ? taskTitle : "Task",
            punishment: punishment && punishment.length > 0 ? punishment : "Punishment",
            deadlineText: deadlineText && deadlineText.length > 0 ? deadlineText : "",
        }
        root.contractQueue.push(contractAlert)
        if (!contractPopup.visible)
            root.showNextContractAlert()
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
    property int sceneWidth: Math.max(1, Math.ceil(originOffsetX + boardWidth))
    property int sceneHeight: Math.max(1, Math.ceil(originOffsetY + boardHeight))

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
        var padding = 30
        // If there's a current task, center on it
        var taskPos = diagramModel.getCurrentTaskPosition()
        if (taskPos) {
            var centerX = taskPos.x + taskPos.width / 2
            var centerY = taskPos.y + taskPos.height / 2
            focusPointWithinDiagramBounds(centerX, centerY, padding)
            return
        }
        // Otherwise scroll to show content with some padding
        var minX = diagramModel.minItemX
        var minY = diagramModel.minItemY
        var targetX = Math.max(0, (minX - padding + root.originOffsetX) * root.zoomLevel)
        var targetY = Math.max(0, (minY - padding + root.originOffsetY) * root.zoomLevel)
        viewport.contentX = targetX
        viewport.contentY = targetY
    }

    function applyDefaultView() {
        if (!viewport || viewport.width <= 0 || viewport.height <= 0) {
            Qt.callLater(root.applyDefaultView)
            return
        }

        root.zoomLevel = clampZoom(0.95)

        if (gridCanvas)
            gridCanvas.requestPaint()
        if (edgeCanvas)
            edgeCanvas.requestPaint()

        if (!diagramModel || diagramModel.count === 0) {
            centerOnPoint((root.boardWidth / 2) - root.originOffsetX, (root.boardHeight / 2) - root.originOffsetY)
            return
        }

        scrollToContent()
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
    property int pendingContractTabIndex: 0
    property int pendingContractTaskIndex: -1
    property string pendingContractTaskTitle: ""
    property string pendingContractPunishment: ""
    property string pendingContractDeadline: ""
    property var contractQueue: []
    property bool contractPopupBusy: false
    property var activeReminders: []
    property var activeContracts: []
    property bool reminderOverviewExpanded: false
    property bool reminderOverviewTouched: false
    property bool contractOverviewExpanded: true
    property bool tabDragActive: false
    property bool tabDragInsideViewport: false
    property string tabDragPreviewName: ""
    property real tabDragPreviewX: 0
    property real tabDragPreviewY: 0

    Shortcut {
        sequence: "Alt+Left"
        enabled: projectManager !== null
            && projectManager.canGoBack
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
            && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: projectManager.goBack()
    }

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
        enabled: diagramModel !== null || tabModelRef !== null
        onActivated: {
            if (root.selectedItemId && root.selectedItemId.length > 0) {
                root.renameSelectedItem()
            } else if (sidebarTabs && sidebarTabs.renameCurrentTab) {
                sidebarTabs.renameCurrentTab()
            }
        }
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: diagramModel !== null && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: root.addTaskOrConnectedTask()
    }

    Shortcut {
        sequence: "Ctrl+-"
        enabled: diagramModel !== null && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: root.addTaskOrConnectedTaskBackward()
    }

    Shortcut {
        sequence: "Ctrl+Minus"
        enabled: diagramModel !== null && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: root.addTaskOrConnectedTaskBackward()
    }

    Shortcut {
        sequence: "Ctrl+M"
        enabled: diagramModel !== null
        onActivated: root.openMarkdownNoteForSelection()
    }

    Shortcut {
        sequence: "Ctrl+N"
        enabled: diagramModel !== null && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: root.addConnectedNote()
    }

    Shortcut {
        sequence: "Ctrl+K"
        enabled: tabModelRef !== null
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
            && (!markdownNoteManager || !markdownNoteManager.editorOpen)
        onActivated: {
            if (sidebarTabs && sidebarTabs.focusSearchField)
                sidebarTabs.focusSearchField()
        }
    }

    Shortcut {
        sequence: "Delete"
        enabled: diagramModel !== null
            && root.selectedItemId.length > 0
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
        onActivated: root.deleteSelectedItem()
    }

    Shortcut {
        sequence: "Left"
        enabled: diagramModel !== null
            && root.selectedItemId.length > 0
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
        onActivated: root.navigateConnectedItem("left")
    }

    Shortcut {
        sequence: "Right"
        enabled: diagramModel !== null
            && root.selectedItemId.length > 0
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
        onActivated: root.navigateConnectedItem("right")
    }

    Shortcut {
        sequence: "Up"
        enabled: diagramModel !== null
            && root.selectedItemId.length > 0
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
        onActivated: root.navigateConnectedItem("up")
    }

    Shortcut {
        sequence: "Down"
        enabled: diagramModel !== null
            && root.selectedItemId.length > 0
            && (!dialogs || !dialogs.anyDialogVisible)
            && !reminderPopup.visible
            && !contractPopup.visible
        onActivated: root.navigateConnectedItem("down")
    }

    Timer {
        id: overviewRefreshTimer
        interval: 1000
        repeat: true
        running: true
        onTriggered: root.refreshOverviewData()
    }

    function findEdgeById(edgeId) {
        if (!diagramModel || !edgeId || edgeId.length === 0)
            return null
        var edges = diagramModel.edges
        for (var i = 0; i < edges.length; ++i) {
            if (edges[i].id === edgeId)
                return edges[i]
        }
        return null
    }

    function openQuickTaskDialogForEdge(edge) {
        if (!diagramModel || !edge)
            return false
        var fromItem = diagramModel.getItemSnapshot(edge.fromId)
        var toItem = diagramModel.getItemSnapshot(edge.toId)
        if (!fromItem || !(fromItem.x || fromItem.x === 0) || !toItem || !(toItem.x || toItem.x === 0))
            return false

        var midCenterX = ((fromItem.x + fromItem.width / 2) + (toItem.x + toItem.width / 2)) / 2
        var midCenterY = ((fromItem.y + fromItem.height / 2) + (toItem.y + toItem.height / 2)) / 2
        var taskWidth = 140
        var taskHeight = 70
        var targetPoint = Qt.point(midCenterX - taskWidth / 2, midCenterY - taskHeight / 2)

        dialogs.quickTaskDialog.edgeInsertMode = true
        dialogs.quickTaskDialog.edgeId = edge.id
        dialogs.quickTaskDialog.edgeFromId = edge.fromId
        dialogs.quickTaskDialog.edgeToId = edge.toId
        dialogs.quickTaskDialog.targetX = targetPoint.x
        dialogs.quickTaskDialog.targetY = targetPoint.y
        dialogs.quickTaskDialog.open()
        return true
    }

    function addTaskOrConnectedTask() {
        if (!diagramModel)
            return
        if (edgeCanvas && edgeCanvas.selectedEdgeId && edgeCanvas.selectedEdgeId.length > 0) {
            var selectedEdge = findEdgeById(edgeCanvas.selectedEdgeId)
            if (selectedEdge && openQuickTaskDialogForEdge(selectedEdge))
                return
            edgeCanvas.selectedEdgeId = ""
        }
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

    function addTaskOrConnectedTaskBackward(sourceIdOverride) {
        if (!diagramModel)
            return
        var sourceId = sourceIdOverride || ""
        var item = null
        if (sourceId.length > 0) {
            item = diagramModel.getItemSnapshot(sourceId)
            if (!item || !(item.x || item.x === 0))
                sourceId = ""
        }
        if (!sourceId && root.selectedItemId && root.selectedItemId.length > 0) {
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
            // Backward chain: create predecessor task and connect new -> source.
            var dropX = item.x - ((item.width || 100) + 50)
            var dropY = item.y
            dialogs.edgeDropTaskDialog.sourceId = sourceId
            dialogs.edgeDropTaskDialog.sourceType = "task"
            dialogs.edgeDropTaskDialog.dropX = dropX
            dialogs.edgeDropTaskDialog.dropY = dropY
            dialogs.edgeDropTaskDialog.reverseDirection = true
            dialogs.edgeDropTaskDialog.open()
        } else {
            addQuickTaskAtCenter()
        }
    }

    function openMarkdownNoteForSelection() {
        if (!diagramModel)
            return
        if (!root.selectedItemId || root.selectedItemId.length === 0)
            return
        var item = diagramModel.getItemSnapshot(root.selectedItemId)
        if (!item || !item.type)
            return
        if (item.type === "note") {
            root.openPresetDialog("note", Qt.point(item.x, item.y), item.id, item.text)
            return
        }
        if (item.type === "freetext") {
            root.openFreeTextDialog(Qt.point(item.x, item.y), item.id, item.text)
            return
        }
        if (markdownNoteManager)
            markdownNoteManager.openNote(root.selectedItemId)
    }

    function openObstacleForItem(itemId) {
        if (!diagramModel || !markdownNoteManager)
            return
        if (!itemId || itemId.length === 0)
            return
        var item = diagramModel.getItemSnapshot(itemId)
        if (!item || !item.type || item.type === "image")
            return
        markdownNoteManager.openObstacle(itemId)
    }

    function openObstacleForSelection() {
        openObstacleForItem(root.selectedItemId)
    }

    function addConnectedNote() {
        if (!diagramModel)
            return
        var sourceId = ""
        var sourceItem = null
        if (root.selectedItemId && root.selectedItemId.length > 0) {
            sourceItem = diagramModel.getItemSnapshot(root.selectedItemId)
            if (sourceItem && (sourceItem.x || sourceItem.x === 0))
                sourceId = root.selectedItemId
        }
        if (!sourceId && root.lastCreatedTaskId && root.lastCreatedTaskId.length > 0) {
            sourceItem = diagramModel.getItemSnapshot(root.lastCreatedTaskId)
            if (sourceItem && (sourceItem.x || sourceItem.x === 0))
                sourceId = root.lastCreatedTaskId
            else
                root.lastCreatedTaskId = ""
        }
        if (!sourceId) {
            var center = root.diagramCenterPoint()
            var centerSnapped = root.snapPoint(center)
            var centerNoteId = diagramModel.addPresetItem("note", centerSnapped.x, centerSnapped.y)
            if (centerNoteId && centerNoteId.length > 0)
                root.selectedItemId = centerNoteId
            return
        }

        var dropX = sourceItem.x + (sourceItem.width || 100) + 50
        var dropY = sourceItem.y
        var drop = root.resolveConnectedDrop(sourceId, "note", dropX, dropY)
        var noteId = diagramModel.addPresetItemAndConnect(sourceId, "note", drop.x, drop.y, "Note")
        if (noteId && noteId.length > 0)
            root.selectedItemId = noteId
    }

    function deleteSelectedItem() {
        if (!diagramModel || !root.selectedItemId || root.selectedItemId.length === 0)
            return
        var itemId = root.selectedItemId
        diagramModel.removeItem(itemId)
        if (root.selectedItemId === itemId)
            root.selectedItemId = ""
        if (edgeCanvas && edgeCanvas.selectedEdgeId && edgeCanvas.selectedEdgeId.length > 0)
            edgeCanvas.selectedEdgeId = ""
    }

    function navigateConnectedItem(direction) {
        if (!diagramModel || !root.selectedItemId || root.selectedItemId.length === 0)
            return
        var nextId = diagramModel.findNearestConnectedItemInDirection(root.selectedItemId, direction)
        if (!nextId || nextId.length === 0)
            return
        root.selectedItemId = nextId
        if (edgeCanvas)
            edgeCanvas.selectedEdgeId = ""

        var item = diagramModel.getItemSnapshot(nextId)
        if (!item || !(item.x || item.x === 0))
            return
        var centerX = item.x + (item.width || 120) / 2
        var centerY = item.y + (item.height || 60) / 2
        centerOnPoint(centerX, centerY)
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

    function resolveConnectedDrop(sourceId, itemKind, dropX, dropY) {
        var snappedX = root.snapValue(dropX)
        var snappedY = root.snapValue(dropY)
        if (!diagramModel || !diagramModel.resolveConnectedPlacement)
            return Qt.point(snappedX, snappedY)
        var placement = diagramModel.resolveConnectedPlacement(
            sourceId,
            itemKind,
            snappedX,
            snappedY,
            root.gridSpacing
        )
        if (!placement || !(placement.x || placement.x === 0) || !(placement.y || placement.y === 0))
            return Qt.point(snappedX, snappedY)
        return Qt.point(root.snapValue(placement.x), root.snapValue(placement.y))
    }

    function diagramCenterPoint() {
        var cx = (viewport.contentX + viewport.width / 2) / root.zoomLevel - root.originOffsetX
        var cy = (viewport.contentY + viewport.height / 2) / root.zoomLevel - root.originOffsetY
        return snapPoint(Qt.point(cx, cy))
    }

    function viewportPointToDiagram(vx, vy) {
        var dx = (viewport.contentX + vx) / root.zoomLevel - root.originOffsetX
        var dy = (viewport.contentY + vy) / root.zoomLevel - root.originOffsetY
        return Qt.point(dx, dy)
    }

    function diagramPointToViewport(dx, dy) {
        var vx = (dx + root.originOffsetX) * root.zoomLevel - viewport.contentX
        var vy = (dy + root.originOffsetY) * root.zoomLevel - viewport.contentY
        return Qt.point(vx, vy)
    }

    function clearTabDragPreview() {
        root.tabDragActive = false
        root.tabDragInsideViewport = false
        root.tabDragPreviewName = ""
        root.tabDragPreviewX = 0
        root.tabDragPreviewY = 0
    }

    function updateTabDragHover(tabIndex, tabName, sceneX, sceneY, active) {
        if (!active) {
            root.clearTabDragPreview()
            return
        }
        root.tabDragActive = true
        root.tabDragPreviewName = tabName || ""

        if (!diagramModel || tabIndex === undefined || tabIndex < 0) {
            root.tabDragInsideViewport = false
            return
        }

        var viewportPos = viewport.mapFromItem(null, sceneX, sceneY)
        var insideViewport = (
            viewportPos.x >= 0 && viewportPos.x <= viewport.width &&
            viewportPos.y >= 0 && viewportPos.y <= viewport.height
        )
        root.tabDragInsideViewport = insideViewport
        if (!insideViewport)
            return

        var diagramPoint = root.viewportPointToDiagram(viewportPos.x, viewportPos.y)
        var snapped = root.snapPoint(diagramPoint)
        root.tabDragPreviewX = snapped.x
        root.tabDragPreviewY = snapped.y
    }

    function handleTabDragRelease(tabIndex, sceneX, sceneY) {
        if (!projectManager || !diagramModel) {
            root.clearTabDragPreview()
            return
        }
        if (tabIndex === undefined || tabIndex < 0) {
            root.clearTabDragPreview()
            return
        }

        var viewportPos = viewport.mapFromItem(null, sceneX, sceneY)
        var insideViewport = (
            viewportPos.x >= 0 && viewportPos.x <= viewport.width &&
            viewportPos.y >= 0 && viewportPos.y <= viewport.height
        )
        if (!insideViewport) {
            root.clearTabDragPreview()
            return
        }

        var diagramPoint = root.viewportPointToDiagram(viewportPos.x, viewportPos.y)
        var snapped = root.snapPoint(diagramPoint)
        var newId = projectManager.addTabAsDrillTask(tabIndex, snapped.x, snapped.y)
        if (newId && newId.length > 0) {
            root.selectedItemId = newId
            root.lastCreatedTaskId = newId
        }
        root.clearTabDragPreview()
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
        if (diagramModel.hasClipboardOpml() || diagramModel.hasClipboardTextLines()) {
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
        if (!markdownNoteManager || !markdownNoteManager.openFreeText)
            return
        markdownNoteManager.openFreeText(
            itemId || "",
            snapValue(point.x),
            snapValue(point.y),
            initialText !== undefined ? initialText : ""
        )
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

    function focusPointWithinDiagramBounds(x, y, padding) {
        var visibleWidth = viewport.width / root.zoomLevel
        var visibleHeight = viewport.height / root.zoomLevel
        var minLeft = diagramModel.minItemX - padding
        var minTop = diagramModel.minItemY - padding
        var maxLeft = (diagramModel.maxItemX + padding) - visibleWidth
        var maxTop = (diagramModel.maxItemY + padding) - visibleHeight

        var targetLeft = x - visibleWidth / 2
        var targetTop = y - visibleHeight / 2

        if (maxLeft < minLeft)
            targetLeft = minLeft
        else
            targetLeft = Math.min(Math.max(targetLeft, minLeft), maxLeft)

        if (maxTop < minTop)
            targetTop = minTop
        else
            targetTop = Math.min(Math.max(targetTop, minTop), maxTop)

        var targetX = (targetLeft + root.originOffsetX) * root.zoomLevel
        var targetY = (targetTop + root.originOffsetY) * root.zoomLevel
        var maxX = Math.max(0, viewport.contentWidth - viewport.width)
        var maxY = Math.max(0, viewport.contentHeight - viewport.height)
        viewport.contentX = Math.min(Math.max(targetX, 0), maxX)
        viewport.contentY = Math.min(Math.max(targetY, 0), maxY)
    }

    function resetView() {
        applyDefaultView()
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
        edgeCanvas: edgeCanvas
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        SidebarTabs {
            id: sidebarTabs
            tabModel: tabModelRef
            projectManager: projectManagerRef
            onTabDragMoved: root.updateTabDragHover
            onTabDragReleased: root.handleTabDragRelease
            onAnalyzeHierarchy: function(tabIndex) { root.openHierarchyWindow(tabIndex) }
        }

        // Main content area (right side)
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                visible: (root.activeReminders && root.activeReminders.length > 0)
                    || (root.activeContracts && root.activeContracts.length > 0)
                radius: 10
                color: "#18232d"
                border.color: "#3a5266"
                border.width: 1
                implicitHeight: overviewColumn.implicitHeight + 16

                Column {
                    id: overviewColumn
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8

                    Rectangle {
                        width: overviewColumn.width
                        height: reminderHeaderRow.implicitHeight + 12
                        radius: 8
                        color: "#21313d"
                        border.color: "#3b566a"
                        border.width: 1
                        visible: root.activeReminders && root.activeReminders.length > 0

                        RowLayout {
                            id: reminderHeaderRow
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            Text {
                                text: "Waiting Reminders"
                                color: "#ffe4c7"
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                text: root.activeReminders.length + " pending"
                                color: "#d6a66b"
                                font.pixelSize: 10
                                font.bold: true
                            }

                            Item {
                                Layout.fillWidth: true
                            }

                            Button {
                                text: root.reminderOverviewExpanded ? "Roll Up" : "Roll Down"
                                onClicked: {
                                    root.reminderOverviewExpanded = !root.reminderOverviewExpanded
                                    root.reminderOverviewTouched = true
                                }
                            }
                        }
                    }

                    Column {
                        width: overviewColumn.width
                        spacing: 6
                        visible: root.activeReminders && root.activeReminders.length > 0 && root.reminderOverviewExpanded

                        Repeater {
                            model: root.activeReminders
                            delegate: Rectangle {
                                width: overviewColumn.width
                                height: 40
                                radius: 6
                                color: "#2e261f"
                                border.color: "#8d6948"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    Column {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        Text {
                                            text: "[" + modelData.tabName + "] " + modelData.taskTitle
                                            color: "#fff7ef"
                                            font.pixelSize: 11
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: "Remind at " + modelData.reminderText
                                            color: "#f1c892"
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Button {
                                        text: "Open Task"
                                        onClicked: {
                                            if (projectManager && projectManager.openTabTask)
                                                projectManager.openTabTask(Number(modelData.tabIndex), Number(modelData.taskIndex))
                                        }
                                    }

                                    Button {
                                        text: "Clear"
                                        onClicked: {
                                            if (projectManager && projectManager.clearReminder) {
                                                projectManager.clearReminder(Number(modelData.tabIndex), Number(modelData.taskIndex))
                                                root.refreshActiveReminders()
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        width: overviewColumn.width
                        height: contractHeaderRow.implicitHeight + 12
                        radius: 8
                        color: "#2b1b1f"
                        border.color: "#b25d6d"
                        border.width: 1
                        visible: root.activeContracts && root.activeContracts.length > 0

                        RowLayout {
                            id: contractHeaderRow
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            Text {
                                text: "Active Contracts"
                                color: "#ffd4d4"
                                font.pixelSize: 12
                                font.bold: true
                            }

                            Text {
                                text: root.activeContracts.length + " active"
                                color: "#f0aeb7"
                                font.pixelSize: 10
                                font.bold: true
                            }

                            Item {
                                Layout.fillWidth: true
                            }

                            Button {
                                text: root.contractOverviewExpanded ? "Roll Up" : "Roll Down"
                                onClicked: root.contractOverviewExpanded = !root.contractOverviewExpanded
                            }
                        }
                    }

                    Column {
                        width: overviewColumn.width
                        spacing: 6
                        visible: root.activeContracts && root.activeContracts.length > 0 && root.contractOverviewExpanded

                        Repeater {
                            model: root.activeContracts
                            delegate: Rectangle {
                                width: overviewColumn.width
                                height: contractPunishmentText.visible ? 50 : 32
                                radius: 6
                                color: modelData.breached ? "#4a2222" : "#37252a"
                                border.color: modelData.breached ? "#d46a6a" : "#84515e"
                                border.width: 1

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    Column {
                                        Layout.fillWidth: true
                                        spacing: 1

                                        Text {
                                            text: "[" + modelData.tabName + "] " + modelData.taskTitle
                                            color: "#f6f7fa"
                                            font.pixelSize: 11
                                            font.bold: true
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            id: contractPunishmentText
                                            visible: modelData.punishment && modelData.punishment.length > 0
                                            text: "Punishment: " + modelData.punishment
                                            color: "#f0c6c6"
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                        }
                                    }

                                    Text {
                                        text: {
                                            var remaining = Number(modelData.remainingSeconds)
                                            if (modelData.breached || remaining <= 0)
                                                return "OVERDUE"
                                            return root.formatRemainingTime(remaining)
                                        }
                                        color: modelData.breached ? "#ff9b9b" : "#ffd9a8"
                                        font.pixelSize: 10
                                        font.bold: true
                                    }

                                    Button {
                                        text: "Open Task"
                                        onClicked: {
                                            if (projectManager && projectManager.openTabTask)
                                                projectManager.openTabTask(Number(modelData.tabIndex), Number(modelData.taskIndex))
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: headerContent.implicitHeight + 16
                radius: 10
                color: "#14202b"
                border.color: "#2c3f53"
                border.width: 1

                RowLayout {
                    id: headerContent
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    anchors.topMargin: 8
                    anchors.bottomMargin: 8
                    spacing: 12

                    ColumnLayout {
                        spacing: 2
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter

                        Text {
                            text: "Current Tab: " + root.activeTabDisplayName()
                            color: "#dfefff"
                            font.pixelSize: 13
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            property string projectName: root.projectDisplayName()
                            visible: projectName !== ""
                            text: "Project: " + projectName
                            color: "#8da6bc"
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    ProgressStatsRow {
                        root: root
                        taskModel: taskModelRef
                        diagramModel: diagramModelRef
                        compact: true
                    }
                }
            }

            ToolbarRow {
                root: root
                diagramModel: diagramModelRef
                projectManager: projectManagerRef
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
                contentWidth: root.sceneWidth * root.zoomLevel
                contentHeight: root.sceneHeight * root.zoomLevel
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
                            id: renameTaskMenuItem
                            text: "Rename Task..."
                            icon.name: "edit-rename"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.type === "task" && item.taskIndex >= 0
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
                            text: "Edit Note/Details...\t\tCtrl+M"
                            icon.name: "document-edit"
                            enabled: diagramModel !== null && diagramLayer.contextMenuItemId.length > 0
                            onTriggered: {
                                root.selectedItemId = diagramLayer.contextMenuItemId
                                root.openMarkdownNoteForSelection()
                            }
                        }
                        MenuItem {
                            text: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return "Add Obstacle..."
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                if (item && item.obstacleMarkdown && String(item.obstacleMarkdown).trim().length > 0)
                                    return "Edit Obstacle..."
                                return "Add Obstacle..."
                            }
                            icon.name: "dialog-warning"
                            visible: {
                                if (!diagramModel || !diagramLayer.contextMenuItemId)
                                    return false
                                var item = diagramModel.getItemSnapshot(diagramLayer.contextMenuItemId)
                                return item && item.type !== "image"
                            }
                            height: visible ? implicitHeight : 0
                            onTriggered: {
                                root.selectedItemId = diagramLayer.contextMenuItemId
                                root.openObstacleForSelection()
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
                            property bool taskContractActive: model.taskContractActive
                            property string taskContractDeadline: model.taskContractDeadline
                            property real taskContractRemaining: model.taskContractRemaining
                            property bool taskContractBreached: model.taskContractBreached
                            property string taskContractPunishment: model.taskContractPunishment
                            property real linkedSubtabCompletion: model.linkedSubtabCompletion
                            property string linkedSubtabActiveAction: model.linkedSubtabActiveAction
                            property bool hasLinkedSubtab: model.hasLinkedSubtab
                            property var freeTextTabs: model.textTabs || []
                            property int freeTextTabIndex: model.textTabIndex || 0
                            property int freeTextTabCount: freeTextTabs && freeTextTabs.length !== undefined ? freeTextTabs.length : 0
                            property var freeTextActiveTab: freeTextTabCount > 0
                                ? freeTextTabs[Math.max(0, Math.min(freeTextTabIndex, freeTextTabCount - 1))]
                                : null
                            property string freeTextDisplayText: {
                                if (itemRect.itemType !== "freetext")
                                    return model.text
                                if (freeTextActiveTab && freeTextActiveTab.text !== undefined)
                                    return String(freeTextActiveTab.text || "")
                                return model.text
                            }
                            property string freeTextActiveTabName: {
                                if (itemRect.itemType !== "freetext")
                                    return ""
                                if (freeTextActiveTab && freeTextActiveTab.name !== undefined) {
                                    var tabName = String(freeTextActiveTab.name || "").trim()
                                    if (tabName.length > 0)
                                        return tabName
                                }
                                return freeTextTabCount > 0 ? "Tab " + (Math.max(0, Math.min(freeTextTabIndex, freeTextTabCount - 1)) + 1) : ""
                            }
                            function cycleFreeTextTab(step) {
                                if (!diagramModel || itemRect.itemType !== "freetext" || freeTextTabCount <= 1)
                                    return
                                var nextIndex = freeTextTabIndex + step
                                if (nextIndex < 0)
                                    nextIndex = freeTextTabCount - 1
                                else if (nextIndex >= freeTextTabCount)
                                    nextIndex = 0
                                diagramModel.setItemTextTabIndex(itemRect.itemId, nextIndex)
                            }
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
                            border.width: (itemRect.taskCountdownExpired || itemRect.taskContractBreached) ? 4 : (itemRect.taskCurrent ? 4 : (isEdgeDropTarget ? 3 : 1))
                            border.color: (itemRect.taskCountdownExpired || itemRect.taskContractBreached) ? "#e74c3c" : (itemRect.taskCurrent ? "#ffcc00" : (isEdgeDropTarget ? "#74d9a0" : (itemDrag.active ? Qt.lighter(model.color, 1.4) : Qt.darker(model.color, 1.6))))
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
                                visible: itemRect.itemType !== "note" && itemRect.itemType !== "freetext" && itemRect.itemType !== "image"
                                width: 18
                                height: 18
                                radius: 4
                                anchors.left: itemRect.isTask ? contractButton.right : parent.left
                                anchors.leftMargin: itemRect.isTask ? 6 : 8
                                anchors.top: parent.top
                                anchors.topMargin: 8
                                color: model.noteMarkdown && model.noteMarkdown.trim().length > 0 ? "#6fd3ff" : "#f5d96b"
                                border.color: model.noteMarkdown && model.noteMarkdown.trim().length > 0 ? "#3298c7" : "#d9b84f"
                                border.width: 1
                                z: 22

                                Text {
                                    anchors.centerIn: parent
                                    text: "N"
                                    color: "#1b2028"
                                    font.pixelSize: 11
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.selectedItemId = itemRect.itemId
                                        root.openMarkdownNoteForSelection()
                                    }
                                }
                            }

                            Rectangle {
                                id: obstacleBadge
                                visible: itemRect.itemType !== "image" && model.obstacleMarkdown && model.obstacleMarkdown.trim().length > 0
                                width: 18
                                height: 18
                                radius: 9
                                anchors.left: noteBadge.visible ? noteBadge.right : (itemRect.isTask ? contractButton.right : parent.left)
                                anchors.leftMargin: noteBadge.visible || itemRect.isTask ? 6 : 8
                                anchors.top: parent.top
                                anchors.topMargin: 8
                                color: "#ff9368"
                                border.color: "#d66d48"
                                border.width: 1
                                z: 22

                                Text {
                                    anchors.centerIn: parent
                                    text: "!"
                                    color: "#1b2028"
                                    font.pixelSize: 12
                                    font.bold: true
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openObstacleForItem(itemRect.itemId)
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

                            Rectangle {
                                id: contractButton
                                visible: itemRect.isTask
                                width: 20
                                height: 20
                                radius: 10
                                anchors.left: reminderButton.right
                                anchors.top: parent.top
                                anchors.leftMargin: 4
                                anchors.topMargin: 8
                                color: itemRect.taskContractBreached ? "#d14c4c" : (itemRect.taskContractActive ? "#9b59b6" : "#1a2230")
                                border.color: itemRect.taskContractBreached ? "#b23a3a" : (itemRect.taskContractActive ? "#8e44ad" : "#4b5b72")
                                border.width: 2
                                z: 20

                                Text {
                                    anchors.centerIn: parent
                                    text: "⚑"
                                    color: (itemRect.taskContractActive || itemRect.taskContractBreached) ? "#ffffff" : "#8a93a5"
                                    font.pixelSize: 10
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function(mouse) {
                                        dialogs.contractContextMenu.taskIndex = itemRect.taskIndex
                                        dialogs.contractContextMenu.deadlineAt = itemRect.taskContractDeadline
                                        dialogs.contractContextMenu.punishment = itemRect.taskContractPunishment
                                        if (mouse.button === Qt.RightButton || itemRect.taskContractActive) {
                                            dialogs.contractContextMenu.popup()
                                        } else {
                                            dialogs.contractDialog.taskIndex = itemRect.taskIndex
                                            dialogs.contractDialog.dateValue = ""
                                            dialogs.contractDialog.timeValue = ""
                                            dialogs.contractDialog.punishmentValue = ""
                                            dialogs.contractDialog.open()
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
                                    id: freeTextTabSwitcher
                                    visible: itemRect.freeTextTabCount > 1
                                    anchors.top: parent.top
                                    anchors.right: parent.right
                                    anchors.topMargin: 10
                                    anchors.rightMargin: 10
                                    radius: 8
                                    color: "#172331"
                                    border.color: "#4f657d"
                                    border.width: 1
                                    width: Math.max(118, Math.min(Math.max(118, parent.width - 52), freeTextTabLabel.implicitWidth + 54))
                                    height: 24
                                    z: 90

                                    Row {
                                        anchors.fill: parent
                                        anchors.leftMargin: 4
                                        anchors.rightMargin: 4
                                        spacing: 2

                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 5
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: freeTextPrevMouse.containsMouse ? "#31485f" : "transparent"

                                            Label {
                                                anchors.centerIn: parent
                                                text: "<"
                                                color: "#d8e5f2"
                                                font.pixelSize: 11
                                                font.bold: true
                                            }

                                            MouseArea {
                                                id: freeTextPrevMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                onClicked: itemRect.cycleFreeTextTab(-1)
                                            }
                                        }

                                        Label {
                                            id: freeTextTabLabel
                                            anchors.verticalCenter: parent.verticalCenter
                                            width: freeTextTabSwitcher.width - 48
                                            horizontalAlignment: Text.AlignHCenter
                                            elide: Text.ElideRight
                                            text: itemRect.freeTextActiveTabName
                                                + " (" + (itemRect.freeTextTabIndex + 1) + "/" + itemRect.freeTextTabCount + ")"
                                            color: "#eef6ff"
                                            font.pixelSize: 11
                                            font.bold: true
                                        }

                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 5
                                            anchors.verticalCenter: parent.verticalCenter
                                            color: freeTextNextMouse.containsMouse ? "#31485f" : "transparent"

                                            Label {
                                                anchors.centerIn: parent
                                                text: ">"
                                                color: "#d8e5f2"
                                                font.pixelSize: 11
                                                font.bold: true
                                            }

                                            MouseArea {
                                                id: freeTextNextMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                onClicked: itemRect.cycleFreeTextTab(1)
                                            }
                                        }
                                    }
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
                                    var text = model.text
                                    if (itemRect.itemType !== "note" && model.noteMarkdown && model.noteMarkdown !== model.text)
                                        text += (text.length > 0 ? "\n\n" : "") + model.noteMarkdown
                                    if (itemRect.hasLinkedSubtab) {
                                        text += "\n\nSubtab: " + Math.round(itemRect.linkedSubtabCompletion) + "%"
                                        if (itemRect.linkedSubtabActiveAction !== "")
                                            text += "\nActive: " + itemRect.linkedSubtabActiveAction
                                    }
                                    if (itemRect.taskContractActive) {
                                        text += "\n\nContract deadline: " + itemRect.taskContractDeadline
                                        if (itemRect.taskContractBreached)
                                            text += "\nStatus: OVERDUE"
                                        text += "\nPunishment: " + itemRect.taskContractPunishment
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
                                ToolTip.text: model.text + (model.noteMarkdown && model.noteMarkdown !== model.text ? "\n\n" + model.noteMarkdown : "")

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
                                ToolTip.text: model.text + (model.noteMarkdown && model.noteMarkdown !== model.text ? "\n\n" + model.noteMarkdown : "")

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
                                anchors.topMargin: itemRect.freeTextTabCount > 1 ? 40 : 24
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                anchors.bottomMargin: 8
                                readonly property bool useMarkdown: {
                                    var editingThisItem = markdownNoteManager
                                        && markdownNoteManager.editorOpen
                                        && markdownNoteManager.activeEditorType === "freetext"
                                        && markdownNoteManager.activeItemId === itemRect.itemId
                                    if (editingThisItem)
                                        return true
                                    if (!diagramModel)
                                        return itemRect.selected || itemRect.hovered
                                    return diagramModel.count <= 80 || itemRect.selected || itemRect.hovered
                                }
                                text: itemRect.freeTextDisplayText
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
                                ToolTip.text: itemRect.freeTextDisplayText

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
                                    if (itemRect.itemType === "chatgpt") {
                                        diagramModel.openChatGpt(itemRect.itemId)
                                    } else if (itemRect.itemType === "wish" || itemRect.itemType === "obstacle") {
                                        if (markdownNoteManager) {
                                            markdownNoteManager.openNote(itemRect.itemId)
                                        }
                                    } else if (itemRect.itemType === "note") {
                                        root.openPresetDialog("note", Qt.point(model.x, model.y), itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex < 0) {
                                        // Task not yet linked to task list - create new task
                                        dialogs.newTaskDialog.openWithItem(itemRect.itemId, model.text)
                                    } else if (itemRect.itemType === "task" && itemRect.taskIndex >= 0) {
                                        // Task linked to task list - drill into its tab
                                        if (projectManager)
                                            projectManager.drillToTab(itemRect.taskIndex)
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
                                // Keep connector outside the node to avoid collisions with in-node controls.
                                x: parent.width - (width / 2)
                                y: Math.round((parent.height - height) / 2)
                                color: edgeDrag.active ? "#4c627f" : "#2a3444"
                                border.color: edgeDrag.active ? "#74a0d9" : "#3b485c"
                                property point dragPoint: Qt.point(model.x, model.y)
                                property bool hoverActive: false
                                z: 26

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

                                TapHandler {
                                    acceptedButtons: Qt.LeftButton
                                    gesturePolicy: TapHandler.DragThreshold
                                    onDoubleTapped: {
                                        var newX = model.x + model.width + 40
                                        var newY = model.y
                                        dialogs.edgeDropTaskDialog.sourceId = itemRect.itemId
                                        dialogs.edgeDropTaskDialog.sourceType = itemRect.itemType
                                        dialogs.edgeDropTaskDialog.dropX = newX
                                        dialogs.edgeDropTaskDialog.dropY = newY
                                        dialogs.edgeDropTaskDialog.open()
                                    }
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
                                    onTapped: function(eventPoint) {
                                        if (diagramModel) {
                                            if (eventPoint.modifiers & Qt.ControlModifier) {
                                                root.addTaskOrConnectedTaskBackward(itemRect.itemId)
                                                return
                                            }
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
                        "Ctrl+N  Connected Note",
                        "Ctrl+K  Find Tab",
                        "Ctrl+-  Backward Chain",
                        "Delete  Remove Node",
                        "Arrows  Connected Task",
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

    Rectangle {
        visible: root.tabDragActive
        property point viewportTop: viewport.mapToItem(root.contentItem, viewport.width / 2, 0)
        x: viewportTop.x - width / 2
        y: viewportTop.y + 10
        radius: 9
        height: 30
        width: dropHintText.implicitWidth + 18
        color: root.tabDragInsideViewport ? "#1c4e64" : "#3e2d2d"
        border.color: root.tabDragInsideViewport ? "#76d7ff" : "#d28f8f"
        border.width: 1
        z: 980

        Text {
            id: dropHintText
            anchors.centerIn: parent
            color: "#eaf7ff"
            font.pixelSize: 12
            font.bold: true
            text: root.tabDragInsideViewport
                ? "Drop to create drill task"
                : "Drag into drawing area"
        }
    }

    Rectangle {
        visible: root.tabDragActive && root.tabDragInsideViewport
        width: 18
        height: 18
        radius: 9
        color: "#3ad39f"
        border.color: "#dff8ef"
        border.width: 2
        opacity: 0.9
        z: 980
        property point viewportPos: root.diagramPointToViewport(root.tabDragPreviewX, root.tabDragPreviewY)
        property point scenePos: viewport.mapToItem(root.contentItem, viewportPos.x, viewportPos.y)
        x: scenePos.x - width / 2
        y: scenePos.y - height / 2
    }

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

    Dialog {
        id: errorDialog
        modal: true
        title: "ActionDraw"
        anchors.centerIn: parent
        width: Math.min(root.width - 60, 700)
        standardButtons: Dialog.Ok
        property string messageText: ""

        background: Rectangle {
            radius: 10
            color: "#0f1b27"
            border.color: "#4f6780"
            border.width: 1
        }

        contentItem: Rectangle {
            implicitWidth: errorDialog.width - 32
            implicitHeight: 240
            color: "transparent"

            ScrollView {
                anchors.fill: parent
                clip: true

                Text {
                    width: Math.max(200, parent.width - 16)
                    text: errorDialog.messageText
                    wrapMode: Text.Wrap
                    color: "#f5f8fc"
                    font.pixelSize: 13
                }
            }
        }
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

    Popup {
        id: contractPopup
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        x: (root.width - width) / 2
        y: 120
        width: Math.min(root.width - 40, 500)

        background: Rectangle {
            radius: 10
            color: "#2b1a1f"
            border.color: "#d46a6a"
            border.width: 2
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Text {
                text: "Contract Breached"
                color: "#ffb1b1"
                font.pixelSize: 14
                font.bold: true
            }

            Text {
                Layout.fillWidth: true
                text: root.pendingContractTaskTitle && root.pendingContractTaskTitle.length > 0 ? root.pendingContractTaskTitle : "Task"
                color: "#f5f6f8"
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: "Deadline: " + root.pendingContractDeadline
                color: "#f2c8c8"
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: "Punishment: " + root.pendingContractPunishment
                color: "#ffd4a8"
                wrapMode: Text.WordWrap
                font.bold: true
            }

            RowLayout {
                spacing: 8

                Button {
                    text: "Open Task"
                    onClicked: {
                        var tabIndex = root.pendingContractTabIndex
                        var taskIndex = root.pendingContractTaskIndex
                        contractPopup.close()
                        if (projectManager && projectManager.openTabTask) {
                            projectManager.openTabTask(tabIndex, taskIndex)
                        } else {
                            root.drillToTask(taskIndex)
                        }
                    }
                }

                Button {
                    text: "Acknowledge"
                    onClicked: contractPopup.close()
                }
            }
        }

        onClosed: {
            root.contractPopupBusy = false
            root.showNextContractAlert()
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
            root.refreshOverviewData()
            Qt.callLater(root.applyDefaultView)
        }
        function onTabSwitched() {
            root.updateBoardBounds()
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
            Qt.callLater(root.applyDefaultView)
        }
        function onTaskDrillRequested(taskIndex) {
            root.showWindow()
            root.drillToTask(taskIndex)
        }
        function onErrorOccurred(message) {
            root.showWindow()
            root.hideYubiKeyPrompt()
            if (markdownNoteManager && markdownNoteManager.hideExternalPrompt)
                markdownNoteManager.hideExternalPrompt()
            root.showErrorDialog(message)
        }
        function onYubiKeyInteractionStarted(message) {
            root.showWindow()
            root.showYubiKeyPrompt(message)
            if (markdownNoteManager && markdownNoteManager.showExternalPrompt)
                markdownNoteManager.showExternalPrompt(message)
        }
        function onYubiKeyInteractionFinished() {
            root.hideYubiKeyPrompt()
            if (markdownNoteManager && markdownNoteManager.hideExternalPrompt)
                markdownNoteManager.hideExternalPrompt()
        }
    }

    Connections {
        target: projectManager
        enabled: projectManager !== null
        function onTaskReminderDue(tabIndex, taskIndex, taskTitle) {
            root.showWindow()
            root.refreshActiveReminders()
            root.showReminderAlert(tabIndex, taskIndex, taskTitle)
        }
        function onTaskContractBreached(tabIndex, taskIndex, taskTitle, punishment, deadlineText) {
            root.showWindow()
            root.refreshOverviewData()
            root.showContractAlert(tabIndex, taskIndex, taskTitle, punishment, deadlineText)
        }
    }

    Connections {
        target: tabModel
        enabled: tabModel !== null
        function onTabsChanged() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onCurrentTabChanged() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onCurrentTabIndexChanged() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onDataChanged() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onRowsInserted() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onRowsRemoved() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
        function onModelReset() {
            root.refreshLinkingTabsPanel()
            root.refreshOverviewData()
        }
    }

    Connections {
        target: markdownNoteManager
        enabled: markdownNoteManager !== null
        function onProjectSaveRequested() {
            root.performSave()
        }

        function onTaskCreated(taskId) {
            if (!taskId || !diagramModel)
                return
            root.selectedItemId = taskId
            var snapshot = diagramModel.getItemSnapshot(taskId)
            if (snapshot && snapshot.taskIndex !== undefined && snapshot.taskIndex >= 0) {
                root.drillToTask(snapshot.taskIndex)
            }
        }

        function onItemSaved(itemId) {
            if (!itemId)
                return
            root.selectedItemId = itemId
        }
    }

    Component.onCompleted: {
        updateBoardBounds()
        refreshLinkingTabsPanel()
        refreshOverviewData()
        Qt.callLater(applyDefaultView)
    }

    onClosing: function(close) {
        if (suppressClosePrompt) {
            suppressClosePrompt = false
            close.accepted = true
            return
        }
        if (!projectManager || !projectManager.hasUnsavedChanges()) {
            close.accepted = true
            return
        }
        close.accepted = false
        closeAfterSaveAsRequested = false
        unsavedChangesDialog.open()
    }

    Dialog {
        id: yubiKeyTouchDialog
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: Math.min(root.width * 0.52, 520)
        visible: root.yubiKeyPromptVisible

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                text: "YubiKey Verification Required"
                font.pixelSize: 17
                font.bold: true
                color: "#e8eef8"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Label {
                text: root.yubiKeyPromptText
                color: "#c7d6e8"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                spacing: 10
                Layout.fillWidth: true

                BusyIndicator {
                    running: root.yubiKeyPromptVisible
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                }

                Label {
                    text: "Waiting for touch..."
                    color: "#9bb0c8"
                    Layout.fillWidth: true
                }
            }
        }

        background: Rectangle {
            radius: 14
            color: "#132031"
            border.color: "#2a4462"
            border.width: 1
        }
    }

    Dialog {
        id: unsavedChangesDialog
        modal: true
        focus: true
        x: Math.round((root.width - width) / 2)
        y: Math.round((root.height - height) / 2)
        width: Math.min(root.width * 0.5, 520)
        title: "Unsaved Changes"

        contentItem: ColumnLayout {
            spacing: 12

            Label {
                text: "The diagram has unsaved changes. Save before closing?"
                color: "#d6e2f0"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
        }

        footer: RowLayout {
            spacing: 8

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "Save"
                onClicked: {
                    unsavedChangesDialog.close()
                    if (projectManager && projectManager.hasCurrentFile()) {
                        var saved = root.performSave()
                        if (saved)
                            root.forceCloseWithoutPrompt()
                    } else {
                        closeAfterSaveAsRequested = true
                        dialogs.saveDialog.open()
                    }
                }
            }

            Button {
                text: "Discard"
                onClicked: {
                    unsavedChangesDialog.close()
                    root.forceCloseWithoutPrompt()
                }
            }

            Button {
                text: "Cancel"
                onClicked: {
                    closeAfterSaveAsRequested = false
                    unsavedChangesDialog.close()
                }
            }
        }

        background: Rectangle {
            radius: 12
            color: "#132031"
            border.color: "#2a4462"
            border.width: 1
        }
    }
}
