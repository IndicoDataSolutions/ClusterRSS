import datetime

from .client import ESConnection

if __name__ == "__main__":
    es = ESConnection("localhost:9200")
    print es.stats("date")
