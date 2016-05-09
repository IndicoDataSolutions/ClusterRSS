import os, re, json
import time
from copy import deepcopy

import indicoio
from tqdm import tqdm
from picklable_itertools.extras import partition_all
import concurrent.futures

from .client import ESConnection
from .schema import Document, INDEX
from .summary import Summary

EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
ENGLISH_SUMMARIZER = Summary(language="english")

def parse_obj_to_document(obj):
    text = obj.get("content")
    title = obj.get("title")
    link = obj.get("link")
    tags = obj.get("symbols")

    # Remove CSS & HTML residue
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"[\s]+", " ", text)
    text = re.sub(r"[[\w\-]*\s*[\.[\w\-]*\s*]*]*\s*{[^}]*}", "", text)
    text = text.encode("ascii", "ignore").decode("ascii", "ignore")

    return Document(
        title=title,
        text=text,
        link=link,
        tags=tags,
        length=len(text),
        summary=ENGLISH_SUMMARIZER.parse(text, sentences=3)
    )

def add_indico(documents, filename):
    new_documents = []
    for i, document in enumerate(documents):
        new_doc = deepcopy(document)
        text = new_doc["text"]
        title = new_doc["title"]
        print i, filename, title
        try:
            # text_analysis = indicoio.analyze_text([text, title], apis=[
            #     "sentiment_hq",
            #     "keywords",
            # ])
            # new_doc["indico"]["sentiment"] = text_analysis.get('sentiment_hq')[0]
            # new_doc["indico"]["keywords"] = text_analysis.get('keywords')[0]
            # new_doc["indico"]["title_sentiment"] = text_analysis.get('sentiment_hq')[1]
            # new_doc["indico"]["title_keywords"] = text_analysis.get('keywords')[1]
            
            # new_doc["indico"]["text_features"] = indicoio.text_features(text)
            # new_doc["indico"]["title_text_features"] = indicoio.text_features(title)
            
            new_doc["indico"]["title_people"] = new_doc["indico"]["people"]
            new_doc["indico"]["title_places"] = new_doc["indico"]["places"]
            new_doc["indico"]["title_organizations"] = new_doc["indico"]["organizations"]

            new_doc["indico"]["people"] = indicoio.people(text)
            new_doc["indico"]["places"] = indicoio.places(text)
            new_doc["indico"]["organizations"] = indicoio.organizations(text)

            new_documents.append(new_doc)
            new_doc = {}
        except:
            import traceback; traceback.print_exc()
            return False

    return new_documents

def upload_data(data_dir, filename):
    t0 = time.time()

    documents = []
    data_file = os.path.join(data_dir, filename)
    with open(data_file, 'rb') as f:
        documents = [json.loads(l) for l in f.readlines()]

    # print len(lines)
    # documents = map(lambda x: parse_obj_to_document(json.loads(x)), lines)
    # documents = filter(lambda doc: doc.link and "Service Unavailable" not in doc.text, documents)
    
    clean_documents = add_indico(documents, filename)
    
    data_dir = os.path.join(os.path.dirname(__file__), '../../entities/')
    if clean_documents:
        print "about to write", len(clean_documents), "documents to", data_dir
        with open(data_dir+filename, 'w') as data_dump:
            for document in clean_documents:
                data_dump.write(json.dumps(document)+'\n')

    print 'done - total time:', time.time() - t0
    return True
            

if __name__ == "__main__":
    es = ESConnection("localhost:9200", index=INDEX)
    DATA_FILE = os.path.join(os.path.dirname(__file__), '../quickie.ndjson')
    upload_data(es, DATA_FILE)
