import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "components"

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

        MarkdownEditorPane {
            id: markdownEditor
            Layout.fillWidth: true
            Layout.fillHeight: true
            placeholderText: "Write your note here..."
            allowCreateTask: true
            sourceItemId: editorRoot.noteId
            textValue: editorRoot.noteText
            onTextValueChanged: editorRoot.noteText = textValue
            onCreateTaskRequested: function(selectedText) {
                if (editorRoot.noteId.length === 0)
                    return
                if (markdownNoteManager && markdownNoteManager.createTaskFromNoteSelection) {
                    markdownNoteManager.createTaskFromNoteSelection(editorRoot.noteId, selectedText)
                    return
                }
                if (diagramModel && diagramModel.createTaskFromMarkdownSelection)
                    diagramModel.createTaskFromMarkdownSelection(editorRoot.noteId, selectedText)
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
                onClicked: editorRoot.saveRequested(editorRoot.noteId, markdownEditor.textValue)
            }
        }
    }

    onVisibleChanged: {
        if (visible)
            markdownEditor.focusEditor()
    }

    onNoteTextChanged: {
        if (markdownEditor.textValue !== noteText)
            markdownEditor.textValue = noteText
    }

    onClosing: function(close) {
        close.accepted = true
        editorRoot.cancelRequested()
    }
}
