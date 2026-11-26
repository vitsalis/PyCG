# einops: judgements of the ground truth

## Status (for resuming)

- Done (pass 1 and a second reading, 2026-11-23 00:10): every site of the
  skeleton has an entry; `check.py --write einops` and `check.py einops`
  report no error; the 12 trace edges that the graph lacks are in
  `einops.rejected.json` (J7, J8; 9 of them since the Corrections of
  2026-11-25).
- J3 and J5 are decided (J3 by the referee's ruling; J5 from the framework
  sources under `deps/einops/`). J1 is overruled by the referee (2026-11-23):
  35 sites carry the ruling's path families ("Stub paths"), 12 of them open
  path sets ("Open path sets"). Keras's attribute tracking is decided
  too (J5, last item), with the tensorflow backend's tracking read since.
- Codex audit round 1 (2026-11-23, `reviews/audit-b7-r1/einops.md`):
  applied its 23 missing edges ("Audit round 1" below) and its metadata
  corrections; its ruling case and its unsure case went to the lead.
- The ledger is the source. The writer drafted it with scratch scripts
  (`$TMPDIR/b7-gt-einops/tools/merge.py` merges hand-written decision
  blocks into the skeleton and drafts `-> <builtin>.f` for plain calls of a
  builtin name); every entry was read against the source. To change an
  entry, edit the ledger and run `check.py --write einops`.

## The package

Release v0.8.2 (commit `8e911db`). Analysed source: `einops/` without
`einops/tests/`: 17 modules, 276 functions, 38 classes.
`pyproject.toml` declares `requires-python = ">=3.9"` and no dependency;
the classifiers name only "Python :: 3". So the supported versions are
CPython 3.9 and later; no other implementation is declared. The trace ran
with numpy 2.4.1 only (`EINOPS_TEST_BACKENDS=numpy`): torch, tensorflow,
keras, jax, flax, cupy, paddle, oneflow, tinygrad, pytensor and mlx are not
installed, so every call into them is named as a missing module (README,
"Callees outside the package"), and all their code comes from reading.

## Backends and tensors (J1)

`get_backend` (`_backends.py:22`) walks `AbstractBackend.__subclasses__()`
recursively and makes a backend for each framework already in
`sys.modules`. So the receivers of a backend method are the eleven package
subclasses: `NumpyBackend`, `JaxBackend` (a `NumpyBackend` whose `self.np`
is `jax.numpy`), `TorchBackend`, `CupyBackend`, `TensorflowBackend`,
`TFKerasBackend`, `OneFlowBackend`, `PaddleBackend`, `TinygradBackend`,
`PyTensorBackend`, `MLXBackend`. `AbstractBackend` is never instantiated
(private module; not in its own `__subclasses__()`). A client's own
subclass is client code. Each inherited method of `AbstractBackend` lists
the subclasses that inherit it in its entry's note.

**J1 (judgement, overruled by the referee and adopted by the lead,
2026-11-23; `reviews/b7-ruling-numpy-einops.md`): stub paths survive
assignment.** The initial tensor of a backend is named by the class that its
`is_appropriate_type` checks with `isinstance` (B4): `numpy.ndarray`,
`jax.numpy.ndarray`, `torch.Tensor`, `cupy.ndarray`, `tensorflow.Tensor`
and `tensorflow.Variable` (`_backends.py:360`), `oneflow.Tensor`,
`tinygrad.Tensor`, `pytensor.tensor.TensorVariable`, `mlx.core.array`.
The writer first also named by that class every later framework result
(a variable or a forwarded value). The ruling overrules this: "A
missing-library result retains its access path through assignment,
storage in package-created containers, and forwarding through package
functions, just as within one expression. Concrete input-type evidence
supplies independently admitted class paths; it does not replace a
produced stub's path, while subscripting a missing-library value, unpacking
it, or performing arithmetic on it supplies no inferred result path." So a
value that a framework function returned keeps its stub path in later
statements and functions (`torch.stack.reshape`,
`torch.Tensor.reshape.permute`, `torch.unsqueeze.expand`), beside the class
paths that `is_appropriate_type` establishes for the initial inputs. See
"Stub paths" below for how the ledger applies it, and "Open path sets".

**J2 (judgement): paddle and keras tensors have no class.**
`PaddleBackend.is_appropriate_type` calls `paddle.is_tensor` and
`TFKerasBackend` calls `tf.is_tensor` and `K.is_keras_tensor`: the
package names no class. So a method call on a client's paddle tensor
(`x.reshape`, `x.transpose`, `x.tile`, `x.unsqueeze`, `x.expand`,
`x.detach().numpy()`, `.squeeze(0)`; `_backends.py:565-614`) has no class
callee (B5). Since the ruling on J1, the results of `paddle.stack` and of
the methods that follow it keep their stub paths, so five paddle sites
(`573:62`, `578:27`, `585:24`, `591:25`, `600:27`) and the paddle part of
`AbstractBackend.reduce` (`102:37`) have those callees ("Stub paths"); the
other paddle sites (`565:24`, `565:32`, `594:22`, the uncalled `tile`) see
only client tensors and keep no callee. The keras backend calls only
functions of `tensorflow.keras.backend`.

**Reductions.** `operation` is always one of `_reductions` at a backend's
`reduce`: `_prepare_transformation_recipe` refuses any other string
(`einops.py:328-329`) and a callable never reaches `backend.reduce`
(`_reduce_axes`). So the value sites `getattr(x, operation)(...)` name
the seven methods for each tensor class, and the final `raise
NotImplementedError` of `TorchBackend.reduce` and `OneFlowBackend.reduce`
has no callee (a check that cannot fail, B1; `_backends.py:258`, `:511`).
`TorchJitBackend.reduce` handles only five, so its raise is reached for
"any" and "all", which the torch `Reduce` layer accepts
(`_torch_specific.py:42`).

**Binding.** `MLXBackend.add_axes(self, x, new_position)` cannot bind the
call `backend.add_axes(tensor, n_axes=..., pos2len=...)` of
`_apply_recipe` (`einops.py:249`): no edge (README, "Edges"). Its body
keeps its edge (`mlx.core.expand_dims`). `MLXBackend` does not override
`add_axis`, which no package code then reaches for it.

**`_debug_importing`.** The two `print` calls of `get_backend`
(`_backends.py:50`, `:55`) are under a private module flag that is
`False` and that no package code sets: no edge (a client's assignment to a
private module attribute is a change of package internals).

## numpy (J3)

**J3 (judgement; the referee's ruling, adopted by the lead, 2026-11-23,
`reviews/b7-ruling-numpy-einops.md`).** einops declares no numpy
requirement (`pyproject.toml:24`: no dependencies; numpy is an optional
backend). Where no dependency requirement is declared, the release's
explicit version-support declarations decide (batch 6, django-constance
(f)); an unpinned installation command in the CI does not admit every
historical release, and the benchmark's pin (numpy 2.4.1) establishes its
own configuration without bounding support. No declaration of einops
establishes a numpy release before 1.25, and the array-API interface
states "numpy >= 2.0" (`README.md:325`). So each dispatched numpy function
is named `numpy._ArrayFunctionDispatcher.__call__` (the form from 1.25 on),
read in numpy 2.4.1 (`deps/einops/numpy-2.4.1/`): `numpy.stack`
(`_core/shape_base.py:378`), `tile` and `expand_dims`
(`lib/_shape_base_impl.py:1199`, `:515`), `einsum`
(`_core/einsumfunc.py:1244`), `broadcast_to`
(`lib/_stride_tricks_impl.py:400`), `concatenate` and its alias `concat`
(`_core/multiarray.py:197`; `_core/__init__.py:143`), `reshape`,
`transpose` and its alias `permute_dims` (`_core/__init__.py:147`), `min`,
`max`, `sum`, `mean`, `prod`, `any` and `all` (`_core/fromnumeric.py`); the
trace agrees. `numpy.arange`, `asarray`, `array` and `from_dlpack` are C
functions (`_core/multiarray.py:58-61`) and keep their path.
Counterfactual (corrected): if a pre-1.25 release of the ordinary backend
were established, only the five `NumpyBackend` sites could gain the public
function names `numpy.stack`, `.tile`, `.concatenate`, `.expand_dims` and
`.einsum` (`_backends.py:181:29`, `184:28`, `187:35`, `193:35`,
`196:30`). The other ten dispatched sites (`array_api.py:12`, `67`, `69`,
`113`; `einops.py:263`, `265`, `273`, `277`, `283`, `285`) use the
array-API interface, whose numpy requirement is >= 2.0.

## Stub paths (the ruling on J1)

The ruling defines path families per backend (its notation: `.m` appends
an attribute; `.mⁿ` repeats the same attribute n >= 1 times;
`R = {min, max, sum, mean, prod, any, all}`): `B` the initial tensors (the
class path and the stacked list, `M.stack`), `X = B ∪ B.reshape`,
`Q = X ∪ X.t` (after the optional transpose), `D` the reduction results,
`F` the added-axis results and `H` the final reshape family (with
`M.arange.reshape` from `_enumerate_directions` and `M.einsum.reshape`
from a no-bias `EinMix` post-rearrangement). The ledger applies its two
tables: 27 sites in `einops._backends` (`96:25`, `99:27`, `102:37`,
`245:26`, `247:26`, `249:25`, `251:26`, `255:42`, `261:25`, `271:24`,
`377:43`, `505:29`, `507:29`, `509:42`, `515:25`, `525:24`, `573:62`,
`578:27`, `585:24`, `591:25`, `600:27`, `641:25`, `644:25`, `648:38`,
`655:27`, `658:24`, `661:30`) and 8 in `einops._torch_specific` (`30:26`,
`32:26`, `34:25`, `36:26`, `39:27`, `46:25`, `62:24`, `74:25`). Each site
keeps its existing callees and gains the family members it lacked; the
ruling's five edges are removed (`torch.Tensor.expand` at `_backends.py:
271:24` and `_torch_specific.py:62:24`, `oneflow.Tensor.expand` at
`525:24`, `tinygrad.Tensor.repeat` at `658:24`, `tinygrad.Tensor.cat` at
`661:30`). The paddle sites `573:62`, `578:27`, `585:24`, `591:25`,
`600:27` now have callees: a client paddle tensor still has no class path
(J2), but `paddle.stack` results and what follows them keep their paths.

The callee lists were generated by a script of the writer's own from the
ruling's definitions: `families.py` (kept with `apply_families.py` in the
audit records' directory `b7-audits/einops/writer-tools/`; its output
`families.json`) and `tools/apply_families.py`, which adds the members to
the 35 entries and nothing else. Each result was read against the source
branch that reaches the site; the source contradicts no part of the
ruling's tables (checked: MLX's `add_axes` cannot bind, so its `F` is
empty; OneFlow's `min` and `max` results are unpacked, `_backends.py:505`,
`:507`; a recipe that reduces adds no axes, so `F` starts from `Q`; the
torch layers reach `TorchJitBackend`, not `TorchBackend`, so only JIT has
`torch.einsum.reshape`; the TF `EinMix` reaches `TensorflowBackend.shape`
with its `tf.einsum` result, `layers/tensorflow.py:88`, `:92`). One reading
the ruling does not spell out: Keras 3's `Layer.__call__` may convert its
input's dtype before `call` (`keras/src/layers/layer.py:837-850`), which
would replace the `tensorflow.einsum` result by Keras's conversion result;
`tensorflow.einsum.shape.as_list` holds for the call without conversion
(input dtype equal to the layer's), which is the default policy's case.

## Open path sets

Where a family repeats an attribute (`.rⁿ`, `.unsqueezeⁿ`: a loop
reassigns `x = x.prod(...)`), the path set has no finite bound. By the
lead's decision the ledger records the members with n = 1 and n = 2 only,
and each such site is an open path set, as jsonpickle's "Open receiver
sets" (README, "Rulings for batch 6"): a stated lower bound, not
counted in the audit's stop rule; the benchmark reports outside edges with
and without einops. 12 sites:

| Site | Family (the ruling's notation) | Why it is open |
|---|---|---|
| `_backends.py:96:25` (`AbstractBackend.reshape`) | `H` for JAX, CuPy, PyTensor, MLX, Torch, OneFlow | Torch's `D` has `Q.rⁿ` for any, all, prod, and OneFlow's `D` has `Q.rⁿ` for sum, mean, prod, any, all (`_backends.py:254-255`, `:503-509`) |
| `_backends.py:255:42` (`TorchBackend.reduce`) | `Q.rⁿ`, r in {any, all, prod} | the loop `x = getattr(x, operation)(dim=i)` (`:254-255`) |
| `_backends.py:509:42` (`OneFlowBackend.reduce`) | `Q.rⁿ`, r in {sum, mean, prod, any, all} | the loop over the reduced axes (`:503`, `:509`) |
| `_backends.py:585:24` (`PaddleBackend.add_axes`) | `Q.unsqueezeⁿ.expand` | the loop `x = self.add_axis(x, ...)` (`:582-583`) |
| `_backends.py:591:25` (`PaddleBackend.reshape`) | `H` for Paddle | its `F` is `Q.unsqueezeⁿ.expand` |
| `_backends.py:600:27` (`PaddleBackend.add_axis`) | `Q.unsqueezeⁿ` | called in the loop of `add_axes` (`:582-583`) |
| `_backends.py:641:25` (`TinygradBackend.reshape`) | `H` for Tinygrad | its `D` is `Q.rⁿ` and its `F` is `Q.unsqueezeⁿ.repeat` |
| `_backends.py:648:38` (`TinygradBackend.reduce`) | `Q.rⁿ`, r in R | the loop over the axes (`:647-648`) |
| `_backends.py:655:27` (`TinygradBackend.add_axis`) | `Q.unsqueezeⁿ` | called in the loop of `AbstractBackend.add_axes` (`:112-113`) |
| `_backends.py:658:24` (`TinygradBackend.tile`) | `Q.unsqueezeⁿ.repeat` | its input comes from that loop |
| `_torch_specific.py:39:27` (`TorchJitBackend.reduce`) | `Q.prodⁿ` | the loop `x = x.prod(dim=i)` (`:38-39`) |
| `_torch_specific.py:74:25` (`TorchJitBackend.reshape`) | `H` for JIT | its `D` has `Q.prodⁿ` |

## array_api (J4)

**J4 (judgement): the arrays of `einops.array_api`.** The functions call
`tensor.__array_namespace__()` on the client's array and then functions of
that namespace. The README lists "numpy >= 2.0", MLX, pydata/sparse,
cubed, ndonnx, jax, cupy and dask: libraries, not classes, "to name a
few". The writer admits only numpy: the README names it with its version,
the tests pass numpy arrays, and numpy 2.x's `ndarray.__array_namespace__`
returns the module `numpy` (read in numpy 2.5.4, `methods.c:3080`). The
other libraries name no class, and their namespace objects would only have
stub paths (`mlx.core.array.__array_namespace__.reshape`). The lead may
rule otherwise.

## Shapes: HashableTuple and UnknownSize (J6)

Both classes are made only by the tensorflow backends:

- `TensorflowBackend.shape` returns a tuple with an `UnknownSize()` for each
  unknown dimension in eager mode (a `tf.Variable` with a partly unknown
  shape), and a `HashableTuple` in graph mode when the shape holds
  unhashable symbols (`_backends.py:373-386`). `TFKerasBackend.shape`
  always returns a `HashableTuple` (`:446`).
- A backend shape reaches `einops.reduce` (`len`), `_apply_recipe` (the
  lru_cache key of `_reconstruct_from_shape`, `einops.py:235`),
  `_reconstruct_from_shape_uncached` (`shape[input_axis]`, `:172`),
  `parse_shape` (`len`, `zip`), `_enumerate_directions` (`enumerate`,
  `len`), `pack` (`len`, slices) and `unpack` (`len`, index, slices). These
  sites accept `HashableTuple.__len__`, `__iter__` and `__getitem__`; the
  default rejections decide every other site.
- **J6 (judgement): parse_shape's output as axes_lengths.** The docstring
  of `parse_shape` documents its output as the `axes_lengths` of other
  operations (`einops.py:687-690`; the tests do it with symbolic backends,
  `tests/test_other.py:212`), so an `UnknownSize` can be a known axis
  length. This admits `UnknownSize.__rmul__` and `__mul__` at
  `known_product *= axes_lengths[axis]` (`einops.py:180`). The writer
  applies it to `reduce`, `rearrange`, `repeat` (axes_lengths annotated
  `Size`, which is `typing.Any`) and to the `Rearrange` and `Reduce`
  layers ("behaves identically to einops.rearrange"), not to `EinMix`,
  whose axes_lengths are the sizes of the weights it creates, nor to
  `einops.array_api`, whose axes_lengths are annotated `int`.
- `UnknownSize.__hash__` and `__eq__` at the lru_cache call of
  `_apply_recipe` (`einops.py:235`): the key hashes the shape and the
  axes_lengths tuple; every `UnknownSize` hashes as `hash(None)`, so a
  lookup that meets a stored key of the same hash compares the tuples, and
  `UnknownSize.__eq__` runs (CPython compares by identity first, then by
  `__eq__`).
- `UnknownSize.__eq__` at `parse_shape`'s `axis_length != 1` and
  `axis.value != axis_length` (`einops.py:726`, `:734`): `UnknownSize`
  defines no `__ne__`; the inherited `object.__ne__` calls `__eq__`. And at
  `unpack`'s `-1 in p_shape` (`packing.py:147`): `packed_shapes` is
  documented as pack's output, whose shapes are slices of the backend's
  shape. `prod` then never gets an `UnknownSize` (the `in` test is true for
  such a shape), so `packing.prod` has no `UnknownSize` edge.
- `_product` (`einops.py:33`): `__rmul__` and `__mul__`, from
  `_reconstruct_from_shape_uncached`'s output groups. `length //
  known_product` (`:191`): `UnknownSize.__floordiv__` when the length is an
  `UnknownSize`.
- `_optimize_transformation` is called by no package code; its tests pass
  lists of ints (`tests/test_other.py:73`): its `*=` sites have no callee.

## Formatting

- `AnonymousAxis.__repr__`: at the two set differences of
  `_prepare_transformation_recipe` that can hold an anonymous axis (repeat,
  left side; reduce, right side; `einops.py:317`, `:327`), and at
  `_report_axes`'s `report_message.format(axes)` (`_einmix.py:12`): the
  right side's anonymous axes reach the first `_report_axes` call (line
  72) before the check of line 83, and the bias shape's anonymous axes are
  checked by no line (lines 131, 135). Formatting a set calls `repr()` of
  each element. The rearrange difference (`:313`) cannot hold one (line 310
  raises first), nor the sets of lines 323 and 406.
- `RearrangeMixin.__repr__` and `ReduceMixin.__repr__`: `{self!r}` in
  `multirecipe` (`layers/__init__.py:39`, `:89`). In every framework
  layer the mixin comes before the framework base, so its `__repr__` wins.
  No package code formats a backend or an `EinMix`.

## Layers (J5, J7)

- The mixins `RearrangeMixin` and `ReduceMixin` are public
  (`einops.layers`); flax's `setup` instantiates them directly. Their
  `super().__init__()` reaches `<builtin>.object.__init__` (a mixin itself)
  or the framework base: `torch.nn.Module.__init__`,
  `tensorflow.keras.layers.Layer.__init__`, `paddle.nn.Layer.__init__`,
  `oneflow.nn.Module.__init__` (named through the base class that the
  package names).
- **J7 (judgement): `_EinmixDebugger`.** It is private
  (`einops.layers._einmix`) and "Used only to test mixin"; only the tests
  instantiate it (`tests/test_layers.py:365`, `376`). By B1 it is no
  receiver, and the three trace edges that it makes
  (`_EinmixMixin.__init__ -> <builtin>.object.__init__`,
  `initialize_einmix -> _EinmixDebugger._create_parameters`,
  `-> _EinmixDebugger._create_rearrange_layers`) are rejected (rule A: a
  direct test invocation of a private API supplies receivers that B1
  excludes). `_EinmixMixin` itself is never instantiated.
- flax's `EinMix(nn.Module, _EinmixMixin)` never runs
  `_EinmixMixin.__init__` (flax makes the class a dataclass); its `setup`
  calls `initialize_einmix`. The flax `Rearrange(...)` and `Reduce(...)`
  calls (`layers/flax.py:68`, `:72`) run the dataclass `__init__` that flax
  generates: no node, no package edge.
- **J5 (judgement, decided from the sources): calls of a package layer
  through its framework base.** `self.pre_rearrange(input)` and
  `self.post_rearrange(result)` in each `EinMix.forward`/`call`/`__call__`
  call a package layer whose call machinery comes from the framework (a
  definition made through a missing library: the README's base-class
  exception). The lead supplied the sources
  (`deps/einops/README.md`: the newest release on or before einops 0.8.2's
  upload, 2026-01-26; oneflow 0.9.0 as `einops/tests/run_tests.py` pins
  it). The edges and their support:
  - torch 2.10.0: `torch.nn.Module.__call__` and `Rearrange.forward`
    (`layers/torch.py:62`, `:67`). `torch/nn/modules/module.py:1915` sets
    `__call__ = _wrapped_call_impl` (`:1772`), which calls `_call_impl`
    (`:1780`), whose `forward_call` is `self.forward` (`:1781`, `:1787`,
    `:1830`; `_slow_forward` under tracing also calls `self.forward`,
    `:1752-1755`). Name: the micro-benchmark README's "Calls of instances"
    and "Inherited methods" (the class that the package names), and the
    README's "Outside names" (a function installed at a public outside
    attribute keeps that path): `torch.nn.Module.__call__`, not
    `Module._wrapped_call_impl`.
  - tensorflow 2.20.0, whose `tf.keras` is Keras 3 (keras 3.13.1):
    `tensorflow.keras.layers.Layer.__call__`, `Rearrange.build` and
    `Rearrange.call` (`layers/tensorflow.py:87`, `:92`).
    `keras/src/layers/layer.py:828-829` (`__call__`, decorated by
    `filter_traceback`, a wrapper at the same public attribute) runs
    `_maybe_build` (`:878`, `:1474-1490`), which calls `self.build`: the
    `build_wrapper` that `Layer.__new__` installs (`:222-241`) and that
    calls `Rearrange.build` (at the first call). Then `super().__call__`
    (`:951`, `:953`), `Operation.__call__` (`keras/src/ops/operation.py:
    32-77`), calls `self.call`, directly or through `symbolic_call` and
    `compute_output_spec` (`operation.py:79-82`, `:99-101`;
    `layer.py:1145-1147`). The Keras backend (`layer.py:54-63`, the
    library's `KERAS_BACKEND` configuration) changes only the mixin below
    `Layer`; `__call__` is `Layer`'s on every backend, so the names do not
    depend on it (the ruling on library behaviour on supported platforms
    and configurations).
  - paddle 3.3.0: `paddle.nn.Layer.__call__` and `Rearrange.forward`
    (`layers/paddle.py:51`, `:57`). `paddle/nn/layer/layers.py:1824-1835`:
    `__call__` calls `self.forward` directly or through
    `_dygraph_call_func` (`:1737`, `:1772`, `:1775`); the package does not
    override `_build_once` (`:1734`).
  - oneflow 0.9.0: `oneflow.nn.Module.__call__` and `Rearrange.forward`
    (`layers/oneflow.py:48`, `:53`). `oneflow/nn/modules/module.py:150-169`:
    `__call__` calls `self.forward` (`:163`) between the forward hooks.
  - flax 0.12.2: `flax.linen.module.wrap_method_once.wrapped_module_method`,
    `Rearrange.__call__` and `Rearrange.setup` (`layers/flax.py:76`,
    `:81`). `Module.__init_subclass__` (`flax/linen/module.py:1034-1046`)
    wraps every method defined in the subclass's own body with
    `wrap_method_once` (`:1135-1152`, `:629-649`); the wrapper (`:693-700`)
    runs `_call_wrapped_method` (`:1167`), which first runs `_try_setup`
    (`:1194`; `:1478-1495`: the wrapped `setup`, once, `:1494`) and then
    the method (`:1216`, `:1218`). The wrapper is a local function of flax
    installed on a package class, so it is named where it is defined (the
    micro-benchmark README, "Functions without an attribute path"; the
    itables precedent `dash.development.base_component._explicitize_args.
    wrapper`).
  - Changed by the sources (2026-11-23): the same wrapper is also a callee
    of `self._create_rearrange_layers(...)` and `self._create_parameters(...)`
    in `initialize_einmix` (`_einmix.py:108`, `:162`), for the flax
    `EinMix`, whose two methods flax wrapped; inside `setup` the wrapper's
    `_try_setup` does nothing (`:1478-1483`). And flax's `_try_setup`
    registers the dataclass fields (`:1490-1492`) through `_freeze_attr`
    (`:1469`, `:458-461`), so the flax `EinMix`'s `self.sizes` is a
    `FrozenDict` when `setup` passes it as `axes_lengths`:
    `axes_lengths.items()` (`_einmix.py:98`) also has
    `flax.core.frozen_dict.FrozenDict.items` (the class's defining module,
    `flax/linen/module.py:52`).
  - Keras attribute tracking (decided 2026-11-23 from the extract that
    the lead added): `Layer.__setattr__` (`keras/src/layers/layer.py:
    1559-1565`) passes every stored value to `self._tracker.track`, which
    wraps a dict in `TrackedDict` (`keras/src/utils/tracking.py:70-72`,
    `:96-98`; tracking is on unless a `DotNotTrackScope` is active,
    `:18-19`, and none is around the package's assignments). So on a Keras
    layer `self.axes_lengths` (`layers/__init__.py:22`, `:73`;
    `_einmix.py:62`) is a `TrackedDict`, which subclasses `dict` and does
    not define `items` (`tracking.py:219-292`). By the rule that an outside
    method is named by the class of the receiver, also when the class
    inherits it, `self.axes_lengths.items()` at `layers/__init__.py:25`,
    `:29`, `:75`, `:79` and `_einmix.py:205` has
    `keras.src.utils.tracking.TrackedDict.items` beside
    `<builtin>.dict.items` (the other frameworks and the plain mixins keep a
    plain dict). The path has no underscore component (rule C); the class
    is not exported by `keras_export`. With Keras's tensorflow backend,
    `super().__setattr__` reaches `KerasAutoTrackable.__setattr__`
    (`keras/src/backend/tensorflow/trackable.py:15-28`, in the extract
    since), whose `sticky_attribute_assignment` returns the value
    unchanged (`:31-58`); TensorFlow's own container wrapping checks exact
    types (`type(value) == dict`, `== collections.OrderedDict`, `== list`:
    tensorflow 2.20.0 `tensorflow/python/trackable/data_structures.py:
    87-121`, in `deps/einops/`), so a `TrackedDict`, a `dict` subclass,
    stays unwrapped and the names hold on every Keras backend. The construction of a
    Keras layer runs `Layer.__new__` and `Operation.__new__`
    (`operation.py:114-200`), which call no package method.

## Other judgements

- **J8: rejected trace edges** (`einops.rejected.json`): the three
  `_EinmixDebugger` edges of J7, and the nine `lru_cache` wrapper
  spellings (Corrections of 2026-11-25).
- **J9: `allow_ops_in_compiled_graph`** (`_torch_specific.py:103-132`):
  `torch` is a missing module; the version tests and the `ImportError`
  are answers of the library, so every branch runs (README, "Missing
  libraries"): `warnings.warn` and the six `torch._dynamo.allow_in_graph`
  calls, which register the functions and do not call them.
- **J10: `PyTensorBackend.create_symbol`** (`_backends.py:691`):
  `isinstance(shape, tuple | list)` raises `TypeError` on Python 3.9 before
  `isinstance` runs, and calls it from 3.10: the edge stays (a supported
  version makes it).
- **J11: the lru_cache wrappers.** `_prepare_transformation_recipe`,
  `_compactify_pattern_for_einsum`, `analyze_pattern` and
  `_reconstruct_from_shape` are `functools.lru_cache` wrappers; a call of
  one has the callees `_functools._lru_cache_wrapper.__call__` and the
  wrapped function (on a cache miss, which a fresh process has). The
  decorator sites name `functools.lru_cache.decorating_function`, which
  wraps without calling.
- **J12: `EinopsError`** subclasses `RuntimeError` and defines no
  `__init__`: `EinopsError(...)` is `<builtin>.RuntimeError.__init__`.
- **J13: `keyword.iskeyword`** is `frozenset(kwlist).__contains__` in
  CPython; it keeps the path that the package imports (the trace lists
  that name as an alias).

## Audit round 1 (Codex, 2026-11-23)

- **numpy scalars at the final reshape** (`_backends.py:96:25`, 22
  edges). A numpy reduction over every axis returns a numpy scalar, not a
  0-d array, and `_apply_recipe` then reshapes it (`reduce(x, "a -> ()",
  "min")` on a 1-d array: `einops.py:247`, then `:251`). The scalar keeps
  the dtype for `min` and `max`; `any`/`all` give `bool_`, `mean` a float.
  Each concrete scalar class inherits `reshape` from `numpy.generic`
  (numpy 2.4.1 `_core/src/multiarray/scalartypes.c.src:2697`) and is named
  one by one (batch 6, jsonpickle (e)): `numpy.bool_`, `int8` to `int64`,
  `uint8` to `uint64`, `float16`, `float32`, `float64`, `longdouble`,
  `complex64`, `complex128`, `clongdouble`, `datetime64`, `timedelta64`,
  and the distinct C-integer classes of the supported platforms (`intc`,
  `uintc` on Linux ILP32; `longlong`, `ulonglong` on Linux LP64;
  `_core/src/multiarray/arraytypes.h.src:99`), with the names of the
  jsonpickle ledger. No other site gets a scalar: transpose comes before
  the reduction, and a recipe that reduces adds no axes.
- **flax `setup` through a direct call** (`_einmix.py:108:38`, 1 edge).
  `initialize_einmix` is public on `einops.layers.flax.EinMix` (rule C:
  no underscore on that path). A client that calls it on a bound `EinMix`
  whose `setup` is pending (`bind` makes a scoped clone,
  `flax/linen/module.py:2037-2038`; construction leaves `setup` pending,
  `:1330-1390`) reaches the wrapped `_create_rearrange_layers`, whose
  `_try_setup` (`:1194`) runs the wrapped `setup` (`:1494`):
  `initialize_einmix -> einops.layers.flax.EinMix.setup`. On that path
  the outer `_create_rearrange_layers` then raises at its first
  assignment (`self.pre_rearrange = None` outside `setup` on an
  initialized module: `SetAttributeFrozenModuleError`,
  `flax/linen/module.py:1252-1281`), so `:162:32` is not reached on it.
- **Metadata**: the note at `_backends.py:181:29` no longer says "2.x"
  (J3: no pre-1.25 release is established); the 35 family notes name the
  archived generator `b7-audits/einops/writer-tools/families.py`;
  the tracking text above is updated.
- **The ruling case, resolved** (the lead, 2026-11-23, adopting the
  writer's and the auditor's reading): the eight unconditional
  `raise NotImplementedError(...)` calls in the bodies of the uncalled base
  methods (`AbstractBackend.is_appropriate_type`, `arange`,
  `stack_on_zeroth_dimension`, `tile`, `concat`, `is_float_type`;
  `_EinmixMixin._create_rearrange_layers`, `_create_parameters`;
  `_backends.py:72:34`, `89:34`, `105:34`, `119:34`, `124:34`, `129:34`;
  `_einmix.py:194:34`, `198:34`) keep their edges: rule A keeps a body's
  edges whether or not anything calls the function, and B1 limits which
  receivers reach receiver-dependent calls, not calls that do not depend
  on the receiver. The 8 edges stay.
- **The unsure case, decided from the flax 0.12.2 NNX sources** (added to
  `deps/einops/flax-0.12.2/flax/nnx/` after the audit): with Keras's jax
  backend and NNX enabled (`keras/src/backend/config.py:236-259`, the
  library's configuration), `JaxLayer` derives from `BaseLayer(nnx.Module)`
  with `pytree=False` (`keras/src/backend/jax/layer.py:3-13`). No edge
  changes:
  - Attribute storage: `Layer.__setattr__` still wraps the dict in a
    `TrackedDict` first (`layer.py:1559-1565`); its `super().__setattr__`
    then reaches `Pytree.__setattr__` and `_setattr`
    (`flax/nnx/pytreelib.py:618-644`), which, for a class with
    `pytree=False`, only checks the trace context (`:746-748`) and stores
    the value unchanged with `object.__setattr__` (`:641-642`). So
    `self.axes_lengths` stays a `TrackedDict`, and the `items` names hold.
  - Class creation: `Pytree.__init_subclass__` (`pytreelib.py:492-605`)
    registers the class with the graph and reads type hints; it calls no
    package method (the package classes have no class annotations).
  - Calls of the layer: `Layer.__call__` comes before `nnx.Module` in the
    MRO, so `self.pre_rearrange(inputs)` keeps its callees; nnx.Module
    defines no `__call__` (`flax/nnx/module.py:51`). `repr` keeps
    `RearrangeMixin.__repr__` first in the MRO.
  - Construction: the metaclass of a Keras layer is then `ModuleMeta`
    (`module.py:45-48`, a subclass of `PytreeMeta`), whose `__call__`
    (`pytreelib.py:399-400`) runs `_graph_node_meta_call` (`:407-421`):
    `cls.__new__` (Keras's `Layer.__new__`), then `_pytree_meta_construct`
    (`:402-403`), which calls `self.__init__`: `RearrangeMixin.__init__`,
    as the ledger has at `layers/tensorflow.py:62:43` and `:66:44`; the
    `check_pytree` branch does not run (`pytree=False`). Whether the call
    of a package class whose metaclass from outside the package overrides
    `__call__` also has that `__call__` as an outside callee (here
    `ModuleMeta.__call__`) was a case that neither README decided. The
    referee ruled (`reviews/b7-ruling-einops-metaclass.md`, adopted by the
    lead): NNX mode is an admitted library configuration (Keras's
    documented `keras.config.set_nnx_enabled` and `KERAS_NNX_ENABLED`,
    `keras/src/backend/config.py:236-259`, `:441`), and the call adds the
    outside edge `EinMix._create_rearrange_layers ->
    flax.nnx.module.ModuleMeta.__call__`, named through the concrete
    metaclass (not `PytreeMeta`), at `layers/tensorflow.py:62:43` and
    `:66:44`; the `RearrangeMixin.__init__` edge stays. No other site of
    einops calls a package class whose metaclass overrides `__call__` in
    an admitted configuration: only the Keras layers can have `ModuleMeta`,
    the package constructs only the tensorflow `Rearrange`, and none of
    the other frameworks' bases in the extracts (torch, paddle, oneflow,
    flax linen, Keras without NNX, TensorFlow's `Trackable`) has a
    metaclass.
- **numpy `intc`/`uintc`** (`_backends.py:96:25`): the referee ruled that
  they stay (`reviews/b7-ruling-einops-platform.md`): an admitted
  operating system includes its architectures and ABIs unless the release
  restricts them, so 32-bit Linux, where these classes are distinct from
  `int32`/`uint32` (`numpy/_core/src/multiarray/arraytypes.h.src:99`),
  is admitted. No edge change.

## Corrections of 2026-11-25

The referee's `ruling-lru-3.md` (adopted by the lead; README, "Rulings for
the corrections of 2026-11-25") names a call of an `lru_cache` wrapper on
CPython through the type that `_functools` exports: `functools` imports
`_lru_cache_wrapper` from `_functools` without listing it in `__all__`
(CPython 3.10.22 `Lib/functools.py:12`, `:642`; 3.12.16 `:645`; 3.15.2
`:738`), a private re-export that establishes no public class path, and
`_functools` exports the type under that attribute
(`Modules/_functoolsmodule.c`, 3.10.22 `:1462`, type name
`functools._lru_cache_wrapper` at `:1419`; 3.15.2 `:1969`, `:1908`).
`functools._lru_cache_wrapper.__call__` becomes
`_functools._lru_cache_wrapper.__call__` here (outside; edge count
unchanged):

| Caller | Site |
|---|---|
| `einops.array_api.reduce` | `einops/array_api.py:17:48` |
| `einops.array_api.pack` | `einops/array_api.py:53:60` |
| `einops.array_api.unpack` | `einops/array_api.py:74:60` |
| `einops.einops._apply_recipe` | `einops/einops.py:235:119` |
| `einops.einops._apply_recipe_array_api` | `einops/einops.py:259:115` |
| `einops.einops._prepare_recipes_for_all_dims` | `einops/einops.py:457:49` |
| `einops.einops.reduce` | `einops/einops.py:539:48` |
| `einops.einops.einsum` | `einops/einops.py:938:45` |
| `einops.packing.pack` | `einops/packing.py:69:60` |
| `einops.packing.unpack` | `einops/packing.py:138:60` |

The trace names the type by its facade qualname, so its 9 pairs `caller ->
functools._lru_cache_wrapper.__call__` are rejected as naming artefacts in
`einops.rejected.json` (rule A).
