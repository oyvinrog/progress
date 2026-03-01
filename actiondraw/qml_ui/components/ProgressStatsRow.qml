import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    id: progressStats
    property var root
    property var taskModel
    property var diagramModel
    property var projectManager
    signal openPouchShopRequested()

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

    Rectangle {
        visible: projectManager !== null
        width: 200
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            anchors.topMargin: 6
            anchors.bottomMargin: 6
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Label {
                    text: "Lv " + (projectManager ? projectManager.gamificationLevel : 1)
                    color: "#8fd8b1"
                    font.pixelSize: 12
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                    text: (projectManager ? projectManager.gamificationXpIntoLevel : 0)
                          + "/" + (projectManager ? projectManager.gamificationXpForNextLevel : 100)
                          + " XP"
                    color: "#9ec8e7"
                    font.pixelSize: 10
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 8
                radius: 4
                color: "#1b2b3a"

                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * (projectManager ? projectManager.gamificationLevelProgress : 0)
                    height: parent.height
                    radius: parent.radius
                    color: "#58a9ff"
                }
            }
        }
    }

    Rectangle {
        visible: projectManager !== null
        width: 200
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            anchors.topMargin: 6
            anchors.bottomMargin: 6
            spacing: 2

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Label {
                    text: (projectManager ? projectManager.gamificationCurrentStreakHours : 0) + "h streak"
                    color: "#ffbf72"
                    font.pixelSize: 12
                    font.bold: true
                }

                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignRight
                    text: (projectManager ? projectManager.gamificationHourlyCompletions : 0)
                          + "/" + (projectManager ? projectManager.gamificationHourlyGoalCompletions : 3)
                          + " hr-goal"
                    color: "#9ec8e7"
                    font.pixelSize: 10
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 8
                radius: 4
                color: "#1b2b3a"

                Rectangle {
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width * (projectManager ? projectManager.gamificationHourlyGoalProgress : 0)
                    height: parent.height
                    radius: parent.radius
                    color: "#ff9f55"
                }
            }
        }
    }

    Rectangle {
        visible: projectManager !== null
        width: 170
        height: 44
        radius: 10
        color: "#14202b"
        border.color: "#2c3f53"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 10
            spacing: 8

            Label {
                text: "\u25c9"
                color: "#ffd166"
                font.pixelSize: 16
                font.bold: true
            }

            Label {
                text: projectManager ? projectManager.gamificationCoins + " coins" : "0 coins"
                color: "#ffd166"
                font.pixelSize: 12
                font.bold: true
            }

            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignRight
                text: projectManager ? (projectManager.gamificationPouchCount + "/" + projectManager.gamificationPouchCapacity + " pouch") : "0/20 pouch"
                color: "#9ec8e7"
                font.pixelSize: 10
            }
        }
    }

    Button {
        visible: projectManager !== null
        text: "Pouch"
        implicitHeight: 44
        onClicked: progressStats.openPouchShopRequested()
    }

    Item { Layout.fillWidth: true }
}
