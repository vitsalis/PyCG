# prometheus-client: blind audit of the ground truth (batch 6)

Release v0.26.0, commit `9b6b971f903e7a08f88da5a95048b7a2a28f55a5`, analysed
source `prometheus_client/` with the vendored `decorator.py` (`exclude = []`).
Audited files (uncommitted in the worktree on 2026-11-22):
`prometheus-client.ledger` (1478 entries, 234 notes, 24 default rejections;
SHA-256 `2dec4e69…cae289`), `prometheus-client.json` (322 nodes, 1100 edges:
408 inside, 692 outside), `prometheus-client.added.json`,
`prometheus-client.rejected.json` (7 edges) and `prometheus-client.md`
(judgements J1 to J7). `check.py prometheus-client` reports no errors; the
old trace has 847 edges and confirms 840 graph edges (76.4%).

I read the README (conventions, scope rules, clarifications, rulings for
batch 6), the package source, `docs/content`, the tests and
`pyproject.toml`, as data. I ran no analysis tool on the package and did
not import or run it. My scratch files are under
`$TMPDIR/audit-prometheus-client/` (skeleton, draw script, blind
answers, binding-check script).

## Summary

- 137 sites re-derived blind: 131 agree, 3 are my errors (an incomplete set
  of exception classes), 2 differ in placement only, 1 differs in judgement
  (J4). No sampled site shows a writer edge that cannot happen or a missed
  edge.
- Exhaustive checks found no missed edge and no impossible edge outside
  J1. The binding check found no call that cannot bind (479 pairs).
- Findings: F1 (J1, one edge that the rules do not support, −1), L1 to L3
  (rulings for the lead or a referee), W1, W2 (wording), R1 (stale text in
  this worktree). If the lead accepts F1 and keeps the writer's other
  choices, the graph has 1099 edges.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Proposal |
|---|---|---|---|---|---|
| F1 | low (edge the rules do not support) | `bridge/graphite.py:70:45` `self._registry.collect()` -> `registry.RestrictedRegistry.collect` | `RestrictedRegistry` does not subclass `Collector` (`registry.py:155`) and its own documentation does not call it a collector. B2 admits it only where the package passes it or the documentation names it for the role: `_bake_output` passes one to the encoder (`exposition.py:121-122`), and the documentation passes one to `generate_latest` only (`docs/content/restricted-registry/_index.md`, `docs/content/registry/_index.md:72-80`). Nothing passes one to `GraphiteBridge` (`docs/content/bridges/graphite.md`, `tests/test_graphite_bridge.py:35`, `38`). See "J1" below. | −1 | remove the callee, or keep it if the referee rules that all exporters' `registry` parameters are one role (J1 reading B) |
| L1 | ruling (J1) | `exposition.py:317:35`, `openmetrics/exposition.py:61:35`, `bridge/graphite.py:70:45`, `registry.py:90:32`, `107:41`, `172:44` | The writer admits `CollectorRegistry` and `RestrictedRegistry` for the exporters but not for `register()`, and cites funcy ruling 7 ("documentation read one entry at a time"), which is about B4 type lists of client collections, not about the implementations of a package Protocol. The README does not say whether one Protocol annotation names the same classes at every parameter. Full analysis in "J1" below. | 0, −1 or +6 | referee |
| L2 | ruling (J4) | `exposition.py:160:23` `start_response(status, headers)`; rejected trace edge `make_wsgi_app.prometheus_app -> wsgiref.handlers.BaseHandler.start_response` | Rule A rejects a trace edge only when the callee is a value that a client supplied. In the trace, the test calls `start_wsgi_server` (`tests/test_exposition.py:660`); the package builds the wsgiref server (`exposition.py:260`) and starts it (`275:12`), and wsgiref passes its own `ServerHandler.start_response`. The writer's `275:12` already treats this wsgiref code as package-started library code (callees `prometheus_app`, `_SilentHandler.log_message`). The B5 sentence "a server or framework that calls the package is a client" (whitenoise) was made for an external server; bottle's note at `bottle.ledger` 1113:27 is a ledger precedent, not a ruling, and no audit examined bottle's own `WSGIRefServer`. | 0 or +1 | lead: the README does not decide it; I lean to the edge (`wsgiref.simple_server.ServerHandler.start_response`, or the trace's name), which leaves the rejected file |
| L3 | ruling (J6), low | `metrics.py:796:45` `self._states.index(state)`; rejected trace edge `Enum.state -> <builtin>.list.index` | The annotation is `Optional[Sequence[str]]` (`metrics.py:770`), the documentation `List[str]` (`docs/content/instrumenting/enum.md:37`). B4: "when an annotation and the documentation both exist and differ, the annotation decides". The writer reads `List` as "differs"; the other reading is that the documentation only narrows a compatible abstract annotation, as funcy ruling 6 lets documentation name a concrete client type. | 0 or +1 | the README literally supports the writer; no change unless the lead reads "differ" as "contradict" |
| W1 | wording (no edge change) | `exposition.py:219:27` and `prometheus-client.md` J5 | `ssl.SSLContext.load_default_certs` calls `set_default_verify_paths` (only `ssl.SSLError`) and, on Windows, enumerates the system stores, where `PermissionError` is caught. The errno classes `IsADirectoryError`, `NotADirectoryError` and `PermissionError` come from opening a file path, which this call does not take. The six edges stay, because `211:27` and `229:23` (file paths of the client) give them. | 0 | narrow the note of `219:27`, or keep the six callees with a note that the site's own set is smaller |
| W2 | wording | `prometheus-client.md` J1, and the reject lines at `registry.py:107:41`, `172:44` | "documentation read one entry at a time (funcy ruling 7)" cites a ruling about client collection types. The reason that fits the README is the Protocol clause of B2 plus the per-parameter B2 routes (see J1). | 0 | reword after L1 |
| R1 | stale text (README, notes) | `README.md:1214` (table row "without `prometheus_client/decorator.py`"), `README.md:1295-1299` (decision 11: "is excluded"), `projects.toml:1959-1963` (notes: "Excluded from the analysed source") | `exclude = []` since commit `1e8dfdd`; the corrected text is commit `8794d6a`, which is on the branch of batch 6 and not an ancestor of this worktree's `HEAD` (`31a0601`). | 0 | merge `8794d6a` into the ground-truth branch of batch 6 |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and the source into
`$TMPDIR/audit-prometheus-client/` and ran `check.py --skeleton`.
It has 2615 sites (1445 call, 8 decorator, 34 with, 192 iter, 368 op, 449
getitem, 38 setitem, 9 delitem, 72 format) and 67 value sites. I numbered
the sites module by module in (line, column) order.

**Draw by kind.** No kind dominates (explicit sites are 1453 of 2615, the
largest implicit kind is getitem with 449), but two candidates sit at 812
sites each (`Metric.__eq__`, `Timestamp.__eq__`) and the small kinds would
often be missed. So I drew by kind in proportion to the counts, at least
one site per kind: `random.Random(20261122)`, then `rng.sample` of 37 call,
1 decorator, 1 with, 5 iter, 10 op, 12 getitem, 1 setitem, 1 delitem and 2
format sites (70), plus the 67 value sites (none was drawn): 137 sites. I
wrote the callees of each from the source before I opened any file of the
writer (`blind-answers.txt` in the scratch directory, with the facts that I
fixed first, among them my own enumeration of the Collector role).

The drawn sites: `asgi` 27:37; `context_managers` 25:30; `decorator`
169:34; `django.exposition` 12:102; `exposition` 314:51, 398:22, 414:16,
487:93, 567:14; `gc_collector` 35:13; `metrics` 22:32, 100:43, 165:103,
174:45, 217:32, 337:56, 411:35, 438:56, 628:14, 646:31, 646:36, 704:27,
773:68; `metrics_core` 247:28, 251:68, 309:36; `mmap_dict` 8:35, 68:29,
86:14, 135:26; `multiprocess` 27:30, 46:6, 55:35, 72:68, 92:44, 143:28;
`openmetrics.exposition` 127:81, 150:75, 151:34, 206:19; `openmetrics.parser`
51:27, 105:20, 115:46, 127:31, 133:19, 188:33, 222:43, 294:42, 352:43,
362:36, 422:28, 445:24, 455:24, 646:68; `parser` 77:48, 100:19, 124:25,
150:9, 239:19, 271:50, 295:28; `platform_collector` 17:39;
`process_collector` 21:41, 51:35, 58:43, 63:59; `samples` 25:85; `utils`
32:31; `values` 68:21, 146:28.

| Class | Sites | Detail |
|---|---|---|
| Agreement | 131 | 106 sites with entries, and 31 implicit sites that the defaults decide, where I also wrote no callee |
| Auditor error (incomplete answer) | 3 | `exposition.py:211:27`, `219:27`, `229:23`: I wrote `FileNotFoundError`, `PermissionError`, `ssl.SSLError`; the writer adds `OSError`, `IsADirectoryError`, `NotADirectoryError` (errnos that a client path can give, J5). The writer's set is right for 211 and 229; see W1 for 219. |
| Placement only | 2 | `multiprocess.py:92:44` and `143:28`: I put `<lambda2>` at the `defaultdict(...)` call and nothing at the lookup; the writer puts each factory lambda at the lookups of missing keys. The edges of `_accumulate_metrics` are the same. |
| Judgement difference | 1 | `exposition.py:160:23`: I wrote `wsgiref.simple_server.ServerHandler.start_response`; the writer writes no callee (J4). See L2. |

The value sites hold the decisions where an error is most likely, and all
67 agree apart from 160:23 and the three J5 sites: `values.ValueClass(...)`
(both value classes; tests assign `values.ValueClass`,
`tests/test_multiprocess.py:59`), `self.__class__(...)` in `labels`
(`MetricWrapperBase`, `Gauge`, `Histogram`, `Enum` `__init__`),
`self._child_samples()` (six classes and `Gauge.set_function.samples`),
`callback(self.duration)` (`Gauge.set`, `Summary.observe`,
`Histogram.observe`), `encoder(registry)` (both `generate_latest` and
`functools.partial.__call__`), `handler(...)` and `handler(...)()` (the
three documented handlers that bind; their closures), `valid_rune_fn(b, i)`
(both rune functions), the `struct.Struct` bound methods of `mmap_dict`,
`desc_func()` (J1), and the client callbacks with no callee (ASGI
`receive`/`send`, `func(*args, **kwargs)` of the `wrapped` closures,
`f()` of `set_function`, the `dispatch_on` implementations, the default
`os.getpid`, `time.time`, the default pid lambda).

## Step 2: exhaustive checks

**Dispatch sets.** I read every entry of the ledger against the source. The
receivers hold: `self._value`, `_count`, `_sum`, `_buckets[i]` are
`ValueClass` objects (both classes); `self._counter` is a `Counter`
(`context_managers.py:16` annotation, `metrics.py:360`); `self._gauge` a
`Gauge`; `self._metric` of `Timer` a `Gauge`, `Summary` or `Histogram`
(`Timer.labels` keeps the class); `self._pusher` the `GraphiteBridge`;
`files` holds `MmapedDict` objects; `self._f` a `BufferedRandom` or, with
the public `read_mode`, a `BufferedReader`; the metric families' own
`add_metric`; `registry.register(self)` only `CollectorRegistry.register`
(annotations `CollectorRegistry`, `Optional[CollectorRegistry]`; the
multiprocess documentation for `MultiProcessCollector`).

**J1, the Collector role.** I enumerated the members from the source, the
annotations, the documentation and the tests before I read the writer's J1
(`blind-answers.txt`, fact F6), then compared.

| Member | `register()` and the registered collectors (`registry.py:90:32`, `107:41`, `172:44`) | Exporters' `registry` (`exposition.py:317:35`, `openmetrics/exposition.py:61:35`, `bridge/graphite.py:70:45`) | README rule |
|---|---|---|---|
| `Counter`, `Gauge`, `Summary`, `Histogram`, `Info`, `Enum` (`MetricWrapperBase.collect`, `.describe`) | in (writer: in) | in (writer: in) | decided: B2, the package's own call (`metrics.py:136`), and the annotation `Collector`, which `MetricWrapperBase` lists as a base (`metrics.py:63`; declared bases count, more-itertools ruling) |
| `GCCollector`, `PlatformCollector`, `ProcessCollector` | in | in | decided: as above (`gc_collector.py:9`, `15`; `platform_collector.py:8`, `24`; `process_collector.py:16`, `46`) |
| `MultiProcessCollector` | in | in (writer: in) | `register()`: decided, the package's own call (`multiprocess.py:33`) and `docs/content/multiprocess/_index.md:61-62`. Exporters: not a subclass; only the Protocol clause of B2 ("the classes that the package documents as its implementations", structlog) admits it, through its docstring "Collector for files for multi-process mode" (`multiprocess.py:20`; `GCCollector` and the others use the same words) and `docs/content/multiprocess/_index.md:110`. Mostly decided. 3 edges. |
| `CollectorRegistry` | out (writer: out) | in (writer: in) | Exporters: decided, B2 defaults (`REGISTRY`) and the documentation of each parameter ("`registry` is a Collector, normally an instance of CollectorRegistry", `exposition.py:635`, `688`). `register()`: not decided; it is in only if being called "a Collector" in another function's documentation makes the class an implementation of the Protocol for every parameter. 3 edges (`_get_names`, `CollectorRegistry.collect`, `RestrictedRegistry.collect` -> `CollectorRegistry.collect`). |
| `RestrictedRegistry` | out (writer: out) | in at 317 and 61; at 70:45 the writer says in, I say out (F1) | 317: decided, documentation and `_bake_output` (`exposition.py:121`); 61: decided, `_bake_output` through the partial of `choose_encoder`; 70:45: not decided, 1 edge; `register()`: as `CollectorRegistry`, 3 edges |
| `_EmptyCollector` | out | out | decided: private, the package never passes it; it is stored only under `target_info`, which `collect` never reads (`registry.py:101`, `166-167`) |
| the Protocol `Collector` | out | out | decided: B1, a Protocol has no instances |

The readings, with the edges each changes against the writer's graph:

- A (the writer): exporters admit every class that some documentation
  calls or uses as a Collector; `register()` admits only the classes that
  the package registers or that subclass `Collector`. 0.
- B (one Protocol, one set): every parameter annotated `Collector` admits
  the same documented implementations, the registries included. +6
  (`CollectorRegistry.collect` and `RestrictedRegistry.collect` at the
  three registry sites).
- C (my reading, the smaller extension of the existing rules): the Protocol
  clause admits the subclasses and the classes whose own documentation
  calls them a Collector (`MultiProcessCollector`); any other class enters a
  parameter only by the per-parameter routes of B2 (default, documentation
  of that parameter, the package's own calls, tests). −1 (F1). If the
  referee does not count the docstring of `MultiProcessCollector`, −3 more
  at the three exporter sites.

The trace does not separate the readings: it has
`generate_latest -> CollectorRegistry.collect`, `RestrictedRegistry.collect`,
and no exporter edge to a metric or collector class.

**Default rejections (24).** I checked each reason and every explicit site
that `check.py --report` lists under it (for example `sorted(...)` of label
items under `Timestamp.__lt__`/`__gt__`, `float(...)` of strings, bytes and
numbers under `Timestamp.__float__`, the `.get()` calls of dicts, environs,
headers and scopes under `PrometheusDjangoView.get` and the two value
`get`s). All hold. The 31 implicit sites of my sample that the defaults
decide all have no callee by my reading. A targeted scan of the source for
comparisons and formats of timestamps, metrics and `self` found only the
sites that accept the candidates (`metrics_core.py:47:34`, `50:51`;
`openmetrics/exposition.py:44:43`, `92:36`; `openmetrics/parser.py:426:38`,
`616:72`, `622:37`; `exposition.py:306:38`; `metrics.py:162:77`, `165:103`,
`212:77`, `231:77`, `281:80`, `289:78`).

**Functions that no site calls (107 nodes, modules included).** Each is
called only by clients or by generated code: the `wrapped` closures and the
decorator-made wrappers (`decorate` stores the caller; the client calls the
generated function), `ContextManager.__call__`, `decorator.__init__`,
`dispatch_on` and its closures, `get_init`, the Python 2 class
`getfullargspec`, `Metric.__eq__`/`__repr__`, `MetricWrapperBase._child_samples`,
`Timer.labels`, the public API entry points, `Collector.collect`,
`_EmptyCollector.collect`, the openmetrics copies of `_is_character_escaped`
and `_replace_escaping` (the module uses those of `parser.py`). No missed
caller.

**Special methods and properties.** The package has no property and no
`__getattr__`, `__bool__`, `__len__`, `__iter__` or `__hash__`, so no
getattr or truth site has a candidate. `Timestamp.__str__`, `__repr__`,
`__float__`, `__eq__`, `__ne__`, `__gt__`, `__lt__`,
`MetricWrapperBase.__str__`/`__repr__` and the context managers' `__enter__`
and `__exit__` have exactly the callers listed above; the reflected
`Timestamp.__lt__` at `openmetrics/parser.py:616:72` and the reflected
`__ne__` at 426:38 and 622:37 are right.

**Rejections and notes.** All read; none wrong apart from L1 to L3 and W1,
W2. Python 2 code (J7) follows the README rule for a branch that only an
unsupported version takes, also when its test is not a version test
(`decorator.py:45`, `116`, `286`; netaddr precedent).

**Callees outside the package.** The names follow the micro-benchmark
rules: inherited methods by the receiver's class
(`collections.defaultdict.items`, `.setdefault`, `http.client.HTTPMessage.get`,
`collections.abc.Mapping.get` for `os.environ.get`), private classes by
their path (`socketserver._SocketWriter.write`), bound methods of module
objects by the class (`struct.Struct.pack`, `.unpack_from`), instance calls
by `__call__` (`functools.partial.__call__`), an explicit base `__init__`
by its path (`contextlib._GeneratorContextManager.__init__`,
`threading.Thread.__init__`, `<builtin>.ValueError.__init__`). The missing
libraries (aiohttp, Django, Twisted, python-snappy) are named by access
path. J3 (`aiohttp.web.Request....` from the package's annotation,
`django.http.HttpRequest.headers.get` from Django's documented request
type) combines the whitenoise ruling (a framework's documented type) with
the missing-module rule; it is the smaller extension, and it decides 4
edges. The pinned test dependencies (asgiref 3.12.1 only) give no other
callee.

**Rejected trace edges (7), checked against the old trace.** The two
`asyncio.Queue` methods (asgiref's `ApplicationCommunicator` passes them as
`receive` and `send`, client callbacks) and the two MagicMock `__call__`
edges (`tests/test_core.py:1059-1061`, `1079-1083`) are client values. The
Mock over `_bake_output` (`tests/test_wsgi.py:73`) is a client change to
package internals. `list.index` is L3 and wsgiref's `start_response` is L2.
The functions of `decorator.py` do not run in this old trace; as the lead
asked, that is not a finding.

**Judgements of the writer.**

| Judgement | Nearest rule | Opinion |
|---|---|---|
| J1 Collector role | B2 (annotation, Protocol clause, per-parameter routes) | partly decided; see the table above, F1 and L1 |
| J2 `MetricWrapperBase` is a receiver | B1 (a plain public class is a receiver of its own methods; `__init__` receives the object being made); python-barcode J1 does not apply, because the `__init__` succeeds with label names and `registry=None` | supported; 1 edge (`MetricWrapperBase.__init__ -> _metric_init`) |
| J3 framework requests of missing libraries | whitenoise ruling 3 (B5) and the missing-module rule (dagster-pipes) | supported as the smaller extension; 4 edges |
| J4 `start_response` of the package's own server | B5's server sentence against rule A and the callback rule | not decided by the README; L2 |
| J5 re-raised exception classes | no rule; B2/B3 (classes the library makes for client inputs) | supported for 211 and 229; W1 for 219 |
| J6 `Enum.state` | B4 ("the annotation decides") | literally supported; L3 |
| J7 Python 2 branches of `decorator.py` | "Judgements": a branch that only an unsupported version takes | supported |

## Step 3: binding check

A script (`tools/bind.py` in the scratch directory; it reads the ledger and
the source with `ast`) matched every call site that has a package callee
with the callee's signature: 479 pairs. 457 bind as written. 12 are
callbacks that library code calls with its own arguments (`t.start()` ->
`prometheus_app(environ, start_response)` and `log_message(format, *args)`;
`float()` -> `__float__`; `open()` -> the `get_method` lambda and
`redirect_request` with six arguments; `str.format` -> `__str__`,
`__repr__`; `re.Pattern.sub` -> the replace functions; the
`types.MethodType` binding of `Gauge.set_function.samples`): each binds,
checked by hand. 10 use `*args` or `**kwargs`
(`self._metric.labels(*args, **kw)`, `self.update(func, **attrs)`,
`self.make(..., **attrs)`, `vancestors(*types)`, `ancestors(*types)`, and
`self.__class__(..., **child_kwargs)` with the `_kwargs` that `Gauge`,
`Histogram` and `Enum` store): each binds for the package's own calls.
None cannot bind; no edge changes. `tls_auth_handler` at
`exposition.py:772:12` is correctly no callee (it cannot bind the five
keyword arguments).

## README and tools

- R1 above: the worktree's README and `projects.toml` notes still describe
  the old exclusion of `decorator.py`.
- The README does not say whether a package Protocol names one set of
  classes for every parameter it annotates (L1); a sentence after the
  structlog clause of B2 would settle it for later packages.
- The README does not say how far to enumerate the classes of a library
  exception that the package re-raises by class (J5).
- `check.py` and `sites.py` behaved as documented. Every `x.__init__(...)`
  is a value site by name because `decorator.py:291` and `299` assign
  `ContextManager.__init__`; the writer noted it at each site.

## Re-check against the new trace (2026-11-22, after the writer's step 4)

The new trace (`dynamic/prometheus-client.json`, commit `4c755be`, with
`decorator.py` analysed) has 896 edges and 248 functions run. Its edges are
a superset of the old trace's 847 edges: 49 new edges, 0 lost. The new
edges are 46 with a caller in `decorator.py` and the three calls of
`decorate` from the `__call__` methods of `context_managers.py`. All 49
are in the graph. The ledger is unchanged (same SHA-256 `2dec4e69…cae289`),
and so is the graph (1100 edges). `check.py prometheus-client` reports no
errors: the trace confirms 889 of 1100 edges (80.8%), and 7 are rejected.

- **Rejected trace edges.** All 7 are still in the new trace, with the same
  callers. The reasons still hold: the asgiref queues and the MagicMock
  collectors are client callbacks, and the Mock over `_bake_output` is a
  client change to package internals. `Enum.state -> list.index` (L3) and
  wsgiref's `start_response` (L2) are with the referee. No new edge needs
  a rejection.
- **The `decorator.py` sites of my sample.** The new trace agrees with the
  ledger and with my blind answers:
  - `169:34` gives `FunctionMaker.update -> getattr`.
  - `223:19` gives `FunctionMaker.create -> FunctionMaker.__init__`.
  - `81:19` gives no edge for the namedtuple `ArgSpec`: `getargspec` calls
    only `inspect.getfullargspec`.
  - `57:35`, `288:49` and `288:57` have no edge: they are Python 2 code
    that never runs.
  - `296:49`, `334:17`, `409:25`, `415:29` and `418:24` did not run:
    no test makes a `ContextManager` or uses `dispatch_on`.
- **The `wrapped` closures.** The trace has their out-edges
  (`__enter__` and `__exit__`, `_new_timer`) and no caller for them in the
  package. This confirms that the generated wrappers of `decorate` call
  them only when a client calls the decorated function.
- **R1** is resolved: the merged base text of `README.md:1214`, decision 11
  and the `projects.toml` notes now say that `decorator.py` is analysed.
- **Unchanged:** F1, L1 to L3, W1 and W2. The binding check does not depend
  on the trace.
