"""Tests for shared clipboard outline parsing."""

from types import SimpleNamespace
import xml.etree.ElementTree as ET

from actiondraw.outline_clipboard import (
    outline_to_indented_text,
    outline_to_opml,
    parse_opml_text,
    parse_text_hierarchy,
)


def test_parse_opml_nested_multiple_roots_and_title_fallback():
    entries = parse_opml_text(
        '<?xml version="1.0"?><opml version="2.0"><body>'
        '<outline text="First"><outline title="Child"/></outline>'
        '<outline>Second</outline>'
        '</body></opml>'
    )

    assert entries == [
        {"text": "First", "level": 0},
        {"text": "Child", "level": 1},
        {"text": "Second", "level": 0},
    ]


def test_parse_opml_handles_namespaces_and_empty_wrapper_outlines():
    entries = parse_opml_text(
        '<opml xmlns="urn:opml"><body><outline>'
        '<outline text="Lifted"><outline text="Nested"/></outline>'
        '</outline></body></opml>'
    )

    assert entries == [
        {"text": "Lifted", "level": 0},
        {"text": "Nested", "level": 1},
    ]


def test_parse_opml_rejects_malformed_and_non_opml_xml():
    assert parse_opml_text("<opml><body><outline text='Broken'></body>") is None
    assert parse_opml_text("<root><outline text='Not OPML'/></root>") is None


def test_parse_text_hierarchy_handles_single_lines_tabs_and_blanks():
    assert parse_text_hierarchy("A single thought") == [
        {"text": "A single thought", "level": 0}
    ]
    assert parse_text_hierarchy("Parent\n\n\tChild\nSibling") == [
        {"text": "Parent", "level": 0},
        {"text": "Child", "level": 1},
        {"text": "Sibling", "level": 0},
    ]


def test_outline_serializers_preserve_hierarchy_unicode_and_special_characters():
    leaf = SimpleNamespace(text="", children=[])
    child = SimpleNamespace(text="Barn & bøker <senere>", children=[leaf])
    root = SimpleNamespace(text='Plan "høst"', children=[child])

    opml_text = outline_to_opml(root, root.text)
    document = ET.fromstring(opml_text)
    assert document.get("version") == "2.0"
    assert document.findtext("head/title") == 'Plan "høst"'
    outlines = document.findall(".//outline")
    assert [outline.get("text") for outline in outlines] == [
        'Plan "høst"',
        "Barn & bøker <senere>",
        "",
    ]
    assert "&amp;" in opml_text and "&lt;senere&gt;" in opml_text
    assert outline_to_indented_text(root) == (
        'Plan "høst"\n  Barn & bøker <senere>\n    '
    )
