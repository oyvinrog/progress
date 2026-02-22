"""Standalone launcher for the priority plot window."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from actiondraw.qml import QML_DIR
from task_model import Tab, TabModel


PRIORITY_PLOT_QML_PATH = QML_DIR / "PriorityPlotWindow.qml"


def _build_demo_tab_model() -> TabModel:
    tab_model = TabModel()
    demo_tabs = [
        Tab(
            name="Take the bus",
            tasks={"tasks": []},
            diagram={"items": [], "edges": [], "strokes": []},
            priority_time_hours=1.5,
            priority_subjective_value=3.0,
        ),
        Tab(
            name="Write report",
            tasks={"tasks": []},
            diagram={"items": [], "edges": [], "strokes": []},
            priority_time_hours=6.0,
            priority_subjective_value=8.0,
        ),
        Tab(
            name="Exercise",
            tasks={"tasks": []},
            diagram={"items": [], "edges": [], "strokes": []},
            priority_time_hours=2.0,
            priority_subjective_value=6.0,
        ),
    ]
    tab_model.setTabs(demo_tabs, active_tab=0)
    tab_model.recomputeAndSortPriorities()
    return tab_model


def main() -> int:
    smoke_mode = "--smoke" in sys.argv or os.environ.get("PRIORITYPLOT_SMOKE") == "1"

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    engine = QQmlApplicationEngine()
    tab_model = _build_demo_tab_model()
    engine.rootContext().setContextProperty("tabModel", tab_model)
    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(PRIORITY_PLOT_QML_PATH)))

    if not engine.rootObjects():
        return 1
    if smoke_mode:
        return 0
    return app.exec()
