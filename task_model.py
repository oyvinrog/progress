"""Shared task model for use across actiondraw and other modules.

This module provides the Task dataclass and TaskModel class that were
previously embedded in progress_list.py, making them available for
independent use by actiondraw.
"""

import copy
import json
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import (
    QAbstractListModel,
    QCoreApplication,
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
from progress_crypto import (
    CryptoError,
    EncryptionCredentials,
    decrypt_project_data,
    encrypt_project_data,
    has_yubikey_cli,
    is_encrypted_envelope,
    yubikey_support_guidance,
)
from actiondraw.priorityplot.model import (
    clamp_subjective_value,
    clamp_time_hours,
    compute_priority_score,
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
    reminder_at: Optional[float] = None  # local timestamp when reminder should fire


@dataclass
class Tab:
    """Represents a single tab containing tasks and diagram data."""
    name: str
    tasks: Dict[str, Any]  # TaskModel.to_dict() data
    diagram: Dict[str, Any]  # DiagramModel.to_dict() data
    priority: int = 0  # 0 = no priority, 1-3 = priority levels
    priority_time_hours: float = 1.01
    priority_subjective_value: float = 1.0
    priority_score: float = 0.0
    include_in_priority_plot: bool = True


@dataclass
class GamificationState:
    """Project-wide gamification progression state."""

    xp_total: int = 0
    coins_total: int = 0
    current_streak_hours: int = 0
    best_streak_hours: int = 0
    last_progress_hour_epoch: Optional[int] = None
    hourly_completions: int = 0
    hourly_goal_completions: int = 3
    pouch_items: Dict[str, int] = field(default_factory=dict)
    pouch_capacity: int = 20
    active_effects: Dict[str, int] = field(default_factory=dict)
    shop_catalog_version: str = "v1"
    coins_earned_total: int = 0
    coins_spent_total: int = 0
    items_used_total: int = 0
    items_dropped_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "xp_total": self.xp_total,
            "coins_total": self.coins_total,
            "current_streak_hours": self.current_streak_hours,
            "best_streak_hours": self.best_streak_hours,
            "hourly_completions": self.hourly_completions,
            "hourly_goal_completions": self.hourly_goal_completions,
            "pouch_items": dict(self.pouch_items),
            "pouch_capacity": self.pouch_capacity,
            "active_effects": dict(self.active_effects),
            "shop_catalog_version": self.shop_catalog_version,
            "coins_earned_total": self.coins_earned_total,
            "coins_spent_total": self.coins_spent_total,
            "items_used_total": self.items_used_total,
            "items_dropped_total": self.items_dropped_total,
        }
        if self.last_progress_hour_epoch is not None:
            payload["last_progress_hour_epoch"] = self.last_progress_hour_epoch
        return payload


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
    ReminderActiveRole = Qt.UserRole + 13
    ReminderAtRole = Qt.UserRole + 14

    avgTimeChanged = Signal()
    totalEstimateChanged = Signal()
    taskCountChanged = Signal()
    taskRenamed = Signal(int, str, arguments=['taskIndex', 'newTitle'])
    taskCompletionChanged = Signal(int, bool, arguments=['taskIndex', 'completed'])
    taskCountdownChanged = Signal(int, arguments=['taskIndex'])
    taskReminderChanged = Signal(int, arguments=['taskIndex'])
    taskReminderDue = Signal(int, str, arguments=['taskIndex', 'taskTitle'])

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
        elif role == self.ReminderActiveRole:
            return self._isReminderActive(task)
        elif role == self.ReminderAtRole:
            return self._formatReminderAt(task)
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
            self.ReminderActiveRole: b"reminderActive",
            self.ReminderAtRole: b"reminderAt",
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

    def _isReminderActive(self, task: Task) -> bool:
        """Return True when the task has an active reminder."""
        return not task.completed and task.reminder_at is not None

    def _formatReminderAt(self, task: Task) -> str:
        """Return a human-readable local datetime for the reminder."""
        if task.completed or task.reminder_at is None:
            return ""
        return datetime.fromtimestamp(task.reminder_at).strftime("%Y-%m-%d %H:%M")

    def _parseReminderDateTime(self, reminder_str: str) -> Optional[float]:
        """Parse reminder datetime string as local time and return timestamp."""
        normalized = reminder_str.strip()
        if not normalized:
            return None

        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(normalized, fmt)
                return parsed.timestamp()
            except ValueError:
                continue

        try:
            # Supports ISO inputs including timezone offsets.
            parsed = datetime.fromisoformat(normalized)
            return parsed.timestamp()
        except ValueError:
            return None

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

    @Slot(int, str, result=bool)
    def setReminderAt(self, row: int, reminder_at_str: str) -> bool:
        """Set a local date/time reminder for a task.

        Accepted formats include:
        - YYYY-MM-DD HH:MM
        - YYYY-MM-DD HH:MM:SS
        - YYYY-MM-DDTHH:MM
        - YYYY-MM-DDTHH:MM:SS
        """
        if row < 0 or row >= len(self._tasks):
            return False

        reminder_at = self._parseReminderDateTime(reminder_at_str)
        if reminder_at is None:
            return False

        task = self._tasks[row]
        task.reminder_at = reminder_at

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
        self.taskReminderChanged.emit(row)
        return True

    @Slot(int)
    def clearReminderAt(self, row: int) -> None:
        """Clear a task reminder."""
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        if task.reminder_at is None:
            return
        task.reminder_at = None

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
        self.taskReminderChanged.emit(row)

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
        due_reminders: List[Tuple[int, str]] = []

        for i, task in enumerate(self._tasks):
            if not task.completed and task.start_time:
                elapsed = (current_time - task.start_time) / 60.0  # to minutes
                task.time_spent += elapsed
                task.start_time = current_time
                changed = True

            # Track tasks with active countdown timers
            if task.countdown_duration is not None and task.countdown_start is not None:
                countdown_task_indices.append(i)

            if task.reminder_at is not None and not task.completed and task.reminder_at <= current_time:
                due_reminders.append((i, task.title))

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

        for i, task_title in due_reminders:
            task = self._tasks[i]
            task.reminder_at = None
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
            self.taskReminderChanged.emit(i)
            self.taskReminderDue.emit(i, task_title)

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
        had_active_reminder = task.reminder_at is not None
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
            task.reminder_at = None
        else:
            # Restart timing
            task.start_time = time.time()

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        self.taskCompletionChanged.emit(row, completed)
        if completed and had_active_reminder:
            self.taskReminderChanged.emit(row)
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
        if task.reminder_at is not None:
            task_dict["reminder_at"] = task.reminder_at
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
                        reminder_at=task_data.get("reminder_at"),
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
    PriorityTimeHoursRole = Qt.UserRole + 6
    PrioritySubjectiveValueRole = Qt.UserRole + 7
    PriorityScoreRole = Qt.UserRole + 8
    IncludeInPriorityPlotRole = Qt.UserRole + 9

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
        if role == self.PriorityTimeHoursRole:
            return tab.priority_time_hours
        if role == self.PrioritySubjectiveValueRole:
            return tab.priority_subjective_value
        if role == self.PriorityScoreRole:
            return tab.priority_score
        if role == self.IncludeInPriorityPlotRole:
            return tab.include_in_priority_plot
        return None

    def roleNames(self) -> Dict[int, bytes]:  # type: ignore[override]
        return {
            self.NameRole: b"name",
            self.IndexRole: b"tabIndex",
            self.CompletionRole: b"completionPercent",
            self.ActiveTaskTitleRole: b"activeTaskTitle",
            self.PriorityRole: b"priority",
            self.PriorityTimeHoursRole: b"priorityTimeHours",
            self.PrioritySubjectiveValueRole: b"prioritySubjectiveValue",
            self.PriorityScoreRole: b"priorityScore",
            self.IncludeInPriorityPlotRole: b"includeInPriorityPlot",
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

    def _tabLinksToName(self, tab: Tab, target_name: str) -> bool:
        if not target_name:
            return False
        tasks = tab.tasks.get("tasks", []) if tab.tasks else []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            if str(task.get("title", "")).strip() == target_name:
                return True
        return False

    @Slot(result=list)
    def getTabsLinkingToCurrentTab(self) -> List[Dict[str, Any]]:
        """Return tabs that contain a task linking to the current tab."""
        if not (0 <= self._current_tab_index < len(self._tabs)):
            return []

        current_tab_name = self._tabs[self._current_tab_index].name.strip()
        if not current_tab_name:
            return []

        links: List[Dict[str, Any]] = []
        for idx, tab in enumerate(self._tabs):
            if idx == self._current_tab_index:
                continue
            if not self._tabLinksToName(tab, current_tab_name):
                continue
            links.append(
                {
                    "tabIndex": idx,
                    "name": tab.name,
                    "completionPercent": self._calculateTabCompletion(tab),
                    "activeTaskTitle": self._getActiveTaskTitle(tab),
                }
            )
        return links

    def _tab_name_to_index_map(self) -> Dict[str, int]:
        name_to_index: Dict[str, int] = {}
        for idx, tab in enumerate(self._tabs):
            name = str(getattr(tab, "name", "") or "").strip()
            if not name or name in name_to_index:
                continue
            name_to_index[name] = idx
        return name_to_index

    def _extract_tab_tasks(self, tab: Tab) -> List[Dict[str, Any]]:
        tasks_payload = tab.tasks if isinstance(tab.tasks, dict) else {}
        tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
        if not isinstance(tasks, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for task in tasks:
            normalized.append(task if isinstance(task, dict) else {})
        return normalized

    def _extract_tab_items(self, tab: Tab) -> List[Dict[str, Any]]:
        diagram_payload = tab.diagram if isinstance(tab.diagram, dict) else {}
        items = diagram_payload.get("items", []) if isinstance(diagram_payload, dict) else []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _build_hierarchy_tab_node(
        self,
        tab_index: int,
        name_to_index: Dict[str, int],
        path_tab_indices: Set[int],
    ) -> Dict[str, Any]:
        if tab_index < 0 or tab_index >= len(self._tabs):
            return {}

        tab = self._tabs[tab_index]
        tab_path = set(path_tab_indices)
        tab_path.add(tab_index)

        tasks = self._extract_tab_tasks(tab)
        items = self._extract_tab_items(tab)

        children: List[Dict[str, Any]] = []
        for item in items:
            item_id = str(item.get("id", ""))
            item_type = str(item.get("item_type", ""))
            item_text = str(item.get("text", ""))
            try:
                task_index = int(item.get("task_index", -1))
            except (TypeError, ValueError):
                task_index = -1

            # Navigator should hide completed tasks.
            if item_type == "task" and 0 <= task_index < len(tasks):
                if bool(tasks[task_index].get("completed", False)):
                    continue

            linked_tab_index = -1
            linked_tab_name = ""
            if 0 <= task_index < len(tasks):
                task_title = str(tasks[task_index].get("title", "")).strip()
                linked_tab_index = name_to_index.get(task_title, -1)
                if linked_tab_index >= 0:
                    linked_tab_name = str(self._tabs[linked_tab_index].name)

            item_node: Dict[str, Any] = {
                "kind": "diagramNode",
                "itemId": item_id,
                "itemType": item_type,
                "text": item_text,
                "taskIndex": task_index,
                "sourceTabIndex": tab_index,
                "sourceTabName": tab.name,
                "linkedTabIndex": linked_tab_index,
                "linkedTabName": linked_tab_name,
                "hasLinkedSubtab": linked_tab_index >= 0,
                "children": [],
            }

            if linked_tab_index >= 0:
                if linked_tab_index in tab_path:
                    item_node["children"] = [{
                        "kind": "cycleRef",
                        "tabIndex": linked_tab_index,
                        "tabName": linked_tab_name,
                    }]
                else:
                    linked_node = self._build_hierarchy_tab_node(linked_tab_index, name_to_index, tab_path)
                    if linked_node:
                        item_node["children"] = [linked_node]

            children.append(item_node)

        return {
            "kind": "tab",
            "tabIndex": tab_index,
            "tabName": tab.name,
            "completionPercent": self._calculateTabCompletion(tab),
            "activeTaskTitle": self._getActiveTaskTitle(tab),
            "children": children,
        }

    @Slot(result=list)
    @Slot(int, result=list)
    def getHierarchyTree(self, root_tab_index: int = -1) -> List[Dict[str, Any]]:
        """Return recursive linked-subdiagram hierarchy.

        Args:
            root_tab_index: Optional tab index to use as a single hierarchy root.
                If negative, all tabs are returned as top-level roots.
        """
        name_to_index = self._tab_name_to_index_map()
        hierarchy: List[Dict[str, Any]] = []

        if root_tab_index >= 0:
            if root_tab_index >= len(self._tabs):
                return []
            node = self._build_hierarchy_tab_node(root_tab_index, name_to_index, set())
            if node:
                hierarchy.append(node)
            return hierarchy

        for index in range(len(self._tabs)):
            node = self._build_hierarchy_tab_node(index, name_to_index, set())
            if node:
                hierarchy.append(node)
        return hierarchy

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

    def _computePriorityScore(self, value: float, time_hours: float) -> float:
        return compute_priority_score(value, time_hours)

    @Slot(int, float, float)
    def setPriorityPoint(self, index: int, time_hours: float, subjective_value: float) -> None:
        """Set tab priority plot coordinates, recompute scores, and auto-sort tabs."""
        if index < 0 or index >= len(self._tabs):
            return

        tab = self._tabs[index]
        if not tab.include_in_priority_plot:
            return
        tab.priority_time_hours = clamp_time_hours(time_hours)
        tab.priority_subjective_value = clamp_subjective_value(subjective_value)
        self.recomputeAndSortPriorities()

    @Slot(int, bool)
    def setIncludeInPriorityPlot(self, index: int, include: bool) -> None:
        """Include or exclude a tab from priority-plot scoring and plotting."""
        if index < 0 or index >= len(self._tabs):
            return
        tab = self._tabs[index]
        include_flag = bool(include)
        if tab.include_in_priority_plot == include_flag:
            return
        tab.include_in_priority_plot = include_flag
        self.recomputeAndSortPriorities()

    @Slot()
    def recomputeAndSortPriorities(self) -> None:
        """Recompute all priority scores and keep tabs sorted by score descending."""
        if not self._tabs:
            return

        current_tab = self._tabs[self._current_tab_index]
        for tab in self._tabs:
            if tab.include_in_priority_plot:
                tab.priority_score = self._computePriorityScore(
                    tab.priority_subjective_value,
                    tab.priority_time_hours,
                )
            else:
                tab.priority_score = 0.0

        indexed_tabs = list(enumerate(self._tabs))
        indexed_tabs.sort(
            key=lambda item: (
                0 if item[1].include_in_priority_plot else 1,
                -item[1].priority_score,
                item[0],
            )
        )
        sorted_tabs = [item[1] for item in indexed_tabs]
        if sorted_tabs == self._tabs:
            model_index = self.index(0, 0)
            end_index = self.index(len(self._tabs) - 1, 0)
            self.dataChanged.emit(
                model_index,
                end_index,
                [
                    self.PriorityTimeHoursRole,
                    self.PrioritySubjectiveValueRole,
                    self.PriorityScoreRole,
                    self.IncludeInPriorityPlotRole,
                ],
            )
            return

        self.beginResetModel()
        self._tabs = sorted_tabs
        self.endResetModel()

        self._current_tab_index = self._tabs.index(current_tab)
        self.tabsChanged.emit()
        self.currentTabIndexChanged.emit()
        self.currentTabChanged.emit()

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
        for tab in self._tabs:
            tab.priority_time_hours = clamp_time_hours(getattr(tab, "priority_time_hours", 1.01))
            tab.priority_subjective_value = clamp_subjective_value(getattr(tab, "priority_subjective_value", 1.0))
            tab.include_in_priority_plot = bool(getattr(tab, "include_in_priority_plot", True))
            if tab.include_in_priority_plot:
                tab.priority_score = self._computePriorityScore(
                    tab.priority_subjective_value,
                    tab.priority_time_hours,
                )
            else:
                tab.priority_score = 0.0
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
    ENCRYPTED_PROJECT_VERSION = "1.2"
    MAX_RECENT_PROJECTS = 8
    BASE_COMPLETION_XP = 10
    FIRST_COMPLETION_IN_HOUR_XP = 3
    MAX_STREAK_BONUS_XP = 7
    BASE_COMPLETION_COINS = 5
    FIRST_COMPLETION_IN_HOUR_COINS = 2
    MAX_STREAK_BONUS_COINS = 3
    BASE_DROP_CHANCE = 0.12
    LUCKY_CHARM_DROP_BONUS = 0.18
    FOCUS_POTION_COIN_BONUS = 2
    LUCKY_CHARM_USES = 3
    DEFAULT_POUCH_CAPACITY = 20

    ITEM_DEFS: Dict[str, Dict[str, Any]] = {
        "focus_potion": {
            "name": "Focus Potion",
            "description": "+2 coins on the next completion",
            "price": 18,
            "icon": "🧪",
            "item_type": "consumable",
        },
        "streak_shield": {
            "name": "Streak Shield",
            "description": "Prevents one streak reset from an hourly gap",
            "price": 30,
            "icon": "🛡️",
            "item_type": "consumable",
        },
        "lucky_charm": {
            "name": "Lucky Charm",
            "description": "Higher item drop chance for the next 3 completions",
            "price": 24,
            "icon": "🍀",
            "item_type": "consumable",
        },
        "cola": {
            "name": "Cola",
            "description": "Spend coins reward",
            "price": 50,
            "icon": "🥤",
            "item_type": "reward",
        },
        "snus": {
            "name": "Snus",
            "description": "Spend coins reward",
            "price": 100,
            "icon": "🧊",
            "item_type": "reward",
        },
        "bolle": {
            "name": "Bolle",
            "description": "Spend coins reward",
            "price": 100,
            "icon": "🥐",
            "item_type": "reward",
        },
        "cinema": {
            "name": "Cinema",
            "description": "Spend coins reward",
            "price": 500,
            "icon": "🎬",
            "item_type": "reward",
        },
        "espresso_shot": {
            "name": "Espresso Shot",
            "description": "Spend coins reward",
            "price": 20,
            "icon": "☕",
            "item_type": "reward",
        },
        "cocoa": {
            "name": "Cocoa",
            "description": "Spend coins reward",
            "price": 40,
            "icon": "🍫",
            "item_type": "reward",
        },
    }
    DROP_WEIGHTS: Tuple[Tuple[str, int], ...] = (
        ("focus_potion", 50),
        ("streak_shield", 30),
        ("lucky_charm", 20),
    )

    saveCompleted = Signal(str)  # Emitted with file path after successful save
    loadCompleted = Signal(str)  # Emitted with file path after successful load
    errorOccurred = Signal(str)  # Emitted with error message on failure
    recentProjectsChanged = Signal()  # Emitted when recent projects list changes
    currentFilePathChanged = Signal()  # Emitted when current file path changes
    sidebarExpandedChanged = Signal()
    tabSwitched = Signal()  # Emitted when switching to a different tab
    taskDrillRequested = Signal(int, arguments=["taskIndex"])
    taskReminderDue = Signal(int, int, str, arguments=["tabIndex", "taskIndex", "taskTitle"])
    yubiKeyInteractionStarted = Signal(str, arguments=["message"])
    yubiKeyInteractionFinished = Signal()
    gamificationChanged = Signal()

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
        set_tab_model = getattr(self._diagram_model, "setTabModel", None)
        if callable(set_tab_model):
            set_tab_model(self._tab_model)
        self._current_file_path: str = ""
        self._settings = QSettings("ProgressTracker", "ProgressTracker")
        self._sidebar_expanded = self._load_sidebar_expanded_setting()
        self._recent_projects: List[str] = self._load_recent_projects()
        self._gamification_state = GamificationState()
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._checkBackgroundTabReminders)
        self._reminder_timer.start(1000)
        self._task_model.taskReminderDue.connect(self._onCurrentTabReminderDue)
        self._task_model.taskCompletionChanged.connect(self._onTaskCompletionChanged)
        if self._tab_model is not None:
            self._task_model.taskCompletionChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskCountChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskRenamed.connect(self._refreshCurrentTabTasks)
            self._task_model.taskReminderChanged.connect(self._refreshCurrentTabTasks)
            # Connect diagram model's currentTaskChanged to update tab sidebar
            if hasattr(self._diagram_model, 'currentTaskChanged'):
                self._diagram_model.currentTaskChanged.connect(self._refreshCurrentTabDiagram)
        self._cached_encryption_credentials: Optional[EncryptionCredentials] = None
        self._cached_encryption_file_path: str = ""
        self._last_saved_snapshot = self._serialize_project_payload(self._build_project_data())

    def _onCurrentTabReminderDue(self, task_index: int, task_title: str) -> None:
        tab_index = self._tab_model.currentTabIndex if self._tab_model is not None else 0
        self.taskReminderDue.emit(tab_index, task_index, task_title)

    def _checkBackgroundTabReminders(self) -> None:
        """Emit due reminders from non-active tabs."""
        if self._tab_model is None:
            return

        now = time.time()
        active_tab = self._tab_model.currentTabIndex

        for tab_index, tab in enumerate(self._tab_model.getAllTabs()):
            if tab_index == active_tab:
                continue
            tasks_payload = tab.tasks if isinstance(tab.tasks, dict) else {}
            tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
            if not isinstance(tasks, list):
                continue

            tab_changed = False
            for task_index, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                if task.get("completed", False):
                    continue

                reminder_at = task.get("reminder_at")
                if reminder_at is None:
                    continue

                try:
                    reminder_ts = float(reminder_at)
                except (TypeError, ValueError):
                    continue

                if reminder_ts > now:
                    continue

                task.pop("reminder_at", None)
                tab_changed = True

                title = str(task.get("title", "")).strip() or "Task"
                self.taskReminderDue.emit(tab_index, task_index, title)

            if tab_changed:
                model_index = self._tab_model.index(tab_index, 0)
                self._tab_model.dataChanged.emit(
                    model_index,
                    model_index,
                    [self._tab_model.CompletionRole, self._tab_model.ActiveTaskTitleRole],
                )

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

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _currentHourEpoch() -> int:
        return int(time.time() // 3600)

    def _hourlyCompletionsForDisplay(self) -> int:
        current_hour = self._currentHourEpoch()
        if self._gamification_state.last_progress_hour_epoch != current_hour:
            return 0
        return self._gamification_state.hourly_completions

    def _normalizeItemCounts(self, payload: Any) -> Dict[str, int]:
        if not isinstance(payload, dict):
            return {}
        normalized: Dict[str, int] = {}
        for item_id in self.ITEM_DEFS.keys():
            count = max(0, self._safe_int(payload.get(item_id), 0))
            if count > 0:
                normalized[item_id] = count
        return normalized

    def _normalizeEffects(self, payload: Any) -> Dict[str, int]:
        if not isinstance(payload, dict):
            return {}
        normalized: Dict[str, int] = {}
        for effect_key in ("focus_next_completion", "streak_shield_charges", "lucky_charm_remaining"):
            count = max(0, self._safe_int(payload.get(effect_key), 0))
            if count > 0:
                normalized[effect_key] = count
        return normalized

    def _pouchItemCount(self, item_id: str) -> int:
        return max(0, self._safe_int(self._gamification_state.pouch_items.get(item_id), 0))

    def _pouchTotalCount(self) -> int:
        return sum(max(0, self._safe_int(v, 0)) for v in self._gamification_state.pouch_items.values())

    def _hasPouchSpace(self, quantity: int = 1) -> bool:
        if quantity <= 0:
            return True
        return self._pouchTotalCount() + quantity <= max(1, self._gamification_state.pouch_capacity)

    def _addPouchItem(self, item_id: str, quantity: int = 1) -> bool:
        if item_id not in self.ITEM_DEFS or quantity <= 0:
            return False
        if not self._hasPouchSpace(quantity):
            return False
        self._gamification_state.pouch_items[item_id] = self._pouchItemCount(item_id) + quantity
        return True

    def _consumePouchItem(self, item_id: str, quantity: int = 1) -> bool:
        if item_id not in self.ITEM_DEFS or quantity <= 0:
            return False
        count = self._pouchItemCount(item_id)
        if count < quantity:
            return False
        new_count = count - quantity
        if new_count <= 0:
            self._gamification_state.pouch_items.pop(item_id, None)
        else:
            self._gamification_state.pouch_items[item_id] = new_count
        return True

    def _effectCount(self, effect_key: str) -> int:
        return max(0, self._safe_int(self._gamification_state.active_effects.get(effect_key), 0))

    def _setEffectCount(self, effect_key: str, count: int) -> None:
        if count <= 0:
            self._gamification_state.active_effects.pop(effect_key, None)
        else:
            self._gamification_state.active_effects[effect_key] = int(count)

    def _chooseDropItemId(self) -> str:
        total_weight = sum(weight for _, weight in self.DROP_WEIGHTS)
        if total_weight <= 0:
            return ""
        roll = random.uniform(0.0, float(total_weight))
        cumulative = 0.0
        for item_id, weight in self.DROP_WEIGHTS:
            cumulative += float(weight)
            if roll <= cumulative:
                return item_id
        return self.DROP_WEIGHTS[-1][0]

    def _advanceHourlyStreakState(self, current_hour: int, first_completion_in_hour: bool) -> None:
        state = self._gamification_state
        if not first_completion_in_hour:
            state.hourly_completions += 1
            return

        previous_hour = state.last_progress_hour_epoch
        if previous_hour is None:
            state.current_streak_hours = 1
        elif current_hour == previous_hour + 1:
            state.current_streak_hours = max(1, state.current_streak_hours + 1)
        elif current_hour > previous_hour + 1:
            shield_charges = self._effectCount("streak_shield_charges")
            if shield_charges > 0:
                self._setEffectCount("streak_shield_charges", shield_charges - 1)
                state.current_streak_hours = max(1, state.current_streak_hours)
            else:
                state.current_streak_hours = 1
        else:
            state.current_streak_hours = max(1, state.current_streak_hours)

        state.last_progress_hour_epoch = current_hour
        state.hourly_completions = 1
        if state.current_streak_hours > state.best_streak_hours:
            state.best_streak_hours = state.current_streak_hours

    def _awardCompletionCoinsAndDrops(self, first_completion_in_hour: bool) -> None:
        state = self._gamification_state
        coins_gain = self.BASE_COMPLETION_COINS
        if first_completion_in_hour:
            coins_gain += self.FIRST_COMPLETION_IN_HOUR_COINS
            coins_gain += min(self.MAX_STREAK_BONUS_COINS, max(0, state.current_streak_hours - 1))

        focus_charges = self._effectCount("focus_next_completion")
        if focus_charges > 0:
            coins_gain += self.FOCUS_POTION_COIN_BONUS
            self._setEffectCount("focus_next_completion", focus_charges - 1)

        state.coins_total += coins_gain
        state.coins_earned_total += coins_gain

        drop_chance = self.BASE_DROP_CHANCE
        lucky_remaining = self._effectCount("lucky_charm_remaining")
        if lucky_remaining > 0:
            drop_chance += self.LUCKY_CHARM_DROP_BONUS
            self._setEffectCount("lucky_charm_remaining", lucky_remaining - 1)

        if self._hasPouchSpace() and random.random() < drop_chance:
            dropped_item = self._chooseDropItemId()
            if dropped_item and self._addPouchItem(dropped_item):
                state.items_dropped_total += 1

    @staticmethod
    def _computeLevelFields(xp_total: int) -> Tuple[int, int, int]:
        level = 1
        xp_remaining = max(0, int(xp_total))
        xp_for_next = 100
        while xp_remaining >= xp_for_next:
            xp_remaining -= xp_for_next
            level += 1
            xp_for_next = 100 * level
        return level, xp_remaining, xp_for_next

    def _loadGamificationState(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            self._gamification_state = GamificationState()
            self.gamificationChanged.emit()
            return

        hourly_goal = max(1, self._safe_int(payload.get("hourly_goal_completions"), 3))
        last_hour_raw = payload.get("last_progress_hour_epoch")
        last_hour = self._safe_int(last_hour_raw) if last_hour_raw is not None else None
        pouch_items = self._normalizeItemCounts(payload.get("pouch_items"))
        active_effects = self._normalizeEffects(payload.get("active_effects"))
        pouch_capacity = max(1, self._safe_int(payload.get("pouch_capacity"), self.DEFAULT_POUCH_CAPACITY))
        self._gamification_state = GamificationState(
            xp_total=max(0, self._safe_int(payload.get("xp_total"), 0)),
            coins_total=max(0, self._safe_int(payload.get("coins_total"), 0)),
            current_streak_hours=max(0, self._safe_int(payload.get("current_streak_hours"), 0)),
            best_streak_hours=max(0, self._safe_int(payload.get("best_streak_hours"), 0)),
            last_progress_hour_epoch=last_hour,
            hourly_completions=max(0, self._safe_int(payload.get("hourly_completions"), 0)),
            hourly_goal_completions=hourly_goal,
            pouch_items=pouch_items,
            pouch_capacity=pouch_capacity,
            active_effects=active_effects,
            shop_catalog_version=str(payload.get("shop_catalog_version", "v1")),
            coins_earned_total=max(0, self._safe_int(payload.get("coins_earned_total"), 0)),
            coins_spent_total=max(0, self._safe_int(payload.get("coins_spent_total"), 0)),
            items_used_total=max(0, self._safe_int(payload.get("items_used_total"), 0)),
            items_dropped_total=max(0, self._safe_int(payload.get("items_dropped_total"), 0)),
        )
        if self._gamification_state.best_streak_hours < self._gamification_state.current_streak_hours:
            self._gamification_state.best_streak_hours = self._gamification_state.current_streak_hours
        self.gamificationChanged.emit()

    def _awardCompletionGamification(self) -> None:
        state = self._gamification_state
        current_hour = self._currentHourEpoch()
        first_completion_in_hour = state.last_progress_hour_epoch != current_hour

        self._advanceHourlyStreakState(current_hour, first_completion_in_hour)

        xp_gain = self.BASE_COMPLETION_XP
        if first_completion_in_hour:
            xp_gain += self.FIRST_COMPLETION_IN_HOUR_XP
            streak_bonus = min(self.MAX_STREAK_BONUS_XP, max(0, state.current_streak_hours - 1))
            xp_gain += streak_bonus
        state.xp_total += xp_gain
        self._awardCompletionCoinsAndDrops(first_completion_in_hour)
        self.gamificationChanged.emit()

    def _onTaskCompletionChanged(self, _task_index: int, completed: bool) -> None:
        if not completed:
            return
        self._awardCompletionGamification()

    def _load_sidebar_expanded_setting(self) -> bool:
        """Load persisted sidebar expansion preference."""
        stored = self._settings.value("ui/sidebar_expanded", True)
        if isinstance(stored, bool):
            return stored
        if isinstance(stored, (int, float)):
            return bool(stored)
        if isinstance(stored, str):
            return stored.strip().lower() in {"1", "true", "yes", "on"}
        return True

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

    @Property(bool, notify=sidebarExpandedChanged)
    def sidebarExpanded(self) -> bool:
        """Return whether the tab sidebar should be expanded."""
        return self._sidebar_expanded

    @Slot(bool)
    def setSidebarExpanded(self, expanded: bool) -> None:
        """Persist and broadcast tab sidebar expansion state."""
        expanded_flag = bool(expanded)
        if self._sidebar_expanded == expanded_flag:
            return
        self._sidebar_expanded = expanded_flag
        self._settings.setValue("ui/sidebar_expanded", self._sidebar_expanded)
        self._settings.sync()
        self.sidebarExpandedChanged.emit()

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

    @Property(int, notify=gamificationChanged)
    def gamificationXp(self) -> int:
        return self._gamification_state.xp_total

    @Property(int, notify=gamificationChanged)
    def gamificationLevel(self) -> int:
        level, _, _ = self._computeLevelFields(self._gamification_state.xp_total)
        return level

    @Property(int, notify=gamificationChanged)
    def gamificationXpIntoLevel(self) -> int:
        _, xp_into_level, _ = self._computeLevelFields(self._gamification_state.xp_total)
        return xp_into_level

    @Property(int, notify=gamificationChanged)
    def gamificationXpForNextLevel(self) -> int:
        _, _, xp_for_next = self._computeLevelFields(self._gamification_state.xp_total)
        return xp_for_next

    @Property(float, notify=gamificationChanged)
    def gamificationLevelProgress(self) -> float:
        _, xp_into_level, xp_for_next = self._computeLevelFields(self._gamification_state.xp_total)
        if xp_for_next <= 0:
            return 0.0
        return xp_into_level / float(xp_for_next)

    @Property(int, notify=gamificationChanged)
    def gamificationCurrentStreakHours(self) -> int:
        return self._gamification_state.current_streak_hours

    @Property(int, notify=gamificationChanged)
    def gamificationBestStreakHours(self) -> int:
        return self._gamification_state.best_streak_hours

    @Property(int, notify=gamificationChanged)
    def gamificationHourlyGoalCompletions(self) -> int:
        return self._gamification_state.hourly_goal_completions

    @Property(int, notify=gamificationChanged)
    def gamificationHourlyCompletions(self) -> int:
        return self._hourlyCompletionsForDisplay()

    @Property(float, notify=gamificationChanged)
    def gamificationHourlyGoalProgress(self) -> float:
        goal = max(1, self._gamification_state.hourly_goal_completions)
        return min(1.0, self._hourlyCompletionsForDisplay() / float(goal))

    @Property(int, notify=gamificationChanged)
    def gamificationCoins(self) -> int:
        return self._gamification_state.coins_total

    @Property(int, notify=gamificationChanged)
    def gamificationPouchCount(self) -> int:
        return self._pouchTotalCount()

    @Property(int, notify=gamificationChanged)
    def gamificationPouchCapacity(self) -> int:
        return max(1, self._gamification_state.pouch_capacity)

    @Property(float, notify=gamificationChanged)
    def gamificationPouchFillPercent(self) -> float:
        capacity = max(1, self._gamification_state.pouch_capacity)
        return min(1.0, self._pouchTotalCount() / float(capacity))

    @Property("QVariantList", notify=gamificationChanged)
    def gamificationPouchSlots(self) -> List[Dict[str, Any]]:
        slots: List[Dict[str, Any]] = []
        capacity = max(1, self._gamification_state.pouch_capacity)
        flattened_ids: List[str] = []

        for item_id in self.ITEM_DEFS.keys():
            count = self._pouchItemCount(item_id)
            if count <= 0:
                continue
            flattened_ids.extend([item_id] * count)

        for idx in range(capacity):
            if idx < len(flattened_ids):
                item_id = flattened_ids[idx]
                item_def = self.ITEM_DEFS.get(item_id, {})
                slots.append(
                    {
                        "index": idx,
                        "filled": True,
                        "itemId": item_id,
                        "name": str(item_def.get("name", item_id)),
                        "icon": str(item_def.get("icon", "")),
                    }
                )
            else:
                slots.append(
                    {
                        "index": idx,
                        "filled": False,
                        "itemId": "",
                        "name": "",
                        "icon": "",
                    }
                )
        return slots

    @Property("QVariantList", notify=gamificationChanged)
    def gamificationPouchItems(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for item_id, item_def in self.ITEM_DEFS.items():
            count = self._pouchItemCount(item_id)
            if count <= 0:
                continue
            items.append(
                {
                    "id": item_id,
                    "name": item_def["name"],
                    "description": item_def["description"],
                    "icon": str(item_def.get("icon", "")),
                    "itemType": str(item_def.get("item_type", "consumable")),
                    "count": count,
                }
            )
        return items

    @Property("QVariantList", notify=gamificationChanged)
    def gamificationShopItems(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for item_id, item_def in self.ITEM_DEFS.items():
            items.append(
                {
                    "id": item_id,
                    "name": item_def["name"],
                    "description": item_def["description"],
                    "price": max(0, self._safe_int(item_def.get("price"), 0)),
                    "icon": str(item_def.get("icon", "")),
                    "itemType": str(item_def.get("item_type", "consumable")),
                    "canAfford": self._gamification_state.coins_total >= max(0, self._safe_int(item_def.get("price"), 0)),
                }
            )
        return items

    @Property(bool, notify=gamificationChanged)
    def gamificationCanAffordAnyShopItem(self) -> bool:
        if not self._hasPouchSpace():
            return False
        for item_def in self.ITEM_DEFS.values():
            price = max(0, self._safe_int(item_def.get("price"), 0))
            if self._gamification_state.coins_total >= price:
                return True
        return False

    @Slot(str, result=int)
    def getPouchItemCount(self, item_id: str) -> int:
        return self._pouchItemCount(str(item_id or ""))

    @Slot(str, result=bool)
    def buyShopItem(self, item_id: str) -> bool:
        item_key = str(item_id or "")
        item_def = self.ITEM_DEFS.get(item_key)
        if item_def is None:
            return False
        if not self._hasPouchSpace():
            return False
        price = max(0, self._safe_int(item_def.get("price"), 0))
        if self._gamification_state.coins_total < price:
            return False
        if not self._addPouchItem(item_key):
            return False
        self._gamification_state.coins_total -= price
        self._gamification_state.coins_spent_total += price
        self.gamificationChanged.emit()
        return True

    @Slot(str, result=bool)
    def usePouchItem(self, item_id: str) -> bool:
        item_key = str(item_id or "")
        item_def = self.ITEM_DEFS.get(item_key)
        if item_def is None:
            return False
        item_type = str(item_def.get("item_type", "consumable"))
        known_consumables = {"focus_potion", "streak_shield", "lucky_charm"}
        if item_type == "consumable" and item_key not in known_consumables:
            return False
        if not self._consumePouchItem(item_key):
            return False

        if item_key == "focus_potion":
            self._setEffectCount("focus_next_completion", self._effectCount("focus_next_completion") + 1)
        elif item_key == "streak_shield":
            self._setEffectCount("streak_shield_charges", self._effectCount("streak_shield_charges") + 1)
        elif item_key == "lucky_charm":
            self._setEffectCount("lucky_charm_remaining", self._effectCount("lucky_charm_remaining") + self.LUCKY_CHARM_USES)
        elif item_type == "reward":
            # Reward purchases are consumable from the pouch but have no gameplay effect.
            pass
        else:
            return False

        self._gamification_state.items_used_total += 1
        self.gamificationChanged.emit()
        return True

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

    def _build_project_data(self) -> Dict[str, Any]:
        """Build a normalized project payload from live in-memory state."""
        if self._tab_model is not None:
            tabs_data = []
            current_tab_index = self._tab_model.currentTabIndex
            current_tasks = self._task_model.to_dict()
            current_diagram = self._diagram_model.to_dict()
            for index, tab in enumerate(self._tab_model.getAllTabs()):
                tabs_data.append({
                    "name": tab.name,
                    "tasks": current_tasks if index == current_tab_index else tab.tasks,
                    "diagram": current_diagram if index == current_tab_index else tab.diagram,
                    "priority": tab.priority,
                    "priority_time_hours": tab.priority_time_hours,
                    "priority_subjective_value": tab.priority_subjective_value,
                    "priority_score": tab.priority_score,
                    "include_in_priority_plot": tab.include_in_priority_plot,
                })

            return {
                "version": self.PROJECT_VERSION,
                "tabs": tabs_data,
                "active_tab": current_tab_index,
                "gamification": self._gamification_state.to_dict(),
            }

        return {
            "version": self.PROJECT_VERSION,
            "tabs": [{
                "name": "Main",
                "tasks": self._task_model.to_dict(),
                "diagram": self._diagram_model.to_dict(),
            }],
            "active_tab": 0,
            "gamification": self._gamification_state.to_dict(),
        }

    def _serialize_project_payload(self, project_data: Dict[str, Any]) -> str:
        """Return deterministic JSON text for change detection."""
        normalized = self._normalize_project_payload_for_change_detection(project_data)
        return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _normalize_project_payload_for_change_detection(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize runtime-only fields so background timers do not mark projects as dirty."""
        normalized = copy.deepcopy(project_data)
        tabs = normalized.get("tabs")
        if not isinstance(tabs, list):
            return normalized

        for tab in tabs:
            if not isinstance(tab, dict):
                continue
            tasks_payload = tab.get("tasks")
            if not isinstance(tasks_payload, dict):
                continue
            tasks = tasks_payload.get("tasks")
            if not isinstance(tasks, list):
                continue
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                if not bool(task.get("completed", False)):
                    task.pop("time_spent", None)

        return normalized

    @Slot(result=bool)
    def hasUnsavedChanges(self) -> bool:
        """Return True when current in-memory state differs from last save/load snapshot."""
        current_snapshot = self._serialize_project_payload(self._build_project_data())
        return current_snapshot != self._last_saved_snapshot

    @Slot(result=bool)
    def saveCurrentProject(self) -> bool:
        """Save the current project to the existing file path."""
        if not self._current_file_path:
            self.errorOccurred.emit("No current project file selected")
            return False
        return self.saveProject(self._current_file_path, force_prompt=False)

    @Slot(str, result=bool)
    def saveProjectAs(self, file_path: str) -> bool:
        """Save project under a new path and always prompt for encryption choice."""
        return self.saveProject(file_path, force_prompt=True)

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

    def _begin_yubikey_interaction(self, operation: str) -> None:
        if operation == "load":
            message = "Touch your YubiKey to decrypt this project."
        else:
            message = "Touch your YubiKey to encrypt and save this project."
        self.yubiKeyInteractionStarted.emit(message)
        QCoreApplication.processEvents()

    def _end_yubikey_interaction(self) -> None:
        self.yubiKeyInteractionFinished.emit()
        QCoreApplication.processEvents()

    def _prompt_encryption_credentials(
        self,
        operation: str,
        file_path: str,
        envelope: Optional[Dict[str, Any]] = None,
    ) -> Optional[EncryptionCredentials]:
        """Prompt the user for credentials on each encrypted save/load operation."""
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        save_mode = operation == "save"
        title = "Save Encrypted Project" if save_mode else "Load Encrypted Project"

        if save_mode:
            modes = ["Passphrase only", "YubiKey only", "Passphrase + YubiKey"]
            mode, ok = QInputDialog.getItem(
                None,
                title,
                "Select encryption mode:",
                modes,
                0,
                False,
            )
            if not ok:
                return None
            require_passphrase = mode in ("Passphrase only", "Passphrase + YubiKey")
            require_yubikey = mode in ("YubiKey only", "Passphrase + YubiKey")
            slot_default = "2"
        else:
            if not isinstance(envelope, dict):
                self.errorOccurred.emit("Encrypted project metadata is missing")
                return None
            encryption = envelope.get("encryption")
            if not isinstance(encryption, dict):
                self.errorOccurred.emit("Encrypted project metadata is invalid")
                return None
            auth_mode = str(encryption.get("auth_mode", "")).strip()
            require_passphrase = auth_mode in ("passphrase", "passphrase+yubikey")
            require_yubikey = auth_mode in ("yubikey", "passphrase+yubikey")
            yk_meta = encryption.get("yubikey")
            slot_default = "2"
            if isinstance(yk_meta, dict):
                slot_default = str(yk_meta.get("slot", "2"))

        if require_yubikey and not has_yubikey_cli():
            self.errorOccurred.emit(yubikey_support_guidance())
            return None

        passphrase: Optional[str] = None
        if require_passphrase:
            prompt = "Enter passphrase:"
            entered, ok = QInputDialog.getText(None, title, prompt, QLineEdit.Password)
            if not ok:
                return None
            if not entered:
                self.errorOccurred.emit("Passphrase cannot be empty")
                return None
            passphrase = entered

        slot = "2"
        if require_yubikey:
            choices = ["1", "2"]
            index = 1 if slot_default not in choices else choices.index(slot_default)
            selected_slot, ok = QInputDialog.getItem(
                None,
                title,
                "Select YubiKey slot:",
                choices,
                index,
                False,
            )
            if not ok:
                return None
            slot = selected_slot

        return EncryptionCredentials(
            passphrase=passphrase,
            use_yubikey=require_yubikey,
            yubikey_slot=slot,
        )

    @Slot(result=bool)
    def hasYubiKeySupport(self) -> bool:
        """Return True when YubiKey CLI support is currently available."""
        return has_yubikey_cli()

    @Slot(result=str)
    def getYubiKeySupportGuidance(self) -> str:
        """Return setup guidance for enabling YubiKey support on this OS."""
        return yubikey_support_guidance()

    @Slot(str, result=bool)
    def saveProject(self, file_path: str, force_prompt: bool = True) -> bool:
        """Save the current project to a JSON file in v1.1 format.

        Args:
            file_path: Path to save the project file (should end in .progress)
            force_prompt: True to force prompting for encryption choice/credentials.
        """
        file_path = self._normalize_file_path(file_path)

        if not file_path:
            self.errorOccurred.emit("No file path specified")
            return False

        # Ensure .progress extension
        if not file_path.endswith(".progress"):
            file_path += ".progress"

        try:
            # Save current tab state first
            self._saveCurrentTabState()
            payload_data = self._build_project_data()
            project_data = dict(payload_data)
            project_data["saved_at"] = datetime.now().isoformat()

            credentials = None
            if (
                not force_prompt
                and self._cached_encryption_credentials is not None
                and self._cached_encryption_file_path == file_path
            ):
                credentials = EncryptionCredentials(
                    passphrase=self._cached_encryption_credentials.passphrase,
                    use_yubikey=self._cached_encryption_credentials.use_yubikey,
                    yubikey_slot=self._cached_encryption_credentials.yubikey_slot,
                )
            else:
                credentials = self._prompt_encryption_credentials("save", file_path)
            if credentials is None:
                return False

            if credentials.use_yubikey:
                self._begin_yubikey_interaction("save")
            try:
                encrypted_payload = encrypt_project_data(project_data, credentials)
                encrypted_payload["version"] = self.ENCRYPTED_PROJECT_VERSION
            finally:
                if credentials.use_yubikey:
                    self._end_yubikey_interaction()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_payload, f, ensure_ascii=False, separators=(",", ":"))

            self._current_file_path = file_path
            self._cached_encryption_file_path = file_path
            self._cached_encryption_credentials = EncryptionCredentials(
                passphrase=credentials.passphrase,
                use_yubikey=credentials.use_yubikey,
                yubikey_slot=credentials.yubikey_slot,
            )
            self.currentFilePathChanged.emit()
            self._add_to_recent(file_path)
            self._last_saved_snapshot = self._serialize_project_payload(payload_data)
            self.saveCompleted.emit(file_path)
            print(f"Project saved to: {file_path}")
            return True

        except (OSError, IOError) as e:
            error_msg = f"Failed to save project: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)
            return False
        except CryptoError as e:
            error_msg = f"Failed to save project: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)
            return False

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

            if is_encrypted_envelope(project_data):
                credentials = self._prompt_encryption_credentials("load", file_path, project_data)
                if credentials is None:
                    return
                if credentials.use_yubikey:
                    self._begin_yubikey_interaction("load")
                try:
                    project_data = decrypt_project_data(project_data, credentials)
                finally:
                    if credentials.use_yubikey:
                        self._end_yubikey_interaction()
                self._cached_encryption_file_path = file_path
                self._cached_encryption_credentials = EncryptionCredentials(
                    passphrase=credentials.passphrase,
                    use_yubikey=credentials.use_yubikey,
                    yubikey_slot=credentials.yubikey_slot,
                )

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
                        priority=tab_data.get("priority", 0),
                        priority_time_hours=tab_data.get("priority_time_hours", 1.01),
                        priority_subjective_value=tab_data.get("priority_subjective_value", 1.0),
                        priority_score=tab_data.get("priority_score", 0.0),
                        include_in_priority_plot=tab_data.get("include_in_priority_plot", True),
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
            self._loadGamificationState(project_data.get("gamification"))

            # Load the active tab's data into the models
            active_tab_data = tabs[active_tab]
            self._task_model.from_dict(active_tab_data.tasks)
            self._diagram_model.from_dict(active_tab_data.diagram)

            self._current_file_path = file_path
            self.currentFilePathChanged.emit()
            self._add_to_recent(file_path)
            self._last_saved_snapshot = self._serialize_project_payload(self._build_project_data())
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
        except CryptoError as e:
            error_msg = f"Failed to load project: {e}"
            self.errorOccurred.emit(error_msg)
            print(error_msg)

    @Slot(int)
    def drillToTask(self, task_index: int) -> None:
        """Focus a task in the current tab and notify UI to center on it."""
        if task_index < 0 or task_index >= self._task_model.rowCount():
            return

        focus_task = getattr(self._diagram_model, "focusTask", None)
        if callable(focus_task):
            focus_task(task_index)
        else:
            set_current_task = getattr(self._diagram_model, "setCurrentTask", None)
            if callable(set_current_task):
                set_current_task(task_index)

        self.taskDrillRequested.emit(task_index)

    @Slot(int, int)
    def openReminderTask(self, tab_index: int, task_index: int) -> None:
        """Open the tab and task targeted by a due reminder."""
        self.openTabTask(tab_index, task_index)

    @Slot(int, int)
    def openTabTask(self, tab_index: int, task_index: int) -> None:
        """Open a tab and focus a task index within that tab."""
        if self._tab_model is not None:
            if tab_index < 0 or tab_index >= self._tab_model.tabCount:
                return
            if self._tab_model.currentTabIndex != tab_index:
                self.switchTab(tab_index)
        self.drillToTask(task_index)

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

    @Slot(int, float, float, result=str)
    def addTabAsDrillTask(self, tab_index: int, x: float, y: float) -> str:
        """Create a task node titled after a tab so it can drill to that tab."""
        if self._tab_model is None:
            return ""
        if tab_index < 0 or tab_index >= self._tab_model.tabCount:
            return ""

        tabs = self._tab_model.getAllTabs()
        if tab_index >= len(tabs):
            return ""
        tab_name = str(tabs[tab_index].name or "").strip()
        if not tab_name:
            return ""

        add_task_from_text = getattr(self._diagram_model, "addTaskFromText", None)
        if not callable(add_task_from_text):
            return ""
        created_item_id = add_task_from_text(tab_name, x, y)
        return str(created_item_id or "")

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
