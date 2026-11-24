Avro, round 1: **1 false edge and 1 ruling question**. No confirmed missing
or naming findings. Neither finding concerns an open path or receiver set.

The audit covered all 439 function/lambda nodes and all 1,748 existing edges.
Counts below are distinct outgoing graph edges, before corrections. Property
accessors sharing a graph node are counted together; every accessor was read.
The checker reported zero undecided sites and zero unaccounted trace edges.

| Module | Functions read | Function edges checked | Module edges checked |
|---|---:|---:|---:|
| `avro` | 0 | 0 | 3 |
| `avro.__main__` | 21 | 95 | 3 |
| `avro.codecs` | 18 | 70 | 9 |
| `avro.compatibility` | 17 | 68 | 1 |
| `avro.constants` | 0 | 0 | 0 |
| `avro.datafile` | 36 | 122 | 10 |
| `avro.errors` | 4 | 18 | 0 |
| `avro.io` | 88 | 376 | 5 |
| `avro.ipc` | 41 | 152 | 7 |
| `avro.name` | 13 | 23 | 2 |
| `avro.protocol` | 26 | 95 | 1 |
| `avro.schema` | 129 | 492 | 8 |
| `avro.tether` | 0 | 0 | 0 |
| `avro.tether.tether_task` | 18 | 46 | 11 |
| `avro.tether.tether_task_runner` | 10 | 41 | 9 |
| `avro.tether.util` | 1 | 4 | 0 |
| `avro.timezones` | 6 | 4 | 0 |
| `avro.tool` | 10 | 65 | 4 |
| `avro.utils` | 1 | 3 | 1 |
| **Total** | **439** | **1,674** | **74** |

Function names in each table carry the indicated module prefix.

`avro.__main__`

| Function | Edges checked |
|---|---:|
| `_parse_args` | 8 |
| `_passthrough_keys_filter` | 0 |
| `cat` | 6 |
| `convert` | 6 |
| `convert_union` | 4 |
| `csv_arg` | 3 |
| `field_selector` | 0 |
| `field_selector.keys_filter` | 2 |
| `guess_input_type` | 3 |
| `iter_csv` | 9 |
| `iter_csv.<lambda1>` | 0 |
| `iter_json` | 5 |
| `main` | 4 |
| `print_avro` | 18 |
| `print_csv` | 3 |
| `print_json` | 2 |
| `print_json_pretty` | 3 |
| `print_schema` | 4 |
| `record_match` | 4 |
| `select_printer` | 0 |
| `write` | 11 |

`avro.codecs`

| Function | Edges checked |
|---|---:|
| `BZip2Codec.compress` | 2 |
| `BZip2Codec.decompress` | 12 |
| `Codec.compress` | 0 |
| `Codec.decompress` | 0 |
| `DeflateCodec.compress` | 2 |
| `DeflateCodec.decompress` | 14 |
| `NullCodec.compress` | 1 |
| `NullCodec.decompress` | 1 |
| `SnappyCodec.compress` | 4 |
| `SnappyCodec.decompress` | 11 |
| `ZstandardCodec.compress` | 3 |
| `ZstandardCodec.decompress` | 12 |
| `_check_crc32` | 3 |
| `_decompress_read_ceiling` | 0 |
| `_max_decompress_length` | 3 |
| `_raise_decompression_too_large` | 1 |
| `_snappy_uncompressed_length` | 0 |
| `get_codec` | 1 |

`avro.compatibility`

| Function | Edges checked |
|---|---:|
| `ReaderWriter.__eq__` | 1 |
| `ReaderWriter.__hash__` | 1 |
| `ReaderWriter.__init__` | 0 |
| `ReaderWriterCompatibilityChecker.__init__` | 0 |
| `ReaderWriterCompatibilityChecker.calculate_compatibility` | 17 |
| `ReaderWriterCompatibilityChecker.check_reader_writer_record_fields` | 11 |
| `ReaderWriterCompatibilityChecker.get_compatibility` | 6 |
| `SchemaCompatibilityResult.__init__` | 1 |
| `SchemaType.__str__` | 0 |
| `check_fixed_size` | 2 |
| `check_reader_enum_contains_writer_enum` | 7 |
| `check_schema_names` | 3 |
| `incompatible` | 3 |
| `lookup_writer_field` | 5 |
| `merge` | 4 |
| `schema_name_equals` | 5 |
| `type_mismatch` | 2 |

`avro.datafile`

| Function | Edges checked |
|---|---:|
| `DataFileReader.__enter__` | 0 |
| `DataFileReader.__exit__` | 1 |
| `DataFileReader.__init__` | 12 |
| `DataFileReader.__iter__` | 0 |
| `DataFileReader.__next__` | 7 |
| `DataFileReader._read_block_header` | 9 |
| `DataFileReader._read_header` | 8 |
| `DataFileReader._skip_sync` | 4 |
| `DataFileReader.close` | 2 |
| `DataFileReader.datum_decoder` | 0 |
| `DataFileReader.datum_reader` | 0 |
| `DataFileReader.determine_file_length` | 3 |
| `DataFileReader.file_length` | 0 |
| `DataFileReader.is_EOF` | 3 |
| `DataFileReader.raw_decoder` | 0 |
| `DataFileReader.reader` | 0 |
| `DataFileWriter.__enter__` | 0 |
| `DataFileWriter.__exit__` | 1 |
| `DataFileWriter.__init__` | 17 |
| `DataFileWriter._write_block` | 17 |
| `DataFileWriter._write_header` | 4 |
| `DataFileWriter.append` | 6 |
| `DataFileWriter.buffer_encoder` | 0 |
| `DataFileWriter.buffer_writer` | 0 |
| `DataFileWriter.close` | 4 |
| `DataFileWriter.datum_writer` | 0 |
| `DataFileWriter.encoder` | 0 |
| `DataFileWriter.flush` | 4 |
| `DataFileWriter.sync` | 4 |
| `DataFileWriter.writer` | 0 |
| `_DataFileMetadata.codec` | 6 |
| `_DataFileMetadata.del_meta` | 1 |
| `_DataFileMetadata.get_meta` | 2 |
| `_DataFileMetadata.meta` | 1 |
| `_DataFileMetadata.schema` | 5 |
| `_DataFileMetadata.set_meta` | 1 |

`avro.errors`

| Function | Edges checked |
|---|---:|
| `AvroOutOfScaleException.__init__` | 2 |
| `AvroTypeException.__init__` | 8 |
| `SchemaResolutionException.__init__` | 4 |
| `_safe_pretty` | 4 |

`avro.io`

| Function | Edges checked |
|---|---:|
| `BinaryDecoder.__init__` | 0 |
| `BinaryDecoder._build_time_object` | 2 |
| `BinaryDecoder.bytes_remaining` | 6 |
| `BinaryDecoder.read` | 6 |
| `BinaryDecoder.read_boolean` | 2 |
| `BinaryDecoder.read_bytes` | 2 |
| `BinaryDecoder.read_date_from_int` | 3 |
| `BinaryDecoder.read_decimal_from_bytes` | 2 |
| `BinaryDecoder.read_decimal_from_fixed` | 9 |
| `BinaryDecoder.read_double` | 3 |
| `BinaryDecoder.read_float` | 3 |
| `BinaryDecoder.read_int` | 1 |
| `BinaryDecoder.read_long` | 3 |
| `BinaryDecoder.read_null` | 0 |
| `BinaryDecoder.read_time_micros_from_long` | 2 |
| `BinaryDecoder.read_time_millis_from_int` | 2 |
| `BinaryDecoder.read_timestamp_micros_from_long` | 3 |
| `BinaryDecoder.read_timestamp_millis_from_long` | 3 |
| `BinaryDecoder.read_utf8` | 2 |
| `BinaryDecoder.reader` | 0 |
| `BinaryDecoder.skip` | 6 |
| `BinaryDecoder.skip_boolean` | 1 |
| `BinaryDecoder.skip_bytes` | 4 |
| `BinaryDecoder.skip_double` | 1 |
| `BinaryDecoder.skip_float` | 1 |
| `BinaryDecoder.skip_int` | 1 |
| `BinaryDecoder.skip_long` | 3 |
| `BinaryDecoder.skip_null` | 0 |
| `BinaryDecoder.skip_utf8` | 1 |
| `BinaryEncoder.__init__` | 0 |
| `BinaryEncoder._timedelta_total_microseconds` | 0 |
| `BinaryEncoder.write` | 4 |
| `BinaryEncoder.write_boolean` | 3 |
| `BinaryEncoder.write_bytes` | 4 |
| `BinaryEncoder.write_date_int` | 2 |
| `BinaryEncoder.write_decimal_bytes` | 8 |
| `BinaryEncoder.write_decimal_fixed` | 7 |
| `BinaryEncoder.write_double` | 2 |
| `BinaryEncoder.write_float` | 2 |
| `BinaryEncoder.write_int` | 1 |
| `BinaryEncoder.write_long` | 2 |
| `BinaryEncoder.write_null` | 0 |
| `BinaryEncoder.write_time_micros_long` | 1 |
| `BinaryEncoder.write_time_millis_int` | 1 |
| `BinaryEncoder.write_timestamp_micros_long` | 7 |
| `BinaryEncoder.write_timestamp_millis_long` | 7 |
| `BinaryEncoder.write_utf8` | 2 |
| `BinaryEncoder.writer` | 0 |
| `DatumReader.__init__` | 0 |
| `DatumReader._ensure_collection_available` | 2 |
| `DatumReader._read_default_value` | 13 |
| `DatumReader._skip_block_bytes` | 3 |
| `DatumReader.read` | 4 |
| `DatumReader.read_array` | 10 |
| `DatumReader.read_data` | 37 |
| `DatumReader.read_enum` | 5 |
| `DatumReader.read_fixed` | 2 |
| `DatumReader.read_map` | 9 |
| `DatumReader.read_record` | 11 |
| `DatumReader.read_union` | 6 |
| `DatumReader.readers_schema` | 0 |
| `DatumReader.skip_array` | 8 |
| `DatumReader.skip_data` | 16 |
| `DatumReader.skip_enum` | 1 |
| `DatumReader.skip_fixed` | 2 |
| `DatumReader.skip_map` | 9 |
| `DatumReader.skip_record` | 2 |
| `DatumReader.skip_union` | 6 |
| `DatumReader.writers_schema` | 0 |
| `DatumWriter.__init__` | 0 |
| `DatumWriter.write` | 4 |
| `DatumWriter.write_array` | 4 |
| `DatumWriter.write_data` | 31 |
| `DatumWriter.write_enum` | 3 |
| `DatumWriter.write_fixed` | 1 |
| `DatumWriter.write_map` | 6 |
| `DatumWriter.write_record` | 3 |
| `DatumWriter.write_union` | 6 |
| `DatumWriter.writers_schema` | 0 |
| `_array_iterator` | 1 |
| `_collection_limits` | 4 |
| `_default_iterator` | 0 |
| `_iterate_node` | 5 |
| `_map_iterator` | 2 |
| `_max_collection_items` | 1 |
| `_min_bytes_per_element` | 10 |
| `_record_iterator` | 2 |
| `validate` | 22 |

`avro.ipc`

| Function | Edges checked |
|---|---:|
| `BaseRequestor.__init__` | 0 |
| `BaseRequestor.local_protocol` | 0 |
| `BaseRequestor.read_call_response` | 11 |
| `BaseRequestor.read_handshake_response` | 7 |
| `BaseRequestor.read_response` | 2 |
| `BaseRequestor.remote_hash` | 2 |
| `BaseRequestor.remote_protocol` | 2 |
| `BaseRequestor.request` | 6 |
| `BaseRequestor.send_protocol` | 0 |
| `BaseRequestor.transceiver` | 0 |
| `BaseRequestor.write_call_request` | 9 |
| `BaseRequestor.write_handshake_request` | 9 |
| `BaseRequestor.write_request` | 2 |
| `FramedReader.__init__` | 0 |
| `FramedReader._read_buffer_length` | 5 |
| `FramedReader.read_framed_message` | 11 |
| `FramedReader.reader` | 0 |
| `FramedWriter.__init__` | 0 |
| `FramedWriter.write_buffer` | 5 |
| `FramedWriter.write_buffer_length` | 4 |
| `FramedWriter.write_framed_message` | 3 |
| `FramedWriter.writer` | 0 |
| `HTTPTransceiver.__init__` | 3 |
| `HTTPTransceiver.close` | 1 |
| `HTTPTransceiver.read_framed_message` | 4 |
| `HTTPTransceiver.transceive` | 2 |
| `HTTPTransceiver.write_framed_message` | 6 |
| `Requestor.issue_request` | 7 |
| `Responder.__init__` | 4 |
| `Responder.get_protocol_cache` | 2 |
| `Responder.invoke` | 0 |
| `Responder.local_hash` | 0 |
| `Responder.local_protocol` | 0 |
| `Responder.process_handshake` | 10 |
| `Responder.protocol_cache` | 0 |
| `Responder.read_request` | 2 |
| `Responder.respond` | 23 |
| `Responder.set_protocol_cache` | 1 |
| `Responder.write_error` | 3 |
| `Responder.write_response` | 2 |
| `_load` | 4 |

`avro.name`

| Function | Edges checked |
|---|---:|
| `Name.__eq__` | 3 |
| `Name.__init__` | 4 |
| `Name.fullname` | 0 |
| `Name.get_space` | 2 |
| `Name.name` | 0 |
| `Name.space` | 1 |
| `Names.__init__` | 0 |
| `Names.add_name` | 3 |
| `Names.get_name` | 3 |
| `Names.has_name` | 2 |
| `Names.prune_namespace` | 1 |
| `_validate_fullname` | 2 |
| `validate_basename` | 2 |

`avro.protocol`

| Function | Edges checked |
|---|---:|
| `Message.__eq__` | 5 |
| `Message.__init__` | 4 |
| `Message.__str__` | 2 |
| `Message.errors` | 0 |
| `Message.name` | 0 |
| `Message.request` | 0 |
| `Message.response` | 0 |
| `Message.to_json` | 21 |
| `Protocol.__eq__` | 4 |
| `Protocol.__init__` | 14 |
| `Protocol.__str__` | 2 |
| `Protocol.fullname` | 4 |
| `Protocol.md5` | 0 |
| `Protocol.messages` | 0 |
| `Protocol.name` | 0 |
| `Protocol.namespace` | 0 |
| `Protocol.to_json` | 11 |
| `Protocol.types` | 0 |
| `Protocol.types_dict` | 2 |
| `_parse_errors` | 4 |
| `_parse_messages` | 5 |
| `_parse_request` | 3 |
| `_parse_response` | 3 |
| `_parse_types` | 4 |
| `make_avpr_object` | 4 |
| `parse` | 3 |

`avro.schema`

| Function | Edges checked |
|---|---:|
| `<lambda1>` | 0 |
| `ArraySchema.__init__` | 8 |
| `ArraySchema.items` | 1 |
| `ArraySchema.match` | 2 |
| `ArraySchema.to_canonical_json` | 10 |
| `ArraySchema.to_json` | 20 |
| `ArraySchema.validate` | 1 |
| `BytesDecimalSchema.__init__` | 3 |
| `BytesDecimalSchema.precision` | 1 |
| `BytesDecimalSchema.scale` | 1 |
| `BytesDecimalSchema.to_json` | 1 |
| `BytesDecimalSchema.validate` | 1 |
| `CanonicalPropertiesMixin.canonical_properties` | 2 |
| `DateSchema.__init__` | 2 |
| `DateSchema.to_json` | 1 |
| `DateSchema.validate` | 1 |
| `DecimalLogicalSchema.__init__` | 4 |
| `EnumSchema.__init__` | 6 |
| `EnumSchema.default` | 4 |
| `EnumSchema.doc` | 1 |
| `EnumSchema.match` | 1 |
| `EnumSchema.symbols` | 2 |
| `EnumSchema.to_canonical_json` | 4 |
| `EnumSchema.to_json` | 5 |
| `EnumSchema.validate` | 1 |
| `EqualByJsonMixin.__eq__` | 5 |
| `EqualByJsonMixin.__hash__` | 2 |
| `EqualByPropsMixin.__eq__` | 5 |
| `EqualByPropsMixin.__hash__` | 2 |
| `ErrorUnionSchema.__init__` | 1 |
| `ErrorUnionSchema.to_json` | 16 |
| `Field.__init__` | 8 |
| `Field.__str__` | 2 |
| `Field.default` | 1 |
| `Field.doc` | 1 |
| `Field.has_default` | 0 |
| `Field.order` | 1 |
| `Field.to_canonical_json` | 9 |
| `Field.to_json` | 19 |
| `FixedDecimalSchema.__init__` | 6 |
| `FixedDecimalSchema.precision` | 1 |
| `FixedDecimalSchema.scale` | 1 |
| `FixedDecimalSchema.to_json` | 1 |
| `FixedDecimalSchema.validate` | 1 |
| `FixedSchema.__init__` | 4 |
| `FixedSchema.match` | 1 |
| `FixedSchema.size` | 1 |
| `FixedSchema.to_canonical_json` | 2 |
| `FixedSchema.to_json` | 5 |
| `FixedSchema.validate` | 3 |
| `LogicalSchema.__init__` | 0 |
| `MapSchema.__init__` | 7 |
| `MapSchema.match` | 2 |
| `MapSchema.to_canonical_json` | 10 |
| `MapSchema.to_json` | 20 |
| `MapSchema.validate` | 2 |
| `MapSchema.values` | 1 |
| `NamedSchema.__init__` | 10 |
| `NamedSchema.fullname` | 0 |
| `NamedSchema.name` | 1 |
| `NamedSchema.name_ref` | 3 |
| `NamedSchema.namespace` | 1 |
| `PrimitiveSchema.<lambda1>` | 0 |
| `PrimitiveSchema.<lambda2>` | 1 |
| `PrimitiveSchema.<lambda3>` | 1 |
| `PrimitiveSchema.<lambda4>` | 1 |
| `PrimitiveSchema.<lambda5>` | 1 |
| `PrimitiveSchema.<lambda6>` | 1 |
| `PrimitiveSchema.<lambda7>` | 1 |
| `PrimitiveSchema.<lambda8>` | 1 |
| `PrimitiveSchema.__init__` | 2 |
| `PrimitiveSchema.match` | 1 |
| `PrimitiveSchema.to_canonical_json` | 3 |
| `PrimitiveSchema.to_json` | 2 |
| `PrimitiveSchema.validate` | 10 |
| `PrimitiveSchema.validate.<lambda1>` | 0 |
| `PropertiesMixin.check_props` | 4 |
| `PropertiesMixin.get_prop` | 2 |
| `PropertiesMixin.other_props` | 2 |
| `PropertiesMixin.props` | 0 |
| `PropertiesMixin.set_prop` | 1 |
| `RecordSchema.__init__` | 9 |
| `RecordSchema.doc` | 1 |
| `RecordSchema.fields` | 1 |
| `RecordSchema.fields_dict` | 1 |
| `RecordSchema.make_field_objects` | 7 |
| `RecordSchema.match` | 1 |
| `RecordSchema.to_canonical_json` | 7 |
| `RecordSchema.to_json` | 8 |
| `RecordSchema.validate` | 4 |
| `Schema.__eq__` | 0 |
| `Schema.__init__` | 5 |
| `Schema.__str__` | 17 |
| `Schema.canonical_form` | 8 |
| `Schema.fingerprint` | 25 |
| `Schema.match` | 0 |
| `Schema.to_canonical_json` | 0 |
| `Schema.to_json` | 0 |
| `Schema.validate` | 0 |
| `TimeMicrosSchema.__init__` | 2 |
| `TimeMicrosSchema.to_json` | 1 |
| `TimeMicrosSchema.validate` | 1 |
| `TimeMillisSchema.__init__` | 2 |
| `TimeMillisSchema.to_json` | 1 |
| `TimeMillisSchema.validate` | 1 |
| `TimestampMicrosSchema.__init__` | 2 |
| `TimestampMicrosSchema.to_json` | 1 |
| `TimestampMicrosSchema.validate` | 2 |
| `TimestampMillisSchema.__init__` | 2 |
| `TimestampMillisSchema.to_json` | 1 |
| `TimestampMillisSchema.validate` | 2 |
| `UUIDSchema.__init__` | 2 |
| `UUIDSchema.to_json` | 1 |
| `UUIDSchema.validate` | 1 |
| `UnionSchema.__init__` | 8 |
| `UnionSchema.match` | 8 |
| `UnionSchema.schemas` | 0 |
| `UnionSchema.to_canonical_json` | 8 |
| `UnionSchema.to_json` | 17 |
| `UnionSchema.validate` | 16 |
| `_crc_64_fingerprint` | 1 |
| `_is_timezone_aware_datetime` | 2 |
| `from_path` | 3 |
| `get_other_props` | 1 |
| `make_avsc_object` | 20 |
| `make_bytes_decimal_schema` | 2 |
| `make_logical_schema` | 14 |
| `make_logical_schema.<lambda1>` | 0 |
| `parse` | 4 |

`avro.tether.tether_task`

| Function | Edges checked |
|---|---:|
| `Collector.__init__` | 3 |
| `Collector.collect` | 5 |
| `HTTPRequestor.__init__` | 0 |
| `HTTPRequestor.request` | 3 |
| `TetherTask.__init__` | 3 |
| `TetherTask.close` | 2 |
| `TetherTask.complete` | 4 |
| `TetherTask.configure` | 6 |
| `TetherTask.count` | 1 |
| `TetherTask.fail` | 4 |
| `TetherTask.input` | 7 |
| `TetherTask.map` | 0 |
| `TetherTask.open` | 7 |
| `TetherTask.partitions` | 0 |
| `TetherTask.reduce` | 0 |
| `TetherTask.reduceFlush` | 0 |
| `TetherTask.status` | 1 |
| `keys_are_equal` | 0 |

`avro.tether.tether_task_runner`

| Function | Edges checked |
|---|---:|
| `HTTPHandlerGen` | 2 |
| `HTTPHandlerGen.TaskRunnerHTTPHandler.__init__` | 2 |
| `HTTPHandlerGen.TaskRunnerHTTPHandler.do_POST` | 9 |
| `TaskRunner.__init__` | 3 |
| `TaskRunner.close` | 0 |
| `TaskRunner.server` | 3 |
| `TaskRunner.start` | 8 |
| `TaskRunner.start.thread_run` | 4 |
| `TaskRunnerResponder.__init__` | 4 |
| `TaskRunnerResponder.invoke` | 6 |

`avro.tether.util`

| Function | Edges checked |
|---|---:|
| `find_port` | 4 |

`avro.timezones`

| Function | Edges checked |
|---|---:|
| `TSTTzinfo.dst` | 1 |
| `TSTTzinfo.tzname` | 0 |
| `TSTTzinfo.utcoffset` | 1 |
| `UTCTzinfo.dst` | 1 |
| `UTCTzinfo.tzname` | 0 |
| `UTCTzinfo.utcoffset` | 1 |

`avro.tool`

| Function | Edges checked |
|---|---:|
| `GenericHandler.do_POST` | 11 |
| `GenericResponder.__init__` | 4 |
| `GenericResponder.invoke` | 3 |
| `_parse_args` | 6 |
| `main` | 4 |
| `main_dump` | 6 |
| `main_rpcreceive` | 7 |
| `main_rpcsend` | 7 |
| `run_server` | 8 |
| `send_message` | 9 |

`avro.utils`

| Function | Edges checked |
|---|---:|
| `_randbytes` | 3 |

Findings follow. Package paths are relative to
`macro-benchmark/projects/avro/`; dependency paths are relative to
`macro-benchmark/selection/batch-8-proposal/deps/`.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|
| AVRO-R1-01 | false | `avro.__main__.main` | `avro/__main__.py:276:33` | `avro.__main__.main -> <builtin>.RuntimeError.__init__` | `_parse_args` requires a subcommand at line 209 and registers only `cat` (210) and `write` (255). Its `parse_args()` at 267 returns one of those command names or raises. Both successful values return from `main` at 273 or 275, so the `UsageError(...)` call at 276 cannot run. Every admitted runtime takes the `required=True` branch. Dependency evidence: CPython 3.10.22 `Lib/argparse.py:1198–1212,2089–2108`; PyPy 3.11 `lib-python/3/argparse.py:1222–1237,2150–2169`. | Scope B limits edges to values supplied by package flows; B1 excludes a guard failure impossible under package-owned values. Rule A preserves uncalled function bodies, not unreachable branches within them. |
| AVRO-R1-02 | ruling | `avro.protocol.Message.to_json` | `avro/protocol.py:215:36` | Current: `avro.protocol.Message.to_json -> <builtin>.dict.__init__`. Question: retain this edge, replace it, or add an edge to `typing._TypedDictMeta.__call__` or `<builtin>.dict`? | `MessageObject` derives from `TypedDict` at `protocol.py:39`. Its metaclass creates a nominal `dict` subclass but assigns `__call__ = dict`, so `MessageObject()` constructs an exact dictionary. CPython 3.10.22 `Lib/typing.py:2350,2381`; the same override occurs in CPython 3.11–3.15 and both admitted PyPy versions. The unresolved case is a metaclass override that aliases a builtin **class**, rather than defining a method. The source does not establish that `dict.__init__` never executes inside that construction. | The batch-7 outside-metaclass ruling (`macro-benchmark/README.md:2911`) names an override through its concrete metaclass. “Outside names” (`:2249`) treats a direct class alias as a class path. The micro README’s constructor rules (`:139–150`) distinguish inherited initializers from builtin class calls. Their interaction for this class-valued override needs a ruling. |

| Total | Count |
|---|---:|
| Missing | 0 |
| False | 1 |
| Naming | 0 |
| Ruling | 1 |
| Unsure | 0 |
| Findings excluded for open path/receiver sets | 0 |