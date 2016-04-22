import re

from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from nltk.stem.snowball import SnowballStemmer
from sklearn.cluster import DBSCAN

def SnowballNumberTokenizer(doc):
    stemmer = SnowballStemmer('english')
    pattern = re.compile(u'(?u)\\b\\w\\w+\\b')
    tokens = pattern.findall(doc)
    return ["#NUMBER" if token[0] in "0123456789_" else stemmer.stem(token) for token in tokens]


def make_feature_vectors(article_list, style):
    tokenizer_params = {
                        "stop_words": 'english',
                        "min_df": 3,
                        "tokenizer": SnowballNumberTokenizer,
                        "ngram_range": (1,2),
                       }
    if style == "tf-idf":
        vectorizer = TfidfVectorizer(**tokenizer_params)
    if style == "count":
        vectorizer = CountVectorizer(**tokenizer_params)
    return vectorizer.fit_transform(article_list)


def DBScanClustering(feature_vectors, **kwargs):
    clusterer = DBSCAN(**kwargs)
    fitted_response = clusterer.fit_predict(feature_vectors)
    centers = clusterer.core_sample_indices_
    print 'centers'
    print centers
    return fitted_response, centers

def parse_float(string):
    return float(string.strip('%'))/100
