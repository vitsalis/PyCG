# tablib: judgements of the ground truth

Status (writer, batch 8, 2026-11-24): complete. `check.py --write tablib`
and `check.py tablib` report no error; every site is decided; every
missing trace edge is in the graph or in `tablib.rejected.json` (16
edges, two of them `lru_cache` wrapper spellings since the Corrections of
2026-11-25). The blind audit (`tablib.audit.md`, 95 of 95 sites agree, four
findings) and the lead's rulings (2026-11-24) are applied: see "Audit"
at the end of this file. Codex round 1: T01 to T07 applied (+7 edges),
T08 ruled by the lead: no edge ("Codex round 1").

Release v3.10.0 (commit `b0ff39f`). Analysed source: `src/tablib/` (root
`src`): 28 modules, 276 functions (13 lambdas), 46 classes; the vendored
`tablib/_vendor/dbfpy/` is part of the package. `tablib/_version.py` is
written at build time and absent from the checkout: `__init__.py:5-10`
takes the `except ImportError` branch, which calls nothing.

The ledger is `tablib.ledger`; `tablib.json` and `tablib.added.json` are
generated from it. 1086 edges (505 inside, 581 outside); 865 confirmed by
the trace, 221 from reading; 1440 ledger entries; 26 value sites; 13
default rejection lines (26 candidates, 4233 candidate-site pairs); no
exclusion.

## Supported versions, implementations and platforms

- `pyproject.toml`: `requires-python = ">=3.10"`; classifiers CPython
  3.10 to 3.15 (`Programming Language :: Python :: 3.15`), no
  implementation classifier and no OS classifier. The test job
  (`.github/workflows/test.yml`) runs CPython 3.10 to 3.15
  (`allow-prereleases`) on `ubuntu-latest`, `macOS-latest` and
  `windows-latest`. So CPython 3.10 and later on Linux, macOS and Windows
  (the platform test jobs establish support, README "Rulings for batch 7",
  textdistance); no PyPy (no declaration).
- The package has no version or platform branch. Library behaviour that
  differs between the admitted versions: `tuple()` of a non-sequence calls
  `__len__` for its length hint on CPython 3.10 to 3.13
  (`Objects/abstract.c`, `PySequence_Tuple`) and not on 3.14 and later;
  `list()`, `sorted()` and `str.join` call it on every admitted version
  (`Objects/listobject.c`). So `tuple(row)` on a `Row`
  (`core.py:814`) has `Row.__len__` (not in the 3.14 trace).
- `__lazy_modules__` (PEP 810, CPython 3.15) makes some imports lazy; an
  import adds no edge, and the module code that a reified import runs
  keeps its edges in the module's node, as without it.
- `-O`: the asserts of `fields.py:80-81, 131, 408, 428` call
  `classproperty.__get__` and `len`; the graph is the union of normal and
  optimized execution.
- Optional dependencies (`[project.optional-dependencies]`): odfpy,
  openpyxl `>=2.6.0`, pandas, pyyaml, tabulate, xlrd, xlwt, all admitted;
  `register_builtins` registers a format when `find_spec` finds its
  library, so every built-in format counts, also `df` (pandas, not in the
  trace environment). Both sides of an optional import run
  (`_df.py:4-7`). Every release that satisfies a declared requirement
  and runs on CPython 3.10 to 3.15 is admitted (README, "Rulings for batch
  7", "Which releases of a dependency are admitted"; the lead's ruling of
  2026-11-24 on F4). The callee names are read from the sources in the
  shared `deps/pypi`, sampled by the lead's rule (the floor, or the oldest
  release that runs on 3.10, and the last release of each minor series;
  `MANIFEST.json` gives the reasons): openpyxl 2.6.0, 2.6.4, 3.0.10, 3.1.5;
  xlrd 1.2.0, 2.0.2; xlwt 1.0.0, 1.1.2, 1.2.0, 1.3.0; odfpy 1.3.0, 1.3.6,
  1.4.1; PyYAML 5.1, 5.1.2, 5.2, 5.3.1, 5.4.1, 6.0.3; tabulate 0.4.2,
  0.4.4, 0.5.1, 0.6, 0.7.7, 0.8.10, 0.9.0, 0.10.0. openpyxl 2.6.x and 3.0.10
  run on 3.10: their `descriptors/slots.py` uses `collections.Callable`,
  but no module of theirs imports it (it does not even import
  `collections`). The only name that differs is `get_column_letter`
  (below, "Callees outside the package"). pandas is not installed and has
  no source here: its calls use missing-module names (README, "Callees
  outside the package").

## Values and architecture, as the ledger uses them

- **Dataset and Row.** `Dataset._data` is a list of `Row`s (made
  in `__init__`, `__setitem__`, `insert`, `insert_col`, `subset`, and
  kept by `filter`, `stack`, `remove_duplicates`). A slice assignment through
  `Dataset.__setitem__` (`d[:] = d[0]`) stores the items of the new Row
  instead: cells, such as the lists, dicts and sets that `yaml.safe_load`
  makes, which then reach `row.copy()` (`core.py:290`) and
  `row.insert(...)` (`core.py:574`; Codex round 1 T04 to T07). `Row` is private: its
  docstring says "Internal Row object" (C; the pymysql ruling of batch 7),
  so its parameters are what the package passes; the tests' direct calls
  of `Row` do not widen them. A Row reaches `Dataset.insert` (and so
  `_validate`, `len(row)`, `list(row)` and `Row(row)`) from `_set_dict`,
  `_transpose_with_headers` and `subset`. `Dataset` has no `__iter__`:
  iterating a Dataset calls `Dataset.__getitem__` until `IndexError`
  (`for row in dataset` in the html, jira, latex and dbf formats;
  `list(tabular_data)` in tabulate). `Row` has `__iter__`, so iterating a
  Row never calls `Row.__getitem__`. `headers` is the property
  `_get_headers`/`_set_headers` (`core.py:324`), `dict` the property
  `_get_dict`/`_set_dict` (`core.py:378`); `title` is a plain attribute.
- **Client values.** Cells, headers (documented as strings, `core.py:145`),
  titles (strings), tags, the handlers of `add_formatter` and the
  callables of `insert_col` are client values (B5): the handlers and
  callables are value sites without callee (`core.py:294`, `296`, `465`).
- **J3. The format registry.** `Registry._formats` maps each key to a
  format object: `JSONFormat()`, `CSVFormat()`, `TSVFormat()` instances,
  and the classes that `load_format_class` imports from their dotted
  paths. The format methods are classmethods (and one staticmethod), so
  the receiver is the class in both cases. `Registry.register` sets an
  `ImportExportBookDescriptor` on `Databook` and an
  `ImportExportSetDescriptor` on `Dataset` for each key, and the
  partialmethods `Dataset.get_<key>` and `set_<key>`. Every dispatch site
  (`Dataset._get_in_format`, `_set_in_format`, `load`, `export`,
  `Databook.load`, `export`, `detect_format` and the four descriptor
  methods) has as callees the method of that name of every built-in
  format that defines it; a format without it raises `AttributeError` or
  the package's `UnsupportedFormat`. A client's registered format is
  client code. The format classes are reached through the public
  `tablib.formats.registry` (documented, `docs/development.rst:96-138`),
  `Dataset.export(**kwargs)` forwards to `export_set`, and the
  documentation points to `tablib.formats._xlsx.XLSXFormat.export_set` for
  its parameters (`docs/formats.rst:287`): their non-underscore methods
  are judged as public. TSVFormat inherits every method of CSVFormat.
  The descriptors' only package load is `dset.html` (`_html.py:53`),
  which the site finder does not see (the attribute is bound by
  `setattr`): added by hand.
- **Streams.** `normalize_input` turns a str into `io.StringIO` and bytes
  into `io.BytesIO`; any other value passes unchanged.
- **The dbf format** writes through the vendored dbfpy: `dbf_new` with
  character and numeric fields, `Dbf(path, readOnly=0)` (`open(path,
  "r+b")`, a `BufferedRandom`), `DbfRecord` and `store`; it reads with
  `Dbf(stream)`, which parses the header (`DbfHeader.fromStream`) and
  decodes records with the field class that the file's type code selects
  (any of the nine registered field classes).

## Default rejections

Thirteen lines, 26 candidates (`check.py --report tablib` gives the
sites): the five `__getitem__` (Dbf, DbfHeader, DbfRecord, Dataset, Row),
`Row.__iter__`, the three descriptor `__get__`, the two `__eq__` of
`DbfFieldDef` and `_InvalidValue`, the three `__len__`,
`DbfFieldDef.__hash__`, `_InvalidValue.__bool__`, the eight `__repr__`
and the two `__str__`. Each reason names the operands of the sites, and
each site that does subscript, iterate, measure, test or format such an
object accepts the candidate in its entry; the implicit sites among them
were taken from the skeleton made without the defaults. The explicit sites
under each default were read in the report.

## Judgement calls

**J1. Documented file streams (14 outside edges, 2 of them traced;
confirmed by the lead after the audit, narrowed by F3).** The stream
inputs (`Dataset.load`, `Databook.load`, `import_set`, `import_book`,
`detect_format`) are documented as "a file-like object, a string, or a
bytestring" (`core.py:416`, `908`, `938`, `955`, `961`), and the tutorial
passes `open('data.csv', 'r')` and `open('my_excel_file.xlsx', 'rb')` to
`Dataset.load` (`docs/tutorial.rst:109`, `118`, `335`). The ledger reads
"file-like object" through these documented examples for `Dataset.load`
and what it forwards the stream to: an `io.TextIOWrapper` and an
`io.BufferedReader` are admitted there, so `stream.read`, `stream.seek`
and `in_stream.read` have these names besides `StringIO` and `BytesIO`
(`core.py:950`, `_csv.py:60`, `_xls.py:43`, `127`, `_df.py:22`,
`_html.py:64`, `header.py:107-108`). `Databook.load` has the abstract
phrase but no example, and documentation is read one entry at a time
(B4, funcy): no file class reaches `XLSFormat.import_book`
(`_xls.py:138`; F3, the lead's ruling), and its traced
`_io.BufferedReader.read` (from tests that pass `Path.open('rb')` to
`Databook.load`) is a rejected trace edge. Any other client stream is
opaque (B5).

**J2. A pandas DataFrame as a stream (8 outside edges).** The df format
imports a DataFrame (`docs/formats.rst`, "df"), `DataFrameFormat.detect`
handles one explicitly (`_df.py:19`), and the tests pass the DataFrame of
`export('df')` to `detect_format` (`tests/test_tablib.py:427-428`). So a
DataFrame is admitted at `Dataset.load`, `detect_format` and the `df`
setters, and, by the combination of admitted values (django-environ
ruling), reaches every detector and every set importer. pandas is not
installed: the calls on it use missing-module names (micro-benchmark
"Missing modules"): `pandas.DataFrame.seek` (`core.py:950`,
`header.py:107`), `pandas.DataFrame.read` (`header.py:108`,
`_csv.py:60`, `_xls.py:43`, `127`, `_html.py:64`),
`pandas.DataFrame.to_dict` (`_df.py:41`). A real DataFrame has no `read`
or `seek`; the missing-module convention fixes the names and lets the
library's answer decide both ways (dagster-pipes keeps
`….download_blob.readall.decode`). No DataFrame reaches `Databook.load`
(nothing documents or tests one there; one parameter's admitted values do
not pass to another, pymysql ruling). The alternative (no edge where
pandas has no such method) removes the seven `read`/`seek` edges.

**J4. The vendored dbfpy (`tablib._vendor`, private).** Its functions
take the values of the package's own calls; an uncalled one is judged as
public with the objects that the package can make. Findings, each
recorded at its sites:
- The package callers: `DBFFormat.export_set` (character and numeric
  fields, a `BufferedRandom`), `DBFFormat.import_set` and `detect`
  (StringIO, BytesIO, the J1 files, a DataFrame; `detect` with a str
  opens it `"rb"`), and the `__main__` blocks of `dbf.py` and `dbfnew.py`,
  which are module code (README, "Edges").
- `demo_create` always raises in `_dbf.addField`: `DbfHeader._addField`
  calls `fields.lookupFor("C")`, and `chr("C")` raises `TypeError`
  (`fields.py:464`). The rest of `demo_create` and the call
  `demo_read(_name)` of `dbf.py:295` are unreachable; `demo_read` is
  judged as public (`Dbf(filename, True)` opens `"rb"`).
- dbfnew's `__main__` block stops at `dbft[i1]` (`dbfnew.py:184`): the
  date field holds `b"20000112"`, and `getDate` of bytes calls
  `datetime.date(*date[:3])`, that is `date(50, 48, 48)`, which raises
  `ValueError` (`utils.py:76`). Lines 185-188 are unreachable.
- Every record is bytes (a text stream fails at `struct.unpack`,
  `header.py:112`, before any record is read), so
  `DbfLogicalFieldDef.decodeValue` always raises at `value in "NnFf "`
  (bytes in str) and its `ValueError` is unreachable.
- `store` always appends (every stored record has index None), so its
  `self.dbf[...] = self` (`record.py:216`) is unreachable and
  `Dbf.__setitem__` is never called; judged as public, it writes any
  record that the package makes, also one read from a BytesIO or a binary
  file, so `DbfRecord._write` has `BytesIO` and `BufferedReader` `seek`
  and `write` (a BufferedReader refuses the write in its body), and
  `toString` reaches the `encodeValue` of every field class (8 edges).
- `utils.getDate` gets None, a tuple, bytes or a date; `getDateTime` gets
  a datetime only (from `DbfDateTimeFieldDef.encodeValue`, after its truth
  test). Their other branches are unreachable, and the nine trace edges
  that the tests' direct calls of these private functions make (int, str,
  None, a date) are rejected (`tablib.rejected.json`, rule A).
- Other unreachable raises: `Dbf.addField`'s `TypeError` (`_new` is
  true), `_FieldDefinition`'s `ValueError` (a length is always passed),
  `DbfFieldDef.__init__`'s `ValueError` at `fields.py:88`,
  `_validateIndex`'s `ValueError`s at `record.py:194` and `198`,
  `DbfHeader.__init__`'s `list(fields)` (fields is always None).
  `_validateIndex`'s `ValueError` at `record.py:196` runs (F2): through
  `Dbf.__setitem__`, `_fixIndex` adds `len(self) + 1` to a negative
  index and checks only the upper bound, so `-10` on an empty table
  becomes `-9`.
The alternative (the tests' direct calls admit their values) keeps the
nine rejected edges; the alternative for `Dbf.__setitem__` (no admitted
record) removes 4 `_write` edges and 5 `encodeValue` edges.

**J5. INVALID_VALUE never leaves dbfpy.** Every `Dbf` of the package has
`ignoreErrors` False (`Dbf.__init__` sets it from its default, and the
setters copy it to the header and the fields), so `decodeFromRecord`
re-raises and never returns `INVALID_VALUE`; no package code compares,
converts or formats it (default rejections; `record.py:155` is
unreachable). `_InvalidValue.__eq__` is never called by the package; its
`other` is judged as public, and the class docstring names
`INVALID_VALUE` itself as an operand ("not equal to anything except for
itself"), so `not other` calls `_InvalidValue.__bool__` (1 edge, traced).

**J6. Cells that the importers make (2 outside edges).**
`serialize_objects_handler` (`_json.py:17`) calls `obj.isoformat()` on a
cell that `json` cannot serialize. Client cells are opaque, but the
package's importers put datetimes (xlrd's `xldate_as_datetime`,
openpyxl, odfpy), dates (odfpy, dbf) and times (odfpy, openpyxl) into a
Dataset: `datetime.datetime.isoformat` (traced), `datetime.date.isoformat`
and `datetime.time.isoformat`.

**J7. `Databook.__repr__`.** No package code, document or test sets a
title on a `Databook`, so `self.title` raises `AttributeError` before
`.lower()` (`core.py:871`): no edge.

**J8. `Registry.register`'s `except AttributeError`.** Formatting a client
str subclass key can raise `AttributeError` (B5, client control flow), so
line 94 runs; its pairs are those of lines 91 and 92.

**J9. `_row_to_lines` validates `justify`** (`_rst.py:63`), but it is
private and the package passes `JUSTIFY_LEFT` or `JUSTIFY_CENTER` only
(`_rst.py:124-134`, `177-186`): the `ValueError` is unreachable, and so is
the `rjust` branch of the closure `just` (`_rst.py:74`; F1).

## Callees outside the package

- Streams by class: `io.StringIO`, `io.BytesIO`, `io.TextIOWrapper`,
  `io.BufferedReader` (J1), `io.BufferedRandom` (`open(..., "r+b")`),
  `io.BufferedWriter` (`open(..., "wb")`).
- Re-exports without `__all__` are named where they are defined:
  `xlwt.Style.easyxf`, `xlwt.Workbook.Workbook` (and its `add_sheet`,
  `save`), `xlwt.Worksheet.Worksheet.write`,
  `openpyxl.workbook.workbook.Workbook` (`save`, `remove`,
  `create_sheet`), `openpyxl.styles.fonts.Font`,
  `openpyxl.styles.alignment.Alignment`, `xlrd.book.Book.sheet_by_index`,
  `sheets`, `xlrd.sheet.Sheet.row_values`, `row_types`. `xlrd.open_workbook`
  and `xlrd.xldate.xldate_as_datetime` are defined where they are
  imported.
- `get_column_letter` (`_xlsx.py:165`, `218`) is a `functools.lru_cache`
  wrapper in openpyxl 3.1.5 (`utils/cell.py:78`):
  `_functools._lru_cache_wrapper.__call__`; in openpyxl 2.6.0, 2.6.4 and
  3.0.10 it is a plain function (`utils/cell.py:107`, `107`, `105`),
  re-exported by `openpyxl.utils` without `__all__`:
  `openpyxl.utils.cell.get_column_letter`. Both names (README, a plain
  function on one admitted release and a wrapper object on another,
  fastjsonschema; F4).
- The other names are the same in every sampled release: openpyxl's
  `ExcelReader.read_manifest`, `load_workbook`, `Workbook` and its
  methods, `Font`, `Alignment` (no metaclass `__call__`); xlrd 1.2.0's
  `open_workbook`, `xldate.xldate_as_datetime`, `book.Book` and
  `sheet.Sheet` (its xlsx reader also makes a `book.Book` and
  `sheet.Sheet`); xlwt 1.0.0 to 1.2.0's `__init__.py` re-exports the same
  names without `__all__`; odfpy 1.3.0 and 1.3.6 have the same factories,
  `Element`, `Node`, `Childless`, `Text` and the same loader; PyYAML 5.x
  defines `safe_dump` and `safe_load` in `yaml/__init__.py`; tabulate is
  the function `tabulate.tabulate` in every release (a module up to 0.8.10,
  a package from 0.9.0).
- odfpy's element factories are functions (`odf.style.Style`,
  `odf.number.DateStyle`, `odf.table.TableCell`, `odf.text.P`, ...) that
  return `odf.element.Element`; its methods are named through `Element`
  (`addElement`, `getAttribute`, `hasChildNodes`). A text node between
  the cells of a row (odfpy's loader adds the whitespace text, `load.py:69-72`)
  makes `is_real_cell` call `odf.element.Text.hasChildNodes` (`_ods.py:116`).
- The csv writer object is named by the type attribute that `_csv`
  exports: `_csv.Writer.writerow` (CPython 3.10 to 3.15 export `Writer`,
  `Modules/_csv.c`: 3.10.22 `:1719`, 3.14.10 and 3.15.2 `:1799`; the
  referee's ruling on C-type names, `b8-ruling-c-type-names-1.md`;
  tablib admits no runtime without that export, so no `_csv.writer`
  fallback). `csv.writer` and `csv.reader` are factories and name their
  own call; `_csv` also exports `Reader` (`:1713`, `:1793`), but no
  tablib site calls a method of a reader object (`CSVFormat.import_set`
  only iterates it). No other outside name of the ledger is a C type
  named by a `tp_name` that differs from its exported attribute.
- Exceptions: a package exception called explicitly names the `__init__`
  of its nearest builtin base (`<builtin>.AttributeError.__init__` for
  `HeadersNeeded`, `<builtin>.NotImplementedError.__init__` for
  `UnsupportedFormat`); a `raise` without a call adds no edge (three
  rejected trace edges).
- `os.close`, `os.remove` (the module imported), `struct.pack`,
  `struct.unpack`, `<builtin>.property.__init__` for the `classproperty`
  objects (a package subclass of `property` without `__init__`).
- pandas (missing module): `pandas.DataFrame`, `pandas.DataFrame.to_dict`,
  `.read`, `.seek` (J2).
- Callbacks: `json.dumps` calls `serialize_objects_handler`,
  `re.Pattern.sub` calls `_escape_tex_reserved_symbols.replace`,
  `HTMLParser.feed` calls the parser's three handlers, tabulate calls
  `Dataset.__len__` and `Dataset.__getitem__` (`list(tabular_data)` from
  0.6 on: 0.10.0 `__init__.py:1539`, 0.9.0 `:1379`, 0.8.10 `:1154`,
  0.7.7 `:749`, 0.6 `:423`; 0.5.1 keeps the Dataset as rows and calls
  `len(rows)`, `rows[0]` and `map(list, rows)`, `tabulate.py:408-413`;
  0.4.2 and 0.4.4 unpack it with `zip(*list_of_lists)`, whose tuple takes
  the length hint on 3.10 to 3.13), `map(str, row)` calls `Row.__iter__`.

## Open path sets

None.

## Rejected trace edges

`tablib.rejected.json`, 16 edges (two `lru_cache` wrapper spellings in the
Corrections of 2026-11-25), the others:
- 9 from the tests' direct calls of the private `utils.getDate` (int,
  str) and `utils.getDateTime` (None, date, int, str): private input
  (J4).
- `CSVFormat.export_stream_set -> _csv.writer.writerow`: a naming
  artefact of the trace (the ground truth has `_csv.Writer.writerow`,
  the referee's ruling on C-type names).
- `XLSFormat.import_book -> _io.BufferedReader.read`: a client stream of
  `Databook.load`, which documents no file class (J1, F3).
- 3 `<builtin>.BaseException.__init__` edges of `raise InvalidDimensions`
  (`core.py:278`, `566`) and `raise InvalidDatasetType` (`core.py:887`)
  without a call: implicit calls outside the package.

## Notes for the auditor

- Bugs of the release that remove no traced edge: `DbfLogicalFieldDef`
  cannot decode (bytes in str); a date field of a dbf file cannot be
  decoded unless its bytes happen to be a valid (year, month, day); a
  dbf `D` field is never written by tablib (only `C` and `N`);
  `DbfRecord.__setitem__` with an int key returns without storing;
  `DbfRecord.fromString` compares `string[0]` (an int) with `"*"`, so a
  deleted flag is never read; `fromStream`'s `bytes(first_32, ...)` is
  dead (overwritten on the next line); `Databook.__repr__` always takes
  its fallback.
- Surprising non-edges: no `Dataset.__iter__` exists; `Row.__getitem__`
  is never reached by iteration; `_InvalidValue` methods are unreachable
  from the package except `__eq__ -> __bool__` (J5); the descriptors'
  `__get__` is reached by the package only at `_html.py:53`.
- `Dataset.insert` reaches `list(row)` with a Row when a dataset with a
  dynamic column gets a shorter row through `Dataset.dict` (`wipe` keeps
  `_dynamic_columns`, `core.py:817-820`): the witness of
  `Dataset.insert -> Row.__iter__`.

## Statistics

`check.py tablib`: 1086 edges (505 inside, 581 outside); the trace
confirms 865 of 1086 (79.7%); 227 of 276 functions run (82.2%); 16
rejected.

`check.py --origin tablib`:

| Project | Trace edges | Rejected | Traced edges in the graph (inside / outside) | Added (inside / outside) | Graph edges (inside / outside) |
| --- | --- | --- | --- | --- | --- |
| tablib | 880 | 16 | 865 (397 / 468) | 221 (108 / 113) | 1086 (505 / 581) |

## Audit

The blind audit (`tablib.audit.md`, 95 of 95 sites agree) had four
findings; the lead ruled after the auditor's opinion (2026-11-24) and
confirmed J1 (for `Dataset.load` and what it forwards to), J2 and J3.

- F1 (applied, -1 outside): `ReSTFormat._row_to_lines.just ->
  <builtin>.str.rjust` removed (J9).
- F2 (applied, +1 outside): `DbfRecord._validateIndex ->
  <builtin>.ValueError` at `record.py:196:29` (J4).
- F3 (applied, -2 outside, +1 rejected): `XLSFormat.import_book ->
  io.BufferedReader.read` and `io.TextIOWrapper.read` at `_xls.py:138:67`
  removed (J1).
- F4 and the former open question O1 (applied, +2 outside): the admitted
  dependency releases were fetched into `deps/pypi` and every outside
  name of the ledger was read against them (see "Supported versions");
  `openpyxl.utils.cell.get_column_letter` added at `_xlsx.py:165:44` and
  `218:58`.

## Codex round 1

`selection/batch-8-proposal/codex-audits/round-1/tablib.md`: 7 missing
edges (1 inside, 6 outside) and 1 ruling question. Each was checked
against the source, the dependency sources and the rules.

- T01 (applied, +1 outside): `Dataset.__repr__ -> <builtin>.bytes.lower`
  (`core.py:220:40`). PyYAML's `SafeConstructor.construct_yaml_binary`
  (registered for `tag:yaml.org,2002:binary`, PyYAML 5.1 to 6.0.3)
  makes bytes, and `YAMLFormat.import_book` stores the title unchanged
  (`_yaml.py:50`): a value that the importer makes (B2, B4; as J6).
- T02 (applied, +1 outside): `_max_word_len -> <builtin>.bytes.split`
  (`_rst.py:29:49`). A mapping keyed by a `!!binary` key becomes the
  headers in `_set_dict` (`core.py:372`), which `_rst.py:46` passes on.
- T03 (applied, +1 outside): `Dbf.indexOfFieldName ->
  <builtin>.bytes.upper` (`dbf.py:207:38`). The same bytes header reaches
  `record[fieldname]` in `DBFFormat.export_set` (`_dbf.py:45`) and
  `DbfRecord.__setitem__` (`record.py:262`); `name.upper()` runs before
  `names.index` fails.
- T04 (applied, +1 inside): `Dataset.__setitem__ -> Row.__iter__`
  (`core.py:195:19`). A slice key is a client value of the public
  `__setitem__`; the list's slice assignment calls `PySequence_Fast`,
  which takes `iter()` of the Row before it makes a list of the iterator
  (`Objects/abstract.c`, `listobject.c`, CPython 3.10.22 and 3.14.10):
  no `Row.__len__`.
- T05 to T07 (applied, +3 outside): `format_row -> <builtin>.list.copy`,
  `dict.copy`, `set.copy` (`core.py:290:31`). After `d[:] = d[0]` on a
  dataset loaded from YAML whose one cell is a list, dict or set
  (`construct_yaml_seq`, `construct_yaml_map`, `construct_yaml_set`),
  `_data` holds that cell, and a formatter makes `format_row` copy it.
  The invariant "`_data` holds only Rows" in this file and in the ledger
  notes is corrected; the same witness adds `<builtin>.list.insert` at
  `core.py:574:27` (a pair the graph already has from `568:32`).
- T08 (lead ruling, Codex round 1: no edge): whether
  `registry.register('title', ...)` admits a package descriptor at
  `Dataset.title`, so that `Dataset.__init__` (`core.py:172:14`) calls
  `ImportExportSetDescriptor.__set__`. The lead adopted the writer's
  reasoning: a registry key names a new format; a key that collides with
  an existing attribute of `Dataset` or `Databook` replaces package
  internals, which B3 and the rule on changes of package internals
  exclude; batch 6's ruling on state changed through a public method
  admits documented effects only.

## The referee's ruling on C-type names (2026-11-24)

`b8-ruling-c-type-names-1.md` (adopted by the lead): an explicit
outside-method edge names a C type by the attribute that its module
exports, per admitted runtime. tablib: `CSVFormat.export_stream_set ->
_csv.writer.writerow` becomes `_csv.Writer.writerow` (`_csv.py:26:26`;
1 edge replaced, the count unchanged). The trace names the type by its
`tp_name`, `_csv.writer`, and lists no alias `_csv.Writer` for the
method: that traced edge is now a rejected trace edge (a naming artefact,
rule A; `tablib.rejected.json`).

## Corrections of 2026-11-25

The referee's `ruling-lru-3.md` (adopted by the lead; README, "Rulings for
the corrections of 2026-11-25") names a call of an `lru_cache` wrapper on
CPython through the type that `_functools` exports: `functools` imports
`_lru_cache_wrapper` from `_functools` without listing it in `__all__`
(CPython 3.10.22 `Lib/functools.py:12`, `:642`; 3.12.16 `:645`; 3.15.2
`:738`), a private re-export that establishes no public class path, and
`_functools` exports the type under that attribute
(`Modules/_functoolsmodule.c`, 3.10.22 `:1462`, type name
`functools._lru_cache_wrapper` at `:1419`; 3.15.2 `:1969`, `:1908`).
`functools._lru_cache_wrapper.__call__` becomes
`_functools._lru_cache_wrapper.__call__` here (outside; edge count
unchanged):

| Caller | Site |
|---|---|
| `tablib.formats._xlsx.XLSXFormat.dset_sheet` | `src/tablib/formats/_xlsx.py:165:44` |
| `tablib.formats._xlsx.XLSXFormat._adapt_column_width` | `src/tablib/formats/_xlsx.py:218:58` |

The trace names the type by its facade qualname, so its 2 pairs `caller ->
functools._lru_cache_wrapper.__call__` are rejected as naming artefacts in
`tablib.rejected.json` (rule A).
