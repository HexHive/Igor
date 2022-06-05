#!/bin/env python3

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

from CFGenerator import *
from sklearn import ensemble
from sklearn import metrics
from sklearn import cluster
from sklearn.manifold import MDS
from matplotlib import cm, colors
import matplotlib.pyplot as plt
import argparse
import os
import math
import shutil

TMP_DIR_SUFFIX = "_clustering_tmp"
OUTLIER_DIR_SUFFIX = "_clustering_outlier"
PLOT_FILENAME = "clustering_visualization.png"


def is_result_dir_available(result_dir):
    """
    Check whether the result dir is available(empty or not exists) or not.

    :param result_dir:
    :return: True, if result_dir is available
    """
    if result_dir is None:
        return False
    if os.path.exists(result_dir) and len(os.listdir(result_dir)) > 0:
        return False
    return True


class ClusterWrapper:
    def __init__(self, traces_dir, result_dir=None, kernel_mode=3, attribute_mode=0, outlier_ratio=0.05,
                 max_cluster=16):
        self._traces_dir = os.path.abspath(os.path.expanduser(traces_dir))
        self._result_dir = result_dir
        self._kernel_mode = kernel_mode
        self._attribute_mode = attribute_mode
        self._outlier_ratio = outlier_ratio
        self._max_cluster = max_cluster
        self._similarity_mat = None
        self.labels_ = None
        if self._result_dir:
            self._result_dir = os.path.expanduser(self._result_dir)
            if not os.path.exists(self._result_dir):
                os.makedirs(self._result_dir)

    def _generate_similarity_matrix(self, traces_dir):
        """
        Invoke CFGenerator to generate a similarity matrix of traces in `traces_dir`.

        Element value ranging from 0(completely different) to 1(identical).

        :param traces_dir: dir containing trace files
        :return: similarity matrix of given trace files
        """
        cfg_generator = CFGenerator(traces_dir, self._kernel_mode, self._attribute_mode)
        cfg_generator.gen_CFG_wrapper()
        cfg_generator.cfg_similarity()
        return cfg_generator.get_similarity_matrix()

    def _handle_outlier(self, tmp_dir, outlier_dir):
        """
        Calling outlier detection function and handle with outliers.

        :param tmp_dir: directory containing copies of original trace files
        :param outlier_dir: directory to store outliers
        :return:
        """
        outlier_flags = self._outlier_detection(tmp_dir)
        number_of_outliers = len(list(filter(lambda x: x == -1, outlier_flags)))
        number_of_samples = len(outlier_flags)

        # When the number of outliers is more or equal than `_outlier_ratio`, we assert that the outer detection
        # algorithm made a mistake, and all samples should be clustered.
        if number_of_outliers >= math.floor(number_of_samples * self._outlier_ratio):
            return

        # When the number of outliers is less than `_outlier_ratio`, we move the outliers from `tmp_dir` to
        # `outlier_dir`, so that they won't be clustered later.
        tmp_dir_files = sorted(os.listdir(tmp_dir))
        for idx, outlier_flag in enumerate(outlier_flags):
            # Not an outlier
            if outlier_flag == 1:
                continue
            # Move the outlier from `tmp_dir` to `outlier_dir`
            src = os.path.join(tmp_dir, tmp_dir_files[idx])
            shutil.move(src, outlier_dir)

    def _outlier_detection(self, tmp_dir):
        """
        Using Isolation Forest for outlier detection.

        :param tmp_dir: directory containing copies of original trace files
        :return: an array, element value -1 indicates an outlier.
        """
        dist_mat = 1 - self._generate_similarity_matrix(tmp_dir)
        iso = ensemble.IsolationForest(contamination='auto', random_state=42)
        outlier_flags = iso.fit(dist_mat).predict(dist_mat)
        return outlier_flags

    def _data_preprocessing(self, tmp_dir, outlier_dir):
        """
        Prepare temporal directory and outlier directory, as well as handling outliers.

        :param tmp_dir: directory containing copies of original trace files
        :param outlier_dir: directory containing outliers
        :return:
        """
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        if not os.path.exists(outlier_dir):
            os.makedirs(outlier_dir)
        for src_file in os.listdir(self._traces_dir):
            src_path = os.path.join(self._traces_dir, src_file)
            shutil.copy(src_path, tmp_dir)
        self._handle_outlier(tmp_dir, outlier_dir)

    def _do_clustering(self, tmp_dir):
        """
        Do the clustering job, enumerate all possible number of clusters, and return the clustering result
        which scores the highest on silhouette score.

        :param tmp_dir: directory containing copies of original trace files
        :return:
        """
        similarity_mat = self._generate_similarity_matrix(tmp_dir)
        self._similarity_mat = similarity_mat
        dist_mat = 1 - similarity_mat
        max_silhouette_score = -math.inf
        this_sc = -math.inf
        last_sc = -math.inf
        predicted_cluster = None
        continuous_decrease_cnt = 0

        for n_clusters_ in range(2, self._max_cluster + 1):
            clustering = cluster.SpectralClustering(
                n_clusters=n_clusters_, assign_labels="discretize", random_state=0, affinity='precomputed').fit(
                similarity_mat)

            # Get clustering result and calculate the corresponding silhouette score.
            predicted = clustering.labels_
            this_sc = metrics.silhouette_score(dist_mat, predicted, metric='precomputed')

            # If the score in current round larger than previous round,
            # we should reset the counter of decrease first
            if this_sc >= last_sc:
                continuous_decrease_cnt = 0
                # If a larger `n_clusters` leads to the same silhouette score as the smaller one,
                # we prefer the smaller `n_clusters`.
                if this_sc > max_silhouette_score:
                    max_silhouette_score = this_sc
                    predicted_cluster = predicted
            else:
                continuous_decrease_cnt += 1

            # If a second consecutive decrease on silhouette score is encountered, return the current best clustering
            # result(`predicted_cluster`).
            if continuous_decrease_cnt == 2:
                return predicted_cluster

            # Save the score in current round
            last_sc = this_sc
        return predicted_cluster

    def clustering(self):
        """
        Note that the returned label list is sorted by filename, since CFGenerator will sort the input
        file list before calculating similarity matrices.

        :return: predicted labels for input samples.
        """
        traces_dir_name = os.path.basename(self._traces_dir)
        tmp_dir = os.path.join("/tmp", traces_dir_name + TMP_DIR_SUFFIX)
        outlier_dir = os.path.join("/tmp", traces_dir_name + OUTLIER_DIR_SUFFIX)
        self._data_preprocessing(tmp_dir, outlier_dir)

        self.labels_ = self._do_clustering(tmp_dir)
        if self._result_dir is not None:
            if not os.path.exists(self._result_dir):
                os.makedirs(self._result_dir)
            self._group_input_files_by_label(self.labels_, tmp_dir, outlier_dir)
            self._plot()

    def _plot(self):
        """
        Generate clustering result plot, saving to the result directory.
        :return:
        """
        labels = np.array(self.labels_)

        c_norm = colors.Normalize(vmin=labels.min(), vmax=labels.max())
        color_map = plt.get_cmap('RdYlGn')
        scalar_map = cm.ScalarMappable(norm=c_norm, cmap=color_map)

        mds = MDS(dissimilarity="precomputed")
        projection = mds.fit_transform(1 - self._similarity_mat)

        plt.figure(dpi=600)
        for label in set(labels):
            selector = (labels == label)
            plt.scatter(projection[selector, 0], projection[selector, 1], color=scalar_map.to_rgba(label),
                        label="cluster {}".format(label), edgecolors="black", linewidth=0.5)
        plt.legend()
        plot_filename = os.path.join(self._result_dir, PLOT_FILENAME)
        plt.savefig(plot_filename)

    def _group_input_files_by_label(self, labels, cluster_tmp_dir, outlier_dir):
        """
        Group input files by their labels and put them into the result dir.

        :param labels: labels returned by clustering function
        :param cluster_tmp_dir: directory containing copies of original trace files
        :param outlier_dir: directory containing outliers
        :return:
        """

        for label in set(labels):
            cluster_label_dir = os.path.join(self._result_dir, "cluster_{}".format(label))
            os.mkdir(cluster_label_dir)

        # The elements of the position in `cluster_tmp_dir_files` and `labels` represents the same object.
        cluster_tmp_dir_files = sorted(os.listdir(cluster_tmp_dir))
        for idx, src_filename in enumerate(cluster_tmp_dir_files):
            src_path = os.path.join(cluster_tmp_dir, src_filename)
            label = labels[idx]
            dst_path = os.path.join(self._result_dir, "cluster_{}".format(label))
            shutil.move(src_path, dst_path)

        shutil.move(outlier_dir, self._result_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", help="traces directory")
    parser.add_argument("-o", help="result directory")
    parser.add_argument("-k", help="kernel mode, default: [3]", type=int, default=3)
    parser.add_argument("-a", help="attribute mode, default: [0]", type=int, default=0)
    parser.add_argument("--outlier", help="outlier ratio, default: [0.05]", type=float, default=0.05)
    parser.add_argument("--max_cluster", help="maximum number of clusters, default: [16]", type=int, default=16)

    args = parser.parse_args()

    if not is_result_dir_available(args.o):
        print("Result directory is not empty, please use another directory.")
        exit(-1)

    C = ClusterWrapper(args.i, args.o, args.k, args.a, args.outlier, args.max_cluster)
    C.clustering()
    print(C.labels_)
