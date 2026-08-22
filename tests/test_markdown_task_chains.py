"""Tests for creating connected diagram tasks from Markdown dash lists."""

from __future__ import annotations

import pytest

from actiondraw.markdown_note_manager import MarkdownNoteManager
from actiondraw.markdown_task_list import parse_markdown_task_list
from actiondraw.model import DiagramModel
from actiondraw.qml import QML_DIR
from task_model import ProjectManager, TabModel, TaskModel


def test_parse_markdown_task_list_accepts_plain_dash_items_and_blank_lines():
    assert parse_markdown_task_list(
        "  - Put on shoes\n\n\t- Go outside\n- Open car  "
    ) == ["Put on shoes", "Go outside", "Open car"]


@pytest.mark.parametrize(
    "selection",
    [
        "- Only one",
        "- One\nprose",
        "- One\n-   ",
        "* One\n* Two",
        "+ One\n+ Two",
        "1. One\n2. Two",
        "- [ ] One\n- Two",
        "- [x] One\n- Two",
    ],
)
def test_parse_markdown_task_list_rejects_unsupported_selections(selection):
    assert parse_markdown_task_list(selection) == []


def test_item_markdown_list_appends_connected_horizontal_chain(app):
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    source_id = diagram_model.addPresetItemWithText("box", 50.0, 60.0, "Source")
    existing_id = diagram_model.createTaskFromMarkdownSelection(source_id, "Existing")
    existing = diagram_model.getItem(existing_id)

    created = diagram_model.createTasksFromMarkdownList(
        source_id,
        "- Put on shoes\n- Go outside\n- Open car",
    )

    assert len(created) == 3
    assert [diagram_model.getItem(item_id).text for item_id in created] == [
        "Put on shoes",
        "Go outside",
        "Open car",
    ]
    assert [diagram_model.getItem(item_id).x for item_id in created] == [
        existing.x + existing.width + 100.0,
        existing.x + 2 * (existing.width + 100.0),
        existing.x + 3 * (existing.width + 100.0),
    ]
    expected_edges = list(zip([existing_id, *created[:-1]], created))
    actual_edges = {(edge["fromId"], edge["toId"]) for edge in diagram_model.edges}
    assert all(edge in actual_edges for edge in expected_edges)
    assert all(task.parent_index == -1 for task in task_model._tasks)


def test_workspace_markdown_list_starts_at_requested_position(app):
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    project_manager = ProjectManager(task_model, diagram_model, TabModel())

    created = project_manager.createTasksFromWorkspaceMarkdownList(
        "- First\n- Second\n- Third",
        410.0,
        260.0,
    )

    assert len(created) == 3
    items = [diagram_model.getItem(item_id) for item_id in created]
    assert [(item.x, item.y) for item in items] == [
        (410.0, 260.0),
        (650.0, 260.0),
        (890.0, 260.0),
    ]
    assert {
        (edge["fromId"], edge["toId"]) for edge in diagram_model.edges
    } == {(created[0], created[1]), (created[1], created[2])}
    assert all(task.parent_index == -1 for task in task_model._tasks)


def test_manager_routes_workspace_list_and_emits_each_created_id(app, monkeypatch):
    class _DummySignal:
        def connect(self, _callback):
            return None

    class _DummyEditor:
        def __init__(self, *_args, **_kwargs):
            self.noteSaved = _DummySignal()
            self.noteSavedAndClosed = _DummySignal()
            self.noteCanceled = _DummySignal()

    class _DummyProjectManager:
        def createTasksFromWorkspaceMarkdownList(self, selected_text, x, y):
            assert selected_text == "- One\n- Two"
            assert (x, y) == (300.0, 200.0)
            return ["task_10", "task_11"]

    monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
    manager = MarkdownNoteManager(DiagramModel(), _DummyProjectManager())
    events = []
    manager.taskCreated.connect(events.append)

    created = manager.createTasksFromEditorList(
        "workspace", "", 300.0, 200.0, "ignored", "- One\n- Two"
    )

    assert created == ["task_10", "task_11"]
    assert events == created


def test_manager_creates_freetext_source_before_attaching_list(app, monkeypatch):
    class _DummySignal:
        def connect(self, _callback):
            return None

    class _DummyEditor:
        def __init__(self, *_args, **_kwargs):
            self.noteSaved = _DummySignal()
            self.noteSavedAndClosed = _DummySignal()
            self.noteCanceled = _DummySignal()

    monkeypatch.setattr("actiondraw.markdown_note_manager.MarkdownNoteEditor", _DummyEditor)
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    manager = MarkdownNoteManager(diagram_model)

    created = manager.createTasksFromEditorList(
        "freetext", "", 25.0, 35.0, "Planning note", "- One\n- Two"
    )

    assert len(created) == 2
    source_id = manager.activeItemId
    assert source_id.startswith("freetext_")
    assert diagram_model.getItem(source_id).text == "Planning note"
    assert any(
        edge["fromId"] == source_id and edge["toId"] == created[0]
        for edge in diagram_model.edges
    )


def test_markdown_editor_qml_exposes_list_action_and_body_highlighting():
    pane = (QML_DIR / "components" / "MarkdownEditorPane.qml").read_text(encoding="utf-8")
    window = (QML_DIR / "MarkdownNoteEditorWindow.qml").read_text(encoding="utf-8")

    assert 'text: "Create Tasks from List"' in pane
    assert "dashTaskListItems" in pane
    assert "highlightCurrentTaskListSelection" in pane
    assert "match[1] + root._taskHighlightStart + title" in pane
    assert "createTaskListRequested(selected)" in pane
    assert "markdownNoteManager.createTasksFromEditorList" in window
    assert 'text: "Create Task"' in pane
