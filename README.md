# PyCG - Python Call Graphs

PyCG generates call graphs for Python code using static analysis.
Given a list of Python files as input it:
- Traverses the AST of the Python module
- Discovers the local modules it imports and further analyzes them
- Tracks namespaces and scopes of modules, classes and functions
- Builds the MRO of each class
- Constructs an assignment graph allowing it to parse higher-order functions

# Installation

PyCG is implemented in Python3 and has no dependencies.
From the root directory:
```
python3 setup.py install
```

# Usage

```
~ >>> pycg -h
usage: pycg [-h] [--package PACKAGE] [--fasten] [--product PRODUCT]
            [--forge FORGE] [--version VERSION] [--timestamp TIMESTAMP]
            [-o OUTPUT]
            [entry_point [entry_point ...]]

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
  -o OUTPUT, --output OUTPUT
                        Output path
```

where the command line arguments are:

- `entry_point`: A list of paths to Python modules that PyCG will analyze.
  It is suggested that this list of paths contains only entry points
  since PyCG automatically discovers all other (local) imported modules.
- `--package`: The unix path to the module's namespace (i.e. the path from
  which the module would be executed). This parameter is really important for
  the correct resolving of imports.
- `--fasten`: Output the callgraph in FASTEN format.
- `-output`: The unix path where the output call graph will be stored in JSON
  format.

The following command line arguments should used only when `--fasten` is
provied:

- `--product`: The name of the package.
- `--forge`: Source the package was downloaded from.
- `--version`: The version of the package.
- `--timestamp` : The timestamp of the package's version.

# Output

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

# Benchmark

We provide an benchmark of minimal snippets of Python code
testing a wide variety of the features that Python provides.

We organize this benchmark into the following categories:

| Category       | No. Tests | Description                                   |
|----------------|-----------|-----------------------------------------------|
| parameters     | 6         | Positional arguments that are functions       |
| assignments    | 5         | Assignment of functions to variables          |
| built-ins      | 3         | Calls to built in functions and data types    |
| classes        | 22        | Class construction, attributes, methods       |
| comprehensions | 1         | Comprehensions                                |
| decorators     | 7         | Function decorators                           |
| dicts          | 5         | Hashmap with values that are functions        |
| direct calls   | 4         | Direct call of a returned function (func()()) |
| exceptions     | 3         | Exceptions                                    |
| eval           | 1         | Usage of eval                                 |
| functions      | 4         | Vanilla function calls                        |
| generators     | 2         | Generators                                    |
| imports        | 13        | Imported modules, functions classes           |
| kwargs         | 3         | Keyword arguments that are functions          |
| lambdas        | 5         | Lambdas                                       |
| mro            | 7         | Method Resolution Order (mro)                 |
| returns        | 4         | Returns that are functions                    |

This benchmark is not dependent on PyCG and can be used to test
other Python call graph generation tools.


# Running Tests & Benchmarks

From the root directory:
```
make test
```
