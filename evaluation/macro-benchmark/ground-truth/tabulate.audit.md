# tabulate: independent audit of the ground truth

Release v0.10.0, commit `3b4cd509820e4c45cd2aaba833aa585ea6308b94`, batch 6.
Audited files: `tabulate.ledger` (769 entries, 1 default
rejection), `tabulate.json` (362 edges: 105 in the package, 257 outside),
`tabulate.added.json` (28 edges), `tabulate.rejected.json` (2 edges),
`tabulate.md` (14 judgements) and the trace `dynamic/tabulate.json` (335
edges). `check.py tabulate` reports no errors.

I judged the files by the README's rules (A, B1 to B5, C, the clarifications
of 2026-11-15 and the rulings for batch 6). I read the package source,
its `README.md`, `pyproject.toml` and the tests as data, and the wcwidth
0.6.0 source of the pinned test dependency, read only. I ran no analysis
tool on the package, read no tool output and ran nothing of the package.
The only Python I ran was the benchmark's own `check.py` (skeleton, reports),
my sampling script, and a bare interpreter to check two facts of CPython
(`'__init__' in str.__dict__`, `inspect.signature` of three builtins).

**Result.** The blind sample agrees with the ledger at all 260 sites. The
exhaustive checks find 1 edge that the rules exclude (E1), 1 missed edge
(M1), 1 case that needs a ruling (J5) and 3 wording items (W1 to W3). E1
and M1 are both outside edges and cancel in the count: the graph stays at
362 edges (105 inside, 257 outside). J5 adds 1 outside edge if the lead
adopts my reading.

## Findings

| Id | Severity | Site or edge | Evidence | Edges |
|---|---|---|---|---|
| E1 | high: edge that the rules exclude | `2728:34` `JupyterHTMLStr(output)` -> `<builtin>.str.__init__` (judgement 10) | `JupyterHTMLStr` (line 2640) defines no `__init__`, and neither does `str`: `'__init__' in str.__dict__` is false (`str.__init__ is object.__init__`; `str` defines only `__new__`). The first `__init__` of the MRO is `object.__init__`, and the micro-benchmark rule ("Instantiation of a snippet class") says: "If it is `object.__init__`, there is no edge." Precedent: dagster-pipes `ledger:1188-1190` ("define no `__init__`; the method is `object.__init__`": no callee). The writer's precedents do not apply: `dict` defines its own `__init__` (`'__init__' in dict.__dict__` is true), and `RuntimeError` inherits `BaseException.__init__`, which is not `object.__init__`. The trace, which ran the html tests, has no edge here. | -1 outside (`_format_table -> <builtin>.str.__init__`, an added edge) |
| M1 | medium: missed edge | `1057:31` `string.rfind(".")` in `_afterpoint`: add `<builtin>.bytes.rfind` | The witness of judgement 6 (a client str subclass whose `replace` returns bytes, in a decimal column of a table with ANSI codes) reaches `_afterpoint(_strip_ansi(s))` (line 1180) with the exact bytes that `re.Pattern.sub` returns (line 1121). For `b"1.5"`: `_isnumber` is true (`float(b"1.5")`), `_isint` is false (`int(b"1.5")` fails), so line 1057 calls `bytes.rfind(".")`. The same holds for `b"1,000.5"` through `_isnumber_with_thousands_separator`. This is the path that the writer already uses for `888:31` (`bytes.decode`). `bytes.rfind` binds the one positional argument and refuses the str inside its own code (as I understand CPython 3.10 to 3.14, `sub` is taken as any object and then tested for an int or a buffer; please check the CPython source if the lead keeps the writer's reading of judgement 5), so the call enters its body under both readings of J5. The note at `1057:31` ("the formatted cells ... are str") must name the witness. | +1 outside (`_afterpoint -> <builtin>.bytes.rfind`), conditional on judgement 6 |
| J5 | needs a ruling (README silent) | `1376:31` `val.replace(raw_val, formatted_val)`: `<builtin>.bytes.replace` (judgement 5) | Reached by documented values: a bytes cell of a float column in a table with an ANSI code elsewhere (`tabulate([[b"1.5"], ["\x1b[31m2\x1b[0m"]])`): `raw_val` is bytes and `formatted_val` a str, and `bytes.replace` raises `TypeError`. The README says "argument binding failure before entry gives no edge", but does not define binding for a C callable. The writer counts the buffer conversion of an argument as binding. I count binding as the matching of arguments to the parameters of the signature (`bytes.replace(self, old, new, /, count=-1)`: two positional arguments bind), and a type that the callable then refuses as a failure in its body. My reading is the smaller extension: it keeps the meaning that binding has for a Python function, and a reader can check it with `inspect.Signature.bind`; the writer's reading depends on where CPython's argument parser checks a type, which differs between methods and versions. Judgement 4 (`NoneType(cell)`, which takes no arguments) is an arity failure under both readings: no edge. | +1 outside (`_format -> <builtin>.bytes.replace`) with my reading; 0 with the writer's |
| W1 | wording | judgement 4 and the note at `1705:55` | `_type` returns `NoneType` also for `b""`: `cell == ""` is false for bytes, `_isnumber(b"")` is false, and `_type(b"")` returns `type(None)` (line 1012). The judgement names only a cell of ANSI codes. | 0 |
| W2 | wording | judgement 6, note at `888:31` | Say why B5 does not remove the edge: the receiver of `decode` is not the client's object (a callback result, opaque under B5) but the exact bytes that `re.Pattern.sub` returns in `_strip_ansi` (line 1121), a library result whose type is known. The same holds for M1. | 0 |
| W3 | wording | `tabulate.md` "Trace" and "Statistics" | After E1 and M1 (and J5), update the lists of edges from reading only (`str.__init__` leaves, `bytes.rfind` and maybe `bytes.replace` come in) and the counts. | 0 |

No finding changes the trace or the rejected edges: E1 and M1 are edges
that the trace does not have.

## Step 1: blind re-derivation

**Skeleton.** A scratch benchmark directory
(`$TMPDIR/audit-tabulate/`, a copy of `projects.toml` and of
`projects/tabulate`), and `check.py --benchmark-dir <scratch> --skeleton
tabulate`: 769 sites, all explicit (767 call, 2 decorator), 203 value sites.
No implicit site has a candidate (no package class defines a special method
other than `__init__`), so the skeleton has none.

**Sample.** I numbered the 769 sites from 0 in (line, column) order and drew
`random.Random(20261122).sample(range(769), 70)`, then added all 203 value
sites: 260 sites, 13 in both. I did not draw by kind: every site is an
explicit call. 180 of the value sites are calls of the namedtuple classes
`Line`, `DataRow` and `TableFormat`, which have no edge; they test the notes
and the rejections of the stored callbacks. I wrote my callees for each site
before I opened any file of the writer (`blind.txt` in the scratch
directory).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Namedtuple calls (value sites) | 180 | 180 | 0 |
| Other value sites | 23 | 23 | 0 |
| Drawn, not value sites | 57 | 57 | 0 |
| **Total** | **260** | **260** | **0** |

Points where I checked the agreement closely:

- `1213:16`, `1243:20` (`list(map(width_fn, ...))`): I wrote the callbacks
  `_visible_width` and `_align_column_choose_width_fn.<lambda1>` at the
  `list` site or at the `map` site; the ledger has them at the `map` sites
  (`1213:20`, `1243:24`). Same edges, same function.
- `1395:56` (`width_fn(h)` in `_align_header`): only
  `_choose_width_fn.<lambda1>`, as in the ledger: the branch runs only for
  `is_multiline`, and tabulate() passes the same flag to `_choose_width_fn`.
- `1139:22` (`len_fn(str(s))`): reachable only through the client str
  subclass of judgement 6; I reached it with `numalign=None` before I read
  the judgement.
- `1705:55` (`_type(cell, numparse)(cell)`): `str`, `bool`, `int`, `float`,
  `bytes`; `NoneType` refuses any argument (no edge).
- `1567:43`, `1592:29`: `dict` and `collections.OrderedDict` methods, on the
  docstring of `_normalize_tabular_data` (see judgement 3 below).

## Step 2: exhaustive checks

**The whole ledger against the source.** I read every entry that is not a
namedtuple call (589 entries) against the source, function by function, and
looked for sites the skeleton might miss (none: the checker accepts the
positions, and every explicit call in the source has an entry). Apart from
E1, M1 and J5 every callee, rejection and note holds.

**Dispatch and value sets.**

| Role | Values | Sites |
|---|---|---|
| row field (`_build_row`, `2577:22`) | partials of `_mediawiki_row_with_attrs`, `_moin_row_with_attrs`, `_html_row_with_attrs`, `_latex_row`, `_asciidoc_row`; the functions `_latex_row`, `_textile_row_with_attrs` | agrees with judgement 11 |
| line field (`_build_line`, `2628:23`) | `_pipe_line_with_colons`, `_grid_line_with_colons`, `_html_begin_table_without_header`, `_latex_line_begin_tabular`; partials of `_latex_line_begin_tabular` and `_asciidoc_row`. The separating line (`2705-2711`) is a line field or a `Line`; html's `""` is false | agrees |
| `padfn` (4 sites) | `_padleft` (right, decimal), `_padboth`, `_padnone` (None), `_padright`; each site reachable with every alignment | agrees |
| `width_fn` of tabulate() (4 sites) | `_visible_width`, `wcwidth.wcswidth`, `len`, `_choose_width_fn.<lambda1>` | agrees |
| `pad_row`, `append_row` (8 sites) | `_pad_row` or the lambda; `_append_basic_row` or the partial of `_append_multiline_row` | agrees |
| `conv` (`897:13`) | `float`, `int` (no package call passes another `inttype`) | agrees |
| `len_fn` (`1137:22`, `1139:22`) | `wcwidth.wcswidth`, `len` (`WIDE_CHARS_MODE` is a documented client flag) | agrees |
| `_CustomTextWrap` receivers | the one instance kind of line 1690, `max_lines` None (judgement 7) | agrees |

**Binding check.** I checked every call of a package function (the 162
pairs of a site and a package callee in the ledger, also the calls through
the partial objects and the value sites) against the callee's signature. All bind,
including `_align_header`'s recursive call with four arguments, the partial
of `_append_multiline_row` with `pad` as a keyword and `rowalign` as a
keyword, and `partial(_asciidoc_row, ...)` with two or three arguments.

**Default rejection.** `tabulate.JupyterHTMLStr.str` decides 27 sites
(`check.py --report tabulate --default tabulate.JupyterHTMLStr.str`). At each
the name `str` is the builtin (`str(...)`, `isinstance(..., str)`,
`map(str, ...)`), and the package never loads an attribute `.str`. Right at
all 27.

**Implicit sites.** `--without-candidates`: no iteration, `with` or mapping
site iterates a lazy `map` or `filter` built in another function; every
`map` of a package function is consumed in the function that builds it.
The package has no generator function.

**Functions that no site calls.** The module node, `simple_separated_format`
(public), `JupyterHTMLStr._repr_html_` and the property `JupyterHTMLStr.str`
(for Jupyter and the client). Their bodies make no call.

**Callees outside the package.** All names follow the micro-benchmark
rules, except E1. I checked `wcwidth.wcswidth` in the pinned wcwidth 0.6.0
(`wcwidth/__init__.py` re-exports it and lists it in `__all__`; line 236 of
`wcwidth/wcwidth.py` defines it as a plain function, without the
`lru_cache` of `wcwidth`), `functools.partial.__call__` for the calls of the
partial objects, `io.TextIOWrapper.readlines` for `sys.stdin` and `open(f)`,
`itertools.zip_longest` for the alias `izip_longest`, and
`importlib.metadata.version` for `_version`.

**Trace.** 335 trace edges: 333 in the graph, 2 rejected. The 2 rejected
edges (`collections.UserDict.get`, `collections.abc.Mapping.keys`) come from
the tests' list of `UserDict`s (`test_input.py:385-418`); see judgement 3.
The trace edge `_isnumber_with_thousands_separator -> <builtin>.bytes.decode`
comes only from the doctest at line 880 (no test passes bytes to a public
path that reaches it); the graph keeps it through judgement 6, and rightly
(W2). If the lead rejected judgement 6, this edge would move to the rejected
edges (rule A: a direct test of a private function), and `_visible_width ->
<builtin>.str` and M1 would go.

## The writer's judgement calls

- **3, OrderedDict methods and the tests' UserDict: supported.** B4 names a
  concrete outside type that the documentation fixes, and "documentation is
  read one entry at a time" (funcy ruling 7). The four sites are in
  `_normalize_tabular_data`, and its own docstring lists "list of
  OrderedDicts" (line 1471) among the inputs it handles: this is the entry of
  the function that holds the sites. No rule limits B4 to the docstrings of
  public functions (rule C itself reads docstrings as documentation). The
  README does not say so in words; the smaller extension is: the docstring of
  a private function documents its own parameters for the sites in that
  function. The UserDict rows are named by no document, so they are client
  objects (B5), as the tests' own `defaultdict` of funcy ruling 7; rejecting
  their two trace edges is right.
- **4, `NoneType(cell)`: supported.** `NoneType` takes no arguments; the call
  fails on the number of arguments, which is binding under any reading.
- **5, `bytes.replace`: not decided by the README.** See J5: I would keep the
  edge (+1).
- **6, a client str subclass whose `replace` returns a non-str: supported.**
  The nearest rules are the clarification "Client control flow (B5)" (an
  admitted subclass can override operations; the effects of client methods
  on control flow count) and B2 ("This does not make an admitted `str`
  subclass behave like an exact `str`", python-barcode `codex.py:240`). Cells
  are arbitrary client objects, and the tests use a str subclass
  (`test_regression.py:294`). Both edges stand: `str(s)` at `1139:26` is a
  builtin call with a client argument, and the receiver at `888:31` is a
  library result (W2). The same witness also gives M1.
- **10, `<builtin>.str.__init__`: wrong.** See E1.
- **1, 2, 7, 8, 9, 11 to 14: supported** by B1 (one state of a private
  class; a check that cannot fail under the package's own values), B3 (a
  client `TableFormat`'s callables are client callbacks), the namedtuple rule,
  the callback rule for `map`, the optional-import and `-O`/`-OO` rules.

## Remarks on the README and the tools

- **R1 (README).** "Argument binding failure before entry" has no definition
  for a C callable (J5). A sentence would settle it for batch 6, for
  example: "A call binds when its arguments match the parameters of the
  callee's signature; a type that the callee then refuses is a failure in its
  body."
- **R2 (README).** The rule for an inherited `__init__` could name the case
  of E1: a builtin base that defines no `__init__` (`str`, `int`, `tuple`,
  `bytes`, `float`) leaves `object.__init__`, so its subclass's call has no
  edge.
- The tools worked as described. The brief's "draw by kind" did not apply:
  every site is an explicit call, and the 203 value sites are all in the
  sample.
