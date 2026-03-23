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
    property var noteTabs: []
    property int activeTabIndex: 0
    property string editorType: "note"
    property real targetX: 0
    property real targetY: 0
    property bool restoringState: false
    property bool externalPromptVisible: false
    property string externalPromptText: "Touch your YubiKey to continue."
    property bool fullWindowMode: false
    property bool saveConfirmationVisible: false
    property int renamingTabIndex: -1

    signal saveRequested(string noteId, string text, var tabs)
    signal saveAndCloseRequested(string noteId, string text, var tabs)
    signal cancelRequested()

    function normalizedTabs(sourceTabs, fallbackText) {
        var list = []
        if (sourceTabs && sourceTabs.length !== undefined) {
            for (var i = 0; i < sourceTabs.length; ++i) {
                var tab = sourceTabs[i] || {}
                var name = String(tab.name || "").trim()
                list.push({
                    name: name.length > 0 ? name : "Tab " + (i + 1),
                    text: String(tab.text || "")
                })
            }
        }
        if (list.length === 0) {
            list.push({
                name: "Tab 1",
                text: String(fallbackText || "")
            })
        }
        return list
    }

    function cloneTabs(sourceTabs) {
        return normalizedTabs(sourceTabs, "").slice(0)
    }

    function expandedTabText(text) {
        var rawText = String(text || "")
        return markdownImagePaster
            ? markdownImagePaster.expandMarkdownImages(rawText)
            : rawText
    }

    function commitActiveTabState() {
        if (!editorRoot.noteTabs || editorRoot.noteTabs.length === 0)
            editorRoot.noteTabs = normalizedTabs([], editorRoot.noteText)
        var nextTabs = cloneTabs(editorRoot.noteTabs)
        var index = Math.max(0, Math.min(editorRoot.activeTabIndex, nextTabs.length - 1))
        var currentName = String(nextTabs[index].name || "").trim()
        if (currentName.length === 0)
            nextTabs[index].name = "Tab " + (index + 1)
        nextTabs[index].text = markdownEditor.textValue
        editorRoot.activeTabIndex = index
        editorRoot.noteTabs = nextTabs
        editorRoot.noteText = nextTabs[index].text
    }

    function activateTab(index) {
        finishTabRename()
        commitActiveTabState()
        if (!editorRoot.noteTabs || index < 0 || index >= editorRoot.noteTabs.length)
            return
        editorRoot.activeTabIndex = index
        editorRoot.noteText = String(editorRoot.noteTabs[index].text || "")
        markdownEditor.textValue = editorRoot.noteText
        markdownEditor.focusEditor()
    }

    function addTab() {
        finishTabRename()
        commitActiveTabState()
        var nextTabs = cloneTabs(editorRoot.noteTabs)
        nextTabs.push({
            name: "Tab " + (nextTabs.length + 1),
            text: ""
        })
        editorRoot.noteTabs = nextTabs
        activateTab(nextTabs.length - 1)
    }

    function closeTab(index) {
        if (!editorRoot.noteTabs || editorRoot.noteTabs.length <= 1 || index < 0 || index >= editorRoot.noteTabs.length)
            return
        finishTabRename()
        commitActiveTabState()
        var nextTabs = cloneTabs(editorRoot.noteTabs)
        nextTabs.splice(index, 1)
        editorRoot.noteTabs = nextTabs
        activateTab(Math.min(index, nextTabs.length - 1))
    }

    function setActiveTabName(name) {
        if (!editorRoot.noteTabs || editorRoot.noteTabs.length === 0)
            return
        var nextTabs = cloneTabs(editorRoot.noteTabs)
        var trimmed = String(name || "").trim()
        nextTabs[editorRoot.activeTabIndex].name = trimmed.length > 0 ? trimmed : "Tab " + (editorRoot.activeTabIndex + 1)
        editorRoot.noteTabs = nextTabs
        editorRoot.renamingTabIndex = -1
    }

    function beginTabRename(index, editor) {
        if (!editorRoot.noteTabs || index < 0 || index >= editorRoot.noteTabs.length || !editor)
            return
        if (editorRoot.activeTabIndex !== index)
            activateTab(index)
        editorRoot.renamingTabIndex = index
        editor.readOnly = false
        editor.forceActiveFocus()
        editor.selectAll()
    }

    function cancelTabRename(index, editor, originalName) {
        if (editor)
            editor.text = originalName
        if (editor)
            editor.readOnly = true
        if (editorRoot.renamingTabIndex === index)
            editorRoot.renamingTabIndex = -1
        markdownEditor.focusEditor()
    }

    function finishTabRename() {
        if (editorRoot.renamingTabIndex >= 0)
            editorRoot.renamingTabIndex = -1
    }

    function saveAllTabs() {
        saveTabs(false)
    }

    function saveAllTabsAndClose() {
        saveTabs(true)
    }

    function saveTabs(closeAfterSave) {
        finishTabRename()
        commitActiveTabState()
        var sourceTabs = cloneTabs(editorRoot.noteTabs)
        var tabs = []
        for (var i = 0; i < sourceTabs.length; ++i) {
            tabs.push({
                name: String(sourceTabs[i].name || ("Tab " + (i + 1))),
                text: expandedTabText(sourceTabs[i].text)
            })
        }
        var text = tabs.length > 0 ? String(tabs[editorRoot.activeTabIndex].text || "") : ""
        if (closeAfterSave)
            editorRoot.saveAndCloseRequested(editorRoot.noteId, text, tabs)
        else
            editorRoot.saveRequested(editorRoot.noteId, text, tabs)
    }

    function loadEditorState(sourceTabs, initialText) {
        restoringState = true
        activeTabIndex = 0
        renamingTabIndex = -1
        noteText = ""
        noteTabs = normalizedTabs(sourceTabs, initialText)
        noteText = String(noteTabs[0].text || "")
        restoringState = false
    }

    function setFullWindowMode(enabled) {
        fullWindowMode = enabled
        visibility = enabled ? Window.Maximized : Window.Windowed
    }

    function showSaveConfirmation() {
        saveConfirmationVisible = true
        saveConfirmationTimer.restart()
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

            Rectangle {
                visible: editorRoot.saveConfirmationVisible
                radius: 6
                color: "#0f766e"
                border.color: "#14b8a6"
                border.width: 1
                implicitWidth: saveConfirmationLabel.implicitWidth + 18
                implicitHeight: saveConfirmationLabel.implicitHeight + 10

                Label {
                    id: saveConfirmationLabel
                    anchors.centerIn: parent
                    text: "Saved"
                    color: "#f0fdfa"
                    font.pixelSize: 13
                    font.bold: true
                }
            }

            Button {
                text: editorRoot.fullWindowMode ? "Exit Full Window" : "Full Window"
                onClicked: editorRoot.setFullWindowMode(!editorRoot.fullWindowMode)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 54
                radius: 14
                color: "#0d1522"
                border.color: "#243347"
                border.width: 1

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 1
                    radius: 13
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#101a29" }
                        GradientStop { position: 1.0; color: "#0b131f" }
                    }
                    opacity: 0.95
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    anchors.topMargin: 7
                    anchors.bottomMargin: 7
                    spacing: 10

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        Row {
                            spacing: 8

                            Repeater {
                                model: editorRoot.noteTabs

                                delegate: Rectangle {
                                    required property int index
                                    required property var modelData

                                    property bool isActive: editorRoot.activeTabIndex === index
                                    property bool isRenaming: editorRoot.renamingTabIndex === index
                                    property string resolvedTabName: String(modelData.name || ("Tab " + (index + 1)))

                                    radius: 11
                                    color: isActive ? "#1b3048" : "#14202f"
                                    border.color: isActive ? "#88d0ff" : (tabMouse.containsMouse ? "#4a627a" : "#2d4054")
                                    border.width: 1
                                    height: 38
                                    width: Math.max(150, tabInlineEditor.implicitWidth + closeButtonContainer.width + 58)

                                    Rectangle {
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        radius: 10
                                        gradient: Gradient {
                                            GradientStop { position: 0.0; color: isActive ? "#223c59" : "#182535" }
                                            GradientStop { position: 1.0; color: isActive ? "#16283d" : "#101926" }
                                        }
                                        opacity: 0.98
                                    }

                                    Rectangle {
                                        visible: isActive
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 7
                                        height: 3
                                        radius: 2
                                        color: "#7bc6ff"
                                        opacity: 0.95
                                    }

                                    MouseArea {
                                        id: tabMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: {
                                            if (!isActive)
                                                editorRoot.activateTab(index)
                                        }
                                        onDoubleClicked: function(mouse) {
                                            if (mouse.button !== Qt.LeftButton)
                                                return
                                            editorRoot.beginTabRename(index, tabInlineEditor)
                                        }
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 14
                                        anchors.rightMargin: 8
                                        spacing: 12

                                        Rectangle {
                                            implicitWidth: 8
                                            implicitHeight: 8
                                            radius: 4
                                            color: isActive ? "#7bc6ff" : "#4a6278"
                                            Layout.alignment: Qt.AlignVCenter
                                        }

                                        Item {
                                            Layout.fillWidth: true
                                            Layout.alignment: Qt.AlignVCenter
                                            implicitHeight: tabInlineEditor.implicitHeight

                                            TextField {
                                                id: tabInlineEditor
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: resolvedTabName
                                                color: isActive ? "#f3f8ff" : "#bfd0e3"
                                                font.pixelSize: 13
                                                font.bold: isActive
                                                readOnly: !isRenaming
                                                background: Rectangle {
                                                    color: tabInlineEditor.readOnly ? "transparent" : "#0d1520"
                                                    border.color: tabInlineEditor.readOnly ? "transparent" : "#88d0ff"
                                                    border.width: tabInlineEditor.readOnly ? 0 : 1
                                                    radius: 4
                                                }
                                                padding: 2
                                                leftPadding: tabInlineEditor.readOnly ? 0 : 4
                                                rightPadding: tabInlineEditor.readOnly ? 0 : 4
                                                onEditingFinished: {
                                                    if (readOnly)
                                                        return
                                                    editorRoot.setActiveTabName(text)
                                                    readOnly = true
                                                }
                                                onActiveFocusChanged: {
                                                    if (!activeFocus && !readOnly) {
                                                        editorRoot.setActiveTabName(text)
                                                        readOnly = true
                                                    }
                                                }
                                                Keys.onEscapePressed: {
                                                    editorRoot.cancelTabRename(index, tabInlineEditor, resolvedTabName)
                                                }
                                            }

                                            MouseArea {
                                                anchors.fill: tabInlineEditor
                                                visible: tabInlineEditor.readOnly
                                                enabled: visible
                                                hoverEnabled: true
                                                acceptedButtons: Qt.LeftButton
                                                onClicked: {
                                                    if (!isActive)
                                                        editorRoot.activateTab(index)
                                                }
                                                onDoubleClicked: function(mouse) {
                                                    if (mouse.button !== Qt.LeftButton)
                                                        return
                                                    editorRoot.beginTabRename(index, tabInlineEditor)
                                                }
                                            }
                                        }

                                        Rectangle {
                                            id: closeButtonContainer
                                            visible: editorRoot.noteTabs.length > 1
                                            implicitWidth: 22
                                            implicitHeight: 22
                                            radius: 7
                                            color: closeButtonMouse.containsMouse ? "#31475f" : "#182433"
                                            border.color: closeButtonMouse.containsMouse ? "#7f9dbb" : "#26384a"
                                            border.width: 1
                                            Layout.alignment: Qt.AlignVCenter

                                            Label {
                                                anchors.centerIn: parent
                                                text: "x"
                                                color: closeButtonMouse.containsMouse ? "#ffffff" : "#90a5bc"
                                                font.pixelSize: 10
                                                font.bold: true
                                            }

                                            MouseArea {
                                                id: closeButtonMouse
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                propagateComposedEvents: false
                                                onClicked: function(mouse) {
                                                    mouse.accepted = true
                                                    editorRoot.closeTab(index)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Button {
                        id: newTabButton
                        text: "New Tab"
                        Layout.preferredHeight: 38
                        Layout.preferredWidth: 92
                        onClicked: editorRoot.addTab()
                        background: Rectangle {
                            radius: 11
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: newTabButton.down ? "#255277" : (newTabButton.hovered ? "#2f628d" : "#274f73") }
                                GradientStop { position: 1.0; color: newTabButton.down ? "#1d3f5d" : "#1f4463" }
                            }
                            border.color: newTabButton.hovered ? "#99dbff" : "#5e8eb5"
                            border.width: 1
                        }
                        contentItem: Label {
                            text: parent.text
                            color: "#eff7ff"
                            font.pixelSize: 13
                            font.bold: true
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }

        MarkdownEditorPane {
            id: markdownEditor
            Layout.fillWidth: true
            Layout.fillHeight: true
            placeholderText: editorRoot.editorType === "freetext" ? "Write your text here..." : "Write your note here..."
            allowCreateTask: true
            previewVisible: true
            sourceItemId: editorRoot.noteId
            textValue: editorRoot.noteText
            onTextValueChanged: {
                if (editorRoot.restoringState)
                    return
                editorRoot.noteText = textValue
                if (!editorRoot.noteTabs || editorRoot.noteTabs.length === 0)
                    return
                var nextTabs = editorRoot.cloneTabs(editorRoot.noteTabs)
                nextTabs[editorRoot.activeTabIndex].text = textValue
                editorRoot.noteTabs = nextTabs
            }
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
                text: "Save (Ctrl+Enter/Ctrl+Return)"
                onClicked: editorRoot.saveAllTabs()
            }

            Button {
                text: "Save and Close (Ctrl+Shift+Enter/Ctrl+Shift+Return)"
                onClicked: editorRoot.saveAllTabsAndClose()
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

    onNoteTabsChanged: {
        if (restoringState) {
            if (activeTabIndex < 0 || activeTabIndex >= noteTabs.length)
                activeTabIndex = 0
            return
        }
        var normalized = normalizedTabs(noteTabs, noteText)
        if (JSON.stringify(normalized) !== JSON.stringify(noteTabs)) {
            noteTabs = normalized
            return
        }
        if (activeTabIndex < 0 || activeTabIndex >= noteTabs.length)
            activeTabIndex = 0
        var currentText = String(noteTabs[activeTabIndex].text || "")
        if (noteText !== currentText)
            noteText = currentText
    }

    Shortcut {
        sequence: "F11"
        onActivated: editorRoot.setFullWindowMode(!editorRoot.fullWindowMode)
    }

    Shortcut {
        sequence: "Ctrl+Return"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveAllTabs()
    }

    Shortcut {
        sequence: "Ctrl+Enter"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveAllTabs()
    }

    Shortcut {
        sequence: "Ctrl+S"
        enabled: editorRoot.visible && markdownNoteManager && markdownNoteManager.requestProjectSave
        onActivated: {
            editorRoot.saveAllTabs()
            markdownNoteManager.requestProjectSave()
        }
    }

    Timer {
        id: saveConfirmationTimer
        interval: 1400
        repeat: false
        onTriggered: editorRoot.saveConfirmationVisible = false
    }

    Shortcut {
        sequence: "Ctrl+Shift+Return"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveAllTabsAndClose()
    }

    Shortcut {
        sequence: "Ctrl+Shift+Enter"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveAllTabsAndClose()
    }

    onClosing: function(close) {
        close.accepted = true
        editorRoot.fullWindowMode = false
        editorRoot.visibility = Window.Windowed
        editorRoot.cancelRequested()
    }

    Dialog {
        id: externalPromptDialog
        modal: true
        focus: true
        closePolicy: Popup.NoAutoClose
        x: Math.round((editorRoot.width - width) / 2)
        y: Math.round((editorRoot.height - height) / 2)
        width: Math.min(editorRoot.width * 0.7, 520)
        visible: editorRoot.externalPromptVisible

        background: Rectangle {
            radius: 14
            color: "#152132"
            border.color: "#7bc6ff"
            border.width: 2
        }

        contentItem: ColumnLayout {
            spacing: 14

            Label {
                text: "YubiKey Verification Required"
                font.pixelSize: 18
                font.bold: true
                color: "#eef6ff"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Label {
                text: editorRoot.externalPromptText
                color: "#d6e4f3"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 10
                color: "#0f1927"
                border.color: "#2f4761"
                border.width: 1
                implicitHeight: promptRow.implicitHeight + 18

                RowLayout {
                    id: promptRow
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    BusyIndicator {
                        running: editorRoot.externalPromptVisible
                        Layout.preferredWidth: 30
                        Layout.preferredHeight: 30
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "Complete the YubiKey step in this save flow. This dialog stays on top until the prompt finishes."
                        color: "#b8cae0"
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
