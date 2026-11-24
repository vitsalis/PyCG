# bottle: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [bottle.md](bottle.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release 0.13.4, commit `b0a0a1014f7a7e6f6b7c193886a0913f46ee3ee6`, analysed
source `bottle.py`. Audited files (untracked in the worktree at the time of
the audit, identified by SHA-256):

| File | SHA-256 (first 12) | Content |
|---|---|---|
| `bottle.ledger` | `e1c239caf740` | 1836 entries, 418 notes, 449 rejections, 46 default rejections |
| `bottle.json` | `a21036deef00` | 386 nodes, 1454 edges (603 in the package, 851 outside) |
| `bottle.rejected.json` | `bb4423afd6c8` | 15 rejected trace edges |
| `bottle.md` | `b8fb8af0107f` | judgements J1-J16 |

`check.py --benchmark-dir macro-benchmark-heldout-3 bottle` reports no
errors. The trace confirms 1013 edges (69.7%), 441 come from reading only,
291 of 385 functions run, and 89 nodes have no caller.

I judged the files by the scope rules A, B1-B5 and C, the conventions of
`macro-benchmark/README.md`, and the lead's rulings for the held-out sets
(ruling 2 of the third set: Python 2 branches run; libraries of the optional
adapters that are not installed are missing modules). I read `bottle.py`,
`setup.py`, the documentation and the tests as data. I ran no static
analysis tool and did not run or import the package. I read the standard
library's `wsgiref` source to check one finding.

**Result.** 2 findings that add edges (F1, F2: +8 edges, all in the
package), 1 remark on placement (R1, no edge change), and 3 cases that the
README does not decide (N1-N3; my proposals change nothing). With F1 and F2
the graph has 1462 edges (611 in the package, 851 outside).

## Findings

| Id | Severity | Site | Evidence | Edges |
|---|---|---|---|---|
| F1 | medium (missing edges) | `WSGIRefServer.run` 3532:35 `self.srv.serve_forever()`; `CGIServer.run` 3495:25 `CGIHandler().run(fixed_environ)` | The ledger names what wsgiref calls back on a request (the application, `FixedHandler.log_request`, `address_string`), but not what it does with the application's output. wsgiref's `BaseHandler.run` stores the return value of the application, iterates it in `finish_response` (`for data in self.result`) and closes it (`self.result.close()`) (`wsgiref/handlers.py:138, 184, 191, 343` of the local CPython; Python 2.7's wsgiref does the same). The output of `Bottle.wsgi` is what `_cast` returns. (1) A `static_file` range response has a `_closeiter` body (2944); `_cast` re-wraps it as `_closeiter(new_iter, out.close)` (1097-1098) and returns it, so wsgiref calls `_closeiter.__iter__` and `_closeiter.close`. (2) An iterable of text without `close` comes back as `imap(encoder, ...)` (1093) and one with `close` as a `_closeiter` over it, so wsgiref's iteration calls `Bottle._cast.<lambda1>`. This is the reasoning of J9 and J10, applied to the server that the package itself starts (a library object that the package creates: the callback rule of B5). `WSGIFileWrapper.__iter__` is not added: wsgiref always sets `wsgi.file_wrapper` (`handlers.py:167-168`), so `_cast` takes the branch of 1065-1066 and never builds a `WSGIFileWrapper` under these two servers. The edges belong to the two adapter sites (the library frames are transparent, the `Bottle.__call__` frame has returned). | +6: `bottle.WSGIRefServer.run` and `bottle.CGIServer.run` each -> `bottle._closeiter.__iter__`, `bottle._closeiter.close`, `bottle.Bottle._cast.<lambda1>` |
| F2 | low (missing edges, Python 2 branch) | `BaseResponse.<lambda1>` 1806:48 `datetime.fromtimestamp(parse_date(x), UTC)` | On Python 2, which runs (ruling 2), `UTC` is `_UTC()` (lines 134-140), a package `tzinfo` subclass that does not define `fromutc`. Python 2.7's `datetime.fromtimestamp(t, tz)` converts with `tz.fromutc(dt)`; the inherited C `tzinfo.fromutc` calls `tz.utcoffset(dt)` and `tz.dst(dt)`. Both are package functions that library code calls back from this site. The ledger lists only `datetime.datetime.fromtimestamp`, and `_UTC.utcoffset` and `_UTC.dst` have no caller in the graph. On Python 3, `UTC` is `timezone.utc` and nothing changes. `_UTC.tzname` stays without a caller. | +2: `bottle.BaseResponse.<lambda1>` -> `bottle._UTC.utcoffset`, `bottle._UTC.dst` |

## Remark (no edge change)

**R1. Callbacks of a lazy `map` or `filter` are placed at the call that
builds the object, not where it is iterated.** 1093:28
`imap(encoder, ...)` accepts `Bottle._cast.<lambda1>`, 1226:31 `map(tob, ...)`
accepts `bottle.tob`, and 584:40 `filter(isfunc, ...)` accepts the lambda of
`get_undecorated_callback`. On Python 3 these calls only build the iterator;
the function runs where the object is iterated: the unpacking of 1226:13,
`next(...)` at 584:28, and, for 1093:28, the parent `_cast`'s `next(iout)`
(1073:25, 1075:29; the note at 1093:28 says so) and the server (F1). The
README's "Limits of the site finder" puts such an edge at the iteration
site. Each pair is in one function, so the graph is the same. Optional fix:
move the lambda of 1093:28 to 1073:25 and 1075:29, whose notes list only the
two `__iter__` methods. (On Python 2, `map` is eager, so 1226:31 is exactly
right there.)

## Cases the README does not decide

**N1. Exception classes that a mounted Bottle passes to `_raise`** (119:19).
The ledger says the exception class of `exc_info` is a client value. When a
Bottle is mounted through the WSGI fallback (J9), the child's `wsgi` passes
`sys.exc_info()` of an exception that its `_handle` caught (1022, 1110-1113);
that exception can come from package code under a client handler
(`TemplateError` 4079, `RouteBuildError` 456, builtin errors that the package
raises). `a[0](a[1])` would then run `<builtin>.Exception.__init__` (+1) or
instantiate builtin exception classes (an open set). Proposed ruling: an
exception that escapes a client callback is a client value (the same idea as
B5's object that a client callback returns). No change.

**N2. `isinstance(result, (dict, DictMixin))` in the view wrapper** (4522,
4524:31 `tplvars.update(result)`). `DictMixin` is
`collections.abc.MutableMapping`, which `MultiDict`, `FormsDict`,
`HeaderDict` and `WSGIHeaderDict` subclass. If the check names them for the
role, `dict.update` calls back their `keys` and `__getitem__` (+5:
`MultiDict.keys`, `WSGIHeaderDict.keys`, `MultiDict.__getitem__`,
`HeaderDict.__getitem__`, `WSGIHeaderDict.__getitem__`). Proposed ruling: no.
The value is what a client callback returns (B5), the check names an
abstract type from outside the package, and no document, test or package
code returns one of these classes from a `@view` handler (B2: an abstract
outside type names a package class only for a role the package implements).
No change.

**N3. Python 2 behaviour of the standard library without a branch in
bottle.** J2 names such behaviour by Python 3 only. One case changes callees:
on Python 2.7, `tempfile._TemporaryFileWrapper.__getattr__` returns the
underlying file's bound method (no `func_wrapper`), so the methods called on
a `NamedTemporaryFile` are those of the file. Named by the README's rule for
Python 2 builtins (the Python 3 name of the type), that adds 13 edges
`io.BufferedRandom.{read,write,seek,tell}` (`_body` 2, `_get_body_string` 1,
`body` 1, `_copy_file` 3, `_lineiter` 1, `write_body` 1, `finish` 1, `raw` 3).
The files that `open()` returns are named `io.Buffered*` already, which is
also what that rule gives for Python 2's `file`. Proposed ruling: keep J2
(the version rule is about the package's own branches); the lead decides.

## Step 1: blind re-derivation

**Sample.** I built a scratch directory `$TMPDIR/heldout3-audit-bottle/` with
a copy of `projects.toml` and a link to `projects/`, and made the skeleton
without the ledger (4413 sites, 181 value sites). `getattr` sites are 1601
of the 4413, so I drew by kind: from the sites that are not value sites, one
`random.Random(20261111)` drew 35 explicit sites (of 1359), then 15
attribute sites (of 1802), then 20 other implicit sites (of 1071). With all
181 value sites: 251 sites. My answers are in `blind.txt` of the scratch
directory, written before I opened the writer's files.

Two process slips, recorded: (1) one `git log` ran with the project checkout
as working directory (no project code ran); (2) a grep for the naming of
`@functools.wraps(...)` in the other ledgers also printed, by a glob error,
the writer's two entries 2023:10 and 3171:10 (`-> functools.partial.__call__`).
I took that convention from the tenacity, pypinyin and pyflakes ledgers, and
I count the two sites as agreeing.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Value sites | 181 | 176 | 5 |
| Random explicit | 35 | 35 | 0 |
| Random attribute | 15 | 15 | 0 |
| Random other implicit | 20 | 20 | 0 |
| **Total** | **251** | **246** | **5 (2.0%)** |

The 5 disagreements, classified:

- **I was wrong (4):** 2782:23, 3264:25, 3404:29 (`read` of a multipart
  buffer): I missed `StringIO.StringIO.read`, the Python 2 `BytesIO`
  (line 130). 4521:26 (`func` of the view wrapper): I missed
  `auth_basic.decorator.wrapper`, which reaches it when `TemplatePlugin`
  wraps a callback decorated with `@auth_basic`.
- **Placement only (1):** 1093:28, see R1.
- **The writer missed an edge (0). The writer has an edge that cannot
  happen (0).**

At my judgement points the writer decided as I did: 119:19 and 1066:60 (no
edge, B5), 565:38 (no package plugin without `apply`), 1685:19 (the
`issubclass` check admits `HTTPError`), 475:39 (static routes store no
`getargs`).

## Step 2: exhaustive checks

**Default rejections (46, 12,946 pairs).** For each candidate I listed where
it can run and checked that those sites accept it. `BaseRequest.__getattr__`:
I scanned its 1638 sites for receivers that can be a request (`request.`,
`self.` in `BaseRequest` methods, the `getattr` and `hasattr` calls); every
attribute that package code loads from a request is a slot, a property, a
`DictProperty` or a method, so it runs only under `hasattr(self, name)` at
1595:19, which accepts it.
`FormsDict.__getattr__`: package code loads only `recode_unicode`,
`input_encoding`, `dict` and methods; the super call of 2258:54 raises before
any call (J15). Item, containment and length methods: the package subscripts
or tests only `response` in `_cast` (1037-1050), `obj` in
`HeaderProperty.__set__`/`__delete__` (1631:12, 1634:16), `self` in
`path_shift` and `__delitem__` (1479, 1549), the FormsDict stores of the
request properties, the ConfigDict stores (219:32, 643, 648, 768, 769, 2427,
2444, 2461, 2465, 4664) and `self[name]` in `getunicode`; all accept. Iteration:
`WSGIHeaderDict.keys` (2350:28), `_cast` (1072:24, 1073:25, 1075:29) and
`BaseResponse.__iter__` (1696:20) accept; the servers' iteration is F1.
Descriptors: every load of a `DictProperty`, `cached_property`,
`lazy_attribute` or `HeaderProperty` attribute in package code is accepted
(28 loads), and so are the stores 2034:26, 2038:20 (`HeaderProperty.__set__`)
and 1146:27 (`DictProperty.__set__`). `__setattr__`: 1171:14 and the eight Bottle stores (631-660, 2053).
`__repr__`: 3969:39 and 1124:43 (J12). No other site where a defaulted
candidate runs.

**Thread-local properties (J1).** I compared every load and store of
`environ`, `_status_line`, `_status_code`, `_cookies`, `_headers` and `body`
in the skeleton with the ledger. The 28 sites without an accessor are right:
18 have receivers that cannot be a `LocalRequest` or `LocalResponse`
(`HTTPResponse` objects in `apply`, `mountpoint_wrapper`, `redirect` and the
JSON wrapper; `WSGIHeaderDict.environ`; `os.environ`), and 10 have other
callees (`BaseRequest.body` at 1365 and 1411, `BaseRequest.__setattr__` at
1171:14, the bodies of `HTTPResponse` objects). `object.__setattr__` (1593:56) and
`getattr(obj, self.attr)` (213:41) reach `fset` and `fget`; 219 and 223 do
not (the request properties are read-only). No `del` of these attributes
exists, so `fdel` has no caller, correctly.

**Templates (J3).** The executed code's callees at 4259:13 are complete for
what `StplParser` emits (`_printlist`, `_str`, `_escape`), the documented
helpers, and `ERROR_PAGE_TEMPLATE` (`e.status`, `request.url`, `repr`,
`type`). The trace confirms `_include`, both lambdas, `url` and
`_get_status`. Jinja2's loader callbacks (4183:45, 4190:31) and Mako (no
callback) are right.

**Python 2 (J2).** Checked the aliases at every use: `tonat`, `json_loads`,
`callable`, `imap`, `urlunquote`, `getargspec`, `new_module`, `BytesIO`
(`StringIO.StringIO` and its methods at the buffer sites: constructor,
`read`, `write`, `seek`, `tell`, `getvalue`, `close`), `iteritems` and friends, `thread`,
`httplib`, renamed modules. All consistent with the README. Found F2 and N3.

**Optional adapters (J4).** All stub names follow the missing-module rules
(calls return instances; attributes of instances lengthen the path; no
callbacks). `isinstance(..., local.local)` (3696) against a stub would raise
before the server starts; treating the code after it as running, as the
ledger does, matches the real library and the ruling. Signal lambdas (J5)
follow the asciinema ruling.

**Functions without a caller (89).** Each is client API (route shortcuts,
`static_file`, `redirect`, the request and response accessors, the
`HeaderDict`/`MultiDict` methods, `ResourceManager`), a Python 2 alias, a
stub callback (`GunicornApplication.load*`, the App Engine and Fapws
functions), `_local_property.fdel`, or `_UTC.utcoffset`/`dst` (F2).

**Rejected trace edges (15).** All are client objects or callbacks of the
tests (B5): the tests' `wsgi.input`, validator streams and `start_response`,
the `map(tob, ...)` that a test route returns, the `filter` meta fields of
`test_config.py`, the files that `test_fileupload.py` passes, a test route's
`BytesIO`, and a test generator's `close`. Agreed.

**Judgements J1-J16.** Agreed, with F1 (J4 omits the output iteration) and
F2 (J2). J7, J9-J14 match my blind reasoning.

## README and tools

- The README does not say where the callback of a lazy `map` or `filter`
  goes when library code started elsewhere iterates it (R1, F1). A sentence
  under "Limits of the site finder" would help.
- B2's `isinstance` rule and B5's "object that a client callback returns"
  pull in opposite directions at 4522 (N2).
- The version rule covers the package's branches but not library behaviour
  that differs between supported versions (N3).
- `check.py --report <name> --default <candidate>` prints the whole report
  around the default's list; usable, but long (3634 lines here).

## Third complete source audit (2026-11-16)

The source-first model and source/support inventory were frozen before opening Bottle ground truth. The full audit checked all 1,482 baseline pairs, 4,768 scanner sites, all 2,932 omitted sites, 46 default exclusions, and every own-target binding. It found 1 false-positive pair and 4 missing pairs; no issue is unresolved.

* Remove BaseRequest.urlparts -> urllib.parse.SplitResult (1449): generated namedtuple construction has no named edge under the global rule. Reject its traced constructor edge explicitly.
* Add static_file -> _sha1.sha1.hexdigest and -> _sha1.sha.hexdigest (2918), the documented CPython and PyPy hashlib fallback receivers. Official pinned primary bytes establish each concrete class.
* Add WSGIFileWrapper.__iter__ -> io.BufferedReader.read (2632/2635) and Bottle.wsgi -> io.BufferedReader.close (1108). The Serving Assets example explicitly names static_file output for the route-output role. B2 preserves that package factory output through _handle/_cast; B5 still hides arbitrary unnamed callback results. A GET file response whose public status property is set to204 exercises1108.

Site-only corrections exclude the unreachable strict DEBUG branch186 while retaining its pair at188; move the lazy encoder witness from construction1093 to consumption1073/1075; add the Python3 filter consumption584:28 while retaining eager Python2 filter584:40; and correct the samesite note to Python2.7 only. The parser's missing-boundary site remains valid through a first-use client str subclass with varying truth, and direct issubclass(cls,BaseResponse) establishes the type-valued response role at copy1685. MultipartError still fails no-argument binding. Earlier audit narratives and their dated counts are historical.

Evidence: the immutable round-3 review, exact edits, primary-source provenance, and six-file replay are in the review handoff; no target, dependency, test, or generated code was imported/executed and no PyCG output was used.

## Milestone review correction (2026-11-16)

This record corrects the round-3 proposal above without changing its bytes.
The retained baseline delta is +1/-1: `static_file -> _sha1.sha1.hexdigest`
is added and `BaseRequest.urlparts -> urllib.parse.SplitResult` is removed.
The revised graph has 1,482 pairs (626 inside, 856 outside) and 1,956
site-target relations. The stored origin result confirms 1,014 pairs
(68.4%); 468 come from reading only.

Three proposed additions are withdrawn. `_sha1.sha.hexdigest` is PyPy-only,
and Bottle has no current explicit PyPy support declaration. The proposed
`Bottle.wsgi -> io.BufferedReader.close` and
`WSGIFileWrapper.__iter__ -> io.BufferedReader.read` depend on client callback
results, which remain opaque under B5. These are rejected proposals, not
false-positive baseline pairs. `BaseResponse.close -> io.BufferedReader.close`
remains unchanged.

The four metadata rows for filter 584:28 and encoder 1093:28/1073:25/1075:29
are allowed map/filter placement normalizations, not defect corrections.
README ruling 12 permits either site within the same function. The strict
DEBUG branch and Python 2.7 samesite explanation remain separate corrections.
The three other original metadata rows are unchanged, including the hypothesis
resolution record. The earlier seven-row metadata total therefore contains
four normalization rows and three other records; it is not seven defects.

The current judgement file and follow-up evidence supersede the withdrawn
claims above. This supplement uses static source/data and the stored origin
result; it does not add an execution or verification result.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 fresh source-first audit, 2026-11-16

All 1,482 prior pairs retained; 21 false negatives added at 29 source sites.
The sole defect family is omitted BaseRequest.__getattr__ dispatch when a
request descriptor raises AttributeError. Public dictionary inputs can raise
that exception after successful request construction. Per-site witnesses cover
prior evaluation, repeated successful cache lookups and fallback cascades;
no failed object is reused and no client callback becomes a named edge.
The package error-page template contributes one execute-site pair.

Graph: 386 nodes, 1,503 edges (647 inside, 856 outside). Historical trace support
stays 1,014; 489 pairs are from reading only. Ledger entries 1,836, value sites 181,
defaults 46 and rejected trace pairs 14 stay unchanged. No independent metadata
defect was found; revised default prose and counts follow the edge correction.

The complete runtime source was frozen before opening this baseline. The
frozen model was a semantic constraint model, not an independently solved
exact graph. Later source-model interpretation corrections are disclosed in
post-freeze-corrections.json; they are not baseline defects. All 4,768 inventoried
sites, 386 scopes, 1,482 baseline pairs, 46 defaults and zero explicit exclusions were
covered. Source-only reasoning; no target, dependency, test, generated code or
PyCG execution. Root owns the structural/origin verification gate.

Evidence bundle: audits/2026-11-15/pass-4/bottle/.
