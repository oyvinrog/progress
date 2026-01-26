"""ActionDraw diagramming module - redirect to actiondraw package.

This file maintains backward compatibility for imports.
The actual implementation is now in the actiondraw/ package.
"""

# Re-export everything from the package for backward compatibility
from actiondraw import (
    ACTIONDRAW_QML,
    CLIPBOARD_MIME_TYPE,
    DiagramEdge,
    DiagramItem,
    DiagramItemType,
    DiagramModel,
    DrawingPoint,
    DrawingStroke,
    ITEM_PRESETS,
    create_actiondraw_window,
    main,
)

__all__ = [
    "ACTIONDRAW_QML",
    "CLIPBOARD_MIME_TYPE",
    "DiagramEdge",
    "DiagramItem",
    "DiagramItemType",
    "DiagramModel",
    "DrawingPoint",
    "DrawingStroke",
    "ITEM_PRESETS",
    "create_actiondraw_window",
    "main",
]

if __name__ == "__main__":
    import sys
    sys.exit(main())
