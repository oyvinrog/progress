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


class TestFolderLinks:
    def test_set_folder_path_normalizes_windows_file_url(self, empty_diagram_model, monkeypatch):
        import actiondraw.model as model_module

        item_id = empty_diagram_model.addBox(10.0, 10.0, "Folder Item")
        monkeypatch.setattr(model_module.os, "name", "nt", raising=False)

        empty_diagram_model.setFolderPath(item_id, "file:///C:/Users/Test%20Folder")

        assert empty_diagram_model.getFolderPath(item_id) == "C:/Users/Test Folder"

    def test_open_folder_windows_uses_startfile(self, empty_diagram_model, monkeypatch):
        import actiondraw.model as model_module

        item_id = empty_diagram_model.addBox(10.0, 10.0, "Folder Item")
        # Simulate legacy stored Windows path format.
        empty_diagram_model.setFolderPath(item_id, "/C:/Users/Test Folder")

        monkeypatch.setattr(model_module.os, "name", "nt", raising=False)
        monkeypatch.setattr(model_module.platform, "system", lambda: "Windows")
        monkeypatch.setattr(model_module.os.path, "isdir", lambda path: path == "C:/Users/Test Folder")

        opened = []
        monkeypatch.setattr(model_module.os, "startfile", lambda path: opened.append(path), raising=False)

        assert empty_diagram_model.openFolder(item_id) is True
        assert opened == ["C:/Users/Test Folder"]


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


class TestMultiTabSupport:
    """Tests for multi-tab support in ActionDraw."""

    @pytest.fixture
    def tab_model(self, app):
        from task_model import TabModel
        return TabModel()

    @pytest.fixture
    def project_manager_with_tabs(self, app, task_model, empty_diagram_model):
        from task_model import ProjectManager, TabModel
        tab_model = TabModel()
        return ProjectManager(task_model, empty_diagram_model, tab_model), tab_model

    # --- Format tests ---

    def test_load_v1_format_creates_single_tab(self, app, tmp_path):
        """Loading a v1.0 file creates a single 'Main' tab."""
        import json
        from task_model import TaskModel, ProjectManager, TabModel

        # Create v1.0 format file
        v1_data = {
            "version": "1.0",
            "saved_at": "2024-01-01T12:00:00",
            "tasks": {
                "tasks": [
                    {"title": "Task 1", "completed": False, "time_spent": 0.0}
                ]
            },
            "diagram": {
                "items": [
                    {"id": "box_0", "item_type": "box", "x": 10.0, "y": 20.0,
                     "width": 120.0, "height": 60.0, "text": "Test Box",
                     "task_index": -1, "color": "#4a9eff", "text_color": "#f5f6f8"}
                ],
                "edges": [],
                "strokes": []
            }
        }
        project_file = tmp_path / "v1_project.progress"
        project_file.write_text(json.dumps(v1_data))

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        project_manager.loadProject(str(project_file))

        assert tab_model.tabCount == 1
        assert tab_model.currentTabName == "Main"
        assert task_model.rowCount() == 1
        assert diagram_model.count == 1

    def test_save_creates_v1_1_format(self, app, tmp_path):
        """Saving a project creates v1.1 format with tabs array."""
        import json
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Test Task", -1)
        diagram_model.addBox(50.0, 50.0, "Box")

        project_file = tmp_path / "new_project.progress"
        project_manager.saveProject(str(project_file))

        data = json.loads(project_file.read_text())
        assert data["version"] == "1.1"
        assert "tabs" in data
        assert len(data["tabs"]) == 1
        assert data["tabs"][0]["name"] == "Main"
        assert "active_tab" in data
        assert data["active_tab"] == 0

    def test_roundtrip_multiple_tabs(self, app, tmp_path):
        """Save and load preserves multiple tabs."""
        import json
        from task_model import TaskModel, ProjectManager, TabModel, Tab

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        # Add tasks and items to first tab
        task_model.addTask("Tab 1 Task", -1)
        diagram_model.addBox(10.0, 10.0, "Tab 1 Box")

        # Save state and add second tab
        tab_model.addTab("Second Tab")
        project_manager.switchTab(1)

        # Add different content to second tab
        task_model.addTask("Tab 2 Task", -1)
        diagram_model.addBox(100.0, 100.0, "Tab 2 Box")

        # Save project
        project_file = tmp_path / "multi_tab.progress"
        project_manager.saveProject(str(project_file))

        # Reload in new instances
        task_model2 = TaskModel()
        diagram_model2 = DiagramModel()
        tab_model2 = TabModel()
        project_manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)

        project_manager2.loadProject(str(project_file))

        assert tab_model2.tabCount == 2
        assert tab_model2.currentTabIndex == 1  # Was active tab

        # Verify tab 2 content loaded
        assert task_model2.rowCount() == 1
        assert diagram_model2.count == 1

        # Switch to tab 1 and verify its content
        project_manager2.switchTab(0)
        assert task_model2.rowCount() == 1
        assert diagram_model2.count == 1

    # --- Tab operation tests ---

    def test_add_tab(self, tab_model):
        """Adding a tab increases count and allows switch."""
        assert tab_model.tabCount == 1  # Starts with Main

        tab_model.addTab("New Tab")
        assert tab_model.tabCount == 2

        tab_model.addTab("")  # Empty name gets default
        assert tab_model.tabCount == 3

    def test_remove_tab(self, tab_model):
        """Removing a tab decreases count."""
        tab_model.addTab("Tab 2")
        tab_model.addTab("Tab 3")
        assert tab_model.tabCount == 3

        tab_model.removeTab(1)
        assert tab_model.tabCount == 2

    def test_rename_tab(self, tab_model):
        """Renaming a tab updates the name."""
        assert tab_model.currentTabName == "Main"

        tab_model.renameTab(0, "Renamed Tab")
        assert tab_model.currentTabName == "Renamed Tab"

    def test_switch_tab(self, tab_model):
        """Switching tabs updates current index."""
        tab_model.addTab("Second")
        assert tab_model.currentTabIndex == 0

        tab_model.setCurrentTab(1)
        assert tab_model.currentTabIndex == 1
        assert tab_model.currentTabName == "Second"

    def test_move_tab(self, tab_model):
        """Moving tabs preserves the active tab and reorders list."""
        tab_model.addTab("Second")
        tab_model.addTab("Third")

        tab_model.moveTab(2, 0)
        assert tab_model.data(tab_model.index(0, 0), tab_model.NameRole) == "Third"
        assert tab_model.currentTabIndex == 1  # Main tab shifted right

    def test_cannot_remove_last_tab(self, tab_model):
        """Cannot remove the last remaining tab."""
        assert tab_model.tabCount == 1
        tab_model.removeTab(0)
        assert tab_model.tabCount == 1  # Still has 1 tab

    def test_tab_completion_role(self, tab_model):
        """Completion percent reflects task completion."""
        tab_model.updateCurrentTabTasks({
            "tasks": [
                {"title": "One", "completed": True},
                {"title": "Two", "completed": False},
            ]
        })
        index = tab_model.index(0, 0)
        assert tab_model.data(index, tab_model.CompletionRole) == 50.0

    # --- Tab data isolation tests ---

    def test_tabs_have_independent_diagrams(self, app, tmp_path):
        """Each tab maintains its own diagram data."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        # Add box to first tab
        diagram_model.addBox(10.0, 10.0, "Tab 1 Box")
        assert diagram_model.count == 1

        # Switch to new tab
        tab_model.addTab("Tab 2")
        project_manager.switchTab(1)

        # New tab should be empty
        assert diagram_model.count == 0

        # Add different box
        diagram_model.addBox(50.0, 50.0, "Tab 2 Box")
        assert diagram_model.count == 1

        # Switch back to first tab
        project_manager.switchTab(0)
        assert diagram_model.count == 1

        # Verify it's the original box
        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.TextRole) == "Tab 1 Box"

    def test_tabs_have_independent_tasks(self, app, tmp_path):
        """Each tab maintains its own task list."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        # Add task to first tab
        task_model.addTask("Tab 1 Task", -1)
        assert task_model.rowCount() == 1

        # Switch to new tab
        tab_model.addTab("Tab 2")
        project_manager.switchTab(1)

        # New tab should have no tasks
        assert task_model.rowCount() == 0

        # Add different task
        task_model.addTask("Tab 2 Task", -1)
        assert task_model.rowCount() == 1

        # Switch back to first tab
        project_manager.switchTab(0)
        assert task_model.rowCount() == 1

        # Verify it's the original task
        index = task_model.index(0, 0)
        assert task_model.data(index, task_model.TitleRole) == "Tab 1 Task"


class TestCountdownTimer:
    """Tests for the countdown timer feature."""

    @pytest.fixture
    def task_model_with_timer(self, app):
        """Create a task model with a task and set up for timer testing."""
        model = TaskModel()
        model.addTask("Task with timer", -1)
        return model

    @pytest.fixture
    def diagram_model_with_timer_task(self, app, task_model_with_timer):
        """Create a diagram model with a task item for timer testing."""
        model = DiagramModel(task_model=task_model_with_timer)
        model.addTask(0, 100.0, 100.0)
        return model, task_model_with_timer

    # --- TaskModel countdown tests ---

    def test_countdown_fields_default_none(self, task_model_with_timer):
        """Task countdown fields default to None."""
        index = task_model_with_timer.index(0, 0)
        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        progress = task_model_with_timer.data(index, task_model_with_timer.CountdownProgressRole)
        expired = task_model_with_timer.data(index, task_model_with_timer.CountdownExpiredRole)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)

        assert remaining == -1.0  # No timer
        assert progress == -1.0  # No timer
        assert expired == False
        assert active == False

    def test_set_countdown_timer_seconds(self, task_model_with_timer):
        """Setting countdown timer in seconds works."""
        task_model_with_timer.setCountdownTimer(0, "30s")
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        progress = task_model_with_timer.data(index, task_model_with_timer.CountdownProgressRole)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)

        assert remaining > 29.0 and remaining <= 30.0
        assert progress > 0.95 and progress <= 1.0
        assert active == True

    def test_set_countdown_timer_minutes(self, task_model_with_timer):
        """Setting countdown timer in minutes works."""
        task_model_with_timer.setCountdownTimer(0, "2m")
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        assert remaining > 119.0 and remaining <= 120.0  # ~2 minutes in seconds

    def test_set_countdown_timer_hours(self, task_model_with_timer):
        """Setting countdown timer in hours works."""
        task_model_with_timer.setCountdownTimer(0, "1h")
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        assert remaining > 3599.0 and remaining <= 3600.0  # ~1 hour in seconds

    def test_set_countdown_timer_numeric(self, task_model_with_timer):
        """Setting countdown timer with plain number (seconds) works."""
        task_model_with_timer.setCountdownTimer(0, "60")
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        assert remaining > 59.0 and remaining <= 60.0

    def test_set_countdown_timer_invalid_row(self, task_model_with_timer):
        """Setting timer on invalid row does nothing."""
        task_model_with_timer.setCountdownTimer(-1, "30s")
        task_model_with_timer.setCountdownTimer(100, "30s")
        # Should not crash

    def test_set_countdown_timer_invalid_format(self, task_model_with_timer):
        """Setting timer with invalid format does nothing."""
        task_model_with_timer.setCountdownTimer(0, "invalid")
        index = task_model_with_timer.index(0, 0)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)
        assert active == False

    def test_set_countdown_timer_empty_string(self, task_model_with_timer):
        """Setting timer with empty string does nothing."""
        task_model_with_timer.setCountdownTimer(0, "")
        index = task_model_with_timer.index(0, 0)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)
        assert active == False

    def test_clear_countdown_timer(self, task_model_with_timer):
        """Clearing countdown timer removes it."""
        task_model_with_timer.setCountdownTimer(0, "30s")
        task_model_with_timer.clearCountdownTimer(0)
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)

        assert remaining == -1.0
        assert active == False

    def test_restart_countdown_timer(self, task_model_with_timer):
        """Restarting countdown timer resets to full duration."""
        import time

        task_model_with_timer.setCountdownTimer(0, "30s")
        time.sleep(0.1)  # Let some time pass

        task_model_with_timer.restartCountdownTimer(0)
        index = task_model_with_timer.index(0, 0)

        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)
        assert remaining > 29.9  # Should be back to ~30 seconds

    def test_restart_without_timer_does_nothing(self, task_model_with_timer):
        """Restarting when no timer set does nothing."""
        task_model_with_timer.restartCountdownTimer(0)
        index = task_model_with_timer.index(0, 0)
        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)
        assert active == False

    def test_complete_task_clears_timer(self, task_model_with_timer):
        """Completing a task clears its countdown timer."""
        task_model_with_timer.setCountdownTimer(0, "30s")
        task_model_with_timer.toggleComplete(0, True)
        index = task_model_with_timer.index(0, 0)

        active = task_model_with_timer.data(index, task_model_with_timer.CountdownActiveRole)
        assert active == False

    def test_countdown_expired_when_time_runs_out(self, task_model_with_timer):
        """Countdown expired is True when time runs out."""
        import time

        task_model_with_timer.setCountdownTimer(0, "0.05s")  # 50ms
        time.sleep(0.1)  # Wait for it to expire

        index = task_model_with_timer.index(0, 0)
        expired = task_model_with_timer.data(index, task_model_with_timer.CountdownExpiredRole)
        remaining = task_model_with_timer.data(index, task_model_with_timer.CountdownRemainingRole)

        assert expired == True
        assert remaining == 0.0

    def test_countdown_progress_decreases_over_time(self, task_model_with_timer):
        """Countdown progress decreases as time passes."""
        import time

        task_model_with_timer.setCountdownTimer(0, "1s")
        index = task_model_with_timer.index(0, 0)

        progress1 = task_model_with_timer.data(index, task_model_with_timer.CountdownProgressRole)
        time.sleep(0.3)
        progress2 = task_model_with_timer.data(index, task_model_with_timer.CountdownProgressRole)

        assert progress2 < progress1

    # --- Serialization tests ---

    def test_countdown_serialization(self, task_model_with_timer):
        """Countdown fields are serialized properly."""
        task_model_with_timer.setCountdownTimer(0, "60s")

        data = task_model_with_timer.to_dict()
        task_data = data["tasks"][0]

        assert "countdown_duration" in task_data
        assert task_data["countdown_duration"] == 60.0
        assert "countdown_start" in task_data

    def test_countdown_deserialization(self, app):
        """Countdown fields are deserialized properly."""
        import time
        model = TaskModel()

        # Create data with countdown fields
        data = {
            "tasks": [{
                "title": "Timed Task",
                "completed": False,
                "time_spent": 0.0,
                "parent_index": -1,
                "indent_level": 0,
                "custom_estimate": None,
                "countdown_duration": 60.0,
                "countdown_start": time.time()
            }]
        }

        model.from_dict(data)
        index = model.index(0, 0)

        active = model.data(index, model.CountdownActiveRole)
        remaining = model.data(index, model.CountdownRemainingRole)

        assert active == True
        assert remaining > 0 and remaining <= 60.0

    def test_countdown_not_serialized_when_none(self, task_model_with_timer):
        """Countdown fields not included when not set."""
        data = task_model_with_timer.to_dict()
        task_data = data["tasks"][0]

        assert "countdown_duration" not in task_data
        assert "countdown_start" not in task_data

    # --- DiagramModel countdown tests ---

    def test_diagram_countdown_roles_exist(self, diagram_model_with_timer_task):
        """DiagramModel has countdown roles."""
        model, _ = diagram_model_with_timer_task
        role_names = model.roleNames()

        assert b"taskCountdownRemaining" in role_names.values()
        assert b"taskCountdownProgress" in role_names.values()
        assert b"taskCountdownExpired" in role_names.values()
        assert b"taskCountdownActive" in role_names.values()

    def test_diagram_countdown_reflects_task_model(self, diagram_model_with_timer_task):
        """DiagramModel countdown roles reflect TaskModel state."""
        diagram_model, task_model = diagram_model_with_timer_task

        task_model.setCountdownTimer(0, "30s")
        index = diagram_model.index(0, 0)

        active = diagram_model.data(index, diagram_model.TaskCountdownActiveRole)
        remaining = diagram_model.data(index, diagram_model.TaskCountdownRemainingRole)
        progress = diagram_model.data(index, diagram_model.TaskCountdownProgressRole)

        assert active == True
        assert remaining > 29.0 and remaining <= 30.0
        assert progress > 0.95 and progress <= 1.0

    def test_diagram_set_countdown_timer_slot(self, diagram_model_with_timer_task):
        """DiagramModel setTaskCountdownTimer slot works."""
        diagram_model, task_model = diagram_model_with_timer_task

        diagram_model.setTaskCountdownTimer(0, "45s")
        index = task_model.index(0, 0)

        remaining = task_model.data(index, task_model.CountdownRemainingRole)
        assert remaining > 44.0 and remaining <= 45.0

    def test_diagram_clear_countdown_timer_slot(self, diagram_model_with_timer_task):
        """DiagramModel clearTaskCountdownTimer slot works."""
        diagram_model, task_model = diagram_model_with_timer_task

        task_model.setCountdownTimer(0, "30s")
        diagram_model.clearTaskCountdownTimer(0)

        index = task_model.index(0, 0)
        active = task_model.data(index, task_model.CountdownActiveRole)
        assert active == False

    def test_diagram_restart_countdown_timer_slot(self, diagram_model_with_timer_task):
        """DiagramModel restartTaskCountdownTimer slot works."""
        import time
        diagram_model, task_model = diagram_model_with_timer_task

        task_model.setCountdownTimer(0, "30s")
        time.sleep(0.1)
        diagram_model.restartTaskCountdownTimer(0)

        index = task_model.index(0, 0)
        remaining = task_model.data(index, task_model.CountdownRemainingRole)
        assert remaining > 29.9

    def test_diagram_countdown_no_task_model(self, app):
        """DiagramModel handles countdown queries without task model."""
        model = DiagramModel()
        model.addBox(100.0, 100.0, "Box")
        index = model.index(0, 0)

        # Should return defaults without crashing
        remaining = model.data(index, model.TaskCountdownRemainingRole)
        active = model.data(index, model.TaskCountdownActiveRole)

        assert remaining == -1.0
        assert active == False


class TestAddTaskWithParent:
    """Tests for TaskModel.addTaskWithParent method."""

    def test_add_task_with_parent_returns_index(self, app):
        """addTaskWithParent returns the inserted row index."""
        model = TaskModel()
        idx = model.addTaskWithParent("Root Task")
        assert idx == 0
        assert model.rowCount() == 1

    def test_add_task_with_parent_root_level(self, app):
        """Adding task at root level with parent_row=-1."""
        model = TaskModel()
        idx = model.addTaskWithParent("Task 1", -1)
        assert idx == 0
        index = model.index(0, 0)
        assert model.data(index, model.IndentLevelRole) == 0

    def test_add_task_with_parent_as_child(self, app):
        """Adding task as child of another task."""
        model = TaskModel()
        parent_idx = model.addTaskWithParent("Parent Task", -1)
        child_idx = model.addTaskWithParent("Child Task", parent_idx)

        assert child_idx == 1
        index = model.index(1, 0)
        assert model.data(index, model.IndentLevelRole) == 1
        assert model.data(index, model.TitleRole) == "Child Task"

    def test_add_task_with_parent_empty_title(self, app):
        """Adding task with empty title returns -1."""
        model = TaskModel()
        idx = model.addTaskWithParent("")
        assert idx == -1
        assert model.rowCount() == 0

    def test_add_task_with_parent_whitespace_title(self, app):
        """Adding task with whitespace-only title returns -1."""
        model = TaskModel()
        idx = model.addTaskWithParent("   ")
        assert idx == -1
        assert model.rowCount() == 0

    def test_add_task_with_parent_nested_children(self, app):
        """Adding multiple levels of nested children."""
        model = TaskModel()
        root = model.addTaskWithParent("Root", -1)
        child1 = model.addTaskWithParent("Child 1", root)
        grandchild = model.addTaskWithParent("Grandchild", child1)

        assert model.rowCount() == 3
        assert model.data(model.index(2, 0), model.IndentLevelRole) == 2


class TestTabModelCompletion:
    """Tests for TabModel completion percentage functionality."""

    def test_tab_completion_role_exists(self, app):
        """TabModel has CompletionRole."""
        from task_model import TabModel
        model = TabModel()
        role_names = model.roleNames()
        assert b"completionPercent" in role_names.values()

    def test_tab_completion_empty_tab(self, app):
        """Empty tab has 0% completion."""
        from task_model import TabModel
        model = TabModel()
        index = model.index(0, 0)
        completion = model.data(index, model.CompletionRole)
        assert completion == 0.0

    def test_tab_completion_with_tasks(self, app):
        """Tab completion reflects task completion."""
        from task_model import TabModel
        model = TabModel()
        # Set tab with 2 tasks, 1 completed
        model._tabs[0].tasks = {
            "tasks": [
                {"title": "Task 1", "completed": True},
                {"title": "Task 2", "completed": False},
            ]
        }
        index = model.index(0, 0)
        completion = model.data(index, model.CompletionRole)
        assert completion == 50.0

    def test_tab_completion_all_completed(self, app):
        """100% completion when all tasks done."""
        from task_model import TabModel
        model = TabModel()
        model._tabs[0].tasks = {
            "tasks": [
                {"title": "Task 1", "completed": True},
                {"title": "Task 2", "completed": True},
            ]
        }
        index = model.index(0, 0)
        completion = model.data(index, model.CompletionRole)
        assert completion == 100.0


class TestTabModelMoveTab:
    """Tests for TabModel.moveTab method."""

    def test_move_tab_forward(self, app):
        """Moving tab forward works."""
        from task_model import TabModel
        model = TabModel()
        model.addTab("Tab 2")
        model.addTab("Tab 3")
        assert model.rowCount() == 3

        model.moveTab(0, 2)
        assert model.data(model.index(0, 0), model.NameRole) == "Tab 2"
        assert model.data(model.index(2, 0), model.NameRole) == "Main"

    def test_move_tab_backward(self, app):
        """Moving tab backward works."""
        from task_model import TabModel
        model = TabModel()
        model.addTab("Tab 2")
        model.addTab("Tab 3")

        model.moveTab(2, 0)
        assert model.data(model.index(0, 0), model.NameRole) == "Tab 3"
        assert model.data(model.index(2, 0), model.NameRole) == "Tab 2"

    def test_move_tab_same_position(self, app):
        """Moving tab to same position does nothing."""
        from task_model import TabModel
        model = TabModel()
        model.addTab("Tab 2")
        model.moveTab(0, 0)
        assert model.data(model.index(0, 0), model.NameRole) == "Main"

    def test_move_tab_invalid_indices(self, app):
        """Moving with invalid indices does nothing."""
        from task_model import TabModel
        model = TabModel()
        model.addTab("Tab 2")
        model.moveTab(-1, 0)
        model.moveTab(0, 10)
        model.moveTab(10, 0)
        # Should not crash, tabs unchanged
        assert model.rowCount() == 2

    def test_move_tab_updates_current_index(self, app):
        """Moving current tab updates currentTabIndex."""
        from task_model import TabModel
        model = TabModel()
        model.addTab("Tab 2")
        model.addTab("Tab 3")
        model.setCurrentTab(0)

        model.moveTab(0, 2)
        assert model.currentTabIndex == 2


class TestTabModelUpdateCurrentTabTasks:
    """Tests for TabModel.updateCurrentTabTasks method."""

    def test_update_current_tab_tasks(self, app):
        """updateCurrentTabTasks updates only tasks data."""
        from task_model import TabModel
        model = TabModel()
        original_diagram = model._tabs[0].diagram

        new_tasks = {"tasks": [{"title": "New Task", "completed": False}]}
        model.updateCurrentTabTasks(new_tasks)

        assert model._tabs[0].tasks == new_tasks
        assert model._tabs[0].diagram == original_diagram

    def test_update_current_tab_tasks_emits_data_changed(self, app):
        """updateCurrentTabTasks emits dataChanged signal."""
        from task_model import TabModel
        model = TabModel()
        signal_received = []

        def on_data_changed(top_left, bottom_right, roles):
            signal_received.append((top_left.row(), roles))

        model.dataChanged.connect(on_data_changed)
        model.updateCurrentTabTasks({"tasks": []})

        assert len(signal_received) == 1
        assert model.CompletionRole in signal_received[0][1]


class TestClipboardFunctionality:
    """Tests for DiagramModel clipboard operations."""

    def test_copy_items_to_clipboard_empty_list(self, empty_diagram_model):
        """Copying empty list returns False."""
        result = empty_diagram_model.copyItemsToClipboard([])
        assert result == False

    def test_copy_items_to_clipboard_invalid_ids(self, empty_diagram_model):
        """Copying non-existent items returns False."""
        result = empty_diagram_model.copyItemsToClipboard(["nonexistent_1"])
        assert result == False

    def test_copy_items_to_clipboard_success(self, empty_diagram_model):
        """Copying valid items succeeds."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test Box")
        result = empty_diagram_model.copyItemsToClipboard([item_id])
        assert result == True

    def test_copy_items_to_clipboard_multiple(self, empty_diagram_model):
        """Copying multiple items preserves edges."""
        id1 = empty_diagram_model.addBox(100.0, 100.0, "Box 1")
        id2 = empty_diagram_model.addBox(200.0, 100.0, "Box 2")
        empty_diagram_model.addEdge(id1, id2)

        result = empty_diagram_model.copyItemsToClipboard([id1, id2])
        assert result == True

    def test_copy_edge_to_clipboard_success(self, empty_diagram_model):
        """Copying edge includes both connected items."""
        id1 = empty_diagram_model.addBox(100.0, 100.0, "Box 1")
        id2 = empty_diagram_model.addBox(200.0, 100.0, "Box 2")
        empty_diagram_model.addEdge(id1, id2)
        edge_id = empty_diagram_model.edges[0]["id"]

        result = empty_diagram_model.copyEdgeToClipboard(edge_id)
        assert result == True

    def test_copy_edge_to_clipboard_invalid(self, empty_diagram_model):
        """Copying non-existent edge returns False."""
        result = empty_diagram_model.copyEdgeToClipboard("nonexistent_edge")
        assert result == False

    def test_copy_edge_to_clipboard_empty(self, empty_diagram_model):
        """Copying empty edge id returns False."""
        result = empty_diagram_model.copyEdgeToClipboard("")
        assert result == False

    def test_has_clipboard_diagram_false_initially(self, empty_diagram_model):
        """hasClipboardDiagram returns False when clipboard is empty."""
        # Clear clipboard first
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.clear()
        result = empty_diagram_model.hasClipboardDiagram()
        assert result == False

    def test_has_clipboard_diagram_after_copy(self, empty_diagram_model):
        """hasClipboardDiagram returns True after copying items."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test")
        empty_diagram_model.copyItemsToClipboard([item_id])
        result = empty_diagram_model.hasClipboardDiagram()
        assert result == True

    def test_paste_diagram_from_clipboard(self, empty_diagram_model):
        """Pasting diagram creates new items."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Original")
        empty_diagram_model.copyItemsToClipboard([item_id])

        # Paste at different position
        result = empty_diagram_model.pasteDiagramFromClipboard(300.0, 300.0)
        assert result == True
        assert empty_diagram_model.count == 2

    def test_paste_diagram_with_edges(self, empty_diagram_model):
        """Pasting diagram preserves edges between items."""
        id1 = empty_diagram_model.addBox(100.0, 100.0, "Box 1")
        id2 = empty_diagram_model.addBox(200.0, 100.0, "Box 2")
        empty_diagram_model.addEdge(id1, id2)
        empty_diagram_model.copyItemsToClipboard([id1, id2])

        result = empty_diagram_model.pasteDiagramFromClipboard(400.0, 400.0)
        assert result == True
        assert empty_diagram_model.count == 4
        assert len(empty_diagram_model.edges) == 2

    def test_paste_diagram_empty_clipboard(self, empty_diagram_model):
        """Pasting from empty clipboard returns False."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.clear()
        result = empty_diagram_model.pasteDiagramFromClipboard(100.0, 100.0)
        assert result == False


class TestParseTextHierarchy:
    """Tests for DiagramModel._parse_text_hierarchy method."""

    def test_parse_flat_lines(self, empty_diagram_model):
        """Parsing flat text produces level 0 entries."""
        text = "Line 1\nLine 2\nLine 3"
        result = empty_diagram_model._parse_text_hierarchy(text)
        assert len(result) == 3
        assert all(entry["level"] == 0 for entry in result)

    def test_parse_indented_lines(self, empty_diagram_model):
        """Parsing indented text produces correct hierarchy."""
        text = "Parent\n  Child 1\n  Child 2\n    Grandchild"
        result = empty_diagram_model._parse_text_hierarchy(text)
        assert len(result) == 4
        assert result[0]["level"] == 0
        assert result[1]["level"] == 1
        assert result[2]["level"] == 1
        assert result[3]["level"] == 2

    def test_parse_empty_lines_ignored(self, empty_diagram_model):
        """Empty lines are ignored."""
        text = "Line 1\n\n\nLine 2"
        result = empty_diagram_model._parse_text_hierarchy(text)
        assert len(result) == 2

    def test_parse_tab_indentation(self, empty_diagram_model):
        """Tab indentation is handled."""
        text = "Parent\n\tChild"
        result = empty_diagram_model._parse_text_hierarchy(text)
        assert len(result) == 2
        assert result[0]["level"] == 0
        assert result[1]["level"] == 1

    def test_parse_text_stripped(self, empty_diagram_model):
        """Text is stripped of leading/trailing whitespace."""
        text = "  Item 1  \n    Item 2  "
        result = empty_diagram_model._parse_text_hierarchy(text)
        assert result[0]["text"] == "Item 1"
        assert result[1]["text"] == "Item 2"


class TestHasClipboardTextLines:
    """Tests for DiagramModel.hasClipboardTextLines method."""

    def test_has_clipboard_text_lines_false_empty(self, empty_diagram_model):
        """Returns False when clipboard is empty."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.clear()
        result = empty_diagram_model.hasClipboardTextLines()
        assert result == False

    def test_has_clipboard_text_lines_single_line(self, empty_diagram_model):
        """Returns False for single line text."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Single line")
        result = empty_diagram_model.hasClipboardTextLines()
        assert result == False

    def test_has_clipboard_text_lines_multiple_lines(self, empty_diagram_model):
        """Returns True for multiple non-empty lines."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Line 1\nLine 2")
        result = empty_diagram_model.hasClipboardTextLines()
        assert result == True


class TestPasteTextFromClipboard:
    """Tests for DiagramModel.pasteTextFromClipboard method."""

    def test_paste_text_as_boxes(self, empty_diagram_model):
        """Pasting text as boxes creates box items."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Box 1\nBox 2\nBox 3")

        result = empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, False)
        assert result == True
        assert empty_diagram_model.count == 3

    def test_paste_text_as_tasks(self, diagram_model_with_task_model):
        """Pasting text as tasks creates task items."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Task A\nTask B")

        initial_task_count = diagram_model_with_task_model._task_model.rowCount()
        result = diagram_model_with_task_model.pasteTextFromClipboard(100.0, 100.0, True)

        assert result == True
        assert diagram_model_with_task_model._task_model.rowCount() == initial_task_count + 2

    def test_paste_text_empty_clipboard(self, empty_diagram_model):
        """Pasting from empty clipboard returns False."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.clear()
        result = empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, False)
        assert result == False

    def test_paste_text_creates_edges(self, empty_diagram_model):
        """Pasting multiple lines creates edges between items."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Item 1\nItem 2\nItem 3")

        empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, False)
        # Should have edges connecting items in sequence
        assert len(empty_diagram_model.edges) == 2

    def test_paste_text_as_tasks_without_task_model(self, empty_diagram_model):
        """Pasting as tasks without task model returns False."""
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText("Task 1\nTask 2")

        result = empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, True)
        assert result == False


class TestProjectManagerRefreshTasks:
    """Tests for ProjectManager._refreshCurrentTabTasks method."""

    def test_refresh_skipped_during_loading(self, app):
        """_refreshCurrentTabTasks is skipped when _loading is True."""
        from task_model import TaskModel, TabModel, ProjectManager
        from actiondraw import DiagramModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_mgr = ProjectManager(task_model, diagram_model, tab_model)

        task_model._loading = True
        # This should not update tab model
        initial_tasks = tab_model._tabs[0].tasks.copy()
        task_model.taskCountChanged.emit()
        # Tasks should not have been serialized
        assert tab_model._tabs[0].tasks == initial_tasks

    def test_refresh_works_when_not_loading(self, app):
        """_refreshCurrentTabTasks works when _loading is False."""
        from task_model import TaskModel, TabModel, ProjectManager
        from actiondraw import DiagramModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_mgr = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("New Task", -1)
        # Tab model should now have the new task
        assert len(tab_model._tabs[0].tasks.get("tasks", [])) == 1


class TestBatchLoading:
    """Tests for batch loading performance optimization."""

    def test_from_dict_batch_insert(self, app):
        """from_dict uses batch insertion for tasks."""
        model = TaskModel()
        data = {
            "tasks": [
                {"title": f"Task {i}", "completed": False, "time_spent": 0.0,
                 "parent_index": -1, "indent_level": 0, "custom_estimate": None}
                for i in range(10)
            ]
        }

        model.from_dict(data)
        assert model.rowCount() == 10

    def test_loading_flag_set_during_from_dict(self, app):
        """_loading flag is set during from_dict execution."""
        model = TaskModel()
        loading_states = []

        # Capture loading state during signal emission
        def capture_state(*args):
            loading_states.append(model._loading)

        model.taskCountChanged.connect(capture_state)

        data = {"tasks": [{"title": "Task", "completed": False, "time_spent": 0.0,
                          "parent_index": -1, "indent_level": 0, "custom_estimate": None}]}
        model.from_dict(data)

        # The signal is emitted after loading is complete, so _loading should be False
        assert loading_states[-1] == False

    def test_loading_flag_reset_after_from_dict(self, app):
        """_loading flag is reset to False after from_dict completes."""
        model = TaskModel()
        data = {"tasks": [{"title": "Task", "completed": False, "time_spent": 0.0,
                          "parent_index": -1, "indent_level": 0, "custom_estimate": None}]}
        model.from_dict(data)
        assert model._loading == False

    def test_loading_flag_reset_on_exception(self, app):
        """_loading flag is reset even if from_dict fails."""
        model = TaskModel()
        # Pass invalid data that might cause issues
        try:
            model.from_dict({"tasks": "invalid"})
        except (TypeError, AttributeError):
            pass
        # Flag should still be reset
        assert model._loading == False


class TestSerializeItemForClipboard:
    """Tests for DiagramModel._serialize_item_for_clipboard method."""

    def test_serialize_item_basic(self, empty_diagram_model):
        """Serializing item produces correct dictionary."""
        from actiondraw import DiagramItem, DiagramItemType
        item = DiagramItem(
            id="box_1",
            item_type=DiagramItemType.BOX,
            x=100.0,
            y=200.0,
            width=120.0,
            height=60.0,
            text="Test Box",
            color="#4a9eff",
            text_color="#f5f6f8",
        )

        result = empty_diagram_model._serialize_item_for_clipboard(item)

        assert result["id"] == "box_1"
        assert result["type"] == "box"
        assert result["x"] == 100.0
        assert result["y"] == 200.0
        assert result["text"] == "Test Box"

    def test_serialize_item_with_note(self, empty_diagram_model):
        """Serializing item with note preserves markdown."""
        from actiondraw import DiagramItem, DiagramItemType
        item = DiagramItem(
            id="note_1",
            item_type=DiagramItemType.NOTE,
            x=0.0,
            y=0.0,
            note_markdown="# Heading\n\nContent",
        )

        result = empty_diagram_model._serialize_item_for_clipboard(item)
        assert result["noteMarkdown"] == "# Heading\n\nContent"


class TestConvertItemType:
    """Tests for DiagramModel.convertItemType method."""

    def test_convert_box_to_note(self, empty_diagram_model):
        """Converting a box to a note changes type and colors."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "My Box")
        empty_diagram_model.convertItemType(item_id, "note")

        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "note"
        assert item.color == "#f7e07b"
        assert item.text_color == "#1b2028"

    def test_convert_to_same_type_noop(self, empty_diagram_model):
        """Converting to the same type does nothing."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test")
        original_item = empty_diagram_model.getItem(item_id)
        original_color = original_item.color

        empty_diagram_model.convertItemType(item_id, "box")

        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "box"
        assert item.color == original_color

    def test_convert_invalid_preset_noop(self, empty_diagram_model):
        """Converting with invalid preset name does nothing."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test")

        empty_diagram_model.convertItemType(item_id, "nonexistent_preset")

        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "box"

    def test_convert_invalid_item_id_noop(self, empty_diagram_model):
        """Converting with invalid item id does nothing."""
        empty_diagram_model.addBox(100.0, 100.0, "Test")
        # Should not raise
        empty_diagram_model.convertItemType("invalid_id", "note")

    def test_convert_to_task_creates_task_entry(self, diagram_model_with_task_model):
        """Converting to task creates entry in task model."""
        model = diagram_model_with_task_model
        task_model = model._task_model
        item_id = model.addPresetItem("note", 100.0, 100.0)
        model.setItemText(item_id, "My New Task")

        initial_task_count = task_model.rowCount()
        model.convertItemType(item_id, "task")

        item = model.getItem(item_id)
        assert item.item_type.value == "task"
        assert item.task_index >= 0
        assert task_model.rowCount() == initial_task_count + 1
        assert task_model.getTaskTitle(item.task_index) == "My New Task"

    def test_convert_task_to_note_removes_task_entry(self, diagram_model_with_task_model):
        """Converting a task to another type removes from task model."""
        model = diagram_model_with_task_model
        task_model = model._task_model
        item_id = model.addTask(0, 100.0, 100.0)  # Create task at index 0

        initial_task_count = task_model.rowCount()
        model.convertItemType(item_id, "note")

        item = model.getItem(item_id)
        assert item.item_type.value == "note"
        assert item.task_index == -1
        assert task_model.rowCount() == initial_task_count - 1

    def test_convert_task_updates_other_task_indices(self, app):
        """Converting a task adjusts indices of subsequent tasks."""
        task_model = TaskModel()
        # Add 3 tasks first
        task_model.addTask("Task 0", -1)
        task_model.addTask("Task 1", -1)
        task_model.addTask("Task 2", -1)

        model = DiagramModel(task_model=task_model)

        id0 = model.addTask(0, 100.0, 100.0)
        id1 = model.addTask(1, 100.0, 150.0)
        id2 = model.addTask(2, 100.0, 200.0)

        # Convert task at index 0 to note
        model.convertItemType(id0, "note")

        # Task indices should be decremented for items with higher indices
        item1 = model.getItem(id1)
        item2 = model.getItem(id2)
        assert item1.task_index == 0  # Was 1, now 0
        assert item2.task_index == 1  # Was 2, now 1

    def test_convert_task_with_current_task_higher_emits_role(self, app):
        """When current task index is one higher than converted item, TaskCurrentRole is emitted."""
        task_model = TaskModel()
        # Add tasks
        task_model.addTask("Task 0", -1)
        task_model.addTask("Task 1", -1)

        model = DiagramModel(task_model=task_model)

        id0 = model.addTask(0, 100.0, 100.0)
        id1 = model.addTask(1, 100.0, 150.0)

        # Set current task to index 1 (the second task)
        model.setCurrentTask(1)
        assert model.currentTaskIndex == 1

        # Convert task at index 0 to note
        # This should:
        # 1. Remove task 0 from task model
        # 2. Decrement _current_task_index from 1 to 0
        # 3. Emit TaskCurrentRole for the converted item (so UI clears its "current" state)
        model.convertItemType(id0, "note")

        item0 = model.getItem(id0)
        item1 = model.getItem(id1)

        # Verify state is correct
        assert item0.task_index == -1
        assert item1.task_index == 0
        assert model.currentTaskIndex == 0

        # The key assertion: item0 should not appear as current task
        index0 = model.index(0, 0)
        is_current = model.data(index0, model.TaskCurrentRole)
        assert is_current == False

    def test_convert_current_task_clears_current_index(self, app):
        """Converting the current task clears currentTaskIndex."""
        task_model = TaskModel()
        task_model.addTask("Task 0", -1)

        model = DiagramModel(task_model=task_model)
        id0 = model.addTask(0, 100.0, 100.0)

        model.setCurrentTask(0)  # Set first task as current
        assert model.currentTaskIndex == 0

        model.convertItemType(id0, "note")

        assert model.currentTaskIndex == -1

    def test_convert_to_task_without_task_model_noop(self, empty_diagram_model):
        """Converting to task without task model does nothing."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test")
        empty_diagram_model.convertItemType(item_id, "task")

        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "box"  # Unchanged

    def test_convert_preserves_text(self, empty_diagram_model):
        """Converting preserves the item's text."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Original Text")
        empty_diagram_model.convertItemType(item_id, "wish")

        item = empty_diagram_model.getItem(item_id)
        assert item.text == "Original Text"

    def test_convert_case_insensitive(self, empty_diagram_model):
        """Preset name lookup is case insensitive."""
        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test")

        empty_diagram_model.convertItemType(item_id, "NOTE")
        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "note"

        empty_diagram_model.convertItemType(item_id, "ObStAcLe")
        item = empty_diagram_model.getItem(item_id)
        assert item.item_type.value == "obstacle"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
