import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: toolbar
    property var root: null
    property var diagramModel: null
    property var viewport: null

    Layout.fillWidth: true
    implicitHeight: 64
    radius: 12
    color: "#14202a"
    border.color: "#2b3f52"
    border.width: 1

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: "#ffffff"
        opacity: 0.02
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 12

        ColumnLayout {
            spacing: 1
            Layout.alignment: Qt.AlignVCenter

            Label {
                text: "ActionDraw"
                color: "#f4f8fc"
                font.pixelSize: 19
                font.bold: true
            }

            Label {
                text: "Map work visually"
                color: "#7f95aa"
                font.pixelSize: 10
            }
        }

        Rectangle {
            width: 1
            height: 34
            color: "#33485d"
            Layout.alignment: Qt.AlignVCenter
        }

        Button {
            id: drawModeButton
            text: diagramModel && diagramModel.drawingMode ? "\u270f Drawing On" : "\u270f Draw"
            highlighted: !!(diagramModel && diagramModel.drawingMode)
            flat: true
            padding: 10
            contentItem: Text {
                text: drawModeButton.text
                color: drawModeButton.highlighted ? "#f0fbff" : "#d6e2ee"
                font.pixelSize: 12
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 8
                color: drawModeButton.highlighted ? "#2d7ab3" : (drawModeButton.hovered ? "#26394b" : "#1c2e3e")
                border.color: drawModeButton.highlighted ? "#4eb3ff" : "#355069"
                border.width: 1
            }
            onClicked: {
                if (diagramModel)
                    diagramModel.setDrawingMode(!diagramModel.drawingMode)
            }
        }

        Button {
            id: colorPickerButton
            text: ""
            enabled: diagramModel ? true : false
            implicitWidth: 34
            implicitHeight: 34
            background: Rectangle {
                radius: 8
                color: "#112131"
                border.color: "#3b566f"
                border.width: 1

                Rectangle {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    radius: 9
                    color: diagramModel ? diagramModel.brushColor : "#ffffff"
                    border.color: "#0c1720"
                    border.width: 1
                }
            }
            onClicked: colorMenu.open()

            Menu {
                id: colorMenu
                parent: colorPickerButton
                y: colorPickerButton.height

                MenuItem {
                    text: "White"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ffffff" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#ffffff")
                }
                MenuItem {
                    text: "Red"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff5555" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#ff5555")
                }
                MenuItem {
                    text: "Orange"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff9944" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#ff9944")
                }
                MenuItem {
                    text: "Yellow"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ffee55" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#ffee55")
                }
                MenuItem {
                    text: "Green"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#55ff55" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#55ff55")
                }
                MenuItem {
                    text: "Cyan"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#55ffff" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#55ffff")
                }
                MenuItem {
                    text: "Blue"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#5588ff" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#5588ff")
                }
                MenuItem {
                    text: "Purple"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#aa55ff" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#aa55ff")
                }
                MenuItem {
                    text: "Pink"
                    Rectangle { anchors.right: parent.right; anchors.rightMargin: 8; anchors.verticalCenter: parent.verticalCenter; width: 16; height: 16; radius: 8; color: "#ff55aa" }
                    onTriggered: diagramModel && diagramModel.setBrushColor("#ff55aa")
                }
            }
        }

        RowLayout {
            spacing: 6
            Layout.alignment: Qt.AlignVCenter

            Label {
                text: "Brush"
                color: "#9ab0c4"
                font.pixelSize: 11
            }

            Slider {
                id: brushSizeSlider
                Layout.preferredWidth: 96
                from: 1
                to: 20
                stepSize: 1
                value: diagramModel ? diagramModel.brushWidth : 3
                onValueChanged: {
                    if (diagramModel && Math.abs(diagramModel.brushWidth - value) > 0.1)
                        diagramModel.setBrushWidth(value)
                }
            }

            Rectangle {
                radius: 6
                color: "#1a2d3d"
                border.color: "#395268"
                border.width: 1
                implicitWidth: 30
                implicitHeight: 22

                Label {
                    anchors.centerIn: parent
                    text: Math.round(brushSizeSlider.value)
                    color: "#dbe8f4"
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        Item { Layout.fillWidth: true }

        Rectangle {
            radius: 10
            color: "#10202c"
            border.color: "#2f4c63"
            border.width: 1
            Layout.alignment: Qt.AlignVCenter

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                Label {
                    text: "Zoom"
                    color: "#d8e5f1"
                    font.pixelSize: 11
                }

                Button {
                    text: "-"
                    flat: true
                    padding: 6
                    onClicked: root.applyZoomFactor(0.9, viewport.width / 2, viewport.height / 2)
                }

                Slider {
                    id: zoomSlider
                    Layout.preferredWidth: 160
                    from: root.minZoom
                    to: root.maxZoom
                    stepSize: 0.01
                    value: root.zoomLevel
                    onValueChanged: {
                        if (Math.abs(root.zoomLevel - value) > 0.0001) {
                            root.setZoomDirect(value, viewport.width / 2, viewport.height / 2)
                        }
                    }
                }

                Button {
                    text: "+"
                    flat: true
                    padding: 6
                    onClicked: root.applyZoomFactor(1.1, viewport.width / 2, viewport.height / 2)
                }

                Button {
                    text: "Reset"
                    flat: true
                    padding: 8
                    onClicked: root.resetView()
                }
            }
        }
    }
}
