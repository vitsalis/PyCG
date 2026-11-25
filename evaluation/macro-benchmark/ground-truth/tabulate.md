# tabulate: judgements of the ground truth

Release v0.10.0 (commit `3b4cd50`). Analysed source: `tabulate/`, one
module (`tabulate/__init__.py`): 77 functions (4 lambdas), 2 classes.
`pyproject.toml` sets `requires-python = ">=3.10"`; the classifiers name
CPython versions 3.10 to 3.14 and no other implementation, so the supported
runtimes are CPython 3.10 and later. Normal and optimized execution (`-O`,
`-OO`) are both included (judgement 13). The only declared dependency is
the optional extra `widechars = ["wcwidth"]`, unpinned.

The ledger is `tabulate.ledger`; the graph `tabulate.json` and the added
edges `tabulate.added.json` are generated from it. No trace edge is
rejected: `tabulate.rejected.json` is empty since Codex audit round 2
(judgement 3). The writer read no
output of any analysis tool and ran nothing of the package. The blind
audit is in `tabulate.audit.md`; its findings E1, M1, J5 and W1 to W3 are
applied below (363 edges). Codex audit round 2 added the UserDict rows
(365 edges; section at the end).

## Architecture, as the ledger uses it

- `tabulate()` (line 1746) is the public entry point. It normalizes the
  input (`_normalize_tabular_data`), wraps cells (`_wrap_text_to_colwidths`,
  which uses the private `_CustomTextWrap`), deduces column types (`_type`,
  `_column_type`), formats every cell to a str (`_format`), aligns columns
  and headers (`_align_column`, `_align_header`) and builds the text
  (`_format_table`).
- A table format is a `TableFormat` namedtuple (line 107) of `Line` and
  `DataRow` namedtuples (lines 70, 73), or of functions and
  `functools.partial` objects, held in the dict `_table_formats` (lines
  362-737). `_build_line` (line 2623) calls a callable line field and
  `_build_row` (line 2572) a callable row field; these two value sites name
  the callables of `_table_formats` (judgement 11).
- The width functions are values: `_choose_width_fn` and
  `_align_column_choose_width_fn` return `_visible_width`,
  `wcwidth.wcswidth`, `len` or a lambda; `_align_column_choose_padfn`
  returns one of the four pad functions; `_format_table` picks `_pad_row`
  or a lambda, and `_append_basic_row` or a partial of
  `_append_multiline_row`.
- `JupyterHTMLStr` (line 2640) is a `str` subclass with `_repr_html_` and a
  property `str`; the package only instantiates it. `_CustomTextWrap`
  (line 2735) subclasses `textwrap.TextWrapper` and overrides `__init__`,
  `_handle_long_word` and `_wrap_chunks`, and adds `_len` and
  `_update_lines`.
- No package class defines a special method other than `__init__`, so no
  implicit site (iteration, operator, truth test, f-string field, attribute
  load) has a package callee: `check.py --report tabulate
  --without-candidates` lists 863 such sites, none of which iterates a lazy
  `map` or `filter` built in another function.

## Scope rules

**A.** Every function keeps the out-edges of its body. `_main`,
`_pprint_file` and `_is_file`, the command line, run in no test (the test
selection leaves out `test/test_cli.py`); their 15 edges, and
`tabulate -> _main`, come from reading.

**B1 and B2.** Most functions are private, so their parameters are what the
package passes. The main facts:
- The cells that `tabulate()` passes to the private helpers after `_format`
  (line 2418) are str: `_format` returns an f-string, `format()`, `str()` or
  `str.replace` result, or `missingval`, which the documentation fixes as a
  string. The headers are str (`list(map(str, headers))`, line 1638). So
  the methods of the helpers' cells are `<builtin>.str` methods.
- The raw client cells reach `_type`, `_isnumber`, `_isint`, `_isbool`,
  `_isnumber_with_thousands_separator` (through `_type`), `_to_str`,
  `_wrap_text_to_colwidths` and `_rst_escape_first_column.escape_empty`.
  Where the code checks `isinstance(x, (str, bytes))` the callees are the
  str and bytes methods; bytes cells are documented (README.md "Type
  Deduction and Missing Values", line 802: `b"abc"`, `b""`).
- `_isconvertible(conv, string)` (line 897): the package passes `float`
  and `int` (the default `inttype` of `_isint`; no package call passes
  another).

**B3.** No arbitrary package object is taken as a cell, header or format
field. A client `TableFormat` (the name is public, and
`test_regression.py:436` builds one) holds client `Line`s, `DataRow`s and
callables: its callables are client callbacks.

**B4.** Documented outside types (judgement 3): a dict of iterables, a list
of dicts or OrderedDicts, a dict of headers (`isinstance(headers, dict)`,
line 1578), str format specifications. The DataFrame, NumPy and DB-API
cursor paths call no method of the client object (only `hasattr`,
attribute loads, `list()` and iteration).

**B5.** Client objects are opaque, but their effects on control flow count
(judgement 6).

**C.** The public names are `tabulate`, `tabulate_formats`,
`simple_separated_format` (`__all__`), the module flags, the
namedtuple classes, and `JupyterHTMLStr` (line 2640) with its property
`str` (line 2648), which no docstring marks private (Codex audit round 2,
metadata; no edge changes: the property returns `self`, and the package
never loads it). Every function with an underscore is private, and so
is `_CustomTextWrap`.

## Judgement calls

1. **Default rejection `tabulate.JupyterHTMLStr.str` (27 sites).** The site
   finder proposes the property `JupyterHTMLStr.str` wherever the name
   `str` is called or passed (`str(x)`, `isinstance(x, str)`,
   `map(str, ...)`). There the name is the builtin; the property runs only
   on a load of the attribute `.str`, and the package never makes one. All
   27 sites are explicit calls, and each keeps its builtin callee
   (`<builtin>.str`, `<builtin>.isinstance` or `<builtin>.map`).

2. **Namedtuple calls (180 value sites).** Every `Line(...)`,
   `DataRow(...)` and `TableFormat(...)` call is a call of a
   `collections.namedtuple` class: no edge (README, "Callees outside the
   package"). Each site has a note. Where a `TableFormat(...)` call passes
   a package function as a field (`453:30`, `543:24`, `648:24`, `658:30`,
   `668:25`, `678:29`, `688:34`, `698:35`, `718:27`), the candidate is
   rejected: the generated `__new__` only stores it. The `partial(...)`
   calls of `_table_formats` (lines 623-734) and of `_format_table` (line
   2667) give `functools.partial` and reject the wrapped function, which
   the later call of the partial object reaches.

3. **Documented input types** (`_normalize_tabular_data`, lines
   1504-1592). `tabular_data.keys()` and `.values()` (`1508:37`,
   `1511:54`) are `<builtin>.dict` methods: README.md and the docstring of
   `tabulate()` (line 1779) name a "dict of iterables". For the rows of a
   "list or another iterable of dicts" (README.md line 83) the methods
   `keys` and `get` (`1567:43`, `1571:34`, `1584:45`, `1592:29`) are those
   of `dict` and of `collections.OrderedDict`: the docstring of
   `_normalize_tabular_data` lists "list of OrderedDicts" (line 1471).
   This reads the docstring of a private function as documentation of the
   public input, because it lists the inputs of `tabulate()`; the lead may
   rule otherwise (then `collections.OrderedDict.keys` and `.get` leave
   four sites, and the traced `collections.OrderedDict.keys` moves to the
   rejected edges). The lead upheld this reading after the audit. Codex
   audit round 2 found that the CHANGELOG documents "lists of UserDicts"
   too (`CHANGELOG:21`, release 0.8.8), and the source still handles them
   in the same branch (line 1561): so the four sites also name
   `collections.UserDict.keys` and `collections.UserDict.get`. `UserDict`
   inherits `keys` from `collections.abc.Mapping` on every supported
   version, and `get` on 3.10 and 3.11 (it defines its own `get` from
   3.12, CPython `Lib/collections/__init__.py`); each is named once, by
   the class of the receiver (README, "Callees outside the package"). The
   writer had rejected the tests' two UserDict trace edges; they are now
   graph edges, and the trace name `collections.abc.Mapping.keys` matches
   `collections.UserDict.keys` through its alias. The CHANGELOG names
   lists only, so a UserDict is not named as a "dict of iterables"
   (`1508:37`, `1511:54`).

4. **`_type(cell, numparse)(cell)`** (`1705:55`). The callee is the type
   that `_type` returns. The cell here is not None, not `""` and not a
   number by `_isnumber`, so: `str`, `bool` ("True"), `bytes` (a bytes
   cell), `int` ("1,000": `_type` takes thousands separators, `int()`
   raises `ValueError` in its body) and `float` ("1,000.5"). `_type`
   returns `NoneType` for a cell that is only ANSI codes and for `b""`
   (for bytes, `cell == ""` is false; audit W1), and `NoneType(cell)` raises "NoneType takes no arguments": the argument
   check of a type that takes none, before its body runs, so no edge (the
   rule "argument binding failure before entry gives no edge"). Note that
   `_type(cell, numparse)` binds `numparse` to `has_invisible`; this
   changes no callee.

5. **`val.replace(raw_val, formatted_val)`** (`1376:31`). For a str `val`
   the callee is `<builtin>.str.replace`. For a bytes `val` (a bytes cell
   of a float column, with ANSI codes elsewhere in the table,
   `tabulate([[b"1.5"], ["\x1b[31m2\x1b[0m"]])`) `raw_val` is bytes and
   `formatted_val` a str. The writer first counted the buffer conversion
   of the str as a binding failure. The lead ruled the auditor's way (audit
   J5; now in the README's rulings for batch 6): for a callable
   written in C, binding is the match of the arguments to the parameters of
   its signature (number and names, as `inspect.Signature.bind` checks); a
   type that the callable then refuses is a failure in its body. The two
   arguments bind, so `_format -> <builtin>.bytes.replace` is an edge.

6. **A client str subclass whose `replace` returns a non-str** (B5,
   "Client control flow"). Cells are arbitrary client objects, so a str
   subclass is admitted (the tests use one, `test_regression.py:294`). Its
   `replace` override, called at `1376:31`, can return any object, and
   `_format` returns it as the formatted cell. This witness reaches two
   branches that the package's own str values never reach:
   - `_visible_width`'s `else` (`1139:22`, `1139:26`): with
     `numalign=None` the column gets `_padnone`, and `_align_column` maps
     `_visible_width` over the cells (`has_invisible` is true), so an int
     result reaches `len_fn(str(s))`. Added edge: `_visible_width ->
     <builtin>.str`.
   - `_isnumber_with_thousands_separator`'s `string.decode()` (`888:31`):
     a bytes result in a decimal column of a table with ANSI codes reaches
     `_afterpoint` through `_strip_ansi` (line 1180), then the decode. B5
     does not remove the edge: the receiver is not the client's object (an
     opaque callback result) but the exact bytes that `re.Pattern.sub`
     returns in `_strip_ansi` (line 1121), a library result whose type is
     known (audit W2). The edge `-> <builtin>.bytes.decode` is also in the
     trace (from the doctest at line 880, a direct test of the private
     function).
   - `_afterpoint`'s `string.rfind(".")` (`1057:31`, audit M1): the same
     bytes, for example `b"1.5"` (`_isnumber` true, `_isint` false), give
     `_afterpoint -> <builtin>.bytes.rfind`; the call binds its one
     argument and refuses the str in its body.
   The lead upheld this judgement after the audit.

7. **`_CustomTextWrap` instances have `max_lines` None** (B1). The class is
   private and the package makes it only at line 1690, without
   `max_lines`; `__init__` sets `self.max_lines = None` and
   `TextWrapper.__init__` keeps the default None. So in `_wrap_chunks` the
   checks of lines 2855-2861, the operands after `self.max_lines is None`
   (line 2913) and the `else` branch of lines 2926-2947 never run: 18
   sites without edges, each with a note (8 of them reject the candidates
   `_len` and `_update_lines`). `width <= 0` (`2854:29`) stays: the width
   is a client column width, and 0 is an int.

8. **`_asciidoc_row`'s `ValueError`** (`312:25`). The function is private,
   and the package calls it only through the partial objects of the
   asciidoc format, with two arguments (`_build_line`) or three
   (`_build_row`). The `else` branch never runs: no edge (a check that
   cannot fail under the package's own values, B1).

9. **`_is_multiline`'s bytes branch** (`1146:20`, `1146:30`). Its only
   package call (line 2383) passes `plain_text`, the str of
   `"\t".join(...)`: no edge.

10. **`JupyterHTMLStr(output)`** (`2728:34`): no callee (audit E1). The
    class defines neither `__new__` nor `__init__`, and `str` defines only
    `__new__` (`'__init__' in str.__dict__` is false). So the first
    `__init__` of the MRO is `object.__init__`, which gives no edge (the
    micro-benchmark rule; the dagster-pipes precedent). The writer's first
    precedents do not apply: `dict` defines its own `__init__`, and
    `RuntimeError` inherits `BaseException.__init__`. The site keeps a
    note. The trace has no edge for this call.

11. **Callable format fields** (value sites `2577:22` and `2628:23`).
    `rowfmt(...)` names the row callables of `_table_formats`:
    `functools.partial.__call__` with `_mediawiki_row_with_attrs`,
    `_moin_row_with_attrs`, `_html_row_with_attrs`, `_latex_row` and
    `_asciidoc_row` (which the partial objects call back), and the
    functions `_latex_row` and `_textile_row_with_attrs`. `linefmt(...)`
    names the line callables: `_pipe_line_with_colons`,
    `_grid_line_with_colons`, `_html_begin_table_without_header`,
    `_latex_line_begin_tabular`, and `functools.partial.__call__` with
    `_latex_line_begin_tabular` and `_asciidoc_row`. Each site excludes the
    callables of the other kind of field. The separating line
    (`2705-2711`) is one of the line fields or a `Line`, so it adds
    nothing.

12. **Builtins called back by `map`.** `len`, `str` and `wcwidth.wcswidth`
    passed to `map` are library callables that library code calls: not
    edges (`1151:19`, `1213:20`, `1243:24`, `1270:30`, `1535:31` and the
    other `map(str, ...)` sites, `2606:21`). A package function passed to
    `map` and iterated in the same function is a callee at the `map` call
    (`_visible_width`, the lambdas, `escape_char`, `_to_str`, `_len`).
    Called directly as a value (`width_fn(h)`, `len_fn(...)`), `len` and
    `wcwidth.wcswidth` are callees.

13. **Optional imports, flags and modes.** Both sides of `import wcwidth`
    (line 26) run, and `WIDE_CHARS_MODE` is a documented flag (README.md
    "Wide (fullwidth CJK) symbols" assigns it), so `wcwidth.wcswidth` and
    `len` are both callees of `_visible_width`, of the width functions and
    of `_CustomTextWrap._len`. `wcwidth.wcswidth` is named by the path the
    package uses (the trace's canonical name is `wcwidth.wcwidth.wcswidth`,
    with this alias). This was checked against the source of the pinned
    test dependency wcwidth 0.6.0 (unpacked by the lead from the
    hash-checked wheel; read only, never run): `wcwidth/__init__.py`
    (SHA-256 `5172769d…a85e`) imports `wcswidth` from `.wcwidth` and lists
    it in `__all__`, and `wcwidth/wcwidth.py` (SHA-256 `a39707fd…7a52`,
    line 236) defines it as a plain function, without the `lru_cache` that
    `wcwidth` has (line 185). So the callee is a function, not a wrapper
    object, and it calls nothing of the package. The extra is unpinned; no
    other release of wcwidth was read. No callee is named in numpy or
    pandas, which the test environment lacks: the package imports neither,
    and its NumPy and DataFrame paths call no method of the client object
    (B4 above; `hasattr`, attribute loads, `list()` and iteration only).
    `from .version import version` (line 38) imports a
    module that the tree lacks; the `ImportError` is caught and no call is
    made. The `if __name__ == "__main__":` block (line 3073) is module code:
    `tabulate -> tabulate._main`. No `TYPE_CHECKING` block and no version
    branch. Under `-O` the two `assert isinstance(...)` (lines 2432, 2476)
    disappear; under `-OO` `_main.__doc__` is None and `textwrap.dedent`
    raises inside its body. The union with normal execution keeps every
    edge.

14. **The command line** (`_main`, `_pprint_file`). `fobject.readlines()`
    (`3058:29`) is `io.TextIOWrapper.readlines`: `_main` passes `sys.stdin`
    (`_is_file` is true only for it, as the other arguments are str) or the
    text file of `open(f)`. `print(..., file=file)` calls the stream's
    `write`, which is library code calling library code.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `tabulate.JupyterHTMLStr.str` | 27 | the name `str` is the builtin; the property runs only on an attribute load `.str` | nowhere |

All 27 are explicit sites (`str(...)`, `isinstance(..., str)`,
`map(str, ...)`), and each keeps its own outside callee.

## Exclusions

| Site | Excluded | Why |
|---|---|---|
| `2577:22` `rowfmt(...)` | `_pipe_line_with_colons`, `_grid_line_with_colons`, `_html_begin_table_without_header`, `_latex_line_begin_tabular` | line fields, called by `_build_line` only |
| `2628:23` `linefmt(...)` | `_mediawiki_row_with_attrs`, `_moin_row_with_attrs`, `_html_row_with_attrs`, `_latex_row`, `_textile_row_with_attrs` | row fields, called by `_build_row` only |

## Value sites

203 value sites: the 180 namedtuple calls (judgement 2) and 23 others.

| Site | Callees |
|---|---|
| `897:13` `conv(string)` | `<builtin>.float`, `<builtin>.int` |
| `1137:22`, `1139:22` `len_fn(...)` | `wcwidth.wcswidth`, `<builtin>.len` |
| `1249:33`, `1262:33`, `1267:36`, `1274:36` `padfn(...)` | `_padleft`, `_padboth`, `_padright`, `_padnone` |
| `1395:56` `width_fn(h)` in `_align_header` | `_choose_width_fn.<lambda1>` (the branch runs only for multiline headers) |
| `2445:18`, `2493:35`, `2497:47`, `2502:34` `width_fn(...)` in `tabulate` | `_visible_width`, `wcwidth.wcswidth`, `<builtin>.len`, `_choose_width_fn.<lambda1>` |
| `1705:55` `_type(cell, numparse)(cell)` | `str`, `bool`, `int`, `float`, `bytes` (judgement 4) |
| `2577:22` `rowfmt(...)`, `2628:23` `linefmt(...)` | judgement 11 |
| `2672:29`, `2688:28`, `2698:20`, `2719:35` `pad_row(...)` | `_pad_row`, `_format_table.<lambda1>` |
| `2678:19`, `2686:27`, `2696:19`, `2718:27` `append_row(...)` | `_append_basic_row`, `functools.partial.__call__`, `_append_multiline_row` |

## Trace

The trace has 335 edges; 333 are in the graph (one trace edge,
`<builtin>.dict.get`, matches both `dict.get` and `OrderedDict.get` sites,
so 336 graph edges are confirmed), and none is rejected (judgement 3). No
trace edge is missing. 29 graph edges come from reading only: the command
line (15, judgement 14 and A), `len` where the tests had wcwidth
(`_visible_width`, `_CustomTextWrap._len`), the int, float and bytes
callees of `1705:55`, `_visible_width -> <builtin>.str` and
`_afterpoint -> <builtin>.bytes.rfind` (judgement 6), `bytes.lower` and
`bytes.strip` on bytes cells, `_format -> <builtin>.bytes.replace`
(judgement 5), `TypeError` of `_normalize_tabular_data`, `ValueError` of
`_wrap_chunks`, `_grid_line_with_colons -> len` (an empty table), and
`tabulate -> _main`.

## Statistics

| | Count |
|---|---|
| Sites | 769 (767 call, 2 decorator); 175 with candidates (181 candidates); 203 value sites |
| Ledger entries | 769 |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 644 / 39 (17) / 2 (9 nodes) / 322 |
| Default rejections | 1, deciding 27 sites |
| Edges | 365: 105 in the package, 260 outside |
| Edges that the trace confirms | 336 of 365 (92.1%) |
| Edges only from reading | 29 |
| Trace edges rejected | 0 |
| Functions that the tests run | 74 of 77 |

## Codex audit round 2

- Missing `_normalize_tabular_data -> collections.UserDict.keys`
  (`1567:43`, `1571:34`): applied (CHANGELOG:21 documents lists of
  UserDicts; named by the receiver's class, inherited from
  `collections.abc.Mapping`).
- Missing `_normalize_tabular_data -> collections.UserDict.get`
  (`1584:45`, `1592:29`): applied (same documentation and naming).
- The two rejected trace edges (`collections.UserDict.get`,
  `collections.abc.Mapping.keys`) left `tabulate.rejected.json`, which is
  now empty.
- Metadata: `JupyterHTMLStr` and its property `str` are public (rule C):
  applied to the scope text of the ledger header and of section C; no edge
  changes.
