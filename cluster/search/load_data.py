import os, re, sys, json
import datetime, logging
from multiprocessing import Pool

from picklable_itertools.extras import partition_all
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from dateutil.parser import parse as date_parse

from pyexcel_xlsx import get_data
import indicoio

from .client import ESConnection
from .schema import Document
from .summary import Summary
from .words import cross_reference

# Turn down requests log verbosity
logging.getLogger('requests').setLevel(logging.CRITICAL)

# Processing
ENGLISH_SUMMARIZER = Summary(language="english")
NOW = datetime.datetime.now()
ONE_YEAR_AGO = NOW.replace(year = NOW.year - 1)
DESCRIPTION_THRESHOLD = 600
NUM_PROCESSES= int(sys.argv[1])
COMPLETED_PATH = os.path.join(os.path.dirname(__file__), '../../completed.txt')

# Logging
root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
root.addHandler(ch)

# Indico
indicoio.config.cloud = 'themeextraction'

SP_TICKERS = open(os.path.join(
    os.path.dirname(__file__), "data", "sp500.txt"
)).readlines()
FINANCIAL_WORDS = set(json.loads(open(os.path.join(
    os.path.dirname(__file__), "data", "financial_keywords.json"
)).read()))

es = ESConnection("localhost:9200")

def _not_in_sp500(document):
    in_text = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["text"]) for ticker in SP_TICKERS])
    in_title = any([re.compile(r'[^a-zA-Z]'+ re.escape(ticker)+ r'[^a-zA-Z]').search(document["title"]) for ticker in SP_TICKERS])
    return not(in_text or in_title)

def _relevant_and_recent(document):
    try:
        if not document.link or "Service Unavailable" in document.text:
            return False
        if not document.get("text") or not document.get("title"):
            return False
        if date_parse(document.get("date")) < ONE_YEAR_AGO and _not_in_sp500(document):
            return False
    except:
        return False
    return True

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
        financial=cross_reference(text, FINANCIAL_WORDS)
    )

def try_except_result(future, default, individual=False):
    try:
        return future.result()
    except:
        if individual:
            return [default]
        raise

def add_indico(executor, documents):
    documents = filter(_relevant_and_recent, documents)
    if not documents:
        return []
    try:
        analysis = {}
        summaries = [executor.submit(ENGLISH_SUMMARIZER.parse, doc.get("text"), sentences=3) for doc in documents]

        analysis["title_sentiment_hq"] = executor.submit(indicoio.sentiment_hq, [doc.get("title") for doc in documents])
        analysis["title_keywords"] = executor.submit(indicoio.keywords, [doc.get("title") for doc in documents], version=1)
        analysis["title_ner"] = executor.submit(indicoio.named_entities, [doc.get("title") for doc in documents], version=2)
        analysis["sentiment_hq"] = executor.submit(indicoio.sentiment_hq, [doc.get("text") for doc in documents])
        analysis["keywords"] = executor.submit(indicoio.keywords, [doc.get("text") for doc in documents], version=1)
        analysis["ner"] = executor.submit(indicoio.named_entities, [doc.get("text") for doc in documents], version=2)

        individual = len(documents) <= 1
        analysis["title_sentiment_hq"] = try_except_result(analysis["title_sentiment_hq"], -1, individual=individual)
        analysis["title_keywords"] = try_except_result(analysis["title_keywords"], [], individual=individual)
        analysis["title_ner"] = try_except_result(analysis["title_ner"], defaultdict(list), individual=individual)
        analysis["sentiment_hq"] = try_except_result(analysis["sentiment_hq"], -1, individual=individual)
        analysis["keywords"] = try_except_result(analysis["keywords"], [], individual=individual)
        analysis["ner"] = try_except_result(analysis["ner"], defaultdict(list), individual=individual)

        for i in xrange(len(documents)):
            # Title Analysis
            documents[i]["indico"] = {}
            documents[i]["indico"]["title_sentiment"] = analysis.get('title_sentiment_hq')[i]
            documents[i]["indico"]["title_keywords"] = analysis.get('title_keywords')[i]
            documents[i]["indico"]["title_people"] = analysis.get('title_ner')[i].get("people")
            documents[i]["indico"]["title_places"] = analysis.get('title_ner')[i].get("places")
            documents[i]["indico"]["title_organizations"] = analysis.get('title_ner')[i].get("organizations")

            # Main Text
            documents[i]["indico"]["sentiment"] = analysis.get('sentiment_hq')[i]
            documents[i]["indico"]["keywords"] = analysis.get('keywords')[i]
            documents[i]["indico"]["people"] = analysis.get('ner')[i].get("people")
            documents[i]["indico"]["places"] = analysis.get('ner')[i].get("places")
            documents[i]["indico"]["organizations"] = analysis.get('ner')[i].get("organizations")

            # Summary
            documents[i]["summary"] = summaries[i].result()

        return documents
    except:
        import traceback; traceback.print_exc()
        if len(documents) <= 1:
            return []

        # Split into batches of 1 and recombine
        try:
            results = []
            for document in documents:
                results.extend(add_indico(executor, [document]))
            return results
        except:
            import traceback; traceback.print_exc()
            return []

def get_all_data_files(current_dir):
    all_files = []
    for subdir, dirs, files in os.walk(current_dir):
        for filename in files:
            all_files.append(os.path.join(current_dir, filename))
    return all_files

def read_data_file(data_file):
    try:
        reader = get_data(data_file, streaming=True)
        columns = reader.next()
        documents = []
        root.debug("Parsing Documents for {0}".format(data_file))
        for line in reader:
            obj = dict(zip(columns, line))
            if len(obj.get("description_text", "") or "") < DESCRIPTION_THRESHOLD:
                continue
            documents.append(parse_obj_to_document(obj))
        return documents
    except:
        import traceback; traceback.print_exc()
        return []

def upload_data(es, data_file):
    indico_executor = ThreadPoolExecutor(max_workers=30)
    executor = ThreadPoolExecutor(max_workers=5)
    try:
        root.debug("Beginning Processing for {0}".format(data_file))
        all_documents = read_data_file(data_file)
        root.debug("Read Data for {0}".format(data_file))
        futures = {}
        root.debug("Adding Indico for {0}".format(data_file))
        for documents in partition_all(20, all_documents):
            futures[executor.submit(add_indico, indico_executor, documents)] = 0

        root.debug("Uploading to elasticsearch for {0}".format(data_file))
        for future in concurrent.futures.as_completed(futures):
            es.upload(future.result())
            del futures[future]

        root.debug("Completed to elasticsearch for {0}".format(data_file))
        return data_file
    except:
        import traceback; traceback.print_exc()

def process(files):
    executor = ThreadPoolExecutor(max_workers=4)
    futures = {executor.submit(upload_data, es, _file): _file for _file in files}

    for future in concurrent.futures.as_completed(futures):
        with open(COMPLETED_PATH, 'ab') as f:
            path = future.result()
            if path:
                f.write(os.path.basename(path) + "\n")
            del futures[future]

if __name__ == "__main__":
    directory = os.path.join(os.path.dirname(__file__), '../../inputxl')

    with open(COMPLETED_PATH, 'rb') as f:
        completed = map(lambda x: x.strip(), f.readlines())

    files = get_all_data_files(directory)
    files = filter(lambda x: not any([y in x for y in completed]), files)

    p = Pool(NUM_PROCESSES)
    files = [files[i:i+NUM_PROCESSES] for i in xrange(0, len(files), NUM_PROCESSES)]
    p.map(process, files)
