import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
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
        parent: Overlay.overlay
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
            else activityCard.refreshName(activity.name)
        }
    }
    function updateGoalDrop(sceneX, sceneY) {
        calendar.externalDropDate = dateAtScene(sceneX, sceneY)
        return calendar.externalDropDate
    }
    function clearGoalDrop() { calendar.externalDropDate = "" }
    function dropGoal(goalId, sceneX, sceneY) {
        var day = dateAtScene(sceneX, sceneY)
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
    function dropNode(nodeId, sceneX, sceneY) {
        var day = dateAtScene(sceneX, sceneY)
        clearGoalDrop()
        if (!day) return false
        // Defer model changes until the node's release handler has returned.
        Qt.callLater(function() {
            var id = planController ? planController.calendarActivityId(nodeId) : ""
            if (!id) { calendarMessage = "This activity is no longer available."; return }
            var existing = scheduledGoals.find(function(g) { return g.id === id })
            var duration = existing ? calendar.dayNumber(existing.endDate) - calendar.dayNumber(existing.startDate) : 0
            var model = rangeModel(id)
            if (model && model.setGoalRange(id, day, calendar.dayKey(calendar.dayNumber(day) + duration))) {
                calendarMessage = ""
                selectDate(day)
            } else calendarMessage = "Could not save dates. Please try again."
        })
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
    GoalRangeDialog { id: goalDialog; parent: Overlay.overlay; goalModel: overview.goalModel; projectManager: overview.projectManager }
    GoalRangeDialog { id: planDialog; parent: Overlay.overlay; objectName: "planRangeDialog"; goalModel: overview.planController; projectManager: overview.projectManager }
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
        weekStart = mondayFor(selectedDate)
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
    property real availableContentHeight: windowRoot && windowRoot.height !== undefined ? windowRoot.height : 800
    implicitHeight: availableContentHeight < 600 ? 88 : 104
    height: implicitHeight
    property string weekStart: ""
    readonly property bool planningOpen: planning.visible
    function mondayFor(key) {
        var n = calendar.dayNumber(key)
        return calendar.dayKey(n - ((new Date(n * 86400000).getUTCDay() + 6) % 7))
    }
    function shiftWeek(amount) { weekStart = calendar.dayKey(calendar.dayNumber(weekStart) + amount * 7) }
    function shortDate(key) {
        var p = key.split("-")
        return Qt.formatDate(new Date(+p[0], +p[1]-1, +p[2]), "d MMM")
    }
    function openPlanning() {
        dayAgenda.close()
        var key = selectedDate || weekStart
        var p = key.split("-")
        calendar.displayedYear = +p[0]; calendar.displayedMonth = +p[1]-1
        planning.open()
    }
    function dateAtScene(x, y) {
        if (planning.visible) return calendar.visible ? calendar.dateAtScene(x, y) : ""
        if (dayAgenda.visible) return ""
        var point = weekDays.mapFromItem(null, x, y)
        if (point.x < 0 || point.x >= weekDays.width || point.y < 0 || point.y >= weekDays.height) return ""
        return calendar.dayKey(calendar.dayNumber(weekStart) + Math.floor(point.x / (weekDays.width / 7)))
    }
    property string deletionError: ""
    function deleteAgendaItem(entry) {
        if (!projectManager || !projectManager.deleteCalendarItem(entry)) {
            deletionError = "Could not delete this item. It may have changed; reopen the daily list and try again."
            return false
        }
        deletionError = ""
        if (windowRoot) windowRoot.refreshActiveReminders()
        return true
    }
    function showDayAgenda(key, item) {
        deletionError = ""
        selectDate(key)
        dayAgenda.anchorItem = item
        dayAgenda.open()
    }

    Rectangle {
        anchors.fill: parent
        color: "#21313d"; radius: 8
        RowLayout {
            id: stripHeader
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 6 }
            height: 30; spacing: 3
            ToolButton { palette.buttonText: "#e0e9ef"; objectName: "previousWeek"; text: "‹"; implicitWidth: 28; implicitHeight: 30; Accessible.name: "Previous week"; onClicked: overview.shiftWeek(-1) }
            ToolButton { palette.buttonText: "#e0e9ef"; objectName: "nextWeek"; text: "›"; implicitWidth: 28; implicitHeight: 30; Accessible.name: "Next week"; onClicked: overview.shiftWeek(1) }
            Label {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                text: overview.calendarMessage && !planning.visible ? overview.calendarMessage : overview.weekStart ? overview.shortDate(overview.weekStart) + " – " + overview.shortDate(calendar.dayKey(calendar.dayNumber(overview.weekStart)+6)) : ""
                color: "#e0e9ef"; font.pixelSize: 12; elide: Text.ElideRight
            }
            ToolButton { palette.buttonText: "#e0e9ef";
                objectName: "clearWeekDate"; visible: overview.selectedDate !== ""
                text: overview.width >= 650 ? overview.shortDate(overview.selectedDate) + " ×" : "×"
                implicitHeight: 30; Accessible.name: "Clear date filter; show all days"
                ToolTip.visible: hovered; ToolTip.text: "Show all days"
                onClicked: overview.selectDate("")
            }
            ToolButton { palette.buttonText: "#e0e9ef";
                objectName: "weekToday"; text: "Today"; implicitHeight: 30; visible: overview.width >= 360
                onClicked: { overview.weekStart = overview.mondayFor(calendar.todayKey); overview.selectDate(calendar.todayKey) }
            }
            ToolButton { palette.buttonText: "#e0e9ef";
                id: monthOpener; objectName: "openPlanningMonth"; text: overview.width < 420 ? "Month" : "Open month"; implicitHeight: 30
                onClicked: overview.openPlanning()
            }
            ToolButton { palette.buttonText: "#e0e9ef"; objectName: "planningActions"; text: "⋮"; implicitWidth: 28; implicitHeight: 30; Accessible.name: "Planning actions"; onClicked: planningActions.popup() }
            Menu {
                id: planningActions
                MenuItem { text: "Today"; visible: overview.width < 360; onTriggered: { overview.weekStart = overview.mondayFor(calendar.todayKey); overview.selectDate(calendar.todayKey) } }
                MenuItem { text: "Add goal"; enabled: !!overview.goalModel; onTriggered: goalDialog.show(null, overview.selectedDate) }
                MenuItem { objectName: "newStandaloneReminder"; text: "New reminder"; onTriggered: overview.dialogs.openStandaloneReminderDialog(overview.selectedDate) }
                MenuItem { text: "Calendar help"; onTriggered: calendarHelp.open() }
            }
        }
        Row {
            id: weekDays
            anchors { left: parent.left; right: parent.right; top: stripHeader.bottom; bottom: parent.bottom; margins: 6; topMargin: 2 }
            Repeater {
                model: overview.weekStart ? 7 : 0
                delegate: Rectangle {
                    id: weekDay
                    required property int index
                    readonly property string key: calendar.dayKey(calendar.dayNumber(overview.weekStart)+index)
                    readonly property int goalCount: calendar.goalCount(key)
                    readonly property int reminderCount: overview.dayCounts[key] || 0
                    objectName: "weekDay_" + key
                    width: weekDays.width/7; height: weekDays.height
                    color: calendar.externalDropDate === key ? "#386a62" : overview.selectedDate === key ? "#354e63" : "transparent"
                    radius: 5
                    border.color: key === calendar.todayKey ? "#7995a7" : "transparent"
                    Button {
                        anchors { left: parent.left; right: parent.right; top: parent.top }
                        height: parent.height - 22; flat: true; padding: 0
                        palette.buttonText: "#e0e9ef"
                        text: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][weekDay.index] + " " + Number(weekDay.key.slice(8))
                        font.pixelSize: overview.width < 500 ? 10 : 12
                        Accessible.name: weekDay.key + ", " + weekDay.goalCount + " goals, " + weekDay.reminderCount + " reminders"
                        onClicked: overview.selectDate(weekDay.key)
                        onDoubleClicked: { overview.selectDate(weekDay.key); goalDialog.show(null, weekDay.key) }
                    }
                    ToolButton { palette.buttonText: "#e0e9ef";
                        id: agendaButton
                        objectName: "weekAgenda_" + weekDay.key
                        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                        height: 22; font.pixelSize: 10; padding: 0
                        text: weekDay.goalCount || weekDay.reminderCount ? weekDay.goalCount + " · " + weekDay.reminderCount : "—"
                        Accessible.name: "Agenda for " + weekDay.key + ": " + weekDay.goalCount + " goals, " + weekDay.reminderCount + " reminders"
                        ToolTip.visible: hovered; ToolTip.text: weekDay.goalCount + " goals · " + weekDay.reminderCount + " reminders"
                        onClicked: overview.showDayAgenda(weekDay.key, agendaButton)
                    }
                }
            }
        }
    }
    Popup {
        id: calendarHelp; parent: Overlay.overlay; anchors.centerIn: parent
        width: Math.min(380, parent.width - 32); modal: true; focus: true
        contentItem: Label { text: "Select a day to filter the map. Open its counts to see activities. Double-click a day to add a goal, or drop a goal or mindmap node onto a date. Open month to drag activities and resize their date ranges. Escape cancels a drag."; wrapMode: Text.WordWrap }
    }
    Popup {
        id: dayAgenda; objectName: "weekAgendaPopup"; parent: Overlay.overlay
        width: Math.min(360, parent.width - 32); height: Math.min(420, parent.height - 32)
        property var anchorItem: null
        readonly property point anchorPoint: anchorItem ? anchorItem.mapToItem(parent, 0, anchorItem.height) : Qt.point(16, 16)
        x: Math.max(16, Math.min(anchorPoint.x, parent.width - width - 16))
        y: Math.max(16, Math.min(anchorPoint.y, parent.height - height - 16))
        padding: 8; focus: true
        onClosed: if (anchorItem) anchorItem.forceActiveFocus()
        background: Rectangle { color: "#21313d"; border.color: "#3b566a"; radius: 8 }
        contentItem: Item { id: popoverAgendaSlot }
    }
    Popup {
        id: planning; objectName: "planningOverlay"; parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(1100, parent.width - 32); height: Math.min(760, parent.height - 32)
        padding: 12; modal: true; focus: true
        closePolicy: calendar.gesture ? Popup.NoAutoClose : Popup.CloseOnEscape
        onClosed: { calendar.cancelGesture(); if (overview.selectedDate) overview.weekStart = overview.mondayFor(overview.selectedDate); monthOpener.forceActiveFocus() }
        background: Rectangle { color: "#192832"; radius: 10; border.color: "#3b566a" }
        contentItem: ColumnLayout {
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Planning"; color: "#e0e9ef"; font.bold: true; Layout.fillWidth: true }
                ToolButton { palette.buttonText: "#e0e9ef"; text: "Add goal"; onClicked: goalDialog.show(null, overview.selectedDate) }
                ToolButton { palette.buttonText: "#e0e9ef"; objectName: "newStandaloneReminder"; text: "New reminder"; onClicked: overview.dialogs.openStandaloneReminderDialog(overview.selectedDate) }
                ToolButton { palette.buttonText: "#e0e9ef"; objectName: "closePlanningMonth"; text: "×"; Accessible.name: "Close planning"; onClicked: planning.close() }
            }
            TabBar {
                id: planningTabs; visible: planning.width < 960; Layout.fillWidth: true
                TabButton { text: "Month" }
                TabButton { objectName: "planningAgendaTab"; text: "Agenda" }
            }
            RowLayout {
                id: calendarContent
                objectName: "reminderCalendarContent"
                Layout.fillWidth: true; Layout.fillHeight: true
                Layout.minimumHeight: 0; Layout.preferredHeight: 0
                spacing: 10
                ReminderCalendar {
                    id: calendar
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    Layout.fillHeight: true
                    Layout.minimumHeight: 0; Layout.preferredHeight: 0
                    Layout.minimumWidth: 0
                    visible: planning.width >= 960 || planningTabs.currentIndex === 0
                    viewportHeightLimit: Math.max(40, calendarContent.height - 100)
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
                    onDateSelected: function(date) { overview.selectDate(date); agenda.contentItem.contentY = 0 }
                    onDateDoubleClicked: function(date) {
                        overview.selectDate(date)
                        goalDialog.show(null, date)
                    }
                }
                Item {
                    id: overlayAgendaSlot
                    visible: planning.width >= 960 || planningTabs.currentIndex === 1
                    Layout.preferredWidth: planning.width >= 960 ? 280 : -1
                    Layout.fillWidth: planning.width < 960
                    Layout.fillHeight: true
                }
            }
        }
    }
    ScrollView {
        id: agenda
        objectName: "planningAgenda"
        parent: dayAgenda.visible ? popoverAgendaSlot : overlayAgendaSlot
        anchors.fill: parent
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
                objectName: "calendarDeletionError"
                visible: overview.deletionError !== ""
                text: overview.deletionError
                width: parent.width; wrapMode: Text.WordWrap; color: "#ffb4a9"
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
                        CheckBox {
                            objectName: "deleteGoal_" + goalRow.modelData.id
                            Accessible.name: "Delete " + goalRow.modelData.name + " from project"
                            ToolTip.visible: hovered; ToolTip.text: Accessible.name
                            onClicked: {
                                checked = false
                                overview.deleteAgendaItem({kind: "goal", id: goalRow.modelData.id})
                            }
                        }
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
            palette.buttonText: "#e0e9ef";
                            objectName: "goalActions_" + goalRow.modelData.id
                            text: "⋮"; Accessible.name: "Actions for " + goalRow.modelData.name
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
                        columns: 3
                        columnSpacing: 8
                        rowSpacing: 4

                        CheckBox {
                            objectName: "deleteReminder_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                            Accessible.name: "Delete " + (reminderRow.entry.title || reminderRow.entry.taskTitle) + " from project"
                            ToolTip.visible: hovered; ToolTip.text: Accessible.name
                            onClicked: {
                                checked = false
                                overview.deleteAgendaItem(reminderRow.entry)
                            }
                        }
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
            palette.buttonText: "#e0e9ef";
                            objectName: "reminderActions_" + (reminderRow.isPlan ? "plan_" : "") + (reminderRow.entry.nodeId || reminderRow.entry.kind)
                            text: "⋮"
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
