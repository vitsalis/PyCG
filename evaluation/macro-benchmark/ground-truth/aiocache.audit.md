# aiocache: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [aiocache.md](aiocache.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release v0.12.3, commit `e673d62e98bf89b619e48f44cd68c96a30d95a1b`. Audited
files: `aiocache.ledger` (576 entries, 151 notes, 1 default rejection, 4
exclusions), `aiocache.json` (190 nodes, 568 edges: 259 in the package, 309
outside), `aiocache.rejected.json` (54 edges), `aiocache.md` (J1-J13).
`check.py --benchmark-dir macro-benchmark-heldout-2 aiocache` reports no
errors. The trace confirms 415 edges; 153 come from reading only.

I read the source, the docs, the examples and the tests as data. I did not
run the package and used no static analysis tool. I wrote my blind answers
before I opened the writer's files (evidence:
`$TMPDIR/heldout2-audit-aiocache/blind-answers.md`, with `sample.txt` and
`scripts/draw.py`).

**Result.** I found no missing edge and no edge that cannot happen. One
finding is doubtful and needs a ruling (F1, J4: -5 or -4 edges). The two
judgement calls that the writer marked for the lead (J2, J3) are, by the
nearest rules, correct as written (0 edges). One naming difference (N1) and
two remarks on the README (R1, R2) change no edge.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Recommendation |
|---|---|---|---|---|---|
| F1 | doubtful, needs a ruling (J4) | `factory.py` 34:21 `cache(serializer=..., plugins=..., **kwargs)` in the private `_create_cache`: the ledger has the `__init__` of all 7 caches | `cache` comes from an alias config. The config has no package annotation for it (`Dict[str, object]`, `factory.py:128, 138`; B2: `object` names no package value) and no `issubclass` check. The writer takes the role from other places: the check of another parameter (`Cache.__new__`, `factory.py:63`) and the annotation of another variable (`AIOCACHE_CACHES`, `__init__.py:11`). By B2 (annotation, documentation for that role, own code, tests and documented examples), the role has `SimpleMemoryCache` (default config `factory.py:130`; docstring `factory.py:210, 234`; tests `tests/ut/test_factory.py:152-331`; `examples/cached_alias_config.py:8`, which `docs/configuration.rst:15` includes) and `RedisCache` (docstring `factory.py:216`; tests `test_factory.py:188, 205, 235, 263, 341, 358`; example line 14). No document, test or example puts `MemcachedCache`, a `*Backend` class or `BaseCache` in a config. "You can set your own classes there" (`factory.py:241`) names client classes. The trace has only `SimpleMemoryCache.__init__`. | -5 (`BaseCache`, `SimpleMemoryBackend`, `MemcachedBackend`, `RedisBackend`, `MemcachedCache` `__init__`); -4 if `MemcachedCache` counts as documented for the role (it is one of the cache classes of `docs/caches.rst`) | Keep `SimpleMemoryCache.__init__` and `RedisCache.__init__`. `Cache.__new__` 68:26 keeps all 7: its `issubclass` check names `BaseCache` for that parameter (B2). |
| N1 | naming only | `memory.py` 38:50, 73:54 `loop.call_later(...)` | I named `asyncio.EventLoop.call_later` (the micro-benchmark's `async/call_soon_callback` uses `asyncio.EventLoop`); the writer names `asyncio.BaseEventLoop.call_later`. Both are aliases of the trace's `asyncio.base_events.BaseEventLoop.call_later`. `asyncio.EventLoop` exists only from Python 3.13, and the ground truth covers 3.7 on (J1). | 0 | Keep the writer's name. |

## Rulings on the writer's judgement calls

**J2, names of raw commands (marked for the lead).** Supported by B2 and
rule A. Keep as written; 0 edges change. The command string is a client
value. It selects a method of an object that the package makes (`dict`,
`aiomcache.Client`, `redis.asyncio.Redis`). B4 then fixes the class, and B2
gives the names in scope: those that the package, its tests and its
documented examples pass. I checked each citation: `tests/acceptance/test_base.py:160-163,
196-200, 237-242`, `tests/ut/backends/test_memory.py:167-168`,
`test_memcached.py:209-217`, `test_redis.py:223-225`,
`examples/serializer_class.py:42` (in `docs/serializers.rst:59`); the package
passes `"eval"` (`redis.py:118, 188`). Rule A also decides it for memory: the
trace has `SimpleMemoryBackend._raw -> dict.get, dict.keys, dict.setdefault`.
These callees are not client values, not implicit calls and not artefacts,
so rule A does not allow their rejection. The alternatives: "none" (B3
extended to outside methods) removes 10 edges (memory 3, memcached 3, redis
4; `Redis.eval` stays) and breaks rule A for 3 trace edges. Every method of
the class cannot be enumerated. If the lead counts `examples/` files that no
document includes as documented examples, `examples/simple_redis.py:15` adds
1 edge (`RedisBackend._raw -> redis.asyncio.Redis.ttl`).

**J3, `_Conn.__getattr__` runs the property `serializer` (marked for the
lead).** Supported by rule A and the anytree precedent. Keep; 0 edges change.
`tests/ut/test_base.py:614-617` loads `conn.serializer` on a `_Conn` whose
cache is a real `BaseCache` (`tests/ut/conftest.py:33-45`). The trace has
`_Conn.__getattr__ -> BaseCache.serializer`. The callee is a package
property. Rule A rejects a trace edge only for a client value, an implicit
call of outside code or a naming artefact, so the edge stays. The anytree
ruling (heldout `anytree.md`, J4) applied B3 by the names that the docs and
tests use; there none was a property. Here a test uses a property name. B3
read literally removes 1 edge and breaks rule A. Reading "any property" adds
1 (`-> BaseCache.plugins`), which no test or document loads through a `_Conn`.

**Other judgement calls.** I agree with J1 and J5-J13, each by the rule that
the writer names. J4 is F1. J5 (`tuple.index`) and J6 (`call_later`
callback) match the trace; J7 adds `ujson.dumps`/`ujson.loads` and two
`logger.debug` edges from reading, by the README default for optional
imports.

## Step 1: blind re-derivation

The skeleton without a ledger has 1187 sites: 627 getattr and 560 others.
Getattr dominates, so I drew by kind (README): from the report order, with
`rng = random.Random(20261111)`, `rng.sample(others, 50)` then
`rng.sample(getattr, 20)`, and added all 68 value sites. 7 value sites fell
in the draw: 131 sites.

| Group | Sites | Agree | Differ |
|---|---|---|---|
| Random, not getattr | 50 | 48 | 2 (73:54 N1; 34:21 F1) |
| Random getattr | 20 | 20 | 0 |
| Value sites outside the draw | 61 | 58 | 3 (J2) |
| **Total** | **131** | **126** | **5** |

The 5 differences, classified:

- **Naming only (1):** `memory.py` 73:54 (N1).
- **The auditor was wrong (3):** the three `_raw` value sites (J2). I left
  the client command names without callees. The writer's reading is the one
  that rules B2 and A support.
- **The writer has edges that the rules do not support (1, doubtful):**
  `factory.py` 34:21 (F1). My blind answer had 3 classes certain and 4
  conditional. After I read the docs and tests, B2 supports 2.
- **The writer missed an edge (0).**

All other answers were identical: the wrappers of the 11 commands (the
callee of `cache.get(...)` is `API.aiocache_enabled.enabled._enabled`), the
three `_build_key`, the six `dumps`/`loads`, the plugin hooks, the three
lambdas and their exclusions, `functools.partial.__call__`, and the default
rejection of `_Conn.__getattr__` at the 20 getattr sites.

## Step 2: exhaustive checks

1. **Dispatch sets.** Every site was checked against the class hierarchy.
   The 14 backend-method sites (11 in the commands, 3 in the locks) have 4
   callees each, and `self._close` has 3: `BaseCache` is a plain public
   class that the tests instantiate (B1). The 11
   `build_key` sites have 3, the 5 `dumps`/`loads` sites have 6, the hooks at
   `base.py:76, 82` have 1 and 4, and `_plugins`/`_timeout`/`_enabled` have
   11/2/1. Inside each backend, `self` is that backend or its `*Cache`
   subclass. The `cached`/`cached_stampede`/`multi_cached` sites are correct.
   No difference, apart from F1.
2. **Default rejection** (`--report --default`, 627 getattr sites). Only 6
   loads have a `_Conn` receiver, all inside `_Conn` methods, and they read
   `_cache` and `_conn`. `__init__` sets both (`base.py:531-533`). The 12
   explicit `getattr`/`hasattr` calls reject it each with the receiver type.
   The default is correct.
3. **Functions that no site calls.** 24 functions and 13 modules. Each is
   reached only by a client: the two `__repr__`, `API.unregister`, the
   `BaseCache` and `_Conn` context methods, `get_connection`,
   `_do_inject_conn`, `_Conn.__getattr__`, the decorators' `__call__` and
   `wrapper`, `multi_cached.__init__`, `cached_stampede.__init__`,
   `Cache.from_url`, `CacheHandler.add/create/set_config`, and the 4
   `OptimisticLock` methods. Each keeps the edges of its body (rule A).
4. **Special methods and properties.** The setters of `serializer` and
   `plugins` (`base.py:120, 123`), the 5 getter loads, the 11 `API.plugins`
   loads (the property is rejected: the receiver is the class `API`),
   `RedLock.__aenter__/__aexit__` at `decorators.py:222`, and
   `Cache.__new__` with no `__init__` after it. All correct.
5. **Rejections and notes.** I read all 167 rejection lines, 151 notes and 4
   exclusions. Every reason holds.
6. **Callees outside the package.** 121 names, 309 edges. Each is named by
   the rules or by a trace alias (`<builtin>.Exception.__init__` =
   `BaseException.__init__`, `pickle.dumps` = `_pickle.dumps`,
   `msgpack.dumps` = `msgpack.packb`). B4 and B5 are applied consistently:
   no outside edge rests on an opaque client value.
7. **Rejected trace edges (54).** 50 are mock calls. In each case a test
   replaced a package internal (`self.client`, `_cache`, `_serializer`,
   `RedLock`, `Cache`, a class `__init__`) or passed a mock. 3 are B5
   "dict-like" client objects (J8). 1 is the Cython naming artefact of
   `msgpack.loads`. All stay rejected.
8. **The 153 untraced edges.** 54 are in the redis and memcached modules:
   47 are calls of the client libraries, which the unit tests mock, and 2
   come from the uncovered `__repr__`. Most others are the
   dispatch over the 7 caches and 6 serializers, plus the except branches of
   optional imports, `ujson`, `warnings.warn`, the J2 commands and F1. Each
   one is possible, except the 5 of F1.

## Remarks on the README

- **R1 (B3 and rule A).** B3's sentence "an attribute name that the client
  supplies is not taken to name a package property" conflicts with rule A
  when a test loads a property through a forwarding `__getattr__` (J3).
  Suggested wording: "...unless the package's tests or documented examples
  use that name". Also, no rule covers a client string that selects a method
  of an object that the package makes (J2). Suggested rule: the callees are
  the names that the package, its tests and its documented examples pass.
  It is still unclear whether "documented examples" includes `examples/`
  files that no document includes (J2: `ttl`, +1 edge).
- **R2 (B4, annotations of stored values).** B4 speaks of a parameter's
  annotation. `CacheHandler._config: Dict[str, Dict[str, object]]`
  (`factory.py:128`) annotates the store that `set_config` fills, but the
  docstring of the parameter says "dict-like" (`factory.py:205`). The writer
  followed the parameter, and I agree. If the lead counts the store's
  annotation, `config.keys()` (`factory.py:251`) gets `<builtin>.dict.keys`:
  +1 edge, and 1 fewer rejected trace edge.

The tools worked as the brief says. A scratch directory with no
`ground-truth/` gave the skeleton and the list of value sites
(`check.py --report`).


## Fourth complete source-first audit (2026-11-16)

Read all 13 runtime modules and froze 177 function/lambda bodies and 1,714
source sites before baseline comparison. Reviewed all 565 baseline pairs,
576 ledger entries, 1,138 omitted sites, 30 zero-edge nodes, the default
rejection and all 5 exclusion lines. All graph pairs and 53 trace rejections
remain valid. No target or dependency code was executed.

One independent metadata correction clarifies J1: the current release CI
explicitly includes PyPy, and the normal/-O/-OO working scope union has no
extra edges because runtime code does not depend on assertions or docstrings.
Historical text above is preserved. Full pair/site/body coverage and the
source-freeze hashes accompany the round-4 audit evidence.
