"""Tests for markdown clipboard image pasting helpers."""

import re

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData
from PySide6.QtGui import QColor, QGuiApplication, QImage

from actiondraw.markdown_image_paster import (
    MarkdownImagePaster,
    image_to_png_base64,
    markdown_image_from_qimage,
)


def test_image_to_png_base64_null_image_returns_empty():
    assert image_to_png_base64(QImage()) == ""


def test_markdown_image_from_qimage_renders_data_url():
    image = QImage(3, 2, QImage.Format_ARGB32)
    image.fill(QColor("#ff0000"))

    markdown = markdown_image_from_qimage(image, "diagram")
    assert markdown.startswith("![diagram](data:image/png;base64,")
    assert markdown.endswith(")")


def test_clipboard_image_markdown_empty_for_text_clipboard(app):
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("plain text")

    paster = MarkdownImagePaster()
    assert paster.clipboardImageMarkdown() == ""


def test_clipboard_image_markdown_when_clipboard_has_image(app):
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    image = QImage(2, 2, QImage.Format_ARGB32)
    image.fill(QColor("#00ff00"))
    clipboard.setImage(image)

    paster = MarkdownImagePaster()
    markdown = paster.clipboardImageMarkdown()
    assert markdown.startswith("![pasted image](data:image/png;base64,")
    assert markdown.endswith(")")


def test_clipboard_image_markdown_from_image_png_mime_data(app):
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None

    image = QImage(2, 2, QImage.Format_ARGB32)
    image.fill(QColor("#0000ff"))
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    assert buffer.open(QIODevice.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()

    mime = QMimeData()
    mime.setData("image/png", byte_array)
    clipboard.setMimeData(mime)

    paster = MarkdownImagePaster()
    markdown = paster.clipboardImageMarkdown()
    assert markdown.startswith("![pasted image](data:image/png;base64,")
    assert markdown.endswith(")")


def test_compact_and_expand_markdown_images_roundtrip():
    image = QImage(3, 2, QImage.Format_ARGB32)
    image.fill(QColor("#ffaa00"))
    full = markdown_image_from_qimage(image, "diagram")
    markdown = f"Before\n{full}\nAfter"

    paster = MarkdownImagePaster()
    compacted = paster.compactMarkdownImages(markdown)
    assert "data:image/png;base64," not in compacted
    assert re.search(r"!\[diagram\]\(adimg://[a-f0-9]{8}(?:-\d+)?\)", compacted)

    expanded = paster.expandMarkdownImages(compacted)
    assert expanded == markdown


def test_compact_and_expand_markdown_images_preserve_size_attrs():
    image = QImage(4, 3, QImage.Format_ARGB32)
    image.fill(QColor("#88cc11"))
    full = markdown_image_from_qimage(image, "diagram")
    markdown = f"{full}{{width=320 height=240}}"

    paster = MarkdownImagePaster()
    compacted = paster.compactMarkdownImages(markdown)
    assert re.search(r"!\[diagram\]\(adimg://[a-f0-9]{8}(?:-\d+)?\)\{width=320 height=240\}", compacted)

    expanded = paster.expandMarkdownImages(compacted)
    assert expanded == markdown


def test_expand_markdown_images_uses_current_alt_and_attrs():
    image = QImage(5, 5, QImage.Format_ARGB32)
    image.fill(QColor("#332211"))
    full = markdown_image_from_qimage(image, "original")
    paster = MarkdownImagePaster()
    compacted = paster.compactMarkdownImages(full)

    token_match = re.search(r"adimg://([a-f0-9]{8}(?:-\d+)?)", compacted)
    assert token_match is not None
    token = token_match.group(1)
    modified = f"![changed](adimg://{token}){{width=210 height=160}}"

    expanded = paster.expandMarkdownImages(modified)
    assert expanded.startswith("![changed](data:image/png;base64,")
    assert expanded.endswith("){width=210 height=160}")


def test_compact_markdown_images_keeps_non_image_content():
    markdown = "# Title\nNormal text with no images."
    paster = MarkdownImagePaster()
    assert paster.compactMarkdownImages(markdown) == markdown
    assert paster.expandMarkdownImages(markdown) == markdown


def test_expand_markdown_images_leaves_unknown_tokens_unchanged():
    markdown = "![x](adimg://deadbeef)"
    paster = MarkdownImagePaster()
    assert paster.expandMarkdownImages(markdown) == markdown


def test_compact_markdown_images_handles_multiple_images():
    image1 = QImage(2, 2, QImage.Format_ARGB32)
    image1.fill(QColor("#112233"))
    image2 = QImage(2, 2, QImage.Format_ARGB32)
    image2.fill(QColor("#445566"))
    full1 = markdown_image_from_qimage(image1, "img1")
    full2 = markdown_image_from_qimage(image2, "img2")
    markdown = f"{full1}\n{full2}"

    paster = MarkdownImagePaster()
    compacted = paster.compactMarkdownImages(markdown)
    tokens = re.findall(r"adimg://([a-f0-9]{8}(?:-\d+)?)", compacted)
    assert len(tokens) == 2
    assert tokens[0] != tokens[1]

    expanded = paster.expandMarkdownImages(compacted)
    assert expanded == markdown


def test_clipboard_image_markdown_token_when_clipboard_has_image(app):
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    image = QImage(2, 2, QImage.Format_ARGB32)
    image.fill(QColor("#00aaff"))
    clipboard.setImage(image)

    paster = MarkdownImagePaster()
    markdown = paster.clipboardImageMarkdownToken()
    assert re.search(r"!\[pasted image\]\(adimg://[a-f0-9]{8}(?:-\d+)?\)", markdown)

    expanded = paster.expandMarkdownImages(markdown)
    assert expanded.startswith("![pasted image](data:image/png;base64,")
    assert expanded.endswith(")")


def test_clipboard_image_markdown_token_empty_for_text_clipboard(app):
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    clipboard.setText("plain text")

    paster = MarkdownImagePaster()
    assert paster.clipboardImageMarkdownToken() == ""


def test_resolve_markdown_image_url_from_token():
    image = QImage(2, 2, QImage.Format_ARGB32)
    image.fill(QColor("#cc22aa"))
    full = markdown_image_from_qimage(image, "x")
    paster = MarkdownImagePaster()
    compacted = paster.compactMarkdownImages(full)

    token_match = re.search(r"adimg://([a-f0-9]{8}(?:-\d+)?)", compacted)
    assert token_match is not None
    token = token_match.group(1)

    resolved = paster.resolveMarkdownImageUrl(f"adimg://{token}")
    assert resolved.startswith("data:image/png;base64,")

    passthrough = paster.resolveMarkdownImageUrl("https://example.com/image.png")
    assert passthrough == "https://example.com/image.png"
