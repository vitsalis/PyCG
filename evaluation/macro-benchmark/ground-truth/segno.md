# segno: judgements of the ground truth

Release 1.6.6 (commit `9b67a3f`). Analysed source: `segno/` (7 modules,
192 functions with 8 lambdas, 8 classes). `pyproject.toml` declares
`requires-python = ">=3.5"`, but the modules use f-strings, so the package
imports only on Python 3.6 and later; the edges are those of 3.6 and later.
Classifier "Operating System :: OS Independent": the Windows branches run.
The dependency `importlib-metadata>=3.6.0; python_version < '3.10'` is not
installed for the trace and is named as a missing module.

The ledger is `segno.ledger`; `segno.json` and `segno.added.json` are
generated from it. `segno.rejected.json` holds 17 trace edges of client
streams (J1).

## Status (for a resumed session)

- Done (2026-11-23 01:00); audit and ruling applied (2026-11-23): every
  site decided; `check.py --write segno` and `check.py segno` report no
  error. 782 edges (292 inside, 490 outside); the trace confirms 723
  (92.5%), 59 come from reading only (24 inside, 35 outside); 18 trace
  edges rejected; 188 of 192 functions run (not run: `QRCode.show`,
  `QRCode.show.delete_file`, `writers.write_svg_debug`,
  `writers.write_terminal_win`).
- The audit (`segno.audit.md`) found F1 and F2; the referee's ruling
  (adopted by the lead) removed 12 outside edges (J1) and added 2 (J5).
  Codex round 1 added 2 outside edges (J4) and corrected one site
  (no edge change); the version_range item was decided by a second ruling (J9).
  Rule C for the three modules whose docstring excludes them from the
  public API was confirmed.
- 1456 ledger entries, 444 value sites, 5 default-rejection lines for 8
  candidates (3529 candidate-site pairs: `QRCode.__getattr__` and
  `QRCodeSequence.__getattr__` 664 each, `Buffer.__getitem__` and
  `Segments.__getitem__` 481 each, `Buffer.__len__` 291,
  `Segments.__len__` 295, `Segments.__iter__` 267, `QRCode.__eq__` 386).
- Pass 2 reviewed the default rejections, the value sites, the added
  edges, the stream receivers of the writers and the binding of the
  package calls; it removed 3 edges (J6, J7).
- The first draft was merged from scratch decision files
  (`$TMPDIR/b7-gt-segno/d_*.txt`, `merge.py`, which also filled plain
  builtin calls and `str.join`/`str.format` calls on literals by an AST
  match, each reviewed in the graph). The ledger is the source of truth:
  edit it directly.

## Architecture, as the ledger uses it

- `segno.make` (and `make_qr`, `make_micro`) call `encoder.encode`, which
  returns an `encoder.Code` namedtuple; `QRCode.__init__` copies its fields
  into slots. `make_sequence` maps `QRCode` over the codes of
  `encoder.encode_sequence`; `tuple.__new__` iterates the map inside
  `QRCodeSequence.__new__` (975:31), which therefore calls
  `QRCode.__init__` (the trace has this edge).
- `QRCode` has `__slots__` and a `__getattr__` for plugin converters
  (`to_<name>`). Every slot is set in `__init__`, and no property raises
  `AttributeError`, so no attribute load of the package misses on a
  QRCode. `QRCodeSequence` (a tuple) forwards a missing attribute to its
  one QRCode (`getattr(self[0], item)`, 1016:27).
- `encoder.py`, `utils.py` and `writers.py` say "DOES NOT belong to the
  public API" in their module docstrings: their functions are private
  (rule C), and their parameters take what the package passes.
- `writers.colorful` decorates `write_svg`, `write_png` and `write_ppm`;
  the module names are then bound to `colorful.decorate.wrapper`, which
  calls the original function (96:21). `writers.save` dispatches through
  `_VALID_SERIALIZERS`.
- `writers.writable` is a `@contextmanager` generator function: a call is
  `contextlib.contextmanager.helper` and `writers.writable` (fastjsonschema
  precedent). The trace misses the second (tracer defect T1).

## Judgements

**J1. The stream receivers of the writers (B4, B5; audit F1, the
referee's ruling, adopted by the lead).** The writers get `out` from
`QRCode.save` (via `writers.save`) or from the package itself. Both public
`save` methods are annotated `out: IO[AnyStr] | str` in the shipped stub
(`segno/__init__.pyi:91`). The annotation takes precedence over the
per-format tables of the docstring ("Filename or io.BytesIO", "Filename or
io.StringIO", `segno/__init__.py:636-923`), and `IO[AnyStr]` fixes no
concrete stream class, so a client stream is opaque (B5). The ruling: "A
shipped stub's abstract stream annotation takes precedence over concrete
stream classes named in narrower per-format documentation; those client
streams remain opaque under B5. Concrete streams supplied by the package
retain their method edges at the sites they can reach." So `f.write` is:
- text writers (`writable(out, 'wt')`): `io.TextIOWrapper.write` (a file
  name; the default `sys.stdout` of `QRCode.terminal`);
- binary writers (`'wb'`): `io.BufferedWriter.write` (a file name);
  `write_png` also `io.BytesIO.write` (the package's own BytesIO of
  `as_png_data_uri`) and `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`
  (the `.png` temporary file of `QRCode.show`), except at 603:18, which
  needs a truthy `dpi` that `show()` never passes;
- `write_svg` (`writable(out, 'wt', encoding)`, encoding never None):
  `io.TextIOWrapper.write` for a file name, and for any stream (the
  package's BytesIO of `svg_inline` and `as_svg_data_uri`, a GzipFile, a
  client stream) the `write` of the codecs StreamWriter that `writable`
  wraps around it (J4).
The writer's first reading (per-format documented classes as B4 types)
gave 12 more pairs; the ruling removed them (`io.StringIO.write` from
write_eps.write_line, write_terminal, write_tex, write_txt, write_xbm and
write_xpm; `io.BytesIO.write` from write_pam, write_pbm, write_pdf,
write_pdf.write_string and write_ppm; `io.BytesIO.tell` from write_pdf),
and the 12 traced pairs are rejected in `segno.rejected.json`. Also
rejected: 4 trace edges to `func_wrapper` from the tests' temporary files
(write_eps.write_line, write_pdf, write_pdf.write_string, write_txt), and
`write_terminal_compact -> io.StringIO.write`. 17 rejected trace edges in
all.

**J2. The optional import of `importlib_metadata`
(`segno/__init__.py:953-957`).** Both sides run (README, Judgements):
`importlib_metadata.entry_points` (a declared requirement below 3.10, not
installed: a missing module) and `importlib.metadata.entry_points`. The
item `ep` of the missing module's result has no stub path, so only
`importlib.metadata.EntryPoint.load` is named at 961:33.

**J3. The forwarding of `QRCodeSequence.__getattr__` (1016:27; B3,
"Forwarded attribute names").** The sequence forwards a name that tuple
lacks to its one QRCode. The callees are the six documented properties of
QRCode (`version`, `error`, `mode`, `designator`, `default_border_size`,
`is_micro`; the tests read five of them through a sequence,
`tests/test_structured_append.py:24-38`), and `QRCode.__getattr__` for the
documented plugin names `to_<name>` (`docs/plugins.rst:60`,
`docs/artistic-qrcodes.rst:28`). `QRCode.mode` is an edge from reading
only.

**J4. The codecs of the SVG writer (66:43, 270:16).** `writable` wraps a
stream in `codecs.getwriter(encoding)(stream)`. The encoding is a string
that selects a library class by name. The admitted values are the default
"utf-8" (`write_svg`, the cli's `--svgencoding`), the "ISO-8859-1" that the
tests pass (`tests/test_svg.py:373`, `tests/test_issue82_svg_inline.py:323`),
and the "ascii" of the tested cli configuration `--svgencoding=ascii`
(`tests/test_cli.py:394-396`). The writer first left ascii out because
that test only builds the configuration; Codex round 1 showed that the
django-constance test-configuration ruling (b) asks for a test that gives
the configuration through the supported interface, not for a test that
runs the selected implementation, and admitted parameters combine
(django-environ ruling): `--svgencoding=ascii` with an `.svgz` output makes
`writers.save` pass a gzip stream, which `writable` wraps. So the classes are
`encodings.utf_8.StreamWriter`, `encodings.latin_1.StreamWriter` and
`encodings.ascii.StreamWriter`, and their inherited `write` is named by the
receiver class. Other codec names are the client's choice.

**J5. Versions and implementations (audit F2, the referee's ruling,
adopted by the lead).** `requires-python = ">=3.5"`; the f-strings
exclude 3.5, and no support drop excludes 3.6 (the removal of the 3.6 test
environment in 0.3.3 withdrew no support; the drop of 1.6.0 concerns
Python 2.7). So CPython 3.6 is admitted, where the compiled pattern is
`_sre.SRE_Pattern` (`re.Pattern` from 3.7): the three `match` calls
(`encoder.py:1319:39`, `helpers.py:329:69`, `345:64`) name both
`re.Pattern.match` and `_sre.SRE_Pattern.match` (configargparse, funcy,
pypinyin precedents; +2 graph edges). No other version branch remains in
the package apart from the import of J2. The CI tests CPython 3.9 to 3.13
and PyPy 3.10 (`.github/workflows/ci.yml:16`), so PyPy is admitted; no
callee name of the ledger differs on PyPy.

**J6. The internal check of `add_codewords` (`encoder.py:504-506`,
`# pragma: no cover`).** `ValueError('Internal error: ...')` runs only if
the codewords do not fill the encoding region. A check of the tables,
reading `consts.py` with `ast` (nothing imported or run), found that for
every version 1 to 40 and every error level the total codewords of `ECC`
equal the data modules of the standard's formula divided by 8, and that
the remainder bits of `make_final_message` (lines 545-551) are the rest;
the four Micro versions also match (36, 80, 132 and 192 modules, with the
4-bit last codeword of M1 and M3). So the check cannot fail under the
package's own values (B1; python-barcode J7, markdown2 J6): 505:25 and
506:47 have no edges (`add_codewords -> <builtin>.ValueError` goes; the
other `len` and `Buffer.__len__` edges stay through 488:26 and 504:18).

**J7. The version check of `make_epc_qr` (`helpers.py:648-649`,
`# pragma: no cover`, "This shouldn't happen").** `_make_epc_qr_data`
raises for a payload over 331 bytes (line 596). The payload is bytes, so
`make_qr` encodes it in one segment, in byte mode or in a more compact
mode; 331 bytes in byte mode need 4 + 16 + 331 * 8 = 2668 bits, and
version 13 with level M holds 2672 (`consts.py:243`); `boost_error=False`
keeps level M. So the version is never above 13, and the `ValueError`
(649:25) and `qr.designator` (649:94) have no edges.

**J8. Outside names checked against the micro-benchmark README** ("Names",
"Edges", "Missing modules"; 2026-11-23, after the lead opened that file).
Every outside callee of the ledger follows those rules: functions by the
path the package imports (`urllib.request.pathname2url`, `os.unlink`,
`functools.reduce`, `operator.lt`); methods by the class of the receiver,
also a private or inheriting class (`argparse._ArgumentGroup.add_argument`,
`encodings.utf_8.StreamWriter.write`, `collections.defaultdict.items`,
`io.TextIOWrapper.writelines`, `tempfile._TemporaryFileWrapper.close`);
library closures by where they are defined
(`contextlib.contextmanager.helper`,
`tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`,
`ctypes.CDLL.__init__._FuncPtr.__call__`); calls of instances by
`__call__` (`functools.partial.__call__`); explicit instantiation of an
outside class by the class (`io.BytesIO`, `threading.Thread`,
`encodings.utf_8.StreamWriter`); an inherited outside `__init__` through
the nearest outside class (`<builtin>.ValueError.__init__`,
`<builtin>.dict.__init__`); the missing module by its access path
(`importlib_metadata.entry_points`; iteration over a stub gives no items,
so the loop body of `QRCode.__getattr__` runs only for `importlib.metadata`,
which agrees with J2). No name changed. The dependency `png` (pypng 0.0.21,
`deps/segno/`) is imported only by the tests, not by `segno/`, so no
callee comes from it.

## Codex round 1

- Missing `writable -> encodings.ascii.StreamWriter` (66:43) and
  `write_svg -> encodings.ascii.StreamWriter.write` (270:16): applied (J4).
- Metadata, `encoder.py:1253:29`: applied. `normalize_errorlevel` is
  private and both package callers pass `accept_none=True`, so the
  `ValueError` there has no callee; the pair stays through 1260:25.
- Unsure, `encoder.version_range -> <builtin>.ValueError` (1476:21): not
  decided; the edge stays. The package callers pass only versions 1 to 40:
  `_encode` calls it only when `version >= 1`, `bit_length_with_overhead`
  only when `version > 0` (the version is a range item of `find_version`
  or the version of `_encode`), and `number_of_symbols_by_version` only
  after `encode_sequence` refused `version < 1`. Each such version is the
  result of `int(version)` in `normalize_version` (line 1173), checked by
  `0 < version < 41`, or an item of `range`. The raise is reachable from a
  package call only if `int()` can return an `int` subclass whose
  comparisons disagree between `normalize_version` and `version_range`
  (B5: repeated checks need not agree). Whether `int(x)` copies a
  subclass result of `__int__` (or of `__index__`/`__trunc__`) to an exact
  `int` on CPython 3.6 to 3.9 and on PyPy 3.10 is decided in C
  (`Objects/abstract.c`, `PyNumber_Long`) and in PyPy's
  `pypy/objspace/std/intobject.py`; neither is among the dependency
  sources (`_cpython/` holds only `Lib/` of 3.10, 3.11 and 3.13; `_pypy/`
  holds `pypy/module` and the libraries, not `objspace`). With those two
  files the question is settled: if every admitted runtime copies to an
  exact `int`, the pair goes and its trace edge (a direct test of the
  private helper, `tests/test_encoder.py:508`) moves to the rejected edges.

  Branch review (2026-11-23): the dependency sources still hold no C code
  of the interpreter (`_cpython/` has `Lib/` for 3.10, 3.11 and 3.13, and
  `Modules/` for two versions, but no `Objects/`, and no 3.6 to 3.9). The
  facts that decide the case: an `int` subclass that only overrides
  comparisons inherits int's `nb_int` slot, which returns an exact `int`
  copy, so `int(version)` strips it; only a subclass whose own `__int__`
  returns an `int` subclass (behaviour that CPython has deprecated since
  bpo-17576) can survive, and whether `PyNumber_Long` then copies the
  result to an exact `int` differs between CPython releases (the writer's
  recollection, not checked against a source). The question needs either
  `Objects/abstract.c` of CPython 3.6 to 3.9 and PyPy's
  `pypy/objspace/std/intobject.py`, or a ruling on whether a client's
  `__int__` that returns a strict `int` subclass (out of the protocol of
  `__int__`, "should return an int") is an admitted value of the
  documented `version: int, str or None`. Sent to the lead, unapplied;
  decided by the second ruling: see J9 (the pair is removed).

**J9. `encoder.version_range -> <builtin>.ValueError` (1476:21; the
referee, `b7-ruling-segno-2.md`, adopted by the lead).** A client `int`
or `str` subclass is an admitted value of `version: int, str or None`,
and deprecated behaviour that an admitted runtime accepts stays in scope.
But on every admitted runtime `int()` returns an exact `int`: CPython 3.6
and later copy a strict subclass that `__int__` returns (`PyNumber_Long`,
`_PyLong_Copy`; bpo-26984), and PyPy 3.6 7.0 and later reconvert it
(CPython 3.5 does not, but the f-strings exclude 3.5). So
`normalize_version` gives exact ints, `0 < version < 41` and the callers'
Micro guards keep `version_range` to 1 to 40, and its `ValueError` never
runs from a package call: the pair goes (-1 outside edge), and the trace
edge, from a direct test of the private helper with 41
(`tests/test_encoder.py:508`), is rejected (18 rejected trace edges).
