# Igor: Crash Deduplication Through Root-Cause Clustering
## Overview

Fuzzing has emerged as the most effective bug-finding technique. The output of a
fuzzer is a set of proof-of-concept (PoC) test cases for all observed “unique”
crashes. It costs developers substantial efforts to analyze each crashing test
case. This, mostly manual, process has lead to the number of reported crashes
out-pacing the number of bug fixes. Automatic crash deduplication techniques,
which mostly rely on coverage profiles and stack hashes, are supposed to
alleviate these pressures. However, these techniques both inflate actual bug
counts and falsely conflate unrelated bugs. This hinders, rather than helps,
developers, and calls for more accurate techniques.

Igor is a tool for automated crash grouping/deduplication. By minimizing each
PoC’s execution trace, it can obtain pruned test cases that exercise the
critical behavior necessary for triggering a bug. Then, Igor use a graph
similarity comparison to cluster crashes based on the control-flow graph of the
minimized execution traces, with each cluster mapping back to a single, unique
root cause.

Igor helps a lot when you have many PoCs and would like to classify them into
several groups according to the root cause, so that you don't need to analyze
the PoCs one by one. 

[Here](https://github.com/HexHive/Igor/tree/main/images/Igor_overview.pdf)
is a flow chart for overviewing the Igor's workflow.

More details about the project can be found at the [paper](https://hexhive.epfl.ch/publications/files/21CCS.pdf).

Our presentation about Igor can be found at the [video](https://www.youtube.com/watch?v=V06x1Ad5dRo)


## Components
This repository is structured as follows:

1. IgorFuzz (AFLplusplus): Our coverage decreasing fuzzer for test cases reduction.
2. Smart_tracer (Pin): Our tracer to record control flow.
3. Analyzer: Prune recorded execution traces and construct control flow graphs 
4. TraceClusterMaker: Our cluster tool based on graph similar matrixs
5. Evaluation: Our evaluation scripts used in Igor paper



## IgorFuzz
We developed IgorFuzz based on AFLplusplus crash exploration mode. It can prune
the paths that unnecessary for bug triggering very fast. Before using IgorFuzz,
we suggest use afl-tmin to shrink the size of crash first, so that IgorFuzz will
have better performance. 

### Installation and Usage
The installation and usage of IgorFuzz is completely same to the AFLplusplus'
crash mode. Even time you want to launch IgorFuzz, you must confirm that you
have put a PoC in input directory and set up output directory properly.


### Reduction in parallel

IgorFuzz reduces one PoC at one time. To apply IgorFuzz on many PoCs parallelly,
we provide users with `mass_fuzz.sh`. It will automatically run over and over
again untill all PoCs in input dir are fuzzed.


Collect all PoCs you want to reduce in input directory(e.g., `/home/my_pocs`), and set up output dir(e.g., `/home/trimmed/my_pocs`). 

The third arg is the number of PoCs you want to fuzz parallelly each time. The
last arg is the duration the fuzzing last for(e.g., 1h2m3s).

Example:
```console
$ ./mass_fuzz.sh /home/my_pocs /home/trimmed/my_pocs 30 10h
```


The form of result is: `/home/trimmed/my_pocs/$the-name-of-a-PoC(like: id:000000,xxxxxxxx)/`


`mass_fuzz.sh` renames fuzzed PoCs like: `fzd_id:000000,xxxxx`. So if there's something wrong with IgorFuzz or you want to shirnk all PoCs again, you can use `./clear_fzd.sh $INPUT_DIR` to remove "fzd" prefix. 



## Tracing and Analyzing

To obtain precise execution traces (basic block level in default) of a specific
binary, we need the following tools:

- `smart_tracer/calltrace_wrapper.py`
- `analyzer/breakpoint_hit_counter.py`
- `analyzer/find_crashing_addr.py`
- `analyzer/trace_shrinker.py`
- `analyzer/trace_pruner.py`

For usages of the above tools, please check `analyzer/README` and `smart_tracer/README`.

### Workflow
Execution traces need to be filted before constructing the control flow graph to
be used to calculate the graph similarity. Follwing steps show how to do that.

#### STEP 1 - In the ASAN disabled environment

- Using `calltrace_wrapper.py` to collect execution traces of the binary under
  test. Users can confiure which granularity they want to use, for now, we
  support instruction level, basic block level, and function call level.
- Using `trace_shrinker.py` to filter out execution traces related to shared
  libraries.

#### STEP 2 - In the ASAN enabled environment

- Using `find_crashing_addr.py` to find out the number of crashing addresses(the line number observed when the binary crashes). For each crashing address, repeat the following three steps:
  - Debug the binary under test, find the last function the binary calls before
    crashing, take down its caller's address(usually, the `call` instruction's
    address).
  - Using `breakpoint_hit_counter.py` to find out how many times the address
    mentioned above is hit before the binary crashes.
  - Copy the breakpoint hit count folder to our ASAN disabled environment.

#### STEP 3 - In the ASAN disabled environment 

- Debug the binary under test, find the same caller as the one in the ASAN enabled environment.
- Using `trace_pruner.py` to prune redundant trace entries that are recorded after the point that the binary should have crashed. This step gives you a pruned traces directory for clustering.



## Clustering

The `TraceClusterMaker` folder contains the utilities for clustering.

`TraceClusterMaker/ClusterMaker.py` will do everything for you, including construct
control flow graphs based on pruned traces, calculate graph similarities and
clustering.

## Ground-truth Benchmark
There are few public benchmark designed for the verification of crash grouping,
especially for real world programs. In order to promote the research of crash
grouping, we provide a a ground-truth benchmark for evaluating crash grouping
techniques, containing 52 CVEs and more than 250,000 crashing test cases from 14
real world programs (generated over 58.7 CPU-years of fuzzing) for subsequent
researchers, Igor also used this dataset to do the evaluations.

We are grateful to [Magma](https://hexhive.epfl.ch/magma/) and
[Moonlight](https://hexhive.epfl.ch/publications/files/21ISSTA2.pdf) for the
original data and the methodology of establishing the ground truth data set. We
used all their crashes and labels in the process of building the our benchmark,
and further expanded the scale of the data set on their basis (more fuzzing time
to generate more crashes).

In our ground-truth benchmark, we used the PoCs from
[PoCalypse](https://github.com/HexHive/PoCalypse).
Every PoC is labeled with its root cause, user can get the label by parse the name of the PoC.

Building Magma targets approach can be found [here](https://hexhive.epfl.ch/magma/docs/getting-started.html)  
Building MoonLight targets approach can be found [here](https://datacommons.anu.edu.au/DataCommons/rest/records/anudc:5927/data/Binaries/)

## Contact
Questions? Concerns? Feel free to ping me via [E-mail](supermolejzy@gmail.com)  
For recent update and new features implementation, please ping Sonic who is pushing this project forward via [E-mail](observer000@qq.com)

## TODO
- ~~Provide evaluation scripts we used in Igor paper~~
- ~~Provide link to Igor's dataset~~
- Provide detailed tutorial for Igor system
- Provide README for evaluation scripts
- Provide scripts to do trace analyzing stuff automaticlly

