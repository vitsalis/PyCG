# tenacity 9.2.1: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

First pass: `tenacity.ledger`, `tenacity.json`, `tenacity.md` and
`tenacity.rejected.json` as they were on disk before commit ac5504f (the
revised version with 557 edges, after the writer removed the 10
stacked-`@retry` edges). Final check: the same files at commit 80ffe0c
("tenacity ground truth after audit", 560 edges), against the lead's final
scope rules A to C. The auditor read the 12 modules of `tenacity/`, the
documentation (`doc/source/*.rst`, `README.rst`, the release notes) and the
tests as data, and used Python semantics only. The auditor did not run the
package or its tests, and did not use PyCG or any other static analysis
tool. The trace (`dynamic/tenacity.json`) was used as a lower bound only.
The writer's files were opened only after the blind derivation of step 1.

Rules applied: the conventions of `macro-benchmark/README.md` and
`micro-benchmark/README.md`, and the lead's final scope rules A to C (they
replace the API rules (1) to (3) of the brief), with the two clauses that the
lead added after this audit:

- **B1, `super()`.** A receiver also counts when a subclass calls the base
  method explicitly on itself through `super()` (this makes T6).
- **B2, unions with a bare `Callable`.** In an annotation that is a union of
  a package base class and a bare `Callable`, only the base-class arm names
  package values for the role (its public subclasses, and instances that the
  package offers for it). The `Callable` arm admits client callbacks only. A
  strategy of another role, or any other package callable, at that site is an
  arbitrary package object where any callable is accepted (B3). This decides
  T7.

## Final result

| ID | Kind | Status | Confidence |
|---|---|---|---|
| T1 | missing edge (convention B4): `stop_when_event_set.__call__ -> threading.Event.is_set` | stands; **fixed** in 80ffe0c | certain |
| T2 | missing edge (convention B4): `sleep_using_event.__call__ -> threading.Event.wait` | stands; **fixed** in 80ffe0c | certain |
| T3 | doubtful, missing note: `retry.wrap -> warnings.warn` | stands (edge kept); **fixed** in 80ffe0c (note at `__init__.py` 785:26, Scope rules B2) | likely |
| T4 | weak reason for a correct edge: nap strategies at `TornadoRetrying.__call__` | stands; **fixed** in 80ffe0c (note at `tornadoweb.py` 62:33, Scope rules B2) | certain |
| T5 | stale text: the old judgement 7 and open question 1 of `tenacity.md` | stands; **fixed** in 80ffe0c (Scope rules B4, B5; "Open questions: None") | certain |
| T6 | missing edge (rule A): `BaseRetrying.wraps.wrapped_f -> tenacity.asyncio.AsyncRetrying.__call__` | stands; **fixed** in 80ffe0c (the writer found it too) | certain |
| T7 | scope question: cross-role strategies that fit the `Callable` arm of an annotation | **decided by the lead: no change** (99 edges stay out) | - |

Final count: **6 findings stand**, all applied in 80ffe0c: 3 missing edges
(T1, T2 under B4; T6 under rule A), 1 doubtful edge kept with a new note
(T3), 2 text findings (T4, T5). T7 was a scope question, decided with no
change. There are no edges that cannot happen and no wrong names. The
committed graph has 560 edges (361 in the package, 199 to outside callees);
the trace confirms 405, 7 trace edges are rejected, 155 edges come from
reading only. The committed files agree with these findings (see "Final
check of the committed files").

## Findings

The evidence describes the files as the first pass found them (before
80ffe0c); "Final check of the committed files" gives their state now.

| ID | Kind | Site or edge | Evidence | Confidence |
|---|---|---|---|---|
| T1 | convention (B4) | `tenacity.stop` 86:33 `self.event.is_set()` in `stop_when_event_set.__call__`: add `-> threading.Event.is_set` | `stop_when_event_set.__init__(self, event: "threading.Event")` (`stop.py:81`) stores the event in `self.event` (`stop.py:82`). Nothing else assigns `self.event`. The annotation fixes a concrete type from outside the package, so the documented execution calls `threading.Event.is_set`. The ledger note calls the event a client callback. The function never ran in the tests, so the trace has nothing to confirm or reject. | certain |
| T2 | convention (B4) | `tenacity.nap` 43:24 `self.event.wait(timeout=timeout)` in `sleep_using_event.__call__`: add `-> threading.Event.wait` | `sleep_using_event.__init__(self, event: "threading.Event")` (`nap.py:37`) stores it in `self.event` (`nap.py:38`). The same argument as T1. The function never ran in the tests. | certain |
| T3 | doubtful (missing note) | `tenacity` 785:26 `warnings.warn(...)` in `retry.wrap`: `-> warnings.warn` | The call runs only when `isinstance(f, retry_base)` (`__init__.py:784`). `tenacity.md` judgement 6 excludes a package strategy as the function to retry (B3), and that is the case the warning is for. One legitimate execution remains: the client passes an instance of its own subclass of `retry_base` as the function (a client object, B2). So keep the edge. But the entry has no note, and judgement 6 reads as if the warning path were out of scope. Add a note at 785:26 that names the client-subclass execution. | likely |
| T4 | weak reason (edge correct) | `tenacity.tornadoweb` 62:33 `self.sleep(do)`: `-> tenacity.nap.sleep`, `-> tenacity.nap.sleep_using_event.__call__`; `tenacity.md` judgement 5 | The note gives the reason "tornado accepts the None they return". By B2 the annotation of the parameter decides, and `TornadoRetrying`'s own annotation `"typing.Callable[[float], Future[None]]"` (`tornadoweb.py:34`) does not admit a sleep that returns `None`. The edges are still right, by another path: the sync `@overload` of `retry` types `sleep: t.Callable[[int \| float], None]` (`__init__.py:757`), and `retry.wrap` passes `**dkw` unchanged to `TornadoRetrying` when `tornado.gen.is_coroutine_function(f)` (`__init__.py:791-801`). So `@retry(sleep=tenacity.nap.sleep)` on a tornado coroutine reaches this site through the API ("the package itself passes them there"). Cite this path in the note and in judgement 5. (In the blind sample I left these two edges out; this path proves the writer right.) | certain |
| T5 | stale text | `tenacity.md` judgement 7 and "Open questions" 1; the notes at `stop.py` 86:33 and `nap.py` 43:24 | They follow the old reading ("as the README does for jmespath's `dict_cls`"). Under the new ruling the event calls are edges (T1, T2), and the logger calls stay without a callee because `logger` is typed `_utils.LoggerProtocol` (`before.py:30`, `after.py:30`, `before_sleep.py:31`), a `typing.Protocol`. The old text was also inconsistent: `to_seconds` has the edge `-> datetime.timedelta.total_seconds` for a client `timedelta` (`_utils.py:107-110`, typed `int \| float \| timedelta`), but the event, typed the same way, had none. The new ruling makes both edges. | certain |
| T6 | missing edge (rule A) | `tenacity` 404:24 `copy(f, *args, **kw)` in `BaseRetrying.wraps.wrapped_f`: add `-> tenacity.asyncio.AsyncRetrying.__call__`; withdraw `tenacity.md` judgement 11 and the matching part of the note | `AsyncRetrying.wraps` calls `super().wraps(fn)` (`asyncio/__init__.py:212`), so `BaseRetrying.wraps` runs with `self` an `AsyncRetrying` and makes a `wrapped_f` whose free variable `self` is that object. The trace proves this receiver: `BaseRetrying.wraps.retry_with -> tenacity.asyncio.AsyncRetrying.wraps` is a trace edge (`tests/test_asyncio.py:184`), and the ledger accepts it at 407:52. When that `wrapped_f` runs, `copy = self.copy()` (`__init__.py:395`) is an `AsyncRetrying`, and `copy(f, ...)` calls the coroutine function `AsyncRetrying.__call__` (the coroutine is returned, not awaited). Judgement 11 removes the edge because that `wrapped_f` "never reaches a client": a reachability argument, which rule A forbids. (B1's wording "a package subclass that inherits the method" would also drop the traced `retry_with` edge, so B1 must include receivers that a `super()` call passes. Of the package's `super()` calls, this is the only one that runs an overridden method whose body dispatches on the class of `self`.) | certain |
| T7 | scope question (decided: no change) | the strategy call sites of step 2 | See "Re-check under rules A to C", point 3. The lead adopted the recommendation and added the B2 clause on unions with a bare `Callable` (see the rules above). | - |

Two observations that are not errors of the ground truth:

- **Counts in the brief.** The files give 557 edges (not 567), 152 edges that
  the trace does not confirm (not 162) and 56 functions with no caller (not
  54), plus the 11 module nodes. `tenacity.md` has the right numbers. The
  difference of 10 edges matches the 10 stacked-`@retry` edges that the md
  says it removed.
- **Trace bookkeeping.** `BaseRetrying.__iter__`, `AsyncRetrying.__anext__` and
  `TornadoRetrying.__call__` are not in the trace's `executed` list, but the
  trace has their out-edges (for example `TornadoRetrying.__call__ ->
  tornado.gen.Return`). The interpreter or tornado starts these generators
  and coroutines (a validator limit). So 24 functions never ran, not 27.

## Decisions on the open questions

1. **A strategy or a retrying object as the function to retry: out.** `fn`
   and `f` take any callable (`fn: t.Callable[..., WrappedFnReturnT]`,
   `__init__.py:539`; `f: t.Callable[P, R]`, `__init__.py:381`). The
   documentation never passes a package object there. `retry.wrap` calls a
   `retry_base` instance in that place a mistake that "will probably hang
   indefinitely" (`__init__.py:784-789`). B3 applies. So the 9 sites
   that call the function to retry and `repr(cb)` (`_utils.py:96`) have no
   package callee. The ledger agrees. Only `warnings.warn` stays, through a
   client subclass (T3).
2. **Stacked `@retry`: out.** No example in `doc/source/index.rst` or
   `README.rst` and no test puts `@retry` on a function that `@retry` already
   decorates. The issue-519 tests (`tests/test_tenacity.py:1639-1667`,
   `tests/test_asyncio.py:126-149`) put a client decorator made with
   `functools.wraps` *over* `@retry`, which is not a second `@retry`. No
   release note shows it, and neither `retry_with` nor `copy` feeds a wrapper
   back in (see "Re-check under rules A to C", point 1). The writer was right
   to remove the 10 stacked-wrapper edges.
3. **`threading.Event`: in (B4).** B4 adds T1 and T2 and
   nothing else. The annotation of every parameter whose value the package
   calls or calls a method on:

   | Parameter | Annotation | Effect |
   |---|---|---|
   | `event` (`stop.py:81`, `nap.py:37`) | `"threading.Event"` | adds `threading.Event.is_set`, `threading.Event.wait` (T1, T2) |
   | `logger` (`before.py:30`, `after.py:30`, `before_sleep.py:31`) | `_utils.LoggerProtocol` (a Protocol) | none: a client callback. The rejected trace edge `before_sleep_log.log_it -> logging.Logger.log` stays rejected |
   | `sleep` (`__init__.py:261`, `asyncio/__init__.py:78`, `tornadoweb.py:34`) | bare `Callable` | none beyond the package values |
   | `retry_error_cls` (`__init__.py:269`, `298`, `748`, `766`; `asyncio/__init__.py:91`) | `type[RetryError]`, a package type | `RetryError.__init__` only (already there). The rejected trace edge to `<builtin>.ValueError` stays rejected: `ValueError` is not a `RetryError` |
   | `reraise` (`__init__.py:268`) | `bool` | none: only a truth test (`__init__.py:481`); `retry_exc.reraise()` is a method of `RetryError` |
   | `time_unit` and the `max`, `min`, `wait`, `jitter`, ... that reach it (`_utils.py:107`) | `int \| float \| timedelta` | `datetime.timedelta.total_seconds` (already there) |
   | `match` (`retry.py:238`) | `str \| re.Pattern[str] \| None` | none on the parameter; `self.match.match` is a package-made `re.Pattern` (already there) |
   | `last_attempt` (`__init__.py:202`) | `"Future"`, a package class | `concurrent.futures.Future.exception`/`.result` (already there) |
   | `before`, `after`, `before_sleep`, `retry_error_callback`, every `predicate`, `fn`, `f`, `cb`, `call` | bare `Callable` | none |
   | `sec_format` (`after.py:32`, `before_sleep.py:34`) | `str` | none: used only by the `%` operator, not an explicit call |
4. **Async strategies at sync sites and the reverse: in, where the
   annotation admits them.**
   - Async retry strategies at the sync retry sites (`_run_retry`, the sync
     `retry_any`/`retry_all`): in. `BaseRetrying.__init__` and the sync
     `retry_any`/`retry_all` take `RetryBaseT = retry_base | Callable[...]`
     (`retry.py:63`, `287`, `304`), and the async strategies subclass
     `retry_base` (`asyncio/retry.py:26`). The sync `@overload` of `retry`
     names `tasyncio.retry.RetryBaseT` (`__init__.py:760`). The `__call__`
     is called and never awaited.
   - Sync strategies at the async sites: in, through `wrap_to_async_func.inner`.
     `AsyncRetrying` takes `"SyncRetryBaseT | RetryBaseT"`
     (`asyncio/__init__.py:83`) and the sync `StopBaseT`/`WaitBaseT`; the
     async `retry_any`/`retry_all` take `retry_base | async_retry_base`
     (`asyncio/retry.py:106`, `130`).
   - Sync sleeps at the `AsyncRetrying` sleep sites: in. The annotation
     `Callable[[int | float], Awaitable[None] | None]`
     (`asyncio/__init__.py:78-79`) admits `nap.sleep` and
     `sleep_using_event`; the call runs, then `await None` fails.
   - Sync sleeps at `TornadoRetrying.__call__`: in, through `retry` (T4).
   - `_portable_async_sleep` or `tornado.gen.sleep` in a `Retrying`: out. A
     client reaches them only by passing a private package value or a library
     object.

## Step 1: blind re-derivation

Before opening the writer's files, the auditor read the whole package and
wrote down the hierarchy and the strategy sets below, then the callees of
each sampled site (kept in the scratch file `blind.py`).

**Sample.** A copy of the tools under `$TMPDIR`, with `projects/` linked
read-only and no `ground-truth/` directory, made the skeleton without
defaults: 779 sites. The sites are numbered from 1 in skeleton order.
`random.Random(20261111).sample(sites, 80)` drew 80 sites; 2 of them have no
candidates by name. The other 43 no-name sites were added: **123 sites**.

| Set | Sites | Package-callee disagreements | Outside-callee disagreements |
|---|---|---|---|
| 80 random sites (18 of them decided only by the writer's defaults) | 80 | 0 | 0 |
| 45 sites with no candidates by name (2 overlap) | 45 | 1 (`tornadoweb` 62:33) | 1 (`nap` 43:24) |
| All | 123 | **1 (0.8 %)** | **1 (0.8 %)** |

Classification of the 2 differences: `tornadoweb` 62:33, *the auditor was
wrong* (T4: the writer's edges stand, on another reason); `nap` 43:24,
*convention* (T2). Writer missed an edge: 0. Edge that cannot happen: 0.
Naming only: 0. These numbers use the brief's rules. Under rule A one sampled
site, #157 (`tenacity` 404:24, T6), lacks an edge in both the writer's
ledger and the auditor's blind derivation: a joint miss, not a disagreement.

<details><summary>The 123 sampled sites (skeleton numbers)</summary>

- `tenacity`: #5 120:2 decorator, #32 295:53 op, #36 298:43 op, #44 349:6 decorator, #54 636:44 op, #68 745:61 op, #76 760:78 call, #78 762:61 op, #83 812:16 call, #90 168:18 format, #113 309:28 call, #114 310:29 call, #120 315:39 call, #127 329:29 call, #136 343:21 format, #142 372:44 call, #145 378:47 call, #149 387:25 call, #152 392:25 call, #157 404:24 call, #161 407:47 getattr, #171 424:25 getattr, #175 427:54 call, #176 430:47 call, #180 434:52 call, #185 440:28 call, #186 444:14 getattr, #192 453:14 getattr, #196 456:21 getattr, #201 458:14 getattr, #204 461:22 getattr, #208 462:18 getattr, #234 480:49 call, #235 482:38 call, #244 504:41 call, #257 519:27 call, #258 544:22 call, #265 553:32 call, #273 560:27 call, #274 569:14 call, #275 569:25 call, #276 575:30 call, #277 582:18 call, #279 586:27 call, #294 672:33 format, #295 672:53 call, #312 791:24 call, #322 803:25 call, #324 805:18 getattr
- `tenacity._utils`: #341 97:29 call, #353 130:20 call, #354 130:21 iter
- `tenacity.asyncio`: #364 53:16 call, #372 88:72 op, #390 67:30 call, #392 72:25 call, #396 119:32 call, #398 120:22 call, #405 130:42 call, #406 130:43 iter, #407 132:36 call, #413 138:53 call, #415 139:33 call, #422 149:81 getattr, #426 161:14 getattr, #435 171:34 call, #436 176:24 call, #450 206:33 call, #456 215:25 call, #459 220:32 call, #461 223:29 call, #464 232:30 call
- `tenacity.asyncio.retry`: #470 46:6 decorator, #477 118:6 decorator, #480 142:6 decorator, #483 50:25 call, #484 56:25 call, #486 77:32 getattr, #489 81:40 call, #490 96:31 call, #492 99:40 call, #497 122:22 call, #503 136:18 iter
- `tenacity.nap`: #541 31:15 call, #542 43:24 call
- `tenacity.retry`: #569 36:34 call, #593 103:34 call, #597 119:26 call, #610 163:30 call, #619 193:30 call, #622 212:34 call, #626 228:38 call, #628 241:28 call, #638 260:37 call, #642 268:34 call, #647 281:30 call, #649 292:21 call, #650 292:44 iter, #651 296:22 call, #654 297:46 iter, #658 309:21 call
- `tenacity.stop`: #667 42:23 op, #679 53:21 call, #682 64:21 call, #686 115:24 getattr
- `tenacity.tornadoweb`: #696 40:6 decorator, #697 41:6 decorator, #703 52:27 call, #705 55:38 call, #713 62:33 call, #714 64:33 call
- `tenacity.wait`: #719 88:6 decorator, #729 55:28 call, #733 85:49 call, #734 86:49 call, #739 107:27 call, #742 133:27 call, #745 135:25 call, #749 175:30 call, #751 192:43 call, #752 193:37 call, #772 314:37 call, #773 316:40 call

</details>

**Hierarchy (blind).** `BaseRetrying(ABC)` has the subclasses `Retrying`,
`AsyncRetrying` (overrides `__call__`, `_add_action_func`, `_run_retry`,
`_run_wait`, `_run_stop`, `iter`, `__iter__`, `wraps`; adds `__aiter__`,
`__anext__`) and `TornadoRetrying` (overrides `__init__`, `__call__`).
`Retrying` has no `__init__`, so `Retrying(...)` runs
`BaseRetrying.__init__`. `stop_base(ABC)`: `stop_any`, `stop_all`,
`_stop_never` (`stop_never`), `stop_when_event_set`, `stop_after_attempt`,
`stop_after_delay`, `stop_before_delay`; `&` makes a `stop_all`, `|` a
`stop_any`. `wait_base(ABC)`: `wait_fixed` (subclass `wait_none`),
`wait_random`, `wait_combine`, `wait_chain`, `wait_exception`,
`wait_incrementing`, `wait_exponential` (subclass `wait_random_exponential`),
`wait_exponential_jitter`; `+` makes a `wait_combine`, `0 + w` (for `sum`)
returns `w`. `retry_base(ABC)`: `_retry_never`, `_retry_always`,
`retry_if_exception` (subclasses `retry_if_exception_type`,
`retry_if_not_exception_type`, `retry_unless_exception_type`,
`retry_if_exception_message` and its subclass
`retry_if_not_exception_message`), `retry_if_exception_cause_type`,
`retry_if_result`, `retry_if_not_result`, `retry_any`, `retry_all`, and
`async_retry_base` with `tenacity.asyncio.retry.retry_if_exception`,
`retry_if_result`, `retry_any`, `retry_all`. Sync `&`/`|` give
`other.__rand__`/`other.__ror__`, so a sync and an async operand give an async
`retry_all`/`retry_any`. `Future(concurrent.futures.Future)`,
`RetryCallState`, `AttemptManager`, `IterState` (a slotted dataclass),
`BaseAction`/`RetryAction`, `DoAttempt`, `DoSleep(float)`,
`RetryError(Exception)`, `TryAgain(Exception)`. The Protocols
`_RetryDecorated`, `_AsyncRetryDecorator` and `_utils.LoggerProtocol` are
never instantiated. `_RetryDecorated.__get__` and
`_AsyncRetryDecorator.__call__` have only `@overload` stubs, so at run time
the class attribute is `typing`'s overload dummy and the node never runs.

## Step 2: strategy dispatch, every site

The blind sets agree with the writer's sets exactly. Each row lists every
site of that kind; the ledger has the same callees at each.

| Set | Size | Members |
|---|---|---|
| stop | 7 | `__call__` of `stop_any`, `stop_all`, `_stop_never`, `stop_when_event_set`, `stop_after_attempt`, `stop_after_delay`, `stop_before_delay` |
| wait | 9 | `__call__` of `wait_fixed` (also `wait_none`), `wait_random`, `wait_combine`, `wait_chain`, `wait_exception`, `wait_incrementing`, `wait_exponential`, `wait_random_exponential`, `wait_exponential_jitter` |
| sync retry | 10 | `__call__` of `_retry_never`, `_retry_always`, `retry_if_exception` (also `_type`, `_not_exception_type`, `_exception_message`), `retry_unless_exception_type`, `retry_if_exception_cause_type`, `retry_if_result`, `retry_if_not_result`, `retry_if_not_exception_message`, `retry_any`, `retry_all` |
| async retry | 4 | `__call__` of the async `retry_if_exception`, `retry_if_result`, `retry_any`, `retry_all` |
| hooks | 6 | `before_nothing`, `before_log.log_it`, `after_nothing`, `after_log.log_it`, `before_sleep_nothing`, `before_sleep_log.log_it` |
| internal actions | 7 shared + 3 sync-only | shared by both variants: the lambdas of `__init__.py:450`, `462`, `500`, `_post_retry_check_actions`, `_post_stop_check_actions`, `exc_check`, `next_action`; sync-only: `BaseRetrying._run_retry`, `_run_wait`, `_run_stop` |

| Site | Size (writer = auditor) |
|---|---|
| `__init__.py` 427:54 `self.retry(...)` | 14: sync + async retry |
| 430:47 `self.wait(...)` | 9 |
| 434:52 `self.stop(...)` | 7 |
| 440:28 `action(...)` in `BaseRetrying.iter` | 16: hooks + 10 internal actions |
| `asyncio` 171:34 `action(...)` in `AsyncRetrying.iter` | 4: `inner`, `AsyncRetrying._run_retry`, `_run_wait`, `_run_stop` |
| `_utils` 130:20 `call(...)` in `inner` | 39: 7 shared internal actions + hooks + stop + wait + sync retry |
| `asyncio` 149:87 / 155:80 / 162:85 | 5 (`inner` + async retry) / 1 / 1 |
| `asyncio/retry` 113:66, 137:67 | 5 each |
| `retry.py` 292:21, 309:21 | 14 each |
| `stop.py` 53:21, 64:21 | 7 each |
| `wait.py` 107:27, 135:25 | 9 each |
| sleep: 519:27 / 560:27 / `asyncio` 139:33, 206:33 / `tornadoweb` 62:33 | 3 (with `tornado.gen.sleep`) / 2 / 3 each (with `_portable_async_sleep`) / 3 (with `tornado.gen.sleep`; T4) |
| 480:49 `retry_error_cls(fut)`, 482:38 `reraise()` | 1 each |
| 306:30 `self.__class__(...)` | 3 `__init__`s |
| 404:24 `copy(f, ...)` | `Retrying.__call__`, `TornadoRetrying.__call__`, `tornado.gen.coroutine.wrapper`; under rule A also `AsyncRetrying.__call__` (T6) |
| `asyncio` 232:30 `copy(fn, ...)` | `AsyncRetrying.__call__` |
| 407:52 `...wraps(f)`, 805:23 `r.wraps(f)` | `BaseRetrying.wraps`, `AsyncRetrying.wraps` |
| `retry.py` 36:34 `other.__rand__`, 50:33 `other.__ror__` | 4 each |
| `retry.py` 103:34 / 163:30 / 281:30 `self.predicate(...)` | 3 `_check`s / `retry_unless_exception_type._check` / `retry_if_not_exception_message._check` |
| client-only: the 9 `fn`/`f` sites, 8 client predicates, 3 `logger.log`, 2 `self.event` | 0 (but T1, T2) |
| the 14 `_add_action_func(...)` calls (`__init__.py:449-500`) | both `_add_action_func`s; the stored function rejected |

Checked in both directions: no member of a role is missing at a site of that
role, and no site lists a member that its role or its class cannot reach.

## Step 3: the actions list

The 14 `_add_action_func` calls add: `self.before`; the lambda of 450;
`self._run_retry`; `self._post_retry_check_actions`; the lambda of 462;
`self.after`; `self._run_wait`; `self._run_stop`;
`self._post_stop_check_actions`; `self.retry_error_callback` (client only, no
package value); `exc_check`; `next_action`; `self.before_sleep`; the lambda
of 500. `BaseRetrying.iter` runs for `Retrying` and `TornadoRetrying`, which
store them unchanged: 16. `AsyncRetrying` wraps each one: its own async
`_run_*` stay as they are (bound async methods are coroutine callables); all
other package actions go into `inner`. The ledger has exactly these sets.

## Step 4: the three variants

Checked: `Retrying.__call__`, `AsyncRetrying.__call__`/`__aiter__`/
`__anext__`/`iter`, `TornadoRetrying.__call__`, `BaseRetrying.__iter__`,
`wraps` (`wrapped_f`, `async_wrapped`, `retry_with`), `copy`, `statistics`
and `retry`'s choice (`is_coroutine_callable`, `_has_tornado`,
`tornado.gen.is_coroutine_function`, `_portable_async_sleep` with trio and
sniffio). Generator and coroutine rule: every coroutine function or
generator gets its edge from the scope that calls it (`async_wrapped ->
AsyncRetrying.__call__`, `AsyncRetrying.iter -> AsyncRetrying._run_*`, the
`wrap_to_async_func(...)(...)` sites -> `inner` and the async strategies,
`wrapped_f -> TornadoRetrying.__call__` through
`tornado.gen.coroutine.wrapper`); `BaseRetrying.__iter__`, `__anext__`,
`__aenter__`/`__aexit__` and `async_wrapped` have no package caller. One
difference, under rule A: the `wrapped_f` that `BaseRetrying.wraps` makes for
an `AsyncRetrying` (through `super().wraps`) never reaches a client, but rule
A gives `wrapped_f` the edges its body can make with that `self`, so
`AsyncRetrying.__call__` belongs at 404:24 (T6). (In the first pass, under the
brief's API rules, the auditor agreed with the writer here.)

## Step 5: the 152 edges that the trace does not confirm

| Class | Edges | Verdict |
|---|---|---|
| Open sets: strategies, hooks, combinator operands that no test passes at that site; the never-run operators `retry_all.__rand__`, `retry_any.__ror__` (sync and async) and their callers' edges to them; `BaseAction.__repr__`/`__str__`; the defensive `RuntimeError`s (a client can call a public strategy with a `RetryCallState` that has no outcome yet); `get_callback_name -> repr`; `sleep_using_event` and `tornado.gen.sleep` at `BaseRetrying.__iter__`/`Retrying.__call__`; `wrapped_f -> TornadoRetrying.__call__`/`tornado.gen.coroutine.wrapper` (the tracer does not attribute the generator that tornado starts) | 121 | certainly possible |
| Version branch `_utils.py:29`: the 7 `-> tenacity._utils.override` module edges, `tenacity._utils -> typing.TypeVar`, `_utils.override -> contextlib.suppress` | 9 | certainly possible (Python 3.10 and 3.11) |
| Async retry strategies at the sync sites `_run_retry`, sync `retry_any`, sync `retry_all` (4 each) | 12 | depends on the annotation ruling; in (decision 4) |
| `nap.sleep`/`sleep_using_event.__call__` at `AsyncRetrying.__call__`, `__anext__` and `TornadoRetrying.__call__` | 6 | depends on the ruling; in (decision 4, T4) |
| `-> RetryError.__str__` from `RetryCallState.__repr__`, `before_sleep_log.log_it`, `retry_if_exception_message._check` (nested retrying) | 3 | depends on the ruling; in: the package itself raises the `RetryError` inside the outer call |
| `retry.wrap -> warnings.warn` | 1 | depends on the ruling; in, through a client subclass of `retry_base` (T3) |
| cannot happen | 0 | |

## Step 6: callers of every function

56 functions and the 11 module nodes other than `tenacity.retry` have no
caller in the graph (the writer's list; the brief said 54). An `rg` of every
name finds only definitions, imports, `__all__`, comments, docstrings, base
class lists and attribute stores, except `__exit__` (called by `__aexit__`,
`__init__.py:255`, in the graph). The four groups are right: client syntax
(20), public API (26: the 2 wrappers, `retry_with`, `Future.construct`, the 3
log factories, 19 strategy constructors), abstract (5), Protocol stubs (5).
No dead code.

## Step 7: default rejections

- `|` (7 candidates, 75 sites): all 75 listed and checked. Every `|` in the
  package is in an evaluated annotation, a module-level type alias
  (`retry.py:63`, `stop.py:42`, `wait.py:58`, `asyncio/retry.py:59`,
  `_utils.py:104`) or an annotation string; the operands are classes, typing
  forms, TypeVars or `None`. There is no `|=`. Annotations of attribute
  targets in function bodies (`retry.py:251`, `__init__.py:614-622`) are never
  evaluated and are not sites. `other.__ror__(self)` (`retry.py:50`) is an
  explicit call and its entry accepts the 4 `__ror__`s. Correct.
- `__iter__` (2 candidates, 64 sites): all 64 checked. They iterate `*args`
  and `*dargs` tuples, `retries`/`stops`/`wait_funcs` tuples, `REPR_FIELDS`,
  the actions list, `dict.items()`, `sys.modules`, a `set`, and 2-argument
  `min`/`max`, which do not iterate. No `for` over a retrying object exists
  in the package. Correct.
- `+` (2 candidates, 11 sites): all 11 checked against an `rg` of every `+`,
  `+=` and `sum(` (one more hit is a docstring, `wait.py:287`). Numbers or
  `WRAPPER_ASSIGNMENTS` tuples only. Correct.
- `_RetryDecorated.__get__` (72 sites): a seeded sample of 40
  (`random.Random(20261111)`) checked. Receivers are retrying objects,
  strategies, functions, modules, a `threading.local`, `IterState` and
  `RetryAction`; none has a class attribute that is a `_RetryDecorated`. The
  node never runs anyway (overload stubs only). Correct.

## Step 8: implicit calls and formatting

All 42 format sites read. Only `{exception}` (`__init__.py:670`) and `{ex}`
(`before_sleep.py:47`) can format a package object (a `RetryError`); both
have `RetryError.__str__`. `{self.last_attempt}` in `RetryError.__str__`
formats a `concurrent.futures.Future`, whose `__repr__` prints only class
names. No strategy class defines `__str__`, `__repr__` or `__format__`.
`str(self.retry_object)` (`__init__.py:633`) has `BaseRetrying.__str__`;
`str(exception)` (`retry.py:258`, `260`) and `traceback.format_exception`
(`before_sleep.py:61`) have `RetryError.__str__`. `%` formatting: the only
uses are `sec_format % secs` and `sec_format % ...sleep` with floats; no
`logger.log` call passes lazy arguments. No package class defines `__bool__`,
`__len__`, `__eq__`, `__hash__`, `__contains__`, `__getattr__`,
`__set_name__` or `__init_subclass__`. Every load of `failed`,
`statistics`, `iter_state` and `seconds_since_start` (57 loads) has the
property where the receiver is of the right type, and a rejection where it
is a function or a `threading.local`. No difference.

## Step 9: rejections, notes, outside callees, rejected trace edges

- Rejections: every rejection at the sites of steps 2 to 4, and a seeded
  sample of 60 of the 140 rejection lines: all hold.
- Notes: all 141 read (the whole ledger was read). Wrong or incomplete: the
  two `self.event` notes (T1, T2, T5), the `tornadoweb` 62:33 note (T4); 785:26
  needs a note (T3).
- Outside callees: 40 checked (`time.sleep`, `time.monotonic`,
  `asyncio.sleep`, `trio.sleep`, `sniffio.current_async_library`,
  `functools.wraps`, `functools.partial.__call__`, `inspect.isclass`,
  `inspect.iscoroutinefunction`, `threading.local`, `tornado.gen.sleep`,
  `tornado.gen.coroutine`, `tornado.gen.coroutine.wrapper`,
  `tornado.gen.Return`, `tornado.gen.is_coroutine_function`,
  `<builtin>.Exception.__init__`, `<builtin>.BaseException.with_traceback`,
  the `concurrent.futures.Future` methods, `datetime.timedelta.total_seconds`,
  `dataclasses.dataclass.wrap`, `re.Pattern.match`, `re.compile`,
  `random.random`, `random.uniform`, `math.log`, `math.isfinite`,
  `traceback.format_exception`, `warnings.warn`, `typing.cast`,
  `typing.TypeVar`, `typing.ParamSpec`, `typing.overload`, `typing.override`,
  `abc.abstractmethod`, `sys.exc_info`, `contextlib.suppress` and some
  builtins). All names follow the micro-benchmark rules. 74 of the 76
  distinct outside names occur in the trace, by name or alias; the other two
  are `<builtin>.repr` and `tornado.gen.coroutine.wrapper` (the trace has the
  latter at a rejected edge, with this name). The 56
  `@override` sites each have `typing.override` and `tenacity._utils.override`.
  `IterState()`, `DoAttempt()`, `DoSleep(...)`, `_retry_never()`,
  `_retry_always()` and `_stop_never()` correctly have no edge.
- `tenacity.rejected.json`: all 7 entries stand under the rules, including
  the new ruling (see decision 3: `logger` is a Protocol; `retry_error_cls` is
  `type[RetryError]`; `sleep` and `fn` are bare callables).

## Step 10: checker and report

`check.py tenacity`: no errors; 557 edges (360 internal, 197 outside); the
trace confirms 405. `--report tenacity`: 0 undecided sites, 45 no-name sites
(all with notes), 0 unaccounted trace edges, and 5 sites with package callees
beyond the candidates. All 5 are right: `self.__class__(...)` in `copy`
(the 3 `__init__`s); `wrap_to_async_func(...)(retry_state)` in
`AsyncRetrying._run_retry` and the async `retry_any`/`retry_all` (the 4 async
`__call__`s, returned unwrapped); `traceback.format_exception` in
`before_sleep_log.log_it` (`RetryError.__str__`, called back by
`TracebackException`).

## Judgement

Completeness: very high. Under the conventions the writer first applied,
the auditor found no missing edge. The final rules added 3 edges: T1 and T2
from B4, and T6 from rule A (the writer's only reachability argument).
Precision: very high. No edge is impossible; the 22 edges that depend on
rulings follow the annotations and the role reading of B2. All findings are
applied in 80ffe0c.

## Re-check under rules A to C and the revised files

The lead's final rules arrived after the first pass, together with the news
that the files on disk are the revised version. The first pass had already
used the files on disk (557 edges), so no note was against the old version.
The auditor re-checked every finding and every exclusion of the ledger
against A to C.

1. **The removal of the 10 stacked-wrapper edges stands.** No example in
   `doc/source/index.rst`, `doc/source/api.rst` or `README.rst`, none of the
   59 release notes and no test puts `@retry` on a function that `@retry` or `wraps()`
   already decorated (searched: consecutive `@retry` decorators, `.wraps(`,
   `retry_with(`, `.copy(`, and every `retrying(...)` call in the tests). The
   tests that call `retry_with` call the new wrapper
   (`tests/test_tenacity.py:1707`, `1797`, `1805`, `1816`, `1828`, `2362`;
   `tests/test_asyncio.py:184-185`, where `thing1` is an argument, not the
   function), and the issue-519 tests stack a client decorator over `@retry`.
   The package never feeds a wrapper back either: `retry_with` passes the
   original `f` to `.wraps(f)` (`__init__.py:407`), `wrapped_f` passes the
   original `f` to `copy(f, ...)` (`__init__.py:404`), `AsyncRetrying.wraps`
   passes the original `fn` to `super().wraps(fn)` (`asyncio/__init__.py:212`),
   and `functools.wraps` stores the original in `__wrapped__`. So a wrapper as
   the function to retry is a package object passed where any callable is
   accepted (B3), and the edges stay out.
2. **Rule A (edges per function).** Every exclusion in the ledger was read
   again for a reachability argument. All but one restrict values (B1
   receivers: "AsyncRetrying overrides it", "self is a
   retry_unless_exception_type"; B2/B3 arguments: the function to retry,
   predicates, loggers, `retry_error_cls`; B2 "the package itself passes them
   there": `repr(cb)` at `_utils.py:96`, whose `cb` the package fills only with
   the function to retry). The one exception is judgement 11, which gives T6.
   Every `super()` call was checked for the same effect: only
   `AsyncRetrying.wraps -> BaseRetrying.wraps` runs an overridden method on a
   subclass receiver whose body dispatches on `self`. The other `super()`
   calls (`__init__`s, `retry_if_not_exception_message._check`,
   `wait_random_exponential.__call__`) make no call that depends on the class
   of `self`.
3. **The step-2 sentence and cross-role values (T7).** The final rules say,
   for a strategy call site, "the `__call__` of every public strategy class
   whose instances fit the parameter's annotated type". The annotations are
   unions of a base class and a structural `Callable`: `StopBaseT = stop_base |
   Callable[[RetryCallState], bool]` (`stop.py:42`), `RetryBaseT = retry_base |
   Callable[[RetryCallState], bool]` (`retry.py:63`), `WaitBaseT = wait_base |
   Callable[[RetryCallState], float | int]` (`wait.py:58`), and
   `retry_error_callback: Callable[[RetryCallState], t.Any]`
   (`__init__.py:270`). Strategies of another role fit these `Callable` arms:
   a retry strategy is a `Callable[[RetryCallState], bool]`, so it fits `stop`;
   a stop strategy fits `retry`; both fit `wait` (`bool` is a subtype of
   `int`); every strategy fits `retry_error_callback`. Read literally, the
   sentence adds 99 edges:

   | Site | Added callees | Edges |
   |---|---|---|
   | `__init__.py` 434:52 `_run_stop` | 10 sync retry | 10 |
   | 427:54 `_run_retry` | 7 stop | 7 |
   | `retry.py` 292:21, 309:21 (`*retries: "RetryBaseT"`) | 7 stop each | 14 |
   | 430:47 `_run_wait` | 7 stop + 10 sync retry | 17 |
   | `wait.py` 107:27 (`*strategies: "WaitBaseT"`) | 7 stop + 10 sync retry | 17 |
   | 440:28 `BaseRetrying.iter` `action(...)` (`retry_error_callback`) | 7 stop + 9 wait + 10 sync retry + 4 async retry | 30 |
   | `asyncio` 171:34 `AsyncRetrying.iter` `action(...)` | 4 async retry (kept unwrapped) | 4 |

   No other site changes: `stop_any`/`stop_all` take `*stops: stop_base`,
   `wait_chain` takes `*strategies: wait_base`, the async `retry_any`/`retry_all`
   take `retry_base | async_retry_base`, `inner` already has all 26 sync
   strategies, the hooks (`-> None`) admit no strategy, and the async
   strategies (they return a coroutine) fit no `bool` or `float` arm.

   **Recommendation: keep the writer's role reading (no change).** B2 admits
   "values that the package provides for that parameter's role" and "a base
   class ... the package implements for that purpose"; B4 says "a bare
   callable holds a client callback". The `Callable` arm of these unions is a
   bare callable, so it admits client callbacks; package values enter
   through the base class of the role (`stop_base`, `retry_base`,
   `wait_base`), the documentation (`doc/source/index.rst:449-482` gives a
   distinct contract for each role) or the defaults. The literal reading
   would also admit absurd values with no strategy role, which B3 excludes
   anyway: `AttemptManager` (its constructor takes a `RetryCallState`) or
   `RetryCallState.get_fn_name` as `retry_error_callback`. This reading keeps
   the 4 async retry strategies at the sync retry sites (they subclass
   `retry_base`, the base class of the role) and the nap sleeps at the async
   sleep sites (provided for the sleep role, admitted by the annotation).
4. **Rule C (public is mechanical).** No change. The private names that
   matter are `_retry_never`, `_retry_always` and `_stop_never` (private
   classes that the package instantiates as the public module-level
   `retry_never`, `retry_always` and `stop_never`, so in), and
   `_portable_async_sleep` (private; a callee only where it is the default).
   Everything else that the strategy sets use is public by its name.
5. **Steps 1 to 10.** The blind-sample statistics, the strategy sets, the
   default rejections, the callers, the formatting check and the rejected
   trace edges do not change. The untraced-edge classification does not
   change either. T1, T2 and T6 are all untraced, so with them the trace
   would confirm 405 of 560 edges (155 untraced). The release notes agree
   with the default rejection of `_RetryDecorated.__get__`:
   `releasenotes/notes/fix-decorated-method-binding-729ace6e58a9fefa.yaml`
   says it is "purely a static-analysis issue; the wrapper is a real function
   at runtime".

## Final check of the committed files (commit 80ffe0c)

`check.py tenacity`: no errors; 560 edges (361 internal, 199 outside); the
trace confirms 405; 7 rejected. The diff from the audited version
(`git diff ac5504f 80ffe0c`) was read line by line.

| Finding | Ledger | Graph | `tenacity.md` |
|---|---|---|---|
| T1 | `stop.py` 86:33 has `-> threading.Event.is_set` and a B4 note | edge present | Scope rules B4; dispatch table row `stop.py:86` |
| T2 | `nap.py` 43:24 has `-> threading.Event.wait` and a B4 note | edge present | Scope rules B4; dispatch table row `nap.py:43` |
| T3 | `__init__.py` 785:26 has a note naming the client `retry_base` subclass | edge kept | Scope rules B2 |
| T4 | `tornadoweb.py` 62:33 note cites `__init__.py:757` and `791-801` | edges kept | Scope rules B2, "Sleep values" |
| T5 | the 3 `logger.log` notes cite the Protocol (B4, B5); the 2 event notes cite B4 | - | old judgements 5 to 8 and 11 replaced by "Scope rules"; "Open questions: None" |
| T6 | `__init__.py` 404:24 has `-> tenacity.asyncio.AsyncRetrying.__call__`; the note cites `super()` and rule A | edge present | Scope rules A and B1 (`super()` exception); dispatch table row 404 (4 callees) |
| T7 | no change | no change | Scope rules B2: "Values of another role are not callees" |

The statistics of `tenacity.md` agree: 766 callees (763 + 3), 142 notes
(141 + 1), 560 edges, 155 edges from reading (129 in the package).

**Second look for reachability arguments (rule A).** Every rejection and
note of the committed ledger with a reason of the kind "runs for", "never",
"only caller", "reaches", "is called" or "calls it later" was read again (36
lines, not counting callee names such as `_stop_never`). None excludes an edge because its function is not called:

- "This method/generator/iter runs for Retrying and TornadoRetrying objects
  (AsyncRetrying overrides it)" (`_run_retry`, `_run_wait`, `_run_stop`,
  `iter`, `__iter__`): receivers (B1). `AsyncRetrying` overrides these methods
  and never calls them through `super()`, so the `super()` clause adds
  nothing there.
- "This `__call__` runs for retry_if_exception, ..." (`retry.py:103`) and
  "self is a retry_unless_exception_type / retry_if_not_exception_message"
  (`retry.py:163`, `281`): receivers (B1); none of those classes calls the
  base `__call__` through `super()`.
- "stored in the actions list; iter() calls it later" (10 rejections at the
  `_add_action_func` sites): the stored function is not called at that site;
  the call is an edge of `iter`/`inner`, where it is listed.
- "`repr(cb)` ... (the only caller is get_fn_name, `__init__.py:632`)"
  (`_utils.py:96`): a value argument (B2: the package passes only
  `RetryCallState.fn` there; any other caller passes client objects, and a
  package object there is B3). The words "the only caller" could suggest a
  caller argument, but the conclusion does not depend on who calls
  `get_callback_name`. Optional rewording only.
- "a RetryError reaches the outcome ..." (3 notes): a value argument for an
  accepted edge.
- The 4 default rejections give value reasons (Protocol never instantiated;
  operands of `|`, `+` and iteration).

Every `super()` call of the package was also checked against the new B1
clause: only `AsyncRetrying.wraps -> BaseRetrying.wraps` runs a base method
whose body (here, its closure `wrapped_f`) dispatches on the class of `self`.
That is T6, now in the graph.

**Remaining remarks (no edge effect, not counted as findings).**

- `tenacity.md` states rule C as "'Public' is judged on the public access
  path". The lead's rule C is mechanical on the qualified name. For tenacity
  the result is the same: `stop_never`, `retry_never` and `retry_always` are
  module-level instances that the package offers for their role (B2), so
  their private classes' `__call__` stay callees under either wording.
- `tenacity.md` counts "27 functions that no test runs", from the trace's
  `executed` list. Three of them (`BaseRetrying.__iter__`,
  `AsyncRetrying.__anext__`, `TornadoRetrying.__call__`) have traced
  out-edges, so 24 never ran (a validator limit, see "Two observations").
- The stacked-wrapper removal stands (see "Re-check", point 1): neither the
  documentation, nor the 59 release notes, nor the tests stack `@retry` or
  feed a wrapper back through `retry_with` or `copy`.


## Round 4 independent source-first audit (2026-11-16)

All original audit bytes above are preserved. A fresh source-only model and
complete AST inventory were frozen before baseline access. The comparison
covered all 560 graph pairs, 1,854 sites (including 1,087 implicit sites without
candidates), 12 default-rejected names, per-site exclusions/rejections and 57
bodies without explicit calls. Its 187 explicitly derived dynamic relations
all matched the baseline. No pair was added; one outside pair was removed:
190 nodes, 559 edges.

The pass resolves the source-model questions: a client
retry_base subclass supports the warning without admitting package strategies
as retried functions; changing client Future answers support the guarded
RuntimeError sites; generated dataclass constructors have no node; pinned
Tornado decorator source supports the wrapper callback; and predicate dispatch
is limited to subclasses inheriting the relevant __call__ body. Typed public
state input supports RetryError string formatting independently of opaque
callback results. The BaseException.with_traceback pair is removed because the cause receiver
stays client-origin data under B5. The considered public typed TryAgain state
witness admits the outer exception but does not supply a B4 concrete receiver
role for its cause; the universal exception-family contract is insufficient. Current judgements and six ledger
notes record the evidence. Dependency code was read inertly only.
