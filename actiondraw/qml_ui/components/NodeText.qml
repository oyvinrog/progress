import QtQuick 2.15
import QtQuick.Controls 2.15

// A clipped label with a stable, fully formatted measurement and an explicit
// way to read overflow. Measurement never depends on hover or selection.
Item {
    id: root
    objectName: "nodeText"
    property alias text: label.text
    property alias textFormat: label.textFormat
    property alias font: label.font
    property alias color: label.color
    property alias horizontalAlignment: label.horizontalAlignment
    property int verticalAlignment: Text.AlignVCenter
    property string measurementText: text
    property int measurementFormat: textFormat
    property color backgroundColor: "#263442"
    property real fittingWidth: -1
    readonly property real fullTextHeight: measure.contentHeight
    readonly property bool overflowing: measure.contentHeight > height + 0.5
        || measure.contentWidth > width + 0.5
        || label.contentHeight > height + 0.5 || label.contentWidth > width + 0.5
    signal readMore()

    function fittedSize(nodeWidth, nodeHeight) {
        var horizontalInset = nodeWidth - width
        var verticalInset = nodeHeight - height
        var maxWidth = Math.max(nodeWidth, 320)
        var maxHeight = Math.max(nodeHeight, 220)
        var candidateWidth = nodeWidth
        fittingWidth = Math.max(1, candidateWidth - horizontalInset)
        var neededHeight = measure.contentHeight + verticalInset
        // Use height at the existing width first. Widen only if that cannot
        // accommodate the text within the compact height limit.
        while (neededHeight > maxHeight && candidateWidth < maxWidth) {
            candidateWidth = Math.min(maxWidth, candidateWidth + 24)
            fittingWidth = Math.max(1, candidateWidth - horizontalInset)
            neededHeight = measure.contentHeight + verticalInset
        }
        fittingWidth = -1
        return Qt.size(candidateWidth, Math.max(nodeHeight, Math.min(maxHeight, Math.ceil(neededHeight))))
    }

    Text {
        id: measure
        visible: false
        width: Math.max(1, root.fittingWidth >= 0 ? root.fittingWidth : root.width)
        text: root.visible ? root.measurementText : ""
        textFormat: root.measurementFormat
        font: label.font
        wrapMode: Text.Wrap
    }

    Item {
        anchors.fill: parent
        anchors.bottomMargin: root.overflowing ? Math.min(24, root.height) : 0
        clip: true
        Text {
            id: label
            width: parent.width
            height: parent.height
            wrapMode: Text.Wrap
            verticalAlignment: root.overflowing ? Text.AlignTop : root.verticalAlignment
        }
        Rectangle {
            visible: root.overflowing
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: Math.min(12, parent.height)
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(root.backgroundColor.r, root.backgroundColor.g, root.backgroundColor.b, 0) }
                GradientStop { position: 1; color: root.backgroundColor }
            }
        }
    }
    Button {
        objectName: "nodeReadMore"
        visible: root.overflowing
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        width: Math.min(implicitWidth, Math.max(24, root.width))
        height: Math.min(24, Math.max(18, root.height))
        padding: 2
        text: "Read more"
        font.pixelSize: 11
        focusPolicy: Qt.StrongFocus
        Accessible.name: "Read full node text"
        contentItem: Text {
            text: parent.text
            font: parent.font
            color: root.color
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: root.backgroundColor
            radius: 3
            border.width: parent.activeFocus || parent.hovered ? 1 : 0
            border.color: root.color
        }
        onClicked: root.readMore()
    }
}
