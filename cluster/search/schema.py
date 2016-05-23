INDEX="indico-cluster-data"

class Document(dict):
    def __init__(self, title="", text="", tags=[], link="", length=0, summary="", financial=[], indico={}, source="", _type="document", date=""):
        super(Document, self).__init__()
        self.update({
            "title": title,
            "text": text,
            "tags": tags,
            "link": link,
            "length": length,
            "summary": summary,
            "financial": financial,
            "indico": indico,
            "date": date,
            "_type": _type,
            "_id": link,
            "source": source
        })

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            return super(Document, self).__getattr__(key)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)
