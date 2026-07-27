"""Preview formatter for fenced markdown code blocks."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, Qt, QObject, Slot
from PySide6.QtGui import QTextDocument, QTextListFormat

try:
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import PythonLexer, SqlLexer
except Exception:  # pragma: no cover - handled by runtime fallback
    highlight = None
    HtmlFormatter = None
    PythonLexer = None
    SqlLexer = None


_PRE_STYLE = (
    "background:#111826;color:#dbe2f2;border:1px solid #334155;border-radius:6px;"
    "padding:10px;white-space:pre-wrap;font-family:Monospace;font-size:13px;"
)

_TAB_HIGHLIGHT_START = "\u2060"
_TAB_HIGHLIGHT_END = "\u2061"
_TASK_HIGHLIGHT_START = "\u2062"
_TASK_HIGHLIGHT_END = "\u2063"

_BULLET_LINE_RE = re.compile(
    r"^(?P<prefix>(?:(?:[ \t]{0,3}>[ \t]?)+)?[ \t]*)"
    r"(?P<marker>[-+*])(?P<spacing>[ \t]+)(?P<body>[^\r\n]*)(?P<ending>\r?\n)?$"
)
_FENCE_RE = re.compile(
    r"^(?:(?:[ \t]{0,3}>[ \t]?)+)?[ \t]{0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$"
)
_THEMATIC_BREAK_RE = re.compile(
    r"^(?:(?:[ \t]{0,3}>[ \t]?)+)?[ \t]{0,3}"
    r"(?P<marker>[-*_])(?:[ \t]*)(?P=marker)(?:[ \t]*(?P=marker)){1,}[ \t]*$"
)
_TASK_PREFIX_RE = re.compile(r"^\[(?P<state>[ xX])\](?P<spacing>[ \t]+)(?P<body>.*)$")
_FULL_STRIKE_RE = re.compile(r"^~~(?P<body>.*)~~$", re.DOTALL)
_UNORDERED_LIST_STYLES = {
    QTextListFormat.ListDisc,
    QTextListFormat.ListCircle,
    QTextListFormat.ListSquare,
}


@dataclass(frozen=True)
class _BulletLine:
    start: int
    end: int
    prefix: str
    marker: str
    spacing: str
    body: str
    ending: str


def _unordered_list_blocks(document: QTextDocument):
    block = document.begin()
    while block.isValid():
        text_list = block.textList()
        if text_list is not None and text_list.format().style() in _UNORDERED_LIST_STYLES:
            yield block
        block = block.next()


def _bullet_lines(markdown: str) -> list[_BulletLine]:
    """Return source lines that can represent Qt Markdown unordered-list blocks."""
    items: list[_BulletLine] = []
    offset = 0
    fence_char = ""
    fence_length = 0

    for line in (markdown or "").splitlines(keepends=True):
        content = line.rstrip("\r\n")
        fence_match = _FENCE_RE.match(content)
        if fence_match:
            fence = fence_match.group("fence")
            if not fence_char:
                fence_char = fence[0]
                fence_length = len(fence)
            elif fence[0] == fence_char and len(fence) >= fence_length:
                fence_char = ""
                fence_length = 0
            offset += len(line)
            continue

        if not fence_char and not _THEMATIC_BREAK_RE.match(content):
            match = _BULLET_LINE_RE.match(line)
            if match:
                prefix = match.group("prefix")
                unquoted_indent = prefix.rsplit(">", 1)[-1]
                # Four-space indentation is a code block unless it is nested
                # beneath a preceding list item.
                indent = len(unquoted_indent.expandtabs(4))
                preceding_indent = None
                if items:
                    preceding_prefix = items[-1].prefix.rsplit(">", 1)[-1]
                    preceding_indent = len(preceding_prefix.expandtabs(4))
                if indent <= 3 or (
                    preceding_indent is not None and indent > preceding_indent
                ):
                    items.append(
                        _BulletLine(
                            start=offset,
                            end=offset + len(line),
                            prefix=prefix,
                            marker=match.group("marker"),
                            spacing=match.group("spacing"),
                            body=match.group("body"),
                            ending=match.group("ending") or "",
                        )
                    )
        offset += len(line)

    # splitlines() returns no entry for an empty source and retains a final
    # non-newline line, so every actionable line is covered above.
    return items


def _toggle_bullet_body(body: str) -> str:
    task_match = _TASK_PREFIX_RE.match(body)
    if task_match and task_match.group("state").lower() == "x":
        restored = task_match.group("body")
        strike_match = _FULL_STRIKE_RE.match(restored)
        return strike_match.group("body") if strike_match else restored

    task_spacing = " "
    if task_match:
        task_spacing = task_match.group("spacing")
        body = task_match.group("body")

    if not _FULL_STRIKE_RE.match(body):
        body = f"~~{body}~~"
    return f"[x]{task_spacing}{body}"


def _toggle_bullet_at_index(markdown: str, index: int) -> str:
    items = _bullet_lines(markdown)
    if index < 0 or index >= len(items):
        return markdown

    item = items[index]
    replacement = (
        f"{item.prefix}{item.marker}{item.spacing}"
        f"{_toggle_bullet_body(item.body)}{item.ending}"
    )
    return f"{markdown[:item.start]}{replacement}{markdown[item.end:]}"


class MarkdownPreviewFormatter(QObject):
    """Render fenced SQL/Python code as HTML for QML rich text preview."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._pygments_formatter = self._build_formatter()
        self._python_lexer = PythonLexer(stripnl=False) if PythonLexer is not None else None
        self._sql_lexer = SqlLexer(stripnl=False) if SqlLexer is not None else None

    def _build_formatter(self):
        if HtmlFormatter is None:
            return None
        for style_name in ("native", "monokai"):
            try:
                # QML rich text does not include external CSS rules for token classes,
                # so emit inline styles for each token span.
                return HtmlFormatter(style=style_name, nowrap=True, noclasses=True)
            except Exception:
                continue
        return None

    def _lexer_for_language(self, language: str):
        lang = (language or "").strip().lower()
        if lang in {"python", "py"}:
            return self._python_lexer
        if lang == "sql":
            return self._sql_lexer
        return None

    def _inject_action_highlights(self, source: str) -> str:
        text = source or ""
        text = text.replace(
            _TAB_HIGHLIGHT_START,
            '<span style="background-color:#60a5fa;color:#000000;">',
        ).replace(_TAB_HIGHLIGHT_END, "</span>")
        text = text.replace(
            _TASK_HIGHLIGHT_START,
            '<span style="background-color:#facc15;color:#000000;">',
        ).replace(_TASK_HIGHLIGHT_END, "</span>")
        return text

    @Slot(str, str, result=str)
    def fencedCodeToHtml(self, language: str, code: str) -> str:  # noqa: N802
        source = code or ""
        lexer = self._lexer_for_language(language)
        if lexer is None or highlight is None or self._pygments_formatter is None:
            escaped = html.escape(source)
            return f"<pre style=\"{_PRE_STYLE}\"><code>{escaped}</code></pre>"

        try:
            body = highlight(source, lexer, self._pygments_formatter)
        except Exception:
            body = html.escape(source)
        return f"<pre style=\"{_PRE_STYLE}\"><code>{body}</code></pre>"

    @Slot(str, result=str)
    def markdownToDisplayHtml(self, markdown: str) -> str:  # noqa: N802
        document = QTextDocument()
        document.setMarkdown(self._inject_action_highlights(markdown or ""))
        return document.toHtml()

    @Slot(str, QObject, int, result=str)
    def toggleListItemAtPosition(  # noqa: N802
        self,
        markdown: str,
        quick_document: QObject,
        position: int,
    ) -> str:
        """Toggle the unordered-list item at a rendered document position."""
        if quick_document is None or position < 0:
            return markdown

        document_getter = getattr(quick_document, "textDocument", None)
        document = document_getter() if callable(document_getter) else quick_document
        if not isinstance(document, QTextDocument):
            return markdown

        clicked_block = document.findBlock(position)
        if not clicked_block.isValid():
            return markdown

        clicked_list = clicked_block.textList()
        if (
            clicked_list is None
            or clicked_list.format().style() not in _UNORDERED_LIST_STYLES
        ):
            return markdown

        for index, block in enumerate(_unordered_list_blocks(document)):
            if block == clicked_block:
                return _toggle_bullet_at_index(markdown or "", index)
        return markdown

    @Slot(str, float, float, float, result=str)
    def toggleListItemAtPoint(  # noqa: N802
        self,
        markdown: str,
        x: float,
        y: float,
        width: float,
    ) -> str:
        """Toggle the unordered-list item at a point in the QML preview text."""
        if width <= 0 or x < 0 or y < 0:
            return markdown

        document = QTextDocument()
        document.setHtml(self.markdownToDisplayHtml(markdown or ""))
        document.setTextWidth(width)
        position = document.documentLayout().hitTest(QPointF(x, y), Qt.FuzzyHit)
        return self.toggleListItemAtPosition(markdown, document, position)
