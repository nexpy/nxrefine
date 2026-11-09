import pytest

from nxrefine.nxserver import NXServer
from nxrefine.parsl import (LARGE, LOCAL, SMALL, block_nodes, label_nodes,
                            large_executor, large_label, polaris,
                            select_executor)


def options(**kwargs):
    return {'server_type': 'multinode', 'account': 'project', **kwargs}


@pytest.mark.parametrize('ntasks, nodes', [
    (5, 10), (10, 10), (12, 12), (24, 24), (25, 13), (30, 15), (48, 24),
    (49, 17), (96, 24)])
def test_block_nodes_fits_the_batch(ntasks, nodes):
    assert block_nodes(ntasks, 10, 24) == nodes


def test_block_nodes_holds_every_command_without_an_extra_block():
    for ntasks in range(1, 200):
        nodes = block_nodes(ntasks, 10, 24)
        blocks = -(-ntasks // nodes)
        assert 10 <= nodes <= 24
        assert blocks == max(-(-ntasks // 24), 1)


def test_large_label_round_trips():
    assert large_label(10, 10) == LARGE
    assert large_label(12, 10) == f'{LARGE}-12'
    assert label_nodes(large_label(12, 10)) == 12
    assert label_nodes(LARGE) is None
    assert label_nodes(SMALL) is None
    assert label_nodes('nx-large-x') is None


def test_default_blocks_have_large_nodes():
    for ntasks in (5, 12, 30, 100):
        assert select_executor(options(), ntasks) == LARGE
    assert select_executor(options(large_nodes=12), 30) == LARGE


def test_small_batches_and_local_servers_are_unchanged():
    assert select_executor(options(max_large_nodes=24), 4) == SMALL
    assert select_executor(options(batch_threshold=6), 6) == SMALL
    assert select_executor({'server_type': 'multicore'}, 30) == LOCAL


def test_generic_blocks_follow_the_batch_when_a_maximum_is_set():
    opts = options(max_large_nodes=24)
    assert select_executor(opts, 5) == LARGE
    assert select_executor(opts, 12) == f'{LARGE}-12'
    assert select_executor(opts, 30) == f'{LARGE}-15'
    assert select_executor(options(max_large_nodes=5), 12) == LARGE


def test_polaris_blocks_follow_the_batch_by_default():
    assert polaris.select_executor(options(), 3) == SMALL
    assert polaris.select_executor(options(), 5) == LARGE
    assert polaris.select_executor(options(), 12) == f'{LARGE}-12'
    assert polaris.select_executor(options(), 24) == f'{LARGE}-24'
    assert polaris.select_executor(options(), 30) == f'{LARGE}-15'
    assert polaris.select_executor(options(), 50) == f'{LARGE}-17'


def test_polaris_blocks_respect_the_settings():
    assert polaris.node_range(options()) == (10, 24)
    assert polaris.node_range(options(large_nodes=4)) == (10, 24)
    assert polaris.node_range(options(large_nodes=16)) == (16, 24)
    assert polaris.node_range(options(max_large_nodes=40)) == (10, 40)
    assert polaris.node_range(options(max_large_nodes=5)) == (10, 10)
    assert polaris.select_executor(options(max_large_nodes=10), 12) == LARGE


def test_large_executor_has_the_block_size_of_its_label():
    executor = large_executor(options(max_blocks=4), f'{LARGE}-12')
    assert executor.label == f'{LARGE}-12'
    assert executor.provider.nodes_per_block == 12
    assert executor.provider.max_blocks == 4
    assert executor.provider.queue == 'prod'


def test_large_executor_ignores_other_labels_and_servers():
    assert large_executor(options(), SMALL) is None
    assert large_executor({'server_type': 'multicore'}, f'{LARGE}-12') is None


def test_polaris_executor_has_the_block_size_of_its_label():
    executor = polaris.large_executor(options(), f'{LARGE}-12')
    assert executor.label == f'{LARGE}-12'
    assert executor.provider.nodes_per_block == 12
    assert executor.provider.queue == 'prod'
    assert polaris.large_executor(options(), LARGE) is None


class FakeKernel:

    def __init__(self):
        self.added = []

    def add_executors(self, executors):
        self.added.extend(executors)


class FakeModule:

    def __init__(self, factory=None):
        if factory:
            self.large_executor = factory


class StubServer(NXServer):

    parsl_options = options()

    def __init__(self, module):
        self._module = module
        self._apps = {SMALL: 'small', LARGE: 'large'}
        self.logged = []

    def log(self, message):
        self.logged.append(message)

    @staticmethod
    def define_app(label):
        return f'app {label}'


@pytest.fixture
def kernel(monkeypatch):
    kernel = FakeKernel()
    monkeypatch.setattr('parsl.dfk', lambda: kernel)
    return kernel


def test_server_adds_the_executor_a_batch_needs(kernel):
    server = StubServer(FakeModule(lambda opts, label: f'executor {label}'))
    server.add_executor(f'{LARGE}-12')
    assert kernel.added == [f'executor {LARGE}-12']
    assert server._apps[f'{LARGE}-12'] == f'app {LARGE}-12'


def test_server_without_a_factory_adds_nothing(kernel):
    server = StubServer(FakeModule())
    server.add_executor(f'{LARGE}-12')
    assert not kernel.added
    assert f'{LARGE}-12' not in server._apps


def test_server_ignores_a_label_the_module_does_not_recognize(kernel):
    server = StubServer(FakeModule(lambda opts, label: None))
    server.add_executor(f'{LARGE}-12')
    assert not kernel.added
    assert f'{LARGE}-12' not in server._apps


def test_server_logs_a_failure_to_add_an_executor(kernel):
    def fail(opts, label):
        raise ValueError('no queue')

    server = StubServer(FakeModule(fail))
    server.add_executor(f'{LARGE}-12')
    assert f'{LARGE}-12' not in server._apps
    assert 'no queue' in server.logged[-1]
