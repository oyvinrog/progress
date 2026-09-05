import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Popup {
    id: root
    objectName: "nodeTextPreview"
    property string itemId: ""
    property string fullText: ""
    property bool richText: false
    width: Math.min(560, Math.max(0, parent.width - 24))
    height: Math.min(460, Math.max(0, parent.height - 24),
                     Math.max(160, textArea.implicitHeight + header.implicitHeight + 10 + padding * 2))
    x: (parent.width - width) / 2
    y: (parent.height - height) / 2
    padding: 16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    background: Rectangle {
        color: "#15222f"
        border.color: "#465e73"
        radius: 10
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 10
        RowLayout {
            id: header
            Layout.fillWidth: true
            Label { text: "Full text"; color: "#f1f7fb"; font.bold: true; Layout.fillWidth: true }
            Button {
                text: "Close"
                onClicked: root.close()
                contentItem: Text {
                    text: parent.text
                    color: "#f1f7fb"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: parent.hovered ? "#304b60" : "#24394a"
                    border.color: parent.activeFocus ? "#8cbddd" : "#465e73"
                    radius: 5
                }
            }
        }
        ScrollView {
            id: scroll
            objectName: "nodePreviewScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            TextArea {
                id: textArea
                objectName: "nodePreviewText"
                text: root.fullText
                textFormat: root.richText ? TextEdit.RichText : TextEdit.PlainText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: "#f1f7fb"
                selectionColor: "#365f80"
                font.pixelSize: 14
                background: null
            }
        }
    }
    onOpened: {
        scroll.contentItem.contentY = 0
        textArea.forceActiveFocus()
    }
    onClosed: { itemId = ""; fullText = "" }
}
