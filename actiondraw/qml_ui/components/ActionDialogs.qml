import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs

Item {
    id: dialogHost
    property var root: null
    property var diagramModel: null
    property var taskModel: null
    property var projectManager: null
    property var markdownNoteManager: null
    property var tabModel: null
    property var diagramLayer: null

    property alias addDialog: addDialog
    property alias boxDialog: boxDialog
    property alias freeTextDialog: freeTextDialog
    property alias edgeDescriptionDialog: edgeDescriptionDialog
    property alias taskDialog: taskDialog
    property alias newTaskDialog: newTaskDialog
    property alias quickTaskDialog: quickTaskDialog
    property alias breakdownDialog: breakdownDialog
    property alias taskRenameDialog: taskRenameDialog
    property alias timerDialog: timerDialog
    property alias timerContextMenu: timerContextMenu
    property alias edgeDropMenu: edgeDropMenu
    property alias edgeDropTaskDialog: edgeDropTaskDialog
    property alias saveDialog: saveDialog
    property alias loadDialog: loadDialog
    property alias subDiagramFileDialog: subDiagramFileDialog
    property alias newSubDiagramFileDialog: newSubDiagramFileDialog
    property alias clipboardPasteDialog: clipboardPasteDialog

    anchors.fill: parent

    Dialog {
        id: addDialog
        modal: true
        width: 360
        title: "Add to Diagram"
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            implicitWidth: 320
            spacing: 12

            Button {
                text: "Box"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("box", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Database"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("database", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Server"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("server", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Cloud"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("cloud", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Note"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("note", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Obstacle"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("obstacle", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Wish"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("wish", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "ChatGPT"
                onClicked: {
                    addDialog.close()
                    root.openPresetDialog("chatgpt", Qt.point(addDialog.targetX, addDialog.targetY), "", undefined)
                }
            }

            Button {
                text: "Task from List"
                enabled: !!(taskModel && taskModel.taskCount > 0)
                onClicked: {
                    addDialog.close()
                    if (taskModel) {
                        taskDialog.targetX = root.snapValue(addDialog.targetX)
                        taskDialog.targetY = root.snapValue(addDialog.targetY)
                        taskDialog.open()
                    }
                }
            }

            Button {
                text: "New Task (freetext)"
                enabled: diagramModel ? true : false
                onClicked: {
                    addDialog.close()
                    root.openQuickTaskDialog(Qt.point(addDialog.targetX, addDialog.targetY))
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Cancel
            onRejected: addDialog.close()
        }
    }

    Dialog {
        id: boxDialog
        modal: true
        property real targetX: 0
        property real targetY: 0
        property string editingItemId: ""
        property string textValue: ""
        property string presetName: "box"
        title: boxDialog.editingItemId.length === 0 ? root.presetTitle(boxDialog.presetName) : "Edit Label"

        onOpened: {
            boxTextField.forceActiveFocus()
            if (boxDialog.editingItemId.length > 0)
                boxTextField.selectAll()
        }

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: boxTextField
                Layout.fillWidth: true
                text: boxDialog.textValue
                placeholderText: "Label"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: boxDialog.textValue = text
                Keys.onReturnPressed: boxDialog.accept()
                Keys.onEnterPressed: boxDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: boxDialogButtonBox
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (!diagramModel)
                return
            if (boxDialog.editingItemId.length === 0) {
                diagramModel.addPresetItemWithText(
                    boxDialog.presetName,
                    root.snapValue(boxDialog.targetX),
                    root.snapValue(boxDialog.targetY),
                    boxDialog.textValue
                )
            } else {
                diagramModel.setItemText(boxDialog.editingItemId, boxDialog.textValue)
            }
            boxDialog.close()
        }
        onRejected: boxDialog.close()

        onClosed: {
            boxDialog.textValue = ""
            boxDialog.editingItemId = ""
            boxDialog.presetName = "box"
        }
    }

    Dialog {
        id: freeTextDialog
        modal: true
        property real targetX: 0
        property real targetY: 0
        property string editingItemId: ""
        property string textValue: ""
        title: freeTextDialog.editingItemId.length === 0 ? "Free Text" : "Edit Free Text"

        onOpened: {
            freeTextArea.forceActiveFocus()
            if (freeTextDialog.editingItemId.length > 0)
                freeTextArea.selectAll()
        }

        contentItem: ColumnLayout {
            width: 360
            spacing: 12

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 160

                TextArea {
                    id: freeTextArea
                    text: freeTextDialog.textValue
                    placeholderText: "Write your text here..."
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    color: "#f5f6f8"
                    font.pixelSize: 14
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 6
                        border.color: "#384458"
                    }
                    onTextChanged: freeTextDialog.textValue = text
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (!diagramModel)
                return
            if (freeTextDialog.editingItemId.length === 0) {
                diagramModel.addPresetItemWithText(
                    "freetext",
                    root.snapValue(freeTextDialog.targetX),
                    root.snapValue(freeTextDialog.targetY),
                    freeTextDialog.textValue
                )
            } else {
                diagramModel.setItemText(freeTextDialog.editingItemId, freeTextDialog.textValue)
            }
            freeTextDialog.close()
        }
        onRejected: freeTextDialog.close()

        onClosed: {
            freeTextDialog.textValue = ""
            freeTextDialog.editingItemId = ""
        }
    }

    Dialog {
        id: edgeDescriptionDialog
        modal: true
        title: "Edge Description"
        property string edgeId: ""
        property string descriptionValue: ""

        function openWithEdge(eId) {
            edgeId = eId
            descriptionValue = diagramModel ? diagramModel.getEdgeDescription(eId) : ""
            open()
        }

        onOpened: edgeDescriptionField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: edgeDescriptionField
                Layout.fillWidth: true
                text: edgeDescriptionDialog.descriptionValue
                placeholderText: "Description (optional)"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: edgeDescriptionDialog.descriptionValue = text
                Keys.onReturnPressed: edgeDescriptionDialog.accept()
                Keys.onEnterPressed: edgeDescriptionDialog.accept()
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && edgeDescriptionDialog.edgeId.length > 0) {
                diagramModel.setEdgeDescription(edgeDescriptionDialog.edgeId, edgeDescriptionDialog.descriptionValue)
            }
            close()
        }
        onRejected: close()

        onClosed: {
            edgeDescriptionDialog.edgeId = ""
            edgeDescriptionDialog.descriptionValue = ""
        }
    }

    Dialog {
        id: taskDialog
        modal: true
        title: "Add Task"
        width: 450
        property real targetX: 0
        property real targetY: 0

        contentItem: ColumnLayout {
            spacing: 12

            ListView {
                id: taskListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 420
                Layout.preferredHeight: 320
                model: taskModel
                clip: true

                delegate: Item {
                    width: taskListView.width
                    height: Math.max(40, taskText.implicitHeight + 16)

                    Rectangle {
                        anchors.fill: parent
                        color: mouseArea.containsMouse ? "#283346" : "#1a2230"
                        border.color: "#30405a"
                    }

                    Text {
                        id: taskText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 12
                        text: model.title
                        color: "#f5f6f8"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    MouseArea {
                        id: mouseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (diagramModel) {
                                diagramModel.addTask(
                                    index,
                                    root.snapValue(taskDialog.targetX),
                                    root.snapValue(taskDialog.targetY)
                                )
                            }
                            taskDialog.close()
                        }
                    }
                }
            }

            Label {
                text: taskModel ? "No tasks available. Add tasks in Progress Tracker." : "Task list unavailable. Open ActionDraw from the task app."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignHCenter
                horizontalAlignment: Text.AlignHCenter
                visible: !taskModel || taskListView.count === 0
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Cancel
            onRejected: taskDialog.close()
        }
    }

    Dialog {
        id: newTaskDialog
        modal: true
        title: "Create Task"
        property string pendingItemId: ""
        property string textValue: ""

        function openWithItem(itemId, text) {
            pendingItemId = itemId
            textValue = text
            open()
        }

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            TextField {
                id: newTaskField
                Layout.fillWidth: true
                text: newTaskDialog.textValue
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: newTaskDialog.textValue = text
                Keys.onReturnPressed: newTaskDialog.accept()
                Keys.onEnterPressed: newTaskDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: newTaskButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && newTaskDialog.pendingItemId.length > 0) {
                diagramModel.createTaskFromText(newTaskDialog.textValue, newTaskDialog.pendingItemId)
            }
        }
        onRejected: newTaskDialog.close()

        onClosed: {
            newTaskDialog.pendingItemId = ""
            newTaskDialog.textValue = ""
        }
    }

    Dialog {
        id: quickTaskDialog
        modal: true
        title: "New Task"
        property real targetX: 0
        property real targetY: 0

        onOpened: quickTaskField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: "Create a new task that will be added to both the diagram and your Progress List."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: quickTaskField
                Layout.fillWidth: true
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                Keys.onReturnPressed: quickTaskDialog.accept()
                Keys.onEnterPressed: quickTaskDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: quickTaskButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && quickTaskField.text.trim().length > 0) {
                var newId = diagramModel.addTaskFromText(
                    quickTaskField.text,
                    root.snapValue(quickTaskDialog.targetX),
                    root.snapValue(quickTaskDialog.targetY)
                )
                if (newId && newId.length > 0) {
                    root.lastCreatedTaskId = newId
                    root.selectedItemId = newId
                }
            }
            quickTaskDialog.close()
        }
        onRejected: quickTaskDialog.close()

        onClosed: {
            quickTaskField.text = ""
        }
    }

    Dialog {
        id: breakdownDialog
        modal: true
        title: "Break Down"
        property string sourceItemId: ""
        property string sourceTypeLabel: ""

        onOpened: breakdownTextArea.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 360
            spacing: 12

            Label {
                text: breakdownDialog.sourceTypeLabel.length > 0
                    ? "Create " + breakdownDialog.sourceTypeLabel + " items. One per line or comma-separated."
                    : "Create items. One per line or comma-separated."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextArea {
                id: breakdownTextArea
                Layout.fillWidth: true
                Layout.preferredHeight: 140
                placeholderText: "One per line"
                selectByMouse: true
                color: "#f5f6f8"
                wrapMode: TextEdit.Wrap
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && breakdownDialog.sourceItemId.length > 0) {
                diagramModel.breakDownItem(breakdownDialog.sourceItemId, breakdownTextArea.text)
            }
            breakdownDialog.close()
        }
        onRejected: breakdownDialog.close()

        onClosed: {
            breakdownDialog.sourceItemId = ""
            breakdownDialog.sourceTypeLabel = ""
            breakdownTextArea.text = ""
        }
    }

    Dialog {
        id: taskRenameDialog
        modal: true
        title: "Rename Task"
        property string editingItemId: ""
        property string textValue: ""

        onOpened: {
            taskRenameField.forceActiveFocus()
            taskRenameField.selectAll()
        }

        function openWithItem(itemId, text) {
            editingItemId = itemId
            textValue = text
            open()
        }

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: "Rename this task. Changes will be synced to the Progress List."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: taskRenameField
                Layout.fillWidth: true
                text: taskRenameDialog.textValue
                placeholderText: "Task name"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: taskRenameDialog.textValue = text
                Keys.onReturnPressed: taskRenameDialog.accept()
                Keys.onEnterPressed: taskRenameDialog.accept()
            }
        }

        footer: DialogButtonBox {
            id: taskRenameButtons
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && taskRenameDialog.editingItemId.length > 0 && taskRenameDialog.textValue.trim().length > 0) {
                diagramModel.renameTaskItem(taskRenameDialog.editingItemId, taskRenameDialog.textValue)
            }
        }
        onRejected: taskRenameDialog.close()

        onClosed: {
            taskRenameDialog.editingItemId = ""
            taskRenameDialog.textValue = ""
        }
    }

    Dialog {
        id: timerDialog
        modal: true
        title: "Set Timer"
        property int taskIndex: -1
        property string durationValue: ""

        onOpened: timerDurationField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 280
            spacing: 12

            Label {
                text: "Enter duration (e.g. 30s, 2m, 1h)"
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: timerDurationField
                Layout.fillWidth: true
                text: timerDialog.durationValue
                placeholderText: "e.g. 2m"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: timerDialog.durationValue = text
                Keys.onReturnPressed: timerDialog.accept()
                Keys.onEnterPressed: timerDialog.accept()
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "30s"
                    onClicked: {
                        timerDialog.durationValue = "30s"
                        timerDialog.accept()
                    }
                    background: Rectangle {
                        color: parent.pressed ? "#384458" : "#2a3240"
                        radius: 4
                        border.color: "#4b5b72"
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "1m"
                    onClicked: {
                        timerDialog.durationValue = "1m"
                        timerDialog.accept()
                    }
                    background: Rectangle {
                        color: parent.pressed ? "#384458" : "#2a3240"
                        radius: 4
                        border.color: "#4b5b72"
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "2m"
                    onClicked: {
                        timerDialog.durationValue = "2m"
                        timerDialog.accept()
                    }
                    background: Rectangle {
                        color: parent.pressed ? "#384458" : "#2a3240"
                        radius: 4
                        border.color: "#4b5b72"
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "5m"
                    onClicked: {
                        timerDialog.durationValue = "5m"
                        timerDialog.accept()
                    }
                    background: Rectangle {
                        color: parent.pressed ? "#384458" : "#2a3240"
                        radius: 4
                        border.color: "#4b5b72"
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && timerDialog.taskIndex >= 0 && timerDialog.durationValue.trim().length > 0) {
                diagramModel.setTaskCountdownTimer(timerDialog.taskIndex, timerDialog.durationValue)
            }
            timerDialog.close()
        }
        onRejected: timerDialog.close()

        onClosed: {
            timerDialog.taskIndex = -1
            timerDialog.durationValue = ""
        }
    }

    Menu {
        id: timerContextMenu
        property int taskIndex: -1

        MenuItem {
            text: "Restart Timer"
            onTriggered: {
                if (diagramModel && timerContextMenu.taskIndex >= 0) {
                    diagramModel.restartTaskCountdownTimer(timerContextMenu.taskIndex)
                }
            }
        }

        MenuItem {
            text: "Clear Timer"
            onTriggered: {
                if (diagramModel && timerContextMenu.taskIndex >= 0) {
                    diagramModel.clearTaskCountdownTimer(timerContextMenu.taskIndex)
                }
            }
        }
    }

    Menu {
        id: edgeDropMenu
        title: "Create & Connect"

        MenuItem {
            text: "\u2192 Task"
            onTriggered: {
                edgeDropTaskDialog.sourceId = root.pendingEdgeSourceId
                edgeDropTaskDialog.sourceType = "task"
                edgeDropTaskDialog.dropX = root.pendingEdgeDropX
                edgeDropTaskDialog.dropY = root.pendingEdgeDropY
                edgeDropTaskDialog.open()
            }
        }

        MenuItem {
            text: "\u2192 Obstacle"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "obstacle",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Obstacle"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 Wish"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "wish",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Wish"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 ChatGPT"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "chatgpt",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Ask ChatGPT"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuSeparator {}

        MenuItem {
            text: "\u2192 Box"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "box",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Box"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 Note"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "note",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Note"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 Database"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "database",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Database"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 Server"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "server",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Server"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        MenuItem {
            text: "\u2192 Cloud"
            onTriggered: {
                if (diagramModel && root.pendingEdgeSourceId) {
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "cloud",
                        root.snapValue(root.pendingEdgeDropX),
                        root.snapValue(root.pendingEdgeDropY),
                        "Cloud"
                    )
                }
                root.pendingEdgeSourceId = ""
            }
        }

        onClosed: {
            root.pendingEdgeSourceId = ""
        }
    }

    Dialog {
        id: edgeDropTaskDialog
        modal: true
        title: sourceType === "task" ? "Create Connected Task" : ("Create Connected " + sourceType.charAt(0).toUpperCase() + sourceType.slice(1))

        property string sourceId: ""
        property string sourceType: "task"
        property real dropX: 0
        property real dropY: 0

        onOpened: edgeDropTaskField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: {
                    if (edgeDropTaskDialog.sourceType === "task" && taskModel)
                        return "Create a new task connected from the source item."
                    else
                        return "Create a new " + edgeDropTaskDialog.sourceType + " connected from the source item."
                }
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            TextField {
                id: edgeDropTaskField
                Layout.fillWidth: true
                placeholderText: edgeDropTaskDialog.sourceType === "task" ? "Task name" : (edgeDropTaskDialog.sourceType.charAt(0).toUpperCase() + edgeDropTaskDialog.sourceType.slice(1) + " label")
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                Keys.onReturnPressed: edgeDropTaskDialog.accept()
                Keys.onEnterPressed: edgeDropTaskDialog.accept()
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && edgeDropTaskDialog.sourceId && edgeDropTaskField.text.trim().length > 0) {
                if (edgeDropTaskDialog.sourceType === "task" && taskModel) {
                    var newId = diagramModel.addTaskFromTextAndConnect(
                        edgeDropTaskDialog.sourceId,
                        root.snapValue(edgeDropTaskDialog.dropX),
                        root.snapValue(edgeDropTaskDialog.dropY),
                        edgeDropTaskField.text
                    )
                    if (newId && newId.length > 0) {
                        root.lastCreatedTaskId = newId
                        root.selectedItemId = newId
                    }
                } else {
                    diagramModel.addPresetItemAndConnect(
                        edgeDropTaskDialog.sourceId,
                        edgeDropTaskDialog.sourceType === "task" ? "box" : edgeDropTaskDialog.sourceType,
                        root.snapValue(edgeDropTaskDialog.dropX),
                        root.snapValue(edgeDropTaskDialog.dropY),
                        edgeDropTaskField.text
                    )
                }
            }
            edgeDropTaskDialog.close()
        }
        onRejected: edgeDropTaskDialog.close()

        onClosed: {
            edgeDropTaskField.text = ""
            edgeDropTaskDialog.sourceId = ""
            edgeDropTaskDialog.sourceType = "task"
        }
    }

    FileDialog {
        id: saveDialog
        title: "Save Project As"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Progress files (*.progress)", "All files (*)"]
        defaultSuffix: "progress"
        onAccepted: {
            if (projectManager) {
                projectManager.saveProject(selectedFile)
            }
        }
    }

    FileDialog {
        id: loadDialog
        title: "Load Project"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Progress files (*.progress)", "All files (*)"]
        onAccepted: {
            if (projectManager) {
                projectManager.loadProject(selectedFile)
            }
        }
    }

    FileDialog {
        id: subDiagramFileDialog
        title: "Select Sub-diagram"
        fileMode: FileDialog.OpenFile
        nameFilters: ["Progress files (*.progress)", "All files (*)"]
        onAccepted: {
            if (diagramModel && diagramLayer && diagramLayer.contextMenuItemId) {
                diagramModel.setSubDiagramPath(diagramLayer.contextMenuItemId, selectedFile)
            }
        }
    }

    FileDialog {
        id: newSubDiagramFileDialog
        title: "Create New Sub-diagram"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Progress files (*.progress)", "All files (*)"]
        defaultSuffix: "progress"
        onAccepted: {
            if (diagramModel && diagramLayer && diagramLayer.contextMenuItemId) {
                diagramModel.createAndLinkSubDiagram(diagramLayer.contextMenuItemId, selectedFile)
            }
        }
    }

    Dialog {
        id: clipboardPasteDialog
        property real pasteX: 0
        property real pasteY: 0
        title: "Paste from Clipboard"
        modal: true
        anchors.centerIn: parent
        width: 320

        contentItem: ColumnLayout {
            width: 300
            spacing: 12

            Label {
                text: "Clipboard has multiple lines. Create tasks or boxes?"
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            RowLayout {
                spacing: 10
                Layout.alignment: Qt.AlignHCenter

                Button {
                    text: "Tasks"
                    onClicked: {
                        if (diagramModel)
                            diagramModel.pasteTextFromClipboard(clipboardPasteDialog.pasteX, clipboardPasteDialog.pasteY, true)
                        clipboardPasteDialog.close()
                    }
                }

                Button {
                    text: "Boxes"
                    onClicked: {
                        if (diagramModel)
                            diagramModel.pasteTextFromClipboard(clipboardPasteDialog.pasteX, clipboardPasteDialog.pasteY, false)
                        clipboardPasteDialog.close()
                    }
                }

                Button {
                    text: "Cancel"
                    onClicked: clipboardPasteDialog.close()
                }
            }
        }
    }
}
