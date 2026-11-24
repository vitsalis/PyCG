# aiocache: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 3 edges and adds 4. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 1 missed edge,
plus 1 correction to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/aiocache-review.json`).
The current ledger and statistics below include both audit passes.

The fourth source-first audit retains all 565 pairs on 190 nodes. It clarifies
J1 with current PyPy support and the normal/optimized configuration union.
This is one scope-metadata correction; no graph count changes.

Release v0.12.3 (commit `e673d62`). Analysed source: `aiocache/`: 13
modules, 177 functions (3 lambdas), 27 classes. `setup.py` has no
`python_requires`; its classifiers name Python 3.7 to 3.11, and the trace
ran on 3.14. The ground truth takes every version from 3.7 on (J1).

The ledger is `aiocache.ledger`; the graph `aiocache.json` is generated
from it. The rejected trace edges are in `aiocache.rejected.json`. The
independent audit is in `aiocache.audit.md`.

## Lead rulings after the audit

- **J2** (the command string of `raw`): kept as written (B2 with B4; rule A
  keeps the three dict trace edges). An `examples/` file that no document
  includes is not a documented example, so `Redis.ttl` stays out.
- **J3** (`_Conn.__getattr__ -> BaseCache.serializer`): kept (rule A, the
  trace edge on a real `BaseCache`; anytree J4). B3 gets "unless the tests
  or the documented examples use the name".
- **J4, audit F1** (`cache(...)` at `factory.py:34` in `_create_cache`):
  changed. The `issubclass` check of `Cache.__new__` belongs to another
  parameter and does not decide this role; B2 does. The callees are the
  `__init__` of `SimpleMemoryCache` and `RedisCache`. `MemcachedCache` is
  out: `docs/caches.rst:81-84` has it only as an `autoclass` entry, and no
  document, test or example puts it in a config. `BaseCache` and the three
  `*Backend` classes are out too (-5 edges, recorded as an exclusion).
  `Cache.__new__` at `factory.py:68` keeps all 7.
- **J6**: use `asyncio.SelectorEventLoop.call_later` and
  `asyncio.ProactorEventLoop.call_later`, the concrete public receivers.
  The global naming rule supersedes audit N1.
- **J8, audit R2** (`set_config`, "dict-like"): superseded by pass 2.
  The documented `get_config` output supplies a package-built dict for the
  same configuration input role, so `config.keys()` has `dict.keys`.
  Arbitrary client dict-like objects remain opaque.
- The serializer config role at `factory.py:24` does not admit
  `MsgPackSerializer`: no package call, test or documented example puts it
  in an alias config. Its use as a backend serializer is a separate role.
- J1, J5, J7 and J9 to J13: as written.

## Architecture, as the ledger uses it

- **Caches.** `BaseCache` (`base.py:90`) has the public commands and the
  backend methods `_add`, `_get`, ..., which raise `NotImplementedError`.
  `SimpleMemoryBackend`, `MemcachedBackend` and `RedisBackend` override the
  backend methods; `SimpleMemoryCache`, `MemcachedCache` and `RedisCache`
  add a default serializer, and the last two override `_build_key`. All
  seven classes are public, and `BaseCache` is a plain class: the tests
  instantiate it (`tests/ut/conftest.py:37, 50`).
- **Command wrappers.** Each of the 11 commands (`add`, `get`, `multi_get`,
  `set`, `multi_set`, `delete`, `exists`, `increment`, `expire`, `clear`,
  `raw`) has four decorators (`base.py:141-145`, ...). The class attribute
  `BaseCache.get` is the closure `API.aiocache_enabled.enabled._enabled`.
  `cache.get(...)` runs `_enabled`, then `API.timeout._timeout`, then
  `API.plugins._plugins`, then the method `BaseCache.get`. `close` has only
  `@API.timeout` (`base.py:484`). So a package call `cache.get(...)` has
  the callee `_enabled`, not `BaseCache.get` (J9).
- **Plugins.** `plugins.py:19-24` sets every `pre_<command>` and
  `post_<command>` of `BasePlugin` to `BasePlugin.do_nothing`;
  `plugins.py:57-60` sets every `post_<command>` of `TimingPlugin` to a
  `do_save_time` closure; `HitMissRatioPlugin` defines `post_get` and
  `post_multi_get`. `_plugins` looks the hooks up with `getattr` and calls
  them.
- **Connections.** `BaseCache.get_connection` returns a private `_Conn`.
  `base.py:560-561` adds a `_do_inject_conn` method to `_Conn` for each
  command; other attributes go through `_Conn.__getattr__` to the cache.
- **Factory.** `Cache(...)` runs `Cache.__new__`, which creates an instance
  of a cache class and calls its `__init__` itself; no `__init__` of `Cache`
  runs. `caches` (`factory.py:256`) is a `CacheHandler` that builds caches
  from alias configs (`_create_cache`).

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. `MemcachedCache.__repr__` and `RedisCache.__repr__` (`# pragma: no
cover`) never ran and keep their `str.format` edge.

**B1. Receivers.**
- `BaseCache` and `BaseSerializer` are plain public classes, so each is a
  receiver of its own methods (J10). The backend method sites in the
  commands (`self._add(...)` and so on) have four callees: the method of
  `BaseCache` and of the three backends. `self._close` has three: the memory
  backends inherit `BaseCache._close`.
- Inside a backend, `self` is that backend or its `*Cache` subclass:
  `self._get` in `SimpleMemoryBackend._gets` is only
  `SimpleMemoryBackend._get`, `self._cas` in `RedisBackend._set` only
  `RedisBackend._cas`, and so on.
- `self.decorator(...)` in `cached.__call__.wrapper` is `cached.decorator`
  or `cached_stampede.decorator` (which inherits `__call__`), not
  `multi_cached.decorator`.

**B2. Arguments and stored values.**
- `client` of `RedLock` and `OptimisticLock` is annotated `BaseCache`
  (`lock.py:65, 136`): any of the 7 caches.
- `serializer` is documented as an "obj derived from BaseSerializer"
  (`base.py:95`): the 6 serializers. `dumps(value)` and `loads(...)` in the
  commands call one of the six, or the client's `dumps_fn` / `loads_fn`.
- `self.build_key` is the client's `key_builder` or `self._build_key`
  (`base.py:117`): `BaseCache._build_key`, `MemcachedCache._build_key` or
  `RedisCache._build_key`.
- `skip_cache_func` and the `key_builder` of `multi_cached` default to the
  three lambdas (`decorators.py:70, 319, 328`). `cached.key_builder`
  defaults to `None`: that site has a note and no callee.
- Names that the client gives as strings: J2 and J3.

**B3. Not considered.** A cache passed as a value to store, as a key, or as
an argument of a decorated client function; a strategy or plugin object
passed where any object is accepted. This rejects the `__repr__` of
`MemcachedCache` and `RedisCache` at every `str()` and `str.format` site.

**B4. Concrete outside types.** The keys are documented as `str`
(`base.py:150`): `key.startswith` (`memory.py:84`) is
`<builtin>.str.startswith`. Redis returns `bytes` (`decode_responses=False`,
`redis.py:79`) and aiomcache returns `bytes`: `<builtin>.bytes.decode`.
`self.client` is the `aiomcache.Client` or `redis.asyncio.Redis` that the
backend creates; a client that replaces it changes package internals (not
considered).

**B5. Client objects are opaque.** The value that the client's function
returns to `multi_cached.decorator` ("dict-like", `decorators.py:253`), and
an arbitrary client config passed to `set_config` ("a dict-like structure",
`factory.py:205`) have no outside callee. The package-built dict returned by
`get_config` is admitted for this documented configuration role and gives
`dict.keys` (J8).

**C. "Public" is judged on the access path.** Public: everything under
`aiocache.base`, `aiocache.backends.*`, `aiocache.serializers`,
`aiocache.plugins`, `aiocache.lock`, `aiocache.decorators` and
`aiocache.factory` without an underscore. Private: `_Conn`, `_ensure_key`,
`_get_cache`, `_get_args_dict`, `_class_from_string`, `_create_cache`, and
the underscore methods.

## Judgement calls

1. **J1: supported versions.** No `python_requires`; the classifiers name
   3.7 to 3.11 (`setup.py:25-29`). The ground truth takes 3.7 and later.
   CPython is in scope. The pinned release also explicitly tests PyPy 3.8
   in `.github/workflows/ci.yml:56-59`, continuing the support announced in
   `CHANGES.rst:129`; no support drop is declared. PyPy is therefore also
   in scope under the applicable version bounds. Normal, `-O` and `-OO`
   execution are included as the round-4 working scope assumption, not as
   explicit user approval. The runtime has no assertions, `__debug__` tests
   or docstring-dependent execution, so these modes add no pairs.
   The package has no version branch and no `TYPE_CHECKING` block. The
   annotations that run before 3.14 (`base.py:20`, `__init__.py:11`,
   `factory.py:128`, `serializers.py:25`, `lock.py:63`) only subscript
   `typing` objects; no package code runs.
2. **J2: names of raw commands.** `getattr(client, command)(...)` in the
   three `_raw` methods (`memory.py:92`, `memcached.py:107`,
   `redis.py:179`) calls the method of the underlying client that the
   client's command string names. Global rule B2 explicitly limits a client
   string selecting an outside method to the names that the package's code,
   tests or documented examples pass. The callees are:
   memory `dict.get`, `dict.keys`, `dict.setdefault`
   (`tests/acceptance/test_base.py:161-163`); memcached
   `aiomcache.Client.get`, `.set`, `.prepend` (`test_base.py:197-200`);
   redis `redis.asyncio.Redis.eval` (the package, `redis.py:118, 188`),
   `.get`, `.set`, `.keys`, `.delete` (`test_base.py:238-242`; "get" also
   in `examples/serializer_class.py:42`, which `docs/serializers.rst:59`
   includes). `examples/simple_redis.py:15` passes `"ttl"`, but no document
   includes that example, so `Redis.ttl` is not a callee. The lead kept
   this reading (see "Lead rulings").
3. **J3: `_Conn.__getattr__` runs a property.**
   `self._cache.__getattribute__(name)` (`base.py:543`) runs the property
   that `name` selects. The name is the attribute that the client loads
   from the `_Conn`. B3 says that a client attribute name is not taken to
   name a package property, but the anytree ruling (J4 there) decided it by
   the names that the docs and tests use. The tests load `timeout`,
   `namespace` and `serializer` (`tests/ut/test_base.py:615-617`), so
   `BaseCache.serializer` is a callee and `BaseCache.plugins` is not. The
   trace confirms the edge. The lead kept it and adds the test-use clause
   to B3 (see "Lead rulings").
4. **J4: the cache classes of the factory** (changed by the lead's
   ruling). `Cache.__new__` checks `issubclass(cache_class, BaseCache)`
   (`factory.py:63`), which names `BaseCache` for that parameter (B2):
   `instance.__init__(**kwargs)` (`factory.py:68`) has the `__init__` of all
   7 caches. `_create_cache` (`factory.py:34`) has no annotation and no
   check, so B2 decides by the classes that the package, its tests and its
   documented examples put in a config: `SimpleMemoryCache` (default config
   `factory.py:130`; docstring `factory.py:210, 234`;
   `tests/ut/test_factory.py:152-331`; `examples/cached_alias_config.py:8`,
   included by `docs/configuration.rst:15`) and `RedisCache`
   (`factory.py:216`; `test_factory.py:188-358`; example line 14).
   `MemcachedCache` is in `docs/caches.rst:81-84` only as an `autoclass`
   entry, and the README (`README.rst:119, 125`) and the examples put only
   the other two in a config, so it is out. One `exclude` line records the
   five classes that are out. The trace has only `SimpleMemoryCache`.
5. **J5: `args_names.index(...)`** (`decorators.py:412`). `args_names` is a
   slice of `f.__code__.co_varnames`, always a tuple: the package reads the
   code object of the decorated function itself (lines 247, 408). The
   ledger names `<builtin>.tuple.index` (B4 by the concrete type), although
   `f` is a client object. The trace confirms it.
6. **J6: event loop callbacks.** `loop.call_later(ttl, self.__delete, key)`
   (`memory.py:38, 73`): the loop calls `__delete` later, so by the
   micro-benchmark rule "Callbacks" it belongs to the scope that runs the
   loop (the client), and is rejected at these sites. The trace agrees. The
   callees are `asyncio.SelectorEventLoop.call_later` and
   `asyncio.ProactorEventLoop.call_later`, named through the concrete public
   receiver on each supported platform. The trace has aliases for both.
7. **J7: optional imports.** Both sides run (README default):
   `redis` and `aiomcache` (`__init__.py:13-31`), `msgpack`
   (`serializers/__init__.py:14-21`, `serializers.py:13-17`), `ujson`
   (`serializers.py:7-11`). So `JsonSerializer.dumps` and `.loads` call
   `json.dumps` / `json.loads` or `ujson.dumps` / `ujson.loads` (the trace
   environment has no ujson), and the `logger.debug` lines of the except
   branches are edges.
8. **J8: abstract structures and package-owned configuration.** An arbitrary
   client "dict-like" config has no concrete outside class (B4, B5), but
   `get_config` returns a deepcopy of the package-built default dict
   (`factory.py:128-133`, `197-201`). The configuration documentation
   (`docs/configuration.rst:6-10`) and `set_config` docstring identify the
   same output/input role. Thus `h.set_config(h.get_config())` on a fresh
   `CacheHandler` calls `<builtin>.dict.keys` at `factory.py:251` (B2).
   This static witness needs no private state assignment or failed object.
   `plugin.pop("class")` (`factory.py:29`) stays opaque; the own default
   serializer config is a dict, so `serializer.pop` (`:22`) retains
   `<builtin>.dict.pop`. The client callback result of `multi_cached` is
   still abstract: `result.update` and `result.items()` (`decorators.py:387,
   389`) have no concrete outside callee. Those two trace edges remain
   rejected. The old audit R2 excluded `config.keys`; pass 2 supersedes it.
9. **J9: calls of commands name the wrapper.** At `self.cache.get(key)`,
   `self.client.set(...)`, `self.cache.multi_get(...)`, and so on
   (`decorators.py:157, 164, 421, 429`, `lock.py:160`), the callee is
   `API.aiocache_enabled.enabled._enabled`, and the candidate
   `BaseCache.<command>` is rejected. `self.close()` in `__aexit__`
   (`base.py:527`) is `API.timeout._timeout`. The trace confirms all of
   them.
10. **J10: `BaseCache` and `BaseSerializer` as receivers.** Both are plain
    public classes that the package documents for subclassing, not `abc`
    classes, so each is a receiver of its own methods (B1). This adds
    `BaseCache._add` and the other backend methods at the command sites, and
    `BaseSerializer.dumps` and `.loads` at the `dumps(...)` and `loads(...)`
    sites. These methods raise `NotImplementedError`.
11. **J11: `functools.wraps`.** The decorator sites `@functools.wraps(...)`
    (`base.py:43, 60, 72`, `decorators.py:107, 355`) have the callee
    `functools.partial.__call__` (tenacity precedent); `update_wrapper`
    calls no package code.
12. **J12: `super().__init__` of `BaseSerializer`** (`serializers.py:29`)
    reaches `object.__init__` for every package serializer:
    `<builtin>.object.__init__`, as the trace names it.
13. **J13: classes without `__init__`.** `InvalidCacheType` and
    `OptimisticLockError` give `<builtin>.Exception.__init__`; the plugin
    classes give no edge at `cls(**plugin)` (`factory.py:31`); the
    serializers without `__init__` give `BaseSerializer.__init__`.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `aiocache.base._Conn.__getattr__` | 627, all `getattr` sites | No package site loads a missing attribute from a `_Conn`: the receivers are caches, serializers, plugins, locks, decorators, outside clients, modules and client objects; the `_Conn` methods load only `_cache` and `_conn`, which `__init__` sets | nowhere |

The default decides only implicit sites. The 12 explicit sites where it
would apply (`getattr` and `hasattr` calls) each have their own rejection,
with the type of the receiver.

## Value sites

68 value sites. The hard ones:

| Site | Callees | Size |
|---|---|---|
| `base.py:47, 48` `func(self, ...)` in `_timeout` | `API.plugins._plugins`, `BaseCache.close` | 2 |
| `base.py:64` `func(...)` in `_enabled` | `API.timeout._timeout` | 1 |
| `base.py:78` `func(self, ...)` in `_plugins` | the 11 command methods | 11 |
| `base.py:76` `pre_` hook | `BasePlugin.do_nothing` | 1 |
| `base.py:82` `post_` hook | `do_nothing`, `do_save_time`, `post_get`, `post_multi_get` | 4 |
| `base.py:548` `getattr(self._cache, cmd_name)(...)` | `_enabled` | 1 |
| `self.build_key(...)`, 11 sites (`base.py`, `lock.py`) | the three `_build_key` | 3 |
| `dumps(value)`, `loads(...)`, 5 sites | the six `dumps` or `loads` | 6 |
| the three `_raw` calls | J2 | 3, 3, 5 |
| `factory.py:24` `cls(**serializer)` | `BaseSerializer.__init__`, `PickleSerializer.__init__` | 2 |
| `factory.py:34` `cache(...)` | `SimpleMemoryCache.__init__`, `RedisCache.__init__` (J4) | 2 |
| `factory.py:68` `instance.__init__(...)` | the `__init__` of the 7 caches (J4) | 7 |
| `redis.py:137` `exp(key, time=ttl)` | `Pipeline.pexpire`, `Pipeline.expire` | 2 |
| `redis.py:77` `connection_pool_class(...)` | `redis.asyncio.ConnectionPool` | 1 |
| `f(...)` (3), `cached.key_builder` (1), `factory.py:31` | none: client callbacks, or `object.__init__` | 0 |

## Exclusions

Four `exclude` lines record a lambda of the other decorator class at the
`skip_cache_func` and `key_builder` sites of `cached`, `cached_stampede` and
`multi_cached`: each default is set only on objects of its own class. A
fifth, at `factory.py:34`, records the `__init__` of `BaseCache`, the three
`*Backend` classes and `MemcachedCache`, which no config of the package,
its tests or its documented examples names (J4).

## Rejected trace edges (53)

- 50 calls of `unittest.mock.CallableMixin.__call__`: the tests replace
  package internals or arguments with mocks (`self.client` of the redis and
  memcached backends, the memory backend's `_cache`, the serializer, the
  plugin, the cache of the decorators, `RedLock`, `aiomcache.Client`,
  `redis.asyncio.Redis`, `Cache`, and an injected command `"dummy"`).
- 2 calls on client "dict-like" callback results in `multi_cached` (J8).
- 1 naming artefact: `msgpack.loads` is a Cython function, which the trace
  names `_cython_3_1_4.cython_function_or_method.__call__`.

## Functions that the tests do not run (4)

`MemcachedCache.__repr__`, `RedisCache.__repr__` (`# pragma: no cover`),
`BaseCache._gets`, `BaseCache._redlock_release`.

## Statistics

| | Count |
|---|---|
| All AST sites | 1,714: the 1,187 sites below plus 527 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 1187 (484 call, 68 decorator, 2 async-with, 627 getattr, 2 setattr, 4 format) |
| Sites with candidates / value sites | 892 / 68 |
| Ledger entries | 576 (484 call, 68 decorator, 16 getattr, 4 format, 2 async-with, 2 setattr) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 684 / 167 (100) / 5 / 151 |
| Default rejections | 1, deciding 627 sites, all implicit |
| Nodes | 190 |
| Edges | 565: 253 in the package, 312 outside |
| Graph edges with a trace name or alias | 416 of 565 (73.6%) |
| Edges only from reading | 149 |
| Trace edges rejected | 53 |
| Functions that the tests run | 173 of 177 |
