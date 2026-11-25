**Status (2026-11-24):** closed. The re-check against the writer's
`b2e58ad` finds W1 and W2 applied and nothing open; the lead confirmed J1
(R1 goes into the README's "Rulings for batch 8"). The graph is unchanged:
323 edges (162 inside, 161 outside).

# vulture: blind audit of the ground truth

Release v2.16, commit `b0f67ba0044693aa9ec0d38fe460590facc98004` (batch 8;
pin of `projects.toml`, `[vulture]`). Audited files, at the writer's commit
`00c349b` on `b8-gt-vulture`: `vulture.ledger` (1256 lines, 4 default
rejections), `vulture.json` (120 nodes, 323 edges: 162 in the package, 161
outside), `vulture.added.json` (41 edges), `vulture.rejected.json` (1 edge)
and `vulture.md` (judgements J1 to J9). `check.py vulture` reports no error;
`check.py --origin vulture`: 283 trace edges, 1 rejected, 282 in the graph,
41 added.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, its clarifications, the rulings for the test
set and for batch 7, and the naming rules of `PyCG/micro-benchmark/README.md`.
I read every module of `vulture/` (the 23 of the analysed source, the
fourteen whitelists included), `pyproject.toml`, `tox.ini`, `README.md`
(the whitelist sections), `.github/workflows/main.yml`, `tests/__init__.py`
and `tests/test_script.py`; from the dependency sources (read only),
`Lib/ast.py` of CPython 3.9.25, 3.12.16, 3.13.18, 3.14.10 and 3.15.2 and
`lib-python/3/ast.py` of PyPy 3.9 and 3.11, `Lib/pkgutil.py` and `Lib/ssl.py`
of 3.15.2, `Lib/tomllib/__init__.py` of 3.11.18, `tomli-2.4.0`'s
`__init__.py`, and PyPy 3.9's `lib-python/3/re.py`. I did not run or import
the package and ran no analysis tool on it. The commands I ran: `check.py`
(`--benchmark-dir <scratch> --skeleton` and the size report on a scratch
copy without the ledger; then `check.py vulture`, `--origin`, `--report`,
`--report --without-candidates`, `--report --default` for the four
defaults), my draw script
(`selection/batch-8-proposal/audits/vulture/draw.py`), and two `ast`
scripts of my own on the text of the skeleton, the ledger and the source
(the comparison and the binding check).

## Final state

78 of 78 sites re-derived blind agree with the ledger. The exhaustive
checks found no missing edge and no edge that cannot happen. Every
judgement call of the writer (J1 to J9) follows from the nearest rule;
J1 rests on rule A and the scope of the analysed source and decides one
inside edge (R1). The findings change no edge: the graph stays at 323
edges (162 inside, 161 outside).

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| W1 | wording (low) | `vulture.md`, "Supported versions": "3.9 and later (3.9 to 3.14 exist with the release's admitted runtimes)" | `requires-python = ">=3.9"` (`pyproject.toml:11`) admits CPython 3.15, which exists (`deps/MANIFEST.json` lists `cpython/3.15.2` for vulture), and "The final classifier is not an upper bound" (README, "Versions and configuration"). I checked what 3.15 could change: its `ast.NodeVisitor` has no `visit_Constant` (as 3.14; `3.15.2/Lib/ast.py:518-591`), `pkgutil.get_data` exists (`pkgutil.py:361`), `ssl.SSLContext()` still defaults its protocol (`ssl.py:444-452`), and `tomllib`, `re`, `pathlib`, `argparse`, `string.Formatter`, `tokenize.open` keep the names of the ledger. | 0 | the writer names 3.15 as admitted, with "no edge changes" |
| W2 | wording (low) | the 84:24 note: tomli "not installed in the trace's environment, named as a missing module" | On Python < 3.11 tomli is the declared dependency (`pyproject.toml:33-35`) and is installed; it is not a missing module there. Its name is its public path either way: `tomli-2.4.0` `__init__.py:5` lists `load` in `__all__`, `:8` imports it from `._parser` (J5 of `vulture.md` says this correctly). The commit message of `00c349b` also says that the whitelists other than `ast_whitelist` "keep 7 outside edges"; the graph has 6 (`argparse.ArgumentParser`, `argparse.ArgumentDefaultsHelpFormatter`, `collections.defaultdict`, `logging.getLogger`, `pint.UnitRegistry`, `ssl.SSLContext`; 7 sites, the formatter called twice). The commit is not rewritten; `vulture.md` J1 lists them right. | 0 | the writer rewords the note |
| R1 | README (low) | J1: `vulture/whitelists/ast_whitelist.py:1`, `from whitelist_utils import Whitelist` | The module imports its sibling by a top-level name, which works only when the file runs as a script (its directory is `sys.path[0]`), as `whitelist_utils.py:24-25` documents and `tests/test_script.py:34-37` does; imported as `vulture.whitelists.ast_whitelist` it raises `ModuleNotFoundError`. The README's nearest sentence (face_classification: code after "an import of a module of the analysed root that the checkout lacks" has no edges) does not cover it: the checkout has the module. The writer and I reached the same reading blind (the module runs as its documented script). One sentence under "Judgements" (a module of the analysed source that the release documents and tests as a script runs as that script) would fix it. | 1 inside edge (`vulture.whitelists.ast_whitelist -> vulture.whitelists.whitelist_utils.Whitelist.__getattr__`, 67 sites) | for the lead; no change proposed |

No F finding.

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/vulture` (`cp -R` from
`$SHARED`) to a scratch directory and ran `check.py --benchmark-dir
<scratch> --skeleton vulture`: 23 modules, 97 functions (1 lambda), 10
classes; 1100 sites (350 call, 10 decorator, 627 getattr, 47 format, 35
getitem, 31 op), 926 with candidates; 12 value sites. Candidates at 50 or
more sites: `Whitelist.__getattr__` 631, `Item.__eq__` 70, `Item.__repr__`
59, `Item.__hash__` 55.

**The draw, by kind.** Attribute loads are 627 of the 1100 sites, each with
the one candidate `Whitelist.__getattr__`. I numbered the sites by (module
in skeleton order, line, column) and drew with one
`random.Random(20261124)`: `rng.sample(explicit, 50)` of the 360 call and
decorator sites, `rng.sample(getattr, 10)` of the 627 attribute loads,
`rng.sample(other, 10)` of the 113 other implicit sites (op, getitem,
format); then the 12 value sites, 4 of which the draw had taken: 78 sites.
The blind answers are commit `0eeff83`
(`selection/batch-8-proposal/audits/vulture/`: `draw.py`, `sample.txt`,
`blind-answers.md`), made before I opened any file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator; 4 of them value sites) | 50 | 50 | 0 |
| Attribute loads | 10 | 10 | 0 |
| Other implicit (4 op, 3 getitem, 3 format) | 10 | 10 | 0 |
| Value sites not in the draw | 8 | 8 | 0 |
| **Total** | **78** | **78** | **0** |

Agreement: 78 of 78. The sample holds the decisions that carry the
judgement calls: J1 (two `whitelist_node_visitor.visit_*` loads accepted,
the other eight loads rejected), J2 (`core.py:638:20` with
`ast.NodeVisitor.visit_Constant` and the call-back
`Vulture.generic_visit`), J6 (nine `self._report` sites, each
`functools.partial.__call__` and `Vulture._define`), J7 (`core.py:438:35`,
the five `_ignore_*`), J4's `pathlib.Path` class call (`core.py:215:29`),
and the callback rejection at `core.py:416:25`. I wrote J1 and J2 as my
own judgements in the blind answers, with the same callees.

## Step 2: exhaustive checks

**Dispatch sets.** No package class has a package subclass, so each method
call on `self` has one receiver class: `Vulture` (core), `Reachability`,
`Item`, `LoggingList`, `LoggingSet`. The two `visit` methods are kept
apart at every site (`Vulture.visit` at 259:27, 649:23, 659:35, 661:27;
`Reachability.visit` at 629:32, the receiver being the `Reachability` of
225:41). `LoggingList.append` and `LoggingSet.add` are callees exactly
where the receiver is a `defined_*`, `unreachable_code` or `used_names`
collection (450:30; 424:36, 482:32, 505:36, 537:40, 610:32, 619:40,
623:32), and rejected on the builtin `parts` (`utils.py:74`, `76`),
`modules` (`utils.py:97`), `noqa_lines[...]` (`noqa.py:38`) and
`_no_fall_through_nodes` (`reachability.py:45`). The callback roles:

| Role | Values | Sites |
|---|---|---|
| `visitor` (`core.py:631-638`) | the 12 `Vulture.visit_*` of node classes that `ast.parse` makes (`MatchClass` from 3.10); `ast.NodeVisitor.visit_Constant` on CPython 3.9 to 3.13 and PyPy 3.9 to 3.11 (`3.9.25/Lib/ast.py:421`, `3.13.18/Lib/ast.py:434-453`, PyPy 3.9 `:419`, PyPy 3.11 `:430`; none in 3.14 and 3.15), which calls back `Vulture.generic_visit`. No other `visit_*` attribute exists on a `Vulture`; `TypeIgnore`, `FunctionType` and `Expression` nodes find none. | 638:20 |
| `Reachability._report` | only the partial of `core.py:220-225` | 9 sites |
| `ignore` of `_define` | `_ignore_import`, `_variable`, `_class`, `_method`, `_function`; `None` from 480, 588 and the partial | 438:35; rejected as candidates at the five passing sites |
| `func` of `_match` | `fnmatch.fnmatch` (case False: 61, 276), `fnmatch.fnmatchcase` (default: 439, 552, 584) | 57:20 |
| `type=csv` | called back by `parse_args` (173:34), rejected at the three `add_argument` calls | |
| `key=` | `by_name`, `by_size` at 345:22; the lambda at 47:22 | |

**Default rejections**, each with `--report --default`:

- `Whitelist.__getattr__` (564 sites): every attribute load outside
  `ast_whitelist.py:6-72` is on a module, an AST node, a package object
  (none defines `__getattr__` but `Whitelist`) or a library class or object;
  the four explicit `getattr(...)` sites (632:26, 634:29, 642:31,
  `lines.py:15:25`) take a `Vulture` or an AST node. The 67 loads of
  `ast_whitelist` accept it (J1). Correct.
- `Item.__eq__` (69), `Item.__hash__` (54): I read all their sites. No
  operand, key or set element is an `Item` but at `set(defined_items)`
  (45:29), which accepts both (J3). `sorted` (345:22) compares keys, never
  Items; `self.used_names |= set(...)` and `item.name not in used_names`
  work on strings. Correct.
- `Item.__repr__` (59): no package site formats, prints or `repr`s an
  `Item`. `_log` gets strings, ints and Paths from its twelve callers;
  `print(e, file=sys.stderr)` (668:14) formats an `InputError`. Correct;
  `Item.__repr__` is the only function no site calls.

**Functions that no site calls.** `Item.__repr__` (above). Every nested
function (`csv`, `get_list`, `handle_syntax_error`, `prepare_pattern`,
`exclude_path`, `by_name`, `by_size`, `is_identifier`, `ignored`, the
lambda) has its caller.

**Special methods and properties.** `Item.size` at its three loads
(156:42, 157:37, 328:25) and the seven `Vulture.unused_*` loads (331-337)
are the only loads of those names in the package. `InputError.__init__`
at the three `InputError(...)` calls; `raise VultureInputException from
err` without a call adds no edge (J9). `Whitelist()` (`ast_whitelist.py:4`)
has no constructor edge (`object.__init__`). `LoggingList.__init__` and
`LoggingSet.__init__` reach `<builtin>.list.__init__` and
`<builtin>.set.__init__` through `super()`.

**Rejections and notes.** The 23 rejection lines and 92 notes agree with
the source.

**Callees outside the package.** Each name checked against the naming
rules and the dependency sources: `argparse.ArgumentParser.add_argument`
(defined on `_ActionsContainer`, named by the receiver),
`.parse_args`; `tomllib.load` (`tomllib/__init__.py:5`, `:7`) and
`tomli.load` (W2); `io.TextIOWrapper.read` for `tokenize.open`'s stream;
`re.Pattern.search`, `re.Match.groupdict` (public on every admitted
runtime; PyPy 3.9 `re.py:280-281`); `string.Formatter`,
`string.Formatter.parse`; `pkgutil.get_data` and `<builtin>.bytes.decode`;
`functools.partial`, `functools.partial.__call__`; `ast.parse`, `dump`,
`iter_fields`, `literal_eval`, `ast.NodeVisitor.visit_Constant`;
`fnmatch.fnmatch`, `fnmatch.fnmatchcase`; `sys.exit`; `pathlib.Path` for
the five class calls, `pathlib.Path.cwd`, and `pathlib.PosixPath.*` with
`pathlib.WindowsPath.*` for the eight method edges (Windows by the CI
matrix, `main.yml:18`; the textdistance ruling); the whitelists' six
(W2). The builtins follow the micro-benchmark names. Nothing is missing:
every explicit site has its outside callee or a note.

**Rejected trace edge.** `read_file -> <builtin>.BaseException.__init__`:
`raise VultureInputException from err` (`utils.py:111`) instantiates a
package class without a call whose first `__init__` is outside the
package; an implicit call of outside code (README, "Implicit calls";
rule A). Correct.

**Trace edges that the graph lacks:** none (`--report`: "trace edges that
no site of the caller accounts for: 0").

**Implicit sites without candidates** (218, `--report
--without-candidates`): no lazy `map` or `filter` of a package function
(the one `map(str, args)` at 402:33 is consumed by `str.join` at the same
site and maps a builtin), and no library code that calls package code
later. The class sites (`Item`, `Vulture`, `Reachability`, `InputError`,
`ExitCode`, `LoggingList`, `LoggingSet`, `Whitelist`, `EnumWhitelist`)
run no package hook.

## Step 3: binding check

An `ast` script of mine matched each ledger callee in the package to the
`ast.Call` at its site and bound the call's arguments to the callee's
parameters (bound methods without `self`; `staticmethod` as called): 151
direct calls, none that cannot bind. The 32 indirect ones, and the lambda
of 47:22, I bound by hand: `csv(str)`; `Item.__hash__` and `Item.__eq__`
from `set()`; `by_name(item)`, `by_size(item)` and the lambda (one key
argument); the five `_ignore_*(filename, name)`; `visit_*(node)` and
`generic_visit(node)`; and
`_define` through the partial, whose `collection` and `confidence`
keywords join the `name`, `first_node`, `last_node` and `message` keywords
of the nine `self._report` calls (`last_node` defaults at 102:29 and
139:25). All bind.

## The writer's judgement calls

| Id | Opinion | Nearest rule |
|---|---|---|
| J1 | Agree (my blind answer had it). The whitelists are modules of the analysed source (`packages = ["vulture"]`, no exclusion), and the release documents and tests them as scripts. 1 inside edge; 6 outside edges of the other whitelists, which also run when imported. | rule A; "Judgements" (face_classification does not apply); R1 |
| J2 | Agree. `ast.NodeVisitor.visit_Constant` is named through the class that the package names (micro-benchmark, "Inherited methods"); `Vulture.generic_visit` is its call-back. Reading `ast.py` needs no exception: it is the standard library. | callback rule (B5); micro-benchmark names |
| J3 | Agree: `x = x = 1` and `import os, os` give equal Items. | "Edges" (some program in a fresh process) |
| J4 | Agree. | textdistance ruling; "Implementation, version and platform combinations" |
| J5 | Agree; see W2 for the note's wording. | "Judgements" (both sides of an optional import) |
| J6 | Agree. | callback rule; "Calls of instances" |
| J7 | Agree. | B2 (private function: the package's own calls) |
| J8 | Agree. | callback rule; argparse converts only string defaults |
| J9 | Agree. | "Implicit calls" (marshmallow `fields.py:102`) |

## For the lead

- R1 (J1): whether a module of the analysed source that the release
  documents and tests as a script, and that imports a sibling by a
  top-level name, runs as that script. It decides 1 inside edge
  (`ast_whitelist -> Whitelist.__getattr__`, 67 sites). The writer and I
  agree that it runs; no referee is needed for one edge.

## Re-check (2026-11-24, against `b2e58ad`)

`git diff 00c349b b2e58ad` touches three files of the writer:
`vulture.ledger` (one line, the note of `config.py` 84:24),
`vulture.added.json` (the same note, regenerated) and `vulture.md`.
`vulture.json` and `vulture.rejected.json` are unchanged, and no callee,
rejection or site line of the ledger changed. The audit files (`9dfa978`)
are untouched. `check.py vulture` reports no error (323 edges, 162 / 161;
1 rejected trace edge); `check.py --origin vulture` gives 283 trace
edges, 1 rejected, 282 in the graph (150 / 132), 41 added (12 / 29), 323
(162 / 161), as before.

| Id | Re-check |
|---|---|
| W1 | Applied. `vulture.md` admits CPython 3.9 to 3.15, cites "Versions and configuration" for the classifier, and records that 3.15 changes no edge (no `visit_Constant`, `pkgutil.get_data`, `ssl.SSLContext()`, the unchanged names). Closed. |
| W2 | Applied. The note of 84:24 now says tomli is the declared dependency, installed on Python < 3.11, with `tomli.load` its public path in `__all__`; J5 and the tomli row of the versions table say the same; "Notes for the auditor" records the 6 outside edges of the other whitelists against the 7 of the first commit message. Closed. |
| R1 | The lead confirmed J1 on 2026-11-24; `vulture.md` J1 records it. The README sentence is the lead's. Closed for this audit. |

Nothing is open.
