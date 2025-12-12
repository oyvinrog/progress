"""Progress tracking task list with time estimation using PySide6 + QML.

Features:
- Tasks with checkboxes to mark completion
- Automatic time tracking for active tasks
- Estimated completion times based on historical average
- Break down tasks into subtasks
- Add new tasks dynamically
"""

import sys
import time
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    Qt,
    Slot,
    QTimer,
    Property,
    Signal,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


@dataclass
class Task:
    title: str
    completed: bool = False
    time_spent: float = 0.0  # minutes
    start_time: Optional[float] = None  # timestamp when started
    parent_index: int = -1  # -1 for root tasks, else index of parent
    indent_level: int = 0
    custom_estimate: Optional[float] = None  # minutes, overrides avg estimate if set


class TaskModel(QAbstractListModel):
    TitleRole = Qt.UserRole + 1
    CompletedRole = Qt.UserRole + 2
    TimeSpentRole = Qt.UserRole + 3
    EstimatedTimeRole = Qt.UserRole + 4
    CompletionTimeRole = Qt.UserRole + 5
    EstimatedTimeOfDayRole = Qt.UserRole + 6
    IndentLevelRole = Qt.UserRole + 7
    TotalEstimatedRole = Qt.UserRole + 8

    avgTimeChanged = Signal()
    totalEstimateChanged = Signal()

    def __init__(self, tasks: List[Task] | None = None):
        super().__init__()
        self._tasks: List[Task] = tasks or []
        self._timer = QTimer()
        self._timer.timeout.connect(self._updateActiveTasks)
        self._timer.start(1000)  # Update every second

    def rowCount(self, parent: QModelIndex | None = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._tasks)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._tasks)):
            return None

        task = self._tasks[index.row()]
        if role == self.TitleRole:
            return task.title
        elif role == self.CompletedRole:
            return task.completed
        elif role == self.TimeSpentRole:
            return task.time_spent
        elif role == self.EstimatedTimeRole:
            return self._estimateTaskTime(index.row())
        elif role == self.CompletionTimeRole:
            return self._estimateCompletionTime(index.row())
        elif role == self.EstimatedTimeOfDayRole:
            return self._estimateTimeOfDay(index.row())
        elif role == self.IndentLevelRole:
            return task.indent_level
        return None

    def roleNames(self):  # type: ignore[override]
        return {
            self.TitleRole: b"title",
            self.CompletedRole: b"completed",
            self.TimeSpentRole: b"timeSpent",
            self.EstimatedTimeRole: b"estimatedTime",
            self.CompletionTimeRole: b"completionTime",
            self.EstimatedTimeOfDayRole: b"estimatedTimeOfDay",
            self.IndentLevelRole: b"indentLevel",
            self.TotalEstimatedRole: b"totalEstimated",
        }

    def _getAverageTaskTime(self) -> float:
        """Calculate average time per completed task."""
        completed_tasks = [t for t in self._tasks if t.completed and t.time_spent > 0]
        if not completed_tasks:
            return 0.0
        return sum(t.time_spent for t in completed_tasks) / len(completed_tasks)

    @Property(float, notify=avgTimeChanged)
    def averageTaskTime(self) -> float:
        return self._getAverageTaskTime()

    def _getTotalEstimatedTime(self) -> float:
        """Calculate total estimated time to complete all remaining tasks."""
        total = 0.0
        for i, task in enumerate(self._tasks):
            if not task.completed:
                total += self._estimateTaskTime(i)
        return total

    @Property(float, notify=totalEstimateChanged)
    def totalEstimatedTime(self) -> float:
        return self._getTotalEstimatedTime()

    @Property(float, notify=totalEstimateChanged)
    def percentageComplete(self) -> float:
        """Calculate percentage of tasks completed."""
        if not self._tasks:
            return 0.0
        completed = sum(1 for t in self._tasks if t.completed)
        return (completed / len(self._tasks)) * 100.0

    @Property(str, notify=totalEstimateChanged)
    def estimatedCompletionTimeOfDay(self) -> str:
        """Calculate the time of day when all tasks will be completed."""
        total_time = self._getTotalEstimatedTime()
        if total_time == 0:
            return ""

        future_time = datetime.now() + timedelta(minutes=total_time)
        return future_time.strftime("%H:%M")

    def _estimateTaskTime(self, row: int) -> float:
        """Estimate time for a single task to complete."""
        task = self._tasks[row]
        if task.completed:
            return task.time_spent

        # Use custom estimate if set
        if task.custom_estimate is not None:
            return task.custom_estimate

        avg_time = self._getAverageTaskTime()
        if avg_time == 0:
            return 0.0

        # Each task is estimated to take the average time
        return avg_time

    def _estimateCompletionTime(self, row: int) -> float:
        """Estimate when this task will be completed (cumulative time from now)."""
        task = self._tasks[row]
        if task.completed:
            return 0.0  # Already completed

        # Find the first incomplete task (currently being worked on)
        first_incomplete_idx = None
        for i, t in enumerate(self._tasks):
            if not t.completed:
                first_incomplete_idx = i
                break

        if first_incomplete_idx is None:
            return 0.0

        # Calculate cumulative time for all incomplete tasks before this one
        cumulative_time = 0.0

        for i in range(first_incomplete_idx, row + 1):
            if self._tasks[i].completed:
                continue

            task_estimate = self._estimateTaskTime(i)
            if task_estimate == 0:
                # No estimate available, skip
                continue

            if i == first_incomplete_idx:
                # First incomplete task: use remaining time
                remaining = task_estimate - self._tasks[i].time_spent
                cumulative_time += max(0.0, remaining)
            elif i < row:
                # Tasks before this one: use full estimate
                cumulative_time += task_estimate
            else:
                # This is the target task: add full estimate
                cumulative_time += task_estimate

        return cumulative_time

    def _estimateTimeOfDay(self, row: int) -> str:
        """Estimate the time of day when this task will be completed."""
        task = self._tasks[row]
        if task.completed:
            return ""  # Already completed, no estimate needed

        completion_time_minutes = self._estimateCompletionTime(row)
        if completion_time_minutes == 0:
            return ""

        # Calculate future time
        future_time = datetime.now() + timedelta(minutes=completion_time_minutes)
        return future_time.strftime("%H:%M")

    def _updateActiveTasks(self) -> None:
        """Update time spent on active (incomplete) tasks."""
        current_time = time.time()
        changed = False
        for i, task in enumerate(self._tasks):
            if not task.completed and task.start_time:
                elapsed = (current_time - task.start_time) / 60.0  # to minutes
                task.time_spent += elapsed
                task.start_time = current_time
                changed = True

        # Update all rows if any task changed, since completion times are interdependent
        if changed and len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.TimeSpentRole, self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

    @Slot(str)
    def addTask(self, title: str, parent_row: int = -1) -> None:
        title = title.strip()
        if not title:
            return

        indent = 0
        if parent_row >= 0 and parent_row < len(self._tasks):
            indent = self._tasks[parent_row].indent_level + 1

        task = Task(
            title=title,
            start_time=time.time(),
            parent_index=parent_row,
            indent_level=indent,
        )

        insert_pos = len(self._tasks)
        if parent_row >= 0:
            # Insert after parent and its existing children
            insert_pos = parent_row + 1
            while insert_pos < len(self._tasks) and self._tasks[insert_pos].indent_level > indent - 1:
                insert_pos += 1

        self.beginInsertRows(QModelIndex(), insert_pos, insert_pos)
        self._tasks.insert(insert_pos, task)
        self.endInsertRows()

    @Slot(int, bool)
    def toggleComplete(self, row: int, completed: bool) -> None:
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        task.completed = completed

        if completed:
            # Finalize time
            if task.start_time:
                elapsed = (time.time() - task.start_time) / 60.0
                task.time_spent += elapsed
                task.start_time = None
        else:
            # Restart timing
            task.start_time = time.time()

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        self.avgTimeChanged.emit()
        self.totalEstimateChanged.emit()

        # Update estimates for all tasks
        if len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.EstimatedTimeRole, self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

    @Slot(int)
    def addSubtask(self, parent_row: int) -> None:
        """Add a subtask under the given parent task."""
        if parent_row < 0 or parent_row >= len(self._tasks):
            return

        # Create placeholder subtask
        self.addTask("Subtask", parent_row)

    @Slot(int, str)
    def renameTask(self, row: int, new_title: str) -> None:
        if row < 0 or row >= len(self._tasks):
            return

        new_title = new_title.strip()
        if not new_title:
            return

        self._tasks[row].title = new_title
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.TitleRole])

    @Slot(int, str)
    def setCustomEstimate(self, row: int, estimate_str: str) -> None:
        """Set a custom time estimate for a task.

        Args:
            row: Task index
            estimate_str: Time string like "30m", "2h", "1.5h", or just a number (minutes)
        """
        if row < 0 or row >= len(self._tasks):
            return

        estimate_str = estimate_str.strip().lower()
        if not estimate_str:
            # Clear custom estimate
            self._tasks[row].custom_estimate = None
        else:
            try:
                # Parse time string
                if estimate_str.endswith('h'):
                    # Hours
                    hours = float(estimate_str[:-1])
                    minutes = hours * 60
                elif estimate_str.endswith('m'):
                    # Minutes
                    minutes = float(estimate_str[:-1])
                else:
                    # Default to minutes
                    minutes = float(estimate_str)

                self._tasks[row].custom_estimate = max(0.0, minutes)
            except ValueError:
                # Invalid format, ignore
                return

        # Update UI
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.EstimatedTimeRole, self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

        # Update total estimate
        self.totalEstimateChanged.emit()

        # Update all completion times since they depend on estimates
        if len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

    @Slot(int, int)
    def moveTask(self, from_row: int, to_row: int) -> None:
        """Move a task from one position to another."""
        if (
            from_row == to_row
            or from_row < 0
            or to_row < 0
            or from_row >= len(self._tasks)
            or to_row >= len(self._tasks)
        ):
            return

        # Qt's beginMoveRows expects destination to be the position before removal
        destination = to_row + 1 if to_row > from_row else to_row
        self.beginMoveRows(QModelIndex(), from_row, from_row, QModelIndex(), destination)
        task = self._tasks.pop(from_row)
        self._tasks.insert(to_row, task)
        self.endMoveRows()

        # Update completion time estimates since order changed
        if len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

    @Slot(int)
    def removeAt(self, row: int) -> None:
        if row < 0 or row >= len(self._tasks):
            return

        # Remove task and all its children
        task = self._tasks[row]
        rows_to_remove = [row]

        # Find all children
        i = row + 1
        while i < len(self._tasks) and self._tasks[i].indent_level > task.indent_level:
            rows_to_remove.append(i)
            i += 1

        # Remove in reverse order to maintain indices
        for r in reversed(rows_to_remove):
            self.beginRemoveRows(QModelIndex(), r, r)
            self._tasks.pop(r)
            self.endRemoveRows()

        self.avgTimeChanged.emit()

    @Slot()
    def clear(self) -> None:
        if not self._tasks:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._tasks) - 1)
        self._tasks.clear()
        self.endRemoveRows()
        self.avgTimeChanged.emit()

    @Slot()
    def pasteSampleTasks(self) -> None:
        sample_tasks = [
            "Review pull requests",
            "Write documentation",
            "Fix critical bug",
            "Update dependencies",
            "Code review meeting",
        ]
        for title in sample_tasks:
            self.addTask(title)


QML_UI = rb"""
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs

ApplicationWindow {
    id: root
    visible: true
    width: 800
    height: 720
    title: "Progress Tracker"
    color: "#0f1115"

    function formatTime(minutes) {
        if (minutes === 0) return "N/A"
        if (minutes < 1) return (minutes * 60).toFixed(0) + "s"
        return minutes.toFixed(1) + "m"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Label {
            text: "Progress Tracker"
            font.pixelSize: 22
            color: "#f5f6f8"
            horizontalAlignment: Text.AlignHCenter
        }

        RowLayout {
            spacing: 12
            Layout.alignment: Qt.AlignHCenter

            Rectangle {
                width: 140
                height: 60
                radius: 8
                color: "#1b2028"
                border.color: "#2e3744"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2

                    Label {
                        property real percentage: taskModel.percentageComplete
                        text: percentage.toFixed(0) + "%"
                        font.pixelSize: 20
                        font.bold: true
                        color: "#4a9eff"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: "Complete"
                        font.pixelSize: 10
                        color: "#8a93a5"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            Rectangle {
                width: 140
                height: 60
                radius: 8
                color: "#1b2028"
                border.color: "#2e3744"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2

                    Label {
                        property real totalTime: taskModel.totalEstimatedTime
                        text: formatTime(totalTime)
                        font.pixelSize: 20
                        font.bold: true
                        color: "#ffa94d"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: "Time Left"
                        font.pixelSize: 10
                        color: "#8a93a5"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            Rectangle {
                width: 140
                height: 60
                radius: 8
                color: "#1b2028"
                border.color: "#2e3744"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2

                    Label {
                        property real avgTime: taskModel.averageTaskTime
                        text: formatTime(avgTime)
                        font.pixelSize: 20
                        font.bold: true
                        color: "#9aa6b8"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: "Avg Time"
                        font.pixelSize: 10
                        color: "#8a93a5"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            Rectangle {
                width: 140
                height: 60
                radius: 8
                color: "#1b2028"
                border.color: "#2e3744"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 2

                    Label {
                        property string completionTime: taskModel.estimatedCompletionTimeOfDay
                        text: completionTime !== "" ? completionTime : "N/A"
                        font.pixelSize: 20
                        font.bold: true
                        color: "#82c3a5"
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Label {
                        text: "Done By"
                        font.pixelSize: 10
                        color: "#8a93a5"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }
        }

        RowLayout {
            spacing: 8

            TextField {
                id: inputField
                Layout.fillWidth: true
                placeholderText: "Add a task..."
                color: "#f5f6f8"
                placeholderTextColor: "#8a93a5"
                selectByMouse: true
                background: Rectangle {
                    color: "#1b2028"
                    radius: 8
                    border.color: "#2e3744"
                }
                onAccepted: {
                    taskModel.addTask(text, -1)
                    text = ""
                }
            }

            Button {
                text: "Add"
                onClicked: {
                    taskModel.addTask(inputField.text, -1)
                    inputField.text = ""
                }
            }
        }

        RowLayout {
            spacing: 8

            Button {
                text: "Paste sample tasks"
                onClicked: taskModel.pasteSampleTasks()
            }

            Button {
                text: "Clear"
                enabled: listView.count > 0
                onClicked: taskModel.clear()
            }

            Button {
                text: "Complete"
                enabled: listView.count > 0
                onClicked: root.close()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 10
            color: "#161a20"
            border.color: "#222832"

            ListView {
                id: listView
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8
                clip: true
                interactive: true
                boundsBehavior: Flickable.StopAtBounds
                model: taskModel

                delegate: Item {
                    id: delegateRoot
                    required property int index
                    required property string title
                    required property bool completed
                    required property real timeSpent
                    required property real estimatedTime
                    required property real completionTime
                    required property string estimatedTimeOfDay
                    required property int indentLevel

                    width: listView.width
                    height: contentRow.implicitHeight + 16

                    Rectangle {
                        id: taskFrame
                        anchors.fill: parent
                        anchors.margins: 0
                        radius: 8
                        color: delegateRoot.completed ? "#1a2820" : (dropArea.containsDrag ? "#2a3240" : "#1f2630")
                        border.color: dropArea.containsDrag ? "#4a5568" : "#2e3744"
                        border.width: dropArea.containsDrag ? 2 : 1

                        RowLayout {
                            id: contentRow
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 8

                            Item {
                                width: delegateRoot.indentLevel * 20
                                height: 1
                            }

                            CheckBox {
                                id: checkbox
                                checked: delegateRoot.completed
                                onToggled: taskModel.toggleComplete(delegateRoot.index, checked)
                            }

                            Label {
                                text: delegateRoot.title
                                color: delegateRoot.completed ? "#6b8068" : "#f5f6f8"
                                font.strikeout: delegateRoot.completed
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                                visible: !editField.visible

                                MouseArea {
                                    anchors.fill: parent
                                    onDoubleClicked: {
                                        editField.text = delegateRoot.title
                                        editField.visible = true
                                        editField.forceActiveFocus()
                                        editField.selectAll()
                                    }
                                }
                            }

                            TextField {
                                id: editField
                                visible: false
                                text: delegateRoot.title
                                color: "#f5f6f8"
                                selectByMouse: true
                                Layout.fillWidth: true
                                background: Rectangle {
                                    color: "#1b2028"
                                    radius: 4
                                    border.color: "#4a5568"
                                }
                                onAccepted: {
                                    taskModel.renameTask(delegateRoot.index, text)
                                    visible = false
                                }
                                onActiveFocusChanged: {
                                    if (!activeFocus && visible) {
                                        taskModel.renameTask(delegateRoot.index, text)
                                        visible = false
                                    }
                                }
                            }

                            ColumnLayout {
                                spacing: 2
                                Layout.minimumWidth: 120

                                Label {
                                    text: {
                                        var time = delegateRoot.completed ? delegateRoot.timeSpent : delegateRoot.estimatedTime
                                        var prefix = delegateRoot.completed ? "" : "~"
                                        if (time < 1) {
                                            return prefix + (time * 60).toFixed(0) + " sec"
                                        }
                                        return prefix + time.toFixed(1) + " min"
                                    }
                                    color: delegateRoot.completed ? "#6b8068" : "#9aa6b8"
                                    font.pixelSize: 12
                                    font.bold: true

                                    MouseArea {
                                        anchors.fill: parent
                                        acceptedButtons: Qt.RightButton
                                        onClicked: {
                                            estimateDialog.taskIndex = delegateRoot.index
                                            estimateDialog.open()
                                        }
                                    }

                                    ToolTip {
                                        text: "Right-click to set custom estimate"
                                        visible: parent.hovered
                                        delay: 1000
                                    }

                                    property bool hovered: false
                                    HoverHandler {
                                        onHoveredChanged: parent.hovered = hovered
                                    }
                                }

                                Label {
                                    text: {
                                        if (delegateRoot.completed) return ""
                                        var time = delegateRoot.completionTime
                                        var timeOfDay = delegateRoot.estimatedTimeOfDay
                                        if (time === 0) return ""

                                        var timeStr = ""
                                        if (time < 1) {
                                            timeStr = "in " + (time * 60).toFixed(0) + " sec"
                                        } else {
                                            timeStr = "in " + time.toFixed(1) + " min"
                                        }

                                        if (timeOfDay !== "") {
                                            timeStr += " (" + timeOfDay + ")"
                                        }
                                        return timeStr
                                    }
                                    color: "#7a8496"
                                    font.pixelSize: 10
                                    visible: !delegateRoot.completed && delegateRoot.completionTime > 0
                                }
                            }

                            ToolButton {
                                text: "+"
                                font.pixelSize: 16
                                contentItem: Text {
                                    text: parent.text
                                    font: parent.font
                                    color: "#9aa6b8"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: taskModel.addSubtask(delegateRoot.index)
                            }

                            Rectangle {
                                id: dragHandle
                                width: 32
                                height: 32
                                radius: 4
                                color: dragMouseArea.pressed ? "#384050" : "#28303d"
                                border.color: "#2e3744"

                                Text {
                                    anchors.centerIn: parent
                                    text: "\u2630"
                                    color: "#9aa6b8"
                                    font.pixelSize: 14
                                }

                                Drag.active: dragMouseArea.drag.active
                                Drag.source: delegateRoot
                                Drag.hotSpot.x: width / 2
                                Drag.hotSpot.y: height / 2

                                MouseArea {
                                    id: dragMouseArea
                                    anchors.fill: parent
                                    cursorShape: drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor

                                    property point startPos

                                    onPressed: function(mouse) {
                                        startPos = Qt.point(dragHandle.x, dragHandle.y)
                                        drag.target = dragHandle
                                    }

                                    onReleased: {
                                        drag.target = null
                                        dragHandle.Drag.drop()
                                        dragHandle.x = startPos.x
                                        dragHandle.y = startPos.y
                                    }
                                }
                            }

                            ToolButton {
                                text: "\u2715"
                                contentItem: Text {
                                    text: parent.text
                                    font: parent.font
                                    color: "#9aa6b8"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: taskModel.removeAt(delegateRoot.index)
                            }
                        }

                        DropArea {
                            id: dropArea
                            anchors.fill: parent

                            onEntered: function(drag) {
                                var sourceItem = drag.source
                                if (sourceItem && sourceItem.index !== delegateRoot.index) {
                                    taskModel.moveTask(sourceItem.index, delegateRoot.index)
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: estimateDialog
        title: "Set Custom Estimate"
        modal: true
        anchors.centerIn: parent
        width: 300
        height: 150

        property int taskIndex: -1

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Label {
                text: "Enter estimate (e.g., 30m, 2h, 45):"
                color: "#f5f6f8"
            }

            TextField {
                id: estimateInput
                Layout.fillWidth: true
                placeholderText: "30m or 1.5h"
                color: "#f5f6f8"
                selectByMouse: true
                background: Rectangle {
                    color: "#1b2028"
                    radius: 4
                    border.color: "#4a5568"
                }
                onAccepted: {
                    taskModel.setCustomEstimate(estimateDialog.taskIndex, text)
                    estimateDialog.close()
                }
                Component.onCompleted: {
                    forceActiveFocus()
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                Button {
                    text: "Set"
                    onClicked: {
                        taskModel.setCustomEstimate(estimateDialog.taskIndex, estimateInput.text)
                        estimateDialog.close()
                    }
                }

                Button {
                    text: "Clear"
                    onClicked: {
                        taskModel.setCustomEstimate(estimateDialog.taskIndex, "")
                        estimateDialog.close()
                    }
                }

                Button {
                    text: "Cancel"
                    onClicked: {
                        estimateDialog.close()
                    }
                }
            }
        }
    }
}
"""


def get_tasks() -> List[Task]:
    """Launch the progress tracker GUI and return the tasks when the window closes.

    Returns:
        List of Task objects with completion status and time tracking.
    """
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    model = TaskModel()
    engine.rootContext().setContextProperty("taskModel", model)
    engine.loadData(QML_UI)

    if not engine.rootObjects():
        return []

    app.exec()
    return [
        Task(
            title=t.title,
            completed=t.completed,
            time_spent=t.time_spent,
            indent_level=t.indent_level,
        )
        for t in model._tasks
    ]


def main() -> int:
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    model = TaskModel()
    engine.rootContext().setContextProperty("taskModel", model)
    engine.loadData(QML_UI)

    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
