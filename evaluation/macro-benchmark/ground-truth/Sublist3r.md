# Sublist3r: judgements of the ground truth

Commit `3f5fc6d` (no release tag). Analysed source: `sublist3r.py` and
`subbrute/`: 3 modules (`sublist3r`, `subbrute`, `subbrute.subbrute`), 99
functions (1 lambda), 16 classes. `setup.py` is not analysed.

The ledger is `Sublist3r.ledger`; the graph `Sublist3r.json` is generated
from it. The project has no tests, so there is no trace and no
`Sublist3r.rejected.json`. The ground truth comes from reading alone. I read
every function. I wrote each site's decision by hand in a scratch file, and a
small script merged the decisions into the skeleton, so that the site lines
stay exactly as the skeleton prints them.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in Sublist3r-review.json (audit record `2026-11-15/Sublist3r-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 447 | 6 | 15 | 456 |

- Exclude the generated `ListProxy.append` implementation, the inferred
  DNS record method after subscription, and string methods inferred from
  opaque requests header results.
- Name the lock by its documented `_thread.LockType` path; the later
  `threading.Lock` alias does not make another class or edge.
- Include eleven historical Python 3 regex names and the two historical
  `_BoundedSemaphore` methods. The Python 3.4 recommendation is not a
  minimum supported version.

## Architecture, as the ledger uses it

- `main` (`sublist3r.py:879`) makes one object of each chosen engine class
  (`sublist3r.py:938`), starts each one (`enum.start()`) and joins it. The 11
  engine classes derive from `enumratorBaseThreaded`, which derives from
  `multiprocessing.Process` and `enumratorBase`. No engine overrides `run`, so
  each one runs `enumratorBaseThreaded.run` in a child process.
- `enumratorBaseThreaded.run` calls `self.enumerate()`. Five engines (Google,
  Yahoo, Ask, Bing, Baidu) inherit `enumratorBase.enumerate`, a loop over
  `generate_query`, `send_req`, `check_response_errors`, `extract_domains`
  and `should_sleep`. The six others (Netcraft, DNSdumpster, Virustotal,
  ThreatCrowd, CrtSearch, PassiveDNS) override `enumerate`.
- With `-b`, `main` calls `subbrute.print_target`, which iterates the
  generator `subbrute.subbrute.run`. `run` starts one `verify_nameservers`
  process and `process_count` `lookup` processes, which share three
  `multiprocessing.Queue` objects and two manager dicts.
- With `-p`, `main` makes a `portscan` and calls its `run`, which starts one
  `threading.Thread` per subdomain with the target `port_scan`.

## Scope rules

The rules A, B1-B5 and C are in `macro-benchmark/README.md`.

**A.** Every function keeps the out-edges of its body. The only function
without a caller is `enumratorBase.extract_domains` (its body has no call):
every class that reaches `enumratorBase.enumerate` past line 228 overrides
it.

**B1. Receivers.** `enumratorBase` and `enumratorBaseThreaded` are plain
public classes, so they are receivers of their own methods.
- `self.generate_query()` (`sublist3r.py:227:40`) has 6 callees: the five
  engine overrides and `enumratorBase.generate_query`, for a plain
  `enumratorBase` or `enumratorBaseThreaded`. That method returns `None`, so
  for the two base classes line 228 raises `AttributeError`. The later sites
  of `enumerate` run only for the five engines that inherit it.
- So at `sublist3r.py:242:41` the callees are the five engines'
  `extract_domains`, and `enumratorBase.extract_domains` is rejected. At
  `237:33`, `Virustotal.send_req` is rejected: Virustotal overrides
  `enumerate`.
- `self.enumerate()` (`sublist3r.py:269:37`) has the 6 overrides and
  `enumratorBase.enumerate`.
- In each engine's own methods, `self` is that engine: no package class
  derives from an engine class.

**B2, B5. Values.** No function has annotations. The CLI passes strings
for supplied `domain`, `ports`, `engines` and `savefile` options; the README
also documents comma-separated ports and engine names. Its `main('yahoo.com',
...)` example passes string domain and savefile values, but `None` for ports
and engines. The concrete string inputs support the `<builtin>.str` methods.
The queues, manager proxies and locks are the
objects that the package makes; a client's own `q` or queue is opaque.

**C.** All top-level functions and classes have public paths. Dunder
constructors remain public under the global exception; the nested
`extract_subdomains` lambda uses its lexical capture and is not an independent
client entrypoint. The README documents `sublist3r.main` as the API.

## Judgement calls

1. **Supported versions and platforms.** Python 2.7 and Python 3
   (`setup.py`: `python_requires='>=2.7'`; README supports Python 2 and 3).
   Python 3.4 is recommended, not a minimum; classifiers do not impose a
   ceiling. Historical regex and semaphore names are therefore included.
   Platforms: Linux and Windows. See judgement 3.

2. **Python 2 names.** Following the pypinyin ruling, code that runs on both
   versions gets only its Python 3 names. On Python 2, `urlparse` and
   `urllib` are the Python 2 modules (`sublist3r.py:26-31`), so
   `urlparse.urlparse(...)` (8 sites) is `urllib.parse.urlparse`, and
   `urllib.unquote(...)` (`sublist3r.py:554:83`) is `urllib.parse.unquote`,
   their Python 3 names. On Python 2, `print(...)` without
   `print_function` is a statement; the call is an edge on Python 3. The
   Python-2-only branches (`sublist3r.py:29-31`, `subbrute.py:26-27`) only
   import. Effect: no edge added or removed.

3. **Windows is a supported platform.** The classifiers name only
   `POSIX :: Linux`, but the README documents the installation on Windows
   (`c:\python27\python.exe -m pip install ...`) and the coloring libraries
   for Windows, and the code has Windows branches. By the README rule ("a
   branch on the platform runs if a platform that the package supports
   takes it"), the Windows branches run:
   - `sublist3r.py:45-59`: `win_unicode_console.enable`, `colorama.init`,
     `<builtin>.print` (module `sublist3r`).
   - `sublist3r.py:884`: `main -> <builtin>.list`; then `self.q.append`
     (`sublist3r.py:271:26`) is also `<builtin>.list.append`.
   - `subbrute.py:33-36` rebinds `multiprocessing.Process` to
     `threading.Thread` when `sublist3r` imports `subbrute` (line 21), before
     the three process classes are defined. So on Windows they are thread
     classes: `threading.Thread.__init__` at `sublist3r.py:263:41`,
     `subbrute.py:41:41` and `180:41`; `threading.Thread.start` at
     `sublist3r.py:940:19`, `subbrute.py:442:34` and `467:21`;
     `threading.Thread.join` at `sublist3r.py:942:18`.
   - `subbrute.py:504-510`: the two `ctypes` calls of `killproc`.
   Effect: 12 edges that only Windows makes. Without this judgement they go.

4. **`start()` runs `run` or the target (callback rule).** The lead's
   instruction and the README's thread rule: the `run` method that
   `Process.start` or `Thread.start` runs belongs to the scope that calls
   `start()`. Edges: `main -> enumratorBaseThreaded.run`
   (`sublist3r.py:940:19`), `subbrute.subbrute.run -> verify_nameservers.run`
   (`subbrute.py:442:34`) and `-> lookup.run` (`467:21`),
   `DNSdumpster.enumerate -> DNSdumpster.check_host` (`sublist3r.py:651:20`),
   `portscan.run -> portscan.port_scan` (`876:20`). The constructor sites
   reject the callback candidates: `threading.Thread(target=...)` and
   `multiprocessing.Process.__init__(self, target = self.run)` store the
   target. `verify_nameservers` and `lookup` override `run`, so the stored
   target `self.run` is never called through `BaseProcess.run`; `start()`
   runs the override itself.

5. **`parser.error = parser_error` (`sublist3r.py:96`).** argparse calls
   `self.error(message)` when the command line does not parse (the required
   `-d` is missing, `-t` is not an int, an unknown option). The instance
   attribute is the plain function `parser_error`, so `parse_args` calls it
   back: `parse_args -> parser_error` at `sublist3r.py:106:29`. This makes
   `parser.error` a name that the package assigns, so subbrute's
   `parser.error(...)` (`subbrute.py:587:21`) is a value site. Its `parser`
   is subbrute's own `optparse.OptionParser`, so its callee is
   `optparse.OptionParser.error`, and `parser_error` is excluded there.

6. **Signal handler: no registration edge.** `signal_init`
   (`subbrute.py:543-551`) stores `killproc` as the handler of SIGINT,
   SIGTSTP and SIGQUIT. Under the global rule, registration does not call
   the handler. A package call that waits for an installed signal can own
   its callback, but Sublist3r has no site that waits for a signal. An asynchronous
   signal during another operation adds no edge. The explicit call of
   `killproc` at `subbrute.py:491` remains; the package's `os.kill` sends
   SIGKILL, which these handlers cannot catch. All three registration sites
   reject `killproc`.

7. **Dead branches by value (`subbrute.py:197-200`, `208-212`).** `ret` is a
   one-element list (`ret = [self.resolver_q.get_nowait()]`), and
   `ret == False` is never true for a list. So `lookup.get_ns` never calls
   `Queue.put` at line 199, and `lookup.get_ns_blocking` never calls `trace`
   (line 209) or `Queue.put` (line 211). The three sites have a note and no
   callee. Effect: 3 edges not in the graph. The basis is the definition of
   an edge ("`A` can call `B` when `A` runs"): the test is false for every
   value, so no run of these functions makes these calls (audit R2).

8. **An outside call that cannot bind (`subbrute.py:311:41`).**
   `self.in_q.get(blocking = False)`: `multiprocessing.queues.Queue.get` has
   the parameters `block` and `timeout` on Python 2.7 and 3, so the call
   raises `TypeError` before the callee starts, and the bare `except` at line
   315 catches it. The README's global rule excludes a call that cannot
   bind its arguments, including this outside callee. For the package-owned
   Queue, line 314 (`self.in_q.put(False)`) is then
   unreachable. A client queue can accept `blocking` and reach its own
   `put`; both client methods remain opaque. Neither site has a named callee. Effect: no edge lost
   (`lookup.run` calls `Queue.get` and `Queue.put` at other sites).

9. **The lock of `DNSdumpster.check_host` (`sublist3r.py:611`, `621`).**
   `DNSdumpster.__init__` sets `self.lock` to a `BoundedSemaphore`
   (line 602), but then `super().__init__` (line 604) runs
   `enumratorBaseThreaded.__init__`, which stores its parameter `lock`
   (line 264). DNSdumpster passes none, so `self.lock` is the default
   `threading.Lock()` of line 260. Its documented public class path is
   `_thread.LockType`, so the callees are `_thread.LockType.acquire` and
   `.release`. The later `threading.Lock` alias is the same class, not a
   second target. `portscan` keeps its `BoundedSemaphore`: include both
   `threading.BoundedSemaphore` and historical `threading._BoundedSemaphore`
   method names across admitted Python 3 versions.

10. **Names of `multiprocessing` objects (doubtful).** I named each method by
    the public path of the class of the receiver:
    - `multiprocessing.Manager()` returns a started `SyncManager`; its `list`
      and `dict` are set on the class by `SyncManager.register`:
      `multiprocessing.managers.SyncManager.list` and `.dict`.
    - `Manager().list()` returns a `multiprocessing.managers.ListProxy`; its
      `append` is generated by `MakeProxyType` through `exec`, so it has
      no edge under the global generated-library-code rule. The Windows
      builtin `list.append` edge remains.
    - `multiprocessing.Queue()` returns a `multiprocessing.queues.Queue`:
      `multiprocessing.queues.Queue.put`, `.get`, `.get_nowait`.
    - `multiprocessing.Manager`, `multiprocessing.Queue` and
      `multiprocessing.freeze_support` are the paths that the code imports
      (bound methods of the default context). `Process.__init__`, `start`
      and `join` are named through the class that the code names:
      `multiprocessing.Process.*`.

11. **Other doubtful outside names.**
    - `kernel32.OpenProcess(...)` and `kernel32.TerminateProcess(...)`
      (`subbrute.py:506:42`, `507:38`, Windows only): `ctypes.windll.kernel32`
      is a `ctypes.WinDLL`. Its attributes are instances of the class
      `_FuncPtr` that `CDLL.__init__` defines for each library. The call is
      that class's `__call__`, named by where the class is defined, without
      `<locals>`: `ctypes.CDLL.__init__._FuncPtr.__call__`.
    - `Resolver.query(host, 'A')[0].to_text()` (`sublist3r.py:613:54`):
      subscription of an unavailable-library result provides no named
      record class or method. The `to_text` call has no callee.

    - dnspython: ordinary unavailable-library calls retain
      `dns.resolver.Resolver` and `dns.resolver.Resolver.query`, the imported
      paths. No concrete return class or alias resolution is inferred.
    - requests: the same rule retains `requests.Session`,
      `requests.Session.get` and `.post` from the imported paths.
    - `hashlib.sha1(...).hexdigest()` has both `_hashlib.HASH.hexdigest`
      and `_sha1.sha1.hexdigest`. The standard library selects its builtin
      SHA-1 implementation when OpenSSL or its SHA-1 constructor is unavailable.
      CPython 3.4 and 3.12 source names that fallback type `_sha1.sha1`; the
      Python 3.12 hashlib documentation explicitly describes the fallback.
      These are distinct receivers, not aliases. Source files, lines and
      SHA-256 hashes are in the pass-2 report (audit record `2026-11-15/pass-2/Sublist3r-review.json`).

12. **`requests.packages.urllib3.disable_warnings`** (`sublist3r.py:37:47`):
    retain the path that the module imports under the ordinary missing-library
    rule. A dependency's internal alias or vendoring layout does not change
    this name.

13. **The `__main__` blocks.** `sublist3r.py:1000-1001` and
    `subbrute.py:553-633` are code of their modules and keep their edges.
    `trace` (`subbrute.py:516`) writes only when the module global `verbose`
    is true; the `__main__` block sets it from `-v` (line 584), so its body
    edges stay.

14. **The second `startswith` in `main` (`sublist3r.py:899:65`).** An
    ordinary str domain that passes the check of lines 893-897 has no `:` or `/`, so it
    never starts with `http://`. Then `not domain.startswith('http://')`
    (899:29) is always true, and `or` never evaluates 899:65. The site has a
    note and no callee. A stateful client `startswith` can reach it, but
    its client method remains opaque and adds no named edge. Effect: no edge changes
    (`main -> <builtin>.str.startswith` stays through 899:29).

15. **The frozen branch (`subbrute.py:554-557`, audit F2).**
    `os.path.dirname(sys.executable)` (556:36) and
    `multiprocessing.freeze_support()` (557:39) run only when
    `getattr(sys, 'frozen', False)` is true, in a frozen executable (cx_Freeze
    on Windows, line 555; also line 480). A frozen build is a way to run the
    module on a supported version and platform, and the code handles it on
    purpose, so the branch runs (nearest rule: the platform rule, with rule
    A). Both edges stay, with notes. The other ruling removes 1 edge
    (`subbrute.subbrute -> multiprocessing.freeze_support`).

## Audit and the lead's rulings (earlier audit)

The blind audit (`Sublist3r.audit.md`) re-derived 102 sites with 0
disagreements. Its findings F1, F2, R1 and R2 are applied above
(judgements 14, 15, 11 and 7); none changes an edge. The lead ruled:

- **Signal handler (judgement 6): kept, no edge.** `signal.signal` stores the
  handler; the interpreter runs it when a signal arrives from outside,
  between the instructions of whatever runs then. It is an edge only at a
  package site that itself makes the signal arrive in its own process.
- **Windows (judgement 3): kept, supported.** The project's README documents
  the Windows install, so the platform branches run (12 edges).
- **Python 2 names (judgement 2): kept.** A function of a module that Python 3
  renamed is the same function: it has its Python 3 name only
  (`urllib.parse.urlparse`, `urllib.parse.unquote`). A function that only
  Python 2 has keeps its Python 2 name.
- **`in_q.get(blocking = False)` (judgement 8): kept, no edge** (a call that
  cannot bind its arguments).
- **F1, F2:** applied as judgements 14 and 15. **R1, R2:** applied in
  judgements 11 and 7.
- All other judgements stand as written.

## Value sites

| Site | Callees | Where the values come from |
|---|---|---|
| `sublist3r.py:938:18` `enum(domain, [], q=..., ...)` | the `__init__` of the 11 engine classes | `chosenEnums` holds the 11 classes of the default list (lines 926-930), or the values of `supported_engines` (lines 910-921) that `-e` selects. Excluded: `enumratorBase.__init__`, `enumratorBaseThreaded.__init__`, `portscan.__init__` |
| `subbrute.py:587:21` `parser.error(...)` | `optparse.OptionParser.error` | judgement 5. Excluded: `sublist3r.parser_error` |

## Default rejections and exclusions

No default rejection: no candidate has 50 or more sites. The many `__init__`
candidates of the explicit `X.__init__(self, ...)` and `super().__init__`
calls are rejected per site with `reject *`. Two `exclude` lines record 4
nodes (the value sites above).

## Statistics

| | Count |
|---|---|
| Sites | 1732: 513 explicit calls and 1219 implicit sites (none with a package candidate) |
| Sites with candidates / value sites | 135 / 2 |
| Ledger entries | 513 |
| Callee lines / rejection lines / exclusion lines / notes | 570 / 46 / 2 / 103 |
| Default rejections | 0 |
| Nodes | 102 (3 modules, 99 functions) |
| Edges | 457: 143 in the package, 314 to 104 callees outside |
| Edges that the trace confirms | none: no trace |
| Edges that only Windows makes | 12 (judgement 3) |
| Package functions without a caller | 1 (`enumratorBase.extract_domains`) |


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
