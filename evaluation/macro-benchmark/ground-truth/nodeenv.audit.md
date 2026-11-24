**Status (2026-11-24):** closed. 134 of 134 blind sites agree; the lead
admitted F1 (+2 inside edges) and sent R1 to the README; the writer applied
F1 and W1 in `d549f3d` (439 edges: 120 inside, 319 outside), and the
re-check against it finds nothing open (section "Re-check").

# nodeenv: blind audit of the ground truth (batch 8)

Release 1.12.0, commit `cb7fc97ebff9792d1fa603fe66baa6fcd5912659`, the
module file `nodeenv.py`. Audited files, at the writer's commit `d071a7c`
of `b8-gt-nodeenv`: `nodeenv.ledger` (1522 lines; 598 entries, 660
callee lines, 7 rejection lines, 107 notes, no default, no exclusion),
`nodeenv.json` (67 nodes, 437 edges: 118 inside, 319 outside),
`nodeenv.added.json` (109 added edges), `nodeenv.rejected.json` (29 edges)
and `nodeenv.md` (J1 to J9). `check.py nodeenv` and `check.py --origin
nodeenv` report no errors; the trace confirms 328 of 437 edges, 62 of 66
functions run.

I read `nodeenv.py` whole, `setup.py`, `tox.ini`, `README.rst`, `CHANGES`,
`.github/workflows/tests.yml` and the tests as data; from the dependency
sources (read only) shtab 1.13.0 (`shtab/__init__.py`) and CPython 3.10,
3.11, 3.14 and 3.15 `Lib/` (`urllib/parse.py`, `urllib/response.py`,
`tempfile.py`, `re/__init__.py`, `concurrent/futures/_base.py`). I ran
nothing of the package and no analysis tool. Commands: `check.py
--benchmark-dir <scratch> --skeleton nodeenv` and `--report nodeenv` on a
scratch copy without the ledger (before the blind commit); after it,
`check.py nodeenv`, `--origin`, `--report`, `--report
--without-candidates`; my own scripts on the text: `draw.py`, a comparison
of the ledger entries with the sample, an `ast` binding check, and a
listing of the graph's nodes and outside names.

## Final state

| | Count |
|---|---|
| Blind sites | 134 (70 drawn, 64 value sites added) |
| Agreement | 134 of 134 |
| Edges missing (writer) | 0 under the rules as written; 2 inside if F1 is ruled to admit |
| Edges that cannot happen | 0 |
| Wording | 1 (W1) |
| Change to the graph | none, unless F1 |

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | case for a ruling (medium) | `mkdir -> create_logger.emit` (`704:21`, `706:21`, `708:21`) and `_get_last_node_version -> create_logger.emit` (`1626:17`); `emit` also at the other five debug sites (`728:21`, `732:21`, `738:25`, `785:17`, `1161:25`), whose callers already have the edge | J1 removes `emit` from every `logger.debug(...)` call because the package sets the logger's level to INFO (`nodeenv.py:399`) and no document or test lowers it, by analogy with pymysql's module flags. But the clarification "Versions and configuration" admits "documented interpreter or library configuration [...] when it changes a package-owned default or value", and says the configuration "need not be repeated in each package's documentation". The level of the logger named `nodeenv` is such a value, and the logging library documents configuring a named logger (`logging.config.dictConfig`, `Logger.setLevel` on `logging.getLogger(name)`) without any change of package internals. The pymysql flag ruling covers a client assignment to a module attribute of the package, not a library's configuration of its own registry. My blind answer agreed with J1; on reading the clarification I think it admits the debug records. | +2 inside if admitted | for the lead |
| W1 | wording (low) | `nodeenv.md:13` | "ran 400 tests; 20 failed": the trace's `tests` record has 400 passed, 20 failed, 98 skipped, 12 deselected (so 420 ran; `repeatability/declared.json:23`). | 0 | the writer corrects it |
| R1 | README (low) | "Callees outside the package", B5 | The README has no sentence on a package function that the package installs as a method of a library class (`logging.StreamHandler.emit = emit`, `nodeenv.py:407`). The writer and I applied the call-back rule (B5) to the package's logging calls and judged `emit`'s receivers by B5 (client handlers opaque, the package's `ch` and logging's `lastResort` named). One sentence would fix it for the next writer. | 0 | for the lead |

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/nodeenv` (`cp -R`) to
a scratch directory and ran `check.py --benchmark-dir <scratch> --skeleton
nodeenv`. It has 598 sites, all explicit (595 call, 3 decorator): the two
package classes define no special method but `__call__`, so no implicit
site has a candidate. 120 sites have candidates (one each); 76 are value
sites (`join`, `abspath`, `logger`, `complete` and `debug` are names that
the module or a class binds).

**Draw.** No kind dominates (there is one), so the draw is one stratum: I
numbered the sites in (module order, line, column) and drew
`random.Random(20261124).sample(explicit, 70)`, then added the 64 value
sites not drawn (12 were drawn): 134 sites. `draw.py`, `sample.txt` and
`blind-answers.md` are in
`macro-benchmark/selection/batch-8-proposal/audits/nodeenv/`, committed in
`817a639` before I opened any file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Drawn (explicit) | 70 | 70 | 0 |
| Value sites not drawn | 64 | 64 | 0 |
| **Total** | **134** | **134** | **0** |

The sample holds every kind of decision the ledger makes: the logging
call-back (`1009:23`, `1185:16`, `1227:25`, `1772:28` with `emit`; nine
debug sites without it), the argparse call-back (`675:29`), the
`contextmanager` helper and generator function (`1333:22`), the operator
table (`353:27`, without `operator.eq`), the platform pairs (`988:49`,
`1572:17`), the three rejections by name (`675:29`, `1031:31`,
`1349:24`), Cygwin-only branches (`1116:14`, `1347:20`, `1488:50`) and the
`os.environ` names (`797:23`, `1698:28`).

## Step 2: exhaustive checks

- **Dispatch sets.** No class hierarchy: `Config` has only classmethods
  called on the class, and `PrintCompletionAction.__call__` is reached
  only from argparse. The call-back roles: logging -> `emit` at the 47
  info, warning, error and critical sites (all 47 have it; 20 callers);
  argparse -> `PrintCompletionAction.__call__` at `675:29` only (argparse
  constructs the action at `478:24` with its own `__init__`, no edge);
  `contextlib.contextmanager.helper` -> `tarfile_open` at `977:27` and
  `1333:22`; `map` -> `build_node_from_src.<lambda1>` at `1138:28` (the
  `zip` of `1144` iterates it in the same function); `instfunc` at
  `1572:17`; `members` and `member_name` at `987:34`, `988:49`;
  `_OPERATORS` at `353:27`. Each is complete.
- **Defaults.** None.
- **Functions that no site calls.** None: every one of the 66 functions
  has an in-edge in the graph.
- **Special methods and properties.** Only `__call__`; no property.
- **Rejections and notes.** The 7 rejections (`nodeenv.parse_args`,
  `nodeenv.urlopen` three times, `nodeenv.copytree` three times) are by
  name only and correct. I read all 107 notes; each agrees with the source.
  The `emit` note (`403:26`) names `lastResort` correctly: a
  `_StderrHandler` inherits `format`, `flush` and the patched `emit` from
  `StreamHandler`, so it adds no name.
- **Callees outside the package.** 162 names; I checked each against the
  imports of `nodeenv.py` and the micro-benchmark rules, and the
  non-obvious ones in the sources: `urllib.parse.urlsplit` is plain on
  3.10 and `lru_cache`d from 3.11 (`parse.py:469` of 3.11.18), so J5's two
  names hold; `addinfourl` derives from `tempfile._TemporaryFileWrapper`
  (`response.py:14`), whose `__getattr__` returns the local `func_wrapper`
  (`tempfile.py:564-581`), and the README documents a `file://` mirror
  (`README.rst:224-228`, `430`), so J3 holds; `urllib.parse.SplitResult._replace`
  is the method of the receiver's class (the trace's
  `collections.namedtuple._replace` resolves to it); `os._Environ.copy`,
  `collections.abc.Mapping.get` and `_sitebuiltins.Quitter.__call__` follow
  the asciinema, anytree and pyfiglet precedents; `certifi.where` is a
  missing module (certifi is an extra, absent from the trace environment,
  `requirements/nodeenv.installed.txt`); `shtab.complete` calls nothing of
  the package (it reads the actions' attributes only). On 3.15, `re.match`
  is an alias of `re.prefixmatch` (`re/__init__.py:169`): the access path
  `re.match` stays.
- **Rejected trace edges.** 29: 25 mocks of `unittest.mock`, each with the
  patch and its test lines (I checked `nodeenv_test.py:370-375`,
  `396-397`, `1888-1898` and `3260-3290`); `_get_versions_json ->
  _io.BufferedReader.read` and `-> _io.BytesIO.read`, `install_npm_win ->
  _io.BytesIO.read` (the tests' own file and BytesIO stand in for the
  response: client objects); `emit -> _io.StringIO.write` (pytest's
  capture handler: a client handler, B5). All correct.
- **Trace edges the graph lacks.** None (`--report`: 0).
- **Implicit sites without candidates.** 1009, mostly attribute loads and
  truth tests. No lazy `map` or `filter` is iterated outside the function
  that builds it, and no library call-back hides at an implicit site: the
  `with` sites over `ctx` and `tarfile_open(...)` (`981:10`, `1333:10`)
  resume the generator that the call site already reached.

## Step 3: binding check

An `ast` script built the signature of every function of `nodeenv.py`
(methods without `self` or `cls`) and bound each call whose callee name is
a package function's name: 115 bind; the 3 that do not are
`urllib2.urlopen(...)` against `nodeenv.urlopen` (`1031`, `1036`, `1039`),
which the ledger rejects by name. By hand: `instfunc(env_dir, src_dir,
args)` binds both `install_npm` and `install_npm_win`; `member_name(member)`
binds the one-parameter lambda; `map` calls `<lambda1>` with one
argument; logging calls `emit(self, record)` as a bound method; argparse
calls `PrintCompletionAction.__call__` with four arguments. No call fails
to bind.

## The writer's judgement calls

| J | Edges | Opinion | Nearest rule |
|---|---|---|---|
| J1 | 20 inside (`emit`) | The 20 edges are right (call-back rule). Leaving out `emit` at debug sites is the open point of F1. | B5 call-back (structlog, pyrate-limiter); configuration: the clarification "Versions and configuration" against the pymysql flag ruling |
| J2 | 4 outside, 1 rejected | Agree. | B5 (client handlers and streams opaque); naming through the public class (`logging.StreamHandler.format`) |
| J3 | 4 outside | Agree: a documented `file://` mirror and an http-to-ftp redirect both give `addinfourl`. | asciinema (redirect), segno and bottle (`func_wrapper`) |
| J4 | inside and outside | Agree: Windows by CI, Cygwin and MSYS2 by `CHANGES:332` and `CHANGES:255`; Solaris and FreeBSD add no name. | "What makes a platform supported" (pyfiglet) |
| J5 | 2 outside | Agree. | fastjsonschema (`urlsplit`) |
| J6 | 4 (2 sites) | Agree. | micro-benchmark generators and call-backs (`main -> main.managed`) |
| J7 | 4 outside | Agree; `operator.eq` cannot be reached by a range the package parses. | B3 (a value the package never produces for that role) |
| J8 | outside | Agree: argparse documents `parser` as the `ArgumentParser`. | B4/B5 (a framework's documented API fixes the type) |
| J9 | 1 outside | Agree. | missing modules |

## For the lead

F1, a small case (2 inside edges): does a library's documented
configuration of a package's named logger (`logging.config.dictConfig`,
`logging.getLogger("nodeenv").setLevel(logging.DEBUG)`) count as
configuration that changes a package-owned value? If yes, `emit` is a
callee of the nine `logger.debug(...)` sites (`704:21`, `706:21`,
`708:21`, `728:21`, `732:21`, `738:25`, `785:17`, `1161:25`, `1626:17`),
which adds `mkdir -> create_logger.emit` and `_get_last_node_version ->
create_logger.emit`. If no, the ledger stays. My opinion: yes, by the
clarification's wording; the writer's reading follows the pymysql ruling,
which is about a module flag of the package.

R1, a sentence for the README on package functions installed into library
classes (no edge changes).

## Re-check (2026-11-24, against `d549f3d`)

The lead's rulings of 2026-11-24: F1 admitted (lowering the level of the
"nodeenv" logger through logging's public interface is documented library
configuration of a package-owned value; the pymysql flag case is a change
of package internals); W1 to fix; R1 to the README's "Rulings for batch 8".
I read the diff `ee89a0d..d549f3d` of the writer's files and ran
`check.py nodeenv` and `check.py --origin nodeenv` (no errors; 439 edges,
120 inside, 319 outside; 111 added, 41 inside; the trace confirms 328).

| Finding | Re-check |
|---|---|
| F1 | Applied. Each of the nine `logger.debug(...)` sites (`704:21`, `706:21`, `708:21`, `728:21`, `732:21`, `738:25`, `785:17`, `1161:25`, `1626:17`) has `nodeenv.create_logger.emit` beside `logging.Logger.debug`, with a note that cites the ruling; the graph gains exactly `mkdir -> create_logger.emit` and `_get_last_node_version -> create_logger.emit` (22 callers of `emit` now). The ledger header and J1 state the ruling and withdraw the first reading. Closed. |
| W1 | Applied: `nodeenv.md` gives 400 passed, 20 failed (declared), 98 skipped, 12 deselected. Closed. |
| R1 | For the README (the lead's "Rulings for batch 8"); no edge of this ledger depends on it. Closed for this audit. |

**The writer's new note on `464:29`** (`shtab.complete`, no `emit`):
correct. shtab 1.13.0 logs only debug records, on its own logger
`logging.getLogger("shtab")` (`shtab/__init__.py:25`; every call is
`log.debug`). That logger is no descendant of "nodeenv", so its records
never reach the package's handler `ch`. Without a handler on the way they
fall to logging's `lastResort`, a library `StreamHandler` whose `emit` is
the patched one, but `lastResort` has the level WARNING
(`logging/__init__.py:1294`, checked at `:1753`), so a debug record never
reaches it, whatever level a client gives shtab's logger. Any other
handler on the way is one that the client configures: client code (B5).
The F1 ruling admits a change of the package logger's level, not a
client's handlers. No edge.

Nothing is open: the audit is closed.
