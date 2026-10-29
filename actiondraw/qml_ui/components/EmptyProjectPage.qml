import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: page
    objectName: "emptyProjectPage"
    color: "#090f15"
    signal addGoalRequested()
    property string recentProjectPath: ""
    signal openRecentProjectRequested(string filePath)
    readonly property bool actionFocused: addGoalButton.activeFocus || openRecentButton.activeFocus

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(540, Math.max(0, parent.width - 64))
        spacing: 22

        Label {
            Layout.fillWidth: true
            text: "What would you like to achieve?"
            color: "#edf3f8"
            font.pixelSize: page.width < 600 ? 28 : 36
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
        Label {
            Layout.fillWidth: true
            text: "Start by adding a goal. Then break it into smaller steps and organize your ideas in a mind map."
            color: "#a6b5c4"
            font.pixelSize: 16
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            lineHeight: 1.3
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
            spacing: 12
            Button {
                id: addGoalButton
                objectName: "emptyProjectAddGoal"
                implicitWidth: 148
                implicitHeight: 46
                text: "Add goal"
                focusPolicy: Qt.StrongFocus
                onClicked: page.addGoalRequested()
                contentItem: Text {
                    text: addGoalButton.text
                    color: "#09121c"
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 7
                    color: addGoalButton.down ? "#65a4dc" : addGoalButton.hovered ? "#a3d2ff" : "#85c1f5"
                    border.width: addGoalButton.activeFocus ? 2 : 0
                    border.color: "#ffffff"
                }
            }
            Button {
                id: openRecentButton
                objectName: "emptyProjectOpenRecent"
                visible: page.recentProjectPath.length > 0
                implicitWidth: 192
                implicitHeight: 46
                text: "Open recent project"
                focusPolicy: Qt.StrongFocus
                onClicked: page.openRecentProjectRequested(page.recentProjectPath)
                ToolTip.visible: hovered || activeFocus
                ToolTip.text: page.recentProjectPath
                ToolTip.delay: 500
                contentItem: Text {
                    text: openRecentButton.text
                    color: "#edf3f8"
                    font.pixelSize: 15
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 7
                    color: openRecentButton.down ? "#29465d" : openRecentButton.hovered ? "#243c50" : "#182b3b"
                    border.width: openRecentButton.activeFocus ? 2 : 1
                    border.color: openRecentButton.activeFocus ? "#ffffff" : "#49647b"
                }
            }
        }
        Label {
            Layout.fillWidth: true
            Layout.topMargin: 4
            text: "For example: Learn a language, Plan a renovation, or Launch a website."
            color: "#7e91a3"
            font.pixelSize: 13
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
    }
    onVisibleChanged: { if (visible) addGoalButton.forceActiveFocus() }
    Component.onCompleted: { if (visible) addGoalButton.forceActiveFocus() }
}
