#!/bin/env python

# Written and maintained by Jiang Zhiyuan <supermolejzy@gmail.com>

import os
import subprocess
import hashlib
import shutil
import argparse
import logging
import time
import re

binary_err_report_path = "/tmp/binary_err"
binary_out_path = "/tmp/binary_out"
gdb_info_report_path = "/tmp/gdb_info"
echo_out_path = "/tmp/e_out"
echo_err_report_path = "/tmp/e_err"

monitor_out_path = "/tmp/m_out"
bug_trigger_result = "./trigger_info"


########################################################################
class AsanOutputParser():
    """"""

    # ----------------------------------------------------------------------
    def __init__(self, asan_output_path=None):
        """Constructor"""
        self._asan_output = asan_output_path
        self.vuln_variable_name = ""  # the invalid accessed variable name


    def invalid_access_length(self):
        invalid_access_len = 0
        action_type = ''

        with open(self._asan_output) as f:
            content = f.readlines()
            for cnt in range(0, len(content)-1):
                if 'WRITE of size' in content[cnt]:
                    numbers = re.findall(r"\b\d+\b", content[cnt]) # parse all numbers in this line
                    if len(numbers) == 0:
                        print('Weird! there is no size of access!\n')
                        return

                    invalid_access_len = int(numbers[0])
                    action_type = "WRITE"
                    break
                elif 'READ of size' in content[cnt]:
                    numbers = re.findall(r"\b\d+\b", content[cnt])  # parse all numbers in this line
                    if len(numbers) == 0:
                        print('Weird! there is no size of access!\n')
                        return

                    invalid_access_len = int(numbers[0])
                    action_type = "READ"
                    break
                else:
                    pass

        return action_type, invalid_access_len

    def _is_overflow(self):
        with open(self._asan_output, 'r+') as f:
            lines = f.readlines()

        for line in lines:
            if "overflow on" in line:
                return True

        return False

    @staticmethod
    def _parse_overflow_variable(line):
        var_search = re.compile(r'[\'](.*?)[\']', re.S)
        print(re.findall(var_search, line))

        return re.findall(var_search, line)

    @staticmethod
    def _parse_undeflow_variable(line):
        var_search = re.compile(r"(?<=offset)\d+")
        print(re.search(var_search, line))

        return re.findall(var_search, line)

    def _parse_vuln_variable(self):
        var_name = ""
        with open(self._asan_output, 'r+') as f:
            lines = f.readlines()

        for line in lines:
            if "overflows this variable" in line:
                var_name = self._parse_overflow_variable(line)
                self.vuln_variable_name = var_name
            elif "underflows this variable" in line:
                var_name = self._parse_undeflow_variable(line)
                self.vuln_variable_name = var_name
            else:
                pass


    # ----------------------------------------------------------------------
    def _run(self):

        # STEP 1: check whether it is overflow
        is_overflow = self._is_overflow()
        if is_overflow:
            self._parse_vuln_variable()
        else:
            return # currently, we only handle overflow type

# ----------------------------------------------------------------------
def main():

    asan_output_path = "/home/vultest/test_asan_parser/asan_0.out"

    parser = AsanOutputParser(asan_output_path)
    parser._run()

    print("The interesting variable name is: ", parser.vuln_variable_name)



    print("Finished!")


if __name__ == "__main__":
    main()



