"""Shared pytest fixtures for Qt application lifecycle."""

import os
import sys
from pathlib import Path

# Qt needs its platform/backend selected before PySide is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest
from PySide6.QtGui import QGuiApplication

# Ensure tests can import local packages/modules regardless of invocation cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def app():
    """Provide a single QGuiApplication for all tests."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication([])
    # Keep teardown empty: several CI PySide/Python combinations segfault if
    # we touch the application, clipboard, or event loop during fixture cleanup.
    return instance


@pytest.fixture
def actiondraw_window(app):
    """Destroy QML engines before releasing their Python context objects."""
    import shiboken6
    from actiondraw.ui import create_actiondraw_window

    windows = []

    def create(*args, **kwargs):
        engine = create_actiondraw_window(*args, **kwargs)
        # Retain the supplied models as well as the engine until teardown.
        windows.append((engine, args, kwargs))
        return engine

    yield create

    for engine, args, kwargs in reversed(windows):
        editor_engine = engine._markdown_note_manager._editor._engine
        if shiboken6.isValid(editor_engine):
            shiboken6.delete(editor_engine)
        if shiboken6.isValid(engine):
            shiboken6.delete(engine)
