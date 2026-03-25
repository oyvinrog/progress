"""Qt-native markdown-to-PDF export with embedded images."""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote

from PySide6.QtCore import QMarginsF, QRectF, QSizeF, QUrl, QObject, Slot
from PySide6.QtGui import (
    QAbstractTextDocumentLayout,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
    QTextFormat,
    QTextImageFormat,
)
from PySide6.QtQml import QJSValue

from .markdown_image_paster import MarkdownImagePaster

_IMAGE_ATTRS_PATTERN = r"(?P<attrs>\{[^}]*\})?"
_IMAGE_NODE_PATTERN = r"!\[(?P<alt>[^\]]*)\]\((?P<url>[^)\s]+)\)" + _IMAGE_ATTRS_PATTERN
_MARKDOWN_IMAGE_RE = re.compile(_IMAGE_NODE_PATTERN)
_STANDALONE_IMAGE_LINE_RE = re.compile(r"^\s*" + _IMAGE_NODE_PATTERN + r"\s*$")
_WIDTH_RE = re.compile(r"width\s*=\s*(\d+)", re.IGNORECASE)
_HEIGHT_RE = re.compile(r"height\s*=\s*(\d+)", re.IGNORECASE)

_PDF_RESOLUTION_DPI = 96
_PDF_MARGIN_POINTS = 36.0
_DEFAULT_PAGE_SIZE = QSizeF(794.0, 1123.0)
_DEFAULT_STYLESHEET = """
body {
    font-family: "Trebuchet MS", "Segoe UI", sans-serif;
    font-size: 12pt;
    line-height: 1.35;
    color: #1f2937;
}
h1 {
    margin-top: 0;
    margin-bottom: 14px;
    color: #0f172a;
}
h2 {
    margin-top: 16px;
    margin-bottom: 10px;
    color: #1e293b;
}
p {
    margin-top: 0;
    margin-bottom: 10px;
}
ul, ol {
    margin-top: 0;
    margin-bottom: 12px;
}
li {
    margin-bottom: 4px;
}
pre, code {
    font-family: "Consolas", "Courier New", monospace;
}
pre {
    background: #f8fafc;
    border: 1px solid #dbe4ee;
    padding: 10px;
    margin-top: 6px;
    margin-bottom: 12px;
    white-space: pre-wrap;
}
blockquote {
    color: #475569;
    border-left: 3px solid #cbd5e1;
    margin-left: 0;
    padding-left: 10px;
}
a {
    color: #2563eb;
    text-decoration: none;
}
"""


@dataclass(frozen=True)
class MarkdownImage:
    """Parsed markdown image node."""

    alt: str
    url: str
    width: int = 0
    height: int = 0
    start: int = 0
    end: int = 0


@dataclass(frozen=True)
class MarkdownSegment:
    """Stable export segment preserving markdown line boundaries."""

    kind: str
    text: str = ""
    image: MarkdownImage | None = None


@dataclass(frozen=True)
class PdfLayoutMetrics:
    """Cheap metrics used for regression tests around layout stability."""

    page_count: int
    block_count: int
    width: float
    height: float
    character_count: int


def parse_image_attrs(attrs_text: str) -> tuple[int, int]:
    """Extract width/height attrs from markdown image attrs."""
    if not attrs_text:
        return 0, 0
    width_match = _WIDTH_RE.search(attrs_text)
    height_match = _HEIGHT_RE.search(attrs_text)
    width = int(width_match.group(1)) if width_match else 0
    height = int(height_match.group(1)) if height_match else 0
    return width, height


def iter_markdown_images(markdown: str) -> Iterable[MarkdownImage]:
    """Yield markdown image nodes in source order."""
    source = markdown or ""
    for match in _MARKDOWN_IMAGE_RE.finditer(source):
        width, height = parse_image_attrs(match.group("attrs") or "")
        yield MarkdownImage(
            alt=match.group("alt") or "",
            url=match.group("url") or "",
            width=width,
            height=height,
            start=match.start(),
            end=match.end(),
        )


def split_markdown_segments(markdown: str) -> list[MarkdownSegment]:
    """Split markdown into stable blocks and standalone image segments."""
    source = markdown or ""
    if not source:
        return []

    segments: list[MarkdownSegment] = []
    markdown_lines: list[str] = []
    in_code_fence = False

    def flush_markdown() -> None:
        if not markdown_lines:
            return
        segments.append(MarkdownSegment(kind="markdown", text="".join(markdown_lines)))
        markdown_lines.clear()

    for line in source.splitlines(keepends=True):
        stripped_line = line.strip()
        if stripped_line.startswith("```"):
            markdown_lines.append(line)
            in_code_fence = not in_code_fence
            continue

        if in_code_fence:
            markdown_lines.append(line)
            continue

        image_match = _STANDALONE_IMAGE_LINE_RE.fullmatch(stripped_line)
        if image_match:
            flush_markdown()
            width, height = parse_image_attrs(image_match.group("attrs") or "")
            segments.append(
                MarkdownSegment(
                    kind="image",
                    image=MarkdownImage(
                        alt=image_match.group("alt") or "",
                        url=image_match.group("url") or "",
                        width=width,
                        height=height,
                    ),
                )
            )
            continue

        markdown_lines.append(line)

    flush_markdown()
    return segments


def _image_from_data_url(url: str) -> QImage:
    if not url.startswith("data:image/") or ";base64," not in url:
        return QImage()
    payload = url.split(";base64,", 1)[1]
    try:
        return QImage.fromData(base64.b64decode(payload))
    except Exception:
        return QImage()


def _image_from_local_url(url: str) -> QImage:
    qurl = QUrl(url)
    local_path = ""
    if qurl.isLocalFile():
        local_path = qurl.toLocalFile()
    elif "://" not in url:
        local_path = unquote(url)
    if not local_path:
        return QImage()
    path = Path(local_path)
    if not path.exists() or not path.is_file():
        return QImage()
    return QImage(str(path))


def load_markdown_image(url: str) -> QImage:
    """Load a markdown image from a data URL or local path."""
    if not url:
        return QImage()
    if url.startswith("data:image/"):
        return _image_from_data_url(url)
    return _image_from_local_url(url)


def compute_image_size(image: QImage, width: int, height: int, max_width: float) -> tuple[float, float]:
    """Resolve the rendered image size for the PDF document."""
    explicit_width = float(width or 0)
    explicit_height = float(height or 0)
    natural_width = float(image.width() or 0)
    natural_height = float(image.height() or 0)
    aspect_ratio = natural_width / natural_height if natural_width > 0 and natural_height > 0 else 1.0

    if explicit_width > 0 and explicit_height > 0:
        return explicit_width, explicit_height
    if explicit_width > 0:
        return explicit_width, max(1.0, explicit_width / max(aspect_ratio, 0.01))
    if explicit_height > 0:
        return max(1.0, explicit_height * max(aspect_ratio, 0.01)), explicit_height

    if natural_width <= 0 or natural_height <= 0:
        fallback_width = max(1.0, min(max_width, 320.0))
        return fallback_width, fallback_width / max(aspect_ratio, 0.01)

    if natural_width <= max_width:
        return natural_width, natural_height

    scaled_width = max_width
    scaled_height = natural_height * (scaled_width / natural_width)
    return scaled_width, scaled_height


def _pdf_page_size(writer: QPdfWriter) -> QSizeF:
    return QSizeF(float(writer.width()), float(writer.height()))


def _create_pdf_writer(output_path: str, title: str = "") -> QPdfWriter:
    writer = QPdfWriter(output_path)
    writer.setResolution(_PDF_RESOLUTION_DPI)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(
        QMarginsF(_PDF_MARGIN_POINTS, _PDF_MARGIN_POINTS, _PDF_MARGIN_POINTS, _PDF_MARGIN_POINTS),
        QPageLayout.Point,
    )
    if title:
        writer.setTitle(title)
    return writer


def _insert_markdown_fragment(cursor: QTextCursor, markdown: str) -> None:
    if not markdown:
        return
    cursor.insertFragment(QTextDocumentFragment.fromMarkdown(markdown))


def _insert_page_break(cursor: QTextCursor) -> None:
    block_format = QTextBlockFormat()
    block_format.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore)
    cursor.insertBlock(block_format)


def _insert_heading(cursor: QTextCursor, level: int, text: str) -> None:
    safe_text = html.escape((text or "").strip() or "Untitled")
    level = max(1, min(6, level))
    cursor.insertHtml(f"<h{level}>{safe_text}</h{level}>")
    cursor.insertBlock()


def _tab_anchor_name(index: int) -> str:
    return f"tab-{index + 1}"


def _insert_anchor_heading(cursor: QTextCursor, level: int, text: str, anchor_name: str) -> None:
    safe_text = html.escape((text or "").strip() or "Untitled")
    safe_anchor = html.escape(anchor_name or "")
    level = max(1, min(6, level))
    cursor.insertHtml(f"<h{level}><a name=\"{safe_anchor}\"></a>{safe_text}</h{level}>")
    cursor.insertBlock()


def _insert_fallback_alt(cursor: QTextCursor, alt: str) -> None:
    fallback = f"[Image: {alt}]" if alt else "[Image]"
    cursor.insertText(fallback)
    cursor.insertBlock()


def _insert_image_block(
    cursor: QTextCursor,
    document: QTextDocument,
    image_node: MarkdownImage,
    max_width: float,
    image_index: int,
) -> None:
    image = load_markdown_image(image_node.url)
    if image.isNull():
        _insert_fallback_alt(cursor, image_node.alt)
        return

    resource_name = QUrl(f"markdown-pdf-image://{id(document)}-{image_index}")
    document.addResource(QTextDocument.ImageResource, resource_name, image)
    render_width, render_height = compute_image_size(
        image,
        image_node.width,
        image_node.height,
        max_width=max_width,
    )
    image_format = QTextImageFormat()
    image_format.setName(resource_name.toString())
    image_format.setWidth(render_width)
    image_format.setHeight(render_height)
    if image_node.alt:
        image_format.setProperty(QTextFormat.ImageAltText, image_node.alt)
    cursor.insertImage(image_format)
    cursor.insertBlock()


def _insert_tab_index(cursor: QTextCursor, title: str, tabs: list[dict[str, str]]) -> None:
    safe_title = html.escape((title or "Markdown Export").strip() or "Markdown Export")
    cursor.insertHtml(
        f"<div style=\"text-align:center; margin-bottom:24px;\">"
        f"<h1 style=\"margin-bottom:6px;\">{safe_title}</h1>"
        f"<div style=\"color:#64748b; font-size:10pt;\">Exported tabs</div>"
        f"</div>"
    )
    cursor.insertHtml("<h2>Contents</h2>")
    list_items = "".join(
        f"<li><a href=\"#{_tab_anchor_name(index)}\">"
        f"{html.escape(str(tab.get('name') or f'Tab {index + 1}'))}"
        f"</a></li>"
        for index, tab in enumerate(tabs)
    )
    cursor.insertHtml(f"<ol>{list_items}</ol>")
    cursor.insertBlock()


def build_document_from_markdown(markdown: str, document: QTextDocument, cursor: QTextCursor, max_width: float) -> None:
    """Append markdown content with stable markdown/image segments."""
    image_index = 0
    for segment in split_markdown_segments(markdown):
        if segment.kind == "markdown":
            _insert_markdown_fragment(cursor, segment.text)
            continue
        if segment.kind == "image" and segment.image is not None:
            _insert_image_block(cursor, document, segment.image, max_width=max_width, image_index=image_index)
            image_index += 1


def build_pdf_document(
    title: str,
    tabs: list[dict[str, str]],
    image_paster: MarkdownImagePaster | None = None,
    page_size: QSizeF | None = None,
) -> QTextDocument:
    """Build a QTextDocument for PDF export."""
    image_paster = image_paster or MarkdownImagePaster()
    normalized_tabs = tabs or [{"name": "Tab 1", "text": ""}]

    document = QTextDocument()
    document.setDefaultFont(QFont("Trebuchet MS", 11))
    document.setDefaultStyleSheet(_DEFAULT_STYLESHEET)
    document.setDocumentMargin(24.0)
    document.setPageSize(page_size or _DEFAULT_PAGE_SIZE)
    document.setUseDesignMetrics(True)

    safe_title = (title or "").strip()
    if safe_title:
        document.setMetaInformation(QTextDocument.DocumentTitle, safe_title)

    content_width = max(1.0, document.pageSize().width() - (document.documentMargin() * 2.0))
    cursor = QTextCursor(document)

    _insert_tab_index(cursor, safe_title or "Markdown Export", normalized_tabs)

    for index, tab in enumerate(normalized_tabs):
        _insert_page_break(cursor)
        tab_name = str(tab.get("name") or f"Tab {index + 1}")
        tab_text = image_paster.expandMarkdownImages(str(tab.get("text") or ""))
        _insert_anchor_heading(cursor, 1, tab_name, _tab_anchor_name(index))
        build_document_from_markdown(tab_text, document, cursor, max_width=content_width)

    return document


def collect_document_layout_metrics(document: QTextDocument) -> PdfLayoutMetrics:
    """Collect stable layout metrics for regression tests."""
    return PdfLayoutMetrics(
        page_count=max(1, document.pageCount()),
        block_count=document.blockCount(),
        width=round(document.pageSize().width(), 3),
        height=round(document.pageSize().height(), 3),
        character_count=document.characterCount(),
    )


def write_document_to_pdf(document: QTextDocument, output_path: str, title: str = "") -> bool:
    """Write a QTextDocument to a PDF file."""
    if not output_path:
        return False

    writer = _create_pdf_writer(output_path, title=title)
    painter = QPainter(writer)
    if not painter.isActive():
        return False

    try:
        page_height = document.pageSize().height()
        page_width = document.pageSize().width()
        page_count = max(1, document.pageCount())
        layout = document.documentLayout()

        for page_index in range(page_count):
            if page_index > 0 and not writer.newPage():
                return False
            painter.save()
            painter.translate(0.0, -page_index * page_height)
            context = QAbstractTextDocumentLayout.PaintContext()
            context.clip = QRectF(0.0, page_index * page_height, page_width, page_height)
            layout.draw(painter, context)
            painter.restore()

        return True
    finally:
        painter.end()


def _normalize_tabs_argument(tabs) -> list[dict[str, str]]:
    if isinstance(tabs, QJSValue):
        tabs = tabs.toVariant()
    if not isinstance(tabs, list):
        return []
    normalized: list[dict[str, str]] = []
    for index, tab in enumerate(tabs):
        if isinstance(tab, QJSValue):
            tab = tab.toVariant()
        if not isinstance(tab, dict):
            continue
        normalized.append(
            {
                "name": str(tab.get("name") or f"Tab {index + 1}"),
                "text": str(tab.get("text") or ""),
            }
        )
    return normalized


def normalize_output_path(output_path: str) -> str:
    """Convert a QML/Qt URL-ish path into a local filesystem path."""
    if not output_path:
        return ""
    qurl = QUrl(output_path)
    if qurl.isLocalFile():
        return qurl.toLocalFile()
    if output_path.startswith("file://"):
        return QUrl(output_path).toLocalFile()
    return output_path


def export_tabs_to_pdf(
    title: str,
    tabs: list[dict[str, str]],
    output_path: str,
    image_paster: MarkdownImagePaster | None = None,
) -> bool:
    """Export markdown tabs to a document-style PDF."""
    local_path = normalize_output_path(output_path)
    if not local_path:
        return False

    writer = _create_pdf_writer(local_path, title=title)
    document = build_pdf_document(
        title,
        tabs,
        image_paster=image_paster,
        page_size=_pdf_page_size(writer),
    )
    return write_document_to_pdf(document, local_path, title=title)


class MarkdownPdfExporter(QObject):
    """QML-facing PDF exporter for markdown content."""

    def __init__(self, image_paster: MarkdownImagePaster | None = None) -> None:
        super().__init__()
        self._image_paster = image_paster or MarkdownImagePaster()

    @Slot(str, "QVariant", str, result=bool)
    def exportTabsToPdf(self, title: str, tabs, output_path: str) -> bool:  # noqa: N802
        normalized_tabs = _normalize_tabs_argument(tabs)
        return export_tabs_to_pdf(title, normalized_tabs, output_path, image_paster=self._image_paster)


__all__ = [
    "MarkdownImage",
    "MarkdownPdfExporter",
    "MarkdownSegment",
    "PdfLayoutMetrics",
    "build_document_from_markdown",
    "build_pdf_document",
    "collect_document_layout_metrics",
    "compute_image_size",
    "export_tabs_to_pdf",
    "iter_markdown_images",
    "load_markdown_image",
    "normalize_output_path",
    "parse_image_attrs",
    "split_markdown_segments",
    "write_document_to_pdf",
]
