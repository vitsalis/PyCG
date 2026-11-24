# pyfiglet: judgements of the ground truth

Status (writer, 2026-11-22): done. Every site is decided, `check.py
--write pyfiglet` and `check.py pyfiglet` report no error. The doubled blind
audit is done (`pyfiglet.audit.md`); its F1 (J1, the referee's platform
ruling) and F2 (a note) are applied, and so are the findings of Codex
audit round 1 (see "Codex round 1"). J2 and J3 decide outside edges only;
each lists its edges.

Release 1.0.4, held as its PyPI sdist (`pyfiglet-1.0.4.tar.gz`, SHA-256
`db9c9940...`). Analysed source: `pyfiglet/` without `pyfiglet/tests/` (not
in the sdist) and `pyfiglet/test.py`: 4 modules (`pyfiglet`,
`pyfiglet.__main__`, `pyfiglet.version`, `pyfiglet.fonts`), 58 functions,
no lambdas, 11 classes. `pyfiglet/__init__.py` holds all the code.

The ledger is `pyfiglet.ledger`; the graph `pyfiglet.json` is generated from
it: 62 nodes, 245 edges (74 inside, 171 outside). There is no trace (no test
can run: `projects.toml`), so every edge comes from reading
(`pyfiglet.added.json`, `"trace": null`) and there is no
`pyfiglet.rejected.json`. No default rejection: the largest candidate set is
`FigletError.__str__` and `FigletFont.__str__`, proposed together at 16
sites (one of them accepts `FigletError.__str__`, J5). No value site.

The writer read every function of the package, `README.md`, `doc/`,
`setup.py`, `PKG-INFO` and the excluded driver `pyfiglet/test.py` (for the
roles that it shows). Nothing of the package was run or imported, and no
analysis tool ran. Library behaviour was read in the CPython sources of
3.10.14 and 3.11.9 (`deps/_cpython`), in the standard libraries of local
CPython 3.12.12, 3.13.12, 3.14.9 and 3.15.2 (read only), and, for 3.9, in
the pure-Python standard library that PyPy 3.9 v7.3.16 copies from CPython
3.9 (`deps/_pypy/pypy3.9-v7.3.16-src/lib-python/3`: `importlib/_common.py`,
`importlib/resources.py`, `zipfile.py`). No CPython 3.9 source was at hand;
see "For the lead".

## Runtimes

- `setup.py:23` (and `PKG-INFO`): `python_requires=">=3.9"`. The classifiers
  stop at 3.11; the final classifier is not an upper bound, so the versions
  are CPython 3.9 and later (read up to 3.15).
- No other implementation is declared ("Programming Language :: Python"
  only), so PyPy is not admitted (README, "Versions and configuration"). The
  CI file that `projects.toml` names (`.github/workflows/test.yml`) is not
  in the sdist and was not read. If it runs PyPy, the edges would not change
  as far as the writer can see: every outside callee is pure Python in
  pathlib, zipfile, optparse and `_sitebuiltins`, or a C class whose public
  name PyPy keeps (`io`, `re`).
- Platforms: Unix only (J1).
- The package has no `assert` and no `__debug__` code: `-O` and `-OO` change
  no edge.
- `from __future__ import annotations` (`__init__.py:8`): no annotation is
  evaluated, so annotations are no sites.

## How the ledger applies the scope rules

**A.** Every function keeps the edges of its body. `FigletFont.__str__`,
`Figlet.getFonts` and `FigletBuilder.smushAmount`'s defaults have no
package caller; they keep their edges.

**B1, receivers.** No package class has a package subclass except the five
`FigletError` classes, which inherit `__init__` and `__str__`. So every
`self.m()` names the method of its own class. Figlet makes one
`FigletRenderingEngine` with `base=self` (`__init__.py:864`; the annotation
is `Optional[Figlet]`), so `self.base.direction` and `self.base.justify`
(`470:43`, `472:43`) run the properties of `Figlet`. The `direction` and
`justify` of a `FigletBuilder` (`594:46`, `646:17`, `731:21`, `799:21`) and
of the `optparse.Values` of `main` (`1000:44`, `1001:26`) are plain
attributes. `r` in `main` is the `FigletString` of `renderText`
(`FigletProduct.getString`, `493`) or of `reverse`/`flip` (`newFromList`).

**B2 and B4, values.** The parameters that carry the client's fonts, text,
directions, justifications, colours and file names are annotated `str`,
`int`, `bool` or `FigletFont`. Some internal parameters of `FigletBuilder`
are unannotated (`addLeft`, `idx` and `smushed` of
`updateSmushedCharInLeftBuffer`, `__init__.py:634`; `addLeft` of
`getLeftSmushedChar`, `623`; `saved_buffer` of `cutBufferAtLastBlank`,
`670`); the package passes strs, ints and lists of strs there, and the
bodies call only `len`, `list` and `str.join` on them, so no package callee
arises (a client object there is opaque, B5). The one package `str` subclass,
`FigletString`, overrides no method that the package calls on such a value
(`endswith`, `partition`, `upper`, `%s`, `format`, `list()`), so no package
callee appears at those sites, and its inherited methods keep their
`<builtin>.str` names. The file objects are package-made: `open(..., 'rb')`
gives `io.BufferedReader`; the resource paths of `importlib.resources.files`
and their streams are named in J1 and J2.

**B5.** `print_figlet` and `main` write to `sys.stdout`, the interpreter's
stream (J3). No client callback reaches the package.

**C.** Every class and method is on a public path (`pyfiglet.X`); the
classmethods and the staticmethod of `FigletFont` are public too. The one
exception is the local helper `__char` of `loadFont` (`__init__.py:314`),
which only `loadFont` calls, with its own list of lines; those calls give
its edges.

## Judgement calls

1. **Platforms: Unix only** (`__init__.py:61-62`; the referee's ruling on
   audit F1, adopted by the lead, `b7-ruling-pyfiglet.md` in the
   audit records). "Supported platforms are those the release declares
   through classifiers or documentation, or establishes through its own
   platform test jobs, subject to explicit restrictions and support drops. A
   platform branch in the code, or a platform-neutral wheel tag, does not by
   itself admit another platform." pyfiglet declares only "Operating System
   :: Unix" (`setup.py`, `PKG-INFO`), and nothing in the sdist declares
   Windows. So the branch `sys.platform == 'win32'` does not run: `62:36`
   has no edge (a note), and no `pathlib.WindowsPath` or
   `_io._WindowsConsoleIO` callee is named. The writer had admitted Windows
   from that branch; the ruling removed 10 outside edges at 14 sites
   (`pyfiglet -> os.path.join`; `pathlib.WindowsPath.joinpath`, `.exists`,
   `.open` in `preloadFont`, `.joinpath`, `.open` in `isValidFont`,
   `.iterdir`, `.is_file` in `getFonts`; `_io._WindowsConsoleIO.write` in
   `print_figlet` and in `main`). No inside edge changed.
2. **Zip imports of the package's own resources** (`__init__.py:142`,
   `182`, `200`; 10 outside edges). The README admits ordinary zip imports
   that `importlib.resources` supports for a package's own resources
   (netaddr), and pyfiglet's own comment says so too ("Figlet is installed
   using a zipped resource", `__init__.py:237`). For a zip import,
   `importlib.resources.files('pyfiglet.fonts')` is a `zipfile.Path`
   (3.9 `importlib/_common.py:fallback_resources`; 3.10 to 3.15
   `zipimporter.get_resource_reader` -> `ZipReader.files`), and its binary
   `open` returns the `zipfile.ZipExtFile` of `ZipFile.open` (3.9 to 3.15
   `zipfile.Path.open`). For a directory the result is
   `pathlib.Path(loader.path).parent` (3.9 `fallback_resources`; 3.10 to
   3.15 `FileReader.files`), a `PosixPath`, and `open('rb')`
   gives an `io.BufferedReader`. `zipfile.Path` has no `resolve`, so the zip
   case takes the `else` branch of `installFonts` (`233`). Edges that only
   the zip import gives: `zipfile.Path.joinpath`, `.exists`, `.open` and
   `zipfile.ZipExtFile.seek` (`preloadFont`); `zipfile.Path.joinpath`,
   `.open`, `zipfile.ZipExtFile.seek`, `.close` (`isValidFont`);
   `zipfile.Path.iterdir`, `.is_file` (`getFonts`). From 3.12 the class is
   `zipfile._path.Path`; it keeps its public alias `zipfile.Path` (netaddr).
3. **`sys.stdout` after `main()`** (`__init__.py:1019`; 5 outside edges
   that rest on an earlier or a concurrent `main()`, and the `-u` edges of the structlog
   precedent). `main()` replaces `sys.stdout` with `sys.stdout.detach()`
   and returns 0 after rendering. So:
   - In `main` the binary writes (`1023:25`, `1025:21`, `1026:21`,
     `1029:25`) go to the `io.BufferedWriter` of the standard text stream;
     under `-u` or `PYTHONUNBUFFERED` to the raw stream, `io.FileIO` (the
     README's configuration clarification; structlog `_output.py:347`).
   - "An edge that depends on what ran earlier in the process counts if
     some program that uses only the public API makes it in a fresh
     process" (README, "Edges"). `main` is public (the console script). A
     second `main()` in one process finds the `io.BufferedWriter` and calls
     `io.BufferedWriter.detach` (`1019:39`), which returns the raw stream;
     its writes then go to `io.FileIO` (the same name as under `-u`). After a `-u` run or a second run, the raw
     stream has no `detach`: AttributeError, no edge.
   - `print_figlet` after a `main()` calls `write(ansiColors)` (`75:25`) on
     that binary stream: `io.BufferedWriter.write`, `io.FileIO.write`. The `str` argument binds and the method
     raises `TypeError` in its body, which keeps the edge (README, "Binding
     for a callable written in C").
   - `80:25` and `81:25` run only after `75:25` and `print` succeeded on a
     text stream, but the README sets no restriction to one thread
     ("Random outcomes and file-system histories"), and concurrent public
     calls may change shared state (the websocket-client ruling, J7). So
     another thread can complete `main()` between lines 77 and 80, or 80
     and 81, and line 1019 puts the binary stream there:
     `io.BufferedWriter.write`, `io.FileIO.write` at `80:25`, and
     `io.BufferedWriter.flush`, `io.FileIO.flush` at `81:25` (`FileIO`
     inherits `flush`; named by the receiver class). Codex audit round 1;
     the writer's first ledger kept only `io.TextIOWrapper.write` and
     `.flush` there.
   Edges that rest on an earlier or a concurrent `main()`:
   `main -> io.BufferedWriter.detach` and `print_figlet ->
   io.BufferedWriter.write`, `io.FileIO.write`, `io.BufferedWriter.flush`,
   `io.FileIO.flush`.
   The blind audit found this decided by the README's "Edges" rule (what
   ran earlier in the process through the public API): no ruling was
   needed.
4. **The second newline branch** (`__init__.py:553-555`; no edge
   changes). In one thread `addCharToProduct` has returned at `536-539`
   for a newline, and nothing between `536` and `553` changes `self.text`
   or `self.iterator`, so the test at `553` is false. But `FigletBuilder`
   and its `goToNextChar()` (`566`) are public, and another thread can
   advance `self.iterator` between lines 550 and 553 (a builder for
   `"A\n"`): the branch runs, so `554:37` has `<builtin>.list.append` and
   `555:31` has `FigletBuilder.handleNewLine` (Codex audit round 1, under
   the concurrency rules of J3). The writer's first ledger held the branch
   unreachable. Both pairs exist at other sites of the function (`537:41`,
   `538:35`), so the graph does not change.
5. **`%s` of a caught package exception** (`368:59`; 1 inside edge). The
   `try` block of `loadFont` raises `FontError` itself (`274:32`,
   `280:32`), and the `except Exception as e` formats `e` with `%s`:
   `str(e)` runs `FigletError.__str__`. Edge `FigletFont.loadFont ->
   FigletError.__str__`.
6. **`exit(0)`** (`__init__.py:975`, `979`, `983`, `987`). `exit` is the
   `_sitebuiltins.Quitter` instance that `site` puts into `builtins`
   (`site.py:804` of 3.15); calling an instance of an outside class is its
   `__call__`, also for a private class (micro-benchmark, "Calls of
   instances"): `_sitebuiltins.Quitter.__call__`. No earlier ground truth
   calls `exit()`; under `python -S` the name does not exist (NameError, no
   edge).
7. **Version branch** (`__init__.py:993-994`): `sys.version_info < (3,)` is
   true only on Python 2, which the release does not support, so
   `arg.decode` (`994:27`) has no edge. `sys.version_info > (3,)`
   (`1017`) is always true.
8. **The `__main__` block of `__init__.py`** (`1034-1035`): the README keeps
   the edges of such a block. Run as a script the file fails at its
   relative import (`line 21`), but `python -m pyfiglet.__init__` imports the
   package first and runs it as `__main__`, so the block can run.
   `pyfiglet -> sys.exit` and `pyfiglet -> pyfiglet.main`.

Smaller decisions, by existing rules:

- `FigletString(...)` (`452:28`, `493:28`) has no edge: `FigletString`
  subclasses `str` and defines neither `__init__` nor `__new__`; `str`
  defines no `__init__` (tabulate's `JupyterHTMLStr`).
- `map(int, ...)` (`283:71`) and `map(ord, ...)` (`502:29`): the builtin
  callbacks are no edges.
- `importlib.resources.files` keeps its name from 3.12, where it is the
  `package_to_anchor` wrapper (a Python function at a public attribute).
- `pathlib.Path(...)` is named `pathlib.Path`; methods on its result by
  the concrete class (`PosixPath`).
- Compiled patterns and matches are `re.Pattern` and `re.Match`.
- `print`, `str` and `str.format` with only str and int arguments reject
  the two `__str__` candidates; the inner function `__char` of `loadFont`
  is the node `pyfiglet.FigletFont.loadFont.__char` (the qualified name,
  unmangled).

## Codex round 1

The full source audit (2026-11-23) found 2 missing outside pairs, no false
edge and no naming error, and 3 metadata items. The writer checked each
against the source and the README and applied all of them; none is
disputed.

- Missing, applied: `print_figlet -> io.BufferedWriter.flush` and
  `io.FileIO.flush` at `81:25` (J3): a `main()` in another thread between
  lines 80 and 81 replaces `sys.stdout` at line 1019; line 81 loads it
  again. The README sets no restriction to one thread, and concurrent
  public calls may change shared state (the websocket-client ruling). +2
  outside edges (243 to 245).
- Metadata, applied: `80:25` also names `io.BufferedWriter.write` and
  `io.FileIO.write` (the pairs exist through `75:25`; J3). `554:37` and
  `555:31` name `<builtin>.list.append` and `FigletBuilder.handleNewLine`
  (the pairs exist at `537:41` and `538:35`; J4). The scope summary now
  names the unannotated parameters of `FigletBuilder` and the private local
  helper `loadFont.__char` (B2, C).

## For the lead

- J1 is ruled (Unix only). J2 (zip import) and J3 (process state after
  `main()`) decide outside edges only; each lists its edges above.
- With Windows out, this ledger names no Windows console stream; the
  disagreement between structlog (`_io._WindowsConsoleIO`) and path
  (`io._WindowsConsoleIO`) remains in those two ground truths.
- No CPython 3.9 source was in `deps/`; the 3.9 facts (J2) come from PyPy's
  copy of the 3.9 standard library. A CPython 3.9 `Lib/` (any 3.9.x) would
  confirm them.
