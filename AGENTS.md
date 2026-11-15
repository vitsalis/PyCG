# Agent instructions

PyCG generates call graphs for Python code with a fully static analysis.
It never imports or executes the code it analyses. Keep it that way.

## Layout

| Path | Content |
|---|---|
| `pycg/` | The tool. `__main__.py` is the CLI, `pycg.py` the `CallGraphGenerator` entry point, `formats/` the output formats |
| `tests/unit/` | Unit tests |
| `tests/test_micro_benchmark.py` | Runs every micro-benchmark case against its expected call graph |
| `micro-benchmark/snippets/<category>/<case>/` | One small program per language feature, with its ground truth in `callgraph.json` |
| `docs/paper-notes.md` | Measurements and decisions for the follow-up paper |

## Commands

```
uv sync                 # create the environment
uv run make test        # all tests
uv run make lint        # ruff check and format check
uv run make format      # apply formatting
uv run pytest -k classes/call   # one benchmark case
```

Supported Python versions: 3.12 to 3.15. The runtime has no dependencies; do
not add one without discussion.

## Rules

- **Ground truth is independent of the tool.** A `callgraph.json` states what
  Python does when the snippet runs. Never edit one to match PyCG's output,
  and never special-case the analysis for a snippet.
- **Known failures are explicit.** `KNOWN_FAILURES` in the benchmark test
  lists the cases the analysis does not handle, as strict expected failures.
  When a change fixes a case, remove its entry. When a new case fails, add it
  with a one-line reason.
- **Tests first.** Write the failing test, then the code. Test behaviour
  through public entry points; cover edge cases and error paths.
- **Results are deterministic.** The same input gives the same output on every
  run and every supported Python version.
- **Replace, do not deprecate.** Remove code that a change makes obsolete.
- Record every measurable result (benchmark numbers, bugs found in ground
  truth, design decisions and their reasons) in `docs/paper-notes.md`.

## Workflow

`dev` is the integration branch. Do each feature on its own branch in a
worktree under `.worktrees/`, and merge it into `dev` with a descriptive
merge commit when tests and lint pass.
