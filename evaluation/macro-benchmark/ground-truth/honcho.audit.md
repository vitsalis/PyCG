Status: closed. Blind answers (commit `0e01eb5`), comparison (74 of 74),
exhaustive checks and binding check found no edge finding; the lead ruled
J6 for the two outside edges, and the re-check against `f8b2292` (297
edges: 99 inside, 198 outside) finds nothing open.

# honcho: blind audit of the ground truth (batch 8)

Release v2.0.0, pin `8af63177405a574612abf90ef55aaa68d76f7686`. Audited
files, as committed in `dc1795c` on `b8-gt-honcho`:
`honcho.ledger` (1025 lines, 363 sites, no default rejection, no
exclusion), `honcho.json` (295 edges: 99 inside, 196 outside; 85 nodes),
`honcho.added.json` (161 added edges), `honcho.md` (J1 to J8). No
`honcho.rejected.json`: every trace edge is in the graph.

Read: the package source (`honcho/`, the nine Jinja2 templates),
`pyproject.toml`, `tox.ini`, `CHANGELOG.rst`, `doc/export.rst`,
`doc/api.rst`, `.github/workflows/main.yml`, the tests
`tests/test_export_base.py` and `tests/test_export_supervisord.py` (as data);
the README's rules and rulings; `PyCG/micro-benchmark/README.md`
("Ground-truth conventions"); the precedents `asciinema.ledger`,
`configargparse.ledger`, `tinydb.ledger`, `pymysql.ledger`,
`pymysql.audit.md`, `mss.ledger`; the dependency sources of `deps/`
(Jinja2 3.1.4 `__init__.py`, `compiler.py`, `nodes.py`, `loaders.py`;
colorama 0.4.6 `initialise.py`, `ansitowin32.py`;
backports.entry-points-selectable 1.3.0; CPython 3.8.20, 3.13.18, 3.14.10,
3.15.2 and PyPy 3.11 `os.py`, `logging/__init__.py`, `subprocess.py`,
`multiprocessing/context.py`). The trace was read only after the blind
commit. Nothing of the package was run; no analysis tool was used.

Commands (all with `python3 -I`, from outside the source trees):

```sh
check.py --benchmark-dir <scratch> --skeleton honcho    # blind skeleton
check.py --benchmark-dir <scratch> honcho
draw.py <skeleton>                                       # the sample
check.py honcho                                          # no errors
check.py --origin honcho
check.py --report honcho
check.py --report honcho --without-candidates
```

## Final state

Agreement: 74 of 74 sampled sites. No edge is missing and no edge is
false. The graph stays at 295 edges (99 inside, 196 outside) unless the
lead rules J6 the other way (+2 outside edges, no inside edge).

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| R1 | remark on the README, low | J6: the side effect of a declared platform dependency that the trace environment lacks | `printer.py:72-82`; `pyproject.toml` (`colorama; sys_platform=="win32"`); colorama 0.4.6 `initialise.py` (`init` assigns `sys.stdout = wrap_stream(...)`), `ansitowin32.py` (`StreamWrapper.isatty`, `should_wrap`) | 0 or +2 outside | for the lead ("For the lead", case 1) |
| R2 | remark on the checker, info | "confirms 134 of 295" against 133 trace edges | `dynamic/honcho.json` aliases: `<builtin>.dict.update` lists `collections.defaultdict.update`; the one trace edge `expand_processes -> <builtin>.dict.update` matches both graph edges (`environ.py:103`, `:114`) | 0 | none; the count is per graph edge |

No F (edge) finding and no W (wording) finding.

## Step 1: blind re-derivation

Skeleton made without the ledger, in
`/tmp/claude-501/-home-vitbot-pycg/gt-scratch/audit8-honcho/b8-audit-honcho/`:
363 sites, 359 `call`, 2 `decorator`, 2 `getattr`; 5 value sites; 119 with
candidates. Explicit sites dominate (361 of 363) and the implicit kind has
2 sites, so by the jsonpickle ruling ("a kind with fewer than 20 sites")
both implicit sites are taken and 68 explicit sites drawn with one
`random.Random(20261124)`; the 4 value sites that the draw missed are
added: 74 sites (`selection/batch-8-proposal/audits/honcho/`: `draw.py`,
`sample.txt`, `blind-answers.md`, commit `0e01eb5`).

| Sites | Agree | Disagree |
|---|---|---|
| 2 getattr (`command.py` 340:20, `environ.py` 26:24) | 2 | 0 |
| 67 explicit, not value sites | 67 | 0 |
| 5 value sites (1 drawn, 4 added) | 5 | 0 |

Every callee set and every rejection agrees, including the decisions that
rest on a judgement: `BaseExport.__init__` at the exporter value site
(J8), the six command functions at `COMMANDS[args.command](args)`, all
five `get_template_loader` at `base.py` 27:46 (J7), the rejection of
`_terminate` at `signal.signal` (J2), of `Process.run` at the
`multiprocessing.Process` constructor (J1), of `_parse_concurrency.<lambda1>`
at its `defaultdict`, and `io.TextIOWrapper.isatty` at `printer.py` 31:57
(J6). The blind answers also named the edges that J1, J2 and J4 put
outside the sample (`Manager._start -> Process.run` at `start()`,
`Manager.loop -> _terminate` at `events.get`, `supervisord.Export.render
-> dashrepl, percentescape` and `runit` `log/run` -> `dashrepl`); the
ledger has each at the same site.

Auditor premise that differs from the writer's, with no edge effect: I
admitted PyPy without a lower bound; `CHANGELOG.rst` 2.0.0 drops PyPy 3.7
and 3.8, so PyPy 3.9 and later (the writer's premise) is right.

## Step 2: exhaustive checks

**Dispatch sets.** Every method name that two package classes share,
with each site's receiver:

| Name | Classes | Sites and decision |
|---|---|---|
| `add_process` | `Procfile`, `Manager` | `command.py:252` Manager (made at 241), `environ.py:49` Procfile (made at 45); the other rejected. Correct |
| `terminate`, `kill` | `Manager`, `ProcessManager` | `manager.py:98`, `133`, `140` on `self` (Manager; no package subclass); `171`, `173` on `_procmgr` (ProcessManager, `manager.py:55`, assigned nowhere else); `compat.py:36` on `self` (ProcessManager). Correct |
| `write` | `Printer` | `manager.py:116`, `192` on `_printer` (Printer or a client printer, opaque); `command.py:390` on a text file: Printer rejected. Correct |
| `render` | `BaseExport` and the four `Export` | `command.py:125` on the exporter of the value site: the four overrides, `BaseExport.render` rejected (the package never makes a `BaseExport` there); the eleven `tpl.render(...)` sites: a `jinja2.Template`, `reject *`. Correct |
| `get_template` | `BaseExport` | the ten `self.get_template(...)` in the four `render`s (inherited); `base.py:37` on a `jinja2.Environment`, rejected. Correct |
| `get_template_loader` | `BaseExport` and the four `Export` | `base.py:27`: all five (J7) |
| `__init__` | eight classes | the `super(Popen, self).__init__` site rejects all (`subprocess.Popen.__init__`); every constructor call names its class's first `__init__`; `ProcessManager()`, `ProcessParams(...)`, `Message(...)` have none |

Roles: `_process_ctor`, `_child_ctor` and the two `_clock` are assigned only
in the package's `__init__`s (`manager.py:54`, `60`; `process.py:30`,
`32`); the tests' fakes change package internals. `export_choices` holds
honcho's four registered exporters (`pyproject.toml`). The printer and
output roles hold `Printer` and `sys.stdout`; client printers and streams
are opaque. Correct.

**Default rejections.** None in the ledger.

**Functions that no site calls.** `_parse_concurrency.<lambda1>` (no
missing-key lookup: `command.py:364` only stores, `environ.py:103` copies
with `update`) and `BaseExport.render` (the package never renders through
a plain `BaseExport`; its body keeps `<builtin>.NotImplementedError` by rule
A). Every other function has a caller. Correct.

**Special methods and properties.** The package defines no special method
but `__init__`. The two properties `Env.port` and `Env.procfile` are
loaded at the two getattr sites only (no other `.port` or `.procfile`
load); both accepted. The implicit sites without candidates (`--report
--without-candidates`, 701 sites) call no package code: no `map` or
`filter`; the three generator `render`s are iterated at `command.py:125`
(edges at the call); the `groupby` key lambdas are called while the same
`render` iterates the groupby (edges at `systemd.py:23`, `upstart.py:17`);
`expand_processes.<lambda1>` runs at `con[name]` in the function that
builds the dict (edge at `environ.py:101`). Correct.

**Rejections, exclusions and notes.** 27 rejection lines, no exclusion;
every reason checked against the source above. The notes on value sites,
receivers and versions are right; the `compiler.py:1764` and
`nodes.py:750-784` references of J4 and `loaders.py:315-316` hold in
Jinja2 3.1.4.

**Callees outside the package (103 names).** Each checked against the
sources:

- Jinja2: `jinja2/__init__.py:9-10`, `21`, `24` re-export `Environment`,
  `Template`, `FileSystemLoader`, `PackageLoader` (`X as X`), so the public
  paths stand. The filters run in `Template.render` (generated code calls
  `environment.filters[name]`); `Filter.as_const` evaluates the filtered
  node first, and every filtered node is an attribute of a context
  variable, so `get_template` calls no filter at compile time.
- `os._Environ` defines `copy` and not `get` or `update` in CPython 3.8 to
  3.15 and PyPy 3.11 (`os.py`): `os._Environ.copy`,
  `collections.abc.Mapping.get`, `collections.abc.MutableMapping.update`.
- `logging.Logger.warn` exists in CPython 3.8.20 to 3.15.2.
- `multiprocessing.Queue` is the default context's `Queue`
  (`context.py:101`), its result a `multiprocessing.queues.Queue`;
  `multiprocessing.Process` is `context.Process` (`context.py:227`, `238`).
- `ctypes.CDLL.__init__._FuncPtr.__call__` for `ctypes.windll.kernel32.*`
  (the mss ruling on `WinDLL`).
- `backports.entry_points_selectable.entry_points` (3.8, 3.9) and
  `colorama.init` (Windows) by their access paths; the real backport
  yields `importlib.metadata.EntryPoint` objects (it imports
  `importlib_metadata` only if present; its own requirement is for Python
  < 3.8), so `importlib.metadata.EntryPoint.load` is the only `load` name.
- `io.BufferedReader.close`: `Process.run` passes only `env` and `cwd`,
  so the pipe is binary with the default buffer.

**Trace edges.** 133 trace edges, 0 rejected, 20 client call-backs dropped
by the tracer. The 13 trace pairs whose callee is not literally in the
graph are aliases of graph names in the trace's alias table
(`argparse._ActionsContainer.add_argument`, `posixpath.join`,
`posix.getcwd`, `jinja2.loaders.PackageLoader`,
`multiprocessing.context.BaseContext.Queue`, `datetime.date.strftime`, and
others); `--report` lists no trace edge that no site accounts for.

## Step 3: binding check

All 123 site-callee pairs with a package callee (68 distinct edges),
matched by an `ast` script against the callees' signatures, and the
call-backs checked by hand: the `defaultdict` factory (no argument), the
`groupby` keys (one), the Jinja2 filters (one), `_terminate(signum,
frame)` (two, from the signal machinery), `Process.run` (`args=(self.events,
True)` against `run(self, events=None, ignore_signals=False)`). Every call
binds. The outside calls with package-built arguments (`subprocess.Popen`
with `stdout`, `stderr`, `shell`, `close_fds`, `env`, `cwd` and
`start_new_session` or `creationflags`; `multiprocessing.Process(name=,
target=, args=)`; `datetime.timedelta(seconds=)`) bind too. No edge goes.

## The writer's judgement calls

| J | Opinion | Nearest rule |
|---|---|---|
| J1 `Manager._start -> Process.run` at `start()` | agree: on Linux CPython 3.8 to 3.13 the default start method forks and the child runs the target inside `start()` | micro-benchmark "Callbacks" (a thread's target belongs to `start()`); README "Edges" (some admitted run) |
| J2 `Manager.loop -> _terminate` at `events.get(timeout=0.1)` | agree: the get blocks in a semaphore or `poll` wait, which a signal interrupts; the handler runs there (PEP 475 retry) | README "Implicit calls", the signal-handler clause (asciinema) |
| J3 versions and platforms | agree: CPython 3.8 and later, PyPy 3.9 and later (CHANGELOG), every platform (`OS Independent`) | "Versions and configuration"; the websocket-client platform-family ruling |
| J4 the package filters as call-backs of `Template.render` | agree, with the default templates only; a `--template-dir` template is client data | B5 (library code that dispatches to what the package's setup registers) |
| J5 both sides of the optional jinja2 import | agree | README "Judgements" (optional imports) |
| J6 `sys.stdout` stays `io.TextIOWrapper` on Windows | no rule decides; see "For the lead" | missing-module convention against "actual library behaviour" |
| J7 `BaseExport` as a receiver of its own `get_template_loader` | agree: a plain public class documented for subclassing | B1 |
| J8 the exporter value site, `EntryPoint.load` | agree | B2 (the package's own registration); the micro-benchmark rule on inherited `__init__` |

## For the lead

1. **J6: colorama's `init()` on Windows (2 outside edges, no inside
   edge).** colorama is a declared dependency on win32 and is absent from
   the Linux trace environment, so the writer treats it as a missing
   module whose stub `init()` leaves `sys.stdout` alone. The real
   `colorama.init()` (0.4.6, `initialise.py`) assigns `sys.stdout =
   wrap_stream(...)`, a `colorama.ansitowin32.StreamWrapper` when
   `should_wrap()` holds (for instance when stdout is not a terminal on
   Windows). `printer.py` runs `init()` at import, before
   `Manager.__init__` (`manager.py:57`), `command_start`
   (`command.py:241`) and `_check_output_encoding` (`command.py:400`) read
   `sys.stdout`; the default `output` of `Printer` is bound earlier and
   stays the interpreter's stream. So the question decides
   `Printer.__init__ -> colorama.ansitowin32.StreamWrapper.isatty`
   (`printer.py:31`) and `_check_output_encoding ->
   colorama.ansitowin32.StreamWrapper.isatty` (`command.py:400`).
   - For the writer: the missing-module convention models a missing
     library as a stub without effects, and "a missing library calls
     nothing back"; the wrapper has no access path from a stub expression.
   - For the edges: "the rule fixes names only: a branch that the
     library's answer decides still runs", and the websocket-client ruling
     uses "each admitted combination's actual library behaviour"; the
     wrapper's class has a public path in the library that a Windows
     install of honcho always has.
   - My opinion: the convention as written covers names, answers and
     call-backs, not a library's change of interpreter state; I lean to
     the two edges, but no rule decides it, so I do not rule. The case
     decides 2 outside edges and nothing inside the package.

## Re-check

Against `f8b2292` (`fix(b8-gt): honcho: colorama's StreamWrapper as Windows
stdout (J6, lead's ruling)`), compared with the audited `dc1795c`; the
commit touches only `honcho.ledger`, `honcho.json`, `honcho.added.json`
and `honcho.md`.

| Item | Check | State |
|---|---|---|
| J6, ruled by the lead (admit the two edges) | `printer.py` 31:57 `self.output.isatty()` and `command.py` 400:29 `sys.stdout.isatty()` each have `-> colorama.ansitowin32.StreamWrapper.isatty` beside `-> io.TextIOWrapper.isatty`, which stays; the two notes give colorama's `init()` at `printer.py:82` and `should_wrap()` | closed |
| The graph | `honcho.json` gains exactly `Printer.__init__ -> colorama.ansitowin32.StreamWrapper.isatty` and `_check_output_encoding -> colorama.ansitowin32.StreamWrapper.isatty`; `honcho.added.json` gains the same two edges with their sites and the two changed notes; no other line of the ledger, graph or added edges changed | closed |
| `honcho.md` | the status, J6 (the ruling quoted, the colorama 0.4.6 references `initialise.py:37`, `111-118`, `ansitowin32.py:49` hold), the outside-callee table and the statistics updated; R2 recorded as needing no change | closed |
| R1, R2 | R1 settled by the ruling; R2 needs no change | closed |
| Checks | `check.py honcho`: 297 edges (99 / 198), no errors; `check.py --origin honcho`: 133 trace edges, 0 rejected, traced 134 (28 / 106), added 163 (71 / 92), graph 297 (99 / 198) | closed |

Nothing is open: the audit is closed.
