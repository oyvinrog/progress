"""Markdown note editor window for ActionDraw."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtQml import QQmlApplicationEngine


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


class MarkdownNoteEditor(QObject):
    """Standalone window for editing markdown notes."""

    noteSaved = Signal(str, str)
    noteCanceled = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._engine = QQmlApplicationEngine()
        self._engine.loadData(MARKDOWN_NOTE_QML.encode("utf-8"))
        roots = self._engine.rootObjects()
        if not roots:
            raise RuntimeError("Failed to load markdown note editor QML.")
        self._root = roots[0]
        self._root.saveRequested.connect(self._handle_save)
        self._root.cancelRequested.connect(self._handle_cancel)

    def open(self, note_id: str, note_text: str, note_title: str) -> None:
        self._root.setProperty("noteId", note_id)
        self._root.setProperty("noteText", note_text)
        self._root.setProperty("noteTitle", note_title)
        self._root.show()
        self._root.raise_()
        self._root.requestActivate()

    def _handle_save(self, note_id: str, note_text: str) -> None:
        self._root.hide()
        self.noteSaved.emit(note_id, note_text)

    def _handle_cancel(self) -> None:
        note_id = self._root.property("noteId")
        self._root.hide()
        self.noteCanceled.emit(note_id)


class MarkdownNoteManager(QObject):
    """Open markdown notes tied to diagram items."""

    def __init__(self, diagram_model) -> None:
        super().__init__()
        self._diagram_model = diagram_model
        self._editor = MarkdownNoteEditor()
        self._editor.noteSaved.connect(self._save_note)

    @Slot(str)
    def openNote(self, item_id: str) -> None:
        item = self._diagram_model.getItem(item_id)
        if not item:
            return
        title_text = item.text.strip()
        title = f"{title_text} Note" if title_text else f"{item.item_type.value.title()} Note"
        self._editor.open(item_id, item.note_markdown, title)

    def _save_note(self, item_id: str, note_text: str) -> None:
        self._diagram_model.setItemMarkdown(item_id, note_text)
