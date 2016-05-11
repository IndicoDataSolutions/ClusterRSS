import os, re, json
import time
from copy import deepcopy
import datetime

import indicoio
from tqdm import tqdm
from picklable_itertools.extras import partition_all
import concurrent.futures
import pyexcel as pe
import pyexcel.ext.xlsx
from dateutil.parser import parse as date_parse

from .client import ESConnection
from .schema import Document, INDEX
from .summary import Summary

EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
ENGLISH_SUMMARIZER = Summary(language="english")
now = datetime.datetime.now()
ONE_YEAR_AGO = now.replace(year = now.year - 1)
with open('cluster/search/sp500.txt') as f:
    SP_TICKERS = f.read().splitlines()

def parse_obj_to_document(obj):
    text = obj.get("description_text")
    title = obj.get("name_post", obj.get("name_story"))
    link = obj.get("url_post", obj.get("url_story"))
    tags = [obj.get("name_categorie", obj.get("name_topics"))]
    pub_date = obj.get("date_published", obj.get("date_published_story"))

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
        date=pub_date,
        summary=ENGLISH_SUMMARIZER.parse(text, sentences=3)
    )


def not_in_sp500(document):
    in_text = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["text"]) for ticker in SP_TICKERS])
    in_title = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["title"]) for ticker in SP_TICKERS])
    return not(in_text or in_title)


def not_relevant_and_recent(document):
    if not document["text"] or not document["title"]:
        print 'lacking content'
        return True
    pub_date = date_parse(document.get("date"))
    if pub_date < ONE_YEAR_AGO and not_in_sp500(document):
        print 'not relevant or recent'
        return True
    return False


def add_indico(documents, filename):
    new_documents = []
    for i, document in tqdm(enumerate(documents)):
        new_doc = deepcopy(document)
        text = new_doc.get("text")
        title = new_doc.get("title")
        new_doc["indico"] = {}
        if not_relevant_and_recent(new_doc):
            continue
        print i, filename, title
        try:
            text_analysis = indicoio.analyze_text([text, title], apis=[
                "sentiment_hq",
                "keywords",
                "people",
                "places",
                "organizations",
                "text_features"
            ])

            new_doc["indico"]["title_sentiment"] = text_analysis.get('sentiment_hq')[1]
            new_doc["indico"]["title_keywords"] = text_analysis.get('keywords')[1]
            new_doc["indico"]["title_people"] = text_analysis.get('people')[1]
            new_doc["indico"]["title_places"] = text_analysis.get('places')[1]
            new_doc["indico"]["title_organizations"] = text_analysis.get('organizations')[1]
            new_doc["indico"]["title_text_features"] = text_analysis.get('text_features')[1]


            new_doc["indico"]["sentiment"] = text_analysis.get('sentiment_hq')[0]
            new_doc["indico"]["keywords"] = text_analysis.get('keywords')[0]
            new_doc["indico"]["people"] = text_analysis.get('people')[0]
            new_doc["indico"]["places"] = text_analysis.get('places')[0]
            new_doc["indico"]["organizations"] = text_analysis.get('organizations')[0]
            new_doc["indico"]["text_features"] = text_analysis.get('text_features')[0]


            new_documents.append(new_doc)
            new_doc = {}
        except:
            import traceback; traceback.print_exc()
            return False

    return new_documents

def upload_data(es, current_dir):
    t0 = time.time()

    documents = []
    for subdir, dirs, files in os.walk(current_dir):
        for filename in files:
            data_file = os.path.join(current_dir, filename)
            print data_file
            lines = [line for line in pe.get_records(file_name=data_file) if line.get("description_text") and len(line.get("description_text")) > 600][:10]
            print len(lines)


            documents = map(lambda x: parse_obj_to_document(x), lines)
            documents = filter(lambda doc: doc.link and "Service Unavailable" not in doc.text, documents)
            print 'raw docs'

            clean_documents = add_indico(documents, filename)
            print "added_indico"


            data_dir = os.path.join(os.path.dirname(__file__), '../../backups/')
            if clean_documents:
                print "about to write", len(clean_documents), "documents to", data_dir
                with open(data_dir+filename, 'w') as data_dump:
                    for document in clean_documents:
                        data_dump.write(json.dumps(document)+'\n')

            print "written"
            es.upload(clean_documents)

            print 'done - total time:', time.time() - t0
            return True


if __name__ == "__main__":
    es = ESConnection("localhost:9200", index=INDEX)
    DATA_FILE = os.path.join(os.path.dirname(__file__), '../../inputxl')
    upload_data(es, DATA_FILE)
