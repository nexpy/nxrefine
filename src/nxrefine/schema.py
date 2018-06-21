from sqlalchemy import create_engine, Column, Integer, String, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects import mysql

import datetime
import os

### DEBUGGING ###
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
    start = Column(mysql.TIMESTAMP(fsp=6))
    end = Column(mysql.TIMESTAMP(fsp=6))
    pid = Column(Integer, default=os.getpid, nullable=False)
    filename = Column(String(255), ForeignKey('files.filename'), nullable=False)

    file = relationship('File', back_populates='tasks')

    def __repr__(self):
        return "<Task {} on {} entry {}, pid={}>".format(self.name,
                self.filename, self.entry, self.pid)

File.tasks = relationship('Task', back_populates='file', order_by=Task.id)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
ipdb.set_trace()

# #Everything below is an example of how this works
# test_file = File(filename='test.txt', nxmax='in progress')
# print(test_file)
#
# #add some files to db
# session.add_all([
#     test_file,
#     File(filename='/home/pgardner/secondFile'),
#     File(filename='thirdFile.exe')
# ])
# session.commit()
#
# #show all the files
# for f in session.query(File).all():
#     print(f)
#
# #Select only the .txt files
# for f in session.query(File.filename).filter(File.filename.like('%.txt')):
#     print(f)
