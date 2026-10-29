import os
import time
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
from nexusformat.nexus import (NeXusError, NXdata, NXdetector, NXentry,
                               NXfield, NXinstrument, NXlink, nxopen)

from nxrefine.nxbeamline import Sector6Beamline
from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXReduce
from nxrefine.scripts import nxready

from test_settings import (make_directory_structure, make_parent_file,
                           make_wrapper_file)

FRAMES = 5


def add_orientation(root, entry_name='f1'):
    root[entry_name] = NXentry()
    root[entry_name]['instrument'] = NXinstrument()
    root[entry_name]['instrument/detector'] = NXdetector()
    root[entry_name]['instrument/detector/orientation_matrix'] = np.eye(3)


def age_file(path, seconds=3600):
    """Make a file look as if it was last modified ``seconds`` ago."""
    old = time.time() - seconds
    os.utime(path, (old, old))


class StubBeamline:
    """Beamline whose logs are always ready (or not, if set)."""

    def __init__(self, ready=True):
        self.ready = ready
        self.frames = None

    def logs_ready(self, frames=None, quiet_seconds=30):
        self.frames = frames
        return (True, []) if self.ready else (False, ["logs not ready"])


# ---------------------------------------------------------------------------
# NXParent
# ---------------------------------------------------------------------------

class TestNXParentReady:

    def test_has_transform_grid(self, tmp_path):
        path = tmp_path / 'sample_scans.nxs'
        make_parent_file(path)
        assert NXParent(path).has_transform_grid() is False
        with nxopen(path, 'rw') as root:
            root['entry/nxscans/transform'] = NXdata(axes=(
                NXfield([0.0, 1.0], name='Ql'),
                NXfield([0.0, 1.0], name='Qk'),
                NXfield([0.0, 1.0], name='Qh')))
        assert NXParent(path).has_transform_grid() is True

    def test_has_transform_grid_requires_all_axes(self, tmp_path):
        path = tmp_path / 'sample_scans.nxs'
        make_parent_file(path)
        with nxopen(path, 'rw') as root:
            root['entry/nxscans/transform'] = NXdata(axes=(
                NXfield([0.0, 1.0], name='Qk'),
                NXfield([0.0, 1.0], name='Qh')))
        assert NXParent(path).has_transform_grid() is False

    def test_has_orientation(self, tmp_path):
        path = tmp_path / 'sample_scans.nxs'
        make_parent_file(path)
        with nxopen(path, 'rw') as root:
            add_orientation(root, 'f1')
            root['f2'] = NXentry()
        parent = NXParent(path)
        assert parent.has_orientation('f1') is True
        assert parent.has_orientation('f2') is False
        assert parent.has_orientation('f3') is False


# ---------------------------------------------------------------------------
# Beamline logs
# ---------------------------------------------------------------------------

def make_sector6(directory):
    beamline = Sector6Beamline.__new__(Sector6Beamline)
    beamline.directory = directory
    beamline.entry = SimpleNamespace(nxname='f1')
    return beamline


def write_logs(directory, rows=FRAMES):
    head = directory / 'f1_head.txt'
    meta = directory / 'f1_meta.txt'
    head.write_text("Storage_Ring_Current, 101.5\nSCU_Current, 380.0\n")
    lines = ["MCS1, MCS2"] + [f"{i}, {2 * i}" for i in range(rows)]
    meta.write_text("\n".join(lines) + "\n")
    age_file(head)
    age_file(meta)
    return head, meta


class TestLogsReady:

    def test_ready(self, tmp_path):
        write_logs(tmp_path)
        ready, reasons = make_sector6(tmp_path).logs_ready(frames=FRAMES)
        assert ready is True
        assert reasons == []

    def test_missing_files(self, tmp_path):
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons == ["f1_head.txt does not exist",
                           "f1_meta.txt does not exist"]

    def test_one_file_missing(self, tmp_path):
        head, meta = write_logs(tmp_path)
        meta.unlink()
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons == ["f1_meta.txt does not exist"]

    def test_empty_file(self, tmp_path):
        head, meta = write_logs(tmp_path)
        meta.write_text("")
        age_file(meta)
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons == ["f1_meta.txt is empty"]

    def test_recently_modified(self, tmp_path):
        head, meta = write_logs(tmp_path)
        os.utime(meta, None)
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons[0].startswith("f1_meta.txt modified ")

    def test_quiet_period_can_be_disabled(self, tmp_path):
        head, meta = write_logs(tmp_path)
        os.utime(meta, None)
        ready, _ = make_sector6(tmp_path).logs_ready(quiet_seconds=0)
        assert ready is True

    def test_unreadable_head(self, tmp_path):
        head, meta = write_logs(tmp_path)
        head.write_text("Storage_Ring_Current 101.5\n")
        age_file(head)
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons[0].startswith("cannot read logs")

    def test_ragged_meta(self, tmp_path):
        head, meta = write_logs(tmp_path)
        with open(meta, 'a') as f:
            f.write("7\n")
        age_file(meta)
        ready, reasons = make_sector6(tmp_path).logs_ready()
        assert ready is False
        assert reasons[0].startswith("cannot read logs")

    def test_too_few_rows(self, tmp_path):
        write_logs(tmp_path, rows=FRAMES - 2)
        ready, reasons = make_sector6(tmp_path).logs_ready(frames=FRAMES)
        assert ready is False
        assert reasons == [f"f1_meta.txt has {FRAMES - 2} rows "
                           f"for {FRAMES} frames"]

    def test_extra_rows_allowed(self, tmp_path):
        write_logs(tmp_path, rows=FRAMES + 3)
        ready, _ = make_sector6(tmp_path).logs_ready(frames=FRAMES)
        assert ready is True


# ---------------------------------------------------------------------------
# NXReduce.link_ready and the nxready script
# ---------------------------------------------------------------------------

@pytest.fixture
def scan(tmp_path):
    """A registered scan with raw data, a parent matrix and a transform."""
    scan_dir, wrapper_file, parent_file, task_dir = (
        make_directory_structure(tmp_path))
    raw_file = scan_dir / 'f1.h5'
    with h5py.File(raw_file, 'w') as f:
        f.create_dataset('entry/data/data',
                         data=np.zeros((FRAMES, 4, 3), dtype=np.int32))
    age_file(raw_file)
    make_wrapper_file(wrapper_file, parent_name=parent_file.name)
    with nxopen(wrapper_file, 'rw') as root:
        root['f1'] = NXentry()
        root['f1/data'] = NXdata()
        root['f1/data/data'] = NXlink('/entry/data/data', file=raw_file)
        root['f1/data/frame_number'] = np.arange(FRAMES)
        root['f1/data/y_pixel'] = np.arange(4)
        root['f1/data/x_pixel'] = np.arange(3)
        root['f1/data'].nxsignal = root['f1/data/data']
        root['f1/data'].nxaxes = [root['f1/data/frame_number'],
                                  root['f1/data/y_pixel'],
                                  root['f1/data/x_pixel']]
    make_parent_file(parent_file)
    with nxopen(parent_file, 'rw') as root:
        add_orientation(root, 'f1')
        root['entry/nxscans/transform'] = NXdata(axes=(
            NXfield([0.0, 1.0], name='Ql'),
            NXfield([0.0, 1.0], name='Qk'),
            NXfield([0.0, 1.0], name='Qh')))
    return SimpleNamespace(directory=scan_dir, wrapper=wrapper_file,
                           parent=parent_file, raw=raw_file)


def link_ready(scan, beamline=None, **kwargs):
    """Return ((ready, messages), reduce) with the reason kinds separate."""
    reduce = NXReduce('f1', directory=scan.directory)
    reduce._beamline = beamline or StubBeamline()
    ready, reasons = reduce.link_ready(**kwargs)
    reduce.kinds = [kind for kind, message in reasons]
    return (ready, [message for kind, message in reasons]), reduce


class TestLinkReady:

    def test_ready(self, scan):
        (ready, reasons), reduce = link_ready(scan)
        assert reasons == []
        assert ready is True
        assert reduce._beamline.frames == FRAMES

    def test_registers_scan_with_parent(self, scan):
        assert 'sample_scan' not in NXParent(scan.parent).scans
        link_ready(scan)
        assert 'sample_scan' in NXParent(scan.parent).scans

    def test_registers_scan_even_if_not_ready(self, scan):
        scan.raw.unlink()
        (ready, reasons), _ = link_ready(scan)
        assert ready is False
        assert 'sample_scan' in NXParent(scan.parent).scans

    def test_registration_is_repeatable(self, scan):
        link_ready(scan)
        (ready, _), _ = link_ready(scan)
        assert ready is True
        assert list(NXParent(scan.parent).scans).count('sample_scan') == 1

    def test_no_scan_file(self, scan):
        scan.wrapper.unlink()
        reduce = NXReduce('f1', directory=scan.directory)
        with pytest.raises(NeXusError, match="sample_scan.nxs' does not"):
            reduce.link_ready()

    def test_unknown_entry(self, scan):
        reduce = NXReduce('f9', directory=scan.directory)
        with pytest.raises(NeXusError, match="'f9' not in"):
            reduce.link_ready()

    def test_entry_not_linked_to_raw_data(self, scan):
        with nxopen(scan.wrapper, 'rw') as root:
            del root['f1/data/data']
        reduce = NXReduce('f1', directory=scan.directory)
        with pytest.raises(NeXusError):
            reduce.link_ready()

    def test_no_orientation_matrix(self, scan):
        with nxopen(scan.parent, 'rw') as root:
            del root['f1/instrument/detector/orientation_matrix']
        (ready, reasons), reduce = link_ready(scan)
        assert ready is False
        assert reasons == [
            "no orientation matrix for f1 in sample_scans.nxs"]
        assert reduce.kinds == ['parent']

    def test_no_transform_grid(self, scan):
        with nxopen(scan.parent, 'rw') as root:
            del root['entry/nxscans/transform']
        (ready, reasons), reduce = link_ready(scan)
        assert ready is False
        assert reasons == ["no transform grid in sample_scans.nxs"]
        assert reduce.kinds == ['parent']

    def test_raw_file_missing(self, scan):
        scan.raw.unlink()
        (ready, reasons), reduce = link_ready(scan)
        assert ready is False
        assert reasons == ["f1.h5 not available"]
        assert reduce.kinds == ['data']

    def test_raw_file_wrong_frame_count(self, scan):
        with h5py.File(scan.raw, 'w') as f:
            f.create_dataset('entry/data/data',
                             data=np.zeros((FRAMES - 1, 4, 3)))
        age_file(scan.raw)
        (ready, reasons), _ = link_ready(scan)
        assert ready is False
        assert reasons == [f"f1.h5 has {FRAMES - 1} frames "
                           f"instead of {FRAMES}"]

    def test_raw_file_not_hdf5(self, scan):
        scan.raw.write_bytes(b"partial")
        age_file(scan.raw)
        (ready, reasons), _ = link_ready(scan)
        assert ready is False
        assert reasons[0].startswith("cannot read f1.h5")

    def test_raw_file_recently_modified(self, scan):
        os.utime(scan.raw, None)
        (ready, reasons), _ = link_ready(scan)
        assert ready is False
        assert reasons[0].startswith("f1.h5 modified ")

    def test_logs_not_ready(self, scan):
        (ready, reasons), reduce = link_ready(scan, StubBeamline(ready=False))
        assert ready is False
        assert reasons == ["logs not ready"]
        assert reduce.kinds == ['data']

    def test_all_reasons_reported(self, scan):
        scan.raw.unlink()
        with nxopen(scan.parent, 'rw') as root:
            del root['entry/nxscans/transform']
        (ready, reasons), reduce = link_ready(scan, StubBeamline(ready=False))
        assert reasons == ["no transform grid in sample_scans.nxs",
                           "f1.h5 not available", "logs not ready"]
        assert reduce.kinds == ['parent', 'data', 'data']


class TestNXReadyScript:

    @pytest.fixture(autouse=True)
    def stub_beamline(self, monkeypatch):
        beamline = StubBeamline()
        monkeypatch.setattr(NXReduce, 'beamline',
                            property(lambda self: beamline))
        self.beamline = beamline

    def run(self, monkeypatch, capsys, *args):
        monkeypatch.setattr('sys.argv', ['nxready', *args])
        with pytest.raises(SystemExit) as exit_info:
            nxready.main()
        captured = capsys.readouterr()
        return exit_info.value.code, captured.out.strip(), captured.err

    def test_file_ready(self, scan, monkeypatch, capsys):
        code, out, err = self.run(monkeypatch, capsys, '-f', str(scan.raw))
        assert (code, out, err) == (0, 'True', '')

    def test_directory_ready(self, scan, monkeypatch, capsys):
        code, out, err = self.run(monkeypatch, capsys,
                                  '-d', str(scan.directory), '-e', 'f1')
        assert (code, out, err) == (0, 'True', '')

    def test_directory_defaults_to_all_entries(self, scan, monkeypatch,
                                               capsys):
        code, out, _ = self.run(monkeypatch, capsys,
                                '-d', str(scan.directory))
        assert (code, out) == (0, 'True')

    def test_waiting_for_data(self, scan, monkeypatch, capsys):
        self.beamline.ready = False
        code, out, err = self.run(monkeypatch, capsys, '-f', str(scan.raw))
        assert code == 1
        assert out == 'False'
        assert err.strip() == "f1: logs not ready"

    def test_waiting_for_parent(self, scan, monkeypatch, capsys):
        with nxopen(scan.parent, 'rw') as root:
            del root['entry/nxscans/transform']
        code, out, err = self.run(monkeypatch, capsys, '-f', str(scan.raw))
        assert code == 3
        assert out == 'False'
        assert err.strip() == "f1: no transform grid in sample_scans.nxs"

    def test_data_takes_precedence_over_parent(self, scan, monkeypatch,
                                               capsys):
        with nxopen(scan.parent, 'rw') as root:
            del root['entry/nxscans/transform']
        self.beamline.ready = False
        code, out, err = self.run(monkeypatch, capsys, '-f', str(scan.raw))
        assert code == 1
        assert out == 'False'
        assert err.splitlines() == ["f1: no transform grid in "
                                    "sample_scans.nxs", "f1: logs not ready"]

    def test_unknown_entry_is_an_error(self, scan, monkeypatch, capsys):
        code, out, err = self.run(monkeypatch, capsys, '-d',
                                  str(scan.directory), '-e', 'f1', 'f2')
        assert code == 2
        assert out == ''
        assert err.strip() == "nxready: 'f2' not in 'sample_scan.nxs'"

    def test_no_scan_file_is_an_error(self, scan, monkeypatch, capsys):
        scan.wrapper.unlink()
        code, out, err = self.run(monkeypatch, capsys, '-f', str(scan.raw))
        assert code == 2
        assert out == ''
        assert err.strip() == "nxready: 'sample_scan.nxs' does not exist"

    def test_missing_directory_is_an_error(self, tmp_path, monkeypatch,
                                           capsys):
        code, out, err = self.run(monkeypatch, capsys,
                                  '-d', str(tmp_path / 'nothing'))
        assert code == 2
        assert out == ''
        assert err.startswith("nxready: ")
