"""Tests for markdown preview code-block formatting."""

import pytest

pygments = pytest.importorskip("pygments")
assert pygments

from actiondraw.markdown_preview_formatter import MarkdownPreviewFormatter  # noqa: E402


def test_sql_fenced_code_returns_highlighted_html():
    formatter = MarkdownPreviewFormatter()
    html = formatter.fencedCodeToHtml("sql", "SELECT id FROM users;")
    assert "<pre" in html
    assert "<code>" in html
    assert "SELECT" in html
    assert "span" in html


def test_python_alias_py_is_supported():
    formatter = MarkdownPreviewFormatter()
    html = formatter.fencedCodeToHtml("py", "def f(x):\n    return x")
    assert "<pre" in html
    assert "span" in html


def test_highlighted_tokens_use_inline_styles_for_qml_preview():
    formatter = MarkdownPreviewFormatter()
    html = formatter.fencedCodeToHtml("python", "def f(x):\n    return x")
    assert "span style=" in html


def test_unsupported_language_is_neutral_and_escaped():
    formatter = MarkdownPreviewFormatter()
    html = formatter.fencedCodeToHtml("javascript", "<script>alert(1)</script>")
    assert "<pre" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_markdown_to_display_html_renders_action_highlight_spans():
    formatter = MarkdownPreviewFormatter()
    html = formatter.markdownToDisplayHtml("\u2060Ship hub\u2061 and \u2062Do now\u2063")
    assert "#60a5fa" in html
    assert "#facc15" in html
    assert "Ship hub" in html
    assert "Do now" in html


def _document_for(formatter, markdown):
    from PySide6.QtGui import QTextDocument

    document = QTextDocument()
    document.setMarkdown(markdown)
    return document


def _position_of(document, text):
    block = document.begin()
    while block.isValid():
        if block.text() == text:
            return block.position()
        block = block.next()
    raise AssertionError(f"Rendered block not found: {text!r}")


@pytest.mark.parametrize("marker", ["-", "*", "+"])
def test_double_click_toggle_completes_and_restores_unordered_item(marker):
    formatter = MarkdownPreviewFormatter()
    markdown = f"{marker} A\n{marker} B\n{marker} C"

    document = _document_for(formatter, markdown)
    completed = formatter.toggleListItemAtPosition(
        markdown, document, _position_of(document, "B")
    )
    assert completed == f"{marker} A\n{marker} [x] ~~B~~\n{marker} C"

    completed_document = _document_for(formatter, completed)
    restored = formatter.toggleListItemAtPosition(
        completed, completed_document, _position_of(completed_document, "B")
    )
    assert restored == markdown


def test_toggle_uses_rendered_item_position_for_repeated_and_nested_items():
    formatter = MarkdownPreviewFormatter()
    markdown = "- Same\n  - Same\n- Same"
    document = _document_for(formatter, markdown)

    blocks = []
    block = document.begin()
    while block.isValid():
        if block.text() == "Same":
            blocks.append(block.position())
        block = block.next()

    updated = formatter.toggleListItemAtPosition(markdown, document, blocks[1])
    assert updated == "- Same\n  - [x] ~~Same~~\n- Same"


def test_toggle_completes_unchecked_task_item():
    formatter = MarkdownPreviewFormatter()
    markdown = "  *   [ ]   Waiting"
    document = _document_for(formatter, markdown)

    updated = formatter.toggleListItemAtPosition(
        markdown, document, _position_of(document, "Waiting")
    )
    assert updated == "  *   [x]   ~~Waiting~~"


def test_toggle_skips_fenced_list_syntax_when_mapping_rendered_item():
    formatter = MarkdownPreviewFormatter()
    markdown = "```\n- code\n```\n\n- Real"
    document = _document_for(formatter, markdown)

    updated = formatter.toggleListItemAtPosition(
        markdown, document, _position_of(document, "Real")
    )
    assert updated == "```\n- code\n```\n\n- [x] ~~Real~~"


def test_toggle_at_preview_point_resolves_rendered_list_item(app):
    assert app
    from PySide6.QtGui import QTextDocument

    formatter = MarkdownPreviewFormatter()
    markdown = "- A\n- B\n- C"
    width = 320.0
    document = QTextDocument()
    document.setHtml(formatter.markdownToDisplayHtml(markdown))
    document.setTextWidth(width)
    block = document.findBlock(_position_of(document, "B"))
    point = document.documentLayout().blockBoundingRect(block).center()

    updated = formatter.toggleListItemAtPoint(
        markdown, point.x(), point.y(), width
    )
    assert updated == "- A\n- [x] ~~B~~\n- C"


@pytest.mark.parametrize(
    "markdown, clicked_text",
    [
        ("1. Numbered", "Numbered"),
        ("Paragraph", "Paragraph"),
        ("```\n- code\n```", "- code"),
    ],
)
def test_toggle_ignores_non_bulleted_content(markdown, clicked_text):
    formatter = MarkdownPreviewFormatter()
    document = _document_for(formatter, markdown)

    updated = formatter.toggleListItemAtPosition(
        markdown, document, _position_of(document, clicked_text)
    )
    assert updated == markdown
