# markdown2: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [markdown2.md](markdown2.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release 2.5.5, commit `150454e3ba02caa3994d19cb5a8344fc92f3ce13`, analysed
source `lib/markdown2.py`. Audited files: the uncommitted ground truth in
the worktree of `feat/heldout-2` on 2026-11-13 (SHA-256 prefixes:
`markdown2.ledger` 3971dd86, `markdown2.json` 241b8a4c, `markdown2.md`
cc42e2f8, `markdown2.rejected.json` 24cdd60f). The ledger has 1316 entries,
1415 callee lines and 75 notes. The graph has 872 edges: 281 in the package,
591 outside. The trace confirms 752 edges, 120 come from reading only, and
1 trace edge is rejected. 10 nodes have no caller. `check.py markdown2`
reports no errors.

I judged the files by the scope rules of `macro-benchmark/README.md` (A,
B1 to B5, C) and the naming rules of `micro-benchmark/README.md`. I read the
whole module and its docstrings, and as data `setup.py` (`pygments>=2.7.3`
at :33, `python_requires=">=3.9, <4"` at :59), `CHANGES.md` and the names
in `test/`. I did not run or import the
package, and I did not use PyCG or any other static analysis tool.

**Result.** The ground truth is sound. The blind sample and the exhaustive
checks found no missing edge and no edge that cannot happen. One finding
changes a ledger line but not the graph (F1). Two remarks concern the README
and `sites.py` (R1, R2). Of the 13 judgement calls, the nearest rules
support all 13 as the writer decided them; J6 needs one correction (F1).

## Findings

| Id | Severity | Site | Evidence | Edges |
|---|---|---|---|---|
| F1 | Low (false reason; site-level miss) | `_memoized.__call__` 4563:29 `self.func(*args)`; `markdown2.md` J6 and the "Exclusions" row | The exclusion says that the arguments are always hashable. They are not. `tab_width` is annotated `int` (`markdown2.py:312`), and a client `int` subclass with `__hash__ = None` fits that annotation (B2: client objects; B4: it is an `int`). It passes `tab_width * " "` (326) and `'%d' % tab_width` (386). Then `self.cache[args]` (4556) raises `TypeError`, and 4563 calls `self.func`. Fix: give 4563:29 the two callees of 4558:49, drop the exclusion, and correct J6. | 0 (both edges already come from 4558:49) |
| R1 | Remark (tool) | `sites.py:564-582`, `_assignments` | A class-body annotation without a value (`tags: List[str]` in `_LinkProcessorExtraOpts`, `markdown2.py:2987`) puts `tags` into `value_names`. So `self.tags(...)` (3618:25) and `super().tags(...)` (3826:28) are value sites "by name only", as the writer noted. The README says a value site needs a name that the package *assigns a value to*; a bare annotation assigns nothing. The tool over-reports, which only adds scrutiny. Either the tool skips `AnnAssign` with `value is None`, or the README says that annotations count. | 0 |
| R2 | Remark (README gap) | J3, J4, J7 and F1 | The README does not decide (a) branches on the version of a dependency (J3), (b) the names in a third-party module that is not installed and cannot be read (J4), (c) whether an annotation limits the values a client passes. B2 admits client objects; B4 uses the annotation to fix the type of a value for method names. J7 keeps a branch for a value the annotation excludes (bytes for `text: str`); J6 removed a branch for a value the annotation admits (F1). A sentence such as "an annotation names the outside type for method calls (B4); it does not remove a branch that the code takes on purpose for another client value" would decide both. | 0 |

## Step 1: blind re-derivation

**Skeleton.** I made a scratch benchmark directory with a copy of
`projects.toml` and a `projects` link, and ran
`check.py --benchmark-dir <scratch> --skeleton markdown2`. The skeleton has
1445 sites: 1288 call, 27 decorator, 83 op, 1 getattr, 46 format; 538 with
candidates; 15 value sites. I numbered the sites from 0 in skeleton order.

**Draw.** `rng = random.Random(20261111)`; `rng.sample(all sites, 70)`; then,
with the same `rng`, `rng.sample(the plain sites not yet drawn, 40)` (the
lead's addition, because a script of the writer drafted the plain entries);
then every value site. One value site (1120:37) was already in the first 70,
so the sample has 124 sites: 112 call, 6 op, 3 decorator, 3 format; 50 have
candidates. Calls dominate the skeleton (89%), and the calls are the sites
that the drafting script touched, so I did not draw by kind.

I wrote the callees of each site from the source alone, before I opened any
of the writer's files. The answers are in
`$TMPDIR/heldout2-audit-markdown2/blind-answers.txt` (SHA-256
`0233e410…ae5331`, written 19:33 local time).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random (first 70) | 70 | 69 | 1 |
| Plain (next 40) | 40 | 40 | 0 |
| Value sites | 15 (1 also in the first 70) | 14 | 1 |
| **Total** | **124** | **122** | **2 (1.6%)** |

The 2 disagreements:

- **Auditor wrong (1): 263:34 `extra.test(text)` in `inner`.** I gave the
  "after" site the `test` methods of all 20 registered extras. The writer
  gives it only the classes that `register()` puts into an "after" list
  (`Extra._exec_order[stage][1]`); Admonitions, LinkPatterns, Strike and
  Underline have no "after" part in their `order` (3329, 3689, 4085, 4201)
  and are never inserted next to a class that is in one. I re-derived both
  lists: the writer is right. No graph change: 251:34 gives `inner` those
  four `test` methods.
- **Writer missed a callee at the site (1): 4563:29.** See F1. No graph
  change.

In the other 122 sites, callees, rejections and outside names agree, also on
the points where a script could err: `_hashlib.HASH.hexdigest` (150:70),
`functools.lru_cache.decorating_function` and `functools.partial.__call__`
for the decorators, `mark_stage.wrapper.inner` for the decorated methods,
`_memoized.__call__` for the two rebound names, `<builtin>.dict.get` after
the `isinstance` test of `header-ids` (955:51), and the callback of each
`re.Pattern.sub`.

## Step 3: exhaustive checks

- **Dispatch sets.** I rebuilt `Extra._exec_order` from the `order` of the
  20 registered classes and the insertion rule of `register()`
  (2485-2508). Before lists: Admonitions, CodeFriendly, FencedCodeBlocks,
  Latex, LinkPatterns, MarkdownFileLinks, MiddleWordEm, Mermaid, Numbering,
  Strike, Underline, Wavedrom. After lists: Alerts, Breaks, CodeFriendly,
  FencedCodeBlocks, Latex, Mermaid, Wavedrom, MarkdownInHTML,
  MarkdownFileLinks, MiddleWordEm, PyShell, SmartyPants, Tables,
  TelegramSpoiler, WikiTables. The callees of 251:34 (10), 252:41 (11),
  263:34 (12) and 264:41 (14) match. The `__init__` set of 422:45 (4)
  matches. `self.process_span` (2684:66), `self.parse_inline_anchor_or_image`
  (3239:59), `self.tags` (3618:25), the `super()` calls (14 sites) and
  `_iab_processor`/`link_processor` (2056, 2057, 1557, 1558) match the MRO.
  I agree that a client could call `LinkProcessor.register()` or
  `GFMItalicAndBoldProcessor.register()`, but no code, test or document of
  the package registers them, so B2 and B3 keep them out of `inner`.
- **Callback roles.** All 35 `sub` sites with a package callback, the two
  `sort(key=...)` sites (551:31, 2172:35), `map` (1595:75),
  `pygments.highlight` (1919:34), the two `lru_cache` methods (2904:45,
  2953:47), `_curry.result` (4417:24), `callback` (1120:37) and
  `_memoized.func` (4558:49) have the right callees. `repl(match)`
  (3703:32) has none: the role is a bare `Callable` (B2).
- **Default rejections.** I read all sites of both defaults
  (`--report --default`). The 77 sites of the `sub` default are `re.sub` or
  the `sub` of a compiled pattern; every `self.sub` callback is accepted
  explicitly. No `_memoized` object reaches any of the 163 sites of the
  `__repr__` default (the only two are module globals that the package only
  calls).
- **Functions that no site calls (10).** `Extra.deregister`, `Extra.run`,
  the 5 functions of `ItalicAndBoldProcessor`, `_NoReflowFormatter.format_description`,
  `_memoized.__repr__`, `markdown_path`. Each is right: public with no
  package caller, abstract with no package subclass, or never called by
  argparse.
- **Special methods and properties.** The package defines `__init__`,
  `__call__` and `__repr__` only, and one property (`_safe_href`, 3145:46).
  No `with`, iteration, operator or format site can reach a package special
  method; no attribute load runs another property.
- **Plain entries (the drafted ones).** I grouped all 591 outside edges by
  callee and read the receiver of every method call (226 `str`, 84 `list`,
  60 `dict`, 150 `re.Match`, 88 `re.Pattern`, and the rest). Every receiver
  has the type that the callee names. A script check found no site where the
  outside method name differs from the attribute called, except the two
  `lru_cache` methods, which are right.
- **Notes and rejections.** I read all 52 distinct rejection and exclusion
  lines and the notes of the 13 explicit sites without callees. They are
  correct, except the exclusion at 4563:29 (F1).
- **Outside names.** The I/O names follow the receiver class
  (`io.TextIOWrapper` for `sys.stdin`/`sys.stdout` and `open(...)`,
  `io.BufferedWriter`/`io.BufferedReader` for the `Popen` pipes,
  `codecs.StreamReaderWriter.read`, and `io.BufferedReader.close` through
  `__getattr__`). `raise MarkdownError(...)` gives
  `<builtin>.Exception.__init__` (3 sites). I checked each of the 120 edges
  from reading only; all are reachable. 62 belong to `main`,
  `markdown_path`, `_regex_from_encoded_pattern` and `_test`, which the
  tests do not run. The other 58 belong to code that the tests do not
  reach: `ItalicAndBoldProcessor`, `Extra.deregister`, Wavedrom, parts of
  Numbering, safe mode with raw HTML, error paths, and the pygments < 2.12
  branch.
- **Rejected trace edge (1).** `Markdown.__init__ -> <builtin>.dict.get`
  comes only from 357:57, on the client's `toc` option. Correct (J11).

## Rulings on the writer's judgement calls

| Call | Ruling the nearest rule supports | Rule | Edges changed |
|---|---|---|---|
| J1 decorated methods | Keep: the call runs `inner`; reject the method name | micro-benchmark "Edges" (case `decorators/functools_wraps`) | 0 |
| J2 doctests of `--self-test` | Keep the 4 callbacks of `_test` | README "`if __name__ == "__main__":` block is code of its module"; micro-benchmark "Callbacks" and "Scopes without a node" (`exec` strings) | 0 |
| J3 pygments < 2.12 branch | Keep `wrap -> pygments.formatters.HtmlFormatter._wrap_div`. The README does not decide dependency versions (R2) | README "Judgements": a version branch runs if a supported version takes it | 0 |
| J4 wavedrom names | Keep the access-path names. The README does not decide (R2) | micro-benchmark "Missing modules" | 0 (1 edge named) |
| J5 optional imports | Keep: both sides run | README "Judgements" default | 0 |
| J6 dead branches | Keep the DEBUG prints, 4509:37, 1476:45 and 3895:31 without callees. Correct 4563:29 (F1) | Rule A ("can call when A runs"); B intro (private `_dedentlines`); F1: B2 and B4 | 0 |
| J7 `convert` of bytes | Keep `<builtin>.str`. The README does not decide (R2) | B2 (client objects); B4 names methods only | 0 |
| J8 `UnicodeWithAttrs(text)` | Keep: no edge | micro-benchmark "Instantiation of a snippet class"; README NamedTuple precedent | 0 |
| J9 library instantiation | Keep `pygments.formatters.HtmlFormatter.__init__`; no edge for argparse's use of `_NoReflowFormatter` | micro-benchmark "Instantiation of a snippet class"; README "Implicit calls" | 0 |
| J10 `pygments.highlight` callback | Keep `HtmlCodeFormatter.wrap` | micro-benchmark "Callbacks" | 0 |
| J11 `toc` option | Keep: no outside callee; reject the trace edge | B5 (extras typed `dict[str, Any]`; no annotation or document fixes `dict`) | 0 |
| J12 `codecs.open` files | Keep `codecs.StreamReaderWriter.read` and `io.BufferedReader.close` | README "Callees outside the package"; micro-benchmark "Names" (a path that resolves to the function that runs) | 0 |
| J13 `sha256(...).hexdigest()` | Keep `_hashlib.HASH.hexdigest` | micro-benchmark "Calls of instances" (private class path) | 0 |

Applying F1 leaves the graph at 872 edges (281 in the package, 591
outside).

## Round 3: supported PyPy cache wrappers (2026-11-16)

The focused follow-up adds functools._lru_cache_wrapper.wrapper edges
from GFMItalicAndBoldProcessor.delimiter_left_or_right (2904:45) and
GFMItalicAndBoldProcessor.body_crosses_span_borders (2953:47). Supported
PyPy 3.11 / 7.3.20 uses this Python wrapper. Both CPython wrapper and
package callback outcomes remain. The accepted stage grows from 879 to
881 edges, with no removals; all four round-3 additions remain.

## Same-function placement clarification (2026-11-16)

Original M1 moves _header_id_exists's lambda from map1595:75 to
membership1595:69. README ruling 12 allows either attribution within this
function. This is an allowed normalization, not a baseline metadata defect.
The other three original metadata groups remain corrections. The relation
choice and all graph pairs are unchanged.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 complete source-first audit (2026-11-16)

Fresh primary source model frozen before baseline comparison. Reviewed
197 bodies, 4735 sites, all 881 pairs, 10 default candidates, one exclusion
and 23 zero-edge bodies. Result: 881 pairs retained, zero additions, zero
removals; 197 nodes unchanged. The current judgement introduction now
accounts for all four round-3 additions. Normal/-O/-OO union, Python bounds
and realized interpreter support are documented in the current judgement.
No target, dependency, tests or generated code ran. Root owns acceptance
and structural/origin gates; this audit does not claim those checks ran.
