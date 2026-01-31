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
        Layout.minimumWidth: progressStatsRow.implicitWidth + 16
        Layout.maximumWidth: 400
        height: 32
        radius: 6
        color: "#1b2028"
        border.color: "#2e3744"

        RowLayout {
            id: progressStatsRow
            anchors.centerIn: parent
            spacing: 8

            Label {
                property real percentage: taskModel ? taskModel.percentageComplete : 0
                text: percentage.toFixed(0) + "%"
                font.pixelSize: 14
                font.bold: true
                color: "#4a9eff"
            }

            Label {
                property int activeIdx: diagramModel ? diagramModel.currentTaskIndex : -1
                property string activeTask: (activeIdx >= 0 && taskModel) ? taskModel.getTaskTitle(activeIdx) : ""
                visible: activeTask !== ""
                text: "\u00b7 " + activeTask
                font.pixelSize: 12
                color: "#82c3a5"
                elide: Text.ElideRight
                Layout.maximumWidth: 200
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: 70
        height: 32
        radius: 6
        color: "#1b2028"
        border.color: "#2e3744"

        RowLayout {
            anchors.centerIn: parent
            spacing: 4

            Label {
                property real totalTime: taskModel ? taskModel.totalEstimatedTime : 0
                text: root.formatTime(totalTime)
                font.pixelSize: 12
                font.bold: true
                color: "#ffa94d"
            }

            Label {
                text: "left"
                font.pixelSize: 10
                color: "#8a93a5"
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: 70
        height: 32
        radius: 6
        color: "#1b2028"
        border.color: "#2e3744"

        RowLayout {
            anchors.centerIn: parent
            spacing: 4

            Label {
                property string completionTime: taskModel ? taskModel.estimatedCompletionTimeOfDay : ""
                text: completionTime !== "" ? completionTime : "N/A"
                font.pixelSize: 12
                font.bold: true
                color: "#82c3a5"
            }
        }
    }

    Item { Layout.fillWidth: true }
}
