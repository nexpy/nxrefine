"""
Simple sqlite-based logging for NXrefine. The database file is located by
default at GUP-xxx/tasks/nxdatabase.db. It contains two tables:
    1. Files: Meant for quickly checking the completion status of scans.
        For each task, records if it is not started, queued but not yet running,
        in progress (started for at least one entry), or done (finished for all
        entries).
    2. Tasks: Detailed information about all tasks. Records queue time (when
        it was placed in the NXserver's fifo, or null if it was run from the
        command line), start time, end time, the task's PID, the wrapper file
        and entry it is working on, and its status.

Usage:
----------------------
Before any other calls, use init() to establish a connection to the database

    >>> import nxrefine.nxdatabase as nxdb
    >>> nxdb.init('sqlite:///relative/path/to/database/file')

Use sync_db() to scan the sample directory and update the database to match
the contents of the wrapper files. This only needs to be run if there are
changes to the files outside of NXrefine code (eg manually deleting an entry
or adding a new .nxs file). Other changes are tracked automatically.

NXdatabase assumes that no identical tasks (i.e., same task, entry, and wrapper 
file) will be queued or running at the same time
"""

import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError

from nexusformat.nexus import nxload
from .nxlock import Lock

NUM_ENTRIES = 3

Base = declarative_base();
# Records files that have: not been processed, queued on the NXserver
    # but not started, started processing, finished processing
_prog = {'not started':0, 'queued':1, 'in progress':2, 'done':3}
NOT_STARTED, QUEUED, IN_PROGRESS, DONE, FAILED = 0,1,2,3,-1
task_names = ('data', 'nxlink', 'nxmax', 'nxfind', 'nxcopy',
              'nxrefine', 'nxtransform', 'nxmasked_transform', 'nxcombine',
              'nxmasked_combine', 'nxpdf')

class File(Base):
    __tablename__ = 'files'

    filename = Column(String(255), nullable=False, primary_key=True)
    data = Column(Integer, default=NOT_STARTED)
    nxlink = Column(Integer, default=NOT_STARTED)
    nxmax = Column(Integer, default=NOT_STARTED)
    nxfind = Column(Integer, default=NOT_STARTED)
    nxcopy = Column(Integer, default=NOT_STARTED)
    nxrefine = Column(Integer, default=NOT_STARTED)
    nxtransform = Column(Integer, default=NOT_STARTED)
    nxmasked_transform = Column(Integer, default=NOT_STARTED)
    nxcombine = Column(Integer, default=NOT_STARTED)
    nxmasked_combine = Column(Integer, default=NOT_STARTED)
    nxpdf = Column(Integer, default=NOT_STARTED)

    def __repr__(self):
        not_started = [k for k,v in vars(self).items() if v == NOT_STARTED]
        queued = [k for k,v in vars(self).items() if v == QUEUED]
        in_progress = [k for k,v in vars(self).items() if v == IN_PROGRESS]
        done = [k for k,v in vars(self).items() if v == DONE]

        return "File path='{}',\n\tnot started={}\n\tqueued={}\n\t" \
                "in_progress={}\n\tdone={}".format(
                self.filename, not_started, queued, in_progress, done)

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    entry = Column(String)
    status = Column(Integer, default=QUEUED)
    # Timestamps with microsecond precision
    queue_time = Column(mysql.TIMESTAMP(fsp=6))
    start_time = Column(mysql.TIMESTAMP(fsp=6))
    end_time = Column(mysql.TIMESTAMP(fsp=6))
    pid = Column(Integer)
    filename = Column(String(255), ForeignKey('files.filename'), nullable=False)

    file = relationship('File', back_populates='tasks')

    def __repr__(self):
        return "<Task {} on {}, entry {}, pid={}>".format(self.name,
                self.filename, self.entry, self.pid)

File.tasks = relationship('Task', back_populates='file', order_by=Task.id)

session = None

def init(connect, echo=False):
    """ Connect to the database, creating tables if necessary

        connect: connect string as specified by SQLAlchemy
        echo: whether or not to echo the emmited SQL statements to stdout
    """
    global session
    if session is None:
        engine = create_engine(connect, echo=echo)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

def get_file(filename):
    """ Return the File object (and associated tasks) matching filename

        filename: string, absolute path of wrapper file to query
     """
    filename = os.path.realpath(filename)
    f = session.query(File) \
            .filter(File.filename == filename) \
            .one()
    return f

# def record_queued_task(filename, task, entry):
def queue_task(filename, task, entry):
    """ Update a file to 'queued' status and create a matching task

        filename, task, entry: strings that uniquely identify the desired task
    """
    filename = os.path.realpath(filename)
    row = session.query(File).filter(File.filename == filename).scalar()
    time = datetime.datetime.now()
    row.tasks.append(Task(name=task, entry=entry, queue_time=time))
    setattr(row, task, QUEUED)
    session.commit()

def start_task(filename, task_name, entry):
    """ Record that a task has begun execution.

        filename, task, entry: strings that uniquely identify the desired task
    """
    filename = os.path.realpath(filename)
    # Get the specified file
    row = session.query(File).filter(File.filename == filename).scalar()
    #Find the desired task, and create a new one if it doesn't exist
    for t in row.tasks:
        if t.name == task_name and t.entry == entry and t.status == QUEUED:
            break
    else:
        # This task was started from command line, not queued on the server
        t = Task(name=task_name, entry=entry)
        row.tasks.append(t)

    t.status = IN_PROGRESS
    t.start_time = datetime.datetime.now()
    t.pid = os.getpid()
    setattr(row, task_name, IN_PROGRESS)
    session.commit()

def end_task(filename, task_name, entry):
    """ Record that a task finished execution.

        Update the task's database entry, and set the matching column in files
        to DONE if it's the last task to finish

        filename, task_name, entry: strings that uniquely identify the desired task
    """
    filename = os.path.realpath(filename)
    row = session.query(File).filter(File.filename == filename).scalar()
    # Others of the same type of task for this file
    matching_tasks = []
    # The entries that have finished this task
    finished_entries = [entry]
    t = None
    for task in row.tasks:
        if task.name == task_name:
            matching_tasks.append(task)
            if task.entry == entry and task.status == IN_PROGRESS:
                t = task
            elif task.status == DONE:
                finished_entries.append(task.entry)
    if t is None:
        print("ERROR: nxdatabase couldn't find task '%s' on file %s/%s"
                    % (task_name, filename, entry))
        return
    t.status = DONE
    t.end_time = datetime.datetime.now()
    # Update the status of the file to DONE if all tasks are done and there is
    # a finished task for each entry, otherwise leave it as IN_PROGRESS
    if len(matching_tasks) >= NUM_ENTRIES and \
                all(task.status == DONE for task in matching_tasks) and \
                all(e in finished_entries for e in ('f1', 'f2', 'f3')):
            setattr(row, task_name, DONE)
    session.commit()

def fail_task(filename, task_name, entry):
    """ Record that a task failed during execution.

        filename, task_name, entry: strings that uniquely identify the desired task
    """
    filename = os.path.realpath(filename)
    task = session.query(Task).filter(Task.filename == filename)\
            .filter(Task.name == task_name)\
            .filter(Task.entry == entry)\
            .filter(Task.status == IN_PROGRESS).first()
    task.status = FAILED
    # TODO: include logging info?
    session.commit()

def sync_db(sample_dir):
    """ Populate the database based on local files (overwriting if necessary)

        sample_dir: Directory containing the .nxs wrapper files
            (ie NXreduce.base_directory)
    """
    from nxrefine.nxreduce import NXReduce
    # Get a list of all the .nxs wrapper files
    wrapper_files = ( os.path.join(sample_dir, filename) for filename in
                    os.listdir(sample_dir) if filename.endswith('.nxs')
                    and all(x not in filename for x in ('parent', 'mask')) )
    tracked_files = session.query(File).all()

    for w in wrapper_files:
        w = os.path.realpath(w)
        base_name = os.path.basename(os.path.splitext(w)[0])
        scan_label = '_'.join(base_name.split('_')[1:]) # e.g. 350K, shrunk_350K
        scan_dir = os.path.join(sample_dir, scan_label)
        try:
            scan_files = os.listdir(scan_dir)
        except OSError:
            scan_files = []
        with Lock(w):
            root = nxload(w)
            entries = (e for e in root.entries if e != 'entry')
        # Track how many entries have finished each task
        tasks = { t: 0 for t in task_names }

        for e in entries:
            nxentry = root[e]
            if e in root and 'data' in nxentry and 'instrument' in nxentry:
                if e+'.h5' in scan_files or e+'.nxs' in scan_files:
                    tasks['data'] += 1
                if 'nxlink' in nxentry:
                    tasks['nxlink'] += 1
                if 'nxmax' in nxentry:
                    tasks['nxmax'] += 1
                if 'nxfind' in nxentry:
                    tasks['nxfind'] += 1
                if 'nxcopy' in nxentry or is_parent(w, sample_dir):
                    tasks['nxcopy'] += 1
                if 'nxrefine' in nxentry:
                    tasks['nxrefine'] += 1
                if 'nxtransform' in nxentry:
                    tasks['nxtransform'] += 1
                if 'nxmasked_transform' in nxentry or 'nxmask' in nxentry:
                    tasks['nxmasked_transform'] += 1
                if 'nxcombine' in root['entry']:
                    tasks['nxcombine'] += 1
                if 'nxmasked_combine' in root['entry']:
                    tasks['nxmasked_combine'] += 1
                if 'nxpdf' in root['entry']:
                    tasks['nxpdf'] += 1

        # If the file already exists, update it, otherwise create a new file
        for row in tracked_files:
            if w == row.filename:
                f = row
                break
        else:
            f = File(filename = w)
        for task, val in tasks.items():
            if val == 0:
                setattr(f, task, NOT_STARTED)
            elif val == NUM_ENTRIES:
                setattr(f, task, DONE)
            else:
                setattr(f, task, IN_PROGRESS)
        session.add(f)
        for row in tracked_files:
            if row.filename not in wrapper_files:
                session.delete(row)
    session.commit()

""" Sample_dir should be the GUPxxx/agcrse2/xtalX directory -
        ie NXreduce.base_directory """
def is_parent(wrapper_file, sample_dir):
    parent_file = os.path.join(sample_dir,
            os.path.basename(os.path.dirname(sample_dir) + '_parent.nxs'))
    if os.path.exists(parent_file):
        return wrapper_file == os.path.realpath(parent_file)
    else:
        return False
