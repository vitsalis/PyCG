# b8-ruling-avro-1: TetherTask (avro Q2 / J8 / audit F2)

Referee: Codex (gpt-6-astra, xhigh), read-only, 2026-11-24, on writer commit 91618dd and audit fd87143. Adopted by the lead, 2026-11-24.

Q2 asks whether avro’s abstract `TetherTask`, which has no subclass in the
analysed package, supplies callees for calls dispatched on client tasks,
and whether excluding those receivers also excludes calls through values
that avro creates and stores on those tasks. The disputed sets are 13
dispatch edges and 17 attribute-derived edges, including the value
forwarded to `Collector.collect`.

I adopt the middle reading: **remove the 13 dispatch edges, retain the 17
attribute-derived edges, and add none**. An instance-dispatched call on a
client subclass of an abstract documented base does not acquire package
callees merely because that subclass could inherit concrete methods.
Separately, a value that package code constructs or selects retains its
provenance through explicit storage and forwarding, including storage on
an otherwise opaque client object, when the package’s assignments and
supported lifecycle establish that value at the call site.
B5’s attribute opacity applies to client-derived values; storage on a
client object does not erase independently established package provenance.
Here, that distinction excludes dispatch on the task while retaining calls
on its package-created requestor, readers, schema, logger and event.

`TetherTask` derives from `abc.ABC` at
[tether_task.py:155](macro-benchmark/projects/avro/avro/tether/tether_task.py:155);
its abstract methods are declared at lines 367, 380 and 397. The test
subclass at `avro/test/word_count_task.py:29` is outside the analysed
package: `projects.toml:3010` excludes `avro/test`. Its explicit base
constructor call at line 43 demonstrates the supported initialization
sequence without making that subclass a package receiver.

The following tables give the complete Q2 disposition against writer
commit `91618dd`. Class names expand as follows:

| Classes | Module |
|---|---|
| `TetherTask`, `Collector`, `HTTPRequestor` | `avro.tether.tether_task` |
| `TaskRunner`, `TaskRunnerResponder` | `avro.tether.tether_task_runner` |
| `DatumReader` | `avro.io` |
| `RecordSchema`, `Field` | `avro.schema` |

**Remove these five edges** at sites in
[tether_task.py](macro-benchmark/projects/avro/avro/tether/tether_task.py).
Each dispatches directly on `self`, whose client subclass supplies no
admitted package receiver for this purpose.

| Line:column | Edge removed |
|---|---|
| 266:22 | `TetherTask.open → TetherTask.fail` |
| 304:22 | `TetherTask.configure → TetherTask.fail` |
| 351:22 | `TetherTask.input → TetherTask.fail` |
| 363:26 | `TetherTask.complete → TetherTask.fail` |
| 436:19 | `TetherTask.fail → TetherTask.close` |

**Remove these eight edges** at sites in
[tether_task_runner.py](macro-benchmark/projects/avro/avro/tether/tether_task_runner.py).
`TaskRunner.__init__` checks and stores the client task at lines 151–153;
`TaskRunnerResponder.__init__` wraps it at line 58. Neither operation
creates an admitted concrete package task.

| Line:column | Edge removed |
|---|---|
| 64:36 | `TaskRunnerResponder.invoke → TetherTask.configure` |
| 68:31 | `TaskRunnerResponder.invoke → TetherTask.partitions` |
| 74:32 | `TaskRunnerResponder.invoke → TetherTask.input` |
| 80:35 | `TaskRunnerResponder.invoke → TetherTask.complete` |
| 81:32 | `TaskRunnerResponder.invoke → TetherTask.close` |
| 89:27 | `TaskRunnerResponder.invoke → TetherTask.fail` |
| 193:23 | `TaskRunner.start → TetherTask.open` |
| 209:24 | `TaskRunner.close → TetherTask.close` |

The site at `68:31` is the implicit setter call; `partitions` names the
property node shared by its accessors. Weakref forwarding changes neither
receiver admission nor provenance: CPython’s
`deps/cpython/3.10.22/Objects/weakrefobject.c:496` forwards attribute
lookup, and lines 512–518 forward assignment to the referent.

**Retain these attribute-derived edges** at sites in `tether_task.py`.
Assignment evidence beginning with `:` refers to that same file.

| Line:column | Edge retained | Assignment evidence |
|---|---|---|
| 104:34 | `Collector.collect → HTTPRequestor.request` | :260, :292, :297, :84 |
| 251:22 | `TetherTask.open → logging.Logger.info` | :226 |
| 263:38 | `TetherTask.open → HTTPRequestor.request` | :260 |
| 300:67 | `TetherTask.configure → RecordSchema.fields` | :197 |
| 300:84 | `TetherTask.configure → Field.order` | :197, :300 |
| 331:50 | `TetherTask.input → DatumReader.read` | :291 |
| 341:57 | `TetherTask.input → DatumReader.read` | :295 |
| 350:29 | `TetherTask.input → logging.Logger.warning` | :226 |
| 362:33 | `TetherTask.complete → logging.Logger.warning` | :226 |
| 365:34 | `TetherTask.complete → HTTPRequestor.request` | :260 |
| 413:34 | `TetherTask.status → HTTPRequestor.request` | :260 |
| 419:34 | `TetherTask.count → HTTPRequestor.request` | :260 |
| 425:23 | `TetherTask.fail → logging.Logger.error` | :226 |
| 432:38 | `TetherTask.fail → HTTPRequestor.request` | :260 |
| 434:31 | `TetherTask.fail → logging.Logger.exception` | :226 |
| 439:22 | `TetherTask.close → logging.Logger.info` | :226 |
| 449:36 | `TetherTask.close → threading.Event.set` | :225 |

Also retain this edge in `tether_task_runner.py`:

| Line:column | Edge retained | Assignment evidence |
|---|---|---|
| 197:46 | `TaskRunner.start → threading.Event.wait` | task.py:225; runner.py:153 |

In that last row, `task.py` abbreviates `tether_task.py` and `runner.py`
abbreviates `tether_task_runner.py`.

The source establishes these receivers individually:

- `open` creates `HTTPRequestor` at line 260 and immediately calls it at
  line 263. `configure` forwards that same stored value to `Collector`
  at lines 292 and 297; `Collector.__init__` stores it at line 84.
  `HTTPRequestor.request` is defined at line 149.
- `configure` creates the readers at lines 291 and 295.
  Their method is `avro/io.py:836`.
- `__init__` parses and stores `midschema` at line 197. The documented
  record example at lines 180–183 supplies a record-schema witness.
  `avro/schema.py:1037` defines `RecordSchema.fields`, and line 464
  defines `Field.order`.
- `__init__` creates the event at line 225 and obtains the logger at
  line 226. These operations establish the outside receiver types;
  their identity is not inferred from an unknown client attribute.

Thus the retained set contains **nine inside edges and eight outside
edges**, represented by 18 sites. The two reader calls in `input` share
one caller–callee pair. The auditor’s outside count of eight is correct.

The abstract dispatch sites remain without package callees:
`tether_task.py:334:29` (`map`), `345:41` and `359:33`
(`reduceFlush`), and `346:32` (`reduce`).

This ruling **follows B1 and the asyncstdlib precedent**.
[README.md:2027](macro-benchmark/README.md:2027)
expressly excludes the concrete inherited `_recreate_cm` at
`contextlib.py:103`; the explanation in
[asyncstdlib.md:284](macro-benchmark/ground-truth/asyncstdlib.md:284)
confirms that the class is abstract because of another method.
Consequently, rejecting only calls of abstract methods cannot stand.
B1’s explicit-self clause does not override its specific exclusion of
client subclasses of documented abstract bases.

The attribute decision **clarifies B5**, while preserving B2’s package
value flows. Asyncstdlib’s opaque `self.gen` originates in a client
callback; jsonpickle’s excluded `__dict__` and class accesses concern
client-derived attributes (`README.md:2407`). Neither precedent decides
a separately constructed value explicitly stored by package code.
The json-repair ruling (`README.md:2366`) likewise permits an independently
admitted package value inside a client container.

Rule A preserves the outgoing calls of these package bodies independently
of their incoming dispatch edges (`README.md:1987`). This ruling requires
actual assignment and forwarding evidence: an attribute name, an abstract
base contract, or a possible client implementation alone supplies none.
It does not admit client callback results, arbitrary client attributes,
or client-defined methods, and it does not exclude dispatch through an
otherwise admitted concrete package subclass.