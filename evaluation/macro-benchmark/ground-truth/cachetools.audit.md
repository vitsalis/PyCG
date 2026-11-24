# cachetools: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release v8.0.0, commit `1ce79efa552d1bdda70d144d401ef9105d999184`. Audited
files: the revised ground truth that follows commit 1975c81
(`cachetools.ledger`: 664 entries, 140 notes; `cachetools.json`: 640 edges,
482 in the package and 158 outside; `cachetools.rejected.json`: 13 edges;
`cachetools.md`). The trace confirms 504 edges, so 136 come from reading
only, and 47 nodes have no caller. `check.py cachetools` reports no errors.

I judged the files by the final scope rules of the lead (A: edges per
function; B1-B5: the values that reach a site; C: public names). I read the
source, `docs/index.rst`, `CHANGELOG.rst`, the `.pyi` stubs and the tests as
data. I did not run the package and did not use any static analysis tool.

**Final state.** 6 findings against the ground truth (A1-A5, C2) and 1
remark on the wording of rule B1 (R1). The lead accepted all of them. A4 and
A5 change the graph: the writer removes 17 edges. The graph then has 623
edges (465 in the package, 158 outside). The trace confirms 504 of them, 119
come from reading only, and 50 nodes have no caller. The other findings
change wording (A1, A2, A3) or two ledger lines (C2).

## Findings

| Id | Kind | Site or edge | Evidence | Confidence | Decision |
|---|---|---|---|---|---|
| A4 | edge that cannot happen (14 edges) | `_decorator.py` 26:26, 51:26, 86:30, 119:26, 152:26, 197:30 `self.__func(...)` -> `_descriptor._Unbound.__call__` (6); `_cached.py` 46:26 `{self.__wrapped__!r}` -> `_cachedmethod._WrapperBase.__repr__`, `_Unbound.__repr__` (2); `_cachedmethod.py` 48:32 and `_descriptor.py` 127:32 `{wrapped!r}` -> each of the three wrapper `__repr__` (6) | These edges need a product of `cachedmethod` (the bound `obj.method` or the `_Unbound` `Cls.method`) as the decorated function of `cached`/`cachedmethod`, or a `cached` wrapper as the method of `cachedmethod`. The parameter is the abstract `Callable[_P, _R]` (`__init__.pyi:204-229, 280-307`). Only `@cached` over `@cached` has evidence that the package uses it in that role: `_cached.py:30-31`, `CHANGELOG.rst:98` ("Fix `@cached` decorator stacking behavior"), `tests/test_cached.py:352`, `tests/test_func.py:135`. No documentation, test or package code passes a `cachedmethod` product as a decorated function, or a wrapper to `cachedmethod`. The docs present `Cls.method` as a discouraged way to call the method (`docs/index.rst:643-652`). B3: an arbitrary package object where any callable is accepted. Keep all 36 mixin `__call__` -> mixin `__call__` edges and `_cached` `__repr__` -> `_cached` `__repr__`: stacked `cached` wrappers give each of them. | likely | accepted by the lead; the writer removes the 14 edges |
| A1 | false rejection reason | `_decorator.py` 26:26, 51:26, 86:30, 119:26, 152:26, 197:30: `_MethodDescriptor.__call__` is not a callee | Excluding the edge is right; the stated reason is not. The note and `cachetools.md` (scope table, row "decorated function") rely on the stub typing. But `__init__.pyi:247-266` (`_cachedmethod_wrapper`, which has `__set_name__`) is the type of the descriptor, and it declares `__call__`. "It only raises `TypeError`" does not stop the call either. The reason by B2/B3: the parameter is the abstract `Callable`, which names no package type for the role. The package never passes a `_MethodDescriptor` there, and its documentation does not offer one. So it is an arbitrary package object where any callable is accepted. | certain | the 6 edges stay out; the writer rewords the reason |
| A2 | doubtful (note text) | `_descriptor.py` 142:46, note of `self.__descriptor.__get__(obj)(*args, **kwargs)` | The note says that for a receiver `None` this calls the `_Unbound`, "whose `__call__` then raises `TypeError`". Not always. `Cls.method(None, a, 1)`: the first `_Unbound.__call__` takes `None` (`_descriptor.py:139`), and `__get__(None)` returns the cached `_Unbound` (`:40-42, 85-89`). The second `__call__` takes `a` as the receiver and calls the method. The edge `_Unbound.__call__ -> _Unbound.__call__` is correct; only the note is wrong. | certain | the writer fixes the note |
| A3 | doubtful (incomplete reason) | `_descriptor.py` 36:30 `self.__call__()`; `cachetools.md` judgement 1 | The edge `_MethodDescriptor.__get__ -> __call__` is justified only by the 3.11/3.12 `@classmethod` branch. It also runs on every supported version when a descriptor that never got `__set_name__` is read with a class as `obj`. Example: `Meta.m = cachedmethod(c)(f)` after `Meta` exists (a class attribute assignment does not call `__set_name__`), then `Cls.m` for a class of metaclass `Meta` (`:32-36`). The edge stays. | likely | the writer fixes judgement 1 |
| C2 | convention (B5; no change to the graph) | `_descriptor.py` 56:50 `obj.__dict__.setdefault(attrname, wrapper)` and 63:51 `obj.__dict__.setdefault("__cachetools_cachedmethods", {})`: callee `<builtin>.dict.setdefault` | The receiver is the `__dict__` of the client's instance. The docs require only "a mutable mapping" (`docs/index.rst:588-592`), and the code handles other mappings (`:57, 64`). Under B5 that object is opaque, so these two sites have no outside callee. The graph edge `_MethodDescriptor.__get__ -> <builtin>.dict.setdefault` stays: at 69:46, `wrappers` is the package's own `{}` of 63:51. The same holds at 66:35 `wrappers.get(self)` for `<builtin>.dict.get`. An attribute of a client object is as opaque as the object (B5). The `**kwargs` mappings are different: the interpreter builds them for the package function's own call, so they are package values and keep their `dict` method edges. | likely | accepted by the lead; the writer changes the two ledger lines, and the graph does not change |
| A5 | edge that cannot happen (3 edges) | `__init__.py` 395:36 and 401:50 `self.__timer()` -> `_TimedCache._Timer.__call__`; 414:27 `getattr(self.__timer, name)` -> `_TimedCache._Timer.__getattr__` | These edges need one cache's `_Timer` as the `timer` of another cache. The parameter is a bare `Callable[[], _TT]` (`__init__.pyi:86, 114, 135`). Its docs offer `time.monotonic` (the default) and `datetime.now` (`docs/index.rst:143-161, 196-208`). No documentation, test or package code passes `cache.timer` as a timer: the tests pass client `Timer()` objects, `datetime.now` and lambdas. When the package rebuilds a `_Timer`, it passes on the raw timer, not the `_Timer` (`_Timer.__reduce__`, `__init__.py:411`). By B2/B3 the package never produces a `_Timer` for this role. The property docstring "The timer function used by the cache" (`__init__.py:438`) describes what the property returns, not what the parameter takes. After the removal, 414:27 rejects `_Timer.__getattr__`, and the notes at 395:36 and 401:50 lose the `_Timer` sentence. | likely | accepted by the lead; the writer removes the 3 edges |
| R1 | rule wording (no change to the ground truth) | B1, applied to `__init__.py:71, 83, 87, 123-142` | B1 said `self` in a method of C is a C or a package subclass that inherits the method. Explicit base calls also pass subclass instances: `cache_setitem(self, ...)` with the default `Cache.__setitem__` (`:181, 236, 309, 354, 509, 648`), and `Cache.get/pop/setdefault(self, ...)` in `_TimedCache` (`:443, 447, 451`). Read literally, B1 would drop the six `popitem` overrides at `:71, 83, 87` and the `TTLCache`/`TLRUCache` methods at `:123-142`, which the trace confirms. The ground truth keeps them and is right. | certain | accepted: B1 now also counts a subclass that calls the base method explicitly (`Cache.__setitem__(self, ...)`, `super()`) |

## Step 1: blind re-derivation

**Class hierarchy (drawn before I opened the ledger).** `D` = defines,
`O` = overrides. `MutableMapping` supplies `popitem`, `update`, `keys`,
`items`, `values`, `__eq__`.

| Class | Base | Methods |
|---|---|---|
| `Cache` | `collections.abc.MutableMapping` | D `__init__`, `__repr__`, `__getitem__`, `__setitem__`, `__delitem__`, `__contains__`, `__missing__`, `__iter__`, `__len__`, `get`, `pop`, `setdefault`, `clear`, `maxsize`, `currsize` (properties), `getsizeof` (static). No `popitem`. |
| `FIFOCache` | `Cache` | O `__init__`, `__setitem__`, `__delitem__`, `clear`; D `popitem` |
| `LFUCache` | `Cache` | O `__init__`, `__getitem__`, `__setitem__`, `__delitem__`, `clear`; D `popitem`, `__touch`; nested `_Link` (`__init__`, `unlink`) |
| `LRUCache` | `Cache` | O `__init__`, `__getitem__`, `__setitem__`, `__delitem__`, `clear`; D `popitem`, `__touch` |
| `RRCache` | `Cache` | O `__init__`, `__setitem__`, `__delitem__`, `clear`; D `popitem`, `choice` |
| `_TimedCache` (private) | `Cache` | O `__init__`, `__repr__`, `__len__`, `currsize`, `get`, `pop`, `setdefault`, `clear`; D `timer`, `expire` (raises); nested `_Timer` (`__init__`, `__call__`, `__enter__`, `__exit__`, `__reduce__`, `__getattr__`) |
| `TTLCache` | `_TimedCache` | O `__init__`, `__contains__`, `__getitem__`, `__setitem__`, `__delitem__`, `__iter__` (generator), `expire`, `clear`; D `popitem`, `__setstate__` (+ lambda), `ttl`; nested `_Link` (`__init__`, `__reduce__`, `unlink`) |
| `TLRUCache` | `_TimedCache` | O `__init__`, `__contains__`, `__getitem__`, `__setitem__`, `__delitem__`, `__iter__` (generator), `expire`, `clear`; D `popitem`, `ttu`, `__delitem`; nested `_Item` (`__init__`, `__lt__`; `total_ordering` adds library `__gt__`, `__le__`, `__ge__`) |
| `func._UnboundTTLCache` | `TTLCache` | O `__init__`, `maxsize` |
| `CacheInfo` | `namedtuple` class | D `_make_info` (classmethod) |
| `_decorator._{Basic,Locked,Condition}Mixin` | `object` | `__init__`, `__call__`, `cache_clear` |
| `_decorator._{Info,LockedInfo,ConditionInfo}Mixin` | `object` | `__init__`, `__call__`, `cache_clear`, `cache_info` |
| `_cached._WrapperBase` | `object` | `__init__`, `__get__`, `__reduce__`, `__repr__`; six wrappers = base + one mixin, each with `__init__` |
| `_cachedmethod._WrapperBase` | `object` | `__init__`, `__reduce__`, `__repr__`, `cache`, `cache_lock`, `cache_condition` (properties), `__none` (static); six wrappers as above |
| `_descriptor._MethodDescriptor` | `object` | `__init__`, `__set_name__`, `__get__`, `__reduce__`, `_lookup`, `__call__`, `__get_unbound`, `__instance_dict_error` |
| `_descriptor._Unbound` | `object` | `__init__`, `__reduce__`, `__repr__`, `__get__`, `__call__`, `__pop_receiver` |

**Sample.** I made the skeleton without the ledger: a copy of `check.py`,
`ledger.py`, `sites.py`, `trace.py`, `projects.toml` and
`micro-benchmark/validate.py` under `$TMPDIR/ct-audit/`, with a symbolic
link to the real `projects/`. It has 1115 sites: 229 implicit (getitem,
setitem, delitem, iter, with, op, truth, class, mapping, format) and 886
others. I numbered the site lines from 0 in file order. Then
`rng = random.Random(20261111)`, `rng.sample(implicit, 30)`,
`rng.sample(others, 50)`. None of the 53 sites with no candidates by name
fell in this sample, so I added all 53: 133 sites. I wrote my callees for
each site before I opened the ledger, and left the callees that depended on
the open questions conditional. The table uses the final decisions.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random implicit | 30 | 30 | 0 |
| Random other (16 explicit, 34 getattr) | 50 | 50 | 0 |
| No candidates by name | 53 | 43 | 10 |
| **Total** | **133** | **123** | **10 (7.5 %)** |

The 10 disagreements, classified:

- **I was wrong (1):** 142:46 `self.__descriptor.__get__(obj)(...)`. I missed
  `_Unbound.__call__`, which `Cls.method(None, ...)` reaches.
- **The writer has an edge that cannot happen (9):** 395:36 and 401:50
  (`-> _Timer.__call__`, A5); `_cachedmethod.py` 48:32 (three `__repr__`,
  A4); the six `self.__func(...)` sites (`-> _Unbound.__call__`, A4).
- **Naming only (0). The writer missed an edge (0).**

At the six `self.__func(...)` sites I also listed `_MethodDescriptor.__call__`
as conditional. The writer excludes it, and so does the final decision (A1).

## Step 2: dispatch over the class hierarchy (B1)

For a site in a method of C, the receivers are C if a client or the package
can create a bare C, every package subclass that inherits the method, and
every package subclass that calls the base method explicitly on itself (the
clause added by R1).
`Cache` and its public subclasses are creatable by clients. `_TimedCache` is
private, and the package never creates a bare one. "Timed" = `TTLCache`,
`TLRUCache`, `_UnboundTTLCache`. Every row is identical to the ledger.

| Site | Receivers (how they reach the method) | Callees |
|---|---|---|
| `self.popitem()` `__init__.py:71, 83, 87` | `Cache` (bare); FIFO, LFU, LRU, RR, timed (explicit `cache_setitem`) | `MutableMapping.popitem` with call-backs `Cache.__iter__`, `__getitem__`, `__delitem__`; `popitem` of FIFO, LFU, LRU, RR, TTL, TLRU |
| `self.getsizeof(value)` `:75` | all | client only: the branch needs `self.getsizeof is not Cache.getsizeof` (`:40-41`) |
| `self.__missing__(key)` `:58, 507, 646` | all | `Cache.__missing__` |
| `key in self` `:123, 129, 139` | `Cache`, FIFO, LFU, LRU, RR (inherit); timed (explicit, `:443, 447, 451`) | `__contains__` of `Cache`, `TTLCache`, `TLRUCache` |
| `self[key]` `:124, 130, 140` | same | `__getitem__` of `Cache`, LFU, LRU, TTL, TLRU |
| `del self[key]` `:131` / `self[key] = value` `:142` | same | the 7 `__delitem__` / the 7 `__setitem__` |
| `del self[key]` in each `popitem` (`:200, 266, 325, 376, 595, 727`) | the class (TTL also `_UnboundTTLCache`) | its own `__delitem__` |
| `self.expire(time)` `:422, 427, 433` | timed (inherit); not a bare `_TimedCache` | `TTLCache.expire`, `TLRUCache.expire` |
| `self.expire(...)` `:512, 551, 588` / `:650, 720` | TTL, `_UnboundTTLCache` / TLRU | `TTLCache.expire` / `TLRUCache.expire` |
| `super().currsize` `:434` | timed | `Cache.currsize` |
| `self.timer` (13 loads), `self.timer()` (8), `with self.timer` / `with self.__timer` (13) | timed / the package's `_Timer` | `_TimedCache.timer`; `_Timer.__call__`; `_Timer.__enter__`, `__exit__` |
| 25 calls of a default `cache_*=Cache.X` or of a local `cache_getitem`/`cache_delitem`; every explicit `Cache.X(self, ...)`, `_TimedCache.X(self, ...)`, `TTLCache.__init__(self, ...)` | | the named function only |
| `self.__touch` `:233, 239, 311`; `unlink()` `:256, 290, 520, 529, 578` | name mangling; link type | own `__touch`; own `_Link.unlink` |
| mixins: `self.cache` (15), `self.cache_lock` (10), `self.cache_condition` (2) | 6 `_cached` wrappers (instance attributes), 6 `_cachedmethod` wrappers (properties) | the `_cachedmethod._WrapperBase` property |
| `cache[key]` (6 mixins) | any public cache, `_UnboundTTLCache`, the dict of `func.py` | `__getitem__` of `Cache`, LFU, LRU, TTL, TLRU |
| `cache[key] = val` (4 mixins) | same | the 7 `__setitem__` |
| `cache.setdefault` (Locked, LockedInfo) | any public cache (`func.py` passes its dict only to ConditionInfo) | `Cache.setdefault`, `_TimedCache.setdefault` |
| `self.cache.clear()` (`_decorator.py:34, 63, 100, 127, 164, 211`) | same | the 7 `clear` overrides; `<builtin>.dict.clear` only at `:211` |
| `cache.maxsize`, `cache.currsize` `:752` | any `Cache` instance | `Cache.maxsize`, `_UnboundTTLCache.maxsize`; `Cache.currsize`, `_TimedCache.currsize` |

No package code calls `update`, `keys`, `items`, `values`, `get`, `pop`,
`len()`, `iter()` or `repr()` on a cache. The only inherited
`MutableMapping` method that the package calls is `popitem`.

## Step 3: the 136 untraced edges

| Class | Edges |
|---|---|
| Certainly possible | 119: 36 `cache[key]` / `cache[key] = val` dispatch from the mixins; 31 `cache.clear()` dispatch; 34 mixin `__call__` -> mixin `__call__` (stacked `cached` wrappers); 4 `_Unbound.__call__` -> mixin `__call__` (`Cls.method(obj)`); 8 key functions; 2 `-> _TimedCache.setdefault`; `_cached` `__repr__` -> `_cached` `__repr__` (stacked); `-> threading.Condition.wait` (`func.py`, two threads with the same key); `_MethodDescriptor.__get__ -> __call__` (A3); `_Unbound.__call__ -> _Unbound.__call__` (A2) |
| Cannot happen; the writer removes them | 17: the 14 edges of A4, and the 3 edges of A5 (`_Timer.__call__ -> _Timer.__call__`, `_Timer.__enter__ -> _Timer.__call__`, `_Timer.__getattr__ -> _Timer.__getattr__`) |

The 504 confirmed edges come from tests that stay inside the public API: no
test creates a `_TimedCache`, passes one cache's `timer` to another cache, or
decorates a product of `cachedmethod` (search of `tests/`).

## The writer's decisions on the three questions

- **(a) `_TimedCache` as a receiver: removed, and that is right (B1, C).**
  I checked each site. `self.expire(time)` at `__init__.py:422, 427, 433`
  runs for the timed classes only: `TTLCache` and `TLRUCache` override
  `expire` (`:558, 688`), and `_UnboundTTLCache` inherits `TTLCache.expire`.
  `self.cache.clear()` at `_decorator.py:34, 63, 100, 127, 164, 211` runs on
  a cache from the client or from `func.py`, never a bare `_TimedCache`.
  `TTLCache` and `TLRUCache` override `clear` (`:598, 730`), so
  `_TimedCache.clear` runs only through the explicit calls at `:599, 731`,
  which the ledger has. The timed classes do inherit `_TimedCache.get`,
  `pop`, `setdefault`, `__repr__`, `__len__` and `currsize`, and the ledger
  keeps every package edge to them (`cache.setdefault ->
  _TimedCache.setdefault`, `cache.currsize -> _TimedCache.currsize`).
  `_TimedCache.expire` keeps its body's out-edges (rule A): none, because
  `raise NotImplementedError` has no call. Confidence: certain.
- **(b) Another cache's `_Timer` as `timer`: kept by the writer; it goes
  (A5, accepted).**
- **(c) Decorated callables: the `cached`/`func.py` wrappers stay (certain).
  `obj.method` and `Cls.method` go (A4, accepted). The `_MethodDescriptor`
  stays out with a B2/B3 reason (A1).** For B2, the evidence that the
  package passes a value there includes the project's own tests and
  documented examples. A stub that types a value as a bare callable is not
  evidence.

## Annotated outside types (B4, B5)

B4 adds an edge only when the annotation or documentation fixes a concrete
outside type. No cachetools parameter has one. B5 then makes every
client-supplied value with an abstract annotation opaque.

| Parameter | Stub | Documentation | Result |
|---|---|---|---|
| `lock` (`cached`) | `AbstractContextManager[Any] \| None` | "an object implementing the context manager protocol", with `threading.Lock`/`RLock` as examples (`docs/index.rst:338-343`) | opaque; the only use is `with lock:` (implicit, never an edge) |
| `condition` (`cached`) | `_AbstractCondition \| None`, a `Protocol` (`__init__.pyi:148-155`) | "an object providing `wait()`, ... `notify_all()` methods as defined by `threading.Condition`" (`:352-355`) | the stub's protocol decides (the lead's decision): opaque. `_ConditionMixin.__call__ -> threading.Condition.notify_all` stays rejected, and `cond.wait()` there has no callee |
| `lock`, `condition`, `cache` (`cachedmethod`) | `Callable[[Any], ...]` | functions called with `self` (`:565-569`) | client callbacks; what they return is opaque |
| `cache` (`cached`) | `MutableMapping[_KT, Any]` | "any mutable mapping type, including plain `dict` and `weakref.WeakValueDictionary`" (`:325-330`) | opaque: the 7 `dict.clear`/`dict.setdefault` rejections stay |
| `timer` | `Callable[[], _TT]` | default `time.monotonic`; example `datetime.now` (`:143-161`) | client callback: `datetime.datetime.now` stays rejected; `time.monotonic` is in as the package default |
| `getsizeof` | `Callable[[_VT], float] \| None` | "a callable `getsizeof(value)`"; example `len` (`:51-53, 395`) | client callback: `<builtin>.len` stays rejected |
| `choice` | `Callable[[Sequence[_KT]], _KT] = random.choice` | "an alternative function" (`:129-132`) | client callback: `min`/`max` stay rejected; `random.choice` is in as the default |
| `ttu` | `Callable[[_KT, _VT, _TT], _TT]` | a user-provided function (`:179-183`) | client callback: no callee |

**Every outside method edge of the graph, by receiver.** No graph edge
depends on an opaque client value:

- `<builtin>.dict.clear`, `.pop`, `<builtin>.list.*`, `<builtin>.set.*`, and
  all `collections.OrderedDict.*`: the receivers are the package's own
  containers (`self.__data`, `__size`, `__links`, `__index`, `__keys`,
  `__order`, `__items`, `__pending`, the `_Link.keys`).
- `<builtin>.dict.clear` at `_ConditionInfoMixin.cache_clear`
  (`_decorator.py:211`): the `{}` that `func.py:42, 56, 70, 84` builds, a
  package value.
- `<builtin>.dict.pop` in `_Unbound.__pop_receiver` and `<builtin>.dict.items`
  in `keys.py`: the `**kwargs` dict that Python builds.
- `<builtin>.dict.update` in `TTLCache.__setstate__`: the `__dict__` of a
  package cache.
- `<builtin>.dict.get` / `.setdefault` in `_MethodDescriptor.__get__`: at
  66:35 and 69:46 the receiver is the package's `{}` of 63:51. At 56:50 and
  63:51 the receiver is the client instance's `__dict__`, which is opaque
  (C2): those two ledger lines lose their callee, but the graph edge stays.
- `threading.Condition.wait`, `.notify_all` from `_ConditionInfoMixin.__call__`
  (the only untraced outside edge is `wait`): the `Condition()` of
  `func.py:28`, a package value, which `_cached.py:90` passes as lock and
  condition.
- `functools.partial.__call__` from the six mixins: the
  `functools.partial(key, obj)` that `_cachedmethod.py:37` builds.
- `types.MappingProxyType.values`: what `inspect.signature` returns.
  `<builtin>.object.__repr__`: an explicit call through `object`.
  `collections.abc.MutableMapping.popitem`: on a package `Cache`.

All 13 rejected trace edges stay rejected. Each callee is a value that the
client supplied (rule A).

## Steps

1. Blind sample: 133 sites (80 seeded, 53 with no candidates). 10
   disagreements: 1 where I was wrong, 9 edges of the writer that cannot
   happen (A4, A5).
2. Dispatch: every self/cache protocol site, about 170 sites, with the B1
   clause of R1. 0 differences.
3. Untraced edges: all 136 classified. 119 certainly possible, 17 cannot
   happen (A4, A5).
4. Decorators: 8 branches of `_cached._wrapper` (6 classes), 8 lambdas of
   `_cachedmethod._wrapper` (6 classes), 12 wrapper `__init__` methods, 6
   mixins (`__call__`, `cache_clear`, `cache_info`), the descriptor protocol,
   `__set_name__`, the version branch, `_Unbound.__call__`/`__get__`, and the
   value sites `self.__func`, `self.__wrapper`, `self.cache_key`,
   `self.__info`, `self.__cache/__lock/__cond`. Findings A1-A5.
   `functools.update_wrapper` and `inspect.signature` call no package code
   back: they read instance attributes, and `inspect.unwrap` follows
   `__wrapped__` to a client function.
5. Callers: 47 nodes with no caller (7 modules, 40 functions); 50 after A4
   and A5 (`_cachedmethod._WrapperBase.__repr__` and `_Unbound.__repr__` are
   then reached only by client `repr()`, `_Timer.__getattr__` only by a
   client attribute read on `cache.timer`). Each reason in `cachetools.md` holds.
   `Cache.getsizeof` is never called: `self.__size` is a dict only when
   `self.getsizeof is not Cache.getsizeof` (`__init__.py:40-41`), and
   `some_cache.getsizeof` is the same function. No package class body holds
   a `_MethodDescriptor`, so `type.__new__` never calls a package
   `__set_name__` (36 class sites; `_HashedTuple` has no site). Rule A:
   every function keeps the out-edges of its body; I found none dropped.
6. Default rejection of `_Timer.__getattr__` (511 getattr sites): correct.
   Only 10 loads have a `_Timer` receiver, all inside `_Timer`
   (`:394-414`). They read `_Timer__nesting`, `_Timer__timer` and
   `_Timer__time`, which are always set first (`:390-391, 400-404`; `copy`
   and `pickle` go through `__reduce__`, so through `__init__`). `_Timer`
   defines `__init__`, `__call__`, `__enter__`, `__exit__`, `__reduce__`,
   `__getattr__`. Special methods are looked up on the type, and no package
   code loads an attribute of `cache.timer`. Only misuse (a direct
   `cache.timer.__exit__()` before any `__enter__`) could make `self.__time`
   fail. The one accepted callee, at the call 414:27, goes with A5; the site
   then rejects it.
7. Rejections and notes: all 206 rejection lines at the sites of steps 2 and
   4, 80 of the other 196 (seed 20261111), and all 140 notes. Every
   rejection reason holds. Notes to change: A1, A2, the A4 notes at the six
   `self.__func` sites and the three `{wrapped!r}` sites, the A5 notes at
   395:36, 401:50 and 414:27, and C2 at 56:50 and 63:51.
8. Outside callees: all 158 outside edges, grouped by callee (54 names).
   Each exists and is named by the rules or by a trace alias (`heapq.*` =
   `_heapq.*`, `types.MethodType` = `builtins.method`, `random.choice` =
   `random.Random.choice`, `collections.OrderedDict.get` =
   `<builtin>.dict.get`). B4/B5 check above. All 13 rejected trace edges are
   client values. The package defaults (`random.choice`, `time.monotonic`,
   `keys.hashkey`/`methodkey`/`typedkey`, the `{}` and `Condition()` of
   `func.py`) are in the graph.
9. `check.py cachetools`: no errors. `--report`: 14 sites with callees beyond
   the candidates (3 `popitem` call-backs, 8 `self.timer()` ->
   `_Timer.__call__`, 3 heapq -> `_Item.__lt__`). All are correct. 0 trace
   edges are unaccounted for.

## Judgement

The ground truth is complete: I found no missing edge, and every confirmed
edge and dispatch row is right. Its precision problem is 17 edges that rest
on two readings beyond rule B2: `cachedmethod` products as decorated
functions (A4, 14 edges) and a cache's `_Timer` as another cache's timer
(A5, 3 edges). The writer removes them. The other findings change wording
only (A1, A2, A3) or two ledger lines without a graph change (C2). After the
removal the graph has 623 edges, and each one is confirmed by the trace or
certainly possible.

## Verification of the writer's result

I checked the ground truth of commit b6597d2 against the version I audited
(the graph of 79fc2ca and 5ff9d60):

- The graph lost exactly the 17 edges of A4 and A5, and gained none. The 181
  nodes are the same. It has 623 edges (465 in the package, 158 outside).
- The trace still confirms the same 504 edges; 119 come from reading only.
- 50 nodes have no caller. The three new ones keep the out-edges of their
  bodies (rule A): `_Timer.__getattr__` -> `<builtin>.getattr`;
  `_cachedmethod._WrapperBase.__repr__` -> `<builtin>.object.__repr__`;
  `_Unbound.__repr__` has none (it formats a client function).
- The notes and rejections at 395:36, 401:50 and 414:27 (A5), at the six
  `self.__func(...)` sites and the three `{wrapped!r}` sites (A4, A1), at
  142:46 (A2), at 36:30 and in judgement 1 (A3), and at 56:50 and 63:51 (C2)
  say what the findings ask. The default rejection now also decides 414:27
  (512 sites), with a reason based on rule B2.
- `check.py cachetools`: no errors; 0 trace edges unaccounted for.
- Rule A: I searched the ledger for reasons based on how a function is
  called rather than on the values that reach a site. Every rejection rests
  on the values. One note is phrased by callers: 752:23, "`_make_info` is
  reached only as `CacheInfo._make_info`". Its result holds by B1: in a
  classmethod of `CacheInfo`, `cls` is `CacheInfo` (no package class derives
  from it) or a client subclass (client code). Wording only; no edge
  changes.


## Fourth full source audit (2026-11-16)

A fresh source-first pass read all seven runtime modules, the shipped stubs,
metadata and CI, and the documentation and tests that establish value roles.
It froze its source model and complete body/site inventories before opening
the baseline ledger, graph or prior project audit. It then reviewed all
615 graph pairs, 1289 AST sites (1122 ledger-relevant), 181 nodes, the
default rejection, all explicit rejections and all exclusions. No target,
dependency or test code was imported or executed.

No graph correction: 181 nodes and 615 pairs remain (459 package,
156 outside). The 17 rejected trace pairs and the 115 added pairs remain.
The judgement file now explicitly records PyPy support from CI and labels
the site-count denominator. These are two metadata clarifications.

The provisional frozen model's claim that the descriptor's `wrappers`
dictionary remains concrete was rejected during comparison: it is the
result of a client mapping method (`_descriptor.py:63`), so B5 keeps it
opaque. Likewise every successful non-None descriptor return crosses a
client method result at lines 56, 66 or 69. The outer call at line 142
therefore keeps only the package `_Unbound` recursion for `obj=None`.
This confirms the existing exclusions; it adds no edge. The source freeze
was preserved without amendment.

The review also confirmed all six-by-six stacked function-wrapper calls
from the tested factory-output role; key partial callbacks; cache receiver
dispatch; heap/sorted/MutableMapping callbacks; timer property and context
protocols; the pre-3.13 descriptor rejection; argument-binding and exception
cutoffs; and the zero-edge bodies. CPython and the explicitly supported
PyPy do not require another target at these sites under the naming rules.

The isolated structural and origin checks passed. Compact pair/site/body
coverage, input and final hashes, and the exact patch are retained in the
pass-4 cachetools audit artifacts. Historical audit text above is unchanged.
