# asyncstdlib: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release v3.14.0, commit `0c5e206189e20466bae9468f13be7f3d49fa70a5`,
`requires-python = "~=3.8"`. Audited files (uncommitted, as of 2026-11-12):

| File | sha256 (first 12) | Content |
|---|---|---|
| `asyncstdlib.ledger` | `67ffe04240b3` | 572 entries, 8 default lines (17 candidates) |
| `asyncstdlib.json` | `2e54ecafb51c` | 661 edges: 477 in the package, 184 outside |
| `asyncstdlib.rejected.json` | `c0890f5afce8` | 5 trace edges |
| `asyncstdlib.md` | `c24a9bb324ed` | roles, judgements 1-10, rulings c1-c3, tool remarks |

The trace (Python 3.14.9, 398 tests passed, 4 skipped) has 418 edges and
confirms 413 of the 661 (62.5%); 248 come from reading only. `check.py
--benchmark-dir macro-benchmark-heldout asyncstdlib` reports no errors, and
`--report` shows 0 trace edges that no site accounts for.

I judged the files by scope rules A, B1-B5 and C of `macro-benchmark/README.md`
and by the lead's ruling c1 (an abstract annotation names a package class only
nominally; a class that merely has the methods enters a role only through the
documentation, or through code, tests or examples that pass it). I read the 11
modules, `docs/index.rst`, `docs/source/**`, the `.pyi` stubs and `unittests/`
as data. I did not run the package and used no static analysis tool.

**Result.** The ground truth is complete: I found no missing edge under the
rules. Its role sets are the ones I derived blind, with one exception (A1,
2 edges, a ruling is needed). One note is wrong (A2, no edge change). One
question about `__del__` is not decided by the README (R1). The writer's tool
remarks (a), (b) and (d) are correct (T1).

## Findings

| Id | Severity | Kind | Site or edge | Evidence | Edges | Decision |
|---|---|---|---|---|---|---|
| A1 | low (needs a ruling) | edge that cannot happen under B2 + c1 | `itertools.py` 395:56 `self._iterator.__anext__()` -> `TeePeer.__anext__`; 409:40 `self._iterator.aclose()` -> `TeePeer.aclose` | `TeePeer.__init__` annotates `iterator: AsyncIterator[T]` (`itertools.py:361`). `TeePeer` subclasses only `Generic` (`:358`), so by c1 the annotation does not name it. No document, stub, test or example mentions `TeePeer` or passes a peer to a peer's constructor (`docs/`, `README.rst`, `unittests/`, `itertools.pyi`: no match; the stub does not even declare `TeePeer`). The only package caller, `Tee.__init__`, unwraps a peer to its `_iterator` (`:464-471`), and `aiter()` of a package object returns the object itself, so the package never stores a peer in `_iterator`. The documentation that puts `TeePeer` in the iterable role is about the documented "(async) iter T" parameters: `tee` yields "(async iter T, ...)" (`docs/source/api/itertools.rst:81-82`) and its docstring passes peers to `a.anext` and `a.map` (`itertools.py:430-433`). `asyncstdlib.md` "Roles 1" itself defines the role as "every parameter documented as an (async) iterable" (`asyncstdlib.md:71`), then lists the undocumented `iterator` of `TeePeer`; judgement 7 keeps the edges only because `TeePeer` is public by path. Nearest rules: B2 (the annotation decides which package values fit) and B3 (a value that the package never produces for that role). | -2 (661 to 659; 477 to 475 in the package) | proposed: reject `TeePeer.__anext__` at 395:56 and `TeePeer.aclose` at 409:40 with this reason, and rewrite judgement 7 and the 395:56 note. If the lead rules that the iterable role covers every parameter annotated with an async iterator type, also undocumented public ones, the edges stay. |
| A2 | low | wrong note (no graph change) | `_lrucache.py` 441:37 `self.__cache.popitem(last=False)`, note "no `__hash__` or `__eq__` of a CallKey runs" | `OrderedDict.popitem` finds the oldest node and pops it by a keyed lookup with the stored hash (`Objects/odictobject.c`: `OrderedDict_popitem_impl` -> `_odict_popkey_hash` -> `_odict_find_node_hash`, and `_PyDict_Pop_KnownHash`). The dict lookup compares by identity first, but calls `__eq__` on every stored key with the same hash that it meets earlier in the probe sequence. Example: keys A then B with equal hash (judgement 8: `hash((-1, 0)) == hash((-2, 0))`); a hit on A moves it to the end (449:37); `popitem(last=False)` then pops B and meets A's slot first, so `A.__eq__(B)` runs `CallKey.__eq__`. The edge `CachedLRUAsyncCallable.__call__ -> CallKey.__eq__` is already in the graph from 430:34, 436:20, 442:29, 446:29 and 449:37. | 0 | proposed: add `-> CallKey.__eq__` at 441:37 (a callee beyond the candidates) or change the note to say that only a hash collision makes popitem compare keys |
| R1 | info (README does not decide) | special method run on a reference drop | `TeePeer.__del__` (`itertools.py:411`); `zip_longest` (`itertools.py:554-566`) | The micro-benchmark gives `__del__` to the scope that drops the last reference (`micro-benchmark/snippets/classes/del_on_last_reference`). Package code can do that for a peer: `a.zip_longest(*a.tee(x), ys)` leaves the peers referenced only by `async_iters` after `del iterables` (`:554`); when a peer is exhausted, `async_iters[index] = fill_iter` (`:566`) and the next rebinding of the loop variable `aiterator` (`:559`) drop it, and `TeePeer.__del__` runs in `zip_longest`. Other drops happen when a package async generator's frame is cleared, at a point that the code does not name. No site kind models a reference drop, and the README says nothing about `__del__`. The ledger lists `TeePeer.__del__` as reached only by the interpreter. | 0 (or +1: `zip_longest -> TeePeer.__del__`) | proposed ruling: a `__del__` that runs because a package scope drops the last reference is out of scope for the macro-benchmark (no site names the call; the frame that runs it depends on the reference count and on generator teardown). No change to the ledger. |
| T1 | info (tools and README) | confirmation of the writer's remarks | `asyncstdlib.md`, "Tools" (a), (b), (d) | (a) `class _ScopedAsyncIterator(_BorrowedAsyncIterator[T, S])` (`asynctools.py:83`): the README promises the `__init__` "of its package bases", but `sites.py` does not resolve a subscripted base, so 110:51 gets no `__init__` candidate. `nullcontext = NullContext` (`contextlib.py:245`) is a module-level alias, which the README's name rule does not cover (only `from m import g as f`). (b) The README's `op` row lists for `in` only `__contains__` and the iteration methods; a dict membership test also hashes the key, so 381:20 and 436:20 need `CallKey.__hash__` beyond the candidates. (d) Calling an instance whose `__call__` is a coroutine function starts no frame, so the trace cannot see `LRUAsyncBoundCallable.__call__ -> *.__call__` (156:25). | 0 | proposed: fix `sites.py` for subscripted package bases; in the README, list `__hash__` of the key for `in` and say that module-level aliases are not followed |

## Step 1: blind re-derivation

**Method.** I made a scratch benchmark directory with a copy of
`projects.toml` and a `projects` symbolic link, and the skeleton with
`check.py --benchmark-dir <scratch> --skeleton asyncstdlib` (1466 sites, 55
value sites). I took the site lines in skeleton order,
`random.Random(20261111).sample(sites, 70)`, and added the 51 value sites
that the sample did not contain: 121 sites. Before I opened any file of the
writer, I wrote the role sets with their evidence and my callees for each
site (`$TMPDIR/heldout-audit-asyncstdlib/blind.md`, with `sample.py`,
`sample.txt`). Of the 121 sites, 86 have a ledger entry and 35 are decided by
the default rejections alone.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random sample (24 call, 2 decorator, 3 class, 1 async-with, 4 iter, 3 async-iter, 5 await, 4 op, 13 getitem, 10 getattr, 1 format; 4 of them value sites) | 70 | 69 | 1 |
| Other value sites | 51 | 50 | 1 |
| **Total** | **121** | **119** | **2 (1.7%)** |

The 2 disagreements:

- **I was wrong (1):** `asynctools.py` 154:42 `_BorrowedAsyncIterator[T, Any](iterator)`.
  I wrote only `typing._GenericAlias.__call__`. On Python 3.9 and later the
  first `__class_getitem__` in the MRO is that of
  `collections.abc.AsyncIterable` (it precedes `Generic`), so the subscript
  is a `types.GenericAlias`; the writer has both `__call__` (judgement 3).
  An outside callee only.
- **Needs a ruling (1):** `itertools.py` 395:56: the writer keeps
  `TeePeer.__anext__`, I rejected it (A1).
- **The writer missed an edge (0). Naming only (0).** Every outside name in
  the sample matched, including `types.AsyncGeneratorType.__anext__`,
  `collections.abc.AsyncIterator.__aiter__`, `itertools.count.__next__` and
  `<builtin>.dict.__init__` for the `TypedDict` call.

## Step 2: role sets, compared role by role

I derived the role sets blind; the writer's sets are in `asyncstdlib.md`,
"Roles". The difference column counts the edges that each difference moves.

| Role | Members (blind) | Writer | Difference |
|---|---|---|---|
| Iterable, "(async) iter T" (`AnyIterable`, `AsyncIterator`) | nominal: `_BorrowedAsyncIterator`, `_ScopedAsyncIterator`, `chain`, `_Grouper`, `GroupBy`; by docs and tests: `TeePeer`; plus the package's own async generators (outside callees). Not `Tee`. | same | `TeePeer` as the `iterator` of `TeePeer` itself: -2 (A1) |
| Awaitable (`apply`, `await_each`, `any_iter`) | none; `AwaitableValue` and `_FutureCachedPropertyValue` are `Generic` only, and the docs pass them only to `asyncio.gather` (`functools.py:250`) | same | 0 |
| `ACloseable` (`closing`) | the iterable role, through the docstring example `a.closing(a.iter(something))` (`contextlib.py:188`) | same | 0 |
| Async context manager | nominal: `NullContext`, `_AsyncGeneratorContextManager`, `_ScopedAsyncIteratorContext`; `NoLock` as the default lock. `enter_context`: the three; `push`: `_AsyncGeneratorContextManager` (test `test_contextlib.py:327-329`); `Tee`/`TeePeer` lock: the three and `NoLock`; `cached_property` lock type: only `NullContext` can be built without arguments | same | 0 |
| Callables | defaults `itertools.add`, `itertools.identity`, `heapq._identity`, `bool`; `ExitStack.enter_context` at `map` (test `test_contextlib.py:273`); wrappers `Awaitify`, `force_async.async_wrapped`, the `partial` of `ExitStack.callback` | same | 0 |
| Package Protocols (`SupportsLT`, `SupportsAdd`, `SupportsBool`, `LRUAsyncCallable`) | none; the three cache classes for `lru` | same | 0 |

I checked every site that applies a role (the 38 `async-iter` sites, the 9
role `aclose()` calls, the 4 role `__anext__()` calls, `aiter()` at 55:33,
the 3 lock and enter sites, `ExitStack.__aexit__` 452:34, the 19 calls of
an awaitified callable, and the 3 calls inside `Awaitify` and
`force_async`). Each has the full set of its role and nothing more (no
package callee where the operand is the package's own async generator),
except A1.

For the lead, the cost of the other readings: a structural reading of the
iterable role would add `Tee` (about 5 edges: `_aiter_sync`, `any_iter`,
`await_each` and the callback of `sorted` to `Tee.__iter__`; `dict` to
`Tee.__len__`); a structural awaitable role would add the two `__await__` to
`apply`, `await_each` and `any_iter` (6 edges). The doc sentence "a tee of a
tee shares its buffer" (`itertools.py:436-437`) means a tee of a peer: the
code tests `isinstance(iterable, TeePeer)` (`:464`), and the tests pass peers
(`test_itertools.py:379, 394`); it is not evidence for a `Tee` argument.

## Step 3: the default rejections

I listed every site of each default with `check.py --report asyncstdlib
--default <candidate>` and read all explicit sites and all implicit sites
that are not annotation subscripts. All defaults are correct.

| Candidate | Sites | Check |
|---|---|---|
| `Tee.__getitem__` | 440 | 347 are `getitem` sites: 332 subscript `typing` objects or package generic classes, 15 subscript tuples, lists, the cache dicts, an instance `__dict__`, `sys.exc_info()` and a str method result. The other 93 iterate, unpack or map `*args`, tuples, lists and dicts, or pass them to builtins (`Tee` has `__iter__`, so iteration never falls back to `__getitem__`). No `Tee` reaches package code. |
| `Tee.__iter__`, `Tee.__len__` | 79, 67 | The iterated or tested client iterables (`_core.py:62`, `asynctools.py:226, 424`, `builtins.py:406, 451`) are not in the role for a `Tee` (Step 2). The truth sites test bools, ints, tuples, lists, sets and client values. |
| `CallKey.__eq__`, `CallKey.__hash__` | 361, 351 | Accepted at the 10 cache sites. `hash(values)` (`_lrucache.py:277`) hashes a tuple of client arguments; `self.values == other.values` (`:284`) compares those tuples. Only gap: 441:37 (A2, no edge change). |
| `_KeyIter.__eq__` | 368 | Accepted at `heapq.py:132, 139, 141`; tuple comparison calls `__eq__` first. No other comparison has a `_KeyIter`. |
| `LRUAsyncBoundCallable.__getattr__` | 291 | Package code loads only `_lru`, `__self__` (slots) and `__wrapped__` (property) on a bound callable. The `hasattr`/`getattr` calls (`asynctools.py:52, 56, 74, 76, 149, 191`; `contextlib.py:332, 334`; `functools.py:106`) get iterators, client objects or the client's instance. No bound callable reaches a callable role, so `inspect.iscoroutinefunction` and `functools.update_wrapper` never probe one. |
| `AwaitableValue.__await__`, `_FutureCachedPropertyValue.__await__` | 81, 81 | Accepted at `functools.py:121`. Every other `await` gets a coroutine, the awaitable of a package async generator, the result of a role `__anext__`/`aclose`, or a client awaitable. |
| Protocol methods (4) | 52, 1, 14, 9 | The Protocols are not instantiated; no package class subclasses them. |
| `CachedProperty.__get__`, `__set_name__`, `LRUAsyncCallable.__get__`, `LRUAsyncBoundCallable.__get__` | 32, 36, 32, 32 | No package class body holds one of these descriptors. Accepted only at `functools.py:106` (`getattr` calls `CachedProperty.__get__` back after the cached value was deleted, test `test_functools.py:106-110`). |

## Step 4: the 248 edges from reading only

| Class | Edges | Check |
|---|---|---|
| Iterable role `__aiter__`/`__anext__` | 158 | possible by B2 + c1 (Step 2); 1 of them is A1 (`_extend_buffer -> TeePeer.__anext__`) |
| Iterable role `aclose` | 54 | possible; 1 of them is A1 (`TeePeer.aclose -> TeePeer.aclose`) |
| Context manager role | 9 | possible (Step 2) |
| Other | 27 | possible: the seven `__repr__` and their `id`/`type`/`getattr` (rule A), `Awaitify.__call__` from the heapq keys and `_aexit_callback` (a sync key or callback), the three `LRUAsyncBoundCallable.__call__` edges (T1, d), `_GenericAlias.__call__` on 3.8, `dict.values` with `typed=True` and keywords, the `TypeError`/`ValueError` of misuse branches, `AwaitableValue.__await__` at `functools.py:121`, `GroupBy.aclose -> _GroupByState.aclose`, `_GroupByState.aclose`/`Closing.__aexit__ -> types.AsyncGeneratorType.aclose` |

## Step 5: other checks

- **Rejected trace edges (5).** All stay rejected. `Awaitify.__call__ ->
  contextlib._GeneratorContextManager.__exit__`: the test pushes a context
  manager of the standard library (`test_contextlib.py:331-333`), a client
  callback (B2). The four `builtins.async_generator.*` edges of
  `_AsyncGeneratorContextManager`: `self.gen` is what the client's function
  returns (`contextlib.py:113`), opaque by B5 and ruling c2.
- **Outside callees (184 edges, 66 names).** Every name is the canonical
  trace name or one of its aliases (`types.AsyncGeneratorType.*` =
  `builtins.async_generator.*`, `types.CoroutineType.__await__` =
  `builtins.coroutine.__await__`, `heapq.*` = `_heapq.*`), except three that
  the tests do not reach and that are correct by the micro-benchmark rules
  (`<builtin>.dict.values`, `<builtin>.id`, `typing._GenericAlias.__call__`).
  B4/B5: every method edge on a builtin type has a package receiver (the
  `**kwargs` dicts, the cache dict and `OrderedDict`, the `deque` of
  `ExitStack`, the `set` of the tee peers, the package's async generators)
  or an annotated concrete type (`qual_name: str`).
- **Functions that no site calls (85).** Each is public API, a special
  method that only client syntax or the interpreter reaches, or a Protocol
  method. Each keeps the out-edges of its body (rule A); I found none
  dropped. `TeePeer.__del__`: see R1.
- **Special methods and properties.** Checked the 7 `__repr__`, the
  `__aiter__`/`__anext__`/`aclose` of the six iterator classes, the 8
  `__aenter__`/`__aexit__` pairs, the 6 `__call__`, the 3 `__get__`,
  `__set_name__`, `__getattr__`, `__hash__`/`__eq__`/`__lt__` of `CallKey`,
  `_KeyIter`, `ReverseLT`, the `Tee` container methods, the 2 `__await__`,
  `__del__`, and the 6 properties (`__wrapped__` x2, `__func__`, `__doc__`,
  `__annotations__`, `_instance_value`). The slot `__wrapped__` of the cache
  classes shadows the Protocol property (`_lrucache.py:324, 353, 406`), as
  the ledger says.
- **Notes and rejections.** I read all 572 entries. All reasons hold, except
  A1 (395:56, 409:40, judgement 7) and A2 (441:37).
- **Judgements of `asyncstdlib.md`.** 1 (roles): agreed, except A1. 2
  (`TYPE_CHECKING`, annotations): agreed. 3 (version-dependent alias):
  agreed; I had missed it. 4 (`ContextDecorator` abstract by `abc`, c3):
  agreed. 5 (`CacheInfo` no edge; `CacheParameters` ->
  `<builtin>.dict.__init__`, as in micro-benchmark
  `operators/missing_dict_subclass`): agreed. 6 (`lru` is a cache object):
  agreed; the class docstring "A LRUAsyncCallable that is bound like a
  method" (`_lrucache.py:132`) describes what the class is, and by c1 that is
  not a role example; nothing passes a bound callable as `lru`. 7: A1. 8:
  agreed; also applies at 441:37 (A2). 9, 10: agreed.

## Judgement

The ground truth is complete and, with one exception, precise. My blind
role sets and the writer's are the same; every role site carries the full
set. The defaults are correct at all their sites. The only edge question is
A1: two edges that need a peer as the iterator of another peer, which no
document, test or package call provides (proposed: remove, 661 to 659). A2
fixes a note, R1 asks for a ruling that changes nothing under the proposal,
and T1 confirms three tool and README gaps that the writer found.


## Fourth source audit (2026-11-16)

A fresh auditor read all eleven runtime modules and support-role evidence,
then froze 1,586 sites and 212 bodies before comparing this baseline.
All 668 pairs, 572 ledger entries, 17 default candidates, 1,014 omitted
sites and five rejected trace pairs were reviewed. No graph change:
212 nodes and 668 edges (484 internal, 184 outside).

The independent model initially overextended structural iterable/context
roles and understated the cached-descriptor restart and nested-bound-cache
roles. Source-based adjudication corrected those proposals; they are not
baseline defects. Current judgement metadata now states the exact
>=3.8,<4 Python bound, CPython/PyPy support, and the normal/-O/-OO union.
A PyPy source check adds CallKey.__hash__ at _lrucache.py:441:37, where
OrderedDict.popitem(last=False) recomputes the stored key hash. This pair
already exists elsewhere in the same caller, so the graph is unchanged.
Assertions and docstring changes add no graph target. Historical text above
is preserved. No target or dependency code was executed.


### Round4 descriptor-fallback supplement (2026-11-16)

A cross-project consistency review adds seven missing package pairs at five
existing sites. The public LRUAsyncBoundCallable constructor admits an opaque
client LRUAsyncCallable implementation whose metadata property raises
AttributeError. Successful construction stores only slots. The first repr
can enter __getattr__ after __wrapped__ fails. Nested public bound wrappers
make __wrapped__, __doc__ and __annotations__ call __getattr__; automatic
fallback in the same first lookup then makes __getattr__ enter each of those
three package getters. All package fields remain unchanged, and no failed
lookup has escaped to a client before these entries. This is normal Python
fallback, not client reuse after a failed operation. Client properties remain
opaque. The initialized __func__, _lru and __self__ accesses add no fallback.

The initial round4 acceptance and source freeze are retained unchanged; this
explicit supplement supersedes its zero-missing-edge result. The final graph
has212 nodes and675 pairs (491 package,184 outside), with413 trace/alias pairs
and262 reading-only pairs. Default/statistics wording changes follow these
seven edge corrections and are not separate metadata defects. Evidence is in
/tmp/pycg-macro-audit-pass4/getattr-consistency-review and
/tmp/pycg-macro-audit-pass4/supplements/asyncstdlib-getattr.
