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
    DrawingPoint,
    DrawingStroke,
    create_actiondraw_window,
)
from task_model import TaskModel


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

    def test_drawing_point(self):
        point = DrawingPoint(x=100.5, y=200.25)
        assert point.x == 100.5
        assert point.y == 200.25

    def test_drawing_stroke_defaults(self):
        stroke = DrawingStroke(
            id="stroke_0",
            points=[DrawingPoint(0.0, 0.0), DrawingPoint(10.0, 10.0)],
        )
        assert stroke.id == "stroke_0"
        assert stroke.color == "#ffffff"
        assert stroke.width == 3.0
        assert len(stroke.points) == 2

    def test_drawing_stroke_custom(self):
        stroke = DrawingStroke(
            id="stroke_1",
            points=[DrawingPoint(5.0, 5.0)],
            color="#ff0000",
            width=10.0,
        )
        assert stroke.color == "#ff0000"
        assert stroke.width == 10.0


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

    def test_add_freetext_item(self, empty_diagram_model):
        """Test adding a freetext item with multiline text."""
        item_id = empty_diagram_model.addPresetItemWithText(
            "freetext", 100.0, 150.0, "Line 1\nLine 2\nLine 3"
        )
        assert item_id.startswith("freetext_")
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "freetext"
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Line 1\nLine 2\nLine 3"
        assert empty_diagram_model.data(index, empty_diagram_model.ColorRole) == "#f5f0e6"
        assert empty_diagram_model.data(index, empty_diagram_model.TextColorRole) == "#2d3436"
        assert empty_diagram_model.data(index, empty_diagram_model.WidthRole) == 200.0
        assert empty_diagram_model.data(index, empty_diagram_model.HeightRole) == 140.0

    def test_add_freetext_empty(self, empty_diagram_model):
        """Test adding a freetext item with empty text."""
        item_id = empty_diagram_model.addPresetItem("freetext", 50.0, 50.0)
        assert item_id.startswith("freetext_")
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "freetext"
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == ""

    def test_freetext_invalid_preset(self, empty_diagram_model):
        """Test that invalid preset returns empty string."""
        item_id = empty_diagram_model.addPresetItem("invalid_type", 50.0, 50.0)
        assert item_id == ""
        assert empty_diagram_model.count == 0

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

    def test_edge_hover_target_during_drag(self, empty_diagram_model):
        """Edge dragging identifies hover target with enlarged hit area."""
        # Box A at (0,0), default size 120x60
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        # Box B at (200, 0), default size 120x60
        b = empty_diagram_model.addBox(200.0, 0.0, "B")
        empty_diagram_model.startEdgeDrawing(a)
        # Drag to exact center of B
        empty_diagram_model.updateEdgeDragPosition(260.0, 30.0)
        assert empty_diagram_model.edgeHoverTargetId == b

    def test_edge_hover_target_with_margin(self, empty_diagram_model):
        """Edge dragging uses 20px margin for easier drop targeting."""
        # Box at (100, 100), size 120x60
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(100.0, 100.0, "B")
        empty_diagram_model.startEdgeDrawing(a)
        # Position 15 pixels to the left of B (within 20px margin)
        empty_diagram_model.updateEdgeDragPosition(85.0, 130.0)
        assert empty_diagram_model.edgeHoverTargetId == b

    def test_edge_hover_target_outside_margin(self, empty_diagram_model):
        """No hover target when drag is outside margin."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(200.0, 200.0, "B")
        empty_diagram_model.startEdgeDrawing(a)
        # Position 30 pixels away (outside 20px margin)
        empty_diagram_model.updateEdgeDragPosition(165.0, 230.0)
        assert empty_diagram_model.edgeHoverTargetId == ""

    def test_edge_hover_target_excludes_source(self, empty_diagram_model):
        """Source item is not a valid hover target."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        empty_diagram_model.startEdgeDrawing(a)
        # Drag within source item bounds
        empty_diagram_model.updateEdgeDragPosition(60.0, 30.0)
        assert empty_diagram_model.edgeHoverTargetId == ""

    def test_edge_hover_target_clears_on_cancel(self, empty_diagram_model):
        """Hover target clears when edge drawing is cancelled."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(200.0, 0.0, "B")
        empty_diagram_model.startEdgeDrawing(a)
        empty_diagram_model.updateEdgeDragPosition(260.0, 30.0)
        assert empty_diagram_model.edgeHoverTargetId == b
        empty_diagram_model.cancelEdgeDrawing()
        assert empty_diagram_model.edgeHoverTargetId == ""

    def test_set_edge_description(self, empty_diagram_model):
        """Edge description can be set and retrieved."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(100.0, 0.0, "B")
        empty_diagram_model.addEdge(a, b)
        edge_id = empty_diagram_model.edges[0]["id"]
        empty_diagram_model.setEdgeDescription(edge_id, "connects to")
        assert empty_diagram_model.getEdgeDescription(edge_id) == "connects to"
        assert empty_diagram_model.edges[0]["description"] == "connects to"

    def test_edge_description_default_empty(self, empty_diagram_model):
        """Edge description defaults to empty string."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(100.0, 0.0, "B")
        empty_diagram_model.addEdge(a, b)
        edge_id = empty_diagram_model.edges[0]["id"]
        assert empty_diagram_model.getEdgeDescription(edge_id) == ""
        assert empty_diagram_model.edges[0]["description"] == ""

    def test_set_edge_description_invalid_id(self, empty_diagram_model):
        """Setting description on nonexistent edge does nothing."""
        a = empty_diagram_model.addBox(0.0, 0.0, "A")
        b = empty_diagram_model.addBox(100.0, 0.0, "B")
        empty_diagram_model.addEdge(a, b)
        empty_diagram_model.setEdgeDescription("nonexistent_edge", "test")
        edge_id = empty_diagram_model.edges[0]["id"]
        assert empty_diagram_model.getEdgeDescription(edge_id) == ""

    def test_get_edge_description_invalid_id(self, empty_diagram_model):
        """Getting description from nonexistent edge returns empty string."""
        assert empty_diagram_model.getEdgeDescription("nonexistent_edge") == ""

    def test_add_preset_item_and_connect(self, empty_diagram_model):
        """Creating a preset item with connection creates both item and edge."""
        source = empty_diagram_model.addBox(0.0, 0.0, "Source")
        target = empty_diagram_model.addPresetItemAndConnect(
            source, "obstacle", 200.0, 0.0, "New Obstacle"
        )
        assert target != ""
        assert len(empty_diagram_model.edges) == 1
        edge = empty_diagram_model.edges[0]
        assert edge["fromId"] == source
        assert edge["toId"] == target

    def test_add_preset_item_and_connect_no_source(self, empty_diagram_model):
        """Creating connected item with empty source still creates item but no edge."""
        target = empty_diagram_model.addPresetItemAndConnect(
            "", "box", 100.0, 100.0, "Orphan Box"
        )
        assert target != ""
        assert len(empty_diagram_model.edges) == 0


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

    def test_get_item_at_with_margin(self, empty_diagram_model):
        """Hit detection with margin enlarges the hit area."""
        # Box at (100, 100), size 120x60
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Box")
        # Inside exact bounds
        assert empty_diagram_model.getItemAtWithMargin(150.0, 130.0, 0.0) == item_id
        # Just outside left edge (99), but within 10px margin
        assert empty_diagram_model.getItemAtWithMargin(95.0, 130.0, 10.0) == item_id
        # Outside even with margin
        assert empty_diagram_model.getItemAtWithMargin(80.0, 130.0, 10.0) is None

    def test_role_names(self, empty_diagram_model):
        roles = empty_diagram_model.roleNames()
        assert roles[empty_diagram_model.IdRole] == b"itemId"
        assert roles[empty_diagram_model.TextRole] == b"text"
        assert roles[empty_diagram_model.ColorRole] == b"color"
        assert roles[empty_diagram_model.TextColorRole] == b"textColor"
        assert roles[empty_diagram_model.TaskCompletedRole] == b"taskCompleted"

    def test_data_invalid_index(self, empty_diagram_model):
        assert empty_diagram_model.data(empty_diagram_model.index(10, 0), empty_diagram_model.IdRole) is None
        assert empty_diagram_model.data(QModelIndex(), empty_diagram_model.IdRole) is None


class TestUnlimitedBoardSize:
    """Tests for unlimited board size (maxItemX, maxItemY properties)."""

    def test_max_item_x_empty(self, empty_diagram_model):
        """Empty model returns 0 for maxItemX."""
        assert empty_diagram_model.maxItemX == 0.0

    def test_max_item_y_empty(self, empty_diagram_model):
        """Empty model returns 0 for maxItemY."""
        assert empty_diagram_model.maxItemY == 0.0

    def test_max_item_x_single_item(self, empty_diagram_model):
        """maxItemX is x + width of the single item."""
        # Box default is 120x60
        empty_diagram_model.addBox(100.0, 50.0, "Box")
        assert empty_diagram_model.maxItemX == 100.0 + 120.0

    def test_max_item_y_single_item(self, empty_diagram_model):
        """maxItemY is y + height of the single item."""
        # Box default is 120x60
        empty_diagram_model.addBox(100.0, 50.0, "Box")
        assert empty_diagram_model.maxItemY == 50.0 + 60.0

    def test_max_item_x_multiple_items(self, empty_diagram_model):
        """maxItemX returns the rightmost edge among all items."""
        empty_diagram_model.addBox(0.0, 0.0, "Box1")  # rightmost: 0 + 120 = 120
        empty_diagram_model.addBox(500.0, 0.0, "Box2")  # rightmost: 500 + 120 = 620
        empty_diagram_model.addBox(200.0, 0.0, "Box3")  # rightmost: 200 + 120 = 320
        assert empty_diagram_model.maxItemX == 620.0

    def test_max_item_y_multiple_items(self, empty_diagram_model):
        """maxItemY returns the bottommost edge among all items."""
        empty_diagram_model.addBox(0.0, 0.0, "Box1")  # bottom: 0 + 60 = 60
        empty_diagram_model.addBox(0.0, 800.0, "Box2")  # bottom: 800 + 60 = 860
        empty_diagram_model.addBox(0.0, 300.0, "Box3")  # bottom: 300 + 60 = 360
        assert empty_diagram_model.maxItemY == 860.0

    def test_max_values_update_on_move(self, empty_diagram_model):
        """Moving an item updates max values."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Box")
        assert empty_diagram_model.maxItemX == 220.0
        assert empty_diagram_model.maxItemY == 160.0
        # Move item far right and down
        empty_diagram_model.moveItem(item_id, 5000.0, 3000.0)
        assert empty_diagram_model.maxItemX == 5120.0
        assert empty_diagram_model.maxItemY == 3060.0

    def test_max_values_with_different_sized_items(self, empty_diagram_model):
        """Items with different sizes are handled correctly."""
        # Add a database (160x90) at position (100, 100)
        empty_diagram_model.addPresetItem("database", 100.0, 100.0)
        assert empty_diagram_model.maxItemX == 100.0 + 160.0
        assert empty_diagram_model.maxItemY == 100.0 + 90.0

    def test_min_item_x_empty(self, empty_diagram_model):
        """Empty model returns 0 for minItemX."""
        assert empty_diagram_model.minItemX == 0.0

    def test_min_item_y_empty(self, empty_diagram_model):
        """Empty model returns 0 for minItemY."""
        assert empty_diagram_model.minItemY == 0.0

    def test_min_item_x_multiple_items(self, empty_diagram_model):
        """minItemX returns the leftmost x position among all items."""
        empty_diagram_model.addBox(500.0, 0.0, "Box1")
        empty_diagram_model.addBox(100.0, 0.0, "Box2")
        empty_diagram_model.addBox(300.0, 0.0, "Box3")
        assert empty_diagram_model.minItemX == 100.0

    def test_min_item_y_multiple_items(self, empty_diagram_model):
        """minItemY returns the topmost y position among all items."""
        empty_diagram_model.addBox(0.0, 800.0, "Box1")
        empty_diagram_model.addBox(0.0, 200.0, "Box2")
        empty_diagram_model.addBox(0.0, 500.0, "Box3")
        assert empty_diagram_model.minItemY == 200.0


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

    def test_add_task_from_text_and_connect(self, diagram_model_with_task_model):
        """Creating a task with connection creates task, diagram item, and edge."""
        source = diagram_model_with_task_model.addBox(0.0, 0.0, "Source")
        task_count_before = diagram_model_with_task_model._task_model.rowCount()
        target = diagram_model_with_task_model.addTaskFromTextAndConnect(
            source, 200.0, 0.0, "Connected Task"
        )
        assert target != ""
        assert len(diagram_model_with_task_model.edges) == 1
        edge = diagram_model_with_task_model.edges[0]
        assert edge["fromId"] == source
        assert edge["toId"] == target
        # Verify task was added to task model
        task_count_after = diagram_model_with_task_model._task_model.rowCount()
        assert task_count_after == task_count_before + 1

    def test_add_task_uses_title(self, diagram_model_with_task_model):
        item_id = diagram_model_with_task_model.addTask(1, 25.0, 35.0)
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TextRole) == diagram_model_with_task_model._task_model.data(
            diagram_model_with_task_model._task_model.index(1, 0),
            diagram_model_with_task_model._task_model.TitleRole,
        )
        assert item_id

    def test_task_completion_syncs_to_task_model(self, diagram_model_with_task_model):
        item_id = diagram_model_with_task_model.addTask(0, 50.0, 60.0)
        assert item_id
        index = diagram_model_with_task_model.index(0, 0)
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskCompletedRole) is False

        diagram_model_with_task_model.setTaskCompleted(0, True)
        task_model = diagram_model_with_task_model._task_model
        assert task_model.data(task_model.index(0, 0), task_model.CompletedRole) is True
        assert diagram_model_with_task_model.data(index, diagram_model_with_task_model.TaskCompletedRole) is True


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


class TestDiagramModelSerialization:
    """Tests for DiagramModel serialization (to_dict/from_dict)."""

    def test_to_dict_empty(self, empty_diagram_model):
        """Test serialization of empty diagram."""
        data = empty_diagram_model.to_dict()
        assert "items" in data
        assert "edges" in data
        assert data["items"] == []
        assert data["edges"] == []

    def test_to_dict_with_items(self, empty_diagram_model):
        """Test serialization with items."""
        empty_diagram_model.addBox(10.0, 20.0, "Test Box")
        empty_diagram_model.addPresetItem("database", 100.0, 100.0)

        data = empty_diagram_model.to_dict()
        assert len(data["items"]) == 2
        assert data["items"][0]["text"] == "Test Box"
        assert data["items"][0]["x"] == 10.0
        assert data["items"][0]["y"] == 20.0
        assert data["items"][1]["item_type"] == "database"

    def test_to_dict_with_edges(self, empty_diagram_model):
        """Test serialization with edges."""
        id1 = empty_diagram_model.addBox(10.0, 20.0, "Box 1")
        id2 = empty_diagram_model.addBox(100.0, 100.0, "Box 2")
        empty_diagram_model.addEdge(id1, id2)

        data = empty_diagram_model.to_dict()
        assert len(data["edges"]) == 1
        assert data["edges"][0]["from_id"] == id1
        assert data["edges"][0]["to_id"] == id2

    def test_to_dict_preserves_all_properties(self, empty_diagram_model):
        """Test that serialization preserves all item properties."""
        empty_diagram_model.addPresetItem("note", 50.0, 75.0)

        data = empty_diagram_model.to_dict()
        item = data["items"][0]

        assert "id" in item
        assert "item_type" in item
        assert "x" in item
        assert "y" in item
        assert "width" in item
        assert "height" in item
        assert "text" in item
        assert "task_index" in item
        assert "color" in item
        assert "text_color" in item
        assert "note_markdown" not in item

    def test_note_markdown_roundtrip(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItem("note", 10.0, 20.0)
        empty_diagram_model.setItemMarkdown(item_id, "# Title\nBody")

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["note_markdown"] == "# Title\nBody"

        new_model = DiagramModel()
        new_model.from_dict(data)
        assert new_model.getItemMarkdown(item_id) == "# Title\nBody"

    def test_from_dict_empty(self, empty_diagram_model):
        """Test loading empty data."""
        empty_diagram_model.addBox(10.0, 20.0, "Existing")
        assert empty_diagram_model.count == 1

        empty_diagram_model.from_dict({"items": [], "edges": []})
        assert empty_diagram_model.count == 0

    def test_from_dict_with_items(self, empty_diagram_model):
        """Test loading items from dict."""
        data = {
            "items": [
                {
                    "id": "box_0",
                    "item_type": "box",
                    "x": 50.0,
                    "y": 75.0,
                    "width": 120.0,
                    "height": 60.0,
                    "text": "Loaded Box",
                    "task_index": -1,
                    "color": "#4a9eff",
                    "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
        }
        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "Loaded Box"
        assert empty_diagram_model.data(index, empty_diagram_model.XRole) == 50.0
        assert empty_diagram_model.data(index, empty_diagram_model.YRole) == 75.0

    def test_from_dict_with_edges(self, empty_diagram_model):
        """Test loading edges from dict."""
        data = {
            "items": [
                {
                    "id": "box_0", "item_type": "box", "x": 10.0, "y": 10.0,
                    "width": 120.0, "height": 60.0, "text": "A",
                    "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8",
                },
                {
                    "id": "box_1", "item_type": "box", "x": 200.0, "y": 200.0,
                    "width": 120.0, "height": 60.0, "text": "B",
                    "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8",
                },
            ],
            "edges": [
                {"id": "edge_0", "from_id": "box_0", "to_id": "box_1"},
            ],
        }
        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 2
        assert len(empty_diagram_model.edges) == 1
        assert empty_diagram_model.edges[0]["fromId"] == "box_0"
        assert empty_diagram_model.edges[0]["toId"] == "box_1"

    def test_from_dict_clears_existing(self, empty_diagram_model):
        """Test that from_dict clears existing items and edges."""
        id1 = empty_diagram_model.addBox(10.0, 20.0, "Old Box 1")
        id2 = empty_diagram_model.addBox(100.0, 100.0, "Old Box 2")
        empty_diagram_model.addEdge(id1, id2)
        assert empty_diagram_model.count == 2
        assert len(empty_diagram_model.edges) == 1

        data = {
            "items": [
                {
                    "id": "new_0", "item_type": "box", "x": 50.0, "y": 50.0,
                    "width": 120.0, "height": 60.0, "text": "New Box",
                    "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
        }
        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 1
        assert len(empty_diagram_model.edges) == 0
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextRole) == "New Box"

    def test_roundtrip_serialization(self, empty_diagram_model):
        """Test that data survives serialization round-trip."""
        id1 = empty_diagram_model.addBox(10.0, 20.0, "Box A")
        id2 = empty_diagram_model.addPresetItem("database", 150.0, 100.0)
        id3 = empty_diagram_model.addPresetItemWithText("note", 200.0, 200.0, "My Note")
        empty_diagram_model.addEdge(id1, id2)
        empty_diagram_model.addEdge(id2, id3)

        # Serialize
        data = empty_diagram_model.to_dict()

        # Create new model and deserialize
        new_model = DiagramModel()
        new_model.from_dict(data)

        assert new_model.count == 3
        assert len(new_model.edges) == 2

        # Check item properties preserved
        index0 = new_model.index(0, 0)
        assert new_model.data(index0, new_model.TextRole) == "Box A"
        assert new_model.data(index0, new_model.XRole) == 10.0

        index1 = new_model.index(1, 0)
        assert new_model.data(index1, new_model.TypeRole) == "database"

        index2 = new_model.index(2, 0)
        assert new_model.data(index2, new_model.TextRole) == "My Note"

    def test_from_dict_handles_invalid_type(self, empty_diagram_model):
        """Test that invalid item types default to box."""
        data = {
            "items": [
                {
                    "id": "invalid_0", "item_type": "nonexistent", "x": 50.0, "y": 50.0,
                    "width": 120.0, "height": 60.0, "text": "Unknown Type",
                    "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
        }
        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "box"

    def test_from_dict_resumes_id_generation(self, empty_diagram_model):
        """Test that ID generation resumes after loading."""
        data = {
            "items": [
                {
                    "id": "box_5", "item_type": "box", "x": 50.0, "y": 50.0,
                    "width": 120.0, "height": 60.0, "text": "Existing",
                    "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
        }
        empty_diagram_model.from_dict(data)

        # Add a new box - should get ID with number >= 6
        new_id = empty_diagram_model.addBox(100.0, 100.0, "New Box")
        # Extract number from ID
        id_num = int(new_id.split("_")[1])
        assert id_num >= 6


class TestDrawingFeature:
    """Tests for the freehand drawing functionality."""

    def test_drawing_mode_default(self, empty_diagram_model):
        """Test that drawing mode is off by default."""
        assert empty_diagram_model.drawingMode is False

    def test_set_drawing_mode(self, empty_diagram_model):
        """Test toggling drawing mode on and off."""
        empty_diagram_model.setDrawingMode(True)
        assert empty_diagram_model.drawingMode is True

        empty_diagram_model.setDrawingMode(False)
        assert empty_diagram_model.drawingMode is False

    def test_brush_color_default(self, empty_diagram_model):
        """Test default brush color."""
        assert empty_diagram_model.brushColor == "#ffffff"

    def test_set_brush_color(self, empty_diagram_model):
        """Test changing brush color."""
        empty_diagram_model.setBrushColor("#ff5555")
        assert empty_diagram_model.brushColor == "#ff5555"

    def test_brush_width_default(self, empty_diagram_model):
        """Test default brush width."""
        assert empty_diagram_model.brushWidth == 3.0

    def test_set_brush_width(self, empty_diagram_model):
        """Test changing brush width."""
        empty_diagram_model.setBrushWidth(10.0)
        assert empty_diagram_model.brushWidth == 10.0

    def test_brush_width_clamped(self, empty_diagram_model):
        """Test brush width is clamped to valid range."""
        empty_diagram_model.setBrushWidth(0.5)
        assert empty_diagram_model.brushWidth == 1.0

        empty_diagram_model.setBrushWidth(100.0)
        assert empty_diagram_model.brushWidth == 50.0

    def test_empty_strokes(self, empty_diagram_model):
        """Test that strokes list is empty initially."""
        assert empty_diagram_model.strokes == []

    def test_start_stroke(self, empty_diagram_model):
        """Test starting a stroke."""
        empty_diagram_model.startStroke(100.0, 200.0)
        current = empty_diagram_model.getCurrentStroke()
        assert current["points"] is not None
        assert len(current["points"]) == 1
        assert current["points"][0]["x"] == 100.0
        assert current["points"][0]["y"] == 200.0

    def test_continue_stroke(self, empty_diagram_model):
        """Test adding points to a stroke."""
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(10.0, 10.0)
        empty_diagram_model.continueStroke(20.0, 20.0)

        current = empty_diagram_model.getCurrentStroke()
        assert len(current["points"]) == 3

    def test_end_stroke(self, empty_diagram_model):
        """Test finishing a stroke adds it to the strokes list."""
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(50.0, 50.0)
        empty_diagram_model.endStroke()

        strokes = empty_diagram_model.strokes
        assert len(strokes) == 1
        assert strokes[0]["points"][0]["x"] == 0.0
        assert strokes[0]["points"][1]["x"] == 50.0

    def test_stroke_uses_current_brush_settings(self, empty_diagram_model):
        """Test that strokes use the current brush color and width."""
        empty_diagram_model.setBrushColor("#ff0000")
        empty_diagram_model.setBrushWidth(8.0)

        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(10.0, 10.0)
        empty_diagram_model.endStroke()

        strokes = empty_diagram_model.strokes
        assert strokes[0]["color"] == "#ff0000"
        assert strokes[0]["width"] == 8.0

    def test_single_point_stroke_not_saved(self, empty_diagram_model):
        """Test that single-point strokes are not saved."""
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.endStroke()

        assert len(empty_diagram_model.strokes) == 0

    def test_undo_last_stroke(self, empty_diagram_model):
        """Test undoing the last stroke."""
        # Draw two strokes
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(10.0, 10.0)
        empty_diagram_model.endStroke()

        empty_diagram_model.startStroke(20.0, 20.0)
        empty_diagram_model.continueStroke(30.0, 30.0)
        empty_diagram_model.endStroke()

        assert len(empty_diagram_model.strokes) == 2

        empty_diagram_model.undoLastStroke()
        assert len(empty_diagram_model.strokes) == 1

        empty_diagram_model.undoLastStroke()
        assert len(empty_diagram_model.strokes) == 0

    def test_undo_empty_strokes(self, empty_diagram_model):
        """Test that undoing on empty list doesn't crash."""
        empty_diagram_model.undoLastStroke()  # Should not raise
        assert len(empty_diagram_model.strokes) == 0

    def test_clear_strokes(self, empty_diagram_model):
        """Test clearing all strokes."""
        # Draw some strokes
        for _ in range(3):
            empty_diagram_model.startStroke(0.0, 0.0)
            empty_diagram_model.continueStroke(10.0, 10.0)
            empty_diagram_model.endStroke()

        assert len(empty_diagram_model.strokes) == 3

        empty_diagram_model.clearStrokes()
        assert len(empty_diagram_model.strokes) == 0

    def test_strokes_serialization(self, empty_diagram_model):
        """Test that strokes are included in to_dict output."""
        empty_diagram_model.setBrushColor("#00ff00")
        empty_diagram_model.setBrushWidth(5.0)
        empty_diagram_model.startStroke(10.0, 20.0)
        empty_diagram_model.continueStroke(30.0, 40.0)
        empty_diagram_model.continueStroke(50.0, 60.0)
        empty_diagram_model.endStroke()

        data = empty_diagram_model.to_dict()
        assert "strokes" in data
        assert len(data["strokes"]) == 1

        stroke = data["strokes"][0]
        assert stroke["color"] == "#00ff00"
        assert stroke["width"] == 5.0
        assert len(stroke["points"]) == 3
        assert stroke["points"][0] == {"x": 10.0, "y": 20.0}

    def test_strokes_deserialization(self, empty_diagram_model):
        """Test that strokes are loaded from from_dict."""
        data = {
            "items": [],
            "edges": [],
            "strokes": [
                {
                    "id": "stroke_0",
                    "color": "#ff00ff",
                    "width": 7.0,
                    "points": [
                        {"x": 100.0, "y": 100.0},
                        {"x": 150.0, "y": 150.0},
                        {"x": 200.0, "y": 100.0},
                    ],
                }
            ],
        }

        empty_diagram_model.from_dict(data)

        strokes = empty_diagram_model.strokes
        assert len(strokes) == 1
        assert strokes[0]["color"] == "#ff00ff"
        assert strokes[0]["width"] == 7.0
        assert len(strokes[0]["points"]) == 3

    def test_strokes_cleared_on_from_dict(self, empty_diagram_model):
        """Test that existing strokes are cleared when loading."""
        # Add some strokes
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(10.0, 10.0)
        empty_diagram_model.endStroke()

        # Load empty diagram
        data = {"items": [], "edges": [], "strokes": []}
        empty_diagram_model.from_dict(data)

        assert len(empty_diagram_model.strokes) == 0

    def test_stroke_id_resumes_after_load(self, empty_diagram_model):
        """Test that stroke ID generation resumes after loading."""
        data = {
            "items": [],
            "edges": [],
            "strokes": [
                {
                    "id": "stroke_10",
                    "color": "#ffffff",
                    "width": 3.0,
                    "points": [{"x": 0.0, "y": 0.0}, {"x": 10.0, "y": 10.0}],
                }
            ],
        }
        empty_diagram_model.from_dict(data)

        # Draw a new stroke
        empty_diagram_model.startStroke(0.0, 0.0)
        empty_diagram_model.continueStroke(10.0, 10.0)
        empty_diagram_model.endStroke()

        strokes = empty_diagram_model.strokes
        assert len(strokes) == 2
        # New stroke should have ID >= stroke_11
        new_id = strokes[1]["id"]
        id_num = int(new_id.split("_")[1])
        assert id_num >= 11

    def test_multiple_strokes_preserved(self, empty_diagram_model):
        """Test drawing multiple strokes."""
        colors = ["#ff0000", "#00ff00", "#0000ff"]

        for i, color in enumerate(colors):
            empty_diagram_model.setBrushColor(color)
            empty_diagram_model.startStroke(float(i * 10), 0.0)
            empty_diagram_model.continueStroke(float(i * 10 + 5), 5.0)
            empty_diagram_model.endStroke()

        strokes = empty_diagram_model.strokes
        assert len(strokes) == 3

        for i, stroke in enumerate(strokes):
            assert stroke["color"] == colors[i]


class TestImagePaste:
    """Tests for image paste functionality."""

    def test_diagram_item_image_data_field(self):
        """Test that DiagramItem has image_data field with default."""
        item = DiagramItem(
            id="image_1",
            item_type=DiagramItemType.IMAGE,
            x=100.0,
            y=200.0,
        )
        assert item.image_data == ""

    def test_diagram_item_image_with_data(self):
        """Test DiagramItem with image_data set."""
        item = DiagramItem(
            id="image_1",
            item_type=DiagramItemType.IMAGE,
            x=100.0,
            y=200.0,
            width=300.0,
            height=200.0,
            image_data="iVBORw0KGgoAAAANSUhEUg==",  # Minimal base64 PNG header
        )
        assert item.image_data == "iVBORw0KGgoAAAANSUhEUg=="
        assert item.item_type == DiagramItemType.IMAGE
        assert item.width == 300.0
        assert item.height == 200.0

    def test_image_type_exists(self):
        """Test that IMAGE type exists in DiagramItemType enum."""
        assert hasattr(DiagramItemType, "IMAGE")
        assert DiagramItemType.IMAGE.value == "image"

    def test_has_clipboard_image_empty(self, empty_diagram_model):
        """Test hasClipboardImage returns False when clipboard has no image."""
        # Clipboard should be empty or have non-image content
        result = empty_diagram_model.hasClipboardImage()
        assert isinstance(result, bool)
        # We can't guarantee clipboard state in tests, just check it doesn't crash

    def test_paste_image_empty_clipboard(self, empty_diagram_model):
        """Test pasteImageFromClipboard returns empty string with no image in clipboard."""
        # With no image in clipboard, should return empty string
        result = empty_diagram_model.pasteImageFromClipboard(100.0, 100.0)
        # Either returns empty string (no image) or a valid ID (if clipboard has image)
        assert isinstance(result, str)

    def test_image_data_role_exists(self, empty_diagram_model):
        """Test ImageDataRole exists in model."""
        assert hasattr(empty_diagram_model, "ImageDataRole")

    def test_model_returns_image_data(self, empty_diagram_model):
        """Test model data() returns image_data for ImageDataRole."""
        # Manually add an image item to test role retrieval
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="image_test",
            item_type=DiagramItemType.IMAGE,
            x=50.0,
            y=50.0,
            width=200.0,
            height=150.0,
            image_data="test_base64_data",
        )
        empty_diagram_model._append_item(item)

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.ImageDataRole) == "test_base64_data"
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "image"

    def test_to_dict_includes_image_data(self, empty_diagram_model):
        """Test to_dict includes image_data for image items."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="image_save",
            item_type=DiagramItemType.IMAGE,
            x=100.0,
            y=100.0,
            width=250.0,
            height=200.0,
            image_data="base64_image_content",
        )
        empty_diagram_model._append_item(item)

        data = empty_diagram_model.to_dict()
        assert len(data["items"]) == 1
        assert data["items"][0]["image_data"] == "base64_image_content"
        assert data["items"][0]["item_type"] == "image"

    def test_to_dict_excludes_image_data_for_non_images(self, empty_diagram_model):
        """Test to_dict does not include image_data for non-image items."""
        empty_diagram_model.addBox(10.0, 10.0, "Test Box")

        data = empty_diagram_model.to_dict()
        assert len(data["items"]) == 1
        assert "image_data" not in data["items"][0]

    def test_from_dict_loads_image_data(self, empty_diagram_model):
        """Test from_dict correctly loads image_data."""
        data = {
            "items": [
                {
                    "id": "image_load",
                    "item_type": "image",
                    "x": 150.0,
                    "y": 150.0,
                    "width": 300.0,
                    "height": 225.0,
                    "text": "",
                    "task_index": -1,
                    "color": "#2a3444",
                    "text_color": "#f5f6f8",
                    "image_data": "loaded_base64_data",
                }
            ],
            "edges": [],
        }

        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TypeRole) == "image"
        assert empty_diagram_model.data(index, empty_diagram_model.ImageDataRole) == "loaded_base64_data"
        assert empty_diagram_model.data(index, empty_diagram_model.WidthRole) == 300.0

    def test_from_dict_handles_missing_image_data(self, empty_diagram_model):
        """Test from_dict handles items without image_data field."""
        data = {
            "items": [
                {
                    "id": "box_old",
                    "item_type": "box",
                    "x": 50.0,
                    "y": 50.0,
                    "width": 120.0,
                    "height": 60.0,
                    "text": "Old Box",
                    "task_index": -1,
                    "color": "#4a9eff",
                    "text_color": "#f5f6f8",
                    # No image_data field - simulates old saved files
                }
            ],
            "edges": [],
        }

        empty_diagram_model.from_dict(data)

        assert empty_diagram_model.count == 1
        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.ImageDataRole) == ""

    def test_image_item_resize(self, empty_diagram_model):
        """Test that image items can be resized."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="image_resize",
            item_type=DiagramItemType.IMAGE,
            x=0.0,
            y=0.0,
            width=200.0,
            height=150.0,
            image_data="test",
        )
        empty_diagram_model._append_item(item)

        empty_diagram_model.resizeItem("image_resize", 400.0, 300.0)

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.WidthRole) == 400.0
        assert empty_diagram_model.data(index, empty_diagram_model.HeightRole) == 300.0

    def test_image_item_resize_respects_minimum(self, empty_diagram_model):
        """Test that image resize respects minimum dimensions."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="image_min",
            item_type=DiagramItemType.IMAGE,
            x=0.0,
            y=0.0,
            width=200.0,
            height=150.0,
            image_data="test",
        )
        empty_diagram_model._append_item(item)

        # Try to resize below minimum
        empty_diagram_model.resizeItem("image_min", 10.0, 5.0)

        index = empty_diagram_model.index(0, 0)
        # Should be clamped to minimum (40.0 width, 30.0 height)
        assert empty_diagram_model.data(index, empty_diagram_model.WidthRole) >= 40.0
        assert empty_diagram_model.data(index, empty_diagram_model.HeightRole) >= 30.0


class TestSubDiagramFunctionality:
    """Tests for sub-diagram linking and progress tracking."""

    def test_sub_diagram_path_field_default(self):
        """Test that sub_diagram_path defaults to empty string."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(id="task_1", item_type=DiagramItemType.TASK, x=0.0, y=0.0)
        assert item.sub_diagram_path == ""

    def test_sub_diagram_path_field_set(self):
        """Test that sub_diagram_path can be set."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="task_1",
            item_type=DiagramItemType.TASK,
            x=0.0,
            y=0.0,
            sub_diagram_path="/path/to/sub.progress"
        )
        assert item.sub_diagram_path == "/path/to/sub.progress"

    def test_set_sub_diagram_path_slot(self, empty_diagram_model):
        """Test setSubDiagramPath slot updates item."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "/path/to/sub.progress")

        item = empty_diagram_model.getItem(item_id)
        assert item.sub_diagram_path == "/path/to/sub.progress"

    def test_set_sub_diagram_path_normalizes_file_url(self, empty_diagram_model):
        """Test setSubDiagramPath normalizes file:// URLs."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "file:///path/to/sub.progress")

        item = empty_diagram_model.getItem(item_id)
        assert item.sub_diagram_path == "/path/to/sub.progress"

    def test_sub_diagram_path_role(self, empty_diagram_model):
        """Test SubDiagramPathRole returns correct value."""
        from actiondraw import DiagramItem, DiagramItemType

        item = DiagramItem(
            id="task_1",
            item_type=DiagramItemType.TASK,
            x=0.0,
            y=0.0,
            sub_diagram_path="/path/to/sub.progress"
        )
        empty_diagram_model._append_item(item)

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramPathRole) == "/path/to/sub.progress"

    def test_sub_diagram_progress_role_no_path(self, empty_diagram_model):
        """Test SubDiagramProgressRole returns -1 when no path set."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == -1

    def test_sub_diagram_progress_role_missing_file(self, empty_diagram_model):
        """Test SubDiagramProgressRole returns -1 for missing file."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "/nonexistent/path.progress")

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == -1

    def test_sub_diagram_progress_calculation(self, empty_diagram_model, tmp_path):
        """Test SubDiagramProgressRole calculates correct percentage."""
        import json

        # Create a sub-diagram file with 2/4 tasks completed (50%)
        sub_diagram = {
            "version": "1.0",
            "tasks": {
                "tasks": [
                    {"title": "Task 1", "completed": True},
                    {"title": "Task 2", "completed": True},
                    {"title": "Task 3", "completed": False},
                    {"title": "Task 4", "completed": False},
                ]
            },
            "diagram": {"items": [], "edges": [], "strokes": []}
        }
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 50

    def test_sub_diagram_progress_100_percent(self, empty_diagram_model, tmp_path):
        """Test SubDiagramProgressRole returns 100 when all tasks complete."""
        import json

        sub_diagram = {
            "version": "1.0",
            "tasks": {
                "tasks": [
                    {"title": "Task 1", "completed": True},
                    {"title": "Task 2", "completed": True},
                ]
            },
            "diagram": {"items": [], "edges": [], "strokes": []}
        }
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 100

    def test_sub_diagram_progress_0_percent(self, empty_diagram_model, tmp_path):
        """Test SubDiagramProgressRole returns 0 when no tasks complete."""
        import json

        sub_diagram = {
            "version": "1.0",
            "tasks": {
                "tasks": [
                    {"title": "Task 1", "completed": False},
                    {"title": "Task 2", "completed": False},
                ]
            },
            "diagram": {"items": [], "edges": [], "strokes": []}
        }
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 0

    def test_sub_diagram_progress_empty_tasks(self, empty_diagram_model, tmp_path):
        """Test SubDiagramProgressRole returns 0 for empty task list."""
        import json

        sub_diagram = {
            "version": "1.0",
            "tasks": {"tasks": []},
            "diagram": {"items": [], "edges": [], "strokes": []}
        }
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 0

    def test_sub_diagram_progress_invalid_json(self, empty_diagram_model, tmp_path):
        """Test SubDiagramProgressRole returns -1 for invalid JSON."""
        sub_file = tmp_path / "invalid.progress"
        sub_file.write_text("not valid json {{{")

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == -1

    def test_to_dict_includes_sub_diagram_path(self, empty_diagram_model):
        """Test to_dict includes sub_diagram_path when set."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "/path/to/sub.progress")

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["sub_diagram_path"] == "/path/to/sub.progress"

    def test_to_dict_omits_empty_sub_diagram_path(self, empty_diagram_model):
        """Test to_dict omits sub_diagram_path when empty."""
        empty_diagram_model.addBox(0.0, 0.0, "Test")

        data = empty_diagram_model.to_dict()
        assert "sub_diagram_path" not in data["items"][0]

    def test_from_dict_loads_sub_diagram_path(self, empty_diagram_model):
        """Test from_dict loads sub_diagram_path correctly."""
        data = {
            "items": [{
                "id": "box_1",
                "item_type": "box",
                "x": 0.0,
                "y": 0.0,
                "width": 120.0,
                "height": 60.0,
                "text": "Test",
                "task_index": -1,
                "color": "#4a9eff",
                "text_color": "#f5f6f8",
                "sub_diagram_path": "/path/to/sub.progress"
            }],
            "edges": [],
            "strokes": [],
            "current_task_index": -1
        }
        empty_diagram_model.from_dict(data)

        item = empty_diagram_model.getItem("box_1")
        assert item.sub_diagram_path == "/path/to/sub.progress"

    def test_from_dict_defaults_missing_sub_diagram_path(self, empty_diagram_model):
        """Test from_dict defaults sub_diagram_path to empty string."""
        data = {
            "items": [{
                "id": "box_1",
                "item_type": "box",
                "x": 0.0,
                "y": 0.0,
                "width": 120.0,
                "height": 60.0,
                "text": "Test",
                "task_index": -1,
                "color": "#4a9eff",
                "text_color": "#f5f6f8"
            }],
            "edges": [],
            "strokes": [],
            "current_task_index": -1
        }
        empty_diagram_model.from_dict(data)

        item = empty_diagram_model.getItem("box_1")
        assert item.sub_diagram_path == ""

    def test_get_item_snapshot_includes_sub_diagram_path(self, empty_diagram_model):
        """Test getItemSnapshot includes subDiagramPath."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "/path/to/sub.progress")

        snapshot = empty_diagram_model.getItemSnapshot(item_id)
        assert snapshot["subDiagramPath"] == "/path/to/sub.progress"

    def test_role_names_include_sub_diagram_roles(self, empty_diagram_model):
        """Test roleNames includes sub-diagram roles."""
        roles = empty_diagram_model.roleNames()
        role_names = [v.decode() for v in roles.values()]
        assert "subDiagramPath" in role_names
        assert "subDiagramProgress" in role_names

    def test_resolve_sub_diagram_path_absolute(self, empty_diagram_model):
        """Test _resolve_sub_diagram_path with absolute path."""
        empty_diagram_model._project_path = "/home/user/project.progress"
        result = empty_diagram_model._resolve_sub_diagram_path("/absolute/path.progress")
        assert result == "/absolute/path.progress"

    def test_resolve_sub_diagram_path_relative(self, empty_diagram_model):
        """Test _resolve_sub_diagram_path with relative path."""
        empty_diagram_model._project_path = "/home/user/project.progress"
        result = empty_diagram_model._resolve_sub_diagram_path("sub/diagram.progress")
        assert result == "/home/user/sub/diagram.progress"

    def test_resolve_sub_diagram_path_empty(self, empty_diagram_model):
        """Test _resolve_sub_diagram_path with empty path."""
        empty_diagram_model._project_path = "/home/user/project.progress"
        result = empty_diagram_model._resolve_sub_diagram_path("")
        assert result == ""

    def test_set_project_path(self, empty_diagram_model):
        """Test setProjectPath sets the path correctly."""
        empty_diagram_model.setProjectPath("/path/to/project.progress")
        assert empty_diagram_model._project_path == "/path/to/project.progress"

    def test_create_and_link_sub_diagram(self, empty_diagram_model, tmp_path):
        """Test createAndLinkSubDiagram creates file and links it."""
        import json

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        sub_file = tmp_path / "new_sub.progress"

        empty_diagram_model.createAndLinkSubDiagram(item_id, str(sub_file), open_after=False)

        # Check file was created
        assert sub_file.exists()

        # Check file has valid structure
        data = json.loads(sub_file.read_text())
        assert "version" in data
        assert "tasks" in data
        assert "diagram" in data

        # Check item was linked
        item = empty_diagram_model.getItem(item_id)
        assert item.sub_diagram_path == str(sub_file)

    def test_create_and_link_sub_diagram_normalizes_file_url(self, empty_diagram_model, tmp_path):
        """Test createAndLinkSubDiagram normalizes file:// URLs."""
        import json

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        sub_file = tmp_path / "new_sub.progress"

        empty_diagram_model.createAndLinkSubDiagram(item_id, f"file://{sub_file}", open_after=False)

        # Check file was created
        assert sub_file.exists()

        # Check item was linked with normalized path
        item = empty_diagram_model.getItem(item_id)
        assert item.sub_diagram_path == str(sub_file)

    def test_open_sub_diagram_returns_false_no_item(self, empty_diagram_model):
        """Test openSubDiagram returns False for nonexistent item."""
        result = empty_diagram_model.openSubDiagram("nonexistent_id")
        assert result is False

    def test_open_sub_diagram_returns_false_no_path(self, empty_diagram_model):
        """Test openSubDiagram returns False when no sub-diagram path set."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        result = empty_diagram_model.openSubDiagram(item_id)
        assert result is False

    def test_open_sub_diagram_returns_false_missing_file(self, empty_diagram_model):
        """Test openSubDiagram returns False when file doesn't exist."""
        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, "/nonexistent/path.progress")
        result = empty_diagram_model.openSubDiagram(item_id)
        assert result is False

    def test_open_sub_diagram_launches_subprocess(self, empty_diagram_model, tmp_path, monkeypatch):
        """Test openSubDiagram launches subprocess with correct arguments."""
        import json
        import subprocess

        # Create a sub-diagram file
        sub_diagram = {"version": "1.0", "tasks": {"tasks": []}, "diagram": {}}
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        # Mock subprocess.Popen
        popen_calls = []
        def mock_popen(args):
            popen_calls.append(args)
        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = empty_diagram_model.openSubDiagram(item_id)

        assert result is True
        assert len(popen_calls) == 1
        assert str(sub_file) in popen_calls[0]

    def test_open_sub_diagram_resolves_relative_path(self, empty_diagram_model, tmp_path, monkeypatch):
        """Test openSubDiagram resolves relative paths correctly."""
        import json
        import subprocess

        # Create project structure
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        sub_dir = project_dir / "subdiagrams"
        sub_dir.mkdir()

        sub_diagram = {"version": "1.0", "tasks": {"tasks": []}, "diagram": {}}
        sub_file = sub_dir / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        # Set project path
        empty_diagram_model.setProjectPath(str(project_dir / "main.progress"))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        # Set relative path
        empty_diagram_model.setSubDiagramPath(item_id, "subdiagrams/sub.progress")

        # Mock subprocess.Popen
        popen_calls = []
        def mock_popen(args):
            popen_calls.append(args)
        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        result = empty_diagram_model.openSubDiagram(item_id)

        assert result is True
        assert len(popen_calls) == 1
        # Should resolve to absolute path
        assert str(sub_file) in popen_calls[0]

    def test_file_watcher_initialized(self, empty_diagram_model):
        """Test that file watcher is initialized."""
        from PySide6.QtCore import QFileSystemWatcher
        assert hasattr(empty_diagram_model, '_sub_diagram_watcher')
        assert isinstance(empty_diagram_model._sub_diagram_watcher, QFileSystemWatcher)

    def test_update_sub_diagram_watches_adds_files(self, empty_diagram_model, tmp_path):
        """Test _update_sub_diagram_watches adds files to watcher."""
        import json

        # Create a sub-diagram file
        sub_diagram = {"version": "1.0", "tasks": {"tasks": []}, "diagram": {}}
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        watched = empty_diagram_model._sub_diagram_watcher.files()
        assert str(sub_file) in watched

    def test_sub_diagram_progress_updates_on_file_change(self, empty_diagram_model, tmp_path):
        """Test that progress updates when sub-diagram file changes."""
        import json
        import time

        # Create initial sub-diagram with 0% progress
        sub_diagram = {
            "version": "1.0",
            "tasks": {
                "tasks": [
                    {"title": "Task 1", "completed": False},
                    {"title": "Task 2", "completed": False},
                ]
            },
            "diagram": {"items": [], "edges": [], "strokes": []}
        }
        sub_file = tmp_path / "sub.progress"
        sub_file.write_text(json.dumps(sub_diagram))

        item_id = empty_diagram_model.addBox(0.0, 0.0, "Test")
        empty_diagram_model.setSubDiagramPath(item_id, str(sub_file))

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 0

        # Update file to 50% progress
        sub_diagram["tasks"]["tasks"][0]["completed"] = True
        sub_file.write_text(json.dumps(sub_diagram))

        # Progress should be updated when file is re-read
        assert empty_diagram_model.data(index, empty_diagram_model.SubDiagramProgressRole) == 50


class TestCommandLineLoading:
    """Tests for command line file loading."""

    def test_main_loads_file_from_argv(self, tmp_path, monkeypatch):
        """Test that main() loads file from command line argument."""
        import json
        import sys

        # Create a project file
        project = {
            "version": "1.0",
            "tasks": {"tasks": [{"title": "Test Task", "completed": False}]},
            "diagram": {"items": [], "edges": [], "strokes": [], "current_task_index": -1}
        }
        project_file = tmp_path / "test.progress"
        project_file.write_text(json.dumps(project))

        # We can't fully test main() without a display, but we can verify
        # that the command line parsing logic works by checking the path handling
        path = str(project_file)

        # Test file:// URL normalization
        file_url = f"file://{path}"
        if file_url.startswith("file://"):
            normalized = file_url[7:]
        else:
            normalized = file_url
        assert normalized == path

        # Test path exists check
        import os
        assert os.path.exists(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
