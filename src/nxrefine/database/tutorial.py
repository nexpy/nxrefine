from sqlalchemy import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

engine = create_engine('sqlite:///:memory:', echo=True)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True);
    name = Column(String)
    fullname = Column(String)
    password = Column(String)

    def __repr__(self):
        return "<User(name='%s', fullname='%s', password='%s')>" % (
                self.name, self.fullname, self.password)


class Address(Base):
    __tablename__ = 'addresses'

    id= Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey(User.id))

    user = relationship("User", back_populates='addresses')

    def __repr__(self):
        return "<Address(email='%s')>" % self.email

User.addresses = relationship("Address", order_by=Address.id, back_populates='user')

Base.metadata.create_all(engine);
