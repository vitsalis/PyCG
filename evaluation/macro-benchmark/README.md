# Macro-benchmark

Sixty real Python packages at pinned releases (`projects.toml`, `batch`):
thirty in six batches of five, and batches 6, 7 and 8, ten packages each.
Each package gets a
hand-written call graph of its source, the ground truth. It is written as a
call-site ledger: one entry per place in the source that can call a
function, with the callees of that site. A naive list of candidate callees
by name, for every site, protects the ledger against missing edges by
construction. To check a ground truth further, `trace.py` records the calls
that the package makes while its own test suite runs. A trace is a lower
bound: every edge of the trace must be in the ground truth. The ground truth
also has the calls that no test makes.

The first full audit (audit record `2026-11-15/README.md`) reviewed all 17,618
original edges and corrected 122 false positives and 453 missed edges.
The second full audit (audit record `2026-11-15/pass-2/README.md`) reviewed the
resulting 17,949 edges under the same global rules. It removes 70 false
positives and adds 60 missed edges, giving 17,939 edges on the same 5,464
nodes. Its separate added-edge file and application patch preserve the
changes for review.

The third full audit (audit record `2026-11-15/pass-3/README.md`) reviewed those
17,939 edges under the same global rules. It removes one false positive
and adds 124 missed edges, giving 18,062 edges on the same 5,464 nodes.
Its reports, added-edge register, patch and retained evidence preserve the
changes for review. Its 124 missed edges triggered the fourth audit.

The fourth full audit (audit record `2026-11-16/pass-4/README.md`) reviewed all
18,062 baseline edges. It removes 1 false positive and adds
60 missed edges, giving 18,121 edges on the same 5,464 nodes.
It also corrects 22 independent metadata groups. The audit retains
source models, coverage records, edge witnesses, independent reviews and
an exact patch. Its added-edge register (audit record `2026-11-16/pass-4/added-edges.json`)
records every added pair. The dated batch tables below remain historical;
the fourth audit gives the current counts for all 30 projects.
Neither revised threshold is exceeded, so the repeat loop stops after this round.

After the audit, one correction: fabric's ground truth named
`invoke.config.Config.set_runtime_ssh_path` and `.load_ssh_config` for the
`self.config` of a `Fab` without `config_class` (`main.py:112-113`). invoke's
`Config` has neither method (invoke 1.0.0, 1.4.1, 1.7.3), so Python calls
nothing there. The two callees left the ledger; the ground truths have
18,119 edges.

The audit records (the reports, registers, patches and evidence of the four
rounds) are not in this repository: they hold copies of third-party sources.
The maintainer keeps them. A reference to an "audit record" names a file of
those records.

The repeat rule was revised on 2026-11-16: after a complete audit, repeat
only if it finds more than 100 missed edges or more than 20 false positives.
The thresholds are strict; exactly 100 missed edges or 20 false positives
do not trigger another round.

## Layout

```
evaluation/macro-benchmark/
├── projects.toml                  # The 60 projects: pin, licence, analysed source, tests, batch
├── projects/                      # Empty: a copy of the sources, for reading only, goes here (not in git)
├── test-environments/<name>.txt        # The test environment, pinned by hash (to record the trace again)
├── test-environments/<name>.installed.txt  # What the container of the trace had installed
├── dynamic/<name>.json            # The trace: the calls made while the test suite runs (trace.py)
├── ground-truth/<name>.json       # The call graph: what scoring reads
├── ground-truth/<name>.ledger     # Its source: the call-site ledger
├── ground-truth/<name>.rejected.json  # Trace edges that are not package edges (optional)
├── ground-truth/<name>.added.json # Graph edges that the trace does not have, generated
├── ground-truth/<name>.md         # Judgements (optional)
├── ground-truth/<name>.audit.md   # The blind audit
├── plugins/                       # pytest plugins that five traces need
├── wheels/                        # Wheels built from pinned sdists that PyPI has no wheel of, with their build records
├── selection/                     # How batches 3 to 8 were drawn: list, exclusions, frame, round logs; batch 8's rulings and audit samples
├── projects.py                    # Reads projects.toml; where the sources of the projects are
├── sites.py                       # Finds the call sites and their candidates (ast only)
├── ledger.py                      # Reads and checks a ledger, makes its graph
├── check.py                       # Command line: checks, skeletons, reports
├── trace.py                       # Makes dynamic/<name>.json
└── draw.py                        # Chooses the packages of a new batch
```

To score a tool you need `projects.toml`, `ground-truth/<name>.json`,
`dynamic/<name>.json` (its aliases match names) and the tool's graph. To
run a tool you also need the sources, which the inputs image holds (see
"Getting the sources"). To record a trace again you need
`test-environments/` and the `trace` service (see "Re-recording a trace").

The ledger is the source of truth. `ground-truth/<name>.json` is generated
from it (`check.py --write`) and committed, so that a scorer needs neither
the ledger nor the tools. The checker fails if the two differ. So does
`ground-truth/<name>.added.json`, from the ledger and the trace (see
"Construction"). A ground truth is not regenerated by a command of the
evaluation: it is the trace, minus the edges that a reviewer rejected,
plus the edges that a reviewer added, and then audited blind.

The audit files, the judgement files and the round logs are records of
their time. They name a batch by its former directory:
`macro-benchmark` or "the development set" (batch 1),
`macro-benchmark-heldout` (batch 2), `-heldout-2` (batch 3), `-heldout-3`
(batch 4), `-heldout-4` (batch 5) and `macro-benchmark-2021` (the ICSE
2021 set); "held-out set" N is batch N + 1. See "How the benchmark grew".

### `projects.toml`

`projects.py` reads `projects.toml` for `trace.py`, `check.py` and the
evaluation scripts. It needs nothing but the standard library of Python
3.12, so that the runner of `evaluation/` finds the analysed source
without loading the tracer (Python 3.14). Each table is a project; its
name is one path component of letters, digits, `_`, `-` and `.`, and names
`projects/<name>` and the files of its results.

| Key | Content |
|---|---|
| `batch` | 1 to 8, the batches in the order in which they were built, or `icse-2021`, the projects of PyCG's ICSE 2021 evaluation |
| `repository`, `tag`, `commit` | A git source: the repository's URL, the release tag if the commit is one, and the pinned commit |
| `sdist`, `sdist_url`, `sdist_sha256` | In place of a git source, a source archive from PyPI: its file name, which names the release, an https URL that ends in that name, and its SHA-256 (see "A project held as an sdist") |
| `root` | The directory on `sys.path`; module names are relative to it |
| `packages` | Package directories or module files: the analysed source. A module file is named as its module (`configargparse.py` is `configargparse`) |
| `exclude` | Paths in the packages that are not analysed |
| `dependencies` | Installed top-level modules that are library code |
| `pytest_args`, `test_requirements` | The test paths, and what the test environment has installed (name or name==version). They go together: a project without them has no test run, its ground truth comes from reading only, and `trace.py` refuses it |
| `pytest_config` | The project's own pytest configuration file |
| `deselect` | The deselected tests: `{test = <node id>, reason = <why>}` |
| `plugins` | pytest plugins: `.py` files of the benchmark directory, given relative to it and outside `projects/`, so that the tests of a project cannot change them |
| `also_installed` | Packages of the project that the test environment installs too: a test requirement can need the package itself (pytest needs pluggy). The run checks that the package was imported from the checkout |
| `environment` | Variables of the test run, by name and value; a name that `trace.py` sets or that configures the interpreter, pytest, the dynamic loader or the locale is refused (see "Precautions") |
| `not_importable` | Packages of the project that the test environment cannot import: they need a library that the environment lacks. No test imports them, and the run checks that |

A project's source is `<sources>/<name>`: the files of a git commit, or the
unpacked copy of an sdist. For this directory's `projects.toml`,
`<sources>` is `/inputs/macro-benchmark/projects` in the images of the
evaluation; any other `projects.toml` (a test's, the copy of a trace), and
this one on the host, has its sources in `projects/` beside it. The root,
the packages and the configuration file, resolved, must stay inside the
project's directory, and every reader of a project's files fails if a
link below the directory has a target outside it: the pin fixes the text
of a link, not what it reaches.

## Construction

The ground truth of a project has two parts, and the benchmark keeps both:

```
graph = (trace - rejected) + added
```

- **Trace** (`dynamic/<name>.json`): the calls that the package made while
  its test suite ran (see "Traces"). This part is reproducible: the
  `trace` service records it again in a container, from the pinned source
  and the pinned test environment, and compares the edges: `NAME=<name>
  docker compose -f evaluation/compose.yaml run --rm trace --compare` (see
  "Re-recording a trace").
- **Rejected** (`ground-truth/<name>.rejected.json`): the trace edges that
  are not edges of the package (rule A), each with its reason.
- **Added** (`ground-truth/<name>.added.json`): the edges of the graph that
  the trace does not have. Agents found them by reading the source, with
  the method of "Writing a ground truth" and "Auditing a ground truth". This
  part is not reproducible: each edge is a judgement. The ledger records
  each judgement, and this README states the method.

`check.py --write` writes the added edges beside the graph, from the ledger
and the trace, with sorted keys and the formatting of the graph:

```json
{
  "edges": {
    "h11._connection.Connection.__init__": {
      "h11._util.Sentinel.__repr__": [
        "h11._connection 175:63 format  {our_role!r}"
      ]
    },
    "h11._headers.Headers.__repr__": {
      "<builtin>.repr": ["h11._headers 117:38 call  repr(list(self))"]
    }
  },
  "notes": {
    "h11._connection 175:63 format  {our_role!r}": [
      "reached when the client passes a role other than CLIENT or SERVER"
    ]
  },
  "trace": "dynamic/h11.json"
}
```

`edges` maps each caller to its added callees, and each callee to its
sites: the ledger entries that give the edge, in source order. A site is
written as in the ledger, after its module (`== h11._headers`, then
`117:38 call  repr(list(self))`), so that a reader can go from an edge to
the entry that decided it. `notes` has the notes of these entries; the
other items of an entry (its rejections, exclusions) stay in the ledger
only. Every edge of a graph comes from a ledger entry: a default rejection
only removes candidates, and no convention makes an edge without an entry.
So every added edge has at least one site.

"Traced" is a match of names in the stored trace: a graph edge `f -> g`
is traced if the trace has an edge of the same caller `f` whose callee is
`g`, or has `g` among its other names (`aliases`; the check of the trace
edges matches names in the same way, see "Format of `dynamic/<name>.json`").
So a graph edge `f -> os.path.join` is traced, not added, if the trace has
`f -> posixpath.join` with the alias `os.path.join`. A match of names is
not a proof that each call ran, and the limits of the trace apply (see
"What the tracer does" and "Limits" under "Traces"):

- Two closures of one qualified name share their aliases in the trace, so
  a graph edge can match the trace edge of its sibling.
- The tracer drops calls whose caller it cannot know and the calls of
  client callbacks, by design, and misses the calls of tracer defect T1.
  So a call that ran can be among the added edges.
- One traced pair of caller and callee covers every site of that pair: the
  other sites of the pair are not added edges, whether or not they ran.

A project without a trace (three projects of the ICSE 2021 set) has
`"trace": null`, and all its edges are added; no empty trace file stands
in for the trace. It can have no rejected edges: nothing was traced.

The checker fails if the file is missing, or is not the one that the ledger
and the trace give. It also checks the identity edge by edge: each graph
edge is traced or added, not both; each added edge is in the graph; each
trace edge is in the graph or rejected, not both under any of its names;
and no rejected edge is in the graph. To
count the parts:

```sh
python -I evaluation/macro-benchmark/check.py --origin [--benchmark-dir DIR] [PROJECT ...]
```

It reads only the committed files (the graph, the added edges, the trace
and the rejected edges; no ledger, no source), checks the identity and
prints a Markdown table: per project, the trace edges, the rejected edges,
the traced edges in the graph, the added edges and the graph edges, each
set of graph edges with its edges inside and outside the package. Graph
edges = traced edges in the graph + added edges. The trace edges are not
always the traced edges in the graph plus the rejected ones: one trace edge
can match two names in the graph (bottle, batch 4:
`BaseResponse.copy -> <builtin>.dict.items` and
`http.cookies.SimpleCookie.items` are both the traced `dict.items`).

## Projects

The 60 projects are in one `projects.toml`. Each has a `batch`: 1 to 8, in
the order in which the batches were built, or `icse-2021` for the five
projects of PyCG's ICSE 2021 evaluation. A command takes project names, so
a batch is its names (five; ten in batches 6, 7 and 8).

### How the benchmark grew

The benchmark was built in batches of five projects. Batch 1 is the five
projects that the analysis was first developed on. Each later batch (2 to
5) was measured once, by a frozen engine, before anyone read its false
positives and false negatives. Then they were read and labelled, the
analysis was improved on them, and the next batch was built. So every
batch was used for development in the end. The five projects of the ICSE
2021 set were added between batches 3 and 4. The batches stopped by the
maintainer's rule: when every rule that no decision blocks, measured
together on the newest batch, gains less than one point of precision and
of recall. Batch 5 met it.

Three batches of ten followed, each measured once in the same way. Batch 6
was measured once, on 2026-11-22, by the frozen engine `c5c6a89`, before
its false positives and false negatives were read; then it became a batch
of development, as batches 2 to 5 did: its false positives and false
negatives were read and labelled, and the engine was developed on it.
Batch 7 was measured once, on 2026-11-23, by the next frozen engine
(`2372b60`), and batch 8 once, on 2026-11-24, by the same engine, in the
same way.

Batches 1 and 2 were chosen before `draw.py` existed. Batches 3, 4 and 5
were drawn by `draw.py` in rounds 1, 2 and 3, batch 6 in rounds 4 and 5,
and batch 7 in rounds 6 and 7 (`selection/round-N.json`; see "Choosing a
new batch"). Round 5 skipped the five of round 4, which its log lists under
`used`. Each round ran with one drop (`--drop`, recorded in its log under
`dropped`), and the draw took the next project of the order in the
stratum: round 4 dropped `sh` (the maintainer's veto, 2026-11-22; `tinytag`
instead), round 5 dropped `attrs` (attrs 26.1.0 was analysed before the
draw: the same release and wheel are in the corpus of the scalability runs,
with committed runs of PyCG and of other tools; `prometheus-client`
instead). Round 7 skipped
the five of round 6, which its log lists under `used`, and dropped `dill`,
because a tool run touched it (dill 0.3.9 is installed in the image of the
call-graph tool HeaderGen); the draw took `mss`, the next project of the
order in stratum 5. Batch 8 was drawn in rounds 8 and 9 and the partial
round 10, by the rule fixed before its draw (see "Choosing a new batch").

### Batch 1

| Project | Release | Licence | Analysed source | Modules | Functions (lambdas) | Classes | Calls | Ledger sites | With candidates | Value sites |
|---|---|---|---|---|---|---|---|---|---|---|
| jmespath | 1.1.0 | MIT | `jmespath/` | 8 | 182 (1) | 19 | 461 | 519 | 375 | 22 |
| tenacity | 9.2.1 | Apache-2.0 | `tenacity/` | 12 | 179 (3) | 56 | 415 | 767 | 542 | 46 |
| cachetools | v8.0.0 | MIT | `src/cachetools/` | 7 | 174 (10) | 37 | 359 | 1122 | 962 | 53 |
| pluggy | 1.7.0 | MIT | `src/pluggy/` | 13 | 101 (1) | 18 | 320 | 795 | 600 | 23 |
| h11 | v0.16.0 | MIT | `h11/` without `h11/tests/` | 11 | 89 (0) | 38 | 352 | 759 | 582 | 23 |

The counts are those of the site finder after it learned the accessors of
`property(...)` and stopped counting annotations without a value.

"Ledger sites" are the sites that need an entry without default rejections,
"Value sites" those whose callee is a value (see below).
`python -I evaluation/macro-benchmark/check.py` prints
these numbers, with the sites by kind. `projects.toml` has the commits, the
test commands and the notes on each project.

A security scan of these five sources and of the five of batch 2
was made on 2026-11-14 (read only; Claude Opus 5.5, the
maintainer's choice for this scan). These two batches date from before the
rule that a scan comes before the first run, so this scan came after their
traces. It found nothing malicious: the ten are safe to run in the trace
container as configured. For each, the files rebuild the git tree of the
pinned commit. Its notes: the tests of h11, anytree and sqlparse that open
a socket or start a process are the ones already deselected; pluggy ships
`CLAUDE.md` and `.claude/settings.json` (data, not instructions);
configargparse's suite imports CPython's `test` package where it exists,
which the slim image does not have.

### Getting the sources

**The rule** (the maintainer, 2026-11-14): git and every download run only
inside a container. The threat is a vulnerability of git that a clone could
trigger on the machine that runs it. So the repository holds no copy of a
project and no submodule of one: `projects.toml` pins each project by
its `repository` and full `commit` (or an sdist by its URL and SHA-256),
and that pin is the only lock. The build of the inputs image
(`evaluation/container/Dockerfile.inputs`) fetches each pinned commit
(`evaluation/container/fetch.py`: `git fetch --depth 1`, https only, no
hooks, no submodules) and writes its files as plain files, without
`.git`, into `/inputs/macro-benchmark/projects/<name>`; an sdist is
downloaded, checked against its SHA-256 and unpacked with tarfile's
`data` filter, and the archive is not kept. A project that is not its pin
fails the build. The trace image of a project copies its source from
there when it is built; `projects.py` reads them there in an image
(`projects.sources`), and in `projects/` beside `projects.toml` elsewhere.
`load_projects` refuses a project whose link leaves its directory.

**The scope.** The build of the inputs image is trusted to write what it
fetched. A defence against a compromised build is not a goal.

To read the sources on the host (to write a ledger, say), copy them out of
the inputs image into `projects/`, which git ignores. `make eval` makes the
same copy, and runs PyCG on it in a container. No service reads it:

```sh
C="docker compose -f evaluation/compose.yaml"
P=evaluation/macro-benchmark/projects
$C build inputs
mkdir -p "$P"
$C run --rm -v "$PWD/$P:/repo/$P" inputs cp -RP /inputs/macro-benchmark/projects/. "$P/"
```

**Traces: first recording and container check.** The five traces of
batch 1 were recorded outside a container, on the maintainer's machine
(macOS on Apple silicon), with CPython 3.14.9 (the `python` of each
trace; the traces of batch 2 of the next day name a uv-managed build) and a
virtual environment per project that had exactly the pins of `test_requirements`
(pytest 9.2.0 and its four dependencies; tenacity also tornado 6.6, trio
0.34.0 and trio's five dependencies), before the container runner existed.
The whole evaluation now runs in containers, so each package is traced
again in a container and its trace compared with the
committed one (`trace_helper.py compare`; see "Re-recording a trace"). `test-environments/<name>.txt` pins the versions of the first
traces. The re-trace is a check: it does not replace the committed traces.
Result (2026-11-14, CPython 3.14.10 in the container against 3.14.9 in
the first traces): for each of the five packages the same tests pass and
the two traces have exactly the same edges.

| Project | Tests | Edges, committed | Edges, container | Only in one |
|---|---|---|---|---|
| jmespath | 991 passed, 1 skipped | 428 | 428 | 0 |
| tenacity | 185 passed | 412 | 412 | 0 |
| cachetools | 416 passed | 517 | 517 | 0 |
| pluggy | 219 passed | 272 | 272 | 0 |
| h11 | 76 passed, 2 deselected | 281 | 281 | 0 |

### Batch 2

Five other packages. `trace.py` and `check.py` take `--benchmark-dir DIR`
for another directory with the same layout (default: this directory; the
trace container and the tests use one); the tools assume nothing about the
projects. A project name is one path component of letters, digits, `_`,
`-` and `.` (`projects.py` refuses any other): it names `projects/<name>`
and the files of its results.

The five ground truths were written and audited as those of batch 1
(see "Writing a ground truth" and "Auditing a ground truth"), without any
result of the analysis. The columns are those of the
tables of batch 1 ("Batch 1" above, "Ground truths" below).

| Project | Release | Licence | Analysed source | Modules | Functions (lambdas) | Classes | Calls | Ledger sites | With candidates | Value sites |
|---|---|---|---|---|---|---|---|---|---|---|
| marshmallow | 4.4.0 | MIT | `src/marshmallow/` | 14 | 234 (0) | 65 | 756 | 1337 | 944 | 71 |
| asyncstdlib | v3.14.0 | MIT | `asyncstdlib/` | 11 | 201 (2) | 36 | 399 | 1463 | 1247 | 55 |
| configargparse | v1.9.0 | MIT | `configargparse.py` | 1 | 67 (2) | 12 | 517 | 518 | 78 | 27 |
| sqlparse | 0.6.1 | BSD-3-Clause | `sqlparse/` | 21 | 223 (6) | 44 | 838 | 3508 | 3137 | 62 |
| anytree | 2.13.0 | Apache-2.0 | `src/anytree/` | 33 | 190 (11) | 35 | 385 | 1083 | 871 | 33 |

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|
| marshmallow | 248 | 831 (461 / 370) | 687 (82.7%) | 144 | 15 | 224 of 234 | 830 | 71 | 11 (531) | 4 |
| asyncstdlib | 212 | 659 (475 / 184) | 413 (62.7%) | 246 | 5 | 178 of 201 | 572 | 55 | 17 (947) | 0 |
| configargparse | 68 | 401 (94 / 307) | 331 (82.5%) | 70 | 5 | 58 of 67 | 518 | 27 | 0 (0) | 18 |
| sqlparse | 244 | 696 (439 / 257) | 660 (94.8%) | 36 | 2 | 216 of 223 | 1000 | 62 | 13 (2576) | 3 |
| anytree | 223 | 565 (354 / 211) | 486 (86.0%) | 79 | 0 | 187 of 190 | 572 | 33 | 13 (656) | 2 |
| **All** | **995** | **3152 (1823 / 1329)** | **2577 (81.8%)** | **575** | **27** | **863 of 915** | **3492** | **248** | **54 (4710)** | **27** |

The counts are those of the site finder after it learned the accessors of
`property(...)` and stopped counting annotations without a value.

The audits re-derived a sample of sites blind and changed these edges:

| Project | Sites re-derived blind | Disagreements | Edges changed by the audit |
|---|---|---|---|
| marshmallow | 136 | 1 (auditor error) | -4 (835 to 831) |
| asyncstdlib | 121 | 2 (1 auditor error, 1 writer edge that cannot happen) | -2 (661 to 659: the edge and the same case at a second site) |
| configargparse | 96 | 0 | 0 (401) |
| sqlparse | 132 | 0 | 0 (696) |
| anytree | 103 | 0 | 0 (565) |
| **All** | **588** | **3** | **-6** |

**Traces: first recording and container check.** The five traces of
batch 2 were recorded outside a container, on
the maintainer's machine (macOS on Apple silicon), with a uv-managed
CPython 3.14.9, which has no `test` package (configargparse needs that),
and a virtual environment per project with exactly the pins of
`test_requirements`, before the container runner existed. Each package is
traced again in a container and its trace compared with the committed one,
as for batch 1; `test-environments/<name>.txt` pins the versions of
the first traces. The re-trace is a check: it does not replace the
committed traces, and it shows trace edges, not results of the analysis.
Result (2026-11-14, CPython 3.14.10 in the container): for each of the
five packages the same tests pass and the two traces have exactly the
same edges.

| Project | Tests | Edges, committed | Edges, container | Only in one |
|---|---|---|---|---|
| marshmallow | 1192 passed | 702 | 702 | 0 |
| asyncstdlib | 398 passed, 4 skipped | 418 | 418 | 0 |
| configargparse | 182 passed, 5 xfailed | 336 | 336 | 0 |
| sqlparse | 535 passed, 2 xfailed, 1 xpassed, 2 deselected | 662 | 662 | 0 |
| anytree | 162 passed, 1 deselected | 486 | 486 | 0 |

### Batch 3

Five packages that `draw.py` drew in round 1
(`selection/round-1.json`, one per size stratum; see "Choosing a new batch").
`plugins/testlib_cases.py` is a pytest plugin of markdown2.

| Project | Release | Licence | Analysed source | Code lines (draw) |
|---|---|---|---|---|
| aiocache | v0.12.3 | BSD-3-Clause | `aiocache/` | 1236 |
| argcomplete | v3.7.2 | Apache-2.0 | `argcomplete/` | 1506 |
| pypinyin | v0.55.0 | MIT | `pypinyin/` without `pypinyin/__pyinstaller/` | 2256 |
| markdown2 | 2.5.5 | MIT | `lib/markdown2.py` | 3018 |
| netaddr | 1.3.0 | BSD-3-Clause | `netaddr/` without `netaddr/tests/` | 3486 |

A security scan of the five checkouts came before any run. The tests run
only as the scan recommends, in a container (see "Recording traces in a
container"); `projects.toml` holds each restriction with its reason:

| Project | Tests run | Left out, and why |
|---|---|---|
| aiocache | `tests/ut`, `tests/acceptance` with `-m "not redis and not memcached"`; plugins pytest-asyncio and pytest-mock by `-p`, `-o asyncio_mode=auto` | `tests/performance` (an HTTP server, Apache Bench, live Redis and memcached); the tests marked `redis` or `memcached` (they connect to local services); `setup.cfg` as configuration (pytest-cov writes into the checkout, warnings are errors); two `test_cache_write_doesnt_wait_for_future` tests, which fail on Python 3.13 and later with or without the tracer (an autospecced async method records its call only when it runs) |
| argcomplete | the five in-process classes of `test/test.py`, by node id, with `--capture=sys -p no:faulthandler` (the package opens and closes file descriptor 9, which pytest's fd capture holds) | the real-shell classes (interactive bash and zsh under a pty, `pip install` from PyPI; their completions run in child processes, which the tracer does not see) |
| pypinyin | `tests`, `pypinyin` with `--doctest-modules -s`, as its `pytest.ini` (a command reads stdin, which pytest's capture refuses) | `pypinyin/__pyinstaller` (a PyInstaller hook); `pytest.ini` as configuration (its addopts need pytest-cov) |
| markdown2 | `test/test_markdown2.py` with the plugin `plugins/testlib_cases.py`, which calls the project's own case generator `test_cases()` | the 17 `knownfailure` cases, the 2 `wavedrom` cases (wavedrom has no wheel), the 2 `pygments<2.14` cases (the harness's own filters), and the timing test `test_slow_hr` |
| netaddr | `netaddr` and the three tutorials, with the project's `pytest.ini` | nothing |

**Provenance.** Each project's test dependencies are installed from
`test-environments/<name>.txt`, which lists the full closure by version and
SHA-256, with pip's `--require-hashes --only-binary :all: --no-deps`; the
hash of each dependency that the security scan read is that of the file it
read, and the others come from PyPI's JSON for that version. Before each
run, `trace.sh` checks that the commit of `projects.toml` is that of the
round log (the build of the inputs image checked the source against that
commit), and the container checks, without importing it, that the package
is found in the copy of that source and nowhere in the environment. After each run, `trace.sh` checks that the
distributions of the container are exactly those of the requirements file
and writes them to `test-environments/<name>.installed.txt`.

The traces were recorded in containers from
`python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f`
(CPython 3.14.10, linux/aarch64). Each package was traced twice, and both
runs gave the same bytes for `dynamic/<name>.json` and
`test-environments/<name>.installed.txt`.

| Project | Passed | Skipped | Expected failures | Deselected | Failed | Trace edges | Functions run |
|---|---|---|---|---|---|---|---|
| aiocache | 540 | 0 | 0 | 264 | 0 | 469 | 173 |
| argcomplete | 52 | 0 | 1 | 0 | 0 | 211 | 49 |
| pypinyin | 985 | 2 | 0 | 0 | 0 | 435 | 132 |
| markdown2 | 244 | 0 | 0 | 22 | 0 | 753 | 180 |
| netaddr | 351 | 1 | 0 | 0 | 0 | 960 | 312 |

aiocache's deselected tests are the 262 that `-m` leaves out (Redis and
memcached) and the 2 of `deselect`.

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|
| aiocache | 190 | 563 (254 / 309) | 415 (73.7%) | 148 | 54 | 173 of 177 | 576 | 68 | 1 (627) | 5 |
| argcomplete | 89 | 334 (91 / 243) | 206 (61.7%) | 128 | 5 | 49 of 74 | 516 | 18 | 1 (131) | 3 |
| pypinyin | 181 | 452 (207 / 245) | 430 (95.1%) | 22 | 5 | 132 of 138 | 670 | 10 | 1 (33) | 1 |
| markdown2 | 197 | 872 (281 / 591) | 752 (86.2%) | 120 | 1 | 180 of 196 | 1316 | 13 | 2 (241) | 1 |
| netaddr | 382 | 1219 (629 / 590) | 960 (78.8%) | 259 | 0 | 312 of 362 | 1708 | 43 | 25 (1820) | 0 |
| **All** | **1039** | **3440 (1462 / 1978)** | **2763 (80.3%)** | **677** | **65** | **846 of 947** | **4786** | **152** | **30 (2852)** | **10** |

The counts are those of the site finder after it learned the accessors of
`property(...)` and stopped counting annotations without a value.

Of aiocache's 54 rejected trace edges, 50 are calls of the mocks that its
tests put in place of clients, serializers and plugins; 54 of its edges
from reading are in the Redis and memcached backends, which the tests
mock. argcomplete's tests run only its in-process part.

The audits re-derived a sample of sites blind and changed these edges:

| Project | Sites re-derived blind | Disagreements | Edges changed by the audit |
|---|---|---|---|
| aiocache | 131 | 5 (3 auditor errors, 1 naming, 1 writer callees that the rules do not support) | -5 (568 to 563, with a ruling on B2) |
| argcomplete | 88 | 6 (3 auditor errors, 2 naming, 1 writer edge that cannot happen) | -6 (340 to 334: -8 with a ruling on B1, +2 by the naming rule) |
| pypinyin | 79 | 0 | -1 (453 to 452, with a ruling on version branches) |
| markdown2 | 124 | 2 (1 auditor error, 1 site where the writer missed callees that the graph already had) | 0 (872) |
| netaddr | 112 | 0 | 0 (1219) |
| **All** | **534** | **13** | **-12** |

markdown2's writer drafted the plain ledger entries with a script of its
own that applies the naming rules to receiver names, and reviewed each
entry; its auditor therefore re-derived 40 more plain sites, and all agree.
netaddr binds five attributes with `property(...)` and not with a
decorator; the site finder of that time proposed no candidate for their
loads and stores, so writer and auditor each listed these 37 sites with a
scan of their own, and all are in the ledger.

### The ICSE 2021 set

The five projects of the
macro-benchmark of PyCG's ICSE 2021 evaluation (Salis et al., ICSE 2021),
at the commits of its artifact (`vitsalis/pycg-evaluation` at `ce37eb5`,
its tag `evaluation-2021`). Their batch is `icse-2021`. The
analysis was developed on them, as on batch 1. Their ground truths are
new: they follow the conventions of this README and do not use the 2021
ground truths, which miss real calls, hold names that name no function,
were completed from the output of tools, and count vendored code and
tests. Three of the projects
are GPL: the repository holds none of their code, and the build of the
inputs image fetches them as every other project. Only autojump's
commit is a release tag; the other entries have no `tag`.
`test-environments/` holds the test environments of autojump and asciinema, and
`plugins/nose_tools.py` is a pytest plugin of asciinema.

| Project | Commit | Licence | Analysed source | Modules | Code lines | Functions (lambdas) | Classes | Python (declared) |
|---|---|---|---|---|---|---|---|---|
| autojump | `06e082c` (release-v22.5.3) | GPL-3.0-or-later | `bin/autojump_data.py`, `bin/autojump_match.py`, `bin/autojump_utils.py` (root `bin`) | 3 | 270 | 43 (11) | 0 | 2.6+, 3.3+ |
| fabric | `34edfe4` (2.0.5 and 11 commits) | BSD-2-Clause | `fabric/` | 12 | 865 | 81 (0) | 17 | 2.7, 3.4+ |
| asciinema | `350d5e9` (after v2.0.0) | GPL-3.0-or-later | `asciinema/` | 24 | 1150 | 137 (3) | 35 | 3.4+ |
| face_classification | `2f152a2` | MIT | `src/` without `src/__init__.py` (root `src`) | 19 | 1455 | 65 (1) | 2 | 3 |
| Sublist3r | `3f5fc6d` | GPL-2.0-only | `sublist3r.py`, `subbrute/` | 3 | 1249 | 99 (1) | 16 | 2.7, 3 |

Code lines are counted as `draw.py` counts them. Four projects are
applications, not packages: the analysed source is the program's own
modules, under the root from which they import each other. Tests,
documentation, site configuration, setup and install scripts, maintainer
tasks and vendored copies are not analysed, as in the other batches. The 2021
selections were wider: autojump's had `bin/autojump_argparse.py`, a
vendored argparse 1.2.1 (425 of its 537 edges); fabric's had
`integration/` (tests), `sites/` (Sphinx configuration) and `tasks.py`
(123 of its 381 edges have a caller in the first two); Sublist3r's had
`setup.py`. The notes of `projects.toml` give each choice.

A security scan of the five checkouts came first. Two projects have a test
run; the other three get a ground truth from reading only. An entry without
`pytest_args` and `test_requirements` has no test run: `trace.py` refuses
it, and `projects.py` refuses an entry that has only one of the two.

| Project | Tests run | Left out, and why |
|---|---|---|
| autojump | `tests/unit` (32 tests by reading), with mock 5.2.0 | nothing (`tests/integration/` is empty); no test calls a function of `autojump_data` |
| asciinema | `tests` (26 tests by reading), with the plugin `plugins/nose_tools.py`: nose 1.3.7 does not import on Python 3.12 and later | `tests/integration.sh` and `tests/distros.sh` (the command line in subprocesses, Docker builds) |
| fabric | none | fabric requires invoke<2.0, and invoke 1.x imports `imp`, which Python 3.12 removed |
| face_classification | none | no tests; dependencies of 2017 (keras 2.0.5, tensorflow 1.1.0) without wheels for Python 3.14 |
| Sublist3r | none | no tests; it queries search engines, DNS resolvers and the ports of other hosts |

The maintainer approved the projects and the two test runs
(2026-11-14). The
traces were recorded in the container of batch 3 (same
image), each twice with the same bytes.

| Project | Passed | Skipped | Expected failures | Failed | Trace edges | Functions run |
|---|---|---|---|---|---|---|
| autojump | 23 | 5 | 4 | 0 | 37 | 17 of 43 |
| asciinema | 26 | 0 | 0 | 0 | 84 | 37 of 137 |

The lead's rulings on the scope:

1. autojump's main script, `bin/autojump` (248 code lines, 17 functions
   with 6 lambdas), has no `.py` suffix. The tools read `.py` files only,
   so the entry leaves it out, as the 2021 selection did: a stated limit
   of the set. For the scope rules the script is a client: what it passes
   does not fix the type of an undocumented parameter.
2. Sublist3r's `subbrute/` is a modified copy of TheRook's subbrute that
   `setup.py` installs as a package of Sublist3r. The entry analyses it,
   as argcomplete's `packages/_shlex.py`.
3. face_classification: the entry analyses the seven scripts (module code
   only). `web/faces.py` imports `emotion_gender_processor` as a top-level
   module; it is named `web.emotion_gender_processor`.
4. Callees outside the package in code that cannot run now are named by
   the versions that the project admits at its commit. fabric's were
   checked against the sources of invoke 1.4.1 and paramiko 2.7.1 (PyPI
   archives, read only). face_classification's (keras 2.0.5, tensorflow
   1.1.0) could not be read: 11 names, 21 edges, have a receiver class
   that is a guess (`ground-truth/face_classification.md`), and the edges
   after each script's first `load_model` assume that this keras accepts
   `compile=False`.

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions | Edges of the 2021 ground truth |
|---|---|---|---|---|---|---|---|---|---|---|---|
| autojump | 46 | 131 (35 / 96) | 33 (25.2%) | 98 | 4 | 17 of 43 | 139 | 12 | 0 (0) | 0 | 537 |
| asciinema | 161 | 428 (174 / 254) | 81 (18.9%) | 347 | 3 | 37 of 137 | 518 | 20 | 0 (0) | 2 | 341 |
| fabric | 93 | 341 (100 / 241) | no trace | 341 | - | - | 375 | 4 | 2 (106) | 0 | 381 |
| face_classification | 84 | 485 (103 / 382) | no trace | 485 | - | - | 912 | 117 | 0 (0) | 1 | 435 |
| Sublist3r | 102 | 447 (143 / 304) | no trace | 447 | - | - | 513 | 2 | 0 (0) | 2 | 406 |
| **All** | **486** | **1832 (555 / 1277)** | **114** | **1718** | **7** | **54 of 180** | **2457** | **155** | **2 (106)** | **5** | **2100** |

The numbers of the last column are sizes only: the new ground truths were
written without the 2021 files, and the scopes differ (see above), so the
two columns do not count the same thing. Most of this set comes from
reading: three projects have no trace and the two traces cover a quarter
and a fifth of their graphs. The audits therefore re-derived more sites:

| Project | Sites re-derived blind | Disagreements | Edges changed by the audit |
|---|---|---|---|
| autojump | 139 (all) | 5 (1 auditor error, 2 naming, 2 sites of one ruling) | -2 (133 to 131: the main script is a client) |
| asciinema | 120 | 2 (auditor naming errors) | +3 (425 to 428: a redirect from http to ftp) |
| fabric | 103 | 2 (1 missed edge, 1 naming) | +1 (340 to 341: +1 called back by invoke, -1 one class under two names, +1 a name by library version) |
| face_classification | 138 | 0 | -1 (486 to 485) |
| Sublist3r | 102 | 0 | 0 (447) |
| **All** | **602** | **9** | **+1** |

face_classification's writer drafted the ledger with a script of its own
from the resolved imports; its auditor read every plain entry outside
`models/cnn.py` against the source. Two iteration sites of asciinema go
over a lazy `map` of a package lambda, for which the site finder proposes
no candidate (see "Limits of the site finder").

### Batch 4

The five packages that `draw.py` drew in round 2
(`selection/round-2.json`, one per size stratum). The maintainer approved the projects
and their test runs as the security scan recommends (2026-11-14).

| Project | Release | Licence | Source | Analysed source | Code lines (draw) |
|---|---|---|---|---|---|
| dagster-pipes | 1.13.28 | Apache-2.0 | sdist from PyPI | `dagster_pipes/` | 1180 |
| fastjsonschema | v2.22.3 | BSD-3-Clause | git | `fastjsonschema/` | 1277 |
| pyflakes | 4.1.0 | MIT | git | `pyflakes/` without `pyflakes/test/` | 1889 |
| bottle | 0.13.4 | MIT | git | `bottle.py` | 3052 |
| itables | v2.9.1 | MIT | git | `itables/`, `itables_for_dash/` (root `src`) | 3117 |

dagster-pipes is the directory `python_modules/dagster-pipes` of the dagster
monorepo, whose release tag the draw pinned (1.13.28 at commit `273178a5`).
A checkout of the monorepo would fetch 1.46 GiB; by the maintainer's
ruling the benchmark holds the package as its sdist instead (see "A project held
as an sdist" under "Recording traces in a container"):
`dagster_pipes-1.13.28.tar.gz`, SHA-256 `f785c2ee…`. Unpacked, its files
other than `PKG-INFO` and `.gitignore` (the monorepo's root file, which the
build adds) are the 14 files of the directory at the tag, byte for byte:
their git tree is `a27c35a0…`, the tree of `python_modules/dagster-pipes`
at commit `273178a5` (security scan). The build of the inputs image checks
the file's SHA-256 and unpacks it into
`/inputs/macro-benchmark/projects/dagster-pipes/` (the archive is not
kept), and `trace_helper.py` checks that its name names the release of the
round log.

A security scan of the five sources came first; it read them and ran
nothing. A second, independent scan (Claude Fable 5.2) read them again and
agreed with every verdict. The tests run only as the scans recommend, in
the container of batch 3; `projects.toml` holds each
restriction with its reason:

| Project | Tests run | Left out, and why |
|---|---|---|
| dagster-pipes | `dagster_pipes_tests` (20 tests by reading) | the pipes tests of dagster core and of the integration libraries (not in the sdist; they need the dagster framework, and many start subprocesses, cloud clients or clusters) |
| fastjsonschema | `tests` with `-m "not benchmark"`, as its `tox.ini` (137 test functions by reading, many parametrized) | the 2 benchmarks (pytest-benchmark); the 4 tests that the JSON-Schema-Test-Suite submodule parametrizes collect nothing, as in the project's CI, which does not check out submodules (the maintainer's ruling: the suite is not added) |
| pyflakes | `pyflakes/test` (791 tests by reading, with the classes that rerun others in doctest mode) | the 5 `IntegrationTests`: they run `python -m pyflakes` in a subprocess, which writes bytecode into the checkout and which the tracer does not see (`TestMain` runs the same cases in the test process) |
| bottle | `test` (377 tests), with Mako and Jinja2 for the template adapters | nothing |
| itables | 16 test files (143 test functions by reading, many parametrized), with pandas, polars, narwhals, pyarrow, tzdata, IPython, typeguard, platformdirs and Jinja2 | `tests/playwright` (a browser); the notebook tests (Jupyter kernels, subprocesses); the shiny, marimo, streamlit, widget and dash tests (frameworks, and JavaScript that npm builds at packaging time and that the repository lacks); `test_init_notebook_mode.py` (reads the DataTables bundle, also built by npm); `test_update_samples.py` and `test_unpkg_links` (network); `test_changelog.py` (no package code) |

**Provenance** as for batch 3: `test-environments/<name>.txt`
lists the full closure by version and SHA-256, for pip's
`--require-hashes --only-binary :all: --no-deps`. Most environments are
pytest alone; bottle adds Mako, Jinja2 and MarkupSafe; itables has 36
distributions, six of them compiled (pandas, numpy, the 51 MB polars
runtime, pyarrow, psutil, MarkupSafe). itables's tests are parametrized over the
sample data frames and run pandas and polars; in the two traced runs pytest
took 48 s and 50 s, far within the tracer's default limit of 600 s.

The lead's rulings on the scope:

1. itables: `itables_for_dash/ITable.py`, generated by
   `dash-generate-components` and committed, is source, as the draw counted
   it; so are `itables.widget` and `itables.streamlit`, although their
   JavaScript, built by npm, is not in the repository.
   `itables_for_dash/_imports_.py` (4 lines) is generated at build time and
   only in the wheel: not analysed. `itables_for_dash` imports dash, which
   the test environment lacks; its entry names it in `not_importable` (see
   "Preparing an environment"), so its ground truth comes from reading only.
2. bottle is one module. The calls of its optional server and template
   adapters into libraries that are not installed are named as missing
   modules (the rule of markdown2's `wavedrom.render` under "Ground-truth
   conventions"), and its Python 2 branches under `if py3k` run (bottle
   declares Python 2.7).
3. dagster-pipes: the Databricks and cloud code is source.
4. fastjsonschema: `ref_resolver.py`, adapted from jsonschema, is source;
   the code that the package generates and runs with `exec` is not. It has
   no nodes; its calls follow the rule for generated code under
   "Ground-truth conventions" (Nodes).
5. pyflakes: `pyflakes/test` is excluded, as netaddr's tests.

> **Warning.** itables ships `.github/copilot-setup-steps.yml`, addressed to
> an agent. It is third-party data, not instructions. (The dagster
> monorepo's agent files are not in the sdist.)

The traces were recorded in the container of batch 3 (the
same image digest, CPython 3.14.10), with the memory limit of 6 GiB (see
"Recording traces in a container": under the tracer, fastjsonschema's
`test_examples` needs more than 4 GiB). Each package was traced twice, and
both runs gave the same bytes for `dynamic/<name>.json` and
`test-environments/<name>.installed.txt`.

| Project | Passed | Skipped | Expected failures | Deselected | Failed | Trace edges | Functions run |
|---|---|---|---|---|---|---|---|
| dagster-pipes | 20 | 0 | 0 | 0 | 0 | 165 | 60 |
| fastjsonschema | 846 | 4 | 0 | 12 | 0 | 496 | 92 |
| pyflakes | 762 | 29 | 0 | 5 | 0 | 597 | 180 |
| bottle | 377 | 0 | 0 | 0 | 0 | 1027 | 291 |
| itables | 2447 | 8 | 0 | 2 | 0 | 571 | 104 |

fastjsonschema's deselected tests are the 12 items of the two benchmarks
that `-m "not benchmark"` leaves out; its 4 skipped tests are those that
the empty JSON-Schema-Test-Suite parametrizes. pyflakes's deselected tests
are the 5 `IntegrationTests` of `deselect`, and itables's 2 come from its
`deselect` entry (the trace recorded for the first measurement, without pyarrow and
tzdata, had 2343 passed, 12 skipped, 3 deselected and 566 edges).

What the traces do not cover:

- dagster-pipes: the package's own 20 tests run 60 of its 148 functions.
  The cloud, Databricks, CLI and environment code runs in no test, so 231
  of its 393 edges come from reading only.
- itables: the run has the 16 test files of the table above. The first
  traces had neither pyarrow nor tzdata, so `tests/test_downsample.py` and
  the time-zone case did not run. After the first measurement, the trace of itables was
  recorded again with the two libraries, on the maintainer's decision of
  2026-11-14. With pyarrow, pandas stores its text columns in Arrow, as in
  the project's CI. `itables_for_dash` is in `not_importable`: no test runs
  it, and all its edges come from reading only.
- Every trace misses the calls of the tracer defect T1 (see "Limits" under
  "Traces"). The ground truths add these edges from reading: 12 of
  fastjsonschema's 53 edges from reading only, and 15 of pyflakes's 49.

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|
| dagster-pipes | 150 | 393 (164 / 229) | 162 (41.2%) | 231 | 3 | 60 of 148 | 454 | 0 | 5 (60) | 1 |
| fastjsonschema | 106 | 548 (314 / 234) | 495 (90.3%) | 53 | 1 | 92 of 95 | 771 | 6 | 1 (159) | 0 |
| pyflakes | 197 | 642 (376 / 266) | 593 (92.4%) | 49 | 4 | 180 of 189 | 837 | 14 | 6 (423) | 3 |
| bottle | 386 | 1461 (608 / 853) | 1013 (69.3%) | 448 | 15 | 291 of 385 | 1836 | 181 | 46 (12946) | 0 |
| itables | 150 | 776 (188 / 588) | 570 (73.5%) | 206 | 2 | 104 of 129 | 1361 | 6 | 1 (706) | 0 |
| **All** | **989** | **3820 (1650 / 2170)** | **2833 (74.2%)** | **987** | **25** | **727 of 946** | **5259** | **207** | **59 (14294)** | **4** |

The rejected trace edges are calls of the tests' own objects: `MagicMock`
objects (dagster-pipes), a dict's `__getitem__` passed as a handler
(fastjsonschema), `StringIO` streams (pyflakes), the tests' streams, files
and callbacks (bottle). itables's 2 are naming artefacts: the tracer names
the `numpy.random` functions `_cython_3_2_8.cython_function_or_method.__call__`.
bottle's writer filled some entries with scratch rules (the calls of
builtins and of a fixed list of standard-library functions, four
decorators, and some attribute loads and stores, among them those of the
thread-local attributes) and reviewed each generated entry against the
source; all other entries were written by hand.

The audits re-derived a sample of sites blind. In itables one candidate,
`_SubscriptableFallback.__getitem__`, sits at 793 of the 1989 sites, and in
bottle 1601 of the 4413 sites are attribute loads, so both auditors drew
the sample by kind. The audits and the lead's rulings changed these edges:

| Project | Sites re-derived blind | Agreements | Findings (ids of the audit file) | Edges changed by the audit | Edges changed by the rulings |
|---|---|---|---|---|---|
| dagster-pipes | 70 (no value site) | 70 | L1, L2 (rulings), W1 (wording), R1, R2 (README) | 0 (385) | +8 (385 to 393: ruling 1) |
| fastjsonschema | 76 | 76 | R1, R2 (README), V1 (a fact the auditor could not check), T1 (tool) | 0 (548) | 0 |
| pyflakes | 84 | 84 | J1 (ruling), A1 (wording), R1 (remark) | 0 (642) | 0 |
| bottle | 251 | 246 (4 auditor errors, 1 placement only) | F1, F2 (missed edges), R1 (placement), N1 to N3 (rulings) | +8 (1454 to 1462: F1 +6, F2 +2) | 0 |
| itables | 76 | 74 (2 auditor errors) | F1, F2, R1 (rulings) | 0 (776) | 0 |
| **All** | **557** | **550** | | **+8** | **+8** |

No audit found an edge of a writer that cannot happen.

The lead's rulings on the ground truths of this set (each general rule is
also stated at its place in the conventions below):

1. `Any` (dagster-pipes judgement 3, audit L1; itables J2 and J3, audit
   R1): an annotation of `Any` states no type, so the documentation can fix
   a concrete outside type (B4). The lead's first ruling on L1 (`Any`
   decides as `object`: the client objects are opaque) was reversed, so
   that one rule holds for the set. dagster-pipes: +8 outside edges, 385 to
   393: +6 at the Azure sites (`__init__.py:1351` to `1353`, `1402`,
   `1403`), named as a missing module, and +2 at the S3 sites
   (`boto3.client.get_object`, `1199:38`; `boto3.client.put_object`,
   `1251:32`). The three `widgets.get` sites keep no callee (the docstring
   names no class), and so do `obj["Body"].read()` and its `.decode`
   (`1200:42`, `1200:51`: the subscript of a missing-module value). itables:
   no change.
2. Missing modules (dagster-pipes judgements 4 and 5, audit L2): the rule
   fixes names only; a branch that the library's answer decides still runs
   (`spark is None`, `1457:36`; `except Py4JJavaError`, `1470:26`). The 7
   GCS edges and the pyspark edge keep their missing-module names: no
   change.
3. Generated code (fastjsonschema, "The generated code"; audit R1): a
   function that `exec` defines has no node; a call in the exec'd module
   code belongs to the function that calls `exec` (`compile ->
   <builtin>.type`, `__init__.py:294:9`); a package function that a
   generated validator calls belongs to the site that calls the validator
   (`validate -> JsonSchemaValueException.__init__` and
   `JsonSchemaValuesException.__init__`, `__init__.py:172:108`). No change.
4. Two kinds of callee by version (fastjsonschema judgement 2, audits R2
   and V1): `urlsplit` is a plain function on Python 3.10 and an
   `lru_cache` wrapper from 3.11, so `ref_resolver.py:52:29` and `64:31`
   name `urllib.parse.urlsplit` and `functools._lru_cache_wrapper.__call__`.
   The writer's reading of the CPython 3.10 to 3.12 sources is kept. No
   change.
5. fastjsonschema: no default rejection for `Indent.__enter__` and
   `__exit__`, which are callees at 103 of their 115 `with` sites. No
   change.
6. Parser options (pyflakes judgement 1, audit J1): a client tree from
   `ast.parse(..., type_comments=True)` holds `TypeIgnore` nodes, which have
   no handler, so `handler(node)` at `checker.py:1252:20` keeps
   `Checker._unknown_handler` (B3). 1 edge stays.
7. Declared requirements (itables J1, audit F1): the versions of a
   dependency that a package admits are decided by its own declared
   requirements, so the `NotRequired`/`Unpack` fallback of `typing.py:26-40`
   runs in all seven modules that use it. 4 edges stay (the modules
   `itables.streamlit`, `itables.widget`, `itables_for_dash` and
   `itables_for_dash.properties` -> `_SubscriptableFallback.__getitem__`).
8. A definition made through a missing library (itables J4, audit F2):
   dash's `_explicitize_args` on the generated `ITable.__init__` was read
   from the dash 4.4.1 wheel (SHA-256 in `itables.md`), never run, and
   confirmed J4: `super().__init__(...)` at `itables_for_dash/__init__.py:56:32`
   has `dash.development.base_component._explicitize_args.wrapper` and
   `itables_for_dash.ITable.ITable.__init__`. No change.
9. bottle, N1 (`_raise`, `bottle.py:119:19`): an exception that escapes a
   client callback is a client value. No change.
10. bottle, N2 (the view wrapper, `bottle.py:4524:31`): the result of a
    client callback is a client object (B5); an `isinstance` against an
    outside abstract type (`DictMixin`) names no package class for it. No
    change.
11. bottle, N3 (judgement J2): library behaviour that differs between
    Python 2 and 3 without a branch in the package is named for Python 3.
    No change.
12. bottle, R1 (`bottle.py:584:40`, `1093:28`, `1226:31`) and F1: where a
    lazy `map` or `filter` is built and iterated in one function, the place
    of its callback in that function does not matter; where library code
    iterates it, or an application's output, the package site that hands
    it to the library is the caller. F1 (+6 inside edges: wsgiref under
    `WSGIRefServer.run` and `CGIServer.run`) and F2 (+2 inside edges: the
    Python 2 `tzinfo.fromutc` calls back `_UTC.utcoffset` and `_UTC.dst`,
    `bottle.py:1806:48`) were accepted.

**Corrections to bottle after the first measurement (2026-11-14).** The analysis
of the false positives and false negatives of round 3 named three doubts about bottle's ground truth and did not
edit it. A second auditor, who had not seen the first audit, derived four
sites blind; the writer checked each and applied three rulings. The bottle
row of the table of ground truths above is the committed graph, as
corrected on 2026-11-14: **1461 edges (608 inside, 853 outside)**, 1013
(69.3%) confirmed by the trace, 448 from reading only. At the first measurement it had
1462 edges (611 / 851), 449 from reading only, and the batch 3821 edges
(1653 / 2168), 988 from reading only. The other columns of the row did not
change: the corrections changed callees and rejections only, at sites that
had entries.

13. bottle, a call that cannot bind (`bottle.py:3613:13`, `3682:13`):
    `depr(0, 13, msg)` passes three arguments and `depr` needs four, so
    Python raises `TypeError` on every version and path. The convention
    already says so ("Edges", "Judgements"): the call has no edge and the
    code after it has no edges. A `def` after such a call never runs and
    makes no function, so `FapwsServer.run.app` has no edges. The first
    audit missed it: neither site was in its sample, and no exhaustive
    check looks at argument counts. -12 edges (4 inside, 8 outside).
14. bottle, `BaseResponse.__iter__` (`bottle.py:1696:20`): the package
    itself stores a `WSGIFileWrapper` as a body (`_mount_wsgi`, line 737,
    for a mounted Bottle whose route returns a file, when the environ has
    no `wsgi.file_wrapper`), so B2 gives `WSGIFileWrapper.__iter__` at
    this site. The default rejection ("the package never iterates one")
    stays for the other sites. +1 inside edge.
15. bottle, Python 2 values (ruling 2 against ruling 11): **a value that
    a Python-2-only branch of the package makes keeps its Python 2 type
    where it flows**, and its builtin callees take the Python 3 name of
    that type. `tonat = tob` (line 160) makes header values, the
    Content-Disposition value and the POST body Python 2 `str`, which is
    `bytes` by its Python 3 name. Ruling 11 covers library behaviour that
    differs without a branch in the package; here a branch of the package
    makes the difference. The ledger already took this view at
    `bottle.py:2770` (`fname.decode`, `<builtin>.bytes.decode`). +10
    outside edges (`bytes.strip`, `split`, `lower`, `replace` in
    `BaseResponse.__repr__`, `.charset`, `_MultipartPart.finish_header`,
    `_parse_http_header`, `_parse_qsl`), next to the `str` callees.
    Values from the environ and the cookies stay `str`.

### Batch 5

The five packages that `draw.py` drew in round 3
(`selection/round-3.json`, one per size stratum): the last batch (see "How
the benchmark grew"). `plugins/outputs_cleanup.py` is a pytest plugin of
python-barcode.

| Project | Release | Licence | Source | Analysed source | Code lines (draw) |
|---|---|---|---|---|---|
| whitenoise | 6.12.0 | MIT | git | `whitenoise/` (root `src`) | 1056 |
| funcy | 2.1 | BSD-3-Clause | git | `funcy/` | 1559 |
| python-barcode | v0.16.1 | MIT | sdist from PyPI | `barcode/` | 1596 |
| pyrate-limiter | v4.5.1 | MIT | git | `pyrate_limiter/` | 2296 |
| structlog | 26.1.0 | MIT OR Apache-2.0 | git | `structlog/` (root `src`) | 3223 |

The draw pinned python-barcode's tag v0.16.1 at commit `cf58852b`. The
checkout at the tag cannot be imported: three modules import
`barcode/version.py`, which setuptools-scm writes at build time. By the
lead's decision the benchmark holds the package as its sdist, as dagster-pipes
(see "A project held as an sdist" under "Recording
traces in a container"): `python_barcode-0.16.1.tar.gz`, SHA-256
`665ed095…`, 59 files, regular files and directories only. It holds every
file of the tag, equal by git blob hash (`setup.cfg` apart: whitespace and
an `[egg_info]` section), and adds `barcode/version.py` (assignments
only), `PKG-INFO` and the `egg-info` directory (security scan).
The build of the inputs image checks the file's SHA-256 and unpacks it into
`/inputs/macro-benchmark/projects/python-barcode/` (the archive is not
kept), and `trace_helper.py` checks that its name names the release of the
round log.

A security scan of the five sources came first (Claude Fable 5.2); it read
them and ran nothing, and found nothing malicious. The tests run only as it
recommends and as the lead decided (below), in the container of batch 3; `projects.toml` holds each restriction with its reason:

| Project | Tests run | Left out, and why |
|---|---|---|
| whitenoise | `tests` (89 test functions by reading), with Django, requests, brotli and tzdata; a WSGI test server on 127.0.0.1 | nothing (`scripts/`, which can fetch a file and rewrite a module, is not collected) |
| funcy | `tests` (209 test functions by reading), with whatever | nothing |
| python-barcode | `tests` (29 test functions by reading, one with 14 parameters), with Pillow and the plugin `plugins/outputs_cleanup.py`: 19 items (21 with Pillow) write into `tests/test_outputs/`, and the plugin removes exactly what is new there at the end of the session | nothing; `setup.cfg` is not the configuration (its addopts need pytest-cov) |
| pyrate-limiter | `tests` with pytest-asyncio by `-p` and its two keys by `-o`, and filelock | `tests/test_multiprocessing.py` (worker processes, which the tracer does not see); `tests/test_aiohttp_limiter.py` (aiohttp is not installed); `test_advisory_lock_id_is_the_same_in_every_process` (two child interpreters, which write bytecode into the checkout copy); `examples/` and `benchmarks/` (HTTPS to httpbin.org, Redis, PostgreSQL). Without redis and psycopg the Redis and PostgreSQL tests skip; `pyproject.toml` is not the configuration (keys of pytest-retry) |
| structlog | `tests` with pytest-asyncio by `-p` and its two keys by `-o`, time-machine, simplejson, and Twisted with its closure | the 4 tests of `tests/test_packaging.py` that ask `importlib.metadata` for the installed distribution (the trace uses the checkout); the tests that need Rich, greenlet or better-exceptions skip (not installed) |

**Provenance** as for batch 3: `test-environments/<name>.txt`
lists the full closure for CPython 3.14 on Linux aarch64 by version and
SHA-256, for pip's `--require-hashes --only-binary :all: --no-deps`. Every
hash was checked against PyPI's JSON for its version (2026-11-14); each
file says which hashes the scan read and which were looked up on PyPI
(pytest 9.2.0 and tzdata). Where a distribution has a pure-Python wheel,
only that wheel is pinned (charset-normalizer, simplejson), so that the
environment has less native code. whitenoise has 15 distributions, one of
them compiled (brotli); funcy 6, none; python-barcode 6, one (Pillow, with
its bundled libraries); pyrate-limiter 7, none; structlog 17, two
(time-machine, zope.interface).

The lead's decisions on the points that the scan left open:

1. python-barcode is held as its PyPI sdist, as dagster-pipes: the
   checkout at the tag cannot be imported. A drawn package is not
   replaced. The other four are git sources at the draw's commits.
2. python-barcode's 19 test items that write into `tests/test_outputs/`
   run: without them only `test_generate_with_bytesio` would render a
   barcode through a writer, and Pillow would be of no use. The plugin
   `plugins/outputs_cleanup.py` (outside the checkout, loaded by
   `trace.py`, client code for the tracer) records the files of the
   checkout at session start and at its end removes what is new in that
   one directory and nothing else; if anything else changed, it raises and
   the run fails. Pillow is installed, so that the image writer runs.
3. One pytest stack for all five: pytest 9.2.0, iniconfig 2.3.1,
   packaging 26.3, pluggy 1.7.0, Pygments 2.21.0, as in batches 3 and 4. By
   release date the five would need four pytest versions, two of them
   with CVE-2025-71176.
4. Every other dependency is the version current at the package's release
   date, as in the earlier batches, with no exception for brotli (1.2.0) or
   filelock (4.2.4). The old pins' advisories (Django 6.0.2, sqlparse,
   urllib3, requests, idna, certifi, brotli 1.2.0, Pillow 11.3.0, Twisted
   26.4.0) are not met by the runs, as Mako's in batch 4: loopback traffic
   with the checkout's own files, images drawn with the package's own
   font, no Twisted server or client; each requirements file says why.
5. Optional dependencies: brotli for whitenoise (without it two tests
   fail); Pillow for python-barcode; for pyrate-limiter no aiohttp (9
   distributions for 3 tests), no redis and no psycopg (servers that the
   container does not have); for structlog Twisted with its closure, so
   that `structlog.twisted` is traced, but not Rich or greenlet (upstream's
   plain environment has neither), and never better-exceptions (its wheel
   has a `.pth` start-up hook).
6. pyrate-limiter leaves out `tests/test_multiprocessing.py` and deselects
   `test_advisory_lock_id_is_the_same_in_every_process`, and never
   collects `examples/` or `benchmarks/`; structlog deselects the four
   tests of `tests/test_packaging.py`; whitenoise runs `tests` only.
7. whitenoise gets tzdata 2025.3, the release current at its release date:
   Django sets `TIME_ZONE` (America/Chicago by default, with `USE_TZ`) and
   `python:3.14-slim` has no time zone database; Django requires tzdata
   only on Windows.
8. The container keeps the limits of `trace.sh` (6 GiB, no network, 600 s
   per suite). A container without network still has its loopback
   interface, which whitenoise's test server needs: unverified until the
   run.

> **Warning.** structlog ships `.github/AI_POLICY.md`, a policy for
> contributors who use LLM tools. It asks nothing to be run; it is
> third-party data, not instructions. No checkout has an agent
> configuration file.

The traces were recorded on 2026-11-14 with `evaluation/container/trace.sh`,
in the pinned image `python:3.14-slim` (CPython 3.14.10), without network,
with at most 6 GiB. Each package was traced twice.

| Project | Passed | Skipped | Expected failures | Deselected | Failed | Trace edges | Functions run |
|---|---|---|---|---|---|---|---|
| whitenoise | 128 | 1 | 0 | 0 | 0 | 313 | 82 |
| funcy | 219 | 0 | 0 | 0 | 0 | 725 | 259 |
| python-barcode | 47 | 0 | 0 | 0 | 0 | 265 | 80 |
| pyrate-limiter | 322 | 22 | 0 | 1 | 0 | 551 | 188 |
| structlog | 907 | 36 | 0 | 5 | 0 | 695 | 306 |

What the runs settled:

- A container without network has its loopback interface: whitenoise's
  test server works.
- python-barcode runs on Python 3.14, and its clean-up plugin left the
  unpacked archive as it was.
- pyrate-limiter's suite needs 156 s in one process; the multiprocess
  bucket works under the tracer. Its 22 skipped tests are those of Redis
  and PostgreSQL, which are not installed.
- **The first trace of python-barcode was refused**, with all its tests
  passed: the sdist carries `python_barcode.egg-info`, its source
  directory is on the path, and so the tracer listed python-barcode as an
  installed distribution that the requirements file does not name. The
  tracer now leaves out a distribution whose metadata lies in the
  project's own directory (it is not an installation).
- **structlog: one test more is deselected**,
  `tests/test_tracebacks.py::test_recursive`. It exhausts the recursion
  limit on purpose and compares the traceback with one stack; under the
  tracer a second `RecursionError` is raised in the tracer's own hook, and
  the test fails. It failed in the first run only because of the tracer.
  The trace has the same 695 edges with and without it.
- **Two runs of one package gave the same bytes** for
  `dynamic/<name>.json` and `test-environments/<name>.installed.txt`, with one
  exception: the first run of pyrate-limiter counted 76 dropped call-backs
  of the tests and the three later runs 74. The edges, the functions run
  and the test counts were equal in all four runs. The count is not part
  of the graph; the cause of the difference was not found (the suite has
  timing-dependent tests). The committed trace is the last run.

What the traces do not cover:

- pyrate-limiter: the Redis and PostgreSQL tests skip, and no test imports
  `pyrate_limiter.extras`. 171 of its 284 edges from reading only have a
  caller in that code.
- python-barcode: no test imports `barcode.pybarcode`, the command line. 23
  of its 83 edges from reading only are there.
- structlog: Rich, greenlet, colorama and better-exceptions are not
  installed. Their calls are named as missing modules (see "Callees outside
  the package"), and the code that uses them runs in no test.
- Every trace misses the calls of the tracer defect T1 (see "Limits" under
  "Traces"). The ground truths add these edges from reading: 3 of
  whitenoise's 15 edges from reading only (the functions that its thread
  pools run), and 2 of pyrate-limiter's 284 (`combined_lock`, a
  `@contextmanager` generator function).

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|
| whitenoise | 94 | 323 (97 / 226) | 308 (95.4%) | 15 | 5 | 82 of 82 | 362 | 15 | 0 (0) | 0 |
| funcy | 305 | 869 (400 / 469) | 674 (77.6%) | 195 | 52 | 259 of 289 | 812 | 112 | 9 (1248) | 3 |
| python-barcode | 126 | 347 (158 / 189) | 264 (76.1%) | 83 | 1 | 80 of 107 | 390 | 25 | 10 (662) | 2 |
| pyrate-limiter | 288 | 831 (411 / 420) | 547 (65.8%) | 284 | 4 | 188 of 263 | 905 | 19 | 8 (539) | 0 |
| structlog | 367 | 828 (400 / 428) | 680 (82.1%) | 148 | 15 | 306 of 346 | 904 | 88 | 21 (7536) | 0 |
| **All** | **1180** | **3198 (1466 / 1732)** | **2473 (77.3%)** | **725** | **77** | **915 of 1087** | **3373** | **259** | **48 (9985)** | **5** |

The rejected trace edges are calls of client objects, most of them the
tests' own: the tests' WSGI application and `BytesIO` objects, the test
server's `start_response` and Django's `get_response` (whitenoise, ruling
3); the callables and objects that the tests pass in, among them their own
`defaultdict` (funcy, ruling 7); a `BytesIO` (python-barcode); a test's
subclass of an abstract state algorithm and a test's own `asyncio.Task`
(pyrate-limiter); `Mock` objects and the tests' streams (structlog). Three
of structlog's are `BaseException.__init__` of a `raise` without a call,
an implicit call of code outside the package.

The audits re-derived a sample of sites blind: a seeded draw of 70 sites
and every value site. No auditor drew by kind, and each audit says why (in
structlog 1019 of the 2519 sites are attribute loads, but its 88 value
sites are explicit calls, so explicit sites dominate the sample). The
audits and the lead's rulings changed these edges:

| Project | Sites re-derived blind | Agreements | Findings (ids of the audit file) | Edges changed by the audit | Edges changed by the rulings |
|---|---|---|---|---|---|
| whitenoise | 84 (70 drawn, 15 value sites, 1 in both) | 84 | L1, L2 (rulings), W1 to W3 (wording), R1, R2 (README) | 0 (323) | 0 |
| funcy | 173 (70 drawn, 112 value sites, 9 in both) | 144 (5 auditor errors, 21 judgement differences, 1 missed edge, 2 entries with callees that cannot reach the site) | F1 (missed edge), F2 (ledger entries), R1, R2 (rulings), R3 (README) | +1 (890 to 891: F1) | -22 (891 to 869: ruling 7) |
| python-barcode | 94 (70 drawn, 25 value sites, 1 in both) | 90 (4 auditor errors) | F1 (ruling), W1 (wording), R1 (remark), R2 (stale text) | 0 (348) | -1 (348 to 347: ruling 2) |
| pyrate-limiter | 87 (70 drawn, 19 value sites, 2 in both) | 87 | J3, J5, J6, J8, J12 (rulings), W1, W2 (wording), R1 to R4 (README) | 0 (831) | 0 |
| structlog | 156 (70 drawn, 88 value sites, 2 in both) | 152 (3 auditor errors of naming, 1 incomplete answer) | F1, F2 (missed edges), L1 to L4 (rulings) | +7 (821 to 828: F1 +6, F2 +1) | 0 |
| **All** | **594** | **557** | | **+8 (3213 to 3221)** | **-23 (3221 to 3198)** |

No audit found an edge of a graph that cannot happen. funcy's F2 corrected
two ledger entries whose edges the graph keeps through another site. The
writers' graphs had 3213 edges; after the audits and the rulings the set
has 3198 (1466 inside, 1732 outside). The binding check (step 3 of
"Auditing a ground truth": every call of a package function against the
callee's signature) was run after the audits, by one more agent, on the
corrected graphs: 1637 pairs of a site and a package callee (whitenoise
106, funcy 436, python-barcode 192, pyrate-limiter 440, structlog 463).
1543 bind; 94 depend on a client's arguments and bind for the package's
own calls or for some client call; none cannot bind. No edge changed.

The lead's rulings on the ground truths of this set (each general rule is
also stated at its place in the conventions below):

1. A call-back through library code (structlog L1, judgements 4 and 5;
   pyrate-limiter J3; whitenoise judgements 3 to 6): when a package call
   hands an object to library code, or starts library code that dispatches
   to an object which the package's documented setup registers, and the
   library then calls a package function, the package function that makes
   the library call is the caller. It generalises ruling 12 of the third
   set. No change: structlog keeps `ProcessorFormatter.format` at
   `_base.py:224:54`, `stdlib.py:374:28` and `400:34`, and the two Twisted
   observers at `_base.py:224:54`; pyrate-limiter keeps `Rate.__repr__` at
   `logger.info("... %s", rates)`, `limiter.py:182:24` (logging formats the
   record lazily); whitenoise keeps the four call-backs of Django
   (`middleware.py:197:40`, `197:43`, `129:47`; `storage.py:98:45`).
2. A client's assignment to a public attribute (pyrate-limiter J5,
   `bucket.py:253:35`; python-barcode J6 and audit R1, `codex.py:240:27`): a
   client uses the public API (constructor arguments, methods); a client's
   assignment to a public attribute of a package object counts only where
   the package's documentation or tests make that assignment.
   pyrate-limiter: no change (the probe `bucket.leak(0)` keeps
   `RedisBucket.leak` and `StateBucket.leak`). python-barcode: nothing
   assigns `code` on a built `Code128`, so `Code128._convert ->
   <builtin>.RuntimeError` goes, -1 (348 to 347).
3. whitenoise, audit L1 (judgement 1; `middleware.py:123:33`,
   `runserver.py:49:30`, `50:32`): a server or framework that calls the
   package is a client. A callable it passes is a client callback. An object
   whose type its documented API fixes is named by that type (B4). This
   extends the bottle precedent to Django: `get_response` has no callee,
   `request.META` is a dict, and the parser of `add_arguments` is Django's
   `CommandParser`. No change; the trace edge to
   `convert_exception_to_response.inner` stays rejected.
4. whitenoise, audit L2 (judgement 2; `middleware.py:139:45`, `150:51`,
   `197:43`; `runserver.py:48:30`): when library code picks an object from
   the client's configuration, the library's defaults and the
   configurations that the package documents are in scope; any other
   configured class is client code. No change: 3 edges rest on Django's
   defaults alone (`FileSystemFinder.list`, `AppDirectoriesFinder.list`,
   `FileSystemStorage.path`), and the trace has all 3.
5. funcy, audit R3 and F1 (`funcs.py:110:49`): an expression in the
   documentation that passes a package function in a role is a documented
   example, in prose as in a code block. `docs/primitives.rst:19` calls
   `notnone` "a shortcut for `complement(isnone)`": +1 inside edge,
   `compose.<lambda1>.<lambda1> -> funcy.primitives.isnone`.
6. funcy, audit R1 (judgement J3; `funcmakers.py:22`, `objects.py:47`,
   `52`): where the documentation names a concrete type for a client value
   ("set", "property"), the value is named by that type (B4), although the
   code tests an abstract class. No change: the 15 edges to
   `<builtin>.set.__contains__` and the 2 to `<builtin>.property.__get__`
   and `__set__` stay.
7. funcy, audit R2 (judgement J6): documentation is read one entry at a
   time: a type list in one function's entry names client collections for
   that function only. -22 edges (891 to 869), each checked by the writer
   (for example `empty` and `walk_values` -> `set`, `tuple`,
   `OrderedDict`). 1 trace edge moves to the rejected edges:
   `join -> collections.defaultdict.copy`, the tests' own value.
8. python-barcode, audit F1 (judgement J5; `codex.py:57:49`): `__init__`
   receives the object being made; its receivers are the instances whose
   construction reaches it, with the arguments the construction passes. A
   client that calls `__init__` again on a built object is not considered.
   No edge `Code39.__init__ -> PZN7.calculate_checksum`: no change.
9. python-barcode, audit W1 (`codex.py:169:29`): B3 ("an object left
   behind after an error") covers any exception that leaves the object
   half-changed, a failed lookup too. No change: the `ValueError` of
   `_new_charset` has no edge.
10. python-barcode, judgement J1 (`base.py:37-38`): a class whose own
    `__init__` always raises has no instance, so `Barcode` is no receiver
    of its own methods (B1). No change.
11. python-barcode, judgement J7: a check that cannot fail under the
    package's own values has no callee (the precedents are markdown2's
    judgement J6 and Sublist3r's `sublist3r.py:899`). No change: the five
    checks at `base.py:43`, `114`, `ean.py:120`, `upc.py:108` and
    `codex.py:169` keep no callee.
12. pyrate-limiter, judgement J12 (`in_memory_bucket.py:75:34`, `77:34`): a
    library function that the library defines with `exec` has no name and
    no edge (`ListProxy.append` and `.extend` of
    `multiprocessing.managers`). No change.
13. pyrate-limiter, judgement J8 (`redis_state.py:86:40`): a call of a stub
    instance is named by the stub's path, as `validate.py` does
    (`redis.Redis.register_script`, `redis.asyncio.Redis.register_script`).
    No change.
14. pyrate-limiter, judgement J6 (`wrappers.py:17-96`): a
    `BucketAsyncWrapper` that wraps a `BucketAsyncWrapper` stays; the
    annotation and the `isinstance` check admit it. No change (its 11 self
    edges stay).
15. structlog, audit F1 and L3 (judgement 6; `tracebacks.py:173:32`):
    accepted. `to_repr` formats frame locals; the package's own raising
    frames hold package objects (B2): the locals of the package's own
    frames, on a raise that the package documents or makes on purpose, are
    in the role. +6 inside edges (`__repr__` of `BoundLoggerBase`,
    `_ThreadLocalDictWrapper`, `PrintLogger`, `WriteLogger`, `BytesLogger`,
    `CapturingLogger`), each checked by the writer (which function, which
    documented exception).
16. structlog, audit F2 and judgement 5 (Twisted's call-backs;
    `twisted.py:248:51`): verified against the pinned Twisted 26.4.0 wheel,
    read as a zip from the security scan's cache, never run. F2 accepted,
    +1 inside edge (`JSONLogObserverWrapper.__call__ ->
    ReprWrapper.__repr__`); the 5 edges of judgement 5 stay.
17. structlog, audit L2 (judgement 8; `_config.py:355:38`, `410:32`,
    `threadlocal.py:123:50`, `196:66`): B4. `type[Context]` fixes `dict`,
    so `<builtin>.dict` stays at the four sites. No change.
18. structlog, audit L4 (judgement 9; `processors.py:675:44`): a package
    Protocol names the classes that the package documents as its
    implementations. `ExceptionPrettyPrinter.__call__ ->
    ExceptionDictTransformer.__call__` stays. No change.

**For the record.** The pyrate-limiter writer downloaded three wheels from
PyPI to read them (requests 2.34.2, httpx 0.28.1, httpx2 2.15.1; judgement
9). It only read them; its brief did not allow network use. The auditor
confirmed judgement 9 from local copies of the same releases. The
structlog writer and auditor read the pinned Twisted 26.4.0 wheel, and the
whitenoise writer and auditor the pinned Django 6.0.2 wheel, from the
security scan's cache: as zip files, with their hashes checked against the
pins, and nothing run. The whitenoise writer ran a few read-only commands
with its working directory inside the checkout; nothing was run or written
there, and the checkout is clean.

### Batch 6

The ten packages that `draw.py` drew in rounds 4 and 5
(`selection/round-4.json`, `round-5.json`, one per size stratum and
round; see "How the benchmark grew"). All ten are git sources at the
draw's commits.

| Project | Release | Licence | Source | Analysed source | Code lines (draw) |
|---|---|---|---|---|---|
| path | v17.1.1 | MIT | git | `path/` | 1126 |
| django-constance | 4.5.0 | BSD-3-Clause | git | `constance/` | 1239 |
| tinytag | 2.3.2 | MIT | git | `tinytag/` without `tinytag/tests/` | 2243 |
| jsonpickle | v4.1.4 | BSD-3-Clause | git | `jsonpickle/` | 2557 |
| json-repair | v0.64.2 | MIT | git | `src/json_repair/` (root `.`) | 3416 |
| django-environ | v0.14.0 | MIT | git | `environ/` | 894 |
| validators | 0.36.0 | MIT | git | `validators/` (root `src`) | 1370 |
| tabulate | v0.10.0 | MIT | git | `tabulate/` | 1789 |
| more-itertools | v11.2.1 | MIT | git | `more_itertools/` | 2703 |
| prometheus-client | v0.26.0 | Apache-2.0 AND BSD-2-Clause | git | `prometheus_client/` | 3607 |

Two security scans came first, one per round (2026-11-22, Claude Fable
5.2). They read the ten trees and PyPI's JSON as data and ran nothing; they
downloaded no wheel and no sdist. They found no malicious code, no
obfuscated payload, no install hook, no `.pth` or `.pyc` file and no
misspelt dependency: nothing blocks the runs. Every restriction is about
what is collected or installed, or about the tracer. The tests run only as
the scans recommend and as the lead decided (below), in the container of
batch 3; `projects.toml` holds each restriction with its reason:

| Project | Tests run | Left out, and why |
|---|---|---|
| path | `path` and `tests` with the project's `pytest.ini` (the doctests, as upstream; 114 test functions by reading), with more-itertools and appdirs | the 2 tests that start child interpreters (`test_import_time`, `test_no_dependencies`: the tracer does not see them, and they write bytecode into the source copy); `docs/conf.py`, which a bare `pytest` imports |
| django-constance | `tests` (154 test functions by reading, and 5 of a mixin), with pytest-django by `-p`, the package's own plugin `constance.test.pytest` by `-p`, `--ds=tests.settings` and `-o django_find_project=false`; Django 6.1.2, redis and tzdata | nothing (upstream also runs the suite with Django's runner) |
| tinytag | `tinytag/tests/test_all.py` (20 test methods) | `tinytag/tests/test_cli.py` (14 tests, each `sys.executable -m tinytag` through a shell: the tracer does not see them, and they write bytecode into the source copy) |
| jsonpickle | `jsonpickle` and `tests` with the project's `pytest.ini` (the doctests, as upstream; 323 test functions by reading), with numpy, pandas, simplejson and tzdata | 9 tests that fail with or without the tracer (deselected after the first trace: 5 count warnings and meet the package's own `DeprecationWarning` about `keys`, 1 uses the numpy type code `a3`, which numpy 2.5.4 refuses, 3 compare string columns that pandas 3.0 stores in its string dtype); the tests of pymongo, ecdsa, feedparser, SQLAlchemy, scikit-learn, PyYAML, ujson and gmpy2 skip (not installed); never `bson` |
| json-repair | `tests` (306 test functions by reading), with jsonschema and pydantic and their closures | `tests/test_performance.py` (timing limits; pytest-benchmark); the mypy tests and the Flask tests skip (not installed: a type tool that would read the package, and a second import of it as `json_repair`) |
| django-environ | `tests`, without Django | nothing |
| validators | `tests`, with eth-hash and pycryptodome (upstream's lock) | the doctests: upstream's `pytest .` imports `docs/conf.py`, `package/export` and the package a second time as `src.validators` |
| tabulate | `tabulate` and `test` with `--doctest-modules` (the doctests, as upstream), with wcwidth | `test/test_cli.py` (11 child interpreters, which the tracer does not see); the numpy and pandas tests skip (not installed); `benchmark/` |
| more-itertools | `tests` (761 test methods by reading) | nothing; the doctests that `load_tests` adds for unittest do not run under pytest |
| prometheus-client | `tests`, with asgiref; servers on loopback and `localhost` | the Twisted, aiohttp, Django and snappy tests skip (not installed, as in upstream's Python 3.14 environment); without pytest-benchmark, `tests/test_parser.py` defines no benchmark test |

**Provenance** as for batch 3: `test-environments/<name>.txt` lists the full
closure for CPython 3.14 on Linux aarch64 by version and SHA-256, for
pip's `--require-hashes --only-binary :all: --no-deps`. The closure was
computed from the `requires_dist` of each pinned release in PyPI's JSON,
with the markers evaluated for CPython 3.14 on Linux; every hash was
checked against PyPI's JSON for its version (2026-11-22). No wheel was
read: each file says which hashes the scans list and which were looked up
on PyPI. Where a distribution has a pure-Python wheel, only that wheel is
pinned (simplejson). path has 7 distributions, none compiled;
django-constance 11, none; tinytag 5 (pytest's stack), none; jsonpickle
11, two (numpy, pandas); json-repair 15, two (rpds-py, pydantic-core);
django-environ 5, none; validators 7, one (pycryptodome, an abi3 wheel);
tabulate 6, none; more-itertools 5, none; prometheus-client 6, none. Every
distribution has a wheel for CPython 3.14 on Linux aarch64.

The lead's decisions on the points that the scans left open:

1. One pytest stack for all ten: pytest 9.2.0, iniconfig 2.3.1, packaging
   26.3, pluggy 1.7.0, Pygments 2.21.0, as in batches 3 to 5. Every other
   dependency is the version current at the package's release date (and,
   where upstream has a lock, its version: json-repair, validators), with
   one exception: django-constance gets tzdata 2026.5, not 2026.6, which
   was uploaded 5 hours before the release (the older release, the pin of
   jsonpickle too).
2. path: appdirs 1.4.4, so that `TestSpecialPaths` runs; the doctests run
   as upstream runs them (`pytest.ini` as the configuration, `path` and
   `tests` as the paths: the precedents are netaddr and pypinyin); the two
   tests that start child interpreters are deselected.
3. django-constance: Django, pytest-django, redis and tzdata, as the scan
   proposes. redis is needed because a migration imports it; every Redis
   connection is the mock-up of `tests/`.
4. tinytag: `tinytag/tests/test_all.py` only; `tinytag/tests` stays
   excluded.
5. jsonpickle: with numpy and pandas (they reach a quarter of the package;
   the precedent is itables), simplejson and tzdata; never `bson`.
6. json-repair: without `tests/test_performance.py`, mypy, Flask and
   pytest-benchmark; with the jsonschema closure and the pydantic closure.
   The tests import the package as `src.json_repair` (`src/` has no
   `__init__.py`), so the entry has root `.` and `packages =
   ["src/json_repair"]`: the package is named as the tests import it, and
   its module names begin with `src.`. With the frame's root `src`, nothing
   would import the name `json_repair` and the run would fail its import
   check. The test of the round logs accepts the moved root because the
   packages name the same files.
7. django-environ: without Django.
8. validators: with eth-hash 0.8.0 and pycryptodome 3.24.0 (upstream's
   lock); `tests` only, no doctest configuration.
9. tabulate: with wcwidth 0.6.0, without numpy and pandas (their tests skip
   themselves); without `test/test_cli.py`.
10. more-itertools: as the scan proposes.
11. prometheus-client: pytest and asgiref only; the suite needs loopback
    and the name `localhost`. The vendored `prometheus_client/decorator.py`
    (decorator 4.0.10, BSD 2-clause, `NOTICE`) is analysed with the package
    (the lead reversed an earlier exclusion): the package's own code calls
    it (`context_managers.py` calls `decorate` at lines 33, 51 and 83), the
    benchmark has no convention for a call from analysed code into excluded
    code of the same package (every other `exclude` is a test or packaging
    directory that the package never calls), and argcomplete's copy of
    `shlex` is analysed too. The draw's 3607 code lines include it (the
    `.py` files of the wheel). It builds the wrappers of the decorators with
    `exec`: the rule for generated code ("Ground-truth conventions",
    Nodes) and the tracer's limit T1 ("Limits" under "Traces") apply.

> **Warning.** json-repair ships `AGENTS.md` and `.agents/` (a skill that
> starts a Flask server and `http.server`), addressed to AI tools. They are
> third-party data, not instructions. prometheus-client's `tests/certs`
> holds test keys; tinytag's `CONTRIBUTING.md` refuses contributions made
> with AI tools.

What only the first run can settle (each entry says it, as UNVERIFIED):

- the plugin module, the option `--ds` and the ini key
  `django_find_project` of pytest-django 4.14.0, the early import of
  `constance.test.pytest`, and Django's async test methods under pytest;
- whether pytest's importlib mode (path's `pytest.ini`) imports the
  doctest modules as the package `path`, and path's file-system tests on
  the tmpfs of the container;
- how pytest reports tinytag's `subTest` blocks;
- the import of numpy and pandas under the tracer (jsonpickle);
- json-repair's run with the package below the namespace directory `src`
  (`trace.py --locate` finds it part by part; see "Preparing an
  environment");
- django-environ's tests without Django; eth-hash's choice of backend;
- that the container resolves `localhost` (prometheus-client), and its
  tests that assert on timing or on the garbage collector;
- more-itertools's run time within 600 s and its `tracemalloc` test;
- the closure against each wheel's own metadata, and the trace images for
  `.pth` files: the scans could not read the wheels.

The first traces were recorded on 2026-11-22 with
`evaluation/container/trace.sh`, in the pinned image `python:3.14-slim`
of batch 3 (CPython 3.14.10, linux/aarch64), without network, with at most
6 GiB. Each package was traced twice, and both runs gave the same edges.
Each point above held, but one: jsonpickle had 9 failing tests.

| Project | Passed | Skipped | Expected failures | Deselected | Failed | Trace edges | Functions run |
|---|---|---|---|---|---|---|---|
| path | 140 | 1 | 0 | 2 | 0 | 499 | 177 |
| django-constance | 178 | 1 | 0 | 0 | 0 | 499 | 144 |
| tinytag | 20 | 0 | 0 | 0 | 0 | 400 | 74 |
| jsonpickle | 379 | 19 | 0 | 0 | 9 | 775 | 219 |
| json-repair | 403 | 2 | 0 | 0 | 0 | 724 | 141 |
| django-environ | 433 | 0 | 0 | 0 | 0 | 235 | 65 |
| validators | 1069 | 0 | 0 | 0 | 0 | 394 | 94 |
| tabulate | 312 | 16 | 0 | 0 | 0 | 335 | 74 |
| more-itertools | 765 | 0 | 0 | 0 | 0 | 995 | 286 |
| prometheus-client | 416 | 12 | 0 | 0 | 0 | 847 | 241 |

path's deselected tests are the 2 of `deselect`. tinytag counts its 20
test methods; their `subTest` blocks are not tests. jsonpickle's 9 failed
tests fail with or without the tracer, against this release or against
the installed numpy and pandas: 5 count the warnings of a call and also
meet the package's own `DeprecationWarning` about `keys` (added in 4.1.2;
pytest records every `DeprecationWarning`), 1 builds a record array with
the type code `a3`, which numpy 2.5.4 refuses, and 3 compare string
columns that pandas 3.0 stores in its default string dtype, where the
package decodes object columns. Upstream names no version of numpy or
pandas (its extra `testing` is unpinned, and it has no lock), so the 9
tests are deselected, each with its reason, as aiocache's 2 that fail on
Python 3.13 and later; the trace of jsonpickle is recorded again with them
deselected. The row above is its first trace.

### Batch 7

The ten packages that `draw.py` drew in rounds 6 and 7
(`selection/round-6.json`, `round-7.json`, one per size stratum and round;
see "How the benchmark grew"), from the frozen frame, with the procedure
unchanged. Round 6 drew pyfiglet, uncertainties, einops, pymysql and segno
(seed 2612795115469913897); round 7 drew tinydb, pgvector, textdistance,
websocket-client and mss (seed 16299633012922554993), with one drop:
`dill`, because a tool run touched it, and the draw took `mss`, the next
project of the order in stratum 5. Eight are git sources at the draw's
commits; uncertainties and pyfiglet are their PyPI sdists, because their
checkouts lack files that the build writes (`uncertainties/version.py`,
which `__init__.py` imports, and the package `pyfiglet/fonts`).

| Project | Release | Licence | Source | Analysed source | Code lines (draw) |
|---|---|---|---|---|---|
| pyfiglet | 1.0.4 | MIT | sdist | `pyfiglet/` without `pyfiglet/tests/` and `pyfiglet/test.py` | 831 |
| uncertainties | 3.2.3 | BSD-3-Clause | sdist | `uncertainties/` | 1521 |
| einops | v0.8.2 | MIT | git | `einops/` without `einops/tests/` | 1883 |
| pymysql | v1.2.3 | MIT | git | `pymysql/` without `pymysql/tests/` | 3074 |
| segno | 1.6.6 | BSD-3-Clause | git | `segno/` | 3126 |
| tinydb | v4.9.0 | MIT | git | `tinydb/` | 809 |
| pgvector | v0.5.1 | MIT | git | `pgvector/` | 1244 |
| textdistance | 4.6.3 | MIT | git | `textdistance/` | 1735 |
| websocket-client | v1.9.2 | Apache-2.0 | git | `websocket/` without `websocket/tests/` | 2739 |
| mss | v10.2.0 | MIT | git | `mss/` (root `src`) | 3365 |

**The selection stage.** The ten trees were fetched at their pins by
`evaluation/container/fetch.py` into a Docker volume and read there, in
containers without network; nothing of a package was run, and no analysis
tool had run on them. The record of that stage is with the audit records:
the proposed entries, the test environments, and the veto list with a
paragraph per package and, for pymysql, pgvector, mss and
websocket-client, how many tests run in the tracer's environment and what
the rest would need. The maintainer's answer to the veto list
(2026-11-22) was "ok on all": no veto, the ten as drawn.

**Two security scans** (2026-11-22, Claude Fable 5.2; part A uncertainties,
einops, segno and tinydb; part B textdistance, websocket-client, pymysql
and pgvector) read the trees and PyPI's JSON as data and ran nothing. They
found no malicious code, no obfuscated payload, no install hook, no `.pth`
or `.pyc` file and no typosquat: the eight test runs are safe as planned,
pymysql only with its nine named paths and pgvector only with its four files
and no database client installed. pyfiglet and mss have no test run and
needed no scan of a run. Before the first trace of each, the lead ran a
check in its trace image, with `-S` and with limits of memory, processes,
CPU and time (the checks that both scans ask for before a run: no start-up
file in the site directories, the installed closure exactly the pins, every
RECORD and numpy's and scipy's layout, the entry points, the modules kept
out in any importable form, pytest's `tmpdir`, the source equal to the
scanned tree, the loopback ports closed and the name lookups; the import of
Hypothesis only after all of them passed); a problem stopped the package.
Its output is with the record of the selection stage. The recordings of
each package follow the rule of batch 7 in "Repeatability".

| Project | Tests run | Left out, and why |
|---|---|---|
| pyfiglet | none | every test runs the console script through a shell (the kind of suite for which `sh` was vetoed in batch 6); the ground truth comes from reading only |
| uncertainties | `tests` with `pyproject.toml` (58 test functions, about 700 items), with numpy | `test_repeated_summation_complexity` (timing), `test_monte_carlo_comparison` (10**6 unseeded samples); the doctests |
| einops | `einops/tests` (65 test functions) with numpy and `environment = { EINOPS_TEST_BACKENDS = "numpy" }` | the tests of torch, keras and flax skip (not installed) |
| pymysql | nine named paths: 33 items that need no server | 161 items that need a MySQL or MariaDB server (`test_connection.py` connects at import); `tests/test_auth.py`; the doctests of `converters.py` |
| segno | `tests` (641 test functions), with pypng | `test_plugin` (needs qrcode-artistic and Pillow); 7 decoding tests skip (no pyzbar); `test_dataoverflow_error` stays, deselected only if the run hits the time limit |
| tinydb | `tests` (152 test functions, about 219 items), with PyYAML 6.0.3 | nothing (`pytest.ini` needs pytest-cov) |
| pgvector | the four files of the types: 63 items, with numpy and scipy | 459 items that need PostgreSQL with pgvector and eight client libraries (seven files connect at import) |
| textdistance | `tests -m "not external"` with `setup.cfg` (66 test functions), Hypothesis 6.140.4 and numpy, with `plugins/hypothesis_profile.py` | the 3 `external` tests; the libraries that it imports by name (rapidfuzz, jellyfish, Levenshtein, pyxDamerauLevenshtein, distance, pylev; tabulate) are never installed |
| websocket-client | `websocket/tests` (221 test methods): 195 run | 26 skip by themselves (10 need the local echo server, 15 the internet, 1 always); no `environment` |
| mss | none | as shipped, a session fixture connects to an X display: no test runs without one; the ground truth comes from reading only |

**Environments.** `test-environments/<name>.txt` for the eight: the
closure for CPython 3.14 on Linux aarch64 from PyPI's JSON, every hash
PyPI's, pytest's stack of batches 3 to 6, every other version the newest
release on or before the package's release, with two exceptions: numpy
2.3.2 for uncertainties and textdistance (the oldest numpy with a cp314
aarch64 wheel), and Hypothesis 6.140.4 for textdistance, the first release
that declares Python 3.14 (6.108.2 and attrs 23.2.0, current at its
release, declare 3.12 at most), with its closure at its own date (attrs
25.4.0, sortedcontainers 2.4.0).

**What the traces cannot cover, and why the four stay.** pymysql and
pgvector run only their offline tests (33 and 63 items): most of each
package talks to a database server. mss and pyfiglet have no test run. The
maintainer kept all four (2026-11-22): a drawn package is not replaced
because its suite cannot run in the tracer's environment (no package has
been dropped for that; partial suites were kept since batch 1, and three
ICSE 2021 projects have no test run). Their ground truths come mostly or
wholly from reading, so each gets a doubled blind audit.

**For the tracer.** websocket-client: the tracer's own `no_proxy` exempts
127.0.0.1 from the proxy that `test_connect` sets, so the trace has the
direct branch (a refused connection to 127.0.0.1:443) where upstream's CI
takes the proxy branch; the tests that run make that one loopback attempt
and five name lookups that must fail, and two test files import modules of
the package a second time. einops, uncertainties and pgvector draw test
data from unseeded random numbers (see "Repeatability"). pymysql ships an
`AGENTS.md` addressed to agents (see the warning of "Traces").

### Batch 8

The frame had too few projects left for two complete rounds:
stratum 2 holds only asgiref, which is touched. By the rule fixed before the
draw ("Choosing a new batch"), rounds 8 and 9 drew from strata 1, 3, 4 and
5, and the partial round 10 from strata 1 and 3 (`selection/round-8.json`,
`round-9.json`, `round-10.json`). Round 8 drew honcho, nodeenv, flit-core
and pyusb (seed 5460937401858195157), after three drops: cerberus and
platformdirs (in the corpora of the scalability runs; platformdirs also in
itables' trace environment) and `sh` (the maintainer's veto of round 4). Round 9 drew
vulture, toolz, tablib and avro (seed 3989746975721607198), round 10
pubchempy and m3u8 (seed 6284874201124768312). Nine are git sources at the
draw's commits; avro is its PyPI sdist, because its checkout does not import
(`avro/__init__.py` reads `VERSION.txt`, and `avro/ipc.py` two schemas,
which `setup.py` copies from `share/` at build time).

| Project | Release | Licence | Source | Analysed source | Code lines (draw) |
|---|---|---|---|---|---|
| honcho | v2.0.0 | MIT | git | `honcho/` | 835 |
| nodeenv | 1.12.0 | BSD-3-Clause | git | `nodeenv.py` | 1793 |
| flit-core | 4.2.0 | BSD-3-Clause | git | `flit_core/` (root `flit_core`; its vendored tomli included) | 2855 |
| pyusb | v1.3.1 | BSD-3-Clause | git | `usb/` | 3245 |
| vulture | v2.16 | MIT | git | `vulture/` (not `dev/`: no importable module) | 1161 |
| toolz | 1.2.0 | BSD-3-Clause | git | `toolz/` without `toolz/tests/` and `toolz/sandbox/tests/`, and `tlz/` | 2144 |
| tablib | v3.10.0 | MIT | git | `tablib/` (root `src`) | 2416 |
| avro | 1.12.2 | Apache-2.0 | sdist | `avro/` without `avro/test/` | 3697 |
| pubchempy | v1.0.5 | MIT | git | `pubchempy.py` | 1159 |
| m3u8 | 6.0.0 | MIT | git | `m3u8/` | 1934 |

**The selection stage.** The ten trees were fetched at their pins into a
Docker volume and read there, in containers without network; nothing of a
package was run, and no analysis tool had run on them. The record of that
stage (the rule, the draw, the proposed entries and environments, the
writers', auditors' and referee's briefs, the veto list, the checks of the
trace images and the script of the trace run) is with the audit records;
`selection/batch-8-proposal/` holds the referee's rulings (`rulings/`) and
the samples, draw scripts and blind answers of the audits (`audits/`). The
maintainer's answer to the veto list (2026-11-24, "just move forward"): no veto; pubchempy without a test
run and pyusb with about 15 tests, each with a doubled blind audit; avro as
its sdist with a pytest run; tablib with odfpy built from its pinned sdist
in a container after a scan of that sdist; MarkupSafe 3.0.3 for honcho.
**Two security scans** (2026-11-24, Claude Fable 5.2; part A honcho,
nodeenv, flit-core, pyusb and the build of odfpy; part B vulture, toolz,
tablib with odfpy, avro and m3u8) read the exported trees, odfpy's sdist
and PyPI's JSON as data and ran nothing. They found no malicious code, no
obfuscated payload, no install hook, no `.pth` or `.pyc` file and no
typosquat: the nine test runs are safe as planned, with one more
deselection (avro's `test_server_with_path`, which connects to
apache.org:80), and odfpy's build is safe with restrictions (a container of
its own, setuptools alone, no network; `wheels/README.md`). The lead's
decisions on their points (2026-11-24): pyusb keeps
`FindDescriptorTest::runTest` as a declared failure; nodeenv's untraced
children are accepted; toolz's `test_has_version` is deselected and its
`filterwarnings = error` kept; vulture's `dev/` is not analysed. flit-core's
documentation holds a policy addressed to AI tools: data, not followed (the
benchmark changes nothing in Flit). The checks of each trace image before
its first trace are with the record of the selection stage.

**typeshed's stub of m3u8.** The frozen engine (PyCG `2372b60`) holds
typeshed's stub data of m3u8 6.0.* (`pycg/analysis/stub_data/third_party/
m3u8.json`, and a row of `stub_data/README.md`), generated from one commit
of typeshed for all stubs, before batch 8 was drawn; nothing in it was
written for the benchmark. The analysed package wins over a stub of its
name (PyCG `docs/design.md`), so the analysis of m3u8 does not read it.

| Project | Tests run | Left out, and why |
|---|---|---|
| honcho | `tests` (92 test functions; 86 run), with mock and Jinja2 | `tests/integration` (13: the console script and child processes); `test_invocation` (a child interpreter); 5 manager tests that start a `multiprocessing.Process` with a local function (Python 3.14's forkserver cannot pickle it; inferred) |
| nodeenv | `tests -m "not integration"` (245 test functions; about 225 run), with shtab | the 9 integration tests (Node.js downloads); `test_module_run_completes_nodeenv` (a child interpreter); the Windows file skips, and each shell test skips without its shell |
| flit-core | `flit_core/tests_core` (80 test functions), with testpath | `tests/` (flit's) |
| pyusb | `test_find.py`, `test_interop.py`, `test_util.py` (16; `FindDescriptorTest::runTest` fails with `NoBackendError`, declared) | 54 tests that need the PIC test device over libusb |
| vulture | `tests` (274 test functions; about 260 run) | `tests/test_script.py` and `test_invalid_cmdline_args` (child interpreters) |
| toolz | `toolz --doctest-modules` with `pyproject.toml` (163 test functions and about 288 doctest examples) | `test_has_version` (toolz is not installed, so it has no metadata); `bench/` |
| tablib | `tests` (183 test functions), with openpyxl, PyYAML, tabulate, xlrd, xlwt, defusedxml and odfpy (the wheel built here) | none |
| avro | `avro/test` (144 test methods; about 119 run) | `test_script.py`, the tether tests (child processes, Java), `test_minimum_speed` (timing), `test_server_with_path` (connects to apache.org:80); the cases of `load_tests` run only under unittest (the plugin `plugins/avro_load_tests.py` keeps the eight classes that only `load_tests` can instantiate out of collection) |
| pubchempy | none | every test calls the PubChem web service; the ground truth comes from reading only |
| m3u8 | `tests` (267 test functions; 263 run) | 4 loader tests that need the local bottle server on port 8112 |

**Environments.** `test-environments/<name>.txt` for the nine with a run, by the
rule of batch 7 (pytest's stack of batches 3 to 7; every other version the
newest release on or before the package's release, with a usable wheel),
with one exception: MarkupSafe 3.0.3 for honcho (the oldest MarkupSafe with
a cp314 aarch64 wheel). odfpy 1.4.1 has no wheel in any release: its wheel
was built from its pinned sdist (`odfpy-1.4.1.tar.gz`, SHA-256
`db766a6e59c5103212f3cc92ec8dd50a0f3a02790233ed0b52148b70d3c438ec`) in a
container after the scans, with setuptools 83.0.0 alone, twice with the
same bytes, and checked against the sdist; it is
`wheels/odfpy-1.4.1-py2.py3-none-any.whl` (SHA-256 `19548df9…af2f8`),
pinned in `test-environments/tablib.txt` by that hash (`wheels/README.md`).

**For the tracer.** Code that runs in a child process is not traced.
honcho's ten `TestManager` tests make `multiprocessing.Queue` objects, which
start the resource tracker (a child) and need a writable `/dev/shm` (the
container has one); toolz's `test_fold` maps through a `Pool`. nodeenv runs
`sh`, `dash` and `bash` on scripts that it writes, each with a child Python,
`python -m venv` five times and three child interpreters of
`nodeenv.py --print-completion`, and starts an HTTP server on 127.0.0.1
(the lead accepts these children). odfpy appends its own directory to
`sys.path` at import, so its modules also answer to top-level names
(`table`, `text`); with defusedxml installed, openpyxl parses through
`defusedxml.ElementTree`. No test of batch 8 that runs draws unseeded
random data (see "Repeatability").

### Ground truths

| Project | Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|---|
| jmespath | 190 | 430 (310 / 120) | 424 (98.6%) | 6 | 4 | 179 of 182 | 519 | 22 | 0 (0) | 1 |
| tenacity | 190 | 560 (361 / 199) | 405 (72.3%) | 155 | 7 | 156 of 179 | 592 | 46 | 12 (192) | 42 |
| cachetools | 181 | 623 (465 / 158) | 504 (80.9%) | 119 | 13 | 173 of 174 | 671 | 53 | 1 (512) | 14 |
| pluggy | 114 | 277 (112 / 165) | 269 (97.1%) | 8 | 3 | 100 of 101 | 455 | 23 | 3 (402) | 9 |
| h11 | 100 | 286 (150 / 136) | 281 (98.3%) | 5 | 0 | 85 of 89 | 472 | 23 | 2 (287) | 6 |
| **All** | **775** | **2176 (1398 / 778)** | **1883 (86.5%)** | **293** | **27** | **693 of 725** | **2709** | **167** | **18 (1393)** | **72** |

The counts are those of the site finder after it learned the accessors of
`property(...)` and stopped counting annotations without a value.

"Confirmed by the trace": ground-truth edges that the trace of the test
suite has; every other trace edge is rejected (rule A), here a client
callback. "Default
rejections (sites)": the defaults, and the sites they decide, counted as
candidate-site pairs: a site that two defaults decide counts twice (bottle,
in batch 4: 46 defaults decide 12946 pairs). "Exclusions":
`exclude` lines.

The audits (see "Auditing a ground truth") re-derived a sample of sites
blind and changed these edges:

| Project | Sites re-derived blind | Disagreements | Edges changed by the rules (writer) | Edges changed by the audit |
|---|---|---|---|---|
| jmespath | 79 | 0 | 0 | -1 (431 to 430) |
| tenacity | 123 | 2 (1 auditor error, 1 convention) | -10 (567 to 557) | +3 (to 560) |
| cachetools | 133 | 10 (9 writer edges that cannot happen, 1 auditor error) | -15 (655 to 640) | -17 (to 623) |
| pluggy | 80 | 0 | 0 | -1 (278 to 277, with a ruling on B4 and B5) |
| h11 | 81 | 0 | 0 | 0 (286) |
| **All** | **496** | **12** | **-25** | **-16** |

## Choosing a new batch

Batches 1 and 2 were chosen by hand. A further batch is chosen by `draw.py`,
so that another person can run the choice again (Baltes and Ralph, EMSE
2022: write down each stage of the sampling and archive the script). It has
two steps: a quality-filtered **frame**, computed once from a fixed public
list and frozen; and a seeded **draw** from the frame, stratified by size. A
claim about a drawn batch holds for the frame, not for all of PyPI. The
thresholds are named constants at the top of the script; the frame and the
round logs record them. The logs record every public upper-case module
constant except the paths, `USER_AGENT` and the `HTTP_*` settings, and
`FILTERS` as the filter names in order: a new or renamed constant of that
form changes the logs.

**List.** `selection/top-pypi-packages-2026-11-01.json` is the 30-day
download list of hugovk/top-pypi-packages (`top-pypi-packages.min.json` at
its tag `2026.11`; 15,000 projects, collected from the public ClickHouse
PyPI dataset). The list date D is its `last_update` date. The rank of a
project is its position in the list (1: the most downloaded).

**Frame.** `draw.py frame` evaluates the projects of the list in rank order
through the filters below, cheap ones first; the first failure ends a
project. It writes `selection/frame.json`: the SHA-256, date and size of
the list, the constants, the funnel (per filter, how many projects reached
it and how many it rejected), and, for every project up to the rank
cut-off, its rank and either the filter that failed and why, or the facts
of a pass. The projects beyond the cut-off are counted in the funnel only.
The frame does not depend on the sets already built: a project of an
existing set or of `selection/excluded.txt` is evaluated like any other,
and only the draw skips it.

| # | Filter | A project passes if | Source |
|---|---|---|---|
| 1 | `rank` | its rank is at most 5,000 | SWE-bench (Jimenez et al., ICLR 2024) starts from the top 5,000 downloads; PyXray (Alexopoulos et al., ICSE 2026) uses the download list |
| 2 | `stub-name` | its name is not `types-*` or `*-stubs` | ours: a stub package has no code to analyse |
| 3 | `release` | its latest release that is neither yanked nor a pre-release and was uploaded on or before D (version order of PEP 440) was uploaded in the 3 years before D | CPyGraph (Chen and Li, arXiv 2026) uses the same window; Alfadel et al. (EMSE 2023) and JARVIS (Huang et al., arXiv 2024) require recent activity |
| 4 | `pure-python` | that release has an sdist and a wheel, and every wheel is `py3-none-any` or `py2.py3-none-any` | Pynguin (Lukasczyk et al., EMSE 2023); CPyGraph |
| 5 | `requires-python` | its `requires_python` admits Python 3.14.0 (no `requires_python` admits it) | ours: the tracer needs Python 3.14 |
| 6 | `licence` | the licence that PyPI states is permissive: every licence of `license_expression` (an exception, `WITH`, fails), else every `License ::` classifier, else a `license` field that is one identifier. A licence that PyPI does not state (no field, or a field of free text) is decided by filter 14 | SWE-bench; CodeSearchNet (Husain et al., arXiv 2019); DaCapo (Blackburn et al., OOPSLA 2006) |
| 7 | `no-dependency` | no `requires_dist` entry applies on CPython 3.14 on Linux without an extra; a marker with another variable fails wherever the variable is, since every comparison is evaluated; a comparison is between versions when both sides are versions, else between strings, and `~=` and `===` compare versions only (PEP 508) | ours, with no precedent in the literature: the ground truth covers the package without outside code. It removes the frameworks and applications that build on other packages: a threat to representativeness |
| 8 | `size` | the wheel has the SHA-256 that PyPI gives, can be read as a zip (member names that decode, no encrypted or unreadable `.py` member), has no member path that is absolute or has `..`, and 800 to 4,000 code lines in its `.py` files outside `*.dist-info`, `*.data` and directories named `tests`, `test`, `testing`, `unittests` | PyCG (Salis et al., ICSE 2021) used projects of fewer than 3,500 lines |
| 9 | `source` | `project_urls` and `home_page` name one GitHub repository (URLs that differ only in the case of the owner or the repository name the same one, as GitHub names ignore case), which has the tag `X`, `vX`, `<name>-X` or `release-X` of the release X (`git ls-remote`) | ours: the release must be cloned from its tag |
| 10 | `history` | at the tag, at least 100 commits and at least 2 distinct commit authors (by author e-mail, without case), from the history of the tag, fetched without blobs | Alfadel et al. (EMSE 2023): at least 100 commits and 2 developers; Kalliamvakou et al. (EMSE 2016): avoid personal projects by the number of committers |
| 11 | `ci` | at the tag, a file below `.github/workflows/` or `.circleci/`, or a file `.travis.yml`, `.gitlab-ci.yml` or `azure-pipelines.yml` at the root (`tox.ini` is not enough) | reaper's CI dimension (Munaiah et al., EMSE 2017); OpenSSF Scorecard, CI-Tests check |
| 12 | `tests` | at the tag, a file `test_*.py` or `*_test.py` anywhere (also in the package) holds a test, by a rule on the text that is the same on every Python version: a `def test...(` on one line, with or without type parameters (`def test_x[T](`), or a `class` line without type parameters whose bases name something that ends in `TestCase` (`class C(unittest.TestCase`), in a file that decodes as UTF-8. The rule reads text, so such a line inside a string, or `TestCase` in a comment of the bases, counts too; type parameters over several lines, and a class with type parameters, do not count: limits of the rule. A test file over 4 MiB is not read and does not count. The ratio of the code lines of those files to the package's code lines is recorded | JARVIS; DynaPyt (Eghbali and Pradel, ESEC/FSE 2022); DyPyBench (Bouzenia et al., FSE 2024) require runnable tests; reaper's unit-test dimension |
| 13 | `released-code` | the `.py` files of the wheel that are missing from the checkout or differ from it hold at most 5% of the wheel's code lines (a version file written at build time passes); the checkout root is searched (`.` or `src`, say), and the differing files are recorded | ours: the tag must be the released code |
| 14 | `github` | the repository has at least 500 stars, is not archived and is not a fork; when PyPI stated no licence, GitHub's detected licence (`license.spdx_id`) is permissive | DyPyBench (500 stars); CodeSearchNet and Alfadel et al. (no forks); last, because of the API limit |

A code line is a line of a token of a statement that is not a string
statement; blank lines and comments are not code. A string statement (a
docstring, say) starts its logical line and has only string literals, not
formatted ones, and parentheses: `"doc"`, `("a" "b")`. A string on the line
of `def f():`, or after a `;`, does not start its logical line, so its lines
are code. (The hand selection counted in the same way, without these
precisions.) The facts of a pass are those that a builder needs:
the release and its upload date, the wheel URL and SHA-256, the repository,
tag and commit, the code lines and top-level import names, the commits and
authors, the CI files, the test files and the test-to-code ratio, the files
that differ from the release, the licence and where it comes from (PyPI's
expression, classifiers or field, or GitHub), and the GitHub facts (stars,
forks, watchers, open issues, archived, fork, created, last push). The
GitHub facts are **as fetched** by the run (the REST API without a token),
not as of D: stars move. The frame records no fetch time.

**Draw.** `draw.py draw --round N` reads the frame and the list, never the
network, and refuses a list whose SHA-256 is not the frame's. It sorts the
passing projects by code lines, ties by name, and cuts them into 5 strata
of equal count; when the count is not a multiple of 5, the first (count
mod 5) strata, those of the smallest projects, have one project more
(CPyGraph's size strata; Nagappan et al., ESEC/FSE 2013, name size as the
main dimension for program analysis). The seed of round N is the first 8
bytes, as a big-endian integer, of SHA-256(the bytes of the list file +
`\n` + `round N`); the order is `random.Random(seed).shuffle()` of the
passing names, sorted by name. The batch is, for each stratum in turn, the
first project of the order that is in the stratum and is neither in the
benchmark (the `projects.toml` of this directory and
of each `--used DIR`), nor in `selection/excluded.txt` (the 2021 benchmark,
the packages of the scalability runs), nor dropped. Names are compared as
PyPI compares them (PEP 503). `--drop NAME=REASON` (repeated) marks a
project that was drawn but dropped at a later stage (the security scan, a
test suite that cannot run in the tracer's environment, the maintainer's
veto, a run of a tool on the project before the draw); the draw takes the
next project of the order in its stratum.
`--skip-stratum N=REASON` (repeated) draws nothing from stratum N and
records it in the log (`skipped`, and `skipped_strata`) with its reason: a
stratum that has no project left, or a stratum that a partial round leaves
out; N is an ASCII number from 1 to 5, given once, and a round skips
not every stratum. Without it, the draw is the same as before (the logs of
rounds 1 to 7 are drawn again byte for byte).

**Batch 8, the rule fixed before its draw** (2026-11-23, the maintainer's
choice "10: 8 + 2 extra"). The frozen frame has too few projects left for
two complete rounds: stratum 2 is exhausted, because its only project left,
asgiref, is touched (django-constance's trace, ground truth and test
environment name it). So: rounds 8 and 9 run the unchanged procedure, with
their own seeds, over strata 1, 3, 4 and 5 (`--skip-stratum 2=...`); then a
third, partial round 10, with its own seed, draws one project each from
strata 1 and 3, by the same rule (`--skip-stratum` 2, 4 and 5). Strata 1
and 3 are the maintainer's choice, fixed before the draw; they were not
strictly the two largest pools, as the rule and round 10's log call them
(a loose reason: the log stays as it is). When the rule was fixed, strata
1, 3, 4 and 5 held 6, 7, 4 and 6 projects not yet used, of them 4 (5 with
vulture), 4, 2 and 4 untouched; before round 10, 4, 5, 2 and 4, of them 3,
2, 0 and 2: stratum 5 ties with stratum 1 or 3 by each count (review
batch8-r1, M4). The seeds depend on the list and the round only, so the
draw of every choice could be computed in advance; the order of the
commits shows that the rule came first, not that the choice was blind.
Batch 8 has 3, 0, 3, 2 and 2 projects in strata 1 to 5. Drops follow the
rule of every round (a project that a corpus, a result, a trace, a ground truth or an environment
names; the maintainer's veto of `sh`), each with its reason in the log.
Each round skips the projects of the earlier ones (`--used` with the
proposal's entries; each log lists them under `used`).

The draw writes `selection/round-<N>.json`: the list and the frame (their
SHA-256), the round, the seed, the constants, the projects already used,
the order, and per stratum its members, its bounds in code lines, the
projects examined in order with the reason of each skip, and the project
selected with its facts from the frame. The frame and the logs have sorted
keys and no time of the run (the dates in them are facts of the list, of
the releases and of the repositories): a rerun from the same cache writes
the same bytes.
`tests/test_draw.py` draws rounds 1 to 10 (batches 3 to 8) again from the committed frame and list, with the seed, the drops
and the skipped strata of each round, reading files only, and checks that each gives the recorded
log. The benchmark directories that the draws used then are gone (one
benchmark now holds every batch), so the test takes the projects already
used from the round log itself.

```sh
python -I evaluation/macro-benchmark/draw.py frame --work ~/draw-work
python -I evaluation/macro-benchmark/draw.py draw --round 1
python -I evaluation/macro-benchmark/draw.py draw --round 1 \
    --drop "name=the test suite does not run in the tracer's environment"
python -I evaluation/macro-benchmark/draw.py check sqlparse==0.6.1 --work ~/draw-work
```

`check NAME[==VERSION]` evaluates every filter on named projects, all of
them even after a failure. With `==VERSION`, a release uploaded after D
fails `release`, and the later filters still evaluate that release. It
writes no frame and no round log, but it fills the cache. Every network
access (PyPI JSON, the wheel, the GitHub API, `git ls-remote`, `git fetch`)
is cached under `--work`: an interrupted `frame` resumes where it stopped, a
rerun reads the cache, and `--offline` fails rather than fetch. A response
or a fetched tag is written under a temporary name and renamed into the
cache once complete, so an interrupted run leaves no partial entry for a
rerun to read. A response that arrives cut is continued with a `Range`
request, and a failed request is tried again a fixed number of times; a
network failure stops the run and is never recorded as a result. The `Range`
request names the first answer's validator in `If-Range`: its strong ETag,
else its Last-Modified (a weak ETag cannot validate a range). An answer that
is not the asked continuation, or an answer 416, starts the body again from
zero; without a validator, so does every attempt. A body is complete when a
read ends without being cut and its length is the total that the server
announced: the Content-Length of the first answer, or the total of a
continuation's Content-Range (a part's own Content-Length counts the part
only). Continuations count against the same `HTTP_REQUESTS_PER_BODY_MAX`
requests, `HTTP_PAUSE_SECONDS` apart; after the last one, the last failure
is raised. When the GitHub API answers that its limit of requests is
reached, the script reads the reset time from the answer, says so, waits,
and goes on; it uses no token. PyPI and GitHub answer with their state of
the day: a release yanked after D changes the answer of a run with an empty
cache.

Nothing of a project is installed, imported or run. The wheel is read as a
zip. The release tag is fetched by its explicit ref (`refs/tags/<tag>`, so a
branch of the same name cannot take its place) into bare repositories, and
peeled to its commit; the frame records both. Its files are read from git's
object store: nothing is checked out, so no hook, filter or line-ending
conversion applies, and git runs without the user's and the system's
configuration and without the caller's `GIT_*` variables (no submodules, no
LFS content). git never asks for credentials (`GIT_TERMINAL_PROMPT=0`): for
a repository that GitHub does not have, `git ls-remote` fails with `not
found` or `could not read Username`, and the script reads both as a missing
repository. The history is fetched without blobs; the tree of the tag is
fetched whole (depth 1), with all its blobs. The files of the tag are the
regular files of its tree (git modes 100644 and 100755): a symbolic link or
a submodule is not a file of the checkout. From that store, the filters read
only the blobs that they need: the test-file candidates and the files whose
path ends in a module path of the wheel. Each one goes to the cache as one
checked record (object, type, size and delimiter, and git's exit status). A
blob over 4 MiB (`MAX_BLOB_BYTES`) is downloaded with the tree but not read:
such a test file does not count for `tests`, and such a module differs for
`released-code`.

`draw.py` reaches the network and runs git on third-party
repositories: run it in the target `maintain` of
`evaluation/container/Dockerfile.inputs` (git, the CA certificates, and uv
for the Python 3.15 that `frame` and `check` need), with the repository
read-only and only `selection/` and the work directory writable.

Only the caller's `http.*` git settings pass to git, as given (a setting
without a value stays without one) and in the order in which git applies
them (the indexed `GIT_CONFIG_KEY_n` first, `GIT_CONFIG_PARAMETERS` last),
so that the last one of a key wins as it does for the caller: a proxy may
need them, as this repository's sandbox needs `http.proxyAuthMethod`.

`frame` and `check` run only on Python 3.15 (`FRAME_PYTHON`), and refuse any
other version; the frame records the version. The code-line count uses the
tokenizer of the running Python, and tokenizers differ between versions on
valid code: a t-string with a comment in a replacement field is one string
token before 3.14 and several tokens, with a comment, from 3.14 on, so the
same file has another count. A file that the tokenizer cannot read counts
its non-blank lines. `draw` reads only the frame and runs on Python 3.12 to
3.15. `draw.py` uses the standard library only.

The literature also suggests filters that the procedure does not use: a
documentation filter (no Python benchmark uses one), strata by PyPI topic,
"Development Status" classifiers, GitHub Release objects (many projects
only tag), age or release-count thresholds, and a filter on recent commits
(it rejects finished, widely used libraries).

## Ground-truth conventions

The names and edge rules are those of
[`evaluation/micro-benchmark/README.md`](../micro-benchmark/README.md). These
are the differences:

- **Scope.** The analysed source is the importable package: the `packages`
  of `projects.toml` (package directories, or module files such as
  `configargparse.py`), without the `exclude` paths. Tests, documentation,
  benchmarks, examples and setup scripts are not analysed. Module names are
  relative to the `root` directory of the project:
  `jmespath.parser.Parser.parse`, `cachetools.keys.hashkey` for
  `src/cachetools/keys.py` (`root = "src"`), and `configargparse.ArgParser`
  for a module file at the root.
- **Nodes.** The keys are the modules of the analysed source and every
  function and lambda defined in them, also the ones that no execution
  calls. Callees outside the package are not keys. A module and a function
  can get the same name; they are then one node (tenacity: the module
  `tenacity/retry.py` and the function `retry` in `tenacity/__init__.py`
  are both `tenacity.retry`). Code that the package generates and runs with
  `exec` is not analysed source: a function that it defines has no node, a
  call in the module code that `exec` runs belongs to the function that
  calls `exec`, and a package function that a generated function calls
  belongs to the package site that calls the generated function
  (micro-benchmark `dynamic/exec_in_function` and
  `dynamic/exec_defines_function`; fastjsonschema: `compile ->
  <builtin>.type` at `__init__.py:294`, and `validate ->
  JsonSchemaValueException.__init__` at `__init__.py:172`, where `validate`
  calls the generated validator; bottle: the templates that
  `SimpleTemplate.execute` runs, `bottle.py:4259`). A library function that
  the library defines with `exec` has no name and no edge (pyrate-limiter:
  `ListProxy.append` and `.extend` of `multiprocessing.managers`,
  `in_memory_bucket.py:75` and `77`).
- **Edges.** An edge `A -> B` exists if the code of `A` can call `B` when `A`
  runs, on any Python version that the release supports
  (`requires-python`). Which calls the code can make is decided by the scope
  rules below. A coroutine function or generator function that the package
  calls is a callee of that call site, whether or not the package awaits or
  iterates the result (the micro-benchmark rule). A call that cannot bind
  its arguments raises `TypeError` before the callee starts: no edge
  (configargparse: `p()` at `configargparse.py:935` on a parser class whose
  `__init__` needs an argument; anytree: `style()` at `render.py:265` on
  `AbstractStyle`). An `if __name__ == "__main__":` block is code of its
  module, which keeps its edges (marshmallow `orderedset.py:84`). An edge
  that depends on what ran earlier in the process counts if some program
  that uses only the public API makes it in a fresh process: sqlparse's
  `_TokenType.__getattr__` creates a token type at its first load and
  caches it (`tokens.py:26`), and `sqlparse.split("select 1")` makes the
  first load of `Comment.Multiline` at `statement_splitter.py:188`. A state
  that only a client's change to package internals makes, such as reloading
  a module or deleting a cached object, is not considered.
- **Callees outside the package.** Builtins, the standard library and
  third-party packages are callees, named by the micro-benchmark rules
  ("Name outside the snippet"). A scorer can restrict the comparison to the
  edges inside the package. A builtin or library callable that library code
  calls back is not an edge (`str` in `json.dumps(data, default=str)`). An
  inherited `__init__`, and an explicit `super().__init__()` that reaches
  code outside the package, are named through the nearest base outside the
  package (`<builtin>.ValueError.__init__`, `abc.ABC.__init__`). A stream
  that `open()` returns, and the default `sys.stdout` and `sys.stderr`, are
  named by their class: `io.TextIOWrapper.write` in text mode
  (configargparse `configargparse.py:1802` and `:2170`). A method of an
  outside object is named by the class of the receiver, also when that class
  inherits it: `collections.defaultdict.items` (marshmallow `schema.py:192`),
  `collections.OrderedDict.get` (cachetools `__init__.py:515`), also when
  both classes are private (argcomplete:
  `argparse._StoreTrueAction.__call__`, `finders.py:290`). A call into a
  third-party module that is not installed is named as a missing module by
  the micro-benchmark rules (markdown2: `wavedrom.render`,
  `markdown2.py:4247`), also when a copy of the library can be read
  (dagster-pipes, bottle, pyrate-limiter). A call of an instance of a stub
  is named by the stub's path, as `validate.py` does (pyrate-limiter: the
  call of a registered redis script, `redis_state.py:86`, is
  `redis.Redis.register_script` and `redis.asyncio.Redis.register_script`).
  The rule fixes names only: a branch that the library's answer decides
  still runs (dagster-pipes: `spark is None` and `except Py4JJavaError`,
  `__init__.py:1457` and `1470`), and a missing library calls nothing back.
  The exception: where a definition of the analysed package is made
  through the library (a base class, a decorator on a package function),
  so that a call of that
  definition goes through library code, that code is read, never run, from
  the release that the project admits, pinned by SHA-256 in the judgements
  file (itables: dash 4.4.1's `_explicitize_args` on the generated
  `ITable.__init__`, `itables_for_dash/__init__.py:56`; Fabric reads Invoke
  bases and the decorators through which its definitions are made). Reading
  another method of the same library, or an ordinary library used by that
  package, does not extend this exception. A documented expression of a missing
  module is named by its access path (dagster-pipes: "A boto3.client("s3")
  object" gives `boto3.client.get_object`, `__init__.py:1199`), but the
  subscript of a missing-module value is not named, so a call on it has no
  callee (`obj["Body"].read()`, `__init__.py:1200`). A method that a private class
  inherits from a public class is named through that public class
  (`collections.abc.Mapping.get` for `os.environ.get`, anytree
  `config.py:6`); a function that a module re-exports without listing it
  in `__all__` is named where it is defined (asciinema:
  `termios.tcsetattr` for `tty.tcsetattr`, `term.py:22`); a builtin type
  without a public path is named as the tracer names it (autojump:
  `builtins.list_iterator.__next__`). One class reached through two
  import paths is one callee when the class is known. This does not resolve
  aliases inside missing libraries: those calls retain their imported paths.
  Where admitted versions give a known concrete receiver two classes,
  the method has both class names. So does a
  callee that is a plain function on one supported version and a wrapper
  object on another (fastjsonschema: `urllib.parse.urlsplit` and
  `functools._lru_cache_wrapper.__call__`, `ref_resolver.py:52` and `64`;
  `urlsplit` has `lru_cache` from Python 3.11). A call of a
  `NamedTuple` class, or of a `collections.namedtuple` class, adds no edge:
  its `__new__` is generated code and its `__init__` is `object.__init__`
  (asyncstdlib `CacheInfo`, `_lrucache.py:341`; anytree `Row`,
  `render.py:287`). This also applies to generated constructors outside
  the package, such as `urllib.parse.SplitResult`.
- **Implicit calls.** An implicit site has only package callees (see "The
  ledger"). Two cases differ from the micro-benchmark. A `raise` of a
  package class without a call adds no edge when the first `__init__` of its
  MRO is outside the package: `raise _FieldInstanceResolutionError` in
  marshmallow (`fields.py:102`), whose first `__init__` is that of
  `TypeError`; the micro-benchmark names that `__init__`
  (`<builtin>.TypeError.__init__`). A `__del__` that runs because a function
  drops the last reference to an object is not an edge (asyncstdlib:
  `zip_longest` can drop the last reference to a `TeePeer`, whose `__del__`
  then runs, `itertools.py:554-566`); the micro-benchmark has a case for it
  (`classes/del_on_last_reference`). A signal handler that the package
  installs is a callee only of the package call where the package waits
  for the signal while the handler is installed (asciinema: the blocking
  `select.select` at `pty.py:99`, which the trace has); `signal.signal`
  only stores it, and a signal that arrives anywhere else is no edge
  (Sublist3r: `killproc`, `subbrute.py`). A method that a decorator of a
  library wraps in generated code is reached as Python runs it: the call
  has the package's wrapper function as its callee, and that function
  calls the method; the generated code has no node (fabric: `@opens` on
  six methods of `Connection`, `connection.py:30`).
- **Judgements.** Calls under `if TYPE_CHECKING:`, in branches on the Python
  version and behind optional imports are judged case by case. The default:
  code under `if TYPE_CHECKING:` does not run; a version branch runs if a
  supported version takes it; both sides of an optional import run. Record
  each judgement, with file and line, in `ground-truth/<name>.md`, and as a
  note at the site. The supported versions are those that the package
  declares: where it declares Python 2, a branch that only Python 2 takes
  runs, and its builtin callees have the Python 3 name of the type
  (pypinyin: `<builtin>.str.encode`, `__init__.py:56`;
  `<builtin>.bytes.decode`, `runner.py:102`). Library behaviour that
  differs between Python 2 and 3 without a branch in the package is named
  for Python 3 (bottle: the methods of a `NamedTemporaryFile`, judgement
  J2). A branch on the version of a
  dependency runs if a version that the package admits takes it (markdown2:
  the pygments branch at `markdown2.py:1915`). Which versions the package
  admits is decided by its own declared requirements, not by those of other
  libraries that a module imports first (itables: the `NotRequired` and
  `Unpack` fallback of `typing.py:26-40` runs in all seven modules that use
  it, also in those that first import dash, streamlit or anywidget). A
  branch on the platform runs
  if a platform that the package supports takes it (netaddr:
  `strategy/ipv4.py:14`). A branch that only an unsupported version takes
  does not run, also when its test is not a version test (netaddr: the
  `except NameError` around `bin()`, `strategy/__init__.py:242`), and a
  `def` in such a branch makes no function, so its body has no edges
  (pypinyin: `compat.callable_check`, `compat.py:26-30`). A function that
  only Python 2 has keeps its Python 2 name (autojump: `itertools.imap`,
  `os.getcwdu`, `<builtin>.dict.iteritems`); a function of a module that
  Python 3 renamed is the same function and has its Python 3 name only
  (Sublist3r: `urllib.parse.urlparse` for `urlparse.urlparse`). This does not
  resolve a module alias hidden inside an ordinary missing dependency.
  A branch for a frozen interpreter runs (Sublist3r:
  `sys.frozen`, `subbrute.py:556`). A branch that a server's answer
  decides runs (asciinema: urllib follows a redirect from http to ftp and
  returns a `urllib.response.addinfourl`, `asciicast/__init__.py:50`).
  Code that runs only after a call that cannot bind its arguments, or
  after an import of a module of the analysed root that the checkout
  lacks, has no edges (face_classification: `grad_cam.py:184`,
  `visualizer.py:131`).

## Scope rules

The audits of batches 1 and 2 established these rules; later audits
clarified them. They apply to all 30 projects. A project judgement records
how its ledger applies the global rules and cannot override them. The
2026-11-15 audit (audit record `2026-11-15/README.md`) applies them to every
project, including the historical ICSE 2021 set.

**A. Edges are per function.** The edges of a function `A` are the calls
that the code of `A` can make when `A` runs. Whether and how `A` itself gets
called does not matter: every function, public or private, tested or not,
reachable from the public API or not, keeps the out-edges of its body. A
trace edge is rejected only when its callee is a value that a client
supplied, when it is an implicit call of code outside the package (see
"Implicit calls" above), when a direct test invocation of a private API
supplies receivers or arguments excluded by B1/B2 and C, when the call
uses a generated namedtuple constructor excluded above, or when the trace
names the callee wrongly: a naming artefact (marshmallow:
`schema_class(...)` at `fields.py:594` makes an instance of a class that
`Schema.from_dict` creates with `type()`, and the tracer names that class
`abc.GeneratedSchema`). Rule A is about whether a function runs: it keeps
the edges of its body even if nothing calls it. It is not about which
values reach its parameters; that is rule B. The private-input rejection
category does not impose public-API reachability: an uncalled private body
still uses the fallback parameter rules stated in B.

**B. The values that can reach a call site when `A` runs limit its edges.**

For a public function or method (rule C), the receiver and the arguments
are what a client or the package can pass. For a private function or
method, which clients do not call, they are what the package's own calls of
it pass: pluggy calls `HookCaller._add_hookimpl` only on callers taken from
the hook relay (`_manager.py:255`), which holds only `HookCaller` objects,
so its `self` is never a `_SubsetHookCaller`. If the package never calls a
private function, its parameters are judged as for a public one, so that
rule A still gives its body edges. What the package's own calls pass counts
in full: tenacity's `wrapped_f` has an `AsyncRetrying` as `self`, because
`AsyncRetrying.wraps` builds it through `super().wraps`.

- **B1. Receivers.** `self` in a method of class `C` is an instance of `C`,
  of a package subclass that inherits the method, or of a subclass that
  calls the method explicitly on itself (`Cache.__setitem__(self, ...)`,
  `super()`), limited to instances that the package or a client can create.
  A client creates instances of public classes; a private class is
  instantiated only where the package does it. A class that cannot be
  instantiated (abstract by `abc`, a `Protocol`) is not a receiver, and
  neither is a class whose own `__init__` always raises: it has no instance
  (python-barcode: `Barcode.__init__` raises `NotImplementedError`,
  `base.py:37-38`). A base class that the package documents for
  subclassing is judged on the class itself: a plain public class is a
  receiver of its own methods; a class that is abstract by `abc` or a
  `Protocol` is not, and the client's
  subclasses are client code (asyncstdlib: `ContextDecorator`,
  `contextlib.py:64`, is abstract by `abc`, so its `_recreate_cm` is no
  callee at `contextlib.py:103`). Where the package makes every instance of
  a private class in one state, a branch that this state never takes adds
  no edge, also in a method of that class that the package never calls
  (argcomplete: the one lexer of its private `shlex` has `debug` 0 and no
  input file, so the debug `print` calls and `sourcehook`'s path calls are
  no edges, `packages/_shlex.py`). A check that cannot fail under the
  package's own values has no callee (python-barcode: the `RuntimeError` at
  `base.py:43`, `114`, `ean.py:120` and `upc.py:108` runs only if a package
  `build` returns a list whose length is not 1, and none does; earlier
  cases: markdown2 judgement J6, Sublist3r `sublist3r.py:899`). B1
  limits which package classes `self` can be; an object that the client
  passes explicitly as `self` to an unbound method of a public class
  (`Cls.method(obj, ...)`) is a client object and opaque (B5), unless it is
  a package instance that fits B1. `__init__` receives the object that is
  being made: its receivers are the instances whose construction reaches
  it, with the arguments that the construction passes. A client that calls
  `__init__` again on a built object is not considered (python-barcode: a
  `PZN7` reaches `Code39.__init__` only from `PZN7.__init__`, with
  `add_checksum=False`, so `PZN7.calculate_checksum` is no callee at
  `codex.py:57`).
- **B2. Arguments and stored values.** The values of a parameter, and of
  what is fed from it, are client objects, the values that the package
  defines for that parameter's role, and the package's defaults. A package
  value is in scope for a role when the parameter's annotation names its
  type or a base class that the package implements for that purpose, when
  the documentation names it for that role (tenacity's API reference: the
  nap functions "can be used as the `sleep` keyword argument"), or when the
  package's own code, tests or documented examples pass it there. A file
  under `examples/` that no document includes is not a documented example.
  An expression in the documentation that passes a package function in a
  role is a documented example, in prose as in a code block (funcy:
  `docs/primitives.rst:19` calls `notnone` "a shortcut for
  `complement(isnone)`", so `isnone` is a callee at `funcs.py:110`).
  A check on another parameter does not decide a role (aiocache: the cache
  class of a configuration, called at `factory.py:34`, is one that the
  tests and documented examples put there, not every class that the
  `issubclass` check of `Cache.__new__` admits). A string of the client
  that selects a method of an outside object that the package made names
  the methods that the package, its tests and its documented examples pass
  (aiocache: the command of `raw`, `memory.py:92`). A client uses the
  public API (constructor arguments, methods): a client's assignment to a
  public attribute of a package object counts only where the package's
  documentation or tests make that assignment (pyrate-limiter: nothing
  assigns `is_async`, so the probe `bucket.leak(0)` at `bucket.py:253`
  reaches only the buckets whose class leaves it `None`; python-barcode:
  a client cannot assign `code` on a built `Code128` merely because the
  attribute is public). This does not make an admitted `str` subclass
  behave like an exact `str`: a first build can reach the `RuntimeError`
  at `codex.py:240` through its overridden indexing, without assigning an
  attribute (see the 2026-11-15 audit). Where the package formats the locals
  of a traceback's frames, the locals of the package's own frames, on a raise
  that the package documents or makes on purpose, are package values;
  client frames stay opaque (structlog: `to_repr`, `tracebacks.py:173`,
  calls the `__repr__` of six package classes).
  When a parameter has an annotation, the annotation decides which package
  values fit (`our_role: Type[Sentinel]` admits any sentinel class). An
  `isinstance` check that admits a package class for a parameter or a
  stored value names that class for the role, as an annotation does
  (anytree: the `NodeMixin.parent` setter admits a `LightNodeMixin` node,
  `nodemixin.py:122`, and so does the `children` setter for each child,
  `nodemixin.py:230`). An abstract type from outside the package in an
  annotation (`AsyncIterator`, `AbstractSet`, a `Protocol`) names a package
  class only if the class subclasses it or is registered with it, not if
  the class only has its methods, and only for a role for which the package
  implements that type: asyncstdlib's iterators fit its iterable
  parameters, which its documentation makes one role
  (`docs/source/notes/iter_scope.rst:17`); marshmallow's `OrderedSet` is a
  set for `only` and `exclude`, but not for the `AbstractSet` arm of
  `partial` or `schemes` (`types.py:15`), where nothing passes one. A
  `Protocol` of the package names the classes that the package documents
  as its implementations (structlog: `ExceptionTransformer` names
  `ExceptionDictTransformer`, `processors.py:675`). A value
  that a test passes only to check that the package refuses it is out of
  scope when the annotation excludes it (marshmallow: a field class as
  `nested`, refused at `fields.py:587`). When the documented type and the
  annotation of a parameter differ, the annotation decides; the
  documentation adds package values only by naming them for the role or
  through documented examples that pass them. In a
  union of a package base class and a bare `Callable`, only the base-class
  arm names package values. A stub or annotation that types a parameter as
  a bare callable is not evidence for any package value. An annotation that
  admits any module or any class (`ModuleType`, `type`, `object`) names no
  package value, as a bare callable does, and neither does `Any`. A value from
  outside the package that the client passes is a client callback, whatever
  the documentation shows (`dict_cls=collections.OrderedDict`,
  `setwriter(print)`).
- **B3. Not considered:** an arbitrary package object passed where any
  object or any callable is accepted, and a value that the package never
  produces for that role (a hand-built syntax tree with a node type that the
  parser never makes; a strategy as the function to retry). A node that the
  parser makes under one of its options is a node that the parser makes
  (pyflakes: `ast.parse(..., type_comments=True)` gives `TypeIgnore` nodes,
  which have no handler, so `handler(node)` calls
  `Checker._unknown_handler`, `checker.py:1252`). Where an
  annotation exists, it decides (B2), not what the package produces. An
  attribute name that the client supplies is not taken to name a package
  property (anytree: `getattr(node, name)` at `render.py:344`,
  `resolver.py:349` and `search.py:234` runs no property), unless the tests
  or the documented examples use the name (aiocache: `conn.serializer`
  through `_Conn.__getattr__`, `base.py:543`, which the trace has). An object that
  the package leaves behind after it raised an error to refuse it is not
  considered (configargparse: `add_argument` raises at
  `configargparse.py:2318-2336`, after the action is already in the
  parser). This holds for any exception that leaves an object half-changed,
  a failed lookup too: the object is not used again. This excludes a retry
  after python-barcode's `KeyError` at `codex.py:211`, but not a first-build
  witness with an admitted client subclass whose length results vary: that
  witness reaches `_new_charset`'s `ValueError` at `codex.py:169` (see the
  2026-11-15 audit).
- **B4. Concrete outside types.** When a parameter's annotation or
  documentation fixes a concrete type from outside the package (`dict`,
  `list`, `str`, `bytes`, `logging.Logger`, `threading.Event`; a
  `TypedDict` counts as `dict`), a method call on it is an edge to that
  type's method. A value whose class the package checks with `isinstance`
  before the call has that concrete type. When an annotation and the
  documentation both exist and differ, the annotation decides (as in B2).
  An annotation of `Any` states no type (PEP 484 gives an unannotated
  parameter the type `Any`; `object`, by contrast, states that every object
  is accepted): a parameter or alias annotated `Any` is judged as one
  without an annotation, so its documentation can fix a concrete outside
  type (itables: the alias `DataFrameOrSeries`, `typing.py:54-57`;
  dagster-pipes: "An azure.storage.blob.BlobServiceClient object",
  `__init__.py:1341`). A documented class that has no public path cannot
  be named: the site keeps a note and no callee.
  An abstract type (`Mapping`,
  `Iterable`, `Callable`, a `Protocol`, "any context manager") does not fix
  the class. But where the documentation names a concrete type for a client
  value, the value is named by that type, although the code tests an
  abstract class (funcy: "set" in `docs/extended_fns.rst` gives
  `<builtin>.set.__contains__`, although `make_func` tests
  `collections.abc.Set`, `funcmakers.py:22`). Documentation is read one
  entry at a time: a type list in one function's entry names client
  collections for that function only (funcy: the types of the `merge` and
  `walk_keys` entries do not name the collections of `empty` or
  `update_in`). A `type[T]` of a concrete outside type `T` fixes `T`
  (structlog: `type[Context]`, which is `type[dict]`, `_config.py:355`).
  The `.pyi` stubs that a package ships next to its modules count as
  annotations (pypinyin). An annotation names the methods of a
  value; it does not remove a branch that the code takes on purpose for
  another client value (markdown2: `str(text, 'utf-8')` in `convert`,
  `markdown2.py:457`, although `text` is annotated `str`).
- **B5. Client objects are opaque.** A method call on a client-supplied
  object, or on one of its attributes, has no outside callee, and what the
  object calls when the package uses it is client behaviour. This holds also
  for a library object that the client built around a package object
  (`itertools.chain(event.headers, ...)`), and for an object that a client
  callback returns (asyncstdlib: `self.gen`, the generator that the
  client's function returns, `contextlib.py:113`). The callback rule (a
  package function that library code calls back is a callee of the package
  site that made the library call) applies to library objects that the
  package creates or passes. Where library code iterates a lazy `map` or
  `filter`, or the output of an application, the package site that hands it
  to the library is the caller (bottle: wsgiref iterates and closes the
  application's output under `WSGIRefServer.run` and `CGIServer.run`,
  `bottle.py:3532` and `3495`). In general, when a package call hands an
  object to library code, or starts library code that dispatches to an
  object which the package's documented setup registers, and the library
  then calls a package function, the package function that makes the
  library call is the caller (structlog: logging calls back
  `ProcessorFormatter.format` on a handler of the documented setup,
  `_base.py:224`; pyrate-limiter: logging formats the record of
  `logger.info("... %s", rates)` and calls `Rate.__repr__`,
  `limiter.py:182`; whitenoise: Django's `FileResponse.__init__` calls back
  `set_headers`, `middleware.py:129`). An exception that escapes a client
  callback is a client value (bottle: `_raise`, `bottle.py:119`). The result
  of a client callback stays a client object even where an `isinstance`
  against an outside abstract type would admit a package class (bottle:
  `isinstance(result, (dict, DictMixin))` in the view wrapper,
  `bottle.py:4522`). A server or framework that calls the package is a
  client: a callable that it passes is a client callback, and an object
  whose type its documented API fixes is named by that type, as in B4
  (whitenoise, after bottle: Django's `get_response` has no callee,
  `middleware.py:123`; `request.META` is a dict; the parser of
  `add_arguments` is Django's `CommandParser`). When library code picks an
  object from the client's configuration, the library's defaults and the
  configurations that the package documents are in scope; any other
  configured class is client code (whitenoise: Django's default finders
  and their `FileSystemStorage`, `middleware.py:139` and `150`; the
  package's two documented storage classes and Django's default
  `StaticFilesStorage`, `middleware.py:197`). A value that the interpreter
  builds for the call of the package function itself (`**kwargs`, `*args`)
  is a package value.

**C. "Public" is judged on the access path.** A class or function is public
if a client can reach it through a path with no component that starts with
an underscore; dunder names such as `__init__` and `__call__` do not count
as underscore components. `pluggy.PluginManager` is public, although
`pluggy._manager` defines it. A class or function on a public path is
still private if its docstring or the documentation marks it private
(`:meta private:`, as on `pluggy.HookCaller.__init__`).


### Clarifications from the full audit (2026-11-15)

These interpretations apply to every project; the
decision record (audit record `2026-11-15/scope-adjudications.json`) gives evidence.

- **Factory outputs (B2).** When documentation names a package factory's
  output for an input role, the output is admitted with the factory's
  public arguments. An example does not restrict those arguments to its
  one value. The output must be constructible through that public API;
  this does not admit hidden closures or arbitrary package callables.
  If the factory returns its argument unchanged, that value still counts
  only when it is admitted for the factory input and the consumer admits
  that factory output (funcy: one-argument `compose`).
- **Input and stored-value annotations (B2).** A field annotation does
  not replace the public parameter's contract when source or tests
  explicitly establish another admitted value for that input
  (structlog: `CapturingLogger` passed to the inherited bound-logger
  constructor, whose `logger` parameter is `WrappedLogger`, an `Any` alias).
- **Forwarded attribute names (B3).** A tested or documented name on an
  admitted receiver remains admitted when a package proxy forwards that
  same name to that receiver. The proxy must construct or hold the receiver
  under B2, and normal lookup must reach the forwarding code. This does not
  admit all property names or arbitrary client callback results
  (structlog: six stdlib bound-logger properties through its lazy proxy).
- **Outside names.** A Python function wrapper installed at a public
  outside attribute keeps that attribute path. A callable wrapper object
  uses its concrete class's `__call__`. A direct alias of a class is a
  class path; a factory returning a different subclass is not that
  subclass's name (`Path` produces `PosixPath` or `WindowsPath`).
- **Concrete types (B4).** A concrete annotation does not admit arbitrary
  out-of-contract types. Explicit handling of another type still counts.
  A builtin call that enters its body counts even if that body raises;
  argument binding failure before entry gives no edge.
- **Client control flow (B5).** Client methods and callback results stay
  opaque, but their effects on control flow count. An admitted subclass
  can override operations; repeated truth or length checks need not agree.
  A witness must use the public API without modifying package internals
  or reusing an object left half-changed by a failure.
- **Versions and configuration.** Use CPython and alternative interpreter
  implementations that the release explicitly supports. A Python-version
  declaration alone does not admit another implementation. Apply the same
  declared version bounds and explicit support drops to each implementation.
  Include names across the release's admitted Python 3 versions. The final classifier is not an upper bound;
  an explicit support drop overrides a stale classifier. Retain an older
  fallback name where that runtime lacks the later public path. Do not
  add two aliases for one class on the same runtime. Documented interpreter
  or library configuration counts when it changes a package-owned default
  or value (`-u` changes the binary standard streams; hashlib's documented
  fallback changes the concrete SHA-1 receiver). This includes ordinary
  zip imports supported by `importlib.resources` for a package's own
  resources (netaddr). The configuration need not be repeated in each
  package's documentation. Client-injected loaders and streams stay opaque.
  This audit includes normal and optimized execution (`-O`, `-OO`) as a
  working assumption. Keep the union of their edges: assertions and `__debug__`-dependent code can be
  absent under `-O`, and docstrings under `-OO`. These modes do not relax
  the input-role, client-opacity or failed-object rules above.
- **Missing libraries.** Reading a library does not make ordinary calls
  transparent. The base/decorator exception applies where the package
  definition actually goes through library code. A decorator that only
  registers a function does not make later framework dispatch transparent.
  Subscript, unpacked and arithmetic results have no inferred stub path;
  direct attribute/call chains retain their imported access path.

The earlier batch-5 rulings that excluded both Code128 error edges are
superseded by the first-build subclass witnesses in this audit. The rules
against arbitrary attribute assignment and failed-object reuse still
apply. Earlier batch tables and audit narratives retain their dated counts.

### Rulings for batch 6 (from 2026-11-22)

These rulings were made on the ground truths of batch 6; batches 7 and 8
follow them. A ruling that
decides many edges is not made by the lead alone: an independent referee
(a model of another provider, given this README and the package's files,
and told not to consider what any analysis tool reports) gives the ruling,
and the lead adopts it unless it contradicts an earlier ruling. Each
ruling records who gave it. A file named for a ruling
(`ruling-<name>.md`, `b7-ruling-<name>.md`) is an audit record.

- **Declared iterable types (B2; more-itertools; the referee, adopted by
  the lead).** For annotation matching, an explicit base declared in a
  `.pyi` file shipped beside a package module counts as a declared base of
  the corresponding package class; run-time method lookup still follows
  the Python implementation. A method match or an ABC `__subclasshook__`
  result alone does not satisfy this annotation rule. In more-itertools
  11.2.1, the documentation and composition examples establish one
  ordinary source-iterable role (`README.rst:8`; `docs/api.rst:270`;
  `more.py:5499`), so its eight stub-declared iterators (`peekable`,
  `seekable`, `islice_extended`, `sized_iterator`, `time_limited`,
  `callback_iter`, `countable` and `serialize`) and its two sequences
  (`numeric_range` and `SequenceView`) fit generic iterable inputs.
  Narrower contracts keep a separate requirement of purpose (the
  referee's second ruling, after the blind audit): specialising the item
  type of an outside `Iterable` annotation does not by itself admit every
  member of the ordinary source-iterable role. For the numeric and index
  inputs (`sizes`, `key_list`, weights, counts, indices, an iterable
  shape and the data of the `running_*` functions), compatible
  `numeric_range` instances are admitted: the class is documented as a
  producer of numeric ranges (`more.py:2266`). `SequenceView` and the
  nine iterator members are not admitted there merely because they can
  carry numbers. Sequence-only inputs keep compatible `numeric_range` and
  `SequenceView` instances; matrices keep `SequenceView`. No member is
  admitted in general as the outer iterable of iterables, tuples or
  mappings without evidence for that input, but the package's own
  forwarding counts: `matmul` passes its admitted `SequenceView` matrix
  to `transpose` (`recipes.py:1051`), so `transpose` keeps it, and that
  passage admits the class at no other outer input. Inner ordinary
  iterables keep the eleven members. Run-time and stub-declared bases are
  treated alike throughout. The private
  `_concurrent_tee` instances that the public `concurrent_tee` returns
  also fit this role: its documentation names those outputs as inputs to
  `serialize` (`more.py:5535`), and the factory-output clarification
  applies; a `_concurrent_tee` built in another way is not considered.
  `bucket` itself is not admitted through `__iter__` alone: its declared
  base is `Container`, and the tested passage to `take`
  (`tests/test_more.py:1084`) supplies a child iterator. Admission
  determines possible values; each site keeps only the calls that Python
  makes on those values (a length check reaches `numeric_range.__len__`,
  `SequenceView.__len__` or `sized_iterator.__len__`; a truth test reaches
  `numeric_range.__bool__`, `peekable.__bool__`, `seekable.__bool__`, or
  the length of `SequenceView` and `sized_iterator`).
- **An environment variable that sets a package-owned value (tinytag; the
  writer and the blind auditor agree, adopted by the lead).** An
  environment variable that the package reads to set a value of its own
  counts as configuration when the package's documentation or its own
  test setup sets it. tinytag reads `TINYTAG_DEBUG` at import; its README
  does not document it, and upstream's test job sets it and requires full
  coverage under it (`.github/workflows/tests.yml:58`, `:131`). So the ten
  edges of its debug branches stay (eight to `<builtin>.print`, and
  `_ID3._parse_frame` to `io.BufferedReader.tell` and `io.BytesIO.tell`).
  This is not the argcomplete case, where the package fixes its own state.
- **The blind audits of batch 6** draw their sample with
  `random.Random(20261122)`: 70 sites and every value site; where one kind
  of site dominates, the draw is split by kind (tinytag: 735 of 780 sites
  are explicit, so 50 explicit and 20 implicit sites).
- **Two limits of the site finder that a writer settles by hand
  (validators; the blind auditor, adopted by the lead).** The finder
  offers every operand of `and` and `or` as a truth site, also the last
  one, which Python does not test there, and it makes no site for a
  parenthesised group: the edge of a truth test is written at the site of
  the operand whose value is tested (`url.py:252:16`). A comparison whose
  method `functools.total_ordering` generates gets no candidate: its
  callees are added by hand (`between.py:74`).
- **A package value inside a client container (B2; json-repair; the blind
  auditor, adopted by the lead).** A package value that the package's own
  tests pass inside a client container to a public parameter is an
  admitted value there (the test clause of B2), and each site keeps the
  calls that Python makes on it. json-repair's tests pass
  `{"a": MISSING_VALUE}` to `SchemaRepairer.repair_value`
  (`tests/test_schema_repairer.py:479`), so `copy.deepcopy` calls
  `MissingValueType.__deepcopy__` back at `schema_repair.py:315` and
  `:337` (2 edges). This is not the h11 case (B5), where no test or
  document puts a package value into the client's iterable.
- **Admitted values of several parameters combine (B2; django-environ;
  the writer and the blind auditor agree, adopted by the lead).** B2
  counts admitted values per parameter, and a path needs only a witness
  through the public interface: the admitted values of the parameters of
  one public call combine freely. In django-environ a `Path` or a
  `NoValue` default with `cast=str` and `parse_default=True` reaches
  `cast(value)` in `Env.parse_value` (`environ.py:613`): edges to
  `Path.__str__` and `NoValue.__repr__`. A client's own value stays a
  client value: a bytes default adds no `bytes` method there.
- **Binding for a callable written in C (tabulate; the blind auditor,
  adopted by the lead against the writer's reading; 1 edge).** "Argument
  binding failure before entry gives no edge" means, for every callable,
  the matching of the arguments to the parameters of its signature
  (number and names, as `inspect.Signature.bind` checks). A type that a C
  callable then refuses is a failure in its body: the edge exists
  (`val.replace(raw_val, formatted_val)` with a bytes cell,
  `tabulate/__init__.py:1376`: `<builtin>.bytes.replace`). A call with the
  wrong number of arguments has no edge (`NoneType(cell)`). Where CPython's
  argument parser checks a type differs between methods and versions, so
  it does not decide an edge.
- **An inherited `__init__` (tabulate; the blind auditor).** A class whose
  first `__init__` in the MRO is `object.__init__` has no constructor
  edge, also when a builtin base is not `object`: `str` defines no
  `__init__`, so `JupyterHTMLStr(output)` has no callee (`dict` defines
  one; the dagster-pipes precedent).
- **jsonpickle (the blind auditor's opinions, adopted by the lead).**
  (a) A role that the documentation gives a base class
  (`jsonpickle.handlers.BaseHandler`) admits the package's subclasses of
  it, as an annotated base class does (B2 with B4): 11 edges. (b) "The
  package" in B3 includes earlier releases whose output this release
  documents that it decodes (the `'c'` arrays of Python 2: 1 edge).
  (c) Calls on the `__dict__` or the class of a client object are opaque
  (B5, "or on one of its attributes"; cachetools C2): 2 edges go; a call
  on the `__dict__` or the class of a library object that the package
  itself reaches stays. (d) A module that the package's tests load as a
  backend by name (`os.path`, `jsonpickle_test.py:986`) is an admitted
  value of that role (the aiocache clause on strings that select
  functions): 2 edges. (e) A module that only a docstring names and that
  neither the package nor its tests pass (`bz2`) is a client value: 4
  edges go.
- **The blind draw where a kind has fewer than 20 sites** takes all of
  them and fills the 70 from the other kind (jsonpickle: 19 implicit, 51
  explicit).
- **Package Protocols and parameter roles (B2; prometheus-client; the
  referee, adopted by the lead).** A package Protocol admits its declared
  package implementations and the classes that the package documents as
  implementations; a class docstring counts as documentation. A default,
  an example or a passage of another package class admits it at that
  parameter and along the package's forwarding calls. That use alone does
  not make the class an implementation at every parameter annotated with
  the Protocol; broader admission needs documentation that joins the
  roles. So `MultiProcessCollector` is a documented Collector
  implementation; `CollectorRegistry` is admitted at the exporter inputs
  that default to it, name it or receive it; and `RestrictedRegistry`
  reaches both text encoders, but neither `GraphiteBridge` nor the role
  of a registered collector. The ruling
  (`ruling-prometheus-client.md`) lists the admitted classes for each
  parameter.
- **Package-started servers (A, B2, B5; prometheus-client; the referee,
  adopted by the lead).** The server-as-client rule applies when the
  client supplies the server or the framework that runs the package.
  When package code selects and starts library server code and gives it
  the package's application, the values that this library code makes and
  passes to the application keep their library provenance, and an
  explicit package call of such a value has its normal outside callee.
  So `start_wsgi_server` makes wsgiref's `start_response` a callee of
  `make_wsgi_app.prometheus_app`
  (`wsgiref.handlers.BaseHandler.start_response`); a callback that an
  external server supplies stays a client callback.
- **An annotation that is wider than the documentation (B4;
  prometheus-client; the referee).** B4 already decides: the annotation
  has precedence where the two differ. `Enum`'s `states` is
  `Sequence[str]`; the documentation's `List[str]` and the tests' lists
  add no `list.index` edge.
- **Environment data read through libraries (path; the referee, adopted
  by the lead).** An environment variable that a library reads, where the
  package calls that library, counts as configuration when the library
  documents it, or the package's documentation or tests set it, and its
  result supplies a package-owned value. The text values that the library
  processes are considered, not only the literal values of the tests or
  of the trace's environment. This covers `HOME` through
  `os.path.expanduser`, and `XDG_CONFIG_HOME` and `XDG_CONFIG_DIRS`
  through appdirs (`tests/test_path.py:1264`, `1270`, `1290`). It admits
  no module, class or callable that a client injects, and no change of
  package internals. So the 60 edges of `path` that rest on `TempDir`
  as the value of `_next_class` stay.
- **Library behaviour on supported platforms (path; the referee, adopted
  by the lead).** The supported-platform rule applies to the package's
  branches and also to library behaviour reached through the package's
  admitted library values: a call back into the package that happens on
  any supported platform and admitted Python version is an edge, by the
  library call-back rule (B5). A trace recorded on one platform does not
  limit this union. The usual imported names are kept (`os.path.*` also
  on Windows), and a module that a client supplies stays a client object
  (`Path.module` is `os.path`; the nine traced `ntpath.*` edges of the
  tests' injected module stay rejected). `path` declares
  `OS Independent` and tests on Windows, so the 38 call-backs that
  `ntpath` and `pathlib` make into `Path.replace` and `Path.__radd__`
  stay.
- **A shared alias of a bare callable (B2; path; the referee).** An alias
  of `Callable[...]` is not a package class or Protocol: a value that the
  documentation passes at one parameter annotated with it
  (`only_newer(...)` at `merge_tree`) is not admitted at the others
  (`copytree`, `move`): 2 edges go.
- **django-constance (the referee, adopted by the lead;
  `ruling-django-constance.md` lists every site).**
  (a) *Configured implementations (B2, B5).* When package or library code
  resolves a class, callable or module that a supported setting names,
  the configuration-selection rule applies whichever code resolves the
  name: the defaults of the package and of the library, and the admitted
  documented configurations, count. This differs from an outside callable
  or object that a client passes directly (B2). A configured
  implementation that the client defines stays client code.
  (b) *Test configurations (B2, B5).* The package's own tests count as
  evidence for a configuration that selects a concrete library
  implementation by name, as for jsonpickle's tested backend and
  tinytag's test environment. This includes a test's replacement setting
  when the same configuration can be given through the supported
  interface. It admits no implementation that a test defines, no mock, no
  arbitrary client callback and no state that needs a change of package
  internals. (The tests' `EmailField`, `TypedMultipleChoiceField`,
  `CheckboxSelectMultiple` and `CharField` as an additional field: 10
  edges; the tests' SQLite connection in migration 0002, with both cursor
  wrappers: 6 edges.)
  (c) *Configured missing factories.* An admitted configuration that
  names a factory in a missing module uses the missing-module convention
  for the factory and for the value it returns:
  `django_redis.get_redis_connection.get`, `.mget`, `.set` (5 edges),
  beside `redis.Redis.*` where another admitted branch makes that
  receiver.
  (d) *Attribute hooks and private names (B2, B3, C).* The public path of
  a special method does not make a private attribute a name that a client
  selects: a direct call of an attribute hook does not admit a
  private-name branch that ordinary attribute operations never reach
  (`Config.__getattr__` and `__setattr__` with `_backend`: 4 edges go).
  This restricts attribute access only; it is no protocol-only rule for
  every public special method.
  (e) *Package-produced stored proxies.* A value that package code reads
  and later restores through its public helper stays admitted when an
  admitted backend stores it unchanged: under a running event loop,
  `override_config` can restore an `AsyncValueProxy` into the memory
  backend, and the calls that then recurse through the proxy count before
  the `RecursionError` (3 and 36 edges stay). A later call whose
  preceding step must raise is not reached.
  (f) *Dependency support without a declared requirement.* When a release
  has no declared dependency requirement for a library, its explicit support
  declarations (classifiers, versioned test environments) give the
  admitted versions: Django 4.2, 5.0, 5.1, 5.2, 6.0 and 6.1.
- **After Codex audit round 1 (the referee, adopted by the lead;
  `ruling-round1-disputes.md` lists every pair).**
  (a) *Body edges of a method that the package never calls (A, B1;
  json-repair).* Rule A separates a function's outgoing edges from
  whether anything calls it, and B1 admits the instances that the package
  creates: such an instance need not escape to the client before its
  methods get their body edges. `StringFileWrapper.__setitem__` calls
  `io.TextIOWrapper.tell`, `.seek` and `.write` on the stream that the
  package opens (3 edges).
  (b) *Unannotated inputs and concrete outside types (B4, B5;
  django-environ, prometheus-client).* That an argument binds does not by
  itself admit a concrete outside type. At an unannotated parameter the
  entry's documented contract, explicit type handling in the code and
  admitted package flows decide the concrete outside receivers; a
  general-purpose library operation that keeps or derives the input's
  path or string representation does not widen that contract. So a bytes
  path at `environ.Path` or at `MultiProcessCollector.merge` adds no
  `bytes` method (4 proposed edges rejected). tabulate differs: its
  documentation shows bytes cells and its code handles bytes. Once a
  concrete receiver is admitted, a method call whose arguments bind
  counts also when the method refuses their types in its body.
  (c) *Random outcomes and file-system histories (path).* "Some program in
  a fresh process" sets no threshold of probability and no restriction to
  an empty file system or to one thread: a call that happens for a
  possible outcome of a library's random-name generator and a possible
  state of the file system is an edge. The 18 callers that reach
  `TempDir.__new__` with a value that usually makes `tempfile.mkdtemp`
  fail also reach `TempDir.__init__` (18 edges).
  (d) *State changed through a public method (B2; jsonpickle).* Calling a
  public method that changes state is not a change of package internals:
  a default handler removed with the public `unregister` (documented;
  the package's tests do it) is an admitted state, and the values that
  the remaining handlers forward then reach the generic pickling path
  (12 edges).
  (e) *One name per admitted concrete receiver class (jsonpickle).* The
  rule "an outside method is named by the class of the receiver, also
  when that class inherits it" has no exception for a large receiver
  set, and B4 does not replace known concrete receivers by their defining
  base. The numpy scalar classes and the `numpy.dtypes` classes that can
  arrive at a site are named one by one (the ruling gives the sets);
  `numpy.generic.tolist` and `numpy.generic.item` go, because `generic`
  has no instances; `numpy.dtype.newbyteorder` stays as the name of the
  older admitted numpy releases.
- **Open receiver sets of a generic serialisation path (jsonpickle; the
  lead, 2026-11-22, after Codex audit round 2; reported to the
  maintainer).** jsonpickle calls protocol methods (`__reduce__`,
  `__reduce_ex__`, `__getnewargs__`, `__setstate__`, `cls.__new__`, the
  class call, a reducer's reconstructor) on whatever object it flattens
  or restores, and its numpy and pandas handlers call `tolist`, `item`
  and `newbyteorder` on whatever scalar, dtype or index arrives. Under
  rulings (d) and (e) above, the callees at these sites are one name per
  concrete library class that a handler can forward, also through
  reducer states and instance dictionaries. That set is open-ended in
  practice: it grows with every admitted release of numpy and pandas,
  with reducers that Cython generates at build time, and with native
  types. Round 1 added about 225 such names; round 2 reported 152 more
  and named three further sources that it could not read. So: (1) the
  ledger records every such pair that a writer or an auditor verified in
  a source: the graph at these sites is a LOWER BOUND, and the package's
  notes say so; (2) the stop rule of the audit rounds counts the
  findings outside these sites; findings at these sites are applied when
  verified and start no further round; (3) the edges outside the
  packages of batch 6 are read for all ten packages and for the nine
  without jsonpickle, both from the per-package table (the edges inside
  the packages, the headline, do not depend on any of this: jsonpickle's
  383 inside edges did not change in either round).
  The sites are listed in `ground-truth/jsonpickle.md` under "Open
  receiver sets".
- **Implementation, version and platform combinations (path; the referee,
  adopted by the lead).** Once a release explicitly supports an
  interpreter implementation, the release's declared Python-version
  bounds and its supported platforms apply to that implementation, unless
  the release states a restriction or a support drop for it. A CI job is
  evidence of support; the version and the platform that it selects do
  not by themselves exclude other combinations. Only combinations on
  which the implementation exists are considered, with that runtime's
  real library behaviour. So `path` admits PyPy 3.11 on Windows: its
  PyPy 3.10 job on Linux admits PyPy, its bound is `>=3.9`, and its
  platforms include Windows. PyPy's `nt` module has no `_path_normpath`,
  so `ntpath.normpath` runs in Python there: 5 call-backs into `Path`
  (`absolute`, `normpath`, `realpath` to `Path.__add__`; `copymode`,
  `copystat` to `Path.replace`). Runtime admission does not relax the
  rules on inputs, configuration and client values.

### Rulings for batch 7 (from 2026-11-23)

Batch 7's ground truths follow every rule above, "Rulings for batch 6"
included. Its blind audits draw their samples with
`random.Random(20261123)`: 70 sites, or 140 for a package whose trace is
partial or absent (pymysql, pgvector, mss, pyfiglet), and every value
site. The rulings that batch 7 added, each by a referee (Codex) where the
rules above did not decide, and adopted by the lead:

- **What makes a platform supported (pyfiglet; the referee,
  `b7-ruling-pyfiglet.md`).** Supported platforms are those the release
  declares through classifiers or documentation, or establishes through
  its own platform test jobs, subject to explicit restrictions and
  support drops. A platform branch in the code, or a platform-neutral
  wheel tag, does not by itself admit another platform. pyfiglet 1.0.4
  declares only `Operating System :: Unix`, and its sdist has no test job
  and no statement about Windows, so its `win32` branch
  (`__init__.py:61-62`) does not run and no `WindowsPath` or Windows
  console receiver is named (ten outside edges went; no edge inside the
  package depends on it).
- **A release that is silent about platforms (textdistance; the referee,
  `b7-ruling-textdistance.md`).** When platform classifiers and
  documentation are silent, the release's platform test jobs establish
  support; neither silence nor a platform-neutral wheel admits additional
  platforms. The CI-combination rule ("Implementation, version and
  platform combinations") permits untested combinations of independently
  admitted implementations, versions and platforms, but does not
  establish support for an otherwise unadmitted platform. textdistance
  4.6.3 has no OS classifier and no platform statement, and all its test
  jobs run on `ubuntu-latest`: Linux is its platform, and the two
  `pathlib.WindowsPath.open` edges went (`libraries.py:30`,
  `benchmark.py:117`). The referee's caution: a platform ruling can
  change edges inside a package (path's call-backs did); here it does
  not.
- **The access paths of forwarded stub values (pgvector; the referee,
  `b7-ruling-pgvector.md`).** Preserve each missing-module access path
  carried by an admitted package argument flow, alongside
  annotation-derived paths where rule B independently admits them. An
  annotation constrains admitted types; it does not rename an admitted
  stub value when package code forwards it. Whether the passing caller is
  public or private does not change this. pgvector's psycopg register
  functions are annotated with `BaseConnection` and `TypeInfo`, and the
  package's own callers pass `psycopg.Connection` and
  `psycopg.AsyncConnection` contexts and results of `TypeInfo.fetch(...)`:
  18 outside edges were added
  (`psycopg.{Connection,AsyncConnection}.adapters.register_*`,
  `psycopg.types.TypeInfo.fetch.register`).
- **A library call-back needs an admitted input (pgvector; the same
  ruling).** The base-class exception exposes call-backs made by the
  reached library implementation, including implicit calls on admitted
  arguments, but does not widen the definition's input roles. A package
  value established for rendering is not thereby admitted for cleaning
  through otherwise opaque client-framework dispatch: a disabled Django
  form field would clean a `SparseVector` initial value
  (`django/forms/fields.py`, `_clean_bound_field`), but no rule admits
  that value at `SparseVectorFormField.to_python`'s parameter, so there
  is no edge to `SparseVector.__eq__` or `__repr__` at
  `django/sparsevec.py:61`.
- **A release's own changelog as a support statement (pgvector).** An
  explicit support statement in the release's changelog counts as a
  declaration under django-constance (f): "Fixed error with Bit
  constructor for NumPy 1.24-1.26" admits numpy 1.x names beside the
  dispatcher name. A parameterized generic used as a class base keeps its
  origin's stub path for inheritance (`UserDefinedType[Any]`).
- **A declared platform family (websocket-client; the referee,
  `b7-ruling-websocket-client.md`).** A declared platform family admits
  its members on which an admitted interpreter and Python version exist,
  subject to the release's explicit restrictions; neither a narrower CI
  matrix nor the interpreter's support-tier list narrows that
  declaration. Use each admitted combination's actual library behaviour,
  including capability probes. websocket-client declares
  `Operating System :: POSIX`, macOS and Windows, so
  `selectors.DefaultSelector` is one of `KqueueSelector`,
  `EpollSelector`, `DevpollSelector` (Solaris), `PollSelector` (a POSIX
  system without the others, such as AIX) and `SelectSelector`
  (`Lib/selectors.py` takes the first that works): 24 outside edges
  were added for the two that the writer had left out.
- **A package callable handed to client code (websocket-client; the same
  ruling).** When the package hands a package callable to client code
  through a supported callback interface, judge its parameters as public
  inputs under B2 to B4; its captured values remain constrained by
  package flows and admitted public state. The client's invocation
  creates no callback edge at the handoff site under B5. The closure
  `closed` of `run_forever`, which a custom dispatcher gets, takes any
  `ABNF` that its annotation admits: a frame that is not a close frame
  reaches `handleDisconnect` and an f-string formats it (one inside
  edge, `handleDisconnect -> ABNF.__str__`, `_app.py:583`, `591`).
- **An abstract stream annotation against documented stream classes
  (segno; the referee, `b7-ruling-segno.md`).** A shipped stub's abstract
  stream annotation takes precedence over concrete stream classes named
  in narrower per-format documentation; those client streams remain
  opaque under B5. Concrete streams supplied by the package retain their
  method edges at the sites they can reach. segno's stub annotates
  `out: IO[AnyStr] | str`, and the docstring of `QRCode.save` names
  `io.BytesIO` or `io.StringIO` per format: twelve outside edges to
  `io.StringIO.write`, `io.BytesIO.write` and `io.BytesIO.tell`, all in
  the trace of the package's tests, became rejected trace edges. This is
  the prometheus-client ruling (B4: the annotation decides).
- **Compiled patterns on CPython 3.6 (segno; the same ruling).** When
  CPython 3.6 is admitted, compiled-pattern methods retain
  `_sre.SRE_Pattern.<method>` beside their `re.Pattern.<method>` names
  on 3.7 and later, as configargparse, funcy and pypinyin have them.
  Removing an old test environment without withdrawing support does not
  exclude that version.
- **A module that its docstring excludes from the public API (segno).** A
  module docstring that excludes the module from the public API marks
  its functions private under C; an uncalled private function still
  receives B's public-parameter fallback.
- **Deprecated behaviour of an admitted client subclass (segno; the
  referee, `b7-ruling-segno-2.md`).** Deprecated behavior of an admitted
  client subclass remains in scope where an admitted runtime accepts it,
  but a control-flow witness must account for conversions that remove
  the subclass's overridden operations. A client `int` or `str` subclass
  fits segno's `version: int, str or None`, but on every admitted runtime
  `int()` returns an exact `int` (CPython 3.6 and later copy a strict
  subclass that `__int__` returns; PyPy 3.6 7.0 and later reconvert it),
  so `normalize_version` and the callers' guards keep
  `encoder.version_range` to versions 1 to 40: its `ValueError`
  (`encoder.py:1476`) has no edge, and the trace edge of a direct test
  of the private helper is rejected.
- **A callable that the release calls internal (pymysql; the referee,
  `b7-ruling-pymysql.md`).** An explicit statement that a callable is
  internal makes it private under C, despite its public spelling or
  direct calls in tests. Such tests do not widen inputs constrained by
  package callers; the uncalled-private fallback still applies, subject
  to B2/B3's restrictions on package values. `Connection.escape` ("for
  internal use; do not use this in your applications") and the functions
  of `pymysql.converters` (CHANGELOG: "It's internal functions") are
  private, so a test that passes `{str: escape_string}` as a mapping
  admits nothing: the inside edge `escape_item -> escape_string` went.
- **One parameter's admitted classes do not pass to another (pymysql;
  the same ruling).** Admission of a package class at one parameter
  extends along actual forwarding calls, but not to another parameter
  merely because both select similar objects. Broader admission requires
  an applicable base-class contract or documentation joining the roles;
  a default value alone establishes neither. The constructor's
  `cursorclass` admits `Cursor` and `DictCursor`; `SSCursor` and
  `SSDictCursor` are documented for `Connection.cursor(cursor)` only:
  the inside edge `Connection.connect -> SSCursor.close` went.
- **Explicit type handling in a private function (pymysql; the referee,
  `b7-ruling-pymysql-2.md`).** Explicit type handling does not supply an
  otherwise excluded input to a private function whose package callers
  constrain its arguments. Admission as a configurable converter does
  not make its parameters public-style: that requires a supported
  interface through which the package hands the callable to client code
  for invocation. pymysql's `convert_datetime`, `convert_timedelta`,
  `convert_time` and `convert_date` test for `bytes` and `bytearray`,
  but the package passes them a `str` or `bytes` only: four outside
  edges to `<builtin>.bytearray.decode` went.
- **A module flag that a client could assign (pymysql).** A client
  assignment to a module flag counts only when package documentation or
  tests establish that assignment; commented-out assignments do not
  (pymysql's `DEBUG` flags stay `False`).
- **A package value used in a refusal test (tinydb; the referee,
  `b7-ruling-tinydb.md`).** A package value used in a refusal test
  remains admitted unless the parameter's annotation excludes it;
  `Mapping` does not exclude a package object among the mapping's
  values. That admission follows package forwarding through successful
  public calls with other admitted settings, while B3 still excludes
  reuse of state left by a failed call. A test inserts a document that
  holds a `TinyDB` to show that JSON storage refuses it; with
  `MemoryStorage` the document is stored, and `Query().f.any(...)`,
  `.all(...)` and `.fragment(...)` then iterate it: three inside edges
  to `TinyDB.__iter__`.
- **A Protocol, a builder and a concrete base (tinydb; the same
  ruling).** A package Protocol admits implementations established for
  that parameter's role; structural compatibility or inheritance from a
  documented implementation does not alone override documentation
  distinguishing a builder from an evaluable condition. A concrete
  package-base annotation admits its package subclasses, and a later
  evaluation failure does not remove calls reached before that failure.
  A bare `Query` is not admitted at `cond: QueryLike` of the table
  methods, and is admitted where `any`/`all` annotate `QueryInstance`.
- **An unannotated mode parameter (tinydb).** An unannotated mode
  parameter is judged from its documented contract and explicit
  handling: `JSONStorage`'s `access_mode` admits the valid `open()`
  modes, text and binary.
- **ctypes (mss; the referee, `b7-ruling-mss.md` and
  `b7-ruling-mss-2.md`).** A ctypes foreign-function call is named
  through the concrete function-pointer class's `__call__`; for functions
  obtained from `CDLL` or `WinDLL` this is
  `ctypes.CDLL.__init__._FuncPtr.__call__`. Package `errcheck` functions
  and package functions entered through C callback thunks are callbacks
  of the package call whose library execution invokes them. A handler
  registered with a C library is a callee only at package calls that can
  dispatch it while installed, as established by source or authoritative
  documentation; registration alone adds no callback edge (mss's Xlib
  error handler is a callee of the ten Xlib calls that wait for a reply
  from the server, by the Xlib, RandR and XFixes documentation; an
  available native library loaded through ctypes is not a missing
  module). A ctypes-generated pointer or array class is named through a
  public class path rooted outside the analysed package when an admitted
  runtime provides one (`ctypes.c_char_p.__pointer_type__`, CPython
  3.14); otherwise the constructor site keeps a note and no callee,
  since neither an alias through a package class nor generated
  class-name metadata supplies an outside name. A method of a ctypes
  class object is named by the class of the receiver per implementation
  (`_ctypes.PyCStructType.in_dll` on CPython,
  `_ctypes.structure.StructureMeta.in_dll` on PyPy).
- **Why a name through a package class is no outside name (mss).** An
  edge counts as inside the package when the callee's name lies in the
  package's namespace, so a path through a package class cannot name a
  class of a library. The referee withdrew two such names for this
  reason.
- **Special methods that a library call invokes (uncertainties; the
  referee, `b7-ruling-uncertainties.md`).** A builtin or library call
  that invokes a package special method on an admitted argument adds
  that method as a callback at the triggering package site, including
  when the method raises. Methods installed dynamically must be checked
  by hand when the site finder supplies no candidate (uncertainties
  installs its operators and `__float__` with `setattr`: `math.ldexp`
  and `math.frexp` convert a number with an empty linear part through
  `__float__`, two inside edges that the writer had missed and the blind
  audit found).
- **Parameter combinations of a public helper (uncertainties).** Public
  helpers retain independently admitted parameter combinations even when
  their package callers use a narrower pairing (an ndarray `arr` with
  `numpy.matrix` as `input_type`: `inverse.view` has both receiver
  names).
- **A lazy map consumed through another library iterator
  (uncertainties).** When library code consumes a lazy map or filter
  through another library iterator, its callback belongs to the package
  site that triggers consumption (`next()` on an `itertools.chain` over
  a `map`).
- **Hashing in a dict display (uncertainties).** The site finder omits
  key hashing in dict displays; for a display used as a call argument,
  record its package hashing edge at the enclosing call site and note
  that it occurs during argument evaluation.
- **An awaited result of a missing module (pgvector; Codex round 1).** A
  stub's access path is kept across `await`, as across a call.
- **Which releases of a dependency are admitted (pgvector,
  uncertainties, textdistance, einops; the referee,
  `b7-ruling-numpy-einops.md`).** A declared dependency requirement,
  including an unversioned installable extra, admits releases satisfying
  that requirement on an admitted Python runtime, subject to explicit
  support restrictions; where no dependency requirement is declared, use
  the release's explicit version-support declarations, including
  changelogs and versioned test environments, rather than treating an
  unpinned installation command as support for every historical release.
  The benchmark pin establishes its own configuration without imposing a
  support bound, and each call site keeps the names from the admitted
  versions on which its interface exists: for numpy's dispatched
  functions, the public function path before 1.25 and
  `numpy._ArrayFunctionDispatcher.__call__` from 1.25 onward.
  uncertainties and textdistance declare a bare `numpy` extra (both
  names); pgvector's changelog names numpy 1.24 to 1.26 (both names);
  einops declares no numpy requirement and no release statement
  establishes a numpy before 1.25 (the dispatcher name only). The lead's
  first ruling for einops ("the pin decides") was wrong as a rule; its
  edges were right.
- **A stub result keeps its path through assignment (einops; the same
  ruling).** A missing-library result retains its access path through
  assignment, storage in package-created containers, and forwarding
  through package functions, just as within one expression. Concrete
  input-type evidence supplies independently admitted class paths; it
  does not replace a produced stub's path, while subscripting a
  missing-library value, unpacking it, or performing arithmetic on it
  supplies no inferred result path.
- **Open path sets (the lead's decision; einops).** A reassignment in a
  loop (`x = x.prod(axis)`) opens a path set only when the source gives no
  finite bound on the number of iterations: then the access paths of a
  stub result at the later sites have no finite bound (`...prod`,
  `...prod.prod`, and so on). A loop whose iteration count the source
  bounds (a fixed range, a fixed tuple) gives a finite family, and every
  member is an edge. For any package with such sites, the ground truth
  records the members with one and two repetitions, declares each site in
  its `<name>.md` under "Open path sets" (the site, the family, why it is
  open), and states the graph at those sites as a lower bound, as
  jsonpickle's open receiver sets. Findings at those sites are applied when
  verified and are not counted in the audit's stop rule, and the outside
  edges of its batch are read with and without each such package. Example: einops, whose reductions loop over the
  reduced axes of a client tensor (12 sites, `einops.md`). No edge inside
  a package depends on it.
- **A stub result at an `isinstance` test (websocket-client; the
  referee after Codex round 1, `b7-ruling-round1-disputes.md`).** For
  macro-benchmark edges, an otherwise unknown missing-library result may
  take either outcome of a concrete-type `isinstance` test; on the
  successful branch, B4 supplies the concrete type's method name without
  erasing the result's retained missing-module access path.
- **A client callback's result and later calls (tinydb; the same
  ruling).** An admitted client callback's opaque result may determine
  whether a call on an independently admitted receiver succeeds and
  later calls run; that witness alone supplies no callee name for the
  callback or its result. A client JSON encoder (the documented `cls`)
  that returns bytes lets `JSONStorage.write` succeed on a binary
  stream, so `flush`, `fileno` and `truncate` of `io.BufferedWriter` and
  `io.BufferedRandom` follow (six outside edges; this revises part 3 of
  `b7-ruling-tinydb.md`).
- **A private class that a public module re-exports (pyfiglet's auditor;
  path, structlog).** A class without a public path that a public module
  imports without listing it in `__all__` is named by its defining
  module: the Windows console stream is `_io._WindowsConsoleIO` (its
  type name in `Modules/_io/winconsoleio.c`; `io.py` imports it only to
  register it), not `io._WindowsConsoleIO`.
- **Architectures of an admitted operating system (einops; the referee,
  `b7-ruling-einops-platform.md`).** An operating system admitted through
  a release's declarations or its own test jobs includes its
  architectures and ABIs on which the admitted interpreter, Python
  version and dependencies can run, unless the release explicitly
  restricts them; a CI runner's architecture alone imposes no such
  restriction (numpy's distinct `intc`/`uintc` scalar classes on 32-bit
  Linux stay at `_backends.py:96:25`).
- **An outside metaclass that overrides `type.__call__` (einops; the
  referee, `b7-ruling-einops-metaclass.md`).** In an admitted
  configuration, an explicit call of a package class whose outside
  metaclass overrides `type.__call__` adds an outside edge to that
  method, named through the concrete metaclass, and retains edges to
  package constructor methods that the call actually invokes (Keras's
  jax backend with NNX enabled: `flax.nnx.module.ModuleMeta.__call__` at
  `layers/tensorflow.py:62` and `:66`, beside `RearrangeMixin.__init__`).

### Rulings for batch 8 (from 2026-11-24)

Batch 8's ground truths follow every rule above, the rulings for batches 6
and 7 included. Its blind audits draw their samples with
`random.Random(20261124)`: 70 sites, or 140 for pubchempy (no trace) and
pyusb (16 tests), and every value site. Each ruling below was given by the
lead after the auditor's opinion, or, where it decides many edges, by a
referee (Codex), whose file is in `selection/batch-8-proposal/rulings/`,
and adopted by the lead. The package's `<name>.md` and `<name>.audit.md`
record each application. Where an auditor asked to clarify an earlier
rule, the clarification is a ruling here; the earlier text stands as it
was.

- **The import-time state of a declared platform dependency (honcho J6;
  the lead).** A declared dependency of an admitted platform is not inert
  because the trace environment lacks it: the missing-module convention
  fixes how a missing library's callees are named, not what the library
  does, and its actual behaviour on that platform decides (as for
  websocket-client and einops). honcho declares `colorama;
  sys_platform=="win32"` and admits Windows; colorama 0.4.6's `init()`,
  which `honcho.printer` runs at import, replaces `sys.stdout` with a
  `colorama.ansitowin32.StreamWrapper` when `should_wrap()` holds. So
  `Printer.__init__` (`printer.py:31`) and `_check_output_encoding`
  (`command.py:400`) also call `colorama.ansitowin32.StreamWrapper.isatty`,
  beside `io.TextIOWrapper.isatty` (2 outside edges; `honcho.md` J6,
  `honcho.audit.md` R1).
- **A client's unbound call runs the body with an opaque `self`
  (pubchempy F1; the lead; clarifies B1's last sentence, the auditor's
  R2).** An object that a client passes explicitly as `self` to an
  unbound method of a public class is a client object and opaque (B5),
  and the method's body runs with it: its attributes are client values,
  and an opaque object may carry any attribute, so a test on a private,
  even name-mangled, attribute of `self` can pass. A witness that needs a
  change of package internals (storing `_Bond__wrapped` through the
  deprecated item assignment) is not used. `Bond.__delitem__(obj, key)`
  reaches `<builtin>.hasattr`, `<builtin>.KeyError` and `<builtin>.delattr`
  (`pubchempy.py:986-988`; 3 outside edges; `pubchempy.md` J6).
- **A package decorator that replaces a function with a package wrapper
  (pubchempy; the auditor's R1, as the writer and the auditor applied it
  blind).** The rule for a library decorator that wraps a method (fabric's
  `@opens`, "Implicit calls") holds for a package decorator too: where the
  decorated name is reached, the callee is the package wrapper that the
  decorator returns, and the wrapper's own call of the decorated function
  is a value site of the wrapper. pubchempy's `deprecated(...)` returns
  `deco`, whose `wrapped` replaces nine functions (`pubchempy.py:879-983`,
  `1287`, `1298`), and `memoized_property` returns
  `property(fget_memoized)` for six (`1214-1240`, `1834-1866`); the
  wrapper value sites are `806:42` and `823:24` (no edge changed). In the
  same package the lead confirmed J2 (the property names that the
  docstrings and documented examples give for "properties" are values of
  `to_dict`'s `getattr(self, p)`, B2; `record` and
  `Substance.deposited_compound` are not, B3) and J5 (`Atom.__contains__
  -> Atom.element`, the package's own name set admits it).
- **A library setting lowered through the library's documented interface
  (nodeenv F1; the lead).** Lowering a named logger's level through
  logging's public interface (`getLogger(name).setLevel`, `dictConfig`)
  is documented library configuration that changes a package-owned value
  ("Versions and configuration"), not a change of package internals: a
  client assigning a package module's own flag is (pymysql). nodeenv sets
  its `nodeenv` logger to INFO and installs its own `emit`; with the level
  lowered, the `logger.debug` sites also reach `create_logger.emit` (2
  inside edges: from `mkdir` and `_get_last_node_version`; `nodeenv.md`
  J1).
- **A package function installed as a method of a library class
  (nodeenv; the auditor's R1, as both applied it).** A package function
  that the package assigns as a method of a library class
  (`logging.StreamHandler.emit = emit`, `nodeenv.py:407`) is a call-back
  of that library (B5): the library's calls reach it, and its receivers
  are judged by B5 (a client's handlers are opaque; the package's own
  handler and logging's `lastResort` are named).
- **ctypes' module-level function-pointer objects (pyusb F1; by the
  existing rules; the auditor's R1).** `ctypes.memset` and
  `ctypes.memmove` are instances of the class that `CFUNCTYPE(...)`
  returns, so a call of them names
  `ctypes.CFUNCTYPE.CFunctionType.__call__` (the micro-benchmark's "Calls
  of instances", and "Outside names" of the 2026-11-15 clarifications: a
  callable wrapper object uses its concrete class's `__call__`); `cast`,
  `string_at` and `wstring_at` are Python functions and are named as
  such. Batch 7's
  ctypes rule covers the foreign functions of a `CDLL`; this covers the
  module's own function-pointer objects (`pyusb.md`).
- **Names from the sources of every admitted runtime (pyusb; the
  auditor's R2).** A callee outside the package is named from the sources
  of each admitted implementation and version, never from memory or
  another ledger. PyPy defines some types at interpreter level
  (`pypy/module/`), which the dependency sources hold beside
  `lib-python/` and `lib_pypy/`. pyusb's `self.lock.acquire()` and
  `.release()` (`core.py:112:30`, `115:30`) are `_thread.RLock.acquire`
  and `.release` on PyPy 3.9 to 3.11 too: `pypy/module/thread/
  moduledef.py:24` registers `RLock` as `os_lock.W_RLock`, whose TypeDef
  is `"_thread.RLock"`, and `lib-python/3/threading.py:46` takes it (no
  `threading._RLock` name; `pyusb.audit.md` R2).
- **A module that the release documents and tests as a script (vulture
  J1; the lead confirmed; the auditor's R1).** A module of the analysed
  source that the release documents and tests as a script runs as that
  script, and an import that works only in that mode is taken as written.
  vulture's whitelists run as scripts (`whitelist_utils.py:24-25`,
  `tests/test_script.py:34-37`); `ast_whitelist`'s `from whitelist_utils
  import Whitelist` gives `vulture.whitelists.ast_whitelist ->
  vulture.whitelists.whitelist_utils.Whitelist.__getattr__` (1 inside
  edge, 67 sites). face_classification's rule (code after an import of a
  module that the checkout lacks has no edges) does not apply: the
  checkout has the module.
- **A fallback that runs only when a vendored part of the analysed source
  is deleted (flit-core J2; the lead; the auditor's R1).** The checkout is
  taken as it is (face_classification): a fallback reached only when a
  distributor deletes a vendored part of the analysed source does not run
  unless the release documents that state. flit-core's `config.py:10-18`
  tries `tomllib`, the vendored `flit_core.vendor.tomli`, then `import
  tomli`; the third runs only on CPython 3.8 to 3.10 with the vendored
  copy deleted, which the release does not document (`doc/bootstrap.rst`
  allows the removal only on 3.11 and later, and `vendor/README`'s
  unbundling keeps the vendored import working). Its 3 outside edges to
  `tomli.loads` go (`flit-core.md` J2). An optional import of an
  installed declared dependency differs: both sides run on different
  versions, and vulture's `tomli.load` beside `tomllib.load` stays
  (`vulture.md` J5).
- **Dispatch on a client subclass of an abstract documented base, and
  package values stored on client objects (avro J8; the referee,
  `b8-ruling-avro-1.md`; also the auditor's R1).** B1's clause on "a
  subclass that calls the method explicitly on itself" concerns package
  subclasses. A call dispatched on a client subclass of an abstract
  documented base gets no package callees merely because that subclass
  could inherit concrete methods (B1, asyncstdlib). A value that package
  code constructs or selects keeps its provenance through explicit
  storage and forwarding, also on an otherwise opaque client object, when
  the package's assignments establish it at the call site (clarifies B5;
  B2's value flows); this needs actual assignment evidence and admits no
  client call-back result, arbitrary client attribute or client-defined
  method. avro's `TetherTask` (an `abc.ABC` with no package subclass):
  the 13 dispatch edges on the client task go (`tether_task.py`, five;
  `tether_task_runner.py`, eight), and the 17 edges on the
  package-created requestor, readers, schema, logger and event stay (9
  inside, 8 outside; the ruling file lists each site).
- **A release's own CI at its tag, for a project held as its sdist
  (avro Q1; the lead; the auditor's R2).** When the analysed artefact (an
  sdist) leaves out the release's test jobs, the jobs at the release's
  tag decide as the path and textdistance rulings say, fetched by tag.
  avro 1.12.2's `test-lang-py.yml` at `release-1.12.2` (in
  `deps/upstream-ci/`) runs on `ubuntu-latest` and `ubuntu-24.04-arm`
  with CPython 3.10 to 3.14, `pypy-3.10` and `pypy-3.11`: CPython 3.10
  and later (the last classifier is no upper bound), PyPy 3.10 and 3.11,
  Linux on x86-64 and aarch64 (einops), so `pathlib.PosixPath` alone and
  the PyPy names (5 outside edges; `avro.md`, "Versions, implementations
  and platforms").
- **A dispatch table of the package selected by a client input (toolz J4;
  the referee, `b8-ruling-toolz-1.md`).** An admitted public input may
  select a handler that the package installs in its own dispatch table;
  client opacity does not erase that handler's provenance, and each
  target needs a witness on an admitted runtime that reaches the call and
  binds, accounting for overwritten entries and short-circuiting.
  Registry membership alone does not admit package objects that B2 or B3
  exclude; admission extends between parameters only through forwarding
  or documentation of a common role (pymysql). toolz's `check_valid`
  (`_signatures.py:684:13`) keeps all 193 registry lambdas, the six
  package keys included (`is_valid_args` and `is_partial_args` document
  one role); no edge changed, and the exclusions are 51 unavailable names
  and 46 overwritten entries.
- **Which releases of a dependency are read (tablib O1/F4; the lead; the
  auditor's R1).** Batch 7's ruling admits every release that satisfies
  the declared requirement on an admitted runtime; a release in the range
  that cannot run on any admitted Python of the package is not admitted.
  The callee names come from the sources of the admitted releases, never
  from memory or another ledger. Which releases are read: the floor of
  the declared range (for a bare requirement, the oldest release that
  runs on the package's oldest admitted Python, decided by reading its
  source), and the last release of each minor series up to the version
  that the environment pins or that the date rule picks (the
  django-constance precedent, the last release of each family). The
  lead fetches them in a container by PyPI's SHA-256 into the dependency
  sources, each with its reason in `MANIFEST.json`. tablib: openpyxl
  2.6.0, 2.6.4, 3.0.10, 3.1.5 (2.6.x and 3.0.x import on 3.10: their
  `descriptors/slots.py` uses `collections.Callable` but no module imports
  it); xlrd 1.2.0 (0.9 to 1.1 call `time.clock()` when opening a
  workbook), 2.0.2; xlwt 1.0.0, 1.1.2, 1.2.0, 1.3.0; odfpy 1.3.0, 1.3.6,
  1.4.1; PyYAML 5.1 (3.10 to 3.13 test `collections.Hashable`), 5.1.2,
  5.2, 5.3.1, 5.4.1, 6.0.3; tabulate 0.4.2 to 0.10.0, the last of each
  series. Only `get_column_letter` changes a name (2 outside edges;
  `tablib.md`). The same rule gives the older releases of honcho's,
  nodeenv's, vulture's and m3u8's declared dependencies. In tablib the
  lead also confirmed J1 for `Dataset.load` (documented file streams) and
  removed `Databook.load`'s two (F3: its documentation names only an
  abstract "file-like object", and documentation is read one entry at a
  time, B4 and funcy).
- **A C type exported under a module attribute other than its type name
  (flit-core's Codex round 1; the referee, `b8-ruling-c-type-names-1.md`).**
  A method of an outside class is named by the class's public path on each
  admitted implementation and version: a public alias where one exists,
  otherwise the attribute under which the defining extension module
  exports the type, even in a module whose name starts with `_`
  (`_csv.Writer` on CPython 3.10 and later, `_sha256.SHA256Type` on 3.8 to
  3.11, `_md5.MD5Type`, `_sha1.SHA1Type`). The type name (`_csv.writer`,
  `_sha256.sha256`) is the fallback only on a runtime that exports no such
  attribute (CPython 3.8 and 3.9 for the csv writer; PyPy, whose `_csv`
  exports factories only and whose `_md5`, `_sha256`, `_sha512` and
  `_sha1` export the classes under their own names, `_sha1.sha`). The
  names are the union over admitted runtimes, never two aliases of one
  class on one runtime. An attribute that a module overwrites names what
  it holds last: CPython 3.10 and 3.11 export the SHA-512 type as
  `_sha512.SHA384Type` (`sha512module.c` sets `SHA384Type` and then
  overwrites it), and SHA-384 keeps `_sha512.sha384`. A factory function
  names its own call, not the methods of its result. The
  pyfiglet/path/structlog ruling still decides a private class without a
  public path that a public module re-exports. Earlier usage does not bind
  (the scope rules: a package judgement cannot override a global rule).
  flit-core (0fa844a), tablib (1 site) and avro (4 sites) follow it: net
  +8 outside edges over the three.
- **The lead's rulings of Codex round 1 (avro, tablib, toolz, pyusb).**
  A class whose metaclass sets `__call__` to a builtin class is called as
  that class: `MessageObject()` on a `TypedDict` (`_TypedDictMeta.__call__
  = dict`) is an edge to `<builtin>.dict` (micro README, "Instantiation
  of a builtin or external class"), and the trace's `dict.__init__` is a
  naming artefact (avro AVRO-R1-02, 1 outside edge renamed). A public
  registry key names a new entry; a key that collides with an existing
  attribute of a package class replaces package internals and admits
  nothing (B3; tablib T08, no edge). Admission follows forwarding from an
  admitted parameter onward, never backwards from a wrapped callable's
  admitted inputs to its wrapper's (pymysql; toolz R02, no edge), and a
  factory's other output is admitted only where documentation names it for
  the role (toolz R01, no edge). A native library that the package declares
  by name and series (pyusb: "libusb 1.x") is read like a dependency
  release: its floor is the oldest release that the package can load (the
  first that exports every symbol the package binds without a guard:
  libusb 1.0.12, `libusb_get_parent`) and the last release of the series
  (1.0.30); an operating system's own implementation on a declared
  platform is read at the platform's supported releases (FreeBSD 14.5 and
  15.1). pyusb: a synchronous libusb transfer handles the context's events
  and runs a concurrent isochronous transfer's callback (6 inside edges;
  `pyusb.md`, J9).

### Rulings for the corrections of 2026-11-25

The corrections of 2026-11-25 re-read published ground truths under the
rulings above. Where those rules did not decide, a referee (Codex) ruled
and the lead adopted the ruling; its file is in
`selection/corrections-2026-11-25/rulings/`, and the package's `<name>.md`
records the application under "Corrections of 2026-11-25".

- **Forwarded stub paths through constructors and recursive forwarding
  (fabric Q-F1, Q-F2; the referee, `ruling-fabric-1.md`).** An admitted
  stub keeps its access path through package storage and argument
  forwarding, constructors included; a parameter's documented or
  annotated type does not rename it (pgvector, einops). Passing a package
  class to an ordinary missing-library factory does not make its result a
  package instance: the result stays a stub (avro's provenance ruling
  covers values that package code constructs or selects, not a library
  result built from a class argument). Recursive forwarding that extends a
  path again and again without a finite bound in the source is an open
  path set, as an unbounded loop reassignment is: the ground truth records
  one and two repetitions of the repeated path segment beyond the
  originating path as lower-bound witnesses, not a count of recursive
  calls, and longer verified members stay valid additions. This does not
  cover recursion that the source bounds, inadmissible inputs, paths lost
  through a subscript, unpacking or arithmetic of a missing-library value,
  or calls that an earlier failure prevents. fabric: `Connection` stores
  the clone `invoke.config.Config.clone` of a vanilla Invoke config
  (`connection.py:261-262`); `get_gateway` forwards `self.config.clone()`
  to a new `Connection` (388, 391), which stores it or clones it again,
  and the first hop of each level repeats the flow through its own
  ProxyJump lookup (281, 303) with no bound on a chain of distinct hosts
  (`sites/docs/concepts/networking.rst:53-55`: gateways "can be chained
  indefinitely"). 18 outside edges added (22 site-callee additions),
  none removed, no inside edge changed; three open path families
  declared in `fabric.md`. The package judgement J1, which reset the path
  at the constructor's parameter, yields to the global rules.
- **Public class aliases by configuration (avro, Sublist3r, pymysql,
  markdown2; the referee, `ruling-names-2.md`; it clarifies
  `b8-ruling-c-type-names-1.md`).** A direct public class alias names the
  receiver's class in each admitted implementation, version and
  configuration where that attribute actually holds the class: stable,
  configuration-dependent and version-dependent aliases alike; a factory
  that returns instances is not a class alias. Without such an alias, the
  defining extension's exported type attribute names it, then the type
  name where no attribute is exported. One name per class in each
  configuration; the names are the union over the admitted
  configurations, and an alias in one configuration does not rename the
  receiver in another where that attribute is a factory. `hashlib.blake2b`
  and `blake2s` always hold the builtin classes (hashlib never takes BLAKE2
  from OpenSSL), so `_blake2.blake2b`/`blake2s` give way to them; PyPy's
  builtin MD5, SHA-2 and SHA-3 classes are `hashlib.md5`, `hashlib.sha256`,
  ... where hashlib falls back to them, while CPython's attributes there
  are factories, so its exported-type names stay; from CPython 3.13
  `threading.Lock` is `_thread.LockType`, so a lock's methods are named
  `threading.Lock.acquire` there beside `_thread.LockType.acquire` for the
  earlier versions. At a direct named constructor (`hashlib.md5(...)`,
  `hashlib.sha256(...)`) the PyPy private names give way to the aliases.
  At `hashlib.new(name)` (avro `schema.py:337`) CPython can fall back to a
  builtin constructor without rebinding the public attribute, so the
  referee found the deletion of the private names undecidable from the
  sources; the lead keeps them beside the added aliases there (no source
  excludes the fallback, and the benchmark removes an edge only on
  evidence that it cannot happen).

## Call sites and candidates

`sites.py` reads the source with `ast` and `tokenize` and finds every call
site. Nothing of the source is imported or run. A site belongs to the node
that its calls belong to (a call in a class body belongs to the enclosing
function or module). It is identified by its module, the position of the
token that makes the call (line and column from 1, in characters), and its
kind:

| Kind | Site | Position | Candidates by name |
|---|---|---|---|
| `call` | `f(...)`, `x.m(...)` | `(` | functions named `f` or `m` (also through `from m import g as f`); for a class named so, its `__init__` and `__new__` and those of its package bases, and the `__call__` of its package metaclass; for `f(...)(...)`, the functions defined in functions named `f` and the `__call__` of classes named `f`; package functions and lambdas passed as arguments (callbacks); for builtins such as `len`, `sorted`, `str`, the special methods they call; for `t.format(...)` and `t.format_map(...)`, what the fields of the template `t` call (as for `format`, and `__getattr__`, `__getitem__` for `{0.a}`, `{0[k]}`) |
| `decorator` | `@d` | `d` | as for a call of `d` |
| `class` | `class C(...)` | `class` | `__init_subclass__` of package bases; `__new__`, `__init__`, `__prepare__` of the package metaclass; every `__set_name__` |
| `with`, `async-with` | each item | the item | `__enter__`, `__exit__` (`__aenter__`, `__aexit__`) |
| `iter`, `async-iter` | `for`, comprehension, `yield from`, `*x`, unpacking | the iterable or target | `__iter__`, `__next__`, `__getitem__` (`__aiter__`, `__anext__`); not generator functions |
| `mapping` | `**x` | `x` | `keys`, `__getitem__` |
| `await` | `await x` | `await` | `__await__` |
| `op` | binary, unary, comparison, augmented assignment | the operator | `__add__` and `__radd__` for `+` (and `__iadd__` for `+=`), `__eq__` for `==`, for `in` `__contains__` and the iteration methods of the container and `__hash__` and `__eq__` of the element (a dict or set looks it up as a key), and so on; for `t % x` also what the conversions of `t` call: `%s` `__str__` and `__repr__`, `%r` `__repr__`, `%d` `__int__` and `__index__`, `%x` `__index__`, `%f` `__float__` and `__index__`, `%(k)` `__getitem__`, bytes `%s` `__bytes__` (all of them when `t` is not a literal) |
| `getitem`, `setitem`, `delitem` | `x[k]` | `[` | `__getitem__`, `__missing__`, `__class_getitem__` (`__setitem__`, `__delitem__`); `__hash__`, `__eq__`, `__index__` of keys |
| `getattr`, `setattr`, `delattr` | `x.a` | `a` | properties named `a`: the decorated functions, and the accessors of `a = property(fget, fset, fdel)` in a class body, by position or keyword, when they are lambdas or functions of that class body (load: `fget`, store: `fset`, delete: `fdel`); `__get__` (`__set__`, `__delete__`) if a class body binds `a` by an assignment or a decorated `def`; every `__getattr__`, `__getattribute__` (`__setattr__`, `__delattr__`) |
| `truth` | `if`, `while`, `assert`, `and`, `or`, `not`, conditional expressions | the tested expression | `__bool__`, `__len__` |
| `format` | `{x}` in an f-string | `{` | `__format__`, `__str__`, `__repr__` (`!r`: `__repr__`) |
| `raise` | `raise C` without a call | `C` | what instantiating a class named `C` runs (as for `call`) |
| `match` | class, mapping and sequence patterns | the pattern | `__instancecheck__`; `keys`, `get`, `__getitem__`, `__len__`; `__len__` and the iteration methods |

Two files can hold nodes of one name, so the module, not the node,
identifies a site. The skeleton orders the sites by module, then by the
position of the definition of their node, then by line, column and the order
of the kinds in this table. The text of a site is its source on one line,
cut to 60 characters with a trailing `...`.

The rules are naive on purpose: a candidate is any package function with a
matching name, wherever it is defined. A `%` conversion proposes the methods
that its fallbacks call too: `%s` reaches `__repr__` through
`object.__str__`, and `%d` and `%f` accept an object that has only
`__index__`. A `str.format` template also proposes what the fields nested in
a format spec call (`{0:{1}}`), and a literal template that `str.format`
rejects proposes every special method that a field can call, as a template
that is not a literal does. Names match as Python stores them: a private
name `__x` in the body of class `C` is `_C__x` (name mangling), so
`self.__walk()` in `C` proposes only `C.__walk`. A subscripted base (`class
String(Field[str])`) is the base `Field`. A module-level alias (`nullcontext
= NullContext`) is not followed, and neither is a class-body alias
(`__radd__ = __add__`). An annotation without a value (`tags: List[str]`)
binds nothing: the name is no value, no descriptor and no attribute for
`__set_name__`. A dict or set calls `__eq__` of a key when two keys have the
same hash, also when no two are equal: CPython hashes integers modulo 2**61
- 1, so two IPv6 networks of netaddr can collide, and its sets and dicts of
networks call `BaseIP.__eq__` (the trace has `IPSet.__init__ ->
BaseIP.__eq__`). `update` and `union` from a dict or a set reuse the stored
hashes and call no `__hash__`. Some sites are not sites, because the object
is builtin by its syntax: iteration over a display (`[a, b]`), a
comprehension or `range()`, `enumerate()` and similar builtins; `**` of a
dict display or of `globals()`; the truth value of a comparison, a constant
or `isinstance()` and similar builtins. Annotations are sites unless the
module has `from __future__ import annotations`: the supported versions
before 3.14 evaluate them when the function is defined. Annotations of local
variables are never evaluated. An augmented assignment to an attribute or a
subscript (`x.a += 1`, `x[k] += 1`) is also a load site of its target
(`getattr`, `getitem`), at the position of its store site.

An explicit site (`call`, `decorator`) always needs a ledger entry. Any
other site needs one only if it has candidates; the skeleton leaves out the
implicit sites without candidates, and `check.py --report <name>
--without-candidates` lists them (`netaddr.ip
[netaddr.ip.IPNetwork.__getstate__] 1053:21 getattr self._value`), to find a
site whose callee no candidate names. A **value site** is a call whose
callee is a value, with no name to match: a parameter or variable (`cb()`),
an attribute that the package assigns a value to (`self._reader(...)`), the
class of an object (`self.__class__(...)`, `type(self)(...)`), or another
expression (`table[k](...)`). A name bound by `def`, `class`, `import` or
the assignment of a lambda is not a value; a name bound by a parameter, any
other assignment, a loop, `with ... as`, `:=`, `except ... as` or a pattern
is. A name resolves as in Python, to the nearest enclosing scope that binds
it, where a class body is visible only to its own code; a builtin such as
`len` proposes its special methods only where no such scope binds its name.
The test is by name too: a call `x.f(...)` is a value site if the package
assigns a value to an attribute `f` anywhere, or to a name `f` in a module
or class body (sqlparse: every `sql.Token(...)`, because `tokens.py:35`
binds the name `Token` to a token type). A value site can also have
candidates by name, when a package function has the name of the attribute
(`self.stop(...)` and a function `stop`); it then needs both the decisions
and the note. Its entry needs a note on where the values come from. These
are the sites where a missing edge is most likely.

**Limits of the site finder.** It follows an accessor of `property(...)`
only when it is a lambda or a function of the same class body. It proposes
no candidate for the accessors of a property that a factory function makes
(bottle: `_local_property()` returns a `property` whose accessors are its
local functions; about 100 loads and stores of the thread-local `request` and `response`
call its `fget` or `fset`, and the writer found them by hand, judgement
J1). Iterating a
lazy `map` or `filter` object calls its function, but a package function
or lambda passed to `map` or `filter` is a candidate only at that call (a
callback): where another site iterates the object, it gets no candidate.
List the iteration sites with `check.py --report <name>
--without-candidates`, and add an entry by hand where one iterates such an
object (asciinema: `pty.py:84:29` and `recorder.py:37:70` iterate
parameters that hold a `map` and a `filter` of a package lambda). Where one
function builds and iterates the object, the edge is the same wherever in
that function the callback is placed (bottle: `map(tob, ...)` at
`bottle.py:1226:31`); where library code iterates it, the callback belongs
to the package site that hands the object to the library (B5). Two other
library objects call package code later, at a site with no candidate by
name: a lazy library object that is set up at its first attribute load
(whitenoise: the first load of Django's `staticfiles_storage` makes the
package's storage and runs its `__init__`, `middleware.py:197:40`), and a
library generator that calls package overrides when it is iterated
(whitenoise: Django's `post_process` generator calls the package's
`hashed_name`, `storage.py:98:45`). Add these entries by hand. Where a
default-rejected candidate sits on every iteration site,
`--report --without-candidates` lists none of these sites (each has a
candidate), and the skeleton leaves them out (the default decides them):
list them with `check.py --report <name> --default <candidate>` (funcy:
`CacheMemory.__getitem__`).

## The ledger

```
# Comments start with #.
default reject cachetools._TimedCache._Timer.__getattr__: ...  (see below)
== jmespath.parser                       the module (file) of the sites below
[jmespath.parser.Parser.parse]           the node that their calls belong to
102:31 call  self._parse(expression)     line:column kind text
    -> jmespath.parser.Parser._parse     a callee
    reject jmespath.lexer.Lexer._parse: the receiver is a Parser
    reject *: the receiver is a Parser   every other candidate
    exclude jmespath.ast.field: why      a node considered, not a candidate
    note: where the callee comes from
    undecided jmespath.foo._parse        not decided yet (skeleton)
    undecided                            callees outside the package not written yet
```

The site lines come from the skeleton; do not edit them. A rejection names
one or more candidates, separated by commas, then a colon and the reason.
`reject *` rejects every candidate that is not a callee. An exclusion
records a package node that the writer considered and left out at a site
where it is not a candidate (mostly at value sites, for the auditor): it
needs a reason, must be a node, and must not be a candidate or a callee of
the site. The callees of a
site include what the callee calls back (the key function that `sorted`
calls, the `run` method that `Thread.start` starts). An implicit site has
only package callees: implicit calls of code outside the package are not
edges. Several entries of one node give its edges in the graph.

**Default rejections.** A candidate that is wrong at almost every site where
it is proposed can be rejected once, with one reason, before the first
module line:

```
default reject cachetools._TimedCache._Timer.__getattr__: only reached for attributes that _Timer does not define, on receivers of type _Timer
```

The default decides that candidate at every site where no entry accepts or
rejects it; a `reject *` at a site also decides it there. An implicit site
whose candidates the defaults all decide needs no entry; at an explicit site
the entry stays, for the callees outside the package. To accept the
candidate at a site, write `->` for it in that site's entry. If the skeleton
left the site out, take its line from `check.py --report <name> --default
<candidate>`: each listed site shows its module, its node and its site line
(`shop.items [shop.items.Basket.walk] 46:20 iter  self.items`); put the site
line under `== <module>` and `[<node>]`. Each
default needs a reason, and one that decides no site (a typo, or a
candidate that every entry decides itself) is an error. The candidate rule
stays the same: a default only records one decision for many sites, and the
report lists them for review.

`check.py` reports: a site that needs an entry and has none; an entry with
no such site (a stale position) or with another text; a candidate that is
neither a callee nor rejected; a rejected name that is not a candidate; an
exclusion of a candidate, of a callee or of a name that is not a node; an
`undecided` line; a value site without a note; an explicit
site with no callees and no note; an outside callee at an implicit site; a
callee in the package that is not a node; a default rejection that decides
no site; a graph file that is not the graph of the ledger; and an added-edges
file that is missing or is not the one of the ledger and the trace, or
that breaks the identity of "Construction".

## Writing a ground truth

1. Start from the skeleton. It lists every site that needs an entry, with its
   candidates `undecided`:

   ```sh
   python -I evaluation/macro-benchmark/check.py --skeleton <name> > evaluation/macro-benchmark/ground-truth/<name>.ledger
   ```

   The size report (`check.py <name>`) shows where a few candidates make
   many sites, such as a `__getattr__` that every attribute load proposes:
   it lists each candidate of 50 or more sites, with its number of sites.
   For those, write the default rejections first, in a ledger with only
   them, and make the skeleton again: it keeps the default rejections of the
   existing ledger and leaves out what they decide. Write it to another file
   first (the shell empties the target of `>` before the command reads it):

   ```sh
   python -I evaluation/macro-benchmark/check.py --skeleton <name> > <name>.ledger.new
   mv <name>.ledger.new evaluation/macro-benchmark/ground-truth/<name>.ledger
   ```

2. Read every function of the analysed source. For each site, write its
   callees under the conventions above, and decide each candidate: a callee,
   or rejected with a reason. For an explicit site, also write the callees
   outside the package, then delete its bare `undecided` line. Never use the
   output of PyCG or of any other static analysis tool.
3. Generate the graph and the added edges, and check, until there are no
   errors:

   ```sh
   python -I evaluation/macro-benchmark/check.py --write <name>
   ```

4. With `dynamic/<name>.json`, the checker also reports each trace edge that
   the graph does not have, and a trace of another commit. Resolve every
   missing trace edge: add it at the site that makes the call, or, if it is
   a client callback that the tracer cannot recognise (an object from
   outside the package that the tests pass in) or another edge that rule A
   rejects, add it to `ground-truth/<name>.rejected.json` with the reason:

   ```json
   {"jmespath.visitor.TreeInterpreter.visit_multi_select_dict":
       {"collections.OrderedDict": "the tests pass OrderedDict as dict_cls"}}
   ```

   The checker reports a rejected edge that the trace does not have, or that
   the graph has. After a change to the ledger or to the trace, run
   `check.py --write` again: the added edges depend on both.

The checker also prints statistics: the edges of the ground truth, the share
that the trace confirms, and the functions that the tests run.

## Auditing a ground truth

Each ground truth was audited by an agent other than its writer, in this
order:

1. **Blind re-derivation.** From a skeleton made without the ledger, the
   auditor numbers the sites in (line, column) order, module by module,
   draws a seeded random sample of them
   (`random.Random(20261111)`, 60 to 80 sites) and adds every value site.
   For each, the auditor writes the callees from the source alone, before
   opening the ledger, then compares and classifies each difference: the
   writer missed an edge, the writer has an edge that cannot happen, naming
   only, or the auditor was wrong. Where one kind of site or one candidate
   dominates the skeleton, the auditor draws the sample by kind and says so
   in the audit (in sqlparse, 44 of the 70 sites of a plain draw were
   attribute loads, and only 19 were explicit calls; in itables,
   `_SubscriptableFallback.__getitem__` is a candidate at 793 of 1989
   sites).
2. **Exhaustive checks** of what a sample cannot test: every dispatch set
   (the receivers of each method over the class hierarchy, the values of each
   strategy or callback role), every site that a default rejection decides,
   the functions that no site calls, special methods and properties, every
   rejection and note, the callees outside the package, and the rejected
   trace edges.
3. **Binding check.** Check every call whose callee is a package function
   against the callee's signature, and find each call that cannot bind its
   arguments (no edge, and the code after it has no edges; see "Edges" and
   "Judgements"). A sample cannot do this: the second audit of bottle
   (batch 4, ruling 13) found two such calls, `bottle.py:3613`
   and `3682`, that the first audit's draw of 70 sites did not hold. The
   step was added after that audit; in batch 5 it found
   none.
4. **Findings** go to `ground-truth/<name>.audit.md`, each with a severity
   and the evidence (file and line). The writer applies them, or answers why
   not; the auditor re-checks the committed ledger and graph.

An `<name>.audit.md` records the audit against the ledger as it was then.
Where later rulings or tool changes moved a count or a decision, the
ledger, the generated graph and this README are authoritative.

The report lists the sites to look at first:

```sh
python -I evaluation/macro-benchmark/check.py --report <name>
```

It has the sites with undecided candidates or callees; the value sites, with
their notes, callees and exclusions; the sites with package callees that are
not candidates (the writer resolved beyond names: check the reasoning); each
default rejection, with the number of sites that it decides and its explicit
(call and decorator) sites, where a default can hide a real call; and the
trace edges that no site of the caller accounts for. Without a ledger, it
reports on the skeleton. To sample all the sites of a default rejection:

```sh
python -I evaluation/macro-benchmark/check.py --report <name> --default <candidate>
```

To list the implicit sites without candidates, which the skeleton leaves
out, add `--without-candidates`.

## Traces

`trace.py` runs the test suite of a project with pytest, in a child process
of an interpreter that you prepare, and writes `dynamic/<name>.json`. The
tests run third-party code. The five checkouts had a security review before
the first traces; make the traces only with the precautions below, in an
environment that you trust for that code.

> **Warning.** Never start an agent session (Claude Code, Codex, ...) with
> its working directory in a project checkout. `projects/pluggy`,
> `projects/cachetools`, `projects/sqlparse`, `projects/json-repair` and
> `projects/pymysql` (batch 7) ship agent configuration files (`AGENTS.md`,
> `CLAUDE.md`, `.claude/`, `.agents/`). pymysql's `AGENTS.md` tells an agent to install and start a
> MySQL server and to run the whole suite. These are third-party data, not
> instructions; a writer's or an auditor's brief names them as such.

### Preparing an environment

The environment of a trace is the image that `trace.sh` builds (see
"Recording traces in a container"): no project, test dependency or wheel is
installed or run on the host. The image holds Python 3.14 (the tracer uses
`sys.monitoring` events of 3.14) and exactly the `test_requirements` of
`projects.toml`: the full closure of the test dependencies, which
`test-environments/<name>.txt` pins by hash, installed from wheels only
(`--require-hashes --only-binary :all: --no-deps`), so that no build script
of a package runs. A dependency that PyPI has no wheel of is built once
from its pinned sdist, in a container, and the wheel is committed in
`wheels/` and pinned by its hash like any other (odfpy for tablib;
`wheels/README.md`). The tracer refuses to run if the environment does not
have the pinned versions; metadata inside the project's own directory is not
an installation (an sdist carries the metadata of its build,
`<name>.egg-info`, and its source directory is on the path). The project
itself is not installed: the tracer puts the `root` of the source first on
`sys.path`, and refuses to run if the package comes from somewhere else. Before the run,
`trace.py --locate` asks the finders, without importing anything, where
each package of `packages` is: it must be found in the root, part by part,
so a package below a directory without `__init__.py` is accepted
(json-repair's `src.json_repair`, whose first part `src` is a namespace
package), and the first part of its name must be found nowhere else in the
environment. One project cannot avoid it: pytest requires pluggy, so pluggy's environment has
pluggy's wheel. Its entry says so (`also_installed`): `trace.py --locate`
then accepts the installed copy, and the run still checks that pluggy was
imported from the source. `--locate` asks every finder of the interpreter
directly, not through `sys.modules`, and they read the file system only: a
package must be found in the root and by no other finder (a builtin or
frozen module, `sys.path` without the root, an editable install), so that
the environment cannot supply it. The run checks that every package of
`packages` was imported from the source, except those that the entry names
in `not_importable`: analysed source that needs a library the test
environment does not have (itables's `itables_for_dash` needs dash). For
those, the run fails if the trace has an edge from or to them.

```sh
PYTHON_IMAGE=python:3.14-slim@sha256:<digest> \
    evaluation/container/trace.sh evaluation/macro-benchmark tenacity
```

The trace records the version of every installed distribution
(`distributions`).

### Precautions

- **Clean source.** The source is a copy of the files of the pinned
  commit, from the inputs image, whose build checked them against the pin.
  The tests and conftest files run too, so the files are compared before
  and after the run: a run that leaves, changes or removes a
  file in the source fails. The child writes no bytecode (`-B`) and pytest
  no cache (`-p no:cacheprovider`).
- **Minimal environment.** The child gets an environment built from
  nothing, with no variable of the caller (no tokens, no `SSH_AUTH_SOCK`, no
  `PYTEST_ADDOPTS`): `PATH` (the bin directory of the interpreter,
  `/usr/bin`, `/bin`), `HOME` and `TMPDIR` (new directories that are deleted
  after the run), `LANG=C.UTF-8`, `PYTHONHASHSEED=0`,
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `NO_PROXY=127.0.0.1,localhost`
  (the fixed hash seed makes sets of strings iterate in the same order in
  every run). An entry may add variables of its own, by name and value
  (`environment = { EINOPS_TEST_BACKENDS = "numpy" }`): a suite that reads
  its settings from the environment gets them, and nothing else does.
  `projects.py` refuses a name that this environment sets and the names
  that configure the interpreter, pytest, the dynamic loader or the locale
  (`PYTHON*`, `PYTEST*`, `LD_*`, `LC_*`; compared without case), so that an
  entry cannot undo a precaution. The child checks that it has the
  variables, and the trace records them (`environment`); `trace_helper.py`
  refuses a trace whose variables are not its entry's. The
  interpreter runs with `-s -P`: no user site-packages, and neither the
  script directory nor the working directory on `sys.path`. Its stdin is
  `/dev/null`, so that code that reads stdin when it is not a terminal
  reads nothing, whoever starts the run.
- **Configuration of the project only.** pytest runs with the checkout as
  rootdir and as the limit for `conftest.py` files (`--rootdir`,
  `--confcutdir`), and with `-c` set to the project's own configuration
  file (`pytest_config`: tenacity, pluggy) or to `/dev/null` (the others):
  pytest then takes no configuration file from a parent directory, such as
  the `pyproject.toml` of this repository. The trace records the rootdir and
  the configuration file that pytest used (`pytest`); the tracer fails if
  they are not these.
- **Only the listed tests.** `pytest_args` names the test paths, so that
  pytest collects nothing else (a bare `pytest` in jmespath would also
  collect `extra/test_hypothesis.py`). `deselect` removes tests, each with a
  reason (h11: `test_against_stdlib_http.py` binds a TCP server on
  127.0.0.1). The trace records them and counts the deselected tests. A
  project without `pytest_args` has no test run, and the tracer refuses it:
  pytest would collect the whole checkout.
- **Plugins outside the checkout.** `plugins` lists pytest plugins that
  the run needs and the project does not have: `.py` files of the benchmark
  directory, outside `projects/`, so that no test can change them. The
  child imports each one by its path (not through `sys.path`, so that it
  cannot hide a module of the project) after the tracer starts, and passes
  it to pytest; its code is client code. The
  trace records them (`plugins`). markdown2's plugin calls the project's
  own case generator, which only its harness calls.
  `plugins/hypothesis_profile.py` is the plugin of a project whose tests use
  Hypothesis. It loads a profile with `deadline=None` (an example that takes
  longer than the deadline, 200 ms by default, fails, and under the tracer
  every call is slower), `database=None` (the example database is a
  directory in the working directory, the source copy, and a run that
  changes the source copy fails) and `derandomize=True` (the examples come
  from a fixed seed, so that two traces of the project draw the same
  examples and can have the same edges), and suppresses every health check
  (a health check fails a test whose examples are slow to generate, large
  or mostly filtered out; under the tracer generation is slower, and a suite
  that passes without the tracer must not fail its health checks with it).
  It also moves Hypothesis's storage
  directory, where it caches the Unicode character map of its text
  strategies outside the database, to a new directory below the run's
  `TMPDIR`. Hypothesis's own pytest plugin is not loaded (no autoloading);
  `@given` tests run without it.
- **Time limit.** The parent stops the run after `--timeout` seconds
  (default 600). The child runs in its own process group; after the run,
  or when it is stopped, every process left in that group (a server that a
  test started) is killed. The parent waits for the child without reaping
  it first, so that its process group id cannot go to an unrelated
  process in between.

### The pytest plugins

`plugins/` holds the five pytest plugins that `plugins` of `projects.toml`
names. Each changes nothing in the checkout; for the tracer it is client
code.

- `hypothesis_profile.py` (the projects whose tests use Hypothesis): see
  "Plugins outside the checkout" under "Precautions".
- `nose_tools.py` (asciinema). asciinema's tests import `assert_equal` and
  `assert_raises` from `nose.tools`. nose 1.3.7, its last release (2015),
  cannot be imported on Python 3.12 and later: importing `nose.tools`
  imports the package `nose`, whose importer imports the module `imp`,
  which Python 3.12 removed. `nose.tools` defines its `assert_*` functions
  as the methods of a `unittest.TestCase`, so they need an instance of it.
  The plugin puts a module `nose.tools` with those two methods in
  `sys.modules` before pytest collects the tests; an empty `__path__`
  makes `nose` a package, so that `nose.tools` is its submodule.
- `testlib_cases.py` (markdown2). markdown2's own harness
  (`test/testlib.py`, run by `make testone`) imports
  `test/test_markdown2.py` and exhausts its generator `test_cases()`. That
  hook adds one test method per case file to the unittest classes of the
  module. pytest never calls it, so without the plugin it sees none of the
  cases. The plugin exhausts the hook once, before pytest collects the
  module, so that pytest collects the generated methods as unittest tests.
  The hook itself is not collected as a test: pytest 9 would refuse the
  whole module because a function named `test_*` yields. The plugin runs
  only the project's own hook.
- `outputs_cleanup.py` (python-barcode). 19 test items of python-barcode
  0.16.1 (21 with Pillow) write barcodes (SVG, PNG, JPEG files) and an
  `index.html` into `tests/test_outputs/` of the checkout; the directory's
  `.gitignore` ignores them. `trace.py` fails a run that leaves a file in
  the checkout copy, so these tests could not run without the plugin. At
  the start of the session it records every file of the rootdir (the
  checkout): the SHA-256 of a file, the target of a link (links are not
  followed), or a directory. At its end it removes what is new in
  `tests/test_outputs/` and nothing else, in reverse order so that a
  directory's contents go before it: new files and links (never the
  target of a link), then new directories. Then the checkout must be as it
  was at the start. If anything else changed (a file outside that
  directory, or one that was in it at the start), it raises
  `OutputsChanged`, listing the changes as `git status` does, and the run
  fails: `trace.py` reports the exception. Its end of session runs last
  (`trylast`), so that the other plugins (the tracer's test counts) finish
  first.
- `avro_load_tests.py` (avro). Eight unittest `TestCase` classes of avro
  1.12.2's tests take constructor arguments (a datum, a schema, a
  fingerprint) that only the modules' unittest `load_tests()` supplies;
  upstream runs them with `python -m unittest discover`. pytest ignores
  `load_tests` and instantiates each class while it collects it, so each
  one is a collection error, which `--deselect` cannot remove (it filters
  items after collection). The plugin returns no collector for exactly
  these class names in exactly these modules (`CLASSES`); every other
  class and module is collected as before. It runs no project code.

### What the tracer does

1. It checks the checkout and the environment (see Precautions).
2. In the child, it starts the tracer of
   `evaluation/micro-benchmark/validate.py`, imports pytest and the
   `plugins`, and runs `pytest <pytest_args> -c <config> --rootdir=.
   --confcutdir=. -p no:cacheprovider --continue-on-collection-errors
   [--deselect=...]` in the checkout.
3. It names the calls with the validator's rules. The code that runs is in
   three zones: the package; library code (the standard library, builtins,
   and the installed `dependencies` of `projects.toml`); and client code
   (all other code: tests, conftest files, pytest, its plugins, the tracer).
   - **Callers** are the modules and functions of the package. A package
     function that client code calls has no caller. Library frames between
     two package frames are transparent: a callback from a builtin belongs to
     the package scope that called the builtin. A client frame ends the
     search: what a test callback calls is not an edge of the package.
   - **Callees** are package functions (every invocation, also implicit
     ones) and, for call expressions, code outside the package. A callee
     defined in client code is dropped and counted in
     `dropped.client_callbacks`. A call in a thread that
     `threading.Thread.start` did not start has no caller and is counted in
     `dropped.unknown_caller`.
   - Threads, generators and coroutines follow the validator.
   - **Starts.** A second `sys.monitoring` tool (id 3; the validator's is
     `PROFILER_ID`) records the first `PY_START` of each package function,
     then stops watching it: that is the only event of a generator or
     coroutine function that the interpreter drives (`__iter__` written as
     a generator, `__anext__`), which no call expression calls. A
     function's code object is registered when its module starts, so
     before the function can run. A function also counts as executed when
     it is the caller or callee of an edge, so a generator function counts
     when its generator is created, even if it never runs.
4. After the run, it checks that the package was imported from the checkout
   and traced from its first import, that pytest used the expected rootdir
   and configuration, that pytest finished with exit status 0 or 1, and that
   the checkout is still clean. Failing and skipped tests do not stop the
   trace. If a check fails, it writes no file.

**pluggy.** pytest imports pluggy. With `src` first on `sys.path`, pytest
runs on the pinned source, which the tracer starts to watch before pytest is
imported. The trace therefore also has the calls that pytest's own plugin
system makes in pluggy. They are real calls of the package. pytest's hook
implementations are client callbacks.

### Re-recording a trace

A trace is the reproducible half of a ground truth. To record the trace of
a project again you need Docker with Compose, `test-environments/<name>.txt`
(the pinned test environment) and the inputs image, which holds the
source. 54 projects have a trace; fabric, face_classification,
Sublist3r, pyfiglet, mss and pubchempy have no test run.

```sh
C="docker compose -f evaluation/compose.yaml"
# 1. Every input by its pin, the source of the project among them (the
#    only step that downloads third-party code).
$C build inputs
# 2. The image of the project: CPython, its pinned test requirements and
#    its source from the inputs image.
NAME=jmespath $C build trace
# 3. Run its tests under the tracer, without network; compare the new
#    trace with the committed one.
NAME=jmespath $C run --rm trace --compare
```

Step 3 copies the source of jmespath out of the image, runs the
tests under the tracer, checks the new trace (its format, the project and
the pin, exactly the distributions of the requirements file) and writes
`evaluation/results/trace/jmespath.json` and `jmespath.installed.txt`.
`--compare` prints the Python version, the test counts and the number of
edges of both traces, the distributions that differ and the edges that
only one trace has, and exits with 0 only if the edge sets are equal. The
committed `dynamic/jmespath.json` is never changed by the service.

The service (`container/trace_entry.py`) runs without network, with a
read-only root, no capability and a non-root user. `/repo` is this
repository, read-only; `/results/trace` (`evaluation/results/trace/`) is
the only writable host mount, so the test suite of a project
(third-party code) writes nowhere else on the host (a finding of the
security scan of 2026-11-14); `/tmp` is a tmpfs. Like `trace.sh`, it runs only
our own code and the project's tests: the trace image holds CPython, the
pinned test requirements and the project's source, neither PyCG nor git.

To replace a committed trace (after a change of the tracer, of the test
selection or of the environment), copy the two files and check the ground
truth against the new trace. `check.py` reads the source too: run it in
the inputs image, which holds the sources, or on the host (Python 3.14
or later) on the copy of the sources out of the inputs image (see "Getting
the sources"); `check.py --write` writes `ground-truth/`, so it runs on the
host:

```sh
B=evaluation/macro-benchmark
cp evaluation/results/trace/jmespath.json $B/dynamic/jmespath.json
cp evaluation/results/trace/jmespath.installed.txt $B/test-environments/
$C run --rm inputs python3 -I -B /repo/$B/check.py jmespath   # in the image
python3 -I $B/check.py jmespath                                # on the host, on the copy
```

`check.py` fails for each new trace edge that is neither in the graph nor
rejected: a reviewer then adds it to the ledger or rejects it with a
reason (see "Writing a ground truth"), and `check.py --write` writes the
graph and the added edges again. No command regenerates a ground truth.

**Repeatability.** On 2026-11-15 each of the 27 traced projects was traced
5 more times with `NAME=<project> $C run --rm trace --compare`, on
linux/aarch64 with CPython 3.14.10, the platform of the committed traces.
132 of the 135 runs give exactly the committed edges. The 3 others are runs
of asciinema: each misses one edge, `asciinema.pty.record._copy ->
asciinema.pty.record.<lambda1>.<lambda1>`, a callback whose call depends on
the timing of a pseudo-terminal. No run gives an edge that the committed
trace lacks. A trace edge is an edge of any run, so each committed trace is
the union of its six recordings, and the traces stay as they are.

**The rule for the recordings of batch 7** (fixed on 2026-11-22, before
any trace of the batch). Each package was recorded twice with its full
test selection, and every recording had to be a valid trace of its pin
and environment. The failed and the errored test ids had to be the same in
both recordings and each declared beforehand with its reason; the declared
failures started empty, and one was added after the first run:
uncertainties' `tests/test_umath.py::test_math_module` fails in both
recordings at the same assertion, because Python 3.14 words the message of
`math.log(0.0)` differently (the calls made before the assertion stay in
the trace), and uncertainties was recorded again. If the full recordings
have the same edges, the first is the trace. Only a package whose tests
were declared beforehand as drawing unseeded random data could have
unequal recordings accepted, as the union of its full recordings, after
two equal recordings with those tests deselected: einops (the five test
modules that draw from `numpy.random.default_rng()` without a seed),
uncertainties (`tests/test_uncertainties.py::test_comparison_ops`,
`tests/test_unumpy.py::test_numpy`) and pgvector
(`tests/test_bit.py::TestBit::test_random`); textdistance's Hypothesis
tests are not on the list, as its profile fixes the seed. Every package's
full recordings had the same edges, so each trace is its first full
recording, and no union was taken. The decision record of each package
(the SHA-256, edge count, test counts and failure ids of each recording)
is an audit record.

Batch 8 was recorded by the same rule. Its declared random tests are
none: toolz's random tests seed their generators, and the `uuid4()` values
of tablib and avro do not change what their tests call. One failure was
declared before its run: pyusb's
`tests/test_util.py::FindDescriptorTest::runTest` calls `usb.core.find`
with no backend, the image has no libusb, and the test fails with
`NoBackendError`; it is kept as the only test of the backend search. The
first run added 20 declared failures of nodeenv: each test writes an
executable into its tmpdir and runs it, or asserts that it is executable,
and the trace container mounts `/tmp` noexec (Docker's tmpfs default, as
for every committed trace); the calls made before each failure stay in the
trace. The same run voided avro's attempt 1, whose eight classes that only
`load_tests()` can instantiate were collection errors; avro's entry then
gained the plugin `plugins/avro_load_tests.py`, and attempt 2 is its trace.
Every package's full recordings had the same edges.

### Recording traces in a container

The traces of batch 3 and of every later batch were recorded in Docker
containers, not on the host: nothing of these packages or of their test
dependencies is installed or run on the host. The `trace` service above is
the way to do it with Docker only. `evaluation/container/trace.sh` is the
maintainers' own script for the same run: it runs Docker from the host,
needs Python on the host for its checks, and writes the trace into
`dynamic/`. It takes the source from the inputs image
(`pycg-inputs`: build it first with `$C build inputs`), a
benchmark directory and one project that has `test-environments/<name>.txt`:

```sh
PYTHON_IMAGE=python:3.14-slim@sha256:<digest> \
    evaluation/container/trace.sh evaluation/macro-benchmark aiocache
```

`--dry-run` prints the commands and runs no container; it only
checks the pin. The checks are in `trace_helper.py`, which runs on the
host, runs nothing of a project, and uses neither the network nor git.
The script:

1. checks that the commit of `projects.toml` is that of the round log that
   drew the project (`trace_helper.py check-pin`); for a project held as an
   sdist (see below), that the sdist of `projects.toml` names the release
   of the round log (`dagster_pipes-1.13.28.tar.gz` for dagster-pipes
   1.13.28);
2. builds the image `pycg-trace-<name>:<tag>` from
   `evaluation/container/Dockerfile.trace`, the requirements file (with
   the Dockerfile the only files of the build context), the wheels built
   here (`wheels/`, the named context `wheels`: pip finds there, by
   `--find-links`, the wheels that PyPI lacks, and installs them by hash
   like every other) and the project's source from the inputs image (the
   named context `inputs`). The tag is 12 hex digits of the SHA-256 of the
   two files, the base image and every file of `wheels/`, so a new or
   changed wheel gives every project a new tag. The
   base image is given by digest in `PYTHON_IMAGE` (the script refuses to
   run without it). The image has the official CPython 3.14 and the
   hash-pinned closure, installed by pip with no configuration (pip is
   then removed), and the project's source at
   `/inputs/macro-benchmark/projects/<name>`; not PyCG, and a user with the
   fixed uid 10001;
3. copies `trace.py`, `projects.py`, `evaluation/micro-benchmark/validate.py`,
   `evaluation/container/entry.sh`, the `projects.toml` and the project's
   plugins into a temporary directory, and makes an empty output
   directory;
4. runs `entry.sh` in the container. It copies the source to a work
   directory on a tmpfs, so that the tests may write next to themselves,
   prints the interpreter, runs `trace.py --locate`
   (the package must be found in the copy and nowhere in the
   environment, by the finders, without importing it), and runs
   `trace.py`: the tracer compares the copy's files before and after the
   run;
5. checks the trace (a regular file under 64 MiB, while the first
   traces were under 2 MiB; the keys and types that
   `trace.py` writes, in its format, of this project and commit, and with
   exactly the distributions of the requirements file), copies it to
   `dynamic/<name>.json`, writes the distributions to
   `test-environments/<name>.installed.txt`, and prints the test counts;
6. removes the temporary directories, and the container if a step failed.
   A failure names the step. The temporary directory goes to the trash
   where the host has a `trash` command (recoverable); else it stays, and
   its path is printed.

The container runs with `--network none --read-only --cap-drop ALL
--security-opt no-new-privileges --pids-limit 512 --memory 6g
--memory-swap 6g --cpus 4 --user 10001:10001`, a tmpfs on `/tmp` (1 GB)
and on `/home/runner` (256 MB), and `HOME=/home/runner`,
`PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. The memory limit was 4
GiB until batch 4: under the tracer, fastjsonschema's
`test_examples`, which compiles a 3.4 MB schema, went over it and the
container killed the tracer; at 6 GiB it passes, within the 7.7 GiB of
the Docker VM that recorded the traces. It has exactly two
mounts: the tracer directory (read-only) and the output directory. The repository, the project's source, the home directory and
the Docker socket are not mounted; there is no `--privileged`, `--pid`,
`--ipc` or host network. The image is built with network access (pip
downloads the wheels); the tests run without any. Docker gets only `PATH`,
`HOME`, `DOCKER_HOST` and `DOCKER_CONFIG` of the caller's environment. The
digest of the base image is recorded in each `test-environments/<name>.installed.txt`.
Inside the container the tracer works as described above; the trace names
code relative to the package root, as on the host, so a trace from a
container has the same format.

**Re-tracing with `trace.sh` to check committed traces.** `trace.sh` writes
`dynamic/<name>.json` and `test-environments/<name>.installed.txt` in the
benchmark directory that it is given. To keep the committed traces, give it
a scratch directory with a copy of `projects.toml` and `test-environments/`
(the source comes from the inputs image). Then compare each new trace
with the committed one:

```sh
python3 -I evaluation/container/trace_helper.py compare \
    evaluation/macro-benchmark/dynamic/jmespath.json "$scratch/dynamic/jmespath.json"
```

It prints the Python version, the test counts and the number of edges of
both traces, the distributions that differ, and the edges that only one
trace has, counted by caller module and by callee kind (`package`: a
function of the package; `builtin`; `library`: the standard library and
the dependencies), then listed. It exits with 0 only if the edge sets are
equal.

**A project held as an sdist.** An entry may name, in place of
`repository`, `tag` and `commit`, a source archive from PyPI: `sdist` (its
file name, ending in `.tar.gz`), `sdist_url` (an https URL that ends in that
name) and `sdist_sha256`; `projects.py` refuses an entry with both forms or
with an incomplete one. The archive is not kept: the build of the inputs
image downloads it, checks its SHA-256 and unpacks it into
`/inputs/macro-benchmark/projects/<name>`, where `check.py`, `sites.py`
and the runner read the source as they read a checkout. The
unpacking (`fetch.unpack_sdist`) uses tarfile's `data` filter (no absolute
path, no `..`, no link out, no device), and every member must be under the
top directory that the file name names (`dagster_pipes-1.13.28/`).
`trace.py` records `sha256:<hash>` as its `commit`; `check.py` compares
that with the entry.

### Format of `dynamic/<name>.json`

| Key | Content |
|---|---|
| `edges` | Sorted adjacency list `{caller: [callees]}` |
| `aliases` | `{callee: [names]}`: other names of a callee outside the package |
| `modules`, `functions` | The package modules that ran, and the functions and lambdas defined in them |
| `executed` | The package functions that ran: called, started (also a generator or coroutine that the interpreter drives) or with out-edges |
| `tests` | Pytest exit status, and the tests by outcome as pytest's summary line counts them (passed, failed, errors, skipped, xfailed, xpassed, deselected): a passing subtest of a `unittest` test is not a test |
| `pytest`, `deselect` | The rootdir and configuration file that pytest used (relative to the checkout); the deselected tests with their reasons |
| `plugins` | Only for a project with `plugins`: their paths, relative to the benchmark directory |
| `failures` | The ids of the failed and the errored tests (`failed`, `errors`), as pytest's summary counts them; written since batch 7 |
| `environment` | Only for a project with `environment`: the variables that its entry adds to the test run, by name |
| `dropped` | `client_callbacks` and `unknown_caller` (see above) |
| `project`, `commit`, `python`, `distributions` | The source and the environment of the trace; for a project held as an sdist, `commit` is `sha256:` and the SHA-256 of the archive |

A callee outside the package has a canonical name: where it is defined. A
function is named by its module and qualified name without `<locals>`
(`posixpath.join`), a class by its module and qualified name, a builtin by
`<builtin>.` and its name, and a method of a builtin type by the type that
defines it (`<builtin>.dict.get`).

The child also finds the other names that resolve to the same object, so
that the checker can match `os.path.join` in the ground truth with
`posixpath.join` in the trace without importing anything. The names are the
paths through the library modules that are loaded at the end of the run:
`module.name`, and `module.Class.name` where the class defines the name or
is in the MRO of a package class or of an object whose method the package
called. Only public names count: those in `__all__` if the module has one,
else those that do not start with an underscore. Modules whose dotted
name has a part that starts with an underscore, and `__main__`, give no
names; `builtins` is written `<builtin>`. A module's namespace is read
with `object.__getattribute__`, neither `isinstance()` nor `vars()`:
`sys.modules` can hold an object that runs code when an attribute is read
(a lazy module). A method call passes a bound method, or the function or
descriptor of the method with the object as first argument; the tracer
notes the class of that object only when the function is what the type
holds under that name, not a function that merely takes the object as
first argument. A callee outside the package of another kind than those
above keeps, as canonical name, the first in sort order of the names that
the validator recorded for it. The checker accepts a
ground-truth callee if it is the canonical name or one of these names.

The output is deterministic for one environment. Another interpreter or
other versions of the installed packages can give another trace.

### Limits

- The limits of the validator apply (see the micro-benchmark README). For
  example, a generator function that builtin code starts has no caller in
  the trace (marshmallow's `OrderedSet.__iter__` under `iter()`), nor has a
  coroutine `__call__` of an instance whose coroutine starts in client code
  (asyncstdlib `_lrucache.py:156`). These edges come from reading only.
- **Tracer defect T1**, a known limit of every committed trace. `trace.py`
  overrides the validator's `on_call` and calls `super().on_call(...)`,
  which adds a frame, so the validator's `sys._getframe(1)`
  (`evaluation/micro-benchmark/validate.py:439` and `449`) reads the frame of
  `trace.py`, not the frame that made the call. So every trace misses the
  calls in module code that `exec` runs (fastjsonschema: `compile ->
  <builtin>.type`), the call of a `@contextmanager` generator function by
  `contextlib` (sqlparse's `utils.indent`; 11 edges of fastjsonschema, 15
  of pyflakes), and the calls of a thread that library code starts. The
  cause is in `trace.py`, not in the validator, which handles these cases
  itself. The ground truths are not affected: their writers add these
  edges from reading. The "confirmed by the trace" counts are lower than
  they would be. The fix comes after round 2: fix and test the tracer,
  re-trace every project in containers, check that the edges of each old trace
  are a subset of the new one, and update the counts and this text. It was
  not made earlier, so that the traces of a batch did not change while its
  ground truths were written.
- `aliases` is keyed by the canonical name of a callee outside the package
  (`trace.py`, `result`). Two outside functions of one canonical name (two
  closures that a factory makes, say) share one list of other names, so a
  graph edge can match the trace edge of the other function (found by the
  review of the added edges, 2026-11-14; see "Construction").
- An object from outside the package that the tests pass in (a builtin
  function, a standard-library class, `functools.partial`) cannot be told
  apart from one that the package chooses. Its calls are in the trace; reject
  them with a reason.
- A ground-truth name that resolves to the callee through another path (a
  private module, a class that the package does not name) does not match.
  The checker lists the names that do.
