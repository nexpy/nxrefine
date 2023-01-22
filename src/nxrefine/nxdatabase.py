# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""Simple sqlite-based logging for NXrefine.

The database file is located by default at GUP-xxx/tasks/nxdatabase.db.
It contains two tables:
    1. Files: Meant for quickly checking the completion status of scans.
        For each task, records if it is not started, queued but not yet
        running, in progress (started for at least one entry), or done
        (finished for all entries).
    2. Tasks: Detailed information about all tasks. Records queue time
        (when it was placed in the NXserver's fifo, or null if it was
        run from the command line), start time, end time, the task's
        PID, the wrapper file and entry it is working on, and its
        status.

Example
-------
Before any other calls, use init() to establish a connection to the
database

    >>> from nxrefine.nxdatabase import NXDatabase
    >>> nxdb = NXDatabase('relative/path/to/database/file')

Use sync_db() to scan the sample directory and update the database to
match the contents of the wrapper files. This only needs to be run if
there are changes to the files outside of NXrefine code (eg manually
deleting an entry or adding a new .nxs files). Other changes are tracked
automatically.

NXDatabase assumes that no identical tasks (i.e., same task, entry, and
wrapper file) will be queued or running at the same time
"""

import datetime
import os

from nexusformat.nexus import NeXusError, NXLock, nxload
from sqlalchemy import (Column, ForeignKey, Integer, String, create_engine,
                        inspect)
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()
# Records files that have: not been processed, queued on the NXserver
# but not started, started processing, finished processing
_prog = {'not started': 0, 'queued': 1, 'in progress': 2, 'done': 3}
NOT_STARTED, QUEUED, IN_PROGRESS, DONE, FAILED = 0, 1, 2, 3, -1


class File(Base):
    __tablename__ = 'files'

    filename = Column(String(255), nullable=False, primary_key=True)
    entries = Column(String(128), nullable=True)
    nxload = Column(Integer, default=NOT_STARTED)
    nxlink = Column(Integer, default=NOT_STARTED)
    nxmax = Column(Integer, default=NOT_STARTED)
    nxfind = Column(Integer, default=NOT_STARTED)
    nxcopy = Column(Integer, default=NOT_STARTED)
    nxrefine = Column(Integer, default=NOT_STARTED)
    nxprepare = Column(Integer, default=NOT_STARTED)
    nxtransform = Column(Integer, default=NOT_STARTED)
    nxmasked_transform = Column(Integer, default=NOT_STARTED)
    nxcombine = Column(Integer, default=NOT_STARTED)
    nxmasked_combine = Column(Integer, default=NOT_STARTED)
    nxpdf = Column(Integer, default=NOT_STARTED)
    nxmasked_pdf = Column(Integer, default=NOT_STARTED)

    def __repr__(self):
        not_started = [k for k, v in vars(self).items() if v == NOT_STARTED]
        queued = [k for k, v in vars(self).items() if v == QUEUED]
        in_progress = [k for k, v in vars(self).items() if v == IN_PROGRESS]
        done = [k for k, v in vars(self).items() if v == DONE]

        return "File path='{}',\n\tnot started={}\n\tqueued={}\n\t" \
            "in_progress={}\n\tdone={}".format(
                self.filename, not_started, queued, in_progress, done)

    def get_entries(self):
        if self.entries:
            return self.entries.split('|')
        else:
            return []

    def set_entries(self, entries):
        self.entries = '|'.join(entries)


class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    entry = Column(String, default='')
    status = Column(Integer, default=QUEUED)
    entries = Column(Integer, default=NOT_STARTED)
    # Timestamps with microsecond precision
    queue_time = Column(mysql.TIMESTAMP(fsp=6))
    start_time = Column(mysql.TIMESTAMP(fsp=6))
    end_time = Column(mysql.TIMESTAMP(fsp=6))
    pid = Column(Integer)
    filename = Column(String(255), ForeignKey('files.filename'),
                      nullable=False)

    file = relationship('File', back_populates='tasks')

    def __repr__(self):
        return "<Task {} on {}, entry {}, pid={}>".format(
            self.name, self.filename, self.entry, self.pid)


File.tasks = relationship('Task', back_populates='file', order_by=Task.id)


class NXDatabase:

    task_names = ('nxload', 'nxlink', 'nxmax', 'nxfind', 'nxcopy', 'nxrefine',
                  'nxprepare', 'nxtransform', 'nxmasked_transform',
                  'nxcombine', 'nxmasked_combine', 'nxpdf', 'nxmasked_pdf')
    NOT_STARTED, QUEUED, IN_PROGRESS, DONE, FAILED = 0, 1, 2, 3, -1

    def __init__(self, db_file, echo=False):
        """Connect to the database, creating tables if necessary.

        Parameters
        ----------
        db_file : str
            Path to the database file
        echo : bool, optional
            True if SQL statements are echoed to `stdout`, by default False.
        """
        with NXLock(db_file):
            connection = 'sqlite:///' + db_file
            self.engine = create_engine(connection, echo=echo)
            Base.metadata.create_all(self.engine)
        self.database = os.path.realpath(self.engine.url.database)
        try:
            os.chmod(self.database, 0o775)
        except Exception:
            pass
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = sessionmaker(bind=self.engine)()
        return self._session

    def get_filename(self, filename):
        """Return the relative path of the requested filename."""
        root = os.path.dirname(os.path.dirname(self.database))
        return os.path.relpath(os.path.realpath(filename), root)

    def get_file(self, filename):
        """Return the File object (and associated tasks) matching filename.

        Parameters
        ----------
        filename : str
            Path of wrapper file.

        Returns
        -------
        File
            File object.
        """
        self.check_tasks()
        f = self.query(filename)

        if f is None:
            filename = os.path.realpath(filename)
            if not os.path.exists(filename):
                raise NeXusError(f"'{filename}' does not exist")
            self.session.add(File(filename=self.get_filename(filename)))
            self.session.commit()
            f = self.sync_file(filename)
        else:
            if (f.entries is None or f.entries == ''
                    or isinstance(f.entries, int)):
                root = nxload(filename)
                f.set_entries([e for e in root.entries if e != 'entry'])
            f = self.sync_data(filename)
        return f

    def query(self, filename):
        return self.session.query(File) \
            .filter(File.filename == self.get_filename(filename)) \
            .one_or_none()

    def sync_file(self, filename):
        """Synchronize the NeXus file contents to the database.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.

        Returns
        -------
        File
            Updated File object.
        """
        f = self.get_file(filename)
        sample_dir = os.path.dirname(filename)
        if f:
            try:
                scan_files = os.listdir(get_directory(filename))
            except OSError:
                scan_files = []
            root = nxload(filename)
            entries = [e for e in root.entries if e != 'entry']
            tasks = {t: 0 for t in self.task_names}
            for e in entries:
                nxentry = root[e]
                if e in root and 'data' in nxentry and 'instrument' in nxentry:
                    if 'nxload' in nxentry:
                        tasks['nxload'] += 1
                    elif e+'.h5' in scan_files or e+'.nxs' in scan_files:
                        tasks['nxload'] += 1
                    if 'nxlink' in nxentry:
                        tasks['nxlink'] += 1
                    if 'nxmax' in nxentry:
                        tasks['nxmax'] += 1
                    if 'nxfind' in nxentry:
                        tasks['nxfind'] += 1
                    if 'nxcopy' in nxentry or is_parent(filename, sample_dir):
                        tasks['nxcopy'] += 1
                    if 'nxrefine' in nxentry:
                        tasks['nxrefine'] += 1
                    if 'nxprepare_mask' in nxentry:
                        tasks['nxprepare'] += 1
                    if 'nxtransform' in nxentry:
                        tasks['nxtransform'] += 1
                    if 'nxmasked_transform' in nxentry or 'nxmask' in nxentry:
                        tasks['nxmasked_transform'] += 1
            if 'nxcombine' in root['entry']:
                tasks['nxcombine'] = len(entries)
            if 'nxmasked_combine' in root['entry']:
                tasks['nxmasked_combine'] = len(entries)
            if 'nxpdf' in root['entry']:
                tasks['nxpdf'] = len(entries)
            if 'nxmasked_pdf' in root['entry']:
                tasks['nxmasked_pdf'] = len(entries)
            for task, value in tasks.items():
                if value == 0:
                    setattr(f, task, NOT_STARTED)
                elif value == len(entries):
                    setattr(f, task, DONE)
                else:
                    setattr(f, task, IN_PROGRESS)
            f.set_entries(entries)
            self.session.commit()
        return f

    def sync_data(self, filename):
        """Update status of raw data linked from File.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.

        Returns
        -------
        File
            Updated File object.
        """
        f = self.query(filename)
        if f:
            scan_dir = get_directory(filename)
            entries = f.get_entries()
            data = 0
            if 'nxload' in [t.name for t in f.tasks]:
                self.update_status(f, 'nxload')
            else:
                for e in entries:
                    if os.path.exists(os.path.join(scan_dir, e+'.h5')):
                        data += 1
                if data == 0:
                    f.nxload = NOT_STARTED
                elif data == len(entries):
                    f.nxload = DONE
                else:
                    f.nxload = IN_PROGRESS
            self.session.commit()
        return f

    def get_task(self, f, task, entry):
        """Return the latest database entry for the specified task.

        This creates a new task if one does not exist.

        Parameters
        ----------
        file : File
            File object.
        task : str
            Task being checked.
        entry : str
            Entry of NeXus file being checked.
        """
        for t in reversed(f.tasks):
            if t.name == task and t.entry == entry:
                break
        else:
            # This task was started from command line
            t = Task(name=task, entry=entry)
            f.tasks.append(t)
        return t

    def task_status(self, filename, task, entry=None):
        """Return the status of the task.

        Parameters
        ----------
        filename : str
            Path of wrapper file.
        task : str
            Task being checked.
        entry : str
            Entry of NeXus file being checked.
        """
        with NXLock(self.database):
            f = self.get_file(filename)
            if entry:
                for t in reversed(f.tasks):
                    if t.name == task and t.entry == entry:
                        status = t.status
                        break
                else:
                    status = NOT_STARTED
            else:
                status = getattr(f, task)
        return status

    def task_complete(self, filename, task, entry=None):
        return self.task_status(filename, task, entry) == DONE

    def queue_task(self, filename, task, entry, queue_time=None):
        """Update a file to 'queued' status and create a matching task.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.
        task : str
            Task being updated.
        entry : str
            Entry of NeXus file being updated.
        """
        with NXLock(self.database):
            f = self.get_file(filename)
            t = self.get_task(f, task, entry)
            t.status = QUEUED
            if queue_time:
                t.queue_time = queue_time
            else:
                t.queue_time = datetime.datetime.now()
            t.start_time = t.end_time = None
            self.update_status(f, task)

    def start_task(self, filename, task, entry, start_time=None):
        """Record that a task has begun execution.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.
        task : str
            Task being updated.
        entry : str
            Entry of NeXus file being updated.
        """
        with NXLock(self.database):
            f = self.get_file(filename)
            t = self.get_task(f, task, entry)
            t.status = IN_PROGRESS
            if start_time:
                t.start_time = start_time
            else:
                t.start_time = datetime.datetime.now()
            t.pid = os.getpid()
            t.end_time = None
            self.update_status(f, task)

    def end_task(self, filename, task, entry, end_time=None):
        """Record that a task finished execution.

        Update the task's database entry, and set the matching column in
        files to DONE if it's the last task to finish

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.
        task : str
            Task being updated.
        entry : str
            Entry of NeXus file being updated.
        """
        with NXLock(self.database):
            f = self.get_file(filename)
            t = self.get_task(f, task, entry)
            t.status = DONE
            if end_time:
                t.end_time = end_time
            else:
                t.end_time = datetime.datetime.now()
            self.update_status(f, task)

    def fail_task(self, filename, task, entry):
        """Record that a task failed during execution.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.
        task : str
            Task being updated.
        entry : str
            Entry of NeXus file being updated.
        """
        with NXLock(self.database):
            f = self.get_file(filename)
            for t in reversed(f.tasks):
                if t.name == task and t.entry == entry:
                    break
            else:
                # No task recorded
                return
            t.status = FAILED
            t.queue_time = None
            t.start_time = None
            t.end_time = None
            self.update_status(f, task)

    def update_status(self, f, task):
        """Update the File object with the status of the specified task.

        Parameters
        ----------
        f : File
            File table being updated
        task : str
            Task being updated.
        """
        sample_dir = os.path.dirname(f.filename)
        status = {}
        if task == 'nxcopy' and is_parent(f.filename, sample_dir):
            setattr(f, task, DONE)
        else:
            if (task == 'nxcombine' or task == 'nxmasked_combine' or
                    task == 'nxpdf' or task == 'nxmasked_pdf'):
                entries = ['entry']
            else:
                entries = f.get_entries()
            for e in entries:
                for t in reversed(f.tasks):
                    if t.name == task and t.entry == e:
                        status[e] = t.status
                        break
                else:
                    status[e] = NOT_STARTED
            if all(s == DONE for s in status.values()):
                setattr(f, task, DONE)
            elif FAILED in status.values():
                setattr(f, task, FAILED)
            elif IN_PROGRESS in status.values():
                setattr(f, task, IN_PROGRESS)
            elif QUEUED in status.values():
                if DONE in status.values():
                    setattr(f, task, IN_PROGRESS)
                else:
                    setattr(f, task, QUEUED)
            elif DONE in status.values():
                setattr(f, task, IN_PROGRESS)
            else:
                setattr(f, task, NOT_STARTED)
        self.session.commit()

    def update_file(self, filename):
        """Update the File object for the specified file.

        This is just a wrapper for 'sync_file' that includes database file
        locking.

        Parameters
        ----------
        filename : str
            Path of wrapper file relative to GUP directory.
        """
        with NXLock(self.database):
            self.sync_file(filename)

    def sync_db(self, sample_dir):
        """ Populate the database based on local files.

        Parameters
        ----------
        sample_dir : str
            Directory containing the NeXus wrapper files.
        """
        # Get a list of all the .nxs wrapper files
        wrapper_files = [
            os.path.join(sample_dir, filename)
            for filename in os.listdir(sample_dir)
            if filename.endswith('.nxs') and
            all(x not in filename for x in ('parent', 'mask'))]
        with NXLock(self.database):
            for wrapper_file in wrapper_files:
                self.sync_file(self.get_file(wrapper_file))
            tracked_files = list(self.session.query(File).all())
            for f in tracked_files:
                if f.filename not in [
                        self.get_filename(w) for w in wrapper_files]:
                    self.session.delete(f)
            self.session.commit()

    def check_tasks(self):
        """Check that all tasks are present, adding a column if necessary."""
        inspector = inspect(self.engine)
        tasks = [task['name'] for task in inspector.get_columns('files')]
        if 'data' in tasks:
            self.rename_column('data', 'nxload')
        for task in self.task_names:
            if task not in tasks:
                self.add_column(task)
        if 'entries' not in tasks:
            self.add_column('entries', data_type=String)

    def add_column(self, column_name, table_name='files',
                   data_type=Integer, default=None):
        """Add a missing column to the database."""
        ret = False
        if default is not None:
            try:
                command = (f"ALTER TABLE '{table_name}' "
                           f"ADD COLUMN '{column_name}' "
                           f"'{data_type.__name__}' "
                           f"DEFAULT {default}")
            except Exception:
                command = (f"ALTER TABLE '{table_name}' "
                           f"ADD COLUMN '{column_name}' "
                           f"'{data_type.__name__}' "
                           f"DEFAULT '{default}'")
        else:
            command = (f"ALTER TABLE '{table_name}' "
                       f"ADD column '{column_name}' '{data_type.__name__}'")
        try:
            connection = self.engine.connect()
            connection.execute(command)
            connection.close()
            ret = True
        except Exception as e:
            print(e)
            ret = False
        return ret

    def rename_column(self, old_column_name, new_column_name,
                      table_name='files'):
        command = (f"ALTER TABLE {table_name} RENAME {old_column_name} TO "
                   f"{new_column_name};")
        try:
            connection = self.engine.connect()
            connection.execute(command)
            connection.close()
            ret = True
        except Exception as e:
            print(e)
            ret = False
        return ret


def get_directory(filename):
    """Return the directory path containing the raw data."""
    base_name = os.path.basename(os.path.splitext(filename)[0])
    sample_dir = os.path.dirname(filename)
    sample = os.path.basename(os.path.dirname(sample_dir))
    scan_label = base_name.replace(sample+'_', '')
    return os.path.join(sample_dir, scan_label)


def is_parent(wrapper_file, sample_dir):
    """True if the wrapper file is set as the parent."""
    parent_file = os.path.join(sample_dir,
                               os.path.basename(os.path.dirname(sample_dir) +
                                                '_parent.nxs'))
    if os.path.exists(parent_file):
        return wrapper_file == os.path.realpath(parent_file)
    else:
        return False
