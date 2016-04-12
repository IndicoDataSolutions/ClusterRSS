import os, unittest
import urllib3
from subprocess import Popen

import indicluster
import requests
from indicluster.elasticsearch.schema import Document
from indicluster.elasticsearch.client import ESConnection

SCRIPTS_EXEC = os.path.abspath(
    os.path.join(
        os.path.dirname(indicluster.__file__),
        "..",
        "scripts",
        "run_elasticsearch_host.sh"
    )
)

INDEX="testing-index"
DOCUMENT = Document(
    title="sample title abcd",
    text="sample text abcd"
)
HOST="localhost:9200"

class TestLoadData(unittest.TestCase):
    def test_upload_document(self):
        es = ESConnection(hosts=[HOST], index=INDEX)
        successes, errors = es.upload([DOCUMENT])
        self.assertEqual(successes, 1)
        self.assertFalse(errors)

    def test_search_document(self):
        es = ESConnection(hosts=[HOST], index=INDEX)
        es.upload([DOCUMENT])
        es.flush()
        results = es.search("sample")
        self.assertEqual(len(results), 1)
    
    def test_tags_as_list(self):
        es = ESConnection(hosts=[HOST], index=INDEX)
        document = Document(
            title="title",
            text="text",
            tags=["tag1", "tag2"],
            link="google.com"
        )
        successes, errors = es.upload([document])
        self.assertEqual(successes, 1)
        es.flush()

        results = es.search("title")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["tags"], ["tag1", "tag2"])

    def tearDown(self):
        es = ESConnection(hosts=[HOST], index=INDEX)
        es.delete()
