# textdistance: blind audit of the ground truth

Status (2026-11-23, auditor): closed. The writer applied F1 to F5
(commit `be19285`) and the re-check below accepts the ledger and graph:
711 edges (332 in the package, 379 outside). Nothing is left.

Release 4.6.3, commit `faa25f6`. Audited files, as they were on
2026-11-23: `textdistance.ledger` (2287 lines), `textdistance.json` (703
edges: 323 in the package, 380 outside; 196 nodes), `textdistance.md`
(J1 to J12), the trace `dynamic/textdistance.json` (506 edges, all in the
graph, none rejected; no `textdistance.rejected.json`). `check.py
textdistance` reports no errors. I read the package source, its README,
`setup.py`, `libraries.json`, the tests and the CI file as data. I ran
nothing of the package and no analysis tool. I read numpy 2.3.2 under
`deps/uncertainties/numpy-2.3.2/` for the numpy names only.

## Blind re-derivation

Skeleton from a scratch copy (`check.py --benchmark-dir <scratch>
--skeleton textdistance`): 766 sites, 753 explicit (741 call, 12
decorator), 13 implicit (3 getattr, 10 format), 53 value sites. The
explicit kind dominates and the implicit kind has fewer than 20 sites, so
by the jsonpickle rule the draw takes all 13 implicit sites and 57
explicit sites (`random.Random(20261123).sample(explicit, 57)`, sites
numbered in (line, column) order module by module). Every value site is
added: 121 sites in all (two value sites were also drawn). The blind
answers were written before I opened any file of the writer (scratch
file `blind-answers.md`, with the draw script and the sample list).

| Result | Sites |
|---|---|
| Agree on every callee and every rejection | 119 |
| Auditor doubt, writer's answer accepted | 2 |
| Disagreements | 0 |

The two doubts: `compression_based.py:190:31` `type(data)()`, where I
asked whether a client list is admitted (the writer and I both give only
`<builtin>.str`; BWTRLENCD has no qval, and `Sequence` fixes no type);
and `libraries.py:30:33`, where I left `pathlib.WindowsPath.open` open
(see F5). The sample covers the three large dispatch sets
(`base.py:35:20`, `179:20`, `187:32`), all 17 `reg(...)` value sites,
the external-library call (`base.py:82:28`) and every `test_func`,
`sim_func` and `sim_test` call: all agree.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | missed edges | `benchmark.py:71:26` `timeit(stmt=STMT, setup=lib.setup, ...)` in `Benchmark.get_external_benchmark`: add `DamerauLevenshtein.__init__`, `Hamming.__init__`, `Jaro.__init__`, `JaroWinkler.__init__`, `Levenshtein.__init__`, `DamerauLevenshtein.__call__`, `Hamming.__call__`, `JaroWinkler.__call__`, `Levenshtein.__call__` | The parameter is `installed: Iterable[Lib]` (`benchmark.py:69`). The annotation names the package class `Lib`, so every `Lib` that the package makes is an admitted value (B2: "the annotation decides which package values fit"). `get_internal_benchmark` makes `Lib`s whose `setup` is `func = __import__("textdistance").{alg}(external=False)` (`benchmark.py:81`, `91`). Passed to `get_external_benchmark`, timeit runs that setup and STMT here, which is exactly the code of `86:28`. By the writer's own J5, the package functions that it calls belong to this site. The ledger's reject reason at `73:27` and the note at `71:26` say that `lib` comes from `get_installed`; that is the package's own call in `run`, not the only admitted value. | +9 inside | likely |
| F2 | missed edge | `base.py:126:28` `s.split()` in `Base._get_sequences`: add `<builtin>.bytes.split` | The package handles client bytes explicitly: `Prefix.__call__` tests `isinstance(s, bytes)` on the prepared first sequence and joins with `b''.join` (`simple.py:39-40`; the ledger has `bytes.join` there), and `_NCDBase.__call__` tests `isinstance(empty, (str, bytes))` (`compression_based.py:60`). `Prefix`, `ArithNCD`, `RLENCD`, `SqrtNCD` and `EntropyNCD` take `qval`, and the README documents `qval=None` ("split sequences by words"). Admitted values of two parameters of one public call combine (django-environ ruling): `Prefix(qval=None)(b'a b', b'a c')` calls `bytes.split` here. J3 names only `str.split` "for the str of the annotated callers", but these callers are not annotated `str` (`Sequence`, or none). | +1 outside | likely |
| F3 | wording | J1 in `textdistance.md` and the note at `base.py:82:28` | They say that `libraries.py:170-199` registers 19 (module, function) pairs. It registers 17 (`rg -c '^reg\(' libraries.py`), with 17 distinct names. `libraries.json` lists the same 17. The 17 callees are right. | 0 | certain |
| F4 | wording (citation) | J2, the notes at `libraries.py:30:33` and `benchmark.py:117:33` | J2 cites the json-repair and validators precedents for `pathlib.WindowsPath.open`. Both of those packages declare `Operating System :: OS Independent` (their ledger notes say so). textdistance declares no platform (no OS classifier; CI runs on ubuntu only, `.github/workflows/main.yml`). So the precedents do not decide this case; F5 applies the batch-7 ruling. | 0 | certain |
| F5 | edges that cannot happen (batch-7 platform ruling) | `libraries.py:30:33` `LIBRARIES_PATH.open('r', ...)` in `LibrariesManager.optimize` and `benchmark.py:117:33` `LIBRARIES_PATH.open('w', ...)` in `Benchmark.save`: remove `pathlib.WindowsPath.open` at both; keep `pathlib.PosixPath.open` | What textdistance 4.6.3 declares: `setup.py:124-131` has six classifiers and no `Operating System` one; `setup.cfg` and `pyproject.toml` say nothing about platforms; `README.md` names no platform (none of the words Windows, Linux, macOS, Unix, POSIX, platform). Its own test jobs are the four jobs of `.github/workflows/main.yml` (lint, pytest-pure, pytest-external, markdownlint-cli), and each has `runs-on: ubuntu-latest` (lines 16, 28, 49, 70). So the release declares no platform through classifiers or documentation, and its own test jobs establish one platform: Linux. Under the ruling, Linux is the supported platform, and the platform-neutral wheel (`py3-none-any`) admits no other. On Linux `Path(__file__) / 'libraries.json'` is a `PosixPath`. The package has no platform branch of its own (no `sys.platform`, `os.name` or `platform` in `textdistance/`), so no other edge depends on this. | -2 outside | certain (given the ruling) |

With F1, F2 and F5 the graph has 711 edges: 332 in the package (+9)
and 379 outside (+1, -2). F5 changes no edge inside the package.

## Platforms (formerly R1, now decided)

R1 asked how to read the platform rule for a package that states no
platform. The batch-7 ruling decides it: supported platforms are those
that the release declares through classifiers or documentation, or
establishes through its own platform test jobs. textdistance declares
none, but its own CI establishes Linux, so the case is not "no platform
at all": Linux is supported; Windows and macOS are not. My earlier
opinion (keep `WindowsPath.open` because the wheel is universal) is
superseded: the ruling says that a platform-neutral wheel tag is no
evidence.

For the referee, in case a release has neither a declaration nor a
platform test job (not this case), my reading would be: no platform is
admitted by default; the receivers are named for the platform of the
release's documented test runs, or, without any, for the platform of the
benchmark's own environment, and no second platform is added.

## The writer's judgement calls

| Call | Nearest rule | Opinion |
|---|---|---|
| J1 external libraries as missing modules | "A call into a third-party module that is not installed is named as a missing module"; django-constance ruling (c): a configuration that names a factory in a missing module uses the missing-module convention | Supported. The strings are package values (`libraries.py:170-199`), not client strings. Cite ruling (c) rather than leave it to the lead. Fix the count (F3). `libraries.py:118:26` with no callee is right: every package library has `presets=None`. |
| J2 platforms | batch-7 ruling "What makes a platform supported" | Not supported: the release establishes only Linux (CI `ubuntu-latest`) and declares nothing else, so `WindowsPath.open` goes (F5); fix the citation (F4). |
| J3 classes of client sequences | B4, round-1 ruling (b), explicit type handling | Supported, except `str.split` alone at `base.py:126:28` (F2). `utils.py:14:21` without a callee is right (unannotated, undocumented, never called by the package: B5). |
| J4 vector_based | B1, rule A; `numpy.asarray` returns a base `ndarray` (it does not pass subclasses) | Supported. Leaving out numpy scalars at `44:26` follows B3 (no document or test passes a scalar). |
| J5 timeit runs generated code | micro-benchmark "Scopes without a node" (a string passed to exec belongs to the scope that calls exec, here timeit's) and "Callbacks"; README "a builtin or library callable that library code calls back is not an edge" | Supported as written: the code runs in timeit's scope, so package functions are call-backs of the package site, and outside callables (`__import__`, the external libraries) are not edges. The other reading (the strings are package code, so their outside calls count too, as fastjsonschema's `compile -> <builtin>.type`) would add 19 outside edges; I do not recommend it, because there the package itself calls `exec`. The README does not cover a library that execs package strings; this is the smaller reading. F1 applies J5 to `71:26`. |
| J6 stored callables | B2 test clause; the shared-alias ruling (path) | Supported. I checked every test: only `Matrix` instances, at NeedlemanWunsch and SmithWaterman (`test_needleman_wunsch.py:28-29`, `test_smith_waterman.py:28-29`); Gotoh's tests pass their own `sim_ident`. |
| J7 MongeElkan.algorithm | B2 (default and tests), B3 | Supported; the `Base.__repr__ -> Base.__repr__` edge through `self.__dict__` is right. |
| J8 words_combinations | B5; no package class has `equality` | Supported. |
| J9 receivers | B1 (plain public base classes; private classes only as the package makes them) | Supported. |
| J10 lazy filter | README "Limits of the site finder" (asciinema precedent) | Supported: the lambda is a callee of `run` at `134:25`, not of `filter_benchmark`. |
| J11 benchmark.py | missing modules (`tabulate.tabulate`); NamedTuple rule; funcy precedent for `collections.namedtuple._replace` | Supported. |
| J12 numpy names | micro-benchmark "Calls of instances"; "Outside names" clarification; itables precedent | Supported. In numpy 2.3.2 the dispatcher type is `tp_name = "numpy._ArrayFunctionDispatcher"` (`_core/src/multiarray/arrayfunction_override.c:760`), `dot` is made by `array_function_from_c_func_and_dispatcher` (`_core/multiarray.py:769`), and `matrix.sum` and `matrix.mean` are defined in `matrixlib/defmatrix.py:295`, `419`. Before numpy 1.25 `numpy.dot` is a Python wrapper at that public attribute, so both names stay. `reduce(numpy.dot, ...)` at `vector_based.py:95:24` rightly has no `numpy.dot` (a library call-back). |

## Exhaustive checks

- **Dispatch sets.** I rebuilt the method resolution of every algorithm
  class for `__call__`, `maximum`, `distance`, `similarity`,
  `normalized_*`, `quick_answer`, `minimum`, `_compress`, `_get_size`,
  `__init__`, and checked each `self(...)`, `self.maximum(...)` and
  `self.<method>(...)` site against the receivers that inherit the
  enclosing method: `base.py` 35:20, 42:28, 42:56, 47:31, 50:29, 57:44,
  99:32, 176:28, 176:58, 179:20, 183:32, 185:32, 187:32;
  `compression_based.py` 47:34, 64:56, 66:42, 83:32, 150:35, 192:33,
  212:34, 244:42; `edit_based.py` 458:36, 463:31, 464:31, 467:30,
  472:31, 473:31, 476:32 and every `quick_answer` call; `phonetic.py`
  149:34; `token_based.py` 215:34, 243:40, 246:60, 257:69; the
  constructor sites of every module; the `super()` calls of
  `libraries.py` (the MRO of `SameLengthTextLibrary`). All agree with the
  ledger header. The exclusions of NeedlemanWunsch and Gotoh at
  `base.py:47:31`, `50:29`, `57:44` and `176:28` are right: they override
  `normalized_distance`, `normalized_similarity` and `distance`.
- **Default rejections.** None in the ledger.
- **Functions that no site calls** (9, besides the 14 modules): `Base.normalized_similarity`, `_NCDBase._compress`,
  `DamerauLevenshtein._numpy` (its call is commented out,
  `edit_based.py:290-291`), `Levenshtein._recursive`,
  `NeedlemanWunsch.normalized_distance` and `.normalized_similarity` (no
  package caller has a NeedlemanWunsch receiver), `Euclidean.__init__`,
  `Minkowski.__init__`, `words_combinations`. Each is right; their bodies
  keep their edges (rule A).
- **Special methods and properties.** The package defines only
  `__init__`, `__call__`, `Base.__repr__`, `LibraryBase.__str__` and the
  properties `LibraryBase.setup` and `Lib.row`; no class defines
  iteration, truth, comparison, hashing or item access. I read the
  implicit sites without candidates (`--without-candidates`): none can
  reach package code. The lazy objects of package lambdas are iterated in
  the same function (`phonetic.py:128`, `131`; `libraries.py:148`)
  except the `filter` of J10. `{lib}` at `benchmark.py:57:58` is the only
  format of a package object.
- **Binding.** Every call of a package function binds: the fixed-arity
  `__call__` methods (Levenshtein, DamerauLevenshtein, JaroWinkler,
  Editex, the vector classes, NeedlemanWunsch, SmithWaterman, Gotoh,
  StrCmp95) get two sequences at each package site and in timeit's
  STMT; `MongeElkan._calc(*seqs)` gets at least two after `quick_answer`.
  Zero-argument `maximum` calls (`base.py:183:32`) enter the body before
  `max()` raises: the edges stay.
- **Notes and rejections.** I read all of them. Wrong only where F1 and
  F3 say.
- **Outside names.** All 117 checked against the micro-benchmark rules:
  builtins and their methods, import paths of module functions and
  classes (`difflib.SequenceMatcher`, `fractions.Fraction`,
  `array.array`, `codecs.encode`, `importlib.import_module`,
  `contextlib.suppress`, `timeit.timeit`), receiver classes
  (`collections.Counter.*`, `collections.defaultdict.keys`,
  `difflib.SequenceMatcher.find_longest_match`), `pathlib.Path` for the
  class call, the missing modules (17 library functions,
  `tabulate.tabulate`), the numpy names (J12). No naming error.
- **Trace.** 506 edges, none rejected, all in the graph; the report
  lists no trace edge that a site does not account for.

## Report

Sites re-derived blind: 121 (13 implicit, 57 explicit, all 53 value
sites). Disagreements: 0; two auditor doubts, both resolved for the
writer. Findings: F1 (+9 inside edges, likely), F2 (+1 outside, likely),
F3 and F4 (wording), F5 (-2 outside, by the batch-7 platform
ruling). J5 needs no ruling in my opinion: the writer's reading
follows the micro-benchmark's exec and call-back rules. The README and
the tools were clear; the batch-7 ruling closed the platform gap.

## Re-check (commit `be19285`, against `23b086d`)

Verdict: accepted. The diff of the textdistance files changes only what
F1 to F5 asked for:

- F1: `benchmark.py:71:26` has the nine package callees
  (`DamerauLevenshtein`, `Hamming`, `Jaro`, `JaroWinkler`, `Levenshtein`
  `__init__`; `DamerauLevenshtein`, `Hamming`, `JaroWinkler`,
  `Levenshtein` `__call__`). The note gives the `Iterable[Lib]` reason,
  and the reject reason at `73:27` no longer says that `lib` comes only
  from `get_installed`.
- F2: `base.py:126:28` has `<builtin>.bytes.split`, with the reason in
  the note.
- F3: the count is 17 in J1 and in the note at `base.py:82:28`.
- F4 and F5: `pathlib.WindowsPath.open` is gone at `libraries.py:30:33`
  and `benchmark.py:117:33`, and `pathlib.PosixPath.open` stays. J2 now
  rests on the referee's ruling (`b7-ruling-textdistance.md`, line 11,
  quoted word for word) and not on the json-repair and validators
  precedents.
- J3 names `bytes.split` with F2's evidence. J5 records the same nine
  edges at `71:26` (18 inside edges in all, with `86:28`) and keeps the
  outside calls of the generated code out, as the audit recommended.
- `textdistance.json`: +10 and -2 edges, exactly these pairs; 711 edges
  (332 / 379). `check.py textdistance` reports no errors. The trace
  still confirms all 506 of its edges, and none is rejected. No other
  site, callee, note or rejection changed.

One leftover sentence, with no edge effect: J1 still ends with "The lead
may rule whether a callee that the package selects by an import-path
string counts as a missing-module call". It now cites django-constance
ruling (c), so the writer may drop that sentence.
