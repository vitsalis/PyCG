# Evaluation

Measures PyCG on two benchmarks and scores its call graphs: the
micro-benchmark (`micro-benchmark/` at the root of the repository) and the
macro-benchmark (`macro-benchmark/` here: 40 real packages with
hand-written ground truths). Standard library only. The analysed sources
are data: PyCG reads them, and no script imports or runs them.

## Commands

| Command | What it does |
|---|---|
| `make eval [BASE=<ref>]` | Builds the inputs image (the 40 sources, fetched by their pins), copies the sources into `macro-benchmark/projects/`, runs `common/loop.py run` on this checkout in a container without network, prints the summary and runs the gate (below); the graphs and `result.json` go to `$EVAL_OUT/pycg-<commit>/` (default `$TMPDIR/pycg-evaluation`) |
| `make eval-record [BASE=<ref>]` | Writes `metrics.json`: each best is the larger of the base's and the measured value (measures first if this commit has no result) |
| `make eval-diff BASE=<ref> [SUMMARY=<file>]` | Measures the engine of BASE on this checkout's benchmarks, runs `loop.py compare` between the two, and appends the Markdown summary (the values with their floors, the changes, the time and peak memory of each macro package) to SUMMARY (default standard output) |
| `make eval-determinism` | Measures this commit again with `PYTHONHASHSEED=1` for the analyses and fails unless every graph is byte-identical to that of seed 0 |
| `make eval-measure-pr`, `eval-measure-seed1`, `eval-measure-base BASE=<ref>`; `make eval-gate`, `eval-compare BASE=<ref>`, `eval-same-graphs`, `eval-labels BASE=<ref> [LABELS=<file>]` | The pieces of the targets above, which CI runs in separate jobs: each of the first three measures one result into `EVAL_OUT` without gating; the others check results that are there. `eval-labels` (`common/labels.py`) decides the labels `metrics-changed` and `benchmark-changed` of a pull request (AGENTS.md, "Protected files"), appends the decision to SUMMARY and writes `<label>=true|false` lines to LABELS |
| `python -I evaluation/common/loop.py compare OLD NEW` | Lists the edges and micro cases that changed between two result directories, scored again now (Python 3.14 or later) |
| `NAME=<project> docker compose -f evaluation/compose.yaml run --rm trace --compare` | Records the trace of one project again and compares it with the committed one (`macro-benchmark/README.md`, "Re-recording a trace") |

`make eval` measures the commit that is checked out: a checkout with
changes is refused. Its container has the repository read-only, no
network, 6 GiB of memory and `PYTHONHASHSEED=0`. The micro-benchmark runs
`EVAL_JOBS` cases at a time (default: the number of CPUs); the
macro-benchmark one project at a time, as its times and memory are
reported. CI measures the pull request, its second hash seed and its base
(`BASE=HEAD^1`, the first parent of the merge commit) in three parallel
jobs, then gates, compares, checks the two seeds and decides the labels
in one job; a last job, the only one that may write to the pull request,
sets or removes the labels. On a pull request these jobs run only when its
diff touches a path that can move the metrics (`tools/check.py
--detect-eval`, `make eval-changes`); the first job of CI decides it, and
writes the decision to the job summary. On a push they always run.

## The gate

`metrics.json` holds, for six values, the best value that main has
reached, the margin, and `benchmark_sha256`, the digest of the benchmark
on which the bests were measured: micro edge precision and recall (all
edges), and the macro-benchmark's precision and recall inside and outside
the package, summed over the 40 projects. `make eval` (`common/gate.py
check`) fails when a value is below its best minus the margin, when a run
failed, or when the digest is not that of this checkout. With `BASE`, it
also fails unless `metrics.json` is what `make eval-record` writes from the
base's file and this measurement: on the base's benchmark, floors only
rise; on a changed benchmark, the measured values are the new bests, and
the summary of the pull request says "benchmark changed: floors
re-based". Time and memory are reported, not gated.

The digest is `sha256sum FILES | sha256sum`, FILES sorted by path: the
files that a measurement reads besides the code of PyCG and of the
evaluation (`common/gate.py`, `benchmark_files`).

| Files | Why |
|---|---|
| `macro-benchmark/projects.toml` | The projects, their pins and their analysed packages |
| `macro-benchmark/ground-truth/<name>.json` of each project | The expected edges |
| `macro-benchmark/dynamic/<name>.json` of each project | Its `aliases` name callees outside the package |
| `common/same_function.json` | Names of one function, matched as one callee |
| `micro-benchmark/snippets/*/*/`: the `.py` files, `callgraph.json`, `requires-python` | The programs, their expected graphs, and which cases run |

The ledgers, notes and audits of a ground truth, the test environments
and the READMEs are not read by a measurement: a change of them keeps the
floors, and cannot re-base them.

## Layout

| Path | Content |
|---|---|
| `common/run.py` | Runs a PyCG checkout on both benchmarks, one child process per job, under a time limit (and, for a caller that gives one, a memory limit); records the wall time and peak memory of each job |
| `common/analyse.py` | The child process: one adapter per API flavour (`new`, and `original` for the 2021 engine, commit 046479e) |
| `common/score.py` | Scores call graphs against the ground truths |
| `common/loop.py` | `run`: run and score a checkout, print a summary; `compare`: what changed between two runs |
| `common/labels.py` | The labels of a pull request: a changed TP, FP or FN count; a changed protected file |
| `common/gate.py` | The gate: the values of a result against `metrics.json`, the new `metrics.json`, the summary of a pull request |
| `metrics.json` | The best value of each gated value, the margin, and the digest of the benchmark |
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

- **Macro-benchmark.** Per project and summed over the 40: tool edges,
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
