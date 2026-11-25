# django-constance: judgements of the ground truth

Release 4.5.0 (commit `1032c50`). Analysed source: `constance/` (root `.`):
26 modules, 157 functions (8 lambdas), 24 classes. `constance/test/` and
`constance/migrations/` are part of the package. `pyproject.toml` sets
`requires-python = ">=3.10"`; the classifiers name CPython only, and Django
4.2, 5.0, 5.1, 5.2, 6.0 and 6.1. The release declares no dependency (not even
Django); the extra `redis` adds redis, unpinned. Every module imports Django.

The ledger is `django-constance.ledger`; the graph `django-constance.json`
is generated from it. 10 trace edges are rejected in
`django-constance.rejected.json` (see "Rejected trace edges").

**Library sources.** Where the trace names a callee, the ledger uses that
name or one of its aliases. The ledger was first written from the writer's
knowledge of the library sources. Then the lead unpacked the pinned wheels of
the test environment (hash-checked against `requirements/django-constance.txt`,
text only, nothing installed or run) into
`deps/django-constance/` (the dependency sources of the audit records): Django 6.1.2, redis
8.1.0, asgiref 3.13.0, pytest-django 4.14.0, sqlparse 0.6.0 and tzdata
2026.5. The writer checked every name and library behaviour of judgement 9
against them. They were read as plain files, never imported or run.
Judgement 9 says which names were verified this way and which were not. No
name had to change.

## Audit and referee ruling (2026-11-22)

The blind audit is `django-constance.audit.md`. It re-derived 96 sites:
88 agree, 3 differ in naming only and 5 are auditor errors. It found no
edge that cannot happen, and all 283 site and package-callee pairs bind.
An independent referee ruled on the open cases
(`ruling-django-constance.md` in the audit records):
- J1, J2, J3 (R2) and J4 stand.
- R1: the package's own test settings count. This added 10 field edges
  and 6 SQLite edges (judgements 3 and 8), and 6 trace edges moved from
  rejected to accepted.
- N1: the stub paths of `django_redis.get_redis_connection` were added,
  +5 edges.
- J10: the `_backend` branches have no edges, -4 edges.

Graph: 660 edges before the ruling, 677 after (+21, -4).

## Architecture, as the ledger uses it

- `constance.config` (`__init__.py:11`) is a `LazyConfig`, a Django
  `LazyObject`. `utils.py:6`, `admin.py:29` and `forms.py:26` each make
  another `LazyConfig`. Each one makes its own `Config` in `_setup`, at the
  first attribute load, store, hash or other forwarded operation in the
  process.
- `Config` (`base.py:131`) stores its backend with `object.__setattr__`
  (`base.py:135`). A config name is no attribute of a `Config`, so a load
  runs `Config.__getattr__` and a store runs `Config.__setattr__`. The
  backend comes from `CONSTANCE_BACKEND`: `RedisBackend` (the default),
  `CachingRedisBackend`, `DatabaseBackend` or `MemoryBackend`. `Backend`
  (`backends/__init__.py`) is abstract by `abc`; each package backend
  overrides all six methods.
- `Config.__getattr__` returns an `AsyncValueProxy` (`base.py:159`) when
  asyncio detection is on (the default) and the thread has a running event
  loop. The proxy's dunder methods read the value synchronously, through
  `Config._get_sync_value`.
- `codecs.py` serialises values to JSON with the encoders and decoders that
  `_register_default_types` registers. The Redis and Database backends use
  it; the Memory backend stores the values themselves.
- The admin (`admin.py`) registers the pseudo model `Config` with
  `ConstanceAdmin` at import. The changelist view builds a `ConstanceForm`
  (`forms.py`), whose `save` writes the changed values to the config.
- `test/unittest.py` and `test/pytest.py` define two `override_config`
  helpers for clients' tests; `test/pytest.py` is also a pytest plugin.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules. This section
shows how the ledger applies them.

**A.** Every function keeps the out-edges of its body. The abstract methods
of `Backend`, `Encoder.__call__` and `Decoder.__call__` have bodies `...`.

**B1. Receivers.**
- `RedisBackend.set` (`redisd.py:89`): `self` is a `RedisBackend`, or a
  `CachingRedisBackend` through `super().set` (`redisd.py:165`). So
  `self.get(key)` has both `get` methods; the trace has both.
- `RedisBackend.aset` (`redisd.py:103`): `CachingRedisBackend` overrides
  `aset` and never calls `RedisBackend.aset` on itself, so `self.aget` is
  only `RedisBackend.aget`. In the same way `RedisBackend.mget` has only a
  `RedisBackend` as `self`.
- `Backend` is abstract by `abc`: its methods are no callees at the backend
  calls of `base.py` and `utils.py`.

**B2. Arguments and stored values.**
- `CONSTANCE_BACKEND` (`base.py:135:83`): the default and the three other
  documented backends (`docs/backends.rst:27, 33, 94, 162`). A client's own
  backend class is client code.
- `CONSTANCE_CONFIG` is a dict or an `OrderedDict` (`docs/index.rst:42,
  196`; `admin.py:174` tests it): its `items`, `keys` and `get` have both
  names. The fieldsets are a dict or a tuple (`docs/index.rst:216, 266`), and
  `admin.py:171` handles an `OrderedDict`: `.items()` after the `dict` check
  has both names.
- The encoders and decoders of `_codecs` are the six defaults of
  `codecs.py:93-98`. A client's `register_type` callbacks are client code.
- `dumps` and `loads` get the default `json.dumps`, `JSONEncoder` and
  `json.loads` at every package call. `json` calls back
  `JSONEncoder.default` and `object_hook`; the trace has both.

**B4. Concrete outside types.**
- The documented Redis connection is a redis client (`redis.Redis`,
  `redis.from_url`, or "a callable that returns a redis connection",
  `docs/backends.rst:68`): `self._rd.get` is `redis.Redis.get`, and so on;
  `self._ard` is a `redis.asyncio.Redis`.
- Django's request: `request.user` is the default `auth.User` or an
  `AnonymousUser`; `request.GET` is a `QueryDict`. pytest's hook arguments
  are a `pytest.Config` and a `pytest.Item`. The `parser` of
  `Command.add_arguments` is Django's `CommandParser` (the whitenoise ruling
  L1).

**B5. Client objects are opaque.** The client's test functions in
`override_config` (`unittest.py:38:43`, `47:37`), the signal receivers of
`config_updated`, and a client's own connection classes, caches and
database connections (judgements 3 and 8).

**C. Public.** The modules, classes and functions whose paths have no
underscore component are public. The private ones are `_as`,
`_register_default_types` and its lambdas, `_set_constance_value`,
`_migrate_from_old_table`, `_override_config` and the private methods
(`_get_value`, `_get_sync_value`, `_aset_internal`, `_check_async_support`,
`_get_async_lock`, `_has_expired`, `_cache_value`, `_aget_unlocked`,
`_log_config_change`). Rule A keeps their body edges; their inputs are what
the package's own calls (or, for `_migrate_from_old_table` and
`_override_config`, Django and pytest) pass. The dunder methods of `Config`
and `AsyncValueProxy` are public methods (dunder names are no underscore
components).

## Judgement calls

Each case is decided by the nearest rule; the lead may rule on them.

1. **Versions.** Python 3.10 and later (CPython). The admitted Django
   versions are those of the classifiers, 4.2 to 6.1, because the release
   declares no requirement. So both sides of `DJANGO_VERSION < (5, 2)`
   (`test/unittest.py:62-75`) run: the instance method `_pre_setup` and the
   classmethod of Django 5.2. For pytest and pluggy, which the package
   imports but does not declare, the names are those of the pinned test
   environment (pytest 9.2.0, pluggy 1.7.0: `pluggy._decorators`).
   **Dependencies without a bound** (the lead's ruling, Codex audit round
   1). pytest, pluggy and asgiref have no version constraint and no
   versioned support declaration in the release. Each is read at the audit
   pin only: pytest 9.2.0, pluggy 1.7.0, asgiref 3.13.0. No other release
   of them is considered. redis differs: the extra `redis` is a declared
   requirement without a bound, so every release that runs on CPython 3.10
   or later is admitted (README, batch 7, "Which releases of a dependency
   are admitted"), read by batch 8's sampling rule (see "Corrections of
   2026-11-25"). asgiref 3.13.0 needs Python 3.11 or later, so its
   Python 3.11 branch counts (`asyncio.coroutines.iscoroutinefunction`,
   `test/unittest.py:32:31`). The Python 3.10 case would need an older
   asgiref and is not considered.
2. **Where an `AsyncValueProxy` reaches package code.** The documentation
   says that synchronous access inside async code "still works", with a
   `RuntimeWarning`, and it names test runners that keep a background event
   loop running during synchronous tests (`docs/index.rst:317-327`). So in
   a fresh process a package function that reads `getattr(config, name)`
   can run in a thread with a running loop and get a proxy:
   - `localize(value) != localize(default)` (`admin.py:74:41`) and
     `current != new` (`forms.py:148:24`) run `AsyncValueProxy.__ne__`
     (the proxy is the left operand; `localize` returns it unchanged);
   - `str(getattr(config, key))` (`management/commands/constance.py:56:38`)
     runs `AsyncValueProxy.__str__`.

   **Stored proxy.** Both `override_config.enable` methods keep the value
   that `getattr` returns, and `disable` stores it back with `setattr`
   (`test/pytest.py:43, 49`; `test/unittest.py:90, 103`). Under a running
   loop that value is a proxy, and the Memory backend (documented for tests,
   `docs/testing.rst:118-129`) stores the object itself. Later loads return
   that proxy: from `MemoryBackend.get`, `mget`, `aget`, `amget`. So:
   - each dunder method of `AsyncValueProxy` can get a proxy from
     `self._get_sync_value()` and calls the same method of it (29 self
     edges; the inner proxy returns itself, so the recursion ends in
     `RecursionError`, after the calls);
   - `smart_bytes(initial.get(name, ""))` (`forms.py:124:44`) runs
     `__str__` through `force_bytes`;
   - `f"{k}\t{v}"` (`management/commands/constance.py:71:42`) runs
     `__str__` through `object.__format__`.

   The Redis and Database backends do not store a proxy: `dumps` raises
   `TypeError` in `JSONEncoder.default` first. If the lead rules the stored
   proxy out, the edges to remove are the 29 self edges, `__rmod__ -> __str__,
   __repr__, __int__, __float__, __index__, __getitem__`, `ConstanceForm.__init__
   -> __str__` and `Command.handle`'s `{v}` part (the edge stays through
   56:38).
3. **Classes and callables that the client's settings name.** The package
   resolves them itself (`import_string`, `import_module_attr`), or Django
   picks them (`caches[...]`). The writer applied the nearest ruling
   (whitenoise L2): the library's defaults and the configurations that the
   package documents are in scope, and any other configured class is client
   code. The referee kept that rule whoever resolves the name (ruling R2;
   README "Configured implementations"). It added that the package's own
   test settings count as configurations (ruling R1; README "Test
   configurations", after jsonpickle's tested backend):
   - `CONSTANCE_ADDITIONAL_FIELDS`. The documented field classes are
     `ChoiceField`, `ImageField` and `JSONField`, and the documented widgets
     `Select` and `Textarea` (`docs/index.rst:131-182`). The package's own
     tests add `EmailField` and `CharField` (`tests/settings.py:61-63`),
     and `TypedMultipleChoiceField` with `CheckboxSelectMultiple`
     (`tests/test_admin.py:279-290`, a replacement setting that the
     settings interface could also supply). They are callees at
     `forms.py:63:39` and `122:44`. Their `prepare_value` is a callee at
     `admin.py:83:64` and `86:67` (`CharField` too, as an additional field),
     and their `to_python` and `clean` at
     `management/commands/constance.py:24`. With R1, 10 edges were added,
     and 3 trace edges moved from rejected to accepted.
   - `CONSTANCE_REDIS_CONNECTION_CLASS`. Two values are documented. A
     project's own mock-up is client code, as are the tests' mock-ups.
     `django_redis.get_redis_connection` is a module that the environment
     lacks, so it is named as a missing module (`redisd.py:24:64`,
     `0003_drop_pickle.py:48:53`). Its result is a stub value, whose
     `get`, `mget` and `set` keep the factory's access path, beside
     `redis.Redis.*` of the default branches (ruling N1; "a redis
     connection" fixes no class under B4). This added 5 edges. The async
     connection class has no documented value, so it has no callee.
   - The cache of `CONSTANCE_DATABASE_CACHE_BACKEND`. Django's default
     `LocMemCache` is refused (`database.py:35`). The documented
     `MemcachedCache` (`docs/backends.rst:126`) does not exist in any
     admitted Django (judgement 9). The tests' cache is their own mock-up
     class. So the cache is always client code: its methods and results
     have no callee, and the six trace edges of the mock-up stay rejected.
   - Django's default storage is `FileSystemStorage` (`forms.py:135:65`).
4. **The `LazyConfig` that the backends pass as the signal sender.** The
   four `config_updated.send(sender=config, ...)` sites pass
   `constance.config`. With a connected receiver (the documented
   `@receiver(config_updated)`, `docs/index.rst:80`), Django's
   `Signal.send` hashes the sender (`sender_receivers_cache.get`) and
   `_live_receivers` runs `_make_id(sender)`, which calls
   `hasattr(sender, "__func__")`. On the `LazyConfig` this runs
   `LazyConfig._setup` if `constance.config` was never used in the process
   (the backend can be reached through another `LazyConfig`), and the
   forwarded load of `__func__` runs `Config.__getattr__`, which raises
   `AttributeError`. So the send sites have `_setup` and
   `Config.__getattr__` (callback through library code, the fresh-process
   rule). The tests connect no receiver, so the trace has neither.
5. **`post_save` receivers.** `DatabaseBackend.__init__` connects its
   bound `clear` for the `Constance` model (`database.py:44`). The callee
   is placed where the package saves a `Constance`: `queryset.create`
   (`145:36`) and `constance.save` (`154:27`); the trace has
   `set -> clear`. The migration 0003 saves objects of the historical model,
   whose sender differs: no edge.
6. **Callbacks through Django.** `AdminSite.register` instantiates
   `ConstanceAdmin` (`admin.py:285`). `has_view_or_change_permission`
   calls the `has_view_permission` and `has_change_permission` overrides
   (`admin.py:108`, `181`). `each_context` calls the four
   `has_*_permission` overrides through `get_app_list` and
   `get_model_perms` (`admin.py:123`, `200`). `form.is_valid()` calls
   `clean_version` and `clean` (`admin.py:115`). `with self` in the
   synchronous `inner` (`test/unittest.py:46`) runs Django's
   `TestContextDecorator.__enter__` and `__exit__`, which call the
   package's `enable` and `disable`. The trace has all of these except the
   last, which the merged trace of the two `inner` closures cannot tell
   apart.
7. **`sync_to_async`.** `sync_to_async(f)` only wraps `f`; awaiting the
   wrapper's call runs `f` in asgiref's thread. The ledger puts `f` at the
   call of the wrapper (`database.py:97:74`, `168:68`;
   `test/unittest.py:37:76`, `40:77`) and rejects it at the wrapping call.
   The edge is the same either way.
8. **The database connection of migration 0002.**
   `schema_editor.connection` is the connection of the `DATABASES`
   setting. Django has no default engine (`DATABASES = {}`), and the
   package documents none. Its own test settings select SQLite
   (`tests/settings.py:21-30`), which counts (judgement 3, ruling R1).
   So the ledger names:
   - `quote_name` (`15:57`) and `sequence_reset_sql` (`28:53`, inherited
     from `BaseDatabaseOperations` and returning `[]`) of
     `django.db.backends.sqlite3.operations.DatabaseOperations`;
   - `cursor` of `django.db.backends.sqlite3.base.DatabaseWrapper`
     (`17:27`, `29:27`);
   - `table_names` of
     `django.db.backends.sqlite3.introspection.DatabaseIntrospection`
     (`18:70`);
   - `execute` of `CursorWrapper` and of `CursorDebugWrapper` (`21:23`,
     `25:23`). Django's default `DEBUG=False` gives the first and the tests'
     `DEBUG=True` the second (`queries_logged`, `_prepare_cursor`).

   `31:27` has no callee, because `sequence_sql` is empty. Another
   configured backend is client code. This added 6 edges, and 3 trace
   edges moved from rejected to accepted. `apps` is Django's documented
   app registry: `Apps.get_model`.
9. **Names that the trace does not confirm, and the library behaviour
   that the callbacks rest on.** Each one was first written from memory.
   It was then checked against the unpacked pinned sources (see "Library
   sources"), file and line given.
   - **Verified, redis 8.1.0:** `redis.from_url` (`redis/__init__.py:57`,
     in `__all__`; `redis/utils.py:52` returns `redis.client.Redis`);
     `redis.Redis` (`redis/__init__.py:3`, `client.py:156`) with `get`,
     `mget` and `set` from `CoreCommands` (`commands/core.py:3194`, `3751`,
     `4292`); `redis.asyncio.from_url` (`asyncio/__init__.py:21`,
     `asyncio/utils.py:7`) and `redis.asyncio.Redis` (`asyncio/client.py:136`,
     with `AsyncCoreCommands`).
   - **Verified, Django 6.1.2:** `add_message` and `warning` in
     `contrib/messages/api.py:22`, `108` (listed in its `__all__`;
     `contrib/messages/__init__.py` re-exports with `*` and has no
     `__all__`, so they are named where they are defined);
     `FileSystemStorage.save`, inherited from `Storage.save`
     (`core/files/storage/base.py:24`). `STORAGES` defaults to
     `FileSystemStorage` (`conf/global_settings.py:285`), `CACHES` to
     `LocMemCache` (`522`) and `DATABASES` to `{}` (`185`).
     `core/cache/backends/memcached.py` has no `MemcachedCache`
     (judgement 3). `AnonymousUser.has_perm` is at
     `contrib/auth/models.py:605` and `PermissionsMixin.has_perm` at `389`.
     All the field classes and the overrides of `prepare_value`, `to_python`
     and `clean` are in `forms/fields.py:179-1387`, and `django.forms`
     re-exports `ImageField`, `Select` and `Textarea`. `SimpleTestCase` has
     `_pre_setup` (a classmethod, `test/testcases.py:380`) and
     `_post_teardown` (`390`), and `TransactionTestCase` has both (`1146`,
     `1235`). `no_style` is `@functools.cache`
     (`core/management/color.py:106`). The per-method `__wrapper__` of
     `lazy` is at `utils/functional.py:184`. `normalize_newlines` is
     `@keep_lazy_text` (`utils/text.py:307`). `csrf_protect_m =
     method_decorator(csrf_protect)` (`contrib/admin/options.py:177`).
     `path = partial(_path, ...)` (`urls/conf.py:95`).
     `checks.register = registry.register`, a `CheckRegistry` method
     (`core/checks/registry.py:126`). The receivers of `get_model_perms`
     are at `contrib/admin/options.py:838-841`.
   - **Verified, the behaviour of judgements 4 to 6:** `Signal.send` tests
     `sender_receivers_cache.get(sender)`, a dict unless `use_caching`, and
     calls `_live_receivers`, which runs `_make_id(sender)`, and so
     `hasattr(target, "__func__")` (`dispatch/dispatcher.py:15-18`, `99`,
     `242-247`, `494`). `LazyObject.__getattr__ = new_method_proxy(getattr)`,
     `__hash__ = new_method_proxy(hash)`, and `__setattr__` runs `_setup`
     (`utils/functional.py:248-364`). `each_context` builds
     `available_apps` with `get_app_list` (`contrib/admin/sites.py:345`),
     and `_build_app_dict` calls `has_module_permission` and
     `get_model_perms` and reads only plain `_meta` attributes (`486-503`).
     `has_view_or_change_permission` is at `contrib/admin/options.py:670`.
     `AdminSite.register` reads `abstract`, `is_composite_pk` and `swapped`
     and calls `admin_class(model, self)` (`sites.py:113-149`).
     `admin_view` only wraps the view (`211-258`). `ModelAdmin.__init__` is
     at `options.py:739`. `_clean_fields` calls `clean_<name>` and
     `_clean_form` calls `clean` (`forms/forms.py:341-354`).
     `TestContextDecorator.__enter__` and `__exit__` call `enable` and
     `disable` (`test/utils.py:432-436`). `force_bytes` returns
     `str(s).encode(...)` (`utils/encoding.py:104`). `localize` returns
     other values unchanged (`utils/formats.py:201-215`). `QuerySet.create`
     calls `obj.save(force_insert=True)` (`db/models/query.py:752`), and
     `Model.save` sends `post_save` (`db/models/base.py:1011`).
     `ContentTypeManager.get_for_model` reads `_meta.concrete_model`
     (`contrib/contenttypes/models.py:26-29`). `Options.app_config` is a
     property (`db/models/options.py:181`).
   - **Verified, asgiref 3.13.0:** `iscoroutinefunction` is
     `inspect.iscoroutinefunction` where `inspect` has
     `markcoroutinefunction`, else `asyncio.iscoroutinefunction`
     (`sync.py:60-64`). `sync_to_async` is a function that returns a
     `SyncToAsync` (`681-716`). `SyncToAsync.__call__` is a coroutine
     method (`502`). It picks a single-thread executor for
     `thread_sensitive` (`508-531`) and runs the wrapped function there
     through `run_in_executor` and `thread_handler`, which calls
     `func(*args, **kwargs)` (`551`, `567`, `614-635`). This is
     judgement 7.
   - **Verified, the classes that the ledger names at the value sites:**
     `TextInput`, `Textarea` and `Select` (`forms/widgets.py:433`, `647`,
     `869`); the field classes (`forms/fields.py`, as above);
     `FileSystemStorage` (`core/files/storage/filesystem.py:19`);
     `Apps.get_model` (`apps/registry.py:188`); `LogEntryManager`
     (`contrib/admin/models.py:24`, `85`). Every method is named by the
     public path of the receiver's class (micro-benchmark rule "Methods"),
     or through the class that the package names for an inherited method
     ("Inherited methods").
   - **Verified, pluggy 1.7.0:** `pluggy.HookimplMarker` is public
     (`pluggy/__init__.py:19`, through `_hooks.py:20`) and defined in
     `_decorators.py:117`; its `__call__` returns the local
     `setattr_hookimpl_opts` (`215-230`). `pytest.hookimpl` is
     `HookimplMarker("pytest")` (pytest `_pytest/config/__init__.py:103`).
   - **Verified, pytest 9.2.0:** `pytest.fixture` is the plain function
     `_pytest.fixtures.fixture` (`fixtures.py:1539`; re-exported at
     `pytest/__init__.py:27`). It returns a `FixtureFunctionMarker`
     (`1609-1611`), a class with no public path, whose `__call__`
     (`1434`) the decorator runs. `Config.addinivalue_line` is at
     `config/__init__.py:1854` (`pytest.Config`, `pytest/__init__.py:15`).
     `get_closest_marker` is defined on `Node` (`nodes.py:379`) and named
     through the documented hook type `pytest.Item` (`nodes.py:680`,
     `pytest/__init__.py:50`). **Renamed:** `pytest.fail` is no function in
     9.2.0. It is the instance `fail: _Fail = _Fail()`
     (`outcomes.py:165`), so the callee is
     `_pytest.outcomes._Fail.__call__` (`outcomes.py:160`, rule "Calls of
     instances"). pytest is not declared, so other pytest versions are not
     considered (judgement 1).
   - **Verified across the admitted Django releases.** The lead supplied
     the text sources of Django 4.2.30, 5.0.14, 5.1.15, 5.2.19 and 6.0.10
     beside 6.1.2. Each is the last release of its family that the
     classifiers name. They were read as files, never imported or run.
     - The lazy-string wrapper at `admin.py:201:95`. In 4.2 the per-method
       wrapper is `__proxy__.__promise__`'s local `__wrapper__`
       (`utils/functional.py:144-152`), so its name is
       `django.utils.functional.lazy.__proxy__.__promise__.__wrapper__`.
       From 5.0 to 6.1 it is lazy's local `__wrapper__` (line 184 in each).
       The ledger keeps both names: two runtimes, one name each.
     - `MemcachedCache`. No release from 4.2 to 6.1 has it:
       `core/cache/backends/memcached.py` defines only
       `BaseMemcachedCache`, `PyLibMCCache` and `PyMemcacheCache`.
     - `_pre_setup`. It is an instance method of `SimpleTestCase` and
       `TransactionTestCase` in 4.2, 5.0 and 5.1, and a classmethod from 5.2
       (`test/testcases.py`). `_post_teardown` is an instance method in every
       release. The names are the same, and both sides of
       `DJANGO_VERSION < (5, 2)` bind (judgement 1).
     - `Signal.send`. Every release hashes the sender in a dict
       `sender_receivers_cache` (unless `use_caching`), and its
       `_live_receivers` calls `_make_id`, which runs
       `hasattr(target, "__func__")` (4.2 `dispatch/dispatcher.py:10-11`,
       `44`, `172`, `251`; the same in 5.0 to 6.0). In every release
       `LazyObject` has `__getattr__ = new_method_proxy(getattr)` and
       `__hash__ = new_method_proxy(hash)`. So judgement 4 holds across the
       range.
     - `each_context`. In every release it builds `available_apps` with
       `get_app_list`, whose `_build_app_dict` calls
       `has_module_permission` and `get_model_perms`. `get_model_perms`
       calls the four `has_*_permission` methods, and
       `has_view_or_change_permission` is in `BaseModelAdmin` (judgement 6).
     - Every other outside class and method that the ledger names has the
       same defining class in all six releases (checked with `ast` on the
       files). Among them are `FileSystemStorage`, `Storage.save`, the
       field classes with the `prepare_value`, `to_python` and `clean` they
       define or inherit, and the widgets `Select`, `Textarea`, `TextInput`
       and `CheckboxSelectMultiple`. Also `CommandParser.add_subparsers`,
       `QuerySet.afirst` and `only`, `get_elided_page_range`,
       `ModelSignal.connect`, `TestContextDecorator.__enter__`,
       `override_settings.__init__`, `Apps.get_model` and `get_app_config`,
       and both `has_perm` methods. And `smart_bytes`, `localize`,
       `make_aware`, `import_string`, `atomic`, `OutputWrapper.write`,
       `MultiValueDict.get` and `CheckRegistry.register`.
     - The R1 SQLite names, in every release: SQLite's
       `DatabaseOperations` defines `quote_name` and inherits
       `sequence_reset_sql`. `DatabaseWrapper` and `DatabaseIntrospection`
       inherit `cursor` (an `async_unsafe` method of
       `BaseDatabaseWrapper`) and `table_names`. `CursorWrapper.execute`
       and `CursorDebugWrapper.execute` exist, and `_prepare_cursor`
       chooses by `queries_logged`.
     - `no_style` is `@functools.lru_cache(maxsize=None)` in 4.2 and
       `@functools.cache` from 5.0: one `_lru_cache_wrapper`.
       `normalize_newlines` is `@keep_lazy_text`, `csrf_protect_m =
       method_decorator(csrf_protect)` and `path` a `partial` in every
       release.

     No name changed between the releases except the lazy wrapper, which
     the ledger already named for both.
   - **Not verified, and not considered.** asgiref was read only at the
     pinned 3.13.0, and pytest and pluggy at 9.2.0 and 1.7.0. The package
     does not declare them, so their other releases are not considered
     (judgement 1, the lead's ruling). The redis releases that the extra
     admits are read in "Corrections of 2026-11-25". The
     Python 3.11 branch of asgiref's `iscoroutinefunction` is named
     `asyncio.coroutines.iscoroutinefunction`. That is read in CPython
     3.12's `asyncio/coroutines.py:1`, `20` (no 3.11 source is on disk).
     Its new `inspect.markcoroutinefunction` (`inspect.py:418`) is the test
     that asgiref makes.
10. **Direct calls of public dunder methods.** The writer kept the
    `key == "_backend"` branches of `Config.__getattr__` (`base.py:146`) and
    `Config.__setattr__` (`164`): a client could call the public dunder
    directly with that key. The referee ruled against it (README "Attribute
    hooks and private names"). Normal lookup always finds `_backend`, and
    `Config.__init__` stores it with `object.__setattr__`. A direct hook call
    with a private name is no admitted use. So the four sites `146:25`,
    `146:44`, `164:18` and `164:32` have no edges (-4). The restriction
    concerns attribute hooks only: the six `__rmod__` formatting edges keep
    their witness, a client str passed to the public `__rmod__` over a
    stored proxy (judgement 2, `base.py:122:22`).

Other decisions:
- An `AnonymousUser` can reach `admin.py:113` and `forms.py:83`. The
  writer first excluded it at `admin.py:113`, because Django's own backend
  never grants an anonymous permission. But with `CONSTANCE_SUPERUSER_ONLY`
  false, a configured client authentication backend can grant one:
  `AnonymousUser.has_perm` asks the backends through `_user_has_perm`. The
  backend stays opaque, and its effect on control flow counts (Codex audit
  round 2).
- Optional imports (`redisd.py:26-49`): both sides run. `redis` is
  installed, so its callees are named normally, not as missing modules.
- `codecs.py` and `checks.py` have `from __future__ import annotations`:
  no annotation is a site. The other annotations hold no calls.
- `threading.Lock` is named as imported (the precedent of Sublist3r);
  `hashlib.sha256` objects have three receivers, `_hashlib.HASH`, and the
  builtin fallback per runtime (see "Corrections of 2026-11-25").

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `Config.__getattr__` | 698 | the receiver is no `Config` that lacks the attribute | the five `getattr(config, ...)` calls and the four `config_updated.send` sites |
| `Config.__setattr__` | 39 | the store target is no `Config` | the five `setattr(config, ...)` calls and `base.py:141:20` |
| 26 dunder methods of `AsyncValueProxy` | 1001 in all | no proxy is the operand | judgement 2 sites: the proxy's own methods, `admin.py:74:41`, `forms.py:124:44`, `148:24`, `management/commands/constance.py:56:38`, `71:42` |
| `Constance.__str__` | 46 | no package code formats a `Constance` | nowhere |

## Value sites

28 sites, each with a note in the ledger.

| Site | Callees | Where the values come from |
|---|---|---|
| `admin.py:112:24`, `114:28` `form_cls(...)` | `ConstanceForm.__init__` | `get_changelist_form` returns `change_list_form` |
| `base.py:135:83` backend class | the four backends' `__init__` | `CONSTANCE_BACKEND` (B2) |
| `codecs.py:26:50` `encoder(o)` | `datetime.isoformat`, lambdas 1, 3, 4, 5, `str` | `_codecs` defaults |
| `codecs.py:62:24` `codec[1](...)` | `datetime.fromisoformat`, lambdas 2, 6, `time.fromisoformat`, `Decimal`, `UUID` | `_codecs` defaults |
| `codecs.py:38:18` `_dumps(...)` | `json.dumps`, `JSONEncoder.default` | default argument |
| `codecs.py:46:22`, `51:18` `_loads(...)` | `json.loads`, `object_hook` | default argument |
| `forms.py:63:39` `klass(...)` | `Select`, `Textarea`, `CheckboxSelectMultiple` | judgement 3 |
| `forms.py:122:44` `field_class(...)` | 9 classes of `FIELDS`, `ChoiceField`, `ImageField`, `JSONField`, `EmailField`, `TypedMultipleChoiceField` | judgement 3 |
| `redisd.py:24:64`, `0003_drop_pickle.py:48:53` | `django_redis.get_redis_connection` | judgement 3 |
| `redisd.py:37:71` | none | judgement 3 |
| `database.py:97:74`, `168:68`; `unittest.py:37:76`, `40:77` | `SyncToAsync.__call__` and the wrapped method | judgement 7 |
| `database.py:144:40` `transaction.atomic` | `django.db.transaction.atomic` | the name is also a class attribute of migration 0002 |
| `unittest.py:38:43`, `47:37` `test_func(...)` | none | the client's test (B5) |
| `unittest.py:66:35`, `75:35`, `78:35` | `SimpleTestCase` and `TransactionTestCase` methods, and the package's own `_pre_setup` (`66:35`, `75:35`) and `_post_teardown` (`78:35`) | the decorated class (judgement 9), or the wrapper that an earlier decoration installed (Codex audit round 1) |
| decorators `pytest.py:14:2`, `20:2`, `62:2`; `unittest.py:34:14`, `44:14` | the decorator objects | `pytest.hookimpl`, `pytest.fixture`, `functools.wraps` |

## Rejected trace edges

| Caller | Callee | Why |
|---|---|---|
| `ConstanceAdmin.changelist_view` | `unittest.mock.CallableMixin.__call__` | the tests' mock of `messages.add_message` |
| `ConstanceForm.__init__` | `unittest.mock.CallableMixin.__call__` | the tests' mock of `messages.warning` |
| `RedisBackend.__init__` | `unittest.mock.CallableMixin.__call__` | the `MagicMock` that the tests put in `sys.modules` for redis |
| `RedisBackend.set` | `unittest.mock.CallableMixin.__call__` | the tests' `MagicMock` for the mock-up connection's `set` |
| `DatabaseBackend.autofill`, `.get`, `.set`, `.clear`, `.amget` | `LocMemCache.get`, `.set`, `BaseCache.set_many`, `.delete_many`; `dict.items` | the tests' cache mock-up (judgement 3) |

## Functions that no site calls

- Called by Django, pytest or clients: the module bodies; the admin's
  views, `get_urls` and its lambda; `ConstanceConfig.ready`;
  `check_fieldsets`; `context_processors.config`; `Command.add_arguments`
  and `handle`; the migration functions and the lambda; the pytest hooks
  and the fixture; `unittest.override_config.__init__`, `__call__` and
  `inner`; `AsyncValueProxy.__await__`;
  `Config.__dir__`; the `Config.Meta` properties `label` and `label_lower`,
  which Django reads in the tests; `utils.aget_values`, `aget_values_for_keys` and
  `get_values_for_keys`.
- Never run: `Config.Meta.get_change_permission` and `get_ordered_objects`
  (no admitted Django version calls them);
  the abstract `Backend` methods; `Encoder.__call__` and
  `Decoder.__call__` (protocol stubs); `Constance.__str__`.
- `modify_test_case._pre_setup` and `_post_teardown` are called by
  Django, and also by themselves: a later decoration calls the wrapper
  that an earlier one installed (`unittest.py:66`, `75`, `78`).
- 144 of the 157 functions ran in the tests.

## Statistics

| | Count |
|---|---|
| Sites | 1745 (595 call, 17 decorator, 11 with, 73 iter, 22 mapping, 26 await, 73 op, 63 getitem, 27 setitem, 1 delitem, 675 getattr, 37 setattr, 86 truth, 39 format) |
| Sites with candidates / value sites | 1416 / 28 |
| Ledger entries | 652 (595 call, 17 decorator, 11 with, 21 op, 6 getattr, 1 getitem, 1 format) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 810 / 195 (66) / 0 / 182 |
| Default rejections | 4 lines, 29 candidates, 1784 candidate-site pairs |
| Nodes | 183 |
| Edges | 680: 256 in the package, 424 outside |
| Edges that the trace confirms | 497 of 680 (73.1%) |
| Edges only from reading | 183 (77 in the package, 106 outside) |
| Trace edges rejected | 10 (of 499) |
| Functions that the tests run | 144 of 157 |

## Codex audit round 1

The audit is `audit-t6-r1/django-constance.md` (an audit record). Edges went
from 677 (255 inside, 422 outside) to 679 (256 inside, 423 outside).

- **Missing 1** (`modify_test_case._pre_setup -> _pre_setup`,
  `test/unittest.py:66:35`, `75:35`): applied. A class decorated twice, or a
  decorated subclass of a decorated class, captures the package's own
  wrapper at line 59, and the call binds in both Django branches.
- **Missing 2** (`modify_test_case._post_teardown -> _post_teardown`,
  `78:35`): applied, for the same reason.
- **Missing 3** (`override_config.__call__ ->
  asyncio.coroutines.iscoroutinefunction`, `32:31`): applied. The package
  admits Python 3.10 and later. asgiref 3.13.0 needs 3.11 or later and
  selects `asyncio.iscoroutinefunction` before Python 3.12
  (`asgiref/sync.py:60-64`), which is defined in `asyncio/coroutines.py`.
  Python 3.10 would need an older asgiref, which is not considered
  (judgement 1).
- **False 1** (`pytest.override_config.disable -> LazyConfig._setup`,
  `test/pytest.py:49:20`): applied, -1 edge. `_original_values` is filled
  only after `enable`'s `getattr` has set up `constance.config`.
- **Naming 1** (`django.get_version` -> `django.utils.version.get_version`,
  `admin.py:132:42`): applied. `django/__init__.py:1` re-exports the
  function without an `__all__`, so the README's re-export rule names it
  where it is defined. The other names that the ledger takes from a
  re-exporting module were checked:
  - the functions have an `__all__` that lists them (`pytest`, `redis`,
    `redis.asyncio`, `hashlib`, `warnings`, `asyncio`, `pickle`,
    `threading`) or are defined where the ledger names them;
  - the classes (`django.dispatch.Signal`, `django.forms.*`) follow the
    class rule "public import path of the class".
- **Naming 2** (`asgiref.sync.iscoroutinefunction` ->
  `inspect.iscoroutinefunction`, `32:31`): applied. `asgiref/sync.py` has
  no `__all__` and assigns the `inspect` function (`sync.py:60-61`).
- **Ruling** (dependencies with no bound): the lead ruled that they are read
  at the audit pin only, for pytest, pluggy, asgiref and redis.
  Judgement 1 now records it.
- **Unsure 1** (other redis releases): decided by that ruling; only redis
  8.1.0 is considered. No edge changed.
- **Unsure 2** (the names of the captured Django test hooks, `66:35`,
  `75:35`, `78:35`): not applied; the rules do not decide it. Two readings
  give different names:
  - The ledger's reading names the method through its defining classes,
    `SimpleTestCase` and `TransactionTestCase`. This is the class that the
    package checks (`issubclass`, line 28) and the class that defines what
    a documented `TestCase` inherits.
  - "Methods" and "Inherited methods" could instead name it through the
    documented receiver class, `django.test.TestCase._pre_setup` and
    `._post_teardown`.

  The receiver is the client's test class, which has no public path. So
  neither rule fixes the class that names the method. The second reading
  would rename 3 pairs. The trace's name for these edges
  (`TransactionTestCase._pre_setup`) has no `TestCase` alias, so the
  checker would then need `TransactionTestCase` kept beside it. This is
  for the lead or the referee.

  **The lead's ruling:** the ledger's names stay, and the ledger does not
  change. The receiver `test_case` is a client's class. The only class that
  the package's code names is `SimpleTestCase`, in its `issubclass` check,
  and `TransactionTestCase` defines the override that the documented
  classes inherit. A second name through `django.test.TestCase` would be an
  alias of the same function on the same runtime, which the README's
  "Versions and configuration" clarification forbids.
- **Metadata 1** (stale note at `admin.py:201:95`): applied. The note now
  says that both names are verified.
- **Metadata 2** (the claim that every path is public): applied. "Scope
  rules", C, now lists the private functions. No decision depended on the
  old wording.
- **Metadata 3** (the graph matches the ledger, 677 pairs; PyPy excluded):
  confirmation, no change.

## Codex audit round 2

The audit is `audit-t6-r2/django-constance.md` (an audit record). Edges went
from 679 (256 inside, 423 outside) to 680 (256 inside, 424 outside).

- **Missing 1** (`ConstanceAdmin.changelist_view ->
  django.contrib.auth.models.AnonymousUser.has_perm`, `admin.py:113:62`):
  applied.
  - `AnonymousUser.has_perm` returns `_user_has_perm(...)`, which returns
    True when a configured backend's `has_perm` does
    (`contrib/auth/models.py:605`, `266-278` in Django 6.1.2; `479`,
    `212-224` in 4.2.30).
  - With `CONSTANCE_SUPERUSER_ONLY` false, a client backend can grant the
    view permission at line 108, so an anonymous request gets to line 113.
  - The backend stays opaque, and its effect on control flow counts (B5).
  - No other site was excluded by this reasoning. The only other anonymous
    case, `forms.py:83:58`, already has the edge, and the `is_superuser`
    checks are attribute loads.
- **Metadata 1** (the lists that omitted the `_pre_setup` and
  `_post_teardown` self edges): applied, in "Value sites" and "Functions
  that no site calls"; no edge change.

## Codex confirmation pass

The pass (`audit-t6-r3/django-constance.md` (an audit record)) found no
missing and no false edge. It raised two metadata items, and both are
applied. At `forms.py:149:24` and `test/pytest.py:44:20` the setter no
longer lists `LazyConfig._setup`, because the `getattr` just before it
(`139:30`, `43:49`) has already set up the same wrapper. The pairs stay
through those earlier sites, so the graph keeps its 680 edges.

## Corrections of 2026-11-25

**(a) The releases of redis.** The extra `redis = ["redis"]`
(`pyproject.toml:42-43`) is a declared requirement without a bound. By
batch 7's ruling "Which releases of a dependency are admitted" it admits
every redis release that runs on an admitted runtime (CPython 3.10 and
later); the lead's batch-6 reading (the audit pin only, judgement 1) is
replaced. Batch 8's rule "Which releases of a dependency are read" gives
the sample: the floor, and the last release of each minor series up to
the pin of the test environment (redis 8.1.0, uploaded 2026-07-30, before
the release of 4.5.0 on 2026-10-28). Each sdist was fetched in a container
by its PyPI SHA-256 and read as text, never run.

- **Floor: 2.6.1** (`c9e0e74e...`). Every older release on PyPI has
  Python 2 syntax that CPython 3.10 does not parse (`except
  (socket.error, socket.timeout), e:`, `redis/connection.py:76` of 2.6.0;
  `client.py:28` of 1.34; 0.6.x is a single Python 2 module). 2.6.1
  imports through `redis/_compat.py`, whose Python 3 branch (`:29-50`)
  covers every Python 2 name that its modules use.
- **Read:** 2.6.1, 2.6.2, 2.7.6, 2.8.0, 2.9.1, 2.10.6, 3.0.1, 3.1.0,
  3.2.1, 3.3.11, 3.4.1, 3.5.3, 4.0.2, 4.1.4, 4.2.2, 4.3.6, 4.4.4, 4.5.5,
  4.6.0, 5.0.8, 5.1.1, 5.2.1, 5.3.1, 6.0.0, 6.1.1, 6.2.0, 6.3.0, 6.4.0,
  7.0.1, 7.1.1, 7.2.2, 7.3.1, 7.4.1, 8.0.1, 8.1.0 (and every 2.x release,
  for the floor).

| Name in the ledger | What every read release has |
|---|---|
| `redis.from_url` (`redisd.py:32:46`, `0003_drop_pickle.py:51:37`) | exported by `redis/__init__.py` (`:7` of 2.6.1 to `:57` of 8.1.0); it returns a `redis.Redis`: `Redis(...)` in 2.6.1 (`utils.py:27-31`), `Redis.from_url(...)` from 2.6.2 on (`utils.py`, `from redis.client import Redis`) |
| `redis.Redis` (`redisd.py:34:43`, `0003_drop_pickle.py:53:34`) | a class in `client.py` (`:1152` of 2.6.1, the backwards-compatible subclass of `StrictRedis` in 2.x; `:416` of 3.0.1; `:156` of 8.1.0) |
| `redis.Redis.get`, `.mget`, `.set` (`redisd.py:62:29`, `78:76`, `90:21`; `0003_drop_pickle.py:57:28`, `61:20`) | defined in `StrictRedis` (2.x: `client.py:454`, `492`, `538` of 2.6.1), in `Redis` (3.x: `client.py:1602`, `1663`, `1763` of 3.5.3) or in `CoreCommands` (4.0 on: `commands/core.py:3194`, `3760` (overloads from `3751`), `4292` of 8.1.0), named through the receiver class `redis.Redis`; the arguments of every package call bind |
| `redis.asyncio.from_url`, `redis.asyncio.Redis` and its `get`, `mget`, `set` (`redisd.py:47:48`, `49:45`, `69:36`, `85:38`, `99:28`) | from 4.2.0 on (`redis/asyncio/__init__.py:15` of 4.2.2, `:21` of 8.1.0; `asyncio/client.py:83` of 4.2.2, `:136` of 8.1.0); before 4.2.0 `import redis.asyncio` fails and `_ard` is `None` (`redisd.py:39-44`), the branch that already runs (optional imports, both sides) |

No name or edge changes: the releases before the pin add no callee and
remove none, because the graph is the union over the admitted releases.

**(b) The builtin SHA-256 object** (`forms.py:124:32`, `125:57`).
`_sha256.sha256.update` and `.hexdigest` are renamed
`_sha256.SHA256Type.update` and `.hexdigest` (2 edges renamed). Batch 8's
ruling "A C type exported under a module attribute other than its type
name" names a C type by the attribute under which its module exports it,
never by the type name where an attribute exists, and never by two aliases
on one runtime. The package admits CPython 3.10 and later only:

| Runtime | Builtin fallback of `hashlib.sha256` | Type name | Exported as | Name |
|---|---|---|---|---|
| CPython 3.10, 3.11 | `_sha256.sha256` (`Lib/hashlib.py:95-97` of 3.11.18) | `_sha256.sha256` (`Modules/sha256module.c:567` of 3.10.22, `:570` of 3.11.18) | `SHA256Type` (`PyModule_AddObject`, `:725`, `:728`) | `_sha256.SHA256Type` |
| CPython 3.12 to 3.15 | `_sha2.sha256` | `_sha2.SHA256Type` (`Modules/sha2module.c:547` of 3.12.16, `:540` of 3.15.2) | `SHA256Type` (`PyModule_AddType`, `:855`, `:867`) | `_sha2.SHA256Type` |
| OpenSSL, every version | `_hashlib.openssl_sha256` | `_hashlib.HASH` (`Modules/_hashopenssl.c:697` of 3.10.22, `:1097` of 3.15.2) | `HASH` (`PyModule_AddType`, `:2143`, `:2787`) | `_hashlib.HASH` |

Graph: 680 edges (256 inside, 424 outside), unchanged in number; 497
confirmed by the trace, unchanged.
