#!/usr/bin/python3

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

import os
import argparse
import re
from find_crashing_addr import CrashesAnalyser
from conifg import config
from multiprocessing import Process, Manager
import subprocess
import json
import math

TMP_OUTPUT_PATH = config["trace_tmp_path"]
COMMAND_SUFFIX = "2>/dev/null | grep -P \"^Breakpoint 1,\" | wc -l"
PAT_COMMON_FRAME = re.compile(r"#(\d)+ (0x.+) in (.+) (\(?/.+\)?)$")
PAT_ORIGIN_FRAME = re.compile(r"#(\d)+(\s0x).+\sin\s_start.+$")
ASAN_FUNC_BLOCK_LIST = ["__lsan", "__interceptor", "__interception", "ubsan", "__asan", "__sanitizer"]
MAX_HIT_COUNT = config["max_hit_count"]

KEY_BREAKPOINT = "breakpoint"
KEY_HIT_COUNT = "hit_count"


class BreakpointHitCounter:
    def __init__(self, binary_path, poc_path, output_path, binary_args, parallel_level=1):  # , gdb_cmd_path):
        self._binary_path = binary_path
        self._poc_path = poc_path
        self._output_path = output_path
        self._binary_args = binary_args
        self._parallel_level = parallel_level
        self._user_src_dir_prefix = config["user_src_dir_prefix"]
        self._gdb_cmd_path = os.path.join(TMP_OUTPUT_PATH, "gdb_cmd")

        if not os.path.exists(output_path):
            os.makedirs(output_path)
        if not os.path.exists(TMP_OUTPUT_PATH):
            os.makedirs(TMP_OUTPUT_PATH)
        if not os.path.exists(self._gdb_cmd_path):
            os.makedirs(self._gdb_cmd_path)

        self._err_dump_path = os.path.join(TMP_OUTPUT_PATH, os.path.basename(self._poc_path.strip('/') + "_err_dump"))
        self._crash_analyser = CrashesAnalyser(self._binary_path, None, None, self._binary_args, None, None,
                                               self._err_dump_path)
        self._hit_count_dict = {}

    def _list_pocs(self, poc_path):
        return os.listdir(poc_path)

    def _record_err_dumps(self, pocs):
        for poc_file in pocs:
            poc_file_full_qualified = os.path.join(self._poc_path, poc_file)
            self._crash_analyser.run_crash(poc_file_full_qualified)

    def _count_breakpoint(self, pocs, result_queue):
        for poc_file in pocs:
            err_dump_file_full_qualified = os.path.join(self._err_dump_path, poc_file)
            call_stack = self._recover_call_stack_from(err_dump_file_full_qualified)
            # gdb_breakpoints is a list of breakpoints
            gdb_breakpoints = self._find_breakpoints(call_stack)
            # While running in parallel, self._hit_count_dict is updated individually in each process.
            self._hit_count_dict[poc_file] = {}
            self._hit_count_dict[poc_file][KEY_BREAKPOINT] = gdb_breakpoints
            self._hit_count_dict[poc_file][KEY_HIT_COUNT] = []
            for breakpoint in gdb_breakpoints:
                self._run_crash(poc_file, breakpoint)
        result_queue.put(self._hit_count_dict)

    def _partition(self, parallel_level, poc_list):
        partition = []
        for i in range(parallel_level):
            length = math.ceil(len(poc_list) / parallel_level)
            start = i * length
            end = (i + 1) * length
            sub_list = poc_list[start: end]
            partition.append(sub_list)
        return partition

    def start(self):
        """
        The entrance of breakpoint hit counter process
        """
        pocs = self._list_pocs(self._poc_path)
        result_queue = Manager().Queue()
        process_list = []

        partitioned_pocs = self._partition(self._parallel_level, pocs)
        print("* Start recording err dumps.")
        for sub_list in partitioned_pocs:
            process = Process(target=self._record_err_dumps, args=(sub_list,))
            process.start()
            process_list.append(process)
        for process in process_list:
            process.join()
        print("* Done.")

        print("* Start counting breakpoint.")
        if self._parallel_level == 1:
            self._count_breakpoint(pocs, result_queue)
        else:
            process_list.clear()
            for sub_list in partitioned_pocs:
                process = Process(target=self._count_breakpoint, args=(sub_list, result_queue))
                process.start()
                process_list.append(process)
            for process in process_list:
                process.join()

            # Update the root process
            while not result_queue.empty():
                partial_hit_count_dict = result_queue.get()
                self._hit_count_dict.update(partial_hit_count_dict)
        print("* Done.")

        # Dump json file
        print("* Dump hit_count.json.")
        json_file = os.path.join(self._output_path, "hit_count.json")
        with open(json_file, 'w') as jf:
            jf.write(json.dumps(self._hit_count_dict, sort_keys=True, indent=2))
        print("* Done.")

    def _parse_binary_args(self, arg_file):
        with open(arg_file, 'r') as f:
            content = f.readline()
            return content

    def _in_user_code(self, src_dir):
        in_target_repo = src_dir.startswith(self._user_src_dir_prefix)
        in_user_source_code = ".c:" in src_dir or ".cc:" in src_dir or ".h:" in src_dir
        return in_target_repo and in_user_source_code

    def _src_dir_to_line_number(self, src_dir):
        """
        Extract src filename and line number and cut the tailing column number from src_dir.

        :param src_dir: directory of source file
        :return: src filename and line number
        """
        code_pos_orig = src_dir.split('/')[-1]
        code_pos_split = code_pos_orig.split(':')
        if len(code_pos_split) == 3:
            code_pos_line_number = ":".join(code_pos_split[:-1])
        else:
            code_pos_line_number = code_pos_orig
        return code_pos_line_number

    def _find_breakpoints(self, call_stack):
        """
        Find the break point of a poc for the target binary.

        :param call_stack: a call stack recovered from error dump
        :return: src file and line number for setting breakpoint in gdb.
        """
        gdb_breakpoints = []
        for i in range(len(call_stack)):
            _, hex_addr, src_dir = call_stack[i]

            if self._in_user_code(src_dir):
                breakpoint = self._src_dir_to_line_number(src_dir)
                if breakpoint not in gdb_breakpoints:
                    gdb_breakpoints.append(breakpoint)

        return gdb_breakpoints

    def _recover_call_stack_from(self, stderr_file):
        """
        Recover call stack from error dump file.

        :param stderr_file: error dump file generated by a sanitizer
        :return: recovered call stack at crash time
        """
        call_stack_rec = []
        with open(stderr_file, 'r') as fx:
            for err_info_line in fx:
                match_obj = re.search(PAT_COMMON_FRAME, err_info_line)
                if not match_obj:  # Hit a call stack record line
                    continue
                frame_no, hex_addr, func_name, src_dir = match_obj.groups()
                if func_name in ASAN_FUNC_BLOCK_LIST:
                    continue
                call_stack_rec.append((frame_no, hex_addr, src_dir))
                if re.search(PAT_ORIGIN_FRAME, err_info_line):  # Hit the entrance point
                    break
        return call_stack_rec

    def _read_breakpoint_count(self, breakpoint_hit_cnt_file):
        with open(breakpoint_hit_cnt_file) as bhcf:
            breakpoint_hit_count = int(bhcf.readline())
        return breakpoint_hit_count

    def _run_crash(self, poc_filename, gdb_breakpoint):
        """
        Parse command line arguments and construct shell script for breakpoint counting.

        :param poc_filename:
        :return: None
        """
        gdb_cmd_file_full_qualified = os.path.join(self._gdb_cmd_path, poc_filename)
        with open(gdb_cmd_file_full_qualified, 'w') as gcf:
            # gdb_breakpoints = self._hit_count_dict[poc_filename][KEY_BREAKPOINT]
            gcf.write("b {}\nr\n".format(gdb_breakpoint))
            for i in range(MAX_HIT_COUNT):
                gcf.write("c\n")
        poc_file_full_qualified = os.path.join(self._poc_path, poc_filename)
        #command = ["echo q | gdb -q -x", gdb_cmd_file_full_qualified, "--args", self._binary_path]
        command = ["gdb -q -x", gdb_cmd_file_full_qualified, "--args", self._binary_path]
        if self._binary_args is None:
            command.append(poc_file_full_qualified)
        else:
            bin_args = self._parse_binary_args(self._binary_args)
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

        command.append(COMMAND_SUFFIX)
        breakpoint_hit_count_file = os.path.join(self._output_path, poc_filename)
        redirect_cmd = "> " + breakpoint_hit_count_file
        command.append(redirect_cmd)
        shell_command = " ".join(command)

        # sample redirect_cmd:
        # "echo q | gdb -q -x gdb.cmd --args /magma_out/target -M poc_abcd 2>/dev/null | grep -P '^Breakpoint 1,' | wc -l > /tmp/breakpoint_cnt/poc_abcd"
        #os.system(shell_command)
        ret = subprocess.run(shell_command, input="q".encode(), shell=True, stderr=subprocess.PIPE)
        if ret.returncode != 0:
            print(ret)
        if ret.stderr:
            print(poc_filename, ret.stderr.decode())

        hit_count = self._read_breakpoint_count(breakpoint_hit_count_file)
        if hit_count >= MAX_HIT_COUNT:
            print("- MAX_HIT_COUNT reached, please consider increase it in config.py. poc filename: {}".format(
                poc_filename))
        self._hit_count_dict[poc_filename][KEY_HIT_COUNT].append(hit_count)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Count how many times a specific break point hits throughout a program's lifetime. \n"
                    "Sample gdb command file is listed in source file.")
    parser.add_argument("-i", help="afl crashes dir")
    parser.add_argument("-o", help="result output dir")
    parser.add_argument("-b", help="cb path without afl_ptr_area")
    parser.add_argument("-a", help="the path of argument file", default=None)
    parser.add_argument("-p", help="parallel level", type=int, default=1)
    args = parser.parse_args()
    Worker = BreakpointHitCounter(args.b, args.i, args.o, args.a, args.p)  # , args.g)
    Worker.start()

###################################
# sample gdb command file
#
# ---------------------------------
# in gdb.cmd:
# ---------------------------------
# b valid.c:1397
# r
# c
# c
# c
# /* type "c" as much time
#                   as you want */
# c
# ---------------------------------
#
# NOTE:
# In the example above, the lines of 'c' is estimated by human while
# analysing crash point manually.
#
# For example, breakpoint A may be hit 2-3 times in program Ap, while
# breakpoint B may be hit only 60-70 times in program Bp. For this case,
# we only need no less than 3 lines of 'c' for program Ap, while program
# Bp needs no less than 70 lines of 'c'.
#
# The first line in gdb command line("b valid.c:1397" in this example) is
# the same. We may need to alter the breakpoint when we deal with different
# target programs, even poc files of one specific program.
###################################
