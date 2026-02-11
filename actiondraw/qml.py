"""QML UI definition for ActionDraw."""

from __future__ import annotations

from pathlib import Path

QML_DIR = Path(__file__).with_name("qml_ui")
ACTIONDRAW_QML_PATH = QML_DIR / "ActionDrawWindow.qml"
MARKDOWN_NOTE_EDITOR_QML_PATH = QML_DIR / "MarkdownNoteEditorWindow.qml"


def load_actiondraw_qml() -> str:
    """Return the ActionDraw QML source as a string."""
    return ACTIONDRAW_QML_PATH.read_text(encoding="utf-8")


ACTIONDRAW_QML = load_actiondraw_qml()

__all__ = [
    "ACTIONDRAW_QML",
    "ACTIONDRAW_QML_PATH",
    "MARKDOWN_NOTE_EDITOR_QML_PATH",
    "QML_DIR",
    "load_actiondraw_qml",
]
