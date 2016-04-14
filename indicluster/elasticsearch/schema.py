INDEX="indico-cluster-data"

class Document(dict):
    def __init__(self, title="", text="", tags=[], link="", indico={}, _type="document"):
        super(Document, self).__init__()
        self.update({
            "title": title,
            "text": text,
            "tags": tags,
            "link": link,
            "indico": indico,
            "_type": _type
        })

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            return super(Document, self).__getattr__(key)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)
