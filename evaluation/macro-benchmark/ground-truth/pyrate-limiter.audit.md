# pyrate-limiter: independent audit of the ground truth

Release v4.5.1, commit `968301de411f722235c6db152a55fa4ea77fd3c7`. Audited
files: the ground truth of commit de651c7 ("as its writer left it"):
`pyrate-limiter.ledger` (905 entries, 966 callee lines, 278 rejection lines,
184 notes, 8 default rejections), `pyrate-limiter.json` (288 nodes, 831
edges: 411 in the package, 420 outside), `pyrate-limiter.rejected.json` (4
trace edges) and `pyrate-limiter.md`. `check.py --benchmark-dir
macro-benchmark-heldout-4 pyrate-limiter` reports no errors; the trace
confirms 547 edges, 284 come from reading only (148 inside, 136 outside),
and no trace edge is unaccounted for.

I judged the files by the README rules (A, B1 to B5, C) and the rulings of
the earlier sets. I read the whole package source (25 modules), the
project's `README.md` (included by `docs/index.md`) and `pyproject.toml`,
and some tests, as data. I ran nothing of the package and no analysis tool.

**Result.** The blind sample agrees with the ledger at all 87 sites. I found
no missed edge and no edge that cannot happen. Every dispatch set over the
seven bucket classes and the sync/async wrapper is right. Two findings are
wording only (W1, W2). Five of the writer's judgements need or invite a
ruling (J3, J5, J6, J8, J12); I support the writer's reading in each. Four
remarks concern the README (R1 to R4). No finding changes the graph unless
the lead rules against the writer on J5 (+5 edges), J6 (-11), J12 (+2) or
J3 (-1).

## Findings

| Id | Kind | Site or claim | Evidence | Edges | Recommendation |
|---|---|---|---|---|---|
| W1 | wording | `pyrate-limiter.md`, judgement 4: "`Decision(...)` (14 sites)" | The ledger has 15 `Decision(` call entries (`algorithm.py` 44, 118, 131, 162, 260, 267; `bucket.py` 118, 120; `in_memory_bucket.py` 89, 98; `postgres.py` 164; `redis_bucket.py` 170, 176; `redis_state.py` 107:24, 107:76). | 0 | say 15 |
| W2 | wording | `pyrate-limiter.md`, "What the trace does not cover": "210 of the 284 edges from reading only have a caller in `buckets.postgres`, ... or `extras`, or a missing-module callee" | 171 of the 284 have a caller there. 210 is the count of edges whose caller **or callee** is there, or whose callee is a missing module (39 more, for example `Leaker._leak -> RedisBucket.leak`, `LogAlgorithm.decide -> PostgresBucket.put.peek_timestamp`). | 0 | say "a caller or a callee in ..." or give 171 |
| J5 | ruling (writer's judgement 5) | `bucket.py:253:35` `bucket.leak(0)`: only `RedisBucket.leak`, `StateBucket.leak` | The probe runs only when `bucket.is_async is None`. Each package bucket class sets the attribute (`bucket.py:35-40`, `in_memory_bucket.py:27`, `sqlite_bucket.py:66`, `postgres.py:82`, `wrappers.py:15`, `state_bucket.py:114`). The project README never assigns `is_async`; it does document `bucket._clock = ...` (README:595-616). | 0 (+5 if ruled otherwise) | keep. Proposed rule (B2, stored values): a public attribute of a package object takes the values that the package assigns, and a client's value only where the documentation or tests assign it |
| J6 | ruling (writer's judgement 6) | a `BucketAsyncWrapper` that wraps a `BucketAsyncWrapper` (`wrappers.py:17-96`) | `bucket: AbstractBucket` and `isinstance(bucket, AbstractBucket)` (`wrappers.py:17-18`) admit the wrapper (B2: the annotation decides; an `isinstance` names the class). No test or document does it (README:386 says "any sync bucket"). | 0 (-11 if ruled otherwise: the 11 self-edges of `put`, `count`, `leak`, `flush`, `peek`, `waiting`, `now`, `failing_rate`, `_last_wait`, `_algorithm`, `rates`) | keep; the rule text supports it |
| J12 | ruling (writer's judgement 12) | `in_memory_bucket.py:75:34`, `77:34` on a `MultiprocessBucket` | `ListProxy.append` and `.extend` are defined by `exec` in `multiprocessing.managers.MakeProxyType`. The micro-benchmark gives such a function no edge (`dynamic/exec_defines_function`: `generated()` adds no edge, although `main.generated` is a path), and `validate.py:234` records none. | 0 (+2 if named `multiprocessing.managers.ListProxy.append`, `.extend`) | keep; state it in the README (R1) |
| J3 | ruling (writer's judgement 3) | `limiter.py:182:24` `logger.info("... %s", rates) -> Rate.__repr__` | Logging formats the record in the calling thread when a handler emits it; `str()` of the list calls `repr()` of each `Rate`. A program that enables INFO makes the call; the trace has the edge (`tests/conftest.py` sets INFO). | 0 (-1 if ruled otherwise) | keep; state it in the README (R2) |
| J8 | ruling (writer's judgement 8) | `redis_state.py:86:40` the script call `-> redis.Redis.register_script`, `redis.asyncio.Redis.register_script` | Micro-benchmark `external/decorator` (calling an instance of the stub `ext.route` is named `ext.route`) and `validate.py:226` ("a stub or an instance of one: named by its path"). With redis-py read, the names would be `redis.commands.core.Script.__call__` and `AsyncScript.__call__`; redis is not installed and I found no copy on this machine. | 0 | keep; state it in the micro-benchmark README (R3) |
| R1 | README | "Nodes" states the `exec` rule for package code only | J12 needs it for library code. | - | add: a library function that `exec` defines has no name; a call of it adds no edge |
| R2 | README | no rule for lazy formatting by a library | J3. | - | add: a package `__str__`/`__repr__` that logging calls when it emits a record is a callee of the logging call |
| R3 | micro-benchmark README | "Missing modules" says what calling an instance of a stub returns, not how the call is named | J8. | - | add: the call is named by the stub's path |
| R4 | README | B2 does not say whether a client may assign a public attribute of a package object | J5 (and `Leaker.sync_buckets`, typed `Dict`, `bucket.py:226`, where the ledger also keeps only the package's `defaultdict`). | - | the rule proposed under J5 |

What I could not check: the SHA-256 of the three wheels that the writer
downloaded (`pyrate-limiter.md`, judgement 9). This machine has unpacked
copies of the same releases (requests 2.34.2, httpx 0.28.1, httpx2 2.15.1,
in uv caches); I read them, never ran them, and they confirm judgement 9
(below). The project's `uv.lock` pins older versions (requests 2.32.4,
httpx2 2.10.0); I could not read those, but the methods involved have the
same role. redis, psycopg and psycopg_pool are not on this machine
(typeshed has `psycopg2` only), so their missing-module names could not be
compared with the real classes.

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch directory
`$TMPDIR/heldout4-audit-pyrate-limiter/` with a copy of `projects.toml` and a
`projects` link, then `check.py --benchmark-dir <scratch> --skeleton
pyrate-limiter`. It has 1221 sites. I numbered them from 0 in (module order,
line, column) and drew `random.Random(20261111).sample(range(1221), 70)`,
then added the 19 value sites (2 were already drawn): 87 sites. I did not
stratify: `Duration.__eq__` is a candidate at 253 sites, all `getitem`, and
the draw has 17 `getitem` sites; 18 of the 87 sites are in the Redis,
PostgreSQL and extras code. Kinds: 55 call, 17 getitem, 6 getattr, 3
decorator, 3 format, 2 op, 1 delitem. I wrote my callees for each site
before I opened any file of the writer or the trace (the file
`blind.md` in the scratch directory).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random (70) | 68 | 68 | 0 |
| Random and value | 2 | 2 | 0 |
| Value only | 17 | 17 | 0 |
| **Total** | **87** | **87** | **0** |

The points that I marked uncertain while blind, and the writer's answer:
`redis_state.py:86:40` (the same two stub names, J8); `bucket.py:380:30`
(the same seven `__init__`, by `Type[AbstractBucket]`); `wrappers.py:56:32`
(the wrapper over a wrapper, J6); `bucket.py:331:32`, `332:33` (only the
package's `defaultdict`, R4).

## Step 2: dispatch sets (B1, B2)

Concrete buckets: `InMemoryBucket`, `MultiprocessBucket` (inherits
`InMemoryBucket.count`, `flush`, `peek`), `StateBucket`, `RedisBucket`,
`SQLiteBucket`, `PostgresBucket`, `BucketAsyncWrapper`. `AbstractBucket`,
`BucketFactory`, `LogAlgorithm`, `StateAlgorithm`, `StateStore` and
`AbstractClock` are abstract by `abc`; `LockLike` is a `Protocol`. I listed
every ledger site whose callees are bucket methods (75 sites) and checked
each set against the class table. All agree with the ledger. The cases
worth naming:

| Site | Receivers | Callees |
|---|---|---|
| `wrappers.py:22` to `96` (`self.bucket.X`) | any bucket, also a wrapper (J6) | 7 `put`, 7 `leak`, 6 `count`, 6 `flush`, 6 `peek`, 3 `waiting`, 4 `now`, the 4 wrapper properties |
| `bucket.py:104:26` `self.put` in `put_decision`; `117:37`, `120:43`, `85:25` | every bucket (the wrapper inherits `put_decision`, `_decision`, `_recorded_wait`) | 7 `put`; the wrapper's `failing_rate`, `_last_wait` |
| `bucket.py:169:31` `self.peek` in `waiting` | the five log buckets | 4 `peek` |
| `bucket.py:167:47` / `174:47` | the line is reached only when `blocking_offset` returns `None` / an int | `FixedWindow.retry_after` / `SlidingWindowLog.retry_after` |
| `bucket.py:253:35` | buckets whose `is_async` is `None` (J5) | `RedisBucket.leak`, `StateBucket.leak` |
| `limiter.py:217, 244, 248, 303, 623` | any bucket | the wrapper is included |
| `limiter.py:273, 297, 357, 370, 650` | only after a `put` or `waiting` that returned a plain value; the wrapper's are coroutine functions (judgement 10) | the wrapper is excluded |
| `bucket.py:66:31` `self._clock.now()` | the clock argument of `StateBucket` (`Optional[AbstractClock]`) admits all five clocks | 5 `now` |
| `bucket.py:443:37` `self.owned_buckets()` | `SingleBucketFactory` (overrides) | `BucketFactory.owned_buckets` rejected (B1, as `ContextDecorator._recreate_cm`) |
| `limiter.py:77` to `105` (`combined_lock`) | `_thread.RLock`; the tuple of `mp_lock` (`_multiprocessing.SemLock` methods) or the `FileLock`, then the RLock | the trace has all six lock methods |

I also checked the branches that only a client value takes but that call
package code on `self` or builtins: `redis_state.py:57` (`TypeError`,
`type`; J14), `limiter.py:359-365` (the "pathological" async tail of
`_blocking_retry_sync`: no package bucket returns a plain value first and an
awaitable later), `limiter.py:655` and `687`. The ledger keeps their edges,
and that is right: the client value reaches the site and the calls do not
depend on it.

## Step 3: the 284 edges from reading only

171 have a caller in `buckets.postgres`, `buckets.redis_bucket`,
`buckets.redis_state`, `clocks.PostgresClock` or `extras`: no test reaches
these with a real client (the tests that construct `RedisBucket` and
`PostgresClock` pass their own fakes). I read each of the 194 edges of these
callers against the source. The other 113: package dispatch that no test
exercises (wrappers over other buckets, J6; `create` with the six other
bucket classes; the clocks of `AbstractBucket.now`; the probe of J5),
`combined_lock` from `_try_acquire` and `_blocking_retry_sync` (tracer
defect T1), error and timeout branches, and `RedisStateStore` methods called
by `StateBucket`. All are possible.

## Step 4: default rejections

I listed every site of each default (`--report --default`). `Duration.__eq__`
(253): the keys and operands are types in annotations, ints, strs, slices
and database rows; `Duration.__eq__` itself compares two ints (`rate.py:35`).
`Rate.__repr__`, `Rate.__str__`, `RateItem.__str__` (52, 51, 51): the
explicit sites are SQL templates, `psycopg.sql.SQL(...).format`, `str` of a
redis member and of a `Path`; the only formatted `Rate`s are the list at
`utils.py:42:46` (accepted) and the log argument of J3. The four
`__enter__`/`__exit__` (33 each): every `with` manages a lock, a
`nullcontext`, a `FileLock`, a context manager of the package or a psycopg
stub. All correct.

## Step 5: rejections, notes, callers, callees outside

- I read all 905 entries, with all 278 rejection lines and 184 notes. Each
  reason holds. The `Decision(...)` notes, the T1 notes and the
  missing-module notes are accurate.
- Nodes without a caller (100: the 25 modules and 75 functions): each keeps the edges of its
  body (rule A); for example `Rate.__str__ -> Duration.readable`,
  `StateAlgorithm.decode -> <builtin>.tuple, <builtin>.float`, the abstract
  stubs with none.
- Callees outside the package (157 names): each exists and is named by the
  rules or by a trace alias (`asyncio.Task.cancel` = `_asyncio.Task.cancel`,
  `types.CoroutineType.close` = `builtins.coroutine.close`, `abc.ABC.__init__`
  = `<builtin>.object.__init__`, `filelock.FileLock.acquire` =
  `filelock._api.BaseFileLock.acquire`, `multiprocessing.managers.SyncManager.list`
  = `BaseManager.register.temp`). The missing-module names follow the
  micro-benchmark rules (`with` gives the stub itself, a call returns an
  instance of the stub) and ruling 2 of the third set (the `isawaitable`
  and `LockNotAvailable` branches run).
- Judgement 9, read from local copies: `requests.Session.__init__` calls
  only `self.mount`, `request` calls `prepare_request`,
  `merge_environment_settings` and `send`, `close` calls no method of
  `self`; the httpx and httpx2 transports call no method of `self`. The
  package overrides none of these, so the `super()` calls have no package
  callee.
- Rejected trace edges (4): `StateBucket.count -> StateAlgorithm.consumed`
  and `StateBucket.waiting -> Algorithm.max_weight` come from the tests'
  `StateAlgorithm` subclasses (client code, B1); the two
  `_cancel_if_pending -> _asyncio.Task` edges come from the test's own Task
  passed to the private `_handle_async_result` (B5). All stay rejected.
- The statistics of `pyrate-limiter.md` match the files (905 entries, 966 /
  278 (79) / 184, 539 default pairs, 831 edges, 547 confirmed), apart from
  W1 and W2.

## Judgement

The ground truth is complete and precise as far as this audit can test it:
87 of 87 blind sites agree, every dispatch set and default is right, and
every edge from reading only is possible. The open points are rulings on
five judgements that the writer already flagged or argued, and two wording
fixes.


## Round 3 complete source audit (2026-11-16)

The independent static review reconstructed all 2560 scanner sites
from the 25 runtime modules before opening this project's ground truth.
The source model, source inventory and support inventory were frozen with SHA-256
on 2026-11-16 at 12:04:51 UTC. The global README's project examples and historical
tables were disclosed as prior exposure; project results were opened only after
the freeze. No target, test, dependency or generated code was imported or run,
and neither PyCG nor the trace supplied semantic answers.

The review retains all 832 baseline pairs on 288 nodes. It confirms no false
positive, no missing pair, and no site metadata correction. All 967
site-target relations agree after source-level control-flow and outside-name
adjudication. The review covers 905 entries,
1655 omitted scanner sites, 539 default
candidate decisions, 351 explicit rejection/exclusion rows,
441 own binding relations and 62 zero-edge nodes.

The checks retain these scope distinctions:

- All seven concrete buckets fit the AbstractBucket role, including nested
  BucketAsyncWrapper values. A wrapper cannot reach the synchronous retry
  branches whose earlier put or waiting result must be plain.
- FixedWindow.blocking_offset always returns None, so it cannot reach the
  _calc_waiting closure; an admitted int subtype can make SlidingWindowLog's
  reflected subtraction return None and reach the earlier retry_after site.
- Client Future/Task and custom algorithm callbacks remain opaque. Public
  factory inputs do not admit arbitrary package callables or failed-object reuse.
- Missing redis, psycopg and aiohttp calls keep stub access paths. Reading
  ordinary library source does not permit callbacks. Requests and HTTPX
  transport base definitions were read through the definition exception and
  add no package overrides.
- Python 3.10 and 3.14 primary sources confirm contextlib.contextmanager.helper,
  the _thread.RLock and _multiprocessing.SemLock receivers, and exec-generated
  ListProxy append/extend methods with no name. FileLock's public class alias
  and admitted call signatures remain valid across the archived versions.

Primary sources are hashed in the round-3 report. They include CPython 3.10.0
and 3.14.0, local CPython 3.15.2 text, PyPy 3.10-v7.3.17 and 3.11-v7.3.20,
filelock 3.0.0/3.18.0/4.2.4, HTTPX 0.28.1,
HTTPX2 2.10.0 (the uv.lock archive hash), and Requests 2.32.4.
Both archived PyPy releases export _thread.RLock with acquire/release methods.
RELEASING.md, CONTRIBUTING.md, CI configuration and nox configuration received
supplemental full-text review after the freeze; these support Python/PyPy scope.
The full evidence is in the staged pyrate-limiter-review.json and its companion
all-site, binding, zero-body and outside-name inventories. A fresh independent
OpenAI auditor was used under the allowed same-provider fallback. Structural,
origin and patch replay checks establish consistency; semantic claims rest on
the source review. Previous audit text remains intact.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 source-first audit (2026-11-16)

A fresh static read retained all 832 pairs on 288 nodes: no new false
positive, missing edge, or ledger-site metadata correction. The source model
was frozen before opening the baseline (manifest SHA-256
`6dd246c74afd89eabd52c07834b3ba460c7186c497163bda373c54b9863bd948`).
Evidence covers all 2,560 scanner sites, 905 ledger entries, 1,655 omitted
sites, 967 site-target relations, 539 default candidate decisions and 292
body occurrences (288 distinct module/function nodes, 62 zero-edge nodes).

Current CI explicitly includes PyPy3.11 and CPython3.14t; requires-python
remains >=3.10 with no inferred upper bound. The normal/-O/-OO union is
the round-wide working assumption after an unanswered optional preference.
Assertion removal produces no additional named pair under the global role
and client-opacity rules. All assertion sites received a separate review.

The new source model initially overgeneralized manager proxy naming. Reading
retained CPython source confirmed that ListProxy append/extend are generated
with exec and remain unnamed. This corrected the model, not the baseline.
HTTP transport and Requests base methods add no callback through their actual
super-call paths. FileLock's alias and call signatures remain valid.
PyPy's thread module exports _thread.RLock acquire/release. Client futures
remain opaque. Historical audit text and all graph/ledger/origin files remain
unchanged. Evidence is in the round-4 pyrate-limiter agent directory. The
lead performs the structural/origin gate separately; no runtime code or
target/dependency tests were executed by this source auditor.
