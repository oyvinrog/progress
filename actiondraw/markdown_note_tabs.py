"""Helpers for normalizing editor tabs used by markdown windows."""

from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_TAB_NAME = "Tab 1"


def normalize_editor_tabs(tabs: Any, fallback_text: str = "", fallback_name: str = DEFAULT_TAB_NAME) -> List[Dict[str, str]]:
    """Return a stable tab list with at least one tab."""
    normalized: List[Dict[str, str]] = []
    if isinstance(tabs, list):
        for index, tab in enumerate(tabs):
            if not isinstance(tab, dict):
                continue
            name = str(tab.get("name", "") or "").strip()
            text = str(tab.get("text", "") or "")
            normalized.append(
                {
                    "name": name or f"Tab {index + 1}",
                    "text": text,
                }
            )
    if normalized:
        return normalized
    return [{"name": str(fallback_name or DEFAULT_TAB_NAME), "text": str(fallback_text or "")}]


def first_tab_text(tabs: Any, fallback_text: str = "") -> str:
    """Return the first tab text from a normalized tab payload."""
    normalized = normalize_editor_tabs(tabs, fallback_text=fallback_text)
    if not normalized:
        return str(fallback_text or "")
    return str(normalized[0].get("text", "") or "")
