import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError

from nexusformat.nexus import nxload
from .lock import Lock

###  DEBUGGING ###
import ipdb;

NUM_ENTRIES = 3

Base = declarative_base();
# Records files that have: not been processed, queued on the NXserver
    # but not started, started processing, finished processing
_prog = {'not started':0, 'queued':1, 'in progress':2, 'done':3}
NOT_STARTED, QUEUED, IN_PROGRESS, DONE = 0,1,2,3

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
    #Combine should probably be special since it involves all 3 samples
    nxcombine = Column(Integer, default=NOT_STARTED)

    def __repr__(self):
        not_started = [k for k,v in vars(self).items() if v == NOT_STARTED]
        queued = [k for k,v in vars(self).items() if v == QUEUED]
        in_progress = [k for k,v in vars(self).items() if v == IN_PROGRESS]
        done = [k for k,v in vars(self).items() if v == DONE]

        return "File path='{}',\n\tnot started={}\n\tqueued={}\n\t " \
                "in_progress={}\n\tdone={}".format(
                self.filename, not_started, queued, in_progress, done)

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    entry = Column(String)
    status = Column(Integer, default=QUEUED)
    # Timestamps with microsecond precision
    queue_time = Column(mysql.TIMESTAMP(fsp=6), default=datetime.datetime.now,
            nullable=False)
    start_time = Column(mysql.TIMESTAMP(fsp=6))
    end_time = Column(mysql.TIMESTAMP(fsp=6))
    # TODO: Should this be set on task start? also probably shouldn't use
            # pid of *this* process. How do I get the pid of the worker?
    pid = Column(Integer, default=os.getpid)
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
        echo: whether or not to echo the emmited SQL statements
    """
    #MySQL database, logging turned on
    engine = create_engine(connect, echo=echo)
    Base.metadata.create_all(engine)
    global session
    session = sessionmaker(bind=engine)()

def record_queued_task(filename, task, entry):
    """ Update a file to 'queued' status and create a matching task """
    filename = os.path.realpath(filename)
    row = session.query(File).filter(File.filename == filename).scalar()
    if row is None:
        print("ERROR: NXdatabase could not find file '{}'".format(filename))
        return
    row.tasks.append(Task(name=task, entry=entry))
    setattr(row, task, QUEUED)
    session.commit()

def update_task(filename, task, entry, status):
    """ Update an existing task, recording that it has started or finished.

        filename, task, entry: strings that uniquely identify the desired task
        status: string, should be 'in progress' or 'done'
    """
    filename = os.path.realpath(filename)
    #Make sure we're only getting one result
    row = session.query(File).filter(File.filename == filename).scalar()
    if row is None:
        print("ERROR: NXdatabase could not find file '{}'".format(filename))
        return
    #Find the index of the desired task
    for i, t in enumerate(row.tasks):
        if t.name == task and t.entry == entry and (
                t.status == QUEUED or t.status == IN_PROGRESS):
            break
    else:
        print('ERROR: NXdatabase could not find running task {} on {}/{}'
                    .format(task, filename, entry))
        return
    row.tasks[i].status = _prog[status]
    if _prog[status] == DONE:
        row.tasks[i].end_time = datetime.datetime.now()
    else:
        row.tasks[i].start_time = datetime.datetime.now()
    # Update the status of the file to 'done' if we've finished all the entries,
    #   otherwise to 'in progress'
    if len(row.tasks) >= NUM_ENTRIES and all(
                t.status == DONE for t in row.tasks if t.name == task):
        setattr(row, task, DONE)
    else:
        setattr(row, task, IN_PROGRESS)
    session.commit()

def get_tasks(filename):
    """ Return the status of each task for filename

        filename: string, absolute path of wrapper file to query
     """
    f = session.query(File) \
            .filter(File.filename == filename) \
            .one()
    return f


def sync_db(sample_dir):
    """ Populate the database based on local files (overwritting if necessary)

        sample_dir: Directory containing the .nxs wrapper files
            (ie NXreduce.base_directory)
    """
    from nxrefine.nxreduce import NXReduce
    # Get a list of all the .nxs wrapper files
    wrapper_files = ( os.path.join(sample_dir, filename) for filename in
                    os.listdir(sample_dir) if filename.endswith('.nxs')
                    and all(x not in filename for x in ('parent', 'mask')) )
    for w in wrapper_files:
        w = os.path.realpath(w)
        print('Found file {}'.format(w))
        # If this file is already in the db, skip processing it
        res = session.query(File)           \
                .filter(File.filename == w) \
                .all()
        if len(res) > 0:
            print("ERROR: NXDatabase found preexisting file '{}'".format(w))
            continue

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
        tasks = { t: 0 for t in ('data', 'nxlink', 'nxmax', 'nxfind', 'nxcopy',
                'nxrefine', 'nxtransform', 'nxcombine') }

        for e in entries:
            if e in root and 'data' in root[e] and 'instrument' in root[e]:
                if e+'.h5' in scan_files or e+'.nxs' in scan_files:
                    tasks['data'] += 1
                if 'nxlink' in root[e]:
                    tasks['nxlink'] += 1
                if 'nxmax' in root[e]:
                    tasks['nxmax'] += 1
                if 'nxfind' in root[e]:
                    tasks['nxfind'] += 1
                if 'nxcopy' in root[e] or is_parent(w, sample_dir):
                    tasks['nxcopy'] += 1
                if 'nxrefine' in root[e]:
                    tasks['nxrefine'] += 1
                if 'nxtransform' in root[e]:
                    tasks['nxtransform'] += 1
                if 'nxcombine' in root['entry']:
                    tasks['nxcombine'] += 1

        f = File(filename = w)
        for task, val in tasks.items():
            if val == 0:
                setattr(f, task, NOT_STARTED)
            elif val == NUM_ENTRIES:
                setattr(f, task, DONE)
            else:
                setattr(f, task, IN_PROGRESS)
        session.add(f)
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
