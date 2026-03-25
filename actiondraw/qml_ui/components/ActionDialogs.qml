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
    property var edgeCanvas: null
    property var monthNames: [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    property var weekdayNames: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    property alias addDialog: addDialog
    property alias boxDialog: boxDialog
    property alias edgeDescriptionDialog: edgeDescriptionDialog
    property alias taskDialog: taskDialog
    property alias newTaskDialog: newTaskDialog
    property alias quickTaskDialog: quickTaskDialog
    property alias breakdownDialog: breakdownDialog
    property alias taskRenameDialog: taskRenameDialog
    property alias timerDialog: timerDialog
    property alias timerContextMenu: timerContextMenu
    property alias reminderDialog: reminderDialog
    property alias reminderContextMenu: reminderContextMenu
    property alias notificationSettingsDialog: notificationSettingsDialog
    property alias contractDialog: contractDialog
    property alias contractContextMenu: contractContextMenu
    property alias edgeDropMenu: edgeDropMenu
    property alias edgeDropTaskDialog: edgeDropTaskDialog
    property alias saveDialog: saveDialog
    property alias loadDialog: loadDialog
    property alias folderDialog: folderDialog
    property alias clipboardPasteDialog: clipboardPasteDialog
    property bool anyDialogVisible: (
        addDialog.visible
        || boxDialog.visible
        || edgeDescriptionDialog.visible
        || taskDialog.visible
        || newTaskDialog.visible
        || quickTaskDialog.visible
        || breakdownDialog.visible
        || taskRenameDialog.visible
        || timerDialog.visible
        || reminderDialog.visible
        || notificationSettingsDialog.visible
        || contractDialog.visible
        || edgeDropTaskDialog.visible
        || clipboardPasteDialog.visible
        || saveDialog.visible
        || loadDialog.visible
    )

    anchors.fill: parent

    function formatDateValue(dateObj) {
        return Qt.formatDateTime(dateObj, "yyyy-MM-dd")
    }

    function formatTimeValue(dateObj) {
        return Qt.formatDateTime(dateObj, "HH:mm")
    }

    function parseDateValue(dateValue) {
        var trimmed = dateValue ? dateValue.trim() : ""
        var match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed)
        if (match) {
            var year = parseInt(match[1], 10)
            var monthIndex = parseInt(match[2], 10) - 1
            var day = parseInt(match[3], 10)
            var parsed = new Date(year, monthIndex, day, 12, 0, 0, 0)
            if (!isNaN(parsed.getTime()) && parsed.getFullYear() === year && parsed.getMonth() === monthIndex && parsed.getDate() === day)
                return parsed
        }
        var now = new Date()
        return new Date(now.getFullYear(), now.getMonth(), now.getDate(), 12, 0, 0, 0)
    }

    function roundedCurrentTime() {
        var now = new Date()
        var roundedMinute = Math.ceil(now.getMinutes() / 5) * 5
        if (roundedMinute >= 60) {
            now.setHours(now.getHours() + 1)
            roundedMinute = 0
        }
        return new Date(
            now.getFullYear(),
            now.getMonth(),
            now.getDate(),
            now.getHours(),
            roundedMinute,
            0,
            0
        )
    }

    function parseTimeValue(timeValue) {
        var trimmed = timeValue ? timeValue.trim() : ""
        var match = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(trimmed)
        if (match) {
            var parsed = dialogHost.roundedCurrentTime()
            parsed.setHours(parseInt(match[1], 10))
            parsed.setMinutes(parseInt(match[2], 10))
            parsed.setSeconds(0)
            parsed.setMilliseconds(0)
            return parsed
        }
        return dialogHost.roundedCurrentTime()
    }

    function daysInMonth(year, monthIndex) {
        return new Date(year, monthIndex + 1, 0).getDate()
    }

    function firstDayOffset(year, monthIndex) {
        return (new Date(year, monthIndex, 1).getDay() + 6) % 7
    }

    function calendarCellDay(cellIndex, year, monthIndex) {
        var offset = dialogHost.firstDayOffset(year, monthIndex)
        var dayNumber = cellIndex - offset + 1
        if (dayNumber < 1 || dayNumber > dialogHost.daysInMonth(year, monthIndex))
            return 0
        return dayNumber
    }

    function openDatePicker(targetDialog) {
        if (!targetDialog)
            return
        datePickerPopup.targetDialog = targetDialog
        var currentDate = dialogHost.parseDateValue(targetDialog.dateValue)
        datePickerPopup.displayYear = currentDate.getFullYear()
        datePickerPopup.displayMonth = currentDate.getMonth()
        datePickerPopup.selectedDay = currentDate.getDate()
        datePickerPopup.open()
    }

    function openTimePicker(targetDialog) {
        if (!targetDialog)
            return
        timePickerPopup.targetDialog = targetDialog
        var currentTime = dialogHost.parseTimeValue(targetDialog.timeValue)
        timePickerPopup.selectedHour = currentTime.getHours()
        timePickerPopup.selectedMinute = currentTime.getMinutes()
        timePickerPopup.open()
    }

    Popup {
        id: datePickerPopup
        modal: true
        focus: true
        padding: 12
        width: 320
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        property var targetDialog: null
        property int displayYear: 0
        property int displayMonth: 0
        property int selectedDay: 0

        function applySelection(day) {
            if (!targetDialog || day <= 0)
                return
            targetDialog.dateValue = dialogHost.formatDateValue(new Date(displayYear, displayMonth, day, 12, 0, 0, 0))
            selectedDay = day
            close()
        }

        background: Rectangle {
            radius: 8
            color: "#1b2028"
            border.color: "#384458"
        }

        contentItem: ColumnLayout {
            spacing: 10

            RowLayout {
                Layout.fillWidth: true

                Button {
                    text: "<"
                    onClicked: {
                        if (datePickerPopup.displayMonth === 0) {
                            datePickerPopup.displayMonth = 11
                            datePickerPopup.displayYear -= 1
                        } else {
                            datePickerPopup.displayMonth -= 1
                        }
                    }
                }

                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: dialogHost.monthNames[datePickerPopup.displayMonth] + " " + datePickerPopup.displayYear
                    color: "#f5f6f8"
                    font.bold: true
                }

                Button {
                    text: ">"
                    onClicked: {
                        if (datePickerPopup.displayMonth === 11) {
                            datePickerPopup.displayMonth = 0
                            datePickerPopup.displayYear += 1
                        } else {
                            datePickerPopup.displayMonth += 1
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Repeater {
                    model: dialogHost.weekdayNames

                    delegate: Label {
                        required property string modelData
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: modelData
                        color: "#8a93a5"
                        font.pixelSize: 11
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 7
                columnSpacing: 6
                rowSpacing: 6

                Repeater {
                    model: 42

                    delegate: Button {
                        id: dayButton
                        required property int index
                        readonly property int dayNumber: dialogHost.calendarCellDay(index, datePickerPopup.displayYear, datePickerPopup.displayMonth)
                        readonly property bool isSelected: {
                            if (!datePickerPopup.targetDialog || dayNumber <= 0)
                                return false
                            var selectedDate = dialogHost.parseDateValue(datePickerPopup.targetDialog.dateValue)
                            return selectedDate.getFullYear() === datePickerPopup.displayYear
                                && selectedDate.getMonth() === datePickerPopup.displayMonth
                                && selectedDate.getDate() === dayNumber
                        }

                        Layout.fillWidth: true
                        Layout.preferredHeight: 32
                        enabled: dayNumber > 0
                        text: dayNumber > 0 ? String(dayNumber) : ""

                        background: Rectangle {
                            radius: 4
                            color: dayButton.isSelected ? "#e67e22" : "#1a2230"
                            border.color: dayButton.enabled ? (dayButton.isSelected ? "#d35400" : "#4b5b72") : "#222a36"
                        }

                        contentItem: Text {
                            text: dayButton.text
                            color: dayButton.enabled ? "#f5f6f8" : "#4b5b72"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }

                        onClicked: datePickerPopup.applySelection(dayNumber)
                    }
                }
            }

            Button {
                Layout.alignment: Qt.AlignRight
                text: "Cancel"
                onClicked: datePickerPopup.close()
            }
        }
    }

    Popup {
        id: timePickerPopup
        modal: true
        focus: true
        padding: 12
        width: 280
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        property var targetDialog: null
        property int selectedHour: 0
        property int selectedMinute: 0

        function applySelection() {
            if (!targetDialog)
                return
            var selected = new Date(2000, 0, 1, selectedHour, selectedMinute, 0, 0)
            targetDialog.timeValue = dialogHost.formatTimeValue(selected)
            close()
        }

        onOpened: {
            hourSpinBox.value = selectedHour
            minuteSpinBox.value = selectedMinute
        }

        onSelectedHourChanged: {
            if (hourSpinBox.value !== selectedHour)
                hourSpinBox.value = selectedHour
        }

        onSelectedMinuteChanged: {
            if (minuteSpinBox.value !== selectedMinute)
                minuteSpinBox.value = selectedMinute
        }

        background: Rectangle {
            radius: 8
            color: "#1b2028"
            border.color: "#384458"
        }

        contentItem: ColumnLayout {
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: "Select time"
                color: "#f5f6f8"
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
            }

            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 12

                SpinBox {
                    id: hourSpinBox
                    from: 0
                    to: 23
                    editable: true

                    validator: IntValidator {
                        bottom: 0
                        top: 23
                    }

                    textFromValue: function(value) {
                        return value < 10 ? "0" + value : String(value)
                    }

                    valueFromText: function(text) {
                        var parsed = parseInt(text, 10)
                        return isNaN(parsed) ? value : parsed
                    }

                    onValueModified: timePickerPopup.selectedHour = value
                }

                Label {
                    text: ":"
                    color: "#f5f6f8"
                    font.pixelSize: 18
                }

                SpinBox {
                    id: minuteSpinBox
                    from: 0
                    to: 59
                    editable: true
                    stepSize: 5

                    validator: IntValidator {
                        bottom: 0
                        top: 59
                    }

                    textFromValue: function(value) {
                        return value < 10 ? "0" + value : String(value)
                    }

                    valueFromText: function(text) {
                        var parsed = parseInt(text, 10)
                        return isNaN(parsed) ? value : parsed
                    }

                    onValueModified: timePickerPopup.selectedMinute = value
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    Layout.fillWidth: true
                    text: "Now"
                    onClicked: {
                        var now = dialogHost.roundedCurrentTime()
                        timePickerPopup.selectedHour = now.getHours()
                        timePickerPopup.selectedMinute = now.getMinutes()
                    }
                }

                Button {
                    Layout.fillWidth: true
                    text: "+15m"
                    onClicked: {
                        var base = new Date(2000, 0, 1, timePickerPopup.selectedHour, timePickerPopup.selectedMinute, 0, 0)
                        base.setMinutes(base.getMinutes() + 15)
                        timePickerPopup.selectedHour = base.getHours()
                        timePickerPopup.selectedMinute = base.getMinutes()
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                Button {
                    text: "Cancel"
                    onClicked: timePickerPopup.close()
                }

                Button {
                    text: "Apply"
                    onClicked: timePickerPopup.applySelection()
                }
            }
        }
    }

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
        width: 620
        property real targetX: 0
        property real targetY: 0
        property string editingItemId: ""
        property string textValue: ""
        property string presetName: "box"
        property real dialogHeight: 180
        title: boxDialog.editingItemId.length === 0 ? root.presetTitle(boxDialog.presetName) : "Edit Label"

        Shortcut {
            sequence: "Ctrl+Return"
            enabled: boxDialog.visible
            onActivated: boxDialog.accept()
        }

        Shortcut {
            sequence: "Ctrl+Enter"
            enabled: boxDialog.visible
            onActivated: boxDialog.accept()
        }

        onTextValueChanged: {
            if (boxMarkdownEditor.textValue !== boxDialog.textValue)
                boxMarkdownEditor.textValue = boxDialog.textValue
        }

        onOpened: {
            boxMarkdownEditor.focusEditor()
            if (boxDialog.editingItemId.length > 0)
                boxMarkdownEditor.selectAll()
        }

        contentItem: ColumnLayout {
            width: boxDialog.width - 32
            Layout.fillWidth: true
            spacing: 12

            Label {
                Layout.fillWidth: true
                text: "Markdown supported. Example: ## Heading, **bold**, - list"
                color: "#8fa2c5"
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }

            MarkdownEditorPane {
                id: boxMarkdownEditor
                Layout.fillWidth: true
                Layout.preferredHeight: boxDialog.dialogHeight
                textValue: boxDialog.textValue
                placeholderText: "Label"
                allowCreateTask: true
                sourceItemId: boxDialog.editingItemId
                onTextValueChanged: boxDialog.textValue = textValue
                onCreateTaskRequested: function(selectedText) {
                    if (!diagramModel)
                        return
                    var sourceId = boxDialog.editingItemId
                    if (sourceId.length === 0) {
                        sourceId = diagramModel.addPresetItemWithText(
                            boxDialog.presetName,
                            root.snapValue(boxDialog.targetX),
                            root.snapValue(boxDialog.targetY),
                            boxDialog.textValue
                        )
                        if (sourceId.length === 0)
                            return
                        boxDialog.editingItemId = sourceId
                        boxMarkdownEditor.sourceItemId = sourceId
                    }
                    var newTaskId = diagramModel.createTaskFromMarkdownSelection(sourceId, selectedText)
                    if (newTaskId.length > 0 && root)
                        root.selectedItemId = newTaskId
                }
            }
        }

        footer: DialogButtonBox {
            id: boxDialogButtonBox
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel

            Component.onCompleted: {
                var okButton = boxDialogButtonBox.standardButton(DialogButtonBox.Ok)
                if (okButton)
                    okButton.text = "Save (Ctrl+Enter)"
            }
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
        property bool edgeInsertMode: false
        property string edgeId: ""
        property string edgeFromId: ""
        property string edgeToId: ""

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
                var newId = ""
                var targetX = root.snapValue(quickTaskDialog.targetX)
                var targetY = root.snapValue(quickTaskDialog.targetY)
                if (quickTaskDialog.edgeInsertMode && quickTaskDialog.edgeId.length > 0) {
                    newId = diagramModel.insertTaskOnEdge(
                        quickTaskDialog.edgeId,
                        quickTaskField.text,
                        targetX,
                        targetY
                    )
                } else {
                    newId = diagramModel.addTaskFromText(
                        quickTaskField.text,
                        targetX,
                        targetY
                    )
                }
                if (newId && newId.length > 0) {
                    root.lastCreatedTaskId = newId
                    root.selectedItemId = newId
                    if (edgeCanvas)
                        edgeCanvas.selectedEdgeId = ""
                }
            }
            quickTaskDialog.close()
        }
        onRejected: quickTaskDialog.close()

        onClosed: {
            quickTaskField.text = ""
            quickTaskDialog.edgeInsertMode = false
            quickTaskDialog.edgeId = ""
            quickTaskDialog.edgeFromId = ""
            quickTaskDialog.edgeToId = ""
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

    Dialog {
        id: notificationSettingsDialog
        modal: true
        title: "Notification Settings"
        property string serverValue: ""
        property string topicValue: ""
        property string tokenValue: ""
        readonly property bool topicConfigured: topicValue.trim().length > 0

        onOpened: {
            serverValue = (projectManager && projectManager.ntfyServer) ? projectManager.ntfyServer : "https://ntfy.sh"
            topicValue = (projectManager && projectManager.ntfyTopic) ? projectManager.ntfyTopic : ""
            tokenValue = (projectManager && projectManager.ntfyToken) ? projectManager.ntfyToken : ""
            ntfyServerField.forceActiveFocus()
        }

        contentItem: ColumnLayout {
            width: 380
            spacing: 12

            Label {
                text: "Configure where due reminders should be published when 'Send notification' is enabled."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                id: ntfyHelpBox
                Layout.fillWidth: true
                implicitHeight: ntfyHelpContent.implicitHeight + 24
                radius: 8
                color: "#1a2633"
                border.color: "#3f5870"

                ColumnLayout {
                    id: ntfyHelpContent
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 6

                    Label {
                        text: "What is ntfy?"
                        color: "#f5f6f8"
                        font.bold: true
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "ntfy is a simple push notification service. ActionDraw sends a message to your ntfy topic when a reminder is due."
                        color: "#c9d7e6"
                        wrapMode: Text.WordWrap
                    }

                    Label {
                        Layout.fillWidth: true
                        text: "Set a topic name here, subscribe to the same topic in the ntfy app or web client, and you will receive reminder notifications there."
                        color: "#9fb3c8"
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Label {
                text: "Server"
                color: "#d7e0ea"
            }

            TextField {
                id: ntfyServerField
                Layout.fillWidth: true
                text: notificationSettingsDialog.serverValue
                placeholderText: "https://ntfy.sh"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: notificationSettingsDialog.serverValue = text
            }

            Label {
                text: "Topic"
                color: "#d7e0ea"
            }

            TextField {
                Layout.fillWidth: true
                text: notificationSettingsDialog.topicValue
                placeholderText: "my-topic"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: notificationSettingsDialog.topicValue = text
            }

            Rectangle {
                Layout.fillWidth: true
                visible: !notificationSettingsDialog.topicConfigured
                radius: 6
                color: "#3a2418"
                border.color: "#b16a3c"

                Label {
                    anchors.fill: parent
                    anchors.margins: 10
                    text: "Notifications are not configured until you set an ntfy topic."
                    color: "#ffd9bf"
                    wrapMode: Text.WordWrap
                }
            }

            Label {
                text: "Bearer Token"
                color: "#d7e0ea"
            }

            TextField {
                Layout.fillWidth: true
                text: notificationSettingsDialog.tokenValue
                placeholderText: "Optional"
                selectByMouse: true
                echoMode: TextInput.Password
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: notificationSettingsDialog.tokenValue = text
            }
        }

        footer: Frame {
            padding: 12

            contentItem: RowLayout {
                spacing: 8

                Button {
                    text: "Test notification"
                    enabled: !!projectManager && notificationSettingsDialog.topicConfigured
                    onClicked: {
                        if (!projectManager || !projectManager.sendTestNtfyNotification) {
                            return
                        }
                        var started = projectManager.sendTestNtfyNotification(
                            notificationSettingsDialog.serverValue,
                            notificationSettingsDialog.topicValue,
                            notificationSettingsDialog.tokenValue
                        )
                        if (started && root && root.showSaveNotification) {
                            root.showSaveNotification("Sending test notification...")
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Button {
                    text: "OK"
                    onClicked: notificationSettingsDialog.accept()
                }

                Button {
                    text: "Cancel"
                    onClicked: notificationSettingsDialog.reject()
                }
            }
        }

        onAccepted: {
            if (projectManager && projectManager.saveNtfySettings) {
                projectManager.saveNtfySettings(
                    notificationSettingsDialog.serverValue,
                    notificationSettingsDialog.topicValue,
                    notificationSettingsDialog.tokenValue
                )
            }
            if (!notificationSettingsDialog.topicConfigured && root && root.showSaveNotification) {
                root.showSaveNotification("Notifications are not configured until you set an ntfy topic")
            }
            notificationSettingsDialog.close()
        }
        onRejected: notificationSettingsDialog.close()
    }

    Dialog {
        id: reminderDialog
        modal: true
        title: "Set Reminder"
        width: 420
        property int taskIndex: -1
        property string dateValue: ""
        property string timeValue: ""
        property bool sendNotification: false

        function parseReminderParts(value) {
            var trimmed = value ? value.trim() : ""
            if (!trimmed.length)
                return { date: "", time: "" }
            var parts = trimmed.split(" ")
            if (parts.length < 2)
                return { date: "", time: "" }
            var datePart = parts[0]
            var timePart = parts[1]
            if (timePart.length >= 5)
                timePart = timePart.slice(0, 5)
            return { date: datePart, time: timePart }
        }

        function setToOffsetMinutes(minutesFromNow) {
            var dt = new Date()
            dt.setMinutes(dt.getMinutes() + minutesFromNow)
            reminderDialog.dateValue = Qt.formatDateTime(dt, "yyyy-MM-dd")
            reminderDialog.timeValue = Qt.formatDateTime(dt, "HH:mm")
        }

        onOpened: {
            if (reminderDialog.dateValue.trim().length === 0 || reminderDialog.timeValue.trim().length === 0) {
                setToOffsetMinutes(60)
            }
            reminderDateButton.forceActiveFocus()
        }

        contentItem: ColumnLayout {
            width: 340
            spacing: 12

            Label {
                text: "Set a local date and time reminder."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                id: reminderNotificationWarning
                Layout.fillWidth: true
                visible: reminderDialog.sendNotification && projectManager && !projectManager.ntfyConfigured
                implicitHeight: warningContent.implicitHeight + 24
                radius: 8
                color: reminderDialog.sendNotification ? "#5a2418" : "#3f281c"
                border.color: reminderDialog.sendNotification ? "#ff8a5b" : "#d08a52"
                border.width: 2

                ColumnLayout {
                    id: warningContent
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Label {
                        Layout.fillWidth: true
                        text: reminderDialog.sendNotification ? "Notification Setup Required" : "Notifications Not Configured"
                        color: "#fff1e8"
                        font.bold: true
                    }

                    Label {
                        Layout.fillWidth: true
                        text: reminderDialog.sendNotification
                            ? "This reminder cannot send notifications until you configure Notification Settings."
                            : "Reminder notifications are currently disabled because no ntfy topic is configured."
                        color: "#ffe0cf"
                        wrapMode: Text.WordWrap
                    }

                    Button {
                        text: "Open Notification Settings"
                        onClicked: {
                            reminderDialog.close()
                            notificationSettingsDialog.open()
                        }
                    }
                }
            }

            Button {
                id: reminderDateButton
                Layout.fillWidth: true
                text: reminderDialog.dateValue.trim().length > 0 ? reminderDialog.dateValue : "Select date"
                contentItem: Text {
                    text: parent.text
                    color: "#f5f6f8"
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onClicked: dialogHost.openDatePicker(reminderDialog)
            }

            RowLayout {
                Layout.fillWidth: true

                Button {
                    id: reminderTimeButton
                    text: reminderDialog.timeValue.trim().length > 0 ? reminderDialog.timeValue : "Select time"
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                    }
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 4
                        border.color: "#384458"
                    }
                    onClicked: dialogHost.openTimePicker(reminderDialog)
                }

                TextField {
                    id: reminderTimeField
                    Layout.fillWidth: true
                    text: reminderDialog.timeValue
                    placeholderText: "HH:MM"
                    selectByMouse: true
                    color: "#f5f6f8"
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 4
                        border.color: "#384458"
                    }
                    onTextChanged: reminderDialog.timeValue = text
                    Keys.onReturnPressed: reminderDialog.accept()
                    Keys.onEnterPressed: reminderDialog.accept()
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "+15m"
                    onClicked: reminderDialog.setToOffsetMinutes(15)
                }
                Button {
                    text: "+1h"
                    onClicked: reminderDialog.setToOffsetMinutes(60)
                }
                Button {
                    text: "+1d"
                    onClicked: reminderDialog.setToOffsetMinutes(24 * 60)
                }
            }

            CheckBox {
                Layout.fillWidth: true
                text: "Send notification"
                checked: reminderDialog.sendNotification
                palette.text: "#f5f6f8"
                font.bold: checked || (projectManager && !projectManager.ntfyConfigured)
                onToggled: reminderDialog.sendNotification = checked
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && reminderDialog.taskIndex >= 0) {
                if (reminderDialog.sendNotification && projectManager && !projectManager.ntfyConfigured) {
                    if (root && root.showSaveNotification)
                        root.showSaveNotification("Go to Notification Settings to configure notifications")
                    return
                }
                var reminderValue = reminderDialog.dateValue.trim() + " " + reminderDialog.timeValue.trim()
                if (reminderDialog.dateValue.trim().length > 0 && reminderDialog.timeValue.trim().length > 0) {
                    var saved = diagramModel.setTaskReminderAt(
                        reminderDialog.taskIndex,
                        reminderValue,
                        reminderDialog.sendNotification
                    )
                    if (!saved) {
                        if (root && root.showSaveNotification)
                            root.showSaveNotification("Invalid reminder. Use YYYY-MM-DD and HH:MM")
                        return
                    }
                }
            }
            reminderDialog.close()
        }
        onRejected: reminderDialog.close()

        onClosed: {
            reminderDialog.taskIndex = -1
            reminderDialog.dateValue = ""
            reminderDialog.timeValue = ""
            reminderDialog.sendNotification = false
        }
    }

    Menu {
        id: reminderContextMenu
        property int taskIndex: -1
        property string reminderAt: ""

        function openEditor() {
            if (reminderContextMenu.taskIndex < 0)
                return
            reminderDialog.taskIndex = reminderContextMenu.taskIndex
            var parts = reminderDialog.parseReminderParts(reminderContextMenu.reminderAt)
            reminderDialog.dateValue = parts.date
            reminderDialog.timeValue = parts.time
            reminderDialog.sendNotification = (
                diagramModel
                && diagramModel.isTaskReminderNotificationEnabled
                && diagramModel.isTaskReminderNotificationEnabled(reminderContextMenu.taskIndex)
            ) || false
            reminderDialog.open()
        }

        MenuItem {
            text: reminderContextMenu.reminderAt && reminderContextMenu.reminderAt.length > 0 ? "Update Reminder" : "Set Reminder"
            onTriggered: reminderContextMenu.openEditor()
        }

        MenuItem {
            text: "Clear Reminder"
            visible: reminderContextMenu.reminderAt && reminderContextMenu.reminderAt.length > 0
            onTriggered: {
                if (diagramModel && reminderContextMenu.taskIndex >= 0) {
                    diagramModel.clearTaskReminderAt(reminderContextMenu.taskIndex)
                }
            }
        }
    }

    Dialog {
        id: contractDialog
        modal: true
        title: "Set Contract"
        property int taskIndex: -1
        property string dateValue: ""
        property string timeValue: ""
        property string punishmentValue: ""
        property string punishmentMode: "fixed"
        property var fixedPunishmentOptions: [
            { value: "coffee", label: "Coffee", icon: "\u2615" },
            { value: "tv", label: "TV", icon: "\ud83d\udcfa" },
            { value: "cacao", label: "Cacao", icon: "\ud83c\udf6b" },
            { value: "chocolate", label: "Chocolate", icon: "\ud83c\udf6c" },
            { value: "soda", label: "Soda", icon: "\ud83e\udd64" },
            { value: "cigar/snus", label: "Cigar / Snus", icon: "\ud83d\udebc" }
        ]
        property var fixedPunishmentIcons: ({
            "coffee": "\u2615",
            "tv": "\ud83d\udcfa",
            "cacao": "\ud83c\udf6b",
            "chocolate": "\ud83c\udf6c",
            "soda": "\ud83e\udd64",
            "cigar/snus": "\ud83d\udebc"
        })

        function normalizedPunishmentValue(value) {
            return value ? value.trim().toLowerCase() : ""
        }

        function isFixedPunishment(value) {
            return fixedPunishmentIcons[normalizedPunishmentValue(value)] !== undefined
        }

        function punishmentDisplayText(value) {
            var trimmed = value ? value.trim() : ""
            if (!trimmed.length)
                return ""
            var icon = fixedPunishmentIcons[normalizedPunishmentValue(trimmed)]
            return icon ? icon + " " + trimmed : trimmed
        }

        function selectPunishment(value) {
            var trimmed = value ? value.trim() : ""
            punishmentValue = trimmed
            punishmentMode = isFixedPunishment(trimmed) ? "fixed" : "custom"
        }

        function parseDeadlineParts(value) {
            var trimmed = value ? value.trim() : ""
            if (!trimmed.length)
                return { date: "", time: "" }
            var parts = trimmed.split(" ")
            if (parts.length < 2)
                return { date: "", time: "" }
            var datePart = parts[0]
            var timePart = parts[1]
            if (timePart.length >= 5)
                timePart = timePart.slice(0, 5)
            return { date: datePart, time: timePart }
        }

        function setToOffsetMinutes(minutesFromNow) {
            var dt = new Date()
            dt.setMinutes(dt.getMinutes() + minutesFromNow)
            contractDialog.dateValue = Qt.formatDateTime(dt, "yyyy-MM-dd")
            contractDialog.timeValue = Qt.formatDateTime(dt, "HH:mm")
        }

        onOpened: {
            if (contractDialog.dateValue.trim().length === 0 || contractDialog.timeValue.trim().length === 0) {
                setToOffsetMinutes(60)
            }
            contractDateButton.forceActiveFocus()
        }

        contentItem: ColumnLayout {
            width: 340
            spacing: 12

            Label {
                text: "Set an absolute deadline and punishment. Contract is satisfied only when task is completed."
                color: "#8a93a5"
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Label {
                text: "Choose a fixed punishment or enter your own."
                color: "#8a93a5"
                font.pixelSize: 11
                Layout.fillWidth: true
            }

            Button {
                id: contractDateButton
                Layout.fillWidth: true
                text: contractDialog.dateValue.trim().length > 0 ? contractDialog.dateValue : "Select date"
                contentItem: Text {
                    text: parent.text
                    color: "#f5f6f8"
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onClicked: dialogHost.openDatePicker(contractDialog)
            }

            RowLayout {
                Layout.fillWidth: true

                Button {
                    id: contractTimeButton
                    text: contractDialog.timeValue.trim().length > 0 ? contractDialog.timeValue : "Select time"
                    contentItem: Text {
                        text: parent.text
                        color: "#f5f6f8"
                        verticalAlignment: Text.AlignVCenter
                        horizontalAlignment: Text.AlignHCenter
                    }
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 4
                        border.color: "#384458"
                    }
                    onClicked: dialogHost.openTimePicker(contractDialog)
                }

                TextField {
                    id: contractTimeField
                    Layout.fillWidth: true
                    text: contractDialog.timeValue
                    placeholderText: "HH:MM"
                    selectByMouse: true
                    color: "#f5f6f8"
                    background: Rectangle {
                        color: "#1b2028"
                        radius: 4
                        border.color: "#384458"
                    }
                    onTextChanged: contractDialog.timeValue = text
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 8
                rowSpacing: 8

                Repeater {
                    model: contractDialog.fixedPunishmentOptions

                    delegate: Button {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.icon + "  " + modelData.label

                        background: Rectangle {
                            radius: 6
                            color: contractDialog.normalizedPunishmentValue(contractDialog.punishmentValue) === modelData.value
                                && contractDialog.punishmentMode === "fixed"
                                ? "#3c4b63"
                                : "#1b2028"
                            border.width: 1
                            border.color: contractDialog.normalizedPunishmentValue(contractDialog.punishmentValue) === modelData.value
                                && contractDialog.punishmentMode === "fixed"
                                ? "#9eb8e8"
                                : "#384458"
                        }

                        contentItem: Text {
                            text: parent.text
                            color: "#f5f6f8"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            elide: Text.ElideRight
                        }

                        onClicked: contractDialog.selectPunishment(modelData.value)
                    }
                }
            }

            Button {
                id: customPunishmentButton
                Layout.fillWidth: true
                text: contractDialog.punishmentMode === "custom"
                    ? "Custom punishment selected"
                    : "Use custom punishment"
                onClicked: {
                    if (contractDialog.punishmentMode !== "custom"
                            && contractDialog.isFixedPunishment(contractDialog.punishmentValue)) {
                        contractDialog.punishmentValue = ""
                    }
                    contractDialog.punishmentMode = "custom"
                    contractPunishmentField.forceActiveFocus()
                }
            }

            TextField {
                id: contractPunishmentField
                Layout.fillWidth: true
                visible: contractDialog.punishmentMode === "custom"
                text: contractDialog.punishmentMode === "custom" ? contractDialog.punishmentValue : ""
                placeholderText: "Custom punishment if missed"
                selectByMouse: true
                color: "#f5f6f8"
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#384458"
                }
                onTextChanged: {
                    if (contractDialog.punishmentMode === "custom")
                        contractDialog.punishmentValue = text
                }
                Keys.onReturnPressed: contractDialog.accept()
                Keys.onEnterPressed: contractDialog.accept()
            }

            Label {
                Layout.fillWidth: true
                visible: contractDialog.punishmentMode === "fixed" && contractDialog.punishmentValue.trim().length > 0
                text: "Selected punishment: " + contractDialog.punishmentDisplayText(contractDialog.punishmentValue)
                color: "#f0c6c6"
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Button {
                    text: "+15m"
                    onClicked: contractDialog.setToOffsetMinutes(15)
                }
                Button {
                    text: "+1h"
                    onClicked: contractDialog.setToOffsetMinutes(60)
                }
                Button {
                    text: "+1d"
                    onClicked: contractDialog.setToOffsetMinutes(24 * 60)
                }
            }
        }

        footer: DialogButtonBox {
            standardButtons: DialogButtonBox.Ok | DialogButtonBox.Cancel
        }

        onAccepted: {
            if (diagramModel && contractDialog.taskIndex >= 0) {
                var deadlineValue = contractDialog.dateValue.trim() + " " + contractDialog.timeValue.trim()
                var punishmentValue = contractDialog.punishmentValue.trim()
                if (!deadlineValue.trim().length || !punishmentValue.length) {
                    if (root && root.showSaveNotification)
                        root.showSaveNotification("Contract requires datetime and punishment")
                    return
                }
                var saved = diagramModel.setTaskContractAt(contractDialog.taskIndex, deadlineValue, punishmentValue)
                if (!saved) {
                    if (root && root.showSaveNotification)
                        root.showSaveNotification("Invalid contract. Use future YYYY-MM-DD HH:MM and punishment")
                    return
                }
            }
            contractDialog.close()
        }
        onRejected: contractDialog.close()

        onClosed: {
            contractDialog.taskIndex = -1
            contractDialog.dateValue = ""
            contractDialog.timeValue = ""
            contractDialog.punishmentValue = ""
            contractDialog.punishmentMode = "fixed"
        }
    }

    Menu {
        id: contractContextMenu
        property int taskIndex: -1
        property string deadlineAt: ""
        property string punishment: ""

        function openEditor() {
            if (contractContextMenu.taskIndex < 0)
                return
            contractDialog.taskIndex = contractContextMenu.taskIndex
            var parts = contractDialog.parseDeadlineParts(contractContextMenu.deadlineAt)
            contractDialog.dateValue = parts.date
            contractDialog.timeValue = parts.time
            contractDialog.selectPunishment(contractContextMenu.punishment)
            contractDialog.open()
        }

        MenuItem {
            text: contractContextMenu.deadlineAt && contractContextMenu.deadlineAt.length > 0 ? "Update Contract" : "Set Contract"
            onTriggered: contractContextMenu.openEditor()
        }

        MenuItem {
            text: "Clear Contract"
            visible: contractContextMenu.deadlineAt && contractContextMenu.deadlineAt.length > 0
            onTriggered: {
                if (diagramModel && contractContextMenu.taskIndex >= 0) {
                    diagramModel.clearTaskContract(contractContextMenu.taskIndex)
                }
            }
        }
    }

    Menu {
        id: edgeDropMenu
        title: "Create & Connect"

        function connectedDrop(itemKind) {
            var baseX = root.snapValue(root.pendingEdgeDropX)
            var baseY = root.snapValue(root.pendingEdgeDropY)
            if (root && root.resolveConnectedDrop)
                return root.resolveConnectedDrop(root.pendingEdgeSourceId, itemKind, baseX, baseY)
            return Qt.point(baseX, baseY)
        }

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
                    var drop = edgeDropMenu.connectedDrop("obstacle")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "obstacle",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("wish")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "wish",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("chatgpt")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "chatgpt",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("box")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "box",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("note")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "note",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("database")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "database",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("server")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "server",
                        drop.x,
                        drop.y,
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
                    var drop = edgeDropMenu.connectedDrop("cloud")
                    diagramModel.addPresetItemAndConnect(
                        root.pendingEdgeSourceId,
                        "cloud",
                        drop.x,
                        drop.y,
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
        property bool reverseDirection: false

        function connectedDrop(itemKind) {
            var baseX = root.snapValue(edgeDropTaskDialog.dropX)
            var baseY = root.snapValue(edgeDropTaskDialog.dropY)
            if (root && root.resolveConnectedDrop)
                return root.resolveConnectedDrop(edgeDropTaskDialog.sourceId, itemKind, baseX, baseY)
            return Qt.point(baseX, baseY)
        }

        onOpened: edgeDropTaskField.forceActiveFocus()

        contentItem: ColumnLayout {
            width: 320
            spacing: 12

            Label {
                text: {
                    if (edgeDropTaskDialog.sourceType === "task" && taskModel) {
                        if (edgeDropTaskDialog.reverseDirection)
                            return "Create a predecessor task connected into the source item."
                        return "Create a new task connected from the source item."
                    }
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
                    var newId = ""
                    var taskDrop = edgeDropTaskDialog.connectedDrop("task")
                    if (edgeDropTaskDialog.reverseDirection) {
                        newId = diagramModel.addTaskFromText(
                            edgeDropTaskField.text,
                            taskDrop.x,
                            taskDrop.y
                        )
                        if (newId && newId.length > 0) {
                            diagramModel.addEdge(newId, edgeDropTaskDialog.sourceId)
                        }
                    } else {
                        newId = diagramModel.addTaskFromTextAndConnect(
                            edgeDropTaskDialog.sourceId,
                            taskDrop.x,
                            taskDrop.y,
                            edgeDropTaskField.text
                        )
                    }
                    if (newId && newId.length > 0) {
                        root.lastCreatedTaskId = newId
                        root.selectedItemId = newId
                    }
                } else {
                    var presetName = edgeDropTaskDialog.sourceType === "task" ? "box" : edgeDropTaskDialog.sourceType
                    var presetDrop = edgeDropTaskDialog.connectedDrop(presetName)
                    diagramModel.addPresetItemAndConnect(
                        edgeDropTaskDialog.sourceId,
                        presetName,
                        presetDrop.x,
                        presetDrop.y,
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
            edgeDropTaskDialog.reverseDirection = false
        }
    }

    FileDialog {
        id: saveDialog
        title: "Save Project As"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Progress files (*.progress)", "All files (*)"]
        defaultSuffix: "progress"
        onAccepted: {
            var saved = false
            if (projectManager) {
                saved = projectManager.saveProjectAs(selectedFile)
            }
            if (root && root.handleSaveDialogAccepted)
                root.handleSaveDialogAccepted(saved)
        }
        onRejected: {
            if (root && root.handleSaveDialogRejected)
                root.handleSaveDialogRejected()
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

    FolderDialog {
        id: folderDialog
        title: "Select Folder"
        onAccepted: {
            if (diagramModel && diagramLayer && diagramLayer.contextMenuItemId) {
                diagramModel.setFolderPath(diagramLayer.contextMenuItemId, selectedFolder)
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
