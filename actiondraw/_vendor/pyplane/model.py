"""Qt-independent mind-map object model."""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .errors import InvalidMapError

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

Side = Literal["left", "right"]


def _new_id() -> str:
    return f"ID_{uuid.uuid4().hex}"


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(slots=True)
class NodeStyle:
    """The deliberately small subset of node presentation supported by PyPlane."""

    color: str | None = None
    background_color: str | None = None
    bold: bool | None = None
    italic: bool | None = None
    font_size: float | None = None
    shape: str | None = None
    edge_color: str | None = None
    edge_width: float | None = None
    edge_style: str | None = None


@dataclass(eq=False, slots=True)
class Node:
    """A node in a :class:`MindMap` tree."""

    text: str = ""
    id: str = field(default_factory=_new_id)
    folded: bool = False
    side: Side | None = None
    link: str | None = None
    note: str | None = None
    style: NodeStyle = field(default_factory=NodeStyle)
    created: int = field(default_factory=_now_ms)
    modified: int = field(default_factory=_now_ms)
    children: list[Node] = field(default_factory=list)
    parent: Node | None = field(default=None, init=False, repr=False)
    _xml: Element | None = field(default=None, init=False, repr=False)
    _original_note: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.side not in (None, "left", "right"):
            raise InvalidMapError(f"invalid node side: {self.side!r}")
        initial = list(self.children)
        self.children.clear()
        for child in initial:
            self._adopt(child)

    def _adopt(self, child: Node, index: int | None = None) -> None:
        if child is self or any(ancestor is child for ancestor in self.ancestors()):
            raise InvalidMapError("a node cannot contain itself or one of its ancestors")
        if child.parent is not None:
            child.parent.children.remove(child)
        child.parent = self
        if index is None:
            self.children.append(child)
        else:
            if index < 0 or index > len(self.children):
                raise IndexError("child index out of range")
            self.children.insert(index, child)
        child.touch()

    def add_child(
        self,
        text: str = "",
        *,
        side: Side | None = None,
        note: str | None = None,
        link: str | None = None,
        style: NodeStyle | None = None,
    ) -> Node:
        """Create, append, and return a child node."""
        child = Node(text=text, side=side, note=note, link=link, style=style or NodeStyle())
        self._adopt(child)
        return child

    def remove(self) -> None:
        """Remove this node and its subtree from its parent."""
        if self.parent is None:
            raise InvalidMapError("the root node cannot be removed")
        parent = self.parent
        parent.children.remove(self)
        self.parent = None
        parent.touch()

    def move_to(self, parent: Node, index: int | None = None) -> None:
        """Move this subtree beneath *parent*."""
        if self.parent is None:
            raise InvalidMapError("the root node cannot be moved")
        if parent is self or any(item is self for item in parent.ancestors()):
            raise InvalidMapError("moving the node there would create a cycle")
        parent._adopt(self, index)

    def walk(self) -> Iterator[Node]:
        """Yield this node and all descendants in display order."""
        yield self
        for child in self.children:
            yield from child.walk()

    def ancestors(self) -> Iterator[Node]:
        current = self.parent
        while current is not None:
            yield current
            current = current.parent

    def touch(self) -> None:
        self.modified = _now_ms()

    def regenerate_ids(self) -> None:
        """Assign fresh IDs to this node and every descendant."""
        for node in self.walk():
            node.id = _new_id()
            node.touch()


class MindMap:
    """A complete mind map with a single root node."""

    def __init__(self, root: str | Node = "New Mind Map") -> None:
        self.root = root if isinstance(root, Node) else Node(str(root))
        if self.root.parent is not None:
            raise InvalidMapError("the map root cannot have a parent")
        self._xml: Element | None = None
        self._source_path: Path | None = None
        self.validate()

    @classmethod
    def load(cls, path: str | Path) -> MindMap:
        from .mm import load

        return load(path)

    def save(self, path: str | Path | None = None) -> None:
        from .mm import save

        destination = Path(path) if path is not None else self._source_path
        if destination is None:
            raise ValueError("save() requires a path for a new map")
        save(self, destination)
        self._source_path = destination

    def walk(self) -> Iterator[Node]:
        return self.root.walk()

    def find(self, node_id: str) -> Node | None:
        return next((node for node in self.walk() if node.id == node_id), None)

    def validate(self) -> None:
        seen_nodes: set[int] = set()
        seen_ids: set[str] = set()
        stack: list[tuple[Node, Node | None]] = [(self.root, None)]
        while stack:
            node, expected_parent = stack.pop()
            if id(node) in seen_nodes:
                raise InvalidMapError("the map contains a cycle or repeated node")
            if not node.id or node.id in seen_ids:
                raise InvalidMapError(f"duplicate or empty node ID: {node.id!r}")
            if node.parent is not expected_parent:
                raise InvalidMapError(f"incorrect parent reference on node {node.id}")
            seen_nodes.add(id(node))
            seen_ids.add(node.id)
            stack.extend((child, node) for child in reversed(node.children))
