# honcho: blind answers (74 sites, seed 20261124)

Written from the source of honcho v2.0.0 (`8af6317`), the dependency
sources of `deps/` (Jinja2 3.1.4, backports.entry-points-selectable 1.3.0,
CPython `Lib/`) and the README's rules only, before any file of the
writer was opened. The trace was not read.

## The draw

1. Skeleton made without a ledger in a scratch copy (`check.py
   --benchmark-dir <scratch> --skeleton honcho`): 363 sites, 359 `call`,
   2 `decorator`, 2 `getattr`; 5 value sites.
2. `draw.py <skeleton>`: sites numbered by (module in skeleton order,
   line, column); explicit sites dominate (361 of 363), and the implicit
   kind has fewer than 20 sites, so by the jsonpickle ruling ("The blind
   draw where a kind has fewer than 20 sites") both implicit sites are
   taken and 68 explicit sites drawn with one `random.Random(20261124)`
   (`rng.sample`); then the 4 value sites that the draw did not take are
   added: 74 sites (`sample.txt`).

## Premises

| What | Decision | Evidence |
|---|---|---|
| Python versions | CPython 3.8 to 3.13 by the classifiers; no `requires-python`, and the last classifier is no upper bound, so 3.14 (the trace's) and later count too | `pyproject.toml` |
| Implementations | CPython and PyPy (classifier; tox `pypy39`, `pypy310`; CI `pypy3.9`, `pypy3.10`) | `pyproject.toml`, `tox.ini`, `.github/workflows/main.yml` |
| Platforms | `Operating System :: OS Independent`: Linux, macOS and Windows; both sides of every `ON_WINDOWS` branch run | `pyproject.toml`; `compat.py:13-43`, `printer.py:72-82`, `process.py:75-81`, `command.py:197-202` |
| `entry_points` | `backports.entry_points_selectable.entry_points` on 3.8 and 3.9 (declared dependency), `importlib.metadata.entry_points` from 3.10 | `command.py:16-19`, `pyproject.toml` |
| Exporters | an installed honcho registers its four `Export` classes in `honcho_exporters`; plugins of other distributions are client code | `pyproject.toml` `[project.entry-points.honcho_exporters]`; `doc/export.rst` |
| Jinja2 | `jinja2>=3.1.2,<4` (extra `export`); `jinja2/__init__.py` re-exports `Environment` and `Template` (`X as X`), so `jinja2.Environment.get_template`, `jinja2.Template.render` | `Jinja2-3.1.4/src/jinja2/__init__.py:9-10` |
| Templates | the package's templates use the package filters `dashrepl` (`runit/log/run`, `supervisord.conf`) and `percentescape` (`supervisord.conf`); a template of a client `template_dir` is client data, and nothing documents or tests a package filter in one, so it adds no call-back (B3, as for a client-supplied attribute name) | `export/templates/`; `doc/export.rst` |
| Private attributes | `_process_ctor`, `_child_ctor`, `_clock` are assigned only in the package's `__init__`s (the tests' replacements change package internals: not considered) | `manager.py:54,60`, `process.py:30,32` |

## Answers

Notation: `->` a callee; `reject` a candidate with its reason.

1. `honcho.__main__` [`honcho.__main__`] 4:9 call `main()`
   -> `honcho.command.main` (the `__main__` block runs).
2. `honcho.colour` [`honcho.colour`] 12:25 call `enumerate(ANSI_COLOURS)`
   -> `<builtin>.enumerate`.
14. `honcho.command` [`honcho.command`] 38:56 call `entry_points(group=...)`
    -> `importlib.metadata.entry_points` (3.10 and later),
    -> `backports.entry_points_selectable.entry_points` (3.8, 3.9; the
    version branch at 16-19 runs on both sides).
16. `honcho.command` [`honcho.command._add_common_args`] 51:24 call
    `parser.add_argument('-d', ...)`
    -> `argparse.ArgumentParser.add_argument` (the package passes the main
    parser and parsers made by `add_parser`, whose `parser_class` is
    `type(self)`, `ArgumentParser`).
23. `honcho.command` [`honcho.command`] 77:35 call `parser.add_subparsers(...)`
    -> `argparse.ArgumentParser.add_subparsers`.
30. `honcho.command` [`honcho.command`] 89:37 call `subparsers.add_parser('check', ...)`
    -> `argparse._SubParsersAction.add_parser` (asciinema precedent).
38. `honcho.command` [`honcho.command.command_export`] 105:17 call `_port(env)`
    -> `honcho.command._port`.
39. `honcho.command` [`honcho.command.command_export`] 107:41 call
    `environ.expand_processes(...)`
    -> `honcho.environ.expand_processes`.
41. (value) `honcho.command` [`honcho.command.command_export`] 113:25 call
    `export_ctor(template_dir=args.template_dir)`
    -> `honcho.export.base.BaseExport.__init__`.
    Note: `export_ctor` is `export_choices[args.format].load()`; the
    argument parser limits `format` to the keys of `export_choices`, the
    `honcho_exporters` entry points; honcho's own distribution registers
    the four `Export` classes (runit, supervisord, systemd, upstart), none
    of which defines `__init__`: the first `__init__` of their MRO is
    `BaseExport.__init__`, which binds `template_dir=`. A plugin of
    another distribution is client code. No outside callee (`object`
    `__new__`, no metaclass).
64. `honcho.command` [`honcho.command`] 182:36 call `subparsers.add_parser('help', ...)`
    -> `argparse._SubParsersAction.add_parser`.
71. `honcho.command` [`honcho.command.command_run`] 206:18 call
    `signal.signal(signal.SIGINT, signal.SIG_IGN)`
    -> `signal.signal`.
72. `honcho.command` [`honcho.command.command_run`] 207:11 call `p.wait()`
    -> `subprocess.Popen.wait` (`p` is a `honcho.process.Popen`, which
    inherits `wait`; named through the nearest outside base).
73. `honcho.command` [`honcho.command.command_run`] 208:13 call `sys.exit(p.returncode)`
    -> `sys.exit`.
78. `honcho.command` [`honcho.command.command_start`] 223:14 call `Env(config)`
    -> `honcho.environ.Env.__init__`.
84. `honcho.command` [`honcho.command.command_start`] 232:32 call `OrderedDict()`
    -> `collections.OrderedDict`.
89. `honcho.command` [`honcho.command.command_start`] 245:38 call
    `environ.expand_processes(...)`
    -> `honcho.environ.expand_processes`.
93. `honcho.command` [`honcho.command.command_start`] 254:17 call `manager.loop()`
    -> `honcho.manager.Manager.loop`.
99. `honcho.command` [`honcho.command`] 270:26 call `parser_start.add_argument('-q', ...)`
    -> `argparse.ArgumentParser.add_argument`.
103. `honcho.command` [`honcho.command`] 285:39 call `subparsers.add_parser('version', ...)`
     -> `argparse._SubParsersAction.add_parser`.
108. `honcho.command` [`honcho.command.map_from`] 304:24 call `_compact({...})`
     -> `honcho.command._compact`.
117. (value) `honcho.command` [`honcho.command.main`] 318:31 call
     `COMMANDS[args.command](args)`
     -> `honcho.command.command_check`, `honcho.command.command_export`,
     `honcho.command.command_help`, `honcho.command.command_run`,
     `honcho.command.command_start`, `honcho.command.command_version`.
     Note: `COMMANDS` (290-297) maps the six sub-command names to these
     functions; `dest='command'` with `required = True` makes
     `args.command` one of the six names of `add_parser`; each takes one
     argument. No outside callee.
126. `honcho.command` [`honcho.command._port`] 340:20 getattr `env.port`
     -> `honcho.environ.Env.port` (the package passes an `Env`, 105, 229).
128. `honcho.command` [`honcho.command._port`] 342:31 call `str(e)`
     -> `<builtin>.str` (`e` is the `ValueError` that `Env.port` raises).
130. `honcho.command` [`honcho.command._read_env`] 346:42 call `env.split(',')`
     -> `<builtin>.str.split` (private; callers pass `args.env`, a string
     of argparse, default `'.env'`).
132. `honcho.command` [`honcho.command._read_env`] 350:35 call
     `os.path.join(app_root, envfile)`
     -> `os.path.join`.
134. `honcho.command` [`honcho.command._read_env`] 351:38 call `f.read()`
     -> `io.TextIOWrapper.read` (`open()` in text mode).
137. `honcho.command` [`honcho.command._parse_concurrency`] 359:25 call
     `defaultdict(lambda: 1)`
     -> `collections.defaultdict`.
     reject `honcho.command._parse_concurrency.<lambda1>`: the constructor
     only stores the factory; `result` is only assigned to (364) and
     copied by `con.update(concurrency)` (`environ.py:103`), so no lookup
     of a missing key calls it.
139. `honcho.command` [`honcho.command._parse_concurrency`] 363:38 call
     `item.split('=', 1)`
     -> `<builtin>.str.split` (`desc` is `args.concurrency`, `type=str`).
147. `honcho.command` [`honcho.command._write_file`] 387:27 call `os.path.dirname(path)`
     -> `os.path.dirname`.
151. `honcho.command` [`honcho.command._write_file`] 393:27 call `CommandError(e)`
     -> `<builtin>.Exception.__init__` (`CommandError` defines no
     `__init__`; reached when `open(path, 'w')` or `write` raises).
156. `honcho.command` [`honcho.command`] 410:9 call `main()`
     -> `honcho.command.main` (the `__main__` block is module code).
164. `honcho.compat` [`honcho.compat.ProcessManager.kill`] 40:26 call
     `os.killpg(pid, signal.SIGKILL)`
     -> `os.killpg` (the non-Windows `kill`).
167. `honcho.environ` [`honcho.environ.Env.port`] 17:23 call `int(self._c['port'])`
     -> `<builtin>.int`.
172. `honcho.environ` [`honcho.environ.Env.load_procfile`] 26:24 getattr `self.procfile`
     -> `honcho.environ.Env.procfile`.
174. `honcho.environ` [`honcho.environ.Env.load_procfile`] 29:30 call
     `parse_procfile(content)`
     -> `honcho.environ.parse_procfile`.
183. `honcho.environ` [`honcho.environ.parse`] 60:28 call `shlex.shlex(line, posix=True)`
     -> `shlex.shlex`.
189. `honcho.environ` [`honcho.environ.parse`] 76:30 call `value.replace(r'\t', '\t')`
     -> `<builtin>.str.replace` (`value` is `''.join(...)`).
201. (value) `honcho.environ` [`honcho.environ.expand_processes`] 118:35 call
     `ProcessParams(n, c, q, e)`
     no callee. Note: `ProcessParams` is a `collections.namedtuple` class
     (82): generated `__new__`, `object.__init__`; no edge.
206. `honcho.export.base` [`honcho.export.base.BaseExport.__init__`] 27:46 call
     `self.get_template_loader()`
     -> `honcho.export.base.BaseExport.get_template_loader` (a client can
     make a plain `BaseExport()`: a documented base class, not abstract;
     the call raises `NotImplementedError` in the body),
     -> `honcho.export.runit.Export.get_template_loader`,
     -> `honcho.export.supervisord.Export.get_template_loader`,
     -> `honcho.export.systemd.Export.get_template_loader`,
     -> `honcho.export.upstart.Export.get_template_loader`
     (the four public subclasses, made without `template_dir` and
     `template_env`).
208. `honcho.export.base` [`honcho.export.base.BaseExport.get_template`] 37:47 call
     `self._template_env.get_template(path)`
     -> `jinja2.Environment.get_template` (`_default_template_env`
     returns a `jinja2.Environment`; a client `template_env` is opaque).
     reject `honcho.export.base.BaseExport.get_template`: the receiver is a
     Jinja2 environment. No package call-back: the loaders are Jinja2's,
     and no package template applies a filter to a constant (no folding at
     compile time).
209. `honcho.export.base` [`honcho.export.base.BaseExport.get_template_loader`]
     40:34 call `NotImplementedError(...)`
     -> `<builtin>.NotImplementedError`.
220. `honcho.export.runit` [`honcho.export.runit.Export.render`] 25:36 call
     `'{0}-{1}'.format(ctx['app'], dashrepl(p.name))`
     -> `<builtin>.str.format`.
221. `honcho.export.runit` [`honcho.export.runit.Export.render`] 25:57 call
     `dashrepl(p.name)`
     -> `honcho.export.base.dashrepl`.
227. `honcho.export.runit` [`honcho.export.runit.Export.render`] 33:38 call
     `run_tpl.render(ctx)`
     -> `jinja2.Template.render`.
     reject `honcho.export.base.BaseExport.render`,
     `honcho.export.runit.Export.render`,
     `honcho.export.supervisord.Export.render`,
     `honcho.export.systemd.Export.render`,
     `honcho.export.upstart.Export.render`: the receiver is the
     `jinja2.Template` that `get_template('run')` returns. The template
     `runit/run` uses no package filter: no call-back.
233. `honcho.export.supervisord` [`honcho.export.supervisord.Export.render`] 13:37
     call `self.get_template('supervisord.conf')`
     -> `honcho.export.base.BaseExport.get_template` (inherited).
234. `honcho.export.supervisord` [`honcho.export.supervisord.Export.render`] 14:21
     call `File(filename, template.render(context))`
     -> `honcho.export.base.File.__init__`.
241. `honcho.export.systemd` [`honcho.export.systemd.Export.render.<lambda1>`]
     23:73 call `proc.name.split(".")`
     -> `<builtin>.str.split` (the package's processes are
     `ProcessParams` whose `name` is a `str` from `expand_processes`;
     a client's objects are opaque).
242. `honcho.export.systemd` [`honcho.export.systemd.Export.render`] 25:22 call
     `"-".join([app_name, group_name])`
     -> `<builtin>.str.join`.
248. `honcho.export.systemd` [`honcho.export.systemd.Export.render`] 32:39 call
     `"{0}.target".format(app_name)`
     -> `<builtin>.str.format`.
253. `honcho.export.systemd` [`honcho.export.systemd.Export.render`] 38:43 call
     `"{0}.target".format(process_master_name)`
     -> `<builtin>.str.format`.
254. `honcho.export.systemd` [`honcho.export.systemd.Export.render`] 38:91 call
     `process_master_tpl.render(context)`
     -> `jinja2.Template.render`.
     reject the five package `render` methods: the receiver is a
     `jinja2.Template`. `systemd/process_master.target` uses no package
     filter.
261. `honcho.export.upstart` [`honcho.export.upstart.Export.render`] 15:40 call
     `self.get_template('process.conf')`
     -> `honcho.export.base.BaseExport.get_template`.
266. `honcho.export.upstart` [`honcho.export.upstart.Export.render`] 20:45 call
     `master_tpl.render(context)`
     -> `jinja2.Template.render`.
     reject the five package `render` methods: the receiver is a
     `jinja2.Template`. `upstart/master.conf` has no expression.
267. `honcho.export.upstart` [`honcho.export.upstart.Export.render`] 23:42 call
     `"{0}-{1}".format(context['app'], name)`
     -> `<builtin>.str.format`.
273. `honcho.export.upstart` [`honcho.export.upstart.Export.render`] 32:35 call
     `context.copy()`
     -> `<builtin>.dict.copy` (the package passes a dict,
     `command.py:115`; a client's context is opaque).
280. `honcho.manager` [`honcho.manager.Manager.__init__`] 53:36 call `get_colours()`
     -> `honcho.colour.get_colours` (a generator function: a callee).
283. `honcho.manager` [`honcho.manager.Manager.__init__`] 58:34 call
     `len(SYSTEM_PRINTER_NAME)`
     -> `<builtin>.len`.
284. (value) `honcho.manager` [`honcho.manager.Manager.add_process`] 71:34 call
     `self._process_ctor(cmd, name=..., quiet=..., colour=..., env=..., cwd=...)`
     -> `honcho.process.Process.__init__`.
     Note: `_process_ctor` is `Process` (60), assigned nowhere else in the
     package; the call binds `Process.__init__`.
290. `honcho.manager` [`honcho.manager.Manager.loop`] 100:22 call
     `signal.signal(signal.SIGTERM, _terminate)`
     -> `signal.signal`.
     reject `honcho.manager.Manager.loop._terminate`: `signal.signal` only
     stores the handler; it runs at the call where `loop` waits, the
     blocking `self.events.get(timeout=0.1)` (110:31; README "Implicit
     calls", asciinema).
294. `honcho.manager` [`honcho.manager.Manager.loop`] 116:40 call
     `self._printer.write(msg)`
     -> `honcho.printer.Printer.write` (the default `Printer(sys.stdout)`
     and the `Printer` of `command_start`; a client printer is opaque).
297. `honcho.manager` [`honcho.manager.Manager.loop`] 128:33 call `self._all_started()`
     -> `honcho.manager.Manager._all_started`.
301. `honcho.manager` [`honcho.manager.Manager.loop`] 132:45 call `self._clock.now()`
     -> `datetime.datetime.now`.
304. `honcho.manager` [`honcho.manager.Manager.loop`] 139:48 call
     `datetime.timedelta(seconds=KILL_WAIT)`
     -> `datetime.timedelta`.
313. `honcho.manager` [`honcho.manager.Manager._start`] 176:45 call
     `self._processes.items()`
     -> `<builtin>.dict.items`.
314. `honcho.manager` [`honcho.manager.Manager._start`] 177:51 call
     `multiprocessing.Process(name=..., target=p['obj'].run, args=...)`
     -> `multiprocessing.Process`.
     reject `honcho.process.Process.__init__`: the class called is
     multiprocessing's `Process`, not the package's.
     reject `honcho.process.Process.run`: the constructor only stores the
     target; it runs at `p['process'].start()` (180:30), the caller of the
     call-back (micro-benchmark: a thread's target belongs to `start()`).
329. `honcho.printer` [`honcho.printer.Printer.__init__`] 31:57 call
     `self.output.isatty()`
     -> `io.TextIOWrapper.isatty` (the default `sys.stdout`, and the
     package's `Printer(sys.stdout)` in `manager.py:57`,
     `command.py:241`; a client stream is opaque).
331. `honcho.printer` [`honcho.printer.Printer.write`] 42:26 call
     `name.ljust(self.width)`
     -> `<builtin>.str.ljust`.
332. `honcho.printer` [`honcho.printer.Printer.write`] 49:22 call
     `isinstance(message.data, bytes)`
     -> `<builtin>.isinstance`.
338. `honcho.printer` [`honcho.printer.Printer.write`] 61:18 call
     `print(prefix + line, file=self.output, flush=True)`
     -> `<builtin>.print`.
346. (value) `honcho.process` [`honcho.process.Process.run`] 36:39 call
     `self._child_ctor(self.cmd, env=self.env, cwd=self.cwd)`
     -> `honcho.process.Popen.__init__`.
     Note: `_child_ctor` is `Popen` (32), assigned nowhere else in the
     package; `Popen.__init__(self, cmd, **kwargs)` binds.
347. `honcho.process` [`honcho.process.Process.run`] 37:27 call
     `self._send_message({...}, type='start')`
     -> `honcho.process.Process._send_message`.
348. `honcho.process` [`honcho.process.Process.run`] 43:26 call
     `signal.signal(signal.SIGINT, signal.SIG_IGN)`
     -> `signal.signal`.
357. `honcho.process` [`honcho.process.Process._send_message`] 58:58 call
     `self._clock.now()`
     -> `datetime.datetime.now`.
363. `honcho.process` [`honcho.process.Popen.__init__`] 83:36 call
     `super(Popen, self).__init__(cmd, **options)`
     -> `subprocess.Popen.__init__`.
     reject `honcho.environ.Env.__init__`,
     `honcho.environ.Procfile.__init__`,
     `honcho.export.base.BaseExport.__init__`,
     `honcho.export.base.File.__init__`,
     `honcho.manager.Manager.__init__`,
     `honcho.printer.Printer.__init__`, `honcho.process.Popen.__init__`,
     `honcho.process.Process.__init__`: `super(Popen, self)` resolves to
     `subprocess.Popen`. `honcho.process.Popen` overrides no method that
     `subprocess.Popen.__init__` calls: no call-back.

## Edges outside this sample that the answers imply

For the comparison after the blind commit, not counted in the sample:
`Manager.loop -> Manager.loop._terminate` at 110:31 (the blocking
`events.get`); `Manager._start -> honcho.process.Process.run` at 180:30
(`start()`); the render sites of `runit/log/run` (`runit.py:38`) and
`supervisord.conf` (`supervisord.py:14`) call back
`honcho.export.base.dashrepl`, and the latter also
`honcho.export.base.percentescape`.
