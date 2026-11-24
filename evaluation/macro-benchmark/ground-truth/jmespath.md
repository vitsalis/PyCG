# jmespath 1.1.0: judgements of the ground truth

Global-rule audit (2026-11-15): 0 removed edges, 0 added
edges; 430 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

The ledger `jmespath.ledger` was written by hand from the source of
`jmespath/` (8 modules) and from Python semantics. No static analysis tool
was used. The trace `../dynamic/jmespath.json` served only as a checklist
after the ledger was complete.

## Statistics

| Item | Count |
|---|---|
| Call sites with an entry | 519 (461 `call`, 34 `decorator`, 1 `class`, 23 `op`) |
| Sites with no candidates by name (value sites) | 22 |
| Callee lines in the ledger | 573 |
| Rejection lines | 77 (30 `reject *`, 78 candidates rejected by name) |
| Exclusions | 1 |
| Default rejections | 0 |
| Notes | 97 |
| Nodes of the graph | 190 (8 modules, 182 functions, 1 of them a lambda) |
| Edges of the graph | 430: 310 inside the package, 120 to 50 callees outside it |
| Edges of the trace | 428: 424 in the graph, 4 in `jmespath.rejected.json` |
| Graph edges that the trace confirms | 424 of 430 (98.6 %) |
| Graph edges only from reading | 6 (listed below) |

The 6 edges that no test makes:

| Edge | Why no test makes it |
|---|---|
| `Functions._func_keys -> <builtin>.dict.keys` | the compliance tests load their data as `OrderedDict` |
| `Functions._func_values -> <builtin>.dict.values` | same |
| `ParsedResult.__repr__ -> <builtin>.repr` | no test calls `repr()` on a `ParsedResult` |
| `Visitor.visit -> Visitor.default_visit` | no test uses a plain `Visitor` |
| `Visitor.default_visit -> <builtin>.NotImplementedError` | follows from the row above |
| `TreeInterpreter.default_visit -> <builtin>.NotImplementedError` | nothing calls `TreeInterpreter.default_visit` (rule B3); the function keeps the edge of its body (rule A) |

## Scope and version judgements

- The package supports Python 3.9 and later (`setup.py:19`). The source has
  no `if TYPE_CHECKING:` block, no branch on the Python version and no
  optional import. `compat.py` imports `sys` and `zip_longest` and does not
  use them. No module has an annotation, so annotations add no site.
- Every module of `jmespath/` is in scope. `bin/jp.py`, the tests and
  `extra/` are not.

## Scope rules

`../README.md` ("Scope rules") is the authority. In short:

- **A.** Edges belong to a function's body. A function keeps its out-edges
  whether or not anything calls it, and whether it is public or private.
  Argument and receiver limits still apply. Global rule A also excludes
  opaque client values, implicit outside calls, private-test inputs outside
  B1/B2/C, and trace naming artefacts.
- **B1.** In a method of class `C`, `self` is an instance of `C` or of a
  package subclass that inherits the method (or calls it explicitly), and
  only an instance that the package or a client can create. A client
  creates instances of public classes; a private class has only the
  instances that the package creates.
- **B2.** Public parameters hold client objects, the package's defaults,
  and package values admitted for that role by annotations, documentation,
  package code, tests or documented examples. Private parameters use the
  package's own calls; a private function with no package caller uses the
  public-parameter fallback. An outside client value remains opaque unless
  B4 fixes its concrete type. A client callable stays opaque even when the
  documentation names it.
- **B3.** An arbitrary package object passed where any object is accepted,
  and a value that the package never produces for that role, are not
  considered.
- **B4.** When the annotation or documentation fixes a concrete outside type
  (`dict`, `str`), a method call on the value is an edge to that type's
  method.
- **B5.** A client object is opaque: a method call on it has no outside
  callee, and what it does when the package uses it is client behaviour.
- **C.** A class or function is public if a path with no component that
  starts with an underscore reaches it; dunder names are exempt. A docstring
  or documentation that marks it private overrides the spelling.

How they apply to jmespath:

- **A.** `TreeInterpreter.default_visit` has no caller but keeps its edge to
  `<builtin>.NotImplementedError`. The private helper
  `ParsedResult._render_dot_file` keeps its edges. The only rejected trace
  edges are the four `collections.OrderedDict` edges, all client values
  (see below).
- **B1 and C.** `Visitor`, `TreeInterpreter`, `GraphvizVisitor`, `Options`,
  `Parser`, `ParsedResult`, `Lexer`, `Functions` and the exception classes
  are public; `_Expression` is private. A plain `Visitor` is therefore a
  receiver of `Visitor.visit`. It has no `visit_` method, so
  `Visitor.default_visit` is a callee of the dispatch at `visitor.py:94`.
  An `_Expression` exists only where the package creates it
  (`visitor.py:164`, with the running `TreeInterpreter`). So
  `expref.visit(...)` in `functions.py` reaches only `_Expression.visit`,
  and `_Expression.visit` reaches only `Visitor.visit`. In
  `TreeInterpreter`, `self.visit` is `Visitor.visit`.
- **B2.** `Options(dict_cls=...)`: the package default `dict`
  (`TreeInterpreter.MAP_TYPE`) is a callee at `visitor.py:233`. The
  `collections.OrderedDict` of the tests is a client callback.
  `Options(custom_functions=...)`: the package's own `functions.Functions()`
  gives `Functions.call_function` at `visitor.py:171`. The AST that
  `ParsedResult`, `TreeInterpreter.visit` and `GraphvizVisitor.visit` get
  is the one that the parser builds. The arguments of the exception
  classes are the strings, ints and token values that the package passes.
- **B3.**
  - A hand-built AST with a node type that the parser never makes is not
    considered. On a `TreeInterpreter`, the `getattr` default at
    `visitor.py:91` runs only for such a node type, so the ledger excludes
    `TreeInterpreter.default_visit` at `visitor.py:94`.
  - `repr(self.parsed)` (`parser.py:534`) gets no
    `ParsedResult.__repr__` self-edge: the parser never puts a
    `ParsedResult` into an AST.
  - A package exception or `ParsedResult` inside the client's data is not
    considered. So `json.dumps(arg, ..., default=str)` (`functions.py:193`)
    calls back no package `__str__` or `__repr__`: the package only produces
    JSON values from `json.loads` (`lexer.py:163-184`) and `_Expression`
    objects, which have neither method. The same holds at the 23 `%`
    formatting sites, which `sites.py` gives the six exception `__str__`
    methods and `ParsedResult.__repr__` as candidates. Their operands are
    strings, ints, lists of strings, token values (a string, an int or a
    JSON value), node values, and the argument values of JMESPath
    functions (JSON values or `_Expression` objects). Each of these sites
    rejects all candidates.
- **B4.** The package has no annotations. Its documented JSON roles and
  package-created values supply dict and str receivers: `arg.keys()` and
  `arg.values()` get the dict methods, and `endswith`, `startswith` and
  `join` get the str methods. `REVERSE_TYPES_MAP` (`functions.py:27-35`)
  validates type-name strings, not concrete class identity. Its
  `OrderedDict` entry does not establish a collections.OrderedDict receiver.
  README.rst names OrderedDict only for the client `dict_cls` factory
  (lines 85-101); the tests' OrderedDict data remain client objects.
- **B5.** The data that a client passes are client values. But the `dict`
  methods at `visitor.py:136` (`value.get`) and `visitor.py:286`
  (`base.values()`) also run on dicts that the package creates: a
  multi-select hash with the default `dict_cls` (`visitor.py:233`) and the
  result of `merge()` (`functions.py:264`). The `dict` callees therefore
  hold without client data. The `OrderedDict` methods that the tests reach
  are rejected. A client's `custom_functions` object is opaque too: at
  `visitor.py:171` the ledger lists only `Functions.call_function`, which
  the package's own default object gives.

## Judgements

1. **Inherited `__init__` of `ValueError`.** `JMESPathError` derives from
   `ValueError` (`exceptions.py:4`) and defines no `__init__`. The
   `super().__init__` calls at `exceptions.py:13` and `exceptions.py:117`
   and the instantiation of `UnknownFunctionError` (`functions.py:76`) get
   the callee `<builtin>.ValueError.__init__`, named through the nearest
   base outside the package (README, "Callees outside the package"). The
   trace names it `<builtin>.BaseException.__init__`; the checker matches
   the two by alias.
2. **Classes without `__init__`.** `lexer.Lexer()` (`parser.py:119`) and
   `functions.Functions()` (`visitor.py:123`) run `object.__init__`: no
   edge. `FunctionRegistry` (the metaclass of `Functions`) defines no
   `__call__`. Each site has a note.
3. **Metaclass at class definition.** `class Functions(metaclass=FunctionRegistry)`
   (`functions.py:67`) calls `FunctionRegistry.__init__`; this edge belongs
   to the module `jmespath.functions`. A client subclass of `Functions`
   also runs it, from client code.
4. **Library code that calls a builtin or library function back.**
   `json.dumps(arg, ..., default=str)` (`functions.py:193`) calls the builtin
   `str` for an object that it cannot encode (an `_Expression`, through
   `to_string(&foo)`), and `inspect.getmembers(cls, predicate=inspect.isfunction)`
   (`compat.py:18`) calls `inspect.isfunction`. These are not edges: the
   micro-benchmark counts a callee outside the package only for a call
   expression of the package (README, "Callees outside the package"). No
   package function is called back at either site: the only package objects
   that reach `json.dumps` are `_Expression` objects, which have no
   `__str__` or `__repr__` (rule B3).
5. **`dict_cls`.** `self._dict_cls()` (`visitor.py:233`) gets the package
   default `<builtin>.dict` (`TreeInterpreter.MAP_TYPE`, `visitor.py:110`).
   A class that the client passes as `Options(dict_cls=...)` is a client
   callback (rule B2). The tests pass `collections.OrderedDict`; those
   trace edges are in `jmespath.rejected.json`.
6. **Methods of `dict` on data.** `arg.keys()`, `arg.values()`
   (`functions.py:288`, `292`), `base.values()` (`visitor.py:286`) and
   `value.get()` (`visitor.py:136`) get the `dict` methods. The package
   creates only plain dicts (multi-select hash with the default `dict_cls`,
   `merge()`), and JSON data are dicts. The tests run these sites on
   `OrderedDict` objects that they create. Those client objects stay opaque
   under B4/B5. Inheriting `dict.get` does not change that reasoning: if an
   OrderedDict receiver were admitted as concrete, the global outside-name
   rule would name `collections.OrderedDict.get`.
7. **`custom_functions`.** `self._functions.call_function(...)`
   (`visitor.py:171`) calls `Functions.call_function`. The object is
   `functions.Functions()` or the client's `Options.custom_functions`; the
   documented use is a subclass of `Functions`, which inherits
   `call_function`. The client's own `_func_*` methods are client code
   (rule B5).
8. **Comparators.** `visit_comparator` calls `comparator_func` in two
   branches. The table `COMPARATOR_FUNC` (`visitor.py:101-108`) has six
   keys; any other key raises `KeyError` at `visitor.py:142`. The branch at
   `visitor.py:144` runs only for `eq` and `ne` (`_EQUALITY_OPS`): callees
   `_equals` and `TreeInterpreter.<lambda1>`. The branch at
   `visitor.py:158` runs for the other four: `operator.lt`, `operator.gt`,
   `operator.le`, `operator.ge`.
9. **`self._expression(...)` in the parser** (17 sites). `sites.py` flags
   them as values, because the lexer assigns an attribute `_expression`
   (`lexer.py:124`). That attribute is on a `Lexer`; `Parser` never assigns
   it, so the callee is the method `Parser._expression`. For the same
   reason, `list(self._expression)` and `len(self._expression)` in the
   lexer (`lexer.py:125`, `127`) reject the candidate `Parser._expression`.
10. **Generators.** `Lexer.tokenize` (called at `parser.py:119`) and
    `compat.get_methods` (called at `functions.py:55`) are generator
    functions. The edge goes to the caller of the function. The calls in
    their bodies belong to them, although `list(self.tokenizer)`
    (`parser.py:120`) and the `for` loop at `functions.py:55` run the bodies.
11. **Key functions.** `sorted`, `min` and `max` with `key=keyfunc`
    (`functions.py:327`, `335`, `345`) call back the closure
    `Functions._create_key_func.keyfunc`. It is a callee of each of the
    three sites.
12. **Exceptions with an exception argument.** `str(e)` at `lexer.py:187`
    gets only `<builtin>.str`: `e` is the `json.JSONDecodeError` from
    `json.loads` at `lexer.py:184`, not a package exception.

## String-built and table-driven dispatch sites

| Site | Expression | Callees | Size | How the set was derived |
|---|---|---|---|---|
| `parser.py:135:28` | `nud_function(left_token)` | 12 `Parser._token_nud_*` and `Parser._error_nud_token` | 13 | every `def _token_nud_` of `parser.py`; the default of the `getattr` at `parser.py:132` for every other token type that `Lexer.tokenize` yields |
| `parser.py:144:27` | `led(left)` | 14 `Parser._token_led_*` | 14 | every `def _token_led_` of `parser.py`; each one has a token type with a binding power above 0 (`BINDING_POWER`, `parser.py:36-67`); a missing handler goes to `_error_led_token` at `parser.py:141` instead |
| `visitor.py:94:22` | `method(node, *args, **kwargs)` | 22 `TreeInterpreter.visit_*` and `Visitor.default_visit` | 23 | every `def visit_` of `visitor.py`, one for each of the 22 node types of `jmespath/ast.py`; the default of the `getattr` at `visitor.py:91` for a plain `Visitor` (rules B1, C). `TreeInterpreter.default_visit` is excluded (rule B3). `GraphvizVisitor` overrides `visit` and has no `visit_*` |
| `functions.py:81:24` | `function(self, *resolved_args)` | 26 `Functions._func_*` | 26 | `FUNCTION_TABLE`, built by `FunctionRegistry._populate_function_table` (`functions.py:50-64`) from the `_func_*` methods with `@signature`: all 26 `_func_*` methods of `Functions` have it |
| `visitor.py:144:35` | `comparator_func(...)` (eq, ne) | `_equals`, `TreeInterpreter.<lambda1>` | 2 | `COMPARATOR_FUNC`, judgement 8 |
| `visitor.py:158:35` | `comparator_func(left, right)` | `operator.lt`, `.gt`, `.le`, `.ge` | 4 | `COMPARATOR_FUNC`, judgement 8 |
| `visitor.py:233:35` | `self._dict_cls()` | `<builtin>.dict` | 1 | `MAP_TYPE`, judgement 5 |

The two `getattr` calls with a method as default (`parser.py:132`,
`visitor.py:91`) do not call that method; their rejections say so.

## Functions that no site calls

| Function | Why |
|---|---|
| `jmespath.compile`, `jmespath.search` | public API |
| `jmespath.parser.Parser.purge` | public class method that clears the cache |
| `jmespath.parser.ParsedResult._render_dot_file` | debugging helper; its docstring (`parser.py:520-528`) says it is not public API; only the tests call it |
| `jmespath.parser.ParsedResult.__repr__` | `repr()` of a result, by the client; no package code calls `repr` or `str` on a `ParsedResult` (rule B3) |
| `__str__` of `ParseError`, `IncompleteExpressionError`, `LexerError`, `ArityError`, `VariadictArityError`, `JMESPathTypeError` | `str()` of an error, by the client or a traceback; no package code formats a package exception (rule B3) |
| `jmespath.visitor.TreeInterpreter.default_visit` | no package dispatch selects this fallback: the parser makes only node types with a handler (rule B3). Direct public calls remain admitted, and its own call of `<builtin>.NotImplementedError` stays in the graph (rule A) |

The 8 modules have no callers. No other function lacks a caller.

## Trace edges in `jmespath.rejected.json`

All four come from `collections.OrderedDict`, which the tests supply: as
`Options(dict_cls=OrderedDict)` (`tests/test_compliance.py:15`,
`tests/test_search.py:14`, `tests/test_parser.py:363`) and as the type of
the test data (`json.load(..., object_pairs_hook=OrderedDict)`,
`tests/test_compliance.py:52`). The package never creates an `OrderedDict`.

| Caller | Rejected callee |
|---|---|
| `TreeInterpreter.visit_multi_select_dict` | `collections.OrderedDict` |
| `TreeInterpreter.visit_value_projection` | `collections.OrderedDict.values` |
| `Functions._func_keys` | `collections.OrderedDict.keys` |
| `Functions._func_values` | `collections.OrderedDict.values` |

## Open questions

None. Rule B3 settles the former question on the fallback of the visitor
dispatch.
