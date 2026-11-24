# face_classification: judgements of the ground truth

Commit `2f152a2` (2019-05-22). Analysed source: what `projects.toml` names
under the root `src`: `utils/`, `models/`, `web/` and the seven scripts. 19
modules, 65 functions (1 lambda), 2 classes. The project is Python 3 only
(README: `python3`), and the analysed source has no branch on the Python
version.

The ledger is `face_classification.ledger`; the graph
`face_classification.json` is generated from it. There is no trace: the
project has no tests, and its pinned dependencies (keras 2.0.5, tensorflow
1.1.0) do not install on a current Python. Every edge comes from reading.
There is no `face_classification.rejected.json`. The independent audit is in
`face_classification.audit.md`; its two findings are applied (F1: judgement
8; N1: the name at `utils/grad_cam.py:42:10`), and the lead's rulings are
recorded at judgements 1, 2, 8 and 13.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in face_classification-review.json (audit record `2026-11-15/face_classification-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 485 | 71 | 49 | 463 |

- Apply the global unavailable-library rule: ordinary operations use
  imported access paths, including attribute and call chains. Do not infer
  ndarray, model, axes, backend-function or uploaded-stream classes.
- Drop seven callbacks through ordinary unavailable-library dispatch
  (Flask views, TensorFlow gradients and Keras Lambda callbacks). Reading
  decorator definitions does not make ordinary dispatch transparent.
- Read the pinned decorator definitions for the narrow definition-time
  exception. Unpinned Flask admits the 1.x, 2.x and 3.x closure names.
- Include `bytes.lower` and `bytes.endswith` for byte paths produced by
  `os.walk` in `DataManager._load_KDEF`.

## Architecture, as the ledger uses it

- The seven scripts are module code only. They load keras models from
  `.hdf5` files, read images or the camera, and call the helpers of
  `utils/`. `train_*` build a model with `models.cnn.mini_XCEPTION` and
  train it.
- `utils.inference`, `utils.preprocessor` and `utils.datasets` are thin
  wrappers around cv2, numpy, pandas, scipy and keras.
- `utils.data_augmentation.ImageGenerator` keeps a list `color_jitter` of
  its own bound methods (`saturation`, `brightness`, `contrast`) and calls
  them in `transform`. Its generator method `flow` feeds `fit_generator` in
  `train_gender_classifier`.
- `utils.grad_cam` builds two keras backend functions (`K.function`): a
  gradient function and a saliency function. It registers a TensorFlow
  gradient function `_GuidedBackProp` and reloads a model under
  `gradient_override_map({'Relu': 'GuidedBackProp'})`.
- `models.cnn` builds keras models: `Sequential` with `add` (`simple_CNN`,
  `simpler_CNN`), or the functional API, where each layer instance is
  called on a tensor (`Conv2D(...)(x)`).
- `web/faces.py` is a Flask application. It runs as a script from
  `src/web/` and imports `emotion_gender_processor` as a top-level module;
  that module is `web.emotion_gender_processor` (ruling 3 of the README).

Apart from their explicit constructors, package classes define no special
methods, properties or metaclasses. So
every site that needs an entry is explicit (907 calls, 5 decorators), and
there is no default rejection.

## Naming of callees outside the package

The global missing-library rule applies. Ordinary unavailable-library
calls use imported access paths such as `keras.models.load_model.predict`,
`numpy.squeeze.astype`, `matplotlib.pyplot.gca.imshow` and
`keras.backend.function`. Attribute and call chains preserve a stub path;
subscription, unpacking and arithmetic do not reveal a new concrete class.
Calling a stub result keeps its path, so `Conv2D(...)(x)` has the same
callee as the constructor call. No model-file name supplies a class.

The definition-time exception permits reading the exact source of a
library decorator applied to a package definition. Flask's decorators
return source-defined registration closures; TensorFlow's registration
preserves the original function. The exception adds no transparency to
ordinary calls such as `app.run`, `K.gradients` or `Sequential.add`.

The requirement pins and the Dockerfile's unpinned installations both
contribute admitted configurations. Unpinned Flask gives the 1.x
`flask.app.Flask`, 2.x `flask.scaffold.Scaffold` and 3.x
`flask.sansio.scaffold.Scaffold` registration-closure names. The audit
records the pinned definition sources and hashes.

## Scope rules

**A. Edges are per function.** Every function keeps the edges of its body.
Nineteen functions have no caller (see the list below); they keep their
edges.

**B1. Receivers.** `self` is a `DataManager` or an `ImageGenerator`. Neither
class has a subclass, so every `self.m(...)` has one callee.

**B2. Arguments.** Most functions are public (rule C) and their parameters
are client objects, or the values that the package's own code passes. Where
the package passes an unavailable-library result, the method call keeps
the imported stub access path:
- `detection_model.detectMultiScale` (`utils/inference.py:15`): the
  package passes the `cv2.CascadeClassifier` of `load_detection_model`.
- `x.astype` in `preprocess_input` (`utils/preprocessor.py:6`): package
  callers pass results with the paths `cv2.resize`, `numpy.asarray` and
  `numpy.expand_dims`. The calls extend those paths with `.astype`; no
  concrete array class is inferred.
- `ground_truth_data.keys()` (`utils/datasets.py:130`): the package passes
  the dict of `DataManager._load_imdb`.
- `model.get_layer` (`utils/grad_cam.py:52`): the package passes the
  `load_model` result, so the call keeps its `.get_layer` path (judgement 4).
  At line 115, `model.layers[0].get_layer` instead has an opaque receiver
  after the unavailable-library subscription and has no named callee.
- `data.min()`, `data.max()`, `axis.imshow` in `pretty_imshow`
  (`utils/visualizer.py:57-63`): the package caller that runs is
  `display_image`, which passes the result paths of `np.squeeze` and `plt.gca()`.
- `gradient_function(...)`, `saliency_function(...)` (`utils/grad_cam.py`):
  judgement 8.

**B5. Client objects are opaque.** These five sites illustrate opaque
client arguments; the Statistics section counts all unnamed sites:
- `saliency_function(...)` in `calculate_guided_gradient_CAM_v2`
  (`utils/grad_cam.py:162`): no package code calls `_v2` (judgement 8).
- `self.ground_truth_transformer.assign_boxes(...)`
  (`utils/data_augmentation.py:207`): the package passes `None`
  (`train_gender_classifier.py:39`), so only a client transformer reaches
  the call.
- `data.min()`, `data.max()`, `axis.imshow(...)` in `normal_imshow`
  (`utils/visualizer.py:73-76`): no package code calls `normal_imshow`.

**C. Public.** Apply the README's public-path rule to module functions and
class methods; dunder methods remain public. Private helpers use actual
package callers, or the opaque fallback when they have no package caller.
Nested `_GuidedBackProp` and the lambda use their lexical captures, not
independent client entrypoints. No untyped client value is cast to a
package class.

## Judgement calls

1. **A call that cannot bind, and the code after it**
   (`utils/grad_cam.py:184-189`). The `__main__` block calls
   `modify_backprop(model, 'GuidedBackProp')`. The function takes three
   arguments (`model, name, task`), so the call raises `TypeError` before
   the callee starts: no edge (README, "Edges"). The block then always
   stops, so the sites at 185, 186 and 189 never run: no edge to
   `compile_saliency_function`, `calculate_guided_gradient_CAM` and
   `cv2.imwrite`. The README's global rule excludes both the call that
   cannot bind and code that only runs after that guaranteed failure.
   Changes 4 edges of `utils.grad_cam`. **Lead's ruling: kept.** A call
   that cannot bind its arguments has no edge, and the code that only runs
   after it has none.
2. **An import that always fails** (`utils/visualizer.py:131-177`). The
   `__main__` block starts with `from utils.utils import get_labels`. The
   checkout has no `utils/utils.py` (`get_labels` is in
   `utils/datasets.py`), so the import raises `ImportError` on every run,
   and the 25 call sites after it never run. The module `utils.visualizer`
   has no edge. This is not a missing third-party module (README,
   "Callees outside the package"): the module is the project's own and
   does not exist at this commit. If the import worked, the block would
   add 18 edges (`get_labels` of the missing module, `pretty_imshow`,
   `make_mosaic`, `pickle.load`, `open`, `load_model`, a layer's
   `get_weights`, `print`, `int`, and numpy and pyplot functions).
   **Lead's ruling: kept.** A module of the analysed root that is missing
   from the checkout is not a third-party stub: the import always fails.
3. **Branches on a constant** (`image_gradcam_demo.py:24, 30-33`;
   `video_gradcam_demo.py:21-27`). Both scripts set `task = 'emotion'` and
   then test it. The `'gender'` branch never runs, so `get_labels('imdb')`
   (31:24) and `get_class_to_arg('imdb')` (24:36) have no edge. Nearest
   rule: B1's ruling that a branch which the program's own state never
   takes adds no edge (argcomplete). It changes no edge of the graph: the
   same callees are called in the other branch.
4. **Loaded models.** The receiver of `predict` and `get_layer` comes
   from `keras.models.load_model`. These are
   `keras.models.load_model.predict` and `.get_layer`; the stored model
   file and its name do not establish an unavailable-library class.
5. **Gradient override context.** `tf.get_default_graph()` gives the
   access path `tensorflow.get_default_graph`; its method call is
   `tensorflow.get_default_graph.gradient_override_map`.
6. **Gradient registration and dispatch.** The pinned `RegisterGradient`
   definition registers and returns the package function without wrapping
   it. Its application uses the source-defined decorator method. The
   ordinary missing-library `keras.backend.gradients` stub does not expose
   dispatcher callbacks, so it has no edge to `_GuidedBackProp`.
7. **Keras Lambda callbacks.** Ordinary `Sequential.add` calls use the
   `keras.models.Sequential.add` access path. They do not reveal the
   library's invocation of the lambda or `target_category_loss_output_shape`.
8. **Keras backend functions.** Results of `K.function` retain
   `keras.backend.function` when called at `utils/grad_cam.py:123, 148`.
   The public `_v2` sibling has no package caller and its generic client
   callable remains opaque; it has no callee at line 162.
9. **matplotlib objects.** Keep the imported attribute or call-result
   path, such as `matplotlib.pyplot.cm.hsv` or `matplotlib.pyplot.gca.imshow`.
   Do not guess a concrete colormap or axes class. An unpacked result of
   `plt.subplots` does not retain an independently named stub path.
10. **Flask decorators.** The definition-time exception admits the
    registration closures read from Flask 1.x, 2.x and 3.x source. Route
    and errorhandler registration do not invoke the registered functions.
11. **Flask dispatch.** `app.run` is the ordinary `flask.Flask.run` stub.
    No view or error-handler callback is inferred through it.
12. **Uploaded files.** `request.files['image']` is a subscription result
    of an unavailable library. It supplies no independently named `read`
    method. `flask.abort` keeps the imported path.
13. **Missing-library control flow.** Stubs provide names, not executable
    specifications for unavailable libraries. Their implementation does
    not prove a later branch dead. Package-defined argument binding and
    missing package modules still decide judgements 1 and 2. The imported
    `Convolution2D` name remains `keras.layers.Convolution2D`.

14. **`statistics.mode`** (the video scripts). `REQUIREMENTS.txt` lists
    the PyPI `statistics` backport; on Python 3 the standard library
    module comes first on `sys.path`. Both are `statistics.mode`.

## Value sites

| Site | Callees | Count |
|---|---|---|
| `models/cnn.py`, `Layer(...)(x)` | `keras.layers.<Class>`: the called stub result keeps the constructor path (BatchNormalization 36, SeparableConv2D 20, Activation 20, Conv2D 19, MaxPooling2D 10, GlobalAveragePooling2D 3) | 108 sites |
| `utils/data_augmentation.py:156:33` `jitter(image_array)` | `ImageGenerator.saturation`, `.brightness`, `.contrast` (the list `color_jitter`, filled only in `__init__`) | 3 |
| `utils/grad_cam.py:42:10` `@ops.RegisterGradient(...)` | `tensorflow.RegisterGradient.__call__`, from the pinned definition; it registers and returns `_GuidedBackProp` without calling it | 1 |
| `utils/grad_cam.py:123:52, 148:33` | `keras.backend.function` (judgement 8) | 1 each |
| `utils/grad_cam.py:162:33` `saliency_function(...)` in `_v2` | none: a client callable, opaque by B5 (judgement 8, audit F1) | 0 |
| `web/faces.py:8:2, 12:2` `@app.route(...)` | `route.decorator` under Flask 1.x, 2.x and 3.x defining classes | 3 each |
| `web/faces.py:22:2, 26:2` `@app.errorhandler(...)` | `errorhandler.decorator` under Flask 1.x, 2.x and 3.x defining classes | 3 each |

The seven ordinary missing-library callbacks formerly assigned to
`utils/grad_cam.py:54:27`, `111:14` and `web/faces.py:31:12` are excluded
under the global stub rule. The existing exclusion at
`utils/grad_cam.py:116:38` remains.

Candidates rejected by name (20 lines): `load_image` of the other module
(the name binds by import or by definition), `ImageGenerator.flow` on the
keras `ImageDataGenerator` (`train_emotion_classifier.py:68`), the bound
methods that `list.append` only stores (`utils/data_augmentation.py:47, 50,
53`), the `Lambda` arguments at 111:21, and the unreachable sites of
judgements 1 to 3.

## Functions that no site calls

- No caller anywhere (19): `web.faces.index`, `upload`, `bad_request`,
  `not_found`; `utils.grad_cam.register_gradient._GuidedBackProp`,
  `compile_gradient_function.<lambda1>`,
  `target_category_loss_output_shape`; `models.cnn.simpler_CNN`, `tiny_XCEPTION`,
  `big_XCEPTION`; `ImageGenerator.do_random_rotation`;
  `utils.grad_cam.reset_optimizer_weights`,
  `calculate_guided_gradient_CAM_v2`; `utils.inference.get_colors`;
  `utils.visualizer.make_mosaic_v2`, `normal_imshow`, `display_image`,
  `draw_mosaic`; and `utils.visualizer.make_mosaic`, whose only callers
  are in the unreachable `__main__` block (judgement 2).
- The modules, as always.

## Statistics

| | Count |
|---|---|
| Sites | 912 (907 call, 5 decorator); 126 with candidates; 117 value sites |
| Ledger entries | 912 |
| Callee lines / rejection lines / exclusion lines / notes | 885 / 20 / 1 / 261 |
| Default rejections | 0 |
| Explicit sites without a callee | 50: unreachable or opaque under the global rules; each has a ledger note |
| Nodes | 84 (19 modules, 65 functions) |
| Edges | 463: 96 in the package, 367 to 191 callees outside |
| Trace | none |


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
