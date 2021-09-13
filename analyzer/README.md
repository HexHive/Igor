### Usage

You can find out crashing addresses of the given PoCs by using:
```console
$ python3 find_crashing_addr.py -i /path/to/PoCs -o /path/to/result/dir -b /magma_out/binary -a ~/binary_args -m 1
```
**Hint:**

- `binary_args` is a file that specifies the binary's parameters, which should be given by user!

---


You can count how many times a breakpoint is hit by using:
```console
$ python3 breakpoint_hit_counter.py -i /path/to/PoCs -o /path/to/result/dir -b /magma_out/binary -a binary_args -g gdb_cmd
```
**Hint:**

- `binary_args` and `gdb_cmd` are files that specify the binary's parameters and control the gdb debugging session, which should be given by user!
- There is a `gdb_cmd.sample` file, which is a sample of `gdb_cmd`.

---

You can remove all traces of shared libraries by using:
```console
$ python3 trace_shrinker.py -i /path/to/trace/files -o /path/to/result/dir
```

---

You can prune redundant trace entries(those recorded after the binary's crashing address) by using:

```console
$ python3 trace_pruner.py -i /path/to/trace/files -c /breakpoint/hit/count/dir -o /path/to/result/dir -a $breakpoint_addr
```

**Hint:**

- The `/breakpoint/hit/count/dir` is produced by `breakpoint_hit_counter.py` in an ASAN enabled environment.
- The `-a` parameter is a hexadecimal number indicating the address of "the breakpoint in the ASAN enabled environment" here in an ASAN disabled environment.

---

`collect_decreased_poc.sh` helps you collect the decreased pocs with the smallest bitmap size.
```console
$ collect_decreased_poc.sh -i /path/to/decreased/poc/dir -o /path/to/result/dir
```

---

`AsanParser.py` and `bitmap_size_formatter.py` are scripts for internal use.
