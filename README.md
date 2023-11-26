# PyCG - Practical Python Call Graphs

[![Linters](https://github.com/vitsalis/PyCG/actions/workflows/linters.yml/badge.svg)](https://github.com/vitsalis/PyCG/actions/workflows/linters.yml)
[![Tests](https://github.com/vitsalis/PyCG/actions/workflows/test.yaml/badge.svg)](https://github.com/vitsalis/PyCG/actions/workflows/test.yaml)

PyCG generates call graphs for Python code using static analysis.
It efficiently supports
* Higher order functions
* Twisted class inheritance schemes
* Automatic discovery of imported modules for further analysis
* Nested definitions

You can read the full methodology as well as a complete evaluation on the
[ICSE 2021 paper](https://arxiv.org/pdf/2103.00587.pdf).

You can cite PyCG as follows.
Vitalis Salis, Thodoris Sotiropoulos, Panos Louridas, Diomidis Spinellis and Dimitris Mitropoulos.
PyCG: Practical Call Graph Generation in Python.
In _43rd International Conference on Software Engineering, ICSE '21_,
25–28 May 2021.

> **PyCG** is archived. Due to limited availability, no further development
> improvements are planned. Happy to help anyone that wants to create a fork to
> continue development.

# Installation

PyCG is implemented in Python3 and requires Python version 3.4 or higher.
It also has no dependencies. Simply:
```
pip install pycg
```

# Usage

```
~ >>> pycg -h
usage: __main__.py [-h] [--package PACKAGE] [--fasten] [--product PRODUCT]
                        [--forge FORGE] [--version VERSION] [--timestamp TIMESTAMP]
                        [--max-iter MAX_ITER] [--operation {call-graph,key-error}]
                        [--as-graph-output AS_GRAPH_OUTPUT] [-o OUTPUT]
                        [entry_point ...]

positional arguments:
  entry_point           Entry points to be processed

optional arguments:
  -h, --help            show this help message and exit
  --package PACKAGE     Package containing the code to be analyzed
  --fasten              Produce call graph using the FASTEN format
  --product PRODUCT     Package name
  --forge FORGE         Source the product was downloaded from
  --version VERSION     Version of the product
  --timestamp TIMESTAMP
                        Timestamp of the package's version
  --max-iter MAX_ITER   Maximum number of iterations through source code. If not specified a fix-point iteration will be performed.
  --operation {call-graph,key-error}
                        Operation to perform. Choose call-graph for call graph generation (default) or key-error for key error detection on dictionaries.
  --as-graph-output AS_GRAPH_OUTPUT
                        Output for the assignment graph
  -o OUTPUT, --output OUTPUT
                        Output path
```

The following command line arguments should used only when `--fasten` is
provied:

- `--product`: The name of the package.
- `--forge`: Source the package was downloaded from.
- `--version`: The version of the package.
- `--timestamp` : The timestamp of the package's version.

# Call Graph Output

## Simple JSON format

The call edges are in the form of an adjacency list where an edge `(src, dst)`
is represented as an entry of `dst` in the list assigned to key `src`:

```
{
    "node1": ["node2", "node3"],
    "node2": ["node3"],
    "node3": []
}
```

## FASTEN Format

For an up-to-date description of the FASTEN format refer to the
[FASTEN
wiki](https://github.com/fasten-project/fasten/wiki/Extended-Revision-Call-Graph-format#python).

# Key Errors Output

We are currently experimenting on identifying potential invalid dictionary
accesses on Python dictionaries (key errors).
The output format for key errors is a list of dictionaries containing:
- The file name in which the key error was identified
- The line number inside the file
- The namespace of the accessed dictionary
- The key used to access the dictionary

```
[{
    "filename": "mod.py",
    "lineno": 2,
    "namespace": "mod.<dict1>",
    "key": "key2"
},
{
    "filename": "mod.py",
    "lineno": 8,
    "namespace": "mod.<dict1>",
    "key": "nokey"
}]
```

# Examples

All the entry points are known and we want the simple JSON format
```
~ >>> pycg --package pkg_root pkg_root/module1.py pkg_root/subpackage/module2.py -o cg.json
```

All entry points are not known and we want the simple JSON format
```
~ >>> pycg --package django $(find django -type f -name "*.py") -o django.json
```

We want the FASTEN format:
```
~ >>> pycg --package pypi_pkg --fasten --product "pypipkg" --forge "PyPI" \
        --version "0.1" --timestamp 42 \
        pypi_pkg/module1.py pkg_root/subpackage/module2.py -o cg.json
```

# Running Tests

From the root directory, first install the [mock](https://pypi.org/project/mock/) package:
```
pip3 install mock
```
Τhen, simply run the tests by executing:
```
make test
```
