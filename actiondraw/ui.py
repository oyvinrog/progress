"""UI creation functions for ActionDraw."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine

from .model import DiagramModel
from .markdown_image_paster import MarkdownImagePaster
from .qml import ACTIONDRAW_QML_PATH, QML_DIR


def create_actiondraw_window(
    diagram_model: DiagramModel,
    task_model,
    project_manager=None,
    markdown_note_manager=None,
    markdown_image_paster=None,
    tab_model=None,
) -> QQmlApplicationEngine:
    """Create and return a QQmlApplicationEngine hosting the ActionDraw UI."""
    from .markdown_note_manager import MarkdownNoteManager

    engine = QQmlApplicationEngine()
    if markdown_note_manager is None:
        markdown_note_manager = MarkdownNoteManager(diagram_model)
    if markdown_image_paster is None:
        markdown_image_paster = MarkdownImagePaster()
    engine.rootContext().setContextProperty("diagramModel", diagram_model)
    engine.rootContext().setContextProperty("taskModel", task_model)
    engine.rootContext().setContextProperty("projectManager", project_manager)
    engine.rootContext().setContextProperty("markdownNoteManager", markdown_note_manager)
    engine.rootContext().setContextProperty("markdownImagePaster", markdown_image_paster)
    engine.rootContext().setContextProperty("tabModel", tab_model)
    engine._markdown_note_manager = markdown_note_manager
    engine._markdown_image_paster = markdown_image_paster
    engine.addImportPath(str(QML_DIR))
    engine.load(QUrl.fromLocalFile(str(ACTIONDRAW_QML_PATH)))
    return engine


def main() -> int:
    """Main entry point for ActionDraw standalone mode."""
    from PySide6.QtWidgets import QApplication
    from task_model import TaskModel, ProjectManager, TabModel

    smoke_mode = "--smoke" in sys.argv or os.environ.get("ACTIONDRAW_SMOKE") == "1"

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    task_model = TaskModel()
    diagram_model = DiagramModel(task_model=task_model)
    tab_model = TabModel()
    project_manager = ProjectManager(task_model, diagram_model, tab_model)

    engine = create_actiondraw_window(
        diagram_model,
        task_model,
        project_manager,
        tab_model=tab_model,
    )
    if not engine.rootObjects():
        return 1

    if smoke_mode:
        return 0

    # Load file from command line argument if provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        # Handle file:// URLs
        if file_path.startswith("file://"):
            file_path = file_path[7:]
        if os.path.exists(file_path):
            project_manager.loadProject(file_path)

    return app.exec()
