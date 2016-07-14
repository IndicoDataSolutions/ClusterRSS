INDEX="indico-cluster-data"

class Document(dict):
    def __init__(self, **kwargs):
        super(Document, self).__init__()
        self.update(kwargs)

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except (AttributeError, KeyError):
            return super(Document, self).__getattr__(key)

    def __setattr__(self, key, value):
        return self.__setitem__(key, value)

    def prepare(self):
        for key, value in self.items():
            if not value:
                del self[key]
        return self
