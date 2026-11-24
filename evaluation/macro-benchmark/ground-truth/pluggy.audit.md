# pluggy 1.7.0: audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Independent audit of `pluggy.ledger`, `pluggy.json`, `pluggy.rejected.json`
and `pluggy.md` (commit `4c7f6365`). Every claim below comes from the source
under `projects/pluggy/src/pluggy/` and Python semantics. No static analysis
tool was used. The trace was used only as a lower bound.

**Result (final).** Under the lead's final scope rules (A, B1-B5, C) and
rulings (a), (b) and (c), the graph has no missing edge, no wrong edge and no
wrong name. One finding stands: F1, a wording fix to the reason of a default
rejection. Its decision is right. F2 and F3, raised under the earlier wording
of the rules, are withdrawn (see "Final scope rules"). Rule B4 adds nothing
for pluggy; rule B5 changes nothing.

**Final count:** 1 finding (F1, false rejection reason, certain). Withdrawn:
2 (F2, F3). Missing edges 0, wrong edges 0, wrong names 0, convention 0.
Graph changes needed: 0 edges added, 0 removed.

## Findings

| Id | Kind | Site or edge | Evidence | Confidence |
|---|---|---|---|---|
| F1 | false rejection reason | `default reject pluggy._compat.DistFacade.__getattr__`, at `pluggy._compat 39:29 getattr self._dist` (in `DistFacade.__getattr__`) and `pluggy._compat 43:32 getattr self._dist` (in `DistFacade.__dir__`) | The default says "this receiver is not one". At these two sites the receiver is `self`, a `DistFacade`. `__getattr__` does not run because `_dist` is a slot (`_compat.py:22`) that `__init__` always sets (`_compat.py:25`), so normal lookup finds it. The decision (reject) is right. `pluggy.md:154` gives the right reason ("The loads of `self._dist` find the slot"); the ledger does not. Fix: decide the two sites with a site-level `reject` and the slot reason, or reword the default. | certain |
| F2 (withdrawn: ruling (a), rules A, B1 and C; the two edges stay) | doubtful (wrong edge under a strict reading) | `pluggy._caller.HookCaller.has_spec -> pluggy._caller._SubsetHookCaller.spec` (site `_caller.py 95:21`) and `pluggy._caller.HookCaller.set_specification -> pluggy._caller._SubsetHookCaller.spec` (sites `103:17`, `105:30`, `106:42`) | Both edges need a client that calls `has_spec()` or `set_specification()` on the `_SubsetHookCaller` that `subset_hook_caller` returns. Neither method has a docstring, and both carry `# TODO: Document, or make private.` (`_caller.py:93`, `:97`). `docs/api_reference.rst:28-30` documents `HookCaller` with `:members:` and no `:undoc-members:`, and `docs/conf.py` sets no default options, so autodoc leaves both methods out of the API reference. The lead's rule (1) says "the API is the documented public interface". The writer reads the API as "public names" (`pluggy.md:104-106`). Under rule (1) as written, these two edges go. The trace has neither. The package never calls these methods on a subset caller (`_manager.py:238`, `:249`, `:360`, `:489` all use relay callers). | unsure |
| F3 (withdrawn: ruling (c), rules B1 and C; not an edge) | doubtful (missing edge under a broad reading) | `pluggy._compat.DistFacade.__getattr__ -> pluggy._compat.DistFacade.__getattr__` at site `_compat.py 39:29 self._dist` | A `DistFacade` from the public `list_plugin_distinfo()` has `_dist` set. `copy.copy`, `copy.deepcopy` and `pickle.loads` make a new instance with `__new__` and then do `hasattr(y, "__setstate__")` before they restore the slots. `DistFacade` and `object` define no `__setstate__`, so `__getattr__` runs, its `self._dist` load fails (slot not set), and `__getattr__` calls itself until `RecursionError`. The recursive call is a package site calling a package function. The trigger is a client that passes a package object to a library function that accepts any object; the lead's rule (3) most likely excludes it. Not added to the ledger; listed for the lead to decide. | unsure |

No finding of kind "missing edge", "wrong edge", "wrong name" or
"convention".

## Final scope rules (lead's rulings, applied after the audit)

### Rules A and C, ruling (a): F2 withdrawn

- Ruling (a): "public" is by name (rule C), not by what the rendered
  documentation includes.
- Rule C makes "public" mechanical. `has_spec` and `set_specification` have
  no leading underscore, and no docstring or document marks them private.
  The missing docstring does not make them private. Rule A keeps the
  out-edges of every function. So the question is only which objects can be
  `self` (rule B1).
- `subset_hook_caller` is public and returns a `_SubsetHookCaller`
  (`_manager.py:648`). That class inherits `has_spec` and
  `set_specification`, so a client can call them on it, and `self` is then a
  `_SubsetHookCaller`. Both edges of F2 are right. The ledger needs no
  change.

### Rule B1: which objects are `self` in the `HookCaller` helpers

I decided each helper from where the package calls it and on which objects.
Clients do not call private entry points (rule C), so the package's own calls
are the only calls of the three private helpers that run on relay callers.
The relay holds only `HookCaller`s. The package sets relay attributes only at
`_manager.py:248` and `:357`, both with a `HookCaller` built at `:247` or
`:356`. By rule B3, a `_SubsetHookCaller` that a client stores in the relay
is not considered, because the package never puts one there.

| Helper | Package call sites | `self` | Can `self` be a `_SubsetHookCaller`? | Ledger | Verdict |
|---|---|---|---|---|---|
| `_remove_plugin` | `_manager.py:317` | `hookcaller` from `get_hookcallers`, which reads `self.hook.__dict__.values()` (`:565`) | no | rejects `_SubsetHookCaller._hookimpls` at 118:44, 119:39, 121:14 | correct |
| `_add_hookimpl` | `_manager.py:255` | `hook` from `getattr(self.hook, hook_name, None)` (`:245`) or `HookCaller(...)` (`:247`) | no | rejects it at 129:41, 134:35, 136:47, 141:18, 143:18, 147:39, 149:18 | correct |
| `_maybe_apply_history` | `_manager.py:254` | the same `hook` as `:255` | no | rejects `_SubsetHookCaller._call_history` at 267:25, 268:49 | correct |
| `_apply_defaults` | `_caller.py:193`, `:216`, `:238` | `self` of `__call__`, `call_historic`, `call_extra`, which are public and inherited by `_SubsetHookCaller` | yes | accepts `_SubsetHookCaller.spec` at 155:17, 155:42, 157:24 | correct |
| `_verify_all_args_are_provided` | `_caller.py:194`, `:217`, `:239` | the same | yes | accepts `_SubsetHookCaller.spec` at 161:17, 162:33, 166:45 | correct |
| `is_historic` (public) | `_caller.py:190`, `:235`, `:266`; `_manager.py:432`; clients | relay callers, and `self` of `__call__` and `call_extra` | yes | accepts `_SubsetHookCaller._call_history` at 114:21 | correct |
| `_SubsetHookCaller` properties | (`self._orig`) | `orig` from `getattr(self.hook, name)` (`_manager.py:637`, stored at `:648` and `_caller.py:300`) | no (`self._orig` is a relay `HookCaller`) | rejects the property at 309:36, 315:27, 319:27 | correct |
| `PluginManager._verify_hook` | `_manager.py:239`, `:253`, `:362` | relay callers | no | rejects `_SubsetHookCaller.spec` at its 7 `hook.spec` loads (439:21 to 458:40) | correct |
| `PluginManager.subset_hook_caller` | (`orig._hookimpls`, `:642`) | `orig`, a relay caller | no | rejects it at 642:50 | correct |

The writer's rejection reasons already name the call sites and the objects
(for example ledger line 84: "`_remove_plugin` is called only at
`_manager.py:317`, on a `HookCaller` of the hook relay"). They do not rely on
the helper being private. `pluggy.md:116-119` says "private methods", but its
argument is the same: the package's call sites and the relay.

### Ruling (c): F3 withdrawn

`_dist` is unset only on an instance that `copy` or `pickle` makes without
`__init__`. Ruling (c): `DistFacade` is in the private module `_compat`, so
clients do not create, copy or pickle its instances (rules C and B1). The
package creates every instance through `__init__` (`_manager.py:539`), which
sets `_dist` (`_compat.py:25`). So the `self._dist` load at 39:29 always
finds the slot, and the self-loop is not an edge. The ledger needs no change.

### Ruling (b): library values that the documentation offers

A value from outside the package that the client passes is a client
callback, also when the documentation uses it as an example. So
`setwriter(print)` (`docs/index.rst:1049`) gives no
`TagTracer._processmessage -> <builtin>.print` edge. The ledger already
follows this (note at `_tracing.py 123:25`). No change.

### Rule B5: client objects are opaque

What a client-supplied object calls when the package uses it is client
behaviour. In pluggy this covers plugins, hook specification namespaces,
hook implementation functions, `call_extra` methods, hook arguments and
results, result callbacks, writers, processors and monitoring functions
(`before`/`after` of the client), also when the client builds them with
library code around a package object (for example `functools.partial` of a
package function). The ledger already treats all of them so: no package edge
and no outside callee goes through them. The two rejected trace edges
(`list.append` of the tests as result callback and as writer) are this case.
No change.

### Ruling on annotated outside types (B4): no change

I checked every parameter and stored value of the package that receives an
explicit method call or an explicit call, and the two rejected trace edges.

| Value | Annotation or documentation | Explicit call on it | Effect of the ruling |
|---|---|---|---|
| `TagTracer._writer` (`setwriter(writer: _Writer \| None)`, `_Writer = Callable[[str], object]`, `_tracing.py:14`, `:127`) | bare callable | `self._writer(...)` (`_tracing.py:123:25`) | client callback, no outside callee. The rejected trace edge `TagTracer._processmessage -> <builtin>.list.append` stays rejected. `print`, which `docs/index.rst:1049` offers, also stays out (ruling (b)) |
| `processor` (`_Processor = Callable[...]`, `_tracing.py:15`, `:130`) | bare callable | `processor(tags, args)` (`:125:22`) | no outside callee |
| `result_callback` (`Callable[[Any], None] \| None`, `_caller.py:203`; `_CallHistory`, `:51-53`) | bare callable | `_caller.py:227:32`, `:273:36` | no outside callee. The rejected trace edge `HookCaller._maybe_apply_history -> <builtin>.list.append` stays rejected |
| `before`, `after` (`_BeforeTrace`, `_AfterTrace`, `_manager.py:36-39`) | `Callable` aliases | `_manager.py:593:19`, `:597:18` | client values have no outside callee. The package's values (the `enable_tracing` closures) are already edges |
| `hook_impl.function` (`_HookImplFunction`, `_impl.py:22`), `call_extra(methods: Sequence[Callable[..., object]])` | callable | 6 `hook_impl.function(...)` sites | no outside callee |
| `HookCaller._hookexec` (`_HookExec`, a `Callable` alias), `PluginManager._inner_hookexec`, `oldcall`, `Result.from_call(func: Callable[[], ResultType])` | callable | the value sites | the package values are already edges. No outside callee |
| `DistFacade._dist` (`dist: importlib.metadata.Distribution`, `_compat.py:24`) | concrete outside type | none: `getattr(self._dist, attr)` (`:39`) and `dir(self._dist)` (`:43`) are builtin calls. Python makes the attribute load and `__dir__` implicitly, which gives no outside edge | nothing to add |
| `dist`, `ep` in `load_setuptools_entrypoints` (results of `importlib.metadata.distributions()`) | concrete outside types | `ep.load()` (`_manager.py:521`) | already `importlib.metadata.EntryPoint.load`. `dist.entry_points` is an attribute load (property), not a call |
| `PluginManager._plugin_distinfo` (`list[tuple[_Plugin, importlib.metadata.Distribution]]`) | concrete | no call on the distributions (`list(...)`, `:549`) | nothing to add |
| `_warn_for_function(warning: Warning, function: Callable)` (`_manager.py:42`) | concrete for `warning` | no method call on `warning` (`warnings.warn_explicit(warning, type(warning), ...)`) | nothing to add |
| `_warn_teardown_exception(e: BaseException)`, `_describe_failure(exc: Exception)` | concrete | only `type(e)`, `repr(exc)` (builtins) and f-strings (implicit) | nothing to add |
| `Result._exception` (`exception: BaseException \| None`, `_result.py:34`) | concrete | `exc.with_traceback(tb)` (`_result.py:103:37`) | already `<builtin>.BaseException.with_traceback`, which matches the ruling |
| `HookSpec.warn_on_impl_args` (`Mapping[str, Warning] \| None`; the docstring of `HookspecMarker.__call__` says "the arguments in the dict", `_decorators.py:91-93`) | abstract annotation, but the documentation fixes `dict` | `.get(...)` (`_manager.py:458:66`) | already `<builtin>.dict.get`, which matches the ruling |
| `spec_opts`, `opts`, `hookimpl_opts` (`HookspecOpts`, `HookimplOpts`: package `TypedDict`s, which are `dict` at run time) | dict | `.get`, `.setdefault` | already `<builtin>.dict.get` and `<builtin>.dict.setdefault` |
| `teardown`, `function_gen` (`Teardown = Generator[None, object, object]`, `_execution.py:24`; the `HookimplMarker` docstring requires a generator function, `_decorators.py:185-204`) | the documentation fixes a generator | `.send`, `.throw`, `.close` | already `types.GeneratorType.*` |
| `text: str` (`_escape_surrogates`, `_is_plain_token`), `tags: str` (`setprocessor`, after `isinstance`), `qualname: str` | `str` | `isascii`, `encode`, `isprintable`, `split`, `rsplit` | already `<builtin>.str.*` and `<builtin>.bytes.decode` |
| `kwargs`/`caller_kwargs` (`Mapping[str, object]`), `remove_plugins` (`Iterable`), `args` (`Sequence`) | abstract | no explicit method call (only `**`, `in`, `[...]`, iteration and `set(...)`) | nothing to add |

Result of the ruling: 0 edges added, 0 removed, 0 rejections changed.

### A note on rule C for pluggy

Every pluggy class is defined in a private module (`pluggy._manager`,
`pluggy._caller`, `pluggy._tracing`, ...) and re-exported from `pluggy`. If
rule C read the defining qualified name literally (`pluggy._manager.PluginManager.register`),
every function would be private. I applied it to the public access path:
`pluggy.PluginManager.register`, `pm.trace.root.setwriter` (the documented
tracing entry point, `_manager.py:168`, `docs/index.rst:1049`). Ruling (c)
uses the defining module for `DistFacade`, which pluggy does not re-export.
For pluggy neither reading changes an edge: the values at every site stay
the same.

## Step 1: blind re-derivation

- Scratch setup: `projects.toml` copied to `$TMPDIR/pluggy-audit/bench/`,
  `projects/` symlinked read-only, empty `ground-truth/`; skeleton made with
  `check.py --config <scratch>/projects.toml --skeleton pluggy` (795 site
  lines, no defaults). Sample: `random.Random(20261111).sample(range(795),
  60)` over the site lines in skeleton order, plus the 20 no-name sites that
  the sample did not contain (2 of the 22 were in it: `_execution.py 147:45`,
  `_manager.py 597:18`). Total: 80 sites.
- I wrote the callees of all 80 sites from the source before I opened the
  ledger. Then I compared site by site.

| Sample | Sites | Agree | Writer missed an edge | Writer has a wrong edge | Naming only | I was wrong |
|---|---|---|---|---|---|---|
| Random (seed 20261111) | 60 | 60 | 0 | 0 | 0 | 0 |
| No-name sites not in the random sample | 20 | 20 | 0 | 0 | 0 | 0 |
| **Total** | **80** | **80** | **0** | **0** | **0** | **0** |

Disagreement rate: 0/60 (0 %) on the random sample, 0/80 on all sampled
sites. Of the 60 random sites, 23 are `getattr` sites that only the three
default rejections decide (no entry); my blind answer for each was "no
callee".

## Step 2: default rejections

| Default | Sites decided | Check | Result |
|---|---|---|---|
| `pluggy._caller.HookRelay.__getattr__` | 403 (all 391 `getattr` sites and the 12 `getattr(...)` calls) | The `def` is inside `if TYPE_CHECKING:` in the class body (`_caller.py:42-44`). `typing.TYPE_CHECKING` is `False` at run time, so the class never gets the function. One argument covers all 403 sites. | correct |
| `pluggy.__getattr__` | 403 | `rg` over the package: no `import pluggy`, no `from pluggy import`, no `pluggy.X` in code (only in docstrings and strings). Imports: `from . import _tracing` (`_manager.py:16`) runs while `__init__.py:24` imports `_manager`, before `__init__.py:32` defines `__getattr__`, so `_handle_fromlist`'s `hasattr(pluggy, "_tracing")` finds no module `__getattr__`. The lazy `from ._compat import DistFacade` (`_manager.py:537`) loads attributes of `pluggy._compat` (no `__path__`, so no `_handle_fromlist`), not of `pluggy`. `import importlib.metadata` (`_manager.py:508`) and `from importlib.metadata import version` (`__init__.py:34`) do not touch `pluggy`. The shims `_hooks.py` and `_callers.py` use only `from ._x import Y`. | correct |
| `pluggy._compat.DistFacade.__getattr__` | 402 | `DistFacade(...)` appears only at `_manager.py:539`; the instances go to the client. No package code receives one back (except through roles that rule (3) excludes). Attribute loads with a `DistFacade` receiver: only `self.*` in the three methods of `DistFacade`: `34:26 self.metadata` (not defined, so `__getattr__` runs: accepted, correct), `39:29 self._dist` and `43:32 self._dist` (slot found: rejected, correct, but see F1). The 12 `getattr(...)` calls have receivers that are client objects, the `HookRelay`, or the raw `Distribution` (`_compat.py:39:23`). `DistFacade` defines `_dist` (slot), `project_name`, `__init__`, `__getattr__`, `__dir__`. | decision correct; reason false at 2 sites (F1) |

Sites examined: all 403 sites by receiver class (391 `getattr` sites by the
module and the receiver of each, 12 `getattr(...)` calls one by one), and the
5 attribute loads in `DistFacade` one by one.

## Step 3: value sites

All 22 no-name sites and `self.__class__(...)` (`_tracing.py:147:30`)
agree with my own enumeration:

- `self._hookexec(...)` (4 sites): `_hookexec` is set only at `_caller.py:77`
  and `:303`; the package passes `self._hookexec` (bound
  `PluginManager._hookexec`) at `_manager.py:247` and `:356` only.
- `self._inner_hookexec(...)`: set at `_manager.py:172` (`_multicall`),
  `:600` (`traced_hookexec`), `:603` (`oldcall`, one of the two).
- `oldcall(...)`: the same two values.
- `before(...)`, `after(...)`: the only package call of
  `add_hookcall_monitoring` is `_manager.py:630` with the closures of
  `enable_tracing`.
- `hooktrace(...)` (2): `TagTracer.get` returns a `TagTracerSub`
  (`_tracing.py:94`), so `TagTracerSub.__call__`.
- `func()`: the lambda of `_manager.py:595` (only call of `from_call`).
  `cls(...)`: `Result.__init__`.
- `hook_impl.function(...)` (6), `result_callback(...)` (2), `self._writer`,
  `processor`: no package value. `rg` confirms the package never calls
  `register` with a package object (`_manager.py:522` registers `ep.load()`),
  never calls `call_historic`, `call_extra`, `setwriter` or `setprocessor`,
  and marks no function with `HookimplMarker`.

## Step 4: wrapper protocol

Checked 10 generator sites (`_execution.py` 45:13, 54:22, 63:23, 122:57,
126:21, 141:25, 167:39, 175:43, 180:34, 184:31) and the 4
`hook_impl.function` sites of the wrapper branches. `run_old_style_hookwrapper`
is the only package generator function; its edge comes from `_multicall`
(122:57), and the calls of its body are its own edges. `next`, `send`,
`throw`, `close` are named `<builtin>.next` and `types.GeneratorType.*`.
No disagreement.

## Step 5: functions with no caller in the package

34 functions (and the 13 modules) have no incoming package edge. For each I
searched every textual use with `rg`, including `getattr`/`setattr` with
string names (`"__call__"`, `"__func__"`, `"__name__"`, `"__dict__"`,
`project_name + "_impl"/"_spec"`). Each is public API, a special method that
only client code triggers, a closure returned to the client (`undo`), or the
`TYPE_CHECKING` `HookRelay.__getattr__`. No missed caller.

## Step 6: polymorphism and properties

- `_SubsetHookCaller` properties (51 `getattr` entries checked): accepted in
  `has_spec`, `set_specification`, `is_historic`, `get_hookimpls`,
  `__call__`, `call_historic`, `call_extra` and in the private helpers
  `_apply_defaults` and `_verify_all_args_are_provided` (which the public
  methods call on `self`: `_caller.py:193-194`, `:216-217`, `:238-239`).
  Rejected in `_remove_plugin`, `_add_hookimpl`, `_maybe_apply_history`
  (only callers `_manager.py:317`, `:255`, `:254`, all on relay callers), in
  the properties themselves (`self._orig` is a relay caller), in
  `_verify_hook` and in `subset_hook_caller`. All correct, also under the
  final rule B1 (see the table under "Final scope rules").
- `TagTracer.get` vs `TagTracerSub.get`: 16 `.get(...)` sites. Only
  `_manager.py:169:76` and `:612:40` call a tracer; both receivers are a
  `TagTracer`. The other 14 are dicts. Correct.
- `Result.exception`: one load (`_manager.py:626:24`), accepted.
  `Result.excinfo`: no load. `DistFacade.project_name`: 5 loads, all on a
  `HookspecMarker`, `HookimplMarker` or `PluginManager` slot or attribute,
  rejected. Correct.
- 66 `format` sites: each value is a `str`, an `int`, a code-object field, an
  `inspect.Signature`, or a client object; no package object is formatted.
  `str(obj)`/`repr(obj)` in `_tracing.py` see only trace values, which the
  package fills with the hook name, constant strings, hook keyword arguments
  and hook results (not the `HookImpl` list, which `before` does not trace).
  Correct.
- `__call__` (4 definitions), `__dir__`, `__getattr__`: covered above.

## Step 7: rejections and notes

Read all 128 rejection lines, 80 notes and the 3 default reasons against the
source. One false reason (F1). Nit: the notes at `_caller.py 227:32` and
`273:36` both point to `pluggy.rejected.json`, which has an entry only for
`_maybe_apply_history`; the `call_historic -> <builtin>.list.append` trace
edge from `227:32` is hidden by the real edge at `218:34`. No effect on the
graph.

## Step 8: callees outside the package

Checked all 166 outside edges of `pluggy.json` against their sites (well
beyond the 40 asked), with focus on `inspect`, `warnings`,
`importlib.metadata`, `typing`, generator methods, descriptor `__get__`
methods, inherited `__init__` of the package exceptions, and methods of
`dict`, `list`, `set`, `str`, `bytes`. No wrong name, no missing callee.

## Step 9: rejected trace edges

Both entries are client callbacks. `testing/test_pluginmanager.py:1178` and
`:1181` pass `result.append` to `call_historic`; `testing/test_tracer.py:26`
and `testing/test_pluginmanager.py:1017` pass `out.append` to `setwriter`.

## Step 10: checker

`check.py pluggy`: no errors; 278 edges (112 internal, 166 outside); the
trace confirms 270 (97.1 %); 100 of 101 functions run. `--report pluggy`: 0
undecided; 1 package callee beyond the candidates
(`_tracing.py 147:30 self.__class__(...) -> TagTracerSub.__init__`), which
is correct. The 8 edges that only reading gives (`pluggy.md:226-235`) are
each justified; two of them are the edges of F2, which stay.

## Open questions about conventions

The lead's rulings answer all three questions of the first version of this
audit:

1. (a) "Documented" vs "public by name": public is by name (rule C). F2 is
   withdrawn; its two edges stay.
2. (b) A library callable that the documentation offers
   (`setwriter(print)`): a client callback. Only values defined in the
   package and the package's own defaults are in scope for a role. No
   `<builtin>.print` edge.
3. (c) Copy or pickle of a `DistFacade`: out of scope, because clients do
   not create, copy or pickle instances of a class in the private module
   `_compat`. F3 is withdrawn.

No question remains open for pluggy. The remark in "A note on rule C for
pluggy" is about wording only and changes no pluggy edge.

## Same-function placement clarification (2026-11-16)

The M7 move of TagTracer._format_message -> _safe_str from _tracing.py:103:31
to103:27 is an allowed map placement normalization under README ruling 12.
The previous constructor attribution was valid because join consumes that
map in the same function. The chosen consumer relation remains; no graph
pair changes. The original seven metadata groups comprise six baseline
correction groups and this one normalization.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).


## Round-four source-first audit (2026-11-16)

A fresh source-first review retained all 278 edges (112 internal, 166 outside)
on 114 nodes. No false positive, missed edge or current-metadata correction
was found. Reviewed all 1,131 AST sites: 795 ledger-relevant sites (455
entries and 340 default-only sites), plus 336 implicit sites without
candidates; all 23 value sites and all 114 bodies were covered.

The source inventory and receiver/callback model were frozen before the
baseline, ledger or prior audit was opened. CPython and explicitly supported
PyPy >=3.10 are included without an inferred upper bound. Rechecked subset
receiver restrictions, opaque client callbacks/results, own generator
resume/exit paths, Result exception receiver variants, all default
rejections/exclusions and zero-call bodies under global A/B1-B5/C.

Graph, ledger, added-edge and rejected-edge files remain byte-identical.
Trusted static structural and origin checks passed; no target code or
analysis tool was executed. Detailed source freeze, pair/site/body coverage
and verification logs are retained in the round-four pluggy review bundle.
