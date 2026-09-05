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
    revealNode = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, tab_model=None, parent=None):
        super().__init__(parent)
        self._tabs = tab_model
        self.map = MindMap('Project')
        self.links = {}
        self._selected = self.map.root.id
        self._selected_ids = [self._selected]
        self._selection_anchor = self._selected
        self._cut_ids = []
        self._undo = []
        self._redo = []
        self._creating_tab = False
        if tab_model is not None:
            tab_model.tabsChanged.connect(self.reconcile)
            tab_model.dataChanged.connect(self.reconcile)
        self.reconcile()

    def reconcile(self, *args):
        if self._creating_tab:
            return
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
        self._selected_ids = [key for key in self._selected_ids if key in nodes]
        if self._selected and self._selected not in nodes:
            self._set_selection(self._selected_ids or [self.map.root.id])
        self._cut_ids = [key for key in self._cut_ids if key in nodes]
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
        self._set_selection([self.map.root.id])
        self._cut_ids = []
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

    @Property('QStringList', notify=changed)
    def selectedIds(self):
        return list(self._selected_ids)

    @Property('QStringList', notify=changed)
    def cutNodeIds(self):
        return [child.id for node in self._branch_roots(self._cut_ids) for child in node.walk()]

    @Property(bool, notify=changed)
    def canCut(self):
        return bool(self._selected_ids) and self.map.root.id not in self._selected_ids

    @Property(bool, notify=changed)
    def canPaste(self):
        return bool(self._cut_ids)

    @Property(bool, notify=changed)
    def canCreateTab(self):
        node = self.map.find(self._selected)
        return (self._tabs is not None and len(self._selected_ids) == 1
                and node is not None and node is not self.map.root
                and node.id not in self.links)

    @Slot()
    def createTabFromSelected(self):
        """Promote a thought in place, retaining its branch and notes.

        Mindmap undo restores the thought, but never deletes project tabs: the
        created tab is reconciled back into the map as a separate root child.
        """
        if not self.canCreateTab:
            return
        node = self.map.find(self._selected)
        # addTab emits tabsChanged synchronously. Defer reconciliation until the
        # new tab is linked here, otherwise it would get a duplicate root node.
        self._creating_tab = True
        try:
            self._tabs.addTab(node.text)
        finally:
            self._creating_tab = False
        tab = self._tabs.getAllTabs()[-1]

        def mutate():
            self.links[node.id] = tab.id
            node.text = tab.name

        self._commit(mutate)
        self.reconcile()
        self.revealNode.emit(node.id)

    def _set_selection(self, ids, primary=None):
        self._selected_ids = list(dict.fromkeys(ids))
        # The initial root selection must not prevent Ctrl+clicking movable branches.
        if len(self._selected_ids) > 1 and self.map.root.id in self._selected_ids:
            self._selected_ids.remove(self.map.root.id)
        self._selected = primary if primary in self._selected_ids else next(iter(self._selected_ids), '')
        self._selection_anchor = self._selected

    def _selection_state(self):
        return self._selected, list(self._selected_ids), self._selection_anchor

    def _restore_selection(self, state):
        self._selected, self._selected_ids, self._selection_anchor = state

    @Slot(str)
    @Slot(str, str)
    def select(self, node_id, mode='replace'):
        if self.map.find(node_id) is None:
            return
        anchor = self._selection_anchor
        if mode == 'toggle':
            ids = list(self._selected_ids)
            if node_id in ids:
                ids.remove(node_id)
            else:
                ids.append(node_id)
            self._set_selection(ids, node_id)
        elif mode == 'range':
            visible = self._layout()
            order = [node.id for node in self.map.walk() if node in visible]
            if anchor in order and node_id in order:
                start, end = sorted((order.index(anchor), order.index(node_id)))
                self._set_selection(order[start:end + 1], node_id)
                self._selection_anchor = anchor
            else:
                self._set_selection([node_id])
        elif mode == 'add':
            self._set_selection(self._selected_ids + [node_id], node_id)
            self._selection_anchor = anchor
        else:
            self._set_selection([node_id])
        self.changed.emit()

    def _branch_roots(self, ids):
        selected = set(ids)
        return [node for node in self.map.walk() if node.id in selected
                and not any(parent.id in selected for parent in node.ancestors())]

    @Slot()
    def cutSelected(self):
        if not self.canCut:
            return
        self._cut_ids = [node.id for node in self._branch_roots(self._selected_ids)]
        self.changed.emit()

    @Slot()
    def cancelCut(self):
        self._cut_ids = []
        self.changed.emit()

    @Slot()
    def pasteSelected(self):
        target = self.map.find(self._selected)
        roots = self._branch_roots(self._cut_ids)
        if target is None or not roots:
            return
        if any(node is target or node in target.ancestors() for node in roots):
            self.errorOccurred.emit('Choose a destination outside the cut branches.')
            return
        def mutate():
            for node in roots:
                node.move_to(target)
            target.folded = False
            self._set_selection([node.id for node in roots])
        if self._commit(mutate):
            self.cancelCut()
            self.revealNode.emit(self._selected)

    @Slot(str)
    @Slot(str, bool)
    def navigate(self, direction, extend=False):
        """Select the nearest visible node in a direction, as in PyPlane's editor."""
        if direction not in ('left', 'right', 'up', 'down'):
            return
        boxes = self._layout()
        current = self.map.find(self._selected)
        while current is not None and current not in boxes:
            current = current.parent
        current = current or self.map.root
        if current.id != self._selected:
            self.select(current.id, 'add' if extend else 'replace')
            self.revealNode.emit(current.id)
            return
        origin = boxes[current]
        ranked = []
        for node, box in boxes.items():
            dx = box.x + box.width / 2 - origin.x - origin.width / 2
            dy = box.center_y - origin.center_y
            primary, perpendicular = {
                'left': (-dx, abs(dy)), 'right': (dx, abs(dy)),
                'up': (-dy, abs(dx)), 'down': (dy, abs(dx)),
            }[direction]
            if primary <= 1.0:
                continue
            reading_order = box.center_y if direction in ('left', 'right') else box.x
            ranked.append((primary + perpendicular * 0.35, perpendicular / primary,
                           reading_order, node.id))
        if ranked:
            self.select(min(ranked)[-1], 'add' if extend else 'replace')
        self.revealNode.emit(self._selected)

    def _commit(self, mutation):
        before = self.to_dict()
        selected = self._selection_state()
        try:
            mutation()
            self.map.validate()
        except (ValueError, IndexError) as exc:
            self.map, self.links = self.decode(before)
            self._restore_selection(selected)
            self.errorOccurred.emit(str(exc))
            self.changed.emit()
            return False
        if self.to_dict() != before:
            self._undo.append((before, selected))
            self._redo.clear()
        self.sceneChanged.emit()
        self.changed.emit()
        return True

    @Slot(bool)
    def addThought(self, sibling=False):
        parent = self.map.find(self._selected) or self.map.root
        if sibling and parent.parent:
            parent = parent.parent
        def mutate():
            parent.folded = False
            self._set_selection([parent.add_child('New thought').id])
        self._commit(mutate)
        self.revealNode.emit(self._selected)

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
        roots = self._branch_roots(self._selected_ids)
        if not roots or self.map.root in roots:
            return
        if any(n.id in self.links for node in roots for n in node.walk()):
            self.errorOccurred.emit('This branch contains tabs. Move the tabs out before deleting it.')
            return
        def mutate():
            self._set_selection([roots[0].parent.id])
            for node in roots:
                node.remove()
        if self._commit(mutate):
            self._cut_ids = [key for key in self._cut_ids if self.map.find(key)]
            self.changed.emit()

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
            self._set_selection([node.id])
        self._commit(mutate)

    @Slot(str)
    def setSide(self, side):
        node = self.map.find(self._selected)
        if node and node.parent is self.map.root and side in ('left', 'right'):
            self._commit(lambda: setattr(node, 'side', side))

    def _restore(self, source, destination):
        if not source:
            return
        destination.append((copy.deepcopy(self.to_dict()), self._selection_state()))
        payload, selection = source.pop()
        self._restore_selection(selection)
        self._cut_ids = []
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
