Status: the audit is complete: blind answers, comparison, exhaustive checks (defaults, dispatch, value roles, uncalled nodes, special methods and properties, notes and rejections, outside names, binding check, rejected trace edges, judgements J1 to J10), and the check against the batch 7 platform rulings (no edge change). Re-check done (see "Re-check"): the committed ledger (617 edges) is correct; nothing is left.

# pymysql: blind audit of the ground truth (batch 7)

Release v1.2.3, commit `c990e86`. Audited files: `pymysql.ledger` (2851
lines, 10 default rejections), `pymysql.json` (623 edges: 312 inside, 311
outside; 216 nodes), `pymysql.added.json` (491 added edges),
`pymysql.rejected.json` (4 edges), `pymysql.md` (J1 to J10). The trace
confirms 132 edges; 49 of 198 functions run. `check.py pymysql` reports no
errors.

I read the package source, `README.md`, `docs/source`, `CHANGELOG.md`,
`pyproject.toml` and the tests as data; I ran nothing of the package and
followed nothing of its `AGENTS.md`. No analysis tool was used. The CPython
and PyPy sources of the audit records (`deps/`) were read only.

## Findings

| Id | Severity | Site or edge | Evidence | Edges |
|---|---|---|---|---|
| F1 | medium (judgement J6) | `converters.py` 31:22 `encoder(val, mapping)` -> `pymysql.converters.escape_string` (edge `escape_item -> escape_string`) | J6 rests on `tests/test_connection.py:930-937` (`test_escape_fallback_encoder`), which passes `{str: escape_string}` as the `mapping` of `Connection.escape`. But `Connection.escape` is private by rule C: its docstring says "Non-standard, for internal use; do not use this in your applications." (`connections.py:531-534`), and the API page leaves it out (`docs/source/modules/connections.rst:8-11`: `:exclude-members: ... escape, literal, write_packet`). Rule A says that a direct test call of a private API does not admit its arguments; B2 says that the parameters of a private function are what the package's own calls pass. The package calls `escape` only with `mapping=None` (`cursors.py:109-123`, `273`; `connections.py:485`, `555`), so the mapping is always `self.encoders`. The json-repair ruling admits a package value in a client container at a *public* parameter only. `escape_item`'s own `mapping` is public, but no test, document or package code passes a mapping with `escape_string` there. So `escape_string` is not an encoder value. | -1 |
| F2 | low (judgement J9; ruling asked) | `connections.py` 722:24 and 727:24 `c.close()` -> `pymysql.cursors.SSCursor.close` (one edge `Connection.connect -> SSCursor.close`) | `c` is `self.cursorclass(self)`. The documentation names Cursor (the default, `connections.py:193`) and DictCursor (`README.md:67`, `docs/source/user/examples.rst:35`) for `cursorclass`; the `:type cursor:` list with SSCursor and SSDictCursor (`connections.py:566-568`) documents the other parameter, `cursor` of `Connection.cursor()`. No test passes `cursorclass` (`rg cursorclass` over the tests: none). The prometheus-client ruling ("that use alone does not make the class an implementation at every parameter ...; broader admission needs documentation that joins the roles") reads per parameter. The README does not say whether the two docstrings make one role. My opinion: they do not join the roles explicitly, so the smaller extension of the rulings is per-parameter admission, and the edge goes. My blind answer kept the edge with a question mark. The other cursorclass edges (`Cursor.__init__`, `Cursor.execute`, `Cursor.close`) do not change. | -1 if ruled so |
| F3 | low (notes only) | `_auth.py` 165:34 and 216:34, notes: "a client handler's packet never reaches this function" | It can. A handler of `auth_plugin_map` returns a packet (the tests' handlers return `self.conn._read_packet()`, `tests/test_auth_state_machine.py:103-105`). If that packet is an auth switch request whose new plugin has no handler, `_get_auth_plugin_handler` returns `None` (`connections.py:1045`) and `_process_auth(plugin_name, auth_packet, None)` passes the handler's packet to `caching_sha2_password_auth` or `sha256_password_auth` (`connections.py:1090-1093`). The packet is the result of a client callback, opaque by B5, so no edge changes; only the two notes are wrong. | 0 |
| I1 | info | `__init__.py` 87:26, default of `DBAPISet.__eq__` | The default says no element `__eq__` meets a DBAPISet because the hashes of the seven constants are far from 0 to 255; `pymysql.md` says they were computed on 64-bit CPython. PyPy (supported) and 32-bit builds hash frozensets differently, so the computation does not cover them. A collision would need a hash in 0 to 255, which is practically impossible, and on a collision the element `int.__eq__` returns `NotImplemented`, so `DBAPISet.__eq__` would run reflected. I accept the default; the note could say "on every supported runtime the chance is negligible" rather than rely on one computation. | 0 |

No finding of a missed edge. Net change if F1 and F2 are accepted: -2 edges
(623 to 621, both added edges, both inside the package).

## Step 1: blind re-derivation

Skeleton made without the ledger in `$TMPDIR/b7-audit-pymysql/`: 2565
sites (1073 explicit, 1191 getattr, 301 other implicit) and 49 value sites.
getattr dominates the implicit sites (the three wrapper `__getattr__` are
candidates at 1197 sites each), so the draw is by kind:
`random.Random(20261123)`, sites numbered in skeleton order, value sites
taken out of the pools, then `sample(explicit, 70)`, `sample(getattr, 35)`,
`sample(other implicit, 35)` in that order, plus all 49 value sites: 189
sites. Files: `draw.py`, `sample.txt`, `blind-answers.md` (written before
I opened any file of the writer).

| Sites | Agree | Disagree |
|---|---|---|
| 70 explicit | 70 | 0 |
| 35 getattr (all default-decided; my answer "none") | 35 | 0 |
| 35 other implicit (34 default-decided, 1 with an entry: the `with` at `connections.py` 438:18) | 35 | 0 |
| 49 value sites | 48 | 1 (`converters.py` 31:22: the writer has `escape_string`, F1) |

The disagreement is a writer edge that the rules do not support (rule C on
`Connection.escape`). Auditor errors: none in the sample. In my working
assumption A3 I named the CPython 3.12+ builtin SHA-1 class
`_sha1.SHA1Type` from memory; the writer's `_sha1.sha1`, with the
precedent of path (probe on CPython 3.9, 3.12, 3.14, 3.15), is right. No
sampled site depended on it. At `connections.py` 722:24 my blind answer
had `SSCursor.close` with a question mark; the writer has it (F2).

## Step 2: exhaustive checks

**Default rejections (10).**
- The three wrapper `__getattr__` (1196 or 1197 sites each). I listed every
  getattr site whose receiver can be a wrapper: the bodies of the three
  classes and `Connection._read_ok_packet`, `MySQLResult._read_ok_packet`,
  `_check_packet_is_eof`, `_read_load_local_packet`. Every load there reads
  an attribute that `__init__` sets before the load, or `__class__`, except
  `self.read_struct` at `protocol.py:299:55`, which the ledger accepts. No
  wrapper leaves the package: `Connection._read_ok_packet` is private and
  all six callers drop its result. The explicit sites under these defaults
  (`fmt.format(obj)` with `{0.hour}` fields on datetime objects, the three
  `getattr(self.packet, key)` on a MysqlPacket) call no wrapper. Correct.
- `DBAPISet.__eq__`, `__hash__`, `__ne__`: no package code compares, hashes
  or stores a DBAPISet; the `!=` sites compare ints, bytes, bools and
  timeouts; `__ne__`'s own `other not in self` is accepted for `__hash__`
  (DBAPISet is not a `set`, so DBAPISet != DBAPISet takes that branch; the
  trace has it). Correct (I1).
- `Charset.__repr__`, `FieldDescriptorPacket.__str__`: the only format of a
  package object is `{field}` at `connections.py:1484`, under `if DEBUG:`.
  The explicit sites under these defaults format ints, strs, bytes,
  exceptions and datetimes. Correct under J1.
- `Cursor.__iter__`, `__next__`: the package never iterates a cursor; the
  explicit sites under these defaults iterate bytes, lists, tuples, regex
  groups, client sequences (B3: a cursor as `args` is not considered) and
  the callable iterator of `fetchall_unbuffered`. Correct.

**Dispatch over the cursor classes (B1).** Receivers: Cursor and DictCursor
(Cursor.close, Cursor._query, Cursor.fetch*, Cursor.scroll); SSCursor and
SSDictCursor (the SSCursor overrides); all four (Cursor.execute,
executemany, callproc, _nextset, __next__, __exit__). MRO checks:
`self._do_get_result()` gives `Cursor._do_get_result` and
`DictCursorMixin._do_get_result` at 101:28, 336:28, 437:28; `_conv_row` gives
`DictCursorMixin._conv_row` at 386:41 and `SSCursor._conv_row` +
`DictCursorMixin._conv_row` at 445:30; `super()._do_get_result()` gives
`Cursor._do_get_result` only; `self.nextset()` gives `Cursor.nextset` at
60:31 and `SSCursor.nextset` at 426:31, both at 165:27 and 276:25. All agree
with the ledger. `Cursor._conv_row` has no caller: right.

**Value roles.** `converter(data)`: int, float, `decimal.Decimal`,
`convert_datetime`, `convert_timedelta`, `convert_date`, and `convert_time`
by its docstring; `through` maps to None (agree). `encoder(val, charset,
mapping)`: `escape_sequence` only (agree). `encoder(val, mapping)`: the 13
values of `encoders` (agree), not `escape_string` (F1). `packet_type(...)`:
MysqlPacket and FieldDescriptorPacket `__init__` (agree). `cursor(self)`
and `self.cursorclass(self)`: `Cursor.__init__` (agree; F2 is about
`close`). `plugin_class(self)`, `handler.authenticate`, `handler.prompt`:
client classes, no callee (agree). `errorclass(...)`: `Error.__init__`
(agree). `self.dict_type(...)`: `<builtin>.dict` (agree). `sha1_new(...)`:
`functools.partial.__call__` (agree). The `err.X(...)` value sites:
`Error.__init__` (agree).

**Nodes that no site calls (74, of which 18 are modules).** I checked
each: they are public entry points, special methods that clients or the
interpreter call (`__enter__`, `__exit__`, `__iter__`, `__next__`, `__del__`,
`__eq__`, `__ne__`, `__repr__`, `__str__`), DEBUG-only (`MysqlPacket.dump`),
unused (`get_bytes`, `is_resultset_packet`, `read_uint32`, `escape_set`,
`through` by identity) or shadowed (`Cursor._conv_row`). The two wrapper
`__getattr__` of EOF and LoadLocal packets have no caller: right (see the
defaults above).

**Special methods and properties.** Properties: `Charset.encoding`
(accepted at 332:55 and 651:45, the two loads on a Charset; rejected at the
nine `.encoding` loads on a Connection), `Charset.is_binary` and
`Connection.open` (no load in the package). `with` sites: only
`contextlib.suppress` and `open()`. Class calls: `DBAPISet(...)` has no
edge (frozenset and DBAPISet define no `__init__`; agree), the others reach
the package `__init__`.

**Rejections and notes.** All 74 site rejections and the notes that state a
receiver or a role read correctly against the source, except the two notes
of F3.

**Callees outside the package.** Names agree with the micro-benchmark rules
and the precedents: `ssl.SSLSocket.settimeout`, `.close`, `.makefile` by
the receiver class although inherited; `io.BufferedReader.read`/`.close`
for `makefile("rb")` and `open(..., "rb")`; `configparser.RawConfigParser.*`
for inherited and explicit base calls; `<builtin>.Exception.__init__` for
`super().__init__` in `Error`; `hashlib.sha256`/`sha512` for the factories;
the hash objects per implementation (J2, checked against
`lib_pypy/_sha1.py:117/129` and `:347/359`, `_sha256.py:206/218`,
`_sha512.py:234/245`, `_hashlib/__init__.py:57` in PyPy 3.9, 3.10 and 3.11);
cryptography and nacl by their imported paths (J7).

**Binding check.** I checked every call of a package function against its
signature (the package callees of the explicit sites, including `encoder(val,
mapping)` into `escape_not_supported(val, charset=None, mapping=None)` and
`Decimal2Literal(o, d)`, `_do_execute_many` with six arguments,
`Error.__init__(*args, sqlstate=None)`): every call binds. The one call that
cannot run is `_auth.scramble_old_password(...)` (`connections.py:1100`),
whose callee load raises `AttributeError` before its arguments (J3; agree).

**Rejected trace edges (4).** The `unittest.mock.CallableMixin.__call__`
edges of `_roundtrip`, `_process_auth`, `_request_authentication` (the
tests patch `write_packet` and `_read_packet` on the connection) and
`set_charset` (called unbound on a `mock.Mock(spec=Connection)`,
`tests/test_err.py`): client objects (B1, B5). Agree.

## The writer's judgement calls

| Id | Opinion |
|---|---|
| J1 DEBUG flags | Supported by B2 ("a client's assignment to a public attribute of a package object counts only where the package's documentation or tests make that assignment"); commented-out lines (`tests/test_auth.py:7-8`) make no assignment, and the tinytag ruling needed a real setting in the test job. A module flag is not named in B2's examples; treating a public module attribute like a public attribute of a package object is the smaller extension. Agree. If the lead ruled otherwise, about 20 edges would come in (`<builtin>.print` from 11 functions, `dump_packet` from 3, `MysqlPacket.dump`, two `bytes.decode`, one `bytes.hex`, `FieldDescriptorPacket.__str__` from `_get_descriptions`). |
| J2 hash objects | Supported by the clarification "hashlib's documented fallback changes the concrete SHA-1 receiver" and the precedents of path and validators; names checked against the PyPy sources. Agree. |
| J3 missing `scramble_old_password` | Python semantics: the callee expression is evaluated before the arguments. Agree. |
| J4 configparser call-backs | B5's call-back rule: library code calls the override on the package's own Parser; `defaults` through the public `**kwargs` is a documented library parameter. Agree. |
| J5 decoders | B2 ("the documentation names it for that role", `converters.py:263-266`). Agree. |
| J6 encoders | Disagree on `escape_string` (F1); agree on the rest. |
| J7 missing modules | Supported by the missing-module rule and the django-constance ruling (c) for the factory's result. Agree. |
| J8 sockets and files | B4/B5 and the outside-name rules. Agree. |
| J9 cursor classes | Agree for `cursor`; for `cursorclass` the README does not decide whether two docstrings make one role (F2). |
| J10 client handlers | B2/B5 and the django-constance ruling (b): a test-defined implementation is not admitted. Agree. |

## Platforms and implementations (the batch 7 platform rulings)

Checked after the lead added "Rulings for batch 7" to the README (the
pyfiglet, textdistance and websocket-client rulings). The ledger was not
changed after my audit (last commit `a7ee1a7`).

What PyMySQL 1.2.3 declares:
- Implementations: CPython and PyPy (`pyproject.toml` classifiers);
  "CPython >= 3.9" and "Latest PyPy 3" (`docs/source/user/installation.rst`).
  Its own test job runs PyPy (`.github/workflows/test.yaml:38-39`,
  `py: "pypy3.11"`). So PyPy is admitted. "Latest PyPy 3" restricts the
  PyPy versions to the newest one.
- Platforms: no `Operating System` classifier and no platform statement in
  the README or the docs. Every job runs on Linux (`test.yaml:16`,
  `django.yaml:11`: `ubuntu-latest`; lint and publish on `ubuntu-slim` and
  `ubuntu-latest`). By the textdistance ruling, Linux is the only supported
  platform; the `sys.platform.startswith("win")` branch
  (`connections.py:240-241`) admits no Windows.

The ledger against it:
- Unix sockets (`connections.py:668-674`): Linux has `AF_UNIX`, so the
  edges `socket.socket`, `socket.socket.settimeout` and
  `socket.socket.connect` of that branch stay. Correct.
- The `win` branch (`connections.py:240-241`) only assigns a literal path.
  The edge of the test itself (`<builtin>.str.startswith`, 240:39) runs on
  Linux too. No Windows name in the ledger.
- Named pipes: `named_pipe` only raises `NotImplementedError`
  (`connections.py:230-233`) on every platform. No platform edge.
- No Windows or macOS receiver anywhere in the ledger (`rg` for
  windows, win32, ntpath, darwin, macos: only the two lines above).
  Everything else is the same on Linux: `ssl.SSLSocket`, `socket.socket`,
  `io.BufferedReader`, `getpass.getuser`, and `os.path.expanduser` (named
  `os.path`).
- PyPy names (J2): these edges rest on PyPy being admitted, and it is.
  The PyPy-only names are `_sha1.sha.digest` and `_sha1.sha.update`, from
  `scramble_native_password`. The other hash names are the same as on
  CPython: `_hashlib.HASH` (`lib_pypy/_hashlib/__init__.py:57`),
  `_sha256.sha256` and `_sha512.sha512`. PyPy 3.11 v7.3.20, the latest PyPy
  in the deps, has the same classes (`_sha1.py:129`, `_sha256.py:218`,
  `_sha512.py:245`). So restricting PyPy to its latest release changes no
  name; the writer's mention of PyPy 3.9 and 3.10 changes no edge.
  `functools.partial.__call__` and the DBAPISet `__init__` note
  (`setobject.py:653`) hold on PyPy too. Correct.

Result: the platform rulings change no edge of pymysql. F1 to F3 stand as
they were.

## Re-check (2026-11-23, against the committed ledger)

Checked against `b7-ruling-pymysql.md` and `b7-ruling-pymysql-2.md` and the
writer's commits `232860a` and `171980b`. I read the diff
`a7ee1a7..HEAD` of `pymysql.ledger`, `.json`, `.added.json` and `.md`.
`check.py pymysql` reports no errors: 617 edges (310 inside, 307 outside),
the trace confirms 132, 4 rejected.

- First ruling (F1, F2): `escape_item -> escape_string` is gone. 31:22 now
  excludes `escape_string` with the reason of the ruling (Connection.escape
  is internal by its docstring, and `pymysql.converters` by
  `CHANGELOG.md:7`). `Connection.connect -> SSCursor.close` is gone at
  722:24 and 727:24; both sites reject it. `Cursor.close` and
  `Cursor.execute` stay. The direct edges to `escape_string` (560:40,
  92:31) and `Cursor.__init__` at 571:26 and 572:32 stay. Correct.
- Second ruling (J11): `<builtin>.bytearray.decode` is gone at 182:25,
  217:25, 269:25 and 303:25, and `<builtin>.bytes.decode` stays at each.
  Correct.
- F3: the two notes (165:34, 216:34) now say that a handler's packet can
  arrive and is opaque. I1: the default of `DBAPISet.__eq__`, the note at
  87:26 and `pymysql.md` now cover PyPy and 32-bit builds. Correct.
- `pymysql.md`: J6, J9 and the new J11 state the rulings; the status
  numbers are right; J1 is unchanged. The 19:26 note of `escape_item` no
  longer cites client mappings of `Connection.escape`.
- Nothing else changed. The ledger diff has only the lines above. The
  graph diff has exactly the 6 removed pairs (2 inside, 4 outside), and
  `added.json` follows them.

**Other entries that could rest on a public `pymysql.converters` or a
public `Connection.escape`.** I read every entry of the converters section
again, and every entry that calls `escape` or a converter:
- Encoder bodies (`escape_bool`, `_int`, `_float`, `_str`, `_bytes`,
  `_not_supported`, `_timedelta`, `_time`, `_datetime`, `_date`,
  `_struct_time`, `Decimal2Literal`): the values reach them through the
  query parameters of the public `execute` and `callproc`. That includes
  inf or nan floats and Decimals, negative timedeltas, dicts, and bytes
  inside a sequence. So their edges keep a package flow.
- `escape_item`'s `TypeError` (26:28): a public `conv` without a str key.
- `escape_set`: no package caller, so it keeps the fallback for uncalled
  private functions.
- `escape_string`'s `str.translate`: its package callers pass str.
- The decoders: they get only what `connections.py:1444` passes, plus
  `convert_time` by its documented decoder role.
- `Connection.escape`: `<builtin>.bytearray.hex` at 539:32 stays. Its
  input is an item of the client's public query parameters, not a value
  that a private caller limits. The release states bytearray as a binary
  parameter type on Python 3 (`CHANGELOG.md:405-407`; the pgvector ruling
  on a changelog as a support statement). Its `mapping` is always None
  now, and no entry relies on another mapping.
- `Connection.literal`: it is private too; its body edges stay by rule A.

No other entry depends on reading them as public.

**Verdict: the committed ledger and graph are correct. I have no open
finding.**

## For the lead

- F2 needs a ruling: does `:type cursor:` of `Connection.cursor()` also
  admit its classes at the `cursorclass` parameter of `Connection`? 1 edge.
- F1 is decided by rule C as written, if the lead agrees that "for internal
  use; do not use this in your applications" marks `Connection.escape`
  private. 1 edge.
- README and tools: no error found. The skeleton, `--report`,
  `--default` and `--without-candidates` worked as documented.

## Audit of the corrections of 2026-11-25

Branch `vitsalis/gt-pymysql-hash` (7865eca, PR #110) against `main`
(2130a69): four outside edges renamed and six added in `pymysql.json`,
`pymysql.added.json`, `pymysql.ledger` and `pymysql.md`;
`evaluation/metrics.json` is not recorded yet. I read `pymysql/_auth.py`
from the inputs image and CPython 3.9.25 to 3.15.2 and PyPy 3.9 v7.3.16,
3.10 v7.3.19 and 3.11 v7.3.23 from the dependency sources, as text.
Nothing ran; no PyCG output was read. pymysql admits CPython 3.9 and
later and PyPy 3.9 to 3.11 (J2).

| Sites (`_auth.py`) | Change | Verdict | Evidence |
|---|---|---|---|
| `33:39`, `34:37`, `38:22`; `36:13`, `37:13` | `_sha1.sha1.digest`, `.update` renamed `_sha1.SHA1Type.*` | agree | `sha1_new = partial(hashlib.new, "sha1")` (`:21`); CPython's fallback `_sha1.sha1` is a factory whose type `_sha1` exports as `SHA1Type` (checked for bottle); PyPy's `_sha1.sha1` is a function returning `_sha1.sha` (kept), and `hashlib.sha1` is that function, so no alias |
| `200:41`, `201:35`, `202:43` | `_sha256.SHA256Type.digest` added; `_sha256.sha256.digest` renamed `hashlib.sha256.digest` | agree | CPython 3.9.25 `sha256module.c:556` (type `"_sha256.sha256"`), `:720`; 3.10.22 `:567`, `:725`; 3.11.18 `:570`, `:728` (`SHA256Type`). PyPy: the class `_sha256.sha256` (`lib_pypy/_sha256.py:206` in 3.9, `:218` in 3.10 and 3.11), cached as `hashlib.sha256` by the fallback (`lib-python/3/hashlib.py`); at a direct constructor the alias holds the class (ruling-names-2), so no runtime keeps `_sha256.sha256` as a name |
| `87:40`, `93:49`, `103:48` | `_sha512.SHA512Type.digest` and `_sha512.SHA384Type.digest` added; `_sha512.sha512.digest` renamed `hashlib.sha512.digest` | agree | CPython 3.9.25 `sha512module.c:778` exports `SHA512Type`; 3.10.22 `:782` and `:788`, 3.11.18 `:785` and `:791` set `SHA384Type` to the SHA-384 type and then to the SHA-512 type, so that attribute names the SHA-512 object there (the C-type ruling's own example); PyPy's class `_sha512.sha512` (`_sha512.py:234` in 3.9, `:245` in 3.10 and 3.11) is `hashlib.sha512` in the fallback |
| the eight sites with data: `33:39`, `34:37`, `87:40`, `93:49`, `103:48`, `200:41`, `201:35`, `202:43` | `_hashlib._OneShotHash.digest` added | agree | PyPy 3.11 `lib_pypy/_hashlib/__init__.py:40-55`: `new(name, string)` returns `_OneShotHash(...)` when `string` is non-empty (the class at `:57`); `hashlib.new` reaches `_hashlib.new(name, data)` (`__hash_new`, `hashlib.py:160`), and `hashlib.sha256`/`sha512` are `openssl_*` from `make_new_hash`, which calls `new(name, string)` (`:367-374`); PyPy 3.9 and 3.10 have no `_OneShotHash` (`new` at `:28` and `:40` returns a `HASH`). `35:17` `sha1_new()` has no data, so `36:13` to `38:22` stay `HASH` |

Kept, rightly: `_hashlib.HASH.*`, `_sha2.SHA256Type.digest` and
`_sha2.SHA512Type.digest` (CPython 3.12 and later), `_sha1.sha.*`.
Nothing missed: `_auth.py:33-38`, `87-103` and `200-202` are the
package's only hash objects (the other "sha256" matches are plugin names),
and the eight sites take non-empty data from the package's callers (a
password, a digest, a concatenation with the scramble or nonce).

Counts. 623 edges (311 inside, 312 outside), 132 traced: as `check.py
pymysql` reports, which passes with the source in place, as do `--origin`
and `--report`; four renamed and six added, as the commit says. The `make
eval` numbers come from PyCG's output, which I did not read.

**Verdict.** Closed: the renames and additions stand, and nothing is
missed. No finding.
