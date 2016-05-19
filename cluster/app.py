# -*- coding: utf-8 -*-
"""
    onboarder
    ~~~~~~~~
    app.views (app)

"""

import os, json
from os.path import abspath
from collections import defaultdict

import tornado.ioloop
import tornado.web
from scipy.spatial.distance import cdist
import numpy as np

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import indicoio

from cluster.models import Bookmark, Base
from cluster.utils import make_feature_vectors, DBScanClustering, highest_scores
from .search.client import ESConnection
from .errors import ClusterError

DEBUG = os.getenv('DEBUG', True) != 'False'

# SETTING UP SQLAlchemy
engine = create_engine('sqlite:///' + abspath(os.path.join(__file__, "../../text-mining.db")))
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

# TODO - ensure these include all that they should
INDICO_VALUES = ['keywords', 'title_keywords', 'people', 'places', 'organizations']

def create_full_cluster_list(cluster_info, key):
    return [entity for article in cluster_info['articles'] for entity in article['indico'].get(key)]

def create_full_cluster_dict(cluster_info, key):
    return {k: v for article in cluster_info['articles'] for k, v in article['indico'].get(key).items()}

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
            es = ESConnection("http://localhost:9200", index='indico-cluster-data')
            data = json.loads(self.request.body)
            query = data.get('query')

            self.set_secure_cookie('current_search', query)

            entries = es.search(query, limit=500)
            if len(entries) < 5:
                self.write(json.dumps({'error':'bad query'}))
                return

            seen_titles = set()
            seen_add = seen_titles.add
            entries = [entry for entry in entries if not (entry['title'] in seen_titles or seen_add(entry['title']))]

            if not entries:
                self.write(json.dumps({'error': 'bad query'}))
                return

            features_matrix = [entry['text'] for entry in entries]
            try:
                feature_vectors = make_feature_vectors(features_matrix, "tf-idf")
                if not feature_vectors.shape[0]:
                    raise Exception('empty results')
            except Exception as e:
                self.write(json.dumps({
                    'error': e.args[0]
                }))
                return


            values = {}
            for i in [.1, .2, .3, .4, .5, .6, .7, .8, .9]:
                all_clusters, all_similarities = DBScanClustering(feature_vectors, algorithm="brute", metric="cosine", eps=i)
                values[i] = len(set(all_clusters))
                if values[i] - 1 >= 4:
                    break

            best_epsilon = max(values.items(), key=lambda x: x[1])[0]
            all_clusters, all_similarities = DBScanClustering(feature_vectors, algorithm="brute", metric="cosine", eps=best_epsilon)

            clusters = []
            top_entry_dicts = []
            relevant_features = []
            similarities = []
            count = defaultdict(int)
            for i in xrange(len(all_clusters)):
                if all_clusters[i] >= 0:
                    count[all_clusters[i]] += 1
                    if count[all_clusters[i]] > 20:
                        continue
                    clusters.append(all_clusters[i])
                    top_entry_dicts.append(entries[i])
                    relevant_features.append(feature_vectors[i])
                    similarities.append(all_similarities[i])

            result_dict = {}
            cluster_features = defaultdict(list)
            for entry, cluster, feature_list, distance in zip(top_entry_dicts, clusters, relevant_features, similarities):
                entry['cluster'] = cluster
                entry["distance"] = distance
                cluster_features[cluster].append(feature_list)

                if cluster not in result_dict.keys():
                    result_dict[cluster] = {}
                    result_dict[cluster]['articles'] = []
                    for val in INDICO_VALUES:
                        result_dict[cluster][val] = defaultdict(int)

                result_dict[cluster]['articles'].append(entry)
                for val in INDICO_VALUES[:2]:
                    for word in entry['indico'][val]:
                        result_dict[cluster][val][word] += 1

                for val in INDICO_VALUES[2:]:
                    for word in entry['indico'][val]:
                        result_dict[cluster][val][word['text']] += 1


            cluster_center = {}
            for cluster, features_list in cluster_features.items():
                features_list = [np.asarray(el.todense()).flatten() for el in features_list]
                array_features = np.array(features_list)
                distance_sums = [sum(dists) for dists in cdist(array_features, array_features, 'euclidean')]
                cluster_center[cluster] = distance_sums.index(min(distance_sums))

            keywords_master_list = []
            title_keywords_master_list = []
            for cluster, cluster_info in result_dict.items():
                cluster_info['people'] = create_full_cluster_list(cluster_info, 'people')
                cluster_info['places'] = create_full_cluster_list(cluster_info, 'places')
                cluster_info['organizations'] = create_full_cluster_list(cluster_info, 'organizations')

                all_keywords = create_full_cluster_dict(cluster_info, 'title_keywords')
                sorted_keywords = sorted(all_keywords.items(), key=lambda k: k[1])
                cluster_info['keywords'] = sorted_keywords[-min(10, len(sorted_keywords)):]
                keywords_master_list.extend([val[0] for val in cluster_info['keywords'] if val[0] != "Shutterstock"])

                sorted_keywords = sorted(cluster_info['title_keywords'].items(), key=lambda k: k[1], reverse=True)
                cluster_info['title_keywords'] = sorted_keywords[:min(5, len(sorted_keywords))]
                title_keywords_master_list.extend([val[0] for val in cluster_info['title_keywords'] if val[0] != "Shutterstock"])

                result_dict[cluster] = cluster_info

            for cluster, values in result_dict.items():
                values['keywords'] = [value for value in values['keywords']
                                      if keywords_master_list.count(value[0]) <= max(len(result_dict)*.35, 1)]
                values['keywords'] = [val[0] for val in values['keywords']][-min(3, len(values['keywords'])):]

                values['title_keywords'] = [value for value in values['title_keywords']
                                      if title_keywords_master_list.count(value[0]) <= max(len(result_dict)*.35, 1)]
                values['title_keywords'] = [val[0] for val in values['title_keywords']][-min(3, len(values['title_keywords'])):]
                values['cluster_title'] = values['articles'][cluster_center[cluster]]
                result_dict[cluster] = values

        except ClusterError as e:
            self.write(json.dumps({"error": str(e)}))

        self.write(json.dumps(result_dict))

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
        link, title, key, origin  = data['link'], data['title'], data['key'], data['origin']
        try:
            bookmark = Bookmark(link=link, title=title, key=key, origin=origin, search=search)
            session = DBSession()
            session.add(bookmark)
            session.commit()
            session.close()
            self.write(json.dumps({'success': True, 'message': 'Successfully added new bookmark!'}))
        except Exception as e:
            self.write(json.dumps({'success': False, 'message': 'Something went wrong, you may already have that link bookmarked.'}))


# NOTE: nginx will be routing /text-mining requests to this app. For example, posts in javascript
#       need to specify /text-mining/query, not /query
application = tornado.web.Application(
    [(r"/text-mining", MainHandler), (r"/text-mining/bookmarks", BookmarkHandler), (r"/text-mining/query", QueryHandler)],
    template_path=abspath(os.path.join(__file__, "../../templates")),
    static_url_prefix="/text-mining/static/",
    static_path=abspath(os.path.join(__file__, "../../static")),
    cookie_secret="verytemporarycookiesecret", #FIXME
    debug=DEBUG
)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.current().start()
