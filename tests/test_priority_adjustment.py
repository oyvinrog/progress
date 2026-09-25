"""Weighted priority scoring, project persistence, and live plot adjustments."""
import copy
import json
import math

import pytest
from PySide6.QtCore import QMetaObject, QObject, QPoint, Qt
from PySide6.QtTest import QTest

from actiondraw.model import DiagramModel
from actiondraw.priorityplot.model import compute_priority_score, normalize_priority_weight
from actiondraw.ui import create_actiondraw_window
from progress_crypto import EncryptionCredentials, decrypt_project_data
from task_model import ProjectManager, Tab, TabModel, TaskModel


def make_tabs():
    return [Tab(name=name, tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
                priority_subjective_value=value, priority_time_hours=hours)
            for name, value, hours in [('Quick', 3, math.e), ('Valuable', 8, math.e ** 2)]]


@pytest.fixture
def project(app):
    tasks = TaskModel()
    tabs = TabModel()
    tabs.setTabs(make_tabs())
    diagram = DiagramModel(tasks)
    manager = ProjectManager(tasks, diagram, tabs)
    return manager, tabs, tasks, diagram


def test_weighted_formula_and_zero_factors():
    assert compute_priority_score(8, math.e ** 2) == pytest.approx(4)
    assert compute_priority_score(8, math.e ** 2, 2, 1) == pytest.approx(32)
    assert compute_priority_score(8, math.e ** 2, 1, 2) == pytest.approx(2)
    assert compute_priority_score(8, math.e ** 2, 0, 1) == pytest.approx(.5)
    assert compute_priority_score(8, math.e ** 2, 1, 0) == 8
    assert compute_priority_score(0, math.e, 0, 0) == 1
    assert compute_priority_score(0, math.e, 1, 0) == 0
    assert compute_priority_score(-3, 0) == 0
    assert math.isfinite(compute_priority_score(3, 0, 2, 2))


@pytest.mark.parametrize('value,expected', [(None, 1), ('bad', 1), (float('nan'), 1),
                                          (float('inf'), 1), (-2, 0), (4, 2), (.7, .7)])
def test_weight_normalization(value, expected):
    assert normalize_priority_weight(value) == expected


def test_deflate_values_spreads_included_tabs_and_preserves_state(project):
    _, tabs, _, _ = project
    source = [
        Tab(name='Low', tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=8, priority_time_hours=2),
        Tab(name='Middle', tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=9, priority_time_hours=4),
        Tab(name='High', tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=10, priority_time_hours=6),
        Tab(name='Excluded', tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=100, priority_time_hours=7, include_in_priority_plot=False),
    ]
    tabs.setTabs(source)
    tabs.setCurrentTab(1)
    active_id = tabs.getCurrentTabData().id
    original_times = {tab.id: tab.priority_time_hours for tab in tabs.getAllTabs()}

    tabs.deflatePriorityValues()

    by_name = {tab.name: tab for tab in tabs.getAllTabs()}
    assert {name: by_name[name].priority_subjective_value
            for name in ('Low', 'Middle', 'High')} == pytest.approx({
                'Low': 2, 'Middle': 5, 'High': 8,
            })
    assert by_name['Excluded'].priority_subjective_value == 100
    assert {tab.id: tab.priority_time_hours for tab in tabs.getAllTabs()} == original_times
    assert tabs.getCurrentTabData().id == active_id
    for tab in tabs.getAllTabs():
        expected = (compute_priority_score(tab.priority_subjective_value, tab.priority_time_hours)
                    if tab.include_in_priority_plot else 0)
        assert tab.priority_score == pytest.approx(expected)


@pytest.mark.parametrize('values', [[0.01, 0.02], [100, 200], [2, 8]])
def test_deflate_low_high_and_existing_target_ranges(values):
    tabs = TabModel()
    tabs.setTabs([
        Tab(name=str(index), tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=value, priority_time_hours=math.e)
        for index, value in enumerate(values)
    ])

    tabs.deflatePriorityValues()

    assert sorted(tab.priority_subjective_value for tab in tabs.getAllTabs()) == pytest.approx([2, 8])


@pytest.mark.parametrize('values', [[9], [9, 9, 9]])
def test_deflate_equal_or_single_values_centers_them(values):
    tabs = TabModel()
    tabs.setTabs([
        Tab(name=str(index), tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
            priority_subjective_value=value)
        for index, value in enumerate(values)
    ])

    tabs.deflatePriorityValues()

    assert [tab.priority_subjective_value for tab in tabs.getAllTabs()] == [5] * len(values)


def test_deflate_no_included_tabs_is_a_noop():
    tabs = TabModel()
    only = Tab(name='Excluded', tasks={'tasks': []}, diagram={'items': [], 'edges': [], 'strokes': []},
               priority_subjective_value=10, include_in_priority_plot=False)
    tabs.setTabs([only])

    tabs.deflatePriorityValues()

    assert not tabs.hasIncludedPriorityTabs
    assert tabs.getAllTabs()[0].priority_subjective_value == 10


def test_live_scores_ties_exclusion_and_restored_tabs(project):
    pm, tabs, _, _ = project
    active_id = tabs.getCurrentTabData().id
    history = copy.deepcopy(tabs.getAllTabs())
    tabs.setPriorityWeights(1, 2)
    assert [t.name for t in tabs.getAllTabs()] == ['Quick', 'Valuable']
    tabs.setPriorityWeights(2, 1)
    assert [t.name for t in tabs.getAllTabs()] == ['Valuable', 'Quick']
    assert tabs.getCurrentTabData().id == active_id
    tabs.setPriorityWeights(0, 0)
    assert [t.name for t in tabs.getAllTabs()] == ['Valuable', 'Quick']
    assert [t.priority_score for t in tabs.getAllTabs()] == [1, 1]
    tabs.setIncludeInPriorityPlot(0, False)
    assert tabs.priorityRanks == [1, 0]
    tabs.setPriorityWeights(2, 2)
    assert tabs.getAllTabs()[-1].priority_score == 0
    tabs.restoreMindmapTabs(history, 0)
    assert [t.name for t in tabs.getAllTabs()] == ['Quick', 'Valuable']
    assert [t.priority_score for t in tabs.getAllTabs()] == pytest.approx([9, 16])
    ranks = {pm.mindmap.links[n['id']]: n['priorityRank'] for n in pm.mindmap.nodes if n['isTab']}
    assert [ranks[t.id] for t in tabs.getAllTabs()] == [2, 1]
    tabs.addTab('New')
    new = tabs.getAllTabs()[-1]
    assert new.priority_score == compute_priority_score(new.priority_subjective_value, new.priority_time_hours, 2, 2)
    tabs.clear()
    assert (tabs.priorityValueWeight, tabs.priorityTimeWeight) == (1, 1)


def test_adjustment_encrypted_roundtrip_and_legacy_switch(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='priority-adjustment-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *args: credentials)
    path = tmp_path / 'weights.progress'
    assert pm.saveProject(str(path))
    assert not pm.hasUnsavedChanges()
    tabs.setPriorityWeights(.4, 1.8)
    assert pm.hasUnsavedChanges()
    expected = {tab.id: tab.priority_score for tab in tabs.getAllTabs()}
    assert pm.saveProject(str(path))
    payload = decrypt_project_data(json.loads(path.read_text()), credentials)
    assert payload['priority_scoring'] == {'value_weight': .4, 'time_weight': 1.8}
    tabs.setPriorityWeights(2, 0)
    pm.loadProject(str(path))
    assert (tabs.priorityValueWeight, tabs.priorityTimeWeight) == (.4, 1.8)
    assert {tab.id: tab.priority_score for tab in tabs.getAllTabs()} == pytest.approx(expected)
    assert not pm.hasUnsavedChanges()
    del payload['priority_scoring']
    legacy = tmp_path / 'legacy.progress'
    legacy.write_text(json.dumps(payload))
    pm.loadProject(str(legacy))
    assert (tabs.priorityValueWeight, tabs.priorityTimeWeight) == (1, 1)
    for tab in tabs.getAllTabs():
        assert tab.priority_score == compute_priority_score(tab.priority_subjective_value, tab.priority_time_hours)
    assert not pm.hasUnsavedChanges()


def test_deflated_values_mark_dirty_and_roundtrip(project, tmp_path, monkeypatch):
    pm, tabs, _, _ = project
    credentials = EncryptionCredentials(passphrase='priority-deflation-test')
    monkeypatch.setattr(pm, '_prompt_encryption_credentials', lambda *args: credentials)
    path = tmp_path / 'deflated.progress'
    assert pm.saveProject(str(path))
    assert not pm.hasUnsavedChanges()

    tabs.deflatePriorityValues()
    expected = {tab.id: tab.priority_subjective_value for tab in tabs.getAllTabs()}
    assert pm.hasUnsavedChanges()
    assert pm.saveProject(str(path))

    tabs.setPriorityPoint(0, math.e, 10)
    pm.loadProject(str(path))
    assert {tab.id: tab.priority_subjective_value for tab in tabs.getAllTabs()} == pytest.approx(expected)
    assert not pm.hasUnsavedChanges()


@pytest.mark.parametrize('settings,expected', [
    ({'value_weight': 'bad', 'time_weight': None}, (1, 1)),
    ({'value_weight': -1, 'time_weight': 4}, (0, 2)),
    ([], (1, 1)),
])
def test_loaded_weights_are_normalized(project, settings, expected):
    _, tabs, _, _ = project
    tabs.setPriorityWeights(.5, .5)
    tabs.setTabs(make_tabs(), priority_scoring=settings)
    assert (tabs.priorityValueWeight, tabs.priorityTimeWeight) == expected
    for tab in tabs.getAllTabs():
        assert tab.priority_score == compute_priority_score(tab.priority_subjective_value, tab.priority_time_hours, *expected)


def find_item(item, name):
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = find_item(child, name)
        if found is not None:
            return found


def test_qml_adjustments_keep_selection_and_matching_ranks(project, app):
    pm, tabs, tasks, diagram = project
    engine = create_actiondraw_window(diagram, tasks, pm, tab_model=tabs)
    warnings = []
    engine.warnings.connect(lambda messages: warnings.extend(m.toString() for m in messages))
    window = engine.rootObjects()[0]
    QMetaObject.invokeMethod(window, 'openPriorityPlotWindow')
    plot = window.property('priorityPlotWindowRef')
    plot.show()
    plot.requestActivate()
    QTest.qWait(80)
    plot.setProperty('selectedTabIndex', 0)
    selected_id = tabs.getAllTabs()[0].id
    active_id = tabs.getCurrentTabData().id
    value = plot.findChild(QObject, 'priorityValueWeightSlider')
    time = plot.findChild(QObject, 'priorityTimeWeightSlider')
    reset = plot.findChild(QObject, 'priorityAdjustmentReset')
    deflate = plot.findChild(QObject, 'priorityDeflateValueButton')
    deflate_dialog = plot.findChild(QObject, 'priorityDeflateValueDialog')
    deflate_explanation = plot.findChild(QObject, 'priorityDeflateValueExplanation')
    try:
        value.forceActiveFocus()
        QTest.keyClick(plot, Qt.Key_Right)
        assert tabs.priorityValueWeight == pytest.approx(1.1)
        assert tabs.getAllTabs()[plot.property('selectedTabIndex')].id == selected_id
        time.forceActiveFocus()
        QTest.keyClick(plot, Qt.Key_Right)
        assert tabs.priorityTimeWeight == pytest.approx(1.1)
        # Mouse adjustment reaches an endpoint and stays synchronized with the model.
        position = value.mapToScene(value.boundingRect().center())
        QTest.mouseClick(plot, Qt.LeftButton, pos=QPoint(int(position.x() + value.width() / 2 - 8), int(position.y())))
        assert tabs.priorityValueWeight > 1.1
        tabs.setPriorityWeights(1, 2)
        QTest.qWait(20)
        assert value.property('value') == 1
        assert time.property('value') == 2
        assert tabs.getAllTabs()[plot.property('selectedTabIndex')].id == selected_id
        assert tabs.getCurrentTabData().id == active_id
        nodes = {pm.mindmap.links[n['id']]: n for n in pm.mindmap.nodes if n['isTab']}
        for index, tab in enumerate(tabs.getAllTabs()):
            point = find_item(plot.contentItem(), 'priorityPlotPoint_' + str(index))
            assert point.property('priorityRank') == nodes[tab.id]['priorityRank']
            assert point.property('pointTime') == tab.priority_time_hours
            assert point.property('pointValue') == tab.priority_subjective_value
        reset.forceActiveFocus()
        QTest.keyClick(plot, Qt.Key_Space)
        assert (tabs.priorityValueWeight, tabs.priorityTimeWeight) == (1, 1)
        assert (value.property('value'), time.property('value')) == (1, 1)
        assert tabs.getAllTabs()[plot.property('selectedTabIndex')].id == selected_id
        assert deflate.property('text') == 'Deflate Value'
        assert '2–8 range' in deflate_explanation.property('text')
        before = {tab.id: tab.priority_subjective_value for tab in tabs.getAllTabs()}
        deflate.forceActiveFocus()
        QTest.keyClick(plot, Qt.Key_Space)
        QTest.qWait(20)
        assert deflate_dialog.property('visible')
        QMetaObject.invokeMethod(deflate_dialog, 'reject')
        assert {tab.id: tab.priority_subjective_value for tab in tabs.getAllTabs()} == before
        deflate.forceActiveFocus()
        QTest.keyClick(plot, Qt.Key_Space)
        QTest.qWait(20)
        QMetaObject.invokeMethod(deflate_dialog, 'accept')
        QTest.qWait(20)
        values_by_name = {tab.name: tab.priority_subjective_value for tab in tabs.getAllTabs()}
        assert values_by_name == pytest.approx({'Quick': 2, 'Valuable': 8})
        assert tabs.getAllTabs()[plot.property('selectedTabIndex')].id == selected_id
        assert tabs.getCurrentTabData().id == active_id
        included_ids = [tab.id for tab in tabs.getAllTabs() if tab.include_in_priority_plot]
        for tab_id in included_ids:
            index = next(i for i, tab in enumerate(tabs.getAllTabs()) if tab.id == tab_id)
            tabs.setIncludeInPriorityPlot(index, False)
        QTest.qWait(20)
        assert not deflate.property('enabled')
        assert not warnings
    finally:
        plot.close()
        window.close()
