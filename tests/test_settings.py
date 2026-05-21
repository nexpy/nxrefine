"""Tests for NXParent/NXReduce settings migration to /entry/nxscans/settings."""

import pathlib
import tempfile

import pytest
from nexusformat.nexus import (NXentry, NXfield, NXparameters, NXprocess,
                               NXroot, NXsubentry, nxopen)
from nexusformat.nexus.tree import string_dtype

from nxrefine.nxparent import NXParent
from nxrefine.nxreduce import NXReduce
from nxrefine.nxsettings import NXSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_directory_structure(tmp_path):
    """Create the minimum file/directory layout expected by NXReduce.

    Layout:
        tmp_path/
          sample/
            label/
              sample_scan.nxs      <- scan wrapper file
              sample_scans.nxs     <- parent file
              scan/                <- scan directory
          tasks/
            settings.ini
    """
    root_dir = tmp_path
    sample_dir = root_dir / "sample" / "label"
    sample_dir.mkdir(parents=True)
    scan_dir = sample_dir / "scan"
    scan_dir.mkdir()
    task_dir = root_dir / "tasks"
    task_dir.mkdir()

    # Create a minimal settings.ini so NXSettings doesn't fail
    NXSettings(task_dir, create=True)

    wrapper_file = sample_dir / "sample_scan.nxs"
    parent_file = sample_dir / "sample_scans.nxs"
    return scan_dir, wrapper_file, parent_file, task_dir


def make_wrapper_file(path, parent_name=None):
    """Write a minimal wrapper NXS file, optionally pointing to a parent."""
    with nxopen(path, 'w') as root:
        root['entry'] = NXentry()
        if parent_name:
            root['entry/nxscans'] = NXprocess()
            root['entry/nxscans/parent'] = parent_name


def make_parent_file(path, entry='/entry', settings=None):
    """Write a parent *_scans.nxs file with optional settings dict."""
    with nxopen(path, 'w') as root:
        root['entry'] = NXentry()
        root['entry/nxscans'] = NXprocess()
        root['entry/nxscans/scans'] = NXfield([], dtype=string_dtype,
                                              maxshape=(None,))
        root['entry/nxscans/selected'] = NXfield([], dtype=bool,
                                                 maxshape=(None,))
        root['entry/nxscans/settings'] = NXparameters()
        if settings:
            for k, v in settings.items():
                root[f'entry/nxscans/settings/{k}'] = v
        if entry != '/entry':
            # Create the subentry structure
            subentry_name = entry.split('/')[-1]
            root[f'entry/{subentry_name}'] = NXsubentry()
            root[f'entry/{subentry_name}/nxscans'] = NXprocess()
            root[f'entry/{subentry_name}/nxscans/settings'] = NXparameters()
            if settings:
                for k, v in settings.items():
                    root[f'entry/{subentry_name}/nxscans/settings/{k}'] = v


# ---------------------------------------------------------------------------
# NXParent unit tests
# ---------------------------------------------------------------------------

class TestNXParentSettings:

    def test_get_setting_returns_value(self, tmp_path):
        parent_file = tmp_path / "sample_scans.nxs"
        make_parent_file(parent_file, settings={'threshold': 99999})
        p = NXParent(parent_file)
        assert p.get_setting('threshold') == 99999

    def test_get_setting_returns_default_when_missing(self, tmp_path):
        parent_file = tmp_path / "sample_scans.nxs"
        make_parent_file(parent_file)
        p = NXParent(parent_file)
        assert p.get_setting('threshold', default=12345) == 12345

    def test_get_setting_returns_none_when_no_settings_group(self, tmp_path):
        parent_file = tmp_path / "sample_scans.nxs"
        # Create a parent file without a settings group
        with nxopen(parent_file, 'w') as root:
            root['entry'] = NXentry()
            root['entry/nxscans'] = NXprocess()
        p = NXParent(parent_file)
        assert p.get_setting('threshold') is None

    def test_write_settings_creates_and_updates(self, tmp_path):
        parent_file = tmp_path / "sample_scans.nxs"
        make_parent_file(parent_file)
        p = NXParent(parent_file)
        p.write_settings(threshold=77777, monitor='monitor2')
        # Re-open to verify persistence
        p2 = NXParent(parent_file)
        assert p2.get_setting('threshold') == 77777
        assert p2.get_setting('monitor') == 'monitor2'

    def test_write_settings_skips_none_values(self, tmp_path):
        parent_file = tmp_path / "sample_scans.nxs"
        make_parent_file(parent_file, settings={'threshold': 50000})
        p = NXParent(parent_file)
        p.write_settings(threshold=None, monitor='monitor1')
        p2 = NXParent(parent_file)
        assert p2.get_setting('threshold') == 50000  # unchanged
        assert p2.get_setting('monitor') == 'monitor1'


# ---------------------------------------------------------------------------
# NXReduce integration tests
# ---------------------------------------------------------------------------

class TestNXReduceSettings:

    def setup_method(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        (self.scan_dir, self.wrapper_file,
         self.parent_file, _) = make_directory_structure(self.tmp)

    def teardown_method(self):
        self._tmp.cleanup()

    def _make_reduce(self, parent_settings=None, **kwargs):
        """Build wrapper + parent files, return an NXReduce instance."""
        make_wrapper_file(self.wrapper_file,
                          parent_name=self.parent_file.name)
        make_parent_file(self.parent_file, settings=parent_settings or {})
        return NXReduce(directory=self.scan_dir, **kwargs)

    # 1. Read path: values come from parent settings
    def test_threshold_read_from_parent_settings(self):
        r = self._make_reduce(parent_settings={'threshold': 12345})
        assert r.threshold == 12345

    def test_monitor_read_from_parent_settings(self):
        r = self._make_reduce(parent_settings={'monitor': 'monitor3'})
        assert r.monitor == 'monitor3'

    # 2. kwarg override takes precedence over parent settings
    def test_kwarg_overrides_parent_settings(self):
        r = self._make_reduce(parent_settings={'threshold': 12345},
                              threshold=99999)
        assert r.threshold == 99999

    # 3. Write path: write_parameters updates parent /entry/nxscans/settings
    def test_write_parameters_updates_parent_settings(self):
        r = self._make_reduce()
        r.write_parameters(threshold=60000, monitor='mon2')
        p = NXParent(self.parent_file)
        assert p.get_setting('threshold') == 60000
        assert p.get_setting('monitor') == 'mon2'

    def test_write_parameters_updates_first_frame(self):
        # last.setter validates against nframes (requires raw data), so test
        # first_frame only here to confirm the field-name mapping.
        r = self._make_reduce()
        r.write_parameters(first=20)
        p = NXParent(self.parent_file)
        assert p.get_setting('first_frame') == 20

    # 4. Backward compat: no parent → read from local /entry/nxreduce
    def test_get_parameter_fallback_to_local_nxreduce(self):
        # No parent link in the wrapper file
        make_wrapper_file(self.wrapper_file, parent_name=None)
        # Write local nxreduce params
        with nxopen(self.wrapper_file, 'rw') as root:
            root['entry/nxreduce'] = NXparameters()
            root['entry/nxreduce/threshold'] = 33333
        r = NXReduce(directory=self.scan_dir)
        assert r.threshold == 33333

    # 5. No-parent fallback: write_parameters writes to local /entry/nxreduce
    def test_write_parameters_fallback_to_local_when_no_parent(self):
        make_wrapper_file(self.wrapper_file, parent_name=None)
        r = NXReduce(directory=self.scan_dir)
        r.write_parameters(threshold=55555)
        with nxopen(self.wrapper_file) as root:
            assert root['entry/nxreduce/threshold'].nxvalue == 55555

    # 6. Subentry: parent property uses /entry/{entry_name} path
    def test_parent_entry_path_for_subentry(self):
        make_wrapper_file(self.wrapper_file,
                          parent_name=self.parent_file.name)
        make_parent_file(self.parent_file, entry='/entry/entry1',
                         settings={'threshold': 77777})
        # NXReduce with subentry matching parent file's subentry
        with nxopen(self.wrapper_file, 'rw') as root:
            root['entry1'] = NXentry()
        r = NXReduce(entry='entry1', subentry='entry1', directory=self.scan_dir)
        assert r.parent.entry_path == '/entry/entry1'
        assert r.parent.get_setting('threshold') == 77777
