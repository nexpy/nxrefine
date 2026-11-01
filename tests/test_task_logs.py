import os
import time

import pytest

from nxrefine.nxserver import NXServer, task_matches


class LogServer(NXServer):
    """A server that only lists the logs in a directory."""

    def __init__(self, log_directory, log_limit=50, log_days=0):
        self.log_directory = log_directory
        self.monitoring_db = log_directory / 'monitoring.db'
        self.log_limit = log_limit
        self.log_days = log_days


def make_log(directory, name, age_days=0, text=''):
    out = directory / f'{name}.out'
    out.write_text(text)
    directory.joinpath(f'{name}.err').write_text('')
    mtime = time.time() - age_days * 86400
    os.utime(out, (mtime, mtime))
    return out


@pytest.fixture
def log_directory(tmp_path):
    directory = tmp_path / 'task_logs'
    directory.mkdir()
    return directory


@pytest.mark.parametrize('name, expected', [
    ('cno_bg_1_30K_nxreduce_f1_20261031_152336', True),
    ('cno_bg_1_30K_nxreduce_f1_f2_f3_20261031_152336_1', True),
    ('nxreduce_bg_1_30K_f1_20260918_100636', True),
    ('cno_bg_1_130K_nxreduce_f1_20261031_152336', False),
    ('nxreduce_bg_1_130K_f1_20260918_100636', False),
    ('abc_bg_1_30K_nxreduce_f1_20261031_152336', False),
    ('cno_bg_2_30K_nxreduce_f1_20261031_152336', False),
    ('echo_a_b_20260918_101847', False),
])
def test_task_matches(name, expected):
    assert task_matches(name, 'cno', 'bg_1', '30K') is expected


def test_limit_keeps_the_newest(log_directory):
    for i in range(5):
        make_log(log_directory, f'log{i}', age_days=5 - i)
    server = LogServer(log_directory, log_limit=3)
    assert server.task_names() == ['log4', 'log3', 'log2']


def test_zero_limit_lists_everything(log_directory):
    for i in range(5):
        make_log(log_directory, f'log{i}', age_days=5 - i)
    server = LogServer(log_directory, log_limit=0)
    assert len(server.task_names()) == 5


def test_days_hides_old_logs(log_directory):
    make_log(log_directory, 'new', age_days=1)
    make_log(log_directory, 'old', age_days=10)
    server = LogServer(log_directory, log_days=7)
    assert server.task_names() == ['new']
    assert LogServer(log_directory, log_days=0).task_names() == ['new', 'old']


def test_limit_and_days_together(log_directory):
    for i in range(4):
        make_log(log_directory, f'new{i}', age_days=i)
    make_log(log_directory, 'old', age_days=30)
    server = LogServer(log_directory, log_limit=2, log_days=7)
    assert server.task_names() == ['new0', 'new1']


def test_match_applies_before_the_limit(log_directory):
    make_log(log_directory, 'cno_bg_1_30K_nxreduce_f1_a', age_days=5)
    for i in range(3):
        make_log(log_directory, f'cno_bg_1_60K_nxreduce_f1_{i}', age_days=i)
    server = LogServer(log_directory, log_limit=2)
    names = server.task_names(
        match=lambda name: task_matches(name, 'cno', 'bg_1', '30K'))
    assert names == ['cno_bg_1_30K_nxreduce_f1_a']


def test_task_output_finds_logs_outside_the_limit(log_directory):
    make_log(log_directory, 'old', age_days=30, text='old output')
    make_log(log_directory, 'new', text='new output')
    server = LogServer(log_directory, log_limit=1, log_days=7)
    assert server.task_names() == ['new']
    assert 'old output' in server.task_output('old')


@pytest.fixture
def log_combo():
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    QtWidgets = pytest.importorskip('qtpy.QtWidgets')
    pytest.importorskip('nexpy.gui.widgets')
    from nexpy.gui.widgets import NXComboBox

    from nxrefine.plugins.server.manage_workflows import (NO_LOGS,
                                                          WorkflowDialog)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    state = type('State', (), {})()
    state.names = []
    state.calls = []
    state.output_box = QtWidgets.QPlainTextEdit()
    state.server = type('Server', (), {
        'task_output': lambda self, name: f'output of {name}'})()
    state.current_log_names = lambda: state.names
    state.update_logs = lambda: WorkflowDialog.update_logs(state)
    state.log_combo = NXComboBox()
    state.log_combo.add(NO_LOGS)
    state.log_combo.setCurrentIndex(0)
    state.log_combo.setEnabled(False)

    def taskview():
        state.calls.append(1)
        WorkflowDialog.taskview(state)
    state.log_combo.currentIndexChanged.connect(taskview)
    state.NO_LOGS = NO_LOGS
    state.update = lambda: WorkflowDialog.update_logs(state)
    state.view = lambda: WorkflowDialog.taskview(state)
    state.app = app
    return state


def test_log_list_changes_do_not_trigger_the_task_view(log_combo):
    for names in (['a', 'b'], ['b', 'c'], [], ['x']):
        log_combo.names = names
        log_combo.update()
        assert log_combo.log_combo.items() == (names or [log_combo.NO_LOGS])
        assert log_combo.log_combo.isEnabled() is bool(names)
    assert log_combo.calls == []


def test_selection_is_kept_when_still_listed(log_combo):
    log_combo.names = ['a', 'b', 'c']
    log_combo.update()
    log_combo.log_combo.select('b')
    log_combo.names = ['b', 'c']
    log_combo.update()
    assert log_combo.log_combo.selected == 'b'


def test_task_view_ignores_the_placeholder(log_combo):
    log_combo.view()
    assert log_combo.output_box.toPlainText() == 'No Logs'
    log_combo.names = ['a']
    log_combo.view()
    assert log_combo.output_box.toPlainText() == 'output of a'
