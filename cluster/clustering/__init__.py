from operator import itemgetter
from collections import defaultdict, Counter

from scipy.spatial.distance import cdist
import numpy as np

from .clusterer import DBScanClusterer

INDICO_VALUES = ["keywords", "title_keywords", "people", "places", "oragnizations"]

def generate_clusters_dict(entries, all_clusters, all_similarities, feature_vectors):
    # Build Result Dict
    count = defaultdict(int)
    cluster_features = {}
    result_dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for i in xrange(len(all_clusters)):
        if all_clusters[i] < 0:
            continue
        count[all_clusters[i]] += 1
        if count[all_clusters[i]] > 20:
            continue
        entry, cluster = entries[i], all_clusters[i]
        entry['cluster'], entry["distance"] = cluster, all_similarities[i]
        cluster_features[cluster] = cluster_features.get(cluster, []) + [feature_vectors[i]]
        result_dict[cluster]["articles"] = result_dict[cluster].get("articles", []) + [entry]

    # Postprocessing
    result_dict = _fill_cluster_indico_data(result_dict)
    result_dict = _filter_threshold_keywords(result_dict)
    result_dict = _fill_cluster_centers(result_dict, cluster_features)

    return result_dict

def _fill_cluster_centers(result_dict, cluster_features):
    cluster_centers = {}
    for cluster, features_list in cluster_features.items():
        array_features = np.array([np.asarray(el).flatten() for el in features_list])
        distance_sums = [sum(dists) for dists in cdist(array_features, array_features, 'euclidean')]
        index = min(enumerate(distance_sums), key=itemgetter(1))[0]

        result_dict[cluster]["cluster_title"] = result_dict[cluster]["articles"][index]

    return result_dict

def _fill_cluster_indico_data(result_dict):
    for cluster, cluster_info in result_dict.iteritems():
        cluster_info["people"] = _create_full_cluster_list(cluster_info, "people")
        cluster_info["places"] = _create_full_cluster_list(cluster_info, "places")
        cluster_info["organizations"] = _create_full_cluster_list(cluster_info, "organizations")
        cluster_info["keywords"] = [word_pair[0] for word_pair in sorted(
            _create_full_cluster_dict(cluster_info, "keywords").items(), key=itemgetter(1), reverse=True
        )[:10]]
        cluster_info['title_keywords'] = [word_pair[0] for word_pair in sorted(
            _create_full_cluster_dict(cluster_info, "title_keywords").items(), key=itemgetter(1), reverse=True
        )[:10]]
        result_dict[cluster] = cluster_info
    return result_dict


def _filter_threshold_keywords(result_dict):
    title_keywords_list = Counter()
    keywords_list = Counter()
    for cluster_info in result_dict.values():
        title_keywords_list.update(filter(lambda x: x != "Shutterstock", cluster_info['title_keywords']))
        keywords_list.update(filter(lambda x: x != "Shutterstock", cluster_info['keywords']))

    for cluster, cluster_info in result_dict.items():
        cluster_info['keywords'] = [value for value in cluster_info['keywords']
                              if keywords_list[value] <= max(len(result_dict)*.35, 1)][-3:]
        cluster_info['title_keywords'] = [value for value in cluster_info['title_keywords']
                              if title_keywords_list[value] <= max(len(result_dict)*.35, 1)][-3:]
        result_dict[cluster] = cluster_info
    return result_dict

def _create_full_cluster_list(cluster_info, key):
    return [entity for article in cluster_info['articles'] for entity in article['indico'].get(key)]

def _create_full_cluster_dict(cluster_info, key):
    return {k: v for article in cluster_info['articles'] for k, v in article['indico'].get(key).items()}
