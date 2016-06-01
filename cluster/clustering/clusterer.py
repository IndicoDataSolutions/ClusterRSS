from sklearn.cluster import DBSCAN
import numpy as np

from ..errors import ClusterError


class DBScanClusterer(object):
    def __init__(self, feature_vectors, algorithm="brute", metric="cosine", **kwargs):
        self.feature_vectors = feature_vectors
        self.kwargs = kwargs
        if not feature_vectors.shape[0]:
            raise ClusterError('empty results')
        kwargs.update({
            "algorithm": algorithm,
            "metric": "cosine"
        })

    def get_clusters(self, eps_range=[0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008, 0.009, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, .1]):
        best_num_clusters = 0
        best_fitted_response, best_cluster = 0, None
        for epsilon in eps_range:
            clusterer = DBSCAN(eps=epsilon, **self.kwargs)
            fitted_response = clusterer.fit_predict(self.feature_vectors)

            # Check if there are more clusters
            num_unique_responses = len(set(fitted_response))
            if num_unique_responses > best_num_clusters:
                best_num_clusters = num_unique_responses
                best_cluster = clusterer
                best_fitted_response = fitted_response

        if not best_cluster.components_.shape[0]:
            similarities = [1] * self.feature_vectors.shape[0]
        else:
            similarities = np.max(self.feature_vectors.dot(best_cluster.components_.T), axis = 1)

        return best_fitted_response, similarities.tolist()
