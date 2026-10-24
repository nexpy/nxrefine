from concurrent.futures import Future

import pytest

from nxrefine import nxserver
from nxrefine.nxserver import NXServer, NXTask


class StubServer(NXServer):
    """A server with a scripted queue and no Parsl, daemon or settings."""

    def __init__(self, commands, pending=()):
        self.commands = [NXTask(command) for command in commands]
        self.tasks = {Future(): NXTask(command) for command in pending}
        self.logged = []
        self.submitted = []
        self.requeued = []
        self.cancelled = False
        self.waited = None

    def log(self, message):
        self.logged.append(message)

    def read_task(self):
        return self.commands.pop(0) if self.commands else None

    def dispatch(self, task):
        self.submitted.append(task.command)

    def add_task(self, tasks, batch_id=None, batch_size=1):
        self.requeued.append(tasks)

    def cancel_blocks(self):
        self.cancelled = True
        super().cancel_blocks()

    def shutdown(self, wait=True):
        self.waited = wait


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(nxserver, 'POLL_INTERVAL', 0)


def test_drain_returns_when_nothing_is_pending():
    server = StubServer([])
    assert server.drain() is True
    assert server.waited is True
    assert not server.cancelled


def test_resume_leaves_pending_tasks_and_parsl_alone():
    server = StubServer(['resume'], pending=['nxreduce -d a'])
    assert server.drain() is False
    assert server.waited is None
    assert len(server.tasks) == 1
    assert not server.cancelled


def test_other_commands_are_dispatched_while_waiting():
    server = StubServer(['nxreduce -d b', 'resume'], pending=['nxreduce -d a'])
    assert server.drain() is False
    assert server.submitted == ['nxreduce -d b']


def test_repeated_stop_is_ignored():
    server = StubServer(['stop', 'resume'], pending=['nxreduce -d a'])
    assert server.drain() is False
    assert server.submitted == []


def test_abort_requeues_unfinished_tasks_without_waiting():
    server = StubServer(['abort'], pending=['nxreduce -d a', 'nxreduce -d b'])
    assert server.drain() is True
    assert server.cancelled
    assert server.waited is False
    assert server.requeued == ['nxreduce -d a', 'nxreduce -d b']
    assert server.tasks == {}


def test_abort_requested_before_waiting_starts():
    server = StubServer([], pending=['nxreduce -d a'])
    assert server.drain(abort=True) is True
    assert server.requeued == ['nxreduce -d a']


def test_finished_tasks_end_the_wait():
    server = StubServer([], pending=['nxreduce -d a'])
    for future in server.tasks:
        future.set_result(None)
    assert server.drain() is True
    assert server.waited is True
    assert server.tasks == {}
