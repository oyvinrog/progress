"""Project-owned mindmap with stable tab references and a QML-facing editor API."""
import copy
import weakref
from types import SimpleNamespace

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QFont, QFontMetricsF

from ._vendor.pyplane.model import MindMap
from ._vendor.pyplane.layout import assigned_sides, layout
from ._vendor.pyplane.mm import dumps, loads


class MindMapController(QObject):
    changed = Signal()
    sceneChanged = Signal()
    resetView = Signal()
    scopeChanging = Signal(str, str)
    tabActivated = Signal(str)
    revealNode = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, tab_model=None, parent=None):
        super().__init__(parent)
        self._tabs = tab_model
        self.map = MindMap('Project')
        self.links = {}
        self._completed = set()
        self._scope_tab = None
        self._view_selections = {}
        self._selected = self.map.root.id
        self._selected_ids = [self._selected]
        self._selection_anchor = self._selected
        self._cut_ids = []
        self._undo = []
        self._redo = []
        self._creating_tab = False
        self._changing_tabs = False
        self.exchange_tabs = None
        if tab_model is not None:
            tab_model.tabsChanged.connect(self.reconcile)
            tab_model.dataChanged.connect(self.reconcile)
        self.reconcile()

    @property
    def exchange_tabs(self):
        return self._tab_history_handler() if self._tab_history_handler else None

    @exchange_tabs.setter
    def exchange_tabs(self, handler):
        # A bound ProjectManager method would otherwise keep both QObjects alive
        # in a Python cycle after their QML engine has been destroyed.
        self._tab_history_handler = weakref.WeakMethod(handler) if handler else None

    @property
    def view_root(self):
        if self._scope_tab:
            for node_id, tab_id in self.links.items():
                if tab_id == self._scope_tab:
                    return self.map.find(node_id) or self.map.root
        return self.map.root

    @Property(bool, notify=changed)
    def tabScoped(self):
        return self._scope_tab is not None

    def set_scope(self, tab_id=None):
        if self._scope_tab == tab_id:
            return
        self.scopeChanging.emit(self._scope_tab or '', tab_id or '')
        self._view_selections[self._scope_tab] = self._selection_state()
        self._scope_tab = tab_id
        self._set_selection([self.view_root.id])
        if tab_id in self._view_selections:
            self._restore_selection(self._view_selections[tab_id])
            ids = [key for key in self._selected_ids if self._in_scope(self.map.find(key))]
            self._set_selection(ids or [self.view_root.id])
        self._cut_ids = []
        self.sceneChanged.emit()
        self.changed.emit()

    def _in_scope(self, node):
        return node is not None and (node is self.view_root or self.view_root in node.ancestors())

    @Slot()
    def toggleCompleted(self):
        ids = set(self._selected_ids)
        if not ids:
            return
        def mutate():
            if ids <= self._completed:
                self._completed.difference_update(ids)
            else:
                self._completed.update(ids)
        self._commit(mutate)

    def reconcile(self, *args):
        if self._creating_tab or self._changing_tabs:
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
        self._completed.intersection_update(nodes)
        self._selected_ids = [key for key in self._selected_ids if self._in_scope(self.map.find(key))]
        if not self._selected_ids or self._selected not in self._selected_ids:
            self._set_selection(self._selected_ids or [self.view_root.id])
        self._cut_ids = [key for key in self._cut_ids if key in nodes]
        self.sceneChanged.emit()
        self.changed.emit()

    def to_dict(self):
        return {'version': 1, 'xml': dumps(self.map).decode('utf-8'),
                'tab_links': dict(self.links), 'completed': sorted(self._completed)}

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
        completed = payload.get('completed', [])
        if (not isinstance(completed, list)
                or any(not isinstance(key, str) or mindmap.find(key) is None for key in completed)
                or len(set(completed)) != len(completed)):
            raise ValueError('Malformed mindmap completion data')
        return mindmap, dict(links)

    def load(self, payload=None):
        self.map, self.links = self.decode(payload) if payload is not None else (MindMap('Project'), {})
        self._completed = set((payload or {}).get('completed', []))
        self._scope_tab = None
        self._view_selections.clear()
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
                'isTab': node.id in self.links, 'folded': node.folded,
                'isViewRoot': node is self.view_root, 'completed': node.id in self._completed}

    def _layout(self):
        font = QFont()
        font.setPixelSize(14)
        metrics = QFontMetricsF(font)
        sizes = {}
        for node in self.view_root.walk():
            padding = 74.0 if node.id in self._completed else 52.0
            sizes[node] = (max(110.0, min(380.0, metrics.horizontalAdvance(node.text) + padding)), 40.0)
        # Layout only needs a root; keep the canonical tree's parent links intact.
        return layout(SimpleNamespace(root=self.view_root), sizes)

    @Property('QVariantList', notify=sceneChanged)
    def nodes(self):
        return [{'id': n.id, 'text': n.text, 'note': n.note or '', 'x': b.x, 'y': b.y,
                 'width': b.width, 'height': b.height, 'isTab': n.id in self.links,
                 'folded': n.folded, 'hasChildren': bool(n.children),
                 'isViewRoot': n is self.view_root, 'completed': n.id in self._completed}
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
        return bool(self._selected_ids) and self.view_root.id not in self._selected_ids

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
        if len(self._selected_ids) > 1 and self.view_root.id in self._selected_ids:
            self._selected_ids.remove(self.view_root.id)
        self._selected = primary if primary in self._selected_ids else next(iter(self._selected_ids), '')
        self._selection_anchor = self._selected

    def _selection_state(self):
        return self._selected, list(self._selected_ids), self._selection_anchor

    def _restore_selection(self, state):
        self._selected, self._selected_ids, self._selection_anchor = state

    @Slot(str)
    @Slot(str, str)
    def select(self, node_id, mode='replace'):
        if not self._in_scope(self.map.find(node_id)):
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
        return [node for node in self.map.walk() if node.id in selected and self._in_scope(node)
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
        if not self._in_scope(target) or not roots or self.view_root in roots:
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
        current = current or self.view_root
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

    def _commit(self, mutation, tab_state=None):
        before = self.to_dict()
        selected = self._selection_state()
        try:
            mutation()
            self.map.validate()
            self._completed.intersection_update(n.id for n in self.map.walk())
        except (ValueError, IndexError) as exc:
            self.map, self.links = self.decode(before)
            self._completed = set(before.get('completed', []))
            self._restore_selection(selected)
            self.errorOccurred.emit(str(exc))
            self.changed.emit()
            return False
        if self.to_dict() != before:
            self._undo.append((before, selected, tab_state))
            self._redo.clear()
        self.sceneChanged.emit()
        self.changed.emit()
        return True

    @Slot(bool)
    def addThought(self, sibling=False):
        parent = self.map.find(self._selected) or self.view_root
        if sibling and parent is not self.view_root and parent.parent:
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
        if not roots or self.view_root in roots:
            return
        removed_ids = {n.id for node in roots for n in node.walk()}
        tab_ids = {self.links[key] for key in removed_ids if key in self.links}
        tab_state = None
        if tab_ids:
            if self.exchange_tabs is None:
                self.errorOccurred.emit('Tab deletion requires a project manager.')
                return
            self._changing_tabs = True
            try:
                tab_state = self.exchange_tabs({'ids': tab_ids, 'tabs': []})
            except ValueError as exc:
                self.errorOccurred.emit(str(exc))
                return
            finally:
                self._changing_tabs = False
        def mutate():
            self._set_selection([roots[0].parent.id])
            for key in removed_ids:
                self.links.pop(key, None)
            for node in roots:
                node.remove()
        if self._commit(mutate, tab_state):
            self._cut_ids = [key for key in self._cut_ids if self.map.find(key)]
            self._view_selections = {key: value for key, value in self._view_selections.items()
                                     if key not in tab_ids}
            self.changed.emit()

    @Slot(str, str, str)
    def moveNode(self, node_id, target_id, placement):
        node, target = self.map.find(node_id), self.map.find(target_id)
        if (not self._in_scope(node) or not self._in_scope(target)
                or node is target or node is self.view_root):
            return
        def mutate():
            parent = (target.parent if placement in ('before', 'after')
                      and target.parent and target is not self.view_root else target)
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
        if node and node.parent is self.view_root and side in ('left', 'right'):
            self._commit(lambda: setattr(node, 'side', side))

    def _reorder_context(self, node_id):
        node = self.map.find(node_id)
        boxes = self._layout()
        if node is self.view_root or node not in boxes or node.parent is None:
            return None, [], boxes
        sides = assigned_sides(SimpleNamespace(root=self.view_root))
        siblings = [n for n in node.parent.children
                    if n in boxes and sides.get(n) == sides.get(node)]
        return node, siblings, boxes

    @Slot(str, int, result=bool)
    def canReorderNode(self, node_id, direction):
        node, siblings, _ = self._reorder_context(node_id)
        return (node is not None and direction in (-1, 1)
                and 0 <= siblings.index(node) + direction < len(siblings))

    def _reorder(self, node, siblings, index):
        old_index = siblings.index(node)
        if index == old_index:
            return
        target = siblings[index]
        sides = assigned_sides(SimpleNamespace(root=self.view_root))

        def mutate():
            # Freeze the current root-branch sides before order changes can
            # influence the layout's automatic balancing.
            for branch in self.view_root.children:
                branch.side = sides[branch]
            parent = node.parent
            insertion = parent.children.index(target) + (index > old_index)
            if parent.children.index(node) < insertion:
                insertion -= 1
            node.move_to(parent, insertion)
            self._set_selection([node.id])

        if self._commit(mutate):
            self.revealNode.emit(node.id)

    @Slot(str, int)
    def reorderNode(self, node_id, direction):
        node, siblings, _ = self._reorder_context(node_id)
        if node is None or direction not in (-1, 1):
            return
        index = siblings.index(node) + direction
        if 0 <= index < len(siblings):
            self._reorder(node, siblings, index)

    @Slot(str, float)
    def reorderNodeAt(self, node_id, center_y):
        node, siblings, boxes = self._reorder_context(node_id)
        if node is None:
            return
        index = sum(boxes[n].center_y < center_y for n in siblings if n is not node)
        self._reorder(node, siblings, index)

    def _restore(self, source, destination):
        if not source:
            return
        payload, selection, tab_state = source[-1]
        inverse = None
        if tab_state is not None:
            self._changing_tabs = True
            try:
                inverse = self.exchange_tabs(tab_state)
            except ValueError as exc:
                self.errorOccurred.emit(str(exc))
                return
            finally:
                self._changing_tabs = False
        destination.append((copy.deepcopy(self.to_dict()), self._selection_state(), inverse))
        source.pop()
        self._restore_selection(selection)
        self._cut_ids = []
        self.map, self.links = self.decode(payload)
        self._completed = set(payload.get('completed', []))
        if tab_state is not None:
            live = {tab.id for tab in self._tabs.getAllTabs()}
            self._view_selections = {key: value for key, value in self._view_selections.items()
                                     if key is None or key in live}
            if self._scope_tab is not None and self._scope_tab not in live:
                self.set_scope()
        self.reconcile()

    @Slot()
    def undo(self):
        self._restore(self._undo, self._redo)

    @Slot()
    def redo(self):
        self._restore(self._redo, self._undo)

    @Slot(str)
    def activate(self, node_id):
        if node_id in self.links and not (self.tabScoped and node_id == self.view_root.id):
            self.tabActivated.emit(self.links[node_id])
