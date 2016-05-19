# -*- coding: utf-8 -*-
"""
    onboarder
    ~~~~~~~~
    app.views (app)

"""

import os, json, traceback
from os.path import abspath
from itertools import islice, chain
from collections import defaultdict

import tornado.ioloop
import tornado.web
from newspaper import Article
from newspaper.configuration import Configuration
import feedparser

from gevent.pool import Pool
from scipy.spatial.distance import cdist
import numpy as np

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import indicoio

from cluster.models import Entry, Base
from cluster.utils import make_feature_vectors, DBScanClustering, highest_scores
from .search.client import ESConnection
from .errors import ClusterError

indicoio.config.api_key = os.getenv('INDICO_API_KEY')
DEBUG = os.getenv('DEBUG', True) != 'False'

POOL = Pool(8)
REQUEST_HEADERS = {'screensize': '2556x1454', 'uid': 'AAAAAF41ulYaCWhtAR9LWQ=='}
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.39 Safari/537.36'
HEADERS = {'User-Agent': USER_AGENT}
NEWSPAPER_CONFIG = Configuration()
NEWSPAPER_CONFIG.fetch_images = False
NEWSPAPER_CONFIG.memoize_articles = False
NEWSPAPER_CONFIG.request_timeout = 5
NEWSPAPER_CONFIG.browser_user_agent = HEADERS['User-Agent']
NEWSPAPER_CONFIG.http_success_only = True
feedparser.USER_AGENT = USER_AGENT

engine = create_engine('sqlite:///' + abspath(os.path.join(__file__, "../../text-mining.db")))
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

INDICO_VALUES = ['keywords', 'title_keywords', 'people', 'places', 'organizations']
def batched(iterable, size):
    sourceiter = iter(iterable)
    while True:
        batchiter = islice(sourceiter, size)
        yield list(chain([batchiter.next()], batchiter))

def pull_from_named_entities(list_of_entities, threshold):
    return list(set([entity['text'] for entity in list_of_entities if entity['confidence'] >= threshold]))

def create_full_cluster_list(cluster_info, key):
    return [entity for article in cluster_info['articles'] for entity in article['indico'].get(key)]

def create_full_cluster_dict(cluster_info, key):
    return {k: v for article in cluster_info['articles'] for k, v in article['indico'].get(key).items()}

def update_articles(articles):
    # indico = article.pop('indico')
    text = [article.get("text") for article in articles]
    indico_analysis = indicoio.analyze_text(text, apis=['keywords', 'sentiment', 'people', 'places', 'organizations'], api_key="fb039b9dafb34eeb83aa3307e8efb167")
    
    for api, results in indico_analysis.items():
        for i, result in enumerate(results):
            articles[i]['indico'][api] = result

    # article['keywords'] = filter(None, list(set([key for key in indico['keywords'].keys() if indico['keywords'][key] > 0.7])))
    # article['text_features'] = indico.get('text_features')
    # article['people'] = pull_from_named_entities(indico['people'], 0.7)
    # article['places'] = pull_from_named_entities(indico['places'], 0.7)
    # article['organizations'] = pull_from_named_entities(indico['organizations'], 0.7)
    return articles


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('text-mining.html', DEBUG=DEBUG)

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
                print features_matrix[0:5]
                feature_vectors = make_feature_vectors(features_matrix, "tf-idf")
                if not feature_vectors.shape[0]:
                    raise Exception('empty results')
            except Exception as e:
                self.write(json.dumps({
                    'error': e.args[0]
                }))
                return


            # for i in [.7, .6, .5, .4, .3, .2, .1]:
            values = {}
            for i in [.1, .2, .3, .4, .5, .6, .7, .8, .9]:
                all_clusters, all_similarities = DBScanClustering(feature_vectors, algorithm="brute", metric="cosine", eps=i)
                values[i] = len(set(all_clusters))
                from collections import Counter
                print i, values[i], Counter(all_clusters)
                if values[i] - 1 >= 4:
                    break
            
            best_epsilon = max(values.items(), key=lambda x: x[1])[0]
            all_clusters, all_similarities = DBScanClustering(feature_vectors, algorithm="brute", metric="cosine", eps=best_epsilon)

            clusters = []
            top_entry_dicts = []
            relevant_features = []
            similarities = []
            num_added = 0
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
                # cluster_info['articles'] = update_articles(cluster_info['articles'])
                
                cluster_info['people'] = create_full_cluster_list(cluster_info, 'people')
                cluster_info['places'] = create_full_cluster_list(cluster_info, 'places')
                cluster_info['organizations'] = create_full_cluster_list(cluster_info, 'organizations')

                all_keywords = create_full_cluster_dict(cluster_info, 'keywords')
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

        # with open('somedata.txt', 'r') as f:
        #     self.write(json.dumps(json.loads(f.read())))
            # f.write(json.dumps(result_dict))
        self.write(json.dumps(result_dict))


# NOTE: nginx will be routing /text-mining requests to this app. For example, posts in javascript
#       need to specify /text-mining/query, not /query
application = tornado.web.Application(
    [(r"/text-mining", MainHandler), (r"/text-mining/query", QueryHandler)],
    template_path=abspath(os.path.join(__file__, "../../templates")),
    static_url_prefix="/text-mining/static/",
    static_path=abspath(os.path.join(__file__, "../../static")),
    cookie_secret="verytemporarycookiesecret",
    debug=DEBUG
)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.current().start()
