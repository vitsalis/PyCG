# sqlparse: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release 0.6.1, commit `09dbe1eec31ed1b3cd05366748865f11ba427d32`. The audited
files are not committed yet; their SHA-256 prefixes identify them:
`sqlparse.ledger` `d4dafd9d` (1000 entries, 1043 callee lines, 199 rejection
lines of which 114 `reject *`, 3 exclusions, 164 notes, 4 default lines for
13 candidates), `sqlparse.json` `22cd7d59` (696 edges: 439 in the package,
257 outside, to 80 outside callees), `sqlparse.md` `db071859`,
`sqlparse.rejected.json` `92d615f7` (2 edges). The trace (Python 3.14.9,
535 passed) confirms 660 edges; 36 come from reading only. `check.py
--benchmark-dir macro-benchmark-heldout sqlparse` reports no errors.

I judged by the README scope rules A, B1 to B5 and C. I read all 21 modules
of `sqlparse/`, `docs/source/api.rst` and `extending.rst`, the tests and the
examples, as data. I did not run or import the package, and I used no static
analysis tool.

**Final state.** No finding changes the graph. I found no missed edge and no
edge that cannot happen. Three cases need a ruling (R1 to R3); the writer
raised R1 and R3. One wording fix is optional (W1). Two remarks are on the
process and the tools (T1, T2). The graph stays at 696 edges.

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Proposal |
|---|---|---|---|---|---|
| R1 | ruling (the writer raised it) | the 4 function edges to `tokens._TokenType.__getattr__`: `StatementSplitter.process` (`statement_splitter.py:188:43`), `StripCommentsFilter._process` (`others.py:35:32`, `35:42`), `find_delimited_spans` (`keywords.py:108:55`, `108:65`, `111:55`), `Comment.is_multiline` (`sql.py:554:66`) | `__getattr__` caches each child type in the parent's instance dict (`tokens.py:26`). No module code creates `Comment.Multiline` or `Comment.Multiline.Hint`, so the first function that loads one in a process calls `__getattr__`. Each site can be first in a fresh process through the public API: `split('select 1')` reaches 188:43 (the text has no `/*` or `$`, so `find_delimited_spans` returns at line 89); `parse('/* c */')` reaches 111:55; `parse('/*+ h */ select 1')` reaches 108:55 and 108:65; `format(';', strip_comments=True)` reaches 35:32 (the splitter loads `Multiline` only for a token other than `;`, line 180); `format('select 1', strip_comments=True)` reaches 35:42; `sql.Comment([...]).is_multiline()` on a group that the client builds reaches 554:66 (the tests also build groups by hand). The README has no rule for edges that depend on what ran before in the process. | 0 (keeps 4) | An edge counts if some client program that uses the public API makes it in a fresh process. Keep the 4 edges. |
| R2 | ruling (an unwritten assumption) | `sqlparse.md`, "Token types", point 4: a client that reloads `sqlparse.tokens` or deletes a cached type "is not considered" | After `importlib.reload(sqlparse.tokens)`, `T.String`, `T.Name` and `T.Keyword` name new types without children. A function load such as `T.Keyword.Order` (`grouping.py:414:51`) would then call `__getattr__` again. This would add 9 edges: `TruncateStringFilter.process`, `group_arrays`, `group_identifier`, `group_order`, `group_period.post`, `group_period.valid_prev`, `group_tzcasts.match`, `Identifier.get_ordering`, `TokenList._get_first_name`. The package does not support that state either: the lexer and the `M_OPEN`/`M_CLOSE` class attributes keep the old types, so `is` tests fail. | 0 (+9 if the lead rules otherwise) | Agree with the writer. Write it down beside B3: a state that only a client's change to package internals makes (reloading a module, deleting a cached attribute) is not considered. |
| R3 | ruling (naming; the writer raised it) | `cli.py:65` to `157`, `group.add_argument(...)` on an `argparse._ArgumentGroup`, named `argparse.ArgumentParser.add_argument` | The method is `argparse._ActionsContainer.add_argument` for both receivers. The micro-benchmark rule names a method through "the public import path of the class of the instance", and `_ArgumentGroup` has none. The checker accepts the writer's name through the trace alias of `_ActionsContainer.add_argument`. | 0 (+1 with a second name) | Keep the writer's name: it is one node for one function, and the checker matches it. |
| W1 | wording (optional) | `default reject sqlparse.tokens._TokenType.__getattr__` | The reason lists the receivers that are not token types as "a module, a class, a token or token list, a filter, a str, a list, a dict, a re.Match, an argparse object". The default also decides sites whose receiver is a `super()` object (`tokens.py:24:28`), a `Lexer` class or instance, a `StatementSplitter`, a `FilterStack`, a `DelimitedSpans`, a file or `sys` stream, or `bytes` (`lexer.py:129:33`). The operative clause "not a token type" holds at all of them; `sqlparse.md`, point 7, already names `super()`. | 0 | Optional: end the list with "or another object that is not a token type". |
| T1 | process remark | the seeded sample of the brief | No default exists in the skeleton without a ledger, so 2274 of its 3508 sites are attribute loads. The 70-site sample drew 44 of them: 27 load an attribute of a module (19 in `keywords.py`), and only 2 can call the candidate. Only 19 sampled sites were explicit calls. | 0 | For a package where one candidate dominates, draw the sample by kind, as the cachetools audit did (implicit sites and others separately). |
| T2 | tool remark (the writer raised it) | the 45 `sql.Token(...)` sites and `lexer.py:160:42` | The site finder treats these calls as value sites: some package code assigns an attribute with the same name (`Token`, the token type, at `tokens.py:35` and `:64`; the slot `is_keyword` at `sql.py:67`). The callee is the class `sql.Token` or the method `Lexer.is_keyword`. Each site needs a note that adds nothing. | 0 | No change needed. The tool could skip a call `m.X(...)` when `m` is a package module and `X` is a class that `m` defines. |

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch directory with a copy of
`projects.toml` and a link to `projects/`, then `check.py --benchmark-dir
<scratch> --skeleton sqlparse` (3508 sites). I numbered the site lines from 0
in file order and drew `random.Random(20261111).sample(range(3508), 70)`.
Then I added all 62 value sites, none of which was in the sample: 132 sites
in all. I wrote my callees for each site from the source before I opened any
file of the writer (the scratch file `blind.md`).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random sample (19 call, 44 getattr, 4 getitem or iter, 2 op, 1 format) | 70 | 70 | 0 |
| Value sites | 62 | 62 | 0 |
| **Total** | **132** | **132** | **0** |

Classified differences:

- **Naming or placement only (1):** `aligned_indent.py:78:40`
  `' '.join(map(str, cond))`. I put the call-backs `Token.__str__` and
  `TokenList.__str__` at the `join` site, or at `map` (78:44). The writer puts
  them at 78:44 (judgement 7). Both sites are in `_process_case`, so the graph
  is the same.
- **Auditor error (1, a count):** I wrote that 53 value sites are
  `sql.Token(...)` calls; there are 45. Each site was compared on its own, so
  no comparison changes.
- **The writer missed an edge (0). The writer has an edge that cannot happen (0).**

The two sampled loads that accept `__getattr__` (`keywords.py:179:64`
`Keyword.Order`; `tokens.py:55:17` `Token.Comment`) and the 17 non-trivial
value sites (the `group()` list, the four `_group` call-back roles, `f(tlist)`
in `wrapped_f`, the three `getattr(self, ...)` dispatches, `self.convert`,
`cls()`, `rexmatch`, `self.is_keyword`, `func(token)`, `func(tk)`,
`grp_cls(subtokens)`) all agree, including the exclusions of the
`@recurse` functions at 478:13 and of the default lambdas of `_group`.

## Step 2: exhaustive checks

**`_TokenType.__getattr__` (2236 default sites, 40 accepted).** I worked out
the import order before I opened the ledger: `sqlparse/__init__.py:14`
imports `cli`, then `engine` (`grouping` -> `sql` -> `tokens`, `utils`; then
`filter_stack` -> `lexer` -> `keywords`), then the filters and `formatter`.
Any import of a submodule runs the package first. The 33 types that module
code creates (21 in `tokens.py:38-71`, 2 in the class body of `TypedLiteral`
at `sql.py:497-498`, 4 in `grouping.py:22-24`, 6 in `keywords.py` at 120,
161, 179, 193 and 793) match the writer's table site by site. I then listed
every load whose receiver is a token type: the chains on `T` or `tokens`, and
the `tokens.py` module variables. There are 155. The 40 accepted ones are the
33 above and the 7 function loads of R1. The 115 others load a type that
module code created before any package function can run (for example
`keywords.py:180:38` and `794:30`, the second loads of `Keyword.Order` and
`Keyword.DCL`). Among the 166 distinct receiver expressions of the other
2081 sites, none is a token type. No library call of the package looks up an
instance attribute of a token type: `str()`, `repr()`, `in`, `len()` and
`str.join` use type slots, and `isinstance` finds `__class__` by the normal
lookup. `super().__getattr__(self, name)` (`tokens.py:24:39`) has no callee.
The 31 sites of the default on the 10 local `match` functions are all
`x.match(...)` on a token or a `re.Pattern`.

**`TokenList.__getitem__` (310 default sites) and `__iter__` (196).** The
operand is a `TokenList` at exactly 9 sites, and the ledger accepts each:
`tlist[...]` at `grouping.py:190:22`, `306:14`, `aligned_indent.py:54:41`,
`59:38`, `reindent.py:167:32`, `238:49`; `list(tlist)` at `grouping.py:47:22`
and `518:22`; `for token in tlist` at `reindent.py:205:26`. Every other
operand is a list (`self.tokens`, its slices, `_groupable_tokens`), a tuple
(the pairs of `_token_matching`, `get_cases`, `M_OPEN`), a str, a dict, a
`re.Match`, a generator or an annotation.

**Dispatch sets, all identical to the ledger.**

| Role | Values (B2) | Callees |
|---|---|---|
| `filter_.process`, `filter_stack.py:34:41` / `44:36` / `47:43` | what `FilterStack.__init__`, `formatter.build_filter_stack` and `sqlparse.format` append; tests, docs and examples add no filter | 3 / 7 / 2 |
| `self._process`, `output.py:30:36` | `OutputFilter` is public and not abstract (B1) | 3 |
| `func(stmt)`, `grouping.py:478:13` | the list at 447-477; 8 names are bound to `wrapped_f` | 18 (8 excluded) |
| `f(tlist)`, `utils.py:78:14` | the 8 `@recurse(...)` functions of `grouping.py:251-423` | 8 |
| `match`, `valid_prev`, `valid_next`, `post` in `_group` (`532:17` to `537:40`) | the 11 package calls (115 to 331) and the recursion at 529; the default lambdas are never used | 11, 10, 11, 10 |
| `func(token)`, `sql.py:253:24` / `func(tk)`, `278:48` | the matchers of `token_first`, `token_next`, `token_next_by`, `token_not_matching`; `token_matching` gets only client functions (`tests/test_tokenize.py:114-116`) / the lambda of `grouping.py:340` | 4 / 1 |
| `grp_cls(subtokens)`, `sql.py:336:26` | 18 group classes, none with its own `__init__` | `TokenList.__init__` |
| `getattr(self, '_process_' + name)`: `reindent.py:143:13`, `aligned_indent.py:135:13`, `others.py:88:13` | the class names of the groups that `grouping` makes; `Values` (443), `Function` (407) and `Where` (366) exist | 7, 5, 3 |
| `self.convert`, `filters/tokens.py:21:37`, `35:37` | `'upper'` (default) and the values of `docs/source/api.rst:27-33` | 3 |
| `indent(...)`, `offset(...)` (11 call sites) | `@contextmanager` (`utils.py:117`, `124`) | `contextlib.contextmanager.helper` and the generator function, as the micro case `context_managers/contextmanager_generator` |

B1 receivers: `flatten` (`sql.py:174:61`, `209:34`, `222:41`: only
`TokenList.flatten`; `reindent.py:173:48`, `176:52`, `236:37`: both),
`get_alias` and `get_real_name` (`sql.py:365:30`, `378:30`, `378:54`: both
classes; `408:43`: `NameAliasMixin` only), `_get_repr_name` (both), and the
`str()` sites (both `__str__` methods, except `TokenList.__str__` only where
the value is a `Statement`, and `Token.__str__` only at `right_margin.py:34:26`
and `aligned_indent.py:114:35`). The filter classes have no package
subclasses except `_CaseFilter` and `OutputFilter`, and the ledger rejects
the methods of the other filter class at every `self.` call.

**The 36 untraced edges.** All can happen: `sqlparse.__main__` (2, for
`python -m sqlparse`); the error paths to `<builtin>.Exception.__init__`
(2), `TypeError` and `type` (2); the 4 `__getattr__` edges (R1); the 8 edges
to `utils.indent` and `utils.offset`; `RightMarginFilter._process` (10, rule
A); `OutputFilter.process -> OutputFilter._process`;
`group_where -> SquareBrackets._groupable_tokens` (for example
`select a[where 1]`: the brackets group first, then `group_where` finds no
closing keyword at line 359); `_stripws_identifierlist -> list.remove`
(whitespace before a comma); `get_name` and `has_alias` on groups that are
not an `Identifier` or a `Function` (3); `insert_after -> list.append` (no
next token); `token_index -> token_index` (a `start` that is not an int).

**Nodes with no caller (42).** The 21 modules, the 2 default lambdas of
`_group` (dead), and 19 public methods or functions that only clients call
(`parse`, `split`, `Token.__repr__`, `is_child_of`, `has_ancestor`,
`get_token_at_offset`, `token_matching`, `has_alias`, `get_parent_name`,
`Statement.get_type`, the 4 `Identifier` methods, `get_parameters`,
`get_window`, `Comparison.left`, `right`, `Comment.is_multiline`). Each keeps
the out-edges of its body. The special methods and properties have the right
callers: `Token.__init__` 12, `TokenList.__init__` 3, `__str__` 6 and 8,
`__getitem__` 5, `__iter__` 3, `_TokenType.__contains__` 5, `__repr__` 1
(`Token._get_repr_name`), the three `_groupable_tokens` 1 each, `leading_ws` 2.

**Rejections and notes.** I read all 199 rejection lines and all 164 notes.
Every reason holds; W1 is the only wording point.

**Outside callees and rejected trace edges.** All 80 outside names resolve.
78 match a trace name or alias (for example `bisect.bisect_left` =
`_bisect.bisect_left`, `threading.Lock` = `_thread.lock`,
`io.TextIOWrapper.readlines` = `_io._IOBase.readlines`). `<builtin>.TypeError`
and `sys.exit` are untraced and correct. The B4 decisions hold:
`<builtin>.dict.get` on the `options` dicts that the package passes;
`<builtin>.bytes.decode` after `isinstance(text, bytes)`; no callee for
`text.read()`, because `io.TextIOBase` is an abstract base class. So the two
rejected trace edges (`get_tokens -> _io.StringIO.read`,
`-> _io.TextIOWrapper.read`) are client streams (`tests/test_split.py:123`,
`130`; `tests/conftest.py:45`), and the rejection is correct (B4, B5).

**Judgement calls in `sqlparse.md`.** All 10 hold. I checked the cited facts:
`pyproject.toml:29` (`>=3.10`), `docs/source/api.rst:27-33`,
`docs/source/extending.rst:83`, `tests/test_tokenize.py:254-263` (collection
creates `Comment.Multiline` and `.Hint` before any test, which is why the
trace has none of the 4 function edges of R1). The statistics of the md
match the files and the checker.

## Judgement

The ground truth is complete and precise as far as reading the source can
tell. The trace confirms 660 of 696 edges, and the other 36 can each happen.
The large default on `__getattr__` is right: I derived the same 40 accepted
sites independently, and no other site can make a first load. The open
points are rulings and wording only (R1 to R3, W1). None of them changes the
graph unless the lead rules R2 against the writer (+9 edges) or R3 for a
second name (+1 edge).

## Same-function placement clarification (2026-11-16)

Original M4 moves Token.__str__ and TokenList.__str__ from map78:44 to
join78:40 inside AlignedIndentFilter._process_case. README ruling 12 allows
either attribution because this function constructs and consumes the map.
This is one normalization group, not a baseline defect. Four other original
metadata groups remain corrections. Both chosen relations and all graph
pairs are unchanged.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 source-first audit (2026-11-16)

Read all 21 runtime modules before comparing the baseline. The frozen
inventory contains 223 functions/lambdas and 4,193 sites. All 697 baseline
pairs, all 1,000 ledger entries, the 3,193 omitted sites, the 13 default
candidates and the 10 exclusions were checked. The graph remains at 244
nodes and 697 pairs, with no site-to-callee changes.

The current judgements now state the release's explicit CPython and PyPy
support from Python 3.10 and the working normal/-O/-OO union. The sole
assertion is satisfied by package calls; optimization adds no target.
Token-type first-load witnesses, filter and grouping callback roles,
contextmanager callbacks, abstract stream opacity and zero-edge bodies
remain consistent with the global rules. The prior same-function map/join
placement remains an allowed normalization, not a newly found defect.

The source-first model's phrase about inherited tuple.__new__ was corrected
in separate review evidence after freezing: `_TokenType(...)` has no
constructor edge under the benchmark convention. That wording error never
became a graph proposal. Historical audit text above is unchanged.
