# -*- coding: utf-8 -*-
"""
    onboarder
    ~~~~~~~~
    app.views (app)

"""

import json
from time import time
import math
import traceback
import os
from os.path import abspath, dirname
from operator import itemgetter
from random import randint

import tornado.ioloop
import tornado.web
import requests
import feedparser
from newspaper import Article
from newspaper.configuration import Configuration

from gevent.pool import Pool
from scipy import spatial
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from indicluster.models import Entry, Base

import indicoio
indicoio.config.api_key = os.getenv('INDICO_API_KEY')

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


def _read_text_from_url(url):
    try:
        article = Article(url, config=NEWSPAPER_CONFIG)
        html = requests.get(url, headers=HEADERS, cookies=REQUEST_HEADERS).text
        article.set_html(html)
        article.parse()
        assert article.text
        return article.text
    except Exception:
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
        self.render('text-mining.html')

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
        session = DBSession()
        data = json.loads(self.request.body)
        group = data.get('group')
        query = data.get('query')
        query_text_features = indicoio.text_features(query)

        entries_with_dups = session.query(Entry).filter_by(group=group).all()
        print "Number of entries (with duplicates): %d" % len(entries_with_dups)
        entries = []
        entry_links = []
        for entry in entries_with_dups:
            if not entry.link in entry_links and not 'Service Unavailable' in entry.text:
                entry_links.append(entry.link)
                entries.append(entry)

        entry_dicts = [{'text': entry.text,
                       'title': entry.title,
                       'link': entry.link,
                       'indico': json.loads(entry.indico),
                       'distance': spatial.distance.cosine(json.loads(entry.indico)['text_features'], query_text_features)}
                      for entry in entries]

        print "Number of entries (without duplicates): %d" % len(entry_dicts)

        sorted_entry_dicts = sorted(entry_dicts, key=lambda k: k['distance'])
        features_matrix = [entry['indico']['text_features'] for entry in sorted_entry_dicts]

        tsne_model = TSNE()
        new_feats = tsne_model.fit_transform(features_matrix)

        kmeans = KMeans(n_clusters=8, n_init=20)
        # kmeans = kmeans.fit(features_matrix)
        # relevant_feats = features_matrix[:50]
        # top_entry_dicts = entry_dicts[:50]
        kmeans.fit(new_feats)
        if len(new_feats > 50):
            relevant_feats = new_feats[-50:]
            top_entry_dicts = entry_dicts[-50:]
        else:
            relevant_feats = new_feats
            top_entry_dicts = top_entry_dicts
        clusters = kmeans.predict(relevant_feats)

        sorted_entry_dicts  = [dict(entry, cluster=str(cluster)) for entry, cluster in zip(top_entry_dicts, clusters)]
        self.write(json.dumps([update_article(article) for article in sorted_entry_dicts]))


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
        print "Processing %s: %s" % (group, url)
        
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
                'error': "rss feed missing standard field 'title' and/or 'link'"
            })

        text = POOL.map(_read_text_from_url, links)
        objs = zip(links, titles, text)
        # obj[2] --> text
        objs = filter(lambda obj: obj[2].strip() != "", objs)
        text = [item[2] for item in objs] # no longer contains empty strings
        indico = indicoio.analyze_text(
            text,
            apis=['text_features', 'people', 'places', 'organizations']
        )
        keywords = indicoio.keywords(text, version=2, top_n=3)
        remapped_results = zip(
            indico['text_features'],
            indico['people'],
            indico['places'],
            indico['organizations'],
            keywords
        )
        formatted_results = [
            dict(zip(
                ['text_features', 'people', 'places', 'organizations', 'keywords'],
                result
            )) for result in remapped_results
        ]

        session = DBSession()

        for metadata, indico_metadata in zip(objs, formatted_results):
            # save to database
            link, title, text = metadata
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
    static_path=abspath(os.path.join(__file__, "../../static")),
    cookie_secret="verytemporarycookiesecret",
    debug=False
)

if __name__ == "__main__":
    application.listen(8002)
    tornado.ioloop.IOLoop.current().start()
