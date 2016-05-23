import os, re, sys, json
import datetime, logging
from multiprocessing import Pool

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
logging.getLogger('requests').setLevel(logging.CRITICAL)

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
root.setLevel(logging.DEBUG)
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

es = ESConnection("localhost:9200")

def _in_sp500(document):
    return any(map(lambda x: x.search(document["text"]), SP500_REGEX)) or \
           any(map(lambda x: x.search(document["title"]), SP500_REGEX))

def _relevant_and_recent(document):
    if not document.link or "Service Unavailable" in document.text:
        return False
    if not document.get("text") or not document.get("title"):
        return False
    if _in_sp500(document):
        return True
    if document.get("date", "") == "":
        return True
    if document.get("date") < ONE_YEAR_AGO:
        return False
    return True

def parse_obj_to_document(obj):
    text = obj.get("description_text")
    title = obj.get("name_post", obj.get("name_story"))
    link = obj.get("url_post", obj.get("url_story"))
    tags = [obj.get("name_categorie", obj.get("name_topics"))]

    # Remove CSS & HTML residue
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"[\s]+", " ", text)
    text = re.sub(r"[[\w\-]*\s*[\.[\w\-]*\s*]*]*\s*{[^}]*}", "", text)
    text = text.encode("ascii", "ignore").decode("ascii", "ignore")

    try:
        source = urlparse(link).netloc.split(".")[-2]
    except:
        import traceback; traceback.print_exc()
        errorLogger.info("Link failed for object: {0}".format(obj.keys))
        source = link

    try:
        pub_date = date_parse(obj.get("date_published", obj.get("date_published_story", obj.get("date_e_post")))).strftime("%s")
    except:
        errorLogger.info("Date failed for object: {0}".format(obj.keys()))
        pub_date = ""

    return Document(
        title=title,
        text=text,
        link=link,
        tags=tags,
        length=len(text),
        date=pub_date,
        indico={},
        financial=cross_reference(text, FINANCIAL_WORDS),
        source=source
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
        texts = [doc.get("text") for doc in documents]
        titles = [doc.get("title") for doc in documents]

        summaries = [executor.submit(ENGLISH_SUMMARIZER.parse, text, sentences=3) for text in texts]
        embeddings = [executor.submit(FINANCE_EMBEDDING._transform, text) for text in texts]

        analysis["title_sentiment_hq"] = executor.submit(indicoio.sentiment_hq, titles)
        analysis["title_keywords"] = executor.submit(indicoio.keywords, titles, version=1)
        analysis["title_ner"] = executor.submit(indicoio.named_entities, titles, version=2)
        analysis["sentiment_hq"] = executor.submit(indicoio.sentiment_hq, texts)
        analysis["keywords"] = executor.submit(indicoio.keywords, texts, version=1)
        analysis["ner"] = executor.submit(indicoio.named_entities, texts, version=2)

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

            # Finance Embeddings
            documents[i]["finance_embeddings"] = embeddings[i].result().tostring()

        return documents
    except:
        import traceback; traceback.print_exc()
        if len(documents) <= 1:
            errorLogger.info("Adding indico failed for document: {0}".format(documents))
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
        errorLogger.info("File reading failed: {0}".format(data_file))
        return []

def upload_data(es, data_file):
    indico_executor = ThreadPoolExecutor(max_workers=30)
    executor = ThreadPoolExecutor(max_workers=5)
    try:
        root.info("Beginning Processing for {0}".format(data_file))
        all_documents = read_data_file(data_file)
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
    executor = ThreadPoolExecutor(max_workers=4)
    futures = {executor.submit(upload_data, es, _file): _file for _file in files}

    for future in concurrent.futures.as_completed(futures):
        with open(COMPLETED_PATH, 'ab') as f:
            path, success = future.result()
            if success:
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
