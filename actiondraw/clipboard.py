"""Clipboard operations mixin for DiagramModel.

This module provides copy/paste functionality for diagram items and edges.
"""

from __future__ import annotations

import base64
import json
import xml.etree.ElementTree as ET
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QJSValue

from .constants import CLIPBOARD_MIME_TYPE
from .types import DiagramEdge, DiagramItem, DiagramItemType

if TYPE_CHECKING:
    from .model import DiagramModel


class ClipboardMixin:
    """Mixin providing clipboard operations."""

    # Signals (will be defined in DiagramModel)
    itemsChanged: Signal
    edgesChanged: Signal

    # Attributes expected from DiagramModel
    _items: List[DiagramItem]
    _edges: List[DiagramEdge]
    _task_model: Any
    _id_source: Any
    _next_id: Callable[[str], str]
    _append_item: Callable[[DiagramItem], None]
    addEdge: Callable[[str, str], None]
    getItem: Callable[[str], Optional[DiagramItem]]

    def _serialize_item_for_clipboard(self, item: DiagramItem) -> Dict[str, Any]:
        note_markdown = item.note_markdown
        if item.item_type == DiagramItemType.NOTE:
            # Notes now keep their canonical content directly in text.
            note_markdown = item.text
        return {
            "id": item.id,
            "type": item.item_type.value,
            "x": item.x,
            "y": item.y,
            "width": item.width,
            "height": item.height,
            "text": item.text,
            "taskIndex": item.task_index,
            "color": item.color,
            "textColor": item.text_color,
            "imageData": item.image_data,
            "noteMarkdown": note_markdown,
            "folderPath": item.folder_path,
        }

    def _build_opml_text(self, items: List[DiagramItem]) -> str:
        opml = ET.Element("opml", {"version": "1.0"})
        head = ET.SubElement(opml, "head")
        title = ET.SubElement(head, "title")
        title.text = "ActionDraw Clipboard"
        body = ET.SubElement(opml, "body")

        selected_task_items: Dict[int, DiagramItem] = {}
        task_children: Dict[int, List[DiagramItem]] = {}
        top_level_items: List[DiagramItem] = []

        for item in items:
            if item.item_type == DiagramItemType.TASK and item.task_index >= 0:
                selected_task_items[item.task_index] = item

        for item in items:
            if item.item_type != DiagramItemType.TASK or item.task_index < 0 or self._task_model is None:
                top_level_items.append(item)
                continue

            parent_index = -1
            task_list = getattr(self._task_model, "_tasks", [])
            if 0 <= item.task_index < len(task_list):
                parent_index = int(task_list[item.task_index].parent_index)

            if parent_index in selected_task_items:
                task_children.setdefault(parent_index, []).append(item)
            else:
                top_level_items.append(item)

        def append_outline(parent: ET.Element, item: DiagramItem) -> None:
            outline = ET.SubElement(parent, "outline", {"text": item.text})
            if item.item_type == DiagramItemType.TASK and item.task_index in task_children:
                for child in task_children[item.task_index]:
                    append_outline(outline, child)

        for item in top_level_items:
            append_outline(body, item)

        xml_text = ET.tostring(opml, encoding="unicode", short_empty_elements=False)
        return f'<?xml version="1.0" encoding="UTF-8"?>{xml_text}'

    def _write_clipboard_payload(self, payload: Dict[str, Any], opml_text: str) -> bool:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        payload_text = json.dumps(payload)
        mime_data = QMimeData()
        mime_data.setData(CLIPBOARD_MIME_TYPE, QByteArray(payload_text.encode("utf-8")))
        mime_data.setText(opml_text)
        clipboard.setMimeData(mime_data)
        return True

    def _read_clipboard_text(self) -> str:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return ""
        mime_data = clipboard.mimeData()
        if mime_data is None or not mime_data.hasText():
            return ""
        return mime_data.text() or ""

    @staticmethod
    def _xml_local_name(tag: str) -> str:
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag

    def _parse_opml_text(self, text: str) -> Optional[List[Dict[str, Any]]]:
        if not text or "<opml" not in text.lower():
            return None
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return None

        if self._xml_local_name(root.tag).lower() != "opml":
            return None

        body = None
        for child in root:
            if self._xml_local_name(child.tag).lower() == "body":
                body = child
                break
        if body is None:
            return None

        entries: List[Dict[str, Any]] = []

        def visit(outline: ET.Element, level: int) -> None:
            text_value = outline.get("text")
            if text_value is None:
                text_value = outline.get("title")
            if text_value is None:
                text_value = (outline.text or "").strip()
            if text_value.strip():
                entries.append({"text": text_value, "level": level})

            next_level = level + 1 if text_value.strip() else level
            for child_outline in outline:
                if self._xml_local_name(child_outline.tag).lower() == "outline":
                    visit(child_outline, next_level)

        for child in body:
            if self._xml_local_name(child.tag).lower() == "outline":
                visit(child, 0)

        return entries or None

    def _read_clipboard_payload(self) -> Optional[Dict[str, Any]]:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return None
        mime_data = clipboard.mimeData()
        if mime_data is None:
            return None
        payload_text: Optional[str] = None
        if mime_data.hasFormat(CLIPBOARD_MIME_TYPE):
            raw = mime_data.data(CLIPBOARD_MIME_TYPE)
            payload_text = bytes(raw).decode("utf-8")
        elif mime_data.hasText():
            payload_text = mime_data.text()
        if not payload_text:
            return None
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("format") != "actiondraw-diagram":
            return None
        return payload

    @Slot("QVariant", result=bool)
    def copyItemsToClipboard(self, item_ids: Any) -> bool:
        if isinstance(item_ids, QJSValue):
            item_ids = item_ids.toVariant()
        if not item_ids:
            return False
        if not isinstance(item_ids, list):
            return False
        normalized_ids = [str(item_id) for item_id in item_ids if item_id]
        if not normalized_ids:
            return False
        selected_items: List[DiagramItem] = []
        items = []
        valid_ids = set()
        for item_id in normalized_ids:
            item = self.getItem(item_id)
            if item is None:
                continue
            selected_items.append(item)
            items.append(self._serialize_item_for_clipboard(item))
            valid_ids.add(item_id)
        if not items:
            return False
        edges = []
        for edge in self._edges:
            if edge.from_id in valid_ids and edge.to_id in valid_ids:
                edges.append({
                    "fromId": edge.from_id,
                    "toId": edge.to_id,
                    "description": edge.description,
                })
        payload = {
            "format": "actiondraw-diagram",
            "version": 1,
            "items": items,
            "edges": edges,
        }
        return self._write_clipboard_payload(payload, self._build_opml_text(selected_items))

    @Slot(str, result=bool)
    def copyEdgeToClipboard(self, edge_id: str) -> bool:
        if not edge_id:
            return False
        edge = next((edge for edge in self._edges if edge.id == edge_id), None)
        if edge is None:
            return False
        item_ids = [edge.from_id, edge.to_id]
        items = []
        valid_ids = set()
        for item_id in item_ids:
            item = self.getItem(item_id)
            if item is None:
                continue
            items.append(self._serialize_item_for_clipboard(item))
            valid_ids.add(item_id)
        if len(valid_ids) < 2:
            return False
        payload = {
            "format": "actiondraw-diagram",
            "version": 1,
            "items": items,
            "edges": [
                {
                    "fromId": edge.from_id,
                    "toId": edge.to_id,
                    "description": edge.description,
                }
            ],
        }
        ordered_items = [self.getItem(item_id) for item_id in item_ids]
        return self._write_clipboard_payload(
            payload,
            self._build_opml_text([item for item in ordered_items if item is not None]),
        )

    @Slot(result=bool)
    def hasClipboardDiagram(self) -> bool:
        return self._read_clipboard_payload() is not None

    @Slot(result=bool)
    def hasClipboardTextLines(self) -> bool:
        text = self._read_clipboard_text()
        lines = [line for line in text.splitlines() if line.strip()]
        return len(lines) > 1

    @Slot(result=bool)
    def hasClipboardOpml(self) -> bool:
        return self._parse_opml_text(self._read_clipboard_text()) is not None

    def _parse_text_hierarchy(self, text: str) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        indent_stack: List[int] = []
        for raw_line in text.splitlines():
            if not raw_line.strip():
                continue
            leading = len(raw_line) - len(raw_line.lstrip(" \t"))
            indent_text = raw_line[:leading].replace("\t", "    ")
            indent_len = len(indent_text)
            if not indent_stack:
                indent_stack = [indent_len]
                level = 0
            else:
                if indent_len > indent_stack[-1]:
                    indent_stack.append(indent_len)
                    level = len(indent_stack) - 1
                else:
                    while indent_stack and indent_len < indent_stack[-1]:
                        indent_stack.pop()
                    if not indent_stack:
                        indent_stack = [indent_len]
                        level = 0
                    elif indent_len > indent_stack[-1]:
                        indent_stack.append(indent_len)
                        level = len(indent_stack) - 1
                    else:
                        level = len(indent_stack) - 1
            entries.append({"text": raw_line.lstrip(" \t").strip(), "level": level})
        return entries

    @Slot(float, float, bool, result=bool)
    def pasteTextFromClipboard(self, x: float, y: float, as_tasks: bool) -> bool:
        text = self._read_clipboard_text()
        if not text:
            return False
        entries = self._parse_opml_text(text)
        if entries is None:
            entries = self._parse_text_hierarchy(text)
        if not entries:
            return False
        if as_tasks and self._task_model is None:
            return False

        indent_spacing = 160.0
        row_spacing = 90.0
        positions = []
        min_x = None
        max_x = None
        min_y = None
        max_y = None
        for idx, entry in enumerate(entries):
            px = entry["level"] * indent_spacing
            py = idx * row_spacing
            positions.append((px, py))
            min_x = px if min_x is None else min(min_x, px)
            max_x = px if max_x is None else max(max_x, px)
            min_y = py if min_y is None else min(min_y, py)
            max_y = py if max_y is None else max(max_y, py)

        if min_x is None or max_x is None or min_y is None or max_y is None:
            return False

        offset_x = x - (min_x + max_x) / 2.0
        offset_y = y - (min_y + max_y) / 2.0

        previous_item_id = ""
        task_index_stack: List[int] = []

        for idx, entry in enumerate(entries):
            level = int(entry["level"])
            text_value = entry["text"]
            px, py = positions[idx]
            item_x = px + offset_x
            item_y = py + offset_y

            while len(task_index_stack) > level:
                task_index_stack.pop()

            task_level = min(level, len(task_index_stack))

            parent_task_index = task_index_stack[task_level - 1] if task_level > 0 else -1

            if as_tasks:
                add_task = getattr(self._task_model, "addTaskWithParent", None)
                if callable(add_task):
                    task_index = add_task(text_value, parent_task_index)
                else:
                    self._task_model.addTask(text_value, parent_task_index)
                    task_index = self._task_model.rowCount() - 1

                item_id = self._next_id("task")
                item = DiagramItem(
                    id=item_id,
                    item_type=DiagramItemType.TASK,
                    x=item_x,
                    y=item_y,
                    width=140.0,
                    height=70.0,
                    text=text_value,
                    task_index=task_index,
                    color="#82c3a5",
                    text_color="#1b2028",
                )
                self._append_item(item)
            else:
                item_id = self._add_preset("box", item_x, item_y, text_value)

            if previous_item_id:
                self.addEdge(previous_item_id, item_id)
            previous_item_id = item_id

            if as_tasks:
                if len(task_index_stack) == task_level:
                    task_index_stack.append(task_index)
                else:
                    task_index_stack[task_level] = task_index

        return True

    @Slot(float, float, result=bool)
    def pasteDiagramFromClipboard(self, x: float, y: float) -> bool:
        payload = self._read_clipboard_payload()
        if not payload:
            return False
        items_data = payload.get("items", [])
        if not isinstance(items_data, list) or not items_data:
            return False
        min_x = None
        min_y = None
        max_x = None
        max_y = None
        for item_data in items_data:
            try:
                item_x = float(item_data.get("x", 0.0))
                item_y = float(item_data.get("y", 0.0))
                item_w = float(item_data.get("width", 120.0))
                item_h = float(item_data.get("height", 60.0))
            except (TypeError, ValueError):
                continue
            min_x = item_x if min_x is None else min(min_x, item_x)
            min_y = item_y if min_y is None else min(min_y, item_y)
            max_x = item_x + item_w if max_x is None else max(max_x, item_x + item_w)
            max_y = item_y + item_h if max_y is None else max(max_y, item_y + item_h)
        if min_x is None or min_y is None or max_x is None or max_y is None:
            return False
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        offset_x = x - center_x
        offset_y = y - center_y

        id_map: Dict[str, str] = {}
        for item_data in items_data:
            item_type_str = str(item_data.get("type", "box"))
            try:
                item_type = DiagramItemType(item_type_str)
            except ValueError:
                item_type = DiagramItemType.BOX

            task_index = int(item_data.get("taskIndex", -1))
            if self._task_model is None or task_index < 0 or task_index >= self._task_model.rowCount():
                task_index = -1

            item_id = self._next_id(item_type.value)
            try:
                item_x = float(item_data.get("x", 0.0)) + offset_x
                item_y = float(item_data.get("y", 0.0)) + offset_y
                item_w = float(item_data.get("width", 120.0))
                item_h = float(item_data.get("height", 60.0))
            except (TypeError, ValueError):
                continue
            text_value = str(item_data.get("text", ""))
            note_markdown_value = str(item_data.get("noteMarkdown", ""))
            if item_type == DiagramItemType.NOTE and note_markdown_value:
                text_value = note_markdown_value
                note_markdown_value = ""

            item = DiagramItem(
                id=item_id,
                item_type=item_type,
                x=item_x,
                y=item_y,
                width=item_w,
                height=item_h,
                text=text_value,
                task_index=task_index,
                color=str(item_data.get("color", "#4a9eff")),
                text_color=str(item_data.get("textColor", "#f5f6f8")),
                image_data=str(item_data.get("imageData", "")),
                note_markdown=note_markdown_value,
                folder_path=str(item_data.get("folderPath", "")),
            )
            self._append_item(item)
            old_id = str(item_data.get("id", ""))
            if old_id:
                id_map[old_id] = item_id

        edges_data = payload.get("edges", [])
        edges_added = False
        if isinstance(edges_data, list):
            for edge_data in edges_data:
                old_from = str(edge_data.get("fromId", ""))
                old_to = str(edge_data.get("toId", ""))
                if not old_from or not old_to:
                    continue
                if old_from not in id_map or old_to not in id_map:
                    continue
                from_id = id_map[old_from]
                to_id = id_map[old_to]
                if from_id == to_id:
                    continue
                if any(edge.from_id == from_id and edge.to_id == to_id for edge in self._edges):
                    continue
                edge_id = f"edge_{len(self._edges)}"
                description = str(edge_data.get("description", ""))
                self._edges.append(DiagramEdge(edge_id, from_id, to_id, description))
                edges_added = True
        if edges_added:
            self.edgesChanged.emit()
        return True

    @Slot(float, float, result=str)
    def pasteImageFromClipboard(self, x: float, y: float) -> str:
        """Paste an image from the clipboard at the specified position.

        Args:
            x: X coordinate for the new image item.
            y: Y coordinate for the new image item.

        Returns:
            The ID of the created image item, or empty string on failure.
        """
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return ""

        mime_data = clipboard.mimeData()
        if mime_data is None or not mime_data.hasImage():
            return ""

        image = clipboard.image()
        if image.isNull():
            return ""

        # Convert QImage to base64-encoded PNG
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()

        image_data = base64.b64encode(byte_array.data()).decode("ascii")
        if not image_data:
            return ""

        # Calculate appropriate size (limit max dimension to 400px while preserving aspect ratio)
        max_dim = 400.0
        width = float(image.width())
        height = float(image.height())
        if width > max_dim or height > max_dim:
            scale = max_dim / max(width, height)
            width = width * scale
            height = height * scale

        item_id = self._next_id("image")
        item = DiagramItem(
            id=item_id,
            item_type=DiagramItemType.IMAGE,
            x=x,
            y=y,
            width=width,
            height=height,
            text="",
            color="#2a3444",
            text_color="#f5f6f8",
            image_data=image_data,
        )
        self._append_item(item)
        return item_id

    @Slot(result=bool)
    def hasClipboardImage(self) -> bool:
        """Check if the clipboard contains an image.

        Returns:
            True if clipboard has an image, False otherwise.
        """
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return False
        mime_data = clipboard.mimeData()
        if mime_data is None:
            return False
        return mime_data.hasImage()
