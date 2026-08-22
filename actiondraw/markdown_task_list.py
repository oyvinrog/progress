"""Helpers for turning plain Markdown dash lists into task titles."""

from __future__ import annotations

import re


_DASH_TASK_RE = re.compile(r"^[ \t]*-[ \t]+(?P<title>.*?)[ \t]*$")
_CHECKBOX_RE = re.compile(r"^\[[ xX]\](?:[ \t]+|$)")


def parse_markdown_task_list(markdown: str) -> list[str]:
    """Return titles from a strict, multi-item Markdown dash list.

    Blank lines are ignored and indentation is flattened. Every other line
    must be a plain ``- title`` item; checkboxes and other list forms are not
    accepted. A single bullet remains the domain of the existing single-task
    action.
    """

    titles: list[str] = []
    for line in str(markdown or "").splitlines():
        if not line.strip():
            continue
        match = _DASH_TASK_RE.fullmatch(line)
        if match is None:
            return []
        title = match.group("title").strip()
        if not title or _CHECKBOX_RE.match(title):
            return []
        titles.append(title)
    return titles if len(titles) >= 2 else []
