import argparse
import json
import logging
import os
import re
import time
import typing
import numpy
import cluster
import DCFG
import GKA

logging.basicConfig(
    level = logging.DEBUG,
    format = '%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s'
)

class MakeCluster:
    """ Wrapper of methods about trace file clustering
    """
    def __init__(
        self,
        trace_lst     :typing.List[str],
        graph         :typing.Type[DCFG.DCFG],
        kernel        :typing.Type[GKA.GKA],
        method        :typing.Type[cluster.ClusterWrapper],
        outlier_ratio :float =0.0,
        max_cluster   :int =16
    ) -> None :
        """ Constructor

        All files in `trace_file_list` will be clustered.

        :param trace_lst:  trace file path string list
        :param graph:  graph type from `DCFG.py`
        :param kernel:  graph kernel algorithm from `GKA.py`
        :param method:  clustering algorithm wrapper from `cluster.py`
        """
        self._graph  = graph
        self._kernel = kernel
        self._method = method

        assert (len(trace_lst) > 2) , "trace items are not enough!"
        self._trace_lst = trace_lst
        self._trace_tag = ["" for i in range(len(trace_lst))]

        self.outlier = outlier_ratio
        self.cluster_num_limit = max_cluster

    def _build_dcfg_lst(self) -> typing.List[DCFG.DCFG] :
        """ Build DCFG objects from `self._trace_lst`
        """
        objs = []
        for t in self._trace_lst:
            o = self._graph(t)
            o.construct_dcfg()
            objs.append(o)
        return objs
    
    def _get_dcfg_all(self, objs :typing.List[DCFG.DCFG]) -> list :
        """ Get DCFG data list from DCFG objects list
        """
        return [o.return_dcfg()  for o in objs]

    def _build_similarity_matrix(self, g_list :list) -> numpy.ndarray :
        """ Build Similarity Matrix

        :param g_list: Graph list
        """
        if (GKA.GKA_GraKeL == self._kernel):
            # Parallelization
            K = self._kernel(isVerbose=False, setJoblib=8)
        else:
            K = self._kernel()
        K.graph_lst = g_list

        return K.get_matrix()

    def launcher(self) -> list :
        """ Launcher for clustering those trace files

        Cluster-ID String for each trace file will be saved in 
        list `self._trace_tag` with the same order as `self._trace_lst` and 
        `self._trace_tag` will be returned finally by this method.
        """

        '''----- 1st Build DCFG -----'''
        logging.info("Building DCFG objects")
        dcfg_obj_lst = self._build_dcfg_lst()
        
        logging.info("Building DCFG graphs")
        dcfg_all_origin = self._get_dcfg_all(dcfg_obj_lst)

        '''----- 2nd Build Similarity Matrix -----'''
        logging.info("Building similarity matrix")
        mat_all_origin = self._build_similarity_matrix(dcfg_all_origin)
        
        '''----- 3rd Check the outliers -----'''
        logging.info("Checking outliers")
                
        checker = cluster.ConvergerWrapper(mat_all_origin, outlier_ratio=self.outlier)
        checker.do_converging()

        if (None == checker.outliers_result):
            logging.info("No outliers were found")
            # No outliers
            mat_all_rm_outlier = mat_all_origin
        else:
            logging.info("Some outliers were found")
            # Have outliers so mark and filter out them (just skip but keep the order)
            dcfg_obj_lst_rm_outlier = []
            for i in range(len(self._trace_lst)):
                if -1 == checker.outliers_result[i]:
                    self._trace_tag[i] = "inf"
                else:
                    dcfg_obj_lst_rm_outlier.append(dcfg_obj_lst[i])
            
            logging.info("Rebuilding similarity matrix")
            mat_all_rm_outlier = \
                self._build_similarity_matrix(self._get_dcfg_all(dcfg_obj_lst_rm_outlier))

        '''----- 4th Clustering -----'''
        logging.info("Do clustering")
        executor = \
            self._method(
                mat_all_rm_outlier, 
                max_cluster = self.cluster_num_limit)
        executor.do_clustering()

        '''----- 5th Save the results -----'''
        # Pre-check to reduce the number of comparison operations
        if "inf" not in self._trace_tag:
            # no outliers so copy directly
            for i in range(len(self._trace_lst)):
                self._trace_tag[i] = str(executor.clusters_result[i])
        else:
            # the tags do not include outliers
            tag_this = 0
            for i in range(len(self._trace_lst)):
                if "inf" == self._trace_tag[i]:
                    continue
                else:
                    self._trace_tag[i] = str(executor.clusters_result[tag_this])
                    tag_this += 1

        return self._trace_tag


def MakeTruth(trace_lst :typing.List[str], regex_str :str) -> typing.List[str] :
    """ Get benchmark tag for each trace file in the file path list

    :param regex_str: Regex for searching benchmark tags
    """
    tags = []
    pattern = re.compile(regex_str)
    for T in trace_lst:
        matches = pattern.findall(T)
        assert (len(matches) != 0) , "CANNOT find Benchmark tags. FILE: %s"%(T)
        if (len(matches) > 1):
            logging.warning("Found dupulicate tags, used the first one. FILE: %s"%(T))
        tags.append(matches[0])
    return tags


def MakeScoresReport(rlst :typing.List[str], tlst :typing.List[str]) -> dict :
    """ Make a report about those scores as a dict compatible with JSON

     :param rlist: result list
     :param tlist: truth list
    """
    scores = {}
    scores["Precision"     ] = cluster.Calculate__Precision     (rlst, tlst)
    scores["Recall"        ] = cluster.Calculate__Recall        (rlst, tlst)
    scores["F-measure"     ] = cluster.Calculate__F_Measure     (rlst, tlst)
    scores["Purity"        ] = cluster.Calculate__Purity        (rlst, tlst)
    scores["Inverse Purity"] = cluster.Calculate__Inverse_Purity(rlst, tlst)
    return scores


def MakeBaseReport(trace_lst :typing.List[str], result_lst :typing.List[str]) -> dict :
    """ Make a report about the results as a dict compatible with JSON

    The outliers will be marked specially in the report if they exist.
    """
    groups = {}

    if "inf" not in result_lst:
        # get the groups
        for i in range(len(result_lst)):
            if result_lst[i] not in groups:
                groups[result_lst[i]] = [trace_lst[i]]
            else:
                groups[result_lst[i]].append(trace_lst[i])
        # make report dict
        return {"Result":groups}
    
    else:
        # get the groups with special treatment for outliers
        olist = [] # outlier list
        for i in range(len(result_lst)):
            res = result_lst[i]
            if "inf" == res:
                olist.append(trace_lst[i])
            else:
                if res not in groups:
                    groups[res] = [trace_lst[i]]
                else:
                    groups[res].append(trace_lst[i])
        # make report dict
        return {"Result":groups, "Outlier":olist}


def MakeFullReport(trace_lst :typing.List[str], result_lst :typing.List[str], truth_lst  :typing.List[str]) -> dict :
    """ Make a full report about the results & scores as a dict compatible with JSON

    The outliers will be marked specially in the report if they exist.
    Of course calculation of scores will not involve outliers.
    """
    groups = {}

    if "inf" not in result_lst:
        # get the groups
        for i in range(len(result_lst)):
            if result_lst[i] not in groups:
                groups[result_lst[i]] = [trace_lst[i]]
            else:
                groups[result_lst[i]].append(trace_lst[i])
        # make report dict
        return {"Result":groups, "Score":MakeScoresReport(result_lst, truth_lst)}
    
    else:
        # get the groups with special treatment for outliers
        odict = {} # outlier dict grouped by benchmark
        rlist = [] # result list without outliers
        tlist = [] # truth list without outliers
        for i in range(len(result_lst)):
            res = result_lst[i]
            if "inf" == res:
                if truth_lst[i] not in odict:
                    odict[truth_lst[i]] = [trace_lst[i]]
                else:
                    odict[truth_lst[i]].append(trace_lst[i])
            else:
                rlist.append(res)
                tlist.append(truth_lst[i])
                if res not in groups:
                    groups[res] = [trace_lst[i]]
                else:
                    groups[res].append(trace_lst[i])
        # make report dict
        return {"Result":groups, "Outlier":odict, "Score":MakeScoresReport(rlist, tlist)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-i", \
                        help="""
                            Traces root directory in which the program
                            search for trace file recursively. EVERY 
                            file is regarded as a trace file. So be
                            careful about your directory.
                        """,
                        type=str,
                        required=True)
    
    parser.add_argument("-o", \
                        help=\
                            """
                            The directory to save json report. The report
                            file name would be a unix timestamp (ms) with 
                            'report_' as its prefix.
                        """,
                        type=str,
                        required=True)
    
    parser.add_argument("--benchmark", \
                        help="""
                            Regex string for searching benchmark tag in file path.
                            The first found will be used. If this parameter
                            are set, the program will run the evaluation process
                            with these ground-truth tags.
                        """, \
                        type=str,
                        default="",
                        required=False)
    
    parser.add_argument("--outlier", \
                        help="""
                            If a valid value ([0.0,1.0]) is passed, we will use
                            Isolation Forest for outlier detection and 
                            the value will be regarded as a ratio, which
                            means when the proportion of outliers is more or
                            equal than the ratio, we assert that all samples 
                            should be clustered. Of course value 0 means
                            no outlier detection (default).
                        """,
                        type=float,
                        default=0.0,
                        required=False
    )

    parser.add_argument("--cluster_limit", \
                        help="""
                            Maximum number of clusters as a limit.
                            (No less than 2 & Default is 16)
                        """,
                        type=int,
                        default=16,
                        required=False
    )

    args = parser.parse_args()

    root_dir = args.i
    repo_dir = args.o

    if (args.outlier < 0.0 or args.outlier > 1.0):
        raise Exception("Invalid outlier ratio")

    # Get trace file
    T_file = []
    for root, dirs, files in os.walk(root_dir, followlinks=True):
        for name in files:
            T_file.append(os.path.join(root, name))
    logging.info("Found {} files in {}".format(len(T_file),root))

    # Get benchmark
    if ("" == args.benchmark):
        in_benchmark = False
    else:
        in_benchmark = True
        benchmark_regex = args.benchmark
    
    if in_benchmark:
        T_mark = MakeTruth(T_file, benchmark_regex)
        logging.info("Benchmark has been built.")

    # Get the results
    T_result = MakeCluster(
        T_file,
        DCFG.DCFG_NX,
        GKA.GKA_GraKeL,
        cluster.ClusterWrapper_spectral,
        outlier_ratio = args.outlier,
        max_cluster   = args.cluster_limit
    ).launcher()

    # Get the report
    logging.info("Generating report")
    if in_benchmark:
        T_report = MakeFullReport(T_file, T_result, T_mark)
    else:
        T_report = MakeBaseReport(T_file, T_result)

    # Make a brief report
    logging.info("Report preview:")
    if in_benchmark:
        print(json.dumps(T_report["Score"], sort_keys=True, indent=4, separators=(',', ': ')))
    if "Outlier" in T_report:
        print(len(T_report["Outlier"]) , "outliers in total")
    print(len(T_report["Result"]), "clusters in total")

    # Save the report to file
    report_path = os.path.join(repo_dir, "report_{}".format(int(1000*time.time())))
    logging.info("Saving report: {}".format(report_path))
    with open(report_path, mode="w") as f:
        f.write(json.dumps(T_report, sort_keys=True, indent=4, separators=(',', ': ')))

    logging.info("All jobs have been done")