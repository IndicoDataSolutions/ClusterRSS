INDEX="indico-cluster-data"

class Document(dict):
    def __init__(self, title="", text="", tags=[], link="", _type="document"):
        super(Document, self).__init__()
        self.update({
            "title": title,
            "text": text,
            "tags": tags,
            "link": link,
            "_type": _type
        })
