"""Markdown source fidelity, native editor and stable node-link integration."""
import copy

import pytest
from PySide6.QtCore import Qt, QMimeData, QPoint
from PySide6.QtGui import QImage, QTextCursor, QTextCharFormat
from PySide6.QtTest import QTest

from actiondraw import mindmap_markdown as md
from actiondraw.mindmap import MindMapController
from actiondraw.mindmap_node_editor import MindMapNodeEditor
from task_model import TabModel


@pytest.fixture
def model(app):
    m = MindMapController()
    yield m
    if m._node_editor:
        m._node_editor.reject()
        m._node_editor.deleteLater()


@pytest.fixture
def editor(model):
    model.openNodeEditor()
    return model._node_editor


def add(m, text, note=''):
    node = m.map.root.add_child(text, note=note)
    return node


def bind(m, owner, target, field='note'):
    text = getattr(owner, field) or ''
    fields = copy.deepcopy(m.text_links.get(owner.id, {}))
    fields[field] = md.reconcile(text, text, [], lambda _: target.id)
    assert m.editNode(owner.id, owner.text, owner.note or '', fields)
    return fields[field][0]


def test_tokens_ignore_escaped_inline_fenced_and_indented_code():
    text = '[[yes]] `[[inline]]` \\[[escaped]]\n```md\n[[fenced]]\n```\n    [[indented]]\n[[last]]'
    assert [m.group(1) for m in md.tokens(text)] == ['yes', 'last']


def test_thought_is_plain_text_and_only_notes_create_links(editor):
    m = editor.controller
    target = add(m, 'Target')
    editor.title.setText('**Literal** [[Target]] <b>name</b>')
    editor.notes.set_mode('source')
    editor.notes.source.setPlainText('**Formatted** [[Target]]')
    editor.accept()
    assert m.map.root.text == '**Literal** [[Target]] <b>name</b>'
    assert m.map.root.note == '**Formatted** [[Target]]'
    assert set(m.text_links[m.map.root.id]) == {'note'}
    assert m.text_links[m.map.root.id]['note'][0]['target'] == target.id
    assert m.searchNodeLinks('Literal')[0]['name'] == m.map.root.text
    assert m._resolve_text_name(m.map.root.text) == m.map.root.id


def test_stable_link_rename_delete_undo_and_roundtrip(model):
    target = add(model, 'Destination')
    owner = add(model, 'Owner', 'Visit [[Destination]]')
    binding = bind(model, owner, target)
    assert model.editNode(target.id, '**Renamed**', '')
    assert model.text_links[owner.id]['note'][0]['target'] == target.id
    payload = model.to_dict()
    model.load(payload)
    assert model.text_links[owner.id]['note'][0] == binding
    model.select(target.id)
    model.deleteSelected()
    assert not model.revealTextLink(target.id)
    assert model.text_links[owner.id]['note'][0]['target'] == target.id
    model.undo()
    assert model.revealTextLink(target.id)
    assert model.selectedId == target.id


def test_unambiguous_names_only_and_source_offset_tracking(model):
    a, b = add(model, 'Same'), add(model, 'Same')
    owner = add(model, 'Owner', '[[Same]] and [[Same]]')
    fields = {'note': md.reconcile(owner.note, owner.note, [], lambda _: None)}
    fields['note'][0]['target'] = a.id
    fields['note'][1]['target'] = b.id
    model.editNode(owner.id, owner.text, owner.note, fields)
    model.editNode(owner.id, owner.text, 'prefix ' + owner.note)
    bindings = model.text_links[owner.id]['note']
    assert [x['target'] for x in bindings] == [a.id, b.id]
    assert bindings[0]['start'] == 7
    owner = model.map.find(owner.id)
    model.editNode(owner.id, owner.text, 'prefix [[Same]]')
    assert len(model.text_links[owner.id]['note']) == 1
    assert model._resolve_text_name('Same') is None


def test_search_whole_project_and_reveal_filtered_folded(app):
    tabs = TabModel(); tabs.addTab('One'); tabs.addTab('Two')
    m = MindMapController(tabs)
    roots = list(m.map.root.children)
    target = roots[1].add_child('**Needle**')
    roots[1].folded = True
    m.set_scope(m.links[roots[0].id])
    assert m.searchNodeLinks('needle')[0]['id'] == target.id
    assert m.revealTextLink(target.id)
    assert m.selectedId == target.id and not roots[1].folded
    assert target.id in {n['id'] for n in m.nodes}


def test_goal_name_keeps_markdown_characters_literal(app):
    tabs = TabModel(); tabs.addTab('Goal')
    m = MindMapController(tabs)
    node = m.map.root.children[0]
    assert m.editNode(node.id, '**Goal**', '')
    assert tabs.getTabSummary(0)['name'] == '**Goal**'
    m.reconcile()
    assert node.text == '**Goal**'
    m.undo(); assert m.map.find(node.id).text == 'Goal'
    m.redo(); assert m.map.find(node.id).text == '**Goal**'


def test_source_and_mode_switches_preserve_exact_text(editor):
    text = '#  Title\n\n- a\n- b\n\n**bold**\n'
    editor.notes.load_draft(text, [])
    for mode in ('source', 'split', 'wysiwyg'):
        editor.notes.set_mode(mode)
        assert editor.notes.markdown == text
    editor.accept()
    assert editor.controller.map.root.note == text


def test_rich_edits_preserve_two_identical_labels_targets(editor):
    m = editor.controller
    a, b = add(m, 'Same'), add(m, 'Same')
    text = '[[Same]] and [[Same]]'
    bindings = md.reconcile(text, text, [], lambda _: a.id)
    bindings[1]['target'] = b.id
    note = editor.notes
    note.load_draft(text, bindings)
    cursor = note.editor.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText('!', QTextCharFormat())
    assert [x['target'] for x in note.bindings] == [a.id, b.id]
    assert note.markdown.count('[[Same]]') == 2
    assert 'mindmap:' not in note.markdown


def test_cancel_and_atomic_commit(editor):
    m = editor.controller
    before = m.to_dict()
    editor.title.setText('**draft**')
    editor.notes.set_mode('source'); editor.notes.source.setPlainText('# notes')
    editor.reject()
    assert m.to_dict() == before
    editor.open_node(m.map.root)
    editor.title.setText('**committed**')
    editor.notes.source.setPlainText('# notes')
    editor.accept()
    assert m.map.root.text == '**committed**' and m.map.root.note == '# notes'
    m.undo(); assert m.to_dict() == before


@pytest.mark.parametrize('mode', ['source', 'wysiwyg'])
def test_popup_keyboard_selection_and_binding(editor, mode):
    editor.notes_toggle.click()
    target = add(editor.controller, 'Destination')
    note = editor.notes
    note.load_draft('', [])
    note.set_mode(mode)
    surface = note.active_surface()
    QTest.keyClicks(surface, '[[')
    QTest.qWait(20)
    assert note.picker.isVisible()
    QTest.keyClicks(note.picker.query, 'Dest')
    QTest.keyClick(note.picker.query, Qt.Key.Key_Return)
    assert not note.picker.isVisible()
    assert '[[Destination]]' in note.markdown
    assert note.bindings[0]['target'] == target.id


def test_image_paste_dimensions_and_table_editing(editor):
    note = editor.notes
    image = QImage(80, 40, QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.red)
    mime = QMimeData(); mime.setImageData(image)
    note.editor.insertFromMimeData(mime)
    assert 'data:image/png;base64,' in note.markdown
    assert 'width="80"' in note.markdown
    note.resize_image(40)
    assert 'width="40"' in note.markdown and 'height="20"' in note.markdown
    note.load_draft('', [])
    note._insert_table(2, 2)
    table = note.editor.textCursor().currentTable()
    assert table is not None
    rows = table.rows()
    note._edit_table('append_row')
    assert table.rows() == rows + 1
    note.editor.undo()
    assert table.rows() == rows


def test_internal_copy_remaps_local_links_keeps_external_targets(model, app):
    branch = add(model, 'Branch')
    child = branch.add_child('Child')
    outside = add(model, 'Outside')
    model.editNode(branch.id, branch.text, '[[Child]] [[Outside]]')
    links = model.text_links[branch.id]['note']
    assert [b['target'] for b in links] == [child.id, outside.id]
    model.select(branch.id); model.copySelected()
    model.select(model.map.root.id); assert model.pasteSelected()
    clone = model.map.find(model.selectedId)
    assert clone.id != branch.id
    assert [b['target'] for b in model.text_links[clone.id]['note']] == [clone.children[0].id, outside.id]
    model.undo(); assert model.map.find(clone.id) is None


def test_malformed_binding_rejected_without_partial_load(model):
    target = add(model, 'Target'); owner = add(model, 'Owner', '[[Target]]')
    bind(model, owner, target)
    before = model.to_dict()
    bad = copy.deepcopy(before); bad['text_links'][owner.id]['note'][0]['start'] = 1000
    with pytest.raises(ValueError, match='binding'):
        model.load(bad)
    assert model.to_dict() == before


def test_unclosed_fence_long_inline_code_and_even_escape():
    source = '[[yes]] ``code ` [[no]]`` \\\\[[backslash]]\n~~~\n[[unclosed]]'
    assert [m.group(1) for m in md.tokens(source)] == ['yes', 'backslash']


@pytest.mark.parametrize('mode', ['source', 'wysiwyg'])
def test_editor_link_deletion_undo_retains_identity(editor, mode):
    m = editor.controller
    target = add(m, 'Same'); add(m, 'Same')
    note = editor.notes
    bindings = md.reconcile('[[Same]]', '[[Same]]', [], lambda _: target.id)
    note.load_draft('[[Same]]', bindings)
    note.set_mode(mode)
    surface = note.active_surface()
    surface.selectAll()
    QTest.keyClick(surface, Qt.Key.Key_Backspace)
    assert not note.bindings
    surface.undo()
    assert note.bindings[0]['target'] == target.id


def test_unicode_source_picker_offsets(editor):
    target = add(editor.controller, 'Destination')
    note = editor.notes
    note.load_draft('😀 ', [])
    note.set_mode('source')
    cursor = note.source.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End)
    note.source.setTextCursor(cursor)
    QTest.keyClicks(note.source, '[[')
    QTest.qWait(10)
    assert note.picker.isVisible()
    note.picker.query.setText('Destination')
    note.picker.choose()
    assert note.markdown == '😀 [[Destination]]'
    assert note.bindings[0]['start'] == 2
    assert note.bindings[0]['target'] == target.id


def test_project_encrypted_roundtrip(app, tmp_path, monkeypatch):
    import json
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TaskModel
    from progress_crypto import EncryptionCredentials, decrypt_project_data
    tasks, tabs = TaskModel(), TabModel(); tabs.addTab('Main')
    pm = ProjectManager(tasks, DiagramModel(tasks), tabs)
    m = pm.mindmap
    target = add(m, 'Private destination')
    owner = add(m, 'Private owner', '# Private notes [[Private destination]]')
    bind(m, owner, target)
    expected = m.to_dict()
    credentials = EncryptionCredentials(passphrase='markdown-roundtrip')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: credentials)
    path = tmp_path / 'markdown.progress'
    assert pm.saveProject(str(path))
    assert 'Private destination' not in path.read_text()
    pm.loadProject(str(path))
    assert m.to_dict() == expected
    # Legacy plaintext project loading uses the same optional field.
    data = decrypt_project_data(json.loads(path.read_text()), credentials)
    path.write_text(json.dumps(data))
    pm.loadProject(str(path))
    assert m.to_dict() == expected


def test_qml_names_are_literal_and_notes_links_navigate(app, actiondraw_window):
    from actiondraw.model import DiagramModel
    from task_model import ProjectManager, TaskModel
    tasks, tabs = TaskModel(), TabModel(); tabs.addTab('Main')
    diagram = DiagramModel(tasks)
    pm = ProjectManager(tasks, diagram, tabs)
    m = pm.mindmap
    target = add(m, 'Destination')
    owner = add(m, '**Literal** [[Destination]] <b>name</b>', 'Go to [[Destination]]')
    bind(m, owner, target)
    engine = actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    window = engine.rootObjects()[0]; window.show(); pm.showMindmap()
    QTest.qWait(80)
    def find(item, name):
        if item.objectName() == name:
            return item
        for child in item.childItems():
            result = find(child, name)
            if result:
                return result
    label = find(window.contentItem(), 'mindmapNodeText_' + owner.id)
    assert label is not None
    assert label.property('text') == owner.text
    # QML Text.PlainText is 0: even HTML-looking names remain literal.
    from PySide6.QtQml import QQmlExpression, qmlContext
    assert QQmlExpression(qmlContext(label), label, 'textFormat === Text.PlainText').evaluate()[0]
    m.select(owner.id); m.openNodeEditor()
    native = m.node_editor()
    assert native.title.text() == owner.text
    surface = native.notes.editor
    QTest.qWait(20)
    point = next((QPoint(x, y) for y in range(0, 120, 2)
                  for x in range(0, min(surface.width(), 500), 2)
                  if surface.anchorAt(QPoint(x, y))), None)
    assert point is not None
    before = m.to_dict()
    QTest.mouseClick(surface.viewport(), Qt.LeftButton, Qt.NoModifier, point)
    QTest.qWait(20)
    assert m.selectedId == target.id
    assert m.to_dict() == before
    assert not m.editorVisible


def test_source_deleting_first_identical_link_keeps_second_target(editor):
    m = editor.controller
    a, b = add(m, 'Same'), add(m, 'Same')
    text = '[[Same]][[Same]]'
    bindings = md.reconcile(text, text, [], lambda _: a.id)
    bindings[1]['target'] = b.id
    note = editor.notes
    note.load_draft(text, bindings); note.set_mode('source')
    cursor = note.source.textCursor(); cursor.setPosition(0)
    cursor.setPosition(8, QTextCursor.MoveMode.KeepAnchor); cursor.removeSelectedText()
    assert note.markdown == '[[Same]]'
    assert note.bindings[0]['target'] == b.id
    note.source.undo()
    assert [b['target'] for b in note.bindings] == [a.id, b.id]
    note.source.redo()
    assert note.bindings[0]['target'] == b.id


def test_reveal_prefers_reference_in_current_goal(app):
    tabs = TabModel(); tabs.addTab('One'); tabs.addTab('Two')
    m = MindMapController(tabs)
    roots = list(m.map.root.children)
    child = roots[1].add_child('Target')
    assert m.addTabReference(roots[0].id, m.links[roots[1].id])
    ref = m.selectedId
    m.set_scope(m.links[roots[0].id])
    assert m.revealTextLink(child.id)
    assert m.selectedId == ref + '/' + child.id
    assert m.tabScoped


@pytest.mark.parametrize('choice', ['Save and navigate', 'Discard and navigate', 'Cancel'])
def test_dirty_navigation_choices(editor, monkeypatch, choice):
    from PySide6.QtWidgets import QMessageBox
    m = editor.controller
    target = add(m, 'Target')
    original = m.map.root.text
    editor.title.setText('Changed')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: 0)
    monkeypatch.setattr(QMessageBox, 'clickedButton',
                        lambda self: next(b for b in self.buttons() if b.text() == choice))
    editor.navigate(target.id)
    assert m.map.root.text == ('Changed' if choice == 'Save and navigate' else original)
    assert editor.isVisible() == (choice == 'Cancel')
    assert (m.selectedId == target.id) == (choice != 'Cancel')


def test_formatting_shortcuts_apply_only_inside_notes(editor):
    editor.notes_toggle.click()
    note = editor.notes
    note.load_draft('Notes text', [])
    editor.title.setText('Plain name')
    editor.title.setFocus()
    QTest.qWait(20)
    QTest.keyClick(editor.title, Qt.Key_B, Qt.ControlModifier)
    assert editor.title.text() == 'Plain name'
    assert note.markdown == 'Notes text'
    assert editor.title.hasFocus()
    note.editor.setFocus()
    note.editor.selectAll()
    QTest.keyClick(note.editor, Qt.Key_B, Qt.ControlModifier)
    assert '**Notes text**' in note.markdown


def test_notes_disclosure_preserves_draft_and_resets_between_nodes(editor):
    QTest.qWait(20)
    assert not editor.notes.window.isVisible()
    assert editor.width() == 520
    compact_height = editor.height()
    assert editor.title.hasFocus()
    target = add(editor.controller, 'Destination')
    owner = add(editor.controller, 'Owner', 'Visit [[Destination]]')
    bind(editor.controller, owner, target)
    editor.open_node(owner)
    assert editor.notes.window.isVisible()
    assert editor.title.selectedText() == 'Owner'
    editor.title.setText('Draft title')
    draft = editor.draft()
    editor.notes_toggle.click()
    assert not editor.notes.window.isVisible()
    assert editor.height() == compact_height
    assert editor.draft() == draft
    editor.notes_toggle.click()
    assert editor.notes.window.isVisible()
    assert editor.notes.active_surface().hasFocus()
    assert editor.draft() == draft
    assert editor.screen().availableGeometry().contains(editor.frameGeometry())
    editor.open_node(target)
    assert not editor.notes.window.isVisible()
    assert editor.title.hasFocus()


@pytest.mark.parametrize('key,modifiers', [
    (Qt.Key_Return, Qt.NoModifier),
    (Qt.Key_Return, Qt.ControlModifier),
    (Qt.Key_S, Qt.ControlModifier),
    (Qt.Key_Escape, Qt.NoModifier),
])
def test_compact_editor_keyboard_save_and_cancel(editor, key, modifiers):
    original = editor.controller.map.root.text
    editor.title.setText('Quick title')
    QTest.qWait(20)
    QTest.keyClick(editor.title, key, modifiers)
    assert not editor.isVisible()
    assert editor.controller.map.root.text == (original if key == Qt.Key_Escape else 'Quick title')


def test_previous_thought_link_metadata_is_retired_without_rewriting_names(model):
    target = add(model, 'Target')
    owner = add(model, '[[Target]]', 'Notes [[Target]]')
    payload = model.to_dict()
    payload['text_links'][owner.id] = {
        'text': md.reconcile(owner.text, owner.text, [], lambda _: target.id),
        'note': md.reconcile(owner.note, owner.note, [], lambda _: target.id),
    }
    model.load(payload)
    assert model.map.find(owner.id).text == '[[Target]]'
    assert set(model.text_links[owner.id]) == {'note'}
    assert model.editNode(owner.id, 'New name', owner.note)
    assert model.text_links[owner.id]['note'][0]['target'] == target.id
