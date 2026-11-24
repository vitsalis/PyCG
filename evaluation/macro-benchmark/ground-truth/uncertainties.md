# uncertainties: judgements of the ground truth

## Status (for resumption)

- Done: the ledger (every site decided), `uncertainties.json`,
  `uncertainties.added.json`, `uncertainties.rejected.json` (1 trace edge);
  `check.py --write uncertainties` and `check.py uncertainties` report no
  error. This file records the judgements.
- Blind audit (`uncertainties.audit.md`) answered: F1 applied (+2 inside
  edges, J21), W1 and W2 applied (J1, J10). F2 applied after the referee's ruling
  (`b7-ruling-uncertainties.md`, adopted by the lead): +2 outside edges,
  J22. The ruling confirms J3 and J4; their rules are quoted there.
- Checked against the README's "Rulings for batch 7": no entry changes
  (see "Rulings for batch 7" below).
- Codex round 1 applied (see "Codex round 1"): +1 inside edge (J23, which
  settles J6 from the PyPy 3.11 interpreter sources), +1 outside edge
  (J24), and the two metadata items (the PyPy callees at `ops.py:550`,
  `639`, `646`; the numpy notes after `b7-ruling-numpy-einops.md`). J5
  stands under that ruling.

Release 3.2.3, held as its PyPI sdist (`projects.toml`). Analysed source:
`uncertainties/` (11 modules, 146 functions with 38 lambdas, 9 classes).
The graph has 157 nodes and 557 edges (221 inside, 336 outside); the trace
confirms 530 (95.2%; the `numpy.ndarray.view` edges of J22 and J24 match
the traced name of the package's own calls); 144 of the 146 functions run in the tests
(`IndexableIter.__str__` and the property `matrix.std_devs` do not).

## Versions, implementations, platforms

- `requires-python = ">=3.8"` (pyproject.toml), classifiers 3.8 to 3.12;
  CI runs CPython 3.8 to 3.12 on Linux, Windows and macOS
  (`.github/workflows/python-package.yml`). The final classifier is no
  upper bound: names are those of CPython 3.8 and later.
- PyPy: the classifier `Implementation :: PyPy` is an explicit declaration
  of support, so PyPy 3.8 and later is admitted (README, "Versions and
  configuration"). Jython: the classifier is stale; no Jython implements
  Python 3.8, so it is not considered ("only combinations on which the
  implementation exists"). See J6 for the one place where PyPy could
  matter.
- `OS Independent`; the package has no platform branch.
- numpy is an optional dependency without a version (`arrays = ["numpy"]`):
  the bare extra admits every numpy release that satisfies it on an
  admitted Python runtime (Python 3.8 and later), with no numeric bound
  (`b7-ruling-numpy-einops.md`, adopted by the lead). `CHANGES.rst` names
  numpy 2.0 (line 61, 3.2.2) and 1.17 (line 111, 3.1.2) as supported. Both sides of the optional imports run (`core.py:70-73`,
  `ops.py:15-22`): the `NotImplementedError` branches of
  `correlated_values`, `correlated_values_norm` and `correlation_matrix`
  have their edges (`core.py:110`, `167`, `227`).
- `-O` and `-OO`: the package has no `assert` and no `__debug__`. Under
  `-OO` the docstrings are `None`; `set_doc` and the `%` templates of
  `ops.py:181-183` and `766-768` (expressions, not docstrings) still run.
  No edge changes.

## Outside names

Checked against `micro-benchmark/README.md` ("Names", "Edges") on
2026-11-23; no name changed. Functions of a module take the path that the
package imports (`warnings.warn` for `from warnings import warn`,
`math.sqrt`, `inspect.getfullargspec`); methods take the class of the
receiver (`re.Pattern.match` for the bound `match` of a compiled pattern,
`<builtin>.type.mro`, `collections.defaultdict.items`, `numpy.matrix.view`
for a unumpy.matrix, which inherits it); calls of instances are
`<class>.__call__` (`functools.partial.__call__` for the decorator of
`functools.wraps`, `numpy.vectorize.__call__`, `numpy.ufunc.__call__`,
`numpy._ArrayFunctionDispatcher.__call__`); a class called is the class
(`collections.defaultdict`, `itertools.chain`, `numpy.vectorize`,
`numpy.matrix`); a package exception without `__init__` names the first
`__init__` of its MRO through the nearest outside base (J17); the default
lambda of `IndexableIter.__init__` belongs to the class body that evaluates
it (`IndexableIter.<lambda1>`). Implicit sites have no outside callee.

## Architecture, as the ledger uses it

- `AffineScalarFunc` (`core.py:336`, public as `UFloat`) and its subclass
  `Variable` (`core.py:726`) are the numbers with uncertainty. Their
  operators are not `def`s of the dunder names. `ops.add_arithmetic_ops`
  (`ops.py:205`) installs with `setattr` the closures
  `ops._wrap.f_with_affine_output` (`__abs__`, `__neg__`, `__pos__`,
  `__trunc__`, `__add__`, `__radd__`, `__floordiv__`, `__rfloordiv__`,
  `__mod__`, `__rmod__`, `__mul__`, `__rmul__`, `__sub__`, `__rsub__`,
  `__truediv__`, `__rtruediv__`, `__pow__`, `__rpow__`; `__div__` and
  `__rdiv__` are skipped because `float` has no such method on Python 3) and
  `add_arithmetic_ops.raise_error` (`__complex__`, `__int__`, `__long__`,
  `__float__`). `ops.add_comparative_ops` (`ops.py:726`) installs
  `add_comparative_ops.__bool__` and the closures
  `force_aff_func_args.op_on_upcast_args` (`__eq__`, `__ne__`, `__gt__`,
  `__ge__`, `__lt__`, `__le__`). Then `core.py:1040-1060` replaces
  `__floordiv__`, `__mod__`, `__abs__`, `__trunc__`, `__lt__`, `__gt__`,
  `__le__` and `__ge__` by `core.deprecation_wrapper.wrapped`, which calls
  the earlier closure.
- So no candidate names an operator of a number with uncertainty. The
  ledger writes these callees by hand where package code applies an
  operator to one: `eq_on_aff_funcs` (`self - y_with_uncert`,
  `ops.py:677`), `add_comparative_ops.__bool__` (`self != 0.0`,
  `ops.py:809`), and the element operators that `numpy.dot` applies in
  `matrix.__rmul__` (`unumpy/core.py:616`, `618`). Everywhere else the
  package applies operators to floats, ints, strs, containers and numpy
  float arrays; most operator calls on numbers with uncertainty come from
  client code, which has no caller.
- Setting `__eq__` with `setattr` after the class is made does not set
  `__hash__` to `None`: `AffineScalarFunc` keeps `object.__hash__`.
  `Variable.__hash__` returns `id(self)`.
- `umath_core` wraps the math functions: those of `fixed_derivatives` and
  `num_deriv_funcs` through `core.wrap` (ops._wrap closures), those of
  `locally_cst_funcs` through `wrap_locally_cst_func`, `fsum` through
  `wrapped_fsum`; `modf`, `ldexp` and `frexp` are `def`s; ten of them are
  wrapped again by `deprecation_wrapper` (`umath_core.py:429-454`).

## Default rejections

Nine defaults; the sites that each decides (candidate-site pairs, from
`check.py --report`):

| Candidate | Sites | Accepted at |
|---|---|---|
| `ops.IndexableIter.__getitem__` | 255 | `ops.py:405:48`, `529:43` |
| `core.Variable.__hash__` | 132 | the dict and set operations with Variable keys (`core.py:317`, `488`, `490`, `917`, `unumpy/core.py:131`, `253`, `455`, and the explicit calls `core.py:207:55`, `909:20`, `920:54`, `579:67`, `773:64`, `unumpy/core.py:193:33`, `413:33`) |
| `core.LinearCombination.__bool__` | 87 | `umath_core.py:351`, `372`, `405` |
| `ops.add_comparative_ops.__bool__` | 90 | nowhere |
| `core.AffineScalarFunc.__repr__` | 49 | `core.py:801:50` (explicit `super().__repr__()`) |
| `core.Variable.__repr__` | 50 | nowhere |
| `core.AffineScalarFunc.__str__` | 47 | nowhere |
| `ops.IndexableIter.__str__` | 47 | nowhere |
| `unumpy.core.matrix.__rmul__` | 35 | `unumpy/core.py:499:28`, `557:30`, `559:26`, `560:26` |

## Judgements

**J1. Operators installed with setattr** (see "Architecture"). Each site
where a number with uncertainty is an operand in package code gets the
closure by hand (`ops.py:677:23`, `809:21`; `unumpy/core.py:616:29`,
`618:29`). `numpy.dot` on an object matrix multiplies and adds the elements
with Python's operators: `OBJECT_dot` calls only `PyNumber_Multiply` and
`PyNumber_Add` on the elements (numpy 2.3.2,
`_core/src/multiarray/arraytypes.c.src:3637-3677`; audit W1), so the
closure is a
call-back of the `numpy.dot` site (README, B5 call-back rule). The trace
has all three pairs.

**J2. Derivatives made with eval** (`ops.py:137`, `141`). The lambdas that
`get_ops_with_reflection` makes with `eval` have no node (README, Nodes:
generated code). The "mod" and "rmod" derivatives call
`partial_derivative(float.__mod__, 1)` and then its closure; these calls
belong to the site that calls the derivative, `ops.py:529:48`
(`f_with_affine_output -> partial_derivative` and
`-> partial_derivative.partial_derivative_of_f`; the first is traced).

**J3. A lazy map consumed by another function** (`umath_core.py:267`,
`ops.py:332`). `umath_core` passes `map(nan_if_exception, derivatives)` to
`core.wrap`; `_wrap` chains it (`itertools.chain`) into an `IndexableIter`,
and `next(self.iterable)` in `IndexableIter.__getitem__` consumes it. The
edge `IndexableIter.__getitem__ -> nan_if_exception` is at `ops.py:332:29`
(the package frame that iterates; the trace has it), and the `map` site
`umath_core.py:267:22` rejects the call-back. The README's rule for lazy
maps ("where library code iterates it, the package site that hands it to
the library is the caller") does not name this case exactly: here package
code calls `next()` on a library chain that holds the map. Nearest rule:
the package site whose call makes the library iterate. Confirmed by the
referee (`b7-ruling-uncertainties.md`, adopted by the lead); the rule:
"When library code consumes a lazy map or filter through another library
iterator, its callback belongs to the package site that triggers
consumption."

**J4. A dict display has no site** (`core.py:773`). `{self: 1.0}` in
`Variable.__init__` hashes the new Variable (the trace has
`Variable.__init__ -> Variable.__hash__`), but the site finder makes no
site for the keys of a dict display. The edge is written at the call that
the display is an argument of, `LinearCombination({self: 1.0})`
(`773:64`), with a note. A limit of the site finder, like those of
"Limits of the site finder". Confirmed by the referee
(`b7-ruling-uncertainties.md`, adopted by the lead); the rule: "The site
finder omits key hashing in dict displays; for a display used as a call
argument, record its package hashing edge at the enclosing call site and
note that it occurs during argument evaluation."

**J5. numpy names.** `numpy.diag`, `numpy.transpose`, `numpy.linalg.eigh`,
`numpy.linalg.inv`, `numpy.linalg.pinv` and `numpy.dot` are C
`_ArrayFunctionDispatcher` instances from numpy 1.25 and Python functions
made by `array_function_dispatch` before (sources of the pin numpy 2.3.2,
deps/uncertainties/numpy-2.3.2, read: `lib/_twodim_base_impl.py:258`,
`_core/fromnumeric.py:629`, `linalg/_linalg.py:557`, `1536`, `2177`,
`_core/multiarray.py:769`, `_core/overrides.py:162`; `eye`, `isscalar` and
`asmatrix` are plain functions with `set_module`, `lib/_twodim_base_impl.py:176-178`,
`_core/numeric.py:1964`, `matrixlib/defmatrix.py:36`). As in
itables J7, each site has both names:
`numpy._ArrayFunctionDispatcher.__call__` and the public attribute path (7
sites, 6 outside edges from reading only: the older numpy sources are not
in the read-only deps, so this follows the itables writer's reading of
numpy 1.24.4; the referee's numpy ruling, `b7-ruling-numpy-einops.md`,
keeps both forms: the public function path before 1.25 and
`numpy._ArrayFunctionDispatcher.__call__` from 1.25). `numpy.sqrt` is a ufunc (`numpy.ufunc.__call__`);
`numpy.array`, `numpy.asanyarray`, `numpy.eye`, `numpy.asmatrix`,
`numpy.isscalar` and the class `numpy.vectorize` keep their public paths
in every release. Calls of a `numpy.vectorize` object are
`numpy.vectorize.__call__`, and the function it vectorizes is a call-back
of that site (`unumpy/core.py:100`, `117`, `205`, `256`, `258`, `312`,
`338`, `459`, `461`). `view` on a unumpy.matrix or a numpy.matrix is
`numpy.matrix.view` (inherited methods are named through the class), on
an ndarray `numpy.ndarray.view`.

**J6. PyPy and keyword calls of builtins** (settled in Codex round 1).
On CPython every `f` that the package wraps refuses keyword arguments:
float slot wrappers and math functions are positional-only, and the `fsum`
lambda takes `*args`. So `f_with_affine_output` raises at `ops.py:506`
before line 550 for a keyword argument, and the package's keyword closures
`partial_derivative(f, name)` (`ops.py:372`, `408`, `544`) are never called
with a package `f`. PyPy is admitted (classifier), and its builtins bind
keywords by parameter name: the gateway names an interp-level argument
`w_x` as `x` and keeps `self` (`pypy3.11-v7.3.20-src/pypy/interpreter/gateway.py:227-236`),
argument parsing refuses a keyword only for parameters marked
positional-only (`argument.py:459-480`; the marker `__posonly__`,
`gateway.py:267`), and neither float's `descr_pow(self, space, w_rhs,
w_third_arg)` (`objspace/std/floatobject.py:583-584`) nor the math
functions (`module/math/interp_math.py`) carry it. PyPy's `inspect`
reads builtin code objects (`lib-python/3/inspect.py:1954-1957`,
`2113-2118`), so the argspec loop of `_wrap` sees their names. On PyPy
therefore `umath.sin(x=ufloat(...))` reaches the `nan_if_exception`
closure at `ops.py:550`, `umath.fmod(x=...)`, `umath.gamma(x=...)` and
`umath.lgamma(x=...)` reach `partial_derivative_of_f` at 550 and its
keyword lines 639 and 646 (`math.fmod`, `math.gamma`, `math.lgamma`;
pairs that already exist through 641 and 648), and the power operator
gives one new pair (J23). The float operators with keywords do not: their
argspec names (`self`, `rhs`) get the analytic derivatives, which are
lambdas of `x` and `y` and cannot bind those keywords (`TypeError`, no
edge).

**J7. `math.hypot` through numerical differentiation** (`ops.py:641:31`,
`648:32`). From Python 3.8 `math.hypot` takes any number of arguments;
`fixed_derivatives` gives two derivatives (`umath_core.py:204`). For
`umath.hypot(1.0, 2.0, x)` only the third argument has an uncertainty, so
`none_converter` makes `partial_derivative(math.hypot, 2)` and its closure
calls `math.hypot`. (With an uncertainty at position 0 or 1 the two-argument
lambda cannot bind three arguments: `TypeError`, no edge there.) 1 edge
from reading only: `partial_derivative_of_f -> math.hypot`.

**J8. The keyword branch of `partial_derivative_of_f`** (`ops.py:639`,
`646`). By J6, on CPython the package's own keyword closures are not
called with a package `f` (on PyPy they are: J6, J23). The tests pass the operators and the umath
functions (ops._wrap closures) to the public `partial_derivative` with an
int `arg_ref`; the docstring documents a str `arg_ref` ("a string
represents the name of an argument in kwargs"). Admitted values combine
(README, batch 6 ruling on django-environ), so `partial_derivative(umath.sin,
"x")(x=1.0)` reaches `f_with_affine_output` at 639 and 646. The math
functions and `float.__mod__` are callees only at the positional lines 641
and 648.

**J9. `ops.py:550:31`.** Only a client's `f` that accepts keywords reaches
this line on CPython (J6), so its callees are the package's
`partial_derivative_of_f` closures (made at 372, 408, 544 for the client's
`f`; traced) and the client's own derivatives (client callbacks). On PyPy
the package's own `f` reach it too (J6): the `nan_if_exception` closures
of the umath functions join, a pair that already exists through 529.

**J10. A number with uncertainty as a float argument** (`core.py:409:36`,
`763:22`, `797:30`, `794:36`). `float(nominal_value)`, `float(value)` and
`isfinite(std_dev)` would call the `__float__` closure
(`add_arithmetic_ops.raise_error`) on a number with uncertainty. The
package passes floats, ints and numpy numbers there, and the documentation
and the tests pass floats (`ufloat(nominal_value: float, std_dev: float)`);
a number with uncertainty is no value of the package for these roles (B3),
so these four sites have no edge to `raise_error`. The package does pass a
number with uncertainty to a float conversion elsewhere: `math.ldexp(x, i)`
and `math.frexp(x)` in the constant branches of `umath_core.ldexp` and
`frexp` (J21, audit F1 and W2). The trace has `raise_error` only as called
by the tests.

**J11. No `__eq__` from hash collisions.** Dicts and sets with Variable keys
compare stored hashes before calling `__eq__`. `Variable.__hash__` is
`id(self)`: distinct live Variables have distinct ids, below the hash
modulus on 64-bit builds; on 32-bit builds a collision would need two
addresses that differ by 2**31 - 1 (odd, impossible for aligned objects)
or by 2**32 - 2 (which needs an address below 2). So no dict or set site calls `op_on_upcast_args` (unlike
netaddr, README "Call sites and candidates").

**J12. `set()` and `set.intersection` hash the keys** (`core.py:909:20`,
`920:54`; `unumpy/core.py:193:33`, `413:33`). CPython reuses stored hashes
only for an exact `dict` (and sets): a `collections.defaultdict` (every
expanded combination, `core.py:298`) and a `dict_keys` view are iterated,
and each Variable is hashed. `set.intersection` hashes each element of a
non-set argument.

**J13. Expanded linear combinations are dicts or defaultdicts**
(`core.py:316:64`, `476:59`; `unumpy/core.py:193:58`, `413:58`). A
Variable's own combination is the dict display `{self: 1.0}`; `.derivatives`
of any other number expands it into the `collections.defaultdict` of
`expand`. Both receivers are named (`<builtin>.dict.items` and
`collections.defaultdict.items`, likewise `keys`).

**J14. `copy.deepcopy` of a LinearCombination** (`core.py:579:67`).
`LinearCombination` has `__slots__`, `__getstate__` and `__setstate__` and
no `__deepcopy__`: `copy.deepcopy` uses `__reduce_ex__(4)`, which calls
`__getstate__`, deep-copies the state and calls `__setstate__`; the
Variable keys of the dicts are copied with `Variable.__deepcopy__` and
hashed into the new dicts; a non-expanded combination's list of pairs
recurses into the same calls. All five call-backs are traced.

**J15. unumpy.matrix as the right operand** (`unumpy/core.py:499`,
`557`, `559`, `560`). For a unumpy.matrix argument of `inv` or `pinv`,
`array_derivative` returns a unumpy.matrix (numpy.vectorize keeps the
subclass), `numpy.asmatrix` returns it unchanged, and `.H` of a real matrix
is its transpose, still a unumpy.matrix. As a subclass of numpy.matrix
that overrides `__rmul__`, its `__rmul__` runs first for `numpy.matrix *
unumpy.matrix`. The other products have a numpy.matrix or an ndarray on the
right (the nominal values are a numpy.matrix after
`unumpy_to_numpy_matrix`).

**J16. `wrap_array_func`** (`unumpy/core.py:138`). The package never calls
it; its `func` is the client's (the tests pass `numpy.linalg.pinv` and a
function of their own), so `func(...)` at 178 and 244 has no callee, and
the trace edge `wrapped_func -> numpy._ArrayFunctionDispatcher.__call__`
(the tests' `numpy.linalg.pinv`) is rejected in `uncertainties.rejected.json`.

**J17. Exceptions without `__init__`.** `NegativeStdDev(...)` and
`NotUpcast(...)` name `<builtin>.Exception.__init__`, `NotParenUncert(...)`
names `<builtin>.ValueError.__init__` (the first `__init__` of the MRO,
named through the nearest base outside the package).

**J18. `frexp` builds a broken combination** (`umath_core.py:413`).
`LinearCombination([2**-exponent, aff_func._linear_part])` is a list of two
items, not of a pair. `expand` pops the LinearCombination and fails to
unpack it (`core.py:311`, `TypeError`, no package callee). No edge beyond
the construction.

**J19. Lambdas stored, not called.** `staticmethod(lambda value: value)`
(`core.py:377`; numpy's `mean` calls it from client code),
`itertools.repeat(lambda *args: 1)`, `core.wrap(flat_fsum, ...)` and
`wraps(lambda arg_list: ..., ...)` (`umath_core.py:317`, `319`),
`numpy.vectorize(...)` constructors and `numpy.matrix.I.getter(getI)`
(`unumpy/core.py:625`) only store their function: the candidate is
rejected there, and the site that calls the stored object has it.

**J20. `inspect.signature(numpy.linalg.pinv)`** (`unumpy/core.py:568`)
exists on every supported Python, so the `except AttributeError` branches
(`569-577`) do not run (they make no call anyway).

**J21. The constant branches of `ldexp` and `frexp`** (`umath_core.py:386:26`,
`422:26`; audit F1, accepted after checking the source). `to_affine_scalar(x)`
returns `x` itself when it is a number with uncertainty (`ops.py:738-739`).
When its linear part is empty (`LinearCombination.__bool__` is
`bool(self.linear_combo)`, `core.py:270-275`), the `else` branch passes `x`
itself, not its nominal value, to `math.ldexp` or `math.frexp`. They convert
it to a C double through `type(x).__float__`, which is `raise_error`
(`ops.py:282-291`), so `raise_error` runs and raises `TypeError`. Such
values come from the package itself: the off-diagonal elements of
`unumpy.ulinalg.inv([[x, 0.0], [0.0, y]])` have zero derivatives, which
`unumpy/core.py:454` skips, so their dicts stay empty and they are
`AffineScalarFunc(0.0, LinearCombination({}))` (`459-462`); the public
`to_affine_scalar(2.0)` (`ops.py:743`; the tests use it, `tests/helpers.py:95`)
and `AffineScalarFunc(2.0, {})` ("can also be used to represent
constants", `core.py:342`) make them too. `x` is in the role ("Version of
frexp that works for numbers with uncertainty", `umath_core.py:394-397`).
`modf` returns in its `else` branch without calling `math`. Confirmed by
the referee (`b7-ruling-uncertainties.md`). +2 inside
edges: `ldexp -> raise_error`, `frexp -> raise_error`. The README's
"Limits of the site finder" does not list this case (audit R2): a builtin
that converts its argument through a special method installed with
`setattr` gets no candidate.

**J22. `inverse.view` on an ndarray** (`unumpy/core.py:490:31`, `531:31`;
audit F2, the referee's ruling `b7-ruling-uncertainties.md`, adopted by
the lead). `inv_with_derivatives` and `pinv_with_derivatives` are public
(C: `uncertainties.unumpy.core`, no underscore, nothing marks them
private). Their shared contract (`unumpy/core.py:355-377`) makes `arr` a
"NumPy ndarray of scalars" and `input_type` the type of the input
array-like, with no requirement that the two agree. So an ndarray `arr`
combines with `numpy.matrix` as `input_type`
(`next(inv_with_derivatives(numpy.array([[2.0]]), numpy.matrix,
iter(())))`, not run). `numpy.linalg.inv` and `pinv` then return an
ndarray, and the matrix branch calls its `view`. Both sites name
`numpy.ndarray.view` beside `numpy.matrix.view` (the receiver of the
package's own calls). The rule: "Public helpers retain independently
admitted parameter combinations even when their package callers use a
narrower pairing." +2 outside edges.

**J23. The power operator called with keywords, on PyPy** (`ops.py:639:31`,
`646:32`; Codex round 1). `UFloat.__pow__(self=ufloat(2.0, 0.1), rhs=3.0)`
calls the `__pow__` closure with keywords only: `pos_w_uncert` is empty,
`names_w_uncert` is `["self"]`, and line 506 calls
`no_complex_func(self=2.0, rhs=3.0)`, which calls `float.__pow__(self=2.0,
rhs=3.0)`. On PyPy that binds (J6). `no_complex_func` takes `*args,
**kwargs`, so the argspec loop of `_wrap` finds no name, and line 541's
`setdefault` makes `partial_derivative(no_complex_func, "self")`. Line 550
calls its closure, whose keyword lines 639 and 646 call `no_complex_func`
for the two shifted values. +1 inside edge:
`partial_derivative_of_f -> no_complex_result.no_complex_func`. On CPython
`float.__pow__` refuses the keywords at line 506, and there is no edge.

**J24. `umatrix` on matrix inputs** (`unumpy/core.py:661:49`; Codex round 1).
`uarray`'s contract admits numpy arrays ("valid arguments for
numpy.array ... numpy.ndarray, etc.", `unumpy/core.py:294-296`); a
`numpy.matrix` or a `unumpy.matrix` is an ndarray by class. `numpy.vectorize`
keeps the subclass (`asanyarray` before and after its ufunc,
`lib/_function_base_impl.py:2615-2628`), so `uarray` returns a matrix
and `.view(matrix)` runs on it. It inherits `view` from numpy.matrix:
`numpy.matrix.view` beside `numpy.ndarray.view`. +1 outside edge.

## Codex round 1

Codex's full audit (`reviews/audit-b7-r1/uncertainties.md`): 2 missing
pairs, 0 false, 0 naming, 2 metadata items. All four were checked against the
source and applied: J23 (+1 inside), J24 (+1 outside), the PyPy callees at
`ops.py:550:31` (`nan_if_exception.wrapped_f`), `639:31` and `646:32`
(`math.fmod`, `math.gamma`, `math.lgamma`) with J6 rewritten, and the numpy
notes (no exact floor; the changelog's numpy 2.0 and 1.17). None disputed.
557 edges (221 inside, 336 outside).

## Rulings for batch 7

The README's "Rulings for batch 7" (2026-11-23), checked against the
ledger. None changes an entry:

- Platforms (pyfiglet, textdistance, websocket-client): `Operating
  System :: OS Independent`, and CI on Linux, Windows and macOS; the package
  has no platform branch, and no outside callee depends on the platform.
- Forwarded stub values, call-backs that need an admitted input (pgvector):
  no missing module.
- Changelog as a support statement (pgvector): `CHANGES.rst` names numpy
  2.0 (line 61) and 1.17 (line 111); with the unbounded extra, the numpy
  ruling (`b7-ruling-numpy-einops.md`) admits every release on an admitted
  Python, so the names of J5 stand.
- A package callable handed to client code (websocket-client): the
  package hands no callable to client code through a callback interface.
  Its returned wrappers (`core.wrap`, the umath and unumpy functions) are
  public functions in any case.
- Abstract stream annotations, compiled patterns on CPython 3.6 (segno):
  there are no streams, and Python 3.6 is not admitted (`>=3.8`).
- A module docstring that excludes the module (segno): `core.py:4` ("Main
  module ..., with internal functions") and `umath_core.py:5`
  ("Implementation of umath.py, with internals") do not exclude their
  modules from the public API: `uncertainties.core` holds `ufloat` and
  `wrap`, and `umath` re-exports `umath_core.__all__`.
- A callable that the release calls internal (pymysql): the comment
  `core.py:57` ("used internally and will be removed by linter if not
  here") covers `nan_if_exception`, `modified_operators` and
  `modified_ops_with_reflection`. If it makes `nan_if_exception` private,
  nothing changes: the ledger already admits only the derivatives that the
  package passes (`ops.py:60:21`). `parsing.py:169` ("not exposed") covers
  `str_to_number_with_uncert`, whose one package caller passes a `str`
  (`core.py:987`); its callees are `str` methods either way. Nothing calls
  `partial_derivative` internal, so J8 stands.
- Admission per parameter, explicit type handling in private functions,
  module flags (pymysql): no entry admits a class at one parameter through
  another. The module dictionaries of `formatting` (`EXP_PRINT` and the
  others), which `format_num`'s docstring documents as customizable, hold
  client values when a client assigns them (`formatting.py:276:40`).
- Refusal tests (tinydb): the tests' refusals (`tests/test_power.py:153`,
  `174`; `test_uncertainties.py:62-75`, `1297-1320`; `test_unumpy.py:51-58`)
  pass floats or numbers with uncertainty to public operators and
  functions. These are values that the ledger already admits, so they add
  no site value.
- Protocols, unannotated mode parameters, re-exported private classes
  (tinydb, pyfiglet): not present.

## Sites

- Dict displays: see J4.
- Implicit sites without candidates that the ledger adds by hand: J1
  (`ops.py:677:23`, `809:21`).
- Sites that a default decides and whose candidate the ledger accepts: see
  "Default rejections".

## Trace

524 trace edges; 523 are in the graph, 1 rejected (J16). The failing test
`tests/test_umath.py::test_math_module` (README, declared failure) fails at
an assertion on a message; its calls before the assertion are in the trace.
The 27 edges from reading only: `partial_derivative_of_f ->
no_complex_func` (J23), the `NotImplementedError` and error
branches, `ldexp`/`frexp -> raise_error` (J21), the older numpy names (J5), `__rfloordiv__` and `__rmod__`,
`math.hypot` (J7), `IndexableIter.__str__`, `matrix.std_devs`, and
`AffineScalarFunc.__repr__`/`std_score -> AffineScalarFunc.std_dev` (the
tests format only Variables there).
