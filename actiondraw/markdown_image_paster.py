"""Clipboard image helpers for markdown note editing."""

from __future__ import annotations

import base64
import hashlib
import re
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

_IMAGE_ATTRS_PATTERN = r"(?P<attrs>\{[^}]*\})?"
_DATA_IMAGE_MARKDOWN_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<url>data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)\)"
    + _IMAGE_ATTRS_PATTERN
)
_TOKEN_IMAGE_MARKDOWN_RE = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<url>adimg://(?P<token>[a-f0-9]{8}(?:-\d+)?))\)"
    + _IMAGE_ATTRS_PATTERN
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

    def __init__(self) -> None:
        super().__init__()
        self._token_to_markdown: dict[str, str] = {}
        self._markdown_to_token: dict[str, str] = {}

    def _register_markdown_image(self, markdown: str) -> str:
        if not markdown:
            return ""
        existing = self._markdown_to_token.get(markdown)
        if existing:
            return existing

        digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:8]
        token = digest
        suffix = 1
        while token in self._token_to_markdown and self._token_to_markdown[token] != markdown:
            token = f"{digest}-{suffix}"
            suffix += 1

        self._token_to_markdown[token] = markdown
        self._markdown_to_token[markdown] = token
        return token

    def _resolve_token_url(self, token: str) -> str:
        if not token:
            return ""
        markdown = self._token_to_markdown.get(token, "")
        if not markdown:
            return ""
        match = _DATA_IMAGE_MARKDOWN_RE.fullmatch(markdown)
        if not match:
            return ""
        return match.group("url")

    @Slot(str, result=str)
    def compactMarkdownImages(self, markdown: str) -> str:
        if not markdown:
            return ""

        def _replace(match: re.Match[str]) -> str:
            alt = match.group("alt")
            full_markdown = match.group(0)
            attrs = match.group("attrs") or ""
            token = self._register_markdown_image(full_markdown)
            if not token:
                return full_markdown
            return f"![{alt}](adimg://{token}){attrs}"

        return _DATA_IMAGE_MARKDOWN_RE.sub(_replace, markdown)

    @Slot(str, result=str)
    def expandMarkdownImages(self, markdown: str) -> str:
        if not markdown:
            return ""

        def _replace(match: re.Match[str]) -> str:
            token = match.group("token")
            alt = match.group("alt")
            attrs = match.group("attrs") or ""
            resolved_url = self._resolve_token_url(token)
            if resolved_url:
                return f"![{alt}]({resolved_url}){attrs}"
            return match.group(0)

        return _TOKEN_IMAGE_MARKDOWN_RE.sub(_replace, markdown)

    @Slot(result=str)
    def clipboardImageMarkdownToken(self) -> str:
        markdown = self.clipboardImageMarkdown()
        if not markdown:
            return ""
        return self.compactMarkdownImages(markdown)

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

    @Slot(str, result=str)
    def resolveMarkdownImageUrl(self, url: str) -> str:
        if not url:
            return ""
        token_prefix = "adimg://"
        if not url.startswith(token_prefix):
            return url
        token = url[len(token_prefix) :]
        if not token:
            return ""
        return self._resolve_token_url(token)
