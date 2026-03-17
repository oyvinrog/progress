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

    signal saveRequested(string noteId, string text, var tabs)
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
        var currentName = String(tabNameField.text || "").trim()
        nextTabs[index].name = currentName.length > 0 ? currentName : "Tab " + (index + 1)
        nextTabs[index].text = markdownEditor.textValue
        editorRoot.activeTabIndex = index
        editorRoot.noteTabs = nextTabs
        editorRoot.noteText = nextTabs[index].text
    }

    function activateTab(index) {
        commitActiveTabState()
        if (!editorRoot.noteTabs || index < 0 || index >= editorRoot.noteTabs.length)
            return
        editorRoot.activeTabIndex = index
        editorRoot.noteText = String(editorRoot.noteTabs[index].text || "")
        markdownEditor.textValue = editorRoot.noteText
        markdownEditor.focusEditor()
    }

    function addTab() {
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
    }

    function saveAllTabs() {
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
        editorRoot.saveRequested(editorRoot.noteId, text, tabs)
    }

    function loadEditorState(sourceTabs, initialText) {
        restoringState = true
        activeTabIndex = 0
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

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 44
                clip: true

                Row {
                    spacing: 6

                    Repeater {
                        model: editorRoot.noteTabs

                        delegate: Rectangle {
                            required property int index
                            required property var modelData

                            radius: 8
                            color: editorRoot.activeTabIndex === index ? "#1f3350" : "#17212f"
                            border.color: editorRoot.activeTabIndex === index ? "#7bc6ff" : "#324255"
                            border.width: 1
                            height: 34
                            width: Math.max(112, tabLabel.implicitWidth + closeButtonContainer.width + 30)

                            MouseArea {
                                anchors.fill: parent
                                onClicked: editorRoot.activateTab(index)
                            }

                            Row {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 8
                                spacing: 10

                                Label {
                                    id: tabLabel
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: String(modelData.name || ("Tab " + (index + 1)))
                                    color: "#e2e8f0"
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                }

                                Rectangle {
                                    id: closeButtonContainer
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: editorRoot.noteTabs.length > 1
                                    width: 22
                                    height: 22
                                    radius: 6
                                    color: closeButtonMouse.containsMouse ? "#24364a" : "#1a2533"
                                    border.color: closeButtonMouse.containsMouse ? "#5f7388" : "#314356"
                                    border.width: 1

                                    Label {
                                        anchors.centerIn: parent
                                        text: "x"
                                        color: closeButtonMouse.containsMouse ? "#f8fafc" : "#9fb0c3"
                                        font.pixelSize: 11
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
                text: "New Tab"
                onClicked: editorRoot.addTab()
            }
        }

        TextField {
            id: tabNameField
            Layout.fillWidth: true
            placeholderText: "Tab name"
            text: (editorRoot.noteTabs && editorRoot.noteTabs.length > 0)
                ? String(editorRoot.noteTabs[editorRoot.activeTabIndex].name || "")
                : ""
            onEditingFinished: editorRoot.setActiveTabName(text)
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
                text: "Save"
                onClicked: editorRoot.saveAllTabs()
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
            if (noteTabs.length > 0) {
                var restoringName = String(noteTabs[activeTabIndex].name || "")
                if (tabNameField.text !== restoringName)
                    tabNameField.text = restoringName
            }
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
        var currentName = String(noteTabs[activeTabIndex].name || "")
        if (tabNameField.text !== currentName)
            tabNameField.text = currentName
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
        sequence: "Ctrl+Enter"
        enabled: editorRoot.visible
        onActivated: editorRoot.saveAllTabs()
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
