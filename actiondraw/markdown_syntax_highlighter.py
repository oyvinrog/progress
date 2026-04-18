"""Markdown fenced-code syntax highlighting for SQL and Python."""

from __future__ import annotations

import re
from typing import Dict, Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

try:
    from pygments import lex
    from pygments.lexers import PythonLexer, SqlLexer
    from pygments.styles import get_style_by_name
    from pygments.token import Token
except Exception:  # pragma: no cover - handled by runtime fallback
    lex = None
    PythonLexer = None
    SqlLexer = None
    Token = None
    get_style_by_name = None


_FENCE_RE = re.compile(r"^\s*```+\s*([A-Za-z0-9_+-]*)\s*$")

_STATE_PLAIN = 0
_STATE_CODE_PYTHON = 1
_STATE_CODE_SQL = 2
_STATE_CODE_OTHER = 3

_INLINE_NONE = 0
_INLINE_TAB = 1
_INLINE_TASK = 2

_TAB_HIGHLIGHT_START = "\u2060"
_TAB_HIGHLIGHT_END = "\u2061"
_TASK_HIGHLIGHT_START = "\u2062"
_TASK_HIGHLIGHT_END = "\u2063"


def _build_code_base_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#dbe2f2"))
    fmt.setFontFixedPitch(True)
    mono = QFont("Monospace")
    mono.setStyleHint(QFont.Monospace)
    fmt.setFont(mono)
    return fmt


def _build_fence_format() -> QTextCharFormat:
    fmt = QTextCharFormat(_build_code_base_format())
    fmt.setForeground(QColor("#8fa3bf"))
    return fmt


def _build_highlight_format(background: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setBackground(QColor(background))
    fmt.setForeground(QColor("#000000"))
    return fmt


def _build_marker_format() -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor("#1b2028"))
    return fmt


class MarkdownCodeFenceHighlighter(QSyntaxHighlighter):
    """Highlight SQL/Python fenced code in markdown text documents."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._code_base_format = _build_code_base_format()
        self._fence_format = _build_fence_format()
        self._tab_highlight_format = _build_highlight_format("#60a5fa")
        self._task_highlight_format = _build_highlight_format("#facc15")
        self._marker_format = _build_marker_format()
        self._lexers = self._build_lexers()
        self._pygments_style = self._build_style()
        self._token_formats: Dict[object, QTextCharFormat] = {}

    def _encode_state(self, code_state: int, inline_state: int) -> int:
        return (inline_state << 8) | code_state

    def _decode_state(self, state: int) -> tuple[int, int]:
        if state < 0:
            return _STATE_PLAIN, _INLINE_NONE
        return state & 0xFF, (state >> 8) & 0xFF

    def _build_lexers(self) -> Dict[int, object]:
        lexers: Dict[int, object] = {}
        if PythonLexer is not None:
            lexers[_STATE_CODE_PYTHON] = PythonLexer(stripnl=False)
        if SqlLexer is not None:
            lexers[_STATE_CODE_SQL] = SqlLexer(stripnl=False)
        return lexers

    def _build_style(self):
        if get_style_by_name is None:
            return None
        for style_name in ("native", "monokai"):
            try:
                return get_style_by_name(style_name)
            except Exception:
                continue
        return None

    def _language_to_state(self, language: str) -> int:
        lang = (language or "").strip().lower()
        if lang in {"python", "py"}:
            return _STATE_CODE_PYTHON
        if lang == "sql":
            return _STATE_CODE_SQL
        return _STATE_CODE_OTHER

    def _token_format(self, token_type: object) -> QTextCharFormat:
        if token_type in self._token_formats:
            return self._token_formats[token_type]

        fmt = QTextCharFormat(self._code_base_format)
        if self._pygments_style is not None:
            token_style = self._pygments_style.style_for_token(token_type)
            color = token_style.get("color")
            bgcolor = token_style.get("bgcolor")
            if color:
                fmt.setForeground(QColor(f"#{color}"))
            if bgcolor:
                fmt.setBackground(QColor(f"#{bgcolor}"))
            if token_style.get("bold"):
                fmt.setFontWeight(QFont.Bold)
            if token_style.get("italic"):
                fmt.setFontItalic(True)
            if token_style.get("underline"):
                fmt.setFontUnderline(True)

        self._token_formats[token_type] = fmt
        return fmt

    def _highlight_lexed_line(self, text: str, state: int) -> None:
        self.setFormat(0, len(text), self._code_base_format)
        lexer = self._lexers.get(state)
        if lexer is None or lex is None or Token is None:
            return
        try:
            offset = 0
            for token_type, token_text in lex(text, lexer):
                token_len = len(token_text)
                if token_len == 0:
                    continue
                if token_type in Token.Text:
                    offset += token_len
                    continue
                self.setFormat(offset, token_len, self._token_format(token_type))
                offset += token_len
        except Exception:
            return

    def _apply_inline_highlights(self, text: str, initial_inline_state: int) -> int:
        inline_state = initial_inline_state
        marker_map = {
            _TAB_HIGHLIGHT_START: ("start", _INLINE_TAB),
            _TAB_HIGHLIGHT_END: ("end", _INLINE_TAB),
            _TASK_HIGHLIGHT_START: ("start", _INLINE_TASK),
            _TASK_HIGHLIGHT_END: ("end", _INLINE_TASK),
        }
        highlight_formats = {
            _INLINE_TAB: self._tab_highlight_format,
            _INLINE_TASK: self._task_highlight_format,
        }

        index = 0
        text_length = len(text)
        while index < text_length:
            marker = marker_map.get(text[index])
            if marker is not None:
                self.setFormat(index, 1, self._marker_format)
                marker_kind, marker_state = marker
                if marker_kind == "start":
                    inline_state = marker_state
                elif inline_state == marker_state:
                    inline_state = _INLINE_NONE
                index += 1
                continue

            chunk_start = index
            while index < text_length and text[index] not in marker_map:
                index += 1
            if inline_state != _INLINE_NONE and index > chunk_start:
                self.setFormat(chunk_start, index - chunk_start, highlight_formats[inline_state])

        return inline_state

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        prev_code_state, prev_inline_state = self._decode_state(self.previousBlockState())

        if prev_code_state in (_STATE_CODE_PYTHON, _STATE_CODE_SQL, _STATE_CODE_OTHER):
            if _FENCE_RE.match(text):
                self.setFormat(0, len(text), self._fence_format)
                self.setCurrentBlockState(self._encode_state(_STATE_PLAIN, prev_inline_state))
                return
            self._highlight_lexed_line(text, prev_code_state)
            next_inline_state = self._apply_inline_highlights(text, prev_inline_state)
            self.setCurrentBlockState(self._encode_state(prev_code_state, next_inline_state))
            return

        opening_match = _FENCE_RE.match(text)
        if opening_match:
            self.setFormat(0, len(text), self._fence_format)
            self.setCurrentBlockState(
                self._encode_state(self._language_to_state(opening_match.group(1)), prev_inline_state)
            )
            return

        next_inline_state = self._apply_inline_highlights(text, prev_inline_state)
        self.setCurrentBlockState(self._encode_state(_STATE_PLAIN, next_inline_state))


class MarkdownHighlighterBridge(QObject):
    """Bridge for attaching markdown syntax highlighters from QML."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._highlighters: Dict[int, MarkdownCodeFenceHighlighter] = {}

    @Slot(QObject)
    def attachToTextDocument(self, text_document_obj: Optional[QObject]) -> None:
        if text_document_obj is None:
            return

        text_document: Optional[QTextDocument] = None
        to_text_document = getattr(text_document_obj, "textDocument", None)
        if callable(to_text_document):
            try:
                text_document = to_text_document()
            except Exception:
                text_document = None
        elif isinstance(to_text_document, QTextDocument):
            text_document = to_text_document
        elif isinstance(text_document_obj, QTextDocument):
            text_document = text_document_obj

        if text_document is None:
            return

        key = id(text_document)
        if key in self._highlighters:
            return

        self._highlighters[key] = MarkdownCodeFenceHighlighter(text_document)
