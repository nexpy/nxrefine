import os
import argparse
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError

from nexusformat.nexus import nxload
from .lock import Lock

###  DEBUGGING ###
import ipdb;

#MySQL database, logging turned on
engine = create_engine('mysql+mysqlconnector://python:pythonpa^ss@18.219.38.132/test',
        echo=True)
Base = declarative_base();
# Records files that have: not been processed, queued on the NXserver
    # but not started, started processing, finished processing
_progress = Enum('not started', 'queued', 'in progress', 'done')

class File(Base):
    __tablename__ = 'files'

    filename = Column(String(255), nullable=False, primary_key=True)
    data = Column(_progress, server_default='not started')
    nxlink = Column(_progress, server_default='not started')
    nxmax = Column(_progress, server_default='not started')
    nxfind = Column(_progress, server_default='not started')
    nxcopy = Column(_progress, server_default='not started')
    nxrefine = Column(_progress, server_default='not started')
    nxtransform = Column(_progress, server_default='not started')
    #Combine should probably be special since it involves all 3 samples
    nxcombine = Column(_progress, server_default='not started')

    def __repr__(self):
        not_started = [k for k,v in vars(self).items() if v == 'not started']
        queued = [k for k,v in vars(self).items() if v == 'queued']
        in_progress = [k for k,v in vars(self).items() if v == 'in progress']
        done = [k for k,v in vars(self).items() if v == 'done']

        return "File path='{}',\n\tnot started={}\n\tqueued={}\n\t " \
                "in_progress={}\n\tdone={}".format(
                self.filename, not_started, queued, in_progress, done)

class Task(Base):
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True)
    name = Column(String(31), nullable=False)
    entry = Column(Integer)
    status = Column(_progress, server_default='queued')
    # Timestamps with microsecond precision
    queue_time = Column(mysql.TIMESTAMP(fsp=6), default=datetime.datetime.now,
            nullable=False)
    start_time = Column(mysql.TIMESTAMP(fsp=6))
    end_time = Column(mysql.TIMESTAMP(fsp=6))
    # TODO: Should this be set on task start? also probably shouldn't use
            # pid of *this* process. How do I get the pid of the worker?
    pid = Column(Integer, default=os.getpid, nullable=False)
    filename = Column(String(255), ForeignKey('files.filename'), nullable=False)

    file = relationship('File', back_populates='tasks')

    def __repr__(self):
        return "<Task {} on {}, entry {}, pid={}>".format(self.name,
                self.filename, self.entry, self.pid)

File.tasks = relationship('Task', back_populates='file', order_by=Task.id)

Base.metadata.create_all(engine)
session = sessionmaker(bind=engine)()

""" Update a file to 'queued' status and create a matching task """
def record_queued_task(filename, task, entry):
    row = session.query(File).filter(File.filename == filename).scalar()
    if row is None:
        print("Could not find file {}".format(filename))
        return
    row.tasks.append(Task(name=task, entry=entry))
    setattr(row, task, 'queued')
    session.commit()

""" Update database entry for filename, recording that task started or finished.
        status should be 'in progress' or 'done' """
def update_task(filename, task, entry, status):
    #Make sure we're only getting one result
    row = session.query(File).filter(File.filename == filename).scalar()
    if row is None:
        print("Could not find file {}".format(filename))
        return
    setattr(row, task, status)
    #Find the index of the desired task
    for i, t in enumerate(row.tasks):
        if t.name == task:
            break
    row.tasks[i].status = status
    if status == 'done':
        row.tasks[i].end_time = datetime.datetime.now()
    else:
        row.tasks[i].start_time = datetime.datetime.now()
    session.commit()

""" Return Task database entry for task in filename """
def get_status(filename, task):
    return session.query(Task) \
            .filter(Task.filename == filename) \
            .filter(Task.name == task) \
            .scalar()

""" Populate the database based on local files. Will overwrite current
    database contents. sample_dir should be NXreduce.base_directory """
def sync_db(sample_dir):
    # Get a list of all the .nxs wrapper files
    wrapper_files = ( os.path.join(sample_dir, filename) for filename in
                    os.listdir(sample_dir) if filename.endswith('.nxs')
                    and all(x not in filename for x in ('parent', 'mask')) )
    for w in wrapper_files:
        base_name = os.path.basename(os.path.splitext(w)[0])
        scan_label = base_name.split('_')[1]
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
                if 'nxlink' in root[e] or 'logs' in root[e]['instrument']:
                    tasks['nxlink'] += 1
                if 'nxmax' in root[e] or 'maximum' in root[e]['data'].attrs:
                    tasks['nxmax'] += 1
                if 'nxfind' in root[e] or 'peaks' in root[e]:
                    tasks['nxfind'] += 1
                if 'nxcopy' in root[e] or is_parent(w, sample_dir):
                    tasks['nxcopy'] += 1
                if 'nxrefine' in root[e]:
                    tasks['nxrefine'] += 1
                if 'nxtransform' in root[e] or e+'_transform.nxs' in scan_files:
                    tasks['nxtransform'] += 1
                if 'nxcombine' in root['entry'] or 'transform.nxs' in scan_files \
                        or 'masked_transform.nxs' in scan_files:
                    tasks['nxcombine'] += 1
        f = File(filename = w)
        for task, val in tasks.items():
            if val == 0:
                setattr(f, task, 'not started')
            elif val == 3:
                setattr(f, task, 'done')
            else:
                setattr(f, task, 'in progress')
        session.add(f)
    try:
        session.flush()
    # Catch if the file already exists in the database
    except IntegrityError as e:
        session.rollback()
        for err in e.params:
            print("ERROR: preexisting entry for '{}'".format(err['filename']))
    else:
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Populate the database based \
            on local NeXus files")
    parser.add_argument('sync', action='store_true',
                        help="Specify 'sync' to sync local files with the database")
