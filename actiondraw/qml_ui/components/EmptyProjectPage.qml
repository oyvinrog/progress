import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: page
    objectName: "emptyProjectPage"
    color: "#090f15"
    signal addGoalRequested()
    readonly property bool actionFocused: addGoalButton.activeFocus

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
        Button {
            id: addGoalButton
            objectName: "emptyProjectAddGoal"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
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
