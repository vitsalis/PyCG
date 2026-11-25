# prometheus-client: judgements of the ground truth

Release v0.26.0 (commit `9b6b971`). Analysed source: `prometheus_client/`
with the vendored `decorator.py` (the lead reversed its exclusion,
commit `1e8dfdd`): 30 modules, 292 functions (7 lambdas), 47 classes.
`pyproject.toml` declares `requires-python = ">=3.9"` and the
implementations CPython and PyPy (classifiers). Normal and `-O`/`-OO`
execution are both included (the two `assert` statements with a call,
`asgi.py:12` and `decorator.py:151`, keep their edges; `decorator.py:329`
asserts without a call).

The ledger is `prometheus-client.ledger`; the graph
`prometheus-client.json` and the added edges are generated from it. Seven
trace edges are rejected in `prometheus-client.rejected.json`.

**The trace.** `dynamic/prometheus-client.json` was recorded again with
`decorator.py` analysed (896 edges, 248 functions run). Step 4 was repeated
against it: its 49 new edges were already in the graph. The tracer misses
the calls of code that `exec` runs (T1).

## Architecture, as the ledger uses it

- The metric wrappers (`metrics.py`): `MetricWrapperBase` and its six
  subclasses `Counter`, `Gauge`, `Summary`, `Histogram`, `Info`, `Enum`.
  A wrapper with label names is a parent; `labels()` makes children with
  `self.__class__(...)`. A child (or a label-less wrapper) runs its
  `_metric_init`, which makes `values.ValueClass` objects.
- `values.ValueClass` is chosen at import (`values.py:163`): `MutexValue`,
  or the `MmapedValue` class of `MultiProcessValue()` when
  `PROMETHEUS_MULTIPROC_DIR` (or the old lower-case name) is set, the
  documented multiprocess mode. The tests also assign
  `values.ValueClass = MultiProcessValue(...)`. Both classes are callees at
  every `values.ValueClass(...)` site and of every `inc`, `set`, `get`,
  `set_exemplar`, `get_exemplar` on a value.
- `Collector` (`registry.py:8`) is a `Protocol`. `MetricWrapperBase`,
  `ProcessCollector`, `GCCollector` and `PlatformCollector` list it as a
  base; a class that lists a Protocol as a base is an ordinary class.
- `Metric` and `Timestamp` define `__eq__` without `__hash__`: they are
  unhashable, so they are never dict keys or set elements.
- `Sample`, `Exemplar`, `NativeHistogram` and `BucketSpan` are
  `NamedTuple` classes: their calls add no edge.
- `decorator.py` makes functions with `compile` and `exec`
  (`FunctionMaker.make`, line 194). The generated functions have no node.
  The generated wrapper of `decorate` calls `_call_` (the `wrapped`
  closures of `context_managers.py`) only when the client calls the
  decorated function, so `wrapped` has no package caller. The exec'd
  source is one `def` statement and calls nothing (195:17).

## Default rejections (24)

`Metric.__eq__` (796 sites), `Timestamp.__eq__` (794), `__ne__` (40),
`__lt__` and `__gt__` (59 each), `__float__` (36), `__str__` (130),
`__repr__` (141), `Metric.__repr__` (142), `MetricWrapperBase.__str__`
(128) and `__repr__` (140), `PrometheusDjangoView.get` (35), the
`__enter__` and `__exit__` of the three context managers (31 each),
`MutexValue.get` and `MmapedValue.get` (29 each), and in `decorator.py`
the Python 2 class `getfullargspec` (`__iter__` 392, `__init__` 4),
`append` (75) and `dispatch_on.gen_func_dec.register` (6). Each default
names the sites that accept the candidate explicitly; those sites have
entries (for example `metrics_core.py:47:34`, `openmetrics/parser.py:426:38`,
`616:72`, `622:37`, `metrics.py:162:77`, `context_managers.py:30:18`).

## Judgements

**J1. The Collector role (B2; many sites).** Ruled by the referee and
adopted by the lead (reading C of the audit, finding L1): admission to the
role of a parameter annotated with the package Protocol `Collector` is per
parameter. The Protocol admits its declared implementations (the metric
wrappers, `ProcessCollector`, `GCCollector`, `PlatformCollector`, which list
`Collector` as a base) and the classes that the package documents as
implementations (`MultiProcessCollector`: its docstring, `multiprocess.py:20`,
and `docs/content/multiprocess/_index.md:108`). Any other package class
enters a parameter only by B2's routes for that parameter (default,
documentation of that parameter, the package's own calls and forwarding,
tests):
- `generate_latest` (`exposition.py:317:35`) and `openmetrics.generate_latest`
  (`openmetrics/exposition.py:61:35`): the implementations, `CollectorRegistry`
  (the default `REGISTRY`) and `RestrictedRegistry` (the documented
  `restricted_registry` example; `_bake_output` passes one through the
  encoder, `exposition.py:121-122`);
- `GraphiteBridge.push` (`bridge/graphite.py:70:45`): the implementations and
  `CollectorRegistry` (default and tests); nothing passes a
  `RestrictedRegistry` there (audit F1: its callee was removed);
- `register(collector)` and the collectors that the registries collect
  (`registry.py:90:32`, `107:41`, `172:44`): the implementations, which the
  package registers; no route passes a registry there, so neither
  registry's `collect` is a callee.
Not values: the Protocol `Collector` (no instances) and the private
`_EmptyCollector` (only stored under the name `target_info`). The
referee's table of admitted classes per parameter
(`ruling-prometheus-client.md`) agrees with every entry of the ledger.

**J2. `MetricWrapperBase` is a receiver (B1; `metrics.py:131:30`,
`193:64`).** It is public (`prometheus_client.metrics.MetricWrapperBase`)
and not abstract: its base `Collector` is a Protocol, but listing a
Protocol as a base makes an ordinary class, which `typing` lets one
instantiate. A client can make one; a label-less one reaches its own
`_metric_init`, which raises `NotImplementedError`. So
`MetricWrapperBase.__init__ -> MetricWrapperBase._metric_init` is an edge,
and `MetricWrapperBase.__init__` is a callee of `self.__class__(...)`.
`MetricWrapperBase._child_samples` is not a callee at `270:39`: every
MetricWrapperBase that is not a parent fails in `__init__`, so none reaches
`_samples` on that branch (B3, a failed construction gives no instance).

**J3. Framework request objects of missing libraries (B5, missing
modules).** aiohttp and Django are not installed. `request` of the
aiohttp handler is annotated `web.Request` (`aiohttp/exposition.py:16`):
its calls are named by the stub path (`aiohttp.web.Request.query.getall`,
`.query.keys`, `.headers.getall`; 18:44, 18:79, 19:56). Django's view
dispatch passes an `HttpRequest`, the type its documented API fixes
(whitenoise ruling 3), so `request.headers.get` is
`django.http.HttpRequest.headers.get` (`django/exposition.py:22:44`,
`23:53`). The package imports neither name for these objects; the
alternative is no callee.

**J4. `start_response` of the package's own server
(`exposition.py:160:23`).** Ruled by the referee and adopted by the lead
(audit L2): when the package selects and starts the server, the values
that the library builds and passes to the package's application keep
their library provenance. `start_wsgi_server` (lines 259-275) makes the
app, chooses wsgiref and `_SilentHandler`, and starts the server thread;
wsgiref's `ServerHandler` passes its `start_response` (`BaseHandler.run`).
So `160:23` has the callee `wsgiref.handlers.BaseHandler.start_response`,
by its canonical name (the trace's `wsgiref.handlers.SimpleHandler.start_response`
is an alias, not a second edge), and the trace edge left the rejected
file. A `start_response` that an external server passes stays a client
callback (B5). `start_wsgi_server` (`t.start()`, 275:12) is also the caller
of `make_wsgi_app.prometheus_app` and `_SilentHandler.log_message`, which
the server threads run (callback rule, bottle F1; the tracer misses them,
T1).

**J5. Re-raised exception classes (`exposition.py:211:27`, `219:27`,
`229:23`).** `exc_type = type(exc)` is the class of the `IOError` that
`ssl.SSLContext.load_verify_locations`, `load_default_certs` or
`load_cert_chain` raised. CPython raises `ssl.SSLError` for content that
OpenSSL refuses, and `OSError` built from the errno of a failed open,
which `OSError.__new__` turns into its errno subclass. At all three
sites the ledger names `ssl.SSLError`, `<builtin>.OSError`,
`FileNotFoundError`, `PermissionError`, `IsADirectoryError` and
`NotADirectoryError`. At `211:27` and `229:23` the files are paths that the
client names. At `219:27` `load_default_certs` also loads files: CPython's
fallback certificate file and directory on Linux (`ssl.py`,
`load_default_certs`, CPython 3.14) and PyPy's `set_default_verify_paths`,
which calls `load_verify_locations` with the default paths (PyPy 3.11
`lib_pypy/_cffi_ssl/_stdssl/__init__.py:1768`). The blind audit's W1 had
narrowed `219:27` to the first two classes; Codex audit round 1 showed
that file errors arise there too, and the list is restored (no edge
changed either time). No precedent decides how far to enumerate the classes of a
library exception.

**J6. `Enum.state` (`metrics.py:796:45`).** `states` is annotated
`Optional[Sequence[str]]`; the documentation's table says `List[str]`
(`docs/content/instrumenting/enum.md:37`). The annotation decides (B4),
and `Sequence` fixes no class, so `self._states.index(state)` has no
callee, and the trace edge `Enum.state -> <builtin>.list.index` is
rejected. The referee upheld this (audit L3): B4 gives the annotation
precedence when the two differ, and `List[str]` is a different, narrower
type.

**J7. The Python 2 and old-Python branches of `decorator.py`.** The
branches for Python 2 (lines 51-71, 116-119, 287-291) do not run on a
supported version, so the class `getfullargspec` and the first `def
__init__` make nothing, and their sites have no edges. On every
supported version `_GeneratorContextManager.__init__` has four arguments,
so the branch of line 294 runs: `prometheus_client.decorator.__init__`
(the second def) calls `contextlib._GeneratorContextManager.__init__`
(296:49). The two defs share one node.

## Other decisions worth checking

- `MultiProcessCollector._accumulate_metrics` (`multiprocess.py:91-93`):
  the three `defaultdict` factories are lambdas. defaultdict calls a
  factory at the lookup of a missing key, so each lambda is a callee of the
  `samples[labels]`, `sample_timestamps[labels]` and `buckets[...]`
  lookups where the key can be missing (110:42, 114:42, 118:32, 120:62,
  123:36, 126:32, 136:36, 140:32, 143:28, 156:36, 158:36), not of the
  lookups that always follow a lookup of the same key (112, 116, 124,
  160).
- `_PrometheusRedirectHandler.redirect_request` (`exposition.py:101:50`):
  `req.get_method()` is the lambda of `_make_handler.handle` (line 515) on
  the first redirect, and `urllib.request.Request.get_method` on a further
  redirect of the request it made (line 105). urllib calls both back from
  `OpenerDirector.open` at 518:47.
- `MetricsHandler.do_GET`: `send_response` logs through
  `MetricsHandler.log_message` (450:27); `self.headers` is an
  `http.client.HTTPMessage`; `self.wfile` is `socketserver._SocketWriter`.
- `PlatformCollector._java` (`platform_collector.py:48:66`): it runs only
  when `system()` returned `"Java"`, which the `platform` module does only
  on Jython, an implementation the release does not support, so its
  receiver is a client's platform module and `java_ver()` has no callee.
  The call `self._java()` (19:35) stays: the tests' platform object
  answers `"Java"` (B5, client control flow).
- `MmapedDict` with the public `read_mode=True` opens its file `'rb'`, so
  `self._f` is a `BufferedReader` or a `BufferedRandom` (66:43 and the
  other file calls).
- `_compress_payload` (`exposition.py:791-795`): python-snappy is not
  installed; the stubs are `snappy.StreamCompressor`, `.compress` and
  `.flush` (an attribute of a stub instance through `getattr`).
- `_use_gateway` (`exposition.py:772:12`): the handler role holds
  `default_handler`, `basic_auth_handler` and `passthrough_redirect_handler`
  (named for the role in `docs/content/exporting/pushgateway.md`, and they
  bind to the five keyword arguments); `tls_auth_handler` cannot bind
  there. Its result (775:6) is `_make_handler.handle` or
  `basic_auth_handler.handle`, from those admitted handlers; what a
  client's handler returns, also a documented client wrapper, is a client
  object (B5).
- The lambda of `ProcessCollector.__init__`'s default (`pid=lambda:
  'self'`) is the node `prometheus_client.process_collector.ProcessCollector.<lambda1>`,
  as the site finder and the trace name it.
- Every `x.__init__(...)` call is a value site by name, because
  `decorator.py:291` and `299` assign an attribute `__init__`; the notes
  say so.

## Callees in libraries that the test environment does not have

aiohttp, Django, Twisted and python-snappy are not in the test environment
(its only library is asgiref 3.12.1). Their calls are named as missing
modules by the access path of the micro-benchmark rules; no copy of them
was read. One package definition is made through a missing library:
`PrometheusDjangoView` subclasses `django.views.View`
(`django/exposition.py:11`). The package never makes or calls a
`PrometheusDjangoView` (Django's view dispatch, a client, calls `get` and
`options`), so no package call goes through View's code, and the
exception for library bases and decorators adds nothing. Every such
callee (14 sites):

| Module | Site | Callee | Basis |
|---|---|---|---|
| `aiohttp.exposition` | 18:44 | `aiohttp.web.Request.query.getall` | annotation `web.Request` (J3) |
| `aiohttp.exposition` | 18:79 | `aiohttp.web.Request.query.keys` | annotation `web.Request` (J3) |
| `aiohttp.exposition` | 19:56 | `aiohttp.web.Request.headers.getall` | annotation `web.Request` (J3) |
| `aiohttp.exposition` | 30:32 | `aiohttp.web.Response` | imported `web` |
| `aiohttp.exposition` | 36:40 | `aiohttp.web.Response.enable_compression` | instance of the stub |
| `django.exposition` | 22:44, 23:53 | `django.http.HttpRequest.headers.get` | Django's documented request type (J3) |
| `django.exposition` | 33:28, 40:28 | `django.http.HttpResponse` | imported name |
| `exposition` | 791:45 | `snappy.StreamCompressor` | optional import, both sides run |
| `exposition` | 792:41 | `snappy.StreamCompressor.compress` | instance of the stub |
| `exposition` | 795:32 | `snappy.StreamCompressor.flush` | `getattr` of the stub instance |
| `twisted._exposition` | 6:57 | `twisted.web.wsgi.WSGIResource` | imported name |
| `twisted._exposition` | 7:35 | `twisted.internet.reactor.getThreadPool` | imported stub `reactor` |

The asgiref source (read only, from the unpacked pinned wheel) confirms
the two rejected ASGI edges: `ApplicationCommunicator` passes
`self.input_queue.get` and `self.output_queue.put` of `asyncio.Queue`
objects as `receive` and `send` (`asgiref/testing.py:46`).

## Rejected trace edges (7)

Client callbacks and client objects: the ASGI test communicator's queues
(`asyncio.Queue.get`, `put`), MagicMock collectors of `tests/test_core.py`
(two edges), the Mock that `tests/test_wsgi.py:73` patches over
`_bake_output` (a client change to package internals), and `list.index` on
the tests' states (J6, upheld by the referee: B4, the annotation decides),
and `FunctionMaker.__init__ -> dict.copy` on the `__dict__` of the tests'
decorated functions (B5, the jsonpickle ruling (c); Codex audit round 1).

## PyPy

**Support.** The release supports PyPy explicitly: the classifier
`Programming Language :: Python :: Implementation :: PyPy`
(`pyproject.toml:39`), the tox environment `pypy3.9` (`tox.ini:2`, `11-13`)
and the CI job `test_pypy` (`.github/workflows/ci.yaml:95-110`, PyPy 3.9).
With `requires-python = ">=3.9"` every PyPy 3.9 and later is admitted. The
sources read (as text, never run) are PyPy 3.10 v7.3.19 and 3.11 v7.3.20,
and, for Codex audit round 1, PyPy 3.9 v7.3.16: the same names hold there
(`threading.py:80` `Lock = _allocate_lock`; the pure-Python `functools.partial`,
`functools.py:281`, `__call__` at 307, with no `_functools.partial`;
`pypy/module/_collections` `defaultdict`; `pypy/module/_io`, `struct`,
`mmap`, `operator`; `sys._getframe`, `pypy/module/sys/moduledef.py:58`;
`gc.get_stats`, `app_referents.py:117`; `lib_pypy/resource.py`), and
`contextlib._GeneratorContextManagerBase.__init__(self, func, args, kwds)`
(`contextlib.py:86`) has four arguments, so `decorator.py:296:49` holds.

**Names (about 40 checked, no change).** The C-implemented callees of the
graph have the same paths on PyPy:
- `functools.partial` and `functools.partial.__call__`: PyPy has no
  `_functools.partial`, so `functools` keeps its pure-Python class
  (`lib-python/3/functools.py:282`, `__call__` at 308); same path, and its
  `__call__` calls the stored `generate_latest` back as on CPython.
- `collections.defaultdict` (`pypy/module/_collections`, `app_defaultdict`;
  `__missing__` calls the default factory) and its inherited `items` and
  `setdefault`.
- `threading.Lock`: `Lock = _allocate_lock` (`lib-python/3/threading.py:88`),
  the same public path.
- the `io` buffered classes and `io.StringIO` (`pypy/module/_io`),
  `itertools.count` and `.product`, `struct.Struct` with `pack` and
  `unpack_from`, `struct.pack`, `mmap.mmap` and `.close`, `re.compile`,
  `re.findall`, `re.Pattern.match`, `.sub`, `.findall`, `re.Match.group`,
  `operator.ne` and `.lt`, the `socket.socket` methods, `ssl.SSLContext`
  and its four methods, `sys._getframe` (`pypy/module/sys/moduledef.py:60`),
  `gc.get_stats` (`pypy/module/gc/app_referents.py:122`) and
  `resource.getpagesize` (`lib_pypy/resource.py:132`).
- the pure-Python standard library that the graph names (`inspect`,
  `contextlib`, `http.server`, `socketserver`, `wsgiref`, `urllib`,
  `platform`, `json`, `copy`, `os`) is PyPy's copy of the same modules;
  `contextlib._GeneratorContextManagerBase.__init__(self, func, args,
  kwds)` has four arguments on both PyPy versions (`contextlib.py:102`,
  `104`), so `decorator.py`'s branch of line 294 is also PyPy's.

**Call-backs (12 checked, no change).** `re.Pattern.sub` to the two
replace functions, `functools.partial.__call__` to the two
`generate_latest`, `defaultdict.__missing__` to the three lambdas,
`Thread.start` to `_RegularPush.run` and the server path of
`start_wsgi_server`, `OpenerDirector.open` to the `get_method` lambda and
`redirect_request`, `send_response` to `log_message`, `float()` to
`Timestamp.__float__`, `str.format` and the namedtuple `__repr__` to
`Timestamp.__str__` and `__repr__`, list and tuple comparison and the
reflected comparisons to the `Timestamp` operators: PyPy makes the same
calls.

**Branches (no change).** `GCCollector.__init__` returns before
`register` when `platform.python_implementation()` is not `'CPython'`
(`gc_collector.py:13`): on PyPy that edge is not made, but the graph is
the union over the runtimes and CPython makes it. The package installs no
`gc` callback (no use of `gc.callbacks`). `PlatformCollector`'s `"Java"`
branch is Jython's, not PyPy's. `process_collector.py:7-13` imports
`resource`, which PyPy has on Linux. `decorator.py`'s `sys._getframe`
fallback (line 165) is for IronPython; PyPy has `sys._getframe`.

No edge changes.

## Codex audit round 1

- Missing `MultiProcessCollector._read_metrics -> <builtin>.bytes.split`
  (`multiprocess.py:60:46`): rejected. `merge`'s `files` has no annotation;
  its docstring says "mmap files", and the package (`collect`, line 170) and
  the tests (`tests/test_multiprocess.py:444-446`, `475-478`) pass str
  paths from `glob.glob` and `os.path.join`. No contract admits a bytes
  path; a client's own bytes value stays a client value (B2, B5; the
  django-environ ruling: "a bytes default adds no bytes method"). The
  referee upheld the rejection: README, "After Codex audit round 1",
  ruling (b), "Unannotated inputs and concrete outside types (B4, B5)".
- False `FunctionMaker.__init__ -> <builtin>.dict.copy`
  (`decorator.py:136:47`): applied (-1). `func` is always a client's
  function there; calls on its `__dict__` are opaque (jsonpickle (c)). The
  trace edge is rejected.
- False `_make_handler.handle -> <builtin>.OSError` (`exposition.py:520:26`):
  applied (-1). urllib's `HTTPErrorProcessor` and `HTTPDefaultErrorHandler`
  stay in every opener that the package builds, so a non-2xx answer raises
  `HTTPError` inside `open()`; the check cannot fail.
- False `_use_gateway -> <builtin>.ValueError` (`exposition.py:770:29`):
  applied (-1). The only DELETE caller passes no compression.
- False `MmapedDict._init_value -> io.BufferedReader.fileno`
  (`mmap_dict.py:104:47`): applied (-1). A BufferedReader raises at the
  `truncate` of 103:29 first.
- Ruling (the spelling `wsgiref.handlers.BaseHandler.start_response`): the
  lead keeps the referee's spelling as a site-specific application of the
  canonical-name rule; no change.
- Unsure 1 (completeness of the TLS exception classes): no change. The
  auditor established no further pair; J5 stands.
- Unsure 2 (PyPy 3.9): decided from PyPy 3.9 v7.3.16 (see "PyPy"): the
  same names and `decorator.py:296:49`; no change.
- Metadata `219:27`: applied; the six classes are restored with the
  CPython and PyPy file paths of `load_default_certs` (no edge change).
- Metadata, a missing-library definition: applied; `PrometheusDjangoView`
  subclasses `django.views.View`, which adds no package call.
- Metadata, client-wrapper results at `775:6`: applied; the note rests on
  the admitted package handlers only.
- Metadata `decorator.py:259:47`: applied; no edge at that site (the class
  of a client callable is opaque); `str.lower` stays through 249:37.

## Codex audit round 2

- No missing and no false edge. Metadata applied: the sentence on `assert`
  statements now names both with a call (`asgi.py:12`, `decorator.py:151`,
  ledger 151:23); no ledger change.
