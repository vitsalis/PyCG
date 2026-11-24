# argcomplete: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [argcomplete.md](argcomplete.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release v3.7.2, commit `0571dc489d9543b40f1bcbc6cbac4377906b76fd`.
Audited files, as they were in the worktree (not committed): `argcomplete.ledger`
(1359 lines), `argcomplete.json` (340 edges: 91 in the package, 249
outside), `argcomplete.rejected.json` (5 edges), `argcomplete.md`
(judgements 1 to 11). `check.py --benchmark-dir macro-benchmark-heldout-2
argcomplete`: no errors. The trace confirms 206 edges; 134 come from reading
only. `--report`: 0 trace edges unaccounted for.

I read the source, `README.rst` and `test/test.py` as data. I did not run
the package, PyCG or any analysis tool, and did not open `pycg/`,
`evaluation/` or `docs/`.

**Result.** 1 finding that changes the graph (A1, 8 edges out), 1 naming
question (N1), and rulings on the writer's judgement calls 1 to 5. Every
other edge, rejection, note, exclusion and default rejection holds. If the
lead accepts A1, the graph has 332 edges (91 in the package, 241 outside);
the trace still confirms 206.

## Findings

| Id | Kind | Edges | Evidence | Confidence |
|---|---|---|---|---|
| A1 | edges that cannot happen (judgement 2) | -8 | See below. | likely; needs the lead's ruling on judgement 2 |
| N1 | naming (judgement 4) | +2 or 0 | `finders.py:290:48`. See "Rulings", judgement 4. | lead's choice |

**A1. The receiver of the uncalled `shlex` methods.** Judgement 2 judges the
receiver of `push_token`, `push_source`, `pop_source` and `sourcehook` "as
for a public method": a `shlex` in any state. B1 decides receivers: "a
private class is instantiated only where the package does it". `shlex` is
private (path `argcomplete.packages._shlex`, rule C). The only instance is
the lexer of `split_line` (`lexers.py:12-14`), and it never leaves
`split_line`. On that lexer, `debug` is 0 (`_shlex.py:52`; no code sets it,
and no parameter feeds it), `infile` is None (`:29`, from `lexers.py:12`),
and `instream` is an `io.StringIO` (`:26-28`). B's sentence on uncalled
private functions speaks of their parameters, so `tok`, `newstream`,
`newfile` stay open; their bodies keep edges (rule A). The writer already
applies this reading to the same object in judgement 1: the note at
`get_token` 106:40 says `pushback` is always empty because "only push_token
(never called) ... fill[s] it". A hypothetical call of an uncalled method
does not change the lexer's state for another method. So these 8 edges need
a receiver that no program can make:

- `push_token -> <builtin>.print`, `<builtin>.repr` (`_shlex.py:76-77`, `debug` is 0);
- `push_source -> <builtin>.print` (`:89-93`, `debug` is 0);
- `pop_source -> <builtin>.print` (`:99-100`, `debug` is 0);
- `pop_source -> io.TextIOWrapper.close` (`:97`): `instream` is a TextIOWrapper only
  as `sys.stdin` (`:31`, needs `instream=None`, which the package never passes)
  or as the file that `get_token` pushes at `:118` (dead by judgement 1);
- `sourcehook -> os.path.isabs`, `os.path.join`, `os.path.dirname` (`:291-292`):
  `self.infile` is None, so `isinstance(self.infile, str)` is False and the
  `and` stops. Only `push_source` and `pop_source` (never called) set `infile`.

The methods keep: `push_token -> deque.appendleft`; `push_source -> isinstance,
io.StringIO, deque.appendleft`; `pop_source -> io.StringIO.close,
deque.popleft`; `sourcehook -> isinstance, open`; `__next__ -> get_token`.
The ledger lines to change: 77:18, 77:49, 91:22, 93:22, 100:18 (note "never
runs"), 97:28 (drop `io.TextIOWrapper.close`), 291:62, 292:35, 292:51 (note
"never runs"), and the notes at 77:18, 91:22, 97:28 and 291:22. All 8 are
outside edges; `<builtin>.repr` and `os.path.isabs` then leave the graph.
If the lead rules instead that a stored value fed from a parameter of an
uncalled method counts (B2, "what is fed from it", through `push_source`'s
`newfile`), the 3 `sourcehook` edges stay and A1 removes 5.

## Rulings on the writer's judgement calls

| Judgement | Nearest rule | Ruling | Edges |
|---|---|---|---|
| 1. Branches of the private `shlex` that the package's values never take | B (values that reach a site), B1, B2 stored values; precedent: cachetools `self.getsizeof(value)` at `__init__.py:75`, "client only: the branch needs `self.getsizeof is not Cache.getsizeof`" (cachetools.audit.md, step 2) | Keep the writer's decision. I checked each listed site: `debug` 0, `source` None, `filestack` and `pushback` empty, `punctuation_chars` '', and `whitespace_split` True makes line 254 always hold (`lexers.py:13`). The count of 15 is right. | 0 (+15 if ruled otherwise) |
| 2. Receiver of the uncalled `shlex` methods | B1 (receivers of a private class), B2 | The receiver is the lexer of `split_line` (A1). | -8 (A1) |
| 3. The original `__call__` of an action (`finders.py:281`, `:285`, `:290`, `_argparse.py:154`) | B5 (an attribute of a client object is opaque); B4 (a class check fixes the class, as `isinstance` does) | Keep the writer's decision. `:281` and an action added after the patch have no outside callee; `issubclass` (`:282`) and `in safe_actions` (`:286`) fix the classes at `:285` and `:290`. | 0 (other reading: +3 at `:281`, `_ExtendAction`, `_HelpAction`, `_VersionAction`; about +10 at `:154`) |
| 4. Names of the inherited `__call__` of `_StoreTrueAction`, `_StoreFalseAction` | README "Callees outside the package": "named by the class of the receiver, also when that class inherits it" | The README rule gives `argparse._StoreTrueAction.__call__` and `argparse._StoreFalseAction.__call__` beside `_StoreConstAction.__call__` (7 names). The anytree J8 precedent moves a private receiver to a public class that defines the method; here no public class defines it, so J8 does not apply. The README does not decide private-to-private; see R2. | +2 by the README rule; 0 if the lead extends J8 |
| 5. The formatter (`finders.py:311-312`) | B4 (`self._formatter` annotated `argparse.HelpFormatter`), B2 | Keep. The scripts' help strings and argparse's `-h` help have no `%`, so `_get_action_help` returns at `:306-307` before `:311`. | 0 |

Judgements 6 to 11 hold (`BaseCompleter` by B1; `os.environ.get` as
`collections.abc.Mapping.get` by anytree J8; `mute_stderr()` gives
`contextlib.contextmanager.helper` and the generator function; the scripts'
`parse_args` sees an unpatched parser, because every path after the patch
ends in `exit_method` or raises out of `autocomplete`; the version branches;
the package exceptions). 0 edges.

## Step 1: blind re-derivation

I made the skeleton without the ledger in `$TMPDIR/heldout2-audit-argcomplete/bench`
(a copy of `projects.toml` and a `projects` symlink): 647 sites (512 call, 4
decorator, 70 iter, 61 op), 18 value sites. I numbered the site lines from 0
in file order and drew `random.Random(20261111).sample(range(647), 70)`:
54 call, 10 iter, 5 op, 1 decorator. Explicit calls already dominate, so a
plain draw. I added the 18 value sites (none was in the draw): 88 sites. I
wrote my callees to `blind-answers.md` there before I opened any writer
file. Where the README did not decide, I wrote the alternatives ("cond").

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Drawn | 70 | 67 | 3 |
| Value sites | 18 | 15 | 3 |
| **Total** | **88** | **82** | **6** |

- **Writer has an edge that cannot happen (1):** `_shlex.py` 93:22 `print(...)`
  in `push_source` (A1).
- **Naming only (2):** `finders.py` 157:29 (I wrote `os._Environ.get`; the
  writer's `collections.abc.Mapping.get` follows anytree J8); `finders.py`
  290:48 (I named 7 receiver classes, the writer 5 defining classes; N1).
- **Auditor wrong (3):** `finders.py` 311:72 (I added
  `argparse.RawDescriptionHelpFormatter` for the scripts' parsers; they
  never reach the line, judgement 5); `finders.py` 281:48 and `_argparse.py`
  154:27 (my conditional argparse action classes; B5 rules them out,
  judgement 3).
- **Writer missed an edge (0).**

My strict reading of the `shlex` stored values gave the same "never runs"
entries as the writer at 115:39, 130:22, 140:52 and 156:30.

## Step 2: exhaustive checks

1. **Dispatch.** `self._action_allowed` (`finders.py:354`): both methods.
   Every other `self.m()` in `CompletionFinder`: the base method
   (`ExclusiveCompletionFinder` overrides only `_action_allowed`).
   `completer(...)` (`:423`): the four `__call__` of judgement 6
   (`SuppressCompleter` stops at `:419-420`). `self.validator`:
   `default_validator`. `exit_method`: `os._exit`. `self.predicate`:
   `os.path.isdir`. `action(...)` (`_argparse.py:154`):
   `IntrospectAction.__call__`. The callbacks `_parse_known_args` at
   `finders.py:230` and `:285`. All match.
2. **Default rejection** of `shlex.__iter__`/`__next__`: all 131 implicit
   sites listed by `--report --default`. No site iterates or searches a
   `shlex`; the `in` sites inside `shlex` search strs. The 16 explicit
   sites reject them with the argument's type. Correct.
3. **Functions that no site calls** (13 functions): `DirectoriesCompleter.__init__`,
   `SuppressCompleter.__init__`, `rl_complete`, `get_display_completions`,
   `mute_stdout`, `warn` (public, client only) and the 6 uncalled `shlex`
   methods plus `__iter__`. Each keeps its body edges (rule A).
4. **Outside callees**: 110 names. Each is named by the rules or a
   precedent (`contextlib.contextmanager.helper`, `collections.abc.Mapping.get`,
   `<builtin>.RuntimeError.__init__`, `io.TextIOWrapper.*` for `open()`,
   `os.fdopen`, `tokenize.open`, `sys.stdout`). B4/B5: every outside method
   edge has a receiver that the package makes or that an annotation or a
   class check fixes; `completer_output.items()` (`:427`) and
   `completer.complete` (`:442`) correctly have none.
5. **Rejections, notes, exclusions**: all read. Wrong only where A1 applies
   (the notes at 77:18, 91:22, 97:28, 291:22). The 3 exclusions of
   `IntrospectAction.__call__` hold (`:269`).
6. **Rejected trace edges**: all 5 hold (`sys.exit` passed by the tests;
   `dict.get` from the tests' dict `os.environ`; `dict.items` of the test
   completer `c_url`).
7. **Untraced edges** (134): 92 in the scripts and `_check_*` modules, 25
   elsewhere, 17 in the uncalled `shlex` methods. All are possible except
   the 8 of A1. Example: `io.debug -> <builtin>.print` is possible but
   untraced, because `_DEBUG` is read at import (`io.py:6`) and the tests set
   `_ARC_DEBUG` only later (`test/test.py:123`).

## README remarks

- **R1.** Rule B says the parameters of an uncalled private function are
  judged as for a public one. It does not say whether the receiver is one of
  them. Proposal: B1 decides the receiver; its stored values come from the
  package's calls only (A1).
- **R2.** The naming rule for an inherited method of an outside object
  assumes a public receiver class. Say what to do when the receiver class
  and the defining class are both private (N1).
- **R3.** Judgement 1 rests on B2 for stored values that the package sets to
  one constant. A sentence in B2 would settle it ("a branch that no value of
  the package or a client takes adds no edge"), with the cachetools
  `getsizeof` case.


## Fourth complete audit (2026-11-16)

Read all runtime source and role/support evidence before opening the baseline.
The frozen model covers 15 modules, 74 functions, 1,899 AST sites and all 516
explicit sites. Compared every one of the 340 baseline pairs and checked all
1,383 implicit sites, including 131 default-decided sites and 1,252 sites with
no package candidates. Checked 18 value sites, three exclusions, five rejected
trace pairs and 14 zero-edge bodies.

Result: no added or removed pair, no node change. One metadata group clarifies
CPython/PyPy >=3.10 and the working normal/-O/-OO union. The action_tuples
assertion follows an append on every reaching branch; optimized execution adds
no target at that site or at the greedy-actions assertion. Two corrections to
the auditor's frozen prose concern public parser re-exports and opaque client
actions; the baseline already handles them correctly. Historical audit text
above is preserved. Root runs the final structural/origin gates separately.
