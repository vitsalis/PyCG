# toolz: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write toolz`
and `check.py toolz` report no error; every site is decided; every trace
edge that the graph lacks is in `toolz.rejected.json`. The audit's F1
and F2 are applied (see "Audit"). J4 is ruled by b8-ruling-toolz-1
(referee, adopted by the lead, 2026-11-24): the 193 registry lambdas
stay; no edge changed. Codex round 1: 17 missing edges applied, two
ruling questions ruled by the lead without edges (see "Codex round 1").

Release 1.2.0 (commit `451af60`). Analysed source: `toolz/` without
`toolz/tests/` and `toolz/sandbox/tests/`, and `tlz/` (root `.`): 16
modules, 462 functions (297 lambdas, 290 of them in the signature registry
of `toolz/_signatures.py`), 8 classes. The ledger is `toolz.ledger`;
`toolz.json` and `toolz.added.json` are generated from it; the 63 rejected
trace edges are in `toolz.rejected.json`.

## Versions, implementations and platforms

- `pyproject.toml`: `requires-python = ">=3.9"`, classifiers CPython and
  PyPy, Python 3.9 to 3.15; no OS classifier. The test job
  (`.github/workflows/test.yml`) runs CPython 3.9 to 3.15 (and the
  free-threaded 3.13t to 3.15t) and PyPy 3.9 to 3.11, all on
  `ubuntu-latest`. So CPython 3.9 to 3.15 and PyPy 3.9 to 3.11 are
  admitted ("Implementation, version and platform combinations"); Linux is
  the platform (the textdistance ruling). No edge depends on the platform.
- Both sides of `if PYPY:` (`functoolz.py:939`) run: the PyPy
  `_check_sigspec` (one node with the first definition) sends every
  registry key to the registry functions (J3, J4) and calls the first
  definition back (`functoolz.py:947`).
- `sys.version_info >= (3, 14)` (`functoolz.py:10`, `630`): the branch
  runs on 3.14 and 3.15, so `Compose._get_annotate` and its `annotate`
  closure exist and keep their edges; `annotationlib` is reached only from
  them and from `_combined_annotations` with a format (3.14 and later).
- `-O` removes the asserts of `expand_sig` (`_signatures.py:647`) and
  `fold` (`parallel.py:61`); the graph is the union of both modes.
- `cytoolz` is optional and no dependency: both outcomes of
  `import_module('cytoolz...')` in `tlz` run (J9); it calls no package
  code back.

## Values and architecture, as the ledger uses them

- **curry.** `curry(func, *args, **kwargs)` unwraps a curry-like `func`
  (`functoolz.py:205-217`) and stores a `functools.partial`; so the
  wrapped callable (`curry.func`) is never a curry. Calling a curry calls
  the partial (`curry.__call__`, `curry.call`), which calls the wrapped
  callable back; on a `TypeError`, `_should_curry` introspects it and
  `bind` makes a new curry (`type(self)(self, ...)`). The curries that the
  package makes: the names of `toolz.curried` (`curried/__init__.py:58-100`),
  `memoize` and `flip` (`@curry`), `toolz.curried.exceptions.merge` and
  `merge_with`, and the operator functions of `toolz.curried.operator`.
- **InstanceProperty.** `curry.func`, `__signature__`, `args`,
  `keywords`, `func_name`, `Compose.__doc__`, `__signature__`,
  `__wrapped__` (`attrgetter('first')`), `__annotate__` (3.14 and later)
  and `excepts.__doc__` are `InstanceProperty` descriptors. A load of one
  of these attributes calls `InstanceProperty.__get__`, which calls
  `property.__get__`, which calls the fget back (`functoolz.py:162`). So
  the callee of such a load is `InstanceProperty.__get__`, and the fgets
  are callees of `InstanceProperty.__get__` (the trace agrees). A load on
  the class gives `classval` (None, or the class docstring).
- **Compose.** `compose(*funcs)` returns `identity`, the one function, or
  a `Compose` whose `first` is the last argument and `funcs` the others in
  calling order. `complement(f)` is `compose(operator.not_, f)`.
- **getter.** `getter(index)` (`itertoolz.py:804`) turns a non-callable
  key into `getter.<lambda1>` (a list of one index), `getter.<lambda2>`
  (an empty list) or an `operator.itemgetter`. `groupby`, `reduceby`,
  `join`, `topk`, `countby`, `pluck` and `EqualityHashKey` apply it, so
  these results are package values of those key roles (as funcy's
  `make_func`). A direct call of an itemgetter is
  `operator.itemgetter.__call__`; one that library code calls (`map`,
  `heapq.nlargest`) is no edge.
- **The signature registry** (`_signatures.py`, private: its docstring
  calls everything there implementation details). `module_info` maps
  modules to names and lists of lambdas; `create_signature_registry`
  (run by `toolz/__init__.py:22`) keys the expanded lambdas by the
  callable that `getattr(module, name)` returns, for the names the module
  has. Python 2 names fail `hasattr`; `operator.__x__` is `operator.x` and
  `operator._abs` is `builtins.abs`, so the later entry overwrites the
  earlier one (J4). The keys include the curries `toolz.flip` and
  `toolz.memoize`, hashed by `curry.__hash__`.
- **tlz.** `tlz/_build_tlz.py` appends a `TlzLoader` to `sys.meta_path`
  and builds each `tlz` module from `cytoolz` or `toolz` (J9).

## Default rejections

| Candidate | Sites decided | Reason | Accepted at |
|---|---|---|---|
| `toolz.__getattr__` | 401 | the module `__getattr__` of `toolz` runs only for a missing attribute of the module `toolz`; no package load names one | nowhere (J7) |
| `Compose.__eq__` | 204 | no Compose reaches this comparison (B3) | `functoolz.py:298`, `550` (twice) |
| `Compose.__hash__` | 158 | no Compose is hashed here | `functoolz.py:292`, `558` (twice) |
| `curry.__eq__` | 171 | no curry reaches this comparison | `functoolz.py:298`, `550` (twice), `927`, `944`, `_signatures.py:692` to `782` (12 sites); `itertoolz.py:100`, `265`, `266`, `548` (twice), `622` to `628` (5 sites), `888` to `924` (9 sites) |
| `curry.__hash__` | 122 | no curry is hashed here | `_build_tlz.py:76`, `79`, `functoolz.py:292`, `558` (twice), `927`, `944`, `_signatures.py:671`, `692` to `782`; `itertoolz.py:100`, `103`, `265`, `266`, `548` (twice), `622` to `628`, `888` to `924` |
| `EqualityHashKey.__eq__` | 205 | no EqualityHashKey reaches this comparison; they reach only `unique`'s key role | `itertoolz.py:265`, `266` |
| `EqualityHashKey.__hash__` | 160 | no EqualityHashKey is hashed here | `itertoolz.py:265`, `266` |

The site counts are those of `check.py --report toolz`. The accepted
implicit sites were added by hand from `check.py --report toolz --default
<candidate>`.

## Judgement calls

1. **Roles of callable parameters (B2, B5).** Each callable parameter
   admits client callables (opaque) and the package values that the
   package's code, its tests and its documented examples (docstrings,
   `doc/source/*.rst`, `README.rst`) pass for that role, along the
   package's forwarding calls. The tests include `bench/` (upstream's CI
   runs `pytest bench/`, `.github/workflows/test.yml`; the trace does
   not). `examples/` is included by no document and is not used. The
   roles with package values:

   | Site | Package callees | Evidence |
   |---|---|---|
   | `curry.__call__` and `curry.call` (`functoolz.py:305`, `341`) | `functools.partial.__call__`; the 37 package functions and the class `excepts` that `toolz.curried` curries; `memoize`, `flip`, `curried.exceptions.merge`, `merge_with`; `EqualityHashKey.__init__`; `second` | `curried/__init__.py:58-100`, `@curry`; `sandbox/core.py:13`, sandbox tests; `test_curried.py:332` (the curried `sorted` calls its key `second` back) |
   | `Compose.__call__` (`functoolz.py:504`, `506`) | `Compose.__call__`, `curry.__call__`, `frequencies`, `concat`; `operator.not_` at 506 | `test_functoolz.py:822` and `702`; `README.rst:67`; `doc/source/streaming-analytics.rst:91`; `doc/source/parallelism.rst:53`; `bench/test_wordcount.py:13`; `functoolz.py:787`; `complement` |
   | `pipe` (`functoolz.py:720`) | `curry.__call__`, `concat` | `doc/source/streaming-analytics.rst:37`, `100`; `bench/test_join.py:15`, `31` |
   | `groupby` key (`itertoolz.py:100`) | getter's results, `first`, `second`, `identity`, `curry.__call__`; the curries that an underapplied curried get returns are hashed and compared at `100:10` (Codex M04) | join's forwarding (`itertoolz.py:882`) of `test_itertoolz.py:412`, `itertoolz.py:843`, `streaming-analytics.rst:192`, `281`, `bench/test_join.py`; `bench/test_groupby.py:8`; `streaming-analytics.rst:87` |
   | `join` rightkey (`itertoolz.py:887`, `894`, `907`, `915`) | getter's results, `first`, `second`, `identity`, `curry.__call__` | as above; the docstring treats the key arguments as one role (`itertoolz.py:867-869`), so the curried `get(0)` of `bench/test_join.py:18` counts here too (audit F2) |
   | `reduceby` key (`itertoolz.py:621`) | getter's results, `curry.__call__` | `streaming-analytics.rst:155` |
   | `unique` key (`itertoolz.py:264`) | `curry.__call__` (curries of EqualityHashKey) | `sandbox/core.py:39`, `sandbox/tests/test_core.py:48-74` |
   | `EqualityHashKey.key` (`sandbox/core.py:77`) | `first`, getter's results | `sandbox/tests/test_core.py:45`, `62-74` |
   | `memoize`'s func (`functoolz.py:462`) | `curry.__call__` | `test_functoolz.py:106` |
   | `valmap` func (`dicttoolz.py:85`) | `identity`, `Compose.__call__`; through the one-argument compose (FO, funcy) its admitted inputs `curry.__call__`, `frequencies`, `concat` (Codex M01-M03) | `test_dicttoolz.py:249`; `streaming-analytics.rst:91`, `101` |
   | `keymap`, `itemmap` func (`dicttoolz.py:101`, `117`) | `identity` | `test_dicttoolz.py:248`, `250` |
   | `merge_with` func (`dicttoolz.py:69`) | `first` | `dicttoolz.py:52` (a docstring example, skipped by doctest but documented) |
   | `update_in` func (`dicttoolz.py:297`, `299`) | `assoc_in.<lambda1>` | `dicttoolz.py:242` |
   | `excepts` handler (`functoolz.py:870`) | `return_none` | the default |
   | `utils.raises` (`utils.py:3`) | `apply` | `test_functoolz.py:54` |

   Client only (no package value is passed): `apply`, `thread_first` and
   `thread_last` forms, `juxt`, `do`, `flip`, `excepts` func,
   `accumulate`, `merge_sorted`, `iterate`, `diff`, `reduceby` binop,
   `valfilter`, `keyfilter`, `itemfilter`, `fold`. A partial, `map` or
   other library object that the client builds around a package function
   is opaque (B5): `map(first, partitionby(identity, ...))`
   (`test_recipes.py:21`), `starmap(merge, join(...))`
   (`tips-and-tricks.rst:78`), `pmap(wordcount, ...)`
   (`parallelism.rst:72`). The alternative, every package function at
   every callable parameter, is the arbitrary package callable that B3
   excludes. This call decides about 120 inside edges, 88 of them at
   `curry.__call__` and `curry.call` (9 of these in the trace).

2. **Curries and Composes inside curries and Composes (B2).** The
   documented curries bind curries and Composes as arguments
   (`map(get([1, 2]))`, `groupby(get(3))`, `valmap(compose(sum,
   pluck(2)))`, `streaming-analytics.rst:38`, `87`, `101`), and the
   documented compositions hold curries and nested Composes (J1). So the
   public `__hash__`, `__eq__`, `__repr__` and `__name__` of curry and
   Compose reach those of the held objects: `curry.__hash__ ->
   curry.__hash__, Compose.__hash__` (`functoolz.py:292`), `curry.__eq__
   -> curry.__eq__, Compose.__eq__` (the `args` tuples, `298`),
   `Compose.__eq__` and `Compose.__hash__` to both (`550`, `558`),
   `Compose.__repr__ -> Compose.__repr__, curry.__repr__` (`!r` of the
   tuple, `545`), `composed_doc` and `Compose.__name__ -> Compose.__name__`
   (`524`, `539`). 12 inside edges. The keyword values that the tests and
   documents bind (key functions, factories, caches) are no such objects,
   so `frozenset(self.keywords.items())` (`293`) calls none.

3. **Registry lookups of a curry (B2, B5).** The introspection functions
   are public, and their `func` role holds curries (the tests pass curries
   of client functions and every toolz callable, `toolz.flip` and
   `toolz.memoize` included, `test_inspect_args.py:314-385`, `387-435`).
   `func in _sigs.signatures` hashes a curry (`curry.__hash__`; traced at
   `_check_sigspec`). A curry equal to a stored curry but not identical
   to it exists: `toolz.flip()` binds no argument and returns
   `curry(flip)`, whose func, args and keywords equal those of
   `toolz.flip`. The dict then compares it with the stored key by
   `curry.__eq__`. It reaches the lookups on PyPy (the PyPy
   `_check_sigspec` looks up every func, `functoolz.py:944`, then the
   registry function looks it up again, `_signatures.py:692` to `782`),
   and on CPython at `functoolz.py:927` when the caller passes a `sigspec`
   that is not a Signature (a public parameter; client control flow
   counts). 7 `curry.__eq__` edges and 6 `curry.__hash__` edges from
   reading. The alternative, no `__eq__` without an observed collision,
   ignores this deterministic equal key.

4. **The lambdas that `check_valid` calls (B2, B5; ruled by
   b8-ruling-toolz-1, referee, adopted by the lead, 2026-11-24).**
   `check_valid` (`_signatures.py:684`) calls the registry lambdas of the
   callable `func` that reaches `is_valid_args` and `_is_valid_args`: on
   PyPy every registry key does; on CPython a key without a signature
   (`ValueError`). `is_valid_args` is public and its docstring states
   "Many builtins in the standard library are also supported"
   (`functoolz.py:1109`), with `map` as its example; `curry._should_curry`
   passes every curried callable (`functoolz.py:330`). The registry itself
   is the package's own list of the callables that it supports in this
   role (its module docstring: "builtin functions in any Python version",
   and the toolz classes and curries it adds). The ledger reads the
   docstring and the registry as admitting every registered callable for
   `func`, and the client's choice of callable as a control-flow effect
   (B5) that selects a package lambda: every lambda that the registry holds on an admitted
   runtime is a callee, 193 inside edges (11 in the trace). Not callees:
   51 lambdas of names that no admitted runtime has (Python 2 builtins,
   `itertools.i*`, operator's Python 2 names, among them the seven dunders
   `__delslice__`, `__div__`, `__getslice__`, `__idiv__`, `__irepeat__`,
   `__repeat__` and `__setslice__` at `_signatures.py:348-433`, and
   `operator._compare_digest`) and 46 lambdas overwritten in the registry
   (45 surviving `operator.__x__` aliases, whose key is `operator.x`, and
   `builtins.abs`, whose key is `operator._abs`); both groups are
   `exclude` lines at the site. (The first commit miscounted these as 44
   and 53.) The narrower reading
   follows the aiocache clause of B2 (a client value that selects names
   the ones the package, its tests and documents pass): the keys that
   `toolz.curried` curries (`map`, `filter`, `sorted`, `reduce`,
   `partial`, `excepts` and the non-ignored operator functions), the ones
   the tests pass to `is_valid_args` (`map`, `dict`, `int`, `sorted`,
   `max`, `bytearray`, `operator.mul`) and the docstring's `map`: 61
   lambdas, 132 edges fewer. The referee's ruling (b8-ruling-toolz-1)
   retains all 193: an admitted public input may select a handler that
   the package installs in its own dispatch table, and the public
   contract supports standard-library builtins (`functoolz.py:1109`).
   The six package-object keys (`curry`, `flip`, `juxt`, `memoize`,
   `Compose`, `InstanceProperty`; `<lambda284>`, `286` to `290`) also
   qualify: `is_valid_args` and `is_partial_args` document complementary
   questions with identical support notes (`functoolz.py:1088-1138`), the
   paired tests reuse the same cases (`test_inspect_args.py:204-205`,
   `354-355`), and the module sweep passes the six keys to
   `is_partial_args` (`test_inspect_args.py:387-425`): one introspection
   role, by documentation, not by forwarding.

5. **Lazy objects with package callbacks (README "Limits of the site
   finder", B5).** A lazy object that package code consumes calls its
   callback at the consuming package function: `dict.update` in `valmap`,
   `keymap`, `itemmap` (`dicttoolz.py:85`, `101`, `117`); the iteration
   in `frequencies` of `countby`'s map (`itertoolz.py:547`, added by
   hand: `getter.<lambda1>`, `<lambda2>`); `tuple(starmap(pluck, ...))`
   in `unzip` (`core.py:133`); `list(results)` in `fold` with the
   default `map` (placed at the partial, `parallel.py:71`, `75`);
   `heapq.nlargest` in `topk` (`itertoolz.py:987`); the defaultdict
   factories `groupby.<lambda1>` and `merge_with.<lambda1>`, called at the
   subscription in the same function. A lazy object returned to the
   client (`remove`, `mapcat`, `pluck`, `partitionby`, `random_sample`,
   `rest`) calls nothing in the package.

6. **Descriptor loads through library code.** `inspect.signature` loads
   `__signature__` of a curry (instance or class) and of the class
   Compose, and `inspect.unwrap` loads `Compose.__wrapped__` and
   `__signature__` (before 3.14 also on the class); `hasattr` and
   `getattr` load the instanceproperties (`functoolz.py:206-208`, `929`);
   the type's `__doc__` getter calls the InstanceProperty of
   `excepts.__doc__` with no instance (`type(self).__doc__`, `902`, and
   `getattr(func, '__doc__')` in `curry.__init__` for the curried class
   `excepts`, `224`). Each is `InstanceProperty.__get__` at the package
   call that made the library code run (CPython `Lib/inspect.py`,
   `unwrap` and `_signature_from_callable`, 3.9 to 3.15;
   `Objects/typeobject.c`, `type_get_doc`). `type(self).__name__` and
   `getattr(cls, '__name__')` read the type's own name, not the property
   `Compose.__name__` or `excepts.__name__`. A getattr walk that meets a
   curry on a class calls `curry.__get__` (`362`, `384`; the tests pickle
   curried methods, `test_serialization.py:68-124`).

7. **`toolz.__getattr__`.** No package load misses an attribute of
   `toolz` (`toolz.pipe`, `toolz.merge`, the curried names; `tlz` reads
   `__package__`, `__file__`, `__doc__`, `__name__` and `__dict__` of
   modules). `curry.__reduce__` walks the qualname of the wrapped
   function, which a client can set (`test_serialization.py:187-192`);
   by B3 (the aiocache clause) a client name reaches an attribute hook
   only where the tests or documents use it, and the tested path through
   `toolz` (`toolz.functoolz...`) exists. So `toolz.__getattr__` has no
   caller; its body keeps its three edges.

8. **Concrete outside types (B4).** The docstrings of `merge`,
   `merge_with`, `valmap`, `keymap`, `itemmap`, `valfilter`, `keyfilter`,
   `itemfilter`, `assoc`, `dissoc` and `update_in` document dictionaries:
   the client's `d` is named `<builtin>.dict`; the tests' `os.environ` and
   their `Mapping` subclass are client objects (their trace edges are
   rejected). `factory()` is `<builtin>.dict` for the default and opaque
   for a client factory. `random_sample`'s `random_state` is the
   `random.Random` that the package makes or the documented
   `random.Random` (`itertoolz.py:1053`). `Signature.parameters` is a
   `types.MappingProxyType`.

9. **tlz and the import system.** `TlzLoader` is on `sys.meta_path`. The
   import system calls `find_spec` for any name that the earlier finders
   do not find: `import_module('cytoolz...')` (`_build_tlz.py:21`), a
   missing toolz submodule (`26`, `test_tlz.py:33`) and a new tlz
   submodule (`87`, which also calls `create_module` and `exec_module`).
   These are callbacks of the `import_module` calls. `find_module` and
   `load_module` are never called by the import system (the loader has
   `find_spec` and `exec_module`); their bodies keep their edges (rule A).

## Callees outside the package

Named by the micro-benchmark rules; the trace's canonical names differ
for these (the checker matches the aliases): `functools.reduce`
(`_functools.reduce`), `warnings.warn` (`_warnings.warn`),
`importlib.machinery.ModuleSpec` (`_frozen_importlib.ModuleSpec`),
`types.ModuleType` (`builtins.module`), `types.MethodType`
(`builtins.method`), `types.MappingProxyType.values` and `.items`
(`builtins.mappingproxy.*`), `operator.not_` (`_operator.not_`),
`random.Random.random` (`_random.Random.random`). The methods of a
`collections.defaultdict` are named by that class
(`collections.defaultdict.items`, `groupby` and `merge_with`). A call of
a functools.partial is `functools.partial.__call__`, of an itemgetter
`operator.itemgetter.__call__`. No missing module is called (cytoolz
calls nothing of the package; its import is `importlib.import_module`).

## Open path sets

None.

## Rejected trace edges

63, all client values (`toolz.rejected.json`): functions and lambdas
that the doctests define (the tracer names them by the module whose
doctest runs, `toolz.functoolz.double`, `toolz.div`, `<lambda>`);
builtins and library callables that the tests pass as callbacks (`sum`,
`str`, `len`, `operator.add`, a `functools.partial`, `log.append`,
`pool.map`, itemgetters); and the methods of the tests' `os.environ`
and `Mapping` subclass.

## Notes for the auditor

- The PyPy `_check_sigspec` and the 3.14 annotation code are not in the
  trace (CPython 3.14 ran `_get_annotate`; PyPy did not run).
- `partition_all`'s error message misspells `parition_all`
  (`itertoolz.py:737`); no edge.
- `_check_sigspec`'s registry branch (`functoolz.py:927-934`) is for
  cytoolz-like objects whose `__signature__` has `__get__`. With toolz the
  test at 927 runs for a non-Signature `sigspec` or a `TypeError` of
  `inspect.signature` (J3), but the call at 933 never does: no registry
  key's `__signature__` has `__get__` (audit F1).
- `curry.__signature__` reaches no package descriptor: the wrapped
  callable is never a curry, and `excepts` and `EqualityHashKey` define no
  `__signature__`.
- `test_fold` maps through a `multiprocessing.Pool`; the workers' calls
  are not traced, and the client map's calls of the package partial are
  client behaviour (J5).

## Statistics

`check.py toolz`: 845 edges (501 inside, 344 outside); the trace confirms
514 of 845 (60.8%); 181 of 462 functions run (39.2%; 290 of the 462 are
registry lambdas); 63 rejected trace edges.

`check.py --origin toolz`:

| Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
|---|---|---|---|---|
| 576 | 63 | 514 (174 / 340) | 331 (327 / 4) | 845 (501 / 344) |

Of the 327 inside edges from reading, 182 are registry lambdas (J4), 82
are callbacks of `curry.__call__` and `curry.call` (J1, Codex M15-M17).

## Audit (2026-11-24)

The blind audit (`toolz.audit.md`) re-derived 159 sites; 144 agree. Of
the 10 edge differences, 9 were the auditor's errors, withdrawn. The
lead's rulings after the auditor's opinion:

- **F1 (0 edges).** The call at `functoolz.py:933` cannot run (no
  registry key's `__signature__` has `__get__`); its six callees are
  removed. The edges stay through `924:34` and `945:31`.
- **F2 (+1 inside).** `join -> curry.__call__` at the four rightkey
  sites (`itertoolz.py:887`, `894`, `907`, `915`): join's docstring treats
  the key arguments as one role, and `bench/test_join.py:18` passes a
  curried `get(0)` (J1).
- **J4** went to the referee (Codex); its ruling b8-ruling-toolz-1,
  adopted by the lead, keeps all 193 lambdas (0 edges) and corrects the
  split of the 97 excluded lambdas to 51 unavailable and 46 overwritten.

Totals after F1 and F2: 828 edges (484 inside, 344 outside).

## Codex round 1

`selection/batch-8-proposal/codex-audits/round-1/toolz.md`: 17 missing
edges, 2 ruling questions, nothing false. Each finding was checked against
the source and the rules; all 17 hold and are applied (+17 inside edges,
828 to 845). They all follow the factory-output clarification (FO: a
documented factory output is admitted with its other public arguments,
and the one-argument `compose` returns an admitted input unchanged, the
funcy precedent).

| Id | Edge | Applied at | Why it holds |
|---|---|---|---|
| M01 to M03 | `valmap -> curry.__call__`, `frequencies`, `concat` | `dicttoolz.py:85:14` | `compose(x)` returns `x` (`functoolz.py:673`); `x` is an admitted compose input (J1) and valmap admits compose outputs (`streaming-analytics.rst:91`) |
| M04, M05 | `groupby -> curry.__hash__`, `curry.__eq__` | `itertoolz.py:100:10` (and the hash at `103:11`) | `toolz.curried.get()` is the documented key factory with other arguments; each `key(item)` underapplies `get` and returns a new curry (`functoolz.py:305-308`, `338`), equal but distinct |
| M06, M07 | `join -> curry.__hash__`, `curry.__eq__` | `itertoolz.py:888` to `924` (9 lookups) | the same keys in join's one key role (F2) |
| M08, M09 | `reduceby -> curry.__hash__`, `curry.__eq__` | `itertoolz.py:622` to `628` (5 sites) | the same key (`streaming-analytics.rst:155`) |
| M10, M11 | `unique -> curry.__hash__`, `curry.__eq__` | `itertoolz.py:265:20`, `266:25` | `curry(EqualityHashKey)` (the documented factory, `sandbox/core.py:13`, without a bound key) returns a curry per item |
| M12 | `frequencies -> curry.__call__` | `itertoolz.py:547:17` | `compose(frequencies, map(get(0)))`: the curried map's map object, iterated by frequencies (README.rst:67, `streaming-analytics.rst:38`) |
| M13, M14 | `frequencies -> curry.__hash__`, `curry.__eq__` | `itertoolz.py:548:10` (getitem and setitem) | the same map with `get()` yields equal curries |
| M15 to M17 | `curry.__call__ -> curry.__call__`, `getter.<lambda1>`, `getter.<lambda2>` | `functoolz.py:305:33` | `compose(sorted, map(get(0)))`, `compose(sorted, pluck([0]))`, `pluck([])`: the curried sorted's partial calls sorted, which consumes the package-made map in `curry.__call__` |

The two ruling questions went to the lead with the writer's opinion;
both lead rulings (2026-11-24) follow it, and no edge changes:

- **R01 (lead ruling: no edge).** `Compose.__call__ -> identity` through
  `compose(compose())`: B2 admits the Compose values that the tests pass
  to compose (`test_functoolz.py:702`); the zero-argument output
  `identity` is a different value, and FO needs documentation naming it
  for compose's input role, which none gives.
- **R02 (lead ruling: no edges).** `memoize.memof` and `memoize.key` to
  `__hash__` and `__eq__` of curry and Compose (6 candidate edges): by
  the pymysql ruling, admission extends along forwarding from an admitted
  parameter onward, not backwards from the wrapped callable's inputs to
  the wrapper's; nothing tests or documents a package value passed to a
  memoized function (`test_functoolz.py:100-106` admits a curry as the
  memoized function, not as its argument).

Totals after Codex round 1: 845 edges (501 inside, 344 outside).

