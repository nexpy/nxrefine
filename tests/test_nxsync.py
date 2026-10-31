import pytest
from nexusformat.nexus import NXentry, nxopen

from nxrefine.nxdatabase import NXDatabase
from nxrefine.scripts import nxsync


@pytest.fixture
def experiment(tmp_path):
    scan_dir = tmp_path / 'sample' / 'label' / 'scan'
    scan_dir.mkdir(parents=True)
    (tmp_path / 'tasks').mkdir()
    wrapper = scan_dir.parent / 'sample_scan.nxs'
    with nxopen(wrapper, 'w') as root:
        root['entry'] = NXentry()
        root['f1'] = NXentry()
        root['f2'] = NXentry()
    return tmp_path, scan_dir, wrapper


def run(monkeypatch, capsys, *args):
    monkeypatch.setattr('sys.argv', ['nxsync', *args])
    with pytest.raises(SystemExit) as exit_info:
        nxsync.main()
    captured = capsys.readouterr()
    return exit_info.value.code, captured.out, captured.err


def tracked_entries(experiment_directory):
    db = NXDatabase(experiment_directory / 'tasks' / 'nxdatabase.db')
    f = db.query('sample/label/sample_scan.nxs')
    return None if f is None else f.get_entries()


def test_scan_file_from_directory(experiment):
    _, scan_dir, wrapper = experiment
    assert nxsync.scan_file(scan_dir) == wrapper


def test_sync_directory(experiment, monkeypatch, capsys):
    root, scan_dir, wrapper = experiment
    code, out, err = run(monkeypatch, capsys, '-d', str(scan_dir))
    assert (code, err) == (0, '')
    assert out.strip() == f"Synchronized {wrapper.resolve()}"
    assert tracked_entries(root.resolve()) == ['f1', 'f2']


def test_sync_file(experiment, monkeypatch, capsys):
    root, _, wrapper = experiment
    code, out, err = run(monkeypatch, capsys, '-f', str(wrapper))
    assert (code, err) == (0, '')
    assert tracked_entries(root.resolve()) == ['f1', 'f2']


def test_missing_scan_file_fails_but_others_sync(experiment, monkeypatch,
                                                 capsys):
    root, scan_dir, wrapper = experiment
    missing = scan_dir.parent / 'sample_missing.nxs'
    code, out, err = run(monkeypatch, capsys, '-f', str(missing),
                         str(wrapper))
    assert code == 1
    assert 'nxsync: sample_missing.nxs' in err
    assert tracked_entries(root.resolve()) == ['f1', 'f2']


def test_unfinished_tasks(experiment):
    root, _, wrapper = experiment
    db = NXDatabase(root.resolve() / 'tasks' / 'nxdatabase.db')
    assert db.unfinished_tasks(wrapper) == {}
    db.update_file(wrapper)
    assert db.unfinished_tasks(wrapper) == {}
    db.queue_task(wrapper, 'nxlink', 'f1')
    assert db.unfinished_tasks(wrapper) == {'nxlink': db.QUEUED}
    db.start_task(wrapper, 'nxmax', 'f1')
    db.fail_task(wrapper, 'nxmax', 'f1')
    assert db.unfinished_tasks(wrapper) == {'nxlink': db.QUEUED,
                                            'nxmax': db.FAILED}


def test_sync_reports_reset_tasks(experiment, monkeypatch, capsys):
    root, scan_dir, wrapper = experiment
    db = NXDatabase(root.resolve() / 'tasks' / 'nxdatabase.db')
    db.update_file(wrapper)
    db.queue_task(wrapper, 'nxlink', 'f1')
    code, out, err = run(monkeypatch, capsys, '-d', str(scan_dir))
    assert (code, err) == (0, '')
    assert 'Reset to match the file: nxlink (queued)' in out
    assert NXDatabase(root.resolve() / 'tasks' /
                      'nxdatabase.db').unfinished_tasks(wrapper) == {}


def test_sync_reports_nothing_to_reset(experiment, monkeypatch, capsys):
    _, scan_dir, _ = experiment
    code, out, err = run(monkeypatch, capsys, '-d', str(scan_dir))
    assert 'Reset' not in out
