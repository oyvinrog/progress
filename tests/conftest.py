"""Shared pytest fixtures for Qt application lifecycle."""

import os
import sys
from pathlib import Path

# Qt needs its platform/backend selected before PySide is imported.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

import pytest
from PySide6.QtCore import QCoreApplication
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

    yield instance

    # Release clipboard-owned Qt objects before interpreter shutdown.
    # Avoid explicitly quitting the app here: some PySide/Python combinations
    # crash when QObject-backed models/timers are still unwinding.
    try:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.clear()
        QCoreApplication.processEvents()
    except RuntimeError:
        # PySide can already be tearing down during interpreter shutdown.
        pass
