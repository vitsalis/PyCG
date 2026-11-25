# django-environ: judgements of the ground truth

Release v0.14.0 (commit `6e1b461`), batch 6. Analysed source:
`environ/` (root `.`): 4 modules, 70 functions (3 lambdas), 7 classes.
`setup.py:239` sets `python_requires='>=3.9,<4'`; the classifiers name
CPython and PyPy and Python 3.9 to 3.14 (`setup.py:156-165`).
`docs/install.rst` names Django >= 2.2 as a requirement, but the package
declares no requirement on it; its only requirement is `typing_extensions`
on Python 3.9 (`setup.py:179-182`). The test run has no Django (the lead's
decision 7 of batch 6).

The ledger is `django-environ.ledger`; the graph `django-environ.json` is
generated from it. Six trace edges are rejected in
`django-environ.rejected.json` (see "Rejected trace edges").

## Statistics

74 nodes (4 modules, 70 functions). 267 edges (79 inside, 188 outside),
after the audit (+2: F1, F2). The trace has 235 edges; 229 of the 267
(85.8%) are confirmed by it, 38 come from reading only. 65 of 70 functions run in the tests (not run:
`Env.channels_url`, `Env.search_url`, `NoValue.__repr__`,
`Path.__unicode__`, `Path.file`). 347 ledger entries, 6 value sites, 11
default rejections, no exclusions.

## Where package objects flow

- `Path` (`environ.py:1196`). A `Path` reaches package code as `self` in its
  methods, as `other` in `__eq__`, `__add__` and `__contains__` (where only
  its `__root__` str is used), and through `Env.path`. `Env.path`'s
  `default` is annotated `Union['Path', NoValue]` (`environ.py:464`), so
  get_value's `default`, and the `value` it returns, can be a Path; smart
  casting (`environ.py:546-549`) makes `cast = type(default)`, the class
  Path; `Env.path` then calls `Path(<a Path>, **kwargs)`. `__root__` is
  always the str of `os.path.abspath`. Path defines `__eq__` without
  `__hash__`, so it is unhashable.
- `FileAwareMapping` (`fileaware_mapping.py:16`, a `MutableMapping`). It
  reaches package code as `self` and as `ENVIRON` of `FileAwareEnv`
  (`environ.py:1193`). Its `env` is the package default `os.environ` or a
  client mapping.
- `Env.ENVIRON` is `os.environ` for `Env`, the FileAwareMapping for
  `FileAwareEnv`, or the dict that the tests assign (`test_env.py:72`, `92`,
  `477`, `517`; `test_schema.py:23`).
- The URLs are `urllib.parse.ParseResult` objects: the documented type of
  the `url` parameters ("urllib.parse.ParseResult or str url") or the result
  of `urlparse`.

## Default rejections (candidate-site pairs)

| Candidate | Sites |
|---|---|
| `Path.__eq__` | 191 |
| `Path.__getitem__` | 175 |
| `FileAwareMapping.__getitem__` | 175 |
| `FileAwareMapping.__len__` | 98 |
| `FileAwareMapping.__iter__` | 80 |
| `FileAwareMapping.__setitem__` | 40 |
| `Env.__contains__` | 37 |
| `Path.__contains__` | 37 |
| `Path.__add__` | 18 |
| `Path.__repr__` | 9 |
| `NoValue.__repr__` | 9 |

Entries accept the candidate where it runs: `FileAwareMapping.__getitem__`
at `Env.__contains__` (`environ.py:261:20`, through
`collections.abc.Mapping.__contains__`) and at `self.ENVIRON[var_name]`
(`520:33`); `FileAwareMapping.__iter__` at `iter(self)`
(`fileaware_mapping.py:73:30`); `Path.__eq__` at `self.__eq__(other)`
(`environ.py:1248:31`).

## Judgements

**J1. Optional imports (`compat.py:14-25`).** Both sides of the
`find_spec` branches run (the default for optional imports).
- `json` is `simplejson` when it is installed: the value site
  `cast(value)` (`environ.py:613:25`) has `json.loads` and
  `simplejson.loads` (a missing module) for the cast of `Env.json`.
- `ImproperlyConfigured` is `django.core.exceptions.ImproperlyConfigured`
  with Django, else the package class `compat.ImproperlyConfigured(Exception)`.
  The seven `ImproperlyConfigured(...)` sites (`environ.py:281`, `524`,
  `778`, `875`, `913`, `1014`, `1304`) have `<builtin>.Exception.__init__`
  and `django.core.exceptions.ImproperlyConfigured` (a missing module in the
  test environment; the micro-benchmark rule for an external class). Django
  is a documented requirement but not a declared one; I took the optional
  import rule over the "declared requirements" rule, because the import is
  guarded by `find_spec`. Ruling (lead, after the audit): J1 stands; the docs expect
  Django.

**J2. The tests' `Env.ENVIRON` dict.** The tests assign a dict to the public
class attribute `ENVIRON`, so by B2 the assignment counts. The dict itself
is the tests' own value: a client object (B5), as the tests' own
`defaultdict` of funcy (batch 5, ruling 7). The method calls on it
(`envval.update`, `envval.setdefault`, `environ.py:1169-1170`) have no
callee for it; the two trace edges are rejected. The package values are
`os.environ` (`collections.abc.MutableMapping.update`, inherited;
`os._Environ.setdefault`, defined by `os._Environ` itself, named as the
asciinema precedent `os._Environ.copy`) and the FileAwareMapping of
`FileAwareEnv` (`MutableMapping.update` and `MutableMapping.setdefault`,
which call back `FileAwareMapping.__setitem__`, and `__getitem__` for
`setdefault`).

**J3. `FileAwareMapping.env`.** The docstring says only "where to read
environment variables from (defaults to os.environ)": no concrete type. The
tests pass dicts: client objects. The package default `os.environ` gives
`collections.abc.Mapping.get` at `fileaware_mapping.py:47:32` (anytree
precedent). The trace edge `-> <builtin>.dict.get` is rejected.

**J4. A Path through `Env.path`.** The annotation of `Env.path`'s default
admits a Path into get_value's `default` (B2: the package's own code passes
it). So:
- `value != default` (`environ.py:553:18`) runs `Path.__ne__` (reflected
  for `str != Path`);
- smart casting gives the class Path as `cast`, and `cast(value)`
  (`613:25`) runs `Path.__init__`;
- `Env.path` then gives that Path to `Path.__init__` as `start`;
  `os.path.dirname(start)` (`1230:36`, with `is_file`) and
  `os.path.join(base, *paths)` in `_absolute_join` (`1302:53`) call
  `os.fspath`, which calls `Path.__fspath__` (library call-backs).
No test passes a Path default, so the trace has none of these edges.
`paths` and the `**overrides` of read_env take client strs only (B3: a
package object passed where any value is accepted is not considered;
`Path.__add__` passes `other.__root__`, and the tests pass
`Path(...).__root__`).

**J5. `Path.__str__` at `cast(value)` (`environ.py:613:25`).** The witness:
`Env().get_value('UNSET', cast=str, default=Path('/x'), parse_default=True)`
(or `env(...)` with the same arguments). The Path default is admitted by
J4; `cast=str` and `parse_default=True` are documented public arguments.
`value != default` is False (two equal Paths), `parse_default` sends the
Path to `parse_value`, and `str(value)` runs `Path.__str__`. This combines
admitted values of three arguments; no document shows it. The same
witness with a `NoValue` default gives `Env.parse_value ->
NoValue.__repr__` (audit F2): the package passes `NOTSET` and its
`Union[X, NoValue]` defaults to get_value's `default`, smart casting skips
a NoValue, and `str()` of it runs `NoValue.__repr__`. So the combination
decides 2 inside edges. Ruling (lead, after the audit): J5 stands; admitted
values of the parameters of one public call combine freely.

**J6. bytes in get_value (`environ.py:538-543`).** `Env.bytes` passes a
default annotated `Union[bytes, NoValue]`, and lines 536-537 handle bytes
explicitly, so `value.startswith`, `value.lstrip` and `value.replace` have
the bytes methods next to the str methods (B4 through the flow of the
argument). `bytes.startswith` is in the trace; `bytes.lstrip` (a bytes
default that starts with `b'$'`) and `bytes.replace` (with the documented
`escape_proxy`) come from reading.

**J7. Smart casting of a client default (`environ.py:549`).**
`cast = type(default)` of a client default is the class of a client object.
I treated it as the client's cast (a client callback, B2/B5). This adds
nothing for int and str (the package's own casts already give
`<builtin>.int` and `<builtin>.str` at `613:25`). It leaves out
`<builtin>.bytes`: `bytes(value)` runs only for a bytes default passed to
an unannotated `default` (`Env.__call__`, `get_value`) without a cast;
`Env.bytes` always passes `cast=str`. Bytes differs from `Path` and `NoValue`: those are package
values that the package itself passes to get_value's `default`, while bytes
is an outside type whose only package flow is `Env.bytes` (B4 through its
annotation), and `Env.bytes` always passes `cast=str`, so that flow never
reaches smart casting. For the same reason the bytes methods of
`parse_value` are not callees. Ruling (lead, after the audit): J7 stands.

**J8. `RuntimeError` at `environ.py:1087`.** The check `caller_frame is
None` (`# pragma: no cover`) fails when read_env has no Python caller
frame: a client that starts it with `_thread.start_new_thread(Env.read_env,
())`, or registers it with `atexit`. The edge stays.

**J9. Names of Env's methods.** Env defines methods named `str`, `bytes`,
`bool`, `int`, `float`, `json`, `list`, `tuple`, `dict`, `url` and `path`.
In a function body these names are the builtins (class attributes are not
in scope), so every candidate `Env.<name>` at `str(...)`, `int(...)`,
`isinstance(x, str)`, `cast=str` and so on is rejected.

**J10. Streams and paths of read_env.** `env_file.read()`
(`environ.py:1103:40`): the parameter is annotated `IO[str]` there, an
abstract type that fixes no class, so the client's stream is opaque; the
trace edge to `_io.StringIO.read` is rejected. `open(env_file, ...)`
(`1100:26`) gets a str or a `pathlib.Path`; the annotation does not admit an
`environ.Path`, so no `Path.__fspath__` there.

**J11. Lazy `map` in parse_value.** `dict(map(lambda kv: ..., ...))`
(`environ.py:583`) builds and iterates the map in one function: the lambda
is a callee of the `map` site. The callbacks of `map(cast[0], ...)`
(`575:29`, `578:30`) are the client's list and tuple casts: no edge.

**J12. Names.** `url._replace(...)` is `urllib.parse.ParseResult._replace`
(the class of the receiver; the trace's canonical name is
`collections.namedtuple._replace`, with this alias). The file of
`open(..., encoding=...)` is an `io.TextIOWrapper`.

**J13. `NoValue` defaults (audit F1).** `Env.str`'s `default` is annotated
`Union[_str, NoValue]` and `NoValue` is public, so a client can pass a
fresh `NoValue()`. get_value tests the default by identity
(`default is self.NOTSET`, `environ.py:522`), so it returns that object.
With `choices`, the f-string at `282:38` formats it and runs
`NoValue.__repr__`: +1 inside edge (`Env.str -> NoValue.__repr__`).

## Rejected trace edges

| Caller | Callee | Reason |
|---|---|---|
| `compat.choose_pymemcache_driver` | `unittest.mock.CallableMixin.__call__` | the tests patch `compat.find_spec` with a MagicMock |
| `compat.choose_rediscache_driver` | `unittest.mock.CallableMixin.__call__` | the same |
| `Env.read_env` | `_io.StringIO.read` | the test's stream (J10) |
| `Env.read_env.set_environ.<lambda1>` | `<builtin>.dict.update` | the tests' `ENVIRON` dict (J2) |
| `Env.read_env.set_environ.<lambda2>` | `<builtin>.dict.setdefault` | the tests' `ENVIRON` dict (J2) |
| `FileAwareMapping.__getitem__` | `<builtin>.dict.get` | the tests' `env` dict (J3) |

## Edges from reading only (38)

The trace lacks: the seven Django `ImproperlyConfigured` edges and
`search_url_config -> <builtin>.Exception.__init__` (J1; no test gives an
invalid search scheme); `simplejson.loads` (J1); the Path flow of J4 and J5
(`get_value -> Path.__ne__`, `parse_value -> Path.__init__` and
`Path.__str__`, two `Path.__fspath__` call-backs); the two
`NoValue.__repr__` edges (J13, J5); the FileAwareEnv edges
(no test uses `FileAwareEnv`: `Env.__contains__` and `get_value` ->
`FileAwareMapping.__getitem__`, the lambdas' MutableMapping and os.environ
callees and call-backs) and `FileAwareMapping.__getitem__ ->
collections.abc.Mapping.get` (J2, J3); `FileAwareMapping.__len__ ->
__iter__` (a generator function that `iter()` starts: a limit of the
tracer); `bytes.lstrip` and `bytes.replace` (J6); `RuntimeError` (J8);
`read_env -> os.path.exists` (the test replaces `os.path.exists` with a
lambda); `_parse_elasticsearch_search_params -> <builtin>.str.join` (no test
index path has a `/`); and the functions that no test runs
(`Env.channels_url`, `Env.search_url`, `Path.__unicode__`, `Path.file`).

## Note on `check.py --report --without-candidates`

In my first report I said that this option printed the normal report and
not the list of implicit sites without candidates. That was my error, not
the tool's. What I ran, with the draft ledger in place:

    PY -I macro-benchmark/check.py --report django-environ --without-candidates 2>/dev/null \
        | rg -v 'getattr|setattr' | head -80

The command printed the normal report: the sizes, value sites, sites with
package callees that are not candidates, and default rejections. The list
comes at the end of the output, after "trace edges that no site of the
caller accounts for", and the `head -80` cut it off. Run again without the
filter and the cut, the option prints 505 lines; the plain `--report` prints
127. The extra lines are the section "implicit sites without candidates:
377", one line per site. The tool works as the README says.

I then read that list. 351 sites are attribute loads and stores. None of
them names a package property (the only one is `Path.root`, which the
package never loads), and the package defines no `__getattr__` or
`__setattr__`. The other 26 sites are class statements, unary minus,
comparisons of ints and tuples, `'../' * other`, and two `with open(...)`
items. None of them iterates a lazy `map` or `filter`, or runs package
code. No entry was missing.

## PyPy

**Decision: in scope.** The release explicitly supports PyPy. Its
classifier is `Programming Language :: Python :: Implementation :: PyPy`
(`setup.py:165`), its CI runs `pypy-3.10` (`.github/workflows/ci.yml:56`,
`tox.ini:36`, `tox.ini:26`), and `CHANGELOG.rst:302` says that PyPy is
supported. The declared bounds `>=3.9,<4` (`setup.py:239`) admit PyPy 3.9,
3.10 and 3.11. I read the sources of PyPy 3.10 (v7.3.19) and 3.11 (v7.3.20)
as text and ran nothing.

**Names (15 checked, no edge change).** I checked the outside callees whose
class or module could differ on PyPy:
- `re.Match.group`, `re.match`, `re.sub` and `re.split`: `re.Match` is
  `type(...match(''))` (`re.py:280` on 3.10, `re/__init__.py:264` on 3.11).
- `io.TextIOWrapper.read`: PyPy's `_io` exports the same class path.
- `itertools.zip_longest`: the same path.
- `os._Environ.setdefault`: defined by `os._Environ` (`os.py:715` on 3.10,
  `716` on 3.11).
- `collections.abc.Mapping.get`, `MutableMapping.update` and
  `MutableMapping.setdefault`: pure Python (`_collections_abc.py:821`,
  `991`, `1009` on 3.10).
- `warnings.warn`: imported from `_warnings` or the Python fallback, under
  the same path (`warnings.py:538`).
- `json.loads`, `logging.getLogger`, `logging.Logger.*`,
  `urllib.parse.*`, `ParseResult.geturl`, and `os.path.*`: pure Python,
  with the same paths.
- `ParseResult._replace`: different. PyPy makes it with `exec`
  (`collections/__init__.py:465` on 3.10, `:488` on 3.11), so on PyPy it is
  generated library code and has no name. The edge stays, because CPython
  defines `_replace` with `def` and the graph is the union over the
  runtimes (Codex audit round 1).

**Call-backs (10 checked, no change).**
- `Mapping.__contains__` calls `self[key]` (`_collections_abc.py:828`).
- `MutableMapping.update` and `setdefault` call `self[key] = ...` and
  `self[key]` (`991-1015`).
- `posixpath.dirname` and `join` call `os.fspath` (`posixpath.py:152`,
  `76`), which calls `Path.__fspath__`.
- `re.sub` calls the replacement function.
- `map` calls the parse_value lambda.
- `iter(self)` starts the generator function `__iter__`.
- `format()` and `str()` reach `Path.__str__` and `NoValue.__repr__`
  through `object.__str__`.
- `!=` runs the reflected `Path.__ne__`.

PyPy makes each of these calls as CPython does, with the same names.

**Branches (none).** The package has no branch on `sys.implementation`,
`platform` or a C accelerator.

No edge changes: 267 edges.

## Codex audit round 1

- **Missing `Path.__contains__ -> <builtin>.bytes.startswith` (1275:40),
  `Path.__getitem__ -> <builtin>.bytes.__getitem__` (1287:42),
  `Path.__sub__ -> <builtin>.bytes.endswith` (1258:61): rejected.**
  These edges need a bytes root, and a bytes value is not admitted for
  `Path.__init__`'s `start` or `paths`. `Path`'s parameters have no
  annotation. Its documentation names strs: `file`'s ":param str name"
  (`environ.py:1211`), and the "List of sub paths" of `path` and
  `__call__` (`1202`, `1237`). The docs pass strs (`environ.Path(__file__) -
  3`, `BASE_DIR('.env')`, `docs/tips.rst` "Using Path objects"), and so do
  the tests (every call in `tests/test_path.py`; `test_env.py:519-520`).
  The package's own flows are strs too: `Env.path` passes os.environ strs
  or a Path, and `path`, `__add__`, `__sub__` and `__invert__` pass
  `__root__` strs. The class's own code also treats the root as a str:
  `str(path)` would raise for a bytes root (`__str__` returns it, `1281`),
  and `__contains__` joins it with `''` (`1274`). So a bytes path is a
  client value outside the documented contract (B2, last sentence; B5;
  clarification "Concrete types": a concrete contract does not admit
  out-of-contract types). This is consistent with J7. In both cases bytes
  is an outside type that the client passes to a parameter for which no
  annotation, document, test or package flow admits it, so the calls on
  the values derived from it are not edges. J6 admits bytes only where
  `Env.bytes`'s annotation `Union[bytes, NoValue]` passes them.
  The referee upheld this rejection (README, "After Codex audit round 1",
  ruling (b): an argument that binds does not admit a concrete outside type
  at an unannotated parameter; the documented contract, explicit type
  handling and admitted package flows decide).
- **Unsure `Path.__sub__ -> <builtin>.bytes.rstrip` (1259:45): rejected.**
  It needs a bytes root (see the item above). With an admitted str root,
  `rstrip` is `<builtin>.str.rstrip`, which the graph already has.
- **Metadata `ParseResult._replace` on PyPy: applied.** It is a note only
  (ledger `919:43`; "PyPy" above). PyPy 3.10 and 3.11 make `_replace` with
  `exec` (`collections/__init__.py:465`, `:488`). The edge stays through
  CPython.
