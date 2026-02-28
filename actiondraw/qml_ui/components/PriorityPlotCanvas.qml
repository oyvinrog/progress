import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    property var tabModel: null
    property int selectedTabIndex: -1
    property real minTimeHours: 1.01
    property real maxTimeHours: 12.0
    property real minSubjectiveValue: 0.0
    property real maxSubjectiveValue: 10.0
    property real leftPadding: 58
    property real rightPadding: 24
    property real topPadding: 28
    property real bottomPadding: 44
    signal pointClicked(int tabIndex)
    signal pointDoubleClicked(int tabIndex)

    radius: 12
    color: "#0f1e2b"
    border.color: "#2a4a63"
    border.width: 1
    clip: true

    function plotWidth() {
        return Math.max(1, width - leftPadding - rightPadding)
    }

    function plotHeight() {
        return Math.max(1, height - topPadding - bottomPadding)
    }

    function toX(timeHours) {
        var clamped = Math.max(minTimeHours, Math.min(maxTimeHours, timeHours))
        var ratio = (clamped - minTimeHours) / (maxTimeHours - minTimeHours)
        return leftPadding + ratio * plotWidth()
    }

    function toY(subjectiveValue) {
        var clamped = Math.max(minSubjectiveValue, Math.min(maxSubjectiveValue, subjectiveValue))
        var ratio = (clamped - minSubjectiveValue) / (maxSubjectiveValue - minSubjectiveValue)
        return height - bottomPadding - (ratio * plotHeight())
    }

    function fromX(xCoord) {
        var normalized = (xCoord - leftPadding) / plotWidth()
        normalized = Math.max(0, Math.min(1, normalized))
        return minTimeHours + normalized * (maxTimeHours - minTimeHours)
    }

    function fromY(yCoord) {
        var normalized = (height - bottomPadding - yCoord) / plotHeight()
        normalized = Math.max(0, Math.min(1, normalized))
        return minSubjectiveValue + normalized * (maxSubjectiveValue - minSubjectiveValue)
    }

    Canvas {
        id: axisCanvas
        anchors.fill: parent
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)

            var left = root.leftPadding
            var right = width - root.rightPadding
            var top = root.topPadding
            var bottom = height - root.bottomPadding

            ctx.strokeStyle = "#43637e"
            ctx.lineWidth = 1

            for (var i = 0; i <= 5; ++i) {
                var gx = left + (i / 5.0) * (right - left)
                ctx.beginPath()
                ctx.moveTo(gx, top)
                ctx.lineTo(gx, bottom)
                ctx.stroke()
            }

            for (var j = 0; j <= 5; ++j) {
                var gy = top + (j / 5.0) * (bottom - top)
                ctx.beginPath()
                ctx.moveTo(left, gy)
                ctx.lineTo(right, gy)
                ctx.stroke()
            }

            ctx.strokeStyle = "#8fbad8"
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(left, top)
            ctx.lineTo(left, bottom)
            ctx.lineTo(right, bottom)
            ctx.stroke()

            ctx.fillStyle = "#cfe7fa"
            ctx.font = "12px Trebuchet MS"
            ctx.fillText("Subjective value", 10, top + 12)
            ctx.fillText("Time to complete (hours)", right - 138, height - 12)
            ctx.fillText(root.minTimeHours.toFixed(2), left - 12, height - 24)
            ctx.fillText(root.maxTimeHours.toFixed(1), right - 20, height - 24)
            ctx.fillText(root.minSubjectiveValue.toFixed(0), left - 34, bottom + 4)
            ctx.fillText(root.maxSubjectiveValue.toFixed(0), left - 34, top + 4)
        }
    }

    Repeater {
        model: root.tabModel

        delegate: Item {
            id: pointItem
            width: 14
            height: 14
            visible: model.includeInPriorityPlot !== false
            property bool isSelected: index === root.selectedTabIndex
            property real pointTime: model.priorityTimeHours || 1.01
            property real pointValue: model.prioritySubjectiveValue || 0.0
            x: root.toX(pointTime) - width / 2
            y: root.toY(pointValue) - height / 2

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: pointItem.isSelected ? "#7cd7ff" : "#54c6ff"
                border.color: pointItem.isSelected ? "#ffffff" : "#d8f5ff"
                border.width: dragArea.drag.active || pointItem.isSelected ? 2 : 1
            }

            Text {
                anchors.bottom: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottomMargin: 4
                text: model.name
                color: "#d4ebfd"
                font.pixelSize: 10
            }

            MouseArea {
                id: dragArea
                anchors.fill: parent
                cursorShape: Qt.OpenHandCursor
                drag.target: pointItem
                drag.minimumX: root.leftPadding - pointItem.width / 2
                drag.maximumX: root.width - root.rightPadding - pointItem.width / 2
                drag.minimumY: root.topPadding - pointItem.height / 2
                drag.maximumY: root.height - root.bottomPadding - pointItem.height / 2
                onPressed: cursorShape = Qt.ClosedHandCursor
                onClicked: root.pointClicked(index)
                onDoubleClicked: root.pointDoubleClicked(index)
                onReleased: {
                    cursorShape = Qt.OpenHandCursor
                    var centerX = pointItem.x + pointItem.width / 2
                    var centerY = pointItem.y + pointItem.height / 2
                    var newTime = root.fromX(centerX)
                    var newValue = root.fromY(centerY)
                    if (root.tabModel && root.tabModel.setPriorityPoint)
                        root.tabModel.setPriorityPoint(index, newTime, newValue)
                    axisCanvas.requestPaint()
                }
            }

            ToolTip {
                visible: dragArea.containsMouse
                delay: 300
                text: {
                    var score = model.priorityScore !== undefined ? model.priorityScore : 0.0
                    return model.name
                        + "\nTime: " + (model.priorityTimeHours || 0).toFixed(2) + "h"
                        + "\nValue: " + (model.prioritySubjectiveValue || 0).toFixed(2)
                        + "\nScore: " + score.toFixed(2)
                }
            }
        }
    }
}
