"""Embedded FastMCP server support for ActionDraw."""

from __future__ import annotations

import asyncio
import copy
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Qt, QThread, Signal, Slot
from PySide6.QtGui import QGuiApplication
from mcp.server.fastmcp import FastMCP
import uvicorn

from task_model import ProjectManager, TabModel, TaskModel

from .model import DiagramModel

DEFAULT_MCP_HOST = "127.0.0.1"
DEFAULT_MCP_PORT = 8765
DEFAULT_MCP_PATH = "/mcp"
DEFAULT_MCP_SERVER_NAME = "actiondraw"


@dataclass
class _CallRequest:
    callback: Callable[[], Any]
    result: Any = None
    error: BaseException | None = None


class _MainThreadExecutor(QObject):
    """Run callables on the Qt owner thread and wait for the result."""

    executeRequested = Signal(object)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.executeRequested.connect(self._execute, Qt.ConnectionType.BlockingQueuedConnection)

    def call(self, callback: Callable[[], Any]) -> Any:
        if QThread.currentThread() is self.thread():
            return callback()
        request = _CallRequest(callback=callback)
        self.executeRequested.emit(request)
        if request.error is not None:
            raise request.error
        return request.result

    @Slot(object)
    def _execute(self, request: _CallRequest) -> None:
        try:
            request.result = request.callback()
        except BaseException as exc:  # pragma: no cover - pass through exact failure
            request.error = exc


class ActionDrawMcpBackend:
    """Thread-safe backend for reading and mutating live ActionDraw state."""

    def __init__(
        self,
        task_model: TaskModel,
        diagram_model: DiagramModel,
        project_manager: ProjectManager | None = None,
        tab_model: TabModel | None = None,
    ):
        self._task_model = task_model
        self._diagram_model = diagram_model
        self._project_manager = project_manager
        self._tab_model = tab_model
        self._executor = _MainThreadExecutor()

    def get_snapshot(self) -> Dict[str, Any]:
        return self._executor.call(self._build_snapshot)

    def add_tab(self, name: str) -> Dict[str, Any]:
        return self._executor.call(lambda: self._add_tab(name))

    def switch_tab(self, tab_index: int) -> Dict[str, Any]:
        return self._executor.call(lambda: self._switch_tab(tab_index))

    def add_task(self, title: str, tab_index: int | None = None, parent_task_index: int = -1) -> Dict[str, Any]:
        return self._executor.call(lambda: self._add_task(title, tab_index, parent_task_index))

    def set_task_completed(
        self,
        task_index: int,
        completed: bool,
        tab_index: int | None = None,
    ) -> Dict[str, Any]:
        return self._executor.call(lambda: self._set_task_completed(task_index, completed, tab_index))

    def create_diagram_task_from_text(self, text: str, x: float, y: float) -> Dict[str, Any]:
        return self._executor.call(lambda: self._create_diagram_task_from_text(text, x, y))

    def _copy_payload(self, payload: Any) -> Any:
        return copy.deepcopy(payload)

    def _active_tab_index(self) -> int:
        if self._tab_model is not None:
            return int(self._tab_model.currentTabIndex)
        return 0

    def _tab_name(self, tab_index: int) -> str:
        if self._tab_model is None:
            return "Main"
        tabs = self._tab_model.getAllTabs()
        if 0 <= tab_index < len(tabs):
            name = str(getattr(tabs[tab_index], "name", "") or "").strip()
            if name:
                return name
        return "Main" if tab_index == 0 else f"Tab {tab_index + 1}"

    def _serialize_tab(self, tab_index: int) -> Dict[str, Any]:
        current_tab_index = self._active_tab_index()
        if self._tab_model is None:
            tasks_payload = self._task_model.to_dict()
            diagram_payload = self._diagram_model.to_dict()
            name = "Main"
            extra: Dict[str, Any] = {}
        else:
            tabs = self._tab_model.getAllTabs()
            if tab_index < 0 or tab_index >= len(tabs):
                raise IndexError(f"Invalid tab index: {tab_index}")
            tab = tabs[tab_index]
            if tab_index == current_tab_index:
                tasks_payload = self._task_model.to_dict()
                diagram_payload = self._diagram_model.to_dict()
            else:
                tasks_payload = self._copy_payload(tab.tasks)
                diagram_payload = self._copy_payload(tab.diagram)
            name = str(getattr(tab, "name", "") or self._tab_name(tab_index))
            extra = {
                "priority": getattr(tab, "priority", 0),
                "priorityTimeHours": float(getattr(tab, "priority_time_hours", 1.01)),
                "prioritySubjectiveValue": float(getattr(tab, "priority_subjective_value", 1.0)),
                "priorityScore": float(getattr(tab, "priority_score", 0.0)),
                "includeInPriorityPlot": bool(getattr(tab, "include_in_priority_plot", True)),
                "icon": str(getattr(tab, "icon", "") or ""),
                "color": str(getattr(tab, "color", "") or ""),
                "pinned": bool(getattr(tab, "pinned", False)),
                "goals": self._copy_payload(getattr(tab, "goals", [])),
            }

        tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
        diagram_items = diagram_payload.get("items", []) if isinstance(diagram_payload, dict) else []
        completed_count = sum(1 for task in tasks if isinstance(task, dict) and bool(task.get("completed", False)))
        active_task_title = ""
        current_task_index = -1
        if isinstance(diagram_payload, dict):
            current_task_index = int(diagram_payload.get("current_task_index", -1))
        if 0 <= current_task_index < len(tasks) and isinstance(tasks[current_task_index], dict):
            active_task_title = str(tasks[current_task_index].get("title", "") or "")

        result = {
            "tabIndex": tab_index,
            "name": name,
            "isCurrentTab": tab_index == current_tab_index,
            "taskCount": len(tasks),
            "completedTaskCount": completed_count,
            "incompleteTaskCount": max(0, len(tasks) - completed_count),
            "diagramItemCount": len(diagram_items),
            "activeTaskTitle": active_task_title,
            "tasks": self._copy_payload(tasks_payload),
            "diagram": self._copy_payload(diagram_payload),
        }
        result.update(extra)
        return result

    def _build_snapshot(self) -> Dict[str, Any]:
        if self._tab_model is None:
            tabs = [self._serialize_tab(0)]
        else:
            tabs = [self._serialize_tab(index) for index in range(self._tab_model.tabCount)]

        reminders = []
        contracts = []
        hierarchy = []
        workspace_tabs: List[Dict[str, str]] = []
        current_file_path = ""
        if self._project_manager is not None:
            reminders = self._copy_payload(self._project_manager.getActiveReminders())
            contracts = self._copy_payload(self._project_manager.getActiveContracts())
            workspace_tabs = self._copy_payload(self._project_manager.getWorkspaceMarkdownTabs())
            current_file_path = str(self._project_manager.currentFilePath or "")
        if self._tab_model is not None:
            hierarchy = self._copy_payload(self._tab_model.getHierarchyTree())

        total_tasks = sum(int(tab.get("taskCount", 0)) for tab in tabs)
        completed_tasks = sum(int(tab.get("completedTaskCount", 0)) for tab in tabs)
        total_items = sum(int(tab.get("diagramItemCount", 0)) for tab in tabs)
        current_tab_index = self._active_tab_index()
        current_tab_name = self._tab_name(current_tab_index)
        return {
            "project": {
                "currentFilePath": current_file_path,
                "currentTabIndex": current_tab_index,
                "currentTabName": current_tab_name,
                "tabCount": len(tabs),
                "totalTasks": total_tasks,
                "completedTasks": completed_tasks,
                "incompleteTasks": max(0, total_tasks - completed_tasks),
                "diagramItemCount": total_items,
                "workspaceMarkdownTabs": workspace_tabs,
            },
            "tabs": tabs,
            "reminders": reminders,
            "contracts": contracts,
            "hierarchy": hierarchy,
            "generatedAt": time.time(),
        }

    def _resolve_tab_index(self, tab_index: int | None) -> int:
        resolved = self._active_tab_index() if tab_index is None else int(tab_index)
        if self._tab_model is None:
            if resolved != 0:
                raise ValueError("Only the main tab is available")
            return 0
        if resolved < 0 or resolved >= self._tab_model.tabCount:
            raise ValueError(f"Invalid tab index: {resolved}")
        return resolved

    def _task_payload_model(self, payload: Dict[str, Any]) -> TaskModel:
        model = TaskModel()
        model.from_dict(self._copy_payload(payload))
        return model

    def _set_noncurrent_tab_tasks(self, tab_index: int, tasks_payload: Dict[str, Any]) -> None:
        if self._tab_model is None:
            raise ValueError("Tabs are not available")
        tabs = self._tab_model.getAllTabs()
        tab = tabs[tab_index]
        self._tab_model.setTabData(
            tab_index,
            self._copy_payload(tasks_payload),
            self._copy_payload(tab.diagram),
        )

    def _add_tab(self, name: str) -> Dict[str, Any]:
        if self._tab_model is None:
            raise ValueError("Tabs are not available")
        normalized = str(name or "").strip()
        self._tab_model.addTab(normalized)
        created_index = self._tab_model.tabCount - 1
        return self._serialize_tab(created_index)

    def _switch_tab(self, tab_index: int) -> Dict[str, Any]:
        resolved = self._resolve_tab_index(tab_index)
        if self._project_manager is None:
            raise ValueError("Project manager is not available")
        self._project_manager.switchTab(resolved)
        return self._serialize_tab(resolved)

    def _add_task(self, title: str, tab_index: int | None, parent_task_index: int) -> Dict[str, Any]:
        normalized = str(title or "").strip()
        if not normalized:
            raise ValueError("Task title is required")

        resolved_tab_index = self._resolve_tab_index(tab_index)
        if resolved_tab_index == self._active_tab_index():
            task_index = self._task_model.addTaskWithParent(normalized, int(parent_task_index))
        else:
            if self._tab_model is None:
                raise ValueError("Tabs are not available")
            tasks_payload = self._serialize_tab(resolved_tab_index)["tasks"]
            temp_model = self._task_payload_model(tasks_payload)
            task_index = temp_model.addTaskWithParent(normalized, int(parent_task_index))
            self._set_noncurrent_tab_tasks(resolved_tab_index, temp_model.to_dict())

        return {
            "tabIndex": resolved_tab_index,
            "tabName": self._tab_name(resolved_tab_index),
            "taskIndex": task_index,
            "task": self._serialize_tab(resolved_tab_index)["tasks"]["tasks"][task_index],
        }

    def _set_task_completed(self, task_index: int, completed: bool, tab_index: int | None) -> Dict[str, Any]:
        resolved_tab_index = self._resolve_tab_index(tab_index)
        resolved_task_index = int(task_index)

        if resolved_tab_index == self._active_tab_index():
            if resolved_task_index < 0 or resolved_task_index >= self._task_model.rowCount():
                raise ValueError(f"Invalid task index: {resolved_task_index}")
            self._task_model.toggleComplete(resolved_task_index, bool(completed))
        else:
            tasks_payload = self._serialize_tab(resolved_tab_index)["tasks"]
            temp_model = self._task_payload_model(tasks_payload)
            if resolved_task_index < 0 or resolved_task_index >= temp_model.rowCount():
                raise ValueError(f"Invalid task index: {resolved_task_index}")
            temp_model.toggleComplete(resolved_task_index, bool(completed))
            self._set_noncurrent_tab_tasks(resolved_tab_index, temp_model.to_dict())

        return {
            "tabIndex": resolved_tab_index,
            "tabName": self._tab_name(resolved_tab_index),
            "taskIndex": resolved_task_index,
            "completed": bool(completed),
            "task": self._serialize_tab(resolved_tab_index)["tasks"]["tasks"][resolved_task_index],
        }

    def _create_diagram_task_from_text(self, text: str, x: float, y: float) -> Dict[str, Any]:
        normalized = str(text or "").strip()
        if not normalized:
            raise ValueError("Task text is required")
        item_id = str(self._diagram_model.addTaskFromText(normalized, float(x), float(y)) or "")
        if not item_id:
            raise RuntimeError("Failed to create diagram task")
        return {
            "tabIndex": self._active_tab_index(),
            "tabName": self._tab_name(self._active_tab_index()),
            "item": self._copy_payload(self._diagram_model.getItemSnapshot(item_id)),
        }


def _clone_snapshot(snapshot_getter: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    return copy.deepcopy(snapshot_getter())


def _resolve_tab(snapshot: Dict[str, Any], tab_index: int | None) -> Dict[str, Any]:
    tabs = snapshot.get("tabs", [])
    if not isinstance(tabs, list) or not tabs:
        raise ValueError("No tabs are available")
    resolved = snapshot.get("project", {}).get("currentTabIndex", 0) if tab_index is None else int(tab_index)
    if resolved < 0 or resolved >= len(tabs):
        raise ValueError(f"Invalid tab index: {resolved}")
    tab = tabs[resolved]
    if not isinstance(tab, dict):
        raise ValueError(f"Invalid tab payload for index: {resolved}")
    return tab


def _list_tasks(snapshot: Dict[str, Any], tab_index: int | None) -> List[Dict[str, Any]]:
    tab = _resolve_tab(snapshot, tab_index)
    tasks_payload = tab.get("tasks", {})
    tasks = tasks_payload.get("tasks", []) if isinstance(tasks_payload, dict) else []
    result: List[Dict[str, Any]] = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        entry = copy.deepcopy(task)
        entry["taskIndex"] = index
        entry["tabIndex"] = tab.get("tabIndex", 0)
        entry["tabName"] = tab.get("name", "")
        result.append(entry)
    return result


def _list_diagram_items(snapshot: Dict[str, Any], tab_index: int | None) -> List[Dict[str, Any]]:
    tab = _resolve_tab(snapshot, tab_index)
    diagram_payload = tab.get("diagram", {})
    items = diagram_payload.get("items", []) if isinstance(diagram_payload, dict) else []
    result: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = copy.deepcopy(item)
        entry["tabIndex"] = tab.get("tabIndex", 0)
        entry["tabName"] = tab.get("name", "")
        result.append(entry)
    return result


def _build_project_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    project = copy.deepcopy(snapshot.get("project", {}))
    tabs = snapshot.get("tabs", [])
    project["tabSummaries"] = [
        {
            "tabIndex": tab.get("tabIndex", 0),
            "name": tab.get("name", ""),
            "isCurrentTab": bool(tab.get("isCurrentTab", False)),
            "taskCount": int(tab.get("taskCount", 0)),
            "completedTaskCount": int(tab.get("completedTaskCount", 0)),
            "incompleteTaskCount": int(tab.get("incompleteTaskCount", 0)),
            "diagramItemCount": int(tab.get("diagramItemCount", 0)),
            "activeTaskTitle": str(tab.get("activeTaskTitle", "") or ""),
        }
        for tab in tabs
        if isinstance(tab, dict)
    ]
    project["reminderCount"] = len(snapshot.get("reminders", []))
    project["contractCount"] = len(snapshot.get("contracts", []))
    return project


def _summarize_project_state(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    summary = _build_project_summary(snapshot)
    current_tab = _resolve_tab(snapshot, None)
    incomplete_tabs = [
        {
            "tabIndex": tab.get("tabIndex", 0),
            "name": tab.get("name", ""),
            "incompleteTaskCount": tab.get("incompleteTaskCount", 0),
        }
        for tab in snapshot.get("tabs", [])
        if isinstance(tab, dict) and int(tab.get("incompleteTaskCount", 0)) > 0
    ]
    incomplete_tabs.sort(key=lambda entry: (-int(entry["incompleteTaskCount"]), int(entry["tabIndex"])))
    return {
        "summary": summary,
        "currentContext": {
            "tabIndex": current_tab.get("tabIndex", 0),
            "tabName": current_tab.get("name", ""),
            "activeTaskTitle": current_tab.get("activeTaskTitle", ""),
            "diagramItemCount": current_tab.get("diagramItemCount", 0),
        },
        "signals": {
            "overdueContracts": [
                contract for contract in snapshot.get("contracts", []) if isinstance(contract, dict) and bool(contract.get("breached", False))
            ],
            "upcomingReminders": snapshot.get("reminders", [])[:5],
            "mostLoadedTabs": incomplete_tabs[:5],
        },
    }


def _identify_focus_items(snapshot: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for contract in snapshot.get("contracts", []):
        if not isinstance(contract, dict):
            continue
        key = ("contract", int(contract.get("tabIndex", 0)), int(contract.get("taskIndex", -1)))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "kind": "contract",
                "priority": 100 if bool(contract.get("breached", False)) else 80,
                "tabIndex": int(contract.get("tabIndex", 0)),
                "tabName": str(contract.get("tabName", "") or ""),
                "taskIndex": int(contract.get("taskIndex", -1)),
                "taskTitle": str(contract.get("taskTitle", "") or ""),
                "reason": (
                    f"Contract breached: {contract.get('punishment', '')}"
                    if bool(contract.get("breached", False))
                    else f"Contract deadline approaching: {contract.get('deadlineText', '')}"
                ),
            }
        )

    for reminder in snapshot.get("reminders", []):
        if not isinstance(reminder, dict):
            continue
        key = ("reminder", int(reminder.get("tabIndex", 0)), int(reminder.get("taskIndex", -1)))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "kind": "reminder",
                "priority": 70,
                "tabIndex": int(reminder.get("tabIndex", 0)),
                "tabName": str(reminder.get("tabName", "") or ""),
                "taskIndex": int(reminder.get("taskIndex", -1)),
                "taskTitle": str(reminder.get("taskTitle", "") or ""),
                "reason": f"Reminder set for {reminder.get('reminderText', '')}",
            }
        )

    current_tab = _resolve_tab(snapshot, None)
    current_tasks = _list_tasks(snapshot, int(current_tab.get("tabIndex", 0)))
    current_task_index = int(current_tab.get("diagram", {}).get("current_task_index", -1))
    if 0 <= current_task_index < len(current_tasks):
        task = current_tasks[current_task_index]
        if not bool(task.get("completed", False)):
            candidates.append(
                {
                    "kind": "currentTask",
                    "priority": 60,
                    "tabIndex": int(task.get("tabIndex", 0)),
                    "tabName": str(task.get("tabName", "") or ""),
                    "taskIndex": current_task_index,
                    "taskTitle": str(task.get("title", "") or ""),
                    "reason": "Current active task in the visible tab",
                }
            )

    for task in current_tasks:
        if bool(task.get("completed", False)):
            continue
        candidates.append(
            {
                "kind": "incompleteTask",
                "priority": 40,
                "tabIndex": int(task.get("tabIndex", 0)),
                "tabName": str(task.get("tabName", "") or ""),
                "taskIndex": int(task.get("taskIndex", -1)),
                "taskTitle": str(task.get("title", "") or ""),
                "reason": "Incomplete task in the current tab backlog",
            }
        )
        if len(candidates) >= max(10, limit * 2):
            break

    candidates.sort(key=lambda entry: (-int(entry["priority"]), int(entry["tabIndex"]), int(entry["taskIndex"])))
    return {"items": candidates[: max(1, int(limit))]}


def _explain_tab_hierarchy(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    tabs = snapshot.get("tabs", [])
    tab_name_to_index = {
        str(tab.get("name", "") or "").strip(): int(tab.get("tabIndex", 0))
        for tab in tabs
        if isinstance(tab, dict) and str(tab.get("name", "") or "").strip()
    }
    links: List[Dict[str, Any]] = []
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        source_index = int(tab.get("tabIndex", 0))
        source_name = str(tab.get("name", "") or "")
        for task in _list_tasks(snapshot, source_index):
            target_index = tab_name_to_index.get(str(task.get("title", "") or "").strip(), -1)
            if target_index < 0 or target_index == source_index:
                continue
            links.append(
                {
                    "fromTabIndex": source_index,
                    "fromTabName": source_name,
                    "viaTaskIndex": int(task.get("taskIndex", -1)),
                    "viaTaskTitle": str(task.get("title", "") or ""),
                    "toTabIndex": target_index,
                    "toTabName": str(tabs[target_index].get("name", "") or ""),
                }
            )
    return {
        "tabCount": len(tabs),
        "linkCount": len(links),
        "links": links,
        "hierarchy": copy.deepcopy(snapshot.get("hierarchy", [])),
    }


def build_actiondraw_mcp_server(
    snapshot_getter: Callable[[], Dict[str, Any]],
    backend: ActionDrawMcpBackend,
    host: str = DEFAULT_MCP_HOST,
    port: int = DEFAULT_MCP_PORT,
) -> FastMCP:
    """Build the embedded ActionDraw MCP server."""

    mcp = FastMCP(
        "ActionDraw",
        instructions=(
            "Embedded ActionDraw MCP server for inspecting tabs, tasks, diagrams, reminders, "
            "contracts, and deterministic project state summaries. Supports core workflow actions."
        ),
        host=host,
        port=port,
        streamable_http_path=DEFAULT_MCP_PATH,
    )

    @mcp.tool(name="get_project_summary", description="Return the current ActionDraw project summary.")
    def get_project_summary() -> Dict[str, Any]:
        return _build_project_summary(_clone_snapshot(snapshot_getter))

    @mcp.tool(name="list_tabs", description="List all ActionDraw tabs and summary metadata.")
    def list_tabs() -> List[Dict[str, Any]]:
        snapshot = _clone_snapshot(snapshot_getter)
        return [
            {
                "tabIndex": tab.get("tabIndex", 0),
                "name": tab.get("name", ""),
                "isCurrentTab": bool(tab.get("isCurrentTab", False)),
                "taskCount": int(tab.get("taskCount", 0)),
                "completedTaskCount": int(tab.get("completedTaskCount", 0)),
                "incompleteTaskCount": int(tab.get("incompleteTaskCount", 0)),
                "diagramItemCount": int(tab.get("diagramItemCount", 0)),
                "activeTaskTitle": str(tab.get("activeTaskTitle", "") or ""),
                "priorityScore": float(tab.get("priorityScore", 0.0)),
                "pinned": bool(tab.get("pinned", False)),
            }
            for tab in snapshot.get("tabs", [])
            if isinstance(tab, dict)
        ]

    @mcp.tool(name="list_tasks", description="List tasks for a tab. Defaults to the active tab.")
    def list_tasks(tab_index: int | None = None) -> List[Dict[str, Any]]:
        return _list_tasks(_clone_snapshot(snapshot_getter), tab_index)

    @mcp.tool(name="list_diagram_items", description="List diagram items for a tab. Defaults to the active tab.")
    def list_diagram_items(tab_index: int | None = None) -> List[Dict[str, Any]]:
        return _list_diagram_items(_clone_snapshot(snapshot_getter), tab_index)

    @mcp.tool(name="get_tab_snapshot", description="Return the full snapshot for one tab. Defaults to the active tab.")
    def get_tab_snapshot(tab_index: int | None = None) -> Dict[str, Any]:
        return _resolve_tab(_clone_snapshot(snapshot_getter), tab_index)

    @mcp.tool(name="get_project_snapshot", description="Return the full ActionDraw project snapshot.")
    def get_project_snapshot() -> Dict[str, Any]:
        return _clone_snapshot(snapshot_getter)

    @mcp.tool(name="get_active_reminders", description="Return active reminders across all tabs.")
    def get_active_reminders() -> List[Dict[str, Any]]:
        return _clone_snapshot(snapshot_getter).get("reminders", [])

    @mcp.tool(name="get_active_contracts", description="Return active contracts across all tabs.")
    def get_active_contracts() -> List[Dict[str, Any]]:
        return _clone_snapshot(snapshot_getter).get("contracts", [])

    @mcp.tool(name="get_hierarchy_tree", description="Return the tab hierarchy tree based on cross-tab task links.")
    def get_hierarchy_tree(root_tab_index: int | None = None) -> List[Dict[str, Any]]:
        snapshot = _clone_snapshot(snapshot_getter)
        if root_tab_index is None:
            return snapshot.get("hierarchy", [])
        hierarchy = snapshot.get("hierarchy", [])
        return [
            node for node in hierarchy
            if isinstance(node, dict) and int(node.get("tabIndex", -1)) == int(root_tab_index)
        ]

    @mcp.tool(name="summarize_project_state", description="Return a deterministic summary of current ActionDraw state.")
    def summarize_project_state() -> Dict[str, Any]:
        return _summarize_project_state(_clone_snapshot(snapshot_getter))

    @mcp.tool(name="identify_focus_items", description="Identify likely focus items from reminders, contracts, and active work.")
    def identify_focus_items(limit: int = 5) -> Dict[str, Any]:
        return _identify_focus_items(_clone_snapshot(snapshot_getter), limit)

    @mcp.tool(name="explain_tab_hierarchy", description="Explain how tabs are linked through task titles and hierarchy data.")
    def explain_tab_hierarchy() -> Dict[str, Any]:
        return _explain_tab_hierarchy(_clone_snapshot(snapshot_getter))

    @mcp.tool(name="add_tab", description="Add a new tab and return its snapshot.")
    def add_tab(name: str) -> Dict[str, Any]:
        return backend.add_tab(name)

    @mcp.tool(name="switch_tab", description="Switch the active tab and return the selected tab snapshot.")
    def switch_tab(tab_index: int) -> Dict[str, Any]:
        return backend.switch_tab(tab_index)

    @mcp.tool(name="add_task", description="Add a task to a tab. Defaults to the active tab.")
    def add_task(title: str, tab_index: int | None = None, parent_task_index: int = -1) -> Dict[str, Any]:
        return backend.add_task(title, tab_index, parent_task_index)

    @mcp.tool(name="set_task_completed", description="Set a task completion state in a tab. Defaults to the active tab.")
    def set_task_completed(task_index: int, completed: bool, tab_index: int | None = None) -> Dict[str, Any]:
        return backend.set_task_completed(task_index, completed, tab_index)

    @mcp.tool(name="create_diagram_task_from_text", description="Create a task item in the current tab diagram at the given coordinates.")
    def create_diagram_task_from_text(text: str, x: float, y: float) -> Dict[str, Any]:
        return backend.create_diagram_task_from_text(text, x, y)

    return mcp


class ActionDrawMcpServerController(QObject):
    """Manage the embedded localhost MCP server lifecycle."""

    statusChanged = Signal()
    _statusUpdateRequested = Signal(str, str)

    def __init__(
        self,
        task_model: TaskModel,
        diagram_model: DiagramModel,
        project_manager: ProjectManager | None = None,
        tab_model: TabModel | None = None,
        host: str = DEFAULT_MCP_HOST,
        port: int = DEFAULT_MCP_PORT,
        server_factory: Callable[[Callable[[], Dict[str, Any]], ActionDrawMcpBackend, str, int], FastMCP] = build_actiondraw_mcp_server,
        uvicorn_server_factory: Callable[[uvicorn.Config], Any] = uvicorn.Server,
    ):
        super().__init__()
        self._backend = ActionDrawMcpBackend(task_model, diagram_model, project_manager, tab_model)
        self._host = host
        self._port = int(port)
        self._status = "stopped"
        self._last_error = ""
        self._server_factory = server_factory
        self._uvicorn_server_factory = uvicorn_server_factory
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._lock = threading.Lock()
        self._statusUpdateRequested.connect(self._apply_status_update, Qt.ConnectionType.QueuedConnection)

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=statusChanged)
    def lastError(self) -> str:
        return self._last_error

    @Property(bool, notify=statusChanged)
    def running(self) -> bool:
        return self._status == "running"

    @Property(str, notify=statusChanged)
    def serverUrl(self) -> str:
        return f"http://{self._host}:{self._port}{DEFAULT_MCP_PATH}"

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        if self._status == "running":
            return f"MCP running on {self.serverUrl}"
        if self._status == "starting":
            return f"Starting MCP on {self._host}:{self._port}"
        if self._status == "stopping":
            return "Stopping MCP server"
        if self._status == "error":
            detail = self._last_error.strip()
            return f"MCP error: {detail}" if detail else "MCP server failed to start"
        return "MCP server is off"

    @Property(str, notify=statusChanged)
    def claudeAddCommand(self) -> str:
        return f"claude mcp add --transport http {DEFAULT_MCP_SERVER_NAME} {self.serverUrl}"

    @Property(str, notify=statusChanged)
    def codexAddCommand(self) -> str:
        return f"codex mcp add {DEFAULT_MCP_SERVER_NAME} --url {self.serverUrl}"

    def _copy_to_clipboard(self, text: str) -> bool:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True

    def _set_status(self, status: str, last_error: str = "") -> None:
        if QThread.currentThread() is self.thread():
            self._apply_status_update(status, last_error)
        else:
            self._statusUpdateRequested.emit(status, last_error)

    @Slot(str, str)
    def _apply_status_update(self, status: str, last_error: str = "") -> None:
        changed = status != self._status or last_error != self._last_error
        if not changed:
            return
        self._status = status
        self._last_error = last_error
        self.statusChanged.emit()

    @Slot()
    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._serve_forever, name="ActionDrawMcpServer", daemon=True)
        self._set_status("starting", "")
        self._thread.start()

    @Slot()
    def stop(self) -> None:
        with self._lock:
            server = self._server
            loop = self._loop
            thread = self._thread
        if server is None or thread is None or not thread.is_alive():
            self._set_status("stopped", "")
            return
        self._set_status("stopping", "")
        server.should_exit = True
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(lambda: None)

    @Slot(result=bool)
    def copyClaudeAddCommand(self) -> bool:
        return self._copy_to_clipboard(self.claudeAddCommand)

    @Slot(result=bool)
    def copyCodexAddCommand(self) -> bool:
        return self._copy_to_clipboard(self.codexAddCommand)

    async def _run_server(self) -> None:
        mcp = self._server_factory(self._backend.get_snapshot, self._backend, self._host, self._port)
        config = uvicorn.Config(
            mcp.streamable_http_app(),
            host=self._host,
            port=self._port,
            log_level="warning",
        )
        server = self._uvicorn_server_factory(config)
        with self._lock:
            self._server = server
            self._loop = asyncio.get_running_loop()

        serve_task = asyncio.create_task(server.serve())
        while not getattr(server, "started", False) and not getattr(server, "should_exit", False) and not serve_task.done():
            await asyncio.sleep(0.05)

        if getattr(server, "started", False):
            self._set_status("running", "")

        await serve_task

        if getattr(server, "started", False) or getattr(server, "should_exit", False):
            self._set_status("stopped", "")
        else:
            self._set_status("error", "MCP server failed to start")

    def _serve_forever(self) -> None:
        try:
            asyncio.run(self._run_server())
        except BaseException as exc:
            self._set_status("error", str(exc))
        finally:
            with self._lock:
                self._server = None
                self._loop = None
                self._thread = None
