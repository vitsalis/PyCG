# vulture: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write vulture`
and `check.py vulture` report no error; every site is decided; every trace
edge is in the graph but one, which `vulture.rejected.json` rejects.
The blind audit (`vulture.audit.md`, 78 of 78 sites agree) found no edge;
its wording findings W1 and W2 are applied (the admitted CPython versions;
the tomli note). J1 was confirmed by the lead, 2026-11-24 (R1 of the
audit). The graph stays at 323 edges.

Release v2.16 (commit `b0f67ba`). Analysed source: `vulture/` (root `.`;
23 modules, 97 functions with 1 lambda, 10 classes), the fourteen modules
of `vulture/whitelists/` included (J1). `dev/` is not analysed (no
importable module; the lead's decision, README "Batch 8"). The ledger is
`vulture.ledger`; `vulture.json` and `vulture.added.json` are generated
from it.

## Supported versions, implementations and platforms

| What | Admitted | Evidence |
|---|---|---|
| Python | CPython 3.9 to 3.15 (every existing version from the bound) | `pyproject.toml`: `requires-python = ">=3.9"`, classifiers 3.9 to 3.14; the final classifier is not an upper bound (README, "Versions and configuration") |
| Implementations | CPython; PyPy 3.9, 3.10, 3.11 | classifiers `Implementation :: CPython` and `:: PyPy`; the version bound applies to PyPy (README, "Implementation, version and platform combinations") |
| Platforms | Linux, macOS, Windows | no OS classifier; the CI matrix `os: [macos-latest, ubuntu-latest, windows-latest]` (`.github/workflows/main.yml:18`); CHANGELOG "Ignore case of `--exclude` arguments on Windows" (textdistance ruling: the test jobs establish the platforms) |
| tomli | `>= 1.1.0` on Python < 3.11 | `pyproject.toml` `dependencies`: installed on those versions; the trace's environment (CPython 3.14) has no tomli |

Version branches: one optional import (`config.py:9-12`, J5). The
package has no platform branch; the platforms decide the class of the
`pathlib` receivers (J4). `ast.NodeVisitor.visit_Constant` exists on
Python 3.9 to 3.13 and on PyPy, not on CPython 3.14 and 3.15 (J2).
CPython 3.15 changes no edge (audit W1): its `ast.NodeVisitor` has no
`visit_Constant` (`deps/cpython/3.15.2/Lib/ast.py`), `pkgutil.get_data`
exists (`pkgutil.py:361`), `ssl.SSLContext()` still defaults its protocol,
and `tomllib`, `re`, `pathlib`, `argparse`, `string.Formatter` and
`tokenize.open` keep the names of the ledger.

`-O` and `-OO`: the `assert` statements with calls are `core.py:69`
(`isinstance`), `core.py:410` (`isinstance`) and `core.py:616`
(`isinstance`); `-O` removes them, so the graph (the union) keeps their
edges. Docstrings carry no calls.

## Values and architecture, as the ledger uses them

- **`Vulture`** (`core.py:190`) is an `ast.NodeVisitor`. `visit` (625)
  visits the children first (`generic_visit`, which calls `visit` on each
  child), then `self.reachability.visit(node)`, then the method
  `visit_<class name of the node>` found with `getattr` (631-638), then
  the parsed type comment. Its receivers are `Vulture` instances; no
  package subclass exists.
- **The collections.** `defined_*` and `unreachable_code` are
  `LoggingList`s, `used_names` a `LoggingSet` (`core.py:198-210`); no
  test or document assigns them. `Vulture._define` appends an `Item` to
  the collection it gets: always one of these LoggingLists.
- **`Reachability`** (`reachability.py:6`) gets `report` from
  `Vulture.__init__`: `partial(self._define, collection=self.unreachable_code,
  confidence=100)` (`core.py:220-225`). No test constructs a
  `Reachability`; a client's `report` is a client callback (B5). So each
  `self._report(...)` (9 value sites) calls `functools.partial.__call__`,
  which calls the bound `Vulture._define` back (J6).
- **`ignore`** of the private `_define` (`core.py:438:35`) is one of the
  five functions that the package passes (`_ignore_import`,
  `_ignore_variable`, `_ignore_class`, `_ignore_method`,
  `_ignore_function`) or `None`, which `ignore and` skips (J7).
- **Paths.** `Vulture.scan` makes `Path(filename)` (228:24) and stores it
  as `self.filename`; `Item.filename` is that value (annotated `Path`);
  `scavenge` makes `Path(path)` for each input (278:22) and
  `Path("whitelists") / ...` (301:24); `make_config` makes
  `pathlib.Path(cli_config["config"])` (206:33). Each is a
  `pathlib.PosixPath`, or a `pathlib.WindowsPath` on Windows (J4).
  `utils.get_modules` and `utils.format_path` are public but unannotated
  and undocumented: the package's flows decide their receivers
  (README, "After Codex audit round 1" (b)).
- **Configuration.** `_parse_toml` reads a binary stream (the
  `open(toml_path, "rb")` of `make_config`, or the client's `tomlfile`)
  with `tomllib.load` or `tomli.load`; the result and its tables are
  dicts. `_parse_args` builds a dict from the `argparse.Namespace`.
- **Source text.** `scan(code)` takes a `str`: the tests pass `str`,
  `utils.read_file` returns the text of `tokenize.open`, and the whitelist
  bytes are decoded (`core.py:312`).

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `Whitelist.__getattr__` | 564 | the only `Whitelist` instance is `whitelist_node_visitor` of `ast_whitelist` | the 67 attribute loads of `ast_whitelist.py:6-72` (J1) |
| `Item.__eq__` | 69 | no operand is an `Item` | `set(defined_items)` (`core.py:45:29`, J3) |
| `Item.__hash__` | 54 | no hashed value is an `Item` | `set(defined_items)` (`core.py:45:29`) |
| `Item.__repr__` | 59 | the package formats no `Item` | nowhere |

4 defaults decide 746 candidate-site pairs. The explicit sites that a
default decides keep their own entries (`getattr(...)`, `set(...)`,
`str(...)`, `print(...)`); none of their arguments is an `Item` or a
`Whitelist`.

## Judgement calls

**J1. The whitelist modules.** `vulture/whitelists/*.py` are modules of
the analysed package (`[tool.setuptools.package-data]` ships them; the
directory has no `__init__.py`, so `vulture.whitelists` is a namespace
package). Vulture reads them as data (`pkgutil.get_data`,
`core.py:306`), and they are also programs: `whitelist_utils.py:24-25`
("whitelist files that are not only syntactically correct, but can also
be executed") and upstream's `test_whitelists_with_python`
(`tests/test_script.py:34-39`, excluded from the trace) runs each one
with `python <file>`. Rule A keeps the edges of module code. `ast_whitelist`
imports `from whitelist_utils import Whitelist` by a top-level name, which
works when the file runs as a script (its directory is `sys.path[0]`) and
fails when the module is imported as `vulture.whitelists.ast_whitelist`.
The script run is the supported use, and the checkout has
`whitelist_utils.py`, so the face_classification rule (an import of a
module that the checkout lacks) does not apply: `Whitelist()` (4:35) has
no callee (no `__init__` of its own; `object.__init__`), and each of the
67 attribute loads `whitelist_node_visitor.visit_*` (6:24 to 72:24) finds
no attribute and calls `Whitelist.__getattr__`, named by the source
module (`vulture.whitelists.whitelist_utils.Whitelist.__getattr__`): 1
inside edge. The other modules' calls are outside edges:
`argparse.ArgumentParser`, `argparse.ArgumentDefaultsHelpFormatter`
(twice), `collections.defaultdict`, `logging.getLogger`, `ssl.SSLContext`
and `pint.UnitRegistry` (pint is no dependency and not installed: a
missing module, named by its access path). Attribute loads on library
classes and objects (`ctypes_whitelist`, `enum_whitelist`,
`ssl_whitelist`, `unittest_whitelist`, ...) run library descriptors only:
implicit calls of code outside the package, no edges. The alternative,
treating the whitelists as data without edges, contradicts rule A (they
are modules of the package and run as documented). Confirmed by the lead,
2026-11-24: the whitelist modules run as the scripts that the release
documents and tests (`tests/test_script.py:34-37`), and
`ast_whitelist -> Whitelist.__getattr__` stands (audit R1).

**J2. `visitor(node)` and `ast.NodeVisitor.visit_Constant`**
(`core.py:638:20`). The callees are the twelve `visit_*` methods of
`Vulture` whose suffix is a node class that `ast.parse` makes (`arg`,
`AsyncFunctionDef`, `Attribute`, `BinOp`, `Call`, `ClassDef`,
`FunctionDef`, `Import`, `ImportFrom`, `Name`, `Assign`, `MatchClass`;
the trace has all twelve). For a `Constant` node, `getattr` finds the
inherited `ast.NodeVisitor.visit_Constant` on Python 3.9 to 3.13
(`deps/cpython/3.9.25/Lib/ast.py:421-440`,
`3.13.18/Lib/ast.py:434-453`; PyPy 3.9 `lib-python/3/ast.py:419-438`,
PyPy 3.11 `:430-449`); CPython 3.14's `ast.py` has none, so the trace
lacks it. `visit_Constant` looks up `visit_Num`, `visit_Str`,
`visit_Bytes`, `visit_NameConstant` or `visit_Ellipsis` (a `Vulture` has
none) and calls `self.generic_visit(node)`, which `Vulture` overrides.
`Vulture` is defined through the library base, so that code is read (the
base-class exception): the site has `ast.NodeVisitor.visit_Constant`
(named through the class that the package names, the micro-benchmark's
inherited-method rule) and `Vulture.generic_visit` (a call-back). New
edge: `Vulture.visit -> ast.NodeVisitor.visit_Constant` (1 outside
edge); `Vulture.visit -> Vulture.generic_visit` is also an edge at 627.

**J3. `set(defined_items)` calls `Item.__eq__`** (`core.py:45:29`).
`_get_unused_items` builds a set of the `Item`s of a `LoggingList`:
`Item.__hash__` for each (the trace has it), and `Item.__eq__` when two
Items have equal hashes. Equal Items occur: `x = x = 1` defines the
variable `x` twice on one line of one file, and `import os, os` the
import `os` twice (`_define` appends an `Item` per definition, and
`__eq__` compares `(filename, first_lineno, name)`). Unequal Items can
also collide (tuple hashes). 1 inside edge, from reading; the trace has
no such input. `Item.__eq__`'s own edges to `Item._tuple` follow rule A.

**J4. Paths on Windows.** The `Path` objects of the package (see "Values")
are `WindowsPath`s on Windows, so each method call on them has both
names: `resolve` (`config.py:206:63`, `core.py:62:25`, `utils.py:92:28`),
`is_file` (`config.py:207:29`, `utils.py:93:24`), `is_dir`
(`utils.py:98:25`), `rglob` (`utils.py:99:38`) and `relative_to`
(`utils.py:62:32`): 8 outside edges to `pathlib.WindowsPath.*`. A class
call `Path(...)` is `pathlib.Path`, and `Path.cwd()` is
`pathlib.Path.cwd` (itables).

**J5. `tomllib.load` and `tomli.load`** (`config.py:84:24`). The optional
import of `config.py:9-12` gives `tomllib` on Python 3.11 and later and
`tomli` (the declared dependency) before; both sides run (the default for
optional imports; itables `config.py:61`). `tomli.load` is listed in
tomli's `__all__` (tomli 2.4.0, `deps/pypi/tomli-2.4.0`), so it keeps
that name. On Python < 3.11 tomli is the installed declared dependency,
not a missing module; the trace's environment (CPython 3.14) has no
tomli, so this 1 outside edge comes from reading (audit W2).

**J6. `self._report(...)`** (`reachability.py`, 9 value sites). The one
package value of `report` is the partial of `Vulture.__init__`, so each
site calls `functools.partial.__call__` (a callable wrapper object, named
by its class) and, through it, `Vulture._define`. The trace has both at
every caller (6 callers, 12 edges). `partial(self._define, ...)`
(`core.py:220:25`) only stores the bound method: `Vulture._define` is
rejected there.

**J7. `ignore(self.filename, name)`** (`core.py:438:35`). `_define` is
private; its callers pass the five `_ignore_*` functions or nothing. All
five are callees (the trace has them). Each `_define` call that passes one
of them rejects it as a candidate: `_define.ignored` calls it.

**J8. `csv` is called by `parse_args`** (`config.py:173:34`). The three
`add_argument(..., type=csv, ...)` calls only store the function;
`ArgumentParser.parse_args` converts each string of `--exclude`,
`--ignore-decorators` and `--ignore-names` with it. The defaults are the
sentinel `object()`, not strings, so argparse does not convert them.
`int` and `str` as types are builtins that library code calls back: no
edges.

**J9. `raise VultureInputException from err`** (`utils.py:111`). The
class is raised without a call; its first `__init__` in the MRO is
`BaseException.__init__`, outside the package: no edge (README,
"Implicit calls"). The trace's `read_file -> <builtin>.BaseException.__init__`
is rejected (see below).

## Callees outside the package

| Callee family | Naming | Sites |
|---|---|---|
| `pathlib` | `pathlib.Path` for a class call; `pathlib.PosixPath.*` and `pathlib.WindowsPath.*` for methods (the concrete class; the trace says `pathlib.Path.*` and `pathlib.PurePath.relative_to`, the defining classes); `pathlib.Path.cwd` | J4 |
| `argparse` | `argparse.ArgumentParser.add_argument` (defined on `_ActionsContainer`; the trace's alias), `argparse.ArgumentParser.parse_args`, `argparse.ArgumentParser`, `argparse.ArgumentDefaultsHelpFormatter` | `config.py:107-173`, whitelists |
| `tomllib` / `tomli` | `tomllib.load` (the trace: `tomllib._parser.load`), `tomli.load` | J5 |
| `io` | `io.TextIOWrapper.read` for the stream of `tokenize.open` (the trace: `_io.TextIOWrapper.read`) | `utils.py:109:26` |
| `re` | `re.compile`, `re.findall`, `re.sub`, `re.match`; `re.Pattern.search`, `re.Match.groupdict` (public since 3.7, on every admitted runtime) | `noqa.py`, `core.py` |
| `functools` | `functools.partial` (class call), `functools.partial.__call__` | J6 |
| `ast` | `ast.parse`, `ast.dump`, `ast.iter_fields`, `ast.literal_eval`, `ast.NodeVisitor.visit_Constant` | J2 |
| others | `fnmatch.fnmatch`, `fnmatch.fnmatchcase` (the value of `func`, `core.py:56-57`), `pkgutil.get_data`, `tokenize.open`, `string.Formatter`, `string.Formatter.parse`, `collections.defaultdict`, `logging.getLogger`, `ssl.SSLContext`, `sys.exit`, `pint.UnitRegistry` (missing) | |
| builtins | `<builtin>.*` by the micro-benchmark rules; `super().__init__()` and `super().append/add` in `LoggingList` and `LoggingSet` are `<builtin>.list.__init__`, `<builtin>.list.append`, `<builtin>.set.__init__`, `<builtin>.set.add`; `<builtin>.bytes.decode` for `pkgutil.get_data`'s result | |

Calls that library code makes on its own objects (the stream's `__enter__`,
`os.fspath` of a `Path` in `fnmatch`, descriptors of library classes in
the whitelists) are implicit and no edges.

## Open path sets

None.

## Rejected trace edges

| Edge | Reason |
|---|---|
| `vulture.utils.read_file -> <builtin>.BaseException.__init__` | an implicit call of code outside the package: `raise VultureInputException from err` instantiates the class without a call (J9) |

## Notes for the auditor

- `Item.__repr__` is never called by the package (the default rejection);
  the trace's `Item.__repr__ -> <builtin>.repr` is the body edge of a
  method that the tests call (rule A).
- The tests never scavenge a file with an import, a directory, or an
  `exclude` list: `pkgutil.get_data`, `bytes.decode`, `prepare_pattern`,
  `is_dir` and `rglob` come from reading.
- `main` and `__main__` do not run in the trace (the CLI tests are
  excluded or deselected); their 7 edges come from reading.
- Release quirks that remove no edge: `_handle_reachability_if` and
  `_handle_reachability_while` test `isinstance(node, ast.IfExp)` on an
  `If` or `While` node, which is always false (`reachability.py:76`,
  `151`); `Reachability.visit` ignores `ast.TryStar` (Python 3.11+), so
  `try`/`except*` blocks get no reachability analysis.
- The commit message of `00c349b` says that the whitelists other than
  `ast_whitelist` keep 7 outside edges; they keep 6 (listed in J1; 7
  sites, the formatter called twice; audit W2).
- Functions that the tests do not run: `Item.__eq__`,
  `Vulture.scavenge.prepare_pattern`, `main` and
  `Whitelist.__getattr__`.

## Statistics

| | Count |
|---|---|
| Sites | 1100 (350 call, 10 decorator, 31 op, 35 getitem, 627 getattr, 47 format); 926 with candidates; 12 value sites |
| Ledger entries | 437 (478 callee lines, 23 rejection lines of which 2 `reject *`, 92 notes, no exclusion) |
| Nodes | 120 (23 modules, 97 functions) |
| Edges | 323: 162 in the package, 161 outside |
| Confirmed by the trace | 282 of 323 (87.3%) |
| From reading only | 41 (12 inside, 29 outside) |
| Rejected trace edges | 1 |
| Functions that the tests run | 93 of 97 |

`check.py --origin vulture`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| vulture | 283 | 1 | 282 (150 / 132) | 41 (12 / 29) | 323 (162 / 161) |
