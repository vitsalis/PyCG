# face_classification: independent audit of the ground truth

Commit `2f152a227c528567924fa1c7587a2e6b8eb43309`, analysed source `src/`
(19 modules, root `src`). Audited files: `face_classification.ledger` (912
entries, 202 notes, 20 rejection lines, 1 exclusion), `face_classification.json`
(84 nodes, 486 edges: 103 in the package, 383 to 183 names outside) and
`face_classification.md` (14 judgements). There is no trace and no
`rejected.json`. `check.py --benchmark-dir macro-benchmark-2021
face_classification` reports no errors.

I read the 19 modules in full. I read nothing of the checkout outside `src/`
(its README, `REQUIREMENTS.txt` and `Dockerfile` included), no library source,
and no output of any analysis tool.

**Result.** The blind sample agrees with the ledger at all 138 sites. I found
no missed edge in the package and no package edge that cannot happen. One
finding removes 1 outside edge (F1, the writer's judgement 8). One finding is
naming only (N1). For the three judgement calls that the lead asked about, the
nearest rules support the writer's choices for judgements 1 and 2, and support
removing the edge of judgement 8. After F1 the graph has 485 edges (103 / 382).

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | minor: an edge that the rules do not support | `utils/grad_cam.py:162:33` `saliency_function([...])` in `calculate_guided_gradient_CAM_v2` -> `keras.backend.tensorflow_backend.Function.__call__` | No package code calls `_v2` (graph: no caller). Rule B: a function that the package never calls has its parameters judged as for a public one. B2: a package value fits a role only through an annotation, the documentation, or the package's own code, tests or documented examples that pass it *there*. Nothing passes a value to `_v2`. The shared name with `calculate_guided_gradient_CAM`'s parameter does not make one role: B2 needs the documentation to say so (asyncstdlib example). So `saliency_function` is a client callable, opaque by B5. The ledger already applies this reading to `normal_imshow` (`utils/visualizer.py` 73:24, 75:24, 76:24: no callee, "no package code calls normal_imshow"). Rule A still keeps the other 6 edges of `_v2`; `saliency.astype` (164:42) stays, because `np.squeeze` returns an ndarray. | -1 (outside) | likely; the writer asks for this ruling |
| N1 | minor: naming only | `utils/grad_cam.py:42:10` `@ops.RegisterGradient(...)` -> `tensorflow.python.framework.ops.RegisterGradient.__call__` | The writer's naming section says that a method is named through the documented public path of the receiver's class (`tensorflow.Graph`, `keras.models.Model`). TensorFlow documents this class as `tf.RegisterGradient`, so by that rule the name is `tensorflow.RegisterGradient.__call__`. The class call at 42:30 keeps the import path (`...ops.RegisterGradient`), as the writer does for other class calls. | 0 (1 renamed) | likely |

## The three judgement calls the lead asked about

| Judgement | Ruling that the nearest rule supports | Rule | Edges it changes |
|---|---|---|---|
| 1: code after a call that always raises `TypeError` (`utils/grad_cam.py:184-189`) | No edge at 184:35, and none at 185:50, 186:51, 189:16. `modify_backprop` takes `(model, name, task)`, and the `__main__` block passes two arguments. No `try` surrounds the call, and nothing rebinds the name, so every run raises at 184 and the rest of the block never runs. | README "Edges" (configargparse `p()`: a call that cannot bind has no edge), and "an edge exists if the code of A can call B when A runs". The version-branch rule is the closest analogue: code that cannot run has no edges. | 4 (`utils.grad_cam` -> `modify_backprop` by the existing rule; `compile_saliency_function`, `calculate_guided_gradient_CAM`, `cv2.imwrite` by the ruling). The writer already applies it. |
| 2: the block after an import that always fails (`utils/visualizer.py:131-177`) | No edges for the 25 sites after line 131. `src/utils/` has no `utils.py` and no `utils/` package (I listed the directory), so with root `src` the import `from utils.utils import get_labels` raises `ImportError` on every run. | README "Callees outside the package": the stub rule of the micro-benchmark applies only to "a third-party module that is not installed". This module belongs to the analysed root and is missing at the commit, so the stub rule does not apply. That leaves "Edges" (can call when A runs). Tool argument: under the stub reading, `utils.utils.get_labels` would be a name inside the package namespace that is not a node. | 18 (I counted the distinct callees of the block: the writer's 18 are right). The writer already applies it. `utils.visualizer` then has no edge, and `make_mosaic` has no caller. |
| 8: an edge from a function that the package never calls (`_v2`, 162:33) | Remove the callee (F1). | B (parameters of a function that is never called are judged as for a public one), B2 (role values), B5 (client objects are opaque) | -1 |

The other judgements are sound under the rules. Judgement 3 (branches on the
constant `task`) changes ledger lines only, not the graph: the same callees run
in the other branch. My nearest rule is "Edges" and the version-branch rule
rather than B1's argcomplete example, which concerns the state of instances of
a private class. The outcome is the same. Judgements 6, 7 and 11 are the three
callback edges that I wrote down before I opened the ledger (see Step 1).

## Step 1: blind re-derivation

Skeleton made without the ledger: a scratch benchmark directory with a copy of
`projects.toml` and a `projects` link, then `check.py --skeleton`. It has 912
sites (907 call, 5 decorator), all explicit, with 117 value sites and 795 plain
sites. Draw: `rng = random.Random(20261111)`, `rng.sample(plain, 100)`, then
`rng.sample(value, 30)` with the same generator, as the lead asked (29 of the
30 are keras layer calls). I added the 8 value sites outside `models.cnn` that
the draw missed, so that all 9 value sites that are not layer calls are in the
sample. I wrote the callees of all 138 sites before I opened any file of the
writer. I also wrote down three callback edges outside the sample.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Plain, drawn | 100 | 100 | 0 |
| Value, drawn (29 layer calls, `saliency_function` 148:33) | 30 | 30 | 0 |
| Value, added (`jitter`, `@ops.RegisterGradient`, `gradient_function`, `saliency_function` of `_v2`, 4 Flask decorators) | 8 | 8 | 0 |
| **Total** | **138** | **138** | **0** |

Disagreements by class: the writer missed an edge 0, the writer has an edge that
cannot happen 0, naming only 0, auditor wrong 0. Three of my readings were
conditional, and the writer made the same choice for each: (TE) no edge at and
after `grad_cam.py:184`; (MI) no edges after `visualizer.py:131`; (DB) no callee at
`video_gradcam_demo.py:24:36`. At 162:33 I wrote the same callee as the writer
(the shared role). F1 comes from the step-3 check of the rules, not from a
disagreement in the sample. The three callback edges that I listed blind are all
in the ledger: `compile_saliency_function -> register_gradient._GuidedBackProp`
(54:27), `compile_gradient_function -> <lambda1>` and
`-> target_category_loss_output_shape` (111:14), `web.faces -> index, upload,
bad_request, not_found` (31:12).

Plain sites, extra care (the writer drafted them with a script): besides the 100
drawn, I read all 544 entries outside `models.cnn` against the source. I checked
the 368 entries of `models.cnn` mechanically: every `X(...)` names
`keras.layers.X` (or `keras.models.X`, `keras.regularizers.l2`,
`keras.layers.add`); each of the 108 `X(...)(y)` names `keras.layers.X.__call__`
of the same class; the 65 `model.add` calls name `keras.models.Sequential.add`.
A second script compared every module-function site (`np.`, `cv2.`, `K.`, `tf.`,
`plt.`, `os.`, `pd.`, builtins) with its import path. It found no wrong name: its
6 hits were chained calls, where the site is the outer method.

## Step 2: exhaustive checks

- **Dispatch.** `self` is a `DataManager` or an `ImageGenerator`. Neither class
  has a subclass, a metaclass, a special method or a property (`rg` over
  `src/`), so every `self.m()` has one callee, and no implicit site has
  candidates. `jitter` (156:33): `color_jitter` is filled only at
  `data_augmentation.py:47, 50, 53`, with `saturation`, `brightness` and
  `contrast`. The roles `gradient_function` and `saliency_function` hold the
  package's `K.function` results (F1 for `_v2`), `detection_model` holds a
  `cv2.CascadeClassifier`, and `ground_truth_transformer` holds only `None` from
  the package (B5: no callee at 207:75).
- **Callbacks into the package.** The candidates are `sorted`, `shuffle`,
  `fit_generator` (keras callbacks only; the generator `flow` is a callee of
  66:41 and 70:57), `Lambda`, `RegisterGradient`, `K.gradients`, `app.run` and
  `ImageDataGenerator.flow` (no `preprocessing_function`). Only judgements 6, 7
  and 11 call package code back. The exclusion at 116:38 holds: the package
  passes `compile_gradient_function` only models loaded outside the override,
  and in `mini_XCEPTION` no Relu lies between `conv2d_7` and the output.
- **Default rejections:** none. **Rejections:** I checked all 20 lines and the
  exclusion. **Notes:** I read all of them outside `models.cnn`, and in
  `models.cnn` by sample.
- **Functions that no site calls:** the graph gives the 12 functions of
  `face_classification.md`. Rule A holds for each: their bodies keep their edges.
  The only edge among them that depends on parameter values is F1.
- **Counts:** 35 explicit sites without a callee (31 unreachable, 4 opaque),
  as the writer states. `--report` lists 3 sites with package callees beyond
  the candidates (judgements 6, 7, 11).

## Step 3: callees outside the package

**Consistency.** All 183 names follow one scheme. A module function or class is
named by the path that the module imports (`numpy.squeeze`,
`keras.layers.Convolution2D`, `keras.layers.core.Lambda`,
`scipy.ndimage.interpolation.affine_transform`). A method is named by the class
of the receiver (`numpy.ndarray.astype`, `keras.models.Sequential.add`,
`keras.layers.Conv2D.__call__`, `pandas.DataFrame.as_matrix`). A library closure
is named where it is defined. The one exception is N1.

**Names whose receiver class is a guess: 11 names, 22 edges** (21 after F1),
that is 5.7% of the 383 outside edges. In each case the code does not fix the
class: the class depends on a data file, an unpinned version or a
configuration.

| Names | Edges | Why the class is a guess |
|---|---|---|
| `keras.models.Sequential.predict`, `keras.models.Model.predict`, `keras.models.Model.get_layer` | 3 + 6 + 2 = 11 | `load_model` returns the class stored in an `.hdf5` file, which nobody read. The writer infers the class from the file name (judgement 4). |
| `matplotlib.axes.Subplot.axis`, `.imshow`, `.set_title` | 1 + 2 + 1 = 4 | matplotlib is unpinned: `AxesSubplot` before 3.7, `Axes` from 3.7 on (judgement 9) |
| `keras.backend.tensorflow_backend.Function.__call__` | 3 (2 after F1) | The keras backend is a user configuration. TensorFlow is the default and the pinned dependency. |
| `tempfile.SpooledTemporaryFile.read` | 1 | The werkzeug stream factory depends on the version: `BytesIO` or `TemporaryFile` before 0.15 (judgement 12) |
| `flask.app.Flask.route.decorator`, `flask.app.Flask.errorhandler.decorator`, `flask.abort` | 1 + 1 + 1 = 3 | Flask is unpinned. The closures move to `flask.scaffold.Scaffold` in Flask 2. Before werkzeug 0.15, `abort` is an `Aborter` instance (judgements 10, 12). |

Other outside names have a certain class but rest on library internals that
cannot be read here: `tensorflow.Graph.gradient_override_map` (a
`contextmanager` function, judgement 5), `flask.Flask.errorhandler` (wrapped by
`setupmethod`), `matplotlib.colors.LinearSegmentedColormap.__call__`, and the
`Convolution2D` alias. The largest risk is judgement 13. Every model load passes
`compile=False`, and the writer assumes that keras 2.0.5's `load_model` accepts
it. If it does not, each script stops at its first `load_model`. I cannot check
this without the keras source.

## README and tools

- The README does not decide judgements 1 and 2 by name. I propose one sentence
  in "Edges": code that cannot run because an earlier statement of its block
  always raises (a call that cannot bind, an import of a module that the
  analysed root lacks) has no edges. The missing-module rule could also say that
  a module of the analysed root is never a stub. Neither change alters the graph.
- For B2, the README could say that a parameter of a function that the package
  never calls gets package values only from an annotation or the documentation,
  and not from a parameter of the same name in another function (F1).
- The tools worked as documented. The skeleton made from a scratch benchmark
  directory needed no change.


## Round 3 independent source audit (2026-11-16)

This review proposes no graph, ledger or added-edge correction. The graph
retains 84 nodes and 463 edges: 96 inside the package and 367 outside.
This section records the review and does not supersede historical text.

The independent reviewer read all 19 analysed modules before opening this
project's ledger or graph. The model was frozen at
2026-11-16T13:27:38.794990+00:00. It is a prose semantic model with a complete
site/node inventory, not a separately enumerated exact graph. The parent
reviewer froze a separate source model before the reviewers exchanged findings.

The review covers all 463 graph pairs, 912 explicit entries, 1,004 omitted
implicit sites, 117 value sites, 12 zero-edge nodes and the sole exclusion.
There are no default rejections. All 114 accepted own site/callee relations
bind their arguments. The rejected two-argument call of modify_backprop at
grad_cam.py:184 still lacks task, and the later calls remain unreachable.
The absent utils.utils import still prevents visualizer's main block.

Source-created tuple/list containers preserve their members and their outside
access paths. Unpacking a missing-library result does not establish a path.
The uncalled normal_imshow and calculate_guided_gradient_CAM_v2 keep opaque
client parameter roles. KDEF's bytes filenames can enter bytes.lower and
bytes.endswith; the suffix error occurs inside the latter builtin.

Official pinned TensorFlow 1.1.0 and Flask 0.10.1, 0.12.5, 1.0, 2.0.0 and
3.1.2 source confirms the decorator names and identity returns. RegisterGradient
and Flask registration decorators do not make later ordinary missing-library
calls transparent. All 19 runtime files and the README, REQUIREMENTS.txt and
Dockerfile match the project's official pinned commit byte for byte.

The machine-readable review, source freeze, per-edge/site/body evidence,
primary-source URLs and SHA-256 hashes are in the round-3 artifacts:
face_classification-review.json and face_classification-agent/.
Structural generation, origin accounting, exact-literal replay and git-apply
replay pass. No target or dependency code was executed. No trace exists;
all 463 edges remain added edges. Only this review record is appended.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 independent source audit (2026-11-16)

A fresh source-first review retains all 463 pairs and 84 nodes (96 package,
367 outside). No false positive, missing pair or independent metadata defect
was found. All 19 modules were read before opening the baseline. The frozen
source model and identities precede comparison. The review covers 1,916
source sites: 912 explicit entries and 1,004 omitted implicit sites; 885
site/target relations; 84 bodies, including 12 empty bodies; all 50 explicit
no-callee sites; 21 named candidate rejections on 20 lines; and one exclusion.
There are no default rejections. All 114 own call/target relations bind their
arguments; 368 CNN call sites also match a separate static imported-name and
call-result resolution pass. These checks inspect source and do not run it.

The two unconditional cutoffs remain: modify_backprop lacks task in the
grad_cam main block, and visualizer's main block imports absent utils.utils.
Source-owned tuples preserve their elements' imported paths; unpacking a
missing-library result does not. ImageGenerator's three constructor-selected
jitters and optional crop/lighting/flip branches establish the retained
flow chains without arbitrary attribute mutation. Registration decorators
return the original functions and do not expose later Flask/TensorFlow/Keras
dispatch. Client-only normal_imshow and guided-CAM-v2 arguments stay opaque.
KDEF bytes filenames can enter bytes.endswith before its suffix error.

The pinned README/Dockerfile declare Python3, with no explicit alternative
implementation or upper bound. There are no assertion, __debug__ or __doc__
access sites, so the round's working normal/-O/-OO union adds no pair. The
mode assumption remains distinct from explicit user approval. This is a
static semantic audit, not a proof of completeness or a dependency-release
exhaustion claim. Parent structural/origin gates and final review follow.
