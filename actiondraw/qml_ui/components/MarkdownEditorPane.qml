import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property string textValue: ""
    property string placeholderText: ""

    function focusEditor() {
        editor.forceActiveFocus()
    }

    function selectAll() {
        editor.selectAll()
    }

    function insertTextAtCursor(value) {
        if (!value || value.length === 0)
            return
        var start = editor.selectionStart
        var end = editor.selectionEnd
        if (start !== end) {
            var left = Math.min(start, end)
            var right = Math.max(start, end)
            editor.remove(left, right)
            editor.cursorPosition = left
        }
        editor.insert(editor.cursorPosition, value)
    }

    function handlePasteFromClipboard() {
        if (!markdownImagePaster) {
            editor.paste()
            return
        }
        var imageMarkdown = markdownImagePaster.clipboardImageMarkdown()
        if (imageMarkdown.length > 0) {
            insertTextAtCursor(imageMarkdown)
            return
        }
        editor.paste()
    }

    SplitView {
        id: markdownEditorSplit
        anchors.fill: parent
        orientation: Qt.Horizontal

        ScrollView {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: 220
            SplitView.preferredWidth: Math.max(260, (markdownEditorSplit.width - 10) / 2)

            TextArea {
                id: editor
                text: root.textValue
                placeholderText: root.placeholderText
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                color: "#f5f6f8"
                font.pixelSize: 14
                background: Rectangle {
                    color: "#1b2028"
                    radius: 6
                    border.color: "#384458"
                }
                Keys.onShortcutOverride: function(event) {
                    var isPaste = event.matches(StandardKey.Paste)
                    var isShiftInsert = ((event.modifiers & Qt.ShiftModifier) && event.key === Qt.Key_Insert)
                    if (isPaste || isShiftInsert) {
                        root.handlePasteFromClipboard()
                        event.accepted = true
                    }
                }
                onTextChanged: root.textValue = text
            }
        }

        Rectangle {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: 220
            SplitView.preferredWidth: Math.max(260, (markdownEditorSplit.width - 10) / 2)
            color: "#0f1624"
            radius: 6
            border.color: "#384458"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                Label {
                    text: "Preview"
                    color: "#aab7cf"
                    font.pixelSize: 12
                    font.bold: true
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    background: Rectangle {
                        color: "#0b1220"
                        radius: 4
                        border.color: "#2b3646"
                    }

                    Text {
                        width: parent.width
                        text: root.textValue
                        textFormat: Text.MarkdownText
                        wrapMode: Text.WordWrap
                        color: "#f5f6f8"
                        leftPadding: 10
                        rightPadding: 10
                        topPadding: 8
                        bottomPadding: 8
                    }
                }
            }
        }
    }

    onTextValueChanged: {
        if (editor.text !== textValue)
            editor.text = textValue
    }
}
