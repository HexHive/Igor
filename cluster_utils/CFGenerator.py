#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import argparse
import networkx as nx
from graphviz import Digraph
import os
import pygraphviz as pgv
from grakel.utils import graph_from_networkx
from grakel.kernels import ShortestPath
from grakel.kernels import RandomWalk
from grakel.kernels import WeisfeilerLehman, VertexHistogram, NeighborhoodSubgraphPairwiseDistance
from grakel.kernels import PropagationAttr
import matplotlib.pyplot as plt

class CFGenerator():
    def __init__(self, traces_dir=None, kernel_mode=None, attribute_mode=None, draw_graph=None):
        self._cfg_all = []
        self._traces_dir = traces_dir
        self._cfg_similarity_matrix = None
        self._kernel_mode = kernel_mode
        self._graph_similarity_matrix = None
        self._attribute_mode = attribute_mode
        self._draw_graph = draw_graph
        pass

    @staticmethod
    def _gen_one_CFG(trace):
        G = nx.DiGraph()
        cfg_edges = set()

        with open(trace, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                edge = (front_node, next_node)
                cfg_edges.add(edge)

        G.add_edges_from(cfg_edges)

        return G


    '''
    [0]           = 0,
    [1]           = 1,
    [2]           = 2,
    [3]           = 4,
    [4 ... 7]     = 8,
    [8 ... 15]    = 16,
    [16 ... 31]   = 32,
    [32 ... 127]  = 64,
    [128 ... 255] = 128
    '''
    @staticmethod
    def _lookup_bucket(hit_counts):
        if hit_counts == 1:
            return 1
        elif hit_counts == 2:
            return 2
        elif hit_counts == 3:
            return 3
        elif hit_counts == 3:
            return 3
        elif (hit_counts >= 4) and (hit_counts <= 7):
            return 4
        elif (hit_counts >= 8) and (hit_counts <= 15):
            return 5
        elif (hit_counts >= 16) and (hit_counts <= 31):
            return 6
        elif (hit_counts >= 32) and (hit_counts <= 127):
            return 7
        elif (hit_counts >= 128) and (hit_counts <= 255):
            return 8
        else:
            return 9
    '''
    Every time one edge was execute in trace, the edge_width++
    '''
    def _get_edges_width(self, trace):
        edges_width = {}
        with open(trace, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                if (front_node, next_node) in edges_width.keys():
                    edges_width[(front_node, next_node)] += 1
                else:
                    edges_width[(front_node, next_node)] = 1

        return edges_width

    @staticmethod
    def _draw_graph(trace):
        dot = Digraph()
        dot.engine = 'fdp'
        edges_width = {}

        with open(trace, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                dot.node(str(front_node), str(front_node))
                dot.node(str(next_node), str(next_node))

                if (front_node, next_node) in edges_width.keys():
                    edges_width[(front_node, next_node)] += 1
                else:
                    edges_width[(front_node, next_node)] = 1

        for edge in edges_width.keys():
            width = CFGenerator._lookup_bucket(edges_width[edge])
            dot.edge(str(edge[0]), str(edge[1]), style='setlinewidth(%d)' % width)

        file_name = trace.split("id:")[1].split("-")[0] + '.gv'
        dot.render(file_name)

    # Calculate the similarity between two CFG
    # Will support multiple algorithm in the future!
    def cfg_similarity(self):
        # Transforms list of NetworkX graphs into a list of GraKeL graphs
        G = graph_from_networkx(self._cfg_all)

        if self._kernel_mode == 0:
            # Uses the RandomWalk kernel to generate the kernel matrices
            # Hint: the larger the graph is, the smaller the lamda should be
            gk = RandomWalk(normalize=True, lamda=0.001)
            K = gk.fit_transform(G)
            self._graph_similarity_matrix = K
        elif self._kernel_mode == 1:
            # Uses the shortest path kernel to generate the kernel matrices
            gk = ShortestPath(with_labels=False, normalize=True)
            K = gk.fit_transform(G)
            self._graph_similarity_matrix = K
        elif self._kernel_mode == 2:
            # Uses the Weisfeiler-Lehman subtree kernel to generate the kernel matrices
            # WL need labeled graph, so we have to add label for each node!
            cfg_all = self._cfg_all
            for graph in cfg_all:
                for node in graph.nodes():
                    nx.set_node_attributes(graph, {node:'a'}, 'label')   # we add same label for every node1

            G_wl = graph_from_networkx(cfg_all, node_labels_tag='label')
            gk = WeisfeilerLehman(n_iter=4, base_graph_kernel=VertexHistogram, normalize=True)
            K = gk.fit_transform(G_wl)
            self._graph_similarity_matrix = K
        elif self._kernel_mode == 3:
            # This is a mode for test, we want to know whether we could get better result if we add graph with attribute
            # We need attributed graph
            cfg_all = self._cfg_all
            if self._attribute_mode == 0:
                G_wl = graph_from_networkx(cfg_all, node_labels_tag='label', edge_labels_tag='hit_counts')
                gk = WeisfeilerLehman(n_iter=1, base_graph_kernel=VertexHistogram, normalize=True)
                K = gk.fit_transform(G_wl)
                self._graph_similarity_matrix = K
        elif self._kernel_mode == 4:
            # Neighborhood Subgraph Pairwise Distance mode
            cfg_all = self._cfg_all
            G_wl = graph_from_networkx(cfg_all, node_labels_tag='label', edge_labels_tag='hit_counts')
            gk = NeighborhoodSubgraphPairwiseDistance(normalize=True)
            K = gk.fit_transform(G_wl)
            self._graph_similarity_matrix = K
        else:
            pass

    def get_similarity_matrix(self):
        return self._graph_similarity_matrix

    def _add_label_for_graph(self, graph, trace):
        for node in graph.nodes():
            nx.set_node_attributes(graph, {node: node}, 'label')  # we add attribute according to caller address

        edge_width = self._get_edges_width(trace)

        nx.set_edge_attributes(graph, name='hit_counts', values=edge_width)

    def gen_CFG_wrapper(self):
        for _, _, traces in os.walk(self._traces_dir):
            # Sort the file list, making sure that the similarity matrix is ordered according to sorted file list.
            traces.sort()
            for trace in traces:
                trace_path = os.path.join(self._traces_dir, trace)

                if self._draw_graph == 1:
                    self._draw_graph(trace_path)
                else:
                    one_cfg = self._gen_one_CFG(trace_path)
                    self._add_label_for_graph(one_cfg, trace_path)
    
                    self._cfg_all.append(one_cfg)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", help="traces directory")
    parser.add_argument("-k", help="kernel mode", type=int, default=0)
    parser.add_argument("-a", help="add attribute mode", type=int, default=0)
    parser.add_argument("-d", help="draw control flow graph or not", type=int, default=0)

    args = parser.parse_args()

    C = CFGenerator(args.t, args.k, args.a, args.d)
    C.gen_CFG_wrapper()
    C.cfg_similarity()

    print("Finished!")


if __name__ == "__main__":
    main()


