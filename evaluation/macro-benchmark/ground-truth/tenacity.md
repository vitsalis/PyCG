# tenacity: judgements

Global-rule audit (2026-11-15): 0 removed edges, 0 added
edges; 560 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Ground truth of tenacity 9.2.1 (commit 4410996), analysed source
`tenacity/` (12 modules, 179 functions with 3 lambdas). The ledger is
`tenacity.ledger`; the graph `tenacity.json` is generated from it. The
supported versions are Python 3.10 and later (`requires-python = ">=3.10"`).
Paths below are relative to `tenacity/`. The independent audit is in
`tenacity.audit.md`.

## Architecture in short

`BaseRetrying` holds the strategies that the client passes (`sleep`, `stop`,
`wait`, `retry`, `before`, `after`, `before_sleep`, `retry_error_cls`,
`retry_error_callback`). Its subclasses are `Retrying` (sync), `AsyncRetrying`
(asyncio and trio, `asyncio/__init__.py`) and `TornadoRetrying` (a
`tornado.gen.coroutine`, `tornadoweb.py`). Each attempt runs `iter()`, which
fills `iter_state.actions` through `_add_action_func` (14 calls,
`__init__.py:449-500`) and then calls every action. `AsyncRetrying` wraps each
action in `_utils.wrap_to_async_func`, which returns a coroutine callable
unchanged and wraps anything else in the coroutine function `inner`.

## Scope rules

The rules are those of `macro-benchmark/README.md` ("Scope rules"), which is
the authority; each is summarised here, followed by how this ledger applies
it. Where a decision left out a package node that is not a candidate of the
site, the entry has an `exclude` line with the rule (42 lines: the function
to retry, strategies of another role, the actions that `inner` or the async
`iter` call, `_portable_async_sleep` at the other sleep sites, two `_check`
methods).

**A. Edges are per function.** The edges of a function are the calls its body
can make when it runs; whether and how the function itself gets called does
not matter. The global rule also permits rejecting trace edges for
client-supplied values, implicit outside calls, excluded private-API inputs,
and incorrect callee names. These categories do not remove the body edges
of an uncalled function.

- Functions that only the client calls (strategy constructors, operators,
  `__iter__`, `__anext__`, `retry_with`, `Future.construct`, ...) have all the
  edges of their bodies.
- `wrapped_f` (`__init__.py:390`) is a closure of `BaseRetrying.wraps`, and
  `self` of `BaseRetrying.wraps` can be an `AsyncRetrying` (rule B1: it calls
  the method on itself through `super()`, `asyncio/__init__.py:212`). So the
  closure can hold an `AsyncRetrying`. `AsyncRetrying.wraps` then drops that
  closure and returns `async_wrapped`; under rule A that does not matter:
  `copy(f, ...)` (`__init__.py:404`) has `AsyncRetrying.__call__` as a callee,
  beside `Retrying.__call__`, `tornado.gen.coroutine.wrapper` and
  `TornadoRetrying.__call__`. (The first versions of this ledger and the audit
  left this edge out because that `wrapped_f` never reaches a client.)
- The 8 rejected trace edges have client-supplied callees or opaque client
  attribute receivers (see "Trace edges rejected as client callbacks").

**B. Edges are limited by the values that can reach a call site.**

Public functions receive the values that clients or the package can pass.
Private functions use the receivers and arguments of their actual package
calls. An uncalled private function uses the public parameter rules, so
rule A still gives its body edges. In tenacity, this restricts the private
strategy runners, action helpers and `_utils` helpers to their actual
inputs. `Any`, `object`, `type` and a bare `Callable` do not name arbitrary
package values. Client assignments to public attributes count only where
tests or documentation make those assignments.

- **B1. Receivers.** `self` in a method of class `C` is an instance of `C`,
  of a package subclass that inherits the method, or of a subclass that calls
  the method explicitly on itself (`super()`), limited to instances that the
  package or a client can create (a private class only where the package
  makes it; an `abc`-abstract class or a `Protocol` is not a receiver).
  - `BaseRetrying.__iter__`, `_run_retry`, `_run_wait`, `_run_stop` and
    `iter` run for `Retrying` and `TornadoRetrying` only: `AsyncRetrying`
    overrides them and never calls them through `super()`. So `self.iter` at
    `__init__.py:514` is `BaseRetrying.iter`, the actions at line 440 are the
    sync ones, and `tornado.gen.sleep` (default of `TornadoRetrying`) is a
    callee of `self.sleep` at line 519.
  - `BaseRetrying.wraps` runs also for an `AsyncRetrying`, which calls it
    through `super()` (`asyncio/__init__.py:212`); see rule A.
  - `_begin_iter`, `_post_retry_check_actions` and `_post_stop_check_actions`
    run for all three classes, so `self._add_action_func` has both
    definitions.
  - `retry_if_exception.__call__` (`retry.py:95`) runs for the classes that
    inherit it, so its `self.predicate` is the `_check` of
    `retry_if_exception_type`, `retry_if_not_exception_type` and
    `retry_if_exception_message`; `retry_unless_exception_type` and
    `retry_if_not_exception_message` override `__call__` and call their own
    `_check` (`retry.py:163`, `281`).
  - The abstract `__call__` of `BaseRetrying`, `retry_base`,
    `async_retry_base`, `stop_base` and `wait_base`, and the `Protocol`
    methods (`_RetryDecorated.*`, `_AsyncRetryDecorator.__call__`,
    `LoggerProtocol.log`) never run. `_RetryDecorated.__get__` is a default
    rejection.
- **B2. Arguments and stored values** are client objects, the values that the
  package defines for the parameter's role, and the package's defaults. A
  package value is in scope for a role when the annotation names its type or
  a base class that the package implements for that purpose, or when the
  package's own code, tests or documented examples pass it there; in a union
  of a package base class and a bare `Callable`, only the base-class arm
  names package values, and a bare-callable annotation is evidence for none.
  A value from outside the package that the client passes is a client
  callback, also when the docs show it as an example.
  - The evidence for the strategy roles is the API reference
    (`doc/source/api.rst`): for each of `after`, `before`, `before_sleep`,
    `sleep`, `retry`, `stop` and `wait` it says "Those functions can be used
    as the `<role>` keyword argument of `tenacity.retry`" and documents the
    module of that role. `retry.wrap` passes `**dkw` unchanged to
    `AsyncRetrying`, `TornadoRetrying` or `Retrying` (`__init__.py:791-803`),
    so the package itself carries these values to all three classes. The
    annotations `RetryBaseT`, `StopBaseT`, `WaitBaseT` (base class arms
    `retry_base`, `stop_base`, `wait_base`) agree for the strategies.
  - So each strategy call gets the values of its role and the defaults of the
    classes that reach it: the stop set (7), the wait set (9), the sync retry
    set (10), the hooks (6) at the action sites, `RetryError` for
    `retry_error_cls`, and the sleep values below. The combinators' operands
    (`stop_any`, `stop_all`, `wait_combine`, `wait_chain`, sync and async
    `retry_any`/`retry_all`) have the same sets.
  - Async retry strategies at the sync retry sites (`__init__.py:427`,
    `retry.py:292`, `309`): they subclass `retry_base`, the base class that
    the annotations name (`RetryBaseT`, `retry.py:63`; `__init__.py:264`;
    `retry.py:287`, `304`), and the sync `@overload` of `retry` names their
    type (`tasyncio.retry.RetryBaseT`, `__init__.py:760`). Their `__call__` is
    a coroutine function: called, never awaited.
  - Sleep values. Every `sleep` annotation in the package is a bare
    `Callable` (`__init__.py:261`, `757`; `asyncio/__init__.py:78-79`;
    `tornadoweb.py:34`), so none of them is evidence. The evidence for the
    nap functions `nap.sleep` and `sleep_using_event` is the API reference
    ("Nap Functions: Those functions can be used as the `sleep` keyword
    argument of `tenacity.retry`", `doc/source/api.rst:50-57`) together with
    `retry.wrap` passing `**dkw` to the class it picks; `nap.sleep` is also
    the default of `BaseRetrying.__init__` (`__init__.py:261`). No test and no
    example passes `sleep_using_event`; its documented role is enough.
    `Retrying.__call__` (`__init__.py:560`): `nap.sleep`,
    `sleep_using_event.__call__`. `BaseRetrying.__iter__` (line 519): the
    same and `tornado.gen.sleep`. `AsyncRetrying.__call__` and `__anext__`
    (`asyncio/__init__.py:139`, `206`): the default `_portable_async_sleep`,
    and the nap functions, which `@retry(sleep=tenacity.nap.sleep)` on a
    coroutine function passes there (called, then `await None` raises
    `TypeError`). `TornadoRetrying.__call__` (`tornadoweb.py:62`): the default
    `tornado.gen.sleep`, and the nap functions, which the same decorator on a
    tornado coroutine passes there (`__init__.py:797-801`). No sleep edge
    lacked this evidence, so none was removed.
  - Values of another role are not callees: a stop strategy as `retry`, a
    wait strategy as `before` (they fit only the bare-`Callable` arm, and the
    API reference offers them for their own role); `exclude` lines record
    this at the strategy and action sites. `retry_error_callback` has no
    package value: default `None`, a bare-`Callable` annotation, and the API
    reference offers nothing for it.
  - `RetryCallState.set_exception` accepts a tuple containing `BaseException`.
    A client can construct the package's `RetryError` with a completed
    `Future` and store it through this public method. Then `repr(state)` and
    the public message retry strategies reach `RetryError.__str__` at
    `__init__.py:670` and `retry.py:258, 260`. After `controller.begin()`,
    `controller.iter(state)` with `retry_always` and `before_sleep_log`
    creates `next_action` and reaches the formatting sites at
    `before_sleep.py:47, 61` (`traceback` calls `str()` back). This typed
    public-state witness supports all five sites. An exception escaping
    a client callback stays opaque under B5.
  - `retry.wrap -> warnings.warn` (`__init__.py:785`): the call runs only when
    `f` is a `retry_base` instance. A package strategy there is out of scope
    (B3), but a client can pass an instance of its own `retry_base` subclass
    as the function (a client object), so the edge stays.
  - Client callbacks: the function to retry, the predicates of
    `retry_if_exception`, `retry_if_result`, `retry_if_not_result`,
    `wait_exception` and the async ones, a client's `retry_error_callback`
    or `retry_error_cls` subclass, and outside values that the client passes
    as a strategy (`trio.sleep`, `asyncio.sleep`, shown in the docs).
- **B3. An arbitrary package object where any callable is accepted** is not
  considered. The function to retry (`fn`, `f`) takes any callable, and the
  package defines no value for that role. So the 9 sites that call it
  (`__init__.py:392`, `544`, `553`; `asyncio/__init__.py:119`, `120`, `130`,
  `132`, `220`; `tornadoweb.py:55`) and `repr(cb)` (`_utils.py:96`) have no
  package callee. This excludes a strategy (`@retry(stop_after_attempt(3))`,
  or the `retry_base` case that `retry.wrap` warns about), a retrying object,
  and an already decorated wrapper (stacked `@retry`; an earlier version had
  these 10 edges). The return value of the retried function is client data:
  no package `__str__`/`__repr__` at `__init__.py:672` and
  `before_sleep.py:55`.
- **B4. A method call on a parameter whose annotation or documentation fixes
  a concrete outside type** is an edge to that type's method; an abstract
  type (a `Protocol`, `Callable`) does not fix the class of a client object.
  - `event: "threading.Event"` (`stop.py:81`, `nap.py:37`):
    `stop_when_event_set.__call__ -> threading.Event.is_set` (`stop.py:86`)
    and `sleep_using_event.__call__ -> threading.Event.wait` (`nap.py:43`).
  - `time_unit: int | float | timedelta` (`_utils.py:107`):
    `to_seconds -> datetime.timedelta.total_seconds`.
  - `match: str | re.Pattern[str] | None` and `re.compile`
    (`retry.py:238`, `252`): `_check -> re.Pattern.match`.
  - `logger: _utils.LoggerProtocol` (`before.py:30`, `after.py:30`,
    `before_sleep.py:31`) is a `Protocol`, so `logger.log(...)` has no callee,
    and the trace edge to `logging.Logger.log` stays rejected. The
    predicates are typed `Callable`: no callee.
- **B5. A client-supplied object is opaque.** A method call on it has no
  outside callee, whatever the docs' examples or the tests pass: the logger,
  the predicates, the function to retry.

**C. "Public" is judged on the access path.** A class or function is public
if a client can reach it through a path with no component that starts with
an underscore (dunder names excepted). It is private if its docstring or
documentation marks it private (`:meta private:`); no docstring in tenacity
does.

- Public: the strategy instances `stop_never`, `retry_never`, `retry_always`
  (instances of the private classes `_stop_never`, `_retry_never`,
  `_retry_always`), the async strategies (`tenacity.asyncio.retry_if_result`,
  ...), `nap.sleep` (`tenacity.sleep`), `sleep_using_event`, the hooks.
- Private: `tenacity.asyncio._portable_async_sleep` (a callee only at the
  `AsyncRetrying` sleep sites, where it is the default), and `_utils` helpers
  that have no public access path. The fallback `_utils.override` is public
  through imports such as `tenacity.override` and `tenacity.wait.override`;
  its node keeps its defining name `tenacity._utils.override`.

## Other judgement calls

1. **`if TYPE_CHECKING:` blocks** do not run (README default):
   `__init__.py:100-111`, `_utils.py:23-28`, `after.py:21`, `before.py:21`,
   `before_sleep.py:22`, `nap.py:21`, `retry.py:23`, `stop.py:22`,
   `wait.py:26`, `asyncio/__init__.py:46`, `asyncio/retry.py:22`,
   `tornadoweb.py:23`. They hold imports only; no call is lost.
2. **Version branch `_utils.py:29`.** On 3.12+ `override` is
   `typing.override`; on 3.10 and 3.11 it is the backport
   `tenacity._utils.override` (its `TypeVar` call, `_utils.py:32`, runs there).
   Both versions are supported, so each of the 56 `@override` sites has both
   callees, with a note. On 3.12+ the name of the callee is `typing.override`
   (where `_utils` takes it), not `tenacity._utils.override`, which is the node
   of the backport.
3. **Optional imports.** Both sides run (README default).
   - tornado: `__init__.py:87-90` and `812-813`. `tornadoweb.py` is in scope
     (`projects.toml`). `retry.wrap` calls `TornadoRetrying` only after
     `_has_tornado()` (`__init__.py:797-801`).
   - trio and sniffio: `asyncio/__init__.py:61-67` imports them only if trio
     is already in `sys.modules`. `_portable_async_sleep` calls
     `sniffio.current_async_library`, `trio.sleep` and `asyncio.sleep`.
4. **Annotations.** No module has `from __future__ import annotations`, so
   annotations are sites. All 75 `|` sites are type unions (classes, typing
   forms, TypeVars, None): `type.__or__`, never the `__or__`/`__ror__` of a
   strategy instance. A default rejection decides them.
5. **Instantiations with no edge.** `IterState()` (`__init__.py:378`): a
   dataclass; its generated `__init__` has no node, and the `list()` of its
   `default_factory` is a call of that generated code. `DoAttempt()`,
   `DoSleep(...)` (a `float` subclass), `_stop_never()`, `_retry_never()`,
   `_retry_always()`: the first `__init__` in the MRO is `object.__init__`.
6. **tornado coroutine.** `TornadoRetrying.__call__` is decorated with
   `tornado.gen.coroutine` (`tornadoweb.py:40`). A call of a
   `TornadoRetrying` object (`copy(f, ...)` in `wrapped_f`, `__init__.py:404`)
   calls `tornado.gen.coroutine.wrapper`, which calls the generator function
   `TornadoRetrying.__call__` back. Both are callees of that site (callback
   rule and generator rule of the micro-benchmark).
7. **`wrap_to_async_func`** (`_utils.py:123`). The outer call
   `wrap_to_async_func(x)(retry_state)` (`asyncio/__init__.py:149, 155, 162`,
   `asyncio/retry.py:113, 137`) calls `x` itself when `x` is a coroutine
   callable (the async retry strategies), else `inner`. `inner` calls `x`
   (`_utils.py:130`); that call belongs to `inner`.
8. **Names of callees outside the package.** `concurrent.futures.Future.*`
   (the package names `futures.Future`, `__init__.py:565`);
   `<builtin>.Exception.__init__` (`RetryError(Exception)`, the nearest class
   outside the package that the code names as base);
   `random.random`, `random.uniform`, `warnings.warn`, `threading.local`,
   `asyncio.sleep`, `trio.sleep`, `sniffio.current_async_library` (the paths
   the package uses; the trace lists them as aliases);
   `dataclasses.dataclass.wrap` and `functools.partial.__call__` (the
   decorators made by `dataclass(slots=True)` and `functools.wraps(...)`);
   `tornado.gen.coroutine.wrapper`; `datetime.timedelta.total_seconds`;
   `threading.Event.is_set`, `threading.Event.wait`. A builtin or library
   callable that library code calls back is not an edge (`list` as the
   `default_factory` of `IterState`).
9. **One node for two names.** The module `tenacity/retry.py` and the
   function `retry` (`__init__.py:773`) are both `tenacity.retry`
   (README). The edges of the module body and of the function are merged.
10. **`%` sites.** Four `%` operators propose the package's `__str__` and
    `__repr__` (README: what the conversions of a non-literal template
    call). `pos_num % 100` and `pos_num % 10` (`_utils.py:64`, `77`) are
    numeric modulo on an `int` (`pos_num: int`; the package passes
    `attempt_number`). `sec_format % secs` (`after.py:42`) and
    `sec_format % retry_state.next_action.sleep` (`before_sleep.py:55`)
    format one float (a difference of `time.monotonic()` values; `float(...)`
    in `RetryAction.__init__`), whatever conversions the client's
    `sec_format` has. No package callee.

## Default rejections

| Candidates | Sites | Reason |
|---|---|---|
| `_RetryDecorated.__get__` | 44 | a `typing.Protocol` never instantiated; `@t.overload` stubs |
| `__or__`/`__ror__` of `retry_base`, `retry_any`, `async_retry_base`, async `retry_any`, `stop_base` (7) | 75 each | every `|` is a type union |
| `BaseRetrying.__iter__`, `AsyncRetrying.__iter__` | 64 each | iteration only over tuples, lists, dict views, sets, genexprs |
| `wait_base.__add__`, `__radd__` | 11 each | every `+`, `+=`, `sum()` adds numbers or tuples |

`other.__ror__(self)` (`retry.py:50`) accepts its four `__ror__` callees in
its own entry. The defaults decide 18 explicit sites, all checked:

- `BaseRetrying.__iter__` and `AsyncRetrying.__iter__` at the builtins that
  can iterate: `set()` (`retry.py:190`) gets no argument; `any`/`all`
  (`retry.py:292`, `309`, `stop.py:53`, `64`) and `sum` (`wait.py:107`) get
  the generator expression of their line; every `min`/`max` (`wait.py:133`
  twice, `198` twice, `238` twice, `244` three times, `327` three times) gets
  two or more numbers, so it iterates nothing. No argument is a retrying
  object.
- `wait_base.__add__`/`__radd__` at `sum(x(retry_state) for x in
  self.wait_funcs)` (`wait.py:107`): `sum` adds what the wait values return,
  and every package wait strategy returns a number (`to_seconds` gives a
  float; `random.random`/`uniform`; `max`/`min` of numbers;
  `float(sum(...))`; `wait_chain` and `wait_exception` pass on another
  strategy's number or the client predicate's, typed `float`), while a
  client callable of `WaitBaseT` returns `float | int` (`wait.py:58`). A
  strategy object never reaches `sum`, so neither `__radd__` (with the
  start value 0) nor `__add__` runs. That entry also decides these
  candidates explicitly.

## Open-set dispatch sites

The strategy sets:

| Set | Size | Members |
|---|---|---|
| stop | 7 | `__call__` of `stop_any`, `stop_all`, `_stop_never`, `stop_when_event_set`, `stop_after_attempt`, `stop_after_delay`, `stop_before_delay` |
| wait | 9 | `__call__` of `wait_fixed` (also `wait_none`), `wait_random`, `wait_combine`, `wait_chain`, `wait_exception`, `wait_incrementing`, `wait_exponential`, `wait_random_exponential`, `wait_exponential_jitter` |
| sync retry | 10 | `__call__` of `_retry_never`, `_retry_always`, `retry_if_exception` (also `_type`, `_not_exception_type`, `_exception_message`), `retry_unless_exception_type`, `retry_if_exception_cause_type`, `retry_if_result`, `retry_if_not_result`, `retry_if_not_exception_message`, `retry_any`, `retry_all` |
| async retry | 4 | `__call__` of `tenacity.asyncio.retry.retry_if_exception`, `retry_if_result`, `retry_any`, `retry_all` |
| hooks | 6 | `before_nothing`, `before_log.log_it`, `after_nothing`, `after_log.log_it`, `before_sleep_nothing`, `before_sleep_log.log_it` |

| Site | Callee | Callees |
|---|---|---|
| `__init__.py:427` `BaseRetrying._run_retry` | `self.retry(...)` | 14: sync retry + async retry |
| `__init__.py:430` `BaseRetrying._run_wait` | `self.wait(...)` | 9: wait |
| `__init__.py:434` `BaseRetrying._run_stop` | `self.stop(...)` | 7: stop |
| `__init__.py:440` `BaseRetrying.iter` | `action(...)` | 16: 10 actions of the package + hooks |
| `asyncio/__init__.py:171` `AsyncRetrying.iter` | `await action(...)` | 4: `inner`, `AsyncRetrying._run_retry`, `_run_wait`, `_run_stop` |
| `_utils.py:130` `wrap_to_async_func.inner` | `call(...)` | 39: 7 actions + hooks + stop + wait + sync retry |
| `asyncio/__init__.py:149` `AsyncRetrying._run_retry` | `wrap_to_async_func(self.retry)(...)` | 5: `inner` + async retry |
| `asyncio/__init__.py:155`, `162` `_run_wait`, `_run_stop` | `wrap_to_async_func(...)(...)` | 1: `inner` |
| `asyncio/retry.py:113`, `137` async `retry_any`, `retry_all` | `wrap_to_async_func(r)(...)` | 5 each: `inner` + async retry |
| `retry.py:292`, `309` `retry_any`, `retry_all` | `r(...)` | 14 each: sync retry + async retry |
| `stop.py:53`, `64` `stop_any`, `stop_all` | `x(...)` | 7 each: stop |
| `wait.py:107` `wait_combine` | `x(...)` | 9: wait |
| `wait.py:135` `wait_chain` | `wait_func(...)` | 9: wait |
| `__init__.py:519` `BaseRetrying.__iter__` | `self.sleep(do)` | 3: `nap.sleep`, `sleep_using_event.__call__`, `tornado.gen.sleep` |
| `__init__.py:560` `Retrying.__call__` | `self.sleep(do)` | 2: `nap.sleep`, `sleep_using_event.__call__` |
| `asyncio/__init__.py:139`, `206` `AsyncRetrying.__call__`, `__anext__` | `self.sleep(do)` | 3 each: `_portable_async_sleep`, `nap.sleep`, `sleep_using_event.__call__` |
| `tornadoweb.py:62` `TornadoRetrying.__call__` | `self.sleep(do)` | 3: `tornado.gen.sleep`, `nap.sleep`, `sleep_using_event.__call__` |
| `__init__.py:480`, `482` `exc_check` | `self.retry_error_cls(fut)`, `retry_exc.reraise()` | 1 each: `RetryError.__init__`, `RetryError.reraise` |
| `__init__.py:306` `BaseRetrying.copy` | `self.__class__(...)` | 3: `BaseRetrying.__init__` (Retrying), `AsyncRetrying.__init__`, `TornadoRetrying.__init__` |
| `__init__.py:404` `wrapped_f` | `copy(f, ...)` | 4: `Retrying.__call__`, `tornado.gen.coroutine.wrapper`, `TornadoRetrying.__call__`, `AsyncRetrying.__call__` (rule A) |
| `asyncio/__init__.py:232` `async_wrapped` | `copy(fn, ...)` | 1: `AsyncRetrying.__call__` |
| `retry.py:36`, `50` `retry_base.__and__`, `__or__` | `other.__rand__`, `other.__ror__` | 4 each: the overrides in the sync and async classes |
| `retry.py:103` `retry_if_exception.__call__` | `self.predicate(...)` | 3: `_check` of `retry_if_exception_type`, `retry_if_not_exception_type`, `retry_if_exception_message` |
| `retry.py:163`, `281` | `self.predicate(...)` | 1 each: `retry_unless_exception_type._check`, `retry_if_not_exception_message._check` |
| `stop.py:86`, `nap.py:43` | `self.event.is_set()`, `self.event.wait(...)` | 1 each: `threading.Event.is_set`, `threading.Event.wait` (B4) |
| function to retry: `__init__.py:392`, `544`, `553`, `asyncio/__init__.py:119`, `120`, `130`, `132`, `220`, `tornadoweb.py:55` | `f(...)`, `fn(...)` | 0: client callback (B3) |
| client objects: `after.py:39`, `before.py:36`, `before_sleep.py:64` (loggers), predicates at `retry.py:212`, `228`, `wait.py:175`, `asyncio/retry.py:81`, `99` | | 0 (B4, B5) |

## Functions that no site calls

56 functions and the 11 module nodes other than `tenacity.retry` have no
caller in the graph. Imports add no edges, so modules have none. The
functions:

- **Reached by client syntax:** `AttemptManager.__enter__`, `__aenter__`,
  `__aexit__` (`with`/`async with` on an attempt; `__exit__` is also called by
  `__aexit__`); `BaseRetrying.__iter__` and `AsyncRetrying.__iter__` (`for`);
  `AsyncRetrying.__aiter__`, `__anext__` (`async for`);
  `BaseRetrying.__getstate__`, `__setstate__` (pickle, `copy`);
  `BaseRetrying.__repr__`, `RetryCallState.__repr__`, `BaseAction.__str__`
  (`repr`/`str` by the client; no package site formats these objects);
  operators `retry_base.__and__`, `__or__`, `async_retry_base.__and__`,
  `__or__`, `stop_base.__and__`, `__or__`, `wait_base.__add__`, `__radd__`
  (`&`, `|`, `+`, `sum()` in client code; `__rand__`/`__ror__` are also called
  from `retry.py:36`, `50`).
- **Public API called by the client:** the decorated functions that
  `wraps()` returns, `BaseRetrying.wraps.wrapped_f` and
  `AsyncRetrying.wraps.async_wrapped` (the client calls them in place of its
  function), `BaseRetrying.wraps.retry_with` (`f.retry_with(...)`),
  `Future.construct`, the factories `after_log`, `before_log`,
  `before_sleep_log`, and the constructors of the strategies that no default
  and no operator makes: `sleep_using_event`, the async `retry_if_exception`
  and `retry_if_result`, `retry_if_exception_cause_type`,
  `retry_if_exception_message`, `retry_if_not_exception_type`,
  `retry_if_not_result`, `retry_if_result`, `retry_unless_exception_type`,
  `stop_after_attempt`, `stop_after_delay`, `stop_before_delay`,
  `stop_when_event_set`, `wait_chain`, `wait_exception`, `wait_exponential`,
  `wait_exponential_jitter`, `wait_incrementing`, `wait_random`.
- **Abstract, never run:** `BaseRetrying.__call__`, `retry_base.__call__`,
  `async_retry_base.__call__`, `stop_base.__call__`, `wait_base.__call__`.
- **`typing.Protocol` stubs, never run:** `_RetryDecorated.__call__`,
  `__get__`, `retry_with`, `_AsyncRetryDecorator.__call__`,
  `_utils.LoggerProtocol.log`.

No dead code was found: every function outside these four groups has a
caller in the graph.

## Trace edges rejected as client callbacks

`tenacity.rejected.json` holds 8 trace edges. Seven callees are objects that
the tests pass in: `ValueError` as `retry_error_cls`
(`tests/test_tenacity.py:1811`; the parameter is typed `type[RetryError]`), a
list's `append` as `sleep` (`tests/test_tenacity.py:543`, `610`), `MagicMock`
loggers (`tests/test_after.py:30`, `tests/test_tenacity.py:165`), an
`AsyncMock` sleep (`tests/test_asyncio.py:644`), a `logging.Logger`
(`tests/test_tenacity.py:1893`; the parameter is typed with the `Protocol`
`LoggerProtocol`, B4), and test functions decorated with
`tornado.gen.coroutine` (`tests/test_tornado.py:29`, `36`). The eighth is
`RetryError.reraise -> <builtin>.BaseException.with_traceback`: its cause
receiver remains opaque client data (B5; see the round-4 judgement below).

## Statistics

| | Count |
|---|---|
| Sites | 1,854 total; 767 ledger-relevant: 415 call, 79 decorator, 3 with, 44 iter, 91 op, 93 getattr, 42 format |
| Ledger entries | 592: 415 call, 79 decorator, 42 format, 49 getattr, 4 op, 3 with |
| Sites that only defaults decide | 175: 87 op, 44 iter, 44 getattr |
| Value sites (no candidates by name, or a value callee such as `self.__class__(...)`) | 46 (all with a note) |
| Ledger lines | 765 callees, 146 rejections (69 `reject *`), 42 exclusions (605 nodes), 149 notes, 4 default rejections (12 candidates) |
| Edges | 559: 361 in the package, 198 to outside callees |
| Edges that the trace confirms | 404 (232 in the package) |
| Edges only from reading | 155 (129 in the package) |
| Trace | 412 edges: 404 in the graph, 8 rejected; 156 of 179 functions run |

The 155 edges from reading are mostly the open sets above (strategy classes
that no test passes at that site, the async flavours at sync sites and the
nap functions at the async and tornado sleep sites, `RetryError.__str__`),
the `@override` edges of the version that the trace interpreter (3.14) does
not take (`tenacity._utils.override`), the tornado and sleep callees of
`BaseRetrying.__iter__`, the `threading.Event` methods, `wrapped_f ->
AsyncRetrying.__call__`, and calls in the 23 functions that no test runs
(abstract methods and `Protocol` stubs among them).

## Open questions

None. The questions of the earlier versions (the function to retry, client
objects of a fixed outside type) are settled by the scope rules B3 and B4.


## Round 4 source-first verification (2026-11-16)

Two source-only models were frozen before baseline disclosure. This pass reviewed
all 560 existing pairs and all 1,854 AST sites, including 1,087 implicit sites
with no package candidate. The graph now has 190 nodes and 559 edges: no added
pairs and one removed pair. The independent model explicitly derived 187 dynamic pairs;
all were present. The 12 default-rejected names, all per-site exclusions and
rejections, public/private receiver roles, 57 bodies without explicit calls,
and optional/version branches were checked against current global rules.

The `RetryError.reraise` call at `__init__.py:215` loses the pair to
`<builtin>.BaseException.with_traceback`. The call can execute, but its cause
receiver is client-origin data and remains opaque under B5. The package does
not construct this cause, and `isinstance(exc, TryAgain)` checks the outer
exception, not its cause. A considered alternate witness stores a normally
chained package `TryAgain` through public `RetryCallState.set_exception`, then
calls `RetryError(state.outcome).reraise()`. That typed API admits the outer
TryAgain but does not give its client-provided cause a concrete outside
receiver role under B4. Python's universal exception-family contract does not
supply the missing package parameter or documented concrete receiver type.
This alternate witness is rejected; it does not broaden B4 for client
attributes in this project alone.

The inconsistent-outcome guards at `retry.py:102,162,280` and
`asyncio/retry.py:80` are possible with a client `Future` subclass whose
`exception()` answers change. The tested public assignment to
`RetryCallState.outcome` (`tests/test_tenacity.py:77`) admits such a receiver.
The `failed` getter observes the first answer; the next call observes `None`.
The client's method stays opaque, but its control-flow effects count. Each
caller already has a separate unset-outcome `RuntimeError` site, so this
clarification does not change graph pairs.

The Tornado definition-decorator exception is pinned to an inertly read
Tornado 6.6 wheel, `tornado-6.6-cp311-abi3-macosx_10_9_universal2.whl`, under
`audits/2026-11-15/pass-2/recovered-inputs/`, SHA-256
`01abf15429d64f04ccfafc238b191cc2c177108b7a331f4461707ad77198c8c2`.
Its `tornado/gen.py` SHA-256 is
`d08e2d46799f1e5a4c2fb7aec291829a57a2b5a9ecde22b363235b4d4dadd3c2`.
`coroutine.wrapper` at line 206 calls `ctx_run(func, *args, **kwargs)` at
line 212. This supports the wrapper and package-generator callback at
`__init__.py:404`. The wheel requires Python >=3.11; the earlier admitted
Tornado 6.0–6.5 source files were also read as AST data and have the same
wrapper-to-function route, covering the release's Python 3.10 lower bound.
Their source hashes are recorded in the round-4 review artifact. This reading
is limited to the definition decorator; ordinary Tornado calls remain opaque
missing-library paths. No target, dependency or tests were imported or run.
