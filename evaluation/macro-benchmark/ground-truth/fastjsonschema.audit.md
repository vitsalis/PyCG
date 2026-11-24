# fastjsonschema: independent audit of the ground truth

> Historical audit snapshot. The global-scope audit of 2026-11-15
> supersedes its current-state claims; see [fastjsonschema.md](fastjsonschema.md)
> and the audit record (audit record `2026-11-15/README.md`).

Release v2.22.3, commit `9d3f5ee74d0749ef4abf695f370437aca5f9d56c`. Audited
files (SHA-256 prefix): `fastjsonschema.ledger` `eb20671d8a6ee0d3` (771
entries, 102 notes, 25 rejection lines, 1 default rejection),
`fastjsonschema.json` `ab53e9cd1bf080b0` (548 edges: 314 in the package, 234
to 67 callees outside), `fastjsonschema.rejected.json` `bd9b07e981e6b94e`
(1 edge), `fastjsonschema.md` `67e8b7ed0a55a06a`, and the trace
`dynamic/fastjsonschema.json` `6d09a230953a85b8` (496 edges). `check.py
--benchmark-dir macro-benchmark-heldout-3 fastjsonschema` reports no errors.
The trace confirms 495 of the 548 edges; 53 come from reading only.

I judged the files by the README conventions and scope rules (A, B1 to B5,
C), the rulings of the later sets, and the lead's scope ruling 4 (the code
that the package generates and runs with `exec` is not source). I read the
package, its tests and `docs/index.rst` as data. I ran no static analysis
tool and read no analysis output. Nothing of the package was run or imported.

**Final state.** The blind sample agrees with the ledger at every site (76
of 76). The exhaustive checks found no edge to add or remove. There are 2
remarks on README wording (R1, R2), 1 fact that I could not check locally
(V1), and 1 tool defect outside the ground truth (T1), which confirms the
writer's own observation.

## Findings

| Id | Severity | Kind | Site or edge | Evidence | Edges |
|---|---|---|---|---|---|
| R1 | low | README wording; asks the lead to confirm | ruling 4 and the calls that generated code makes: `__init__.py:294:9` (`exec`), `__init__.py:172:108` (`compile(...)(data)`) | Ruling 4 (README "A fifth directory", item 4) says that generated code is not source. It does not say what happens to the calls that this code makes. Before I opened the writer's files, I applied the micro-benchmark rules (micro README "Nodes", "Scopes without a node"; cases `dynamic/compile_exec`, `exec_defines_function`, `exec_in_function`). (1) A function that `exec` defines has no node, and a call of it has no named callee. (2) The calls in the module code of the exec'd string belong to the scope that calls `exec`. That code is always `NoneType = type(None)` (`generator.py:139`, indent 0) and the `def` lines, so `compile -> <builtin>.type`. (3) A package function that a generated function calls is a callee of the package site that called the generated function. The only such site is `validate` 172:108, and the package functions are `JsonSchemaValueException.__init__` (`generator.py:308-324`) and `JsonSchemaValuesException.__init__` (`generator.py:160`). The builtin and library calls of a generated function are no edges. The writer reached the same three decisions independently (`fastjsonschema.md`, "The generated code"). Proposed sentence for ruling 4: "it has no nodes; calls in its module code belong to the function that runs `exec`, and the package functions that a generated function calls are callees of the package site that calls the generated function (micro-benchmark `dynamic/*exec*`)." | 0 (the graph already has the 3 edges; the trace has `validate -> JsonSchemaValueException.__init__`) |
| R2 | low | README wording | `ref_resolver.py:52:29` and `64:31` `urlparse.urlsplit(uri)` -> `urllib.parse.urlsplit` and `functools._lru_cache_wrapper.__call__` | The README rule "Where the admitted versions of a library give a receiver two classes, the method has both names" (fabric, `connection.py:291`) speaks of receivers. Here a module function is a plain function on one version and an `lru_cache` wrapper on later ones. The writer extends the rule to give both names, and I agree: the nearest rule supports it. Proposal: "a receiver two classes, or a callee two kinds of object". | 0 |
| V1 | low | fact not checked locally | the same two sites: the `urllib.parse.urlsplit` name relies on 3.10 being a plain function | Local CPython sources: 3.9 has a plain `def urlsplit` (CommandLineTools 3.9, `urllib/parse.py:437`). 3.13, 3.14 and 3.15 have `@functools.lru_cache(typed=True)` (uv 3.13.12 `:469`, Homebrew 3.14 and 3.15). No 3.10, 3.11 or 3.12 source is on this machine, and I did not fetch any. The writer read them on GitHub (judgement 2). My memory agrees that the cache came in 3.11. If 3.10 already had the cache, 2 edges go: `normalize -> urllib.parse.urlsplit` and `resolve_remote -> urllib.parse.urlsplit`. | 0 (or -2) |
| T1 | medium, tool; not a ground-truth finding | the tracer loses an owner frame | `macro-benchmark/trace.py:190-196`; `micro-benchmark/validate.py:439, 449, 513-518`; `trace.py:149-157` | I confirm the writer's observation by reading; I ran nothing. `trace.py` overrides `on_call` and calls `super().on_call(...)`. The validator registers `self.on_call` as the CALL callback (`validate.py:526-528`), so the override is the callback, and in the validator's `on_call` `sys._getframe(1)` is the frame of `trace.py`, not the frame that made the call. As a result, `_eval_owner` finds no exec frame, so the call `type(None)` in the exec'd module code gets no owner. `caller()` (`trace.py:149-157`) also stops at `trace.py`, which `_classify` counts as client code, so the generator function that `contextlib.contextmanager.helper` calls gets no caller. Here this explains 12 of the 53 reading-only edges (the 11 `@contextmanager` edges and `compile -> <builtin>.type`). The same edges are missing from every macro trace (also a thread that library code starts, which takes the same path). The README "Traces / Limits" names sqlparse's `utils.indent` behind `@contextmanager` as a limit of the validator. But the validator handles that case itself (`validate.py:445-452`; micro README, "Generators and coroutines"). The ground truths are not affected, because they add these edges from reading. The trace-confirmation counts and the Limits text are affected. | 0 |

**Note on process (no finding).** One read-only `python -I -c` command, which
printed six source lines to check site positions, ran with its working
directory inside the checkout. `-I` keeps that directory off `sys.path`, and
nothing of the package was imported. All later commands used absolute paths.

## Step 1: blind re-derivation

**Skeleton.** A scratch benchmark directory
`$TMPDIR/heldout3-audit-fastjsonschema/` holds a copy of `projects.toml` and a
`projects` link. `check.py --benchmark-dir <scratch> --skeleton
fastjsonschema` gives 771 sites: 640 call, 11 decorator, 115 with, 5 getattr,
and 6 value sites. Explicit calls dominate, so I drew the sample without
strata. I numbered the site lines from 0 in skeleton order, then took
`random.Random(20261111).sample(range(771), 70)` and added the 6 value sites,
none of which the draw took: 76 sites. I wrote the callees of each site
before I opened the ledger, the graph, the judgements, the rejections or the
trace. The blind file is
`$TMPDIR/heldout3-audit-fastjsonschema/blind.md` (SHA-256 `0bda8106…`,
written 07:55:50; I first read the ledger after 07:56).

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random: `self.l(...)` calls | 14 | 14 | 0 |
| Random: `with self.l(...)` | 10 | 10 | 0 |
| Random: other explicit calls (builtins, `str.format`, `re`, package methods, `@contextmanager` calls, `super()`, a decorator) | 44 | 44 | 0 |
| Random: `with` of a `@contextmanager` call | 2 | 2 | 0 |
| Value sites (172:108, 362:59, 209:21, `indent.py` 10:20, 66:34, 122:19) | 6 | 6 | 0 |
| **Total** | **76** | **76** | **0** |

Classified differences: writer missed an edge 0; writer has an edge that
cannot happen 0; naming only 0; auditor wrong 0. Points that the sample
settles: every `self.l(...)` calls `fastjsonschema.indent.indent.wrapper`
(the `@indent` closure), and `CodeGenerator.l` is reached only through
`func(...)` at `indent.py:10:20`. A `@contextmanager` call has
`contextlib.contextmanager.helper` and the generator function as callees,
and its `with` item has none. `JsonSchemaDefinitionException(...)` has
`<builtin>.ValueError.__init__`. `func()` at `generator.py:209:21` has the
35 `generate_*` methods. 172:108 has the three callees of R1.

## Step 2: dispatch over the class hierarchy (B1)

Hierarchy: `CodeGenerator` -> `CodeGeneratorDraft04` -> `06` -> `07` ->
`2019`. `_factory` makes only the four draft classes (`__init__.py:362`), and
the tests make `CodeGeneratorDraft07` directly (`tests/conftest.py:25`).
Overridden methods: `__init__` (all but 2019), `global_state` (04),
`_generate_func_code_block`, `generate_type`, `generate_minimum`,
`generate_maximum` (06). Every row is the same as the ledger.

| Site | Receivers | Callees |
|---|---|---|
| `self._generate_func_code_block(...)` `generator.py:175` | 04 / 06, 07, 2019 | `CodeGenerator._generate_func_code_block`, `CodeGeneratorDraft06._generate_func_code_block` |
| `func()` `generator.py:209` | bound methods that the three `__init__` methods store (`draft04.py:49-75`, `draft06.py:30-36`, `draft07.py:35-39`) | 24 of 04 + 3 overrides of 06 + 5 new of 06 + 3 of 07 = 35 |
| `code_generator.global_state` `__init__.py:292` | the four draft classes | `CodeGeneratorDraft04.global_state` only; it reaches `CodeGenerator.global_state` through `super()` (`draft04.py:80`) |
| `super().__init__(...)` `draft04.py:45`, `draft06.py:29`, `draft07.py:33` | linear MRO | `CodeGenerator.__init__`, `Draft04.__init__`, `Draft06.__init__` |
| `_get_code_generator_class(d)(...)` `__init__.py:362` | four classes | `__init__` of 04, 06, 07 (2019 inherits 07's) |
| `cls(...)` `ref_resolver.py:122` | `RefResolver` (no package subclass) | `RefResolver.__init__` |
| `self._resolver.*` (`generator.py:76, 154, 227-229, 332`) | the `RefResolver` that `_factory` passes or `generator.py:72` makes | `RefResolver` methods; `resolving`/`in_scope` through `helper` |
| `super().__init__(...)` `exceptions.py:39, 68` | `JsonSchemaException` has no `__init__` | `<builtin>.ValueError.__init__` |

Whether `CodeGenerator` is private (its docstring says it "is not supposed to
be used directly") changes no edge, as the writer says: a bare
`CodeGenerator` has an empty keyword table and only inherited methods.

## Step 3: exhaustive checks

- **Default rejection.** `CodeGenerator.l` decides 159 sites. All 159 are
  `self.l(...)` calls, and each has exactly `-> indent.indent.wrapper` (my
  script over the ledger). All 103 `with self.l(...)` entries have exactly
  `Indent.__enter__` and `Indent.__exit__`. The other 12 `with` sites (6
  `trial_validation`, 2 `resolving`, 3 `in_scope`, 1 `urlopen`) reject both,
  which is right: their context managers are outside the package.
- **Every rejection and note.** 25 rejection lines: 5 `fastjsonschema.compile`
  at `re.compile`, 1 `CodeGenerator.global_state` at 292:35, 1 `func_code` at
  294:9, 1 `Draft04.global_state` at `draft04.py:80:23`, and 17 `reject *`
  (12 `with`, 5 `super().__init__`). All are correct. I read all 102 notes;
  their facts agree with the source.
- **Special methods and properties.** The only special methods are
  `Indent.__enter__`/`__exit__` and the `__init__` methods. The 5 getattr
  sites cover `global_state` (2), `func_code` (2) and `global_state_code`.
  `JsonSchemaValueException.path` and `rule_definition` have no package site.
  They keep their body edges (rule A). `rule_definition -> <builtin>.dict.get`
  is right: the generated code passes a dict literal, or `False` for a
  boolean schema, and `False` returns before the `get` call.
- **Functions without a caller.** `validate`, `path`, `rule_definition` and
  the modules. Nothing is missing.
- **Callees outside the package (67).** I checked the names against the local
  sources of 3.9, 3.13, 3.14 and 3.15. `addinfourl` derives from
  `tempfile._TemporaryFileWrapper` (`urllib/response.py:14`), whose
  `__getattr__` returns `func_wrapper`. `addinfourl.info` is inherited from
  `addinfo`. `HTTPResponse.info` and `HTTPResponse.read` are defined in
  `http.client`. The file, ftp and data handlers build headers with
  `email.message_from_string`. `SplitResult.geturl` is inherited from a
  private base on 3.15 and keeps its public name. `functools.partial.__call__`
  follows the micro-benchmark rule "Calls of instances". See V1 for
  `urlsplit`.
- **Version branches, `TYPE_CHECKING`, optional imports.** There are none
  (searched). The annotations call no package code.
- **Rejected trace edge.** `resolve_remote -> <builtin>.dict.__getitem__` is
  correct. The tests pass `repo.__getitem__` as a handler
  (`tests/test_integration.py:141, 147, 166`; `tests/test_composition.py:63,
  110`): a client callback.
- **Reading-only edges (53).** All are reachable, and the writer's breakdown
  adds up: `__main__` 6, draft-07 content keywords 10, remote fetch 12,
  error branches and enum of dicts 10, `normalize -> urlsplit` 1, `validate` 2,
  `@contextmanager` 11, `compile -> type` 1. For the last 12, see T1.
- **Judgement calls of `fastjsonschema.md`.** I agree with all 8. Judgement 2
  depends on V1.


## Round 3: full source-first audit (2026-11-16)

Two independent readers froze their models after reading all 11 runtime
modules (2,232 lines), before opening the baseline graph or ledger. They
then reviewed all 548 pairs, 917 site-target relations and 1,951 scanner
sites, including the 1,180 implicit expressions without ledger entries.
All 601 package-target relations passed static argument-binding checks.
No target code, tests, generated validator or dependency was run or imported.

No false positive, missed edge or site-target correction was found. The
548 edges remain 314 package and 234 outside edges. The stored trace
corroborates 495; 53 remain supported by source reading. The one rejected
trace pair remains a client-supplied dict handler. The trace was not rerun.

Two judgement-text corrections apply: the 12 non-Indent context sites are
six trial_validation, two _resolver.resolving, one _resolver.in_scope,
two self.in_scope and one urlopen; direct construction of CodeGenerator
is private under global rule C, while admitted draft receivers reach its
base bodies. These corrections change no graph, ledger, added-edge or
rejected-edge bytes.

The earlier V1 is resolved by reading CPython 3.10.16 and 3.11.11 primary
sources: urlsplit is plain in 3.10 and an lru-cache wrapper in 3.11. Both
recorded names remain. The urllib file-response read target remains the
tempfile forwarding closure, as the response inheritance and wrapper
source show. Historical R1/R2 are covered by the current shared rules.
The historical T1 tracer observation was not revalidated or changed here.

The exact metadata patch, complete six-file proposal, source and baseline
hashes, full pair/site adjudications, binding evidence and separate empty
addition list are in /tmp/pycg-macro-audit-pass3/fastjsonschema-* artifacts.
Exact replay, the static ledger checker and --origin passed. The historical
content above is preserved unchanged; this section records the new audit.

## Round 3: public outside cache wrapper check (2026-11-16)

A focused negative control reviewed `ref_resolver.normalize` (52:29) and
`ref_resolver.resolve_remote` (64:31). PyPy 3.11 / 7.3.20 decorates the
public outside function `urllib.parse.urlsplit` with a Python function
wrapper. The global outside-name rule preserves that public attribute
path. Both caller pairs already exist, so the check adds no edges and
removes none; the graph remains at 548 edges. Existing CPython callable
object outcomes remain. setup.py lists CPython and Python >=3.10; this
negative control does not assert explicit PyPy support. Even if PyPy is
admitted, it introduces no additional pair at these sites.

Review evidence: round-3 audit and effective reports (audit record `2026-11-15/pass-3/README.md`).

## Round 4: full source-first audit (2026-11-16)

A fresh source model covered all 11 runtime modules, 106 module/function
bodies and 1,951 inventory sites before baseline access. Comparison retained
all 548 pairs (314 package, 234 outside) and all 917 site-target relations.
The 771 ledger entries and 1,180 omitted implicit sites agree with that model.
The 159-site default rejection, 25 rejection lines, six value sites and one
rejected trace pair remain supported. No graph, added-edge or rejected-edge
bytes change. Target code, generated code, tests and dependencies were never
executed or imported.

The release admits CPython >=3.10 with no declared upper bound. No current
alternative interpreter support was found; the prior PyPy negative control
is not admission evidence. The normal/-O/-OO union is a working preference
after an unanswered optional question. Assertions at generator.py:233,274
check package-generated data prefixes; removing them or docstrings produces
no additional target. The global declared-Python2 rule remains unchanged and
is inapplicable to this release.

One ledger note is clarified at generator.py:429:39: regex.flags is numeric,
while the local flags argument is a string. This changes no target. Source,
pair, site, body and default/exclusion coverage is retained in
/tmp/pycg-macro-audit-pass4/fastjsonschema-agent. Structural and origin gates
are reserved for the root acceptance step; this record does not claim them.
