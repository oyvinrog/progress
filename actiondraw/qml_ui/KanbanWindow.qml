import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: root
    width: 1180
    height: 720
    visible: true
    title: "Kanban Board"
    color: "#0a1118"

    property var tabModel: null
    property var tabModelRef: tabModel
    property var projectManager: null
    property var projectManagerRef: projectManager
    property var slotHours: [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
    property var boardItems: []
    property string feedback: ""
    property string resizeItemId: ""
    property int resizeStartHour: 8
    property int resizeHours: 1
    property real resizeSceneX: 0
    property real resizeSceneY: 0
    property int timelineHourHeight: 154
    property int timelineGutterWidth: 156
    property var timelineCards: buildTimelineCards()

    function durationOf(item) { return Number(item.kanbanDurationHours || 1) }
    function displayDuration(item) {
        return item.itemId === resizeItemId ? resizeHours : durationOf(item)
    }
    function buildTimelineCards() {
        var items = boardItems.filter(function(item) { return item.kanbanStatus === "in_progress" })
        items.sort(function(a, b) {
            return a.kanbanSlotHour - b.kanbanSlotHour || String(a.itemId).localeCompare(String(b.itemId))
        })
        var ends = [], result = []
        for (var i = 0; i < items.length; ++i) {
            var card = items[i], column = 0
            while (column < ends.length && ends[column] > card.kanbanSlotHour) ++column
            ends[column] = card.kanbanSlotHour + durationOf(card)
            result.push({card: card, column: column})
        }
        return result
    }
    function timelineColumnCount() {
        var count = 1
        for (var i = 0; i < timelineCards.length; ++i)
            count = Math.max(count, timelineCards[i].column + 1)
        return count
    }
    function setDuration(itemId, hours) {
        var ok = false
        if (projectManagerRef && projectManagerRef.setKanbanItemDuration)
            ok = projectManagerRef.setKanbanItemDuration(itemId, hours)
        else if (tabModelRef) {
            for (var i = 0; i < boardItems.length; ++i)
                if (boardItems[i].itemId === itemId)
                    ok = tabModelRef.setKanbanDuration(boardItems[i].tabIndex, hours)
        }
        feedback = ok ? "" : "The task must fit between 08:00 and 18:00."
    }
    function updateResize(sceneX, sceneY) {
        resizeSceneX = sceneX
        resizeSceneY = sceneY
        var point = timelineSurface.mapFromItem(null, sceneX, sceneY)
        var endHour = 8 + Math.round(point.y / timelineHourHeight)
        resizeHours = Math.max(1, Math.min(18 - resizeStartHour, endHour - resizeStartHour))
    }
    function finishResize(commit) {
        var itemId = resizeItemId, hours = resizeHours
        resizeItemId = ""
        if (commit && itemId.length) setDuration(itemId, hours)
    }
    Shortcut {
        sequence: "Escape"
        enabled: root.resizeItemId.length > 0
        onActivated: root.finishResize(false)
    }
    Timer {
        interval: 30
        repeat: true
        running: root.resizeItemId.length > 0
        onTriggered: {
            var point = timelineView.mapFromItem(null, root.resizeSceneX, root.resizeSceneY)
            var delta = point.y < 36 ? -12 : (point.y > timelineView.height - 36 ? 12 : 0)
            if (delta) {
                timelineView.contentY = Math.max(0, Math.min(timelineView.contentHeight - timelineView.height,
                                                            timelineView.contentY + delta))
                root.updateResize(root.resizeSceneX, root.resizeSceneY)
            }
        }
    }
    property string createStatus: "todo"
    property int createSlotHour: -1
    property string todoSearchText: ""
    property var dropZones: []
    property bool dragActive: false
    property string dragItemId: ""
    property string dragTabName: ""
    property string dragTabIcon: ""
    property real dragSceneX: 0
    property real dragSceneY: 0
    property int kanbanSlotMinHeight: 154
    property int kanbanCardMinHeight: 70
    property int kanbanCardWithActiveMinHeight: 94
    property int kanbanLayoutRevision: 0

    function refreshBoardItems() {
        if (projectManagerRef && projectManagerRef.getKanbanItems) {
            boardItems = projectManagerRef.getKanbanItems()
        } else {
            var fallback = []
            var count = tabModelRef && tabModelRef.rowCount ? tabModelRef.rowCount() : 0
            for (var i = 0; i < count; ++i) {
                var summary = tabModelRef.getTabSummary(i)
                if (summary.kanbanStatus === "unscheduled")
                    continue
                fallback.push({ itemId: "tab:" + summary.id, sourceType: "tab",
                                sourceId: summary.id, tabIndex: i, name: summary.name,
                                sourceLabel: "Tab", icon: summary.icon || "▣",
                                color: summary.color || "#4aa3ff",
                                completionPercent: summary.completionPercent || 0,
                                activeTaskTitle: summary.activeTaskTitle || "",
                                kanbanStatus: summary.kanbanStatus,
                                kanbanSlotHour: summary.kanbanSlotHour,
                                kanbanDurationHours: summary.kanbanDurationHours || 1 })
            }
            boardItems = fallback
        }
        kanbanLayoutRevision += 1
    }

    function modelCount() { return boardItems.length }

    function slotLabel(hour) {
        var start = Number(hour)
        var end = start + 1
        var startText = start < 10 ? "0" + start : String(start)
        var endText = end < 10 ? "0" + end : String(end)
        return startText + ":00-" + endText + ":00"
    }

    function placementMatches(cardStatus, cardSlotHour, targetStatus, targetSlotHour) {
        var status = String(cardStatus || "todo")
        var slot = Number(cardSlotHour === undefined ? -1 : cardSlotHour)
        if (targetStatus !== "in_progress")
            return status === targetStatus
        return status === "in_progress" && slot === Number(targetSlotHour)
    }

    function todoSearchMatches(cardName, sourceLabel) {
        var query = todoSearchText.trim().toLowerCase()
        if (query.length === 0)
            return true
        return (String(cardName || "") + " " + String(sourceLabel || ""))
            .toLowerCase().indexOf(query) >= 0
    }

    function cardMatchesSection(cardStatus, cardSlotHour, cardName, sourceLabel,
                                targetStatus, targetSlotHour) {
        if (!placementMatches(cardStatus, cardSlotHour, targetStatus, targetSlotHour))
            return false
        return targetStatus !== "todo" || todoSearchMatches(cardName, sourceLabel)
    }

    function sectionCardCount(targetStatus, targetSlotHour) {
        var count = 0
        for (var i = 0; i < boardItems.length; ++i) {
            var item = boardItems[i]
            if (targetStatus === "in_progress") {
                if (item.kanbanStatus === targetStatus && item.kanbanSlotHour <= targetSlotHour
                        && targetSlotHour < item.kanbanSlotHour + durationOf(item)) count += 1
                continue
            }
            if (cardMatchesSection(item.kanbanStatus, item.kanbanSlotHour,
                                   item.name, item.sourceLabel,
                                   targetStatus, targetSlotHour))
                count += 1
        }
        return count
    }

    function inProgressCardCount() {
        var revision = kanbanLayoutRevision
        var count = 0
        for (var i = 0; i < boardItems.length; ++i) {
            if (boardItems[i].kanbanStatus === "in_progress")
                count += 1
        }
        return count
    }

    function todoSearchHasMatches() {
        if (todoSearchText.trim().length === 0)
            return true
        for (var i = 0; i < boardItems.length; ++i) {
            var item = boardItems[i]
            if (placementMatches(item.kanbanStatus, item.kanbanSlotHour, "todo", -1)
                    && todoSearchMatches(item.name, item.sourceLabel))
                return true
        }
        return false
    }

    function setPlacement(itemId, status, slotHour) {
        feedback = ""
        for (var n = 0; n < boardItems.length; ++n) {
            if (boardItems[n].itemId === itemId && status === "in_progress"
                    && slotHour + durationOf(boardItems[n]) > 18) {
                feedback = "This task would end after 18:00. Choose an earlier start."
                return
            }
        }
        if (projectManagerRef && projectManagerRef.setKanbanItemPlacement) {
            projectManagerRef.setKanbanItemPlacement(String(itemId), status, Number(slotHour))
            return
        }
        for (var i = 0; i < boardItems.length; ++i) {
            if (boardItems[i].itemId === itemId && tabModelRef) {
                tabModelRef.setKanbanPlacement(boardItems[i].tabIndex, status, Number(slotHour))
                return
            }
        }
    }

    function postponeInProgressFromSlot(startHour) {
        var skipped = boardItems.filter(function(item) {
            return item.kanbanStatus === "in_progress" && item.kanbanSlotHour >= startHour
                && item.kanbanSlotHour + durationOf(item) >= 18
        }).length
        feedback = skipped ? skipped + " task(s) could not be postponed beyond 18:00." : ""
        if (projectManagerRef && projectManagerRef.postponeKanbanItems)
            projectManagerRef.postponeKanbanItems(Number(startHour))
        else if (tabModelRef)
            tabModelRef.postponeInProgressFromSlot(Number(startHour))
    }

    function clearKanbanLane(status, slotHour) {
        if (projectManagerRef && projectManagerRef.clearKanbanItems)
            projectManagerRef.clearKanbanItems(status, Number(slotHour))
        else if (tabModelRef)
            tabModelRef.clearKanbanLane(status, Number(slotHour))
    }

    function moveKanbanLaneBack(status, slotHour) {
        var blocked = status === "done" && boardItems.some(function(item) {
            return item.kanbanStatus === "done" && durationOf(item) > 1
        })
        feedback = blocked ? "Extended tasks cannot return at 17:00. Drag them to an earlier hour." : ""
        if (projectManagerRef && projectManagerRef.moveKanbanItemsBack)
            projectManagerRef.moveKanbanItemsBack(status, Number(slotHour))
        else if (tabModelRef)
            tabModelRef.moveKanbanLaneBack(status, Number(slotHour))
    }

    function registerDropZone(zone) {
        if (!zone || dropZones.indexOf(zone) >= 0)
            return
        var nextZones = dropZones.slice(0)
        nextZones.push(zone)
        dropZones = nextZones
    }

    function unregisterDropZone(zone) {
        var nextZones = []
        for (var i = 0; i < dropZones.length; ++i) {
            if (dropZones[i] !== zone)
                nextZones.push(dropZones[i])
        }
        dropZones = nextZones
    }

    function dropItemAt(itemId, sceneX, sceneY) {
        var viewportPoint = timelineView.mapFromItem(null, sceneX, sceneY)
        if (viewportPoint.x >= 0 && viewportPoint.x < timelineView.width
                && viewportPoint.y >= 0 && viewportPoint.y < timelineView.height) {
            var timelinePoint = timelineSurface.mapFromItem(null, sceneX, sceneY)
            var hour = 8 + Math.floor(timelinePoint.y / timelineHourHeight)
            if (hour >= 8 && hour < 18) {
                setPlacement(itemId, "in_progress", hour)
                return true
            }
        }
        for (var i = dropZones.length - 1; i >= 0; --i) {
            var zone = dropZones[i]
            if (!zone || !zone.visible)
                continue
            var local = zone.mapFromItem(null, sceneX, sceneY)
            if (local.x < 0 || local.y < 0 || local.x > zone.width || local.y > zone.height)
                continue
            setPlacement(itemId, zone.targetStatus, zone.targetSlotHour)
            return true
        }
        return false
    }

    function cardScenePoint(card, localX, localY) {
        return card ? card.mapToItem(null, localX, localY) : Qt.point(0, 0)
    }

    function beginCardDrag(card, itemId, tabName, tabIcon, localX, localY) {
        var scene = cardScenePoint(card, localX, localY)
        dragActive = true
        dragItemId = String(itemId)
        dragTabName = String(tabName || "")
        dragTabIcon = String(tabIcon || "")
        dragSceneX = scene.x
        dragSceneY = scene.y
    }

    function updateCardDrag(card, localX, localY) {
        if (!dragActive)
            return
        var scene = cardScenePoint(card, localX, localY)
        dragSceneX = scene.x
        dragSceneY = scene.y
    }

    function endCardDrag() {
        if (dragActive && dragItemId.length > 0)
            dropItemAt(dragItemId, dragSceneX, dragSceneY)
        dragActive = false
        dragItemId = ""
        dragTabName = ""
        dragTabIcon = ""
    }

    function openItem(itemId) {
        if (projectManagerRef && projectManagerRef.openKanbanItem)
            projectManagerRef.openKanbanItem(String(itemId))
        else if (tabModelRef) {
            for (var i = 0; i < boardItems.length; ++i)
                if (boardItems[i].itemId === itemId) tabModelRef.setCurrentTab(boardItems[i].tabIndex)
        }
        root.close()
    }

    function removeItem(itemId) {
        if (projectManagerRef && projectManagerRef.removeKanbanItem) {
            projectManagerRef.removeKanbanItem(String(itemId))
            return
        }
        for (var i = 0; i < boardItems.length; ++i)
            if (boardItems[i].itemId === itemId && tabModelRef)
                tabModelRef.setKanbanPlacement(boardItems[i].tabIndex, "unscheduled", -1)
    }

    function openCreateDialog(status, slotHour) {
        createStatus = status
        createSlotHour = slotHour
        createNameField.text = ""
        createTabDialog.open()
        createNameField.forceActiveFocus()
    }

    function confirmCreateTab() {
        if (!tabModelRef || !tabModelRef.createTabAtKanbanPlacement)
            return
        var name = createNameField.text.trim()
        var createdIndex = tabModelRef.createTabAtKanbanPlacement(name, createStatus, createSlotHour)
        if (createdIndex >= 0 && projectManagerRef && projectManagerRef.switchTab)
            projectManagerRef.switchTab(createdIndex)
    }


    Rectangle {
        anchors.fill: parent
        z: -2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0d1822" }
            GradientStop { position: 1.0; color: "#101923" }
        }
    }

    Component.onCompleted: refreshBoardItems()

    Connections {
        target: root.projectManagerRef
        ignoreUnknownSignals: true
        function onKanbanChanged() { root.refreshBoardItems() }
    }

    Connections {
        target: root.tabModelRef
        ignoreUnknownSignals: true
        function onRowsInserted() { root.refreshBoardItems() }
        function onRowsRemoved() { root.refreshBoardItems() }
        function onModelReset() { root.refreshBoardItems() }
        function onDataChanged() { root.refreshBoardItems() }
    }

    Component {
        id: kanbanCardComponent

        Rectangle {
            id: itemCard
            property string itemId: ""
            property string sourceType: ""
            property int tabIndex: -1
            property string itemName: ""
            property string itemIcon: ""
            property string itemColor: ""
            property string sourceLabel: ""
            property real completionPercent: 0
            property string activeTaskTitle: ""
            property int startHour: -1
            property int durationHours: 1
            property bool timelineCard: startHour >= 8
            property int shownHours: root.resizeItemId === itemId ? root.resizeHours : durationHours
            property bool dragging: cardMouse.dragging
            property real pressX: 0
            property real pressY: 0
            objectName: sourceType === "tab" ? "kanbanCard_" + tabIndex
                                                : "kanbanCard_" + itemId

            width: parent ? parent.width : 240
            implicitHeight: Math.max(
                activeTaskTitle.length > 0 ? root.kanbanCardWithActiveMinHeight : root.kanbanCardMinHeight,
                cardContent.implicitHeight + 16
            )
            height: timelineCard ? shownHours * root.timelineHourHeight - 8 : implicitHeight
            radius: 8
            color: cardMouse.containsMouse ? "#203445" : "#172737"
            border.color: cardMouse.containsMouse ? "#72b8d8" : "#314b5f"
            border.width: 1
            scale: dragging ? 1.02 : 1.0
            opacity: dragging ? 0.88 : 1.0

            Drag.active: cardDragHandler.active
            Drag.source: itemCard
            Drag.keys: ["kanban-item"]
            Drag.supportedActions: Qt.MoveAction
            Drag.hotSpot.x: width / 2
            Drag.hotSpot.y: height / 2

            Behavior on scale { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: 90; easing.type: Easing.OutCubic } }

            Rectangle {
                width: 4
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                radius: 2
                color: itemColor.length > 0 ? itemColor : "#4aa3ff"
            }

            Item {
                id: cardDragHandler
                property bool active: cardMouse.dragging
            }

            MouseArea {
                id: cardMouse
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: dragging ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                preventStealing: true
                property bool dragging: false

                onPressed: function(mouse) {
                    itemCard.pressX = mouse.x
                    itemCard.pressY = mouse.y
                    dragging = false
                }
                onPositionChanged: function(mouse) {
                    if (!(mouse.buttons & Qt.LeftButton))
                        return
                    var dx = mouse.x - itemCard.pressX
                    var dy = mouse.y - itemCard.pressY
                    if (!dragging && Math.sqrt(dx * dx + dy * dy) >= 6) {
                        dragging = true
                        root.beginCardDrag(itemCard, itemCard.itemId, itemCard.itemName,
                                           itemCard.itemIcon, mouse.x, mouse.y)
                    }
                    if (dragging)
                        root.updateCardDrag(itemCard, mouse.x, mouse.y)
                }
                onReleased: function(mouse) {
                    if (dragging) {
                        root.updateCardDrag(itemCard, mouse.x, mouse.y)
                        root.endCardDrag()
                        dragging = false
                        return
                    }
                    if (mouse.x >= itemCard.width - 42)
                        root.removeItem(itemCard.itemId)
                    else
                        root.openItem(itemCard.itemId)
                }
                onCanceled: {
                    if (dragging)
                        root.endCardDrag()
                    dragging = false
                }
            }

            RowLayout {
                id: cardContent
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 8
                anchors.topMargin: 8
                anchors.bottomMargin: itemCard.timelineCard ? 18 : 8
                spacing: 8

                Text {
                    text: itemIcon.length > 0 ? itemIcon : "."
                    color: "#dcebf6"
                    font.pixelSize: 13
                    font.bold: true
                    Layout.alignment: Qt.AlignTop
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    spacing: 3
                    Text {
                        text: itemName
                        color: "#f0f7ff"
                        font.pixelSize: 13
                        font.bold: true
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: itemCard.timelineCard
                        text: (itemCard.startHour < 10 ? "0" : "") + itemCard.startHour + ":00–"
                              + (itemCard.startHour + itemCard.shownHours < 10 ? "0" : "")
                              + (itemCard.startHour + itemCard.shownHours) + ":00"
                        color: "#b4dded"
                        font.pixelSize: 12
                        Layout.fillWidth: true
                    }
                    Text {
                        text: sourceLabel
                        color: "#8eabba"
                        font.pixelSize: 10
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: activeTaskTitle.length > 0
                        text: "Active: " + activeTaskTitle
                        color: "#9fd0b3"
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: Math.round(completionPercent) + "% complete"
                        color: "#94bdd4"
                        font.pixelSize: 10
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 26
                    Layout.alignment: Qt.AlignTop
                    radius: 6
                    color: "#26394b"
                    border.color: "#3c5569"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "x"
                        color: "#dceaf4"
                        font.pixelSize: 11
                        font.bold: true
                    }
                }
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 5
                width: 32
                height: 3
                radius: 2
                color: "#8eabba"
                visible: itemCard.timelineCard
            }
            MouseArea {
                objectName: "kanbanResize_" + itemCard.itemId
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 16
                visible: itemCard.timelineCard
                cursorShape: Qt.SizeVerCursor
                hoverEnabled: true
                ToolTip.visible: containsMouse && !pressed
                ToolTip.text: "Drag to change the end time"
                preventStealing: true
                onPressed: function(mouse) {
                    root.resizeItemId = itemCard.itemId
                    root.resizeStartHour = itemCard.startHour
                    root.resizeHours = itemCard.durationHours
                    var point = mapToItem(null, mouse.x, mouse.y)
                    root.resizeSceneX = point.x
                    root.resizeSceneY = point.y
                }
                onPositionChanged: function(mouse) {
                    if (!pressed || root.resizeItemId !== itemCard.itemId) return
                    var point = mapToItem(null, mouse.x, mouse.y)
                    root.updateResize(point.x, point.y)
                }
                onReleased: root.finishResize(true)
                onCanceled: root.finishResize(false)
            }
        }
    }
    Component {
        id: boardSectionComponent

        Rectangle {
            id: sectionRoot
            property string sectionTitle: ""
            property string targetStatus: "todo"
            property int targetSlotHour: -1
            property bool showTodoSearch: targetStatus === "todo"
            property int visibleCardCount: root.kanbanLayoutRevision >= 0
                ? root.sectionCardCount(targetStatus, targetSlotHour)
                : 0
            property bool canPostpone: targetStatus === "in_progress"
                && targetSlotHour < 17
            property bool canMoveBack: targetStatus !== "todo" && visibleCardCount > 0
            property bool canClear: targetStatus !== "todo" && visibleCardCount > 0
            objectName: "kanbanDrop_" + targetStatus + "_" + targetSlotHour

            width: parent ? parent.width : 220
            height: parent ? parent.height : root.kanbanSlotMinHeight
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: dropArea.containsDrag ? "#1c3445" : "#10202d"
            border.color: dropArea.containsDrag ? "#7dd3fc" : "#2c4a5f"
            border.width: 1

            Component.onCompleted: root.registerDropZone(sectionRoot)
            Component.onDestruction: root.unregisterDropZone(sectionRoot)

            DropArea {
                id: dropArea
                anchors.fill: parent
                keys: ["kanban-item"]
                z: 20
                onDropped: function(drop) {
                    if (drop.source && drop.source.itemId !== undefined) {
                        root.setPlacement(drop.source.itemId, sectionRoot.targetStatus, sectionRoot.targetSlotHour)
                        drop.acceptProposedAction()
                    }
                }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: sectionRoot.sectionTitle
                        color: "#e8f4ff"
                        font.pixelSize: 14
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Button {
                        text: "+1h"
                        visible: sectionRoot.targetStatus === "in_progress"
                        enabled: sectionRoot.canPostpone
                        Layout.preferredWidth: 44
                        Layout.preferredHeight: 28
                        objectName: "kanbanPostponeButton_" + sectionRoot.targetSlotHour
                        ToolTip.visible: hovered
                        ToolTip.text: "Postpone this slot and later slots"
                        onClicked: root.postponeInProgressFromSlot(sectionRoot.targetSlotHour)
                    }

                    Button {
                        text: "Back"
                        visible: sectionRoot.targetStatus !== "todo"
                        enabled: sectionRoot.canMoveBack
                        Layout.preferredWidth: 48
                        Layout.preferredHeight: 28
                        objectName: "kanbanMoveBackButton_" + sectionRoot.targetStatus + "_" + sectionRoot.targetSlotHour
                        ToolTip.visible: hovered
                        ToolTip.text: "Move all cards in this lane back one step"
                        onClicked: root.moveKanbanLaneBack(sectionRoot.targetStatus, sectionRoot.targetSlotHour)
                    }

                    Button {
                        text: "Clear"
                        visible: sectionRoot.targetStatus !== "todo"
                        enabled: sectionRoot.canClear
                        Layout.preferredWidth: 48
                        Layout.preferredHeight: 28
                        objectName: "kanbanClearButton_" + sectionRoot.targetStatus + "_" + sectionRoot.targetSlotHour
                        ToolTip.visible: hovered
                        ToolTip.text: "Move all cards in this lane to Todo"
                        onClicked: root.clearKanbanLane(sectionRoot.targetStatus, sectionRoot.targetSlotHour)
                    }

                    Button {
                        text: "+"
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 28
                        ToolTip.visible: hovered
                        ToolTip.text: "Create card in this lane"
                        onClicked: root.openCreateDialog(sectionRoot.targetStatus, sectionRoot.targetSlotHour)
                    }
                }

                TextField {
                    visible: sectionRoot.showTodoSearch
                    Layout.fillWidth: true
                    Layout.preferredHeight: sectionRoot.showTodoSearch ? 34 : 0
                    objectName: "kanbanTodoSearchField"
                    placeholderText: "Search Todo"
                    text: root.todoSearchText
                    selectByMouse: true
                    onTextChanged: root.todoSearchText = text
                }

                Flickable {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: cardsColumn.height
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                    Column {
                        id: cardsColumn
                        width: parent.width
                        spacing: 8

                        Repeater {
                            model: root.boardItems

                            delegate: Loader {
                                required property var modelData
                                property bool placedHere: root.cardMatchesSection(
                                    modelData.kanbanStatus,
                                    modelData.kanbanSlotHour,
                                    modelData.name,
                                    modelData.sourceLabel,
                                    sectionRoot.targetStatus,
                                    sectionRoot.targetSlotHour
                                )
                                width: cardsColumn.width
                                height: placedHere && item ? item.implicitHeight : 0
                                visible: placedHere
                                active: placedHere
                                sourceComponent: kanbanCardComponent
                                onHeightChanged: Qt.callLater(cardsColumn.forceLayout)
                                onVisibleChanged: Qt.callLater(cardsColumn.forceLayout)
                                onActiveChanged: Qt.callLater(cardsColumn.forceLayout)
                                onLoaded: {
                                    item.itemId = modelData.itemId || ""
                                    item.itemName = modelData.name || ""
                                    item.itemIcon = modelData.icon || ""
                                    item.sourceType = modelData.sourceType || ""
                                    item.tabIndex = modelData.tabIndex === undefined ? -1 : modelData.tabIndex
                                    item.itemColor = modelData.color || ""
                                    item.sourceLabel = modelData.sourceLabel || ""
                                    item.completionPercent = modelData.completionPercent || 0
                                    item.activeTaskTitle = modelData.activeTaskTitle || ""
                                }
                            }
                        }

                        Text {
                            visible: sectionRoot.targetStatus === "todo"
                                && root.todoSearchText.trim().length > 0
                                && !root.todoSearchHasMatches()
                            width: cardsColumn.width
                            text: "No Todo matches"
                            color: "#8eabba"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            padding: 14
                        }
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Kanban Board"
                color: "#edf7ff"
                font.pixelSize: 20
                font.bold: true
                Layout.fillWidth: true
            }

            Text {
                text: root.modelCount() + (root.modelCount() === 1 ? " item" : " items")
                color: "#95bfd7"
                font.pixelSize: 12
            }
        }

        Text {
            text: root.feedback
            visible: text.length > 0
            color: "#ffd28a"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Loader {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                sourceComponent: boardSectionComponent
                onLoaded: {
                    item.sectionTitle = "Todo"
                    item.targetStatus = "todo"
                    item.targetSlotHour = -1
                }
            }

            Loader {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                sourceComponent: boardSectionComponent
                onLoaded: {
                    item.sectionTitle = "Ready"
                    item.targetStatus = "ready"
                    item.targetSlotHour = -1
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 10
                color: "#0f1d29"
                border.color: "#2a465a"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "In Progress"
                            color: "#e8f4ff"
                            font.pixelSize: 14
                            font.bold: true
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Button {
                            text: "Back"
                            enabled: root.inProgressCardCount() > 0
                            Layout.preferredWidth: 48
                            Layout.preferredHeight: 28
                            objectName: "kanbanInProgressMoveBackButton"
                            ToolTip.visible: hovered
                            ToolTip.text: "Move all in-progress cards to Ready"
                            onClicked: root.moveKanbanLaneBack("in_progress", -1)
                        }

                        Button {
                            text: "Clear All"
                            enabled: root.inProgressCardCount() > 0
                            Layout.preferredWidth: 72
                            Layout.preferredHeight: 28
                            objectName: "kanbanInProgressClearAllButton"
                            ToolTip.visible: hovered
                            ToolTip.text: "Move all in-progress cards to Todo"
                            onClicked: root.clearKanbanLane("in_progress", -1)
                        }
                    }

                    Flickable {
                        id: timelineView
                        objectName: "kanbanTimeline"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        contentWidth: Math.max(width, root.timelineGutterWidth + root.timelineColumnCount() * 248)
                        contentHeight: 10 * root.timelineHourHeight
                        interactive: root.resizeItemId.length === 0 && !root.dragActive
                        ScrollBar.vertical: ScrollBar {}
                        ScrollBar.horizontal: ScrollBar {
                            policy: timelineView.contentWidth > timelineView.width ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                        }
                        Item {
                            id: timelineSurface
                            width: timelineView.contentWidth
                            height: timelineView.contentHeight
                            Repeater {
                                model: root.slotHours
                                delegate: Rectangle {
                                    required property int modelData
                                    objectName: "kanbanDrop_in_progress_" + modelData
                                    y: (modelData - 8) * root.timelineHourHeight
                                    width: timelineSurface.width
                                    height: root.timelineHourHeight
                                    color: modelData % 2 ? "#10202d" : "#132432"
                                    border.color: "#2c4a5f"
                                    Column {
                                        x: 6
                                        y: 10
                                        spacing: 6
                                        Text {
                                            text: root.slotLabel(modelData)
                                            color: "#e8f4ff"
                                            font.bold: true
                                        }
                                        Text {
                                            property int taskCount: root.sectionCardCount("in_progress", modelData)
                                            text: taskCount + (taskCount === 1 ? " task" : " tasks")
                                            color: "#8eabba"
                                        }
                                        Row {
                                            spacing: 2
                                            Button {
                                                text: "+1h"
                                                width: 48
                                                objectName: "kanbanPostponeButton_" + modelData
                                                enabled: modelData < 17
                                                onClicked: root.postponeInProgressFromSlot(modelData)
                                            }
                                            Button {
                                                text: "+"
                                                width: 32
                                                onClicked: root.openCreateDialog("in_progress", modelData)
                                            }
                                        }
                                        Row {
                                            spacing: 2
                                            Button {
                                                text: "Back"
                                                width: 58
                                                objectName: "kanbanMoveBackButton_in_progress_" + modelData
                                                enabled: root.sectionCardCount("in_progress", modelData) > 0
                                                onClicked: root.moveKanbanLaneBack("in_progress", modelData)
                                            }
                                            Button {
                                                text: "Clear"
                                                width: 58
                                                objectName: "kanbanClearButton_in_progress_" + modelData
                                                enabled: root.sectionCardCount("in_progress", modelData) > 0
                                                onClicked: root.clearKanbanLane("in_progress", modelData)
                                            }
                                        }
                                    }
                                }
                            }
                            Repeater {
                                model: root.timelineCards
                                delegate: Loader {
                                    required property var modelData
                                    x: root.timelineGutterWidth + modelData.column * width
                                    y: (modelData.card.kanbanSlotHour - 8) * root.timelineHourHeight + 4
                                    width: (timelineSurface.width - root.timelineGutterWidth) / root.timelineColumnCount()
                                    height: root.displayDuration(modelData.card) * root.timelineHourHeight - 8
                                    z: root.resizeItemId === modelData.card.itemId ? 3 : 1
                                    sourceComponent: kanbanCardComponent
                                    onLoaded: {
                                        var card = modelData.card
                                        item.width = Qt.binding(function() { return width - 8 })
                                        item.itemId = card.itemId
                                        item.itemName = card.name || ""
                                        item.itemIcon = card.icon || ""
                                        item.sourceType = card.sourceType || ""
                                        item.tabIndex = card.tabIndex === undefined ? -1 : card.tabIndex
                                        item.itemColor = card.color || ""
                                        item.sourceLabel = card.sourceLabel || ""
                                        item.completionPercent = card.completionPercent || 0
                                        item.activeTaskTitle = card.activeTaskTitle || ""
                                        item.startHour = card.kanbanSlotHour
                                        item.durationHours = root.durationOf(card)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Loader {
                Layout.preferredWidth: 220
                Layout.fillHeight: true
                sourceComponent: boardSectionComponent
                onLoaded: {
                    item.sectionTitle = "Done"
                    item.targetStatus = "done"
                    item.targetSlotHour = -1
                }
            }
        }
    }

    Rectangle {
        visible: root.dragActive
        x: root.dragSceneX - width / 2
        y: root.dragSceneY - height / 2
        width: 220
        height: 54
        radius: 8
        color: "#24465f"
        border.color: "#8bd8ff"
        border.width: 1
        opacity: 0.92
        z: 1000

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            spacing: 8

            Text {
                text: root.dragTabIcon && root.dragTabIcon.length > 0 ? root.dragTabIcon : "."
                color: "#f2fbff"
                font.pixelSize: 13
                font.bold: true
            }

            Text {
                text: root.dragTabName
                color: "#f2fbff"
                font.pixelSize: 13
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    Dialog {
        id: createTabDialog
        title: "New Tab"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: root.confirmCreateTab()

        ColumnLayout {
            width: 320
            spacing: 8

            Label {
                text: root.createStatus === "in_progress"
                    ? "Create in " + root.slotLabel(root.createSlotHour)
                    : "Create in " + (root.createStatus === "done" ? "Done" : (root.createStatus === "ready" ? "Ready" : "Todo"))
            }

            TextField {
                id: createNameField
                Layout.fillWidth: true
                placeholderText: "Tab name"
                selectByMouse: true
                onAccepted: createTabDialog.accept()
            }
        }
    }

}
