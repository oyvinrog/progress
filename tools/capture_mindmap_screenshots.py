#!/usr/bin/env python3
"""Render the README's fictional launch plan with the real ActionDraw QML UI.

Run from a source checkout: python tools/capture_mindmap_screenshots.py
No project files are loaded or saved; PNGs are written to assets/.
"""

import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QMetaObject, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actiondraw.model import DiagramModel
from actiondraw.ui import create_actiondraw_window
from task_model import ProjectManager, TabModel, TaskModel


def main():
    app = QGuiApplication([])
    tasks = TaskModel()
    tabs = TabModel()
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    mindmap = project.mindmap
    tabs.renameTab(0, "Website launch")
    tabs.addTab("Customer research")
    tabs.addTab("Launch checklist")
    names = ["Website launch", "Customer research", "Launch checklist"]
    for name, score in zip(names, [9, 6, 3]):
        index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.name == name)
        tabs.setPriorityPoint(index, math.e, score)
    linked = {tab_id: node_id for node_id, tab_id in mindmap.links.items()}
    by_name = {tab.name: linked[tab.id] for tab in tabs.getAllTabs()}
    website, research, checklist = [by_name[name] for name in names]
    mindmap.select(mindmap.map.root.id)
    mindmap.editSelected("Autumn launch", "A sample project for the ActionDraw README.")

    def add(parent, title, note="", complete=False):
        mindmap.select(parent)
        mindmap.addThought(False)
        mindmap.editSelected(title, note)
        node_id = mindmap.selectedId
        if complete:
            mindmap.toggleCompleted()
        return node_id

    mindmap.select(website)
    mindmap.setSide("right")
    content = add(website, "Content & messaging")
    add(content, "Draft homepage copy", complete=True)
    review = add(content, "Review with design", "Goal: agree on the homepage story before development.\n\nBring to the review:\n- Final headline and customer benefit\n- Two customer quotes\n- Mobile layout and call to action\n\nDone when: copy and layout are approved.")
    review_at = (datetime.now() + timedelta(days=7)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    mindmap.set_reminder(review, review_at.timestamp())
    build = add(website, "Build & quality")
    add(build, "Check mobile layout")
    add(build, "Test signup flow")
    mindmap.select(research)
    mindmap.setSide("left")
    add(research, "Interview 5 customers", complete=True)
    add(research, "Summarize pain points")
    mindmap.select(checklist)
    mindmap.setSide("left")
    add(checklist, "Prepare announcement")
    add(checklist, "Publish & monitor")
    mindmap.toggleBookmark(review)

    engine = create_actiondraw_window(diagram, tasks, project, tab_model=tabs)
    window = engine.rootObjects()[0]
    window.resize(1440, 760)
    window.show()
    pane = window.findChild(QObject, "mindmapPane")
    if pane is None:
        raise RuntimeError("Mindmap pane was not created")

    def capture(name, fit=True):
        QTest.qWait(300)
        if fit:
            QMetaObject.invokeMethod(pane, "fitMap")
        QTest.qWait(300)
        image = window.grabWindow()
        path = ROOT / "assets" / name
        if image.isNull() or not image.save(str(path)):
            raise RuntimeError(f"Could not capture {path}")
        print(f"Saved {path.relative_to(ROOT)} ({image.width()}x{image.height()})")

    try:
        project.showMindmap()
        mindmap.select(website)
        capture("mindmap-overview.png")
        mindmap.activate(website)
        mindmap.select(review)
        capture("mindmap-branch.png")
        QMetaObject.invokeMethod(pane, "editNode")
        capture("mindmap-notes.png", fit=False)
    finally:
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
