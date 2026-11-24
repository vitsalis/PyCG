# sqlparse: judgements of the ground truth

Global-rule audit (2026-11-15): 0 removed edges, 1 added
edge; 697 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Release 0.6.1 (commit `09dbe1e`). Analysed source: `sqlparse/`: 21 modules,
223 functions (6 lambdas), 44 classes. `pyproject.toml:29` sets
`requires-python = ">=3.10"`, so the supported versions are 3.10 and later.
The release explicitly supports CPython and PyPy (the two implementation
classifiers in `pyproject.toml`). The final version classifier is not an
upper bound. `CHANGELOG` drops Python 3.8 and 3.9; it does not drop PyPy.

The ledger is `sqlparse.ledger`; the graph `sqlparse.json` is generated from
it. Two trace edges are rejected in `sqlparse.rejected.json`.

## Architecture, as the ledger uses it

- `parse`, `parsestream`, `format` and `split` (`__init__.py`) build a
  `FilterStack` (`engine/filter_stack.py`). `FilterStack.run` lexes
  (`lexer.tokenize`), runs the `preprocess` filters on the token stream,
  splits statements (`StatementSplitter.process`), groups each statement
  (`grouping.group`) if grouping is on, then runs the `stmtprocess` and
  `postprocess` filters on it.
- The parse tree: `sql.Token` (a leaf, `ttype` a token type) and
  `sql.TokenList` (a group, `ttype` `None`) with 20 subclasses. No class
  defines `__eq__`, `__len__` or `__bool__` (the `__len__` methods are
  commented out). `TokenList` defines `__iter__` and `__getitem__` over
  `self.tokens`. `Identifier` and `Function` take `get_real_name` and
  `get_alias` from `NameAliasMixin`, which precedes `TokenList` in their MRO.
- `Token.is_group` is `False` for a leaf and `True` for a group
  (`sql.py:66`, `171`); `Token.match` tests `self.ttype is ttype`, so a
  match on a token type never selects a group.

## Token types (`_TokenType.__getattr__`)

This section states the argument for the default rejection of
`sqlparse.tokens._TokenType.__getattr__` (2236 sites) and for the 40 sites
that accept it.

**1. When `__getattr__` runs.** `tokens._TokenType` (`tokens.py:15`) is a
`tuple` subclass without `__slots__`, so each instance has a `__dict__`.
Python calls `__getattr__` only when normal lookup fails. For a name that does
not start with `__`, `__getattr__` makes the child type, stores it in the
instance dict of the parent (`setattr(self, name, new)`, `tokens.py:26`) and
returns it. Every later load of that name on that parent finds it in the
dict and does not call `__getattr__`. So a load `P.X` calls `__getattr__`
only if it is the first load of `X` on `P` in the process. Special methods
are looked up on the type, not through `__getattr__`. No package code loads
a dunder name from a token type, so the dunder branch (`tokens.py:23-24`)
never runs through an implicit package attribute load. It can run through
the public bound method `sqlparse.tokens.Token.__getattr__`, whose dunder
name is permitted by rule C. A direct call with `"__absent__"` reaches
`super()` before the failing superclass lookup. It requires no reload,
deleted cache entry or client modification of package internals.

**2. How the package names token types.** Every module that uses token
types imports the module `tokens`: as `T` (`sql.py:12`, `grouping.py:9`,
`statement_splitter.py:9`, the six modules of `filters/`) or as `tokens`
(`keywords.py:12`, `lexer.py:18`). No module imports a token type by name.
A load `T.Keyword` is a module attribute, not a `__getattr__` call. Only
the second and later components of a chain (`T.Keyword.DML`: the load of
`DML` on `Keyword`) load an attribute of a token type. `rg` for
`(T|tokens)\.\w+\.\w+` over `sqlparse/` lists every such chain; no package
code loads an attribute from a token type that it holds in a variable or a
parameter (`ttype`, `action`, `self.ttype` are only compared, tested with
`in` or passed on).

**3. Module code that `import sqlparse` runs, in order.** Any import of a
submodule runs `sqlparse/__init__.py` first. Its line 14 imports, in this
order:

1. `cli` (`cli.py:20-25`): stdlib modules, the partly made `sqlparse`, and
   `exceptions`. No token type.
2. `engine` (`engine/__init__.py:8-10`): first `grouping`. `grouping.py:8`
   imports `sql`, and `sql.py:12` imports `tokens`:
   - `tokens.py` runs completely and creates 21 types at 21 sites (lines
     38-71): `Token.Text`, `Text.Whitespace`, `Whitespace.Newline`,
     `Token.Error`, `Token.Other`, `Token.Keyword`, `Token.Name`,
     `Token.Literal`, `Literal.String`, `Literal.Number`,
     `Token.Punctuation`, `Token.Operator`, `Operator.Comparison`,
     `Token.Wildcard`, `Token.Comment`, `Token.Assignment`,
     `Token.Generic`, `Generic.Command`, `Keyword.DML`, `Keyword.DDL`,
     `Keyword.CTE`. Lines 64-66 set `Token.Token`, `Token.String` and
     `Token.Number` with `setattr`; they load nothing.
   - `sql.py:13` imports `utils` (no token type). The class bodies of
     `sql.py` load module attributes (`T.Punctuation`, `T.Keyword`) and two
     chains, in the body of `TypedLiteral`: `T.Name.Builtin` (497:23,
     creates `Name.Builtin`) and `T.String.Single` (498:24, creates
     `String.Single`).
   - Back in `grouping.py`: line 22 creates `Number.Integer` (22:35) and
     `Number.Float` (22:53); line 23 loads `String.Single` (exists, from
     `sql.py:498`) and creates `String.Symbol` (23:49); line 24 creates
     `Name.Placeholder` (24:26). The `@recurse(...)` decorators run
     `recurse` and `wrap`, which load no token type.
   - Then `filter_stack` (`engine/__init__.py:9`), which imports `lexer`
     (`filter_stack.py:10`), which imports `keywords` (`lexer.py:18`).
     `keywords.py` module code: `SQL_REGEX` (lines 119-204) creates
     `Comment.Single` (120:52), `Comment.Single.Hint` (120:59),
     `Number.Hexadecimal` (161:37), `Keyword.Order` (179:64, and finds it
     at 180, 181) and `Keyword.TZCast` (193:60); every other chain there
     exists already (`Name.Placeholder`, `Number.Float`, `Number.Integer`,
     `String.Single`, `String.Symbol`, `Name.Builtin`, `Keyword.DDL`,
     `Operator.Comparison`). The dicts `KEYWORDS` and `KEYWORDS_*` (lines
     206-1111) load `Keyword.DML`, `Keyword.DDL`, `Keyword.CTE` and
     `Name.Builtin` (all exist) and create `Keyword.DCL` (793:29).
     `_NO_SPANS = DelimitedSpans({}, {})` (line 76) runs
     `DelimitedSpans.__init__`, which loads no token type. `lexer.py`
     module code loads none.
   - `filter_stack.py:11-14` then imports `grouping` (done),
     `statement_splitter` (only class and method definitions), `exceptions`
     and `filters`: the six filter modules load no chain at module level
     except `filters/tokens.py:30` (`T.String.Symbol`, exists).
3. `filters`, `formatter`, `sql`, `tokens` (`__init__.py:14`): already
   imported, or (`formatter.py`) no token type.

`sqlparse/__main__.py` is not imported by `import sqlparse`; `python -m
sqlparse` imports the package first, then runs it, and it loads no token
type.

| Module | Sites that create a type | Types created |
|---|---|---|
| `tokens.py` | 21 (38:14 to 71:15) | the 21 listed above |
| `sql.py` (class body of `TypedLiteral`) | 497:23, 498:24 | `Name.Builtin`, `String.Single` |
| `engine/grouping.py` | 22:35, 22:53, 23:49, 24:26 | `Number.Integer`, `Number.Float`, `String.Symbol`, `Name.Placeholder` |
| `keywords.py` | 120:52, 120:59, 161:37, 179:64, 193:60, 793:29 | `Comment.Single`, `Comment.Single.Hint`, `Number.Hexadecimal`, `Keyword.Order`, `Keyword.TZCast`, `Keyword.DCL` |

These 33 sites accept the candidate. The order between the modules only
decides which module creates a type; the set of 33 types that module code
creates does not depend on it.

**4. Why a load in a function is not the first load of these 33 types.**
During the import, the only package functions that run are `recurse` and
`wrap` (the decorators of `grouping.py`) and `DelimitedSpans.__init__`
(`keywords.py:76`); none of them loads a token type. Every other package
function runs only when a client calls it, and a client can reach a package
function only after `sqlparse/__init__.py` has finished, so after all 33
types exist. A load of one of them in a function therefore finds it in the
instance dict and calls no `__getattr__`. A client that deletes a type from
an instance dict, or reloads `sqlparse.tokens`, is not considered (ruling
R2).

**5. The types that no module code creates.** The package also names
`Comment.Multiline` and `Comment.Multiline.Hint`, and only in functions.
The first load of each in a process is in whichever of these functions runs
first, so these 7 function sites accept the candidate (ruling R1 gives a
public-API trigger for each):

| Site | Function | Load |
|---|---|---|
| `statement_splitter.py:188:43` | `StatementSplitter.process` | `T.Comment.Multiline` |
| `others.py:35:32` | `StripCommentsFilter._process` | `T.Comment.Multiline` |
| `others.py:35:42` | `StripCommentsFilter._process` | `.Hint` of `T.Comment.Multiline` |
| `keywords.py:108:55` | `find_delimited_spans` | `tokens.Comment.Multiline` |
| `keywords.py:108:65` | `find_delimited_spans` | `.Hint` of `tokens.Comment.Multiline` |
| `keywords.py:111:55` | `find_delimited_spans` | `tokens.Comment.Multiline` |
| `sql.py:554:66` | `Comment.is_multiline` | `T.Comment.Multiline` |

For example, `sqlparse.split("select 1")` in a fresh process: the text has
no `/*` and no `$`, so `find_delimited_spans` returns at line 89, and
`StatementSplitter.process` evaluates the tuple at line 187-188 for the
`select` token, which loads `Comment.Multiline` first. `.Hint` can be first
in `StripCommentsFilter._process` or at `keywords.py:108` (the opener
`/*+`), whichever runs first. `T.Comment.Single.Hint` at `others.py:35:65`
exists (`keywords.py:120`).

**6. The trace.** The trace has exactly four callers of `__getattr__`: the
modules `sqlparse.tokens`, `sqlparse.sql`, `sqlparse.engine.grouping` and
`sqlparse.keywords`. No package function calls it in the trace, which fits
point 4. The four function edges of point 5 are not in the trace: the test
module `tests/test_tokenize.py` loads `T.Comment.Multiline` and
`T.Comment.Multiline.Hint` in its `parametrize` arguments (lines 255-263)
when pytest collects it, before any test runs. That is client code, so in
the traced process no package function makes the first load.

**7. The default.** It decides the other 2236 attribute-load sites: the
receiver is not a token type (a module, a class, a token or group, a
filter, a str, a list, a dict, a `re.Match`, an argparse object), or it is
one of the 33 types of point 3. `super().__getattr__(self, name)`
(`tokens.py:24:39`) has no callee: neither `tuple` nor `object` defines
`__getattr__`, so the attribute load raises `AttributeError`.

## Value dispatch

**The filter stack.** `FilterStack` is public, and so are its three lists.
The package fills them only in `FilterStack.__init__`
(`StripTrailingSemicolonFilter`), `formatter.build_filter_stack` and
`sqlparse.format` (`SerializerUnicode`). The tests and documentation add no
filter of their own. By rule B2 each list holds the package filters that
the package puts there; filters of the client are client objects.

| Site | Callees | Size |
|---|---|---|
| `filter_stack.py:34:41` preprocess `filter_.process(stream)` | `_CaseFilter.process` (`KeywordCaseFilter`), `IdentifierCaseFilter.process`, `TruncateStringFilter.process` | 3 |
| `filter_stack.py:44:36` stmtprocess `filter_.process(stmt)` | `process` of `StripTrailingSemicolonFilter`, `SpacesAroundOperatorsFilter`, `StripCommentsFilter`, `StripWhitespaceFilter`, `ReindentFilter`, `AlignedIndentFilter`, `RightMarginFilter` | 7 |
| `filter_stack.py:47:43` postprocess `filter_.process(stmt)` | `SerializerUnicode.process`, `OutputFilter.process` | 2 |
| `output.py:30:36` `self._process(...)` | `OutputPythonFilter._process`, `OutputPHPFilter._process`, `OutputFilter._process` (judgement 2) | 3 |

**The grouping engine.**

| Site | Callees | Size |
|---|---|---|
| `grouping.py:478:13` `func(stmt)` | `recurse.wrap.wrapped_f` (the 8 functions decorated with `@recurse` are bound to it) and the 17 undecorated functions of the list at 447-477 | 18 |
| `utils.py:78:14` `f(tlist)` in `wrapped_f` | the 8 decorated functions (`grouping.py:251-423`) | 8 |
| `grouping.py:532:17` `match(token)` | the 10 local `match` functions and `group_typed_literal.match_to_extend` | 11 |
| `grouping.py:534:37` `valid_prev(prev_)` | the local `valid_prev`, or the shared `valid`, of the 10 group functions | 10 |
| `grouping.py:534:59` `valid_next(next_)` | the local `valid_next`, the shared `valid`, or `valid_final` | 11 |
| `grouping.py:537:40` `post(...)` | the 10 local `post` functions | 10 |
| `sql.py:253:24` `func(token)` in `_token_matching` | `token_first.matcher`, `token_next.matcher`, `token_next_by.<lambda1>`, `token_not_matching.<lambda1>` | 4 |
| `sql.py:278:48` `func(tk)` | `group_comments.<lambda1>` (grouping.py:339) | 1 |
| `sql.py:336:26` `grp_cls(subtokens)` | `TokenList.__init__` (no group class defines `__init__`) | 1 |

`_group` is private, and all eleven package calls pass `valid_prev`,
`valid_next` and `post`, so its default lambdas
(`sqlparse.engine.grouping.<lambda1>`, `<lambda2>`, defaults evaluated by
the module) are never called. They are excluded at 534:37 and 534:59.

**Dispatch on the class name.** `ReindentFilter._process`,
`AlignedIndentFilter._process` and `StripWhitespaceFilter._stripws` call
`getattr(self, '_process_' + type(tlist).__name__.lower(), default)`. The
callees are the methods whose suffix names a class of `sql.py`
(`reindent.py:143:13`: where, parenthesis, function, identifierlist, case,
values, default; `aligned_indent.py:135:13`: statement, parenthesis,
identifierlist, case, default; `others.py:88:13`: identifierlist,
parenthesis, default). Each such method then knows the class of `tlist`,
which decides its subscript sites (`tlist[0]` of a `Parenthesis`, `Function`
or `Case` runs `TokenList.__getitem__`).

**Other value sites.** The 45 `sql.Token(...)` sites are calls of the class
`sql.Token`; the site finder sees the token type `tokens.Token` (a value)
under the same name. `self.convert(value)` (`filters/tokens.py:21:37`,
`35:37`) is `getattr(str, case)`: `<builtin>.str.upper`, `.lower`,
`.capitalize` (judgement 4). `rexmatch(text, pos)` (`lexer.py:153:29`) is
the bound `re.Pattern.match` that `set_SQL_REGEX` stores. `self.is_keyword`
(`lexer.py:160:42`) is `Lexer.is_keyword`; the site finder sees the token
slot `is_keyword`. `cls()` (`lexer.py:53:44`) makes a `Lexer`, which has no
`__init__`.

## Scope rules

**A. Edges are per function.** `RightMarginFilter._process` keeps its 10
out-edges, although `RightMarginFilter.process` raises `NotImplementedError`
and only `_process` itself calls it. The module `sqlparse.__main__` keeps its
two edges (`sys.exit`, `cli.main`): its body runs for `python -m sqlparse`.

**B1. Receivers.** Public methods admit constructible classes and concrete
subclasses that inherit them. Private methods use actual package inputs; an
uncalled private body uses the public-parameter fallback. Failed argument
binding enters no function. A failing initializer retains calls reached in
its body but supplies no completed receiver. Clients do not reinitialize
instances or reuse arbitrary half-changed objects.

`self` in a filter method is an instance of that filter
class; no filter class has a package subclass except `_CaseFilter`
(`KeywordCaseFilter`, `IdentifierCaseFilter`) and `OutputFilter` (`OutputPythonFilter`,
`OutputPHPFilter`). This rejects `ReindentFilter.nl`, `_next_token`,
`_process_default` and `_split_kwds` in `AlignedIndentFilter` and the
reverse. `_CaseFilter` is private and never instantiated, and
`IdentifierCaseFilter` overrides `process`, so `self` in
`_CaseFilter.process` is a `KeywordCaseFilter` (`ttype in self.ttype` runs
`_TokenType.__contains__`; in `IdentifierCaseFilter.process` the `ttype` is
a tuple). `TokenList.has_alias` and `get_name` are public on every group, so
both `NameAliasMixin.get_alias` and `TokenList.get_alias` are callees (and
the same for `get_real_name`).

**B2. Arguments and stored values.** Broad `Any`, `object`, `type` and
`Callable` annotations do not admit arbitrary package objects. Client assignment
of a package value to a public attribute requires a documentation or test witness
for that role; public visibility alone does not provide one.

The filter lists and the grouping
callbacks above. `split_unquoted_newlines(stmt)` gets a `Statement` from the
package (`others.py:179`), so `str(stmt)` runs `TokenList.__str__` only.
`Token.__init__` gets a `str` value at every package call, so `str(value)`
calls no package code.

**B3. Not considered.** An arbitrary package object as an option value of
`validate_options` (the `{x!r}` format sites), as the `value` of a token,
or as a filter in a list where the package never puts it.

**B4. Concrete outside types.** Annotations, including shipped stubs, take
precedence over conflicting documentation. This release ships no stubs.
Abstract outside types alone do not identify a concrete implementation.

`options` of `validate_options` and
`build_filter_stack` is a dict (the `**options` of `format`, or `vars(args)`
in the CLI): `<builtin>.dict.get`. `text` after `isinstance(text, bytes)`:
`<builtin>.bytes.decode`. `isinstance(text, TextIOBase)` names an abstract
io base class, so `text.read()` (`lexer.py:120:29`) has no outside callee
(judgement 5).

**B5. Client objects are opaque.** The stream of `parsestream`, the funcs of
`token_matching`, a client subclass of `Lexer`.

**C. Public.** `sqlparse.engine.FilterStack`, the filters of
`sqlparse.filters` (and `sqlparse.filters.output.OutputFilter`), the classes
of `sqlparse.sql`, `sqlparse.lexer.Lexer`, `sqlparse.keywords` and
`sqlparse.utils` functions are public paths. `_group`, `_group_matching`,
`_is_delimiter`, `_CaseFilter`, `TokenList._token_matching` and the `_process`
methods are private.

## Judgement calls

1. **No version branches, no `if TYPE_CHECKING:`, no optional imports.**
   The modules have no `from __future__ import annotations`; the annotations
   of `__init__.py` (`str | None`, `tuple[sql.Statement, ...]`,
   `IO[str]`) run `type.__or__` and `__class_getitem__` of builtins and
   `typing`, no package code (3.14 evaluates them lazily; no edge either
   way). Round 4 also checks the working union of normal, `-O` and `-OO`
   execution. This configuration scope remains a working assumption, not
   recorded user approval. The only active assertion is `end is None` in
   `TokenList._token_matching` (`sql.py:244`). Its five package call sites
   either leave `reverse=False` or omit `end`, so removing the assertion
   adds no call target. No runtime code reads `__doc__` or `__debug__`.
2. **`OutputFilter._process`** (`output.py:19`, raises
   `NotImplementedError`) is a callee of `OutputFilter.process`
   (`output.py:30:36`). `OutputFilter` is public
   (`sqlparse.filters.output.OutputFilter`) and not abstract by `abc`, so a
   client can make one (rule B1). The trace does not have the edge.
3. **Classes without `__init__`.** `Lexer()`, `SerializerUnicode()`,
   `StripTrailingSemicolonFilter()`, `SpacesAroundOperatorsFilter()`,
   `StripCommentsFilter()`, `StripWhitespaceFilter()` and `_TokenType(...)`
   (a `tuple` subclass) have no edge, as `DoAttempt()` and `DoSleep(...)` in
   tenacity. `SQLParseError(...)` is `<builtin>.Exception.__init__`, as
   `HookCallError` in pluggy.
4. **`getattr(str, case)`** (`filters/tokens.py:16`): `case` is
   documented as "upper", "lower" or "capitalize" (`docs/source/api.rst:27-33`),
   `validate_options` enforces it for `format`, and the default is
   'upper'. A client passing another `str` method name to `KeywordCaseFilter`
   directly is not considered.
5. **Streams.** `parsestream` takes `str | IO[str]` (`__init__.py:33`);
   `Lexer.get_tokens` calls `text.read()` after `isinstance(text,
   TextIOBase)`. The tests pass an `io.StringIO` (`tests/test_split.py:123`,
   `130`) and an open file (`tests/conftest.py:45`). Both are client
   objects; the trace edges `get_tokens -> _io.StringIO.read` and
   `-> _io.TextIOWrapper.read` are rejected in `sqlparse.rejected.json`.
6. **`@contextmanager` functions `indent` and `offset`** (`utils.py:117,
   124`). A call `indent(self)` runs `contextlib.contextmanager.helper`,
   which calls the generator function back: both are callees, as in the
   micro-benchmark case `context_managers/contextmanager_generator`. The
   trace has the `helper` edges but none of the 8 edges to
   `utils.indent` and `utils.offset`: making the generator runs no frame of
   it, and the tracer attributes the first `next()` of `__enter__` to no
   call site.
7. **`map(str, cond)`** (`aligned_indent.py:78:44`): map construction is
   lazy. The consuming `' '.join` call (78:40) invokes `str` on each token,
   reaching `Token.__str__` or `TokenList.__str__`. Both package targets
   are recorded at join as an allowed placement normalization. README
   ruling 12 also permits the previous map site within this same function.
   The map site keeps only `<builtin>.map`; the graph pairs are unchanged.
8. **The default factory** of `defaultdict(lambda: ([], []))`
   (`keywords.py:92`) is a callee of the subscript sites that miss
   (`keywords.py:100:35`, `112:31`), through `defaultdict.__missing__`.
   `DelimitedSpans.resolve` subscripts `_closers` only with tags that
   `find_delimited_spans` has stored, so it never calls it.
9. **Naming.** `sys.stdout` and `sys.stderr` are named `io.TextIOWrapper`
   (`write`, `flush`); the trace names them `_io.TextIOWrapper.*`, and the
   checker accepts both. `group.add_argument` on an
   `argparse._ArgumentGroup` (cli.py:65-157) is named
   `argparse._ArgumentGroup.add_argument` under the global concrete-receiver
   rule. `ArgumentParser` is a sibling, not its public ancestor. The four
   direct parser calls at cli.py:40,45,51,58 retain
   `argparse.ArgumentParser.add_argument`.
10. **`super().__getattr__`** (`tokens.py:24:39`): a call site with no
    callee and a note (see "Token types").

## Rulings of the lead

The independent audit (`sqlparse.audit.md`) raised three cases that the
README did not decide. The lead ruled:

- **R1 (lead): edges that depend on what ran earlier in the process.** Such
  an edge counts if some program that uses only the public API makes it in
  a fresh process. The 4 function edges to `tokens._TokenType.__getattr__`
  (7 sites, "Token types", point 5) stay. The auditor's trigger for each
  site, each in a fresh process:
  - `statement_splitter.py:188:43` (`StatementSplitter.process`):
    `sqlparse.split('select 1')`. The text has no `/*` or `$`, so
    `find_delimited_spans` returns at line 89.
  - `keywords.py:111:55` (`find_delimited_spans`): `sqlparse.parse('/* c
    */')`.
  - `keywords.py:108:55` and `108:65` (`find_delimited_spans`):
    `sqlparse.parse('/*+ h */ select 1')`.
  - `others.py:35:32` (`StripCommentsFilter._process`):
    `sqlparse.format(';', strip_comments=True)`. The splitter loads
    `Multiline` only for a token other than `;` (line 180).
  - `others.py:35:42` (`StripCommentsFilter._process`):
    `sqlparse.format('select 1', strip_comments=True)`.
  - `sql.py:554:66` (`Comment.is_multiline`): `sql.Comment([...]).is_multiline()`
    on a group that the client builds (the tests also build groups by
    hand).
- **R2 (lead): changes to package internals are not considered (B3).** A
  state that only a client's change to package internals makes, such as
  `importlib.reload` of a package module or the deletion of a cached token
  type, is not considered. (After a reload of `sqlparse.tokens`, 9 more
  functions would call `__getattr__` again; the package does not support
  that state either, because the lexer and the `M_OPEN`/`M_CLOSE` class
  attributes keep the old types.)
- **R3: superseded by the global-rule audit (2026-11-15).** The former
  local ruling collapsed group and parser calls to one name. Judgement9
  now applies the same concrete-receiver rule as every project: the group
  edge is `argparse._ArgumentGroup.add_argument`.

The audit's optional wording point W1 is applied: the reason of the
`__getattr__` default now lists all receivers that are not token types
(`super()` objects, `Lexer`, `StatementSplitter`, `FilterStack`,
`DelimitedSpans`, file and `sys` streams, `bytes`), and ends with "or
another object that is not a token type".

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `tokens._TokenType.__getattr__` | 2236 | not a token type, or the type already exists | the 40 first loads of the table above and of "Token types" |
| `sql.TokenList.__getitem__` | 310 | the operand is a list, tuple, str, dict, `re.Match`, generator, argparse value or annotation | `grouping.py:190:22`, `306:14` (`tlist[...]` in two `post` functions); `aligned_indent.py:54:41`, `59:38`; `reindent.py:167:32`, `238:49` |
| `sql.TokenList.__iter__` | 196 | the same operands | `reindent.py:205:26` (`for token in tlist`); `list(tlist)` at `grouping.py:47:22` and `518:22` |
| the 10 local `match` functions of `grouping.py` | 31 each | only `_group` calls them (532:17); `x.match(...)` is `Token.match` | `grouping.py:532:17` |

The explicit sites that a default decides are builtin calls whose arguments
are lists, generators, ints or str (`enumerate`, `max`, `all`, `any`,
`list`, `sum`, `iter`, `reversed`, `map`), `getattr(str, case)`,
`getattr(self, ...)` on filters, and `sqlparse.format(...)` in the CLI
(the package function, not `str.format`).

## Exclusions

| Site | Excluded | Why |
|---|---|---|
| `grouping.py:478:13` `func(stmt)` | the 8 functions decorated with `@recurse` | the names are bound to `wrapped_f`, which calls them |
| `grouping.py:534:37` `valid_prev(prev_)` | `sqlparse.engine.grouping.<lambda1>` | the default of a private function that every caller overrides |
| `grouping.py:534:59` `valid_next(next_)` | `sqlparse.engine.grouping.<lambda2>` | the same |

## Functions that no site calls

- **Public API**: `parse`, `split` (and `format`, `parsestream`, which the
  CLI and `parse` call), `Token.__repr__`, `Token.is_child_of`,
  `has_ancestor`, `TokenList.get_token_at_offset`, `token_matching`,
  `has_alias`, `get_parent_name`, `Statement.get_type`, the four
  `Identifier` methods, `Function.get_parameters`, `get_window`,
  `Comparison.left`, `right`, `Comment.is_multiline`. All ran in the tests
  except `Comment.is_multiline`.
- **Dead code**: the two default lambdas of `_group`.
- Not run in the tests: `OutputFilter._process`,
  `RightMarginFilter._process`, `Comment.is_multiline`,
  `SquareBrackets._groupable_tokens`, `TokenList.get_real_name`, and the two
  lambdas (216 of 223 functions run).

## Tools

- **`sql.Token(...)` as a value site.** The site finder marks the 45 calls
  `sql.Token(...)` (filters, `StatementSplitter.process`) as value sites,
  because the package also binds the name `Token` to a value: the token
  type `tokens.Token = _TokenType()` (`tokens.py:35`). The callee is the
  class `sqlparse.sql.Token`; each site needs a note that adds nothing.
- **`self.is_keyword(...)` as a value site** (`lexer.py:160:42`): `Token`
  has a slot `is_keyword` that `Token.__init__` assigns (`sql.py:67`), so
  the site finder treats the name as an assigned attribute. The receiver is
  a `Lexer`, and the callee is the method `Lexer.is_keyword`.
- **Order-dependent first loads in the trace.** Whether a load of a token
  type calls `__getattr__` depends on what ran before it in the process. In
  the trace, client code (test collection) made the first loads of
  `Comment.Multiline` and `Comment.Multiline.Hint`, so the trace cannot
  confirm the four function edges of "Token types", point 5. A trace of
  another test order, or of a single test, could have them. The README had
  no rule for such state-dependent calls; ruling R1 decides them.
- **Generator functions behind `@contextmanager`.** The tracer records the
  `contextlib.contextmanager.helper` edges but none of the 8 edges to
  `utils.indent` and `utils.offset` (judgement 6).

## Statistics

| | Count |
|---|---|
| All AST sites | 4,193: the 3,508 sites below plus 685 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 3508 (838 call, 21 decorator, 168 iter, 1 mapping, 48 op, 117 getitem, 2274 getattr, 41 format) |
| Sites with candidates / value sites | 3137 / 62 |
| Ledger entries | 1000 (838 call, 21 decorator, 43 getattr, 8 getitem, 1 iter, 48 op, 41 format) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 1042 / 199 (114) / 3 (10 nodes) / 177 |
| Default rejections | 13 candidates in 4 lines, deciding 2236, 310, 196 and 31 sites each |
| Edges | 697: 439 in the package, 258 to 81 callees outside |
| Edges that the trace confirms | 660 of 697 (94.7%) |
| Edges only from reading | 37 (22 in the package, 15 outside) |
| Trace edges rejected | 2 |
| Functions that the tests run | 216 of 223 |
