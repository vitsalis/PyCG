# fabric: independent audit of the ground truth

Commit `34edfe4a1cc9e3d72c3cc41490673db29afe7bbb`. Audited files:
`fabric.ledger` (375 entries, 2 default rejections), `fabric.json` (340
edges: 99 in the package, 241 outside, to 146 outside callees) and
`fabric.md` (J1 to J14). There is no trace and no `fabric.rejected.json`.
`check.py --benchmark-dir macro-benchmark-2021 fabric` reports no errors.

I read the 12 modules and `setup.py`, and searched the tests and `sites/` as
data. I did not run the package and used no static analysis tool. invoke
1.x and paramiko cannot be read here. Each statement below on their
behaviour comes from my memory of their source and API, and is marked so.

**State.** 3 findings (A1 to A3), all for the lead to rule on, and 2
remarks. A1 adds 1 edge, A2 removes 2, A3 adds 1 (or renames 1). If the lead
accepts all three as proposed, the graph keeps 340 edges (100 in the
package, 240 outside). Every other decision of the ledger agrees with mine.

## Findings

| Id | Kind (edges) | Site | Evidence | Confidence | Proposal |
|---|---|---|---|---|---|
| A1 | the writer missed an edge (+1) | `main.py:89:44` `super(Fab, self).no_tasks_given()` | invoke 1.x `Program.no_tasks_given` calls `self.print_help()` and raises `Exit`. `print_help` prints the core options from `self.initial_context.help_tuples()`. `initial_context` is a property that calls `self.core_args()`. That call is how `Fab.core_args` (`main.py:24-54`) puts `-S`, `-H`, `-i` into the parser and the help. Fabric's own comment confirms that the parent prints help (`main.py:86-87`). So `Fab.core_args` is a callback of 89:44. J3 (last bullet) and the note at 89:44 say the opposite. | likely (invoke unread) | add `-> fabric.main.Fab.core_args` at 89:44; fix J3 and the note. `Fab.core_args` then has a caller. |
| A2 | naming: one callee with two names (-2) | `connection.py:545:36` `StringIO(...)` -> `invoke.vendor.six.StringIO`, `six.StringIO`; `group.py:172:22` `Queue()` -> `invoke.vendor.six.moves.queue.Queue`, `six.moves.queue.Queue` | In both copies of six, `StringIO` is the same class (`io.StringIO` on Python 3, `StringIO.StringIO` on Python 2), and `moves.queue.Queue` is `queue.Queue` (`Queue.Queue`). Each pair is one callee, so it is one edge. Micro-benchmark README, "Names": several paths can resolve to one function, and the ground truth uses one path. This differs from `decorator.decorator` (27:2): the vendored copy and the PyPI copy are two functions, so both edges stay. The ledger already names the queue's methods `queue.Queue.put`, `.get`, `.empty` (J6). | certain (that each pair is one object) | keep one name each. For consistency with J6, `queue.Queue` and `io.StringIO`; the lead may prefer the first import path. Fix J6. |
| A3 | naming that needs a ruling (+1, or a rename) | `connection.py:291:48`, `296:52`, `320:50` `self.ssh_config.get(...)` -> `<builtin>.dict.get` | README, "Callees outside the package": a method is named by the class of the receiver, also when that class inherits it (`collections.OrderedDict.get`). From paramiko 2.5 (mid-2019, before the commit date in `fabric.md`), `SSHConfig.lookup` returns an `SSHConfigDict`. J1 names the call by "the function that runs in every version". No README rule says that. The README rule for dependency versions (a branch runs if an admitted version takes it; the lead's ruling 4: names by the versions that the project admits at its commit) gives both callees. | likely (paramiko unread; the 2.5 change is from memory) | add `paramiko.config.SSHConfigDict.get` next to `<builtin>.dict.get`: +1 edge (`Connection.__init__`). If the lead takes only the newest version admitted at the commit, rename instead (0). |

## Step 1: blind re-derivation

I made the skeleton without the ledger, in `$TMPDIR/macro2021-audit-fabric/`
(a copy of `projects.toml` and a `projects` link). It has 432 sites, and each
one needs an entry. I numbered the site lines from 0 in file order and drew
`random.Random(20261111).sample(range(432), 100)`, then added the 4 value
sites (one was already drawn): 103 sites. I wrote the callees of each site
in `blind-answers.md` before I opened `fabric.ledger`, `.json` or `.md`.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (74 call, 3 decorator), with the 4 value sites | 77 | 75 | 2 |
| Implicit (10 op, 8 getitem, 4 getattr, 2 setitem, 1 with) | 26 | 26 | 0 |
| **Total** | **103** | **101** | **2** |

The 2 disagreements, classified:

- **The writer missed an edge (1):** `main.py:89:44` (A1).
- **Naming only (1):** `group.py:172:22`. I wrote `queue.Queue`; the ledger
  has two names for that class (A2).
- **The writer has an edge that cannot happen (0). I was wrong (0).**

My blind file left one question open that the sample did not hit: the name
of `ssh_config.get` (A3).

## Step 2: exhaustive checks

**Dispatch (B1).** No package class has a package subclass except
`Group`, whose `SerialGroup` and `ThreadingGroup` inherit `__init__`.
Every `self.m()` and `other._identity()` site resolves to the one method of
its class. `self.config` of a `Connection` is always a fabric `Config`
(`connection.py:255-262`), so 388:55 is `Config.clone`. The receivers of
the sites in `opens`, `Remote`, `Transfer`, `Tunnel` and `TunnelManager`
are the package's own objects, as the ledger's notes say. All agree.

**Value sites and callback roles.** `opens` 30:18: the six `@opens`
methods. 608:44 and 623:44: `Remote`, the default of `global_defaults`
(`config.py:244`), so `invoke.Runner.__init__`. 81:20: `Group.__init__`.
Thread starts: `TunnelManager._run` (745:22), `Tunnel._run` (859:25,
89:25), `thread_worker` (181:25); the constructor at 176:45 rightly rejects
`thread_worker`. The two calls that the site finder does not flag (R1),
`debug(...)` and `self.config_class(...)`, are right. All agree.

**(a) Library callbacks.** Each edge is at the package site that called
invoke or paramiko:

- `Remote`: invoke's `Runner.run` runs under `Context._run` and
  `Context._sudo`, so the nine methods are callees of 609:25 and 624:26.
  `read_proc_stdout`, `read_proc_stderr` and `_write_proc_stdin` run in IO
  threads that `Runner.run` starts; library frames are transparent, so
  they also belong to these two sites. This agrees with my blind answers.
  `Context.run` at 637:43 uses invoke's `Local`: no callback.
- `Config`: `global_defaults` at 93:37 and 261:34 (and 157:56 for the role
  `into=Config`, which the package passes at 261); `_clone_init_kwargs` and
  `Config.__init__` at 139:40 and 261:34. invoke's `Context.__init__`,
  `Runner.__init__`, `Program.__init__`, `load_collection` and
  `update_config` call nothing that fabric overrides. Only
  `no_tasks_given` does (A1).
- Threads: agree (see above), and J5 (below).

**(b) `@opens`.** See J2 below. The ledger is consistent at all 12 sites:
the 6 `@opens` decorator sites have no edge, the 5 calls of a decorated
method (`runners.py:19`, `transfer.py:33`, `executor.py:48`,
`group.py:148`, `158`) call `opens`, and `opens` calls the method at 30:18.

**(c) Default rejections.** I read every site of
`--report fabric --default` for both candidates: 57 sites for `__eq__`,
and 49 for `__hash__` (the same sites without the 8 comparisons). The keys
and operands are str, int, tuples of str and int, and sockets and channels
in a list (`r` of `select`, which hashes nothing). No Connection appears.
All 106 decisions are right. The 6 `GroupResult` key sites accept both
candidates (J8): two equal Connections in one group reach `__eq__` at the
four `results[cxn]` sites, and at `_bifurcate` two keys can still share a
hash (ports that differ by 2**61 - 1; also `hash(-1) == hash(-2)`). This
follows the README's netaddr precedent. I agree.

**(d) Names of outside callees.** The names follow J1 consistently. A class
that fabric imports keeps its import path (`invoke.Context`,
`invoke.config.Config`). An inherited method is named through the base that
fabric names (`invoke.Context._set`, `invoke.util.ExceptionHandlingThread.join`).
A paramiko object is named by its defining module. This matches the
micro-benchmark rules ("Functions of a module", "Methods", "Inherited
methods"). The only inconsistencies are A2 and A3. 24 names (31 edges) rest
on the class of an object that invoke or paramiko returns, which cannot be
read here: `paramiko.channel.Channel` (10 names, 13 edges),
`paramiko.sftp_client.SFTPClient` (8, 11), `paramiko.transport.Transport`
(4, 5), `invoke.config.DataProxy.setdefault` (1, 1), and the `dict` of
`SSHConfig.lookup` (1, 1). These return types are part of documented APIs,
so I consider the names likely right.

**Functions that no site calls.** The graph has 35 nodes without a caller:
12 modules and 23 functions. These are the functions that `fabric.md`
lists, without `expand_calls`, which calls itself. After A1,
`Fab.core_args` has a caller.

**Rejections and notes.** I read all 86 rejection lines and 77 notes. Each
reason holds. J4 (`DataProxy.setdefault`), J7 (`map` on both Python
versions), J9, J11 (the Windows branch: `getpass.getuser` raises
`ImportError` there without `pwd`), J12, J13 and J14 agree with my reading.

## The writer's judgement calls that need a ruling

| Call | The ruling that the nearest rule supports | Edges it changes |
|---|---|---|
| J1, naming through the import path | Keep. Micro-benchmark "Names": a function of a module by the path that the code imports; a method by the public path of the receiver's class; an inherited method through the class that the code names. Two parts of J1 do not follow them: A2 and A3. | 0 for the import paths; -2 (A2) and +1 (A3) |
| J2, the `@opens` wrapper | The wrapper is the callee, and it calls `opens` back. Micro-benchmark "Nodes": a function that library code generates (here by `exec` in `FunctionMaker`) has no node and counts as code outside; "Callbacks": the package function that it calls belongs to the calling package site. The cases `dynamic/exec_defines_function` (`generated()` gives `main -> main.helper` and no edge for `generated`) and `stdlib_classes/dataclass_post_init` decide it. A direct edge to the method does not happen: `opens` is called first. decorator 5 makes a named closure (`decorator.decorate.fun`), but it was released after the commit, so the ruling on versions admitted at the commit excludes it. | 0 (keep the ledger). The direct reading would replace 5 edges `-> opens` with 5 edges to the methods. |
| J5, the handler that paramiko's Transport thread calls | `Connection.open -> forward_remote.callback`, at 524:28. Micro-benchmark "Callbacks": the `run` of a thread belongs to the scope that calls `start()`, and an event-loop callback to the scope that runs the loop, not to the scope that registers it. `SSHClient.connect` starts the Transport thread (from memory of paramiko); `request_port_forward` only stores the handler. | 0 (keep). Putting it at 867:48 would move 1 edge. |
| J10, a library default class | Keep `invoke.config.Config` at 95:40. B2 counts "the package's defaults"; `Fab` inherits `Program.__init__`, so invoke's default `config_class` is the default of `Fab`'s constructor. It is not a client value (B5 is about what the client supplies), and `Fab` is public (C). | 0 (keep). Removal would be -1. |

## Remarks

- **R1 (site finder).** Two calls of a value are not flagged as value
  sites: `debug(...)` (8 sites), because `util.py:10` binds `debug` with
  `globals()[x] = ...`, not with an assignment to the name; and
  `self.config_class(...)` (`main.py:95`), because library code
  (`Program.__init__`) assigns the attribute. The writer found both. The
  README section "Limits of the site finder" could list this case.
- **R2 (process).** One read-only listing (`wc`, `ls`, `git log -1`) ran
  with the checkout as working directory, against the rule "never cd into
  it". It wrote nothing and ran no project code.

## Independent third pass (2026-11-16)

The auditor froze a substantive source-only prose model and complete AST/site
inventory before inspecting the graph or ledger. The model is not an exact
independent pair graph. Full comparison retained all 353 edges, all 428
site-target relations, and all 93 nodes. The review covered all 1,038 sites,
375 ledger entries, 663 omitted sites, inherited/decorated callbacks,
argument binding, zero-edge bodies, supported branches, and default
rejections. The graph and ledger require no change. Histories are append-only.

Invoke/decorator source was read only where Fabric definitions cross a base
or decorator. Ordinary missing thread dispatch, Paramiko callbacks and
subscripted missing-library returns remain opaque. Group.__init__ keeps its
existing map/extend callback placement under the same-function rule.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).

## Fourth source-first audit (2026-11-16)

A fresh audit read all 12 runtime modules before opening the baseline and
froze its role/support model, 81 functions and 1,038 sites. It then reviewed
all 353 pairs, 428 site-target relations, 375 ledger entries, 663 omitted
sites, both defaults and all 93 bodies. No missed edge or false positive
was confirmed; 93 nodes and 353 edges remain.

One metadata correction replaces the stale rejection reason at
`group.py:176:45`: the ordinary missing `ExceptionHandlingThread` does not
supply a package callback at its later start call. Package Tunnel subclasses
retain their separately justified inherited callbacks. No graph decision
changes. Normal/-O/-OO is the round-4 working scope assumption. Python 2.7
and Python 3.4+ paths remain, with release-local interpreter evidence and
retained Invoke/decorator source checked statically. No analyzed code ran.
