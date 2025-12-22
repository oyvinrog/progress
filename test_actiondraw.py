"""Tests for the rewritten actiondraw module."""

import sys
import pytest
from PySide6.QtCore import QModelIndex
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from actiondraw import (
    DiagramEdge,
    DiagramItem,
    DiagramItemType,
    DiagramModel,
    create_actiondraw_window,
)
from progress_list import TaskModel


@pytest.fixture(scope="session")
def app():
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)
    return instance


@pytest.fixture
def task_model(app):
    model = TaskModel()
    model.addTask("Task 1", -1)
    model.addTask("Task 2", -1)
    model.addTask("Task 3", -1)
    return model


@pytest.fixture
def empty_diagram_model(app):
    return DiagramModel()


@pytest.fixture
def diagram_model_with_task_model(app, task_model):
    return DiagramModel(task_model=task_model)


class TestDataClasses:
    def test_diagram_item_defaults(self):
        item = DiagramItem(id="box_1", item_type=DiagramItemType.BOX, x=10.0, y=20.0)
        assert item.width == 120.0
        assert item.height == 60.0
        assert item.task_index == -1
        assert item.color == "#4a9eff"

    def test_diagram_edge(self):
        edge = DiagramEdge(id="edge_1", from_id="a", to_id="b")
        assert edge.id == "edge_1"
        assert edge.from_id == "a"
        assert edge.to_id == "b"


class TestDiagramModelBasics:
    def test_empty_model(self, empty_diagram_model):
        assert empty_diagram_model.rowCount() == 0
        assert empty_diagram_model.count == 0
        assert empty_diagram_model.edges == []

    def test_add_box(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Box")
        assert item_id.startswith("box_")
        assert empty_diagram_model.count == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Box"
        assert empty_diagram_model.data(index, empty_diagram_model.XRole) == 10.0
        assert empty_diagram_model.data(index, empty_diagram_model.YRole) == 20.0

    def test_add_preset_item(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItem("database", 50.0, 75.0)
        assert item_id.startswith("database_")
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "database"
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Database"
        assert empty_diagram_model.data(index, empty_diagram_model.ColorRole) == "#c18f5e"
        assert empty_diagram_model.data(index, empty_diagram_model.TextColorRole) == "#1b2028"

        custom_id = empty_diagram_model.addPresetItemWithText("note", 10.0, 20.0, "Release Plan")
        assert custom_id.startswith("note_")
        index = empty_diagram_model.index(1, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "note"
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Release Plan"
        assert empty_diagram_model.data(index, empty_diagram_model.TextColorRole) == "#1b2028"

    def test_add_task(self, diagram_model_with_task_model):
        item_id = diagram_model_with_task_model.addTask(0, 50.0, 100.0)
        assert item_id.startswith("task_")
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskIndexRole) == 0

    def test_add_task_invalid_index(self, diagram_model_with_task_model):
        assert diagram_model_with_task_model.addTask(-1, 0.0, 0.0) == ""
        assert diagram_model_with_task_model.addTask(99, 0.0, 0.0) == ""

    def test_add_task_without_model(self, empty_diagram_model):
        assert empty_diagram_model.addTask(0, 0.0, 0.0) == ""

    def test_move_item(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.moveItem(item_id, 100.0, 200.0)
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.XRole) == 100.0
        assert empty_diagram_model.data(index, empty_diagram_model.YRole) == 200.0

    def test_move_item_invalid(self, empty_diagram_model):
        empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.moveItem("does_not_exist", 10.0, 10.0)

    def test_set_item_text(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Old")
        empty_diagram_model.setItemText(item_id, "New")
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "New"

    def test_set_item_text_invalid(self, empty_diagram_model):
        empty_diagram_model.addBox(0.0, 0.0, "Old")
        empty_diagram_model.setItemText("missing", "New")

    def test_resize_item(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        empty_diagram_model.resizeItem(item_id, 200.0, 120.0)
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.WidthRole) == 200.0
        assert empty_diagram_model.data(index, empty_diagram_model.HeightRole) == 120.0


class TestEdges:
    def test_add_edge(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        assert len(empty_diagram_model.edges) == 1
        assert empty_diagram_model.edges[0]["fromId"] == a
        assert empty_diagram_model.edges[0]["toId"] == b

    def test_add_edge_same_item(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.addEdge(a, a)
        assert empty_diagram_model.edges == []

    def test_add_edge_duplicate(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.addEdge(a, b)
        assert len(empty_diagram_model.edges) == 1

    def test_remove_item_clears_edges(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.removeItem(a)
        assert empty_diagram_model.count == 1
        assert empty_diagram_model.edges == []

    def test_remove_item_invalid(self, empty_diagram_model):
        empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.removeItem("missing")

    def test_edge_drag_state(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.startEdgeDrawing(a)
        assert empty_diagram_model.edgeDrawingFrom == a
        empty_diagram_model.updateEdgeDragPosition(100.0, 120.0)
        assert empty_diagram_model.isDraggingEdge is True
        assert empty_diagram_model.edgeDragX == 100.0
        assert empty_diagram_model.edgeDragY == 120.0
        empty_diagram_model.finishEdgeDrawing(a)
        assert empty_diagram_model.edgeDrawingFrom == ""
        assert empty_diagram_model.isDraggingEdge is False

    def test_cancel_edge_drawing(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.startEdgeDrawing(a)
        empty_diagram_model.cancelEdgeDrawing()
        assert empty_diagram_model.edgeDrawingFrom == ""

    def test_remove_edge(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        assert len(empty_diagram_model.edges) == 1
        edge_id = empty_diagram_model.edges[0]["id"]
        empty_diagram_model.removeEdge(edge_id)
        assert empty_diagram_model.edges == []

    def test_remove_edge_invalid(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.removeEdge("nonexistent_edge")
        assert len(empty_diagram_model.edges) == 1

    def test_remove_edge_between(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        c = empty_diagram_model.addBox(100.0, 100.0, "C")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.addEdge(b, c)
        assert len(empty_diagram_model.edges) == 2
        empty_diagram_model.removeEdgeBetween(a, b)
        assert len(empty_diagram_model.edges) == 1
        assert empty_diagram_model.edges[0]["fromId"] == b
        assert empty_diagram_model.edges[0]["toId"] == c

    def test_remove_edge_between_invalid(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 50.0, "B")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.removeEdgeBetween(b, a)  # Wrong direction
        assert len(empty_diagram_model.edges) == 1


class TestQueries:
    def test_get_item(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Box")
        item = empty_diagram_model.getItem(item_id)
        assert item is not None
        assert item.id == item_id

    def test_get_item_missing(self, empty_diagram_model):
        assert empty_diagram_model.getItem("missing") is None

    def test_get_item_at(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Box")
        assert empty_diagram_model.getItemAt(50.0, 40.0) == item_id

    def test_get_item_at_outside(self, empty_diagram_model):
        empty_diagram_model.addBox(0.0, 0.0, "Box")
        assert empty_diagram_model.getItemAt(1000.0, 1000.0) is None

    def test_item_id_at_slot(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Box")
        assert empty_diagram_model.itemIdAt(20.0, 20.0) == item_id
        assert empty_diagram_model.itemIdAt(500.0, 500.0) == ""

    def test_role_names(self, empty_diagram_model):
        roles = empty_diagram_model.roleNames()
        assert roles[empty_diagram_model.IdRole] == b"itemId"
        assert roles[empty_diagram_model.TextRole] == b"text"
        assert roles[empty_diagram_model.ColorRole] == b"color"
        assert roles[empty_diagram_model.TextColorRole] == b"textColor"

    def test_data_invalid_index(self, empty_diagram_model):
        assert empty_diagram_model.data(empty_diagram_model.index(10, 0), empty_diagram_model.IdRole) is None
        assert empty_diagram_model.data(QModelIndex(), empty_diagram_model.IdRole) is None


class TestTaskIntegration:
    def test_create_task_from_text(self, diagram_model_with_task_model):
        box_id = diagram_model_with_task_model.addBox(0.0, 0.0, "Temp")
        original_count = diagram_model_with_task_model._task_model.rowCount()
        diagram_model_with_task_model.createTaskFromText("New Task", box_id)
        assert diagram_model_with_task_model._task_model.rowCount() == original_count + 1
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"

    def test_add_task_from_text(self, diagram_model_with_task_model):
        original_task_count = diagram_model_with_task_model._task_model.rowCount()
        item_id = diagram_model_with_task_model.addTaskFromText("Freetext Task", 100.0, 200.0)
        assert item_id.startswith("task_")
        assert diagram_model_with_task_model._task_model.rowCount() == original_task_count + 1
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TypeRole) == "task"
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TextRole) == "Freetext Task"

    def test_add_task_from_text_empty_string(self, diagram_model_with_task_model):
        original_count = diagram_model_with_task_model._task_model.rowCount()
        item_id = diagram_model_with_task_model.addTaskFromText("   ", 0.0, 0.0)
        assert item_id == ""
        assert diagram_model_with_task_model._task_model.rowCount() == original_count

    def test_add_task_from_text_no_task_model(self, empty_diagram_model):
        item_id = empty_diagram_model.addTaskFromText("Should Fail", 0.0, 0.0)
        assert item_id == ""

    def test_add_task_uses_title(self, diagram_model_with_task_model):
        item_id = diagram_model_with_task_model.addTask(1, 25.0, 35.0)
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TextRole) == diagram_model_with_task_model._task_model.data(
            diagram_model_with_task_model._task_model.index(1, 0),
            diagram_model_with_task_model._task_model.TitleRole,
        )
        assert item_id


class TestBidirectionalRename:
    """Test bidirectional name syncing between diagram and task list."""

    def test_rename_task_item_syncs_to_task_model(self, diagram_model_with_task_model):
        """Renaming a task in the diagram should update the task list."""
        task_model = diagram_model_with_task_model._task_model
        # Add a task from the task list to the diagram
        item_id = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        
        # Rename via diagram
        diagram_model_with_task_model.renameTaskItem(item_id, "Renamed Task")
        
        # Check diagram item was updated
        item = diagram_model_with_task_model.getItem(item_id)
        assert item.text == "Renamed Task"
        
        # Check task model was updated
        task_title = task_model.data(task_model.index(0, 0), task_model.TitleRole)
        assert task_title == "Renamed Task"

    def test_rename_in_task_model_syncs_to_diagram(self, diagram_model_with_task_model):
        """Renaming a task in the task list should update the diagram."""
        task_model = diagram_model_with_task_model._task_model
        # Add a task from the task list to the diagram
        item_id = diagram_model_with_task_model.addTask(1, 100.0, 100.0)
        
        # Get original name
        item = diagram_model_with_task_model.getItem(item_id)
        assert item.text == "Task 2"
        
        # Rename via task model
        task_model.renameTask(1, "Updated From List")
        
        # Check diagram item was updated
        item = diagram_model_with_task_model.getItem(item_id)
        assert item.text == "Updated From List"

    def test_rename_task_item_no_task_index(self, empty_diagram_model):
        """Renaming a non-task item should only update the diagram."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Original")
        empty_diagram_model.renameTaskItem(item_id, "Updated")
        item = empty_diagram_model.getItem(item_id)
        assert item.text == "Updated"

    def test_rename_task_item_empty_text(self, diagram_model_with_task_model):
        """Empty text should be ignored."""
        item_id = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        original_text = diagram_model_with_task_model.getItem(item_id).text
        
        diagram_model_with_task_model.renameTaskItem(item_id, "  ")
        
        item = diagram_model_with_task_model.getItem(item_id)
        assert item.text == original_text

    def test_rename_task_item_same_text(self, diagram_model_with_task_model):
        """Same text should be ignored (no unnecessary updates)."""
        task_model = diagram_model_with_task_model._task_model
        item_id = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        original_text = diagram_model_with_task_model.getItem(item_id).text
        
        # This should not trigger any updates
        diagram_model_with_task_model.renameTaskItem(item_id, original_text)
        
        item = diagram_model_with_task_model.getItem(item_id)
        assert item.text == original_text

    def test_rename_task_item_invalid_id(self, diagram_model_with_task_model):
        """Invalid item ID should be handled gracefully."""
        # Should not raise
        diagram_model_with_task_model.renameTaskItem("invalid_id", "New Name")

    def test_on_task_renamed_updates_multiple_items(self, diagram_model_with_task_model):
        """Multiple diagram items pointing to the same task should all update."""
        task_model = diagram_model_with_task_model._task_model
        # Add the same task twice to the diagram
        item_id1 = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        item_id2 = diagram_model_with_task_model.addTask(0, 200.0, 200.0)
        
        # Rename via task model
        task_model.renameTask(0, "Shared Update")
        
        # Both items should be updated
        assert diagram_model_with_task_model.getItem(item_id1).text == "Shared Update"
        assert diagram_model_with_task_model.getItem(item_id2).text == "Shared Update"


class TestConnectAll:
    def test_connect_all_orders_by_position(self, empty_diagram_model):
        a = empty_diagram_model.addBox(100.0, 100.0, "A")
        b = empty_diagram_model.addBox(0.0, 0.0, "B")
        c = empty_diagram_model.addBox(50.0, 50.0, "C")
        empty_diagram_model.connectAllItems()
        assert len(empty_diagram_model.edges) == 2
        assert empty_diagram_model.edges[0]["fromId"] == b
        assert empty_diagram_model.edges[0]["toId"] == c
        assert empty_diagram_model.edges[1]["fromId"] == c
        assert empty_diagram_model.edges[1]["toId"] == a

    def test_connect_all_handles_existing_edges(self, empty_diagram_model):
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(50.0, 0.0, "B")
        c = empty_diagram_model.addBox(100.0, 0.0, "C")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.connectAllItems()
        assert len(empty_diagram_model.edges) == 2

    def test_connect_all_ignores_small_sets(self, empty_diagram_model):
        empty_diagram_model.connectAllItems()
        assert empty_diagram_model.edges == []
        empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.connectAllItems()
        assert empty_diagram_model.edges == []


class TestCreateActionDrawWindow:
    def test_create_window(self, app, diagram_model_with_task_model):
        engine = create_actiondraw_window(diagram_model_with_task_model, diagram_model_with_task_model._task_model)
        assert isinstance(engine, QQmlApplicationEngine)
        assert engine.rootObjects()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
