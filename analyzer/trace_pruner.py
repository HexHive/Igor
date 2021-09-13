#!/bin/env/python3

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

import os
import argparse
import r2pipe
import json
import subprocess
from conifg import config
import re

TMP_OUTPUT_PATH = config["trace_tmp_path"]
KEY_BREAKPOINT = "breakpoint"
KEY_HIT_COUNT = "hit_count"
PAT_BREAKPOINT_ADDR = re.compile(r'Breakpoint 1 at (0x[a-z0-9]+)')


class TracePruner:
    def __init__(self, trace_dir, breakpoint_hit_count_file, output_dir, target_binary, binary_args):
        self._trace_dir = trace_dir
        self._breakpoint_hit_count_file = breakpoint_hit_count_file
        self._output_dir = output_dir
        self._target_binary = target_binary
        self._gdb_cmd_path = os.path.join(TMP_OUTPUT_PATH, "trace_gdb_cmd")
        self._binary_args = binary_args
        with open(self._breakpoint_hit_count_file, 'r') as bhcf:
            self._hit_count_dict = json.load(bhcf)

        if not os.path.exists(self._gdb_cmd_path):
            os.makedirs(self._gdb_cmd_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        print("* Initializing r2.")
        self._r2_init()
        print("* Done.")

    def _get_trace_files(self):
        return os.listdir(self._trace_dir)

    def _r2_init(self):
        """
        Initialize r2 instances
        """
        # Disable stderr of radare2
        self._r2 = r2pipe.open(self._target_binary, flags=['-2'])
        self._r2.cmd("aa")

    def _parse_binary_args(self, arg_file):
        with open(arg_file, 'r') as f:
            content = f.readline()
            return content

    def _construct_target_binary_args(self, poc_file_full_qualified):
        command = []
        if self._binary_args is None:
            command.append(poc_file_full_qualified)
        else:
            bin_args = self._parse_binary_args(self._binary_args)
            command = []
            if '@@' in bin_args:
                arg_before_poc = bin_args.split("@@")[0].strip()
                arg_behind_poc = bin_args.split("@@")[1].strip()

                if len(arg_before_poc) != 0:
                    command.extend(arg_before_poc.split(" "))

                command.append(poc_file_full_qualified)
                command.extend(arg_behind_poc.split(" "))
            else:
                command.append(poc_file_full_qualified)
                command.extend(self._binary_args.split(" "))
        return command

    def _addresses_of_source(self, trace_filename):
        """
        Given a source code line number, return the corresponding instruction address.

        :param trace_filename:
        :return: address of the given line
        """
        trace_file_full_qualified = os.path.join(self._trace_dir, trace_filename)
        gdb_breakpoints = self._hit_count_dict[trace_filename][KEY_BREAKPOINT]
        addresses_of_source = []
        for breakpoint in gdb_breakpoints:
            gdb_cmd = "b {}\nq\n".format(breakpoint).encode()
            shell_cmd = ["gdb -q --args", self._target_binary]
            shell_cmd.extend(self._construct_target_binary_args(trace_file_full_qualified))
            p = subprocess.run(" ".join(shell_cmd), input=gdb_cmd, stdout=subprocess.PIPE, shell=True)
            try:
                address = PAT_BREAKPOINT_ADDR.search(p.stdout.decode()).groups()[0]
                addresses_of_source.append(address)
            except Exception as e:
                print(e)
                print(p.stdout.decode())
        return addresses_of_source

    def _next_call_inst_addr(self, cur_addr, call_insts):
        cur_addr = int(cur_addr, 16)
        for call_inst in call_insts:
            if call_inst == '':
                continue
            call_inst_addr = int(call_inst.split()[0], 16)
            if call_inst_addr >= cur_addr:
                return call_inst_addr
        else:
            return None

    def _find_call_ins_addrs(self, addrs):
        """
        Find the first call-instruction's address in the basic block of the breakpointed source code line.

        :param addr: an address in a basic block
        :return: the first call-instruction's address
        """
        next_call_ins_addrs = []
        for cur_addr in addrs:
            call_insts = self._r2.cmd("s {}; pdsf | grep call | grep -v magma_log".format(cur_addr)).split('\n')
            # next_call_addr is an int
            next_call_addr = self._next_call_inst_addr(cur_addr, call_insts)
            next_call_ins_addrs.append(next_call_addr)
        return next_call_ins_addrs

    def _get_last_breakpoint_addr_index(self, hit_count, trace_file_lines, breakpoint_addr):
        if hit_count == 0:
            return None
        stop_position = hit_count
        breakpoint_addr_int = breakpoint_addr
        curr_position = 0
        for idx, line in enumerate(trace_file_lines):
            line_int = int(line, 16)
            if line_int == breakpoint_addr_int:
                curr_position += 1
            if curr_position == stop_position:
                return idx
        else:
            return None

    def _get_breakpoints_hit_count(self, trace_filename):
        return self._hit_count_dict[trace_filename][KEY_HIT_COUNT]

    def _prune_trace(self, trace_filename):
        """
        Prune one trace file.
        :param trace_filename:
        :return:
        """
        trace_file_path = os.path.join(self._trace_dir, trace_filename)
        output_file_path = os.path.join(self._output_dir, trace_filename)

        breakpoints_hit_count = self._get_breakpoints_hit_count(trace_filename)

        breakpoint_addrs = self._addresses_of_source(trace_filename)
        # cut_addrs are hexadecimal numbers
        cut_addrs = self._find_call_ins_addrs(breakpoint_addrs)

        trace_file = open(trace_file_path, "r")
        trace_file_lines = trace_file.readlines()
        trace_file.close()

        for idx, cut_addr in enumerate(cut_addrs):
            if cut_addr is None:
                continue
            hit_count = breakpoints_hit_count[idx]
            stop_idx = self._get_last_breakpoint_addr_index(hit_count, trace_file_lines, cut_addr)
            if stop_idx is None:
                continue

            # Prune the trace with the first valid cut_addr
            stop_idx += 1
            output_file = open(output_file_path, "w")
            for line in trace_file_lines[:stop_idx]:
                output_file.write(line)
            output_file.close()
            return
        else:
            print("- Failed to prune \"{}\"".format(trace_filename))
            return

    def prune_traces(self):
        """
        Prune all trace files in trace dir.
        :return:
        """
        trace_filenames = self._get_trace_files()
        for trace_filename in trace_filenames:
            self._prune_trace(trace_filename)

    def start(self):
        print("* Start pruning.")
        self.prune_traces()
        print("* Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Prune trace files according to a designated address and its breakpoint hit count")
    parser.add_argument("-i", help="trace file dir")
    parser.add_argument("-c", help="breakpoint hit count file")
    parser.add_argument("-o", help="result output dir (auto create if not exists)")
    parser.add_argument("-b", help="target binary")
    parser.add_argument("-a", help="the path of argument file", default=None)
    args = parser.parse_args()
    tp = TracePruner(args.i, args.c, args.o, args.b, args.a)  # , args.a)
    tp.start()
