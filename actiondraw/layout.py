"""Layout algorithms mixin for DiagramModel.

This module provides item arrangement/layout functionality.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, TYPE_CHECKING

from PySide6.QtCore import Slot

from .types import DiagramEdge, DiagramItem

if TYPE_CHECKING:
    from .model import DiagramModel


class LayoutMixin:
    """Mixin providing layout/arrangement operations."""

    # Attributes expected from DiagramModel
    _items: List[DiagramItem]
    _edges: List[DiagramEdge]
    moveItem: Callable[[str, float, float], None]

    @Slot(str)
    def arrangeItems(self, layout_type: str) -> None:
        """Arrange diagram items using the specified layout algorithm.

        Args:
            layout_type: One of 'grid', 'horizontal', 'vertical', 'hierarchical'
        """
        if not self._items:
            return

        padding = 40.0  # Space between items
        start_x = 60.0
        start_y = 60.0

        if layout_type == "grid":
            self._arrange_grid(start_x, start_y, padding)
        elif layout_type == "horizontal":
            self._arrange_flow(start_x, start_y, padding, horizontal=True)
        elif layout_type == "vertical":
            self._arrange_flow(start_x, start_y, padding, horizontal=False)
        elif layout_type == "hierarchical":
            self._arrange_hierarchical(start_x, start_y, padding)

    def _arrange_grid(self, start_x: float, start_y: float, padding: float) -> None:
        """Arrange items in a grid pattern."""
        n = len(self._items)
        cols = max(1, int(math.ceil(math.sqrt(n))))

        # Sort items by their current position to maintain some order
        sorted_items = sorted(self._items, key=lambda item: (item.y, item.x))

        # Find the max dimensions for uniform grid cells
        max_width = max(item.width for item in self._items)
        max_height = max(item.height for item in self._items)
        cell_width = max_width + padding
        cell_height = max_height + padding

        for idx, item in enumerate(sorted_items):
            row = idx // cols
            col = idx % cols
            new_x = start_x + col * cell_width
            new_y = start_y + row * cell_height
            self.moveItem(item.id, new_x, new_y)

    def _arrange_flow(self, start_x: float, start_y: float, padding: float, horizontal: bool) -> None:
        """Arrange items in a single row or column."""
        # Sort by current position in the flow direction
        if horizontal:
            sorted_items = sorted(self._items, key=lambda item: (item.x, item.y))
        else:
            sorted_items = sorted(self._items, key=lambda item: (item.y, item.x))

        current_pos = start_x if horizontal else start_y

        for item in sorted_items:
            if horizontal:
                self.moveItem(item.id, current_pos, start_y)
                current_pos += item.width + padding
            else:
                self.moveItem(item.id, start_x, current_pos)
                current_pos += item.height + padding

    def _arrange_hierarchical(self, start_x: float, start_y: float, padding: float) -> None:
        """Arrange items in layers based on edge connections (DAG layout).

        Connected components are kept together and arranged side by side.
        """
        if not self._items:
            return

        item_by_id = {item.id: item for item in self._items}
        item_ids = set(item_by_id.keys())

        # Build adjacency info (directed)
        outgoing: Dict[str, List[str]] = {item.id: [] for item in self._items}
        incoming: Dict[str, List[str]] = {item.id: [] for item in self._items}
        # Also build undirected adjacency for finding connected components
        neighbors: Dict[str, set] = {item.id: set() for item in self._items}

        for edge in self._edges:
            if edge.from_id in item_ids and edge.to_id in item_ids:
                outgoing[edge.from_id].append(edge.to_id)
                incoming[edge.to_id].append(edge.from_id)
                neighbors[edge.from_id].add(edge.to_id)
                neighbors[edge.to_id].add(edge.from_id)

        # Find connected components using DFS
        visited: set = set()
        components: List[List[str]] = []

        def find_component(start_id: str) -> List[str]:
            component = []
            stack = [start_id]
            while stack:
                item_id = stack.pop()
                if item_id in visited:
                    continue
                visited.add(item_id)
                component.append(item_id)
                for neighbor_id in neighbors[item_id]:
                    if neighbor_id not in visited:
                        stack.append(neighbor_id)
            return component

        # Find all connected components, processing items in position order
        for item in sorted(self._items, key=lambda i: (i.y, i.x)):
            if item.id not in visited:
                component = find_component(item.id)
                if component:
                    components.append(component)

        # Arrange each connected component and track positions
        component_gap = padding * 2  # Extra gap between components
        current_x_offset = start_x

        for component_ids in components:
            component_items = [item_by_id[item_id] for item_id in component_ids]

            # Assign layers within this component
            layers: Dict[str, int] = {}
            layer_visited: set = set()

            def assign_layer(item_id: str, layer: int) -> None:
                if item_id in layer_visited:
                    layers[item_id] = max(layers.get(item_id, 0), layer)
                    return
                layer_visited.add(item_id)
                layers[item_id] = max(layers.get(item_id, 0), layer)
                for child_id in outgoing[item_id]:
                    if child_id in component_ids:
                        assign_layer(child_id, layer + 1)

            # Start from items with no incoming edges within this component
            component_set = set(component_ids)
            roots = [item_id for item_id in component_ids
                     if not any(inc in component_set for inc in incoming[item_id])]

            if not roots:
                # No clear roots (cycle), use topmost item
                roots = [min(component_ids, key=lambda id: (item_by_id[id].y, item_by_id[id].x))]

            for root_id in roots:
                assign_layer(root_id, 0)

            # Handle any items not reached (shouldn't happen but just in case)
            for item_id in component_ids:
                if item_id not in layers:
                    layers[item_id] = 0

            # Group items by layer within this component
            layer_items: Dict[int, List[DiagramItem]] = {}
            for item_id in component_ids:
                layer = layers[item_id]
                if layer not in layer_items:
                    layer_items[layer] = []
                layer_items[layer].append(item_by_id[item_id])

            # Sort items within each layer by original x position
            for layer in layer_items:
                layer_items[layer].sort(key=lambda item: item.x)

            # Calculate component dimensions and position items
            max_height = max(item.height for item in component_items)
            layer_spacing = max_height + padding * 2

            # Find the widest layer to determine component width
            max_layer_width = 0.0
            for layer_num in layer_items:
                items_in_layer = layer_items[layer_num]
                layer_width = sum(item.width for item in items_in_layer) + padding * (len(items_in_layer) - 1)
                max_layer_width = max(max_layer_width, layer_width)

            # Position items in this component
            current_y = start_y
            for layer_num in sorted(layer_items.keys()):
                items_in_layer = layer_items[layer_num]
                current_x = current_x_offset

                for item in items_in_layer:
                    self.moveItem(item.id, current_x, current_y)
                    current_x += item.width + padding

                current_y += layer_spacing

            # Move to next component position
            current_x_offset += max_layer_width + component_gap
