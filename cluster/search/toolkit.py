import datetime

from .client import ESConnection

if __name__ == "__main__":
    es = ESConnection("localhost:9200")
    year_2015 = (
        datetime.datetime(2015, 1, 1),
        datetime.datetime(2016, 1, 1)
    )

    year_2014 = (
        datetime.datetime(2014, 1, 1),
        datetime.datetime(2015, 1, 1)
    )

    year_2013 = (
        datetime.datetime(2013, 1, 1),
        datetime.datetime(2014, 1, 1)
    )
