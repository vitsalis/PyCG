# path: judgements of the ground truth

Release v17.1.1 (commit `0f86209`), batch 6. Analysed source:
`path/` (root `.`): 5 modules (`path`, `path.classes`, `path.masks`,
`path.matchers`, `path.compat.py38`), 182 functions (5 lambdas), 19
classes. The ledger is `path.ledger`; `path.json` and `path.added.json`
are generated from it; `path.rejected.json` holds 12 trace edges.

## Supported versions and platforms

- `pyproject.toml:28`: `requires-python = ">=3.9"`, with no upper bound.
  The versions are CPython 3.9 and later.
- The CI matrix (`.github/workflows/main.yml:52-53`) also runs `pypy3.10`
  on Linux. So PyPy is an implementation that the release supports, under
  the same bound; the section "PyPy" below records the check against the
  PyPy 3.10 and 3.11 sources (3 edges to `_sha1.sha`).
- `pyproject.toml:25`: `Operating System :: OS Independent`. The code has
  Windows branches on purpose (`__init__.py:1191`, `1231`, `1299`, `1682`,
  `1688`), the `test` extra has `pywin32` for Windows, and the CI tests on
  `windows-latest` (`main.yml:35-41`). So Windows is a supported platform,
  as for netaddr and Sublist3r. On Windows `os.path` is `ntpath`. The
  README ruling "Library behaviour on supported platforms" applies.
- `-O` and `-OO`: `assert self.fget is not None` (`classes.py:9`) has no
  call; nothing else depends on them.

## Architecture, as the ledger uses it

- `Path` subclasses `str`. It overrides `__new__`, `__init__`, `__repr__`,
  `__add__`, `__radd__`, `__truediv__`, `__rtruediv__`, `__enter__`,
  `__exit__` and one `str` method, `replace`. Nearly every method returns
  `self._next_class(value)`.
- `_next_class` is a `classes.ClassProperty` (a `property` subclass) over a
  classmethod, in `Path` (returns `cls`), `TempDir` (returns `Path`) and
  `Multi` (returns the first class of the MRO that is not a `Multi`).
  `special` is the fourth `ClassProperty`. So a load of `x._next_class`
  runs `ClassProperty.__get__`, which calls the classmethod, and the call
  `self._next_class(v)` constructs the returned class. The ledger puts
  `ClassProperty.__get__` at each load (39 entries added by hand, because
  the default rejection of `ClassProperty.__get__` removes these loads from
  the skeleton), and the constructors at the call; the `_next_class`
  candidates of the call are rejected.
- `joinpath` is a `classes.multimethod`; the package never loads it.
- `Multi.for_class(cls)` makes `type('Multi' + name, (Multi, cls), {})`;
  `SpecialResolver.get_dir` builds such a class from `path_class` and
  calls `detect`. A Multi value is only returned to the client; no package
  code iterates one (default rejection of `Multi.__iter__`).
- `matchers.load` turns a pattern into `Pattern`, `None` into `Null()`, and
  passes other values through. `CaseInsensitive.normcase` is
  `staticmethod(ntpath.normcase)`.

## Judgements

**J1. The module of a Path.** The class attribute `module` is `os.path`
(`__init__.py:178`), the only package value of that role. Calls through
`self.module` and `cls.module` are named `os.path.<name>` on every platform
(the whitenoise precedent: imported `os.path` names keep that path). A
module that the client puts there, by `Path.using_module(ntpath)` or by the
assignment `p.module = ntpath` that the tests make
(`tests/test_path.py:154`, `1109`), is a value from outside the package that
the client passes: a client object (B2, B5; the precedent of
`dict_cls=collections.OrderedDict`). Its functions are no callees. Nine
trace edges to `ntpath.*` are rejected for this reason
(`path.rejected.json`). `CaseInsensitive`'s `ntpath.normcase` is a package
value and keeps its name (`matchers.py:58`, `65`).

**J2. Path values in `str` parameters.** `Path` is a `str`, so a `str`
annotation admits it. The package documents a Path as a drop-in string and
its tests and docstrings pass Paths as path arguments (`orig.replace(
dest.joinpath('fee'))`, `__init__.py:1338`; `testFile.copy(testA)`,
`target.link(Path(tmpdir) / 'link')` in the tests). So a parameter whose
role is a path (`rel`, `first`, `others`, `start`, `dest`, `new`,
`newpath`, `newlink`, `target`, `target_or_old`, `dst`) admits a Path, and
so do `name` and `stem`, whose values the package itself produces as Paths
(`Path.name` returns a Path; `Path.stem` returns `self.name` itself when
the name has no extension, because `genericpath._splitext` returns its
argument). Gives `with_name -> Path.__radd__` (`__init__.py:389:63`),
`with_stem -> Path.__add__` (`325:36`), and the `__add__` callbacks of
`shutil.copy`, `copy2`, `move` and `copytree` for a Path `dst`. `TempDir`
takes the parameters of `tempfile.mkdtemp` (its docstring, `1970`), so its
`dir` is a path role too and admits a Path (audit F2, adopted by the
referee): `TempDir.__new__ -> Path.__add__` (`1994:35`). A `str`
parameter of another role (a mode, an encoding, a hash name, a pattern, a
suffix, a scope, a message) admits no package value (B3: the package never
produces one for that role).

**J3. Library code that calls Path methods back.** Library functions that
get a Path call its overridden operators and `replace`. The callbacks are
callees of the package site that calls the library function (rule B5).
They were read in the CPython sources of 3.9, 3.12, 3.13, 3.14 and 3.15
(the standard library of each, read as text; nothing of the package ran).
3.10 and 3.11 were not available; where 3.9 and 3.12 agree, the ledger
assumes the same. The facts that the edges rest on:

- `posixpath.join` does `path += sep + b`: `Path.__add__` when the first
  part is a Path, `Path.__radd__` when a later part is a Path (`sep + b`,
  then `str + Path`, where Python tries the subclass's `__radd__` first).
  `posixpath.abspath` of a relative Path joins it to `os.getcwd()`
  (`__radd__`). `posixpath.ismount` joins the Path with `'..'`
  (`__add__`). `posixpath.realpath` of 3.9 to 3.12, for a relative Path
  without a separator: `rest.partition(sep)` returns the Path itself (a
  `str` subclass instance is returned unchanged when the separator is
  missing, checked on 3.9 and 3.15 with a `str` subclass of the writer's
  own), and `join('', name)` adds it (`__radd__`).
- On Windows, `ntpath.normcase` calls `s.replace('/', '\\')` on the Path
  (every version); `splitdrive` (3.9 to 3.11) and `splitroot` (3.12) call
  `p.replace(altsep, sep)`, and 3.12's `splitdrive` returns `root + tail`
  with `tail` the Path (`__radd__`); `ntpath.join`, `split`, `dirname`,
  `basename`, `isabs` (3.9 and 3.10; 3.11 calls `replace` on a slice) and `normpath` (3.9 and 3.10; C from
  3.11) call them. From
  3.13 `splitroot` and `normpath` are C functions, which call nothing.
  In 3.12, `splitroot` returns a UNC path without a third separator
  (`\\server\share`) itself as the drive (`ntpath.py:211-216`), so
  `split` (`d + r + head`, `:250`) and `join` (`result_drive + ...`) run
  `Path.__add__`, and pathlib's `_format_parsed_parts` (`drv + root + ...`,
  `pathlib.py:430-432`) does the same for a UNC raw path (Codex audit
  round 1).
- `os.makedirs`, `os.removedirs` and `os.renames` call `os.path.split` on
  the Path (Windows: `replace`). `glob.glob` and `glob.iglob` call
  `os.path.split` on the pattern (Windows: `replace`; for `iglob` at the
  iteration of its generator, `__init__.py:670:33`).
- `shutil.copy`, `copy2` join a directory `dst` with the base name;
  `copytree` joins `src` and `dst` with each entry name; `rmtree` joins the
  path with each entry name (`_rmtree_safe_fd`, and `os.walk` in
  `_rmtree_unsafe`); `move` joins a directory `dst` and, when `os.rename`
  fails for a directory, calls `_destinsrc` (abspath in 3.9 to 3.12, realpath later),
  `copytree` and `rmtree` on the Path.
- `pathlib` from 3.12 keeps the raw argument and parses it later with
  `path.replace(altsep, sep)`; `altsep` exists only on Windows. So
  `pathlib.Path(self).replace(t)` calls `Path.replace` on `self`
  (`__init__.py:1358:44`; J11 for the target).
- `tempfile.mkdtemp` keeps `dir` as given, computes `prefix + name +
  suffix` and joins it to `dir`: `Path.__add__` for a Path `dir` (J2),
  `Path.__radd__` for a Path suffix (J4) and, from 3.12, in `abspath` of a
  relative joined Path.
- The C functions (`os.stat`, `os.listdir`, `open`, `os.symlink`, ...) take
  the `str` value and call nothing.

**J4. TempDir as a constructed class (78 edges: 38 callers to
`TempDir.__new__`, the same 38 to `TempDir.__init__`, and the 2 call-backs
`TempDir.__new__ -> Path.__radd__` and `-> Path.replace` at `1994:35`, which
F2 also supports).** `TempDir` inherits the classmethods `cwd`, `home`,
`joinpath` and the ClassProperty `special`, so a client can call
`TempDir.cwd()` or `TempDir.special(...)` (B1: a package subclass that
inherits the method). `TempDir.special()` makes a `SpecialResolver` whose
`path_class` is `TempDir`; `get_dir` then builds `MultiTempDir = (Multi,
TempDir)` and `detect` calls `TempDir(value)` or `MultiTempDir(value)`,
that is `tempfile.mkdtemp(value)`. This succeeds when the appdirs value has
no separator (for example `XDG_CONFIG_HOME=cfg`, or `XDG_CONFIG_DIRS=a:b`
with `multipath=True`, which gives a MultiTempDir instance; verified in
appdirs 1.4.4, `appdirs.py:166-204` and `206-255`: without an appname,
`user_config_dir` returns `$XDG_CONFIG_HOME` unchanged and
`site_config_dir(multipath=True)` returns the `os.pathsep` join of the
parts of `$XDG_CONFIG_DIRS`, on Linux). The
`_next_class` of a MultiTempDir is `Multi._next_class`, which returns
`TempDir`, so every `self._next_class(v)` on such an instance runs
`TempDir.__new__` (`mkdtemp(v)`). The ledger names `TempDir.__new__` and
`TempDir.__init__` at every such call. A `v` without a separator lets
`mkdtemp` succeed directly. A `v` with a separator lets it succeed when the
parent that the random name gives already exists and lacks the child. The
referee ruled after Codex audit round 1 that possible random outcomes and
ordinary file-system histories count (README, ruling (c)). The first
version of this ledger named `TempDir.__init__` only for a `v` without a
separator; the 18 rows with a separator (`cwd`, `__add__`, `__radd__`,
`__truediv__`, `__rtruediv__`, `absolute`, `normcase`, `normpath`,
`realpath`, `expanduser`, `expandvars`, `dirname`, `with_name`,
`splitpath`, `splitext`, `glob`, `iglob`, `TempDir.__enter__`) now have it
too, and `splitdrive`'s `409:57` is annotated as well (its pair already
exists through `409:32`).
B1 decides the three `TempDir.__new__` edges of `cwd`, `home` and
`detect`. The others rest on environment values read through libraries
(`HOME`, `XDG_CONFIG_HOME`, `XDG_CONFIG_DIRS`, which the tests also set):
the referee's ruling, now the README's "Environment data read through
libraries", admits them. The ledger matches the ruling's site-by-site
table and its round-1 addition.

**J5. Windows `abspath` fallback.** `ntpath.abspath` catches the
`ValueError` of `_getfullpathname` for a path with an embedded null
character and falls back to `isabs`, `splitdrive`/`splitroot` and `join` on
the Path itself (`replace`, `__radd__`). `Path('a\0')` is a public-API
value. Gives `absolute -> Path.replace` (also in the trace, through the
tests' ntpath module) and `ismount -> Path.replace`, `-> Path.__radd__`.

**J6. Hash objects.** `hashlib.new(hash_name)` returns an OpenSSL
`_hashlib.HASH` (on CPython `_hashlib.HASHXOF` for a SHAKE name), or by
the documented fallback a builtin object. The hash names in scope are the
names that `hashlib.new` accepts on an admitted build: `read_hash` and
`read_hexhash` refer their `hash_name` to hashlib's list ("List of
supported hashes can be obtained from :mod:`hashlib` package.", `985`,
`995`), and `_hash` takes theirs and `read_md5`'s `'md5'`. Only the
guaranteed names change a callee; the others make the OpenSSL classes. The
earlier reading, `md5` (`read_md5`, the tests) and `sha1` (the docstring
of `_hash`) only, yields to scope rule B2 (see "Corrections of
2026-11-28"). The builtin MD5 and SHA-1 classes are named `_md5.MD5Type`
and `_sha1.SHA1Type` on CPython, and `hashlib.md5` (beside `_md5.md5`) and
`_sha1.sha` on PyPy (see "Corrections of 2026-11-25"); the SHA-2, BLAKE2,
SHA-3 and SHAKE classes as in "Corrections of 2026-11-28".

**J7. File objects.** `chunks` passes the client's `mode` and `buffering`
to `open`; its overloads admit text and binary modes. The lambda's
`f.read(size)` (`__init__.py:816:43`) names `io.TextIOWrapper`,
`BufferedReader`, `BufferedWriter`, `BufferedRandom` and `FileIO` (a
`read` of a write-only stream enters the builtin and raises: an edge, as
the "Concrete types" clarification says). `in_place` admits only read
modes: `readable` is a `TextIOWrapper`, `BufferedReader` or (`buffering=0`)
`FileIO`; `writable` a `TextIOWrapper`, `BufferedWriter` or `FileIO`. The
fixed modes (`bytes`, `read_bytes`, `write_bytes`, `read_text`,
`write_lines`) have one class each. On Windows, `open` of a console name
(`CONIN$`, `CONOUT$`, `CON`) makes the raw stream an `_io._WindowsConsoleIO`
instead of a `FileIO` (CPython `Modules/_io/_iomodule.c:323-327`, with
`_PyIO_get_console_type`, `winconsoleio.c:64-95`; 3.11.9 and 3.13.1), and
with `buffering=0` returns it unbuffered (`_iomodule.c:380`). So `chunks`'
lambda also has `_io._WindowsConsoleIO.read`, on CPython and on PyPy (see
"Corrections of 2026-11-25"). At the other sites the console raw stream is
wrapped in a `BufferedReader`, `BufferedWriter` or `TextIOWrapper`, which
are already named. `in_place` cannot open a console: it first renames
`self` to the backup name, and a console device cannot be renamed.

**J8. `only_newer` as a copy function.** `merge_tree`'s docstring passes
`only_newer(shutil.copy2)` as `copy_function` (`__init__.py:1651`), so
`only_newer.wrapper` is a package value for `merge_tree` only:
`merge_tree -> only_newer.wrapper` (`1675:30`, in the trace). `copytree`
and `move` share the annotation `_CopyFn` (`86`, `1524`, `1540`), but that
alias is a bare `Callable[[str, str], object]`, not a package class or
Protocol, and a bare-callable annotation is no evidence for a package
value (B2). Documentation is read one entry at a time, and the docstring's
"similar to copytree" names no shared value. So their `copy_function` is
the default `shutil.copy2` or a client callable, and they have no edge to
the wrapper (referee, case 3; README "A shared alias of a bare
callable"). The default `shutil.copy2` is a callee where the package
calls it (`merge_tree`, `1675:30`), and no edge where shutil calls it.
`only_newer.wrapper`'s own `copy_func(src, dst)` (`1854:25`) has no callee:
the client's function (the trace edge to `shutil.copy2` is rejected).

**J9. Version and platform branches.** `compat/py38.py:3` (`< (3, 9)`)
never runs on a supported version: its first `removesuffix` and
`removeprefix` make no function, so their sites have no edges. The
`rmtree` overloads under `>= (3, 12)`, `>= (3, 11)` and the else branch all
run. The Windows branches run: the Windows `get_owner` calls `globals()`,
`NotImplementedError` and the missing module `win32security` (pywin32 is
not installed: `win32security.GetFileSecurity`,
`win32security.GetFileSecurity.GetSecurityDescriptorOwner`,
`win32security.LookupAccountSid`). The missing-module rule fixes the
names only; nothing is inferred from the stub's value. The real
`LookupAccountSid` returns a 3-tuple, and the return line has only `str`
operations, so it adds no edge either way.
`startfile` (Windows) calls `os.startfile`; the POSIX `get_owner`,
`group`, `statvfs`, `pathconf`, `chown` and `chroot` run on POSIX.

**J10. `Traversal`.** `walker.send(traverse)` is
`types.GeneratorType.send`: the documented walker is `Path.walk()`
(`__init__.py:127`). `walk`'s `traverse()` (`600:39`) is `child.is_dir`
or the `functools.partial` that `Traversal` sends
(`functools.partial.__call__`).

**J11. `Path.__new__ -> Path.replace`.** `Path.replace` with one argument
passes `pathlib.Path(self).replace(target)` to `_next_class`, so
`Path.__new__` gets a pathlib object whose raw path is the client's target
Path (J2). `str.__new__` calls its `__str__`, which on Windows from 3.12
parses the raw path with `replace`. One edge (`185:31`).

**J12. `Path.__repr__` in error texts.** `OSError.__str__` formats the
file name with `%R`, and `shutil.copyfile`'s `SameFileError` uses
`"{!r} and {!r}"`. So `walk`'s `{exc}` (`591:59`: the `OSError` of
`os.listdir(self)`) and the shutil calls of `copyfile`, `copy`, `copy2`,
`copytree` (`str(why)` of a joined Path, `SameFileError` with
`dirs_exist_ok`), `move` (its fallback to `copytree` with `str(why)`, and
to `copy2` with `SameFileError`; audit F1) and `merge_tree`'s
`copy_function` run `Path.__repr__`.
`602:56` does not: that exception comes from `Path.is_dir`, which does not
raise, or from a client function.

**J13. Iteration and callbacks of lazy objects.** `iterdir` returns a
lazy `filter(match, ...)`; the package iterates it in `dirs`, `files`,
`walk` (`594:22`) and `merge_tree` (`list(...)`, `1656:23`), which get
`Null.__call__` and `Pattern.__call__` (entries added by hand: the default
of `Multi.__iter__` hides these iteration sites). The callbacks of `iter`
(`chunks`), `itertools.filterfalse` (`merge_tree`) and `map` (`compound`)
are placed at the call, which is in the function that iterates.
`padded` and `compose` take any iterable or callable; a Multi instance is
an `Iterable` only through `str`, and the package never passes one (B3).

## Default rejections

| Candidate | Sites | Reason (short) | Accepted at |
|---|---|---|---|
| `SpecialResolver.ResolverScope.__getattr__`, `SpecialResolver.__getattr__` | 453 each | normal lookup finds every attribute that the package loads on these objects | nowhere |
| `classes.ClassProperty.__get__` | 71 | the attribute is not `_next_class` or `special` | the 39 `_next_class` loads |
| `classes.multimethod.__get__` | 110 | the package never loads `joinpath` | nowhere |
| `Multi.__iter__` | 66 | no package iteration is over a Multi | nowhere |
| `Path.__enter__`, `__exit__`, `TempDir.__enter__`, `__exit__` | 18 each | no `with` over a Path | nowhere |

## Value sites

26. The notes say where each callee comes from. The hard ones:
`self._next_class(...)`-like calls (`cls(...)` in `cwd`, `home`, `glob`,
`iglob`, `detect`: J4); `error_fn` (`Handlers.strict`, `warn`, `ignore`);
`match` (`Null.__call__`, `Pattern.__call__`); `traverse()` (J10);
`normcase(...)` in `fnmatch` and `matchers` (J1, J3); `mask(...)` in
`chmod` (`functools.partial.__call__`, the inner lambda of `compose`, and
`simple.<lambda1>` through the partial); `f1`, `f2` in `compose` (f2 is
always an original function, because `reduce` folds from the left);
`ignore` and `copy_function` in `merge_tree` (the default lambda
`path.Path.<lambda1>`; J8); the `ClassProperty.__get__` call
(`classes.py:10:46`: the four classmethods); `self.unlink()` (the class
alias `unlink = remove`).

## Rejected trace edges (12)

Nine edges to `ntpath` functions through the tests' module (J1); the
tests' `results.append` in place of `os.chroot`; the tests'
`shutil.ignore_patterns(...)` as `ignore`; and `shutil.copy2` as the
client's `copy_func` of `only_newer`.

## Statistics

187 nodes; 763 edges (422 inside, 341 outside); 487 (63.8%) confirmed by
the trace, 276 from reading only; 177 of 182 functions run (not run:
`copy2`, `copymode`, `move`, `owner`, `startfile`). Of the edges from
reading only, 83 rest on the hash names of J6 that the tests do not pass,
78 on J4 and most of the others on the Windows branches of J3 and on
functions that no test runs. Tracer defect T1: the
`@contextmanager` function `DirectoryNotEmpty.translate` is called by
`contextlib` (`rmdir_p`, `removedirs_p`), and the trace misses it.

## Audit and rulings

The blind audit (`path.audit.md`) found no edge that cannot happen. The
referee's ruling, adopted by the lead, kept J1, J2, J4 (60 edges) and the
38 Windows call-backs, and changed: -2 (`copytree` and `move` ->
`only_newer.wrapper`, J8), +1 F1 (`move -> Path.__repr__`, J12), +1 F2
(`TempDir.__new__ -> Path.__add__`, J2). Wording W1 (J4 count) and W2 (J9)
are applied. The totals stay 636 edges and 12 rejected trace edges. The
PyPy check (section "PyPy") then adds 3 edges: 639.

## PyPy

**Decision.** The release explicitly supports PyPy. Its CI runs
`pypy3.10` on `ubuntu-latest` (`.github/workflows/main.yml:52-53`), and no
support drop is declared. The aiocache precedent says that PyPy in the
release's CI is in scope. The declared bound `requires-python = ">=3.9"`
(`pyproject.toml:28`) also applies to PyPy, so the admitted PyPy versions
are those for Python 3.9 and later. I read the provided sources of PyPy
3.10 v7.3.19 and 3.11 v7.3.20 as text; I ran nothing.

**Names (a): 19 outside classes and modules checked.**
- One difference: hashlib's builtin SHA-1. On PyPy, `_sha1.sha1` is a
  function (`lib_pypy/_sha1.py:359`). It returns an instance of the pure
  Python class `_sha1.sha` (`:129`, with `update`, `digest` and `hexdigest`
  at `:231`, `:277` and `:326`). No path of that class equals
  `_sha1.sha1`, so I added `_sha1.sha.update`, `.digest` and `.hexdigest`
  at `979:21`, `990:44` and `1000:47`. That is +3 edges, the same name that
  the bottle ledger notes.
- Same paths as on CPython, so no change:
  - `_hashlib.HASH` (`lib_pypy/_hashlib/__init__.py:57`). PyPy's builtin
    MD5 class `_md5.md5` (`pypy/module/_md5`; `hashlib.py` uses the same
    fallback, `83-94`, `153-170`) is not a CPython path: CPython names its
    MD5 type `_md5.MD5Type` (see "Corrections of 2026-11-25")
  - the `io` classes (`_io.FileIO`, `TextIOWrapper`, `BufferedReader`,
    `BufferedWriter`, `BufferedRandom`, exported as `io.*`)
  - `functools.partial` (the pure Python class, `lib-python/3/functools.py:282`,
    whose `__call__` calls the function as CPython's does), `functools.reduce`,
    `functools.wraps`, `functools.lru_cache`
  - `re.Pattern` and `re.Match` (`re.py:279-280`)
  - the `itertools` objects, `types.GeneratorType.send`, `datetime.datetime`,
    `contextlib.contextmanager.helper`, `pwd`, `grp`, `warnings.warn`, the
    builtins.

**Call-backs (b): 31 library call-back sites checked.** The library
functions involved are PyPy's copies of the CPython 3.10 and 3.11 standard
library. Each copy has the statements that the edges of J3, J11 and J12
rest on:
- `posixpath.join` `path += sep + b` (`:86-88`), `ismount` `join(path, '..')`
  (`:202`) and `_joinrealpath` `rest.partition(sep)` (3.10 `:416`, 3.11 `:445`)
- `ntpath.normcase` `s.replace` (`:78`/`:79`), `splitdrive` `p.replace`
  (`:179`/`:186`) and `normpath` `path.replace` (`:511`/`:510`)
- shutil's `SameFileError` `{!r}` (`:234`/`:236`), `str(why)` (`:505`/`:519`)
  and the joins in `_copytree` and `_rmtree_safe_fd`
- `tempfile.mkdtemp`'s join (`:381`/`:382`) and `glob`'s `os.path.split`
- pathlib 3.10/3.11 converts with `str(a)` (`:581`/`:496`) and so calls no
  `replace` there. The CPython 3.12 witness keeps J11.

PyPy on Linux makes no call-back that CPython does not; a missing one
removes nothing, because the graph is the union of the runtimes. PyPy 3.11
on Windows makes five more. The referee admits that runtime (README,
"Implementation, version and platform combinations"), so they are in the
graph (Codex audit round 2, below).

**Branches (c).** The package has no branch on `sys.implementation` or
`platform`, and no import of a C accelerator with a Python fallback. Its
optional imports (`win32security`, `pwd`, `grp`) are judged in J9.

PyPy 3.9 sources were not provided at first, and `_sha1.sha` was assumed
for 3.9. The corrections of 2026-11-25 read PyPy 3.9 v7.3.16 (audit A1):
it has the same names, `_sha1.sha` included (see "Corrections of
2026-11-25").

## Outside names verified in the pinned test dependencies

The lead provided the unpacked, hash-checked wheels of the test environment
as plain text (appdirs 1.4.4, more_itertools 10.7.0). I read them and did not
run or import them.

- `appdirs.AppDirs` (`__init__.py:1914:39`): a plain class
  (`appdirs.py:407`). Its `__init__` takes the five keyword arguments that
  `SpecialResolver.__init__` passes and only stores them (`409-415`). The
  call names the class, as the micro-benchmark rule for an outside class
  says.
- `getattr(self.wrapper, prop_name)` (`1931:24`): the names that
  `get_dir` builds (`user_data_dir`, `site_config_dir` and the others) are
  properties of `AppDirs` (`417-450`). Each property calls the module
  function with the stored str arguments. That is library code calling
  library code, so it adds no edge, and no Path reaches it.
- more_itertools: the package never imports it. Only the tests use it
  (`ilen`). No ledger name depends on it.

## For the record

The writer read the standard library sources of the local CPython 3.9,
3.12, 3.13, 3.14 and 3.15 as text. It ran two small snippets on its own
`str` subclass and on `hashlib` (no package code): `str.partition`
returns the subclass instance when the separator is missing, and the
builtin hash classes are `_md5.md5` and `_sha1.sha1`. A larger probe of the
standard library with such a subclass was refused by the permission system
and did not run.

## Codex audit round 1

- Missing `Path.__radd__ -> Path.__add__` (`221:46`): applied. A direct
  call `Path('b').__radd__(Path('a'))` is admitted (README, django-constance
  ruling (d): no protocol-only rule for public special methods).
- Missing `Path.__rtruediv__ -> Path.__add__` (`243:49`): applied (a direct
  call with a Path `rel`; also the Windows 3.12 UNC chain of `ntpath.join`).
- Missing `-> Path.__add__` through the Windows CPython 3.12 UNC chain at
  `dirname` (`294:52`), `basename` (`298:53`), `splitpath` (`396:42`),
  `glob` (`652:42`), `iglob` (`670:33`), `makedirs` (`1378:20`),
  `renames` (`1324:19`) and `replace` (`1358:44`): all 8 applied. I checked
  `ntpath.py:211-216` and `:250` and `pathlib.py:430-432` in 3.12. Correction
  (Codex audit round 2): the chain of `split` and `join` also exists in
  CPython 3.11 and PyPy 3.11, whose `splitdrive` returns the original
  object for such a UNC path (`Python-3.11.9/Lib/ntpath.py`, `return p,
  p[:0]`), and `split` computes `d + head`. It does not exist in 3.9 and
  3.10 (`splitdrive` returns a slice) or from 3.13 (`splitroot` is C).
- The same pattern at callers that the auditor did not list:
  - +1 `Path.__new__ -> Path.__add__` (`185:31`): applied. It is the
    pathlib parse of a UNC target, J11.
  - Already in the graph: `__truediv__`, `__rtruediv__`, `joinpath`,
    copy/copy2/copytree/move/rmtree/merge_tree/TempDir.__new__ through
    `join`, and makedirs of copytree.
  - No edge: `removedirs` (it calls `rmdir` on the share root first, and
    that fails before `split`); `drive`/`splitdrive` (`root + tail` adds
    two empty strs). On CPython: `absolute`, `ismount`, `realpath`,
    `isabs`, `normpath` (C `normpath` from 3.11, a slice in 3.10). PyPy
    3.11 on Windows differs: see round 2.
- Rulings item (`Path.cwd -> TempDir.__init__` and the other
  `TempDir.__new__`-only rows): for the referee. My view: the auditor is
  right that a separator alone does not prove failure. `mkdtemp` succeeds
  when the random name happens to match an existing directory with no
  such child. But the same argument adds `TempDir.__init__` to all 18
  `__new__`-only callers of the ruling's table, so it is not mine to
  apply.
- Unsure item (a PyPy Windows console stream at `816:43` behind
  `PYPY_ENABLE_WINCONSOLEIO`): rejected. An undocumented environment
  switch of the interpreter is not admitted configuration, because the
  package's docs and tests do not set it. Nothing added.
- Metadata (`path.md:13`, stale PyPy note): fixed.
- Counts: 639 (388 inside, 251 outside) before; 650 (399 inside, 251
  outside) after; 12 rejected trace edges.
- Referee's ruling on the Rulings item (dispute 3; README "After Codex
  audit round 1", ruling (c)): for the auditor. Applied +18
  `-> path.TempDir.__init__` at the 18 sites of the ruling's table, and
  annotated `409:57`. The notes no longer say that a separator makes
  `mkdtemp` fail. Counts: 650 before; 668 (417 inside, 251 outside) after;
  12 rejected trace edges.

## Codex audit round 2

I read the PyPy 3.11 v7.3.20 and 3.10 v7.3.19 sources and CPython 3.10.14
and 3.11.9 (`deps/_cpython`) as text. PyPy 3.11's `nt` exports no
`_path_normpath` (none in `pypy/module/posix`), so its `ntpath.normpath`
is the Python fallback (`lib-python/3/ntpath.py:494`). That fallback calls
`path.replace` and `splitdrive`. 3.11's `splitdrive` returns the original
object for a UNC path without a third separator, and the fallback ends
with `prefix + ...`.

- Missing `absolute`, `normpath`, `realpath -> Path.__add__` (`270:52`,
  `278:53`, `282:53`): first for the referee, applied after the ruling (below). Only PyPy 3.11 on
  Windows gives them. CPython 3.10 `splitdrive` returns a slice, and
  CPython 3.11 and later normalize in C (`Python-3.11.9/Lib/ntpath.py:493`).
  PyPy is admitted by a Linux CI job, and Windows by the classifier and the
  CPython CI. Whether the cross product is admitted is a scope question.
- Missing `copymode`, `copystat -> Path.replace` (`1506:24`, `1509:24`):
  first for the referee (the same question), applied after the ruling (below).
  `os.path.realpath(dst, strict=True)` for a symlink `dst` on Windows is in
  shutil 3.11 and 3.12 (`Python-3.11.9/Lib/shutil.py:309`, `389`; 3.12
  `:313`, `:393`), but CPython's `realpath` starts with the C `normpath`,
  so only PyPy 3.11 calls `.replace` on the Path. CPython 3.10 and PyPy
  3.10 shutil have no `realpath` call.
- The same pattern at callers that the auditor did not list (also PyPy
  3.11 on Windows only, so also for the referee, none applied):
  - `absolute` by the normal path: wrong. The referee corrected it: PyPy's
    `abspath` is `normpath(_getfullpathname(path))` (`ntpath.py:576`), so
    a successful call normalizes a plain str. The edge rests on the
    auditor's embedded-null witness alone.
  - `ismount` (`abspath`), `move` (`_destinsrc`'s `abspath`) and
    `copymode`/`copystat` for a UNC `dst` (`Path.__add__`; the auditor's
    Unsure 2): these give no new pair beyond the five, except
    `copymode`/`copystat -> Path.__add__`, which needs a UNC share root
    that is a symlink, which I could not show.
  - CPython 3.11's `split`/`join` UNC chain adds witnesses to pairs that
    are already in the graph, and no new pair.
- Unsure 1 (CPython `_WindowsConsoleIO` for `CONIN$` at `816:43`): it
  needed `Modules/_io/_iomodule.c` and `winconsoleio.c`. After the lead
  provided them (3.11.9, 3.13.1), applied +1
  `path.Path.chunks.<lambda1> -> io._WindowsConsoleIO.read` (J7). No other
  io site gets this receiver.
- Unsure 2: covered above, not counted.
- Metadata: `path.md:363` (no PyPy-only call-back) is corrected for PyPy
  on Windows. `path.md:414` (3.11 `splitdrive` returns slices) is
  corrected. The ledger note at `278:53` now says that CPython 3.10 also
  normalizes in Python. The reconciliation item needs no action.
- Counts: 668 (417 inside, 251 outside) before; 669 (417 inside, 252
  outside) after Unsure 1; 12 rejected trace edges. Accepted as real: 1
  missing (Unsure 1), 0 false.
- Referee's ruling on the scope question: PyPy 3.11 on Windows is
  admitted (README, "Implementation, version and platform combinations").
  Applied the five pairs, with notes that cite the PyPy sources:
  `absolute` (`270:52`, embedded-null witness), `normpath` (`278:53`),
  `realpath` (`282:53`) -> `Path.__add__`, and `copymode` (`1506:24`),
  `copystat` (`1509:24`) -> `Path.replace`. No other pair changes
  (`ismount` and `move` already have `__add__`; there is no
  `copymode`/`copystat -> __add__`). Final counts: 674 edges (422 inside,
  252 outside), 12 rejected trace edges.

## Codex confirmation pass

No missing or false edge. Two notes were corrected: `isabs` calls `replace` on the Path only in CPython 3.9 and 3.10 (3.11 uses a slice); the reason of the `Multi.__iter__` default now names `Path.__enter__`/`__exit__`, which keep a Multi value but do not iterate it. 674 edges, unchanged.

## Corrections of 2026-11-25

**The Windows console stream (`__init__.py:816:43`, `chunks.<lambda1>`).**
The callee `io._WindowsConsoleIO.read` is renamed `_io._WindowsConsoleIO.read`
(one edge renamed). `io`
imports the class outside its `__all__`, only to register it with
`RawIOBase`, so `io._WindowsConsoleIO` is no public path (README, batch 7,
"A private class that a public module re-exports"), and batch 8's ruling
"A C type exported under a module attribute other than its type name"
names it by the attribute under which the defining module exports it. The
name is the same on every runtime that path admits on Windows:

| Runtime | Definition | Exported by `_io` as | `io` |
|---|---|---|---|
| CPython 3.9 to 3.15 | `Modules/_io/winconsoleio.c`, type name `"_io._WindowsConsoleIO"` (`:1117` of 3.9.25, `:1131` of 3.11.18, `.name` at `:1234` of 3.12.16, `:1269` of 3.15.2); `open` makes it for a console name (`_iomodule.c:380` of 3.9.25, `:324` of 3.11.18, `:329` of 3.13.18) | `_WindowsConsoleIO` (`PyModule_AddType`, `_iomodule.c:737` of 3.9.25, `ADD_TYPE` `:704` of 3.12.16, `:710` of 3.15.2) | `from _io import _WindowsConsoleIO` and `RawIOBase.register` only (`Lib/io.py:95-99` of 3.9.25, `110-114` of 3.10.22, `111-115` of 3.11.18, `94-98` of 3.15.2) |
| PyPy 3.9, 3.10 and 3.11 on Windows | `pypy/module/_io/interp_win32consoleio.py`, TypeDef `'_io.WinConsoleIO'` with `read` (`:522-531` of 3.9 v7.3.16, `:528-537` of 3.10 v7.3.19, `:529-538` of 3.11 v7.3.23); `open` makes it for a console name (`interp_io.py:123-126` of 3.9, `113-116` of 3.11) | `_WindowsConsoleIO` (`pypy/module/_io/moduledef.py:33` of 3.9, `:34` of 3.10 and 3.11) | as CPython (`lib-python/3/io.py:95-99` of 3.9, `110-114` of 3.10, `111-115` of 3.11) |

The other `io` names of the ground truth (`TextIOWrapper`,
`BufferedReader`, `BufferedWriter`, `BufferedRandom`, `FileIO`) are in
`io.__all__` and stay.

**The builtin hash objects (`_hash`, `read_hash`, `read_hexhash`:
`__init__.py:979:21`, `990:44`, `1000:47`).** `hashlib.new(hash_name)`
(`977`) returns an OpenSSL `_hashlib.HASH` or, by hashlib's fallback, a
builtin MD5 or SHA-1 object (J6). Batch 8's ruling "A C type exported under
a module attribute other than its type name"
(`selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md`) and the
ruling "Public class aliases by configuration" (Rulings for the
corrections of 2026-11-25, `ruling-names-2.md`) name each class by a public class alias where the attribute holds it, else
by the attribute that its module exports, else by its type name:

| Runtime | MD5 | SHA-1 |
|---|---|---|
| CPython 3.9 to 3.15 | type `"_md5.md5"`, exported as `MD5Type` (`Modules/md5module.c:583` of 3.9.25, `:358` of 3.15.2); `hashlib.md5` is a factory: `_md5.MD5Type` | type `"_sha1.sha1"`, exported as `SHA1Type` (`sha1module.c:560` of 3.9.25, `:568-570` of 3.10.22, `:353` of 3.15.2); `hashlib.sha1` is a factory: `_sha1.SHA1Type` |
| PyPy 3.9, 3.10, 3.11 | the class `_md5.md5` (`pypy/module/_md5/moduledef.py:22` of 3.9, 3.10 and 3.11), which the fallback binds as `hashlib.md5` (`lib-python/3/hashlib.py:94` of 3.9 v7.3.16, `92-94` of 3.10): `hashlib.md5`, and `_md5.md5` beside it at `hashlib.new` (the lead's decision at avro `schema.py:337`) | `_sha1.sha1` is a function (`lib_pypy/_sha1.py:347` of 3.9, `:359` of 3.10) that returns the class `_sha1.sha` (`:117` of 3.9, with `update`, `digest` and `hexdigest` at `:219`, `:265`, `:314`; `:129` of 3.10): `_sha1.sha` |

So at each of the three sites `_sha1.sha1.X` is renamed `_sha1.SHA1Type.X`
(it names no class on any runtime), and `_md5.MD5Type.X` and
`hashlib.md5.X` are added; `_hashlib.HASH.X`, `_md5.md5.X` and
`_sha1.sha.X` stay; on PyPy `_hashlib.HASH` is the class of
`lib_pypy/_hashlib/__init__.py:34` (3.9), `:57` (3.10). 3 edges renamed, 6
added: 680 edges (422 inside, 258 outside); no trace edge changes.

## Corrections of 2026-11-28

**Every hash name of hashlib (`_hash`, `read_hash`, `read_hexhash`:
`__init__.py:979:21`, `990:44`, `1000:47`; the audit of the corrections of
2026-11-28, N7a; the ruling is
`selection/corrections-2026-11-28/rulings/n7a.md`).** The public methods
`read_hash` and `read_hexhash` document their `hash_name` with "List of
supported hashes can be obtained from :mod:`hashlib` package." (`985`,
`995`; `docs/api.rst` renders them with `:members:`). By scope rule B2 the
documentation names the role's values, as avro's `Schema.fingerprint`
docstring did (avro J5): every name that `hashlib.new` accepts on an
admitted build. `_hash` is private, so its `hash_name` is what its package
callers pass: `read_md5`'s `'md5'` and the two public parameters (rule B).
J6, which kept `md5` and `sha1` only, yields: a project judgement cannot
override the global rules. hashlib's documentation sends the reader to
`algorithms_guaranteed` and `algorithms_available`
(`Lib/hashlib.py:14-19` of 3.9.25); a name outside the guaranteed set goes
only to `_hashlib.new`, which makes `_hashlib.HASH` or `_hashlib.HASHXOF`,
so only the guaranteed names change a callee. The classes that each
guaranteed name makes through `hashlib.new(name)` (OpenSSL, else the
builtin constructor; BLAKE2 always builtin), named by the public alias
where hashlib's fallback binds the class, else by the exported type
attribute, else by the type name (`ruling-names-2.md`,
`b8-ruling-c-type-names-1.md`), with the private names kept beside the
aliases at `hashlib.new` (the lead's decision at avro `schema.py:337`):

| Hash | CPython 3.9 | CPython 3.10, 3.11 | CPython 3.12 to 3.15 | PyPy 3.9 to 3.11 |
|---|---|---|---|---|
| sha224, sha256 | `_sha256.SHA224Type`, `SHA256Type` (`sha256module.c:718`, `:720`) | the same (`:720`, `:725` of 3.10.22; `:723`, `:728` of 3.11.18) | `_sha2.SHA224Type`, `SHA256Type` (`sha2module.c:852`, `:855` of 3.12.16; `:864`, `:867` of 3.15.2) | the classes `_sha256.sha224`, `sha256` (`lib_pypy/_sha256.py:230`, `:206` of 3.9), bound as `hashlib.sha224`, `sha256` |
| sha384, sha512 | `_sha512.SHA384Type`, `SHA512Type` (`sha512module.c:776`, `:778`) | SHA-384 by its type name `_sha512.sha384`, SHA-512 as `_sha512.SHA384Type` (the export is overwritten, `:782`, `:788` of 3.10.22; `:785`, `:791` of 3.11.18) | `_sha2.SHA384Type`, `SHA512Type` (`:858`, `:861` of 3.12.16) | the classes `_sha512.sha384`, `sha512` (`_sha512.py:258`, `:234` of 3.9), bound as `hashlib.sha384`, `sha512` |
| blake2b, blake2s | `hashlib.blake2b`, `blake2s` (always the builtin classes) | same | same | same |
| sha3_224 to sha3_512 | the types `_sha3.sha3_224` to `sha3_512` (`_sha3/sha3module.c:731-734`), bound as `hashlib.sha3_*` | same (`PyModule_AddType`, `:770` of 3.10.22, `:617` of 3.11.18) | same (`sha3module.c:580-588` of 3.12.16, `:666-674` of 3.15.2) | the classes `_sha3.sha3_*` (`_sha3/__init__.py:88-100` of 3.9), bound as `hashlib.sha3_*` |
| shake_128, shake_256 | the types `_sha3.shake_*` (`:741-742`), bound as `hashlib.shake_*`; OpenSSL: `_hashlib.HASHXOF` (`_hashopenssl.c:2208`) | same; `HASHXOF` `:2165` of 3.10.22 | same; `HASHXOF` `:2280` of 3.12.16, `:2809` of 3.15.2 | the classes `_sha3.shake_*` (`:104`, `:108` of 3.9); OpenSSL: `_hashlib.HASH` (PyPy's `_hashlib.new` makes no other class without data) |

The `digest` and `hexdigest` of every SHAKE class take a required `length`
(`_sha3.shake_128.digest`, `Modules/_sha3/clinic/sha3module.c.h:121` of
3.9.25; `_hashlib.HASHXOF.digest`, `_hashopenssl.c:720` of 3.9.25; PyPy
`_shake.digest(self, length)`, `lib_pypy/_sha3/__init__.py:66`, `:84` of
3.9), and path calls them without arguments, so the binding fails before
entry and `990:44` and `1000:47` get no SHAKE callee (B4, as at avro
`schema.py:338:24`); `update` binds for every class.

Added, all outside, none removed: at `979:21` 31 callees (`.update` of
the 26 receivers below, `_hashlib.HASHXOF`, `hashlib.shake_128`,
`hashlib.shake_256`, `_sha3.shake_128`, `_sha3.shake_256`), at `990:44`
and `1000:47` 26 each (`.digest`, `.hexdigest`). The 26 receivers:
`_sha256.SHA224Type`, `_sha256.SHA256Type`, `_sha512.SHA384Type`,
`_sha512.SHA512Type`, `_sha512.sha384`, `_sha2.SHA224Type`,
`_sha2.SHA256Type`, `_sha2.SHA384Type`, `_sha2.SHA512Type`,
`hashlib.sha224`, `hashlib.sha256`, `hashlib.sha384`, `hashlib.sha512`,
`_sha256.sha224`, `_sha256.sha256`, `_sha512.sha512`, `hashlib.blake2b`,
`hashlib.blake2s`, `hashlib.sha3_224` to `hashlib.sha3_512` and
`_sha3.sha3_224` to `_sha3.sha3_512`. 83 site-callee entries and 83 graph
edges: 680 to 763 edges (422 inside, 341 outside).

The trace (`dynamic/path.json`, CPython 3.14.10 with OpenSSL) runs only
`read_md5` and `read_hexhash('md5')` (`tests/test_path.py:251`, `256`):
`_hash -> _hashlib.HASH.update`, `read_hash -> _hashlib.HASH.digest` and
`read_hexhash -> _hashlib.HASH.hexdigest`, all already in the graph. It
records none of the 83 added edges, which is what the tests' one hash
name gives, and it records no edge at these callers that the ground truth
lacks: no trace edge is rejected or changes.
