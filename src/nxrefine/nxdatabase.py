from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker

engine = create_engine('mysql+cymysql://python:pythonpa^ss@18.219.38.132/test',
        echo=True)

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
def sync_db():
    return None
