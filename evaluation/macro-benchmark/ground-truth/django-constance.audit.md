# django-constance: independent audit of the ground truth

Release 4.5.0, commit `1032c50d39ef5e737b99a42870d60bf8e2e34c39` (batch 6).
Audited files, as last written on 2026-11-22 at 15:48 EET and
unchanged at 16:05 (uncommitted in the ground-truth branch of batch 6): `django-constance.ledger` (652
entries), `.json` (660 edges: 255 inside, 405 outside), `.added.json` (174
edges), `.rejected.json` (16 trace edges), `.md` (judgements 1 to 10) and
`dynamic/django-constance.json` (499 trace edges). `check.py
django-constance` reports no errors.

Method: README "Auditing a ground truth" and the auditor brief of batch 6.
I read the package source, `docs/`, `tests/` and the pinned dependency
sources (Django 6.1.2, asgiref 3.13.0, redis 8.1.0 under
`deps/django-constance/` (the dependency sources of the audit records); pytest 9.2.0 and pluggy
1.7.0 from the tool venv, the same versions as the pins) as text. I ran no
analysis tool and no package code.

**Result.** No edge that cannot happen and no missed edge that the rules
require. One convention finding (N1, +5 edges if adopted, only under the
reading of judgement 3), two wording findings (W1, W2) and two README
remarks (R1, R2). Six judgement calls ask for a ruling. The table "Judgement
calls" gives the README rule that decides each, my opinion, and the
number of edges that depends on it. Binding check: 283 pairs of a site and
a package callee, all bind.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Proposed decision |
|---|---|---|---|---|---|
| N1 | low (convention; only under judgement 3) | `redisd.py:62:29` `self._rd.get`, `78:76` `.mget`, `90:21` `.set`; `0003_drop_pickle.py:57:28` `_rd.get`, `61:20` `_rd.set` | Judgement 3 admits the documented `CONSTANCE_REDIS_CONNECTION_CLASS = 'django_redis.get_redis_connection'` (`docs/backends.rst:70`) and names its call as a missing module (`redisd.py:24:64`, `0003:48:53`). The value it returns is then a stub instance. The README names calls on such a value by the stub's access path: "Calling a stub ... returns an instance of that stub" (micro-benchmark, Missing modules), "A call of an instance of a stub is named by the stub's path" (pyrate-limiter ruling 13), "a documented expression of a missing module is named by its access path" (dagster-pipes `boto3.client.get_object`), and "direct attribute/call chains retain their imported access path" (clarification "Missing libraries"). The ledger names only `redis.Redis.get`, `.mget`, `.set`, by the docs' words "a callable that returns a redis connection" (`backends.rst:68`), which names no class. `redis.Redis.*` stays for the default branches (`redisd.py:32`, `34`; `0003:51`, `53`). | +5 (`RedisBackend.get -> django_redis.get_redis_connection.get`, `.mget -> ...mget`, `.set -> ...set`; `migrate_pickled_data -> ...get`, `...set`) | add the 5 stub names, or the writer answers why B4 fixes `redis.Redis` for the stub's result; if the referee rejects judgement 3, the question disappears |
| W1 | wording (no edge change) | `base.py:122:22` (`AsyncValueProxy.__rmod__` -> `__str__`, `__repr__`, `__int__`, `__float__`, `__index__`, `__getitem__`); `django-constance.md` judgement 10 | The ledger note and judgement 10 justify the str-formatting edges only by a direct call of the public `__rmod__` with a str. A protocol witness exists that needs no direct call: a client str subclass whose `__mod__` returns `NotImplemented` once and then delegates to `str.__mod__` (`S("%s") % config.X`): Python then calls the proxy's `__rmod__`, whose `other % value` formats the stored proxy. The clarification "Client control flow (B5)" admits it ("An admitted subclass can override operations; repeated ... checks need not agree"). So these 6 edges depend on judgement 2 (stored proxy) only, not on judgement 10. | 0 | reword the note and judgement 10; judgement 10 then decides 4 edges, not 10 |
| W2 | wording (no edge change) | judgement 9, "Not verified: older admitted versions" | The admitted Django range is 4.2 to 6.1 (judgement 1), and only 6.1.2 was read. One edge rests on a 4.2 name from memory (`history_view -> django.utils.functional.lazy.__proxy__.__promise__.__wrapper__`, `admin.py:201:95`). I could not read 4.2 either; from memory the 4.2 `lazy` has `__proxy__.__prepare_class__` and a classmethod `__promise__` that returns a local `__wrapper__`, which agrees with the ledger. | 0 | keep; the lead may supply the Django 4.2 and 5.0 wheels to close the list of judgement 9 |
| R1 | README remark | B5 (whitenoise ruling L2) | L2 admits "the library's defaults and the configurations that the package documents". It does not say whether the package's own test settings count as a documented configuration, while B2 counts the package's tests for package values, and the tinytag ruling counts the package's own test setup for an environment variable. The writer reads L2 literally (tests do not count). That decides about 9 edges and 3 trace edges in judgement 3 (the tests' `EmailField`, `TypedMultipleChoiceField`, `CheckboxSelectMultiple`, `tests/settings.py:61`, `tests/test_admin.py:282-290`, with their `prepare_value`, `to_python` and `clean`) and 5 or 6 edges and 3 trace edges in judgement 8 (the tests' SQLite connection, `tests/settings.py:21-30`). My blind answers counted the tests; on reflection the literal text supports the writer. | 0 now | the lead confirms the literal reading, or the referee rules on both judgements together |
| R2 | README remark | B2 last sentence against B5 (L2) | The two sentences overlap for outside classes that a setting names and the documentation shows: B2 calls them client callbacks "whatever the documentation shows", L2 puts "the configurations that the package documents" in scope. L2 speaks of "library code" that picks; constance picks with Django's `import_string` (library) for `CONSTANCE_ADDITIONAL_FIELDS` and with its own `import_module_attr` (package) for `CONSTANCE_REDIS_CONNECTION_CLASS`. See judgement 3 below. | see J3 | a sentence in B5 that says which rule holds for settings, and whether it matters who resolves the dotted path |

Checked and not a finding: I suspected a missed callback
`ConstanceAdmin.changelist_view -> AsyncValueProxy.__bool__` at
`admin.py:115:29` (`form.is_valid()` -> `FileField._clean_bound_field` ->
`FileField.clean(data, initial)`, whose `if not data and initial` tests a
stored proxy as the initial value of a documented `ImageField`;
`django/forms/fields.py:708-710`, `forms.py:341-349`). It cannot happen: a
stored proxy returns itself, so `ConstanceForm.__init__` (`admin.py:112:24`,
before line 115) already ends in `RecursionError` at `forms.py:124:44`. No
edge.

## Step 1: blind re-derivation

The blind answers are in
`$TMPDIR/audit-django-constance/blind-answers.md` (saved at 15:51,
before any writer file was opened at 15:55; the work started at 15:39), with
the draw script `draw.py` and the drawn list `sample.json` beside it.

**Sample.** Skeleton without ledger: 1745 sites, 28 value sites. Attribute
sites (675 getattr, 37 setattr) are 41% of the skeleton, and nearly all of
them have only the candidate `Config.__getattr__`; so the draw is split by
kind: `random.Random(20261122)`, `rng.sample(explicit, 35)` (612 call and
decorator sites), `rng.sample(attribute, 15)` (712), `rng.sample(other, 20)`
(421 other implicit sites), plus the 28 value sites, 2 of which were drawn:
96 sites. Sites numbered in (line, column) order module by module.

| Group | Sites | Agree | Naming only | Auditor wrong | Writer missed | Writer cannot happen |
|---|---|---|---|---|---|---|
| Explicit | 35 | 32 | 2 | 1 | 0 | 0 |
| Attribute | 15 | 15 | 0 | 0 | 0 | 0 |
| Other implicit | 20 | 20 | 0 | 0 | 0 | 0 |
| Value sites (26 not drawn) | 26 | 21 | 1 | 4 | 0 | 0 |
| **All** | **96** | **88** | **3** | **5** | **0** | **0** |

The 8 differences:

- **Naming only (3):** `forms.py:63:39` (`django.forms.widgets.Select` and
  `.Textarea`, mine; the ledger `django.forms.Select`, `.Textarea`, the
  path that the documented setting uses); `forms.py:77:30`
  (`django.forms.fields.CharField`, mine; `django.forms.CharField`, the
  path the code uses); `0003_drop_pickle.py:68:29`
  (`django.db.migrations.operations.special.RunPython`, mine;
  `django.db.migrations.RunPython`). One class each; the ledger's names
  follow "the path as the snippet reaches it".
- **Auditor wrong (5):**
  - `test/unittest.py:66:35`, `75:35`, `78:35`: I gave no callee
    (methods of the client's test class, B5). The ledger names Django's
    `SimpleTestCase` and `TransactionTestCase` `_pre_setup` and
    `_post_teardown`. B4 supports the ledger: the package checks
    `issubclass(test_func, SimpleTestCase)` (`unittest.py:28`) and the docs
    show a `TestCase` (`docs/testing.rst:16-29`); a client override is
    client code. The trace has the `TransactionTestCase` edges.
  - `0002_migrate_from_old_table.py:25:23` (`cursor.execute`) and
    `forms.py:122:44` (`EmailField`): I counted the tests' configuration
    (SQLite; the tests' additional field) under L2. The literal L2 admits
    only documented configurations (R1).

Blind views that the ledger improved: at the four `config_updated.send`
sites I had `LazyConfig._setup` only; the ledger also has
`Config.__getattr__`, through `_make_id`'s `hasattr(sender, "__func__")`
(`django/dispatch/dispatcher.py:15-18`, `494`; verified). The writer is
right.

## Step 2: exhaustive checks

**Dispatch sets (B1).** `Backend` is abstract by `abc` (no receiver).
`Config._backend` is one of the four package backends at every backend
call (`base.py:138`, `168`, `174`, `177`; `utils.py:22`, `55`;
`base.py:23` through the proxy's Config): agree. `RedisBackend.set` has
`self` RedisBackend or CachingRedisBackend (`super().set`, `redisd.py:165`),
so `self.get` has both `get`; `RedisBackend.aset` and `RedisBackend.mget`
only a RedisBackend (CachingRedisBackend overrides both and never calls
them on itself); `RedisBackend.amget`, `get`, `aget`, `_aset_internal` both
classes: all agree. Every `super()` call resolves as the ledger says.
`override_config.enable`/`disable` of the two helpers never mix
(`pytest.py:56`, `59`; `unittest.py:46`, `65`, `74`, `79`): agree.

**Callback roles.** `encoder(o)` (`codecs.py:26:50`) and `codec[1](...)`
(`62:24`): the six defaults of `codecs.py:93-98`, client registrations
are client callbacks: agree, lambda numbering checked. `_dumps`/`_loads`
defaults with the callbacks `JSONEncoder.default` and `object_hook`:
agree. The backend class (`base.py:135:83`): the four documented package
classes: agree. `form_cls` (`admin.py:112`, `114`): `ConstanceForm.__init__`:
agree. The four `sync_to_async(...)()` sites: `SyncToAsync.__call__` and
the wrapped method (asgiref `sync.py:502-635`): agree. `post_save` ->
`DatabaseBackend.clear` at `database.py:145:36` and `154:27`, not at the
migration's historical model: agree. Django's call-backs (`AdminSite.register`,
`has_view_or_change_permission`, `each_context`, `is_valid`,
`TestContextDecorator.__enter__`/`__exit__`): agree, each read in 6.1.2.

**LazyConfig forwarding.** Every load, store and hash of a `LazyConfig`
that package code makes (18 sites: the 10 `getattr`/`setattr(config, ...)`
calls, the 4 loads `config._backend` and `config.amget` of `utils.py`, the
4 `send` sites) has
`LazyConfig._setup`, and `Config.__getattr__`/`__setattr__` where the name
is a config name: complete.

**Default rejections (4 lines, 29 candidates).** I read every explicit site
that a default decides (`check.py --report`: the `getattr`/`hasattr` calls
on modules, Django's `LazySettings` and values; `len`, `list`, `zip`,
`sorted`, `any`, `dict` on package or client values; `str.format` at
`admin.py:155:105`; the two `super().__setattr__` calls). None hides a real
call. `Constance.__str__`: no package code and no Django code that the
package calls formats a `Constance` (checked `QuerySet.get`, `create`,
`delete`, `Model.save`, `LogEntry.objects.create`).

**Functions no site calls, special methods, properties.** As in the
judgements file. `Config.Meta.app_config` is reached at `admin.py:126:39`
only; `label`, `label_lower` only by Django in client calls;
`get_change_permission`, `get_ordered_objects` by no admitted Django. The
`_backend` branch of `Config.__getattr__` (`base.py:145-146`) is reached by
no protocol: normal lookup always finds `_backend`, and `copy`, `deepcopy`
and pickle probe `__setstate__`, `__deepcopy__`, never `_backend`.
`Config.__setattr__`'s branch (`164`) needs a store of the private name
`_backend` (J10).

**Rejections and notes.** All 195 rejection lines and 170 notes read;
each reason holds. The 16 rejected trace edges: 5 `unittest.mock`
objects of the tests; 6 calls of the tests' cache mock-up (a client class
whose methods are bound `LocMemCache` methods; the result of a client's
cache is a client object, B5); 3 of the tests' additional fields and 3 of
the tests' SQLite connection (both by the literal L2, R1). Agree.

**Callees outside the package.** Every outside name of the sample and of
the J sites checked against the pinned sources: `redis.from_url`,
`redis.Redis`, `redis.asyncio.from_url`, `redis.asyncio.Redis` and their
`get`/`mget`/`set` (`redis/__init__.py:3`, `57`; `commands/core.py:3194`,
`3751`, `4292`; `asyncio/__init__.py:21`); `Signal.send`,
`ModelSignal.connect`, `LazyObject` (`django/utils/functional.py`);
`CommandParser.add_subparsers` (`partial(CommandParser, ...)` for the
sub-parsers, `core/management/base.py`), `argparse._SubParsersAction.add_parser`;
the cursor and `async_unsafe` path (`db/backends/base/base.py:283-320`);
`FileField.clean`, `localize`, `smart_bytes`/`force_bytes`;
`pluggy._decorators.HookimplMarker.__call__.setattr_hookimpl_opts`,
`_pytest.fixtures.FixtureFunctionMarker.__call__`; Python 3.15's
`ContextDecorator.__call__` (`async_inner`). One convention question: N1.

## Step 3: binding check

283 pairs of a site and a package callee (the `-> constance.` lines of
the ledger). Each call was checked against the callee's signature,
including the call-backs that library code makes: `post_save` calls
`clear(signal=, sender=, instance=, created=, update_fields=, raw=,
using=)` and `clear(self, sender, instance, created, **kwargs)` binds;
`AdminSite.register` calls `admin_class(model, self)`;
`get_model_perms` calls `has_add_permission(request)` (`*args`); asgiref
calls `func(*args, **kwargs)` with `()` or `(key, value)`; Django calls
`_pre_setup` as an instance method before 5.2 (the first def, `inner_self`)
and as a classmethod from 5.2 (the second); `form_cls(data=, files=,
initial=, request=)` binds `__init__(self, initial, request=None, *args,
**kwargs)`. All 283 bind with the arguments that the package or the
library passes; no call cannot bind. No edge changes.

## Judgement calls

| J | Question | README rule that decides it | Writer | My opinion | Edges that depend on it |
|---|---|---|---|---|---|
| J1 | Admitted Django versions | Not decided: "decided by its own declared requirements", and the release declares none (`pyproject.toml` has no dependencies). The smaller extension: the versions that the release explicitly supports, as for interpreters ("Versions and configuration"): classifiers 4.2 to 6.1, tox `dj42`..`dj61` (`djmain` is `ignore_outcome`) | 4.2 to 6.1 | agree | 1 edge directly (`history_view -> lazy.__proxy__.__promise__.__wrapper__`, Django 4.2); both sides of `DJANGO_VERSION < (5, 2)` give the same edges. Names of 4.2 to 6.0 not read (W2) |
| J2 | When package code holds an `AsyncValueProxy` | Decided: "Edges" (some program that uses only the public API makes it, fresh process) with B ("what the package's own calls pass counts in full"). The docs say that sync access in async code "still works" with a warning and name runners that keep a loop running (`docs/index.rst:317-327`); the Memory backend is the documented test backend (`docs/testing.rst:118-129`); the pytest helper's `with` and its decorator run `enable` in the loop thread (CPython 3.15 `ContextDecorator.async_inner`; before 3.15 `inner`, which asgiref's `main_wrap` calls in the loop); the unittest helper's async path does not (thread-sensitive `sync_to_async` runs in a thread with no running loop, asgiref `sync.py:347-365`) | first order and stored proxy | agree with both. First order: `admin.py:74:41`, `forms.py:148:24` (`__ne__`), `constance.py:56:38` (`__str__`). Stored proxy: only `MemoryBackend.set` keeps it (`dumps` raises in Redis and Database); it returns itself, so every special method recurses to `RecursionError`, after the call. Reflected comparisons with a proxy as `other` need a client to pass a proxy: B3, not considered (the ledger rejects them) | first order 3; stored proxy 36 (29 self edges, `__rmod__` -> 6 str-format methods, `ConstanceForm.__init__ -> __str__`) |
| J3 | Classes and callables that settings name | Partly decided. B5/L2 ("when library code picks an object from the client's configuration, the library's defaults and the configurations that the package documents are in scope") decides `CONSTANCE_ADDITIONAL_FIELDS` (Django's `import_string` picks) and the database cache (`caches[...]` picks). For `CONSTANCE_REDIS_CONNECTION_CLASS` the package's own `import_module_attr` picks: no rule decides; the smaller extension applies L2 whoever resolves the path. B2's last sentence is the alternative reading (R2). The backend class is a package value named by the docs (B2) in every reading | L2 for all | agree. The cache: Django's default `LocMemCache` is refused (`database.py:35`) and the documented `MemcachedCache` is absent from Django 6.1.2 (`core/cache/backends/memcached.py`), so no callee in any reading | 16 edges and 4 trace edges (writer's count, verified: 2 widgets, 3 field classes, 3 `prepare_value`, 6 `to_python`/`clean`, 2 `django_redis`); +5 more if N1 is adopted; about 9 edges and 3 trace edges more if tests count (R1) |
| J4 | `send(sender=constance.config)` | Decided: the callback rule (B5) and "Edges" (fresh-process witness). Verified in 6.1.2: `send` hashes the sender in `sender_receivers_cache.get` (a plain dict, `dispatcher.py:99`, `242-247`) and `_live_receivers` calls `_make_id`, whose `hasattr(target, "__func__")` is forwarded to `Config.__getattr__` (`15-18`, `494`); a receiver is documented (`docs/index.rst:80`); `constance.config` is still empty when the set comes through the LazyConfig of forms, admin or utils, or a direct `Config()` | `_setup` and `Config.__getattr__` at the 4 sites | agree | 8 |
| J8 | `schema_editor.connection` of migration 0002 | Decided by L2: Django picks the backend from `DATABASES`; Django's default is none (`global_settings.py:185`, `{}`, the dummy backend, which refuses `cursor`, so `migrate` never reaches the function) and the package documents no engine | no callee; 3 trace edges rejected | agree under the literal L2 (R1) | 5 or 6 edges (sqlite3 `quote_name`, `cursor`, `table_names`, `sequence_reset_sql`, `CursorWrapper.execute`, and `CursorDebugWrapper.execute` if `DEBUG = True` of `tests/settings.py:96` counts) and 3 trace edges, if tests count |
| J10 | Direct call of a public special method | Not decided. Rule C makes dunders public and B lets a client pass any argument to a public method: literally the `_backend` branches keep their edges. Against: ruling 8 of batch 5 (a client that calls `__init__` again is not considered) and B3 (an attribute name that the client supplies is not taken to name package internals). The smaller extension of those: a special method is reached only through the operation that Python maps to it, with the arguments Python passes | keeps the 4 edges | the README does not decide; I lean to the protocol-only reading (nothing in the docs or tests calls a dunder directly or stores `_backend`), but either is defensible | 4 (`Config.__getattr__ -> <builtin>.super`, `-> object.__getattribute__`, `base.py:146`; `Config.__setattr__ -> <builtin>.super`, `-> object.__setattr__`, `164`). Not the 6 `__rmod__` edges (W1) |

Rulings for the lead or the referee: J3 (with R1, R2 and N1), J10, and
the scope question of R1, which also decides J8. J1 needs only the lead's
confirmation; J2 and J4 are decided by existing rules.

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-constance-redis` (fe9da93, PR #105) against `main`
(0febb44): two outside edges renamed, none added or removed, in
`django-constance.json`, `django-constance.added.json`,
`django-constance.ledger` and `django-constance.md`, and
`evaluation/metrics.json` re-based; no other file changed. I read
`constance/` and `pyproject.toml` from the inputs image; the redis sdists
of every release before 2.6.1 and of 2.6.1, 2.6.2, 2.10.6, 3.0.1, 3.5.3,
4.1.4, 4.2.2, 5.0.8, 6.4.0 and 8.1.0, fetched in a container by PyPI's
SHA-256 and parsed (never imported or run) by CPython 3.10.22's `ast` in
the container; and CPython 3.10.22 to 3.15.2 from the dependency sources.
No PyCG output was read.

**(a) The redis releases.** `pyproject.toml:42-43` declares the extra
`redis = ["redis"]`, and the package admits CPython 3.10 and later only
(`:11`, `:37`), so batch 7's rule admits every redis release that runs on
CPython 3.10 and later, and batch 8's rule reads the floor and the last
release of each minor series up to the pin 8.1.0.

- Floor: agree, 2.6.1. CPython 3.10's parser rejects every release before
  it: 0.6.0 and 0.6.1 (`redis.py:85`, `:92`), 1.34 and 1.34.1
  (`client.py:28`), 2.0.0 (`client.py:53`), 2.2.0 and 2.2.2 (`:54`),
  2.2.4 to 2.4.13 (`connection.py:26` to `:73`), 2.6.0 (`connection.py:76`,
  "multiple exception types must be parenthesized"). 2.6.1 parses, and its
  imports take `_compat.py`'s Python 3 branch (`:29-50`; no
  `collections` ABC alias, no Python 2 module). The parser matters: CPython
  3.14 accepts `except (socket.error, socket.timeout), e:` as a tuple of
  exceptions (PEP 758), so this check must use a 3.10 parser.
- The series: agree. PyPI's last release of each minor series from 2.6 to
  8.1 is exactly the writer's list; 8.2.0 (2026-11-23) is after the pin
  and the release of django-constance 4.5.0.
- The sample I read gives the writer's answer: `redis.from_url` is exported
  by `__init__.py` in all ten and returns a `redis.Redis` (`Redis(...)` in
  2.6.1 `utils.py:27-31`, `Redis.from_url(url, db, **kwargs)` in 2.6.2);
  `redis.Redis` is a class (2.6.1 `client.py:1152`, a subclass of
  `StrictRedis` `:148`; 3.0.1 `:416`; 8.1.0 `:156`); `get`, `mget` and `set`
  exist with signatures that bind the package's calls (`redisd.py:62`,
  `78`, `90`: one key; a list; a key and a value): 2.6.1 `client.py:454`,
  `492`, `538`; 3.5.3 `:1602`, `1663`, `1763`; 4.1.4 `commands/core.py:1227`,
  `1392`, `1590`; 8.1.0 `:3194`, `3751-3760`, `4292`. `redis/asyncio` is
  absent in 4.1.4 and present from 4.2.2 (`__init__.py:1`, `15`;
  `asyncio/client.py:83`, `asyncio/utils.py:7`) to 8.1.0 (`:21`, `:136`),
  so `import redis.asyncio` before 4.2.0 raises `ImportError` and
  `redisd.py:40-44` sets `_ard` to `None`, the branch that already runs.
- No edge depends on a release-specific name: every redis callee of the
  graph (`redis.from_url`, `redis.Redis` and its `get`, `mget`, `set`,
  `redis.asyncio.from_url`, `redis.asyncio.Redis` and its `get`, `mget`,
  `set`) is a public path that every release after its introduction has,
  and the methods are named through the receiver class, so the class that
  defines them (`StrictRedis`, `Redis`, `CoreCommands`) changes no name.

**(b) The builtin SHA-256 object.**

| Site | Change | Verdict | Evidence |
|---|---|---|---|
| `forms.py:124:32` `version_hash.update(...)` | `_sha256.sha256.update` renamed `_sha256.SHA256Type.update` | agree | `version_hash = hashlib.sha256()` (`:81`). On CPython 3.10 and 3.11 hashlib's fallback is the factory `_sha256.sha256` (`Lib/hashlib.py:94-97` of 3.11.18), whose objects have `.name = "_sha256.sha256"` (`sha256module.c:567` of 3.10.22, `:570` of 3.11.18) and whose type `_sha256` exports as `SHA256Type` (`PyModule_AddObject`, `:725`, `:728`) |
| `forms.py:125:57` `version_hash.hexdigest()` | `_sha256.sha256.hexdigest` renamed `_sha256.SHA256Type.hexdigest` | agree | the same object |
| both | `_sha2.SHA256Type.*` and `_hashlib.HASH.*` kept | agree | from 3.12 the fallback is `_sha2.sha256` (3.12.16 `hashlib.py:95-97`), type `.name = "_sha2.SHA256Type"` added by `PyModule_AddType` (`sha2module.c:547`, `855` of 3.12.16; `:540`, `867` of 3.15.2); `_hashlib.HASH` as in the bottle audit |

No public class alias applies (ruling-names-2): the package declares
`Implementation :: CPython` only (`pyproject.toml:37`), and CPython's
`hashlib.sha256` is a factory. Nothing missed: `forms.py:81` is the only
hash in the package; its locks (`memory.py:13`, `redisd.py:109`) are used
only in `with` statements, implicit sites with no outside edge, and the
constructor names `threading.Lock` and `threading.RLock` do not change.
No other outside callee falls under the two rulings.

Counts. 680 edges (256 inside, 424 outside), 497 traced, 183 added: as
`check.py django-constance` reports, which passes with the source in
place, as do `--origin` and `--report`. `gate.benchmark_digest()` on the
branch gives `7636db90bff3d5642c226403bade93101c540f974adf73875bf7a59194802ce0`,
the recorded digest. The `make eval` numbers come from PyCG's output,
which I did not read.

| Id | Finding | Where | Fix |
|---|---|---|---|
| A1 | the Python 2 syntax of redis 1.34 is cited at `client.py:31`; that line is `sock.setsockopt(...)`, and the syntax is `except socket.error, e:` at `:28` | `django-constance.md`, "Corrections of 2026-11-25", (a), floor | cite `:28` |

**Verdict.** The two renames stand, the floor and the sample hold, and
nothing is missed. A1 corrects one citation; no edge depends on it.

A1 was applied before the merge (`django-constance.md` cites
`client.py:28` of redis 1.34). The audit is closed.
