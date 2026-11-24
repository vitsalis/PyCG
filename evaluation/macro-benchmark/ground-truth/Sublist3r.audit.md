# Sublist3r: independent audit of the ground truth

Commit `3f5fc6da0142540c56e97c98f9925bb7d0855fb5`. Audited files:
`Sublist3r.ledger` (513 entries, 82 notes, 46 rejection lines of which 31 are
`reject *`, 2 exclusion lines for 4 nodes), `Sublist3r.json` (102 nodes, 447
edges: 143 in the package, 304 to 101 callees outside) and `Sublist3r.md`
(13 judgements). There is no trace and no `Sublist3r.rejected.json`: the
ground truth comes from reading alone. `check.py --benchmark-dir
macro-benchmark-2021 Sublist3r` reports no errors.

I read `sublist3r.py`, `subbrute/subbrute.py` (`subbrute/__init__.py` is
empty), `README.md` and `setup.py` of the project, as data. I did not run or
import the project, and I used no static analysis tool. To check the names
of standard-library callees I read the stdlib source of the local Python
3.15 (`multiprocessing/managers.py`, `queues.py`, `context.py`,
`ctypes/__init__.py`) and printed the types of `threading.Lock()`,
`re.compile()` and `hashlib.sha1()`. dnspython and requests cannot be read
here.

**Result.** 102 sites re-derived blind; all 102 agree with the ledger. No
finding changes the graph. Two low findings (F1, F2) and two remarks (R1,
R2) change notes or one ledger line. Each of the four judgement calls of
the writer follows the README's nearest rule; the rulings that I propose
keep the graph as it is (447 edges).

## Findings

| Id | Severity | Site | Evidence | Edges | Proposal |
|---|---|---|---|---|---|
| F1 | low (a callee at a site that cannot run) | `sublist3r.py` 899:65 `domain.startswith('https://')` | Line 894 returns unless `domain` matches `^(http\|https)?[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,}$` (line 893). The pattern admits no `:` or `/`, so a domain that passes never starts with `http://`. Then `not domain.startswith('http://')` (899:29) is always true, and `or` never evaluates 899:65. (I checked the pattern alone: `http://example.com`, `https://example.com` fail; `example.com`, `example.com\n` pass.) The ledger treats the unreachable 314:38 in the same way: no callee, a note. | 0: `main -> <builtin>.str.startswith` stays through 899:29 | Remove the callee at 899:65 and add a note, as at 314:38 |
| F2 | low (a judgement that is not recorded) | `subbrute.py` 556:36 `os.path.dirname(sys.executable)`, 557:39 `multiprocessing.freeze_support()` | These run only when `getattr(sys, 'frozen', False)` (554) is true, that is, in a frozen executable ("cx_freeze windows", line 555; also line 480). The ledger keeps both edges with no note, and `Sublist3r.md` has no judgement for this branch. The README does not decide it. | 0 with my proposal; -1 if the branch is judged dead (`subbrute.subbrute -> multiprocessing.freeze_support`; `os.path.dirname` stays through 560:36) | Keep the edges, record the judgement in `Sublist3r.md` and as notes at 556:36 and 557:39. Nearest rule: the platform rule ("a branch on the platform runs if a platform that the package supports takes it") with rule A. A frozen build is a way to run the module on a supported version and platform (Windows, judgement 3), and the code handles it on purpose |
| R1 | remark (note text) | `sublist3r.py` 613:54 `Resolver.query(host, 'A')[0].to_text()` -> `dns.rdtypes.IN.A.A.to_text` | dnspython cannot be read here. The stub rules of missing modules do not define `x[0]`, so the README does not decide this name. The name follows the receiver-class rule ("a method of an outside object is named by the class of the receiver") with the class that dnspython 1.x and 2.x use for IN A records, as far as I know. Judgement 11 says "from memory" for `query`, but not for this name. | 0 | Add "from memory; dnspython cannot be read here" to judgement 11 and the note |
| R2 | remark (reason) | `subbrute.py` 199:36, 209:18, 211:32 (judgement 7) | I agree that the three branches never run: `ret` is a one-element list (196, 207), and a list never compares equal to `False`. The direct basis is the definition of an edge ("`A` can call `B` when `A` runs"): the test is false for every value. The precedent that the writer cites (argcomplete's private lexer, B1) is about the state of a private class, which this case does not need. | 0 (the 3 edges stay out) | Optional: cite the edge definition in judgement 7 |

## Step 1: blind re-derivation

I made the skeleton in a scratch directory (a copy of `projects.toml` and a
link to `macro-benchmark-2021/projects`), without the ledger: 513 sites,
all of kind `call`, 2 value sites. I numbered the sites from 0 in skeleton
order and drew `random.Random(20261111).sample(range(513), 100)`, then added
the 2 value sites (no overlap): 102 sites (40 in `subbrute.subbrute`, 60 in
`sublist3r`, 2 value sites; 29 with package candidates). I wrote the
callees of each site, with my class hierarchy and my readings of the open
questions, to `$TMPDIR/macro2021-audit-Sublist3r/blind-answers.md` before I
opened `Sublist3r.ledger`, `.json` or `.md`.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random, `subbrute.subbrute` | 40 | 40 | 0 |
| Random, `sublist3r` | 60 | 60 | 0 |
| Value sites (`subbrute.py` 587:21, `sublist3r.py` 938:18) | 2 | 2 | 0 |
| **Total** | **102** | **102** | **0** |

Disagreements by class: the writer missed an edge 0; the writer has an edge
that cannot happen 0; naming only 0; the auditor was wrong 0.

My blind readings matched the writer's on each open question that the
sample touched: Windows supported (`colorama.init` at 55:22,
`threading.Thread.__init__` at 41:41, `<builtin>.list.append` at 271:26);
Python 3 names for the Python 2 modules (`urllib.parse.urlparse` at
902:38); no edge at the unreachable 314:38; the receiver sets of
`enumratorBase.enumerate` (233:40, 240:46, 242:41, 254:30); the outside
names `multiprocessing.queues.Queue.*`, `multiprocessing.managers.ListProxy.append`,
`_hashlib.HASH.hexdigest`, `re.Pattern.findall`, `dns.resolver.Resolver.query`.

## Step 3: exhaustive checks

**Dispatch over the class hierarchy (B1).** `enumratorBase` and
`enumratorBaseThreaded` are plain public classes. Five engines (Google,
Yahoo, Ask, Bing, Baidu) inherit `enumratorBase.enumerate`; six (Netcraft,
DNSdumpster, Virustotal, ThreatCrowd, CrtSearch, PassiveDNS) override it.
A bare base gets `None` from `generate_query` and fails at line 228. So
227:40 has 6 callees (with `enumratorBase.generate_query`), and the later
sites of `enumerate` have only the five engines: `get_page` 3 callees
(233:40, 247:40), `check_response_errors` 3 (240:46), `extract_domains` 5
(242:41, `enumratorBase.extract_domains` rejected), `should_sleep` 4
(254:30), `send_req` 1 (237:33, `Virustotal.send_req` rejected).
`self.enumerate()` (269:37) has 7 callees. In each engine's own methods
`self` is that engine: no class derives from an engine. Every row is the
same as the ledger.

**`start()` and what the library calls back.** Each receiver and callback
is in the ledger:

| Site | Receiver | Callees |
|---|---|---|
| `sublist3r.py` 940:19 `enum.start()` | the 11 engine objects of 938:18; none overrides `run` | `multiprocessing.Process.start`, `threading.Thread.start` (Windows), `sublist3r.enumratorBaseThreaded.run` |
| `subbrute.py` 442:34 | the `verify_nameservers` of 441 | `multiprocessing.Process.start`, `threading.Thread.start` (Windows), `verify_nameservers.run` |
| `subbrute.py` 467:21 | each `lookup` of 466 | the same two, `lookup.run` |
| `sublist3r.py` 651:20 | `threading.Thread(target=self.check_host)` of 650 | `threading.Thread.start`, `DNSdumpster.check_host` |
| `sublist3r.py` 876:20 | `threading.Thread(target=self.port_scan)` of 875 | `threading.Thread.start`, `portscan.port_scan` |
| `sublist3r.py` 106:29 `parser.parse_args()` | argparse calls `self.error(msg)`, the instance attribute `parser_error` of line 96 | `argparse.ArgumentParser.parse_args`, `sublist3r.parse_args -> sublist3r.parser_error` |
| `sublist3r.py` 963:28, `subbrute.py` 404:25 | `sorted` calls the key | `subdomain_sorting_key`; `extract_subdomains.<lambda1>` |

The constructor sites (41:41, 180:41, 650:33, 875:33) only store the target
and reject it, which is right: `verify_nameservers` and `lookup` override
`run`, so `start()` runs the override and never the stored `self.run`.
`max(count, key=count.get)` (502:25, 504:25) calls back a library method: no
edge. `type=int` of argparse: no edge. No other package function is passed
to library code.

**Dead branches that the writer judged.** 199:36, 209:18, 211:32 (judgement
7): right (R2). 311:41 and 314:38 (judgement 8): right; the stdlib
signature is `get(self, block=True, timeout=None)` (`multiprocessing/queues.py:96`).
The sites after 228 for a bare base: right. One more dead site that the
ledger keeps: 899:65 (F1). `lookup.check` line 278 (`retries > 3`) is also
dead (line 218 resets `retries`, and the test at 273 returns at 3), but it
has no call.

**Functions without a caller.** Only `enumratorBase.extract_domains`: every
receiver that reaches 242:41 overrides it. Right.

**Special methods and properties.** The package defines none apart from
`__init__`, no class attribute and no `__getattr__`. So no implicit site has
a package candidate, as the checker says. No default rejection exists.

**Rejections, exclusions and notes.** I read all of them. Each rejection
names a receiver or a global name that decides it. The two exclusion lines
are right: `chosenEnums` holds only the 11 engines; subbrute's `parser` is
an `optparse.OptionParser` whose `error` attribute the package never
assigns. Statistics of `Sublist3r.md` match the ledger (558 callee lines,
46 rejections, 31 `reject *`, 2 exclusion lines, 82 notes, 447 edges).

**Lock of `DNSdumpster.check_host` (judgement 9).** Right:
`super().__init__` (604) stores the default `lock=threading.Lock()` of line
260 over the `BoundedSemaphore` of line 602. `type(threading.Lock())` is
`_thread.lock`; on Python 3.13 and later `threading.Lock` is that type, so
`threading.Lock.acquire` is an alias of `_thread.lock.acquire`.

**Outside names.** Each doubtful name, the rule that decides it, and
whether it is the receiver's class:

| Name | Rule | Receiver's class? |
|---|---|---|
| `multiprocessing.Manager`, `multiprocessing.Queue`, `multiprocessing.freeze_support` | functions of a module: the path that the code imports (micro-benchmark "Names") | not a method (in Python 3, bound methods of the default context, `context.py:50, 101`) |
| `multiprocessing.managers.SyncManager.list`, `.dict` | methods: the class of the receiver; `Manager()` returns a started `SyncManager`, and `register` sets `list` and `dict` on that class (`managers.py:738-739, 1278-1279`), so they have an attribute path | yes |
| `multiprocessing.managers.ListProxy.append` | the class of the receiver, also when it inherits the method (README); `append` is made by `exec` in `MakeProxyType` (`managers.py:978`) on `BaseListProxy` | yes (`managers.py:1170`) |
| `multiprocessing.queues.Queue.put`, `.get`, `.get_nowait` | the class of the receiver (`context.py:101` returns it) | yes |
| `multiprocessing.Process.__init__`, `.start`, `.join`; `threading.Thread.*` on Windows | inherited methods: named through the outside class that the code names | the outside base of a package class, as the rule asks |
| `dns.resolver.Resolver`, `dns.resolver.Resolver.query` | dnspython cannot be read: missing-module rule; it gives the receiver's class | yes |
| `dns.rdtypes.IN.A.A.to_text` | not decided by the README; receiver-class rule from knowledge of dnspython (R1) | yes, if memory is right |
| `requests.Session`, `requests.Session.get`, `.post` | the path that the code uses; the class is `requests.sessions.Session` | yes (public alias) |
| `requests.packages.urllib3.disable_warnings` | the path that the code imports | not a method |
| `_thread.lock.acquire`, `.release` | the class of the receiver (judgement 9) | yes |
| `ctypes.CDLL.__init__._FuncPtr.__call__` | calls of instances (`<class path>.__call__`, also for a private class) with the rule for definitions without an attribute path; the class is defined in `CDLL.__init__` (`ctypes/__init__.py:410-418`) | yes (Windows only) |
| `_hashlib.HASH.hexdigest`, `re.Pattern.*`, `io.TextIOWrapper.*`, `collections.Counter.pop`, `socket.socket.*`, `threading.BoundedSemaphore.*` | the class of the receiver (types checked on Python 3.15) | yes |

I found no wrong outside name and no missing outside callee.

## The writer's judgement calls: proposed rulings

| Judgement | Ruling that the nearest README rule supports | Rule | Edges vs the ledger |
|---|---|---|---|
| 6. Signal handler stored by `signal.signal` (`subbrute.py:545-548`) | No edge `signal_init -> killproc`, as the ledger. `signal.signal` stores the handler. Only the terminal sends SIGINT, SIGTSTP, SIGQUIT; the package sends only SIGKILL (512), which no handler catches. No package call makes the handler run. | Callbacks: a callback belongs to the scope whose call made the library run it (`start()`, `asyncio.run`) | 0 (the other ruling: +1) |
| 3. Windows branches (classifier `POSIX :: Linux` only) | Windows is supported, as the ledger. The project README documents a Windows install (`README.md:31-33, 44-47, 66-69`) and the Windows colour libraries (`98-101`); the code handles Windows on purpose (`sublist3r.py:42-59`, `subbrute.py:33-36, 503-510`). Classifiers list platforms; they do not exclude others. The 2021 entry already takes the supported versions from the README. | Judgements: "a branch on the platform runs if a platform that the package supports takes it" (netaddr) | 0 (the other ruling: -12, the edges that judgement 3 lists; I counted the same 12) |
| 8. `self.in_q.get(blocking = False)` (`subbrute.py:311:41`) | No edge at 311:41; 314:38 is unreachable, as the ledger. The rule is stated for any call, not only for package callees. | Edges: "a call that cannot bind its arguments raises `TypeError` before the callee starts: no edge" | 0 either way: `lookup.run` calls `Queue.get` at 306:33 and `Queue.put` at 323, 325, 354 |
| 2. Python 2 names (`urlparse`, `urllib`) | Python 3 names only, as the ledger. The sites run on both versions; only the module bound to the name differs (`sublist3r.py:26-31`). The README names the builtin callees of Python 2 code by the Python 3 type; it does not decide renamed stdlib modules, and the same reasoning gives their Python 3 names. | Judgements: Python 2 builtin callees have the Python 3 name of the type (pypinyin) | 0 (the other ruling: +9, `urlparse.urlparse` from 8 functions and `urllib.unquote` from `create_cookies`) |

## README and tools

The tools worked as the README says. The README does not decide three
things that this project raises: a branch on a frozen interpreter (F2), the
name of a value that subscription of a missing-module stub returns (R1),
and stdlib modules that Python 3 renamed (judgement 2). The proposals above
use the nearest rules; the lead rules.


## Round 3 independent source audit (2026-11-16)

This review read all three analysed modules and the README/setup support
metadata before opening this project's graph or ledger. The source model
was frozen at 2026-11-16T13:37:52.535970Z. It is a prose model with a full
AST and site inventory, not an independently enumerated exact graph.

The review compared all 457 baseline pairs, all 513 explicit ledger sites,
and all 1,219 omitted implicit sites. It checked all 102 bodies, including
15 zero-edge bodies, both value sites, four excluded nodes, and the absence
of default rejections. It checked argument binding at 164 own-callee site
occurrences using AST signatures and inspected callback argument supply.
No edge correction is proposed: 143 internal and 314 outside edges remain.

The review checked Python 2/3 and Windows/POSIX branches; own Process/Thread
callbacks; the overwritten DNSdumpster lock; the base enumerate None-return
barrier; dead list-versus-False branches; Queue.get's invalid keyword;
missing-library paths and opaque subscript values; generated proxy methods;
error paths; and package versus client roles under A/B1-B5/C. Standard
library version/name evidence is recorded in the round-3 review artifacts.
No target, dependency, test, example or generated source was executed or
imported. No network enumeration ran. There is no project trace; all 457
edges remain source-derived additions. The historical text above is kept
byte for byte. Machine-readable evidence and replay hashes are in
`Sublist3r-review.json` and `Sublist3r-agent/` of the round-3 audit.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 source-first audit (2026-11-16)

All 457 baseline pairs and 102 nodes remain: zero false positives, zero
missing edges. All 1,732 sites were reviewed: 513 explicit ledger entries
and 1,219 omitted implicit sites, with 570 site-target relations. Coverage
includes all 102 bodies (15 empty), nine explicit no-callee sites, both value
sites, four excluded nodes and no default rejections. An inert AST signature
audit checked 164 source-authored callee relations and callback arguments.

The review retains the constructor/MRO and base-None cutoffs, Windows
Process/Thread rebinding, callback ownership, overwritten DNSdumpster lock,
Queue.get binding failure, dead list-False branches, missing-library opacity,
generated proxy exclusion, and historical outside names. No executable assert
or docstring-dependent branch occurs. CPython scope is Python2.7 and Python3;
3.4 is recommended, not a lower bound, and no explicit alternative interpreter
support was found. Normal/-O/-OO is a working assumption, not user approval.

One metadata group corrects the current Statistics table's source-site
denominator; its old 513 count covered only explicit calls. The previous
round3 append already stated both explicit and omitted counts. New audit
evidence and repeated scope prose are not additional metadata defects.

Source, inputs and inventories were frozen before baseline comparison.
No target, dependency, test, generated code, PyCG or network enumeration ran.
There is no trace; all 457 edges remain from source reading. Root verification,
independent final review and installation follow this handoff.
