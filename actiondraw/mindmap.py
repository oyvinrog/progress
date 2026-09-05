"""Project-owned mindmap with stable tab references and a QML-facing editor API."""
import copy

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QFont, QFontMetricsF

from ._vendor.pyplane.model import MindMap
from ._vendor.pyplane.layout import layout
from ._vendor.pyplane.mm import dumps, loads


class MindMapController(QObject):
    changed = Signal()
    sceneChanged = Signal()
    resetView = Signal()
    tabActivated = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, tab_model=None, parent=None):
        super().__init__(parent)
        self._tabs = tab_model
        self.map = MindMap('Project')
        self.links = {}
        self._selected = self.map.root.id
        self._undo = []
        self._redo = []
        if tab_model is not None:
            tab_model.tabsChanged.connect(self.reconcile)
            tab_model.dataChanged.connect(self.reconcile)
        self.reconcile()

    def reconcile(self, *args):
        tabs = self._tabs.getAllTabs() if self._tabs is not None else []
        live = {tab.id: tab for tab in tabs}
        nodes = {node.id: node for node in self.map.walk()}
        seen = set()
        for node_id, tab_id in list(self.links.items()):
            if node_id not in nodes or tab_id not in live or tab_id in seen:
                del self.links[node_id]
            else:
                nodes[node_id].text = live[tab_id].name
                seen.add(tab_id)
        for tab in tabs:
            if tab.id not in seen:
                self.links[self.map.root.add_child(tab.name).id] = tab.id
        if self.map.find(self._selected) is None:
            self._selected = self.map.root.id
        self.sceneChanged.emit()
        self.changed.emit()

    def to_dict(self):
        return {'version': 1, 'xml': dumps(self.map).decode('utf-8'),
                'tab_links': dict(self.links)}

    @staticmethod
    def decode(payload):
        if not isinstance(payload, dict) or payload.get('version') != 1:
            raise ValueError('Unsupported or malformed mindmap payload')
        if not isinstance(payload.get('xml'), str) or not isinstance(payload.get('tab_links'), dict):
            raise ValueError('Malformed mindmap data')
        mindmap = loads(payload['xml'].encode('utf-8'))
        # PyPlane flattens rich notes when reading Freeplane documents. Our editor
        # writes plain text in a single paragraph; retain its exact whitespace.
        for node in mindmap.walk():
            paragraph = node._xml.find("richcontent[@TYPE='NOTE']/html/body/p")
            if paragraph is not None and not len(paragraph):
                node.note = paragraph.text or ''
                node._original_note = node.note
        links = payload['tab_links']
        if any(not isinstance(k, str) or not isinstance(v, str) or mindmap.find(k) is None
               for k, v in links.items()):
            raise ValueError('Malformed mindmap tab links')
        if mindmap.root.id in links or len(set(links.values())) != len(links):
            raise ValueError('Duplicate tab links or linked mindmap root')
        return mindmap, dict(links)

    def load(self, payload=None):
        self.map, self.links = self.decode(payload) if payload is not None else (MindMap('Project'), {})
        self._undo.clear()
        self._redo.clear()
        self._selected = self.map.root.id
        self.reconcile()
        self.resetView.emit()

    @Property(str, notify=changed)
    def selectedId(self):
        return self._selected

    @Property('QVariantMap', notify=changed)
    def selectedNode(self):
        node = self.map.find(self._selected)
        if node is None:
            return {}
        return {'id': node.id, 'text': node.text, 'note': node.note or '',
                'isTab': node.id in self.links, 'folded': node.folded}

    def _layout(self):
        font = QFont()
        font.setPixelSize(14)
        metrics = QFontMetricsF(font)
        sizes = {node: (max(110.0, min(380.0, metrics.horizontalAdvance(node.text) + 52.0)), 40.0)
                 for node in self.map.walk()}
        return layout(self.map, sizes)

    @Property('QVariantList', notify=sceneChanged)
    def nodes(self):
        return [{'id': n.id, 'text': n.text, 'note': n.note or '', 'x': b.x, 'y': b.y,
                 'width': b.width, 'height': b.height, 'isTab': n.id in self.links,
                 'folded': n.folded, 'hasChildren': bool(n.children)}
                for n, b in self._layout().items()]

    @Property('QVariantList', notify=sceneChanged)
    def edges(self):
        boxes = self._layout()
        result = []
        for n, b in boxes.items():
            if n.parent in boxes:
                p = boxes[n.parent]
                right = b.x > p.x
                result.append({'x1': p.x + (p.width if right else 0), 'y1': p.center_y,
                               'x2': b.x + (0 if right else b.width), 'y2': b.center_y})
        return result

    @Property(bool, notify=changed)
    def canUndo(self):
        return bool(self._undo)

    @Property(bool, notify=changed)
    def canRedo(self):
        return bool(self._redo)

    @Slot(str)
    def select(self, node_id):
        if self.map.find(node_id):
            self._selected = node_id
            self.changed.emit()

    def _commit(self, mutation):
        before = self.to_dict()
        selected = self._selected
        try:
            mutation()
            self.map.validate()
        except (ValueError, IndexError) as exc:
            self.map, self.links = self.decode(before)
            self._selected = selected
            self.errorOccurred.emit(str(exc))
            self.changed.emit()
            return
        if self.to_dict() != before:
            self._undo.append((before, selected))
            self._redo.clear()
        self.sceneChanged.emit()
        self.changed.emit()

    @Slot(bool)
    def addThought(self, sibling=False):
        parent = self.map.find(self._selected) or self.map.root
        if sibling and parent.parent:
            parent = parent.parent
        def mutate():
            parent.folded = False
            self._selected = parent.add_child('New thought').id
        self._commit(mutate)

    @Slot(str, str)
    def editSelected(self, text, note):
        node = self.map.find(self._selected)
        if node is None:
            return
        def mutate():
            if node.id not in self.links:
                node.text = text
            node.note = note or None
        self._commit(mutate)

    @Slot()
    def toggleFold(self):
        node = self.map.find(self._selected)
        if node and node.children:
            self._commit(lambda: setattr(node, 'folded', not node.folded))

    @Slot()
    def deleteSelected(self):
        node = self.map.find(self._selected)
        if node is None or node.parent is None:
            return
        if any(n.id in self.links for n in node.walk()):
            self.errorOccurred.emit('This branch contains tabs. Move the tabs out before deleting it.')
            return
        def mutate():
            self._selected = node.parent.id
            node.remove()
        self._commit(mutate)

    @Slot(str, str, str)
    def moveNode(self, node_id, target_id, placement):
        node, target = self.map.find(node_id), self.map.find(target_id)
        if node is None or target is None or node is target:
            return
        def mutate():
            parent = target.parent if placement in ('before', 'after') and target.parent else target
            index = None
            if parent is not target:
                index = parent.children.index(target) + (placement == 'after')
                if node.parent is parent and parent.children.index(node) < index:
                    index -= 1
            node.move_to(parent, index)
            parent.folded = False
            self._selected = node.id
        self._commit(mutate)

    @Slot(str)
    def setSide(self, side):
        node = self.map.find(self._selected)
        if node and node.parent is self.map.root and side in ('left', 'right'):
            self._commit(lambda: setattr(node, 'side', side))

    def _restore(self, source, destination):
        if not source:
            return
        destination.append((copy.deepcopy(self.to_dict()), self._selected))
        payload, self._selected = source.pop()
        self.map, self.links = self.decode(payload)
        self.reconcile()

    @Slot()
    def undo(self):
        self._restore(self._undo, self._redo)

    @Slot()
    def redo(self):
        self._restore(self._redo, self._undo)

    @Slot(str)
    def activate(self, node_id):
        if node_id in self.links:
            self.tabActivated.emit(self.links[node_id])
