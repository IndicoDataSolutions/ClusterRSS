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
from selenium import webdriver

from gevent.pool import Pool
from scipy.spatial.distance import cdist
import numpy as np

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import indicoio

from indicluster.models import Entry, Base
from indicluster.utils import make_feature_vectors, DBScanClustering
from .search.client import ESConnection

indicoio.config.api_key = os.getenv('INDICO_API_KEY')
DEBUG = os.getenv('DEBUG', True) != 'False'

DRIVER = webdriver.PhantomJS('/usr/local/bin/phantomjs')
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

def _read_text_from_url(url):
    try:
        article = Article(url, config=NEWSPAPER_CONFIG)
        DRIVER.get(url)
        article.set_html(DRIVER.page_source)
        article.parse()
        assert article.text
        return article.text
    except Exception as e:
        traceback.print_exc()
        # page doesn't exist or couldn't be parsed
        return ""

def pull_from_named_entities(list_of_entities, threshold):
    return list(set([entity['text'] for entity in list_of_entities if entity['confidence'] >= threshold]))

def update_article(article):
    indico = article.pop('indico')
    article['keywords'] = filter(None, list(set([key for key in indico['keywords'].keys() if indico['keywords'][key] > 0.7])))
    article['text_features'] = indico.get('text_features')
    article['people'] = pull_from_named_entities(indico['people'], 0.7)
    article['places'] = pull_from_named_entities(indico['places'], 0.7)
    article['organizations'] = pull_from_named_entities(indico['organizations'], 0.7)
    return article


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
        session = DBSession()
        entries = session.query(Entry.group).all()
        groups = list(set([entry[0] for entry in entries]))
        session.commit()
        session.close()
        self.write(json.dumps(groups))

    def post(self):
        es = ESConnection("localhost:9200")
        data = json.loads(self.request.body)
        group = data.get('group')
        query = data.get('query')

        entries = es.search(query, limit=500)

        if not entries:
            self.write(json.dumps({'error': 'bad query'}))
            return

        features_matrix = [entry['text'] for entry in entries]
        feature_vectors = make_feature_vectors(features_matrix, "tf-idf")

        for i in [0, .1, .2, .3, .4, .5]:
            all_clusters, centers = DBScanClustering(feature_vectors, metric="euclidean", eps=1.0+i)
            if sum([1 for cluster in all_clusters if cluster != -1]) > len(all_clusters)/4:
                break

        clusters = []
        top_entry_dicts = []
        relevant_features = []
        num_added = 0
        for i in xrange(len(all_clusters)):
            if all_clusters[i] >= 0:
                clusters.append(all_clusters[i])
                top_entry_dicts.append(entries[i])
                relevant_features.append(feature_vectors[i])
                num_added += 1
                if num_added == 50:
                    break

        result_dict = {}
        cluster_features = defaultdict(list)
        for entry, cluster, feature_list in zip(top_entry_dicts, clusters, relevant_features):
            entry['cluster'] = cluster
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
        for cluster, values in result_dict.items():
            third_highest = sorted(values['people'].values(), reverse=True)[min(2, len(values['people'].values())-1)]
            values['people'] = [person for person, number in values['people'].items()
                                if number >= third_highest and person != "Shutterstock"]
            third_highest = sorted(values['organizations'].values(), reverse=True)[min(2, len(values['organizations'].values())-1)]
            values['organizations'] = [org for org, number in values['organizations'].items()
                                if number >= third_highest and org != "Shutterstock"]
            third_highest = sorted(values['places'].values(), reverse=True)[min(2, len(values['places'].values())-1)]
            values['places'] = [place for place, number in values['places'].items()
                                if number >= third_highest and place != "Shutterstock"]

            sorted_keywords = sorted(values['keywords'].items(), key=lambda k: k[1])
            values['keywords'] = sorted_keywords[-min(10, len(sorted_keywords)):]
            keywords_master_list.extend([val[0] for val in values['keywords'] if val[0] != "Shutterstock"])

            sorted_keywords = sorted(values['title_keywords'].items(), key=lambda k: k[1])
            values['title_keywords'] = sorted_keywords[-min(10, len(sorted_keywords)):]
            title_keywords_master_list.extend([val[0] for val in values['title_keywords'] if val[0] != "Shutterstock"])

            result_dict[cluster] = values


        for cluster, values in result_dict.items():
            values['keywords'] = [value for value in values['keywords']
                                  if keywords_master_list.count(value[0]) <= max(len(result_dict)*.35, 1)]
            values['keywords'] = [val[0] for val in values['keywords']][-min(3, len(values['keywords'])):]

            values['title_keywords'] = [value for value in values['title_keywords']
                                  if title_keywords_master_list.count(value[0]) <= max(len(result_dict)*.35, 1)]
            values['title_keywords'] = [val[0] for val in values['title_keywords']][-min(3, len(values['title_keywords'])):]
            values['cluster_title'] = values['articles'][cluster_center[cluster]]

            result_dict[cluster] = values

        self.write(json.dumps(result_dict))


class RSSHandler(tornado.web.RequestHandler):
    def post(self):
        """
        # NEEDS TO BE REFACTORED + ERROR HANDLING
        Steps:
            - Pull down RSS feed links
            - Scrape links for text content
            - Augment with indico API
            - Save to database
        """
        data = json.loads(self.request.body)
        group = data.get('group')
        url = data.get("url")

        try:
            feed = feedparser.parse(url, request_headers=REQUEST_HEADERS)
        except Exception:
            return json.dumps({
                'error': 'Invalid rss feed'
            })

        try:
            links = [entry['link'] for entry in feed['entries']]
            titles = [entry['title'] for entry in feed['entries']]
        except Exception:
            return json.dumps({
                'error': "RSS feed at %s missing standard field 'title' and/or 'link'." % url
            })

        text = map(_read_text_from_url, links)
        objs = zip(links, titles, text)
        objs = filter(lambda obj: obj[2].strip() != "", objs)
        text = [item[2] for item in objs] # no longer contains empty strings
        if not text:
            return self.write(json.dumps({
                'error': 'No links successfully parsed from rss feed %s.' % url
            }))

        FULL_FIELD_LIST = [
            'text_features',
            'people',
            'places',
            'organizations',
            'keywords',
            'title_keywords',
            'sentiment'
        ]

        indico = {}
        for field in FULL_FIELD_LIST:
            indico[field] = []

        for batch in batched(text, 20):
            try:
                APIS = ['text_features', 'people', 'places', 'organizations']
                indico_results = indicoio.analyze_text(
                    batch,
                    apis=APIS
                )
                for API in APIS:
                    indico[API].extend(indico_results[API])
                indico['keywords'].extend(indicoio.keywords(batch, version=2, top_n=3))
                indico['title_keywords'].extend(indicoio.keywords(batch, version=2, top_n=3))
                indico['sentiment'].extend(indicoio.sentiment(batch))
            except Exception as e:
                import traceback
                traceback.print_exc()
                print "An error occurred while retrieving results from the indico API."

        remapped_results = zip(*[indico[field] for field in FULL_FIELD_LIST])
        formatted_results = [
            dict(zip(FULL_FIELD_LIST, result)) for result in remapped_results
        ]

        session = DBSession()

        for metadata, indico_metadata in zip(objs, formatted_results):
            # save to database
            link, title, text = metadata
            already_exists = session.query(Entry).filter(Entry.link==link).first()
            if not already_exists:
                entry = Entry(
                    text=text,
                    title=title,
                    link=link,
                    indico=indico_metadata,
                    group=group,
                    rss_feed=url
                )
                session.add(entry)

        session.commit()
        session.close()
        self.write(json.dumps(links))


# NOTE: nginx will be routing /text-mining requests to this app. For example, posts in javascript
#       need to specify /text-mining/query, not /query
application = tornado.web.Application(
    [(r"/text-mining", MainHandler), (r"/text-mining/add-rss-feed", RSSHandler), (r"/text-mining/query", QueryHandler)],
    template_path=abspath(os.path.join(__file__, "../../templates")),
    static_url_prefix="/text-mining/static/",
    static_path=abspath(os.path.join(__file__, "../../static")),
    cookie_secret="verytemporarycookiesecret",
    debug=DEBUG
)

if __name__ == "__main__":
    application.listen(8003)
    tornado.ioloop.IOLoop.current().start()
