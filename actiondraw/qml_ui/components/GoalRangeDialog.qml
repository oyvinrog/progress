import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Dialog {
    id: dialog
    objectName: "goalRangeDialog"
    property var goalModel
    property var projectManager
    property string goalId: ""
    title: goalId ? "Edit Goal Time Range" : "Add Goal with Time Range"
    modal: true
    anchors.centerIn: parent
    width: 360
    function show(goal, selectedDate) {
        goalId = goal ? goal.id : ""
        nameField.text = goal ? goal.name : ""
        var today = selectedDate || Qt.formatDate(new Date(), "yyyy-MM-dd")
        startField.text = goal ? (goal.startDate || goal.goalStartDate || today) : today
        endField.text = goal ? (goal.endDate || goal.goalEndDate || today) : today
        errorLabel.text = ""
        open()
    }
    contentItem: ColumnLayout {
        TextField { id: nameField; objectName: "goalRangeName"; Layout.fillWidth: true; placeholderText: "Goal name"; readOnly: !!dialog.goalId }
        Label { text: "Start date (inclusive)"; color: "#ffffff" }
        TextField { id: startField; objectName: "goalRangeStart"; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD"; Accessible.name: "Start date YYYY-MM-DD" }
        Label { text: "End date (inclusive)"; color: "#ffffff" }
        TextField { id: endField; objectName: "goalRangeEnd"; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD"; Accessible.name: "End date YYYY-MM-DD" }
        Label { id: errorLabel; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: "#ffaaa0"; visible: text.length > 0 }
        RowLayout {
            Button {
                text: "Save"; objectName: "saveGoalRange"
                onClicked: {
                    if (!dialog.goalModel) return
                    var id = dialog.goalId
                    var ok = id ? dialog.goalModel.setGoalRange(id, startField.text, endField.text)
                                : (id = dialog.goalModel.createScheduledGoal(nameField.text, startField.text, endField.text)) !== ""
                    if (!ok) { errorLabel.text = "Enter a name and valid YYYY-MM-DD dates; end must be on or after start."; return }
                    if (!dialog.goalId && dialog.projectManager)
                        dialog.projectManager.switchTab(dialog.goalModel.goalIndex(id))
                    dialog.close()
                }
            }
            Button { text: "Cancel"; onClicked: dialog.close() }
        }
    }
}
