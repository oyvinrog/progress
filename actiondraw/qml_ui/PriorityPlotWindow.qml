import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "components"

Window {
    id: root
    width: 980
    height: 640
    visible: true
    title: "Priority Plot"
    color: "#0a141d"

    property var tabModel: null
    property var tabModelRef: tabModel

    Rectangle {
        anchors.fill: parent
        z: -2
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0c1a26" }
            GradientStop { position: 1.0; color: "#122336" }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 10

        Rectangle {
            Layout.fillWidth: true
            height: 72
            radius: 10
            color: "#112638"
            border.color: "#2f5875"
            border.width: 1

            Column {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.topMargin: 10
                spacing: 4

                Text {
                    text: "Priority Plot"
                    color: "#ecf6ff"
                    font.pixelSize: 18
                    font.bold: true
                }

                Text {
                    text: "Score = subjective value / ln(time hours). Drag points and release to update tab priority ordering."
                    color: "#9ec6e2"
                    font.pixelSize: 12
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            PriorityPlotCanvas {
                Layout.fillWidth: true
                Layout.fillHeight: true
                tabModel: root.tabModelRef
            }

            Rectangle {
                Layout.preferredWidth: 280
                Layout.fillHeight: true
                radius: 12
                color: "#0f2030"
                border.color: "#2a4e68"
                border.width: 1

                Column {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "Tab Scores"
                        color: "#d9efff"
                        font.pixelSize: 14
                        font.bold: true
                    }

                    Repeater {
                        model: root.tabModelRef

                        delegate: Rectangle {
                            width: parent.width
                            height: 52
                            radius: 8
                            color: index === 0 ? "#244e67" : "#173245"
                            border.color: "#3b6682"
                            border.width: 1

                            Column {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 1

                                Text {
                                    text: (index + 1) + ". " + model.name
                                    color: "#e7f4ff"
                                    font.pixelSize: 11
                                    font.bold: true
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                                Text {
                                    text: "Score " + (model.priorityScore || 0).toFixed(2)
                                          + " | t=" + (model.priorityTimeHours || 0).toFixed(2)
                                          + "h | v=" + (model.prioritySubjectiveValue || 0).toFixed(2)
                                    color: "#9fc6de"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
