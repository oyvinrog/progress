import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    id: progressStats
    property var root
    property var taskModel
    property var diagramModel
    property bool compact: false

    spacing: compact ? 8 : 12
    visible: taskModel !== null
    Layout.fillWidth: !compact
    Layout.alignment: Qt.AlignRight | Qt.AlignVCenter

    Rectangle {
        visible: taskModel !== null
        Layout.minimumWidth: compact ? 0 : progressStatsRow.implicitWidth + 28
        Layout.maximumWidth: compact ? 360 : 480
        Layout.preferredWidth: compact ? Math.min(progressStatsRow.implicitWidth + 20, 360) : -1
        Layout.fillWidth: compact
        height: compact ? 34 : 44
        radius: compact ? 8 : 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            id: progressStatsRow
            anchors.centerIn: parent
            spacing: compact ? 8 : 10

            Label {
                property real percentage: taskModel ? taskModel.percentageComplete : 0
                text: percentage.toFixed(0) + "%"
                font.pixelSize: compact ? 14 : 16
                font.bold: true
                color: "#67b8ff"
            }

            Label {
                text: "complete"
                color: "#86a0b6"
                font.pixelSize: compact ? 10 : 11
            }

            Label {
                property int activeIdx: diagramModel ? diagramModel.currentTaskIndex : -1
                property string activeTask: (activeIdx >= 0 && taskModel) ? taskModel.getTaskTitle(activeIdx) : ""
                visible: activeTask !== ""
                text: "\u00b7 " + activeTask
                font.pixelSize: compact ? 11 : 12
                color: "#8fd8b1"
                elide: Text.ElideRight
                Layout.maximumWidth: compact ? 120 : 250
                Layout.fillWidth: compact
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: compact ? 106 : 120
        height: compact ? 34 : 44
        radius: compact ? 8 : 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            anchors.centerIn: parent
            spacing: compact ? 5 : 6

            Label {
                property real totalTime: taskModel ? taskModel.totalEstimatedTime : 0
                text: root.formatTime(totalTime)
                font.pixelSize: compact ? 12 : 13
                font.bold: true
                color: "#ffbf72"
            }

            Label {
                text: "left"
                font.pixelSize: compact ? 10 : 11
                color: "#8da6bc"
            }
        }
    }

    Rectangle {
        visible: taskModel !== null
        width: compact ? 122 : 138
        height: compact ? 34 : 44
        radius: compact ? 8 : 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            anchors.centerIn: parent
            spacing: compact ? 5 : 6

            Label {
                text: "ETA"
                font.pixelSize: compact ? 10 : 11
                color: "#8da6bc"
            }

            Label {
                property string completionTime: taskModel ? taskModel.estimatedCompletionTimeOfDay : ""
                text: completionTime !== "" ? completionTime : "N/A"
                font.pixelSize: compact ? 12 : 13
                font.bold: true
                color: "#8fd8b1"
            }
        }
    }

    Item {
        visible: !compact
        Layout.fillWidth: true
    }
}
