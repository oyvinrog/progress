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
