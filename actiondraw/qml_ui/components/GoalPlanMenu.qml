import QtQuick 2.15
import QtQuick.Controls 2.15

Menu {
    id: menu
    title: "Add to plan"
    property var controller: null
    property string goalId: ""
    enabled: !!controller && goalId !== ""
    MenuItem {
        objectName: "goalPlanReady"
        text: menu.controller ? menu.controller.planReadyLabel : "Ready"
        onTriggered: menu.controller.addGoalToReady(menu.goalId)
    }
    MenuSeparator {}
    Repeater {
        model: menu.controller ? menu.controller.planHourOptions : []
        delegate: MenuItem {
            required property var modelData
            objectName: "goalPlanHour_" + modelData.hour
            text: modelData.label
            onTriggered: menu.controller.addGoalToPlan(menu.goalId, modelData.hour)
        }
    }
    MenuSeparator {}
    Repeater {
        model: menu.controller ? menu.controller.planWeekdayOptions : []
        delegate: MenuItem {
            required property var modelData
            objectName: "goalPlanWeekday_" + modelData.weekday
            text: modelData.label
            onTriggered: menu.controller.scheduleGoalToWeekday(menu.goalId, modelData.weekday)
        }
    }
}
