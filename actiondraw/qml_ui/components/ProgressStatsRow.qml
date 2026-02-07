import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    id: progressStats
    property var root
    property var taskModel
    property var diagramModel

    spacing: 12
    Layout.fillWidth: true
    visible: taskModel !== null

    Rectangle {
        visible: taskModel !== null
        Layout.minimumWidth: progressStatsRow.implicitWidth + 28
        Layout.maximumWidth: 480
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            id: progressStatsRow
            anchors.centerIn: parent
            spacing: 10

            Label {
                property real percentage: taskModel ? taskModel.percentageComplete : 0
                text: percentage.toFixed(0) + "%"
                font.pixelSize: 16
                font.bold: true
                color: "#67b8ff"
            }

            Label {
                text: "complete"
                color: "#86a0b6"
                font.pixelSize: 11
            }

            Label {
                property int activeIdx: diagramModel ? diagramModel.currentTaskIndex : -1
                property string activeTask: (activeIdx >= 0 && taskModel) ? taskModel.getTaskTitle(activeIdx) : ""
                visible: activeTask !== ""
                text: "\u00b7 " + activeTask
                font.pixelSize: 12
                color: "#8fd8b1"
                elide: Text.ElideRight
                Layout.maximumWidth: 250
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: 120
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            anchors.centerIn: parent
            spacing: 6

            Label {
                property real totalTime: taskModel ? taskModel.totalEstimatedTime : 0
                text: root.formatTime(totalTime)
                font.pixelSize: 13
                font.bold: true
                color: "#ffbf72"
            }

            Label {
                text: "left"
                font.pixelSize: 11
                color: "#8da6bc"
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: 138
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            anchors.centerIn: parent
            spacing: 6

            Label {
                text: "ETA"
                font.pixelSize: 11
                color: "#8da6bc"
            }

            Label {
                property string completionTime: taskModel ? taskModel.estimatedCompletionTimeOfDay : ""
                text: completionTime !== "" ? completionTime : "N/A"
                font.pixelSize: 13
                font.bold: true
                color: "#8fd8b1"
            }
        }
    }

    Item { Layout.fillWidth: true }
}
