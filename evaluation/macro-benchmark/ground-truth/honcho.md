# honcho: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write honcho`
and `check.py honcho` report no error; every site is decided; every trace
edge is in the graph, so there is no `honcho.rejected.json`. After the
blind audit, the lead's ruling on J6 (2026-11-24) added 2 outside edges
(295 to 297 edges). The auditor's R2 (one trace edge that matches two
graph edges through the alias table) needs no change (the lead).

Release v2.0.0 (commit `8af6317`). Analysed source: `honcho/` (root `.`;
15 modules, 70 functions with 4 lambdas, 14 classes). The checkout has no
`honcho/_version.py` (setuptools-scm writes it at build time);
`honcho/__init__.py` falls back to `0.0.0+unknown` and has no call either
way.

## Versions, implementations and platforms

`pyproject.toml` has no `requires-python`. Its classifiers name CPython 3.8
to 3.13, the implementations CPython and PyPy, and "Operating System :: OS
Independent". The CHANGELOG of 2.0.0 drops CPython 3.6 and 3.7 and PyPy 3.7
and 3.8 and adds PyPy 3.9 and 3.10; CI (`.github/workflows/main.yml`,
`tox.ini`) runs CPython 3.8 to 3.13 and PyPy 3.9 and 3.10 on
`ubuntu-latest`. By the README ("Versions and configuration": the final
classifier is not an upper bound; an explicit support drop counts per
implementation), the admitted runtimes are CPython 3.8 and later (3.8 to
3.15 in the deps) and PyPy 3.9 and later, on every platform (the
classifier declares independence; the pyfiglet and textdistance rulings
apply only to releases that are silent or restrict the platform).
Consequences:

| Site | Branch | Edges |
|---|---|---|
| `compat.py:13-43` | Windows: `ProcessManager.terminate` through `ctypes.windll.kernel32`, `kill` calls `terminate` | `ProcessManager.terminate -> ctypes.CDLL.__init__._FuncPtr.__call__`, `ProcessManager.kill -> ProcessManager.terminate` |
| `printer.py:72-82` | Windows: `colorama.init()`, or a `_colour_string` without calls if colorama is missing (both sides of the optional import run) | `honcho.printer -> colorama.init` |
| `process.py:75-81` | Windows: `creationflags`; elsewhere `start_new_session` | `<builtin>.dict.update` either way |
| `command.py:197-202` | Windows: the argv list; elsewhere `shlex.quote` | no edge of its own |
| `command.py:16-19` | 3.8, 3.9 (CPython and PyPy 3.9): `backports.entry_points_selectable.entry_points`; 3.10 and later: `importlib.metadata.entry_points` | `honcho.command -> backports.entry_points_selectable.entry_points` |

The two Windows `def`s of `compat.py` share the names of the POSIX ones:
one node each, with the union of the edges.

The `assert`s (`environ.py:39`, `manager.py:70`) test `in` on dicts and
call nothing, so `-O` changes no edge.

## Values, as the ledger uses them

- **Commands.** `main` parses `sys.argv` (or `argv`) with the module's
  parser; `args.command` is one of the six subparser names, and `COMMANDS`
  maps them to the six command functions (`command.py:318`). The options
  are strs (`type=str` or no type); `args.env`, `args.app_root`, `args.log`
  are strs.
- **Configuration.** `map_from` builds a `ChainMap` of three dicts and
  `DEFAULTS`; `Env` wraps it. `Env.port` converts the str of the port;
  `Env.procfile` joins two strs. `_read_env` and `Env.load_procfile` read
  text-mode files (`io.TextIOWrapper.read`). `environ.parse` returns a
  dict.
- **Processes.** `Procfile.processes` is an `OrderedDict`;
  `expand_processes` returns `ProcessParams` namedtuples whose `env` is a
  dict. The concurrency map of `_parse_concurrency` is a `defaultdict`
  that `expand_processes` copies with `update`.
- **Manager internals.** `Manager._process_ctor` is `Process`,
  `_procmgr` a `ProcessManager`, `_clock` `datetime.datetime`, `events` a
  `multiprocessing.Queue()` (a `multiprocessing.queues.Queue`), `_colours`
  the generator of `get_colours`. `Process._child_ctor` is
  `honcho.process.Popen` and `Process._clock` `datetime.datetime`. Nothing
  in the package reassigns these private attributes; the tests do
  (`FakePopen`, `FakeClock`, `FakeProcessManager`), which is a change of
  package internals, and the tracer dropped those calls as client
  callbacks (20).
- **Printers.** The package passes `Printer(sys.stdout, ...)` to `Manager`
  (`command.py:241`) or makes `Printer(sys.stdout)` itself
  (`manager.py:57`); a client printer is opaque. The package's messages
  are `Message` namedtuples with a `datetime.datetime` time, a str name
  and bytes (`Process.run`) or str (`_system_print`) data.
- **The child's pipe.** `Popen` gets only `env` and `cwd` from `Process.run`
  besides its own `stdout=PIPE`, `stderr=STDOUT`, so `_child.stdout` is an
  `io.BufferedReader`.
- **Exporters.** `export_choices` holds the entry points of the group
  `honcho_exporters`; honcho's distribution registers the four `Export`
  classes (runit, supervisord, systemd, upstart), each of which inherits
  `BaseExport.__init__` and overrides `get_template_loader` and `render`. A
  plugin's exporter is client code (`doc/export.rst`). `_template_env` is
  the `jinja2.Environment` of `_default_template_env`, whose
  `get_template` returns a `jinja2.Template`; a client `template_env`
  (`BaseExport(template_env=...)`) is opaque.

## Default rejections

None.

## Judgement calls

**J1. `Manager._start -> Process.run` (1 inside edge).** `_start` makes a
`multiprocessing.Process` whose target is `p['obj'].run`, the bound `run`
of the `honcho.process.Process` of `add_process`, and `start()` runs it in
the child that it forks (the default start method on Linux up to 3.13;
the forked child runs the target inside `start()`). By the callback rule
the target belongs to the scope that calls `start()` (`manager.py:180`),
as in the asciinema and Sublist3r precedents. The constructor site
(`manager.py:177`) rejects `Process.run`: it only stores it. The trace
lacks the edge: the five tests that call `loop` are deselected (Python
3.14's forkserver cannot pickle their local function), and a child is
not traced anyway. Alternative: no edge, if code that a child process
runs were not counted; the precedents count it.

**J2. The signal handler `Manager.loop._terminate` (1 inside edge).**
`loop` installs `_terminate` for SIGTERM and SIGINT (`manager.py:100-101`)
and then blocks in `self.events.get(timeout=0.1)` (`manager.py:110`),
where it spends its time while the handler is installed; a signal there
interrupts the wait, and the interpreter runs the Python handler
(`PyErr_CheckSignals` on `EINTR`) before the wait retries. By the README
("Implicit calls": a handler is a callee only of the package call where
the package waits for the signal while it is installed; asciinema's
`select.select`), the edge is at `110:38`; `signal.signal` only stores it,
and a signal at another point is no edge. Alternative: no edge, if a
polling `get` with a timeout were not a wait for the signal; the loop
exists to wait for its children and for these two signals.

**J3. Versions and platforms (4 edges, 1 inside).** See the table above.

**J4. Jinja2 filters of the package's templates (2 inside edges).**
`_default_template_env` registers `dashrepl` and `percentescape` as
filters. Jinja2 compiles a template into Python code that calls a
filter during `Template.render` (Jinja2 3.1.4,
`src/jinja2/compiler.py:1764`, `visit_Filter`; constant folding,
`nodes.py:750-784`, does not apply, because every filtered value is an
attribute of a context variable). That generated code is library code, so
the filters are callbacks of the package's `render` call:
`templates/runit/log/run` applies `dashrepl` (`runit.py:38`, an edge that
`runit.py:25` already gives), and `templates/supervisord/supervisord.conf`
applies `dashrepl` and `percentescape` (`supervisord.py:14`: the two new
edges). The systemd and upstart templates apply only `shellquote`, which
is `shlex.quote`. The other calls of the generated code (`dict.items` on
`process.env`, `shlex.quote`) are library calls of library code: no
edge. Templates from `--template-dir` are the client's: their filter
calls are client behaviour (B5). Read from the sdist
`jinja2-3.1.4.tar.gz` (SHA-256
`4a3aee7acbbe7303aede8e9648d13b8bf88a429282aa6122a993f0ac800cb369`,
`deps/pypi/Jinja2-3.1.4`), never run.

**J5. The optional import of jinja2 (2 outside edges).**
`export/base.py:5-15` prints a message and exits when jinja2, the extra
`export`, is missing. Both sides of an optional import run (README,
"Judgements"): `honcho.export.base -> <builtin>.print` and `-> sys.exit`.

**J6. Standard streams and colorama (2 outside edges; ruling of the
lead, 2026-11-24, after the blind auditor's opinion).** `Printer.__init__`
calls `self.output.isatty()` (`printer.py:31`) and
`_check_output_encoding` calls `sys.stdout.isatty()` (`command.py:400`);
the package's output is `sys.stdout`, named `io.TextIOWrapper` (README,
"Callees outside the package"). On Windows, colorama, a declared
dependency there, runs `colorama.init()` at the import of `printer.py`
(line 82); colorama 0.4.6's `init` replaces `sys.stdout` with a
`colorama.ansitowin32.StreamWrapper` when `should_wrap()` holds
(`colorama/initialise.py:37-56` and `wrap_stream`, lines 111-118;
`StreamWrapper.isatty`, `ansitowin32.py:49`; read in
`deps/pypi/colorama-0.4.6`, never run). The writer's first version
treated the missing-module stub as inert and kept `io.TextIOWrapper.isatty`
only. The lead ruled: "The missing-module convention fixes how a missing
library's callees are named; it does not make the library inert: its
actual behaviour decides (as in the websocket-client and einops
rulings)." Both sites run after that import (the `Printer(sys.stdout)`
calls of `manager.py:57` and `command.py:241`, and `main`), so both keep
`io.TextIOWrapper.isatty` (other platforms, or a console that needs no
wrapping) and add `colorama.ansitowin32.StreamWrapper.isatty`. The
default `output` of `Printer` (line 17) is bound before line 82 runs; a
call that relies on it reaches `io.TextIOWrapper` only, which adds no
other name.

**J7. `BaseExport` as a receiver of its own `get_template_loader` (1
inside edge).** `BaseExport` is a plain public class that the
documentation gives for subclassing (`doc/export.rst`, "Adding support
for new export formats"); by B1 it is a receiver of its own methods. So
`BaseExport.__init__ -> BaseExport.get_template_loader`
(`base.py:27`), which raises `NotImplementedError`; the four package
exporters give the other four callees. `BaseExport.render` is never
called by the package: `command_export` calls `render` on one of the
four registered exporters, each of which overrides it.

**J8. Entry points.** `export_choices[args.format].load()` is
`importlib.metadata.EntryPoint.load` (3.10 and later). On 3.8 and 3.9 the
`backports` stub's result iterates no items, so the dict is empty there;
the real backport would give `importlib.metadata.EntryPoint` objects
too, so the names are the same. `export_ctor(...)` (`command.py:113`) is
a value site: `BaseExport.__init__`, inherited by all four exporters.

## Callees outside the package

| Callee | How it is named |
|---|---|
| `jinja2.Environment`, `.get_template`, `jinja2.FileSystemLoader`, `jinja2.PackageLoader`, `jinja2.Template.render` | Jinja2 is installed; public paths of `jinja2/__init__.py` (bottle precedent) |
| `colorama.init`, `backports.entry_points_selectable.entry_points` | missing modules: access paths |
| `os._Environ.copy`; `collections.abc.Mapping.get`, `collections.abc.MutableMapping.update` | `os.environ` defines `copy` and inherits `get` and `update` (asciinema, anytree, bottle precedents) |
| `subprocess.Popen.__init__`, `subprocess.Popen.wait` | `honcho.process.Popen` inherits them (`super(Popen, self).__init__`) |
| `io.BufferedReader.close` | the binary pipe of `Popen` |
| `io.TextIOWrapper.read`, `.write`, `.isatty` | text-mode `open()`, and `sys.stdout` |
| `colorama.ansitowin32.StreamWrapper.isatty` | `sys.stdout` after `colorama.init()` on Windows (J6) |
| `multiprocessing.Queue`, `multiprocessing.queues.Queue.get`, `.put`, `multiprocessing.Process`, `multiprocessing.Process.start` | the module function and the classes of its results (Sublist3r, asciinema) |
| `argparse.ArgumentParser.add_argument`, `.add_subparsers`, `.parse_args`, `argparse._SubParsersAction.add_parser` | by the receiver's class, private classes too (argcomplete) |
| `ctypes.CDLL.__init__._FuncPtr.__call__` | Windows `kernel32` functions (Sublist3r, segno) |
| `datetime.datetime.now`, `datetime.datetime.strftime`, `datetime.timedelta` | by the receiver's class; the trace's canonical `datetime.date.strftime` has this alias |
| `collections.defaultdict.update`, `collections.OrderedDict.items` | by the receiver's class |
| `logging.Logger.info`, `.error`, `.warn` | `logging.getLogger(__name__)`; `warn` exists in CPython 3.8 to 3.15 |
| `<builtin>.Exception.__init__` | `CommandError(...)`: the first `__init__` of its MRO |
| `importlib.metadata.EntryPoint.load` | J8 |

A call of the namedtuple classes `ProcessParams` and `Message`
(`environ.py:118`, `manager.py:192`, `process.py:56`) and of
`ProcessManager()` (`manager.py:55`, `object.__init__`) has no callee.

## Open path sets

None.

## Rejected trace edges

None: every edge of the trace is in the graph.

## Notes for the auditor

- `_parse_concurrency.<lambda1>` is never called: nothing looks up a
  missing key of that defaultdict (`expand_processes` copies it with
  `update`, which reads the stored pairs on CPython and PyPy). By contrast
  `expand_processes.<lambda1>` runs at `con[name]` (`environ.py:108`); the
  edge is written at the `defaultdict` call (`environ.py:101`), in the
  same function.
- The lambdas of `systemd.py:23` and `upstart.py:17` are called by
  `itertools.groupby` as the same function iterates it; the edges are at
  the `groupby` calls.
- `ProcessManager()` has no `__init__`; its two methods are reached only
  through `Manager._killall` and the Windows `kill`.
- The documentation's example exporter calls `get_template('run.sh')`
  without `self.` (`doc/export.rst:53`): a bug of the example, client
  code.
- `Manager._killall` reads `p['pid']`, which a process has only after its
  start message: a `KeyError` before that removes no edge.
- `PackageLoader(__name__, ...)` gets a module name, not a package; Jinja2
  3.1.4 uses the module's directory (`loaders.py:315-316`).
- The trace confirms 134 of 297 edges: the deselected integration tests,
  the deselected `loop` tests and the fakes that replace private
  attributes leave `command.py` (beyond module code), `Manager.loop`'s
  signal and kill paths, `Process`'s real `Popen`, and every Jinja2 render
  unexercised.

## Statistics

`check.py honcho`:

```
honcho: 15 modules, 70 functions (4 lambdas), 14 classes, 359 calls
  sites: 363 (359 call, 2 decorator, 2 getattr); 119 with candidates (179 candidates); 5 value sites
  ground truth: 297 edges (99 internal, 198 outside)
  trace: 133 edges; confirms 134 of 297 ground-truth edges (45.1%); 41 of 70 functions run (58.6%); 0 rejected
honcho: no errors
```

`check.py --origin honcho`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| honcho | 133 | 0 | 134 (28 / 106) | 163 (71 / 92) | 297 (99 / 198) |
