# nodeenv: judgements of the ground truth

Status: complete (2026-11-24); the audit (`nodeenv.audit.md`, 134 of 134
sites agree) and the lead's ruling on its finding F1 are applied (J1,
+2 inside edges). Every site is decided;
`check.py --write nodeenv`, `check.py nodeenv` and `check.py --origin
nodeenv` report no error. Every call of a package function was checked to
bind its arguments.

Release 1.12.0 (commit `cb7fc97`). Analysed source: the module file
`nodeenv.py` (root `.`), 66 functions (2 lambdas), 2 classes. Lines
1799-2400 are shell, batch and PowerShell templates (strings), with no
call.

The trace (`dynamic/nodeenv.json`, CPython 3.14.10 on Linux): 400
passed, 20 failed (declared: the container's noexec `/tmp`, see
`repeatability/declared.json`), 98 skipped, 12 deselected. What those tests would call after the
script or the fake npm runs is in child processes (shells, npm), which are
untraced and run no package code; the calls of the package before the
failure are in the trace. Every other untraced edge comes from reading.

Scratch drafting: the entries were written by hand in a table keyed by
site and merged into the skeleton by a script of the writer; the 34
`parser.add_argument(...)` sites of `make_parser` got
`argparse.ArgumentParser.add_argument` from the site text. Every entry was
reviewed against the source.

## Supported versions, implementations and platforms

- `setup.py`: `python_requires='>=3.10'`, classifiers Python 3.10 to 3.14
  and `Implementation :: CPython` only. So CPython 3.10 and later; 3.15
  is admitted (the final classifier is no upper bound) and changes no
  name used here (`re.match` is an alias of `re.prefixmatch` there; the
  ledger keeps the access path `re.match`). PyPy is not admitted.
- Platforms: the CI runs the tests on `ubuntu-latest`, `macos-latest` and
  `windows-latest` (`.github/workflows/tests.yml`); `README.rst:443` and
  CHANGES name Cygwin and MSYS ("Support for Cygwin #194", "Added support
  for MSYS2 #263"), and CHANGES "Added support for Solaris/illumos" and
  FreeBSD's architecture name. `setup.py` says `platforms='any'`. So the
  module constants `is_WIN` and `is_CYGWIN` (lines 48-49) take both values,
  and every branch on them runs (J4).
- Version branches: `sys.version_info >= (3, 12)` at lines 993 and 1334
  takes both sides (`extractall(..., filter="data")` from 3.12).
  `urllib.parse.urlsplit` is an `lru_cache` wrapper from 3.11 (J5).
- Optional imports: `shtab` (extra `completion`, `shtab>=1.11`;
  installed in the trace) and `certifi` (extra `certifi`; not installed,
  a missing module): both sides of each `try: import` run (J9).

## Values, as the ledger uses them

- `logger` (line 424) is the `logging.Logger` named "nodeenv" that
  `create_logger` makes: level INFO, one `logging.StreamHandler` (`ch`) on
  the `sys.stderr` of import time, and `logging.StreamHandler.emit`
  replaced by the local function `create_logger.emit` (line 407) for every
  StreamHandler of the process (J1, J2).
- `join` and `abspath` are `os.path.join` and `os.path.abspath`, bound at
  module level (lines 44-45). Every `join(...)` and `abspath(...)` is a
  value site for the site finder; its note says so.
- `nodeenv.urlopen` returns what `urllib.request.urlopen` returns (J3).
- `args` is the `argparse.Namespace` of `parse_args` (the options of
  `make_parser`): `args.node`, `args.npm`, `args.jobs`, `args.make_path`
  are str; `args.requirements` and `args.local_requirements` lists of str.
- `subprocess.Popen` is always made without text mode: `communicate()`
  gives bytes (`clear_output` decodes them), and `proc.stdout` of `callit`
  is an `io.BufferedReader`.
- Files: `open(..., 'rb')` gives `io.BufferedReader`, `open(..., 'wb')`
  `io.BufferedWriter`, text mode `io.TextIOWrapper`.
- `tarfile_open` yields the `TarFile` of `tarfile.open` (`TarFile.open`
  bound to `TarFile`); the archive of `download_node_src` is that
  `TarFile`, or a `zipfile.ZipFile` on Windows, Cygwin and MSYS.

## Default rejections

None. The two package classes define no special method but `__call__`, so
no implicit site has a candidate.

## Judgement calls

J1. **The logging call-back** (decides 22 inside edges; ruling of the
lead, 2026-11-24, for the debug sites). `create_logger` assigns its local
`emit` to `logging.StreamHandler.emit` (line 407) and gives the package logger a
StreamHandler. A call `logger.info(...)`, `.warning`, `.error` or
`.critical` reaches `Logger.callHandlers`, which calls `handle`, then the
patched `emit`, of that handler: by the call-back rule (B5; structlog's
`ProcessorFormatter.format`, pyrate-limiter's `Rate.__repr__`), `emit` is
a callee of each such site, beside `logging.Logger.<level>`. The callers:
`writefile`, `callit`, `_download_node_file`, `download_node_src`,
`make_certifi_context`, `urlopen`, `copy_node_from_prebuilt`,
`build_node_from_src`, `install_node`, `report_node_download_error`,
`install_node_wrapped`, `install_npm`, `install_npm_win`,
`install_packages`, `install_activate`, `create_environment`,
`print_node_versions`, `resolve_node_version`, `get_env_dir` and `main`
(20 edges; the trace has 12). A `logger.debug(...)` call also has
`emit` (ruling of the lead, 2026-11-24, on the audit's finding F1): the
package sets the level to INFO (line 399), and nothing of the package,
its documentation or its tests lowers it, but the README clarification
"Versions and configuration" admits documented library configuration
that changes a package-owned value, and logging documents setting the
level of a named logger (`logging.getLogger("nodeenv").setLevel(
logging.DEBUG)`, `logging.config.dictConfig`), a public interface of the
library. The pymysql flag ruling differs: there a client would assign a
module flag of the package itself, a change of package internals. So
`mkdir -> emit` and `_get_last_node_version -> emit`, whose only logger
calls are debug calls, are edges too (the trace has neither: its level
stayed INFO). The writer's first reading, which applied the pymysql rule
and left these 2 inside edges out, is withdrawn.

J2. **The receivers of `emit`** (4 outside edges, 1 rejected trace edge).
`emit` is no attribute of a public path; logging calls it on every
StreamHandler whose class does not override `emit`. The package's own is
`ch`, whose stream is `sys.stderr` at import (`io.TextIOWrapper`; `-u`
does not change the text layer). Library code makes one more:
`logging.lastResort`, a `_StderrHandler` (a StreamHandler subclass whose
`stream` property is `sys.stderr`), used when a record finds no handler;
it adds no name. A client's handler (pytest's capture handlers on the
root logger, whose stream is a `StringIO`) is a client object (B5): the
trace edge `emit -> _io.StringIO.write` is rejected. Callees:
`logging.StreamHandler.format`, `<builtin>.getattr`,
`io.TextIOWrapper.write`, `logging.StreamHandler.flush` (the trace names
`format` through `logging.Handler`, an alias of the same function).

J3. **The response of `urlopen`** (4 outside edges from reading). The
responses read at `911:53`, `1316:53`, `1318:52` and `1584:36` come from
`urllib.request.urlopen`: an `http.client.HTTPResponse` for http and
https, and a `urllib.response.addinfourl` for a `file://` mirror, which
`README.rst:224-228` and the `--mirror` entry (`README.rst:430`) document
and `test_mirror_option_local_directory` uses, and for ftp (an ftp mirror,
or a server's redirect to ftp, which `HTTPRedirectHandler` follows: the
asciinema ruling). `addinfourl` has no `read`: its base
`tempfile._TemporaryFileWrapper` returns the local `func_wrapper` from
`__getattr__` (asciinema judgement 9, segno, bottle). So each of the four
sites has `http.client.HTTPResponse.read` and
`tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`. The npm
registry URLs of `install_npm_win` are https, so there only a redirect to
ftp gives the second name; the alternative (HTTPResponse only at
`1316:53` and `1318:52`) would remove 1 edge
(`install_npm_win -> ...func_wrapper`).

J4. **Platforms** (decides inside edges). Windows, Cygwin and MSYS are
supported (above), so these run: `install_activate -> mkdir` (`1456:14`)
and `install_activate -> callit` (`cygpath`, `1487:36`), Cygwin and MSYS
only; `copy_node_from_prebuilt -> writefile` and `-> make_executable`
(Cygwin); `create_environment -> install_npm_win` (`1572:17`, Windows,
Cygwin, MSYS); `download_node_src -> _extract_zip` and `-> <lambda1>`
(the zip branch); `main -> _sitebuiltins.Quitter.__call__` (`exit(1)`,
Windows with `--node=system`, line 1733; pyfiglet J6). The POSIX branches
(`tarfile_open`, `operator.attrgetter`, `os.symlink("node", ...)`) run on
Linux and macOS.

J5. **`urlsplit`** (`1048:21`): `urllib.parse.urlsplit` (3.10) and
`_functools._lru_cache_wrapper.__call__` (3.11 and later), the
fastjsonschema precedent. `parts._replace` is
`urllib.parse.SplitResult._replace` (the trace's
`collections.namedtuple._replace` is an alias).

J6. **`tarfile_open`** (`977:27`, `1333:22`). `tarfile_open` is a
`@contextlib.contextmanager` generator function: a call runs
`contextlib.contextmanager.helper`, which calls the generator function
back (the micro-benchmark rule; dagster-pipes). Both sites have both
callees; the trace has `helper` at `1333:22` only (the tests patch
`tarfile_open` in `download_node_src`).

J7. **`_OPERATORS[op](version, other)`** (`353:27`). `match_node_range`
is public, and its `ranges` are documented as "the parsed alternatives"
of `parse_node_range`, which makes only the operators `>=`, `>`, `<=`
and `<` (`_comparator_constraints`, lines 238-297: `=` and the other
forms are rewritten). A hand-built range with `=` is a value that the
package never produces for that role (B3). So `operator.ge`, `.gt`,
`.le`, `.lt`; `operator.eq` (line 212) is no callee.

J8. **`PrintCompletionAction.__call__`**. argparse calls it from
`parser.parse_args()` in `parse_args` (`675:29`, callback) with the
parser that holds it, the `argparse.ArgumentParser` of `make_parser`;
argparse documents the `parser` argument as that ArgumentParser (B4), so
`parser.error` and `parser.exit` are `argparse.ArgumentParser.error` and
`.exit`. `shtab.complete` and `shtab.cmd` call nothing of the package
back (shtab 1.13.0's `complete_*` read the actions and log only debug
records).

J9. **`certifi.where`** (`1014:59`). certifi is an optional extra and not
installed in the benchmark: a missing module, named by its access path.

## Callees outside the package

- Functions of a module keep the imported path: `os.path.join` (also
  through the module names `join`, `abspath`), `os.path.exists`,
  `shlex.quote` (imported as `_quote`), `urllib.request.urlopen` and
  `urllib.request.Request` (the module is imported as `urllib2`),
  `urllib.parse.unquote`, `.urlunsplit`, `tarfile.open`, `re.match`,
  `operator.ge`, `concurrent.futures.wait`,
  `concurrent.futures.ThreadPoolExecutor`.
- Methods by the class of the receiver: `configparser.ConfigParser.read`
  (and `.get`, `.getboolean`, `.has_option`, `.has_section`),
  `logging.StreamHandler.setLevel` and `.setFormatter`,
  `argparse.ArgumentParser.add_argument`, `types.MappingProxyType.items`
  for `vars(cls).items()`, `collections.abc.Mapping.get` for
  `os.environ.get`, `os._Environ.copy` (asciinema).
- `exit(1)`: `_sitebuiltins.Quitter.__call__`.
- `certifi.where`: a missing module (J9).

## Open path sets

None.

## Rejected trace edges

`nodeenv.rejected.json`, 30 edges (the `lru_cache` wrapper spelling of
`split_url_auth` since the Corrections of 2026-11-25), the others:

- 25 edges to `unittest.mock.CallableMixin.__call__`: the tests patch a
  callee of the function with a mock (each entry names the patch and its
  test lines).
- `_get_versions_json -> _io.BufferedReader.read` and `-> _io.BytesIO.read`,
  `install_npm_win -> _io.BytesIO.read`: the tests make `nodeenv.urlopen`
  return a file or a `BytesIO` of their own.
- `create_logger.emit -> _io.StringIO.write`: pytest's capture handler
  (J2).

## Notes for the auditor

- `logger.debug(...)` sites are value sites only because `Config` binds
  an attribute `debug` (line 80); their note says why `emit` is a callee
  (J1).
- No `emit` edge at `464:29` (`shtab.complete`): shtab logs only debug
  records on its own logger "shtab", which passes no handler of the
  package; they reach only handlers that a client configures on the root
  logger, client code by the configuration-selection rule (B5,
  whitenoise), and the ruling of J1 admits a level change on the package's
  logger, not handlers of the client.
- `build_node_from_src` builds a lazy `map` of its lambda (`1138:28`) and
  iterates it through the `zip` of line 1144 in the same function: the
  lambda is a callee at the `map` site (README, "Limits of the site
  finder").
- `_get_last_node_version` calls `_get_versions_json()` when it builds
  the generator expression and `version_filter(v)` when `next` runs it:
  both belong to the function.
- Functions that the tests do not run: `Config._dump`, `callit`,
  `get_node_src_url`, `get_root_url` (the tests patch `callit`,
  `get_node_bin_url` and `get_node_src_url`).
- `logger.info(out)` in `install_npm` (`1301:20`) logs bytes; logging
  formats them with `str()`: no package call.
- A bug of the release that removes no edge: `get_node_bin_url` has the
  key `'amd64'` twice in `archmap` (lines 862-863).

## Statistics

`check.py nodeenv`:

```
nodeenv: 1 modules, 66 functions (2 lambdas), 2 classes, 595 calls
  sites: 598 (595 call, 3 decorator); 120 with candidates (120 candidates); 76 value sites
  ground truth: 439 edges (120 internal, 319 outside)
  trace: 357 edges; confirms 327 of 439 ground-truth edges (74.5%); 62 of 66 functions run (93.9%); 30 rejected
nodeenv: no errors
```

`check.py --origin nodeenv`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| nodeenv | 357 | 30 | 327 (79 / 248) | 112 (41 / 71) | 439 (120 / 319) |

| | Count |
|---|---|
| Sites | 598 (595 call, 3 decorator); 120 with candidates; 76 value sites |
| Ledger entries | 598 (669 callee lines, 7 rejection lines, 107 notes, no exclusion) |
| Nodes | 67 (1 module, 66 functions) |
| Edges | 439: 120 in the package, 319 outside |
| Confirmed by the trace | 327 of 439 (74.5%) |
| From reading only | 112 (41 inside, 71 outside) |
| Rejected trace edges | 30 |
| Default rejections | 0 |

## Corrections of 2026-11-25

The referee's `ruling-lru-3.md` (adopted by the lead; README, "Rulings for
the corrections of 2026-11-25") names a call of an `lru_cache` wrapper on
CPython through the type that `_functools` exports: `functools` imports
`_lru_cache_wrapper` from `_functools` without listing it in `__all__`
(CPython 3.10.22 `Lib/functools.py:12`, `:642`; 3.12.16 `:645`; 3.15.2
`:738`), a private re-export that establishes no public class path, and
`_functools` exports the type under that attribute
(`Modules/_functoolsmodule.c`, 3.10.22 `:1462`, type name
`functools._lru_cache_wrapper` at `:1419`; 3.15.2 `:1969`, `:1908`).
`functools._lru_cache_wrapper.__call__` becomes
`_functools._lru_cache_wrapper.__call__` here (outside; edge count
unchanged):

| Caller | Site |
|---|---|
| `nodeenv.split_url_auth` | `nodeenv.py:1048:21` |

The trace names the type by its facade qualname, so its 1 pair `caller ->
functools._lru_cache_wrapper.__call__` is rejected as a naming artefact in
`nodeenv.rejected.json` (rule A).
