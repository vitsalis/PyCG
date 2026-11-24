# avro: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write avro`
and `check.py avro` report no error; every site is decided; every trace edge is in the graph or in
`avro.rejected.json` (10 edges: 9 by J1, 1 naming artefact). After the blind audit
(`avro.audit.md`, 85 of 88 sites agree) and the lead's rulings of
2026-11-24: F1 removed 1 inside edge; Q1 admitted PyPy 3.10 and 3.11 on
Linux (5 outside edges added); Q3 confirmed J1; W1 corrected J8's count;
the referee's ruling on Q2 (b8-ruling-avro-1, J8) removed 13 inside edges.
Codex round 1 removed 1 outside edge and renamed 1 (see "Codex round 1").
The referee's ruling on C-type names (b8-ruling-c-type-names-1, adopted by
the lead) added 8 and removed 1 outside edge (J5, "PyPy", "Callees outside
the package").

Release 1.12.2, the PyPI sdist `avro-1.12.2.tar.gz` (SHA-256
`e900e7b5…78fe08`). Analysed source: `avro/` without `avro/test/` (19
modules, 439 functions with 12 lambdas, 89 classes, 3231 sites). The
ledger is `avro.ledger`; `avro.json` and `avro.added.json` are generated
from it.

## Versions, implementations and platforms

- `pyproject.toml` declares `requires-python = ">=3.10"` and the
  classifiers CPython 3.10 to 3.14; no implementation classifier, no
  operating system classifier. The sdist has no CI file; upstream's
  `.github/workflows/test-lang-py.yml` at the tag `release-1.12.2`
  (`deps/upstream-ci/avro-release-1.12.2-test-lang-py.yml`, SHA-256
  `a3bf73c3…590897`) runs its test job on `ubuntu-latest` and
  `ubuntu-24.04-arm` with CPython 3.10 to 3.14, `pypy-3.10` and
  `pypy-3.11`. The lead's ruling on Q1 (2026-11-24; the path ruling
  "Implementation, version and platform combinations" and the textdistance
  ruling): the admitted runtimes are CPython 3.10 and later (3.15 included:
  the last classifier is no upper bound) and PyPy 3.10 and 3.11 (sources
  `pypy3.10-v7.3.19` and `pypy3.11-v7.3.23` of the deps), on Linux
  (x86-64 and aarch64) only. Names that depend on it: `pathlib.PosixPath`
  only (no `WindowsPath`) at `schema.py:1351:38`, `tool.py:46:84` and
  `:100:77`; the PyPy names below ("PyPy"). No edge inside the package
  depends on the platform or the implementation.
- Version branches: `utils.py:27` (`sys.version_info >= (3, 8)`) takes the
  `typing` branch on every admitted version; `tool.py:107` and
  `__main__.py:209` take `add_subparsers(required=True, ...)`, so the
  `else` calls (`:107:127`, `:209:127`) have no edge. `random.randbytes`
  exists from 3.9, so `utils._randbytes` is never used (its body keeps its
  edges, rule A).
- Optional imports (`codecs.py:119-136`): both sides run. bz2 is in the
  standard library; python-snappy and zstandard are optional extras that
  the test environment does not install: missing modules, named by their
  module path (`snappy.compress`, `zstandard.ZstdCompressor`,
  `zstandard.ZstdDecompressor.stream_reader.read`; the import binds
  `zstandard` as `zstd`, the stubs keep the module's name).
- `-O`: the one assert with a call (`tether_task.py:49`,
  `inputProtocol.types_dict`) keeps its edge in the union.
- Configuration that the package documents and the tests set:
  `AVRO_MAX_COLLECTION_ITEMS` (`io.py:687-742`, also in the error
  messages) and `AVRO_MAX_DECOMPRESS_LENGTH` (`codecs.py:46-76`); both
  read through `os.environ.get`, named `collections.abc.Mapping.get`.
  `AVRO_TETHER_OUTPUT_PORT` is documented in `TetherTask.open`.

## PyPy

The names that differ on PyPy, each from the file that defines it (both
PyPy releases unless one is named):

- `hashlib.new` is `__hash_new` (`lib-python/3/hashlib.py:170-171`), which
  calls `_hashlib.new(name, data)` (`:160`). PyPy 3.11's `_hashlib.new`
  returns a `_hashlib._OneShotHash` when the data are not empty
  (`lib_pypy/_hashlib/__init__.py:40-57`); `fingerprint` passes the UTF-8
  canonical form, never empty, so `schema.py:338:24` adds
  `_hashlib._OneShotHash.digest`. PyPy 3.11's `hashlib.md5` is
  `_hashlib.openssl_md5` (`hashlib.py:172`, `:307`), made by
  `make_new_hash` (`_hashlib/__init__.py:367-374`, for every name of
  `_algorithms`, `:294`), which calls `new(name, string)`: the same class
  at `protocol.py:108:59` (the encoded JSON of the protocol). PyPy 3.10's
  `_hashlib.new` makes a `_hashlib.HASH` (`__init__.py:40-43`, class
  `:57`), the CPython name.
- The fallback `_sha1.sha1` is a function that returns a `_sha1.sha`
  (`lib_pypy/_sha1.py:129`, `:359`): `schema.py:338:24` adds
  `_sha1.sha.digest`. The other fallback classes are named by the classes
  PyPy defines (b8-ruling-c-type-names-1): `_md5.md5` (the mixed module
  `pypy/module/_md5/moduledef.py:22`
  exports `W_MD5` as `md5` and takes precedence over `lib_pypy/_md5.py`),
  `_sha256.sha224`, `_sha256.sha256`, `_sha512.sha384`, `_sha512.sha512`
  (`lib_pypy/_sha256.py:218`, `:242`; `_sha512.py:245`, `:269`;
  `lib-python/3/hashlib.py` imports `_sha256` and `_sha512` in both
  releases), `_sha3.sha3_*` (`lib_pypy/_sha3/__init__.py`), `_blake2.blake2b`
  and `blake2s` (`lib_pypy/_blake2/__init__.py:157-166` in 3.10, `:160-169` in 3.11, set the names).
- zlib exports the Decompress type itself as `decompressobj`
  (`pypy/module/zlib/moduledef.py:30`; TypeDef `'Decompress'` without a
  module, `interp_zlib.py:399` in 3.10, `:422` in 3.11): its public path is
  `zlib.decompressobj`, so `codecs.py:208:52` and `:214:43` add
  `zlib.decompressobj.decompress` and `.flush` beside CPython's
  `zlib.Decompress`.
- The csv writer is named by its type name `_csv.writer` (TypeDef
  `'_csv.writer'`, `pypy/module/_csv/interp_writer.py:172` in 3.10, `:185`
  in 3.11; `moduledef.py:73-87` exports only the factories), beside
  CPython's exported `_csv.Writer` (b8-ruling-c-type-names-1).
- The same names as on CPython: `bz2.BZ2Decompressor` (`'_bz2.BZ2Decompressor'`,
  `pypy/module/bz2/interp_bz2.py:537`), `struct.Struct` (`'Struct'`,
  `pypy/module/struct/interp_struct.py:244`, exported by
  `moduledef.py:60`), the `io` classes (`'_io.BytesIO'`,
  `'_io.BufferedReader'`, `'_io.BufferedWriter'`, `'_io.FileIO'`,
  `'_io.TextIOWrapper'`, `pypy/module/_io/interp_bytesio.py`,
  `interp_bufferedio.py`, `interp_fileio.py`, `interp_textio.py`),
  `collections.deque` (`'collections.deque'`,
  `pypy/module/_collections/interp_deque.py:574`), `socket.socket`
  (subclass of `'_socket.socket'`, `pypy/module/_socket/interp_socket.py:1110`),
  `binascii.crc32` (`pypy/module/binascii/moduledef.py:29`).
- Unchanged behaviour: PyPy's `datetime` is `lib-python/3/datetime.py`;
  its `astimezone` calls the tzinfo's `utcoffset` (before testing `tz is
  mytz`) and `tzinfo.fromutc` (`utcoffset`, `dst`), its `__sub__` skips the
  offsets when both sides have the same tzinfo, its `isoformat` calls
  `utcoffset`: the package callees of J7. Its `json` encodes `str`
  subclasses through `ESCAPE.sub` without `__str__`
  (`lib-python/3/json/encoder.py`): J2 gains no edge.

## Values, as the ledger uses them

- **Schemas.** The concrete schema classes are `PrimitiveSchema`, its
  logical subclasses (`BytesDecimalSchema`, `DateSchema`,
  `TimeMillisSchema`, `TimeMicrosSchema`, `TimestampMillisSchema`,
  `TimestampMicrosSchema`, `UUIDSchema`), `FixedSchema`,
  `FixedDecimalSchema`, `EnumSchema`, `ArraySchema`, `MapSchema`,
  `UnionSchema`, `ErrorUnionSchema` and `RecordSchema` (types record, error
  and request). `Schema` and `NamedSchema` are abstract by `abc`. A field
  type, array item, map value or protocol response can be any of them; a
  union branch is never a union (`UnionSchema.__init__` refuses a branch
  of type "union", which an `ErrorUnionSchema` also has). The macros of
  the ledger list the dispatch sets: 16 `to_json`, 7 `to_canonical_json`
  (the logical classes inherit), 7 `match`, 15 `validate`.
- **Equality and hashing.** Every concrete schema takes `__eq__` and
  `__hash__` from `EqualByPropsMixin` (primitives, fixed, enum and their
  subclasses) or `EqualByJsonMixin` (array, map, union, record, and
  `Field`), which come before `Schema` in the MRO; `Schema.__eq__` is never
  called. The package compares schemas only in `Message.__eq__` and in
  `EqualByPropsMixin.__eq__` (J4); it hashes only `ReaderWriter` pairs, in
  the memo dict of `ReaderWriterCompatibilityChecker`. The tests compare
  schemas with schemas and with `object()`, Names with Names
  (`test_name.py:87-91`) and Protocols with Protocols
  (`test_protocol.py:462`): these are the admitted `that`/`other` values.
- **Streams (J1).** `BinaryDecoder`, `BinaryEncoder`, `DataFileReader` and
  `DataFileWriter` annotate their stream with the abstract `IO[bytes]` or
  `IO[AnyStr]`, so a client's stream is opaque (the segno ruling). The
  package's own streams: `io.BytesIO` (codecs, ipc, tether, the buffer of
  `DataFileWriter`); through `DataFileReader`, the `io.BufferedReader` of
  the files that `avro.tool` and `avro.__main__.cat` open with
  `argparse.FileType("rb")` or of `sys.stdin.buffer`; through
  `DataFileWriter`, the output of `avro.__main__.write`: a file of
  `FileType("wb")` (`io.BufferedWriter`) or `sys.stdout.buffer`
  (`io.BufferedWriter`, `io.FileIO` under `python -u`). `FramedReader`
  reads the `rfile` of the request handlers that the package starts
  (`socket.makefile("rb", -1)`, an `io.BufferedReader`) or the
  `http.client.HTTPResponse` of `HTTPTransceiver`; `FramedWriter` writes
  the `wfile` (`socketserver._SocketWriter`, `wbufsize` 0) or an
  `io.BytesIO`.
- **Data.** Decoded records and maps are dicts; `datum` parameters are
  client data. A datetime decoded from a timestamp has
  `tzinfo=avro.timezones.utc`; the tests put `avro.timezones.utc` and
  `tst` into the datetimes they write (`test_io.py:119-139`), admitted as
  package values inside client containers (the json-repair ruling).
- **Codecs.** `KNOWN_CODECS` holds `NullCodec`, `DeflateCodec`,
  `BZip2Codec`, `SnappyCodec` and `ZstandardCodec` (where installed);
  `get_codec` returns one of the classes.

## Default rejections

| Candidates | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `Schema.__eq__` | 536 | abstract, always overridden by a mixin's `__eq__` | nowhere |
| `__eq__` of the two mixins, `Name`, `Message`, `Protocol`, `ReaderWriter` | 532 to 536 each | no operand or key is such an object | the memo dict (`compatibility.py:156-163`), `Message.__eq__` (`protocol.py:226:64`), `EqualByPropsMixin.__eq__` (`schema.py:226:54`, J4) |
| `__hash__` of the two mixins and `ReaderWriter` | 374 to 378 each | no such object is hashed | the memo dict |
| `DataFileReader.__iter__`, `__next__` | 184, 186 | no data file is iterated | `tool.main_dump`, `tool`'s `next(dfr)`, `__main__.print_avro` |
| `Message.errors` | 171 | the loads are of the module `avro.errors` | the five loads on Messages (ipc, protocol) |
| `__str__` of `Schema`, `Field`, `Protocol`, `Message`, `SchemaType` | 163 to 170 each | no such object is formatted or converted | the `str()` calls on schemas and protocols, `_safe_pretty`'s fallback (J3), the SchemaType formats (J2) |
| `_DataFileMetadata.schema` | 116 | the loads are of the module `avro.schema` | the four loads and stores in `datafile`, `__main__.print_schema` |
| `name` of `Name`, `Message`, `Protocol`, `NamedSchema` | 58 to 67 each | Fields have an instance attribute `name` | every load on a Name, Message, Protocol or NamedSchema |

8 defaults (23 candidates) decide 6616 candidate-site pairs.

## Judgement calls

**J1. Client streams and the rejected trace edges.** By the segno ruling
(an abstract stream annotation: client streams opaque; concrete streams
supplied by the package keep their edges), the stream methods are named by
the package's own streams only ("Values"). The tests' append tests pass
files opened in an update mode (`io.BufferedRandom`); no package flow
makes one, so the 9 trace edges to `_io.BufferedRandom.*` are rejected
(`avro.rejected.json`). The `io.BufferedReader` and `io.BufferedWriter`
edges that the tests also make stay, because the package's command-line
tools pass such streams. The lead confirmed J1 (Q3, 2026-11-24: the segno
ruling; client streams at `IO[...]` parameters are opaque). `DataFileWriter.__init__`'s append branch (`writer.seek`,
`datafile.py:197`) has only client streams: no callee.

**J2. SchemaType members as type names.** `SchemaType(str, Enum)` defines
`__str__`. The tests pass its members where schema JSON goes into the
public constructors: `PrimitiveSchema(SchemaType.INT)`, the items, values
and branches of `ArraySchema`, `MapSchema`, `UnionSchema`, and the "type"
of dicts inside them, records and fields included
(`test_compatibility.py:38-51`, `136-158`, `402-427`). So a schema's
`type` (and a primitive's `fullname`) can be such a member. Its `==` and
hash are `str`'s (str comes first in the MRO); an f-string calls
`Enum.__format__`, which calls `str(self)` (`enum.py`, 3.10 and 3.12+),
hence `SchemaType.__str__`. Edges: `type_mismatch` (2 formats),
`calculate_compatibility` (`compatibility.py:274:58`; both in the trace),
`UnionSchema.__init__` (`schema.py:904:58`, a union of two equal
members), `make_logical_schema` (`:1239:132`, `:1242:90`, a client
logicalType that does not fit the type), `Name.__init__` (`name.py:91:52`,
a member forwarded by `Names.has_name` with a Names that has a default
namespace). The admitted members are the ones the tests use at each
position; a member the tests never pass to `PrimitiveSchema` (such as
`ARRAY`, which it refuses) is not considered, so `schema.py:513:47` has no
edge. 5 inside edges rest on J2 (2 of them in the trace).

**J3. `_safe_pretty` returns the schema.** `SchemaResolutionException`
formats `_safe_pretty(writers_schema)`, which returns the schema itself
when `json.dumps` or `json.loads` raises. `other_props` is
`Mapping[str, object]`, so a schema built with a value that json cannot
serialize (a set) makes `str(schema)` raise; the f-string then formats the
schema, whose `object.__format__` calls `Schema.__str__` again
(`errors.py:105:48`, `106:48`; one edge,
`SchemaResolutionException.__init__ -> Schema.__str__`).

**J4. `EqualByPropsMixin.__eq__` compares props dicts.** `self.props ==
getattr(that, "props")` compares the values of equal keys. `that` is an
admitted schema whose props can hold schemas (an `ArraySchema`'s "items",
a `MapSchema`'s "values", a `RecordSchema`'s "fields" list of Fields).
`other_props` (`Mapping[str, object]`) lets a client give a primitive the
same keys, `PrimitiveSchema("int", {"type": "array", "items": 1})`; the
plain value's `__eq__` returns `NotImplemented` and Python calls the
schema's `__eq__` reflected. Edges: `EqualByPropsMixin.__eq__ ->
EqualByPropsMixin.__eq__` and `-> EqualByJsonMixin.__eq__`
(`schema.py:226:54`). The JSON comparison of `EqualByJsonMixin.__eq__`
holds only parsed JSON: no edge.

**J5. Hash objects.** (PyPy's names: see "PyPy".) `Schema.fingerprint` calls `hashlib.new` for any
name of `hashlib.algorithms_guaranteed` (its docstring). `h.digest()`
(`schema.py:338:24`) names `_hashlib.HASH.digest` (OpenSSL),
`_blake2.blake2b.digest` and `_blake2.blake2s.digest` (hashlib never takes
blake2 from OpenSSL, `__block_openssl_constructor`), and the documented
fallback's builtin classes, each named by its module's exported type
attribute where the runtime has one (b8-ruling-c-type-names-1, adopted by
the lead): `_md5.MD5Type` (`Modules/md5module.c`, 3.10.22 `:591` to 3.15.2
`:358`), `_sha1.SHA1Type` (`sha1module.c`, 3.10.22 `:569` to 3.15.2
`:354`), `_sha3.sha3_224` to `_sha3.sha3_512`; on CPython 3.10 and 3.11
`_sha256.SHA224Type` and `_sha256.SHA256Type` (`sha256module.c:720`,
`:725`; 3.11.18 `:723`, `:728`) and, for the SHA-512 object,
`_sha512.SHA384Type`: `sha512module.c` exports `SHA384Type` and then
overwrites the attribute with the SHA-512 type (3.10.22 `:782`, `:788`;
3.11.18 `:785`, `:791`), so SHA-384 keeps its type name `_sha512.sha384`
and SHA-512 has no other path; from 3.12 `_sha2.SHA224Type` to
`_sha2.SHA512Type` (`sha2module.c`, `PyModule_AddType`). PyPy's classes
keep their lowercase names ("PyPy"): `_md5.md5`, `_sha1.sha`,
`_sha256.sha224`, `_sha256.sha256`, `_sha512.sha384`, `_sha512.sha512`.
The ruling removed `_sha1.sha1.digest`, which names neither runtime's
class. shake_128 and shake_256 objects need a length, so
`digest()` cannot bind: no edge. `Protocol.__init__`'s `hashlib.md5`
digest has `_hashlib.HASH.digest`, `_hashlib._OneShotHash.digest` (PyPy
3.11), `_md5.MD5Type.digest` (CPython) and `_md5.md5.digest` (PyPy). Precedents:
markdown2 J13, path J6, pymysql J2.

**J6. The default validator.** `PrimitiveSchema.validate` looks the type
up in `_validators` with the default `lambda x: False`
(`schema.py:551-552`). `Schema.__init__` annotates `type_: str`, so an
admitted client `str` subclass of a primitive name with its own `__hash__`
passes the `in PRIMITIVE_TYPES` test (equality) but misses the dict, and
the default lambda runs (the python-barcode precedent on admitted `str`
subclasses). One inside edge: `PrimitiveSchema.validate ->
PrimitiveSchema.validate.<lambda1>`. By the same reasoning the "unknown
type" raises of `make_avsc_object` keep their `Exception.__init__` edges.

**J7. tzinfo call-backs.** The package's `UTCTzinfo` and `TSTTzinfo`
methods are called back by `datetime`:
- `datum.astimezone(tz=utc)` (`io.py:663:33`, `673:33`) calls the
  `utcoffset` of the datum's tzinfo (`TSTTzinfo` for `tst`; `utc` returns
  the datum itself) and then `utc.fromutc`, the C `tzinfo.fromutc`, which
  calls `UTCTzinfo.utcoffset` and `.dst` (`_datetimemodule.c`,
  `datetime_astimezone`, `tzinfo_fromutc`). The subtraction that follows
  has the same tzinfo on both sides: no call.
- `dt.tzinfo.utcoffset(dt)` (`schema.py:115:57`): both `utcoffset`s.
- Formatting or `str()` of an aware datetime calls `isoformat`, which
  calls the tzinfo's `utcoffset`: the `{datum}` of
  `AvroTypeException.__init__` (`errors.py:77:46`) and of the warnings of
  `write_data` that a datetime can reach (time logical types,
  `io.py:1372:64`, `1380:64`; decimals, `1406:68`, `1419:68`); and the
  decoded timestamps (tzinfo `utc`) that `avro.tool` prints or formats
  (`tool.py:54:48`, `101:10`) and that the csv writer of
  `__main__.print_csv` converts (`__main__.py:71:15`). `repr()` of a
  datetime calls no `utcoffset` (`tool.main_dump`), and `json.dumps`
  refuses a datetime before any call.

**J8. TetherTask, an abstract base for client subclasses
(b8-ruling-avro-1).** `TetherTask` is documented for subclassing and
abstract by `abc` (`tether_task.py:155`; `map`, `reduce`, `reduceFlush`,
`:367-407`); the package has no subclass (the tests' `word_count_task.py`
is excluded). The referee's ruling (Codex, 2026-11-24, adopted by the
lead; `selection/batch-8-proposal/rulings/b8-ruling-avro-1.md`) takes the
middle reading:

- No package callee for a call dispatched on the task, whether the method
  is abstract or concrete: by B1 the client's subclass of an abstract
  documented base is no admitted receiver (the asyncstdlib precedent
  excludes the concrete inherited `_recreate_cm`). The 13 dispatch sites
  have no callee: `self.fail` and `self.close` in `TetherTask`
  (`tether_task.py:266:22`, `304:22`, `351:22`, `363:26`, `436:19`) and the
  calls on the stored task in `TaskRunnerResponder.invoke` and `TaskRunner`
  (`tether_task_runner.py:64:36`, `68:31`, the `partitions` setter,
  `74:32`, `80:35`, `81:32`, `89:27`, `193:23`, `209:24`; the weakref
  proxy forwards to the client's task). Nor do the abstract calls
  (`tether_task.py:334:29`, `345:41`, `346:32`, `359:33`).
- Values that the package creates and stores on the task keep their
  provenance (a clarification of B5: storage on a client object does not
  erase package provenance established by assignment and forwarding). The
  17 attribute-derived edges stay: the `HTTPRequestor` of `open`
  (`:260`), also forwarded to `Collector` (`:292`, `:297`, `:84`), with
  `HTTPRequestor.request` at `104:34`, `263:38`, `365:34`, `413:34`,
  `419:34`, `432:38`; the `DatumReader`s of `configure` (`:291`, `:295`)
  at `331:50`, `341:57`; the parsed `midschema` (`:197`, a record by the
  documented example) at `300:67`, `300:84`; the logger of `:226`
  (`logging.Logger.info`, `.warning`, `.error`, `.exception` at `251:22`,
  `350:29`, `362:33`, `425:23`, `434:31`, `439:22`); the event of `:225`
  (`threading.Event.set` at `449:36`, `.wait` at
  `tether_task_runner.py:197:46`). 9 inside and 8 outside edges.

The ruling removed 13 inside edges from the writer's first reading
(commit `91618dd`); the audit (F2, R1, W1) had asked for it.

**J9. Servers that the package starts.** `tool.run_server` and
`TaskRunner.start.thread_run` make an `http.server.HTTPServer` with the
package's handler class and call `serve_forever` (the package-started
servers ruling). `GenericHandler` has no `__init__`: the library's
`BaseRequestHandler.__init__` calls `handle`, which calls `do_POST`, a
call-back of `run_server`'s `serve_forever` (`tool.py:94:25`).
`TaskRunnerHTTPHandler` defines `__init__`, which the server calls
(`tether_task_runner.py:185:46`) and which calls
`http.server.BaseHTTPRequestHandler.__init__` explicitly; `do_POST` is
the call-back of that call (`:116:56`). `Thread.start` runs `thread_run`
(`:189:22`); `GenericHandler`'s quitter thread runs the server's
`shutdown`, library code (no edge).

**J10. Lazy iteration in `print_avro`.** `filter(predicate,
data_file_reader)` calls `DataFileReader.__iter__` when it is made
(`__main__.py:109:27`); the generator expression over the `islice`
consumes it, calling `DataFileReader.__next__` and, through the
`functools.partial` predicate, `record_match` (`112:63`; the
uncertainties ruling). `argparse`'s `parse_args` calls the types
`csv_arg` and `avro.schema.from_path` (`267:29`).

## Callees outside the package

- Inherited exception constructors: the package's exception classes
  define no `__init__` but `AvroTypeException`,
  `AvroOutOfScaleException` and `SchemaResolutionException`, so a call
  names the first outside `__init__` of the MRO:
  `<builtin>.Exception.__init__`, `<builtin>.UserWarning.__init__`
  (`AvroWarning`, `IgnoredLogicalType`), `<builtin>.RuntimeError.__init__`
  (`UsageError`, `AvroRuntimeException`, whose `RuntimeError` comes first)
  and `<builtin>.NotImplementedError.__init__` (`UnsupportedCodec`).
- `MessageObject()` (a `TypedDict` class): `<builtin>.dict`, because
  typing's `_TypedDictMeta` sets `__call__ = dict` (lead ruling, Codex
  round 1; the trace's `<builtin>.dict.__init__` is rejected). The `namedtuple` classes
  `ValidationNode` and `_ttype`: no edge.
- `os.environ.get`: `collections.abc.Mapping.get`; `randbytes`:
  `random.randbytes`; `hashlib.new`, `hashlib.md5`; the csv writer's
  `writerow`: `_csv.Writer.writerow` on CPython (the exported type,
  `Modules/_csv.c`, 3.10.22 `:1719` to 3.15.2 `:1799`) and
  `_csv.writer.writerow` on PyPy (b8-ruling-c-type-names-1).
- Inherited library methods are named through the receiver's class:
  `http.server.HTTPServer.serve_forever` and `.shutdown`,
  `http.server.BaseHTTPRequestHandler.send_response` on the package's
  handlers, `argparse.ArgumentParser.add_argument`,
  `argparse._SubParsersAction.add_parser`.
- `sys.stdout.flush()`: `io.TextIOWrapper.flush`.

## Open path sets

None.

## Rejected trace edges

10: the 9 `_io.BufferedRandom.*` edges from the tests' append tests (J1), and
`Message.to_json -> <builtin>.dict.__init__`, a naming artefact (AVRO-R1-02).

## Notes for the auditor

- `__main__.convert_union` passes each branch's name (a str) to
  `convert`, whose `field.type` then raises `AttributeError`; for an
  unnamed branch `s.name` raises first. The edges stay.
- `BaseRequestor.request` calls `self.issue_request`, which only
  `Requestor` defines.
- `Field` has `EqualByJsonMixin.__hash__` but no `fingerprint`: hashing a
  Field raises `AttributeError` (no edge to `Schema.fingerprint` from a
  Field).
- `TetherTask.close` tests `self.clienTransciever`, which is always None:
  no callee at `tether_task.py:442:44`.
- `make_avsc_object`'s "Unknown Named Type" raise (`schema.py:1299`) is
  reached only with a client `str` subclass whose comparisons disagree.
- `ErrorUnionSchema` has the type "union", so it cannot be a union
  branch; that limits the branch dispatch sets.
- Name of a value site by name only: `uuid.UUID(datum)`
  (`schema.py:1193`), because `avro.constants` binds `UUID` to a str.

## Open questions

None open. Settled (2026-11-24): Q1 by the lead (CPython 3.10+, PyPy 3.10
and 3.11, Linux; "Versions, implementations and platforms"), Q3 by the
lead (J1 confirmed), Q2 by the referee (b8-ruling-avro-1, J8).

## Audit (`avro.audit.md`)

| Finding | Action |
|---|---|
| F1 | applied: `ErrorUnionSchema.to_json -> UUIDSchema.to_json` removed at `schema.py:956:42` (a UUIDSchema's type is always "string", which lines 954-955 skip); -1 inside |
| F2 | Q2, ruled by the referee (b8-ruling-avro-1), adopted by the lead: the 13 dispatch edges removed, the 17 attribute-derived edges kept (J8); -13 inside |
| F3 | Q1, ruled by the lead: the PyPy names applied, +5 outside (the audit counted 3; the two `_hashlib._OneShotHash.digest` edges of PyPy 3.11 are cited in "PyPy" for the auditor's re-check) |
| W1 | applied: J8's outside count is 8 |
| R1 | for the lead (README wording of B1) |

## Codex round 1

(`selection/batch-8-proposal/codex-audits/round-1/avro.md`.)

| Finding | Outcome |
|---|---|
| AVRO-R1-01 (false): `avro.__main__.main -> <builtin>.RuntimeError.__init__` at `__main__.py:276:33` | Applied: -1 outside. `args` comes from `_parse_args`, whose subparsers are required (line 209; every admitted version takes that branch) and are only `cat` and `write`. argparse stores the exact subcommand name and refuses any other (`_SubParsersAction.__call__`: CPython 3.10.22 `Lib/argparse.py:1198-1212`, the same in 3.11 to 3.15 and in PyPy 3.10 and 3.11), and neither subparser has an argument with the dest `command`. So `main` returns at line 273 or 275, and the `UsageError` call cannot run (B1: a check that cannot fail under the package's own values has no callee; python-barcode). |
| AVRO-R1-02 (ruling): `Message.to_json -> <builtin>.dict.__init__` at `protocol.py:215:36` | Applied by the lead ruling, Codex round 1 (the writer's opinion adopted): `_TypedDictMeta.__call__ = dict` (CPython 3.10.22 `Lib/typing.py:2381`; PyPy 3.11 `lib-python/3/typing.py:3057`) makes `MessageObject()` an explicit call of the builtin class (micro-benchmark, "Instantiation of a builtin or external class"): the edge is `Message.to_json -> <builtin>.dict`; the trace edge to `<builtin>.dict.__init__` is rejected as a naming artefact (rule A). Edge count unchanged. |

## Statistics

| | Count |
|---|---|
| Sites | 3231 (1669 call, 103 decorator, 10 with, 106 iter, 216 op, 270 getitem, 44 setitem, 2 delitem, 651 getattr, 16 setattr, 144 format); 2329 with candidates; 18 value sites |
| Ledger entries | 2152 (2386 callee lines, 446 rejection lines of which 419 `reject *`, 340 notes, no exclusion) |
| Nodes | 458 (19 modules, 439 functions) |
| Edges | 1754: 1050 in the package, 704 outside |
| Confirmed by the trace | 837 of 1754 (47.7%); the trace has 847 edges |
| From reading only | 917 (inside 530, outside 387) |
| Rejected trace edges | 10 |
| Functions that the tests run | 246 of 439 (the `load_tests` cases, the tether modules, `tool`, `__main__` and `ipc`'s transport do not run) |

`check.py --origin avro`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| avro | 847 | 10 | 837 (520 / 317) | 917 (530 / 387) | 1754 (1050 / 704) |
