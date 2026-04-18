"""Tests for markdown fenced code syntax highlighting."""

import pytest
from PySide6.QtGui import QTextDocument

pygments = pytest.importorskip("pygments")
assert pygments

from actiondraw.markdown_syntax_highlighter import (  # noqa: E402
    MarkdownCodeFenceHighlighter,
    MarkdownHighlighterBridge,
)


def _block_with_text(document: QTextDocument, expected_text: str):
    block = document.firstBlock()
    while block.isValid():
        if block.text() == expected_text:
            return block
        block = block.next()
    raise AssertionError(f"Could not find block text: {expected_text!r}")


def _format_ranges_for_line(document: QTextDocument, text: str):
    block = _block_with_text(document, text)
    return list(block.layout().formats())


def test_python_fenced_block_is_token_highlighted(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText("Intro\n```python\ndef foo(x):\n    return x + 1  # inc\n```\nOutro\n")
    highlighter.rehighlight()

    prose_ranges = _format_ranges_for_line(document, "Intro")
    assert prose_ranges == []

    python_ranges = _format_ranges_for_line(document, "def foo(x):")
    assert len(python_ranges) >= 2


def test_sql_fenced_block_is_token_highlighted(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText(
        "```sql\nSELECT id, name FROM users WHERE id = 1;\n```\n"
    )
    highlighter.rehighlight()

    sql_ranges = _format_ranges_for_line(document, "SELECT id, name FROM users WHERE id = 1;")
    assert len(sql_ranges) >= 2


def test_unsupported_language_uses_neutral_code_style(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText("```javascript\nconst x = 1;\n```\n")
    highlighter.rehighlight()

    ranges = _format_ranges_for_line(document, "const x = 1;")
    assert len(ranges) == 1
    assert ranges[0].format.foreground().color().name().lower() == "#dbe2f2"


def test_unclosed_fence_continues_highlighting_until_end(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText("```sql\nSELECT 1\nstill code\n")
    highlighter.rehighlight()

    tail_ranges = _format_ranges_for_line(document, "still code")
    assert len(tail_ranges) >= 1


def test_python_alias_py_is_supported(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText("```py\ndef x():\n    pass\n```\n")
    highlighter.rehighlight()

    alias_ranges = _format_ranges_for_line(document, "def x():")
    assert len(alias_ranges) >= 2


def test_bridge_attaches_once_and_highlights_document(app):
    document = QTextDocument()
    bridge = MarkdownHighlighterBridge()

    bridge.attachToTextDocument(document)
    bridge.attachToTextDocument(document)
    assert len(bridge._highlighters) == 1

    document.setPlainText("```python\nprint('ok')\n```\n")
    highlighter = next(iter(bridge._highlighters.values()))
    highlighter.rehighlight()
    line_ranges = _format_ranges_for_line(document, "print('ok')")
    assert len(line_ranges) >= 1


def test_bridge_accepts_property_text_document(app):
    class _PropertyDoc:
        def __init__(self, doc):
            self.textDocument = doc

    document = QTextDocument()
    bridge = MarkdownHighlighterBridge()
    bridge.attachToTextDocument(_PropertyDoc(document))
    assert len(bridge._highlighters) == 1


def test_invisible_action_markers_are_highlighted(app):
    document = QTextDocument()
    highlighter = MarkdownCodeFenceHighlighter(document)
    document.setPlainText("\u2060Ship hub\u2061 and \u2062Do now\u2063")
    highlighter.rehighlight()

    ranges = _format_ranges_for_line(document, "\u2060Ship hub\u2061 and \u2062Do now\u2063")
    assert any(
        r.start == 1
        and r.length == len("Ship hub")
        and r.format.background().color().name().lower() == "#60a5fa"
        and r.format.foreground().color().name().lower() == "#000000"
        for r in ranges
    )
    assert any(
        r.format.background().color().name().lower() == "#facc15"
        and r.format.foreground().color().name().lower() == "#000000"
        for r in ranges
    )
