"""Bounded text fitting and real QML overflow/preview regressions."""

import os
from pathlib import Path
import subprocess
import sys

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtTest import QSignalSpy

from actiondraw import DiagramItem, DiagramItemType, DiagramModel


def test_fit_limits_manual_sizes_and_round_trip(app):
    model = DiagramModel()
    item_id = model.addBox(10, 20, "Long text")
    item = model.getItem(item_id)
    assert model.fitItemText(item_id, 1000, 1000)
    assert (item.width, item.height) == (320, 220)
    model.resizeItem(item_id, 500, 300)
    assert not model.fitItemText(item_id, 200, 100)
    assert (item.width, item.height) == (500, 300)
    restored = DiagramModel()
    fit_requests = QSignalSpy(restored.textFitRequested)
    restored.from_dict(model.to_dict())
    assert fit_requests.count() == 0
    assert (restored.getItem(item_id).width, restored.getItem(item_id).height) == (500, 300)
    assert restored.getItem(item_id).text == "Long text"


def test_fit_collision_and_geometry(app):
    model = DiagramModel()
    first = model.addBox(0, 0, "First")
    second = model.addBox(160, 0, "Second")
    model.addEdge(first, second)
    assert not model.fitItemText(first, 240, 100)
    assert model.getItem(first).width == 120
    model.moveItem(second, 500, 0)
    assert model.fitItemText(first, 240, 100)
    assert model._item_center(model.getItem(first)) == (120, 50)
    assert model.maxItemY == 100
    assert model.getItemSnapshot(first)["width"] == 240


@pytest.mark.parametrize("width,height", [(float("nan"), 100), (100, float("inf"))])
def test_fit_rejects_invalid_dimensions(app, width, height):
    model = DiagramModel()
    item_id = model.addBox(0, 0, "Text")
    assert not model.fitItemText(item_id, width, height)
    assert not model.fitItemText("missing", 200, 100)


def test_fit_excludes_images(app):
    model = DiagramModel()
    model._append_item(DiagramItem(id="image", item_type=DiagramItemType.IMAGE, x=0, y=0))
    assert not model.fitItemText("image", 320, 220)
    assert model.getItem("image").width == 120


def test_fit_requests_follow_visible_text_edits_not_tab_selection(app):
    model = DiagramModel()
    requests = QSignalSpy(model.textFitRequested)
    item_id = model.addPresetItem("freetext", 0, 0)
    assert requests.count() == 1
    model.setEditorTabs(item_id, "freetext", [
        {"name": "First", "text": "Short"}, {"name": "Second", "text": "Other"},
    ])
    assert requests.count() == 2
    model.setItemTextTabIndex(item_id, 1)
    assert requests.count() == 2
    model.setEditorTabs(item_id, "freetext", [
        {"name": "First", "text": "Changed inactive tab"}, {"name": "Second", "text": "Other"},
    ])
    assert requests.count() == 2
    model.setEditorTabs(item_id, "freetext", [
        {"name": "First", "text": "Changed inactive tab"}, {"name": "Second", "text": "Long " * 100},
    ])
    assert requests.count() == 3
    model.setItemText(item_id, "Changed again")
    assert requests.count() == 3  # The primary tab is currently inactive.
    model.setItemText(item_id, "Changed again")
    assert requests.count() == 3


def test_node_text_qml_runtime():
    # Isolate the known PySide/Python 3.13 cyclic-finalization crash, as the
    # application's validation smoke test does. Assertions still fail normally.
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--qml-runtime"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "QML runtime checks passed" in result.stdout
    assert "Binding loop" not in result.stderr
    assert "TypeError" not in result.stderr
    assert "ReferenceError" not in result.stderr


def _check_qml_runtime():
    from PySide6.QtCore import QMetaObject, QObject, QPointF, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from actiondraw import create_actiondraw_window
    from task_model import TaskModel

    app = QGuiApplication([])
    tasks = TaskModel()
    model = DiagramModel(tasks)
    long_text = "This is a long label with readable words. " * 20
    item_id = model.addBox(30, 30, long_text)
    engine = create_actiondraw_window(model, tasks)
    assert engine.rootObjects()
    window = engine.rootObjects()[0]

    def settle():
        QTest.qWait(30)

    def walk(item):
        yield item
        for child in item.childItems():
            yield from walk(child)

    def node_for(node_id):
        return next(item for item in walk(window.contentItem())
                    if item.objectName() == "diagramNode_" + node_id)

    def label_for(node_id):
        return next(item for item in walk(node_for(node_id))
                    if item.objectName() == "nodeText" and item.isVisible())

    def read_button(node_id):
        return next(item for item in walk(label_for(node_id))
                    if item.objectName() == "nodeReadMore")

    def click(item):
        point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        settle()

    settle()
    original = model.to_dict()
    label = label_for(item_id)
    assert label.property("overflowing")
    assert (model.getItem(item_id).width, model.getItem(item_id).height) == (120, 60)

    # The actual button must win pointer handling over node drag/tap handlers.
    click(read_button(item_id))
    preview = window.findChild(QObject, "nodeTextPreview")
    assert preview.property("visible")
    assert "readable words" in preview.property("fullText")
    assert model.to_dict() == original
    QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
    QTest.keyClick(window, Qt.Key_C, Qt.ControlModifier)
    assert "readable words" in app.clipboard().text()
    window.setProperty("selectedItemId", item_id)
    QTest.keyClick(window, Qt.Key_Delete)
    assert model.getItem(item_id) is not None
    QTest.keyClick(window, Qt.Key_Escape)
    settle()
    assert not preview.property("visible")

    # Keyboard activation, small windows, and zoom-independent overlay sizing.
    read_button(item_id).forceActiveFocus()
    QTest.keyClick(window, Qt.Key_Space)
    settle()
    assert preview.property("visible")
    width = preview.property("width")
    window.setProperty("zoomLevel", 0.5)
    settle()
    assert preview.property("width") == width
    window.setWidth(400)
    window.setHeight(350)
    settle()
    assert preview.property("width") <= 376
    assert preview.property("height") <= 326
    QTest.keyClick(window, Qt.Key_Escape)
    window.setWidth(1100)
    window.setHeight(800)
    window.setProperty("zoomLevel", 1)
    settle()

    # Real text measurement: short text, newlines, unbroken URLs, Markdown,
    # and large content. Every edit preserves font size and caps geometry.
    for text in ["Short", "First\nSecond\nThird", "https://example.com/" + "x" * 600,
                 "# Heading\n\n" + "- **A Markdown list item**\n" * 40, long_text * 20]:
        model.setItemText(item_id, text)
        settle()
        item = model.getItem(item_id)
        assert 120 <= item.width <= 320
        assert 60 <= item.height <= 220
        assert label.property("font").pixelSize() == 14
        assert label.property("fullTextHeight") > 0
    assert label.property("overflowing")
    assert (item.width, item.height) == (320, 220)
    model.resizeItem(item_id, 120, 60)
    settle()
    assert (item.width, item.height) == (120, 60)
    assert QMetaObject.invokeMethod(node_for(item_id), "fitText", Qt.DirectConnection)
    settle()
    assert (item.width, item.height) == (320, 220)
    click(read_button(item_id))
    reader = preview.findChild(QObject, "nodePreviewText")
    assert reader.property("readOnly") and reader.property("selectByMouse")
    scroll = preview.findChild(QObject, "nodePreviewScroll")
    flickable = scroll.property("contentItem")
    assert flickable.property("contentHeight") > flickable.property("height")
    flickable.setProperty("contentY", 100)
    assert flickable.property("contentY") == 100
    QTest.keyClick(window, Qt.Key_Escape)

    # The normal node types share the same overflow path and use their own font
    # and padding; switching free-text tabs only changes the displayed content.
    for i, kind in enumerate(["note", "database", "server", "cloud", "wish", "obstacle", "chatgpt", "freetext"]):
        typed_id = model.addPresetItemWithText(kind, 2000 + i * 400, 2000, long_text)
        settle()
        assert label_for(typed_id).property("overflowing")
        assert model.getItem(typed_id).height <= 220
    free_id = typed_id
    model.setEditorTabs(free_id, "freetext", [
        {"name": "First", "text": "Short"}, {"name": "Second", "text": long_text},
    ])
    settle()
    free_size = (model.getItem(free_id).width, model.getItem(free_id).height)
    assert not label_for(free_id).property("overflowing")
    model.setItemTextTabIndex(free_id, 1)
    settle()
    assert label_for(free_id).property("overflowing")
    task_id = model.addTaskFromText(long_text, 6000, 2000)
    settle()
    assert label_for(task_id).property("overflowing")
    assert label_for(task_id).property("font").bold()
    assert (model.getItem(free_id).width, model.getItem(free_id).height) == free_size
    model.setItemTextTabIndex(free_id, 0)
    model.setItemText(free_id, long_text)
    settle()
    assert label_for(free_id).property("overflowing")

    # Creation fits after the delegate exists; collision leaves geometry alone.
    fresh = model.addBox(600, 30, "A moderately long label " * 3)
    settle()
    assert model.getItem(fresh).height > 60
    crowded = model.addBox(600, 300, "Short")
    model.addBox(730, 300, "Neighbor")
    model.setItemText(crowded, long_text)
    settle()
    assert (model.getItem(crowded).width, model.getItem(crowded).height) == (120, 60)

    saved = model.to_dict()
    model.from_dict(saved)
    settle()
    assert [(i["x"], i["y"], i["width"], i["height"], i["text"]) for i in model.to_dict()["items"]] == [
        (i["x"], i["y"], i["width"], i["height"], i["text"]) for i in saved["items"]
    ]
    label = label_for(item_id)

    # Crossing the lightweight Markdown threshold and changing selection must
    # never modify the existing node's dimensions.
    dimensions = (model.getItem(item_id).width, model.getItem(item_id).height)
    for i in range(81):
        model.addBox(2000 + i * 400, 1000, "Short")
    settle()
    window.setProperty("selectedItemId", "")
    settle()
    window.setProperty("selectedItemId", item_id)
    settle()
    assert (model.getItem(item_id).width, model.getItem(item_id).height) == dimensions

    # A diagram replacement (even reusing IDs), or deletion, closes the panel.
    click(read_button(item_id))
    assert preview.property("visible")
    model.from_dict(saved)
    settle()
    assert not preview.property("visible")
    click(read_button(item_id))
    assert preview.property("visible")
    model.removeItem(item_id)
    settle()
    assert not preview.property("visible")
    print("QML runtime checks passed", flush=True)


if __name__ == "__main__":
    try:
        _check_qml_runtime()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stderr.flush()
        os._exit(1)
    os._exit(0)
