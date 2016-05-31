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
        best_num_clusters = [0, 0]
        for epsilon in eps_range:
            clusterer = DBSCAN(eps=epsilon, **self.kwargs)
            fitted_response = clusterer.fit_predict(self.feature_vectors)

            # If results are worse, just skip the rest
            # if len(set(fitted_response)) < best_num_clusters:
            #     continue

            # Calculate similarites
            if len(set(fitted_response)) > best_num_clusters[0]:
                best_num_clusters = [len(set(fitted_response)), epsilon]

            # If it's good enough, let's go!
        clusterer = DBSCAN(eps=best_num_clusters[1], **self.kwargs)
        
        fitted_response = clusterer.fit_predict(self.feature_vectors)
        if not clusterer.components_.shape[0]:
            similarities = [1] * self.feature_vectors.shape[0]
        else:
            similarities = np.max(self.feature_vectors.dot(clusterer.components_.T), axis = 1)

        return fitted_response, similarities.tolist()
