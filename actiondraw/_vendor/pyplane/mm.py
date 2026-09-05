"""Freeplane ``.mm`` XML reader and writer."""

from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import IO, cast

from .errors import MMFormatError
from .model import MindMap, Node, NodeStyle, Side

MAX_DEPTH = 1_000
_DOCTYPE = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() == "true"


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.match(r"^\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", value)
    return float(match.group(1)) if match else None


def _plain_note(element: ET.Element) -> str:
    text = "".join(element.itertext())
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _parse_node(element: ET.Element, depth: int = 0) -> Node:
    if depth > MAX_DEPTH:
        raise MMFormatError(f"map nesting exceeds the limit of {MAX_DEPTH}")
    position = element.get("POSITION")
    side: Side | None
    if position == "left":
        side = "left"
    elif position in {"right", "bottom_or_right", "top_or_left"}:
        side = "right"
    else:
        side = None
    font = element.find("font")
    edge = element.find("edge")
    style = NodeStyle(
        color=element.get("COLOR"),
        background_color=element.get("BACKGROUND_COLOR"),
        bold=_bool(font.get("BOLD")) if font is not None else None,
        italic=_bool(font.get("ITALIC")) if font is not None else None,
        font_size=_number(font.get("SIZE")) if font is not None else None,
        shape=element.get("STYLE"),
        edge_color=edge.get("COLOR") if edge is not None else None,
        edge_width=_number(edge.get("WIDTH")) if edge is not None else None,
        edge_style=edge.get("STYLE") if edge is not None else None,
    )
    note_element = next(
        (item for item in element.findall("richcontent") if item.get("TYPE") == "NOTE"), None
    )
    note = _plain_note(note_element) if note_element is not None else None
    try:
        created = int(element.get("CREATED", "0"))
        modified = int(element.get("MODIFIED", "0"))
    except ValueError as exc:
        raise MMFormatError("node timestamps must be integers") from exc
    node = Node(
        text=element.get("TEXT", ""),
        id=element.get("ID", ""),
        folded=element.get("FOLDED", "false").lower() == "true",
        side=side,
        link=element.get("LINK"),
        note=note,
        style=style,
        created=created,
        modified=modified,
    )
    node._xml = deepcopy(element)
    node._original_note = note
    for child_element in element.findall("node"):
        child = _parse_node(child_element, depth + 1)
        child.parent = node
        node.children.append(child)
    return node


def loads(data: bytes | str) -> MindMap:
    """Decode a Freeplane XML document from bytes or text."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if _DOCTYPE.search(raw):
        raise MMFormatError("DTD and entity declarations are not allowed")
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        document = ET.fromstring(raw, parser=parser)
    except (ET.ParseError, ValueError) as exc:
        raise MMFormatError(f"invalid .mm XML: {exc}") from exc
    if document.tag != "map":
        raise MMFormatError("expected a <map> document root")
    roots = document.findall("node")
    if len(roots) != 1:
        raise MMFormatError("a map must contain exactly one root <node>")
    try:
        mindmap = MindMap(_parse_node(roots[0]))
    except (ValueError, RecursionError) as exc:
        raise MMFormatError(f"invalid map structure: {exc}") from exc
    mindmap._xml = deepcopy(document)
    mindmap.validate()
    return mindmap


def load(path: str | Path) -> MindMap:
    """Load a Freeplane map from *path*."""
    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise MMFormatError(f"could not read {source}: {exc}") from exc
    mindmap = loads(data)
    mindmap._source_path = source
    return mindmap


def _set_or_remove(element: ET.Element, key: str, value: object | None) -> None:
    if value is None:
        element.attrib.pop(key, None)
    else:
        element.set(key, str(value))


def _child(element: ET.Element, tag: str) -> ET.Element:
    existing = element.find(tag)
    if existing is not None:
        return existing
    child = ET.Element(tag)
    first_node = next((i for i, item in enumerate(element) if item.tag == "node"), len(element))
    element.insert(first_node, child)
    return child


def _sync_note(element: ET.Element, node: Node) -> None:
    notes = [item for item in element.findall("richcontent") if item.get("TYPE") == "NOTE"]
    if node.note == node._original_note:
        return
    for item in notes:
        element.remove(item)
    if node.note is None:
        return
    rich = ET.Element("richcontent", {"TYPE": "NOTE"})
    body = ET.SubElement(ET.SubElement(ET.SubElement(rich, "html"), "body"), "p")
    body.text = node.note
    first_node = next((i for i, item in enumerate(element) if item.tag == "node"), len(element))
    element.insert(first_node, rich)


def _build_node(node: Node, *, is_root: bool = False, is_root_child: bool = False) -> ET.Element:
    element = deepcopy(node._xml) if node._xml is not None else ET.Element("node")
    _set_or_remove(element, "TEXT", node.text)
    _set_or_remove(element, "ID", node.id)
    _set_or_remove(element, "CREATED", node.created)
    _set_or_remove(element, "MODIFIED", node.modified)
    _set_or_remove(element, "FOLDED", "true" if node.folded else None)
    _set_or_remove(element, "LINK", node.link)
    # Nested branches can be roots of a tab-scoped editor view.
    position = node.side if not is_root else None
    _set_or_remove(element, "POSITION", position)
    _set_or_remove(element, "COLOR", node.style.color)
    _set_or_remove(element, "BACKGROUND_COLOR", node.style.background_color)
    _set_or_remove(element, "STYLE", node.style.shape)

    has_font = any(
        value is not None for value in (node.style.bold, node.style.italic, node.style.font_size)
    )
    font = element.find("font")
    if has_font:
        font = _child(element, "font")
        bold = str(node.style.bold).lower() if node.style.bold is not None else None
        italic = str(node.style.italic).lower() if node.style.italic is not None else None
        _set_or_remove(font, "BOLD", bold)
        _set_or_remove(font, "ITALIC", italic)
        _set_or_remove(font, "SIZE", node.style.font_size)
    elif font is not None and not font.attrib and len(font) == 0:
        element.remove(font)

    has_edge = any(
        value is not None
        for value in (node.style.edge_color, node.style.edge_width, node.style.edge_style)
    )
    edge = element.find("edge")
    if has_edge:
        edge = _child(element, "edge")
        _set_or_remove(edge, "COLOR", node.style.edge_color)
        _set_or_remove(edge, "WIDTH", node.style.edge_width)
        _set_or_remove(edge, "STYLE", node.style.edge_style)
    elif edge is not None and not edge.attrib and len(edge) == 0:
        element.remove(edge)

    _sync_note(element, node)
    for old_child in list(element):
        if old_child.tag == "node":
            element.remove(old_child)
    element.extend(_build_node(child, is_root_child=is_root) for child in node.children)
    return element


def dumps(mindmap: MindMap) -> bytes:
    """Encode *mindmap* as a Freeplane-compatible XML document."""
    mindmap.validate()
    document = deepcopy(mindmap._xml) if mindmap._xml is not None else ET.Element("map")
    document.set("version", document.get("version", "freeplane 1.12.1"))
    root_element = _build_node(mindmap.root, is_root=True)
    old_roots = [item for item in list(document) if item.tag == "node"]
    insertion = list(document).index(old_roots[0]) if old_roots else len(document)
    for old_root in old_roots:
        document.remove(old_root)
    document.insert(insertion, root_element)
    try:
        ET.indent(document, space="  ")
    except AttributeError:  # pragma: no cover - Python 3.10+ always has this
        pass
    encoded = ET.tostring(
        document, encoding="utf-8", xml_declaration=True, short_empty_elements=True
    )
    return cast(bytes, encoded)


def dumps_node(node: Node) -> bytes:
    """Encode one node subtree for clipboard or interchange use."""
    is_root_child = node.parent is not None and node.parent.parent is None
    encoded = ET.tostring(
        _build_node(node, is_root_child=is_root_child),
        encoding="utf-8",
        short_empty_elements=True,
    )
    return cast(bytes, encoded)


def loads_node(data: bytes | str) -> Node:
    """Decode one ``<node>`` subtree."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if _DOCTYPE.search(raw):
        raise MMFormatError("DTD and entity declarations are not allowed")
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        element = ET.fromstring(raw, parser=parser)
    except (ET.ParseError, ValueError) as exc:
        raise MMFormatError(f"invalid node XML: {exc}") from exc
    if element.tag != "node":
        raise MMFormatError("expected a <node> root")
    try:
        node = _parse_node(element)
        MindMap(node).validate()
    except (ValueError, RecursionError) as exc:
        raise MMFormatError(f"invalid node structure: {exc}") from exc
    return node


def save(mindmap: MindMap, path: str | Path) -> None:
    """Atomically save *mindmap* to *path*."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = dumps(mindmap)
    temporary: IO[bytes] | None = None
    temporary_name: str | None = None
    try:
        temporary = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        )
        temporary_name = temporary.name
        temporary.write(data)
        temporary.flush()
        temporary.close()
        Path(temporary_name).replace(destination)
    except OSError:
        if temporary is not None and not temporary.closed:
            temporary.close()
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
        raise
    mindmap._source_path = destination
