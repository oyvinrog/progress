import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: sidebar
    property var tabModel
    property var projectManager
    property var onTabDragReleased
    property int expandedWidth: 252
    property int collapsedWidth: 48
    readonly property bool keepExpanded: tabContextMenu.visible || renameTabDialog.visible
    readonly property bool isExpanded: sidebarHoverHandler.hovered || keepExpanded

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

    HoverHandler {
        id: sidebarHoverHandler
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: sidebar.isExpanded ? 10 : 6
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            height: 34
            radius: 8
            color: "#192736"
            border.color: "#31485e"
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                Text {
                    text: sidebar.isExpanded ? "Project Tabs" : ">"
                    color: "#dbe7f3"
                    font.pixelSize: sidebar.isExpanded ? 12 : 14
                    font.bold: true
                    Layout.alignment: Qt.AlignVCenter
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
                        property int tabPriority: model.priority || 0
                        property int dragTabIndex: index
                        property string dragTabName: model.name || ""
                        property bool suppressClick: false
                        width: tabColumnContent.width
                        height: tabButton.activeTaskTitle !== "" && sidebar.isExpanded ? 54 : 40
                        radius: 9
                        color: isActive ? "#1f3b54" : (tabMouseArea.containsMouse ? "#1a2f42" : "#132535")
                        border.color: isActive ? "#64c1ff" : "#2a4358"
                        border.width: 1

                        Behavior on color {
                            ColorAnimation { duration: 110 }
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
                            onActiveChanged: {
                                if (active)
                                    tabButton.suppressClick = true
                                else if (tabButton.suppressClick && typeof sidebar.onTabDragReleased === "function") {
                                    var scenePos = tabButton.mapToItem(
                                        null,
                                        tabDragHandler.centroid.position.x,
                                        tabDragHandler.centroid.position.y
                                    )
                                    sidebar.onTabDragReleased(tabButton.dragTabIndex, scenePos.x, scenePos.y)
                                }
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
                                    id: priorityBadge
                                    visible: tabButton.tabPriority > 0
                                    width: 16
                                    height: 16
                                    radius: 4
                                    color: tabButton.tabPriority === 1 ? "#d84f4f" :
                                           tabButton.tabPriority === 2 ? "#e1943c" :
                                           tabButton.tabPriority === 3 ? "#4da268" : "transparent"

                                    Text {
                                        anchors.centerIn: parent
                                        text: tabButton.tabPriority
                                        color: "#ffffff"
                                        font.pixelSize: 10
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
                                    text: model.name.length > 0 ? model.name.charAt(0).toUpperCase() : "T"
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
                                var priorityText = tabButton.tabPriority === 1 ? "[Priority 1 - High] " :
                                                   tabButton.tabPriority === 2 ? "[Priority 2 - Medium] " :
                                                   tabButton.tabPriority === 3 ? "[Priority 3 - Low] " : ""
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
                            onClicked: function(mouse) {
                                if (tabButton.suppressClick && mouse.button === Qt.LeftButton) {
                                    tabButton.suppressClick = false
                                    return
                                }
                                if (mouse.button === Qt.RightButton) {
                                    tabContextMenu.tabIndex = index
                                    tabContextMenu.tabName = model.name
                                    tabContextMenu.popup()
                                } else {
                                    if (projectManager)
                                        projectManager.switchTab(index)
                                }
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
                renameTabDialog.tabIndex = tabContextMenu.tabIndex
                renameTabDialog.currentName = tabContextMenu.tabName
                renameTabDialog.open()
            }
        }
        MenuItem {
            text: "Delete"
            enabled: tabModel ? tabModel.tabCount > 1 : false
            onTriggered: {
                if (tabModel && tabModel.tabCount > 1) {
                    var wasCurrentTab = (tabContextMenu.tabIndex === tabModel.currentTabIndex)
                    tabModel.removeTab(tabContextMenu.tabIndex)
                    if (wasCurrentTab && projectManager)
                        projectManager.reloadCurrentTab()
                }
            }
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
