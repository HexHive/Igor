import argparse
from graphviz import Digraph
import os

class Painter():
    def __init__(self, original_poc=None, decreased_poc=None, output_dir=None, paint_mode=0):
        self._cfg_all = []
        self._poc_ori = original_poc
        self._poc_de = decreased_poc
        self._out_dir = output_dir
        self._edges_ori = None      # edges executed by original poc
        self._edges_de = None      # edges executed by decreased poc

        # 0 is compare graph, 1 is single graph, 2 is calculate graph difference only
        self._paint_mode = paint_mode

        self._inter_edge_cnt = 0
        self._pruned_edge_cnt = 0
        self._new_edge_cnt = 0
        self._inter_node_cnt = 0
        self._pruned_node_cnt = 0
        self._new_node_cnt = 0



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

    @staticmethod
    def _add_width_for_graph(trace_file, dot_item):
        edges_width = {}

        with open(trace_file, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                if (front_node, next_node) in edges_width.keys():
                    edges_width[(front_node, next_node)] += 1
                else:
                    edges_width[(front_node, next_node)] = 1

            for edge in edges_width.keys():
                width = Painter._lookup_bucket(edges_width[edge])
                dot_item.edge(str(edge[0]), str(edge[1]), style='setlinewidth(%d)' % width)

    @staticmethod
    def _parse_edges_from_trace(trace_file):
        edges = set()

        if trace_file is None:
            print("Weird!\n")

        with open(trace_file, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                edge = (front_node, next_node)
                edges.add(edge)

        return edges

    @staticmethod
    def _parse_nodes_from_trace(trace_file):
        nodes = set()

        with open(trace_file, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                nodes.add(front_node)
                nodes.add(next_node)

        return nodes

    @staticmethod
    def _different_edges_between_traces(trace_ori, trace_de):
        edges_ori = set()
        edges_de = set()

        inter_edges = set()      # intersection of A and B
        pruned_edges = set()     # A - (A & B)
        new_edges = set()        # B - A

        edges_ori = Painter._parse_edges_from_trace(trace_ori)
        edges_de = Painter._parse_edges_from_trace(trace_de)

        inter_edges = edges_ori & edges_de
        pruned_edges = edges_ori - (edges_ori & edges_de)
        new_edges = edges_de - edges_ori

        return inter_edges, pruned_edges, new_edges

    @staticmethod
    def _different_nodes_between_traces(trace_ori, trace_de):
        nodes_ori = set()
        nodes_de = set()

        inter_nodes = set()  # intersection of A and B
        pruned_nodes = set()  # A - (A & B)
        new_nodes = set()  # B - A

        nodes_ori = Painter._parse_nodes_from_trace(trace_ori)
        nodes_de = Painter._parse_nodes_from_trace(trace_de)

        inter_nodes = nodes_ori & nodes_de
        pruned_nodes = nodes_ori - (nodes_ori & nodes_de)
        new_nodes = nodes_de - nodes_ori

        return inter_nodes, pruned_nodes, new_nodes

    @staticmethod
    def _draw_compare_graph_edge(dot_item, inter_edges, pruned_edges, new_edges):
        """
        intersection will be black
        pruned edges will be red
        new edges will be green
        """
        for edge in inter_edges:
            dot_item.edge(str(edge[0]), str(edge[1]), color="black")

        for edge in pruned_edges:
            dot_item.edge(str(edge[0]), str(edge[1]), color="red")

        for edge in new_edges:
            dot_item.edge(str(edge[0]), str(edge[1]), color="green")

        return dot_item

    @staticmethod
    def _draw_compare_graph_node(dot_item, inter_nodes, pruned_nodes, new_nodes):
        """
        intersection will be black
        pruned nodes will be red
        new nodes will be green
        """
        for node in pruned_nodes:
            dot_item.node(str(node), color="red", style="filled", fillcolor="red")

        for node in new_nodes:
            dot_item.node(str(node), color="green", style="filled", fillcolor="green")

        return dot_item

    def draw_graph(self):
        dot = Digraph()

        with open(self._poc_ori, 'rb') as f:
            content = f.readlines()
            for i in range(len(content) - 1):
                front_node = int(content[i].decode('utf-8', 'ignore').split('\n')[0], 16)
                next_node = int(content[i + 1].decode('utf-8', 'ignore').split('\n')[0], 16)

                dot.node(str(front_node), str(front_node))
                dot.node(str(next_node), str(next_node))

        if self._paint_mode == 0:
            inter_edges, pruned_edges, new_edges = Painter._different_edges_between_traces(self._poc_ori, self._poc_de)
            inter_nodes, pruned_nodes, new_nodes = Painter._different_nodes_between_traces(self._poc_ori, self._poc_de)

            dot = Painter._draw_compare_graph_edge(dot, inter_edges, pruned_edges, new_edges)
            dot = Painter._draw_compare_graph_node(dot, inter_nodes, pruned_nodes, new_nodes)
        elif self._paint_mode == 1:
            Painter._add_width_for_graph(self._poc_ori, dot)
        elif self._paint_mode == 2:
            # calculate number of intersection & pruned & new edges/nodes only
            inter_edges, pruned_edges, new_edges = Painter._different_edges_between_traces(self._poc_ori, self._poc_de)
            inter_nodes, pruned_nodes, new_nodes = Painter._different_nodes_between_traces(self._poc_ori, self._poc_de)
            self._inter_edge_cnt = len(inter_edges)
            self._inter_node_cnt = len(inter_nodes)
            self._pruned_edge_cnt = len(pruned_edges)
            self._pruned_node_cnt = len(pruned_nodes)
            self._new_edge_cnt = len(new_edges)
            self._new_node_cnt = len(new_nodes)

            return          # we don't want to paint in this mode!
        else:
            pass

        file_name = self._poc_ori.split("id:")[1].split("-")[0] + '.gv'
        dot.render(file_name)

    def print_graph_diff(self):
        # print("intersection edge count: %d\n" % self._inter_edge_cnt)
        # print("pruned edge count: %d\n" % self._pruned_edge_cnt)
        # print("new edge count: %d\n" % self._new_edge_cnt)
        # print("intersection node count: %d\n" % self._inter_node_cnt)
        # print("pruned node count: %d\n" % self._pruned_node_cnt)
        # print("new node count: %d\n" % self._new_node_cnt)
        shrink_rate = self._pruned_edge_cnt/(self._inter_edge_cnt + self._pruned_edge_cnt)
        poc_id = self._poc_de.split("id:")[1].split("-")[0]
        print("poc {} ------------- decrease rate: {}\n".format(poc_id, shrink_rate))

    @staticmethod
    def get_diff_statics(ori_trace, de_trace):
        inter_edges, pruned_edges, new_edges = Painter._different_edges_between_traces(ori_trace, de_trace)
        inter_nodes, pruned_nodes, new_nodes = Painter._different_nodes_between_traces(ori_trace, de_trace)
        inter_edge_cnt = len(inter_edges)
        inter_node_cnt = len(inter_nodes)
        pruned_edge_cnt = len(pruned_edges)
        pruned_node_cnt = len(pruned_nodes)
        new_edge_cnt = len(new_edges)
        new_node_cnt = len(new_nodes)

        return inter_edge_cnt, inter_node_cnt, pruned_edge_cnt, pruned_node_cnt, new_edge_cnt, new_node_cnt

    def get_graph_diff(self):
        # print("intersection edge count: %d\n" % self._inter_edge_cnt)
        # print("pruned edge count: %d\n" % self._pruned_edge_cnt)
        # print("new edge count: %d\n" % self._new_edge_cnt)
        # print("intersection node count: %d\n" % self._inter_node_cnt)
        # print("pruned node count: %d\n" % self._pruned_node_cnt)
        # print("new node count: %d\n" % self._new_node_cnt)
        shrink_rate = self._pruned_edge_cnt / (self._inter_edge_cnt + self._pruned_edge_cnt)
        if "id" not in self._poc_de:
            poc_id = self._poc_ori.split(".")[1]
        else:
            poc_id = self._poc_de.split("id:")[1].split(",")[0]
            poc_id = "id:" + poc_id

        return poc_id, shrink_rate

    def show_shrink_rate_wrapper(self):
        for _, _, traces in os.walk(self._traces_dir):
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
    parser.add_argument("-i", help="original poc path")
    parser.add_argument("-d", help="decreased poc path")
    parser.add_argument("-o", help="output directory")
    parser.add_argument("-m", help="painting mode", type=int, default=0)

    args = parser.parse_args()

    P = Painter(args.i, args.d, args.o, args.m)

    if args.m == 0:
        P.draw_graph()
    elif args.m == 2:
        P.draw_graph()
        P.print_graph_diff()
    else:
        pass

    print("Finished!")


if __name__ == "__main__":
    main()