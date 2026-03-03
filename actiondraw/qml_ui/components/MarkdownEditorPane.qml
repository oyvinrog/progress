pragma ComponentBehavior: Bound
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root

    property string textValue: ""
    property string placeholderText: ""
    property bool allowCreateTask: false
    property bool previewVisible: true
    property string sourceItemId: ""
    property string _cachedSelectionText: ""
    property var _previewBlocks: []
    property int _minPreviewImageWidth: 48
    property int _minPreviewImageHeight: 48

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
        var imageMarkdown = markdownImagePaster.clipboardImageMarkdownToken()
        if (imageMarkdown.length > 0) {
            insertTextAtCursor(imageMarkdown)
            return
        }
        editor.paste()
    }

    function parseImageAttrs(attrsText) {
        var parsed = {
            width: 0,
            height: 0
        }
        if (!attrsText || attrsText.length === 0)
            return parsed

        var widthMatch = attrsText.match(/width\s*=\s*(\d+)/i)
        var heightMatch = attrsText.match(/height\s*=\s*(\d+)/i)
        if (widthMatch && widthMatch.length > 1)
            parsed.width = parseInt(widthMatch[1], 10)
        if (heightMatch && heightMatch.length > 1)
            parsed.height = parseInt(heightMatch[1], 10)
        return parsed
    }

    function buildMarkdownImage(alt, url, width, height) {
        var safeAlt = alt || ""
        var safeUrl = url || ""
        var w = Math.max(_minPreviewImageWidth, Math.round(width))
        var h = Math.max(_minPreviewImageHeight, Math.round(height))
        return "![" + safeAlt + "](" + safeUrl + "){width=" + w + " height=" + h + "}"
    }

    function appendTextAndImageBlocks(blocks, source, startOffset, endOffset) {
        var imageRegex = /!\[([^\]]*)\]\(([^)\s]+)\)(\{[^}]*\})?/g
        var chunk = source.slice(startOffset, endOffset)
        var cursor = 0
        var match

        while ((match = imageRegex.exec(chunk)) !== null) {
            var start = match.index
            var end = imageRegex.lastIndex
            if (start > cursor) {
                blocks.push({
                    kind: "text",
                    text: chunk.slice(cursor, start)
                })
            }
            var attrs = parseImageAttrs(match[3] || "")
            blocks.push({
                kind: "image",
                alt: match[1] || "",
                url: match[2] || "",
                width: attrs.width,
                height: attrs.height,
                start: startOffset + start,
                end: startOffset + end
            })
            cursor = end
        }

        if (cursor < chunk.length) {
            blocks.push({
                kind: "text",
                text: chunk.slice(cursor)
            })
        }
    }

    function escapeHtml(value) {
        var source = value || ""
        return source
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;")
    }

    function codeBlockHtml(language, code) {
        var lang = language || ""
        var source = code || ""
        if (markdownPreviewFormatter && markdownPreviewFormatter.fencedCodeToHtml)
            return markdownPreviewFormatter.fencedCodeToHtml(lang, source)
        return "<pre style=\"background:#111826;color:#dbe2f2;border:1px solid #334155;border-radius:6px;padding:10px;white-space:pre-wrap;font-family:Monospace;font-size:13px;\"><code>"
            + escapeHtml(source)
            + "</code></pre>"
    }

    function parsePreviewBlocks(markdown) {
        var source = normalizeLineBreaks(markdown)
        if (!source || source.length === 0)
            return []

        var blocks = []
        var inCode = false
        var language = ""
        var textStart = 0
        var codeStart = 0
        var codeContentStart = 0
        var cursor = 0

        while (cursor < source.length) {
            var newline = source.indexOf("\n", cursor)
            var lineEnd = newline >= 0 ? newline : source.length
            var lineAfter = newline >= 0 ? newline + 1 : source.length
            var line = source.slice(cursor, lineEnd)
            var fenceMatch = line.match(/^\s*```+\s*([A-Za-z0-9_+-]*)\s*$/)

            if (!inCode && fenceMatch) {
                appendTextAndImageBlocks(blocks, source, textStart, cursor)
                inCode = true
                language = (fenceMatch[1] || "").toLowerCase()
                codeStart = cursor
                codeContentStart = lineAfter
                textStart = lineAfter
            } else if (inCode && fenceMatch) {
                blocks.push({
                    kind: "code",
                    language: language,
                    code: source.slice(codeContentStart, cursor),
                    start: codeStart,
                    end: lineAfter
                })
                inCode = false
                language = ""
                textStart = lineAfter
            }

            cursor = lineAfter
        }

        if (inCode) {
            blocks.push({
                kind: "code",
                language: language,
                code: source.slice(codeContentStart),
                start: codeStart,
                end: source.length
            })
        } else {
            appendTextAndImageBlocks(blocks, source, textStart, source.length)
        }
        return blocks
    }

    function refreshPreviewBlocks() {
        _previewBlocks = parsePreviewBlocks(root.textValue)
    }

    function updateImageSizeAtRange(start, end, alt, url, width, height) {
        var source = normalizeLineBreaks(root.textValue)
        if (start < 0 || end <= start || end > source.length)
            return

        var replacement = buildMarkdownImage(alt, url, width, height)
        root.textValue = source.slice(0, start) + replacement + source.slice(end)
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
                        if (isPaste || isShiftInsert)
                            event.accepted = true
                    }
                    Keys.onPressed: function(event) {
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
                    Component.onCompleted: {
                        if (markdownHighlighterBridge && markdownHighlighterBridge.attachToTextDocument)
                            markdownHighlighterBridge.attachToTextDocument(editor.textDocument)
                    }
                }
            }

            Rectangle {
                visible: root.previewVisible
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
                        id: previewScroll
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        background: Rectangle {
                            color: "#0b1220"
                            radius: 4
                            border.color: "#2b3646"
                        }

                        Item {
                            width: previewScroll.availableWidth
                            implicitHeight: contentColumn.implicitHeight + 16

                            Column {
                                id: contentColumn
                                x: 10
                                y: 8
                                width: Math.max(0, parent.width - 20)
                                spacing: 8

                                Repeater {
                                    model: root._previewBlocks

                                    delegate: Item {
                                        required property var modelData
                                        width: parent ? parent.width : 0
                                        implicitHeight: blockContent.implicitHeight

                                        Item {
                                            id: blockContent
                                            width: parent.width
                                            implicitHeight: textPreview.visible
                                                ? textPreview.implicitHeight
                                                : (codePreview.visible
                                                    ? codePreview.implicitHeight
                                                    : imagePreview.implicitHeight)

                                            Text {
                                                id: textPreview
                                                visible: modelData && modelData.kind === "text"
                                                width: parent.width
                                                text: root.normalizeLineBreaks(markdownImagePaster
                                                    ? markdownImagePaster.expandMarkdownImages(modelData.text || "")
                                                    : (modelData.text || ""))
                                                textFormat: Text.MarkdownText
                                                wrapMode: Text.WordWrap
                                                color: "#f5f6f8"
                                            }

                                            Text {
                                                id: codePreview
                                                visible: modelData && modelData.kind === "code"
                                                width: parent.width
                                                text: root.codeBlockHtml(modelData.language || "", modelData.code || "")
                                                textFormat: Text.RichText
                                                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                                color: "#dbe2f2"
                                            }

                                            Item {
                                                id: imagePreview
                                                visible: modelData && modelData.kind === "image"
                                                width: parent.width
                                                implicitHeight: imageFrame.height + 8

                                                Rectangle {
                                                    id: imageFrame
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    y: 4
                                                    color: "transparent"
                                                    border.color: imageResizeDrag.active ? "#8fe2ff" : "#3a4659"
                                                    border.width: imageResizeDrag.active ? 2 : 1
                                                    radius: 4

                                                    property real naturalWidth: previewImage.implicitWidth > 0 ? previewImage.implicitWidth : 320
                                                    property real naturalHeight: previewImage.implicitHeight > 0 ? previewImage.implicitHeight : 180
                                                    property real naturalAspect: naturalHeight > 0 ? naturalWidth / naturalHeight : 1.0
                                                    property real maxAllowedWidth: Math.max(root._minPreviewImageWidth, imagePreview.width - 16)
                                                    property real baseWidth: modelData.width > 0
                                                        ? Math.min(maxAllowedWidth, Math.max(root._minPreviewImageWidth, modelData.width))
                                                        : Math.min(maxAllowedWidth, Math.max(120, naturalWidth))
                                                    property real baseHeight: modelData.height > 0
                                                        ? Math.max(root._minPreviewImageHeight, modelData.height)
                                                        : Math.max(root._minPreviewImageHeight, baseWidth / Math.max(0.01, naturalAspect))
                                                    property real liveWidth: baseWidth
                                                    property real liveHeight: baseHeight
                                                    property real dragStartWidth: 0
                                                    property real dragStartHeight: 0

                                                    onBaseWidthChanged: if (!imageResizeDrag.active) liveWidth = baseWidth
                                                    onBaseHeightChanged: if (!imageResizeDrag.active) liveHeight = baseHeight

                                                    width: Math.min(maxAllowedWidth, Math.max(root._minPreviewImageWidth, liveWidth))
                                                    height: Math.max(root._minPreviewImageHeight, liveHeight)

                                                    Image {
                                                        id: previewImage
                                                        anchors.fill: parent
                                                        anchors.margins: 2
                                                        fillMode: Image.PreserveAspectFit
                                                        smooth: true
                                                        asynchronous: true
                                                        source: {
                                                            var rawUrl = modelData.url || ""
                                                            if (rawUrl.indexOf("adimg://") === 0 && markdownImagePaster)
                                                                return markdownImagePaster.resolveMarkdownImageUrl(rawUrl)
                                                            return rawUrl
                                                        }
                                                    }

                                                    Rectangle {
                                                        id: sizeBadge
                                                        anchors.left: parent.left
                                                        anchors.top: parent.top
                                                        anchors.margins: 6
                                                        color: "#0b1220"
                                                        border.color: "#3a4659"
                                                        border.width: 1
                                                        radius: 3
                                                        visible: imageResizeDrag.active

                                                        implicitWidth: sizeLabel.implicitWidth + 8
                                                        implicitHeight: sizeLabel.implicitHeight + 4

                                                        Label {
                                                            id: sizeLabel
                                                            anchors.centerIn: parent
                                                            text: Math.round(imageFrame.width) + " x " + Math.round(imageFrame.height)
                                                            color: "#cbd5e1"
                                                            font.pixelSize: 10
                                                        }
                                                    }

                                                    Rectangle {
                                                        id: imageResizeHandle
                                                        width: 14
                                                        height: 14
                                                        radius: 3
                                                        color: "#8fe2ff"
                                                        border.color: "#0b1220"
                                                        border.width: 1
                                                        anchors.right: parent.right
                                                        anchors.bottom: parent.bottom
                                                        anchors.rightMargin: -6
                                                        anchors.bottomMargin: -6

                                                        DragHandler {
                                                            id: imageResizeDrag
                                                            target: null

                                                            onActiveChanged: {
                                                                if (active) {
                                                                    imageFrame.dragStartWidth = imageFrame.width
                                                                    imageFrame.dragStartHeight = imageFrame.height
                                                                } else {
                                                                    root.updateImageSizeAtRange(
                                                                        modelData.start,
                                                                        modelData.end,
                                                                        modelData.alt,
                                                                        modelData.url,
                                                                        imageFrame.width,
                                                                        imageFrame.height
                                                                    )
                                                                }
                                                            }

                                                            onTranslationChanged: if (active) {
                                                                var minW = root._minPreviewImageWidth
                                                                var minH = root._minPreviewImageHeight
                                                                var maxW = imageFrame.maxAllowedWidth
                                                                var startW = imageFrame.dragStartWidth
                                                                var startH = imageFrame.dragStartHeight
                                                                var nextW = Math.min(maxW, Math.max(minW, startW + translation.x))
                                                                var nextH = Math.max(minH, startH + translation.y)
                                                                var keepAspect = (imageResizeDrag.centroid.modifiers & Qt.ShiftModifier) !== 0

                                                                if (keepAspect) {
                                                                    var aspect = Math.max(0.01, startH > 0 ? startW / startH : imageFrame.naturalAspect)
                                                                    var widthDominant = Math.abs(translation.x) >= Math.abs(translation.y)

                                                                    if (widthDominant) {
                                                                        nextH = Math.max(minH, nextW / aspect)
                                                                        nextW = Math.min(maxW, Math.max(minW, nextH * aspect))
                                                                    } else {
                                                                        nextW = Math.min(maxW, Math.max(minW, nextH * aspect))
                                                                        nextH = Math.max(minH, nextW / aspect)
                                                                    }
                                                                }

                                                                imageFrame.liveWidth = nextW
                                                                imageFrame.liveHeight = nextH
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
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
        var incoming = root.normalizeLineBreaks(textValue)
        if (markdownImagePaster)
            incoming = markdownImagePaster.compactMarkdownImages(incoming)
        if (root.normalizeLineBreaks(editor.text) !== incoming)
            editor.text = incoming
        root.refreshPreviewBlocks()
    }

    Component.onCompleted: root.refreshPreviewBlocks()
}
