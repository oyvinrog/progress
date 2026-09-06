import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Column {
    id: overview
    objectName: "reminderOverview"
    property var windowRoot
    property var projectManager
    property var dialogs
    spacing: 6

    Rectangle {
        width: overview.width
        height: reminderHeader.implicitHeight + 12
        radius: 8
        color: "#21313d"
        border.color: "#3b566a"
        visible: !!overview.projectManager

        Flow {
            id: reminderHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 6
            spacing: 10

            Label {
                text: "Waiting Reminders · " + overview.windowRoot.activeReminders.length + " pending"
                color: "#ffe4c7"
                font.pixelSize: 12
                font.bold: true
                height: newReminderButton.implicitHeight
                verticalAlignment: Text.AlignVCenter
            }
            Button {
                id: newReminderButton
                objectName: "newStandaloneReminder"
                text: "New Reminder"
                onClicked: overview.dialogs.openStandaloneReminderDialog()
            }
            Button {
                objectName: "toggleReminderOverview"
                text: overview.windowRoot.reminderOverviewExpanded ? "Roll Up" : "Roll Down"
                onClicked: {
                    overview.windowRoot.reminderOverviewExpanded = !overview.windowRoot.reminderOverviewExpanded
                    overview.windowRoot.reminderOverviewTouched = true
                }
            }
        }
    }

    ScrollView {
        width: overview.width
        height: Math.min(reminderRows.implicitHeight, 180)
        clip: true
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
        visible: overview.windowRoot.activeReminders.length > 0 && overview.windowRoot.reminderOverviewExpanded

        Column {
            id: reminderRows
            width: overview.width
            spacing: 6

            Repeater {
                model: overview.windowRoot.activeReminders
                delegate: Rectangle {
                    id: reminderRow
                    required property var modelData
                    objectName: "reminderRow_" + (modelData.nodeId || modelData.kind)
                    width: reminderRows.width
                    height: rowContent.implicitHeight + 12
                    radius: 6
                    color: "#2e261f"
                    border.color: "#8d6948"

                    GridLayout {
                        id: rowContent
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 6
                        columns: width >= 560 ? 2 : 1
                        columnSpacing: 8
                        rowSpacing: 4

                        Column {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: 1
                            Text {
                                width: parent.width
                                text: "[" + reminderRow.modelData.tabName + "] " + (reminderRow.modelData.title || reminderRow.modelData.taskTitle)
                                color: "#fff7ef"
                                font.pixelSize: 11
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: "Due in " + (reminderRow.modelData.countdownText || "0:00")
                                color: "#ffe3a8"
                                font.pixelSize: 10
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: "Remind at " + reminderRow.modelData.reminderText
                                color: "#f1c892"
                                font.pixelSize: 10
                                elide: Text.ElideRight
                            }
                        }
                        RowLayout {
                            spacing: 6
                            Button {
                                objectName: "openReminder_" + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                text: reminderRow.modelData.kind === "mindmap" ? "Open Node" : "Open Task"
                                visible: reminderRow.modelData.kind !== "standalone"
                                onClicked: {
                                    var data = reminderRow.modelData
                                    if (data.kind === "mindmap")
                                        overview.projectManager.openMindmapReminder(data.nodeId)
                                    else
                                        overview.projectManager.openTabTask(Number(data.tabIndex), Number(data.taskIndex))
                                }
                            }
                            Button {
                                objectName: "editReminder_" + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                text: "Edit"
                                onClicked: {
                                    var data = reminderRow.modelData
                                    if (data.kind === "mindmap")
                                        overview.dialogs.openMindmapReminderDialog(data.nodeId, data.reminderText, data.sendNotification)
                                    else if (data.kind === "standalone")
                                        overview.dialogs.openStandaloneReminderEditDialog(Number(data.standaloneIndex), data.title || data.taskTitle, data.reminderText, data.sendNotification || false)
                                    else
                                        overview.dialogs.openTaskReminderEditDialog(Number(data.tabIndex), Number(data.taskIndex), data.reminderText, data.sendNotification || false)
                                }
                            }
                            Button {
                                objectName: "clearReminder_" + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                text: "Clear"
                                onClicked: {
                                    var data = reminderRow.modelData
                                    var host = overview.windowRoot
                                    var manager = overview.projectManager
                                    if (data.kind === "mindmap")
                                        manager.clearMindmapReminder(data.nodeId)
                                    else if (data.kind === "standalone")
                                        manager.clearStandaloneReminder(Number(data.standaloneIndex))
                                    else
                                        manager.clearReminder(Number(data.tabIndex), Number(data.taskIndex))
                                    host.refreshActiveReminders()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
