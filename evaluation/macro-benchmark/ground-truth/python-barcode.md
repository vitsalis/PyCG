# python-barcode: judgements of the ground truth

Release v0.16.1, held as its PyPI sdist (`python_barcode-0.16.1.tar.gz`,
SHA-256 `665ed095…`). Analysed source: `barcode/` (root `.`): 19 modules,
107 functions, 0 lambdas, 28 classes. `pyproject.toml` sets
`requires-python = ">=3.9"`, so the supported versions are 3.9 and later.
Pillow is an optional dependency (extra `images`, unpinned).

The ledger is `python-barcode.ledger`; the graph `python-barcode.json` is
generated from it. One trace edge is rejected
(`python-barcode.rejected.json`).

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in python-barcode-review.json (audit record `2026-11-15/python-barcode-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 347 | 0 | 2 | 349 |

- `Code128` retains its nominal `str` input. A client subtype can vary
  indexing independently of iteration, reaching `_convert`'s `RuntimeError`.
- An admitted input can supply a buffer with stateful length and reach
  `_new_charset`'s `ValueError`.
  Neither case needs attribute mutation or reuse after failed construction;
  the client methods stay opaque while their control-flow effects count.

## Architecture, as the ledger uses it

- `barcode.get` (`__init__.py:82`) looks the class up in `__BARCODE_MAP`
  (`__init__.py:36-59`) and calls it. The map holds 16 classes. Their
  `__init__` methods are 14 functions: `EuropeanArticleNumber14` and
  `EuropeanArticleNumber8` inherit `EuropeanArticleNumber13.__init__`.
- `Barcode` (`base.py:16`) is the base of every barcode class. Its
  `__init__`, `build` and `get_fullcode` only raise `NotImplementedError`.
  Its `default_writer` is the class `SVGWriter` (`base.py:21`), so
  `self.default_writer()` runs `SVGWriter.__init__`. No package class
  rebinds `default_writer` or `default_writer_options`.
- `Barcode.render` sets the options of `self.writer`, builds the pattern
  and calls `self.writer.render([code])`. The subclasses that override
  `render` (Code39, Code128, EAN-13, ITF, UPC-A) call it through
  `super().render`; `CODABAR` inherits it.
- `BaseWriter` (`writer.py:78`) stores four callbacks in `self._callbacks`.
  `BaseWriter.render` calls them. `SVGWriter.__init__` and
  `ImageWriter.__init__` pass their own bound methods. `ImageWriter` is
  defined only when the PIL imports succeed (`writer.py:416-420`).
- `barcode/pybarcode.py` is the command line (`python-barcode` script). No
  test imports it, so the trace has no edge of it.

## Scope rules

**A. Edges are per function.** Every function keeps the out-edges of its
body. The CLI functions, `Code128.encoded`, `CODABAR` and `Barcode.to_ascii`
run in no test; their edges come from reading.

**B1. Receivers.**
- Every barcode class overrides `build` and `get_fullcode`, and `Barcode`
  is no receiver (judgement J1). So `self.build()` and
  `self.get_fullcode()` in `Barcode.render`, `Barcode.__repr__` and
  `Barcode.to_ascii` name the methods of the concrete classes only.
- `Barcode.to_ascii` (`base.py:41`) runs for the classes that do not
  override `to_ascii`: CODABAR, Code39, PZN7, PZN8, Code128, Gs1_128 and
  ITF. The EAN family and UPC-A have their own `to_ascii`.
- `EuropeanArticleNumber13.__init__` calls `self.calculate_checksum`
  (`ean.py:63`) on every class of the EAN family: `EuropeanArticleNumber14`
  overrides it, the others use the EAN-13 method.
- `self.writer` is annotated `BaseWriter` (`base.py:35`). Its methods are
  those of `BaseWriter`, `SVGWriter` and `ImageWriter` (judgement J3).

**B2. Arguments and stored values.**
- The callbacks of `BaseWriter` (`writer.py:231`, `264`, `281`, `302`,
  `304`): the package passes only the bound methods of `SVGWriter` and
  `ImageWriter`. The constructor and `register_callback` type a callback as
  a bare `Callable`, which is no evidence for a package value. A client's
  callable is opaque (B5).
- `func(args, parser)` (`pybarcode.py:99`): `func` is the default that
  `set_defaults` gave to the chosen sub-parser, `list_types` or
  `create_barcode`.
- `create_barcode(args, parser)` has no annotation and no docstring. The
  package's own call passes the `argparse.Namespace` of `main` (str values)
  and the `ArgumentParser`. So `args.type.upper()` is `<builtin>.str.upper`
  and `parser.error` is `argparse.ArgumentParser.error`.
- `SVGWriter.write` (`writer.py:413`): see judgement J4.

**B3. Not considered.** A package object passed as a code, a file name, a
colour or a size. The f-strings and `str.format` fields format strs, ints
and floats; this is the reason of the default rejection.

**B4. Concrete outside types.** `options: dict` gives `<builtin>.dict.items`
(`writer.py:192`); the class attribute `default_writer_options: ClassVar[dict]`
gives `<builtin>.dict.copy` (`base.py:104`). The attributes `text` and
`human` are annotated `str` (`writer.py:105-106`). `fp: BinaryIO` is an
abstract type and fixes no class.

**B5. Client objects are opaque.** The client's file objects (`fp`) and
callbacks are opaque unless another rule fixes their concrete type.
Writer options use the concrete dict and documented string/numeric roles
under B4; other client values remain opaque. A callback's opaque behavior
can still affect package control flow, as in J6 and J7.

## Default rejection

One `default reject` line decides ten candidates: `Barcode.__repr__` and
the `__str__` of the nine classes that define one (`BarcodeError` and eight
barcode classes). It decides 662 candidate-site pairs (68 sites for
`__repr__`, 66 for each `__str__`). The sites are the 39 f-string fields,
the 11 `%` operators (all integer modulo), the 9 `print` calls of the CLI
and the 9 `str.format` calls (68 sites; the two `!r` fields propose only
`__repr__`). No barcode and no `BarcodeError` is formatted
or printed in the package. The `{x!r}` fields format a str (`name`,
annotated `str`, `__init__.py:104`; the result of `get_fullcode`,
`base.py:48`). The interpreter's printing of an escaped exception is no
package call.

## Value sites

25 sites. 9 are `str.format` on a str (`SIZE`, `writer.py:73`, and the
literal of `codex.py:36`): the site finder marks every `.format(...)` as a
value site because `ImageWriter.__init__` assigns `self.format`. One is
`self._draw.text(...)` (`writer.py:482`), a method of the PIL `ImageDraw`
object, marked because the writer assigns `self.text`. The others:

- `barcode(code, writer, **options)` (`__init__.py:106`): the 14
  `__init__` methods of the map's classes.
- `get_barcode(name)` (`__init__.py:112`): the module alias of `get`.
- `self.default_writer()` and `Barcode.default_writer()` (7 sites):
  `SVGWriter.__init__`.
- the five callback sites of `BaseWriter.render` and `func(args, parser)`
  (see B2).

## Judgements

Each judgement names its file and line and applies the global scope rules.

**J1. `Barcode` is no receiver of its own methods** (`base.py:37-38`).
`Barcode.__init__` raises `NotImplementedError`, so no client and no package
code can make a `Barcode` instance through its constructor. Global B1
explicitly excludes classes whose own initializer always raises, as well
as abstract classes and Protocols.
Effect: `Barcode.build` and `Barcode.get_fullcode` are rejected at
`base.py:41`, `48`, `110`, `112`, `ean.py:118` and `upc.py:106`, and
`Barcode.__init__` has no caller. The changelog (v0.14.0) speaks of client
subclasses of `Barcode`; under B1 they are client code and do not add
package receiver classes or override the fixed one-element build results
used by J7.

**J2. `ImageWriter._init` never raises `RuntimeError`** (`writer.py:446-447`).
`ImageWriter` is defined only when the three PIL imports succeed
(`writer.py:33-36`, `416-420`). The `except` branch sets `Image`,
`ImageDraw` and `ImageFont` to `None` together, and then `ImageWriter` is
`None`. So `ImageDraw is None` is false whenever `_init` runs. Only a
client's change to the module global `barcode.writer.ImageDraw` makes it
true, which the conventions do not consider. The site has a note and no
callee (one edge less).

**J3. `BaseWriter` is a receiver of its own methods** (`writer.py:78`). It
is a plain public class, and its `__init__` takes the four callbacks, so a
client can make one and pass it as the writer. `docs/writers.rst` ("Custom
writers") documents it for subclassing. B1 makes such a class a receiver of
its own methods. Its `save` and `write` raise `NotImplementedError`, but
the calls happen: `Barcode.save -> BaseWriter.save` (`base.py:78`) and
`Barcode.write -> BaseWriter.write` (`base.py:94`). No test makes them.

**J4. `SVGWriter.write -> io.BufferedWriter.write`** (`writer.py:413`).
`fp` is annotated `BinaryIO`, an abstract type, so the annotation names no
method, and a client's `fp` is opaque. But `generate` opens the file itself
for an `os.PathLike` output (`__init__.py:145-147`) and passes it through
`Barcode.write` (`base.py:94`). B2 counts what the package's own calls pass,
so the edge is in the graph. No test passes a path-like object; the trace
has the same edge from the tests' own open files. The trace edge to
`_io.BytesIO.write` is the tests' `BytesIO` and is rejected.

**J5. `Code39.__init__` calls only `Code39.calculate_checksum`**
(`codex.py:57`). `self` can be a `PZN7` or a `PZN8`, but `PZN7.__init__`,
their only path into `Code39.__init__`, passes `add_checksum=False`
(`codex.py:113`). So the branch runs only for a `Code39`, and
`PZN7.calculate_checksum` is rejected. A client can call
`Code39.__init__(pzn, code)` again on a built `PZN7`; B1's last sentence
would make that object a package instance. The lead's ruling on audit F1
decides it: `__init__` receives the object that is being made, with the
arguments of that construction, and a client that calls `__init__` again on
a built object is not considered (one edge less).

**J6. `Code128._convert` can raise `RuntimeError`** (`codex.py:240`).
`Code128` retains its nominal `str` input. A client subtype may iterate
ordinary admitted characters while returning a different character from
indexing. `_maybe_switch_charset` then need not leave charset C before
`_convert` receives an ordinary nonnumeric character. The explicit
`RuntimeError` is reachable through construction and `build`, without
attribute assignment or failed-object reuse. The client hooks remain
unnamed under B5; their control-flow effects count.

**J7. Four checks that never fail have no callee.** Earlier ground truths
give no callee to a call that cannot run (markdown2 J6; Sublist3r
`sublist3r.py:899`).
- `base.py:43`, `base.py:114`, `ean.py:120`, `upc.py:108`: each
  `RuntimeError` runs only if `self.build()` returns a list whose length is
  not 1. Every package `build` returns a list of one str
  (`codabar.py:77`, `codex.py:81`, `codex.py:277`, `ean.py:111`,
  `ean.py:187`, `itf.py:70`, `upc.py:98`), whatever the public attributes
  hold.
The `ValueError` at `codex.py:169` is different. An admitted nominal
`str` input subtype can yield a digit whose reflected addition supplies
a buffer with stateful length. This reaches
`_new_charset` with the current charset through an ordinary `build` call,
without internal assignment or reuse after an exception. The callee is
therefore included, together with J6's `RuntimeError`.

The four excluded pairs are `Barcode.render`, `Barcode.to_ascii`,
`EuropeanArticleNumber13.to_ascii` and `UniversalProductCodeA.to_ascii` to
`<builtin>.RuntimeError`.

The `NotImplementedError` checks of `BaseWriter.render` (`writer.py:235`)
and of the two `_init` methods (`writer.py:326`, `449`) stay: `render` is
public and takes the client's list of lines, and it calls `initialize`
before its own check.

**J8. Optional import and `TYPE_CHECKING`.** Both sides of the optional
import of Pillow run (README default): the module `barcode.writer` calls
`logging.getLogger` and `logging.Logger.info` (`writer.py:40-41`), the
`ImageWriter` methods are nodes, and both branches on `ImageWriter is not
None` in `pybarcode.py` run (lines 21, 37, 51, 82). The blocks under `if
TYPE_CHECKING:` do not run (`__init__.py:32`, `base.py:12`, `writer.py:13`,
`codex.py:19`; in `version.py:13-14` `TYPE_CHECKING` is a local `False`).
They hold no call.

## Audit outcome and rulings (earlier audit)

The blind audit (`python-barcode.audit.md`) re-derived 94 sites (a seeded
draw of 70 and every value site). 90 agree; at the other 4 the auditor was
wrong. It found no missing edge, no edge that cannot happen and no naming
error. The lead's rulings:

- **F1** (`codex.py:57`, J5): no edge `Code39.__init__ ->
  PZN7.calculate_checksum`. `__init__` receives the object that is being
  made; its receivers are the instances whose construction reaches it, with
  the arguments that the construction passes. A client that calls
  `__init__` again on a built object is not considered. The rejection
  stays; its reason now says this.
- **W1** (`codex.py:169`, J7): the reason was incomplete. After a
  `KeyError` at `codex.py:211` the object is left in charset B with a
  buffered character. B3's sentence on an object left behind after an
  error covers any exception that leaves the object half-changed. No edge.
  After R1's ruling this state needs a client assignment that does not
  count, so B3 is now the second reason in the note and in J7.
- **R1** (`codex.py:240`, J6): the auditor agreed with my first version,
  which kept the edge. A later ruling for the whole set, made on another
  package, changes it: a client uses the public API (constructor arguments,
  methods); a client's assignment to a public attribute of a package
  object counts only where the package's documentation or tests make that
  assignment. Nothing in `docs/`, `tests/` or `README.rst` assigns `code`
  on a built object, and no constructor lets an unsupported character
  through. So `Code128._convert -> <builtin>.RuntimeError` goes (348 to
  347 edges).
- **J1** stands: a class whose own `__init__` always raises has no
  instance (the lead adds this to B1). J7's precedent goes into the README
  conventions.

The graph has 347 edges (158 inside, 189 outside).

## Names outside the package

- The minidom methods are named by the class of the receiver (README):
  `xml.dom.minidom.Element.appendChild` and
  `xml.dom.minidom.Document.toprettyxml` (the trace's canonical names are
  `Node.appendChild` and `Node.toprettyxml`; its aliases match), and
  `xml.dom.minidom.Document.toxml` (no trace edge: `compress` is false in
  every test).
- `argparse`: `add_argument` and `set_defaults` of `_ActionsContainer` are
  named through `argparse.ArgumentParser`; `add_parser` through the private
  class `argparse._SubParsersAction` (the argcomplete precedent).
- Pillow: `PIL.Image.new`, `PIL.ImageDraw.Draw`,
  `PIL.ImageDraw.ImageDraw.rectangle`, `PIL.ImageDraw.ImageDraw.text`,
  `PIL.ImageFont.truetype`, `PIL.Image.Image.save`. The trace (Pillow
  11.3.0) has all six.
- Files: `io.BufferedWriter.write` for `open(..., "wb")`;
  `gzip.open`, `gzip.GzipFile.write` and `gzip.GzipFile.close` for the
  compressed SVG (`writer.py:399-401`).

## The trace

The trace has 265 edges. 264 are in the graph. The one rejected edge is
`SVGWriter.write -> _io.BytesIO.write`: the tests pass a `BytesIO`
(`test_writers.py:40`, `test_init.py:42`), and no package code makes one.
The tests run 80 of the 107 functions; `pybarcode.py` is never imported.
The package uses no `exec`, `@contextmanager` or thread, so the tracer
defect T1 does not apply.

| Nodes | Edges (inside / outside) | Confirmed by the trace | From reading only | Rejected trace edges | Functions run | Ledger entries | Value sites | Default rejections (sites) | Exclusions |
|---|---|---|---|---|---|---|---|---|---|
| 126 | 349 (158 / 191) | 264 (75.6%) | 85 | 1 | 80 of 107 | 390 | 25 | 10 (662) | 2 |

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
