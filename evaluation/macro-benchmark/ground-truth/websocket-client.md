# websocket-client: judgements of the ground truth

Release v1.9.2 (commit `12225f5`). Analysed source: `websocket/` without
`websocket/tests/`: 15 modules, 153 functions, 35 classes. `setup.py`
sets `python_requires=">=3.10"`; the classifiers name CPython 3.10 to 3.14
and macOS, POSIX and Windows. No other interpreter is declared, so only
CPython is in scope. `install_requires` is empty; the extra `optional`
names python-socks and wsaccel, which are not installed (missing modules).
Standard `-O`/`-OO` execution is included; the package has no `assert`
that guards a call except `assert dispatcher is not None` (`_app.py:450`,
`:588`), which holds on every path.

The ledger is `websocket-client.ledger`; the graph `websocket-client.json`
is generated from it. The 29 rejected trace edges are in
`websocket-client.rejected.json` (28 calls of `unittest.mock` objects that
the tests pass in, 1 naming artefact; see "Trace").

## Status (for a resumed session)

- Pass 1 (every site of every module decided): done 2026-11-22.
  `check.py --write websocket-client` reports no error.
- Pass 2 (review): done 2026-11-22: the value sites, the sites with
  callees beyond names, the implicit sites without candidates, the
  documented examples (`docs/source/*.rst`, `README.md`) and a binding
  check of every call of a package function (all bind). No change.
- Audit and ruling applied 2026-11-23: the blind audit
  (`websocket-client.audit.md`, F1 to F4) and the referee's ruling
  (`b7-ruling-websocket-client.md` in the audit records), adopted by the
  lead: F1 (J5, +1 inside edge at two sites), F2 and F3 (reasons only), F4
  (J6, +24 outside edges); J7 confirmed. 623 edges (202 inside, 421
  outside).
- Codex audit round 1 applied 2026-11-23 (see "Codex round 1"): 18 of
  its 19 missing outside pairs, the unsure `pending` pair, and the three
  metadata items; the disputed pair was added by the referee's ruling,
  which adds five more pairs of the same pattern (648 edges: 202 inside,
  446 outside).

## Architecture, as the ledger uses it

- `WebSocket` (`_core.py`) holds `sock` (the socket), `sock_opt`
  (`_socket.sock_opt`), `frame_buffer` and `cont_frame` (`_abnf.py`),
  `lock` and `readlock` (a `threading.Lock`, or a `NoLock` when
  `enable_multithread` is false), and `dispatcher`.
- `WebSocketApp` (`_app.py`) holds `sock`, a `WebSocket` made in
  `run_forever.initialize_socket`. `run_forever` rebinds its local
  `dispatcher` to what `create_dispatcher` returns (a `WrappedDispatcher`
  around the client's custom dispatcher, an `SSLDispatcher` for `wss`, or
  a `Dispatcher`) before `initialize_socket` first runs, so the
  `WebSocket`'s dispatcher and the `dispatcher.read` call see those three.
- The dispatcher classes (`_dispatcher.py`) are private: no public path
  reaches them. `DispatcherBase` is never instantiated; `Dispatcher` and
  `SSLDispatcher` inherit its `__init__`, `timeout`, `reconnect` and `send`.
- `handshake_response` objects and `sock_opt` objects keep plain instance
  attributes (`status`, `headers`, `subprotocol`, `timeout`): no
  `WebSocket` property runs on them.

## Judgements

**J1. Optional imports of wsaccel and python-socks** (`_abnf.py:30-51`,
`_utils.py:32-437`, `_http.py:39-58`). Both sides run (README,
"Judgements"). wsaccel and python-socks are not installed, so their calls
use missing-module names: `wsaccel.xormask.XorMaskerSimple`,
`….XorMaskerSimple.process`, `wsaccel.utf8validator.Utf8Validator`,
`….Utf8Validator.validate`, `python_socks._errors.ProxyError` (beside the
fallback class's `Exception.__init__`, `_http.py:78`),
`python_socks.sync.Proxy.create` and `python_socks.sync.Proxy.create.connect`
(the variable `ws_proxy` keeps the access path of the call that made it, as
`spark.conf.get` in dagster-pipes judgement 5). The two definitions of
`_mask` and of `_validate_utf8` are one node each.

**J2. `logging.NullHandler` fallback** (`_logging.py:24-30`). The
`except ImportError` branch is not an optional dependency: `logging` has
`NullHandler` on every supported version, so only an unsupported version
takes the branch, and `NullHandler()` at `_logging.py:33` is
`logging.NullHandler`. The fallback class's `emit` is `pass` and has no
edges either way.

**J3. Which sockets have names.** The package makes two kinds of socket:
`socket.socket` (`_http._open_socket`, `_http.py:216`) and `ssl.SSLSocket`
(`ssl.SSLContext.wrap_socket`, `_http.py:338`, with the package's own
context or the client's documented `ssl.SSLContext`, `docs/source/faq.rst:207`).
Methods on `WebSocket.sock` and on the `sock` parameters of
`_socket.recv`/`send` (annotated `socket.socket`, B4) are named for both
classes. The client's pre-initialised socket (the `socket` option of
`connect`, documented as "Pre-initialized stream socket", `_core.py:275`;
`WebSocketApp(socket=...)`, annotated `Optional[socket.socket]`,
`_app.py:76`) is a `socket.socket` by B4 (audit F3); every site it reaches
already names `socket.socket`, so no edge changes. Other notes:
- the socket that python-socks returns (`_http.py:125`) is the stub value
  `python_socks.sync.Proxy.create.connect`. For a `ws` url it travels
  unchanged in package-created tuples (`_http.py:133`, `143`) to
  `WebSocket.sock` (`_core.py:279`, `298`): a missing-module value keeps
  its access path when package code forwards it (README, "Rulings for
  batch 7"; Codex round 1). Every call on `WebSocket.sock` and on the
  `sock` of `_socket.recv`/`send` therefore also names
  `python_socks.sync.Proxy.create.connect.<method>`. A SOCKS `wss`
  connection is wrapped in an `ssl.SSLSocket` (`_http.py:129`).
- `SSLDispatcher.select` (`_dispatcher.py:117`) calls `sock.pending()`
  on `ssl.SSLSocket` and on the python-socks stub: `create_dispatcher`
  chooses the dispatcher from the original url (`_app.py:596-597`), and a
  `wss` url that redirects to a `ws` url (`_core.py:290-309`) reconnects
  through SOCKS without TLS, so the `SSLDispatcher` sees the stub, whose
  attribute call is named by its path
  (`python_socks.sync.Proxy.create.connect.pending`; Codex round 1, the
  unsure case). A plain `socket.socket` (the client's pre-initialised one,
  or a redirect to `ws` without SOCKS) has no `pending`: the call raises
  `AttributeError` before any callee.
- The package's sockets never return `None` from `recv`; the raise at
  `_socket.py:141` is reached by an admitted client subclass of
  `socket.socket` whose `recv` returns `None` (B5 clarification).
- `_http.connect`'s `except` (`_http.py:171`) closes a `socket.socket`
  only: the `SSLSocket` is assigned by the last statement that can raise.

**J4. `WebSocketApp.sock`** is the `WebSocket` of `initialize_socket`
(`_app.py:408`) or `None`. The tests assign mock objects to it; a test's
mock is a client object and adds no callee.

**J5. Custom dispatchers and `closed`** (`_app.py:525-558`,
`_dispatcher.py:129-165`; audit F1 and F2; the referee's ruling, adopted
by the lead). The client's custom dispatcher is a client object. The
documented one is the module `rel` (`README.md:120`,
`docs/source/examples.rst:740`, `:779`), a third-party library that is not
installed; a value from outside the package that the client passes is a
client value whatever the documentation shows (B2), and the tests pass
mocks or their own classes. So `signal`, `read`, `buffwrite` and `timeout`
on it have no callee. A package dispatcher cannot be the inner dispatcher
of a `WrappedDispatcher`: `WrappedDispatcher.__init__` calls
`dispatcher.signal` first, which no package dispatcher has.

The ruling: "When the package hands a package callable to client code
through a supported callback interface, judge its parameters as public
inputs under B2 to B4; its captured values remain constrained by package
flows and admitted public state. The client's invocation creates no
callback edge at the handoff site under B5." `WrappedDispatcher.send`
hands `closed` (as `handleDisconnect`), `_socket.send` and the `read`
callback to the client's dispatcher; the handoff sites
(`_dispatcher.py:153`, `158`, `162`) gain no edges. `closed`'s parameter
`e` takes the values of its annotation, which names `ABNF`:
- an `ABNF` whose opcode is not CLOSE (`ABNF(opcode=ABNF.OPCODE_TEXT,
  data=b"x")`) passes the conversion at `_app.py:539` unchanged and
  reaches `handleDisconnect` (`:558`), whose f-strings format it: edge
  `run_forever.handleDisconnect -> ABNF.__str__` at `_app.py:583:24` and
  `591:25` (audit F1; the two entries override the default rejection of
  `ABNF.__str__`);
- a close frame with `str` data (the annotation of `ABNF.data`) reaches
  `_parse_close_frame`, which keeps `str.encode` (`_app.py:661`); the
  explicit fallback `bytes(data)` (`_app.py:663`) stays by "explicit
  handling of another type counts". F2 gives an independent witness for
  both: the tests assign the public `last_close_frame` (annotated
  `Optional[ABNF]`, `_app.py:171`; `tests/test_app.py:833`), and
  `teardown` forwards it to `_get_close_args` (`_app.py:392-397`).
`read` and `check` take no input; `initialize_socket`'s `reconnecting`
admits both Booleans, which the package's calls already cover;
`handleDisconnect` and `teardown` are not handed to the client.

**J6. `selectors.DefaultSelector`** (`_dispatcher.py:76`, `102`;
`_socket.py:110`, `179`; audit F4; the referee's ruling, adopted by the
lead). The constructor is named by the direct alias
`selectors.DefaultSelector`. The ruling: "A declared platform family
admits its members on which an admitted interpreter and Python version
exist, subject to the release's explicit restrictions; neither a narrower
CI matrix nor the interpreter's support-tier list narrows that
declaration." The release declares macOS, POSIX and Windows
(`setup.py:53-55`), and `selectors.py` picks the first usable of kqueue,
epoll, devpoll, poll and select. So the instances are named by five
classes, for `register`, `select` and `close` at the twelve method sites:
`selectors.KqueueSelector` (macOS), `selectors.EpollSelector` (Linux),
`selectors.DevpollSelector` (Solaris), `selectors.PollSelector` (AIX) and
`selectors.SelectSelector` (Windows).

**J7. Unreachable raises.** `continuous_frame.extract` raises at
`_abnf.py:483` only if `data is None`, which line 470 already excluded
(a local variable): no edge. The checks at `_abnf.py:378-398`
(`header`, `length`, `mask_value` still `None` after the `recv_*` calls)
are kept: `frame_buffer` is public (`websocket.frame_buffer`), and a
client thread can call its public `clear()` while `recv_frame` runs (the
lock is not taken by `clear`), so the raises can happen ("no restriction
to one thread"). The referee confirmed J7 as written.

**J8. `NoLock`** defines no `__init__`: `NoLock()` (`_core.py:127`, `128`)
and `NonInteractive()` (`_wsdump.py:147`) have no constructor edge.
`InteractiveConsole()` (`_wsdump.py:149`) is
`code.InteractiveConsole.__init__`. The `with self.lock` and
`with self.readlock` of `WebSocket` reach `NoLock.__enter__` and
`__exit__`; the locks of `frame_buffer` and `WebSocketApp` are always
`threading.Lock`.

**J9. Callbacks.** `WebSocketApp`'s `on_*` callbacks and `header`
callable, `WebSocket`'s `get_mask_key`, and `frame_buffer`'s `recv_fn`
from a client are client callbacks. The package's own values: `os.urandom`
as `ABNF.get_mask_key`; `WebSocket._recv` as `recv_fn`;
`run_forever.read` and `check` as the read and check callbacks of
`Dispatcher.read` and `SSLDispatcher.read`; `initialize_socket` as the
reconnector of `DispatcherBase.reconnect`. `DispatcherBase.timeout` is
never called by the package, so its `callback` is judged as for a public
parameter: a bare `Callable`, no package value. `Thread.start` runs
`WebSocketApp._send_ping` (`_app.py:221`) and `_wsdump.main.recv_ws`
(`_wsdump.py:208`); `argparse.ArgumentParser.parse_args` calls
`VAction.__call__` back (`_wsdump.py:96`).

**J10. Names of outside receivers.** `http.cookies.SimpleCookie` methods
by that class; its values are `http.cookies.Morsel` (`Morsel.get`, a
dict method, named by the receiver's class); `os.environ.get` is
`collections.abc.Mapping.get`; `hashlib.sha1(...).digest()` is
`_hashlib.HASH.digest` and, by hashlib's documented fallback,
`_sha1.sha1.digest`; `ipaddress.ip_network` results are `IPv4Network` or
`IPv6Network` (`subnet_of` for both).

## Default rejections

- `WebSocket.__iter__`, `WebSocket.__next__`: no package site iterates a
  `WebSocket`; `WebSocket.next` accepts `__next__` explicitly.
- `ABNF.__str__`: no other format, `%` or `str()` site converts a frame;
  the two explicit `frame.__str__()` calls and the two f-strings of
  `run_forever.handleDisconnect` (`_app.py:583:24`, `591:25`, J5) accept it.
- `SimpleCookieJar.get`: only `CookieJar.get(host)` (`_handshake.py:139`)
  has a jar receiver, and it accepts it.

## Trace

The tests ran without network and without the echo server: 195 passed, 26
skipped. 127 of 153 functions ran. Rejected trace edges (29):

- 28 edges to `unittest.mock.CallableMixin.__call__`: the tests pass mock
  sockets, dispatchers, selectors and patched functions; a test's mock is a
  client object (B5).
- `SimpleCookieJar.set -> <builtin>.dict.get`: the tracer names the
  `Morsel.get` of `_cookiejar.py:47` by its defining class; the graph has
  `http.cookies.Morsel.get` there (naming artefact).

## Codex round 1

Report: `audit-b7-r1/websocket-client.md` in the audit records.

Applied:
- 17 pairs `python_socks.sync.Proxy.create.connect.*` (`fileno`,
  `settimeout`, `close`, `gettimeout`, `shutdown`, `recv`, `send`) at the
  `_core.py` and `_socket.py` sites of the report (J3 rewritten).
- `run_forever.read -> wsaccel.xormask.XorMaskerSimple.process.decode`
  at `_app.py:496:39`: `_mask` returns the stub result (`_abnf.py:38`),
  and `ABNF.mask`, `frame_buffer.recv_frame`, `continuous_frame.add` (a
  package list, `_abnf.py:460`) and `extract` (`:473`) forward it
  unchanged to `frame.data`, which `read` decodes with no type test.
- The unsure pair `SSLDispatcher.select ->
  python_socks.sync.Proxy.create.connect.pending` (`_dispatcher.py:117:24`):
  accepted (J3: wss-to-ws redirect through SOCKS).
- Metadata: the default-rejection paragraph above; the witness of
  `_socket.py:141` (a client `socket.socket` subclass); `_abnf.py:250:29`
  has no callee (`len` returns at most `sys.maxsize` = 2**63 - 1, so
  `length >= 2**63` never holds; `ABNF.format -> <builtin>.ValueError`
  stays through `:245` and `:247`).

Ruled (the referee, `b7-ruling-round1-disputes.md` case 1, adopted by the
lead): "For macro-benchmark edges, an otherwise unknown missing-library
result may take either outcome of a concrete-type `isinstance` test; on
the successful branch, B4 supplies the concrete type's method name without
erasing the result's retained missing-module access path." So
`WebSocket.recv -> wsaccel.xormask.XorMaskerSimple.process.decode` is added
at `_core.py:433:44`, beside `<builtin>.bytes.decode`. The same pattern
adds five more outside pairs, where the stub result of `_mask` reaches a
`str` test:
- `WebSocket.pong -> ….process.encode` at `_core.py:417:37` (the data of
  a received ping frame, `_core.py:498`, `_wsdump.py:163`);
- `ABNF.mask -> ….process.encode` and `-> ….process.encode.encode` at
  `_abnf.py:302:31` (pong forwards the payload through `send`,
  `create_frame`, `format` and `_get_masked`, unchanged or as the stub
  result of its own `.encode`);
- `WebSocketApp._parse_close_frame -> ….process.encode` at
  `_app.py:661:37` (a received masked close frame, through `closed`);
- `_utils.validate_utf8 -> ….process.encode` at `_utils.py:447:35`
  (`continuous_frame.extract`, `_abnf.py:479`).
No python-socks value meets a concrete-type `isinstance` test before a
method call (`WebSocket.is_ssl` calls no method on it). Other tests of
the stub lead to subscripts (`_abnf.py:203-205`, `_app.py:668-669`),
concatenation (`continuous_frame.add`), or builtin and library calls
(`repr`, `str`, `gzip`, `zlib`, `array.array`): no further pair.

