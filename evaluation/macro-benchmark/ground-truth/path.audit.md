# path: blind audit of the ground truth

Batch 6. Release v17.1.1, commit `0f86209f`. Audited files, as
they were on 2026-11-22: `path.ledger` (2026 lines, 5 default rejections),
`path.json` (636 edges: 388 inside, 248 outside), `path.added.json` (149
edges from reading only), `path.rejected.json` (12 trace edges), `path.md`
(judgements J1 to J13). `check.py path` reports no errors.

I read the package source, its README, docs, `pyproject.toml`, the CI file
and `tests/test_path.py` as data, and the CPython standard library sources of
3.12, 3.13, 3.14 and 3.15 that exist on this machine (read only). No CPython
3.9 to 3.11 source exists here, so the writer's claims that rest on those
versions only (`ntpath.isabs` and `splitdrive` with `.replace` in 3.9 to
3.11, `ntpath.normpath` in 3.9) are not checked by me; each such edge also
holds on 3.12 or I say so. I ran no package code, no probe and no snippet,
and no analysis tool. The appdirs wheel text was not needed.

## Summary

| Id | Kind | Edge change | Confidence |
|---|---|---|---|
| F1 | missed edge | +1 `Path.move -> Path.__repr__` | likely |
| F2 | missed edge, if J2 covers TempDir's `dir` | +1 `TempDir.__new__ -> Path.__add__` | doubtful (writer's answer wanted) |
| F3 | edges that a rule may not support (ruling) | -2 or 0 (`copytree`, `move` -> `only_newer.wrapper`) | ruling |
| L1 | J4, environment as witness (ruling) | -57 or 0 | ruling |
| L2 | Windows library behaviour (ruling or confirm) | -38 or 0 | ruling |
| W1 | wording: J4 count | 0 | certain |
| W2 | wording: J9 stub unpacking | 0 | certain |
| R1 | README: how to split a draw by kind | 0 | remark |

Blind sample: 96 sites, 90 agree, 6 differ; all 6 are my errors. The
binding check finds no call that cannot bind (346 pairs).

## Step 1: blind re-derivation

The skeleton without the ledger (scratch benchmark under
`$TMPDIR/audit-path/`, `check.py --skeleton path`) has 1018 sites:
403 call, 65 decorator, 449 getattr, 101 other implicit (op, iter, with,
format); 26 value sites. getattr sites are 44% of the sites, and nearly all
have only the two `SpecialResolver` `__getattr__` candidates, so I drew by
kind. I numbered the sites from 0 in (line, column) order, module by module
(`path`, `path.classes`, `path.compat.py38`, `path.masks`,
`path.matchers`), and drew with `rng = random.Random(20261122)`:
`rng.sample(explicit, 35)`, then `rng.sample(getattr, 20)`, then
`rng.sample(other, 15)`. No value site fell in the draw, so the sample is
70 + 26 = 96 sites. My answers, with the assumptions I made before I opened
any file of the writer, are in `$TMPDIR/audit-path/blind.md`
(scripts `draw.py`, `show.py`; draw `sample.json`).

| Group | Sites | Agree | Differ |
|---|---|---|---|
| Explicit | 35 | 30 | 5 |
| getattr | 20 | 20 | 0 |
| Other implicit | 15 | 15 | 0 |
| Value sites | 26 | 25 | 1 |
| **All** | **96** | **90** | **6** |

The 6 differences, all auditor errors:

- `185:31` `super().__new__(cls, other)`: I missed `Path.replace` (J11).
  `str.__new__` calls `__str__` of the `pathlib.Path` that `Path.replace`
  passes; from 3.12, pathlib keeps the raw argument (the client's target
  Path) and `_parse_path` calls `path.replace(altsep, sep)` on Windows
  (checked: `pathlib.py:394` in 3.12, `pathlib/_local.py:264` in 3.13,
  `pathlib/__init__.py:288` in 3.14, `:291` in 3.15).
- `524:32`, `1325:32`, `1501:32` `self._next_class(...)`: I had
  `TempDir.__new__` for a MultiTempDir receiver but not `TempDir.__init__`.
  The argument can be a name without a separator, so `mkdtemp` succeeds
  and `__init__` runs. Same premise (J4) as mine; my answer was incomplete.
- `1000:47` `.hexdigest()`: I listed the builtin fallback classes of any
  algorithm (blake2). The writer names `_md5.md5` and `_sha1.sha1` only,
  the algorithms that the package, tests and docstring pass (J6). The
  aiocache rule (B2: a client string that selects an outside object names
  what the package, tests and documented examples pass) supports the
  writer.
- `1675:30` `copy_function(source, dest)`: I missed the Windows call-backs
  of `ntpath.join` in `shutil.copy2` (`Path.replace` in `splitroot` on
  3.12, `Path.__radd__` in `result_drive + result_root + result_path`
  for a relative Path).

Two of my answers were conditional on J2 (`325:36` `stem + self.suffix`,
`matchers.py:58:33`); the writer's J2 settles both as I had them.

## Step 2: exhaustive checks

**Dispatch sets (B1).** Receivers of the inherited Path methods: Path,
ExtantPath, ExtantFile, TempDir, the `using_module` classes and the
`Multi.for_class` classes; `_MultiPathType` is never instantiated. The
ledger agrees everywhere: `self._validate()` (`190:23`: the three
`_validate`), `Path.__enter__ -> Path.cwd`, `TempDir.__exit__ ->
Path.rmtree`, `TempDir.__enter__` (Path constructors, `TempDir.__new__` for a
MultiTempDir), `ClassProperty.__get__` at all 39 `_next_class` loads (39
loads in the skeleton, 39 accepted), `classes.py:10:46` (the four
classmethods). Role sets: `error_fn` (Handlers.strict, warn, ignore),
`match` (`Null.__call__`, `Pattern.__call__`), `traverse()` (`Path.is_dir`,
`functools.partial.__call__`), `mask` and `f1`/`f2` in `compose`
(`functools.partial.__call__`, the inner lambda, `simple.<lambda1>`),
`ignore` (`path.Path.<lambda1>`), `copy_function` (`shutil.copy2`,
`only_newer.wrapper`; see F3), `cls(input)` in `detect`: all as I derived.

**Default rejections.** I checked each against the source:
`SpecialResolver`/`ResolverScope.__getattr__` (453 sites: every attribute
that package code loads on these objects exists; the four explicit
`getattr(...)` calls are on a str, `os`, an `AppDirs` and a `Pattern`);
`ClassProperty.__get__` (71: no other name is a ClassProperty, and the
package never loads `special`); `multimethod.__get__` (110: the package
never loads `joinpath`); `Multi.__iter__` (66: package code iterates no
Multi instance, `in` uses `str.__contains__`, and no library function that
gets a Path iterates its characters; `Multi.__iter__`'s own map is iterated
by the client); `Path`/`TempDir` `__enter__`/`__exit__` (18: the with items
are `contextlib.suppress`, file objects and `translate()`). All correct.

**Functions without a caller** (79 nodes, the 5 modules among them): each is called only by clients
or not at all (`__rtruediv__`: no package `str / Path`; `drive`, `stem`,
`relpath`, `realpath`, `splitdrive`, `joinpath`, `home`, the shutil
wrappers, `SpecialResolver.__init__` through the client's partial,
`Permissions.__str__`, `Traversal`). No missed caller found.

**Special methods, properties, op and format sites.** Every `+`, `/` and
f-string site matches my reading, including `1761:26` (`Path.__add__`),
`389:63` (`__radd__`, J2), `591:59` `{exc}` (`OSError.__str__` formats the
Path filename with `%R`: `Path.__repr__`) and `602:56` (no call-back). The
property loads (`name`, `suffix`, `parent`, `bits`, `symbolic`) are right.

**Library call-backs (J3, J5, J11, J12).** I checked the 31 sites that name
a call-back against the 3.12 to 3.15 sources: `posixpath.join` (`path +=
sep + b`: `__add__`; `sep + b` and `str + Path`: `__radd__`), `abspath`
(join with cwd: `__radd__`), `realpath` 3.12 (`partition` and `join('',
name)`: `__radd__`), `ismount` (`join(path, '..')`: `__add__`),
`ntpath.normcase` (both branches `s.replace`), `ntpath.splitroot` 3.12
(Python, `p.replace`), `splitdrive` 3.12 (`root + tail`), the ntpath
`abspath` fallback for an embedded null (J5), `shutil.copy`, `copy2`,
`copytree`, `rmtree`, `move`, `copyfile` (`SameFileError` with `{!r}`),
`_copytree`'s `str(why)` (`shutil.py:600`, `606` in 3.15), `tempfile.mkdtemp`
(`prefix + name + suffix`, join), `glob._iglob` (`os.path.split`),
`copymode` and `copystat` (no call-back), the C functions of `os` (none).
All edges hold, except two gaps (F1, F2).

**Outside names.** I read all 164 outside callee names against their
sites: `os.path.*`
for the package's module (J1), `ntpath.normcase` for `CaseInsensitive`,
`pathlib.Path`, `pathlib.PosixPath.replace` and `WindowsPath.replace`
(platform classes of the receiver), `io.*` classes by mode (J7),
`_hashlib.HASH`, `_md5.md5`, `_sha1.sha1` (J6), `contextlib.contextmanager.helper`,
`functools.partial.__call__`, `types.GeneratorType.send`,
`<builtin>.property.__init__` for `@classes.ClassProperty`,
`<builtin>.OSError.__init__` for `DirectoryNotEmpty(...)`,
`<builtin>.property.setter`, the missing module `win32security.*`. No
naming error. `masks.Permissions(...)` (`1143:33`) rightly has no callee.

**Rejected trace edges (12).** The 9 `ntpath.*` edges come from the tests'
`using_module(ntpath)` and `p.module = ntpath` (client values, J1); the
tests' `results.append` as `os.chroot`; `shutil.ignore_patterns(...)` as
`ignore`; `shutil.copy2` as `only_newer`'s `copy_func`. All are client
values (B2, B5). Correct. The trace edges that the tests make through their
ntpath module and that the graph keeps (`__truediv__`, `absolute`,
`basename`, `dirname`, `fnmatch`, `normcase`, `relpathto`, `splitdrive`,
`splitpath` -> `Path.replace`) each have a Windows witness through
`os.path` (L2).

## Step 3: binding check

346 pairs of an explicit site and a package callee (script `binding.py`).
All bind: the constructors take one argument (`Path.__new__`,
`Path.__init__`) or `*args, **kwargs` (TempDir); the call-backs are
operators or `replace(old, new)`; `ignore(self, [...])` binds
`Path.<lambda1>(dir, contents)`; `source.merge_tree(dest, symlinks=...,
copy_function=..., ignore=...)` binds the keyword-only parameters;
`removesuffix(self, self.name)` binds the 3.9 definition. The one call that
cannot bind, `pattern.normcase(self.name)` for a Path pattern
(`633:24`), has no edge in the ledger, as it should. No change.

## Findings

### F1. Missed edge: `Path.move -> Path.__repr__` (+1, likely)

`1541:29` `shutil.move(self, dst, copy_function=copy_function)`. When
`os.rename` fails for a directory, `shutil.move` calls `copytree(src,
real_dst, copy_function=copy_function, symlinks=True)` (`shutil.py:945`,
3.15), and `_copytree` formats each `OSError` with `str(why)`
(`shutil.py:600`, `606`). `OSError.__str__` formats the file name with
`%R`. `srcname = os.path.join(src, name)` is a Path (src is self), and so
is `dstname` for a Path `dst`. Witnesses: `os.readlink(srcname)` or
`os.symlink(linkto, dstname)` fails under `symlinks=True`, or `copystat(src,
dst)` fails on the Path `src` (`606`). A second witness: when `os.rename`
fails for a file (EACCES on the target directory) and the target is a hard
link to `src`, `copy_function(src, real_dst)` is `shutil.copy2`, whose
`copyfile` raises `SameFileError("{!r} and {!r} ...")` (`shutil.py:293`).
The ledger already gives `Path.copytree -> Path.__repr__` for the same
`str(why)` (J12); `move` reaches the same code. Add `path.Path.__repr__` at
`1541:29` and name it in J12.

### F2. Possible missed edge: `TempDir.__new__ -> Path.__add__` (+1, doubtful)

`1994:35` `tempfile.mkdtemp(*args, **kwargs)`. `mkdtemp` keeps `dir` as
given (`_sanitize_params` only infers the type) and computes
`_os.path.join(dir, prefix + name + suffix)`. With a Path `dir`,
`posixpath.join` runs `path += ...` on it: `Path.__add__`. `dir` has the
role of a path, and the TempDir docstring says that TempDir takes the
parameters of `mkdtemp`; the tests pass `dir=tmpdir` (a `py.path.local`, a
client object). J2 admits a Path for every path-role `str` parameter,
because the package documents a Path as a drop-in string. If that reading
covers TempDir's unannotated `dir`, the edge is missing. The same Path `dir`
also gives `Path.__radd__` (3.12 and later: `abspath` of the joined Path)
and `Path.replace` (Windows) at this site without J4, so these two would no
longer depend on J4. The writer should answer whether J2 covers `dir`.

### F3. Ruling: `only_newer.wrapper` in `copytree` and `move` (J8; -2 or 0)

`1529:28` and `1541:29` name `only_newer.wrapper`, which shutil calls back
as `copy_function`. Evidence for the role: `only_newer` returns `_CopyFn`,
the `TYPE_CHECKING` alias `Callable[[str, str], object]` that also
annotates the three `copy_function` parameters; only `merge_tree`'s
docstring passes `only_newer(shutil.copy2)` (`__init__.py:1651`).

- Against: B2 says that an annotation that types a parameter as a bare
  callable is no evidence for any package value, and `_CopyFn` is a bare
  callable. Ruling 7 of batch 5 reads documentation one entry at a time,
  so the `merge_tree` example admits the wrapper for `merge_tree` only.
  Then the 2 edges go.
- For: the shared alias makes one copy-function role across the three
  methods, as the more-itertools ruling found one iterable role, and the
  factory-output clarification admits `only_newer`'s output in that role.
  Then the edges stay.

The README does not decide whether a shared bare-callable alias makes one
role. The smaller extension of the rules is the reading against (B2's
bare-callable sentence and ruling 7 are explicit). `merge_tree ->
only_newer.wrapper` (traced) stays in both readings.

### L1. Ruling: J4, an environment value as witness (-57 or 0)

My blind view agrees with the writer's facts. B1 decides that `TempDir` is a
class of the inherited classmethods and of the ClassProperty `special`:
`TempDir.cwd()`, `TempDir.home()` and `TempDir.special(...)` are public
calls, so `Path.cwd`, `Path.home` and `Multi.detect -> TempDir.__new__`
hold without anything else (`mkdtemp` is entered and raises on an absolute
suffix). These 3 edges are decided.

The other 57 edges need a value without a separator from the environment:
`HOME=cfg` for `Path.home -> TempDir.__init__`; `XDG_CONFIG_HOME=cfg` for
`detect -> TempDir.__init__`; `XDG_CONFIG_DIRS=a:b` with `multipath=True`
for a MultiTempDir instance, whose `self._next_class(v)` runs
`TempDir(v)` (the other 35 `__new__` edges and 18 `__init__` edges, and
`TempDir.__new__ -> Path.__radd__` and `-> Path.replace`, which need a Path
suffix): 2 + 35 + 18 + 2 = 57. The README has no rule on an environment variable that a library
(appdirs, `posixpath.expanduser`) reads as data. The tinytag ruling is
narrower: it admits an environment variable that the package itself reads
when the documentation or the test setup sets it. Two readings:

- Environment values are client inputs, like the contents of the file
  system (and the tests set `XDG_CONFIG_HOME`, `XDG_CONFIG_DIRS` and `HOME`
  with monkeypatch): all edges stay.
- Library results that depend on the environment count only as the
  tinytag ruling allows: the 57 edges go (55 if F2 is accepted, which
  gives the two TempDir call-backs another witness).

### L2. Ruling or confirmation: library behaviour on Windows (-38 or 0)

The package supports Windows: `Operating System :: OS Independent`, the
`sys.platform == "win32"` branches, `pywin32` in the test extra, and
`windows-latest` in `.github/workflows/main.yml`. The README decides the
package's own platform branches (netaddr: a branch on the platform runs if
a supported platform takes it), and it names library behaviour by version
(fastjsonschema ruling 4; "Include names across the release's admitted
Python 3 versions"); the outside-names clarification names both
`PosixPath` and `WindowsPath`. It does not say in words that library
behaviour on a supported platform is in scope. My view: it is, and that is
the smaller extension (a supported platform is treated like a supported
version). 38 edges depend on it: 30 `-> Path.replace` (every caller except
`Pattern.__call__`, whose `ntpath.normcase` is a package value on every
platform), and 8 `-> Path.__radd__` (`copy`, `copy2`, `copytree`, `drive`,
`ismount`, `merge_tree`, `rmtree`, `splitdrive`). 9 of the 30 are in the
trace only through the tests' ntpath module; under the other reading they
move to `path.rejected.json` (J1).

### W1. Wording: the J4 count (no change)

`path.md` J4 says 59 edges, 20 of them to `TempDir.__init__`. The graph has
58 constructor edges from other callers (38 `TempDir.__new__`, 20
`TempDir.__init__`), and 2 more edges rest on J4 (`TempDir.__new__ ->
Path.__radd__` and `-> Path.replace`). Give the exact list or count.

### W2. Wording: J9, the stub unpacking (no change)

J9 says that a stub yields no items, so `account, domain, typecode =
win32security.LookupAccountSid(...)` raises. The README's missing-module
rule fixes names only, and a branch that the library's answer decides still
runs (dagster-pipes, ruling 2 of batch 4). The real `LookupAccountSid`
returns a 3-tuple. The return line has only str operations, so no edge
changes; reword the reason.

### R1. README: the split of a draw by kind (remark)

The batch-6 rule says that the draw is split by kind where one kind
dominates, with tinytag's 50 and 20 as the example, but gives no rule for
the shares. I used 35 explicit, 20 getattr and 15 other implicit sites,
because the getattr sites are 44% and carry nearly no edges.

## The judgement calls asked about

- **J4** (`_next_class` and `TempDir`): B1 decides 3 edges; 57 need a
  ruling on environment witnesses (L1).
- **J2** (Path in `str` parameters): decided by B2. The annotation `str`
  names a base class that the package implements for the purpose of a
  path string (README.rst: Path objects "may be passed directly to other
  APIs that expect simple text representations of paths"), so a path-role
  parameter admits a Path; a parameter of another role does not (B3, "a
  value that the package never produces for that role"). The writer's split
  of roles is right. The open edge is F2.
- **J3, J5, J11, J12** (library call-backs): decided by B5 (the call-back
  rule for objects that the package passes to library code; precedents
  pyrate-limiter `Rate.__repr__` through logging, structlog). The Windows
  part is L2. Missing: F1.
- **J1** (`module`): decided by B2's last sentence (a value from outside
  the package that the client passes is a client callback, whatever the
  documentation shows) and B5. `os.path` only. The other reading (a
  client's module names its functions) would add the 9 rejected trace
  edges and about 30 `ntpath.<name>` edges, one per caller of
  `self.module`.
- J6, J7, J9, J10, J13: supported by B2 (aiocache rule), the Concrete types
  clarification, the version and platform rules, B4 and the lazy-object
  rules. J8: F3.

## Re-check

To do after the writer applies or answers F1 to F3 and W1, W2, and after the
referee rules on L1 and L2.

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-path-wcio` (f3e5295, PR #106) against `main`
(14798e4): four outside edges renamed and six added in `path.json`,
`path.added.json`, `path.ledger` and `path.md`; `evaluation/metrics.json`
is not recorded yet (the lead records it at the merge). I read
`path/__init__.py` from the inputs image, and CPython 3.9.25 to 3.15.2 and
PyPy 3.9 v7.3.16, 3.10 v7.3.19 and 3.11 v7.3.23 from the dependency
sources, as text. Nothing ran; no PyCG output was read.

| Site | Change | Verdict | Evidence |
|---|---|---|---|
| `__init__.py:816:43` `f.read(size)` | `io._WindowsConsoleIO.read` renamed `_io._WindowsConsoleIO.read` | agree | `io` imports the class outside `__all__` only to register it (`Lib/io.py:95-99` of 3.9.25, `110-114` of 3.10.22, `111-115` of 3.11.18, `95-99` of 3.12.16, `94-98` of 3.15.2; PyPy `lib-python/3/io.py:95-99` of 3.9, `110-114` of 3.10, `111-115` of 3.11), so it has no public alias (batch 7, the pyfiglet ruling, which names this very class `_io._WindowsConsoleIO`). CPython: type name `"_io._WindowsConsoleIO"` (`winconsoleio.c:1117` of 3.9.25, `:1129` of 3.10.22, `:1131` of 3.11.18, `.name` `:1234` of 3.12.16, `:1269` of 3.15.2), added to `_io` by `ADD_TYPE` (`_iomodule.c:737` of 3.9.25, `:752` of 3.10.22, `:704` of 3.12.16, `:710` of 3.15.2). PyPy on Windows: `_io` exports `W_WinConsoleIO` (TypeDef `'_io.WinConsoleIO'`, with `read`) as `_WindowsConsoleIO` (`moduledef.py:33` of 3.9, `:34` of 3.10 and 3.11; `interp_win32consoleio.py:523`, `531` of 3.9, `528-537` of 3.10), and `open` makes it for a console name (`interp_io.py:113-116` of 3.11) |
| `979:21`, `990:44`, `1000:47` | `_sha1.sha1.X` renamed `_sha1.SHA1Type.X` | agree | `hashlib.new(hash_name)` (`977`) falls back to the factory `_sha1.sha1`; `_sha1` exports its type as `SHA1Type` on CPython 3.9 to 3.15 (checked in the bottle audit); on PyPy `_sha1.sha1` is a function returning the class `_sha1.sha`, so `_sha1.sha1` names no class on any runtime |
| the three sites | `_md5.MD5Type.X` added | agree | CPython 3.9 to 3.15: type name `"_md5.md5"` (`md5module.c:467` of 3.9.25, `.name` `:495` of 3.10.22, `:252` of 3.15.2), exported as `MD5Type` (`:583`, `:591`, `:594` of 3.11.18, `:355` of 3.12.16, `:358` of 3.15.2); `hashlib.md5` is a factory there, so no class alias |
| the three sites | `hashlib.md5.X` added, `_md5.md5.X` kept | agree | PyPy's `_md5` exports the class `W_MD5` (TypeDef `'_md5_md5'`) as `md5` (`moduledef.py:22` in 3.9 to 3.11), and hashlib's fallback caches `_md5.md5` (`hashlib.py:94` of 3.9, `:94` of 3.10) and binds it as `hashlib.md5` when OpenSSL lacks MD5 (ruling-names-2, H2); at `hashlib.new` the private name stays beside the alias (the lead's decision at avro `schema.py:337`) |
| the three sites | `_sha1.sha.X`, `_hashlib.HASH.X` kept | agree | PyPy's `_sha1.sha` (`lib_pypy/_sha1.py:117`, `update` `:219`, `digest` `:265`, `hexdigest` `:314` of 3.9; `:129` of 3.10 and 3.11) and `_hashlib.HASH` (`lib_pypy/_hashlib/__init__.py:34` of 3.9, `:57` of 3.10); CPython's `_hashlib` exports `HASH` |

Nothing missed. The two hash names in scope are md5 and sha1 (J6), and
`977` is the only hash constructor; the console stream reaches only the
lambda at `816` unbuffered (J7). No other outside callee of `path.json`
falls under the rulings: the other `io` classes are in `io.__all__`,
`re.Pattern` and `re.Match` are public, `functools.partial` is public on
both implementations, and `types.GeneratorType` is public.

Counts. 680 edges (422 inside, 258 outside), 487 traced (71.6%), 193 from
reading only: as `check.py path` reports, which passes with the source in
place, as do `--origin` and `--report`. The `make eval` numbers come from
PyCG's output, which I did not read.

| Id | Finding | Where | Fix |
|---|---|---|---|
| A1 | path admits PyPy 3.9 (`requires-python = ">=3.9"`, section "PyPy"), and `path.md` still says "PyPy 3.9 sources were not provided" and assumes them; the dependency sources now hold PyPy 3.9 v7.3.16, which gives the same names for every PyPy name of this correction (lines in the table above) | `path.md`, section "PyPy" (last paragraph) and "Corrections of 2026-11-25" (the console table says "PyPy 3.10 and 3.11", the hash table "PyPy 3.10, 3.11") | cite PyPy 3.9 v7.3.16 with this evidence |

**Verdict.** The four renames and the six additions stand, and nothing is
missed. A1 completes the evidence; no edge depends on it.

A1 was applied before the merge (`path.md` and its correction tables cite
PyPy 3.9 v7.3.16). The audit is closed.
