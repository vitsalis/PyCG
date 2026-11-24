# Evaluation

Measures PyCG on two benchmarks and scores its call graphs: the
micro-benchmark (`micro-benchmark/` here) and the
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
| `make eval-measure-pr`, `eval-measure-seed1`, `eval-measure-base BASE=<ref>`; `make eval-gate`, `eval-compare BASE=<ref>`, `eval-same-graphs`, `eval-labels BASE=<ref> [LABELS=<file>]` | The pieces of the targets above, which CI runs in separate jobs: each of the first three measures one result into `EVAL_OUT` without gating; the others check results that are there. `eval-labels` (`common/labels.py`) decides the labels `metrics-changed` (a TP, FP or FN count of the micro-benchmark or of the macro-benchmark inside or outside the package differs from the base's) and `benchmark-changed` (a changed path is protected: `PROTECTED` of `labels.py` lists the paths of AGENTS.md, "Protected files") of a pull request, appends the decision to SUMMARY and writes `<label>=true|false` lines to LABELS |
| `python -I evaluation/common/loop.py compare OLD NEW` | Lists the edges and micro cases that changed between two result directories, scored again now (Python 3.14 or later) |
| `NAME=<project> docker compose -f evaluation/compose.yaml run --rm trace --compare` | Records the trace of one project again and compares it with the committed one (`macro-benchmark/README.md`, "Re-recording a trace") |

`loop.py run` runs the checkout on both benchmarks (`run.py`, into
`OUT/NAME`), scores the graphs (`score.py`, into `OUT/NAME/result.json`) and
prints a summary in raw names: the micro-benchmark (cases, exact cases,
edge precision and recall), the macro-benchmark inside the package and
outside it (precision, recall and F1 per project and summed), and the runs
that failed. The micro-benchmark runs `--micro-jobs` cases at a time; the
macro-benchmark one project at a time, as its times and memory are
reported. `loop.py compare` reads two such directories (the same tool at
two commits) and lists, per project of the macro-benchmark, the edges that
became true positives, stopped being true positives, became false
positives and stopped being false positives (raw names; `[in]` marks a
callee inside the package), and the micro-benchmark cases that became or
stopped being exact. A run that failed or is absent on either side is no
measurement: its edges are neither lost nor gained. `compare` never reads
`result.json`: it scores both graph directories again, now, with today's
table of names of one function, and says which (its SHA-256, also under
`scorer` in `--json`).

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
re-based". A base without `metrics.json` (an empty base file) has no
floors to check. Every `metrics.json` carries `benchmark_sha256`: the gate
fails with an assertion on one without it. `gate.py summary` writes the Markdown of a pull request: each value of the
base and of the result with its floor, whether the benchmark changed, the
changes that `loop.py compare` wrote, and the time and peak memory of each
macro package. Time and memory are reported, not gated.

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
| `micro-benchmark/` | One small program per language feature with its ground truth, and the validator that runs them (`micro-benchmark/README.md`) |
| `macro-benchmark/` | The projects, ground truths, traces and their tools (`macro-benchmark/README.md`) |
| `compose.yaml`, `container/Dockerfile.inputs`, `container/fetch.py` | The inputs image: the sources of the macro-benchmark, fetched when the image is built |
| `container/Dockerfile.trace`, `container/trace_entry.py`, `container/trace.sh`, `container/trace_helper.py`, `container/entry.sh` | Records the trace of one project in a container |
| `results/trace/` | Where the `trace` service writes a new trace (git ignores its content) |
| `tests/` | The tests of the scripts; `make test` runs them |

The scripts load each other by path: `evaluation/` is not a Python package.
The standard library has no YAML parser, so `compose.yaml` keeps to plain
YAML (mappings, lists of scalars, JSON lists, anchors, aliases and merge
keys): `tests/test_compose.py` reads that much. The micro-benchmark's place
is `macro-benchmark/projects.py`, `MICRO_BENCHMARK`.

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
`tests/test_same_function_table.py` checks, on the interpreter that runs
it, that every group names one object of its standard library and that
the table is in order. A name that the interpreter lacks fails the test,
unless `FIRST_VERSION_BY_NAME_ABSENT_ON_PURPOSE` exempts it (it exempts
none). CI runs it on Python 3.12 to 3.15, so the table holds only groups
that are one object on every supported CPython.

`common/lookup.py`, which that test uses, looks names of the standard
library up by static inspection; the scoring does not use it, because
what a name finds can depend on what was imported before. `resolve(name)`
gives `("object", function)`, `("missing", last object found)` or
`("unknown", None)`. It imports only the longest dotted prefix of the name
that is in `ALLOWED_MODULES` (`<builtin>` is the builtins module), with
warnings ignored: standard-library modules and submodules that do nothing
but define names when imported. A name through any other module
(third-party, a `__main__` entry point, `antigravity`, `this`, a GUI
toolkit) is not looked up. An allowed module may still import others and
initialise its own objects when it is imported. The rest of the name is
looked up in the `__dict__` of each object: of a module (a submodule is
never taken from it: it is there only if something imported it), of a
class and its MRO (not its metaclass), of an instance and then its type
(`inspect.getattr_static`). No property, descriptor or `__getattr__` runs.
A path through a function or method (its return value) is missing: the
attributes of a function are not callees. The function of the object
found is the one that a call through it runs, found without calling
anything: a static or class method is its function, a property its
getter, a bound method its function, a method bound to an object of a
builtin type the descriptor of that type (or itself, when the type holds
this very builtin, as `object.__new__`); a function, a class or a
descriptor of a builtin type is itself. Anything else (a module, an object
that is not callable, a cached property) has no function. Any exception
makes the name unknown.
**Normalised**: the raw matching after the renamings of `NORMALISATIONS` in
`common/score.py`, each of which keeps the function that an edge refers
to. `loop.py run` prints the raw mode.

### The scorer

`common/score.py` scores a tool directory in the layout that `run.py`
writes: `macro/<project>.json` and `micro/<category>/<case>.json`, each a
call graph `{caller: [callees]}`, and optionally `<benchmark>/runs.json`
with the status of each run. Graphs of other tools in this layout are
scored too; without `runs.json` a missing graph counts as a failed run, and
a run that `runs.json` records as ok but whose graph is gone is a failed
run too (`missing graph`). Every failed run is listed with the error and
its place from the run record when it has them. The macro-benchmark keeps
every run record; the micro-benchmark a summary of the statuses, times and
memory, with the runs that did not finish. The projects scored are those
of `projects.toml` that have a ground truth; the benchmark directory is
the directory of `projects.toml`, with `projects/`, `ground-truth/` and
`dynamic/`.

Edges are compared as sets of matched (caller, callee) pairs, and every
tool edge is scored. "inside" are the edges whose callee is in the
packages, by name; "outside" the others; "all" is kept for comparison with
PyCG's 2021 evaluation. A false positive or negative is listed once, by its
matched names, with its spellings when the names in the graph differ. The
nodes are compared too: those of the ground truth that the tool lacks, and
the tool's nodes in the package that the ground truth lacks.

Callers are matched as written: the trace and the table apply to callees
only. A name in the analysed packages never changes, and nor does a name
whose representative would be in them. A name that the trace gives to two
or more callees identifies none of them: classes that a library creates at
run time can share one qualified name (each `type("Call", (Base,),
{"__call__": staticmethod(f)})` is another class named `lib.Call`), and then
`lib.Call.__call__` is a name of every `f`. Such a name is matched by
string equality, after the table of names of one function, as any name.
The normalised mode renames a class-body caller to the scope that runs the
class body (the nearest enclosing function, else the module), unless the
class name is also a module or function of the ground truth; the classes
are read from the analysed source with `ast`, and a file that does not
parse (Python 2 code) is skipped.

As in PyCG's 2021 evaluation, a micro-benchmark graph is complete if every
edge it reports is in the ground truth and sound if it reports every edge
of the ground truth, all edges counted. Without a graph, complete, sound
and exact are all false. A result records under `scorer` the SHA-256 of
the table of names of one function, which the counts depend on, and the
interpreter, which they do not.

## The runner

`common/run.py` runs a PyCG checkout on both benchmarks and keeps its call
graphs.

| Benchmark | Jobs |
|---|---|
| micro | Every case of `micro-benchmark/snippets`: the entry point is `main.py`, the package root the case directory. A case whose `requires-python` is newer than the interpreter is skipped |
| macro | Every project of `macro-benchmark/projects.toml`: the entry points are all modules of the analysed source, the package root is the project's `root`. A project whose source is not there is skipped |

The runner reads the jobs of every benchmark before it runs any, so that
`projects.toml` and its pins are checked before the first run. It loads
only `macro-benchmark/projects.py`, not the tracer, which needs Python
3.14, so that it works on Python 3.12 and later. A checkout with changes
(`git status --porcelain` not empty), or not under git, is refused unless
`--allow-dirty`: the recorded commit must say which code ran. It writes
`OUT/NAME/BENCHMARK/runs.json` (the tool, the benchmark commit and, for
each job, its status, wall time and peak memory) and one graph per job
that finished: `OUT/NAME/micro/<category>/<case>.json`,
`OUT/NAME/macro/<project>.json`. `OUT` is `$TMPDIR/pycg-evaluation` by
default, outside the repository; a graph that would be outside `OUT/NAME`
(a project name with `..`) is refused. The JSON files have each container
of scalars on one line: deterministic, and one edge or one case per line
in a diff. The timeout, 1800 seconds per job by default, is the one limit
of every run.

**The child.** Each job runs in its own child interpreter, `python -S -s -P
-B common/analyse.py REQUEST.json`. `-S`: no `site` module, so no `.pth`
file and no `sitecustomize` runs (an installed package that is the
analysed target could); `-s`: no user site-packages; `-P`: neither the
script directory nor the working directory on `sys.path`; `-B`: no
bytecode in the checkout. Not `-E`: it would drop `PYTHONHASHSEED`, the
only variable of the environment (`--hash-seed`, default 0: the original
analysis iterates over sets, and its result depends on the hash seed).
`analyse.py` puts the checkout first on `sys.path` itself and builds the
generator with the adapter of the API flavour (`--flavour`). The request
has `checkout`, `flavour`, `entry_points`, `package` (the package root),
`graph` (where to write the call graph) and `result` (where to write the
status). The call graph is `{caller: [callees]}`, sorted. The result is
`{"status": "ok"}` or `{"status": "crash", "error": ..., "where": ...}`,
with `seconds` (construction, analysis and output) and `peak_rss_mib`, the
peak resident set size of the child: on Linux `VmHWM`, which starts again
at exec, not `ru_maxrss`, which keeps the parent's (elsewhere `ru_maxrss`,
in bytes on macOS). `where` is the innermost frame in the checkout,
relative to it, else the innermost frame. A child that dies before it
writes its result is a crash, with its exit status and the last line of
its standard error.

**Paths.** The child runs in a new temporary directory, so every path that
it gets is made absolute, the graph's included, and a graph of an earlier
run is removed first. Directories (the checkout, the package root, the
directory of each entry point) are resolved as the file system does: the
path is split first, so that `link/../a.py` is `a.py` in the parent of the
link's target. A file keeps its name, a link included (a symbolic link
`b.py` to `a.py` is the module `b`), and so does the interpreter, when it
is a path and not a name looked up on `PATH` (the interpreter of a virtual
environment is a link).

**Limits.** Standard error goes to a file: a pipe that nobody reads while
the parent watches the child could fill and block it. The child starts a
new session, so it leads a process group of its own, which holds every
process that it starts (unless one of them starts a session of its own).
The parent looks at whether the child has ended with pauses that double
from 1 ms up to 10 ms: the wall time of a run is measured to that
resolution, and is the end that the parent saw, before the cleanup. It
stops the child past the timeout (status `timeout`) or, for a caller that
gives a memory limit, when a sample of the resident set size of its
process group (the child and the processes it started), taken at once and
then every 0.2 seconds, is over the limit (status `memory`). The size of a
group is the sum of the resident set sizes of its processes, in MiB
rounded to 0.1: on Linux, of the processes whose `/proc/<pid>/stat` names
the group (the third field after the name, which ends at the last `)`: a
name is any bytes); on macOS, of those that `proc_listpgrppids` of libproc
lists, into a buffer of 4096 pids that doubles while it is full. Memory
that two processes share after a fork counts in each. An ended process
that is not yet reaped (a zombie) holds no memory: on Linux its
`/proc/<pid>/statm` is all zeros; macOS's `proc_pid_rusage` still reports
its last resident size, so a process with an exit time counts as ended. If
the group, or a process of it that is there, cannot be read, the run stops
with status `unmeasured`: an unread memory is not an empty one. The
largest sample replaces the child's own peak when it is larger: the group
held more than the child.

**Ending a child.** The parent sees that the child has ended without
reaping it (`waitid` with `WNOWAIT`; macOS before Python 3.13 has no
`os.waitid`, so the runner calls the C function, whose `siginfo_t` has
`si_code` at byte 8 and `si_pid` at byte 12, 0 while the child runs). A
stopped child has not ended; macOS reports a stopped child too, though
only ended ones are asked for. Until the child is reaped, its pid, which
is the id of its process group, cannot go to another process, so the
`SIGKILL` that the parent then sends to the group cannot reach a group
that reuses the id. The other processes of the group are reaped by their
new parent. The group is killed also on an exception or an interrupt of
the parent. macOS refuses (EPERM) to signal a group that holds the ended,
unreaped child alone, which is harmless when no member of the group is
alive. After such a refusal the runner lists the live members of the group
and sends each `SIGKILL`, three times (a member can start another),
waiting up to a second each time (a killed process does not end at once),
and lists them once more; a process that cannot be read counts as alive.
If one is alive, the status is `cleanup failed`, with the signals sent and
denied and the members gone and still alive, after the child had 5
seconds to end. If the group cannot be listed, the child alone is killed:
it is not reaped, so it is there.

**Parallel jobs.** The runner runs the jobs of a benchmark `workers` at a
time in threads and keeps the records in the order of the jobs, whatever
the order in which they end. Each job keeps its own limits: a child is
watched by the thread that started it. The first exception of a job, as
soon as it comes, or an interrupt (Ctrl-C reaches the main thread only)
starts no other job and kills the process group of every child that runs
now; the thread of each child sees it end, kills what is left and reaps
it. A thread counts its job as running before it checks whether to start
it, so that the cleanup waits for it, and the cleanup kills again until no
job runs: an interrupt can come before `submit()` returns the future of a
job that runs.

## Isolation

Each analysis runs in `python -S -s -P -B evaluation/common/analyse.py`
with the checkout first on `sys.path`, in a new temporary directory, with
an environment of `PYTHONHASHSEED` alone. The benchmark sources are
fetched only in the build of the inputs image, by their pins, without
running them. A trace runs a project's tests in a container without
network, with a read-only root and a non-root user.

Git and every download run only in a container, never on the host (the
maintainer's rule of 2026-11-14): the repository holds no submodule,
`projects.toml` is the only lock of every source of the benchmark, and the
maintenance commands that need the network run in the target `maintain` of
`container/Dockerfile.inputs`. `tests/test_no_host_git.py` keeps an
inventory of every place in `evaluation/` (but its tests, the copied
sources and the micro-benchmark's snippets) that writes a git command line
(a list or tuple whose first item is `"git"`) or imports a network client, each stated as git on our own
checkout, a step of the build of the inputs image, or a step of the
maintenance image. A new place fails the test until it is stated, and a
stated place that is gone fails it too. It reads the syntax trees only: it
is a guard, not a proof.

## The inputs image

`container/fetch.py macro DESTINATION`, a step of the build of the inputs
image, is the only place where git runs on third-party content. It writes
each project of `projects.toml` to `DESTINATION/<name>`. A git source is
fetched at its one pinned commit into a bare repository (`git fetch
--depth 1 URL COMMIT`, https only, no configuration of the user or the
system, no hooks, no submodules, every received object checked by git) and
written as the plain files of the commit's tree, without `.git`: the bytes
and modes of its blobs, a link as a link, a nested submodule not fetched.
No checkout runs, so no attribute, filter or hook of the fetched
repository applies. An sdist is downloaded, checked against its SHA-256
and unpacked with tarfile's `data` filter; the archive is not kept.
Nothing fetched is run. A source that is not its pin is not written, and
the command fails, so the build fails.
