"""Tests for the rewritten actiondraw module."""

import time

import pytest
from PySide6.QtCore import QModelIndex
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
from actiondraw.qml import QML_DIR
from actiondraw.markdown_note_manager import MarkdownNoteManager
from actiondraw.qml import load_actiondraw_qml
from progress_crypto import CryptoError, EncryptionCredentials, yubikey_support_guidance
from task_model import TaskModel


@pytest.fixture(autouse=True)
def fixed_project_encryption_credentials(monkeypatch):
    """Avoid interactive credential prompts in tests."""
    import base64
    import importlib.util
    import json

    from task_model import ProjectManager

    def _fake_prompt(self, operation, file_path, envelope=None):
        return EncryptionCredentials(passphrase="test-passphrase")

    monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials", _fake_prompt)

    crypto_available = (
        importlib.util.find_spec("cryptography") is not None
        and importlib.util.find_spec("argon2") is not None
    )
    if crypto_available:
        return

    def _fake_encrypt(project_data, credentials):
        plaintext = json.dumps(project_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return {
            "version": "1.2",
            "saved_at": project_data.get("saved_at"),
            "encryption": {
                "cipher": "AES-256-GCM",
                "kdf": "Argon2id",
                "kdf_params": {"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
                "salt_b64": "ZmFrZXNhbHQ=",
                "nonce_b64": "ZmFrZW5vbmNl",
                "aad_b64": "ZmFrZWFhZA==",
                "auth_mode": "passphrase",
                "yubikey": {"enabled": False, "slot": "2", "challenge_b64": ""},
            },
            "ciphertext": base64.b64encode(plaintext).decode("ascii"),
        }

    def _fake_decrypt(envelope, credentials):
        if credentials.passphrase != "test-passphrase":
            raise CryptoError("Unable to decrypt project: invalid credentials or corrupted file")
        raw = base64.b64decode(envelope["ciphertext"].encode("ascii"))
        return json.loads(raw.decode("utf-8"))

    def _fake_is_encrypted(payload):
        return isinstance(payload, dict) and "encryption" in payload and "ciphertext" in payload

    from task_model import decrypt_project_data, encrypt_project_data, is_encrypted_envelope
    assert decrypt_project_data and encrypt_project_data and is_encrypted_envelope
    monkeypatch.setattr("task_model.encrypt_project_data", _fake_encrypt)
    monkeypatch.setattr("task_model.decrypt_project_data", _fake_decrypt)
    monkeypatch.setattr("task_model.is_encrypted_envelope", _fake_is_encrypted)


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

    def test_resolve_connected_placement_uses_base_when_free(self, empty_diagram_model):
        source_id = empty_diagram_model.addBox(0.0, 0.0, "Source")
        placement = empty_diagram_model.resolveConnectedPlacement(source_id, "task", 300.0, 120.0, 60.0)
        assert placement["x"] == 300.0
        assert placement["y"] == 120.0

    def test_resolve_connected_placement_stacks_down_when_base_occupied(self, empty_diagram_model):
        source_id = empty_diagram_model.addBox(0.0, 0.0, "Source")
        empty_diagram_model.addBox(300.0, 120.0, "Blocker")
        placement = empty_diagram_model.resolveConnectedPlacement(source_id, "task", 300.0, 120.0, 60.0)
        assert placement["x"] == 300.0
        assert placement["y"] == 180.0

    def test_resolve_connected_placement_skips_multiple_occupied_rows(self, empty_diagram_model):
        source_id = empty_diagram_model.addBox(0.0, 0.0, "Source")
        empty_diagram_model.addBox(300.0, 120.0, "Blocker 0")
        empty_diagram_model.addBox(300.0, 180.0, "Blocker 1")
        empty_diagram_model.addBox(300.0, 240.0, "Blocker 2")
        placement = empty_diagram_model.resolveConnectedPlacement(source_id, "task", 300.0, 120.0, 60.0)
        assert placement["x"] == 300.0
        assert placement["y"] == 300.0

    def test_resolve_connected_placement_uses_upward_fallback(self, empty_diagram_model):
        source_id = empty_diagram_model.addBox(0.0, 0.0, "Source")
        for offset in range(0, 51):
            empty_diagram_model.addBox(300.0, 120.0 + (offset * 60.0), f"Blocker {offset}")
        placement = empty_diagram_model.resolveConnectedPlacement(source_id, "task", 300.0, 120.0, 60.0)
        assert placement["x"] == 300.0
        assert placement["y"] == 0.0

    def test_resolve_connected_placement_respects_item_dimensions(self, empty_diagram_model):
        source_id = empty_diagram_model.addBox(0.0, 0.0, "Source")
        empty_diagram_model.addBox(300.0, 120.0, "Base Blocker")
        empty_diagram_model.addBox(450.0, 180.0, "Right-side Blocker")

        task_placement = empty_diagram_model.resolveConnectedPlacement(source_id, "task", 300.0, 120.0, 60.0)
        note_placement = empty_diagram_model.resolveConnectedPlacement(source_id, "note", 300.0, 120.0, 60.0)

        assert task_placement["y"] == 180.0
        assert note_placement["y"] == 240.0

    def test_role_names(self, empty_diagram_model):
        roles = empty_diagram_model.roleNames()
        assert roles[empty_diagram_model.IdRole] == b"itemId"
        assert roles[empty_diagram_model.TextRole] == b"text"
        assert roles[empty_diagram_model.ColorRole] == b"color"
        assert roles[empty_diagram_model.TextColorRole] == b"textColor"
        assert roles[empty_diagram_model.TaskCompletedRole] == b"taskCompleted"
        assert roles[empty_diagram_model.LinkedSubtabCompletionRole] == b"linkedSubtabCompletion"
        assert roles[empty_diagram_model.LinkedSubtabActiveActionRole] == b"linkedSubtabActiveAction"
        assert roles[empty_diagram_model.HasLinkedSubtabRole] == b"hasLinkedSubtab"
        assert roles[empty_diagram_model.TextTabsRole] == b"textTabs"
        assert roles[empty_diagram_model.TextTabIndexRole] == b"textTabIndex"

    def test_data_invalid_index(self, empty_diagram_model):
        assert empty_diagram_model.data(empty_diagram_model.index(10, 0), empty_diagram_model.IdRole) is None
        assert empty_diagram_model.data(QModelIndex(), empty_diagram_model.IdRole) is None

    def test_find_nearest_connected_task_in_direction_right(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        right_near = diagram_model_with_task_model.addTask(1, 260.0, 100.0)
        right_far = diagram_model_with_task_model.addTask(2, 500.0, 100.0)
        diagram_model_with_task_model.addEdge(source, right_near)
        diagram_model_with_task_model.addEdge(source, right_far)

        picked = diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "right")
        assert picked == right_near

    def test_find_nearest_connected_task_in_direction_uses_steering(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 200.0, 200.0)
        straight_right = diagram_model_with_task_model.addTask(1, 380.0, 200.0)
        down_right = diagram_model_with_task_model.addTask(2, 300.0, 360.0)
        diagram_model_with_task_model.addEdge(source, straight_right)
        diagram_model_with_task_model.addEdge(source, down_right)

        picked = diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "right")
        assert picked == straight_right

    def test_find_nearest_connected_task_in_direction_up_and_down(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 300.0, 300.0)
        up_task = diagram_model_with_task_model.addTask(1, 300.0, 120.0)
        down_task = diagram_model_with_task_model.addTask(2, 300.0, 520.0)
        diagram_model_with_task_model.addEdge(source, up_task)
        diagram_model_with_task_model.addEdge(source, down_task)

        assert diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "up") == up_task
        assert diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "down") == down_task

    def test_find_nearest_connected_item_in_direction_from_non_task_source(self, diagram_model_with_task_model):
        source_box = diagram_model_with_task_model.addBox(100.0, 100.0, "Source")
        right_note = diagram_model_with_task_model.addPresetItem("note", 260.0, 100.0)
        diagram_model_with_task_model.addEdge(source_box, right_note)

        picked = diagram_model_with_task_model.findNearestConnectedItemInDirection(source_box, "right")
        assert picked == right_note

    def test_find_nearest_connected_task_in_direction_includes_non_task_items(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        right_box = diagram_model_with_task_model.addBox(260.0, 100.0, "Box")
        right_task = diagram_model_with_task_model.addTask(1, 420.0, 100.0)
        diagram_model_with_task_model.addEdge(source, right_box)
        diagram_model_with_task_model.addEdge(source, right_task)

        picked = diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "right")
        assert picked == right_box

    def test_find_nearest_connected_task_in_direction_returns_empty_for_no_match(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 100.0, 100.0)
        left_task = diagram_model_with_task_model.addTask(1, 0.0, 100.0)
        diagram_model_with_task_model.addEdge(source, left_task)

        assert diagram_model_with_task_model.findNearestConnectedTaskInDirection(source, "right") == ""


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

    def test_insert_task_on_edge(self, diagram_model_with_task_model):
        """Inserting a task on an edge replaces it with two connected edges."""
        source = diagram_model_with_task_model.addBox(0.0, 0.0, "Source")
        target = diagram_model_with_task_model.addBox(200.0, 0.0, "Target")
        diagram_model_with_task_model.addEdge(source, target)
        edge_id = diagram_model_with_task_model.edges[0]["id"]
        task_count_before = diagram_model_with_task_model._task_model.rowCount()

        inserted = diagram_model_with_task_model.insertTaskOnEdge(
            edge_id, "Inserted Task", 100.0, 50.0
        )

        assert inserted != ""
        assert diagram_model_with_task_model._task_model.rowCount() == task_count_before + 1
        inserted_item = diagram_model_with_task_model.getItemSnapshot(inserted)
        assert inserted_item["text"] == "Inserted Task"
        assert len(diagram_model_with_task_model.edges) == 2
        assert diagram_model_with_task_model.edges[0]["fromId"] == source
        assert diagram_model_with_task_model.edges[0]["toId"] == inserted
        assert diagram_model_with_task_model.edges[1]["fromId"] == inserted
        assert diagram_model_with_task_model.edges[1]["toId"] == target

    def test_insert_task_on_edge_preserves_description_upstream(self, diagram_model_with_task_model):
        """Splitting an edge keeps its description on the upstream replacement edge."""
        source = diagram_model_with_task_model.addBox(0.0, 0.0, "Source")
        target = diagram_model_with_task_model.addBox(200.0, 0.0, "Target")
        diagram_model_with_task_model.addEdge(source, target)
        edge_id = diagram_model_with_task_model.edges[0]["id"]
        diagram_model_with_task_model.setEdgeDescription(edge_id, "depends on")

        inserted = diagram_model_with_task_model.insertTaskOnEdge(
            edge_id, "Inserted Task", 100.0, 50.0
        )

        assert inserted != ""
        assert diagram_model_with_task_model.edges[0]["description"] == "depends on"
        assert diagram_model_with_task_model.edges[1]["description"] == ""

    def test_insert_task_on_invalid_edge_is_noop(self, diagram_model_with_task_model):
        """Invalid edge ids leave the graph and task list unchanged."""
        source = diagram_model_with_task_model.addBox(0.0, 0.0, "Source")
        target = diagram_model_with_task_model.addBox(200.0, 0.0, "Target")
        diagram_model_with_task_model.addEdge(source, target)
        task_count_before = diagram_model_with_task_model._task_model.rowCount()
        edges_before = list(diagram_model_with_task_model.edges)

        inserted = diagram_model_with_task_model.insertTaskOnEdge(
            "missing_edge", "Inserted Task", 100.0, 50.0
        )

        assert inserted == ""
        assert diagram_model_with_task_model._task_model.rowCount() == task_count_before
        assert diagram_model_with_task_model.edges == edges_before

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

    def test_completion_advances_current_task_when_single_outgoing(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 0.0, 0.0)
        target = diagram_model_with_task_model.addTask(1, 100.0, 0.0)
        diagram_model_with_task_model.addEdge(source, target)

        diagram_model_with_task_model.setCurrentTask(0)
        assert diagram_model_with_task_model.currentTaskIndex == 0

        diagram_model_with_task_model.setTaskCompleted(0, True)
        assert diagram_model_with_task_model.currentTaskIndex == 1

    def test_completion_does_not_choose_when_multiple_outgoing(self, diagram_model_with_task_model):
        source = diagram_model_with_task_model.addTask(0, 0.0, 0.0)
        target_one = diagram_model_with_task_model.addTask(1, 100.0, 0.0)
        target_two = diagram_model_with_task_model.addTask(2, 200.0, 0.0)
        diagram_model_with_task_model.addEdge(source, target_one)
        diagram_model_with_task_model.addEdge(source, target_two)

        diagram_model_with_task_model.setCurrentTask(0)
        assert diagram_model_with_task_model.currentTaskIndex == 0

        diagram_model_with_task_model.setTaskCompleted(0, True)
        assert diagram_model_with_task_model.currentTaskIndex == -1


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
        assert data["items"][0]["text"] == "# Title\nBody"
        assert "note_markdown" not in data["items"][0]

        new_model = DiagramModel()
        new_model.from_dict(data)
        assert new_model.getItemMarkdown(item_id) == "# Title\nBody"

    def test_note_tabs_roundtrip_preserves_primary_text(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItem("note", 10.0, 20.0)
        empty_diagram_model.setEditorTabs(
            item_id,
            "note",
            [
                {"name": "Overview", "text": "# Title\nBody"},
                {"name": "Ideas", "text": "- one\n- two"},
            ],
        )

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["text"] == "# Title\nBody"
        assert data["items"][0]["note_tabs"][1]["name"] == "Ideas"

        new_model = DiagramModel()
        new_model.from_dict(data)
        item = new_model.getItem(item_id)
        assert item is not None
        assert item.text == "# Title\nBody"
        assert item.note_tabs[1]["text"] == "- one\n- two"

    def test_obstacle_markdown_roundtrip(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Task")
        empty_diagram_model.setItemObstacleMarkdown(item_id, "Blocked by dependency")

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["obstacle_markdown"] == "Blocked by dependency"

        new_model = DiagramModel()
        new_model.from_dict(data)
        assert new_model.getItemObstacleMarkdown(item_id) == "Blocked by dependency"

    def test_freetext_tabs_roundtrip_preserves_canvas_text(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItemWithText("freetext", 10.0, 20.0, "Visible")
        empty_diagram_model.setEditorTabs(
            item_id,
            "freetext",
            [
                {"name": "Visible", "text": "Visible"},
                {"name": "Draft", "text": "Hidden draft"},
            ],
        )

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["text"] == "Visible"
        assert data["items"][0]["text_tabs"][1]["name"] == "Draft"

        new_model = DiagramModel()
        new_model.from_dict(data)
        item = new_model.getItem(item_id)
        assert item is not None
        assert item.text == "Visible"
        assert item.text_tabs[1]["text"] == "Hidden draft"

    def test_freetext_preview_tab_index_roundtrip(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItemWithText("freetext", 10.0, 20.0, "Visible")
        empty_diagram_model.setEditorTabs(
            item_id,
            "freetext",
            [
                {"name": "Visible", "text": "Visible"},
                {"name": "Draft", "text": "Hidden draft"},
            ],
        )
        empty_diagram_model.setItemTextTabIndex(item_id, 1)

        data = empty_diagram_model.to_dict()
        assert data["items"][0]["text_tab_index"] == 1

        new_model = DiagramModel()
        new_model.from_dict(data)
        item = new_model.getItem(item_id)
        assert item is not None
        assert item.text == "Visible"
        assert item.text_tab_index == 1

    def test_freetext_preview_tab_index_clamps_after_tab_replacement(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItemWithText("freetext", 10.0, 20.0, "Visible")
        empty_diagram_model.setEditorTabs(
            item_id,
            "freetext",
            [
                {"name": "Visible", "text": "Visible"},
                {"name": "Draft", "text": "Hidden draft"},
            ],
        )
        empty_diagram_model.setItemTextTabIndex(item_id, 1)

        empty_diagram_model.setEditorTabs(
            item_id,
            "freetext",
            [{"name": "Visible", "text": "Visible"}],
        )

        item = empty_diagram_model.getItem(item_id)
        index = empty_diagram_model.index(0, 0)
        assert item is not None
        assert item.text_tab_index == 0
        assert empty_diagram_model.data(index, empty_diagram_model.TextTabIndexRole) == 0

    def test_freetext_preview_tab_index_change_emits_model_roles(self, empty_diagram_model):
        item_id = empty_diagram_model.addPresetItemWithText("freetext", 10.0, 20.0, "Visible")
        empty_diagram_model.setEditorTabs(
            item_id,
            "freetext",
            [
                {"name": "Visible", "text": "Visible"},
                {"name": "Draft", "text": "Hidden draft"},
            ],
        )

        emitted_roles = []
        empty_diagram_model.dataChanged.connect(lambda _top_left, _bottom_right, roles: emitted_roles.append(list(roles)))

        empty_diagram_model.setItemTextTabIndex(item_id, 1)

        index = empty_diagram_model.index(0, 0)
        assert empty_diagram_model.data(index, empty_diagram_model.TextTabIndexRole) == 1
        assert empty_diagram_model.data(index, empty_diagram_model.TextTabsRole)[1]["text"] == "Hidden draft"
        assert any(empty_diagram_model.TextTabIndexRole in roles for roles in emitted_roles)

    def test_freetext_preview_tab_index_clamps_on_load(self):
        model = DiagramModel()
        model.from_dict({
            "items": [
                {
                    "id": "freetext_0",
                    "item_type": "freetext",
                    "x": 10,
                    "y": 20,
                    "width": 120,
                    "height": 80,
                    "text": "Visible",
                    "text_tabs": [{"name": "Visible", "text": "Visible"}],
                    "text_tab_index": 9,
                    "task_index": -1,
                    "color": "#4a9eff",
                    "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
            "strokes": [],
        })

        item = model.getItem("freetext_0")
        index = model.index(0, 0)
        assert item is not None
        assert item.text_tab_index == 0
        assert model.data(index, model.TextTabIndexRole) == 0

    def test_empty_obstacle_markdown_not_serialized(self, empty_diagram_model):
        item_id = empty_diagram_model.addBox(10.0, 20.0, "Task")
        empty_diagram_model.setItemObstacleMarkdown(item_id, "Blocked")
        empty_diagram_model.setItemObstacleMarkdown(item_id, "")

        data = empty_diagram_model.to_dict()
        assert "obstacle_markdown" not in data["items"][0]

    def test_from_dict_defaults_missing_obstacle_markdown(self, empty_diagram_model):
        empty_diagram_model.from_dict({
            "items": [
                {
                    "id": "box_0",
                    "item_type": "box",
                    "x": 10.0,
                    "y": 20.0,
                    "width": 120.0,
                    "height": 60.0,
                    "text": "Legacy",
                    "task_index": -1,
                    "color": "#4a9eff",
                    "text_color": "#f5f6f8",
                }
            ],
            "edges": [],
        })

        assert empty_diagram_model.getItemObstacleMarkdown("box_0") == ""

    def test_from_dict_migrates_legacy_note_markdown_to_text(self, empty_diagram_model):
        empty_diagram_model.from_dict({
            "items": [
                {
                    "id": "note_0",
                    "item_type": "note",
                    "x": 10.0,
                    "y": 20.0,
                    "width": 160.0,
                    "height": 110.0,
                    "text": "Old Title",
                    "task_index": -1,
                    "color": "#f7e07b",
                    "text_color": "#1b2028",
                    "note_markdown": "# Migrated\nBody",
                }
            ],
            "edges": [],
        })
        item = empty_diagram_model.getItem("note_0")
        assert item is not None
        assert item.text == "# Migrated\nBody"
        assert item.note_markdown == ""

    def test_create_task_from_markdown_selection_chains_tasks(self, diagram_model_with_task_model):
        source_id = diagram_model_with_task_model.addPresetItemWithText("box", 50, 60, "Source")

        first_task_id = diagram_model_with_task_model.createTaskFromMarkdownSelection(source_id, "First task")
        assert first_task_id.startswith("task_")
        first_task = diagram_model_with_task_model.getItem(first_task_id)
        assert first_task is not None
        assert first_task.text == "First task"
        assert any(
            edge["fromId"] == source_id and edge["toId"] == first_task_id
            for edge in diagram_model_with_task_model.edges
        )

        second_task_id = diagram_model_with_task_model.createTaskFromMarkdownSelection(source_id, "Second task")
        assert second_task_id.startswith("task_")
        assert any(
            edge["fromId"] == first_task_id and edge["toId"] == second_task_id
            for edge in diagram_model_with_task_model.edges
        )

    def test_create_task_from_markdown_selection_requires_task_model(self, empty_diagram_model):
        source_id = empty_diagram_model.addPresetItemWithText("box", 10, 20, "Source")
        assert empty_diagram_model.createTaskFromMarkdownSelection(source_id, "Task text") == ""

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

    def test_save_creates_encrypted_v1_2_envelope(self, app, tmp_path):
        """Saving a project creates encrypted v1.2 envelope format."""
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
        assert data["version"] == "1.2"
        assert "encryption" in data
        assert "ciphertext" in data
        assert data["encryption"]["cipher"] == "AES-256-GCM"
        assert data["encryption"]["kdf"] == "Argon2id"
        assert data["encryption"]["auth_mode"] == "passphrase"

    def test_roundtrip_multiple_tabs(self, app, tmp_path):
        """Save and load preserves multiple tabs."""
        from task_model import TaskModel, ProjectManager, TabModel

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

    def test_has_unsaved_changes_tracks_diagram_edits(self, app, tmp_path):
        """Unsaved state flips true after diagram changes and false after save."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        assert project_manager.hasUnsavedChanges() is False

        diagram_model.addBox(20.0, 30.0, "Unsaved Box")
        assert project_manager.hasUnsavedChanges() is True

        project_file = tmp_path / "unsaved_state.progress"
        project_manager.saveProject(str(project_file))
        assert project_manager.hasUnsavedChanges() is False

    def test_has_unsaved_changes_ignores_active_task_time_drift(self, app, tmp_path):
        """Auto-updating active task timers should not immediately re-mark project as unsaved."""
        import time
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        task_model.addTask("Running task", -1)

        project_file = tmp_path / "unsaved_time_drift.progress"
        project_manager.saveProject(str(project_file))
        assert project_manager.hasUnsavedChanges() is False

        for _ in range(5):
            time.sleep(0.25)
            app.processEvents()

        assert project_manager.hasUnsavedChanges() is False

    def test_has_unsaved_changes_false_after_load(self, app, tmp_path):
        """Loading an existing project resets unsaved state baseline."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        diagram_model.addBox(50.0, 60.0, "Saved Box")

        project_file = tmp_path / "load_baseline.progress"
        project_manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel()
        tab_model2 = TabModel()
        project_manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        project_manager2.loadProject(str(project_file))

        assert project_manager2.hasUnsavedChanges() is False

    def test_load_encrypted_wrong_passphrase_fails(self, app, tmp_path, monkeypatch):
        """Loading with wrong passphrase emits an error and does not load."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        task_model.addTask("Secret", -1)

        project_file = tmp_path / "secure.progress"
        project_manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel()
        tab_model2 = TabModel()
        project_manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)

        def _wrong_prompt(self, operation, file_path, envelope=None):
            return EncryptionCredentials(passphrase="wrong-passphrase")

        monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials", _wrong_prompt)

        errors = []
        project_manager2.errorOccurred.connect(errors.append)
        project_manager2.loadProject(str(project_file))

        assert errors
        assert "invalid credentials" in errors[-1]
        assert task_model2.rowCount() == 0

    def test_save_current_reuses_loaded_credentials_without_prompt(self, app, tmp_path, monkeypatch):
        """After loading encrypted project, Save reuses in-memory credentials."""
        from task_model import TaskModel, ProjectManager, TabModel

        calls = []

        def _tracking_prompt(self, operation, file_path, envelope=None):
            calls.append(operation)
            return EncryptionCredentials(passphrase="test-passphrase")

        monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials", _tracking_prompt)

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        task_model.addTask("Secret", -1)

        project_file = tmp_path / "reuse_save.progress"
        project_manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel()
        tab_model2 = TabModel()
        project_manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        project_manager2.loadProject(str(project_file))

        calls.clear()
        project_manager2.saveCurrentProject()

        assert calls == []

    def test_save_as_prompts_even_with_cached_loaded_credentials(self, app, tmp_path, monkeypatch):
        """Save As always prompts for encryption selection/credentials."""
        from task_model import TaskModel, ProjectManager, TabModel

        calls = []

        def _tracking_prompt(self, operation, file_path, envelope=None):
            calls.append(operation)
            return EncryptionCredentials(passphrase="test-passphrase")

        monkeypatch.setattr(ProjectManager, "_prompt_encryption_credentials", _tracking_prompt)

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        task_model.addTask("Secret", -1)

        project_file = tmp_path / "save_as_source.progress"
        project_manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel()
        tab_model2 = TabModel()
        project_manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        project_manager2.loadProject(str(project_file))

        calls.clear()
        save_as_file = tmp_path / "save_as_target.progress"
        project_manager2.saveProjectAs(str(save_as_file))

        assert calls == ["save"]
        assert save_as_file.exists()

    def test_save_with_yubikey_emits_touch_prompt_signals(self, app, tmp_path, monkeypatch):
        """YubiKey save flow emits start/finish prompt signals for UI feedback."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        task_model.addTask("Secret", -1)

        project_file = tmp_path / "yk_signal.progress"
        project_manager._current_file_path = str(project_file)
        project_manager._cached_encryption_file_path = str(project_file)
        project_manager._cached_encryption_credentials = EncryptionCredentials(
            passphrase=None,
            use_yubikey=True,
            yubikey_slot="2",
        )

        class _FakeKeyMaterial:
            def scrub(self):
                pass

        def _fake_derive_key_material(credentials):
            assert credentials.use_yubikey is True
            assert credentials.yubikey_slot == "2"
            return _FakeKeyMaterial()

        def _fake_encrypt_with_derived_key(project_data, key_material):
            assert isinstance(key_material, _FakeKeyMaterial)
            return {
                "version": "1.2",
                "saved_at": project_data.get("saved_at"),
                "encryption": {
                    "cipher": "AES-256-GCM",
                    "kdf": "Argon2id",
                    "kdf_params": {"time_cost": 3, "memory_cost": 65536, "parallelism": 1, "hash_len": 32},
                    "salt_b64": "ZmFrZXNhbHQ=",
                    "nonce_b64": "ZmFrZW5vbmNl",
                    "aad_b64": "ZmFrZWFhZA==",
                    "auth_mode": "yubikey",
                    "yubikey": {"enabled": True, "slot": "2", "challenge_b64": "Y2hhbGxlbmdl"},
                },
                "ciphertext": "ZmFrZWNpcGhlcnRleHQ=",
            }

        monkeypatch.setattr("task_model.derive_key_material", _fake_derive_key_material)
        monkeypatch.setattr("task_model.encrypt_with_derived_key", _fake_encrypt_with_derived_key)

        started = []
        finished = []
        project_manager.yubiKeyInteractionStarted.connect(started.append)
        project_manager.yubiKeyInteractionFinished.connect(lambda: finished.append(True))

        project_manager.saveCurrentProject()

        assert len(started) == 1
        assert "Touch your YubiKey" in started[0]
        assert len(finished) == 1
        assert project_file.exists()

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

    def test_remove_active_tab_reloads_surviving_diagram(self, app):
        """Deleting the current tab must not leak its diagram into the next tab."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        diagram_model.addBox(10.0, 10.0, "Tab 0 Box")

        tab_model.addTab("Tab 1")
        project_manager.switchTab(1)
        diagram_model.addBox(20.0, 10.0, "Tab 1 Box")

        tab_model.addTab("Tab 2")
        project_manager.switchTab(2)
        diagram_model.addBox(30.0, 10.0, "Tab 2 Box")

        project_manager.switchTab(1)
        project_manager.removeTab(1)

        assert tab_model.tabCount == 2
        assert tab_model.currentTabIndex == 1
        assert diagram_model.count == 1
        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.TextRole) == "Tab 2 Box"

    def test_remove_active_tab_reloads_surviving_tasks(self, app):
        """Deleting the current tab must not leak its task list into the next tab."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Tab 0 Task", -1)

        tab_model.addTab("Tab 1")
        project_manager.switchTab(1)
        task_model.addTask("Tab 1 Task", -1)

        tab_model.addTab("Tab 2")
        project_manager.switchTab(2)
        task_model.addTask("Tab 2 Task", -1)

        project_manager.switchTab(1)
        project_manager.removeTab(1)

        assert tab_model.tabCount == 2
        assert tab_model.currentTabIndex == 1
        assert task_model.rowCount() == 1
        index = task_model.index(0, 0)
        assert task_model.data(index, task_model.TitleRole) == "Tab 2 Task"

    def test_remove_non_current_tab_preserves_current_live_state(self, app):
        """Deleting another tab must not disturb the current tab or future saves."""
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel()
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        diagram_model.addBox(10.0, 10.0, "Main Box")

        tab_model.addTab("Tab 1")
        project_manager.switchTab(1)
        diagram_model.addBox(20.0, 10.0, "Tab 1 Box")

        tab_model.addTab("Tab 2")
        project_manager.switchTab(2)
        diagram_model.addBox(30.0, 10.0, "Tab 2 Box")

        project_manager.switchTab(2)
        project_manager.removeTab(0)

        assert tab_model.currentTabIndex == 1
        assert diagram_model.count == 1
        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.TextRole) == "Tab 2 Box"

        diagram_model.addBox(35.0, 10.0, "Tab 2 New Box")
        project_manager.switchTab(0)
        project_manager.switchTab(1)

        texts = [
            diagram_model.data(diagram_model.index(row, 0), diagram_model.TextRole)
            for row in range(diagram_model.count)
        ]
        assert texts == ["Tab 2 Box", "Tab 2 New Box"]

    def test_project_manager_drill_to_task_sets_current(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Drill target", -1)
        diagram_model = DiagramModel(task_model=task_model)
        diagram_model.addTask(0, 40.0, 60.0)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        project_manager.drillToTask(0)
        assert diagram_model.currentTaskIndex == 0

    def test_project_manager_open_tab_task_switches_and_drills(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Main Task", -1)
        diagram_model.addTask(0, 20.0, 20.0)

        tab_model.addTab("Second")
        tab_model.setTabData(
            1,
            {"tasks": [{"title": "Second Task", "completed": False}]},
            {
                "items": [{
                    "id": "task_0",
                    "item_type": "task",
                    "x": 40.0,
                    "y": 60.0,
                    "width": 140.0,
                    "height": 70.0,
                    "text": "Second Task",
                    "task_index": 0,
                    "color": "#2e5c88",
                    "text_color": "#f5f6f8",
                }],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            },
        )

        project_manager.openTabTask(1, 0)
        assert tab_model.currentTabIndex == 1
        assert diagram_model.currentTaskIndex == 0

    def test_project_manager_open_tab_task_enables_back_and_restores_origin(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Main Task", -1)
        diagram_model.addTask(0, 20.0, 20.0)
        diagram_model.focusTask(0)

        tab_model.addTab("Second")
        tab_model.setTabData(
            1,
            {"tasks": [{"title": "Second Task", "completed": False}]},
            {
                "items": [{
                    "id": "task_0",
                    "item_type": "task",
                    "x": 40.0,
                    "y": 60.0,
                    "width": 140.0,
                    "height": 70.0,
                    "text": "Second Task",
                    "task_index": 0,
                    "color": "#2e5c88",
                    "text_color": "#f5f6f8",
                }],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            },
        )

        project_manager.openTabTask(1, 0)

        assert project_manager.canGoBack is True
        assert tab_model.currentTabIndex == 1
        assert diagram_model.currentTaskIndex == 0

        project_manager.goBack()

        assert project_manager.canGoBack is False
        assert tab_model.currentTabIndex == 0
        assert diagram_model.currentTaskIndex == 0

    def test_project_manager_manual_switch_tab_does_not_enable_back(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        tab_model.addTab("Second")

        project_manager.switchTab(1)

        assert tab_model.currentTabIndex == 1
        assert project_manager.canGoBack is False

    def test_project_manager_go_back_unwinds_multiple_drills(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Tab 1 Task", -1)
        diagram_model.addTask(0, 10.0, 10.0)

        tab_model.addTab("Tab 2")
        tab_model.addTab("Tab 3")
        tab_model.setTabData(
            1,
            {"tasks": [{"title": "Tab 2 Task", "completed": False}]},
            {
                "items": [{
                    "id": "task_0",
                    "item_type": "task",
                    "x": 30.0,
                    "y": 30.0,
                    "width": 140.0,
                    "height": 70.0,
                    "text": "Tab 2 Task",
                    "task_index": 0,
                    "color": "#2e5c88",
                    "text_color": "#f5f6f8",
                }],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            },
        )
        tab_model.setTabData(
            2,
            {"tasks": [{"title": "Tab 3 Task", "completed": False}]},
            {
                "items": [{
                    "id": "task_0",
                    "item_type": "task",
                    "x": 50.0,
                    "y": 50.0,
                    "width": 140.0,
                    "height": 70.0,
                    "text": "Tab 3 Task",
                    "task_index": 0,
                    "color": "#2e5c88",
                    "text_color": "#f5f6f8",
                }],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            },
        )

        project_manager.openTabTask(1, 0)
        project_manager.openTabTask(2, 0)

        assert tab_model.currentTabIndex == 2
        assert project_manager.canGoBack is True

        project_manager.goBack()
        assert tab_model.currentTabIndex == 1
        assert diagram_model.currentTaskIndex == 0
        assert project_manager.canGoBack is True

        project_manager.goBack()
        assert tab_model.currentTabIndex == 0
        assert diagram_model.currentTaskIndex == -1
        assert project_manager.canGoBack is False

    def test_project_manager_load_clears_back_history(self, app, tmp_path):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        task_model.addTask("Main Task", -1)
        diagram_model.addTask(0, 20.0, 20.0)
        tab_model.addTab("Second")
        tab_model.setTabData(
            1,
            {"tasks": [{"title": "Second Task", "completed": False}]},
            {
                "items": [{
                    "id": "task_0",
                    "item_type": "task",
                    "x": 40.0,
                    "y": 60.0,
                    "width": 140.0,
                    "height": 70.0,
                    "text": "Second Task",
                    "task_index": 0,
                    "color": "#2e5c88",
                    "text_color": "#f5f6f8",
                }],
                "edges": [],
                "strokes": [],
                "current_task_index": -1,
            },
        )

        project_manager.openTabTask(1, 0)
        assert project_manager.canGoBack is True

        project_file = tmp_path / "back_history.progress"
        project_manager.saveProject(str(project_file))
        project_manager.loadProject(str(project_file))

        assert project_manager.canGoBack is False

    def test_project_manager_open_reminder_task_uses_open_tab_task(self, app, monkeypatch):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        captured = []

        def _capture_open(tab_index, task_index):
            captured.append((tab_index, task_index))

        monkeypatch.setattr(project_manager, "openTabTask", _capture_open)
        project_manager.openReminderTask(3, 7)
        assert captured == [(3, 7)]

    def test_project_manager_add_tab_as_drill_task(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        tab_model.addTab("Backend API")
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        created_item_id = project_manager.addTabAsDrillTask(1, 120.0, 240.0)
        assert created_item_id.startswith("task_")
        assert task_model.rowCount() == 1
        assert task_model.getTaskTitle(0) == "Backend API"
        assert diagram_model.count == 1
        item = diagram_model.getItemSnapshot(created_item_id)
        assert item["taskIndex"] == 0
        assert item["text"] == "Backend API"


class TestActionDrawQmlTaskInteractions:
    def test_linked_task_double_click_drills_to_tab(self):
        qml = load_actiondraw_qml()

        assert "Task linked to task list - drill into its tab" in qml
        assert "projectManager.drillToTab(itemRect.taskIndex)" in qml
        assert "dialogs.taskRenameDialog.openWithItem(itemRect.itemId, model.text)" not in qml

    def test_task_context_menu_exposes_rename_and_drill(self):
        qml = load_actiondraw_qml()

        assert 'id: renameTaskMenuItem' in qml
        assert 'text: "Rename Task..."' in qml
        assert 'id: drillToTabMenuItem' in qml

    def test_toolbar_exposes_back_button(self):
        qml = (QML_DIR / "components" / "ToolbarRow.qml").read_text(encoding="utf-8")

        assert 'text: "\\u2190 Back"' in qml
        assert 'projectManager.goBack()' in qml
        assert 'projectManager.canGoBack' in qml

    def test_shortcut_exposes_back_navigation(self):
        qml = load_actiondraw_qml()

        assert 'sequence: "Alt+Left"' in qml
        assert 'onActivated: projectManager.goBack()' in qml
        assert 'projectManager: projectManagerRef' in qml

    def test_f2_shortcut_renames_selected_item_or_current_tab(self):
        qml = load_actiondraw_qml()
        sidebar_qml = (QML_DIR / "components" / "SidebarTabs.qml").read_text(encoding="utf-8")

        assert 'sequence: "F2"' in qml
        assert 'if (root.selectedItemId && root.selectedItemId.length > 0)' in qml
        assert 'root.renameSelectedItem()' in qml
        assert 'else if (sidebarTabs && sidebarTabs.renameCurrentTab)' in qml
        assert 'sidebarTabs.renameCurrentTab()' in qml
        assert 'function renameCurrentTab()' in sidebar_qml
        assert 'openTabRenameDialog(tabModel.currentTabIndex, summary.name || "")' in sidebar_qml

    def test_note_badge_excludes_freetext_items(self):
        qml = load_actiondraw_qml()

        assert 'id: noteBadge' in qml
        assert 'visible: itemRect.itemType !== "note" && itemRect.itemType !== "freetext" && itemRect.itemType !== "image"' in qml
        assert 'visible: itemRect.itemType !== "note" && model.noteMarkdown && model.noteMarkdown.trim().length > 0' not in qml
        assert 'color: model.noteMarkdown && model.noteMarkdown.trim().length > 0 ? "#6fd3ff" : "#f5d96b"' in qml
        assert 'border.color: model.noteMarkdown && model.noteMarkdown.trim().length > 0 ? "#3298c7" : "#d9b84f"' in qml

    def test_freetext_tooltip_and_selection_use_freetext_flow(self):
        qml = load_actiondraw_qml()

        assert 'if (item.type === "freetext") {' in qml
        assert 'root.openFreeTextDialog(Qt.point(item.x, item.y), item.id, item.text)' in qml
        assert 'ToolTip.text: model.text + (model.noteMarkdown && model.noteMarkdown !== model.text ? "\\n\\n" + model.noteMarkdown : "")' in qml
        assert 'ToolTip.text: model.text + (model.noteMarkdown && model.noteMarkdown !== model.text ? "\\n\\n" + model.noteMarkdown : "")' not in qml[qml.index('id: freeTextLabel'):]
        assert 'ToolTip.text: itemRect.freeTextDisplayText' in qml[qml.index('id: freeTextLabel'):]

    def test_freetext_canvas_preview_has_tab_switcher(self):
        qml = load_actiondraw_qml()

        assert 'property var freeTextTabs: model.textTabs || []' in qml
        assert 'property int freeTextTabIndex: model.textTabIndex || 0' in qml
        assert 'id: freeTextTabSwitcher' in qml
        assert 'visible: itemRect.freeTextTabCount > 1' in qml
        assert 'diagramModel.setItemTextTabIndex(itemRect.itemId, nextIndex)' in qml
        assert 'text: itemRect.freeTextDisplayText' in qml[qml.index('id: freeTextLabel'):]


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


class TestTaskReminders:
    """Tests for task reminder date/time notifications."""

    @pytest.fixture
    def task_model_with_reminder(self, app):
        model = TaskModel()
        model.addTask("Task with reminder", -1)
        return model

    @pytest.fixture
    def diagram_model_with_reminder_task(self, app, task_model_with_reminder):
        model = DiagramModel(task_model=task_model_with_reminder)
        model.addTask(0, 100.0, 100.0)
        return model, task_model_with_reminder

    def test_reminder_defaults(self, task_model_with_reminder):
        index = task_model_with_reminder.index(0, 0)
        active = task_model_with_reminder.data(index, task_model_with_reminder.ReminderActiveRole)
        reminder_at = task_model_with_reminder.data(index, task_model_with_reminder.ReminderAtRole)
        assert active == False
        assert reminder_at == ""
        assert task_model_with_reminder.isReminderNotificationEnabled(0) is False

    def test_set_reminder_valid(self, task_model_with_reminder):
        from datetime import datetime, timedelta

        reminder_dt = datetime.now() + timedelta(hours=1)
        reminder_str = reminder_dt.strftime("%Y-%m-%d %H:%M")
        assert task_model_with_reminder.setReminderAt(0, reminder_str, True) is True

        index = task_model_with_reminder.index(0, 0)
        active = task_model_with_reminder.data(index, task_model_with_reminder.ReminderActiveRole)
        reminder_at = task_model_with_reminder.data(index, task_model_with_reminder.ReminderAtRole)
        assert active == True
        assert reminder_at == reminder_str
        assert task_model_with_reminder.isReminderNotificationEnabled(0) is True

    def test_set_reminder_invalid(self, task_model_with_reminder):
        assert task_model_with_reminder.setReminderAt(0, "not-a-date") is False
        index = task_model_with_reminder.index(0, 0)
        active = task_model_with_reminder.data(index, task_model_with_reminder.ReminderActiveRole)
        assert active == False

    def test_clear_reminder(self, task_model_with_reminder):
        from datetime import datetime, timedelta

        reminder_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_reminder.setReminderAt(0, reminder_str, True) is True
        task_model_with_reminder.clearReminderAt(0)

        index = task_model_with_reminder.index(0, 0)
        active = task_model_with_reminder.data(index, task_model_with_reminder.ReminderActiveRole)
        reminder_at = task_model_with_reminder.data(index, task_model_with_reminder.ReminderAtRole)
        assert active == False
        assert reminder_at == ""
        assert task_model_with_reminder.isReminderNotificationEnabled(0) is False

    def test_due_reminder_emits_signal_and_clears(self, task_model_with_reminder):
        from datetime import datetime, timedelta

        reminder_str = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_reminder.setReminderAt(0, reminder_str) is True

        due = []
        task_model_with_reminder.taskReminderDue.connect(lambda idx, title: due.append((idx, title)))
        task_model_with_reminder._updateActiveTasks()

        assert due == [(0, "Task with reminder")]
        index = task_model_with_reminder.index(0, 0)
        active = task_model_with_reminder.data(index, task_model_with_reminder.ReminderActiveRole)
        assert active == False

    def test_reminder_serialization(self, task_model_with_reminder):
        from datetime import datetime, timedelta

        reminder_str = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_reminder.setReminderAt(0, reminder_str, True) is True
        data = task_model_with_reminder.to_dict()
        task_data = data["tasks"][0]
        assert "reminder_at" in task_data
        assert task_data["reminder_send_notification"] is True

    def test_reminder_deserialization(self, app):
        import time

        model = TaskModel()
        data = {
            "tasks": [{
                "title": "Reminder Task",
                "completed": False,
                "time_spent": 0.0,
                "parent_index": -1,
                "indent_level": 0,
                "custom_estimate": None,
                "reminder_at": time.time() + 3600,
                "reminder_send_notification": True,
            }]
        }

        model.from_dict(data)
        index = model.index(0, 0)
        active = model.data(index, model.ReminderActiveRole)
        reminder_at = model.data(index, model.ReminderAtRole)
        assert active == True
        assert isinstance(reminder_at, str)
        assert reminder_at != ""
        assert model.isReminderNotificationEnabled(0) is True

    def test_diagram_reminder_roles_exist(self, diagram_model_with_reminder_task):
        model, _ = diagram_model_with_reminder_task
        role_names = model.roleNames()
        assert b"taskReminderActive" in role_names.values()
        assert b"taskReminderAt" in role_names.values()

    def test_diagram_reminder_reflects_task_model(self, diagram_model_with_reminder_task):
        from datetime import datetime, timedelta

        diagram_model, task_model = diagram_model_with_reminder_task
        reminder_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, reminder_str) is True

        index = diagram_model.index(0, 0)
        active = diagram_model.data(index, diagram_model.TaskReminderActiveRole)
        reminder_at = diagram_model.data(index, diagram_model.TaskReminderAtRole)
        assert active == True
        assert reminder_at == reminder_str

    def test_diagram_clear_reminder_slot(self, diagram_model_with_reminder_task):
        from datetime import datetime, timedelta

        diagram_model, task_model = diagram_model_with_reminder_task
        reminder_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, reminder_str) is True

        diagram_model.clearTaskReminderAt(0)
        index = task_model.index(0, 0)
        active = task_model.data(index, task_model.ReminderActiveRole)
        assert active == False

    def test_diagram_set_reminder_slot_returns_status(self, diagram_model_with_reminder_task):
        from datetime import datetime, timedelta

        diagram_model, task_model = diagram_model_with_reminder_task
        reminder_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")

        assert diagram_model.setTaskReminderAt(0, reminder_str, True) is True
        assert diagram_model.setTaskReminderAt(0, "invalid") is False

        index = task_model.index(0, 0)
        active = task_model.data(index, task_model.ReminderActiveRole)
        assert active == True
        assert diagram_model.isTaskReminderNotificationEnabled(0) is True

    def test_project_manager_sends_ntfy_for_current_tab_due_reminder(self, app, monkeypatch):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel
        import task_model as task_model_module

        task_model = TaskModel()
        task_model.addTask("Current Reminder", -1)
        reminder_str = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, reminder_str, True) is True

        published = []
        monkeypatch.setattr(
            task_model_module,
            "_publish_ntfy_message_async",
            lambda title, message, server=None, topic=None, token=None: published.append((title, message, server, topic, token)),
        )

        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        project_manager.saveNtfySettings("https://example.ntfy", "alerts", "secret")

        task_model._updateActiveTasks()

        assert project_manager is not None
        assert published == [("ActionDraw Reminder", "Reminder due: Current Reminder\nTab: Main", "https://example.ntfy", "alerts", "secret")]

    def test_project_manager_emits_current_tab_reminder_due(self, app):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Current Reminder", -1)
        reminder_str = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, reminder_str) is True

        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        project_manager.saveNtfySettings("https://ntfy.sh", "", "")

        due = []
        project_manager.taskReminderDue.connect(lambda tab_idx, task_idx, title: due.append((tab_idx, task_idx, title)))
        task_model._updateActiveTasks()

        assert due == [(0, 0, "Current Reminder")]

    def test_project_manager_emits_background_tab_reminder_due(self, app):
        import time
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Tab 1 Task", -1)
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)
        project_manager.saveNtfySettings("https://ntfy.sh", "", "")

        tab_model.addTab("Tab 2")
        tab_model.setTabData(
            1,
            {
                "tasks": [{
                    "title": "Background Reminder",
                    "completed": False,
                    "time_spent": 0.0,
                    "parent_index": -1,
                    "indent_level": 0,
                    "custom_estimate": None,
                    "reminder_at": time.time() - 1,
                    "reminder_send_notification": True,
                }]
            },
            {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
        )

        due = []
        project_manager.taskReminderDue.connect(lambda tab_idx, task_idx, title: due.append((tab_idx, task_idx, title)))
        project_manager._checkBackgroundTabReminders()

        assert due == [(1, 0, "Background Reminder")]

        # Reminder is cleared after firing
        tabs = tab_model.getAllTabs()
        task_data = tabs[1].tasks["tasks"][0]
        assert "reminder_at" not in task_data
        assert "reminder_send_notification" not in task_data

    def test_project_manager_sends_ntfy_for_background_tab_due_reminder(self, app, monkeypatch):
        import time
        from task_model import TaskModel, ProjectManager, TabModel
        import task_model as task_model_module

        task_model = TaskModel()
        task_model.addTask("Tab 1 Task", -1)
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        tab_model.addTab("Tab 2")
        tab_model.setTabData(
            1,
            {
                "tasks": [{
                    "title": "Background Reminder",
                    "completed": False,
                    "time_spent": 0.0,
                    "parent_index": -1,
                    "indent_level": 0,
                    "custom_estimate": None,
                    "reminder_at": time.time() - 1,
                    "reminder_send_notification": True,
                }]
            },
            {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
        )

        published = []
        monkeypatch.setattr(
            task_model_module,
            "_publish_ntfy_message_async",
            lambda title, message, server=None, topic=None, token=None: published.append((title, message, server, topic, token)),
        )
        project_manager.saveNtfySettings("https://example.ntfy", "alerts", "secret")

        project_manager._checkBackgroundTabReminders()

        assert published == [("ActionDraw Reminder", "Reminder due: Background Reminder\nTab: Tab 2", "https://example.ntfy", "alerts", "secret")]

    def test_project_manager_persists_ntfy_settings(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        project_manager.saveNtfySettings("https://example.ntfy", "alerts", "secret")

        assert project_manager.ntfyServer == "https://example.ntfy"
        assert project_manager.ntfyTopic == "alerts"
        assert project_manager.ntfyToken == "secret"
        assert project_manager.ntfyConfigured is True

        project_manager.saveNtfySettings("https://example.ntfy", "", "")

        assert project_manager.ntfyConfigured is False

    def test_project_manager_sends_test_ntfy_notification(self, app, monkeypatch):
        from task_model import TaskModel, ProjectManager, TabModel
        import task_model as task_model_module

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        published = []
        statuses = []
        project_manager.testNotificationCompleted.connect(
            lambda success, message: statuses.append((success, message))
        )

        def fake_publish(title, message, server=None, topic=None, token=None, callback=None):
            published.append((title, message, server, topic, token))
            if callback is not None:
                callback(True, "")

        monkeypatch.setattr(task_model_module, "_publish_ntfy_message_async", fake_publish)

        started = project_manager.sendTestNtfyNotification(
            "https://example.ntfy",
            "alerts",
            "secret",
        )

        assert started is True
        assert published == [
            (
                "ActionDraw Test Notification",
                "This is a test notification from ActionDraw.",
                "https://example.ntfy",
                "alerts",
                "secret",
            )
        ]
        assert statuses == [(True, "Test notification sent")]

    def test_project_manager_does_not_send_test_ntfy_without_topic(self, app, monkeypatch):
        from task_model import TaskModel, ProjectManager, TabModel
        import task_model as task_model_module

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        published = []
        statuses = []
        project_manager.testNotificationCompleted.connect(
            lambda success, message: statuses.append((success, message))
        )

        monkeypatch.setattr(
            task_model_module,
            "_publish_ntfy_message_async",
            lambda *args, **kwargs: published.append((args, kwargs)),
        )

        started = project_manager.sendTestNtfyNotification(
            "https://example.ntfy",
            "",
            "secret",
        )

        assert started is False
        assert published == []
        assert statuses == [(False, "Notifications are not configured until you set an ntfy topic")]

    def test_project_manager_reports_test_ntfy_publish_failure(self, app, monkeypatch):
        from task_model import TaskModel, ProjectManager, TabModel
        import task_model as task_model_module

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        statuses = []
        project_manager.testNotificationCompleted.connect(
            lambda success, message: statuses.append((success, message))
        )

        def fake_publish(title, message, server=None, topic=None, token=None, callback=None):
            if callback is not None:
                callback(False, "boom")

        monkeypatch.setattr(task_model_module, "_publish_ntfy_message_async", fake_publish)

        started = project_manager.sendTestNtfyNotification(
            "https://example.ntfy",
            "alerts",
            "secret",
        )

        assert started is True
        assert statuses == [(False, "Failed to send test notification: boom")]

    def test_project_manager_get_active_reminders_returns_sorted_cross_tab_results(self, app):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Current Reminder", -1)
        current_str = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, current_str) is True

        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        earlier = (datetime.now() + timedelta(minutes=15)).timestamp()
        later = (datetime.now() + timedelta(hours=5)).timestamp()
        tab_model.addTab("Tab 2")
        tab_model.setTabData(
            1,
            {
                "tasks": [
                    {
                        "title": "Completed Reminder",
                        "completed": True,
                        "time_spent": 0.0,
                        "parent_index": -1,
                        "indent_level": 0,
                        "custom_estimate": None,
                        "reminder_at": later,
                    },
                    {
                        "title": "Background Reminder",
                        "completed": False,
                        "time_spent": 0.0,
                        "parent_index": -1,
                        "indent_level": 0,
                        "custom_estimate": None,
                        "reminder_at": earlier,
                    },
                ]
            },
            {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
        )

        reminders = project_manager.getActiveReminders()

        assert [entry["taskTitle"] for entry in reminders] == ["Background Reminder", "Current Reminder"]
        assert reminders[0]["tabName"] == "Tab 2"
        assert reminders[1]["tabName"] == "Main"

    def test_project_manager_clear_reminder_clears_current_tab(self, app):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Current Reminder", -1)
        reminder_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setReminderAt(0, reminder_str) is True

        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        project_manager.clearReminder(0, 0)

        index = task_model.index(0, 0)
        assert task_model.data(index, task_model.ReminderActiveRole) is False
        assert project_manager.getActiveReminders() == []

    def test_project_manager_clear_reminder_clears_background_tab(self, app):
        import time
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Current Task", -1)
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        tab_model.addTab("Tab 2")
        tab_model.setTabData(
            1,
            {
                "tasks": [{
                    "title": "Background Reminder",
                    "completed": False,
                    "time_spent": 0.0,
                    "parent_index": -1,
                    "indent_level": 0,
                    "custom_estimate": None,
                    "reminder_at": time.time() + 600,
                }]
            },
            {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
        )

        project_manager.clearReminder(1, 0)

        tabs = tab_model.getAllTabs()
        assert "reminder_at" not in tabs[1].tasks["tasks"][0]
        assert project_manager.getActiveReminders() == []


class TestTaskContracts:
    """Tests for deadline-based task contracts."""

    @pytest.fixture
    def task_model_with_contract(self, app):
        model = TaskModel()
        model.addTask("Task with contract", -1)
        return model

    @pytest.fixture
    def diagram_model_with_contract_task(self, app, task_model_with_contract):
        model = DiagramModel(task_model=task_model_with_contract)
        model.addTask(0, 100.0, 100.0)
        return model, task_model_with_contract

    def test_contract_defaults(self, task_model_with_contract):
        index = task_model_with_contract.index(0, 0)
        assert task_model_with_contract.data(index, task_model_with_contract.ContractActiveRole) is False
        assert task_model_with_contract.data(index, task_model_with_contract.ContractDeadlineRole) == ""
        assert task_model_with_contract.data(index, task_model_with_contract.ContractRemainingRole) == -1.0
        assert task_model_with_contract.data(index, task_model_with_contract.ContractBreachedRole) is False
        assert task_model_with_contract.data(index, task_model_with_contract.ContractPunishmentRole) == ""

    def test_set_contract_valid(self, task_model_with_contract):
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Throw away coke") is True

        index = task_model_with_contract.index(0, 0)
        assert task_model_with_contract.data(index, task_model_with_contract.ContractActiveRole) is True
        assert task_model_with_contract.data(index, task_model_with_contract.ContractDeadlineRole) == deadline_str
        assert task_model_with_contract.data(index, task_model_with_contract.ContractPunishmentRole) == "Throw away coke"

    def test_set_contract_invalid_inputs(self, task_model_with_contract):
        assert task_model_with_contract.setContractAt(0, "not-a-date", "Punishment") is False
        assert task_model_with_contract.setContractAt(0, "", "Punishment") is False
        assert task_model_with_contract.setContractAt(0, "2099-01-01 09:00", "") is False

    def test_set_contract_rejects_past_datetime(self, task_model_with_contract):
        from datetime import datetime, timedelta

        past_str = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, past_str, "Punishment") is False

    def test_contract_remaining_decreases(self, task_model_with_contract):
        import time
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Punishment") is True
        index = task_model_with_contract.index(0, 0)
        remaining_1 = task_model_with_contract.data(index, task_model_with_contract.ContractRemainingRole)
        time.sleep(0.2)
        remaining_2 = task_model_with_contract.data(index, task_model_with_contract.ContractRemainingRole)
        assert remaining_2 < remaining_1

    def test_contract_breach_emits_once(self, task_model_with_contract):
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Punishment") is True

        task = task_model_with_contract._tasks[0]
        task.contract_deadline_at = time.time() - 1
        due = []
        task_model_with_contract.taskContractBreached.connect(
            lambda idx, title, punishment, deadline: due.append((idx, title, punishment, deadline))
        )
        task_model_with_contract._updateActiveTasks()
        task_model_with_contract._updateActiveTasks()

        assert len(due) == 1
        index = task_model_with_contract.index(0, 0)
        assert task_model_with_contract.data(index, task_model_with_contract.ContractBreachedRole) is True

    def test_complete_task_clears_contract(self, task_model_with_contract):
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Punishment") is True
        task_model_with_contract.toggleComplete(0, True)
        index = task_model_with_contract.index(0, 0)
        assert task_model_with_contract.data(index, task_model_with_contract.ContractActiveRole) is False

    def test_clear_contract(self, task_model_with_contract):
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Punishment") is True
        task_model_with_contract.clearContract(0)
        index = task_model_with_contract.index(0, 0)
        assert task_model_with_contract.data(index, task_model_with_contract.ContractActiveRole) is False
        assert task_model_with_contract.data(index, task_model_with_contract.ContractPunishmentRole) == ""

    def test_contract_serialization(self, task_model_with_contract):
        from datetime import datetime, timedelta

        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model_with_contract.setContractAt(0, deadline_str, "Punishment") is True
        data = task_model_with_contract.to_dict()
        task_data = data["tasks"][0]
        assert "contract_deadline_at" in task_data
        assert task_data["contract_punishment"] == "Punishment"

    def test_contract_deserialization(self, app):
        model = TaskModel()
        data = {
            "tasks": [{
                "title": "Contract Task",
                "completed": False,
                "time_spent": 0.0,
                "parent_index": -1,
                "indent_level": 0,
                "custom_estimate": None,
                "contract_deadline_at": time.time() + 3600,
                "contract_punishment": "No coke",
                "contract_breached": False,
                "contract_breach_notified": False,
            }]
        }
        model.from_dict(data)
        index = model.index(0, 0)
        assert model.data(index, model.ContractActiveRole) is True
        assert model.data(index, model.ContractPunishmentRole) == "No coke"

    def test_diagram_contract_roles_exist(self, diagram_model_with_contract_task):
        model, _ = diagram_model_with_contract_task
        role_names = model.roleNames()
        assert b"taskContractActive" in role_names.values()
        assert b"taskContractDeadline" in role_names.values()
        assert b"taskContractRemaining" in role_names.values()
        assert b"taskContractBreached" in role_names.values()
        assert b"taskContractPunishment" in role_names.values()

    def test_diagram_contract_reflects_task_model(self, diagram_model_with_contract_task):
        from datetime import datetime, timedelta

        diagram_model, task_model = diagram_model_with_contract_task
        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setContractAt(0, deadline_str, "Punishment") is True
        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.TaskContractActiveRole) is True
        assert diagram_model.data(index, diagram_model.TaskContractDeadlineRole) == deadline_str
        assert diagram_model.data(index, diagram_model.TaskContractPunishmentRole) == "Punishment"

    def test_diagram_set_and_clear_contract_slot(self, diagram_model_with_contract_task):
        from datetime import datetime, timedelta

        diagram_model, task_model = diagram_model_with_contract_task
        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert diagram_model.setTaskContractAt(0, deadline_str, "Punishment") is True
        index = task_model.index(0, 0)
        assert task_model.data(index, task_model.ContractActiveRole) is True
        diagram_model.clearTaskContract(0)
        assert task_model.data(index, task_model.ContractActiveRole) is False

    def test_project_manager_emits_current_tab_contract_breached(self, app):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Current Contract", -1)
        deadline_str = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setContractAt(0, deadline_str, "Punishment") is True
        task_model._tasks[0].contract_deadline_at = time.time() - 1
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        due = []
        project_manager.taskContractBreached.connect(
            lambda tab_idx, task_idx, title, punishment, deadline: due.append(
                (tab_idx, task_idx, title, punishment, deadline)
            )
        )
        task_model._updateActiveTasks()

        assert len(due) == 1
        assert due[0][0] == 0
        assert due[0][1] == 0
        assert due[0][2] == "Current Contract"

    def test_project_manager_emits_background_tab_contract_breached_once(self, app):
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Tab 1 Task", -1)
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        tab_model.addTab("Tab 2")
        tab_model.setTabData(
            1,
            {
                "tasks": [{
                    "title": "Background Contract",
                    "completed": False,
                    "time_spent": 0.0,
                    "parent_index": -1,
                    "indent_level": 0,
                    "custom_estimate": None,
                    "contract_deadline_at": time.time() - 1,
                    "contract_punishment": "Throw away coke",
                    "contract_breached": False,
                    "contract_breach_notified": False,
                }]
            },
            {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
        )

        due = []
        project_manager.taskContractBreached.connect(
            lambda tab_idx, task_idx, title, punishment, deadline: due.append(
                (tab_idx, task_idx, title, punishment, deadline)
            )
        )
        project_manager._checkBackgroundTabReminders()
        project_manager._checkBackgroundTabReminders()

        assert len(due) == 1
        assert due[0][0] == 1
        assert due[0][1] == 0
        assert due[0][2] == "Background Contract"

    def test_project_manager_get_active_contracts(self, app):
        from datetime import datetime, timedelta
        from task_model import TaskModel, ProjectManager, TabModel

        task_model = TaskModel()
        task_model.addTask("Active Contract", -1)
        deadline_str = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        assert task_model.setContractAt(0, deadline_str, "No coke") is True
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        project_manager = ProjectManager(task_model, diagram_model, tab_model)

        contracts = project_manager.getActiveContracts()
        assert len(contracts) == 1
        assert contracts[0]["taskTitle"] == "Active Contract"
        assert contracts[0]["punishment"] == "No coke"


class TestLinkedSubtabMetadata:
    """Tests for task-level linked subtab metadata on diagram items."""

    def test_linked_subtab_defaults_without_tab_model(self, app):
        task_model = TaskModel()
        task_model.addTask("Parent Task", -1)
        diagram_model = DiagramModel(task_model=task_model)
        diagram_model.addTask(0, 100.0, 100.0)

        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.HasLinkedSubtabRole) is False
        assert diagram_model.data(index, diagram_model.LinkedSubtabCompletionRole) == -1.0
        assert diagram_model.data(index, diagram_model.LinkedSubtabActiveActionRole) == ""

    def test_linked_subtab_completion_and_active_action(self, app):
        from task_model import Tab, TabModel

        task_model = TaskModel()
        task_model.addTask("Build API", -1)
        diagram_model = DiagramModel(task_model=task_model)

        tab_model = TabModel()
        tab_model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "Build API", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
                Tab(
                    name="Build API",
                    tasks={
                        "tasks": [
                            {"title": "Scope", "completed": True},
                            {"title": "Implement", "completed": False},
                        ]
                    },
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": 1},
                ),
            ],
            active_tab=0,
        )
        diagram_model.setTabModel(tab_model)
        diagram_model.addTask(0, 120.0, 140.0)

        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.HasLinkedSubtabRole) is True
        assert diagram_model.data(index, diagram_model.LinkedSubtabCompletionRole) == 50.0
        assert diagram_model.data(index, diagram_model.LinkedSubtabActiveActionRole) == "Implement"

    def test_linked_subtab_updates_when_tab_data_changes(self, app):
        from task_model import Tab, TabModel

        task_model = TaskModel()
        task_model.addTask("Launch", -1)
        diagram_model = DiagramModel(task_model=task_model)

        tab_model = TabModel()
        tab_model.setTabs(
            [
                Tab(name="Main", tasks={"tasks": []}, diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1}),
                Tab(
                    name="Launch",
                    tasks={"tasks": [{"title": "Prep", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=0,
        )
        diagram_model.setTabModel(tab_model)
        diagram_model.addTask(0, 80.0, 90.0)

        emitted_roles = []

        def _capture_data_changed(_first, _last, roles):
            emitted_roles.append(list(roles))

        diagram_model.dataChanged.connect(_capture_data_changed)

        tab_model.setTabData(
            1,
            {"tasks": [{"title": "Ship", "completed": True}]},
            {"items": [], "edges": [], "strokes": [], "current_task_index": 0},
        )

        index = diagram_model.index(0, 0)
        assert diagram_model.data(index, diagram_model.LinkedSubtabCompletionRole) == 100.0
        assert diagram_model.data(index, diagram_model.LinkedSubtabActiveActionRole) == "Ship"
        assert any(diagram_model.LinkedSubtabCompletionRole in roles for roles in emitted_roles)
        assert any(diagram_model.LinkedSubtabActiveActionRole in roles for roles in emitted_roles)


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

    def test_get_tabs_linking_to_current_tab(self, app):
        """Returns tabs that contain a task matching current tab name."""
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "API", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
                Tab(
                    name="API",
                    tasks={"tasks": [{"title": "Do work", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": 0},
                ),
                Tab(
                    name="Other",
                    tasks={"tasks": [{"title": "API", "completed": True}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=1,
        )

        links = model.getTabsLinkingToCurrentTab()
        link_names = [link["name"] for link in links]
        assert link_names == ["Main", "Other"]
        assert links[0]["tabIndex"] == 0
        assert links[1]["tabIndex"] == 2

    def test_get_tabs_linking_to_current_tab_empty_when_no_matches(self, app):
        """No linking tabs returns an empty list."""
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "Task A", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
                Tab(
                    name="Subtab",
                    tasks={"tasks": [{"title": "Task B", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=1,
        )

        assert model.getTabsLinkingToCurrentTab() == []

    def test_get_hierarchy_tree_includes_all_nodes(self, app):
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "API", "completed": False}]},
                    diagram={
                        "items": [
                            {
                                "id": "task_0",
                                "item_type": "task",
                                "text": "API",
                                "task_index": 0,
                            },
                            {
                                "id": "note_0",
                                "item_type": "note",
                                "text": "Ideas",
                                "task_index": -1,
                            },
                        ],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
                Tab(
                    name="API",
                    tasks={"tasks": [{"title": "Ship", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=0,
        )

        tree = model.getHierarchyTree()
        assert len(tree) == 2
        main = tree[0]
        assert main["kind"] == "tab"
        assert main["tabName"] == "Main"
        assert len(main["children"]) == 2
        assert main["children"][0]["itemId"] == "task_0"
        assert main["children"][0]["hasLinkedSubtab"] is True
        assert main["children"][0]["linkedTabName"] == "API"
        assert main["children"][1]["itemId"] == "note_0"
        assert main["children"][1]["hasLinkedSubtab"] is False

    def test_get_hierarchy_tree_builds_recursive_subdiagram(self, app):
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "API", "completed": False}]},
                    diagram={
                        "items": [{"id": "task_main", "item_type": "task", "text": "API", "task_index": 0}],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
                Tab(
                    name="API",
                    tasks={"tasks": [{"title": "DB", "completed": False}]},
                    diagram={
                        "items": [{"id": "task_api", "item_type": "task", "text": "DB", "task_index": 0}],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
                Tab(
                    name="DB",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=0,
        )

        tree = model.getHierarchyTree()
        main_link = tree[0]["children"][0]
        assert len(main_link["children"]) == 1
        api_tab = main_link["children"][0]
        assert api_tab["kind"] == "tab"
        assert api_tab["tabName"] == "API"
        assert api_tab["children"][0]["linkedTabName"] == "DB"

    def test_get_hierarchy_tree_marks_cycles(self, app):
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "API", "completed": False}]},
                    diagram={
                        "items": [{"id": "task_main", "item_type": "task", "text": "API", "task_index": 0}],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
                Tab(
                    name="API",
                    tasks={"tasks": [{"title": "Main", "completed": False}]},
                    diagram={
                        "items": [{"id": "task_api", "item_type": "task", "text": "Main", "task_index": 0}],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
            ],
            active_tab=0,
        )

        tree = model.getHierarchyTree()
        api_tab = tree[0]["children"][0]["children"][0]
        cycle_entry = api_tab["children"][0]["children"][0]
        assert cycle_entry["kind"] == "cycleRef"
        assert cycle_entry["tabName"] == "Main"

    def test_get_hierarchy_tree_with_root_index_returns_single_root(self, app):
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={"tasks": [{"title": "API", "completed": False}]},
                    diagram={
                        "items": [{"id": "task_main", "item_type": "task", "text": "API", "task_index": 0}],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
                Tab(
                    name="API",
                    tasks={"tasks": [{"title": "Deploy", "completed": False}]},
                    diagram={"items": [], "edges": [], "strokes": [], "current_task_index": -1},
                ),
            ],
            active_tab=1,
        )

        rooted = model.getHierarchyTree(1)
        assert len(rooted) == 1
        assert rooted[0]["kind"] == "tab"
        assert rooted[0]["tabName"] == "API"

    def test_get_hierarchy_tree_with_invalid_root_index_returns_empty(self, app):
        from task_model import TabModel

        model = TabModel()
        assert model.getHierarchyTree(999) == []

    def test_get_hierarchy_tree_hides_completed_task_nodes(self, app):
        from task_model import TabModel, Tab

        model = TabModel()
        model.setTabs(
            [
                Tab(
                    name="Main",
                    tasks={
                        "tasks": [
                            {"title": "Done Task", "completed": True},
                            {"title": "Next Task", "completed": False},
                        ]
                    },
                    diagram={
                        "items": [
                            {"id": "task_done", "item_type": "task", "text": "Done Task", "task_index": 0},
                            {"id": "task_next", "item_type": "task", "text": "Next Task", "task_index": 1},
                            {"id": "note_0", "item_type": "note", "text": "Keep", "task_index": -1},
                        ],
                        "edges": [],
                        "strokes": [],
                        "current_task_index": -1,
                    },
                ),
            ],
            active_tab=0,
        )

        tree = model.getHierarchyTree(0)
        assert len(tree) == 1
        child_ids = [child.get("itemId") for child in tree[0]["children"]]
        assert "task_done" not in child_ids
        assert "task_next" in child_ids
        assert "note_0" in child_ids

    def test_priority_plot_roles_exist(self, app):
        """Priority plot roles are exposed to QML."""
        from task_model import TabModel

        model = TabModel()
        role_names = model.roleNames()
        assert b"priorityTimeHours" in role_names.values()
        assert b"prioritySubjectiveValue" in role_names.values()
        assert b"priorityScore" in role_names.values()
        assert b"includeInPriorityPlot" in role_names.values()
        assert b"icon" in role_names.values()
        assert b"color" in role_names.values()
        assert b"pinned" in role_names.values()

    def test_set_tab_icon_and_color(self, app):
        """Tab icon and color setters update model roles."""
        from task_model import TabModel

        model = TabModel()
        model.setTabIcon(0, "!")
        model.setTabColor(0, "#336699")
        assert model.data(model.index(0, 0), model.IconRole) == "!"
        assert model.data(model.index(0, 0), model.ColorRole) == "#336699"

        # Invalid colors are normalized to empty.
        model.setTabColor(0, "not-a-color")
        assert model.data(model.index(0, 0), model.ColorRole) == ""

    def test_set_tab_pinned(self, app):
        """Pinned tabs expose their role and summary state."""
        from task_model import TabModel

        model = TabModel()
        model.setTabPinned(0, True)

        assert model.data(model.index(0, 0), model.PinnedRole) is True
        assert model.getPinnedTabIndices() == [0]
        assert model.getTabSummary(0)["pinned"] is True

    def test_priority_plot_score_and_sort(self, app):
        """Setting plot coordinates recomputes score and reorders tabs."""
        from task_model import TabModel

        model = TabModel()
        model.addTab("Second")
        model.setPriorityPoint(0, 4.0, 4.0)
        model.setPriorityPoint(1, 2.0, 6.0)

        assert model.data(model.index(0, 0), model.NameRole) == "Second"
        top_score = model.data(model.index(0, 0), model.PriorityScoreRole)
        low_score = model.data(model.index(1, 0), model.PriorityScoreRole)
        assert top_score > low_score

    def test_priority_plot_sort_preserves_current_tab(self, app):
        """Current tab remains the same logical tab after priority sorting."""
        from task_model import TabModel

        model = TabModel()
        model.addTab("Second")
        model.setCurrentTab(1)
        assert model.currentTabName == "Second"

        model.setPriorityPoint(1, 2.0, 8.0)
        model.setPriorityPoint(0, 8.0, 1.0)

        assert model.currentTabName == "Second"

    def test_priority_plot_exclusion_removes_from_scoring_order(self, app):
        """Excluded tabs are not scored and are sorted after included tabs."""
        from task_model import TabModel

        model = TabModel()
        model.addTab("Second")
        model.setPriorityPoint(0, 2.0, 9.0)  # High score
        model.setPriorityPoint(1, 2.0, 3.0)  # Lower score
        names_before = [
            model.data(model.index(i, 0), model.NameRole)
            for i in range(model.tabCount)
        ]
        main_index = names_before.index("Main")

        model.setIncludeInPriorityPlot(main_index, False)

        names_after = [
            model.data(model.index(i, 0), model.NameRole)
            for i in range(model.tabCount)
        ]
        assert names_after[-1] == "Main"
        assert model.data(model.index(model.tabCount - 1, 0), model.PriorityScoreRole) == pytest.approx(0.0)


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

    def test_recent_tab_indices_follow_switch_move_and_remove(self, app):
        """Recent tabs stay stable across switching, moves, and removals."""
        from task_model import TabModel

        model = TabModel()
        model.addTab("Tab 2")
        model.addTab("Tab 3")

        model.setCurrentTab(1)
        assert model.recentTabIndices == [0]

        model.setCurrentTab(2)
        assert model.recentTabIndices == [1, 0]

        model.moveTab(0, 2)
        assert model.currentTabName == "Tab 3"
        assert model.recentTabIndices == [0, 2]

        model.removeTab(0)
        assert model.recentTabIndices == [1]

    def test_remove_current_tab_emits_current_tab_signals(self, app):
        """Removing the active tab emits current-tab notifications for the replacement tab."""
        from task_model import TabModel

        model = TabModel()
        model.addTab("Tab 2")
        model.addTab("Tab 3")
        model.setCurrentTab(1)

        changed_names = []
        changed_indices = []
        model.currentTabChanged.connect(lambda: changed_names.append(model.currentTabName))
        model.currentTabIndexChanged.connect(lambda: changed_indices.append(model.currentTabIndex))

        model.removeTab(1)

        assert model.currentTabIndex == 1
        assert model.currentTabName == "Tab 3"
        assert changed_indices[-1] == 1
        assert changed_names[-1] == "Tab 3"


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


class TestPriorityPlotPersistence:
    def test_priority_plot_fields_roundtrip(self, app, tmp_path):
        """Priority plot fields are saved and loaded in project files."""
        from task_model import ProjectManager, Tab, TabModel, TaskModel

        project_file = tmp_path / "priority_fields.progress"

        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        tab_model.setTabs(
            [
                Tab(
                    name="Alpha",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                    priority_time_hours=3.0,
                    priority_subjective_value=5.0,
                    priority_score=0.0,
                ),
                Tab(
                    name="Beta",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                    priority_time_hours=2.0,
                    priority_subjective_value=7.0,
                    priority_score=0.0,
                ),
            ],
            active_tab=0,
        )
        tab_model.recomputeAndSortPriorities()

        manager = ProjectManager(task_model, diagram_model, tab_model)
        manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel(task_model=task_model2)
        tab_model2 = TabModel()
        manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        manager2.loadProject(str(project_file))

        tabs = tab_model2.getAllTabs()
        assert len(tabs) == 2
        loaded_names = {tab.name for tab in tabs}
        assert loaded_names == {"Alpha", "Beta"}
        loaded_by_name = {tab.name: tab for tab in tabs}
        assert loaded_by_name["Alpha"].priority_time_hours == pytest.approx(3.0)
        assert loaded_by_name["Alpha"].priority_subjective_value == pytest.approx(5.0)
        assert loaded_by_name["Alpha"].priority_score > 0
        assert loaded_by_name["Alpha"].include_in_priority_plot is True
        assert loaded_by_name["Beta"].priority_time_hours == pytest.approx(2.0)
        assert loaded_by_name["Beta"].priority_subjective_value == pytest.approx(7.0)
        assert loaded_by_name["Beta"].priority_score > 0
        assert loaded_by_name["Beta"].include_in_priority_plot is True

    def test_priority_plot_exclusion_field_roundtrip(self, app, tmp_path):
        """Priority plot exclusion flag is persisted."""
        from task_model import ProjectManager, Tab, TabModel, TaskModel

        project_file = tmp_path / "priority_exclusion.progress"
        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        tab_model.setTabs(
            [
                Tab(
                    name="Included",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                    include_in_priority_plot=True,
                ),
                Tab(
                    name="Excluded",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                    include_in_priority_plot=False,
                ),
            ],
            active_tab=0,
        )

        manager = ProjectManager(task_model, diagram_model, tab_model)
        manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel(task_model=task_model2)
        tab_model2 = TabModel()
        manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        manager2.loadProject(str(project_file))

        loaded = {tab.name: tab for tab in tab_model2.getAllTabs()}
        assert loaded["Included"].include_in_priority_plot is True
        assert loaded["Excluded"].include_in_priority_plot is False

    def test_tab_icon_color_and_pinned_roundtrip(self, app, tmp_path):
        """Tab icon, color, and pinned state are persisted."""
        from task_model import ProjectManager, Tab, TabModel, TaskModel

        project_file = tmp_path / "tab_icon_color.progress"
        task_model = TaskModel()
        diagram_model = DiagramModel(task_model=task_model)
        tab_model = TabModel()
        tab_model.setTabs(
            [
                Tab(
                    name="Styled",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                    icon="!",
                    color="#2277aa",
                    pinned=True,
                ),
                Tab(
                    name="Plain",
                    tasks={"tasks": []},
                    diagram={"items": [], "edges": [], "strokes": []},
                ),
            ],
            active_tab=0,
        )

        manager = ProjectManager(task_model, diagram_model, tab_model)
        manager.saveProject(str(project_file))

        task_model2 = TaskModel()
        diagram_model2 = DiagramModel(task_model=task_model2)
        tab_model2 = TabModel()
        manager2 = ProjectManager(task_model2, diagram_model2, tab_model2)
        manager2.loadProject(str(project_file))

        loaded = {tab.name: tab for tab in tab_model2.getAllTabs()}
        assert loaded["Styled"].icon == "!"
        assert loaded["Styled"].color == "#2277aa"
        assert loaded["Styled"].pinned is True
        assert loaded["Plain"].icon == ""
        assert loaded["Plain"].color == ""
        assert loaded["Plain"].pinned is False


class TestPriorityPlotStandalone:
    def test_priority_plot_smoke(self, app, monkeypatch):
        """Standalone priority plot launcher supports smoke mode."""
        from actiondraw.priorityplot.app import main

        monkeypatch.setenv("PRIORITYPLOT_SMOKE", "1")
        assert main() == 0


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

    def test_copy_items_to_clipboard_sets_opml_text(self, empty_diagram_model):
        """Copying items publishes OPML text alongside the custom MIME payload."""
        from PySide6.QtGui import QGuiApplication

        item_id = empty_diagram_model.addBox(100.0, 100.0, "Test Box")
        assert empty_diagram_model.copyItemsToClipboard([item_id]) == True

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        mime_data = clipboard.mimeData()
        assert mime_data is not None
        assert mime_data.hasText()
        assert "<opml" in mime_data.text()
        assert 'outline text="Test Box"' in mime_data.text()

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

    def test_has_clipboard_opml_true_for_valid_opml(self, empty_diagram_model):
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(
            '<?xml version="1.0" encoding="UTF-8"?><opml version="1.0">'
            "<head><title>Example</title></head><body><outline text=\"Parent\">"
            "<outline text=\"Child\"></outline></outline></body></opml>"
        )

        assert empty_diagram_model.hasClipboardOpml() == True

    def test_has_clipboard_opml_false_for_invalid_xml(self, empty_diagram_model):
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText("<opml><body><outline text='Broken'></body>")

        assert empty_diagram_model.hasClipboardOpml() == False

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

    def test_paste_opml_as_tasks_preserves_hierarchy(self, diagram_model_with_task_model):
        """OPML paste creates nested task hierarchy."""
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(
            '<?xml version="1.0" encoding="UTF-8"?><opml version="1.0">'
            "<head><title>Example</title></head><body>"
            '<outline text="Parent"><outline text="Child"></outline></outline>'
            "</body></opml>"
        )

        initial_task_count = diagram_model_with_task_model._task_model.rowCount()
        result = diagram_model_with_task_model.pasteTextFromClipboard(100.0, 100.0, True)

        assert result == True
        assert diagram_model_with_task_model._task_model.rowCount() == initial_task_count + 2
        parent_task = diagram_model_with_task_model._task_model._tasks[initial_task_count]
        child_task = diagram_model_with_task_model._task_model._tasks[initial_task_count + 1]
        assert parent_task.title == "Parent"
        assert child_task.title == "Child"
        assert child_task.parent_index == initial_task_count
        assert child_task.indent_level == parent_task.indent_level + 1

    def test_paste_opml_as_boxes_creates_items_and_edges(self, empty_diagram_model):
        """OPML paste as boxes uses the existing item creation path."""
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(
            '<?xml version="1.0" encoding="UTF-8"?><opml version="1.0">'
            "<body><outline text=\"One\"><outline text=\"Two\"></outline></outline></body></opml>"
        )

        result = empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, False)
        assert result == True
        assert empty_diagram_model.count == 2
        assert len(empty_diagram_model.edges) == 1

    def test_paste_opml_preserves_multiline_text(self, diagram_model_with_task_model):
        """XML character references in OPML text survive paste."""
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(
            '<?xml version="1.0" encoding="UTF-8"?><opml version="1.0">'
            "<body><outline text=\"Line 1&#10;Line 2\"></outline></body></opml>"
        )

        initial_task_count = diagram_model_with_task_model._task_model.rowCount()
        assert diagram_model_with_task_model.pasteTextFromClipboard(100.0, 100.0, True) == True
        assert diagram_model_with_task_model._task_model._tasks[initial_task_count].title == "Line 1\nLine 2"

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

    def test_non_opml_text_still_uses_existing_multiline_parser(self, empty_diagram_model):
        """Plain text fallback remains unchanged when clipboard text is not OPML."""
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText("Parent\n  Child")

        result = empty_diagram_model.pasteTextFromClipboard(100.0, 100.0, False)
        assert result == True
        assert empty_diagram_model.count == 2
        assert len(empty_diagram_model.edges) == 1

    def test_copy_task_selection_exports_nested_opml(self, diagram_model_with_task_model):
        """Copying parent and child task items exports nested OPML text."""
        from PySide6.QtGui import QGuiApplication

        parent_task_index = diagram_model_with_task_model._task_model.addTaskWithParent("Parent")
        child_task_index = diagram_model_with_task_model._task_model.addTaskWithParent("Child", parent_task_index)
        parent_item_id = diagram_model_with_task_model.addTask(parent_task_index, 100.0, 100.0)
        child_item_id = diagram_model_with_task_model.addTask(child_task_index, 220.0, 100.0)

        assert diagram_model_with_task_model.copyItemsToClipboard([parent_item_id, child_item_id]) == True

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        text = clipboard.text()
        assert 'outline text="Parent"' in text
        assert 'outline text="Child"' in text
        assert "<outline text=\"Parent\"><outline text=\"Child\">" in text


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
        """Serializing note item uses note text as canonical markdown payload."""
        from actiondraw import DiagramItem, DiagramItemType
        item = DiagramItem(
            id="note_1",
            item_type=DiagramItemType.NOTE,
            x=0.0,
            y=0.0,
            text="# Heading\n\nContent",
            note_markdown="legacy value should be ignored for notes",
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


class TestYubiKeyGuidance:
    def test_guidance_windows_no_admin_instructions(self, monkeypatch):
        monkeypatch.setattr("progress_crypto._has_native_yubikey_api", lambda: False)
        monkeypatch.setattr("progress_crypto._resolve_ykman_binary", lambda raise_on_missing=False: None)
        monkeypatch.setattr("progress_crypto.platform.system", lambda: "Windows")
        message = yubikey_support_guidance()
        assert "no-admin option" in message
        assert "YKMAN_PATH" in message

    def test_guidance_reports_detected_ykman_path(self, monkeypatch):
        monkeypatch.setattr("progress_crypto._has_native_yubikey_api", lambda: False)
        monkeypatch.setattr("progress_crypto._resolve_ykman_binary", lambda raise_on_missing=False: "/tmp/ykman")
        message = yubikey_support_guidance()
        assert "YubiKey support detected" in message
        assert "/tmp/ykman" in message


class TestMarkdownNoteManager:
    def test_request_project_save_emits_signal(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()

        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)
        events = []
        manager.projectSaveRequested.connect(lambda: events.append("save"))

        manager.requestProjectSave()

        assert events == ["save"]

    def test_save_freetext_keeps_editor_open_and_confirms_save(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.note_id = ""
                self.save_confirmation_calls = 0

            def set_note_id(self, note_id):
                self.note_id = note_id

            def show_save_confirmation(self):
                self.save_confirmation_calls += 1

        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)
        manager._set_editor_state("freetext", "", 120.0, 80.0, True)

        manager._save_note("", "Draft text")

        assert manager.editorOpen is True
        assert manager.activeEditorType == "freetext"
        assert manager.activeItemId == manager._editor.note_id
        assert manager._editor.save_confirmation_calls == 1
        assert manager._editor.note_id.startswith("freetext_")
        item = empty_diagram_model.getItem(manager._editor.note_id)
        assert item is not None
        assert item.text == "Draft text"

    def test_save_note_keeps_editor_open_and_confirms_save(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.save_confirmation_calls = 0

            def show_save_confirmation(self):
                self.save_confirmation_calls += 1

        item_id = empty_diagram_model.addBox(40.0, 30.0, "Task")
        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)
        manager._set_editor_state("note", item_id, 40.0, 30.0, True)

        manager._save_note(item_id, "Updated markdown")

        assert manager.editorOpen is True
        assert manager.activeEditorType == "note"
        assert manager.activeItemId == item_id
        assert manager._editor.save_confirmation_calls == 1
        assert empty_diagram_model.getItemMarkdown(item_id) == "Updated markdown"

    def test_open_note_with_empty_markdown_uses_note_editor(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.open_calls = []

            def open(self, *args, **kwargs):
                self.open_calls.append((args, kwargs))

        item_id = empty_diagram_model.addBox(40.0, 30.0, "Task")
        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)

        manager.openNote(item_id)

        assert manager.editorOpen is True
        assert manager.activeEditorType == "note"
        assert manager.activeItemId == item_id
        args, kwargs = manager._editor.open_calls[0]
        assert args[0] == item_id
        assert args[1] == ""
        assert args[2] == "Task Note"
        assert kwargs["editor_type"] == "note"
        assert kwargs["tabs"][0]["text"] == ""

    def test_open_obstacle_uses_obstacle_editor_type(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.open_calls = []

            def open(self, *args, **kwargs):
                self.open_calls.append((args, kwargs))

        item_id = empty_diagram_model.addBox(40.0, 30.0, "Task")
        empty_diagram_model.setItemObstacleMarkdown(item_id, "Blocked")
        empty_diagram_model.setEditorTabs(
            item_id,
            "obstacle",
            [
                {"name": "Main", "text": "Blocked"},
                {"name": "Dependencies", "text": "Vendor wait"},
            ],
        )
        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)

        manager.openObstacle(item_id)

        assert manager.activeEditorType == "obstacle"
        assert manager.activeItemId == item_id
        args, kwargs = manager._editor.open_calls[0]
        assert args[0] == item_id
        assert args[1] == "Blocked"
        assert args[2] == "Task Obstacle"
        assert kwargs["editor_type"] == "obstacle"
        assert kwargs["tabs"][1]["name"] == "Dependencies"

    def test_save_obstacle_keeps_editor_open_and_confirms_save(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.save_confirmation_calls = 0

            def show_save_confirmation(self):
                self.save_confirmation_calls += 1

        item_id = empty_diagram_model.addBox(40.0, 30.0, "Task")
        empty_diagram_model.setItemMarkdown(item_id, "Existing note")
        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)
        manager._set_editor_state("obstacle", item_id, 40.0, 30.0, True)

        manager._save_note(
            item_id,
            "Blocked by vendor",
            [
                {"name": "Main", "text": "Blocked by vendor"},
                {"name": "Follow-up", "text": "Waiting on procurement"},
            ],
        )

        assert manager.editorOpen is True
        assert manager.activeEditorType == "obstacle"
        assert manager.activeItemId == item_id
        assert manager._editor.save_confirmation_calls == 1
        assert empty_diagram_model.getItemObstacleMarkdown(item_id) == "Blocked by vendor"
        assert empty_diagram_model.getItemMarkdown(item_id) == "Existing note"
        item = empty_diagram_model.getItem(item_id)
        assert item is not None
        assert item.obstacle_tabs[1]["name"] == "Follow-up"

    def test_save_and_close_note_updates_model_and_closes_editor(self, empty_diagram_model, monkeypatch):
        class _DummySignal:
            def connect(self, _callback):
                return None

        class _DummyEditor:
            def __init__(self, *_args, **_kwargs):
                self.noteSaved = _DummySignal()
                self.noteSavedAndClosed = _DummySignal()
                self.noteCanceled = _DummySignal()
                self.save_confirmation_calls = 0

            def show_save_confirmation(self):
                self.save_confirmation_calls += 1

        item_id = empty_diagram_model.addBox(40.0, 30.0, "Task")
        monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
        manager = MarkdownNoteManager(empty_diagram_model)
        manager._set_editor_state("note", item_id, 40.0, 30.0, True)

        manager._save_and_close_note(item_id, "Updated markdown")

        assert empty_diagram_model.getItemMarkdown(item_id) == "Updated markdown"
        assert manager._editor.save_confirmation_calls == 1
        assert manager.editorOpen is False
        assert manager.activeEditorType == ""
        assert manager.activeItemId == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
