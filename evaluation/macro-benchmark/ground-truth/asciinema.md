# asciinema: judgements of the ground truth

Commit `350d5e9` (develop, after v2.0.0; `__init__.py` says 2.0.2).
Analysed source: `asciinema/`, 24 modules, 137 functions (3 lambdas), 35
classes. The package supports Python 3.4 and later: `CHANGELOG.md:37`
explicitly drops 3.3, overriding its stale classifier. `README.md:63` and
`setup.py` impose no upper bound; `setup.py` excludes Python 2.

The ledger is `asciinema.ledger`; the graph `asciinema.json` is generated
from it. `asciinema.rejected.json` holds the 3 rejected trace edges.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) retained all
428 edges, with no confirmed false positive or missing edge. Its source-site
evidence is in asciinema-review.json (audit record `2026-11-15/asciinema-review.json`).
The review corrected the supported-version range to Python 3.4+ and the
FTP-response failure explanation. These are metadata corrections only; the
graph, 347 source-only edges and three trace rejections are unchanged.

## Values, as the ledger uses them

- **env.** `Config`, `get_config_home`, `load` and the commands take an
  `env` mapping. The package default is `os.environ`
  (`config.py:24, 130, 153`; `__main__.py:106`). `os.environ.get` is named
  `collections.abc.Mapping.get`, by the earlier rulings (anytree,
  argcomplete, pypinyin). `os.environ.copy()` is `os._Environ.copy`:
  `_Environ` defines `copy` itself, and no public class of its MRO does.
- **Streams of `open_url`** (`asciicast/__init__.py:36-80`): `sys.stdin`
  or a text file of `open()` (`io.TextIOWrapper`), or, for an http(s) URL,
  an `encodings.utf_8.StreamReader` (the class that
  `codecs.getreader('utf-8')` returns) over the `http.client.HTTPResponse`
  of `urlopen`, over the `gzip.GzipFile` around it, or over the
  `urllib.response.addinfourl` of a redirect to an ftp URL (judgement 11).
- **Asciicast objects.** `open_from_url.__enter__` returns a
  `v2.Asciicast` (through `build_from_header_and_file`) or a
  `v1.Asciicast`. `Player._play`, `CatCommand.execute` call
  `stdout_events` on both.
- **Recording.** `recorder.record` wraps its writer class (`raw.writer` or
  `v2.writer`) in an `async_writer`, and its notifier (from
  `get_notifier`) in an `async_notifier`. It passes these two to its
  `record` parameter, `pty.record` by default.

## Scope rules

- **A.** Every function keeps the edges of its body. `v1.Asciicast.events`,
  `v1.Asciicast.v2_header` and `record_asciicast` have no package caller.
- **B1.** `async_worker` is a plain public class, so it is a receiver of its
  own methods. Its `run` calls `self.perform`, which only `async_notifier`
  defines (`async_worker.py:31`). `Notifier.notify` runs for the three
  notifiers that inherit it; a plain `Notifier` has no `args`
  (`notifier.py:11`).
- **B2.** `pty.record` is public, but the package passes it only the
  `async_writer` and `async_notifier` of `recorder.record`
  (`recorder.py:47-55`). The tests pass a client `FakeStdout`. So
  `writer.write_stdout`, `writer.write_stdin` and `notifier.notify` in
  `pty.record` (`pty.py:25, 51, 80`) have only the `async_writer` and
  `async_notifier` methods. The `raw.writer` and `v2.writer` methods are
  rejected there; they are callees in `async_writer.run`
  (`recorder.py:79, 81`).
- **B5.** A client mapping, stream, adapter or player without a concrete
  parameter contract is opaque. MultipartFormdataEncoder.iter documents
  fields and files as dicts (`urllib_http_adapter.py:26-27`), so their
  items calls follow B4. The tests pass dicts as the `env` of `Config`
  (`tests/config_test.py:19`), so the trace has three `<builtin>.dict.get`
  edges. They are rejected (`asciinema.rejected.json`), as argcomplete
  rejects the `dict.get` of its tests' `os.environ`.
- **C.** Public access paths have no underscore component, except dunder
  names such as `__init__`. Explicit documentation of privacy still applies.
  `asciinema.__main__` is the CLI entry module; its functions have actual
  package calls. Private helpers include `Api._headers`, `Player._play`,
  `URLLibHttpAdapter._parse_headers`, the non-dunder `__` helpers of Config,
  v1.Asciicast and v2.writer, and `commands.record._tmp_path`. Their inputs
  follow actual package calls; an uncalled private function uses the global
  parameter fallback. Local functions and lambdas keep enclosing captures
  and admitted consumer arguments; their lexical names are not public paths.
  For example, Player._play gets the `/dev/tty` file or None, and the pty
  helpers retain the writer/notifier passed to their enclosing record call.

## Judgement calls

1. **Version branch** `__init__.py:6-7`: `raise ImportError(...)` runs only on
   Python 2, which the package does not support. Site `7:22` has no
   callee, with a note. **Lead's ruling: no edge** (Python 3 only).
2. **Optional import** `async_worker.py:1-9`: `multiprocessing` (`Process`,
   `Queue`), else `threading.Thread` and `queue.Queue`. Both sides run
   (README default), so `15:27`, `18:31`, `19:27`, `23:23`, `24:26` and
   `27:23` name both libraries.
3. **The target of `start()`** (`async_worker.py:19:27`): `start()` runs
   `self.run`, a callback as the README's `Thread.start`. The callees are
   `async_writer.run` and `async_worker.run`. With `multiprocessing` the
   target runs in the child process that `start()` forks; the edge holds
   anyway, and the `threading` side gives it in a thread. `Process(...)` at
   `18:31` only stores the target, so the two `run` candidates are rejected
   there.
4. **The signal handler** `pty.record.<lambda1>.<lambda1>` (the trace has
   `_copy -> <lambda1>.<lambda1>`). `_signals` installs it with
   `signal.signal` (`pty.py:85`). The ledger puts the edge at
   `select.select` in `_copy` (`pty.py:99:49`): the loop blocks there; a
   signal interrupts it, and `select` runs the Python handler
   (`PyErr_CheckSignals` on `EINTR`) before it retries (3.5 and later) or
   raises `EINTR` (3.4; caught at `pty.py:100`). This is a callback of
   `select`. A signal that arrives at another point runs the handler in an
   unrelated frame; by analogy with `__del__` (README, "Implicit calls"),
   that is not an edge. Blocking `os.write` calls on the terminal or the
   pty (`pty.py:45, 59`) could also be interrupted; not considered.
   **Lead's ruling: keep**, the edge at `select.select` only. The rule: a
   signal handler that the package installs is a callee of the package
   call where the package waits for the signal while the handler is
   installed (a blocking `select`, `signal.pause`); `signal.signal` only
   stores it, and a signal that arrives anywhere else is not an edge, as a
   `__del__` is not.
5. **Lazy `map`** callbacks. `map(lambda s: ..., [...])` at `pty.py:144:32`
   is iterated by `_signals` (`pty.py:84:29`), which calls
   `pty.record.<lambda1>` (the trace confirms it). `filter(None,
   map(lambda var: ..., ...))` at `commands/record.py:68` is passed as
   `capture_env` and iterated in `recorder.record` (`recorder.py:37:70`),
   which calls `RecordCommand.execute.<lambda1>`. The `map` sites reject
   the lambdas. The two `iter` sites have no candidates, so the skeleton
   does not list them; the ledger has entries for them.
6. **argparse type** `positive_float` (`__main__.py:75, 83, 84`):
   `add_argument` stores it; `parse_args()` (`__main__.py:103:29`) calls it
   on an option string and on a str default (`maybe_str` of a configured
   limit).
7. **`HTMLParser.feed`** (`asciicast/__init__.py:61:24`) calls back
   `Parser.handle_starttag`.
8. **`StreamReader.close`**: `codecs.StreamReader` has no `close`; its
   `__getattr__` returns the `close` of the wrapped stream. So `close()` in
   `v1/v2.open_from_file.__exit__` (`v1.py:60`, `v2.py:56`) calls
   `io.TextIOWrapper.close`, `http.client.HTTPResponse.close`,
   `gzip.GzipFile.close` or `urllib.response.addinfourl.close`
   (judgement 11).
9. **`HTTPError.read()`** (`urllib_http_adapter.py:83:26`): on 3.5 and later,
   `urllib.response.addbase` is a `tempfile._TemporaryFileWrapper`, whose
   `__getattr__` returns its local `func_wrapper` around the response's
   `read`: `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` (named
   where it is defined, as `contextlib.contextmanager.helper`). On 3.4, `addbase.__init__` binds `read` to the response's `read`:
   `http.client.HTTPResponse.read`. The whole-benchmark audit checked the
   pinned historical and current library sources. **Lead's ruling: keep both
   names** (a name that differs between supported versions).
10. **`raw.writer` files** (`raw.py:19, 22`): `open(..., 'wb'/'ab',
    buffering=0)` gives an `io.FileIO`, the package default
    (`async_writer.run` passes no buffering). `raw.writer` is public, and a
    client buffering other than 0 gives an `io.BufferedWriter`. Both are
    callees. `v2.writer` opens in text mode, where every buffering that
    works gives an `io.TextIOWrapper`.
11. **`urlopen` returns `http.client.HTTPResponse`** for the http(s) URLs of
    `open_url` and `post`, **or a `urllib.response.addinfourl`** when the
    server redirects to an ftp URL. First draft: not considered. **Lead's
    ruling (audit A1): add the edges.** The edge rule asks what the code
    can call when it runs; the graph already counts answers that the
    server decides (gzip, the HTML `<link>`). Checked against the standard
    library (3.13 source): `HTTPRedirectHandler.http_error_302` allows the
    schemes http, https and ftp (`urllib/request.py:678`; the check exists
    since 3.2); `FTPHandler`, a default handler, returns
    `addinfourl(fp, headers, req.full_url)` from `ftp_open`; `addinfourl`
    defines `geturl`; `close` is a class attribute of `addinfourl`
    (`tempfile._TemporaryFileWrapper.close` on 3.5+, `addbase.close`
    before), so `StreamReader.__getattr__` returns it. Three edges:
    `open_url -> urllib.response.addinfourl.geturl` (`asciicast/__init__.py:50:30`),
    and `urllib.response.addinfourl.close` in `v1.open_from_file.__exit__`
    (`v1.py:60:24`) and `v2.open_from_file.__exit__` (`v2.py:56:24`). An
    ftp response has no `Content-Encoding`, so the gzip branch adds
    nothing. In `post` (`urllib_http_adapter.py:76-77`) the same redirect
    adds no read edge. Older `addinfourl` responses lack `status`; modern
    ones have it but lack `getheaders`, so `_parse_headers` fails before
    the body read. The explanation changes across versions, not the graph.
12. **`subprocess.run(..., capture_output=True)`** (`notifier.py:11, 64`)
    works from 3.7 onward (3.4 has no `subprocess.run`; 3.5 and 3.6
    reject `capture_output`). Those versions are supported, so the edge stays.
13. **Naming of `tty.tcgetattr` and `tty.tcsetattr`** (`term.py:14, 22`):
    `tty` takes them from `termios` (`from termios import *`) and does not
    export them in `__all__`. The ledger names them `termios.tcgetattr` and
    `termios.tcsetattr`, where they are defined; the tracer accepts no
    `tty.` alias for them. `tty.setraw` is defined in `tty`. **Lead's
    ruling (with audit N1): keep** `termios.*` and
    `collections.abc.Mapping.get`; both precedents go into the README.
14. **Codec objects** are named in `encodings.utf_8`, as the trace names
    the incremental decoder: `encodings.utf_8.StreamReader` and its
    `read`/`readline`, `encodings.utf_8.IncrementalDecoder` and its
    `decode`, and `encodings.utf_8.encode` for the 11 `encoder(...)` value
    sites (`codecs.getencoder('utf-8')`, which is `codecs.utf_8_encode`;
    `codecs` does not export that name).
15. **`os.execvpe`** (`pty.py:135`) runs in the child that `pty.fork()`
    makes; it is an edge of `pty.record`. The trace sees only the parent.
16. **Explicit base `__init__` calls**: `Notifier.__init__(self)`
    (`notifier.py:56`) reaches `object.__init__`, named
    `<builtin>.object.__init__`. `URLLibHttpAdapter()`, `Player()`,
    `NoopNotifier()` and `c()` in `get_notifier` reach `object.__init__`:
    no edge, a note.

## Value sites (20)

| Site | Callees |
|---|---|
| `__main__.py:106:27` `args.cmd(...)` | the `__init__` of the five command classes that `set_defaults` stores |
| `asciicast/__init__.py:59:31, 78:27` `utf8_reader(...)` | `encodings.utf_8.StreamReader` |
| `v2.py:88:67, 89:68` `getincrementaldecoder(...)(...)` | `encodings.utf_8.IncrementalDecoder` |
| `notifier.py:78:22` `c()` | none (`object.__init__`) |
| `pty.py:85:32` `old_handlers.append` | `<builtin>.list.append` (a local list) |
| `recorder.py:49:19` `record(...)` | `pty.record` (the default; nobody passes another) |
| `recorder.py:74:25` `self.writer(...)` | `raw.writer.__init__`, `v2.writer.__init__` |
| `urllib_http_adapter.py`, 11 `encoder(...)` | `encodings.utf_8.encode` |

## Audit and rulings

The blind audit (`asciinema.audit.md`) re-derived 120 sites: 118 agree,
and the 2 differences were naming errors of the auditor (N1). The lead
ruled: judgement 4 (signal handler) keep; judgement 11 (audit A1, the
redirect to ftp) add 3 edges; judgement 9 (names that differ between
versions) keep both names; judgement 1 (Python-2-only branch) no edge;
judgement 13 and N1 (names) keep; all other judgements as written. The
graph went from 425 to 428 edges.

## Trace

84 trace edges: 81 are in the graph, 3 are rejected (B5, above). 37 of
137 functions run. The tests cover `config`, the `v2.writer`, and
`pty.record` in the parent process. `dropped.client_callbacks` is the
test's `FakeStdout.write_stdout`.

## Statistics

| | Count |
|---|---|
| Ledger entries | 518 (475 call, 14 decorator, 12 with, 15 getattr, 2 iter) |
| Callee lines / rejection lines (`reject *`) / exclusions / notes | 559 / 72 (27) / 2 / 95 |
| Default rejections | 0 (no candidate reaches 50 sites) |
| Nodes | 161 |
| Edges | 428: 174 in the package, 254 to 142 callees outside |
| Confirmed by the trace | 81 (18.9%) |
| From reading only | 347 |
| Rejected trace edges | 3 |
| Functions that the tests run | 37 of 137 |

## Third full source audit (2026-11-16)

A fresh independent source-first review retained all 428 edges: 174 inside
the package and 254 outside. It found no confirmed false positive, missed
edge or site metadata correction. It reviewed all 24 runtime modules,
137 functions and lambdas, 1,500 scanner sites, 518 ledger entries,
72 rejection lines and two exclusions. There are no default rejections.
The 982 sites without entries have no additional package callees. The
review checked all 34 zero-edge nodes, including 14 function/lambda bodies.

The pre-comparison model was prose, not an independently enumerated exact
graph. Its timestamped freeze preceded access to the graph and ledger.
The review read the runtime source, tests, README, manual and format docs
as data; it ran no package, dependency, example or test code. Later static
reading of CHANGELOG corrected the model's provisional lower bound to
Python 3.4, consistent with the existing ledger. The original freeze was
retained. Client environment dicts stay opaque under B5; the tests do not
add their outside methods without a concrete parameter contract.

Fresh official CPython source confirmed argparse conversion and HTML
parser callbacks, worker target dispatch, codec lookup and delegation,
HTTP/FTP response paths and supported-version HTTPError read naming.
The graph, ledger and added-edge bytes are unchanged. The three stored
trace rejections remain valid; trace data was used only for origin
accounting after semantic review.


## Fourth full source audit (2026-11-16)

A fresh source-first audit retains all 428 edges (174 in the package and
254 outside), with no confirmed false positive, missing edge or independent
metadata correction. It reviewed all 24 runtime modules, 137 functions/lambdas,
161 bodies, 1,500 source sites, 518 ledger entries and 559 site-target relations.
It also reviewed the 982 omitted sites, 72 rejection lines, two exclusions and
34 zero-edge nodes. There are no default rejections.

The source model and inventories were frozen before reading the baseline.
The required global rules had already exposed their asciinema examples; this
prior exposure is disclosed. One model error was corrected after comparison:
tests that pass client environment dicts do not establish named outside methods
without a concrete B4 contract. The three existing trace rejections remain valid.
The graph, ledger, added edges and rejected-edge bytes remain unchanged.

The release supports CPython 3.4 and later, with no declared upper bound and
no explicit alternative-interpreter support. The changelog's explicit 3.3 drop
overrides the old classifier. Under the round's working normal/-O/-OO union,
removing the five header assertions adds no named target; the source has no
__debug__ or __doc__ reads. Targeted raw standard-library reading confirmed
callback placement, codec delegation, HTTP/FTP cutoffs and HTTPError naming.
No target, dependency, test, example, generated code or PyCG was executed.
Coverage records document the review and do not prove completeness.
