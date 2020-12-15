# PyCG - Practical Python Call Graphs

PyCG generates call graphs for Python code using static analysis.
It efficiently supports
* Higher order functions
* Twisted class inherritance schemes
* Automatic discovery of imported modules for further analysis
* Nested definitions

You can read the full methodology as well as a complete evaluation on the
[ICSE 2021 paper](https://vitsalis.com/papers/pycg.pdf).

Abstract:
> Call graphs play an important role in different contexts, such as profiling and vulnerability propagation analysis. Generating call graphs in an efficient manner can be a challenging task when it comes to high-level languages that are modular and incorporate dynamic features and higher-order functions. Despite the language's popularity, there have been very few tools aiming to generate call graphs for Python programs. Worse, these tools suffer from several effectiveness issues that limit their practicality in realistic programs. We propose a pragmatic, static approach for call graph generation in Python. We compute all assignment relations between program identifiers of functions, variables, classes, and modules through an inter-procedural analysis. Based on these assignment relations, we produce the resulting call graph by resolving all calls to potentially invoked functions. Notably, the underlying analysis is designed to be efficient and scalable, handling several Python features, such as modules, generators, function closures, and multiple inheritance. We have evaluated our prototype implementation, which we call PyCG, using two benchmarks: a micro-benchmark suite containing small Python programs and a set of macro-benchmarks with several popular real-world Python packages. Our results indicate that PyCG can efficiently handle thousands of lines of code in less than a second (0.34 seconds for 1k LoC on average). Further, it outperforms the state-of-the-art for Python in both precision and recall: PyCG achieves high rates of precision ~99, and adequate recall ~69.3. Finally, we demonstrate how PyCG can aid dependency impact analysis by showcasing a potential enhancement to GitHub's security advisory notification service using a real-world example.

# Installation

PyCG is implemented in Python3 and has no dependencies. Simply:
```
pip install pycg
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

# Running Tests

From the root directory:
```
make test
```
