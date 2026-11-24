# fabric: judgements of the ground truth

Commit `34edfe4` (2020-01-10; the 2.0 branch, 11 commits after the tag
2.0.5). Analysed source: `fabric/`: 12 modules, 81 functions, 17 classes.
Supported: Python 2.7 and 3.4+ (README.rst:4 and installing.rst:105), on
POSIX and Windows. The classifiers impose no upper bound. `setup.py:67-71` requires `invoke>=1.0,<2.0` and `paramiko>=2.4`.

The ledger is `fabric.ledger`; the graph `fabric.json` is generated from it.
There is **no trace**: invoke 1.x does not import on Python 3.12 and later
(`projects.toml`). The ground truth comes from reading alone, so there is
no `fabric.rejected.json`. The ledger was first written without the
library sources. After the audit (`fabric.audit.md`), every statement about
invoke and paramiko was checked in the source archives of invoke 1.4.1 and
paramiko 2.7.1 (both admitted at the commit), read only. "Rulings after the
audit" and "Verified in the library sources" below give the result.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in fabric-review.json (audit record `2026-11-15/fabric-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 341 | 1 | 13 | 353 |

- Normalize six's library-only Python 2 `StringIO` difference to
  `io.StringIO`; the package has no Python-version branch here.
- Seven Invoke configuration operations can format a documented gateway
  `Connection` and call its `__repr__`.
- The optional external decorator 5 branch supplies named `dec` and `fun`
  closures. Add the module decorator edge and five wrapper-call edges;
  retain the package `opens` callbacks.

## Architecture, as the ledger uses it

- `Connection` (`connection.py:33`) subclasses invoke's `Context`, a
  `DataProxy`. It keeps an SSHClient, its missing-library transport result,
  and either a Fabric Config or an ordinary InvokeConfig.clone result.
  Six methods carry `@opens` (586-780), a decorator made
  with `decorator` (27).
- `Config` (`config.py:12`) subclasses invoke's `Config`. It overrides
  `__init__`, `clone`, `_clone_init_kwargs` and the staticmethod
  `global_defaults`, which sets `runners.remote` to `Remote` (244).
- `Remote` (`runners.py:4`) subclasses invoke's `Runner`. invoke's
  `Runner.run` calls its methods back.
- `TunnelManager` and `Tunnel` (`tunnels.py`) subclass invoke's
  `ExceptionHandlingThread`, whose `run` calls `self._run()`.
- `Group` is a `list` of Connections. SerialGroup puts those Connections
  in GroupResult keys; ThreadingGroup keys from outside results stay opaque.
- `Fab` (`main.py:18`) subclasses invoke's `Program`; `FabExecutor` and
  `ConnectionCall` (`executor.py`) subclass `Executor` and `Call`. invoke's
  `Program.run` calls their methods; the client calls `Program.run` (the
  console script `fab` runs `fabric.main:program.run`), so these methods
  have no package caller.

## Judgements

**J1. Names of invoke and paramiko callees.** Ordinary missing-library
calls retain their imported attribute/call paths. Reading a dependency
source does not make those calls transparent. Thus a Connection's transport
has path `paramiko.client.SSHClient.get_transport`; its session methods
extend that path through `open_session`. Transfer methods extend
`paramiko.client.SSHClient.open_sftp`. The lookup result's `get` is
`paramiko.config.SSHConfig.lookup.get`, not `dict.get` or `SSHConfigDict.get`.
Package-return descriptions do not replace these known origins.

The narrow base/decorator exception still applies when a package definition
actually traverses library code: Invoke bases of Config, Connection, Remote,
Fab, ConnectionCall and the tunnel classes; and the decorator wrapping
`opens`. It is not an exemption for every Invoke object. Plain external
Config.clone, DataProxy.setdefault and ExceptionHandlingThread calls remain
ordinary missing-library calls, with no package callbacks.

Concrete input contracts still apply under B4. Connection's `config`
parameter is documented as Fabric Config or Invoke Config. A vanilla
InvokeConfig's ordinary clone result is stored as an imported-path stub,
so its later `base_ssh_config.lookup`, `connect_kwargs.setdefault`, `clone`,
`runners.remote`, and `gateway` method chains keep that origin. Recursive
gateway construction crosses the documented config parameter boundary
again; it admits the same Config roles, not an unlimited chain of inferred
outside types. TunnelManager's constructor similarly documents its transport
as `paramiko.transport.Transport`. The stored transport keeps that name;
its ordinary `open_channel` result remains a `Transport.open_channel` stub
through the close, recv and sendall calls in Tunnel. Tunnel's generic "SSH channel" prose does
not name a concrete Channel parameter type.

**J2. `@opens` and the generated wrappers** (`connection.py:27-30`).
Vendored decorator 4.0.11 generates the decorator and wrappers with exec.
Generated functions have no node. Applying the decorator does not run the
original `opens`; calling the wrapped method does. `opens` calls `open`
and one of its six captured undecorated methods. Calling either generator
method counts before it is iterated.

The optional external decorator 5.0.9 defines source closures `dec` and
`fun`: the six decorator sites call `decorator.decorator.dec`; admitted
method-call sites call `decorator.decorate.fun` and the package `opens`.
There are four such sites: `Remote.start`, `Transfer.sftp`, `SerialGroup.run`
and the anonymous task. The CLI documentation explicitly names
Connection.run for that anonymous task (sites/docs/cli.rst:109-113), so
its context role remains admitted independently of missing Task dispatch.
`thread_worker` has no such parameter contract or admitted library flow;
its two opaque method calls have no named callees.

**J3. Callbacks through Invoke.** The base exception applies at the
package definition that actually traverses the library. Connection's
inherited `_run` and `_sudo` helpers dispatch on its admitted Remote
runner and reach all nine Remote overrides: start, read_proc_stdout,
read_proc_stderr, _write_proc_stdin, process_is_finished, send_interrupt,
returncode, generate_result and stop. `local` uses Invoke's Local default.

Fabric Config's base initializer calls its global_defaults. Its explicit
base clone calls the package _clone_init_kwargs and constructor; the base
_clone_init_kwargs can call the admitted into.global_defaults. The vanilla
InvokeConfig.clone call in Connection.__init__ is ordinary and supplies no
such callback; the direct Fabric Config construction at line 256 remains.

Five callers can format a documented gateway Connection inside inherited
configuration code: Fabric Config.__init__ and clone, and Fab.create_config,
load_collection and update_config. The ordinary DataProxy.setdefault call
adds no repr callback. An intervening package method owns its own calls.

Package TunnelManager and Tunnel inherit ExceptionHandlingThread; calling
start on those definitions dispatches their _run methods. The plain
ExceptionHandlingThread constructed in ThreadingGroup is an ordinary missing
library object: its start does not call thread_worker back. Its return
objects do not reveal kwargs or Connection keys.

Fab.no_tasks_given calls the Program base, whose print_help reads
initial_context and calls the package core_args override. The other explicit
Program base methods used here do not invoke a Fabric override.

**J4. `connect_kwargs.setdefault`** (`connection.py:363`). An explicit
connect_kwargs argument has the documented dict type. A real Fabric Config
uses its inherited lookup implementation, which produces a DataProxy over
the nested dict. The third origin is the ordinary vanilla-config clone
result: `invoke.config.Config.clone.connect_kwargs.setdefault`.
The three names are therefore that path, `<builtin>.dict.setdefault`, and
`invoke.config.DataProxy.setdefault`. Calling a plain DataProxy method does
not itself traverse a package subclass definition, so its internal merge
and repr callback are excluded.

**J5. The handler of `forward_remote`** (`connection.py:851, 867`).
Neither ordinary SSHClient.connect nor request_port_forward is transparent
under the missing-library rule. Neither calls the package callback back in
this graph. Rule A still gives the nested callback its own socket, Tunnel,
thread-start and append edges, with enclosing local-host/port/list captures;
its channel argument remains opaque.

Within forward_remote, the tunnels list starts empty and only that callback
could append to it. No admitted callback execution mutates this list, so the
cleanup-loop calls of Event.set and thread.join have no receiver. The
ordinary request/cancel calls keep their get_transport attribute paths.

**J6. Optional imports of six and decorator** (`connection.py:4-11`,
`group.py:1-4`). Both import arms remain in scope. StringIO keeps
`invoke.vendor.six.StringIO` and `six.StringIO`; Queue keeps
`invoke.vendor.six.moves.queue.Queue` and `six.moves.queue.Queue`, with
the same prefixes on empty/get calls. These are ordinary missing imports,
so their aliases are not resolved by reading six. The concrete-class alias
rule does not apply to unknown missing-library values. Both decorator
imports remain; their actual use to define package wrappers permits the
narrow source inspection described in J2.

**J7. `map(Connection, hosts)`** (`group.py:70`). On Python 2, `map` calls
`Connection` at once; on Python 3, `list.extend` calls it when it iterates.
`Connection.__init__` is a callee of both sites.

**J8. `Connection.__eq__` at GroupResult key sites** (`group.py:148,
150, 248, 250`). SerialGroup holds admitted Connections directly. Repeated
hosts can give equal keys; distinct integer ports separated by the hash
modulus can give distinct colliding keys. GroupResult._bifurcate also receives
these Connection keys. Thus both __hash__ and __eq__ occur at these four
sites. ThreadingGroup's keys at 194 and 207 instead come from unpacked or
subscripted ordinary missing-library results. Those values are opaque and
do not supply Connection callbacks.

**J9. `print(...)`** (`main.py:21-22`). A call on Python 3; a print
statement on Python 2. The edge `<builtin>.print` is that of Python 3.

**J10. `self.config_class(lazy=True)`** (`main.py:95`). `config_class` is
an argument of invoke's `Program.__init__`, which `Fab` inherits. The
package passes fabric's `Config` (`main.py:147`). A client that makes a
`Fab` without it gets invoke's default, invoke's `Config`. That value is
neither a client object nor a package value; the ledger keeps it as the
inherited default (callee `invoke.config.Config`). Global B2 includes
the package defaults, including the constructor default inherited by `Fab`.

**J11. The Windows branch of `get_local_user`** (`util.py:31-44`). On
Python 2.7 and 3.4 to 3.6 on Windows, `getpass.getuser` raises
`ImportError` (no `pwd`) when no user variable is set. Windows is a
supported platform, so `win32api.GetUserName` is an edge. No pywin32
implementation source is needed for this ordinary missing-library call:
the name is its imported access path.

**J12. The file-like `local` of `Transfer.put`** (`transfer.py:260, 262,
265`). `local.tell()` and `local.seek()` act on the client's file-like
object (documented only as "a file-like object"). B5: no callee; each site
has a note.

**J13. Python 2 names.** No version branch exists in the source. Strings
and their methods have the Python 3 names (`<builtin>.str.rsplit` for a
`unicode` host on Python 2); `IOError(...)` is `<builtin>.IOError`, the
name in `builtins` (`config.py:185`).

**J14. `super(dict, self).__init__`** (`group.py:236`). `super(dict, self)`
skips `GroupResult` and `dict`; the method is `object.__init__`:
`<builtin>.object.__init__`. With any argument it raises `TypeError`; the
package calls `GroupResult()` without arguments.

## Scope rules

**B1. Receivers.** Connection.config is either the admitted Fabric Config
or the stored result of an ordinary vanilla InvokeConfig.clone. Later direct
attribute/call chains preserve that result path (J1). Remote's documented
context role is Connection. A gateway explicitly supplied in its documented
role can be a Connection or string. A fallback from the stored clone result
can instead retain `invoke.config.Config.clone.gateway`; its open and
transport.open_channel calls retain that path.

**B2. Arguments.** Connection.__init__ documents its config parameter as
Fabric Config or Invoke Config. Remote is the documented package default for
runners.remote; other client runner classes stay opaque. Transfer's
connection role names Connection. TunnelManager documents concrete Transport
for its constructor input. Tunnel receives the corresponding open_channel
stub, or an opaque remote-handler argument, together with package-created
sockets and Events. Private _run methods use their actual package start
flows; a generic channel description does not admit Paramiko Channel.
The anonymous task retains its documented Connection role. thread_worker
has no concrete parameter contract and no admitted ordinary-thread callback
flow, so its cxn/queue methods remain opaque.

**B4. Concrete outside types.** `connect_kwargs` is a `dict` (documented,
`connection.py:219`): `connect_kwargs.get` is `<builtin>.dict.get` (354).

**B5. Client objects.** The file-like `local` (J12); the file-like object
of `Transfer.get` (`getfo` writes into it: client code).

**C. Public and private.** Public APIs have a reachable path under
`fabric.` with no underscore component, except dunder names such as
`__init__`. Explicitly documented private APIs remain private. Private
helpers take values from actual package callers; an uncalled private
function uses the global rule B fallback for its parameters. Local
callbacks such as `anonymous` and `forward_remote.callback` retain their
enclosing captures and admitted consumer arguments. Their lexical names
are not public access paths. `opens` is exposed as a decorator, whose
wrapper retains its captured method. Documented public factory outputs
retain the factory's admitted arguments and actual captures.

## Default rejections

| Candidate | Sites decided | Accepted explicitly at |
|---|---|---|
| `Connection.__eq__` | 57 | `group.py:148:24, 150:24, 248:31, 250:32` (J8) |
| `Connection.__hash__` | 49 | the same four sites |

Both defaults decide only implicit sites (subscripts, `in` tests and
comparisons of primitive keys, tuples, sockets and opaque outside values).
ThreadingGroup key sites reject Connection explicitly because the values
come from opaque library result unpacking/subscripts. No explicit call
site has either candidate.

## Value sites

| Site | Callees |
|---|---|
| `connection.py:30:18` `method(self, *args, **kwargs)` | the six methods decorated with `@opens` (J2) |
| `connection.py:608:44`, `623:44` `self.config.runners.remote(self)` | `invoke.Runner.__init__` for Remote; `invoke.config.Config.clone.runners.remote` for the stored ordinary clone result |
| `group.py:81:20` `cls()` | `Group.__init__` (inherited by `SerialGroup` and `ThreadingGroup`) |

Two more sites call a value that the site finder does not flag:
`main.py:95:40` (J10), and every `debug(...)`, which is `log.debug`
bound at `util.py:9-10` (`logging.Logger.debug`).

## Functions that no site calls

- Client API: `Connection.get`, `put`, `local`, `__enter__`, `__exit__`,
  `__lt__`; `Group.from_connections`, `Group.run`,
  `Group.get`, `SerialGroup.run`, `ThreadingGroup.run`;
  `GroupResult.succeeded`, `failed`.
- Called by invoke under `Program.run`, which the client calls: five `Fab`
  methods (`print_version`, `load_collection`, `no_tasks_given`,
  `create_config`, `update_config`), `FabExecutor.dedupe`,
  `ConnectionCall.make_context`, and `FabExecutor.expand_calls.anonymous`
  (the body of the task that invoke's `Executor.execute` runs).
  `Fab.core_args` has a caller since ruling A1 (`no_tasks_given`), the
  property `_remainder_only` is read by `load_collection` and
  `no_tasks_given`, and `FabExecutor.expand_calls` only calls itself.
- `forward_remote.callback` and `thread_worker` have no admitted package
  caller under the ordinary missing-library rule. The callback keeps its
  independent body edges; thread_worker has only opaque receiver calls.
- `Group.run` and `Group.get` only raise `NotImplementedError`.

## Rulings after the audit (earlier audit)

The blind audit (`fabric.audit.md`) re-derived 103 sites; 101 agreed. The
lead ruled:

| Ruling | Change | Edges |
|---|---|---|
| A1 | `main.py:89:44`: add `Fab.core_args` (invoke 1.4.1 `program.py:535-539, 658-666, 641-650`); J3 corrected | +1 (in the package) |
| A2 | one class is one callee: `Queue()` is `queue.Queue` (`group.py:172:22`); `StringIO(...)` is `io.StringIO` and `StringIO.StringIO` (`connection.py:545:36`); the two `decorator.decorator` stay | -1 (the queue; StringIO keeps two names) |
| A3 | `connection.py:291:48, 296:52, 320:50`: `<builtin>.dict.get` and `paramiko.config.SSHConfigDict.get` | +1 |
| J1, J2, J5, J10 | kept as written | 0 |

Result: 341 edges (100 in the package, 241 outside), from 340.

## Verified in the library sources (earlier concrete-library audit)

After the earlier rulings, invoke and paramiko behavior was checked in
invoke 1.4.1 and paramiko 2.7.1. The following records those implementation
facts and that audit's result. Source inspection alone does not authorize
ordinary missing-library callbacks or concrete returned-class names; the
current J1-J8 above apply the global rule and supersede those graph
inferences. The narrow base/decorator findings still apply.

- **`Remote` callbacks (J3), all nine confirmed.** `Context._run` and
  `_sudo` call `runner.run` (`context.py:99-101, 176-229`). `Runner.run`
  (`runners.py:362-366`) runs `_run_body`: `start` (411), the IO threads
  (418-420) of `handle_stdout` -> `read_proc_stdout` (737) and, without a
  pty, `handle_stderr` -> `read_proc_stderr` (622, 750); `write_proc_stdin`
  -> `_write_proc_stdin` (960) from `handle_stdin` (822) and `respond`
  (884); `wait` reads `process_is_finished` (942); `send_interrupt` on
  `KeyboardInterrupt` (444); `returncode` (570); `generate_result` (573,
  and 407 for a dry run); `stop` in `_stop_everything` (371). Remote
  overrides no other method that `Runner` calls (`close_proc_stdin`,
  `kill`, `should_use_pty` stay invoke's). `Runner.__init__` (61-107),
  `Result.__init__` (1401-1423), `Context.__init__` (`context.py:36-63`)
  and `Context.run` with `Local` (80-94) call no package code.
- **`Config` callbacks, confirmed.** `Config.__init__` calls
  `self.global_defaults()` (`config.py:582`); the other methods it calls
  are not overridden. `Config.clone` (979-1073) calls
  `self._clone_init_kwargs(into=into)` and the class (1032), then
  `load_base_conf_files` and `merge`; `_clone_init_kwargs` calls
  `into.global_defaults()` (1092); `clone` admits only an `into` that
  subclasses the receiver's class (1018), so fabric's `Config` fits.
  `DataProxy._get` wraps a nested dict in a `DataProxy` (169-187), whose
  `setdefault` is its own method (281-294): J4 confirmed.
- **Threads, confirmed.** `ExceptionHandlingThread.run` (`util.py:210-245`)
  calls `self._run()` if it exists, else `Thread.run`, which calls the
  target.
- **`Program`, earlier A1 check.** `print_version` (655),
  `core_args` (35-138), `load_collection` (684-709), `update_config`
  (288-339) and `__init__` (176-271) call no other `Fab` override.
- **Executor and tasks.** `Call.clone` instantiates `into` with
  `clone_data()` (`tasks.py:443-471`); `Call.__init__` (371) and
  `Task.__init__` (47-110) store their arguments and do not call the body.
- **Generated wrappers (J2).** invoke vendors decorator 4.0.11
  (`vendor/decorator.py:221-255`), as J2 describes. Six 1.10.0
  (`vendor/six.py`) for A2.
- **paramiko (J1, J5, A3).** `SSHConfig.lookup` returns an
  `SSHConfigDict` (`config.py:183-237`, "versionchanged 2.5"), a `dict`
  subclass that defines only `__init__`, `as_bool`, `as_int` (623-700).
  `SSHClient.connect` makes the `Transport` and calls `start_client`
  (`client.py:370, 406`), which starts its thread (`transport.py:648,
  653`); `Transport.run` (2015) passes channel-open messages to
  `_parse_channel_open` (2864), which calls `self._tcp_handler` (2836);
  `request_port_forward` only stores it (1019-1071): J5 confirmed.
  `open_session` returns `open_channel(...)`, a `Channel` (875, 924-1013);
  `open_sftp` returns `Transport.open_sftp_client()`, an `SFTPClient`
  (`client.py:550-556`, `transport.py:1087-1097`).
- **The 24 names that depend on a returned class, all confirmed** in these
  versions: 10 methods defined by `Channel` (`channel.py:164-827`), 8 by
  `SFTPClient` (`sftp_client.py:472-785`), 4 by `Transport`
  (`open_session`, `open_channel`, `request_port_forward`,
  `cancel_port_forward`), `invoke.config.DataProxy.setdefault`, and the
  lookup dict (now two names, A3). `paramiko.agent.AgentRequestHandler.close`
  (`agent.py:339`) also exists.
- **Considered, not added.** `Config._load_file` picks a loader by the
  suffix of the file (`config.py:880`, `getattr(self, "_load_" + suffix)`).
  For the runtime file of `-f` (`Program.update_config`, `main.py:111`), a
  file named `x.ssh_file` would call fabric's `Config._load_ssh_file`. The
  suffix is a string that the client supplies, and no test or document
  uses it: not considered (B3, as for an attribute name that the client
  supplies).

**Additional source checks:** the retained audit snapshots include
Invoke 1.0.0 and 1.7.3 configuration and program code, Paramiko 2.4.0
configuration code, and external decorator 5.0.9. The second pass reads
these relevant bodies and verifies their hashes. Paramiko 2.4.0
`lookup` builds an ordinary dict; decorator 5.0.9 defines the `dec` and
`fun` closures. The audit does not exhaust every admitted release.
External six and pywin32 implementations were not independently read.

## Statistics

| | Count |
|---|---|
| Sites | 432 (333 call, 17 decorator, 1 with, 21 op, 27 getitem, 16 setitem, 1 delitem, 16 getattr) |
| Sites with candidates / value sites | 205 / 4 |
| Ledger entries | 375 |
| Callee lines / rejection lines / exclusion lines / notes | 428 / 91 / 0 / 113 |
| Default rejections | 2, deciding 57 and 49 sites, all implicit |
| Nodes | 93 (12 modules, 81 functions) |
| Edges | 353: 99 in the package, 254 to 163 callees outside |
| Trace | none: no edge confirmed, no edge rejected |

## Third source-first audit (2026-11-16)

An independent source-first review read all 12 runtime modules, inventoried all
1,038 AST call sites, and reviewed package documentation and test input roles
before opening this ledger. It then checked all 353 caller/callee pairs and
428 site-target relations, including 663 omitted sites, the two default
rejections, own-target argument binding, and every zero-edge body. No edge or
site-target correction was confirmed. The graph retains 93 nodes and 353 edges.

Fresh official source copies of Invoke 1.0.0 and 1.7.3 and decorator 4.4.2
and 5.2.1 were read statically for the narrow base/decorator exception.
Ordinary missing-library calls remain opaque imported-path stubs. The report
records their URLs and SHA-256 hashes; no package, dependency, test, example,
or generated wrapper was imported or executed. The report also separates
the frozen prose model from post-comparison refinements. There is no trace
or rejected-edge file; all 353 graph edges remain source-added.

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
