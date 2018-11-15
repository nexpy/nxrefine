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

from nexusformat.nexus import nxload, NeXusError
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
    entries = Column(Integer, default=NOT_STARTED)
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
    try:
        session.close()
    except Exception:
        pass
    engine = create_engine(connect, echo=echo)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

def get_filename(filename):
    """Return the relative path of the requested filename"""
    database = os.path.realpath(session.bind.url.database)
    root = os.path.dirname(os.path.dirname(database))
    return os.path.relpath(os.path.realpath(filename), root)

def get_file(filename):
    """ Return the File object (and associated tasks) matching filename

        filename: string, path of wrapper file relative to GUP directory
     """
    f = session.query(File) \
            .filter(File.filename == get_filename(filename)) \
            .one_or_none()

    if f is None:
        filename = os.path.realpath(filename)
        if not os.path.exists(filename):
            raise NeXusError("'%s' does not exist" % filename)
        session.add(File(filename = get_filename(filename)))        
        session.commit()
        f = sync_file(filename)
    else:
        f = sync_data(filename)
    return f

def get_directory(filename):
    """Return the directory path containing the raw data"""
    base_name = os.path.basename(os.path.splitext(filename)[0])
    sample_dir = os.path.dirname(filename)
    sample = os.path.basename(os.path.dirname(sample_dir))
    scan_label = base_name.replace(sample+'_', '')
    return os.path.join(sample_dir, scan_label)

def sync_file(filename):
    """ Return the File object (and associated tasks) matching filename

        filename: string, path of wrapper file relative to GUP directory
     """
    f = get_file(filename)
    sample_dir = os.path.dirname(filename)
    if f:
        try:
            scan_files = os.listdir(get_directory(filename))
        except OSError:
            scan_files = []

        tasks = { t: 0 for t in task_names }
        with Lock(filename):
            root = nxload(filename)
            entries = (e for e in root.entries if e != 'entry')
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
                    if 'nxcopy' in nxentry or is_parent(filename, sample_dir):
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
        for task, val in tasks.items():
            if val == 0:
                setattr(f, task, NOT_STARTED)
            elif val == NUM_ENTRIES:
                setattr(f, task, DONE)
            else:
                setattr(f, task, IN_PROGRESS)
        session.commit()
    return f

def sync_data(filename):
    """ Update status of raw data linked from File

        filename: string, path of wrapper file relative to GUP directory
     """
    f = session.query(File) \
            .filter(File.filename == get_filename(filename)) \
            .one_or_none()
    if f:
        scan_dir = get_directory(filename)
        data = 0
        for e in ['f1', 'f2', 'f3']:
            if os.path.exists(os.path.join(scan_dir, e+'.h5')):
                data += 1
        if data == 0:
            f.data = NOT_STARTED
        elif data == NUM_ENTRIES:
            f.data = DONE
        else:
            f.data = IN_PROGRESS
        session.commit()
    return f

update_file = sync_file #Temporary backward compatibility    
update_data = sync_data

def queue_task(filename, task, entry):
    """ Update a file to 'queued' status and create a matching task

        filename, task, entry: strings that uniquely identify the desired task
    """
    f = get_file(filename)
    for t in reversed(f.tasks):
        if t.name == task and t.entry == entry:
            break
    else:
        t = Task(name=task, entry=entry)
        f.tasks.append(t)
    t.status = QUEUED
    t.queue_time = datetime.datetime.now()
    session.commit()
    update_status(filename, task)

def start_task(filename, task, entry):
    """ Record that a task has begun execution.

        filename, task, entry: strings that uniquely identify the desired task
    """
    f = get_file(filename)
    #Find the desired task, and create a new one if it doesn't exist
    for t in reversed(f.tasks):
        if t.name == task and t.entry == entry:
            break
    else:
        # This task was started from command line, not queued on the server
        t = Task(name=task, entry=entry)
        f.tasks.append(t)
    t.status = IN_PROGRESS
    t.start_time = datetime.datetime.now()
    t.pid = os.getpid()
    session.commit()
    update_status(filename, task)

def end_task(filename, task, entry):
    """ Record that a task finished execution.

        Update the task's database entry, and set the matching column in files
        to DONE if it's the last task to finish

        filename, task, entry: strings that uniquely identify the desired task
    """
    f = get_file(filename)
    # The entries that have finished this task
    for t in reversed(f.tasks):
        if t.name == task and t.entry == entry:
            break
    else:
        # This task was started from command line, not queued on the server
        t = Task(name=task, entry=entry)
        f.tasks.append(t)
    t.status = DONE
    t.end_time = datetime.datetime.now()
    session.commit()
    update_status(filename, task)

def fail_task(filename, task, entry):
    """ Record that a task failed during execution.

        filename, task, entry: strings that uniquely identify the desired task
    """
    f = get_file(filename)
    for t in reversed(f.tasks):
        if t.name == task and t.entry == entry:
            break
    else:
        #No task recorded
        return
    t.status = FAILED
    t.queue_time = None
    t.start_time = None
    t.end_time = None
    session.commit()
    update_status(filename, task)
    
def update_status(filename, task):
    f = get_file(filename)
    status = {}
    if task == 'nxcombine' or task == 'nxmasked_combine':
        entries = ['entry']
    else:
        entries = ['f1', 'f2', 'f3']
    for e in entries:
        for t in reversed(f.tasks):
            if t.name == task and t.entry == e:
                status[e] = t.status
                break
        else:
            status[e] = NOT_STARTED
    if IN_PROGRESS in status.values():
        setattr(f, task, IN_PROGRESS)
    elif QUEUED in status.values():
        setattr(f, task, QUEUED)
    elif all(s == DONE for s in status.values()):
        setattr(f, task, DONE)
    else:
        setattr(f, task, NOT_STARTED)    
    session.commit()

def sync_db(sample_dir):
    """ Populate the database based on local files (overwriting if necessary)

        sample_dir: Directory containing the .nxs wrapper files
    """
    # Get a list of all the .nxs wrapper files
    wrapper_files = [os.path.join(sample_dir, filename) for filename in
                     os.listdir(sample_dir) if filename.endswith('.nxs')
                     and all(x not in filename for x in ('parent', 'mask'))]

    for wrapper_file in wrapper_files:
        sync_file(get_file(wrapper_file))
    tracked_files = list(session.query(File).all())
    for f in tracked_files:
        if f.filename not in [get_filename(w) for w in wrapper_files]:
            session.delete(f)
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
