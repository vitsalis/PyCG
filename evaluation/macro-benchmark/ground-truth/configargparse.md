# configargparse: judgements of the ground truth

Global-rule audit, pass 1 (2026-11-15): 0 removed edges, 3 added
edges; 404 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Pass 2 (2026-11-16): 1 removed edge, 3 added edges; 406 edges
after that pass. Source-site and provenance corrections are recorded in the
pass-2 audit (audit record `2026-11-15/pass-2/README.md`).

Release v1.9.0 (commit `1829aa1`). Analysed source: the single module
`configargparse.py`: 67 functions (2 lambdas), 12 classes. `setup.py:125`
sets `python_requires=">=3.6"`, so the supported versions are 3.6 and later.
Its implementation classifiers explicitly name CPython and PyPy. There is no
declared upper bound. The round-4 working scope includes normal, `-O` and
`-OO` execution; this is an assumption pending the optional preference, not
an explicit user approval. The current graph has 408 edges on 68 nodes.

The ledger is `configargparse.ledger`; the graph `configargparse.json` is
generated from it. `configargparse.rejected.json` rejects 6 trace edges.
The naming-only rejection `add_argument -> argparse._ActionsContainer.add_argument`
records the original definition name in the trace. Import replaces that
attribute with package code; the graph instead uses the three saved
`original_add_argument_method` paths in judgement 8.

## Architecture, as the ledger uses it

- `ArgumentParser` (`configargparse.py:1015`) subclasses
  `argparse.ArgumentParser`. It overrides `__init__`, `parse_args`,
  `parse_known_args` and `format_help`, and inherits the rest (`error`,
  `exit`, `_get_formatter`, `_add_action`, ...). Inherited methods are named
  through `argparse.ArgumentParser`.
- At import, the module replaces `argparse._ActionsContainer.add_argument`
  with its own function `add_argument` (`:2447`), after it saves the
  original as `original_add_argument_method` (`:2444`). `add_arg` and `add`
  become aliases of it (`:2483-2484`). So `self.add_argument(...)` on any
  argparse container runs `configargparse.add_argument`, also when argparse
  itself calls it.
- `self._config_file_parser` is a `ConfigFileParser` (`:94`) instance,
  set only in `__init__` (`:1160-1175`). There are seven package classes:
  `ConfigFileParser` (a plain base whose methods raise
  `NotImplementedError`), `DefaultConfigFileParser`,
  `ConfigparserConfigFileParser`, `YAMLConfigFileParser`,
  `TomlConfigParser`, `IniConfigParser` and `CompositeConfigParser`.
  `CompositeConfigParser` keeps a list of parsers (`self.parsers`, annotated
  `list[ConfigFileParser]`, `:935`).
- The config streams of the package are the `io.StringIO` of `:1439` and
  the text files that the default `config_file_open_func`, the builtin
  `open` (`:1114`), returns (`io.TextIOWrapper`).
- `add_argument` turns a write-out-config-file `_StoreAction` into an
  instance of a class that it builds with `type()` (`:2306`), with the
  bases `(_WriteOutConfigFileActionMixin, type(action))`.

## Scope rules

**A. Edges are per function.** Every function keeps its body edges. The
three methods of `ConfigFileParser` keep their edge to
`<builtin>.NotImplementedError`.

**B1. Receivers.** Public methods admit constructible classes and concrete
subclasses that inherit them. Private methods use actual package inputs;
an uncalled private body uses the public-parameter fallback. Failed argument
binding enters no function. An initializer that raises keeps calls reached
in its body, but failed construction supplies no completed receiver. Clients
do not reinitialize instances or reuse arbitrary half-changed objects.

`ConfigFileParser` has no `abc` base and no abstract
method, and it is public: a client can pass it (or an instance) as
`config_file_parser_class` or in `config_parser_types`. So it is a receiver,
as `jmespath.visitor.Visitor` is (jmespath audit, R2). The six dispatch
sites on config file parsers therefore have all seven methods:
`p.parse(stream)` (`:957:31`), `parser.get_syntax_description()`
(`:995:110`), `self.parsers[0].serialize(items)` (`:1005:41`),
`self._config_file_parser.parse(stream)` (`:1449:66`), `.serialize(...)`
(`:1796:63`) and `.get_syntax_description()` (`:2228:77`).

**B2. Arguments and stored values.** Broad `Any`, `object`, `type` and
`Callable` annotations do not admit arbitrary package objects. Client
assignment to a public attribute requires a documentation or test witness
for that role.

- `config_file_parser_class` and `config_parser_types`: any package
  `ConfigFileParser` class or instance (docstrings `:1063`, `:927`; module
  docstring `:556`; the annotation `list[ConfigFileParser]` at `:935`).
- Streams: the package's own streams (see above). The callees of
  `stream.read()`, `.seek(0)` and `.close()` are `io.StringIO.*` and
  `io.TextIOWrapper.*`.
- `config_file_open_func`: the default is the builtin `open`, so
  `<builtin>.open` at `:1799:53`, `:2033:73` and `:2110:57`, and
  `io.TextIOWrapper.write` at `:1802:42`. A client function is a client
  callback.

**B3. Not considered.** `entry()` (`:2038:39`): a client stream factory.
The `__call__` of `TomlConfigParser`, `IniConfigParser` and
`CompositeConfigParser` takes no argument, but returns a parser, not a
stream; they are excluded there.

**B4. Concrete outside types.** Annotations take precedence over conflicting
documentation; shipped stubs would count as annotation evidence, but this
release ships none. Abstract types alone do not fix a concrete outside
class, and `Any` supplies no concrete type. For example, the `io.IOBase`
stream documentation does not add arbitrary stream implementations.

- `items` of `serialize` and the result of `parse` are documented as
  `OrderedDict` (`:113`, `:124`), and the package builds them so:
  `collections.OrderedDict.items` (judgement 7).
- `isinstance` tests fix `dict` (`:510`, `:644`), `bytes` (`:707`) and
  `str` (`:1328`, `:1913`).
- The args of `parse_known_args` are strs ("a list of args as in argparse",
  `:1317`), as are the args that `convert_item_to_command_line_arg` makes.

**B5. Client objects are opaque.** A client stream, a client file for
`print_values`, a client `config_file_open_func` and its result, and the
lines of a client stream have no outside callee.

**C. Public.** Everything in the module is public, except the names with a
leading underscore: `_WriteOutConfigFileActionMixin`,
`_keep_literal_or_convert_to_str`, `_subparsers_of`,
`_dispatches_to_subparsers`, `_convert_parsed_value_to_config_file_value`,
and the `_`-methods of `ArgumentParser`.

## Judgement calls

1. **Version branch** (`:31-37`). Python 3.9 and later bind
   `is_boolean_optional_action` to `<lambda1>` (`:33`) and append
   `argparse.BooleanOptionalAction` (`:32:47`); 3.6 to 3.8 bind it to
   `<lambda2>` (`:37`). Both are supported, so the three calls in
   `convert_item_to_command_line_arg` (`:1906:46`, `:1917:50`, `:1924:50`)
   have both lambdas. `<lambda2>` never runs in the trace (Python 3.14).
   The branch `sys.version_info < (3, 9)` at `:1199` has no call.
2. **Optional imports.** `TomlConfigParser.parse` imports `tomllib as
   toml`, else the `toml` package (`:692-701`). Both sides run, so
   `toml.loads(content)` (`:709:32`) has `tomllib.loads` and `toml.loads`.
   `serialize` imports only `toml` (`toml.dumps`). `_load_yaml` imports
   `CSafeLoader`/`CDumper`, else `SafeLoader`/`Dumper` (`:492-497`): no call
   differs. Its `ImportError` branch gives `<builtin>.Exception.__init__`
   (`:487:52`).
3. **Python 3.6's argparse.** In 3.6, `_SubParsersAction._name_parser_map`
   is a `collections.OrderedDict`; from 3.7 it is a `dict` (checked in
   CPython's `Lib/argparse.py` on the branches 3.6, 3.7 and 3.8). So
   `action.choices.values()` (`:2361:51`) has `<builtin>.dict.values` and
   `collections.OrderedDict.values`.
4. **A `CompositeConfigParser` inside a `CompositeConfigParser`.** `p()`
   (`:935:50`) has the `__call__` of `TomlConfigParser`, `IniConfigParser`
   and `CompositeConfigParser`. The tests pass only the first two instances,
   and classes. A `CompositeConfigParser` is a `ConfigFileParser` instance,
   which the docstring and the annotation name, so I kept it. This also
   gives the self-edges `CompositeConfigParser.parse -> .parse` and
   `.serialize -> .serialize` and `.get_syntax_description ->
   .get_syntax_description`.
5. **A class called without its required argument** (ruling: lead, Q1 of
   the audit; a call that fails to bind its arguments does not run the
   callee: no edge, as the micro-benchmark rule gives for a plain
   function). `p()` (`:935:50`) and
   `config_file_parser_class()` (`:1167:64`) call a class with no argument.
   For `TomlConfigParser`, `IniConfigParser` and `CompositeConfigParser` the
   call fails to bind the required argument before `__init__` runs, so I
   gave no edge to their `__init__` (excluded, with the reason). The other
   package parser classes have `object.__init__`: no edge. So `:1167:64`
   has no callee.
6. **`print_values(file=sys.stdout)`** (ruling: lead, Q3 of the audit;
   the default `sys.stdout` is a package default, B2, so the edge to
   `io.TextIOWrapper.write` stays) (`:2168`). The default is
   `sys.stdout` when the module is imported, an `io.TextIOWrapper` in a
   normal interpreter: `file.write(...)` (`:2170:19`) has
   `io.TextIOWrapper.write`. Under pytest the default is pytest's capture
   object, and the test passes a `StringIO`; that trace edge is rejected
   (client object).
7. **Plain dicts as `items`** (ruling: lead, B4; the documentation fixes
   the concrete outside type `OrderedDict`, so the method call is an edge
   to `collections.OrderedDict.items`, and the plain dicts of the tests are
   client objects whose trace edges are rejected). The docstring of
   `ConfigFileParser.serialize` (`:124`) says "an OrderedDict", and every
   package call passes one (`get_items_for_config_file_output`, `:1839`).
   The tests pass plain dicts to `ConfigparserConfigFileParser.serialize`
   and `IniConfigParser.serialize` (`tests/test_configargparse.py:3582,
   4436, 4446`). I kept only `collections.OrderedDict.items` at the three
   `items.items()` sites (`:251:38`, `:404:38`, `:905:38`), and rejected the
   two trace edges to `<builtin>.dict.items` as client objects. If the
   documented type is read as "a dict", the three sites also get
   `<builtin>.dict.items` (+3 edges, one of them in
   `DefaultConfigFileParser.serialize`).
8. **The replaced `add_argument`.**
   - `self.add_argument(...)` (`:1180:30`, `:1189:30`):
     `configargparse.add_argument`.
   - `argparse.ArgumentParser.__init__(self, ...)` (`:1157:41`) calls
     `self.add_argument(...)` for `-h/--help` (with `add_help`, the
     default), so it also has `configargparse.add_argument` (trace
     confirms).
   - `self.original_add_argument_method(...)` (`:2300:47`) runs the saved
     original through `argparse.ArgumentParser.original_add_argument_method`,
     `argparse._ArgumentGroup.original_add_argument_method`, or
     `argparse._MutuallyExclusiveGroup.original_add_argument_method`.
     The receiver comes from the public parser and group APIs
     (`tests/test_configargparse.py:468-476`). The old
     `argparse._ActionsContainer.add_argument` path resolves to the package
     replacement after import, so it is not the outside callee name.
   - A module reload would make `original_add_argument_method` the
     replacement itself. Nothing in the package reloads it; not considered.
9. **The write-out action.** `super(_WriteOutConfigFileActionMixin,
   self).__call__(...)` (`:148:61`) finds `type(action)`, an
   `argparse._StoreAction` (`:2302`): `argparse._StoreAction.__call__`,
   the canonical name of a private class. A client subclass of
   `_StoreAction` is client code.
10. **Library callbacks.**
    - `argparse.ArgumentParser.parse_known_args(self, ...)` (`:1549:75`)
      calls back `_WriteOutConfigFileActionMixin.__call__` (the action),
      `ArgumentParser.format_help` (the `-h` action calls `print_help`) and
      `ArgumentParser.parse_known_args` (`_SubParsersAction.__call__` on a
      configargparse subparser, `parser_class` defaults to `type(self)`).
      The trace has all three.
    - `arg_parser.parse_known_args(...)` (`:2101:59`) calls back
      `_open_config_files.error_method`, which `:2098` sets as
      `arg_parser.error`, on a parse error. The trace has it.
    - No other library call reaches package code. `error`, `exit`,
      `format_usage` and `_get_formatter` are not overridden.
      `ArgumentDefaultsRawHelpFormatter` (`:84-91`), which argparse
      instantiates through `formatter_class` (in `_get_formatter`), defines
      no method, so no package node runs.
11. **An action left in a parser by a failed `add_argument`** (ruling:
    lead, Q2 of the audit; an object that the package leaves behind after
    it raised an error to refuse it is not considered, B3).
    `add_argument` raises its `ValueError`s (`:2318-2336`) after the
    original has added the action. A client that catches the error and
    still parses could reach the mixin's `__call__` from `:2101:59`. I did
    not consider a parser after a failed `add_argument` (B3).
12. **`functools.lru_cache`.** The decorator (`:577:2`) is the local
    function `functools.lru_cache.decorating_function`. A call of
    `is_quoted` (`:599:17`, `:860:33`) runs
    `functools._lru_cache_wrapper.__call__` on CPython. On the supported
    PyPy 3.11 / 7.3.20 release it runs the Python function
    `functools._lru_cache_wrapper.wrapper`. PyPy provides no `_functools`
    accelerator; `hidden_applevel` returns the same function. Both wrappers
    call `is_quoted` back on a cache miss. The supported-implementation
    union retains both wrapper edges at both sites.
13. **Exceptions of the package.** `ConfigFileParserException` and
    `ConfigFileParserMissingDependency` define no `__init__`: their calls
    give `<builtin>.Exception.__init__` (the trace's
    `<builtin>.BaseException.__init__`), as in pluggy. `super().__init__()`
    in `TomlConfigParser`, `IniConfigParser` and `CompositeConfigParser`
    gives `<builtin>.object.__init__`.
14. **`os.fsdecode`** (`:2216:51`) is defined by the closure
    `os._fscodec()`, but it has the attribute path `os.fsdecode`, which is
    its name here.

The public `get_items_for_config_file_output` also accepts plain dicts
under its documented dict-of-dicts contract (lines 1339-1342,1566-1576,1833).
Its four `items()` sites at 1840, 1863, 1874, 1877 therefore name both dict and
OrderedDict. Internal callers alone do not restrict this public argument.

On admitted Python 3.6, the regex receiver types have no public `re.Match`
or `re.Pattern` aliases. Keep `_sre.SRE_Match.group` for
`DefaultConfigFileParser.parse` and `_sre.SRE_Pattern.match` for `is_quoted`,
as well as their modern names on Python 3.7 and later.

## Value sites

27 value sites. Most of them are calls of a name that the module also
assigns:
`ArgumentParser.parse = parse_args` (`:2486`), `_ActionsContainer.add =
add_argument` (`:2484`), `arg_parser.error = ...` (`:2098`), `ArgumentError
= argparse.ArgumentError` (`:2454`), `self.sections = ...` (`:684`, `:823`).
Each has an exclusion for the package node that the assignment could
suggest.

| Site | Callees | Size |
|---|---|---|
| `:577:2` `@functools.lru_cache(...)` | `functools.lru_cache.decorating_function` | 1 |
| `:341:39`, `:840:39` `config.sections()` | `configparser.ConfigParser.sections` | 1 each |
| `:935:50` `p()` | `__call__` of Toml, Ini, Composite | 3 |
| `:957:31`, `:1449:66` `.parse(stream)` | the 7 `parse` methods | 7 each |
| `:1167:64` `config_file_parser_class()` | none (judgement 5) | 0 |
| `:1180:30`, `:1189:30` `self.add_argument(...)` | `configargparse.add_argument` | 1 each |
| 8 sites `self.error(...)` | `argparse.ArgumentParser.error` | 1 each |
| `:1302:36` `ArgumentError(None, msg)` | `argparse.ArgumentError` | 1 |
| `:1410:41`, `:1492:57`, `:2356:13` `.add(...)` | `<builtin>.set.add` | 1 each |
| `:1657:73` `getattr(parser, "_could_set_option", ...)(...)` | `ArgumentParser._could_set_option` | 1 |
| 3 sites `self._config_file_open_func(...)` | `<builtin>.open` | 1 each |
| `:2038:39` `entry()` | none (client callback) | 0 |
| `:2300:47` `self.original_add_argument_method(...)` | `original_add_argument_method` through `argparse.ArgumentParser`, `argparse._ArgumentGroup`, `argparse._MutuallyExclusiveGroup` | 3 |

## Rejected trace edges

| Caller | Callee | Why |
|---|---|---|
| `ArgumentParser.__init__` | `unittest.mock.CallableMixin.__call__` | the test patches `argparse.ArgumentParser.__init__` with a mock (`test_configargparse.py:1148`) |
| `ArgumentParser.print_values` | `_io.StringIO.write` | the test's `StringIO` as `file` (`:1246-1247`) |
| `ConfigparserConfigFileParser.serialize` | `<builtin>.dict.items` | the tests' plain dict as `items` (`:4436`, `:4446`); judgement 7 |
| `IniConfigParser.serialize` | `<builtin>.dict.items` | the test's plain dict as `items` (`:3582`); judgement 7 |
| `TomlConfigParser.parse` | `_io.BytesIO.read` | the test's `BytesIO` stream (`:3487-3496`) |
| `add_argument` | `argparse._ActionsContainer.add_argument` | naming-only artifact: this old attribute now resolves to the package replacement; the graph names the saved outside method through the parser and group classes (judgement 8) |

## Functions that the tests do not run

9 of 67: `<lambda2>` (Python 3.6 to 3.8 only); the three methods of
`ConfigFileParser`; and the `get_syntax_description` methods of
`CompositeConfigParser` (with `guess_format_name`),
`ConfigparserConfigFileParser`, `IniConfigParser` and `TomlConfigParser`.

## Statistics

| | Count |
|---|---|
| All AST sites | 1,549: the 518 sites below plus 1,031 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 518 (517 call, 1 decorator); 78 with candidates (132 candidates); 27 value sites |
| Ledger entries | 518 |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 585 / 10 (5) / 18 (24 nodes) / 94 |
| Default rejections | 0 |
| Nodes | 68 |
| Edges | 408: 94 in the package, 314 to 112 callees outside |
| Edges that the trace confirms | 330 of 408 (80.9%) |
| Edges only from reading | 78 (34 in the package, 44 outside) |
| Trace edges rejected | 6 |
| Functions that the tests run | 58 of 67 |

## Round 3: supported PyPy cache wrappers (2026-11-16)

The focused follow-up adds two outside edges: `unquote_str` and
`IniConfigParser.parse` each call `functools._lru_cache_wrapper.wrapper`
on supported PyPy 3.11 / 7.3.20. No edges are removed. The graph now has
408 edges. Existing CPython wrapper and package callback edges remain.

## Round 4: complete source-first audit (2026-11-16)

All 408 baseline pairs, 1,549 AST sites and 68 bodies were reviewed. No graph
change was found. The 518 explicit entries cover 517 calls and one decorator;
the remaining 1,031 implicit sites add no package call. There are no default
rejections. All 24 excluded targets at 18 sites and six trace rejections remain.

The two assertions at lines 602 and 1913 disappear under `-O` and `-OO`.
Their normal-mode calls remain in the union. The second assertion is not an
unconditional type guard: the documented string/list role, package string
values, and client opacity leave the named `lower` target unchanged. No runtime
branch reads docstrings, so `-OO` adds no target. Client stream outputs remain
opaque; the named text-stream and string operations have package-created
`StringIO` or default `open` witnesses. Existing CPython/PyPy wrapper targets
and Python 3.6 regex and argparse alternatives remain.

The pass-2 heading now labels 406 as its historical result. The current table
and round-3 result correctly show 408. Historical audit prose is preserved.
