import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: sidebar
    property var tabModel
    property var projectManager
    property var onTabDragMoved
    property var onTabDragReleased
    property var onAnalyzeHierarchy
    property int expandedWidth: 252
    property int collapsedWidth: 48
    readonly property var iconPresetValues: [
        "⭐", "✅", "⚠", "📌", "🚩", "🎯",
        "📝", "📅", "🔒", "🔗", "💡", "🧠"
    ]
    readonly property var colorPresetValues: [
        "#4aa3ff", "#2fd7c4", "#45d66f", "#f5c542",
        "#ff8a3d", "#ff5d73", "#d46bff", "#7a8cff",
        "#6b7c93", "#7f8c8d", "#a77d54", "#e6e6e6"
    ]
    readonly property bool keepExpanded: (
        tabContextMenu.visible
        || renameTabDialog.visible
        || tabIconDialog.visible
        || tabColorDialog.visible
    )
    readonly property bool persistedExpanded: projectManager ? projectManager.sidebarExpanded : true
    readonly property bool isExpanded: persistedExpanded || keepExpanded

    function toggleSidebarExpanded() {
        if (!projectManager || !projectManager.setSidebarExpanded)
            return
        projectManager.setSidebarExpanded(!persistedExpanded)
    }

    function openTabRenameDialog(tabIndex, tabName) {
        renameTabDialog.tabIndex = tabIndex
        renameTabDialog.currentName = tabName
        renameTabDialog.open()
    }

    function openTabIconDialog(tabIndex, tabIcon, tabName) {
        tabIconDialog.tabIndex = tabIndex
        tabIconDialog.currentIcon = tabIcon || ""
        tabIconDialog.currentName = tabName || ""
        tabIconDialog.open()
    }

    function openTabColorDialog(tabIndex, tabColor, tabName) {
        tabColorDialog.tabIndex = tabIndex
        tabColorDialog.currentColor = tabColor || ""
        tabColorDialog.currentName = tabName || ""
        tabColorDialog.open()
    }

    Layout.fillHeight: true
    Layout.preferredWidth: isExpanded ? expandedWidth : collapsedWidth
    Behavior on Layout.preferredWidth {
        NumberAnimation {
            duration: 140
            easing.type: Easing.OutCubic
        }
    }

    radius: 12
    color: "#131f2a"
    border.color: "#2b3f53"
    border.width: 1
    visible: tabModel !== null
    clip: true

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#1a2a38" }
            GradientStop { position: 1.0; color: "#101a24" }
        }
        opacity: 0.32
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: sidebar.isExpanded ? 10 : 6
        spacing: 8

        Rectangle {
            id: headerBox
            Layout.fillWidth: true
            height: 34
            radius: 8
            color: {
                if (headerMouseArea.pressed)
                    return "#24425a"
                if (headerMouseArea.containsMouse)
                    return "#22384c"
                return "#192736"
            }
            border.color: "#31485e"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: sidebar.isExpanded ? 10 : 6
                anchors.rightMargin: sidebar.isExpanded ? 10 : 6
                spacing: 8

                Text {
                    text: sidebar.isExpanded ? "Project Tabs" : "Tabs"
                    color: "#dbe7f3"
                    font.pixelSize: sidebar.isExpanded ? 12 : 10
                    font.bold: true
                    Layout.alignment: sidebar.isExpanded ? Qt.AlignVCenter : (Qt.AlignVCenter | Qt.AlignHCenter)
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    visible: sidebar.isExpanded
                    radius: 6
                    color: "#103047"
                    border.color: "#2f5871"
                    implicitWidth: 30
                    implicitHeight: 20

                    Text {
                        anchors.centerIn: parent
                        text: tabModel ? tabModel.tabCount : 0
                        color: "#8dd4ff"
                        font.pixelSize: 11
                        font.bold: true
                    }
                }

                Text {
                    text: sidebar.isExpanded ? "<" : ">"
                    color: "#9fc6e0"
                    font.pixelSize: 14
                    font.bold: true
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            MouseArea {
                id: headerMouseArea
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor
                onClicked: function(mouse) {
                    if (mouse.button === Qt.LeftButton && !sidebar.keepExpanded)
                        sidebar.toggleSidebarExpanded()
                }
            }
        }

        Flickable {
            id: tabFlickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: tabColumnContent.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: tabColumnContent
                width: tabFlickable.width
                spacing: 4

                Repeater {
                    model: tabModel

                    delegate: Rectangle {
                        id: tabButton
                        property bool isActive: tabModel ? index === tabModel.currentTabIndex : false
                        property string activeTaskTitle: model.activeTaskTitle || ""
                        property real tabPriorityScore: model.priorityScore || 0
                        property int dragTabIndex: index
                        property string dragTabName: model.name || ""
                        property string tabIcon: model.icon || ""
                        property string tabColor: model.color || ""
                        property color tabAccentColor: tabColor !== ""
                            ? tabColor
                            : (isActive ? "#64c1ff" : "#2a4358")
                        property color idleTabColor: Qt.darker(tabAccentColor, 4.2)
                        property color hoverTabColor: Qt.darker(tabAccentColor, 3.6)
                        property color activeTabColor: Qt.darker(tabAccentColor, 2.9)
                        property bool suppressClick: false
                        property bool dragging: tabDragHandler.active
                        width: tabColumnContent.width
                        height: tabButton.activeTaskTitle !== "" && sidebar.isExpanded ? 54 : 40
                        radius: 9
                        scale: dragging ? 1.03 : 1.0
                        opacity: dragging ? 0.9 : 1.0
                        color: isActive ? activeTabColor : (tabMouseArea.containsMouse ? hoverTabColor : idleTabColor)
                        border.color: dragging ? "#8fe2ff" : tabAccentColor
                        border.width: dragging ? 2 : 1

                        Behavior on color {
                            ColorAnimation { duration: 110 }
                        }
                        Behavior on scale {
                            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
                        }
                        Behavior on opacity {
                            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
                        }

                        Drag.active: tabDragHandler.active
                        Drag.keys: ["progress-tab"]
                        Drag.supportedActions: Qt.CopyAction
                        Drag.mimeData: ({ "text/plain": tabButton.dragTabName })
                        Drag.hotSpot.x: width / 2
                        Drag.hotSpot.y: height / 2

                        DragHandler {
                            id: tabDragHandler
                            target: null
                            acceptedButtons: Qt.LeftButton
                            dragThreshold: 4
                            onActiveChanged: {
                                var scenePos = tabButton.mapToItem(
                                    null,
                                    tabDragHandler.centroid.position.x,
                                    tabDragHandler.centroid.position.y
                                )
                                if (active) {
                                    tabButton.suppressClick = true
                                    if (typeof sidebar.onTabDragMoved === "function")
                                        sidebar.onTabDragMoved(tabButton.dragTabIndex, tabButton.dragTabName, scenePos.x, scenePos.y, true)
                                } else {
                                    if (typeof sidebar.onTabDragMoved === "function")
                                        sidebar.onTabDragMoved(tabButton.dragTabIndex, tabButton.dragTabName, scenePos.x, scenePos.y, false)
                                    if (tabButton.suppressClick && typeof sidebar.onTabDragReleased === "function") {
                                        sidebar.onTabDragReleased(tabButton.dragTabIndex, scenePos.x, scenePos.y)
                                    }
                                }
                            }
                            onTranslationChanged: {
                                if (!tabDragHandler.active || typeof sidebar.onTabDragMoved !== "function")
                                    return
                                var scenePos = tabButton.mapToItem(
                                    null,
                                    tabDragHandler.centroid.position.x,
                                    tabDragHandler.centroid.position.y
                                )
                                sidebar.onTabDragMoved(tabButton.dragTabIndex, tabButton.dragTabName, scenePos.x, scenePos.y, true)
                            }
                        }

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 6
                            anchors.bottomMargin: 6
                            spacing: 2

                            RowLayout {
                                spacing: 6

                                Rectangle {
                                    id: tabAccentSwatch
                                    width: 12
                                    height: 12
                                    radius: 6
                                    color: tabButton.tabAccentColor
                                    border.color: isActive ? "#d9efff" : "#aac2d8"
                                    border.width: 1
                                    visible: sidebar.isExpanded
                                }

                                Text {
                                    id: tabIconText
                                    text: tabButton.tabIcon
                                    visible: sidebar.isExpanded && tabButton.tabIcon.length > 0
                                    color: isActive ? "#ffffff" : "#d9e8f6"
                                    font.pixelSize: 12
                                    font.bold: true
                                }

                                Rectangle {
                                    id: priorityBadge
                                    visible: tabButton.tabPriorityScore > 0
                                    width: 36
                                    height: 16
                                    radius: 4
                                    color: "#1b4d67"
                                    border.color: "#68c8f2"
                                    border.width: 1

                                    Text {
                                        anchors.centerIn: parent
                                        text: tabButton.tabPriorityScore.toFixed(2)
                                        color: "#ffffff"
                                        font.pixelSize: 9
                                        font.bold: true
                                    }
                                }

                                Text {
                                    id: tabName
                                    text: model.name
                                    color: isActive ? "#ffffff" : "#b0c2d4"
                                    font.pixelSize: 11
                                    font.bold: isActive
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    visible: sidebar.isExpanded
                                }

                                Text {
                                    text: tabButton.tabIcon.length > 0
                                        ? tabButton.tabIcon
                                        : (model.name.length > 0 ? model.name.charAt(0).toUpperCase() : "T")
                                    visible: !sidebar.isExpanded
                                    color: isActive ? "#ffffff" : "#b0c2d4"
                                    font.pixelSize: 12
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.fillWidth: true
                                }

                                Text {
                                    id: tabPercent
                                    text: Math.round(model.completionPercent) + "%"
                                    color: isActive ? "#88d5ff" : "#8ca5ba"
                                    font.pixelSize: 10
                                    font.bold: true
                                    visible: sidebar.isExpanded
                                }
                            }

                            Text {
                                id: tabActiveTask
                                visible: sidebar.isExpanded && tabButton.activeTaskTitle !== ""
                                text: tabButton.activeTaskTitle
                                color: isActive ? "#9be4bc" : "#7ea98f"
                                font.pixelSize: 9
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        ToolTip {
                            visible: tabMouseArea.containsMouse
                            text: {
                                var priorityText = tabButton.tabPriorityScore > 0
                                    ? "[Score " + tabButton.tabPriorityScore.toFixed(2) + "] "
                                    : ""
                                var baseText = priorityText + model.name + " (" + Math.round(model.completionPercent) + "%)"
                                if (tabButton.activeTaskTitle)
                                    baseText += "\n" + tabButton.activeTaskTitle
                                return baseText + "\nDrag to drawing to create a drill task"
                            }
                            delay: 500
                        }

                        MouseArea {
                            id: tabMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            cursorShape: tabDragHandler.active ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                            onClicked: function(mouse) {
                                if (tabButton.suppressClick && mouse.button === Qt.LeftButton) {
                                    tabButton.suppressClick = false
                                    return
                                }
                                if (mouse.button === Qt.RightButton) {
                                    tabContextMenu.tabIndex = index
                                    tabContextMenu.tabName = model.name
                                    tabContextMenu.tabIcon = model.icon || ""
                                    tabContextMenu.tabColor = model.color || ""
                                    tabContextMenu.includeInPlot = model.includeInPriorityPlot !== false
                                    tabContextMenu.popup()
                                } else {
                                    if (projectManager)
                                        projectManager.switchTab(index)
                                }
                            }
                            onDoubleClicked: function(mouse) {
                                if (mouse.button !== Qt.LeftButton)
                                    return
                                sidebar.openTabRenameDialog(index, model.name)
                            }
                        }
                    }
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: ScrollBar.AsNeeded
                width: 6
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 34
            radius: 8
            color: addTabMouseArea.containsMouse ? "#24425a" : "#193044"
            border.color: "#325771"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10

                Text {
                    text: sidebar.isExpanded ? "+ Add Tab" : "+"
                    color: "#d2e4f3"
                    font.pixelSize: sidebar.isExpanded ? 11 : 16
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: !sidebar.isExpanded
                }
            }

            MouseArea {
                id: addTabMouseArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    if (tabModel) {
                        tabModel.addTab("")
                        if (projectManager)
                            projectManager.switchTab(tabModel.tabCount - 1)
                    }
                }
            }
        }
    }

    Menu {
        id: tabContextMenu
        property int tabIndex: -1
        property string tabName: ""
        property string tabIcon: ""
        property string tabColor: ""
        property bool includeInPlot: true

        Menu {
            title: "Set Priority"

            MenuItem {
                text: "1 - High"
                onTriggered: {
                    if (tabModel)
                        tabModel.setPriority(tabContextMenu.tabIndex, 1)
                }
            }
            MenuItem {
                text: "2 - Medium"
                onTriggered: {
                    if (tabModel)
                        tabModel.setPriority(tabContextMenu.tabIndex, 2)
                }
            }
            MenuItem {
                text: "3 - Low"
                onTriggered: {
                    if (tabModel)
                        tabModel.setPriority(tabContextMenu.tabIndex, 3)
                }
            }
            MenuSeparator {}
            MenuItem {
                text: "Clear Priority"
                onTriggered: {
                    if (tabModel)
                        tabModel.setPriority(tabContextMenu.tabIndex, 0)
                }
            }
        }

        MenuSeparator {}

        MenuItem {
            text: (tabContextMenu.includeInPlot === true)
                ? "Exclude from Priority Plot"
                : "Include in Priority Plot"
            onTriggered: {
                if (tabModel && tabModel.setIncludeInPriorityPlot) {
                    tabModel.setIncludeInPriorityPlot(tabContextMenu.tabIndex, !tabContextMenu.includeInPlot)
                    tabContextMenu.includeInPlot = !tabContextMenu.includeInPlot
                }
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "Set Icon..."
            onTriggered: {
                sidebar.openTabIconDialog(tabContextMenu.tabIndex, tabContextMenu.tabIcon, tabContextMenu.tabName)
            }
        }
        MenuItem {
            text: "Clear Icon"
            enabled: tabContextMenu.tabIcon.length > 0
            onTriggered: {
                if (tabModel && tabModel.setTabIcon)
                    tabModel.setTabIcon(tabContextMenu.tabIndex, "")
            }
        }
        MenuItem {
            text: "Set Color..."
            onTriggered: {
                sidebar.openTabColorDialog(tabContextMenu.tabIndex, tabContextMenu.tabColor, tabContextMenu.tabName)
            }
        }
        MenuItem {
            text: "Clear Color"
            enabled: tabContextMenu.tabColor.length > 0
            onTriggered: {
                if (tabModel && tabModel.setTabColor)
                    tabModel.setTabColor(tabContextMenu.tabIndex, "")
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "Analyze Hierarchy..."
            onTriggered: {
                if (typeof sidebar.onAnalyzeHierarchy === "function")
                    sidebar.onAnalyzeHierarchy(tabContextMenu.tabIndex)
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "Move Left"
            enabled: tabModel ? tabContextMenu.tabIndex > 0 : false
            onTriggered: {
                if (tabModel && tabContextMenu.tabIndex > 0)
                    tabModel.moveTab(tabContextMenu.tabIndex, tabContextMenu.tabIndex - 1)
            }
        }
        MenuItem {
            text: "Move Right"
            enabled: tabModel ? tabContextMenu.tabIndex < tabModel.tabCount - 1 : false
            onTriggered: {
                if (tabModel && tabContextMenu.tabIndex < tabModel.tabCount - 1)
                    tabModel.moveTab(tabContextMenu.tabIndex, tabContextMenu.tabIndex + 1)
            }
        }
        MenuItem {
            text: "Rename..."
            onTriggered: {
                sidebar.openTabRenameDialog(tabContextMenu.tabIndex, tabContextMenu.tabName)
            }
        }
        MenuItem {
            text: "Delete"
            enabled: tabModel ? tabModel.tabCount > 1 : false
            onTriggered: {
                if (projectManager && tabModel && tabModel.tabCount > 1)
                    projectManager.removeTab(tabContextMenu.tabIndex)
            }
        }
    }

    Dialog {
        id: tabIconDialog
        property int tabIndex: -1
        property string currentIcon: ""
        property string currentName: ""
        property string selectedIcon: ""
        title: "Set Tab Icon"
        modal: true
        anchors.centerIn: parent
        width: 360
        standardButtons: Dialog.Ok | Dialog.Cancel

        contentItem: ColumnLayout {
            width: tabIconDialog.width - 32
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                height: 36
                radius: 7
                color: "#122638"
                border.color: "#325771"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Text {
                        text: tabIconDialog.selectedIcon.length > 0 ? tabIconDialog.selectedIcon : "T"
                        color: "#f1f7ff"
                        font.pixelSize: 14
                        font.bold: true
                    }

                    Text {
                        text: tabIconDialog.currentName.length > 0 ? tabIconDialog.currentName : "Tab Preview"
                        color: "#c8d8e8"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            Text {
                text: "Choose an icon"
                color: "#b6c9db"
                font.pixelSize: 11
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 6
                rowSpacing: 6
                columnSpacing: 6

                Repeater {
                    model: sidebar.iconPresetValues

                    delegate: Rectangle {
                        required property string modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        radius: 6
                        color: tabIconDialog.selectedIcon === modelData ? "#2a4a63" : "#1a2f42"
                        border.color: tabIconDialog.selectedIcon === modelData ? "#7bc6ff" : "#33546d"
                        border.width: 1

                        Text {
                            anchors.centerIn: parent
                            text: modelData
                            color: "#eaf3fd"
                            font.pixelSize: 12
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                tabIconDialog.selectedIcon = modelData
                                customIconField.text = modelData
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "None"
                    onClicked: {
                        tabIconDialog.selectedIcon = ""
                        customIconField.text = ""
                    }
                }

                TextField {
                    id: customIconField
                    Layout.fillWidth: true
                    placeholderText: "Custom icon (emoji/symbol)"
                    selectByMouse: true
                    maximumLength: 4
                    onTextChanged: {
                        tabIconDialog.selectedIcon = text.trim()
                    }
                    onAccepted: tabIconDialog.accept()
                }
            }
        }

        onOpened: {
            selectedIcon = currentIcon
            customIconField.text = currentIcon
            customIconField.selectAll()
            customIconField.forceActiveFocus()
        }

        onAccepted: {
            if (tabModel && tabModel.setTabIcon)
                tabModel.setTabIcon(tabIndex, selectedIcon.trim())
        }
    }

    Dialog {
        id: tabColorDialog
        property int tabIndex: -1
        property string currentColor: ""
        property string currentName: ""
        property string selectedColor: ""
        title: "Set Tab Color"
        modal: true
        anchors.centerIn: parent
        width: 360
        standardButtons: Dialog.Ok | Dialog.Cancel

        contentItem: ColumnLayout {
            width: tabColorDialog.width - 32
            spacing: 10

            Rectangle {
                Layout.fillWidth: true
                height: 36
                radius: 7
                color: "#122638"
                border.color: "#325771"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8

                    Rectangle {
                        width: 14
                        height: 14
                        radius: 7
                        color: tabColorDialog.selectedColor.length > 0 ? tabColorDialog.selectedColor : "#2a4358"
                        border.color: "#aac2d8"
                        border.width: 1
                    }

                    Text {
                        text: tabColorDialog.currentName.length > 0 ? tabColorDialog.currentName : "Tab Preview"
                        color: "#c8d8e8"
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: tabColorDialog.selectedColor.length > 0 ? tabColorDialog.selectedColor : "default"
                        color: "#9fc1d9"
                        font.pixelSize: 10
                    }
                }
            }

            Text {
                text: "Choose a color"
                color: "#b6c9db"
                font.pixelSize: 11
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 6
                rowSpacing: 6
                columnSpacing: 6

                Repeater {
                    model: sidebar.colorPresetValues

                    delegate: Rectangle {
                        required property string modelData
                        Layout.fillWidth: true
                        Layout.preferredHeight: 26
                        radius: 6
                        color: modelData
                        border.color: tabColorDialog.selectedColor === modelData ? "#ecf6ff" : "#355268"
                        border.width: tabColorDialog.selectedColor === modelData ? 2 : 1

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                tabColorDialog.selectedColor = modelData
                                customColorField.text = modelData
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "Default"
                    onClicked: {
                        tabColorDialog.selectedColor = ""
                        customColorField.text = ""
                    }
                }

                TextField {
                    id: customColorField
                    Layout.fillWidth: true
                    placeholderText: "Custom color (for example: #4aa3ff)"
                    selectByMouse: true
                    onTextChanged: {
                        tabColorDialog.selectedColor = text.trim()
                    }
                    onAccepted: tabColorDialog.accept()
                }
            }
        }

        onOpened: {
            selectedColor = currentColor
            customColorField.text = currentColor
            customColorField.selectAll()
            customColorField.forceActiveFocus()
        }

        onAccepted: {
            if (tabModel && tabModel.setTabColor)
                tabModel.setTabColor(tabIndex, selectedColor.trim())
        }
    }

    Dialog {
        id: renameTabDialog
        property int tabIndex: -1
        property string currentName: ""
        title: "Rename Tab"
        modal: true
        anchors.centerIn: parent
        width: 300
        standardButtons: Dialog.Ok | Dialog.Cancel

        TextField {
            id: renameTabField
            width: parent.width
            text: renameTabDialog.currentName
            placeholderText: "Tab name"
            selectByMouse: true
            onAccepted: renameTabDialog.accept()
        }

        onOpened: {
            renameTabField.text = currentName
            renameTabField.selectAll()
            renameTabField.forceActiveFocus()
        }

        onAccepted: {
            if (tabModel && renameTabField.text.trim())
                tabModel.renameTab(tabIndex, renameTabField.text.trim())
        }
    }
}
