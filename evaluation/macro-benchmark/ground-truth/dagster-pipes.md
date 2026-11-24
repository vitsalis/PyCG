# dagster-pipes: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 0 edges and adds 1. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 2 corrections to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/dagster-pipes-review.json`).
The current ledger and statistics below include both audit passes.

The third complete source-first audit (2026-11-16) reviewed all 394 graph
edges, 495 ledger site-target relations and 1,317 scanner sites. It found
no false positives or missed edges. Four explanation corrections clarify
the constructor contract, logger callback witness, stream factory sites
and TypedDict construction. The graph remains 150 nodes and 394 edges.

The fourth complete source-first audit (2026-11-16) reviewed all 394 graph
edges, all 495 site-target relations and all 1,317 source sites. It found
no graph defect. The admitted interpreter scope is CPython 3.10–3.14;
the supplied release declares no alternative implementation. The working
normal/-O/-OO union and ordinary unbuffered standard streams add no edge.
Two initial auditor-model differences were corrected against the global
B4 rule and inherited TypedDict naming convention; neither was a baseline
defect. The graph remains 150 nodes and 394 edges.

Release 1.13.28, held as its PyPI sdist (`dagster_pipes-1.13.28.tar.gz`,
SHA-256 `f785c2ee…`). Analysed source: `dagster_pipes/` (`__init__.py`,
1981 lines, and `version.py`, one assignment): 2 modules, 148 functions,
54 classes. `pyproject.toml` sets `requires-python = ">=3.10,<3.15"`, so the
supported versions are 3.10 to 3.14. All line numbers below are of
`dagster_pipes/__init__.py`.

The ledger is `dagster-pipes.ledger`; the graph `dagster-pipes.json` is
generated from it. Three trace edges are rejected in
`dagster-pipes.rejected.json` (the tests' `MagicMock` objects).

| Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|
| 150 | 394 (165 / 229) | 162 (41.1%) | 232 | 3 | 60 of 148 | 454 | 0 | 5 (60) | 0 |

The trace (CPython 3.14.10, 20 tests passed) covers little: the package's
own tests construct a `PipesContext` with mocks, run the two stdio log
writers, the Prefect writer and one error path of
`PipesDefaultMessageWriter.open`. The cloud, Databricks, CLI and environment
code runs in no test.

## Architecture, as the ledger uses it

- `open_dagster_pipes` (1609) makes a `PipesContext` (1651) from three
  objects: a params loader (`PipesParamsLoader`), a context loader
  (`PipesContextLoader`) and a message writer (`PipesMessageWriter`).
- `PipesContext.__init__` (1686) enters `context_loader.load_context(...)`
  and `message_writer.open(...)` on an `ExitStack`. Both methods are
  `@contextmanager` generator functions. The call runs
  `contextlib.contextmanager.helper`, which calls the generator function
  back (sqlparse precedent). `open` yields the message channel; every
  message goes through `channel.write_message`.
- Blob store writers (S3, GCS, Azure, DBFS, Unity Catalog Volumes) inherit
  `PipesBlobStoreMessageWriter.open` (632), which calls their `make_channel`
  and runs `buffered_upload_loop` (683): a plain `threading.Thread` runs
  `_upload_loop`, which calls the channel's `upload_messages_chunk`.
- Log writers (`PipesStdioLogWriter` and its two subclasses) are a separate
  hierarchy. `PipesStdioLogWriterChannel.capture` (835) starts `tee`,
  redirects a file descriptor, and runs `handler` in an `ExcThread`;
  `handler` calls the channel's `write_chunk`.

## Scope rules

**A. Edges are per function.** Every function keeps its edges. 51
functions (and the two modules) have no caller in the graph: the public API that clients call (the
`PipesContext` properties and report methods, `open_dagster_pipes`,
`encode_param`, `to_asset_key_path`, constructors), the abstract methods,
and two private functions that nothing calls,
`_assert_opt_param_value` (355) and `_assert_single_partition` (291). They
keep their edges.

**B1. Receivers.** Ten classes are abstract by `abc`: `PipesContextLoader`,
`PipesLogWriterChannel`, `PipesLogWriter`, `PipesMessageWriter`,
`PipesMessageWriterChannel`, `PipesParamsLoader`,
`PipesBlobStoreMessageWriter`, `PipesBlobStoreMessageWriterChannel`,
`PipesStdioLogWriter`, `PipesStdioLogWriterChannel`. They are no receivers,
and every concrete package subclass overrides each of their abstract
methods, so no abstract method is a callee. `PipesLogWriterChannel.capture`
is `@contextmanager` over `@abstractmethod` (519-521); `functools.wraps`
copies `__isabstractmethod__` to the wrapper, so the class is abstract too.
`PipesContext`, `PipesDefaultLogWriter` and `ExcThread` have no package
subclass.

**B2. Roles, by annotation.**
- `message_writer: PipesMessageWriter` (1612, 1690): the seven concrete
  message writers. `message_writer.open` (1696:81) therefore has
  `PipesDefaultMessageWriter.open`, `PipesBlobStoreMessageWriter.open` and
  `PipesPrefectLogsMessageWriter.open`; `get_opened_extras` (573:49) has
  `PipesMessageWriter`'s and `PipesDbfsMessageWriter`'s.
- `context_loader: PipesContextLoader`: the six concrete loaders (1695:78).
- `params_loader: PipesParamsLoader`: `PipesMappingParamsLoader` (also as
  `PipesEnvVarParamsLoader`), `PipesCliArgsParamsLoader`,
  `PipesDatabricksNotebookWidgetsParamsLoader` (1640, 1692, 1693).
- The message channel: `PipesContext._message_channel` is what the
  writers' `open` yields; `PipesDefaultLogWriterChannel.message_channel` is
  annotated `PipesMessageWriterChannel` (1026). Both give five
  `write_message` callees: the four blob store channels share
  `PipesBlobStoreMessageWriterChannel.write_message`, then the file,
  stream, buffered stream and Prefect channels (1035:43, 1698:44, 1725:48,
  1738:44).
- Thread targets: `ExcThread` is public; the package's only target is
  `self.handler` (850). A client's target is a client callback.

**B2. Public logger reuse.** `PipesPrefectLogsMessageWriterChannel`
accepts `logger: logging.Logger`. The package-created `_PipesLogger`,
exposed as `PipesContext.log`, fits that role. Reusing it makes
`self._logger.info` at 1578:26 invoke `_PipesLoggerHandler.emit`. A
separate file-backed context supplies a nonrecursive witness; its public
logger can be enabled with `setLevel(logging.INFO)`. The package's own
default logger does not restrict this public parameter. Thus
`_PipesLoggerHandler.emit` has an incoming package edge, even though the
logging library performs the dispatch.

**B4. Concrete outside types.** `TracebackException` (`tb`, 477),
`threading.Event` (`handler`, 884), `logging.Logger` (1569),
`logging.LogRecord` (471) fix their classes. `metadata` and `value` are
dicts after `isinstance` checks (386, 394). `PipesParams` is the abstract
`Mapping`, so it fixes nothing; where the package itself passes params,
they are the dict that `decode_param` makes with `json.loads`, so `.get` on
params is `<builtin>.dict.get` (marshmallow precedent, `schema.py:651`). The
`PipesException` and message values are `TypedDict`s, which count as `dict`
(1588:48, 1595:40). `payload` of `upload_messages_chunk` is the
`io.StringIO` that `_upload_loop` passes (706:56).

**B5. Client objects are opaque.** The tests' `MagicMock` loaders and
writers, and the Databricks widgets (judgement 3, 1521-1527). The S3 body
sites (1200:42, 1200:51) have no callee for another reason: the rules do not
define the subscript of a missing-module value (judgement 3). These explicit
sites have notes and no callee.

**C. Public paths.** Everything in `dagster_pipes/__init__.py` without a
leading underscore is public. `_PipesLogger`, `_PipesLoggerHandler` and the
`_`-functions are private; `_make_message` is private although a test
imports it. The docstring of `PipesContext` says that users should not
instantiate it directly (1659), so its constructor is private under C.
Its three input roles are the values that `open_dagster_pipes` forwards
from its public annotated parameters. This gives the same concrete
loader and writer sets; direct test construction with mocks does not
widen them.

## Judgement calls

1. **`if TYPE_CHECKING:`** (43-46) imports `MagicMock` and
   `google.cloud.storage.Client` for annotations. No call; the block does
   not run.
2. **Version branch** (478): `sys.version_info >= (3, 13)`. Both sides run
   on supported versions. The 3.13 side has `<builtin>.str.split` (479:37);
   the other side has no call.
3. **Clients annotated `Any`: the docstring decides** (lead's ruling,
   which reverses my first reading so that one rule holds for the set). An
   annotation of `Any` states no type (PEP 484 gives an unannotated
   parameter the type `Any`; `object`, by contrast, states that every object
   is accepted). For B4, a parameter annotated `Any` is treated as one
   without an annotation: its docstring can fix a concrete outside type, and
   a method call on it is then an edge to that type's method, named by the
   usual rules, and as a missing module where the library is not installed
   (judgement 4). A class with no public path cannot be named: that site
   keeps a note and no callee. For B2, `Any` names no package value.
   - Azure (`client: Any`, docstring "An azure.storage.blob.BlobServiceClient
     object", 1341, 1361, 1388): azure-storage-blob is not installed, so the
     names are those of a missing module (judgement 4). A `with` statement
     on a stub gives the stub itself. 6 edges added:
     `PipesAzureBlobStorageContextLoader.load_context` ->
     `azure.storage.blob.BlobServiceClient.get_blob_client` (1351:42),
     `….get_blob_client.download_blob` (1352:44),
     `….get_blob_client.download_blob.readall` (1352:54),
     `….get_blob_client.download_blob.readall.decode` (1353:36);
     `PipesAzureBlobStorageMessageWriterChannel.upload_messages_chunk` ->
     `….get_blob_client` (1402:42), `….get_blob_client.upload_blob`
     (1403:36). The real classes would be `BlobClient`,
     `StorageStreamDownloader` and `bytes`.
   - S3 (`client: Any`, docstring "A boto3.client("s3") object", 1189,
     1207, 1236): boto3 is not installed and was not read in the original audit.
     Its ordinary calls use missing-module names whether or not library
     source can be read. The docstring's expression `boto3.client("s3")` has the shape of the
     micro-benchmark example `ext.client().get()` (lead's ruling, on the
     auditor's proposal). 2 edges added:
     `PipesS3ContextLoader.load_context` -> `boto3.client.get_object`
     (1199:38) and `PipesS3MessageWriterChannel.upload_messages_chunk` ->
     `boto3.client.put_object` (1251:32). The real class has no public name:
     botocore makes it at run time. `obj["Body"].read()` (1200:42) and its
     `.decode` (1200:51) keep a note and no callee: the rules for a missing
     module do not define the subscript of a stub value.
   - Widgets (`widgets: Any`, 1516): the class docstring says only
     "widgets (base params) in a Databricks Notebook" and names no class.
     The three `widgets.get` sites (1521:32, 1524:45, 1527:45) keep a note
     and no callee (B5).
4. **GCS names: missing module.** `client: "GCSClient"` (1270, 1289, 1318)
   names `google.cloud.storage.Client`, a concrete outside type (B4), so its
   method calls have callees. google-cloud-storage is not installed (only
   the optional extra `stubs` names it, without a version) and was not read
   here. Under the current global README rule, ordinary calls to a module
   that is not installed use missing-module names even when a copy of its
   source can be read. The original audit applied the markdown2
   `wavedrom.render` precedent. These 7 edges keep their missing-module
   names:
   `google.cloud.storage.Client.get_bucket` (1277:38, 1325:51),
   `….get_bucket.blob` (1277:51, 1329:30),
   `….get_bucket.blob.download_as_bytes` (1277:74),
   `….get_bucket.blob.download_as_bytes.decode` (1278:36),
   `….get_bucket.blob.upload_from_string` (1329:54). The real names of the
   public API would be `google.cloud.storage.Client.get_bucket`,
   `google.cloud.storage.Bucket.blob`,
   `google.cloud.storage.Blob.download_as_bytes`,
   `google.cloud.storage.Blob.upload_from_string` and
   `<builtin>.bytes.decode`. The original audit contrasted these names with
   the then-current face_classification precedent, which used real
   public-API names for unread libraries. That comparison records the
   earlier audit; the current global README gives one rule for ordinary
   missing-library calls, regardless of source availability. Reading a
   library does not make its ordinary return values transparent. The
   base/decorator exception applies only to package definitions made
   through library code; it does not apply to these client calls. The
   original lead ruling on control flow still holds: the missing-module
   rule fixes names only, and a branch that the library's answer decides
   still runs.
5. **Optional import of pyspark and py4j** (1447-1453): both sides run. The
   `except ImportError` side raises `DagsterPipesError` (1451:36). pyspark
   is not installed: `SparkSession.getActiveSession()` is
   `pyspark.sql.SparkSession.getActiveSession` (1455:46, the same name
   either way), and `spark.conf.get` (1461:30, 1462:57, 1465:44) is the
   missing-module name `pyspark.sql.SparkSession.getActiveSession.conf.get`,
   one edge. The real name would be `pyspark.sql.conf.RuntimeConfig.get`
   (or `pyspark.sql.connect.conf.RuntimeConf.get` for a Spark Connect
   session in pyspark 4). The `spark is None` branch (1457:36) is kept: the
   real `getActiveSession` returns `None` without a session. Same ruling as
   judgement 4.
6. **`sys.__stdout__` and `sys.__stderr__`** (828, 830): the `stdio`
   property returns the original streams. I named them
   `io.TextIOWrapper` like the default `sys.stdout` and `sys.stderr` of the
   README (846:45 `fileno`, 866:33 `flush`); the trace confirms both.
   `sys.stdout` and `sys.stderr` passed to the stream channels (955, 967)
   give `io.TextIOWrapper.writelines` (1000:32, 1017:36).
7. **`tee.stdin`** (848:56): `Popen(..., stdin=PIPE)` without text mode
   makes an `io.BufferedWriter`; the trace confirms
   `_io.BufferedWriter.fileno`.
8. **Thread callbacks.** `thread.start()` has the thread's `run` as callee:
   `PipesBlobStoreMessageWriterChannel._upload_loop` at 688:25 (a plain
   `Thread` target) and `ExcThread.run` at 862:29 (an override).
   `super().run()` in `ExcThread.run` (770:24) has `threading.Thread.run`
   and the target `PipesStdioLogWriterChannel.handler`, which `Thread.run`
   calls. The trace has all three.
9. **`sys.stderr.write(traceback.format_exception(...))`** (779:29): the
   argument is a list, so `write` raises `TypeError`, but the call is made:
   the edge to `io.TextIOWrapper.write` is kept.
10. **Branches for values that the annotations exclude.**
    `RuntimeError` in `PipesDefaultLogWriter.message_channel` (1054:31,
    `message_channel` is annotated as a channel, not `Optional`) and
    `ValueError` in `stdio` (832:29, `stream` is a `Literal` of two values)
    are kept: the code takes them on purpose for a client value (markdown2
    precedent under B4).
11. **Calls of package classes without a package `__init__`.**
    `DagsterPipesError(...)` (24 sites in 18 functions) is
    `<builtin>.Exception.__init__`.
    `PipesException(...)` (483:26), a `TypedDict`, is
    `<builtin>.dict.__init__` under the explicit micro-benchmark
    `type_hints/typed_dict_call` convention. Its metaclass
    `typing._TypedDictMeta.__call__` delegates to `dict`; the target name
    does not imply ordinary `type.__call__` dispatch on a package class. `ExcThread(...)`
    (850:31) is `threading.Thread.__init__`. `PipesDefaultContextLoader()`
    and `PipesDefaultMessageWriter()` (1641:69, 1642:69) run
    `object.__init__`: no edge. `super().__init__()` in
    `PipesDefaultLogWriter` and `PipesStdioFileLogWriter` (1049:25,
    1162:25) reaches `object.__init__` after `ABC` and `Generic`, named
    `abc.ABC.__init__` (h11 precedent); the trace's
    `<builtin>.object.__init__` matches it.
12. **Default rejections.** Four lines, five candidates, 60 sites:
    `PipesContext.__enter__` and `__exit__` (14 `with` sites each; no `with`
    in the package enters a `PipesContext`), `PipesContext.get` (17 sites;
    accepted at 1637:32), `PipesContext.set` (4 sites; accepted at 1647:21),
    `ExcThread.join` (11 sites; accepted at 870:28).
