"""Tests for markdown clipboard image pasting helpers."""

import sys

import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData
from PySide6.QtGui import QColor, QGuiApplication, QImage

from actiondraw.markdown_image_paster import (
    MarkdownImagePaster,
    image_to_png_base64,
    markdown_image_from_qimage,
)


@pytest.fixture(scope="session")
def app():
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)
    return instance


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
