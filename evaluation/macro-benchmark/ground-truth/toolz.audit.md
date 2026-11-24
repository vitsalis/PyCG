Status: closed (2026-11-24). F1 and F2 applied in `9ae1884` (re-check 1);
J4 ruled by b8-ruling-toolz-1 (referee, adopted by the lead) and recorded
in `3daebad` (re-check 2). Nothing is open; final graph 828 edges (484
inside, 344 outside).

# toolz: blind audit of the ground truth (batch 8)

Release 1.2.0, commit `451af60`. Audited files at the writer's commit
`d9a80bb`: `toolz.ledger` (2484 lines, 7 default rejections), `toolz.json`
(827 edges: 483 inside, 344 outside), `toolz.added.json`,
`toolz.rejected.json` (63 edges), `toolz.md` (J1 to J9). Blind answers:
commit `021a213` (`selection/batch-8-proposal/audits/toolz/`).

I read the analysed source, the tests (`toolz/tests`,
`toolz/sandbox/tests`), `bench/` (after the blind commit), `doc/source`,
`README.rst`, `pyproject.toml`, `tox.ini`, `.github/workflows/test.yml`
and the trace as data; the CPython (3.9.25 to 3.15.2) and PyPy (3.9 to
3.11) sources of `deps/` read only. Nothing of the package was run; no
analysis tool was used. Commands: `check.py --benchmark-dir <scratch>
--skeleton toolz` (skeleton without a ledger), `check.py toolz`,
`check.py --origin toolz`, `check.py --report toolz`, `check.py --report
toolz --without-candidates`; my own `ast` scripts for the draw, the
registry of `_signatures.py` and the binding check. Before the blind
commit I made one `grep -l` over `macro-benchmark/ground-truth/` that
excluded `toolz.*` and printed file names only (to find a precedent);
it showed no file of the writer.

## Final state

- Agreement: 144 of 159 sites identical; 5 more differ only in where the
  same edge is written (149 of 159 on the graph). Of the 10 sites that
  differ in edges, 9 are my errors (A1 to A3) and 1 is a writer entry that
  cannot run (F1, no graph edge).
- Edges missing: 1 if the writer accepts F2 (`join -> curry.__call__`).
- Edges that cannot happen: none in the graph; F1 removes six callees of
  one site, whose six edges stay through `functoolz.py:924` and `945`.
- If F1 and F2 are accepted: 828 edges (484 inside, 344 outside).
- J4 (193 registry lambdas) is the lead's; my opinion is under "For the
  lead".

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | low; callees at a site that cannot run | `functoolz.py` 933:31 `builtin_func(*builtin_args)`: the six `_sigs._*` functions | the branch needs a registered `func` whose `__signature__` has `__get__` (`functoolz.py:927-931`). No builtin of CPython 3.9 to 3.15 defines `__signature__` (`Objects`, `Python/bltinmodule.c`, `Modules/_functoolsmodule.c`, `itertoolsmodule.c`, `_operator.c`, `Lib/functools.py`, `Lib/operator.py`: none); on the classes `curry` and `Compose` the InstanceProperty gives `classval` `None` (`functoolz.py:160-161`), on `toolz.flip` and `toolz.memoize` a `Signature`, which the writer's own note at 930:28 says; on PyPy the original `_check_sigspec` gets only unregistered callables (`functoolz.py:944-947`) | 0 (the six edges `_check_sigspec -> _sigs._*` stay from 924:34 and 945:31) | writer: drop the six callees, note why the call is unreachable; also the md note "the registry branch ... runs for a non-Signature sigspec" should say that only the test runs |
| F2 | low; missed edge (judgement on a role) | `itertoolz.py` 887:27, 894:27, 907:31, 915:31 `rightkey(item)`: `-> toolz.functoolz.curry.__call__` (edge `join -> curry.__call__`) | `bench/test_join.py:18` passes the curried `get(0)` as `leftkey` (the writer's J1 admits it at `groupby`); `join`'s docstring documents the two keys as one role: "Usually the key arguments are callables to be applied to the sequences. If the keys are not obviously callable then it is assumed that indexing was intended" (`itertoolz.py:867-869`), and the code treats both alike (`877-880`). That is documentation joining the roles (pymysql: "Broader admission requires ... documentation joining the roles") | +1 inside | writer decides; if the roles stay separate, a note at 887:27 |

No finding of an edge that cannot happen in the graph. No wording
findings (W) and no remarks on the README (R) beyond the J4 case.

## Step 1: blind re-derivation

The skeleton (made in a scratch copy without the ledger): 1256 sites, 599
explicit, 440 `getattr`, 217 other implicit, 96 value sites. `getattr`
sites are 35% of the skeleton with one candidate (`toolz.__getattr__`), so
the draw is split by kind: `random.Random(20261124)`, `rng.sample` of 45
explicit, then 15 other implicit, then 10 `getattr`, plus the 89 value
sites that the draw did not take: 159 sites (`draw.py`, `sample.txt`,
`blind-answers.md`).

| Sites | Identical | Placement only | Differ |
|---|---|---|---|
| 45 explicit (drawn) | 43 | 1 (`keymap` 101:22) | 1 (`join` 894:27, also a value site) |
| 15 other implicit | 15 | 0 | 0 |
| 10 getattr | 10 | 0 | 0 |
| 89 value sites (added) | 76 | 4 (`fold` 70:22, 71:30, 74:22, 75:30) | 9 (`_signatures.py` 684:13; `functoolz.py` 305:33, 341:29, 720:20, 933:31; `itertoolz.py` 100:14, 887:27, 907:31, 915:31) |

| Id | Kind | Sites | Edges | Cause |
|---|---|---|---|---|
| A1 | my error: missed edge | `curry.__call__` 305:33, `curry.call` 341:29: `-> toolz.itertoolz.second` | 2 | the curried builtin `sorted` calls its key back; `test_curried.py:33` binds `key=second` |
| A2 | my error: missed edges | `pipe` 720:20 `-> concat`; `groupby` 100:14 `-> identity`; `join` 887:27, 894:27, 907:31, 915:31 `-> identity` | 3 | I did not read `bench/`, which upstream's CI runs (`.github/workflows/test.yml:50`): `bench/test_join.py:15`, `:18`, `:26`, `:34`, `bench/test_groupby.py:8` |
| A3 | my error: narrower role | `check_valid` 684:13: `<lambda284>`, `<lambda286>` to `<lambda290>` (keys `curry`, `flip`, `juxt`, `memoize`, `Compose`, `InstanceProperty`) | 6 | I held these package objects to B3 at `is_valid_args`. The tests pass every callable of `toolz` and `toolz.functoolz` to `is_partial_args` (`test_inspect_args.py:387-435`) and `toolz.curry`, `excepts`, `juxt` to `num_required_args` and `has_keywords` (`test_curried.py:44-50`), and the docstrings of `is_valid_args` and `is_partial_args` share their "Implementation notes" word for word (`functoolz.py:1104-1109`, `1133-1138`): one documented introspection role. I withdraw my answer; the lead's J4 ruling should name this |
| F1 | writer entry that cannot run | `_check_sigspec` 933:31 | 0 | see F1 |
| placement | same edges | `keymap` 101:22 (writer at 101:14), `fold` 70:22, 74:22, 71:30, 75:30 (writer at the partial, I at the map) | 0 | both placements are allowed (README "Limits of the site finder"; funcy J4) |

My independent derivation of the registry matched the writer's: 290
lambdas, 97 never registered or overwritten (Python 2 names,
`operator._compare_digest`, which `from _operator import *` skips, the 45
dunder aliases, and `builtins.abs`, overwritten by `operator._abs`), 193
registered. My blind witness for `curry.__eq__` at the registry lookups (a
client object with a chosen hash) gives the same edges as the writer's
better one (`toolz.flip()` returns a curry equal to the stored key, J3).

## Step 2: exhaustive checks

- **Default rejections (7).** Read every explicit site that each decides
  (`check.py --report toolz`) and the implicit sites of the sample:
  `toolz.__getattr__` (401 sites: every name that the package loads on
  the module `toolz` exists, `__init__.py:1-20`; the client qualname walk
  of `curry.__reduce__` is J7); the six `__eq__`/`__hash__` defaults
  (sets and dicts of client values in `dissoc`, `unique`, `isdistinct`,
  `join`, `memoize.key`, `curry.__hash__`'s keywords, `EqualityHashKey`'s
  `hash(val)`, `tlz`'s `hash(tv)`). Each holds; the accepted sites are the
  registry lookups (J3), the nested curries and Composes (J2) and
  `unique`'s EqualityHashKeys.
- **Callback roles (J1).** Every callable parameter checked against the
  tests, `bench/`, the docstrings and `doc/source`: the writer's table is
  complete except F2. Client-only roles confirmed (`apply`, thread forms,
  `juxt`, `do`, `flip`, `excepts` func, `accumulate`, `merge_sorted`,
  `iterate`, `diff`, `reduceby` binop, the three filters, `fold`).
- **Dispatch sets.** `InstanceProperty.__get__` reaches the nine package
  fgets (`curry.func`, `__signature__`, `args`, `keywords`, `func_name`,
  `Compose.__doc__`, `__signature__`, `_get_annotate`, `excepts.__doc__`;
  `__wrapped__` is `attrgetter`, a library callable). The 43 package
  callables that curries wrap, plus `second`, are complete
  (`curried/__init__.py:58-100`, `@curry`, `curried/exceptions.py`,
  `sandbox/core.py:13`).
- **Uncalled functions** (155, 97 of them registry lambdas that no
  runtime registers): `find_module`, `load_module`, `toolz.__getattr__`,
  the pickling hooks, `memof`, `juxt.__call__`, `excepts.__call__`,
  `_InstanceAnnotations.__get__`, `random_sample.<lambda1>` and the public
  functions that only clients call. Each has no package caller under the
  rules.
- **Special methods and properties.** `type(self).__doc__` and
  `getattr(func, '__doc__')` on the class `excepts` call the
  InstanceProperty with no instance (CPython `Objects/typeobject.c:875`
  in 3.9, `type_get_doc` in 3.15); `type(self).__name__` reads the type's
  name. `Compose.__name__` at 524:29 and 539:19 (nested Compose),
  `curry.__get__` at the getattr walks. Agreed.
- **Notes, rejections, exclusions.** Read all; the `exclude` lines at
  684:13 list the 97 lambdas above. Only F1's note is wrong.
- **Callees outside the package.** All 91 names checked against the
  micro-benchmark rules and the sources (`types.MappingProxyType.values`,
  `<builtin>.property.__get__` for the explicit `property.__get__`,
  `random.Random.random`, `collections.defaultdict.items`,
  `importlib.machinery.ModuleSpec`, `annotationlib.annotations_to_string`).
  The client `d` of the dicttoolz functions is `<builtin>.dict` by their
  docstrings (B4, J8). No naming error.
- **Rejected trace edges (63).** All are doctest-defined functions, test
  callables from outside the package, or the tests' `os.environ` and
  Mapping subclass; each fits B2's last sentence or B5.
- **Trace edges that the graph lacks:** none (`check.py --report`).
- **Implicit sites without candidates** (`--without-candidates`): the
  iteration sites that consume package lazy objects are `frequencies`
  (countby's map, added by the writer), `unzip`'s `tuple(starmap(...))`,
  `fold`'s `list(results)`, `topk`'s `nlargest` and the three
  `dict.update` consumers; the documented pipelines (`streaming-
  analytics.rst`, `parallelism.rst`, `README.rst:67`) add no other
  package callback. Lazy objects returned to the client (`remove`,
  `mapcat`, `pluck`, `partitionby`, `random_sample`, `rest`) call nothing
  in the package (funcy J4).

## Step 3: binding check

An `ast` script matched every ledger call whose callee is a package
function named at the call (152 pairs) against the callee's signature: one
flag, a false positive (`tlz_loader.exec_module(...)` is a bound method).
The callbacks were checked by hand: `reduce(evalform_front, forms, val)`,
`starmap(pluck, enumerate(seqs))`, `nlargest(key=getter.<lambda1>)`,
`partial(_reduce, binop[, initial=...])` over a chunk,
`partial(instanceproperty, ...)(fget)`, `_InstanceAnnotations.fget(obj)`,
`builtin_func(*builtin_args)` (`_is_arity(n, func)`), `memoize.key(args,
kwargs)`, `assoc_in.<lambda1>(x)`, `reduceby.<lambda1>()`,
`return_none(e)`, `apply()`, and the wrapped callables of curries (a
witness binds for each). No call fails to bind; no code after a failing
call.

## The writer's judgement calls

| J | Opinion | Nearest rule |
|---|---|---|
| J1 | Agree, with F2. `bench/` counts as tests: upstream's CI runs `pytest bench/` | B2 (tests, documented examples), funcy (position-free compose role), B5 |
| J2 | Agree: documented curries bind curries and Composes, so the tuple hash, `==` and `!r` reach their methods | B2, "Special methods that a library call invokes" |
| J3 | Agree; the `toolz.flip()` witness is deterministic | "Call sites and candidates" (equal hashes call `__eq__`), B5 client control flow |
| J4 | The lead's; my opinion below | B2, B3, B5 |
| J5 | Agree | README "Limits of the site finder", funcy J4 |
| J6 | Agree; verified in `inspect.py` (`unwrap`, `_signature_from_callable`) and `type_get_doc` | callback rule (B5), uncertainties ruling |
| J7 | Agree | B3 (anytree, aiocache: client attribute names) |
| J8 | Agree | B4 |
| J9 | Agree | callback rule; both outcomes of an optional import |

## For the lead

**J4: the lambdas that `check_valid` calls (`_signatures.py:684`), 193
or 61 (132 inside edges).** My opinion: every lambda that an admitted
runtime registers is a callee (the writer's reading), for these reasons.

1. The keys are client values of a public role. `is_valid_args` is
   public (rule C: `toolz.functoolz.is_valid_args`; its docstring has
   doctests), and so are `curry` and the curried builtins that reach it
   through `_should_curry` (`functoolz.py:330`). B2 gives the values of a
   parameter as "client objects, the values that the package defines for
   that parameter's role, and the package's defaults". The admission
   tests of B2 and B3 (annotation, documentation, tests; "an arbitrary
   package object passed where any object or any callable is accepted")
   restrict **package** values. A builtin is not a package value: any
   builtin is a client object, and the docstring states the role covers
   them ("Many builtins in the standard library are also supported",
   `functoolz.py:1109`, with `map` as its example at `:1101`).
2. The client's choice selects package code. B5 makes a client object
   opaque: its own methods have no outside callee. But "their effects on
   control flow count" (clarification "Client control flow (B5)"). Here
   the package's own code looks the client value up in its own table
   (`signatures[func]`, `_signatures.py:694`) and calls the package
   lambda explicitly (`:684`). The callee is the package's code for a
   supported input, not the client object.
3. The aiocache clause does not fit. It covers "a string of the client
   that selects a method of an outside object that the package made": the
   selector is a free name, and the callee is outside code that the name
   picks from an open set. jsonpickle (d) and (e) apply it to a backend
   module named by the tests and to `bz2`, named only in a docstring; in
   both the edges that went or stayed were calls into the client-chosen
   module (outside). In toolz the selector is the role's own value, and
   the table is closed and package-defined: the registry is the
   package's own list of the callables it supports (`_signatures.py:6-10`).
   Restricting it to the keys that the tests happen to pass would make
   most of the package's handling of its documented inputs unreachable.
   The aiocache clause's other sentence ("A check on another parameter
   does not decide a role") does not apply either: the registry is how
   this parameter is handled, not a check on another one.
4. The runtime makes every registered key reach `check_valid`: PyPy is
   admitted (classifier, CI jobs PyPy 3.9 to 3.11; "Implementation,
   version and platform combinations"), and its `_check_sigspec`
   (`functoolz.py:942-947`) sends every registered callable to the
   registry; on CPython the keys without a signature do (`frozendict` on
   3.15 has none, `Objects/dictobject.c:8537`). A witness binds for every
   lambda (the client chooses the arguments).
5. Six of the 193 keys are package objects (`curry`, `flip`, `juxt`,
   `memoize`, `Compose`, `InstanceProperty`). For them B3 does apply; they
   are admitted only if the introspection functions are one documented
   role (A3: the tests pass every toolz callable to `is_partial_args` and
   to `num_required_args`/`has_keywords`, and the two docstrings share
   their implementation notes). If the lead holds the roles per function
   (pymysql: "One parameter's admitted classes do not pass to another"),
   these 6 edges go (187). `excepts` stays either way
   (`toolz.curried.excepts` reaches it on PyPy).

No rule of the README decides the case expressly; the nearest ones (B2's
client values, B5's control-flow clarification) favour the wide reading,
and the narrow one extends a clause written for open-ended names of
outside code. Since it decides 132 inside edges, it goes to the referee
by the brief's rule.

## Re-check

### Re-check 1, against `9ae1884` (2026-11-24)

The lead's rulings: F1 apply; F2 admit (+1 inside); J4 to the referee, with
the six package-object keys (A3) as a sub-question.

| Finding | State at `9ae1884` | Result |
|---|---|---|
| F1 | `functoolz.py` 933:31 has no callee and a note that the branch cannot run; `toolz.functoolz._check_sigspec` keeps its six edges to `_num_required_args`, `_has_varargs`, `_has_keywords`, `_is_valid_args`, `_is_partial_args`, `_is_arity` (through 924:34 and 945:31) | closed |
| F2 | `-> toolz.functoolz.curry.__call__` at `itertoolz.py` 887:27, 894:27, 907:31, 915:31, with the evidence in the note of 887:27; the graph gains `toolz.itertoolz.join -> toolz.functoolz.curry.__call__` | closed |
| J4 | unchanged (193 lambdas at 684:13), with the referee | open |

Nothing else changed: the ledger diff `bfa7a47..9ae1884` touches only these
five sites; the graph diff is exactly the one added edge (none removed);
`toolz.md` records the rulings and the new totals. `check.py toolz`: no
errors, 828 edges (484 inside, 344 outside). `check.py --origin toolz`:
576 trace edges, 63 rejected, 514 traced (174 / 340), 314 added (310 / 4),
828 (484 / 344).

### Re-check 2, against `3daebad` (2026-11-24)

The ruling (`selection/batch-8-proposal/rulings/b8-ruling-toolz-1.md`,
b8-gt `d8b840d`): all 193 lambdas stay at `_signatures.py` 684:13,
the six package-object keys included (one documented introspection role;
my withdrawal of A3 accepted); no edge changes; the 97 excluded lambdas
are 51 unavailable and 46 overwritten, not 44 and 53.

| Check | Result |
|---|---|
| The split, from the source | My own derivation (`ast` over `_signatures.py`, the names of `builtins`, `functools`, `itertools`, `operator` on CPython 3.9 to 3.15 and PyPy 3.9 to 3.11): 51 unavailable = the 50 lambdas of 38 names that no admitted runtime has (14 Python 2 builtins, 5 `itertools.i*`, 19 operator Python 2 names, 7 of them the dunders `__delslice__`, `__div__`, `__getslice__`, `__idiv__`, `__irepeat__`, `__repeat__`, `__setslice__`) plus `operator._compare_digest`, which `from _operator import *` skips; 46 overwritten = 45 dunder aliases (`Lib/operator.py:416-460` in 3.9) plus `builtins.abs` (`operator._abs`, `Lib/operator.py:22`). Both `exclude` lines at 684:13 hold exactly these sets (51 and 46); they are disjoint from the 193 callees, and the three sets make the 290 lambdas |
| The callees | 684:13 keeps the 193 lambdas of the ruling's ranges |
| Notes and `toolz.md` | the note at 684:13 (and its copy in `toolz.added.json`), the two `exclude` reasons, J4, the status line and the "Audit" section cite b8-ruling-toolz-1 and give 51 and 46 |
| Nothing else changed | the diff `9ae1884..3daebad` touches only the 684:13 entry, its copy in `toolz.added.json` and `toolz.md`; `toolz.json` is identical |
| `check.py toolz` | no errors; 828 edges (484 inside, 344 outside) |
| `check.py --origin toolz` | 576 trace edges, 63 rejected, 514 traced (174 / 340), 314 added (310 / 4), 828 (484 / 344) |

J4 is closed. Nothing is open; the audit is closed.

## Codex round 1 re-check (2026-11-24)

Against `d7b23f1` (M01 to M17) and `e9b49d7` (R01, R02), from the
findings in `selection/batch-8-proposal/codex-audits/round-1/toolz.md`.
The toolz files did not change between my re-check 2 (`ae76c4d`) and
`dce3eb7`; the merges in between touch only other packages.

**Graph.** `toolz.json` at `d7b23f1` against `dce3eb7`: exactly 17 edges
added, the 17 of the findings, none removed; `e9b49d7` leaves the graph
unchanged. `check.py toolz`: no errors, 845 edges (501 inside, 344
outside). `check.py --origin toolz`: 576 trace edges, 63 rejected, 514
traced (174 / 340), 331 added (327 / 4), 845 (501 / 344).

**Each finding, against the source and the rules.**

| Id | Edge | Site in the ledger | Check | Result |
|---|---|---|---|---|
| M01 to M03 | `valmap -> curry.__call__`, `frequencies`, `concat` | `dicttoolz.py` 85:14 (the `dict.update` that consumes the map, as for `identity` and `Compose.__call__`) | `compose(x)` returns `x` (`functoolz.py:672-673`); the documentation names a compose output for valmap's `func` (`streaming-analytics.rst:91`, `:101`), and curries, `frequencies` and `concat` are admitted compose inputs (J1). The factory-output clarification covers exactly this ("one-argument `compose`"). `concat` is a plain function, so the call happens | agree |
| M04, M05 | `groupby -> curry.__hash__`, `curry.__eq__` | 100:10 getitem `d[key(item)]`; the hash also at 103:11 setitem `rv[k]` (no new edge) | `toolz.curried.get()` binds nothing and returns an equal curry (`bind`, `functoolz.py:338`); `key(item)` then fails in `get` (missing `seq`), `_should_curry` returns True (`is_partial_args` binds, no varargs, `is_valid_args` fails) and `bind` returns `curry(get, item)`. Two equal items give equal, distinct curries with equal hashes (`hash((get, (0,), None))`), so the defaultdict compares them by the stored key's `curry.__eq__`. Admission: the documented key `get(3)` (`streaming-analytics.rst:87`) with other public arguments (FO) | agree |
| M06, M07 | `join -> curry.__hash__`, `curry.__eq__` | the nine lookups 888:20 to 924:20 | the same curries as right keys (the one key role of F2, `bench/test_join.py:18`) meet the left keys that `groupby` stored | agree |
| M08, M09 | `reduceby -> curry.__hash__`, `curry.__eq__` | 622:14, 624:18, 627:18, 628:10, 628:23 | the same key mechanism; `reduceby(get(3), ...)` is documented (`streaming-analytics.rst:155`) | agree |
| M10, M11 | `unique -> curry.__hash__`, `curry.__eq__` | 265:20, 266:25 | `curry(EqualityHashKey)` with no bound key: `EqualityHashKey(0)` misses `item` (`sandbox/core.py:64`), `_should_curry` returns True and `bind` returns `curry(EqualityHashKey, 0)`, equal and distinct per equal item. Admission: the documented factory `curry(EqualityHashKey, ...)` (`sandbox/core.py:13`, `:28-29`, `:39`) with other public arguments (FO) | agree |
| M12 | `frequencies -> curry.__call__` | 547:17 iter `seq` | `compose(frequencies, map(get(0)))`: `curry.__call__` of the curried map returns a map over the get curry, and `frequencies` iterates it (README "Limits of the site finder"; B5). README.rst:67 composes `frequencies` with the curried map; `streaming-analytics.rst:38` passes a curried get to it | agree |
| M13, M14 | `frequencies -> curry.__hash__`, `curry.__eq__` | 548:10 getitem and setitem | the same map over `get()` yields equal, distinct curries as keys of the defaultdict | agree |
| M15 to M17 | `curry.__call__ -> curry.__call__`, `getter.<lambda1>`, `getter.<lambda2>` | `functoolz.py` 305:33 (the partial's call; the note updated) | `compose(sorted, map(get(0)))`, `compose(sorted, pluck([0]))`, `pluck([])`: the curried `sorted` (`curried/__init__.py:92`) is a curry, admitted in the compose role (J1); its partial calls `sorted`, which consumes the map that the previous curry made (`pluck`, `itertoolz.py:796-797`; `getter`, `:808`, `:812`). The callback belongs to the package call that hands the map to library code. Not at `curry.call` (341:29): no document hands a package-made map to `.call`, and the edges there would differ | agree |

**Nothing else changed.** The ledger diff `dce3eb7..d7b23f1` has six
hunks, all at the sites above; its one removed line is the old note at
305:33, which the new note replaces with the same text plus M15 to M17.
The binding of each new callee holds (`curry.__hash__`/`__eq__` through
dict and set operations; `curry.__call__` and the getter lambdas with one
item). `e9b49d7` changes only `toolz.md`.

**R01 and R02.** `toolz.md` ("Codex round 1") records both as lead
rulings of 2026-11-24 with no edge: R01 (`Compose.__call__ -> identity`
through `compose(compose())`: the tests admit the Compose values they
pass, not the zero-argument output, and FO needs documentation naming it)
and R02 (`memof` and `memoize.key` to `__hash__`/`__eq__` of curry and
Compose: admission follows forwarding from an admitted parameter onward,
pymysql; nothing passes a package value to a memoized function). Neither
adds an edge to the ledger or the graph. I agree with both readings.

No disagreement. Nothing is open; the audit stays closed.
