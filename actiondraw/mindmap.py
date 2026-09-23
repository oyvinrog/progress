"""Project-owned mindmap with stable tab references and a QML-facing editor API."""
import copy
import math
import weakref
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication

from ._vendor.pyplane.model import MindMap
from ._vendor.pyplane.layout import assigned_sides, layout
from ._vendor.pyplane.mm import dumps, loads
from .outline_clipboard import (
    looks_like_opml,
    outline_to_indented_text,
    outline_to_opml,
    parse_opml_text,
    parse_text_hierarchy,
)


class MindMapController(QObject):
    changed = Signal()
    sceneChanged = Signal()
    resetView = Signal()
    scopeChanging = Signal(str, str)
    tabActivated = Signal(str)
    revealNode = Signal(str)
    errorOccurred = Signal(str)
    clipboardChanged = Signal()

    def __init__(self, tab_model=None, parent=None):
        super().__init__(parent)
        self._tabs = tab_model
        self.map = MindMap('Project')
        self.links = {}
        self._completed = set()
        self._measure_progress = set()
        self.reminders = {}
        self._bookmarks = []
        self._scope_tab = None
        self._view_selections = {}
        self._selected = self.map.root.id
        self._selected_ids = [self._selected]
        self._selection_anchor = self._selected
        self._cut_ids = []
        self._search_query = ''
        self._priority_filter = 1.0
        self._undo = []
        self._redo = []
        self._creating_tab = False
        self._changing_tabs = False
        self.exchange_tabs = None
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self.clipboardChanged)
        if tab_model is not None:
            tab_model.tabsChanged.connect(self.reconcile)
            tab_model.priorityRanksChanged.connect(self.reconcile)
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
        self.clearSearch()
        self._priority_filter = 1.0
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
                for node_id in ids:
                    self.reminders.pop(node_id, None)
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
        self._measure_progress.intersection_update(nodes)
        self._bookmarks = [key for key in self._bookmarks if key in nodes]
        self.reminders = {key: value for key, value in self.reminders.items() if key in nodes}
        self._selected_ids = [key for key in self._selected_ids if self._in_scope(self.map.find(key))]
        if not self._selected_ids or self._selected not in self._selected_ids:
            self._set_selection(self._selected_ids or [self.view_root.id])
        self._cut_ids = [key for key in self._cut_ids if key in nodes]
        self._sync_filter_selection()
        self.sceneChanged.emit()
        self.changed.emit()

    def to_dict(self):
        return {'version': 1, 'xml': dumps(self.map).decode('utf-8'),
                'tab_links': dict(self.links), 'completed': sorted(self._completed),
                'reminders': copy.deepcopy(self.reminders), 'bookmarks': list(self._bookmarks),
                'measure_progress': sorted(self._measure_progress)}

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
        measure_progress = payload.get('measure_progress', [])
        if (not isinstance(measure_progress, list)
                or any(not isinstance(key, str) or mindmap.find(key) is None
                       for key in measure_progress)
                or len(set(measure_progress)) != len(measure_progress)):
            raise ValueError('Malformed mindmap progress settings')
        bookmarks = payload.get('bookmarks', [])
        if (not isinstance(bookmarks, list)
                or any(not isinstance(key, str) or mindmap.find(key) is None for key in bookmarks)
                or len(set(bookmarks)) != len(bookmarks)):
            raise ValueError('Malformed mindmap bookmarks')
        reminders = payload.get('reminders', {})
        if not isinstance(reminders, dict):
            raise ValueError('Malformed mindmap reminders')
        for node_id, reminder in reminders.items():
            if (not isinstance(node_id, str) or mindmap.find(node_id) is None
                    or not isinstance(reminder, dict)
                    or type(reminder.get('at')) not in (int, float)
                    or type(reminder.get('send_notification')) is not bool):
                raise ValueError('Malformed mindmap reminder')
            try:
                if not math.isfinite(reminder['at']):
                    raise ValueError('Non-finite reminder date')
                datetime.fromtimestamp(reminder['at'])
            except (ValueError, OverflowError, OSError) as exc:
                raise ValueError('Malformed mindmap reminder date') from exc
        return mindmap, dict(links)

    def load(self, payload=None):
        self.map, self.links = self.decode(payload) if payload is not None else (MindMap('Project'), {})
        self._search_query = ''
        self._priority_filter = 1.0
        self._completed = set((payload or {}).get('completed', []))
        self._measure_progress = set((payload or {}).get('measure_progress', []))
        self.reminders = copy.deepcopy((payload or {}).get('reminders', {}))
        self._bookmarks = list((payload or {}).get('bookmarks', []))
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

    @Property(str, notify=changed)
    def searchQuery(self):
        return self._search_query

    def _search_matches(self):
        query = self._search_query.casefold()
        retained = self._priority_nodes()
        return [node for node in self.view_root.walk()
                if node in retained and query in node.text.casefold()] if query else []

    @Property(int, notify=changed)
    def searchMatchCount(self):
        return len(self._search_matches())

    @Property(int, notify=changed)
    def searchMatchPosition(self):
        ids = [node.id for node in self._search_matches()]
        return ids.index(self._selected) + 1 if self._selected in ids else 0

    @Slot()
    def clearSearch(self):
        if self._search_query:
            self._search_query = ''
            self.changed.emit()

    @Slot(str)
    def searchText(self, query):
        self._search_query = query
        self.navigateSearch(0)

    @Slot(int)
    def navigateSearch(self, direction):
        matches = self._search_matches()
        if not matches:
            self.changed.emit()
            return
        ids = [node.id for node in matches]
        index = ((ids.index(self._selected) + direction) % len(ids)
                 if self._selected in ids else (-1 if direction < 0 else 0))
        node = matches[index]
        for ancestor in node.ancestors():
            if self._in_scope(ancestor):
                ancestor.folded = False
        self.select(node.id)
        self.sceneChanged.emit()
        self.revealNode.emit(node.id)

    @Property('QVariantMap', notify=changed)
    def selectedNode(self):
        node = self.map.find(self._selected)
        if node is None:
            return {}
        return {'id': node.id, 'text': node.text, 'note': node.note or '',
                'isTab': node.id in self.links, 'folded': node.folded,
                'isViewRoot': node is self.view_root, 'completed': node.id in self._completed,
                'bookmarked': node.id in self._bookmarks,
                'measureProgress': node.id in self._measure_progress,
                **self.reminderData(node.id)}

    @Property('QVariantList', notify=changed)
    def bookmarks(self):
        result = []
        for node_id in self._bookmarks:
            node = self.map.find(node_id)
            if node is not None:
                path = list(reversed(list(node.ancestors()))) + [node]
                result.append({'id': node.id, 'text': node.text,
                               'path': ' / '.join(n.text for n in path)})
        return result

    @Slot(str)
    def toggleBookmark(self, node_id):
        if self.map.find(node_id) is None:
            return
        def mutate():
            if node_id in self._bookmarks:
                self._bookmarks.remove(node_id)
            else:
                self._bookmarks.append(node_id)
        self._commit(mutate)

    @Slot(str)
    def toggleMeasureProgress(self, node_id):
        if self.map.find(node_id) is None:
            return
        def mutate():
            if node_id in self._measure_progress:
                self._measure_progress.remove(node_id)
            else:
                self._measure_progress.add(node_id)
        self._commit(mutate)

    @Slot(str, result=bool)
    def measuresProgress(self, node_id):
        return node_id in self._measure_progress

    @Slot(str)
    def jumpToBookmark(self, node_id):
        if node_id in self._bookmarks:
            self.reveal_reminder(node_id)

    @Slot(str, result='QVariantMap')
    def reminderData(self, node_id):
        reminder = self.reminders.get(node_id)
        return {'reminderActive': reminder is not None,
                'reminderAt': datetime.fromtimestamp(reminder['at']).strftime('%Y-%m-%d %H:%M') if reminder else '',
                'reminderSendNotification': reminder['send_notification'] if reminder else False}

    def set_reminder(self, node_id, timestamp, send_notification=False):
        if self.map.find(node_id) is None:
            return False
        return self._commit(lambda: self.reminders.update({
            node_id: {'at': timestamp, 'send_notification': bool(send_notification)}}))

    @Slot(str)
    def clearReminder(self, node_id):
        if node_id in self.reminders:
            self._commit(lambda: self.reminders.pop(node_id, None))

    def consume_reminder(self, node_id):
        """Delivery is not undoable; scrub this schedule from both history stacks."""
        reminder = self.reminders.pop(node_id, None)
        if reminder is None:
            return
        for payload, _, _ in self._undo + self._redo:
            saved = payload.get('reminders', {})
            if saved.get(node_id) == reminder:
                saved.pop(node_id)
        self.sceneChanged.emit()
        self.changed.emit()

    def reveal_reminder(self, node_id):
        node = self.map.find(node_id)
        if node is None:
            return False
        if not self._in_scope(node):
            self.set_scope()
        if node not in self._priority_nodes():
            self.setPriorityFilter(1.0)
        for ancestor in node.ancestors():
            ancestor.folded = False
        self.select(node_id)
        self.sceneChanged.emit()
        self.revealNode.emit(node_id)
        return True

    def _priority_data(self):
        """Project-wide priority thirds and top-three badges, independent of scope."""
        all_tabs = self._tabs.getAllTabs() if self._tabs is not None else []
        tabs = sorted((tab for tab in all_tabs if tab.include_in_priority_plot),
                      key=lambda tab: tab.priority_score)
        result = {}
        start = 0
        while start < len(tabs):
            end = start + 1
            score = tabs[start].priority_score
            while end < len(tabs) and tabs[end].priority_score == score:
                end += 1
            percentile = (start + end) / (2 * len(tabs))
            level = 1 if percentile < 1 / 3 else 3 if percentile >= 2 / 3 else 2
            for tab in tabs[start:end]:
                result[tab.id] = {'priorityScore': score, 'priorityLevel': level,
                                  'priorityRank': 0}
            start = end
        ranks = self._tabs.priorityRanks if self._tabs is not None else []
        for tab, rank in zip(all_tabs, ranks):
            if 1 <= rank <= 3:
                result[tab.id]['priorityRank'] = rank
        return result

    def _scope_scores(self, priorities):
        return [priorities[self.links[n.id]]['priorityScore'] for n in self.view_root.walk()
                if self.links.get(n.id) in priorities]

    @Property(float, notify=changed)
    def priorityFilter(self):
        return self._priority_filter

    @Property(bool, notify=changed)
    def priorityFilterEnabled(self):
        return bool(self._scope_scores(self._priority_data()))

    @Property(str, notify=changed)
    def priorityFilterText(self):
        scores = self._scope_scores(self._priority_data())
        if self._priority_filter == 1 or not scores:
            return 'All'
        cutoff = max(scores) + (min(scores) - max(scores)) * self._priority_filter
        return f'Score ≥ {cutoff:.3g}'

    def _priority_nodes(self, priorities=None):
        priorities = self._priority_data() if priorities is None else priorities
        scores = self._scope_scores(priorities)
        root = self.view_root
        if self._priority_filter == 1 or not scores:
            return set(root.walk())
        cutoff = max(scores) + (min(scores) - max(scores)) * self._priority_filter
        retained = {root}
        matching = {}
        for node in root.walk():
            if node.id in self.links:
                data = priorities.get(self.links[node.id])
                matching[node] = data is not None and data['priorityScore'] >= cutoff
            else:
                matching[node] = matching.get(node.parent, False)
            if matching[node]:
                retained.add(node)
        for node in list(retained):
            ancestor = node.parent
            while ancestor is not None and node is not root:
                retained.add(ancestor)
                if ancestor is root:
                    break
                ancestor = ancestor.parent
        return retained

    def _sync_filter_selection(self):
        if self._priority_filter == 1:
            return
        if not self.priorityFilterEnabled:
            self._priority_filter = 1.0
            return
        visible = self._layout()
        ids = [key for key in self._selected_ids if self.map.find(key) in visible]
        if self._selected in ids and ids == self._selected_ids:
            return
        node = self.map.find(self._selected)
        while node is not None and node not in visible:
            node = node.parent
        self._set_selection(ids or [(node or self.view_root).id], self._selected)

    @Slot(float)
    def setPriorityFilter(self, position):
        if not math.isfinite(position):
            return
        self._priority_filter = max(0.0, min(1.0, position)) if self.priorityFilterEnabled else 1.0
        self._sync_filter_selection()
        self.sceneChanged.emit()
        self.changed.emit()

    def _layout(self, priorities=None):
        if priorities is None:
            priorities = self._priority_data()
        font = QFont()
        font.setPixelSize(14)
        metrics = QFontMetricsF(font)
        font.setBold(True)
        bold_metrics = QFontMetricsF(font)
        sizes = {}
        for node in self.view_root.walk():
            padding = 74.0 if node.id in self._completed else 52.0
            if node.id in self._bookmarks:
                padding += 20.0
            if self.links.get(node.id) in priorities:
                padding += 30.0
                if priorities[self.links[node.id]]['priorityRank'] > 0:
                    padding += 30.0
            node_metrics = bold_metrics if node.style.bold else metrics
            width = max(110.0, min(380.0, node_metrics.horizontalAdvance(node.text) + padding))
            if node.id in self.reminders:
                width = max(width, 210.0)
            sizes[node] = (width, 40.0 + (24.0 if node.id in self.reminders else 0.0)
                           + (24.0 if node.id in self._measure_progress else 0.0))
        # Layout only needs a root; keep the canonical tree's parent links intact.
        if self._priority_filter == 1:
            return layout(SimpleNamespace(root=self.view_root), sizes)
        retained = self._priority_nodes(priorities)
        sides = assigned_sides(SimpleNamespace(root=self.view_root))
        projected = {node: copy.copy(node) for node in retained}
        for node, clone in projected.items():
            clone.children = [projected[child] for child in node.children if child in retained]
            clone.parent = projected.get(node.parent)
            clone.side = sides.get(node, node.side)
        boxes = layout(SimpleNamespace(root=projected[self.view_root]),
                       {projected[node]: size for node, size in sizes.items() if node in retained})
        return {node: boxes[projected[node]] for node in sizes
                if node in projected and projected[node] in boxes}

    @Property('QVariantList', notify=sceneChanged)
    def nodes(self):
        priorities = self._priority_data()
        return [{'id': n.id, 'text': n.text, 'note': n.note or '', 'x': b.x, 'y': b.y,
                 'width': b.width, 'height': b.height, 'isTab': n.id in self.links,
                 'folded': n.folded, 'hasChildren': bool(n.children), 'bold': bool(n.style.bold),
                 'isViewRoot': n is self.view_root, 'completed': n.id in self._completed,
                 'bookmarked': n.id in self._bookmarks,
                 'measureProgress': n.id in self._measure_progress,
                 'progressPercent': (math.floor(100 * sum(child.id in self._completed for child in n.children)
                                                  / len(n.children) + 0.5) if n.children else 0),
                 **self.reminderData(n.id),
                 **priorities.get(self.links.get(n.id), {'priorityScore': None, 'priorityLevel': 0,
                                                       'priorityRank': 0})}
                for n, b in self._layout(priorities).items()]

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

    def _clipboard_text(self):
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return ''
        mime_data = clipboard.mimeData()
        if mime_data is None or not mime_data.hasText():
            return ''
        return mime_data.text() or ''

    def _clipboard_outline(self):
        text = self._clipboard_text()
        if not text.strip():
            return None
        entries = parse_opml_text(text)
        if entries is not None:
            return entries
        if looks_like_opml(text):
            return None
        return parse_text_hierarchy(text) or None

    def _export_node(self, node_id):
        node = self.map.find(node_id)
        if node is None:
            self.errorOccurred.emit('The branch to export no longer exists.')
        return node

    @Slot(str, result=bool)
    def copyBranchAsOpml(self, node_id):
        node = self._export_node(node_id)
        clipboard = QGuiApplication.clipboard()
        if node is None or clipboard is None:
            return False
        clipboard.setText(outline_to_opml(node, node.text or 'ActionDraw Branch'))
        return True

    @Slot(str, result=bool)
    def copyBranchAsText(self, node_id):
        node = self._export_node(node_id)
        clipboard = QGuiApplication.clipboard()
        if node is None or clipboard is None:
            return False
        clipboard.setText(outline_to_indented_text(node))
        return True

    @Slot(str, str, result=bool)
    def saveBranchAsOpml(self, node_id, output_path):
        node = self._export_node(node_id)
        if node is None:
            return False
        path_value = str(output_path or '')
        url = QUrl(path_value)
        if url.isLocalFile() or path_value.startswith('file:'):
            path_value = url.toLocalFile()
        if not path_value:
            self.errorOccurred.emit('No OPML export path was selected.')
            return False
        try:
            Path(path_value).write_text(
                outline_to_opml(node, node.text or 'ActionDraw Branch'),
                encoding='utf-8',
            )
        except (OSError, ValueError) as exc:
            self.errorOccurred.emit(f'Could not export OPML: {exc}')
            return False
        return True

    @Property(bool, notify=clipboardChanged)
    def canPasteClipboardText(self):
        return self._clipboard_outline() is not None

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

    @Slot(result=bool)
    def pasteSelected(self):
        target = self.map.find(self._selected)
        if self._cut_ids:
            roots = self._branch_roots(self._cut_ids)
            if not self._in_scope(target) or not roots or self.view_root in roots:
                return False
            if any(node is target or node in target.ancestors() for node in roots):
                self.errorOccurred.emit('Choose a destination outside the cut branches.')
                return False

            def move_cut_branches():
                for node in roots:
                    node.move_to(target)
                target.folded = False
                self._set_selection([node.id for node in roots])

            if self._commit(move_cut_branches):
                self.cancelCut()
                self.revealNode.emit(self._selected)
                return True
            return False

        if not self._in_scope(target):
            return False
        text = self._clipboard_text()
        entries = parse_opml_text(text)
        if entries is None:
            if looks_like_opml(text):
                self.errorOccurred.emit('Clipboard contains malformed or empty OPML.')
                return False
            entries = parse_text_hierarchy(text)
        if not entries:
            return False

        created_roots = []

        def import_outline():
            target.folded = False
            parents = []
            for entry in entries:
                level = min(max(0, int(entry['level'])), len(parents))
                del parents[level:]
                parent = target if level == 0 else parents[level - 1]
                side = 'right' if parent is self.view_root else None
                node = parent.add_child(str(entry['text']).strip(), side=side)
                parents.append(node)
                if level == 0:
                    created_roots.append(node)
            self._set_selection([node.id for node in created_roots], created_roots[0].id)

        if not self._commit(import_outline):
            return False
        self.revealNode.emit(created_roots[0].id)
        return True

    @Slot(str)
    @Slot(str, bool)
    def navigate(self, direction, extend=False):
        """Follow the tree horizontally and nearby visible nodes vertically."""
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
        if direction in ('left', 'right'):
            if current is self.view_root:
                root_center = origin.x + origin.width / 2
                target = None if current.folded else next(
                    (child for child in current.children if child in boxes
                     and ((boxes[child].x + boxes[child].width / 2 < root_center)
                          == (direction == 'left'))), None)
            else:
                parent = current.parent
                parent_center = boxes[parent].x + boxes[parent].width / 2
                on_left = origin.x + origin.width / 2 < parent_center
                toward_parent = direction == ('right' if on_left else 'left')
                if toward_parent:
                    target = parent
                else:
                    target = (next((child for child in current.children if child in boxes), None)
                              if not current.folded else None)
            if target is not None:
                self.select(target.id, 'add' if extend else 'replace')
            self.revealNode.emit(self._selected)
            return
        ranked = []
        for node, box in boxes.items():
            dx = box.x + box.width / 2 - origin.x - origin.width / 2
            dy = box.center_y - origin.center_y
            primary, perpendicular = {
                'up': (-dy, abs(dx)), 'down': (dy, abs(dx)),
            }[direction]
            if primary <= 1.0:
                continue
            ranked.append((primary + perpendicular * 0.35, perpendicular / primary,
                           box.x, node.id))
        if ranked:
            self.select(min(ranked)[-1], 'add' if extend else 'replace')
        self.revealNode.emit(self._selected)

    def _commit(self, mutation, tab_state=None):
        before = self.to_dict()
        previous_ids = {n.id for n in self.map.walk()}
        selected = self._selection_state()
        try:
            mutation()
            self.map.validate()
            live = {n.id for n in self.map.walk()}
            self._completed.intersection_update(live)
            self._measure_progress.intersection_update(live)
            self._bookmarks = [key for key in self._bookmarks if key in live]
            self.reminders = {key: value for key, value in self.reminders.items() if key in live}
        except (ValueError, IndexError) as exc:
            self.map, self.links = self.decode(before)
            self._completed = set(before.get('completed', []))
            self._measure_progress = set(before.get('measure_progress', []))
            self.reminders = copy.deepcopy(before.get('reminders', {}))
            self._bookmarks = list(before.get('bookmarks', []))
            self._restore_selection(selected)
            self.errorOccurred.emit(str(exc))
            self.changed.emit()
            return False
        if self.to_dict() != before:
            self._undo.append((before, selected, tab_state))
            self._redo.clear()
        retained = self._priority_nodes()
        if any(n.id not in previous_ids and n not in retained for n in self.map.walk()):
            self._priority_filter = 1.0
        self._sync_filter_selection()
        self.sceneChanged.emit()
        self.changed.emit()
        return True

    def add_siblings(self, parent_id, titles):
        """Append actions vertically under one parent as a single undoable edit."""
        parent = self.map.find(parent_id)
        if parent is None or not self._in_scope(parent) or not titles:
            return []
        if any(not isinstance(title, str) or not title.strip() for title in titles):
            return []
        created = []

        def mutate():
            parent.folded = False
            for title in titles:
                # Keep the group together when the parent is the scoped view root.
                created.append(parent.add_child(title.strip(), side='right').id)
            self._set_selection([created[0]])

        if not self._commit(mutate):
            return []
        self.revealNode.emit(created[0])
        return created

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

    @Slot(float, float, result=bool)
    def addThoughtAt(self, x, y):
        """Infer a parent and insertion position from a visible canvas point."""
        if not math.isfinite(x) or not math.isfinite(y):
            return False
        boxes = self._layout()
        if any(b.x <= x <= b.x + b.width and b.y <= y <= b.y + b.height
               for b in boxes.values()):
            return False
        sides = assigned_sides(SimpleNamespace(root=self.view_root))
        groups = {}
        for node in boxes:
            if node is not self.view_root:
                groups.setdefault((node.parent, sides[node]), []).append(node)

        gaps = []
        for (parent, side), siblings in groups.items():
            for upper, lower in zip(siblings, siblings[1:]):
                a, b = boxes[upper], boxes[lower]
                left, right = min(a.x, b.x), max(a.x + a.width, b.x + b.width)
                top, bottom = a.y + a.height, b.y
                if left <= x <= right and top < y < bottom:
                    distance = (x - (left + right) / 2) ** 2 + (y - (top + bottom) / 2) ** 2
                    gaps.append((distance, parent, side, parent.children.index(lower)))
        if gaps:
            _, parent, side, index = min(gaps, key=lambda gap: gap[0])
        else:
            def distance(node):
                b = boxes[node]
                return max(b.x - x, 0, x - b.x - b.width) ** 2 + max(b.y - y, 0, y - b.y - b.height) ** 2

            nearest = min(boxes, key=distance)
            b = boxes[nearest]
            side = sides.get(nearest, 'left' if x < b.x + b.width / 2 else 'right')
            outward = x < b.x if side == 'left' else x > b.x + b.width
            parent = nearest if nearest is self.view_root or outward else nearest.parent
            siblings = groups.get((parent, side), [])
            following = next((n for n in siblings if boxes[n].center_y > y), None)
            index = (parent.children.index(following) if following else
                     parent.children.index(siblings[-1]) + 1 if siblings else len(parent.children))

        def mutate():
            # Inserting a branch must not rebalance existing automatic sides.
            for branch in self.view_root.children:
                branch.side = sides[branch]
            parent.folded = False
            node = parent.add_child('New thought', side=side)
            node.move_to(parent, index)
            self._set_selection([node.id])

        if not self._commit(mutate):
            return False
        self.revealNode.emit(self._selected)
        return True

    @Slot(str, bool, result=bool)
    def addSiblingRelative(self, node_id, before):
        target = self.map.find(node_id)
        if not self._in_scope(target) or target is self.view_root:
            return False
        parent = target.parent
        index = parent.children.index(target) + (0 if before else 1)
        sides = assigned_sides(SimpleNamespace(root=self.view_root))

        def mutate():
            for branch in self.view_root.children:
                branch.side = sides[branch]
            parent.folded = False
            node = parent.add_child('New thought', side=sides[target])
            node.move_to(parent, index)
            self._set_selection([node.id])

        if not self._commit(mutate):
            return False
        self.clearSearch()
        self.revealNode.emit(self._selected)
        return True

    @Slot()
    def toggleBold(self):
        nodes = [self.map.find(key) for key in self._selected_ids]
        nodes = [node for node in nodes if self._in_scope(node)]
        if not nodes:
            return
        bold = not all(node.style.bold for node in nodes)

        def mutate():
            for node in nodes:
                node.style.bold = bold
                node.touch()

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
            if self._commit(lambda: setattr(node, 'side', side)):
                self.revealNode.emit(node.id)

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
        self._measure_progress = set(payload.get('measure_progress', []))
        self.reminders = copy.deepcopy(payload.get('reminders', {}))
        self._bookmarks = list(payload.get('bookmarks', []))
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
