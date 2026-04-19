"""Tests for the embedded ActionDraw MCP server."""

from __future__ import annotations

import asyncio
import time

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from actiondraw import DiagramModel
from actiondraw.mcp_server import (
    ActionDrawMcpBackend,
    ActionDrawMcpServerController,
    build_actiondraw_mcp_server,
)
from task_model import ProjectManager, TabModel, TaskModel


def _process_events_until(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    QCoreApplication.processEvents()
    assert predicate()


def _sample_backend() -> ActionDrawMcpBackend:
    task_model = TaskModel()
    task_model.addTask("Ship MCP server", -1)
    task_model.addTask("Review tabs", -1)
    task_model.toggleComplete(1, True)
    task_model._tasks[0].reminder_at = time.time() + 3600
    task_model._tasks[0].contract_deadline_at = time.time() + 7200
    task_model._tasks[0].contract_punishment = "Write a postmortem"

    diagram_model = DiagramModel(task_model=task_model)
    diagram_model.addTask(0, 100.0, 100.0)
    diagram_model.setCurrentTask(0)

    tab_model = TabModel()
    project_manager = ProjectManager(task_model, diagram_model, tab_model)
    project_manager.setWorkspaceMarkdownTabs([
        {"name": "Inbox", "text": "Project-wide markdown"},
    ])
    tab_model.getAllTabs()[0].markdown_tabs = [
        {"name": "Overview", "text": "Main tab markdown"},
    ]

    tab_model.addTab("Later")
    later_tasks = TaskModel()
    later_tasks.addTask("Deep work block", -1)
    tab_model.getAllTabs()[1].markdown_tabs = [
        {"name": "Plan", "text": "Later tab markdown"},
    ]
    tab_model.setTabData(
        1,
        later_tasks.to_dict(),
        {"items": [], "edges": [], "strokes": [], "current_task_index": -1},
    )

    return ActionDrawMcpBackend(
        task_model,
        diagram_model,
        project_manager=project_manager,
        tab_model=tab_model,
    )


def _call_tool(server, name: str, arguments: dict) -> object:
    result = asyncio.run(server.call_tool(name, arguments))
    if isinstance(result, tuple):
        if len(result) >= 2 and isinstance(result[1], dict) and "result" in result[1]:
            return result[1]["result"]
        if len(result) == 1:
            return result[0]
    return result


class TestBuildActionDrawMcpServer:
    def test_registers_expected_tools(self, app):
        backend = _sample_backend()
        server = build_actiondraw_mcp_server(backend.get_snapshot, backend)

        tools = asyncio.run(server.list_tools())
        names = {tool.name for tool in tools}

        assert {
            "get_project_summary",
            "list_tabs",
            "list_tasks",
            "list_diagram_items",
            "get_tab_snapshot",
            "get_project_snapshot",
            "get_active_reminders",
            "get_active_contracts",
            "get_hierarchy_tree",
            "summarize_project_state",
            "identify_focus_items",
            "explain_tab_hierarchy",
            "add_tab",
            "switch_tab",
            "add_task",
            "set_task_completed",
            "create_diagram_task_from_text",
        } <= names

    def test_read_tools_reflect_live_state(self, app):
        backend = _sample_backend()
        server = build_actiondraw_mcp_server(backend.get_snapshot, backend)

        summary = _call_tool(server, "get_project_summary", {})
        tabs = _call_tool(server, "list_tabs", {})
        current_tasks = _call_tool(server, "list_tasks", {})
        later_tasks = _call_tool(server, "list_tasks", {"tab_index": 1})
        items = _call_tool(server, "list_diagram_items", {})
        snapshot = _call_tool(server, "get_project_snapshot", {})
        focus_items = _call_tool(server, "identify_focus_items", {"limit": 3})

        assert summary["currentTabName"] == "Main"
        assert len(tabs) == 2
        assert current_tasks[0]["title"] == "Ship MCP server"
        assert later_tasks[0]["title"] == "Deep work block"
        assert items[0]["item_type"] == "task"
        assert snapshot["project"]["workspaceMarkdownTabs"] == [
            {"name": "Inbox", "text": "Project-wide markdown"},
        ]
        assert snapshot["tabs"][0]["tabMarkdownTabs"] == [
            {"name": "Overview", "text": "Main tab markdown"},
        ]
        assert snapshot["tabs"][1]["tabMarkdownTabs"] == [
            {"name": "Plan", "text": "Later tab markdown"},
        ]
        assert focus_items["items"]

    def test_mutation_tools_update_models(self, app):
        backend = _sample_backend()
        server = build_actiondraw_mcp_server(backend.get_snapshot, backend)

        added_tab = _call_tool(server, "add_tab", {"name": "Inbox"})
        added_task = _call_tool(server, "add_task", {"title": "Inbox zero", "tab_index": 2})
        completed = _call_tool(
            server,
            "set_task_completed",
            {"tab_index": 2, "task_index": 0, "completed": True},
        )
        switched = _call_tool(server, "switch_tab", {"tab_index": 1})
        created_item = _call_tool(
            server,
            "create_diagram_task_from_text",
            {"text": "Sketch next step", "x": 240.0, "y": 120.0},
        )

        assert added_tab["name"] == "Inbox"
        assert added_task["task"]["title"] == "Inbox zero"
        assert completed["task"]["completed"] is True
        assert switched["name"] == "Later"
        assert created_item["item"]["type"] == "task"


class _FakeServer:
    created_count = 0

    def __init__(self, config):
        type(self).created_count += 1
        self.config = config
        self.started = False
        self.should_exit = False
        self.force_exit = False

    async def serve(self):
        self.started = True
        while not self.should_exit:
            await asyncio.sleep(0.01)


class _FailingServer:
    def __init__(self, config):
        self.config = config
        self.started = False
        self.should_exit = False
        self.force_exit = False

    async def serve(self):
        raise RuntimeError("port already in use")


class TestActionDrawMcpServerController:
    def test_start_stop_and_duplicate_start(self, app):
        backend = _sample_backend()
        _FakeServer.created_count = 0
        controller = ActionDrawMcpServerController(
            backend._task_model,
            backend._diagram_model,
            project_manager=backend._project_manager,
            tab_model=backend._tab_model,
            uvicorn_server_factory=_FakeServer,
        )

        controller.start()
        controller.start()
        _process_events_until(lambda: controller.status == "running")

        assert controller.running is True
        assert controller.serverUrl.endswith("/mcp")
        assert _FakeServer.created_count == 1

        controller.stop()
        _process_events_until(lambda: controller.status == "stopped")
        assert controller.running is False
        assert controller.serverUrl.endswith("/mcp")

    def test_startup_failure_sets_error(self, app):
        backend = _sample_backend()
        controller = ActionDrawMcpServerController(
            backend._task_model,
            backend._diagram_model,
            project_manager=backend._project_manager,
            tab_model=backend._tab_model,
            uvicorn_server_factory=_FailingServer,
        )

        controller.start()
        _process_events_until(lambda: controller.status == "error")

        assert "port already in use" in controller.lastError

    def test_copy_add_commands(self, app):
        backend = _sample_backend()
        controller = ActionDrawMcpServerController(
            backend._task_model,
            backend._diagram_model,
            project_manager=backend._project_manager,
            tab_model=backend._tab_model,
        )

        assert controller.claudeAddCommand == "claude mcp add --transport http actiondraw http://127.0.0.1:8765/mcp"
        assert controller.codexAddCommand == "codex mcp add actiondraw --url http://127.0.0.1:8765/mcp"

        assert controller.copyClaudeAddCommand() is True
        assert QGuiApplication.clipboard().text() == controller.claudeAddCommand

        assert controller.copyCodexAddCommand() is True
        assert QGuiApplication.clipboard().text() == controller.codexAddCommand
