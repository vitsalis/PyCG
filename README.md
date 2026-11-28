# PyCG - Practical Python Call Graphs

[![CI](https://github.com/vitsalis/PyCG/actions/workflows/ci.yml/badge.svg)](https://github.com/vitsalis/PyCG/actions/workflows/ci.yml)

PyCG generates the call graph of a Python package with a fully static
analysis: it never imports or runs the code that it analyses. It follows the
values that a program passes around (functions, classes, instances,
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

[docs/design.md](docs/design.md) describes the analysis.

## Results

Measured by CI on main at commit 4564f944:

| Set | Precision | Recall |
|---|---|---|
| Micro-benchmark, all edges | 0.952 | 0.950 |
| Macro-benchmark, inside the package | 0.926 | 0.880 |
| Macro-benchmark, outside the package | 0.938 | 0.821 |

The micro-benchmark has one small program per language feature; the
macro-benchmark has 60 real packages with hand-written call graphs. On 20
large packages PyCG finishes 19, each in under 4 minutes.
[evaluation/](evaluation/README.md) describes the sets and how they were
built.

## Installation

PyCG is one binary, `pycg`, written in Rust. It needs no Python to run and
reads Python 3.14 syntax. Install it with Cargo from this repository:

```
cargo install --git https://github.com/vitsalis/PyCG --locked pycg
```

or from a checkout of it:

```
cargo install --path crates/pycg --locked
```

Releases come later. The package `pycg` on PyPI is the 2021 version.

## Usage

```
pycg --package pkg pkg/module1.py pkg/subpackage/module2.py -o cg.json
```

`pycg --help` lists the options. `--cap` is the one setting of the analysis:
the most values it keeps for one variable or expression before it treats
the value as unknown (5,000 by default). A module that cannot be read or
parsed is reported as failed, with a warning, and analysed as an empty
module.

## Output

PyCG writes one JSON document, specified in [docs/format.md](docs/format.md):
the analysed modules, their definitions, the names that each module exports,
the outside names that the code calls, and the call sites of each caller
with what each may call, the implicit calls by construct, and the calls
whose callee is not known, with the cause. The document is deterministic. In
the classic call graph, a caller's callees are the union of the callees of
its sites.

## Limits

- **No flow-sensitive heap.** An attribute or container element holds
  every value ever stored there, so `d["k"] = a; d["k"] = b; d["k"]()`
  calls both.
- **No calling context.** A parameter holds what every caller passes, so a
  helper that forwards its arguments mixes the values of all its callers.
- **No model of what outside code calls.** A function given to outside
  code (a thread target, a callback) gets no edge from that code; if no
  analysed code calls it, it is an entry point and its body is analysed.
- **No code built at run time.** `eval`, `exec`, and attribute names
  computed from more than four strings are not followed, so the calls that
  they make give no edges.
- **No scale to the standard library as analysed code.** The analysis is
  fast on packages that use the standard library as outside code, but does
  not finish when the standard library itself is analysed.

## History and citation

The first version of PyCG is described in the
[ICSE 2021 paper](https://arxiv.org/pdf/2103.00587.pdf). The repository was
archived in November 2023; development restarted in 2026 with a redesigned
analysis for Python 3.12 and later, and the 2021 analysis is the tag
`baseline-original-engine`.

You can cite PyCG as follows.
Vitalis Salis, Thodoris Sotiropoulos, Panos Louridas, Diomidis Spinellis and
Dimitris Mitropoulos.
PyCG: Practical Call Graph Generation in Python.
In _43rd International Conference on Software Engineering, ICSE '21_,
25–28 May 2021.
