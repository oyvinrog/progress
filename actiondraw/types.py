"""Data types for ActionDraw diagrams.

This module contains the core data structures used throughout the
ActionDraw diagramming system.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class DiagramItemType(Enum):
    """Supported diagram item types."""

    BOX = "box"
    TASK = "task"
    DATABASE = "database"
    SERVER = "server"
    CLOUD = "cloud"
    NOTE = "note"
    FREETEXT = "freetext"
    OBSTACLE = "obstacle"
    WISH = "wish"
    IMAGE = "image"
    CHATGPT = "chatgpt"


@dataclass
class DiagramItem:
    """A rectangular shape displayed on the canvas."""

    id: str
    item_type: DiagramItemType
    x: float
    y: float
    width: float = 120.0
    height: float = 60.0
    text: str = ""
    task_index: int = -1
    color: str = "#4a9eff"
    text_color: str = "#f5f6f8"
    image_data: str = ""  # Base64-encoded PNG data for IMAGE type
    note_markdown: str = ""  # Markdown note content for note-like items
    folder_path: str = ""  # Path to linked folder


@dataclass
class DiagramEdge:
    """A directed connection between two diagram items."""

    id: str
    from_id: str
    to_id: str
    description: str = ""


@dataclass
class DrawingPoint:
    """A single point in a drawing stroke."""

    x: float
    y: float


@dataclass
class DrawingStroke:
    """A freehand drawing stroke on the canvas."""

    id: str
    points: List[DrawingPoint]
    color: str = "#ffffff"
    width: float = 3.0
