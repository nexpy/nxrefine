"""Tests for NXDatabase timing fields in NXprocess groups and sync_subentries."""

import datetime
import os
import pathlib
import tempfile
import unittest.mock as mock

import pytest
from nexusformat.nexus import (NXcollection, NXentry, NXprocess, NXsubentry,
                               nxopen)

from nxrefine.nxdatabase import DONE, NOT_STARTED, File, NXDatabase, Task
from nxrefine.nxreduce import NXReduce
from nxrefine.nxsettings import NXSettings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_directory_structure(tmp_path):
    """Create the experiment layout expected by NXDatabase and NXReduce.

    Layout:
        tmp_path/               <- experiment root (NXDatabase.experiment_directory)
          sample/label/
            sample_scan.nxs
            scan/               <- NXReduce directory
          tasks/
            nxdatabase.db
            settings.ini
    """
    sample_dir = tmp_path / 'sample' / 'label'
    sample_dir.mkdir(parents=True)
    scan_dir = sample_dir / 'scan'
    scan_dir.mkdir()
    tasks_dir = tmp_path / 'tasks'
    tasks_dir.mkdir()
    NXSettings(tasks_dir, create=True)
    wrapper = sample_dir / 'sample_scan.nxs'
    return scan_dir, wrapper, tasks_dir


def make_db(tasks_dir):
    return NXDatabase(tasks_dir / 'nxdatabase.db')


def make_wrapper(path, entries=('f1',)):
    """Create a minimal wrapper file with the given top-level entries."""
    with nxopen(path, 'w') as root:
        root['entry'] = NXentry()
        for e in entries:
            root[e] = NXentry()


def add_subentry_task(wrapper_path, entry_name, subentry_name, task_name,
                      timing=None):
    """Add a completed NXprocess for a subentry task to the wrapper file."""
    with nxopen(wrapper_path, 'rw') as root:
        nxentry = root[entry_name]
        if subentry_name not in nxentry:
            nxentry[subentry_name] = NXsubentry()
        sub = nxentry[subentry_name]
        if 'nxworkflow' not in sub:
            sub['nxworkflow'] = NXcollection()
        proc = NXprocess(program=task_name, sequence_index=1,
                         version='nxrefine v0.0')
        if timing:
            for field, value in timing.items():
                proc[field] = value
        sub['nxworkflow'][task_name] = proc


def add_entry_task(wrapper_path, entry_name, task_name, timing=None):
    """Add a completed NXprocess for an entry-level task to the wrapper file."""
    with nxopen(wrapper_path, 'rw') as root:
        nxentry = root[entry_name]
        if 'nxworkflow' not in nxentry:
            nxentry['nxworkflow'] = NXcollection()
        proc = NXprocess(program=task_name, sequence_index=1,
                         version='nxrefine v0.0')
        if timing:
            for field, value in timing.items():
                proc[field] = value
        nxentry['nxworkflow'][task_name] = proc


# ---------------------------------------------------------------------------
# Tests for _get_nxprocess
# ---------------------------------------------------------------------------

class TestGetNXProcess:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        _, _, tasks_dir = make_directory_structure(tmp_path)
        self.db = make_db(tasks_dir)

    def test_finds_process_in_nxworkflow(self):
        group = NXentry()
        group['nxworkflow'] = NXcollection()
        group['nxworkflow']['nxmax'] = NXprocess()
        result = self.db._get_nxprocess(group, 'nxmax')
        assert result is group['nxworkflow']['nxmax']

    def test_finds_process_directly_in_group(self):
        group = NXentry()
        group['nxmax'] = NXprocess()
        result = self.db._get_nxprocess(group, 'nxmax')
        assert result is group['nxmax']

    def test_prefers_nxworkflow_over_direct(self):
        group = NXentry()
        group['nxmax'] = NXprocess(program='direct')
        group['nxworkflow'] = NXcollection()
        group['nxworkflow']['nxmax'] = NXprocess(program='in_workflow')
        result = self.db._get_nxprocess(group, 'nxmax')
        assert str(result['program']) == 'in_workflow'

    def test_returns_none_when_missing(self):
        assert self.db._get_nxprocess(NXentry(), 'nxmax') is None

    def test_returns_none_when_only_wrong_task_in_workflow(self):
        group = NXentry()
        group['nxworkflow'] = NXcollection()
        group['nxworkflow']['nxlink'] = NXprocess()
        assert self.db._get_nxprocess(group, 'nxmax') is None


# ---------------------------------------------------------------------------
# Tests for sync_subentries
# ---------------------------------------------------------------------------

class TestSyncSubentries:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        _, self.wrapper, tasks_dir = make_directory_structure(tmp_path)
        self.db = make_db(tasks_dir)
        make_wrapper(self.wrapper, entries=['f1'])
        self.filename = str(self.wrapper.relative_to(tmp_path))
        # Register the wrapper file with its entries in the database
        f = File(filename=self.filename)
        f.set_entries(['f1'])
        self.db.session.add(f)
        self.db.session.commit()

    def test_creates_task_record_for_completed_subentry_task(self):
        add_subentry_task(self.wrapper, 'f1', 'mysub', 'nxmax')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        assert any(t.name == 'nxmax' and t.entry == 'f1'
                   and t.subentry == 'mysub' and t.status == DONE
                   for t in f.tasks)

    def test_reads_timing_fields_from_nxprocess(self):
        queue = datetime.datetime(2026, 5, 13, 9, 59, 0)
        start = datetime.datetime(2026, 5, 13, 10, 0, 0)
        end = datetime.datetime(2026, 5, 13, 10, 5, 0)
        add_subentry_task(self.wrapper, 'f1', 'mysub', 'nxmax', timing={
            'queue_time': queue.isoformat(),
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
            'pid': 99999,
        })
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        t = next(x for x in f.tasks
                 if x.name == 'nxmax' and x.subentry == 'mysub')
        assert t.queue_time == queue
        assert t.start_time == start
        assert t.end_time == end
        assert t.pid == 99999

    def test_handles_missing_timing_fields_gracefully(self):
        add_subentry_task(self.wrapper, 'f1', 'mysub', 'nxmax')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        t = next(x for x in f.tasks
                 if x.name == 'nxmax' and x.subentry == 'mysub')
        assert t.queue_time is None
        assert t.start_time is None
        assert t.end_time is None
        assert t.pid is None

    def test_skips_task_with_existing_done_record(self):
        add_subentry_task(self.wrapper, 'f1', 'mysub', 'nxmax')
        f = self.db.query(self.filename)
        f.tasks.append(Task(name='nxmax', entry='f1', subentry='mysub',
                            status=DONE, filename=self.filename))
        self.db.session.commit()
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        matching = [t for t in f.tasks
                    if t.name == 'nxmax' and t.subentry == 'mysub']
        assert len(matching) == 1

    def test_no_task_created_for_absent_nxprocess(self):
        with nxopen(self.wrapper, 'rw') as root:
            root['f1']['mysub'] = NXsubentry()
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        assert not any(t.subentry == 'mysub' for t in f.tasks)

    def test_multiple_subentries_and_tasks_handled(self):
        for sub in ('sub1', 'sub2'):
            add_subentry_task(self.wrapper, 'f1', sub, 'nxmax')
            add_subentry_task(self.wrapper, 'f1', sub, 'nxfind')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        created = {(t.name, t.subentry) for t in f.tasks}
        assert ('nxmax', 'sub1') in created
        assert ('nxmax', 'sub2') in created
        assert ('nxfind', 'sub1') in created
        assert ('nxfind', 'sub2') in created


# ---------------------------------------------------------------------------
# Tests for entry-level task sync (no subentry)
# ---------------------------------------------------------------------------

class TestSyncEntryLevelTasks:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        _, self.wrapper, tasks_dir = make_directory_structure(tmp_path)
        self.db = make_db(tasks_dir)
        make_wrapper(self.wrapper, entries=['f1'])
        self.filename = str(self.wrapper.relative_to(tmp_path))
        f = File(filename=self.filename)
        f.set_entries(['f1'])
        self.db.session.add(f)
        self.db.session.commit()

    def test_creates_task_record_for_entry_level_task(self):
        add_entry_task(self.wrapper, 'f1', 'nxmax')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        assert any(t.name == 'nxmax' and t.entry == 'f1'
                   and (t.subentry or '') == '' and t.status == DONE
                   for t in f.tasks)

    def test_reads_timing_fields_for_entry_level_task(self):
        queue = datetime.datetime(2026, 5, 13, 9, 59, 0)
        start = datetime.datetime(2026, 5, 13, 10, 0, 0)
        end = datetime.datetime(2026, 5, 13, 10, 5, 0)
        add_entry_task(self.wrapper, 'f1', 'nxmax', timing={
            'queue_time': queue.isoformat(),
            'start_time': start.isoformat(),
            'end_time': end.isoformat(),
            'pid': 42,
        })
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        t = next(x for x in f.tasks
                 if x.name == 'nxmax' and x.entry == 'f1'
                 and (x.subentry or '') == '')
        assert t.queue_time == queue
        assert t.start_time == start
        assert t.end_time == end
        assert t.pid == 42

    def test_handles_missing_timing_fields_for_entry_level_task(self):
        add_entry_task(self.wrapper, 'f1', 'nxlink')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        t = next(x for x in f.tasks
                 if x.name == 'nxlink' and x.entry == 'f1'
                 and (x.subentry or '') == '')
        assert t.queue_time is None
        assert t.start_time is None
        assert t.end_time is None
        assert t.pid is None

    def test_skips_entry_level_task_with_existing_done_record(self):
        add_entry_task(self.wrapper, 'f1', 'nxmax')
        f = self.db.query(self.filename)
        f.tasks.append(Task(name='nxmax', entry='f1', subentry='',
                            status=DONE, filename=self.filename))
        self.db.session.commit()
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        matching = [t for t in f.tasks
                    if t.name == 'nxmax' and t.entry == 'f1'
                    and (t.subentry or '') == '']
        assert len(matching) == 1

    def test_creates_combine_task_from_root_entry(self):
        queue = datetime.datetime(2026, 5, 13, 11, 0, 0)
        end = datetime.datetime(2026, 5, 13, 11, 30, 0)
        add_entry_task(self.wrapper, 'entry', 'nxcombine', timing={
            'queue_time': queue.isoformat(),
            'end_time': end.isoformat(),
            'pid': 7,
        })
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        t = next(x for x in f.tasks
                 if x.name == 'nxcombine' and x.entry == 'entry'
                 and (x.subentry or '') == '')
        assert t.status == DONE
        assert t.queue_time == queue
        assert t.end_time == end
        assert t.pid == 7

    def test_entry_and_subentry_tasks_both_created(self):
        add_entry_task(self.wrapper, 'f1', 'nxmax')
        add_subentry_task(self.wrapper, 'f1', 'mysub', 'nxmax')
        self.db.sync_subentries(self.filename)
        f = self.db.query(self.filename)
        entry_tasks = [t for t in f.tasks
                       if t.name == 'nxmax' and t.entry == 'f1']
        assert any((t.subentry or '') == '' for t in entry_tasks)
        assert any((t.subentry or '') == 'mysub' for t in entry_tasks)


# ---------------------------------------------------------------------------
# Tests for record() timing fields written to NXprocess
# ---------------------------------------------------------------------------

class TestRecordTimingFields:

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        scan_dir, self.wrapper, _ = make_directory_structure(tmp_path)
        with nxopen(self.wrapper, 'w') as root:
            root['entry'] = NXentry()
        self.reduce = NXReduce(directory=scan_dir)

    def _get_proc(self, task_name):
        """Read the NXprocess from the wrapper file after record() was called."""
        with nxopen(self.wrapper) as root:
            return root[f'entry/nxworkflow/{task_name}']

    def test_record_writes_end_time(self):
        before = datetime.datetime.now()
        self.reduce.record('nxmax')
        after = datetime.datetime.now()
        proc = self._get_proc('nxmax')
        assert 'end_time' in proc
        end = datetime.datetime.fromisoformat(str(proc['end_time']))
        assert before <= end <= after

    def test_record_writes_pid(self):
        self.reduce.record('nxmax')
        proc = self._get_proc('nxmax')
        assert 'pid' in proc
        assert int(proc['pid']) == os.getpid()

    def test_record_writes_start_time_after_record_start(self):
        self.reduce._db = mock.MagicMock()
        before = datetime.datetime.now()
        self.reduce.record_start('nxmax')
        self.reduce.record('nxmax')
        after = datetime.datetime.now()
        proc = self._get_proc('nxmax')
        assert 'start_time' in proc
        start = datetime.datetime.fromisoformat(str(proc['start_time']))
        assert before <= start <= after

    def test_record_omits_start_time_without_record_start(self):
        self.reduce.record('nxmax')
        proc = self._get_proc('nxmax')
        assert 'start_time' not in proc

    def test_record_writes_queue_time_after_queue_task(self):
        self.reduce._db = mock.MagicMock()
        self.reduce.not_processed = mock.MagicMock(return_value=True)
        before = datetime.datetime.now()
        self.reduce.queue_task('nxmax')
        self.reduce.record('nxmax')
        after = datetime.datetime.now()
        proc = self._get_proc('nxmax')
        assert 'queue_time' in proc
        qt = datetime.datetime.fromisoformat(str(proc['queue_time']))
        assert before <= qt <= after

    def test_record_omits_queue_time_without_queue_task(self):
        self.reduce.record('nxmax')
        proc = self._get_proc('nxmax')
        assert 'queue_time' not in proc
