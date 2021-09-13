#!/usr/bin/python3

# Written and maintained by Jiang Zhiyuan <supermolejzy@gmail.com>

import os
import subprocess
import hashlib
import shutil
import argparse
import logging
import time
import re

# from AsanParser import *

binary_err_report_path = "/tmp/binary_err"
binary_out_path = "/tmp/binary_out"
gdb_info_report_path = "/tmp/gdb_info"
echo_out_path = "/tmp/e_out"
echo_err_report_path = "/tmp/e_err"
crash_inst_path = "/script/crash_inst_addr/crashes_addr"


########################################################################
class CrashesAnalyser:
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, binary_path, crash_source_dir, crash_target_dir, binary_args, group_mode, access_len_mode,
                 output_dir="/tmp/errout.d"):
        """Constructor"""
        self.binary = binary_path
        self.crash_dict = dict()
        self.inputs_path = set()
        self.crash_source_dir = crash_source_dir
        self.crash_target_dir = crash_target_dir
        self.binary_args = binary_args
        self._crash_pos_all = dict()
        self._group_mode = group_mode
        self._access_mode = access_len_mode
        self._invalid_read_len = set()
        self._invalid_write_len = set()
        self._output_dir = output_dir
        if not os.path.exists(self._output_dir):
            os.makedirs(self._output_dir)
        if crash_target_dir and not os.path.exists(crash_target_dir):
            os.makedirs(crash_target_dir)

    # ----------------------------------------------------------------------
    def start_work(self):
        """"""
        self._get_crashes()
        self._handle_crashes()

    # ----------------------------------------------------------------------
    def _get_crashes(self):
        """"""
        for crash in os.listdir(self.crash_source_dir):
            crash_path = os.path.join(self.crash_source_dir, crash)
            self.inputs_path.add(crash_path)

    # ----------------------------------------------------------------------
    def _handle_crashes(self):
        """"""
        for crash_path in self.inputs_path:
            if self._group_mode == 1:
                self._group_by_crash_postion_in_source(crash_path)

            # if self._access_mode == 1:
            #     self.invalid_access_len(crash_path)

    # ----------------------------------------------------------------------
    def _parse_binary_args(self, arg_file):
        content = ""
        with open(arg_file, 'r') as f:
            content = f.readline()

            return content

    def run_crash(self, crash_path):
        args = [self.binary]
        # args.append(crash_path)
        if self.binary_args is None:
            args.append(crash_path)
        else:
            bin_args = self._parse_binary_args(self.binary_args)
            if '@@' in bin_args:
                arg_before_poc = bin_args.split("@@")[0]
                arg_behind_poc = bin_args.split("@@")[1].strip()

                if len(arg_before_poc) != 0:
                    args.extend(arg_before_poc.split(" ")[:-1])

                args.append(crash_path)
                args.extend(arg_behind_poc.split(" "))
            else:
                args.append(crash_path)
                args.extend(self.binary_args.split(" "))

        with open(binary_err_report_path, 'w+') as f:
            pass
        err_file = os.path.join(self._output_dir, os.path.basename(crash_path))
        er = open(err_file, 'w')
        cmd = " ".join(args)
        p = subprocess.run(cmd, shell=True, stderr=er)
        er.flush()
        er.close()

    # ----------------------------------------------------------------------
    def _group_by_crash_postion_in_source(self, crash_path):
        # we need to run current crash first, so that we can generate corresponding output file
        self.run_crash(crash_path)

        # parse the output file to do analyze
        errfile = '/tmp/errout.d/' + os.path.basename(crash_path)
        with open(errfile, 'r+') as f:
            content = f.readlines()
            for cnt in range(0, len(content) - 1):
                if ".c:" in content[cnt] or ".cc:" in content[cnt] or ".h:" in content[cnt]:
                    crash_pos = content[cnt].split('/')[-1].split('\n')[0]

                    if crash_pos in self._crash_pos_all.keys():
                        self._crash_pos_all[crash_pos].append(crash_path)
                        break
                    else:
                        self._crash_pos_all[crash_pos] = [crash_path]
                        break

        return

    # ----------------------------------------------------------------------
    # def invalid_access_len(self, crash_path):
    #     self._run_crash(crash_path)
    #
    #     parser = AsanOutputParser(binary_err_report_path)
    #     action_type, length = parser.invalid_access_length()
    #
    #     if action_type == "WRITE":
    #         self._invalid_write_len.add(length)
    #     elif action_type == "READ":
    #         self._invalid_read_len.add(length)
    #     else:
    #         pass


# ----------------------------------------------------------------------
def main():
    """"""
    logging.basicConfig(level=logging.NOTSET,
                        format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", help="afl crashes dir")
    parser.add_argument("-o", help="classified dir")
    parser.add_argument("-b", help="cb path without afl_ptr_area")
    parser.add_argument("-a", help="the path of argument file", default=None)
    parser.add_argument("-m", help="crash group mode", type=int, default=0)
    parser.add_argument("-l", help="invalid access length", type=int, default=0)
    args = parser.parse_args()
    Worker = CrashesAnalyser(args.b, args.i, args.o, args.a, args.m, args.l)
    Worker.start_work()

    if args.m == 1:
        # print the group result
        for item in Worker._crash_pos_all.keys():
            print("===================", item, "===================")
            for crash_id in Worker._crash_pos_all[item]:
                print(crash_id)

        # Dump the group result into a file
        result_file = os.path.join(args.o, "group_by_address")
        with open(result_file, 'w+') as f:
            summary_1 = "[+] Crash Location Summary" + "\n"
            f.write(summary_1)
            summary_2 = "[+] There are " + str(len(Worker._crash_pos_all)) + " unique locations in total" + "\n"
            f.write(summary_2)
            summary_3 = "[+] They are: " + str(Worker._crash_pos_all.keys()) + "\n"
            f.write(summary_3)

            for item in Worker._crash_pos_all.keys():
                str_addr = "===================" + item + "===================" + "\n"
                f.write(str_addr)
                for crash_id in Worker._crash_pos_all[item]:
                    f.write(crash_id)
                    f.write('\n')

    if args.l == 1:
        print("invalid read length are: ", sorted(Worker._invalid_read_len))
        print("invalid write length are: ", sorted(Worker._invalid_write_len))

    print('Finished!')


if __name__ == "__main__":
    main()
