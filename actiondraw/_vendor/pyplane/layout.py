"""Deterministic, toolkit-neutral tree layout."""

from __future__ import annotations

from dataclasses import dataclass

from .model import MindMap, Node, Side


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


def assigned_sides(mindmap: MindMap) -> dict[Node, Side]:
    """Resolve unspecified root branches by balancing visible subtree sizes."""
    result: dict[Node, Side] = {}
    weights: dict[Side, int] = {"left": 0, "right": 0}
    for branch in mindmap.root.children:
        weight = sum(1 for _ in branch.walk())
        side = branch.side or ("right" if weights["right"] <= weights["left"] else "left")
        weights[side] += weight
        for node in branch.walk():
            result[node] = side
    return result


def layout(
    mindmap: MindMap,
    sizes: dict[Node, tuple[float, float]] | None = None,
    *,
    horizontal_gap: float = 90.0,
    vertical_gap: float = 18.0,
) -> dict[Node, Box]:
    """Lay out visible nodes around the root without overlapping siblings."""
    sizes = sizes or {}
    sides = assigned_sides(mindmap)
    subtree_height: dict[Node, float] = {}

    def size(node: Node) -> tuple[float, float]:
        return sizes.get(node, (max(80.0, min(260.0, len(node.text) * 7.5 + 28.0)), 34.0))

    def measure(node: Node) -> float:
        own_height = size(node)[1]
        if node.folded or not node.children:
            subtree_height[node] = own_height
        else:
            child_height = sum(measure(child) for child in node.children)
            child_height += vertical_gap * (len(node.children) - 1)
            subtree_height[node] = max(own_height, child_height)
        return subtree_height[node]

    for child in mindmap.root.children:
        measure(child)

    result: dict[Node, Box] = {}
    root_width, root_height = size(mindmap.root)
    result[mindmap.root] = Box(-root_width / 2, -root_height / 2, root_width, root_height)

    def place(node: Node, side: Side, parent_box: Box, top: float) -> None:
        width, height = size(node)
        center_y = top + subtree_height[node] / 2
        if side == "right":
            x = parent_box.x + parent_box.width + horizontal_gap
        else:
            x = parent_box.x - horizontal_gap - width
        node_box = Box(x, center_y - height / 2, width, height)
        result[node] = node_box
        if node.folded:
            return
        children_height = sum(subtree_height[child] for child in node.children)
        children_height += vertical_gap * max(0, len(node.children) - 1)
        child_top = top + (subtree_height[node] - children_height) / 2
        for child in node.children:
            place(child, side, node_box, child_top)
            child_top += subtree_height[child] + vertical_gap

    for side in ("left", "right"):
        branches = [child for child in mindmap.root.children if sides[child] == side]
        total = sum(subtree_height[node] for node in branches)
        total += vertical_gap * max(0, len(branches) - 1)
        top = -total / 2
        for branch in branches:
            place(branch, side, result[mindmap.root], top)
            top += subtree_height[branch] + vertical_gap
    return result
