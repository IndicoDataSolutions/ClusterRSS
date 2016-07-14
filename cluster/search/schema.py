import math

INDEX="indico-cluster-data"

class Document(dict):
    def __init__(self, **kwargs):
        super(Document, self).__init__()
        kwargs["_type"] = kwargs.pop("_type", "document")
        if "link" in kwargs:
            kwargs["_id"] = kwargs["link"]
        filtered = self._filter_kwargs(kwargs)
        self.update(filtered)

    def _filter_kwargs(self, kwargs):
        filtered = {}
        for key, value in kwargs.iteritems():
            if isinstance(value, float):
                if math.isnan(value):
                    continue
            if key.lower().startswith("Unnamed:"):
                continue
            filtered[key] = value
        return filtered

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
