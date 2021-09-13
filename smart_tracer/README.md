### Usage

You can collect a binary's function-caller-address traces of given PoCs by using:

```console
$ python3 calltrace_wrapper.py -p pin -t pintool/calltrace.so -o /trace/storage/dir -b /path/to/binary -i /path/to/PoCs -a binary_args
```

### Hint

- The `binary_args` is a file that specifies the binary's parameters, which should be given by user! 

- The `pin` binary comes with an Intel Pin distribution, please check the Pin's download site [ Pin - A Binary Instrumentation Tool - Downloads ](https://software.intel.com/content/www/us/en/develop/articles/pin-a-binary-instrumentation-tool-downloads.html).
- There are `-m` and `-f` parameters as well, for blocking specific modules or functions. 
- For more details, use `python3 calltrace_wrapper.py -h`.

