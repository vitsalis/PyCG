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
| `micro-benchmark/snippets/<category>/<case>/` | One small program per language feature, with its ground truth in `callgraph.json` |
| `docs/design.md` | The design of the analysis: what it models, its rules, termination, open problems |
| `evaluation/` | Measures PyCG: the runner, the scorer and their tests (`evaluation/README.md`, `evaluation/AGENTS.md`) |
| `evaluation/macro-benchmark/` | 30 real packages with hand-written ground truths and traces |

## Commands

```
make setup              # create the environment (uv sync --locked)
make test               # all tests: the engine's and the evaluation's
make lint               # ruff check and format check
make format             # apply formatting
make eval               # measure this commit on both benchmarks (Docker)
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
- Record every measurable result (benchmark numbers, bugs found in ground
  truth, design decisions and their reasons) in the commit message of the
  change. Benchmark numbers come from `make eval` on a clean commit.
- **The evaluation measures PyCG only.** Work under `evaluation/` follows
  `evaluation/AGENTS.md`: third-party code runs only in Docker.

## Workflow

Do each feature on its own branch from `main`, in a worktree under
`.worktrees/`, and open a pull request when tests and lint pass.
