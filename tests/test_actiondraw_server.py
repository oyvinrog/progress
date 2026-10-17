"""Remote editing uses the same project, encryption and GUI thread as desktop."""
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest
from PySide6.QtCore import QThread, QSettings

from actiondraw.model import DiagramModel
from actiondraw.server import ActionDrawServer, ApiError, ProjectApi
from progress_crypto import EncryptionCredentials
from task_model import ProjectManager, TabModel, TaskModel


@pytest.fixture
def project(app, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    monkeypatch.setattr('task_model.QSettings', lambda *args: settings)
    tasks, tabs = TaskModel(), TabModel()
    tabs.addTab('Goal')
    pm = ProjectManager(tasks, DiagramModel(tasks), tabs)
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *a: EncryptionCredentials(passphrase='test-password'))
    assert pm.saveProject(str(tmp_path / 'remote.progress'))
    yield pm
    pm._reminder_timer.stop()
    pm.deleteLater()


def edit(api, action, **kwargs):
    return api.command(dict(action=action, revision=api.sync_revision(), **kwargs))


def test_edit_save_conflict_and_independent_navigation(project):
    api = ProjectApi(project)
    m = project.mindmap
    root = m.map.root.id
    goal = project._tab_model.getAllTabs()[0]
    m.set_scope(goal.id)
    selection = m._selection_state()
    edit(api, 'child', node=root, title='Phone thought')
    assert m._scope_tab == goal.id
    assert m._selection_state() == selection
    node = next(n for n in api.state()['nodes'] if n['title'] == 'Phone thought')
    revision = api.revision
    assert edit(api, 'edit', node=node['id'], title='Edited', note='Notes')['saved']
    assert not project.hasUnsavedChanges()
    with pytest.raises(ApiError, match='project changed'):
        api.command(dict(action='edit', node=node['id'], title='Stale', note='', revision=revision))
    path = project.currentFilePath
    assert 'Edited' not in open(path).read()
    project.loadProject(path)
    assert project.mindmap.map.find(node['id']).text == 'Edited'
    assert project.mindmap.map.find(node['id']).note == 'Notes'


def test_projection_does_not_unfold_desktop(project):
    m = project.mindmap
    m.addThought()
    parent = m.map.find(m.selectedId)
    parent.add_child('Hidden child')
    parent.folded = True
    state = ProjectApi(project).state()
    assert any(n['title'] == 'Hidden child' for n in state['nodes'])
    assert parent.folded


def test_references_cycles_completion_and_history(project):
    api = ProjectApi(project)
    root = project.mindmap.map.root.id
    edit(api, 'child', node=root, title='Container')
    container = next(n for n in api.state()['nodes'] if n['title'] == 'Container')
    goal = project._tab_model.getAllTabs()[0]
    edit(api, 'reference', node=container['id'], goal=goal.id)
    ref = next(n for n in api.state()['nodes'] if n['reference'])
    edit(api, 'child', node=ref['id'], title='Shared')
    occurrences = [n for n in api.state()['nodes'] if n['title'] == 'Shared']
    assert len(occurrences) == 2
    edit(api, 'complete', node=occurrences[0]['id'])
    assert all(n['completed'] for n in api.state()['nodes'] if n['title'] == 'Shared')
    edit(api, 'undo')
    assert not any(n['completed'] for n in api.state()['nodes'] if n['title'] == 'Shared')
    goal_node = next(n for n in api.state()['nodes'] if n['goalId'] == goal.id and not n['reference'])
    with pytest.raises(ApiError):
        edit(api, 'move', node=container['id'], target=goal_node['id'])
    edit(api, 'delete', node=ref['id'])
    assert project._tab_model.goalIndex(goal.id) >= 0


def test_planning_and_markdown(project):
    api = ProjectApi(project)
    goal = project._tab_model.getAllTabs()[0]
    root = project.mindmap.map.root.id
    edit(api, 'child', node=root, title='Plan')
    node = next(n for n in api.state()['nodes'] if n['title'] == 'Plan')
    edit(api, 'goal_range', goal=goal.id, start='2032-02-28', end='2032-03-02')
    with pytest.raises(ApiError):
        edit(api, 'goal_range', goal=goal.id, start='2032-03-02', end='2032-02-28')
    edit(api, 'reminder', node=node['id'], at='2032-02-29T09:30', notify=True)
    edit(api, 'deadline', node=node['id'], minutes=30)
    edit(api, 'schedule', node=node['id'], weekday=0)
    edit(api, 'kanban', item='node:'+node['sourceId'], status='ready')
    edit(api, 'markdown', goal=goal.id, tabs=[dict(name='Phone', text='# Notes')])
    state = api.state()
    assert state['goals'][0]['markdown'][0]['text'] == '# Notes'
    assert state['kanban']
    assert any(r['kind'] == 'mindmap' for r in state['reminders'])
    assert any(r['kind'] == 'kanban_schedule' for r in state['reminders'])
    edit(api, 'complete', node=node['id'])
    assert node['sourceId'] not in project.mindmap.reminders


def test_import_export_and_atomic_save_failure(project, monkeypatch):
    api = ProjectApi(project)
    root = project.mindmap.map.root.id
    edit(api, 'import', node=root, text='Parent\n  Child')
    exported = edit(api, 'export', node=root, format='opml')['text']
    assert '<opml' in exported and 'Child' in exported
    original = open(project.currentFilePath, 'rb').read()
    def fail(*args):
        raise OSError('disk full')
    with monkeypatch.context() as patch:
        patch.setattr('task_model.os.replace', fail)
        result = edit(api, 'child', node=root, title='Unsaved')
        assert not result['saved']
        assert open(project.currentFilePath, 'rb').read() == original
        assert project.hasUnsavedChanges()
    assert edit(api, 'save')['saved']
    assert not project.hasUnsavedChanges()


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def http(app, url, token=None, payload=None, **headers):
    def request():
        if token:
            headers['Authorization'] = 'Bearer ' + token
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), exc.headers
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(request)
        deadline = time.monotonic() + 6
        while not future.done() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.005)
        return future.result()


@pytest.fixture
def server(project, monkeypatch):
    monkeypatch.setattr(ActionDrawServer, 'addresses', property(lambda self: [dict(address='127.0.0.1', label='Test', tailscale=False)]))
    server = ActionDrawServer(project)
    yield server
    server.stop()
    server.deleteLater()


def test_http_auth_origin_assets_gui_thread_restart(app, server, monkeypatch):
    port = available_port()
    assert server.start('127.0.0.1', port), server.error
    token = server._token
    url = f'http://127.0.0.1:{port}'
    assert server.url == url+'/#key='+token
    assert server.boundAddress == '127.0.0.1'
    assert server.qr.startswith('data:image/svg+xml;base64,')
    observed = []
    original = server.api.state
    def state(since=None):
        observed.append(QThread.currentThread() == app.thread())
        return original(since)
    monkeypatch.setattr(server.api, 'state', state)
    code, body, headers = http(app, url+'/api/state')
    assert code == 401
    assert http(app, url+'/api/state', 'wrong')[0] == 401
    assert http(app, url+'/api/state', token, Origin='http://evil.example')[0] == 403
    assert http(app, url+'/api/state', token, Host='evil.example')[0] == 403
    code, body, headers = http(app, url+'/api/state', token)
    assert code == 200 and observed == [True]
    assert headers['Cache-Control'] == 'no-store'
    payload = json.loads(body)
    assert http(app, url+'/api/command', token, dict(action='child', node=payload['root'], title='HTTP thought', revision=payload['revision']))[0] == 200
    assert http(app, url+'/api/command', token, dict(action='child', node=payload['root'], title='Duplicate stale', revision=payload['revision']))[0] == 409
    for path in ('/', '/app.js', '/style.css'):
        assert http(app, url+path)[0] == 200
    assert http(app, url+'/server.py')[0] == 404
    assert http(app, url+'/api/command', token, {'padding': 'x' * (1024 * 1024)})[0] == 413
    server.stop()
    assert not server.running and not server.url
    assert server.start('127.0.0.1', port)
    assert server._token != token
    assert http(app, url+'/api/state', token)[0] == 401
    server.pm.projectAccessEnding.emit()
    assert not server.running


def test_start_errors_and_stop_on_save_as(server, tmp_path):
    assert not server.start('203.0.113.4', 8765)
    assert not server.start('127.0.0.1', 0)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0));sock.listen()
        assert not server.start('127.0.0.1', sock.getsockname()[1])
        assert 'Cannot start' in server.error
    assert server.start('127.0.0.1', available_port())
    assert server.pm.saveProject(str(tmp_path/'other.progress'))
    assert not server.running


def test_remove_board_card_and_bad_commands(project):
    api = ProjectApi(project)
    root = project.mindmap.map.root.id
    edit(api, 'child', node=root, title='Card')
    node = next(n for n in api.state()['nodes'] if n['title'] == 'Card')
    edit(api, 'kanban', item='node:'+node['id'], status='ready')
    edit(api, 'kanban', item='node:'+node['id'], status='unscheduled')
    assert not any(i['itemId'] == 'node:'+node['id'] for i in api.state()['kanban'])
    with pytest.raises(ApiError):
        edit(api, 'loadProject', path='/tmp/not-authorized')
    with pytest.raises(ApiError):
        edit(api, 'edit', node=node['id'], title=[], note='')
    with pytest.raises(ApiError):
        edit(api, 'schedule', node=node['id'], weekday=True)


def test_queued_request_cannot_cross_stop_restart(app, server):
    from concurrent.futures import Future
    assert server.start('127.0.0.1', available_port())
    request = Future()
    server.request.emit((request, server._epoch, 'command', dict(
        action='child', node=server.pm.mindmap.map.root.id, title='Must not appear',
        revision=server.api.sync_revision())))
    server.stop()
    assert server.start('127.0.0.1', available_port())
    app.processEvents()
    with pytest.raises(ApiError, match='access has ended'):
        request.result()
    assert not any(n.text == 'Must not appear' for n in server.pm.mindmap.map.walk())


def test_server_dialog_loads(project, actiondraw_window, app):
    from PySide6.QtCore import QObject, QMetaObject
    engine = actiondraw_window(project._diagram_model, project._task_model, project,
                               tab_model=project._tab_model)
    assert engine.rootObjects()
    root = engine.rootObjects()[0]
    dialog = root.findChild(QObject, 'actiondrawServerDialog')
    assert dialog is not None
    assert QMetaObject.invokeMethod(dialog, 'open')
    app.processEvents()
    assert dialog.property('visible')
    assert engine._actiondraw_server.addresses
    QMetaObject.invokeMethod(dialog, 'close')


def test_quick_creation_returns_selection_and_inserts_adjacent_sibling(project):
    api = ProjectApi(project)
    root = project.mindmap.map.root.id
    first = edit(api, 'child', node=root, title='First')['nodeId']
    last = edit(api, 'child', node=root, title='Last')['nodeId']
    middle = edit(api, 'sibling', node=first, title='Middle')['nodeId']
    children = next(n for n in api.state()['nodes'] if n['id'] == root)['children']
    assert children.index(middle) == children.index(first) + 1
    assert children.index(last) > children.index(middle)
    goal = project._tab_model.getAllTabs()[0]
    edit(api, 'reference', node=first, goal=goal.id)
    ref = next(n for n in api.state()['nodes'] if n['reference'])
    shared = edit(api, 'child', node=ref['id'], title='Shared child')['nodeId']
    sibling = edit(api, 'sibling', node=shared, title='Shared sibling')['nodeId']
    snapshot = {n['id']: n for n in api.state()['nodes']}
    assert snapshot[shared]['parent'] == ref['id']
    assert snapshot[sibling]['parent'] == ref['id']


def test_idle_polls_skip_serialization_layout_and_full_payload(project, monkeypatch):
    from unittest.mock import Mock
    import actiondraw.server as module
    api = ProjectApi(project)
    first = api.state()
    build = Mock(wraps=project._build_project_data)
    layout = Mock(wraps=module.layout)
    monkeypatch.setattr(project, '_build_project_data', build)
    monkeypatch.setattr(module, 'layout', layout)
    clock = time.monotonic()
    for i in range(120):
        # Two hours of idle polling must not trigger periodic project scans.
        monkeypatch.setattr(time, "monotonic", lambda: clock + i * 60)
        response = api.state(first['revision'])
        assert response['unchanged'] and 'nodes' not in response
        assert response['saved']
    assert build.call_count == layout.call_count == 0
    # A second client gets the cached layout, but a fresh canonical check.
    assert api.state()['nodes'] == first['nodes']
    assert build.call_count == 1 and layout.call_count == 0
    # A signalled desktop edit is visible at the very next poll.
    project.mindmap.editNode(project.mindmap.map.root.id, 'Changed on desktop', '')
    response = api.state(first['revision'])
    assert response['nodes'][0]['title'] == 'Changed on desktop'
    assert not response['saved'] and layout.call_count == 1


def test_full_refresh_and_command_detect_unsignalled_edits(project):
    api = ProjectApi(project)
    state = api.state()
    root = project.mindmap.map.root
    root.text = 'Direct write'
    # No signals were emitted, but a write must never accept a stale revision.
    with pytest.raises(ApiError, match='project changed'):
        api.command(dict(action='child', revision=state['revision'], node=root.id, title='Stale'))
    state = api.state()
    root.text = 'Another direct write'
    assert api.state(state['revision'])['unchanged']
    response = api.state()
    assert response['nodes'][0]['title'] == 'Another direct write'


def test_cached_save_status_and_plaintext_release(project):
    api = ProjectApi(project)
    project.mindmap.editNode(project.mindmap.map.root.id, 'Sensitive content', '')
    state = api.state()
    assert not state['saved']
    assert project.saveCurrentProject()
    assert api.state(state['revision'])['saved']
    project.projectAccessEnding.emit()
    assert api._cached_state is None and api._snapshot is None


def test_conditional_http_response(app, server):
    assert server.start('127.0.0.1', available_port())
    url = server.url.split('/#')[0]
    token = server._token
    code, body, _ = http(app, url+'/api/state', token)
    assert code == 200
    revision = json.loads(body)['revision']
    code, body, _ = http(app, url+f'/api/state?since={revision}', token)
    assert code == 200 and json.loads(body)['unchanged']
    assert len(body) < 350
    assert http(app, url+'/api/state?since=invalid', token)[0] == 400
    server.stop()
    assert server.api._cached_state is None and server.api._snapshot is None


def test_standalone_reminders_invalidate_idle_cache(project):
    api = ProjectApi(project)
    state = api.state()
    assert project.addStandaloneReminder('Phone reminder', '2099-01-01 12:00', False)
    updated = api.state(state['revision'])
    assert updated['revision'] > state['revision']
    assert updated['reminders']
    assert project.updateStandaloneReminder(0, 'Renamed reminder', '2099-01-02 12:00', False)
    renamed = api.state(updated['revision'])
    assert renamed['revision'] > updated['revision']
    project.clearStandaloneReminder(0)
    cleared = api.state(renamed['revision'])
    assert cleared['reminders'] == []
    assert project.addStandaloneReminder('Due', '2000-01-01 12:00', False)
    state = api.state()
    project._checkStandaloneReminders()
    assert api.state(state['revision'])['revision'] > state['revision']
