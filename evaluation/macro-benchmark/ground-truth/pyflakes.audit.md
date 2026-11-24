# pyflakes: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [pyflakes.md](pyflakes.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release 4.1.0, commit `5324946c5d8602697f5df6d98ad162920b3e5d61`. Analysed
source: `pyflakes/` without `pyflakes/test/` (8 modules, 189 functions with 6
lambdas, 80 classes). Audited files, as they are in the worktree
`feat/heldout-3-gt` before any commit: `pyflakes.ledger` (837 entries, 3
default lines for 6 candidates), `pyflakes.json` (642 edges: 376 in the
package, 266 to 92 callees outside), `pyflakes.rejected.json` (4 edges),
`pyflakes.md`, and the trace `dynamic/pyflakes.json` (CPython 3.14.10, 762
passed, 29 skipped, 5 deselected; 597 edges). `check.py pyflakes`: no errors;
the trace confirms 593 of the 642 edges; 0 trace edges are unaccounted for.

I judged the files by the README rules (A, B1-B5, C), with the rulings of the
second held-out set and the 2021 set. I read the whole source, `setup.py`
(`python_requires='>=3.11'`), `tox.ini`, the CI file and the test harness as
data. I did not run or import the package, and I did not use any static
analysis tool or its output.

**Final state.** No finding changes the graph. One case needs a ruling (J1:
1 edge, which writer and auditor both keep). One finding changes the wording
of the two `VariableKey` default reasons (A1, 0 edges). One remark (R1)
supports a judgement of the writer.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Severity |
|---|---|---|---|---|---|
| J1 | case for a ruling (writer and auditor agree) | `checker.py:1252:20` `handler(node)` -> `Checker._unknown_handler` | `iter_child_nodes` walks every field in `node.__class__._fields` (`checker.py:179-188`), so on the root `Module` it also yields the nodes of `type_ignores`. `ast.parse(src, type_comments=True)` puts a `TypeIgnore` there for each `# type: ignore` comment. `Checker` has no `TYPEIGNORE`, so `getattr(self, 'TYPEIGNORE', self._unknown_handler)` (`:1016`) returns `_unknown_handler`, and `:1252` calls it. `Checker` is public; its `tree` is a client object made by the stdlib parser. B3 leaves out only node types that the parser never makes. On 3.11-3.15 no other parser class lacks a handler (computed with the `ast` class lists of 3.13, 3.14 and 3.15 against the class-body names; 3.11 adds `TryStar`, 3.12 the four type-parameter classes, all handled; `alias` never reaches `handleNode`). | keep: 0; if the lead rules the other way: -1 (642 to 641); the 4 body edges stay by rule A | ruling |
| A1 | default reason inexact (wording) | the two `default reject pyflakes.checker.VariableKey.__eq__/__hash__` lines (ledger lines 8-9) | The reasons say that `VariableKey` objects "live only in" the local lists and Counters of `Checker.DICT`. A `VariableKey` inside a tuple key escapes: `{(a, 1): 1, (a, 1): 2}` reports `MultiValueRepeatedKeyLiteral` with the tuple as `key` (`checker.py:1832-1841`), stored in `message_args` (`messages.py:120-122`) and kept in `Checker.messages`. No default-decided site hashes or compares it there: `Message.__str__` formats it with `%r` (`messages.py:17`; `VariableKey` has no `__repr__`), and `GLOBAL` reads `message_args[0]` only of `UndefinedName` messages (`checker.py:1876-1879`, short-circuit `or`). The writer's note at `messages.py:17:51` already says this. All 183/141 decisions stay. | 0 | low |
| R1 | remark (supports judgement 3) | `api.py:131-155, 171-172`, `_exitOnSignal.handler` | SIGPIPE is not only an outside event: when `main` has installed the handler and stdout is a pipe that the reader closed, the package's own write (`Reporter.flake`, `reporter.py:84-85`, through a buffered `io.TextIOWrapper`) causes it. Still no edge under the README rule: the package does not wait for the signal, and the frame in which CPython runs the Python handler depends on buffering and on where the eval loop next checks for signals. | 0 | none |

## Step 1: blind re-derivation

**Sample.** Skeleton made without the ledger: a scratch directory with a copy
of `projects.toml` and a `projects` link, `check.py --skeleton pyflakes`:
1045 sites (752 call, 25 decorator, 83 op, 96 getitem, 8 setitem, 1 delitem,
55 getattr, 3 setattr, 22 format). Calls are 72% of the sites, so a plain
draw tests the explicit sites well. I numbered the site lines from 0 in file
order, drew `random.Random(20261111).sample(range(1045), 70)`, and added the
14 value sites (none was in the draw): 84 sites. Kinds: 69 call (12 of them
value sites), 4 decorator (2 value sites), 3 getattr, 3 getitem, 3 op, 1
setitem, 1 format. 8 of the 84 are decided by the defaults only. I wrote my
callees for each site before I opened any file of the writer:
`$TMPDIR/heldout3-audit-pyflakes/blind.md`.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random draw | 70 | 70 | 0 |
| Value sites | 14 | 14 | 0 |
| **Total** | **84** | **84** | **0** |

The value sites are the heart of this package: `handler(node)` (38 callees),
`handler()` in `_run_deferred` (6), `messageClass(...)` in `report` (30),
`cls()` in `in_scope` (3), the two `func(self, ...)` of the annotation
wrappers (2 and 1), the two `is_name_match_fn(...)` (2 each), `fn(self,
annotation, parent)` (1), the two `parse_format_string(...)` (1 each),
`_doctest_parser()(docstring)` (1), and the two `@functools.wraps(func)` (1
each). Each callee set and each rejection is the same as mine. At
`handler(node)` I had `_unknown_handler` as a callee "if the writer differs,
for a ruling"; the writer keeps it with the same reason (J1).

**Exposure.** Before I wrote `blind.md`, one search of the earlier ledgers for
naming practice used an rg glob filter that rg does not apply to explicit
paths. It printed two lines of `pyflakes.ledger` (669 and 1207: `->
functools._lru_cache_wrapper.__call__`) and lines 35-40 and 139-140 of
`pyflakes.md` (which methods the package decorators and `functools.cache`
wrap; a heading). None of these is a sampled site, and the naming is the
micro-benchmark's. I also ran one `git status` with the checkout as the
working directory of the command (it reads; it runs no project code).

**My own errors (no disagreement).** `blind.md` says "all 51 classes of
messages.py" are passed to `report`: it is the 50 subclasses; the base
`Message` is never passed.

## Step 2: dispatch sets

| Site | Values | Callees | Ledger |
|---|---|---|---|
| `handler(node)` `:1252` | the upper-case class-body names over the ast classes of 3.11-3.15 (aliases `:1327-2285`) | 37 handler functions + `_unknown_handler` (J1) | same |
| `getattr(self, nodeType, ...)` `:1016` | no upper-case attribute is a property | `<builtin>.getattr` only | same |
| `handler()` `:778` | the 5 callables given to `deferFunction` (`:1314`, `:1747`, `:1978`, `:2023`, `:2051`) | 4 package lambdas or functions, `functools.partial.__call__`, and `in_string_annotation.in_annotation_func` called back by the partial | same |
| `messageClass(...)` `:891` | each of the 50 `Message` subclasses is passed by a `report` call (I matched every class to its call lines; 3.15 only: the three lazy-import classes; 3.11-3.13 only: `FutureFeatureNotDefined`; 3.14+: `TStringMissingPlaceholders`) | the 29 own `__init__` + `Message.__init__` | same |
| `cls()` `:816` | `_ast_node_scope` values, `DoctestScope`, `TypeScope` | `ClassScope.__init__`, `FunctionScope.__init__`, `<builtin>.dict.__init__` | same |
| `func(self, ...)` `:699`, `:707` | `handleAnnotation` (`@in_annotation`), `Checker.handleNode` (`:1313`); `handleStringAnnotation` | 2; 1 | same |
| `value.redefines(existing)` `:959`, `:969` | every binding class that `addBinding` gets | the 5 `redefines` | same (a `Builtin` never meets an existing binding: `:752-753`, `:1272-1273`) |
| `value.imported_name` `:882` | the 5 importation classes | 4 properties (`FutureImportation` inherits `ImportationFrom`'s) | same |
| 11 `super()` chains, 29 `Message.__init__(self, ...)` | MRO of each class | as the ledger | same |
| `self.handleAnnotation(...)` `:2011`, `:2069` | the class attribute is the `@in_annotation` wrapper | `in_annotation.in_annotation_func` | same |
| every call of `in_scope`, `_enter_annotation`, `_type_param_scope` (14 caller nodes) | `@contextlib.contextmanager` | `contextlib.contextmanager.helper` + the generator function | same |

## Step 3: what a sample cannot test

1. **Default rejections.** I listed every site of each default
   (`--report pyflakes --default`). `Binding.__repr__`, `Builtin.__repr__`,
   `Scope.__repr__` (25 sites) and `Message.__str__` (24): each f-string
   field and `%` operand is a str, an int or a class. `VariableKey.__eq__`
   (183) and `__hash__` (141): I read all their op, setitem and delitem
   sites (87) and the DICT and GLOBAL getitem sites; keys and operands are
   names, AST nodes, classes, ints and tuples of them. `VariableKey` objects
   occur only in `DICT` (accepted at `:1816:41`, `:1823:71`, `:1825:41`) and
   in the message arguments of A1.
2. **Implicit sites without candidates** (`--without-candidates`): 108
   iter, 141 truth, 19 with, 3 mapping, 80 class. The package defines no
   `__iter__`, `__bool__`, `__len__`, `__enter__`, `keys`, metaclass or
   `__init_subclass__`, and uses no `map` or `filter`. No missing site.
3. **Functions that no site calls**: 8 modules, `_exitOnSignal.handler`
   (judgement 3, R1), the `source_statement` properties of `Importation`,
   `SubmoduleImportation`, `ImportationFrom` (public; no package reader),
   `Scope.__repr__` (debugging). Each keeps its body's edges (rule A).
4. **Properties and setters**: the 55 getattr and 3 setattr sites; each
   receiver class defines or inherits the property it names. The setters of
   `futuresAllowed` and `annotationsFutureEnabled` are their getters' nodes.
5. **Rejections and notes**: I read the whole ledger. Every rejection reason
   and note holds, except the default reasons of A1.
6. **Callees outside the package**: 92 names, 266 edges. Each is named by
   the micro-benchmark rules and the README: default streams by class
   (`io.TextIOWrapper.write`/`.read`, `io.BufferedReader.read` for
   `open(..., 'rb')`), `collections.abc.Mapping.get` for `os.environ.get`,
   `collections.Counter.items` (inherited, named by the receiver's class),
   `argparse.ArgumentParser.add_argument`, `string.Formatter.parse`,
   `doctest.DocTestParser.get_examples`, `functools.partial.__call__`,
   `functools._lru_cache_wrapper.__call__`, `<builtin>.property.setter`,
   `<builtin>.dict.*` for the scope classes (subclasses of `dict`). B4/B5:
   client streams, paths, file names and builtins sets are opaque; the
   `str` receivers come from documentation (`reporter.py:51`,
   `checker.py:105-106`) or from the package's own calls (`api.py:108`).
7. **Untraced edges (49)**, all possible: 15 generator functions started by
   `contextlib`; 14 in version branches (3.15 lazy imports: `IMPORT` 4,
   `IMPORTFROM` 1, `_in_try` 2, two message `__init__` and their
   `Message.__init__`; 3.11-3.13: `FutureFeatureNotDefined.__init__` and its
   `Message.__init__`, `handleAnnotation -> handleNode`); 5 of
   `_unknown_handler` (J1); 8 in the debugging `__repr__` methods; 4 to the
   default streams (the tests replace them); `__main__ -> api.main` (the
   deselected subprocess tests); `handler -> sys.exit`; `_is_typing_helper
   -> _is_any_typing_member.<lambda1>` (`import typing` then
   `typing.List[int]` reaches `:653`).
8. **Rejected trace edges (4)**: `_io.StringIO.read`/`.write` from `main`
   and the three `Reporter` writers. The tests pass `io.StringIO` streams and
   `TestMain` replaces `sys.stdin`, `sys.stdout` and `sys.stderr`
   (`test_api.py:53-62`, read as data): client objects (B5). They stay rejected.
9. **Judgement calls** of `pyflakes.md` (9): I agree with each. 1 is J1.
   3 (signals) holds; see R1. 4 (version branches): every branch named runs
   on some version of 3.11-3.15. 5 (`Counter` and `VariableKey`): correct,
   including the hash collision of a `VariableKey` with the `str` of its
   name and the reflected `__eq__`.

## Judgement

The ground truth is complete and precise as far as I can test it: 84 of 84
sampled sites agree, every dispatch set matches, every untraced edge is
possible, and no default hides a call. The lead rules J1 (keep or remove
one edge). The writer may reword the two `VariableKey` default reasons
(A1); no edge changes.


## Round 3 complete source audit (2026-11-16)

This append preserves the historical audit above as an unchanged byte prefix.
Two independent source models were frozen before baseline comparison. The
review read all eight runtime modules (2,956 lines), then reviewed every one
of the 642 baseline pairs, 949 ledger site-target relations, and 2,674 scanner
sites, including the 1,837 unlisted sites. No target code, target tests,
generated target code or dependency was executed or imported.

The proposal retains every baseline pair and adds two outside pairs:
`Checker.__init__ -> functools._lru_cache_wrapper.wrapper` at
`checker.py:739:56`, and `Checker.handleDoctests` to that closure at
`:1259:53`. Pyflakes supports PyPy; the preserved PyPy 7.3.20 release
sources identify Python 3.11.13 and a Python cache wrapper closure. The
CPython wrapper-object edges remain. The proposed graph has 644 pairs
(376 internal, 268 outside); 592 match a trace name and 52 come from source
reading. All five trace rejections remain unchanged.

Metadata corrections distinguish the 1,045 sites requiring ledger/default
decisions from all 2,674 scanner sites, and distinguish unknown leading
future imports from late ones. A late unknown future import after `pass`
can reach `FutureFeatureNotDefined` on CPython 3.14+; the report site is
not version-guarded. This correction changes no pair.

The round-3 scratch handoff contains a source inventory and snapshots,
per-pair witnesses, all scanner-site decisions, all source/ledger six-tuples,
independent argument-binding rows, an exact six-file staged proposal, an
application patch and replay checks. The source-first memo records the
limited prior exposure to shared rules and aggregate historical headings.
The static checks establish artifact consistency; they are not an execution
test or proof of semantic completeness.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 complete source audit (2026-11-16)

The fresh source model was frozen before opening the baseline graph, ledger,
judgements, audit or trace. It covers all eight runtime modules, 189 unique
functions/lambdas, 199 definition bodies (two property getter/setter pairs
share graph nodes), and 2,674 scanner sites. The initial mandatory global
README read exposed historical aggregate counts and its global parser-option
example; the source model discloses this limited exposure.

All 644 baseline pairs and 951 site-target relations remain supported. The
audit also reviewed 1,837 omitted sites: 208 with candidates covered by the
six defaults, and 1,629 without candidates. All 197 graph nodes remain,
including 20 zero-edge nodes. All 63 diagnostic report sites bind their
arguments to the 50 passed message classes. Five trace rejections remain.

There are no original-baseline graph defects and no proposal-only graph
corrections. CPython and explicitly supported PyPy use the >=3.11 bound;
the README's older 3.9+ statement does not override the support drop. The
working normal/-O/-OO union adds no pairs. The two existing PyPy cache-wrapper
pairs were checked against preserved raw release sources, read as data.
Bytes paths produced by os.walk still reach bytes.endswith before that
builtin raises on the str suffix; the later suffix test does not run.

The current judgement records the fourth audit and scope clarification.
The graph, ledger, added-edge register and rejected-edge register are
unchanged. This paragraph is appended; the historical audit bytes above
are preserved. No target, test, dependency or generated code was executed
or imported. The root auditor runs structural/origin gates after handoff.
