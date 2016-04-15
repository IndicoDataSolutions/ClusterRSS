import os, re, json
import pickle

import indicoio
from tqdm import tqdm
from picklable_itertools.extras import partition_all
from concurrent.futures import ThreadPoolExecutor

from .client import ESConnection
from .schema import Document, INDEX

EXECUTOR = ThreadPoolExecutor(max_workers=4)

def parse_obj_to_document(obj):
    text = obj.get("content")
    title = obj.get("title")
    link = obj.get("link")
    tags = obj.get("symbols")

    # Remove CSS & HTML residue
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"[\s]+", " ", text)
    text = re.sub(r"[[\w\-]*\s*[\.[\w\-]*\s*]*]*\s*{[^}]*}", "", text)

    return Document(
        title=title,
        text=text.encode("ascii", "ignore"),
        link=link,
        tags=tags
    )

def add_indico(documents):
    text = [document["text"] for document in documents]
    title = [document["title"] for document in documents]

    try:
        sentiment = EXECUTOR.submit(indicoio.sentiment_hq, text)
        keywords_text = EXECUTOR.submit(indicoio.keywords, text)
        keywords_title = EXECUTOR.submit(indicoio.keywords, title)
        text_features = EXECUTOR.submit(indicoio.text_features, text)
        title_features = EXECUTOR.submit(indicoio.text_features, title)
        people_text = EXECUTOR.submit(indicoio.people, title)
        organizations_text = EXECUTOR.submit(indicoio.organizations, title)
        places_text = EXECUTOR.submit(indicoio.places, title)
    except:
        import traceback; traceback.print_exc()

    sentiment = sentiment.result()
    keywords_text = keywords_text.result()
    keywords_title = keywords_title.result()
    text_features = text_features.result()
    title_features = title_features.result()
    people_text = people_text.result()
    organizations_text = organizations_text.result()
    places_text = places_text.result()

    for i in xrange(len(text)):
        documents[i]["indico"]["sentiment"] = sentiment[i]
        documents[i]["indico"]["keywords"] = keywords_text[i]
        documents[i]["indico"]["title_keywords"] = keywords_title[i]
        documents[i]["indico"]["text_features"] = text_features[i]
        documents[i]["indico"]["title_features"] = title_features[i]
        documents[i]["indico"]["people"] = people_text[i]
        documents[i]["indico"]["organizations"] = organizations_text[i]
        documents[i]["indico"]["places"] = places_text[i]

    return documents

def upload_data(es, data_file):
    executor = ThreadPoolExecutor(max_workers=4)
    documents = []
    with open(data_file, 'rb') as f:
        lines = f.readlines()

    for documents in tqdm(partition_all(20, lines)):
        documents = map(lambda x: parse_obj_to_document(json.loads(x)), documents)
        documents = filter(lambda doc: doc.link and "Service Unavailable" not in doc.text, documents)

        future = executor.submit(add_indico, documents)
        es.upload(future.result())

if __name__ == "__main__":
    DATA_FILE = os.path.join(
        os.path.dirname(__file__),"data", "stocks_news.ndjson.txt"
    )
    es = ESConnection("localhost:9200", index=INDEX)
    upload_data(es, DATA_FILE)
