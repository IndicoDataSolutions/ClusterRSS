import os, re, json
import pickle

from tqdm import tqdm
from picklable_itertools.extras import partition_all

from .client import ESConnection
from .schema import Document, INDEX

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
        text=text.decode("ascii", "ignore"),
        link=link,
        tags=tags
    )

def upload_data(es, data_file):
    documents = []
    with open(data_file, 'rb') as f:
        for line in tqdm(f):
            documents.append(
                parse_obj_to_document(
                    json.loads(line)
                )
            )

    for documents in partition_all(200, documents):
        es.upload(documents)

if __name__ == "__main__":
    DATA_FILE = os.path.join(
        os.path.dirname(__file__),"data", "stocks_news.ndjson.txt"
    )
    es = ESConnection(hosts=["localhost:9200"], index=INDEX)
    upload_data(es, DATA_FILE)
