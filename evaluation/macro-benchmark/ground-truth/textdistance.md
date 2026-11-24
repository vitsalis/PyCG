# textdistance: judgements of the ground truth

Status (writer): the ledger covers all 14 modules and every site is
decided; `check.py --write textdistance` reports no error. All 506 trace
edges are in the graph (none rejected). The blind audit's F1 to F3 are
applied (703 to 713 edges: 332 inside, 381 outside) and F4's citation is
corrected; after the referee's platform ruling (R1, audit F5) the two
`WindowsPath.open` edges are gone: 711 edges (332 inside, 379 outside).

Release 4.6.3 (commit `faa25f6`). Analysed source: `textdistance/` (14
modules, 182 functions with 8 lambdas, 54 classes). `setup.py` sets
`python_requires='>=3.5'`, but `algorithms/base.py`, which every
algorithm module imports, starts with `from __future__ import annotations`
(Python 3.7 and later; so do the other annotated modules except
`algorithms/vector_based.py`, whose annotations are evaluated), and the code uses f-strings, so the release runs on
CPython 3.7 and later. It
states no other implementation, no Python version classifier and no
platform. The ledger is `textdistance.ledger`; the graph
`textdistance.json` is generated from it. The ledger header gives the
receiver sets and the method resolution of every algorithm class.

## Architecture, as the ledger uses it

- Every algorithm is a class derived from `Base` or `BaseSimilarity`
  (`algorithms/base.py`); the package makes one module-level instance of
  most of them, and a client calls the instance (`__call__`) or its public
  methods `distance`, `similarity`, `maximum`, `normalized_*`,
  `quick_answer`. These methods dispatch on `self`, so most package edges
  are dispatch sets (`self(*sequences)` at `base.py:35:20` and `179:20`,
  `self.maximum(...)` at seven sites).
- `quick_answer` calls `external_answer`, which looks up the libraries
  registered for the class name in a clone of `libraries.prototype`
  (`libraries.py:166-199`) and calls the first that applies.
- The compression classes share `_NCDBase.__call__`, which calls
  `_get_size` and `_compress` on `self`.

## Judgements

- **J1. The external libraries (`base.py:82:28`, `libraries.py:118:26`).**
  `external_answer` calls `func(*prepared_sequences)`, where `func` is
  `getattr(import_module(module_name), func_name)` for the 17 (module,
  function) pairs that `libraries.py:170-199` registers; `optimize()` keeps
  all 17 (`libraries.json` lists each; audit F3 corrected the count). The libraries are the package's
  declared extras (`setup.py` `extras_require`), and the default
  `external=True` reaches them when they are installed. They are not
  installed in the test environment, so they are named as missing modules
  by their access path: 17 distinct names, as django-constance ruling (c)
  does for a configured factory in a missing module. A library object that a client
  registers or builds (with presets, attr or another module) selects a
  client value: no callee at `libraries.py:118:26`. The blind audit
  found this supported by django-constance ruling (c) and by B2 ("the
  package's own code passes it there"); no further ruling was needed.
- **J2. Platforms (`libraries.py:30:33`, `benchmark.py:117:33`).** The
  referee's ruling, adopted by the lead (audit R1 and F5): "When platform
  classifiers and documentation are silent, the release's platform test
  jobs establish support; neither silence nor a platform-neutral wheel
  admits additional platforms." textdistance has no Operating System
  classifier and no platform in its documentation, and its CI jobs run on
  ubuntu only (`.github/workflows/main.yml`), so Linux is its supported
  platform: `LIBRARIES_PATH.open` is `pathlib.PosixPath.open` only (-2
  outside edges to `pathlib.WindowsPath.open`).
- **J3. Classes of client sequences.** The compared sequences are client
  objects. A concrete outside type is named where an annotation fixes it
  (`str`: StrCmp95, Editex, MRA, LCSSeq, LCSStr, RatcliffObershelp, B4),
  where the code checks the type (`isinstance(empty, (str, bytes))`,
  `compression_based.py:60`; `isinstance(sequences[0], str)`, `:81`), and
  where the package makes the value (the lists of `_get_sequences` for
  qval None or > 1, the bytes of `_BinaryNCDBase.__call__`). `Sequence[...]`
  fixes no type, and the README asks that "everything should work not only
  with strings" (round-1 ruling (b)). So `type(sequences[0])()` at
  `compression_based.py:58:35` has `str`, `bytes` and `list`;
  `type(data)()` at `190:31` only `str` (BWTRLENCD has no qval parameter);
  `s.split()` at `base.py:126:28` has `str.split` (the str of the
  annotated callers) and `bytes.split` (client bytes, which the package
  handles explicitly at `simple.py:39-40` and `compression_based.py:60`,
  with the documented `qval=None`: audit F2); `t.split()` in
  `words_combinations`
  (`utils.py:14:21`) has no callee (no annotation, no documentation).
- **J4. vector_based (`vector_based.py:44:26`, `71:31`, `94:26`).** The
  module is public (no underscore) although `algorithms/__init__.py` does
  not import it and its docstring calls it a draft, so its classes are
  receivers (B1) and keep their edges. `s1` and `s2` pass through
  `numpy.asarray`, which returns an ndarray; the ledger takes the inputs as
  vectors (the classes compare vectors), so `result.sum()` is
  `numpy.ndarray.sum`. Scalar inputs would make numpy scalars there; they
  are not considered (no document or test passes one).
- **J5. timeit runs generated code (`benchmark.py:71:26`, `86:28`).**
  `timeit` compiles the setup and STMT strings into a function and calls
  it. Following the generated-code rule (fastjsonschema precedent), the
  package functions that this code calls belong to the package site that
  starts it: at `86:28` the `__init__` of DamerauLevenshtein, Hamming,
  Jaro, JaroWinkler and Levenshtein (`setup` builds
  `textdistance.{alg}(external=False)` for each name of `get_algorithms`)
  and their `__call__` (Jaro runs `JaroWinkler.__call__`). The same nine
  edges are at `71:26` (audit F1): `get_external_benchmark` takes
  `installed: Iterable[Lib]`, so the Libs of `get_internal_benchmark`,
  whose setup is this code, are admitted there too. The outside calls of
  the generated code (`__import__`, and the external libraries that the
  setup of `LibraryBase.setup` imports) are not edges. 18 inside edges.
- **J6. Callables stored by the constructors.** `test_func`, `sim_func`
  and `sim_test` default to `self._ident` (`Base._ident`, a staticmethod).
  The tests pass a `Matrix` instance as `sim_func` of NeedlemanWunsch and
  SmithWaterman (`tests/test_edit/test_needleman_wunsch.py:29`,
  `test_smith_waterman.py:29`), so `Matrix.__call__` is a callee at
  `edit_based.py:501:63` and `553:63`. `SimFunc` and `TestFunc` are aliases
  of a bare `Callable` (`types.py:7-8`), so the shared-alias ruling (path)
  admits the Matrix only there: not at Gotoh (`624:40`, where the tests
  pass their own function) or at Prefix's `sim_test` (`simple.py:32:33`).
- **J7. MongeElkan.algorithm (`token_based.py:243:40`, `246:60`,
  `257:69`).** Unannotated; the default is `DamerauLevenshtein()`
  (line 228) and the tests pass `textdistance.jaro_winkler`
  (`tests/test_token/test_monge_elkan.py:19`). Another package algorithm
  is an arbitrary package object (B3). So `maximum` is `Base.maximum` or
  `JaroWinkler.maximum`, and `similarity` is `Base.similarity` or
  `BaseSimilarity.similarity`. `Base.__repr__` formats `self.__dict__`, so
  it calls `Base.__repr__` of the stored algorithm and of a stored Matrix
  (`base.py:168:39`).
- **J8. `words_combinations` (`utils.py:23:21`).** `f` is a client value:
  no test or document passes a package object, and no package algorithm
  has the attribute `equality` that line 19 reads before the call.
- **J9. Receivers (B1).** `Base` and `BaseSimilarity` are plain public
  classes whose `__init__` does not raise, so they are receivers of their
  own methods: `Base.__call__` (it raises `NotImplementedError`) is a
  callee at `base.py:35:20` and `179:20`. `_NCDBase` and `_BinaryNCDBase`
  are private and never instantiated: only their public subclasses are
  receivers, so `_NCDBase._compress` is no callee (every subclass
  overrides it).
- **J10. A lazy filter iterated elsewhere (`benchmark.py:100:22`,
  `134:25`).** `filter_benchmark` returns `filter(lambda ...)` without
  iterating it; `run` iterates it with `list(...)` at `134:25`, so the
  lambda is a callee there (added by hand: the site finder offers it only
  at the `filter` call).
- **J11. benchmark.py.** It imports `tabulate` (the benchmark extra), which
  the test environment lacks: `tabulate.tabulate` is a missing module.
  `Lib` is a `typing.NamedTuple`: its calls add no edge, and `_replace` is
  `collections.namedtuple._replace` (the funcy precedent). The
  `if __name__ == "__main__":` block is module code.
- **J12. numpy names.** numpy is installed in the test environment and
  unpinned by the package. `numpy.zeros`, `numpy.arange` and
  `numpy.asarray` are plain functions; `numpy.sqrt` is a ufunc
  (`numpy.ufunc.__call__`); `numpy.dot` is an array-function dispatcher,
  so it has `numpy._ArrayFunctionDispatcher.__call__` and `numpy.dot` (the
  itables precedent for releases before 1.25); `numpy.matrix` is a class.
  Both sides of every optional `numpy` and `lzma` import run.

## Outside names

Every outside callee was checked against the naming rules of
`micro-benchmark/README.md` ("Names", "Edges", "Missing modules"): import
paths for module functions and outside classes (`difflib.SequenceMatcher`,
`codecs.encode`, `functools.reduce`, `contextlib.suppress`,
`timeit.timeit`, `array.array`), the class of the receiver for methods
(`collections.Counter.values`, `collections.defaultdict.keys`,
`pathlib.PosixPath.open`, `numpy.ndarray.sum`, `numpy.matrix.sum`),
`<class>.__call__` for calls of instances (`numpy.ufunc.__call__`,
`numpy._ArrayFunctionDispatcher.__call__`), the place of definition for a
library local function (`collections.namedtuple._replace`), the access
path for missing modules, and the first `__init__` of the MRO for package
classes (`Base.__init__` for MRA, LCSStr, RatcliffObershelp, Length,
Identity, Bag; no edge for the NamedTuple `Lib`). In numpy 2.3.2,
`zeros`, `arange` and `asarray` come from `_multiarray_umath`
(`_core/multiarray.py:12-17`, exported as `numpy.*`), and `dot` is an
`_ArrayFunctionDispatcher` (`_core/multiarray.py:770`,
`_core/overrides.py:162`). No name changed.

## Trace

506 trace edges, all in the graph; none rejected. The trace does not run
`benchmark` or `vector_based` (no test imports them) or the external
libraries (not installed), so their edges come from reading.
