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
