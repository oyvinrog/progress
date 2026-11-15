"""Programmable native Markdown notes. See README.md for the public API."""
from __future__ import annotations

import hashlib
import base64
import argparse
import html
from html.parser import HTMLParser
import re
import sys
import threading
import uuid
from pathlib import Path
from typing import Callable, Iterable

from PySide6.QtCore import QUrl, QBuffer, QIODevice, Qt, QMimeData, QRectF
from PySide6.QtGui import QAction, QFont, QTextCharFormat, QTextCursor, QTextImageFormat, QImage, QPixmap, QTextDocument, QTextTable, QTextFrameFormat, QColor, QTextListFormat, QTextFormat, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QInputDialog, QMainWindow, QMessageBox,
    QPlainTextEdit, QSplitter, QTextEdit, QToolBar, QComboBox,
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QLabel, QToolButton,
)

__all__ = ['Note', 'run']
_app = None


def _application():
    global _app
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('Create and edit Notes on the main GUI thread.')
    _app = QApplication.instance() or QApplication(sys.argv[:1])
    return _app


def run() -> int:
    """Run Qt's event loop once, after constructing your notes."""
    return _application().exec()


def _image_tag(src, alt='', width=None, height=None):
    attrs = {'src': str(src), 'alt': alt}
    for name, value in [('width', width), ('height', height)]:
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f'{name} must be a positive pixel size')
            attrs[name] = f'{value:g}'
    return '<img ' + ' '.join(f'{k}="{html.escape(str(v), quote=True)}"' for k, v in attrs.items()) + '>'


def _clipboard_image(mime):
    if mime.hasImage():
        data = mime.imageData()
        if isinstance(data, QPixmap):
            data = data.toImage()
        if isinstance(data, QImage) and not data.isNull():
            return data
    if mime.hasUrls():
        for url in mime.urls():
            if url.isLocalFile():
                image = QImage(url.toLocalFile())
                if not image.isNull():
                    return image
    return None


class _PasteImages:
    def canInsertFromMimeData(self, mime):
        return _clipboard_image(mime) is not None or super().canInsertFromMimeData(mime)

    def insertFromMimeData(self, mime):
        image = _clipboard_image(mime)
        if image is None:
            super().insertFromMimeData(mime)
            return
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, 'PNG')
        src = 'data:image/png;base64,' + base64.b64encode(bytes(buffer.data())).decode('ascii')
        width = min(image.width(), 640)
        height = round(image.height() * width / image.width())
        if isinstance(self, QTextEdit):
            src = self.note._register_image(src, image)
            fmt = QTextImageFormat()
            fmt.setName(src)
            fmt.setWidth(width)
            fmt.setHeight(height)
            self.textCursor().insertImage(fmt)
        else:
            self.insertPlainText(_image_tag(src, 'Pasted image', width, height) + '\n\n')


class _SourceEditor(_PasteImages, QPlainTextEdit):
    pass


class _ImageResizeHandle(QLabel):
    def __init__(self, editor):
        super().__init__(editor.viewport())
        self.editor = editor
        self.drag = None
        self.setFixedSize(14, 14)
        self.setStyleSheet('background: #267bba; border: 2px solid white;')
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip('Drag to resize image (keeps proportions)')
        self.setAccessibleName('Resize image by dragging')
        self.hide()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        rect = self.editor._selected_image_rect()
        if rect is None:
            return
        cursor = self.editor.note._image_cursor()
        self.drag = [event.globalPosition(), rect.width(), rect.height(), cursor, False]
        event.accept()

    def mouseMoveEvent(self, event):
        if self.drag is None:
            return
        origin, width, height, cursor, changed = self.drag
        delta = event.globalPosition() - origin
        # Project the pointer onto the image diagonal so both axes work.
        scale = max(1 / width, min(10000 / width,
            1 + (delta.x() * width + delta.y() * height) / (width * width + height * height)))
        fmt = cursor.charFormat().toImageFormat()
        if abs(fmt.width() - width * scale) < 0.01 and abs(fmt.height() - height * scale) < 0.01:
            return
        if changed:
            cursor.joinPreviousEditBlock()
        else:
            cursor.beginEditBlock()
        fmt.setWidth(width * scale)
        fmt.setHeight(height * scale)
        cursor.setCharFormat(fmt)
        cursor.endEditBlock()
        self.drag[4] = True
        self.editor.viewport().update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.drag is not None and event.button() == Qt.MouseButton.LeftButton:
            self.mouseMoveEvent(event)
            cursor = self.drag[3]
            self.drag = None
            self.editor.setTextCursor(cursor)
            self.editor.setFocus()
            event.accept()


class _RichEditor(_PasteImages, QTextEdit):
    def __init__(self):
        super().__init__()
        self._image_handle = _ImageResizeHandle(self)
        self._table_plus = []
        for label, operation in [('Add row at bottom', 'append_row'), ('Add column on right', 'append_column')]:
            button = QToolButton(self.viewport())
            button.setText('+')
            button.setFixedSize(24, 24)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setStyleSheet('QToolButton { background: #e8f3fb; color: #175b8c; border: 1px solid #267bba; border-radius: 12px; font-size: 20px; } QToolButton:hover { background: #c6e4fa; }')
            button.clicked.connect(lambda checked=False, op=operation: self.note._edit_table(op))
            button.hide()
            self._table_plus.append(button)
        self.cursorPositionChanged.connect(self.viewport().update)
        self.selectionChanged.connect(self.viewport().update)

    def _selected_image_rect(self):
        if self.isReadOnly() or self.textCursor().selectedText() != '\ufffc':
            return None
        cursor = self.note._image_cursor()
        fmt = cursor.charFormat().toImageFormat()
        image = self.note._image_data(fmt)
        width, height = fmt.width(), fmt.height()
        if not image.isNull():
            width = width or (height * image.width() / image.height() if height else image.width())
            height = height or width * image.height() / image.width()
        width, height = width or 16, height or 16
        cursor.setPosition(cursor.selectionStart())
        rect = self.cursorRect(cursor)
        block = cursor.block()
        line = block.layout().lineForTextPosition(cursor.positionInBlock())
        baseline = rect.top() + (line.ascent() if line.isValid() else rect.height())
        return QRectF(rect.left(), baseline - height, width, height)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not hasattr(self, 'note'):
            return
        rect = self._selected_image_rect()
        if rect is not None:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor('#267bba'), 1))
            painter.drawRect(rect)
            painter.end()
            self._image_handle.move(round(rect.right()) - 7, round(rect.bottom()) - 7)
            self._image_handle.show()
            self._image_handle.raise_()
        else:
            self._image_handle.hide()
        table = self.textCursor().currentTable() if not self.isReadOnly() else None
        if table is None:
            for button in self._table_plus:
                button.hide()
        else:
            bounds = self.document().documentLayout().frameBoundingRect(table)
            bounds.translate(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())
            positions = [(bounds.center().x() - 12, bounds.bottom() + 2),
                         (bounds.right() + 2, bounds.center().y() - 12)]
            for button, (x, y) in zip(self._table_plus, positions):
                button.move(round(x), round(y))
                # Do not hide/show an already visible button during repaint:
                # hiding releases its native mouse grab in the middle of a click.
                button.setVisible(self.viewport().rect().intersects(button.geometry()))
                button.raise_()

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        table = cursor.currentTable()
        if (not self.isReadOnly() and table is not None
                and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            cell = table.cellAt(cursor)
            backwards = event.key() == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            index = cell.row() * table.columns() + cell.column() + (-1 if backwards else 1)
            if index < 0:
                cursor.setPosition(table.firstPosition() - 1)
            else:
                if index >= table.rows() * table.columns():
                    cursor.beginEditBlock()
                    table.appendRows(1)
                    self.note._style_table(table)
                    cursor.endEditBlock()
                cell = table.cellAt(index // table.columns(), index % table.columns())
                cursor = cell.firstCursorPosition()
                cursor.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        try:
            cursor = self.note._image_cursor(self.cursorForPosition(event.pos()))
        except ValueError:
            cursor = None
        if cursor is not None:
            self.setTextCursor(cursor)
        menu = self.createStandardContextMenu()
        table_cursor = self.cursorForPosition(event.pos())
        if cursor is None and table_cursor.currentTable() is not None and self.note.mode == 'wysiwyg':
            self.setTextCursor(table_cursor)
            menu.addSeparator()
            for label, operation in self.note._table_commands:
                menu.addAction(label, lambda op=operation: self.note._edit_table(op))
        if cursor is not None:
            menu.addSeparator()
            resize = menu.addAction('Resize image…')
            resize.triggered.connect(self.note._resize_dialog)
        try:
            menu.exec(event.globalPos())
        finally:
            menu.deleteLater()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                self.setTextCursor(self.note._image_cursor(self.cursorForPosition(event.pos())))
                self.note.window.statusBar().showMessage('Image selected — drag the blue corner to resize, or click Resize image')
            except ValueError:
                pass

    def mouseDoubleClickEvent(self, event):
        try:
            self.setTextCursor(self.note._image_cursor(self.cursorForPosition(event.pos())))
        except ValueError:
            super().mouseDoubleClickEvent(event)
        else:
            self.note._resize_dialog()

    def createMimeDataFromSelection(self):
        original = super().createMimeDataFromSelection()
        mime = QMimeData()
        for name in original.formats():
            mime.setData(name, original.data(name))
        try:
            cursor = self.note._image_cursor(self.textCursor())
            if self.textCursor().selectedText() == '\ufffc':
                image = self.note._image_data(cursor.charFormat().toImageFormat())
                if not image.isNull():
                    mime.setImageData(image)
        except ValueError:
            pass
        return mime


class _Window(QMainWindow):
    def closeEvent(self, event):
        note = self.note
        if note.dirty and not note._force_close:
            choice = QMessageBox.question(self, 'Unsaved note', 'Save changes before closing?',
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel)
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.StandardButton.Save and not note._save_dialog():
                event.ignore()
                return
        event.accept()


class Note:
    """Create a visible editor. Mutating builder methods return self.

    Use ``show=False`` for tests. In scripts call ``Note.run()`` after setup;
    an existing Qt application can use its own event loop.
    ``source``, ``editor``, and ``window`` expose the underlying Qt widgets.
    """
    def __init__(self, title='Untitled', text='', *, path=None, mode='split', show=True):
        self.app = _application()
        self.title = title
        self.path = None
        self._markdown = ''
        self._saved = ''
        self._syncing = False
        self._force_close = False
        self._callbacks = []
        self._embedded_images = {}
        self.window = _Window()
        self.window.note = self
        self.window.resize(1080, 740)
        self.source = _SourceEditor()
        self.source.setFont(QFont('monospace', 11))
        self.source.setPlaceholderText('Write Markdown here…')
        self.editor = _RichEditor()
        self.editor.note = self
        self.editor.setFont(QFont('Sans Serif', 12))
        self.editor.setPlaceholderText('Your note starts here…')
        self.editor.document().setDocumentMargin(28)
        self.editor.document().setBaseUrl(QUrl.fromLocalFile(str(Path.cwd()) + '/'))
        self.editor.document().setDefaultStyleSheet('h1 {color:#245c50;} a {color:#267bba;}')
        self.splitter = QSplitter()
        self.splitter.addWidget(self.source)
        self.splitter.addWidget(self.editor)
        self.window.setCentralWidget(self.splitter)
        self._toolbar()
        self.source.textChanged.connect(self._source_changed)
        self.editor.textChanged.connect(self._rich_changed)
        self.editor.cursorPositionChanged.connect(self._update_format_tools)
        self.markdown = text
        if path is not None:
            self.load(path)
        self._saved = self.markdown
        self.set_mode(mode)
        self._status()
        if show:
            self.show()

    @property
    def markdown(self):
        return self._markdown

    @markdown.setter
    def markdown(self, value):
        if not isinstance(value, str):
            raise TypeError('markdown must be a string')
        if value == self._markdown:
            return
        self._markdown = value
        self._syncing = True
        try:
            self.source.setPlainText(value)
            self._render(value)
        finally:
            self._syncing = False
        self._changed()

    @property
    def dirty(self):
        return self.markdown != self._saved

    def _status(self):
        self.window.setWindowTitle(f'{"● " if self.dirty else ""}{self.title} — Mark')
        self.window.statusBar().showMessage(
            f'{len(self.markdown.split())} words · {len(self.markdown)} characters'
            + (f' · {self.path}' if self.path else ''))

    def _changed(self):
        self._status()
        for callback in tuple(self._callbacks):
            callback(self.markdown)

    def _source_changed(self):
        if self._syncing:
            return
        self._markdown = self.source.toPlainText()
        self._syncing = True
        try:
            self._render(self._markdown)
        finally:
            self._syncing = False
        self._changed()

    def _render(self, markdown):
        # Some Qt builds ignore raw HTML images in Markdown. Resolve them
        # explicitly after parsing, while keeping code examples literal.
        images = []
        class ImageParser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                self.attrs = dict(attrs)
        def substitute(match):
            raw = match.group(0)
            parser = ImageParser()
            parser.feed(raw)
            token = 'MARKIMAGE' + uuid.uuid4().hex.upper()
            images.append((token, raw, parser.attrs))
            return token
        prepared = re.sub(r'<img\b[^>]*>', substitute, markdown, flags=re.IGNORECASE)
        self.editor.setMarkdown(prepared)
        doc = self.editor.document()
        for token, raw, attrs in images:
            cursor = doc.find(token)
            if cursor.isNull():
                continue
            if cursor.charFormat().fontFixedPitch() or cursor.blockFormat().nonBreakableLines():
                cursor.insertText(raw)
                continue
            fmt = QTextImageFormat()
            fmt.setName(attrs.get('src', ''))
            fmt.setProperty(QTextCharFormat.Property.ImageAltText, attrs.get('alt', ''))
            for key, setter in [('width', fmt.setWidth), ('height', fmt.setHeight)]:
                try:
                    size = float(attrs.get(key, 0))
                    if size > 0:
                        setter(size)
                except (ValueError, TypeError):
                    pass
            image = self._image_data(fmt)
            if not image.isNull():
                if fmt.name().startswith('data:image/'):
                    fmt.setName(self._register_image(fmt.name(), image))
                else:
                    doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(fmt.name()), image)
            cursor.insertImage(fmt)
        def style_tables(frame):
            for child in frame.childFrames():
                if isinstance(child, QTextTable):
                    self._style_table(child)
                style_tables(child)
        style_tables(doc.rootFrame())
        doc.clearUndoRedoStacks()

    def _rich_markdown(self, doc=None):
        # Qt's writer drops image dimensions. Serialize image placeholders in a
        # clone, then restore HTML images, leaving the live undo stack intact.
        doc = doc if doc is not None else self.editor.document().clone()
        images = []
        block = doc.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isImageFormat():
                    fmt = fragment.charFormat().toImageFormat()
                    token = 'MARKIMAGE' + uuid.uuid4().hex.upper()
                    tag = _image_tag(self._embedded_images.get(fmt.name(), fmt.name()), fmt.stringProperty(
                        QTextCharFormat.Property.ImageAltText), fmt.width() or None, fmt.height() or None)
                    images.append((fragment.position(), fragment.length(), token, tag))
                iterator += 1
            block = block.next()
        for pos, length, token, tag in reversed(images):
            cursor = QTextCursor(doc)
            cursor.setPosition(pos)
            cursor.setPosition(pos + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(token, QTextCharFormat())
        result = doc.toMarkdown()
        for _, _, token, tag in images:
            result = result.replace(token, tag)
        return result

    def _rich_changed(self, force=False):
        if self._syncing or (self.mode != 'wysiwyg' and not force):
            return
        self._markdown = self._rich_markdown()
        self._syncing = True
        try:
            self.source.setPlainText(self._markdown)
        finally:
            self._syncing = False
        self._changed()

    def set_mode(self, mode):
        """Choose source, split (source plus preview), or wysiwyg."""
        if mode not in ('source', 'split', 'wysiwyg'):
            raise ValueError('mode must be source, split, or wysiwyg')
        self.mode = mode
        self.source.setVisible(mode != 'wysiwyg')
        self.editor.setVisible(mode != 'source')
        self.editor.setReadOnly(mode != 'wysiwyg')
        for name, action in self._modes.items():
            action.setChecked(name == mode)
        self._update_format_tools()
        return self

    def append(self, markdown):
        """Append raw Markdown exactly as supplied."""
        self.markdown += markdown
        return self

    def text(self, text):
        """Append a paragraph (Markdown syntax is accepted)."""
        return self.append(str(text) + '\n\n')

    def heading(self, text, level=1):
        if level not in range(1, 7):
            raise ValueError('heading level must be 1–6')
        return self.text('#' * level + ' ' + str(text))

    def bullet_list(self, items: Iterable[str], *, ordered=False):
        return self.text('\n'.join(f'{i}. {item}' if ordered else f'- {item}'
                                   for i, item in enumerate(items, 1)))

    def task(self, text, checked=False):
        return self.append(f'- [{"x" if checked else " "}] {text}\n')

    def quote(self, text):
        return self.text('\n'.join('> ' + line for line in str(text).splitlines()))

    def code(self, code, language=''):
        if re.search(r'[\r\n`]', language):
            raise ValueError('language must be a single fence-free line')
        fence = '`' * max(3, max((len(m) + 1 for m in re.findall(r'`+', code)), default=3))
        return self.text(f'{fence}{language}\n{code}\n{fence}')

    def link(self, label, url):
        label = str(label).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')
        url = str(url).replace('>', '%3E').replace('<', '%3C').replace('\n', '%0A')
        return self.text(f'[{label}](<{url}>)')

    def image(self, src, alt='', *, width=None, height=None):
        """Append an image; sizes are pixels. Relative paths use the note's folder."""
        return self.text(_image_tag(src, alt, width, height))

    def table(self, headers, rows):
        headers = list(headers)
        rows = [list(row) for row in rows]
        if not headers or any(len(row) != len(headers) for row in rows):
            raise ValueError('table rows must match nonempty headers')
        def line(row):
            return '| ' + ' | '.join(str(cell).replace('|', '\\|').replace('\n', '<br>') for cell in row) + ' |'
        return self.text('\n'.join([line(headers), line(['---'] * len(headers))] + [line(row) for row in rows]))

    def rule(self):
        return self.text('---')

    def clear(self):
        self.markdown = ''
        return self

    def on_change(self, callback: Callable[[str], None]):
        """Subscribe to changes; callback receives Markdown. Returns unsubscribe."""
        self._callbacks.append(callback)
        def unsubscribe():
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        return unsubscribe

    def save(self, path=None):
        target = Path(path).expanduser().resolve() if path is not None else self.path
        if target is None:
            raise ValueError('supply a path for the first save')
        target.write_text(self.markdown, encoding='utf-8')
        self.path = target
        self.title = target.stem
        self.editor.document().setBaseUrl(QUrl.fromLocalFile(str(target.parent) + '/'))
        self._saved = self.markdown
        self._status()
        return self

    def load(self, path):
        target = Path(path).expanduser().resolve()
        content = target.read_text(encoding='utf-8')
        self.path = target
        self.title = target.stem
        self.editor.document().setBaseUrl(QUrl.fromLocalFile(str(target.parent) + '/'))
        self.markdown = content
        self._saved = content
        self._status()
        return self

    def export_html(self, path):
        """Write Qt's rendered HTML (images remain external references)."""
        content = self.editor.document().toHtml()
        for name, data in self._embedded_images.items():
            content = content.replace(name, data)
        Path(path).write_text(content, encoding='utf-8')
        return self

    def show(self):
        self.window.show()
        return self

    def close(self, *, force=False):
        """Close, prompting for unsaved changes unless force=True."""
        self._force_close = force
        try:
            return self.window.close()
        finally:
            self._force_close = False

    run = staticmethod(run)

    def _save_dialog(self, save_as=False):
        path = self.path
        if save_as or path is None:
            path, _ = QFileDialog.getSaveFileName(self.window, 'Save Markdown', str(path or ''), 'Markdown (*.md)')
        if not path:
            return False
        try:
            self.save(path)
            return True
        except OSError as exc:
            QMessageBox.warning(self.window, 'Could not save', str(exc))
            return False

    def _insert(self, markdown):
        if self.mode == 'wysiwyg':
            if markdown.lstrip().startswith('<img '):
                self.editor.textCursor().insertHtml(markdown)
            else:
                self.editor.textCursor().insertMarkdown(markdown)
        else:
            self.source.insertPlainText(markdown)

    def _format(self, kind):
        if self.mode == 'wysiwyg':
            fmt = QTextCharFormat()
            current = self.editor.currentCharFormat()
            if kind == 'bold':
                fmt.setFontWeight(QFont.Weight.Normal if current.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold)
            elif kind == 'italic':
                fmt.setFontItalic(not current.fontItalic())
            else:
                fmt.setFontStrikeOut(not current.fontStrikeOut())
            self.editor.mergeCurrentCharFormat(fmt)
            self.editor.setFocus()
        else:
            cursor = self.source.textCursor()
            marker = {'bold': '**', 'italic': '*', 'strike': '~~'}[kind]
            cursor.insertText(marker + (cursor.selectedText() or kind) + marker)
            self.source.setFocus()
        self._update_format_tools()

    def _update_format_tools(self):
        if not hasattr(self, '_styles'):
            return
        rich = getattr(self, 'mode', '') == 'wysiwyg'
        fmt = self.editor.currentCharFormat()
        for kind, checked in [('bold', fmt.fontWeight() >= QFont.Weight.Bold),
                              ('italic', fmt.fontItalic()), ('strike', fmt.fontStrikeOut())]:
            self._format_actions[kind].setChecked(rich and checked)
        self._styles.blockSignals(True)
        self._styles.setCurrentIndex(self.editor.textCursor().blockFormat().headingLevel() if rich else 0)
        self._styles.blockSignals(False)
        for item in getattr(self, '_table_actions', []):
            item.setEnabled(rich and self.editor.textCursor().currentTable() is not None)

    def _insert_table_dialog(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle('Insert table')
        layout = QFormLayout(dialog)
        layout.addRow(QLabel('The first row contains column headings.'))
        rows, columns = QSpinBox(), QSpinBox()
        rows.setRange(1, 100)
        rows.setValue(3)
        columns.setRange(1, 20)
        columns.setValue(3)
        layout.addRow('Data rows', rows)
        layout.addRow('Columns', columns)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Insert table')
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._insert_table(rows.value(), columns.value())

    def _insert_table(self, rows, columns):
        if self.mode != 'wysiwyg':
            headers = '| ' + ' | '.join(f'Column {i + 1}' for i in range(columns)) + ' |'
            divider = '| ' + ' | '.join('---' for _ in range(columns)) + ' |'
            row = '| ' + ' | '.join(' ' for _ in range(columns)) + ' |'
            self._insert('\n\n' + '\n'.join([headers, divider] + [row] * rows) + '\n\n')
            self.source.setFocus()
            return
        cursor = self.editor.textCursor()
        if cursor.currentTable() is not None:
            self.window.statusBar().showMessage('Move outside the current table to insert another table.')
            return
        cursor.beginEditBlock()
        table = cursor.insertTable(rows + 1, columns)
        self._style_table(table)
        for column in range(columns):
            table.cellAt(0, column).firstCursorPosition().insertText(f'Column {column + 1}')
        cursor.endEditBlock()
        cell = table.cellAt(0, 0)
        selected = cell.firstCursorPosition()
        selected.setPosition(cell.lastCursorPosition().position(), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(selected)
        self.editor.setFocus()

    @staticmethod
    def _style_table(table):
        fmt = table.format()
        fmt.setHeaderRowCount(1)
        fmt.setBorder(1)
        fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        fmt.setBorderBrush(QColor('#82939e'))
        fmt.setBorderCollapse(True)
        fmt.setCellPadding(8)
        table.setFormat(fmt)
        for row in range(table.rows()):
            for column in range(table.columns()):
                cell = table.cellAt(row, column)
                cf = cell.format().toTableCellFormat()
                cf.setBorder(1)
                cf.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                cf.setBorderBrush(QColor('#82939e'))
                cf.setBackground(QColor('#e8eef3') if row == 0 else QColor('white'))
                cell.setFormat(cf)

    def _edit_table(self, operation):
        if self.mode != 'wysiwyg':
            return
        cursor = self.editor.textCursor()
        table = cursor.currentTable()
        if table is None:
            return
        cell = table.cellAt(cursor)
        row, column = cell.row(), cell.column()
        cursor.beginEditBlock()
        if operation == 'delete' or (operation == 'remove_row' and table.rows() == 1) or (operation == 'remove_column' and table.columns() == 1):
            cursor.setPosition(table.firstPosition() - 1)
            cursor.setPosition(table.lastPosition() + 1, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        else:
            if operation == 'append_row':
                row = table.rows()
                table.appendRows(1)
            elif operation == 'append_column':
                column = table.columns()
                table.appendColumns(1)
            elif operation == 'above':
                table.insertRows(row, 1)
            elif operation == 'below':
                row += 1
                table.insertRows(row, 1)
            elif operation == 'left':
                table.insertColumns(column, 1)
            elif operation == 'right':
                column += 1
                table.insertColumns(column, 1)
            elif operation == 'remove_row':
                table.removeRows(row, 1)
            elif operation == 'remove_column':
                table.removeColumns(column, 1)
            self._style_table(table)
            cursor.setPosition(table.cellAt(min(row, table.rows() - 1), min(column, table.columns() - 1)).firstCursorPosition().position())
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self._update_format_tools()

    def _paragraph(self, kind, level=0):
        if self.mode != 'wysiwyg':
            cursor = self.source.textCursor()
            start, end = cursor.selectionStart(), cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            start = cursor.position()
            cursor.setPosition(end)
            if end > start and cursor.atBlockStart():
                cursor.movePosition(QTextCursor.MoveOperation.PreviousCharacter)
            cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)
            cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
            lines = cursor.selectedText().split('\u2029')
            prefix = {'heading': '#' * level + ' ' if level else '', 'quote': '> ',
                      'bullet': '- ', 'number': '1. '}[kind]
            if kind == 'heading':
                lines = [re.sub(r'^#{1,6} ', '', line) for line in lines]
            cursor.insertText('\n'.join(prefix + line for line in lines))
            self.source.setFocus()
            return
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        if kind in ('bullet', 'number'):
            fmt = QTextListFormat()
            fmt.setStyle(QTextListFormat.Style.ListDisc if kind == 'bullet' else QTextListFormat.Style.ListDecimal)
            fmt.setIndent(1)
            cursor.createList(fmt)
        else:
            block = cursor.blockFormat()
            if kind == 'heading':
                block.setHeadingLevel(level)
            else:
                block.setProperty(QTextFormat.Property.BlockQuoteLevel, 1)
            cursor.setBlockFormat(block)
            if kind == 'heading':
                chars = QTextCharFormat()
                chars.setFontWeight(QFont.Weight.Bold if level else QFont.Weight.Normal)
                chars.setProperty(QTextFormat.Property.FontSizeAdjustment, max(0, 4 - level) if level else 0)
                cursor.mergeBlockCharFormat(chars)
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        self._update_format_tools()

    def _choose_link(self):
        widget = self.editor if self.mode == 'wysiwyg' else self.source
        cursor = widget.textCursor()
        url, ok = QInputDialog.getText(self.window, 'Insert link', 'URL')
        if not ok or not url.strip():
            return
        label = cursor.selectedText() or url.strip()
        if self.mode == 'wysiwyg':
            cursor.insertHtml('<a href="' + html.escape(url.strip(), quote=True) + '">' + html.escape(label) + '</a>')
        else:
            cursor.insertText('[' + label.replace(']', '\\]') + '](<' + url.strip().replace('>', '%3E') + '>)')
        widget.setFocus()

    def _choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self.window, 'Insert image', '', 'Images (*.png *.jpg *.jpeg *.gif *.webp *.svg *.bmp)')
        if path:
            width, ok = QInputDialog.getInt(self.window, 'Image size', 'Width in pixels (0 = natural size)', 0, 0, 10000)
            if ok:
                self._insert(_image_tag(Path(path).as_uri(), Path(path).stem, width or None) + '\n\n')

    def _image_cursor(self, cursor=None):
        cursor = QTextCursor(cursor or self.editor.textCursor())
        doc = self.editor.document()
        if cursor.hasSelection():
            if cursor.selectedText() == '\ufffc' and cursor.charFormat().isImageFormat():
                return cursor
            raise ValueError('Select a single image to resize it.')
        for pos in (cursor.position(), cursor.position() - 1):
            if 0 <= pos < doc.characterCount() - 1 and doc.characterAt(pos) == '\ufffc':
                selected = QTextCursor(doc)
                selected.setPosition(pos)
                selected.setPosition(pos + 1, QTextCursor.MoveMode.KeepAnchor)
                if selected.charFormat().isImageFormat():
                    return selected
        raise ValueError('Click an image in the preview or WYSIWYG pane first.')

    def _register_image(self, src, image):
        # Qt's data-URL rendering can normalize slash sequences in base64.
        # Use an opaque resource name in the editor and data URLs on disk.
        name = 'mark-image:' + hashlib.sha256(src.encode()).hexdigest()
        self._embedded_images[name] = src
        self.editor.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(name), image)
        return name

    def _image_data(self, fmt):
        src = self._embedded_images.get(fmt.name(), fmt.name())
        if src.startswith('data:image/') and ';base64,' in src:
            try:
                return QImage.fromData(base64.b64decode(src.split(',', 1)[1]))
            except ValueError:
                return QImage()
        url = self.editor.document().baseUrl().resolved(QUrl(src))
        return QImage(url.toLocalFile()) if url.isLocalFile() else QImage()

    def resize_image(self, width, height=None):
        """Resize a selected/adjacent image; omitted height preserves aspect ratio."""
        _image_tag('', width=width, height=height)
        cursor = self._image_cursor()
        fmt = cursor.charFormat().toImageFormat()
        if height is None:
            if fmt.width() and fmt.height():
                height = width * fmt.height() / fmt.width()
            else:
                image = self._image_data(fmt)
                height = width * image.height() / image.width() if not image.isNull() else 0
        fmt.setWidth(width)
        fmt.setHeight(height)
        cursor.setCharFormat(fmt)
        if self.mode != 'wysiwyg':
            self._rich_changed(force=True)
        self.editor.setTextCursor(cursor)
        return self

    def _resize_dialog(self):
        try:
            cursor = self._image_cursor()
        except ValueError as exc:
            QMessageBox.information(self.window, 'Resize image', str(exc))
            return
        fmt = cursor.charFormat().toImageFormat()
        image = self._image_data(fmt)
        initial = round(fmt.width())
        if not initial and not image.isNull():
            initial = round(fmt.height() * image.width() / image.height()) if fmt.height() else image.width()
        initial = max(1, min(initial or 320, 10000))
        width, ok = QInputDialog.getInt(self.window, 'Resize image',
            'Width in pixels (keeps image proportions)', initial, 1, 10000)
        if ok:
            self.resize_image(width)

    def _find(self):
        term, ok = QInputDialog.getText(self.window, 'Find', 'Text to find')
        if ok and term:
            widget = self.editor if self.mode == 'wysiwyg' else self.source
            if not widget.find(term):
                widget.moveCursor(QTextCursor.MoveOperation.Start)
                widget.find(term)

    def _toolbar(self):
        bar = QToolBar('Note tools')
        bar.setMovable(False)
        self.window.addToolBar(bar)
        def action(label, callback, shortcut=None):
            item = QAction(label, self.window)
            item.triggered.connect(lambda checked=False: callback())
            if shortcut:
                item.setShortcut(shortcut)
            bar.addAction(item)
            return item
        action('Save', self._save_dialog, 'Ctrl+S')
        action('Save as', lambda: self._save_dialog(True), 'Ctrl+Shift+S')
        bar.addSeparator()
        self._modes = {}
        for mode in ('source', 'split', 'wysiwyg'):
            item = action(mode.capitalize(), lambda m=mode: self.set_mode(m))
            item.setCheckable(True)
            self._modes[mode] = item
        action('Find', self._find, 'Ctrl+F')
        self.window.addToolBarBreak()
        bar = QToolBar('Formatting')
        bar.setMovable(False)
        self.window.addToolBar(bar)
        action('Undo', lambda: (self.editor if self.mode == 'wysiwyg' else self.source).undo())
        action('Redo', lambda: (self.editor if self.mode == 'wysiwyg' else self.source).redo())
        bar.addSeparator()
        self._styles = QComboBox()
        self._styles.setAccessibleName('Paragraph style')
        self._styles.addItems(['Normal'] + [f'Heading {level}' for level in range(1, 7)])
        self._styles.activated.connect(lambda level: self._paragraph('heading', level))
        bar.addWidget(self._styles)
        self._format_actions = {}
        for label, kind, shortcut in [('Bold', 'bold', 'Ctrl+B'), ('Italic', 'italic', 'Ctrl+I'),
                                      ('Strikethrough', 'strike', None)]:
            item = action(label, lambda k=kind: self._format(k), shortcut)
            item.setCheckable(True)
            self._format_actions[kind] = item
        bar.addSeparator()
        action('Bullets', lambda: self._paragraph('bullet'))
        action('Numbering', lambda: self._paragraph('number'))
        action('Quote', lambda: self._paragraph('quote'))
        action('Task', lambda: self._insert('\n- [ ] Task\n'))
        bar.addSeparator()
        action('Link', self._choose_link, 'Ctrl+K')
        action('Image', self._choose_image)
        action('Resize image…', self._resize_dialog).setToolTip(
            'Select an image to change its width while keeping its proportions')
        self.window.addToolBarBreak()
        bar = QToolBar('Tables')
        bar.setMovable(False)
        self.window.addToolBar(bar)
        action('Insert table…', self._insert_table_dialog)
        bar.addSeparator()
        self._table_commands = [('Row above', 'above'), ('Row below', 'below'),
                                ('Column left', 'left'), ('Column right', 'right'),
                                ('Delete row', 'remove_row'), ('Delete column', 'remove_column'),
                                ('Delete table', 'delete')]
        self._table_actions = []
        for label, operation in self._table_commands:
            item = action(label, lambda op=operation: self._edit_table(op))
            item.setToolTip(label + ' — click a table cell in WYSIWYG first')
            item.setEnabled(False)
            self._table_actions.append(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', help='Markdown file to open')
    parser.add_argument('--demo', action='store_true', help='Open a sample note')
    args = parser.parse_args()
    note = Note(path=args.file) if args.file else Note('Welcome to Mark')
    if args.demo:
        note.heading('A little space for big ideas').text('A programmable Markdown notebook. **Write in source**, preview alongside it, or switch to *WYSIWYG*.')
        note.heading('Your next idea', 2).task('Try editing this note', True).task('Add an image and choose its width').text('')
        note.table(['Feature', 'Ready'], [['Live preview', 'Yes'], ['Rich text editing', 'Yes'], ['Python API', 'Yes']])
        note.code('from mark import Note\n\nnote = Note("My notebook")\nnote.heading("Hello").text("Made with Python.")\nNote.run()', 'python')
        note.quote('Use Ctrl+S to keep your work.').rule().text('Local files. Native windows. Your code.')
    return run()


if __name__ == '__main__':
    raise SystemExit(main())

