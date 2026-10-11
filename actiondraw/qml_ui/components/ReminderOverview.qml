import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Column {
    id: overview
    objectName: "reminderOverview"
    property var windowRoot
    property var projectManager
    property var dialogs
    property var planController
    property double nowTimestamp: Date.now() / 1000
    property string selectedDate: ""
    readonly property var futureReminders: {
        var entries = windowRoot ? windowRoot.activeReminders : []
        return entries.filter(function(entry) { return Number(entry.reminderAt) > overview.nowTimestamp })
    }
    readonly property var dayCounts: {
        var counts = {}
        futureReminders.forEach(function(entry) {
            var key = calendar.dateKey(new Date(Number(entry.reminderAt) * 1000))
            counts[key] = (counts[key] || 0) + 1
        })
        return counts
    }
    readonly property var filteredReminders: futureReminders.filter(function(entry) {
        return !overview.selectedDate || calendar.dateKey(new Date(Number(entry.reminderAt) * 1000)) === overview.selectedDate
    })
    Connections {
        target: overview.windowRoot
        function onActiveRemindersChanged() { overview.nowTimestamp = Date.now() / 1000 }
    }
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
                text: "Waiting Reminders · " + overview.futureReminders.length + " pending"
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
                onClicked: overview.dialogs.openStandaloneReminderDialog(overview.selectedDate)
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

    GridLayout {
        id: calendarContent
        objectName: "reminderCalendarContent"
        width: overview.width
        columns: width >= 800 ? 2 : 1
        columnSpacing: 10
        rowSpacing: 6
        visible: !!overview.windowRoot && overview.windowRoot.reminderOverviewExpanded

        ReminderCalendar {
            id: calendar
            Layout.preferredWidth: 320
            Layout.fillWidth: calendarContent.columns === 1
            Layout.alignment: Qt.AlignTop
            dayCounts: overview.dayCounts
            nowTimestamp: overview.nowTimestamp
            selectedDate: overview.selectedDate
            onDateSelected: function(date) { overview.selectedDate = date }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignTop
            Label {
                visible: overview.selectedDate !== ""
                text: "Reminders for " + overview.selectedDate
                color: "#ffe4c7"
            }
            Label {
                objectName: "reminderEmptyDay"
                visible: overview.filteredReminders.length === 0
                text: overview.selectedDate ? "No reminders for this day" : "No waiting reminders"
                color: "#f1c892"
            }
            ScrollView {
                id: reminderList
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(reminderRows.implicitHeight, 180)
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                visible: overview.filteredReminders.length > 0

                Column {
                    id: reminderRows
                    width: reminderList.availableWidth
                    spacing: 6

                    Repeater {
                        model: overview.filteredReminders
                        delegate: Rectangle {
                            id: reminderRow
                            required property var modelData
                            readonly property bool isPlan: modelData.kind === "kanban_schedule"
                            objectName: "reminderRow_" + (isPlan ? "plan_" : "") + (modelData.nodeId || modelData.kind)
                            width: reminderRows.width
                            height: rowContent.implicitHeight + 12
                            radius: 6
                            color: "#2e261f"
                            border.color: "#8d6948"

                            Menu {
                                id: rescheduleMenu
                                objectName: "reschedulePlanMenu_" + reminderRow.modelData.nodeId
                                Repeater {
                                    model: overview.planController ? overview.planController.planWeekdayOptions : []
                                    delegate: MenuItem {
                                        required property var modelData
                                        objectName: "reschedulePlanWeekday_" + reminderRow.modelData.nodeId + "_" + modelData.weekday
                                        text: modelData.label
                                        onTriggered: overview.planController.scheduleNodeToWeekday(
                                            reminderRow.modelData.nodeId, modelData.weekday)
                                    }
                                }
                            }

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
                                        text: (reminderRow.isPlan ? "Add and notify at " : "Remind at ") + reminderRow.modelData.reminderText
                                        color: "#f1c892"
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                }
                                RowLayout {
                                    spacing: 6
                                    Button {
                                        objectName: "openReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                        text: reminderRow.isPlan || reminderRow.modelData.kind === "mindmap" ? "Open Node" : "Open Task"
                                        visible: reminderRow.modelData.kind !== "standalone"
                                        onClicked: {
                                            var data = reminderRow.modelData
                                            if (reminderRow.isPlan || data.kind === "mindmap")
                                                overview.projectManager.openMindmapReminder(data.nodeId)
                                            else
                                                overview.projectManager.openTabTask(Number(data.tabIndex), Number(data.taskIndex))
                                        }
                                    }
                                    Button {
                                        objectName: "editReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                        text: reminderRow.isPlan ? "Reschedule" : "Edit"
                                        onClicked: {
                                            var data = reminderRow.modelData
                                            if (reminderRow.isPlan)
                                                rescheduleMenu.popup()
                                            else if (data.kind === "mindmap")
                                                overview.dialogs.openMindmapReminderDialog(data.nodeId, data.reminderText, data.sendNotification)
                                            else if (data.kind === "standalone")
                                                overview.dialogs.openStandaloneReminderEditDialog(Number(data.standaloneIndex), data.title || data.taskTitle, data.reminderText, data.sendNotification || false)
                                            else
                                                overview.dialogs.openTaskReminderEditDialog(Number(data.tabIndex), Number(data.taskIndex), data.reminderText, data.sendNotification || false)
                                        }
                                    }
                                    Button {
                                        objectName: "clearReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.modelData.nodeId || reminderRow.modelData.kind)
                                        text: reminderRow.isPlan ? "Cancel" : "Clear"
                                        onClicked: {
                                            var data = reminderRow.modelData
                                            var host = overview.windowRoot
                                            var manager = overview.projectManager
                                            if (reminderRow.isPlan)
                                                overview.planController.cancelPlanSchedule(data.nodeId)
                                            else if (data.kind === "mindmap")
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
    }
}
