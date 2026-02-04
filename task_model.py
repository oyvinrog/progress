"""Shared task model for use across actiondraw and other modules.

This module provides the Task dataclass and TaskModel class that were
previously embedded in progress_list.py, making them available for
independent use by actiondraw.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Qt,
    QTimer,
    QUrl,
    QSettings,
    Signal,
    Slot,
    Property,
)


@dataclass
class Task:
    """Represents a single task with time tracking."""
    title: str
    completed: bool = False
    time_spent: float = 0.0  # minutes
    start_time: Optional[float] = None  # timestamp when started
    parent_index: int = -1  # -1 for root tasks, else index of parent
    indent_level: int = 0
    custom_estimate: Optional[float] = None  # minutes, overrides avg estimate if set
    countdown_duration: Optional[float] = None  # countdown duration in seconds
    countdown_start: Optional[float] = None  # timestamp when countdown started


@dataclass
class Tab:
    """Represents a single tab containing tasks and diagram data."""
    name: str
    tasks: Dict[str, Any]  # TaskModel.to_dict() data
    diagram: Dict[str, Any]  # DiagramModel.to_dict() data
    priority: int = 0  # 0 = no priority, 1-3 = priority levels


class TaskModel(QAbstractListModel):
    """Qt model for managing a list of tasks with time estimation."""
    
    TitleRole = Qt.UserRole + 1
    CompletedRole = Qt.UserRole + 2
    TimeSpentRole = Qt.UserRole + 3
    EstimatedTimeRole = Qt.UserRole + 4
    CompletionTimeRole = Qt.UserRole + 5
    EstimatedTimeOfDayRole = Qt.UserRole + 6
    IndentLevelRole = Qt.UserRole + 7
    TotalEstimatedRole = Qt.UserRole + 8
    CountdownRemainingRole = Qt.UserRole + 9
    CountdownProgressRole = Qt.UserRole + 10
    CountdownExpiredRole = Qt.UserRole + 11
    CountdownActiveRole = Qt.UserRole + 12

    avgTimeChanged = Signal()
    totalEstimateChanged = Signal()
    taskCountChanged = Signal()
    taskRenamed = Signal(int, str, arguments=['taskIndex', 'newTitle'])
    taskCompletionChanged = Signal(int, bool, arguments=['taskIndex', 'completed'])
    taskCountdownChanged = Signal(int, arguments=['taskIndex'])

    def __init__(self, tasks: Optional[List[Task]] = None):
        super().__init__()
        self._tasks: List[Task] = tasks or []
        self._loading = False  # Flag to suppress signals during bulk loading
        self._timer = QTimer()
        self._timer.timeout.connect(self._updateActiveTasks)
        self._timer.start(1000)  # Update every second
        self.taskCountChanged.emit()

    def rowCount(self, parent: Optional[QModelIndex] = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._tasks)

    @Property(int, notify=taskCountChanged)
    def taskCount(self) -> int:
        """Expose the current number of tasks to QML."""
        return len(self._tasks)

    @Slot(int, result=str)
    def getTaskTitle(self, index: int) -> str:
        """Get the title of a task by index."""
        if 0 <= index < len(self._tasks):
            return self._tasks[index].title
        return ""

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
        elif role == self.CountdownRemainingRole:
            return self._getCountdownRemaining(task)
        elif role == self.CountdownProgressRole:
            return self._getCountdownProgress(task)
        elif role == self.CountdownExpiredRole:
            return self._isCountdownExpired(task)
        elif role == self.CountdownActiveRole:
            return self._isCountdownActive(task)
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
            self.CountdownRemainingRole: b"countdownRemaining",
            self.CountdownProgressRole: b"countdownProgress",
            self.CountdownExpiredRole: b"countdownExpired",
            self.CountdownActiveRole: b"countdownActive",
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
    def currentActiveTaskTitle(self) -> str:
        """Get the title of the first incomplete task (currently being worked on)."""
        for task in self._tasks:
            if not task.completed:
                return task.title
        return ""

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

    def _getCountdownRemaining(self, task: Task) -> float:
        """Get seconds remaining on countdown timer, or -1 if no timer."""
        if task.countdown_duration is None or task.countdown_start is None:
            return -1.0
        elapsed = time.time() - task.countdown_start
        remaining = task.countdown_duration - elapsed
        return max(0.0, remaining)

    def _getCountdownProgress(self, task: Task) -> float:
        """Get countdown progress as 0.0-1.0, or -1 if no timer."""
        if task.countdown_duration is None or task.countdown_start is None:
            return -1.0
        if task.countdown_duration <= 0:
            return 0.0
        elapsed = time.time() - task.countdown_start
        progress = 1.0 - (elapsed / task.countdown_duration)
        return max(0.0, min(1.0, progress))

    def _isCountdownExpired(self, task: Task) -> bool:
        """Return True if countdown has expired without task completion."""
        if task.completed:
            return False
        if task.countdown_duration is None or task.countdown_start is None:
            return False
        elapsed = time.time() - task.countdown_start
        return elapsed >= task.countdown_duration

    def _isCountdownActive(self, task: Task) -> bool:
        """Return True if countdown timer is active."""
        return task.countdown_duration is not None and task.countdown_start is not None

    @Slot(int, str)
    def setCountdownTimer(self, row: int, duration_str: str) -> None:
        """Set a countdown timer for a task.

        Args:
            row: Task index
            duration_str: Duration string like "30s", "2m", "1h", or just a number (seconds)
        """
        if row < 0 or row >= len(self._tasks):
            return

        duration_str = duration_str.strip().lower()
        if not duration_str:
            return

        try:
            # Parse duration string
            if duration_str.endswith('h'):
                hours = float(duration_str[:-1])
                seconds = hours * 3600
            elif duration_str.endswith('m'):
                minutes = float(duration_str[:-1])
                seconds = minutes * 60
            elif duration_str.endswith('s'):
                seconds = float(duration_str[:-1])
            else:
                # Default to seconds
                seconds = float(duration_str)

            if seconds <= 0:
                return

            task = self._tasks[row]
            task.countdown_duration = seconds
            task.countdown_start = time.time()

            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [
                self.CountdownRemainingRole,
                self.CountdownProgressRole,
                self.CountdownExpiredRole,
                self.CountdownActiveRole
            ])
            self.taskCountdownChanged.emit(row)

        except ValueError:
            # Invalid format, ignore
            return

    @Slot(int)
    def clearCountdownTimer(self, row: int) -> None:
        """Clear the countdown timer for a task.

        Args:
            row: Task index
        """
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        task.countdown_duration = None
        task.countdown_start = None

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [
            self.CountdownRemainingRole,
            self.CountdownProgressRole,
            self.CountdownExpiredRole,
            self.CountdownActiveRole
        ])
        self.taskCountdownChanged.emit(row)

    @Slot(int)
    def restartCountdownTimer(self, row: int) -> None:
        """Restart the countdown timer for a task to its full duration.

        Args:
            row: Task index
        """
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        if task.countdown_duration is None:
            return

        task.countdown_start = time.time()

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [
            self.CountdownRemainingRole,
            self.CountdownProgressRole,
            self.CountdownExpiredRole,
            self.CountdownActiveRole
        ])
        self.taskCountdownChanged.emit(row)

    def _updateActiveTasks(self) -> None:
        """Update time spent on active (incomplete) tasks and countdown timers."""
        current_time = time.time()
        changed = False
        countdown_task_indices = []

        for i, task in enumerate(self._tasks):
            if not task.completed and task.start_time:
                elapsed = (current_time - task.start_time) / 60.0  # to minutes
                task.time_spent += elapsed
                task.start_time = current_time
                changed = True

            # Track tasks with active countdown timers
            if task.countdown_duration is not None and task.countdown_start is not None:
                countdown_task_indices.append(i)

        # Update all rows if any task changed, since completion times are interdependent
        if changed and len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.TimeSpentRole, self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

        # Update countdown timer displays and notify listeners (like DiagramModel)
        for i in countdown_task_indices:
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [
                self.CountdownRemainingRole,
                self.CountdownProgressRole,
                self.CountdownExpiredRole
            ])
            # Emit signal so DiagramModel can update its own dataChanged
            self.taskCountdownChanged.emit(i)

    def addTask(self, title: str, parent_row: int = -1) -> None:
        """Add a new task to the model."""
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
        self.totalEstimateChanged.emit()
        self.taskCountChanged.emit()

    def addTaskWithParent(self, title: str, parent_row: int = -1) -> int:
        """Add a new task and return its row index."""
        title = title.strip()
        if not title:
            return -1

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
            insert_pos = parent_row + 1
            while insert_pos < len(self._tasks) and self._tasks[insert_pos].indent_level > indent - 1:
                insert_pos += 1

        self.beginInsertRows(QModelIndex(), insert_pos, insert_pos)
        self._tasks.insert(insert_pos, task)
        self.endInsertRows()
        self.totalEstimateChanged.emit()
        self.taskCountChanged.emit()
        return insert_pos

    def toggleComplete(self, row: int, completed: bool) -> None:
        """Toggle task completion status."""
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
            # Clear countdown timer when task is completed
            task.countdown_duration = None
            task.countdown_start = None
        else:
            # Restart timing
            task.start_time = time.time()

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        self.taskCompletionChanged.emit(row, completed)
        self.avgTimeChanged.emit()
        self.totalEstimateChanged.emit()

        # Update estimates for all tasks
        if len(self._tasks) > 0:
            first = self.index(0, 0)
            last = self.index(len(self._tasks) - 1, 0)
            self.dataChanged.emit(first, last, [self.EstimatedTimeRole, self.CompletionTimeRole, self.EstimatedTimeOfDayRole])

    def addSubtask(self, parent_row: int) -> None:
        """Add a subtask under the given parent task."""
        if parent_row < 0 or parent_row >= len(self._tasks):
            return

        # Create placeholder subtask
        self.addTask("Subtask", parent_row)

    def renameTask(self, row: int, new_title: str) -> None:
        """Rename an existing task."""
        if row < 0 or row >= len(self._tasks):
            return

        new_title = new_title.strip()
        if not new_title:
            return

        old_title = self._tasks[row].title
        if old_title == new_title:
            return

        self._tasks[row].title = new_title
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.TitleRole])
        self.taskRenamed.emit(row, new_title)

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

    def removeAt(self, row: int) -> None:
        """Remove a task and all its children."""
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
        self.totalEstimateChanged.emit()
        self.taskCountChanged.emit()

    def _task_to_dict(
        self,
        task: Task,
        indent_level: Optional[int] = None,
        parent_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        task_dict = {
            "title": task.title,
            "completed": task.completed,
            "time_spent": task.time_spent,
            "parent_index": task.parent_index if parent_index is None else parent_index,
            "indent_level": task.indent_level if indent_level is None else indent_level,
            "custom_estimate": task.custom_estimate,
        }
        if task.countdown_duration is not None:
            task_dict["countdown_duration"] = task.countdown_duration
        if task.countdown_start is not None:
            task_dict["countdown_start"] = task.countdown_start
        return task_dict

    def getSubtasksData(self, parent_row: int) -> Dict[str, Any]:
        """Return child tasks of a parent as a to_dict-style payload."""
        if parent_row < 0 or parent_row >= len(self._tasks):
            return {"tasks": []}

        parent_indent = self._tasks[parent_row].indent_level
        start = parent_row + 1
        if start >= len(self._tasks) or self._tasks[start].indent_level <= parent_indent:
            return {"tasks": []}

        tasks_data: List[Dict[str, Any]] = []
        base_indent = parent_indent + 1
        last_index_by_indent: List[int] = []

        for i in range(start, len(self._tasks)):
            child = self._tasks[i]
            if child.indent_level <= parent_indent:
                break

            normalized_indent = max(0, child.indent_level - base_indent)
            while len(last_index_by_indent) <= normalized_indent:
                last_index_by_indent.append(-1)

            parent_index = -1 if normalized_indent == 0 else last_index_by_indent[normalized_indent - 1]
            tasks_data.append(self._task_to_dict(child, normalized_indent, parent_index))

            last_index_by_indent[normalized_indent] = len(tasks_data) - 1
            if len(last_index_by_indent) > normalized_indent + 1:
                last_index_by_indent = last_index_by_indent[: normalized_indent + 1]

        return {"tasks": tasks_data}

    def clear(self) -> None:
        """Clear all tasks from the model."""
        if not self._tasks:
            return
        self.beginRemoveRows(QModelIndex(), 0, len(self._tasks) - 1)
        self._tasks.clear()
        self.endRemoveRows()
        self.avgTimeChanged.emit()
        self.totalEstimateChanged.emit()
        self.taskCountChanged.emit()

    def pasteSampleTasks(self) -> None:
        """Add sample tasks for testing."""
        sample_tasks = [
            "Review pull requests",
            "Write documentation",
            "Fix critical bug",
            "Update dependencies",
            "Code review meeting",
        ]
        for title in sample_tasks:
            self.addTask(title)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tasks to a dictionary for saving.

        Returns:
            Dictionary containing all task data.
        """
        tasks_data = []
        for task in self._tasks:
            tasks_data.append(self._task_to_dict(task))
        return {"tasks": tasks_data}

    def from_dict(self, data: Dict[str, Any]) -> None:
        """Load tasks from a dictionary.

        Args:
            data: Dictionary containing task data (from to_dict).
        """
        self._loading = True
        try:
            # Clear existing tasks without emitting signals
            if self._tasks:
                self.beginRemoveRows(QModelIndex(), 0, len(self._tasks) - 1)
                self._tasks.clear()
                self.endRemoveRows()

            # Load new tasks with batch insertion
            tasks_data = data.get("tasks", [])
            if tasks_data:
                new_tasks = []
                for task_data in tasks_data:
                    task = Task(
                        title=task_data.get("title", ""),
                        completed=task_data.get("completed", False),
                        time_spent=task_data.get("time_spent", 0.0),
                        parent_index=task_data.get("parent_index", -1),
                        indent_level=task_data.get("indent_level", 0),
                        custom_estimate=task_data.get("custom_estimate"),
                        countdown_duration=task_data.get("countdown_duration"),
                        countdown_start=task_data.get("countdown_start"),
                    )
                    # Don't auto-start timing for loaded tasks
                    if not task.completed:
                        task.start_time = time.time()
                    new_tasks.append(task)

                # Batch insert all tasks at once
                self.beginInsertRows(QModelIndex(), 0, len(new_tasks) - 1)
                self._tasks.extend(new_tasks)
                self.endInsertRows()
        finally:
            self._loading = False

        self.avgTimeChanged.emit()
        self.totalEstimateChanged.emit()
        self.taskCountChanged.emit()


class TabModel(QAbstractListModel):
    """Qt model for managing multiple tabs in a project.

    Each tab contains its own TaskModel and DiagramModel data.
    """

    NameRole = Qt.UserRole + 1
    IndexRole = Qt.UserRole + 2
    CompletionRole = Qt.UserRole + 3
    ActiveTaskTitleRole = Qt.UserRole + 4
    PriorityRole = Qt.UserRole + 5

    tabsChanged = Signal()
    currentTabChanged = Signal()
    currentTabIndexChanged = Signal()

    def __init__(self):
        super().__init__()
        self._tabs: List[Tab] = [Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": []})]
        self._current_tab_index: int = 0

    def rowCount(self, parent: Optional[QModelIndex] = QModelIndex()) -> int:  # type: ignore[override]
        return len(self._tabs)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):  # type: ignore[override]
        if not index.isValid() or not (0 <= index.row() < len(self._tabs)):
            return None

        tab = self._tabs[index.row()]
        if role == self.NameRole:
            return tab.name
        if role == self.IndexRole:
            return index.row()
        if role == self.CompletionRole:
            return self._calculateTabCompletion(tab)
        if role == self.ActiveTaskTitleRole:
            return self._getActiveTaskTitle(tab)
        if role == self.PriorityRole:
            return tab.priority
        return None

    def roleNames(self) -> Dict[int, bytes]:  # type: ignore[override]
        return {
            self.NameRole: b"name",
            self.IndexRole: b"tabIndex",
            self.CompletionRole: b"completionPercent",
            self.ActiveTaskTitleRole: b"activeTaskTitle",
            self.PriorityRole: b"priority",
        }

    @Property(int, notify=currentTabIndexChanged)
    def currentTabIndex(self) -> int:
        return self._current_tab_index

    @Property(str, notify=currentTabChanged)
    def currentTabName(self) -> str:
        if 0 <= self._current_tab_index < len(self._tabs):
            return self._tabs[self._current_tab_index].name
        return ""

    @Property(int, notify=tabsChanged)
    def tabCount(self) -> int:
        return len(self._tabs)

    def _calculateTabCompletion(self, tab: Tab) -> float:
        tasks = tab.tasks.get("tasks", []) if tab.tasks else []
        if not tasks:
            return 0.0
        completed = sum(1 for task in tasks if task.get("completed"))
        return (completed / len(tasks)) * 100.0

    def _getActiveTaskTitle(self, tab: Tab) -> str:
        """Get the title of the active (current) task for a tab."""
        if not tab.diagram or not tab.tasks:
            return ""
        current_task_index = tab.diagram.get("current_task_index", -1)
        if current_task_index < 0:
            return ""
        tasks = tab.tasks.get("tasks", [])
        if current_task_index < len(tasks):
            return tasks[current_task_index].get("title", "")
        return ""

    @Slot(str)
    def addTab(self, name: str = "") -> None:
        """Add a new empty tab."""
        if not name or not name.strip():
            name = f"Tab {len(self._tabs) + 1}"

        new_tab = Tab(
            name=name.strip(),
            tasks={"tasks": []},
            diagram={"items": [], "edges": [], "strokes": []}
        )

        self.beginInsertRows(QModelIndex(), len(self._tabs), len(self._tabs))
        self._tabs.append(new_tab)
        self.endInsertRows()
        self.tabsChanged.emit()

    @Slot(int)
    def removeTab(self, index: int) -> None:
        """Remove a tab at the given index. Cannot remove last tab."""
        if len(self._tabs) <= 1:
            return  # Cannot remove last tab
        if index < 0 or index >= len(self._tabs):
            return

        self.beginRemoveRows(QModelIndex(), index, index)
        self._tabs.pop(index)
        self.endRemoveRows()

        # Adjust current tab index if needed
        if self._current_tab_index >= len(self._tabs):
            self._current_tab_index = len(self._tabs) - 1
            self.currentTabIndexChanged.emit()
            self.currentTabChanged.emit()
        elif self._current_tab_index > index:
            self._current_tab_index -= 1
            self.currentTabIndexChanged.emit()

        self.tabsChanged.emit()

    @Slot(int, str)
    def renameTab(self, index: int, name: str) -> None:
        """Rename a tab."""
        if index < 0 or index >= len(self._tabs):
            return
        if not name or not name.strip():
            return

        self._tabs[index].name = name.strip()
        model_index = self.index(index, 0)
        self.dataChanged.emit(model_index, model_index, [self.NameRole])
        if index == self._current_tab_index:
            self.currentTabChanged.emit()

    @Slot(int, int)
    def setPriority(self, index: int, priority: int) -> None:
        """Set the priority for a tab (0 = none, 1-3 = priority levels)."""
        if index < 0 or index >= len(self._tabs):
            return
        if priority < 0 or priority > 3:
            return

        self._tabs[index].priority = priority
        model_index = self.index(index, 0)
        self.dataChanged.emit(model_index, model_index, [self.PriorityRole])

    @Slot(int)
    def setCurrentTab(self, index: int) -> None:
        """Switch to a different tab."""
        if index < 0 or index >= len(self._tabs):
            return
        if index == self._current_tab_index:
            return

        self._current_tab_index = index
        self.currentTabIndexChanged.emit()
        self.currentTabChanged.emit()

    def getCurrentTabData(self) -> Tab:
        """Get the current tab's data."""
        return self._tabs[self._current_tab_index]

    def setCurrentTabData(self, tasks: Dict[str, Any], diagram: Dict[str, Any]) -> None:
        """Update the current tab's data."""
        if 0 <= self._current_tab_index < len(self._tabs):
            self._tabs[self._current_tab_index].tasks = tasks
            self._tabs[self._current_tab_index].diagram = diagram
            model_index = self.index(self._current_tab_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CompletionRole, self.ActiveTaskTitleRole])

    def setTabData(self, index: int, tasks: Dict[str, Any], diagram: Dict[str, Any]) -> None:
        """Update a specific tab's data."""
        if 0 <= index < len(self._tabs):
            self._tabs[index].tasks = tasks
            self._tabs[index].diagram = diagram
            model_index = self.index(index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CompletionRole, self.ActiveTaskTitleRole])

    def updateCurrentTabTasks(self, tasks: Dict[str, Any]) -> None:
        """Update only the current tab's tasks data."""
        if 0 <= self._current_tab_index < len(self._tabs):
            self._tabs[self._current_tab_index].tasks = tasks
            model_index = self.index(self._current_tab_index, 0)
            self.dataChanged.emit(model_index, model_index, [self.CompletionRole, self.ActiveTaskTitleRole])

    def getAllTabs(self) -> List[Tab]:
        """Get all tabs."""
        return self._tabs

    def setTabs(self, tabs: List[Tab], active_tab: int = 0) -> None:
        """Replace all tabs with new data."""
        self.beginResetModel()
        self._tabs = tabs if tabs else [Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": []})]
        self.endResetModel()

        # Validate and set active tab index
        if active_tab < 0 or active_tab >= len(self._tabs):
            active_tab = 0
        self._current_tab_index = active_tab

        self.tabsChanged.emit()
        self.currentTabIndexChanged.emit()
        self.currentTabChanged.emit()

    def clear(self) -> None:
        """Reset to a single empty tab."""
        self.setTabs([Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": []})], 0)

    @Slot(int, int)
    def moveTab(self, from_index: int, to_index: int) -> None:
        """Move a tab to a new index."""
        if from_index == to_index:
            return
        if not (0 <= from_index < len(self._tabs) and 0 <= to_index < len(self._tabs)):
            return

        destination = to_index + 1 if to_index > from_index else to_index
        self.beginMoveRows(QModelIndex(), from_index, from_index, QModelIndex(), destination)
        tab = self._tabs.pop(from_index)
        self._tabs.insert(to_index, tab)
        self.endMoveRows()

        if self._current_tab_index == from_index:
            self._current_tab_index = to_index
            self.currentTabIndexChanged.emit()
            self.currentTabChanged.emit()
        elif from_index < self._current_tab_index <= to_index:
            self._current_tab_index -= 1
            self.currentTabIndexChanged.emit()
        elif to_index <= self._current_tab_index < from_index:
            self._current_tab_index += 1
            self.currentTabIndexChanged.emit()


class ProjectManager(QObject):
    """Manager for saving and loading project files.

    Project files are JSON files containing:
    - v1.0: Task list data and diagram data (single tab)
    - v1.1: Multiple tabs, each with its own tasks and diagram data
    """

    PROJECT_VERSION = "1.1"
    MAX_RECENT_PROJECTS = 8

    saveCompleted = Signal(str)  # Emitted with file path after successful save
    loadCompleted = Signal(str)  # Emitted with file path after successful load
    errorOccurred = Signal(str)  # Emitted with error message on failure
    recentProjectsChanged = Signal()  # Emitted when recent projects list changes
    currentFilePathChanged = Signal()  # Emitted when current file path changes
    tabSwitched = Signal()  # Emitted when switching to a different tab

    def __init__(self, task_model: TaskModel, diagram_model_or_manager, tab_model: Optional["TabModel"] = None):
        """Initialize ProjectManager.

        Args:
            task_model: The TaskModel instance.
            diagram_model_or_manager: Either a DiagramModel directly or an
                ActionDrawManager (for backwards compatibility).
            tab_model: Optional TabModel for multi-tab support.
        """
        super().__init__()
        self._task_model = task_model
        # Support both DiagramModel directly and ActionDrawManager (backwards compat)
        if hasattr(diagram_model_or_manager, 'diagram_model'):
            self._diagram_model = diagram_model_or_manager.diagram_model
        else:
            self._diagram_model = diagram_model_or_manager
        self._tab_model = tab_model
        self._current_file_path: str = ""
        self._settings = QSettings("ProgressTracker", "ProgressTracker")
        self._recent_projects: List[str] = self._load_recent_projects()
        if self._tab_model is not None:
            self._task_model.taskCompletionChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskCountChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskRenamed.connect(self._refreshCurrentTabTasks)
            # Connect diagram model's currentTaskChanged to update tab sidebar
            if hasattr(self._diagram_model, 'currentTaskChanged'):
                self._diagram_model.currentTaskChanged.connect(self._refreshCurrentTabDiagram)

    def _load_recent_projects(self) -> List[str]:
        """Load recent projects list from settings."""
        stored = self._settings.value("recentProjects", [])
        # QSettings may return a string if only one item, or None
        if stored is None:
            return []
        if isinstance(stored, str):
            stored = [stored] if stored else []
        if isinstance(stored, list):
            # Filter out non-existent files
            return [p for p in stored if p and os.path.exists(p)][:self.MAX_RECENT_PROJECTS]
        return []

    def _save_recent_projects(self) -> None:
        """Save recent projects list to settings."""
        self._settings.setValue("recentProjects", self._recent_projects)
        self._settings.sync()  # Ensure settings are written to disk

    def _add_to_recent(self, file_path: str) -> None:
        """Add a project to the recent projects list."""
        if not file_path or not os.path.exists(file_path):
            return
        # Remove if already in list
        if file_path in self._recent_projects:
            self._recent_projects.remove(file_path)
        # Add to front
        self._recent_projects.insert(0, file_path)
        # Trim to max size
        self._recent_projects = self._recent_projects[:self.MAX_RECENT_PROJECTS]
        self._save_recent_projects()
        self.recentProjectsChanged.emit()

    @Property("QVariantList", notify=recentProjectsChanged)
    def recentProjects(self) -> List[str]:
        """Return the list of recent project file paths."""
        return self._recent_projects

    @Slot()
    def newInstanceActionDraw(self) -> None:
        """Open a new instance of ActionDraw."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        actiondraw_path = os.path.join(script_dir, "actiondraw.py")
        self._launchScript(actiondraw_path)

    def _launchScript(self, script_path: str) -> None:
        """Launch a Python script as a new process."""
        try:
            subprocess.Popen(
                [sys.executable, os.path.abspath(script_path)],
                start_new_session=True,
            )
        except OSError as e:
            self.errorOccurred.emit(f"Failed to open new instance: {e}")

    @Slot(result=list)
    def getRecentProjectNames(self) -> List[Dict[str, str]]:
        """Return list of recent projects with display name and path."""
        result = []
        for path in self._recent_projects:
            name = os.path.basename(path)
            # Remove .progress extension for display
            if name.endswith(".progress"):
                name = name[:-9]
            result.append({"name": name, "path": path})
        return result

    @Property(str, notify=currentFilePathChanged)
    def currentFilePath(self) -> str:
        """Return the current project file path."""
        return self._current_file_path

    def _normalize_file_path(self, file_path: str) -> str:
        """Convert file URLs into local paths, including Windows file URLs."""
        if file_path.startswith("file:"):
            url = QUrl(file_path)
            if url.isLocalFile():
                file_path = url.toLocalFile()
            else:
                file_path = url.path()
        if os.name == "nt" and file_path.startswith("/") and len(file_path) > 2 and file_path[2] == ":":
            file_path = file_path[1:]
        return file_path

    @Slot(result=bool)
    def hasCurrentFile(self) -> bool:
        """Return True if a current project file is set."""
        return bool(self._current_file_path)

    @Slot()
    def saveCurrentProject(self) -> None:
        """Save the current project to the existing file path."""
        if not self._current_file_path:
            self.errorOccurred.emit("No current project file selected")
            return
        self.saveProject(self._current_file_path)

    def _saveCurrentTabState(self) -> None:
        """Save the current task/diagram state to the tab model."""
        if self._tab_model is not None:
            self._tab_model.setCurrentTabData(
                self._task_model.to_dict(),
                self._diagram_model.to_dict()
            )

    def _refreshCurrentTabTasks(self, *args) -> None:
        if self._tab_model is not None and not self._task_model._loading:
            self._tab_model.updateCurrentTabTasks(self._task_model.to_dict())

    def _refreshCurrentTabDiagram(self) -> None:
        """Update the current tab's diagram data (including active task)."""
        if self._tab_model is not None:
            self._tab_model.setCurrentTabData(
                self._task_model.to_dict(),
                self._diagram_model.to_dict()
            )

    @Slot(str)
    def saveProject(self, file_path: str) -> None:
        """Save the current project to a JSON file in v1.1 format.

        Args:
            file_path: Path to save the project file (should end in .progress)
        """
        file_path = self._normalize_file_path(file_path)

        if not file_path:
            self.errorOccurred.emit("No file path specified")
            return

        # Ensure .progress extension
        if not file_path.endswith(".progress"):
            file_path += ".progress"

        try:
            # Save current tab state first
            self._saveCurrentTabState()

            if self._tab_model is not None:
                # v1.1 format with tabs
                tabs_data = []
                for tab in self._tab_model.getAllTabs():
                    tabs_data.append({
                        "name": tab.name,
                        "tasks": tab.tasks,
                        "diagram": tab.diagram,
                        "priority": tab.priority,
                    })

                project_data = {
                    "version": self.PROJECT_VERSION,
                    "saved_at": datetime.now().isoformat(),
                    "tabs": tabs_data,
                    "active_tab": self._tab_model.currentTabIndex,
                }
            else:
                # Fallback: save as single tab in v1.1 format
                project_data = {
                    "version": self.PROJECT_VERSION,
                    "saved_at": datetime.now().isoformat(),
                    "tabs": [{
                        "name": "Main",
                        "tasks": self._task_model.to_dict(),
                        "diagram": self._diagram_model.to_dict(),
                    }],
                    "active_tab": 0,
                }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, ensure_ascii=False, separators=(",", ":"))

            self._current_file_path = file_path
            self.currentFilePathChanged.emit()
            self._add_to_recent(file_path)
            self.saveCompleted.emit(file_path)
            print(f"Project saved to: {file_path}")

        except (OSError, IOError) as e:
            error_msg = f"Failed to save project: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)

    def _loadFromV1(self, project_data: Dict[str, Any]) -> List[Tab]:
        """Convert v1.0 format data to tabs structure.

        Args:
            project_data: Project data in v1.0 format (tasks + diagram at root).

        Returns:
            List containing a single Tab with the v1.0 data.
        """
        tasks_data = project_data.get("tasks", {"tasks": []})
        diagram_data = project_data.get("diagram", {"items": [], "edges": [], "strokes": []})
        return [Tab(name="Main", tasks=tasks_data, diagram=diagram_data)]

    @Slot(str)
    def loadProject(self, file_path: str) -> None:
        """Load a project from a JSON file.

        Supports both v1.0 (single tab) and v1.1 (multi-tab) formats.

        Args:
            file_path: Path to the project file
        """
        file_path = self._normalize_file_path(file_path)

        if not file_path:
            self.errorOccurred.emit("No file path specified")
            return

        if not os.path.exists(file_path):
            self.errorOccurred.emit(f"File not found: {file_path}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                project_data = json.load(f)

            version = project_data.get("version", "1.0")
            active_tab = 0

            # Handle different versions
            if version == "1.0" or "tabs" not in project_data:
                # v1.0 format: convert to single-tab structure
                print(f"Loading v1.0 project, converting to multi-tab format")
                tabs = self._loadFromV1(project_data)
            else:
                # v1.1+ format: load tabs directly
                tabs_data = project_data.get("tabs", [])
                tabs = []
                for tab_data in tabs_data:
                    tabs.append(Tab(
                        name=tab_data.get("name", "Tab"),
                        tasks=tab_data.get("tasks", {"tasks": []}),
                        diagram=tab_data.get("diagram", {"items": [], "edges": [], "strokes": []}),
                        priority=tab_data.get("priority", 0)
                    ))
                active_tab = project_data.get("active_tab", 0)

                # Ensure at least one tab exists
                if not tabs:
                    tabs = [Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": []})]

            # Validate active_tab index
            if active_tab < 0 or active_tab >= len(tabs):
                active_tab = 0

            # Update tab model if available
            if self._tab_model is not None:
                self._tab_model.setTabs(tabs, active_tab)

            # Load the active tab's data into the models
            active_tab_data = tabs[active_tab]
            self._task_model.from_dict(active_tab_data.tasks)
            self._diagram_model.from_dict(active_tab_data.diagram)

            self._current_file_path = file_path
            self.currentFilePathChanged.emit()
            self._add_to_recent(file_path)
            self.loadCompleted.emit(file_path)
            print(f"Project loaded from: {file_path}")

        except json.JSONDecodeError as e:
            error_msg = f"Invalid project file format: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)
        except (OSError, IOError) as e:
            error_msg = f"Failed to load project: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)
        except (KeyError, TypeError) as e:
            error_msg = f"Corrupted project file: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)

    @Slot(int)
    def drillToTab(self, task_index: int) -> None:
        """Switch to (or create) a tab for a task's subtasks."""
        if self._tab_model is None:
            return
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return

        task_title = self._task_model.getTaskTitle(task_index).strip()
        if not task_title:
            return

        target_index = -1
        for idx, tab in enumerate(self._tab_model.getAllTabs()):
            if tab.name == task_title:
                target_index = idx
                break

        if target_index == -1:
            subtasks_data = self._task_model.getSubtasksData(task_index)
            diagram_data = {
                "items": [],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            }
            self._tab_model.addTab(task_title)
            target_index = self._tab_model.tabCount - 1
            self._tab_model.setTabData(target_index, subtasks_data, diagram_data)

        self.switchTab(target_index)

    @Slot(int)
    def switchTab(self, index: int) -> None:
        """Switch to a different tab, saving current state first.

        Args:
            index: Index of the tab to switch to.
        """
        if self._tab_model is None:
            return

        # Save current tab state
        self._saveCurrentTabState()

        # Switch tab in tab model
        self._tab_model.setCurrentTab(index)

        # Load new tab data into models
        tab_data = self._tab_model.getCurrentTabData()
        self._task_model.from_dict(tab_data.tasks)
        self._diagram_model.from_dict(tab_data.diagram)

        self.tabSwitched.emit()

    @Slot()
    def reloadCurrentTab(self) -> None:
        """Reload the current tab's data without saving first.

        Use this after tab deletion to load the new current tab's data
        without overwriting it with stale data from the deleted tab.
        """
        if self._tab_model is None:
            return

        tab_data = self._tab_model.getCurrentTabData()
        self._task_model.from_dict(tab_data.tasks)
        self._diagram_model.from_dict(tab_data.diagram)

        self.tabSwitched.emit()
