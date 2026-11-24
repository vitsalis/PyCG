# Agent instructions

PyCG generates call graphs for Python code with a fully static analysis.
It never imports or executes the code it analyses. Keep it that way.

## Layout

| Path | Content |
|---|---|
| `pycg/` | The tool. `__main__.py` is the CLI, `pycg.py` the `CallGraphGenerator` entry point, `formats/` the output format (docs/format.md) |
| `pycg/analysis/` | The analysis: the builder that turns the AST into constraints, the rules, and the solver |
| `tests/unit/` | Unit tests |
| `tests/test_micro_benchmark.py` | Runs every micro-benchmark case against its expected call graph |
| `evaluation/micro-benchmark/snippets/<category>/<case>/` | One small program per language feature, with its ground truth in `callgraph.json` |
| `docs/design.md` | The design of the analysis: what it models, its rules, termination, open problems |
| `evaluation/` | Measures PyCG: the runner, the scorer and their tests (`evaluation/README.md`, `evaluation/AGENTS.md`) |
| `evaluation/macro-benchmark/` | 40 real packages with hand-written ground truths and traces |

## Commands

```
make setup              # create the environment (uv sync --locked)
make check              # before pushing: lint, and the tests of what the change touches
make check FULL=1       # every check, as make lint and make test
make test               # all tests: the engine's and the evaluation's
make lint               # ruff check and format check
make format             # apply formatting
make eval               # measure this commit on both benchmarks and gate it (Docker)
make eval-record        # raise evaluation/metrics.json to the values measured
uv run pytest -k classes/call   # one benchmark case
```

Supported Python versions: 3.12 to 3.15. The runtime has no dependencies; do
not add one without discussion.

## Rules

- **Ground truth is independent of the tool.** A `callgraph.json` states what
  Python does when the snippet runs. Never edit one to match PyCG's output,
  and never special-case the analysis for a snippet.
- **Known failures are explicit.** `tests/known_failures.txt` lists the
  cases the analysis does not handle, each with its cause, as strict expected
  failures. `tests/triage.py` holds the causes and regenerates the file: run
  it after a change, and give a new failing case its cause there.
- **Tests first.** Write the failing test, then the code. Test behaviour
  through public entry points; cover edge cases and error paths.
- **Results are deterministic.** The same input gives the same output on every
  run and every supported Python version.
- **Replace, do not deprecate.** Remove code that a change makes obsolete.
- Record every measurable result (bugs found in ground truth, measurements
  other than those of `make eval`, design decisions and their reasons) in
  the commit message of the change. The numbers of `make eval` go in the
  pull request description (see Workflow).
- **The evaluation measures PyCG only.** Work under `evaluation/` follows
  `evaluation/AGENTS.md`: third-party code runs only in Docker.

## Protected files

These paths define what PyCG is measured against:

- `evaluation/macro-benchmark/ground-truth/`
- `evaluation/macro-benchmark/dynamic/`
- `evaluation/macro-benchmark/projects.toml`
- `evaluation/macro-benchmark/test-environments/`
- `evaluation/common/same_function.json`
- `evaluation/micro-benchmark/snippets/**/callgraph.json`
- `tests/known_failures.txt`
- `evaluation/metrics.json`
- `.github/`

Every agent follows these rules:

1. Change a protected file other than `evaluation/metrics.json` (rule 3)
   only when your task names that file and the change to make. Otherwise
   stop and report the change you would make and why.
2. Never change a protected file to make a test, the gate or CI pass.
3. Only `make eval-record` writes `evaluation/metrics.json`. Never edit it by
   hand, never lower a value, never change the margin. Run `make
   eval-record` when a change raises a value or changes the benchmark (its
   digest in the file; the measured values then become the bests), and
   commit the file with the change.
4. Only `tests/triage.py` writes `tests/known_failures.txt`. A case leaves
   the file when it passes. Add a case only with `tests/triage.py
   --readmit`, and only when your task says so.
5. Report a failing gate, a failed run or a lost edge; never work around
   it. No special case for a benchmark program, no option that exists for a
   benchmark, no edit of a ground truth to match PyCG's output.

CI labels every pull request `benchmark-changed` when its diff touches a
protected file, and `metrics-changed` when a TP, FP or FN count (micro,
macro inside, macro outside) differs from its base. The maintainer reviews
both.

## Workflow

Do each feature on its own branch from `main`, in a worktree under
`.worktrees/`. One pull request makes one change.

Name a branch `<username>/<feature>`: the GitHub username the work is
pushed under, then the feature in lowercase words joined by hyphens, for
example `vitsalis/no-comments-eval`.

Write each commit message as `type(scope): summary`, for example
`fix(engine): bind explicit static method __get__`. The type is one of
`feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `ci`, `build` and
`chore`; the scope is the area the change touches (`engine`, `cli`, `agents`,
`micro`, `bench`, `eval`, `ci`, `docs`). The summary is lowercase and in
the imperative, with no full stop. The body says why, with the commands
and the measurements behind the change.

While developing, run the narrowest tests that cover the change (`uv run
pytest tests/test_x.py -k name`). Before pushing, run `make check` and
nothing more. Then push the branch and open a draft pull request at once.
CI runs the full tests on every supported Python and, when the diff touches
a path that can move the metrics (`EVAL_PATHS` of `tools/check.py`), the
gate of `make eval` and the determinism check; do not run them locally as
well. Run `make eval` locally only to investigate a metrics change, or
before `make eval-record` when the gate of CI reports that a value rose and
must be recorded.

Mark a pull request ready only when CI is green for its exact current
commit: lint, tests, the gate (no value below its floor, no failed run) and
the determinism check. Its description carries the metrics table of the job
summary of CI.
