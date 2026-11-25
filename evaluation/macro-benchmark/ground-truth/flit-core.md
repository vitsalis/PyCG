# flit-core: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write
flit-core` and `check.py flit-core` report no error; every site is
decided; the trace has no edge that the graph lacks. After the blind
audit (`flit-core.audit.md`, 83 of 84 sites agree; F1, W1, R1) the lead
ruled on J2 (2026-11-24): its 3 outside edges went (650 to 647 edges);
F1 falls with J2, W1 is answered in J2, R1 is for the lead. Codex
round 1 (below): 4 names corrected, 1 outside edge added (648 edges).

Release 4.2.0 (commit `eeaf9e7`). Analysed source: `flit_core/flit_core/`
with root `flit_core` (13 modules, 122 functions, no lambda, 17 classes),
the vendored tomli 1.2.3 (`flit_core/vendor/tomli/`) included. The ledger
is `flit-core.ledger`; `flit-core.json` and `flit-core.added.json` are
generated from it. No trace edge is rejected, so there is no
`flit-core.rejected.json`.

## Versions, implementations and platforms

| What | Admitted | Evidence |
|---|---|---|
| Python | CPython 3.8 to 3.15 | `pyproject.toml`: `requires-python = '>=3.8'`, no version classifier; CI matrix 3.8 to 3.14 (`.github/workflows/test.yml`); `tox.ini` lists py38 to py315; 3.15.2 exists (deps) |
| Implementations | CPython only | no PyPy classifier, CI job or statement (README, "Versions and configuration") |
| Platforms | Linux, Windows | no OS classifier; CI runs `ubuntu-latest` and `windows-latest` (the batch-7 rulings on pyfiglet and textdistance); macOS is not admitted |
| Optimisation | normal, `-O`, `-OO` | the union; the two `assert`s (`common.py:393`, `:508-509`) keep their edges |

Version branches: only the optional import of `config.py:10-18` (J2, J3).
Platform branches: `if os.sep != '/'` in `WheelBuilder._add_file`
(`wheel.py:116`), taken on Windows: `_add_file -> <builtin>.str.replace`.
No `TYPE_CHECKING` block. `wheel.py` has `from __future__ import
annotations`; the other modules evaluate their annotations at definition
time, and those annotations only subscript typing objects (no edge).

Names that differ by version: the builtin SHA-256 object of hashlib's
fallback (J6) and the csv writer (`_csv.writer` on 3.8 and 3.9,
`_csv.Writer` from 3.10; Codex round 1, M1). Every other outside name
was checked in the CPython sources of the deps for 3.8.20 and 3.15.2
(`zipfile._ZipWriteFile`, `ZipInfo.from_file`,
`spec_from_file_location`).

## Values and architecture, as the ledger uses them

- **Public interface (J1).** The PEP 517 hooks of `flit_core.buildapi` and
  the command line `python -m flit_core.wheel` (`wheel.main`). Every other
  function and class is private: its parameters get what the package
  passes.
- **The client's inputs.** The source tree in the working directory
  (`pyproject.toml`, the module files, symlinks), the hook arguments
  (directory strings; `config_settings` is unused), the documented
  environment variables `SOURCE_DATE_EPOCH` and `FLIT_ALLOW_INVALID`
  (`doc/cmdline.rst:217`, `:242`; both branches run), and argv of
  `wheel.main`.
- **The TOML document.** `read_flit_config` parses `pyproject.toml` with
  `tomllib.loads` or the vendored tomli: dicts, lists, strs, ints, floats,
  bools and `datetime` values, made by the package's own call, so not
  opaque. Where the code calls a method without a type check, the callee
  is the method of the TOML type that has it (`.get` only on a dict,
  `.split` and `.strip` only on a str); any other type fails at the
  attribute load, before a call. `_check_type` and friends fix the type
  where they run.
- **Paths.** `Path('pyproject.toml')`, `Path.cwd()`, `Path(directory)` and
  argparse's `type=Path` make a `pathlib.PosixPath` on Linux and a
  `pathlib.WindowsPath` on Windows; `/`, `parent`, `glob` and
  `relative_to` keep the class. Each Path method therefore has both names
  (17 outside edges have `WindowsPath`).
- **Streams.** `open(..., 'w', encoding='utf-8')` in
  `prepare_metadata_for_build_wheel` gives an `io.TextIOWrapper`;
  `WheelBuilder._write_to_zip` yields an `io.StringIO`, as does
  `SdistBuilder.build` (`sdist.py:257`). `write_entry_points`,
  `Metadata.write_metadata_file` and `_write_wheel_file` write to these.
  `open(..., 'rb')` gives an `io.BufferedReader`; `open(fd, 'w+b')` an
  `io.BufferedRandom`, which only `zipfile` uses.
- **Builders.** `SdistBuilder.from_ini_path` and
  `WheelBuilder.from_ini_path` are called only on their own classes
  (`buildapi.py:84`, `wheel.py:231`), so `cls(...)` is their
  `__init__`. flit, the command-line tool, subclasses `SdistBuilder`
  (its docstring); that subclass is client code.
- **Metadata.** `make_metadata` builds every `Metadata` from the keys of
  `read_pep621_metadata`, `get_info_from_module` and `name`/`provides`;
  none is `license`, so `Metadata.license` stays `None` (J8).

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `common.VCSError.__str__` | 149 | flit_core never makes a VCSError | nowhere |
| `config.EntryPointsConflict.__str__` | 149 | no formatted or converted value is one | nowhere |

2 defaults decide 298 candidate-site pairs (112 format sites, the `str()`
and `print` calls and the `.format` calls).

## Judgement calls

**J1. Only the PEP 517 hooks and `python -m flit_core.wheel` are
public.** `flit_core/README.rst` (the distribution's readme): "The only
public interface is the API specified by PEP 517, at
``flit_core.buildapi``." By C and the batch-7 ruling on pymysql (an
explicit statement makes a callable private despite its spelling), the
functions of `common`, `config`, `sdist`, `wheel`, `versionno` and the
vendored tomli are private, though their paths have no underscore.
`doc/bootstrap.rst:18` documents `python -m flit_core.wheel`, so
`wheel.main` is reached through the documented command line (its argv is
the command line). The direct calls of `tests_core` do not widen any
input (pymysql ruling). Private functions that the package never calls
get B's public-parameter fallback: `parse_entry_point`, `hash_file`
(J6), `LoadedConfig.add_scripts`, `SdistBuilder.prep_entry_points`,
`VCSError.__init__`/`__str__`, `EntryPointsConflict.__str__` and the
vendored `load`. Edges decided: none of the graph changes with the
alternative (all of these public): the parameters would take the same
types (the package's own values already reach every method that a
client value could), and client streams and callables stay opaque; the
`License:` branch of J8 writes with methods that other sites of the same
function already have.

**J2. The unvendored tomli (`config.py:10-18`; ruling of the lead,
2026-11-24: no edge).** The import tries `tomllib`, then the vendored
copy, then `tomli`. The third side runs only on CPython 3.8 to 3.10 with
the vendored `flit_core/vendor/tomli` deleted. The release does not
document that state: `doc/bootstrap.rst` allows removing the bundled
tomli only "if you use Python 3.11 or newer", where `import tomllib`
(line 11) succeeds and line 18 is never reached, and for older versions
says only to "special-case installing ``flit_core`` and/or ``tomli``";
`flit_core/vendor/README` describes unbundling as replacing the package
with `from tomli import *`, which keeps `from .vendor import tomli`
(line 14) working. Only the code comment at `config.py:15-16` names a
removal that reaches line 18. The README takes the checkout as it is
(face_classification: code after an import of a module that the checkout
lacks has no edges). So `read_flit_config` has no `tomli.loads` edge and
no stub reaches `prep_toml_config` (3 edges of the first commit went:
`read_flit_config -> tomli.loads`, `prep_toml_config -> tomli.loads.get`
and `-> tomli.loads.get.get`). The audit's F1 (2 further stub edges,
conditional on J2) falls with it; its W1 (the evidence of
`doc/bootstrap.rst`) is answered by this text.

**J3. The vendored tomli (`config.py:13-14`).** On CPython 3.8 to 3.10
`import tomllib` fails and `tomllib` is `flit_core.vendor.tomli`, which
re-exports `_parser.loads`: `read_flit_config ->
flit_core.vendor.tomli._parser.loads` (1 inside edge, not in the 3.14
trace). By rule A the vendored functions keep their body edges on every
version (137 edges, 78 inside). The package calls only `loads`, with a
str and the default `parse_float=float`: the `parse_float(...)` value
sites have `<builtin>.float` only (`ParseFloat` is a bare `Callable`, B2).
`load` is never called; its `fp` is annotated `BinaryIO` (abstract), so
`fp.read()` and `s_bytes.decode()` have no callee. `Output(...)` is a
`NamedTuple` class call: no edge. `cached_tz` is wrapped by
`lru_cache(maxsize=None)`: its call has
`_functools._lru_cache_wrapper.__call__` and `cached_tz` (configargparse
and einops precedents; no PyPy, so no `.wrapper`).

**J4. Platforms (17 + 1 outside edges).** See the table above. The
`WindowsPath` names of `is_dir`, `is_file`, `open`, `read_text`, `glob`,
`relative_to`, `as_posix`, `resolve` and `mkdir`, and the Windows branch
`rel_path.replace(os.sep, '/')` (`wheel.py:119`), rest on Windows. The
module functions keep their imported names (`os.path.join` for `osp.join`
on both platforms; `posixpath.join` for `pjoin`, which `sdist.py:10`
imports from `posixpath`).

**J5. The module that `get_docstring_and_version_via_import` runs
(`common.py:175-202`).** The client's module is executed with
`spec.loader.exec_module(m)`. `spec_from_file_location` is given no
loader and picks one by suffix; `Module.file` always ends in `.py`
(`common.py:28`, `:71`), so the loader is an
`importlib.machinery.SourceFileLoader` (`_get_supported_file_loaders`
in `importlib/_bootstrap_external.py` of 3.8.20 and 3.15.2; the location
is passed through `os.fspath`). The module's code is client code. Its
`__doc__` and `__version__` are a str or None as Python sets them, or
what the client's code assigns (opaque, B5), so `docstring.strip()` and
the later str methods (`common.py:228`, `:233`) are named for `str`.

**J6. Hash objects (`wheel.py:137`, `:164`; `common.py:305-308`; 8
outside edges).** `hashlib.sha256()` returns an OpenSSL `_hashlib.HASH`,
or, by hashlib's documented fallback, the builtin object, whose class
the module exports as `_sha256.SHA256Type` on CPython 3.8 to 3.11 (its
type name is `_sha256.sha256`; Codex round 1, N1 to N4) and
`_sha2.SHA256Type` from 3.12
(`Modules/sha256module.c`, `Modules/sha2module.c` of the deps; the
precedents of django-constance and markdown2). `update`, `digest` and
`hexdigest` have the three names. `hash_file(path, algorithm='sha256')`
is never called by the package (J1 fallback): no test or document passes
another algorithm, so only the default is in scope (B2, a client string
that selects an outside object; path's precedent for `hashlib.new`);
`hashlib.new('sha256')` gives the same three receivers.

**J7. Exceptions of the package.** `ConfigError`, `ProblemInModule`,
`NoDocstringError`, `NoVersionError`, `InvalidVersion`, `EntryPointsConflict`
and tomli's `TOMLDecodeError` define no `__init__`: their calls name
`<builtin>.ValueError.__init__`. `raise EntryPointsConflict`
(`config.py:236`) is a raise without a call whose first `__init__` is
`ValueError`'s: no edge (README, "Implicit calls").
`_license_files_from_globs` raises a `ConfigError` inside its own `try`
(`config.py:320`), which its `except ValueError` catches and re-raises
with another message (line 327): both constructor calls are edges.

**J8. `Metadata.license` (`common.py:449-450`).** No package code puts a
`license` key into the dict of `make_metadata`, so `license` is the
class default `None` and `fp.write(f'License: {license}\n')` never runs
(B1, a private class in one state). The site has a note and no callee;
the pair `write_metadata_file -> io.TextIOWrapper.write` and `->
io.StringIO.write` exists at the other writes.

**J9. Properties and arguments.** Where a property is passed as an
argument (`_write_wheel_file(f, supports_py2=metadata.supports_py2)`,
`log.debug(..., target.file)`, `pjoin(self.dir_name, ...)`), the property
runs at its own getattr site and the call site rejects it as a callback.
`info.file` (`buildapi.py:75`, `:80`; `wheel.py:271`) is the attribute of
the `types.SimpleNamespace` of `make_wheel_in`, not `Module.file`.

## Callees outside the package

| Callee | Name used | Why |
|---|---|---|
| `os.path` functions (`osp` alias too) | `os.path.join`, `.normpath`, `.relpath`, `.realpath`, `.isabs`, `.isdir`, `.dirname`, `.basename` | the imported path; the trace's `posixpath.*` and `posix._path_normpath` are aliases |
| `pjoin` | `posixpath.join` | imported from `posixpath` |
| `os.environ.get` | `collections.abc.Mapping.get` | `os._Environ` inherits it (anytree precedent) |
| Path methods | `pathlib.PosixPath.*`, `pathlib.WindowsPath.*` | the class of the receiver (J4); `Path.cwd` is called on the class: `pathlib.Path.cwd` |
| file and string streams | `io.TextIOWrapper.*`, `io.BufferedReader.read`, `io.StringIO.*` | the class that `open` or the package makes |
| SHA-256 objects | `_hashlib.HASH.*`, `_sha256.SHA256Type.*`, `_sha2.SHA256Type.*` | J6; the module attributes that export the classes |
| csv writer | `csv.writer`, `_csv.Writer.writerow` (3.10 and later), `_csv.writer.writerow` (3.8, 3.9) | 3.10 exports the class as `_csv.Writer`; before, it has no public path and keeps its type name (netaddr precedent) |
| zip member writer | `zipfile._ZipWriteFile.write` | the class of `ZipFile.open(..., 'w')`, no public path |
| loader | `importlib.machinery.SourceFileLoader.exec_module` | J5 |
| argparse | `argparse.ArgumentParser.add_argument` | the receiver's class (the trace names `_ActionsContainer`) |
| `@contextmanager` calls | `contextlib.contextmanager.helper` and the package generator function | argcomplete precedent |
| `@lru_cache` | `functools.lru_cache`, `functools.lru_cache.decorating_function`, `_functools._lru_cache_wrapper.__call__` | J3 |
| package exceptions | `<builtin>.ValueError.__init__` | J7 |

## Open path sets

None.

## Rejected trace edges

None: every one of the 458 trace edges is in the graph.

## Notes for the auditor

- The tracer misses the call-backs of `@contextmanager` generator
  functions (defect T1): `get_docstring_and_version_via_import ->
  _module_load_ctx` and the four callers of `WheelBuilder._write_to_zip`
  come from reading.
- `map(osp.normpath, ...)` in `SdistBuilder.from_ini_path` and `map(str,
  ...)` in `Module.__init__` and `_check_types` give only `<builtin>.map`:
  the iteration calls a library function. argparse's `type=Path`
  (`wheel.py:254`) and logging's `%s` formatting are library calls too.
- The `set()` calls reject the candidate `vendor.tomli._parser.Flags.set`;
  `out.flags.set(...)` and `flags.set(...)` in tomli accept it.
- `config.py` imports `difflib` and never uses it.
- Functions that the tests never run: the 37 functions of the vendored
  tomli (3.14 imports `tomllib`), and `VCSError.__init__`, `__str__`,
  `hash_file`, `parse_entry_point`, `EntryPointsConflict.__str__`,
  `LoadedConfig.add_scripts`, `SdistBuilder.prep_entry_points`.

## Statistics

`check.py flit-core`: 13 modules, 122 functions (0 lambdas), 17 classes,
941 calls; 1086 sites (941 call, 11 decorator, 22 getattr, 112 format),
446 with candidates (601 candidates), 14 value sites; 648 edges (200
internal, 448 outside); the trace has 458 edges and confirms 458 of 648
(70.7%); 78 of 122 functions run (63.9%); 0 rejected.

`check.py --origin flit-core`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| flit-core | 458 | 0 | 458 (116 / 342) | 190 (84 / 106) | 648 (200 / 448) |

| Ledger | Count |
|---|---|
| Entries | 974 (941 call, 11 decorator, 22 getattr) |
| Callee lines | 1024 |
| Rejection lines | 37 (no `reject *`) |
| Notes | 139 |
| Exclusions | 0 |
| Default rejections | 2, deciding 298 candidate-site pairs |

## Codex round 1

All five findings hold and are applied (`selection/batch-8-proposal/
codex-audits/round-1/flit-core.md`).

| Id | Site | Applied | Evidence |
|---|---|---|---|
| N1 | `common.py:308:23` | `_sha256.sha256.hexdigest` becomes `_sha256.SHA256Type.hexdigest` | CPython 3.8 to 3.11 export the builtin SHA-256 class as the module attribute `SHA256Type` (`PyModule_AddObject`, `Modules/sha256module.c` of 3.8.20 and 3.11.18); `_sha256.sha256` is its type name and, as a module attribute, the factory function. A class with a public path is named by it (micro-benchmark "Names"; README, "Outside names") |
| N2 | `wheel.py:143:31` | `_sha256.SHA256Type.update` | as N1 |
| N3 | `wheel.py:147:55` | `_sha256.SHA256Type.digest` | as N1 |
| N4 | `wheel.py:165:55` | `_sha256.SHA256Type.digest` | as N1 |
| M1 | `wheel.py:209:32`, `211:28` | `+ write_record -> _csv.Writer.writerow` (1 outside edge); `_csv.writer.writerow` stays | CPython 3.10 to 3.15 export the writer class as `_csv.Writer` (`PyModule_AddObjectRef`, `Modules/_csv.c` of 3.10.22 and 3.14.10); 3.8 and 3.9 do not, so their fallback name stays ("Versions and configuration": keep an older fallback name where that runtime lacks the later public path) |

Counts: 647 to 648 edges (200 inside, 448 outside).

The referee's ruling on the names of exported C types
(`selection/batch-8-proposal/rulings/b8-ruling-c-type-names-1.md`,
adopted by the lead) confirms N1 to N4 and M1 as applied: no change.

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
| `flit_core.vendor.tomli._re.match_to_datetime` | `flit_core/flit_core/vendor/tomli/_re.py:71:41` |

The package has no trace of these calls, so no trace edge is rejected.
