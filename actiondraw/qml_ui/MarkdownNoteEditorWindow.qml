import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
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
    property string editorType: "note"
    property real targetX: 0
    property real targetY: 0
    property bool fullWindowMode: false

    signal saveRequested(string noteId, string text)
    signal cancelRequested()

    function setFullWindowMode(enabled) {
        fullWindowMode = enabled
        visibility = enabled ? Window.Maximized : Window.Windowed
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10

        RowLayout {
            Layout.fillWidth: true

            Label {
                text: editorRoot.noteTitle
                color: "#e2e8f0"
                font.pixelSize: 16
                font.bold: true
            }

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: editorRoot.fullWindowMode ? "Exit Full Window" : "Full Window"
                onClicked: editorRoot.setFullWindowMode(!editorRoot.fullWindowMode)
            }
        }

        MarkdownEditorPane {
            id: markdownEditor
            Layout.fillWidth: true
            Layout.fillHeight: true
            placeholderText: editorRoot.editorType === "freetext" ? "Write your text here..." : "Write your note here..."
            allowCreateTask: true
            previewVisible: !editorRoot.fullWindowMode
            sourceItemId: editorRoot.noteId
            textValue: editorRoot.noteText
            onTextValueChanged: editorRoot.noteText = textValue
            onCreateTaskRequested: function(selectedText) {
                if (markdownNoteManager && markdownNoteManager.createTaskFromEditorSelection) {
                    markdownNoteManager.createTaskFromEditorSelection(
                        editorRoot.editorType,
                        editorRoot.noteId,
                        editorRoot.targetX,
                        editorRoot.targetY,
                        markdownEditor.textValue,
                        selectedText
                    )
                    if (editorRoot.noteId.length === 0
                        && editorRoot.editorType === "freetext"
                        && markdownNoteManager.activeItemId
                        && markdownNoteManager.activeItemId.length > 0) {
                        editorRoot.noteId = markdownNoteManager.activeItemId
                    }
                    return
                }
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
            visible: !editorRoot.fullWindowMode

            Button {
                text: "Cancel"
                onClicked: editorRoot.cancelRequested()
            }

            Button {
                text: "Save"
                onClicked: editorRoot.saveRequested(
                    editorRoot.noteId,
                    markdownImagePaster
                        ? markdownImagePaster.expandMarkdownImages(markdownEditor.textValue)
                        : markdownEditor.textValue
                )
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

    Shortcut {
        sequence: "F11"
        onActivated: editorRoot.setFullWindowMode(!editorRoot.fullWindowMode)
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveRequested(
            editorRoot.noteId,
            markdownImagePaster
                ? markdownImagePaster.expandMarkdownImages(markdownEditor.textValue)
                : markdownEditor.textValue
        )
    }

    Shortcut {
        sequence: "Ctrl+Enter"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveRequested(
            editorRoot.noteId,
            markdownImagePaster
                ? markdownImagePaster.expandMarkdownImages(markdownEditor.textValue)
                : markdownEditor.textValue
        )
    }

    onClosing: function(close) {
        close.accepted = true
        editorRoot.fullWindowMode = false
        editorRoot.visibility = Window.Windowed
        editorRoot.cancelRequested()
    }
}
