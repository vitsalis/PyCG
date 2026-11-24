# dagster-pipes: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [dagster-pipes.md](dagster-pipes.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release 1.13.28, held as its PyPI sdist (SHA-256 `f785c2ee…`). Audited files,
as the writer left them in the worktree (not committed):
`dagster-pipes.ledger` (454 entries, 118 notes, 67 rejection lines, 1
exclusion, 4 default lines for 5 candidates that decide 60 sites),
`dagster-pipes.json` (150 nodes, 385 edges: 164 in the package, 221
outside), `dagster-pipes.rejected.json` (3 edges) and `dagster-pipes.md`
(judgements 1 to 12). `check.py --benchmark-dir macro-benchmark-heldout-3
dagster-pipes` reports no errors. The trace (`dynamic/dagster-pipes.json`,
CPython 3.14.10, 20 passed) has 165 edges and confirms 162 graph edges;
the other 3 are the rejected ones.

I judged the files by the README's conventions and scope rules (A, B1 to B5,
C) and by the rulings of the second held-out set and the 2021 set. I read
`dagster_pipes/__init__.py`, `version.py`, `pyproject.toml` and the tests as
data. I ran no static analysis tool and did not run or import the package.

**Result.** The ground truth is complete and precise as far as I can test.
The blind sample agrees on all 70 sites. The exhaustive checks found no
missed edge and no edge that cannot happen. Two cases need a ruling of the
lead; the writer flagged both (judgements 3, 4 and 5). Neither changes the
edge count under the writer's reading. One wording fix and two README
remarks.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Proposal |
|---|---|---|---|---|---|
| L1 | ruling needed (writer's judgement 3; I agree with the writer) | Clients annotated `Any` with a documented type: S3 (`__init__.py:1192, 1212, 1243`, docstring "A boto3.client("s3") object", 1189), Azure (1344, 1365, 1394, docstring "An azure.storage.blob.BlobServiceClient object", 1341), widgets (1516, no class named) | B4: "When an annotation and the documentation both exist and differ, the annotation decides." `Any` admits every value, as `object` does (B2's list). The authors chose `Any` on purpose: "we don't want to depend on boto3" (1214-1215). | 0 as written. If the docstring decided: +10 (S3 `get_object`, `StreamingBody.read`, `bytes.decode` at 1199-1200; `put_object` 1251; Azure `get_blob_client` x2, `download_blob`, `readall`, `bytes.decode` 1351-1353; `upload_blob` 1403). boto3's client class and its methods are generated at run time by botocore, so the S3 names would have no public path. | Keep the writer's reading. Add `Any` to B4: an annotation that admits every value (`Any`, `object`) fixes no outside type, and it decides over the documentation. |
| L2 | ruling needed (writer's judgements 4, 5) | GCS calls (1277:38, 1277:51, 1277:74, 1278:36, 1325:51, 1329:30, 1329:54) and pyspark `spark.conf.get` (1461:30, 1462:57, 1465:44) named as a missing module: `google.cloud.storage.Client.get_bucket.blob...`, `pyspark.sql.SparkSession.getActiveSession.conf.get` | The writer follows the README sentence on a module that is not installed and cannot be read, with the lead's rulings markdown2 J4 (wavedrom: "not in the test environment, so its code cannot be read") and fabric J11 (pywin32). face_classification used real public names for keras, and fabric read invoke and paramiko from PyPI. My blind notes used the real classes (`google.cloud.storage.Bucket.blob`, `google.cloud.storage.Blob.download_as_bytes`, `.upload_from_string`, `<builtin>.bytes.decode`, `pyspark.sql.conf.RuntimeConfig.get`). The precedents favour the writer. **One inconsistency:** the ledger takes the names from the stub but the branches from the real library. A micro-benchmark stub never returns `None` and never raises, yet the ledger keeps the `spark is None` branch (1457:36, note "the real getActiveSession returns None then") and the `except Py4JJavaError` branch with `warnings.warn` (1470:26). | 0 as written (7 GCS edges and 1 pyspark edge renamed either way). Real names with both admitted pyspark classes (classic `RuntimeConfig`, Spark Connect `pyspark.sql.connect.conf.RuntimeConf`): +1. Strict stub semantics for branches: -1 (`PipesDbfsMessageWriter.get_opened_extras -> warnings.warn`; the 1457 edge also comes from 1451). | Keep the writer's names (J4). State in the README that the missing-module rule fixes names only, and that a branch that the library's answer decides runs (as asciinema's server answer). The ledger then stays as it is. |
| W1 | wording (no graph change) | notes at 895:44 and 1151:23 | Both say "f is the stream that the builtin open returns"; the variables are `input_file` (887) and `file` (1150). | 0 | Rename in the two notes. |
| R1 | README remark | README, "A fifth directory: the third held-out set" | It still says "The set has no ground truth and no trace yet." | 0 | Update when the set is committed. |
| R2 | README remark | README, "Auditing a ground truth" | It does not say in which order the sites are numbered before `rng.sample`. I sorted the skeleton's sites by (line, column), as the cachetools audit did ("in file order"). | 0 | Say "in file order (line, column)". |

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch benchmark directory
`$TMPDIR/heldout3-audit-dagster-pipes/bench` with a copy of
`projects.toml` and links to `projects/` and `archives/`, then
`check.py --benchmark-dir <scratch> --skeleton dagster-pipes`. It has 468
sites (391 call, 53 decorator, 14 with, 10 getattr), 203 with candidates,
and 0 value sites, so the sample has no value sites to add. I sorted the
sites by (line, column) and drew `random.Random(20261111).sample(sites,
70)`: 56 calls, 8 decorators, 5 `with`, 1 getattr (this is the skeleton's
mix; explicit calls dominate). I wrote the callees of each site, the class
hierarchy, and my decision at every site with candidates or callbacks, to
`blind.md` before I opened any writer file or the trace.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Sampled calls, decorators and the getattr | 65 | 65 | 0 |
| Sampled `with` sites (decided by the default on `PipesContext.__enter__/__exit__`) | 5 | 5 | 0 |
| **Total** | **70** | **70** | **0** |

Beyond the sample, my blind decisions at all 203 sites with candidates and
at the three callback sites (688:25, 770:24, 862:29) agree with the ledger.
My blind list of expected outside callees agrees too, except the GCS and
pyspark names (L2: naming only; the precedents favour the writer, so I
count it as my naming error).

## Step 2: dispatch sets (B1, B2)

Abstract by `abc` (no receivers): `PipesContextLoader`,
`PipesLogWriterChannel` (its `capture` is `contextmanager` over
`abstractmethod`; `functools.wraps` copies `__isabstractmethod__`),
`PipesLogWriter`, `PipesMessageWriter`, `PipesMessageWriterChannel`,
`PipesParamsLoader`, `PipesBlobStoreMessageWriter`,
`PipesBlobStoreMessageWriterChannel`, `PipesStdioLogWriter`,
`PipesStdioLogWriterChannel`. Every concrete package subclass overrides
each abstract method. Every row is identical to the ledger.

| Site | Receivers or role values | Callees |
|---|---|---|
| `message_writer.open` 1696:81 | 7 concrete message writers (annotation 1612, 1690) | helper; `PipesBlobStoreMessageWriter.open` (5 blob writers), `PipesDefaultMessageWriter.open`, `PipesPrefectLogsMessageWriter.open` |
| `context_loader.load_context` 1695:78 | 6 concrete loaders | helper and the 6 `load_context` |
| `params_loader.*` 1640, 1692, 1693 | Mapping (and EnvVar), CliArgs, DatabricksNotebookWidgets | their 3 methods each |
| `.write_message` 1035:43, 1698:44, 1725:48, 1738:44 | channels that the writers yield; annotation `PipesMessageWriterChannel` (1026) | BlobStore channel base (4 channels inherit), File, Stream, BufferedStream, PrefectLogs |
| `get_opened_extras` 573:49 / 540:49 | message writers / log writers | `PipesMessageWriter`'s and `PipesDbfsMessageWriter`'s / `PipesLogWriter`'s |
| `make_channel` 644:36 / 796:47, 797:47 | 5 blob writers / 2 stdio log writers | their overrides |
| `upload_messages_chunk` 706:47 | 4 blob channels | their overrides |
| `capture` 799:55, 800:55; `write_chunk` 898:41 | 2 stdio log channels | `PipesStdioLogWriterChannel.capture` (+ helper); the 2 `write_chunk` |
| `thread.start()` 688:25 / 862:29; `super().run` 770:24 | plain `Thread` with target / `ExcThread` / target `self.handler` (851) | `_upload_loop` / `ExcThread.run` / `threading.Thread.run` + `handler` |
| `super().__init__` (14 sites) | MRO | as in the ledger; 1049:25 and 1162:25 `abc.ABC.__init__` (h11 precedent; trace `<builtin>.object.__init__`) |

## Step 3: the default rejections

All 60 sites listed by `--report --default <candidate>`: 14 `with` sites
(files, a tempfile wrapper, ExitStacks, nullcontext, the
`_GeneratorContextManager` objects, the Azure blob clients); 17 `.get`
(dicts of params, messages and exceptions, `queue.Queue`, the widgets, the
pyspark configuration); 4 `.set` (`threading.Event`, builtin `set()`); 11
`.join` (str, `os.path`, a plain `Thread` at 693:28, `super()` at 775:21).
No site enters a `PipesContext` or calls the class's `get`/`set`; the one
`ExcThread.join` is accepted at 870:28. All correct.

## Step 4: functions with no caller, special methods, properties

52 functions and 2 modules have no caller. Each is client API (the
`PipesContext` properties, report methods, `__enter__`/`__exit__`,
`open_dagster_pipes`, `encode_param`, `to_asset_key_path`, constructors of
the cloud classes and `PipesStdioFileLogWriter.__init__`), an abstract
method, `_PipesLoggerHandler.emit` (logging calls it when a client logs
through `PipesContext.log`), `PipesLogWriter.get_opened_payload` (nothing
calls it; `PipesBlobStoreMessageWriter._log_writer` stays `None`), or
`_assert_opt_param_value` / `_assert_single_partition` (no call in the
source). Each keeps the out-edges of its body (rule A). The three
properties that the package reads (`name` x4, `stdio` x2,
`message_channel` at 1062:34) are accepted; `temp_file.name` (841:58,
853:31) and `self.message_channel` on the log channel (1035:14) are
rightly rejected. No package class defines `__iter__`, `__len__`,
`__bool__`, `__eq__`, `__hash__`, `__getitem__`, `__format__`, `__str__`
or `__repr__`; the 849 implicit sites without candidates hold no package
callee (I checked the 11 iteration and 2 mapping sites by hand).

## Step 5: rejections, notes, outside callees, trace

- All 67 rejection lines and all 118 notes hold, except the wording of W1.
- The exclusion at 1578:26 (`_PipesLoggerHandler.emit` under
  `Logger.info`) is right: `_PipesLogger` is never registered under a
  logger name, and the package passes only `logging.getLogger(LOGGER_NAME)`.
- All 221 outside edges (104 names) exist and are named by the rules or
  by a trace alias: the default and original streams as
  `io.TextIOWrapper.*`, `tee.stdin` as `io.BufferedWriter.fileno`,
  `ExcThread(...)` as `threading.Thread.__init__`, `PipesException(...)`
  as `<builtin>.dict.__init__` (TypedDict; micro `typed_dict_call`),
  inherited `argparse.ArgumentParser.add_argument`,
  `logging.Logger.addHandler` on `_PipesLogger`. `params.get` as
  `<builtin>.dict.get` rests on the package's own params, the dicts of
  `decode_param` (json); client mappings are opaque. B4 holds for
  `TracebackException`, `threading.Event`, `logging.Logger`,
  `logging.LogRecord`, and the `isinstance` checks (386, 394, and `str`
  in `_assert_env_param_type`).
- The 3 rejected trace edges are calls of the tests' `MagicMock`
  (`test_context.py:47-51`): client objects (B5). Correct.
- The writer's judgements 1, 2 and 6 to 12 hold; 3, 4 and 5 are L1 and L2.
- 223 edges come from reading only; I classified each package edge among
  them (110) and found each certainly possible: the cloud and Databricks
  paths, the stream channels, the CLI and environment loaders, and the
  dispatch sets above, which the tests do not reach.

## Follow-up after the ruling on `Any`

The lead reversed L1: `Any` states no type, so for B4 the docstring of a
parameter annotated `Any` can fix a concrete outside type, named by the
usual rules; a class with no public path cannot be named. L2 stands
(missing-module names for google-cloud-storage, azure-storage-blob and
pyspark, which are not installed). I checked the writer's delta against
the source and the two rulings. `check.py`: no errors; 391 edges (164 /
227), 162 confirmed, 229 from reading only. The delta is exactly +6
outside edges, with no merge into an existing edge.

**The 6 added callees: correct.**

- The documented type is the one in the docstrings: "client (Any): An
  azure.storage.blob.BlobServiceClient object." at 1341, 1361 and 1388.
  azure-storage-blob is not in `requirements/dagster-pipes.txt`, so L2
  applies.
- The chained names follow the micro-benchmark rules for a missing module.
  An attribute of a stub instance is the stub with the longer path. A call
  returns an instance of that stub. A `with` statement on a stub gives the
  stub itself, so `blob_client` is the instance of `…get_blob_client`. The
  names are `azure.storage.blob.BlobServiceClient.get_blob_client` (1351:42,
  1402:42), `….get_blob_client.download_blob` (1352:44),
  `….download_blob.readall` (1352:54), `….readall.decode` (1353:36) and
  `….get_blob_client.upload_blob` (1403:36).
- `.decode` at 1353:36: in the real library it is `<builtin>.bytes.decode`.
  `StorageStreamDownloader.readall()` returns bytes when `download_blob`
  gets no `encoding`, and here it gets none. Under L2 the name comes from
  the stub, as for GCS at 1278:36 (`….download_as_bytes.decode`). The
  writer is consistent with L2.

**The 7 sites left without a callee.**

- Widgets (1521:32, 1524:45, 1527:45): correct. The class docstring (1514)
  says only "extracts params from widgets (base params) in a Databricks
  Notebook". `__init__` (1516) has no docstring. No class is named.
- S3: "no public path" is right for the class. botocore makes the client
  class with `type()` at run time and binds it to no module attribute;
  boto3's documentation calls it `S3.Client`, but that is only a
  documentation name. The writer applies the ruling as the lead stated it.
- **One point for the lead (consistency of L1 with L2; +2 edges if
  changed).** The "no public path" argument reads the real library. By the
  J4/J11 precedent that L2 keeps, a library that is not installed (boto3
  and botocore are not) is not read: it is named as a missing module, as
  Azure now is. The docstring's own expression `boto3.client("s3")` then
  has the exact shape of the micro-benchmark example `ext.client().get()`:
  a call of the stub `boto3.client` returns an instance of it, so
  `get_object` (1199:38) would be `boto3.client.get_object` and
  `put_object` (1251:32) would be `boto3.client.put_object`. Even by real
  names, the method is (from my knowledge of botocore, not read here) the
  closure `_api_call` of `ClientCreator._create_api_method`, which the
  micro-benchmark rule "Functions without an attribute path" can name by
  where it is defined. So the S3 class has no public path, but its two
  method calls can still be named. Either way, `obj["Body"].read()` and
  `.decode` (1200:42, 1200:51) stay without a callee: the micro-benchmark
  does not define the subscript of a stub instance (a README gap). I
  propose the missing-module names, because they apply L2 to S3 as to
  Azure. The writer is not at fault: the ruling named this case.


## Third complete audit (2026-11-16)

Two independent models were frozen after reading all 1,982 runtime lines
and all 432 test lines, before either reviewer opened this project's
graph, ledger, trace or earlier semantic reports. Shared-rule examples
about dagster-pipes were disclosed in both freezes. No target, tests or
third-party dependencies were imported or executed.

The comparison reviewed all 394 graph pairs, all 495 ledger site-target
relations, all 454 ledger entries and all 863 omitted scanner sites.
It also checked 181 package site-target argument bindings, the 3 rejected
trace edges, abstract receiver sets, public/private input roles, all
properties, context-manager and thread callbacks, supported Python
3.10–3.14 branches and missing-library names. No false positive or missed
edge was found. The graph remains 150 nodes and 394 edges (165 package,
229 outside); 162 are traced and 232 are source-only.

Four explanation groups were corrected: the PipesContext constructor is
private by its explicit docstring; the logger callback now has a current
public-API witness instead of a stale exclusion reference; stream and
buffered-stream notes name their distinct factory sites; TypedDict
construction explains metaclass delegation separately from the benchmark's
dict.__init__ name. The None-channel RuntimeError and invalid-stream
ValueError remain deliberate public-input validation paths under B4.

The complete pass-3 record contains one verdict per graph pair and scanner
site, exact edits, hashes, immutable source-first models, a separate empty
edge-additions file and replay checks. The earlier sections above remain a
historical record and do not override these current conclusions.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Fourth complete audit (2026-11-16)

The fresh primary auditor read both runtime modules and all shipped tests,
then froze a full 1,317-site model before opening the baseline. Global
README examples and historical counts were disclosed before comparison.
No target, test, dependency or generated code was executed.

All 394 graph pairs, 495 site-target relations, 454 ledger entries and
863 omitted sites were reviewed. The 150 bodies, five default candidates
covering 60 candidate-site relations, and three rejected client-mock pairs
were retained. No graph changes are proposed.

The frozen model had two errors: TypedDict construction used dict instead
of the benchmark's dict.__init__ name; the explicit None-channel error
was over-restricted by its constructor annotation. B4 keeps this intentional
validation path. Both corrections are recorded separately from the freeze.

The current metadata now records CPython 3.10–3.14 with no evidenced
alternative interpreter, and the working normal/-O/-OO union. Assertions
only guard builtin/client data operations; removing them creates no new
package callee. There is no runtime docstring lookup. Unbuffered standard
streams retain their TextIOWrapper; the Popen pipe uses its default
buffering and retains BufferedWriter. Callback, cloud stub and client-opacity decisions
are unchanged. Root acceptance runs the structural and origin gates.
