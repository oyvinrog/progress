import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: sidebar
    property var tabModel
    property var projectManager

    Layout.fillHeight: true
    Layout.preferredWidth: 220
    radius: 8
    color: "#1b2028"
    border.color: "#2e3744"
    visible: tabModel !== null

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

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
                spacing: 2

                Repeater {
                    model: tabModel

                    delegate: Rectangle {
                        id: tabButton
                        property bool isActive: tabModel ? index === tabModel.currentTabIndex : false
                        property string activeTaskTitle: model.activeTaskTitle || ""
                        property int tabPriority: model.priority || 0
                        width: tabColumnContent.width
                        height: 32
                        radius: 5
                        color: isActive ? "#3b485c" : (tabMouseArea.containsMouse ? "#2a3444" : "transparent")
                        border.color: isActive ? "#4a9eff" : "transparent"
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            anchors.topMargin: 4
                            anchors.bottomMargin: 4
                            spacing: 0

                            RowLayout {
                                spacing: 6

                                Rectangle {
                                    id: priorityBadge
                                    visible: tabButton.tabPriority > 0
                                    width: 16
                                    height: 16
                                    radius: 3
                                    color: tabButton.tabPriority === 1 ? "#e53935" :
                                           tabButton.tabPriority === 2 ? "#fb8c00" :
                                           tabButton.tabPriority === 3 ? "#43a047" : "transparent"

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
                                    color: isActive ? "#ffffff" : "#9aa6b8"
                                    font.pixelSize: 11
                                    font.bold: isActive
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                Text {
                                    id: tabPercent
                                    text: Math.round(model.completionPercent) + "%"
                                    color: isActive ? "#4a9eff" : "#7f8a9a"
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }

                            Text {
                                id: tabActiveTask
                                visible: tabButton.activeTaskTitle !== ""
                                text: tabButton.activeTaskTitle
                                color: isActive ? "#82c3a5" : "#6a7a6a"
                                font.pixelSize: 9
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }

                        ToolTip {
                            visible: tabMouseArea.containsMouse && (tabName.truncated || tabActiveTask.truncated || tabButton.tabPriority > 0)
                            text: {
                                var priorityText = tabButton.tabPriority === 1 ? "[Priority 1 - High] " :
                                                   tabButton.tabPriority === 2 ? "[Priority 2 - Medium] " :
                                                   tabButton.tabPriority === 3 ? "[Priority 3 - Low] " : ""
                                return priorityText + model.name + " (" + Math.round(model.completionPercent) + "%)" + (tabButton.activeTaskTitle ? "\n" + tabButton.activeTaskTitle : "")
                            }
                            delay: 500
                        }

                        MouseArea {
                            id: tabMouseArea
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            onClicked: function(mouse) {
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
            height: 28
            radius: 5
            color: addTabMouseArea.containsMouse ? "#2a3444" : "transparent"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8

                Text {
                    text: "+ Add Tab"
                    color: "#7f8a9a"
                    font.pixelSize: 11
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
