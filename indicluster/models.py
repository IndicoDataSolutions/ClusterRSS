import json
import os.path

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from sqlalchemy import create_engine

Base = declarative_base()

class Entry(Base):
    """
    text:
        - text as parsed by Newspaper python lib
    title:
        - article title
    link:
        - link to original source of text
    indico:
        - text features
        - people
        - places
        - organizations
        - keywords v2
    group:
        - label for group of RSS feeds
          that all contain similar content
    """
    __tablename__ = 'entries'

    id = Column('id', Integer, primary_key=True)
    text = Column('text', String)
    title = Column('title', String)
    link = Column('link', String, unique=True)
    indico = Column('indico', String)
    group = Column('group', String)
    rss_feed = Column('rss_feed', String)

    def __init__(self, text, title, link, indico, group, rss_feed):
        self.text = text
        self.title = title
        self.link = link
        self.indico = json.dumps(indico)
        self.group = group
        self.rss_feed = rss_feed

if __name__ == "__main__":
    # initialize the db
    engine = create_engine('sqlite:///' + os.path.abspath(os.path.join(__file__, "../../text-mining.db")))
    Base.metadata.create_all(engine)
