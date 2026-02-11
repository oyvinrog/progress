"""Compatibility loader for markdown note editor QML source."""

from __future__ import annotations

from .qml import MARKDOWN_NOTE_EDITOR_QML_PATH


def load_markdown_note_qml() -> str:
    """Return the markdown note editor QML source as a string."""
    return MARKDOWN_NOTE_EDITOR_QML_PATH.read_text(encoding="utf-8")


MARKDOWN_NOTE_QML = load_markdown_note_qml()

__all__ = ["MARKDOWN_NOTE_QML", "load_markdown_note_qml"]
