#!/usr/bin/python3

# Written and maintained by Jiang Xiyue <xiyue_jiang@outlook.com>

import re, sys
filename = sys.argv[1]

"""
A simple utility for formatting the output of bitmap-size.
Format: "<len> <map size> <exec speed> <poc filename>"
"""

patt_name = re.compile(r"Attempting dry run with '(.+)'")
patt_info = re.compile(r"len = (\d+), map size = (\d+), exec speed = (\d+) us")

bm_size_file = open(filename)
lines = bm_size_file.readlines()

start_flag = False
name = ""

for line in lines:
    mat = patt_name.search(line)
    if mat is not None:
        start_flag = True
        name = mat.groups()[0]

    mat = patt_info.search(line)
    if start_flag == True and mat is not None:
        # Reset start_flag to handle unexpected format.
        start_flag = False
        _len, map_size, exec_speed = mat.groups()
        print("{}\t{}\t{}\t{}".format(_len, map_size, exec_speed, name))

bm_size_file.close()
