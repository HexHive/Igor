#!/bin/env python

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

import os
import argparse

DEBUG = 0

class Tracer():
    def __init__(self, pin_path, pintool_path, traces_store_dir, binary_path, pocs_dir, module_blocklist, func_blocklist, *arg):
        self._pin_path = pin_path
        self._pintool_path = pintool_path
        self._traces_store_dir = traces_store_dir
        self._binary_path = binary_path
        self._pocs_dir = pocs_dir
        self._bin_args_file = ""
        self._module_blocklist = module_blocklist
        self._func_blocklist = func_blocklist

        self._args_before_poc = ""
        self._args_behind_poc = ""

        self._pin_args= ""

        if arg:
            # parse binary argument first
            self._bin_args_file = arg[0]
            bin_args = self._parse_binary_args(self._bin_args_file)
            if '@@' in bin_args:
                arg_before = bin_args.split("@@")[0].strip()
                arg_behind = bin_args.split("@@")[1].strip()

                if len(arg_before):
                    self._args_before_poc = arg_before

                if len(arg_behind):
                    self._args_behind_poc = arg_behind

        self._pin_args= "-blockModule {} -blockFunc {}".format(self._module_blocklist, self._func_blocklist)


    def _parse_binary_args(self, arg_file):
        content = ""
        with open(arg_file, 'r') as f:
            content = f.readline()
            return content

    def _tracer(self, poc_path, *args):
        """
        Construct a shell command and run it for tracing.
        """
        poc_name = os.path.basename(poc_path)
        result_path = os.path.join(self._traces_store_dir, poc_name)

        if self._bin_args_file:
            # target program have args before & behind poc
            if len(self._args_before_poc) and len(self._args_behind_poc):
                command = '{} -t {} {} -o {} -- {} {} {} {}'.format(self._pin_path,
                                                                           self._pintool_path,
                                                                           self._pin_args,
                                                                           result_path,
                                                                           self._binary_path,
                                                                           self._args_before_poc,
                                                                           poc_path,
                                                                           self._args_behind_poc)
            # target program only have args before poc
            elif len(self._args_before_poc) and len(self._args_behind_poc) == 0:
                command = '{} -t {} {} -o {} -- {} {} {}'.format(self._pin_path,
                                                                            self._pintool_path,
                                                                            self._pin_args,
                                                                            result_path,
                                                                            self._binary_path,
                                                                            self._args_before_poc,
                                                                            poc_path)
            # target program only have args behind poc
            elif len(self._args_before_poc) == 0 and len(self._args_behind_poc):
                command = '{} -t {} {} -o {} -- {} {} {}'.format(self._pin_path,
                                                                             self._pintool_path,
                                                                             self._pin_args,
                                                                             result_path,
                                                                             self._binary_path,
                                                                             poc_path,
                                                                             self._args_behind_poc)
            else:
                pass

            os.system(command)
        else:
            command = '{} -t {} {} -o {} -- {} {}'.format(self._pin_path,
                                                                       self._pintool_path,
                                                                       self._pin_args,
                                                                       result_path,
                                                                       self._binary_path,
                                                                       poc_path)
            os.system(command)

    def tracer_wapper(self):
        for _, _, pocs in os.walk(self._pocs_dir):
            for poc in pocs:
                poc_path = os.path.join(self._pocs_dir, poc)

                self._tracer(poc_path)
def main():
    if DEBUG == 1:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", help="pin path")
    parser.add_argument("-t", help="pintool path")
    parser.add_argument("-o", help="traces storage dir")
    parser.add_argument("-b", help="binary path")
    parser.add_argument("-i", help="pocs dir")
    parser.add_argument("-m", help="module blocklist(listed modules won't be recorded), separated by comma, no extra white space. default: [libc]", type=str, default="libc")
    parser.add_argument("-f", help="function blocklist(listed functions won't be recorded), separated by comma, no extra white space. default: [magma_log]", type=str, default="magma_log")
    parser.add_argument("-a", help="the path of argument file", default=None)

    args = parser.parse_args()

    if args.a is None:
        F = Tracer(args.p, args.t, args.o, args.b, args.i, args.m, args.f)
        F.tracer_wapper()

    else:
        F = Tracer(args.p, args.t, args.o, args.b, args.i, args.m, args.f, args.a)
        F.tracer_wapper()


    print("Finished!")

if __name__ == "__main__":
    main()
