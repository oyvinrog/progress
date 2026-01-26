"""ActionDraw diagramming module built with PySide6 and QML.

The implementation focuses on predictable coordinate handling so drawing
connections between items works reliably when dragging across the canvas.
"""

from .constants import CLIPBOARD_MIME_TYPE, ITEM_PRESETS
from .model import DiagramModel
from .qml import ACTIONDRAW_QML
from .types import (
    DiagramEdge,
    DiagramItem,
    DiagramItemType,
    DrawingPoint,
    DrawingStroke,
)
from .ui import create_actiondraw_window, main

__all__ = [
    "ACTIONDRAW_QML",
    "CLIPBOARD_MIME_TYPE",
    "DiagramEdge",
    "DiagramItem",
    "DiagramItemType",
    "DiagramModel",
    "DrawingPoint",
    "DrawingStroke",
    "ITEM_PRESETS",
    "create_actiondraw_window",
    "main",
]
