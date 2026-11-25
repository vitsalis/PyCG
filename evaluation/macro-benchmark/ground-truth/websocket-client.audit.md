Status (2026-11-23): done, re-checked against 5d3bb31. F1-F4 are applied as the referee ruled (623 edges). Left: nothing, apart from one wording slip in websocket-client.md J6 (see "Re-check").

# websocket-client: independent audit of the ground truth

Release v1.9.2, commit `12225f5ce6e27536be3b0da85fd763ed75581bcc`. Audited files:
the writer's commit `30981af` (`websocket-client.ledger`, `.json`, `.added.json`,
`.rejected.json`, `.md`). `check.py websocket-client` reports no errors: 598
edges (201 inside, 397 outside); the trace has 380 edges, confirms 353 graph
edges, and 29 trace edges are rejected.

I judged the files by the README's conventions and scope rules (A, B1-B5, C),
its clarifications and its rulings for batch 6. I read the package
source, `setup.py`, the tests, `README.md` and `docs/` as data. I ran nothing
of the package and used no analysis tool.

**Result.** 90 sites re-derived blind: 90 agree. 4 findings. F1 adds 1 edge
if the lead keeps the writer's reading of J5. F2 and F3 change reasons only.
F4 applies the batch 7 ruling on supported platforms (README, commit
`fb7ffd8`) to J6 and adds 24 edges (two selector classes). The graph goes
from 598 to 623 edges, all of them outside the package except F1's.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | missed edge, conditional on J5 (medium) | `_app.py:583:24` `info(f"{e} - reconnect")` and `:591:25` `error(f"{e} - goodbye")`: `run_forever.handleDisconnect -> websocket._abnf.ABNF.__str__` | J5 keeps `str.encode` (`_app.py:661`) because a custom dispatcher can call `closed` with any `ABNF` (its annotation, `_app.py:533`). The same reading admits an `ABNF` of another opcode: `closed` converts only close frames (`:539`), so such an `e` reaches `handleDisconnect` unchanged (`:558`), and the f-string formats it: `format(e, "")` calls `ABNF.__str__`. J5's own text says "the formatted `e` ... is never an `ABNF`", which holds only for the package's own call of `closed` (`:484`). The default rejection of `ABNF.__str__` decides both sites. If the lead rejects J5's custom-dispatcher reading, F1 goes and `:661`/`:663` keep their edges by F2. | +1 | likely |
| F2 | reason only (low) | J5; ledger notes at `_app.py:661:37` and `:663:31` | A second, independent witness for the two edges: the tests assign the public attribute `last_close_frame` (`tests/test_app.py:833`), so by B2 a client may assign an `ABNF` there (annotation `Optional[ABNF]`, `_app.py:171`), and `ABNF.data` is `Optional[Union[str, bytes]]` (`_abnf.py:156`). `ABNF.create_frame("x", OPCODE_CLOSE)` keeps a `str` (`_abnf.py:235`). `teardown` uses it (`_app.py:392-397`) and reaches `_parse_close_frame`. This basis needs no reading of what a custom dispatcher passes. The `bytes(data)` fallback stays by "explicit handling of another type counts". | 0 | likely |
| F3 | wording (low) | J3; ledger header lines 8-9; notes at `_socket.py:124:27`, `:141:49`, `_dispatcher.py:117:24` | The client's pre-initialised socket is not opaque: `WebSocketApp.__init__` annotates it `Optional[socket.socket]` (`_app.py:76`), and `WebSocket.connect` documents the `socket` option as "socket: Pre-initialized stream socket" (`_core.py:275-276`). B4 names it `socket.socket`. No edge changes: every site that this socket reaches already names `socket.socket`, and `socket.socket` has no `pending`, so `SSLDispatcher.select` (`_dispatcher.py:117`) raises `AttributeError` there before any call. The note at `_socket.py:141` ("a client's socket can return None") then has no witness, but `:143` gives the same callee. | 0 | certain |

## Step 1: blind re-derivation

**Sample.** Skeleton without the ledger, in `$TMPDIR/b7-audit-websocket-client/`
(a copy of `projects.toml` and of the source): 940 sites, 758 explicit (755
call, 3 decorator) and 182 implicit; 20 value sites. Explicit sites are 81% of
the skeleton, so I drew by kind, as tinytag's audit did: sites numbered in
(line, column) order module by module, `rng = random.Random(20261123)`,
`rng.sample(explicit, 50)`, then `rng.sample(implicit, 20)`, plus the 20 value
sites (none was in the draw): 90 sites. I wrote my callees in
`$TMPDIR/b7-audit-websocket-client/blind.md` (file time 00:00:13) before I
opened any writer file (`draw.py` and `sample.json` beside it).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call) | 50 | 50 | 0 |
| Implicit (9 format, 6 iter, 5 op) | 20 | 20 | 0 |
| Value sites | 20 | 20 | 0 |
| **Total** | **90** | **90** | **0** |

All 20 implicit sites have no package callee; the ledger leaves them to the
three default rejections, which decide them correctly. Among the value sites:
`os.urandom` at `_abnf.py:272`; `WebSocket._recv` at `_abnf.py:420`;
`run_forever.initialize_socket`, `.read`, `.check` at the dispatcher callbacks
(`_dispatcher.py:54, 81, 83, 107, 109`); `WrappedDispatcher.timeout` at `:155`
and `:165`; no callee at the client callbacks (`_app.py:420, 685, 692`;
`_dispatcher.py:46, 162`); `socket.socket.recv` and `ssl.SSLSocket.recv` at
the three `sock.recv` sites.

## Step 2: exhaustive checks

**Every ledger entry.** I read all 2118 lines against the source. Apart from
F1-F3, every callee, rejection, exclusion and note is right.

**Dispatch sets (B1).** No package class has a package subclass except the
dispatchers and the `_wsdump` consoles.
- `WebSocket`: no subclass; `self.*` sites name `WebSocket` methods only.
  `create_connection`'s `class_` (`Type[WebSocket]`, default `WebSocket`) gives
  `WebSocket.__init__` only.
- Dispatchers: `Dispatcher` and `SSLDispatcher` inherit `DispatcherBase`'s
  `__init__`, `timeout`, `reconnect`, `send`; `WrappedDispatcher` is separate.
  `run_forever` rebinds its local `dispatcher` at `_app.py:596` before
  `initialize_socket` first runs, so `dispatcher.read` (`:451`) has all three
  `read`s, `:607` only `DispatcherBase.reconnect`, `:589` only
  `WrappedDispatcher.reconnect`, and `WebSocket._send` (`_core.py:638`)
  `DispatcherBase.send` and `WrappedDispatcher.send`. A package dispatcher
  cannot be the inner dispatcher of a `WrappedDispatcher`
  (`dispatcher.signal` at `_dispatcher.py:145`), so `DispatcherBase.timeout`
  has no package caller: right.
- `console` in `_wsdump.main`: `NonInteractive` or `InteractiveConsole`;
  `raw_input` resolves to `RawInput.raw_input` in both MROs.
- Locks: only `WebSocket.lock` and `readlock` can be a `NoLock`.

**Callback roles.** `on_*`, `header`, `get_mask_key`, client `recv_fn`: client
callables (bare `Callable` or no package value in code, tests or docs). The
documented custom dispatcher is the module `rel` (`README.md:120`), a value
from outside the package that the client passes: client (B2, last sentence),
so nothing that it calls back is an edge. Library call-backs:
`Thread.start` -> `_send_ping` and `main.recv_ws`; `parse_args` ->
`VAction.__call__`. `add_argument` builds `VAction` with
`argparse.Action.__init__` (no edge): right.

**Default rejections.** I listed every site of the four defaults
(`--report --default`). `WebSocket.__iter__`/`__next__` (97 sites each): no
package site iterates a `WebSocket`. `SimpleCookieJar.get` (54): every
receiver is a dict, `os.environ`, a `Morsel` or `ABNF.OPCODE_MAP`.
`ABNF.__str__` (84): right at every site except the two of F1.

**Functions that no site calls** (41 nodes, 15 of them modules): client API
(`WebSocketApp` methods, `WebSocket.abort`, `fileno`, `is_ssl`, `next`,
`send_*`, `set_mask_key`, the four property getters, `set_reconnect`,
`setdefaulttimeout`, `isEnabledForDebug`, `SimpleCookieJar.set`),
`WebSocket.__iter__`, `DispatcherBase.timeout`, and
`_logging.NullHandler.emit` (never defined, J2). No package code loads
`timeout`, `status`, `headers` or `subprotocol` on a `WebSocket`. Right.

**Special methods and properties.** `ABNF.__str__` only through the explicit
`frame.__str__()` calls (and F1). `NoLock.__enter__`/`__exit__` at the two
`with` of `WebSocket`. The four `property(...)` calls (`_core.py:187-226`)
only store accessors. No package class defines `__bool__`, `__len__`,
`__eq__`, `__hash__`, `__contains__` or `__getattr__`.

**Binding check.** Every call of a package function binds, including
`handshake(self.sock, url, *addrs, **options)` (`addrs` is the 3-tuple of
`_http.connect`), `class_(..., **options)` (`WebSocket.__init__` has `**_`),
`self.timeout(seconds, reconnector, True)` (`*args`), and
`reconnector(reconnecting=True)`. No call fails to bind.

**Callees outside the package: every name** (150 distinct names) against the
micro-benchmark's naming rules. All follow them:
- builtins and builtin-type methods (`<builtin>.int.from_bytes`,
  `<builtin>.bytes.join`, ...); package exceptions without `__init__` give
  `<builtin>.Exception.__init__` (31 callers), also for the fallback classes
  of `_http.py:48`; builtin class calls give the class (`<builtin>.ValueError`).
- module functions by the imported path: `base64.encodebytes` (imported as
  `base64encode`), `urllib.parse.urlparse`/`unquote`, `os.path.isfile`/`isdir`,
  `os.urandom`, `hmac.compare_digest`, `hashlib.sha1`, `inspect.stack`,
  `socket.getaddrinfo`, `struct.*`, `time.*`, `zlib`/`gzip.decompress`,
  `logging.getLogger`, `ipaddress.ip_address`/`ip_network`.
- class calls by class path: `threading.Lock`/`Event`/`Thread`, `socket.socket`,
  `ssl.SSLContext`, `array.array`, `http.cookies.SimpleCookie`,
  `argparse.ArgumentParser`, `logging.NullHandler`/`StreamHandler`,
  `selectors.DefaultSelector` (a direct alias of a class, "Outside names");
  `code.InteractiveConsole.__init__` for the inherited `__init__`.
- methods by the receiver's class, also when inherited:
  `http.cookies.Morsel.get` (a dict subclass), `http.cookies.SimpleCookie.items`,
  `.update`, `.values`, `logging.Logger.*`, `threading.Thread.*`,
  `threading.Event.*`, `ssl.SSLContext.*`, `socket.socket.*`,
  `ssl.SSLSocket.*` (`recv`, `send`, `shutdown`, `pending` defined there;
  `settimeout`, `gettimeout`, `fileno`, `close` inherited),
  `ipaddress.IPv4Network.subnet_of`/`IPv6Network.subnet_of`,
  `argparse.ArgumentParser.add_argument`, `io.TextIOWrapper.write`/`flush`
  (the default `sys.stdout`), `collections.abc.Mapping.get` (`os.environ`,
  anytree precedent), the concrete selector classes (J6; two are missing, F4).
- `_hashlib.HASH.digest` and `_sha1.sha1.digest`: hashlib's documented
  fallback, as in path's ledger (`path.ledger:1004-1006`). I could not check
  the builtin type's name: the CPython trees under `deps/_cpython/` hold no
  `sha1module.c`. The name rests on path's precedent.
- missing modules by access path: `wsaccel.xormask.XorMaskerSimple`, `.process`,
  `wsaccel.utf8validator.Utf8Validator`, `.validate`,
  `python_socks._errors.ProxyError`, `python_socks.sync.Proxy.create`,
  `python_socks.sync.Proxy.create.connect`. The proxy socket reaches
  `WebSocket.sock` through tuple unpacking (`_core.py:279`), so it has no
  stub path there ("Missing libraries"): right.

**Rejected trace edges (29).** 28 edges to `unittest.mock.CallableMixin.__call__`:
the tests' mocks (passed in, or patched over package internals and library
functions); none is a package or library edge. `SimpleCookieJar.set ->
<builtin>.dict.get`: the tracer names `Morsel.get` by its defining class; the
graph has `http.cookies.Morsel.get` at `_cookiejar.py:47`. Right (rule A,
naming artefact). The reason "a client object, opaque under B5" fits the mocks
passed in; for a mock patched over a library function the reason is that a
test's change of internals is not considered. Same outcome.

## The writer's judgement calls

| Call | Opinion |
|---|---|
| J1 optional imports | Supported: "Judgements" (both sides of an optional import run), missing-module names, dagster-pipes judgement 5 for `ws_proxy`. |
| J2 `NullHandler` fallback | Supported: a branch that only an unsupported version takes does not run (netaddr `strategy/__init__.py:242`). |
| J3 socket names | Supported, with F3's wording: the client's socket is `socket.socket` by B4, not opaque. `_http.py:171` closes only a `socket.socket`: `wrap_socket` closes its own socket when the handshake fails, and an asynchronous `KeyboardInterrupt` between the last assignment and `return` is not considered (as the Sublist3r signal ruling treats signals that arrive anywhere). |
| J4 `WebSocketApp.sock` | Supported: the tests' mocks are client objects. |
| J5 closed and custom dispatchers | The README does not decide whether a package closure that the package hands to client code (`closed`, as `handleDisconnect`) takes the values its annotation admits. The smaller extension: yes, as for a public parameter (B2: the annotation decides), since the client calls it. Then F1 follows. The two `_parse_close_frame` edges hold either way (F2). |
| J6 selector classes | Decided by the batch 7 ruling on supported platforms: F4 (+24 edges, `DevpollSelector` and `PollSelector`). |
| J7 raises after a thread race | Supported by ruling (c) after Codex round 1 ("no restriction ... to one thread") and ruling (d) (a public method that changes state is not a change of internals): `frame_buffer` and `clear()` are public. I found no single-thread witness: `recv_header`, `recv_length` and `recv_mask` set their fields after the client's `recv_fn` returns. 1 edge (`frame_buffer.recv_frame -> <builtin>.Exception.__init__`, `_abnf.py:379, 394, 398`). |
| J8 `NoLock`, consoles | Supported: the tabulate ruling on an inherited `__init__`. |
| J9 callbacks | Supported (B2, B5, callback rule). |
| J10 outside receivers | Supported (bottle and path precedents for hashlib; the receiver-class rule). |

## F4: J6 under "What makes a platform supported" (batch 7 ruling, fb7ffd8)

This section replaces my earlier R1 ("needs a ruling"). The new ruling decides
it.

**What websocket-client 1.9.2 declares or establishes.**
- Classifiers (`setup.py:53-55`): `Operating System :: MacOS :: MacOS X`,
  `Operating System :: POSIX`, `Operating System :: Microsoft :: Windows`.
  It uses no POSIX child classifier (`POSIX :: Linux`, `:: BSD`,
  `:: SunOS/Solaris`, `:: AIX`).
- Documentation: `README.md` and `docs/source/*.rst` say nothing about
  platforms (I searched for windows, linux, macos, posix, bsd, solaris, aix,
  platform, operating system). `ChangeLog` mentions old Windows fixes (#370,
  #427, #573). That history is consistent with the Windows classifier and
  adds no platform.
- Platform test jobs: `build.yml:16` runs `os: [ubuntu-latest]` only;
  `codecoverage.yml:7`, `doctest.yml:7` and `lint.yml:7` run on
  `ubuntu-latest`. So CI establishes Linux.
- No explicit restriction or support drop.

**Which selector classes follow.** `selectors.DefaultSelector` takes the first
of kqueue, epoll, devpoll and poll that the platform has, and select otherwise
(CPython 3.11.9 `Lib/selectors.py:612-621`):
- Linux (CI, and within POSIX): `EpollSelector`. In the ledger.
- macOS (classifier): `KqueueSelector`. In the ledger. The BSDs are within
  POSIX and also give `KqueueSelector`: no further name.
- Windows (classifier): `SelectSelector`. In the ledger.
- Other POSIX systems: `DevpollSelector` on Solaris and illumos, and
  `PollSelector` on a POSIX system with none of the three event APIs (AIX,
  for example). **Not in the ledger.**

The ruling admits "those the release declares through classifiers". The
pyfiglet application reads a family classifier (`Operating System :: Unix`)
as covering its family and excluding what lies outside it (Windows). By the
same reading, `Operating System :: POSIX` declares the POSIX systems, and
Solaris, illumos and AIX are POSIX systems. The ruling has no requirement
that a member of the declared family be named. The path ruling still applies:
only combinations on which CPython 3.10-3.14 exists count. That CPython runs
on Solaris or illumos and on AIX in those versions is my general knowledge.
The sources of the audit records do not show it: they hold no `selectmodule.c`, which
would show where `select.devpoll` exists.

**Edge change: +24 (missed edges, medium, likely).** `DevpollSelector` and
`PollSelector` each for 12 caller-method pairs:

| Caller | Methods | Sites |
|---|---|---|
| `_dispatcher.Dispatcher.read` | `register`, `select`, `close` | `_dispatcher.py:77`, `80`, `85` |
| `_dispatcher.SSLDispatcher.read` | `register`, `close` | `:103`, `:111` |
| `_dispatcher.SSLDispatcher.select` | `select` | `:122` |
| `_socket.recv._recv` | `register`, `select`, `close` | `_socket.py:111`, `113`, `114` |
| `_socket.send._send` | `register`, `select`, `close` | `:180`, `:182`, `:183` |

The names are `selectors.DevpollSelector.register`, `.select`, `.close` and
`selectors.PollSelector.register`, `.select`, `.close`: public classes of
`selectors`, named by the receiver's class: both inherit `register` and
`select` from `_PollLikeSelector`; `DevpollSelector` defines `close`, and
`PollSelector` inherits it from `_BaseSelectorImpl`
(`Lib/selectors.py:433`, `490-500`, 3.11.9). The constructor stays
`selectors.DefaultSelector`. J6's note should then name five classes and drop
its open question.

**The reading that gives 0 edges.** If the lead holds that a family
classifier declares only the members that the release names or tests, the
supported POSIX systems are Linux (CI) and macOS (classifier). The ledger is
then complete and F4 changes nothing. I do not take this reading. The ruling
says "declares through classifiers", and the release's only POSIX declaration
is the family itself. This reading would also leave the BSDs without
support, although the outcome for them is the same.

**The second ruling of the section** (a private class that a public module
re-exports is named by its defining module, `_io._WindowsConsoleIO`). It
changes nothing here. On Windows, `_wsdump` calls only `write` and `flush` on
the default `sys.stdout`, which is an `io.TextIOWrapper` there too; no raw
console stream method is called. The other private classes in the graph are
already named by their defining module (`_hashlib.HASH`, `_sha1.sha1`).

## Notes on the README and the tools

- `check.py --report <name> --default <candidate>` prints the whole report and
  then the default's sites, not the default's sites alone. That works, but the
  README's wording suggests a short listing.
- The CPython sources of the audit records hold no `sha1module.c` and no
  `selectmodule.c`, so the `_sha1` type name and the platforms of `devpoll`
  cannot be checked there.

## Re-check (2026-11-23, against `5d3bb31`)

**Verdict: the findings are applied as ruled, and nothing else changed.** I
diffed `30981af..HEAD` for the websocket-client files; `check.py
websocket-client` reports no errors and 623 edges (202 inside, 421 outside;
the trace confirms 353, 29 rejected).

- **F1.** The ledger has new entries `_app.py 583:24 format {e}` and
  `591:25 format {e}`, each `-> websocket._abnf.ABNF.__str__`, with notes that
  cite the ruling. The default rejection of `ABNF.__str__` now names these
  two sites as exceptions. The graph gains the one inside edge
  `run_forever.handleDisconnect -> ABNF.__str__`.
- **F4.** `selectors.DevpollSelector.*` and `selectors.PollSelector.*` were
  added at exactly the twelve sites of the table:
  `_dispatcher.py` 77, 80, 85, 103, 111 and 122, and `_socket.py` 111, 113,
  114, 180, 182 and 183. Each site gets the method of its call. The
  `DefaultSelector` note at `_dispatcher.py:76` now names the five classes.
  The graph gains 24 outside edges in the five callers: 6, 4, 2, 6 and 6
  names.
- **F2 and F3.** The wording is applied at the ledger header and the notes at
  `_app.py:661` and `663`, `_core.py:146`, `_dispatcher.py:117`, and
  `_socket.py:124` and `141`. It is also applied in J3 and J5 of the
  judgements file.
- **No other change.** The graph diff holds only these 25 edges, and the
  ledger diff only the lines above. J6 and J7 in `websocket-client.md` are
  updated with the referee's text. One slip, wording only: J6 cites the
  classifiers as `setup.py:39`; they are at `setup.py:53-55` (line 39 is
  `python_requires`).

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-websocket-client-sha1` (3943dc8, PR #112) against
`main` (2130a69): one outside edge renamed in `websocket-client.json`,
`websocket-client.added.json`, `websocket-client.ledger` and
`websocket-client.md`; `evaluation/metrics.json` is not recorded yet. I
read `websocket/` and `setup.py` from the inputs image and CPython 3.10.22
to 3.15.2 from the dependency sources, as text. Nothing ran; no PyCG
output was read.

| Site | Change | Verdict | Evidence |
|---|---|---|---|
| `_handshake.py:215:53` `hashlib.sha1(value).digest()` (`_handshake._validate`) | `_sha1.sha1.digest` renamed `_sha1.SHA1Type.digest` | agree | websocket-client admits CPython 3.10 and later only (`setup.py:39`, classifiers `:47-52`; `websocket-client.md`, the opening section); hashlib's fallback is the factory `_sha1.sha1`, whose type `_sha1` exports as `SHA1Type` on 3.10.22 `sha1module.c:568-570` through 3.15.2 `:353` (all checked for bottle); `hashlib.sha1` is a factory, so no public class alias applies (ruling-names-2) |
| the same | `_hashlib.HASH.digest` kept | agree | `_hashlib` exports `HASH` (`PyModule_AddType`) |

Nothing missed: `_handshake.py:215` is the package's only hash object; its
locks (`_core.py:124-125`, `_abnf.py:320`, `_app.py:170`) are used only in
`with` statements, implicit sites; no other outside callee of the graph
falls under the two rulings. Counts: 648 edges (202 inside, 446 outside),
unchanged in number, 353 traced: as `check.py websocket-client` reports,
which passes with the source in place, as do `--origin` and `--report`.

**Verdict.** Closed: the rename stands, and nothing is missed. No
finding.
