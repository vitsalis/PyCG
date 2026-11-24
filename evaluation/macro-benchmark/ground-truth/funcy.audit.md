# funcy: independent audit of the ground truth

Release 2.1, commit `04aafae9a7390cce610b45b5dca3a630e43c1713`. Audited files:
the ground truth as its writer left it (commit `f6ec69d`): `funcy.ledger`
(812 entries, 179 notes, 9 default rejections, 3 exclusion lines),
`funcy.json` (890 edges: 399 in the package, 491 outside),
`funcy.rejected.json` (51 edges) and `funcy.md` (judgements J1 to J12).
`check.py --benchmark-dir macro-benchmark-heldout-4 funcy` reports no
errors. The trace confirms 679 edges (76.3%); 211 come from reading only.

I read the 16 modules, `tests/`, `docs/*.rst`, `README.rst` and `setup.py`
as data. I ran nothing of the package and no analysis tool. I did not read
the other packages of the set.

**Result.** No edge of the graph is an edge that cannot happen. One edge is
missing (F1, +1). Two ledger entries list callees that cannot reach their
site, with no change to the graph (F2). Two judgements need a ruling
(R1, R2: up to -17 and -22 edges). One remark on the README (R3).

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | missed edge | `funcs.py:110:49` `g(*a, **kw)` in `compose.<lambda1>.<lambda1>` -> `funcy.primitives.isnone` | `docs/primitives.rst:19`: `notnone` is "A shortcut for ``complement(isnone)``". `complement(pred)` is `compose(__not__, pred)` (`funcs.py:121`), so `isnone` is the later function `g`. J9 takes an inline expression of the same kind (``count_by(identity, ...)``, `seqs.rst:528`) as documentation. The note at 110:49 lists `identity`, `re_tester('^_')`, `r'^_'` and `even` for the pred of `complement`, not `isnone`. | +1 (inside), 890 to 891 | likely |
| F2 | callees that cannot reach the site (ledger only) | `funcs.py:83:24` lists `lmap` and `keep`; `funcs.py:86:28` lists `lmap` | `autocurried`, `funcs.py:75-90`. Line 83 runs only when line 80 fails. Without `spec.varkw`, line 80 fails only if `len(args) + len(kwargs) < max_n`, and then `len(args) + len(set(kwargs) & spec.names) >= max_n` is false (the intersection has at most `len(kwargs)` names). Neither `lmap` (`'f*'` in `ARGS['funcy.seqs']`, `_inspect.py:88-91, 108-116`) nor `keep` (`_code_to_spec`, `_inspect.py:163`) has `**kwargs`. Line 86 needs `req_n < max_n`: `lmap` has `req_n = max_n = 2`; `keep` has `req_n = 1`, `max_n = 2` (`test_funcs.py:141`, `_keep('01')`). An explicit `n` gives `Spec(n, set(), n, set(), False)` (`funcs.py:72`), which reaches only line 81. So 83:24 has no package callee and 86:28 has `keep` only. The edges `autocurried -> lmap` and `-> keep` stay (81:24). The notes "as at 81:24" go. | 0 | certain |
| R1 | ruling (the README does not decide) | J3: `<builtin>.set.__contains__` for `make_func` of a set (15 edges); the same question for `<builtin>.property.__get__` and `__set__` at `objects.py:47`, `52` (2 edges) | `make_func` checks the abstract `collections.abc.Set` (`funcmakers.py:22`), and B4 says that an abstract type fixes no class. But `extended_fns.rst:8-16` names "set" in a table that names concrete kinds (int, slice, string) and uses "mapping" for the abstract case, and B4 lets the documentation fix a concrete type; the tests pass builtin sets. `wrap_prop` is documented for "a property" (`objects.py:36`, `objects.rst:32`); the tests wrap a builtin property that the test builds (otherwise a client object, B5). My blind reading took both as opaque. Proposal: keep the writer's reading (a documented builtin type name fixes the type, as `dict` does in B4) and state it in B4. If the lead rules them abstract: -15 edges, and 3 trace edges (`split_keys`, `iffy.<lambda1>`, `juxt.<lambda1>` -> `set.__contains__`) move to the rejected file; for the property, -2 edges and 2 trace edges move. | 0 or -17 | - |
| R2 | ruling (the README does not decide) | J6: collection types read from the whole of `colls.rst` | B4 speaks of "a parameter's annotation or documentation". J6 applies the type lists of the `merge` entry ("dicts, sets, lists, tuples, iterators or strings") and of the `walk_keys` entry ("dict, defaultdict, OrderedDict") to every collection function, also where the function's own entry names no type. J1 reads the documentation per entry for callables; J6 reads it per module for outside types. The per-entry reading removes 22 edges: `empty` -> `set`, `tuple`, `OrderedDict`; `walk_values` -> `set`, `tuple`, `OrderedDict`; `select` -> `OrderedDict`; `split_keys` -> `OrderedDict`, `OrderedDict.items`, `defaultdict.items`; `project` -> `OrderedDict`; `omit` -> `OrderedDict`; `itervalues` -> `defaultdict.values`, `OrderedDict.values`; `join` -> `defaultdict.copy`, `OrderedDict.copy`, `defaultdict.update`, `OrderedDict.update`; `update_in` -> `defaultdict.copy`, `OrderedDict.copy`, `defaultdict.get`, `OrderedDict.get`. It keeps `walk`'s `set` and `tuple` (`colls.rst:37-38`) and `OrderedDict` (`flip(OrderedDict(...))`, `colls.rst:174`, reaches `walk`), `select`'s `set`, `dict`, `tuple` (`colls.rst:87, 90`; `README.rst:56`), `join`'s list, tuple, dict and set (`merge`), and every type that an `isinstance` test or `FACTORY_REPLACE` fixes. One trace edge moves to the rejected file: `join -> collections.defaultdict.copy` (`test_colls.py:70-72`). Proposal: the per-entry reading, which is the literal B4 and agrees with J1. | 0 or -22 | - |
| R3 | README wording | inline code in prose as a documented example | B2 names "documented examples". J9 counts the inline ``count_by(identity, ...)``; F1 applies the same to ``complement(isnone)``. Proposal: an inline expression that passes a package value counts as a documented example. | 0 | - |

## Step 1: blind re-derivation

**Skeleton and sample.** I made the skeleton without the ledger: a scratch
benchmark directory `/tmp/claude-501/heldout4-audit-funcy/` with a copy of
`projects.toml` and a link `projects` to `macro-benchmark-heldout-4/projects`,
then `check.py --benchmark-dir <scratch> --skeleton funcy`. It has 1473
sites: 785 call, 17 decorator, 671 implicit; every implicit site has a
candidate. I numbered the sites by module (skeleton order), line and
column, and drew `random.Random(20261111).sample(sites, 70)`. The draw has
41 call, 2 decorator, 10 getattr, 4 setattr, 6 iter, 4 op, 1 getitem, 1
setitem and 1 mapping site. No kind dominates the skeleton (getattr is 21%;
the largest candidate, `CacheMemory.__getitem__`, is at 358 of 1473 sites),
so the draw is plain. I added the 112 value sites (9 were drawn): 173 sites.

I wrote the callees of each site from the source, the tests and the
documentation before I opened any file of the writer or the trace. The
evidence is in the scratch directory: `blind.txt` (SHA-256
`2eb3146957bd8fb32ffe07ac7a8c506a9d49c13218de5fe775535179dca4885d`, written
at 11:05 before the writer's files were opened), `sample.txt` (the draw),
`skeleton.ledger` and `draw.py`. In `blind.txt` I marked four questions as
open: one role across functions, the signature default `key=identity`, the
documented collection types, and the coupling of `func` and `spec` in
`autocurry`.

| Group | Sites | Agree | Differ |
|---|---|---|---|
| Random sites that are not value sites | 61 | 60 | 1 |
| Value sites | 112 | 84 | 28 |
| **Total** | **173** | **144** | **29** |

The 29 differences, each site counted once:

- **I was wrong (4).** `flow.py:26:37`: I named `<builtin>.Exception`. With
  the default `Exception`, positional arguments need an explicit class
  first, and `Exception` takes no keyword arguments, so no package value
  reaches the call (J10 is right). `colls.py:131:26`, `157:26`, `202:16`: I
  named `operator.itemgetter.__call__`, which `map` or `filter` calls back;
  a library callable that library code calls back is no edge (README,
  "Callees outside the package").
- **Naming only, I was wrong (1).** `funcs.py:110:47`: I wrote
  `operator.__not__`. The writer's `operator.not_` follows the rule for a
  name that a module does not list in `__all__` (asciinema:
  `termios.tcsetattr`) and the micro-benchmark example `operator.add`.
- **The writer missed an edge (1).** `funcs.py:110:49`: `isnone` (F1).
- **The writer lists callees that cannot reach the site (2).**
  `funcs.py:83:24`, `86:28` (F2). No graph change.
- **Judgements (21).** J3 (`<builtin>.set.__contains__`) at 15 more sites
  (R1). J6 (`tuple`, `set`, `OrderedDict` of the factory) at 6 more sites
  (R2). At `seqs.py:257:41` the writer also adds `isa.<lambda1>` and `odd`
  to `split`, because J1 makes `split` and `lsplit` one role; I had them at
  `lsplit` only. I accept J1: one docs entry documents both, as
  asyncstdlib's documentation made its iterable parameters one role.

All other sites agree, also the hard ones: the compose pair (`f` and `g`),
`juxt` and `ljuxt` (with J1's exclusions), the three `iffy` callbacks, the
seven `@decorator` functions at `decorators.py:47`, the stacked wrappers
at `flow.py:42` and `152`, `curry` reaching `re_test` through the partial
of `funcs.py:52`, the `rpartial` recursion of `rcurry`, the
`time_formatters` lambdas, `self.__class__(...)` with
`LabeledContextDecorator` itself, and `identity` from the signature
`key=identity` (J9).

## Step 2: exhaustive checks

**Receivers (B1).** `self.__class__(...)` (`debug.py:106`) is a
`LabeledContextDecorator`, `log_errors` or `log_durations`; `with cm`
(`debug.py:115`) gives the enter and exit methods of the two subclasses;
`self.decorator(label)` (`debug.py:104`) is inherited by all three.
`memory` in `_memory_decorator` is a dict or a `CacheMemory`: `memory[key]`
and the store are accepted at `calc.py:52`, `55`; `memory.pop` is
`dict.pop` for both; `memory.clear` is `CacheMemory.clear` or `dict.clear`.
`call()` in the seven `@decorator` functions is `Call.__call__`, built at
`decorators.py:46`. All agree.

**Callback roles (B2).** For each callback parameter I listed the package
values from the package's own calls, the tests and the documentation. I
grepped `docs/*.rst` and `README.rst` for package functions passed as
arguments (42 lines) and checked each against the graph. Every documented
value is at its sites, except `isnone` (F1). The lazy consumers of J4 (the
26 sites whose package callees are not candidates) match the roles:
`_lmap` (11 values, among them `first`, `second`, `lcat`, `autocurried`,
the `make_lookuper` wrapper, the `silent` wrapper and a composed lambda from
the documentation), `_lfilter`, `lremove`, `lkeep`, `lcat` (the map of
`lmapcat`), `lsplit_by`, `take` (the filter of `one`), `some`, `colls.all`,
`colls.any`, `is_distinct`, `partition_by`, `lwhere`, `re_all`, and J5's
`first -> where.<lambda1>` and `group_values -> re_finder.<lambda2>`. No
other package site consumes a lazy object with a package callback:
`lreductions` hands `accumulate` only client functions; `pluck`,
`pluck_attr`, `invoke` and `zip_values` use builtins, `itemgetter`,
`attrgetter` or `methodcaller`.

**Default rejections.** The 9 defaults decide 1248 site pairs. I read
every explicit site that the report lists for each default. None runs the
candidate: a `CacheMemory` iterates with `dict.__iter__`, and its `get` and
`pop` do not call `__getitem__`; the package reads only `_func`, `_args`,
`_kwargs` and `__dict__` of a `Call`; `LazyObject` finds `_init`, `_setup`
and `__dict__` without `__getattr__`, and `object.__setattr__` bypasses its
`__setattr__`; no package code formats `EMPTY`, a `Call` (except
`decorators.py:85`, accepted) or a `WrapperProp`. The error message of
`get_spec` (`_inspect.py:136`) formats a `WrapperProp` only if a client
curries one, which B3 excludes.

**Functions that no site calls.** 135 nodes (16 of them modules) have no
caller. `dec`, `constantly.<lambda1>`, `curry.<lambda1>`,
`rcurry.<lambda1>`, `sums`, `Call.__repr__`, `LazyObject.__setattr__`, the
`nullcontext` methods, `WrapperProp.__repr__`, `WrapperProp.__del__` and
`EmptyType.__repr__` have no package caller and no documented package
value that would give them one. The others are public entry points.

**Special methods and properties.** The `__init__` chains, the context
manager methods, `cached_property.__get__` through `WrapperProp.__get__`,
`cached_readonly.__set__` (J7), the `CacheMemory` item methods and
`Call.__str__` through `__repr__` are all in the graph. No package class
uses `@cached_property`, so no package attribute load runs it.

**Rejections, notes and exclusions.** I read the reject lines and notes of
the 146 sampled entries and of every value site, and the 3 exclusion lines
(J1). They are correct, except the notes of F2.

**Callees outside the package.** I read all 130 outside names. They follow
the naming rules: `operator.not_` (J12), `collections.namedtuple._replace`
(a local function of library code), `types.MappingProxyType.values` for
`Signature.parameters`, `timeit.default_timer` (the imported path),
`functools.partial.__call__` for a call of a partial, `re.Pattern.search`
and `finditer`, `<builtin>.object.__new__`. Only R1 and R2 can change them.

**Rejected trace edges.** All 51 are calls of the tests' own callables
(builtins, bound methods, operator functions, and `whatever` expressions
that the tracer names by the `int` method they end in) and one client
object (`time.sleep` replaced with `timeouts.append`, `test_flow.py:92`).
All are correct.

**Judgement calls.** I agree with J1 (and its 3 exclusions), J2, J4, J5,
J7, J8, J9, J10, J11 and J12, and with the statement on the trace limit T1
(no `exec`, no thread; `reraise` has no package caller). J3 is R1, J6 is
R2.

## Edge changes

| Item | Change |
|---|---|
| F1 | +1 (890 to 891; 400 inside) |
| F2 | 0 (two ledger entries) |
| R1, if the lead rules "set" and "property" abstract | -15, and -2 for the property |
| R2, if the lead rules per entry | -22 |

## The README and the tools

The tools worked as the README describes. The README does not decide R1
(a builtin type name in the documentation, where the code tests an
abstract type) or R2 (whether one entry's documentation fixes types for
another function); R3 asks it to say whether an inline expression in prose
is a documented example. My own errors came from rules that the README
states clearly (library callables called back, arguments that cannot
bind).

## Re-check after the writer's changes

Checked against commit `f9b52d3` (clean tree). The lead's rulings: R1 kept
(the two `property` edges and the 15 `set.__contains__` edges stay); R2 by
the per-entry reading; R3: an expression in the documentation that passes a
package function in a role is a documented example, in prose as in a code
block.

**Nothing else changed.** The edge sets of `funcy.json` at `f6ec69d` and
now differ by exactly 23 edges: the 22 of R2 removed and the F1 edge
`compose.<lambda1>.<lambda1> -> funcy.primitives.isnone` added. The 305
nodes are the same. 869 edges: 400 inside, 469 outside. The ledger diff
has only these entries, their notes, the two F2 entries (83:24 now has no
callee and a note; 86:28 has `keep` only) and the F1 note.

**The 22 removed edges.** Each is right under the per-entry reading. No
entry or docstring of `empty`, `walk_values`, `select` (and its callers
`select_keys`, `select_values`, `compact`), `split_keys`, `project`,
`omit`, `itervalues`, `join`/`merge` or `update_in`/`set_in` names an
`OrderedDict`, a `defaultdict` method, or a set or tuple for these
parameters. No funcy code hands these functions such a collection: `omit`
gets the `**kwargs` dict of `get_arg`; `update_in` makes only `{}` (line
305); `join` gets client collections, and the documented
`merge(project(__builtins__, names), project(globals(), names))` gives it
dicts; `empty`, `walk_values`, `split_keys`, `project` and `itervalues`
have no package caller of this kind.

**No edge of the same kind is left.** I listed every collection-type
callee that remains in the graph (dict, list, set, tuple, str, bytes,
`OrderedDict`, `defaultdict`, mappingproxy). Each is fixed by the
function's own entry (`walk`: set, tuple; `select`: set, dict, tuple;
`merge`: dicts, sets, lists, tuples, strings; `split_keys`, `project`,
`update_in`: dict), by an `isinstance` test or `FACTORY_REPLACE`, by a
collection that funcy builds (kwargs dicts, `{}`, sets, lists,
`defaultdict(list)`), or by a package call from a function whose entry
names the type: `walk -> collections.OrderedDict` and
`iteritems -> collections.OrderedDict.items` through `flip(OrderedDict(...))`
and the `walk_keys` entry; `iteritems -> collections.defaultdict.items`
through the `walk_values` entry (both reach `iteritems`). These stay.

**R3.** Apart from ``count_by(identity, ...)`` (J9) and
``complement(isnone)`` (F1), the documentation has no inline expression
that passes a package function in a role, so R3 adds no other edge.

**The trace.** Every one of the 725 trace edges is in the graph (by name or
alias) or in `funcy.rejected.json`. The trace confirms 674 edges, 5 fewer
than before: `join -> collections.defaultdict.copy` moved to the rejected
file, and `itervalues -> defaultdict.values`, `join -> defaultdict.update`,
`split_keys -> defaultdict.items` and `update_in -> defaultdict.get` had
matched trace edges through an alias, which `<builtin>.dict.values`,
`.update`, `.items` and `.get` still match. The new rejected edge (52 in
all) is a trace edge, is not in the graph, and its reason is true: the
tests' own defaultdicts (`test_colls.py:70-72`), which `merge`'s entry does
not name. `check.py --benchmark-dir macro-benchmark-heldout-4 funcy`:
no errors.

**Result.** I agree with the changed ground truth. I would change no edge.

## Third complete source audit (2026-11-16)

The independent model and full source inventory were frozen before comparison. All 16 runtime files (2392 lines), 289 function nodes, 1714 scanner sites, 812 baseline ledger entries, 902 omitted sites, every default rejection and all 926 baseline pairs were reviewed statically. This pass finds 0 false-positive pairs and 60 missing pairs.

Documented compose factory outputs include compose() (identity) and a singleton compose whose make_func result is returned unchanged. The applicable map/lmap, walk and some_fn/juxt roles therefore include those concrete outputs. Documented handoffs of the map iterator carry them into _lfilter, lremove, lcat and some. The variadic compose role does not constrain an admitted own function to its example position. Documented rcurry partial outputs also vary with public n, adding its two outer callable branches at _lfilter. Every added pair has a concrete source/role/binding witness in the round-3 report. No arbitrary package-callable universe is admitted.

Site metadata moves make_func callbacks from lazy map construction to consuming reduce/list at funcs.py:111,130,136, and groupby mapper callbacks from construction to the for-iteration at seqs.py:411. These moves preserve their graph pairs. The audit also completes symmetric compose argument-site relations.

No target, test, dependency or generated code was imported or executed. The stored trace was used only by structural/origin gates. The historical audit text above is preserved byte-for-byte. Exact edits, git patch, six-file stage, all-site evidence, binding audit and input/artifact hashes accompany the round-3 report.

## Milestone review clarification (2026-11-16)

The three make_func callback moves in funcs.py are allowed normalizations:
111:32 -> 111:22 in compose, 130:27 -> 130:23 in ljuxt, and 136:27 -> 136:23 in
juxt. README ruling 12 permits either map/filter placement when construction
and consumption occur in the same function. Neither placement is an invalid
edge. These three groups must be separated from defect counts.

The groupby move at seqs.py:411:28 -> 411:21 remains a site correction under
the current text: its placement exception names map/filter only. The two
mapper relations belong at the consuming for-iteration. The remaining three
metadata groups add witnesses for existing pairs. Thus the original seven
metadata groups comprise three normalizations and four other site groups.
All graph pairs remain unchanged. Earlier audit bytes remain historical.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 source-first audit (2026-11-16)

A fresh source model and inventory were frozen before reading this project's baseline. The audit read all 16 runtime files (2,392 lines), current support declarations, and relevant documentation and test roles as inert source. It checked all 986 existing pairs, 1,714 sites, 813 ledger entries, 901 omitted sites, 305 module/function scopes (including 53 zero-edge scopes), nine default candidates deciding 1,247 site pairs, five excluded candidate-site pairs (four distinct nodes) at three sites, and 52 rejected trace pairs. No false-positive or missing pair was found. The graph, ledger and edge registers are unchanged. This records a new audit, not a metadata-defect correction.

The scope is Python 3.4 and later, CPython plus the explicitly supported PyPy implementation. Funcy 2.0 explicitly dropped Python 2. The normal/-O/-OO union remains the shared working assumption; the optional preference was unanswered. Removing the two assertions or docstrings adds no admitted named edge. Retained raw inspect, functools and regex implementation sources support the existing external names.

The audit retained the per-entry role limits: CacheMemory's dict inheritance does not establish a mapper/general-collection role; its documented memory operations are cache storage. Nested wrapped properties retain their descriptor role, while client-built functools partials remain opaque. Only joining explicitly documents a bytes separator; str_join retains the str edge. Post-freeze clarifications are recorded separately without changing frozen evidence.

Evidence is staged in `/tmp/pycg-macro-audit-pass4/funcy-agent`: source freeze, full pair/site/body/default/exclusion coverage, input hashes and separate post-freeze corrections. No target code or tests were executed. Root performs structural/origin verification before acceptance. Static review cannot prove absence of every possible missed edge.
