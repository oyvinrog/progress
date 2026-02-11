"""QML source for the markdown note editor window."""

MARKDOWN_NOTE_QML = r"""
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: editorRoot
    visible: false
    width: 760
    height: 520
    minimumWidth: 680
    minimumHeight: 420
    color: "#111826"
    title: noteTitle

    property string noteId: ""
    property string noteTitle: "Markdown Note"
    property string noteText: ""

    signal saveRequested(string noteId, string text)
    signal cancelRequested()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        Label {
            text: editorRoot.noteTitle
            color: "#e2e8f0"
            font.pixelSize: 16
            font.bold: true
        }

        SplitView {
            id: noteSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal

            TextArea {
                id: editor
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.minimumWidth: 280
                SplitView.preferredWidth: Math.max(320, (noteSplit.width - 10) / 2)
                text: editorRoot.noteText
                wrapMode: TextArea.Wrap
                color: "#f8fafc"
                selectionColor: "#60a5fa"
                background: Rectangle {
                    color: "#0b1220"
                    radius: 8
                    border.color: "#2b3646"
                }
            }

            Rectangle {
                SplitView.fillWidth: true
                SplitView.fillHeight: true
                SplitView.minimumWidth: 280
                SplitView.preferredWidth: Math.max(320, (noteSplit.width - 10) / 2)
                color: "#0b1220"
                radius: 8
                border.color: "#2b3646"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Label {
                        text: "Preview"
                        color: "#cbd5f5"
                        font.pixelSize: 12
                        font.bold: true
                    }

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        Text {
                            width: parent.width
                            text: editor.text
                            textFormat: Text.MarkdownText
                            wrapMode: Text.WordWrap
                            color: "#e2e8f0"
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 8

            Button {
                text: "Cancel"
                onClicked: editorRoot.cancelRequested()
            }

            Button {
                text: "Save"
                onClicked: {
                    editorRoot.noteText = editor.text
                    editorRoot.saveRequested(editorRoot.noteId, editor.text)
                }
            }
        }
    }

    onVisibleChanged: {
        if (visible) {
            editor.forceActiveFocus()
        }
    }

    onNoteTextChanged: {
        if (editor.text !== noteText) {
            editor.text = noteText
        }
    }

    onClosing: function(close) {
        close.accepted = true
        editorRoot.cancelRequested()
    }
}
"""
