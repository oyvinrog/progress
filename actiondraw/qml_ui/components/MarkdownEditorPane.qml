import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property string textValue: ""
    property string placeholderText: ""
    property bool allowCreateTask: false
    property string sourceItemId: ""
    property string _cachedSelectionText: ""

    signal createTaskRequested(string selectedText)

    function normalizeLineBreaks(value) {
        if (!value)
            return ""
        return value.replace(/\u2029/g, "\n")
    }

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

    function selectedTextNormalized() {
        var start = editor.selectionStart
        var end = editor.selectionEnd
        if (start < 0 || end < 0 || start === end)
            return ""
        var left = Math.min(start, end)
        var right = Math.max(start, end)
        return editor.text.slice(left, right).replace(/\u2029/g, "\n").trim()
    }

    function refreshSelectionCache() {
        var selected = selectedTextNormalized()
        if (selected.length > 0)
            _cachedSelectionText = selected
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

    ColumnLayout {
        anchors.fill: parent
        spacing: 8

        SplitView {
            id: markdownEditorSplit
            Layout.fillWidth: true
            Layout.fillHeight: true
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
                    onTextChanged: root.textValue = root.normalizeLineBreaks(text)
                    onSelectionStartChanged: root.refreshSelectionCache()
                    onSelectionEndChanged: root.refreshSelectionCache()
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
                            text: root.normalizeLineBreaks(root.textValue)
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

        RowLayout {
            Layout.fillWidth: true
            visible: root.allowCreateTask

            Item {
                Layout.fillWidth: true
            }

            Button {
                text: "Create Task"
                enabled: root.selectedTextNormalized().length > 0 || root._cachedSelectionText.length > 0
                onClicked: {
                    var selected = root.selectedTextNormalized()
                    if (selected.length === 0)
                        selected = root._cachedSelectionText
                    if (selected.length > 0)
                        root.createTaskRequested(selected)
                }
            }
        }
    }

    onTextValueChanged: {
        if (root.normalizeLineBreaks(editor.text) !== root.normalizeLineBreaks(textValue))
            editor.text = root.normalizeLineBreaks(textValue)
    }
}
