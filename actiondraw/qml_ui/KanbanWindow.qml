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
    property string createStatus: "todo"
    property int createSlotHour: -1
    property string todoSearchText: ""
    property int pendingDeleteTabIndex: -1
    property string pendingDeleteTabName: ""
    property var dropZones: []
    property bool dragActive: false
    property int dragTabIndex: -1
    property string dragTabName: ""
    property string dragTabIcon: ""
    property real dragSceneX: 0
    property real dragSceneY: 0

    function modelCount() {
        if (!tabModelRef)
            return 0
        if (tabModelRef.rowCount)
            return tabModelRef.rowCount()
        if (tabModelRef.count !== undefined)
            return Number(tabModelRef.count)
        return 0
    }

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

    function todoSearchMatches(cardName) {
        var query = todoSearchText.trim().toLowerCase()
        if (query.length === 0)
            return true
        return String(cardName || "").toLowerCase().indexOf(query) >= 0
    }

    function cardMatchesSection(cardStatus, cardSlotHour, cardName, targetStatus, targetSlotHour) {
        if (!placementMatches(cardStatus, cardSlotHour, targetStatus, targetSlotHour))
            return false
        if (targetStatus !== "todo")
            return true
        return todoSearchMatches(cardName)
    }

    function todoSearchHasMatches() {
        var query = todoSearchText.trim()
        if (query.length === 0 || !tabModelRef || !tabModelRef.getTabSummary)
            return true
        for (var i = 0; i < modelCount(); ++i) {
            var summary = tabModelRef.getTabSummary(i)
            if (summary
                    && placementMatches(summary.kanbanStatus, summary.kanbanSlotHour, "todo", -1)
                    && todoSearchMatches(summary.name)) {
                return true
            }
        }
        return false
    }

    function setPlacement(tabIndex, status, slotHour) {
        if (!tabModelRef || !tabModelRef.setKanbanPlacement)
            return
        tabModelRef.setKanbanPlacement(Number(tabIndex), status, Number(slotHour))
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

    function dropTabAt(tabIndex, sceneX, sceneY) {
        for (var i = dropZones.length - 1; i >= 0; --i) {
            var zone = dropZones[i]
            if (!zone || !zone.visible)
                continue
            var local = zone.mapFromItem(null, sceneX, sceneY)
            if (local.x < 0 || local.y < 0 || local.x > zone.width || local.y > zone.height)
                continue
            setPlacement(tabIndex, zone.targetStatus, zone.targetSlotHour)
            return true
        }
        return false
    }

    function cardScenePoint(card, localX, localY) {
        if (!card)
            return Qt.point(0, 0)
        return card.mapToItem(null, localX, localY)
    }

    function beginCardDrag(card, tabIndex, tabName, tabIcon, localX, localY) {
        var scene = cardScenePoint(card, localX, localY)
        dragActive = true
        dragTabIndex = Number(tabIndex)
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
        if (dragActive && dragTabIndex >= 0)
            dropTabAt(dragTabIndex, dragSceneX, dragSceneY)
        dragActive = false
        dragTabIndex = -1
        dragTabName = ""
        dragTabIcon = ""
    }

    function openTab(tabIndex) {
        if (tabIndex < 0 || tabIndex >= root.modelCount())
            return
        if (projectManagerRef && projectManagerRef.openKanbanTab)
            projectManagerRef.openKanbanTab(tabIndex)
        else if (projectManagerRef && projectManagerRef.switchTab)
            projectManagerRef.switchTab(tabIndex)
        else if (tabModelRef && tabModelRef.setCurrentTab)
            tabModelRef.setCurrentTab(tabIndex)
        root.close()
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

    function requestDeleteTab(tabIndex, tabName) {
        if (tabIndex < 0 || tabIndex >= root.modelCount() || root.modelCount() <= 1)
            return
        pendingDeleteTabIndex = tabIndex
        pendingDeleteTabName = tabName || ""
        deleteTabDialog.open()
    }

    function confirmDeleteTab() {
        if (pendingDeleteTabIndex < 0 || pendingDeleteTabIndex >= root.modelCount())
            return
        if (projectManagerRef && projectManagerRef.removeTab)
            projectManagerRef.removeTab(pendingDeleteTabIndex)
        else if (tabModelRef && tabModelRef.removeTab)
            tabModelRef.removeTab(pendingDeleteTabIndex)
        pendingDeleteTabIndex = -1
        pendingDeleteTabName = ""
    }

    Rectangle {
        anchors.fill: parent
        z: -2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0d1822" }
            GradientStop { position: 1.0; color: "#101923" }
        }
    }

    Component {
        id: kanbanCardComponent

        Rectangle {
            id: tabCard
            property int modelIndex: -1
            property string tabName: ""
            property string tabIcon: ""
            property string tabColor: ""
            property real completionPercent: 0
            property string activeTaskTitle: ""
            property bool suppressClick: false
            property bool dragging: cardMouse.dragging
            property real pressX: 0
            property real pressY: 0

            property int tabIndex: modelIndex
            objectName: "kanbanCard_" + tabIndex

            width: parent ? parent.width : 240
            height: activeTaskTitle.length > 0 ? 82 : 62
            radius: 8
            color: cardMouse.containsMouse ? "#203445" : "#172737"
            border.color: cardMouse.containsMouse ? "#72b8d8" : "#314b5f"
            border.width: 1
            scale: dragging ? 1.02 : 1.0
            opacity: dragging ? 0.88 : 1.0

            Drag.active: cardDragHandler.active
            Drag.source: tabCard
            Drag.keys: ["kanban-tab"]
            Drag.supportedActions: Qt.MoveAction
            Drag.hotSpot.x: width / 2
            Drag.hotSpot.y: height / 2

            Behavior on scale {
                NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
            }

            Behavior on opacity {
                NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
            }

            Rectangle {
                width: 4
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                radius: 2
                color: tabColor && tabColor.length > 0 ? tabColor : "#4aa3ff"
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
                    tabCard.pressX = mouse.x
                    tabCard.pressY = mouse.y
                    dragging = false
                    tabCard.suppressClick = false
                }

                onPositionChanged: function(mouse) {
                    if (!(mouse.buttons & Qt.LeftButton))
                        return
                    var dx = mouse.x - tabCard.pressX
                    var dy = mouse.y - tabCard.pressY
                    if (!dragging && Math.sqrt(dx * dx + dy * dy) >= 6) {
                        dragging = true
                        tabCard.suppressClick = true
                        root.beginCardDrag(
                            tabCard,
                            tabCard.tabIndex,
                            tabCard.tabName,
                            tabCard.tabIcon,
                            mouse.x,
                            mouse.y
                        )
                    }
                    if (dragging)
                        root.updateCardDrag(tabCard, mouse.x, mouse.y)
                }

                onReleased: function(mouse) {
                    if (dragging) {
                        root.updateCardDrag(tabCard, mouse.x, mouse.y)
                        root.endCardDrag()
                        dragging = false
                        return
                    }
                    if (mouse.x >= tabCard.width - 42)
                        root.requestDeleteTab(tabCard.tabIndex, tabCard.tabName)
                    else
                        root.openTab(tabCard.tabIndex)
                }

                onCanceled: {
                    if (dragging)
                        root.endCardDrag()
                    dragging = false
                }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 8
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                spacing: 8

                Text {
                    text: tabIcon && tabIcon.length > 0 ? tabIcon : "."
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
                        text: tabName
                        color: "#f0f7ff"
                        font.pixelSize: 13
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: activeTaskTitle.length > 0
                        text: "Active: " + activeTaskTitle
                        color: "#9fd0b3"
                        font.pixelSize: 10
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
                    color: root.modelCount() > 1 ? "#26394b" : "#1a2530"
                    border.color: "#3c5569"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "x"
                        color: root.modelCount() > 1 ? "#dceaf4" : "#617181"
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
            objectName: "kanbanDrop_" + targetStatus + "_" + targetSlotHour

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
                keys: ["kanban-tab"]
                z: 20
                onDropped: function(drop) {
                    if (drop.source && drop.source.tabIndex !== undefined) {
                        root.setPlacement(drop.source.tabIndex, sectionRoot.targetStatus, sectionRoot.targetSlotHour)
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
                        text: "+"
                        Layout.preferredWidth: 32
                        Layout.preferredHeight: 28
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
                            model: root.tabModelRef

                            delegate: Loader {
                                property bool placedHere: root.cardMatchesSection(
                                    kanbanStatus,
                                    kanbanSlotHour,
                                    name,
                                    sectionRoot.targetStatus,
                                    sectionRoot.targetSlotHour
                                )
                                width: cardsColumn.width
                                height: placedHere ? (activeTaskTitle.length > 0 ? 82 : 62) : 0
                                visible: placedHere
                                active: placedHere
                                sourceComponent: kanbanCardComponent
                                onLoaded: {
                                    item.modelIndex = index
                                    item.tabName = name || ""
                                    item.tabIcon = icon || ""
                                    item.tabColor = color || ""
                                    item.completionPercent = completionPercent || 0
                                    item.activeTaskTitle = activeTaskTitle || ""
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
                text: root.modelCount() + " tabs"
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

                    Text {
                        text: "In Progress"
                        color: "#e8f4ff"
                        font.pixelSize: 14
                        font.bold: true
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
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 154
                                    sourceComponent: boardSectionComponent
                                    onLoaded: {
                                        item.sectionTitle = root.slotLabel(modelData)
                                        item.targetStatus = "in_progress"
                                        item.targetSlotHour = Number(modelData)
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

    Dialog {
        id: deleteTabDialog
        title: "Remove Tab"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: root.confirmDeleteTab()

        Label {
            width: 320
            wrapMode: Text.WordWrap
            text: "Remove tab \"" + root.pendingDeleteTabName + "\" completely?"
        }
    }
}
