# asyncstdlib: judgements of the ground truth

Global-rule audit (2026-11-15): 0 removed edges, 9 added
edges; 668 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Release v3.14.0 (commit `0c5e206`). Analysed source: `asyncstdlib/` (11
modules, 201 functions with 2 lambdas, 36 classes). The `*.pyi` stubs next to
the modules are not analysed source; the ledger uses them only as type
evidence (judgement 6). `pyproject.toml` sets `requires-python = "~=3.8"`, so
the supported Python versions are >=3.8,<4.0. CPython and PyPy are in
scope: the pinned release actively tests both in
`.github/workflows/unittests.yml:15-16`, and `_lrucache.py:1-6,286`
explicitly accounts for PyPy. The final classifier is not an upper bound.

The ledger is `asyncstdlib.ledger`; the graph `asyncstdlib.json` is generated
from it. `asyncstdlib.rejected.json` has the 5 trace edges that are not
package edges.

## Architecture, as the ledger uses it

- Almost every public function is an async generator function. It takes an
  (async) iterable, makes a `ScopedIter` (`_core.py:66`) or calls `aiter()`
  (`_core.py:41`), and iterates the result with `async for`.
  `aiter(subject)` returns `subject.__aiter__()` for an async iterable, else
  the async generator of `_aiter_sync(subject)`.
- The package has its own async iterator classes: `TeePeer`, `chain`,
  `GroupBy` and `_Grouper` (`itertools.py`), and `_BorrowedAsyncIterator`
  and its subclass `_ScopedAsyncIterator` (`asynctools.py`). `chain`,
  `GroupBy` and `_Grouper` subclass `typing.AsyncIterator` and inherit
  `collections.abc.AsyncIterator.__aiter__`. The borrowed iterators keep
  `__anext__` in a slot: it holds the `__anext__` of an async generator
  expression (`asynctools.py:46, 51`), so `async for` over a borrowed
  iterator runs no package `__anext__`.
- `_core.awaitify` (`_core.py:101`) returns a coroutine function unchanged
  and wraps any other callable in an `Awaitify` (`_core.py:111`). All
  callable parameters (function, key, predicate) pass through it, so the
  call sites of these parameters call `Awaitify.__call__` or the client's
  coroutine function.
- The context managers: `ScopedIter` (internal), `NoLock` (the default lock
  of `tee`), `NullContext`, `Closing`, `ExitStack`, `Tee`,
  `_ScopedAsyncIteratorContext` (made by `scoped_iter`) and
  `_AsyncGeneratorContextManager` (made by `contextmanager`).
- The LRU caches (`_lrucache.py`): `lru_cache` makes an
  `UncachedLRUAsyncCallable`, `MemoizedLRUAsyncCallable` or
  `CachedLRUAsyncCallable`. Their `__get__` (inherited from the Protocol
  `LRUAsyncCallable`) makes an `LRUAsyncBoundCallable`. Keys are `CallKey`
  objects, or a single int or str argument (`_lrucache.py:316`).
- Name shadowing. `builtins.py` defines `iter`, `zip`, `map`, `list`,
  `tuple`, `dict`, `set`, `sorted`, `enumerate` and others, so inside that
  module these names are the async versions; it reaches the real builtins
  as `_sync_builtins.enumerate` and `_sync_builtins.sorted`. In
  `itertools.py`, `aiter` is `asyncstdlib.builtins.iter`, `zip` is the async
  `zip`, but `enumerate`, `tuple` and `set` are the builtins. `heapq.py`
  takes `aiter`, `awaitify`, `ScopedIter` and `borrow` from `_core`.

## Roles

A major judgement of this ledger is which package objects can reach a parameter. The current graph has 262 edges that the trace does not have. The
annotations are abstract types: `AnyIterable` (a union of `Iterable` and
`AsyncIterable`), `AsyncIterator`, `Awaitable`, `AsyncContextManager`,
`Callable`, and the package Protocols of `_typing.py`. The ledger applies
scope rule B2 as the lead ruled (ruling c1, below):

- An abstract annotation names a package class for a role only when the
  class subclasses it or is registered with it. Structural fit alone (a
  class that only has `__iter__`, `__await__` or `aclose`) names nothing.
- A class that does not subclass the annotation enters the role only when
  the documentation names it for the role, or the package's own code, tests
  or documented examples pass it there.

Each table gives, per member, the evidence that puts it in the role. Paths
without a directory are in `asyncstdlib/`; tests are in `unittests/`.

### 1. Iterable role

Parameters: every parameter documented as an "(async) iterable", for
example `subject` of `aiter` (`_core.py:41`, `AnyIterable`), `iterable` of
`ScopedIter` (`_core.py:76`), `iterator` of `anext` (`builtins.py:29`,
`AsyncIterator`) and of `borrow` (`asynctools.py:130`). It is one role for
the whole API:
`docs/source/notes/iter_scope.rst:17-18` ("All async iterators of
asyncstdlib that work on other iterators assume sole ownership of the
iterators passed to them") and `:45` ("every asyncstdlib async iterator
performs such cleanup").

| Member | Evidence |
|---|---|
| async generators of the package's async generator functions and expressions | `types.AsyncGeneratorType` is registered with `collections.abc.AsyncGenerator` (`_collections_abc.py`, `AsyncGenerator.register(async_generator)`). Package code passes them: `itertools.py:279` (`aenumerate(_borrow(async_iter))`), `itertools.py:552` (`aiter(_repeat(...))`), `builtins.py:235` (`ScopedIter(zip(...))`), `heapq.py:127-128` (`a_enumerate(_KeyIter[Any].from_iters(...))`), `heapq.py:183` (`a_zip(range(n), borrow(iterator))`). Tests: `test_itertools.py:113` (`a.enumerate(a.cycle(...))`), `test_builtins.py:290` (`a.dict(a.zip(...))`) |
| `chain` | subclasses `AsyncIterator` (`itertools.py:146`); tests `test_itertools.py:131` (`a.list(a.chain(...))`), `:183` (`a.anext(chain)`) |
| `GroupBy` | subclasses `AsyncIterator` (`itertools.py:663`); test `test_itertools.py:521` (`a.iter(gby)`) |
| `_Grouper` | subclasses `AsyncIterator` (`itertools.py:629`); test `test_itertools.py:525` (`a.list(g)`) |
| `_BorrowedAsyncIterator` | subclasses `AsyncGenerator` (`asynctools.py:26`); tests `test_asynctools.py:55` (`a.scoped_iter(b1)`), `:77` (`a.anext(borrowed_aiterable)`) |
| `_ScopedAsyncIterator` | subclasses `_BorrowedAsyncIterator` (`asynctools.py:83`); example `iter_scope.rst:73` (`a.islice(async_iter, 3)`); tests `test_itertools.py:308` (`a.islice(a1, 5)`), `test_asynctools.py:20, 32` (`a.iter(a1)`, `a.scoped_iter(a1)`) |
| `TeePeer` | no base but `Generic` (`itertools.py:358`); the docstring example of `tee` passes peers to `a.anext` and `a.map` (`itertools.py:432-433`); tests `test_itertools.py:379` (`a.tee(tee_peer)`), `:394` (`a.tee(tee_state, n=3)`) |

The `iterator` of `TeePeer.__init__` (`itertools.py:361`) is not a
documented parameter of this role. Its values are what the package passes,
`Tee.__init__` (`itertools.py:464-471`), and that excludes a `TeePeer`
(lead ruling A1, below).

Not members: `Tee` (`itertools.py:416`, `Generic` only). It has `__iter__`,
`__len__` and `__getitem__` (`itertools.py:482-497`), and its docstring
offers indexing, iteration and unpacking to the client, but no package
code, test or example passes a `Tee` to a package function. This decides the
defaults on `Tee.__iter__`, `Tee.__len__` and `Tee.__getitem__` (for example
`_core.py:62`, `builtins.py:451`, `asynctools.py:424`).

Consequence: every `async for` over `aiter()` of such a parameter gets six
package callees (`TeePeer.__aiter__`, `_BorrowedAsyncIterator.__aiter__`,
and the `__anext__` of `TeePeer`, `chain`, `GroupBy` and `_Grouper`), and
an explicit `aclose()` gets the six package `aclose` methods and
`types.AsyncGeneratorType.aclose`.

### 2. Awaitable role

Parameters: `args` and `kwargs` of `apply` (`asynctools.py:290`,
`Awaitable[Any]`), `awaitables` of `await_each` (`asynctools.py:199`), the
`Awaitable` arms of `any_iter` (`asynctools.py:378-383`).

No package member. `AwaitableValue` (`functools.py:51`) and
`_FutureCachedPropertyValue` (`functools.py:68`) have `__await__` but
subclass only `Generic`; the documentation passes them only to
`asyncio.gather` (`functools.py:250`), and no test passes them to a
package function. Package coroutines are awaitables, but their `__await__`
is outside the package.

### 3. Async context manager role

| Member | Evidence |
|---|---|
| `NullContext` | subclasses `AsyncContextManager` (`contextlib.py:210`); test `test_contextlib.py:264` (`exit_stack.enter_context(a.nullcontext(value))`); the default lock type of `CachedProperty` (`functools.py:139`) |
| `_AsyncGeneratorContextManager` | subclasses `ContextDecorator` (`contextlib.py:109`), which subclasses `AsyncContextManager` (`contextlib.py:64`); test `test_contextlib.py:327-329` (`exit_stack.push(suppress())`) |
| `_ScopedAsyncIteratorContext` | subclasses `AsyncContextManager` (`asynctools.py:93`) |
| `NoLock` (lock parameters only) | no base (`itertools.py:340`); the package passes it as the default lock (`itertools.py:476`) |

Not members: `Closing` (`contextlib.py:172`, `Generic` only), `ExitStack`
(`contextlib.py:251`), `Tee` (`itertools.py:416`) and `ScopedIter`
(`_core.py:66`, an internal helper). They have `__aenter__` and `__aexit__`,
but they do not subclass `AsyncContextManager`, and nothing passes them.

The parameters, and the members that reach each:
- `lock` of `Tee` (`itertools.py:460`) and of `TeePeer` (`itertools.py:363`),
  entered at `itertools.py:383`: `NoLock`, `NullContext`,
  `_AsyncGeneratorContextManager`, `_ScopedAsyncIteratorContext`.
- `cm` of `ExitStack.enter_context` (`contextlib.py:361`, `AnyContextManager`),
  entered at `contextlib.py:398`; its `__aexit__` is called at
  `contextlib.py:452`: `NullContext`, `_AsyncGeneratorContextManager`,
  `_ScopedAsyncIteratorContext`.
- `exit` of `ExitStack.push` (`contextlib.py:299`, `SE`): the runtime source leaves `SE` unbound, but the shipped `contextlib.pyi` binds it to async/sync context managers and callables. The async context-manager arm admits `NullContext`, `_AsyncGeneratorContextManager` and `_ScopedAsyncIteratorContext`; the test also pushes an `_AsyncGeneratorContextManager` (`test_contextlib.py:327-329`). Their exits run at `contextlib.py:452`, whose target set already includes all three.
- the lock type of `cached_property` (`functools.py:190`,
  `Type[AsyncContextManager[Any]]`; default `nullcontext`, `functools.py:139`),
  instantiated without arguments at `functools.py:183`: of the three
  classes only `NullContext` can be made so. Its instance is entered at
  `functools.py:111`.

### 4. Package Protocols

| Protocol | Members | Evidence |
|---|---|---|
| `ACloseable` (`_typing.py:88`; bound of `AClose`, the type of `thing` of `closing`, `contextlib.py:196`) | the members of the iterable role | no class subclasses it; the docstring of `closing` passes `a.iter(something)` (`contextlib.py:188`), an async iterator of the iterable role. `Tee` and `ExitStack` have `aclose` but nothing passes them; `_GroupByState` is private and never reaches a client |
| `SupportsLT`, `SupportsAdd`, `SupportsBool` (`_typing.py:69, 78, 60`; bounds of `LT` and `ADD`) | none | no class subclasses them, and no package value is passed as a key, item or summand; so `ReverseLT.__lt__` (`heapq.py:164`), `_KeyIter.__lt__` (`heapq.py:95`), `_min_max` (`builtins.py:315, 322`) and `itertools.add` compare and add client values only |
| `LRUAsyncCallable` (`_lrucache.py:68`; the type of `lru` of `LRUAsyncBoundCallable`, `_lrucache.py:136`) | `UncachedLRUAsyncCallable`, `MemoizedLRUAsyncCallable`, `CachedLRUAsyncCallable`, `LRUAsyncBoundCallable` | the first three subclass it (`_lrucache.py:321,350,403`); the bound callable is a documented implementation (`_lrucache.py:132`), admitted by B2 (judgement 6) |

### 5. Callable roles

| Parameter | Package members | Evidence |
|---|---|---|
| `function` of `accumulate` (`itertools.py:76-78`) | `itertools.add` | the default |
| `key` of `groupby` (`itertools.py:689-698`) | `itertools.identity` | used when `key` is `None` (`itertools.py:694`) |
| `key` of `nlargest` and `nsmallest` (`heapq.py:207, 229`) | `heapq._identity` | used when `key` is `None` (`heapq.py:221, 237`) |
| `predicate` of `filterfalse` (`itertools.py:246`) | `bool` (outside the package) | used when `predicate` is `None` (`itertools.py:255-256`) |
| `function` of `map` (`builtins.py:206`) | the bound `ExitStack.enter_context` | test `test_contextlib.py:273` (`a.map(exit_stack.enter_context, contexts)`) |
| every other callable parameter | none | a bare `Callable` or the TypeVar `AC` names no package value (B2), and no code, test or example passes one |

### Other readings

A structural reading (annotations admit every package class that fits the
protocol) would add `Tee.__iter__` and `Tee.__len__` at the sync
iterations, the two `__await__` at `apply`, `await_each` and `any_iter`,
`Closing`, `ExitStack` and `Tee` in the context manager role, `Tee.aclose`
and `ExitStack.aclose` at `Closing.__aexit__`, and `ReverseLT.__lt__` at the
comparisons. A narrow reading (only what the tests and examples pass to
each parameter) would remove most of the six-callee sets: the trace
confirms them only where a test passes that kind of iterator to that
function. The lead kept the reading above (ruling c1).

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. Examples: the five `__repr__` of `asynctools.py` and `functools.py`
keep their edges (`<builtin>.id`, `<builtin>.type`, the `__repr__` of the
wrapped iterator), and no test runs them.

**B1. Receivers.** Public methods admit constructible classes and concrete
subclasses that inherit them. Private methods use actual package inputs;
an uncalled private body uses the public-parameter fallback. Failed argument
binding enters no function. An initializer that raises keeps calls reached
in its body, but failed construction supplies no completed receiver. Clients
do not reinitialize instances or reuse arbitrary half-changed objects.

- `self._lru` of `LRUAsyncBoundCallable` (`_lrucache.py:156-183`) is a
  cache object or another bound callable (judgement 6). The four
  `LRUAsyncCallable.cache_*` and its `__wrapped__` property never run: the
  three subclasses override the methods, their `__wrapped__` is a slot
  (`_lrucache.py:324, 353, 406`), and the Protocol is not instantiated.
- `self` in `ContextDecorator.__call__` is an
  `_AsyncGeneratorContextManager`: `ContextDecorator` is abstract by `abc`
  (judgement 4, ruling c3).
- Plain public classes are receivers of their own methods (ruling c3):
  `type(self)()` in `ExitStack.pop_all` (`contextlib.py:295`) and
  `cls(...)` in `chain.from_iterable` (`itertools.py:191`) make an
  `ExitStack` and a `chain`; client subclasses are client code.
- `self.__wrapped__` of `Awaitify`, of the borrowed iterators and of the
  caches is a slot, so the `__wrapped__` properties are rejected at those
  loads.

**B2.** See "Roles". Broad `Any`, `object`, `type` and `Callable` annotations
do not admit arbitrary package objects. Client assignment to a public
attribute requires a documentation or test witness for that role.

**B3.** Not considered: a package object as an argument of a cached
function (`CallKey`, `_lrucache.py:277`), as the direct value of
`AwaitableValue(value: R)` or the result of a client's `cached_property`
getter (`functools.py:56-57, 65, 125`), as the bad argument of
`ExitStack.push` (`contextlib.py:339`), or as an item of a client iterable
(the comparisons of `_min_max` and `heapq`).

**B4.** Concrete types: `qual_name` (`str`, `_utility.py:28`),
`self._tee_peers` (`set[int]`, `itertools.py:371, 407, 412`), the
`**kwargs` dicts of the caches (`_lrucache.py:309, 314`, a package value by
B5), the `dict` and `OrderedDict` caches, the `deque` of `ExitStack`. Shipped
stubs count as annotation evidence, and annotations take precedence over
conflicting documentation. Abstract types alone do not fix a concrete
outside class; `Any` supplies no concrete type. The six adjacent `.pyi`
files were checked, including `contextlib.pyi` for `ExitStack.push` and
`_lrucache.pyi` for bound-cache roles.

**B5. Client objects are opaque.** `self.gen` of an
`_AsyncGeneratorContextManager` is the async generator of the client's
function (`contextlib.py:113`): its `__anext__`, `aclose` and `athrow`
(`contextlib.py:122, 129, 140, 142`) have no callee, and the four trace
edges are rejected. The `__exit__` of a context manager that a test made
with the standard `contextlib.contextmanager` is a client callback
(`Awaitify.__call__`, rejected).

**C. Public paths.** The public names are the `__all__` of
`asyncstdlib/__init__.py` and of the public modules. Rule C also makes
public some classes that no document mentions: `TeePeer`, `NoLock`
(`asyncstdlib.itertools`), `ReverseLT` (`asyncstdlib.heapq`),
`AwaitableValue`, `CachedProperty`, `LRUAsyncBoundCallable`
(`asyncstdlib.functools`), `acallable_iterator` (`asyncstdlib.builtins`),
`itertools.add` and `itertools.identity`. The `_core` helpers are also on
public paths (`asyncstdlib.builtins.aiter`, `.ScopedIter`, `.Sentinel`,
`asyncstdlib.contextlib.awaitify`, `asyncstdlib.heapq.borrow`), but the
docstring of `_core.py` marks them internal ("not bound to maintaining a
public interface"), so the ledger treats them as private. This changes no
edge: their parameters get the same roles from the package's own calls.

## Judgement calls

1. **Roles** (see above; ruling c1). The ledger header states them; the
   notes of the sites refer to the header.
2. **`if TYPE_CHECKING:`** (`itertools.py:21-22`) only imports `TypeAlias`
   for an annotation. It has no call. Annotations are evaluated on 3.8 to
   3.13 (not in `heapq.py` and `_lrucache.py`, which have `from __future__
   import annotations`); they only subscript `typing` objects, and the
   defaults decide those sites. No version branch and no optional import.
   The round-four working scope also includes normal, `-O` and `-OO`
   execution (an unanswered optional preference, not user approval). The
   assertions at `builtins.py:85` and `_lrucache.py:256` can disappear.
   A callable nonnegative int subclass can reach `lru_decorator` under `-O`,
   but its wrapper constructor targets already have ordinary int/None
   witnesses. Accepting a nondefault Sentinel at `builtins.py:85` also
   adds no named target. Copies of `__doc__` at `functools.py:143` and
   `contextlib.py:115`, and the explicit property at `_lrucache.py:177-179`,
   add no target under `-OO`. Keep the normal-mode assertion-call edges.
3. **Version-dependent callee** (`asynctools.py:154`,
   `_BorrowedAsyncIterator[T, Any](iterator)`). The first
   `__class_getitem__` in the MRO is that of `collections.abc.AsyncGenerator`
   on 3.9 and later (a `types.GenericAlias`), and that of `Generic` on 3.8
   (a `typing._GenericAlias`). Both `__call__` are callees; the trace (3.14)
   has the first.
4. **`ContextDecorator._recreate_cm`** (`contextlib.py:94`) is rejected at
   `contextlib.py:103:41`, by the lead's ruling c3 (below). B1 decides on
   the class itself: `ContextDecorator` (`contextlib.py:64`) subclasses
   `typing.AsyncContextManager`, which is
   `contextlib.AbstractAsyncContextManager`, an `abc.ABC` with an abstract
   `__aexit__`. `ContextDecorator` does not define `__aexit__`, so it is
   abstract by `abc` (`ContextDecorator()` raises `TypeError`; checked on
   the standard library, also true on 3.8). It is not a receiver; client
   subclasses are client code (the tenacity precedent), and its only package
   subclass, `_AsyncGeneratorContextManager`, overrides `_recreate_cm`. No
   test runs `ContextDecorator._recreate_cm`. Edge change: none (661 edges
   before and after).
5. **Instantiation of `CacheInfo` and `CacheParameters`.** `CacheInfo` is a
   `NamedTuple`: no edge, as in cachetools.md judgement 6
   (`_lrucache.py:341, 392, 457`). `CacheParameters` is a `TypedDict`, a
   subclass of `dict` at run time: `<builtin>.dict.__init__`
   (`_lrucache.py:338, 389, 454`; the trace confirms it).
6. **The `lru` of `LRUAsyncBoundCallable`** (`_lrucache.py:136`) admits
   another bound callable. Its docstring identifies it as an
   `LRUAsyncCallable`; this documented implementation satisfies B2.
   The inner and outer generic parameters need not be the same: an inner
   callable can still accept the leading argument the outer one binds.
   For an async function with three positional arguments, bind the first
   through an inner wrapper and the second through an outer wrapper.
   This supports nine recursive edges in `__call__`, the four cache
   methods, `__getattr__`, and the three metadata properties at lines 142-183.
   No target execution was needed to establish this argument flow.
7. **`TeePeer` is public by path** (lead ruling A1, B2/B3). Being public by
   path makes the class a receiver of its own methods; it does not put a
   peer in a role. The `iterator` of `TeePeer.__init__` is annotated
   `AsyncIterator` (`itertools.py:361`), which `TeePeer` does not subclass
   (ruling c1); no documentation, test, example or stub passes a peer there;
   the package's own caller, `Tee.__init__`, unwraps a peer before it builds
   one (`itertools.py:464-471`); and a peer that a client passes by hand is
   an arbitrary object where any iterator is accepted (B3). So
   `TeePeer.__anext__` is rejected at `itertools.py:395:56` and
   `TeePeer.aclose` at `itertools.py:409:40` (2 edges removed, 661 to 659).
8. **Hash collisions of `CallKey`.** Two different argument tuples can have
   the same hash (`hash((-1, 0)) == hash((-2, 0))`), so storing and testing
   a key can call `CallKey.__eq__` (`_lrucache.py:381, 382, 436, 442,
   446`). A cache hit compares two equal `CallKey` objects. The same holds
   for `OrderedDict.popitem` (`_lrucache.py:441`, audit finding A2): on CPython it pops
   by a keyed lookup with the stored hash, which meets a colliding key first
   when `move_to_end` (line 449) moved it behind the oldest one. No graph
   change: the edge already comes from the other sites.

   Admitted PyPy 3.11 v7.3.20 differs: its `OrderedDict.popitem(last=False)`
   selects the first key and calls `self.pop(k)` (`app_odict.py:64-77`).
   The object-key dictionary strategy uses `r_dict(space.eq_w, space.hash_w)`;
   its `pop` constructs `_r_dictkey`, which calls the key hash. Therefore
   `CallKey.__hash__` also belongs at this site. That caller/callee pair
   already exists elsewhere, so the graph remains unchanged. Primary
   sources, read as text, are pinned at PyPy tag `release-pypy3.11-v7.3.20`:
   `_collections/moduledef.py` SHA-256
   `a11570a33ed3241a3b985d0b3b9efd8a669d59045de69c822215756f87d917dd`,
   `_collections/app_odict.py` SHA-256
   `5103bdcd1295423783ac26e4b1e4417060ba1ac9444cea5610464536960a9b52`,
   `objspace/std/dictmultiobject.py` SHA-256
   `f440e43f9007d0fc9d691ebf00c0b0b6d0d59fc3bf7faf2e30a691b066cce209`,
   and `rpython/rlib/objectmodel.py` SHA-256
   `925d3fea22a61605cfaea8d8c23b2434a0e85bbb8f6faa324f988600d221f333`.
   Paths except `rpython/` are under PyPy's `pypy/` directory. Exact
   URLs and inert copies are retained in the round-four evidence.
9. **`getattr(self._instance, self._name)`** (`functools.py:106`) runs when
   the cached value was deleted: `getattr` finds the `CachedProperty` on the
   client's class and calls `CachedProperty.__get__` back.
10. **`NoLock()`** (`itertools.py:476`): `NoLock` defines no `__init__`;
    no edge.

## Rulings of the lead

The lead ruled on these questions of this ledger. Each is applied in the
ledger and in the sections above.

- **c1 (lead): nominal, not structural.** Under B2 an abstract annotation
  (`AsyncIterator`, `Awaitable`, a Protocol) names a package class for a
  role only when the class subclasses it or is registered with it. A class
  that only has the right methods enters a role through the other routes of
  B2: the documentation names it for the role, or the package's own code,
  tests or documented examples pass it there. Applied in "Roles".
- **c2 (lead): an object that a client callback returns is a client object**
  (B5): opaque, no outside callee, and what it calls is client behaviour.
  Applied to `self.gen` of `_AsyncGeneratorContextManager`
  (`contextlib.py:113, 122, 129, 140, 142`) and to the four rejected trace
  edges.
- **c3 (lead): receivers of a base class documented for subclassing.**
  Decide by B1 on the class itself, not on client subclasses. A plain
  public class (not abstract by `abc`, not a Protocol) is a receiver of its
  own methods (the jmespath `Visitor` ruling). A class that is abstract by
  `abc` or a Protocol is not a receiver; client subclasses are client code
  (the tenacity precedent). Applied to every package base class:
  - `ContextDecorator` (`contextlib.py:64`), the only class whose docstring
    documents client subclassing (`contextlib.py:66-90`): abstract by `abc`,
    so no edge to `ContextDecorator._recreate_cm` (judgement 4).
  - `LRUAsyncCallable` (`_lrucache.py:68`): a Protocol, not a receiver; its
    three subclasses override every method but `__get__`.
  - `_BorrowedAsyncIterator` (`asynctools.py:26`): private, the base of
    `_ScopedAsyncIterator`; the package makes both, no change.
  - The plain public classes whose methods dispatch on `self` or `cls`
    (`ExitStack`, `chain`, `Tee`) are receivers of their own methods; the
    ledger already had these edges.

  Edge change of c3: none (661 edges before and after).
- **A1 (lead, B2/B3): a `TeePeer` is not the iterator of another `TeePeer`.**
  The annotation `AsyncIterator` of `TeePeer.__init__` does not name
  `TeePeer` (c1), nothing documents or passes a peer there, `Tee.__init__`
  unwraps peers, and a hand-built peer of a peer is an arbitrary object
  (B3). Being public by path makes a class a receiver, not a member of a
  role. Applied at `itertools.py:395:56` and `409:40` (judgement 7):
  661 to 659 edges.
- **R1 (lead): `__del__` on a reference drop is not an edge.** A `__del__`
  that runs because a function drops the last reference to an object is not
  an edge in the macro-benchmark: no site kind models it, and the first five
  ground truths have none. So `TeePeer.__del__` (`itertools.py:411`) has no
  package caller, also where `zip_longest` drops a peer
  (`itertools.py:554-566`). 0 edges.

## Tools

Remarks on `check.py` and `sites.py` and on the trace, found while writing
this ledger:

- **(a) Missing `__init__` candidates.** The skeleton proposes no
  `__init__` for three class calls: `_ScopedAsyncIterator(self._iterator)`
  (`asynctools.py:110`; the class inherits `__init__` through the subscripted
  base `_BorrowedAsyncIterator[T, S]`), `nullcontext(iterator)`
  (`asynctools.py:192`; `nullcontext` is a module-level alias of
  `NullContext`, `contextlib.py:245`) and `_BorrowedAsyncIterator[T, Any](iterator)`
  (`asynctools.py:154`, a value site). The ledger adds the callees beyond
  the candidates. The first is fixed: `sites.py` now reads a subscripted
  base, so `_BorrowedAsyncIterator.__init__` is a candidate at
  `asynctools.py:110`.
- **(b) `__hash__` at `in` sites.** At `key in self.__cache`
  (`_lrucache.py:381, 436`) the key's `__hash__` is not a candidate, although
  a dict membership test hashes the key. The README's `op` row listed only
  `__contains__` and the iteration methods for `in`. The ledger added
  `CallKey.__hash__` beyond the candidates. Fixed: an `in` site now proposes
  the element's `__hash__`, as a `getitem` site does for a key, and the
  README says so. The third `in` site that gets the candidate,
  `type(key[0]) in fast_types` (`_lrucache.py:316`), tests a type; the
  default rejection of `CallKey.__hash__` decides it.
- **(d) A coroutine called through an instance.** The trace has no edge
  `LRUAsyncBoundCallable.__call__ -> *LRUAsyncCallable.__call__`, although
  the method runs: the callee `self._lru(...)` (`_lrucache.py:156`) is an
  instance whose `__call__` is a coroutine function, and the coroutine
  starts later in client code. The three edges are from reading only.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `Tee.__getitem__` | 440 | no package code subscripts, iterates or searches a `Tee` | nowhere |
| `Tee.__iter__`, `Tee.__len__` | 79, 67 | a `Tee` is not in the iterable role (Roles, 1) | nowhere |
| `CallKey.__eq__`, `CallKey.__hash__` | 361, 352 | only the cache dicts hash and compare a `CallKey` | `_lrucache.py:375, 381, 382, 400, 430, 436, 441, 442, 446, 449, 465` |
| `_KeyIter.__eq__` | 368 | only the heapq calls of `merge` compare two `_KeyIter` | `heapq.py:132, 139, 141` |
| `LRUAsyncBoundCallable.__getattr__` | 293 | initialized slots/methods do not fail; missing names and metadata descriptor AttributeError can reach fallback | `_lrucache.py:142, 171, 175, 179, 183` |
| `AwaitableValue.__await__`, `_FutureCachedPropertyValue.__await__` | 81, 81 | only `_await_impl` awaits a cached value | `functools.py:121` |
| `SupportsBool.__bool__`, `SupportsLT.__lt__`, `SupportsAdd.__add__`, `ACloseable.aclose` | 52, 1, 14, 9 | Protocol methods that never run | nowhere |
| `CachedProperty.__get__`, `CachedProperty.__set_name__`, `LRUAsyncCallable.__get__`, `LRUAsyncBoundCallable.__get__` | 11, 33, 11, 11 | no package class binds these descriptors | `functools.py:106` (`CachedProperty.__get__`, a callback of `getattr`) |

The 1,014 sites without ledger entries comprise 891 candidate-bearing
sites decided by defaults and 123 implicit sites without package candidates.
The per-candidate counts above can overlap and include listed sites where
a default decides a candidate that the entry does not address.

Some defaults decide explicit sites (`check.py --report asyncstdlib`
lists them): the builtins `tuple`, `len`, `set`, `enumerate`, `reversed`,
`bool`, `hash`, `getattr` and `hasattr` on lists, tuples, dicts,
generators, client objects or async iterators, and the `aclose()` calls
(for `ACloseable.aclose`). None of the sites decided by these defaults receives a `Tee`, a
`CallKey` or a `_KeyIter`; the nested-bound-callable `getattr` is decided
explicitly.

## Value sites (55)

Every value site has a note. The groups:

| Sites | Callees |
|---|---|
| calls of an awaitified callable (`map`, `filter`, `_min_max`, `sorted`, `reduce`, `accumulate`, `dropwhile`, `filterfalse`, `starmap`, `takewhile`, `acallable_iterator`, heapq keys, `_GroupByState.step`) | `Awaitify.__call__`, plus the defaults (`add`, `identity`, `_identity`) and `ExitStack.enter_context` at `map` |
| `iterator.__anext__()` on the iterable role (`anext`, `_KeyIter.from_iters`, `pull_head`, `TeePeer._extend_buffer`) | the four package `__anext__` and `types.AsyncGeneratorType.__anext__` (in `_extend_buffer` not `TeePeer.__anext__`, ruling A1) |
| `aclose()` in `zip` | the iterable-role `aclose` set |
| `Awaitify.__call__`, `force_async.async_wrapped` | `<builtin>.bool` (filterfalse), `force_async.async_wrapped` |
| `self._lru(...)` | the three cache `__call__` and `LRUAsyncBoundCallable.__call__` |
| `ExitStack.__aexit__` `callback(...)` | the three context manager `__aexit__`, `Awaitify.__call__`, `functools.partial.__call__`, `_aexit_callback` |
| `cls(...)`, `type(self)(...)` | `CallKey.__init__`, `_KeyIter.__init__`, `chain.__init__`, `_AsyncGeneratorContextManager.__init__`, `ExitStack.__init__` |
| `ordered(...)` and `key(...)` in `_largest` | `ReverseLT.__init__`, `_largest.<lambda1>`; `Awaitify.__call__`, `_identity` |
| client callbacks (`apply`, `sync`, the cached function, the `cached_property` getter, the `contextmanager` function, the decorated function of `inner`, `self.gen`) | none |

## Functions that no site calls

85 functions have no package caller. Most are the public API (the
functions of `__all__`, the methods of `Closing`, `ExitStack`, `Tee`,
`LRUAsyncBoundCallable`), and special methods that only client syntax or
the interpreter reaches (`Tee.__getitem__`, `TeePeer.__del__` (ruling R1),
`CachedProperty.__set_name__`). Never run in the tests (23): the four
`_typing` Protocol methods, the five `LRUAsyncCallable` methods and
property, `ContextDecorator._recreate_cm`, the seven `__repr__`,
`LRUAsyncBoundCallable.__get__`, `__func__` and `__annotations__`,
`GroupBy.aclose`, `_GroupByState.aclose` and `_Grouper.aclose`.

## Statistics

| | Count |
|---|---|
| All AST sites | 1,586: the 1,463 sites below plus 123 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 1463 (399 call, 44 decorator, 33 class, 24 async-with, 65 iter, 38 async-iter, 13 mapping, 81 await, 42 op, 347 getitem, 7 setitem, 293 getattr, 49 truth, 28 format) |
| Sites with candidates / value sites | 1247 / 55 |
| Ledger entries | 572 (399 call, 44 decorator, 38 async-iter, 24 async-with, 28 format, 17 op, 16 getattr, 3 setitem, 2 getitem, 1 await) |
| Callee lines / rejection lines (`reject *`) / exclusions / notes | 819 / 150 (105) / 0 (0 nodes) / 158 |
| Default rejections | 8 lines, 17 candidates |
| Nodes | 212 (11 modules, 201 functions) |
| Edges | 675: 491 in the package, 184 to 66 callees outside |
| Edges that the trace confirms | 413 of 675 (61.2%) |
| Edges only from reading | 262 (248 in the package, 14 outside) |
| Trace edges rejected | 5 |
| Functions that the tests run | 178 of 201 |

The trace misses three edges of a method that runs (see "Tools", d). It
also misses the nine nested-bound-callable edges of judgement 6.


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
