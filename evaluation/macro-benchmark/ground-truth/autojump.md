# autojump: judgements of the ground truth

Release v22.5.3 (commit `06e082c`, tag `release-v22.5.3`). Analysed source:
`bin/autojump_data.py`, `bin/autojump_match.py` and `bin/autojump_utils.py`
under the root `bin`: 3 modules, 43 functions (11 lambdas), no class. The
project declares Python 2.6+ and 3.3+ (README; tox: py26, py27, py33 to
py35), so the branches that only Python 2 takes run.

The ledger is `autojump.ledger`; the graph `autojump.json` is generated from
it. `autojump.rejected.json` holds the 4 rejected trace edges. The
independent audit is in `autojump.audit.md`; "Rulings" below records how
the lead decided its findings and the judgement calls.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in autojump-review.json (audit record `2026-11-15/autojump-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 131 | 0 | 4 | 135 |

- An `IOError` subtype raised by opaque client `data.items()` may implement
  mapping access. The constant percent-format string then succeeds, so
  `save` can enter `print` and `sys.exit`.
- Add `io.BufferedRandom.close` for the admitted Python 3.3 Windows
  temporary-file implementation and `_sre.SRE_Match.group` for historical
  Python 3 regex receivers.

## Architecture, as the ledger uses it

- `autojump_data` reads and writes the data file. `load` returns a dict
  (path to weight). `save` writes the data back. `entriefy` turns a dict
  into `Entry` tuples; `Entry` is a `collections.namedtuple` class
  (`autojump_data.py:29`). Both files are opened with `codecs.open`
  (imported as `open`, line 8).
- `autojump_match` has three matchers. Each returns a lazy `filter` object
  (`itertools.ifilter` on Python 2) over the client's haystack.
- `autojump_utils` has small helpers: iteration (`first`, `second`, `last`,
  `take`), strings, the environment and the platform.
- `autojump_data` and `autojump_match` bind `imap` and `ifilter` in a
  version branch; `autojump_utils` binds only `imap`. These names refer to
  the builtins `map` and `filter` on Python 3, and `itertools.imap` and
  `itertools.ifilter` on Python 2. `autojump_utils.py:16` (and
  `autojump_match.py:14`) also
  bind `os.getcwdu = os.getcwd` on Python 3.
- The main script `bin/autojump` is outside the analysed source (ruling of
  the lead). It is a client, as the tests are: it calls almost every
  function, and what it passes is a client value. It does not fix the type
  of an undocumented parameter (ruling on audit F1).

## Scope rules

**A.** Every function keeps the out-edges of its body. 22 functions have no
package caller (the public functions that only `bin/autojump` or the tests
call, and the 4 lambdas of judgement 6). The 4 rejected trace edges are
calls on client values (B5, see "Trace").

**B1.** No class, so no receiver of a package class.

**B2 and B5.** Module-level functions are public (rule C), and their
arguments are client objects, unless the package itself passes them or a
docstring fixes their type. The 11 lexical lambdas retain their actual
captured values and callback argument flow; they are not public functions. A parameter's name is not documentation. Opaque client values
decide 6 explicit sites, which have no callee:
- the 4 sites in `first` and `second`: `it.__next__()` and `it.next()` in
  `first` (`autojump_utils.py:41`, `42`) and both `it.next()` in `second`
  (`182`, `183`). No package code calls `first` or `second`, and nothing
  documents `xs`;
- by the ruling on audit F1, `ch.isupper()` in `has_uppercase`
  (`autojump_utils.py:84`) and `data.items()` in `save`
  (`autojump_data.py:133`). Neither parameter is documented, and no package
  code calls either function (judgements 3 and 4).

**B4.** Docstrings fix these concrete types:
- `entriefy(data)`: "Converts a dictionary": `<builtin>.dict.items` and, on
  Python 2, `<builtin>.dict.iteritems` (`autojump_data.py:48`, `49`).
- `encode_local(string)`: "Converts string" (judgement 2).
- the docstring example of `match_fuzzy` (judgement 3).

## Judgement calls

1. **Names of the builtin iterator types.** `last` calls `it.__next__()` on
   `iter(xs)` (`autojump_utils.py:122`). The package passes a tuple and a
   list (judgement 3), so the callees are the `__next__` of the tuple and
   list iterators. Their types have no public path. I named them as the
   trace names them: `builtins.tuple_iterator.__next__` and
   `builtins.list_iterator.__next__`. Ruling: kept.
2. **Python 2 names.** Builtin callees of Python-2-only code have the Python
   3 name of the type, and a method that only Python 2 has keeps its name.
   20 edges are made only on Python 2:
   - `unicode(...)` is `<builtin>.str` (`autojump_utils.py:85`, `210`).
   - `string.encode(...)` in `encode_local` (`autojump_utils.py:34`):
     `<builtin>.str.encode` (a unicode) and `<builtin>.bytes.encode` (a
     Python 2 str). The docstring "Converts string" (line 31) names a
     Python 2 string, which is either type. The package's own `%` strings
     that reach `encode_local` through `print_local` (`print_entry`, line
     144; `print_tab_menu`, lines 162-168) are a Python 2 str when the
     entry's path is not a unicode.
   - `data.iteritems()` is `<builtin>.dict.iteritems`
     (`autojump_data.py:49`).
   - `it.next()` in `last` (`autojump_utils.py:125`):
     `builtins.list_iterator.next` and `builtins.tuple_iterator.next` (the
     Python 2 types `listiterator` and `tupleiterator`).
   - Python 2 module functions keep their path: `itertools.imap`,
     `itertools.ifilter`, `os.getcwdu`.
   - `os.getcwdu()` in `get_pwd` (`autojump_utils.py:76`) has two callees:
     `os.getcwd` (Python 3, through line 16) and `os.getcwdu` (Python 2).
   - Code that runs on both versions gets only the Python 3 name:
     `'"{0}"'.format` is `<builtin>.str.format` (`autojump_utils.py:198`),
     and match objects use the union of admitted Python 3 names:
     `re.Match` and historical `_sre.SRE_Match`.

   Ruling: kept.
3. **Types from the docstring example of `match_fuzzy`.** It gives
   `needles = ['foo', 'bar']` and entries `(path='/foo/bar/baz',
   weight=11)` (`autojump_match.py:96-104`). This documentation fixes
   needles as a list of str and the path of an entry as a str (B4).
   Effect: 4 edges.
   - `match_fuzzy -> <builtin>.str.lower` (`autojump_match.py:117`) and
     `match_fuzzy.<lambda2> -> <builtin>.str.lower` (`120`).
   - `last -> builtins.list_iterator.__next__` (`autojump_utils.py:122`,
     also in the trace) and `last -> builtins.list_iterator.next` (`125`).

   Ruling: the 4 edges are kept. My first draft also read the signature
   `has_uppercase(string)` as documentation of a str. Ruling (audit F1): a
   parameter's name is not documentation. So `ch.isupper()`
   (`autojump_utils.py:84`) has no callee, and the trace edge
   `has_uppercase -> <builtin>.str.isupper` is rejected (B5). Effect: -1
   edge.
4. **`save(config, data)`: `data.items()` has no callee**
   (`autojump_data.py:133`). My first draft took `data` to be the dict that
   `load` returns and that `entriefy` documents as its `data`. Ruling (audit
   F1): `save`'s docstring does not type `data`, and the dicts that
   `bin/autojump` passes are client values. So the site has no callee.
   Effect: -1 edge.
5. **`print` and `sys.exit` can run in `save`** (`autojump_data.py:139`,
   `140`). The untyped client `data.items()` can raise an `IOError` subtype
   with mapping access. CPython accepts that exception as the mapping
   operand of the constant percent-format string, so formatting succeeds.
   The package then calls `print` and `sys.exit`. The client callback and
   exception stay opaque under B5; their control-flow effects count.

6. **Lazy `map` and `filter` objects that a function returns.** `entriefy`
   and the three matchers return the map or filter object unconsumed. Its
   function argument runs when the caller iterates it, in the caller's code.
   By the callback rule, the edge belongs to that caller, not to the
   function that made the object. So 4 lambdas have no package caller:
   `entriefy.<lambda1>`, `match_anywhere.<lambda1>`,
   `match_consecutive.<lambda1>` and `match_fuzzy.<lambda4>`. The trace
   agrees: it runs the two matcher lambdas and has no edge from their
   matchers. Where the same function consumes the object (`dict()` in
   `load`, `list()` in `sanitize`), the lambdas are callees, put at the
   `imap` and `ifilter` sites (as in sqlparse and markdown2). Ruling: kept.
7. **Outside names, by earlier rulings.** `codecs.open` returns a
   `codecs.StreamReaderWriter`: `f.write` is
   `codecs.StreamReaderWriter.write`. It defines no `flush`, so `f.flush()`
   runs the `flush` of its stream, which `codecs.open` opens in mode
   `'wb'`: `io.BufferedWriter.flush` (`autojump_data.py:136`, as markdown2's
   `io.BufferedReader.close`). `temp.close()` is
   `tempfile._TemporaryFileWrapper.close` (`autojump_data.py:130`), and
   `io.BufferedRandom.close` on the admitted Python 3.3 Windows branch.
   `Entry(*tup)` adds no edge (a namedtuple class, `autojump_data.py:46`).
   Ruling: kept.

## Rulings (earlier audit)

The blind audit re-derived all 139 sites: 134 agree, and it found no
missed edge and no edge that cannot happen. The lead ruled:

| Finding | Ruling | Effect |
|---|---|---|
| F1: two standards for undocumented parameters | Strict (option S): the main script is a client, and a parameter's name is not documentation. `has_uppercase -> <builtin>.str.isupper` and `save -> <builtin>.dict.items` go; the trace edge `has_uppercase -> <builtin>.str.isupper` is rejected. `first` and `second` stay without callees | -2 edges (133 to 131), +1 rejected trace edge |
| F2: the reason for `<builtin>.bytes.encode` rests on test values | The note at `autojump_utils.py:34:25` and judgement 2 now rest on the docstring and the package's `%` strings | 0 |
| F3: the count of explicit sites decided by B5 | Corrected: 4 in `first` and `second`; with the 2 sites of F1, 6 | 0 |
| F4: the Python 3 clause of the note at `autojump_utils.py:174:67` | Dropped: the edge `<builtin>.str.rstrip` holds through Python 2 alone, where `unico` makes a unicode | 0 |
| Judgements 1, 2, 5, 6, 7 | Kept as written | 0 |
| Judgement 3 | The 4 edges from the docstring example of `match_fuzzy` are kept; the `has_uppercase` part goes (F1) | -1 (in F1) |
| Judgement 4 | Goes (F1) | -1 (in F1) |

## Trace

The trace (23 tests passed, 5 skipped, 4 xfailed) has 37 edges and runs 17
of 43 functions. No test calls a function of `autojump_data` or
`match_fuzzy`. 33 trace edges are in the graph. The other 4 are rejected
(B5): `first -> builtins.list_iterator.__next__` and
`-> builtins.range_iterator.__next__`, `last ->
builtins.range_iterator.__next__` (the tests pass a list and a range; no
package code passes a range to `last`), and `has_uppercase ->
<builtin>.str.isupper` (the test passes a str to an undocumented
parameter).

The graph has 46 nodes and 135 edges (35 inside, 100 outside). The trace
confirms 33 (24.4%); 102 come from reading only. No default rejection and no
exclusion. 12 value sites.

## Source-first round 3 (2026-11-16)

An independent source-first review covered all 46 nodes and 353 sites (139
explicit calls and 214 implicit sites), including all 135 baseline pairs,
all 12 value sites, and every zero-edge body. No graph pair changes. The
ledger is byte-identical to the baseline. Four callback relations retain
their map/filter construction sites: `load`'s `tupleize`, `correct_length`
and `parse` at 82:21, 84:28 and 84:49, and `sanitize`'s `clean` at 175:21.
The callbacks execute when `dict(...)` in `load` (81:24) and `list(...)` in
`sanitize` (175:16) consume the lazy objects. The global rule permits this
same-function placement; no callback-site metadata correction was made.

The review retained `save -> print` and `save -> sys.exit`: a client
`IOError` subtype with mapping access lets the no-placeholder percent
format succeed. The retained CPython 3.3 `PyUnicode_Format` source accepts
non-tuple, non-string operands with `tp_as_mapping`; its unused-argument
error requires that no mapping operand was accepted. This supports the
witness by source reading only. The review also retained the Python 3.3
Windows temporary-file close path, historical regex match names, Python 2
branches, and strict opacity for undocumented client inputs. No default
rejections, package classes, missing runtime dependencies, or unresolved
findings exist. The trace was read only for origin accounting.

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
