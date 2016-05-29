import json, os, logging
import requests
import datetime

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import indicoio
from indicoio.custom import Collection
from picklable_itertools.extras import partition_all

from client import ESConnection

indicoio.config.cloud = 'themeextraction'
indicoio.config.api_key=os.getenv("CUSTOM_INDICO_API_KEY")

EXECUTOR_SPLITTEXT = ThreadPoolExecutor(max_workers=8)
EXECUTOR_CUSTOM = ThreadPoolExecutor(max_workers=8)
HEADERS = {
    "X-ApiKey": indicoio.config.api_key
}

growth_collection = Collection("Growth-v3", domain="finance")

# Logging
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Logging
root = logging.getLogger("elasticsearch.update")
root.setLevel(logging.INFO)
fileHandler = logging.FileHandler("output.log")
fileHandler.setLevel(logging.DEBUG)
root.addHandler(fileHandler)

LOG_LIMIT = 160

def splittext(documents):
    result = json.loads(requests.post(
        "https://themeextraction.indico.domains/splittext/batch",
        headers=HEADERS,
        data=json.dumps({
            "data": [doc["_source"]["text"] for doc in documents]
        }), verify=False).text)
    return documents, result.get("results")

def growth(document):
    results = growth_collection.predict(document["_source"]["sentences"], domain="finance")
    document["_source"]["growth"] = results
    return document

def add_splittext(docs):
    split_futures = {}
    root.info("Begin splittext on {0} documents".format(len(docs)))
    for documents in partition_all(20, docs):
        split_futures[EXECUTOR_SPLITTEXT.submit(splittext, documents)] = 0

    result_documents = []

    for future in concurrent.futures.as_completed(split_futures):
        documents, sentences = future.result()
        root.info("Sample of first splittext document in batch with {0}".format(sentences[0])[:LOG_LIMIT] + "...")
        for idx in xrange(len(documents)):
            documents[idx]["_source"]["sentences"] = [sent["text"] for sent in sentences[idx]]
        result_documents += documents
    return result_documents

def add_custom_growth(docs):
    custom_futures = {}
    root.info("Begin Growth on {0} documents".format(len(docs)))
    for document in docs:
        custom_futures[EXECUTOR_CUSTOM.submit(growth, document)] = 0

    result_documents = []
    for future in concurrent.futures.as_completed(custom_futures):
        document = future.result()
        root.info("Sample of document completed {0}".format(document["_source"]["growth"][:5])[:LOG_LIMIT] + "...")
        result_documents.append(document)
        del custom_futures[future]
    return result_documents

def change_date(docs):
    for doc in docs:
        doc["_source"]["date"] = datetime.datetime.fromtimestamp(int(doc["_source"].get("date", "0")))
    return docs
    
if __name__ == "__main__":
    es = ESConnection("localhost:9200")
    # es.update("*", "20m", add_splittext, window=5000)
    # es.update("*", "20m", add_custom_growth, window=5000)
    es.update("*", "2m", change_date, window=5000)
