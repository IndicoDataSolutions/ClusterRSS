import unittest, os, os.path, sys, urllib, datetime, json
from copy import deepcopy

import cluster
from cluster.search.schema import Document
from cluster.search.client import ESConnection

import logging
LOGGER = logging.getLogger()
LOGGER.level = logging.DEBUG
stream_handler = logging.StreamHandler(sys.stdout)
LOGGER.addHandler(stream_handler)

# Will probably need this at some point (right now you need to be running ES to test)
# SCRIPTS_EXEC = os.path.abspath(
#     os.path.join(
#         os.path.dirname(cluster.__file__),
#         "..",
#         "scripts",
#         "run_elasticsearch_host.sh"
#     )
# )

INDEX="indico-cluster-date"
HOST="localhost:9200"

import tornado.web
from tornado.options import options
import tornado.testing

# add application root to sys.path
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(APP_ROOT, '..'))

# import your app module
from cluster.app import make_app

class NewTestCase(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        return make_app()

    def query(self, query_data):
        return json.loads(self.fetch(
            '/text-mining/query',
            method='POST',
            body=json.dumps(query_data)
        ).body)

    def test_basic_query(self):
        cluster_res = self.query({'query': 'Samsung'})
        # Assert 10 clusters returned
        self.assertEqual(len(cluster_res.keys()), 10)

    def test_article_limit(self):
        cluster_res_default = self.query({'query': 'Samsung', 'limit': '500'}) # default limit is 500
        cluster_res_limited = self.query({'query': 'Samsung', 'limit': '100'})
        self.assertTrue(len(cluster_res_default.keys()) > len(cluster_res_limited.keys()))

    def test_source_filter(self):
        cluster_res = self.query({'query': 'Samsung', 'source': 'thestreet'})
        # The Street only returns 1 cluster worth of articles on Samsung
        self.assertEqual(len(cluster_res.keys()), 1)

    def test_date_filter(self):
        cluster_res = self.query({'query': 'Apple', 'start': '2000', 'end': '2005'})
        # Not too many early articles for Apple
        self.assertEqual(len(cluster_res.keys()), 4)

    def test_threshold_filter(self):
        cluster_res_default = self.query({'query': 'Samsung', 'threshold': '0.3'})
        cluster_res_conservative = self.query({'query': 'Samsung', 'threshold': '0.5'})
        self.assertTrue(len(cluster_res_default.keys()) > len(cluster_res_conservative.keys()))

    def test_cluster_article_min(self):
        cluster_res_default = self.query({'query': 'Samsung', 'min-samples': '3'})
        cluster_res_liberal = self.query({'query': 'Samsung', 'min-samples': '2'})
        # If you need less articles to create a cluster you should have more clusters
        self.assertTrue(len(cluster_res_default.keys()) < len(cluster_res_liberal.keys()))
