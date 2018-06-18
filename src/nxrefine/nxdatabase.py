import os

from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

from nexusformat.nexus import nxload

import nxrefine.nxreduce

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
    import ipdb; ipdb.set_trace()
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
        with nxrefine.nxreduce.Lock(w):
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
                if 'nxcombine' in root['entry'] or 'transform.nxs' in files \
                        or 'masked_transform.nxs' in files:
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
    session.commit()

""" Sample_dir should be the GUPxxx/agcrse2/xtalX directory """
def is_parent(wrapper_file, sample_dir):
    parent_file = os.path.join(sample_dir,
            os.path.basename(os.path.dirname(sample_dir) + '_parent.nxs'))
    if os.path.exists(parent_file):
        return wrapper_file == os.path.realpath(parent_file)
    else:
        return False


# sync_db('')
