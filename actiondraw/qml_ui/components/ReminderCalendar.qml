import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: calendar
    objectName: "reminderCalendar"
    property var dayCounts: ({})
    property double nowTimestamp: Date.now() / 1000
    property string selectedDate: ""
    property int displayedYear: new Date().getFullYear()
    property int displayedMonth: new Date().getMonth()
    readonly property string todayKey: dateKey(new Date(nowTimestamp * 1000))
    readonly property var calendarDays: {
        var offset = (new Date(displayedYear, displayedMonth, 1).getDay() + 6) % 7
        var cells = []
        for (var i = 0; i < 42; ++i) {
            var date = new Date(displayedYear, displayedMonth, 1 - offset + i)
            cells.push({key: dateKey(date), day: date.getDate(), inMonth: date.getMonth() === displayedMonth})
        }
        return cells
    }
    signal dateSelected(string date)

    function dateKey(date) {
        return date.getFullYear() + "-" + ("0" + (date.getMonth() + 1)).slice(-2) + "-" + ("0" + date.getDate()).slice(-2)
    }
    function changeMonth(offset) {
        var date = new Date(displayedYear, displayedMonth + offset, 1)
        displayedYear = date.getFullYear()
        displayedMonth = date.getMonth()
    }
    function showToday() {
        var date = new Date(nowTimestamp * 1000)
        displayedYear = date.getFullYear()
        displayedMonth = date.getMonth()
    }

    implicitHeight: calendarColumn.implicitHeight + 12
    implicitWidth: 320
    color: "#21313d"
    border.color: "#3b566a"
    radius: 8

    ColumnLayout {
        id: calendarColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 6
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            Button {
                objectName: "reminderPreviousMonth"
                text: "‹"
                implicitWidth: 32
                Accessible.name: "Previous month"
                onClicked: calendar.changeMonth(-1)
            }
            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: Qt.formatDate(new Date(calendar.displayedYear, calendar.displayedMonth, 1), "MMMM yyyy")
                color: "#fff7ef"
                font.bold: true
            }
            Button {
                objectName: "reminderNextMonth"
                text: "›"
                implicitWidth: 32
                Accessible.name: "Next month"
                onClicked: calendar.changeMonth(1)
            }
        }
        RowLayout {
            Button {
                objectName: "reminderToday"
                text: "Today"
                onClicked: calendar.showToday()
            }
            Button {
                objectName: "reminderAllDays"
                text: "All days"
                highlighted: calendar.selectedDate === ""
                onClicked: calendar.dateSelected("")
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 7
            columnSpacing: 2
            rowSpacing: 2
            Repeater {
                model: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                delegate: Label {
                    required property string modelData
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: modelData
                    color: "#f1c892"
                    font.pixelSize: 10
                }
            }
            Repeater {
                model: calendar.calendarDays
                delegate: Button {
                    id: dayButton
                    required property var modelData
                    readonly property int reminderCount: calendar.dayCounts[modelData.key] || 0
                    objectName: "reminderDay_" + modelData.key
                    Layout.fillWidth: true
                    Layout.preferredWidth: 40
                    Layout.preferredHeight: 32
                    highlighted: calendar.selectedDate === modelData.key
                    Accessible.name: modelData.key + ", " + reminderCount + " reminders"
                    onClicked: calendar.dateSelected(modelData.key)
                    background: Rectangle {
                        radius: 4
                        color: dayButton.highlighted ? "#8d6948" : dayButton.down ? "#3b566a" : "#2b3d4a"
                        border.width: dayButton.modelData.key === calendar.todayKey || dayButton.highlighted ? 2 : 1
                        border.color: dayButton.modelData.key === calendar.todayKey ? "#ffe3a8" : dayButton.highlighted ? "#f1c892" : "#3b566a"
                    }
                    contentItem: Item {
                        Row {
                            anchors.centerIn: parent
                            spacing: 2
                            Text {
                                text: dayButton.modelData.day
                                color: dayButton.modelData.key === calendar.todayKey ? "#ffe3a8" : "#fff7ef"
                                opacity: dayButton.modelData.inMonth ? 1 : 0.45
                                font.bold: dayButton.modelData.key === calendar.todayKey
                                font.pixelSize: 11
                        }
                        Rectangle {
                            visible: dayButton.reminderCount > 0
                            width: countLabel.implicitWidth + 6
                            height: 15
                            radius: 7
                            color: "#8d6948"
                            Text {
                                id: countLabel
                                anchors.centerIn: parent
                                text: dayButton.reminderCount
                                color: "#fff7ef"
                                font.pixelSize: 10
                            }
                        }
                      }
                    }
                }
            }
        }
    }
}
