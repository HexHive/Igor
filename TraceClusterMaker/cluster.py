import typing
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm, colors
from sklearn import cluster, ensemble, metrics
from sklearn.manifold import MDS


class ClusterWrapper:
    """ Wrapper for basic methods about clustering

    The result can be retrieved from `self.clusters_result` which is
    a `numpy.ndarray` whose length equals the number of samples and 
    in which value of index i is the Cluster-ID of sample i. Result
    is `None` which indicates unprepared data.
    """
    def __init__(self, M :np.ndarray) -> None :
        """ Constructor

        :param M: similarity matrix, normalized and symmetric.
        """
        self._similarity_mat = M
        self.clusters_result = None

    def plotter(self, file_name :str) -> None :
        """ Generate clustering result plot and save to file.
        """
        labels = self.clusters_result
        assert (type(labels) == np.ndarray) , "Invalid `self.clusters_result`!"

        c_norm = colors.Normalize(vmin=labels.min(), vmax=labels.max())
        color_map = plt.get_cmap('RdYlGn')
        scalar_map = cm.ScalarMappable(norm=c_norm, cmap=color_map)

        mds = MDS(dissimilarity="precomputed")
        projection = mds.fit_transform(1 - self._similarity_mat)

        plt.figure(dpi=600)
        for label in set(labels):
            selector = (labels == label)
            plt.scatter(
                projection[selector, 0], 
                projection[selector, 1], 
                color = scalar_map.to_rgba(label),
                label = "cluster {}".format(label),
                edgecolors = "black",
                linewidth = 0.5
            )
        plt.legend()
        plt.savefig(file_name, dpi="figure", format="png")
    

class ClusterWrapper_spectral(ClusterWrapper):
    """ Wrapper for methods about Spectral Clustering
    """
    def __init__(self, M: np.ndarray, max_cluster: int = 16) -> None:
        """ Constructor

        :param M: similarity matrix, normalized and symmetric.
        :param max_cluster: Upper limit of the number of clusters. No less than 2.
        """
        super().__init__(M)
        assert (max_cluster >= 2) , "Upper limit of the number of clusters must be no less than 2"
        self._max_cluster = max_cluster
        self.attempts_cnt = 0
        self.best_silhouette_score = -np.inf
        self.continuous_decrease_cnt = 0

    def do_clustering(self):
        """ Implementation of Spectral Clustering

        Do the clustering job, enumerate all possible number of clusters (begin at 1), 
        and save the clustering result which scores the highest on silhouette score.

        The correct value of silhouette score for 1 cluster should be zero according to
        https://stackoverflow.com/questions/62793786/why-does-scikit-learn-silhouette-score-return-an-error-for-1-cluster
         and https://en.wikipedia.org/wiki/Silhouette_(clustering) and 
        `Rousseeuw, Peter J. "Silhouettes: a graphical aid to the interpretation and validation of cluster analysis." Journal of computational and applied mathematics 20 (1987): 53-65.`.

        `silhouette_score` in `scikit-learn` (v 0.24.2) does not work with 
        one cluster and gives an unexpected error says: 
        `ValueError: Number of labels is 1. Valid values are 2 to n_samples - 1 (inclusive)`

        So if we try to enumerate all possible number of clusters begin at 1,
        the `silhouette_score` we get first should be 0. And when the following
        for-loop ends, we would get only one cluster if `silhouette_score`  is still 0.

        However, this result should be treated with caution because
        there may be such a possibility:
        0 => - => - (for-loop break) => + => + => ...

        What's more, `scikit-learn` says that its Silhouette Coefficient
        is only defined if number of labels is `2 <= n_labels <= n_samples - 1`
        """
        distance_mat = 1 - self._similarity_mat

        # Pretend to put all into one cluster
        self.attempts_cnt = 1
        self.prev_silhouette_score = self.best_silhouette_score # previous = -np.inf
        self.this_silhouette_score = 0 # one cluster so the score=0
        self.best_silhouette_score = 0 # -np.inf < 0 so update the best
        self.continuous_decrease_cnt = 0 # reset the counter
        self.prev_silhouette_score = self.this_silhouette_score # save this score for next round

        # We should avoid this kind of risk:
        # 0 => - => - => + => + => ...
        # If we stop trying when a second consecutive decrease 
        # on silhouette score is encountered, we will stop after
        # the second minus value. However we may still have better
        # result if we kept trying. So we set a flag here and use 
        # it later to avoid such risk.
        last_score_is_zero = True

        best_round = None
        for N in range(2, 1 + self._max_cluster):
            ''' ROUND BEGIN '''
            # Record the number of attempts
            self.attempts_cnt = N
            # Run clustering process
                
            clustering = \
                cluster.SpectralClustering(
                    n_clusters = N,
                    assign_labels = "discretize",
                    random_state = 0,
                    affinity = 'precomputed',
                    n_jobs = 1,
                    verbose = False
                ).fit(self._similarity_mat)

            # Get clustering result and calculate the corresponding silhouette score.
            predicted = clustering.labels_
            self.this_silhouette_score = \
                metrics.silhouette_score(
                    distance_mat,
                    predicted,
                    metric='precomputed'
                )

            if not (0 == self.prev_silhouette_score):
                last_score_is_zero = False

            if self.this_silhouette_score >= self.prev_silhouette_score:
                # If the score in current round larger than previous round,
                # we should reset the counter of decrease
                self.continuous_decrease_cnt = 0
                if self.this_silhouette_score > self.best_silhouette_score:
                    # If a larger `n_clusters` leads to the same silhouette score 
                    # as the smaller one, we prefer the smaller `n_clusters`.
                    # So use `>` rather than `>=` here
                    self.best_silhouette_score = self.this_silhouette_score
                    self.clusters_result = predicted
                    best_round = N
            else:
                if not last_score_is_zero:
                    self.continuous_decrease_cnt += 1

            # Print the silhouette score of this round
            print("Round {}: silhouette score is {}".format(self.attempts_cnt, self.this_silhouette_score))

            # If a second consecutive decrease on silhouette score is encountered, 
            # stop immediately with the current best `self.clusters_result`.
            if self.continuous_decrease_cnt == 2:
                break

            # Save this score for next round
            self.prev_silhouette_score = self.this_silhouette_score
            ''' ROUND END '''
        
        print("Best -> Round {}".format(best_round))
        if (0 == self.best_silhouette_score):
            # Only one cluster in the result
            self.clusters_result = \
                self.best_predicted_result = \
                    np.zeros(len(self._similarity_mat))
            print("Be careful: only 1 cluster in the result!")


class ConvergerWrapper:
    """ Wrapper for methods about detecting outliers
    """
    def __init__(self, M :np.ndarray, outlier_ratio :float =0.05) -> None :
        """ Constructor

        :param M: similarity matrix, normalized and symmetric.
        :param outlier_ratio: When the proportion of outliers is more or equal than `outlier_ratio`, 
                              we assert that the outlier detection algorithm made a mistake, 
                              which means all samples should be clustered.
        """
        self._similarity_mat = M
        self._outlier_ratio = outlier_ratio
        self.outliers_result = None

    def do_converging(self):
        """ Implementation of the converger

        Using Isolation Forest for outlier detection. The result
        `self.outliers_result` would be `None` which indicates the 
        proportion of outliers is more or equal than `outlier_ratio`, or
        a `numpy.ndarray` whose length equals the number of samples and
        in which element value -1 indicates an outlier and 1 for normal.
        """
        if (0.0 == self._outlier_ratio):
            # Obvioulsy ratio=0 indicates that the user
            # hope all samples should be clustered or
            # intends not to check outliers but still 
            # wants to keep consistency of invocation procedure
            return
        
        distance_mat = 1 - self._similarity_mat
        iso = \
            ensemble.IsolationForest(
                contamination='auto', random_state=42
            )
        outlier_flags = iso.fit(distance_mat).predict(distance_mat)

        # When the proportion of outliers is more or equal than `_outlier_ratio`, 
        # we assert that the outer detection algorithm made a mistake, 
        # which means all samples should be clustered. Otherwise those outliers
        # could be remove so that they won't be clustered later.
        number_of_outliers = len(list(filter(lambda x: x == -1, outlier_flags)))
        number_of_samples = len(outlier_flags)
        if number_of_outliers >= np.floor(number_of_samples * self._outlier_ratio):
            return
        else:
            self.outliers_result = outlier_flags


def Calculate__TFPN(result_lst :typing.List[str], truth_lst :typing.List[str]) -> typing.Tuple[int,int,int,int] :
    """ Calculate TP, TN, FP, FN

    https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html

    An alternative to this information-theoretic interpretation of clustering is to 
    view it as a series of decisions, one for each of the $N(N-1)/2$ pairs of documents 
    in the collection. We want to assign two documents to the same cluster if and only 
    if they are similar. 

    A TP (true positive) decision assigns two similar documents to the same cluster.
    A TN (true negative) decision assigns two dissimilar documents to different clusters.
    There are two types of errors we can commit.
    A (FP) decision assigns two dissimilar documents to the same cluster.
    A (FN) decision assigns two similar documents to different clusters.
    """
    assert (len(result_lst) == len(truth_lst)) , "Unmatched length!"
    L  = len(result_lst)
    SS_TP = 0 # Same cluster & Same class
    DD_TN = 0 # Diff cluster & Diff class 
    SD_FP = 0 # Same cluster & Diff class
    DS_FN = 0 # Diff cluster & Same class

    for i in range(L):
        for j in range(1+i , L):
            if   (result_lst[i] == result_lst[j]) and (truth_lst[i] == truth_lst[j]):
                # same cluster, same class
                SS_TP += 1
            elif (result_lst[i] == result_lst[j]) and (truth_lst[i] != truth_lst[j]):
                # same cluster, diff class
                SD_FP += 1
            elif (result_lst[i] != result_lst[j]) and (truth_lst[i] == truth_lst[j]):
                # diff cluster, same class
                DS_FN += 1
            elif (result_lst[i] != result_lst[j]) and (truth_lst[i] != truth_lst[j]):
                # diff cluster, diff class
                DD_TN += 1

    return SS_TP, DD_TN, SD_FP, DS_FN


def Calculate__Precision(result_lst :typing.List[str], truth_lst :typing.List[str]) -> float :
    """ Calculate Precison

    https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html
    """
    TP, TN, FP, FN = Calculate__TFPN(result_lst, truth_lst)
    return TP/(TP+FP)


def Calculate__Recall(result_lst :typing.List[str], truth_lst :typing.List[str]) -> float :
    """ Calculate Precison

    https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html
    """
    TP, TN, FP, FN = Calculate__TFPN(result_lst, truth_lst)
    return TP/(TP+FN)


def Calculate__Rand_Index(result_lst :typing.List[str], truth_lst :typing.List[str]) -> float :
    """
    Calculate Rand Index

    https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html
    """
    TP, TN, FP, FN = Calculate__TFPN(result_lst, truth_lst)
    return (TP+TN)/(TP+FP+FN+TN)


def Calculate__F_Measure(result_lst :typing.List[str], truth_lst :typing.List[str], beta :float =1.0) -> float :
    """ Calculate F measure

    https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-clustering-1.html

    The Rand index gives equal weight to false positives and false negatives. Separating 
    similar documents is sometimes worse than putting pairs of dissimilar documents 
    in the same cluster. We can use the F measure measuresperf to penalize false negatives 
    more strongly than false positives by selecting a value $\beta > 1$, thus giving more 
    weight to recall. In information retrieval, evaluating clustering with $F$ has the advantage 
    that the measure is already familiar to the research community.
    """
    P = Calculate__Precision(result_lst, truth_lst)
    R = Calculate__Recall(result_lst, truth_lst)
    return (1 + beta**2) * P * R / (R + P * beta**2)


def Calculate__Purity(result_lst :typing.List[str], truth_lst :typing.List[str]) -> float :
    """ Calculate Purity

    REF:
    `Amigó, Enrique, et al. "A comparison of extrinsic clustering evaluation metrics based on formal constraints." Information retrieval 12.4 (2009): 461-486.`

    The most popular measures for cluster evaluation are Purity, Inverse Purity
    and their harmonic mean (F measure). Purity [Zhao and Karypis, 2001] focuses
    on the frequency of the most common category into each cluster. To compute purity ,
    each cluster is assigned to the class which is most frequent in the cluster, and then
    the accuracy of this assignment is measured by counting the number of correctly assigned
    documents and dividing by N. 

    Accuracy EQUALS Purity.
    """
    assert (len(result_lst) == len(truth_lst)) , "Unmatched length!"
    N = len(result_lst)

    # Label each item in the list with an integer starting from 0 and represented result & truth as clusters.
    result = {}
    truth  = {}
    for i in range(N):
        if result_lst[i] not in result:
            result[result_lst[i]] = set([i])
        else:
            result[result_lst[i]].add(i)
        
        if truth_lst[i] not in truth:
            truth[truth_lst[i]] = set([i])
        else:
            truth[truth_lst[i]].add(i)
    
    # Traverse each cluster in result, find which class in truth is most frequent in the cluster.
    all_sum = 0
    for this_cluster in result:
        max_cnt = 0
        for this_class in truth:
            coincidence = len(result[this_cluster] & truth[this_class])
            if coincidence > max_cnt:
                max_cnt = coincidence
        all_sum += max_cnt
    
    return all_sum/N


def Calculate__Inverse_Purity(result_lst :typing.List[str], truth_lst :typing.List[str]) -> float :
    """ Calculate Inverse Purity

    REF:
    `Amigó, Enrique, et al. "A comparison of extrinsic clustering evaluation metrics based on formal constraints." Information retrieval 12.4 (2009): 461-486.`

    The most popular measures for cluster evaluation are Purity, Inverse Purity
    and their harmonic mean (F measure). Purity penalizes the noise in a cluster, 
    but it does not reward grouping items from the same category together; if we 
    simply make one cluster per item, we reach trivially a maximum purity value. 
    Inverse Purity focuses on the cluster with maximum recall for each category.
    """
    return Calculate__Purity(truth_lst, result_lst)


if __name__ == "__main__":
    pass