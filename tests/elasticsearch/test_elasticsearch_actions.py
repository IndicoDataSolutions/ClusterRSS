import os, unittest, datetime
from copy import deepcopy

import cluster
from cluster.search.schema import Document
from cluster.search.client import ESConnection

SCRIPTS_EXEC = os.path.abspath(
    os.path.join(
        os.path.dirname(cluster.__file__),
        "..",
        "scripts",
        "run_elasticsearch_host.sh"
    )
)

INDEX="testing-index"
DOCUMENT = Document(
    title="sample title abcd",
    text="sample text abcd",
    date=datetime.datetime.now()
)
HOST="localhost:9200"

class TestLoadData(unittest.TestCase):
    def setUp(self):
        self.es = ESConnection(HOST, index=INDEX)

    def test_upload_document(self):
        successes, errors = self.es.upload([DOCUMENT])
        self.assertEqual(successes, 1)
        self.assertFalse(errors)

    def test_search_document(self):
        self.es.upload([DOCUMENT])
        self.es.flush()
        results = self.es.search("sample")
        self.assertEqual(len(results), 1)

    def test_tags_as_list(self):
        document = Document(
            title="title",
            text="text",
            tags=["tag1", "tag2"],
            link="google.com",
            date=datetime.datetime.now()
        )
        successes, errors = self.es.upload([document])
        self.assertEqual(successes, 1)
        self.es.flush()

        results = self.es.search("title")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tags"], ["tag1", "tag2"])

    def test_date_range(self):
        old_document = Document(
            title="old",
            text="embarassingly old subject matter",
            tags=["old", "older"],
            link="google.com",
            date=datetime.datetime(1990, 1, 1)
        )
        successes, errors = self.es.upload([old_document])
        self.assertEqual(successes, 1)
        self.es.flush()

        results = self.es.search('old', start_date=datetime.datetime(2015, 1, 1))
        self.assertEqual(len(results), 0)

    def test_source(self):
        well_sourced_doc, poorly_sourced_doc = [deepcopy(DOCUMENT), deepcopy(DOCUMENT)]
        well_sourced_doc.update({'source': 'good'})
        poorly_sourced_doc.update({'source': 'bad'})

        successes, errors = self.es.upload([well_sourced_doc, poorly_sourced_doc])
        self.assertEqual(successes, 2)
        self.es.flush()

        results = self.es.search('title', source="good")
        self.assertEqual(len(results), 1)

    def tearDown(self):
        self.es.delete()
