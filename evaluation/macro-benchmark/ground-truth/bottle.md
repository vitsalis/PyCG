# bottle: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 5 edges and adds 26. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 8 corrections to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/bottle-review.json`).
The current ledger and statistics below include all four complete audit passes.

Release 0.13.4 (commit `b0a0a10`). Analysed source: `bottle.py`, one module
with 385 functions (21 lambdas) and 71 classes; `root = "."`, so the module
is `bottle`. The support matrix and changelog admit Python 2.7 and
Python 3.8 and later; stale setup.py error text does not lower the Python
3 minimum. The package declares no dependency. Mako and Jinja2 are installed
in the test environment for the template adapters; the server adapters'
libraries, Cheetah and ujson are not.

The ledger is `bottle.ledger`; the graph `bottle.json` is generated from
it. Fourteen trace edges are rejected (`bottle.rejected.json`): thirteen are
client objects or client callbacks of the tests, and one is a generated
namedtuple constructor without a named callee under the global rule. The blind audit is in
`bottle.audit.md`; its findings F1 and F2 are applied (+8 edges, 1454 to
1462), and the lead kept J1 to J16 and ruled on N1 to N3 and R1 (see the
end of this file).

| Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections |
|---|---|---|---|---|---|---|---|---|
| 386 | 1503 (647 / 856) | 1014 (67.5%) | 489 | 14 | 291 of 385 | 1836 | 181 | 46 |

**How the ledger was drafted.** The writer read the whole module. A scratch
script merged the writer's decisions into the skeleton; it filled only
calls of builtins and of a fixed list of standard-library functions when
the call expression is that name (`len(x)`, `os.path.join(...)`), and the
`@property`, `@staticmethod`, `@classmethod` and `@DictProperty(...)`
decorators. A second scratch rule added the loads and stores of the
thread-local attributes (J1), of the DictProperty attributes of a request,
of `Bottle.catchall` and `Bottle._global_config`, and the stores through
`Bottle.__setattr__`; every generated entry was reviewed against the
source. All other entries were written by hand.

## Architecture, as the ledger uses it

- `Bottle` holds a `Router`, a list of `Route` objects, a `ConfigDict`
  overlay of a class-level `ConfigDict` (`Bottle._global_config`, a
  `lazy_attribute`), plugins and hooks. `Bottle.__setattr__` (line 1143)
  guards every attribute store of a Bottle; for the name `catchall` it
  reaches `DictProperty.__set__` through `object.__setattr__` (1146:27).
- `Bottle.__init__` installs a `JSONPlugin` and a `TemplatePlugin`.
  `Route.call` is a `cached_property` whose function applies the plugins
  (`Route._make_callback`) in reverse order of installation:
  `TemplatePlugin.apply` wraps the callback with `view` when the route has
  a `template` config, then `JSONPlugin.apply` wraps the result. Plugins
  are unique by name (`all_plugins`, line 553).
- The module-level `request` and `response` are a `LocalRequest` and a
  `LocalResponse` (lines 4603, 4607). Their `environ`, `_status_line`,
  `_status_code`, `_cookies`, `_headers` and `body` are properties made by
  `_local_property` (lines 1911-1926, 1936, 1946-1950); `bind` is
  `BaseRequest.__init__` or `BaseResponse.__init__`.
- The request properties of `BaseRequest` decorated with
  `@DictProperty(...)` (13 functions, lines 1174-1432) are DictProperty
  objects: a load runs `DictProperty.__get__`, which calls the function
  (`self.getter(obj)`, 214:58) and caches the result in the environ.
- `MultiDict`, `FormsDict`, `HeaderDict` and `WSGIHeaderDict` subclass
  `collections.abc.MutableMapping` (`DictMixin`, line 97). `ConfigDict` and
  `AppStack` subclass `dict` and `list`.
- `SimpleTemplate` compiles the template with `StplParser.translate` into
  Python code and runs it with `exec` (4259:13).

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. The server adapters, `_main`, `run`, `FileCheckerThread`, the
cookie functions and the Python 2 methods of `MultiDict` never ran in the
tests and keep their edges.

**B1. Receivers.**
- `self` in the methods of `BaseRequest` can be the `LocalRequest`
  `request`; in the methods of `BaseResponse`, the `LocalResponse`
  `response` (J1). `self` in `HTTPResponse.apply` is an `HTTPResponse`,
  never a `LocalResponse`.
- `self.prepare(...)` in `BaseTemplate.__init__` (4082:21): `BaseTemplate`
  is a plain public class, so its own `prepare` (which raises) is a
  callee, with the four adapters. At `TEMPLATES[tplid].prepare(...)` and
  `.render(...)` (4490:50, 4497:35) the object is an existing template; no
  `BaseTemplate` instance can exist, because its `__init__` always calls
  the `prepare` that raises.
- `server.run(app)` (3981:27, 3985:23): every adapter of `server_names`
  and the public base `ServerAdapter`; `AiohttpUVLoopServer` inherits
  `AiohttpServer.run`.
- `self.get_event_loop()` (3788:40): both subclasses override it, so
  `AsyncioServerAdapter.get_event_loop` is no callee.

**B2. Arguments and stored values.**
- `self.getter(obj)` (214:58), `self.func(obj)` (237:61),
  `self.getter(cls)` (249:28): the functions that the package decorates.
- `self.filters[mode](conf)` (380:65), `wildcard_filter(...)` (414:57),
  `f(query.pop(n))` (460:29): the four filter lambdas of `Router.__init__`
  and what they return; filters of `add_filter` are client callbacks.
- `cb(self, key, value)` (2526:18): the `functools.partial` of
  `trigger_hook` that `Bottle.__init__` adds. `hook(*args)` (698:21) has
  only client hooks.
- `self.meta_get(key, 'filter', ...)(value)` (2474:58): only the default
  lambda; the package sets no `filter` meta field.
- `self.reader(value)` / `self.writer(value)` (1628:27, 1631:37): `int`
  and the two lambdas of `BaseResponse.expires`.
- `cls()` in `BaseResponse.copy` (1685:19): see J7.
- `MultiDict.get(..., type=None)` (2193:24): `type` is a client cast
  function; no edge.

**B3.** The attribute name of `hasattr(self, name)` in
`BaseRequest.__setattr__` (1595:19) is the client's; the tests set `foo`
and `body` (`test_environ.py:457-465`), so `BaseRequest.__getattr__` and
the property `BaseRequest.body` are callees.

**B4. Concrete outside types.** The WSGI environ is a builtin dict (PEP
3333 requires one): its `get`, `pop`, `copy` and `keys` are `<builtin>.dict`
methods. PEP 3333 also fixes the status and header values as native strs
(728:47, 729:51, 981:47) and what the input stream's `read` returns as
bytes (1322:42, 1324:47).

**B5. Client objects are opaque.** The server's objects in the environ are
client objects: the original `wsgi.input` stream, `wsgi.errors` (1020:41,
1021:41, 1125:41, 1126:41), `wsgi.file_wrapper` (1066:60) and the server's
`start_response`. So are the exception class of a mounted application's
`exc_info` (`_raise`, 119:19 and 119:40), a value that the client stores as
a request attribute (`var.__get__`, 1587:31), the template source buffer
(4070:34), and the objects of the rejected trace edges. A public assignment
`request["wsgi.input"] = request.body` reuses the package-created BytesIO
or temporary file in the same role and clears the body cache. Its read
methods therefore count in `_iter_body` and `_iter_chunked`.

**C. Public.** Public: the module's names without an underscore, among
them `Bottle`, `BaseRequest`, `LocalRequest`, `BaseResponse`,
`LocalResponse`, `HTTPResponse`, `HTTPError`, `DictProperty`,
`cached_property`, `lazy_attribute`, `HeaderProperty`, `MultiDict`,
`FormsDict`, `HeaderDict`, `WSGIHeaderDict`, `ConfigDict`, `AppStack`,
`ResourceManager`, `FileUpload`, the adapters and templates. Private:
`_MultipartParser`, `_MultipartPart`, `_ImportRedirect`, `_closeiter`,
`_local_property`, `_rangeiter`, `_parse_*`, `_hkey`, `_hval`, `_lscmp`,
`_cli_*`, `_main`, `_raise`, `_stderr`.

## Default rejections

46 defaults decide 12,945 candidate-site pairs: the `__getattr__` of
`BaseRequest` and `FormsDict` (1,638 and 1,639 sites), the item, length,
iteration, containment and `repr` special methods of the dict-like classes
(74 to 597 sites each), the `__get__` and `__set__` of the four
descriptor classes (50 to 218), the `__setattr__` of `BaseRequest` and
`Bottle` (204 and 197), and the `keys` and `get` methods (63 to 75). Each
site where one of them runs accepts it explicitly (for example `response`
in `_cast`, 1037:33 to 1050:25; the FormsDict stores of the request
properties; the ConfigDict stores; `self[name]` in `getunicode`,
2251:34). The report's explicit sites under each default were read; none
hides a call.

## Value sites

181. The hard ones: the route callback (996:37, 2026:30, 4521:26: J11),
the error handler (1057:69), the mounted application and its
`start_response` (736:27, 1113:27, 1128:27: J9), `getattr(app(), name)(...)`
(3193:36: the twelve Bottle methods of lines 3198-3209), the adapters'
`handler` (the default or a loaded Bottle: `Bottle.__call__`), `tonat`
(`touni` and `tob`), `json_loads`, `callable`, `imap`, `urlunquote` and
`getargspec` (both Python branches: J2), and the file methods bound in
`_copy_file`, `write_body` and `WSGIFileWrapper.__iter__`.

## Judgement calls

- **J1. Thread-local properties.** A load or store of `environ` on `self`
  in a `BaseRequest` method, or on `request`, calls
  `_local_property.fget` or `.fset`; so do `_status_line`, `_status_code`,
  `_cookies`, `_headers` and `body` on `self` in a `BaseResponse` method,
  on `response`, on `other` in `HTTPResponse.apply` (1970-1974) and on
  `copy` in `BaseResponse.copy` (1687, 1689). `self.environ = ...` in
  `BaseRequest.__init__` goes through `BaseRequest.__setattr__`, whose
  `object.__setattr__` calls `fset` (1593:56). The site finder proposes no
  candidate for these accessors (they are not functions of the class
  body). The trace confirms them.
- **J2. Python 2 branches** (lines 120-145, 160, 2158-2179). They run
  (lead's ruling 2). Same function under a renamed module: the Python 3
  name only (`urllib.parse.urljoin`, `http.cookies.SimpleCookie`,
  `configparser.ConfigParser`, `_thread.interrupt_main`, `pickle.loads`).
  Only in Python 2: the Python 2 name (`StringIO.StringIO` and its
  methods for `BytesIO`, line 130; `itertools.imap`; `inspect.getargspec`;
  `imp.new_module`; `<builtin>.callable`; `<builtin>.dict.iteritems`,
  `iterkeys`, `itervalues`); `json_loads` is `json_lds` (`json.loads`,
  `ujson.loads`), `tonat` is `tob`, and the Python 2 str that `tob` makes
  keeps that type where it flows (bytes by its Python 3 name; ruling R-c
  below). The `_raise` that `exec` defines on
  Python 2 (line 145) is generated code without a node, so 723:31 names
  only `bottle._raise`. Behaviour of the standard library that differs
  between versions without a branch in bottle (the methods of
  `NamedTemporaryFile`, `functools.partial`) is named by Python 3 only.
- **J3. Templates run with exec** (4259:13). The calls of the executed
  code belong to `execute` (the micro-benchmark rule for `exec`); the code
  is generated, so it has no node. The ledger names what the generated
  code calls (`_printlist` = `list.extend`, `_str` and `_escape` = the
  lambdas of `prepare`), the documented template functions (`include` and
  `rebase` through `functools.partial`, `get`, `setdefault`, `defined` =
  dict methods of the environment, `docs/stpl.rst`), and what the
  package's own `ERROR_PAGE_TEMPLATE` (line 4560) calls: `e.status`
  (`BaseResponse._get_status`), `request.url`, `repr`, `type`. Other calls
  of a client template are client code. The trace has the package
  callees of this site.
- **J4. Optional libraries** (lines 3489-3804, 4154, 82). Ordinary
  missing-library calls keep their imported access paths and do not
  invoke callbacks. `GunicornApplication(BaseApplication)` falls under
  the global package-definition-through-library exception. Pinned
  Gunicorn 27.0.1 source shows constructor dispatch to `load_config`,
  concrete `gunicorn.config.Config.set`, and run-time dispatch to `load`,
  the Bottle application and package output iteration/close callbacks.
  The constructor callback belongs to 3730:28; run callbacks belong to
  3730:34. The standard-library wsgiref adapters likewise invoke the
  application and their package handler overrides.

  Gunicorn 27.0.1 sources were read without execution. Source URLs use
  `https://raw.githubusercontent.com/benoitc/gunicorn/27.0.1/` plus the path below.

  | Source path | SHA-256 |
  | --- | --- |
  | `gunicorn/app/base.py` | `2448c3fd62c03b08e7cb6688e52de5d86ac60773d98e848e1ebfb4cb1dd6689e` |
  | `gunicorn/arbiter.py` | `52f69bfc279fe07ba602bb658067802184bf15364d3c4f4385738661d0ffe05a` |
  | `gunicorn/config.py` | `d7609a46b5e88df488d1f83dcc4c99ef44ae510e81bd53f8b6d04db62071fcd5` |
  | `gunicorn/http/wsgi.py` | `2b8be67bf98bb3f1dcee2f301cb5830c27d86336ba796f612840b8bab64a96b0` |
  | `gunicorn/workers/base.py` | `9a39e0e16d6233298a3db01442c7913f17329e05caff9eb3263edc9037f50ed3` |
  | `gunicorn/workers/sync.py` | `cdd76b61e7c2d529dc301f83fd6129df632c5078ca53280d52e48c9a948b32ec` |
- **J5. Signal handlers** (3705, 3793). `signal.signal` only stores the
  lambda; the lambda is a callee of the blocking call where the package
  waits while it is installed (`serve_forever`, 3706:29; `serve`,
  3795:14), as in the asciinema ruling. Both run only in a reloader child.
- **J6. Import hook** (lines 2066-2105, 4618). Importing bottle puts an
  `_ImportRedirect` into `sys.meta_path`. The `__import__` calls of the
  package (2101:19, 3859:45) make the import system call its `find_spec`
  (`find_module` on Python 2); for a target in the documented virtual
  package `bottle.ext`, `load` also runs `create_module` and `exec_module`
  (`load_module` on Python 2). The trace has
  `_ImportRedirect.load_module -> find_spec`. Import statements are not
  call sites, so the finder calls that they trigger have no site.
- **J7. `BaseResponse.copy(cls)`** (1684-1689). The `issubclass` check
  admits any subclass of `BaseResponse` (the anytree ruling on
  `isinstance` checks): `HTTPError()` runs `HTTPError.__init__`, a
  `LocalResponse` makes the stores of 1687 and 1689 call `fset`;
  `MultipartError()` cannot bind `msg` (no edge). Only `redirect` passes a
  class (`HTTPResponse`).
- **J8. hasattr on a request** (1595:19): see B3.
- **J9. A Bottle mounted as a WSGI application.** `_mount_app` falls back
  to `_mount_wsgi` for a Bottle in three cases (lines 752-765). Then
  `app(...)` runs `Bottle.__call__` (736:27); the child's `wsgi` calls the
  `start_response` of `mountpoint_wrapper` (1113:27, 1128:27); the child's
  output (a `_closeiter`, a `WSGIFileWrapper` or a map of
  `_cast.<lambda1>`) becomes the body of the parent's `HTTPResponse`
  itself (line 737: `rs.body` is empty, so no chain), which the parent's
  `_cast` iterates (1072:24, 1093:28) and a client can iterate through
  `BaseResponse.__iter__` (1696:20).
- **J10. `_closeiter` bodies.** A static_file range response has a
  `_closeiter` body (2944:35); `_cast` iterates it through `out.body`
  (1072:24), a client can iterate the response (`BaseResponse.__iter__`,
  1696:20), and `BaseResponse.close` and `_closeiter.close` close it
  (1700:28, 2651:17).
- **J11. Route callbacks** (996:37, 2026:30, 4521:26). Package values in
  the callback role: `mountpoint_wrapper` (mount routes skip every plugin,
  line 742), the wrappers of `JSONPlugin` and of `view` (TemplatePlugin),
  and the wrappers of `@view` and `@auth_basic` on a callback (documented
  in `docs/tutorial.rst:714` and used by `test_auth.py:9`). A plugin
  without `apply` (565:38) is a client decorator; no package decorator is
  installed as one. A client may reuse `Route.call` unchanged as a new
  route callback or pass it to `view` or `auth_basic`. Plugin uniqueness
  and mount skip settings constrain the original route, not this public
  reuse; all nine additional wrapper-to-wrapper pairs count.
- **J12. `repr(E)` in `Bottle.wsgi`** (1124:43). Exceptions escaping
  client callbacks are opaque under B5. A client handler that calls
  `abort` or `redirect` does not supply an admitted BaseResponse receiver
  at this site; remove `BaseResponse.__repr__`.
- **J13. Closing the output** (1108:52). A WSGIFileWrapper receives an
  opaque client file here. A static_file response is enclosed by the
  package `_closeiter`, whose separate close edge remains. There is no
  direct `io.BufferedReader.close` edge at this site. Likewise
  `WSGIFileWrapper.__iter__` does not name the client file's read method.
  `_MultipartPart.raw` is reached only for buffered parts, so its read,
  seek and tell sites name BytesIO/StringIO, not temporary-file wrappers.
- **J14. Jinja2 loader** (4183:45, 4190:31). `get_template` calls the
  bound `Jinja2Template.loader` through the `FunctionLoader`; a template
  that extends or includes another at render time does too, and a cached
  template is checked with the loader's `uptodate` lambda (line 4199).
- **J15. `super(FormsDict, self).__getattr__(name)`** (2258:54). No class
  after `FormsDict` in the MRO defines `__getattr__`, so the attribute load
  raises `AttributeError` before any call: no edge.
- **J16. Classes without `__init__`.** `TemplatePlugin()` (662:36) and
  `_UTC()` (140:15, Python 2) reach `object.__init__`: no edge.
  `AppStack()` (4614:36) names `<builtin>.list.__init__`; the package
  exceptions without `__init__` name `<builtin>.Exception.__init__`.

## Rejected trace edges

`bottle.rejected.json`: the validator's `wsgi.errors` and
`start_response` (3), `map(tob, ...)` built
by a test route (`test_outputfilter.py:24`), the `filter` meta fields
`bool` and `int` of `test_config.py:59-60`, the files and destinations
that `test_fileupload.py` passes to `FileUpload` and `save` (5), a test
route's `BytesIO` in `WSGIFileWrapper`, and the close of a test route's
generator. It also records `BaseRequest.urlparts -> urllib.parse.SplitResult`
at `bottle.py:1449`: the inherited namedtuple constructor is generated library
code and has no named constructor edge under the round-3 ruling. The ordinary
`SplitResult.geturl` call at `bottle.py:1430` remains a separate edge.

## Audit findings applied

- **F1 (+6).** wsgiref's `BaseHandler.run` iterates the application's
  output and closes it (`wsgiref/handlers.py`: `finish_response`, `close`).
  Under `CGIServer.run` (3495:25) and `WSGIRefServer.run` (3532:35) the
  output of `Bottle.wsgi` can be a `_closeiter` (a static_file range
  response, or an iterable with `close`) or a map of `_cast.<lambda1>`, so
  both sites add `_closeiter.__iter__`, `_closeiter.close` and
  `Bottle._cast.<lambda1>`. Public request mutation can remove the
  `wsgi.file_wrapper` key, so both adapters also iterate the package
  WSGIFileWrapper. For Gunicorn, a client file's close property can
  restore the saved wrapper class after `_cast` selects its absent-key
  branch; the worker then iterates the package wrapper. Client side
  effects affect control flow without naming client methods.
- **F2 (+2, Python 2).** At 1806:48 on Python 2, `UTC` is the package's
  `_UTC` (line 140); `datetime.fromtimestamp(t, tz)` converts with the
  inherited `tzinfo.fromutc`, which calls back `_UTC.utcoffset` and
  `_UTC.dst`. This completes J2.

## Lead's rulings on the audit

- N1: an exception that escapes a client callback is a client value; no
  edge at `_raise` (119:19).
- N2: the result of a client callback is a client object (B5); an
  `isinstance` test against an outside abstract type names no package
  class there (4524:31 unchanged).
- N3: library behaviour that differs between Python 2 and 3 without a
  branch in bottle is named for Python 3 (J2).
- R1: the callbacks of a lazy `map` or `filter` may stay at the call that
  builds the iterator when the iteration is in the same function (584:40,
  1093:28, 1226:31 unchanged).

## Corrections after the look, 2026-11-14

A second blind audit of four sites (`.git/handover/round3/audit3b-bottle.md`)
and the lead's rulings R-a to R-c changed the graph from 1462 to 1461
edges (608 inside, 853 outside).

- **R-a (-12).** `depr(0, 13, msg)` in `FapwsServer.run` (3613:13) and
  `DieselServer.run` (3682:13) passes three arguments, and `depr` needs
  four (line 181): `TypeError` before `depr` starts, on every version
  (README "Edges" and "Judgements"). The calls have no edge, and neither has
  the code after them (3617:17 to 3632:19; 3684:30, 3685:16); the `def app`
  at 3627 never runs, so `FapwsServer.run.app` has no edge (3629:27). Each
  explicit site keeps its entry with a note. Removed: 8 edges of
  `FapwsServer.run`, `FapwsServer.run.app -> Bottle.__call__`, 3 edges of
  `DieselServer.run`. Every other `depr` call has four arguments or more.
- **R-b (+1).** The package stores a `WSGIFileWrapper` as a body: a Bottle
  mounted as a WSGI application whose route returns a file, when the
  environ has no `wsgi.file_wrapper`, returns one from its `_cast`, and
  line 737 makes it the parent's body. `BaseResponse.__iter__` (1696:20)
  accepts `WSGIFileWrapper.__iter__` (B2). Placement only: the two
  `__iter__` methods of the child's output move from `next(iout)`
  (1073:25, 1075:29) to `iter(out)` (1072:24), since line 737 makes no
  chain.
- **R-c (+10, Python 2).** `tonat = tob` (line 160) makes Python 2 str
  values, bytes by their Python 3 name, and they keep that type where they
  flow. I checked each receiver: the header values of `headerlist`
  (`BaseResponse.__repr__`, 1907:59) and `content_type` in
  `BaseResponse.charset` (1813:43, :65, :79) go through `_hval` (1613); the
  Content-Disposition and Content-Type of a multipart part go through
  `HeaderDict.__setitem__` and `_hval` (2279) into `_parse_http_header`
  (its 13 string sites, 3027-3046) and `self.filename.split` (3422:52); the
  POST body is `tonat(..., 'latin1')` (1401) into `_parse_qsl` (3054:25,
  3056:24, 3058:39, 3059:41). Added next to the `str` callees:
  `BaseResponse.__repr__ -> bytes.strip`; `BaseResponse.charset ->
  bytes.split, bytes.strip`; `_MultipartPart.finish_header -> bytes.split`;
  `_parse_http_header -> bytes.split, .strip, .lower, .replace`;
  `_parse_qsl -> bytes.split, bytes.replace`. Values from the environ and
  the cookies stay `str` (ruling N3: no branch in bottle makes them).

`http_date` also reaches `_UTC.utcoffset` through `utctimetuple`: a
client can pass the package-created date exposed by the public expires
property. Bottle 0.13 explicitly dropped Python 3.1-3.7 in its support
matrix and changelog; stale setup.py error prose does not admit those
runtimes, so no historical `_sre` receiver names are added.

## Third complete source audit (2026-11-16)

The source-first model and source/support inventory were frozen before opening Bottle ground truth. The full audit checked all 1,482 baseline pairs, 4,768 scanner sites, all 2,932 omitted sites, 46 default exclusions, and every own-target binding. Milestone review retains 1 false-positive baseline pair and 1 missing baseline pair. Three proposed additions were withdrawn; they are not baseline false positives.

* Remove BaseRequest.urlparts -> urllib.parse.SplitResult (1449): generated namedtuple construction has no named edge under the global rule. Reject its traced constructor edge explicitly.
* Add static_file -> _sha1.sha1.hexdigest (2918), the CPython hashlib fallback receiver. The proposed PyPy-only _sha1.sha.hexdigest is excluded: Bottle has no current explicit PyPy support declaration under the selected interpreter rule.
* Withdraw the proposed WSGIFileWrapper.__iter__ -> io.BufferedReader.read (2632/2635) and Bottle.wsgi -> io.BufferedReader.close (1108). Their witnesses pass through a client callback result, which remains opaque under B5 even when the example returns static_file output. BaseResponse.close -> io.BufferedReader.close remains unchanged.

Site-only corrections exclude the unreachable strict DEBUG branch186 while retaining its pair at188, and correct the samesite note to Python2.7 only. The map/filter placements are allowed normalizations under README ruling12: the encoder witness moves from1093:28 to1073:25/1075:29, and the filter gains a consumer witness at584:28 while retaining584:40. Either placement within the same function is permitted; these changes are not false positives, false negatives, or corrections to an invalid prior placement. The parser's missing-boundary site remains valid through a first-use client str subclass with varying truth, and direct issubclass(cls,BaseResponse) establishes the type-valued response role at copy1685. MultipartError still fails no-argument binding. Earlier audit narratives and their dated counts are historical.

Evidence: the immutable round-3 review, exact edits, primary-source provenance, and six-file replay are in the review handoff; no target, dependency, test, or generated code was imported/executed and no PyCG output was used.

## Fourth complete audit (2026-11-16)

The fresh source-first audit retained all 1,482 baseline pairs and added 21
missed pairs at 29 existing ledger sites. These are BaseRequest.__getattr__
callbacks after AttributeError from a request property or DictProperty.
A public BaseRequest(environ), or successful LocalRequest.bind(environ),
can receive a client dict subclass whose selected get or membership operation
raises AttributeError. Python then invokes the package fallback. Client
methods stay opaque. The witnesses use a first public operation after successful
construction, preserve required earlier operations and never reuse failed state.
The built-in error page contributes the SimpleTemplate.execute pair through
its literal request.url expression. No arbitrary client template is assumed.

The __getattr__ default rejection now distinguishes these property failures
from ordinary existing methods and initialized environ access. This is part of
the edge correction, not a separate metadata defect. All other defaults and
explicit exclusions were reviewed. Counts above include the correction.

The support scope is CPython 2.7.3 and later within 2.x, plus CPython 3.8 and
later, without an inferred upper bound. The 0.13 changelog explicitly drops
earlier versions despite stale setup/tox text. No current alternative-interpreter
support is established; the previous pass's exclusion of PyPy targets stands.
The normal/-O/-OO union remains a working global assumption, not an answered
user preference. Removing copy's assert does not create an arbitrary class role:
its explicit BaseResponse subclass check names that role, including LocalResponse
and HTTPError. MultipartError() fails argument binding. HeaderProperty's
__doc__ assignment remains executable under -OO. No further edge change follows.

Evidence: audits/2026-11-15/pass-4/bottle/, including source freeze,
fallback-witnesses.json, pair/site/body/default coverage and review.md.
