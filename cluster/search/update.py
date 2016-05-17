import json, os

from client import ESConnection

from .words import cross_reference

FINANCIAL_WORDS = set(json.loads(open(os.path.join(
    os.path.dirname(__file__), "data", "financial_keywords.json"
)).read()))

def add_financial_keywords(doc):
    text = doc["text"]
    doc["financial"] = cross_refrence(text, FINANCIAL_WORDS)
    return doc

if __name__ == "__main__":
    es = ESConnection("localhost:9200")
    es.update("*", "60m", add_financial_keywords)
