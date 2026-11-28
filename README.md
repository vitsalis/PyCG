# PyCG - Practical Python Call Graphs

[![CI](https://github.com/vitsalis/PyCG/actions/workflows/ci.yml/badge.svg)](https://github.com/vitsalis/PyCG/actions/workflows/ci.yml)

> **PyCG is maintained again.** The repository was archived in November
> 2023. Development restarted in 2026 with a new analysis for Python 3.12
> and later.

PyCG generates call graphs for Python code with a fully static analysis:
it never imports or runs the code that it analyses. The analysis follows
the values that a program passes around (functions, classes, instances,
containers), so it resolves

* calls through variables, arguments, return values, attributes and
  containers (higher-order code)
* methods through class hierarchies, `super()`, decorators, properties and
  descriptors
* the calls that the interpreter makes without a call expression (`for`,
  `with`, operators, subscripts, `await` and others)
* imports inside the package, followed automatically
* calls into code outside the package (the builtins, the standard library,
  other packages), named through type stubs

The analysis is fast on packages that use the standard library as external
code. It does not yet scale to programs that include large generic
libraries such as the standard library itself: see *Open problems* in
[docs/design.md](docs/design.md), which is the specification of the
analysis.

The first version of PyCG is described in the
[ICSE 2021 paper](https://arxiv.org/pdf/2103.00587.pdf). The analysis in
this repository is a redesign of it; that version is the tag
`baseline-original-engine`. [evaluation/](evaluation/README.md) measures
PyCG on the micro-benchmark and on a benchmark of real packages:
`make eval`.

You can cite PyCG as follows.
Vitalis Salis, Thodoris Sotiropoulos, Panos Louridas, Diomidis Spinellis and Dimitris Mitropoulos.
PyCG: Practical Call Graph Generation in Python.
In _43rd International Conference on Software Engineering, ICSE '21_,
25–28 May 2021.

# Installation

PyCG is one binary, `pycg`, written in Rust. It needs no Python to run and
reads Python 3.14 syntax. Install it with Cargo from this repository:
```
cargo install --git https://github.com/vitsalis/PyCG --locked pycg
```

Or from a checkout of it:
```
git clone https://github.com/vitsalis/PyCG
cd PyCG
cargo install --path crates/pycg --locked
```

Releases, on crates.io and as archives for each platform, come later.

The package `pycg` on PyPI is the 2021 version.

# Usage

```
~ >>> pycg -h
usage: pycg [-h] [--package PACKAGE] [--package-name PACKAGE_NAME]
            [--package-version PACKAGE_VERSION] [-o OUTPUT] [--cap N]
            [entry_point ...]

Write the call graph of a Python package as one JSON document.

positional arguments:
  entry_point           Entry points to be processed

options:
  -h, --help            show this help message and exit
  --package PACKAGE     Package root: module names are relative to it and only
                        modules under it are analysed. Default: the deepest
                        directory that contains every entry point
  --package-name PACKAGE_NAME
                        Name of the analysed package
  --package-version PACKAGE_VERSION
                        Version of the analysed package
  -o, --output OUTPUT   Output path
  --cap N               The most objects that the analysis keeps for one
                        variable or expression: past it the value is treated
                        as unknown, and calls through it are reported as
                        unresolved (saturated). 'none' removes the cap: the
                        analysis may then not finish, or run out of memory, on
                        large inputs. Default: 5000
```

A module that cannot be read or parsed is reported as failed, with a
warning, and analysed as an empty module.

`--cap` is the one setting of the analysis; the document records it.
`--cap none` gives the analysis without a cap, which may not finish on
large inputs.

# Output

PyCG writes one JSON document, specified in [docs/format.md](docs/format.md).
It lists the analysed modules, their definitions (modules, classes with
their MROs, functions), the names that each module exports, the outside
names that the code calls, and the call sites of each caller: the position
of each call, what it may call, the implicit calls (`for`, `with`,
operators, properties and others) by construct, and the calls whose callee
is not known, with the cause. The document is deterministic: the same
input gives the same bytes on every run and platform.

The classic call graph maps each node to the sorted names that it calls:
each definition that is not a class, and each outside name, is a node, and
a caller's callees are the union of the callees of its sites.

```
{
    "node1": ["node2", "node3"],
    "node2": ["node3"],
    "node3": []
}
```

# Examples

All the entry points are known:
```
~ >>> pycg --package pkg_root pkg_root/module1.py pkg_root/subpackage/module2.py -o cg.json
```

All entry points are not known, and the package is named in the document:
```
~ >>> pycg --package django --package-name django --package-version 5.2 \
        $(find django -type f -name "*.py") -o django.json
```

# Development

Install [Rust](https://rustup.rs/) (`rust-toolchain.toml` pins the
toolchain) and [uv](https://docs.astral.sh/uv/), which runs the Python of
the evaluation harness and the repository's tools. Then, from the root
directory:
```
make setup    # the environment of the harness and tools (uv sync --locked)
make test     # cargo test --locked, then the tests of the harness and tools
make lint     # ruff, no comments, cargo fmt --check, cargo clippy
make format   # ruff and cargo fmt
make check    # before pushing: lint, and the tests of what the change touches
```

The case harness checks the cases of `tests/cases/<family>/<name>/` (a
program, its request and the expected document) and every micro-benchmark
case. Each micro-benchmark case is a directory
`evaluation/micro-benchmark/snippets/<category>/<name>/` that contains a
`main.py` and the expected `callgraph.json`; the harness finds new case
directories automatically and names them `micro/<category>/<name>`. A
filter runs the cases whose name contains it, and `--exact` the one case of
that name:
```
cargo test -p pycg --test cases -- --exact micro/classes/call
```

The cases that the analysis fails are listed, each with its cause, in
`tests/known_failures.txt`, as strict expected failures. After a change to
the analysis, build the binary with `cargo build --release` and regenerate
the list with `python tests/triage.py`, which holds the causes. It removes
the cases that pass now and never adds a case by itself: a failing case
that is not in the list is a regression or a new case, and the tool
reports it and fails. Give such a case a cause in `tests/triage.py` and
add it with `--readmit <category>/<case>`.
