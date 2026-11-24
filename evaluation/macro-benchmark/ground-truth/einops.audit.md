Status (2026-11-23, after the stub-path ruling): complete. The re-check of commit d353106 (2107 edges: 297 inside, 1810 outside) found no difference from the ruling or the source; see "Re-check after the stub-path ruling". O1 is closed. Nothing is left; the writer has no change to apply.

# einops: blind audit of the ground truth (batch 7)

Release v0.8.2, commit `8e911db`. Audited files: the ledger at commit
`90748db` of the ground-truth branch `b7-gt` (825 entries, 119 notes, 10 default
rejections), `einops.json` (823 edges: 297 in the package, 526 outside),
`einops.added.json`, `einops.rejected.json` (3 edges) and `einops.md`
(J1 to J13). `check.py einops` reports no error. The trace (numpy backend
only) has 255 edges and confirms 252; 57 of 276 functions run.

I read the package source, its README, its tests (as data, for B2), the
README of the benchmark and of the micro-benchmark, and the framework
sources of the audit records, `deps/einops/` (torch 2.10.0,
keras 3.13.1 with the 295 files now present, flax 0.12.2, paddle 3.3.0,
oneflow 0.9.0, numpy 2.4.1). I ran nothing of the package and no analysis
tool.

**Final state.** No finding changes an edge. The blind sample agrees with
the ledger on every package edge. The six disagreements are mine (naming
of numpy callees, one judgement). Five observations (O1 to O5) need no
change. O1 and O5 name framework files (TensorFlow's trackable data
structures, `flax.nnx`) that would close two points that the extract
leaves open.

## Findings

| Id | Severity | Site or edge | Evidence | Edge change |
|---|---|---|---|---|
| O1 | closed (01:05, TensorFlow 2.20.0 source) | TensorFlow's `AutoTrackable` does not wrap again | `AutoTrackable.__setattr__` (`tensorflow/python/trackable/autotrackable.py:58-70`) calls `sticky_attribute_assignment` (`data_structures.py:125-157`), which calls `wrap_or_unwrap` (`:87-121`). That function wraps by exact type only: `type(value) == dict` gives `_DictWrapper`, `type(value) == list` gives `ListWrapper` (`:110-115`; the comment at `:104-105` says the check is exact on purpose, so that dict and list subclasses are left alone). A tuple is wrapped only when it holds a Trackable, an exact dict or list, or such a tuple (`_should_wrap_tuple`, `:62-82`). So a `TrackedDict` (`axes_lengths`, `_multirecipe`) and a `TrackedList` (`_params` and its shape lists) stay as they are. `_axes_lengths`, a tuple of (name, length) tuples, stays a plain tuple. The value is then stored by `object.__setattr__` (`Trackable`, `base.py:278`, defines no `__setattr__`). No callee name changes at the five `items` sites or anywhere else. The earlier text of O1 follows. | none |
| O1 (earlier text) | info | Keras layers: `self.axes_lengths.items()` at `layers/__init__.py:25`, `:29`, `:75`, `:79`, `_einmix.py:205` -> `keras.src.utils.tracking.TrackedDict.items` | I confirm the writer's reading: `Layer.__setattr__` (`keras/src/layers/layer.py:1559-1565`) passes the value to `Tracker.track`, which wraps a dict in `TrackedDict` (`utils/tracking.py:96-98`); `TrackedDict` (`:219-292`) defines no `items`. The extract now has `backend/tensorflow/trackable.py`: `KerasAutoTrackable.__setattr__` (`:15-28`) calls `sticky_attribute_assignment` (`:31-58`), which returns the value unchanged, then `super().__setattr__` = TensorFlow's `AutoTrackable.__setattr__`. That file is not in the extract. From my memory of TensorFlow, its `data_structures.wrap_or_unwrap` wraps only an exact `dict` (`type(value) == dict`), so a `TrackedDict` stays. If the lead wants this checked, extract `tensorflow/python/trackable/data_structures.py` and `autotrackable.py` from tensorflow 2.20.0. | none |
| O2 | closed: the referee overruled the writer's J1 and my opinion here; the ledger at d353106 applies the ruling (see "Re-check after the stub-path ruling") | J1: a tensor that a framework function returned is named by its class in later statements (`_torch_specific.py:60-62`), but a chain in one expression keeps the stub path (`torch.zeros.uniform_`, `layers/torch.py:36`; `torch.Tensor.detach.cpu`, `_backends.py:238`) | The README decides the chain ("direct attribute/call chains retain their imported access path", "Missing libraries"). It does not decide a variable assigned from a stub call. The writer's choice (the class that `is_appropriate_type` checks, B4, with the docstrings' "tensor of the same type as input") is the smaller extension. Outside names only. | none |
| O3 | info (naming) | `_einmix.py:98` `axes_lengths.items()` -> `flax.core.frozen_dict.FrozenDict.items` (flax `EinMix`) | Confirmed from source: `_try_setup` re-registers the dataclass fields (`flax/linen/module.py:1490-1492`) through `_freeze_attr` (`:1469`, `:458-461`), so `self.sizes` is a `FrozenDict` when `setup` passes it on. `flax/core/frozen_dict.py` is not in the extract; whether `FrozenDict` defines `items` or inherits `Mapping.items`, the name by the receiver class is the same. | none |
| O5 | info | Keras with the jax backend and NNX on: `JaxLayer` derives from `flax.nnx.Module` (`keras/src/backend/jax/layer.py:3-14`), whose `__setattr__` and `__init_subclass__` the extract does not have | Keras's own NNX bypass covers only `_called` and `built` (`layer.py:1566-1576`). I cannot check whether `nnx.Module` stores a `TrackedDict` unchanged or calls package code at class creation. This is a configuration of a library that einops does not test. It could only add outside names. | none |
| O4 | info | `einops.py:259` (`_apply_recipe_array_api`): no `UnknownSize.__hash__` or `__eq__` | My blind answer added them through a `parse_shape` output passed as axes_lengths. The writer is right: `array_api.reduce` annotates `**axes_lengths: int` (`array_api.py:7`), and the annotation decides (B2); `array_api.rearrange` and `repeat` only forward to it, and an array-API array has no `UnknownSize` shape. Auditor error. | none |

## Re-check after the stub-path ruling (commit d353106)

The ruling is `reviews/b7-ruling-numpy-einops.md`. J3 stays with a
corrected reason. J1 and O2 are overruled: a stub result keeps its path
through assignment, through package-created containers and through
forwarding. **Verdict: the ledger applies the ruling exactly. I find no
difference at any site.**

1. **Scope of the change.** I compared the ledgers of `90748db` and
   `d353106` site by site with a parser of my own. Both have 825 sites and
   the same 10 default rejections. Callees changed at exactly 35 sites,
   which are the ruling's 27 sites in `einops._backends` and 8 in
   `einops._torch_specific`. At these sites only outside callees were
   added or removed, and no rejection or exclusion changed. No entry
   outside the 35 sites changed, notes included. In `einops.json` the 297
   inside edges are identical, and only the 25 callers of the 35 sites
   changed. `einops.rejected.json` did not change, and `check.py einops`
   reports no error.
2. **Hand derivation from the source.** I checked the prefixes against the
   code first:
   - The input of `_apply_recipe` is the client's tensor, or the
     `stack_on_zeroth_dimension` result for a list (`einops.py:529-533`).
     Then come the optional `reshape` (`:243`) and the optional transpose
     (`:245`), so the prefixes are B, X and Q.
   - A recipe that reduces cannot add axes, because a reduction refuses
     new identifiers on the right side (`einops.py:324-327`). So the
     input of `add_axes` is in Q.
   - `add_axes` runs only with a nonempty `added_axes` (`:248`), so at
     least one `unsqueeze` precedes `expand` and `repeat`.
   - OneFlow's `min` and `max` results are unpacked (`_backends.py:505`,
     `:507`), so they give no path.
   - MLX's `add_axes` cannot bind (`einops.py:249`).
   - The post-pattern of a no-bias `EinMix` is a pure regrouping
     (`_einmix.py:100-106`), so it reaches only the final reshape. A bias
     makes `result += self.bias`, which is arithmetic and gives no path.
   - The torch layers go through `TorchJitBackend`
     (`layers/torch.py:16`, `:26`). That is why only JIT has
     `torch.einsum.reshape` and the torch backend does not.
   - `_enumerate_directions` gives `M.arange.reshape` for every backend
     but JIT (`einops.py:758`).
   - `pack` stores its reshape results in its own list (`packing.py:85`),
     so `tinygrad.Tensor.reshape.cat` is right.
   - `unpack` and `asnumpy` reach these methods only with a subscript or a
     client tensor, so they give no further path.

   Then I wrote the family sets in an independent script (not the
   writer's generator, which I did not run). For twelve sites, the
   expected set equals the ledger's callee set exactly:

   | Backend | Sites | Members |
   |---|---|---|
   | torch | `255:42` | 48 |
   | paddle | `585:24` | 8 |
   | paddle | `591:25` | 70 |
   | tinygrad | `661:30` | 1 |
   | tinygrad | `641:25` | 137 |
   | tinygrad | `658:24` | 16 |
   | JIT | `74:25` | 30 |
   | JIT | `39:27` | 8 |
   | AbstractBackend | `99:27` | 17 |
   | AbstractBackend | `96:25` | 446 |
   | oneflow | `505:29` | 8 |
   | oneflow | `509:42` | 80 |

   For `96:25`, 446 is the numpy name plus H for six backends: 67 for JAX,
   66 each for CuPy and PyTensor, 65 for MLX (its F is empty), 90 for
   Torch and 91 for OneFlow. The added counts of the other 23 sites agree
   with the ruling's tables. I also looked for flows that the ruling
   leaves out and found none:
   - The tensorflow and keras backends make no method call on a tensor,
     except `x.numpy()` on a client tensor and `x.shape.as_list()`, which
     is in the table.
   - The `to_numpy` methods see only client tensors.
   - A flax, paddle or oneflow `__call__` passes its input unchanged.
   - Keras converts the input only when its dtype differs from the
     layer's (`keras/src/layers/layer.py:843-850`), so the writer's
     `tensorflow.einsum.shape.as_list` holds for the call without
     conversion.
3. **The five removed edges** are gone from `einops.json`, and each caller
   keeps its family member instead:
   - `TorchBackend.add_axes`, `OneFlowBackend.add_axes` and
     `TorchJitBackend.add_axes`: `M.unsqueeze.expand`.
   - `TinygradBackend.tile`: the 16 `.unsqueezeⁿ.repeat` paths.
   - `TinygradBackend.concat`: `tinygrad.Tensor.reshape.cat`.

   The source supports each removal. The three `expand` calls and the
   `tile` call run only after at least one `unsqueeze`, because the
   package calls these private methods only under `len(added_axes) > 0`.
   The `concat` call runs only on `pack`'s reshape results, because
   `pack` is its only caller.
4. **The twelve open sites** are exactly the sites whose family has a
   repeated attribute:
   - The reduction loops: `255:42`, `509:42`, `648:38`, and JIT `39:27`.
   - The `unsqueeze` loops: `585:24`, `600:27`, `655:27`, `658:24`.
   - The reshape families that contain them: `96:25` (through Torch's and
     OneFlow's D), `591:25`, `641:25`, and JIT `74:25`.

   Each open site lists n = 1 and n = 2 and nothing more. The other 23
   sites are finite, and their lists are complete. OneFlow's `min` and
   `max` (`505`, `507`) are finite because of the unpacking.
5. **einops.md.**
   - J1 now states the ruling and quotes it correctly.
   - J2 correctly names the paddle sites that `paddle.stack` results now
     reach, and the sites that stay without a callee: `565:24`, `565:32`,
     `594:22`.
   - J3 carries the referee's reason and the corrected counterfactual: the
     five `NumpyBackend` sites only.
   - "Stub paths" lists the 35 sites and the five removals.
   - "Open path sets" lists the same twelve sites as I find. It records
     them as a lower bound, as the lead decided.
   - One point to fix in the text, not the graph: "Stub paths" says that
     the generator lives in `$TMPDIR/b7-gt-einops/tools/`, but the lead
     says that it is kept at
     `b7-audits/einops/writer-tools/` of the audit records. The
     durable path should be named.

O2 is closed by the ruling. My blind O2 opinion (keep the writer's
statement-boundary naming) was overruled, and the current ledger is right
under the ruling.

## Re-check of the Keras tracking (after the lead's message, 00:50)

The ledger is still commit `90748db`, the one audited above (823 edges,
with `TrackedDict.items` at `layers/__init__.py:25`, `:29`, `:75`, `:79`
and `_einmix.py:205`). I judged it with the full Keras extract (295 files).

- **Does the TensorFlow backend wrap the dict again?** `Layer.__setattr__`
  (`layer.py:1559-1576`) makes the `TrackedDict` and then calls
  `super().__setattr__`. With the tensorflow backend the next class is
  `TFLayer(KerasAutoTrackable)` (`backend/tensorflow/layer.py:9`).
  `KerasAutoTrackable.__setattr__` (`backend/tensorflow/trackable.py:15-28`)
  calls `sticky_attribute_assignment` (`:31-58`), which only records the
  name for a `TrackedDict`, and it returns the same value. Then it calls
  `super().__setattr__`, which is TensorFlow's
  `tf.__internal__.tracking.AutoTrackable`. TensorFlow is not in the extract
  (O1). From memory, its `wrap_or_unwrap` wraps only an exact `dict` or
  `list`, so a `TrackedDict` or `TrackedList` stays as it is.
  Other backends: torch (`TorchLayer(torch.nn.Module)`, whose
  `_setattr_hook` changes only a non-Keras `torch.nn.Module`), numpy and
  openvino (plain classes) do not wrap the value. On jax, `JaxLayer` is a
  plain class unless NNX is on. With NNX it derives from `flax.nnx.Module`
  (`backend/jax/layer.py:3-14`), and that source is not in the extract (O5).
- **Other values that the einops Keras layers store.** I listed each
  attribute that the tf layers and their mixins set, and each later use of
  it:
  - `pattern`, `reduction`, `weight_shape`, `bias_shape` and
    `einsum_pattern` are a str, None or a client callable, so `track`
    returns them unchanged.
  - `_multirecipe` (dict) becomes a `TrackedDict`. It is only subscripted
    (`layers/__init__.py:45`, `:95`), an implicit outside call, so no edge.
  - `_axes_lengths` (a tuple of pairs) is rebuilt as a plain tuple
    (`tracking.py:89-93`). It is iterated and hashed only as the
    `axes_lengths` of `_apply_recipe`.
  - `_params` (list) becomes a `TrackedList`, and its inner shape lists
    become `TrackedList`s too (`tracking.py:137-142`). It is only unpacked
    (`layers/tensorflow.py:69`), and the shapes go to Keras's `add_weight`,
    so no package method call is made on them.
  - `pre_rearrange` and `post_rearrange` hold a layer or None. `weight` and
    `bias` hold Keras variables.
  - The values of `initialize_einmix` (`axes_lengths`,
    `pre_reshape_lengths`) are locals and stay plain dicts, so `98:87`
    keeps `<builtin>.dict.items` for the tf `EinMix`.

  So the five `TrackedDict.items` sites are the only sites that tracking
  changes. No list, tuple or set needs another name.
- **Verdict:** the current ledger is right on this point. No edge change.

## Step 1: blind re-derivation

Skeleton from a scratch benchmark without the ledger:
1520 sites (771 call, 23 decorator, 726 implicit), 27 value sites.
Sites numbered in (module order of the skeleton, line, column); the sample
is `sorted(random.Random(20261123).sample(range(1520), 140))`, the doubled
sample that the lead asked for (the trace ran the numpy backend only). No
kind dominates (explicit sites are 52%), so the draw is plain: 82 explicit
and 58 implicit sites. Three value sites fell in the sample
(`_backends.py:255:42`, `einops.py:269:36`, `:289:2`), so 164 distinct
sites were re-derived: 140 drawn and the 24 other value sites. The answers
were written before I opened any of the writer's files
(`$TMPDIR/b7-audit-einops/blind-answers.md`, with `draw.py` and
`sample.json`).

| Class of disagreement | Sites | Detail |
|---|---|---|
| writer missed an edge | 0 | |
| writer edge that cannot happen | 0 | |
| naming only (auditor error) | 5 | `_backends.py:181:29`, `array_api.py:67:43`, `:113:23`, `einops.py:285:28`, `:273:49`: I wrote `numpy.stack`, `numpy.reshape`, `numpy.min` ...; in numpy 2.4.1 these are `_ArrayFunctionDispatcher` objects (`numpy/_core/overrides.py:164`; type name `numpy._ArrayFunctionDispatcher`, `_core/src/multiarray/arrayfunction_override.c:760`), so by "Outside names" (a callable wrapper object uses its class's `__call__`) and J3 the writer's `numpy._ArrayFunctionDispatcher.__call__` is right |
| auditor wrong (judgement) | 1 | `einops.py:259:115` (O4) |
| incomplete auditor answer | 1 | `_backends.py:102:37`: I listed the seven `numpy.ndarray` methods and left the other tensor classes as "naming"; the writer's 28 further names (`jax.numpy.ndarray`, `cupy.ndarray`, `pytensor.tensor.TensorVariable`, `mlx.core.array`) follow J1 |

Every package edge of the sample agrees, including the cases that need the
framework sources: the flax wrapper at `_einmix.py:162:32`, the Keras
`TrackedDict.items` at `layers/__init__.py:75:59` and `_einmix.py:205:52`,
the five framework `__call__` value sites (10 sites), and the lru_cache
call-backs of `UnknownSize.__hash__` and `__eq__` at `einops.py:235:119`.

## Step 2: exhaustive checks

**Layers through their framework base (J5).** I checked each edge against
the framework source:

- torch: `Module.__call__ = _wrapped_call_impl` (`torch/nn/modules/module.py:1915`),
  `_wrapped_call_impl` -> `_call_impl` (`:1772-1776`), `forward_call` is
  `self.forward` or `_slow_forward` (`:1781`, `:1787`, `:1830`). The name
  `torch.nn.Module.__call__` follows "Inherited methods" (the base that the
  package names) and "Outside names".
- keras 3.13.1: `Layer.__call__` (`layer.py:828-829`, under
  `filter_traceback`) -> `_maybe_build` (`:1474-1490`), which calls the
  `build_wrapper` that `Layer.__new__` installs (`:222-241`); a one-argument
  `build(self, input_shape)` gets the first shape whatever its name
  (`update_shapes_dict_for_target_fn`, `:1966-1969`). Then
  `super().__call__` (`:951`, `:953`) -> `Operation.__call__` -> `call`.
  `Layer.__new__`, `Operation.__new__` (`ops/operation.py:114-200`) and
  `Layer.__init__` call no package method. With the torch Keras backend,
  `TorchLayer._setattr_hook` (`backend/torch/layer.py:43-55`) wraps only a
  non-Keras `torch.nn.Module`; it does not touch a dict.
- paddle: `Layer.__call__` (`layers.py:1824-1835`) calls `forward` directly
  or through `_dygraph_call_func` (`:1737-1775`); `_build_once` is not
  overridden.
- oneflow: `Module.__call__` (`module.py:150-169`) calls `forward`; its
  lazy-mode warning calls `_shallow_repr` (`:1360-1373`), which uses
  `extra_repr` and `_get_name` and not the package's `__repr__`.
- flax: `__init_subclass__` (`linen/module.py:1034-1046`) wraps every
  method in the class's own `__dict__` (`:1135-1153`, `:629-649`), so the
  wrapper `wrap_method_once.wrapped_module_method` (`:693-700`) is a callee
  wherever package code calls `Rearrange.__call__`, `EinMix._create_parameters`
  or `EinMix._create_rearrange_layers` on a flax receiver: the four value
  sites and `_einmix.py:108`, `:162`, all in the ledger. These are all the
  package call sites of wrapped methods. `initialize_einmix` is inherited
  from the non-Module mixin and stays unwrapped (`layers/flax.py:44`, plain
  callee, right). `_call_wrapped_method` runs `_try_setup` first
  (`:1194`, `:1478-1495`), so `Rearrange.setup` at `layers/flax.py:76`, `:81`
  is right. The flax `Rearrange(...)` calls (`:68`, `:72`) run the
  generated dataclass `__init__` and flax's `__post_init__`: no package edge.
  The name follows "Functions without an attribute path" and the itables
  precedent.
- The `super().__init__()` callees of the three mixins (`<builtin>.object.__init__`
  for the plain mixins that flax makes; the framework bases otherwise) are
  right. The torch, keras, paddle and oneflow bases have no metaclass and
  no `__init_subclass__` (searched in their extracts); flax's
  `__init_subclass__` makes the dataclass and wraps the methods, and calls
  no package code (`_find_compact_name_scope_methods` only reads
  attributes, `wrap_method_once` only tests `hasattr`).

**Default rejections** (`--report einops --default ...`, all ten). I traced
where the package makes `HashableTuple` and `UnknownSize` objects
(`_backends.py:375`, `:386`, `:446`) and every place they flow: the
backend shape sites of `reduce`, `_reconstruct_from_shape_uncached`,
`_apply_recipe`, `parse_shape`, `_enumerate_directions`, `pack` and
`unpack`, and the axes lengths of J6. The accepting sites are exactly the
ones I find: 17 site-candidate pairs for the `HashableTuple` methods (plus
its two constructor calls) and 10 for the `UnknownSize` methods. I read every
explicit site that each default decides; none takes a backend shape or an
`UnknownSize`. Points that I checked one by one: `hash(shape)`
(`_backends.py:382`) holds ints and tf tensors only; `prod` (`packing.py:93`)
never gets an `UnknownSize`, because `-1 in p_shape` is true for such a
shape (CPython compares the element first, `UnknownSize.__eq__` answers
True); `length % known_product` (`einops.py:187`) and `!=` at `:183` are
guarded by `isinstance(..., int)`. For the five `__repr__` defaults, the
accepted sites (`einops.py:317`, `:327`, `_einmix.py:12`,
`layers/__init__.py:39`, `:89`) are the only places where an
`AnonymousAxis` or a layer is formatted: `:313` raises first (`:309-310`),
`:323` filters out anonymous axes, `:406` holds only names of unknown
length, and `_einmix.py:117` comes after the check of `:83`. No package
code formats a backend or an `EinMix`.

**lru_cache call-backs.** `einops.py:235`: three positional arguments, so
the C `lru_cache` key is the argument tuple; its hash runs
`UnknownSize.__hash__` for an eager tensorflow shape or a `parse_shape`
axis length, and every `UnknownSize` hashes as `hash(None)`, so a second
call with the same recipe meets a stored key of the same hash and the
tuple comparison runs `UnknownSize.__eq__`. Both edges are right. The other
three cached functions take strings, ints, names and the client's
reduction: no package `__hash__` or `__eq__`.

**Dispatch sets.** `BackendSubclass()` (`_backends.py:56`): the eleven
backends, each with its own `__init__`. The receivers of every backend
method call match the overrides: `shape` (Abstract for numpy, jax, torch,
cupy, oneflow, mlx), `reshape`, `transpose`, `reduce`, `add_axes`,
`add_axis`, `tile`, `stack_on_zeroth_dimension`, `concat`, `arange`,
`to_numpy`, `einsum`, `is_float_type`, `is_appropriate_type`.
`getattr(x, operation)(...)`: seven reductions per class at
`_backends.py:102` (numpy, jax, cupy, pytensor, mlx; paddle has no class,
J2), `any`/`all`/`prod` for torch (`:255`), five for oneflow (`:509`), seven
for tinygrad (`:648`), tensorflow (`:389`) and keras (`:449`). The
reduction is always one of `_reductions` (`einops.py:324-329`; with
`rearrange` and `repeat` the recipe has no reduced axis).

**Binding check.** I checked every call of a package function against its
signature. The only failure is the writer's: `MLXBackend.add_axes(self, x,
new_position)` cannot bind `einops.py:249`. Keras's `build(**shapes_dict)`
binds the one-argument `build` (above).

**Functions that no site calls** (from `einops.json`): each is public, a
framework entry point (`forward`, `call`, `build`, `get_config`, `setup`,
flax `__call__`), a pickle hook, an override that no receiver reaches
(`TorchBackend.tile`, `OneFlowBackend.tile`, `PaddleBackend.tile`,
`MLXBackend.tile`, `AbstractBackend.add_axis`, the torch layers'
`_apply_recipe`), only tested (`_optimize_transformation`, `from_numpy`,
`create_symbol`, `eval_symbol`, `layers`, `_EinmixDebugger`), or called
by nothing, the tests included (`ParsedExpression.flat_axes_order`). None
should have a caller.

**Rejected trace edges.** The three `_EinmixDebugger` edges: rule A, a
direct test invocation of a private API whose receiver B1 excludes. Right.

**Outside callees.** I read every entry of `_backends`, `_torch_specific`,
`array_api`, `einops`, `layers`, `_einmix`, the framework layer modules,
`packing` and `parsing`. The names follow the rules (missing modules by
access path; `<builtin>.RuntimeError.__init__` for `EinopsError`;
`<builtin>.type.__subclasses__`; `collections.OrderedDict.values`;
`functools._lru_cache_wrapper.__call__` and
`functools.lru_cache.decorating_function`).

## The writer's judgement calls

| Call | Nearest rule | Opinion |
|---|---|---|
| J1 tensor classes | B4 (a class checked with `isinstance`) | Supported; see O2 for the open naming part. |
| J2 paddle and keras tensors have no class | B4 (no class named), B5 | Supported. |
| J3 numpy names from the pin | the lead's ruling | Applied correctly; the dispatcher type name and the C functions checked in the 2.4.1 source. |
| J4 array_api admits numpy only | B4 (documentation), B2 (tests) | Supported: the README names "numpy >= 2.0" and the tests pass numpy arrays; the other libraries name no class. |
| J5 framework call paths | base-class exception | Verified line by line (above). |
| J6 parse_shape output as axes_lengths | B2 factory outputs, documented example `einops.py:687-690` | Supported. The `EinMix` exclusion changes no edge (its axis lengths reach only `_product`, the parameter shapes and the `Rearrange` layers, which J6 covers). The `array_api` exclusion follows its `int` annotation (O4). |
| J7, J8 `_EinmixDebugger` | B1, A | Supported. |
| J9 `allow_ops_in_compiled_graph` | missing-library branches; dependency versions | Supported on both grounds: einops declares no torch bound, so torch 2.0 to 2.7 take the `allow_in_graph` branch. |
| J10 `tuple \| list` | "Edges": any supported version | Supported. |
| J11 lru_cache wrappers | micro-benchmark "Calls of instances", "Functions without an attribute path" | Supported. |
| J12 `EinopsError` | micro-benchmark "Instantiation" | Supported. |
| J13 `keyword.iskeyword` | "Functions of a module": the path that the package imports | Supported. |
| `_debug_importing` prints | B2: a client's assignment counts only where docs or tests make it (the tests do not set it) | Supported. |
| Keras tracking (open point) | "A method of an outside object is named by the class of the receiver" | Supported; O1. |

## For the lead

No ruling is needed for an edge. Two naming points stay with the lead if
it wants them settled: J1's cross-statement naming (O2), and the
TensorFlow `AutoTrackable` file that O1 names. The README and the tools
were clear for this package; the skeleton, the report and `--default`
worked as documented.
