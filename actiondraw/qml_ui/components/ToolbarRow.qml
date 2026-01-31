import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    id: toolbar
    property var root: null
    property var diagramModel: null
    property var viewport: null

    Layout.fillWidth: true
    spacing: 12

    Label {
        text: "ActionDraw"
        color: "#f5f6f8"
        font.pixelSize: 20
    }

    Rectangle {
        width: 1
        height: 24
        color: "#3b485c"
    }

    Button {
        id: drawModeButton
        text: diagramModel && diagramModel.drawingMode ? "\u270f Drawing" : "\u270f Draw"
        highlighted: !!(diagramModel && diagramModel.drawingMode)
        onClicked: {
            if (diagramModel)
                diagramModel.setDrawingMode(!diagramModel.drawingMode)
        }
    }

    Button {
        id: colorPickerButton
        text: ""
        enabled: diagramModel ? true : false
        implicitWidth: 32
        implicitHeight: 32
        background: Rectangle {
            color: diagramModel ? diagramModel.brushColor : "#ffffff"
            border.color: "#5b6878"
            border.width: 2
            radius: 4
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
        spacing: 4

        Label {
            text: "Size:"
            color: "#a8b8c8"
        }

        Slider {
            id: brushSizeSlider
            Layout.preferredWidth: 80
            from: 1
            to: 20
            stepSize: 1
            value: diagramModel ? diagramModel.brushWidth : 3
            onValueChanged: {
                if (diagramModel && Math.abs(diagramModel.brushWidth - value) > 0.1)
                    diagramModel.setBrushWidth(value)
            }
        }

        Label {
            text: Math.round(brushSizeSlider.value)
            color: "#f5f6f8"
            Layout.preferredWidth: 20
        }
    }

    Item { Layout.fillWidth: true }

    RowLayout {
        spacing: 6
        Layout.alignment: Qt.AlignVCenter

        Label {
            text: "Zoom"
            color: "#f5f6f8"
        }

        Button {
            text: "-"
            onClicked: root.applyZoomFactor(0.9, viewport.width / 2, viewport.height / 2)
        }

        Slider {
            id: zoomSlider
            Layout.preferredWidth: 140
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
            onClicked: root.applyZoomFactor(1.1, viewport.width / 2, viewport.height / 2)
        }

        Button {
            text: "Reset"
            onClicked: root.resetView()
        }
    }
}
