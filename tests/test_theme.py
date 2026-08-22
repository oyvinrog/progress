"""Tests for ActionDraw's cross-platform Qt control palette."""

from PySide6.QtGui import QColor, QPalette

from actiondraw.theme import build_actiondraw_palette, configure_actiondraw_theme


def test_actiondraw_palette_keeps_enabled_and_disabled_buttons_visible():
    palette = build_actiondraw_palette()

    assert palette.color(QPalette.Active, QPalette.Button) == QColor("#2b4155")
    assert palette.color(QPalette.Active, QPalette.ButtonText) == QColor("#f8fafc")
    assert palette.color(QPalette.Disabled, QPalette.Button) == QColor("#1b2936")
    assert palette.color(QPalette.Disabled, QPalette.ButtonText) == QColor("#77899a")
    assert palette.color(QPalette.Active, QPalette.Button) != palette.color(
        QPalette.Active, QPalette.Window
    )


def test_configure_actiondraw_theme_installs_palette(app):
    configure_actiondraw_theme(app)

    palette = app.palette()
    assert palette.color(QPalette.Active, QPalette.Button) == QColor("#2b4155")
    assert palette.color(QPalette.Active, QPalette.ButtonText) == QColor("#f8fafc")
