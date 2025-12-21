"""Tests for actiondraw.py with TDD approach.

Run tests with: pytest test_actiondraw.py -v
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtCore import QModelIndex, Qt, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from actiondraw import (
    DiagramModel,
    DiagramItem,
    DiagramEdge,
    DiagramItemType,
    create_actiondraw_window,
)
from progress_list import TaskModel, Task


@pytest.fixture
def app():
    """Create QGuiApplication instance for tests."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)
    yield instance


@pytest.fixture
def task_model(app):
    """Create a TaskModel instance with sample tasks."""
    model = TaskModel()
    model.addTask("Task 1", -1)
    model.addTask("Task 2", -1)
    model.addTask("Task 3", -1)
    return model


@pytest.fixture
def empty_diagram_model(app):
    """Create an empty DiagramModel."""
    return DiagramModel()


@pytest.fixture
def diagram_model_with_task_model(app, task_model):
    """Create a DiagramModel with TaskModel."""
    return DiagramModel(task_model=task_model)


class TestDiagramItem:
    """Tests for DiagramItem dataclass."""

    def test_diagram_item_creation_box(self):
        """Test creating a box diagram item."""
        item = DiagramItem(
            id="box_1",
            item_type=DiagramItemType.BOX,
            x=10.0,
            y=20.0,
            text="Test Box",
        )
        assert item.id == "box_1"
        assert item.item_type == DiagramItemType.BOX
        assert item.x == 10.0
        assert item.y == 20.0
        assert item.text == "Test Box"
        assert item.width == 120.0  # default
        assert item.height == 60.0  # default
        assert item.task_index == -1
        assert item.color == "#4a9eff"  # default

    def test_diagram_item_creation_task(self):
        """Test creating a task diagram item."""
        item = DiagramItem(
            id="task_1",
            item_type=DiagramItemType.TASK,
            x=50.0,
            y=100.0,
            text="Test Task",
            task_index=0,
            color="#82c3a5",
        )
        assert item.id == "task_1"
        assert item.item_type == DiagramItemType.TASK
        assert item.task_index == 0
        assert item.color == "#82c3a5"


class TestDiagramEdge:
    """Tests for DiagramEdge dataclass."""

    def test_diagram_edge_creation(self):
        """Test creating a diagram edge."""
        edge = DiagramEdge(id="edge_1", from_id="box_1", to_id="box_2")
        assert edge.id == "edge_1"
        assert edge.from_id == "box_1"
        assert edge.to_id == "box_2"


class TestDiagramModel:
    """Tests for DiagramModel class."""

    def test_diagram_model_creation_empty(self, empty_diagram_model):
        """Test creating an empty DiagramModel."""
        assert empty_diagram_model.rowCount() == 0
        assert len(empty_diagram_model.edges) == 0
        assert empty_diagram_model.count == 0

    def test_diagram_model_creation_with_task_model(self, diagram_model_with_task_model):
        """Test creating DiagramModel with TaskModel."""
        assert diagram_model_with_task_model.rowCount() == 0
        assert diagram_model_with_task_model._task_model is not None

    def test_add_box(self, empty_diagram_model):
        """Test adding a box to the diagram."""
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Test Box")
        assert item_id.startswith("box_")
        assert empty_diagram_model.rowCount() == 1
        assert empty_diagram_model.count == 1

        # Check the item data
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.IdRole) == item_id
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "box"
        assert empty_diagram_model.data(index, empty_diagram_model.XRole) == 10.0
        assert empty_diagram_model.data(index, empty_diagram_model.YRole) == 20.0
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Test Box"

    def test_add_box_empty_text(self, empty_diagram_model):
        """Test adding a box with empty text."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "")
        assert empty_diagram_model.rowCount() == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == ""

    def test_add_task(self, diagram_model_with_task_model):
        """Test adding a task from TaskModel to the diagram."""
        item_id = diagram_model_with_task_model.addTask(0, 50.0, 100.0)
        assert item_id.startswith("task_")
        assert diagram_model_with_task_model.rowCount() == 1

        # Check the item data
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskIndexRole) == 0
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.XRole) == 50.0
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.YRole) == 100.0

    def test_add_task_invalid_index(self, diagram_model_with_task_model):
        """Test adding a task with invalid index."""
        item_id = diagram_model_with_task_model.addTask(-1, 0.0, 0.0)
        assert item_id == ""

        item_id = diagram_model_with_task_model.addTask(100, 0.0, 0.0)
        assert item_id == ""

    def test_add_task_no_task_model(self, empty_diagram_model):
        """Test adding a task when no TaskModel is set."""
        item_id = empty_diagram_model.addTask(0, 0.0, 0.0)
        assert item_id == ""

    def test_move_item(self, empty_diagram_model):
        """Test moving an item."""
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Test")
        empty_diagram_model.moveItem(item_id, 100.0, 200.0)

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.XRole) == 100.0
        assert empty_diagram_model.data(index, empty_diagram_model.YRole) == 200.0

    def test_move_item_invalid_id(self, empty_diagram_model):
        """Test moving an item with invalid ID."""
        empty_diagram_model.addBox(10.0, 20.0, "Test")
        # Should not raise error, just do nothing
        empty_diagram_model.moveItem("invalid_id", 100.0, 200.0)

    def test_set_item_text(self, empty_diagram_model):
        """Test setting item text."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Original")
        empty_diagram_model.setItemText(item_id, "Updated")

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Updated"

    def test_set_item_text_invalid_id(self, empty_diagram_model):
        """Test setting text for invalid item ID."""
        empty_diagram_model.addBox(0.0, 0.0, "Test")
        # Should not raise error
        empty_diagram_model.setItemText("invalid_id", "Updated")

    def test_add_edge(self, empty_diagram_model):
        """Test adding an edge between two items."""
        box1_id = empty_diagram_model.addBox(0.0, 0.0, "Box 1")
        box2_id = empty_diagram_model.addBox(100.0, 100.0, "Box 2")

        empty_diagram_model.addEdge(box1_id, box2_id)
        assert len(empty_diagram_model.edges) == 1
        edge = empty_diagram_model.edges[0]
        assert edge["fromId"] == box1_id
        assert edge["toId"] == box2_id

    def test_add_edge_same_item(self, empty_diagram_model):
        """Test adding an edge from an item to itself (should be ignored)."""
        box_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.addEdge(box_id, box_id)
        assert len(empty_diagram_model.edges) == 0

    def test_add_edge_duplicate(self, empty_diagram_model):
        """Test adding duplicate edge (should be ignored)."""
        box1_id = empty_diagram_model.addBox(0.0, 0.0, "Box 1")
        box2_id = empty_diagram_model.addBox(100.0, 100.0, "Box 2")

        empty_diagram_model.addEdge(box1_id, box2_id)
        empty_diagram_model.addEdge(box1_id, box2_id)  # Duplicate
        assert len(empty_diagram_model.edges) == 1

    def test_remove_item(self, empty_diagram_model):
        """Test removing an item."""
        box1_id = empty_diagram_model.addBox(0.0, 0.0, "Box 1")
        box2_id = empty_diagram_model.addBox(100.0, 100.0, "Box 2")
        empty_diagram_model.addEdge(box1_id, box2_id)

        assert empty_diagram_model.rowCount() == 2
        assert len(empty_diagram_model.edges) == 1

        empty_diagram_model.removeItem(box1_id)

        assert empty_diagram_model.rowCount() == 1
        assert len(empty_diagram_model.edges) == 0  # Edge should be removed too

    def test_remove_item_invalid_id(self, empty_diagram_model):
        """Test removing an item with invalid ID."""
        empty_diagram_model.addBox(0.0, 0.0, "Box")
        # Should not raise error
        empty_diagram_model.removeItem("invalid_id")

    def test_start_edge_drawing(self, empty_diagram_model):
        """Test starting edge drawing."""
        box_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.startEdgeDrawing(box_id)
        assert empty_diagram_model.edgeDrawingFrom == box_id

    def test_finish_edge_drawing(self, empty_diagram_model):
        """Test finishing edge drawing."""
        box1_id = empty_diagram_model.addBox(0.0, 0.0, "Box 1")
        box2_id = empty_diagram_model.addBox(100.0, 100.0, "Box 2")

        empty_diagram_model.startEdgeDrawing(box1_id)
        empty_diagram_model.finishEdgeDrawing(box2_id)

        assert empty_diagram_model.edgeDrawingFrom == ""
        assert len(empty_diagram_model.edges) == 1

    def test_finish_edge_drawing_same_item(self, empty_diagram_model):
        """Test finishing edge drawing to the same item (should not create edge)."""
        box_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.startEdgeDrawing(box_id)
        empty_diagram_model.finishEdgeDrawing(box_id)

        assert len(empty_diagram_model.edges) == 0

    def test_cancel_edge_drawing(self, empty_diagram_model):
        """Test canceling edge drawing."""
        box_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.startEdgeDrawing(box_id)
        assert empty_diagram_model.edgeDrawingFrom == box_id

        empty_diagram_model.cancelEdgeDrawing()
        assert empty_diagram_model.edgeDrawingFrom == ""

    def test_create_task_from_text(self, diagram_model_with_task_model):
        """Test creating a task from text."""
        initial_task_count = diagram_model_with_task_model._task_model.rowCount()
        box_id = diagram_model_with_task_model.addBox(0.0, 0.0, "New Task")

        diagram_model_with_task_model.createTaskFromText("New Task", box_id)

        # Task should be added to TaskModel
        assert diagram_model_with_task_model._task_model.rowCount() == initial_task_count + 1

        # Box should be converted to task
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskIndexRole) == initial_task_count

    def test_create_task_from_text_no_task_model(self, empty_diagram_model):
        """Test creating task from text when no TaskModel is set."""
        box_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        # Should not raise error, just do nothing
        empty_diagram_model.createTaskFromText("New Task", box_id)

    def test_get_item(self, empty_diagram_model):
        """Test getting an item by ID."""
        box_id = empty_diagram_model.addBox(10.0, 20.0, "Test Box")
        item = empty_diagram_model.getItem(box_id)

        assert item is not None
        assert item.id == box_id
        assert item.text == "Test Box"

    def test_get_item_invalid_id(self, empty_diagram_model):
        """Test getting an item with invalid ID."""
        item = empty_diagram_model.getItem("invalid_id")
        assert item is None

    def test_get_item_at(self, empty_diagram_model):
        """Test getting item at coordinates."""
        box_id = empty_diagram_model.addBox(10.0, 20.0, "Test")
        # Item is 120x60, so center is at (70, 50)
        found_id = empty_diagram_model.getItemAt(70.0, 50.0)
        assert found_id == box_id

    def test_get_item_at_outside(self, empty_diagram_model):
        """Test getting item at coordinates outside any item."""
        empty_diagram_model.addBox(10.0, 20.0, "Test")
        found_id = empty_diagram_model.getItemAt(1000.0, 1000.0)
        assert found_id is None

    def test_get_item_at_multiple_items(self, empty_diagram_model):
        """Test getting item when multiple items overlap (should return topmost)."""
        box1_id = empty_diagram_model.addBox(0.0, 0.0, "Box 1")
        box2_id = empty_diagram_model.addBox(0.0, 0.0, "Box 2")  # Overlaps

        # Should return the last added item (topmost)
        found_id = empty_diagram_model.getItemAt(60.0, 30.0)
        assert found_id == box2_id

    def test_model_roles(self, empty_diagram_model):
        """Test that all model roles are properly defined."""
        roles = empty_diagram_model.roleNames()
        # roleNames() returns a dict mapping role integers to byte strings
        role_values = set(roles.values())
        assert b"itemId" in role_values
        assert b"itemType" in role_values
        assert b"x" in role_values
        assert b"y" in role_values
        assert b"width" in role_values
        assert b"height" in role_values
        assert b"text" in role_values
        assert b"taskIndex" in role_values
        assert b"color" in role_values

    def test_data_invalid_index(self, empty_diagram_model):
        """Test data() with invalid index."""
        result = empty_diagram_model.data(QModelIndex(), empty_diagram_model.IdRole)
        assert result is None

        invalid_index = empty_diagram_model.index(100, 0)
        result = empty_diagram_model.data(invalid_index, empty_diagram_model.IdRole)
        assert result is None


class TestDiagramModelIntegration:
    """Integration tests for DiagramModel with TaskModel."""

    def test_add_task_from_model(self, diagram_model_with_task_model):
        """Test adding a task from TaskModel and verifying it's linked."""
        # Add task to diagram
        item_id = diagram_model_with_task_model.addTask(0, 0.0, 0.0)

        # Verify task title matches
        index = diagram_model_with_task_model.index(0, 0)
        diagram_text = diagram_model_with_task_model.data(index, diagram_model_with_task_model.TextRole)

        task_index = diagram_model_with_task_model._task_model.index(0, 0)
        task_title = diagram_model_with_task_model._task_model.data(task_index, TaskModel.TitleRole)

        assert diagram_text == task_title

    def test_create_task_updates_both_models(self, diagram_model_with_task_model):
        """Test that creating a task updates both DiagramModel and TaskModel."""
        box_id = diagram_model_with_task_model.addBox(0.0, 0.0, "New Task Name")
        initial_count = diagram_model_with_task_model._task_model.rowCount()

        diagram_model_with_task_model.createTaskFromText("New Task Name", box_id)

        # TaskModel should have one more task
        assert diagram_model_with_task_model._task_model.rowCount() == initial_count + 1

        # DiagramModel item should be updated to task type
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskIndexRole) == initial_count


class TestActionDrawManager:
    """Tests for ActionDrawManager integration."""

    def test_actiondraw_manager_creation(self, app, task_model):
        """Test creating ActionDrawManager."""
        from progress_list import ActionDrawManager

        manager = ActionDrawManager(task_model)
        assert manager._task_model == task_model
        assert manager._diagram_model is not None
        assert manager._actiondraw_engine is None
        assert manager._actiondraw_window is None

    def test_show_actiondraw_creates_window(self, app, task_model):
        """Test that showActionDraw creates the window."""
        import progress_list
        
        manager = progress_list.ActionDrawManager(task_model)

        with patch('progress_list.create_actiondraw_window') as mock_create:
            mock_window = MagicMock()
            mock_engine = MagicMock()
            mock_engine.rootObjects.return_value = [mock_window]
            mock_create.return_value = mock_engine

            manager.showActionDraw()

            assert mock_create.called
            assert manager._actiondraw_engine == mock_engine
            assert manager._actiondraw_window == mock_window
            assert mock_window.showWindow.called

    def test_show_actiondraw_reuses_window(self, app, task_model):
        """Test that showActionDraw reuses existing window."""
        import progress_list
        
        manager = progress_list.ActionDrawManager(task_model)

        with patch('progress_list.create_actiondraw_window') as mock_create:
            mock_window = MagicMock()
            mock_engine = MagicMock()
            mock_engine.rootObjects.return_value = [mock_window]
            mock_create.return_value = mock_engine

            # First call
            manager.showActionDraw()
            assert mock_create.call_count == 1

            # Second call should reuse
            manager.showActionDraw()
            assert mock_create.call_count == 1  # Not called again
            assert mock_window.showWindow.call_count == 2


class TestCreateActionDrawWindow:
    """Tests for create_actiondraw_window function."""

    def test_create_actiondraw_window(self, app, diagram_model_with_task_model):
        """Test creating ActionDraw window."""
        engine = create_actiondraw_window(diagram_model_with_task_model, diagram_model_with_task_model._task_model)
        assert isinstance(engine, QQmlApplicationEngine)

        root_objects = engine.rootObjects()
        assert len(root_objects) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

