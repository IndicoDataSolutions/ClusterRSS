import os, re, sys, json
import datetime, logging
from multiprocessing import Pool
import time

from picklable_itertools.extras import partition_all
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from dateutil.parser import parse as date_parse
from urlparse import urlparse

from pyexcel_xlsx import get_data
import indicoio
from indicoapi.ML.custom.utils.finance.model import FinanceEmbeddingModel

from .client import ESConnection
from .schema import Document
from .summary import Summary
from .words import cross_reference

# Turn down requests log verbosity
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Processing
ENGLISH_SUMMARIZER = Summary(language="english")
NOW = datetime.datetime.now()
ONE_YEAR_AGO = NOW.replace(year = NOW.year - 1).strftime("%s")
DESCRIPTION_THRESHOLD = 600
NUM_PROCESSES= int(sys.argv[1])
COMPLETED_PATH = os.path.join(os.path.dirname(__file__), '../../completed.txt')
FINANCE_EMBEDDING = FinanceEmbeddingModel()

# Logging
root = logging.getLogger("elasticsearch.load_data")
root.setLevel(logging.INFO)
fileHandler = logging.FileHandler("output.log")
fileHandler.setLevel(logging.DEBUG)
root.addHandler(fileHandler)

errorLogger = logging.getLogger("error")
fileHandler = logging.FileHandler("error.log")
fileHandler.setLevel(logging.INFO)
errorLogger.addHandler(fileHandler)

# Indico
indicoio.config.cloud = 'themeextraction'

SP_TICKERS = open(os.path.join(
    os.path.dirname(__file__), "data", "sp500.txt"
)).readlines()
FINANCIAL_WORDS = set(json.loads(open(os.path.join(
    os.path.dirname(__file__), "data", "financial_keywords.json"
)).read()))

SP500_REGEX = [re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]') for ticker in SP_TICKERS]

es = ESConnection("localhost:9200", index="reviews")

FIELD_MAPPING = {
    "name_post": "title",
    "name_story": "title",
    "name": "title",
    "url_post": "link",
    "url_story": "link",
    "url_book": "link",
    "url_doctors": "link",
    "url": "link",
    "name_categorie": "tags",
    "name_topics": "tags",
    "description_text": "text",
    "description": "text",
    "date_e_post": "date",
    "date_published": "date",
    "date_published_story": "date",
    "name_colleges": "school_name",
    "state": "location",
    "destinations": "location"
}

def _in_sp500(document):
    return any(map(lambda x: x.search(document["text"]), SP500_REGEX)) or \
           any(map(lambda x: x.search(document["title"]), SP500_REGEX))

def _relevant_and_recent(document):
    if not document.link or "Service Unavailable" in document.text:
        return False
    if not document.get("text"):
        return False
    if _in_sp500(document):
        return True
    if document.get("date", "") == "":
        return True
    if document.get("date") < ONE_YEAR_AGO:
        return False
    return True

def parse_obj_to_document(obj):
    for key in FIELD_MAPPING:
        if key in obj:
            obj[FIELD_MAPPING[key]] = obj.pop(key)

    text = obj.get("text")
    link = obj.get("link")

    if not text or not isinstance(text, basestring):
        root.debug("Text field was not found in document with fields: {0}".format(obj.keys()))
        return

    if text.endswith("This is an automated posting."):
        root.debug("Automated posting found.")
        return

    # Remove CSS & HTML residue
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"[\s]+", " ", text)
    text = re.sub(r"[[\w\-]*\s*[\.[\w\-]*\s*]*]*\s*{[^}]*}", "", text)
    text = text.encode("ascii", "ignore").decode("ascii", "ignore")

    obj["text"] = text
    obj["length"] = len(text)
    try:
        if link:
            obj["source"] = urlparse(link).netloc.split(".")[-2]
    except:
        import traceback; traceback.print_exc()
        errorLogger.debug("Link failed for object: {0}".format(obj.keys()))
        obj["source"] = link

    try:
        obj["date"] = date_parse(obj.get("date")).strftime("%s")
    except:
        errorLogger.debug("Date failed for object: {0}".format(obj.keys()))
        obj["date"] = ""

    obj["financial"] = cross_reference(obj["text"], FINANCIAL_WORDS)
    obj["indico"] = {}
    return Document(**obj)

def try_except_result(future, rerun, data, default, individual=False, sleep=10):
    try:
        return future.result()
    except Exception as e:
        import traceback; traceback.print_exc()
        if "Gateway" in str(e):
            time.sleep(sleep)
            return try_except_result(rerun(data), rerun, data, default, individual=False, sleep=sleep*2)
        if individual:
            return [default]
        return [try_except_result(rerun([doc]), rerun, [doc], default, individual=True) for doc in data]

def add_indico(executor, documents):
    documents = filter(_relevant_and_recent, documents)
    if not documents:
        return []
    try:
        analysis = {}
        texts = [doc.get("text") for doc in documents]
        titles = [doc.get("title") for doc in documents]

        summaries = [executor.submit(ENGLISH_SUMMARIZER.parse, text, sentences=3) for text in texts]
        embeddings = [executor.submit(FINANCE_EMBEDDING._transform, text) for text in texts]

        title_sentiment_hq = lambda data: executor.submit(indicoio.sentiment_hq, data)
        title_keywords = lambda data: executor.submit(indicoio.keywords, data, version=1)
        title_people = lambda data: executor.submit(indicoio.people, data, version=2)
        title_places = lambda data: executor.submit(indicoio.places, data, version=2)
        title_organizations = lambda data: executor.submit(indicoio.organizations, data, version=2)
        sentiment_hq = lambda data: executor.submit(indicoio.sentiment_hq, data)
        keywords = lambda data: executor.submit(indicoio.keywords, data, version=1)
        people = lambda data: executor.submit(indicoio.people, data, version=2)
        places = lambda data: executor.submit(indicoio.places, data, version=2)
        organizations = lambda data: executor.submit(indicoio.organizations, data, version=2)

        analysis["title_sentiment_hq"] = title_sentiment_hq(titles)
        analysis["title_keywords"] = title_keywords(titles)
        analysis["title_people"] = title_people(titles)
        analysis["title_places"] = title_places(titles)
        analysis["title_organizations"] = title_organizations(titles)
        analysis["sentiment_hq"] = sentiment_hq(texts)
        analysis["keywords"] = keywords(texts)
        analysis["people"] = people(texts)
        analysis["places"] = places(texts)
        analysis["organizations"] = organizations(texts)

        individual = len(documents) <= 1
        analysis["title_sentiment_hq"] = try_except_result(analysis["title_sentiment_hq"], title_sentiment_hq, titles, -1, individual=individual)
        analysis["title_keywords"] = try_except_result(analysis["title_keywords"], title_keywords, titles, [], individual=individual)
        analysis["title_people"] = try_except_result(analysis["title_people"], title_people, titles, defaultdict(list), individual=individual)
        analysis["title_places"] = try_except_result(analysis["title_places"], title_places, titles, defaultdict(list), individual=individual)
        analysis["title_organizations"] = try_except_result(analysis["title_organizations"], title_organizations, titles, defaultdict(list), individual=individual)
        analysis["sentiment_hq"] = try_except_result(analysis["sentiment_hq"], sentiment_hq, texts, -1, individual=individual)
        analysis["keywords"] = try_except_result(analysis["keywords"], keywords, texts, [], individual=individual)
        analysis["people"] = try_except_result(analysis["people"], people, texts, defaultdict(list), individual=individual)
        analysis["places"] = try_except_result(analysis["places"], places, texts, defaultdict(list), individual=individual)
        analysis["organizations"] = try_except_result(analysis["organizations"], organizations, texts, defaultdict(list), individual=individual)

        for i in xrange(len(documents)):
            # Title Analysis
            documents[i]["indico"] = {}
            documents[i]["indico"]["title_sentiment"] = analysis.get('title_sentiment_hq')[i]
            documents[i]["indico"]["title_keywords"] = analysis.get('title_keywords')[i]
            documents[i]["indico"]["title_people"] = analysis.get('title_people')[i]
            documents[i]["indico"]["title_places"] = analysis.get('title_places')[i]
            documents[i]["indico"]["title_organizations"] = analysis.get('title_organizations')[i]

            # Main Text
            documents[i]["indico"]["sentiment"] = analysis.get('sentiment_hq')[i]
            documents[i]["indico"]["keywords"] = analysis.get('keywords')[i]
            documents[i]["indico"]["people"] = analysis.get('people')[i]
            documents[i]["indico"]["places"] = analysis.get('places')[i]
            documents[i]["indico"]["organizations"] = analysis.get('organizations')[i]

            # Summary
            documents[i]["summary"] = summaries[i].result()

            # Finance Embeddings
            documents[i]["finance_embeddings"] = json.dumps(embeddings[i].result().tolist())

        return documents
    except:
        import traceback;
        errorLogger.info(traceback.format_exc())
        return []

def get_all_data_files(current_dir):
    all_files = []
    for subdir, dirs, files in os.walk(current_dir):
        for filename in files:
            all_files.append(os.path.join(current_dir, filename))
    return all_files

def read_file(data_file):
    try:
        return read_xlsx_file(data_file)
    except:
        return read_ndjson_file(data_file)

def read_ndjson_file(data_file):
    documents = []
    with open(data_file, 'rb') as f:
        root.debug("Parsing Documents for {0}".format(data_file))
        for line in f:
            try:
                obj = json.loads(line)
                obj = parse_obj_to_document(obj)
                if obj:
                    documents.append(obj)
            except Exception as e:
                import traceback; traceback.print_exc()
                errorLogger.info("NDJSON Line reading failed with error: {0}\n{1}:{2}".format(e, data_file, line))
    return documents

def read_xlsx_file(data_file):
    try:
        reader = get_data(data_file, streaming=True)
        columns = reader.next()
        documents = []
        root.debug("Parsing Documents for {0}".format(data_file))
        for line in reader:
            obj = dict(zip(columns, line))
            if len(obj.get("description_text", "") or "") < DESCRIPTION_THRESHOLD:
                continue
            try:
                obj = {key.lower():value for key,value in obj.iteritems() if not key.startswith("Unnamed: ")}
                obj = parse_obj_to_document(obj)
                if obj:
                    documents.append(obj)
            except:
                import traceback; traceback.print_exc()
        return documents
    except:
        import traceback; traceback.print_exc()
        errorLogger.info("XLSX File reading failed: {0}".format(data_file))
        raise

def upload_data(es, data_file):
    indico_executor = ThreadPoolExecutor(max_workers=4)
    executor = ThreadPoolExecutor(max_workers=4)
    try:
        root.info("Beginning Processing for {0}".format(data_file))
        all_documents = read_file(data_file)
        root.info("Read Data for {0}".format(data_file))
        futures = {}
        root.info("Adding Indico for {0}".format(data_file))
        for documents in partition_all(20, all_documents):
            futures[executor.submit(add_indico, indico_executor, documents)] = 0

        root.info("Uploading to elasticsearch for {0}".format(data_file))
        for future in concurrent.futures.as_completed(futures):
            es.upload(future.result())
            del futures[future]

        root.info("Completed to elasticsearch for {0}".format(data_file))
        return data_file, len(all_documents) > 0
    except:
        import traceback; traceback.print_exc()
        return "", False

def process(files):
    executor = ThreadPoolExecutor(max_workers=2)
    futures = {executor.submit(upload_data, es, _file): _file for _file in files}
    for future in concurrent.futures.as_completed(futures):
        with open(COMPLETED_PATH, 'ab') as f:
            path, success = future.result()
            if success:
                f.write(os.path.basename(path) + "\n")
            del futures[future]

if __name__ == "__main__":
    directory = os.path.join(os.path.dirname(__file__), '../../ingress_data')

    with open(COMPLETED_PATH, 'rb') as f:
        completed = map(lambda x: x.strip(), f.readlines())

    files = get_all_data_files(directory)
    files = filter(lambda x: not any([y in x for y in completed]), files)

    p = Pool(NUM_PROCESSES)
    files = [files[i:i+NUM_PROCESSES] for i in xrange(0, len(files), NUM_PROCESSES)]
    p.map(process, files)
