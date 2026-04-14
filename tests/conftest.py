"""Shared pytest fixtures for Qt application lifecycle."""

import os
import sys
from pathlib import Path

import pytest

# Ensure tests can import local packages/modules regardless of invocation cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def app():
    """Provide a single QGuiApplication for all tests."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)

    yield instance

    # Avoid PySide shutdown crashes when clipboard owns QMimeData.
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()

    QCoreApplication.processEvents()
