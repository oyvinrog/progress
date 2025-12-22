"""Tests for progress_list.py with coverage tracking."""

import sys
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication

from progress_list import Task, TaskModel


@pytest.fixture
def app():
    """Create QGuiApplication instance for tests."""
    # QGuiApplication is a singleton, only create if doesn't exist
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)
    yield instance


@pytest.fixture
def task_model(app):
    """Create a TaskModel instance."""
    return TaskModel()


@pytest.fixture
def task_model_with_tasks(app):
    """Create a TaskModel with sample tasks."""
    tasks = [
        Task(title="Task 1", time_spent=5.0, completed=True),
        Task(title="Task 2", time_spent=0.0, completed=False, start_time=time.time()),
        Task(title="Task 3", time_spent=0.0, completed=False, start_time=time.time()),
    ]
    return TaskModel(tasks)


class TestTask:
    """Tests for Task dataclass."""

    def test_task_creation(self):
        """Test creating a task with default values."""
        task = Task(title="Test Task")
        assert task.title == "Test Task"
        assert task.completed is False
        assert task.time_spent == 0.0
        assert task.start_time is None
        assert task.parent_index == -1
        assert task.indent_level == 0

    def test_task_with_custom_values(self):
        """Test creating a task with custom values."""
        task = Task(
            title="Custom Task",
            completed=True,
            time_spent=10.5,
            start_time=12345.0,
            parent_index=2,
            indent_level=1,
        )
        assert task.title == "Custom Task"
        assert task.completed is True
        assert task.time_spent == 10.5
        assert task.start_time == 12345.0
        assert task.parent_index == 2
        assert task.indent_level == 1


class TestTaskModel:
    """Tests for TaskModel."""

    def test_model_initialization(self, task_model):
        """Test model initializes empty."""
        assert task_model.rowCount() == 0
        assert len(task_model._tasks) == 0

    def test_model_with_initial_tasks(self, task_model_with_tasks):
        """Test model initializes with tasks."""
        assert task_model_with_tasks.rowCount() == 3

    def test_task_count_property_updates(self, task_model):
        """Task count property reflects list mutations."""
        assert task_model.taskCount == 0
        task_model.addTask("Task A")
        assert task_model.taskCount == 1
        task_model.addTask("Task B")
        assert task_model.taskCount == 2
        task_model.removeAt(0)
        assert task_model.taskCount == 1
        task_model.clear()
        assert task_model.taskCount == 0

    def test_role_names(self, task_model):
        """Test role names are correctly defined."""
        roles = task_model.roleNames()
        assert roles[TaskModel.TitleRole] == b"title"
        assert roles[TaskModel.CompletedRole] == b"completed"
        assert roles[TaskModel.TimeSpentRole] == b"timeSpent"
        assert roles[TaskModel.EstimatedTimeRole] == b"estimatedTime"
        assert roles[TaskModel.CompletionTimeRole] == b"completionTime"
        assert roles[TaskModel.IndentLevelRole] == b"indentLevel"

    def test_data_invalid_index(self, task_model_with_tasks):
        """Test data returns None for invalid index."""
        invalid_index = QModelIndex()
        assert task_model_with_tasks.data(invalid_index, TaskModel.TitleRole) is None

    def test_data_title_role(self, task_model_with_tasks):
        """Test retrieving title via data()."""
        index = task_model_with_tasks.index(0, 0)
        assert task_model_with_tasks.data(index, TaskModel.TitleRole) == "Task 1"

    def test_data_completed_role(self, task_model_with_tasks):
        """Test retrieving completed status via data()."""
        index = task_model_with_tasks.index(0, 0)
        assert task_model_with_tasks.data(index, TaskModel.CompletedRole) is True

        index2 = task_model_with_tasks.index(1, 0)
        assert task_model_with_tasks.data(index2, TaskModel.CompletedRole) is False

    def test_data_time_spent_role(self, task_model_with_tasks):
        """Test retrieving time spent via data()."""
        index = task_model_with_tasks.index(0, 0)
        assert task_model_with_tasks.data(index, TaskModel.TimeSpentRole) == 5.0

    def test_data_indent_level_role(self, task_model):
        """Test retrieving indent level via data()."""
        task_model.addTask("Parent")
        task_model.addTask("Child", 0)

        parent_index = task_model.index(0, 0)
        child_index = task_model.index(1, 0)

        assert task_model.data(parent_index, TaskModel.IndentLevelRole) == 0
        assert task_model.data(child_index, TaskModel.IndentLevelRole) == 1


class TestTaskModelOperations:
    """Tests for task operations."""

    def test_add_task(self, task_model):
        """Test adding a task."""
        task_model.addTask("New Task")
        assert task_model.rowCount() == 1
        assert task_model._tasks[0].title == "New Task"
        assert task_model._tasks[0].start_time is not None

    def test_add_empty_task(self, task_model):
        """Test adding empty task is ignored."""
        task_model.addTask("")
        task_model.addTask("   ")
        assert task_model.rowCount() == 0

    def test_add_subtask(self, task_model):
        """Test adding a subtask."""
        task_model.addTask("Parent Task")
        task_model.addSubtask(0)

        assert task_model.rowCount() == 2
        assert task_model._tasks[1].title == "Subtask"
        assert task_model._tasks[1].indent_level == 1

    def test_add_subtask_invalid_index(self, task_model):
        """Test adding subtask with invalid parent index."""
        task_model.addSubtask(-1)
        task_model.addSubtask(999)
        assert task_model.rowCount() == 0

    def test_toggle_complete(self, task_model_with_tasks):
        """Test toggling task completion."""
        # Complete an incomplete task
        task_model_with_tasks.toggleComplete(1, True)
        assert task_model_with_tasks._tasks[1].completed is True
        assert task_model_with_tasks._tasks[1].start_time is None

        # Uncomplete a completed task
        task_model_with_tasks.toggleComplete(1, False)
        assert task_model_with_tasks._tasks[1].completed is False
        assert task_model_with_tasks._tasks[1].start_time is not None

    def test_toggle_complete_invalid_index(self, task_model):
        """Test toggle complete with invalid index."""
        task_model.toggleComplete(-1, True)
        task_model.toggleComplete(999, True)
        # Should not crash

    def test_rename_task(self, task_model):
        """Test renaming a task."""
        task_model.addTask("Original Name")
        task_model.renameTask(0, "New Name")

        assert task_model._tasks[0].title == "New Name"

    def test_rename_task_empty(self, task_model):
        """Test renaming with empty string is ignored."""
        task_model.addTask("Original Name")
        task_model.renameTask(0, "")
        task_model.renameTask(0, "   ")

        assert task_model._tasks[0].title == "Original Name"

    def test_rename_task_invalid_index(self, task_model):
        """Test rename with invalid index."""
        task_model.renameTask(-1, "New Name")
        task_model.renameTask(999, "New Name")
        # Should not crash

    def test_move_task(self, task_model):
        """Test moving a task to a different position."""
        task_model.addTask("Task 1")
        task_model.addTask("Task 2")
        task_model.addTask("Task 3")

        # Move task 0 to position 2
        task_model.moveTask(0, 2)
        assert task_model._tasks[0].title == "Task 2"
        assert task_model._tasks[1].title == "Task 3"
        assert task_model._tasks[2].title == "Task 1"

    def test_move_task_invalid(self, task_model):
        """Test move with invalid indices."""
        task_model.addTask("Task 1")
        task_model.addTask("Task 2")

        # Same position
        task_model.moveTask(0, 0)
        assert task_model._tasks[0].title == "Task 1"

        # Out of bounds
        task_model.moveTask(-1, 1)
        task_model.moveTask(0, 999)
        task_model.moveTask(999, 0)
        # Should not crash

    def test_remove_task(self, task_model):
        """Test removing a task."""
        task_model.addTask("Task 1")
        task_model.addTask("Task 2")

        task_model.removeAt(0)
        assert task_model.rowCount() == 1
        assert task_model._tasks[0].title == "Task 2"

    def test_remove_task_with_children(self, task_model):
        """Test removing a task removes its children."""
        task_model.addTask("Parent")
        task_model.addSubtask(0)
        task_model.addSubtask(0)

        assert task_model.rowCount() == 3

        task_model.removeAt(0)
        assert task_model.rowCount() == 0

    def test_remove_task_invalid_index(self, task_model):
        """Test remove with invalid index."""
        task_model.removeAt(-1)
        task_model.removeAt(999)
        # Should not crash

    def test_clear(self, task_model_with_tasks):
        """Test clearing all tasks."""
        assert task_model_with_tasks.rowCount() == 3
        task_model_with_tasks.clear()
        assert task_model_with_tasks.rowCount() == 0

    def test_clear_empty_model(self, task_model):
        """Test clearing already empty model."""
        task_model.clear()
        assert task_model.rowCount() == 0

    def test_paste_sample_tasks(self, task_model):
        """Test pasting sample tasks."""
        task_model.pasteSampleTasks()
        assert task_model.rowCount() == 5
        assert task_model._tasks[0].title == "Review pull requests"


class TestTimeEstimation:
    """Tests for time estimation logic."""

    def test_average_task_time_no_completed(self, task_model):
        """Test average time with no completed tasks."""
        task_model.addTask("Task 1")
        assert task_model.averageTaskTime == 0.0

    def test_average_task_time_with_completed(self, task_model_with_tasks):
        """Test average time calculation."""
        # Only Task 1 is completed with 5.0 minutes
        assert task_model_with_tasks.averageTaskTime == 5.0

    def test_average_task_time_multiple_completed(self, task_model):
        """Test average with multiple completed tasks."""
        task_model._tasks = [
            Task(title="T1", completed=True, time_spent=10.0),
            Task(title="T2", completed=True, time_spent=20.0),
            Task(title="T3", completed=True, time_spent=30.0),
        ]
        assert task_model.averageTaskTime == 20.0

    def test_estimate_task_time_no_avg(self, task_model):
        """Test task time estimation with no average."""
        task_model.addTask("Task 1")
        assert task_model._estimateTaskTime(0) == 0.0

    def test_estimate_task_time_with_avg(self, task_model_with_tasks):
        """Test task time estimation uses average."""
        # Average is 5.0, so incomplete tasks should estimate 5.0
        assert task_model_with_tasks._estimateTaskTime(1) == 5.0
        assert task_model_with_tasks._estimateTaskTime(2) == 5.0

    def test_estimate_task_time_completed(self, task_model_with_tasks):
        """Test completed task returns actual time spent."""
        assert task_model_with_tasks._estimateTaskTime(0) == 5.0

    def test_estimate_completion_time(self, task_model_with_tasks):
        """Test completion time estimation."""
        # Task at index 1 is first incomplete with time_spent=0
        # Should show remaining time: 5.0 - 0.0 = 5.0
        result = task_model_with_tasks._estimateCompletionTime(1)
        assert result == 5.0

        # Task at index 2 is second incomplete
        # Should show: time_remaining_on_first (5.0) + avg_time (5.0) = 10.0
        result = task_model_with_tasks._estimateCompletionTime(2)
        assert result == 10.0

    def test_estimate_completion_time_completed(self, task_model_with_tasks):
        """Test completion time for completed task is 0."""
        assert task_model_with_tasks._estimateCompletionTime(0) == 0.0

    def test_total_estimated_time(self, task_model_with_tasks):
        """Test total estimated time calculation."""
        # Two incomplete tasks, each estimated at 5.0 minutes
        assert task_model_with_tasks.totalEstimatedTime == 10.0

    def test_total_estimated_time_no_tasks(self, task_model):
        """Test total estimated time with no tasks."""
        assert task_model.totalEstimatedTime == 0.0

    def test_realistic_scenario_user_reported(self, task_model):
        """Test the exact scenario reported by user.

        Scenario:
        - Task 1 'Write documentation': completed in 11 seconds (0.183 min)
        - Task 2 'Fix critical bug': in progress, spent 6 seconds (0.1 min)
        - Task 3 'Update dependencies': not started

        Expected:
        - Avg time: 0.183 min (11 sec)
        - Task 2 estimate: 0.183 min (11 sec)
        - Task 2 completion: 0.083 min (5 sec remaining)
        - Task 3 estimate: 0.183 min (11 sec)
        - Task 3 completion: 0.266 min (5 sec remaining + 11 sec = 16 sec)
        """
        # Setup tasks
        task_model._tasks = [
            Task(title="Write documentation", completed=True, time_spent=0.183),
            Task(title="Fix critical bug", completed=False, time_spent=0.1, start_time=time.time()),
            Task(title="Update dependencies", completed=False, time_spent=0.0, start_time=time.time()),
        ]

        # Test average
        avg = task_model.averageTaskTime
        assert abs(avg - 0.183) < 0.001

        # Test Task 2 estimate (should be avg, not current time_spent)
        task2_estimate = task_model._estimateTaskTime(1)
        assert abs(task2_estimate - 0.183) < 0.001, f"Task 2 estimate should be {0.183}, got {task2_estimate}"

        # Test Task 2 completion time (remaining time: avg - spent = 0.183 - 0.1 = 0.083)
        task2_completion = task_model._estimateCompletionTime(1)
        assert abs(task2_completion - 0.083) < 0.001, f"Task 2 completion should be {0.083}, got {task2_completion}"

        # Test Task 3 estimate (should be avg)
        task3_estimate = task_model._estimateTaskTime(2)
        assert abs(task3_estimate - 0.183) < 0.001, f"Task 3 estimate should be {0.183}, got {task3_estimate}"

        # Test Task 3 completion time (remaining on task2 + full task3 = 0.083 + 0.183 = 0.266)
        task3_completion = task_model._estimateCompletionTime(2)
        expected_task3_completion = 0.083 + 0.183
        assert abs(task3_completion - expected_task3_completion) < 0.001, \
            f"Task 3 completion should be {expected_task3_completion}, got {task3_completion}"

    def test_completion_time_with_in_progress_first_task(self, task_model):
        """Test completion time calculation when first task has progress."""
        task_model._tasks = [
            Task(title="T1", completed=False, time_spent=3.0, start_time=time.time()),  # 3 min spent, avg will be 10
            Task(title="T2", completed=False, time_spent=0.0, start_time=time.time()),
            Task(title="T3", completed=True, time_spent=10.0),
        ]

        avg = task_model.averageTaskTime
        assert avg == 10.0

        # Task 1 completion: 10 - 3 = 7 minutes remaining
        task1_completion = task_model._estimateCompletionTime(0)
        assert abs(task1_completion - 7.0) < 0.001

        # Task 2 completion: 7 (remaining on T1) + 10 (full T2) = 17
        task2_completion = task_model._estimateCompletionTime(1)
        assert abs(task2_completion - 17.0) < 0.001

    def test_simple_three_task_scenario(self, task_model):
        """Test exact user scenario: A done in 7s, B and C waiting.

        Expected:
        - A: completed in 7s (0.117 min)
        - B: first incomplete, should complete in ~7s from now
        - C: second incomplete, should complete in ~14s from now (7s for B + 7s for C)
        """
        task_model._tasks = [
            Task(title="A", completed=True, time_spent=0.117),  # 7 seconds
            Task(title="B", completed=False, time_spent=0.0, start_time=time.time()),
            Task(title="C", completed=False, time_spent=0.0, start_time=time.time()),
        ]

        avg = task_model.averageTaskTime
        assert abs(avg - 0.117) < 0.001, f"Avg should be 0.117, got {avg}"

        # B is first incomplete, should complete in avg time (7 seconds)
        b_completion = task_model._estimateCompletionTime(1)
        assert abs(b_completion - 0.117) < 0.001, f"B should complete in 0.117 min (7s), got {b_completion}"

        # C is second incomplete, should complete in 2 * avg time (14 seconds)
        c_completion = task_model._estimateCompletionTime(2)
        expected_c = 0.117 * 2  # 14 seconds
        assert abs(c_completion - expected_c) < 0.001, f"C should complete in {expected_c} min (14s), got {c_completion}"

    def test_custom_estimate_parsing(self, task_model):
        """Test parsing of custom estimate strings."""
        task_model.addTask("Task 1")
        task_model.addTask("Task 2")
        task_model.addTask("Task 3")

        # Test minutes format
        task_model.setCustomEstimate(0, "30m")
        assert task_model._tasks[0].custom_estimate == 30.0

        # Test hours format
        task_model.setCustomEstimate(1, "2h")
        assert task_model._tasks[1].custom_estimate == 120.0

        # Test decimal hours
        task_model.setCustomEstimate(2, "1.5h")
        assert task_model._tasks[2].custom_estimate == 90.0

    def test_custom_estimate_plain_number(self, task_model):
        """Test custom estimate with plain number (defaults to minutes)."""
        task_model.addTask("Task 1")
        task_model.setCustomEstimate(0, "45")
        assert task_model._tasks[0].custom_estimate == 45.0

    def test_custom_estimate_clear(self, task_model):
        """Test clearing custom estimate."""
        task_model.addTask("Task 1")
        task_model.setCustomEstimate(0, "30m")
        assert task_model._tasks[0].custom_estimate == 30.0

        # Clear estimate
        task_model.setCustomEstimate(0, "")
        assert task_model._tasks[0].custom_estimate is None

    def test_custom_estimate_affects_completion_time(self, task_model):
        """Test that custom estimates affect completion time calculations."""
        # Setup: A completed in 10 min, B with 30m custom estimate, C with default
        task_model._tasks = [
            Task(title="A", completed=True, time_spent=10.0),
            Task(title="B", completed=False, time_spent=0.0, start_time=time.time(), custom_estimate=30.0),
            Task(title="C", completed=False, time_spent=0.0, start_time=time.time()),
        ]

        # B should complete in 30 minutes (its custom estimate)
        b_completion = task_model._estimateCompletionTime(1)
        assert abs(b_completion - 30.0) < 0.001, f"B should complete in 30 min, got {b_completion}"

        # C should complete in 30 (B custom) + 10 (C uses avg) = 40 minutes
        c_completion = task_model._estimateCompletionTime(2)
        assert abs(c_completion - 40.0) < 0.001, f"C should complete in 40 min, got {c_completion}"

    def test_custom_estimate_invalid_format(self, task_model):
        """Test that invalid formats are ignored."""
        task_model.addTask("Task 1")
        task_model.setCustomEstimate(0, "invalid")
        assert task_model._tasks[0].custom_estimate is None

        task_model.setCustomEstimate(0, "abc123")
        assert task_model._tasks[0].custom_estimate is None


class TestUpdateActiveTasks:
    """Tests for active task time tracking."""

    def test_update_active_tasks(self, task_model_with_tasks):
        """Test that active tasks get time updated."""
        initial_time = task_model_with_tasks._tasks[1].time_spent

        # Simulate time passing
        time.sleep(0.1)
        task_model_with_tasks._updateActiveTasks()

        # Time should have increased slightly
        assert task_model_with_tasks._tasks[1].time_spent > initial_time

    def test_update_active_tasks_completed_ignored(self, task_model_with_tasks):
        """Test that completed tasks don't get updated."""
        initial_time = task_model_with_tasks._tasks[0].time_spent

        task_model_with_tasks._updateActiveTasks()

        # Completed task time should not change
        assert task_model_with_tasks._tasks[0].time_spent == initial_time

    def test_update_active_tasks_no_start_time(self, task_model):
        """Test update with task that has no start time."""
        task_model._tasks = [Task(title="Test", completed=False, start_time=None)]
        task_model._updateActiveTasks()
        # Should not crash


class TestSignals:
    """Tests for Qt signals."""

    def test_avg_time_changed_signal(self, task_model, qtbot):
        """Test avgTimeChanged signal is emitted."""
        with qtbot.waitSignal(task_model.avgTimeChanged, timeout=1000):
            task_model.addTask("Task 1")
            task_model.toggleComplete(0, True)

    def test_total_estimate_changed_signal(self, task_model, qtbot):
        """Test totalEstimateChanged signal is emitted."""
        task_model.addTask("Task 1")
        with qtbot.waitSignal(task_model.totalEstimateChanged, timeout=1000):
            task_model.toggleComplete(0, True)

    def test_data_changed_signal(self, task_model, qtbot):
        """Test dataChanged signal is emitted."""
        task_model.addTask("Task 1")
        with qtbot.waitSignal(task_model.dataChanged, timeout=1000):
            task_model.renameTask(0, "New Name")


class TestGetTasksFunction:
    """Tests for the get_tasks() function."""

    @patch('progress_list.QApplication')
    @patch('progress_list.QQmlApplicationEngine')
    def test_get_tasks_empty(self, mock_engine_class, mock_app_class):
        """Test get_tasks with no tasks."""
        from progress_list import get_tasks

        mock_app = Mock()
        mock_engine = Mock()
        mock_app_class.return_value = mock_app
        mock_engine_class.return_value = mock_engine
        mock_engine.rootObjects.return_value = [Mock()]
        mock_app.exec.return_value = 0

        # Mock the model to have no tasks
        with patch('progress_list.TaskModel') as mock_model_class:
            mock_model = Mock()
            mock_model._tasks = []
            mock_model_class.return_value = mock_model

            result = get_tasks()
            assert result == []

    @patch('progress_list.QApplication')
    @patch('progress_list.QQmlApplicationEngine')
    def test_get_tasks_with_tasks(self, mock_engine_class, mock_app_class):
        """Test get_tasks returns task list."""
        from progress_list import get_tasks

        mock_app = Mock()
        mock_engine = Mock()
        mock_app_class.return_value = mock_app
        mock_engine_class.return_value = mock_engine
        mock_engine.rootObjects.return_value = [Mock()]
        mock_app.exec.return_value = 0

        # Mock the model with tasks
        with patch('progress_list.TaskModel') as mock_model_class:
            mock_model = Mock()
            mock_model._tasks = [
                Task(title="Task 1", completed=True, time_spent=5.0),
                Task(title="Task 2", completed=False, time_spent=2.0),
            ]
            mock_model_class.return_value = mock_model

            result = get_tasks()
            assert len(result) == 2
            assert result[0].title == "Task 1"
            assert result[1].title == "Task 2"

    @patch('progress_list.QApplication')
    @patch('progress_list.QQmlApplicationEngine')
    def test_get_tasks_no_root_objects(self, mock_engine_class, mock_app_class):
        """Test get_tasks when engine fails to load."""
        from progress_list import get_tasks

        mock_app = Mock()
        mock_engine = Mock()
        mock_app_class.return_value = mock_app
        mock_engine_class.return_value = mock_engine
        mock_engine.rootObjects.return_value = []

        result = get_tasks()
        assert result == []


class TestMainFunction:
    """Tests for the main() function."""

    @patch('progress_list.QApplication')
    @patch('progress_list.QQmlApplicationEngine')
    def test_main_success(self, mock_engine_class, mock_app_class):
        """Test main function successful execution."""
        from progress_list import main

        mock_app = Mock()
        mock_engine = Mock()
        mock_app_class.return_value = mock_app
        mock_engine_class.return_value = mock_engine
        mock_engine.rootObjects.return_value = [Mock()]
        mock_app.exec.return_value = 0

        result = main()
        assert result == 0

    @patch('progress_list.QApplication')
    @patch('progress_list.QQmlApplicationEngine')
    def test_main_failure(self, mock_engine_class, mock_app_class):
        """Test main function when engine fails."""
        from progress_list import main

        mock_app = Mock()
        mock_engine = Mock()
        mock_app_class.return_value = mock_app
        mock_engine_class.return_value = mock_engine
        mock_engine.rootObjects.return_value = []

        result = main()
        assert result == 1


class TestTaskModelSerialization:
    """Tests for TaskModel serialization (to_dict/from_dict)."""

    def test_to_dict_empty(self, task_model):
        """Test serialization of empty task model."""
        data = task_model.to_dict()
        assert "tasks" in data
        assert data["tasks"] == []

    def test_to_dict_with_tasks(self, task_model):
        """Test serialization with tasks."""
        task_model.addTask("Task 1")
        task_model.addTask("Task 2")
        task_model.toggleComplete(0, True)

        data = task_model.to_dict()
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["title"] == "Task 1"
        assert data["tasks"][0]["completed"] is True
        assert data["tasks"][1]["title"] == "Task 2"
        assert data["tasks"][1]["completed"] is False

    def test_to_dict_preserves_custom_estimate(self, task_model):
        """Test serialization preserves custom estimates."""
        task_model.addTask("Task with estimate")
        task_model.setCustomEstimate(0, "30m")

        data = task_model.to_dict()
        assert data["tasks"][0]["custom_estimate"] == 30.0

    def test_to_dict_preserves_indent_level(self, task_model):
        """Test serialization preserves indent levels."""
        task_model.addTask("Parent Task")
        task_model.addSubtask(0)

        data = task_model.to_dict()
        assert data["tasks"][0]["indent_level"] == 0
        assert data["tasks"][1]["indent_level"] == 1

    def test_from_dict_empty(self, task_model):
        """Test loading empty data."""
        task_model.addTask("Existing task")
        assert task_model.rowCount() == 1

        task_model.from_dict({"tasks": []})
        assert task_model.rowCount() == 0

    def test_from_dict_with_tasks(self, task_model):
        """Test loading tasks from dict."""
        data = {
            "tasks": [
                {"title": "Loaded Task 1", "completed": False, "time_spent": 0.0,
                 "parent_index": -1, "indent_level": 0, "custom_estimate": None},
                {"title": "Loaded Task 2", "completed": True, "time_spent": 15.5,
                 "parent_index": -1, "indent_level": 0, "custom_estimate": 30.0},
            ]
        }
        task_model.from_dict(data)

        assert task_model.rowCount() == 2
        assert task_model._tasks[0].title == "Loaded Task 1"
        assert task_model._tasks[0].completed is False
        assert task_model._tasks[1].title == "Loaded Task 2"
        assert task_model._tasks[1].completed is True
        assert task_model._tasks[1].time_spent == 15.5
        assert task_model._tasks[1].custom_estimate == 30.0

    def test_from_dict_clears_existing(self, task_model):
        """Test that from_dict clears existing tasks."""
        task_model.addTask("Old Task 1")
        task_model.addTask("Old Task 2")
        assert task_model.rowCount() == 2

        data = {"tasks": [{"title": "New Task", "completed": False, "time_spent": 0.0,
                          "parent_index": -1, "indent_level": 0, "custom_estimate": None}]}
        task_model.from_dict(data)

        assert task_model.rowCount() == 1
        assert task_model._tasks[0].title == "New Task"

    def test_roundtrip_serialization(self, task_model):
        """Test that data survives serialization round-trip."""
        task_model.addTask("Task A")
        task_model.addTask("Task B")
        task_model.toggleComplete(0, True)
        task_model.setCustomEstimate(1, "45m")
        task_model.addSubtask(1)

        # Serialize
        data = task_model.to_dict()

        # Create new model and deserialize
        new_model = TaskModel()
        new_model.from_dict(data)

        assert new_model.rowCount() == 3
        assert new_model._tasks[0].title == "Task A"
        assert new_model._tasks[0].completed is True
        assert new_model._tasks[1].title == "Task B"
        assert new_model._tasks[1].custom_estimate == 45.0
        assert new_model._tasks[2].indent_level == 1


class TestProjectManager:
    """Tests for ProjectManager save/load functionality."""

    @pytest.fixture
    def project_manager(self, task_model):
        """Create a ProjectManager instance."""
        from progress_list import ActionDrawManager, ProjectManager
        actiondraw_manager = ActionDrawManager(task_model)
        return ProjectManager(task_model, actiondraw_manager)

    def test_save_and_load_project(self, project_manager, task_model, tmp_path):
        """Test saving and loading a project file."""
        # Add some tasks
        task_model.addTask("Test Task 1")
        task_model.addTask("Test Task 2")
        task_model.toggleComplete(0, True)

        # Save project
        file_path = str(tmp_path / "test_project.progress")
        project_manager.saveProject(file_path)

        # Verify file was created
        import os
        assert os.path.exists(file_path)

        # Clear tasks
        task_model.clear()
        assert task_model.rowCount() == 0

        # Load project
        project_manager.loadProject(file_path)

        # Verify tasks were restored
        assert task_model.rowCount() == 2
        assert task_model._tasks[0].title == "Test Task 1"
        assert task_model._tasks[0].completed is True
        assert task_model._tasks[1].title == "Test Task 2"

    def test_save_adds_extension(self, project_manager, task_model, tmp_path):
        """Test that .progress extension is added if missing."""
        file_path = str(tmp_path / "test_project")  # No extension
        project_manager.saveProject(file_path)

        import os
        assert os.path.exists(file_path + ".progress")

    def test_save_with_file_url(self, project_manager, task_model, tmp_path):
        """Test saving with file:// URL prefix."""
        file_path = str(tmp_path / "test_project.progress")
        project_manager.saveProject(f"file://{file_path}")

        import os
        assert os.path.exists(file_path)

    def test_load_with_file_url(self, project_manager, task_model, tmp_path):
        """Test loading with file:// URL prefix."""
        task_model.addTask("URL Test Task")
        file_path = str(tmp_path / "test_project.progress")
        project_manager.saveProject(file_path)

        task_model.clear()
        project_manager.loadProject(f"file://{file_path}")

        assert task_model.rowCount() == 1
        assert task_model._tasks[0].title == "URL Test Task"

    def test_load_nonexistent_file(self, project_manager, task_model, tmp_path):
        """Test loading a file that doesn't exist."""
        error_received = []
        project_manager.errorOccurred.connect(lambda msg: error_received.append(msg))

        project_manager.loadProject(str(tmp_path / "nonexistent.progress"))

        assert len(error_received) == 1
        assert "not found" in error_received[0].lower()

    def test_load_invalid_json(self, project_manager, task_model, tmp_path):
        """Test loading an invalid JSON file."""
        file_path = tmp_path / "invalid.progress"
        file_path.write_text("{ invalid json }")

        error_received = []
        project_manager.errorOccurred.connect(lambda msg: error_received.append(msg))

        project_manager.loadProject(str(file_path))

        assert len(error_received) == 1
        assert "invalid" in error_received[0].lower() or "format" in error_received[0].lower()

    def test_save_empty_path(self, project_manager, task_model):
        """Test saving with empty path."""
        error_received = []
        project_manager.errorOccurred.connect(lambda msg: error_received.append(msg))

        project_manager.saveProject("")

        assert len(error_received) == 1

    def test_project_file_format(self, project_manager, task_model, tmp_path):
        """Test that saved file has correct format."""
        import json

        task_model.addTask("Format Test")
        file_path = str(tmp_path / "format_test.progress")
        project_manager.saveProject(file_path)

        with open(file_path, "r") as f:
            data = json.load(f)

        assert "version" in data
        assert "saved_at" in data
        assert "tasks" in data
        assert "diagram" in data

    def test_signals_on_save(self, project_manager, task_model, tmp_path):
        """Test that saveCompleted signal is emitted."""
        completed_received = []
        project_manager.saveCompleted.connect(lambda path: completed_received.append(path))

        file_path = str(tmp_path / "signal_test.progress")
        project_manager.saveProject(file_path)

        assert len(completed_received) == 1
        assert file_path in completed_received[0]

    def test_signals_on_load(self, project_manager, task_model, tmp_path):
        """Test that loadCompleted signal is emitted."""
        task_model.addTask("Signal Test")
        file_path = str(tmp_path / "signal_test.progress")
        project_manager.saveProject(file_path)

        completed_received = []
        project_manager.loadCompleted.connect(lambda path: completed_received.append(path))

        project_manager.loadProject(file_path)

        assert len(completed_received) == 1
        assert file_path in completed_received[0]

    def test_current_file_path_updated(self, project_manager, task_model, tmp_path):
        """Test that currentFilePath is updated after save/load."""
        file_path = str(tmp_path / "path_test.progress")

        assert project_manager.currentFilePath == ""

        task_model.addTask("Path Test")
        project_manager.saveProject(file_path)

        assert file_path in project_manager.currentFilePath

        task_model.clear()
        project_manager.loadProject(file_path)

        assert file_path in project_manager.currentFilePath
