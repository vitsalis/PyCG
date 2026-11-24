# structlog: independent audit of the ground truth

Release 26.1.0, commit `8174a86a2f14b5bd295eded733ff5fffc12aa173`
(held-out set 4). Audited files: the ground truth as its writer left it
(commit `9e32849`): `structlog.ledger` (904 entries, 175 notes, 21 default
rejections over 7536 candidate-site pairs), `structlog.json` (367 nodes, 821
edges: 393 in the package, 428 to 161 callees outside), `structlog.rejected.json`
(15 edges) and `structlog.md` (18 judgements). The trace confirms 680 edges;
141 come from reading only. `check.py --benchmark-dir macro-benchmark-heldout-4
structlog` reports no errors.

I judged the files by the scope rules of `macro-benchmark/README.md` (A,
B1 to B5, C, and the lead's rulings of the earlier sets). I read the source,
`docs/`, `tests/` and `pyproject.toml` as data. I ran nothing of the package
and used no static analysis tool. Twisted, zope.interface, rich, greenlet,
colorama and better-exceptions are not installed on this machine; I could not
read them (see "What I could not check").

**Result.** The ledger is careful and complete. The blind sample of 156
sites found no edge of the writer that cannot happen and no missed edge.
The exhaustive checks found 2 missed-edge findings (F1 medium, F2 low; up to
+7 edges) and 4 cases for the lead (L1 to L4), each a judgement that the
writer already flagged. With F1 and F2 the graph would have 828 edges (400
in the package, 428 outside).

## Findings

| Id | Kind | Site | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | missed edges (with judgement 6) | `tracebacks.py:173:32` `repr(obj)` in `to_repr` | See "F1" below. `extract` passes every frame local to `to_repr` (`tracebacks.py:325`) when `show_locals` is true, the default (`SHOW_LOCALS = True`, line 49; `ExceptionDictTransformer.__init__`, line 430; `dict_tracebacks`, `processors.py:444`). The frames of the logged traceback include the package's own frames when a package function raised, and their locals are package objects. The entry rejects them because "no test or documented example puts another package object there"; but the package's own frames put them there, and "what the package's own calls pass counts in full" (README, B). | +6: `tracebacks.to_repr` -> `_base.BoundLoggerBase.__repr__`, `threadlocal._ThreadLocalDictWrapper.__repr__`, `_output.PrintLogger.__repr__`, `_output.WriteLogger.__repr__`, `_output.BytesLogger.__repr__`, `testing.CapturingLogger.__repr__` | likely (`BoundLoggerBase.__repr__`: high) |
| F2 | missed edge | `twisted.py:248:51` `textFromEventDict(eventDict)` in `JSONLogObserverWrapper.__call__` | `EventAdapter` with the twisted `JSONRenderer` as `dictRenderer` (the ledger's own role set at `326:47`) takes its `err` path (`twisted.py:314-328`): `_why` is the tuple `((ReprWrapper(...),), {"_structlog": True})` that `JSONRenderer.__call__` returns (`twisted.py:187-196`). `log.err(_stuff=failure, _why=...)` publishes `why` with `isError` and `failure` and without `_structlog`, so `JSONLogObserverWrapper.__call__` calls `textFromEventDict` (line 244). As I remember Twisted's source, `textFromEventDict` applies `reflect.safe_str` to `why` when the message is empty; `str()` of the tuple calls `ReprWrapper.__repr__`. | +1: `twisted.JSONLogObserverWrapper.__call__` -> `twisted.ReprWrapper.__repr__` | unverified (Twisted 26.4.0 not read) |

### F1 in detail

Three public-API programs reach `to_repr` with package objects in package
frames (a fresh process each; `rich` is missing, so `to_repr` takes the
`repr(obj)` branch, line 173):

1. `structlog.configure(processors=[structlog.processors.dict_tracebacks,
   structlog.processors.JSONRenderer()])`; `log = structlog.get_logger()`;
   `try: log.unbind("missing")` `except KeyError: log.exception("failed")`.
   `BoundLoggerBase.unbind` documents `KeyError` (`_base.py:88-89`) and raises
   it at line 93. Its frame holds `self` and `bl`, bound loggers:
   `BoundLoggerBase.__repr__`. (The frame of `BoundLoggerLazyProxy.unbind`
   holds the proxy: the edge to its `__repr__` that the ledger already has.)
2. The same with `context_class=structlog.threadlocal.wrap_dict(dict)`: the
   `KeyError` rises in `_ThreadLocalDictWrapper.__delitem__`
   (`threadlocal.py:218-219`), whose local `self` is the wrapper:
   `_ThreadLocalDictWrapper.__repr__`.
3. `processors=[dict_tracebacks, LogfmtRenderer()]` and a key with a blank:
   `LogfmtRenderer.__call__` documents and raises `ValueError`
   (`processors.py:144-145, 165-167`). Its parameter `_` is the wrapped logger
   (`get_locals` hides only names that start with `__` by default, line 305),
   so the frame holds a `PrintLogger` with the default factory, and a
   `WriteLogger`, `BytesLogger` or `CapturingLogger` with their documented
   factories: their `__repr__`. (Also `PrintLogger.__getstate__` and
   `__deepcopy__` raise for a client file, `_output.py:73, 93`, with `self` as
   local.)

`ReturnLogger` has no `__repr__`. No package frame holds a `ReprWrapper` in a
local on a documented raise, so `ReprWrapper.__repr__` stays out. If the lead
reads the logged exception as a client object whose frames are opaque (B5),
the proxy edge that the ledger keeps from the trace must go too; the two
readings should not be mixed.

### Disagreements of the sample that were naming only (no finding)

`_output.py:93:29, 201:29, 323:29`: I wrote `copy.error`; the ledger has
`copy.Error`. `copy.error` is an alias outside `copy.__all__` (`['Error',
'copy', 'deepcopy', 'replace']`), so the writer's name is right (README: a
re-exported name outside `__all__` is named where it is defined). My error.

## Cases for the lead

| Id | Writer's judgement | Question | My proposal | Edges at stake |
|---|---|---|---|---|
| L1 | 4, 5 | Library call-backs through objects that the client registers globally: a `ProcessorFormatter` on a logging handler; a structlog observer in Twisted's publisher. The README has a callback rule for library objects that the package creates or passes (B5), and none for handlers or observers that the client registers. | Keep the writer's edges. Proposed rule: "A package object that the client registers with a library in the role that the package documents for it (a `ProcessorFormatter` on a handler, a package observer in Twisted's publisher) is a callee of the package site whose library call dispatches to it." The objects are package values in documented roles, as processors are. | 5: `ProcessorFormatter.format` at `_base.py:224:54` (in the trace), `stdlib.py:374:28`, `400:34`; `JSONLogObserverWrapper.__call__`, `PlainFileLogObserver.__call__` at `224:54` |
| L2 | 8 | `type[Context]` (= `type[dict]`) for `context_class` and `dict_class`: B4 (the annotation fixes `dict`) or B2's last sentence (`dict` that the client passes is a client callback). | B4: a call of a value annotated `type[T]`, T a concrete outside type, calls T; this matches B4 naming `threading.Event.set` on a client's event. Add the case to B4. | 0 at `_config.py:355:38`, `410:32`; 2 trace edges at `threadlocal.py:123:50`, `196:66` would move to the rejected edges |
| L3 | 6 | Frame locals in `to_repr` | See F1. | +6 |
| L4 | 9 | B2 speaks only of Protocols from outside the package. structlog's own Protocols (`ExceptionTransformer`, `ColumnFormatter`, `BindableLogger`) are implemented structurally by package classes that the docstrings name (`ExceptionDictTransformer`; `KeyValueColumnFormatter`, `LogLevelColumnFormatter`). | Keep the writer's reading: a package Protocol in an annotation names the package classes that the package documents or passes as its implementations. Add this to B2. | 1 from reading (`processors.py:675:44` -> `ExceptionDictTransformer.__call__`) |

Judgement 11 (method names on the wrapped logger) and judgement 10 (names
forwarded by the proxy) follow B3 and the aiocache rule; I agree and need no
ruling.

## Step 1: blind re-derivation

**Sample.** Skeleton without the ledger: `check.py --benchmark-dir
$TMPDIR/heldout4-audit-structlog --skeleton structlog` (a copy of
`projects.toml` and a link to `projects/`). It has 2519 sites (755 call, 55
decorator, 1019 getattr, 178 setattr, 512 others). I numbered them in
skeleton order, module by module, (line, column) within, and drew
`random.Random(20261111).sample(range(2519), 70)`, plus all 88 value sites
(2 overlap): 156 sites. The draw was plain: 29 of the 70 are attribute loads
and 20 are explicit sites; the 88 value sites are explicit calls, so explicit
sites dominate the whole. I wrote my callees, and the role sets they use,
to `$TMPDIR/heldout4-audit-structlog/blind.md` before I opened any file of
the writer or the trace.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random, implicit (getattr, setattr, setitem, getitem, iter, truth) | 50 | 50 | 0 |
| Random, explicit (not value sites) | 18 | 18 | 0 |
| Value sites (2 of them also random) | 88 | 84 | 4 |
| **Total** | **156** | **152** | **4** |

The 4 disagreements:

- **Naming only, the auditor was wrong (3):** `copy.error` against
  `copy.Error` (above).
- **The auditor was incomplete (1):** `_base.py:224:54`. I left
  `ProcessorFormatter.format` to a ruling and missed the two observers that
  Twisted's publisher calls back (`JSONLogObserverWrapper.__call__`,
  `PlainFileLogObserver.__call__`). After review I agree with the writer,
  under L1.
- **The writer missed an edge (0). The writer has an edge that cannot
  happen (0).**

My five conditional answers (`<builtin>.dict` at `_config.py:355:38`,
`410:32`, `threadlocal.py:123:50`, `196:66`; `ExceptionDictTransformer` at
`processors.py:675:44`) are the writer's answers too (L2, L4).

## Step 2: exhaustive checks

**Dispatch sets.** I derived each role set from the source, docs and tests
before reading the ledger. The ledger's header sets are the same: bound
loggers (BoundLoggerBase, the generic, stdlib and twisted BoundLoggers, the six
`type()`-made filtering classes, AsyncBoundLogger), wrapped loggers, logger
factories (with the class `PrintLogger` of `tests/test_stdlib.py:1651`), the
29 processors, contexts. I checked every entry that uses them, and every
other value role: column formatters, exception renderers (with the function
`rich_traceback` of the `rich is None` branch), exception transformers, the
five stampers, the eleven call-site handlers, the `_items_sorter` closures
and `methodcaller`, `self._repr`, `_copier`, `value_repr` (`ConsoleRenderer._repr`
and `str`), `dictRenderer`, the observer of `JSONLogObserverWrapper`,
`sync_bl`, `self.bind` of the proxy (the method or the closure
`finalized_bind`, `_config.py:390`), and `self.error` in `_native.exception`
(`meth` or `_nop`). All agree. The receivers of `self.bind()`, `unbind`,
`try_unbind`, `new`, `_proxy_to_logger` and `_dispatch_to_sync` over the class
hierarchy are right in every entry; `super()` resolutions are right.

**Default rejections (21).** I read each reason and the explicit sites that
`--report` lists (`getattr`, `hasattr`, `setattr`, `print`, `repr`, `str`,
`len`, `max`, `any`, `sorted`, `set`, `tuple`). The accepted sites are right:
`_ThreadLocalDictWrapper.__getattr__` for dict methods on a context and for
`dict.update(wrapper)` looking up `keys` (`contextvars.py:77:15`,
`threadlocal.py:252:15`); `GreenThreadLocal.__getattr__`/`__setattr__` for
`_tl.dict_`; `CapturingLogger.__getattr__` at `_base.py:224:27`; the generic
`BoundLogger.__getattr__` at `_config.py:426:23`; `_ThreadLocalDictWrapper.__eq__`
at `_base.py:67:34` (also reflected after `dict.__eq__`). The one site where
a default reason fails is `tracebacks.py:173:32` (F1). Truth tests, `in`,
iteration and subscript stores never see a wrapped context: event dicts are
`.copy()` results, plain dicts also for a wrapped context.

**Functions that no site calls (172 nodes).** All are client entry points
(public methods and properties, a-methods, pickling and copy hooks, factory
and processor `__init__`s), Protocol stubs, `__delattr__` of
`GreenThreadLocal`, and module nodes. Only `BoundLoggerBase.__repr__` gains a
caller with F1.

**Special methods and properties.** The `_context` properties (10 sites),
`_dict`, the ConsoleRenderer property setters (`dev.py:697, 714, 720, 1069`),
`__delitem__` at `_base.py:93:28`, explicit `__eq__` calls, the
`findCaller` call-back of `_FixedFindCallerLogger` and the `ReprWrapper.__repr__`
call-backs at `224:54` and `twisted.py:219:30` are right (the last two rest
on Twisted's behaviour, unverified). Dataclass and NamedTuple calls have no
callee, as the micro-benchmark's `stdlib_classes/dataclass_*` cases give;
`@dataclass(frozen=True)` has `dataclasses.dataclass` and
`dataclasses.dataclass.wrap` (`dataclass_order`).

**Callees outside the package (161).** The trace confirms 132 names. The
other 29: missing modules (rich 5, colorama 2, greenlet 1, better_exceptions
1), the Windows branch (`SystemError`, `str.format`), `importlib.metadata`
(the deselected packaging tests) and `str.split`, the stdlib pass-through
methods (the tests replace them with client functions,
`tests/test_stdlib.py:283-300`), `logging.Logger.critical/debug/error/findCaller`,
`weakref.WeakKeyDictionary.setdefault` (greenlet path), and
`twisted.python.log.LogPublisher.msg` and `twisted.python.log.err`. All follow
the micro-benchmark rules as far as I can check: `copy.Error`,
`collections.abc.Mapping.get` for `os.environ.get`, `builtins.FrameLocalsProxy.items`
(no public path also on 3.15), `asyncio.BaseEventLoop.run_in_executor`,
`multiprocessing.current_process`, `io.TextIOWrapper`/`io.BufferedWriter` for
the default streams.

**Rejected trace edges (15).** All right: Mock objects as processors,
factory, context class and observer (4); the tests' `StringIO`, `BytesIO` and
binary files (8); `BaseException.__init__` of a `raise` without a call (3).

**Notes and rejections.** I read every entry outside the sample. No note
states a wrong fact that I could check.

## What I could not check

Twisted 26.4.0 and zope.interface are not on this machine; I did not use the
network. Unverified: the name `twisted.python.log.LogPublisher.msg`
(judgement 13); that `log.err` calls `repr()` on `_stuff` (the docstring of
`ReprWrapper`, `twisted.py:125`, says so); that `textFromEventDict` applies
`safe_str` to the message items and to `why` (F2, judgement 5); that the
publisher calls registered observers. rich, greenlet, colorama and
better-exceptions are named as missing modules and were not read.

## Remarks on the README and the tools

- The README has no rule for L1 (globally registered call-backs), L2
  (`type[T]` with a concrete T), L3 (frame locals of a logged traceback) and
  L4 (package Protocols). The writer flagged all four; each needs one sentence.
- The site finder does not mark calls of dataclass fields as value sites
  (`dev.py:310:39`, `938:26`): a field annotation without a value binds
  nothing for the tool, but the generated `__init__` assigns the attribute.
  The writer found both by hand and wrote notes. A fix: treat the annotated
  fields of a `@dataclass` class body as assigned attributes.
- The tools worked as documented. The skeleton, the report and
  `--report --default` gave all I needed.

## Re-check after the writer's changes

Checked against commit `fa2d474` (ledger, graph, judgements). Rulings as
the lead gave them: the locals of the package's own frames on a raise that
the package documents or makes on purpose are in the role (B2); a library
call-back belongs to the package function that makes the library call.

**Result: I agree. No edge to change.**

1. **Nothing else changed.** The edge sets of `structlog.json` at `9e32849`
   and now differ by exactly 7 added edges and none removed; the 367 nodes
   are the same; `structlog.rejected.json` is unchanged. 828 edges, 400
   inside. `check.py --benchmark-dir macro-benchmark-heldout-4 structlog`:
   no errors; the trace confirms 680 of 828.
2. **The six edges at `tracebacks.py:173:32`.** Each checked against the
   source. `to_repr` reaches every frame local through `extract`
   (`tracebacks.py:325`; `show_locals` defaults to true, line 49;
   `get_locals` hides only names that start with `__`, line 305).
   - `BoundLoggerBase.__repr__`: `self` and `bl` of `unbind`, which documents
     and raises `KeyError` (`_base.py:88-93`); `self` of `_process_event`,
     which documents and raises `ValueError` (`_base.py:147-149, 191`).
   - `_ThreadLocalDictWrapper.__repr__`: `self` of `__delitem__`, where that
     `KeyError` rises for a wrap_dict context (`threadlocal.py:218-219`).
   - `PrintLogger`, `WriteLogger`, `BytesLogger.__repr__`: `self` of
     `__getstate__` and `__deepcopy__`, which raise `PicklingError` and
     `copy.Error` on purpose (`_output.py:73, 93, 179, 201, 295, 323`); and
     the parameter `_` (the wrapped logger) of `LogfmtRenderer.__call__`,
     which documents and raises `ValueError` (`processors.py:144-145, 167`).
   - `CapturingLogger.__repr__`: the same parameter `_` with
     `CapturingLoggerFactory`.

   **No class of the same kind is missing.** The package defines `__repr__`
   in 8 classes and `__str__` or `__format__` in none (`rg "def __repr__"`).
   Seven are now callees of `to_repr`. The eighth, `ReprWrapper`, is rightly
   rejected: `twisted.JSONRenderer` builds it only in its return expression,
   after `_extractStuffAndWhy` has raised or not; `__init__`, `__eq__` and
   `__repr__` cannot raise; and the frames that hold one later
   (`_proxy_to_logger` with `args`, Twisted's `err`) raise nothing on
   purpose (Twisted's frames are library frames). The other documented
   raises hold no instance of these classes as a local: `ProcessorFormatter.__init__`
   and `ConsoleRenderer.__init__` (`TypeError`, `ValueError`; dataclass
   reprs are generated code), `ExceptionDictTransformer.__init__`,
   `_make_stamper`, `ConsoleRenderer.get_active`, `structlog.__getattr__`,
   `_extractStuffAndWhy` (client event dicts and Failures),
   `AsyncBoundLogger.unbind` (no `__repr__`). `DropEvent` never reaches the
   client.
3. **F2 (`twisted.py:248:51`) and the Twisted facts.** The wheel
   `twisted-26.4.0-py3-none-any.whl` of the scan's cache has SHA-256
   `dc25ea0e…4c0`, the pin of `requirements/structlog.txt:59-60` (the
   zope.interface 8.5 wheel also matches its pin). I read it as a zip and
   ran nothing. Confirmed:
   - `err` calls `msg(repr(_stuff), why=_why, isError=1, **kw)` when
     `_stuff` is no `Failure` and no `Exception` (`twisted/python/log.py:131`);
     with a `Failure` it publishes `why=_why` (`log.py:127`).
   - `LogPublisher.msg` builds the event and calls `publishToNewObserver`
     with `textFromEventDict` (`log.py:277`), which calls it
     (`twisted/logger/_legacy.py:121`) and then the global publisher
     (`_legacy.py:149`). The publisher calls each observer in turn,
     synchronously, catching exceptions (`twisted/logger/_observer.py:78-85`).
     `addObserver` and `startLoggingWithObserver` wrap a legacy observer in
     `LegacyLogObserverWrapper` (`log.py:207, 228`), whose `__call__` calls it
     (`_legacy.py:92`) and leaves an empty `message` tuple empty.
   - `textFromEventDict` applies `reflect.safe_str` to `why` when the message
     is empty and the event is an error (`log.py:420-424`), and to each
     message item otherwise (`log.py:438`); `safe_str` is `str(o)`
     (`twisted/python/reflect.py:432-433`), so a `ReprWrapper`, or a tuple
     that holds one, calls `ReprWrapper.__repr__`. F2 holds.
   - The name `twisted.python.log.LogPublisher.msg`: `log.msg` is
     `theLogPublisher.msg` (`log.py:306, 334`). `synchronize(LogPublisher)`
     (`log.py:280`) replaces the class attribute with the closure `sync` of
     `twisted.python.threadable._sync`, because `threading` imports
     (`threadable.py`, end). The closure is reachable through the attribute
     `LogPublisher.msg`, so the method rule names it, not the rule for
     closures without an attribute path. I agree with the writer's name; no
     trace edge checks it.


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

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


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
