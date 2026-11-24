# structlog: judgements of the ground truth

Release 26.1.0 (commit `8174a86`). Analysed source: `src/structlog/` (root
`src`): 21 modules, 346 functions (12 lambdas), 64 classes.
`pyproject.toml:13` sets `requires-python = ">=3.10"`, so the supported
versions are 3.10 and later. The only declared dependency is
`typing-extensions` on Python 3.10.

The ledger is `structlog.ledger`; the graph `structlog.json` is generated
from it. `structlog.rejected.json` holds the 13 trace edges that are not
package edges. The trace is `../dynamic/structlog.json`.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in structlog-review.json (audit record `2026-11-15/structlog-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 828 | 5 | 39 | 862 |

- Name running asyncio loops by `SelectorEventLoop` and `ProactorEventLoop`,
  replacing five defining-base names with ten concrete-receiver edges.
- `LoggerFactory()("")` produces the root logger and adds 20 `RootLogger`
  method edges. Binary unbuffered stdout adds four `FileIO` and Windows
  console edges. Python 3.15 adds `types.FrameLocalsProxyType.items`.
- Four package callbacks follow documented object roles: proxy context
  access, nested JSON observers, and two paths that format `ReprWrapper`.
- Two previously rejected trace pairs now have source-supported `FileIO`
  aliases, so they move from rejected to confirmed.

## Architecture, as the ledger uses it

- A bound logger carries a context (a dict) and a list of processors, and
  wraps a logger (`_logger`). `BoundLoggerBase._proxy_to_logger`
  (`_base.py:193`) runs the processors (`_process_event`) on a copy of the
  context and calls the method of the wrapped logger by name
  (`getattr(self._logger, method_name)(*args, **kw)`, `_base.py:224`).
- `get_logger` and `wrap_logger` return a `BoundLoggerLazyProxy`
  (`_config.py:303`). Its `bind` builds the bound logger from the global
  configuration `_CONFIG` and can cache it by storing the closure
  `finalized_bind` on the instance (`_config.py:390`). Its `__getattr__`
  forwards every other attribute to a new bound logger.
- The default wrapper class is a "filtering" class that
  `_make_filtering_bound_logger` builds with `type()` (`_native.py:264`).
  Its methods are the closures `meth`, `ameth`, `log`, `alog`, the
  functions `_nop`, `_anop`, `exception`, `aexception`, and two lambdas.
  Six such classes exist (`_native.py:272-277`).
- The deprecated `threadlocal` module makes context classes with
  `wrap_dict` (`threadlocal.py:81`): subclasses of `_ThreadLocalDictWrapper`
  whose instances keep their dict in a thread-local `_tl.dict_` and find
  every dict method through `__getattr__`. With greenlet installed, `_tl`
  is a `GreenThreadLocal` (`_greenlets.py`).
- The output loggers (`_output.py`, `testing.py`) bind every logging
  method name to one `msg` method, except `CapturingLogger`, which serves
  every name through `__getattr__` (`testing.py:190`).

## Role sets

The ledger header lists these sets; each value site uses one of them.

| Set | Members | Evidence |
|---|---|---|
| Bound loggers (BL) | `BoundLoggerBase`, `structlog.BoundLogger`, `stdlib.BoundLogger`, `twisted.BoundLogger`, the six `BoundLoggerFilteringAt*` classes, `stdlib.AsyncBoundLogger` | docstrings of `configure` (wrapper_class) and of the classes; the default `make_filtering_bound_logger(0)` |
| Wrapped loggers (W) | `PrintLogger`, `WriteLogger`, `BytesLogger`, `ReturnLogger`, `CapturingLogger`, a `logging.Logger` or `logging.RootLogger`, the module `twisted.python.log` | the factories below; `docs/recipes.md:127` and `docs/thread-local.md:107` wrap a `PrintLogger` |
| Logger factories (F) | `PrintLoggerFactory` (default), `WriteLoggerFactory`, `BytesLoggerFactory`, `ReturnLoggerFactory`, `CapturingLoggerFactory`, `stdlib.LoggerFactory`, `twisted.LoggerFactory`, the class `PrintLogger` | docstrings ("To be used with `structlog.configure`'s logger_factory"), `docs/`; `tests/test_stdlib.py:1651` passes `PrintLogger` |
| Processors (P, 29) | 11 functions and 18 `__call__`s (ledger header) | `docs/processors.md`, the API reference |
| Contexts (C) | `dict`, wrap_dict instances | `Context = dict[Any, Any]` (`typing.py:47`), default `dict` (`_config.py:57`) |

Client callables in these roles (Mock objects, `simplejson.dumps`, client
streams, client processors) are client callbacks.

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. The Protocol stubs of `typing.py` have no calls. `GreenThreadLocal`,
`RichTracebackFormatter.__call__` and `better_traceback` never ran in the
tests; their edges come from reading.

**B1. Receivers.**
- `self` in a `BoundLoggerBase` method is a BoundLoggerBase or one of its
  package subclasses. So `self.bind()` (`_base.py:91, 103, 119`) has
  `BoundLoggerBase.bind` and `stdlib.BoundLogger.bind`; the proxy's `bind`
  and `AsyncBoundLogger.bind` are rejected.
- In the proxy, `self.bind` is `BoundLoggerLazyProxy.bind` or the closure
  `finalized_bind` (`_config.py:400, 403, 414, 424`).
- `exception` and `aexception` (`_native.py:44, 52`) are only methods of
  the filtering classes, so `self.error` is `meth` or `_nop`
  (`_native.py:49, 74`).
- The Protocols `BindableLogger`, `FilteringBoundLogger`,
  `ExceptionTransformer` and `ColumnFormatter` are never receivers.

**B2. Arguments and stored values.** Each value site has a note on where
its values come from. The annotations here are mostly bare `Callable`s or
`Any` (`WrappedLogger = Any`), so the sets come from the defaults, the
docstrings, `docs/` and the tests.

**B3. Not considered.** A package object that a client puts into an event
dict, logs, or passes where any object is accepted (for example a bound
logger as a value for `JSONRenderer`, `ConsoleRenderer._repr` or
`_json_fallback_handler`).

**B4. Concrete outside types.** `Context = dict[Any, Any]` and
`type[Context]` fix `dict` (judgement 8). The event dict is a
`MutableMapping` by annotation (abstract), but the package always passes a
dict: the copy of `_base.py:168` or the dict of `ProcessorFormatter.format`
(`stdlib.py:1160, 1166`). So event-dict methods are `<builtin>.dict.*`.

**B5. Client objects are opaque.** The streams that clients pass to
`WriteLogger`, `BytesLogger` and `PlainFileLogObserver`; the client's
values in event dicts; the message of a foreign log record.

**C. Public.** `structlog/__init__.py` re-exports the API. The public
`make_filtering_bound_logger` factory exposes the filtering classes, and
`wrap_dict` exposes its context classes. Their public arguments are in
scope for the documented roles. `get_logger` and `wrap_logger` expose
lazy proxies. `threadlocal.ThreadLocal` directly aliases `GreenThreadLocal`
when greenlet is importable. `_FixedFindCallerLogger` and `_Configuration`
have only private construction paths. Local closures
retain their actual enclosing values; a public factory does not expose
every nested function as an arbitrary callable.

## Judgement calls

1. **Optional imports** (`dev.py:38-54`, `tracebacks.py:28-32`,
   `threadlocal.py:37-44`, `__init__.py:45-48`): both sides run. rich,
   colorama, better_exceptions and greenlet are not installed; their calls
   are named as missing modules (`rich.console.Console`,
   `rich.pretty.traverse`, `colorama.init`, `better_exceptions.format_exception`,
   `greenlet.getcurrent`). A missing library calls nothing back. Twisted and
   zope.interface are installed in the test environment but not on the
   machine where the ledger was written: their names follow the trace
   (`twisted.python.failure.Failure.getTraceback`, `zope.interface.implementer`)
   or the source of structlog. After the audit, Twisted 26.4.0 was read
   from the pinned wheel (see "Audit outcome and rulings").
2. **Platform branch** `if _IS_WINDOWS:` (`dev.py:70`): Windows is
   supported (colorama). Both definitions of `_init_terminal` are one node;
   the Windows body gives `SystemError`, `str.format`, `colorama.deinit`,
   `colorama.init`.
3. **Version branches.** `sys.version_info >= (3, 11)` at `_base.py:22`,
   `stdlib.py:27`, `typing.py:30` only imports `Self`. `tracebacks.py:266`
   (exception groups) runs on 3.11 and later. `frame.f_locals` is a dict on
   3.10 to 3.12 and a `FrameLocalsProxy` from 3.13. The call at
   `tracebacks.py:332:57` has `<builtin>.dict.items`, the historical
   `builtins.FrameLocalsProxy.items` name where no public alias exists,
   and `types.FrameLocalsProxyType.items` on Python 3.15, which exposes
   that public class alias. These are names across supported versions.
4. **Callbacks through logging.** When the wrapped logger is a
   `logging.Logger`, `getattr(self._logger, method_name)(...)`
   (`_base.py:224:54`) calls back `_FixedFindCallerLogger.findCaller`
   (`Logger._log` calls `self.findCaller`) and `ProcessorFormatter.format`
   (the formatter of a handler, the setup of `docs/standard-library.md`).
   The trace has both. By the same reading, `stdlib.BoundLogger.handle` and
   `callHandlers` (`stdlib.py:374:28`, `400:34`) get `ProcessorFormatter.format`
   (from reading only). Global B5 includes library callbacks through
   objects registered by the documented setup. This includes the formatter
   and logger class above; no project-specific ruling remains open.
5. **Callbacks through twisted** (`_base.py:224:54`, `twisted.py:219:30`).
   With `twisted.LoggerFactory`, the wrapped logger is the module
   `twisted.python.log`. Its `err` calls `repr()` on `_stuff`; with
   `twisted.JSONRenderer`, `_stuff` is a `ReprWrapper` (the docstring at
   `twisted.py:125` says so): `ReprWrapper.__repr__`. Twisted's publisher
   calls the observers that the client registered; the package's observers
   are `JSONLogObserverWrapper` and `PlainFileLogObserver` (the documented
   pairing with `JSONRenderer` and `plainJSONStdOutLogger`). In
   `PlainFileLogObserver.__call__`, `textFromEventDict` applies `safe_str`
   to the message, a `ReprWrapper`, whose `str()` falls back to
   `__repr__`. These 5 edges come from reading only; after the audit they
   were checked against the source of Twisted 26.4.0 and kept (ruling L1).
6. **Frame locals in tracebacks** (`tracebacks.py:173:32`, `repr(obj)` in
   `to_repr`). `obj` is a local of a frame of the logged exception. The
   tests log an exception whose test frame holds the proxy of `get_logger`
   (`tests/test_tracebacks.py:1024-1040`): the trace has
   `to_repr -> BoundLoggerLazyProxy.__repr__`, which the ledger keeps. The
   writer first rejected the other package objects; after the audit (F1)
   the ruling adds six `__repr__` callees (see "Audit outcome and rulings").
7. **`dict.update` with a wrapped context** (`contextvars.py:77:15`,
   `threadlocal.py:252:15`): `ctx.update(get_context(bl))` looks up `keys`
   on the argument; a wrap_dict instance finds it only through
   `__getattr__`, so `_ThreadLocalDictWrapper.__getattr__` is a callee
   (then `update` raises `TypeError` for a non-empty context, because the
   wrapper has no `__getitem__`). From reading only.
8. **`type[Context]` as dict** (`_config.py:355:38`, `410:32`,
   `threadlocal.py:123:50`, `196:66`). `context_class` and the `dict_class`
   of `wrap_dict` are typed `type[Context]`, that is `type[dict]`. The
   ledger names `<builtin>.dict` at these class calls, as B4 names methods
   of a fixed type, although the client is the one who passes `dict`. The
   global B4 rule explicitly fixes a concrete `type[T]` to `T`, and names
   this case. The `<builtin>.dict` targets therefore stay at all four
   sites. The outside-client callback rule does not override the concrete
   type annotation. No project-specific ruling remains open.
9. **`ExceptionTransformer`** (`processors.py:418:60`, `675:44`): the
   annotation is the package's own Protocol. Its implementations are
   `_format_exception` (the default) and `ExceptionDictTransformer`
   (`dict_tracebacks`; the `ExceptionRenderer` docstring names it). The
   ledger takes both for `ExceptionRenderer` and `ExceptionPrettyPrinter`
   (the Protocol's docstring names both processors). Global B2 explicitly
   admits the documented implementations of a package Protocol and names
   this example. `ExceptionPrettyPrinter.__call__ ->
   ExceptionDictTransformer.__call__` is from reading only.
10. **Attribute names forwarded by the proxy** (`_config.py:426:23`,
    `getattr(bl, name)`): generic `BoundLogger.__getattr__` serves missing
    logging method names. The six stdlib getters `name`, `level`, `parent`,
    `propagate`, `handlers`, and `disabled` also run: tests/test_stdlib.py:239-252
    uses these exact names, and the documented lazy proxy exposes that same
    bound-logger interface. This is B3's named-property exception. The lazy
    proxy's own `_context` resolves before `__getattr__`; it adds no getter here.
11. **Method names on the wrapped logger** (`_base.py:224:54`): the names
    that the package's bound loggers pass (debug, info, warning, error,
    critical, exception; msg and err for twisted). The generic BoundLogger
    passes any client name; `logging.Logger.warn` (3.10 to 3.12) and other
    names that only a client chooses are not taken (B3).
12. **`copy.error`** (`_output.py:93, 201, 323`) is an alias of the class
    `copy.Error`; named `copy.Error`, the public name in `copy.__all__`
    (the trace's name).
13. **`twisted.python.log.msg`** is the bound method `theLogPublisher.msg`
    (`twisted/python/log.py:306, 334`); named
    `twisted.python.log.LogPublisher.msg` by the rule for methods.
    `synchronize(LogPublisher)` (`log.py:280`) replaces the class attribute
    with the closure `sync` of `twisted.python.threadable._sync`, which
    calls the original method; the class attribute is an attribute path,
    so the method rule applies, not the rule for closures. No trace edge
    checks the name.
14. **Dataclasses and NamedTuples.** `ColumnStyles`, `Column`,
    `KeyValueColumnFormatter`, `RichTracebackFormatter` (`dev.py`) and
    `Frame`, `SyntaxError_`, `Stack`, `Trace` (`tracebacks.py`) are
    dataclasses; `CapturedCall` and `CallsiteParameterAdder._RecordMapping`
    are NamedTuples. Their calls have a note and no callee.
15. **`raise DropEvent`** and the other raises of package exceptions without
    a call (`stdlib.py:840`, `testing.py:63`, `dev.py:776, 781`) give no
    edge (README, Implicit calls); the three trace edges to
    `<builtin>.BaseException.__init__` are rejected.
16. **Executor callbacks.** The lambdas that `run_in_executor` runs in the
    default executor's thread are callees of the `run_in_executor` sites
    (`_native.py:72, 191, 235`, `stdlib.py:465, 673`). The trace misses
    them (T1: threads that library code starts).
17. **Renderers of `EventAdapter`** (`twisted.py:326, 330`): the default
    `ConsoleRenderer`, `KeyValueRenderer` (`docs/twisted.md:47`) and the
    twisted `JSONRenderer` (the docstring).
18. **`AsyncBoundLogger` in `as_immutable`** (`threadlocal.py:126:30`): it
    has no attribute `_logger` (slots), so the argument raises
    `AttributeError` before `logger.__class__(...)` is called; no
    `AsyncBoundLogger.__init__` edge. Its `_context` property is a callee
    at `_base.py:245`, `threadlocal.py:123, 124, 154, 158, 159`.

## Default rejections

These are current scanner decisions after explicit site exceptions.

| Candidates | Pairs decided per candidate | Accepted explicitly at |
|---|---:|---|
| `structlog.__getattr__` (module) | 964 | nowhere |
| `BoundLoggerLazyProxy.__getattr__` | 964 | nowhere |
| `_generic.BoundLogger.__getattr__` | 964 | `_config.py:426:23` |
| `GreenThreadLocal.__getattr__`, `__setattr__` | 964, 179 | thread-local storage reads/writes |
| `CapturingLogger.__getattr__` | 964 | wrapped-logger dispatch and stdlib passthrough properties/methods |
| `_ThreadLocalDictWrapper.__getattr__` | 955 | context dict-method forwarding, dict.update callbacks, and the nine same-lookup `_dict` fallback sites |
| the three `__eq__` | 206 each | context comparison and explicit `__eq__` calls |
| `_ThreadLocalDictWrapper.__len__`, `__iter__`, `__setitem__` | 147, 141, 61 | nowhere |
| the eight `__repr__` | 66 each | wrapped context/logger formatting, Twisted/logging callbacks, and traceback locals |

21 candidates decide 7,449 candidate-site pairs. Explicit entries take
precedence. The round-4 descriptor witness below explains why a lazy `_dict`
getter can invoke `__getattr__` while the first lookup is still active.

## Trace edges rejected (13)

Mock objects that the tests pass as processors, logger factory and observer
(4); the tests' own streams for `WriteLogger`, `BytesLogger` and
`PlainFileLogObserver` (6); `BaseException.__init__` of a `raise` without a
call (3).

## Limits of the tools met

- The site finder does not mark `self.value_repr(value)` (`dev.py:310:39`)
  and `col.formatter(col.key, val)` (`dev.py:938:26`) as value sites: the
  dataclass fields are annotations without a value, which bind nothing for
  the tool. They are value calls; the entries have notes.

## Statistics

| | Count |
|---|---|
| Sites | 2726 (755 call, 55 decorator, 64 class, 5 with, 110 iter, 43 mapping, 22 await, 127 op, 97 getitem, 61 setitem, 6 delitem, 1019 getattr, 178 setattr, 127 truth, 52 format, 5 raise) |
| Ledger entries | 917 |
| Value sites | 88 |
| Callee lines / rejection lines / exclusion lines / notes | 1117 / 231 / 0 / 240 |
| Default rejections | 21 candidates, 7449 pairs |
| Nodes | 367 |
| Edges | 908: 450 in the package, 458 to 184 callees outside |
| Confirmed by the retained trace accounting | 682 of 908 (75.1%) |
| From reading only | 226 |
| Functions that the tests run (retained prior trace result) | 306 of 346 |

## Audit outcome and rulings (earlier audit)

The independent audit (`structlog.audit.md`) re-derived 156 sites blind: 152
agree, and the auditor was wrong at the other 4 (3 naming, 1 incomplete). It
found no edge of the writer that cannot happen. Its exhaustive checks gave two
missed-edge findings (F1, F2) and four cases for the lead (L1 to L4), all of
them judgements that this file had flagged. The lead's rulings, as applied:

- **F1 / L3, frame locals (`tracebacks.py:173:32`, judgement 6): accepted,
  +6 inside edges.** `to_repr` formats every frame local of the logged
  traceback, by default. A package class is a callee only if an instance of
  it is a local or an argument in a frame of a package function that can
  raise an exception that the package documents or raises on purpose; client
  frames stay opaque. Checked one by one (the note at the site names each
  frame):
  - `BoundLoggerBase.__repr__`: `BoundLoggerBase.unbind` (`self`, `bl`) on
    its documented `KeyError` (`_base.py:88-93`); `_process_event` (`self`)
    on its documented `ValueError` (`_base.py:147-191`).
  - `_ThreadLocalDictWrapper.__repr__`: `__delitem__` (`self`) when that
    `KeyError` rises from a wrap_dict context (`threadlocal.py:218-219`).
  - `PrintLogger`, `WriteLogger`, `BytesLogger.__repr__`: their
    `__getstate__` and `__deepcopy__` (`self`) raise `PicklingError` and
    `copy.Error` on purpose (`_output.py:73, 93, 179, 201, 295, 323`); and
    the parameter `_` of `LogfmtRenderer.__call__` (the wrapped logger),
    which documents and raises `ValueError` (`processors.py:144-145, 167`).
  - `CapturingLogger.__repr__`: the parameter `_` of
    `LogfmtRenderer.__call__` with `CapturingLoggerFactory`.
  - Kept: `BoundLoggerLazyProxy.__repr__` (the frame of the proxy's
    `unbind` on the same `KeyError`, and the trace). Out:
    `ReprWrapper.__repr__` (no raising package frame holds one) and
    `ReturnLogger` (no `__repr__`).
- **F2 (`twisted.py:248:51`): accepted after reading Twisted, +1 inside
  edge.** `JSONLogObserverWrapper.__call__ -> ReprWrapper.__repr__`.
- **J5, Twisted's behaviour: verified, all edges kept.** The wheel
  `twisted-26.4.0-py3-none-any.whl` was found in the scan's cache
  (`/private/tmp/claude-501/heldout4-scan-work/deps/wheels/`). Its SHA-256,
  `dc25ea0e…4c0`, equals the pin of `requirements/structlog.txt`. It was
  read as a zip; nothing was installed, imported or run. What the source
  does (`twisted/python/log.py`, `twisted/logger/_legacy.py`,
  `twisted/logger/_observer.py`):
  - `err` calls `msg(repr(_stuff), ...)` when `_stuff` is no `Failure` and
    no `Exception` (`log.py:131`): `_proxy_to_logger -> ReprWrapper.__repr__`
    for `err` with the twisted `JSONRenderer`.
  - `LogPublisher.msg` passes every event to `publishToNewObserver`
    (`log.py:277`), which calls `textFromEventDict` (`_legacy.py:121`).
    `textFromEventDict` applies `reflect.safe_str` (that is `str()`) to the
    message items (`log.py:438`), or to `why` in its error branch
    (`log.py:420-424`): `ReprWrapper.__repr__` also for `msg`, and the F2
    edge for the `why` tuple of `EventAdapter` with the twisted
    `JSONRenderer`.
  - `log.addObserver` and `startLoggingWithObserver` wrap a legacy observer
    in `LegacyLogObserverWrapper`, which calls it (`_legacy.py:92`); the
    global publisher calls its observers in turn, synchronously
    (`_observer.py:59-83`): `_proxy_to_logger -> JSONLogObserverWrapper.__call__`
    and `-> PlainFileLogObserver.__call__`.
  - The name `twisted.python.log.LogPublisher.msg` stays (judgement 13);
    at run time the class attribute is the `sync` wrapper of
    `twisted.python.threadable`.
- **L1, callbacks through registered objects (judgements 4, 5): kept,** by
  the lead's rule: when a package call hands an object to library code, or
  starts library code that dispatches to an object that the package's
  documented setup registers (a `ProcessorFormatter` on a logging handler,
  a structlog observer in Twisted's publisher, `_FixedFindCallerLogger` as
  the logging class), and the library calls a package function, the package
  function that makes the library call is the caller.
- **L2, `type[Context]` (judgement 8): B4.** `type[Context]` fixes `dict`;
  `<builtin>.dict` stays at the four sites.
- **L4, package Protocols (judgement 9):** a Protocol of the package names
  the classes that the package documents as its implementations;
  `ExceptionPrettyPrinter.__call__ -> ExceptionDictTransformer.__call__`
  stays.

Edges: 821 to 828 (393 to 400 inside; 428 outside unchanged). All 7 new edges
come from reading only.


## Round 3 source-first review: lazy and wrapped logger passthroughs

At `_config.py:426`, `BoundLoggerLazyProxy.__getattr__` binds the configured
bound logger and calls `getattr(bl, name)`. For `structlog.stdlib.BoundLogger`,
`name`, `level`, `parent`, `propagate`, `handlers`, and `disabled` invoke six
property getters. `tests/test_stdlib.py:239-252` explicitly uses all six names
in `getattr` on that interface. The documented standard-library configuration
exposes the same bound-logger interface through `get_logger()` and its lazy
proxy. These satisfy scope B3's named-property exception. The proxy's own
`_context` resolves before `__getattr__`; it adds no further edge at this site.

The tests also construct `structlog.stdlib.BoundLogger` with a
`CapturingLogger`: `tests/test_stdlib.py:59-63,389` and the `cl` fixture in
`tests/conftest.py:69-71`. Its inherited constructor accepts and stores that
logger. This is explicit evidence for the constructor role under B2. The
`_logger: logging.Logger` field annotation does not discard this tested value.
Scope A covers every passthrough body on that valid instance. The six property
bodies and thirteen method bodies reach `CapturingLogger.__getattr__` at their
attribute reads. The thirteen method calls also invoke its returned `log`
closure, whose `*args, **kw` accepts their arguments. These add 32 pairs.
Separate processor logger parameters keep their annotations and their own
named input evidence; this does not admit a general processor cross-product.

The round adds 38 pairs at 38 relations and removes none: the graph has
900 pairs and 1,108 site relations. There are no independent site-only
metadata corrections. The audit read all 21 runtime modules and checked all
862 baseline pairs, 1,070 baseline relations, 2,726 scanner sites, default
rejections, own argument bindings, zero-edge bodies, and outside names.
The frozen source-only model preceded baseline access; exact relation
normalization followed comparison. Runtime source and support inputs match
the official pinned commit archive; only export-substituted `.git_archival.txt`
differs. No target, dependency, test, example, generated code, PyCG, or tracing
run served as a semantic oracle. Structural and origin checks read the
existing trace only after semantic adjudication.


## Round 4 source-first review (2026-11-16)

All 900 baseline pairs were retained. Eight missing pairs at nine property
sites were added, giving 908 pairs and 1,117 relations with 367 nodes.

The public `wrap_dict` accepts `type[Context]`, including a client dict subclass.
Its constructor can raise `AttributeError` while `_dict` lazily creates the
thread-local dictionary at `threadlocal.py:196`. The interpreter then calls
`_ThreadLocalDictWrapper.__getattr__` during the same lookup. This adds edges
from `__init__`, `__repr__`, `__iter__`, `__setitem__`, `__delitem__`, `__len__`,
`__getattr__`, and `processors._json_fallback_handler`. Constructor sites
184 and 186 account for the ninth relation. A completed wrapper can be used
for its first access in a fresh thread, where the dict is absent; no failed
object is reused and no internal state is assigned. For `__init__`, its first
construction suffices even though it later fails. `as_immutable` gets no new
edge because its preceding `_tl.dict_` read requires existing storage.

Two pre-existing metadata groups were corrected: judgement 10's stale rejection
of the six forwarded stdlib getters, and the older scanner/default table.
Graph-derived totals changed with the additions. Historical audit text remains
preserved. The audit covered all 2,726 sites and 367 bodies, including 100
zero-edge bodies, the 21 defaults, and the 13 retained trace rejections.

Supported scope remains Python >=3.10 without a classifier upper bound;
historic PyPy mentions do not establish current alternative support. Normal,
`-O`, and `-OO` are the round's working union, not a claimed user approval.
There is no executable assertion or docstring-dependent branch here.

The source model and input/site/body inventories were frozen before baseline
comparison. All evidence was read as inert text/AST/JSON. No target, dependency,
test, example or generated code, PyCG, or trace was executed. Root verification
and final acceptance follow the agent handoff.
