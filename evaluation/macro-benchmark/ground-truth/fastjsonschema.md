# fastjsonschema: judgements of the ground truth

The global-scope audit of 2026-11-15 removes 0 edges and adds 0. The global
README rules apply to this project without local exceptions. The current ledger
and counts below include these corrections.

See the audit record (audit record `2026-11-15/README.md`) for evidence.

Release v2.22.3 (commit `9d3f5ee`). Analysed source: `fastjsonschema/`
(root `.`): 11 modules, 95 functions (no lambda), 11 classes.
`setup.py` sets `python_requires=">=3.10"`, so the supported versions are
3.10 and later.

The ledger is `fastjsonschema.ledger`; the graph `fastjsonschema.json` is
generated from it. One trace edge is rejected
(`fastjsonschema.rejected.json`).

## Architecture, as the ledger uses it

- `compile`, `compile_to_code` and `validate` (`__init__.py`) make a
  `RefResolver` (`ref_resolver.py`) and a code generator through
  `_factory`. `_get_code_generator_class` returns `CodeGeneratorDraft04`,
  `06`, `07` or `2019`; each one subclasses the one before, and
  `CodeGeneratorDraft2019` only extends `FORMAT_REGEXS`.
- A generator writes Python source line by line with `self.l(...)`.
  `CodeGenerator.l` is decorated with `@indent` (`generator.py:250`), so
  the class attribute `l` is `indent.wrapper` (`indent.py:8`). `wrapper`
  calls the original `l` back (`indent.py:10`) and returns an `Indent`,
  whose `__enter__` and `__exit__` run for `with self.l(...)`.
- Each schema keyword maps to a bound `generate_*` method in the
  `OrderedDict` `_json_keywords_to_function`, which only the `__init__`
  methods of the generators fill (`draft04.py:49`, `draft06.py:30`,
  `draft07.py:35`). `run_generate_functions` calls them
  (`generator.py:209`).
- `RefResolver.in_scope` and `RefResolver.resolving` and
  `CodeGenerator.trial_validation` are `@contextmanager` generator
  functions: a call runs `contextlib.contextmanager.helper`, which calls the
  generator function back; the `with` site runs no package code (sqlparse's
  `indent(self)`, argcomplete judgement 8).

## The generated code (for the lead)

`compile` runs the generated source with `exec(code_generator.func_code,
global_state)` (`__init__.py:294`) and returns the function that it
defines, or a `functools.partial` of it when `formats` is not empty. README
scope ruling 4 says that this code is not source. The ledger applies the
micro-benchmark rules for `exec`:

1. **No node.** The generated functions (`validate_*`, and the local `fn`
   of `uniqueItems`) are code outside the package (micro-benchmark "Nodes":
   a function that a string passed to `exec` defines has no node).
2. **Its module code belongs to `compile`.** The string's module code is
   `NoneType = type(None)` (`generator.py:139`) and the `def` statements,
   whose defaults (`{}`, `None`) call nothing. "Calls in a string passed to
   eval or exec belong to the scope that calls eval or exec"
   (micro-benchmark "Scopes without a node"; `dynamic/exec_in_function`).
   So `compile -> <builtin>.type` is an edge, at the `exec` site. The trace
   does not have it; see "Trace" below.
3. **Package code that a generated function calls is a callback.** A
   generated function instantiates `JsonSchemaValueException` for each
   failed rule (`generator.py:308-324`) and `JsonSchemaValuesException`
   when `fast_fail=False` (`generator.py:160, 245`). Like `helper()` in
   `dynamic/exec_defines_function`, these `__init__` calls belong to the
   package scope that calls the generated function. The only such scope is
   `validate` (`compile(...)(data)`, `__init__.py:172:108`): edges
   `validate -> JsonSchemaValueException.__init__` (in the trace) and
   `validate -> JsonSchemaValuesException.__init__`. The call itself has no
   callee for the generated function; with formats it calls
   `functools.partial.__call__`. Every other call of generated code (the
   builtins, `re` patterns, `Decimal`, the client's custom formats) is a
   call of code outside the package and is no edge.

A client that calls the validator itself is client code: no edge.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted at |
|---|---|---|---|
| `fastjsonschema.generator.CodeGenerator.l` | 159 (all explicit `self.l(...)` calls) | `@indent` replaces `l` by `wrapper`; each site calls `fastjsonschema.indent.indent.wrapper`, and only `wrapper` calls `l` back | `indent.py:10:20` (`func(...)`, a value site, not a candidate there) |

The size report also lists `Indent.__enter__` and `Indent.__exit__` (115
sites each). They are **not** default rejections: they are callees at 103
of the 115 `with` sites (every `with self.l(...)`). The README keeps
defaults for candidates that are wrong at almost every site, and has no
default acceptance; so the ledger accepts them at the 103 sites and
rejects them at the 12 others (`reject *`): 6 `with self.trial_validation()`,
2 `with self._resolver.resolving(...)`, 1 `with self._resolver.in_scope(...)`,
2 `with self.in_scope(...)`, and 1 `with urlopen(uri)`.

## Scope rules

**A.** Every function keeps its body edges. Never run by the tests:
`CodeGeneratorDraft07.generate_content_encoding` and
`generate_content_media_type` (no test schema has those keywords), and
`fastjsonschema.__main__.main`.

**B1. Receivers.**
- `self` in the generator methods is a `CodeGeneratorDraft04`, `06`, `07`
  or `2019`. `self._generate_func_code_block(...)` (`generator.py:175`)
  has both callees: `CodeGenerator`'s (for a draft-04 generator) and
  `CodeGeneratorDraft06`'s override.
- `func()` (`generator.py:209`) has the 35 `generate_*` methods: the 24 of
  draft 04, the 3 overrides of draft 06 (`generate_type`,
  `generate_minimum`, `generate_maximum`, bound for a draft-06, 07 or 2019
  generator), the 5 new ones of draft 06 and the 3 of draft 07.
- `code_generator.global_state` (`__init__.py:292`) is
  `CodeGeneratorDraft04.global_state` only: every class that `_factory`
  makes inherits that override, which calls `CodeGenerator.global_state`
  through `super()` (`draft04.py:80`).
- `CodeGenerator`'s docstring says that the class "is not supposed to be
  used directly", so its direct-construction entry is private under C.
  The draft subclasses have public paths and are constructed by `_factory`
  and the tests. Their construction and inherited method calls reach the
  base bodies. This keeps the recorded edges without admitting a client
  construction of plain `CodeGenerator` or changes to its keyword table.

**B2/B4. Arguments.**
- `definition` is annotated `dict[str, Any] | bool` (`__init__.py:137`);
  sub-schemas are JSON values (dicts for objects), as the documented
  examples and `json.loads` give them. Method calls on schema objects are
  `<builtin>.dict.get`, `.items`, `.keys` (jmespath's convention for JSON
  data). The trace has these names.
- `handlers` values are typed as a bare callable
  (`Mapping[str, Callable[[str], Any]]`): no package value.
  `handlers[scheme](uri)` (`ref_resolver.py:66`) has a note and no callee.
- `formats` values are a str or a bare callable: no package value.
- The tests make `CodeGeneratorDraft07(definition, formats=...,
  use_formats=...)` without a resolver (`tests/conftest.py:25`), so
  `RefResolver.from_schema` at `generator.py:72` is a real call (B2, the
  tests); the trace has it.

**B3/B5.** A `definition` that a client gives to the
`JsonSchemaValueException` constructor itself is opaque; the package's own
exceptions (from generated code) carry a dict, so
`rule_definition -> <builtin>.dict.get` (`exceptions.py:54`).

**C.** Public paths: `fastjsonschema.validate`, `compile`,
`compile_to_code`, the exceptions, `fastjsonschema.RefResolver` (imported
into the package, not in `__all__`; the tests call
`RefResolver.from_schema`), the generator classes
(`fastjsonschema.draft07.CodeGeneratorDraft07`, used by the tests), and the
helpers of `generator.py` (the tests call `serialize_regexes`).

## Judgement calls

1. **`TYPE_CHECKING`, version branches, optional imports:** none. The
   annotations (`dict[str, Any] | bool`, `Mapping[...]`) are evaluated at
   definition time on 3.10 to 3.13 and lazily on 3.14; their `|` and
   subscripts run no package code, so no edge depends on the version.
2. **`urlsplit` by version** (`ref_resolver.py:52:29`, `64:31`). On 3.10
   `urllib.parse.urlsplit` is a plain function; from 3.11 on it is decorated
   with `@functools.lru_cache(typed=True)` (read in the CPython sources of
   3.10, 3.11, 3.12 from GitHub, and 3.13 to 3.15 locally). The site has
   both names: `urllib.parse.urlsplit` and
   `functools._lru_cache_wrapper.__call__` (the README's rule of a receiver
   with two classes across admitted versions, applied to a function). The
   trace (3.14) has the second.
3. **Remote `$ref` without a handler** (`ref_resolver.py:68-75`). It runs:
   the documentation names it (`__init__.py:225-227`, "for example `http`,
   `https`, or `file` URLs"). `urlopen` returns an
   `http.client.HTTPResponse` for http(s) and a `urllib.response.addinfourl`
   for file, ftp and data URLs. So `response.info()` has
   `http.client.HTTPResponse.info` and `urllib.response.addinfourl.info`;
   `.get_content_charset()` has `http.client.HTTPMessage.…` and
   `email.message.Message.get_content_charset` (urllib's handlers build the
   headers with `email.message_from_string`); `response.read()` has
   `http.client.HTTPResponse.read` and
   `tempfile._TemporaryFileWrapper.__getattr__.func_wrapper` (asciinema
   judgement 9). No test reaches this branch (no network).
4. **Exceptions without `__init__`.** `JsonSchemaDefinitionException(...)`
   (25 sites) runs `ValueError.__init__`: `<builtin>.ValueError.__init__`
   (jmespath's convention). The `super().__init__(...)` of the two other
   exceptions (`exceptions.py:39, 68`) skips `JsonSchemaException` and also
   reaches `<builtin>.ValueError.__init__`. The trace names it
   `<builtin>.BaseException.__init__`; the checker resolves the two.
5. **`re.compile` and the candidate `fastjsonschema.compile`** (5 sites):
   the call is the standard library's, an attribute of the module `re`.
6. **`exec(...)` and the candidate `CodeGenerator.func_code`**
   (`__init__.py:294:9`): the argument is the str that the property
   returned at `294:25`.
7. **`sys.stdin.read()`** (`__main__.py:11`): `io.TextIOWrapper.read`
   (pypinyin, asciinema).
8. **`OrderedDict` methods**: `_json_keywords_to_function` is an
   `OrderedDict`, so `.update` and `.items` are
   `collections.OrderedDict.update` and `.items` (the trace agrees).

## Value sites

| Site | Callees | Where the values come from |
|---|---|---|
| `__init__.py:172:108` `compile(...)(data)` | `functools.partial.__call__`, `JsonSchemaValueException.__init__`, `JsonSchemaValuesException.__init__` | the generated function or its partial ("The generated code") |
| `__init__.py:362:59` `_get_code_generator_class(definition)(...)` | `CodeGeneratorDraft04/06/07.__init__` | the four classes; 2019 inherits 07's `__init__` |
| `generator.py:209:21` `func()` | the 35 `generate_*` methods | B1 above |
| `indent.py:10:20` `func(self, line, ...)` | `CodeGenerator.l` | `@indent` decorates only `l` |
| `ref_resolver.py:66:34` `handlers[scheme](uri)` | none | client callables (B2, B5) |
| `ref_resolver.py:122:19` `cls(...)` | `RefResolver.__init__` | the package calls `from_schema` only on `RefResolver` |

## Trace

Recorded in the container (CPython 3.14.10): 846 passed, 4 skipped, 12
deselected; 496 edges. Resolved:

- **Added from the trace**: the `functools._lru_cache_wrapper.__call__`
  name of `urlsplit` (judgement 2).
- **Rejected**: `resolve_remote -> <builtin>.dict.__getitem__`. The tests
  pass a dict's bound `__getitem__` as a handler (`tests/test_integration.py:141`,
  `test_composition.py:63`): a client callback.

Edges only from reading (53): `__main__` (6); the paths that no test
takes: the draft-07 content keywords (10), the remote fetch (12, with the
3.10 name of `urlsplit`), error branches and an enum of dicts (10),
`normalize -> urllib.parse.urlsplit` (the 3.10 name), and `validate`'s
partial and `JsonSchemaValuesException` (2); and two kinds that the tracer
misses:

- the 11 calls of `@contextmanager` generator functions
  (`trial_validation` 6, `in_scope` 3, `resolving` 2), which
  `contextlib.contextmanager.helper` starts;
- `compile -> <builtin>.type`, the call in the exec'd module code.

**Observation on the tracer (not a ground-truth decision).** Both misses
look like one cause in `macro-benchmark/trace.py`: its `on_call` override
calls `super().on_call(...)`, which adds a frame, so the validator's
`sys._getframe(1)` in `on_call` (`micro-benchmark/validate.py:439` and the
`self.caller(sys._getframe(1))` of deferred functions) sees the frame of
`trace.py`. That frame is not exec code, so the exec owner is not found,
and `trace.py` is classified as client code, so `caller()` returns no
caller for a generator function that library code starts. The README
attributes the `@contextmanager` gap to the validator (Traces, "Limits"),
but the validator itself handles it. Found by reading only; nothing was
run.

## Statistics

| | Count |
|---|---|
| Sites | 771 (640 call, 11 decorator, 115 with, 5 getattr) |
| Sites with candidates / value sites | 475 / 6 |
| Ledger entries | 771 |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 917 / 25 (17) / 0 / 102 |
| Default rejections | 1, deciding 159 explicit sites |
| Edges | 548: 314 in the package, 234 outside |
| Graph edges with a trace name or alias | 495 of 548 (90.3%) |
| Edges only from reading | 53 |
| Trace edges rejected | 1 |
| Functions that the tests run | 92 of 95 |

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
