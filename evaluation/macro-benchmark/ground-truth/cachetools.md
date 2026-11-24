# cachetools: judgements of the ground truth

Global-rule audit (2026-11-15): 8 removed edges, 0 added
edges; 615 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Release v8.0.0, commit `1ce79efa552d1bdda70d144d401ef9105d999184`, analysed
source `src/cachetools/` (7 modules; the `.pyi` stubs are not analysed).
`requires-python = ">= 3.11"`, with no upper bound. The release
explicitly supports PyPy: `.github/workflows/ci.yml` tests `pypy3.11`
alongside CPython 3.11–3.15 and free-threaded builds. Python 3.10 was
dropped in v8.0.0 (`CHANGELOG.rst:4`); the final classifier is not an
upper bound. The ledger is `cachetools.ledger`; the graph
`cachetools.json` is generated from it. The ground truth comes from reading
the source. The dynamic trace served only as a checklist.

## Architecture in short

- `Cache(collections.abc.MutableMapping)` keeps the items in a dict
  (`self.__data`). `FIFOCache`, `LFUCache`, `LRUCache` and `RRCache` derive
  from `Cache`. `TTLCache` and `TLRUCache` derive from `_TimedCache(Cache)`.
  `func._UnboundTTLCache` derives from `TTLCache`.
- Most operations go through `self[key]`, `key in self`, `del self[key]`,
  `self.popitem()` and `self.expire()`. A site in a base class dispatches
  over every subclass that can be the receiver.
- The subclasses call the base special methods through default parameters
  (`cache_setitem=Cache.__setitem__`) or local variables
  (`cache_getitem = Cache.__getitem__`).
- `cached` and `cachedmethod` select one of six wrapper classes. Each wrapper
  class combines a base (`_cached._WrapperBase` or
  `_cachedmethod._WrapperBase`) with one of six mixins of `_decorator.py`.
  The mixins hold `__call__`, `cache_clear` and `cache_info`.
  `cachedmethod` returns a `_MethodDescriptor`. Its `__get__` calls one of
  eight lambdas that make the per-instance wrapper.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules for all
projects. Each rule is summarised here, followed by how this ledger applies it.

**A. Edges are per function.** The edges of a function are the calls that
its body can make when it runs. Whether and how the function itself gets
called does not matter: every function, public or private, tested or not,
keeps the out-edges of its body. The global rule permits rejecting trace
edges for client-supplied values, implicit outside calls, excluded
private-API inputs and incorrect callee names. These categories do not
remove the body edges of an uncalled function.

- `_TimedCache.expire` has no caller, but keeps the edges of its body. It has
  none: `raise NotImplementedError` without parentheses is not a call.
- `_Timer.__getattr__` has no package caller, and keeps its edge to
  `<builtin>.getattr`.
- The 17 rejected trace edges cross client argument or callback-result boundaries (see
  "Trace edges rejected as client callbacks").

**B. Edges are limited by the values that can reach a call site.**

Public functions receive the values that clients or the package can pass.
Private functions with package callers use the receivers and arguments of
those calls. A private function with no package caller uses the public
parameter rules, so rule A still gives its body edges. The wrapper and
cache helper constructors therefore use their actual package inputs.
`Any`, `object`, `type` and a bare `Callable` do not name arbitrary package
values. Client assignments to public attributes count only where the
package documentation or tests make those assignments.

*B1. Receivers.* `self` in a method of class `C` is an instance of `C`, of a
package subclass that inherits the method, or of a subclass that calls the
method explicitly on itself, limited to the instances that the package or a
client can create. Clients create instances of public classes; a private
class is instantiated only where the package does it. An object that the
client passes explicitly as `self` to an unbound method of a public class
(`Cls.method(obj, ...)`) is a client object and opaque (B5), unless it is a
package instance that fits B1.

- No `_TimedCache` instance exists: the timed caches are `TTLCache`,
  `TLRUCache` and `func._UnboundTTLCache` (created only by `func.ttl_cache`,
  `func.py:98`). So `self.expire(time)` in `_TimedCache` (`__init__.py:422,
  427, 433`) rejects `_TimedCache.expire`, and the six `self.cache.clear()`
  sites of the mixins reject `_TimedCache.clear` (judgement 3).
- `_Timer` is created only by `_TimedCache.__init__` (`__init__.py:418`) and
  through `_Timer.__reduce__`. `TTLCache._Link` and `TLRUCache._Item` are
  created only by their caches.
- A receiver also counts when a subclass calls the base method explicitly on
  itself: `Cache.__setitem__(self, ...)` through the defaults
  `cache_setitem=Cache.__setitem__` (`__init__.py:182, 237, 310, 355, 513,
  656`), `Cache.get(self, ...)`, `Cache.pop(self, ...)` and
  `Cache.setdefault(self, ...)` in `_TimedCache` (`__init__.py:443, 447,
  451`), and `super().currsize` (`__init__.py:434`). This is why
  `self.popitem()` in `Cache.__setitem__` lists the `popitem` overrides of
  the subclasses, and why `key in self`, `self[key]`, `del self[key]` and
  `self[key] = value` in `Cache.get`, `pop` and `setdefault` list the
  `TTLCache` and `TLRUCache` methods.
- The dispatch table below lists, at each site, the package classes whose
  instances can be the receiver. No site lists a method that only a client
  object passed as `self` (`Cache.get(obj, key)`) could reach.
- `Cls.method(None, ...)` (`_descriptor.py:142`): the receiver `None` that
  the client passes to the `_Unbound` of a `cachedmethod` is a client object
  and opaque. The package calls no method on it: `_MethodDescriptor.__get__`
  tests only its identity (`obj is None`, `_descriptor.py:40`) and returns
  the package's own `_Unbound` (`_descriptor.py:42`), and the site then calls
  that package object. So the edge `_Unbound.__call__ -> _Unbound.__call__`
  stays: it depends on no behaviour of the client object.

*B2. Arguments and stored values* are client objects, the values that the
package defines for the role of the parameter, and the package's defaults. A
package value is in scope when the annotation names its type or a base class
that the package implements for that purpose, or when the package's own
code, tests or documented examples pass it there. A stub that types a
parameter as a bare callable is not evidence. The package's defaults
are also in scope. A value from outside the package that the client passes
is a client callback, also when the documentation shows it as an example.

| Parameter (stub annotation) | Package values in scope | Client values (callbacks, no outside callee) |
|---|---|---|
| `cache` of `cached` (`MutableMapping`) | every public cache class; the dict `{}` that `func.py` passes (`func.py:42, 56, 70, 84`, only to `_ConditionInfoWrapper`); `func.py`'s own caches, also `_UnboundTTLCache` | a dict or mapping of the client |
| `cache` of `cachedmethod` (`Callable[[Any], MutableMapping]`) | no package callable is admitted for this role; the client callback and its result remain opaque (B5). Package cache dispatch in the shared mixins is independently supported through cached's documented cache role. | the callable itself |
| `key` (`Callable[..., _KT]`) | the four key functions of `keys.py`; defaults `keys.hashkey` (`cached`), `keys.methodkey` (`cachedmethod`), `keys.typedkey`/`hashkey` (`func.py:27`) | a client key function |
| `lock` (`AbstractContextManager`), `condition` (`_AbstractCondition`) | the `threading.Condition()` of `func.py:28`, passed as lock and condition of a `_ConditionInfoWrapper` | client locks and conditions |
| `timer` (`Callable[[], _TT]`) | the default `time.monotonic` | a client timer (`datetime.now` in the docs and tests) |
| `choice` (`Callable[[Sequence], _KT]`) | the default `random.choice` | a client function (`min`, `max` in the tests) |
| `getsizeof`, `ttu` | none (judgement 5) | the client's function (`len` in the tests) |
| decorated function of `cached` and `func.py` (`Callable[_P, _R]`) | stacked wrappers of `cached` and `func.py` (`_cached.py:30-31`, `CHANGELOG.rst:98`, `tests/test_cached.py:352`, `tests/test_func.py:135`) | a client function |
| method of `cachedmethod` (`Callable[Concatenate[Any, _P], _R]`) | none: the package binds it itself (`types.MethodType(method, obj)`, `_cachedmethod.py:70-100`) | a client function |

*B3. Not considered:* an arbitrary package object passed where any object or
any callable is accepted, and a value that the package never produces for
that role. At a value site, an `exclude` line records such a package
function that I considered:

- A product of `cachedmethod` (`obj.method`, `Cls.method`, the
  `_MethodDescriptor`) as the decorated function of `cached` or
  `cachedmethod`, or a `cached` wrapper as the method of `cachedmethod`. The
  parameter is typed with the abstract `Callable`, which names no package
  type for the role, and no documentation, test or package code passes such
  an object there. So the six `self.__func(...)` sites (`_decorator.py:26,
  51, 86, 119, 152, 197`) have no edge to `_Unbound.__call__` or
  `_MethodDescriptor.__call__`; the format sites `{wrapped!r}` at
  `_cachedmethod.py:48` and `_descriptor.py:127` have no package callee; and
  `{self.__wrapped__!r}` at `_cached.py:46` has only
  `_cached._WrapperBase.__repr__`.
- Another cache's public `.timer` (a `_Timer`) as `timer`. The parameter is a
  bare `Callable[[], _TT]`; the docs offer `time.monotonic` and
  `datetime.now` (`docs/index.rst:143-161, 196-208`); no test or package
  code passes `cache.timer`; `_Timer.__reduce__` passes on the raw timer
  (`__init__.py:411`). The docstring of the property ("The timer function
  used by the cache", `__init__.py:438`) describes what it returns, not what
  the parameter takes. So `self.__timer()` (`__init__.py:395, 401`) has no
  edge to `_Timer.__call__`, and `getattr(self.__timer, name)` (414) has no
  edge to `_Timer.__getattr__`.
- Caches as keys or values: `repr(self.__data)` at `__init__.py:49` has no
  package callee, although a client could store a cache in another cache.
- A `_Timer` as a lock: the `with lock:` sites have no package callee.

*B4. A method call on a parameter whose annotation or documentation fixes a
concrete outside type* is an edge to the method of that type. An abstract
type (`MutableMapping`, `Callable`, a context manager, no annotation) does
not fix the class of a client object. The shipped `.pyi` files count as
annotations. They type `cached`'s cache as `MutableMapping` and its
condition as `_AbstractCondition`; these abstract annotations take
precedence over the concrete examples in the documentation. Therefore
those examples do not add client `dict`, `WeakValueDictionary` or
`Condition` method callees. This differs from an abstract `isinstance`
check without such an annotation, where global B4 allows documentation
to fix a concrete type. No parameter has a concrete outside annotation
on which the package calls a method, so B4 adds no edge here.
The instance `__dict__` of a client object is an attribute of that
object, so it is as opaque as the object (B5), and the documentation asks
only for "a mutable mapping" (`docs/index.rst:588-592`): the calls
`obj.__dict__.setdefault(...)` at `_descriptor.py:56, 63` have no outside
callee. A `**kwargs` mapping is a package value: the interpreter builds it
for the call of the package function itself, so its class is `dict`, and
`kwargs.items()` (`keys.py`) and `kwargs.pop` (`_descriptor.py:158`) keep
their `<builtin>.dict.*` edges.

*B5. Client objects are opaque.* A method call on a client-supplied object,
or on one of its attributes, has no outside callee unless global B4
fixes a concrete type. The abstract annotations above leave these client
objects opaque; examples and tests do not override those annotations.
What an opaque client object calls when the package uses it is client
behaviour. A value that the package builds
itself, or that the interpreter builds for the call of the package function
(`**kwargs`, `*args`), keeps its builtin method edges. I checked every edge
to a method of a builtin or library type:

- Client values give no edge. A client dict as `cache`: `cache.setdefault`
  (`_decorator.py:57, 158`) and `self.cache.clear()` (`_decorator.py:34, 63,
  100, 127, 164`) have no `<builtin>.dict.*` callee. A client lock or
  condition: `cond.wait()` and `cond.notify_all()` of `_ConditionMixin`
  (`_decorator.py:80, 96`) have no callee. The trace edges that these calls
  make are in `cachetools.rejected.json`.
- Package-built values keep their edges. In `_ConditionInfoMixin`, the one
  mixin that `func.py`'s `{}` and `Condition()` reach: `<builtin>.dict.clear`
  at `_decorator.py:211`, `threading.Condition.wait` at 188 (only from
  reading: two threads with the same key) and `threading.Condition.notify_all`
  at 207. Also the dicts, `OrderedDict`s, lists and sets that the caches and
  mixins create and the `functools.partial` of `_cachedmethod.py:37`. The
  dict argument at `_descriptor.py:63` does not fix the type of the
  opaque client method result assigned to `wrappers`.
- Values that the interpreter or the library builds for the package keep
  their edges: the `**kwargs` dicts (`kwargs.items()` in `keys.py`,
  `kwargs.pop` at `_descriptor.py:158`) and
  `inspect.signature(self).parameters` (`types.MappingProxyType.values`).
- An attribute of a client object is opaque: `obj.__dict__.setdefault(...)`
  at `_descriptor.py:56, 63` has no callee. Its return is also opaque (B5).
  Thus `wrappers.get` and `wrappers.setdefault` at lines 66 and69 have no
  concrete callee. Every successful non-None path returns an opaque value,
  so the outer call at line 142 has no mixin callee. The None path returns
  the package `_Unbound`, preserving its recursive `__call__` edge.

The global-rule audit removes eight edges: two dict methods and six mixin
calls. Four were traced and now have explicit rejection reasons.

**C. "Public" is judged on the access path.** A class or function is public
if a client can reach it through a path with no component that starts with
an underscore (dunder names excepted). It is private if its docstring or
documentation marks it private (`:meta private:`). No cachetools docstring or
document marks a name private this way.

- `_TimedCache` and `_Timer` have private class names. The inherited methods
  `_TimedCache.get`, `pop`, `setdefault`, `__len__`, `__repr__`, `currsize`,
  `timer` are public as `TTLCache.get` and so on.
- `CacheInfo._make_info`, `func._cache`, `func._UnboundTTLCache`, the
  modules `_cached`, `_cachedmethod`, `_decorator`, `_descriptor` and
  `keys._HashedTuple` are private implementation names. Their constructors
  and helper calls use the package flows described above. This does not
  mean clients never call objects returned by the public API: clients can
  use the wrappers' `cache_clear` and `cache_info` methods and a cache's
  public `.timer` object. Those receivers are the constructed outputs, not
  arbitrary instances of private implementation classes.

**How the rules changed this ground truth: 655 -> 640 -> 623 -> 615 edges.** The
first version had 655 edges. B1 removed 9 (`_TimedCache.__repr__`,
`__len__`, `currsize` -> `_TimedCache.expire`; the six `cache_clear` ->
`_TimedCache.clear`). B3 removed 6 (the six `self.__func(...)` ->
`_MethodDescriptor.__call__`). That gave 640. The second audit applied B2 as
worded above and removed 17 more, for 623: 14 edges that used a product of
`cachedmethod` as a decorated function (the six `self.__func(...)` ->
`_Unbound.__call__`, and 8 `__repr__` edges at `_cached.py:46`,
`_cachedmethod.py:48` and `_descriptor.py:127`), and 3 edges that used
another cache's `.timer` as `timer` (`_Timer.__call__ -> _Timer.__call__`,
`_Timer.__enter__ -> _Timer.__call__`, `_Timer.__getattr__ ->
_Timer.__getattr__`). Stacked `cached` and `func.py` wrappers stay, with all
36 mixin-to-mixin `__call__` edges and `_cached._WrapperBase.__repr__ ->
_cached._WrapperBase.__repr__`. None of the 32 removed edges is in the trace.
The tooling pass after the audits added 7 `%` formatting sites (judgement 13)
and the `exclude` lines; neither changed an edge. The global-rule audit
of 2026-11-15 removes eight more under B5, giving 615 edges.

## Judgements

1. **`_MethodDescriptor.__get__ -> __call__` (`_descriptor.py:32-36`).**
   The branch runs when `__get__` reads, with a class as `obj`, a descriptor
   that never got `__set_name__`. Then `__get__` calls `self.__call__()`,
   which raises `TypeError`. Two executions reach it. On Python 3.11 and 3.12
   (supported), `@classmethod` calls `__get__(cls, type(cls))` and does not
   forward `__set_name__` (comment at line 34). On every supported version, a
   descriptor assigned to an attribute of an existing metaclass gets no
   `__set_name__` (`Meta.m = cachedmethod(c)(f)`), and `Cls.m` for a class
   `Cls` of metaclass `Meta` calls `__get__(Cls, Meta)`. The edge is in the
   ground truth. The trace (Python 3.14, no such metaclass in the tests)
   cannot confirm it.
2. **No `TYPE_CHECKING` code and no optional imports.** `func.py` imports
   `threading.Condition` unconditionally. The local imports
   (`__init__.py:762, 779`; `_descriptor.py:147`) add no edge.
3. **`_TimedCache.expire` (`__init__.py:459`, `# pragma: no cover`).** It is
   an abstract hook: it raises `NotImplementedError`. Every timed cache that
   a client can create (`TTLCache`, `TLRUCache`, `_UnboundTTLCache`)
   overrides it, and `_TimedCache` is private (rule B1). So the three
   `self.expire(time)` sites of `_TimedCache` (`__init__.py:422, 427, 433`)
   reject it, and the node has no caller. Its body makes no call (rule A). The same reason rejects
   `_TimedCache.clear` at the six `self.cache.clear()` sites of the mixins;
   `TTLCache.clear` and `TLRUCache.clear` still call it explicitly.
4. **Defaults bound at definition time.** `cache_getitem=Cache.__getitem__`,
   `cache_setitem`, `cache_delitem`, `cache_repr`, `cache_len` (`__init__.py`
   181, 188, 230, 236, 251, 301, 309, 313, 354, 360, 420, 425, 497, 509, 526,
   636, 648, 667, 735) give one callee each: the default. Python calls these
   special methods through syntax with fewer arguments, and no package code
   passes the parameter.
5. **`Cache.getsizeof` is never called by the package (`__init__.py:75`).**
   `self.getsizeof(value)` runs only when `self.__size` is a dict. `Cache.__init__`
   makes it a dict only when `self.getsizeof is not Cache.getsizeof`
   (`__init__.py:40-41`). So the callee is always the client's `getsizeof`.
   Passing `Cache.getsizeof` (or `some_cache.getsizeof`, the same function)
   keeps `self.__size` at `None`.
6. **`CacheInfo(...)` has no edge (`__init__.py:752, 754`).** `cls` is
   `CacheInfo`, a subclass of a `collections.namedtuple` class. Its MRO has
   only `object.__init__`, and the generated `__new__` has no node. This
   follows the micro-benchmark case `stdlib_classes/namedtuple_methods`.
7. **`map(type, args)` (`keys.py:49, 61`).** No edge to `<builtin>.type`: a
   builtin that a builtin calls is not a call expression (micro-benchmark
   `builtins/builtin_as_callback`). The explicit `type(v)` at `keys.py:46, 58`
   is an edge.
8. **Callbacks through the library.** `heapq.heappush`, `heapify` and
   `heappop` on lists of `TLRUCache._Item` call `_Item.__lt__`
   (`__init__.py:665, 700, 707`). `sorted(..., key=lambda ...)` calls
   `TTLCache.__setstate__.<lambda1>` (`__init__.py:547`); it compares timer
   values, not `_Item` objects. `functools.partial.__call__` calls the key
   function (`_decorator.py:20` and the five other `cache_key` sites).
   `MutableMapping.popitem` calls `Cache.__iter__`, `Cache.__getitem__` and
   `Cache.__delitem__` (`__init__.py:71, 83, 87`).
9. **Name mangling.** `self.__touch` in `LFUCache` is `_LFUCache__touch`, and
   in `LRUCache` it is `_LRUCache__touch`. Each site has one callee. The same
   applies to `self.__links`: a dict in `LFUCache`, an `OrderedDict` in
   `TTLCache`.
10. **Names outside the package.** Methods of `OrderedDict` objects are named
    through `collections.OrderedDict` (`collections.OrderedDict.get` for the
    inherited `dict.get`). `obj.__dict__.setdefault` has no named callee: the client instance dictionary is an opaque mutable mapping (B5).
    `inspect.signature(self).parameters.values()` is
    `types.MappingProxyType.values`. `types.MethodType(...)` is an
    instantiation edge to `types.MethodType`. `random.choice` and
    `time.monotonic` use the path that the code reaches.
11. **`__set_name__` at the 36 class sites.** No package class body holds a
    `_MethodDescriptor`. Only client class bodies with `@cachedmethod` call
    `_MethodDescriptor.__set_name__`, through `type.__new__`.
12. **Multiple inheritance of two package caches by a client class** is not
    considered. Sites such as `del self[key]` in `FIFOCache.popitem` list only
    the `__delitem__` of the class itself, because no package class derives
    from `FIFOCache`.
13. **`%` formatting (7 sites).** `"%s is empty" % type(self).__name__` in the
    six `popitem` methods (`__init__.py:197, 263, 322, 373, 592, 724`) formats
    a str. `Cache.__repr__` (`__init__.py:47`) formats two str
    (`type(self).__name__`, `repr(self.__data)`), the client's maxsize (a
    number; `math.inf` from `func.py:15`) and the currsize (an int, or a sum
    of the client's `getsizeof` results). No operand is a package object, so
    the sites have no callee.

## Default rejection

| Candidate | Sites it decides | Reason (short) |
|---|---|---|
| `cachetools._TimedCache._Timer.__getattr__` | 512: the 511 `getattr` sites and one explicit site, the call `getattr(self.__timer, name)` | `__getattr__` runs only when a lookup on a `_Timer` fails. The package reads only `_Timer`'s own attributes, inside `_Timer`, and they are always set. Every other receiver is not a `_Timer`. |

At the explicit call `getattr(self.__timer, name)` (`__init__.py:414`) the
reason holds as worded: the receiver is the raw timer, `time.monotonic` or
the client's timer, never a `_Timer`. `_Timer` is private (rule B1), and the
package creates one only in `_TimedCache.__init__` (`__init__.py:418`) and
through `_Timer.__reduce__` (`__init__.py:411`), both times around the raw
timer; another cache's `.timer` is not a value for the `timer` parameter
(rules B2, B3). A client timer's own `__getattr__` is client behaviour (B5).
So the default decides that site too. Outside the package,
`_Timer.__getattr__` runs when the client reads an attribute of
`cache.timer`, and when `copy.deepcopy` looks up `__deepcopy__` on a `_Timer`.
Both have no package caller.

## Dispatch over the class hierarchy

"Any package cache" means an instance of `Cache`, `FIFOCache`, `LFUCache`,
`LRUCache`, `RRCache`, `TTLCache`, `TLRUCache` or `_UnboundTTLCache` (rule
B1).

| Site | Lines | Package callees |
|---|---|---|
| `self.popitem()` in `Cache.__setitem__` | `__init__.py:71, 83, 87` | 9: six `popitem` overrides, and `Cache.__iter__`, `Cache.__getitem__`, `Cache.__delitem__` through `collections.abc.MutableMapping.popitem` (for a `Cache`); 10 with the outside callee |
| `key in self` in `Cache.get`, `pop`, `setdefault` | `__init__.py:123, 129, 139` | 3: `__contains__` of `Cache`, `TTLCache`, `TLRUCache` |
| `self[key]` in `Cache.get`, `pop`, `setdefault` | `__init__.py:124, 130, 140` | 5: `__getitem__` of `Cache`, `LFUCache`, `LRUCache`, `TTLCache`, `TLRUCache` |
| `del self[key]` in `Cache.pop` | `__init__.py:131` | 7: every `__delitem__` |
| `self[key] = value` in `Cache.setdefault` | `__init__.py:142` | 7: every `__setitem__` |
| `self.expire(time)` in `_TimedCache` | `__init__.py:422, 427, 433` | 2: `TTLCache.expire`, `TLRUCache.expire` (judgement 3) |
| `cache[key]` in the six mixins | `_decorator.py:23, 48, 82, 114, 147, 190` | 5 (as `self[key]`) |
| `cache[key] = val` in four mixins | `_decorator.py:28, 89, 121, 200` | 7 |
| `cache.setdefault(key, val)` | `_decorator.py:57, 158` | 2: `Cache.setdefault`, `_TimedCache.setdefault` |
| `self.cache.clear()` | `_decorator.py:34, 63, 100, 127, 164, 211` | 7 clear methods; at 211 also `<builtin>.dict.clear` (the dict of `func.py`) |
| `self.cache_key(...)` | `_decorator.py:20, 43, 73, 111, 142, 181` | 4 key functions; 5 with `functools.partial.__call__` |
| `self.__func(...)` | `_decorator.py:26, 51, 86, 119, 152, 197` | 6: six mixin `__call__` (stacked wrappers) |
| `self.__descriptor.__get__(obj)(...)` | `_descriptor.py:142` | 1: `_Unbound.__call__` for obj=None; non-None returns are opaque client mapping-method results (B5) |
| `self.__wrapper(obj, self)` | `_descriptor.py:54, 68` | 8 lambdas of `_cachedmethod._wrapper` |
| `{self.__wrapped__!r}`, `{wrapped!r}` | `_cached.py:46`, `_cachedmethod.py:48`, `_descriptor.py:127` | 1 at `_cached.py:46` (`_cached._WrapperBase.__repr__`); none at the other two (rule B3) |
| `cache.maxsize`, `cache.currsize` in `_make_info` | `__init__.py:752` | 2 each |

The sites in the subclasses (`del self[key]` in each `popitem`,
`self.expire(time)` in `TTLCache` and `TLRUCache`) have one callee: no package
class derives from `FIFOCache`, `LFUCache`, `LRUCache`, `RRCache` or
`TLRUCache`, and `_UnboundTTLCache` inherits these methods from `TTLCache`.

## Trace edges rejected as client callbacks

`cachetools.rejected.json` has 17 trace edges. Thirteen are calls of objects
that the tests pass in:

- `getsizeof=len` (`<builtin>.len` from `Cache.__setitem__`);
- `choice=min`, `choice=max` (from `RRCache.popitem`);
- `timer=datetime.now` (from `_Timer.__call__` and `_Timer.__enter__`);
- a dict as `cache` of `cached`/`cachedmethod` without a condition
  (`<builtin>.dict.clear` from five `cache_clear` methods,
  `<builtin>.dict.setdefault` from `_LockedMixin.__call__` and
  `_LockedInfoMixin.__call__`);
- a `threading.Condition` with `info=False` (`threading.Condition.notify_all`
  from `_ConditionMixin.__call__`).

The other four are `_MethodDescriptor.__get__` to `dict.get` and
`dict.setdefault`, and `_Unbound.__call__` to `_BasicMixin.__call__` and
`_InfoMixin.__call__`. They cross the opaque client-result boundary above.

## Functions that no site calls

50 nodes have no caller in the graph. None is a missed edge:

- **Modules** (7): `cachetools`, `cachetools._cached`, `cachetools._cachedmethod`,
  `cachetools._decorator`, `cachetools._descriptor`, `cachetools.func`,
  `cachetools.keys`.
- **Public API that the client calls**: `cachedmethod`,
  `cachedmethod.decorator`, `func.fifo_cache`, `lfu_cache`, `lru_cache`,
  `rr_cache`, `ttl_cache`; `TLRUCache.__init__` (no package code creates a
  `TLRUCache`); `Cache.getsizeof` (judgement 5); the properties
  `RRCache.choice`, `TTLCache.ttl`, `TLRUCache.ttu`; `_TimedCache.get` and
  `_TimedCache.pop` (the `get` and `pop` of every timed cache); the wrapper
  methods `cache_clear` (six) and `cache_info` (three);
  `func._cache.decorator.<lambda1>` (the `cache_parameters` attribute).
- **Special methods that only client syntax or the library reaches**:
  `_TimedCache.__len__` and `__repr__` (`len()`, `repr()` of a timed cache;
  `_make_info` calls `len()` only for objects that are not caches);
  `TTLCache.__iter__` and `TLRUCache.__iter__` (iteration over a timed cache;
  both override `popitem`, so `MutableMapping.popitem` never iterates over
  them; the regenerated trace shows both run under client iteration); `_cached._WrapperBase.__get__` and `_Unbound.__get__` (attribute
  access in a client class); `_MethodDescriptor.__set_name__` (judgement 11);
  `_Timer.__getattr__` (the client reads an attribute of `cache.timer`, or
  `copy.deepcopy` looks up `__deepcopy__`; a `_Timer` never wraps another
  `_Timer`, rule B3); `_cachedmethod._WrapperBase.__repr__` and
  `_Unbound.__repr__` (`repr()` of `obj.method` and `Cls.method` by the
  client; no package wrapper wraps them, rule B3). By rule A, all three keep
  the edges of their bodies (`<builtin>.getattr`, `<builtin>.object.__repr__`).
- **Pickle and copy protocol** (`pickle`, `copy` called by the client):
  `TTLCache._Link.__reduce__`, `_Timer.__reduce__`, `TTLCache.__setstate__`,
  `_cached._WrapperBase.__reduce__`, `_cachedmethod._WrapperBase.__reduce__`,
  `_MethodDescriptor.__reduce__`, `_MethodDescriptor._lookup`,
  `_Unbound.__reduce__`.
- **Not reachable through the public API**: `_TimedCache.expire`, the
  abstract hook that every timed cache overrides (judgement 3, rules A and
  B1).

## Statistics

| Measure | Value |
|---|---|
| Ledger-relevant sites (of 1289 total AST sites) | 1122: 359 call, 16 decorator, 36 class, 29 with, 24 iter, 16 mapping, 43 op, 23 getitem, 20 setitem, 17 delitem, 511 getattr, 18 truth, 10 format |
| Sites with candidates / value sites | 962 / 53 |
| Ledger entries | 671 (all 375 explicit sites; 296 implicit sites; the default decides the other 451 getattr sites; in total it decides 512 sites, one of them explicit) |
| Entries with callees / without | 447 / 224 (11 explicit sites without callees, each with a note) |
| Callee lines / rejected candidates / exclusions / notes | 681 / 477 (258 entries with `reject *`) / 20 / 142 |
| Edges | 615: 459 in the package, 156 to 52 callees outside |
| Trace | 517 edges (347 in the package, 170 outside); 173 of 174 functions run (not `_TimedCache.expire`) |
| Edges confirmed by the trace | 500 of 615 (81.3%) |
| Trace edges rejected as client callbacks | 17 |
| Edges only from reading | 115 (114 in the package, 1 outside) |

The edges only from reading are: the dispatch sites above for the cache
classes that the tests do not combine with a site; the mixin-to-mixin
`__call__` edges of stacked wrappers that the tests do not combine; the
descriptor branch (judgement 1); `_Unbound.__call__ -> _Unbound.__call__` (a
receiver `None`); and `threading.Condition.wait`, which needs two threads that
compute the same key at the same time.
