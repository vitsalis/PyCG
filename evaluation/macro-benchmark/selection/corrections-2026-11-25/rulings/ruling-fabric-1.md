The question is whether Fabric’s recursive `Connection(config=...)` calls
preserve the access path of an ordinary missing-library clone result,
reset it to the documented Config roles, or establish a concrete Fabric
Config; if the path survives, the further question is whether unbounded
recursive growth receives the open-path treatment, counting `.clone`
repetitions or gateway levels.

**I rule B on Q-F1 and (i) on Q-F2.** An admitted stub retains its access
path through package storage and argument forwarding, including
constructors; a parameter’s documented or annotated type does not rename
it. Passing a package class to an ordinary missing-library factory does
not establish that its result is a package instance. Recursive forwarding
that repeatedly extends a path without a source-imposed finite bound
creates an open path set, just as unbounded loop reassignment does. Record
one and two repetitions of the repeated access-path segment beyond the
originating path as lower-bound witnesses, rather than counting recursive
invocations.

Here, let `Sk` mean `invoke.config.Config` followed by `k` copies of
`.clone`. The initial ordinary clone produces `S1`, stored at
[connection.py:261–262](evaluation/macro-benchmark/projects/fabric/fabric/connection.py:261).
For a connection storing `Sm`, the call at
[388:55](evaluation/macro-benchmark/projects/fabric/fabric/connection.py:388)
produces `S(m+1)`, which the package forwards through its own `kwargs`
dictionary at line 391. The new constructor stores that path when
`isinstance(config, Config)` succeeds, or appends another `.clone` at
261 when it fails. Thus one gateway level adds one or two copies of the
same repeated segment.

The first hop receives no explicit gateway
([connection.py:377–391](evaluation/macro-benchmark/projects/fabric/fabric/connection.py:377)),
so its own lookup at 281 and `get_gateway()` call at 303 can repeat this
flow. The guard at 384–385 excludes the current host; it supplies no bound
on a chain of distinct hosts. Arbitrarily long finite chains can terminate
without requiring a failed object to be reused. The documentation also
explicitly permits indefinitely chained gateways
([networking.rst:53–55](evaluation/macro-benchmark/projects/fabric/sites/docs/concepts/networking.rst:53)).

**Add the following edges; remove none.** Every caller below has prefix
`fabric.connection.Connection.`. All sites refer to
[Fabric’s connection.py](evaluation/macro-benchmark/projects/fabric/fabric/connection.py);
each listed callee is a separate addition.

| Caller | Site | Callees added |
|---|---|---|
| `__init__` | `261:34` | `S3`, `S4` |
| `__init__` | `281:61` | `S2.base_ssh_config.lookup`, `S3.base_ssh_config.lookup` |
| `__init__` | `291:48` | `S2.base_ssh_config.lookup.get`, `S3.base_ssh_config.lookup.get` |
| `__init__` | `296:52` | `S2.base_ssh_config.lookup.get`, `S3.base_ssh_config.lookup.get` |
| `__init__` | `320:50` | `S2.base_ssh_config.lookup.get`, `S3.base_ssh_config.lookup.get` |
| `resolve_connect_kwargs` | `363:38` | `S2.connect_kwargs.setdefault`, `S3.connect_kwargs.setdefault` |
| `get_gateway` | `388:55` | `S3`, `S4` |
| `open_gateway` | `549:26` | `S2.gateway.open`, `S3.gateway.open` |
| `open_gateway` | `558:51` | `S2.gateway.transport.open_channel`, `S3.gateway.transport.open_channel` |
| `run` | `608:44` | `S2.runners.remote`, `S3.runners.remote` |
| `sudo` | `623:44` | `S2.runners.remote`, `S3.runners.remote` |

The receiver evidence is the storage at 262, lookup-result assignment at
281, `connect_kwargs` assignment at 349, and gateway fallback at 398
stored by 303. The last two sites access `self.config` directly.

These are **22 site–callee additions and 18 distinct outside graph edges**:
the three `__init__` `.get` sites share their two caller–callee pairs.
No inside edge changes. The precise families to declare for these eleven
sites under “Open path sets” are:

| Sites | Family |
|---|---|
| Stored-config suffix calls | `Sm.<suffix>`, `m ≥ 1` |
| `get_gateway`, `388:55` | `Sm`, `m ≥ 2` |
| `__init__`, `261:34` | Existing `S1`, plus `Sm`, `m ≥ 3` |

In particular, this flow does **not** add `S2` at 261: recursive arguments
first arrive as `S2`, and that site appends another `.clone`.

This follows **pgvector’s forwarding ruling**
([README.md:2495](evaluation/macro-benchmark/README.md:2495)),
**einops’s assignment/container/function-forwarding ruling**
([README.md:2711](evaluation/macro-benchmark/README.md:2711)),
and **websocket-client’s `isinstance` ruling**
([README.md:2734](evaluation/macro-benchmark/README.md:2734)).
It expressly **extends** the loop formulation of open path sets to
recursive forwarding
([README.md:2719](evaluation/macro-benchmark/README.md:2719)).
Reading A’s boundary reset in `fabric.ledger:11` and `fabric.md:79–82`
cannot override those global rules
([README.md:1832](evaluation/macro-benchmark/README.md:1832)).

Reading C does not follow from **Avro**. That ruling preserves provenance
established by package construction or selection and explicit assignment
([b8-ruling-avro-1.md:16](evaluation/macro-benchmark/selection/batch-8-proposal/rulings/b8-ruling-avro-1.md:16)).
Fabric selects the **class argument** `Config`; the **returned value**
at 261 still originates in an ordinary missing-library method. The narrow
base/decorator exception does not make that call transparent
([README.md:1735](evaluation/macro-benchmark/README.md:1735)).
Consequently, C removes no stub edges and supplies no constructor callback
there.

The sampling decision is not a cap: longer verified paths remain valid
lower-bound additions. This extension does not cover source-bounded
recursion, inadmissible inputs, paths lost through missing-value
subscripting/unpacking/arithmetic, or calls prevented by an inevitable
earlier failure.

The supplied rules and source decide this question. The referenced
`dynamic/fabric.json` is absent, consistently with
[projects.toml:2520–2527](evaluation/macro-benchmark/projects.toml:2520);
no trace is needed for this ruling. No files were changed, package code
executed, or analysis results consulted.