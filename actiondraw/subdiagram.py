"""Sub-diagram handling mixin for DiagramModel.

This module provides functionality for linked sub-diagrams.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QFileSystemWatcher, QModelIndex, Signal, Slot

from .types import DiagramItem

if TYPE_CHECKING:
    from .model import DiagramModel


class SubDiagramMixin:
    """Mixin providing sub-diagram operations."""

    # Signals (will be defined in DiagramModel)
    itemsChanged: Signal

    # Roles (will be defined in DiagramModel)
    SubDiagramPathRole: int
    SubDiagramProgressRole: int

    # Attributes expected from DiagramModel
    _items: List[DiagramItem]
    _project_path: str
    _sub_diagram_watcher: QFileSystemWatcher
    index: Callable[[int, int], QModelIndex]
    dataChanged: Signal
    getItem: Callable[[str], Optional[DiagramItem]]

    def _init_subdiagram(self) -> None:
        """Initialize sub-diagram state. Call from DiagramModel.__init__."""
        self._project_path = ""
        self._sub_diagram_watcher = QFileSystemWatcher()
        self._sub_diagram_watcher.fileChanged.connect(self._on_sub_diagram_changed)

    def setProjectPath(self, path: str) -> None:
        """Set the current project file path for resolving relative sub-diagram paths.

        Args:
            path: Path to the current project file.
        """
        self._project_path = path

    @Slot(str, str)
    def setSubDiagramPath(self, item_id: str, path: str) -> None:
        """Set the sub-diagram path for an item.

        Args:
            item_id: ID of the item to update.
            path: Path to the .progress file, or empty string to clear.
        """
        # Normalize file:// URL to path
        if path.startswith("file://"):
            path = path[7:]

        for row, item in enumerate(self._items):
            if item.id == item_id:
                if item.sub_diagram_path == path:
                    return
                item.sub_diagram_path = path
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.SubDiagramPathRole, self.SubDiagramProgressRole])
                self.itemsChanged.emit()
                # Update file watcher
                self._update_sub_diagram_watches()
                return

    @Slot(str)
    def openSubDiagram(self, item_id: str) -> bool:
        """Open the sub-diagram linked to an item in a new window.

        Args:
            item_id: ID of the item with the sub-diagram link.

        Returns:
            True if subprocess was launched, False otherwise.
        """
        item = self.getItem(item_id)
        if not item or not item.sub_diagram_path:
            return False

        # Normalize file:// URL to path (in case it wasn't normalized when set)
        path = item.sub_diagram_path
        if path.startswith("file://"):
            path = path[7:]

        # Resolve relative paths against current project directory
        if self._project_path and not os.path.isabs(path):
            base_dir = os.path.dirname(self._project_path)
            path = os.path.join(base_dir, path)

        if not os.path.exists(path):
            print(f"Sub-diagram file not found: {path}")
            return False

        # Launch new process with the sub-diagram file
        # Import at runtime to avoid circular imports
        import actiondraw
        script_path = os.path.abspath(actiondraw.__file__)
        subprocess.Popen([sys.executable, script_path, path])
        return True

    @Slot(str, str)
    def createAndLinkSubDiagram(self, item_id: str, file_path: str, open_after: bool = True) -> None:
        """Create a new empty sub-diagram file and link it to an item.

        Args:
            item_id: ID of the item to link.
            file_path: Path where to create the new .progress file.
            open_after: Whether to open the sub-diagram in a new window after creating.
        """
        # Normalize file:// URL to path
        if file_path.startswith("file://"):
            file_path = file_path[7:]

        # Create empty project structure
        empty_project = {
            "version": "1.0",
            "saved_at": "",
            "tasks": {"tasks": []},
            "diagram": {"items": [], "edges": [], "strokes": [], "current_task_index": -1}
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(empty_project, f, indent=2)

            # Link the new file to the item
            self.setSubDiagramPath(item_id, file_path)

            # Open it in a new window
            if open_after:
                self.openSubDiagram(item_id)
        except (OSError, IOError) as e:
            print(f"Failed to create sub-diagram: {e}")

    def _calculate_sub_diagram_progress(self, sub_diagram_path: str) -> int:
        """Calculate completion percentage of a linked sub-diagram.

        Args:
            sub_diagram_path: Path to the .progress file.

        Returns:
            Percentage (0-100) of completed tasks, or -1 if no sub-diagram or error.
        """
        if not sub_diagram_path:
            return -1

        # Resolve relative paths against current project directory
        if hasattr(self, '_project_path') and self._project_path and not os.path.isabs(sub_diagram_path):
            base_dir = os.path.dirname(self._project_path)
            sub_diagram_path = os.path.join(base_dir, sub_diagram_path)

        if not os.path.exists(sub_diagram_path):
            return -1

        try:
            with open(sub_diagram_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            tasks = data.get("tasks", {}).get("tasks", [])
            if not tasks:
                return 0

            completed = sum(1 for t in tasks if t.get("completed", False))
            return int((completed / len(tasks)) * 100)
        except (json.JSONDecodeError, OSError, KeyError):
            return -1

    def _resolve_sub_diagram_path(self, sub_diagram_path: str) -> str:
        """Resolve a sub-diagram path to an absolute path."""
        if not sub_diagram_path:
            return ""
        if self._project_path and not os.path.isabs(sub_diagram_path):
            base_dir = os.path.dirname(self._project_path)
            return os.path.join(base_dir, sub_diagram_path)
        return sub_diagram_path

    def _on_sub_diagram_changed(self, path: str) -> None:
        """Handle sub-diagram file changes - refresh progress for affected items."""
        # Re-add the file to the watcher (some systems remove it after modification)
        if os.path.exists(path) and path not in self._sub_diagram_watcher.files():
            self._sub_diagram_watcher.addPath(path)

        # Find items that reference this path and emit dataChanged
        for row, item in enumerate(self._items):
            resolved = self._resolve_sub_diagram_path(item.sub_diagram_path)
            if resolved == path:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.SubDiagramProgressRole])

    def _update_sub_diagram_watches(self) -> None:
        """Update the file watcher to watch all current sub-diagram files."""
        # Remove all current watches
        current_files = self._sub_diagram_watcher.files()
        if current_files:
            self._sub_diagram_watcher.removePaths(current_files)

        # Add watches for all sub-diagram paths
        for item in self._items:
            if item.sub_diagram_path:
                resolved = self._resolve_sub_diagram_path(item.sub_diagram_path)
                if resolved and os.path.exists(resolved):
                    self._sub_diagram_watcher.addPath(resolved)
