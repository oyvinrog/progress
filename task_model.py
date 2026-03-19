"""Shared task model for use across actiondraw and other modules.

This module provides the Task dataclass and TaskModel class that were
previously embedded in progress_list.py, making them available for
independent use by actiondraw.
"""

import copy
import json
import math
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
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
from PySide6.QtGui import QColor
from progress_crypto import (
    CryptoError,
    DerivedKeyMaterial,
    EncryptionCredentials,
    decrypt_and_derive_key_material,
    decrypt_project_data,
    derive_key_material,
    encrypt_project_data,
    encrypt_with_derived_key,
    has_yubikey_cli,
    is_encrypted_envelope,
    yubikey_support_guidance,
)
from actiondraw.priorityplot.model import (
    clamp_subjective_value,
    clamp_time_hours,
    compute_priority_score,
)


CRACK_MODEL_PROFILE_NAME = "Top-end GPU cluster"
CRACK_MODEL_ARGON2_GUESSES_PER_SECOND = 300_000_000.0
CRACK_MODEL_UNIVERSE_AGE_SECONDS = 13.8e9 * 365.25 * 24 * 60 * 60
CRACK_MODEL_COMMON_WORDS = (
    "password",
    "passphrase",
    "secret",
    "welcome",
    "qwerty",
    "letmein",
    "admin",
    "iloveyou",
    "dragon",
    "progress",
)
CRACK_MODEL_KDF_PARAMS_TEXT = "Argon2id t=3, m=65536, p=1"
DEFAULT_NTFY_SERVER = "https://ntfy.sh"


def _coalesce_ntfy_settings(
    server: Optional[str] = None,
    topic: Optional[str] = None,
    token: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Resolve ntfy settings from explicit values with environment fallback."""
    resolved_server = (server if server is not None else os.getenv("PROGRESS_NTFY_SERVER", DEFAULT_NTFY_SERVER)).strip()
    resolved_topic = (topic if topic is not None else os.getenv("PROGRESS_NTFY_TOPIC", "")).strip()
    resolved_token = (token if token is not None else os.getenv("PROGRESS_NTFY_TOKEN", "")).strip()
    if not resolved_server:
        resolved_server = DEFAULT_NTFY_SERVER
    return resolved_server, resolved_topic, resolved_token


def _send_ntfy_message(server: str, topic: str, title: str, message: str, token: str = "") -> None:
    """Send a single ntfy message using the HTTP publish API."""
    normalized_server = (server or DEFAULT_NTFY_SERVER).strip().rstrip("/")
    normalized_topic = (topic or "").strip().strip("/")
    if not normalized_topic:
        return

    url = f"{normalized_server}/{urllib.parse.quote(normalized_topic, safe='')}"
    data = message.encode("utf-8")
    headers = {
        "Title": title,
        "Tags": "alarm_clock",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=10):
        pass


def _publish_ntfy_message_async(
    title: str,
    message: str,
    server: Optional[str] = None,
    topic: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """Publish an ntfy message in a background thread when configured."""
    resolved_server, resolved_topic, resolved_token = _coalesce_ntfy_settings(server, topic, token)
    if not resolved_topic:
        return

    def _worker() -> None:
        try:
            _send_ntfy_message(resolved_server, resolved_topic, title, message, resolved_token)
        except (OSError, urllib.error.URLError, ValueError) as exc:
            print(f"Failed to publish ntfy reminder: {exc}", file=sys.stderr)

    threading.Thread(target=_worker, name="ntfy-reminder", daemon=True).start()


def _infer_charset_size(passphrase: str) -> int:
    """Infer the brute-force character pool from observed passphrase characters."""
    has_lower = any("a" <= ch <= "z" for ch in passphrase)
    has_upper = any("A" <= ch <= "Z" for ch in passphrase)
    has_digit = any(ch.isdigit() for ch in passphrase)
    has_space = any(ch.isspace() for ch in passphrase)
    has_symbol = any((not ch.isalnum()) and (not ch.isspace()) and ord(ch) <= 127 for ch in passphrase)
    has_non_ascii = any(ord(ch) > 127 for ch in passphrase)

    charset = 0
    if has_lower:
        charset += 26
    if has_upper:
        charset += 26
    if has_digit:
        charset += 10
    if has_symbol:
        charset += 33
    if has_space:
        charset += 1
    if has_non_ascii:
        # Use a broad bucket for non-ASCII scripts/symbols.
        charset += 2048
    return max(charset, 1)


def _estimate_bruteforce_guesses(passphrase: str) -> int:
    """Estimate brute-force search space C^L."""
    if not passphrase:
        return 0
    charset = _infer_charset_size(passphrase)
    return charset ** len(passphrase)


def _has_sequence_run(text: str) -> bool:
    if len(text) < 3:
        return False
    for i in range(len(text) - 2):
        a = ord(text[i])
        b = ord(text[i + 1])
        c = ord(text[i + 2])
        if (b - a == 1 and c - b == 1) or (b - a == -1 and c - b == -1):
            return True
    return False


def _estimate_human_effective_bits(passphrase: str) -> float:
    """Estimate effective entropy bits for user-chosen passphrases."""
    if not passphrase:
        return 0.0

    charset = _infer_charset_size(passphrase)
    base_bits = len(passphrase) * math.log2(charset)

    lower = passphrase.lower()
    penalties = 0.0

    if lower in CRACK_MODEL_COMMON_WORDS:
        penalties += 26.0

    for token in CRACK_MODEL_COMMON_WORDS:
        if token in lower:
            penalties += 8.0
            break

    if len(set(passphrase)) <= max(1, len(passphrase) // 4):
        penalties += 8.0

    if _has_sequence_run(lower):
        penalties += 6.0

    if len(passphrase) < 12:
        penalties += float(12 - len(passphrase)) * 1.5

    if passphrase.isdigit():
        penalties += 10.0
    elif passphrase.isalpha():
        penalties += 7.0

    year_like = any(str(year) in lower for year in range(1950, 2101))
    if year_like:
        penalties += 5.0

    effective_bits = max(4.0, min(base_bits, base_bits - penalties))
    return effective_bits


def _estimate_human_guesses(passphrase: str) -> float:
    """Convert effective entropy bits into an equivalent search-space size."""
    bits = _estimate_human_effective_bits(passphrase)
    if bits <= 0:
        return 0.0
    return 2.0 ** bits


def _estimate_crack_seconds(guesses: float, guesses_per_second: float) -> Tuple[float, float]:
    """Return (expected_seconds, worst_case_seconds)."""
    if guesses <= 0 or guesses_per_second <= 0:
        return (0.0, 0.0)
    worst = guesses / guesses_per_second
    return (worst / 2.0, worst)


def _format_duration_human(seconds: float) -> str:
    if not math.isfinite(seconds):
        return "not available"
    if seconds <= 1.0:
        return "less than a second"
    if seconds >= CRACK_MODEL_UNIVERSE_AGE_SECONDS:
        return "longer than the age of the universe"

    hour = 3600.0
    day = 24.0 * hour
    year = 365.25 * day

    def _fmt(value: float, digits: int = 1) -> str:
        if value >= 1000:
            return f"{value:,.0f}"
        rounded = round(value, digits)
        if float(rounded).is_integer():
            return str(int(rounded))
        return f"{rounded}"

    if seconds < 48 * hour:
        primary_value = seconds / hour
        primary = f"{_fmt(primary_value)} hours"
    elif seconds < 730 * day:
        primary_value = seconds / day
        primary = f"{_fmt(primary_value)} days"
    else:
        primary_value = seconds / year
        primary = f"{_fmt(primary_value)} years"

    days_value = seconds / day
    hours_value = seconds / hour
    years_value = seconds / year
    return (
        f"{primary} (~{_fmt(days_value)} days, "
        f"~{_fmt(hours_value)} hours, "
        f"~{_fmt(years_value, 2)} years)"
    )


def _build_passphrase_crack_time_report(passphrase: str, *, include_yubikey_note: bool = False) -> str:
    """Build a human-readable dual estimate from the current passphrase."""
    if not passphrase:
        return "Enter a passphrase to see a crack-time estimate."

    brute_guesses = float(_estimate_bruteforce_guesses(passphrase))
    human_guesses = _estimate_human_guesses(passphrase)
    brute_expected, brute_worst = _estimate_crack_seconds(
        brute_guesses,
        CRACK_MODEL_ARGON2_GUESSES_PER_SECOND,
    )
    human_expected, human_worst = _estimate_crack_seconds(
        human_guesses,
        CRACK_MODEL_ARGON2_GUESSES_PER_SECOND,
    )

    lines = [
        f"Model: {CRACK_MODEL_PROFILE_NAME}, {CRACK_MODEL_KDF_PARAMS_TEXT}.",
        "Assumes offline attack against Argon2id-derived key material.",
        (
            "Brute-force (charset^length): "
            f"Expected {_format_duration_human(brute_expected)}; "
            f"Worst-case {_format_duration_human(brute_worst)}."
        ),
        (
            "Human-pattern adjusted: "
            f"Expected {_format_duration_human(human_expected)}; "
            f"Worst-case {_format_duration_human(human_worst)}."
        ),
    ]
    if include_yubikey_note:
        lines.append("Note: Passphrase+YubiKey mode also requires YubiKey-derived secret material.")
    return "\n".join(lines)


def _validate_passphrase_confirmation(passphrase: str, confirmation: str) -> Tuple[bool, str]:
    """Validate passphrase + confirmation fields for save operations."""
    if not passphrase:
        return False, "Passphrase cannot be empty."
    if not confirmation:
        return False, "Confirm your passphrase."
    if passphrase != confirmation:
        return False, "Passphrases do not match."
    return True, "Passphrases match."


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
    reminder_send_notification: bool = False  # whether to publish to ntfy when due
    contract_deadline_at: Optional[float] = None  # local timestamp when contract deadline is due
    contract_punishment: str = ""  # user-defined punishment text
    contract_breached: bool = False  # whether deadline has passed before completion
    contract_breach_notified: bool = False  # whether breach alert has been emitted


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
    icon: str = ""
    color: str = ""
    pinned: bool = False


@dataclass
class NavigationSnapshot:
    """Represents a restorable drill-navigation context."""
    tab_index: int
    task_index: int = -1


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
    ContractActiveRole = Qt.UserRole + 15
    ContractDeadlineRole = Qt.UserRole + 16
    ContractRemainingRole = Qt.UserRole + 17
    ContractBreachedRole = Qt.UserRole + 18
    ContractPunishmentRole = Qt.UserRole + 19

    avgTimeChanged = Signal()
    totalEstimateChanged = Signal()
    taskCountChanged = Signal()
    taskRenamed = Signal(int, str, arguments=['taskIndex', 'newTitle'])
    taskCompletionChanged = Signal(int, bool, arguments=['taskIndex', 'completed'])
    taskCountdownChanged = Signal(int, arguments=['taskIndex'])
    taskReminderChanged = Signal(int, arguments=['taskIndex'])
    taskReminderDue = Signal(int, str, arguments=['taskIndex', 'taskTitle'])
    taskContractChanged = Signal(int, arguments=['taskIndex'])
    taskContractBreached = Signal(
        int,
        str,
        str,
        str,
        arguments=['taskIndex', 'taskTitle', 'punishment', 'deadlineText'],
    )

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
        elif role == self.ContractActiveRole:
            return self._isContractActive(task)
        elif role == self.ContractDeadlineRole:
            return self._formatContractDeadline(task)
        elif role == self.ContractRemainingRole:
            return self._getContractRemaining(task)
        elif role == self.ContractBreachedRole:
            return self._isContractBreached(task)
        elif role == self.ContractPunishmentRole:
            return self._getContractPunishment(task)
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
            self.ContractActiveRole: b"contractActive",
            self.ContractDeadlineRole: b"contractDeadline",
            self.ContractRemainingRole: b"contractRemaining",
            self.ContractBreachedRole: b"contractBreached",
            self.ContractPunishmentRole: b"contractPunishment",
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

    def _getReminderNotificationEnabled(self, task: Task) -> bool:
        """Return whether the reminder should send an ntfy notification when due."""
        return bool(task.reminder_send_notification)

    def _isContractActive(self, task: Task) -> bool:
        """Return True when a task has an active contract."""
        return (
            not task.completed
            and task.contract_deadline_at is not None
            and bool(task.contract_punishment.strip())
        )

    def _formatContractDeadline(self, task: Task) -> str:
        """Return contract deadline as local datetime string."""
        if not self._isContractActive(task):
            return ""
        return datetime.fromtimestamp(task.contract_deadline_at).strftime("%Y-%m-%d %H:%M")

    def _getContractRemaining(self, task: Task) -> float:
        """Return seconds until deadline, or -1 if no active contract."""
        if not self._isContractActive(task):
            return -1.0
        return float(task.contract_deadline_at - time.time())

    def _isContractBreached(self, task: Task) -> bool:
        """Return True if task contract is breached."""
        if not self._isContractActive(task):
            return False
        return bool(task.contract_breached)

    def _getContractPunishment(self, task: Task) -> str:
        """Return punishment text for an active contract."""
        if not self._isContractActive(task):
            return ""
        return str(task.contract_punishment)

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
    @Slot(int, str, bool, result=bool)
    def setReminderAt(self, row: int, reminder_at_str: str, send_notification: bool = False) -> bool:
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
        task.reminder_send_notification = bool(send_notification)

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
        self.taskReminderChanged.emit(row)
        return True

    @Slot(int, str, str, result=bool)
    def setContractAt(self, row: int, contract_deadline_str: str, punishment: str) -> bool:
        """Set a task contract with absolute local deadline and punishment."""
        if row < 0 or row >= len(self._tasks):
            return False

        punishment_text = punishment.strip()
        if not punishment_text:
            return False

        contract_deadline_at = self._parseReminderDateTime(contract_deadline_str)
        if contract_deadline_at is None:
            return False
        if contract_deadline_at <= time.time():
            return False

        task = self._tasks[row]
        task.contract_deadline_at = contract_deadline_at
        task.contract_punishment = punishment_text
        task.contract_breached = False
        task.contract_breach_notified = False

        idx = self.index(row, 0)
        self.dataChanged.emit(
            idx,
            idx,
            [
                self.ContractActiveRole,
                self.ContractDeadlineRole,
                self.ContractRemainingRole,
                self.ContractBreachedRole,
                self.ContractPunishmentRole,
            ],
        )
        self.taskContractChanged.emit(row)
        return True

    @Slot(int)
    def clearReminderAt(self, row: int) -> None:
        """Clear a task reminder."""
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        if task.reminder_at is None and not task.reminder_send_notification:
            return
        task.reminder_at = None
        task.reminder_send_notification = False

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
        self.taskReminderChanged.emit(row)

    def isReminderNotificationEnabled(self, row: int) -> bool:
        """Return whether the given task reminder should publish to ntfy."""
        if row < 0 or row >= len(self._tasks):
            return False
        return self._getReminderNotificationEnabled(self._tasks[row])

    @Slot(int)
    def clearContract(self, row: int) -> None:
        """Clear a task contract."""
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        had_contract = self._isContractActive(task) or task.contract_deadline_at is not None
        if not had_contract:
            return

        task.contract_deadline_at = None
        task.contract_punishment = ""
        task.contract_breached = False
        task.contract_breach_notified = False

        idx = self.index(row, 0)
        self.dataChanged.emit(
            idx,
            idx,
            [
                self.ContractActiveRole,
                self.ContractDeadlineRole,
                self.ContractRemainingRole,
                self.ContractBreachedRole,
                self.ContractPunishmentRole,
            ],
        )
        self.taskContractChanged.emit(row)

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
        contract_task_indices = []
        due_contracts: List[Tuple[int, str, str, str]] = []

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

            if self._isContractActive(task):
                contract_task_indices.append(i)
                if task.contract_deadline_at <= current_time and not task.contract_breached:
                    task.contract_breached = True
                if task.contract_breached and not task.contract_breach_notified:
                    due_contracts.append(
                        (
                            i,
                            task.title,
                            task.contract_punishment,
                            datetime.fromtimestamp(task.contract_deadline_at).strftime("%Y-%m-%d %H:%M"),
                        )
                    )

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

        for i in contract_task_indices:
            idx = self.index(i, 0)
            self.dataChanged.emit(
                idx,
                idx,
                [
                    self.ContractActiveRole,
                    self.ContractDeadlineRole,
                    self.ContractRemainingRole,
                    self.ContractBreachedRole,
                    self.ContractPunishmentRole,
                ],
            )
            self.taskContractChanged.emit(i)

        for i, task_title in due_reminders:
            task = self._tasks[i]
            task.reminder_at = None
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [self.ReminderActiveRole, self.ReminderAtRole])
            self.taskReminderChanged.emit(i)
            self.taskReminderDue.emit(i, task_title)
            task.reminder_send_notification = False

        for i, task_title, punishment, deadline_text in due_contracts:
            task = self._tasks[i]
            task.contract_breach_notified = True
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [self.ContractBreachedRole])
            self.taskContractChanged.emit(i)
            self.taskContractBreached.emit(i, task_title, punishment, deadline_text)

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
        had_active_contract = self._isContractActive(task)
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
            task.contract_deadline_at = None
            task.contract_punishment = ""
            task.contract_breached = False
            task.contract_breach_notified = False
        else:
            # Restart timing
            task.start_time = time.time()

        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        self.taskCompletionChanged.emit(row, completed)
        if completed and had_active_reminder:
            self.taskReminderChanged.emit(row)
        if completed and had_active_contract:
            self.taskContractChanged.emit(row)
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
            if task.reminder_send_notification:
                task_dict["reminder_send_notification"] = True
        if task.contract_deadline_at is not None:
            task_dict["contract_deadline_at"] = task.contract_deadline_at
            task_dict["contract_punishment"] = task.contract_punishment
            task_dict["contract_breached"] = task.contract_breached
            task_dict["contract_breach_notified"] = task.contract_breach_notified
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
                        reminder_send_notification=task_data.get("reminder_send_notification", False),
                        contract_deadline_at=task_data.get("contract_deadline_at"),
                        contract_punishment=task_data.get("contract_punishment", ""),
                        contract_breached=task_data.get("contract_breached", False),
                        contract_breach_notified=task_data.get("contract_breach_notified", False),
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
    IconRole = Qt.UserRole + 10
    ColorRole = Qt.UserRole + 11
    PinnedRole = Qt.UserRole + 12

    tabsChanged = Signal()
    currentTabChanged = Signal()
    currentTabIndexChanged = Signal()
    recentTabsChanged = Signal()

    def __init__(self):
        super().__init__()
        self._tabs: List[Tab] = [Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": []})]
        self._current_tab_index: int = 0
        self._recent_tab_indices: List[int] = []

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
        if role == self.IconRole:
            return tab.icon
        if role == self.ColorRole:
            return tab.color
        if role == self.PinnedRole:
            return tab.pinned
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
            self.IconRole: b"icon",
            self.ColorRole: b"color",
            self.PinnedRole: b"pinned",
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

    @Property("QVariantList", notify=recentTabsChanged)
    def recentTabIndices(self) -> List[int]:
        return list(self._recent_tab_indices)

    def _emitRecentTabsChanged(self) -> None:
        self.recentTabsChanged.emit()

    def _setRecentTabIndices(self, indices: List[int]) -> None:
        normalized: List[int] = []
        for index in indices:
            if not isinstance(index, int):
                continue
            if index < 0 or index >= len(self._tabs):
                continue
            if index == self._current_tab_index or index in normalized:
                continue
            normalized.append(index)
            if len(normalized) >= 5:
                break
        if normalized == self._recent_tab_indices:
            return
        self._recent_tab_indices = normalized
        self._emitRecentTabsChanged()

    def _recordRecentTab(self, index: int) -> None:
        if index < 0 or index >= len(self._tabs):
            return
        merged = [index]
        for recent_index in self._recent_tab_indices:
            if recent_index != index:
                merged.append(recent_index)
        self._setRecentTabIndices(merged)

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

    @Slot(result="QVariantList")
    def getPinnedTabIndices(self) -> List[int]:
        """Return pinned tab indices in their current manual order."""
        return [index for index, tab in enumerate(self._tabs) if bool(getattr(tab, "pinned", False))]

    @Slot(int, result="QVariantMap")
    def getTabSummary(self, index: int) -> Dict[str, Any]:
        """Return a QML-friendly summary for one tab."""
        if index < 0 or index >= len(self._tabs):
            return {}
        tab = self._tabs[index]
        return {
            "tabIndex": index,
            "name": tab.name,
            "completionPercent": self._calculateTabCompletion(tab),
            "activeTaskTitle": self._getActiveTaskTitle(tab),
            "priorityScore": tab.priority_score,
            "includeInPriorityPlot": tab.include_in_priority_plot,
            "icon": tab.icon,
            "color": tab.color,
            "pinned": tab.pinned,
        }

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
        self._emitRecentTabsChanged()

    @Slot(int)
    def removeTab(self, index: int) -> None:
        """Remove a tab at the given index. Cannot remove last tab."""
        if len(self._tabs) <= 1:
            return  # Cannot remove last tab
        if index < 0 or index >= len(self._tabs):
            return

        previous_current_index = self._current_tab_index
        self.beginRemoveRows(QModelIndex(), index, index)
        self._tabs.pop(index)
        self.endRemoveRows()

        # Adjust current tab index if needed
        if self._current_tab_index >= len(self._tabs):
            self._current_tab_index = len(self._tabs) - 1
            self.currentTabIndexChanged.emit()
        elif self._current_tab_index > index:
            self._current_tab_index -= 1
            self.currentTabIndexChanged.emit()
        elif self._current_tab_index == index:
            self._current_tab_index = min(index, len(self._tabs) - 1)
            self.currentTabIndexChanged.emit()

        if self._current_tab_index != previous_current_index or index == previous_current_index:
            self.currentTabChanged.emit()

        self.tabsChanged.emit()
        updated_recent_indices: List[int] = []
        for recent_index in self._recent_tab_indices:
            if recent_index == index:
                continue
            if recent_index > index:
                updated_recent_indices.append(recent_index - 1)
            else:
                updated_recent_indices.append(recent_index)
        self._setRecentTabIndices(updated_recent_indices)

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

    def _normalizeTabColor(self, color: str) -> str:
        color_text = str(color or "").strip()
        if not color_text:
            return ""
        parsed_color = QColor(color_text)
        if not parsed_color.isValid():
            return ""
        return parsed_color.name(QColor.HexRgb)

    @Slot(int, str)
    def setTabIcon(self, index: int, icon: str) -> None:
        """Set a tab icon glyph/text."""
        if index < 0 or index >= len(self._tabs):
            return
        normalized = str(icon or "").strip()
        if self._tabs[index].icon == normalized:
            return
        self._tabs[index].icon = normalized
        model_index = self.index(index, 0)
        self.dataChanged.emit(model_index, model_index, [self.IconRole])

    @Slot(int, str)
    def setTabColor(self, index: int, color: str) -> None:
        """Set a tab accent color using any valid Qt color string."""
        if index < 0 or index >= len(self._tabs):
            return
        normalized = self._normalizeTabColor(color)
        if self._tabs[index].color == normalized:
            return
        self._tabs[index].color = normalized
        model_index = self.index(index, 0)
        self.dataChanged.emit(model_index, model_index, [self.ColorRole])

    @Slot(int, bool)
    def setTabPinned(self, index: int, pinned: bool) -> None:
        """Persist whether a tab should appear in the pinned quick-access section."""
        if index < 0 or index >= len(self._tabs):
            return
        normalized = bool(pinned)
        if self._tabs[index].pinned == normalized:
            return
        self._tabs[index].pinned = normalized
        model_index = self.index(index, 0)
        self.dataChanged.emit(model_index, model_index, [self.PinnedRole])

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
        recent_tabs = [
            self._tabs[index]
            for index in self._recent_tab_indices
            if 0 <= index < len(self._tabs)
        ]
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
        self._setRecentTabIndices([
            self._tabs.index(tab)
            for tab in recent_tabs
            if tab in self._tabs
        ])
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

        previous_index = self._current_tab_index
        self._current_tab_index = index
        self.currentTabIndexChanged.emit()
        self.currentTabChanged.emit()
        self._recordRecentTab(previous_index)

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
            tab.icon = str(getattr(tab, "icon", "") or "").strip()
            tab.color = self._normalizeTabColor(getattr(tab, "color", ""))
            tab.pinned = bool(getattr(tab, "pinned", False))
        self.endResetModel()

        # Validate and set active tab index
        if active_tab < 0 or active_tab >= len(self._tabs):
            active_tab = 0
        self._current_tab_index = active_tab
        self._recent_tab_indices = []

        self.tabsChanged.emit()
        self.currentTabIndexChanged.emit()
        self.currentTabChanged.emit()
        self._emitRecentTabsChanged()

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

        updated_recent_indices: List[int] = []
        for recent_index in self._recent_tab_indices:
            if recent_index == from_index:
                updated_recent_indices.append(to_index)
            elif from_index < recent_index <= to_index:
                updated_recent_indices.append(recent_index - 1)
            elif to_index <= recent_index < from_index:
                updated_recent_indices.append(recent_index + 1)
            else:
                updated_recent_indices.append(recent_index)
        self._setRecentTabIndices(updated_recent_indices)


class ProjectManager(QObject):
    """Manager for saving and loading project files.

    Project files are JSON files containing:
    - v1.0: Task list data and diagram data (single tab)
    - v1.1: Multiple tabs, each with its own tasks and diagram data
    """

    PROJECT_VERSION = "1.1"
    ENCRYPTED_PROJECT_VERSION = "1.2"
    MAX_RECENT_PROJECTS = 8

    saveCompleted = Signal(str)  # Emitted with file path after successful save
    loadCompleted = Signal(str)  # Emitted with file path after successful load
    errorOccurred = Signal(str)  # Emitted with error message on failure
    recentProjectsChanged = Signal()  # Emitted when recent projects list changes
    currentFilePathChanged = Signal()  # Emitted when current file path changes
    sidebarExpandedChanged = Signal()
    ntfySettingsChanged = Signal()
    canGoBackChanged = Signal()
    tabSwitched = Signal()  # Emitted when switching to a different tab
    taskDrillRequested = Signal(int, arguments=["taskIndex"])
    taskReminderDue = Signal(int, int, str, arguments=["tabIndex", "taskIndex", "taskTitle"])
    taskContractBreached = Signal(
        int,
        int,
        str,
        str,
        str,
        arguments=["tabIndex", "taskIndex", "taskTitle", "punishment", "deadlineText"],
    )
    yubiKeyInteractionStarted = Signal(str, arguments=["message"])
    yubiKeyInteractionFinished = Signal()

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
        self._navigation_back_stack: List[NavigationSnapshot] = []
        self._restoring_navigation = False
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._checkBackgroundTabReminders)
        self._reminder_timer.start(1000)
        self._task_model.taskReminderDue.connect(self._onCurrentTabReminderDue)
        self._task_model.taskContractBreached.connect(self._onCurrentTabContractBreached)
        if self._tab_model is not None:
            self._task_model.taskCompletionChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskCountChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskRenamed.connect(self._refreshCurrentTabTasks)
            self._task_model.taskReminderChanged.connect(self._refreshCurrentTabTasks)
            self._task_model.taskContractChanged.connect(self._refreshCurrentTabTasks)
            self._tab_model.rowsRemoved.connect(self._clearNavigationHistory)
            self._tab_model.rowsMoved.connect(self._clearNavigationHistory)
            self._tab_model.modelReset.connect(self._clearNavigationHistory)
            # Connect diagram model's currentTaskChanged to update tab sidebar
            if hasattr(self._diagram_model, 'currentTaskChanged'):
                self._diagram_model.currentTaskChanged.connect(self._refreshCurrentTabDiagram)
        self._cached_key_material: Optional[DerivedKeyMaterial] = None
        self._cached_encryption_file_path: str = ""
        self._last_saved_snapshot = self._serialize_project_payload(self._build_project_data())

    @Property(bool, notify=canGoBackChanged)
    def canGoBack(self) -> bool:
        """Return whether drill-navigation history is available."""
        return bool(self._navigation_back_stack)

    def _emitCanGoBackChanged(self, was_enabled: bool) -> None:
        if was_enabled != bool(self._navigation_back_stack):
            self.canGoBackChanged.emit()

    def _currentNavigationSnapshot(self) -> NavigationSnapshot:
        tab_index = self._tab_model.currentTabIndex if self._tab_model is not None else 0
        task_index = -1
        current_task_index = getattr(self._diagram_model, "currentTaskIndex", -1)
        if isinstance(current_task_index, int) and current_task_index >= 0:
            task_index = current_task_index
        return NavigationSnapshot(tab_index=tab_index, task_index=task_index)

    def _pushNavigationSnapshot(self, snapshot: NavigationSnapshot) -> None:
        if self._restoring_navigation:
            return
        if self._navigation_back_stack and self._navigation_back_stack[-1] == snapshot:
            return
        was_enabled = bool(self._navigation_back_stack)
        self._navigation_back_stack.append(snapshot)
        self._emitCanGoBackChanged(was_enabled)

    def _clearNavigationHistory(self, *args) -> None:
        was_enabled = bool(self._navigation_back_stack)
        if not was_enabled:
            return
        self._navigation_back_stack.clear()
        self._emitCanGoBackChanged(was_enabled)

    def _shouldCaptureNavigation(self, destination_tab_index: int, destination_task_index: int = -1) -> bool:
        if self._tab_model is not None:
            if destination_tab_index < 0 or destination_tab_index >= self._tab_model.tabCount:
                return False
        current_snapshot = self._currentNavigationSnapshot()
        return (
            current_snapshot.tab_index != destination_tab_index
            or current_snapshot.task_index != destination_task_index
        )

    def _restoreNavigationSnapshot(self, snapshot: NavigationSnapshot) -> None:
        if self._tab_model is not None:
            if snapshot.tab_index < 0 or snapshot.tab_index >= self._tab_model.tabCount:
                return
            self.switchTab(snapshot.tab_index)

        focus_task = getattr(self._diagram_model, "focusTask", None)
        if (
            snapshot.task_index >= 0
            and callable(focus_task)
            and snapshot.task_index < self._task_model.rowCount()
        ):
            focus_task(snapshot.task_index)

    def _tabDisplayName(self, tab_index: int) -> str:
        """Return a stable human-readable name for a tab index."""
        if self._tab_model is None:
            return "Main"
        tabs = self._tab_model.getAllTabs()
        if 0 <= tab_index < len(tabs):
            name = str(getattr(tabs[tab_index], "name", "")).strip()
            if name:
                return name
        return "Main" if tab_index == 0 else f"Tab {tab_index + 1}"

    def _publishReminderNotification(self, tab_index: int, task_title: str) -> None:
        """Send an ntfy notification for a due reminder when configured."""
        title = task_title.strip() or "Task"
        tab_name = self._tabDisplayName(tab_index)
        message = f"Reminder due: {title}"
        if tab_name:
            message += f"\nTab: {tab_name}"
        _publish_ntfy_message_async(
            "ActionDraw Reminder",
            message,
            self.ntfyServer,
            self.ntfyTopic,
            self.ntfyToken,
        )

    def _onCurrentTabReminderDue(self, task_index: int, task_title: str) -> None:
        tab_index = self._tab_model.currentTabIndex if self._tab_model is not None else 0
        if self._task_model.isReminderNotificationEnabled(task_index):
            self._publishReminderNotification(tab_index, task_title)
        self.taskReminderDue.emit(tab_index, task_index, task_title)

    def _onCurrentTabContractBreached(
        self,
        task_index: int,
        task_title: str,
        punishment: str,
        deadline_text: str,
    ) -> None:
        tab_index = self._tab_model.currentTabIndex if self._tab_model is not None else 0
        self.taskContractBreached.emit(tab_index, task_index, task_title, punishment, deadline_text)

    def _checkBackgroundTabReminders(self) -> None:
        """Emit due reminders and contract breaches from non-active tabs."""
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
                    reminder_ts = None
                else:
                    try:
                        reminder_ts = float(reminder_at)
                    except (TypeError, ValueError):
                        reminder_ts = None

                if reminder_ts is not None and reminder_ts <= now:
                    task.pop("reminder_at", None)
                    send_notification = bool(task.pop("reminder_send_notification", False))
                    tab_changed = True
                    title = str(task.get("title", "")).strip() or "Task"
                    if send_notification:
                        self._publishReminderNotification(tab_index, title)
                    self.taskReminderDue.emit(tab_index, task_index, title)

                deadline_at = task.get("contract_deadline_at")
                punishment = str(task.get("contract_punishment", "")).strip()
                if deadline_at is None or not punishment:
                    continue

                try:
                    deadline_ts = float(deadline_at)
                except (TypeError, ValueError):
                    continue

                if task.get("completed", False):
                    continue

                if deadline_ts > now:
                    continue

                if bool(task.get("contract_breached", False)) and bool(task.get("contract_breach_notified", False)):
                    continue

                task["contract_breached"] = True
                task["contract_breach_notified"] = True
                tab_changed = True

                title = str(task.get("title", "")).strip() or "Task"
                deadline_text = datetime.fromtimestamp(deadline_ts).strftime("%Y-%m-%d %H:%M")
                self.taskContractBreached.emit(tab_index, task_index, title, punishment, deadline_text)

            if tab_changed:
                model_index = self._tab_model.index(tab_index, 0)
                self._tab_model.dataChanged.emit(
                    model_index,
                    model_index,
                    [self._tab_model.CompletionRole, self._tab_model.ActiveTaskTitleRole],
                )

    def _get_cross_tab_tasks(self, tab_index: int) -> Optional[List[Dict[str, Any]]]:
        """Return mutable task dictionaries for a tab, if available."""
        if self._tab_model is None:
            if tab_index != 0:
                return None
            payload = self._task_model.to_dict()
        else:
            if tab_index < 0 or tab_index >= self._tab_model.tabCount:
                return None
            if tab_index == self._tab_model.currentTabIndex:
                payload = self._task_model.to_dict()
            else:
                tab = self._tab_model.getAllTabs()[tab_index]
                payload = tab.tasks if isinstance(tab.tasks, dict) else {}

        if not isinstance(payload, dict):
            return None
        tasks = payload.get("tasks", [])
        if not isinstance(tasks, list):
            return None
        return tasks

    def _emit_tab_summary_changed(self, tab_index: int) -> None:
        """Notify listeners that summary data for a tab may have changed."""
        if self._tab_model is None:
            return
        model_index = self._tab_model.index(tab_index, 0)
        self._tab_model.dataChanged.emit(
            model_index,
            model_index,
            [self._tab_model.CompletionRole, self._tab_model.ActiveTaskTitleRole],
        )

    @Slot(result="QVariantList")
    def getActiveReminders(self) -> List[Dict[str, Any]]:
        """Return active reminders across all tabs sorted by soonest first."""
        now = time.time()
        reminders: List[Dict[str, Any]] = []

        if self._tab_model is None:
            tab_indices = [0]
            current_tab_index = 0
        else:
            tab_indices = list(range(self._tab_model.tabCount))
            current_tab_index = self._tab_model.currentTabIndex

        for tab_index in tab_indices:
            tasks = self._get_cross_tab_tasks(tab_index)
            if tasks is None:
                continue
            if self._tab_model is None:
                tab_name = "Main"
            else:
                tab = self._tab_model.getAllTabs()[tab_index]
                tab_name = getattr(tab, "name", "") or "Tab"

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
                if reminder_ts <= now:
                    continue
                title = str(task.get("title", "")).strip() or "Task"
                reminders.append(
                    {
                        "tabIndex": tab_index,
                        "tabName": tab_name,
                        "taskIndex": task_index,
                        "taskTitle": title,
                        "reminderAt": reminder_ts,
                        "reminderText": datetime.fromtimestamp(reminder_ts).strftime("%Y-%m-%d %H:%M"),
                        "isCurrentTab": tab_index == current_tab_index,
                    }
                )

        reminders.sort(key=lambda entry: float(entry.get("reminderAt", 0.0)))
        return reminders

    @Slot(result="QVariantList")
    def getActiveContracts(self) -> List[Dict[str, Any]]:
        """Return active contracts across all tabs with countdown/overdue metadata."""
        now = time.time()
        contracts: List[Dict[str, Any]] = []

        if self._tab_model is None:
            tasks = self._task_model.to_dict().get("tasks", [])
            for task_index, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                if task.get("completed", False):
                    continue
                deadline_at = task.get("contract_deadline_at")
                punishment = str(task.get("contract_punishment", "")).strip()
                if deadline_at is None or not punishment:
                    continue
                try:
                    deadline_ts = float(deadline_at)
                except (TypeError, ValueError):
                    continue
                title = str(task.get("title", "")).strip() or "Task"
                contracts.append(
                    {
                        "tabIndex": 0,
                        "tabName": "Main",
                        "taskIndex": task_index,
                        "taskTitle": title,
                        "deadlineText": datetime.fromtimestamp(deadline_ts).strftime("%Y-%m-%d %H:%M"),
                        "deadlineAt": deadline_ts,
                        "remainingSeconds": float(deadline_ts - now),
                        "breached": bool(task.get("contract_breached", False)) or deadline_ts <= now,
                        "punishment": punishment,
                    }
                )
            return contracts

        current_tab_index = self._tab_model.currentTabIndex
        for tab_index, tab in enumerate(self._tab_model.getAllTabs()):
            tab_tasks_payload = self._task_model.to_dict() if tab_index == current_tab_index else tab.tasks
            tasks = tab_tasks_payload.get("tasks", []) if isinstance(tab_tasks_payload, dict) else []
            if not isinstance(tasks, list):
                continue
            tab_name = getattr(tab, "name", "") or "Tab"
            for task_index, task in enumerate(tasks):
                if not isinstance(task, dict):
                    continue
                if task.get("completed", False):
                    continue
                deadline_at = task.get("contract_deadline_at")
                punishment = str(task.get("contract_punishment", "")).strip()
                if deadline_at is None or not punishment:
                    continue
                try:
                    deadline_ts = float(deadline_at)
                except (TypeError, ValueError):
                    continue
                title = str(task.get("title", "")).strip() or "Task"
                contracts.append(
                    {
                        "tabIndex": tab_index,
                        "tabName": tab_name,
                        "taskIndex": task_index,
                        "taskTitle": title,
                        "deadlineText": datetime.fromtimestamp(deadline_ts).strftime("%Y-%m-%d %H:%M"),
                        "deadlineAt": deadline_ts,
                        "remainingSeconds": float(deadline_ts - now),
                        "breached": bool(task.get("contract_breached", False)) or deadline_ts <= now,
                        "punishment": punishment,
                    }
                )

        contracts.sort(key=lambda entry: float(entry.get("deadlineAt", 0.0)))
        return contracts

    @Slot(int, int)
    def clearReminder(self, tab_index: int, task_index: int) -> None:
        """Clear a reminder in the current tab or a background tab."""
        tasks = self._get_cross_tab_tasks(tab_index)
        if tasks is None:
            return
        if task_index < 0 or task_index >= len(tasks):
            return
        task = tasks[task_index]
        if not isinstance(task, dict) or task.get("reminder_at") is None:
            return

        if self._tab_model is None or tab_index == self._tab_model.currentTabIndex:
            self._task_model.clearReminderAt(task_index)
            return

        task.pop("reminder_at", None)
        task.pop("reminder_send_notification", None)
        self._emit_tab_summary_changed(tab_index)

    def _string_setting(self, key: str, default: str = "") -> str:
        """Read a string setting from QSettings."""
        value = self._settings.value(key, default)
        if value is None:
            return default
        return str(value)

    @Property(str, notify=ntfySettingsChanged)
    def ntfyServer(self) -> str:
        """Return the configured ntfy server, or the default server."""
        stored = self._string_setting("notifications/ntfy_server", "").strip()
        return stored or DEFAULT_NTFY_SERVER

    @Property(str, notify=ntfySettingsChanged)
    def ntfyTopic(self) -> str:
        """Return the configured ntfy topic."""
        return self._string_setting("notifications/ntfy_topic", "").strip()

    @Property(str, notify=ntfySettingsChanged)
    def ntfyToken(self) -> str:
        """Return the configured ntfy bearer token."""
        return self._string_setting("notifications/ntfy_token", "")

    @Property(bool, notify=ntfySettingsChanged)
    def ntfyConfigured(self) -> bool:
        """Return whether reminder notifications are configured."""
        return bool(self.ntfyTopic.strip())

    @Slot(str, str, str)
    def saveNtfySettings(self, server: str, topic: str, token: str) -> None:
        """Persist ntfy settings used for reminder notifications."""
        normalized_server = (server or "").strip() or DEFAULT_NTFY_SERVER
        normalized_topic = (topic or "").strip()
        normalized_token = token or ""

        changed = (
            normalized_server != self.ntfyServer
            or normalized_topic != self.ntfyTopic
            or normalized_token != self.ntfyToken
        )
        if not changed:
            return

        self._settings.setValue("notifications/ntfy_server", normalized_server)
        self._settings.setValue("notifications/ntfy_topic", normalized_topic)
        self._settings.setValue("notifications/ntfy_token", normalized_token)
        self._settings.sync()
        self.ntfySettingsChanged.emit()

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
                    "icon": tab.icon,
                    "color": tab.color,
                    "pinned": tab.pinned,
                })

            return {
                "version": self.PROJECT_VERSION,
                "tabs": tabs_data,
                "active_tab": current_tab_index,
            }

        return {
            "version": self.PROJECT_VERSION,
            "tabs": [{
                "name": "Main",
                "tasks": self._task_model.to_dict(),
                "diagram": self._diagram_model.to_dict(),
            }],
            "active_tab": 0,
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
            if save_mode:
                entered = self._prompt_save_passphrase_with_confirmation(
                    title=title,
                    include_yubikey_note=require_yubikey,
                )
                if entered is None:
                    return None
                passphrase = entered
            else:
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

    def _prompt_save_passphrase_with_confirmation(
        self,
        *,
        title: str,
        include_yubikey_note: bool,
    ) -> Optional[str]:
        """Prompt for passphrase and confirmation with live crack-time estimate."""
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
            QPlainTextEdit,
            QSizePolicy,
            QVBoxLayout,
        )
        from PySide6.QtGui import QGuiApplication

        dialog = QDialog()
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setMinimumWidth(680)
        dialog.resize(680, 420)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)

        intro = QLabel(
            "Enter your passphrase twice. The estimate below is based on offline attacks "
            "against Argon2id-derived key material."
        )
        intro.setWordWrap(True)
        intro.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(intro)

        form = QFormLayout()
        passphrase_edit = QLineEdit()
        passphrase_edit.setObjectName("savePassphraseEdit")
        passphrase_edit.setEchoMode(QLineEdit.Password)
        confirm_edit = QLineEdit()
        confirm_edit.setObjectName("confirmPassphraseEdit")
        confirm_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Passphrase:", passphrase_edit)
        form.addRow("Confirm passphrase:", confirm_edit)
        layout.addLayout(form)

        status_label = QLabel("Passphrase cannot be empty.")
        status_label.setObjectName("passphraseStatusLabel")
        status_label.setStyleSheet("color: #d67f4b;")
        status_label.setWordWrap(True)
        status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(status_label)

        estimate_label = QPlainTextEdit()
        estimate_label.setObjectName("passphraseEstimateLabel")
        estimate_label.setReadOnly(True)
        estimate_label.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        estimate_label.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        estimate_label.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        estimate_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        estimate_label.setMinimumHeight(150)
        estimate_label.setMaximumHeight(340)
        estimate_label.setPlainText("Enter a passphrase to see a crack-time estimate.")
        layout.addWidget(estimate_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("savePassphraseOkButton")
        buttons.button(QDialogButtonBox.Cancel).setObjectName("savePassphraseCancelButton")
        layout.addWidget(buttons)

        min_height = 380
        max_height = 900
        screen = dialog.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            max_height = int(screen.availableGeometry().height() * 0.9)

        def _fit_dialog_height() -> None:
            layout.activate()
            target_height = max(min_height, layout.sizeHint().height() + 24)
            target_height = min(target_height, max_height)
            if dialog.height() != target_height:
                dialog.resize(dialog.width(), target_height)

        def _refresh() -> None:
            passphrase = passphrase_edit.text()
            confirmation = confirm_edit.text()
            valid, message = _validate_passphrase_confirmation(passphrase, confirmation)
            status_label.setText(message)
            status_label.setStyleSheet("color: #6dc37b;" if valid else "color: #d67f4b;")
            buttons.button(QDialogButtonBox.Ok).setEnabled(valid)
            estimate_label.setPlainText(
                _build_passphrase_crack_time_report(
                    passphrase,
                    include_yubikey_note=include_yubikey_note,
                )
            )
            _fit_dialog_height()

        passphrase_edit.textChanged.connect(_refresh)
        confirm_edit.textChanged.connect(_refresh)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        _refresh()
        if dialog.exec() != QDialog.Accepted:
            return None
        return passphrase_edit.text()

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

            if (
                not force_prompt
                and self._cached_key_material is not None
                and self._cached_encryption_file_path == file_path
            ):
                encrypted_payload = encrypt_with_derived_key(project_data, self._cached_key_material)
                encrypted_payload["version"] = self.ENCRYPTED_PROJECT_VERSION
            else:
                credentials = self._prompt_encryption_credentials("save", file_path)
                if credentials is None:
                    return False

                if credentials.use_yubikey:
                    self._begin_yubikey_interaction("save")
                try:
                    key_material = derive_key_material(credentials)
                    encrypted_payload = encrypt_with_derived_key(project_data, key_material)
                    encrypted_payload["version"] = self.ENCRYPTED_PROJECT_VERSION
                finally:
                    if credentials.use_yubikey:
                        self._end_yubikey_interaction()

                self._cached_key_material = key_material
                self._cached_encryption_file_path = file_path

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_payload, f, ensure_ascii=False, separators=(",", ":"))

            self._current_file_path = file_path
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
                    project_data, key_material = decrypt_and_derive_key_material(
                        project_data, credentials,
                    )
                finally:
                    if credentials.use_yubikey:
                        self._end_yubikey_interaction()
                self._cached_encryption_file_path = file_path
                self._cached_key_material = key_material

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
                        icon=tab_data.get("icon", ""),
                        color=tab_data.get("color", ""),
                        pinned=tab_data.get("pinned", False),
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
            self._clearNavigationHistory()
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
        if self._shouldCaptureNavigation(tab_index, task_index):
            self._pushNavigationSnapshot(self._currentNavigationSnapshot())
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

        if self._shouldCaptureNavigation(target_index):
            self._pushNavigationSnapshot(self._currentNavigationSnapshot())
        self.switchTab(target_index)

    @Slot()
    def goBack(self) -> None:
        """Restore the previous drill-navigation context."""
        if not self._navigation_back_stack:
            return

        while self._navigation_back_stack:
            was_enabled = bool(self._navigation_back_stack)
            snapshot = self._navigation_back_stack.pop()
            self._emitCanGoBackChanged(was_enabled)
            if self._tab_model is not None:
                if snapshot.tab_index < 0 or snapshot.tab_index >= self._tab_model.tabCount:
                    continue
            self._restoring_navigation = True
            try:
                self._restoreNavigationSnapshot(snapshot)
            finally:
                self._restoring_navigation = False
            return

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

    @Slot(int)
    def removeTab(self, index: int) -> None:
        """Remove a tab while keeping live models aligned with the surviving tab."""
        if self._tab_model is None:
            return
        if self._tab_model.tabCount <= 1:
            return
        if index < 0 or index >= self._tab_model.tabCount:
            return

        current_index = self._tab_model.currentTabIndex
        removing_current_tab = index == current_index

        if not removing_current_tab:
            self._saveCurrentTabState()

        self._tab_model.removeTab(index)

        if removing_current_tab:
            self.reloadCurrentTab()
        else:
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
