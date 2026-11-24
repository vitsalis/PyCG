# markdown2: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 0 edges and adds 5. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 4 corrections to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/markdown2-review.json`).
The current ledger and statistics below include both audit passes.

The third complete source-first audit and its PyPy follow-up retain all
877 baseline pairs and add four pairs: two supported-version SHA-256
fallback receiver methods (J13) and two PyPy cache-wrapper calls. They
also normalize the header lookup lambda placement from map1595:75 to
membership1595:69. README ruling 12 permits both within this function. The graph has 881 edges
and 1427 site-target relations. Historical audit records remain unchanged.

Release 2.5.5 (commit `150454e`). Analysed source: `lib/markdown2.py`, one
module with 196 functions (5 lambdas) and 36 classes; `root = "lib"`, so
the module is `markdown2`. `setup.py:59` sets `python_requires=">=3.9, <4"`.
The optional dependencies are `pygments>=2.7.3`, `wavedrom` and
`latex2mathml` (`setup.py:32-36`).

The ledger is `markdown2.ledger`; the graph `markdown2.json` is generated
from it. One trace edge is rejected (`markdown2.rejected.json`, judgement
J11). The blind audit is in `markdown2.audit.md`: 122 of 124 sites agree;
its finding F1 is applied (J6). The lead kept J1 to J13 and ruled on J3, J4
and J7 (see each).

**How the ledger was drafted.** The writer read the whole module. A
scratch script of the writer then filled the plain entries from the site
text with the receiver rules below (for example: a name that ends in `_re`
or `_pat` is a compiled pattern, `.group()` is `re.Match.group`, `text` is a
`str`). It knows nothing about call targets. Every drafted entry was then
reviewed against the source; the review corrected `list.index` (2172:83),
`tuple.index` (3495:87) and the callbacks of 551:31, 998:42, 1919:34,
2172:35 and 3771:45. In all, 212 entries were written by hand.

## Architecture, as the ledger uses it

- `Markdown.convert` runs a fixed pipeline of methods. Sixteen of them are
  decorated with `@mark_stage(Stage.X)` (`markdown2.py:579-2108`). The
  decorator returns the closure `mark_stage.wrapper.inner`, so the class
  attribute is `inner` and a call `self._run_block_gamut(text)` runs
  `inner`. `inner` runs the extras of the stage, then the original method
  through `func(md, text, ...)` (255:24), then the extras that run after
  the stage. These call sites have the callee `mark_stage.wrapper.inner`
  and reject the candidate of the method name.
- The extras are subclasses of `Extra` (an `abc.ABC`). The module registers
  20 of them (`markdown2.py:4325-4344`). `register()` puts each class into
  the "before" list (`Extra._exec_order[stage][0]`) or the "after" list
  (`[1]`) of its stages, or next to an extra that it names. `_setup_extras`
  instantiates the registered classes that the client enables
  (`markdown2.py:419-422`); `inner` calls their `test` and `run`.
- `LinkProcessor` and `GFMItalicAndBoldProcessor` are not registered at
  import, but clients can register both through inherited public
  `Extra.register`.
  `Markdown._do_links` and `Markdown._do_italics_and_bold` instantiate them
  directly (1556, 2055). `ItalicAndBoldProcessor` is abstract by `abc` (its
  `sub` is an `abstractmethod`) and the package defines no subclass of it.
- Text passes through `re.sub` and the `sub` methods of compiled patterns,
  with package callbacks (`self._h_sub`, `self.sub`, local functions,
  lambdas). Each of these 35 sites has the callback as a callee.
- `_hash_html_blocks` wraps `_hash_html_block_sub` with `_curry`
  (`markdown2.py:978`); the closure `_curry.result` is the callback of
  three `sub` sites and of `_strict_tag_block_sub`.
- `_xml_oneliner_re_from_tab_width` and `_hr_tag_re_from_tab_width` are
  rebound to `_memoized` objects (`markdown2.py:4589, 4609`). A call of
  the name runs `_memoized.__call__`, which calls the function.

## Scope rules

**A. Edges are per function.** Each function keeps the calls its body can
make under the global scope rules, independently of package reachability.
Impossible branches and calls whose arguments cannot bind before entry
remain excluded. TYPE_CHECKING-only code does not run; an annotation
without a value does not establish a runtime value binding. Evaluated
annotation calls retain their edges under the global rules.
`ItalicAndBoldProcessor` (5 functions), `Extra.deregister` and
`markdown_path` have no package caller and keep their edges. `main` and
`_regex_from_encoded_pattern` never ran in the tests and keep theirs.

**B1. Receivers.**
- `extra.test(text)` and `extra.run(text)` in `inner` (251:34, 252:41,
  263:34, 264:41): `extra` is an instance of a registered class. The
  "before" lists hold Admonitions, CodeFriendly, FencedCodeBlocks, Latex,
  LinkPatterns, MarkdownFileLinks, MiddleWordEm, Mermaid, Numbering,
  Strike, Underline, Wavedrom. The "after" lists hold Alerts, Breaks,
  CodeFriendly, FencedCodeBlocks, Latex, Mermaid, Wavedrom, MarkdownInHTML,
  MarkdownFileLinks, MiddleWordEm, PyShell, SmartyPants, Tables,
  TelegramSpoiler, WikiTables. Latex, Mermaid and Wavedrom are inserted
  next to FencedCodeBlocks wherever it is, also in the "after" list of
  PREPROCESS; WikiTables is inserted before Tables, in the "after" list of
  LISTS. Each site has the `test` or `run` that these classes have (own,
  `FencedCodeBlocks.*` for Mermaid, `Extra.test` for the others).
  Public registration adds `GFMItalicAndBoldProcessor.test/run` before
  ITALIC_AND_BOLD, and `LinkProcessor.test/run` at both of its configured
  positions. `ItalicAndBoldProcessor` and `Extra.run` remain abstract.
- `self.process_span(...)` in `GFMItalicAndBoldProcessor.run` (2684:66):
  `self` is a `GFMItalicAndBoldProcessor` or a `CodeFriendly`, whose `run`
  calls this `run` through `super()` (3457). `MiddleWordEm` overrides
  `run`. Callees: both `process_span` methods.
- `self.parse_inline_anchor_or_image(...)` in `LinkProcessor.run`
  (3239:59): `self` is a `LinkProcessor` or a `MarkdownFileLinks` (through
  `super().run`, 3813). Callees: both methods.
- `self.tags(...)` in `FencedCodeBlocks.sub` (3618:25): `self` is a
  `FencedCodeBlocks` or a `Mermaid`. Callees: both `tags` methods.
- `self.strong_re.sub(self.sub, text)` and `self.em_re.sub(self.sub, text)`
  in `ItalicAndBoldProcessor.run` (2550:38, 2551:34): `self` is an instance
  of a client subclass, whose `sub` overrides the abstract one. No package
  `sub` is a callee.
- `self._iab_processor` (2056, 2057) and `link_processor` (1557, 1558) are
  the objects that the method makes just before.
- `PyShell.sub` (3986:67): `self.md.extra_classes['fenced-code-blocks']` is
  a `FencedCodeBlocks` (Mermaid is registered as `mermaid`).

**B2. Arguments and stored values.**
- `callback(...)` in `_strict_tag_block_sub` (1120:37), a private method:
  the package passes `_curry.result` (991), the lambda of 1001 and
  `MarkdownInHTML.run.callback` (3771).
- `function(...)` in `_curry.result` (4417:24): `_curry` is private; its
  only call passes `self._hash_html_block_sub`.
- `self.func(*args)` in `_memoized.__call__` (4558:49): the two functions
  of 4589 and 4609.
- `klass(...)` in `_setup_extras` (422:45): the registered classes; their
  first `__init__` is `CodeFriendly.__init__`, `MarkdownFileLinks.__init__`,
  `MiddleWordEm.__init__`, `LinkProcessor.__init__` or `Extra.__init__`.
- `MiddleWordEm.__init__` (3851:27): `options` is annotated
  `Union[dict, bool, None]`; the bool becomes a dict and `None` becomes
  `{}`, so `options.setdefault` is `<builtin>.dict.setdefault`.
- `repl(match)` in `LinkPatterns.run` (3703:32): `repl` is typed
  `Union[str, Callable[[re.Match[str]], str]]`, a bare callable; `main()`
  passes strs only. A callable is a client callback: no edge.

**B4. Concrete outside types.**
- `Markdown.extras` is annotated `dict[str, Any]`: `self.extras.get`,
  `.update`, `.copy`, `.setdefault` are `<builtin>.dict` methods.
- The value of the `header-ids` extra is a dict: `Markdown.__init__`
  replaces any other value with a dict after an `isinstance` test
  (`markdown2.py:360-365`). So `self.extras['header-ids'].get(...)` is
  `<builtin>.dict.get` (413, 540, 1592, 1639, 1670, 955).
- The options of `Breaks`, `LinkProcessor`, `MarkdownFileLinks` and
  `Wavedrom` are annotated with a `TypedDict` (`markdown2.py:3423, 2998,
  3790, 4229`): `self.options.get` is `<builtin>.dict.get`.
- The link patterns are typed `re.Pattern[str]` (`markdown2.py:136`):
  `regex.finditer` is `re.Pattern.finditer` (3698:40).
- `formatter_opts` in `_color_with_pygments` is the `**` dict that the
  interpreter builds: `<builtin>.dict.setdefault` (1917:34).

**B5. Client objects are opaque.** The option value of the `toc` extra is
typed `Any` and only the client supplies a mapping there (judgement J11).

**C. Public.** The module's public names: `markdown`, `markdown_path`,
`Markdown`, `MarkdownWithExtras`, `MarkdownError`, `Stage`, `mark_stage`,
`Extra` and all extra classes, `UnicodeWithAttrs`, `calculate_toc_html`,
`main`. Private: `_curry`, `_memoized`, `_dedent`, `_dedentlines`,
`_slugify`, `_xml_*`, `_html_escape_url`, `_regex_from_encoded_pattern`,
`_NoReflowFormatter`, `_test`, and ordinary underscore methods. Dunder
names retain their protocol roles. Private definitions remain in scope for
actual package calls, captures and the global private-helper fallback; an
underscore does not remove a function or its valid body edges.

## Judgement calls

- **J1. Decorated methods** (31 call sites). A call of a method that
  `@mark_stage` decorates has the callee `mark_stage.wrapper.inner`. The
  candidate of the method name is rejected: the name is bound to `inner`.
  The trace names these calls the same way.
- **J2. Doctests of `--self-test`** (`_test`, 4674:20). `doctest.testmod()`
  runs the docstring examples of the module `__main__`. When markdown2 runs
  as a script with `--self-test` (the `__main__` block, 4814), that module
  is markdown2 itself. Its examples (22-29, 847-857) call
  `markdown2.markdown`, `Markdown()`, `convert` and `_detab`; doctest runs
  them with `exec`. The ledger gives these four callbacks to `_test`.
  When another program is `__main__`, the examples are client code. The
  lead kept this judgement.
- **J3. pygments before 2.12** (1915). `HtmlCodeFormatter.wrap` has a branch
  for `wrap(source, outfile)`, which pygments calls before 2.12. `setup.py`
  admits `pygments>=2.7.3`, so the branch runs on a supported version:
  edge to `pygments.formatters.HtmlFormatter._wrap_div`. Lead's ruling:
  the version-branch default covers a dependency's version too; a branch
  runs if a version that the package admits takes it.
- **J4. wavedrom names** (4247). wavedrom is not installed in the test
  environment. Ordinary missing-module calls retain access-path names even
  when the library source can be read. The ledger names
  `wavedrom.render` and the method of its result `wavedrom.render.tostring`
  by access path, as the micro-benchmark does for a missing module. If
  wavedrom returns an `svgwrite.Drawing` (its README saves the result with
  `saveas`), the real name is `svgwrite.Drawing.tostring`. Lead's ruling:
  the names of a missing module, as written.
- **J5. Optional imports**: pygments (1866-1873), latex2mathml (3662-3666),
  wavedrom (4245-4250). Both sides run. No version branch on Python exists,
  and no `if TYPE_CHECKING:`. Annotations are evaluated at definition on
  3.9-3.13; they only subscript `typing` objects and builtins.
- **J6. Branches that cannot run.**
  - `_xml_escape_attr` is private. Its only calls (3124, 3274) omit
    `skip_single_quote`, whose default is True (4612). The guarded
    replacement at 4625:34 cannot run; `str.replace` remains at 4621-4623.
  - `_dedentlines`: `DEBUG` is the local constant `False` (4464), so the
    five `print` sites (4466-4513) have no callee.
  - `_dedentlines` (4509:37): the margin is the smallest indent that the
    first loop measures with the same rules, so the second loop never meets
    another character first; the `ValueError` has no edge.
  - `_find_non_whitespace` (1476:45): the pattern `\s*` always matches, so
    `len(text)` never runs.
  - Corrected by audit F1: the `TypeError` branch of `_memoized.__call__`
    (4563:29) can run. It needs an argument that cannot be hashed;
    `self.tab_width` is annotated `int`, and a client `int` subclass with
    `__hash__ = None` fits the annotation and passes `Markdown.__init__`
    (`tab_width * " "`, `'%d' % tab_width`). By the J7 ruling the
    annotation does not remove the branch. The site has the two callees of
    4558:49, so the graph does not change.
  - `MiddleWordEm.sub` (3895:31): `super().sub` fails with `AttributeError`
    (no class of the MRO after `MiddleWordEm` defines `sub`). The `super()`
    call itself (3895:25) stays: a client can call this public method with
    a match of another pattern.
- **J7. `convert` of bytes** (457:23). `text` is annotated `str`, but the
  method converts a non-str argument with `str(text, 'utf-8')`. The ledger
  keeps `<builtin>.str`: the code handles this input on purpose. Lead's
  ruling: an annotation names methods (B4); it does not remove a branch
  that the code takes on purpose for another client value.
- **J8. `UnicodeWithAttrs(text)`** (561:30). A str subclass without
  `__init__` or `__new__`: the first `__init__` of the MRO is
  `object.__init__`. No edge.
- **J9. Library instantiation of package classes.** `HtmlCodeFormatter(...)`
  (1918:38) runs `pygments.formatters.HtmlFormatter.__init__`. argparse
  instantiates `_NoReflowFormatter` for help output; it never calls
  `format_description` (an optparse method name), so no package code runs.
- **J10. Callback of `pygments.highlight`** (1919:34). The formatter calls
  back `HtmlCodeFormatter.wrap`, which calls `_wrap_code`, `_add_newline`
  and the inherited `_wrap_pre`.
- **J11. The `toc` option** (357:57, 555:86). `self.extras["toc"].get(...)`
  runs on the client's option value. `extras` is typed `dict[str, Any]`;
  the package itself stores only `None`, ints and strs under `toc`. The
  sites have no outside callee (B5). The trace edge
  `Markdown.__init__ -> <builtin>.dict.get` comes only from 357 and is
  rejected (the tests pass dicts, `test/tm-cases/toc_depth.opts` and
  others). In `convert`, `dict.get` stays from 540.
- **J12. Files of `codecs.open`** (183-184, 4776-4777). With an encoding,
  `codecs.open` returns a `codecs.StreamReaderWriter` over a binary file.
  `fp.read()` is `codecs.StreamReaderWriter.read`; `fp.close()` goes
  through `StreamReaderWriter.__getattr__` to `io.BufferedReader.close`.
- **J13. `sha256(...).hexdigest()`** (150:70):
  `_hashlib.HASH.hexdigest`, `_sha256.sha256.hexdigest` and
  `_sha2.SHA256Type.hexdigest`. The public factory selects OpenSSL when
  available and the builtin implementation otherwise. CPython 3.9 and 3.11
  name the fallback class `_sha256.sha256`; CPython 3.12 names it
  `_sha2.SHA256Type`. All are supported runtimes, and none of these concrete
  classes has a public `hashlib` class alias. The factory itself remains
  `hashlib.sha256`. This accounts for platform/version alternatives without
  changing package or library internals.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `_memoized.__repr__` | 163 (83 op, 46 format, 34 call) | the only `_memoized` objects are two module globals that the package only calls | nowhere |
| the `sub` of the 9 classes `Admonitions`, `Alerts`, `FencedCodeBlocks`, `ItalicAndBoldProcessor`, `MiddleWordEm`, `PyShell`, `Tables`, `Wavedrom`, `WikiTables` | 77 each (76 for `ItalicAndBoldProcessor.sub`) | the call is `re.sub` or `re.Pattern.sub` | the `self.sub` callbacks: 3374:39, 3409:33, 3629:45, 3884:46, 4004:37, 4132:28, 4261:57, 4279:33 |

Together the 10 candidates decide 241 sites: 129 implicit (83 op, 46
format) and 112 explicit calls, which keep their entries for the callees
outside the package. `ItalicAndBoldProcessor.sub` has its own rejection at
2550:38 and 2551:34 (B1), and `super().sub` at 3895:31 rejects all nine.

## Exclusions

| Site | Excluded | Why |
|---|---|---|
| 422:45 `klass(...)` | `ItalicAndBoldProcessor.__init__` | abstract; public registration admits `LinkProcessor.__init__` |

## Value sites (13)

| Site | Callees |
|---|---|
| 255:24 `func(md, text, ...)` | the 16 decorated methods |
| 422:45 `klass(...)` | 5 `__init__` methods (B2) |
| 1001:42 `hash_html_block_sub(...)` | `_curry.result` |
| 1007:51, 1073:63 `_hr_tag_re_from_tab_width(...)`, `_xml_oneliner_re_from_tab_width(...)` | `_memoized.__call__` |
| 1120:37 `callback(...)` | `_curry.result`, `_hash_html_blocks.<lambda1>`, `MarkdownInHTML.run.callback` |
| 3703:32 `repl(match)` | none (client callback) |
| 4417:24 `function(...)` | `Markdown._hash_html_block_sub` |
| 4558:49, 4563:29 `self.func(*args)` | the two `_memoized` functions |
| 2906:6, 2955:6, 240:10 decorators | `functools.lru_cache.decorating_function`, `functools.partial.__call__` |

`self.tags` (3618:25) and `super().tags` (3826:28) are ordinary method
dispatch, described in B1. The annotation-only TypedDict key `tags` creates
no value binding.

## Functions that no site calls

`Extra.deregister` (public, no package caller), `Extra.run` (abstract), the
five functions of `ItalicAndBoldProcessor` (abstract, no package subclass),
`_NoReflowFormatter.format_description` (argparse does not call it),
`_memoized.__repr__`, and `markdown_path` (public).

## Statistics

| | Count |
|---|---|
| All source sites | 4735 (1288 calls, 27 decorators, 3420 other implicit sites) |
| Sites needing a decision before defaults | 1445 |
| Sites with candidates / value sites | 538 / 13 |
| Ledger entries | 1317 (1288 call, 27 decorator, 1 getattr, 1 op) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 1427 / 91 (33) / 1 / 77 |
| Default rejections | 10 candidates in 2 lines, deciding 241 sites |
| Nodes | 197 (1 module, 196 functions) |
| Edges | 881: 286 in the package, 595 outside |
| Graph edges with a trace name or alias | 752 of 881 (85.4%) |
| Edges only from reading | 129 |
| Trace edges rejected | 1 |
| Functions that the tests run | 180 of 196 |

The third audit reviewed all 3419 previously unlisted sites: 129 decided
by defaults and 3290 without candidates. The membership witness now has a
ledger entry, leaving 3418 unlisted sites. All 148 test `.opts` files were
read for callback and option roles; no package callback is supplied as the
bare `LinkPatterns` replacement. The source-first inventory records full
runtime coverage and exact supporting-document read limits.

Primary source retained for outside names and callbacks (SHA-256):

| Source | SHA-256 |
|---|---|
| `pygments-2.11.2-html.py` | `d0b186b16733a43cf246565351b8071caabda9a8097d088306aedf46a3d4aa57` |
| `pygments-2.19.2-html.py` | `38f3277a9ebd9d7f0f6964df2d30818e87441befae9b43823833a97be94bb9ff` |
| `pygments-2.19.2-formatter.py` | `f27e06ae9a038970cf05ccd97113a37c5bca14a3bb07797828308e04e32262f9` |
| `pygments-2.19.2-formatters-init.py` | `c8dc8bc014da37fe0e5d2224eb9ad7f47b3b288fdcae3dceed711afb09ca5886` |
| `pygments-2.19.2-formatters-mapping.py` | `927f8696b61740d6d1be8a33c8153a30c76a96c04645f6d0ecbc9f1b35efc703` |
| `pygments-2.19.2-init.py` | `78bc19b173a8e6afc9eb8870a2ac3f6b18b0b07018b2b093f3dfd00f4b6639fa` |
| `cpython-3.9.0-hashlib.py` | `a25e6f24d6ae5b5205844e2717f3d6dbeda005c1afeaf4d450b4f2c363a3d34a` |
| `cpython-3.9.0-sha256module.c` | `4544ff587ffcde319f1917239d90ce94071cbbc2d4b029773266d975f6833295` |
| `cpython-3.11.0-sha256module.c` | `88baf8d2cb10723c9c72abcaab61db97f4184f49fe67dd4ae509e7b1e0d0f453` |
| `cpython-3.12.0-hashlib.py` | `b8d50741dff7f57b336f42d029f5f637bd0d65c37ca201004d7991e82047624a` |
| `cpython-3.12.0-sha2module.c` | `f85ad72e79447a9457642b7d521e327b8c93ca0f7a545dce7cb99da311749f19` |
| `cpython-3.15.2-doctest.py` | `822e293ae054f1bfc3daaa4ccbe45d523314a26845a10d1be5c6c393b04621cb` |
| `latex2mathml-3.78.1-converter.py` | `efd06ba8bbf5c3904b74d2594f79bda9e7fdd889bc84a13ad9e570a8d3da70c1` |

Pygments sources are from the named upstream tags. Its public formatter
export maps to `formatters.html.HtmlFormatter`; `highlight` reaches the
package `wrap` override through the base formatter. The old tag verifies
the admitted pre-2.12 `outfile` branch. CPython sources establish the hash
factory/type paths above and `doctest.testmod` selecting `__main__`, finding
its docstrings, and executing their examples. Thus J2 attributes exactly
the four package calls in the package-owned examples to `_test`. The
latex2mathml 3.78.1 source defines undecorated `converter.convert`. Sources
were read, never imported or executed.


## Round 3: supported PyPy cache wrappers (2026-11-16)

The README explicitly supports PyPy; setup.py requires Python >=3.9,<4.
On PyPy 3.11 / 7.3.20, GFMItalicAndBoldProcessor methods
`delimiter_left_or_right` (2904:45) and `body_crosses_span_borders`
(2953:47) call `functools._lru_cache_wrapper.wrapper`. Their cached helpers
are package functions, so the outside wrapper retains its definition name.
The existing CPython `.__call__` and package callback edges remain.
The focused follow-up adds two edges to the accepted 879-edge stage:
881 edges, zero removals. The two earlier round-3 hashlib additions remain.

## Round 4: complete source-first audit (2026-11-16)

All 881 baseline pairs are retained: no added or removed pair, and no node
change. The audit covers all 197 bodies, 4735 source sites, 1317 ledger
entries, 10 default-rejected candidates, the one explicit exclusion and
23 zero-edge bodies. The 3418 sites without an entry comprise 129 implicit
format/operator sites decided by the memoizer default and 3289 sites
without package candidates. Their receiver and callback flows were checked
against the source, including the lazy map consumed at1595:69.

The opening round-3 count description now includes both SHA-256 additions
and the two later PyPy cache-wrapper additions. Graph, ledger, added-edge
register and rejected-edge file are unchanged. Historical audit bytes are
preserved, with this round appended separately.

Interpreter scope intersects the declared >=3.9,<4 bounds with actual
CPython and explicitly supported PyPy releases. README's Jython statement
does not establish an existing Jython3.9+ runtime. The last classifier is
not an upper bound. Normal, -O and -OO are included under the round-4
global working assumption, not a recorded user approval. The three
assertions at348,746,927 and the memoizer docstring return at4567 add no
new pair: the constructor already normalizes its extras, the emacs group
excludes newlines, and a None regex match still fails before group entry.
Removing docstrings gives no new call in __repr__; normal-mode doctest
callbacks remain in the union. Source-owned DEBUG=False remains false.
