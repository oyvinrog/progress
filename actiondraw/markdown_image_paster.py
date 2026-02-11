"""Clipboard image helpers for markdown note editing."""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, QUrl, Slot
from PySide6.QtGui import QGuiApplication, QImage

SUPPORTED_IMAGE_MIME_TYPES = (
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/bmp",
    "image/gif",
)


def image_to_png_base64(image: QImage) -> str:
    """Return a PNG base64 payload for a QImage, or empty string on failure."""
    if image.isNull():
        return ""

    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    if not buffer.open(QIODevice.WriteOnly):
        return ""
    save_ok = image.save(buffer, "PNG")
    buffer.close()
    if not save_ok:
        return ""

    raw = bytes(byte_array)
    if not raw:
        return ""
    return base64.b64encode(raw).decode("ascii")


def markdown_image_from_qimage(image: QImage, alt_text: str = "pasted image") -> str:
    """Render a markdown image node from a QImage using a PNG data URL."""
    image_base64 = image_to_png_base64(image)
    if not image_base64:
        return ""
    return f"![{alt_text}](data:image/png;base64,{image_base64})"


def markdown_image_from_bytes(image_bytes: bytes, alt_text: str = "pasted image") -> str:
    """Render markdown image node from arbitrary encoded image bytes."""
    if not image_bytes:
        return ""
    image = QImage.fromData(image_bytes)
    return markdown_image_from_qimage(image, alt_text=alt_text)


def _markdown_image_from_url(url: QUrl, alt_text: str = "pasted image") -> str:
    if not url.isLocalFile():
        return ""
    local_path = url.toLocalFile()
    if not local_path:
        return ""
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        return ""
    try:
        image_bytes = path.read_bytes()
    except OSError:
        return ""
    return markdown_image_from_bytes(image_bytes, alt_text=alt_text)


class MarkdownImagePaster(QObject):
    """Expose clipboard image-to-markdown conversion to QML."""

    @Slot(result=str)
    def clipboardImageMarkdown(self) -> str:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return ""
        mime_data = clipboard.mimeData()
        if mime_data is None:
            return ""

        # Primary path
        if mime_data.hasImage():
            image = clipboard.image()
            markdown = markdown_image_from_qimage(image)
            if markdown:
                return markdown

        # Fallback for clipboards exposing image bytes via mime formats only.
        for mime_type in SUPPORTED_IMAGE_MIME_TYPES:
            if mime_data.hasFormat(mime_type):
                raw = bytes(mime_data.data(mime_type))
                markdown = markdown_image_from_bytes(raw)
                if markdown:
                    return markdown

        # Fallback for copied file paths pointing to image files.
        if mime_data.hasUrls():
            for url in mime_data.urls():
                markdown = _markdown_image_from_url(url)
                if markdown:
                    return markdown

        return ""
