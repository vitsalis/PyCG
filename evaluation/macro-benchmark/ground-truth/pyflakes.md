# pyflakes: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 1 edges and adds 1. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

The second complete audit found 0 false positives and 0 missed edges,
plus 1 correction to source-site attribution or explanations. See
the pass-2 report (audit record `2026-11-15/pass-2/pyflakes-review.json`).
The third complete audit adds two outside edges for PyPy cache wrappers and
removes none. It also clarifies the future-feature witness and site counts.
The fourth complete source audit retains all 644 edges and all 197 nodes.
It checks the complete source/site inventory under the normal, `-O` and `-OO`
working union. The current ledger and statistics below include all four audits.

Release 4.1.0 (commit `5324946`). Analysed source: `pyflakes/` without
`pyflakes/test/`: 8 modules, 189 functions (6 lambdas), 80 classes.
`setup.py:45` sets `python_requires='>=3.11'`, so the supported versions are
3.11 and later; the branches for 3.12, 3.13, 3.14 and 3.15 run.
CPython and PyPy are explicitly supported by the setup classifiers. NEWS
4.1.0 drops Python 3.10, overriding the stale README claim of 3.9+. There
is no declared upper bound. The fourth audit uses normal, `-O` and `-OO`
execution as a working union, not an affirmative user approval. Removing
assertions or docstrings adds no graph pair for the admitted value roles.

The ledger is `pyflakes.ledger`; the graph `pyflakes.json` is generated from
it. Five trace edges are rejected in `pyflakes.rejected.json` (an invalid
client-mutated AST and client
streams of the tests). The ledger was written from the source; the trace
came after and was used as a check only.

## Architecture, as the ledger uses it

- `Checker.__init__` (`checker.py:730`) walks the tree. `handleChildren`
  calls `handleNode` for each child; `handleNode` (`:1234`) asks
  `getNodeHandler` (`:1011`) for the handler of the node's class and calls
  it: `handler(node)` (`:1252`). The handler is the attribute of `Checker`
  named by the ast class name in upper case (`getattr(self, nodeType,
  self._unknown_handler)`, `:1016`). The class body binds most of these
  names to a few functions by aliases (`DELETE = WHILE = ... =
  handleChildren`, `:1327-2285`). See "Node dispatch".
- Function bodies, annotations, doctests and string annotations run later:
  `deferFunction` (`:759`) stores a callable, `_run_deferred` (`:770`) calls
  it (`handler()`, `:778`). See "Deferred functions".
- Names live in scopes. The scope classes (`Scope` and its subclasses,
  `:522-594`) are subclasses of `dict`, so their `get`, `items`, `values`,
  `pop` and `setdefault` are `<builtin>.dict` methods. `in_scope` (`:815`)
  makes a scope with `cls()`. The values of a scope are bindings
  (`Binding` and its subclasses, `:210-519`).
- A finding is a message: `report(messageClass, *args)` (`:890`) appends
  `messageClass(self.filename, *args)`. See "Message dispatch".
- Three methods are generators under `@contextlib.contextmanager`
  (`in_scope`, `_enter_annotation`, `_type_param_scope`). Two methods are
  wrapped by package decorators: `handleAnnotation` by `@in_annotation`
  (`:1316`) and `handleStringAnnotation` by `@in_string_annotation`
  (`:1288`). Two functions are wrapped by `@functools.cache`
  (`_custom_builtins`, `_doctest_parser`).

## Node dispatch (computed attribute names)

`nodeType` is a class name of the `ast` module, in upper case. This is a
computed attribute name, so the lead asked for each judgement here.

1. **The getattr runs no package code** (`checker.py:1016`). Every
   attribute of `Checker` with an upper-case name is a function; none is a
   property. The candidate `_unknown_handler` is rejected there: `getattr`
   only returns it as the default.
2. **The callees of `handler(node)`** (`checker.py:1252`) are the handler
   functions that the ast classes of Python 3.11 to 3.15 select. The site
   finder does not follow the class-body aliases, so the value site lists
   every function:

   | Handler function | Selected by the ast classes |
   |---|---|
   | `handleChildren` | Delete, While, With, withitem, AsyncWith, Expr, BoolOp, UnaryOp, Set, Attribute, Starred, Slice, keyword, FormattedValue, Interpolation (3.14+), Match, match_case, MatchClass, MatchOr, MatchSequence, MatchSingleton, MatchValue |
   | `ignore` | Pass, Load, Store, Del, the boolean, binary, unary and comparison operators |
   | `FOR` | For, AsyncFor, comprehension |
   | `IF` | If, IfExp |
   | `GLOBAL` | Global, Nonlocal |
   | `GENERATOREXP` | GeneratorExp, ListComp, SetComp, DictComp |
   | `CONTINUE` | Continue, Break |
   | `YIELD` | Yield, Await, YieldFrom |
   | `FUNCTIONDEF` | FunctionDef, AsyncFunctionDef |
   | `ASSIGN` | Assign, NamedExpr |
   | `TUPLE` | Tuple, List |
   | `TRY` | Try, TryStar |
   | `_match_target` | MatchAs, MatchMapping, MatchStar |
   | `handleNodeStore` | ParamSpec, TypeVarTuple (3.12+) |
   | `TYPEALIAS`, `TYPEVAR` | TypeAlias, TypeVar (3.12+) |
   | `TEMPLATESTR` | TemplateStr (3.14+) |
   | one class each | `SUBSCRIPT`, `CALL`, `BINOP`, `CONSTANT`, `RAISE`, `JOINEDSTR`, `DICT`, `ASSERT`, `NAME`, `RETURN`, `LAMBDA`, `ARGUMENTS`, `ARG`, `CLASSDEF`, `AUGASSIGN`, `ANNASSIGN`, `IMPORT`, `IMPORTFROM`, `EXCEPTHANDLER`, `COMPARE` |

   The aliases `NAMECONSTANT`, `INDEX`, `EXTSLICE`, `AUGLOAD`, `AUGSTORE`
   and `PARAM` name classes that the parser of 3.11 and later no longer
   makes; their functions are reached through other classes anyway. No
   handler call reaches `Module` and the other root classes (the checker
   calls `handleChildren` on the root, never `handleNode`), nor `alias`
   (`IMPORT` and `IMPORTFROM` read the names themselves). The trace has all
   these edges except `_unknown_handler`.
3. **`_unknown_handler` is a callee of `handler(node)`** (global rule B3). The parser makes `TypeIgnore` nodes, in `Module.type_ignores`,
   when the client parses with `ast.parse(..., type_comments=True)` and the
   source has a `# type: ignore` comment. `Checker` has no `TYPEIGNORE`, so
   `handleChildren(tree)` on the module gives such a node to
   `_unknown_handler`. The tree is a client object (`api.check` parses
   without the flag). B3 leaves out a hand-built tree with a node type that
   the parser never makes; this node type the parser makes. Rule B3
   decides one edge, `handleNode -> _unknown_handler`; the four edges of
   its body stay by rule A in any case. The function has `# pragma: no
   cover`, and the trace does not have it.
4. **Handlers of a client subclass** (flake8 subclasses `Checker`) are
   client code. `self` in a `Checker` method is a `Checker` (B1).

## Deferred functions

`handler()` at `checker.py:778` calls what `deferFunction` stored. The
package stores five callables:

| Stored at | Callable | Callee at 778 |
|---|---|---|
| `:1314` | the lambda of `handle_annotation_always_deferred` | `Checker.handle_annotation_always_deferred.<lambda1>` |
| `:1740` | `functools.partial(self.handleStringAnnotation, ...)` | `functools.partial.__call__`, which calls back the bound wrapper `in_string_annotation.in_annotation_func` |
| `:2023` | `runFunction` of `LAMBDA` | `Checker.LAMBDA.runFunction` |
| `:1978` | the lambda of `FUNCTIONDEF` | `Checker.FUNCTIONDEF.<lambda1>` |
| `:2051` | the lambda of `CLASSDEF` | `Checker.CLASSDEF.<lambda1>` |

The candidate `api._exitOnSignal.handler` (same name) is rejected.
`deferFunction` is public; a callable of the client is client code. The
storing sites (`:1314`, `:1740`, `:1978`, `:2023`, `:2051`) reject the
stored callable: they do not call it. The trace has the six callees.

## Message dispatch

`messageClass(self.filename, *args, **kwargs)` at `checker.py:891`. The
checker passes each of the 50 subclasses of `Message` to `report` at least
once (checked with a scan of `messages.X` in `checker.py`). 29 of them
define `__init__`; the 21 others inherit `Message.__init__`. So the site
has 30 callees. Four classes are passed only in version branches:
`EagerUseOfLazyImport` and the two lazy-import messages (3.15), and
`TStringMissingPlaceholders` (3.14+, through `TEMPLATESTR`).
`FutureFeatureNotDefined` is not version-guarded. CPython 3.14+ rejects an
unknown leading future import, but `pass` followed by
`from __future__ import invented` reaches this report: the leading-future
scan stops at `pass`, and AST preprocessing leaves the later import.
The trace (3.14) has 27 of the 30 edges. Two absent constructors are
3.15-only; the third is `FutureFeatureNotDefined.__init__`. Each
`__init__` calls `Message.__init__` explicitly (29 sites, `reject *`).

## Decorated methods and library wrappers

- `self.handleAnnotation(...)` (`:2011`, `:2069`) calls the wrapper that
  `@in_annotation` made: `in_annotation.in_annotation_func`. The candidate
  `Checker.handleAnnotation` is rejected there; the wrapper calls it at
  `func(self, ...)` (`:699`). That site also calls `Checker.handleNode`,
  because `handle_annotation_always_deferred` wraps it with
  `in_annotation(Checker.handleNode)` (`:1313`) and its lambda calls the
  wrapper (`:1314`). In `in_string_annotation.in_annotation_func`, `func`
  is only `handleStringAnnotation` (`:707`).
- A call of a `@contextlib.contextmanager` method has two callees:
  `contextlib.contextmanager.helper` and the generator function (README:
  sqlparse `utils.indent`). The tracer does not see the generator function
  started by library code, so 15 such edges come from reading only.
- `_custom_builtins()` (`:739`) and `_doctest_parser()` (`:1259`) call
  `functools._lru_cache_wrapper.__call__` on CPython, or
  `functools._lru_cache_wrapper.wrapper` on supported PyPy. Both wrappers
  call the package function on a cache miss. Pyflakes declares PyPy support
  in `setup.py` and tests `pypy3` in `tox.ini`. PyPy 7.3.20 implements
  Python 3.11.13; its `functools.cache` returns the nested Python wrapper
  because the release has no `_functools` accelerator. `hidden_applevel`
  returns that same function after marking its code. The closure keeps its
  defining name under the global naming rules. `_doctest_parser()(docstring)`
  calls `doctest.DocTestParser.get_examples`, the bound method it returns.
  Primary release sources: [functools.py](https://github.com/pypy/pypy/blob/release-pypy3.11-v7.3.20/lib-python/3/functools.py)
  and [hidden_applevel](https://github.com/pypy/pypy/blob/release-pypy3.11-v7.3.20/pypy/module/__pypy__/interp_magic.py).
  Their SHA-256 hashes are `23291a1a186d6eb0ccfd3d61546b3d06a3ac37c59e46e61f50aae8626d96fce3` and `af10e8aca1e49b7513f552cd6913524f76e5d9e495c91bee2d32e3619fca549d`, respectively.
- `@functools.wraps(func)` (`:696`, `:704`) is the `functools.partial`
  that `functools.wraps` returns: `functools.partial.__call__` (tenacity
  practice).
- `parse_format_string` (`:39`) is the bound method `parse` of a
  `string.Formatter`: `string.Formatter.parse` at `:1375` and `:1432`.

## Scope rules

**A. Edges are per function.** Functions without a package caller keep
their edges: `Scope.__repr__` (`dict.__repr__(self)` calls back
`Binding.__repr__` and `Builtin.__repr__` for the bindings in the scope,
`:527`), the `source_statement` properties of `Importation`,
`SubmoduleImportation` and `ImportationFrom` (public API, used by clients;
only `StarImportation.imported_name` reads its own), and
`_exitOnSignal.handler`.

**B1. Receivers.**
- `super()` calls follow the MRO of every class that reaches them:
  `Definition.redefines` reaches `Binding.redefines` (`:245`);
  `Importation.__init__` reaches `Binding.__init__` for all its subclasses
  (`:302`); `ClassScope.__init__` and `FunctionScope.__init__` reach
  `<builtin>.dict.__init__` (`:532`, `:550`).
- `value.redefines(existing)` (`:959`, `:969`): `value` is any binding
  that the package adds, so all five `redefines` methods are callees.
- `self.source_statement` in `StarImportation.imported_name` (`:412`):
  `StarImportation` has no subclass.

**B2. Arguments and stored values.**
- `cls()` in `in_scope` (`:816`): the package passes the seven scope
  classes that it uses (`_ast_node_scope`, `DoctestScope`, `TypeScope`).
  `ClassScope` and `FunctionScope` run their `__init__`, the five others
  `<builtin>.dict.__init__`.
- `is_name_match_fn` (`:630`, `:653`): `_is_typing_helper` is private; its
  callers pass the lambdas of `_is_typing` and `_is_any_typing_member`.
- `str(message)` in `Reporter.flake` (`reporter.py:84`): the docstring
  names a `pyflakes.messages.Message`; the callee is `Message.__str__`.
- `isPythonFile(filename)`: `iterSourceCode` passes `str` or `bytes`
  paths from `os.walk` and `os.path.join` (`api.py:106-109`). A bytes path
  reaches `bytes.endswith` at line 76, then raises TypeError inside that
  builtin because the suffix is str. Entry to the builtin still counts.

**B3. Not considered.** A hand-built or deliberately invalid mutated
tree. The traced `Checker.NAME -> RuntimeError` comes from replacing an
AST context with `object()` (`test_undefined_names.py:831`), so it is
rejected. Parser-created names use only Load, Store and Del contexts. A package object passed into
the arguments of a message class by the client (the formatting sites
`messages.py:16-17` reject the `__repr__` and `__str__` candidates).

**B4. Concrete outside types.** `Reporter.syntaxError`'s `text` is
documented as unicode (`reporter.py:51`): `<builtin>.str.splitlines`.
`os.environ.get` is named `collections.abc.Mapping.get` (README, anytree).

**B5. Client objects are opaque.** The streams of a `Reporter` are client
objects, except the default `sys.stdout` and `sys.stderr` of
`_makeDefaultReporter` (`reporter.py:92`), named
`io.TextIOWrapper.write`; `sys.stdin.read()` in `main` is
`io.TextIOWrapper.read`. The tests pass `io.StringIO` objects: the four
trace edges to `_io.StringIO.write` and `.read` are rejected.

**C. Public.** Public: `pyflakes.api` (`check`, `checkPath`,
`checkRecursive`, `iterSourceCode`, `isPythonFile`, `main`),
`pyflakes.reporter.Reporter`, `pyflakes.messages.*`, and
`pyflakes.checker.*` without an underscore (`Checker` and its public
methods, the binding and scope classes, `in_annotation`,
`parse_percent_format`, ...). Private: `_custom_builtins`,
`_doctest_parser`, `_is_typing_helper`, `_must_match`, `_exitOnSignal`,
`_get_version`, `_makeDefaultReporter`, and the `Checker` methods with an
underscore.

## Judgement calls

1. **`_unknown_handler` at `checker.py:1252`**: a callee (see "Node
   dispatch", 3). Settled by global rule B3.
2. **Computed handler names at `checker.py:1016`**: no package code runs
   in the getattr (see "Node dispatch", 1).
3. **Signal handlers** (`api.py:131-155`, installed at `:171-172`): no
   edge to `_exitOnSignal.handler`, as Sublist3r (judgement 6).
   `signal.signal` stores it. SIGINT comes from the terminal and SIGPIPE
   from a reader that closed the pipe. `sys.stdin.read()` (`api.py:184`)
   blocks while the SIGINT handler is installed, but the package does not
   wait for a signal there; the asciinema audit kept only the `select`
   that waits for signals and not the other blocking calls.
4. **Version branches** (all run on some supported version):
   `checker.py:1063-1064` (3.15), `:1198` and `:1318-1321` (the `else` of
   `handleAnnotation`: 3.11 to 3.13), `:1591-1594` and `:1616-1619` (both
   sides), `:2119-2124`, `:2145-2150`, `:2168-2169` (lazy imports, 3.15),
   `:2275-2278` (3.12+). The unknown-future report at `:2159-2161`
   also runs on 3.14+ for a late future import; only a leading unknown
   future feature is rejected by the newer parser. `PYPY` (`:21`) is set
   and never read. No `TYPE_CHECKING` block, no optional import.
5. **Dict keys and `VariableKey`** (`Checker.DICT`, `:1816`, `:1823`,
   `:1825`). `convert_to_value` makes a `VariableKey` for a `Name` key or
   value, also inside a tuple. `collections.Counter` hashes the keys
   (`VariableKey.__hash__`) and compares keys of equal hash
   (`VariableKey.__eq__`; the hash of a `VariableKey` is the hash of its
   name, so it collides with the str of the same name and `__eq__` runs
   reflected). These callees are not candidates by name at the `Counter`
   calls. `i_key == key` (`:1823:71`) is a site that the default decided;
   its entry accepts `VariableKey.__eq__`.
6. **Callbacks of `dict.__repr__`** (`:527:63`): `Binding.__repr__` and
   `Builtin.__repr__`, for the values of the scope.
7. **`UnhandledKeyType()`** (`:203`): its first `__init__` is
   `object.__init__`; no edge, a note.
8. **`isinstance(self.scope, ...)` and friends** (17 call sites): the site
   finder proposes `Checker.scope` as a callback because the argument
   names it. The property runs at the getattr site in the same
   expression; the call site rejects it. `report(..., value.imported_name)`
   (`:880`) is the same case.
9. **The setters** of `futuresAllowed` and `annotationsFutureEnabled`
   (`:1246`, `:2143`, `:2163`) are the same node as their getters.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `checker.VariableKey.__eq__` | 183 | `VariableKey` objects are made and hashed or compared only in `Checker.DICT`; one inside a tuple key also reaches `MultiValueRepeatedKeyLiteral.message_args` (`:1837`), where nothing hashes or compares it | `:1816:41`, `:1823:71`, `:1825:41` |
| `checker.VariableKey.__hash__` | 141 | the same | `:1816:41`, `:1825:41` |
| `checker.Binding.__repr__`, `checker.Builtin.__repr__`, `checker.Scope.__repr__`, `messages.Message.__str__` | 25, 25, 25, 24 | no f-string field or `%` operand formats a binding, scope or message | `:527:63` (`dict.__repr__`: the two binding `__repr__`), `reporter.py:84:31` (`Message.__str__`) |

The defaults decide only implicit sites. Each explicit site where a
default would apply has its own rejection with the type of its argument
(`frozenset`, `set`, `hash`, `str` and `.format` calls), as in h11.

## Value sites

14 value sites, each with a note: `handler(node)` (38 callees),
`handler()` (6), `messageClass(...)` (30), `cls()` (3), the two `func(self,
...)` of the annotation wrappers (2 and 1), the two `is_name_match_fn(...)`
(2 each), `fn(self, annotation, parent)` (1), the two
`parse_format_string(...)` (1 each), `_doctest_parser()(docstring)` (1),
and the two `@functools.wraps(func)` decorators (1 each). Three exclusion
lines record nodes considered at `:699:24` and `:778:20`.

## Functions that the tests do not run

9 of 189: `_exitOnSignal.handler` (signal), `Binding.__repr__`,
`Builtin.__repr__`, `Scope.__repr__` (debugging), `Checker._in_try` and
the `__init__` of `EagerUseOfLazyImport`, `LazyImportStarNotPermitted`
(3.15), `FutureFeatureNotDefined`, and `_unknown_handler`.

## Statistics

| | Count |
|---|---|
| All scanner sites | 2674 |
| Sites needing an entry or a default decision | 1045 (752 call, 25 decorator, 83 op, 96 getitem, 8 setitem, 1 delitem, 55 getattr, 3 setattr, 22 format) |
| Ledger entries | 837 (752 call, 25 decorator, 55 getattr, 3 setattr, 2 op) |
| Default rejections | 6 candidates in 3 lines |
| Nodes | 197 (8 modules, 189 functions) |
| Edges | 644: 376 in the package, 268 outside |
| Graph edges with a trace name or alias | 592 of 644 (91.9%) |
| Edges only from reading | 52 |
| Trace edges rejected | 5 |
| Functions that the tests run | 180 of 189 |
