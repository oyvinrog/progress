"""Constants and presets for ActionDraw diagrams."""

from typing import Any, Dict

from .types import DiagramItemType


CLIPBOARD_MIME_TYPE = "application/x-actiondraw-diagram"


ITEM_PRESETS: Dict[str, Dict[str, Any]] = {
    "box": {
        "type": DiagramItemType.BOX,
        "width": 120.0,
        "height": 60.0,
        "color": "#4a9eff",
        "text": "Box",
        "text_color": "#f5f6f8",
    },
    "database": {
        "type": DiagramItemType.DATABASE,
        "width": 160.0,
        "height": 90.0,
        "color": "#c18f5e",
        "text": "Database",
        "text_color": "#1b2028",
    },
    "server": {
        "type": DiagramItemType.SERVER,
        "width": 150.0,
        "height": 90.0,
        "color": "#3d495c",
        "text": "Server",
        "text_color": "#f5f6f8",
    },
    "cloud": {
        "type": DiagramItemType.CLOUD,
        "width": 170.0,
        "height": 100.0,
        "color": "#6a9ddb",
        "text": "Cloud",
        "text_color": "#1b2028",
    },
    "note": {
        "type": DiagramItemType.NOTE,
        "width": 160.0,
        "height": 110.0,
        "color": "#f7e07b",
        "text": "Note",
        "text_color": "#1b2028",
    },
    "freetext": {
        "type": DiagramItemType.FREETEXT,
        "width": 200.0,
        "height": 140.0,
        "color": "#f5f0e6",
        "text": "",
        "text_color": "#2d3436",
    },
    "obstacle": {
        "type": DiagramItemType.OBSTACLE,
        "width": 140.0,
        "height": 100.0,
        "color": "#e74c3c",
        "text": "Obstacle",
        "text_color": "#ffffff",
    },
    "wish": {
        "type": DiagramItemType.WISH,
        "width": 140.0,
        "height": 100.0,
        "color": "#f1c40f",
        "text": "Wish",
        "text_color": "#2d3436",
    },
    "chatgpt": {
        "type": DiagramItemType.CHATGPT,
        "width": 180.0,
        "height": 90.0,
        "color": "#1f8f6b",
        "text": "Ask ChatGPT",
        "text_color": "#f5f6f8",
    },
}
