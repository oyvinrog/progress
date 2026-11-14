"""Plain thought names and transactional Markdown notes for mindmap nodes.

The rich editor, image tools and table tools are adapted from Mark; this module
adds project ownership, wiki-link identity and navigation without file dialogs.
"""
from __future__ import annotations

import copy
from hashlib import sha256
import re
import uuid

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFrame, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QLabel, QToolBar, QToolButton, QVBoxLayout)

from ._vendor.mark import Note
from . import mindmap_markdown as md
from .theme import build_actiondraw_palette


def qt_position(text, offset):
    return len(text[:offset].encode('utf-16-le')) // 2


def py_position(text, offset):
    return len(text.encode('utf-16-le')[:offset * 2].decode('utf-16-le', errors='ignore'))


class LinkPicker(QFrame):
    def __init__(self, note):
        super().__init__(note.window, Qt.WindowType.Popup)
        self.note = note
        self.setObjectName('mindmapLinkPicker')
        self.setPalette(build_actiondraw_palette())
        self.resize(520, 300)
        layout = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setPlaceholderText('Search nodes throughout this project')
        self.query.setAccessibleName('Search nodes')
        self.results = QListWidget()
        layout.addWidget(self.query)
        layout.addWidget(self.results)
        self.query.textChanged.connect(self.refresh)
        self.results.itemClicked.connect(self.choose)
        self.query.installEventFilter(self)
        self.results.installEventFilter(self)

    def refresh(self, text):
        self.results.clear()
        for candidate in self.note.controller.searchNodeLinks(text):
            item = QListWidgetItem(candidate['name'] + '\n' + candidate['path'])
            item.setData(Qt.ItemDataRole.UserRole, candidate)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)
        else:
            item = QListWidgetItem('No matching nodes')
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)

    def open(self, query=''):
        self.query.setText(query)
        self.refresh(query)
        surface = self.note.editor if self.note.mode == 'wysiwyg' else self.note.source
        self.move(surface.mapToGlobal(surface.cursorRect().bottomLeft() + QPoint(0, 8)))
        self.show()
        self.query.setFocus()
        self.query.setCursorPosition(len(query))

    def choose(self, item=None):
        item = item or self.results.currentItem()
        candidate = item.data(Qt.ItemDataRole.UserRole) if item else None
        if candidate:
            self.hide()
            self.note.insert_node_link(candidate)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.choose()
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                self.note.active_surface().setFocus()
                return True
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                delta = 1 if event.key() == Qt.Key.Key_Down else -1
                self.results.setCurrentRow(max(0, min(self.results.count() - 1,
                                                      self.results.currentRow() + delta)))
                return True
        return super().eventFilter(obj, event)


class EditorEvents(QObject):
    def __init__(self, note):
        super().__init__(note.window)
        self.note = note

    def eventFilter(self, obj, event):
        note = self.note
        if event.type() == QEvent.Type.MouseButtonRelease and obj is note.editor.viewport():
            if event.button() == Qt.MouseButton.LeftButton:
                href = note.editor.anchorAt(event.position().toPoint())
                if href and not note.editor.textCursor().hasSelection():
                    note.follow(href)
                    return True
        return False


class NodeNote(Note):
    def __init__(self, controller, dialog):
        self.controller = controller
        self.dialog = dialog
        self.bindings = []
        self._binding_source = ''
        self._binding_versions = {}
        self._targets = {}
        self._link_labels = {}
        self._replace_cursor = None
        self._completion_generation = 0
        super().__init__(show=False, mode='wysiwyg')
        self.window.setWindowFlags(Qt.WindowType.Widget)
        self.window.statusBar().hide()
        self._modes['wysiwyg'].setText('Rich text')
        self._modes['split'].setText('Split preview')
        self.editor.document().setDefaultStyleSheet('h1,h2,h3 {color:#e2e8f0;} a {color:#60a5fa;}')
        self.picker = LinkPicker(self)
        self.events = EditorEvents(self)
        self.editor.viewport().installEventFilter(self.events)
        self.source.document().contentsChange.connect(self.source_range_changed)
        self.source.textChanged.connect(self.maybe_complete)
        self.editor.textChanged.connect(self.maybe_complete)
        # Retain all formatting/table tools, but saving is owned by the project.
        for action in self.window.findChildren(QAction):
            if not action.shortcut().isEmpty():
                self.window.addAction(action)
                action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            if action.text() in ('Save', 'Save as'):
                action.setVisible(False)
                action.setEnabled(False)
                action.setShortcut('')
        tools = QToolBar('Node links')
        self.window.addToolBar(tools)
        tools.addAction('Insert node link', self.choose_link)
        tools.addAction('Inline code', self.inline_code)
        tools.addAction('Code block', lambda: self._insert('\n```\ncode\n```\n'))

    @staticmethod
    def _style_table(table):
        Note._style_table(table)
        for row in range(table.rows()):
            for column in range(table.columns()):
                cell = table.cellAt(row, column)
                fmt = cell.format().toTableCellFormat()
                fmt.setBackground(QColor('#243447' if row == 0 else '#111826'))
                cell.setFormat(fmt)

    def active_surface(self):
        return self.editor if self.mode == 'wysiwyg' else self.source

    def load_draft(self, text, bindings):
        self._binding_versions = {}
        self._targets = {}
        self._embedded_images.clear()
        self.bindings = md.reconcile(text, text, bindings, self.controller._resolve_text_name)
        self._binding_source = text
        # The upstream setter intentionally skips equal text; a different node
        # can have identical source and different link targets.
        self._markdown = text
        self._syncing = True
        try:
            self.source.setPlainText(text)
            self._render(text)
        finally:
            self._syncing = False
        self.set_mode('wysiwyg')
        self._saved = text

    def _render(self, markdown):
        source_key = sha256(markdown.encode()).digest()
        self.bindings = copy.deepcopy(self._binding_versions[source_key]) if source_key in self._binding_versions else md.reconcile(
            self._binding_source, markdown, self.bindings, self.controller._resolve_text_name)
        self._binding_versions[source_key] = copy.deepcopy(self.bindings)
        self._targets.update({b["id"]: b["target"] for b in self.bindings})
        self._binding_source = markdown
        self._link_labels = {b['id']: markdown[b['start'] + 2:b['end'] - 2] for b in self.bindings}
        super()._render(md.prepare(markdown, self.bindings))
        # Keep broken links clickable for repair, with a visible error colour.
        doc = self.editor.document()
        block = doc.begin()
        by_id = {b['id']: b for b in self.bindings}
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid():
                    fmt = fragment.charFormat()
                    binding = by_id.get(fmt.anchorHref().removeprefix('mindmap:'))
                    if fmt.isAnchor():
                        cursor = QTextCursor(doc)
                        cursor.setPosition(fragment.position())
                        cursor.setPosition(fragment.position() + fragment.length(), QTextCursor.MoveMode.KeepAnchor)
                        unresolved = binding and not self.controller.map.find(binding['target'] or '')
                        fmt.setForeground(QColor('#f2ad65' if unresolved else '#60a5fa'))
                        fmt.setToolTip('Unresolved node link — click to choose a node' if unresolved else fmt.anchorHref())
                        cursor.setCharFormat(fmt)
                it += 1
            block = block.next()
        doc.clearUndoRedoStacks()

    def _rich_markdown(self):
        doc = self.editor.document().clone()
        anchors = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                fragment = it.fragment()
                if fragment.isValid() and fragment.charFormat().anchorHref().startswith('mindmap:'):
                    key = fragment.charFormat().anchorHref()[8:]
                    if anchors and anchors[-1][0] + anchors[-1][1] == fragment.position() and anchors[-1][2] == key:
                        anchors[-1][1] += fragment.length()
                        anchors[-1][3] += fragment.text()
                    else:
                        anchors.append([fragment.position(), fragment.length(), key, fragment.text()])
                it += 1
            block = block.next()
        replacements = []
        for pos, length, key, label in reversed(anchors):
            marker = 'NODELINK' + uuid.uuid4().hex.upper()
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(marker, QTextCharFormat())
            replacements.append((marker, key, label))
        result = super()._rich_markdown(doc).rstrip('\n')
        self._targets.update({b['id']: b['target'] for b in self.bindings})
        new = []
        # Work left-to-right so offsets refer to the final source string.
        for marker, key, label in sorted(replacements, key=lambda item: result.index(item[0])):
            start = result.index(marker)
            token = '[[' + label + ']]'
            result = result[:start] + token + result[start + len(marker):]
            target = self._targets.get(key)
            if any(b['id'] == key for b in new):
                key = uuid.uuid4().hex
                self._targets[key] = target
            new.append({'start': start, 'end': start + len(token), 'id': key,
                        'target': target})
        self.bindings = md.reconcile(result, result, new, self.controller._resolve_text_name)
        self._binding_source = result
        self._binding_versions[sha256(result.encode()).digest()] = copy.deepcopy(self.bindings)
        return result

    def source_range_changed(self, position, removed, added):
        if self._syncing:
            return
        old, new = self._binding_source, self.source.toPlainText()
        start = py_position(old, position)
        end = py_position(old, position + removed)
        inserted = py_position(new, position + added) - py_position(new, position)
        delta = inserted - (end - start)
        carried = []
        for binding in self.bindings:
            item = dict(binding)
            if item['end'] <= start:
                carried.append(item)
            elif item['start'] >= end:
                item['start'] += delta
                item['end'] += delta
                carried.append(item)
        self.bindings = md.reconcile(new, new, carried, self.controller._resolve_text_name)
        self._binding_source = new

    def maybe_complete(self):
        self._completion_generation += 1
        generation = self._completion_generation
        if self._syncing or not hasattr(self, 'picker') or self.picker.isVisible():
            return
        surface = self.active_surface()
        cursor = surface.textCursor()
        prefix = cursor.block().text()[:py_position(cursor.block().text(), cursor.positionInBlock())]
        match = re.search(r'(?<!\\)\[\[([^\]\n]*)$', prefix)
        if not match:
            return
        if self.mode == 'wysiwyg' and (cursor.charFormat().fontFixedPitch() or cursor.blockFormat().nonBreakableLines()):
            return
        if self.mode != 'wysiwyg':
            offset = py_position(self.source.toPlainText(), cursor.position())
            suffix = 'x]]' if not match.group(1) else ']]'
            proposed = self.source.toPlainText()[:offset] + suffix + self.source.toPlainText()[offset:]
            if not any(m.end() == offset + len(suffix) for m in md.tokens(proposed)):
                return
        cursor.setPosition(cursor.position() - qt_position(match.group(0), len(match.group(0))), QTextCursor.MoveMode.KeepAnchor)
        self._replace_cursor = cursor
        QTimer.singleShot(0, lambda: self.picker.open(match.group(1))
                          if self.dialog.isVisible() and generation == self._completion_generation else None)

    def choose_link(self):
        self._replace_cursor = self.active_surface().textCursor()
        self.picker.open()

    def choose_existing(self, start):
        self.set_mode('source')
        cursor = self.source.textCursor()
        token = next((m for m in md.tokens(self.markdown) if m.start() == start), None)
        if token:
            cursor.setPosition(qt_position(self.markdown, token.start()))
            cursor.setPosition(qt_position(self.markdown, token.end()), QTextCursor.MoveMode.KeepAnchor)
            self.source.setTextCursor(cursor)
            self._replace_cursor = cursor
            self.picker.open(token.group(1))

    def insert_node_link(self, candidate):
        cursor = self._replace_cursor or self.active_surface().textCursor()
        label = candidate['name'].replace(']', '').replace('\n', ' ')
        key = uuid.uuid4().hex
        if self.mode == 'wysiwyg':
            self.bindings.append({'start': -1, 'end': -1, 'id': key, 'target': candidate['id']})
            fmt = QTextCharFormat()
            fmt.setAnchor(True)
            fmt.setAnchorHref('mindmap:' + key)
            fmt.setForeground(QColor('#60a5fa'))
            fmt.setFontUnderline(True)
            cursor.insertText(label, fmt)
            self.editor.setTextCursor(cursor)
            self.editor.setCurrentCharFormat(QTextCharFormat())
        else:
            start = py_position(self.markdown, cursor.selectionStart())
            cursor.insertText('[[' + label + ']]')
            for binding in self.bindings:
                if binding['start'] == start:
                    binding['target'] = candidate['id']
                    binding['id'] = key
            self._binding_versions[sha256(self.markdown.encode()).digest()] = copy.deepcopy(self.bindings)
            self._syncing = True
            try:
                self._render(self.markdown)
            finally:
                self._syncing = False
            self.source.setTextCursor(cursor)
        self._replace_cursor = None
        self.active_surface().setFocus()

    def inline_code(self):
        if self.mode != 'wysiwyg':
            self._insert('`code`')
            return
        fmt = QTextCharFormat()
        fmt.setFontFixedPitch(True)
        fmt.setFontFamilies(['monospace'])
        self.editor.mergeCurrentCharFormat(fmt)

    def follow(self, href):
        if not href.startswith('mindmap:'):
            if QUrl(href).scheme() in ('http', 'https', 'mailto'):
                QDesktopServices.openUrl(QUrl(href))
            return
        binding = next((b for b in self.bindings if 'mindmap:' + b['id'] == href), None)
        if not binding:
            return
        if not binding['target']:
            self.choose_existing(binding['start'])
        elif self.controller.map.find(binding['target']) is None:
            self.controller.errorOccurred.emit('This linked node no longer exists.')
            self.choose_existing(binding['start'])
        else:
            self.dialog.navigate(binding['target'])


class MindMapNodeEditor(QDialog):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setObjectName('mindmapNodeEditor')
        self.setWindowTitle('Thought and notes')
        self.setPalette(build_actiondraw_palette())
        self.setModal(True)
        self.title = QLineEdit()
        self.title.setObjectName('mindmapNodeTitle')
        self.title.setPlaceholderText('Thought')
        self.title.setAccessibleName('Thought')
        self.title.returnPressed.connect(self.accept)
        self.notes = NodeNote(controller, self)
        self.notes.editor.setObjectName('mindmapNodeNotes')
        self.notes_toggle = QToolButton()
        self.notes_toggle.setObjectName('mindmapNotesToggle')
        self.notes_toggle.setCheckable(True)
        self.notes_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.notes_toggle.toggled.connect(self.set_notes_expanded)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        title_label = QLabel('Thought')
        title_label.setBuddy(self.title)
        layout.addWidget(title_label)
        layout.addWidget(self.title)
        layout.addWidget(self.notes_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.notes.window, 1)
        layout.addWidget(buttons)
        self._return_window = None
        self.node_id = ''
        self.original = None
        controller.loading.connect(self.clear_project)
        save = QAction(self)
        save.setShortcut('Ctrl+S')
        save.triggered.connect(self.accept)
        self.addAction(save)
        accept = QAction(self)
        accept.setShortcut('Ctrl+Return')
        accept.triggered.connect(self.accept)
        self.addAction(accept)
        self.set_notes_expanded(False)

    def set_notes_expanded(self, expanded):
        self.notes_toggle.blockSignals(True)
        self.notes_toggle.setChecked(expanded)
        self.notes_toggle.blockSignals(False)
        self.notes_toggle.setText('Hide notes' if expanded else 'Add notes')
        self.notes_toggle.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.notes.window.setVisible(expanded)
        if not expanded:
            self.notes.picker.hide()
        self.layout().invalidate()
        self.layout().activate()
        available = self.screen().availableGeometry()
        # Leave room for the native window frame as well as the client area.
        width = min(1050 if expanded else 520, available.width() - 40)
        height = min(760 if expanded else self.sizeHint().height(), available.height() - 80)
        self.resize(width, height)
        if self.isVisible():
            frame = self.frameGeometry()
            self.move(max(available.left(), min(frame.left(), available.right() - frame.width() + 1)),
                      max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)))
            (self.notes.active_surface() if expanded else self.title).setFocus()

    def clear_project(self):
        self.reject()
        self.node_id = ''
        self.original = None
        self.title.clear()
        self.notes.load_draft('', [])

    def open_node(self, node):
        self._return_window = QGuiApplication.focusWindow()
        self.winId()
        if self._return_window is not self.windowHandle():
            self.windowHandle().setTransientParent(self._return_window)
        self.node_id = node.id
        fields = self.controller.text_links.get(node.id, {})
        self.title.setText(node.text)
        self.notes.load_draft(node.note or '', fields.get('note', []))
        self.original = self.draft()
        self.set_notes_expanded(bool((node.note or '').strip()))
        self.show()
        self.raise_()
        self.activateWindow()
        self.title.setFocus()
        self.title.selectAll()

    def draft(self):
        return (self.title.text(), self.notes.markdown,
                {'note': copy.deepcopy(self.notes.bindings)})

    def accept(self):
        if self.controller.map.find(self.node_id) is None:
            self.controller.errorOccurred.emit('This node no longer exists.')
            return
        text, note, bindings = self.draft()
        if self.controller.editNode(self.node_id, text, note, bindings):
            super().accept()

    def done(self, result):
        self.notes.picker.hide()
        super().done(result)
        import shiboken6
        if self._return_window is not None and shiboken6.isValid(self._return_window):
            self._return_window.requestActivate()

    def navigate(self, target):
        if self.draft() != self.original:
            choice = QMessageBox(self)
            choice.setWindowTitle('Unsaved changes')
            choice.setText('Save this node before following the link?')
            save = choice.addButton('Save and navigate', QMessageBox.ButtonRole.AcceptRole)
            discard = choice.addButton('Discard and navigate', QMessageBox.ButtonRole.DestructiveRole)
            choice.addButton(QMessageBox.StandardButton.Cancel)
            choice.exec()
            if choice.clickedButton() is save:
                self.accept()
                if self.isVisible():
                    return
            elif choice.clickedButton() is discard:
                self.reject()
            else:
                return
        else:
            self.reject()
        self.controller.revealTextLink(target)
