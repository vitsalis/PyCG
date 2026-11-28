# N5a. jsonpickle: nested view bases and the `.get` path of a decoded dict

Adopted by the lead in place of a referee, maintainer's instruction of
2026-11-28. Raised by the audit of the corrections of 2026-11-28
(`../audits/corrections-2026-11-28.audit.md`, N5a). Read at `8e1db387`.
Paths are relative to `evaluation/macro-benchmark/`; a package's files are
cited from its root under `projects/<name>/`, its ground truth is under
`ground-truth/`, and numpy's files are cited from the root of its sdist.

**1. The question.** `NumpyNDArrayHandlerView.restore`
(`jsonpickle/ext/numpy.py:325-351`) reads `data.get('base')` (327:24) and
forwards that dict through `self.context.restore(base, reset=False)`
(333:40) to the restore of the base array, which is again
`NumpyNDArrayHandlerView.restore` (the handler that `register_handlers`
installs for `np.ndarray` with `base=True`, `ext/numpy.py:370`). With the
ujson or the yaml backend the top-level decoded dict is a missing-module
result, so every `data.get(...)` keeps an access path, one `.get` longer
per forwarding. Write `X` for `ujson.loads` or `yaml.safe_load` and `Gk`
for `X` followed by `k` copies of `.get`; the dict at nesting depth `d`
(0 is the top-level array) is `Gd`, and a `data.get(...)` on it is
`G(d+1)`.

| Sites | Caller | Callees at `8e1db387` (`jsonpickle.ledger`) |
|---|---|---|
| 96:24 | `NumpyNDArrayHandler.restore_flags` | `G1`, `G2` (`:377-383`) |
| 112:67, 114:25 | `NumpyNDArrayHandler.restore` | `G1`, `G2` (`:432-444`) |
| 151:29 | `NumpyNDArrayHandlerBinary.restore_byteorder` | `G1`, `G2` (`:456-462`) |
| 216:67, 217:33, 224:35, 225:35 | `NumpyNDArrayHandlerBinary.restore` | `G1`, `G2` (`:579-610`) |
| 327:24 | `NumpyNDArrayHandlerView.restore` | `G1`, `G2` (`:694-700`) |
| 343:69, 344:31, 345:32, 346:33 | `NumpyNDArrayHandlerView.restore` | `G1` only (`:741-760`) |

The ledger's notes rest on one claim: "the base of a view is an array that
owns its data, so its dict has no base and the else branch, lines 343-346,
does not run for it" (327:24); `jsonpickle.md`, "Corrections of
2026-11-25", says the same, and `q5.md` §4 calls the flow "one forwarding,
no loop: a finite path". The audit pointed out that
`NumpyNDArrayHandlerView.flatten` writes a base inside a base whenever
`obj.base.base` is a contiguous ndarray (`ext/numpy.py:281-283` runs the
same handler on the base), and that numpy stops collapsing a base at a
change of subclass. Can an admitted numpy give a view whose base does not
own its data, to unbounded depth; and if so, does the open path rule
apply, with which members?

**2. The ruling.** **Apply the fabric ruling: numpy keeps a view's base
unchanged across a change of subclass on every admitted release read
(1.17.3, 2.5.4), so `NumpyNDArrayHandlerView` writes and restores bases
nested without a bound in the source, and the `.get` path of the decoded
dict through `data.get('base')` and `self.context.restore` (327, 333) is
an open path set.** The ground truth records `G1`, `G2` and `G3` at each
site that runs at depth 0, 1 and 2, and declares the sites under "Open
path sets" in `jsonpickle.md`. This covers only the view handler's
recursion; it does not admit hand-written JSON that the package never
writes, and adds nothing at subscripts (`data['values']`,
`data['dtype']`).

Effect, jsonpickle only, each for `X` = `ujson.loads` and `X` =
`yaml.safe_load`:

| Site | Caller | Added |
|---|---|---|
| 343:69, 344:31, 345:32, 346:33 | `NumpyNDArrayHandlerView.restore` | `X.get.get`, `X.get.get.get` |
| 327:24 | `NumpyNDArrayHandlerView.restore` | `X.get.get.get` |
| 96:24 | `NumpyNDArrayHandler.restore_flags` | `X.get.get.get` |
| 112:67, 114:25 | `NumpyNDArrayHandler.restore` | `X.get.get.get` |
| 151:29 | `NumpyNDArrayHandlerBinary.restore_byteorder` | `X.get.get.get` |
| 216:67, 217:33, 224:35, 225:35 | `NumpyNDArrayHandlerBinary.restore` | `X.get.get.get` |

- 34 site-callee entries (16 at 343-346, 18 at the nine other sites);
  callee lines 1626 to 1660.
- 10 graph edges added (`-> ujson.loads.get.get.get` and
  `-> yaml.safe_load.get.get.get` for the five callers); the `X.get.get`
  at 343-346 are already edges of `NumpyNDArrayHandlerView.restore`
  through 327:24. 1310 to 1320 edges: 383 inside, 937 outside. None
  removed, no inside edge, no trace edge changes.
- The ledger notes at 327:24 and 343-346 and the shared note of the other
  sites point to "Open path sets"; `jsonpickle.md` declares the sets, and
  its Corrections of 2026-11-25 and `q5.md` §4 carry a correction note.
- `benchmark-rules.md`: one bullet in "Rulings for the corrections of
  2026-11-28". jsonpickle already declares open receiver sets, so the
  outside score without the open-set packages already leaves it out.

**3. What the rules say.**

- "Rulings for the corrections of 2026-11-25", fabric
  (`../../corrections-2026-11-25/rulings/ruling-fabric-1.md`): "Recursive
  forwarding that extends a path again and again without a finite bound
  in the source is an open path set, as an unbounded loop reassignment
  is: the ground truth records one and two repetitions of the repeated
  path segment beyond the originating path as lower-bound witnesses, not
  a count of recursive calls, and longer verified members stay valid
  additions. This does not cover recursion that the source bounds,
  inadmissible inputs, paths lost through a subscript, unpacking or
  arithmetic of a missing-library value, or calls that an earlier failure
  prevents."
- Batch 7, "Open path sets (the lead's decision; einops)": a package with
  such sites records the members with one and two repetitions, declares
  each site in its `<name>.md` under "Open path sets" (the site, the
  family, why it is open), and states the graph at those sites as a lower
  bound.
- Batch 7, "A stub result keeps its path through assignment (einops)":
  the result keeps its access path through "forwarding through package
  functions"; the ledger already applied this to the one forwarding at
  333:40 (`G2`).
- Batch 7, "Which releases of a dependency are admitted"; batch 8, "Which
  releases of a dependency are read": jsonpickle's `testing` extra
  declares `numpy` bare (`pyproject.toml:54`) and jsonpickle admits
  CPython 3.8 and later, so every numpy release that runs on CPython 3.8
  or later up to the environment pin (numpy 2.5.4,
  `test-environments/jsonpickle.txt:59`) is admitted.
- Scope rules B2 and B5 for jsonpickle (`jsonpickle.md`, "Scope rules"):
  `encode` accepts any object, a registered handler fixes the class, and
  the ndarray handler covers every ndarray subclass (`base=True`).

The rules decide the question once the numpy fact is known: if numpy can
chain bases without bound, the fabric ruling makes the base path an open
path set, and the ownership claim of the ledger and the "finite path" of
`q5.md` are factual errors, not rulings.

**4. The evidence.**

- jsonpickle (`jsonpickle/ext/numpy.py`, read at the pinned commit): the
  sites are as the table of §1 says. `flatten` stores a view by reference
  when `isinstance(base, np.ndarray) and base.flags.forc` (279) with
  `data['base'] = self.context.flatten(base, reset=False)` (281-283), and
  `restore` takes `data.get('base', None)` (327) and, when it is set,
  `self.context.restore(base, reset=False)` (333), else the by-value
  restore of `NumpyNDArrayHandlerBinary` (330), which reaches 112, 114,
  151 and 216-225; `restore_flags` (96) runs from all three restores
  (118, 228, 349).
- numpy, fetched as sdists inside a `python:3.14-slim` container, each
  checked against the SHA-256 that PyPI lists, and read as text: 2.5.4
  (the pin; `9a94cf75...`) and 1.17.3 (the first release with CPython 3.8
  wheels; `a0678793...`). `PyArray_SetBaseObject`
  (`numpy/_core/src/multiarray/arrayobject.c:154` of 2.5.4,
  `numpy/core/src/multiarray/arrayobject.c:164` of 1.17.3) is where a
  view's base is set (`PyArray_NewFromDescr_int` calls it, `ctors.c:884-889`
  of 2.5.4, and `PyArray_View`, `convert.c:668-691`, uses that for
  `ndarray.view`). It walks the chain only while three conditions hold,
  identically in both releases:

  | Condition to keep collapsing | 2.5.4 | 1.17.3 |
  |---|---|---|
  | loop: `while (PyArray_Check(obj) && arr != obj)` | `:181` | `:191` |
  | stop if `obj` owns its data (`NPY_ARRAY_OWNDATA`) | `:191` | `:201` |
  | stop at a different subclass: `if (Py_TYPE(tmp) != Py_TYPE(arr)) break;` | `:203` | `:213` |
  | base set: `((PyArrayObject_fields *)arr)->base = obj;` | `:221` | `:231` |

  The independent audit of this application
  (`../audits/corrections-2026-11-28-r2.audit.md`, J1) read the last
  release of every minor series from 1.16 to 2.4 as well (1.16.6, 1.17.5,
  1.18.5, 1.19.5, 1.20.3, 1.21.6, 1.22.4, 1.23.5, 1.24.4, 1.25.2, 1.26.4,
  2.0.2, 2.1.3, 2.2.6, 2.3.5, 2.4.6), each sdist checked against PyPI's
  SHA-256, as batch 8's "Which releases of a dependency are read" asks:
  with 1.17.3 and 2.5.4, all 18 releases have the same body of
  `PyArray_SetBaseObject`, byte for byte once whitespace is removed (the
  subclass stop at `:213` of 1.16.6 to 1.18.5, `:214` of 1.19.5, `:216`
  of 1.20.3, `:217` of 1.21.6 and 1.22.4, `:200` of 1.23.5 and 1.24.4,
  `:204` of 1.25.2 and 1.26.4, `:205` of 2.0.2, `:203` of 2.1.3 to
  2.5.4).

  So a view `a_k = a_{k-1}.view(t_k)` of a view that does not own its
  data keeps `a_k.base is a_{k-1}` whenever `type(a_{k-1}.base) !=
  type(a_k)`. numpy's own test relies on it: "Create subclass so base will
  not be collapsed" (`numpy/_core/tests/test_multiarray.py:133-135` of
  2.5.4). The type sequence `matrix, ndarray, ndarray, matrix, matrix,
  ndarray, ndarray, ...` meets the condition at every step, so the chain
  grows by one level per view; every member is a whole-array view, so
  `flags.forc` holds at every level and `flatten` takes the by-reference
  branch at every level. `numpy.matrix` is numpy's own class
  (`numpy/matrixlib/defmatrix.py:74` of 2.5.4); a client subclass of
  `ndarray`, as in numpy's test, gives the same chain.
- A run, in a container from the trace image
  (`python@sha256:9aaa4740...`, no write to the checkout), of numpy 2.5.4
  installed from the hashes of `test-environments/jsonpickle.txt` and
  jsonpickle from the read-only checkout, json backend, repeated for this
  record on 2026-11-28 with the same result: views 1 to 7 over an owning
  `matrix` give a `base` depth of 1 to 7 in what `encode` writes; decoding
  the 7-view document calls `NumpyNDArrayHandlerView.restore` 8 times, 7
  of them with a `base` key, and the round trip gives the same values;
  `np.arange(4.0).view(Sub)[...]` keeps a `Sub` base whose base is an
  `ndarray`, as numpy's test says. With `sys.settrace` on `ext/numpy.py`
  and the dict at each depth marked (text, binary and object-dtype
  owners), the depths at which each site ran:

  | Views | 96, 327 | 343, 344, 345, 346 | 112, 114, 151, 216, 217, 224, 225 (by value) |
  |---|---|---|---|
  | 2 | 0, 1, 2 | 0, 1 | 2 |
  | 3 | 0, 1, 2, 3 | 0, 1, 2 | 3 |

  So every listed site runs at depth 2 (`G3`) with three views or fewer,
  and the view branch at depth 1 (`G2`) with two.
- No other package flow reaches these handlers with a retained path: the
  unpickler forwards the top-level object or the `data.get('base')`
  result only (`unpickler.py` has no other `.get(` that forwards decoded
  data: 201, 206, 884, 891), and pandas' `meta` returns inside a tuple
  that its callers unpack (`jsonpickle.md`, Corrections of 2026-11-25).
  The trace does not bear on it: ujson and PyYAML are not installed.

**5. Against.** The depth is bounded in practice by Python's recursion
limit (a few frames per level in `Unpickler.restore`, `_restore`,
`_restore_object` and the handler), and nobody pickles a chain of
alternating `matrix` views. But the ruling asks for a bound "in the
source", and neither jsonpickle nor numpy has one; fabric's gateway chain
has the same runtime limit. A second argument: `numpy.matrix` is pending
deprecation. It exists in every admitted release read, and a client
`ndarray` subclass, as in numpy's own test, gives the same chain.
