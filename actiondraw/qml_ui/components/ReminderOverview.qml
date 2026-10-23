import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Column {
    id: overview
    objectName: "reminderOverview"
    property var windowRoot
    property var projectManager
    property var dialogs
    property var goalModel: null
    readonly property var scheduledGoals: {
        var result = []
        var goals = goalModel ? goalModel.scheduledGoals : []
        var plans = planController && planController.plannedGoals ? planController.plannedGoals : []
        for (var i = 0; i < goals.length; ++i) result.push(goals[i])
        for (var j = 0; j < plans.length; ++j) result.push(plans[j])
        return result.sort(calendar.compareGoals)
    }
    readonly property var filteredGoals: scheduledGoals.filter(function(g) {
        return !overview.selectedDate || (g.startDate <= overview.selectedDate && g.endDate >= overview.selectedDate)
    })
    property var undoChange: null
    property bool savingCalendarRange: false
    property string calendarMessage: ""
    function saveCalendarRange(id, start, end) {
        var before = scheduledGoals.find(function(g) { return g.id === id })
        var model = rangeModel(id)
        if (!before || !model) { calendarMessage = "This activity is no longer available."; return false }
        if (before.startDate === start && before.endDate === end) return true
        // QML model objects may be updated in place by the synchronous model signal.
        var oldStart = String(before.startDate), oldEnd = String(before.endDate)
        savingCalendarRange = true
        var success = model.setGoalRange(id, start, end)
        savingCalendarRange = false
        if (!success) { calendarMessage = "Could not save dates. Please try again."; return false }
        undoChange = {id:id, start:oldStart, end:oldEnd, afterStart:start, afterEnd:end}
        calendarMessage = "Activity dates updated."
        return true
    }
    function undoCalendarRange() {
        var change = undoChange
        if (!change) return
        var current = scheduledGoals.find(function(g) { return g.id === change.id })
        if (!current || current.startDate !== change.afterStart || current.endDate !== change.afterEnd) {
            undoChange = null; calendarMessage = "Dates changed elsewhere; Undo is no longer available."; return
        }
        savingCalendarRange = true
        var model = rangeModel(change.id)
        var success = model && model.setGoalRange(change.id, change.start, change.end)
        savingCalendarRange = false
        if (success) { undoChange = null; calendarMessage = "Date change undone." }
        else calendarMessage = "Could not undo the date change. Try again."
    }
    function selectActivity(id) {
        if (planController && planController.setActivityFilter) planController.setActivityFilter(id)
    }
    function showActivityDetails(id, sceneX, sceneY) {
        var goal = scheduledGoals.find(function(g) { return g.id === id })
        if (!goal) return
        var point = activityCard.parent.mapFromItem(null, sceneX, sceneY)
        activityCard.anchorX = point.x; activityCard.anchorY = point.y
        activityCard.show(goal, "")
    }
    GoalRangeDialog {
        id: activityCard
        objectName: "calendarActivityCard"
        activityCard: true
        saveHandler: overview.saveCalendarRange
        onActivityOpened: function(id) { overview.openGoal(id) }
    }
    onScheduledGoalsChanged: {
        if (!savingCalendarRange && undoChange) {
            var changed = scheduledGoals.find(function(g) { return g.id === undoChange.id })
            if (!changed || changed.startDate !== undoChange.afterStart || changed.endDate !== undoChange.afterEnd) {
                undoChange = null; calendarMessage = "Dates changed elsewhere; Undo is no longer available."
            }
        }
        if (!savingCalendarRange && activityCard.visible) {
            var activity = scheduledGoals.find(function(g) { return g.id === activityCard.goalId })
            if (!activity) activityCard.close()
            else if (activity.startDate !== activityCard.sourceStart || activity.endDate !== activityCard.sourceEnd)
                activityCard.show(activity, "")
        }
        if (windowRoot && scheduledGoals.length && !windowRoot.reminderOverviewTouched)
            windowRoot.reminderOverviewExpanded = true
    }
    function updateGoalDrop(sceneX, sceneY) {
        calendar.externalDropDate = calendar.dateAtScene(sceneX, sceneY)
        return calendar.externalDropDate
    }
    function clearGoalDrop() { calendar.externalDropDate = "" }
    function dropGoal(goalId, sceneX, sceneY) {
        var day = calendar.dateAtScene(sceneX, sceneY)
        clearGoalDrop()
        if (!day) return false
        if (!goalModel || !goalId) return true
        var index = goalModel.goalIndex(goalId)
        if (index < 0) return true
        var goal = goalModel.getTabSummary(index)
        var duration = goal.goalStartDate && goal.goalEndDate
            ? calendar.dayNumber(goal.goalEndDate) - calendar.dayNumber(goal.goalStartDate) : 0
        if (goalModel.setGoalRange(goalId, day, calendar.dayKey(calendar.dayNumber(day) + duration)))
            selectDate(day)
        return true
    }
    function rangeModel(id) { return id.indexOf("plan:") === 0 ? planController : goalModel }
    function openGoal(id) {
        if (id.indexOf("plan:") === 0) {
            projectManager.openMindmapReminder(id.slice(5))
            return
        }
        if (goalModel && projectManager) {
            var index = goalModel.goalIndex(id)
            if (index >= 0) projectManager.switchTab(index)
        }
    }
    GoalRangeDialog { id: goalDialog; goalModel: overview.goalModel; projectManager: overview.projectManager }
    GoalRangeDialog { id: planDialog; objectName: "planRangeDialog"; goalModel: overview.planController; projectManager: overview.projectManager }
    property var planController
    property double nowTimestamp: Date.now() / 1000
    property string selectedDate: ""
    property bool initializingDate: true
    function applyDateFilter() {
        if (planController && planController.setDateFilter) planController.setDateFilter(selectedDate)
    }
    function selectDate(day) {
        calendar.selectedGoalId = ""
        // Selecting the already-highlighted initial day must still filter the map.
        if (selectedDate === day) applyDateFilter()
        else selectedDate = day
    }
    Component.onCompleted: {
        selectedDate = calendar.dateKey(new Date(nowTimestamp * 1000))
        initializingDate = false
        syncAgendaReminders()
    }
    onSelectedDateChanged: if (!initializingDate) applyDateFilter()
    readonly property var futureReminders: {
        var entries = windowRoot ? windowRoot.activeReminders : []
        return entries.filter(function(entry) { return Number(entry.reminderAt) > overview.nowTimestamp })
    }
    readonly property var dayCounts: {
        var counts = {}
        futureReminders.forEach(function(entry) {
            var key = calendar.dateKey(new Date(Number(entry.reminderAt) * 1000))
            counts[key] = (counts[key] || 0) + 1
        })
        return counts
    }
    readonly property var filteredReminders: futureReminders.filter(function(entry) {
        return !overview.selectedDate || calendar.dateKey(new Date(Number(entry.reminderAt) * 1000)) === overview.selectedDate
    }).sort(function(a, b) { return Number(a.reminderAt) - Number(b.reminderAt) })
    // Update reminder roles in place so countdown ticks do not destroy open menus.
    ListModel { id: agendaReminders; dynamicRoles: true }
    function syncAgendaReminders() {
        for (var i = 0; i < filteredReminders.length; ++i) {
            var entry = filteredReminders[i]
            var key = entry.kind + ":" + (entry.nodeId ||
                (entry.kind === "standalone" ? entry.standaloneIndex : entry.tabIndex + ":" + entry.taskIndex))
            var found = -1
            for (var j = i; j < agendaReminders.count; ++j) {
                if (agendaReminders.get(j).key === key) { found = j; break }
            }
            if (found < 0) agendaReminders.insert(i, {key: key, entry: entry})
            else {
                if (found !== i) agendaReminders.move(found, i, 1)
                agendaReminders.setProperty(i, "entry", entry)
            }
        }
        if (agendaReminders.count > filteredReminders.length)
            agendaReminders.remove(filteredReminders.length, agendaReminders.count - filteredReminders.length)
    }
    onFilteredRemindersChanged: syncAgendaReminders()
    Connections {
        target: overview.windowRoot
        function onActiveRemindersChanged() { overview.nowTimestamp = Date.now() / 1000 }
    }
    spacing: 6

    Rectangle {
        width: overview.width
        height: reminderHeader.implicitHeight + 12
        radius: 8
        color: "#21313d"
        border.color: "#3b566a"
        visible: !!overview.projectManager

        Flow {
            id: reminderHeader
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 6
            spacing: 10

            Label {
                text: "Planning"
                color: "#ffe4c7"
                font.pixelSize: 12
                font.bold: true
                height: newReminderButton.implicitHeight
                verticalAlignment: Text.AlignVCenter
            }
            Button {
                text: "Add goal"
                visible: !!overview.goalModel
                onClicked: goalDialog.show(null, overview.selectedDate)
            }
            Button {
                id: newReminderButton
                objectName: "newStandaloneReminder"
                text: "New reminder"
                onClicked: overview.dialogs.openStandaloneReminderDialog(overview.selectedDate)
            }
            Button {
                objectName: "toggleReminderOverview"
                text: overview.windowRoot.reminderOverviewExpanded ? "Roll Up" : "Roll Down"
                onClicked: {
                    overview.windowRoot.reminderOverviewExpanded = !overview.windowRoot.reminderOverviewExpanded
                    overview.windowRoot.reminderOverviewTouched = true
                }
            }
        }
    }

    GridLayout {
        id: calendarContent
        objectName: "reminderCalendarContent"
        width: overview.width
        columns: overview.width >= 960 ? 2 : 1
        columnSpacing: 10
        rowSpacing: 6
        visible: !!overview.windowRoot && overview.windowRoot.reminderOverviewExpanded

        ReminderCalendar {
            id: calendar
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignTop
            Layout.minimumWidth: 0
            viewportHeightLimit: overview.windowRoot && overview.windowRoot.height !== undefined
                ? Math.max(130, Math.min(624, overview.windowRoot.height * (calendarContent.columns === 2 ? 0.5 : 0.3) - reminderHeader.implicitHeight))
                : 624
            goals: overview.scheduledGoals
            onGoalOpened: function(id) { overview.openGoal(id) }
            onActivityRequested: function(id, sceneX, sceneY) { overview.selectActivity(id) }
            onActivityDetailsRequested: function(id, sceneX, sceneY) { overview.showActivityDetails(id, sceneX, sceneY) }
            onRangeEdited: function(id, start, end) { overview.saveCalendarRange(id, start, end) }
            statusMessage: overview.calendarMessage
            undoAvailable: overview.undoChange !== null
            onUndoRequested: overview.undoCalendarRange()
            onStatusDismissed: overview.calendarMessage = ""
            dayCounts: overview.dayCounts
            nowTimestamp: overview.nowTimestamp
            selectedDate: overview.selectedDate
            onDateSelected: function(date) { overview.selectDate(date); agenda.contentItem.contentY = 0; agenda.forceActiveFocus() }
            onDateDoubleClicked: function(date) {
                overview.selectDate(date)
                goalDialog.show(null, date)
            }
        }
        ScrollView {
            id: agenda
            objectName: "planningAgenda"
            Layout.fillWidth: calendarContent.columns === 1
            Layout.preferredWidth: calendarContent.columns === 2 ? 300 : -1
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignTop
            Layout.preferredHeight: calendarContent.columns === 2 ? calendar.implicitHeight : Math.min(180, agendaRows.implicitHeight)
            clip: true
            padding: 6
            background: Rectangle { color: "#21313d"; radius: 6 }
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            onActiveFocusChanged: if (activeFocus) contentItem.contentY = 0
            Column {
                id: agendaRows
                width: agenda.availableWidth
                spacing: 4
                Label {
                    text: overview.selectedDate || "All scheduled items"
                    color: "#e0e9ef"; font.bold: true
                }
                Label {
                    objectName: "reminderEmptyDay"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    visible: overview.filteredReminders.length === 0 && overview.filteredGoals.length === 0
                    text: overview.selectedDate ? "No goals or reminders for this day" : "No scheduled goals or waiting reminders"
                    color: "#9aafbd"
                }
                Label { text: "Goals · " + overview.filteredGoals.length; color: "#9aafbd" }
                Repeater {
                    model: overview.filteredGoals
                    delegate: Rectangle {
                        id: goalRow
                        required property var modelData
                        width: agendaRows.width; height: 52
                        radius: 4; color: "#263744"
                        border.color: calendar.selectedGoalId === modelData.id ? "#7dbde8" : "transparent"
                        RowLayout {
                            anchors.fill: parent; anchors.margins: 4
                            Button {
                                objectName: "openGoal_" + goalRow.modelData.id
                                Layout.fillWidth: true; Layout.minimumWidth: 0
                                flat: true
                                Accessible.name: goalRow.modelData.name
                                ToolTip.visible: hovered
                                ToolTip.text: goalRow.modelData.name
                                contentItem: Column {
                                    Text { width: parent.width; text: goalRow.modelData.name; elide: Text.ElideRight; color: "#e0e9ef"; font.pixelSize: 12 }
                                    Text { width: parent.width; text: goalRow.modelData.startDate + " → " + goalRow.modelData.endDate; elide: Text.ElideRight; color: "#9aafbd"; font.pixelSize: 10 }
                                }
                                onClicked: {
                                    var point = mapToItem(null, 0, height)
                                    calendar.showActivity(goalRow.modelData.id, point.x, point.y)
                                }
                            }
                            ToolButton {
                                objectName: "goalActions_" + goalRow.modelData.id
                                text: "⋮"; palette.buttonText: "#c5d5df"; Accessible.name: "Actions for " + goalRow.modelData.name
                                onClicked: goalActions.popup()
                            }
                        }
                        Menu {
                            id: goalActions
                            MenuItem { objectName: "editGoalRange_" + goalRow.modelData.id; text: "Edit time range"; onTriggered: (goalRow.modelData.nodeId ? planDialog : goalDialog).show(goalRow.modelData, "") }
                            MenuItem { objectName: "clearGoalRange_" + goalRow.modelData.id; text: "Remove time range"; onTriggered: overview.rangeModel(goalRow.modelData.id).clearGoalRange(goalRow.modelData.id) }
                        }
                    }
                }
                Label { text: "Reminders · " + overview.filteredReminders.length; color: "#9aafbd" }
                Repeater {
                    model: agendaReminders
                    delegate: Rectangle {
                        id: reminderRow
                        required property var entry
                        readonly property bool isPlan: entry.kind === "kanban_schedule"
                        objectName: "reminderRow_" + (isPlan ? "plan_" : "") + (entry.nodeId || entry.kind)
                        width: agendaRows.width
                        height: 64
                        radius: 6
                        color: "#263744"
                        border.color: "#304450"

                        Menu {
                            id: rescheduleMenu
                            objectName: "reschedulePlanMenu_" + reminderRow.entry.nodeId
                            Repeater {
                                model: overview.planController ? overview.planController.planWeekdayOptions : []
                                delegate: MenuItem {
                                    required property var modelData
                                    objectName: "reschedulePlanWeekday_" + reminderRow.entry.nodeId + "_" + modelData.weekday
                                    text: modelData.label
                                    onTriggered: overview.planController.scheduleNodeToWeekday(
                                        reminderRow.entry.nodeId, modelData.weekday)
                                }
                            }
                        }

                        GridLayout {
                            id: rowContent
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 6
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 4

                            Column {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 1
                                Text {
                                    width: parent.width
                                    text: "[" + reminderRow.entry.tabName + "] " + (reminderRow.entry.title || reminderRow.entry.taskTitle)
                                    color: "#fff7ef"
                                    font.pixelSize: 11
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: "Due in " + (reminderRow.entry.countdownText || "0:00")
                                    color: "#ffe3a8"
                                    font.pixelSize: 10
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: (reminderRow.isPlan ? "Add and notify at " : "Remind at ") + reminderRow.entry.reminderText
                                    color: "#f1c892"
                                    font.pixelSize: 10
                                    elide: Text.ElideRight
                                }
                            }
                            ToolButton {
                                objectName: "reminderActions_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                                text: "⋮"
                                palette.buttonText: "#c5d5df"
                                Accessible.name: "Actions for " + (reminderRow.entry.title || reminderRow.entry.taskTitle)
                                onClicked: reminderActions.popup()
                            }
                            Menu {
                                id: reminderActions
                                MenuItem {
                                    objectName: "openReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                                    text: reminderRow.isPlan || reminderRow.entry.kind === "mindmap" ? "Open Node" : "Open Task"
                                    visible: reminderRow.entry.kind !== "standalone"
                                    onTriggered: {
                                        var data = reminderRow.entry
                                        if (reminderRow.isPlan || data.kind === "mindmap")
                                            overview.projectManager.openMindmapReminder(data.nodeId)
                                        else
                                            overview.projectManager.openTabTask(Number(data.tabIndex), Number(data.taskIndex))
                                    }
                                }
                                MenuItem {
                                    objectName: "editReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                                    text: reminderRow.isPlan ? "Reschedule" : "Edit"
                                    onTriggered: {
                                        var data = reminderRow.entry
                                        if (reminderRow.isPlan)
                                            rescheduleMenu.popup()
                                        else if (data.kind === "mindmap")
                                            overview.dialogs.openMindmapReminderDialog(data.nodeId, data.reminderText, data.sendNotification)
                                        else if (data.kind === "standalone")
                                            overview.dialogs.openStandaloneReminderEditDialog(Number(data.standaloneIndex), data.title || data.taskTitle, data.reminderText, data.sendNotification || false)
                                        else
                                            overview.dialogs.openTaskReminderEditDialog(Number(data.tabIndex), Number(data.taskIndex), data.reminderText, data.sendNotification || false)
                                    }
                                }
                                MenuItem {
                                    objectName: "clearReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                                    text: reminderRow.isPlan ? "Cancel" : "Clear"
                                    onTriggered: {
                                        var data = reminderRow.entry
                                        var host = overview.windowRoot
                                        var manager = overview.projectManager
                                        if (reminderRow.isPlan)
                                            overview.planController.cancelPlanSchedule(data.nodeId)
                                        else if (data.kind === "mindmap")
                                            manager.clearMindmapReminder(data.nodeId)
                                        else if (data.kind === "standalone")
                                            manager.clearStandaloneReminder(Number(data.standaloneIndex))
                                        else
                                            manager.clearReminder(Number(data.tabIndex), Number(data.taskIndex))
                                        host.refreshActiveReminders()
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
