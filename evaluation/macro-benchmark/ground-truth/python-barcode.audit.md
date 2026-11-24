# python-barcode: independent audit of the ground truth

Release v0.16.1, held as its PyPI sdist (`python_barcode-0.16.1.tar.gz`,
SHA-256 `665ed095…`). Audited files, as the writer left them in commit
57cf06b: `python-barcode.ledger` (390 entries, 79 notes, 53 rejection
lines, 2 exclusions, one default line for 10 candidates),
`python-barcode.json` (126 nodes, 348 edges: 158 in the package, 190
outside), `python-barcode.rejected.json` (1 edge) and `python-barcode.md`
(judgements J1 to J8). `check.py --benchmark-dir macro-benchmark-heldout-4
python-barcode` reports no errors. The trace confirms 264 edges; 84 come
from reading only.

I judged the files by the README's conventions and scope rules (A, B1 to
B5, C). I read the source, `docs/`, `README.rst`, the tests and the
standard-library source of `xml.dom.minidom` as data. I did not run or
import the package, and I used no static analysis tool.

**Result.** The ground truth is complete and precise for every site I
checked: I found no missing edge, no edge that cannot happen and no wrong
name. There are two judgement points for the lead (F1, R1) and one note to
reword (W1). Only F1 can change the graph (+1 edge).

## Findings

| Id | Kind | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | ruling (writer's J5) | `codex.py:57:49` `self.calculate_checksum()` in `Code39.__init__`: `-> barcode.codex.PZN7.calculate_checksum` is rejected | B1's last sentence: an object that the client passes explicitly as `self` to an unbound method of a public class is opaque "unless it is a package instance that fits B1". A `PZN7` (or `PZN8`) fits B1 for `Code39.__init__`: `PZN7.__init__` calls it on itself through `super()` (`codex.py:113`). So `Code39.__init__(pzn7_obj, "X")` has a `PZN7` as `self`, and `add_checksum` keeps its default `True` (`codex.py:47`), so `codex.py:56-57` run and dispatch to `PZN7.calculate_checksum` (`codex.py:118`). The call happens; the `TypeError` of `str += int` comes after it. The writer saw this and took a second initialisation "as outside the rules" (J5), but no rule says so: the README excludes "a client's change to package internals" (reloading a module, deleting a cached object), and `Code39.__init__` is public (dunder names do not count, rule C). No other site changes by this reading: every other explicit base call that a package instance fits names callees that the ledger already has. | +1 if the lead keeps the literal B1 reading (348 to 349); 0 if the lead adds a rule that a constructor run again on a built instance is not considered (then the README should say so) | likely (the reading); the decision is the lead's |
| W1 | wording (note and J7) | `codex.py:169:29` `ValueError(...)` in `Code128._new_charset`, its note, and the second bullet of J7 | The note says that `_buffer` "fills only in charset C" and that the raise "never runs". Under J6's own premise (a client may store any str in `code`) that is false after an error. Example: `bc.code = "²a"` (`"²".isdigit()` is true; no charset holds it). `_build` buffers `"²"` in C (`codex.py:233-234`); `"a"` switches to B (`207`); `self._convert(self._buffer[0])` at `211` raises `KeyError` in `code128.B` (`229`) before `212` empties the buffer. The object is left in charset B with a buffered character. Then `bc.code = ""; bc.build()` reaches `264` in charset B, and `_new_charset("B")` raises at `169`. The edge stays out only by B3: "An object that the package leaves behind after it raised an error to refuse it is not considered" (configargparse precedent). Without J6's premise the state cannot arise: of the characters that `check_code` admits (`codex.py:155`), only the ASCII digits pass `isdigit()`, and charsets A and B encode them. The note and J7 should name this post-error state and B3. | 0 (+1 only if the lead rules that B3 covers an error raised on purpose and not a `KeyError` of a table lookup; I propose that it covers both) | certain (the chain); likely (B3 applies) |
| R1 | remark on J6 (no change proposed) | `codex.py:240:27` `RuntimeError(...)` in `Code128._convert`: callee kept | I agree with J6. B1 limits the "one state" exclusion to private classes (argcomplete's `shlex`), which implies that a client may set the public attributes of a public class; `Code128` declares `code: str` (`codex.py:146`). Against it: no test or document sets `code` after construction (search of `tests/`, `docs/`, `README.rst`), and B2 says that a stored value is what is fed from the parameter, which `check_code` validates. If the lead takes the B2 reading, -1 edge (`Code128._convert -> <builtin>.RuntimeError`), and W1 becomes moot. | 0 (or -1) | likely |
| R2 | stale text (not the ground truth) | `macro-benchmark-heldout-4/projects.toml:9`, `macro-benchmark/README.md:598` | projects.toml says "It has no ground truth and no trace yet"; the README says the set has "no ground truth yet". Both are stale once the ground truths are committed. projects.toml line 8 names `evaluation/loop.py`, the README (line 91) `evaluation/common/loop.py`; I did not open `evaluation/` to see which is right. | 0 | certain |

## Step 1: blind re-derivation

I made the skeleton without the ledger: a scratch directory
`$TMPDIR/heldout4-audit-python-barcode/` with a copy of `projects.toml` and
a `projects` link, and `check.py --benchmark-dir <scratch> --skeleton
python-barcode`. It has 440 sites (387 call, 3 decorator, 11 op, 39
format), 186 with candidates, 25 value sites. I numbered the sites from 0
in (line, column) order, module by module, and drew
`random.Random(20261111).sample(range(440), 70)`, then added every value
site (25, one already drawn): 94 sites (84 call, 1 decorator, 8 format, 1
op; 36 with candidates). Explicit calls are 88% of the skeleton, the
informative kind, so I drew without strata. I wrote the callees of each
site from the source alone (`blind.md` in the scratch directory) before I
opened the ledger, the graph, the judgements or the trace.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random draw | 70 | 66 | 4 |
| Value sites outside the draw | 24 | 24 | 0 |
| **Total** | **94** | **90** | **4** |

The 4 disagreements, all mine:

- **I was wrong (4).** `base.py:43:31`, `base.py:114:31`, `ean.py:120:31`:
  I gave `<builtin>.RuntimeError`. The check cannot fail: `self` is a
  package barcode (J1), and every package `build` returns a list of one str
  (`codabar.py:77`, `codex.py:81`, `277`, `ean.py:111`, `187`, `itf.py:70`,
  `upc.py:98`). `codex.py:169:29`: I gave `<builtin>.ValueError`. The writer
  is right that it adds no edge, but its reason is incomplete (W1).
- **Writer missed an edge (0). Writer edge that cannot happen (0). Naming
  only (0).**

Points that I noted blind, outside the sample, and found in the ledger as I
had them: `SVGWriter.write -> io.BufferedWriter.write` from `generate`'s own
`open` (J4); `BaseWriter.save` and `BaseWriter.write` as callees of
`self.writer.*` (J3); the `except ImportError` side of `writer.py:33-42`
(J8); the receivers of `Barcode.to_ascii`; the six `render` callees of
`Barcode.save`; `PIL.Image.Image.save` in `ImageWriter.save` and `.write`.

## Step 2: dispatch over the class hierarchy (B1)

`Barcode` has no instance (its `__init__` raises, J1). `BaseWriter` is a
receiver of its own methods (J3). `ImageWriter` exists (both sides of the
optional import run). Every row is identical to the ledger.

| Site | Receivers | Callees |
|---|---|---|
| `self.build()` `base.py:41` | the classes that inherit `Barcode.to_ascii`: CODABAR, Code39, PZN7, PZN8, Code128, Gs1_128, ITF | `build` of CODABAR, Code39, Code128, ITF |
| `self.get_fullcode()` `base.py:48`, `110` | every package barcode | the 9 overrides (CODABAR, Code39, PZN7, Code128, Gs1_128, EAN13, EAN8, ITF, UPCA) |
| `self.build()` `base.py:112` | every package barcode | the 7 `build` (CODABAR, Code39, Code128, EAN13, EAN8, ITF, UPCA) |
| `self.render(...)` `base.py:76` (2), `93` | every package barcode | `Barcode.render` (CODABAR), `render` of Code39, Code128, EAN13, ITF, UPCA |
| `self.writer.save` / `.write` `base.py:78`, `94` | BaseWriter, SVGWriter, ImageWriter | the three `save` / the three `write` |
| `self.writer.set_options` / `.render` `base.py:111`, `116`; `writer.set_options` `__init__.py:139` | same | `BaseWriter.set_options` / `BaseWriter.render` |
| `barcode.save` / `.write` `__init__.py:144`, `147`, `149` | the instance that `get` returns | `Barcode.save` / `Barcode.write` |
| `self.calculate_checksum()` `codex.py:57` | Code39 only (J5) | `Code39.calculate_checksum` (see F1) |
| `self.calculate_checksum()` `codex.py:112`, `ean.py:63`, `upc.py:46` | PZN7, PZN8 / the EAN family / UPCA | `PZN7.` / `EAN13.` and `EAN14.` / `UPCA.calculate_checksum` |
| `self._is_char_fnc1_char` `codex.py:204` | Code128, Gs1_128 | both |
| `self._calculate_checksum` `codex.py:271`, `isxn.py:75`, `107`, `122` | Code128 / ISBN10 / ISSN | the class's own |
| `self.build()` `ean.py:118`, `upc.py:106` | EAN family / UPCA | `EAN13.build`, `EAN8.build` / `UPCA.build` |
| 16 `super()....` calls | MRO | the next class's method (`ean.py:201`: EAN8 has no `__init__`, so EAN13's) |
| `barcode(code, writer, **options)` `__init__.py:106` | the 16 classes of `__BARCODE_MAP` | their 14 `__init__` (EAN14 and EAN8 inherit EAN13's) |
| 7 `self.default_writer()`, `Barcode.default_writer()` | | `SVGWriter.__init__` (`base.py:21`; client subclasses that override it are client code, changelog 0.14) |
| 5 callback sites `writer.py:231`, `264`, `281`, `302`, `304` | SVGWriter, ImageWriter (BaseWriter: client callbacks) | the bound methods that the two `__init__` pass |
| `func(args, parser)` `pybarcode.py:99` | | `list_types`, `create_barcode` |

A client's explicit unbound call does not widen any row except F1's:
`Barcode.to_ascii(ean13_obj)` does not fit B1 (EAN13 overrides `to_ascii`
and never calls `Barcode.to_ascii`), so the rejections at `base.py:41` hold.

## Step 3: the sites of the default rejection

The default rejects `Barcode.__repr__` and the nine `__str__` at 68 sites
(662 candidate-site pairs; `check.py --report python-barcode --default
barcode.base.Barcode.__repr__`). I checked the value at each: 39 f-string
fields (codes, digits, checksums, `len()`, file names, colours, font size,
the version string, the class name, the `!r` of a str), 11 `%` operators
(all `int % int`), 9 `print` calls (str literals, `", ".join(...)`, and
`name`, the str that `generate` returns from `save` for a str output), 9
`str.format` calls (on `SIZE` and on a literal; floats and strs). No barcode
and no `BarcodeError` is formatted, printed or converted anywhere in the
package. The default is correct.

## Step 4: the 84 edges from reading only

All are possible:

| Class | Edges |
|---|---|
| Public paths that no test takes (36) | 9 `__repr__ -> get_fullcode`; 6 of `Barcode.to_ascii`, 4 of `EAN13.to_ascii`, 3 of `UPCA.to_ascii`; `Code128.encoded -> _build`; CODABAR: `get -> CODABAR.__init__`, `CODABAR.__init__ -> SVGWriter.__init__`, `CODABAR.build -> str.join` and `-> BarcodeError.__init__`, `Barcode.render -> CODABAR.build` and `-> CODABAR.get_fullcode`; `Barcode.render -> Gs1_128.get_fullcode`; `Barcode.save -> Barcode.render`; 5 `Barcode.write -> render` |
| Error paths that no test takes (16) | 9 more `-> BarcodeError.__init__` (no test makes a package error: `BarcodeError.__init__` is not in `executed`) and the other 3 edges of `check_code`; 3 `-> NotImplementedError`; `Code128._convert -> RuntimeError` (J6, R1) |
| Options that no test sets (5) | `SVGWriter._finish -> toxml` and the 3 gzip edges (`compress`); `generate -> open` (path-like output) |
| BaseWriter as a writer, J3 (2) | `Barcode.save -> BaseWriter.save`, `Barcode.write -> BaseWriter.write` |
| The side of the optional import without Pillow, J8 (2) | `logging.getLogger`, `logging.Logger.info` |
| The command line, never imported by a test (23) | the module's call of `main`, 11 of `main`, 9 of `create_barcode`, 2 of `list_types` |

## Step 5: nodes without a caller

38: 19 modules, 9 `__str__` and `Barcode.__repr__` (only a client's
`str()`/`repr()` or the interpreter calls them), `Barcode.__init__`,
`Barcode.build`, `Barcode.get_fullcode` (J1), the three `to_ascii`,
`Code128.encoded`, `get_class`, `BaseWriter.register_callback` (public API
that the package never calls). Each keeps the out-edges of its body (rule
A); the bodies of `Barcode.__init__`, `build`, `get_fullcode`,
`BaseWriter.save`, `write` and `register_callback` have no call.

## Step 6: rejections, notes and outside callees

- All 53 rejection lines and all 79 notes: every reason holds, except the
  rejection at `codex.py:57:49` (F1) and the note at `codex.py:169:29` (W1).
- All 190 outside edges (73 names). Each callee exists and is named by the
  micro-benchmark rules: minidom methods by the receiver's class
  (`Element.appendChild` and `Document.toxml`/`toprettyxml` are inherited
  from `Node`; `getDOMImplementation` returns `Document.implementation`, a
  `DOMImplementation`); `gzip.GzipFile.*` for `gzip.open(..., "wb")`;
  `io.BufferedWriter.write` for `open(..., "wb")`; argparse through
  `ArgumentParser` and the private `_SubParsersAction`; the six Pillow
  names; `os.path.*` and `functools.reduce` by the imported path (trace
  aliases `posixpath.*`, `_functools.reduce`). The trace confirms every
  name it can see.
- B4/B5: no graph edge rests on a client object. The `dict` methods are on
  the package's dicts, `**kwargs`, or the annotated `options: dict`; `fp`
  is opaque except for `generate`'s own file (J4).
- The rejected trace edge `SVGWriter.write -> _io.BytesIO.write` is the
  tests' `BytesIO` (rule A): correct.

## Step 7: the judgements

- **J1** (Barcode is no receiver): agree. Only `Barcode.__new__(Barcode)`,
  which skips `__init__`, makes an instance; no rule counts an instance made
  without its constructor.
- **J2** (`ImageWriter._init` never raises `RuntimeError`): agree;
  `Image`, `ImageDraw` and `ImageFont` are `None` together
  (`writer.py:37-42`), and then `ImageWriter` is `None`.
- **J3** (BaseWriter is a receiver), **J4** (`io.BufferedWriter.write` at
  `writer.py:413`), **J8** (optional import, `TYPE_CHECKING`): agree.
- **J5**: F1. **J6**: R1. **J7**: agree for the four `RuntimeError`
  checks; the `ValueError` check needs W1's reason.
- T1 does not apply: the package has no `exec`, `eval`, `@contextmanager`
  or thread (search of `barcode/`).

## Tools and README

`check.py` (skeleton, report, `--default`) worked as the README says. The
site finder marks every `.format(...)` and `self._draw.text(...)` as a
value site by name (`self.format`, `self.text`), as documented; the writer
noted each one. The README decides every case here except F1 (a
constructor run again on a built instance) and the scope of B3's
post-error sentence (W1).

## Complete source-first audit, round 3 (2026-11-16)

The full runtime source, tests, documentation and release metadata were read
before comparison with the installed round-2 ground truth. The independent
module model and AST/site inventory were frozen first. Global README exposure
included its existing python-barcode construction and Code128 subclass examples.
No target, test, dependency or generated code was imported or executed.

All 349 pairs and 453 exact site-target relations were checked. The review
covered all 1507 scanner sites, including 1117 without ledger entries, all
662 default candidate decisions, all own call bindings, and every zero-edge
body. It found no false positive, missing pair or site-relation correction.
The graph and ledger remain unchanged. Earlier audit records are historical;
the current Code128 error decisions are J6 and J7 in python-barcode.md.

The review retains the constructor-specific PZN checksum restriction, the
constructible BaseWriter receiver, the package-owned binary file in
SVGWriter.write, and both first-build Code128 error witnesses. The four
singleton-build checks and the absent-Pillow ImageWriter check remain
unreachable. Client callbacks and library objects supplied by clients stay
opaque. No lazy callback ownership correction was needed.

The independent review challenged the BytesIO exclusion because the getting-started
SVG example passes one. The explicit BinaryIO annotation of Barcode.write and
SVGWriter.write decides the role under B4; a concrete example does not replace
an abstract annotation. The client's BytesIO remains opaque. In contrast,
generate's own open(..., "wb") supplies an io.BufferedWriter through Barcode.write,
which independently supports the retained write edge.

Pillow source availability does not make a missing module transparent. Here
PIL is a declared benchmark dependency. Independently, the T_Image and
T_ImageDraw aliases name PIL.Image.Image and PIL.ImageDraw.ImageDraw; the
_image and _draw attribute annotations and _finish return annotation fix these
concrete types. Barcode.save/write pass that rendered Image output into
ImageWriter.save/write. Client-provided output remains opaque.

Concrete DOM, argparse and gzip receiver names were checked against official
CPython 3.9.0 and 3.14.0 source text; Pillow 11.3.0 source confirms Image and
ImageDraw return types. Requires-Python >=3.9 has no upper bound. The exact
primary-source URLs, bytes and SHA-256 identities are recorded in the round-3
evidence manifest. These source samples establish the relevant names; the
audit did not execute or enumerate every supported interpreter release.

Structural and origin checks derive the graph and added-edge file from the
ledger. These checks establish artifact consistency, not semantic correctness.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).

## Complete source-first audit, round 4 (2026-11-16)

A fresh source-first review read all 19 runtime modules, support declarations,
tests and relevant documentation before baseline comparison. Its frozen model
and input identities are retained with the round-4 evidence. Mandatory global
rules had already exposed the published Barcode and Code128 examples; that
exposure is disclosed. No target or dependency code was executed.

The review retains all 349 pairs (158 package, 191 outside), all 453 site-target
relations and all 126 nodes. It found no missing edge, false positive or
site-relation correction. Coverage includes 1,507 source sites, 390 explicit
ledger entries, 1,117 omitted implicit sites, 662 default candidate decisions,
both explicit exclusions and all 42 zero-edge scopes.

The supported scope is CPython >=3.9; the pinned release declares no current
alternative interpreter. The normal/-O/-OO union is the recorded working
assumption, not a user-approved change. Its three assertions introduce no
additional named target: absent-Pillow CLI execution calls None after assertion
removal, while successful ImageWriter construction and minidom's no-feature
DOM implementation make the other checks redundant. Own docstrings are not
read at runtime.

The review independently retained the first-build Code128 exception paths,
PZN constructor-specific checksum dispatch, stored writer callbacks, concrete
package-created binary streams and DOM/Pillow receivers, and the opaque client
BytesIO rejection. Earlier outcome counts and rulings above remain historical.
A count typo in the new frozen model (15 rather than 16 mapped classes) is
recorded separately as a proposal-only correction; the baseline was correct.
