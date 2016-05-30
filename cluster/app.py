# -*- coding: utf-8 -*-
"""
    onboarder
    ~~~~~~~~
    app.views (app)

"""

import os, json
from os.path import abspath
import argparse

import tornado.ioloop
import tornado.web
import numpy as np

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cluster.models import Bookmark, Base
from cluster.clustering import DBScanClusterer, generate_clusters_dict
from .search.client import ESConnection
from .errors import ClusterError
from .utils import list_of_seq_unique_by_key

DEBUG = os.getenv('DEBUG', True) != 'False'

# SETTING UP SQLAlchemy
engine = create_engine('sqlite:///' + abspath(os.path.join(__file__, "../../text-mining.db")))
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
ES = ESConnection("http://localhost:9200", index='indico-cluster-data')

class QueryHandler(tornado.web.RequestHandler):
    """
    GET:
        - Query for all unique groups
        - Return json of group names for use in dropdown on frontend
    POST:
        - Query for all entries for a given group
        - Filter by relevance to a given query (cosine similarity of text features)
        - Take that collection of articles, run KMeans
        or other clustering algorithm on that subset
        - Assign each article to a numeric cluster
        - Pass json serialized articles + cluster numbers to the frontend
    """
    def get(self):
        self.write(json.dumps({'meow': 'meow'}))

    def post(self):
        try:
            data = json.loads(self.request.body)
            query = data.get('query')
            self.set_secure_cookie('current_search', query)

            entries = ES.search(query, limit=1000)
            entries = list_of_seq_unique_by_key(entries, "title")

            if len(entries) < 5:
                raise ClusterError("insufficient results for given query")

            feature_vectors = np.asarray([json.loads(entry['finance_embeddings']) for entry in entries])
            all_clusters, all_similarities = DBScanClusterer(feature_vectors, algorithm="brute", metric="cosine").get_clusters()
            result_dict = generate_clusters_dict(entries, all_clusters, all_similarities, feature_vectors)

            self.write(json.dumps(result_dict))

        except ClusterError as e:
            import traceback; traceback.print_exc()
            self.write(json.dumps({"error": str(e)}))

        except Exception as e:
            import traceback; traceback.print_exc()
            self.write(json.dumps({
                'error': "Uncaught error - " + str(e)
            }))

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('text-mining.html', DEBUG=DEBUG)

class BookmarkHandler(tornado.web.RequestHandler):

    def get(self):
        """shows added images"""
        session = DBSession()
        bookmarks = session.query(Bookmark.search).distinct(Bookmark.search)
        query_groups = [bookmark[0] for bookmark in bookmarks]
        bookmarks = {group: session.query(Bookmark).filter_by(search=group).all() for group in query_groups}
        session.close()
        self.render('dashboard.html', bookmarks=bookmarks, groups=query_groups)

    def post(self):
        """add image link to bookmarks"""
        data = json.loads(self.request.body)
        search = self.get_secure_cookie('current_search')
        link, text, title, key, origin  = data['link'], data['text'], data['title'], data['key'], data['origin']
        try:
            bookmark = Bookmark(text=text, link=link, title=title, key=key, origin=origin, search=search)
            session = DBSession()
            session.add(bookmark)
            session.commit()
            session.close()
            self.write(json.dumps({'success': True, 'message': 'Successfully added new bookmark!'}))
        except Exception:
            self.write(json.dumps({'success': False, 'message': 'Something went wrong, you may already have that link bookmarked.'}))


class Practice(tornado.web.RequestHandler):

    def get(self):
        self.render('practice.html')

# NOTE: nginx will be routing /text-mining requests to this app. For example, posts in javascript
#       need to specify /text-mining/query, not /query
application = tornado.web.Application(
    [
        (r"/text-mining", MainHandler),
        (r"/text-mining/bookmarks", BookmarkHandler),
        (r"/text-mining/query", QueryHandler),
        (r"/text-mining/practice", Practice)
    ],
    template_path=abspath(os.path.join(__file__, "../../templates")),
    static_url_prefix="/text-mining/static/",
    static_path=abspath(os.path.join(__file__, "../../static")),
    cookie_secret="verytemporarycookiesecret", #FIXME
    debug=DEBUG
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8002)
    args = parser.parse_args()

    application.listen(args.port)
    tornado.ioloop.IOLoop.current().start()
