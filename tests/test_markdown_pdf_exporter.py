"""Tests for markdown PDF export."""

from __future__ import annotations

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QColor, QImage

from actiondraw.markdown_image_paster import MarkdownImagePaster, markdown_image_from_qimage
from actiondraw.markdown_pdf_exporter import (
    MarkdownPdfExporter,
    build_pdf_document,
    collect_document_layout_metrics,
    compute_image_size,
    export_tabs_to_pdf,
    parse_image_attrs,
    split_markdown_segments,
)


def _make_image(width: int, height: int, color: str = "#336699") -> QImage:
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor(color))
    return image


def _image_formats(document):
    formats = []
    for fmt in document.allFormats():
        if fmt.isImageFormat():
            formats.append(fmt.toImageFormat())
    return formats


def test_parse_image_attrs_extracts_dimensions():
    assert parse_image_attrs("{width=320 height=240}") == (320, 240)
    assert parse_image_attrs("{height=180 width=220}") == (220, 180)
    assert parse_image_attrs("{alt=ignored}") == (0, 0)


def test_compute_image_size_scales_natural_size_to_fit_page():
    image = _make_image(1000, 500)

    width, height = compute_image_size(image, width=0, height=0, max_width=400.0)

    assert width == 400.0
    assert height == 200.0


def test_split_markdown_segments_preserves_code_fences_and_standalone_images():
    image_markdown = "![diagram](data:image/png;base64,Zm9v){width=200 height=100}"
    markdown = "# Title\n\n```python\nprint('x')\n```\n\n" + image_markdown + "\nAfter\n"

    segments = split_markdown_segments(markdown)

    assert [segment.kind for segment in segments] == ["markdown", "image", "markdown", "markdown"]
    assert "```python" in segments[0].text
    assert segments[1].image is not None
    assert segments[1].image.width == 200
    assert segments[1].image.height == 100
    assert segments[2].text == "\n"
    assert segments[3].text == "After\n"


def test_build_pdf_document_expands_tokens_and_preserves_explicit_image_size():
    image = _make_image(8, 6, "#ff8800")
    paster = MarkdownImagePaster()
    expanded = markdown_image_from_qimage(image, "diagram")
    compact = paster.compactMarkdownImages(f"{expanded}{{width=320 height=240}}")

    document = build_pdf_document(
        "Exported Note",
        [{"name": "Tab 1", "text": compact}],
        image_paster=paster,
        page_size=QSizeF(640.0, 900.0),
    )

    image_formats = _image_formats(document)
    plain_text = document.toPlainText()

    assert len(image_formats) == 1
    assert image_formats[0].width() == 320.0
    assert image_formats[0].height() == 240.0
    assert "Tabs" in plain_text
    assert "Tab 1" in plain_text


def test_build_pdf_document_adds_index_before_tab_content():
    document = build_pdf_document(
        "Multi Tab",
        [
            {"name": "Overview", "text": "# Intro\nFirst tab"},
            {"name": "Details", "text": "Second tab body"},
        ],
        page_size=QSizeF(640.0, 900.0),
    )

    plain_text = document.toPlainText()
    assert "Multi Tab" in plain_text
    assert "Tabs" in plain_text
    assert plain_text.index("Tabs") < plain_text.index("Overview")
    assert plain_text.index("Overview") < plain_text.index("Details")


def test_repeated_builds_have_identical_layout_metrics(app):
    image = _make_image(16, 12, "#44aa55")
    markdown = (
        "# Title\n\n"
        "- one\n"
        "- two\n\n"
        "```python\nprint('hi')\n```\n\n"
        + markdown_image_from_qimage(image, "chart")
        + "{width=160 height=120}\n"
        "After image\n"
    )
    tabs = [{"name": "Tab 1", "text": markdown}, {"name": "Tab 2", "text": "More text"}]

    document_a = build_pdf_document("Stable Export", tabs, page_size=QSizeF(640.0, 900.0))
    document_b = build_pdf_document("Stable Export", tabs, page_size=QSizeF(640.0, 900.0))

    assert collect_document_layout_metrics(document_a) == collect_document_layout_metrics(document_b)


def test_export_tabs_to_pdf_writes_non_empty_pdf_twice(app, tmp_path):
    image = _make_image(16, 12, "#44aa55")
    image_markdown = markdown_image_from_qimage(image, "chart") + "{width=160 height=120}"
    tabs = [{"name": "Tab 1", "text": f"# Title\n\n{image_markdown}\nAfter image\n"}]
    output_one = tmp_path / "note-one.pdf"
    output_two = tmp_path / "note-two.pdf"

    exported_one = export_tabs_to_pdf("Export Test", tabs, str(output_one))
    exported_two = export_tabs_to_pdf("Export Test", tabs, str(output_two))

    assert exported_one is True
    assert exported_two is True
    assert output_one.exists()
    assert output_two.exists()
    assert output_one.stat().st_size > 0
    assert output_two.stat().st_size > 0


def test_qml_exporter_slot_accepts_python_list(app, tmp_path):
    output_path = tmp_path / "slot.pdf"
    exporter = MarkdownPdfExporter()

    exported = exporter.exportTabsToPdf(
        "Slot Export",
        [{"name": "Tab 1", "text": "Simple body"}],
        str(output_path),
    )

    assert exported is True
    assert output_path.exists()
    assert output_path.stat().st_size > 0
