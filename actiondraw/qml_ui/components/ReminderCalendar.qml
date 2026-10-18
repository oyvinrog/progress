import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: calendar
    objectName: "reminderCalendar"
    property var dayCounts: ({})
    property var goals: []
    property real viewportHeightLimit: 456
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
            var h = 72
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
        gesture = {id:goal.id, mode:mode, start:dayNumber(goal.startDate), end:dayNumber(goal.endDate),
                   anchor:dayNumber(calendarDays[cell].key), x:x, y:y}
        previewStart = goal.startDate; previewEnd = goal.endDate
        validDrop = true; moved = false
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
        if (commit) rangeEdited(g.id,previewStart,previewEnd)
        else if (!moved && validDrop) goalOpened(g.id)
    }
    function cancelGesture() { gesture=null; hoverMonth=0; validDrop=false }
    Keys.onEscapePressed: { cancelGesture(); pointer.pressedCell=-1 }
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
                ToolTip.text: "Double-click a day to add a goal. Drag goals to move, drag ends to resize. Escape cancels."
            }
            Button { objectName:"reminderAllDays"; text:"All days"; highlighted:calendar.selectedDate===""; onClicked:calendar.dateSelected("") }
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
                        onClicked:calendar.dateSelected(modelData.key)
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
                                x:modelData.column*grid.width/7+2; y:22+modelData.lane*18
                                width:modelData.span*grid.width/7-6; height:16; radius:3
                                color:"#243d50"; border.color:modelData.goal.color || "#7dbde8"; border.width:1
                                Text { anchors {fill:parent; leftMargin:12; rightMargin:12} text:bar.modelData.goal.name; elide:Text.ElideRight; color:"white"; verticalAlignment:Text.AlignVCenter; font.pixelSize:10 }
                                Text { visible:bar.modelData.first; text:"│"; color:"white"; anchors.left:parent.left }
                                Text { visible:bar.modelData.last; text:"│"; color:"white"; anchors.right:parent.right }

                            }
                        }
                    }
                }
                MouseArea {
                    id: pointer
                    anchors.fill: parent
                    property int pressedCell: -1
                    onPressed: function(mouse) {
                        pressedCell=calendar.cellAt(mouse.x,mouse.y)
                        if (pressedCell<0) return
                        var week=calendar.weeks[Math.floor(pressedCell/7)]
                        var column=pressedCell%7
                        var lane=Math.floor((mouse.y-week.top-22)/18)
                        for (var i=0;i<week.bars.length;++i) {
                            var b=week.bars[i]
                            if (b.lane!==lane || column<b.column || column>=b.column+b.span) continue
                            var left=b.column*grid.width/7+2, right=(b.column+b.span)*grid.width/7-4
                            if (mouse.x < left || mouse.x > right || mouse.y-week.top-(22+b.lane*18) >= 16) continue
                            var mode=mouse.x-left<10 && b.first ? "start" : right-mouse.x<10 && b.last ? "end" : "move"
                            calendar.beginGesture(b.goal,mode,mouse.x,mouse.y)
                            return
                        }
                    }
                    onDoubleClicked: function(mouse) {
                        if (calendar.gesture) return
                        var cell = calendar.cellAt(mouse.x, mouse.y)
                        if (cell < 0) return
                        pressedCell = -1
                        calendar.dateDoubleClicked(calendar.calendarDays[cell].key)
                    }
                    onPositionChanged: function(mouse) {
                        if (!calendar.gesture) return
                        calendar.updateGesture(mouse.x,mouse.y)
                        var a=mapToItem(previous,mouse.x,mouse.y), b=mapToItem(next,mouse.x,mouse.y)
                        calendar.hoverMonth=a.x>=0 && a.x<previous.width && a.y>=0 && a.y<previous.height ? -1 :
                                            b.x>=0 && b.x<next.width && b.y>=0 && b.y<next.height ? 1 : 0
                        if (mouse.x>viewport.contentX+viewport.width-20) viewport.contentX=Math.max(0,Math.min(viewport.contentWidth-viewport.width,viewport.contentX+8))
                        if (mouse.x<viewport.contentX+20) viewport.contentX=Math.max(0,viewport.contentX-8)
                        if (mouse.y>viewport.contentY+viewport.height-35)
                            viewport.contentY=Math.min(viewport.contentHeight-viewport.height,viewport.contentY+8)
                        if (mouse.y<viewport.contentY+15) viewport.contentY=Math.max(0,viewport.contentY-8)
                    }
                    onReleased: function(mouse) {
                        if (calendar.gesture) calendar.finishGesture()
                        else if (pressedCell>=0 && calendar.cellAt(mouse.x,mouse.y)===pressedCell)
                            calendar.dateSelected(calendar.calendarDays[pressedCell].key)
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
                        y: calendar.weeks[Math.floor(index / 7)].top + 58
                        width: grid.width / 7 - 4
                        height: 14
                        padding: 0
                        text: "+" + hiddenGoals + " more"
                        Accessible.name: "Show " + hiddenGoals + " more goals for " + modelData.key
                        contentItem: Text { text: parent.text; color: "#9cbed5"; font.pixelSize: 10; elide: Text.ElideRight }
                        onClicked: calendar.dateSelected(modelData.key)
                    }
                }
            }
        }
    }
}
