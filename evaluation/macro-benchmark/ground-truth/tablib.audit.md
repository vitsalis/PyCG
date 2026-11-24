**Status (2026-11-24):** closed. The writer applied F1 to F4 and the
lead's rulings in `c80e4aa` (1079 edges: 504 inside, 575 outside; 13
rejected trace edges); the re-check (section "Re-check" at the end) finds
nothing open.

# tablib: blind audit of the ground truth

Release v3.10.0, commit `b0ff39fb9b2f457e5332249b4cc2ec11eabf46ee` (batch 8,
traced). Audited files: `tablib.ledger` (4103 lines, 1440 entries, 13
default rejection lines with 26 candidates), `tablib.json` (304 nodes, 1079
edges: 504 inside, 575 outside), `tablib.added.json` (210 edges),
`tablib.rejected.json` (12 edges) and `tablib.md` (J1 to J9, O1, O2), at
the writer's commit `c52455e` on `b8-gt-tablib`. `check.py tablib`
reports no errors; `check.py --origin tablib` gives 880 trace edges, 12
rejected, 869 traced edges in the graph, 210 added.

I judged the files by the scope rules A, B1 to B5 and C of
`macro-benchmark/README.md`, with the clarifications, the rulings for
batch 6 and the rulings for batch 7, and named outside callees by
`PyCG/micro-benchmark/README.md`. I read all 28 modules of `src/tablib/`,
`pyproject.toml`, `tox.ini`, `HISTORY.md`, `.github/workflows/test.yml` (as
data), `docs/*.rst`, the tests that pass values to public parameters, the
trace, and from `deps/`: odfpy 1.4.1 (`odf/element.py`, `number.py`,
`style.py`, `table.py`, `load.py`), openpyxl 3.1.5 (`utils/cell.py`,
`workbook/__init__.py`, `styles/__init__.py`), xlwt 1.3.0 and xlrd 2.0.2
(`__init__.py`), tabulate 0.10.0 (`_normalize_tabular_data`), and CPython
3.10 to 3.15 `Modules/_csv.c` and 3.13/3.14 `Objects/abstract.c`
(`PySequence_Tuple`). I did not run or import the package or a library, and
ran no analysis tool. Commands: `check.py --benchmark-dir <scratch>
--skeleton tablib` and `--report tablib` on a scratch copy without the
ledger; then `check.py tablib`, `--origin`, `--report`, `--report
--without-candidates`, and `--report --default` for `Row.__iter__`,
`Row.__len__`, `Row.__getitem__`, `Dataset.__len__`,
`Dataset.__getitem__`, `Dbf.__len__`; my `draw.py`; and an `ast` script of
my own for the binding check.

## Final state

Agreement 95 of 95. One edge that cannot happen (F1), one missing edge
(F2), two edges whose admission needs a ruling (F3), two edges expected
missing that cannot be verified from `deps/` (F4). No edge inside the
package changes. With F1 and F2 applied the graph stays at 1079 edges (504
inside, 575 outside); F3 as I read it gives 1077 and one more rejected
trace edge; F4 would add 2 once read.

## Findings

| Id | Kind | Site or edge | Evidence (file:line) | Edges | Decision |
|---|---|---|---|---|---|
| F1 | edge that cannot happen (low) | `_rst.py:74:35`, `ReSTFormat._row_to_lines.just -> <builtin>.str.rjust` | `just` reads the closure's `justify`; `_row_to_lines` is private and its only callers pass `JUSTIFY_CENTER` (`_rst.py:129`, `181`) or the default `JUSTIFY_LEFT` (`:134`, `:186`); nothing passes `JUSTIFY_RIGHT` (`:12`). The writer's own J9 makes the `ValueError` at `:64` unreachable for the same reason. The trace has only `center` and `ljust`. | -1 outside | the writer removes the callee, notes the site as J9 |
| F2 | missing edge (low) | `record.py:196:29`, `DbfRecord._validateIndex -> <builtin>.ValueError` | J4 judges the uncalled `Dbf.__setitem__` as public, so `index` is any int. `Dbf._fixIndex` (`dbf.py:181-187`) adds `len(self) + 1` to a negative index and checks only the upper bound: `index = -10` on an empty table returns `-9`. `__setitem__` stores it (`dbf.py:248`) and `_write` calls `_validateIndex(False)` (`record.py:172`), which raises at `:196`. The note "never negative" is wrong. | +1 outside | the writer adds the callee (it stands or falls with J4's `Dbf.__setitem__` decision) |
| F3 | edges no rule admits (low; for the lead) | `_xls.py:138:67`, `XLSFormat.import_book -> io.BufferedReader.read` (traced) and `-> io.TextIOWrapper.read` | J1 takes the concrete file classes from the tutorial's examples, which pass `open(...)` only to `Dataset.load` (`docs/tutorial.rst:109`, `118`, `335`). `Databook.load` (`core.py:905-911`) carries the same abstract phrase "a file-like object" but no example. B4 (funcy): "Documentation is read one entry at a time". Every other J1 site is reached from `Dataset.load` by forwarding (`detect_format`, `import_set`); these two are reached only through `Databook.load`. | -2 outside (1 to `rejected.json`) | my opinion: remove; the lead rules (part of J1) |
| F4 | expected missing names, unverified (for the lead) | `_xlsx.py:165:44`, `218:58`: `openpyxl.utils.cell.get_column_letter` beside `functools._lru_cache_wrapper.__call__` | tablib declares `openpyxl>=2.6.0` (`pyproject.toml`, `HISTORY.md:150`). In 3.1.5 the function is `@lru_cache` (`openpyxl/utils/cell.py:78`); from memory, 2.6.x and 3.0.x define it as a plain function over `_STRING_COL_CACHE`. README: "a callee that is a plain function on one supported version and a wrapper object on another" keeps both names (fastjsonschema `urlsplit`), and the batch-7 dependency ruling keeps the names of every admitted release. Not read: no openpyxl before 3.1.5 is in `deps/`. | +2 outside (expected) | the lead supplies the sources (see "For the lead"); the writer then adds the names that the sources confirm |

Wording: J4's list "`_validateIndex`'s three `ValueError`s" (`tablib.md`)
becomes two with F2; J9 should name `just`'s `rjust` with F1. No separate
W finding.

## Step 1: blind re-derivation

**Skeleton.** I copied `projects.toml` and `projects/tablib` to a scratch
directory and ran `check.py --benchmark-dir <scratch> --skeleton tablib`:
2025 sites (1053 call, 76 decorator, 144 iter, 16 mapping, 119 op, 106
getitem, 26 setitem, 7 delitem, 277 getattr, 36 setattr, 122 truth, 43
format), 1490 with candidates, 26 value sites.

**Draw.** No kind dominates: explicit sites are 1129 of 2025 (56 %), the
largest implicit kind (`getattr`) 277 (14 %). So the draw is plain:
`audits/tablib/draw.py` numbers the sites by (module in skeleton order,
line, column) and takes `random.Random(20261124).sample(range(2025), 70)`,
then adds the 25 value sites not drawn (`_df.py:22:22` was drawn). 95
sites; the 70 drawn are 41 call, 3 decorator, 12 getattr, 5 iter, 3 op, 2
getitem, 1 each of mapping, setattr, setitem and truth. The answers were
committed as `4e23445` (`audits/tablib/blind-answers.md`, `sample.txt`,
`draw.py`) before I opened any file of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit (call, decorator), drawn | 44 | 44 | 0 |
| Implicit, drawn | 26 | 26 | 0 |
| Value sites not in the draw | 25 | 25 | 0 |
| **Total** | **95** | **95** | **0** |

The 17 drawn implicit sites without a ledger entry (`dbf.py:228:34`,
`dbfnew.py:3:33`, `fields.py:86:27`, `utils.py:71:34`, `core.py:183:45`,
`250:45`, `847:13`, `formats/__init__.py:75:29`, `_csv.py:45:40`,
`_html.py:88:57`, `_latex.py:55:62`, `_ods.py:118:32`, `211:36`,
`_rst.py:256:24`, `_xls.py:86:20`, `158:23`, `_xlsx.py:157:33`) are decided
by the defaults, and I had rejected every candidate there. The two
non-edges that a reading by name would give, `header.py:88:31` (`list`)
and `header.py:200:28` (`DbfFieldDef.__init__`), were non-edges in both.

## Step 2: exhaustive checks

- **Dispatch sets.** The format dispatch (J3): `Dataset.load` and
  `_set_in_format` and `ImportExportSetDescriptor.__set__` name the ten
  formats with `import_set`; `export`, `_get_in_format` and
  `ImportExportSetDescriptor.__get__` the fourteen with `export_set`
  (`TSVFormat` inherits `CSVFormat`'s); `Databook.load` and the book
  descriptor's `__set__` the five with `import_book`; `Databook.export`
  and its `__get__` the seven with `export_book`; `detect_format` the nine
  with `detect`. Each set matches the class bodies. Field definitions:
  `decodeFromRecord` names the eight distinct `decodeValue`s
  (`DbfFloatFieldDef` inherits the numeric one), `DbfRecord.toString` the
  eight `encodeValue`s (through J4's `Dbf.__setitem__`), and
  `lookupFor(...).fromString`, `fieldInfo`, `toString` the base methods
  that no subclass overrides. `Dbf.HeaderClass`, `RecordClass` and
  `dbf_new.FieldDefinitionClass` have one value each (`__slots__`, no
  subclass, no assignment). The formatter and dynamic-column callables are
  client callbacks (`tests/test_tablib.py:195-202`, `615-638`;
  `docs/tutorial.rst:233-275`).
- **Default rejections.** I read the reports of `--default` for the six
  candidates above. Every site where a `Row`, `Dataset` or `Dbf` is
  iterated, subscripted, measured or truth-tested has an entry that
  accepts the candidate (`core.py:44`, `183`, `232`, `258-272`, `290-297`,
  `406`, `462-464`, `620`, `726`, `739`, `814`, `828`, `852`,
  `_sql.py:63`, the four `for row in dataset` and tabulate's
  `list(tabular_data)`, `dbf.py:184-185`, `260`, `record.py:178`, `213`,
  dbfnew's `183-184`); the default-decided sites iterate lists, tuples,
  dicts, library objects or client values. The `__repr__`, `__str__`,
  `__eq__`, `__hash__` and `__bool__` defaults rest on J5 (no
  `INVALID_VALUE` leaves dbfpy: every package `Dbf` has `ignoreErrors`
  False), which holds.
- **Functions that no site calls** (61 function nodes without an
  in-edge, beside the 28 modules): client API (`Dataset.sort`, `stack`, `subset`, ...,
  `Databook.size`, `sheets`), pickling hooks of `Row`, the descriptors'
  book methods and `ImportExportSetDescriptor.__set__`, the partialmethod
  targets `_get_in_format` and `_set_in_format`, and dbfpy's uncalled
  helpers (`Dbf.__setitem__`, `newRecord`, `demo_read`, `DbfRecord.asDict`,
  `asList`, `delete`, `DbfHeader.fromString`, `__getitem__`, the
  `_InvalidValue` methods). None has a package caller that the graph
  misses; each keeps its body edges (rule A).
- **Special methods and properties.** The properties `headers`, `dict`,
  `height`, `width`, `Row.tuple`, the dbfpy lambdas (`Dbf.<lambda2>`,
  `<lambda3>`, `<lambda5>`, `DbfHeader.<lambda1-3>`, `DbfRecord.<lambda1>`)
  and the setters `Dbf.ignoreErrors`, `DbfHeader.ignoreErrors` are at their
  loads and stores; `classproperty.__get__` at the two `defaultValue`
  loads; the descriptor `__get__` at `_html.py:53:28` (added by hand,
  correct: `Registry.register` always sets `html`). The slots (`changed`,
  `recordCount`, `ignoreErrors` of fields) have no callee.
- **Rejections, exclusions and notes.** I read all 434 rejection lines
  (no exclusion exists) and every note; the unreachable-code notes of J4
  hold (`demo_create` raises at `addField`; dbfnew's block raises at
  `dbft[i1]` on `date(50, 48, 48)`; `bytes in str` at `fields.py:315`)
  except `record.py:196:29` (F2). The closure branch at `_rst.py:74` is F1.
- **Callees outside the package.** Checked against `deps/` and CPython:
  `odf.element.Element.addElement`/`getAttribute` (the `number`, `style`,
  `table`, `text` factories return `Element`; `StyleElement` is a function,
  `odf/style.py:24`), `odf.element.Text.hasChildNodes` (`element.py:286`;
  `load.py:69-72` adds text nodes), `xlwt.Style.easyxf`,
  `xlwt.Workbook.Workbook.*`, `xlwt.Worksheet.Worksheet.write` (re-exports
  in `xlwt/__init__.py` without `__all__`), `openpyxl.workbook.workbook.Workbook`,
  `openpyxl.styles.fonts.Font`, `openpyxl.styles.alignment.Alignment`,
  `openpyxl.reader.excel.*`, `xlrd.open_workbook`, `xlrd.book.Book.*`,
  `xlrd.sheet.Sheet.*`, `tabulate.tabulate` with its call-backs into
  `Dataset.__len__` and `__getitem__` (tabulate 0.10.0
  `__init__.py:1539`), `_csv.writer.writerow` (the type is `_csv.writer`
  on 3.10 to 3.15, `Modules/_csv.c`), `<builtin>.AttributeError.__init__`
  and `<builtin>.NotImplementedError.__init__` for `HeadersNeeded` and
  `UnsupportedFormat`, `<builtin>.property.__init__` for `classproperty`,
  pandas as a missing module. `tuple()` calls `__len__` on 3.10 to 3.13
  and not on 3.14 (`PySequence_Tuple`), as the writer says.
- **Rejected trace edges.** The nine `getDate`/`getDateTime` edges come
  from direct test calls of private functions with values that no package
  call passes (rule A, private input; the pymysql ruling); the three
  `BaseException.__init__` edges are `raise` without a call (README,
  "Implicit calls"). All twelve stand.
- **Trace edges that the graph lacks:** none (`check.py` and the report).
- **Implicit sites without candidates** (1117: 829 getattr, 123 op, 103
  setattr, 46 class, 16 raise): no `iter` site among them, so no lazy
  `map`/`filter` or library generator is iterated without a candidate;
  every `map` is consumed in the function that builds it, with client or
  library callables except `map(str, row)` (`core.py:232:31`, `Row.__iter__`,
  in the graph). The `raise` sites and the `class` sites have no package
  callee.

## Step 3: binding check

My script parses every module with `ast`, finds the call node of each
ledger site, and binds the call's arguments against the signature of each
package callee (implicit `self` or `cls` for methods, classmethods,
`__init__`; none for staticmethods and functions). 396 site-callee pairs
checked; 310 bind; the other 86 pass `*args` or `**kwargs` (the format
dispatch `fmt.export_set(self, **kwargs)`, `addField(*defs)`), and each
binds with the package's own empty or tuple values. I also checked the
call-backs by hand (`serialize_objects_handler(obj)`, `replace(match)`,
the three parser handlers, `self.fget(cls)`, tabulate's `__getitem__(i)`).
No call fails to bind.

## The writer's judgement calls

| J | My opinion | Nearest rule |
|---|---|---|
| J1 (documented file streams, 16 edges) | Agree for `Dataset.load` and what it forwards to; disagree for the two edges reached only through `Databook.load` (F3). | B4 (a concrete type named by documentation; funcy, one entry at a time); B2 forwarding (pymysql) |
| J2 (a DataFrame as a stream, 8 edges) | Agree. The tests pass the frame of `export('df')` to `detect_format` (`tests/test_tablib.py:427-428`); the combination ruling (django-environ) carries it to every detector and set importer; the `read`/`seek` names follow the missing-module convention, under which `hasattr(stream, 'seek')` may succeed (websocket-client: a stub result may take either outcome). | B2 test clause; "Missing modules"; einops (a stub result keeps its path through forwarding) |
| J3 (the format registry) | Agree. | B1, B2 (documented `registry`, `docs/development.rst`) |
| J4 (vendored dbfpy) | Agree, with F2. `Dbf.__setitem__` judged as public is the rule's fallback for an uncalled private function, and it decides the 8 `encodeValue` edges and the `BufferedReader`/`BytesIO` write edges; the rejected trace edges follow rule A. | A; B (uncalled private fallback); B1 (argcomplete) |
| J5 (`INVALID_VALUE` never leaves dbfpy) | Agree. | B1 (every instance in one state) |
| J6 (importer cells at `isoformat`) | Agree. | B2 (package values), B4 (`isinstance` and the importers' types) |
| J7 (`Databook.__repr__`) | Agree: no document or test sets a Databook title. | B2 (pyrate-limiter, python-barcode: assignments of public attributes) |
| J8 (`register`'s `except AttributeError`) | Agree; it adds no pair. | Clarification "Client control flow" |
| J9 (`justify`) | Agree; its consequence for `rjust` is F1. | B (private inputs) |

## For the lead

1. **F3** (2 outside edges, one traced): whether the tutorial's `open()`
   examples for `Dataset.load` admit file objects at `Databook.load`.
   My opinion: no (B4, "one entry at a time").
2. **The admitted dependency releases (O1, F4).** The rules admit every
   release that satisfies the declared requirement, not the pinned trace
   environment only:
   - README, "Rulings for batch 7", "Which releases of a dependency are
     admitted" (`b7-ruling-numpy-einops.md`): "A declared dependency
     requirement, including an unversioned installable extra, admits
     releases satisfying that requirement on an admitted Python runtime,
     subject to explicit support restrictions"; "The benchmark pin
     establishes its own configuration without imposing a support bound,
     and each call site keeps the names from the admitted versions on which
     its interface exists"; the lead's "the pin decides" (einops) "was
     wrong as a rule". tablib's extras give `openpyxl>=2.6.0`
     (`HISTORY.md:150` fixes that floor) and bare `odfpy`, `pyyaml`,
     `tabulate`, `xlrd`, `xlwt`, `pandas`; each admits every release that
     runs on CPython 3.10 to 3.15.
   - The django-constance ruling of Codex round 1 ("Dependencies without a
     bound ... read at the audit pin only", `django-constance.md`,
     judgement 1) predates this ruling and is superseded by it for
     unversioned extras: the batch-7 ruling names "an unversioned
     installable extra" explicitly. It does not limit tablib's bare extras
     to the pin.
   - "Callees outside the package": a callee that is a plain function on
     one admitted version and a wrapper on another has both names
     (fastjsonschema `urlsplit`, from Python 3.11), which is F4's case;
     "Judgements": a dependency-version branch runs if an admitted version
     takes it (markdown2).
   - **Read from sources: yes.** `writer.md` ("every callee is decided by
     reading"; "If a source that you need is not there, ask the lead;
     never download it") and `auditor.md` (Step 2: "each name from the
     dependency sources, not from another ledger") require it. Precedent:
     django-constance, where the lead supplied the text sources of Django
     4.2.30, 5.0.14, 5.1.15, 5.2.19 and 6.0.10 beside the pin, "the last
     release of its family that the classifiers name", and the audit's W2
     had flagged a 4.2 name taken from memory; uncertainties took the
     older numpy names from another ledger's reading, which the batch-8
     auditor brief now excludes. So the older releases are fetched by the
     lead in a container, as `deps/` was, and pinned by SHA-256 in
     `MANIFEST.json`.
   - **Scope (no rule decides it; R1).** For a family-named range the
     precedent reads the last release of each family. For an open range
     the README is silent. My proposal: the floor (or the oldest release
     that runs on CPython 3.10) and the last release of each minor series:
     openpyxl 2.6.0, 2.6.4, 3.0.10 (F4: `get_column_letter`;
     `ExcelReader.read_manifest` and `Workbook.remove` at the floor);
     xlrd's last 1.x (its `open_workbook`, `Book`, `Sheet`,
     `xldate_as_datetime`); tabulate's last single-module release
     (`_normalize_tabular_data`'s call-backs into `Dataset`); the oldest
     odfpy, PyYAML and xlwt 1.x that run on 3.10. pandas needs none
     (missing module). From my reading of the pinned sources, only
     `get_column_letter` is expected to change a name (2 edges); the
     others are checks that the names hold.

## Remarks on the README

- **R1 (low).** The dependency ruling admits every release of an open or
  bare requirement but says nothing on which releases a writer must read
  to find where a name changes. The django-constance precedent (last
  release of each named family) covers closed ranges only. One sentence
  would fix it (see "For the lead", item 2).

## Re-check against `c80e4aa`

The lead ruled on 2026-11-24: F1 and F2 apply, F3 removes both edges, J1
(for `Dataset.load`), J2 and J3 stand, and O1/F4 follow batch 7's release
ruling with the lead's sampling rule (the floor or the oldest release that
runs on the oldest admitted Python, and the last release of each minor
series), fetched into `deps/pypi`. I read `git diff a510a72 c80e4aa` of
the five writer files, ran `check.py tablib` (no errors) and `check.py
--origin tablib` (880 trace edges, 13 rejected, 868 traced in the graph,
211 added, 1079 graph edges: 504 inside, 575 outside), and read the new
dependency sources as files.

| Id | Change in `c80e4aa` | Check | State |
|---|---|---|---|
| F1 | `_rst.py:74:35`: `-> <builtin>.str.rjust` replaced by a note (J9); J9 names the branch | `just` now has `center` and `ljust` only | closed |
| F2 | `record.py:196:29`: `-> <builtin>.ValueError` with the `_fixIndex` note; J4 lists the two other `ValueError`s as unreachable | graph has `DbfRecord._validateIndex -> <builtin>.ValueError` | closed |
| F3 | `_xls.py:138:67`: `io.BufferedReader.read` and `io.TextIOWrapper.read` removed; `_io.BufferedReader.read` of `XLSFormat.import_book` in `tablib.rejected.json` with the reason; J1 narrowed to 14 edges | the rejected edge is the traced one; `check.py` accepts it | closed |
| F4 | `_xlsx.py:165:44` and `218:58`: `-> openpyxl.utils.cell.get_column_letter` beside the wrapper name | see below | closed |

**Dependency names, read against the sampled releases.**

- openpyxl 2.6.0, 2.6.4, 3.0.10: `get_column_letter` is a plain function
  (`utils/cell.py:107`, `107`, `105`, a lookup in `_STRING_COL_CACHE`, no
  decorator); `openpyxl/utils/__init__.py` imports it from `.cell` and has
  no `__all__`, so `openpyxl.utils.cell.get_column_letter` is the name.
  3.1.5 has the `lru_cache` (`:78`). `ExcelReader` and `read_manifest`
  (`reader/excel.py:118`/`135`, `118`/`135`, `116`/`133`), `load_workbook`,
  `Workbook.create_sheet`, `remove`, `save`, and `Font`/`Alignment` from
  `styles.fonts`/`styles.alignment` exist in all three. **The `slots.py`
  claim holds:** `descriptors/slots.py` uses `collections.Callable` (line
  14) but has no import statement at all, and no module of these releases
  imports it; no other module uses a `collections` ABC alias, so the three
  releases import on CPython 3.10.
- tabulate 0.5.1 keeps the Dataset as `rows` and calls `len(rows)`,
  `rows[0]` and `list(map(list, rows))` (`_normalize_tabular_data`):
  `Dataset.__len__` and `__getitem__`. 0.4.2 has no normalisation;
  `tabulate(list_of_lists, ...)` does `zip(*list_of_lists)` (line 422),
  whose unpacking takes the length hint (on 3.10 to 3.13) and iterates by
  `__getitem__`. Both accept the `headers` and `tablefmt` keywords that
  `CLIFormat` passes. The call-backs at `_cli.py:23:24` are unchanged.
- xlrd 1.2.0: `open_workbook` (`__init__.py:33`), `book.Book.sheets` and
  `sheet_by_index` (`book.py:450`, `461`), `sheet.Sheet.row_types` and
  `row_values` (`sheet.py:483`, `491`), `xldate.xldate_as_datetime`
  (`xldate.py:130`); its xlsx reader also makes a `Book` (`xlsx.py:793`);
  `perf_counter` with a `clock` fallback (`book.py:16-19`), so it imports
  on 3.10.
- xlwt 1.0.0, 1.1.2, 1.2.0: `__init__.py` re-exports `Workbook`,
  `Worksheet` and `easyxf` without `__all__`, as 1.3.0; `Style.easyxf`,
  `Workbook.add_sheet`, `save` and `Worksheet.write` exist in each.
- odfpy 1.3.0, 1.3.6: `Node.hasChildNodes`, `Childless.hasChildNodes`,
  `Text(Childless, Node)`, `Element.addElement`, `getAttribute`;
  `StyleElement` is a function returning an `Element`, `DateStyle` and
  `TableCell` return `Element`s; `opendocument.load`,
  `OpenDocumentSpreadsheet` and `OpenDocument.save` exist.
- PyYAML 5.1 and 5.4.1: `safe_load` and `safe_dump` are defined in
  `lib3/yaml/__init__.py` (`:154`, `:300`).

**Nothing else changed.** The diff of the ledger touches only the four
sites of F1 to F4; `tablib.json` changes by the five edges (-1, +1, -2,
+2); `tablib.added.json` and `tablib.rejected.json` follow; `tablib.md`
records the rulings, the sampled releases and the per-release evidence.
No finding is open.

## Codex round 1 re-check

Against `a8bff7e` (T01 to T07) and `574148b` (T08, the lead's ruling: no
edge) on `b8-gt-tablib`; the findings are
`selection/batch-8-proposal/codex-audits/round-1/tablib.md`. At `574148b`
the graph has 1086 edges (505 inside, 581 outside): `git diff 23df514
574148b` of the ledger and the graph adds exactly the seven edges below
and the pair `insert_col -> <builtin>.list.insert` at `core.py:574:27`,
which the graph already had from `568:32`; nothing else changes. The later
`4f908c7` (`_csv.Writer.writerow`, the referee's C-type naming ruling) is
outside this re-check, as the lead asked; `check.py tablib` at `HEAD`
reports no errors.

| Id | Edge (site) | Check | State |
|---|---|---|---|
| T01 | `Dataset.__repr__ -> <builtin>.bytes.lower` (`core.py:220:40`) | `construct_yaml_binary` returns `base64.decodebytes(...)`, bytes, and is registered for `tag:yaml.org,2002:binary` in PyYAML 5.1 (`lib3/yaml/constructor.py:286-295`, `439`) and 6.0.3 (`lib/yaml/constructor.py:294-303`, `448`); `YAMLFormat.import_book` stores `sheet['title']` unchanged (`_yaml.py:50`). Only `str` and `bytes` of the YAML and JSON scalar types have `lower`. | agree |
| T02 | `_max_word_len -> <builtin>.bytes.split` (`_rst.py:29:49`) | A `!!binary` mapping key reaches `self.headers = list(pickle[0].keys())` (`core.py:372`) through `_yaml.py:40`; `_rst.py:46` passes each header to `_max_word_len`, whose truth test passes and whose `text.split()` is `bytes.split` (no argument, so it binds). | agree |
| T03 | `Dbf.indexOfFieldName -> <builtin>.bytes.upper` (`dbf.py:207:38`) | `DBFFormat.export_set` makes the field from `str(name).upper()` (`fields.py:85`), so the DBF write succeeds, then passes the bytes header to `record[fieldname]` (`_dbf.py:45`); `DbfRecord.__setitem__` skips its `int` branch and calls `indexOfFieldName` (`record.py:262`); `name.upper()` runs before `names.index` raises. | agree |
| T04 | `Dataset.__setitem__ -> Row.__iter__` (`core.py:195:19`) | A slice key is a client value of the public `__setitem__` (its sibling `__getitem__` handles slices explicitly, `core.py:191`). CPython 3.10.22 and 3.14.10: slice assignment reaches `list_ass_slice` (`listobject.c:2934`; 3.14 through `list_ass_slice_lock_held`), which calls `PySequence_Fast` on the `Row`; `PySequence_Fast` calls `PyObject_GetIter` and then `PySequence_List` of the generator (`abstract.c`), so no `Row.__len__`. | agree |
| T05 to T07 | `format_row -> <builtin>.list.copy`, `dict.copy`, `set.copy` (`core.py:290:31`) | The witness binds and runs as written: `_set_dict` makes one Row whose cell is the YAML list, dict or set (`construct_yaml_seq`, `construct_yaml_map`, `construct_yaml_set`); `d[0]` is a one-item tuple; `_validate` compares its length with `width` 1; the slice assignment stores the cell in `_data`; `add_formatter(None, ...)` and `d.dict` reach `row.copy()`. No step fails before it (B3 does not apply). | agree |
| T08 | `Dataset.__init__ -> ImportExportSetDescriptor.__set__` (`core.py:172:14`) | The lead's ruling (no edge) is recorded in `tablib.md`; it agrees with B3 and the rule on changes of package internals. | closed by ruling |

**The corrected invariant.** After a slice assignment, `_data` can hold the
items of the assigned value: the containers and scalars that the importers
make (YAML: list, dict, set, str, bytes, int, float, bool, None, date,
datetime), and also the tuples of a package slice (`d[:] = d[0:2]` on a
two-column dataset gives two `Row.tuple` results). I read every use of an
element of `_data` in the package (`core.py`, `_sql.py`):

- Explicit method calls on such an element: `row.copy()` (`core.py:290`,
  T05 to T07: `list`, `dict`, `set` are the only produced types with
  `copy`), `row.insert(...)` (`core.py:574`, `list.insert`, added; no other
  produced type has `insert`), and `row.has_tag(tag)` (`core.py:653`: no
  produced type has it, so the call raises `AttributeError` before it is
  made). `row.insert` at `core.py:465` and `81` act on lists that the
  package makes, not on `_data` elements.
- Everything else is a builtin call already in the graph (`len`, `list`,
  `tuple`, `map`, `enumerate`, `zip`, `itemgetter`) or an implicit site
  (iteration, subscription, `del`, the `.tuple` loads at `core.py:189` and
  `191`), where an outside type adds no edge and no package method can be
  reached: no produced cell is a package object.
- The formats see `_data` only through `_package`, whose `format_row`
  returns `list(row)`, through `Dataset.__getitem__` (a tuple, or a list
  for a non-Row element, `core.py:191`), or through `_sql.py:62-63`, which
  iterates the element and passes its items to `_render_literal`, whose
  calls are all `isinstance`-guarded or `str(...)`.

The same reading for bytes titles and headers (T01 to T03) finds no other
method that a produced bytes value reaches: `str(h)`, `to_str` (already
`bytes.decode`), `len`, the `re.sub` of the sheet-title helpers (the
TypeError is inside the call), `str(name).upper()` in
`DbfFieldDef.__init__`, and openpyxl's `check_string`, which decodes bytes
before `startswith` (openpyxl 2.6.0, 3.0.10, 3.1.5 `cell/cell.py`), so
`_xlsx.py:189` keeps `str.startswith` only.

No disagreement; nothing is open from Codex round 1.

## C-type names re-check

Against `4f908c7`, which applies `b8-ruling-c-type-names-1.md` (b8-gt
`3a3dcd0`). `git diff 574148b 4f908c7` changes one ledger callee
(`_csv.py:26:26`, `CSVFormat.export_stream_set`: `_csv.writer.writerow`
becomes `_csv.Writer.writerow`), the graph by that one replaced edge (1086
edges, 505 inside, 581 outside), and adds the traced `_csv.writer.writerow`
to `tablib.rejected.json` as a naming artefact (rule A); `check.py
--origin tablib` gives 880 trace edges, 14 rejected, 867 traced edges in
the graph, 219 added.

- The export lines hold. `Modules/_csv.c` makes the writer type from
  `Writer_Type_spec` and adds it as `"Writer"` with
  `PyModule_AddObjectRef` in every admitted CPython: 3.10.22 `:1719`,
  3.11.18 `:1753`, 3.12.16 `:1776`, 3.13.18 `:1760`, 3.14.10 and 3.15.2
  `:1799` (the reader type as `"Reader"` six lines earlier). tablib admits
  CPython 3.10 to 3.15 and no PyPy, so no `_csv.writer` fallback is
  needed, and none is in the graph.
- The writer's sweep holds. Of the 120 outside names in the graph, the
  receivers that are C types are named through a public alias whose
  module exports the type: `io.*` (`_io` types re-exported by `io`),
  `re.Pattern`, `re.Match`, `xml.etree.ElementTree.Element` (`from
  _elementtree import *`, `ElementTree.py:2092`),
  `functools._lru_cache_wrapper` (`from _functools import
  _lru_cache_wrapper`, `functools.py:642` in 3.10.22, `:738` in 3.15.2,
  the type's `tp_name` being the same), the `datetime` types,
  `itertools.zip_longest`, `operator.itemgetter`, and the builtins.
  `csv.writer` and `csv.reader` are factories and name their own calls;
  the reader object is only iterated (`_csv.py:46`), which is an implicit
  site with no outside edge. Every other outside name is a Python class
  or function of a library, or a missing-module path. No other name
  changes.

No disagreement; nothing is open from the C-type naming ruling.
