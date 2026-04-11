"""Clipboard helpers for importing markdown editor tabs from plain text."""

from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication


def parse_tabs_from_clipboard_text(text: str) -> List[Dict[str, str]]:
    """Convert plain clipboard text into markdown editor tabs."""
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    tabs: List[Dict[str, str]] = []
    for raw_line in normalized.split("\n"):
        name = raw_line.strip()
        if not name:
            continue
        tabs.append({"name": name, "text": ""})
    return tabs


class MarkdownTabClipboard(QObject):
    """Expose clipboard tab import helpers to QML."""

    @Slot(result="QVariantList")
    def clipboardTabs(self) -> List[Dict[str, str]]:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return []
        return parse_tabs_from_clipboard_text(clipboard.text())
