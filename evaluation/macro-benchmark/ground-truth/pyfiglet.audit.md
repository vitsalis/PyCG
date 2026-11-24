STATUS: DONE, including the re-check of commit f1f6876 (section 6):
approved. Nothing is left.

# Audit of the pyfiglet ground truth (batch 7, blind auditor)

Audited: `pyfiglet.ledger`, `pyfiglet.json`, `pyfiglet.added.json` and
`pyfiglet.md` as of 2026-11-22 23:52 (253 edges: 74 inside, 179 outside;
`check.py pyfiglet`: no errors). No trace and no `.rejected.json` exist.

## 1. Blind re-derivation

The blind answers were written before I opened any writer file:
`/tmp/claude-501/b7-audit-pyfiglet/blind-answers.md` (with `draw.py`,
`sample.txt` and `skeleton.ledger` in the same directory).

- Skeleton from a scratch benchmark dir (`check.py --benchmark-dir ...
  --skeleton pyfiglet`): 322 sites (300 call, 7 decorator, 5 op, 10
  getattr); 114 with candidates; 0 value sites.
- Draw (doubled audit, 140 sites): fewer than 140 sites have candidates, so
  all 114 were taken, and 26 sites were filled from the other 208 with
  `random.Random(20261123).sample(others, 26)` (sites numbered in
  (module, line, column) order). The seed is the brief's; the README's
  "Rulings for batch 6" names `random.Random(20261122)` for the audits
  of batch 6. The lead may want to make the two agree.
- I read every function of `__init__.py` and `__main__.py`, `setup.py`,
  `README.md`, `PKG-INFO`, and the stdlib sources named below.

Result: 137 of 140 sites agree exactly (callees and rejections, inside and
outside). The 3 differing sites:

| Site | Writer | Blind | Class |
|---|---|---|---|
| `554:37` | no callee (dead branch, J4) | `<builtin>.list.append` | auditor wrong |
| `555:31` | no callee (dead branch, J4) | `FigletBuilder.handleNewLine` | auditor wrong |
| `1029:25` | also `_io._WindowsConsoleIO.write` | not that name | judgement J1 (Windows) |

J4 is right: line 536 returns when `self.text[self.iterator]` is a newline,
and nothing between 536 and 553 changes `self.text` or `self.iterator`
(`getCurWidth`, `currentSmushAmount`, `smushAmount`, `smushChars` and the
`list.append` only read them), so the test at 553 is always false. The graph
does not change: both edges exist at 537:41 and 538:35.

One blind open question (Q1, not a sampled site) was wrong too: I gave
`print_figlet`'s 80:25 and 81:25 the binary-stream names after an earlier
`main()`. The writer is right that 75:25 (or `print` at 77:10) raises
`TypeError` first on a binary stream, so 80:25 and 81:25 keep only
`io.TextIOWrapper.write` and `.flush`.

The blind answers agree with the writer on every non-obvious case: J5
(`368:59 -> FigletError.__str__`), J6 (`_sitebuiltins.Quitter.__call__`),
J2 (`zipfile.Path`, `zipfile.ZipExtFile`), J3 at 75:25 and 1029:25
(`io.BufferedWriter.write`, `io.FileIO.write`), the property loads at
470:43 and 472:43, and every `__str__`, `append`, `direction`, `justify`
and `getFonts` rejection.

## 2. Exhaustive checks

- **Every ledger entry read** (865 lines): every callee, rejection and note.
  No wrong edge, no missing edge, no wrong rejection found.
- **Binding check.** Every call of a package function binds (Figlet,
  FigletFont, FigletBuilder with 5 positionals, FigletRenderingEngine,
  FigletProduct, the four FigletError subclasses with one argument,
  `smushChars(left=, right=)`, `color_to_ansi(..., isBackground=)`, the
  classmethods and the staticmethod, `__char(data)`, `newFromList(out)`).
  None fails.
- **Dispatch sets.** No package class has a package subclass except the
  four `FigletError` subclasses (they inherit `__init__` and `__str__`).
  `self.product` is always the `FigletProduct` of `FigletBuilder.__init__`;
  `self.Font` the `FigletFont` of `setFont`; `self.base` the `Figlet` of
  `Figlet.__init__` (`Optional[Figlet]`; `None` raises at `self.base.Font`
  before the builder call). `r` in `main` is a `FigletString` at
  1009-1015 (`strip_surrounding_newlines` returns a plain `str`, but only on
  the `if` arm, and 1015 is the `elif`).
- **Properties.** The finder lists all ten loads of `direction`/`justify`;
  only 470:43, 472:43, 889:21 and 891:23 have a `Figlet` receiver. No store
  targets a `Figlet` property.
- **Special methods.** `FigletError.__str__` runs only at 368:59 (J5). No
  package `__bool__`, `__len__`, `__iter__`, `__eq__`, `__hash__`,
  `__format__` exists, so the 739 implicit sites without candidates
  (`--report --without-candidates`) need no entry. `FigletString(...)`
  (452:28, 493:28) has no constructor edge (tabulate ruling).
- **Functions that no site calls:** `Figlet.getFonts`,
  `FigletFont.__str__`, `print_figlet` (public API) and the modules. Each
  keeps its body edges (rule A).
- **Default rejections:** none. **Rejected trace edges:** none (no trace).
- **Outside names** (93 distinct), against the micro-benchmark rules and
  the precedents (netaddr for `importlib.resources` paths, structlog for
  `-u`): all consistent. I checked the library facts in the sources:
  3.9 `importlib/_common.py:fallback_resources` (PyPy 3.9's copy of the
  CPython 3.9 stdlib, lines 9-25) returns `pathlib.Path(...).parent` or
  `zipfile.Path`; 3.9 `zipfile.Path.open` returns the `ZipExtFile` for a
  binary mode (`zipfile.py:2319-2331`); 3.11 `zipfile.py:2423-2504` and
  3.12, 3.14 `zipfile/_path/__init__.py` have `open`, `is_file`, `exists`,
  `iterdir`, `joinpath` and no `resolve` (so the zip case takes the `else`
  of `installFonts`, 233); 3.14 `readers.FileReader.files` returns
  `pathlib.Path(loader.path).parent`.
- **Optimised modes:** no `assert`, no `__debug__` (grep): `-O`/`-OO`
  change nothing.

## 3. Findings

| # | Severity | Finding | Edges |
|---|---|---|---|
| F1 | ruling needed (medium) | J1: I would not admit Windows (below). | -10 outside, if adopted |
| F2 | cosmetic | Note at `75:25` says "(main.py 1019)"; the line is `__init__.py:1019`. | 0 |

No other finding. The inside graph (74 edges) is unchanged by every item of
this audit.

## 4. The writer's judgement calls

- **J1, Windows (10 outside edges).** The README does not decide a package
  whose only OS declaration is `Operating System :: Unix`
  (`setup.py`, PKG-INFO) and whose code has a `win32` branch
  (`__init__.py:61`). The nearest rules: "A branch on the platform runs if a
  platform that the package supports takes it" and "The supported versions
  are those that the package declares"; "a branch that only an unsupported
  version takes does not run". The writer's analogy ("the final classifier
  is not an upper bound") is about version classifiers beside a
  `python_requires` that is the real declaration; for platforms the
  classifier is the only declaration. The same file has a Python 2 branch
  (`993-994`, J7) that the ledger rightly treats as dead, so a branch in
  the code is not by itself a support statement. `py3-none-any` is the tag
  of any pure-Python wheel, not a platform claim. The CI file is not in the
  sdist; the upstream test command runs after `apt install` (Linux).
  The smaller extension: *a platform is supported when the release declares
  it (classifiers, documentation, a CI job); a platform branch in the code
  alone does not admit the platform.* Under it the 10 edges go
  (`pyfiglet -> os.path.join`; 7 `pathlib.WindowsPath.*`; 2
  `_io._WindowsConsoleIO.write`). If the lead admits Windows instead, the
  writer's 10 edges are complete: I found no further Windows-only callee.
  This decides 10 edges; the lead may want the referee.
- **J2, zip imports (10 outside edges).** Supported by the clarification
  "Versions and configuration" (ordinary zip imports for a package's own
  resources, netaddr). Agree; the edge list is complete.
- **J3, `sys.stdout` after `main()` (4 edges rest on an earlier `main()`).**
  Supported directly by "Edges": "An edge that depends on what ran earlier
  in the process counts if some program that uses only the public API makes
  it in a fresh process" (sqlparse). `pyfiglet.main` is public; the state
  is the package's own `sys.stdout = sys.stdout.detach()`, not a client's
  change of package internals. Witness: `python -c "import pyfiglet;
  pyfiglet.main(); pyfiglet.main(); pyfiglet.print_figlet('x',
  colors='RED')" hi`. The `-u` names follow "`-u` changes the binary
  standard streams" (clarification) and structlog. Agree; no ruling needed
  beyond the existing rule.
- **J4, dead branch.** Supported (B1: "A check that cannot fail under the
  package's own values has no callee"). Here it holds for every input, not
  only package values. Agree; no graph change.
- **J5.** Supported (callback rule; the `%s` conversion calls `__str__`).
  Agree; 1 inside edge.
- **J6, `exit(0)`.** Supported by the micro-benchmark rule "Calls of
  instances ... `<class path>.__call__`, also when the class is private".
  Agree. No earlier precedent; it may be worth one line in the README.
- **J7, J8.** Supported (unsupported-version branch; `__main__` block of
  marshmallow `orderedset.py:84`). Agree.

## 5. Naming of the Windows console stream (lead's question)

The rules give **`_io._WindowsConsoleIO`**:

- Macro README, "Callees outside the package": "a function that a module
  re-exports without listing it in `__all__` is named where it is defined
  (asciinema: `termios.tcsetattr` for `tty.tcsetattr`, `term.py:22`); a
  builtin type without a public path is named as the tracer names it
  (autojump: `builtins.list_iterator.__next__`)."
- Micro README, "Names": "Methods: The public import path of the class of
  the instance"; "Methods of other builtin types: A type that is not in
  `builtins` is named by its public path"; "Calls of instances: ... also
  when the class is private (`functools._lru_cache_wrapper.__call__`)".
- Facts (CPython 3.11.9): `Modules/_io/winconsoleio.c:1131` gives the type
  the name `"_io._WindowsConsoleIO"`, so `__module__` is `_io` and the
  tracer names it `_io._WindowsConsoleIO`. `Lib/io.py:110-115` imports it
  (`from _io import _WindowsConsoleIO`) only to register it with
  `RawIOBase`, and `io.__all__` (`io.py:44-50`) does not list it. The class
  has no public path (every path has an underscore component), so the
  "public path" rules do not apply; the re-export rule and the tracer rule
  both give its defining module, `_io`.

So structlog's `_io._WindowsConsoleIO` follows the rules, and path's
`io._WindowsConsoleIO` should become `_io._WindowsConsoleIO` (seen in path's
ledger as `io._WindowsConsoleIO.read`). The README does not say this in one
place: a sentence such as "a private class that a public module re-exports
without listing it in `__all__` is named by its defining module" would
settle it.

## 6. Re-check of the committed ground truth (commit f1f6876)

The referee upheld F1 (`b7-ruling-pyfiglet.md`). The writer applied F1 and
F2. I compared the pyfiglet files of `f2e1b45..f1f6876`, and the pyfiglet
files have no later change.

- **Ledger.** Callees changed only at the 14 sites of the ruling's table.
  Each site lost only its Windows name (`os.path.join` at 62:36, which
  becomes a note; `pathlib.WindowsPath.*` at 142:72, 143:27, 155:32,
  182:69, 182:80, 200:72, 202:91 and 205:32; `_io._WindowsConsoleIO.write`
  at 75:25, 1023:25, 1025:21, 1026:21 and 1029:25). Each site kept the
  other callees that the table lists. No other callee changed, and no
  rejection changed. At 235:27 only the reason changed: "a PosixPath or
  WindowsPath" became "a PosixPath". The reworded notes (header, 142:72,
  155:32, 202:91, 205:32, 75:25 with F2's `__init__.py:1019`, 1023:25) only
  drop Windows and add no claim.
- **Graph.** `pyfiglet.json` lost exactly the 10 caller-callee pairs of
  the ruling, and nothing else changed. `check.py pyfiglet` reports no
  errors. The graph has 243 edges: 74 inside (unchanged) and 169 outside.
  `pyfiglet.added.json` changed in the same way.
- **pyfiglet.md.** J1 now quotes the ruling. J2 drops `WindowsPath`. J3
  now counts 3 edges that rest on an earlier `main()`:
  `main -> io.BufferedWriter.detach`, and `print_figlet ->
  io.BufferedWriter.write` and `io.FileIO.write`. That count is right.
- Two remarks on wording, with no edge effect:
  - J3 still ends with "**For the lead to rule.**". By section 4, the
    existing "Edges" rule decides J3, so this line can go if the lead
    agrees.
  - The "For the lead" note says that the naming disagreement remains.
    The README now names `_io._WindowsConsoleIO` (README:2558-2560), but
    `path.ledger:929` still has `io._WindowsConsoleIO.read`. That is
    outside this package.

Verdict: approved. The committed ledger and graph apply the ruling exactly.
