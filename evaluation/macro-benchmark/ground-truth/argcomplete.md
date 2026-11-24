# argcomplete: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 0 edges and adds 6. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 2 corrections to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/argcomplete-review.json`).
The current ledger and statistics below include the earlier corrections.
The fourth complete source audit retains all 340 edges; its execution-scope
clarification is recorded in judgement 12 and the appended audit record.

Release v3.7.2 (commit `0571dc4`). Analysed source: `argcomplete/`: 15
modules, 74 functions (no lambdas), 13 classes. `pyproject.toml:5` sets
`requires-python = ">=3.10"`, so the supported versions are 3.10 and later,
without an upper bound. Its implementation classifiers explicitly name CPython
and PyPy. Normal, `-O` and `-OO` execution are included under the round-4
working configuration assumption; this is not a recorded user approval.

The ledger is `argcomplete.ledger`; the graph `argcomplete.json` is
generated from it. `argcomplete.rejected.json` rejects 5 trace edges. The
independent audit is in `argcomplete.audit.md`. The ledger applies the
lead's rulings on it (see "Rulings after the audit").

## Architecture, as the ledger uses it

- `CompletionFinder` (`finders.py:33`) is the engine. `argcomplete.autocomplete`
  is an instance of it (`__init__.py:12`). `ExclusiveCompletionFinder`
  (`finders.py:626`) overrides only `_action_allowed`.
- `_patch_argument_parser` (`finders.py:245`) changes the class of the
  client's parser to `type(classname, (IntrospectiveArgumentParser,
  parser.__class__), {})` (`:266`). It changes the class of each action of
  that parser to `IntrospectAction`, a class that `patch` defines with the
  old class of the action as its base (`:273-294`). It keeps the old class
  in `_orig_class` and the old bound `__call__` in `_orig_callable`.
- `IntrospectiveArgumentParser` (`packages/_argparse.py:79`) overrides
  only `_parse_known_args`. argparse's `parse_known_args` calls it back. Its
  `take_action` calls each action, so `IntrospectAction.__call__` runs.
  For a subparsers action, `IntrospectAction.__call__` patches the chosen
  subparser (`finders.py:284`) and calls the original
  `_SubParsersAction.__call__`, which calls `parse_known_args` on that
  subparser; argparse then calls back `_parse_known_args` again.
- Completers (`completers.py`): `BaseCompleter`, `ChoicesCompleter` (also
  the instance `EnvironCompleter`), `FilesCompleter`,
  `_FilteredFilesCompleter` with its subclass `DirectoriesCompleter`, and
  `SuppressCompleter`.
- `packages/_shlex.py` is a copy of Python 3.6's `shlex`. The package makes
  one instance: the lexer of `split_line` (`lexers.py:12-14`).

## Scope rules

**A. Edges are per function.** Every function keeps its body edges. The
uncalled methods of `shlex` (`push_token`, `push_source`, `pop_source`,
`sourcehook`, `__next__`) keep the edges that the package's lexer can reach
(judgement 2). `BaseCompleter.__call__` keeps its edge to
`NotImplementedError`.

**B1. Receivers.** `self` of `CompletionFinder` methods is a
`CompletionFinder` or an `ExclusiveCompletionFinder` (both public). So
`self._action_allowed(...)` (`finders.py:354`) has both `_action_allowed`
methods; every other `self.x()` call has the `CompletionFinder` method.
`BaseCompleter` is a plain public base that the docstring offers for
subclassing (`completers.py:24`), so a client can construct it. Its
`default_completer` role comes from the BaseCompleter annotation (B2),
not from constructibility alone (judgement 6).

**B2. Arguments and stored values.**
- `exit_method` (`finders.py:83`): the default `os._exit`. The tests pass
  `sys.exit`, which the docstring suggests (`:100-101`); a function from
  outside the package that the client passes is a client callback.
- `validator`: the default `default_validator` (`:69`). Client functions
  are client callbacks.
- `predicate` of `_FilteredFilesCompleter` (private): only
  `DirectoriesCompleter.__init__` passes one, `os.path.isdir`
  (`completers.py:139`). So `self.predicate(candidate)` (`:132`) is
  `os.path.isdir`.
- `completer` (`finders.py:423`): see "Value sites".

**B3. Not considered.** A package function as a completer or validator
(the documentation offers none). A class that the client adds to
`safe_actions` (`finders.py:117`).

**B4. Concrete outside types.** The parser is annotated
`argparse.ArgumentParser` (`finders.py:40, 56, 81`), so its method calls
are argparse methods (`parse_known_args`, `_get_positional_actions`,
`_get_values`, `_match_argument`, ...). `self._formatter` is annotated
`argparse.HelpFormatter | None` (`:41`). Checks fix the class of an action
in two places: `issubclass(self._orig_class, argparse._SubParsersAction)`
(`:282`) and `self._orig_class in safe_actions` (`:286`).
`completer_output` is checked against `Mapping`, which is abstract: no
class is fixed.

**B5. Client objects are opaque.** The actions of the client's parser are
argparse objects that the client's `add_argument` calls made. Where no
check fixes their class, a call of their `__call__` has no callee.
The public script parser is a separate package-created value: its help,
`--dest`, and `--yes`/`--user` actions retain their concrete classes after
patching and reuse (judgement 3). An object that a client completer returns is opaque
(`finders.py:427`). A non-callable completer (readline protocol, `:442`)
is a client object.

**C. "Public" is judged on the access path.** Private by path:
`argcomplete._check_module`, `argcomplete._check_console_script`,
`argcomplete.packages._shlex.shlex`, and
`completers._FilteredFilesCompleter`. Public: `CompletionFinder`,
`ExclusiveCompletionFinder`, the completers, `split_line`, `shellcode`,
`debug`, `warn`, `mute_stderr`, `argcomplete.io.mute_stdout`, and the two
scripts. `IntrospectiveArgumentParser` is public through its import in
`argcomplete.finders` (`finders.py:16`). The same import makes
`argcomplete.finders.action_is_greedy`, `action_is_open` and
`action_is_satisfied` public; graph names retain their defining module.

## Judgement calls

1. **Branches of the private `shlex` that never run** (lead's ruling:
   keep). Rule B1 (a private class has only the instances that the package
   makes) with B2 (stored values). `shlex` is private (rule C). The package
   makes one instance (`lexers.py:12`): `instream` a str (so an
   `io.StringIO`), `infile` None, `posix=True`, no `punctuation_chars`;
   then `whitespace_split = True` (`lexers.py:13`). Nothing else sets
   `debug` (0, `_shlex.py:52`), `source` (None, `:55`), `filestack` or
   `pushback`, and the lexer never leaves `split_line`. So these sites
   never run and have only a note:
   - `__init__` `63:48`, `67:41`, `67:55`, `68:54` (no punctuation chars);
   - `get_token` `106:40`, `108:22`, `108:53` (`pushback` is empty);
     `115:39`, `115:55`, `118:37`, `119:37` (`source` is None);
     `125:32`, `126:37` (`filestack` is empty); `130:22`, `130:45`,
     `132:22` (`debug` is 0);
   - `read_token` `140:52`, `251:56` (no punctuation chars, no state `c`);
     `261:52`, `263:49`, `265:30` (line 254 always holds, because of
     `whitespace_split`); `146:22`, `156:30`, `193:30`, `211:30`,
     `226:30`, `277:22`, `277:49`, `279:22` (`debug` is 0).

   This leaves out 15 edges: `get_token -> sourcehook`, `push_source`,
   `pop_source`, `get_token`; `get_token -> <builtin>.print`,
   `<builtin>.repr`, `collections.deque.popleft`; `read_token ->
   <builtin>.print`, `<builtin>.repr`, `collections.deque.pop`,
   `collections.deque.append`, `collections.deque.appendleft`; `__init__ ->
   <builtin>.str.maketrans`, `<builtin>.dict.fromkeys`,
   `<builtin>.str.translate`. The trace agrees: `get_token` calls only
   `read_token`.
2. **Methods of `shlex` that the package never calls** (lead's ruling on
   audit A1). `push_token`, `push_source`, `pop_source`, `sourcehook`,
   `error_leader`, `__iter__` and `__next__` never run (`get_token` calls
   `push_source`, `pop_source` and `sourcehook` only in the dead branches of
   judgement 1). By rule A they keep their body edges, and by rule B their
   parameters (`tok`, `newstream`, `newfile`) stay open. Their receiver is
   the same lexer, in the same state, as in judgement 1 (B1): a call of
   one uncalled method does not change the state for another. So these
   sites never run and have only a note:
   - `push_token` `77:18`, `77:49`; `push_source` `91:22`, `93:22`;
     `pop_source` `100:18` (`debug` is 0);
   - `sourcehook` `291:62`, `292:35`, `292:51` (`infile` is None, so
     `isinstance(self.infile, str)` is False and the `and` stops).

   `pop_source` `97:28` keeps only `io.StringIO.close`: `instream` is the
   `io.StringIO` of `:26`. This leaves out 8 edges: `push_token ->
   <builtin>.print`, `<builtin>.repr`; `push_source -> <builtin>.print`;
   `pop_source -> <builtin>.print`, `io.TextIOWrapper.close`; `sourcehook ->
   os.path.isabs`, `os.path.join`, `os.path.dirname`. I read the code again:
   none of these 8 calls is reached with the lexer's state. The methods keep
   `push_token -> collections.deque.appendleft`; `push_source ->
   <builtin>.isinstance`, `io.StringIO`, `collections.deque.appendleft`;
   `pop_source -> io.StringIO.close`, `collections.deque.popleft` (it raises
   `IndexError` on the empty deque, but the call is made); `sourcehook ->
   <builtin>.isinstance`, `<builtin>.open`; `__next__ -> get_token`.
3. **The original `__call__` of an action** (`finders.py:281`, `:285`,
   `:290`; lead's ruling: keep).
   - `:281` runs when `completing` is False. A client can reuse the public
script parser after `CompletionFinder(parser).rl_complete` patches it and
returns. Its package-created default help action reaches
`argparse._HelpAction.__call__`; `--dest` reaches `_StoreAction.__call__`,
and `--yes` or `--user` reaches `_StoreTrueAction.__call__` when `main`
parses the process command line. Other client actions remain opaque.
   - `:285`: `issubclass` fixes `_SubParsersAction` (B4). It calls
     `parse_known_args` on the subparser that `:284` patched, so the site
     also has `IntrospectiveArgumentParser._parse_known_args` (library
     callback).
   - `:290`: the `safe_actions` set (`finders.py:18-26`) fixes seven
     classes (B4); judgement 4 names their functions.
   - `_argparse.py:154` also runs on a directly constructed public
`IntrospectiveArgumentParser`. Its default help action stays native because
`patch` returns at 261-262 for this receiver. The help action is a package-
created library default, so its `__call__` counts.
4. **Names of inherited `__call__` of private argparse classes** (lead's
   ruling on audit N1). The README rule decides: a method of an outside
   object is named by the class of the receiver, also when that class
   inherits it (configargparse names private argparse classes the same
   way). At `finders.py:290:48`, `_StoreTrueAction` and `_StoreFalseAction`
   inherit `_StoreConstAction.__call__`, so the site has
   `argparse._StoreTrueAction.__call__` and
   `argparse._StoreFalseAction.__call__`, and keeps
   `argparse._StoreConstAction.__call__` for receivers of that class. The
   site has 7 names. I checked every other outside method name of the
   ledger: none other is named by a defining class that differs from the
   receiver class. The `argparse.ArgumentParser.*` methods (`add_argument`
   is defined on `_ActionsContainer`) already have the receiver class. The
   one exception stays by ruling: `os.environ.get` is
   `collections.abc.Mapping.get` (judgement 7).
5. **The formatter** (`finders.py:311-312`; B4).
   The default is `argparse.HelpFormatter`. The script parser publicly exposes
   the package-created `RawDescriptionHelpFormatter` configuration. A client can
   add a percent-bearing help string with public `add_argument` and then call
   `rl_complete`, reaching both its constructor and inherited `_expand_help`.
   Name each method through its concrete receiver class.
6. **Completers** (`finders.py:423`; judgements 6 to 11 stand as written, by the lead's ruling): `ChoicesCompleter.__call__`,
   `FilesCompleter.__call__`, `_FilteredFilesCompleter.__call__` (through
   `DirectoriesCompleter`) and `BaseCompleter.__call__`. The
   `default_completer: BaseCompleter` annotation admits these constructible
   package instances (B1, B2). The separate `action.completer` role has
   documented ChoicesCompleter and EnvironCompleter assignments, and the
   SuppressCompleter assignment in `test/test.py:221`. The package also
   constructs ChoicesCompleter from an action's choices. A
   `SuppressCompleter` never gets to `:423`: its `suppress()` returns True,
   so `:420` continues.
7. **`os.environ`.** `os.environ.get(...)` is
   `collections.abc.Mapping.get` (anytree precedent: `os._Environ` is
   private). The tests replace `os.environ` with a dict (`test/test.py:121,
   1063`); those `dict.get` edges are rejected.
8. **`mute_stderr()`** (`finders.py:228:29`): `contextlib.contextmanager.helper`
   and `argcomplete.io.mute_stderr`, as sqlparse's `indent(self)`.
9. **Scripts.** `argcomplete.autocomplete(parser)` (`activate...py:41`,
   `register...py:63`) is a value site: the instance of `__init__.py:12`,
   so `CompletionFinder.__call__`. Reuse of the exposed parser through
   `rl_complete` also makes `activate...main` call the package override
   `IntrospectiveArgumentParser._parse_known_args` (judgement 3). The
   `if __name__ == "__main__":` blocks keep their edges.
10. **Version branches.** `_check_console_script.py:36` (`< (3, 12)`)
    runs on 3.10 and 3.11; its only operation is a subscript of an outside
    object. `_argparse.py:171-178` tests the shape of argparse's option
    tuples (3.11.9+, 3.12.7+); both sides run on some supported version and
    have no call. There is no `if TYPE_CHECKING:` and no optional import.
11. **Exceptions of the package.** `ArgcompleteMarkerNotFound` and
    `ArgcompleteException` define no `__init__`: their calls give
    `<builtin>.RuntimeError.__init__` and `<builtin>.Exception.__init__`.
    The trace names the first `<builtin>.BaseException.__init__`; the
    checker accepts the alias.

12. **Interpreters and optimized execution (round 4).** CPython and PyPy
    are explicitly supported by `pyproject.toml`; no later support drop was
    found. The final classifier is not an upper bound. Under the working
    normal/`-O`/`-OO` union, the assertions do not remove additional edges.
    `consume_optional` reaches its `action_tuples` assertion only after an
    append before each loop break (`_argparse.py:217-218`, `246-247`). The
    greedy-action assertion (`finders.py:376`) guards a package-created list:
    optional parsing gives a singleton, and a positional remainder that
    consumes arguments leaves no arguments for a later remainder. Even an
    opaque client effect that changes the count admits no new completer type.
    Removed None checks still fail at the next attribute access, and the
    predicate is the package's `os.path.isdir`. Under `-OO`, script docstrings
    become `None` descriptions for argparse, with no package dispatch change.
    All 340 baseline pairs remain. This clarifies execution scope independently
    of any graph correction.

## Default rejections

| Candidates | Sites decided | Reason (short) |
|---|---|---|
| `shlex.__iter__`, `shlex.__next__` | 131 | No `shlex` is iterated, unpacked or tested with `in`; the only `shlex` is the lexer of `split_line`, read with `get_token` |

The default decides only implicit sites. Each of the 16 explicit sites
where it would apply has its own rejection with the type of its argument:
`list(...)`, `set(...)` (`completers.py:94`), `enumerate`, `iter`, `set()`,
`max`, `min`, `zip` (`_argparse.py`), and `dict(...)` with keyword
arguments only (`shell_integration.py`).

## Value sites

18 value sites.

| Site | Callees | Size |
|---|---|---|
| `completers.py:132:34` `self.predicate(candidate)` | `os.path.isdir` | 1 |
| `finders.py:148, 155, 160, 205` `exit_method(...)` | `os._exit` | 1 each |
| `finders.py:281:48` `self._orig_callable(...)` | `argparse._HelpAction.__call__`, `_StoreAction.__call__`, `_StoreTrueAction.__call__` | 3 |
| `finders.py:285:48` `self._orig_callable(...)` | `_SubParsersAction.__call__`, `IntrospectiveArgumentParser._parse_known_args` | 2 |
| `finders.py:290:48` `self._orig_callable(...)` | `__call__` of `_StoreAction`, `_StoreConstAction`, `_StoreTrueAction`, `_StoreFalseAction`, `_AppendAction`, `_AppendConstAction`, `_CountAction` | 7 |
| `finders.py:423:49` `completer(...)` | `__call__` of `BaseCompleter`, `ChoicesCompleter`, `FilesCompleter`, `_FilteredFilesCompleter` | 4 |
| `finders.py:428, 433, 445` `self.validator(...)` | `default_validator` | 1 each |
| `_argparse.py:154:27` `action(...)` | `IntrospectAction.__call__`, `argparse._HelpAction.__call__` | 2 |
| `_argparse.py:193:47`, `234:47` `match_argument(...)` | `argparse.ArgumentParser._match_argument` | 1 each |
| `_argparse.py:265:39` `match_partial(...)` | `argparse.ArgumentParser._match_arguments_partial` | 1 |
| `activate...py:41:25`, `register...py:63:29` `argcomplete.autocomplete(parser)` | `CompletionFinder.__call__` | 1 each |

Three `exclude` lines record `IntrospectAction.__call__` at `:281`, `:285`
and `:290`: `patch` skips an action that already has `_orig_class`
(`finders.py:269`), so the original class is never an `IntrospectAction`.

## Rejected trace edges

| Caller | Callee | Why |
|---|---|---|
| `CompletionFinder.__call__` | `sys.exit` | the tests pass `exit_method=sys.exit` (`test/test.py:139`) |
| `CompletionFinder.__init__` | `<builtin>.dict.get` | the tests replace `os.environ` with a dict (`test/test.py:121, 1063`) |
| `CompletionFinder.quote_completions` | `<builtin>.dict.get` | the same |
| `split_line` | `<builtin>.dict.get` | the same |
| `CompletionFinder._complete_active_option` | `<builtin>.dict.items` | the test completer `c_url` returns a dict (`test/test.py:282, 303`) |

## Functions that the tests do not run

25 of 74: the two scripts (14 functions), `_check_module.main`,
`_check_console_script.main`, `mute_stdout`, `BaseCompleter.__call__`, and
seven methods of `shlex` (judgement 2). The trace project notes say why:
only the in-process test classes ran.

## Statistics

| | Count |
|---|---|
| All AST sites | 1,899: the 647 sites below plus 1,252 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 647 (512 call, 4 decorator, 70 iter, 61 op) |
| Sites with candidates / value sites | 265 / 18 |
| Ledger entries | 516 (512 call, 4 decorator) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 497 / 29 (6) / 3 / 118 |
| Default rejections | 1 line, 2 candidates, deciding 131 sites, all implicit |
| Nodes | 89 (15 modules, 74 functions) |
| Edges | 340: 92 in the package, 248 outside |
| Graph edges with a trace name or alias | 206 of 340 (60.6%) |
| Edges only from reading | 134 |
| Trace edges rejected | 5 |
| Functions that the tests run | 49 of 74 |

## Rulings after the audit

The audit (`argcomplete.audit.md`) re-derived 88 sites blind: 82 agree, and
no edge was missed. The lead ruled:

| Item | Ruling | Edges |
|---|---|---|
| Judgement 1 (dead branches of `shlex`) | keep (B1 with B2) | 0 |
| Judgement 2, audit A1 (uncalled `shlex` methods) | the same lexer and state decide: 8 sites never run | -8 |
| Judgement 3 (original `__call__` of an action) | keep (B5 at `:281` and `_argparse.py:154`; B4 at `:285`, `:290`) | 0 |
| Judgement 4, audit N1 (names at `finders.py:290:48`) | name by the receiver class: add `_StoreTrueAction.__call__`, `_StoreFalseAction.__call__` | +2 |
| Judgement 5 (formatter) | keep (B4) | 0 |
| Judgements 6 to 11 | as written; `os.environ.get` stays `collections.abc.Mapping.get` | 0 |

The graph went from 340 edges (91 / 249) to 334 (91 / 243).
