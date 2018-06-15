from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#MySQL database, logging turned on
engine = create_engine('mysql+cymysql://python:pythonpa^ss@18.219.38.132/test',
        echo=True)
Base = declarative_base();


class File(Base):
    __tablename__ = 'files'
    # Records files that have: not been processed, queued on the NXserver
        # but not started, started processing, finished processing
    _progress = Enum('not started', 'queued', 'in progress', 'done')

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
        return "<File(filename='{})>".format(
                self.filename)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

#Everything below is an example of how this works
test_file = File(filename='test.txt', nxmax='in progress')
print(test_file)

#add some files to db
session.add_all([
    test_file,
    File(filename='/home/pgardner/secondFile'),
    File(filename='thirdFile.exe')
])
session.commit()

#show all the files
for f in session.query(File).all():
    print(f)

#Select only the .txt files
for f in session.query(File.filename).filter(File.filename.like('%.txt')):
    print(f)
