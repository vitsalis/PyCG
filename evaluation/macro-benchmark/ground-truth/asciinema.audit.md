# asciinema: independent audit of the ground truth

Commit `350d5e9d8b7cee1be5db4091815942c9d035e7dc` (develop, after v2.0.0).
Audited files: `asciinema.ledger` (518 entries: 475 call, 14 decorator,
12 with, 15 getattr, 2 iter), `asciinema.json` (161 nodes, 425 edges: 174
in the package, 251 to 140 callees outside), `asciinema.rejected.json` (3
edges) and `asciinema.md` (16 judgements). The trace has 84 edges: 81 are
in the graph, 3 are rejected. 37 of 137 functions run. `check.py
--benchmark-dir macro-benchmark-2021 asciinema` reports no errors, and
`--report` shows 0 trace edges that no site accounts for.

I read the 24 modules of `asciinema/` in full, and `tests/pty_test.py`,
`tests/config_test.py` and `tests/asciicast/v2_test.py` as data for rule
B2. I did not run the package and did not use any analysis tool. I read
the standard library of the local Python 3.15 for two facts (urllib's
redirect check, `codecs.StreamReader` without `close`). The 3.3 to 3.7
facts below are from memory where I say so.

**Result.** The blind sample of 120 sites agrees with the ledger on every
edge. The two differences are names, and in both the writer is right. I
found no missing edge and no edge that cannot happen under the current
rules. One judgement of the writer (A1, an http redirect to ftp) needs a
ruling; it would add 3 edges. The three judgement calls that the lead
named change 0 edges under the README's nearest rules (section "Rulings").
One README gap on names (N1) changes no edge.

## Findings

| Id | Severity | Site or edge | Evidence | Edges |
|---|---|---|---|---|
| A1 | low; needs a ruling | `open_url` (`asciicast/__init__.py:48-53`), `v1.open_from_file.__exit__` (`v1.py:60`), `v2.open_from_file.__exit__` (`v2.py:56`) | Judgement 11 leaves out a redirect from an http(s) URL to an ftp URL. urllib follows it: `HTTPRedirectHandler` allows the schemes http, https and ftp (`urllib/request.py:678` of 3.15; the same check since 3.2, from memory), and `FTPHandler.ftp_open` returns a `urllib.response.addinfourl` (`:1569`). Then `response.geturl()` at 50:30 calls `urllib.response.addinfourl.geturl`, and the `close()` of the StreamReader over it (judgement 8) calls `urllib.response.addinfourl.close` in both `__exit__`. The URL is a value of the client (B2), and the ground truth already counts other answers of the server: the gzip branch (`gzip.GzipFile.close`) and the HTML page with a `<link>` (recursion at 76:28). The README has no rule on what a server can return. I propose to add the edges, by rule B and the precedent of the gzip branch. In `post` (`urllib_http_adapter.py:76-77`) the same redirect gives no edge: `addinfourl` has no `status` on 3.3 to 3.7, so line 77 raises `AttributeError` first. | +3 if accepted |
| N1 | README gap (names; no edge) | `term.py:14:38, 22:26`; `os.environ.get` (10 sites) | The micro-benchmark rule names a module function by "the path that the snippet imports": `tty.tcgetattr`. The tracer accepts only names in `__all__`, and `tty.__all__` does not have `tcgetattr` (the trace names `termios.tcgetattr`). The writer uses `termios.*` (judgement 13). In the same way, `os.environ.get` is `collections.abc.Mapping.get` by anytree J8 (`macro-benchmark-heldout/ground-truth/anytree.md`, item 8), but the README says only "also when both classes are private" (`argparse._StoreTrueAction.__call__`). I wrote `tty.tcsetattr` and `os._Environ.get` blind, and both are wrong by these precedents. Proposal: write both rules in the README, "Callees outside the package": a function that a module re-exports without `__all__` is named where it is defined; a method that a private class inherits from a public class is named through the public class. | 0 |

## Step 1: blind re-derivation

**Sample.** I made the skeleton without the ledger: a scratch benchmark
directory under `$TMPDIR/macro2021-audit-asciinema/bench/` with a copy of
`projects.toml` and a symbolic link to `macro-benchmark-2021/projects`,
then `check.py --benchmark-dir <scratch> --skeleton asciinema`. It has 516
sites, 20 of them value sites. I drew
`random.Random(20261111).sample(non_value_sites, 100)` over the other 496
sites in skeleton order, and added the 20 value sites: 120 sites (the
plain draw: 95 calls, 1 decorator, 3 with, 1 getattr). I wrote the callees
of each site to `blind-answers.md` in that directory before I opened the
writer's files. Script: `draw.py`; sample: `sample.txt`; comparison:
`compare.txt`.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random (not value sites) | 100 | 98 | 2 (naming) |
| Value sites | 20 | 20 | 0 |
| **Total** | **120** | **118** | **2** |

The 2 disagreements, classified:

- **Naming only; the auditor was wrong (2):** `config.py` 133:23
  `env.get("HOME")` (I wrote `os._Environ.get`; the ledger has
  `collections.abc.Mapping.get`, anytree J8) and `term.py` 22:26 (I wrote
  `tty.tcsetattr`; the ledger has `termios.tcsetattr`, the name that the
  tracer accepts). See N1.
- **The writer missed an edge (0). The writer has an edge that cannot
  happen (0).**

The value sites agree in full: `args.cmd(...)` gives the five command
`__init__`; `utf8_reader(...)` the class `encodings.utf_8.StreamReader`;
`getincrementaldecoder(...)(...)` the class
`encodings.utf_8.IncrementalDecoder`; `c()` no edge (`object.__init__`);
`old_handlers.append` `<builtin>.list.append` (a value site only by the
attribute name `append`, which `recorder.py:65` and
`commands/record.py:25` assign); `record(...)` `pty.record` (the
default); `self.writer(...)` the `__init__` of `raw.writer` and
`v2.writer`; the 11 `encoder(...)` `encodings.utf_8.encode`.

## Step 2: exhaustive checks

**Dispatch sets (B1, B2).** Each row equals the ledger.

| Site | Receivers or values | Callees |
|---|---|---|
| `args.cmd(...)` `__main__.py:106` / `command.execute()` `:107` | the five classes of `set_defaults` (`:79-100`) | five `__init__` / five `execute` |
| `self.print*` in the commands | `Command` and its five subclasses; none overrides | `Command.print`, `print_info`, `print_warning`, `print_error` |
| `a.stdout_events()` `cat.py:16`, `asciicast.stdout_events()` `player.py:22` | what `open_from_url.__enter__` returns | `v1.Asciicast.stdout_events`, `v2.Asciicast.stdout_events` |
| `self.context.__enter__()` `asciicast/__init__.py:96, 100` / `__exit__` `:108` | the `open_from_file` of line 95 or 99 | v2 / v1 `__enter__`; both `__exit__` |
| `self.file.readline/read/close` | `sys.stdin`, `open()` text file, `StreamReader` over `HTTPResponse` or `GzipFile`; `get_duration`'s file | `io.TextIOWrapper.*`, `encodings.utf_8.StreamReader.read/readline`; `close` of `TextIOWrapper`, `HTTPResponse`, `GzipFile` (`codecs.StreamReader` has no `close`; its `__getattr__` gives the stream's) |
| `self.process.start()` `async_worker.py:19` | `async_worker` (public), `async_writer`, `async_notifier` | `multiprocessing.Process.start`, `threading.Thread.start`, callbacks `async_worker.run`, `async_writer.run` |
| `self.perform(...)` `async_worker.py:31` | `async_notifier`, a plain `async_worker` (raises) | `async_notifier.perform` |
| `self.notifier.notify` `recorder.py:95` | what `get_notifier` returns, or `None` | `Notifier.notify`, `CustomCommandNotifier.notify`, `NoopNotifier.notify` |
| `self.args(text)` `notifier.py:11` | Terminal, AppleScript, LibNotify notifiers | their three `args` |
| `notifier.notify`, `writer.write_stdout/stdin` in `pty.record` (`pty.py:25, 51, 80`) | the `async_notifier` and `async_writer` of `recorder.py:47-55`; the test passes a client `FakeStdout` (`tests/pty_test.py:36-39`) | `async_notifier.notify`; `async_writer.write_stdout/stdin` |
| `self.writer(...)`, `with`, `w.write_stdout/stdin` `recorder.py:74-81` | `v2.writer` (default, `:12`), `raw.writer` (`commands/record.py:28`) | `__init__`, `__enter__`, `__exit__`, `write_stdout`, `write_stdin` of both |
| `self.http_adapter.post` `api.py:35`, `self.player.play` `play.py:18` | the package defaults | `URLLibHttpAdapter.post`, `Player.play` |

**Callbacks of library code.** All present: `parse_args()` ->
`positive_float` (`__main__.py:103:29`; `add_argument` only stores the
type, and the three `add_argument` sites reject it); `parser.feed(html)`
-> `Parser.handle_starttag` (`asciicast/__init__.py:61:24`);
`self.process.start()` -> both `run` (`async_worker.py:19:27`; `Process(...)`
rejects them). `iter(self.queue.get, None)` (`async_worker.py:30`,
`recorder.py:75`) calls a library method back: no edge. These are the 6
sites of `--report` with callees that are not candidates; all 6 are right.

**Lazy `map` and `filter` of a package lambda.** I scanned the source for
`map(` and `filter(`: two lambdas, both consumed lazily. `pty.py:144`
`map(<lambda1>, ...)` is iterated at `pty.py:84:29` in `_signals`; the
ledger has `84:29 iter signal_list -> pty.record.<lambda1>` (the trace has
it). `commands/record.py:68` `filter(None, map(<lambda1>, ...))` is passed
as `capture_env` and iterated at `recorder.py:37:70`; the ledger has
`37:70 iter capture_env -> RecordCommand.execute.<lambda1>`. The `map`
sites reject the lambdas. `if capture_env:` at `recorder.py:36` does not
iterate. Both entries are correct.

**Code in a forked child.** `os.execvpe` (`pty.py:135`) runs in the child
of `pty.fork()`: in the ledger. With `multiprocessing` (fork on every
supported Unix version, 3.3 to 3.7), `start()` runs `run` in the forked
child: in the ledger at 19:27. If `execvpe` fails, the exception unwinds
the child through `async_notifier.__exit__` and `async_writer.__exit__`,
whose edges are already in the graph.

**Functions without a package caller.** `record_asciicast`,
`v1.Asciicast.events` and `v1.Asciicast.v2_header` (plus the 24 modules).
Each is public and keeps the edges of its body (rule A).
`self.v2_header = header` (`v2.py:21`) stores on a `v2.Asciicast` and does
not touch the property of `v1`.

**Special methods and properties.** The package defines no special method
other than `__init__`, `__enter__`, `__exit__`, and no `__str__`,
`__bool__`, `__len__`, `__iter__` or `__call__`; so no implicit site has a
package callee except `with` and the 15 property loads. The 12 properties
of `Config` are reached at the 13 getattr sites that name them; the two
other getattr sites, the loads of `self.install_id` in `Api`, reject
`Config.install_id` (an instance attribute). The 14 decorator sites give `<builtin>.property` and
`<builtin>.classmethod`. No class site exists (no package metaclass,
`__init_subclass__` or `__set_name__`).

**Rejections and notes.** I read all 72 rejection lines, the 2
exclusions and the 95 notes. Every reason holds. No default rejection
exists.

**Callees outside the package.** All 140 names, grouped by callee. Each
call exists on a supported version and has the name of the micro-benchmark
rules, of the README precedents, or of a trace alias. Points checked:
`io.FileIO` and `io.BufferedWriter` for `raw.writer` (buffering 0, or a
client's other buffering; judgement 10, right by B2: the client gives an
int, and the file is the package's own object); `os._Environ.copy`
(defined by `_Environ`); `encodings.utf_8.encode` (the public name of
`_codecs.utf_8_encode` that the tracer accepts); `<builtin>.object.__init__`
for the explicit `Notifier.__init__(self)` (`notifier.py:56`);
`argparse.ArgumentTypeError`; the names of judgement 9 (below).

**Rejected trace edges.** The 3 `<builtin>.dict.get` edges come from the
dicts that `tests/config_test.py:11-19` passes as `env`. B5: client
objects. They stay rejected.

## Rulings on the writer's judgement calls

| Judgement | Ruling that the nearest rule supports | Rule | Edges |
|---|---|---|---|
| 4: the signal handler `pty.record.<lambda1>.<lambda1>` at `select.select` (`pty.py:99:49`) | Keep the edge at `select.select` only. The trace has `_copy -> <lambda1>.<lambda1>`, and rule A rejects a trace edge only for a client value, an implicit call of outside code or a naming artefact; none applies. `select` runs the handler inside the package's call (PEP 475 retry on 3.5+, `EINTR` on 3.3 and 3.4, caught at `pty.py:100-105`), as library code that calls a callback back. A handler that runs between two bytecodes runs at a point that the code does not choose, as the `__del__` of the README. A strict reading of "Callbacks" would also add the other blocking calls while the handlers are installed: `os.write` in `_write_stdout` and `_write_master` (`pty.py:45, 59`, blocking writes to the terminal and the pty master), and the `TCSAFLUSH` `tcsetattr` of `term.raw.__enter__` and `__exit__` (the `with` at `pty.py:155` runs before `_signals(old_handlers)` at `:161`): +4. I do not propose them: only `select` is the call where the package waits for signals (the wakeup fd of `:142` is in its fd set). Proposal for the README: "A signal handler that the package installs is a callee of the call where the package waits for the signal, and of no other site." | micro-benchmark "Callbacks"; README "Implicit calls" (`__del__`) | 0 (+4 by the strict reading) |
| 9, 12, 13: names that differ between the supported versions | Every version's callee is an edge. `e.read()` (`urllib_http_adapter.py:83:26`) keeps both names: `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` on 3.5 to 3.7 and `http.client.HTTPResponse.read` on 3.3 and 3.4 (my memory agrees: `addbase` became a `_TemporaryFileWrapper` in 3.5). `subprocess.run` stays: 3.7 has it with `capture_output`. `multiprocessing.Process`, `multiprocessing.Queue` and `termios.*` are one name on every version. | README "Edges" ("on any Python version that the release supports"); micro-benchmark "Names" (closures of library code) | 0 |
| 1: the Python-2-only branch `__init__.py:6-7` | No edge: only Python 2 takes it, and the package supports 3.3 to 3.7. The ledger has no callee at 7:22 and a note. `pty.py:103` (`except select.error`, "Python < 3.3") is also unreachable, as `select.error` is `OSError` from 3.3 and line 100 catches it first; it has no call. | README "Judgements" ("a branch that only an unsupported version takes does not run") | 0 (+1 if the branch ran) |

The other judgements (2, 3, 5 to 8, 10, 14 to 16) agree with my blind
answers and with the README.

## README and tools

The tools worked as documented. The skeleton has no site for the two
lazy-`map` iterations (no candidate), as the lead warned; the checker
accepts the writer's entries for them. The README is unclear on two
points: names (N1), and the place of a signal handler (judgement 4).

## Third full source audit (2026-11-16)

A fresh independent source-first review retained all 428 edges: 174 inside
the package and 254 outside. It found no confirmed false positive, missed
edge or site metadata correction. It reviewed all 24 runtime modules,
137 functions and lambdas, 1,500 scanner sites, 518 ledger entries,
72 rejection lines and two exclusions. There are no default rejections.
The 982 sites without entries have no additional package callees. The
review checked all 34 zero-edge nodes, including 14 function/lambda bodies.

The pre-comparison model was prose, not an independently enumerated exact
graph. Its timestamped freeze preceded access to the graph and ledger.
The review read the runtime source, tests, README, manual and format docs
as data; it ran no package, dependency, example or test code. Later static
reading of CHANGELOG corrected the model's provisional lower bound to
Python 3.4, consistent with the existing ledger. The original freeze was
retained. Client environment dicts stay opaque under B5; the tests do not
add their outside methods without a concrete parameter contract.

Fresh official CPython source confirmed argparse conversion and HTML
parser callbacks, worker target dispatch, codec lookup and delegation,
HTTP/FTP response paths and supported-version HTTPError read naming.
The graph, ledger and added-edge bytes are unchanged. The three stored
trace rejections remain valid; trace data was used only for origin
accounting after semantic review.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Fourth full source audit (2026-11-16)

A fresh source-first audit retains all 428 edges (174 in the package and
254 outside), with no confirmed false positive, missing edge or independent
metadata correction. It reviewed all 24 runtime modules, 137 functions/lambdas,
161 bodies, 1,500 source sites, 518 ledger entries and 559 site-target relations.
It also reviewed the 982 omitted sites, 72 rejection lines, two exclusions and
34 zero-edge nodes. There are no default rejections.

The source model and inventories were frozen before reading the baseline.
The required global rules had already exposed their asciinema examples; this
prior exposure is disclosed. One model error was corrected after comparison:
tests that pass client environment dicts do not establish named outside methods
without a concrete B4 contract. The three existing trace rejections remain valid.
The graph, ledger, added edges and rejected-edge bytes remain unchanged.

The release supports CPython 3.4 and later, with no declared upper bound and
no explicit alternative-interpreter support. The changelog's explicit 3.3 drop
overrides the old classifier. Under the round's working normal/-O/-OO union,
removing the five header assertions adds no named target; the source has no
__debug__ or __doc__ reads. Targeted raw standard-library reading confirmed
callback placement, codec delegation, HTTP/FTP cutoffs and HTTPError naming.
No target, dependency, test, example, generated code or PyCG was executed.
Coverage records document the review and do not prove completeness.
