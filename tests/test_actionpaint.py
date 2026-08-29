"""Tests for Action Paint state, persistence, and ActionDraw import integration."""

from actiondraw.actionpaint import ActionPaintModel, empty_action_paint_state
from actiondraw.model import DiagramModel
from actiondraw.ui import create_actiondraw_window
from progress_crypto import EncryptionCredentials
from task_model import ProjectManager, TabModel, TaskModel


def test_action_edit_move_delete_and_reorder(app):
    model = ActionPaintModel()
    first = model.addAction("Wash car", 100, 120)
    second = model.addAction("Fix vacuum cleaner", 300, 320)

    assert [item["order"] for item in model.actions] == [1, 2]
    model.moveAction(1, 0)
    assert model.orderedTitles == ["Fix vacuum cleaner", "Wash car"]
    assert [item["order"] for item in model.actions] == [1, 2]

    model.renameAction(first, "Wash and wax car")
    model.moveActionMarker(second, 350, 360)
    moved = next(item for item in model.actions if item["id"] == second)
    assert (moved["x"], moved["y"]) == (350.0, 360.0)

    model.removeAction(second)
    assert model.orderedTitles == ["Wash and wax car"]
    assert model.actions[0]["order"] == 1


def test_drawing_tools_undo_and_clear_preserve_actions(app):
    model = ActionPaintModel()
    model.addAction("Keep me", 20, 30)
    model.startDrawing("pencil", 1, 2, "#000000", 3)
    model.continueDrawing(4, 5)
    model.endDrawing()
    model.startDrawing("line", 10, 20, "#ff0000", 6)
    model.continueDrawing(30, 40)
    model.endDrawing()
    model.startDrawing("rectangle", 50, 60, "#00ff00", 8)
    model.continueDrawing(100, 120)
    model.endDrawing()
    text_id = model.addText("Garage", 130, 140, "#2962ff", 28)

    assert text_id.startswith("paint_")
    assert [item["type"] for item in model.elements] == ["pencil", "line", "rectangle", "text"]
    assert model.elements[0]["points"][-1] == {"x": 4.0, "y": 5.0}
    assert model.elements[1]["x2"] == 30.0
    assert model.elements[2]["y2"] == 120.0

    assert model.elements[3]["text"] == "Garage"
    assert model.elements[3]["font_size"] == 28.0
    model.undoLastDrawing()
    assert [item["type"] for item in model.elements] == ["pencil", "line", "rectangle"]
    model.clearDrawing()
    assert model.elements == []
    assert model.orderedTitles == ["Keep me"]


def test_import_signature_blocks_duplicates_until_semantic_change(app):
    model = ActionPaintModel()
    action_id = model.addAction("One", 10, 20)
    model.markImported()
    assert model.imported is True

    model.moveActionMarker(action_id, 100, 200)
    assert model.imported is True

    model.renameAction(action_id, "One changed")
    assert model.imported is False


def test_eraser_removes_touched_element_and_undo_restores_it(app):
    model = ActionPaintModel()
    model.startDrawing("line", 10, 20, "#000000", 4)
    model.continueDrawing(110, 20)
    model.endDrawing()
    assert model.canUndo is True

    model.beginErase()
    assert model.eraseAt(60, 21, 8) is True
    model.endErase()
    assert model.elements == []

    model.undoLastDrawing()
    assert len(model.elements) == 1
    assert model.elements[0]["type"] == "line"
    model.markImported()
    model.addAction("Two", 30, 40)
    assert model.imported is False


def test_state_round_trip_keeps_order_and_import_status(app):
    model = ActionPaintModel()
    model.addAction("A", 1, 2)
    model.addAction("B", 3, 4)
    model.moveAction(1, 0)
    model.markImported()
    state = model.to_dict()

    restored = ActionPaintModel()
    restored.from_dict(state)
    assert restored.orderedTitles == ["B", "A"]
    assert restored.imported is True


def test_actiondraw_creates_connected_chain_at_position(app):
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    created = diagram_model.createTaskChainAtPosition(["First", "Second", "Third"], 250, 300)

    assert len(created) == 3
    assert task_model.rowCount() == 3
    assert [(edge["fromId"], edge["toId"]) for edge in diagram_model.edges] == list(zip(created, created[1:]))
    positions = [(diagram_model.getItem(item_id).x, diagram_model.getItem(item_id).y) for item_id in created]
    assert positions == [(250.0, 300.0), (490.0, 300.0), (730.0, 300.0)]
    assert diagram_model.createTaskChainAtPosition([], 0, 0) == []
    assert diagram_model.createTaskChainAtPosition(["valid", "  "], 0, 0) == []


def test_action_paint_is_isolated_per_tab_and_serialized(app):
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    tab_model = TabModel()
    manager = ProjectManager(task_model, diagram_model, tab_model)
    paint = ActionPaintModel(tab_model=tab_model)

    paint.addAction("Main action", 10, 20)
    tab_model.addTab("Garage")
    manager.switchTab(1)
    assert paint.orderedTitles == []
    paint.addAction("Garage action", 30, 40)

    payload = manager._build_project_data()
    assert payload["tabs"][0]["action_paint"]["actions"][0]["text"] == "Main action"
    assert payload["tabs"][1]["action_paint"]["actions"][0]["text"] == "Garage action"

    manager.switchTab(0)
    assert paint.orderedTitles == ["Main action"]


def test_legacy_tab_defaults_to_empty_action_paint(app):
    tab_model = TabModel()
    assert tab_model.getCurrentTabData().action_paint == empty_action_paint_state()


def test_encrypted_project_round_trip_and_dirty_detection(app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        ProjectManager,
        "_prompt_encryption_credentials",
        lambda self, operation, file_path, envelope=None: EncryptionCredentials(passphrase="paint-test"),
    )
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    tab_model = TabModel()
    manager = ProjectManager(task_model, diagram_model, tab_model)
    paint = ActionPaintModel(tab_model=tab_model)
    manager._last_saved_snapshot = manager._serialize_project_payload(manager._build_project_data())
    assert manager.hasUnsavedChanges() is False

    paint.addAction("Persist me", 44, 55)
    assert manager.hasUnsavedChanges() is True
    path = tmp_path / "paint.progress"
    assert manager.saveProject(str(path)) is True

    task_model_2 = TaskModel()
    diagram_model_2 = DiagramModel(task_model=task_model_2)
    tab_model_2 = TabModel()
    manager_2 = ProjectManager(task_model_2, diagram_model_2, tab_model_2)
    paint_2 = ActionPaintModel(tab_model=tab_model_2)
    manager_2.loadProject(str(path))
    assert paint_2.orderedTitles == ["Persist me"]


def test_actionpaint_qml_and_toolbar_are_wired():
    paint_qml = open("actiondraw/qml_ui/ActionPaintWindow.qml", encoding="utf-8").read()
    toolbar_qml = open("actiondraw/qml_ui/components/ToolbarRow.qml", encoding="utf-8").read()
    window_qml = open("actiondraw/qml_ui/ActionDrawWindow.qml", encoding="utf-8").read()

    assert "Add to ActionDraw" in paint_qml
    assert 'root.activeTool === "pencil"' in paint_qml
    assert 'root.activeTool === "text"' in paint_qml
    assert 'root.activeTool === "eraser"' in paint_qml
    assert "paintModel.addText" in paint_qml
    assert "paintModel.eraseAt" in paint_qml
    assert "sequences: [StandardKey.Undo]" in paint_qml
    assert "paintModel.moveAction" in paint_qml
    assert "preventStealing: true" in paint_qml
    assert "function updateCanvasInteraction()" in paint_qml
    assert "Action Paint" in toolbar_qml
    assert "openActionPaintWindow" in window_qml


def test_integrated_actionpaint_window_opens(app):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest

    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    tab_model = TabModel()
    manager = ProjectManager(task_model, diagram_model, tab_model)
    engine = create_actiondraw_window(diagram_model, task_model, manager, tab_model=tab_model)
    root = engine.rootObjects()[0]

    root.openActionPaintWindow()
    app.processEvents()
    paint_window = root.property("actionPaintWindowRef")
    assert paint_window is not None
    assert paint_window.property("hostRoot") == root
    paint_window.setProperty("activeTool", "pencil")
    QTest.mousePress(paint_window, Qt.LeftButton, Qt.NoModifier, QPoint(120, 160))
    QTest.mouseMove(paint_window, QPoint(150, 180), 5)
    QTest.mouseMove(paint_window, QPoint(190, 210), 5)
    QTest.mouseMove(paint_window, QPoint(230, 240), 5)
    QTest.mouseRelease(paint_window, Qt.LeftButton, Qt.NoModifier, QPoint(230, 240))
    app.processEvents()
    assert len(engine._action_paint_model.elements) == 1
    assert len(engine._action_paint_model.elements[0]["points"]) >= 3
    QTest.keyClick(paint_window, Qt.Key_Z, Qt.ControlModifier)
    app.processEvents()
    assert engine._action_paint_model.elements == []

    engine._action_paint_model.addAction("First", 100, 100)
    engine._action_paint_model.addAction("Second", 200, 200)
    app.processEvents()
    first_handle = paint_window.actionDragHandleAt(0)
    second_handle = paint_window.actionDragHandleAt(1)
    assert first_handle is not None
    assert second_handle is not None
    start = first_handle.mapToScene(QPointF(20, 25)).toPoint()
    end = second_handle.mapToScene(QPointF(20, 25)).toPoint()
    QTest.mousePress(paint_window, Qt.LeftButton, Qt.NoModifier, start)
    QTest.mouseMove(paint_window, end, 10)
    QTest.mouseRelease(paint_window, Qt.LeftButton, Qt.NoModifier, end)
    app.processEvents()
    assert engine._action_paint_model.orderedTitles == ["Second", "First"]
    paint_window.close()
