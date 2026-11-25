# avro 1.12.2: blind answers of the audit (seed 20261124)

Written from the sdist's source (`avro/`, read whole), its metadata
(`pyproject.toml`, `PKG-INFO`), its tests as data (`avro/test/`), the trace
(`dynamic/avro.json`, the shared copy), the CPython sources of
`deps/cpython/` and the rules of `macro-benchmark/README.md`, before any
file of the writer was opened. The skeleton was made without the ledger in
`$TMPDIR/b8-audit-avro/` (`check.py --benchmark-dir ... --skeleton avro`).

## The draw

3231 sites: 1772 explicit (1669 call, 103 decorator), 1459 implicit
(651 getattr, 270 getitem, 216 op, 144 format, 106 iter, 44 setitem,
16 setattr, 10 with, 2 delitem); 18 value sites. No kind dominates
(explicit 55 %), so the 70 are split in proportion: 38 explicit and 32
implicit (`rng.sample(explicit, 38)`, then `rng.sample(implicit, 32)` on one
`random.Random(20261124)`), then the 18 value sites, none of them drawn:
88 sites. `draw.py` makes `sample.txt` from the skeleton and the size report.

## Assumptions fixed before answering

| Question | Answer used here |
|---|---|
| Versions, implementations | CPython 3.10 to 3.14 (`requires-python >=3.10`, classifiers 3.10 to 3.14); PyPy 3.10 and 3.11 (upstream's `test-lang-py.yml` matrix: `pypy-3.10`, `pypy-3.11`) |
| Platforms | Linux (the release declares no OS; upstream's jobs run on `ubuntu-latest` and `ubuntu-24.04-arm`; textdistance ruling), x86-64 and aarch64 |
| Optional imports | `bz2`, `snappy`, `zstandard` (`codecs.py:119-136`): both sides run; `snappy` and `zstandard` are not installed, so missing modules |
| Client streams | `IO[AnyStr]` / `IO[bytes]` parameters (`DataFileWriter`, `DataFileReader`, `BinaryEncoder`, `BinaryDecoder`) are abstract stream annotations: a stream that the client passes is opaque (B5, the segno ruling); the package's own `io.BytesIO` buffers and the CLI's `argparse.FileType` files and standard streams keep their names |
| `TetherTask` | abstract by `abc` (`map`, `reduce`, `reduceFlush`), documented for subclassing, no package subclass: not a receiver of its methods; the client's subclass is client code (B1, asyncstdlib), so a call through `self` in its methods (an inherited method, or a method of an attribute that `__init__` sets) has no callee (B5: "or on one of its attributes"). This is a case for the lead's ruling; the alternative is noted at site 3021 |
| `__init__` of a package class with no own `__init__` | named through the nearest outside base (`<builtin>.UserWarning.__init__`) |
| `collections.namedtuple` classes | no edge (`ValidationNode`, `_ttype`) |

## Answers

Notation: `->` callee; `reject` candidate with the reason. A site with no
`->` has no callee.

### Explicit sites (38)

| # | Site | Node | Callees | Rejected candidates |
|---|---|---|---|---|
| 3 | `avro/__init__.py:34:93` `.strip()` | `avro` | `<builtin>.str.strip` | none |
| 8 | `__main__.py:62:10` `print(result)` | `print_json_pretty` | `<builtin>.print` | the five `__str__`: `result` is the `str` of `json.dumps(...).replace` |
| 123 | `__main__.py:180:19` `dict(zip(...))` | `iter_csv` | `<builtin>.dict` | `DataFileReader.__iter__`, `__next__`: `dict` iterates a `zip` of two lists |
| 179 | `__main__.py:258:33` `subparser_write.add_argument(...)` | `_parse_args` | `argparse.ArgumentParser.add_argument` (`add_parser` makes `type(parser)`, an `ArgumentParser`) | none |
| 221 | `codecs.py:176:34` `readers_decoder.skip_long()` | `NullCodec.decompress` | `avro.io.BinaryDecoder.skip_long` | none |
| 263 | `codecs.py:261:41` `avro.io.BinaryDecoder(...)` | `BZip2Codec.decompress` | `avro.io.BinaryDecoder.__init__` | none (the `bz2` branch runs: optional import) |
| 472 | `compatibility.py:303:41` `incompatible(...)` | `check_reader_writer_record_fields` | `avro.compatibility.incompatible` | `Name.name`, `Message.name`, `Protocol.name`, `NamedSchema.name`: `reader_field` is a `Field`, whose `name` is an instance attribute, and no function is passed |
| 493 | `compatibility.py:341:30` `incompatible(...)` | `check_fixed_size` | `avro.compatibility.incompatible` | none |
| 569 | `datafile.py:144:22` `self.del_meta(CODEC_KEY)` | `_DataFileMetadata.codec` (deleter) | `avro.datafile._DataFileMetadata.del_meta` | none |
| 612 | `datafile.py:233:31` `self._write_header()` | `DataFileWriter._write_block` | `avro.datafile.DataFileWriter._write_header` | none |
| 897 | `io.py:381:62` `datetime.timedelta(days_since_epoch)` | `BinaryDecoder.read_date_from_int` | `datetime.timedelta` | none |
| 1022 | `io.py:740:46` `avro.errors.AvroWarning(...)` | `_collection_limits` | `<builtin>.UserWarning.__init__` (`AvroWarning` defines no `__init__`) | none |
| 1286 | `io.py:1090:6` `@staticmethod` | `avro.io` | `<builtin>.staticmethod` | none |
| 1596 | `io.py:1418:36` `isinstance(datum, decimal.Decimal)` | `DatumWriter.write_data` | `<builtin>.isinstance` | none |
| 1641 | `io.py:1458:33` `encoder.write_int(...)` | `DatumWriter.write_enum` | `avro.io.BinaryEncoder.write_int` (annotation `BinaryEncoder`; no package subclass) | none |
| 1695 | `ipc.py:47:49` `avro.io.DatumWriter(...)` | `avro.ipc` | `avro.io.DatumWriter.__init__` | none |
| 1740 | `ipc.py:156:51` `self.local_protocol.messages.get(...)` | `BaseRequestor.write_call_request` | `<builtin>.dict.get` (the package's `local_protocol` is a `Protocol`: `tool.send_message`, `HTTPRequestor.request`; `Protocol.messages` is the dict of `_parse_messages`) | none |
| 1837 | `ipc.py:300:61` `self.local_protocol.messages.get(...)` | `Responder.respond` | `<builtin>.dict.get` (the package passes a `Protocol`: `GenericResponder`, `TaskRunnerResponder`) | none |
| 2062 | `protocol.py:108:36` `str(self)` | `Protocol.__init__` | `<builtin>.str`, `avro.protocol.Protocol.__str__` | `SchemaType.__str__`, `Message.__str__`, `Field.__str__`, `Schema.__str__`: `self` is a `Protocol` (no package subclass) |
| 2158 | `protocol.py:226:51` `getattr(self, prop)` | `Message.__eq__` | `<builtin>.getattr` (the names are slots: member descriptors, no package code) | none |
| 2195 | `protocol.py:252:30` `json_data.get("namespace")` | `make_avpr_object` | `<builtin>.dict.get` (`ProtocolObject` is a `TypedDict`: `dict`, B4) | none |
| 2266 | `schema.py:207:38` `str(that)` | `EqualByJsonMixin.__eq__` | `<builtin>.str`, `avro.schema.Schema.__str__` (`that: object` names no package value, but the tests compare parsed schemas of every kind: `test_schema.py:932`, `:1000`; every schema class inherits `Schema.__str__`) | `Field.__str__`: neither the package nor its tests compare a `Field` with a field or schema on the right; `Message.__str__`, `Protocol.__str__`, `SchemaType.__str__`: never passed. `Message.__eq__` passes `getattr(that, prop)` only for a client `that` (opaque) |
| 2289 | `schema.py:251:26` `isinstance(type_, str)` | `Schema.__init__` | `<builtin>.isinstance` | none |
| 2351 | `schema.py:380:6` `@property` | `avro.schema` | `<builtin>.property` | none |
| 2458 | `schema.py:598:22` `self.set_prop("size", size)` | `FixedSchema.__init__` | `avro.schema.PropertiesMixin.set_prop` | none |
| 2586 | `schema.py:832:49` `make_avsc_object(...)` | `MapSchema.__init__` | `avro.schema.make_avsc_object` | none |
| 2599 | `schema.py:856:34` `self.props.copy()` | `MapSchema.to_json` | `<builtin>.dict.copy` (`props` makes a `dict`) | none |
| 2660 | `schema.py:956:42` `schema.to_json(names)` | `ErrorUnionSchema.to_json` | `to_json` of `PrimitiveSchema`, `BytesDecimalSchema`, `DateSchema`, `TimeMillisSchema`, `TimeMicrosSchema`, `TimestampMillisSchema`, `TimestampMicrosSchema`, `FixedSchema`, `FixedDecimalSchema`, `EnumSchema`, `ArraySchema`, `MapSchema`, `ErrorUnionSchema`, `RecordSchema` (14: the declared errors are any schema that `make_avsc_object` makes, a nested `{"type": "error_union"}` included, since `UnionSchema.__init__` refuses only `type == "union"`) | `Schema.to_json`: abstract, every class overrides it; `UUIDSchema.to_json`: its type is `"string"`, which the loop skips; `UnionSchema.to_json`: a union cannot hold a union (`schema.py:905`); `Field`, `Message`, `Protocol` `.to_json`: no branch is one |
| 2708 | `schema.py:1036:6` `@property` | `avro.schema` | `<builtin>.property` | none |
| 2792 | `schema.py:1232:40` `logical_types.get(...)` | `make_logical_schema` | `<builtin>.dict.get` | none |
| 2906 | `tether_task.py:44:23` `hf.read()` | `avro.tether.tether_task` | `io.TextIOWrapper.read` (`open(pfile)`, text mode) | `BinaryDecoder.read`, `DatumReader.read`: `hf` is the file |
| 2921 | `tether_task.py:59:23` `hf.read()` | `avro.tether.tether_task` | `io.TextIOWrapper.read` | as 2906 |
| 2984 | `tether_task.py:306:6` `@property` | `avro.tether.tether_task` | `<builtin>.property` | none |
| 3021 | `tether_task.py:439:22` `self.log.info(...)` | `TetherTask.close` | none: `self` is an instance of a client subclass (B1: `TetherTask` is abstract by `abc`; the client's subclasses are client code), and `log` is an attribute of that client object (B5). **For the lead**: if the client subclass that calls `TetherTask.__init__` is a receiver, the callee is `logging.Logger.info` | none |
| 3041 | `tether_task_runner.py:70:35` `self.log.error(...)` | `TaskRunnerResponder.invoke` | `logging.Logger.error` (`self` is a `TaskRunnerResponder`, a package class; `log` from its `__init__`; the branch runs when the assignment to the client task, through a weak proxy, raises) | none |
| 3052 | `tether_task_runner.py:77:34` `self.runner.close()` | `TaskRunnerResponder.invoke` | `avro.tether.tether_task_runner.TaskRunner.close` (a weak proxy of the `TaskRunner` that `HTTPHandlerGen` gets) | `DataFileReader.close`, `DataFileWriter.close`, `HTTPTransceiver.close`, `TetherTask.close`: the runner is a `TaskRunner` |
| 3120 | `tether/util.py:27:15` `s.bind(...)` | `find_port` | `socket.socket.bind` | none |
| 3164 | `tool.py:88:33` `GenericResponder(...)` | `run_server` | `avro.tool.GenericResponder.__init__` | `avro.ipc.Responder.__init__`: `GenericResponder` defines `__init__`; its own explicit call is another site (`tool.py:46`) |

### Implicit sites (32)

None of them has a package callee except where a callee is written.

| # | Site | Node | Callees | Rejected candidates |
|---|---|---|---|---|
| 105 | `__main__.py:173:22` getitem `IO[AnyStr]` | `avro.__main__` | none | the `__eq__` and `__hash__` candidates: typing objects only |
| 115 | `__main__.py:177:71` iter `info` | `iter_csv` | none | `DataFileReader.__iter__`, `__next__`: `info` is a stream (`IO[AnyStr]`) |
| 191 | `__main__.py:275:27` getattr `args.schema` | `main` | none | `_DataFileMetadata.schema`: `args` is an `argparse.Namespace` |
| 366 | `compatibility.py:185:28` op `reader.type in PRIMITIVE_TYPES` | `calculate_compatibility` | none | all twelve: a `str` looked up in a set of `SchemaType` members; no package `__eq__` or `__hash__` runs |
| 380 | `compatibility.py:197:66` getattr `writer.values` | `calculate_compatibility` | `avro.schema.MapSchema.values` | none |
| 671 | `datafile.py:341:27` getitem `IO[bytes]` | `avro.datafile` | none | all ten: typing objects |
| 721 | `datafile.py:408:24` getattr `avro.errors` | `DataFileReader.__next__` | none | `Message.errors`: a module attribute |
| 773 | `io.py:109:28` getitem `Union[...]` | `avro.io` | none | all ten: builtin types and `None` |
| 1092 | `io.py:868:24` getattr `avro.errors` | `DatumReader.read_data` | none | `Message.errors`: module attribute |
| 1201 | `io.py:948:44` getattr `avro.schema` | `DatumReader.skip_data` | none | `_DataFileMetadata.schema`: module attribute |
| 1218 | `io.py:960:47` getattr `avro.schema` | `avro.io` | none | as 1201 |
| 1235 | `io.py:982:50` getattr `writers_schema.symbols` | `DatumReader.read_enum` | `avro.schema.EnumSchema.symbols` | none |
| 1247 | `io.py:995:24` getattr `avro.errors` | `DatumReader.read_enum` | none | `Message.errors`: module attribute |
| 1262 | `io.py:1049:64` format `{MAX_COLLECTION_ITEMS_ENV}` | `_ensure_collection_available` | none | the five `__str__`: a `str` constant |
| 1312 | `io.py:1125:45` iter `_collection_limits()` | `DatumReader.skip_array` | none | `DataFileReader.__iter__`, `__next__`: a tuple |
| 1386 | `io.py:1228:78` getattr `avro.schema` | `avro.io` | none | `_DataFileMetadata.schema`: module attribute |
| 1463 | `io.py:1312:58` getattr `field_schema.schemas` | `DatumReader._read_default_value` | `avro.schema.UnionSchema.schemas` (also for an `ErrorUnionSchema`, which inherits it) | none |
| 1501 | `io.py:1355:24` getattr `avro.errors` | `DatumWriter.write_data` | none | `Message.errors`: module attribute |
| 1647 | `io.py:1477:25` iter `datum` | `DatumWriter.write_array` | none | `DataFileReader.__iter__`, `__next__`: `datum` is a `Sequence` (checked at `io.py:1430`); a `DataFileReader` is none |
| 1810 | `ipc.py:248:33` getattr `self.local_protocol` | `Responder.__init__` | `avro.ipc.Responder.local_protocol` | `BaseRequestor.local_protocol`: `self` is a `Responder` |
| 1814 | `ipc.py:250:55` getattr `self.local_protocol` | `Responder.__init__` | `avro.ipc.Responder.local_protocol` | as 1810 |
| 2019 | `name.py:173:75` format `{space_attr}` | `Names.add_name` | none | the five `__str__`: `Optional[str]` |
| 2076 | `protocol.py:123:32` getitem `Optional[...]` | `avro.protocol` | none | all ten: typing objects and classes (a class's hash is `type`'s) |
| 2107 | `protocol.py:144:74` iter `self.messages.items()` | `Protocol.to_json` | none | `DataFileReader.__iter__`, `__next__`: dict items |
| 2204 | `protocol.py:267:33` getitem `Sequence[str]` | `avro.protocol` | none | all ten |
| 2246 | `schema.py:171:36` getitem `MutableMapping[str, object]` | `avro.schema` | none | all ten |
| 2292 | `schema.py:253:18` op `type_ not in VALID_TYPES` | `Schema.__init__` | none | all twelve: a `str` against a tuple of `str` |
| 2379 | `schema.py:430:24` getattr `avro.errors` | `Field.__init__` | none | `Message.errors`: module attribute |
| 2517 | `schema.py:709:111` format `{symbols}` | `EnumSchema.__init__` | none | the five `__str__`: a sequence of `str` |
| 2577 | `schema.py:811:24` getattr `self.canonical_properties` | `ArraySchema.to_canonical_json` | `avro.schema.CanonicalPropertiesMixin.canonical_properties` | none |
| 2813 | `schema.py:1249:45` getattr `avro.name` | `avro.schema` | none | the four `name`: module attribute |
| 2948 | `tether_task.py:196:30` getattr `avro.schema` | `TetherTask.__init__` | none | `_DataFileMetadata.schema`: module attribute |

### Value sites (18)

| # | Site | Node | Callees | Where the values come from |
|---|---|---|---|---|
| 12 | `__main__.py:71:15` `_write_row(...)` | `print_csv` | `_csv.writer.writerow` (the bound method of `csv.writer(sys.stdout)`, `__main__.py:65`; the type has no public path: `.name = "_csv.writer"` in `Modules/_csv.c` of 3.10 to 3.14); `avro.timezones.UTCTzinfo.utcoffset` | the writer calls `str()` on a field that is not a `str` or float; a record read by `DataFileReader` holds a timestamp-millis or timestamp-micros value as a `datetime` with `tzinfo=avro.timezones.utc` (`io.py:415`, `:425`), and `datetime.__str__` (isoformat) calls the tzinfo's `utcoffset`: the library call-back of the package site (B5). `TSTTzinfo` is never read back |
| 47 | `__main__.py:112:22` `fs(...)` | `print_avro` | `avro.__main__.field_selector.keys_filter`, `avro.__main__._passthrough_keys_filter` | `fs = field_selector(fields)` (`__main__.py:111`): the closure when `fields` is not empty, else the module function |
| 56 | `__main__.py:117:23` `_write_row(sorted(record))` | `print_avro` | `_csv.writer.writerow` | as 12; the row is a sorted list of keys (`str`): no call-back |
| 58 | `__main__.py:118:16` `printer(record)` | `print_avro` | `avro.__main__.print_json`, `avro.__main__.print_json_pretty`, `avro.__main__.print_csv` | `select_printer(format_)` (`__main__.py:75`) |
| 114 | `__main__.py:177:58` `getattr(i, "decode", lambda: i)()` | `iter_csv` | `avro.__main__.iter_csv.<lambda1>`, `<builtin>.bytes.decode` | `i` is a line of `info: IO[AnyStr]`; the CLI's files are text (`argparse.FileType("r")`, `sys.stdin`), so `str` and the lambda; `bytes` lines are handled explicitly (the comment at `:175`, `AnyStr`) |
| 149 | `__main__.py:197:39` `iter_records(file_, schema)` | `write` | `avro.__main__.iter_json`, `avro.__main__.iter_csv` (generator functions) | the dict at `__main__.py:194` |
| 776 | `io.py:127:46` `ValidationNode(...)` | `validate` | none | `collections.namedtuple` class (`io.py:107`): no edge |
| 781 | `io.py:134:36` `ValidationNode(...)` | `validate` | none | namedtuple; reject `Name.name`, `Message.name`, `Protocol.name`, `NamedSchema.name`: `current_node.name` is a tuple field, and no function is passed |
| 793 | `io.py:148:68` `_ITERATORS.get(...)(node)` | `_iterate_node` | `avro.io._record_iterator`, `avro.io._array_iterator`, `avro.io._map_iterator`, `avro.io._default_iterator` | `_ITERATORS` (`io.py:184-189`: record, error and request to `_record_iterator`) and the default |
| 794 | `io.py:149:29` `ValidationNode(*item)` | `_iterate_node` | none | namedtuple |
| 797 | `io.py:168:27` `ValidationNode(...)` | `_record_iterator` | none | namedtuple; reject the four `name`: `field.name` is a `Field` instance attribute |
| 804 | `io.py:174:27` `ValidationNode(...)` | `_array_iterator` | none | namedtuple; reject `ArraySchema.items`: its value is passed, not the function (the property runs at its own getattr site) |
| 809 | `io.py:181:27` `ValidationNode(...)` | `_map_iterator` | none | namedtuple |
| 2443 | `schema.py:552:33` `validator(datum)` | `PrimitiveSchema.validate` | `avro.schema.PrimitiveSchema.<lambda1>` to `<lambda8>` | `_validators` (`schema.py:499-508`); `PrimitiveSchema.validate.<lambda1>` (the default) is not reached: every receiver that does not override `validate` is a plain `PrimitiveSchema`, whose type is one of the eight keys (`schema.py:512`). (A client `str` subclass whose hash differs from its `str` value would reach it; I do not admit that) |
| 2780 | `schema.py:1193:22` `uuid.UUID(datum)` | `UUIDSchema.validate` | `uuid.UUID` | the stdlib module (`schema.py:48`); a value site because `avro.constants.UUID` binds the name |
| 2793 | `schema.py:1234:31` `schema_type(other_props)` | `make_logical_schema` | `avro.schema.DateSchema.__init__`, `avro.schema.make_bytes_decimal_schema`, `avro.schema.make_logical_schema.<lambda1>`, `avro.schema.TimestampMicrosSchema.__init__`, `avro.schema.TimestampMillisSchema.__init__`, `avro.schema.TimeMicrosSchema.__init__`, `avro.schema.TimeMillisSchema.__init__`, `avro.schema.UUIDSchema.__init__` | the dict at `schema.py:1220-1230` |
| 2914 | `tether_task.py:54:18` `_ttype(*taskschema.symbols)` | `avro.tether.tether_task` | none | namedtuple class (`tether_task.py:53`) |
| 3112 | `tether_task_runner.py:229:19` `taskcls()` | `avro.tether.tether_task_runner` | none | `getattr` of a module and class named on the command line (`:218-228`): a client class; a package class there is `TetherTask`, abstract (its instantiation raises before `__init__`) |

## Cases for the lead, from the blind pass

1. `TetherTask` (site 3021 and every method of the class, and `TaskRunner`'s
   calls on its task): see the table of assumptions.
2. The test files that `avro/test` opens with `"ab+"` are
   `io.BufferedRandom`, passed to `IO[AnyStr]` parameters: client streams,
   so the trace edges to `_io.BufferedRandom.*` are rejected (segno). The
   `io.BufferedReader` and `io.BufferedWriter` edges stay, because the
   package's own CLI (`__main__.py:254`, `:265`, `:266`; `tool.py:109`, `:114`,
   `:119`) opens such files and passes them on.
