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

    def get_clusters(self, epsilon_step=.1):
        if epsilon_step <= 0 or epsilon_step > 1:
            raise ValueError("epsilon_step must be between 0 and 1 exclusive")
        epsilon = epsilon_step
        best_num_clusters = 0
        while epsilon < 1:
            clusterer = DBSCAN(eps=epsilon, **self.kwargs)
            fitted_response = clusterer.fit_predict(self.feature_vectors)

            # If results are worse, just skip the rest
            if len(fitted_response) < best_num_clusters:
                epsilon += epsilon_step
                continue

            # Calculate similarites
            best_num_clusters = len(fitted_response)
            if not clusterer.components_.shape[0]:
                similarities = [1] * self.feature_vectors.shape[0]
            else:
                similarities = np.max(self.feature_vectors.dot(clusterer.components_.T), axis = 1)

            # If it's good enough, let's go!
            if best_num_clusters > 4:
                return fitted_response, similarities.tolist()
            epsilon += epsilon_step
        return fitted_response, similarities.tolist()
