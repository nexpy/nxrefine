import os

from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

from nxrefine.nxreduce import Lock


engine = create_engine('mysql+cymysql://python:pythonpa^ss@18.219.38.132/test',
        echo=False)

Base = automap_base()

class File(Base):
    __tablename__='files'

    def __repr__(self):
        not_started = [k for k,v in vars(self).items() if v == 'not started']
        queued = [k for k,v in vars(self).items() if v == 'queued']
        in_progress = [k for k,v in vars(self).items() if v == 'in progress']
        done = [k for k,v in vars(self).items() if v == 'done']

        return "File path='{}', \n\tnot started={} \n\tqueued={}\n\t " \
                "in_progress={} \n\tdone={}".format(
                self.filename, not_started, queued, in_progress, done)

Base.prepare(engine, reflect=True)
session = sessionmaker(bind=engine)()

# ### Testing ###
# session.add_all([File(filename='test.txt', nxlink='in progress'),
#     File(filename='hey/another.txt', nxlink='done', nxmax='done', nxfind='in progress')
# ])
# session.commit()
# for inst in session.query(File):
#     print(inst)

""" Update database entry for filename """
def update_db(filename, task, status):
    #Make sure we're only getting one result
    row = session.query(File).filter(File.filename == filename).scalar()
    if row is None:
        print("No file by that name exists")
        return
    setattr(row, task, status)
    session.commit()

""" Return database entry for task in filename """
def get_status(filename, task):
    status = session.query(File.filename, getattr(File, task)).filter(
            File.filename == filename).scalar()
    return scalar[0]

""" Populate the database based on local files. Will overwrite current
    database contents """
def sync_db(sample_dir):

    # Get a list of all the .nxs wrapper files
    wrapper_files = ( os.path.join(sample_dir, filename) for filename in
                    os.listdir(sample_dir) if filename.endswith('.nxs')
                    and all(x not in filename for x in ('parent', 'mask')) )

    for w in wrapper_files:
        base_name = os.path.basename(os.path.splitext(wrapper_file)[0])
        scan_label = base_name.replace(self.sample+'_', '')
        scan_dir = os.path.join(sample_dir, scan_label)
        try:
            scan_files = os.listdir(scan_dir)
        except OSError:
            scan_files = []
        with Lock(w):
            root = nxload(w)
            entries = (e for e in root.entries if e != 'entry')
        # Track how many entries have finished each task
        tasks = { t: 0 for t in ('data', 'nxlink', 'nxmax', 'nxfind', 'nxcopy', 'nxrefine',
                'nxtransform', 'nxcombine') }
        for t in tasks:
            for e in entries:
                # TODO: create dictionary of lambdas to check task completion conditions?
