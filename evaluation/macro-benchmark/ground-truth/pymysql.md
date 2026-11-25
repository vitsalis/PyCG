# pymysql: judgements of the ground truth

Release v1.2.3 (commit `c990e86`). Analysed source: `pymysql/` without
`pymysql/tests/`: 18 modules, 198 functions, 27 classes.
`pyproject.toml` declares `requires-python = ">=3.9"` and the classifiers
CPython and PyPy; `docs/source/user/installation.rst` names "CPython >= 3.9"
and "Latest PyPy 3". No platform classifier.

The ledger is `pymysql.ledger`; the graph `pymysql.json` is generated from
it. The trace covers only the nine offline test paths (33 items): 49 of 198
functions run, so most edges come from reading. Four trace edges are
rejected in `pymysql.rejected.json`: the tests' mocks
(`unittest.mock.CallableMixin.__call__`).

`AGENTS.md` of the tree (install and start mysqld) is third-party data;
none of it was followed.

## Status (for a resumed session)

- Done: every site has an entry; `check.py --write pymysql` and
  `check.py pymysql` report no error; the 4 missing trace edges are
  rejected.
- The ledger is generated from the skeleton and hand-written decision
  files in `$TMPDIR/b7-gt-pymysql/` (`merge.py`, `d1_*.txt` to `d4_*.txt`,
  `run.sh`). If the scratch directory is gone, edit `pymysql.ledger`
  directly.
- Second pass done (2026-11-22): the implicit sites without candidates
  (`check.py --report pymysql --without-candidates`, 695) and every site of
  the default `Cursor.__iter__` were read again; no site calls package code
  that no candidate names. Nothing is left for the writer.
- Graph: 216 nodes, 623 edges (311 inside, 312 outside); the trace
  confirms 132 (21.2%); 49 of 198 functions run (after the Corrections
  of 2026-11-25).
- Audit applied (2026-11-23, `pymysql.audit.md`; the referee's ruling
  `b7-ruling-pymysql.md`, adopted by the lead): F1 and F2 remove 2 inside
  edges (J6, J9 below); F3 corrects the notes at `_auth.py` 165:34 and
  216:34; I1 corrects the hash wording. J1 is confirmed. The referee's
  second ruling (`b7-ruling-pymysql-2.md`, adopted by the lead) removes 4
  outside edges (J11). Codex audit round 1 adds 1 inside edge (J12) and
  removes 1 outside edge (`_lenenc_int -> ValueError`); see "Codex round 1".

## Default rejections

- The `__getattr__` of `OKPacketWrapper`, `EOFPacketWrapper` and
  `LoadLocalPacketWrapper` (1197 sites each): the package reads only the
  attributes that each `__init__` sets. One load reaches a `__getattr__`:
  `self.read_struct` in `OKPacketWrapper.__init__` (`protocol.py:299:55`),
  which accepts it; the call `self.read_struct("<HH")` (`299:66`) then runs
  `MysqlPacket.read_struct` on the wrapped packet. No wrapper reaches a
  client (`Connection._read_ok_packet` is private and its callers drop it).
- `DBAPISet.__eq__`, `__hash__`, `__ne__`: the package never compares,
  hashes or stores its DBAPISet constants. `__ne__`'s `other not in self`
  (`__init__.py:87:26`) accepts `__hash__` (the tests compare two
  DBAPISets, `test_MySQLdb_nonstandard.py:15`; the trace has the edge) and,
  since Codex round 1, `__eq__` (J12). In `__eq__`'s lookup (`93:26`)
  `other` is not a frozenset, so no DBAPISet meets it.
- `Charset.__repr__`, `FieldDescriptorPacket.__str__`: no Charset and no
  field descriptor is formatted; the one format of a field is under
  `if DEBUG:` (`connections.py:1484`).
- `Cursor.__iter__`, `Cursor.__next__`: the package never iterates a
  cursor.

## Judgements

**J1. `DEBUG` flags.** `connections.DEBUG`, `protocol.DEBUG` and
`_auth.DEBUG` are module constants `False`. Nothing in the package, its
tests or its documentation sets them: `tests/test_auth.py:7-8` has
`# pymysql.connections.DEBUG = True` and `# pymysql._auth.DEBUG = True`
only as comments. A client's assignment to a package module attribute
counts only where documentation or tests make it (B2, the pyrate-limiter
and python-barcode rulings); tinytag's `TINYTAG_DEBUG` counted because
upstream's test job sets it. So every `if DEBUG:` branch does not run: the
`print` calls, `dump_packet` calls and `self.dump()` under it have no edge
(`_auth.py:161`, `172`, `178`, `222`, `242`, `251`, `255`, `267`;
`connections.py:674`, `691`, `743`, `759`, `800`, `898`, `971`, `975`,
`1036`, `1054`, `1077`, `1219`, `1223`, `1442`, `1484`; `protocol.py:70`,
`71`, `218`, `323`, `346`). `dump_packet` and `MysqlPacket.dump` keep the
edges of their bodies (rule A). For the lead: if commented-out lines in a
test should count as the tests setting the flag, about 30 sites gain
`<builtin>.print`, `dump_packet` and `MysqlPacket.dump` edges.
`_DEFAULT_AUTH_PLUGIN` is set by `tests/test_auth.py:76` and `111`: its
branch (`connections.py:1249-1250`) runs, but it makes no call.

**J2. Hash objects.** `sha1_new = partial(hashlib.new, "sha1")`
(`_auth.py:21`): its calls are `functools.partial.__call__`; partial calls
`hashlib.new` back (library code, no edge). The hash objects follow the
precedents of path (J6) and validators: OpenSSL's `_hashlib.HASH`, or by
hashlib's documented fallback the builtin object, named by the attribute
under which its module exports the type (Corrections of 2026-11-25).
SHA-1: `_sha1.SHA1Type` on CPython, and on PyPy `_sha1.sha` (the fallback
`_sha1.sha1` is a function there). SHA-256: `_sha256.SHA256Type` on CPython
3.9 to 3.11, `_sha2.SHA256Type` from 3.12, on PyPy `hashlib.sha256` (the
public alias of PyPy's class). SHA-512: `_sha512.SHA512Type` on CPython 3.9,
`_sha512.SHA384Type` on 3.10 and 3.11, `_sha2.SHA512Type` from 3.12, on
PyPy `hashlib.sha512` (classes of `lib_pypy/_sha256.py:206/218` and
`_sha512.py:234/245` in PyPy 3.9, 3.10 and 3.11). The factories keep their imported paths (`hashlib.sha256`,
`hashlib.sha512`).

**J3. `_auth.scramble_old_password`** (`connections.py:1100`): the module
`_auth` defines no such function, so the load of the callee raises
`AttributeError` before the arguments are evaluated. Neither the call nor
`auth_packet.read_all()` in its arguments has an edge.

**J4. configparser call-backs.** `optionfile.Parser` overrides
`optionxform`. `configparser.RawConfigParser.read` (`cfg.read`,
`connections.py:250`) and `.get` (`optionfile.py:20`) call
`self.optionxform`, so both sites have `Parser.optionxform` (the trace has
it at `Parser.get`). `RawConfigParser.__init__` (`optionfile.py:7`) calls it
for each key of a `defaults` dict (`_read_defaults`, CPython 3.11
`configparser.py:1148-1152`); `Parser` is public and forwards `**kwargs`,
so a client's `Parser(defaults={...})` reaches it: the edge stays. The
inherited `read` is named `configparser.RawConfigParser.read` (the
micro-benchmark rule for inherited methods).

**J5. Decoders** (`converter(data)`, `connections.py:1444`). The values of
`Connection.decoders` are the int-keyed values of `conv`, by default
`converters.conversions`: `int`, `float`, `decimal.Decimal`,
`convert_datetime`, `convert_timedelta`, `convert_date` and `through`
(also `convert_bit`), which `_get_descriptions` turns into `None`.
`convert_time` is added: its docstring documents it as the converter for
`FIELD_TYPE.TIME` (`converters.py:263-266`), a role named in the
documentation (B2). A client's own decoder is a client callback.

**J6. Encoders** (`encoder(val, mapping)`, `converters.py:31`). The values
are the 13 functions of the package's `encoders` other than
`escape_sequence` (directly, or through `Connection.encoders`, the
non-int keys of the constructor's `conv`, by default `conversions`);
`escape_sequence` is reached only at line 29. A client's own encoder in
`conv` is a client callback. `escape_string` is not a callee here (audit
F1, the referee's ruling): `Connection.escape` is internal by its docstring
("for internal use; do not use this in your applications",
`connections.py:530-533`), and the functions of `pymysql.converters` are
internal by `CHANGELOG.md:7` ("It's internal functions"), so both are
private under C. The tests' mapping `{str: pymysql.converters.escape_string}`
(`tests/test_connection.py:936`) does not widen the mappings that the
package's callers pass: every package call of `Connection.escape` omits
`mapping`, and no package mapping holds `escape_string`. The direct edges
to `escape_string` at `connections.py:560:40` and `converters.py:92:31`
stay. `escape_string`, `escape_set` and `through` are excluded at the site.

**J7. Missing modules.** cryptography (extra `rsa`) and PyNaCl (extra
`ed25519`) are not installed. Their calls keep the imported paths:
`cryptography.hazmat.primitives.serialization.load_pem_public_key`,
`cryptography.hazmat.backends.default_backend`,
`cryptography.hazmat.primitives.asymmetric.padding.OAEP` and `.MGF1`,
`cryptography.hazmat.primitives.hashes.SHA1`, and
`nacl.bindings.crypto_*`. `rsa_key.encrypt` (`_auth.py:148`) is
`cryptography.hazmat.primitives.serialization.load_pem_public_key.encrypt`
(a stub value keeps the factory's path, the django-constance precedent).
Both sides of the optional imports run.

**J8. Sockets and files.** `Connection._sock` is the package's
`socket.socket` (`connections.py:668`, `681`) or the `ssl.SSLSocket` of
`ctx.wrap_socket` (`952`); `_rfile` is the `io.BufferedReader` of
`makefile("rb")`. A socket that a client passes to `connect(sock)` is a
client object. Inherited methods of `SSLSocket` are named by the receiver
class (`ssl.SSLSocket.settimeout`, `.close`).

**J9. Cursor classes** (`connections.py:571`, `572`, `721`, `722`, `726`,
`727`). `Connection.cursor(cursor)` documents four classes (`:type cursor:`,
`connections.py:567-568`): Cursor, SSCursor, DictCursor and SSDictCursor;
all inherit `Cursor.__init__` (571:26). The constructor's `cursorclass`
admits only Cursor (its default) and DictCursor (`README.md:67`,
`docs/source/user/examples.rst:35`): admission at one parameter extends
along actual forwarding calls, not to another parameter that selects
similar objects (audit F2, the referee's ruling). `conn.cursor(SSCursor)`
does not change `conn.cursorclass`. So in `connect` the cursor `c` is a
Cursor or a DictCursor: `Cursor.execute` (721:26, 726:26) and `Cursor.close`
(722:24, 727:24), and no `SSCursor.close`. The bodies of the streaming
cursors keep their edges (rule A).

**J10. Client handlers.** The classes of `auth_plugin_map` are client
classes (the package defines none; the tests define their own). Calls of
the class, of `authenticate` and of `prompt` have no callee
(`connections.py:1057`, `1082`, `1119`, `1160`).

**J11. Private decoder inputs** (`converters.py` 182:25, 217:25,
269:25, 303:25; the referee's second ruling, adopted by the lead). The
four `convert_*` functions are private (`CHANGELOG.md:7`) and the package
calls them only at `connections.py:1444`, with the field data that it
decodes to `str` or leaves as bytes (`use_unicode=False`, or a binary
field). "Explicit type handling does not supply an otherwise excluded
input to a private function whose package callers constrain its
arguments. Admission as a configurable converter does not make its
parameters public-style: that requires a supported interface through
which the package hands the callable to client code for invocation." So
their `isinstance(obj, (bytes, bytearray))` checks keep only the bytes
arm: `<builtin>.bytes.decode` stays at each site, and
`<builtin>.bytearray.decode` goes (-4 outside edges). `convert_time` is
package-called through its documented decoder role, so the same applies.
The note of `escape_item` 19:26 now justifies `dict.get` by the package's
encoder dicts, not by client mappings of the internal `Connection.escape`.

**J12. A reflected `__eq__` in `DBAPISet.__ne__`** (`__init__.py:87:26`;
Codex round 1). `DBAPISet` is public, so a client can build one from its
own type codes. In `DBAPISet([h]) != pymysql.NUMBER`, with `h` the int
`hash(pymysql.NUMBER)`, `other not in self` hashes `NUMBER`
(`DBAPISet.__hash__`), finds the element `h` with the same hash, calls
`int.__eq__(h, NUMBER)`, which returns `NotImplemented`, and the
interpreter then calls the reflected `NUMBER.__eq__(h)`: an edge
`__ne__ -> DBAPISet.__eq__`. Codex's witness is a client element whose
`__hash__` returns that hash and whose `__eq__` returns `NotImplemented`.
That witness rests on B5's clarification that a client value's effects on
control flow count. I take the int witness: an int is the element type
that the package itself uses (type codes), so no crafted class is needed,
and the reading does not depend on how much a client class's `__hash__` may
do. The earlier argument (the module constants' hashes are far from 0 to
255) only covered the package's own sets. Not disputed.

## Codex round 1

- Missing `DBAPISet.__ne__ -> DBAPISet.__eq__` at `87:26`: applied (J12).
- False `_lenenc_int -> <builtin>.ValueError` at `connections.py:77:25`
  and `89:25`: applied. `_lenenc_int` is private, and its only callers
  (`986`, `1004`, `1006`, `1007`) pass `len()` results: never negative,
  and at most `sys.maxsize` (below `1 << 64`) on CPython and PyPy. Both
  checks cannot fail (B1).
- Metadata: the note of `escape_item` 19:26 now says that `escape_set`,
  which no package code calls, can forward a client mapping (opaque, no
  callee). The note of `Error.__init__` 20:25 now says that `super()`
  starts after `Error`, skips `MySQLError` and reaches `Exception`.
- No finding is disputed.

## Notes for the auditor

- `caching_sha2_password_auth` ends without `return pkt`
  (`_auth.py:270`): its full-authentication path returns `None`, and
  `_request_authentication` then calls a method of `None`. This is a bug of
  the release, not a convention; it removes no edge.
- `DBAPISet(...)` calls have no edge: neither `DBAPISet` nor `frozenset`
  defines `__init__` (CPython and PyPy's `setobject.py:653`), so the first
  `__init__` of the MRO is `object.__init__`.
- `err.X(...)` in `connections.py` and `cursors.py` are value sites only
  because the class body of `Connection` binds the same names
  (`connections.py:1255-1264`); each is the class of `pymysql.err`.

## Corrections of 2026-11-25

Two referee rulings, adopted by the lead, decide the names of the builtin
hash objects. Batch 8's "A C type exported under a module attribute other
than its type name" (`b8-ruling-c-type-names-1.md`) names a method of an
outside class by the attribute under which the defining extension module
exports the type, on each admitted runtime; the type name stays only on a
runtime that exports none, a factory names only its own call, and an
attribute that a module overwrites names what it holds last. The
corrections' ruling on public aliases (`ruling-names-2.md`; README,
"Rulings for the corrections of 2026-11-25") puts a direct public class
alias first in each implementation, version and configuration where the
attribute holds the receiver's class, also when the alias exists only in
that configuration; a factory is no class alias. pymysql admits CPython
3.9 and later and PyPy 3.9 to 3.11 (J2). The sources are the batch-8
dependency set (CPython and PyPy).

| Site | Caller | Edge removed | Edge added | Evidence |
|---|---|---|---|---|
| `_auth.py:33:39`, `34:37`, `38:22` | `_auth.scramble_native_password` | `_sha1.sha1.digest` | `_sha1.SHA1Type.digest` | `_sha1` exports the SHA-1 type as `SHA1Type` on every admitted CPython (`Modules/sha1module.c` 3.9.25 `:560`, 3.10.22 `:568-570`, 3.11.18 `:571`, 3.12.16 `:354`, 3.13.18 `:356`, 3.14.10 `:371`, 3.15.2 `:353`); `_sha1.sha1` is the factory on CPython and on PyPy (`lib_pypy/_sha1.py:347` in 3.9, `:359` in 3.10 and 3.11), whose object, `_sha1.sha`, is already named |
| `_auth.py:36:13`, `37:13` | `_auth.scramble_native_password` | `_sha1.sha1.update` | `_sha1.SHA1Type.update` | as above |
| `_auth.py:200:41`, `201:35`, `202:43` | `_auth.scramble_caching_sha2` | none | `_sha256.SHA256Type.digest` | CPython 3.9 to 3.11 export the SHA-256 type as `SHA256Type` (`Modules/sha256module.c` 3.9.25 `:720`, 3.10.22 `:725`, 3.11.18 `:728`); `hashlib.sha256` is a factory there |
| the same | the same | `_sha256.sha256.digest` | `hashlib.sha256.digest` | on PyPy, hashlib's fallback binds `hashlib.sha256` to the class `_sha256.sha256` (`lib-python/3/hashlib.py:98` in 3.9 and 3.10, `:97` in 3.11; the class `lib_pypy/_sha256.py:206` in 3.9, `:218` in 3.10 and 3.11), so the public alias names it |
| `_auth.py:87:40`, `93:49`, `103:48` | `_auth.ed25519_password` | none | `_sha512.SHA512Type.digest` | CPython 3.9 exports the SHA-512 type as `SHA512Type` (`Modules/sha512module.c` 3.9.25 `:778`) |
| the same | the same | none | `_sha512.SHA384Type.digest` | CPython 3.10 and 3.11 set `SHA384Type` to the SHA-384 type and then overwrite it with the SHA-512 type (3.10.22 `:782`, `:788`; 3.11.18 `:785`, `:791`), so the attribute holds the SHA-512 type |
| the same | the same | `_sha512.sha512.digest` | `hashlib.sha512.digest` | on PyPy, hashlib's fallback binds `hashlib.sha512` to the class `_sha512.sha512` (`lib-python/3/hashlib.py:102` in 3.9 and 3.10, `:101` in 3.11; the class `lib_pypy/_sha512.py:234` in 3.9, `:245` in 3.10 and 3.11) |
| `_auth.py:33:39`, `34:37`, `87:40`, `93:49`, `103:48`, `200:41`, `201:35`, `202:43` | `scramble_native_password`, `ed25519_password`, `scramble_caching_sha2` | none | `_hashlib._OneShotHash.digest` | on PyPy 3.11, `_hashlib.new(name, string)` returns a `_hashlib._OneShotHash` when `string` is non-empty (`lib_pypy/_hashlib/__init__.py:40-57`; its `digest`, `:79`); `hashlib.new` reaches it through `__hash_new` (`lib-python/3/hashlib.py:160`), and the named constructors are `_hashlib.openssl_*`, which `make_new_hash` makes to call `new(name, string)` (`lib_pypy/_hashlib/__init__.py:367-374`; `lib-python/3/hashlib.py:307` binds them); each of these sites hashes data that can be non-empty (the password, the scramble, `stage1`, `p1`, `p2 + nonce`). The class is named as the receiver's class (micro-benchmark naming; avro `protocol.py:108:59`). `36:13` to `38:22` start from `sha1_new()` with no data, a `_hashlib.HASH` |

These are direct named constructors (`hashlib.sha256(...)`,
`hashlib.sha512(...)`), whose OpenSSL constructors make no separate
builtin fallback (ruling-names-2), so the fallback object always comes
with the alias. What stays: `_hashlib.HASH.*`; `_sha2.SHA256Type` and
`_sha2.SHA512Type` (CPython 3.12 and later); `_sha1.sha.*` (PyPy's SHA-1
class; `hashlib.sha1` is a factory on both implementations, so no hashlib
name there). Four graph edges renamed and six added (all outside): 623
edges, 311 in the package, 312 outside.
