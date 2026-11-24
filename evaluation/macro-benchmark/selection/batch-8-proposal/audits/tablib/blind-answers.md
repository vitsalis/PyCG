# tablib: blind answers (seed 20261124)

Written from the source of tablib v3.10.0 (`b0ff39f`), the dependency
sources in `deps/` (odfpy 1.4.1), the trace `dynamic/tablib.json` and the
README's rules, before any file of the writer was opened.

## Draw

The skeleton (made in a scratch copy, without a ledger) has 2025 sites:
1129 explicit (1053 call, 76 decorator) and 896 implicit, 26 value sites.
No kind dominates (explicit 56 %; the largest implicit kind, `getattr`, is
277 sites, 14 %), so the draw is plain: `draw.py` numbers the sites by
(module in skeleton order, line, column) and takes
`random.Random(20261124).sample(range(2025), 70)`, then adds the value sites
not drawn (25 of 26; `_df.py:22:22` was drawn). 95 sites. The drawn 70:
41 call, 3 decorator, 12 getattr, 5 iter, 3 op, 2 getitem, 1 each of
mapping, setattr, setitem, truth.

## Facts used throughout

- Supported: CPython 3.10 to 3.15 (`requires-python >=3.10`, classifiers,
  `tox.ini`), Linux, macOS, Windows (`test.yml`). No PyPy.
- `tablib._vendor.*` is private (C). `Dataset._data` is always a list of
  `Row`; `Row._row` is a list; `Dataset.headers` is
  `property(_get_headers, _set_headers)` and returns a list or `None`;
  `width`, `height` are properties.
- Iterating a `Dataset` uses `__getitem__` (no `__iter__`), whose int
  branch returns `Row.tuple`, a `tuple`.
- Registered formats are classes (`load_format_class`) or instances of
  `JSONFormat`, `CSVFormat`, `TSVFormat`; their `export_set`, `import_set`
  are classmethods (builtin descriptors).
- `dbfpy.fields.lookupFor(t)` does `chr(t)`: a `str` type code raises
  `TypeError`. The package's only tuple field definitions
  (`dbf.demo_create`) carry `str` codes, so `DbfHeader._addField` never
  reaches its tuple branch's constructor call.
- Every `DbfHeader(...)` of the package passes no `fields` (`Dbf.__init__`
  with `new`, `fromStream` with `None`, `dbf_new.write`): the
  `else: list(fields)` branch never runs (B1, the argcomplete clause).
- Field classes: none overrides `__init__`, `fromString`, `toString`,
  `fieldInfo`; `DbfDateFieldDef` and `DbfDateTimeFieldDef` bind
  `defaultValue` to a `utils.classproperty`; instances of every registered
  field class come from `DbfHeader.fromStream` on a client DBF.
- Formatters (`add_formatter`) and dynamic columns are client callables
  (tests and `docs/tutorial.rst` pass local functions,
  `random.randint`); no package value is documented or tested there.
- pandas is an optional extra, not installed in the trace environment:
  a missing module (`pandas.DataFrame`).
- Outside names follow the trace where it names the class
  (`xlwt.Workbook.Workbook.add_sheet`, `odf.element.Element.*`,
  `xml.etree.ElementTree.Element.append`).

## Answers

"rej all" = every candidate rejected, for the reason given.

| # | Site | Callees | Candidates rejected, and why |
|---|---|---|---|
| 3 | `dbf.py:116:22` call `isinstance(f, str)` | `<builtin>.isinstance` | none |
| 8 | `dbf.py:125:57` call `bool(readOnly)` | `<builtin>.bool` | rej all: `readOnly` is `0`, `True` or `False` from the package's callers (`_dbf.py:41`, `:71`, `dbfnew.py:165`, `dbf.py:259`) |
| 12 | `dbf.py:132:43` value `self.HeaderClass()` | `tablib._vendor.dbfpy.header.DbfHeader.__init__` | note: `HeaderClass = header.DbfHeader` (`dbf.py:87`); reached with `new=True` (`demo_create`, `dbf.py:267`) |
| 15 | `dbf.py:135:54` value `self.HeaderClass.fromStream(...)` | `...header.DbfHeader.fromStream` | `DbfRecord.fromStream`: the class is `DbfHeader` |
| 46 | `dbf.py:207:27` value `names.index(...)` | `<builtin>.list.index` | note: `names` is a list display |
| 49 | `dbf.py:211:32` value `self.RecordClass(self)` | `...record.DbfRecord.__init__` | note: `RecordClass = record.DbfRecord` (`dbf.py:88`) |
| 56 | `dbf.py:228:34` iter `*defs` | none | rej all: `defs` is the `*args` tuple |
| 63 | `dbf.py:244:43` value `self.RecordClass.fromStream(...)` | `...record.DbfRecord.fromStream` | `DbfHeader.fromStream`: the class is `DbfRecord` |
| 92 | `dbfnew.py:3:33` getitem on a str literal | none | rej all: `str` |
| 98 | `dbfnew.py:84:24` value `self.cls(...)` | `...fields.DbfFieldDef.__init__` | note: `cls` is a `FLD_TYPES` class (`dbfnew.py:56-68`); none overrides `__init__` |
| 103 | `dbfnew.py:142:53` value `self.FieldDefinitionClass(...)` | `...dbfnew._FieldDefinition.__init__` | note: `FieldDefinitionClass = _FieldDefinition` (`:116`) |
| 119 | `dbfnew.py:166:10` call `print(repr(dbft))` (main block) | `<builtin>.print` | rej all: the argument is the `str` that `repr` returns; the block runs (`dbfn.write` and `Dbf(...)` succeed) |
| 149 | `fields.py:81:21` getattr `self.defaultValue` | `...utils.classproperty.__get__` | the two format descriptors: `defaultValue` is a plain value or a `classproperty` (`fields.py:366`, `:400`); `DbfDateFieldDef` instances come from `fromStream` and `dbfnew`'s main block; the `assert` is code (union with `-O`) |
| 155 | `fields.py:85:31` call `.upper()` | `<builtin>.str.upper` | none |
| 156 | `fields.py:86:27` getattr `self.__class__.length` | none | rej all: `length` is a plain class attribute on every field class |
| 178 | `fields.py:133:19` value `cls(...)` | `...fields.DbfFieldDef.__init__` | note: `cls` is the class `lookupFor` returns (`header.py:130`), a registered subclass; binds (6 arguments) |
| 283 | `fields.py:472:23` call `__all__.append(_name)` | `<builtin>.list.append` | `Dbf.append`, `Dataset.append`, `Row.append`: `__all__` is a list |
| 287 | `header.py:88:31` call `list(fields)` | none | rej all; note: no package call of `DbfHeader` passes `fields`, so the branch never runs (B1, every instance in one state) |
| 291 | `header.py:96:14` setattr `self.changed` | none | rej all: `changed` is a slot |
| 294 | `header.py:101:30` value `cls.fromStream(...)` | `...header.DbfHeader.fromStream` | `DbfRecord.fromStream`; note: `fromString` is never called by the package, so `cls` is `DbfHeader`; `fromStream` is entered (it fails later at `struct.unpack` on a `str`) |
| 308 | `header.py:122:19` value `cls(None, ...)` | `...header.DbfHeader.__init__` | note: `cls` is `DbfHeader` (only caller `Dbf.__init__` through `HeaderClass`) |
| 318 | `header.py:130:58` value `....fromString(_data, _pos)` | `...fields.DbfFieldDef.fromString` | `DbfHeader.fromString`, `DbfRecord.fromString`: the receiver is a field class |
| 334 | `header.py:171:25` call `"\n".join(...)` | `<builtin>.str.join` | none |
| 336 | `header.py:172:49` call `_fld.fieldInfo()` | `...fields.DbfFieldDef.fieldInfo` | none |
| 344 | `header.py:200:28` value `_cls(...)` | none | note: unreachable; `lookupFor(_type)` at `:199` raises `TypeError` on the `str` codes of the only tuple definitions (`dbf.py:268-273`) |
| 355 | `header.py:238:32` call `_fld.toString()` | `...fields.DbfFieldDef.toString` | `DbfHeader.toString`, `DbfRecord.toString`: field definitions only |
| 385 | `record.py:123:30` value `cls.fromString(...)` | `...record.DbfRecord.fromString` | `DbfFieldDef.fromString`, `DbfHeader.fromString`: `cls` is `DbfRecord` |
| 387 | `record.py:123:53` value `cls.rawFromStream(...)` | `...record.DbfRecord.rawFromStream` | none |
| 389 | `record.py:142:19` value `cls(...)` | `...record.DbfRecord.__init__` | note: `cls` is `DbfRecord`; binds (4 arguments) |
| 455 | `utils.py:29:30` value `str.index(b'\0')` | `<builtin>.bytes.index` | note: `str` is the parameter, the 32-byte `bytes` field descriptor from `fromStream` (a `str` stream fails earlier at `struct.unpack`) |
| 467 | `utils.py:71:34` iter `*time.strptime(...)[:3]` | none | rej all: a `tuple` |
| 505 | `core.py:60:18` setitem `self._row[i]` | none | rej all: `_row` is a list, `i` an int |
| 514 | `core.py:84:34` call `self._row.copy()` | `<builtin>.list.copy` | `Row.copy`: `_row` is a list |
| 521 | `core.py:104:24` call `isinstance(tag, str)` | `<builtin>.isinstance` | none |
| 532 | `core.py:172:32` call `kwargs.get('title')` | `<builtin>.dict.get` | `Dataset.get`: `kwargs` is a dict |
| 540 | `core.py:182:41` value `self.headers.index(key)` | `<builtin>.list.index` | note: `headers` is a list (`_set_headers`) |
| 542 | `core.py:183:45` iter `self._data` | none | rej all: a list |
| 552 | `core.py:199:21` getattr `self.headers` | `tablib.core.Dataset._get_headers` | the three `__get__`: the attribute is a `property` |
| 557 | `core.py:204:41` value `self.headers.index(key)` | `<builtin>.list.index` | note as 540 |
| 597 | `core.py:250:45` getattr `....export_set` | none | rej all: a classmethod of a format class |
| 635 | `core.py:294:40` value `callback(cell)` | none | note: a client formatter |
| 638 | `core.py:296:44` value `callback(row[col])` | none | note: a client formatter |
| 662 | `core.py:358:26` call `isinstance(pickle, list)` | `<builtin>.isinstance` | `Row.list`: `list` is the builtin name |
| 722 | `core.py:463:57` call `self._dynamic_columns.items()` | `<builtin>.dict.items` | none |
| 725 | `core.py:465:37` value `func(row)` | none | note: a client dynamic column |
| 746 | `core.py:554:27` call `map(col, self._data)` | `<builtin>.map` | rej all: `map` iterates a list; `col` is a client callable |
| 790 | `core.py:637:41` value `self.headers.index(col)` | `<builtin>.list.index` | note as 540 |
| 870 | `core.py:779:25` getattr `self.headers` | `tablib.core.Dataset._get_headers` | as 552 |
| 898 | `core.py:812:19` call `set()` | `<builtin>.set` | rej all: no argument |
| 922 | `core.py:847:13` iter `row_no, row` | none | rej all: the `tuple` from `enumerate` |
| 928 | `core.py:851:32` getattr `self.headers` | `tablib.core.Dataset._get_headers` | as 552 |
| 929 | `core.py:851:45` value `self.headers.index(key)` | `<builtin>.list.index` | note as 540 |
| 953 | `core.py:919:36` call `UnsupportedFormat(...)` | `<builtin>.NotImplementedError.__init__` | none; MRO `UnsupportedFormat, TablibException, NotImplementedError, ...` |
| 1003 | `formats/__init__.py:75:29` getattr `self._format.import_set` | none | rej all: a classmethod |
| 1033 | `formats/__init__.py:107:26` call `self.register(...)` | `tablib.formats.Registry.register` | none; both sides of `find_spec('yaml')` |
| 1083 | `_cli.py:17:6` decorator `@classmethod` | `<builtin>.classmethod` | none |
| 1112 | `_csv.py:45:40` mapping `**kwargs` | none | rej all: a dict |
| 1124 | `_csv.py:53:41` getattr `dset.width` | `tablib.core.Dataset.width` | none |
| 1151 | `_dbf.py:44:46` call `zip(dataset.headers, row)` | `<builtin>.zip` | rej all: `row` is the `tuple` that iterating a `Dataset` gives |
| 1165 | `_dbf.py:61:23` call `dbf.Dbf(in_stream)` | `...dbf.Dbf.__init__` | none |
| 1179 | `_df.py:22:22` value `DataFrame(stream.read())` | `pandas.DataFrame` | note: `DataFrame` is pandas' (missing module) or `None`, which returns at `:17` |
| 1183 | `_df.py:34:30` value `DataFrame(dset.dict, ...)` | `pandas.DataFrame` | note as 1179 (`None` raises at `:31`) |
| 1196 | `_html.py:24:35` getattr `dataset.headers` | `tablib.core.Dataset._get_headers` | as 552 |
| 1208 | `_html.py:37:26` call `tr.append(td)` | `xml.etree.ElementTree.Element.append` | `Dbf.append`, `Dataset.append`, `Row.append`: `tr` is an `ET.Element` |
| 1242 | `_html.py:88:57` op `==` | none | rej all: `str` or `None` against the client's `table_id` |
| 1308 | `_json.py:56:28` call `dbook.add_sheet(data)` | `tablib.core.Databook.add_sheet` | none |
| 1320 | `_latex.py:55:62` getattr `dataset.title` | none | rej all: an instance attribute |
| 1377 | `_ods.py:27:21` call `style.addElement(...)` | `odf.element.Element.addElement` | none; `number.DateStyle` returns `style.StyleElement(...)`, an `Element` (`odf/style.py:24-29`) |
| 1379 | `_ods.py:31:21` call `style.addElement(...)` | `odf.element.Element.addElement` | none |
| 1384 | `_ods.py:33:36` call `number.Minutes(...)` | `odf.number.Minutes` | none |
| 1417 | `_ods.py:89:25` call `BytesIO()` | `io.BytesIO` | none |
| 1443 | `_ods.py:118:32` iter `sheet.childNodes` | none | rej all: a list of odf nodes |
| 1485 | `_ods.py:161:46` call `cell.getAttribute('value')` | `odf.element.Element.getAttribute` | none; a `Text` node has `data` and skips the call |
| 1520 | `_ods.py:211:36` op `row_number == 1` | none | rej all: ints |
| 1550 | `_ods.py:242:43` call `table.TableCell(...)` | `odf.table.TableCell` | none |
| 1557 | `_ods.py:250:22` call `isinstance(stream, bytes)` | `<builtin>.isinstance` | none |
| 1591 | `_rst.py:54:45` call `len(text)` | `<builtin>.len` | rej all: `text` is a `str` (`to_str`) |
| 1611 | `_rst.py:82:32` value `wrapper.wrap(text)` | `textwrap.TextWrapper.wrap` | note: `wrapper` is the package's `TextWrapper()` (`:117`, `:168`) |
| 1621 | `_rst.py:89:41` call `pad.join(line)` | `<builtin>.str.join` | none (`just` belongs to its own site at `:86`) |
| 1632 | `_rst.py:101:52` call `len(median_lens)` | `<builtin>.len` | rej all: a list |
| 1637 | `_rst.py:108:29` call `max(w, l)` | `<builtin>.max` | rej all: ints |
| 1649 | `_rst.py:124:25` call `lines.extend(...)` | `<builtin>.list.extend` | `Dataset.extend`: `lines` is a list |
| 1688 | `_rst.py:187:25` call `lines.append(row_sep)` | `<builtin>.list.append` | rej all: a list |
| 1698 | `_rst.py:214:6` decorator `@classmethod` | `<builtin>.classmethod` | none |
| 1716 | `_rst.py:256:24` getattr `cls.export_set_as_simple_table` | none | rej all: a classmethod |
| 1798 | `_xls.py:84:30` call `wb.add_sheet(...)` | `xlwt.Workbook.Workbook.add_sheet` | `Databook.add_sheet`: `wb` is an `xlwt.Workbook` (naming: the trace's defining-module path) |
| 1801 | `_xls.py:86:20` truth `dset.title` | none | rej all: a client `str` or `None` |
| 1816 | `_xls.py:110:23` call `range(sheet.nrows)` | `<builtin>.range` | none |
| 1857 | `_xls.py:158:23` op `i == 0` | none | rej all: ints |
| 1930 | `_xlsx.py:124:46` getattr `dset.width` | `tablib.core.Dataset.width` | none |
| 1931 | `_xlsx.py:124:57` call `len(row_vals)` | `<builtin>.len` | rej all: a list |
| 1951 | `_xlsx.py:157:33` getitem `sep[0]` | none | rej all: a `(index, text)` tuple |
| 1999 | `_yaml.py:15:6` decorator `@classmethod` | `<builtin>.classmethod` | none |
| 2013 | `_yaml.py:49:34` call `tablib.Dataset()` | `tablib.core.Dataset.__init__` | none |
| 2018 | `_yaml.py:52:28` call `dbook.add_sheet(data)` | `tablib.core.Databook.add_sheet` | none |

Two non-edges that a reader of names alone would give: `header.py:88:31`
(`<builtin>.list`) and `header.py:200:28` (`DbfFieldDef.__init__`).
