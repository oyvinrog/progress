import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    objectName: "goalRangeDialog"
    property var goalModel
    property bool activityCard: false
    property real anchorX: 0
    property real anchorY: 0
    property var saveHandler: null
    property string sourceStart: ""
    property string sourceEnd: ""
    signal activityOpened(string id)
    property var projectManager
    property string goalId: ""
    property var nodeController: null
    property string nodeId: ""
    title: activityCard ? "Activity details" : goalId ? "Edit Goal Time Range" : "Add Goal with Time Range"
    modal: !activityCard
    anchors.centerIn: activityCard ? null : parent
    x: activityCard ? Math.max(8, Math.min(anchorX, parent.width - width - 8)) : 0
    y: activityCard ? Math.max(8, Math.min(anchorY, parent.height - height - 8)) : 0
    width: Math.min(360, parent ? parent.width - 16 : 360)
    function show(goal, selectedDate) {
        nodeId = ""
        goalId = goal ? goal.id : ""
        nameField.text = goal ? goal.name : ""
        var today = selectedDate || Qt.formatDate(new Date(), "yyyy-MM-dd")
        startField.text = goal ? (goal.startDate || goal.goalStartDate || today) : today
        endField.text = goal ? (goal.endDate || goal.goalEndDate || today) : today
        sourceStart = startField.text; sourceEnd = endField.text
        errorLabel.text = ""
        open()
    }
    function showForNode(id, name) {
        goalId = ""
        nodeId = id
        nameField.text = name
        startField.text = Qt.formatDate(new Date(), "yyyy-MM-dd")
        endField.text = startField.text
        sourceStart = startField.text; sourceEnd = endField.text
        errorLabel.text = ""
        open()
    }
    function saveRange() {
        if (nodeId) {
            if (!nodeController || !nodeController.createScheduledGoalFromNode(nodeId, startField.text, endField.text)) {
                errorLabel.text = "Choose a valid end date on or after the start date. The node must still exist and not already be a goal."
                return
            }
            dialog.close()
            return
        }
        if (dialog.saveHandler) {
            if (dialog.saveHandler(dialog.goalId, startField.text, endField.text)) dialog.close()
            else errorLabel.text = "Could not save. Choose a valid end date on or after the start date and try again."
            return
        }
        if (!dialog.goalModel) return
        var id = dialog.goalId
        var ok = id ? dialog.goalModel.setGoalRange(id, startField.text, endField.text)
                    : (id = dialog.goalModel.createScheduledGoal(nameField.text, startField.text, endField.text)) !== ""
        if (!ok) {
            errorLabel.text = "Enter a name and choose an end date on or after the start date."
            return
        }
        if (!dialog.goalId && dialog.projectManager)
            dialog.projectManager.switchTab(dialog.goalModel.goalIndex(id))
        dialog.close()
    }
    onOpened: {
        if (goalId || nodeId) startField.forceActiveFocus()
        else nameField.forceActiveFocus()
    }
    onClosed: datePicker.close()
    Shortcut { sequence: "Return"; enabled: dialog.visible && !datePicker.visible; onActivated: dialog.saveRange() }
    Shortcut { sequence: "Enter"; enabled: dialog.visible && !datePicker.visible; onActivated: dialog.saveRange() }

    Popup {
        id: datePicker
        objectName: "goalDatePicker"
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: 320
        padding: 12
        modal: true
        focus: true
        property var targetField: null
        property int year: 0
        property int month: 0
        function showFor(field) {
            targetField = field
            var parts = field.text.split("-")
            year = Number(parts[0])
            month = Number(parts[1]) - 1
            open()
        }
        function changeMonth(offset) {
            var date = new Date(year, month + offset, 1)
            year = date.getFullYear()
            month = date.getMonth()
        }
        function selectDay(day) {
            targetField.text = year + "-" + ("0" + (month + 1)).slice(-2) + "-" + ("0" + day).slice(-2)
            close()
        }
        onClosed: { if (targetField && dialog.visible) targetField.forceActiveFocus() }
        contentItem: ColumnLayout {
            RowLayout {
                Button { objectName: "goalDatePreviousMonth"; text: "‹"; Accessible.name: "Previous month"; onClicked: datePicker.changeMonth(-1) }
                Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.formatDate(new Date(datePicker.year, datePicker.month, 1), "MMMM yyyy")
                }
                Button { objectName: "goalDateNextMonth"; text: "›"; Accessible.name: "Next month"; onClicked: datePicker.changeMonth(1) }
            }
            GridLayout {
                columns: 7
                Layout.fillWidth: true
                columnSpacing: 2
                rowSpacing: 2
                Repeater {
                    model: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    Label { required property string modelData; text: modelData; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter }
                }
                Repeater {
                    model: 42
                    Button {
                        required property int index
                        readonly property int day: index - ((new Date(datePicker.year, datePicker.month, 1).getDay() + 6) % 7) + 1
                        readonly property bool validDay: day > 0 && day <= new Date(datePicker.year, datePicker.month + 1, 0).getDate()
                        objectName: "goalDateDay_" + day
                        text: validDay ? day : ""
                        enabled: validDay
                        opacity: validDay ? 1 : 0
                        Layout.fillWidth: true
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 32
                        highlighted: validDay && datePicker.targetField
                            && datePicker.targetField.text === datePicker.year + "-" + ("0" + (datePicker.month + 1)).slice(-2) + "-" + ("0" + day).slice(-2)
                        Accessible.name: datePicker.year + "-" + (datePicker.month + 1) + "-" + day
                        onClicked: datePicker.selectDay(day)
                        Keys.onReturnPressed: datePicker.selectDay(day)
                        Keys.onEnterPressed: datePicker.selectDay(day)
                    }
                }
            }
            Button { text: "Cancel"; onClicked: datePicker.close() }
        }
    }
    contentItem: ColumnLayout {
        TextField { id: nameField; objectName: "goalRangeName"; visible: !dialog.activityCard; Layout.fillWidth: true; placeholderText: "Goal name"; readOnly: !!dialog.goalId || !!dialog.nodeId }
        Label { visible: dialog.activityCard; text: nameField.text; Layout.fillWidth: true; wrapMode: Text.WordWrap; font.bold: true }
        Label { text: "Start date (inclusive)" }
        Button { id: startField; objectName: "goalRangeStart"; Layout.fillWidth: true; Accessible.name: "Choose start date: " + text; onClicked: datePicker.showFor(startField) }
        Label { text: "End date (inclusive)" }
        Button { id: endField; objectName: "goalRangeEnd"; Layout.fillWidth: true; Accessible.name: "Choose end date: " + text; onClicked: datePicker.showFor(endField) }
        Label { id: errorLabel; objectName: "goalRangeError"; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#ffaaa0"; visible: text.length > 0 }
        Button {
            visible: dialog.activityCard; text: "Open activity"; objectName: "openCalendarActivity"
            onClicked: { dialog.activityOpened(dialog.goalId); dialog.close() }
        }
        RowLayout {
            Button {
                text: "Save"; objectName: "saveGoalRange"
                onClicked: dialog.saveRange()
            }
            Button { objectName: "cancelGoalRange"; text: "Cancel"; onClicked: dialog.close() }
        }
    }
}
