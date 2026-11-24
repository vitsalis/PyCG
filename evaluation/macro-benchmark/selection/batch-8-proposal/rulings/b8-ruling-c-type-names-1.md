The dispute is whether an explicit outside-method edge uses a C type’s
exported module attribute or its `tp_name` when those differ, and whether
older ground-truth usage overrides the naming rules.

**The exported type attribute takes precedence, separately for each
admitted implementation and version.** Use a public class alias when
available; otherwise use the defining extension module’s exported type
attribute, such as `_csv.Writer` or `_sha256.SHA256Type`, even though the
module starts with `_`. A factory function names its own invocation, not
methods of its result. Use the defining-module/type-name fallback only
where that runtime provides no such type path. Take the union across
admitted runtimes, retaining a fallback only where needed and never adding
two aliases for one class on the same runtime.

This follows the [micro-benchmark naming rules](PyCG/micro-benchmark/README.md:69)
and the [outside-name and version clarifications](macro-benchmark/README.md:2249).
**Flit-core’s changes at `0fa844a` conform.**

Dependency references below are relative to
`macro-benchmark/selection/batch-8-proposal/deps/`.

| Receiver and runtime | Class name | Dependency evidence |
|---|---|---|
| CSV writer, CPython 3.8–3.9 | `_csv.writer`, fallback | `cpython/3.8.20/Modules/_csv.c:1330`, initializer `:1626`; 3.9.25 `:1376`, initializer `:1670`: no writer-type export |
| CSV writer, CPython 3.10–3.15 | `_csv.Writer` | `Modules/_csv.c`: 3.10.22 `:1719`, 3.11.18 `:1753`, 3.12.16 `:1776`, 3.13.18 `:1760`, 3.14.10 and 3.15.2 `:1799` |
| SHA-224/256, CPython 3.8–3.11 | `_sha256.SHA224Type`, `_sha256.SHA256Type` | `Modules/sha256module.c`: 3.8.20 `:724`, `:726`; 3.9.25 `:718`, `:720`; 3.10.22 `:720`, `:725`; 3.11.18 `:723`, `:728` |
| MD5, admitted CPython versions | `_md5.MD5Type` | `cpython/3.10.22/Modules/md5module.c:591`; export persists through 3.15.2 `:358` |
| SHA-1, admitted CPython versions | `_sha1.SHA1Type` | `cpython/3.10.22/Modules/sha1module.c:569`; export persists through 3.15.2 `:354` |

There is a material SHA-512 exception in the supplied sources.
[CPython 3.10.22](macro-benchmark/selection/batch-8-proposal/deps/cpython/3.10.22/Modules/sha512module.c:782)
exports `sha384_type` as `SHA384Type`, then overwrites that attribute with
`sha512_type` at line 788; 3.11.18 does the same at lines 785 and 791.
`PyModule_AddObject` ultimately uses `PyDict_SetItemString`
(`cpython/3.11.18/Python/modsupport.c:661`, `:675`). Therefore **SHA-512’s
path is `_sha512.SHA384Type` in those sources**, while SHA-384 retains
`_sha512.sha384` because its export was overwritten. Adding
`_sha512.SHA512Type` for those versions would invent an attribute.

Avro also admits PyPy 3.10 and 3.11. In both supplied PyPy trees:

| Receiver | Name retained | Dependency evidence |
|---|---|---|
| CSV writer | `_csv.writer` fallback | `pypy/module/_csv/moduledef.py:73–87` exports factories only; `interp_writer.py:173` / `:186` supplies the type name |
| MD5 | `_md5.md5` | `pypy/module/_md5/moduledef.py:22` exports the type itself |
| SHA-224/256 | `_sha256.sha224`, `_sha256.sha256` | Actual classes at `lib_pypy/_sha256.py:242`, `:218` |
| SHA-384/512 | `_sha512.sha384`, `_sha512.sha512` | Actual classes at `lib_pypy/_sha512.py:269`, `:245` |
| SHA-1 | `_sha1.sha` | Class at `lib_pypy/_sha1.py:129`; `sha1` at `:359` is a factory |

The following changes are relative to shared commit `dce3eb7`. Every table
row specifies a caller-to-callee edge; coordinates reproduce the ledgers.

For **flit-core**, source paths are relative to
`macro-benchmark/projects/flit-core/flit_core/flit_core/`, and callers below
have prefix `flit_core.`. The [ledger](macro-benchmark/ground-truth/flit-core.ledger:337)
records these sites.

| Site | Caller | Remove | Add |
|---|---|---|---|
| `common.py:308:23` | `common.hash_file` | `_sha256.sha256.hexdigest` | `_sha256.SHA256Type.hexdigest` |
| `wheel.py:143:31` | `wheel.WheelBuilder._add_file` | `_sha256.sha256.update` | `_sha256.SHA256Type.update` |
| `wheel.py:147:55` | `wheel.WheelBuilder._add_file` | `_sha256.sha256.digest` | `_sha256.SHA256Type.digest` |
| `wheel.py:165:55` | `wheel.WheelBuilder._write_to_zip` | `_sha256.sha256.digest` | `_sha256.SHA256Type.digest` |
| `wheel.py:209:32`, `211:28` | `wheel.WheelBuilder.write_record` | — | `_csv.Writer.writerow` |

Receiver construction is at `common.py:307` and `wheel.py:137`, `:164`,
`:207`. Flit-core admits CPython 3.8+, so both CSV sites retain
`_csv.writer.writerow` for 3.8–3.9. Existing `_hashlib.HASH.*` and
`_sha2.SHA256Type.*` remain. These are four replaced graph edges and one
additional graph edge across six sites, **already applied at `0fa844a`**.

For **avro**, source paths are relative to
`macro-benchmark/projects/avro/avro/`, and callers have prefix `avro.`.
The [ledger](macro-benchmark/ground-truth/avro.ledger:59)
records the CSV sites; its hash sites are at ledger lines 3681 and 4161.

| Site | Caller | Remove | Add |
|---|---|---|---|
| `__main__.py:71:15` | `__main__.print_csv` | — | `_csv.Writer.writerow` |
| `__main__.py:117:23` | `__main__.print_avro` | — | `_csv.Writer.writerow` |
| `protocol.py:108:59` | `protocol.Protocol.__init__` | — | `_md5.MD5Type.digest` |
| `schema.py:338:24` | `schema.Schema.fingerprint` | `_sha1.sha1.digest` | `_sha1.SHA1Type.digest` |
| `schema.py:338:24` | `schema.Schema.fingerprint` | — | `_md5.MD5Type.digest` |
| `schema.py:338:24` | `schema.Schema.fingerprint` | — | `_sha256.SHA224Type.digest` |
| `schema.py:338:24` | `schema.Schema.fingerprint` | — | `_sha256.SHA256Type.digest` |
| `schema.py:338:24` | `schema.Schema.fingerprint` | — | `_sha512.SHA384Type.digest` |

Receiver construction is at `__main__.py:65`, `protocol.py:108`, and
`schema.py:337`. The existing admission ruling includes CPython 3.10+ and
PyPy 3.10/3.11 (`avro.md:17`; upstream CI
`deps/upstream-ci/avro-release-1.12.2-test-lang-py.yml:44`).

Consequently, avro retains `_csv.writer.writerow`, `_md5.md5.digest`,
both lowercase `_sha256` names, and both lowercase `_sha512` names for
the runtime reasons above. It also retains `_sha1.sha.digest`;
**PyPy does not justify `_sha1.sha1.digest`**. Other existing hash names
remain. The result is eight added and one removed graph edge across four
sites.

For **tablib**, the
[ledger entry](macro-benchmark/ground-truth/tablib.ledger:2374)
has one affected site:

| Source site | Caller | Remove | Add |
|---|---|---|---|
| `src/tablib/formats/_csv.py:26:26` | `tablib.formats._csv.CSVFormat.export_stream_set` | `_csv.writer.writerow` | `_csv.Writer.writerow` |

The writer is constructed at line 23. Tablib admits CPython 3.10+ and no
PyPy (`tablib.md:24–31`; `pyproject.toml:18`; its CI matrix), so no
lowercase fallback remains.

| Batch-8 package | Sites affected | Graph edges added | Graph edges removed |
|---|---:|---:|---:|
| honcho | 0 | 0 | 0 |
| nodeenv | 0 | 0 | 0 |
| flit-core | 6 | 5 | 4 |
| pyusb | 0 | 0 | 0 |
| vulture | 0 | 0 | 0 |
| toolz | 0 | 0 | 0 |
| tablib | 1 | 1 | 1 |
| avro | 4 | 8 | 1 |
| pubchempy | 0 | 0 | 0 |
| m3u8 | 0 | 0 | 0 |

These are **14 additions and six removals, net +8 outside edges** against
`dce3eb7`. The seven unaffected packages have no affected CSV/hash method
names in their ground-truth files.

The older usage **does not bind**. The
[scope-rule introduction](macro-benchmark/README.md:1979)
explicitly says that package judgements cannot override global rules.
Tinytag’s and netaddr’s lowercase-only CSV naming, and the cited
django-constance, bottle, and Sublist3r hash naming, do not conform where
their admitted CPython runtime exports the type attribute. A lowercase
name can nevertheless remain valid for another admitted runtime; that
does not justify omitting the exported-type name. This states conformity
only and makes no decision about changing older batches’ files.

The [pyfiglet/path/structlog ruling](macro-benchmark/README.md:2897)
still governs a private class without a public path that a facade merely
re-exports. It does not make `tp_name` override an actual exported type
attribute. This ruling clarifies that distinction and follows the
existing version-union rule. It concerns names of already-admitted
explicit outside calls, not admission of new receivers or implicit
outside edges.

No files were changed, and no package was run or imported.