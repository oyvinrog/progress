"""Shared parsing helpers for clipboard outlines."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


_OPML_OPENING_TAG = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?opml(?:\s|>)", re.IGNORECASE)


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.rsplit(":", 1)[-1]


def looks_like_opml(text: str) -> bool:
    """Return whether *text* appears intended to be an OPML document."""
    return bool(text and _OPML_OPENING_TAG.search(text))


def parse_opml_text(text: str) -> list[dict[str, Any]] | None:
    """Return a flattened OPML outline, or ``None`` for non/invalid OPML."""
    if not looks_like_opml(text):
        return None
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None

    if _xml_local_name(root.tag).lower() != "opml":
        return None

    body = next(
        (child for child in root if _xml_local_name(child.tag).lower() == "body"),
        None,
    )
    if body is None:
        return None

    entries: list[dict[str, Any]] = []

    def visit(outline: ET.Element, level: int) -> None:
        text_value = outline.get("text")
        if text_value is None:
            text_value = outline.get("title")
        if text_value is None:
            text_value = (outline.text or "").strip()
        if text_value.strip():
            entries.append({"text": text_value, "level": level})

        next_level = level + 1 if text_value.strip() else level
        for child_outline in outline:
            if _xml_local_name(child_outline.tag).lower() == "outline":
                visit(child_outline, next_level)

    for child in body:
        if _xml_local_name(child.tag).lower() == "outline":
            visit(child, 0)

    return entries or None


def parse_text_hierarchy(text: str) -> list[dict[str, Any]]:
    """Parse non-empty lines into a hierarchy based on changing indentation."""
    entries: list[dict[str, Any]] = []
    indent_stack: list[int] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        leading = len(raw_line) - len(raw_line.lstrip(" \t"))
        indent_len = len(raw_line[:leading].replace("\t", "    "))
        if not indent_stack:
            indent_stack = [indent_len]
            level = 0
        elif indent_len > indent_stack[-1]:
            indent_stack.append(indent_len)
            level = len(indent_stack) - 1
        else:
            while indent_stack and indent_len < indent_stack[-1]:
                indent_stack.pop()
            if not indent_stack:
                indent_stack = [indent_len]
                level = 0
            elif indent_len > indent_stack[-1]:
                indent_stack.append(indent_len)
                level = len(indent_stack) - 1
            else:
                level = len(indent_stack) - 1
        entries.append({"text": raw_line.lstrip(" \t").strip(), "level": level})
    return entries


def outline_to_opml(root: Any, title: str = "ActionDraw Branch") -> str:
    """Serialize a tree with ``text`` and ``children`` attributes as OPML."""
    opml = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = title
    body = ET.SubElement(opml, "body")

    def append_outline(parent: ET.Element, node: Any) -> None:
        outline = ET.SubElement(parent, "outline", {"text": str(node.text)})
        for child in node.children:
            append_outline(outline, child)

    append_outline(body, root)
    xml_text = ET.tostring(opml, encoding="unicode", short_empty_elements=False)
    return f'<?xml version="1.0" encoding="UTF-8"?>{xml_text}'


def outline_to_indented_text(root: Any, indent: str = "  ") -> str:
    """Serialize a tree with ``text`` and ``children`` attributes as plain text."""
    lines: list[str] = []

    def append_line(node: Any, level: int) -> None:
        lines.append(f"{indent * level}{node.text}")
        for child in node.children:
            append_line(child, level + 1)

    append_line(root, 0)
    return "\n".join(lines)
