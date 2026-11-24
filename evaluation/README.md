# Evaluation

Measures PyCG on two benchmarks and scores its call graphs: the
micro-benchmark (`micro-benchmark/` at the root of the repository) and the
macro-benchmark (`macro-benchmark/` here: 30 real packages with
hand-written ground truths). Standard library only. The analysed sources
are data: PyCG reads them, and no script imports or runs them.

## Commands

| Command | What it does |
|---|---|
| `make eval` | Builds the inputs image (the 30 sources, fetched by their pins), copies the sources into `macro-benchmark/projects/`, then runs `common/loop.py run` on this checkout in a container without network and prints the summary; the graphs and `result.json` go to `$EVAL_OUT/pycg-<commit>/` (default `$TMPDIR/pycg-evaluation`) |
| `python -I evaluation/common/loop.py compare OLD NEW` | Lists the edges and micro cases that changed between two such directories, scored again now (Python 3.14 or later) |
| `NAME=<project> docker compose -f evaluation/compose.yaml run --rm trace --compare` | Records the trace of one project again and compares it with the committed one (`macro-benchmark/README.md`, "Re-recording a trace") |

`make eval` measures the commit that is checked out: a checkout with
changes is refused. Its container has the repository read-only, no
network, 6 GiB of memory and `PYTHONHASHSEED=0`.

## Layout

| Path | Content |
|---|---|
| `common/run.py` | Runs a PyCG checkout on both benchmarks, one child process per job, under a time limit (and, for a caller that gives one, a memory limit); records the wall time and peak memory of each job |
| `common/analyse.py` | The child process: one adapter per API flavour (`new`, and `original` for the 2021 engine, commit 046479e) |
| `common/score.py` | Scores call graphs against the ground truths |
| `common/loop.py` | `run`: run and score a checkout, print a summary; `compare`: what changed between two runs |
| `common/same_function.json` | Names of one function of the standard library, which the scorer matches as one callee |
| `common/lookup.py` | The static lookup of standard-library names that `tests/test_same_function_table.py` checks the table with |
| `macro-benchmark/` | The projects, ground truths, traces and their tools (`macro-benchmark/README.md`) |
| `compose.yaml`, `container/Dockerfile.inputs`, `container/fetch.py` | The inputs image: the sources of the macro-benchmark, fetched when the image is built |
| `container/Dockerfile.trace`, `container/trace_entry.py`, `container/trace.sh`, `container/trace_helper.py`, `container/entry.sh` | Records the trace of one project in a container |
| `results/trace/` | Where the `trace` service writes a new trace (git ignores its content) |
| `tests/` | The tests of the scripts; `make test` runs them |

The scripts load each other by path: `evaluation/` is not a Python
package. The micro-benchmark's place is `macro-benchmark/projects.py`,
`MICRO_BENCHMARK`.

## How the scores are computed

The headline is the edges whose callee is inside the analysed package.
Edges to callees outside it (builtins, the standard library, third-party
code) are reported apart: their names depend on how a tool models code
that it does not analyse.

- **Macro-benchmark.** Per project and summed over the 30: tool edges,
  ground-truth edges, true and false positives, false negatives,
  precision, recall and F1, for the edges inside the package, outside it,
  and all. The sums add the counts, then compute precision and recall.
- **Micro-benchmark.** Per case: complete (no false positive), sound (no
  false negative) and exact (the graph equals the ground truth, nodes
  included, as `tests/test_micro_benchmark.py` compares them). A case whose
  `requires-python` is newer than the interpreter is skipped.
- **Runs.** Each job's status (ok, crash with the error and where it
  happened, timeout, memory), wall time and peak resident set size. A run
  that failed scores no edge: its ground-truth edges are false negatives.

### How names are matched

Two modes are reported. **Raw**: the names as written, except that a
callee outside the package that the project's trace knows
(`macro-benchmark/dynamic/<name>.json`, `aliases`) counts as the function
it resolves to, and a callee outside the package that is in a group of
`common/same_function.json` counts as the group's representative. Nothing
is imported while scoring, so the scores do not depend on the interpreter.
**Normalised**: the raw matching after the renamings of `NORMALISATIONS` in
`common/score.py`, each of which keeps the function that an edge refers
to. `loop.py run` prints the raw mode.

## Isolation

Each analysis runs in `python -S -s -P -B evaluation/common/analyse.py`
with the checkout first on `sys.path`, in a new temporary directory, with
an environment of `PYTHONHASHSEED` alone. The benchmark sources are
fetched only in the build of the inputs image, by their pins, without
running them. A trace runs a project's tests in a container without
network, with a read-only root and a non-root user.
