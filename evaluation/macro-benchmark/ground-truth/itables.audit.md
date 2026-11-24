# itables: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [itables.md](itables.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release v2.9.1, commit `13fc4f5706575ca08f3f3e7da435bea293e429ac`. Analysed
source: `src/itables/` and `src/itables_for_dash/` (lead's scope ruling 1).
Audited files, as the writer left them (not committed): `itables.ledger`
(1361 entries, 1352 callee lines, 58 rejection lines, 83 notes, 1 default
rejection), `itables.json` (776 edges: 188 in the package, 588 outside, to
227 outside callees), `itables.rejected.json` (2 edges), `itables.md`
(J1-J11). `check.py --benchmark-dir macro-benchmark-heldout-3 itables`
reports no errors; the trace confirms 565 of the 776 edges.

I read the source, `pyproject.toml`, `docs/other_dataframes.md` and one test
as data. I did not run or import the package, and I did not use any static
analysis tool or open `pycg/`, `evaluation/` or `docs/` of this repository.
Process deviation: at the start I ran two read-only commands (`git log -1`,
`fd -e py`) with the working directory inside `projects/itables`. The brief
forbids that. Nothing from the checkout ran.

**Result.** The ground truth is sound. The blind sample found no writer
error. Two findings ask the lead to rule on judgement calls that the writer
already flagged (F1: -4 edges; F2: -1 edge only if dash's code does not
confirm it). R1 asks to confirm a reading of B4 that the README does not
state. No other change.

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | low (ruling) | J1: `itables.streamlit`, `itables.widget`, `itables_for_dash`, `itables_for_dash.properties` -> `itables.typing._SubscriptableFallback.__getitem__` (`streamlit.py:26:21`, `widget/__init__.py:38:25`, `:55:25`, `itables_for_dash/__init__.py:39:25`, `properties.py:23:21`, `:57:21`) | The fallback exists only if `from typing_extensions import NotRequired, Unpack` fails (`typing.py:26-40`). Each of these modules first imports a framework: `streamlit.py:3-4`, `widget/__init__.py:5-6` (anywidget), `itables_for_dash/__init__.py:6` -> `ITable.py:4-5` (typing_extensions with `NotRequired`, and dash), `properties.py:3` (dash; reached only through `itables_for_dash/__init__.py`). From memory (none of these is installed here): dash requires `typing_extensions>=4.1.1`, streamlit `>=4.4.0`, anywidget `>=4.2.0`, and typing_extensions has `Unpack` since 4.1.0. So no installable environment both imports these modules and takes the fallback. The README rule "a version that the package admits" does not say if the constraints of other dependencies count. Proposed ruling: a dependency version counts only if it can be installed together with the libraries that the code imports before the branch. Then the 4 edges go. The 3 edges of `itables.typing`, `itables.javascript` and `itables.shiny` stay (no third-party import). The lead can check the three requirements in the PyPI metadata. | -4 (776 to 772; 188 to 184 in the package) | likely |
| F2 | low (ruling) | J4: `itables_for_dash/__init__.py:56:32` `super().__init__(...)` -> `dash.development.base_component._explicitize_args.wrapper` and -> `itables_for_dash.ITable.ITable.__init__` | dash is not installed and was not read. The README says such a library is a missing module ("cannot be read"), and a stub never calls its arguments. Under that rule the callee is `dash.development.base_component._explicitize_args` (the object that the stub returned at `ITable.py:76`, as at `streamlit.py:30:37`), with no callback. The writer's argument is real: `ITable.py:64` pops `_explicit_args`, which only dash's wrapper supplies. My memory of dash agrees with the writer (a local `wrapper(*args, **kwargs)` that adds `_explicit_args` and calls `func`). Proposed: read `dash/development/base_component.py` from the dash 4.4.0 archive (the version of the build hook, `pyproject.toml`), read only, as the 2021 set did for invoke and paramiko. Keep J4 if it confirms; otherwise apply the stub rule. | 0 if confirmed; else -1 in the package (and `.wrapper` renamed to `_explicitize_args`) | likely (J4 holds) |
| R1 | remark (ruling) | B4 for `df: DataFrameOrSeries` | `DataFrameOrSeries` is `Any` (`typing.py:57`); its docstring lists concrete classes (`typing.py:54-56`), and `docs/other_dataframes.md` adds a pyarrow Table and a modin DataFrame (both wrapped by `narwhals.from_native`). The writer takes the documented classes (B4), selected by the module and class names the package tests (`typing.py:74-91`). I took the opposite stance blind (client frames opaque, B5) and now side with the writer: `Any` does not contradict the documentation, a union of concrete classes is not an abstract type, and fabric already names one method under two receiver classes. The README does not state this case. Proposed wording for B4: "A type alias of `Any` whose documentation lists concrete classes fixes those classes; a check of the class's module or name selects among them, as `isinstance` does." Under the other reading, a few dozen outside edges (mostly confirmed by the trace) would become rejected trace edges. | 0 | likely |

## Step 1: blind re-derivation

**Skeleton without the ledger.** A scratch benchmark directory under
`$TMPDIR/heldout3-audit-itables/` held a copy of `projects.toml` and a
`projects` link. `check.py --skeleton itables` gave 1989 sites: 1236 call,
5 decorator, 477 getitem, 151 iter, 65 op, 22 mapping, 31 setattr, 2
getattr; 6 value sites. The candidate
`_SubscriptableFallback.__getitem__` is proposed at 793 sites, and 715
implicit sites have it as their only candidate. So I drew by kind, in
skeleton order: `rng = random.Random(20261111)`; `rng.sample(explicit, 45)`
(1235 explicit sites without the value sites); `rng.sample(fallback-only
implicit, 15)`; `rng.sample(setattr and getattr, 10)`; plus the 6 value
sites: 76 sites. I wrote the callees of each from the source before I opened
the writer's files and the trace (`$TMPDIR/heldout3-audit-itables/blind.md`).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Explicit | 45 | 45 | 0 |
| Implicit, only the fallback candidate | 15 | 15 | 0 |
| setattr | 10 | 10 | 0 |
| Value sites | 6 | 4 | 2 |
| **Total** | **76** | **74** | **2** |

The 2 disagreements, both mine:

- **Auditor naming error.** `streamlit.py:30:37`
  `_streamlit_component_func(...)`: I wrote
  `streamlit.components.v2.component.__call__`. The micro-benchmark case
  `external/decorator` names the call of an object that a stub returned by
  the stub's path: `streamlit.components.v2.component`, as the writer has.
  We agree that `<lambda1>` is no callee.
- **Auditor stance (R1).** `downsample.py:180:24` `type(df)(...)`: I had
  only `pandas.DataFrame` (the numpy path, `javascript.py:1162`, with a
  `maxBytes` below one cell); the writer also has `polars.DataFrame`, from a
  documented polars frame. Under R1 the writer is right.

## Step 2: exhaustive checks

- **Default rejection** (706 sites). The 87 subscripts of `NotRequired` and
  `Unpack` (74 in `typing.py`, 13 in signatures) accept the candidate, and
  no other site does (script over the skeleton and the ledger). No other
  operand can be a `_SubscriptableFallback`. The 78 explicit sites under the
  default are builtins over frames, dicts, lists, strs and generators, and
  `Styler.format("{:.3f}")` (no index field); each keeps its outside callee.
  No package module has `from __future__ import annotations`, and no
  syntax needs Python 3.10, so the 3.9 and 3.10 branch is real.
- **setattr and getattr** (33 sites). All 31 setattr sites rightly reject
  `_ITableOptionsModule.__setattr__`: no package code stores on the
  `itables.options` module after `options.py:237`, and the store of
  `__class__` runs the plain module's `__setattr__`. The getattr site
  `widget/__init__.py:78:36` `self.style` is the property;
  `sample_pandas_dfs.py:394:12` `df.style` is pandas'.
- **Dispatch and callbacks.** `widget.ITable` (`update` from the `df`
  setter, the `style` getter); `JavascriptFunction.__init__` (the only two
  instantiations, `javascript.py:1306`, `:1317`); `TableValuesEncoder.default`
  called back by `json.dumps` (`datatables_format.py:330`); the `re.Pattern.sub`
  callbacks (`javascript.py:770`, `:824`, `:857`, `:884`); the three polars
  lambdas, called by `with_columns` and not by `map_elements`; the
  `lru_cache` wrapper (`sample_pandas_dfs.py:316`, `:350`). All correct.
- **Frames (R1).** I checked each method call on a frame against the classes
  that reach it after the conversions of `get_itable_arguments`
  (`javascript.py:1139-1198`): `Series.items` in the three public functions
  that a Series can reach (`datatables_format.py:298`, `downsample.py:18`,
  `javascript.py:1092`), `estimated_size` (polars and narwhals), `to_frame`
  (pandas, polars, narwhals), the Styler-only branch (`:1334-1344`),
  `safe_reset_index` (`assert isinstance`, `:1734`). No edge depends on a
  class that cannot reach the site.
- **Functions that no site calls** (44 nodes, with the 21 modules). Rule A
  holds; the checker requires an entry for every explicit site.
  `_raise_if_javascript_code` is judged as public, as B requires.
- **Callees outside the package** (227 names). One scheme: module functions
  by import path, methods by the public class of the receiver, missing
  modules by access path (streamlit, anywidget, dash, tomli). The numpy
  dispatchers and ufuncs are calls of instances
  (`numpy._ArrayFunctionDispatcher.__call__`, `numpy.ufunc.__call__`), while
  Cython functions keep their module path (`numpy.random.binomial`, as
  aiocache's `msgpack.loads`). This follows the micro-benchmark split between
  function types and other callable classes. The polars methods that
  `call_expr` generates have an attribute path (`polars.Series.to_physical`),
  which the trace accepts as an alias of `polars.series.utils.call_expr.wrapper`.
  I read all 211 edges from reading only; each has a path that a supported
  version or a documented input takes.
- **Rejected trace edges** (2): naming artefacts of `numpy.random`
  functions, as aiocache's precedent. Accepted.
- **Judgements.** J1: F1. J2, J3: R1. J4: F2. J5 accepted: the test passes a
  dict that the package's `get_expanded_style` made
  (`tests/test_javascript.py:206-208`), a package value for that role (B2).
  J6-J11 accepted.

## README and tools

The tools worked as documented. The README does not decide F1 (dependency
versions limited by other dependencies), F2 (an unread library whose
protocol the analysed source shows) or R1 (documented classes behind an
`Any` alias); proposed rulings are above.

## Third complete source audit (2026-11-16)

The independent source model and inventory were frozen before baseline comparison. The audit reviewed all 925 baseline pairs, all 1361 ledger entries, all 3656 current scanner sites, all 2295 omitted sites (including 1667 without candidates), the 706 default decisions, all 301 own-target bindings and all zero-edge bodies. It found 0 false-positive pairs and 2 missing pairs.

* At sample_pandas_dfs.py:350:33 add generate_random_series -> functools._lru_cache_wrapper.wrapper. Supported PyPy 3.11 returns the pure-Python bounded cache closure; CPython's C-wrapper edge and the package cache-miss callback remain.
* At sample_pandas_dfs.py:370:50 add generate_random_df -> <builtin>.str.title. A concrete ndarray/Sequence[str] subclass containing an object-dtype builtin string is an admitted public input. NumPy choice preserves that dtype without calling a client conversion hook, and its object getter returns the builtin string. The usual numpy.str_.title edge remains.

Site metadata alone removes config.load_config_file at config.py:99:25 -> ValueError: the fixed option checks return or warn, type mismatches are caught, and typeguard check_type ignores global callback configuration. The pair survives at config.py:87/91. Widget update at widget/__init__.py:91 remains reachable through public kwargs supplying the three deleted keys; both caption regex callbacks have a public table_html/df=None witness. The public generate_encoder factory returns a public class, so direct valid calls to its public default method retain its primitive branch. These retained witnesses are documented in the round-3 handoff.

All prior audit text remains historical. The source-first and post-freeze evidence, pinned primary sources, exact edits, six-file replay and verification results form the round-3 handoff. No target, dependency, generated code or test was imported or executed; no PyCG output or dynamic trace was used as semantic evidence. Source/provenance gates use only static input and stored origin metadata.

## Milestone review correction (2026-11-16)

This record corrects the round-3 proposal above without changing its bytes.
The retained delta is +1/-0: `generate_random_df -> <builtin>.str.title`.
The proposed `generate_random_series -> functools._lru_cache_wrapper.wrapper`
is withdrawn because itables has no explicit PyPy support declaration under
the selected interpreter rule. It is a rejected proposal, not a false-positive
baseline pair. The CPython cache-wrapper edge and package callback remain.

The revised graph has 926 pairs (188 inside, 738 outside) and 1,559
site-target relations. The stored origin result confirms 610 pairs (65.9%);
316 come from reading only. The config.py:99:25 site-only correction remains.
The current judgement file and follow-up evidence supersede the withdrawn
claim above. No new target execution or evaluation gate is reported here.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round 4 source-first audit (2026-11-16)

Retain all 150 nodes and 926 pairs: 0 false positives, 0 missed edges. Full coverage
is recorded in the round 4 handoff: 21 modules, 129 function names, 3656 sites,
1361 ledger entries, 1559 site-target relations, 2295 omitted sites, 706 default
decisions, 58 rejection lines (80 candidates), 6 value sites and 17 zero-edge
bodies. The six original baseline files are staged; only judgements and this
append-only audit record change.

One metadata group states CPython >=3.9 and the unanswered normal/-O/-OO working
assumption, and advances the current pass provenance. All 22 assertions and
all callback/receiver boundaries were checked. safe_reset_index gets only
pandas.DataFrame on package paths; no optimized-mode edge is added.

The frozen source model was corrected separately for the public encoder
factory's direct default(True) path and the compiled PySeries naming rule.
These were auditor-model errors, not defects in the installed ground truth.
The raw primary sources and all source, baseline and final hashes are retained.
No package/dependency/test/generated code was executed or imported. Root
verification and ordered acceptance remain the final step for this handoff.
