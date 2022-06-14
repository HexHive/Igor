# TraceClusterMaker

`TraceClusterMaker` is a refactoring and enhancement of `cluster_utils` with some new features added and more user-friendly oriented.

## Overview

<img src="./overview.png" width=640/>

This tool enumerate all files from the given *root directory* and treat them all as traces. A *trace* file is a **UTF-8** encoded multi-line plain-text file with any legal file name, in which each line has a hexadecimal address value prefixed with *0x*. In addition, line breaks are compatible across platforms. You can browse `trace_file_example.txt` to understand this file structure.

If you have ground-truth class info about each trace for evaluation, we highly recommend that you attach these class tags to the trace-file-path in a pattern that single regex expression can match, so that  values for some metrics, such as *purity* and *F1-measure*, will be automatically calculated and written to the report. For example, place some corresponding traces in directory `CVE-1234-12345` and `CVE-5678-67890`. Then place the two folders in a so-called *root directory* `all_traces`. Set parameter `--benchmark` with `CVE-\d{4}-\d{5}` additionally and run, you will get a report contains some useful scores.

The traces found would be read and analysed one by one. Finally a report file with *JSON* format would be saved in the destination folder you specified.

⚠️**Remember**: 

## Installation


## Usage


## Understanding the Report

