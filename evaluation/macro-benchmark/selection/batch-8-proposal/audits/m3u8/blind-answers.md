# m3u8 6.0.0: blind answers of the audit

Written from the source at `49417d05602fc472b518ec61aa9b327cd00e079d`, the
README's rules and rulings, `PyCG/micro-benchmark/README.md`, the entry of
`projects.toml` and the dependency sources (CPython 3.7 to 3.15,
backports-datetime-fromisoformat 2.0.1), before any file of the writer was
opened.

## The draw

The skeleton (made without a ledger in a scratch copy) has 1303 sites: 780
explicit (766 `call`, 14 `decorator`) and 523 implicit. No kind dominates
as in tinytag, but the implicit sites are mostly dict and list subscripts
and `**` of dicts, so the draw is split in proportion: 42 explicit and 28
implicit sites, with one `random.Random(20261124)` (`draw.py`). Of the 10
value sites the draw holds one (`parser.py:523:26`); the other 9 are added:
79 sites (`sample.txt`, numbered by module in skeleton order, line, column).

## Settings that the answers use

| What | Value |
|---|---|
| Python | `python_requires=">=3.7"`: CPython 3.7 to 3.15; no PyPy (no declaration) |
| Platform | no classifier; CI on `ubuntu-latest` only: Linux (textdistance ruling) |
| backports-datetime-fromisoformat | declared for `python_version < '3.11'`; both sides of the optional import at `parser.py:9-14` run |
| Public | everything in `m3u8`, `m3u8.model`, `m3u8.parser`, `m3u8.httpclient`, `m3u8.mixins`, `m3u8.version_matching*` without an underscore |

## Answers

`->` a callee; `x` a rejected candidate. "Rest" names every other
candidate of the site.

### Explicit sites (42)

| # | Site | Callees | Rejections and reasons |
|---|---|---|---|
| 2 | `m3u8 [loads] 77:27 urljoin(uri, ".")` | `urllib.parse.urljoin` | none |
| 4 | `m3u8 [m3u8] 86:34 DefaultHTTPClient()` (default of `load`, module scope) | `m3u8.httpclient.DefaultHTTPClient.__init__` | none |
| 30 | `httpclient [DefaultHTTPClient.download] 24:45 resource.read().decode(...)` | `<builtin>.bytes.decode` | none; `resource` is what `OpenerDirector.open` returns (`http.client.HTTPResponse`, or `urllib.response.addinfourl` for `file:`, `ftp:`, `data:`); `read()` gives bytes on all |
| 67 | `model [M3U8.__init__] 171:43 self._base_uri.endswith("/")` | `<builtin>.str.endswith` | none; `base_uri` is documented as a uri string; the package passes `urljoin` and `os.path.dirname` results (str) |
| 97 | `model [M3U8._initialize_attributes] 207:34 self.files.append(key.uri)` | `<builtin>.list.append` | x `MediaList.uri`, `SegmentList.uri`: the argument is the `uri` attribute of a `Key` (a str), no function |
| 125 | `model [M3U8._initialize_attributes] 237:30 ImagePlaylist(...)` | `m3u8.model.ImagePlaylist.__init__` | x `M3U8.base_uri`, `Segment.base_uri`: the argument is the property's value (the getter runs at the getattr site 238:35), not the function |
| 132 | `model [M3U8._initialize_attributes] 247:39 self.data.get("server_control", None)` | `<builtin>.dict.get` | none; `self.data` is `parse`'s dict or `{}` |
| 239 | `model [M3U8.dumps] 412:30 str(self.session_data)` | `<builtin>.str`, `m3u8.model.TagList.__str__` | x rest: `session_data` is always a `SessionDataList`, which inherits `TagList.__str__` |
| 244 | `model [M3U8.dumps] 417:42 self.segments.dumps(timespec, infspec)` | `m3u8.model.SegmentList.dumps` | x rest: `segments` is a `SegmentList` (documented, and set by `_initialize_attributes`) |
| 270 | `model [Segment.__init__] 583:40 DateRangeList(...)` | `<builtin>.list.__init__` | none; `DateRangeList` -> `TagList` -> `list`: no package `__init__` |
| 271 | `model [Segment.__init__] 584:23 DateRange(**daterange)` | `m3u8.model.DateRange.__init__` | none |
| 285 | `model [Segment.dumps] 607:30 output.append("\n")` | `<builtin>.list.append` | none |
| 425 | `model [InitializationSection.__str__] 927:43 "{tag}:{attributes}".format(...)` | `<builtin>.str.format` | x every `__str__`: both fields are str (`self.tag` is the class attribute `ext_x_map`, `attributes` a `join`) |
| 437 | `model [Playlist.__init__] 967:42 resolution.strip('"')` | `<builtin>.str.strip` | none; the parser leaves `resolution` of `EXT-X-STREAM-INF` a raw str |
| 443 | `model [Playlist.__init__] 973:38 StreamInfo(...)` | `m3u8.model.StreamInfo.__init__` | none |
| 492 | `model [IFramePlaylist.__str__] 1073:22 str(...resolution[1])` | `<builtin>.str` | x every `__str__`: the item is an int of the pair that `__init__` builds |
| 530 | `model [StreamInfo.__str__] 1145:22 str(self.resolution[0])` | `<builtin>.str` | x every `__str__`: `resolution` is an int pair (documented "a tuple (w, h) of integers"; the package builds int pairs) |
| 567 | `model [Media.dumps] 1245:29 media_out.append(...)` | `<builtin>.list.append` | none |
| 667 | `model [DateRange.__init__] 1462:75 attr.startswith("x_")` | `<builtin>.str.startswith` | none; keyword names are str |
| 681 | `model [DateRange.dumps] 1488:29 daterange.append(...)` | `<builtin>.list.append` | none |
| 698 | `model [ContentSteering.dumps] 1517:53 ",".join(steering)` | `<builtin>.str.join` | none |
| 702 | `model [ImagePlaylist.__init__] 1542:38 resolution.split("x")` | `<builtin>.str.split` | none; the parser casts `resolution` with `str` |
| 717 | `model [ImagePlaylist.__str__] 1573:36 image_stream_inf.append(...)` | `<builtin>.list.append` | none |
| 752 | `model [number_to_string] 1656:28 decimal.Decimal(str(number))` | `decimal.Decimal` | none |
| 807 | `parser [parse] 134:29 line.startswith(f"...")` | `<builtin>.str.startswith` | none; `content` is documented as a string |
| 829 | `parser [parse] 155:29 line.startswith(...)` | `<builtin>.str.startswith` | none |
| 838 | `parser [parse] 164:29 line.startswith(...)` | `<builtin>.str.startswith` | none |
| 859 | `parser [parse] 185:29 line.startswith(...)` | `<builtin>.str.startswith` | none |
| 869 | `parser [parse] 195:24 _parse_skip(**parse_kwargs)` | `m3u8.parser._parse_skip` | none; binds (`line`, `data`, the rest to `**parse_kwargs`) |
| 892 | `parser [parse] 218:29 line.startswith(...)` | `<builtin>.str.startswith` | none |
| 901 | `parser [parse] 232:34 line.startswith("#")` | `<builtin>.str.startswith` | none |
| 935 | `parser [_parse_extinf] 270:29 ParseError(lineno, line)` | `m3u8.parser.ParseError.__init__` | none; strict mode and an `#EXTINF` without a comma |
| 1018 | `parser [_parse_stream_inf.<lambda1>] 358:56 float(x)` | `<builtin>.float` | none |
| 1033 | `parser [_parse_image_stream_inf] 387:44 remove_quotes_parser(...)` | `m3u8.parser.remove_quotes_parser` | none |
| 1103 | `parser [_parse_simple_parameter_raw_value] 520:46 param.replace(...)` | `<builtin>.str.replace` | none |
| 1106 | `parser [_parse_simple_parameter_raw_value] 523:26 cast_to(value)` (value site) | `m3u8.parser.cast_date_time`, `<builtin>.int`, `<builtin>.str` | none; private: the package passes `cast_date_time` (`_parse_program_date_time`), `int` (bitrate, target duration, media sequence, discontinuity sequence, version) and `str` (allow cache; the default for playlist type) |
| 1146 | `parser [_parse_cueout] 600:29 remove_quotes_parser("cue")` | `m3u8.parser.remove_quotes_parser` | none |
| 1166 | `parser [_parse_rendition_report] 641:37 data["rendition_reports"].append(...)` | `<builtin>.list.append` | none |
| 1216 | `parser [_parse_preload_hint] 700:49 _parse_attribute_list(...)` | `m3u8.parser._parse_attribute_list` | none |
| 1248 | `parser [normalize_attribute] 769:53 ....strip()` | `<builtin>.str.strip` | none |
| 1292 | `version_matching_rules [ValidFloatingPointEXTINF.validate] 72:35 self.line.replace(...)` | `<builtin>.str.replace` | none; `line: str` |
| 1298 | `version_matching_rules [ValidFloatingPointEXTINF.validate] 85:30 is_floating_number(duration)` | `m3u8.version_matching_rules.ValidFloatingPointEXTINF.validate.is_floating_number` | none |

### Implicit sites (28)

None of these sites has a package callee; every candidate is rejected.

| # | Site | Reason |
|---|---|---|
| 78 | `model [M3U8._initialize_attributes] 184:27 iter self.data.get("segment_map", [])` | a list of dicts |
| 88 | `model [M3U8._initialize_attributes] 197:13 iter attr, param` | unpacks a 2-tuple of str of `simple_attributes` |
| 114 | `model [M3U8._initialize_attributes] 225:23 iter self.data.get("iframe_playlists", [])` | a list |
| 329 | `model [Segment.dumps] 659:28 op infspec == "milliseconds"` | `infspec` is a str (default `"auto"`) |
| 372 | `model [PartialSegment.__init__] 790:26 mapping **daterange` | dicts of the parser; `PreloadHint` and `ServerControl` have no `keys` |
| 399 | `model [Key.__str__] 873:45 getattr self.uri` | receiver `Key` or `SessionKey`; `uri` is an instance attribute, not a property |
| 462 | `model [Playlist.__str__] 1001:22 iter self.media` | a list built in `__init__` |
| 501 | `model [IFramePlaylist.__str__] 1086:17 getattr self.uri` | receiver `IFramePlaylist`; plain attribute |
| 504 | `model [IFramePlaylist.__str__] 1087:59 getattr self.uri` | same |
| 553 | `model [Media.dumps] 1230:17 getattr self.uri` | receiver `Media`; plain attribute |
| 607 | `model [ServerControl.dumps] 1346:20 getitem self[attr]` | **-> `m3u8.model.ServerControl.__getitem__`**; x `PreloadHint.__getitem__` (receiver is a `ServerControl`, which has no subclass), x the two `__eq__` (the key is a str) |
| 687 | `model [DateRange.dumps] 1496:32 format {denormalize_attribute(attr)}` | a str |
| 808 | `parser [parse] 134:32 format {protocol.ext_x_asset}` | a str constant |
| 822 | `parser [parse] 147:34 mapping **parse_kwargs` | a dict |
| 837 | `parser [parse] 162:28 mapping **parse_kwargs` | a dict |
| 882 | `parser [parse] 207:32 mapping **parse_kwargs` | a dict |
| 924 | `parser [_parse_key] 260:12 op key not in data["keys"]` | a dict in a list of dicts and `None` |
| 951 | `parser [_parse_ts_chunk] 286:53 getitem state[...]` | a dict, str key |
| 982 | `parser [_parse_ts_chunk] 308:28 getitem data["keys"]` | a dict, str key |
| 1031 | `parser [_parse_i_frame_stream_inf] 383:9 getitem data[...]` | a dict, str key |
| 1085 | `parser [_parse_cue_span] 486:10 setitem state["cue_out"]` | a dict, str key |
| 1098 | `parser [_parse_start] 511:9 setitem data["start"]` | a dict, str key |
| 1099 | `parser [_parse_gap] 515:10 setitem state["gap"]` | a dict, str key |
| 1151 | `parser [_parse_cueout] 606:10 setitem state[...]` | a dict, str key |
| 1223 | `parser [_parse_daterange] 712:21 setitem attribute_parser["scte35_in"]` | the dict of `remove_quotes_parser`, str key |
| 1251 | `parser [get_segment_custom_value] 779:43 getitem state["segment"]` | the parser's state dict |
| 1265 | `version_matching [get_version] 8:17 iter file_lines` | `List[str]`; the package passes the list of `splitlines` |
| 1291 | `version_matching_rules [ValidFloatingPointEXTINF.validate] 69:28 op ... not in self.line` | a str in a str |

So: 1 package edge (`ServerControl.dumps -> ServerControl.__getitem__`).

### Value sites added (9)

| # | Site | Callees | Note |
|---|---|---|---|
| 775 | `parser [parse] 96:49 custom_tags_parser(line, lineno, data, state)` | none | a client callback (`parse`, `M3U8`, `loads`, `load`); the package defines no parser for the role (`get_segment_custom_value` and `save_segment_custom_value` are helpers that a parser calls, with another signature) |
| 967 | `parser [_parse_ts_chunk] 297:32 scte_op(...)` | `<builtin>.dict.get`, `<builtin>.dict.pop` | `scte_op` is `state.get` or `state.pop` of the parser's state dict (`parser.py:296`) |
| 969 | `... 298:39 scte_op(...)` | same | same |
| 971 | `... 299:41 scte_op(...)` | same | same |
| 973 | `... 300:44 scte_op(...)` | same | same |
| 975 | `... 301:40 scte_op(...)` | same | same |
| 1008 | `parser [_parse_attribute_list] 335:43 attribute_parser[name](value)` | `m3u8.parser.remove_quotes`, `<builtin>.int`, `<builtin>.float`, `<builtin>.str`, `m3u8.parser._parse_stream_inf.<lambda1>`, `m3u8.parser._parse_start.<lambda1>`, `m3u8.parser._parse_server_control.<lambda1>`, `.<lambda2>`, `.<lambda3>`, `m3u8.parser._parse_part_inf.<lambda1>`, `m3u8.parser._parse_part.<lambda1>` | private; the values of the parser dicts of its 19 package callers (`remove_quotes` through `remove_quotes_parser`); `_parse_asset` passes `{}`; any attribute name can appear in the content |
| 1009 | `parser [_parse_attribute_list] 337:35 default_parser(value)` | `<builtin>.str` | only `_parse_asset` passes a `default_parser` (`str`) |
| 1272 | `version_matching [valid_in_all_rules] 21:25 rule(version, line_number, line)` | `m3u8.version_matching_rules.VersionMatchRuleBase.__init__` | `rule` iterates the module list `available_rules` (three subclasses, none with an `__init__`); nothing documents a change of that list |
