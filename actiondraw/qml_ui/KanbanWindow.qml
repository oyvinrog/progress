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
    property int kanbanCardEstimatedHeight: 112
    property int kanbanSectionChromeHeight: 58
    property int kanbanCardSpacing: 8
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
                                kanbanSlotHour: summary.kanbanSlotHour })
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
            if (cardMatchesSection(item.kanbanStatus, item.kanbanSlotHour,
                                   item.name, item.sourceLabel,
                                   targetStatus, targetSlotHour))
                count += 1
        }
        return count
    }

    function inProgressSlotHeight(slotHour) {
        var revision = kanbanLayoutRevision
        var count = sectionCardCount("in_progress", slotHour)
        if (count <= 1)
            return kanbanSlotMinHeight
        return Math.max(kanbanSlotMinHeight,
                        kanbanSectionChromeHeight + count * kanbanCardEstimatedHeight
                        + Math.max(0, count - 1) * kanbanCardSpacing)
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
            height: implicitHeight
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
                anchors.bottomMargin: 8
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
                    Layout.fillHeight: true
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

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: root.slotHours

                                delegate: Loader {
                                    property int slotHour: Number(modelData)
                                    property real desiredHeight: root.kanbanLayoutRevision >= 0
                                        ? root.inProgressSlotHeight(slotHour)
                                        : root.kanbanSlotMinHeight
                                    Layout.fillWidth: true
                                    Layout.minimumHeight: desiredHeight
                                    Layout.preferredHeight: desiredHeight
                                    height: desiredHeight
                                    sourceComponent: boardSectionComponent
                                    onLoaded: {
                                        item.width = Qt.binding(function() { return width })
                                        item.height = Qt.binding(function() { return desiredHeight })
                                        item.sectionTitle = root.slotLabel(slotHour)
                                        item.targetStatus = "in_progress"
                                        item.targetSlotHour = slotHour
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
