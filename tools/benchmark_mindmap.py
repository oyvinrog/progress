"""Reproduce large-map costs: python tools/benchmark_mindmap.py --nodes 2000.

Use --qml to include an offscreen application and QML delegate updates.
Timings are diagnostic, not machine-dependent test assertions.
"""
import argparse
import os
from pathlib import Path
import sys
from time import perf_counter

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QGuiApplication
from actiondraw.model import DiagramModel
from task_model import ProjectManager, TabModel, TaskModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nodes', type=int, default=2000)
    parser.add_argument('--qml', action='store_true')
    args = parser.parse_args()
    app = QGuiApplication([])
    tasks, tabs = TaskModel(), TabModel()
    diagram = DiagramModel(tasks)
    project = ProjectManager(tasks, diagram, tabs)
    m = project.mindmap
    tab_id = tabs.getAllTabs()[0].id
    branch = m.map.find(next(key for key, value in m.links.items() if value == tab_id))
    for i in range(args.nodes):
        branch.add_child(f'Thought {i}')

    def render():
        m.nodes
        m.edges

    if args.qml:
        from actiondraw.ui import create_actiondraw_window
        engine = create_actiondraw_window(diagram, tasks, project, tab_model=tabs)
        engine.rootObjects()[0].show()
        project.showMindmap()
        app.processEvents()
    else:
        m.sceneChanged.connect(render)
    render()  # Warm font caches before measurement.

    def measure(label, operation):
        start = perf_counter()
        operation()
        app.processEvents()
        print(f'{label}: {(perf_counter() - start) * 1000:.1f} ms', flush=True)

    measure('scene data', render)
    measure('search', lambda: m.searchText('Thought'))
    measure('next match', lambda: m.navigateSearch(1))
    measure('open tab', lambda: project.openMindmapTab(tab_id))
    measure('project view', project.showMindmap)
    branch.folded = True
    measure('folded scene', m.sceneChanged.emit)
    measure('search unfolding branch', lambda: m.searchText('Thought 199'))
    if args.qml:
        import shiboken6
        shiboken6.delete(engine._markdown_note_manager._editor._engine)
        shiboken6.delete(engine)


if __name__ == '__main__':
    main()
