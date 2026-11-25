# json-repair: judgements of the ground truth

Release v0.64.2 (commit `f13a96b`). Analysed source: `src/json_repair/`
under the root `.` (the entry's decision, README "Batch 6", decision 6), so
every module name starts with `src.json_repair`: 22 modules, 144 functions
(2 lambdas), 12 classes; 166 nodes. `pyproject.toml` declares
`requires-python = ">=3.10"` and "Operating System :: OS Independent"; it
names no implementation, so the supported versions are CPython 3.10 and
later. The optional extra `schema` admits `jsonschema>=4.21` and
`pydantic>=2`.

The ledger is `json-repair.ledger`; the graph `json-repair.json` is
generated from it. 751 edges (394 inside, 357 outside); the trace confirms
714 (95.1 %); 141 of 144 functions run. 10 trace edges are rejected in
`json-repair.rejected.json` (client streams, a client default factory and
a call on a client module's `__dict__`, see J3 and J6).

The ledger was drafted with a script of the writer's own (scratch, not
committed) that fills the obvious builtin callees and the calls on a
`JSONParser` or `SchemaRepairer` receiver; every entry was then read
against the source, and every other entry was written by hand. No analysis
tool was run on the package, and no analysis output was read.

## Architecture, as the ledger uses it

- `JSONParser` (`json_parser.py:21`) holds the input in `json_str`, a
  `str` or a `StringFileWrapper`, a `JsonContext` in `context`, a list
  `deferred_contexts`, and the callable `log`. The `parse_*` methods
  forward to module functions of `parse_array.py`, `parse_comment.py`,
  `parse_number.py`, `parse_object.py` and `parse_string.py`, which take
  the parser as `self` (or `parser`).
- `SchemaRepairer` (`schema_repair.py:140`) holds the root schema, a log
  list (or `None`) in `log`, and a cache of jsonschema validators. Its
  `_log` appends to that list. It is unrelated to the parser's `log`.
- `JsonContext.enter` returns a `_JsonContextEntry`, a context manager
  whose `__enter__` and `__exit__` call `JsonContext.set` and `reset`.
- `MISSING_VALUE` (`utils/constants.py:12`) marks an object value that is
  missing; the package passes it only to `SchemaRepairer.repair_value`
  (`parse_object.py:312`).

## Default rejections

| Candidate | Sites decided | Why |
|---|---|---|
| `StringFileWrapper.__getitem__` | 521 | the subscripted object is no `StringFileWrapper` (annotations, strs, lists, dicts, tuples, schema values) |
| `StringFileWrapper.__len__` | 383 | the operand of the truth test, `len()` or other builtin is no `StringFileWrapper` |
| `StringFileWrapper.__setitem__` | 25 | the package never assigns an item of a wrapper |
| `MissingValueType.__repr__` | 111 | no formatted, printed or `str()`-converted value is `MISSING_VALUE` (J8); every `%` is an integer remainder |

The sites where the wrapper is the operand accept `__getitem__` (31 sites)
and `__len__` (17 sites) explicitly (J1).

## Judgements

**J1. Where a `StringFileWrapper` is.** `JSONParser.__init__` stores a
`StringFileWrapper` in `json_str` when it gets a stream
(`json_parser.py:62`; `load` and `from_file` give one). `JSONParser` and
`StringFileWrapper` are public, and the annotation of `json_str` is
`str | StringFileWrapper`; the tests also assign one
(`tests/test_parse_string.py:535`). `json_str` is reassigned only to a
`str` (`parse_object.py:239`, `342`). So every subscript and `len()` of a
parser's `json_str` (and of the local alias `json_str` in
`_try_parse_simple_quoted_string`) calls `__getitem__` or `__len__`,
except under an `isinstance(..., str)` guard: `json_parser.py:196`, `215`,
`217`, `232` (guards at 189 and 226) and `parse_string.py:66` (the `str`
branch of 62). The wrapper's own `self[i]` (`string_file_wrapper.py:91`)
and `len(self)` (97, 119, 160) call them too.

**J2. The parser's `log`.** `self.log` is assigned only in
`JSONParser.__init__`: the bound method `_log` when `logging` is true, else
the no-op lambda (`json_parser.py:76`, `79`). All 64 `self.log(...)` and
`parser.log(...)` sites have both callees. No test or document assigns
`log` on a parser.

**J3. Streams.** The annotation `TextIO` of `fd`/`json_fd` fixes no
concrete class (it is a typing stand-in, judged like `Mapping`). A stream
that a client passes is a client object (B5). The package opens one stream
itself: `from_file` passes the `io.TextIOWrapper` of `Path.open()`
(`json_repair.py:326`) through `load` and `repair_json` to the
`StringFileWrapper` (`json_parser.py:62`). So `StringFileWrapper.__init__`,
`get_buffer` and `_ensure_chunk_position` call `io.TextIOWrapper.tell`,
`seek` and `read`. The tests pass `io.StringIO` streams; the 7 trace edges
to `_io.StringIO.*` from these three methods are rejected. In `cli`,
`sys.stdin.read()` (`json_repair.py:463`) is `io.TextIOWrapper.read` (the
default `sys.stdin`); the test's `io.StringIO` in its place
(`tests/test_repair_json_cli.py:49`) is rejected.

**J4. The jsonschema validator class (for the lead).**
`_get_root_validator` calls `jsonschema.validators.validator_for(schema)`
and instantiates what it returns (`schema_repair.py:175-176`). That class
is the one that the schema's `"$schema"` names, else the library's default,
the latest draft: `Draft202012Validator` for the admitted versions
(`>=4.21`). Neither the package, its tests, its documentation nor its
examples set `"$schema"`, and pydantic's `model_json_schema()` emits none.
By the rule on library code that picks an object from the client's
configuration (B5: the library's defaults and the configurations that the
package documents are in scope), the ledger names only
`jsonschema.validators.Draft202012Validator` and its `evolve`, `is_valid`
and `validate` (`schema_repair.py:165`, `176`, `186`, `197`). The nearest
rule decides it; a client schema with `"$schema"` of another draft would
reach `Draft3Validator` to `Draft201909Validator`. The admitted range has
no upper bound; the name is that of the jsonschema 4.x releases.

**J5. `StringFileWrapper.__setitem__` (the referee's ruling (a) after
Codex audit round 1).** The package never calls this method and never
hands its own wrappers to a client (`repair_json` keeps its parser local).
My first draft gave the four `self.fd` calls no callee for that reason.
The referee ruled otherwise: rule A keeps a function's body edges whether
or not anything calls it, and B1 admits the instances that the package
creates, so the wrapper that holds the `io.TextIOWrapper` of `from_file`
is a receiver here although it never escapes to the client. So
`self.fd.tell()` (162:40), `.seek(...)` (163:21) and `.write(value)`
(164:22) call `io.TextIOWrapper.tell`, `.seek` and `.write` (+3 outside
edges). `write` binds and, on that read-only stream, is entered and raises
in its body, which keeps the edge (the batch-6 ruling on binding for a
callable written in C). For the same reason this witness never reaches the
second `seek` (165:21), which has no callee; the pair to `seek` comes from
163:21. A client's own stream stays opaque (B5).

**J6. Pydantic models.** `schema` is annotated `Any`; its documentation
says "a pydantic v2 model" (`json_repair.py:126`, `247`, `284`, `320`). By
B4 (an `Any` annotation states no type, so the documentation fixes it) the
model is a subclass of `pydantic.BaseModel`: `schema.model_json_schema()`
is `pydantic.BaseModel.model_json_schema` (`schema_repair.py:133`). Its
documented attributes are named by pydantic's types: `model_config` is a
`ConfigDict` (a `TypedDict`, so `<builtin>.dict.get`, 51), `model_fields`
a dict of `pydantic.fields.FieldInfo` (`<builtin>.dict.items`, 53;
`FieldInfo.is_required`, 62). `field.default_factory()` (70) calls the
client model's own factory: a client callback, no callee; the trace edge
`_add_pydantic_field_metadata -> <builtin>.list` (a test model's
`field(default_factory=list)`, `tests/test_schema_guided_parse.py:530`) is
rejected. `load_schema_model` imports a client module named by the client
(99): its code is client code, and `module.__dict__.get(class_name)` (100)
is a call on the `__dict__` of that client object, so it has no callee
(B5; batch-6 ruling jsonpickle (c); Codex audit round 1). The check
`int(version.split(".")[0]) < 2` (131) runs, but its branch (132) needs a
pydantic below 2, which the package does not admit (`pydantic>=2`), so the
`ValueError` there has no callee (Codex audit round 1).

**J7. Path methods.** `Path(...)` is `pathlib.Path`; it returns a
`PosixPath` or a `WindowsPath`, so `.open()` names
`pathlib.PosixPath.open` and `pathlib.WindowsPath.open`
(`json_repair.py:326`, `448`, `472`), as in netaddr and itables. The
package declares itself OS independent.

**J8. `MISSING_VALUE` is never formatted; it is deep-copied in a
container.** `repair_value` replaces a top-level `MISSING_VALUE` before any
other step: `normalize_missing_values` (schema `True` or empty) or
`_fill_missing` (`schema_repair.py:265-274`). The package's tests also pass
it inside a dict to the public `repair_value`
(`tests/test_schema_repairer.py:479-480`, `{"a": MISSING_VALUE}`), and by
B2's test clause that container is an admitted value there (the lead's
ruling on audit F1; my first draft called it "not considered (B3)", which
was the wrong rule). With a schema `{"anyOf": [...]}` or
`{"type": [...]}` the dict reaches `copy.deepcopy(value)` in
`_repair_union` (315:60) or `_repair_type_union` (337:63), which calls
`MissingValueType.__deepcopy__` back: +2 edges. `MissingValueType.__repr__`
stays a default rejection: with a dict container every path of
`repair_value` replaces `MISSING_VALUE` (`normalize_missing_values`,
`_fill_missing` or a nested `repair_value`) before a value is formatted or
validated; only a list such as `[MISSING_VALUE]` under `{"type": "array"}`
without `items` would keep it, and no test passes one (the auditor's
reason).

**J9. `ExitStack` in `parse_json`.** `stack.enter_context(entry)`
(`json_parser.py:287:40`) calls the entry's `__enter__` back;
`ExitStack.__exit__` at the end of the `with` block (285:18) calls each
entry's `__exit__`. So `__enter__` is a callee of the call and `__exit__`
of the `with` site.

**J10. Dataclasses.** `StringParseState()` (`parse_string.py:203`),
`ObjectSchemaConfig(...)` and `ArraySchemaConfig(...)`
(`parser_schema.py:61`, `71`, `75`) run generated `__init__` methods: no
node, no edge; the `list()` and `dict()` of the default factories are
calls of that generated code (the precedent is tenacity's `IterState`).
`@dataclass(frozen=True)` is a call of `dataclasses.dataclass` and a
decorator whose callee is its local function `dataclasses.dataclass.wrap`.

**J11. The import by `__package__` (for the lead).**
`importlib.import_module(f"{__package__}.json_repair")`
(`schema_repair.py:370`) imports the package's own module: with the
entry's root `.` the package is `src.json_repair`, so the callee at 371 is
`src.json_repair.json_repair.loads`. Under the installed name
`json_repair` it is the same function under the other import name; the
ledger follows the entry's naming.

**J12. Callables passed in the package.** `_parse_top_level`
(`json_parser.py:143`) is private; its callers pass `self.parse_json` and
the lambda of `parse_with_schema`, so `parse_element()` (144, 155) has
both. `classify_object_value_comma` is public with a bare `Callable`
parameter: a client's callable is a client callback; the package's values
are the closure `_scan_string_body.cached_skip_to_character`
(`parse_string.py:740`) and, by default, `parser.skip_to_character`
(`object_value_context.py:42`). Both are callees at 34, 83 and 90.

**J13. Abstract annotations.** `match_pattern_properties` takes a
`Mapping[str, Any]` (`utils/pattern_properties.py:8`), which fixes no
class; the package passes only a dict (`parser_schema.py:58-60`), so
`.items()` is `<builtin>.dict.items`. A client's own mapping is a client
object.

**J14. Module code under `__main__`.** `json_repair.py:483-484` and
`__main__.py:5-6` keep their edges (`sys.exit`, `cli`).

## Outside names verified in the dependency sources

After the ledger was written, the lead made the pinned wheels of the test
environment readable as plain sources
(`deps/json-repair/` (the dependency sources of the audit records), unpacked in a container and
hash-checked). The writer read them as text and ran or imported nothing.
These names and facts were checked there; none changed the ledger:

- jsonschema 4.26.0, `jsonschema/validators.py`:
  `validator_for` returns `_LATEST_VERSION` when the schema has no
  `"$schema"` (lines 1396-1399), and `_LATEST_VERSION` is
  `Draft202012Validator` (859; the class is made by `create`, 812). The
  class that `create` returns defines `evolve` (339), `validate` (448) and
  `is_valid` (485). So the names
  `jsonschema.validators.validator_for`,
  `jsonschema.validators.Draft202012Validator` and its `.evolve`,
  `.is_valid` and `.validate` (`schema_repair.py:165`, `175`, `176`, `186`,
  `197`) hold, and J4's default is the default of this release. `evolve`
  itself calls `validator_for(schema, default=self.__class__)` (341), so
  the evolved validator for a subschema keeps the root class unless the
  subschema has its own `"$schema"` (client configuration, as in J4). The
  lower bound 4.21 could not be read; the 2020-12 draft has been the
  latest of jsonschema since 4.0.
- pydantic 2.14.1: `BaseModel` (`main.py:136`, exported as
  `pydantic.BaseModel`) has the classmethod `model_json_schema` (607);
  `model_config` is `ClassVar[ConfigDict]` (173) and `ConfigDict` is a
  `TypedDict` (`config.py:34`), so a dict; `model_fields` is a class
  property that returns `Dict[str, FieldInfo]` (294; its descriptor runs
  on the attribute load, library code, no edge); `FieldInfo.is_required`
  is a method (`fields.py:923`) and `default_factory` an attribute that
  holds the model's callable (146). `GenerateJsonSchema` does not emit
  `"$schema"` (the line that would set it is commented out,
  `json_schema.py:443`), which J4 relies on.

The standard-library names (`pathlib`, `argparse`, `contextlib`, `json`,
`io`, `dataclasses`, `copy`, `importlib`, `enum`) were not read from these
sources; they match the trace's names or its aliases, except
`pathlib.WindowsPath.open` (another platform) and `io.TextIOWrapper.read`
at `json_repair.py:463` (the tests replace `sys.stdin`).

## Remarks on the README and the tools

- "Re-recording a trace" still says that batch 6 has no trace yet; the
  traces of batch 6 are committed (`98c93f8`).
- `check.py --report <name> --default <candidate>` lists every site of the
  named default, and the explicit sites of the other defaults as well; the
  site lines of one default have to be cut out of the output by hand.

## Codex audit round 1

- Missing, `StringFileWrapper.__setitem__ -> io.TextIOWrapper.tell`, `.seek`,
  `.write` (`string_file_wrapper.py:162:40`, `163:21`, `164:22`; 3 outside
  edges): sent to the referee (J5 against rule A; see below); the referee
  ruled for the auditor (README, "After Codex audit round 1", (a)):
  **applied**, +3 outside edges, J5 rewritten.
- False, `load_schema_model -> <builtin>.dict.get`
  (`schema_repair.py:100:47`): **applied**. The module is the client's,
  named by its `'module:ClassName'` string (the tests import their own
  modules); a call on the `__dict__` of a client object is opaque (B5;
  batch-6 ruling jsonpickle (c)). The traced edge moves to
  `json-repair.rejected.json`. -1 outside edge.
- Metadata, `schema_repair.py:132:29`: **applied**. The branch needs a
  pydantic below 2; the package admits `pydantic>=2` (`pyproject.toml:27`),
  so the `ValueError` there has no callee. No edge change:
  `schema_from_input -> <builtin>.ValueError` stays through 137:21.
- Metadata, the inheritance statement in `json-repair.audit.md:108`
  (`ContextValues` subclasses `Enum`, `utils/json_context.py:6`): right,
  and no edge depends on it (an `Enum` member load calls no package code);
  the audit file is not the writer's to edit, so it is noted here only.

### J5 against rule A (3 edges)

The question: is the package's own wrapper, the one that holds the
`io.TextIOWrapper` of `from_file`, a receiver of `__setitem__`, although no
program that uses the public API can make it one?

For the auditor's reading (the edges exist):
- Rule A: "every function, public or private, tested or not, reachable
  from the public API or not, keeps the out-edges of its body", and "Rule A
  is about whether a function runs ... It is not about which values reach
  its parameters; that is rule B."
- B1: "`self` in a method of class `C` is an instance of `C` ... limited to
  instances that the package or a client can create." The package creates
  this instance.
- B2: "The values of a parameter, and of what is fed from it, are client
  objects, the values that the package defines for that parameter's role,
  and the package's defaults." `fd` is one stored role, and the ledger
  already admits the `io.TextIOWrapper` for it in `__init__`, `get_buffer`
  and `_ensure_chunk_position`.

For J5 (no edge):
- B: "For a public function or method (rule C), the receiver and the
  arguments are what a client or the package can pass." The package never
  passes its wrapper to `__setitem__`, and a client cannot reach it:
  `repair_json` keeps the parser local.
- Clarifications, client control flow: "A witness must use the public API
  without modifying package internals"; batch-6 ruling (django-environ):
  "a path needs only a witness through the public interface." No such
  witness exists for this receiver.

My view: the README's text is closer to the auditor's. B1 asks only that
the package can create the instance, and B2 judges stored values per role;
J5 added a condition (that the instance can reach the method through the
public API) that no sentence states as a limit on receivers. The witness
sentences are about control flow and the combination of parameters, not
about which created instances count. I would accept the 3 edges if the
lead or the referee reads it so; the binding is no obstacle (`write` on a
read-only file fails inside the C method, the tabulate ruling).
