Audited **tablib, round 1**: all 276 functions, including 13 lambdas,
and all 28 module bodies. Checked all 1,079 existing graph edges.

The read-only checker reports zero undecided sites and zero unaccounted
trace edges. No package code was executed or imported.

Function names below omit the common `tablib.` prefix. Counts are distinct
outgoing edges in the existing graph, before the findings.

| Function read | Edges checked |
|---|---:|
| `_vendor.dbfpy.dbf.Dbf.<lambda1>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.<lambda2>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.<lambda3>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.<lambda4>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.<lambda5>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.<lambda6>` | 0 |
| `_vendor.dbfpy.dbf.Dbf.__getitem__` | 2 |
| `_vendor.dbfpy.dbf.Dbf.__init__` | 7 |
| `_vendor.dbfpy.dbf.Dbf.__len__` | 1 |
| `_vendor.dbfpy.dbf.Dbf.__repr__` | 2 |
| `_vendor.dbfpy.dbf.Dbf.__setitem__` | 2 |
| `_vendor.dbfpy.dbf.Dbf._fixIndex` | 5 |
| `_vendor.dbfpy.dbf.Dbf.addField` | 1 |
| `_vendor.dbfpy.dbf.Dbf.append` | 1 |
| `_vendor.dbfpy.dbf.Dbf.close` | 3 |
| `_vendor.dbfpy/dbf.Dbf.flush` | 4 |
| `_vendor.dbfpy.dbf.Dbf.ignoreErrors` | 2 |
| `_vendor.dbfpy.dbf.Dbf.indexOfFieldName` | 2 |
| `_vendor.dbfpy.dbf.Dbf.newRecord` | 1 |
| `_vendor.dbfpy.dbf.demo_create` | 2 |
| `_vendor.dbfpy.dbf.demo_read` | 6 |
| `_vendor.dbfpy.dbfnew._FieldDefinition.__init__` | 0 |
| `_vendor.dbfpy.dbfnew._FieldDefinition.appendToHeader` | 2 |
| `_vendor.dbfpy.dbfnew._FieldDefinition.getDbfField` | 1 |
| `_vendor.dbfpy.dbfnew.dbf_new.__init__` | 0 |
| `_vendor.dbfpy.dbfnew.dbf_new.add_field` | 2 |
| `_vendor.dbfpy.dbfnew.dbf_new.write` | 6 |
| `_vendor.dbfpy.fields.DbfCharacterFieldDef.decodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfCharacterFieldDef.encodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfCurrencyFieldDef.decodeValue` | 1 |
| `_vendor.dbfpy.fields.DbfCurrencyFieldDef.encodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfDateFieldDef.<lambda1>` | 1 |
| `_vendor.dbfpy.fields.DbfDateFieldDef.decodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfDateFieldDef.encodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfDateTimeFieldDef.<lambda1>` | 1 |
| `_vendor.dbfpy.fields.DbfDateTimeFieldDef.decodeValue` | 4 |
| `_vendor.dbfpy.fields.DbfDateTimeFieldDef.encodeValue` | 4 |
| `_vendor.dbfpy.fields.DbfFieldDef.__eq__` | 2 |
| `_vendor.dbfpy.fields.DbfFieldDef.__hash__` | 1 |
| `_vendor.dbfpy.fields.DbfFieldDef.__init__` | 6 |
| `_vendor.dbfpy.fields.DbfFieldDef.__lt__` | 2 |
| `_vendor.dbfpy.fields.DbfFieldDef.__ne__` | 2 |
| `_vendor.dbfpy.fields.DbfFieldDef.__repr__` | 1 |
| `_vendor.dbfpy.fields.DbfFieldDef.decodeFromRecord` | 9 |
| `_vendor.dbfpy.fields.DbfFieldDef.decodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfFieldDef.encodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfFieldDef.fieldInfo` | 0 |
| `_vendor.dbfpy.fields.DbfFieldDef.fromString` | 4 |
| `_vendor.dbfpy.fields.DbfFieldDef.rawFromRecord` | 0 |
| `_vendor.dbfpy.fields.DbfFieldDef.toString` | 2 |
| `_vendor.dbfpy.fields.DbfIntegerFieldDef.decodeValue` | 1 |
| `_vendor.dbfpy.fields.DbfIntegerFieldDef.encodeValue` | 2 |
| `_vendor.dbfpy.fields.DbfLogicalFieldDef.decodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfLogicalFieldDef.encodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfMemoFieldDef.decodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfMemoFieldDef.encodeValue` | 0 |
| `_vendor.dbfpy.fields.DbfNumericFieldDef.decodeValue` | 3 |
| `_vendor.dbfpy.fields.DbfNumericFieldDef.encodeValue` | 3 |
| `_vendor.dbfpy.fields.lookupFor` | 1 |
| `_vendor.dbfpy.fields.registerField` | 0 |
| `_vendor.dbfpy.header.DbfHeader.<lambda1>` | 0 |
| `_vendor.dbfpy.header.DbfHeader.<lambda2>` | 0 |
| `_vendor.dbfpy.header.DbfHeader.<lambda3>` | 0 |
| `_vendor.dbfpy.header.DbfHeader.<lambda4>` | 0 |
| `_vendor.dbfpy.header.DbfHeader.__getitem__` | 3 |
| `_vendor.dbfpy.header.DbfHeader.__init__` | 3 |
| `_vendor.dbfpy.header.DbfHeader.__repr__` | 2 |
| `_vendor.dbfpy.header.DbfHeader._addField` | 4 |
| `_vendor.dbfpy.header.DbfHeader.addField` | 2 |
| `_vendor.dbfpy.header.DbfHeader.fromStream` | 20 |
| `_vendor.dbfpy.header.DbfHeader.fromString` | 3 |
| `_vendor.dbfpy.header.DbfHeader.ignoreErrors` | 1 |
| `_vendor.dbfpy.header.DbfHeader.setCurrentDate` | 1 |
| `_vendor.dbfpy.header.DbfHeader.toString` | 4 |
| `_vendor.dbfpy.header.DbfHeader.write` | 9 |
| `_vendor.dbfpy.record.DbfRecord.<lambda1>` | 0 |
| `_vendor.dbfpy.record.DbfRecord.__getitem__` | 2 |
| `_vendor.dbfpy.record.DbfRecord.__init__` | 2 |
| `_vendor.dbfpy.record.DbfRecord.__repr__` | 7 |
| `_vendor.dbfpy.record.DbfRecord.__setitem__` | 2 |
| `_vendor.dbfpy.record.DbfRecord._validateIndex` | 1 |
| `_vendor.dbfpy.record.DbfRecord._write` | 13 |
| `_vendor.dbfpy.record.DbfRecord.asDict` | 4 |
| `_vendor.dbfpy.record.DbfRecord.asList` | 0 |
| `_vendor.dbfpy.record.DbfRecord.delete` | 0 |
| `_vendor.dbfpy.record.DbfRecord.fromStream` | 2 |
| `_vendor.dbfpy.record.DbfRecord.fromString` | 2 |
| `_vendor.dbfpy.record.DbfRecord.rawFromStream` | 6 |
| `_vendor.dbfpy.record.DbfRecord.store` | 4 |
| `_vendor.dbfpy.record.DbfRecord.toString` | 10 |
| `_vendor.dbfpy.utils._InvalidValue.__bool__` | 0 |
| `_vendor.dbfpy.utils._InvalidValue.__eq__` | 1 |
| `_vendor.dbfpy.utils._InvalidValue.__float__` | 0 |
| `_vendor.dbfpy.utils._InvalidValue.__int__` | 0 |
| `_vendor.dbfpy.utils._InvalidValue.__ne__` | 0 |
| `_vendor.dbfpy.utils._InvalidValue.__repr__` | 0 |
| `_vendor.dbfpy.utils._InvalidValue.__str__` | 0 |
| `_vendor.dbfpy.utils.classproperty.__get__` | 2 |
| `_vendor.dbfpy.utils.getDate` | 4 |
| `_vendor.dbfpy.utils.getDateTime` | 1 |
| `_vendor.dbfpy.utils.unzfill` | 1 |
| `core.Databook.__init__` | 0 |
| `core.Databook.__repr__` | 0 |
| `core.Databook._package` | 2 |
| `core.Databook.add_sheet` | 2 |
| `core.Databook.export` | 10 |
| `core.Databook.load` | 10 |
| `core.Databook.sheets` | 0 |
| `core.Databook.size` | 1 |
| `core.Databook.wipe` | 0 |
| `core.Dataset.__delitem__` | 6 |
| `core.Dataset.__getitem__` | 6 |
| `core.Dataset.__init__` | 3 |
| `core.Dataset.__len__` | 1 |
| `core.Dataset.__repr__` | 1 |
| `core.Dataset.__setitem__` | 2 |
| `core.Dataset.__str__` | 11 |
| `core.Dataset._clean_col` | 4 |
| `core.Dataset._get_dict` | 1 |
| `core.Dataset._get_headers` | 0 |
| `core.Dataset._get_in_format` | 15 |
| `core.Dataset._package` | 5 |
| `core.Dataset._package.format_row` | 6 |
| `core.Dataset._set_dict` | 9 |
| `core.Dataset._set_headers` | 2 |
| `core.Dataset._set_in_format` | 12 |
| `core.Dataset._transpose_with_headers` | 8 |
| `core.Dataset._transpose_without_headers` | 6 |
| `core.Dataset._validate` | 5 |
| `core.Dataset.add_formatter` | 5 |
| `core.Dataset.append` | 1 |
| `core.Dataset.append_col` | 1 |
| `core.Dataset.append_separator` | 3 |
| `core.Dataset.export` | 17 |
| `core.Dataset.extend` | 1 |
| `core.Dataset.filter` | 2 |
| `core.Dataset.get` | 3 |
| `core.Dataset.get_col` | 1 |
| `core.Dataset.height` | 1 |
| `core.Dataset.insert` | 9 |
| `core.Dataset.insert_col` | 14 |
| `core.Dataset.insert_separator` | 1 |
| `core.Dataset.load` | 15 |
| `core.Dataset.lpop` | 2 |
| `core.Dataset.lpush` | 1 |
| `core.Dataset.lpush_col` | 1 |
| `core.Dataset.pop` | 1 |
| `core.Dataset.remove_duplicates` | 5 |
| `core.Dataset.rpop` | 2 |
| `core.Dataset.rpush` | 2 |
| `core.Dataset.rpush_col` | 2 |
| `core.Dataset.sort` | 7 |
| `core.Dataset.stack` | 6 |
| `core.Dataset.stack_cols` | 11 |
| `core.Dataset.subset` | 13 |
| `core.Dataset.transpose` | 4 |
| `core.Dataset.width` | 3 |
| `core.Dataset.wipe` | 0 |
| `core.Row.__contains__` | 0 |
| `core.Row.__delitem__` | 0 |
| `core.Row.__getitem__` | 0 |
| `core.Row.__getstate__` | 0 |
| `core.Row.__init__` | 3 |
| `core.Row.__iter__` | 0 |
| `core.Row.__len__` | 1 |
| `core.Row.__repr__` | 1 |
| `core.Row.__setitem__` | 0 |
| `core.Row.__setstate__` | 0 |
| `core.Row.append` | 1 |
| `core.Row.copy` | 2 |
| `core.Row.has_tag` | 4 |
| `core.Row.insert` | 1 |
| `core.Row.list` | 1 |
| `core.Row.lpush` | 1 |
| `core.Row.rpush` | 2 |
| `core.Row.tuple` | 1 |
| `core.detect_format` | 17 |
| `core.import_book` | 2 |
| `core.import_set` | 2 |
| `formats.FormatDescriptorBase.__init__` | 1 |
| `formats.FormatDescriptorBase.ensure_format_loaded` | 1 |
| `formats.ImportExportBookDescriptor.__get__` | 8 |
| `formats.ImportExportBookDescriptor.__set__` | 7 |
| `formats.ImportExportSetDescriptor.__get__` | 15 |
| `formats.ImportExportSetDescriptor.__set__` | 12 |
| `formats.Registry.formats` | 3 |
| `formats.Registry.get_format` | 4 |
| `formats.Registry.register` | 3 |
| `formats.Registry.register_builtins` | 2 |
| `formats._cli.CLIFormat.export_set` | 5 |
| `formats._csv.CSVFormat.detect` | 7 |
| `formats._csv.CSVFormat.export_set` | 2 |
| `formats._csv.CSVFormat.export_stream_set` | 6 |
| `formats._csv.CSVFormat.import_set` | 8 |
| `formats._dbf.DBFFormat.detect` | 1 |
| `formats._dbf.DBFFormat.export_set` | 20 |
| `formats._dbf.DBFFormat.import_set` | 9 |
| `formats._df.DataFrameFormat.detect` | 6 |
| `formats._df.DataFrameFormat.export_set` | 4 |
| `formats._df.DataFrameFormat.import_set` | 3 |
| `formats._html.HTMLFormat.export_book` | 4 |
| `formats._html.HTMLFormat.export_set` | 6 |
| `formats._html.HTMLFormat.import_set` | 12 |
| `formats._html.TablibHTMLParser.__init__` | 2 |
| `formats._html.TablibHTMLParser.handle_data` | 0 |
| `formats._html.TablibHTMLParser.handle_endtag` | 3 |
| `formats._html.TablibHTMLParser.handle_starttag` | 2 |
| `formats._jira.JIRAFormat._get_body` | 3 |
| `formats._jira.JIRAFormat._get_header` | 1 |
| `formats._jira.JIRAFormat._serialize_row` | 3 |
| `formats._jira.JIRAFormat.export_set` | 3 |
| `formats._json.JSONFormat.detect` | 1 |
| `formats._json.JSONFormat.export_book` | 3 |
| `formats._json.JSONFormat.export_set` | 3 |
| `formats._json.JSONFormat.import_book` | 5 |
| `formats._json.JSONFormat.import_set` | 3 |
| `formats._json.serialize_objects_handler` | 6 |
| `formats._latex.LATEXFormat._cmidrule` | 0 |
| `formats._latex.LATEXFormat._colspec` | 1 |
| `formats._latex.LATEXFormat._escape_tex_reserved_symbols` | 2 |
| `formats._latex.LATEXFormat._escape_tex_reserved_symbols.replace` | 1 |
| `formats._latex.LATEXFormat._midrule` | 3 |
| `formats._latex.LATEXFormat._serialize_row` | 3 |
| `formats._latex.LATEXFormat.export_set` | 7 |
| `formats._ods.ODSFormat.detect` | 3 |
| `formats._ods.ODSFormat.dset_sheet` | 13 |
| `formats._ods.ODSFormat.export_book` | 8 |
| `formats._ods.ODSFormat.export_set` | 7 |
| `formats._ods.ODSFormat.import_book` | 5 |
| `formats._ods.ODSFormat.import_set` | 3 |
| `formats._ods.ODSFormat.import_sheet` | 8 |
| `formats._ods.ODSFormat.import_sheet.is_real_cell` | 3 |
| `formats._ods.ODSFormat.read_cell` | 7 |
| `formats._ods.ODSFormat.read_cell.convert_date` | 2 |
| `formats._ods.set_date_style` | 5 |
| `formats._ods.set_time_style` | 5 |
| `formats._rst.ReSTFormat._get_column_string_lengths` | 13 |
| `formats._rst.ReSTFormat._get_column_widths` | 7 |
| `formats._rst.ReSTFormat._row_to_lines` | 8 |
| `formats._rst.ReSTFormat._row_to_lines.just` | 2 |
| `formats._rst.ReSTFormat._use_simple_table` | 2 |
| `formats._rst.ReSTFormat.export_book` | 2 |
| `formats._rst.ReSTFormat.export_set` | 8 |
| `formats._rst.ReSTFormat.export_set_as_grid_table` | 11 |
| `formats._rst.ReSTFormat.export_set_as_simple_table` | 11 |
| `formats._rst._max_word_len` | 3 |
| `formats._rst.to_str` | 3 |
| `formats._sql.SQLFormat._render_literal` | 7 |
| `formats._sql.SQLFormat.detect` | 0 |
| `formats._sql.SQLFormat.export_set` | 7 |
| `formats._sql.SQLFormat.import_set` | 1 |
| `formats._xls.XLSFormat.detect` | 6 |
| `formats._xls.XLSFormat.dset_sheet` | 8 |
| `formats._xls.XLSFormat.export_book` | 8 |
| `formats._xls.XLSFormat.export_set` | 7 |
| `formats._xls.XLSFormat.import_book` | 8 |
| `formats._xls.XLSFormat.import_set` | 9 |
| `formats._xls.XLSFormat.import_sheet` | 7 |
| `formats._xls.XLSFormat.read_cell` | 1 |
| `formats._xls.safe_xls_sheet_title` | 1 |
| `formats._xlsx.XLSXFormat._adapt_column_width` | 8 |
| `formats._xlsx.XLSXFormat.detect` | 2 |
| `formats._xlsx.XLSXFormat.dset_sheet` | 12 |
| `formats._xlsx.XLSXFormat.export_book` | 10 |
| `formats._xlsx.XLSXFormat.export_set` | 7 |
| `formats._xlsx.XLSXFormat.import_book` | 5 |
| `formats._xlsx.XLSXFormat.import_set` | 3 |
| `formats._xlsx.XLSXFormat.import_sheet` | 5 |
| `formats._xlsx.safe_xlsx_sheet_title` | 1 |
| `formats._yaml.YAMLFormat.detect` | 2 |
| `formats._yaml.YAMLFormat.export_book` | 2 |
| `formats._yaml.YAMLFormat.export_set` | 2 |
| `formats._yaml.YAMLFormat.import_book` | 5 |
| `formats._yaml.YAMLFormat.import_set` | 3 |
| `formats.load_format_class` | 4 |
| `utils.normalize_input` | 3 |
| **276 functions** | **1,016** |

Module bodies were checked separately:

| Module | Edges checked |
|---|---:|
| `tablib` | 0 |
| `tablib._vendor` | 0 |
| `tablib._vendor.dbfpy` | 0 |
| `tablib._vendor.dbfpy.dbf` | 3 |
| `tablib._vendor.dbfpy.dbfnew` | 14 |
| `tablib._vendor.dbfpy.fields` | 10 |
| `tablib._vendor.dbfpy.header` | 2 |
| `tablib._vendor.dbfpy.record` | 2 |
| `tablib._vendor.dbfpy.utils` | 0 |
| `tablib.core` | 2 |
| `tablib.exceptions` | 0 |
| `tablib.formats` | 0 |
| `tablib.formats._cli` | 1 |
| `tablib.formats._csv` | 1 |
| `tablib.formats._dbf` | 1 |
| `tablib.formats._df` | 1 |
| `tablib.formats._html` | 1 |
| `tablib.formats._jira` | 1 |
| `tablib.formats._json` | 1 |
| `tablib.formats._latex` | 6 |
| `tablib.formats._ods` | 8 |
| `tablib.formats._rst` | 1 |
| `tablib.formats._sql` | 2 |
| `tablib.formats._tsv` | 0 |
| `tablib.formats._xls` | 3 |
| `tablib.formats._xlsx` | 2 |
| `tablib.formats._yaml` | 1 |
| `tablib.utils` | 0 |
| **28 modules** | **63** |

In the findings, source paths are relative to
`macro-benchmark/projects/tablib/src/tablib/`. Dependency paths are relative
to `macro-benchmark/selection/batch-8-proposal/deps/`. Rules refer to
`macro-benchmark/README.md`.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|
| T01 | missing | `tablib.core.Dataset.__repr__` | `core.py:220:40` | `-> <builtin>.bytes.lower` | PyYAML constructs `!!binary` as bytes (`pypi/PyYAML-6.0.3/lib/yaml/constructor.py:294–305`). `YAMLFormat.import_book` stores the decoded title unchanged (`formats/_yaml.py:50`). Loading a book with `title: !!binary QQ==` and `data: []`, then representing its first sheet, reaches `self.title.lower()` with `b'A'`. | B2: actual package-produced and stored values; B4: concrete outside receivers. The constructor’s documented string type does not erase a value assigned by an importer. |
| T02 | missing | `tablib.formats._rst._max_word_len` | `formats/_rst.py:29:49` | `-> <builtin>.bytes.split` | YAML `- ? !!binary YQ==\n  : 1\n` produces a mapping keyed by `b'a'`. `_yaml.py:40` forwards it to `_set_dict`; `core.py:372` installs its keys as headers without string conversion. `_rst.py:45–46` measures the bytes header and passes it to `_max_word_len`, which calls `text.split()`. | B2: package forwarding; B4: concrete outside receivers; B for private parameters supplied by package calls. |
| T03 | missing | `tablib._vendor.dbfpy.dbf.Dbf.indexOfFieldName` | `_vendor/dbfpy/dbf.py:207:38` | `-> <builtin>.bytes.upper` | The bytes header of T02 reaches DBF export. `_dbf.py:33–45` passes the original header to `record[fieldname]`; `record.py:262` forwards it to `indexOfFieldName`. `fields.py:85` normalizes the separate DBF field name, not the Dataset header. `name.upper()` runs before `names.index(...)` rejects the bytes result. | B2/B4: produced concrete values retain provenance through forwarding. Ground-truth “Edges”: a later failure does not remove a call already entered. |
| T04 | missing | `tablib.core.Dataset.__setitem__` | `core.py:195:19` | `-> tablib.core.Row.__iter__` | With `d = Dataset([1, 2]); d[:] = [3, 4]`, validation succeeds and line 195 assigns a package-created `Row` to a list slice. CPython calls `PySequence_Fast(value)` (`cpython/3.10.22/Objects/listobject.c:3004`), which calls `PyObject_GetIter` (`Objects/abstract.c:2152–2175`), reaching `Row.__iter__`. | C: public special method; B2/B5: an opaque client key may control execution; “Implicit calls” and library callbacks count package methods. No integer-only key contract exists here. |
| T05 | missing | `tablib.core.Dataset._package.format_row` | `core.py:290:31` | `-> <builtin>.list.copy` | Load YAML `- - [1, 2]\n`, then execute the shared witness below. PyYAML constructs the nested list (`constructor.py:405–408`). Slice assignment at `core.py:195` stores that list directly in `_data`; `_package` forwards it at line 305. With a formatter installed, line 290 calls its `copy()`. | B2: library-produced values and actual package flows; B4: concrete receiver; batch-6 ruling “State changed through a public method”; B3 excludes failed-object reuse, but this witness has no failed preceding operation. |
| T06 | missing | `tablib.core.Dataset._package.format_row` | `core.py:290:31` | `-> <builtin>.dict.copy` | As T05, using YAML `- - {k: 1}\n`. PyYAML constructs the dictionary (`constructor.py:410–414`); successful slice assignment stores it directly in `_data`, and line 290 calls `dict.copy()`. | B2/B4 and the public-state-change ruling, as T05. |
| T07 | missing | `tablib.core.Dataset._package.format_row` | `core.py:290:31` | `-> <builtin>.set.copy` | As T05, using YAML `- - !!set {k: null}\n`. PyYAML constructs a set (`constructor.py:396–400`, registered at 463–465); successful slice assignment stores it directly in `_data`, and line 290 calls `set.copy()`. | B2/B4 and the public-state-change ruling, as T05. |
| T08 | ruling | `tablib.core.Dataset.__init__` | `core.py:172:14` | Question: `-> tablib.formats.ImportExportSetDescriptor.__set__` | `registry.register('title', custom_format)` installs a package descriptor at `Dataset.title` (`formats/__init__.py:89`). A custom format whose `import_set` returns normally lets the next `Dataset()` reach that descriptor at line 172. Does public registration admit names colliding with existing attributes, or does B3 exclude undocumented collision names? | B3 restricts client-selected attribute names; batch-6 ruling “State changed through a public method” admits supported public mutations. Neither explicitly settles installing a package descriptor under a colliding name later accessed by fixed source syntax. |

The shared witness for T05–T07 is source-derived and was not executed.
Set `document` to the YAML string specified in its row:

```python
d = tablib.Dataset().load(document, "yaml")
d[:] = d[0]
d.add_formatter(None, lambda value: value)
d.dict
```

`d[0]` contains one imported container, so the assignment passes the
one-column validation. List slice assignment consumes the new `Row` and
stores that container as an element of `_data`. The formatter then reaches
the container’s `copy()` method. This disproves the ledger’s invariant
that every `_data` element is always a `Row`.

T04 does **not** add `Row.__len__`: `PySequence_Fast` obtains the iterator
first, then materializes that generator.

None of these findings is at a declared open path or open receiver set.
T08 is a rule question, not a counted missing edge.

| Missing | False | Naming | Ruling | Unsure |
|---:|---:|---:|---:|---:|
| **7** | **0** | **0** | **1** | **0** |

The seven missing edges comprise **1 inside** and **6 outside** the package.