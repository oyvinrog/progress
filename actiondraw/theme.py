"""Cross-platform Qt Quick Controls theme for ActionDraw."""

from __future__ import annotations

from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtQuickControls2 import QQuickStyle


def build_actiondraw_palette(base_palette: QPalette | None = None) -> QPalette:
    """Build the explicit dark palette used by every ActionDraw window."""
    palette = QPalette(base_palette) if base_palette is not None else QPalette()
    colors = {
        QPalette.Window: "#0b121a",
        QPalette.WindowText: "#e2e8f0",
        QPalette.Base: "#111826",
        QPalette.AlternateBase: "#182433",
        QPalette.ToolTipBase: "#243447",
        QPalette.ToolTipText: "#f8fafc",
        QPalette.Text: "#e2e8f0",
        QPalette.Button: "#2b4155",
        QPalette.ButtonText: "#f8fafc",
        QPalette.BrightText: "#ffffff",
        QPalette.Link: "#60a5fa",
        QPalette.Highlight: "#2d7ab3",
        QPalette.HighlightedText: "#ffffff",
        QPalette.PlaceholderText: "#8ca0b3",
    }
    for role, color in colors.items():
        palette.setColor(QPalette.Active, role, QColor(color))
        palette.setColor(QPalette.Inactive, role, QColor(color))

    disabled_colors = {
        QPalette.WindowText: "#77899a",
        QPalette.Text: "#77899a",
        QPalette.Button: "#1b2936",
        QPalette.ButtonText: "#77899a",
        QPalette.Highlight: "#31475a",
        QPalette.HighlightedText: "#9aabba",
        QPalette.PlaceholderText: "#647687",
    }
    for role, color in disabled_colors.items():
        palette.setColor(QPalette.Disabled, role, QColor(color))
    return palette


def configure_actiondraw_theme(app: QGuiApplication | None = None) -> None:
    """Select a deterministic Controls style and install ActionDraw's palette."""
    if QQuickStyle.name() != "Fusion":
        QQuickStyle.setStyle("Fusion")
    application = app or QGuiApplication.instance()
    if application is not None:
        application.setPalette(build_actiondraw_palette(application.palette()))
