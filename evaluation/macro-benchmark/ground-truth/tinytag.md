# tinytag: judgements of the ground truth

Release 2.3.2 (commit `c123836`). Analysed source: `tinytag/` without
`tinytag/tests/`: 3 modules (`tinytag`, `tinytag.tinytag`,
`tinytag.__main__`), 79 functions (no lambdas), 16 classes.
`pyproject.toml` sets `requires-python = ">=3.7"`, so the supported versions
are 3.7 and later. The CI matrix (`.github/workflows/tests.yml`) runs CPython
3.7 to 3.15, the free-threaded builds and PyPy 3.8 to 3.11, on Linux, macOS
and Windows. The package has no branch on the Python version, the
implementation or the platform, and no `assert` or `__debug__`, so `-O` and
`-OO` change no edge.

The ledger is `tinytag.ledger`; the graph `tinytag.json` is generated from
it. Nine trace edges are rejected in `tinytag.rejected.json` (judgements J2
and J4). The ground truth was written from the source alone; no analysis
tool ran on the package, and nothing of the package was run or imported.

## Architecture, as the ledger uses it

- `tinytag/tinytag.py` holds everything. `TinyTag` is the public class.
  `TinyTag.get` (a classmethod) chooses a parser class, makes an instance,
  gives it a file object and calls `_load`, which calls `self._parse(fh)`.
- The eight parser classes `_MP4`, `_ID3`, `_MPEG`, `_Ogg`, `_Wave`,
  `_Flac`, `_ASF` and `_Aiff` subclass `TinyTag` and override `_parse`. They
  are private (rule C; the changelog of 2.0.0 says "TinyTag subclasses are
  now private"). `_ID3`, `_MPEG` and `_Ogg` define `__init__` and call
  `super().__init__()`; the other five inherit `TinyTag.__init__`.
- Some parsers delegate to others: `_ID3._parse` makes a `_Flac` or an
  `_MPEG` for the audio part; `_Ogg._parse` makes a `_Flac` for Ogg FLAC;
  `_Wave._parse` and `_Aiff._parse` make an `_ID3` with `_only_id3 = True`
  for an embedded ID3 chunk. Each then calls `self._update(child)`.
- `TYPE_CHECKING = False` is a local constant (line 39), so the block at
  lines 42-54 never runs, and line 56 binds `_StringListDict` and
  `_ImageListDict` to `dict`. `OtherFields` and `OtherImages` are therefore
  dict subclasses without methods of their own: their construction is
  `<builtin>.dict.__init__` (trace confirms), and their methods are
  `<builtin>.dict.items`, `.values`, `.get`.
- `_MP4` parses through an atom tree: nested dicts whose leaves are
  callables (judgement J8). The trees are cached on the class at the first
  call (`_audio_data_tree`, `_meta_data_tree`, `_combined_tree`); the edges
  of the builders count, as a fresh process makes them.

## File objects

The file object reaches the parsers in two kinds. The client's `file_obj`
of `TinyTag.get` is annotated `BinaryIO | None`, an abstract type, so it
names no class (B4); the README's "file-like object (e.g. BytesIO)" is an
example, not a type, and a client's object is opaque (B5). This follows
python-barcode J4 (`fp: BinaryIO`, the client's BytesIO rejected). The
package's own file objects are:

- `P`: the `io.BufferedReader` that `get` opens with `open(filename, 'rb')`
  (line 146) when the client passes a file name and no `file_obj`;
- `B`: the `io.BytesIO` objects that the package makes (lines 786, 1741,
  1760, 1767, 1787, 1813, 1857, 2030, 2056, 2291, 2310, 2333, 2517).

Which kind reaches each function, from its package callers:

| Function | Receivers of `fh` | Why |
|---|---|---|
| `TinyTag.get`, `_get_parser_for_file_handle` | P | the file of `get` |
| `_MP4._traverse_atoms`, `_MPEG._parse`, `_Ogg._parse_pages`, `_Wave._parse` (fh), `_ASF._parse` (fh), `_Aiff._parse` | P | only `get` (and, for `_MPEG`, `_ID3._parse` after the `_only_id3` return) gives them a file |
| `_MP4._read_atom_header` | P, B | `_traverse_atoms` (P) and `_parse_custom_field` (B, line 786) |
| `_MP4._parse_custom_field` | B | its own `BytesIO(data)` |
| `_ID3._parse` | P, B per site | B from `_Wave`/`_Aiff`, which set `_only_id3`, so B reaches only lines 1073 and 1081; lines 1084, 1088, 1102, 1105 come after the return at 1083 and see only P |
| `_ID3._parse_id3v2_header`, `_parse_id3v2`, `_parse_frame` | P, B | called from `_ID3._parse` before the `_only_id3` return |
| `_ID3._parse_id3v1` | P | called only at line 1103, after the return |
| `_Flac._parse` | P, B | from `get`, from `_ID3._parse` (P) and from `_Ogg._parse` (the walker B, line 1774) |
| `_Flac._parse_image` | P, B | from `_Flac._parse` and from `_Ogg._parse_vorbis_comment` (B, line 1857) |
| `_Ogg._parse_vorbis_comment` | P, B | from `_set_vorbis_comment_fields` (B) and `_Flac._parse` (P, B) |
| `_ASF._parse_value` | B | the walkers of `_ASF._parse` (annotated `BytesIO`) |
| the `walker` variables | B | `BytesIO(...)` in the same function |

The Ogg packets are `bytearray`s (line 1909), so `packet.startswith` is
`<builtin>.bytearray.startswith` (trace confirms). The test
`test_file_obj_compatibility` (`test_all.py:3397-3404`) passes its own
`BytesIO` of `vbri.mp3`; the seven trace edges to `_io.BytesIO.read`,
`.seek` and `.tell` that only this object makes are rejected (J2).

## Scope rules

**A. Edges are per function.** Every function keeps its body's edges.
`TinyTag._parse` (only `raise NotImplementedError`), `_ID3._unsynchsafe`,
`_MP4._build_audio_data_tree`, `_MP4._data_parser`, `_MP4._nums_parser`
(each of the last two only defines and returns a closure) and
`Image.__init__` (only attribute stores) have no out-edges because their
bodies make no call. Rejected trace edges: the client's
BytesIO (J2) and a test's direct call of the private `_load` (J4).

**B1. Receivers.** `self` in a `TinyTag` method that the parsers inherit is
an instance of a parser class. `_load` is private; its package callers
(`get`, `_ID3._parse`, `_Ogg._parse`, `_Wave._parse`, `_Aiff._parse`) call
it on parser instances only, so `self._parse` at line 299 has the eight
overrides and not `TinyTag._parse`. `self.images` is always the `Images` of
`TinyTag.__init__`, so `self.images._set_field` and `._update` are the
`Images` methods, and `self._set_field` in a parser is `TinyTag._set_field`.
`self._parse_image` is `_ID3._parse_image` in `_ID3._parse_frame` (line
1417) and `_Flac._parse_image` in `_Flac._parse` (line 2150).

**B2. Arguments and stored values.** The values that the package stores
and passes are builtin: field values are `str`, `int`, `float` or `bool`;
the other fields and images are lists of `str` and of `Image`; header and
chunk data are `bytes` (from `read`) or `bytearray` (Ogg packets). No
package object is formatted, compared, hashed or iterated by an implicit
site, which is the reason of the default rejection.

**B3. Not considered.** A client's assignment to the private attributes
(`_filehandler`, `_only_id3`, `_load_image`) or to the class caches.

**B4. Concrete outside types.** `file_obj: BinaryIO` fixes no class (see
"File objects"). `filename` (`bytes | str | PathLike`) goes only to
`os.fsdecode` and `open`. `encoding` (`str | None`) only names a codec for
`bytes.decode`.

**B5. Client objects are opaque.** The client's `file_obj`; a client's
`PathLike` (its `__fspath__`, called by `fsdecode` and `open`, is client
code).

**C. Public and private.** Public: `TinyTag` and its public methods and
properties, `Image`, `Images`, `OtherFields`, `OtherImages` and the three
exceptions (`tinytag/__init__.py`). Private: the eight parser classes and
every `_`-method. `tinytag.__main__` is the command line (`python -m
tinytag`); its `_`-functions are private and called only by `_run`.

## Judgement calls

1. **Debug output (`TINYTAG_DEBUG`).** Line 59 sets `_DEBUG =
   bool(environ.get('TINYTAG_DEBUG'))` at import. The 10 `if _DEBUG:`
   blocks print with `<builtin>.print`; one of them also calls `fh.tell()`
   twice (`_parse_frame`, line 1318). The README of tinytag does not
   document the variable; the code comment says "some of the parsers can
   print debug info", and upstream's own test workflow sets
   `TINYTAG_DEBUG=true` (`tests.yml`; `projects.toml` note). The trace does
   not set it, so none of these calls ran. I decided by the nearest rule:
   an edge counts if a program that uses only the public API makes it in a
   fresh process ("Edges"), and a process environment set before the
   import is no change to package internals; the configuration rule of the
   "Clarifications" (configuration that changes a package-owned value)
   points the same way. So the branches run. The 14 debug sites carry a
   note (`judgement J1`).
   **Ruling (lead, after the blind audit):** the ten edges stay. An
   environment variable that the package reads to set a value of its own
   counts as configuration when the package's documentation or its own
   test setup sets it (README, "Rulings for batch 6"). Upstream's test
   job sets `TINYTAG_DEBUG: true` for the unit tests
   (`.github/workflows/tests.yml:58-61`) and requires full coverage under
   it (`tests.yml:131`, `coverage report
   --fail-under=${MIN_COVERAGE_PERCENTAGE}`, which is 100). The writer and
   the auditor reached this independently. The ten edges, all outside the
   package and all from reading only:
   `TinyTag._set_field`, `TinyTag._set_other_field`, `Images._set_field`,
   `Images._set_other_field`, `_MP4._traverse_atoms`,
   `_ID3._parse_id3v2_header`, `_ID3._parse_frame`,
   `_Ogg._parse_vorbis_comment` -> `<builtin>.print`, and
   `_ID3._parse_frame` -> `io.BufferedReader.tell`, `io.BytesIO.tell`.
   The other callees of the debug sites stay through sites outside the
   debug blocks (`_traverse_atoms -> <builtin>.len`, line 689).
2. **File objects.** See "File objects". The client's `file_obj` is opaque
   (B4/B5, python-barcode J4). Seven trace edges are rejected:
   `TinyTag.get -> _io.BytesIO.seek`, `.tell`;
   `_get_parser_for_file_handle -> _io.BytesIO.read`;
   `_ID3._parse -> _io.BytesIO.read`; `_ID3._parse_id3v1 ->
   _io.BytesIO.read`; `_MPEG._parse -> _io.BytesIO.read`, `.tell`. The
   other `BytesIO` edges of the trace are package values and stay. One
   `BytesIO` edge comes from reading only: `_Flac._parse -> io.BytesIO.seek`
   (line 2156, an Ogg FLAC stream with a block that is skipped).
3. **`cls != TinyTag` in `_get_parser_class`** (line 276). Through the
   public path `cls` is `TinyTag`, so the branch `return cls` runs only for
   a call of `get` on a private parser class (`test_invalid_file`,
   `test_all.py:3435-3447`: `_MP4.get(...)` and so on) or on a client
   subclass (client code). It has no call, and every edge that those tests
   make is also reachable through `TinyTag.get` (each parser class is
   chosen by extension or magic bytes, and each `ParseError` of an invalid
   header is reached from a file with the matching extension). No change.
4. **The `None` check of `_load`** (lines 294-295). `_load` is private,
   and every package caller sets `_filehandler` to a file object first
   (`get` after its own check at line 147; `_ID3._parse` lines 1092 and
   1110; `_Ogg._parse` line 1774; `_Wave._parse` line 2056; `_Aiff._parse`
   line 2517). The check cannot fail under the package's own values (B1;
   python-barcode J7), so `ValueError("File handle is required")` has no
   callee. `test_unimplemented_load` (`test_all.py:3533-3548`) calls `_load`
   through a client subclass of `TinyTag` with `file_handle=None` and with
   a `BytesIO`; its two trace edges (`_load -> <builtin>.ValueError`,
   `_load -> TinyTag._parse`) are rejected as a direct test invocation of a
   private API (rule A).
5. **Default rejection of `Image.__repr__`** (61 sites). No package code
   formats or prints an `Image`. The candidate sites are `str()`, `print()`
   and f-string fields of strs, ints, floats, bytes and lists, and the six
   `%` operators of ints (`% 2`). In `Image.__repr__` itself the fields are
   the attributes of an `Image`, annotated `str`, `int`, `bytes`, `str |
   None`. In `__main__._run`, `{exc}` formats an `OSError` or a
   `TinyTagException`; the exceptions define no `__str__`, and a
   `ParseError(exc)` holds the parser's exception, whose arguments are no
   `Image`. The tests' `str(vars(tag.images))` calls `Image.__repr__` from
   client code (no caller in the trace).
6. **Exceptions.** `ParseError(...)` and `UnsupportedFormatError(...)` (8
   sites) are named `<builtin>.Exception.__init__`, the first `__init__` of
   their MRO (the trace's `<builtin>.BaseException.__init__` has this
   alias). `raise NotImplementedError` (line 332) has no call.
7. **Names outside the package.** `os.environ.get` is
   `collections.abc.Mapping.get` (anytree precedent; trace confirms).
   `fsdecode` is `os.fsdecode` (the trace names `os._fscodec.fsdecode` with
   that alias). The csv writer's methods are `_csv.writer.writerow` and
   `.writerows` (netaddr precedent): the writer's type has no public path;
   `type(csv.writer(io.StringIO()))` is `_csv.writer` on CPython 3.12 to
   3.15, checked with the standard library only. `sys.stderr.write` is
   `io.TextIOWrapper.write` and the image file of `open(..., 'wb')` is an
   `io.BufferedWriter`. `isfile` and `splitext` are `os.path.isfile` and
   `os.path.splitext`, the paths that the module imports.
8. **Value sites** (3; see the table below).
9. **The command line** (`tinytag/__main__.py`). `projects.toml` leaves out
   `test_cli.py`, so the module runs in no test: its 5 functions and 35
   edges come from reading only. `data` in `_print_tag` is the dict of
   `TinyTag.as_dict` (strs, ints, floats, bools, lists of str), so
   `json.dumps` and the csv writer call no package code. `tag.as_dict()` is
   `TinyTag.as_dict`, not `Images.as_dict`.

## PyPy

**Decision: explicitly supported.** The release's test workflow runs the
unit tests on `pypy-3.8`, `pypy-3.9`, `pypy-3.10` and `pypy-3.11`
(`.github/workflows/tests.yml:20`), under the same coverage gate as
CPython. `pyproject.toml:65` pins `mypy<1.19.0` for PyPy in the `dev`
extra, and the test suite has a PyPy-on-Windows skip
(`tinytag/tests/test_all.py:3406-3409`). No classifier names PyPy, and the
README says only "Supports Python 3.7 or higher". With `requires-python =
">=3.7"`, every PyPy 3.x release from 3.7 on is admitted; the CI tests
3.8 to 3.11. I read the PyPy 3.10 (v7.3.19) and 3.11 (v7.3.20) sources as
text and ran nothing.

**Names checked (14 callee names, the same on both PyPy versions; no
change):**
- `io.BufferedReader.read`, `.seek`, `.tell`, `.close` and
  `io.BufferedWriter.write`: PyPy's `_io` defines `_io.BufferedReader`
  and `_io.BufferedWriter` with these methods
  (`pypy/module/_io/interp_bufferedio.py:1023-1043` and `1074-1090` in
  3.11, `1018-1038` and `1069-1085` in 3.10), and `lib-python/3/io.py:55`
  re-exports them as in CPython.
- `io.BytesIO` and its `read`, `seek`, `tell`: `_io.BytesIO`
  (`interp_bytesio.py:205-220`).
- `io.StringIO` and `.getvalue`: `_io.StringIO` (`interp_stringio.py:482-493`).
- `io.TextIOWrapper.write`: `_io.TextIOWrapper`
  (`interp_textio.py:1464-1474` in 3.11, `1424-1434` in 3.10).
- `_csv.writer.writerow` and `.writerows`, and `csv.writer`: PyPy's writer
  type is also named `_csv.writer` (`pypy/module/_csv/interp_writer.py:185-188`
  in 3.11, `172-175` in 3.10), and `lib-python/3/csv.py:7` imports `writer`
  from `_csv`.
- `struct.unpack` and `struct.unpack_from`: the interpreter-level module
  `_struct` (`pypy/module/struct/moduledef.py:48`, `56-57`), re-exported by
  `lib-python/3/struct.py:13`.
- `binascii.a2b_base64`: `pypy/module/binascii/moduledef.py:20`.
- `collections.abc.Mapping.get` for `os.environ.get`: PyPy's `os._Environ`
  subclasses `MutableMapping` (`lib-python/3/os.py:666` in 3.11, `667` in
  3.10), as in CPython. `os.fsdecode`, `warnings.warn` and `json.dumps`
  are on the same paths. The builtin methods (`bytes`, `bytearray`, `str`,
  `dict`, `list`, `set`) keep their `<builtin>` names.

**Call-backs: none to check.** No library call in the package receives a
package object that the library could call back: `json.dumps` and the csv
writer get only builtin values, and `struct`, `binascii` and the io
methods get bytes and ints. **Branches: none.** The package has no branch
on `sys.implementation` or `platform`, and no accelerator import with a
fallback. No edge changes.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `tinytag.tinytag.Image.__repr__` | 61 | no package code formats, prints or converts an `Image` (J5) | nowhere |

The 18 explicit sites that the default decides are `str(...)` and
`print(...)` calls; each keeps its own entry with `<builtin>.str` or
`<builtin>.print`.

## Value sites and exclusions

| Site | Callees | Exclusions |
|---|---|---|
| `tinytag.py:163:31` `parser_class()` | `_ID3.__init__`, `_MPEG.__init__`, `_Ogg.__init__`, `TinyTag.__init__` (for `_Wave`, `_Flac`, `_ASF`, `_MP4`, `_Aiff`) | `Image.__init__`, `Images.__init__` |
| `tinytag.py:690:53` `sub_path(data)` | the nine leaves of the atom trees: `_MP4._parse_mvhd`, `_parse_mp4a`, `_parse_alac` (audio tree), `_data_parser._parse_data_atom`, `_nums_parser._parse_nums`, `_parse_id3v1_genre`, `_parse_cover_image`, `_parse_custom_field`, `_parse_uuid` (meta tree; the one-leaf tree of line 721 holds a `_data_parser` closure) | `_Ogg._parse_vorbis_comment`, `_Flac._parse_image` |
| `tinytag.py:800:37` `parser(data_atom)` | `_MP4._data_parser._parse_data_atom` (line 799) | `_MP4._nums_parser._parse_nums` |

All leaves of the atom trees are generator functions; the call starts
them, and the loop over the result (line 690) resumes their frames, which
is no edge of its own.

## Functions that no site calls

- Public API reached only by clients: `TinyTag.get_image`, the properties
  `TinyTag.audio_offset` and `TinyTag.extra`, `Images.as_dict`,
  `Image.__repr__`. All ran in the tests.
- `TinyTag._parse`: no package caller (B1, J4); it ran only in
  `test_unimplemented_load`.
- `tinytag.__main__._run` is called by the module's `__main__` block.

## Statistics

| | Count |
|---|---|
| Sites | 780 (704 call, 31 decorator, 6 op, 2 getattr, 37 format); 272 with candidates; 3 value sites |
| Ledger entries | 737 (704 call, 31 decorator, 2 getattr) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 793 / 76 (3) / 3 (5 nodes) / 37 |
| Default rejections | 1, deciding 61 sites |
| Nodes | 82 (3 modules, 79 functions) |
| Edges | 437: 134 in the package, 303 outside |
| Edges that the trace confirms | 391 of 437 (89.5%) |
| Edges only from reading | 46 (9 inside, 37 outside): 35 of `__main__`, 10 of the debug branches (J1), 1 `_Flac._parse -> io.BytesIO.seek` |
| Trace edges rejected | 9 |
| Functions that the tests run | 74 of 79 (the 5 of `__main__` do not run) |
