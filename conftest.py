"""Shared pytest fixtures for Qt application lifecycle."""

import sys

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication


@pytest.fixture(scope="session")
def app():
    """Provide a single QGuiApplication for all tests."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)

    yield instance

    # Avoid PySide shutdown crashes when clipboard owns QMimeData.
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()

    QCoreApplication.processEvents()
