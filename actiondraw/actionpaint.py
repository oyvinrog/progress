"""State model and standalone launcher for the Action Paint companion tool."""

from __future__ import annotations

import copy
import json
import math
import os
import sys
from itertools import count
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot


CANVAS_WIDTH = 1600
CANVAS_HEIGHT = 1000


def empty_action_paint_state() -> Dict[str, Any]:
    """Return a fresh, serializable Action Paint state."""
    return {"elements": [], "actions": [], "last_imported_signature": ""}


def normalize_action_paint_state(value: Any) -> Dict[str, Any]:
    """Normalize untrusted/legacy project data into the current schema."""
    source = value if isinstance(value, dict) else {}
    elements: List[Dict[str, Any]] = []
    for raw in source.get("elements", []):
        if not isinstance(raw, dict) or raw.get("type") not in {"pencil", "line", "rectangle", "text"}:
            continue
        element = copy.deepcopy(raw)
        element["id"] = str(element.get("id", ""))
        element["color"] = str(element.get("color", "#263238"))
        if element["type"] == "text":
            element["text"] = str(element.get("text", "")).strip()
            if not element["text"]:
                continue
            for key in ("x", "y"):
                try:
                    element[key] = float(element.get(key, 0))
                except (TypeError, ValueError):
                    element[key] = 0.0
            try:
                element["font_size"] = max(8.0, min(144.0, float(element.get("font_size", 24.0))))
            except (TypeError, ValueError):
                element["font_size"] = 24.0
            elements.append(element)
            continue
        try:
            element["width"] = max(1.0, min(50.0, float(element.get("width", 3.0))))
        except (TypeError, ValueError):
            element["width"] = 3.0
        if element["type"] == "pencil":
            points = []
            for point in element.get("points", []):
                if isinstance(point, dict):
                    try:
                        points.append({"x": float(point.get("x", 0)), "y": float(point.get("y", 0))})
                    except (TypeError, ValueError):
                        pass
            element["points"] = points
        else:
            for key in ("x1", "y1", "x2", "y2"):
                try:
                    element[key] = float(element.get(key, 0))
                except (TypeError, ValueError):
                    element[key] = 0.0
        elements.append(element)

    actions: List[Dict[str, Any]] = []
    for raw in source.get("actions", []):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("text", "")).strip()
        if not title:
            continue
        try:
            x = float(raw.get("x", 0))
            y = float(raw.get("y", 0))
        except (TypeError, ValueError):
            continue
        actions.append({"id": str(raw.get("id", "")), "text": title, "x": x, "y": y})

    return {
        "elements": elements,
        "actions": actions,
        "last_imported_signature": str(source.get("last_imported_signature", "")),
    }


class ActionPaintModel(QObject):
    """Editable Action Paint state, optionally backed by the active TabModel tab."""

    elementsChanged = Signal()
    actionsChanged = Signal()
    importedChanged = Signal()
    stateChanged = Signal()
    undoChanged = Signal()

    def __init__(self, tab_model=None, demo_mode: bool = False):
        super().__init__()
        self._tab_model = tab_model
        self._demo_mode = bool(demo_mode)
        self._state = empty_action_paint_state()
        self._element_ids = count()
        self._action_ids = count()
        self._active_element_id = ""
        self._undo_stack: List[List[Dict[str, Any]]] = []
        self._pending_erase_snapshot: Optional[List[Dict[str, Any]]] = None
        self._erase_active = False
        if tab_model is not None:
            tab_model.currentTabChanged.connect(self.loadCurrentTab)
            tab_model.modelReset.connect(self.loadCurrentTab)
            self.loadCurrentTab()
        elif demo_mode:
            self.loadDemo()

    def _current_tab(self):
        if self._tab_model is None:
            return None
        try:
            return self._tab_model.getCurrentTabData()
        except (AttributeError, IndexError):
            return None

    def _persist(self) -> None:
        tab = self._current_tab()
        if tab is not None:
            tab.action_paint = self.to_dict()
        self.stateChanged.emit()

    def _semantic_change(self) -> None:
        self._state["last_imported_signature"] = ""
        self.actionsChanged.emit()
        self.importedChanged.emit()
        self._persist()

    def _reset_id_sources(self) -> None:
        max_element = -1
        for element in self._state["elements"]:
            try:
                max_element = max(max_element, int(str(element["id"]).rsplit("_", 1)[1]))
            except (IndexError, KeyError, ValueError):
                pass
        max_action = -1
        for action in self._state["actions"]:
            try:
                max_action = max(max_action, int(str(action["id"]).rsplit("_", 1)[1]))
            except (IndexError, KeyError, ValueError):
                pass
        self._element_ids = count(max_element + 1)
        self._action_ids = count(max_action + 1)

    def _signature(self) -> str:
        payload = [{"id": item["id"], "text": item["text"]} for item in self._state["actions"]]
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _push_undo_snapshot(self, snapshot: Optional[List[Dict[str, Any]]] = None) -> None:
        self._undo_stack.append(copy.deepcopy(self._state["elements"] if snapshot is None else snapshot))
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)
        self.undoChanged.emit()

    @staticmethod
    def _distance_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0.0 and dy == 0.0:
            return math.hypot(px - x1, py - y1)
        scale = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (x1 + scale * dx), py - (y1 + scale * dy))

    def _element_hit(self, element: Dict[str, Any], x: float, y: float, radius: float) -> bool:
        kind = element.get("type")
        if kind == "text":
            font_size = float(element.get("font_size", 24.0))
            left = float(element.get("x", 0.0)) - radius
            top = float(element.get("y", 0.0)) - radius
            width = max(font_size * 0.6, len(str(element.get("text", ""))) * font_size * 0.6)
            return left <= x <= left + width + radius * 2 and top <= y <= top + font_size + radius * 2

        threshold = radius + float(element.get("width", 1.0)) / 2.0
        if kind == "pencil":
            points = element.get("points", [])
            if len(points) == 1:
                return math.hypot(x - float(points[0]["x"]), y - float(points[0]["y"])) <= threshold
            return any(
                self._distance_to_segment(
                    x, y,
                    float(points[index - 1]["x"]), float(points[index - 1]["y"]),
                    float(points[index]["x"]), float(points[index]["y"]),
                ) <= threshold
                for index in range(1, len(points))
            )
        if kind == "line":
            return self._distance_to_segment(
                x, y, float(element["x1"]), float(element["y1"]),
                float(element["x2"]), float(element["y2"]),
            ) <= threshold
        if kind == "rectangle":
            left = min(float(element["x1"]), float(element["x2"]))
            right = max(float(element["x1"]), float(element["x2"]))
            top = min(float(element["y1"]), float(element["y2"]))
            bottom = max(float(element["y1"]), float(element["y2"]))
            return any(
                self._distance_to_segment(x, y, *edge) <= threshold
                for edge in (
                    (left, top, right, top), (right, top, right, bottom),
                    (right, bottom, left, bottom), (left, bottom, left, top),
                )
            )
        return False

    @Property("QVariantList", notify=elementsChanged)
    def elements(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self._state["elements"])

    @Property("QVariantList", notify=actionsChanged)
    def actions(self) -> List[Dict[str, Any]]:
        return [dict(item, order=index + 1) for index, item in enumerate(self._state["actions"])]

    @Property("QVariantList", notify=actionsChanged)
    def orderedTitles(self) -> List[str]:
        return [item["text"] for item in self._state["actions"]]

    @Property(int, notify=actionsChanged)
    def actionCount(self) -> int:
        return len(self._state["actions"])

    @Property(bool, notify=undoChanged)
    def canUndo(self) -> bool:
        return bool(self._undo_stack)

    @Property(bool, notify=importedChanged)
    def imported(self) -> bool:
        return bool(self._state["actions"]) and self._state["last_imported_signature"] == self._signature()

    @Property(bool, constant=True)
    def demoMode(self) -> bool:
        return self._demo_mode

    @Slot()
    def loadCurrentTab(self) -> None:
        tab = self._current_tab()
        self._state = normalize_action_paint_state(getattr(tab, "action_paint", None))
        self._active_element_id = ""
        self._undo_stack.clear()
        self._pending_erase_snapshot = None
        self._erase_active = False
        self._reset_id_sources()
        self.elementsChanged.emit()
        self.actionsChanged.emit()
        self.importedChanged.emit()
        self.undoChanged.emit()

    @Slot(str, float, float, str, float)
    def startDrawing(self, tool: str, x: float, y: float, color: str, width: float) -> None:
        if tool not in {"pencil", "line", "rectangle"}:
            return
        self._push_undo_snapshot()
        element_id = f"paint_{next(self._element_ids)}"
        base = {"id": element_id, "type": tool, "color": str(color), "width": max(1.0, min(50.0, float(width)))}
        if tool == "pencil":
            base["points"] = [{"x": float(x), "y": float(y)}]
        else:
            base.update({"x1": float(x), "y1": float(y), "x2": float(x), "y2": float(y)})
        self._state["elements"].append(base)
        self._active_element_id = element_id
        self.elementsChanged.emit()

    @Slot(float, float)
    def continueDrawing(self, x: float, y: float) -> None:
        if not self._active_element_id:
            return
        element = next((item for item in self._state["elements"] if item["id"] == self._active_element_id), None)
        if element is None:
            return
        if element["type"] == "pencil":
            element["points"].append({"x": float(x), "y": float(y)})
        else:
            element["x2"] = float(x)
            element["y2"] = float(y)
        self.elementsChanged.emit()

    @Slot()
    def endDrawing(self) -> None:
        if not self._active_element_id:
            return
        self._active_element_id = ""
        self.elementsChanged.emit()
        self._persist()

    @Slot()
    def undoLastDrawing(self) -> None:
        if not self._undo_stack:
            return
        self._active_element_id = ""
        self._pending_erase_snapshot = None
        self._erase_active = False
        self._state["elements"] = self._undo_stack.pop()
        self.elementsChanged.emit()
        self.undoChanged.emit()
        self._persist()

    @Slot()
    def clearDrawing(self) -> None:
        if not self._state["elements"]:
            return
        self._push_undo_snapshot()
        self._active_element_id = ""
        self._state["elements"].clear()
        self.elementsChanged.emit()
        self._persist()

    @Slot(str, float, float, str, float, result=str)
    def addText(self, text: str, x: float, y: float, color: str, font_size: float) -> str:
        """Place a text element on the painting."""
        value = str(text).strip()
        if not value:
            return ""
        self._push_undo_snapshot()
        element_id = f"paint_{next(self._element_ids)}"
        self._state["elements"].append({
            "id": element_id,
            "type": "text",
            "text": value,
            "x": float(x),
            "y": float(y),
            "color": str(color),
            "font_size": max(8.0, min(144.0, float(font_size))),
        })
        self.elementsChanged.emit()
        self._persist()
        return element_id

    @Slot()
    def beginErase(self) -> None:
        self._pending_erase_snapshot = copy.deepcopy(self._state["elements"])
        self._erase_active = True

    @Slot(float, float, float, result=bool)
    def eraseAt(self, x: float, y: float, radius: float) -> bool:
        """Erase the topmost drawing element touched by the eraser."""
        hit_radius = max(2.0, min(100.0, float(radius)))
        for index in range(len(self._state["elements"]) - 1, -1, -1):
            if not self._element_hit(self._state["elements"][index], float(x), float(y), hit_radius):
                continue
            if self._pending_erase_snapshot is not None:
                self._push_undo_snapshot(self._pending_erase_snapshot)
                self._pending_erase_snapshot = None
            elif not self._erase_active:
                self._push_undo_snapshot()
            self._state["elements"].pop(index)
            self.elementsChanged.emit()
            self._persist()
            return True
        return False

    @Slot()
    def endErase(self) -> None:
        self._pending_erase_snapshot = None
        self._erase_active = False

    @Slot(str, float, float, result=str)
    def addAction(self, text: str, x: float, y: float) -> str:
        title = str(text).strip()
        if not title:
            return ""
        action_id = f"action_{next(self._action_ids)}"
        self._state["actions"].append({"id": action_id, "text": title, "x": float(x), "y": float(y)})
        self._semantic_change()
        return action_id

    @Slot(str, str)
    def renameAction(self, action_id: str, text: str) -> None:
        title = str(text).strip()
        if not title:
            return
        for action in self._state["actions"]:
            if action["id"] == action_id and action["text"] != title:
                action["text"] = title
                self._semantic_change()
                return

    @Slot(str, float, float)
    def moveActionMarker(self, action_id: str, x: float, y: float) -> None:
        for action in self._state["actions"]:
            if action["id"] == action_id:
                action["x"] = max(0.0, min(float(CANVAS_WIDTH), float(x)))
                action["y"] = max(0.0, min(float(CANVAS_HEIGHT), float(y)))
                self.actionsChanged.emit()
                self._persist()
                return

    @Slot(str)
    def removeAction(self, action_id: str) -> None:
        remaining = [item for item in self._state["actions"] if item["id"] != action_id]
        if len(remaining) == len(self._state["actions"]):
            return
        self._state["actions"] = remaining
        self._semantic_change()

    @Slot(int, int)
    def moveAction(self, from_index: int, to_index: int) -> None:
        count_actions = len(self._state["actions"])
        if not (0 <= from_index < count_actions and 0 <= to_index < count_actions) or from_index == to_index:
            return
        item = self._state["actions"].pop(from_index)
        self._state["actions"].insert(to_index, item)
        self._semantic_change()

    @Slot()
    def markImported(self) -> None:
        if not self._state["actions"]:
            return
        was_imported = self.imported
        self._state["last_imported_signature"] = self._signature()
        if not was_imported:
            self.importedChanged.emit()
        self._persist()

    @Slot(result=bool)
    def simulateImport(self) -> bool:
        if not self._demo_mode or not self._state["actions"] or self.imported:
            return False
        self.markImported()
        return True

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._state)

    def from_dict(self, data: Any) -> None:
        self._state = normalize_action_paint_state(data)
        self._active_element_id = ""
        self._undo_stack.clear()
        self._pending_erase_snapshot = None
        self._erase_active = False
        self._reset_id_sources()
        self.elementsChanged.emit()
        self.actionsChanged.emit()
        self.importedChanged.emit()
        self.undoChanged.emit()

    @Slot()
    def loadDemo(self) -> None:
        self._state = empty_action_paint_state()
        self._undo_stack.clear()
        self._pending_erase_snapshot = None
        self._erase_active = False
        self._reset_id_sources()
        # Garage, car, wheels, and a simple upright vacuum.
        for tool, x1, y1, x2, y2 in (
            ("rectangle", 60, 70, 830, 690),
            ("rectangle", 210, 380, 540, 570),
            ("line", 210, 445, 275, 380),
            ("line", 475, 380, 540, 445),
            ("line", 690, 280, 735, 525),
            ("rectangle", 660, 490, 760, 610),
        ):
            self.startDrawing(tool, x1, y1, "#263238", 5)
            self.continueDrawing(x2, y2)
            self.endDrawing()
        for cx in (285, 465):
            self.startDrawing("pencil", cx - 30, 570, "#263238", 8)
            for px, py in ((cx - 18, 592), (cx + 18, 592), (cx + 30, 570), (cx + 18, 548), (cx - 18, 548), (cx - 30, 570)):
                self.continueDrawing(px, py)
            self.endDrawing()
        self.addText("Garage", 330, 95, "#263238", 34)
        self.addAction("Wash car", 390, 335)
        self.addAction("Fix vacuum cleaner", 790, 440)
        self._undo_stack.clear()
        self.undoChanged.emit()


def main() -> int:
    """Run the standalone Action Paint demo."""
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from .qml import ACTIONPAINT_QML_PATH, QML_DIR
    from .theme import configure_actiondraw_theme

    smoke_mode = "--smoke" in sys.argv or os.environ.get("ACTIONPAINT_SMOKE") == "1"
    app = QApplication.instance() or QApplication(sys.argv)
    configure_actiondraw_theme(app)
    engine = QQmlApplicationEngine()
    model = ActionPaintModel(demo_mode=True)
    engine.rootContext().setContextProperty("actionPaintModel", model)
    engine.rootContext().setContextProperty("diagramModel", None)
    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(ACTIONPAINT_QML_PATH)))
    engine._action_paint_model = model
    if not engine.rootObjects():
        return 1
    if smoke_mode:
        return 0
    return app.exec()


__all__ = ["ActionPaintModel", "CANVAS_HEIGHT", "CANVAS_WIDTH", "empty_action_paint_state", "normalize_action_paint_state", "main"]
