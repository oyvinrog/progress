"""Preview formatter for fenced markdown code blocks."""

from __future__ import annotations

import html
from typing import Optional

from PySide6.QtCore import QObject, Slot

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
