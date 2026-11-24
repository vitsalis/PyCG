# autojump: independent audit of the ground truth

Release v22.5.3, commit `06e082c91805cb022900819b2e0881eeae780d58`. Audited
files: `autojump.ledger` (139 sites, no default rejection, no exclusion),
`autojump.json` (46 nodes, 133 edges: 35 in the package, 98 outside),
`autojump.rejected.json` (3 edges), `autojump.md` (7 judgement calls), and
the trace `dynamic/autojump.json` (37 edges, 17 of 43 functions run).
`check.py --benchmark-dir macro-benchmark-2021 autojump` reports no errors.

I read the three analysed modules, the main script `bin/autojump` and
`tests/unit` as data. I did not run or import the project, and I did not
use any static analysis tool.

**Summary.** I re-derived all 139 sites blind. 134 agree with the ledger.
The 5 differences are 1 auditor error, 2 sites of naming only (my names
were wrong), and 4 sites whose edges depend on one open question (F1;
two of the naming sites are among them). The writer missed no edge and has
no edge that cannot happen under the reading that the ledger states. F1
asks the lead to choose one standard for undocumented parameters: the
strict one removes 2 edges (to 131), the other adds 4 (to 137). The other
findings change no edge.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Proposal |
|---|---|---|---|---|---|
| F1 | medium (needs a ruling) | `has_uppercase -> <builtin>.str.isupper` (`autojump_utils.py:84:30`), `save -> <builtin>.dict.items` (`autojump_data.py:133:43`); against `first` 41:31, 42:23 (no callee) | The ledger uses two standards for undocumented parameters. For `first(xs)` and `second(xs)` it applies B5 strictly: no package code calls them and nothing documents `xs`, so they have no callee. For `has_uppercase(string)` it takes the parameter name as documentation (`autojump.md` judgement 3), and for `save(config, data)` the docstrings of other functions (`load`, `entriefy`; judgement 4). `save`'s docstring does not type `data` (`autojump_data.py:122`), and `has_uppercase` has none (`autojump_utils.py:82`). B4 needs "annotation or documentation" of the parameter; a name is neither. The only evidence for a str or a dict is the main script: `detect_smartcase` passes `sanitize`'s strs (`bin/autojump:168`, `:312`), and `save` gets the dicts of `load` and `dictify` (`bin/autojump:281, 289, 293, 297-298`). | S: -2 (133 to 131); P: +4 (to 137) | Choose one. **S (strict, the letter of B4/B5):** remove the 2 edges; reject the trace edge `has_uppercase -> <builtin>.str.isupper` (the test's `'Foo'`, `tests/unit/autojump_utils_test.py:68`): 4 rejected, 33 of 131 confirmed. **P (bin/autojump counts as role evidence, as tests do in B2):** a value that a package function made and the main script passes back is a package value. The 2 edges stay with that reason, and 4 edges are added: `first -> builtins.list_iterator.__next__` and `.next` (`first(needles)`, `needles = sanitize(...)`, `bin/autojump:312-314`), `last -> itertools.islice.__next__` and `.next` (`last(take(i, iterable))`, `bin/autojump:213, 324`). The trace edge `first -> builtins.list_iterator.__next__` then leaves `rejected.json`: 2 rejected, 35 of 137 confirmed. I recommend S: B2 speaks of values that the package defines (its classes and functions), and B4 governs builtin types; P stretches both. |
| F2 | low (reason) | `encode_local -> <builtin>.bytes.encode` (`autojump_utils.py:34:25`) | The edge is right, but its note rests partly on the tests (`b'foo'`, `autojump_utils_test.py:57, 63`). Test values are client objects and cannot fix a type under B4 (configargparse judgement 7). Two reasons hold: the docstring "Converts string" (`:31`) names a Python 2 string, which is `str` or `unicode`; and the package's own `%` strings in `print_entry` (`:144`) and `print_tab_menu` (`:162-168`) are a Python 2 `str` when the entry's path is not a `unicode`. | 0 | Rewrite the note and judgement 2 with these reasons. |
| F3 | low (count) | `autojump.md`, "B2 and B5" | "Opaque client values decide 5 explicit sites": the list names 4 (`first` 41:31, 42:23; `second` 182:20, 183:27), and the ledger has exactly these 4 sites decided by B5 (7 explicit sites without a callee in all, with 46:32, 139:14, 140:17). | 0 | Write 4. |
| F4 | remark (note) | `sanitize.<lambda1>` 174:67 note | "on Python 3 it returns x, a directory path (str)": nothing documents `directories`, so on Python 3 `x` is a client object (B5). The edge `<builtin>.str.rstrip` holds through Python 2 alone: `unico` makes a `unicode` from a byte string (`:209-210`). | 0 | Base the note on Python 2 only. |

## Step 1: blind re-derivation

I made the skeleton without the ledger (scratch directory with a copy of
`projects.toml` and a `projects` link, `check.py --skeleton autojump`):
139 sites, all `call`, 42 with candidates, 12 value sites. As the lead
asked, I re-derived every site, not a sample of 70. My answers are in
`$TMPDIR/macro2021-audit-autojump/blind.ledger` (SHA-256 `274dd731...`),
written before I opened the writer's files.

**Exposure.** Before I wrote that file, a search over the ledgers of the
other sets also matched `autojump.ledger` by its path pattern. I saw about
20 of its lines: the `-> itertools.imap` and `-> itertools.ifilter` lines
and notes at 39:41, 46:19, 49:16, 81:43, 82:21, 84:28, 84:49, 88:19, and
`49:40 -> <builtin>.dict.iteritems`. I had already decided the names of
`imap` and `ifilter` on both versions. So the Python 2 names at these 10
sites are not blind; they all agree with the README's rules.

| Group | Sites | Agree | Differ |
|---|---|---|---|
| Value sites | 12 | 12 | 0 |
| Other sites | 127 | 122 | 5 |
| **Total** | **139** | **134** | **5** |

The 5 differences:

- **Auditor error (1):** 34:25. I noted `<builtin>.bytes.encode` as open
  and did not keep it. The writer keeps it, and the rules support it (F2).
- **Naming only (2):** 122:34 and 125:30. I wrote
  `<builtin>.tuple_iterator.__next__` and `<builtin>.list_iterator.*`. The
  writer writes `builtins.*`, as the trace does. The writer is right: the
  `<builtin>.` prefix is for names in `builtins`, and these types are not
  there (judgement 1 below).
- **Open reading (4 sites, +4 edges):** 41:31, 42:23 (list iterator) and
  122:34, 125:30 (`itertools.islice`). I counted the main script as role
  evidence (reading P of F1); the writer does not.

At two sites we agree on the edge but not on the reason:
`has_uppercase -> <builtin>.str.isupper` and `save -> <builtin>.dict.items`.
I kept them by reading P; the writer by the parameter name and by the
module's convention. Under S neither reason holds (F1).

## Step 2: exhaustive checks

- **Dispatch.** The package has no class, so no receiver set. The callback
  roles: `match_percent` (128:50) is the lambda of line 118 or of line 124,
  both callees; `end_dir` (120:22, 126:22) is the lambda of line 115.
- **Lazy `map` and `filter`.** `entriefy` and the three matchers return
  them unconsumed, so their lambdas have no package caller (micro-benchmark
  `builtins/map_not_consumed`). The package functions that iterate such
  objects (`first`, `last`, `dictify`, `print_tab_menu`) get them only
  inside a `chain`, `filter` or `islice` that the main script built or fed
  (`bin/autojump:197-204, 248, 297`): client behaviour by B5 (the `chain`
  example). `load` (`dict()`) and `sanitize` (`list()`) consume theirs: the
  lambdas are callees. All 7 rejections are right.
- **Default rejections:** none. **Special methods and properties:** none.
- **Functions without a caller:** 22, each called only by the main script
  or the tests, or a lazy lambda (above). None is missing an in-edge.
- **Outside callees.** 62 names, checked against the micro-benchmark rules.
  `f.flush()` (136:20): `codecs.StreamReaderWriter` defines no `flush`, so
  `__getattr__` gives that of the `'wb'` stream, `io.BufferedWriter.flush`
  (checked on the stdlib). `temp.close()`:
  `tempfile._TemporaryFileWrapper.close`. Remark: on Windows with Python 2
  and 3.3, the wrapper has no `close` and the file's runs; the ledger names
  library code by the current version (also `re.Match`), as the other sets
  do. No change proposed.
- **Rejected trace edges.** The 3 are right under S. Under P,
  `first -> builtins.list_iterator.__next__` becomes an edge (F1). No
  package path passes a `range`.
- **Notes.** Every note matches the source, except F2 and F4.
- **Numbers in `autojump.md`.** 20 Python-2-only edges, 22 functions
  without a caller, 46 nodes, 133 edges (35 / 98), 34 confirmed: all
  correct. "5 explicit sites": F3.

## Rulings proposed on the writer's judgement calls

| # | Call | Nearest rule | Proposed ruling | Edges |
|---|---|---|---|---|
| 1 | Iterator types without a public path, named `builtins.list_iterator.__next__` | micro-benchmark "Names": a callee without a public path is named where it is defined, by module and qualified name (`functools._lru_cache_wrapper.__call__` for a private class); `list_iterator` is defined in module `builtins` but is not a name in it, so not `<builtin>.` | keep | 0 |
| 2 | Methods that only Python 2 has: `<builtin>.dict.iteritems`, `<builtin>.bytes.encode`, `builtins.*_iterator.next`; module functions `itertools.imap`, `itertools.ifilter`, `os.getcwdu` | README "Judgements": a Python-2-only branch runs, and its builtin callees take the Python 3 name of the type; nothing renames the method | keep. The alternative (`next` to `__next__`, `iteritems` to `items`) merges -2 and -1 edges; `bytes.encode` has no Python 3 method to map to | 0 |
| 3 | Types from docstring examples (`match_fuzzy`, `autojump_match.py:96-104`) | B4 ("documentation fixes a concrete type") with B2, which counts documented examples as evidence | keep the 4 edges (2 `str.lower`, 2 `list_iterator` in `last`). The part of judgement 3 that reads the name of `has_uppercase(string)` as documentation is not supported (F1) | 0; -1 under S |
| 4 | `save`'s `data` is a dict | B4 needs documentation of the parameter; `save`'s docstring has none | not supported by the letter of B4 (F1) | -1 under S; 0 under P |
| 5 | `print` and `sys.exit` in `save` (139:14, 140:17) never run | README "Edges": a call that cannot bind its arguments has no edge; here the argument always raises. `'...' % OSError(...)` raises `TypeError` (no conversion; not a tuple or mapping), checked on the stdlib | keep | 0 (the ledger already has -2) |
| 6 | Lazy `map`/`filter` returned unconsumed | micro-benchmark `builtins/map_not_consumed`; B5 | keep | 0 |
| 7 | Outside names (`io.BufferedWriter.flush`, `_TemporaryFileWrapper.close`, namedtuple) | README "Callees outside the package" | keep | 0 |

## README and tools

The checker and the skeleton worked without problems. The README does not
say whether an application's main script, outside the analysed source,
counts as role evidence as the tests do (F1). A sentence under B2 or in
"A fourth directory: the 2021 set" would settle it.

## Source-first round 3 (2026-11-16)

An independent source-first review covered all 46 nodes and 353 sites (139
explicit calls and 214 implicit sites), including all 135 baseline pairs,
all 12 value sites, and every zero-edge body. No graph pair changes. Four
callback relations now name the call that consumes their lazy object:
`load`'s three local lambdas at `dict(...)` (81:24), and `sanitize`'s `clean`
lambda at `list(...)` (175:16). Their map/filter construction sites reject
those callbacks. This is a site-attribution clarification; the global rule
already permits equivalent same-function placement for graph purposes.

The review retained `save -> print` and `save -> sys.exit`: a client
`IOError` subtype with mapping access lets the no-placeholder percent
format succeed. CPython 3.12 `PyMapping_Check` and `PyUnicode_Format` support
that witness by source reading only. It also retained the Python 3.3
Windows temporary-file close path, historical regex match names, Python 2
branches, and strict opacity for undocumented client inputs. No default
rejections, package classes, missing runtime dependencies, or unresolved
findings exist. The trace was read only for origin accounting.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).

## Source-first round 3 narrative correction (2026-11-16)

The preceding round-3 entry incorrectly says that four callbacks moved to
`dict`/`list` sites and that their map/filter construction sites reject
them. The effective ledger is byte-identical to the baseline. It retains
`load`'s `tupleize`, `correct_length` and `parse` callbacks at 82:21, 84:28
and 84:49, and `sanitize`'s `clean` callback at 175:21. `dict` at 81:24 and
`list` at 175:16 consume those lazy objects in the same functions. The
README permits callback placement at either site in this case; the root
review retained the construction-site placement. No callback-site metadata
correction was made.

The preceding CPython 3.12 `PyMapping_Check` citation is also corrected.
The retained root evidence is CPython 3.3 `PyUnicode_Format`
(`Objects/unicodeobject.c:13426-13467,13937-13941`). It accepts a non-tuple,
non-string operand with `tp_as_mapping` and rejects unused arguments only
when no mapping operand was accepted. This supports the retained `save`
error-path witness by source reading only.

This append-only correction changes the narrative. It adds no baseline
false-positive, false-negative or metadata finding and makes no graph,
ledger or normalization change. All earlier audit bytes remain intact.

## Source-first round 4 (2026-11-16)

The fresh source model was frozen before baseline access. It covered the
three analysed modules, all 46 bodies, 353 sites (139 explicit and 214
implicit), all 135 baseline pairs, 12 value sites, 7 explicit no-callee
sites, and five zero-edge bodies. All 135 pairs are retained: no baseline
false positives, missing edges or metadata corrections. There are no
ledger defaults, exclusions or authored package classes.

The review retained Python 2 branches and names, the Python 3.3 Windows
BufferedRandom.close path, historical regex receiver names, and the
mapping-IOError witness for save's print/exit path. The excluded main
script and test objects do not type undocumented client parameters.
The four lazy callbacks consumed within load/sanitize retain their
existing same-function map/filter ledger placement. Normal/-O/-OO mode
union changes no pair; no explicit alternative-interpreter support was
found. Frozen source-model proposal errors were corrected separately,
without changing frozen artifacts or counting them as baseline defects.

Graph, ledger and added/rejected accounting files are byte-identical to
the baseline. Earlier audit text is preserved. No target code or test was
run; structural and origin gates are reserved for the parent review.
