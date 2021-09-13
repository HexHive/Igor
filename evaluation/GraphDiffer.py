import argparse
import os
from Painter import *

class GraphDiffer():
    def __init__(self, original_poc_dir=None, decreased_poc_dir=None, output_dir=None, need_print=0, need_statics=0):
        self._poc_ori_dir = original_poc_dir
        self._poc_de_dir = decreased_poc_dir
        self._out_dir = output_dir
        self._need_print = need_print
        self._need_statics = need_statics

        self._decrease_rate_all = {}

    def graph_differ_wrapper(self):
        for _, _, ori_traces in os.walk(self._poc_ori_dir):
            for ori_trace in ori_traces:
                ori_trace_path = os.path.join(self._poc_ori_dir, ori_trace)
                trace_id = None
                trace_tail = None

                if "id" not in ori_trace_path:
                    trace_id = ori_trace_path.split(".")[1]
                    trace_tail = ori_trace_path.split(".")[1]
                else:
                    if "," in ori_trace_path:
                        trace_id = ori_trace_path.split("id:")[1].split(",")[0]
                    elif "-" in ori_trace_path:
                        trace_id = ori_trace_path.split("id:")[1].split("-")[0]
                    trace_tail = ori_trace_path[-3::]

                for _, _, de_traces in os.walk(self._poc_de_dir):
                    for de_trace in de_traces:
                        if trace_id == trace_tail:
                            # means we are searching the no id file
                            if "id" in de_trace:
                                continue
                        if (trace_id in de_trace) and (trace_tail in de_trace):
                            de_trace_path = os.path.join(self._poc_de_dir, de_trace)
                            P = Painter(ori_trace_path, de_trace_path, self._out_dir, paint_mode=2)
                            P.draw_graph()
                            if self._need_print == 0:
                                poc_id, shrink_rate = P.get_graph_diff()
                                poc_unique_name = trace_id + "__" + trace_tail
                                self._decrease_rate_all[poc_unique_name] = shrink_rate
                                continue
                            else:
                                P.print_graph_diff()
                                continue

    def _show_prune_statics(self, poc_id):
        ori_trace = GraphDiffer._find_poc_from_dir(self._poc_ori_dir, poc_id)
        de_trace = GraphDiffer._find_poc_from_dir(self._poc_de_dir, poc_id)

        P = Painter()
        inter_edge_cnt, inter_node_cnt, pruned_edge_cnt, pruned_node_cnt, new_edge_cnt, new_node_cnt = P.get_diff_statics(ori_trace, de_trace)

        return inter_edge_cnt, inter_node_cnt, pruned_edge_cnt, pruned_node_cnt, new_edge_cnt, new_node_cnt

    def show_decrease_res(self):
        max_shrink_rate = max(self._decrease_rate_all.values())
        max_shrink_poc = ''
        for poc_id, rate in self._decrease_rate_all.items():
            if rate == max_shrink_rate:
                max_shrink_poc = poc_id

        print("[!]max shrink rate is {}, belongs to poc {}\n".format(max(self._decrease_rate_all.values()), max_shrink_poc))

        # print the statics of decrease
        inter_edge_cnt, inter_node_cnt, pruned_edge_cnt, pruned_node_cnt, new_edge_cnt, new_node_cnt = self._show_prune_statics(max_shrink_poc)

        print("[*]inter_edge_cnt is: \033[1;37m {} \033[0m\n".format(inter_edge_cnt))
        print("[*]inter_node_cnt is: \033[1;37m {} \033[0m\n".format(inter_node_cnt))
        print("[-]pruned_edge_cnt is: \033[1;31m {} \033[0m\n".format(pruned_edge_cnt))
        print("[-]pruned_node_cnt is: \033[1;31m {} \033[0m\n".format(pruned_node_cnt))
        print("[+]new_edge_cnt is: \033[1;32m {} \033[0m\n".format(new_edge_cnt))
        print("[+]new_node_cnt is: \033[1;32m {} \033[0m\n".format(new_node_cnt))

        return max_shrink_poc

    @staticmethod
    def _find_poc_from_dir(dir_path, poc_id):
        for _, _, pocs in os.walk(dir_path):
            for poc in pocs:
                id = poc_id.split("__")[0]
                tail = poc_id.split("__")[1]
                if (id in poc) and (tail in poc):
                    poc_path = os.path.join(dir_path, poc)

                    return poc_path

    def show_decrease_statics(self):
        per_10 = 0
        per_10_20 = 0
        per_20_30 = 0
        per_30_40 = 0
        per_40_50 = 0
        per_50_60 = 0
        per_60_70 = 0
        per_70_80 = 0
        per_80_90 = 0
        per_90_100 = 0
        poc_unexpect = 0

        for rate in self._decrease_rate_all.values():
            if rate <= 0.10:
                per_10 += 1
            elif (rate > 0.10) and (rate <= 0.20):
                per_10_20 += 1
            elif (rate > 0.20) and (rate <= 0.30):
                per_20_30 += 1
            elif (rate > 0.30) and (rate <= 0.40):
                per_30_40 += 1
            elif (rate > 0.40) and (rate <= 0.50):
                per_40_50 += 1
            elif (rate > 0.50) and (rate <= 0.60):
                per_50_60 += 1
            elif (rate > 0.60) and (rate <= 0.70):
                per_60_70 += 1
            elif (rate > 0.70) and (rate <= 0.80):
                per_70_80 += 1
            elif (rate > 0.80) and (rate <= 0.90):
                per_80_90 += 1
            elif (rate > 0.90) and (rate <= 1):
                per_90_100 += 1
            else:
                poc_unexpect += 1

        print("decrease rate (0%,  10%]:  {}\n".format(per_10))
        print("decrease rate (10%, 20%]:  {}\n".format(per_10_20))
        print("decrease rate (20%, 30%]:  {}\n".format(per_20_30))
        print("decrease rate (30%, 40%]:  {}\n".format(per_30_40))
        print("decrease rate (40%, 50%]:  {}\n".format(per_40_50))
        print("decrease rate (50%, 60%]:  {}\n".format(per_50_60))
        print("decrease rate (60%, 70%]:  {}\n".format(per_60_70))
        print("decrease rate (70%, 80%]:  {}\n".format(per_70_80))
        print("decrease rate (80%, 90%]:  {}\n".format(per_80_90))
        print("decrease rate (90%, 100%]: {}\n".format(per_90_100))
        print("decrease rate (100%, ]: {}\n".format(poc_unexpect))

    def dump_shrink_statics(self):
        res_file = "/tmp/shrink_statics"

        with open(res_file, "w") as f:
            content = ""
            for poc, rate in self._decrease_rate_all.items():
                content += "poc: "
                content += poc
                content += ", shrink rate is: "
                content += str(rate)
                content += "\n"

            f.write(content)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", help="original poc directory")
    parser.add_argument("-d", help="decreased poc directory")
    parser.add_argument("-o", help="output directory")
    parser.add_argument("-p", help="want to print to screen or not", type=int, default=0)
    parser.add_argument("-s", help="want to show decrease statics to screen or not", type=int, default=0)

    args = parser.parse_args()

    G = GraphDiffer(args.i, args.d, args.o, args.p, args.s)
    G.graph_differ_wrapper()
    if args.s == 1:
        # only show statics of different decrease rate percentage
        G.show_decrease_statics()
    elif args.s == 2:
        # dump shrink percentage for each poc into a file
        G.dump_shrink_statics()
    else:
        # will draw graphs and show max decrease rate
        most_shrinked_poc = G.show_decrease_res()

        ori_trace_path = None
        de_trace_path = None

        id = most_shrinked_poc.split("__")[0]
        tail = most_shrinked_poc.split("__")[1]

        # I hate this hard code implementation!
        for _, _, ori_traces in os.walk(args.i):
            for ori_trace in ori_traces:
                if (id in ori_trace) and (tail in ori_trace):
                    ori_trace_path = os.path.join(args.i, ori_trace)
                    break

        for _, _, de_traces in os.walk(args.d):
            for de_trace in de_traces:
                if (id in de_trace) and (tail in de_trace):
                    de_trace_path = os.path.join(args.d, de_trace)
                    break

        P = Painter(ori_trace_path, de_trace_path, args.o, paint_mode=0)
        P.draw_graph()

    print("Finished!")


if __name__ == "__main__":
    main()