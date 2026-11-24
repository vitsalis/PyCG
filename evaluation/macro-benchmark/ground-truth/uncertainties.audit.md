STATUS (re-check done): the committed ledger and graph (787ede5) are correct at 555 edges (220 inside, 335 outside). Nothing is left for this audit.

# uncertainties: blind audit of the ground truth (batch 7)

Release 3.2.3, PyPI sdist (SHA-256 `76a5653e…`). Audited files, as
committed at `68a7e45` (ledger of `f58fbfc`): `uncertainties.ledger` (539
site entries, 9 default rejections, 113 notes), `uncertainties.json` (551
edges: 218 inside, 333 outside), `uncertainties.added.json` (24 edges),
`uncertainties.rejected.json` (1 trace edge), `uncertainties.md` (J1 to
J20). `check.py uncertainties` reports no errors; the trace confirms 527 of
551 edges.

I judged the files by the README's scope rules (A, B1 to B5, C), its
clarifications and the rulings for batch 6. I read the package, its
tests and `doc/` as data, the numpy 2.3.2 sources under
`deps/uncertainties/`, and PyPy's `interp_math.py` under `deps/_pypy/`. I
ran no analysis tool and nothing of the package. Blind answers:
`/tmp/claude-501/b7-audit-uncertainties/blind-answers.md` (written before I
opened the writer's files).

**Final state (before the writer's answers).** 1 missed-edge finding (F1,
+2 inside edges), 1 doubtful omission for the lead (F2, +2 outside edges),
2 wording findings (W1, W2), 2 README remarks (R1, R2) and 1 process note
(P1). The blind sample has no writer error. If F1 and F2 are accepted, the
graph has 555 edges (220 inside, 335 outside).

## Findings

| Id | Kind | Site or edge | Evidence | Confidence | Edges |
|---|---|---|---|---|---|
| F1 | missed edges (inside) | `umath_core.py:386:26` `math.ldexp(x, i)` -> `uncertainties.ops.add_arithmetic_ops.raise_error`; `umath_core.py:422:26` `math.frexp(x)` -> the same | In `ldexp` and `frexp`, `to_affine_scalar(x)` returns `x` itself when `x` is a number with uncertainty (`ops.py:738-739`). The `else` branch runs when `aff_func._linear_part` is false, that is when its `linear_combo` is empty (`core.py:270-275`). That branch passes `x`, not its nominal value, to `math.ldexp`/`math.frexp`. Both convert `x` to a C double, which calls `type(x).__float__`; `ops.py:282-291` installs `raise_error` as `__float__`, so it runs and raises `TypeError`. (CPython: the `double` argument converter calls `PyFloat_AsDouble`, which calls `nb_float`; the math module's C source is not in the deps. PyPy: `_get_double` calls `space.float(w_x)`, `pypy/module/math/interp_math.py:19-23`, `104`, `410`.) Witnesses through the public API: (a) package-made: `unumpy.ulinalg.inv([[x, 0.0], [0.0, y]])` with numbers with uncertainty `x`, `y`: the off-diagonal elements have zero derivatives, so their dicts stay empty (`unumpy/core.py:437-462`, `454`) and they are `AffineScalarFunc(0.0, LinearCombination({}))`; then `umath.ldexp(r[0, 1], 1)`. (b) `uncertainties.core.to_affine_scalar(2.0)` (public path; the tests use it, `tests/helpers.py:95-96`). (c) `AffineScalarFunc(2.0, {})`: the class "can also be used to represent constants" (`core.py:342`). `x` is in the role: "Version of frexp that works for numbers with uncertainty" (`umath_core.py:394-397`). J10 says that no package code passes a number with uncertainty to a float conversion; these two sites do. Not in the trace. | certain | +2 inside |
| F2 | doubtful omission (outside), for the lead | `unumpy/core.py:490:31` and `531:31` `inverse.view(numpy.matrix)`: also `numpy.ndarray.view` | `inv_with_derivatives` and `pinv_with_derivatives` are public (no underscore). Their documented contract (`func_with_deriv_to_uncert_func`, `unumpy/core.py:355-377`): `arr` is a "NumPy ndarray of scalars", `input_type` the "data type of the input array-like object"; the package passes `numpy.matrix` subclasses as `input_type` (`type(array_like)`, `421`). By the ruling "Admitted values of several parameters combine" (django-environ), `inv_with_derivatives(numpy.array([[2.0]]), numpy.matrix, iter([]))` is a witness: `numpy.linalg.inv` returns an ndarray, and `issubclass(input_type, numpy.matrix)` holds, so `view` runs on an ndarray. The ledger names only `numpy.matrix.view`, which is right for every call that the package makes itself (its `arr` is then a numpy.matrix, `81:24`). J5 already says "on an ndarray `numpy.ndarray.view`". | likely | +2 outside |
| W1 | wording (no edge) | J1, `uncertainties.md:121-125` | J1 says that numpy's object dot loop (`arraytypes.c.src`) "is not among the extracted deps, so the trace is the evidence". It is now (deps README, "Added later (part 5)"): `OBJECT_dot`, `numpy/_core/src/multiarray/arraytypes.c.src:3637-3677`, calls only `PyNumber_Multiply` and `PyNumber_Add` on the elements. This confirms J1's `f_with_affine_output` at `unumpy/core.py:616:29` and `618:29`, and that `numpy.dot` calls no `__bool__` or comparison there. Cite the source. | certain | 0 |
| W2 | wording (follows F1) | J10, `uncertainties.md:226-234`; note at `core.py:409:36` | After F1, J10 should say that the package itself passes a number with uncertainty to `math.ldexp` and `math.frexp` in the constant branches (F1), and keep its B3 argument for `core.py:409`, `763`, `794`, `797`. | certain | 0 |
| R1 | README remark | B5 and "Limits of the site finder", lazy `map` | The rule "where library code iterates it, the package site that hands it to the library is the caller" does not name J3's case: package code calls `next()` on a library `itertools.chain` that holds the map (`ops.py:332`). Proposed wording: "the caller is the package function whose call runs the library code that iterates the object" (the micro-benchmark's Callbacks rule: "belongs to the snippet scope whose call made that code run"). | - | 0 |
| R2 | README remark | "Limits of the site finder" | Two limits that this ledger settles by hand: a dict display hashes its keys and has no site (J4, `core.py:773`); and a builtin that converts an argument through a special method that `setattr` installed (`math.ldexp(x)` -> `__float__`, F1) has no candidate. Add both to the list, so that the next writer and auditor look for them. | - | 0 |
| P1 | process | blind draw | Before I wrote my answers, an `rg` of mine over `ground-truth/*.ledger` printed 5 lines of `uncertainties.ledger` (253-257: `625:33` -> `<builtin>.getattr`, `629:26`, `<builtin>.type.mro`). `625:33` is in my sample. I count it apart; my answer agrees. I saw nothing else. | - | 0 |

## Step 1: blind re-derivation

Skeleton from a scratch benchmark directory (`$TMPDIR/b7-audit-uncertainties/`,
a copy of `projects.toml` and of the source): 934 sites (491 explicit, 443
implicit; 622 with candidates; 44 value sites). I numbered the sites in
(line, column) order, module by module, and drew
`random.Random(20261123).sample(range(934), 70)`. No kind dominates (52.6 %
explicit), and the largest candidate (`IndexableIter.__getitem__`) sits at
27.5 % of the sites, so I did not split the draw by kind. With the 44 value
sites (2 also drawn): 112 sites.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Drawn (37 explicit, 33 implicit; 625:33 not blind, P1) | 70 | 70 | 0 |
| Value sites not drawn | 42 | 40 | 2 |
| **Total** | **112** | **110** | **2** |

The 2 disagreements, one cause:

- **I was wrong (2):** `ops.py:639:31` and `646:32` (the keyword branch of
  `partial_derivative_of_f`). I gave no callee, because only a client's `f`
  reaches these lines from the package's own keyword closures. The writer
  has `f_with_affine_output` (J8): the tests pass the operators and the
  umath functions as `f` of the public `partial_derivative`
  (`tests/test_uncertainties.py:193`, `tests/test_umath.py:48`), the
  docstring documents a str `arg_ref` (`ops.py:603-605`), and admitted
  values combine (ruling of batch 6, django-environ). The call enters
  `f_with_affine_output` before `math.sin(x=...)` raises. The writer is
  right.
- **Writer missed an edge (0), writer edge that cannot happen (0), naming
  only (0).**

My blind doubts D1 to D3 were settled by the writer in the same way that I
would settle them: D1 (float methods at 470 only through a client's unbound
call) changes no graph edge, because 506 has them; D2 (PyPy) is J6; D3 is J3.

## Step 2: exhaustive checks

**Operators of numbers with uncertainty (the lead's first point).** No
candidate names these callees, so I read every site of the package where
an operand could be a number with uncertainty: the 195 operator sites
without candidates (`check.py --report --without-candidates`), the 106
operator sites with candidates, the 89 truth sites, every `abs`, `float`,
`int`, `bool`, `hash`, `round`, `max`, `sum`, math function and numpy call.

- Accepted by the writer, and right: `ops.py:677:23` (`self - y_with_uncert`
  -> `f_with_affine_output`), `809:21` (`self != 0.0` -> `op_on_upcast_args`),
  `unumpy/core.py:616:29`, `618:29` (`numpy.dot` multiplies and adds the
  elements, W1).
- Missed: F1 (`math.ldexp(x, i)`, `math.frexp(x)` -> `raise_error` through
  `__float__`).
- Checked, no edge: every other operand is a float, int, str, container,
  numpy float array or a client value. In detail: the derivative
  coefficients (`core.py:317`, `490`, `917`) are numbers that derivative
  functions return on nominal values (`ops.py:482-486`, `497-506`);
  `partial_derivative_of_f` shifts nominal values (`ops.py:631-650`; a
  number with uncertainty as its argument is B3, no test or document passes
  one); `std_score`'s `value` is a number (docs `user_guide.rst:629`, tests
  `test_uncertainties.py:540`); `ufloat`'s and the setter's `std_dev`
  (`core.py:794`, `1023`) and `float(nominal_value)` (`409`, `763`) are J10
  (B3); the numpy ufuncs and operators of `correlated_values`,
  `correlation_matrix`, `wrap_array_func` and `pinv_with_derivatives` act on
  float arrays; `umath.factorial(x)` with a number with uncertainty would
  call `__int__` on Python 3.8 and 3.9, but an integer is the role there
  (`umath_core.py:280-284`), so B3. No truth site tests a number with
  uncertainty (the 90 sites of the `add_comparative_ops.__bool__` default).
  No dict or set compares Variable keys with `__eq__` (J11); no package code
  hashes a non-Variable number with uncertainty (`object.__hash__`, outside).

**The nine default rejections.** I read every site that each decides
(`check.py --report uncertainties --default <candidate>`), and its explicit
sites. All right:

- `IndexableIter.__getitem__` (255 sites): the only IndexableIter is
  `derivatives_args_index`; its two subscripts (`ops.py:405:48`, `529:43`)
  accept; nothing iterates it (it has no `__iter__`).
- `Variable.__hash__` (132): every dict and set operation with Variable keys
  accepts (all 111 subscript sites listed and checked; `core.py:207:55`,
  `317`, `488`, `490`, `579:67`, `773:64`, `909:20`, `917:38`, `917:58`,
  `920:54`; `unumpy/core.py:131:33`, `193:33`, `253:36`, `413:33`,
  `455:36`). `variables |= set(...)` (`193:27`, `413:27`) reuses the stored
  hashes: no edge, correctly.
- `LinearCombination.__bool__` (87): only `umath_core.py:351`, `372`, `405`
  test a LinearCombination.
- `add_comparative_ops.__bool__` (90): see above.
- `AffineScalarFunc.__repr__` (49), `Variable.__repr__` (50),
  `AffineScalarFunc.__str__` (47), `IndexableIter.__str__` (47): the package
  formats only strs, floats, ints, classes and the client's tag; the one
  accepting site is `core.py:801:50` (`super().__repr__()`).
- `matrix.__rmul__` (35): the right operand is a unumpy.matrix only at
  `unumpy/core.py:499:28`, `557:30`, `559:26`, `560:26` (J15; for a
  unumpy.matrix argument the nominal values become a numpy.matrix at `81`,
  so `inverse_mat` and `arr` are never a unumpy.matrix in the package's own
  calls).

**Dispatch sets.** `f_with_affine_output`'s `f` at `470:21` and `506:28`
(16 float methods, `no_complex_func`, 30 math functions, the `fsum` lambda),
the derivatives at `529:48` (with the eval'd mod lambdas'
`partial_derivative` and its closure, J2), `550:31`,
`partial_derivative_of_f` at `639` to `648`, `none_converter` at `335:48`,
`wrapped_f` at `60:21`, `deprecation_wrapper.wrapped` at `core.py:1035:20`,
`op_on_upcast_args` at `779:28`, `cls` at `558:19` and `743:23`, the
vectorized callables of `unumpy/core.py`: all agree with my blind answers
(one auditor error, above).

**Lambdas made with eval** (J2): no node; the mod and rmod derivatives'
calls of `partial_derivative` and its closure sit at `ops.py:529:48`
(README, Nodes: a package function that a generated function calls belongs
to the site that calls the generated function). Right. `eval` itself calls
nothing (`137:17`, `141:17`).

**numpy names per release** (J5): read in numpy 2.3.2. `diag`
(`lib/_twodim_base_impl.py`), `transpose`, `linalg.eigh`, `inv`, `pinv` and
`dot` are `_ArrayFunctionDispatcher` objects; `eye` is a plain function
(`finalize_array_function_like` returns it, `_core/overrides.py:29-31`),
`asmatrix` and `isscalar` plain functions with `set_module`
(`matrixlib/defmatrix.py:36-37`, `_core/numeric.py:1964-1965`);
`vectorize.__call__` exists (`lib/_function_base_impl.py:2539`). numpy has
no version bound and Python 3.8 admits numpy 1.17 to 1.24, so the
`numpy.<path>` name of the older Python wrapper is right at the 7 sites (the
itables J7 and textdistance J12 precedents). Agree.

**The lazy map** (J3): `map(nan_if_exception, derivatives)`
(`umath_core.py:267`) is iterated only inside `next(self.iterable)` in
`IndexableIter.__getitem__` (`ops.py:332`), through the `itertools.chain` of
`_wrap` (`357`). The writer's placement is the micro-benchmark's Callbacks
rule (the package scope whose call made the library code run) and the
trace. Agree; the README wording is R1. The other lazy maps: `235:25`
(built and consumed in `wrapped_func`: placement does not matter, README)
and `344:26` (`map(str, ...)`: a builtin callable that library code calls
back is no edge). Right.

**Functions without a caller in the graph** (22). Each is reached only by
client code or by library code that client code starts: the dunder methods
of `AffineScalarFunc` (`__deepcopy__`, `__format__`, `__getstate__`,
`__setstate__`, `__str__`), `Variable.__repr__`, `dtype.<lambda1>` (numpy's
`mean`), `std_score`, `correlated_values`, `correlation_matrix`,
`ufloat_fromstr`, `deprecation_wrapper.wrapped` (the package applies no
`<`, `>`, `<=`, `>=`, `abs`, `//`, `%` to a number with uncertainty, and
calls no deprecated umath function), `IndexableIter.__str__`,
`add_comparative_ops.__bool__`, `wrapped_fsum.<lambda3>` (`umath.fsum`), the
three matrix properties (no package code loads `.I`, `.nominal_values` or
`.std_devs` on a unumpy.matrix), `umatrix`, `wrap_array_func` and its
closure. `raise_error` gets two callers by F1.

**Special methods and properties.** Every load and store of `nominal_value`,
`std_dev` and `derivatives` (26 sites; 4 of them load the module functions
through `uncert_core` and correctly reject the properties) names the right receivers
(`AffineScalarFunc.std_dev` and `Variable.std_dev` where `self` can be
either; `Variable.std_dev` alone in `__copy__`; `AffineScalarFunc.std_dev`
alone for `difference`, `ops.py:680:57`). The aliases `n` and `s` are never
loaded in the package. `__setstate__`'s `setattr` sets slot names only. The
copy protocol at `core.py:579:67` (J14) is right.

**Rejections and notes.** I read every site rejection and every note of the
ledger. All are right; the note at `core.py:409:36` needs W2.

**Callees outside the package** (157 names). Checked against the
micro-benchmark's "Names": module functions by the imported path
(`math.isfinite`, `math.sqrt`, `warnings.warn`, `inspect.getfullargspec`),
methods by the receiver's class (`re.Pattern.match`, `re.Match.group`,
`collections.defaultdict.items`, `<builtin>.type.mro`, `numpy.matrix.view`
for a unumpy.matrix), calls of instances as `<class>.__call__`
(`functools.partial.__call__`, `numpy.vectorize.__call__`,
`numpy.ufunc.__call__`, `numpy._ArrayFunctionDispatcher.__call__`), classes
by their path, exceptions without `__init__` through the nearest outside
base (J17). No naming error; F2 is a missing receiver class, not a name.

**Rejected trace edge** (1): `wrap_array_func.wrapped_func ->
numpy._ArrayFunctionDispatcher.__call__`, the tests' `numpy.linalg.pinv`, a
client callback (J16). Right.

**Binding check.** I checked every site with a package callee against the
callee's signature. Only the known case binds badly: J7 (`math.hypot` with
three arguments and an uncertain first or second argument: the
two-argument derivative lambda cannot bind; the third-argument path is the
edge). No other call fails to bind.

## The writer's judgement calls

| Id | Opinion |
|---|---|
| J1 | Agree; W1 (cite OBJECT_dot, now in the deps). |
| J2 | Agree: the README's rule for generated code. |
| J3 | Agree. The README does not name this case exactly (R1); the smaller extension is the micro-benchmark's Callbacks rule: the package function whose call runs the iterating library code. |
| J4 | Agree: the edge is real (the trace has it); writing it at the enclosing call with a note is the README's practice for sites that the finder lacks (R2). |
| J5 | Agree (itables J7, textdistance J12). |
| J6 | Agree that no graph edge depends on it: every pair that PyPy's keyword arguments could add already exists at another site of the same caller (I also checked PyPy's possible failure of `getfullargspec` on builtins: it adds no pair either). No ruling is needed for the graph; a note at `550:31`, `639:31`, `646:32` is enough. |
| J7 | Agree. |
| J8 | Agree (my blind answer was wrong): admitted values combine. |
| J9 | Agree. |
| J10 | Right for `core.py:409`, `763`, `794`, `797`; wrong as a general statement: F1, W2. |
| J11 | Agree. |
| J12 | Agree. (For a Variable's own exact dict, `set(derivatives1)` reuses the stored hashes; the defaultdict of any other number makes the edge.) |
| J13 to J20 | Agree. |

## Re-check under "Rulings for batch 7" (README, commit fb7ffd8)

- **Platforms.** uncertainties 3.2.3 declares `Operating System :: OS
  Independent` (`PKG-INFO:18`, `pyproject.toml:32`), and its own test job
  runs on `ubuntu-latest`, `windows-latest` and `macos-latest`
  (`.github/workflows/python-package.yml:17-19`). So Linux, Windows and
  macOS are supported by declaration and by test jobs. The package has no
  platform branch, and no library behaviour that it reaches (math, numpy,
  re, inspect, copy) calls back into the package differently by platform.
  No edge changes.
- **Implementations.** PyPy is declared (`Implementation :: PyPy`,
  `PKG-INFO:27`), with no test job and no restriction: admitted, as the
  writer has it. Jython is declared (`PKG-INFO:26`), but no Jython
  implements Python 3.8 or later (`Requires-Python: >=3.8`), so "only
  combinations on which the implementation exists" excludes it, as the
  writer has it. PyPy changes no graph edge (J6; I also checked PyPy's
  `_get_double`, which calls `__float__` as CPython does, so F1 holds on
  PyPy too).
- **`numpy.dot` call-back** (`unumpy/core.py:616`, `618`). I listed
  `deps/uncertainties/numpy-2.3.2/numpy/_core/src/` again: 39 `*.src`
  templates, `multiarray/arraytypes.c.src` among them. `OBJECT_dot`
  (`arraytypes.c.src:3637-3677`) applies `PyNumber_Multiply` to each pair
  of elements and `PyNumber_Add` to the partial sums, nothing else. On a
  unumpy.matrix of numbers with uncertainty these are the `__mul__`,
  `__rmul__`, `__add__` and `__radd__` closures, all
  `ops._wrap.f_with_affine_output`. The writer's call-back edge at both
  sites is right; only J1's statement about the sources is stale (W1).
  Unchanged: F1 (+2 inside), F2 (+2 outside, for the lead).

## For the lead

- F2 needs a decision: does the combination ruling admit a direct call of
  the public helper `inv_with_derivatives` with an ndarray `arr` and a
  matrix `input_type` (2 outside edges)? I think it does.
- No ruling is needed for J6 (no graph edge depends on it).
- R1 and R2 are README wording.

## Re-check (commit 787ede5)

Checked: `git diff f58fbfc..HEAD` of `uncertainties.ledger`, `.json`,
`.added.json`, `.rejected.json` and `.md` (this audit file left aside), and
`check.py uncertainties` (no errors; 555 edges, 220 inside, 335 outside;
the trace confirms 529).

- **J21 (F1).** `umath_core 386:26` and `422:26` have
  `-> uncertainties.ops.add_arithmetic_ops.raise_error`, with a correct
  note. The graph and the added edges have `ldexp -> raise_error` and
  `frexp -> raise_error`. Right.
- **J22 (F2).** `unumpy.core 490:31` and `531:31` have
  `-> numpy.ndarray.view` beside `numpy.matrix.view`; the note quotes the
  referee's rule. Both callers have the edge in the graph. They count as
  traced, not added: the tracer names the package's own `view` call
  `numpy.ndarray.view`, so one trace edge matches both names (the README's
  bottle case, "Construction"). Right.
- **J1 (W1)** cites `OBJECT_dot`, `arraytypes.c.src:3637-3677`. **J10
  (W2)** is narrowed to its four sites and points to J21. **J3 and J4**
  quote the referee's rules, in `uncertainties.md` and in the notes of
  `ops.py:332:29` and `core.py:773:64`. Right.
- **Nothing else changed.** The ledger diff is exactly these 6 entries (4
  callees, notes); the graph diff is exactly the 4 edges;
  `uncertainties.rejected.json` is unchanged. The other `.md` changes
  restate the outside-name check, update the J5 citations to the numpy
  2.3.2 pin, and add the check against "Rulings for batch 7". I agree with
  that check.
- One stale line, wording only: the status of `uncertainties.md` still
  lists J6 as "Open for the lead". No graph edge depends on J6, as the
  audit says. J5 stays open for the referee's numpy ruling.

**Verdict: correct at 555 edges (220 inside, 335 outside).** If the
pending numpy ruling changes the numpy names, the 7 dispatcher sites of J5
need a new check.
