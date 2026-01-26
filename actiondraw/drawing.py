"""Drawing operations mixin for DiagramModel.

This module provides freehand drawing/stroke functionality.
"""

from __future__ import annotations

from itertools import count
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PySide6.QtCore import Slot

from .types import DrawingPoint, DrawingStroke

if TYPE_CHECKING:
    from .model import DiagramModel


class DrawingMixin:
    """Mixin providing freehand drawing operations.

    Note: Properties (drawingMode, brushColor, brushWidth, strokes) are defined
    in DiagramModel since they need access to signals defined there.
    """

    # Attributes expected from DiagramModel
    _strokes: List[DrawingStroke]
    _current_stroke: Optional[DrawingStroke]
    _drawing_mode: bool
    _brush_color: str
    _brush_width: float
    _stroke_id_source: count

    def _init_drawing(self) -> None:
        """Initialize drawing state. Call from DiagramModel.__init__."""
        self._strokes = []
        self._current_stroke = None
        self._drawing_mode = False
        self._brush_color = "#ffffff"
        self._brush_width = 3.0
        self._stroke_id_source = count()

    def _get_drawing_mode(self) -> bool:
        return self._drawing_mode

    def _set_drawing_mode(self, value: bool) -> None:
        if self._drawing_mode != value:
            self._drawing_mode = value
            self.drawingModeChanged.emit()

    @Slot(bool)
    def setDrawingMode(self, enabled: bool) -> None:
        self._set_drawing_mode(enabled)

    def _get_brush_color(self) -> str:
        return self._brush_color

    def _set_brush_color(self, value: str) -> None:
        if self._brush_color != value:
            self._brush_color = value
            self.brushColorChanged.emit()

    @Slot(str)
    def setBrushColor(self, color: str) -> None:
        self._set_brush_color(color)

    def _get_brush_width(self) -> float:
        return self._brush_width

    def _set_brush_width(self, value: float) -> None:
        clamped = max(1.0, min(50.0, value))
        if self._brush_width != clamped:
            self._brush_width = clamped
            self.brushWidthChanged.emit()

    @Slot(float)
    def setBrushWidth(self, width: float) -> None:
        self._set_brush_width(width)

    def _get_strokes(self) -> List[Dict[str, Any]]:
        """Return all strokes as a list of dicts for QML consumption."""
        result = []
        for stroke in self._strokes:
            result.append({
                "id": stroke.id,
                "color": stroke.color,
                "width": stroke.width,
                "points": [{"x": pt.x, "y": pt.y} for pt in stroke.points],
            })
        return result

    @Slot(float, float)
    def startStroke(self, x: float, y: float) -> None:
        """Begin a new drawing stroke at the given position."""
        stroke_id = f"stroke_{next(self._stroke_id_source)}"
        self._current_stroke = DrawingStroke(
            id=stroke_id,
            points=[DrawingPoint(x, y)],
            color=self._brush_color,
            width=self._brush_width,
        )
        self.drawingChanged.emit()

    @Slot(float, float)
    def continueStroke(self, x: float, y: float) -> None:
        """Add a point to the current stroke."""
        if self._current_stroke is not None:
            self._current_stroke.points.append(DrawingPoint(x, y))
            self.drawingChanged.emit()

    @Slot()
    def endStroke(self) -> None:
        """Finish the current stroke and add it to the strokes list."""
        if self._current_stroke is not None and len(self._current_stroke.points) >= 2:
            self._strokes.append(self._current_stroke)
        self._current_stroke = None
        self.drawingChanged.emit()

    @Slot(result="QVariant")
    def getCurrentStroke(self) -> Dict[str, Any]:
        """Return current stroke being drawn, or empty dict."""
        if self._current_stroke is None:
            return {}
        return {
            "id": self._current_stroke.id,
            "color": self._current_stroke.color,
            "width": self._current_stroke.width,
            "points": [{"x": pt.x, "y": pt.y} for pt in self._current_stroke.points],
        }

    @Slot()
    def clearStrokes(self) -> None:
        """Remove all drawing strokes."""
        self._strokes.clear()
        self._current_stroke = None
        self.drawingChanged.emit()

    @Slot()
    def undoLastStroke(self) -> None:
        """Remove the most recent stroke."""
        if self._strokes:
            self._strokes.pop()
            self.drawingChanged.emit()
