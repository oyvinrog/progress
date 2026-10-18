"""Private, desktop-owned HTTP access to the open ActionDraw project."""
from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import io
import json
from concurrent.futures import Future
from datetime import datetime
from pathlib import Path
import secrets
import threading
from types import SimpleNamespace

from PySide6.QtCore import QObject, Property, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface

from ._vendor.pyplane.layout import layout
from .markdown_note_tabs import normalize_editor_tabs
from .mindmap import _content
from .outline_clipboard import outline_to_indented_text, outline_to_opml


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class ProjectApi:
    """GUI-thread adapter. No HTTP worker may access the project models."""
    def __init__(self, manager):
        self.pm = manager
        self.mm = manager.mindmap
        self.tabs = manager._tab_model
        self.revision = 0
        self.fingerprint = None
        self.clear_cache()
        # Signals only mark dirty. No work/timer is installed for idle servers.
        for owner, names in (
            (self.mm, ('changed', 'planChanged')),
            (self.tabs, ('tabsChanged', 'scheduledGoalsChanged', 'kanbanChanged',
                         'priorityRanksChanged', 'priorityWeightsChanged', 'currentTabChanged',
                         'goalsChanged', 'assessmentChanged', 'dataChanged', 'rowsMoved')),
            (manager, ('loadCompleted', 'saveCompleted', 'workspaceMarkdownTabsChanged',
                       'currentTabMarkdownTabsChanged', 'kanbanChanged', 'standaloneRemindersChanged',
                       'taskReminderDue', 'taskContractBreached')),
            (manager._task_model, ('taskCountChanged', 'taskRenamed',
                                  'taskCompletionChanged', 'taskReminderChanged', 'dataChanged')),
            (manager._diagram_model, ('itemsChanged', 'edgesChanged', 'drawingChanged')),
        ):
            if owner is not None:
                for name in names:
                    getattr(owner, name).connect(self.invalidate)
        manager.projectAccessEnding.connect(self.clear_cache)

    def invalidate(self, *args):
        self._dirty = True

    def clear_cache(self, *args):
        # Snapshot data is plaintext: release it when access ends or a file changes.
        self._dirty = True
        self._snapshot = None
        self._cached_state = None
        self._cached_day = None

    def sync_revision(self, force=True):
        # Idle reads never walk the project. Commands and full refreshes still
        # force a fresh check, including legacy/direct writes without signals.
        if not force and not self._dirty:
            return self.revision
        snapshot = self.pm._serialize_project_payload(self.pm._build_project_data())
        digest = hashlib.sha256(snapshot.encode()).digest()
        if digest != self.fingerprint:
            self.fingerprint = digest
            self.revision += 1
            self._cached_state = None
        self._snapshot = snapshot
        self._dirty = False
        return self.revision

    def state(self, since=None):
        self.sync_revision(force=since is None)
        now = datetime.now()
        day = now.date()
        status = dict(revision=self.revision,
                      saved=self._snapshot == self.pm._last_saved_snapshot,
                      canUndo=self.mm.canUndo, canRedo=self.mm.canRedo,
                      serverNow=now.isoformat(timespec='seconds'),
                      timezone=now.astimezone().tzname())
        if since == self.revision and self._cached_day == day:
            return dict(status, unchanged=True)
        if self._cached_state is not None and self._cached_day == day:
            return dict(self._cached_state, **status)
        m = self.mm
        with m.independent_view():
            root = m.view_root
            tree = list(root.walk())
            # Clone the projection, so browser folding never mutates desktop state.
            clones = {n: copy.copy(n) for n in tree}
            for n, clone in clones.items():
                clone.children = [clones[c] for c in n.children]
                clone.parent = clones.get(n.parent)
                clone.folded = False
            boxes = layout(SimpleNamespace(root=clones[root]))
            priorities = m._priority_data()
            nodes = []
            for n in tree:
                key = _content(n).id
                b = boxes[clones[n]]
                nodes.append(dict(id=n.id, sourceId=key, parent=n.parent.id if n.parent else None,
                    children=[c.id for c in n.children], title=n.text, note=n.note or '',
                    goalId=m._tab_id(n), reference=getattr(n, 'reference', False),
                    completed=key in m._completed, bookmarked=key in m._bookmarks,
                    bold=bool(n.style.bold), side=n.side, measureProgress=key in m._measure_progress,
                    progressPercent=round(100 * sum(_content(c).id in m._completed for c in n.children) / len(n.children)) if n.children else 0,
                    x=b.x, y=b.y, width=b.width, height=b.height,
                    **m._reminder_data(key), **m._deadline_data(key), **m._plan_data(key),
                    **priorities.get(m._tab_id(n), {})))
        goals = [dict(id=t.id, name=t.name, start=t.goal_start_date, end=t.goal_end_date,
                      markdown=normalize_editor_tabs(t.markdown_tabs)) for t in self.tabs.getAllTabs()]
        self._cached_state = dict(root=root.id, nodes=nodes, goals=goals,
                    markdown=self.pm.getWorkspaceMarkdownTabs(), reminders=self.pm.getActiveReminders(),
                    kanban=self.pm.getKanbanItems(), weekdays=m.planWeekdayOptions)
        self._cached_day = day
        return dict(self._cached_state, **status)

    @staticmethod
    def string(data, name, default=None):
        value = data.get(name, default)
        if not isinstance(value, str) or len(value) > 500000:
            raise ApiError(400, f'Invalid {name}.')
        return value

    @staticmethod
    def integer(data, name, default=0, low=-1, high=10000):
        value = data.get(name, default)
        if type(value) is not int or not low <= value <= high:
            raise ApiError(400, f'Invalid {name}.')
        return value

    def command(self, data):
        if not isinstance(data, dict):
            raise ApiError(400, 'Expected an object.')
        if type(data.get('revision')) is not int or data['revision'] != self.sync_revision():
            raise ApiError(409, 'The project changed. Review the refreshed version before submitting again.')
        action = self.string(data, 'action')
        m, pm, tabs = self.mm, self.pm, self.tabs
        node_id = data.get('node')
        if node_id is not None and not isinstance(node_id, str):
            raise ApiError(400, 'Invalid node.')
        result = None
        created_node = None
        with m.independent_view(node_id):
            n = m._find(node_id) if node_id else None
            source = m.sourceNodeId(node_id) if n else None
            goal_id = self.string(data, 'goal', '')
            goal_index = tabs.goalIndex(goal_id)
            goal = tabs.getAllTabs()[goal_index] if goal_index >= 0 else None
            node_actions = {'edit','child','sibling','complete','bold','bookmark','progress','delete',
                            'move','side','promote','reference','import','export','reminder','deadline','schedule'}
            if action in node_actions and n is None:
                raise ApiError(400, 'Select a node.')
            m._last_commit_error = ''
            if action == 'edit':
                title, note = self.string(data, 'title'), self.string(data, 'note', '')
                if not title.strip():
                    raise ApiError(400, 'A title is required.')
                result = m.editNode(node_id, title, note)
                linked = m._tab_id(n)
                if linked:
                    tabs.renameTab(tabs.goalIndex(linked), title)
            elif action in ('child', 'sibling'):
                title = self.string(data, 'title', 'New thought').strip()
                parent = n.parent if action == 'sibling' else n
                if parent is None or not title:
                    raise ApiError(400, 'Choose a parent and enter a title.')
                def add_node():
                    nonlocal created_node
                    child = parent.add_child(title)
                    if action == 'sibling':
                        child.move_to(parent, parent.children.index(n) + 1)
                    created_node = child.id
                result = m._commit(add_node)
            elif action in ('complete', 'bold', 'bookmark', 'progress', 'promote', 'delete'):
                if action == 'delete' and n is m.view_root:
                    raise ApiError(400, 'The project root cannot be deleted.')
                operations = {'complete': m.toggleCompleted, 'bold': m.toggleBold,
                              'bookmark': lambda: m.toggleBookmark(source),
                              'progress': lambda: m.toggleMeasureProgress(source),
                              'promote': m.createTabFromSelected, 'delete': m.deleteSelected}
                result = operations[action]()
            elif action == 'move':
                target = self.string(data, 'target')
                placement = self.string(data, 'placement', 'child')
                if not m._find(target) or placement not in ('child', 'before', 'after') or n is m.view_root:
                    raise ApiError(400, 'Invalid move destination.')
                result = m.moveNode(node_id, target, placement)
            elif action == 'side':
                side = self.string(data, 'side')
                if side not in ('left', 'right'):
                    raise ApiError(400, 'Invalid branch side.')
                result = m.setSide(side)
            elif action == 'reference':
                if goal is None:
                    raise ApiError(400, 'Goal no longer exists.')
                result = m.addTabReference(node_id, goal_id)
            elif action == 'import':
                result = m.importBranchText(node_id, self.string(data, 'text'))
            elif action == 'export':
                text = outline_to_opml(n, n.text) if data.get('format') == 'opml' else outline_to_indented_text(n)
                return dict(revision=self.revision, text=text, saved=not pm.hasUnsavedChanges())
            elif action == 'reminder':
                at = self.string(data, 'at', '')
                result = pm.setMindmapReminder(source, at, data.get('notify') is True) if at else m.clearReminder(source)
            elif action == 'deadline':
                minutes = self.integer(data, 'minutes', low=0, high=525600)
                result = m.setDeadline(source, minutes) if minutes else m.clearDeadline(source)
            elif action == 'schedule':
                day = self.integer(data, 'weekday', low=-1, high=6)
                result = m.scheduleNodeToWeekday(source, day) if day >= 0 else m.cancelPlanSchedule(source)
            elif action in ('undo','redo'):
                result = m.undo() if action == 'undo' else m.redo()
            elif action == 'goal_add':
                tabs.addTab(self.string(data, 'title'))
            elif action in ('goal_rename','goal_delete','goal_range'):
                if goal is None:
                    raise ApiError(400, 'Goal no longer exists.')
                if action == 'goal_rename':
                    tabs.renameTab(goal_index, self.string(data, 'title'))
                elif action == 'goal_delete':
                    tabs.removeTab(goal_index)
                else:
                    start, end = self.string(data, 'start', ''), self.string(data, 'end', '')
                    result = tabs.setGoalRange(goal_id, start, end) if start or end else tabs.clearGoalRange(goal_id)
            elif action == 'markdown':
                entries = data.get('tabs')
                if not isinstance(entries, list) or not entries or any(not isinstance(t, dict) or
                        not isinstance(t.get('name'), str) or not isinstance(t.get('text'), str) for t in entries):
                    raise ApiError(400, 'Invalid Markdown tabs.')
                if goal_id:
                    if goal is None:
                        raise ApiError(400, 'Goal no longer exists.')
                    goal.markdown_tabs = normalize_editor_tabs(entries)
                    pm.currentTabMarkdownTabsChanged.emit()
                else:
                    pm.setWorkspaceMarkdownTabs(entries)
            elif action in ('kanban','duration'):
                item = self.string(data, 'item')
                status = self.string(data, 'status', 'unscheduled')
                if status not in ('unscheduled','todo','ready','in_progress','done'):
                    raise ApiError(400, 'Invalid Kanban lane.')
                result = (pm.setKanbanItemDuration(item, self.integer(data, 'duration', 1, low=1, high=24))
                          if action == 'duration' else pm.removeKanbanItem(item) if status == 'unscheduled' else pm.setKanbanItemPlacement(item, status,
                          self.integer(data, 'hour', -1, low=-1, high=23)))
            elif action == 'standalone_reminder':
                index = self.integer(data, 'index', -1)
                at = self.string(data, 'at', '')
                if index >= 0 and not at:
                    pm.clearStandaloneReminder(index)
                elif index >= 0:
                    result = pm.updateStandaloneReminder(index, self.string(data, 'title'), at, data.get('notify') is True)
                else:
                    result = pm.addStandaloneReminder(self.string(data, 'title'), at, data.get('notify') is True)
            elif action == 'task_reminder':
                if goal is None:
                    raise ApiError(400, 'Goal no longer exists.')
                index = self.integer(data, 'index', low=0)
                at = self.string(data, 'at', '')
                result = pm.setReminder(goal_index, index, at, data.get('notify') is True) if at else pm.clearReminder(goal_index, index)
            elif action != 'save':
                raise ApiError(400, 'Unknown action.')
            if result is False or m._last_commit_error:
                raise ApiError(400, m._last_commit_error or 'This change is not valid.')
        m.sceneChanged.emit()
        m.changed.emit()
        m.planChanged.emit()
        self.sync_revision()
        saved = pm.saveCurrentProject()
        self.sync_revision()
        return dict(revision=self.revision, saved=saved, nodeId=created_node,
                    message='' if saved else 'Edit applied, but saving failed. Retry Save.')


class ActionDrawServer(QObject):
    changed = Signal()
    request = Signal(object)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.pm = manager
        self.api = ProjectApi(manager)
        self._thread = None
        self._loop = None
        self._halt = None
        self._token = ''
        self._url = self._qr = self._error = self._address = ''
        self._epoch = 0
        self._running = False
        self.request.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)
        manager.projectAccessEnding.connect(self.stop)
        app = QGuiApplication.instance()
        if app:
            app.aboutToQuit.connect(self.stop)

    @Property(bool, notify=changed)
    def running(self):
        return self._running

    @Property(str, notify=changed)
    def boundAddress(self):
        return self._address

    @Property(str, notify=changed)
    def url(self):
        return self._url

    @Property(str, notify=changed)
    def qr(self):
        return self._qr

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property('QVariantList', notify=changed)
    def addresses(self):
        addresses = []
        for interface in QNetworkInterface.allInterfaces():
            if not interface.flags() & QNetworkInterface.InterfaceFlag.IsUp:
                continue
            for entry in interface.addressEntries():
                ip = entry.ip()
                if ip.protocol() != QAbstractSocket.NetworkLayerProtocol.IPv4Protocol or ip.isLoopback():
                    continue
                address = ip.toString()
                tail = 'tailscale' in interface.name().lower()
                addresses.append(dict(address=address, label=f'{interface.humanReadableName()} — {address}', tailscale=tail))
        addresses.sort(key=lambda a: (not a['tailscale'], a['address']))
        return addresses or [dict(address='127.0.0.1', label='Localhost (no network interface)', tailscale=False)]

    @Slot(result=bool)
    def prepare(self):
        if not self.pm.currentFilePath:
            return False
        return self.pm.saveCurrentProject()

    @Slot(str, int, result=bool)
    def start(self, address, port):
        if self._running:
            return True
        self._error = ''
        if address not in [a['address'] for a in self.addresses] or not 1 <= port <= 65535:
            self._error = 'Select a local network interface and a port between 1 and 65535.'
        elif (not self.pm.currentFilePath or self.pm._cached_key_material is None
              or self.pm._cached_encryption_file_path != self.pm.currentFilePath):
            self._error = 'Save and unlock the project on the desktop before starting.'
        if self._error:
            self.changed.emit()
            return False
        try:
            import qrcode
            import qrcode.image.svg
            self._epoch += 1
            self._token = secrets.token_urlsafe(32)
            self._address = address
            self._url = f'http://{address}:{port}/#key={self._token}'
            buffer = io.BytesIO()
            qrcode.make(self._url, image_factory=qrcode.image.svg.SvgPathImage).save(buffer)
            self._qr = 'data:image/svg+xml;base64,' + base64.b64encode(buffer.getvalue()).decode()
            ready = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(address, port, ready), daemon=True,
                                            name='ActionDraw HTTP')
            self._thread.start()
            if not ready.wait(5):
                raise RuntimeError('Server startup timed out.')
            if self._error:
                raise RuntimeError(self._error)
            self._running = True
        except Exception as exc:
            self.stop()
            self._error = str(exc)
        self.changed.emit()
        return self._running

    @Slot()
    def copyLink(self):
        QGuiApplication.clipboard().setText(self._url)

    @Slot()
    def stop(self):
        self._epoch += 1
        self._running = False
        self._token = self._url = self._qr = self._address = ''
        if self._loop and self._halt and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._halt.set)
        if self._thread:
            self._thread.join(timeout=3)
        self._thread = None
        self.api.clear_cache()
        self.changed.emit()

    @Slot(object)
    def _dispatch(self, request):
        future, epoch, operation, payload = request
        if not future.set_running_or_notify_cancel():
            return
        try:
            if not self._running or epoch != self._epoch:
                raise ApiError(401, 'Server access has ended.')
            result = self.api.state(payload) if operation == 'state' else self.api.command(payload)
            future.set_result(result)
        except Exception as exc:
            future.set_exception(exc)

    async def _call(self, operation, payload=None):
        future = Future()
        self.request.emit((future, self._epoch, operation, payload))
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout=30)

    def _run(self, address, port, ready):
        try:
            asyncio.run(self._serve(address, port, ready))
        except Exception as exc:
            self._error = f'Cannot start server: {exc}'
            ready.set()
        finally:
            self._loop = self._halt = None

    async def _serve(self, address, port, ready):
        from aiohttp import web
        self._loop = asyncio.get_running_loop()
        self._halt = asyncio.Event()
        origin = f'http://{address}:{port}'

        @web.middleware
        async def guard(request, handler):
            headers = {'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                       'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                       'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"}
            try:
                if request.host != f'{address}:{port}':
                    raise ApiError(403, 'Invalid host.')
                if request.headers.get('Origin', origin) != origin or request.headers.get('Sec-Fetch-Site') == 'cross-site':
                    raise ApiError(403, 'Cross-origin access is not allowed.')
                if request.path.startswith('/api/'):
                    expected = 'Bearer ' + self._token
                    if not self._token or not hmac.compare_digest(request.headers.get('Authorization',''), expected):
                        raise ApiError(401, 'Scan the current QR code to connect.')
                response = await handler(request)
            except ApiError as exc:
                response = web.json_response({'error': exc.message}, status=exc.status)
            except (ValueError, TypeError, KeyError):
                response = web.json_response({'error': 'Invalid request.'}, status=400)
            except asyncio.TimeoutError:
                response = web.json_response({'error': 'Desktop is busy. Refresh before trying again.'}, status=503)
            except web.HTTPException as exc:
                response = web.json_response({'error': exc.reason}, status=exc.status)
            except Exception:
                response = web.json_response({'error': 'Could not complete this request. Refresh to check its result.'}, status=500)
            response.headers.update(headers)
            return response

        async def state(request):
            since = request.query.get('since')
            if since is not None:
                try:
                    since = int(since)
                except ValueError:
                    raise ApiError(400, 'Invalid revision.')
                if since < 0:
                    raise ApiError(400, 'Invalid revision.')
            return web.json_response(await self._call('state', since))

        async def command(request):
            if request.content_type != 'application/json':
                raise ApiError(400, 'Expected JSON.')
            return web.json_response(await self._call('command', await request.json()))

        async def asset(request):
            name = request.match_info.get('name') or 'index.html'
            if name not in ('index.html','app.js','style.css'):
                raise web.HTTPNotFound()
            mime = {'index.html':'text/html','app.js':'text/javascript','style.css':'text/css'}[name]
            return web.Response(body=(Path(__file__).parent / 'web' / name).read_bytes(), content_type=mime)

        app = web.Application(middlewares=[guard], client_max_size=1024*1024)
        app.router.add_get('/api/state', state)
        app.router.add_post('/api/command', command)
        app.router.add_get('/', asset)
        app.router.add_get('/{name}', asset)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=1)
        await runner.setup()
        try:
            await web.TCPSite(runner, address, port).start()
            ready.set()
            await self._halt.wait()
        finally:
            await runner.cleanup()
