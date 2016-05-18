import json, os

from client import ESConnection
from .words import cross_reference

FINANCIAL_WORDS = set(json.loads(open(os.path.join(
    os.path.dirname(__file__), "data", "financial_keywords.json"
)).read()))

LINKS = set()
IDS_DELETE = list()

def add_financial_keywords(doc):
    source = doc["_source"]
    if not source.get("financial"):
        text = source["text"]
        source["financial"] = cross_reference(text, FINANCIAL_WORDS)
        return True
    return False

def dedup(doc):
    if doc["_source"].get("link") in LINKS:
        IDS_DELETE.append(doc.get("_id"))
    LINKS.add(doc["_source"].get("link"))
    return False

def convert_link_to_id(doc):
    if doc["_id"] != doc["_source"]["link"]:
        IDS_DELETE.append(doc["_id"])
        doc["_id"] = doc["_source"]["link"]
        return True
    return False

def update(doc):
    changed = False
    # changed = add_financial_keywords(doc)
    # changed = dedup(doc) or changed
    changed = convert_link_to_id(doc) or changed
    return changed

if __name__ == "__main__":
    es = ESConnection("localhost:9200")
    try:
        es.update("*", "1m", update, window=5000)
    except:
        import traceback; traceback.print_exc()
    finally:
        import json
        with open("set_of_links.json", 'wb') as f:
            f.write(json.dumps(list(LINKS)))
        with open("ids_to_delete.json", 'wb') as f:
            f.write(json.dumps(IDS_DELETE))
    es.delete_by_ids(IDS_DELETE)
