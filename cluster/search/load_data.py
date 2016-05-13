import os, re, json
import time
from copy import deepcopy
import datetime
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

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

indicoio.config.cloud = 'themeextraction'
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
        indico={},
        summary=ENGLISH_SUMMARIZER.parse(text, sentences=3)
    )


def not_in_sp500(document):
    in_text = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["text"]) for ticker in SP_TICKERS])
    in_title = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["title"]) for ticker in SP_TICKERS])
    return not(in_text or in_title)


def not_relevant_and_recent(document):
    if not document["text"] or not document["title"]:
        return True
    pub_date = date_parse(document.get("date"))
    if pub_date < ONE_YEAR_AGO and not_in_sp500(document):
        return True
    return False


def add_indico(documents):
    print 'add indico'
    before_documents = [deepcopy(document) for document in documents]
    new_documents = []
    for documents_sub_list in [before_documents[x:x+50] for x in xrange(0, len(before_documents), 50)]:
        documents_sub_list = [doc for doc in documents_sub_list if not not_relevant_and_recent(doc)]
        try:
            text_analysis = {}
            text_analysis["sentiment_hq"] = indicoio.sentiment_hq([doc.get("title") for doc in documents_sub_list])
            text_analysis["keywords"] = indicoio.keywords([doc.get("title") for doc in documents_sub_list], version=1)
            ner = indicoio.named_entities([doc.get("title") for doc in documents_sub_list], version=2)
            text_analysis["people"] = ner["people"]
            text_analysis["places"] = ner["places"]
            text_analysis["organizations"] = ner["organizations"]

            for i in range(len(documents_sub_list)):
                documents_sub_list[i]["indico"] = {}
                documents_sub_list[i]["indico"]["title_sentiment"] = text_analysis.get('sentiment_hq')[i]
                documents_sub_list[i]["indico"]["title_keywords"] = text_analysis.get('keywords')[i]
                documents_sub_list[i]["indico"]["title_people"] = text_analysis.get('people')[i]
                documents_sub_list[i]["indico"]["title_places"] = text_analysis.get('places')[i]
                documents_sub_list[i]["indico"]["title_organizations"] = text_analysis.get('organizations')[i]

            text_analysis = {}
            text_analysis["sentiment_hq"] = indicoio.sentiment_hq([doc.get("text") for doc in documents_sub_list])
            text_analysis["keywords"] = indicoio.keywords([doc.get("text") for doc in documents_sub_list], version=1)
            ner = indicoio.named_entities([doc.get("text") for doc in documents_sub_list], version=2)
            text_analysis["people"] = ner["people"]
            text_analysis["places"] = ner["places"]
            text_analysis["organizations"] = ner["organizations"]

            for i in range(len(documents_sub_list)):
                documents_sub_list[i]["indico"]["sentiment"] = text_analysis.get('sentiment_hq')[i]
                documents_sub_list[i]["indico"]["keywords"] = text_analysis.get('keywords')[i]
                documents_sub_list[i]["indico"]["people"] = text_analysis.get('people')[i]
                documents_sub_list[i]["indico"]["places"] = text_analysis.get('places')[i]
                documents_sub_list[i]["indico"]["organizations"] = text_analysis.get('organizations')[i]


            new_documents.extend(documents_sub_list)
        except:
            import traceback; traceback.print_exc()
            return False

    return new_documents


def upload_data(es, current_dir):
    t0 = time.time()
    executor = ThreadPoolExecutor(max_workers=4)
    all_files = []
    for subdir, dirs, files in os.walk(current_dir):
        for filename in files:
            all_files.append(os.path.join(current_dir, filename))


    def worker(files):
        def sub_problem(data_file):
            try:
                print data_file
                lines = [line for line in pe.get_records(file_name=data_file) if line.get("description_text") and len(line.get("description_text")) > 600]
                print len(lines)


                documents = map(lambda x: parse_obj_to_document(x), lines)
                documents = filter(lambda doc: doc.link and "Service Unavailable" not in doc.text, documents)
                print 'raw docs'
                return add_indico(documents)
            except:
                print 'error in:'
                print data_file
                import traceback; traceback.print_exc()
                return []

        futures = {executor.submit(sub_problem, data_file): data_file for data_file in files}
        data_dir = os.path.join(os.path.dirname(__file__), '../../backups/')
        for future in concurrent.futures.as_completed(futures):
            # clean_documents = futures[future]
            try:

                print "written"
                try:
                    es.upload(future.result())
                except:
                    import traceback; traceback.print_exc()
            except:
                import traceback; traceback.print_exc()

            print 'done - total time:', time.time() - t0

    for some_files in [all_files[i::4] for i in xrange(4)]:
        p = multiprocessing.Process(target=worker, args=(some_files,))
        p.start()
        print 'started job'


if __name__ == "__main__":
    es = ESConnection("localhost:9200", index=INDEX)
    DATA_FILE = os.path.join(os.path.dirname(__file__), '../../inputxl')
    upload_data(es, DATA_FILE)
