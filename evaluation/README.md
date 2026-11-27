# Evaluation

PyCG claims that its call graphs hold the calls that a program makes, and
few others. The evaluation checks that claim against what Python does when
the code runs, so that every change shows whether it makes PyCG better or
worse, and on which kind of code.

## Why each set exists

- **The micro-benchmark** isolates one language feature per program. A
  case that fails names the feature that PyCG gets wrong, which a large
  program cannot do. It grew from the benchmark of PyCG's 2021 paper, so
  the two analyses compare on it.
- **The macro-benchmark** is real code, where the features mix and most
  calls cross modules and classes. It shows how well PyCG does on the
  packages that people analyse, both on calls inside the package and on
  calls into code outside it.
- **The dynamic traces** check the macro-benchmark's ground truths. A
  hand-written ground truth can miss a call; a trace of the package's own
  test suite records calls that really happen, so every traced call must
  be in the ground truth.
- **The scale set** shows whether PyCG finishes on large packages, and in
  how much time and memory. The benchmarks' packages are small enough to
  analyse in seconds, so they cannot show that.

## The sets

**Micro-benchmark.** Small programs, one language feature each, grouped by
kind of feature. Each comes with the call graph that Python gives when it
runs.

**Macro-benchmark.** 60 real packages at pinned releases. Each has a
hand-written call graph of its source, built site by site from the source
and, where the package's tests run, checked against its trace.

**Dynamic traces.** For each macro-benchmark package whose tests run, the
calls that the package made while its own test suite ran: a lower bound
of its call graph.

**Scale set.** 20 large packages, pinned by release or commit, on which
the time and peak memory of an analysis are measured, and whether it
finishes under a memory cap. They have no ground truth and are not
scored.

The directory of each set has a README with its internals.

## Results

Precision is the share of PyCG's edges that are in the ground truth; recall
is the share of the ground truth's edges that PyCG finds. On the
macro-benchmark, "inside" counts the edges whose callee is in the analysed
package, and "outside" the edges to builtins, the standard library and
other packages, whose names depend on how a tool models code that it does
not analyse. The macro-benchmark's values sum the counts over the 60
packages.

The best values that main has reached:

| Set | Precision | Recall |
|---|---|---|
| Micro-benchmark, all edges | 0.9525 | 0.9493 |
| Macro-benchmark, inside the package | 0.9262 | 0.8799 |
| Macro-benchmark, outside the package | 0.9374 | 0.8217 |

Every change is measured against its base on these values, and none may
fall more than 0.01 below the base's.
