# jmespath 1.1.0: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

First audit: `jmespath.ledger`, `jmespath.json`, `jmespath.md` and
`jmespath.rejected.json` at commit 77e7a29. Final re-check: the same files
at commit 17e5243 ("jmespath ground truth after audit"), against the final
scope rules A to C of the lead. The auditor read the 8 modules of
`jmespath/` and Python semantics only. The auditor did not run the package or
its tests, and did not use PyCG or any other static analysis tool. The
auditor used the trace only as a lower bound.

## Final result

| ID | Kind | Status | Confidence |
|---|---|---|---|
| R1 | wrong edge: `Visitor.visit -> TreeInterpreter.default_visit` | stands; **fixed** in 17e5243 | certain |
| D1 | stale text: the "Scope rule" section of `jmespath.md` states rules that A and C replace | stands; **open** (text only, no edge changes) | certain |
| F1, F2, R2, R3a, R3b, R4 | see "Withdrawn findings" | withdrawn | - |

Final count: **2 findings stand**. One is an edge finding (R1, already
applied). One is a text finding (D1, open). There are no missing edges. The
committed graph (430 edges, 310 inside the package, 120 to 50 outside
callees) agrees with rules A to C at every site.

## Rules applied (final form, all five projects)

- **A. Edges are per function.** The edges of a function are the calls
  that its code can make when it runs. Every function keeps the out-edges
  of its body: public or private, tested or not, reachable from the API or
  not. A trace edge is rejected only when its callee is a value that a
  client supplied.
- **B. Values restrict edges.**
  1. Receivers: `self` in a method of class C is an instance of C, or of a
     package subclass that inherits the method. Only instances that the
     package or a client can create count. A client can create instances
     of public classes; the package alone creates instances of a private
     class. A class with `abc` abstract methods is never a receiver.
  2. Arguments and stored values: client objects, or values that the
     package provides for that parameter's role.
  3. Two kinds of value are not considered: an arbitrary package object
     passed where any object is accepted, and a value that the package
     never produces for that role (a hand-built AST with a node type that
     the parser never makes).
  4. When the annotation or documentation of a parameter fixes a concrete
     outside type, a method call on the parameter is an edge to that
     type's method. An unannotated parameter or a bare callable holds a
     client callback.
- **C. "Public" is mechanical.** A name is public when no component of the
  qualified name starts with an underscore (dunder names excepted), unless
  a docstring or the documentation marks it private.

## Findings that stand

| ID | Kind | Site or edge | Evidence | Confidence |
|---|---|---|---|---|
| R1 | wrong edge (fixed in 17e5243) | `jmespath.visitor` 94:22 `method(node, *args, **kwargs)` -> `jmespath.visitor.TreeInterpreter.default_visit` | On a `TreeInterpreter`, `getattr(self, 'visit_' + node['type'], self.default_visit)` (`visitor.py:91`) returns the default only for a node type without a `visit_` method. The parser builds only the 22 node types of `ast.py`, and `visitor.py` has a `visit_` method for each. A hand-built node is excluded by B3. The committed ledger has the matching note at 94:22. | certain |
| D1 | stale text (no edge effect) | `jmespath.md`, section "Scope rule" | Its lead sentence "An edge needs an execution of the package through its API" contradicts A: edges are per function, whatever reaches the function. Its rule 1 ("The API is the documented public interface. Clients do not call private entry points") contradicts C: public is mechanical. The ledger and graph already follow A and C. The private `_render_dot_file`, `GraphvizVisitor` and `purge` keep their body edges. `TreeInterpreter.default_visit -> <builtin>.NotImplementedError` stays, and `Visitor.default_visit` is kept as a callee because `Visitor` is a public class. Only the stated rule is out of date. The ledger notes at 94:22, 193:30 and 534:20 cite "rule 3"; that rule survives as B3. | certain |

## Withdrawn findings and why

| ID | Was | Why withdrawn |
|---|---|---|
| F1 | Judgement 1 of the first `jmespath.md` counted a hand-built AST as API use. Judgement 2 called it misuse. | Settled by B3. The writer applied it in 17e5243: R1 is removed, and the rejection of the `ParsedResult.__repr__` self-edge at `parser.py` 534:20 stands. |
| F2 | `json.dumps(arg, default=str)` at `functions.py:193` would call a package `__str__`/`__repr__` for a package object in the client's data. | B3: a package object passed where any object is accepted is not considered. The note at 193:30 is right. |
| R2 | `Visitor.visit -> Visitor.default_visit` is wrong, because the README does not document `Visitor`. | C and B1: `Visitor` is public and not abstract by `abc`, so a client can create a plain `Visitor`. With a parser-made AST, `Visitor().visit(jmespath.compile('a').parsed)` reaches `Visitor.default_visit` (a plain `Visitor` has no `visit_*` attribute). The edge is right. |
| R3a | `TreeInterpreter.default_visit` and `Visitor.default_visit -> <builtin>.NotImplementedError` are wrong, because no API execution runs these methods. | A: every function keeps the out-edges of its body. |
| R3b | The 10 out-edges of `_render_dot_file` and `GraphvizVisitor` are wrong, because only the tests call the private `_render_dot_file`. | A. Under C, `GraphvizVisitor` is public anyway. |
| R4 | `Parser.purge -> <builtin>.dict.clear` is doubtful, because `purge` is undocumented. | A, and C: `purge` is public. |

## Final re-check of the committed ledger and graph (17e5243)

**Changes since the audited version.** `git diff 40a7cee 17e5243` shows
three changes to the ledger and graph:

- The graph loses one edge, R1. The 94:22 entry loses the callee and gains
  a note.
- New notes at 193:30 and 534:20 cite the scope rule.
- No other site changed.

`check.py jmespath` reports no errors: 430 edges, 424 confirmed by the
trace, 4 rejected.

**Rule A: no body edge was dropped.**

- Every node with a call site has a non-empty edge list.
- Only two explicit sites have no callee, and both are correct for the
  same reason. `lexer.Lexer()` (`parser.py:119`) and `functions.Functions()`
  (`visitor.py:123`) run `object.__init__`, which gives no edge.
- The functions that no package code calls keep their body edges:
  - `TreeInterpreter.default_visit` and `Visitor.default_visit` ->
    `<builtin>.NotImplementedError`.
  - `ParsedResult._render_dot_file` -> `GraphvizVisitor.__init__` and
    `GraphvizVisitor.visit`.
  - The 8 out-edges of the three `GraphvizVisitor` methods.
  - `Parser.purge` -> `<builtin>.dict.clear`.
  - `ParsedResult.__repr__` -> `<builtin>.repr`.
- The only removed edge is R1. A value restriction (B3) removes it, not
  reachability.

**Rule B1: receivers of the visitor classes.** The four classes are
`Visitor`, `TreeInterpreter` and `GraphvizVisitor` (public; clients can
create them) and `_Expression` (private; the package creates it only at
`visitor.py:164`).

| Method | Receivers | Self-call sites and callees | Verdict |
|---|---|---|---|
| `Visitor.__init__` | `Visitor`, and `TreeInterpreter`/`GraphvizVisitor` through `super` | none | right |
| `Visitor.visit` | plain `Visitor`; `TreeInterpreter` (inherits). Not `GraphvizVisitor` (overrides `visit`, `visitor.py:313`) | 89:40 `<builtin>.dict.get`; 91:29 `<builtin>.getattr` (the default is not called there); 94:22: 22 `TreeInterpreter.visit_*` for a `TreeInterpreter`, `Visitor.default_visit` for a plain `Visitor` | right (after R1) |
| `Visitor.default_visit` | `Visitor`; `GraphvizVisitor` inherits it, but only a direct call reaches it there | 97:34 `<builtin>.NotImplementedError` | right |
| `TreeInterpreter.__init__` | `TreeInterpreter` | `super` -> `Visitor.__init__`; `Options()` -> `Options.__init__`; `Functions()` gives no edge | right |
| `TreeInterpreter.visit_*`, `_is_true`, `_is_false`, `default_visit` | `TreeInterpreter` (no package subclass) | 24 `self.visit` sites -> `Visitor.visit`, rejecting `GraphvizVisitor.visit` and `_Expression.visit` (not in the MRO); `self._is_true`/`_is_false` -> `TreeInterpreter`; `self._functions.call_function` -> `Functions.call_function`; `self._dict_cls()` -> `<builtin>.dict` | right |
| `GraphvizVisitor.__init__`, `.visit`, `._visit` | `GraphvizVisitor` (no package subclass) | `super` -> `Visitor.__init__`; `self._visit` -> `GraphvizVisitor._visit`; `self._lines.append` -> `<builtin>.list.append` | right |
| `_Expression.visit` | `_Expression`, created only at `visitor.py:164` with `self` as `interpreter` | 80:38 `self.interpreter.visit` -> `Visitor.visit` | right |
| outside callers | - | `parser.py` 516:35 `interpreter.visit` -> `Visitor.visit`; 530:34 `renderer.visit` -> `GraphvizVisitor.visit`; `functions.py` 252:39, 320:30, 351:34 `expref.visit` -> `_Expression.visit` (an `expref` argument passed the type-name check; a client object of a class named `_Expression` is a client callback under B4) | right |

**Rules B2 to B4: values at method calls on parameters.** The auditor
checked every method call on a parameter or stored value. For each one,
some value that the package itself produces reaches the site. So the
listed builtin method is an edge by the package's own values, and B4 is
not needed to justify it.

- `token_type.upper()`: token types are strings.
- `t.split`: `@signature` type names.
- `signature[-1].get`: `@signature` dicts.
- `value.get`, `base.values()`, `arg.keys()`, `arg.values()`: dicts that
  the package creates through a multi-select hash with the default
  `dict_cls`, or through `merge`.
- `search.endswith`/`startswith`, `separator.join`: strings.
- `node.get`: parser AST dicts.
- `name.startswith`: names from `inspect.getmembers`.

The `dict_cls` and `custom_functions` options hold client values: the
client's class and the client's `Functions` subclass. Their own methods are
client callbacks (B4). The package defaults `<builtin>.dict` and
`Functions.call_function` are edges.

**Rejected trace edges.** The 4 `collections.OrderedDict` entries reject
callees that the client supplied: the `dict_cls` class, and the methods of
`OrderedDict` objects that come from that class or from the tests'
`object_pairs_hook`. This is right under A and B4: `dict_cls` is an
unannotated parameter that holds a bare callable. There is one tension in
the wording (open question 1).

## Blind sample (step 1)

- **Sample.** The skeleton has 496 sites. The auditor numbered them in file
  order and drew 60 with `random.Random(20261111).sample(range(1, 497), 60)`.
  The numbers were 22 27 38 39 42 45 57 60 68 73 81 86 93 101 102 104 122
  129 138 140 148 156 161 162 177 186 218 228 235 239 240 242 243 245 249
  285 299 314 321 325 326 334 348 349 352 360 367 371 376 386 387 411 428
  442 446 452 453 454 461 496. Three of the 22 sites with no candidates by
  name were in the sample; the other 19 were added. Total: 79 sites (75
  `call`, 4 `decorator`). By module: parser 39, functions 24, visitor 12,
  lexer 3, exceptions 1. The skeleton has no implicit site except the
  `class` site at `functions.py:67`, so the sample has none.
- **Method.** The auditor wrote the callees of all 79 sites from the source
  (scratch file, before the ledger was opened), then compared them site by
  site with the ledger.
- **Writer against auditor.** 0 sites with a difference: 0/60 in the
  random sample, 0/79 overall. All four dispatch tables matched exactly
  (nud 13, led 14, visitor 24, `FUNCTION_TABLE` 26), and so did both
  comparator branches (2 and 4 callees).
- **Both against the final rules.** 1 site of 79 was wrong in both the
  writer's first ledger and the auditor's blind set: site 426,
  `visitor.py` 94:22 (R1). It is not in the random 60, so the rate there is
  0/60. Class of the error: a wrong edge, now fixed.
- **Caveat.** Most sampled sites are simple calls on `self` or on
  `jmespath.ast`. The sample cannot test implicit calls, because there are
  almost none. Steps 2 to 5 cover the harder cases.

## Coverage by step

1. **Blind re-derivation:** 79 sites (see above).
2. **Dispatch completeness:** 7 tables, all complete. After R1, every
   callee can be reached.
   - Counts of the definitions: 12 `def _token_nud_`, 14 `def _token_led_`,
     22 `def visit_`, 26 `def _func_` and 26 `@signature(` decorators.
   - Parser tables: every token type that `Lexer.tokenize` yields has a key
     in `BINDING_POWER`, so line 137 raises no `KeyError`. Every led method
     has a token type with a binding power above 0. star, not and lbrace go
     to `_error_led_token`. Every type without a nud method goes to
     `_error_nud_token`, for example dot and eof.
   - Visitor table: the 22 node types of `ast.py` map one-to-one to the
     `visit_` methods (`current_node` builds type `current`).
   - `COMPARATOR_FUNC` has 6 keys: eq and ne at 144:35, the other four at
     158:35.
   - `FUNCTION_TABLE` holds the 26 decorated `_func_*` methods.
     `inspect.getmembers` does not see the methods of the metaclass.
   - The key function `keyfunc` is a callee at all three sites: `sorted`,
     `min` and `max` (327:27, 335:23, 345:23).
3. **Callers of every function:** 12 functions and the 8 modules have no
   caller in the package.
   - The 12: `compile`, `search`, `Parser.purge`,
     `ParsedResult._render_dot_file`, `ParsedResult.__repr__`, the six
     exception `__str__` methods, and (after R1)
     `TreeInterpreter.default_visit`.
   - The auditor searched the source with `rg` for each name, for
     `getattr`/`setattr`/`__dict__`/`vars`, and for `str(` and `repr(`. No
     use was found that the ledger misses.
   - Under A, each of the 12 keeps its body edges.
4. **Stored callables:** 10 stores, each followed to its call:
   - `COMPARATOR_FUNC` (144:35 and 158:35).
   - `MAP_TYPE`, through `_dict_cls` (233:35).
   - `FUNCTION_TABLE` (81:24).
   - `_method_cache` and the `getattr` default `self.default_visit`
     (94:22).
   - The `getattr` default `self._error_nud_token` (135:28).
   - `keyfunc`, which `_create_key_func` returns (the three key sites).
   - `_record_signature`, which `signature` returns (26 decorator sites).
   - `custom_functions` and `Functions()`, kept in `_functions` (171:45).
   - `self.tokenizer`, a generator (edge at 119:48).
   - `_Expression.interpreter` (80:38).

   The default arguments hold no callables.
5. **Implicit calls:** the package defines 12 class `__init__` methods, the
   metaclass `FunctionRegistry.__init__`, 6 `__str__` and 1 `__repr__`.
   - It defines no property, `__eq__`, `__hash__`, `__bool__`, `__len__`,
     `__iter__`, `__contains__`, `__getattr__`, `__call__`, `__get__`,
     `__set_name__` or `__init_subclass__`. So truth tests, `in`, `==`,
     iteration and attribute loads have no package candidates.
   - The ledger has the metaclass hook (`functions.py:67` ->
     `FunctionRegistry.__init__`).
   - `str(e)` at `lexer.py:187` is decided.
   - The auditor read all 23 `%` formatting sites (exceptions 6, parser 6,
     lexer 5, visitor 5, functions 1). With the values that rule B allows,
     none formats an object whose class has a package `__str__` or
     `__repr__`. The objects that reach `%s` are strings, numbers, JSON
     values and `_Expression`, which inherits `object.__repr__`.
6. **Rejections and notes:** all 54 `reject` lines (7 `reject *`) and all
   98 notes of the committed ledger. Each reason is true in the source and
   agrees with rules A to C. The scope text in `jmespath.md` is stale (D1).
7. **Outside callees:** the auditor drew 40 of the 120 outside edges with
   the same seed and checked each for existence and naming. All 40 exist and
   are correctly named. The auditor also read the entry of every one of the
   461 explicit sites and found no missing builtin or library callee.
   - `<builtin>.ValueError.__init__` is named through the class that the
     code names. The trace's canonical `<builtin>.BaseException.__init__`
     lists it as an alias.
   - Other names checked: `<builtin>.type.__init__`; `operator.le` (not
     `_operator.le`); `json.loads` through `from json import loads`;
     `<builtin>.dict` for the default `dict_cls`.
8. **Rejected trace edges:** 4 entries, all `collections.OrderedDict`.
   - `OrderedDict` appears in the package only as strings in
     `TYPES_MAP`/`REVERSE_TYPES_MAP` (`functions.py:20, 30`) and in a
     comment (`visitor.py:68`). The package never creates one.
   - All 4 callees are client-supplied values (see the final re-check).
   - The trace also drops 3 client callbacks: the tests' own `_func_*`
     methods (`tests/test_custom_functions.py:9`,
     `tests/test_search.py:22, 28`), which `call_function` calls at 81:24.
     Dropping them is correct.
9. **Checker:** `check.py jmespath` at 17e5243 reports no errors. In the
   `--report` (run at 77e7a29; 17e5243 changes no site position or
   candidate):
   - 0 undecided sites.
   - All 22 sites with no candidates by name have notes.
   - 0 trace edges are unaccounted.
   - 3 callees beyond the candidates: `Functions._create_key_func.keyfunc`
     at `sorted`, `min` and `max`. All 3 are correct: the closure is a
     variable, so no name proposes it.

## Open questions about conventions

1. **"The documentation offers them" (B2) against B4 and the macro README.**
   `README.rst:85-101` of jmespath offers `collections.OrderedDict` as
   `dict_cls`. Read alone, B2's phrase "the documentation offers them"
   would make `OrderedDict` a value that the package provides for that
   role. Its 4 trace edges would then be graph edges, not rejections. B4
   ("a bare callable holds a client callback") and the "Client callbacks"
   example of `macro-benchmark/README.md`, which uses exactly this case,
   say the opposite. The auditor follows B4 and the README: the writer's
   rejections stand. A rule text that restricts "offers" to values that
   the package itself defines would remove the tension.
2. **The macro README still states the old edge rule.** Its "Edges" bullet
   says "An execution is any use of the package through its API". That is
   the wording that rule A replaces. This is the same staleness as D1, but
   in a file that the jmespath writer does not own.
3. **`%` formatting has no `__str__` candidates.** `sites.py` gives a `%`
   site the candidates `__mod__` and `__rmod__` only. `'%s' % x` calls
   `x.__str__`, and `%r` calls `__repr__`. A ledger therefore cannot record
   such an edge. jmespath has no such edge under rule B (step 5). Other
   projects can have real cases.


## Round 4 source audit (2026-11-16)

Reviewed all 430 baseline pairs and all 1,421 inventoried sites against the
pinned source under the current global rules. No additional false positive,
missed edge or metadata correction was justified. The graph retains 190 nodes,
310 package pairs and 120 outside pairs.

The review includes 519 ledger entries, 573 site/target relations, 321 expanded
candidate rejections, one explicit exclusion, no default rejections and 54
empty-adjacency bodies. A fresh auditor and root source models were frozen before
baseline comparison. Root retains prior-round knowledge; the auditor disclosed
exposure to global README examples. Four OrderedDict method alternatives remain
excluded as client data or client factory output under B4/B5.

The structural and origin checks passed. All six baseline files matched the
reviewed stage before this appendix. The existing six reading-only pairs are
not new round-4 additions. Static source reasoning and operation-family review
cover omissions; pair-set equality alone is not evidence of completeness.
No target, dependency, test or generated code was executed. The complete round-4
audit retains the source models, per-pair/site decisions, root acceptance,
verification logs and separate added-edge register.
