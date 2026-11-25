**Status (2026-11-24, re-check 2 against `263af5f`):** closed. Every
finding is applied or ruled: F1 (the writer), F3 and Q3 (the lead), F2
(the referee, b8-ruling-avro-1), W1; R1 and R2 are with the lead for the
README. Final graph: 1748 edges (1050 inside, 698 outside); after
Codex round 1 (re-checked against `47ed387`), 1747 (1050 inside, 697
outside); after the C-type names ruling (re-checked against `7d1f3d6`),
1754 (1050 inside, 704 outside).

# avro: blind audit of the ground truth

Release 1.12.2, the PyPI sdist `avro-1.12.2.tar.gz` (SHA-256
`e900e7b5…78fe08`; batch 8). Audited files: `avro.ledger` (6098 lines, 8
default rejection lines with 23 candidates), `avro.json` (458 nodes, 1757
edges: 1064 in the package, 693 outside), `avro.added.json`,
`avro.rejected.json` (9 edges) and `avro.md` (J1 to J10, Q1 to Q3), at the
writer's commit `91618dd` of `b8-gt-avro`. `check.py avro` reports no
errors; `check.py --origin avro` gives 847 trace edges, 9 rejected, 838 in
the graph, 919 added.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with the clarifications, the rulings for
batch 6 and for batch 7, and the naming rules of
`PyCG/micro-benchmark/README.md`. I read the whole analysed source (19
modules), `pyproject.toml`, `PKG-INFO`, `setup.py`, the tests as data
(`avro/test/`), the trace `dynamic/avro.json`, upstream's
`test-lang-py.yml` at `release-1.12.2`
(`deps/upstream-ci/`, SHA-256 `a3bf73c3…590897`), and from the dependency
sources CPython 3.10.22 to 3.15.2 (`Modules/_csv.c`, the hash modules,
`Lib/enum.py`) and PyPy 3.10 v7.3.19 and 3.11 v7.3.23 (`lib_pypy/_sha1.py`,
`_blake2`, `_hashlib`, `_sha3`, `pypy/module/zlib`, `_md5`, `_csv`, `bz2`).
I did not run or import the package and ran no analysis tool on it. I ran
`check.py` (skeleton in a scratch copy, size report, `--report`,
`--report --without-candidates`, `--origin`) and scripts of my own on the
text of the skeleton, the ledger, the graph and the trace, and an `ast`
script for the binding check.

**Final state.** 85 of the 88 sites re-derived blind agree. Of the 3
others, 2 are my errors, 1 is the Q2 ruling case, and one of my errors sits
at a site where the writer also has an edge that cannot happen (F1). The
graph loses 1 inside edge by F1. Q1 (PyPy) adds 3 outside edges if the lead
admits PyPy (F3); Q2 removes 13 to 30 edges depending on the ruling (F2);
Q3 changes nothing. 1 wording finding, 2 remarks on the README.

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | edge that cannot happen (medium) | `ErrorUnionSchema.to_json -> UUIDSchema.to_json` at `schema.py:956:42` | The loop skips every branch with `schema.type == "string"` (`schema.py:954-955`). A `UUIDSchema`'s `type` is the literal `"string"` that `UUIDSchema.__init__` passes (`schema.py:1186` to `PrimitiveSchema.__init__`, `Schema.__init__` sets `self.type`, `:256`); no public API changes `type`. So a UUID branch never reaches `to_json` here. (`UnionSchema.to_json`, `:929:42`, has no such skip: its `UUIDSchema.to_json` stays.) | -1 inside | the writer removes the callee at `956:42` |
| F2 | ruling (Q2; high, many edges) | the calls through `self` in `TetherTask`'s methods and through the task in `TaskRunner` and `TaskRunnerResponder` (J8) | `TetherTask` is abstract by `abc` (`tether_task.py:155`, `367-407`) and documented for subclassing; the package has no subclass. B1: "a class that is abstract by abc ... is not [a receiver], and the client's subclasses are client code" (asyncstdlib: `_recreate_cm` is no callee at `contextlib.py:103`). See "For the lead" | -13 inside (dispatch only), or -22 inside and -8 outside (dispatch and attributes) | for the lead; referee if it decides 10 or more edges |
| F3 | ruling (Q1; low) | PyPy names | upstream's `test-lang-py.yml` (release-1.12.2) runs `pypy-3.10` and `pypy-3.11` beside CPython 3.10 to 3.14, on `ubuntu-latest` and `ubuntu-24.04-arm`. If PyPy is admitted: `Schema.fingerprint -> _sha1.sha.digest` (PyPy's fallback `_sha1.sha1()` returns an instance of `class sha`, `lib_pypy/_sha1.py:129`, `:359-368`, in both PyPy releases), and `DeflateCodec.decompress -> zlib.decompressobj.decompress`, `-> zlib.decompressobj.flush` (PyPy's `zlib` exports the Decompress type itself as `decompressobj`, `pypy/module/zlib/moduledef.py:30`; its typedef has no module, `interp_zlib.py:399`). The other implementation-specific names are the same on PyPy: `_csv.writer` (`pypy/module/_csv/interp_writer.py:172`), `_md5.md5` (`pypy/module/_md5/moduledef.py`), `_hashlib.HASH`, `_blake2.blake2b`/`blake2s`, `_sha3.sha3_*`, `_sha256.*`, `_sha512.*`, `_bz2.BZ2Decompressor` (named `bz2.BZ2Decompressor`); PyPy's pure-Python `datetime` calls the same tzinfo methods (J7) | +3 outside | for the lead (my opinion below) |
| W1 | wording (low) | `avro.md` J8 | "9 outside edges (`logging.Logger`, `threading.Event`)" go if client subclasses are not receivers: the graph has 8 such edges (`TetherTask.open`, `.close` to `Logger.info`; `.input`, `.complete` to `Logger.warning`; `.fail` to `Logger.error` and `Logger.exception`; `.close` to `Event.set`; `TaskRunner.start` to `Event.wait`) | 0 | the writer corrects the count, after the ruling |
| R1 | README (low) | B1 | B1 lists as receivers "a subclass that calls the method explicitly on itself (`Cache.__setitem__(self, ...)`, `super()`)" and, two sentences later, says that the client's subclasses of an abstract documented base are client code. The writer read the first clause as covering a client subclass that calls `TetherTask.__init__` (J8). The README could say that the first clause concerns package subclasses | 0 (13 to 30 through F2) | for the lead |
| R2 | README (low) | "Versions and configuration", the textdistance ruling | avro is held as its sdist, which leaves out `.github/`. The README does not say whether the release's own test jobs are read at the release tag when the analysed artefact omits them (Q1) | 0 (3 through F3) | for the lead |

## Step 1: blind re-derivation

**Skeleton.** `projects.toml` and `projects/avro` copied (`cp -R`) to a
scratch directory, `check.py --benchmark-dir <scratch> --skeleton avro`:
3231 sites (1669 call, 103 decorator, 10 with, 106 iter, 216 op, 270
getitem, 44 setitem, 2 delitem, 651 getattr, 16 setattr, 144 format), 2329
with candidates, 18 value sites. Twenty-five candidates sit at 50 or more
sites (seven `__eq__` at 538, three `__hash__` at 380, the two
`DataFileReader` iteration methods, `Message.errors` at 176, five `__str__`
at 172, `_DataFileMetadata.schema` at 123, four `name` properties at 70,
`AvroTypeException.__init__` at 60, `Names.__init__` at 56).

**Sample, drawn by kind.** No kind dominates (explicit sites are 1772 of
3231, 55 %), so the 70 are split in that proportion: 38 explicit and 32
implicit, drawn with one `random.Random(20261124)` over the sites numbered
by (module in skeleton order, line, column), then the 18 value sites (none
drawn): 88 sites. The draw script, the sample and my answers are in
`selection/batch-8-proposal/audits/avro/` (`draw.py`, `sample.txt`,
`blind-answers.md`), committed as `daad9b2` before I opened any file of the
writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator) | 38 | 36 | 2 (`schema.py:956:42`, `tether_task.py:439:22`) |
| Implicit (10 getattr of a module, 7 other getattr, 6 getitem, 4 iter, 3 format, 2 op) | 32 | 32 | 0 |
| Value sites | 18 | 17 | 1 (`schema.py:552:33`) |
| **Total** | **88** | **85** | **3** |

The 3 disagreements, classified:

- **`schema.py:956:42` (`ErrorUnionSchema.to_json`): my error and a
  writer's edge that cannot happen.** I accepted
  `ErrorUnionSchema.to_json` for a nested `{"type": "error_union"}` branch;
  but an `ErrorUnionSchema` has the type `"union"` (`UnionSchema.__init__`
  calls `Schema.__init__(self, "union", ...)`, `schema.py:886`), which a
  union refuses as a branch (`:905`). The writer accepted
  `UUIDSchema.to_json`, which the `"string"` skip excludes (F1). The other
  13 callees agree.
- **`schema.py:552:33` (`validator(datum)`): my error.** I rejected the
  default `PrimitiveSchema.validate.<lambda1>`. `Schema.__init__` annotates
  `type_: str`, and an admitted client `str` subclass that keeps `str`'s
  equality but defines its own `__hash__` passes `type not in
  PRIMITIVE_TYPES` (`:512`) and misses the dict lookup (`:551`): the
  python-barcode and segno (`b7-ruling-segno-2.md`) precedents admit such
  subclasses. I had seen the witness and set it aside; the writer's J6 is
  right.
- **`tether_task.py:439:22` (`self.log.info` in `TetherTask.close`): the Q2
  ruling case.** I wrote no callee (the client's subclass instance is
  client code, and `log` is its attribute); the writer has
  `logging.Logger.info` (J8). See F2.

My conventions, written before I read the ledger, are the writer's:
`<builtin>.UserWarning.__init__` for `AvroWarning`; no edge for the
`namedtuple` classes `ValidationNode` and `_ttype`; `_csv.writer.writerow`
for `_write_row`; `avro.timezones.UTCTzinfo.utcoffset` at
`__main__.py:71:15` (the csv writer converts a decoded aware `datetime` with
`str()`); `io.TextIOWrapper.read` for the protocol files; the segno ruling
for the streams, with the CLI's `argparse.FileType` files and standard
streams as package streams; Python 3.10 and later for the version branches.

## Step 2: exhaustive checks

**Dispatch sets.** I listed every site with three or more package callees
(27 sites) and checked each set against the class hierarchy:

- `to_json` (16 classes): `Schema.__str__` (`:269:39`), `Field.to_json`
  (`:478:44`), `ArraySchema.to_json` (`:804:47`), `MapSchema.to_json`
  (`:857:60`), `Message.to_json` (`protocol.py:219:52`): any schema, error
  unions included (a field, item, value or response can be
  `{"type": "error_union"}`). `UnionSchema.to_json` (`:929:42`): 14, no
  union and no error union. `ErrorUnionSchema.to_json` (`:956:42`): 14 with
  `UUIDSchema` (F1). `Protocol.to_json` (`protocol.py:143:36`): the four
  named classes.
- `to_canonical_json` (7: the logical classes inherit `PrimitiveSchema`'s,
  `FixedDecimalSchema` `FixedSchema`'s, `ErrorUnionSchema` `UnionSchema`'s)
  and 6 at `UnionSchema.to_canonical_json`; `match` (7, and 6 for union
  branches); `validate` (15, and 14 for union branches): correct.
- `codec.compress` and `codec.decompress` (`datafile.py:242:69`,
  `387:47`): the five codec classes, the snappy and zstandard ones by the
  optional-import rule; correct.
- `self.invoke` (`ipc.py:310:39`): `Responder`, `GenericResponder`,
  `TaskRunnerResponder`; correct (`Responder` is a plain public class).
- The value sites: as in Step 1.

**Default rejections.** 8 lines, 23 candidates, 6616 candidate-site pairs.
I read every explicit site that each default decides (`--report`), and the
places where the package compares, hashes, iterates, formats or converts
an object that has one of these methods: the memo dict of
`ReaderWriterCompatibilityChecker` (`compatibility.py:156-163`, accepted),
`Message.__eq__` (`protocol.py:226:64`, accepted), `EqualByPropsMixin.__eq__`
(`schema.py:226:54`, J4), the iteration of a `DataFileReader`
(`__main__.py:109:27`, `112:63`, `tool.py:124:39`, `132:25`, `141:25`,
accepted), `str()` of schemas and protocols (accepted at every such site),
the `errors`, `schema` and `name` loads on Messages, data files and named
objects (accepted). The other sites compare and hash strs, `SchemaType`
members (`str`'s `==` and hash come first in the MRO; `Enum.__hash__`,
`enum.py`, comes later), bytes, ints, tuples and JSON values. No default
hides a call.

**Functions that no site calls.** 59 keys have no in-edge: the 19 modules
and 40 functions. Each is justified: unused public API
(`ReaderWriterCompatibilityChecker.__init__`, `DataFileWriter.sync`,
`BinaryDecoder.read_null`, `HTTPTransceiver.close`, `Name.get_space`,
`Protocol.fullname`, the `doc`, `precision` and `scale` properties,
`PropertiesMixin.other_props`, `TaskRunner.server`, `TetherTask.status`,
`.count`, `Collector.collect`), comparisons and hashes that only clients
make (`Name.__eq__`, `Message.__eq__`, `Message.__str__`,
`Protocol.__eq__`, the two mixins' `__hash__`), abstract methods
(`Schema.*`, `Codec.*`, `TetherTask.map`, `.reduce`, `.reduceFlush`),
`TetherTask.__init__` (only a client subclass calls it), the tzinfo methods
that no admitted call reaches (`TSTTzinfo.dst`, both `tzname`; `astimezone`
calls only the target's `dst`), `utils._randbytes` (every admitted version
has `random.randbytes`) and `io._max_collection_items` (only the tests
call it).

**Special methods and properties.** The 17 sites with package callees that
are not candidates (`--report`) are call-backs: the lazy filter of
`print_avro` (J10), `parse_args` calling `csv_arg` and `from_path`, the
tzinfo call-backs (J7), `getattr`/`hasattr` of `fullname`, `size` and
`props`, the handler `__init__` and `do_POST` of the package-started
servers (J9), and `Thread.start` running `thread_run`. All hold. The
property loads and stores of `datafile.py`, `io.py` and `ipc.py` that I
read (codec and schema setters, `writers_schema` setters, `remote_protocol`
and `send_protocol`) name the right accessor node.

**Rejections and notes.** I read the 329 notes and the rejections at the
sites with a note on a missing or opaque callee: the append branch of
`DataFileWriter.__init__` (client streams only), the stream notes, the
two-argument `AvroTypeException` (the unpacking at `errors.py:73` raises
first), `clienTransciever` (always `None`), the version branches of
`add_subparsers`, the tzinfo class calls (no `__init__` in the MRO). All
hold. J3 and J4 rest on a client's `other_props`; `Schema.__init__`
annotates it `Optional[Mapping[str, object]]`, and B3 says that "where an
annotation exists, it decides": I agree with both (see the judgement
calls).

**Callees outside the package.** 219 names. I checked each against the
micro-benchmark rules and the dependency sources: the hash classes of J5
per CPython version (`Modules/` of 3.10.22 to 3.15.2), `_csv.writer`
(`.name = "_csv.writer"` in every version), `zlib.Decompress`,
`bz2.BZ2Decompressor` (listed in `bz2.__all__`), `socketserver._SocketWriter`
(`wbufsize` 0), `io.FileIO` for `sys.stdout.buffer` under `-u`,
`pathlib.PosixPath.read_text` (Linux), the missing-module paths of snappy
and zstandard (`zstandard.ZstdDecompressor.stream_reader.read` through the
`with` stub). All are right for CPython on Linux; F3 lists the PyPy names.

**Rejected trace edges.** 9, all `_io.BufferedRandom.*` from the append
tests of `test_datafile.py`: client streams at `IO[AnyStr]` parameters
(Q3). I agree. **Trace edges that the graph lacks:** none.

**Implicit sites without candidates.** 2655 (`--report
--without-candidates`). The package builds one lazy object that library
code consumes (`filter(predicate, data_file_reader)`, `__main__.py:109`;
J10) and hands generators to `csv.reader` and `str.join`, whose code is the
package's own; the library call-backs (csv, datetime, http.server,
threading, argparse) are in the ledger. Nothing is missing.

## Step 3: binding check

An `ast` script matched every call site of the ledger with a package
callee (959 site-callee pairs) to the callee's `def` and bound the call's
arguments. 885 bind. 11 were flagged: 9 are calls on the module constants
`HANDSHAKE_*` and `META_*`, which my script took for classes (they are
`DatumReader` and `DatumWriter` instances, and the bound calls fit
`read(self, decoder)` and `write(self, datum, encoder)`), and 2 pass
`*args` (`errors.py:91`, `tether_task.py:152`) and bind any arity. The 12
lambda callees and the 51 call-backs and value calls I checked by hand
(the iterators, printers, readers, `schema_type` targets, validators,
`csv_arg` and `from_path`, `thread_run`, `do_POST`, the tzinfo methods).
No call fails to bind; the writer's shake case (`h.digest()` without a
length, J5) is right to have no edge.

## The writer's judgement calls

- **J1 (client streams).** Agree: the segno ruling, as I wrote blind.
- **J2 (`SchemaType` members as types).** Agree. `test_compatibility.py:38-51`,
  `136-158`, `402-427` pass members to the public constructors; the
  members' `__str__` runs through `Enum.__format__` and `!s`. Nearest rule:
  B2, the test clause.
- **J3 (`_safe_pretty` returns the schema).** Agree. `other_props` is
  annotated `Mapping[str, object]`, which admits a value that `json` cannot
  serialize; B3's "where an annotation exists, it decides" keeps it.
- **J4 (`EqualByPropsMixin.__eq__` compares props).** Agree, with a
  remark: the witness needs a primitive whose `other_props` hold reserved
  keys and a non-props schema on the right. `Mapping[str, object]` admits
  the keys (B3, the annotation decides), and `Schema.__eq__`'s docstring
  ("Determines how two schema are compared", `schema.py:310-314`) makes
  every schema an admitted right operand of every schema's `__eq__`, not
  only the same kind that the tests compare.
- **J5 (hash objects).** Agree for CPython (type names checked in
  `Modules/`). With PyPy, `_sha1.sha.digest` is added (F3).
- **J6 (the default validator).** Agree (my blind error).
- **J7 (tzinfo call-backs).** Agree; I found the `print_csv` case blind.
  The `datetime` C code (`datetime_astimezone`, `tzinfo_fromutc`) and the
  pure-Python one call the same methods.
- **J8 (`TetherTask`).** Disagree: see F2 and "For the lead".
- **J9 (package-started servers).** Agree (the prometheus-client ruling).
- **J10 (the lazy filter).** Agree (the uncertainties ruling).

## For the lead

1. **Q1, platforms and implementations (F3, 3 outside edges).** My
   opinion: CPython 3.10 to 3.14 (3.15 too: the final classifier is no
   upper bound) and PyPy 3.10 and 3.11, on Linux, x86-64 and aarch64. The
   sdist has no CI file and no OS or implementation classifier, but it is
   built from the tag `release-1.12.2`, whose `test-lang-py.yml` is the
   release's own test job for `lang/py`, the directory the sdist packages
   (the README records the checkout root `lang/py` and the frame's `ci`
   filter read the workflows at that tag). By "Implementation, version and
   platform combinations" (path: "A CI job is evidence of support"; a PyPy
   job admits PyPy) the `pypy-3.10` and `pypy-3.11` jobs admit PyPy under
   the `>=3.10` bound; by the textdistance ruling the jobs' `ubuntu-*`
   runners make Linux the only platform, and the einops ruling keeps both
   architectures. The 3 PyPy names are in F3; the platform keeps the
   writer's `PosixPath` names.
2. **Q2, `TetherTask` (F2).** My opinion: the client's subclass instances
   are not receivers. B1's sentence on documented bases is the specific
   rule: an abstract base "is not [a receiver], and the client's
   subclasses are client code"; asyncstdlib applies it to a concrete
   method that the client's subclass inherits (`_recreate_cm`, no callee
   at `contextlib.py:103`), which is the case of `self.fail()`,
   `self.close()` and the task calls of `TaskRunner` and
   `TaskRunnerResponder`. The clause "a subclass that calls the method
   explicitly on itself" names package subclasses (cachetools) and does
   not turn client code into a receiver (R1). Then `self` in `TetherTask`'s
   methods is a client object, and by B5 a call on one of its attributes
   (`self.log`, `self.outputClient`, `self.inReader`, `self.midReader`,
   `self.midschema`, `self.ready_for_shutdown`, and `TaskRunner`'s
   `self.task.ready_for_shutdown`) has no callee; `Collector.collect`'s
   `outputClient`, which only `configure` passes from the task, is then
   no admitted `HTTPRequestor` either. Edges: 13 inside (to `fail`,
   `close`, `open`, `configure`, `input`, `complete`, `partitions`), 9
   more inside (`HTTPRequestor.request` from `open`, `complete`, `status`,
   `count`, `fail` and `Collector.collect`; `DatumReader.read` from
   `input`; `RecordSchema.fields` and `Field.order` from `configure`) and
   8 outside (W1): 30 edges. A middle reading (dispatch only; attributes
   that `TetherTask`'s own code sets are package values) removes the 13.
   The case decides 13 to 30 edges: by the brief, a referee case.
3. **Q3, `io.BufferedRandom` at `IO[AnyStr]` (0 edges).** My opinion: the
   segno ruling applies. `IO[AnyStr]` and `IO[bytes]` are abstract stream
   annotations (B4); the tests' files are outside objects that the client
   passes (B5); and unlike segno, no document of avro names a concrete
   stream class, so the case is plainer. The 9 trace edges stay rejected,
   and the `io.BufferedReader`, `io.BufferedWriter` and `io.FileIO` edges
   stay because the package's own CLI makes those streams.

## Re-check 1 (the writer's commit `59133af`)

The lead's rulings of 2026-11-24: F1 applied; Q1 as proposed (CPython 3.10
and later, PyPy 3.10 and 3.11, Linux x86-64 and aarch64; R2 goes to the
README); Q3 confirmed; W1 fixed; Q2 sent to the Codex referee.

`check.py avro`: no errors, 1761 edges (1063 inside, 698 outside).
`check.py --origin avro`: 847 trace edges, 9 rejected, 838 in the graph,
923 added (543 / 380). Between `91618dd` and `59133af` the graph has the
same 458 nodes; one edge goes and five come:

| Finding | Change in the graph | Verdict |
|---|---|---|
| F1 | `ErrorUnionSchema.to_json -> UUIDSchema.to_json` removed (`schema.py:956:42`; the `reject *` reason names the `"string"` skip) | closed |
| F3 | `DeflateCodec.decompress -> zlib.decompressobj.decompress`, `-> zlib.decompressobj.flush` (`codecs.py:208:52`, `214:43`); `Schema.fingerprint -> _sha1.sha.digest` (`schema.py:338:24`) | closed: the three names of the audit |
| F3 | `Schema.fingerprint -> _hashlib._OneShotHash.digest` (`schema.py:338:24`) and `Protocol.__init__ -> _hashlib._OneShotHash.digest` (`protocol.py:108:59`), which the audit missed | closed: both are right (below) |
| W1 | `avro.md` J8 counts 8 outside edges, listed | closed |
| Q3 | `avro.rejected.json` unchanged (9 edges); J1 cites the ruling | closed |
| F2 | J8 unchanged, marked as waiting for the referee | open |

**The two `_OneShotHash` edges, from the PyPy 3.11 v7.3.23 sources.**
`lib-python/3/hashlib.py` binds `new = __hash_new` when `_hashlib` imports
(`:169-172`); `__hash_new` passes every name but `blake2b` and `blake2s`
(`__block_openssl_constructor`, `:78-80`) to `_hashlib.new(name, data)`
(`:160`). In `lib_pypy/_hashlib/__init__.py`, `new` returns a
`_OneShotHash(...)` when `string` is not empty and `EVP_Digest` succeeds
(`:40-52`); the class is defined at `:57` in the module `_hashlib`, and its
`digest` (`:79-82`) takes no argument, so `h.digest()` binds.
`Schema.fingerprint` passes `self.canonical_form.encode("utf-8")`, never
empty (`schema.py:327`, `:337`): `schema.py:338:24` reaches
`_hashlib._OneShotHash.digest`. `hashlib.md5` is
`__get_openssl_constructor("md5")` (`hashlib.py:303-307`, the function at `:126`), which returns
`_hashlib.openssl_md5`; that function is `make_new_hash("md5", ...)`'s
`new_hash` (`_hashlib/__init__.py:367-374`, for each name of `_algorithms`,
`:294`), which calls `new(name, string)`. `Protocol.__init__` passes the
encoded JSON of the protocol, never empty (`protocol.py:108`), so
`protocol.py:108:59` reaches the same method. The name follows the rule for
a private class of a library (`argparse._StoreTrueAction.__call__`). PyPy
3.10 v7.3.19 has no `_OneShotHash`: its `new` makes a `_hashlib.HASH`
(`__init__.py:40-43`, class `:57`), the name that the graph already has. Where
`EVP_Digest` succeeds for a shake name, PyPy 3.11 makes a `_OneShotHash`
too, whose `digest()` binds: no further name.

**Nothing else changed.** The ledger diff has only these entries, their
notes and the rewritten `reject *` reason at `schema.py:956:42`; the new
"PyPy" section of `avro.md` matches the names that I read in the PyPy
sources for the audit (F3), and its statement on `datetime` agrees with
`lib-python/3/datetime.py` of PyPy 3.11 (`astimezone` calls the source
tzinfo's `utcoffset` before it tests `tz is mytz`, `:1996-2012`; the callee
is already in the graph).

Open after re-check 1: F2 (Q2), with the referee.

## Re-check 2 (the writer's commit `263af5f`)

The referee's ruling `b8-ruling-avro-1` (Codex, adopted by the lead,
`selection/batch-8-proposal/rulings/b8-ruling-avro-1.md`) takes the middle
reading of Q2: the 13 dispatch edges go, the 17 attribute-derived edges
stay, none is added.

`check.py avro`: no errors, 1748 edges (1050 inside, 698 outside).
`check.py --origin avro`: 847 trace edges, 9 rejected, 838 in the graph,
910 added (530 / 380). Between `59133af` and `263af5f`:

- **The graph** has the same 458 nodes and loses exactly the ruling's 13
  inside edges, adds none: `TetherTask.open`, `.configure`, `.input`,
  `.complete -> TetherTask.fail`; `TetherTask.fail -> TetherTask.close`;
  `TaskRunnerResponder.invoke -> TetherTask.configure`, `.partitions`,
  `.input`, `.complete`, `.close`, `.fail`; `TaskRunner.start ->
  TetherTask.open`; `TaskRunner.close -> TetherTask.close`.
- **The ledger** changes only at the ruling's 13 sites
  (`tether_task.py:266:22`, `304:22`, `351:22`, `363:26`, `436:19`;
  `tether_task_runner.py:64:36`, `68:31`, `74:32`, `80:35`, `81:32`,
  `89:27`, `193:23`, `209:24`): each has no callee, a `reject *` and a note
  that cite b8-ruling-avro-1.
- **The 17 kept edges** are in the graph, at the 18 sites of the ruling's
  tables (`HTTPRequestor.request` from `Collector.collect`, `open`,
  `complete`, `status`, `count`, `fail`; `DatumReader.read` from `input`
  at `331:50` and `341:57`; `RecordSchema.fields` and `Field.order` from
  `configure`; the six `logging.Logger` edges; `threading.Event.set` and
  `TaskRunner.start -> threading.Event.wait`).
- **The abstract sites** `tether_task.py:334:29`, `345:41`, `346:32` and
  `359:33` still have no callee.
- **`avro.md`**: J8 is rewritten after the ruling, with the 13 sites and
  the 17 edges and their assignment evidence; the status, the open
  questions, the audit table and the statistics follow. `avro.rejected.json`
  is unchanged (9 edges). Nothing else changed.

Remark, no change needed: the `reject *` reason at `tether_task_runner.py:193:23`
and `209:24` mentions the `weakref.proxy` of `TaskRunnerResponder`, which
those two `TaskRunner` sites do not use; the reason holds without it.

Nothing is open.

## Codex round 1 re-check (the writer's commits `7a69359`, `fe2c156`, `47ed387`)

The findings are `selection/batch-8-proposal/codex-audits/round-1/avro.md`
(1 false edge, 1 ruling); the writer's answers are `avro.md`, "Codex round
1". The `_csv.writer` and `_sha256.*` names wait for the pending referee
ruling on C-type naming and are not checked here.

`check.py avro`: no errors, 1747 edges (1050 inside, 697 outside).
`check.py --origin avro`: 847 trace edges, 10 rejected, 837 in the graph,
910 added (530 / 380). Between `263af5f` and `47ed387` the graph keeps its
458 nodes, loses `avro.__main__.main -> <builtin>.RuntimeError.__init__`
and `avro.protocol.Message.to_json -> <builtin>.dict.__init__`, and gains
`avro.protocol.Message.to_json -> <builtin>.dict`. The ledger changes only
at `__main__.py:276:33` and `protocol.py:215:36`; `avro.rejected.json` adds
only the one trace edge below; `avro.audit.md` is untouched.

| Finding | Verdict |
|---|---|
| AVRO-R1-01 (false): `main -> <builtin>.RuntimeError.__init__` at `__main__.py:276:33` | Agree. `_parse_args` makes the subparsers required (`__main__.py:209`; every admitted version takes the `>= (3, 7)` branch) and registers only `cat` and `write` (`:210`, `:255`); no argument of either subparser has the dest `command`, and nothing sets a default for it. An unknown name fails the choices check or the lookup in `_SubParsersAction.__call__` (CPython 3.10.22 `Lib/argparse.py:1196-1212`, the same code in 3.11 to 3.15 and in PyPy 3.10 and 3.11, `lib-python/3/argparse.py:1198`, `:1223`), whose `ArgumentError` `parse_args` turns into an exit. So `args.command` is `"cat"` or `"write"`, `main` returns at `:273` or `:275`, and the `UsageError` at `:276` never runs: a check that cannot fail under the package's own values (B1). The note says so. -1 outside |
| AVRO-R1-02 (ruling): `protocol.py:215:36`, `MessageObject()` | Agree with the lead's ruling. `MessageObject` derives from `TypedDict` (`protocol.py:39`, through `avro/utils.py:28`), whose metaclass `_TypedDictMeta` sets `__call__ = dict` in every admitted runtime (CPython `Lib/typing.py:2381` in 3.10.22, `:3057` in 3.11.18, `:2966` in 3.12.16, `:3257` in 3.13.18, `:3275` in 3.14.10, `:3307` in 3.15.2; PyPy `lib-python/3/typing.py:2381` in 3.10, `:3057` in 3.11). The call is a call of the builtin class `dict`, named `<builtin>.dict` (micro-benchmark, "Instantiation of a builtin or external class"); the trace's `<builtin>.dict.__init__` is a naming artefact, rejected with that reason (rule A). Net 0 edges |

No disagreement. The audit stays closed.

## C-type names re-check (the writer's commit `7d1f3d6`)

The ruling `b8-ruling-c-type-names-1` (the referee, adopted by the lead):
an explicit outside method is named by the exported type attribute of the
defining module where the runtime has one, else by the type name, per
admitted implementation and version, as a union without two aliases for
one class on one runtime. Dependency paths below are relative to
`selection/batch-8-proposal/deps/`.

`check.py avro`: no errors, 1754 edges (1050 inside, 704 outside).
`check.py --origin avro`: 847 trace edges, 10 rejected, 837 in the graph,
917 added (530 / 387). Between `47ed387` and `7d1f3d6` the graph keeps its
458 nodes and changes exactly as the ruling's avro table says: it loses
`Schema.fingerprint -> _sha1.sha1.digest` and gains `_csv.Writer.writerow`
from `print_csv` (`__main__.py:71:15`) and `print_avro` (`:117:23`),
`_md5.MD5Type.digest` from `Protocol.__init__` (`protocol.py:108:59`), and
`_md5.MD5Type.digest`, `_sha1.SHA1Type.digest`, `_sha256.SHA224Type.digest`,
`_sha256.SHA256Type.digest`, `_sha512.SHA384Type.digest` from
`Schema.fingerprint` (`schema.py:338:24`). The ledger changes only at those
four sites (callees and notes); `avro.rejected.json` is unchanged (10
edges); `avro.md` follows (J5, "PyPy", "Callees outside the package", the
statistics); `avro.audit.md` is untouched.

| Name | Runtimes | Source | Verdict |
|---|---|---|---|
| `_csv.Writer.writerow` | CPython 3.10 to 3.15 | `Modules/_csv.c`: the writer type is added as `"Writer"` (3.10.22 `:1717-1719`, 3.11.18 `:1753`, 3.12.16 `:1776`, 3.13.18 `:1760`, 3.14.10 and 3.15.2 `:1799`) | right |
| `_csv.writer.writerow` (kept) | PyPy 3.10, 3.11 | `pypy/module/_csv/moduledef.py`: the module exports the factories `reader` and `writer` and `Dialect`, no writer type; the TypeDef is `'_csv.writer'` | right |
| `_md5.MD5Type.digest` | CPython | `Modules/md5module.c`: `"MD5Type"` (3.10.22 `:591`, 3.11.18 `:594`, 3.12.16 `:355`, 3.13.18 `:369`, 3.14.10 `:381`, 3.15.2 `:358`) | right, at both sites |
| `_md5.md5.digest` (kept) | PyPy | `pypy/module/_md5/moduledef.py:22` exports the type as `md5` | right |
| `_sha1.SHA1Type.digest` | CPython | `Modules/sha1module.c`: `"SHA1Type"` (3.10.22 `:568-570`, 3.15.2 `:353-355`, the same in between) | right |
| `_sha1.sha.digest` (kept); `_sha1.sha1.digest` removed | PyPy | `lib_pypy/_sha1.py:129` defines `class sha`; `sha1` (`:359`) is a factory. No runtime has a class at `_sha1.sha1` | right |
| `_sha256.SHA224Type.digest`, `_sha256.SHA256Type.digest` | CPython 3.10, 3.11 | `Modules/sha256module.c`: 3.10.22 `:720`, `:725`; 3.11.18 `:723`, `:728` | right |
| `_sha256.sha224.digest`, `_sha256.sha256.digest` (kept) | PyPy | `lib_pypy/_sha256.py:242`, `:218` | right |
| `_sha512.SHA384Type.digest` | CPython 3.10, 3.11 (the SHA-512 object) | `Modules/sha512module.c` adds the SHA-384 type as `"SHA384Type"` and then the SHA-512 type under the same name (3.10.22 `:782`, `:788`; 3.11.18 `:785`, `:791`): the attribute ends at the SHA-512 type | right |
| `_sha512.sha384.digest` (kept) | CPython 3.10, 3.11 (no export left) and PyPy | `sha512module.c` as above; `lib_pypy/_sha512.py:269` | right |
| `_sha512.sha512.digest` (kept) | PyPy | `lib_pypy/_sha512.py:245` | right |
| `_sha2.SHA224Type` to `_sha2.SHA512Type` `.digest` (kept) | CPython 3.12 to 3.15 | `Modules/sha2module.c`: `PyModule_AddType` of the four types, whose type names are `_sha2.SHA*Type` (3.12.16 `:852-861`, 3.15.2 `:864-873`) | right |

**The other names of C types in the graph**, checked for an exported
attribute that differs from the name used: `_hashlib.HASH` (the module adds
the type with `PyModule_AddType`, `Modules/_hashopenssl.c`, 3.10.22 `:2143`,
3.15.2 `:2787`; PyPy's `class HASH`), `_sha3.sha3_*` (added with
`PyModule_AddType` under their type names; PyPy's classes of the same
names), `_blake2.blake2b`, `blake2s` (likewise; PyPy sets the same names),
`bz2.BZ2Decompressor` (the public alias), `zlib.Decompress` (CPython's
`zlibmodule.c` exports no Compress or Decompress type, only
`_ZlibDecompressor` from 3.12, another class: the type name is the
fallback) beside PyPy's `zlib.decompressobj` (the type itself), `struct.Struct`,
`re.Pattern`, `collections.deque` and the `io` classes (public aliases).
The Python classes (`_hashlib._OneShotHash`, `socketserver._SocketWriter`,
`http.client.HTTPResponse`, `argparse._SubParsersAction`) are named where
defined. No other avro site names a type whose module exports it under
another attribute, and no runtime gets two names for one class.

No disagreement. The audit stays closed.
