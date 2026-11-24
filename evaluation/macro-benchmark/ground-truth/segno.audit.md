STATUS (2026-11-23): audit closed. F1 and F2 were upheld by the referee and applied by the writer (98a5eb8); the re-check (section 7) passed. Nothing is open.

# Audit of the segno ground truth (batch 7)

Auditor: audit7-segno (Claude), blind to the writer's work until the blind
answers were saved. Ledger audited: `segno.ledger` as of 2026-11-23 (791
edges, 292 inside, 499 outside; `check.py segno`: no errors).

## 1. Blind re-derivation

Skeleton made without the ledger in `$TMPDIR/b7-audit-segno/`
(`check.py --benchmark-dir ... --skeleton segno`: 2887 ledger sites, 444
value sites). Sites numbered in (module, line, column) order; draw with
`random.Random(20261123)`. The blind answers are saved as evidence in
`$TMPDIR/b7-audit-segno/blind-answers.md` (with `sample.json` and the draw
script `scripts/draw.py`).

- **Plain sample:** 70 of the 2443 sites that are not value sites. No kind
  dominates (call 40%, getattr 27% of the frame), so a plain draw: 30 call,
  17 getattr, 8 iter, 7 op, 4 truth, 2 getitem, 1 mapping, 1 decorator.
- **Value sample:** 296 of the 444 value sites are `EC(...)` calls of the
  namedtuple in `consts` (one callee dominates). A fresh
  `random.Random(20261123)` drew 10 EC sites, then 60 of the 148 other
  value sites. All 148 non-EC value sites were then checked by group
  (section 3.2).

| Sample | Sites | Agree | Disagreements |
|---|---|---|---|
| Plain | 70 | 70 | 0 |
| Value | 70 | 50 | 20 sites: 17 writer callees that the rules do not support (F1), 3 auditor errors |

- **Writer callees that the rules do not support (17 sites, F1):**
  `io.StringIO.write` or `io.BytesIO.write` at the `write` sites of the
  writers for EPS, PDF, TXT, PBM, PAM, PPM, XPM, XBM, TeX and ANSI
  (writers 396, 645, 727, 766, 830, 866, 868, 899, 930, 939, 940, 975,
  977, 982, 988, 1019, 1022). See F1.
- **Auditor errors (3 sites):** writers 610:22, 615:18, 616:14. I missed
  `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`: `QRCode.show`
  saves into its own `NamedTemporaryFile(..., suffix='.png')`
  (`__init__.py:423-425`), so `write_png` gets that wrapper and
  `f.write` is its `func_wrapper`. The writer is right.
- Everything else agrees, also the outside names (`argparse.ArgumentParser.add_argument`,
  `operator.lt`/`gt`, `functools.partial.__call__` with the partial's
  package callback, `encodings.utf_8.StreamWriter.write` in
  `write_svg_debug`, the ten serializer callees at `writers.py:1603`, the
  `@colorful` wrapper as the callee of `write_svg`/`write_png`/`write_ppm`
  calls).

## 2. Findings

### F1 (high; 12 edges outside the package; needs the lead's ruling, or the referee's if the lead finds it is not decided): the documented `io.StringIO`/`io.BytesIO` of `QRCode.save` are not receivers (J1)

Evidence. J1 names `io.StringIO.write` and `io.BytesIO.write`/`.tell` as
receivers of `f` in the writers because the docstring of `QRCode.save`
says "Filename or io.BytesIO" / "Filename or io.StringIO" per kind
(`segno/__init__.py:636-923`). But `segno/__init__.pyi:91` annotates
the same parameter: `def save(self, out: IO[AnyStr] | str, ...)` (also
`QRCodeSequence.save`, `__init__.pyi:105`). The README:

- B4: "The `.pyi` stubs that a package ships next to its modules count as
  annotations (pypinyin)"; "When an annotation and the documentation both
  exist and differ, the annotation decides"; "An abstract type (`Mapping`,
  `Iterable`, `Callable`, a `Protocol`, ...) does not fix the class."
  `typing.IO[AnyStr]` is abstract.
- The batch-6 ruling "An annotation that is wider than the documentation
  (B4; prometheus-client; the referee)": "B4 already decides: the
  annotation has precedence where the two differ. `Enum`'s `states` is
  `Sequence[str]`; the documentation's `List[str]` and the tests' lists add
  no `list.index` edge." This is the same case: an abstract annotation,
  a concrete class in the docstring, and tests that pass that class.
- B2/B5: "A value from outside the package that the client passes is a
  client callback, whatever the documentation shows"; a method call on a
  client-supplied object has no outside callee.

So a client stream at `QRCode.save`/`QRCodeSequence.save` is opaque, as
the writer already treats it at `QRCode.terminal` (`out: TextIO | str |
None`, `__init__.pyi:88`) and for the tests' `NamedTemporaryFile`. The named receivers stay
only where the package makes the stream: `open()` of a path
(`io.TextIOWrapper`, `io.BufferedWriter`), the default `sys.stdout`, the
package's `io.BytesIO` of `as_png_data_uri` (so `write_png ->
io.BytesIO.write` stays), the codecs StreamWriter of `write_svg`, the
`GzipFile` of `.svgz`, and the tempfile wrapper of `QRCode.show`.

Edges that go (all 12 are traced; each moves to `segno.rejected.json`
with the reason "the tests pass an io.StringIO/io.BytesIO to
QRCode.save; `out` is annotated `IO[AnyStr] | str` (`__init__.pyi:91`),
which fixes no class (B4, the prometheus-client ruling); a client stream
is opaque (B5)", as for the existing `func_wrapper` rejections):

- `io.StringIO.write` from `write_eps.write_line`, `write_terminal`,
  `write_tex`, `write_txt`, `write_xbm`, `write_xpm` (6);
- `io.BytesIO.write` from `write_pam`, `write_pbm`, `write_pdf`,
  `write_pdf.write_string`, `write_ppm` (5);
- `io.BytesIO.tell` from `write_pdf` (1).

Net: 791 to 779 edges (inside unchanged at 292; outside 499 to 487);
rejected trace edges 5 to 17. The ledger entries at the `write`/`tell`
sites of these writers lose the callee and their notes change (44
entries: 29 with `io.StringIO.write`, 15 with `io.BytesIO.write` or
`.tell`; the 9 `write_png` entries keep `io.BytesIO.write`).

The writer's counter-reading (J1: the per-kind table is the narrower
contract and so decides) has no support in the README: the rule is that
the annotation decides where the two differ, and the prometheus ruling
applied it to an annotation wider than the documentation. I ask the lead
to confirm. If the lead keeps J1, the README needs a sentence that a
per-kind docstring table overrides a wider stub annotation, which would
contradict the prometheus ruling.

### F2 (low; +2 edges outside the package; naming): the compiled pattern on Python 3.6

`requires-python = ">=3.5"` (`pyproject.toml:13`); the writer (J5) takes
3.6 and later because of the f-strings. On CPython 3.6 a compiled pattern
is `_sre.SRE_Pattern`, which has no public path (`re.Pattern` is the
name from 3.7; the writer should confirm this against the 3.6 sources
before adding the name). The README: "Include names across the
release's admitted Python 3 versions ... Retain an older fallback name
where that runtime lacks the later public path", and "a builtin type
without a public path is named as the tracer names it" (autojump). So
`_sre.SRE_Pattern.match` is a second name beside `re.Pattern.match` at
`encoder.py:1319:39` (`is_alphanumeric`) and `helpers.py:329:69` and
`345:64` (`make_vcard_data`): +2 edges. No other callee name of the
ledger differs on 3.6 (I checked the stream, functools, contextlib,
tempfile, codecs and argparse names; `importlib.metadata` is not reached
there because `importlib_metadata` is a declared requirement below 3.10).
If the lead rules that the f-string floor does not admit 3.6 as a
"supported version" (it is declared, and it works), this goes.

### Not findings (checked and agreed)

- `birthday`/`rev` (`helpers.py:160`, `326`, `342`): the stub says `str |
  datetime.date | None`, so `datetime.date.strftime`. A client
  `datetime.datetime` (a subclass with its own `strftime`) is a client
  choice of subclass; the annotation names `date`. No change.

## 3. Exhaustive checks

### 3.1 Default rejections (5 lines, 8 candidates, 3529 pairs)

I read each default against every place where the package can have a
QRCode, a QRCodeSequence, a Buffer or a Segments, and listed the explicit
sites of each default (`check.py --report segno --default <c>`). All
eight are right.

- `QRCode.__getattr__`, `QRCodeSequence.__getattr__` (664 each): every
  QRCode slot is set in `__init__` (`__init__.py:225-239`); no property
  raises `AttributeError` (`get_version_name`, `get_error_name`,
  `get_mode_name` raise `ValueError`); the package loads on a
  QRCodeSequence only `terminal` and `save` (`cli.py:283`, `285`), which
  the class defines. The only real call is the forwarding at
  `__init__.py:1016:27`, which the ledger accepts (J3).
- `Buffer.__getitem__`, `Segments.__getitem__` (481 each): a Buffer is
  subscripted only at `encoder.py:502:39` and a Segments only at
  `__init__.py:239:35`, both accepted. Buffer has `__getitem__` but no
  `__iter__`, so an iteration of a Buffer would call it: none happens (the
  package never iterates a Buffer; `Buffer(iterable)` is always called
  without an argument; `extend` takes bytearrays and generators).
- `Buffer.__len__` (291), `Segments.__len__` (295): the accepted sites are
  `_encode` 229/231/233, `add_codewords` 488/504, `boost_error_level` 269
  and `QRCode.__init__` 239:50; 506:47 is J6. No truth test of a Buffer
  or a Segments exists.
- `Segments.__iter__` (267): only `_encode` 225:20 iterates a Segments.
- `QRCode.__eq__` (386): the package never compares, hashes or looks up a
  QRCode (it is unhashable).

### 3.2 Value sites (444)

The 296 `EC(...)` calls and `Code(...)` (`encoder.py:253`) are namedtuple
constructors: no edge (README, namedtuple rule). I checked the 148 others
by group: the bound methods (`append_bits`, `extend`, `add_segment`,
`list.append` aliases, `bytes.find`, `re.Pattern.match`), the partials
(`writeline`, `writestr`, `row_filter`, `set_color`, `sa_info`,
`_replace_quotes`, the `quote` partial at 307:20), the strategy values
(`is_better`, `eval_mask`, `mask_pattern` with the eight mask functions,
`is_encoding_region`, `iterfn`, `make` in the cli, `serializer` at 1601
and 1603, `f` in the `@colorful` wrapper), the codecs class at 66:43, and
the 61 `write` sites. All agree with my reading except the
`io.StringIO`/`io.BytesIO` callees of F1.

### 3.3 Judgement calls of `segno.md`

| J | Opinion |
|---|---|
| J1 streams | The file-name, `sys.stdout`, package-BytesIO, tempfile and codecs receivers are right. The documented client classes are not supported: F1. The rejection of `write_terminal_compact -> _io.StringIO.write` and of the 4 `func_wrapper` edges is right under either reading. |
| J2 optional import | Supported (README, Judgements: both sides of an optional import run; missing-module naming; iteration over a stub gives no items). |
| J3 forwarding | Supported by "Forwarded attribute names (B3)": the six properties are documented names on the admitted receiver; `to_<name>` is documented (`docs/plugins.rst`). |
| J4 codecs | Supported by the aiocache clause of B2 and django-constance ruling (b) (a tested configuration that selects a concrete library implementation by name): utf-8 (default) and ISO-8859-1 (`tests/test_svg.py:373`). |
| J5 versions | Supported (f-strings: 3.6+; PyPy by the CI job, the path ruling). F2 is its one naming consequence. |
| J6 `add_codewords` check | Verified myself: a script of my own reads `consts.py` with `ast` and a small evaluator (no import, no exec), rebuilds the free modules of `make_matrix` + finder + alignment patterns, and compares them with the codeword bits of `make_final_message` (blocks' total codewords x 8 + remainder bits, minus 4 for M1 and M3). All 168 (version, level) pairs are equal, so `idx != len(codewords)` cannot be true (bits are never more than modules; `islice` caps each block at `num_data`). Removal supported (B1, "a check that cannot fail under the package's own values"). Script: `$TMPDIR/b7-audit-segno/scripts/j6_check.py`. |
| J7 EPC version | Verified: the payload is at most 331 bytes (`helpers.py:596`); it contains newlines, so byte mode; 4 + 16 + 331 x 8 = 2668 bits, and `SYMBOL_CAPACITY[13][M]` = 2672 (`consts.py:243`), with `boost_error=False` and `error='m'`. Version 13 is never exceeded; 649:25 and 649:94 have no edges. Removal supported. |
| J8 names | Agreed, with F2. |

Rule C for the modules whose docstring says they are not public
(`encoder.py:10`, `utils.py:11`, `writers.py:11`; `consts.py` says
"Internal module"): the README's "its docstring or the documentation
marks it private" does not say "module docstring". The smaller extension
is that a module docstring that marks the module as not public API is
documentation that marks every function defined in it private;
`docs/api.rst` documents only `segno` and `segno.helpers`, which agrees. I
agree with the writer. Effect: their parameters take the package's
values, and `write_svg_debug` (never called) is judged as public.

### 3.4 Other checks

- **Functions that no site calls:** the public API (`QRCode.matrix_iter`,
  `png_data_uri`, `svg_data_uri`, `svg_inline`, `symbol_size`, `show`,
  `__eq__`, `QRCodeSequence.__getattr__`, `make_micro`, the seven
  `helpers.make_*`) and `write_svg_debug`. Each keeps its out-edges.
- **Binding check:** every call of a package function binds, including
  the `@colorful` chain (`as_svg_data_uri` -> wrapper -> `write_svg` with
  `cm`), the partials (`write_line`, `write_string`,
  `row_to_color_values`, `_StructuredAppendInfo`) and the cli's
  `make(..., **kw)`. None fails.
- **Rejected trace edges (5):** right (client streams).
- **Added edges (55):** I read all of them; all are supported (`QRCode.show`
  and `delete_file`, the Windows terminal, the missing
  `importlib_metadata`, `writable` as a generator function under
  `contextmanager`, the error branches 1029 and 1489, the merge branch
  1571, `cli -> main` under `__main__`).
- **Outside names (145):** read against the micro-benchmark rules; agreed
  except F2.
- **Lazy objects:** `map(QRCode, ...)` is iterated by `tuple.__new__` in
  `QRCodeSequence.__new__` (975:31; the trace has it); the generator
  expressions of `pack_row`, `toints` and `to_binary` keep their callees
  in the enclosing function. Agreed.

## 4. Summary of edge changes

| Finding | Severity | Edges |
|---|---|---|
| F1 documented client streams | high (ruling) | -12 (all traced; 12 more rejected trace edges) |
| F2 `_sre.SRE_Pattern.match` on 3.6 | low | +2 |

With both: 791 to 781 edges (inside 292 unchanged).

## 5. README and tools

- The tools worked as documented (`--skeleton` and `--report` on a scratch
  benchmark directory, `--report --default`).
- Rule C says "its docstring or the documentation marks it private"; it
  does not say whether a module docstring ("DOES NOT belong to the public
  API") marks the functions of the module. A sentence would help (section
  3.3 gives the reading that I and the writer both use).
- B4 begins "When a parameter's annotation or documentation fixes a
  concrete type"; J1 shows that a writer can read a per-kind docstring
  table as fixing the type despite a wider stub annotation. The
  prometheus-client ruling decides it, but it sits far from B4: a pointer
  in B4 to that ruling would prevent the misreading.

## 6. Check under the batch-7 platform ruling (README, "Rulings for batch 7", commit fb7ffd8)

The ruling: a platform is supported when the release declares it
(classifiers, documentation) or establishes it by its own platform test
jobs; a platform branch in the code alone admits nothing.

What segno 1.6.6 declares:

- Classifier `Operating System :: OS Independent` (`pyproject.toml:20`).
  This declares every operating system, so Windows is declared. It is not
  the pyfiglet case, which declares only `Operating System :: Unix`.
- The documentation also states the Windows behaviour. The docstring of
  the public `QRCode.terminal` (`segno/__init__.py:518-520`: "Under
  Windows, no ANSI escape sequence is generated but the Windows API is
  used ...") is rendered by `docs/api.rst:7-9` (`automodule:: segno`,
  `:members:`).
- The CI has one job on `ubuntu-24.04` (`.github/workflows/ci.yml:12`).
  It restricts nothing: no explicit restriction or support drop for any
  platform exists in the release (`CHANGES.rst` drops only Python 2.7
  and PyPy2 testing).

So the `win32` branch of `QRCode.terminal` (`__init__.py:532-540`) runs,
and the body of `write_terminal_win` (`writers.py:1025-1064`) runs past
`ctypes.windll` (1039). On any other platform `ctypes.windll` raises
`AttributeError` there, but one supported platform is enough.

The edges that depend on Windows, all in the ledger and all supported:

- inside (2): `QRCode.terminal -> writers.write_terminal_win` (537:43),
  `write_terminal_win -> utils.matrix_iter` (1048:27);
- outside (7), from `write_terminal_win`: `ctypes.CDLL.__init__._FuncPtr.__call__`
  (1039:50, 1041:60), `ctypes.create_string_buffer`, `<builtin>.OSError`,
  `struct.unpack`, `functools.partial`, `functools.partial.__call__`
  (1056, 1061, 1063), `io.TextIOWrapper.write` (1057, 1062, 1064).

Console streams: on Windows the default `sys.stdout` and `sys.stderr` are
still `io.TextIOWrapper` objects (over a raw `_io._WindowsConsoleIO` in a
console). The package calls only their `write` and `writelines`, so the
names `io.TextIOWrapper.write` and `io.TextIOWrapper.writelines`
(`cli.py:279`) are right on every platform. No raw console class is
named in the ledger, and none needs to be: the package never calls the
raw stream (the batch-7 naming ruling for `_io._WindowsConsoleIO` does
not apply). The other platform-sensitive callees keep their names on
Windows: `open()` gives `io.TextIOWrapper` and `io.BufferedWriter`, and
`tempfile.NamedTemporaryFile` returns `tempfile._TemporaryFileWrapper` on
every platform (so `func_wrapper` and `_TemporaryFileWrapper.close` stand).
`os.unlink`, `webbrowser.open_new_tab` and `urllib.request.pathname2url`
are named by the path that the package imports (`pathname2url` is
`nturl2path.pathname2url` on Windows, but the path rule keeps the
imported name).

Result: no change from this ruling. F1 and F2 are unchanged.

## 7. Re-check of the committed ledger (98a5eb8, against 4bc6ba4)

The referee upheld F1 and F2 and confirmed the reading of rule C
(`b7-ruling-segno.md`; README, "Rulings for batch 7"). I re-checked the
committed segno files against the ledger that I audited.

- **Checker:** `check.py segno` reports no errors: 781 edges (292
  inside, 489 outside); the trace confirms 724; 17 trace edges rejected.
- **Ledger, entry by entry:** I parsed both ledgers and compared the
  callees of every entry. The site set is the same, and exactly 48
  entries changed:
  - 44 lost one callee, exactly the sites of the ruling's table:
    `io.StringIO.write` at 29 entries (write_eps.write_line 2,
    write_terminal 7, write_tex 10, write_txt 2, write_xbm 5,
    write_xpm 3), `io.BytesIO.write` at 12 (write_pam 2, write_pbm 4,
    write_pdf 3, write_pdf.write_string 1, write_ppm 2) and
    `io.BytesIO.tell` at 3 (write_pdf 693:37, 697:33, 700:33);
  - 3 gained `_sre.SRE_Pattern.match` beside `re.Pattern.match`
    (`encoder 1319:39`, `helpers 329:69`, `helpers 345:64`);
  - 1 lost `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper`
    (`writers 603:18`; see below).

  No rejection, exclusion or default changed. Only the notes of the
  changed entries and the header comment changed, and they now give the
  reason of J1.
- **The referee's site-only correction at 603:18 is right.** I checked it
  myself. `QRCode.show` calls `self.save(f, scale=scale, dark=dark,
  light=light, border=border)` (`__init__.py:425`) and passes no `dpi`.
  So `writers.save` and the `@colorful` wrapper call `write_png` with its
  default `dpi=None` (`writers.py:469`), and `if dpi:` (602) skips the
  `pHYs` write at 603. No other package flow gives `write_png` the
  temporary file. The site keeps `io.BufferedWriter.write`, and
  `io.BytesIO.write` stays because `as_png_data_uri` forwards the
  client's `dpi` through `**kw`. The pair `write_png -> func_wrapper`
  stays in the graph through the other eight `write` sites (598:14 and
  others), so no graph edge changes.
- **Graph:** exactly 12 edges went (the 12 caller-callee pairs of F1) and
  2 came (`is_alphanumeric -> _sre.SRE_Pattern.match`,
  `make_vcard_data -> _sre.SRE_Pattern.match`). `write_png ->
  io.BytesIO.write` stays.
- **Rejected trace edges (17):** the 12 new ones use the trace's names
  (`_io.StringIO.write`, `_io.BytesIO.write`, `_io.BytesIO.tell`). Their
  shared reason is the ruling's: a client-supplied stream, and `out:
  IO[AnyStr] | str` (`__init__.pyi:91`) fixes no concrete stream class
  under B4. The 5 earlier rejections are unchanged.
- **J1 and J5 in `segno.md`:** they now state the ruling. J1 gives the
  annotation precedence, keeps the package-made streams (file names,
  `sys.stdout`, the BytesIO of `as_png_data_uri`, the codecs
  StreamWriter, `GzipFile`, and the temporary file of `show` except at
  603:18), and lists the 12 removed pairs and the 17 rejections. J5
  admits CPython 3.6 and names the three `match` sites. Both agree with
  the ledger.

Verdict: the ruling is applied completely and correctly; nothing else
changed. The audit is closed.

