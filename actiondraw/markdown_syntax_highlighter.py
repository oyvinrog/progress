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

_STATE_PLAIN = -1
_STATE_CODE_PYTHON = 1
_STATE_CODE_SQL = 2
_STATE_CODE_OTHER = 3


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


class MarkdownCodeFenceHighlighter(QSyntaxHighlighter):
    """Highlight SQL/Python fenced code in markdown text documents."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._code_base_format = _build_code_base_format()
        self._fence_format = _build_fence_format()
        self._lexers = self._build_lexers()
        self._pygments_style = self._build_style()
        self._token_formats: Dict[object, QTextCharFormat] = {}

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

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        prev_state = self.previousBlockState()

        if prev_state in (_STATE_CODE_PYTHON, _STATE_CODE_SQL, _STATE_CODE_OTHER):
            if _FENCE_RE.match(text):
                self.setFormat(0, len(text), self._fence_format)
                self.setCurrentBlockState(_STATE_PLAIN)
                return
            self._highlight_lexed_line(text, prev_state)
            self.setCurrentBlockState(prev_state)
            return

        opening_match = _FENCE_RE.match(text)
        if opening_match:
            self.setFormat(0, len(text), self._fence_format)
            self.setCurrentBlockState(self._language_to_state(opening_match.group(1)))
            return

        self.setCurrentBlockState(_STATE_PLAIN)


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
