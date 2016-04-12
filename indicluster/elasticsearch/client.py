import logging

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from schema import INDEX

# Logging configuration?
es_logger = logging.getLogger('elasticsearch')
es_logger.propagate = False
es_logger.setLevel(logging.INFO)

class ESConnection(object):
    """Creates an Elasticsearch connection to the dedicated master hosts

    Arguments:
    hosts -- a list of strings of host addresses domain:port
    index (defaulted) -- "table" of the elasticsearch to use
    Keyword Arugments:
    http://elasticsearch-py.readthedocs.org/en/master/api.html?highlight=types#elasticsearch

    Returns an ESConnection object
    """
    def __init__(self, hosts, index=INDEX, **kwargs):
        self.index = index
        self.es = Elasticsearch(hosts=hosts, **kwargs)

    def upload(self, documents):
        """Loads a document object into the Elasticsearch database

        Arguments:
        es -- ElasticSearch object from the `elasticsearch` library
        document -- self object containing the document data as defined in schemas

        Returns the result of loading data into Elasticsearch
        """
        # Assign the indices for the bulk call
        for doc in documents:
            doc["_index"] = self.index
        return bulk(self.es, documents)

    def search(self, query, size=100, only_documents=True):
        """Performs a query on the Elasticsearch connection
        https://www.elastic.co/guide/en/elasticsearch/reference/current/full-text-queries.html

        Returns a dict that looks like:
        {
            u'hits': {
                u'hits':[
                    {
                        u'_score': 0.16273327,
                        u'_type': u'document',
                        u'_id': u'sH5-CYXFQ8GEqJXI7tPqdg',
                        u'_source': {
                            u'text': u'sample text abcd',
                            u'title': u'sample title abcd',
                            u'tags': []
                        },
                        u'_index':
                        u'indico-text-data'
                    }
                ],
                u'total': 0,
                u'max_score': None
            },
            u'_shards': {
                u'successful': 5,
                u'failed': 0,
                u'total': 5
            },
            u'took': 26,
            u'timed_out': False
        }
        """
        results = self.es.search(index=self.index, q=query, size=size)
        if only_documents:
            return self._format_search(results)
        return results

    def delete_by_ids(self, ids, _type):
        """Deletes a document by id
        """
        return bulk(self.es, [{
            "_op_type": "delete",
            "_index": self.index,
            "_type": _type,
            "_id": _id
        } for _id in ids])

    def delete(self):
        """Removes all the documents in this index
        """
        return self.es.indices.delete(self.index)

    def flush(self):
        """Flushes operations to the host for changes
        """
        return self.es.indices.refresh(self.index)

    def _format_search(self, search_result):
        """Pulls out just the found documents"""
        return map(lambda doc: doc["_source"], search_result["hits"]["hits"])
