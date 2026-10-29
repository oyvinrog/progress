import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: handle
    required property var dragOverview
    required property var entry
    implicitWidth: 28
    implicitHeight: 36
    Accessible.name: "Drag to another day"
    Label { anchors.centerIn: parent; text: "⠿"; font.pixelSize: 22; color: "#9aafbd" }
    ToolTip.visible: mouse.containsMouse && !mouse.pressed
    ToolTip.text: "Drag onto another day to move this item"
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
        property point start
        property bool dragging: false
        onPressed: function(event) { start = Qt.point(event.x, event.y); dragging = false }
        onPositionChanged: function(event) {
            if (!pressed) return
            var point = mapToItem(null, event.x, event.y)
            if (!dragging && Math.hypot(event.x - start.x, event.y - start.y) >= Qt.styleHints.startDragDistance) {
                dragging = true
                handle.dragOverview.beginAgendaDrag(handle.entry, point.x, point.y)
            }
            if (dragging) handle.dragOverview.updateAgendaDrag(point.x, point.y)
        }
        onReleased: function(event) {
            if (dragging) {
                var point = mapToItem(null, event.x, event.y)
                handle.dragOverview.finishAgendaDrag(point.x, point.y)
            }
            dragging = false
        }
        onCanceled: { dragging = false; handle.dragOverview.cancelAgendaDrag() }
    }
}
