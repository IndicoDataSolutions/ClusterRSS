import os.path

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine

Base = declarative_base()


class Bookmark(Base):
    """
    key:
        - API key associated with bookmark link
    link:
        - link to image being bookmarked
    title:
        - user added title for image
    """
    __tablename__ = 'bookmarks'

    id = Column('id', Integer, primary_key=True)
    key = Column('api_key', String)
    link = Column('link', String)
    text = Column('text', String)
    title = Column('title', String)
    origin = Column('origin', String)
    search = Column('search', String)

    def __init__(self, key, link, text, title, origin, search):
        self.key = key
        self.link = link
        self.text = text
        self.title = title
        self.origin = origin
        self.search = search

if __name__ == "__main__":
    # initialize the db
    engine = create_engine('sqlite:///' + os.path.abspath(os.path.join(__file__, "../../text-mining.db")))
    Base.metadata.create_all(engine)
