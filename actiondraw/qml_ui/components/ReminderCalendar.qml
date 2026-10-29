import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: calendar
    objectName: "reminderCalendar"
    property var dayCounts: ({})
    property var goals: []
    property real viewportHeightLimit: 624
    property double nowTimestamp: Date.now() / 1000
    property string selectedDate: ""
    property int displayedYear: new Date().getFullYear()
    property int displayedMonth: new Date().getMonth()
    readonly property string todayKey: dateKey(new Date(nowTimestamp * 1000))
    readonly property var calendarDays: {
        var offset = (new Date(displayedYear, displayedMonth, 1).getDay() + 6) % 7
        var cells = []
        for (var i = 0; i < 42; ++i) {
            var date = new Date(displayedYear, displayedMonth, 1 - offset + i)
            cells.push({key: dateKey(date), day: date.getDate(), inMonth: date.getMonth() === displayedMonth})
        }
        return cells
    }
    // UTC is used solely as an integer civil-day coordinate, never as a goal timestamp.
    function dayNumber(key) { var p = key.split("-"), d = new Date(0); d.setUTCFullYear(+p[0], +p[1]-1, +p[2]); return Math.floor(d.getTime() / 86400000) }
    function dayKey(n) { return new Date(n * 86400000).toISOString().slice(0, 10) }
    function dateKey(date) { return date.getFullYear() + "-" + ("0"+(date.getMonth()+1)).slice(-2) + "-" + ("0"+date.getDate()).slice(-2) }
    function goalCount(key) { return goals.filter(function(g) { return g.startDate <= key && g.endDate >= key }).length }
    function compareGoals(a, b) {
        return a.startDate.localeCompare(b.startDate) || a.endDate.localeCompare(b.endDate) || a.id.localeCompare(b.id)
    }
    function hiddenCount(key) {
        var cell = calendarDays.findIndex(function(d) { return d.key === key })
        if (cell < 0) return 0
        var column = cell % 7
        return weeks[Math.floor(cell / 7)].hiddenBars.filter(function(b) {
            return column >= b.column && column < b.column + b.span
        }).length
    }
    readonly property int weekHeight: 100
    readonly property int barHeight: 28
    readonly property int lanePitch: 30
    property string selectedGoalId: ""
    property string hoveredGoalId: ""
    property string statusMessage: ""
    property bool undoAvailable: false
    signal undoRequested()
    signal statusDismissed()
    signal activityRequested(string goalId, real sceneX, real sceneY)
    signal activityDetailsRequested(string goalId, real sceneX, real sceneY)
    function showActivity(id, sceneX, sceneY) {
        selectedGoalId = id
        activityRequested(id, sceneX, sceneY)
    }
    onGoalsChanged: {
        var selected = goals.find(function(g) { return g.id === selectedGoalId })
        if (!selected) selectedGoalId = ""
        if (gesture) {
            var current = goals.find(function(g) { return g.id === gesture.id })
            if (!current || dayNumber(current.startDate) !== gesture.start || dayNumber(current.endDate) !== gesture.end)
                cancelGesture()
        }
    }
    function barAt(x, y) {
        var cell = cellAt(x, y)
        if (cell < 0) return null
        var week = weeks[Math.floor(cell / 7)]
        for (var i = 0; i < week.bars.length; ++i) {
            var b = week.bars[i], top = week.top + 22 + b.lane * lanePitch
            var left = b.column * grid.width / 7 + 2, right = (b.column + b.span) * grid.width / 7 - 4
            if (x < left || x > right || y < top || y >= top + barHeight) continue
            return {bar:b, mode:x-left < 24 && b.first ? "start" : right-x < 24 && b.last ? "end" : "move"}
        }
        return null
    }
    function showOverflow(key, item) {
        overflow.date = key
        var point = item.mapToItem(Overlay.overlay, 0, item.height)
        overflow.x = Math.max(8, Math.min(point.x, Overlay.overlay.width - overflow.width - 8))
        overflow.y = Math.max(8, Math.min(point.y, Overlay.overlay.height - overflow.height - 8))
        overflow.open()
    }
    function updateSceneGesture(sceneX, sceneY) {
        var point = grid.mapFromItem(null, sceneX, sceneY)
        updateGesture(point.x, point.y)
        var a = previous.mapFromItem(null, sceneX, sceneY), b = next.mapFromItem(null, sceneX, sceneY)
        hoverMonth = a.x >= 0 && a.x < previous.width && a.y >= 0 && a.y < previous.height ? -1 :
                     b.x >= 0 && b.x < next.width && b.y >= 0 && b.y < next.height ? 1 : 0
        if (point.x > viewport.contentX + viewport.width - 20) viewport.contentX = Math.max(0, Math.min(viewport.contentWidth - viewport.width, viewport.contentX + 8))
        if (point.x < viewport.contentX + 20) viewport.contentX = Math.max(0, viewport.contentX - 8)
        if (point.y > viewport.contentY + viewport.height - 35) viewport.contentY = Math.max(0, Math.min(viewport.contentHeight - viewport.height, viewport.contentY + 8))
        if (point.y < viewport.contentY + 15) viewport.contentY = Math.max(0, viewport.contentY - 8)
    }
    readonly property var weeks: {
        var result = [], top = 0
        for (var w = 0; w < 6; ++w) {
            var start = dayNumber(calendarDays[w*7].key), lanes = [], bars = []
            goals.slice().sort(compareGoals).forEach(function(g) {
                var a = Math.max(start, dayNumber(g.startDate)), b = Math.min(start+6, dayNumber(g.endDate))
                if (a > b) return
                var lane = 0
                while (lane < lanes.length && lanes[lane] >= a) ++lane
                lanes[lane] = b
                bars.push({goal:g, column:a-start, span:b-a+1, lane:lane,
                           first:a === dayNumber(g.startDate), last:b === dayNumber(g.endDate)})
            })
            var h = weekHeight
            result.push({top:top, height:h, bars:bars.filter(function(b) { return b.lane < 2 }), hiddenBars:bars.filter(function(b) { return b.lane >= 2 })})
            top += h
        }
        return result
    }
    readonly property real gridHeight: weeks[5].top + weeks[5].height
    property var gesture: null
    property string previewStart: ""
    property string previewEnd: ""
    property bool validDrop: false
    property int hoverMonth: 0
    property bool moved: false
    signal dateSelected(string date)
    signal dateDoubleClicked(string date)
    signal goalOpened(string goalId)
    signal rangeEdited(string goalId, string startDate, string endDate)

    property string externalDropDate: ""
    function dateAtScene(sceneX, sceneY) {
        if (!visible) return ""
        var point = viewport.mapFromItem(null, sceneX, sceneY)
        if (point.x < 0 || point.y < 0 || point.x >= viewport.width || point.y >= viewport.height) return ""
        point = grid.mapFromItem(null, sceneX, sceneY)
        var cell = cellAt(point.x, point.y)
        return cell < 0 ? "" : calendarDays[cell].key
    }
    function changeMonth(offset) {
        var d = new Date(displayedYear, displayedMonth+offset, 1)
        displayedYear = d.getFullYear(); displayedMonth = d.getMonth()
    }
    function showToday() {
        var d = new Date(nowTimestamp*1000)
        displayedYear = d.getFullYear(); displayedMonth = d.getMonth()
        dateSelected(dateKey(d))
    }
    function cellAt(x, y) {
        if (x < 0 || x >= grid.width || y < 0) return -1
        for (var w=0; w<6; ++w)
            if (y >= weeks[w].top && y < weeks[w].top+weeks[w].height)
                return w*7 + Math.floor(x / (grid.width/7))
        return -1
    }
    function beginGesture(goal, mode, x, y) {
        var cell = cellAt(x,y)
        if (cell < 0) return
        previewStart = goal.startDate; previewEnd = goal.endDate
        gesture = {id:goal.id, mode:mode, start:dayNumber(goal.startDate), end:dayNumber(goal.endDate),
                   anchor:dayNumber(calendarDays[cell].key), x:x, y:y}
        validDrop = true; moved = false
        selectedGoalId = goal.id
        forceActiveFocus()
    }
    function updateGesture(x,y) {
        if (!gesture) return
        if (Math.abs(x-gesture.x)+Math.abs(y-gesture.y)>5) moved = true
        var cell = cellAt(x,y)
        var visiblePoint = grid.mapToItem(viewport,x,y)
        validDrop = cell >= 0 && visiblePoint.x >= 0 && visiblePoint.x < viewport.width && visiblePoint.y >= 0 && visiblePoint.y < viewport.height
        if (!validDrop) return
        var delta = dayNumber(calendarDays[cell].key)-gesture.anchor
        var a=gesture.start, b=gesture.end
        if (gesture.mode === "move") { a+=delta; b+=delta }
        else if (gesture.mode === "start") a=Math.min(b,a+delta)
        else b=Math.max(a,b+delta)
        previewStart=dayKey(a); previewEnd=dayKey(b)
    }
    function finishGesture() {
        if (!gesture) return
        var g=gesture, commit=validDrop && moved
        gesture=null; hoverMonth=0
        if (commit && (previewStart !== dayKey(g.start) || previewEnd !== dayKey(g.end)))
            rangeEdited(g.id,previewStart,previewEnd)
        else if (!moved && validDrop) {
            var point = grid.mapToItem(null, g.x, g.y)
            showActivity(g.id, point.x, point.y)
        }
    }
    function finishOverflowGesture() { finishGesture(); overflow.close() }
    function cancelGesture() { gesture=null; hoverMonth=0; validDrop=false }
    Keys.onEscapePressed: function(event) {
        if (gesture || pointer.pressedCell >= 0 || overflow.visible) {
            cancelGesture(); pointer.pressedCell = -1; overflow.close()
        } else event.accepted = false
    }

    Timer { interval: 650; repeat: true; running: calendar.gesture !== null && calendar.hoverMonth !== 0; onTriggered: calendar.changeMonth(calendar.hoverMonth) }
    implicitHeight: column.implicitHeight+12
    implicitWidth: 700
    color: "#21313d"; border.color: "#3b566a"; radius: 8
    ColumnLayout {
        id: column
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 6 }
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            Button { id: previous; Layout.preferredWidth: 32; objectName: "reminderPreviousMonth"; text:"‹"; Accessible.name:"Previous month"; onClicked: calendar.changeMonth(-1) }
            Label { Layout.fillWidth:true; text: Qt.formatDate(new Date(calendar.displayedYear,calendar.displayedMonth,1),"MMMM yyyy"); color:"#fff7ef"; horizontalAlignment:Text.AlignHCenter }
            Button { id: next; Layout.preferredWidth: 32; objectName:"reminderNextMonth"; text:"›"; Accessible.name:"Next month"; onClicked:calendar.changeMonth(1) }
            Button { objectName:"reminderToday"; text:"Today"; onClicked:calendar.showToday() }
            ToolButton {
                text: "?"
                palette.buttonText: "#c5d5df"
                Accessible.name: "Calendar help"
                ToolTip.visible: hovered || activeFocus
                ToolTip.text: "Double-click a day to add a goal. Drag goals to move, drag ends to resize. Click an activity to select its branch. Use Details to edit its dates. Use + more to see and drag hidden activities. Date changes can be undone. Escape cancels."
            }
            Button { objectName:"reminderAllDays"; text:"All days"; highlighted:calendar.selectedDate===""; onClicked:calendar.dateSelected("") }
            Button {
                objectName: "calendarActivityDetails"
                text: "Details"
                enabled: calendar.selectedGoalId !== ""
                Accessible.name: "Edit selected activity details"
                onClicked: {
                    var point = mapToItem(null, 0, height)
                    calendar.activityDetailsRequested(calendar.selectedGoalId, point.x, point.y)
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: calendar.statusMessage !== ""
            Label { Layout.fillWidth: true; text: calendar.statusMessage; color: "#e0e9ef"; wrapMode: Text.WordWrap }
            Button { objectName: "calendarUndo"; text: "Undo"; visible: calendar.undoAvailable; onClicked: calendar.undoRequested() }
            ToolButton { text: "×"; Accessible.name: "Dismiss notification"; onClicked: calendar.statusDismissed() }
        }
        Label {
            parent: calendar
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            z: 3
            visible: calendar.gesture !== null
            text: calendar.gesture ? calendar.previewStart+" → "+calendar.previewEnd+(calendar.validDrop ? "" : " · Drop on a day to save") : "Double-click a day to add a goal · Drag goals to move · Drag ends to resize · Escape cancels"
            color:"#f1c892"; font.pixelSize:11
        }
        Flickable {
            id: viewport
            Layout.fillWidth:true
            Layout.preferredHeight: Math.min(calendar.gridHeight+24, calendar.viewportHeightLimit)
            contentWidth: Math.max(width, 560)
            contentHeight: calendar.gridHeight+24
            clip:true
            interactive: calendar.gesture === null
            ScrollBar.horizontal: ScrollBar { policy: viewport.contentWidth > viewport.width ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            ScrollBar.vertical: ScrollBar { policy: viewport.contentHeight > viewport.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            Row {
                Repeater {
                    model:["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                    Label { required property string modelData; width:viewport.contentWidth/7; height:24; text:modelData; color:"#f1c892"; horizontalAlignment:Text.AlignHCenter }
                }
            }
            Item {
                id:grid
                y:24; width:viewport.contentWidth; height:calendar.gridHeight
                Repeater {
                    model:calendar.calendarDays
                    delegate: Button {
                        id:day
                        required property var modelData
                        required property int index
                        readonly property int reminderCount: calendar.dayCounts[modelData.key] || 0
                        readonly property int goalsCount: calendar.goalCount(modelData.key)
                        objectName:"reminderDay_"+modelData.key
                        x:(index%7)*grid.width/7; y:calendar.weeks[Math.floor(index/7)].top
                        width:grid.width/7-2; height:calendar.weeks[Math.floor(index/7)].height
                        Accessible.name:modelData.key+", "+goalsCount+" goals, "+reminderCount+" reminders"
                        onClicked: calendar.dateSelected(modelData.key)
                        background:Rectangle {
                            color:calendar.externalDropDate===day.modelData.key ? "#386a62" : calendar.selectedDate===day.modelData.key ? "#354e63" : "#263744"
                            border.color:day.modelData.key===calendar.todayKey ? "#ffe3a8" : "#304450"
                            radius:3
                        }
                        contentItem:Text {
                            text:day.modelData.day + (day.reminderCount > 0 ? "  • " + day.reminderCount : "")
                            color:"#fff7ef"; opacity:day.modelData.inMonth ? 1 : 0.5
                            font.pixelSize:12; verticalAlignment:Text.AlignTop
                        }
                    }
                }
                Repeater {
                    model:calendar.weeks
                    delegate: Item {
                        id:week
                        required property var modelData
                        y:modelData.top; width:grid.width; height:modelData.height
                        Repeater {
                            model:week.modelData.bars
                            delegate:Rectangle {
                                id:bar
                                required property var modelData
                                objectName:"goalBar_"+modelData.goal.id+"_"+modelData.column
                                x:modelData.column*grid.width/7+2; y:22+modelData.lane*calendar.lanePitch
                                readonly property bool focused: modelData.goal.id === calendar.selectedGoalId || modelData.goal.id === calendar.hoveredGoalId
                                width:modelData.span*grid.width/7-6; height:calendar.barHeight; radius:3
                                color:focused ? "#386a62" : "#243d50"; border.color:modelData.goal.color || "#7dbde8"; border.width:1
                                Text { anchors {fill:parent; leftMargin:24; rightMargin:24} text:bar.modelData.goal.name; elide:Text.ElideRight; color:"white"; verticalAlignment:Text.AlignVCenter; font.pixelSize:11 }
                                Text { anchors.verticalCenter: parent.verticalCenter; width: 24; horizontalAlignment: Text.AlignHCenter; visible:bar.modelData.first && bar.focused; text:bar.focused ? "↔" : "│"; color:"white"; anchors.left:parent.left }
                                Text { anchors.verticalCenter: parent.verticalCenter; width: 24; horizontalAlignment: Text.AlignHCenter; visible:bar.modelData.last && bar.focused; text:bar.focused ? "↔" : "│"; color:"white"; anchors.right:parent.right }

                            }
                        }
                    }
                }
                Repeater {
                    model: calendar.gesture && calendar.moved ? calendar.weeks : []
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        readonly property int weekStart: calendar.dayNumber(calendar.calendarDays[index*7].key)
                        readonly property int firstDay: Math.max(weekStart, calendar.dayNumber(calendar.previewStart))
                        readonly property int lastDay: Math.min(weekStart+6, calendar.dayNumber(calendar.previewEnd))
                        visible: lastDay >= firstDay
                        x: (firstDay-weekStart)*grid.width/7+2; y: modelData.top+22
                        width: Math.max(0, lastDay-firstDay+1)*grid.width/7-6; height: calendar.barHeight
                        color: "#663b9588"; border.color: "#9df0d7"; border.width: 2; radius: 3
                    }
                }
                MouseArea {
                    id: pointer
                    anchors.fill: parent
                    property int pressedCell: -1
                    ToolTip {
                        id: activityTooltip
                        objectName: "calendarGoalTooltip"
                        readonly property var goal: calendar.goals.find(function(g) { return g.id === calendar.hoveredGoalId })
                        visible: pointer.containsMouse && !!goal && !calendar.gesture
                        delay: 500
                        text: goal ? goal.name + "\n" + goal.startDate + " → " + goal.endDate : ""
                        x: Math.max(0, Math.min(pointer.mouseX + 12, pointer.width - width))
                        y: pointer.mouseY + 20
                        width: Math.min(implicitWidth, Math.max(160, calendar.width - 24), 420)
                        contentItem: Label {
                            text: activityTooltip.text
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: activityTooltip.palette.toolTipText
                        }
                    }
                    onPressed: function(mouse) {
                        pressedCell=calendar.cellAt(mouse.x,mouse.y)
                        if (pressedCell<0) return
                        var hit = calendar.barAt(mouse.x, mouse.y)
                        if (hit) calendar.beginGesture(hit.bar.goal, hit.mode, mouse.x, mouse.y)
                    }

                    onDoubleClicked: function(mouse) {
                        if (calendar.gesture || calendar.barAt(mouse.x, mouse.y)) return
                        var cell = calendar.cellAt(mouse.x, mouse.y)
                        if (cell < 0) return
                        pressedCell = -1
                        calendar.dateDoubleClicked(calendar.calendarDays[cell].key)
                    }
                    hoverEnabled: true
                    cursorShape: calendar.gesture ? Qt.ClosedHandCursor : (calendar.hoveredGoalId ? Qt.OpenHandCursor : Qt.ArrowCursor)
                    onExited: calendar.hoveredGoalId = ""
                    onPositionChanged: function(mouse) {
                        if (!calendar.gesture) {
                            var hit = calendar.barAt(mouse.x, mouse.y)
                            calendar.hoveredGoalId = hit ? hit.bar.goal.id : ""
                            cursorShape = hit ? (hit.mode === "move" ? Qt.OpenHandCursor : Qt.SizeHorCursor) : Qt.ArrowCursor
                            return
                        }
                        var point = mapToItem(null, mouse.x, mouse.y)
                        calendar.updateSceneGesture(point.x, point.y)
                    }
                    onReleased: function(mouse) {
                        if (calendar.gesture) calendar.finishGesture()
                        else if (pressedCell>=0 && calendar.cellAt(mouse.x,mouse.y)===pressedCell) {
                            var key = calendar.calendarDays[pressedCell].key
                            calendar.dateSelected(key)
                        }
                        pressedCell=-1
                    }
                    onCanceled: { calendar.cancelGesture(); pressedCell=-1 }
                }
                Repeater {
                    model: calendar.calendarDays
                    delegate: ToolButton {
                        required property var modelData
                        required property int index
                        readonly property int hiddenGoals: calendar.hiddenCount(modelData.key)
                        objectName: "calendarMore_" + modelData.key
                        visible: hiddenGoals > 0
                        x: (index % 7) * grid.width / 7 + 2
                        y: calendar.weeks[Math.floor(index / 7)].top + 80
                        width: grid.width / 7 - 4
                        height: 20
                        padding: 0
                        text: "+" + hiddenGoals + " more"
                        Accessible.name: "Show " + hiddenGoals + " more goals for " + modelData.key
                        contentItem: Text { text: parent.text; color: "#9cbed5"; font.pixelSize: 10; elide: Text.ElideRight }
                        onClicked: calendar.showOverflow(modelData.key, this)
                    }
                }
            }
        }
    }
    Popup {
        id: overflow
        objectName: "calendarOverflow"
        parent: Overlay.overlay
        property string date: ""
        readonly property var activities: calendar.goals.filter(function(g) { return g.startDate <= date && g.endDate >= date }).sort(calendar.compareGoals)
        width: Math.min(340, parent.width - 16)
        height: Math.min(parent.height - 16, 380, 78 + activities.length * 54)
        padding: 10; focus: true; modal: false
        // Keep the mouse grab alive while dragging out of the panel.
        opacity: calendar.gesture && calendar.gesture.fromOverflow ? 0 : 1
        onClosed: { if (calendar.gesture && calendar.gesture.fromOverflow) calendar.cancelGesture() }
        background: Rectangle { color: "#21313d"; border.color: "#7dbde8"; radius: 8 }
        contentItem: ColumnLayout {
            RowLayout {
                Label { text: overflow.date; color: "white"; font.bold: true; Layout.fillWidth: true }
                ToolButton { text: "×"; palette.buttonText: "#c5d5df"; Accessible.name: "Close activities"; onClicked: overflow.close() }
            }
            Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: "Drag middle to move · Drag Start or End to resize"; color: "#c5d5df"; font.pixelSize: 11 }
            ListView {
                id: overflowList
                objectName: "calendarOverflowList"
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 4
                model: overflow.activities
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    id: overflowRow
                    required property var modelData
                    width: overflowList.width; height: 50; radius: 4
                    color: rowPointer.containsMouse || activeFocus ? "#354e63" : "#263744"
                    border.color: modelData.color || "#7dbde8"
                    objectName: "overflowGoal_" + modelData.id
                    activeFocusOnTab: true
                    ToolTip.visible: rowPointer.containsMouse
                    ToolTip.text: rowPointer.hoverMode === "start" ? "Drag to set start date"
                        : rowPointer.hoverMode === "end" ? "Drag to set end date" : modelData.name + " · Click to select"
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData.name + ", " + modelData.startDate + " to " + modelData.endDate
                    function selectActivity() {
                        var point = mapToItem(null, 0, height)
                        overflow.close()
                        calendar.showActivity(modelData.id, point.x, point.y)
                    }
                    Keys.onReturnPressed: selectActivity()
                    Keys.onSpacePressed: selectActivity()
                    Repeater {
                        model: ["start", "end"]
                        delegate: Rectangle {
                            required property string modelData
                            objectName: "overflowHandle_" + modelData + "_" + overflowRow.modelData.id
                            width: 32; height: parent.height - 2; y: 1
                            x: modelData === "start" ? 1 : parent.width - width - 1
                            radius: 3; color: rowPointer.hoverMode === modelData && rowPointer.containsMouse ? "#4a6b81" : "#304858"
                            Accessible.role: Accessible.StaticText
                            Accessible.name: "Drag to set " + modelData + " date for " + overflowRow.modelData.name
                            Column {
                                anchors.centerIn: parent
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: "↔"; color: "#e0e9ef"; font.pixelSize: 16 }
                                Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData === "start" ? "Start" : "End"; color: "#c5d5df"; font.pixelSize: 9 }
                            }
                        }
                    }
                    Column {
                        anchors.fill: parent; anchors.margins: 6; anchors.leftMargin: 39; anchors.rightMargin: 39
                        Text { width: parent.width; text: overflowRow.modelData.name; color: "white"; elide: Text.ElideRight }
                        Text { width: parent.width; text: overflowRow.modelData.startDate + " → " + overflowRow.modelData.endDate; color: "#c5d5df"; font.pixelSize: 11 }
                    }
                    MouseArea {
                        id: rowPointer
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: pressed ? (dragMode === "move" ? Qt.ClosedHandCursor : Qt.SizeHorCursor)
                            : (hoverMode === "move" ? Qt.OpenHandCursor : Qt.SizeHorCursor)
                        readonly property string hoverMode: modeAt(mouseX)
                        property string dragMode: "move"
                        function modeAt(x) { return x < 33 ? "start" : x >= width - 33 ? "end" : "move" }
                        property point pressPoint
                        property bool dragging: false
                        property bool canceled: false
                        onPressed: function(mouse) {
                            pressPoint = mapToItem(null, mouse.x, mouse.y)
                            dragMode = modeAt(mouse.x)
                            dragging = false; canceled = false
                        }
                        onPositionChanged: function(mouse) {
                            if (!pressed || canceled) return
                            var point = mapToItem(null, mouse.x, mouse.y)
                            if (!dragging && Math.abs(point.x-pressPoint.x)+Math.abs(point.y-pressPoint.y)>6) {
                                var g = overflowRow.modelData
                                calendar.previewStart = g.startDate; calendar.previewEnd = g.endDate
                                // Resize anchors to the actual endpoint, even when it is outside this month.
                                // Moves retain the offset of the day from which the panel was opened.
                                var anchorDate = dragMode === "start" ? g.startDate : dragMode === "end" ? g.endDate : overflow.date
                                calendar.moved = true; calendar.validDrop = false
                                calendar.gesture = {id:g.id, mode:dragMode, start:calendar.dayNumber(g.startDate), end:calendar.dayNumber(g.endDate),
                                    anchor:calendar.dayNumber(anchorDate), x:0, y:0, fromOverflow:true}
                                calendar.selectedGoalId = g.id
                                dragging = true
                            }
                            if (dragging && calendar.gesture) calendar.updateSceneGesture(point.x, point.y)
                        }
                        onReleased: {
                            if (canceled) return
                            if (dragging) calendar.finishOverflowGesture()
                            else overflowRow.selectActivity()
                        }
                        onCanceled: { canceled = true; calendar.cancelGesture() }
                    }
                }
            }
        }
    }

}
