#!/usr/bin/python3

# Written and maintained by Jiang Zhiyuan <supermolejzy@gmail.com>

import os
import argparse

DEBUG = 0

class TraceShrinker():
    def __init__(self, ori_traces_path, shrinked_traces_path):
        self._input_dir = ori_traces_path
        self._output_dir = shrinked_traces_path

        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)

    @staticmethod
    def _remove_stack_trace(input_file, output_path):
        final_content = ""
        original_content = ""
        with open(input_file, 'rb') as f:
            original_content = f.readlines()

        with open(output_path, 'ab') as f:
            for line in original_content:
                if b"7fff" in line:
                    continue
                else:
                    f.write(line)


    def shrink_wrapper(self):
        for _, _, traces in os.walk(self._input_dir):
            for trace in traces:
                trace_file = os.path.join(self._input_dir, trace)
                shrinked_trace_file = os.path.join(self._output_dir, trace)

                self._remove_stack_trace(trace_file, shrinked_trace_file)



def main():
    if DEBUG == 1:
        pass

    parser = argparse.ArgumentParser()

    parser.add_argument("-i", help="original traces dir")
    parser.add_argument("-o", help="output shrinked traces storage dir")

    args = parser.parse_args()

    T = TraceShrinker(args.i, args.o)
    T.shrink_wrapper()

    print("Finished!")

if __name__ == "__main__":
    main()

