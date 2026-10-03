"""Editable causal DAGs. Likelihoods are annotations, not an inference engine."""
from __future__ import annotations

import copy
import json
import math
import uuid
import weakref

from PySide6.QtCore import QObject, Property, Signal, Slot


def empty_causal_model_state():
    return dict(version=1, nodes=[], edges=[], description='', action_order=[], last_imported_signature='')


def _reachable(edges, start, target):
    pending, seen = [start], set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            pending.extend(e['target'] for e in edges if e['source'] == node)
    return False


def normalize_causal_model_state(value):
    state = empty_causal_model_state()
    if not isinstance(value, dict):
        return state
    for raw in value.get('nodes', []) if isinstance(value.get('nodes'), list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            node = dict(id=str(raw['id']), type=str(raw['type']), label=str(raw['label']).strip(),
                        x=float(raw.get('x', 0)), y=float(raw.get('y', 0)), notes=str(raw.get('notes', '')))
        except (KeyError, ValueError, TypeError):
            continue
        if (node['id'] and node['label'] and node['type'] in {'variable', 'action', 'outcome'}
                and all(math.isfinite(node[k]) and node[k] >= 0 for k in ('x', 'y'))
                and not any(n['id'] == node['id'] for n in state['nodes'])):
            state['nodes'].append(node)
    ids = {n['id'] for n in state['nodes']}
    for raw in value.get('edges', []) if isinstance(value.get('edges'), list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            edge = dict(id=str(raw['id']), source=str(raw['source']), target=str(raw['target']),
                        likelihood=None if raw.get('likelihood') is None else float(raw['likelihood']),
                        notes=str(raw.get('notes', '')))
        except (KeyError, ValueError, TypeError):
            continue
        weight = edge['likelihood']
        if (not edge['id'] or edge['source'] not in ids or edge['target'] not in ids
                or edge['source'] == edge['target']
                or (weight is not None and (not math.isfinite(weight) or not 0 <= weight <= 100))
                or any(e['id'] == edge['id'] or (e['source'], e['target']) == (edge['source'], edge['target']) for e in state['edges'])
                or _reachable(state['edges'], edge['target'], edge['source'])):
            continue
        state['edges'].append(edge)
    actions = [n['id'] for n in state['nodes'] if n['type'] == 'action']
    order = value.get('action_order', [])
    for key in (order if isinstance(order, list) else []) + actions:
        if key in actions and key not in state['action_order']:
            state['action_order'].append(key)
    state['description'] = str(value.get('description', ''))
    state['last_imported_signature'] = str(value.get('last_imported_signature', ''))
    return state


class CausalModelModel(QObject):
    changed = Signal()
    stateChanged = Signal()
    sceneChanged = Signal()
    resetView = Signal()
    errorChanged = Signal()

    def __init__(self, tab_model=None):
        super().__init__()
        self._tabs = weakref.proxy(tab_model) if tab_model is not None else None
        self._state = empty_causal_model_state()
        self._undo, self._redo = [], []
        self._drag = None
        self._error = ''
        if tab_model is not None:
            tab_model.currentTabChanged.connect(self.loadCurrentTab)
            tab_model.modelReset.connect(self.loadCurrentTab)
            self.loadCurrentTab()

    def _fail(self, message):
        self._error = message
        self.errorChanged.emit()
        return False

    def _signature(self):
        return json.dumps([(n['id'], n['label']) for n in self.actions], ensure_ascii=False)

    def _current_tab(self):
        if self._tabs is None:
            return None
        try:
            if self._tabs.currentTabIndex < 0:
                return None
            return self._tabs.getCurrentTabData()
        except (IndexError, ReferenceError):
            # No active tab during a reset, or the owning model was released.
            return None

    def _publish(self):
        tab = self._current_tab()
        if tab is not None:
            tab.causal_model = self.to_dict()
        if self._drag is None:
            self.changed.emit()
        self.sceneChanged.emit()
        self.stateChanged.emit()

    def _commit(self, before):
        if before == self._state:
            return
        self._undo.append(before)
        self._undo = self._undo[-100:]
        self._redo.clear()
        self._error = ''
        self.errorChanged.emit()
        self._publish()

    @Property('QVariantList', notify=changed)
    def nodes(self):
        return copy.deepcopy(self._state['nodes'])

    @Property('QVariantList', notify=changed)
    def edges(self):
        return copy.deepcopy(self._state['edges'])

    @Property('QVariantList', notify=changed)
    def actions(self):
        lookup = {n['id']: n for n in self._state['nodes']}
        return [dict(lookup[key], order=i + 1) for i, key in enumerate(self._state['action_order'])]

    @Property('QStringList', notify=changed)
    def orderedTitles(self):
        return [n['label'] for n in self.actions]

    @Property(str, notify=changed)
    def description(self):
        return self._state['description']

    @Property(str, notify=errorChanged)
    def validationError(self):
        return self._error

    @Property(bool, notify=changed)
    def canUndo(self):
        return bool(self._undo)

    @Property(bool, notify=changed)
    def canRedo(self):
        return bool(self._redo)

    @Property(bool, notify=changed)
    def imported(self):
        return bool(self.actions) and self._signature() == self._state['last_imported_signature']

    @Slot(str, str, float, float, result=str)
    @Slot(str, str, float, float, str, result=str)
    def addNode(self, label, kind, x, y, notes=""):
        if not label.strip() or kind not in {'variable', 'action', 'outcome'} or not all(math.isfinite(v) and v >= 0 for v in (x, y)):
            self._fail('Enter a label, valid node type, and nonnegative position.')
            return ''
        before = self.to_dict()
        key = str(uuid.uuid4())
        self._state['nodes'].append(dict(id=key, label=label.strip(), type=kind, x=x, y=y, notes=notes))
        if kind == 'action':
            self._state['action_order'].append(key)
        self._commit(before)
        return key

    @Slot(str, str, str, str, result=bool)
    def editNode(self, key, label, kind, notes):
        node = next((n for n in self._state['nodes'] if n['id'] == key), None)
        if node is None or not label.strip() or kind not in {'variable', 'action', 'outcome'}:
            return self._fail('Select a node and enter a label and valid type.')
        before = self.to_dict()
        node.update(label=label.strip(), type=kind, notes=notes)
        order = self._state['action_order']
        if kind == 'action' and key not in order:
            order.append(key)
        elif kind != 'action' and key in order:
            order.remove(key)
        self._commit(before)
        return True

    @Slot(str)
    def removeNode(self, key):
        before = self.to_dict()
        self._state['nodes'] = [n for n in self._state['nodes'] if n['id'] != key]
        self._state['edges'] = [e for e in self._state['edges'] if key not in (e['source'], e['target'])]
        self._state['action_order'] = [k for k in self._state['action_order'] if k != key]
        self._commit(before)

    @Slot()
    def beginNodeDrag(self):
        self._drag = self.to_dict()

    @Slot(str, float, float)
    def moveNode(self, key, x, y):
        node = next((n for n in self._state['nodes'] if n['id'] == key), None)
        if node is None or not all(math.isfinite(v) for v in (x, y)):
            return
        before = self.to_dict()
        node.update(x=max(0, x), y=max(0, y))
        if self._drag is None:
            self._commit(before)
        else:
            self._publish()

    @Slot()
    def endNodeDrag(self):
        if self._drag is not None:
            before, self._drag = self._drag, None
            self._commit(before)

    def _weight(self, text):
        if not str(text).strip():
            return None
        weight = float(text)
        if not math.isfinite(weight) or not 0 <= weight <= 100:
            raise ValueError()
        return weight

    @Slot(str, str, str, str, result=str)
    def addEdge(self, source, target, likelihood, notes):
        ids = {n['id'] for n in self._state['nodes']}
        if source not in ids or target not in ids:
            self._fail('Select two existing nodes.')
            return ''
        if source == target:
            self._fail('A node cannot cause itself.')
            return ''
        if any((e['source'], e['target']) == (source, target) for e in self._state['edges']):
            self._fail('This connection already exists.')
            return ''
        if _reachable(self._state['edges'], target, source):
            self._fail('This connection would create a cycle. Use separate nodes for successive times.')
            return ''
        try:
            weight = self._weight(likelihood)
        except (TypeError, ValueError):
            self._fail('Likelihood must be blank or a number from 0 to 100.')
            return ''
        before = self.to_dict()
        key = str(uuid.uuid4())
        self._state['edges'].append(dict(id=key, source=source, target=target, likelihood=weight, notes=notes))
        self._commit(before)
        return key

    @Slot(str, str, str, result=bool)
    def editEdge(self, key, likelihood, notes):
        edge = next((e for e in self._state['edges'] if e['id'] == key), None)
        if edge is None:
            return self._fail('Select an existing connection.')
        try:
            weight = self._weight(likelihood)
        except (TypeError, ValueError):
            return self._fail('Likelihood must be blank or a number from 0 to 100.')
        before = self.to_dict()
        edge.update(likelihood=weight, notes=notes)
        self._commit(before)
        return True

    @Slot(str)
    def removeEdge(self, key):
        before = self.to_dict()
        self._state['edges'] = [e for e in self._state['edges'] if e['id'] != key]
        self._commit(before)

    @Slot(int, int)
    def moveAction(self, source, target):
        order = self._state['action_order']
        if not (0 <= source < len(order) and 0 <= target < len(order)):
            return
        before = self.to_dict()
        order.insert(target, order.pop(source))
        self._commit(before)

    @Slot(str)
    def setDescription(self, text):
        before = self.to_dict()
        self._state['description'] = text
        self._commit(before)

    @Slot()
    def markImported(self):
        if self.actions:
            self._state['last_imported_signature'] = self._signature()
            # Import bookkeeping must survive graph undo without enabling duplicate imports.
            for snapshot in self._undo + self._redo:
                snapshot['last_imported_signature'] = self._state['last_imported_signature']
            self._publish()

    @Slot()
    def undo(self):
        self.endNodeDrag()
        if self._undo:
            self._redo.append(self.to_dict())
            self._state = self._undo.pop()
            self._publish()

    @Slot()
    def redo(self):
        if self._redo:
            self._undo.append(self.to_dict())
            self._state = self._redo.pop()
            self._publish()

    def to_dict(self):
        return copy.deepcopy(self._state)

    def from_dict(self, value):
        self._state = normalize_causal_model_state(value)
        self._undo.clear()
        self._redo.clear()
        self._drag = None
        self._error = ''
        self.errorChanged.emit()
        self.resetView.emit()
        self.changed.emit()

    @Slot()
    def loadCurrentTab(self):
        self.from_dict(getattr(self._current_tab(), 'causal_model', None))
