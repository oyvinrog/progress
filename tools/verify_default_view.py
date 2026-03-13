#!/usr/bin/env python3
"""Verify ActionDraw's startup/reset viewport against a real QML window."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QGuiApplication

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from actiondraw.model import DiagramModel
from actiondraw.ui import create_actiondraw_window
from task_model import ProjectManager, TabModel, TaskModel


def _numeric_property(obj: Any, name: str) -> float | None:
    value = obj.property(name)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _walk_children(obj: Any) -> list[Any]:
    result = [obj]
    for child in obj.children():
        result.extend(_walk_children(child))
    return result


def _find_viewport(root: Any) -> Any:
    expected_width = _numeric_property(root, "sceneWidth")
    expected_height = _numeric_property(root, "sceneHeight")
    zoom_level = _numeric_property(root, "zoomLevel")
    if expected_width is None or expected_height is None or zoom_level is None:
        raise RuntimeError("Root object is missing scene/zoom properties")

    target_content_width = expected_width * zoom_level
    target_content_height = expected_height * zoom_level

    best_candidate = None
    best_score = float("inf")
    for child in _walk_children(root):
        content_width = _numeric_property(child, "contentWidth")
        content_height = _numeric_property(child, "contentHeight")
        width = _numeric_property(child, "width")
        height = _numeric_property(child, "height")
        if None in (content_width, content_height, width, height):
            continue
        if content_width <= width or content_height <= height:
            continue
        score = abs(content_width - target_content_width) + abs(content_height - target_content_height)
        score -= (width * height) / 1000.0
        if score < best_score:
            best_score = score
            best_candidate = child

    if best_candidate is None:
        raise RuntimeError("Could not locate the diagram viewport")
    return best_candidate


def _wait(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _build_models() -> tuple[TaskModel, DiagramModel, TabModel, ProjectManager]:
    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    tab_model = TabModel()
    project_manager = ProjectManager(task_model, diagram_model, tab_model)
    return task_model, diagram_model, tab_model, project_manager


def _capture_screenshot(root: Any, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = root.screen().grabWindow(root.winId())
    if not pixmap.save(str(output_path)):
        raise RuntimeError(f"Failed to save screenshot to {output_path}")


def _visible_diagram_rect(root: Any, viewport: Any) -> dict[str, float]:
    width = float(viewport.property("width"))
    height = float(viewport.property("height"))
    top_left = root.viewportPointToDiagram(0.0, 0.0)
    bottom_right = root.viewportPointToDiagram(width, height)
    return {
        "left": float(top_left.x()),
        "top": float(top_left.y()),
        "right": float(bottom_right.x()),
        "bottom": float(bottom_right.y()),
    }


def _target_focus(diagram_model: DiagramModel) -> tuple[float, float]:
    task_pos = diagram_model.getCurrentTaskPosition()
    if task_pos:
        return (
            float(task_pos["x"]) + (float(task_pos["width"]) / 2.0),
            float(task_pos["y"]) + (float(task_pos["height"]) / 2.0),
        )
    return (
        (float(diagram_model.minItemX) + float(diagram_model.maxItemX)) / 2.0,
        (float(diagram_model.minItemY) + float(diagram_model.maxItemY)) / 2.0,
    )


def verify(project_path: Path, screenshot_path: Path, settle_ms: int) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QGuiApplication.instance() or QGuiApplication([])
    task_model, diagram_model, tab_model, project_manager = _build_models()
    engine = create_actiondraw_window(
        diagram_model,
        task_model,
        project_manager,
        tab_model=tab_model,
    )
    if not engine.rootObjects():
        raise RuntimeError("QML engine failed to create a root window")

    root = engine.rootObjects()[0]
    project_manager.loadProject(str(project_path))
    _wait(settle_ms)

    if diagram_model.count == 0:
        raise RuntimeError("Loaded project has no diagram items to verify")

    viewport = _find_viewport(root)
    rect = _visible_diagram_rect(root, viewport)
    focus_x, focus_y = _target_focus(diagram_model)
    min_viewport = root.diagramPointToViewport(float(diagram_model.minItemX), float(diagram_model.minItemY))
    max_viewport = root.diagramPointToViewport(float(diagram_model.maxItemX), float(diagram_model.maxItemY))

    visible_width = rect["right"] - rect["left"]
    visible_height = rect["bottom"] - rect["top"]
    zoom_level = float(root.property("zoomLevel"))

    overlap_left = max(rect["left"], float(diagram_model.minItemX))
    overlap_top = max(rect["top"], float(diagram_model.minItemY))
    overlap_right = min(rect["right"], float(diagram_model.maxItemX))
    overlap_bottom = min(rect["bottom"], float(diagram_model.maxItemY))
    overlap_width = max(0.0, overlap_right - overlap_left)
    overlap_height = max(0.0, overlap_bottom - overlap_top)

    failures: list[str] = []
    if overlap_width <= 0 or overlap_height <= 0:
        failures.append("viewport does not overlap the diagram bounds")

    if not (rect["left"] <= focus_x <= rect["right"] and rect["top"] <= focus_y <= rect["bottom"]):
        failures.append("intended focus point is outside the visible viewport")

    if abs(zoom_level - 0.95) > 0.02:
        failures.append("startup/reset zoom is not close to the intended 0.95 default")

    blank_x_ratio = max(0.0, visible_width - overlap_width) / visible_width if visible_width else 1.0
    blank_y_ratio = max(0.0, visible_height - overlap_height) / visible_height if visible_height else 1.0
    if blank_x_ratio > 0.75 or blank_y_ratio > 0.75:
        failures.append("viewport shows mostly blank space along one axis")

    viewport_width = float(viewport.property("width"))
    viewport_height = float(viewport.property("height"))
    if not (0.0 <= float(min_viewport.x()) <= viewport_width * 0.25):
        failures.append("diagram starts too far from the left edge")
    if not (0.0 <= float(min_viewport.y()) <= viewport_height * 0.25):
        failures.append("diagram starts too far from the top edge")
    if float(max_viewport.x()) < viewport_width * 0.7:
        failures.append("diagram does not make good use of horizontal viewport space")
    if float(max_viewport.y()) < viewport_height * 0.55:
        failures.append("diagram does not make good use of vertical viewport space")

    _capture_screenshot(root, screenshot_path)

    print(f"project={project_path}")
    print(f"screenshot={screenshot_path}")
    print(f"zoom={zoom_level:.4f}")
    print(
        "viewport="
        f"{float(viewport.property('width')):.1f}x{float(viewport.property('height')):.1f}"
        f" content=({float(viewport.property('contentX')):.1f}, {float(viewport.property('contentY')):.1f})"
    )
    print(
        "visible_diagram_rect="
        f"({rect['left']:.1f}, {rect['top']:.1f}) -> ({rect['right']:.1f}, {rect['bottom']:.1f})"
    )
    print(
        "diagram_bounds="
        f"({float(diagram_model.minItemX):.1f}, {float(diagram_model.minItemY):.1f})"
        f" -> ({float(diagram_model.maxItemX):.1f}, {float(diagram_model.maxItemY):.1f})"
    )
    print(f"focus_point=({focus_x:.1f}, {focus_y:.1f})")
    print(
        "diagram_bounds_in_viewport="
        f"({float(min_viewport.x()):.1f}, {float(min_viewport.y()):.1f})"
        f" -> ({float(max_viewport.x()):.1f}, {float(max_viewport.y()):.1f})"
    )

    if diagram_model.rowCount() > 0:
        diagram_model.setCurrentTask(0)
        _wait(120)
        root.scrollToContent()
        _wait(120)

        task_rect = _visible_diagram_rect(root, viewport)
        print(
            "active_task_visible_rect="
            f"({task_rect['left']:.1f}, {task_rect['top']:.1f})"
            f" -> ({task_rect['right']:.1f}, {task_rect['bottom']:.1f})"
        )
        if task_rect["left"] < float(diagram_model.minItemX) - 30.5:
            failures.append("active-task focus still exposes too much blank space on the left")
        if task_rect["top"] < float(diagram_model.minItemY) - 30.5:
            failures.append("active-task focus still exposes too much blank space above the diagram")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: viewport frames the diagram with an overview-friendly composition")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "project",
        nargs="?",
        default=str(PROJECT_ROOT / "demo.progress"),
        help="Project file to load for verification",
    )
    parser.add_argument(
        "--screenshot",
        default="/tmp/actiondraw-default-view.png",
        help="Where to save the rendered screenshot",
    )
    parser.add_argument(
        "--settle-ms",
        type=int,
        default=900,
        help="How long to wait for QML layout/signals before checking geometry",
    )
    args = parser.parse_args()
    return verify(Path(args.project).resolve(), Path(args.screenshot).resolve(), args.settle_ms)


if __name__ == "__main__":
    raise SystemExit(main())
