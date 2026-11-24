# configargparse: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release v1.9.0, commit `1829aa14c317374aa1467e1d01f99472282183ff`. Audited
files: the untracked ground truth in the worktree `feat/heldout`
(`configargparse.ledger`: 518 entries, 571 callee lines, 10 rejection lines,
18 exclusion lines, 88 notes; `configargparse.json`: 401 edges, 94 in the
package and 307 outside, to 107 outside callees; `configargparse.rejected.json`:
5 edges; `configargparse.md`: 14 judgements). `check.py --benchmark-dir
macro-benchmark-heldout configargparse` reports no errors. The trace
(Python 3.14.9, 182 passed, 5 xfailed) confirms 331 edges; 70 come from
reading only. 58 of 67 functions run.

I judged the files by the scope rules A, B1-B5 and C of
`macro-benchmark/README.md` and the naming rules of
`micro-benchmark/README.md`. I read the source, the project `README.md` and
the tests as data. I did not run or import the package, and I did not use
any static analysis tool. To check the version judgements I read CPython's
`Lib/argparse.py` for 3.6, 3.7 and 3.8 (fetched from the CPython branches)
and the local 3.9, 3.13, 3.14 and 3.15 sources.

**Final state.** No finding changes the graph. The blind sample agrees with
the ledger at every site. I found no missing edge and no edge that cannot
happen. Three judgements rest on cases that the README does not decide (Q1,
Q2, Q3); I agree with the writer on each and propose a ruling. One remark on
wording (W1).

## Findings

| Id | Kind | Site or edge | Evidence | Edges if ruled otherwise | Decision proposed |
|---|---|---|---|---|---|
| Q1 | needs a ruling (README silent) | `:935:50` `p()` and `:1167:64` `config_file_parser_class()` -> `__init__` of `TomlConfigParser`, `IniConfigParser`, `CompositeConfigParser` (excluded) | These `__init__` take a required argument (`:679`, `:817`, `:933`). A call with no argument raises `TypeError` while it binds the arguments, before the body starts. The micro-benchmark rule says an edge exists when A calls B; here B's code never runs, and `sys.monitoring` sees no start of B. | +6 (3 from `CompositeConfigParser.__init__`, 3 from `ArgumentParser.__init__`) | Keep them out. Proposed README line: "A call that fails to bind its arguments does not run the callee: no edge." |
| Q2 | needs a ruling (README silent) | `:2101:59` `arg_parser.parse_known_args(...)` -> `_WriteOutConfigFileActionMixin.__call__` (left out, judgement 11) | `add_argument` raises its `ValueError`s (`:2318-2336`) after the original method has already added the action to the parser (`:2300`). With both `is_config_file_arg` and `is_write_out_config_file_arg`, the action gets the mixin class (`:2306`) and stays in `_actions`. A client that catches the error and parses reaches `_open_config_files` (`:2077`), which adds that action to `arg_parser` (`:2090`). | +1 (`_open_config_files -> _WriteOutConfigFileActionMixin.__call__`) | Keep it out by B3. Proposed README line: "An object that the package leaves behind after it raised an error to refuse it is not considered (B3)." |
| Q3 | needs a ruling (README silent) | `print_values -> io.TextIOWrapper.write` (`:2170:19`, judgement 6) | The default `file=sys.stdout` (`:2168`) is the value of `sys.stdout` when the module is imported. Its class depends on the environment: `io.TextIOWrapper` in a normal interpreter, pytest's capture object under the tests. The edge is the only one of the graph that rests on an environment-dependent default. | -1 | Keep it (B2, the package's default). Proposed README line: "A default bound from interpreter state (`sys.stdout`) has the type that a normal interpreter gives it." |
| W1 | wording (no change to the graph) | `configargparse.md`, judgement 10 | The judgement lists the parser methods that argparse calls and that the package does not override. It does not say why library code that instantiates the package class `ArgumentDefaultsRawHelpFormatter` (`:84`, as `formatter_class`, through `_get_formatter`) runs no package node: the class defines no method (`:84-91`). | 0 | Add one sentence. |

Two judgements could be read the other way, but the existing rules and
precedents decide them, so I do not raise them as findings:

- `ConfigFileParser` as a receiver (B1, 6 edges): it has no `abc` base, it
  is public, and a client can pass it as `config_file_parser_class` or in
  `config_parser_types`. jmespath R2 (`Visitor`) is the precedent.
- A `CompositeConfigParser` inside a `CompositeConfigParser` (judgement 4,
  4 edges): the annotation `list[ConfigFileParser]` (`:935`) and the
  docstring "composed by other ConfigFileParser instances" (`:927`) admit
  it. B2 says that the annotation decides.

## Step 1: blind re-derivation

**Sample.** I made the skeleton without the ledger, in a scratch benchmark
directory with a copy of `projects.toml` and a link to `projects/`. It has
518 sites, all explicit (517 call, 1 decorator), 27 of them value sites. No
implicit site has a candidate: the package defines no special method other
than `__init__` and `__call__`, and no property. I numbered the sites from 0
in skeleton order and drew `random.Random(20261111).sample(range(518), 70)`.
I added the 27 value sites (1 was already drawn): 96 sites. I wrote the
callees of each site from the source alone, before I opened any file of the
writer (`$TMPDIR/heldout-audit-configargparse/blind.md`, with the draw in
`sample.txt`).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random (70) | 70 | 70 | 0 |
| Value sites not drawn | 26 | 26 | 0 |
| **Total** | **96** | **96** | **0** |

At the three dispatch sites of the sample (`:957:31`, `:1449:66`,
`:1796:63`) I left `ConfigFileParser` open as "B1 literal". The writer
includes it, and so do I after the check above. Before I opened the ledger I
also listed the library callbacks that I expected outside the sample
(`:1157:41`, `:1549:75`, `:2101:59`, `:599:17`, `:860:33`, `:148:61`, the
three `super().__init__()`, the three `is_boolean_optional_action` calls,
the stream methods). The ledger has each of them, with the same callees.

## Step 2: dispatch and value roles

| Site | Values (where they come from) | Callees |
|---|---|---|
| `.parse(stream)` `:957:31`, `:1449:66`; `.serialize(...)` `:1005:41`, `:1796:63`; `.get_syntax_description()` `:995:110`, `:2228:77` | `_config_file_parser` is set only at `:1161-1167`; `self.parsers` only at `:935`. Any package parser instance, `ConfigFileParser` included | the 7 methods of that name |
| `p()` `:935:50` | instances whose `__call__` returns self (README.md:401-403, tests 3597-3602), or classes (tests pass `YAMLConfigFileParser`, `DefaultConfigFileParser`) | `__call__` of Toml, Ini, Composite; no `__init__` (Q1) |
| `config_file_parser_class()` `:1167:64`; `DefaultConfigFileParser()` `:1161:63` | a subclass of `ConfigFileParser` (`:1164`) | none (object.__init__, or Q1) |
| `self.add_argument(...)` `:1180:30`, `:1189:30`; argparse's `__init__` `:1157:41` | `_ActionsContainer.add_argument` is replaced at `:2447` | `configargparse.add_argument` |
| `self.original_add_argument_method(...)` `:2300:47` | saved at `:2444` | `argparse._ActionsContainer.add_argument` (canonical name; `argparse.ArgumentParser.add_argument` now resolves to the replacement) |
| `super(...).__call__(...)` `:148:61` | `type(action)` is an `argparse._StoreAction` (`:2302`); no argparse class from 3.6 to 3.15 derives from it | `argparse._StoreAction.__call__` |
| `argparse.ArgumentParser.parse_known_args(self, ...)` `:1549:75` | the actions and subparsers of a configargparse parser | + `_WriteOutConfigFileActionMixin.__call__` (action call), `ArgumentParser.format_help` (`_HelpAction` -> `print_help`), `ArgumentParser.parse_known_args` (`_SubParsersAction.__call__`, `parser_class` defaults to `type(self)`; the same call in 3.6, 3.7, 3.8, 3.9 and 3.14) |
| `arg_parser.parse_known_args(...)` `:2101:59` | the plain argparse parser of `:2086`, whose `error` is `error_method` (`:2098`) | + `_open_config_files.error_method` |
| 8 `self.error(...)`; `self.exit(0)` | inherited; `:2098` replaces `error` only on `arg_parser` | `argparse.ArgumentParser.error`, `.exit` |
| `is_quoted(...)` `:599:17`, `:860:33` | the `_lru_cache_wrapper` of `:577` | `functools._lru_cache_wrapper.__call__`, `is_quoted` |
| `is_boolean_optional_action(action)` `:1906`, `:1917`, `:1924` | version branch `:31` (3.6-3.8 and 3.9+ both supported) | `<lambda1>`, `<lambda2>` |
| `self._config_file_open_func(...)` `:1799:53`, `:2033:73`, `:2110:57` | default `open` (`:1114`) | `<builtin>.open` |
| stream methods: `read` `:335`, `:705`, `:834`; `seek` `:971`; `close` `:1519`; `close` `:2130`; `write` `:1802` | `StringIO(config_file_contents)` (`:1439`) and text files of `open` | `io.StringIO.*` and `io.TextIOWrapper.*`; `:2130` and `:1802` only `io.TextIOWrapper` (no `StringIO` reaches them) |
| `action.choices.values()` `:2361:51` | `_name_parser_map`: `_collections.OrderedDict()` in 3.6 (`Lib/argparse.py:1076` of the 3.6 branch), `{}` from 3.7; else a dict by the `isinstance` at `:2387` | `<builtin>.dict.values`, `collections.OrderedDict.values` |
| `items.items()` `:251:38`, `:404:38`, `:905:38`; `config_items.items()` `:1456:53` | docstrings `:113`, `:124` say OrderedDict; the package builds one (`:1839`) | `collections.OrderedDict.items` (lead's B4 ruling, judgement 7) |

Every other `self.x(...)` site names a method that only `ArgumentParser`
defines (or only `YAMLConfigFileParser`, for `_load_yaml`). The package
defines no subclass of those classes.

## Step 3: the 70 edges from reading only

| Class | Edges |
|---|---|
| Paths of tested functions that the tests do not take | 22: `ArgumentParser.error` from `_open_config_files`, `_reject_write_out_config_file_args` and `parse_known_args` (3); `argparse.ArgumentError` from `parse_args` (exit_on_error=False); `ValueError`, `str.format`, `type` in `convert_item_to_command_line_arg` (a tuple from `ast.literal_eval` at `:380` reaches `:1982`); the error calls of `CompositeConfigParser.parse` (`Exception.__init__`, `repr`, `str`, `str.join`), `DefaultConfigFileParser.parse` (`Exception.__init__`, `getattr`, `str.format`), `IniConfigParser.parse` (`Exception.__init__`, `str`), `ConfigparserConfigFileParser.parse` (`str`), `YAMLConfigFileParser.parse` (`getattr`, `type`: a YAML file that is not a mapping); the quoted-string branch of `unquote_str` (`ast.literal_eval`, `isinstance`, `ValueError`) |
| Dispatch to parser classes that the tests do not use at that site | 22: `format_help` (6 `get_syntax_description`), `parse_known_args` (3 `parse`), `write_config_file` (5 `serialize`), `CompositeConfigParser.parse` (3 `parse`), `CompositeConfigParser.serialize` (5 `serialize`) |
| Bodies of functions that the tests never run (rule A) | 15: the 3 `ConfigFileParser` methods (`NotImplementedError`); `CompositeConfigParser.get_syntax_description` (`enumerate`, `guess_format_name`, 6 `get_syntax_description`); `guess_format_name` (`str.lower`, `.strip`, `.replace`, `.upper`) |
| Nested `CompositeConfigParser` (judgement 4) | 4: `__init__ -> __call__`, and the self-edges of `parse`, `serialize`, `get_syntax_description` |
| Version and optional-import branches | 4: `<lambda2>` (3.6-3.8), `toml.loads` (before 3.11), `_load_yaml -> Exception.__init__` (no PyYAML), `collections.OrderedDict.values` (3.6) |
| Package streams and defaults | 3: `ConfigparserConfigFileParser.parse -> io.TextIOWrapper.read`, `CompositeConfigParser.parse -> io.StringIO.seek` (`config_file_contents`), `print_values -> io.TextIOWrapper.write` (Q3) |

All 70 are possible on a supported version. None cannot happen.

## Rejected trace edges

All 5 stay rejected. Each callee is a method of an object that a test
supplied: the `MagicMock` that patches `argparse.ArgumentParser.__init__`
(test `:1148`), the `StringIO` passed as `file` (`:1246-1247`), the plain
dicts passed as `items` (`:3582`, `:4436`, `:4446`; lead's ruling), and the
`BytesIO` stream (`:3487-3496`). `TomlConfigParser.parse ->
<builtin>.bytes.decode` stays in the graph: the `isinstance` at `:707` fixes
the type (B4), and the trace confirms it.

## Steps

1. Blind sample: 96 sites (70 seeded, 26 more value sites). 0 disagreements.
2. Dispatch and value roles: every site in the table above. 0 differences.
3. Untraced edges: all 70 classified as possible.
4. Nodes: 68 (the module, 67 functions with 2 lambdas). 7 functions have no
   package caller (`parse_args`, `print_values`, `get_source_to_settings_dict`,
   `get_argument_parser`, and the `__init__` of Toml, Ini, Composite): each
   is client-only, and each keeps its body edges (rule A).
5. Special methods: the 4 `__call__` and 4 `__init__`. Callers checked
   (`:66:36`, `:935:50`, `:1549:75`). No property, no other special method,
   no class site with a candidate.
6. Default rejections: none.
7. Rejections and notes: all 10 rejection lines, 18 exclusion lines (24
   nodes) and 88 notes. Each reason holds. The note at `:2101:59` ("whose
   `__call__` is library code") holds under Q2.
8. Outside callees: all 307 edges, grouped by the 107 callees. Each exists
   and is named by the micro-benchmark rules, or by its canonical name where
   no public path reaches it (`argparse._ActionsContainer.add_argument`,
   `argparse._StoreAction.__call__`, `functools._lru_cache_wrapper.__call__`,
   `functools.lru_cache.decorating_function`). The explicit
   `super().__init__()` calls give `<builtin>.object.__init__`, as h11 gives
   `abc.ABC.__init__`.
9. Judgements 1-14 of `configargparse.md`: all hold. I verified judgement 3
   in the CPython 3.6 source and judgements 8 and 10 in 3.6 to 3.15.
   Judgements 5, 11 and 6 are Q1, Q2 and Q3.
10. Statistics of `configargparse.md` match the ledger and the checker.

## Judgement

The ground truth is complete and precise for the rules as they stand. The
sample has no disagreement, the dispatch sets are right, and every untraced
edge is possible. The three cases that the README does not decide (Q1, Q2,
Q3) are decided in the direction that the nearest rule supports. Ruled the
other way, they would change the graph by +6, +1 and -1 edges.

## Round 3: supported PyPy cache wrappers (2026-11-16)

A focused source review found two missing outside edges. Calls of cached
`is_quoted` from `unquote_str` (599:17) and `IniConfigParser.parse`
(860:33) run `functools._lru_cache_wrapper.wrapper` on supported PyPy
3.11 / 7.3.20. This supplements the accepted round-3 stage: 406 to 408
edges, zero removals. It does not repeat the whole-project audit.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4: complete source-first audit (2026-11-16)

A fresh source model was frozen before reading the baseline. The complete
runtime module, supported-runtime declarations, parser-role documentation and
pertinent tests were read as inert text/AST. All 408 pairs, 1,549 source sites,
68 bodies (11 with no edges), 24 exclusions and six trace rejections were
reviewed. No pair or node changes were found.

Metadata now states the CPython/PyPy >=3.6 scope and the normal/-O/-OO union
working assumption. The assertion-only explanation at line 1916 now accounts
for optimized execution; no target changes. The judgement header labels the
pass-2 count 406 as historical; the current count remains 408. Prior audit
bytes above are unchanged. Complete coverage and freeze manifests accompany
the round-4 audit evidence.
