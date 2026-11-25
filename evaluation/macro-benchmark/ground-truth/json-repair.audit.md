# json-repair: independent audit of the ground truth

Release v0.64.2, commit `f13a96b9c7ef0f590bc647e7c5424560b948462e`, root `.`,
package `src/json_repair` (module names `src.json_repair.*`). Audited files,
uncommitted in the worktree on 2026-11-22: `json-repair.ledger`,
`json-repair.json` (747 edges: 392 inside, 355 outside),
`json-repair.added.json` (32 edges), `json-repair.rejected.json` (9 edges)
and `json-repair.md` (J1 to J14). `check.py json-repair` reports no errors;
the trace confirms 715 of 747 edges; 141 of 144 functions run.

I judged the files by the README's rules (A, B1 to B5, C, the
clarifications of 2026-11-15 and the rulings for batch 6). I read the
package source, its tests, `README.md`, `docs/` and `examples/` as data, and
the dependency sources under `deps/json-repair/` (the dependency sources of the audit records) as
text. I ran no analysis tool on the package and read no analysis output.
The only commands that touched the package were the benchmark's own
`check.py --skeleton`, `--report` and `--report --default`.

**Result.** The blind sample of 142 sites agrees with the ledger at every
site. The exhaustive checks found one missed callee at two sites (F1,
+2 edges if the lead accepts it) and two wording faults (F2, F3, no edge
change). I agree with the writer on J4, J5 and J11, the three calls that
ask for a ruling, and on every other judgement except the reason of J8.

## Findings

| Id | Severity | Kind | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|---|
| F1 | medium (needs the lead's ruling) | missed edge | `schema_repair.py` 315:60 and 337:63 `copy.deepcopy(value)`: add `-> src.json_repair.utils.constants.MissingValueType.__deepcopy__`, so `SchemaRepairer._repair_union -> MissingValueType.__deepcopy__` and `SchemaRepairer._repair_type_union -> MissingValueType.__deepcopy__` | See "F1" below. The tests pass `{"a": MISSING_VALUE}` as `value` to the public `SchemaRepairer.repair_value` (`tests/test_schema_repairer.py:479-480`). B2 admits a package value that the tests pass in a role, and `value: Any` names no type that could exclude it (B4). With a client schema `{"anyOf": [{"type": "object"}]}` or `{"type": ["object", "null"]}`, `repair_value` (`schema_repair.py:265-298`) reaches `_repair_union` or `_repair_type_union` with that dict, and `copy.deepcopy` calls `MISSING_VALUE.__deepcopy__` back (`utils/constants.py:8`). J8's reason, "not considered (B3)", conflicts with B2's test clause: B3 excludes values that the package never produces for a role, not values that its tests pass there. | +2 | likely |
| F2 | low (wording) | false reason | J8 in `json-repair.md`, notes at 315:60 and 337:63 | Whatever the lead rules on F1, the reason must change. If F1 is rejected, the reason is B5 (a client container is opaque "whatever it is built from", h11 `h11.ledger:644`), not B3. The claim "no package container holds MISSING_VALUE" is true, but a container from the tests does. | 0 | certain |
| F3 | trivial (wording) | false detail | default rejection of `StringFileWrapper.__getitem__` ("... schema value or Match"); notes at `parser_schema.py` 10:2 and 18:2 ("CPython 3.10 to 3.14") | The package makes no `re.Match` (it imports no `re`). `requires-python = ">=3.10"` has no upper bound, and CPython 3.15 (released) keeps the local `wrap` in `dataclasses.dataclass`, so "3.10 and later" is the correct range. | 0 | certain |

### F1: the evidence and the counter-argument

Witness, through the public API only:
`SchemaRepairer({}, None).repair_value({"a": MISSING_VALUE}, {"anyOf": [{"type": "object"}]}, "$")`.
`resolve_schema` returns the dict; the value is not `MISSING_VALUE` itself,
so line 273 does not return; `"anyOf"` leads to `_repair_union` (288), and
`copy.deepcopy({"a": MISSING_VALUE})` (315) deep-copies the item through its
`__deepcopy__`. `{"type": ["object", "null"]}` takes the same path through
`_repair_type_union` (298, 337). The tests that pass the container are
`assert repairer.repair_value({"a": MISSING_VALUE}, {}, "$") == {"a": ""}` and
the same with `{"allOf": []}` (`tests/test_schema_repairer.py:479-480`). The
package also tests the copy behaviour itself (`test_missing_value_deepcopy`,
`:17-18`). The schema is a client dict with any content, and each JSON
Schema keyword above is documented input.

The counter-argument for the writer's result is B5: "an iterable that the
client supplies is opaque ... whatever it is built from" (h11, rejection of
`Headers.__getitem__` at `h11.ledger:644`; README B5, `itertools.chain`).
In my opinion B2 decides this case, for three reasons. The h11 role admitted
no package value, but here the tests pass exactly this container to this
public parameter. The package treats the container as a concrete `dict`, not
as an opaque object: `normalize_missing_values` and `_repair_object` walk it
after `isinstance` checks (`schema_repair.py:109-117`, `465`). And
`copy.deepcopy` is a library function that the package calls on the value,
not a method of a client object. The callback rule then makes
`__deepcopy__` a callee of the package site. The change is 2 edges, so the
lead can rule alone ("Rulings for batch 6").

`MissingValueType.__repr__` stays rejected. With the container shape that
the tests pass (a dict), every path of `repair_value` replaces
`MISSING_VALUE` (`normalize_missing_values`, `_fill_missing`, or a nested
`repair_value`) before a value is formatted or validated. Only a list such as
`[MISSING_VALUE]` under `{"type": "array"}` without `items` keeps it
(`_repair_array`, 389-443), and jsonschema's error message would then call
`repr` on it. No test passes such a list to `repair_value`, so I do not
propose that edge.

## Step 1: blind re-derivation

I made the skeleton without the ledger in
`$TMPDIR/audit-json-repair/` (a copy of `projects.toml` and of
`projects/json-repair`). It has 2172 sites: 1219 explicit (1210 call,
9 decorator), of which 72 are value sites, and 953 implicit. Explicit calls
dominate, and two candidates (`StringFileWrapper.__getitem__` at 552 sites
and `__len__` at 400) dominate the implicit sites. So I drew by kind: I
ordered the sites module by module in (line, column) order, and with
`rng = random.Random(20261122)` I drew `rng.sample(explicit, 35)` from the
1147 explicit non-value sites, then `rng.sample(implicit, 35)` from the 953
implicit sites. I added all 72 value sites. I wrote the callees of all 142
sites (file `blind-answers.txt` in that directory) before I opened any file
of the writer.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random explicit (calls, one decorator) | 35 | 35 | 0 |
| Random implicit (truth, getitem, op, iter, format, with) | 35 | 35 | 0 |
| Value sites (64 `self.log`/`parser.log`, 2 `parse_element()`, 3 `skip_to_character()`, 2 `@dataclass(frozen=True)`, 1 `validator_cls(...)`) | 72 | 72 | 0 |
| **Total** | **142** | **142** | **0** |

Before opening the ledger I had decided the same global questions as the
writer, with the same answers: `json_str` is a `str` or a
`StringFileWrapper` at every parser site outside an `isinstance(..., str)`
guard (J1); `log` is `_log` or the lambda (J2); the two values of
`parse_element` and of `skip_to_character` (J12); the streams (J3); the
validator class (J4); `__setitem__` (J5); `dataclasses.dataclass.wrap` (J10).
Of the 35 implicit sites, 33 have only defaulted candidates, and the
ledger has no entry for them (the defaults decide them). Two have entries:
`parse_object.py` 342:38 accepts `__getitem__`, and `json_repair.py` 326:10
rejects the `_JsonContextEntry` methods for a file's `with`. My answer at
all 35 matches the ledger. The
writer missed no edge, has no edge that cannot happen, and no site differs
in naming.

## Step 2: exhaustive checks

**Dispatch.** Twelve classes. Only `SchemaDefinitionError(ValueError)` has a
base, and no package class has a package subclass, so every method call on
`self` has one receiver class. `_JsonContextEntry` is private and made only
by `JsonContext.enter` (`json_context.py:39`). Every `self.context.*` call in
`JSONParser` and the `parse_*` modules reaches `JsonContext`, and every
`*.clear()` on a list is `<builtin>.list.clear` with `JsonContext.clear`
rejected. Every row is in the ledger.

**`StringFileWrapper` candidates.** I listed every `json_str` expression
of the package (`rg json_str`). 30 subscripts and 14 `len()` calls take a
parser's `json_str` (or the alias in `_try_parse_simple_quoted_string`)
outside a `str` guard, and the wrapper itself adds `self[i]` (91) and
`len(self)` (97, 119, 160). That gives 31 `__getitem__` and 17 `__len__`
sites, the same 48 sites that the ledger accepts. The guarded sites
(`json_parser.py:196`, `215`, `217`, `232`; `parse_string.py:63`, `66`)
correctly reject them. No truth test, iteration or `in` takes `json_str`.

**Defaults.** `--report json-repair --default <candidate>` for each of the
four defaults: 521, 383, 25 and 111 sites. I read the explicit sites of each
(the `enumerate`, `set`, `min`, `max`, `any`, `all`, `dict`, `list`,
`tuple`, `iter`, `print` and `str` calls). None takes a wrapper, a
formatted `MISSING_VALUE` or an item assignment of a wrapper.
`__setitem__` is never reached by the package: correct. For
`MissingValueType.__repr__`, see F1 (the default holds).

**Functions with no caller.** `MissingValueType.__repr__` (correct),
`MissingValueType.__deepcopy__` (F1), `ObjectComparer.__init__` (correct:
the class is used only through its two static methods) and
`StringFileWrapper.__setitem__` (correct).

**Special methods.** `__enter__` and `__exit__` of `_JsonContextEntry` at the
four `with self.context.enter(...)` sites and through `ExitStack` (J9):
correct. The three `with Path(...).open()` sites reject them: correct.
Dataclass and `NamedTuple` rules: `StringParseState()`,
`ObjectSchemaConfig(...)` and `ArraySchemaConfig(...)` have no edge, and
`MissingValueType()` has none (`object.__init__`): correct.

**Binding check.** I checked every call of a package function against its
signature: the forwarding methods of `JSONParser`, the two `JSONParser(...)`
and the `SchemaRepairer(...)` calls, `load`/`loads`/`from_file`/`repair_json`
with their keywords, the helpers of `parse_object.py` and `parse_string.py`
(four to six positional arguments each), `classify_object_value_comma` and
both values of its callable (`(character, idx=0)`), and `repair_or_drop`.
All bind. No call is unbindable.

**Value sites.** All 72 are in the sample; each note gives the source of the
values.

**Outside callees.** I read every entry with an outside callee. The names
follow the micro-benchmark rules and the trace's names or aliases:
`io.TextIOWrapper.tell/seek/read` (aliases of `_io.TextIOWrapper.*`),
`pathlib.Path` and `pathlib.PosixPath.open` (alias of the traced
`pathlib.Path.open`) with `pathlib.WindowsPath.open` (J7, README precedent),
`pydantic.BaseModel.model_json_schema` (alias of
`pydantic.main.BaseModel.model_json_schema`),
`pydantic.fields.FieldInfo.is_required`,
`jsonschema.validators.validator_for`, `Draft202012Validator` and its
`evolve`, `is_valid` and `validate` (checked in jsonschema 4.26.0:
`validators.py:1396-1408`, `859`, `339`, `448`, `485`; pydantic's
`json_schema.py:441-443` emits no `"$schema"`), `typing.cast`,
`typing.overload`, `enum.auto`, `contextlib.ExitStack` and `.enter_context`,
`json.JSONDecoder` and `.raw_decode`, `copy.deepcopy`,
`importlib.import_module`, `argparse.ArgumentParser.*`, `sys.exit`,
`dataclasses.dataclass`, `.wrap` and `.field`. The outside callees of client
objects are absent, as B5 requires: client streams,
`field.default_factory()`, the client module of `load_schema_model`, a
client mapping in `match_pattern_properties` and the `default=` of
`json_dumps_args`.

**Rejected trace edges (9).** Seven `_io.StringIO.*` edges from
`StringFileWrapper.__init__`, `get_buffer` and `_ensure_chunk_position`, and
`cli -> _io.StringIO.read`. These are streams that the tests pass or put in
place of `sys.stdin`, so they are client objects (B5). The ninth is
`_add_pydantic_field_metadata -> <builtin>.list`, the default factory of a
test model, a client callback. All nine rejections are correct.

**Added edges (32).** I read each one: the module code under `__main__`,
the wrapper sites of J1, the log callees of J2 that the tests did not
reach, the default `parser.skip_to_character` of J12, `WindowsPath.open`,
`sys.stdin.read`, the two `ValueError`s of the missing optional
dependencies, and the body of `__setitem__` (rule A). All are possible.

## The writer's judgement calls

- **J1 to J3, J6, J7, J9, J10, J12 to J14**: supported by the nearest rules
  (B1, B2 annotations, B4 for `Any` with documentation and for `TypedDict`,
  B5, the callback rule, the `Path` clarification, the dataclass and
  `__main__` conventions). I agree.
- **J4 (validator class): I agree.** The nearest rule decides it: B5, "when
  library code picks an object from the client's configuration, the
  library's defaults and the configurations that the package documents are
  in scope; any other configured class is client code". The aiocache
  sentence of B2 (a client string that selects a method names what the
  package, its tests and its examples pass) gives the same answer. Nothing
  in the package, its tests, docs or examples sets `"$schema"`, and
  pydantic emits none. So the only callee is
  `jsonschema.validators.Draft202012Validator`, the `_LATEST_VERSION` of
  every admitted jsonschema release (4.21 and later), with its `evolve`,
  `is_valid` and `validate`. `evolve` keeps the class (`default=self.__class__`).
- **J5 (`__setitem__`): I agree.** B1 limits the receivers to wrappers
  that can reach the method. The package never calls `__setitem__`, and
  its own wrappers stay inside the parser that `repair_json` keeps local.
  So only a wrapper that a client builds arrives there. Its `fd` is a client
  stream: `TextIO` is an abstract typing class and fixes no concrete type
  (B4), so the stream is opaque (B5). The four `self.fd` calls have no
  callee. The body keeps `isinstance`, `len` and `__len__` (rule A). No new
  rule is needed.
- **J8: the result needs the lead's ruling, and the reason is wrong (F1,
  F2).**
- **J11 (`__package__` import): I agree.** README "Ground-truth
  conventions", Scope: module names are relative to the entry's root, so
  the file `src/json_repair/json_repair.py` is the node
  `src.json_repair.json_repair`. The test environment imports it under
  that name, so `__package__` is `src.json_repair` there. If the package is
  imported as `json_repair`, Python makes a second module object from the
  same file, and the same source function runs. The smallest extension of
  the rules is that a node is a function of the analysed files, named under
  the entry's root, whatever name the import used. It agrees with the README
  rule "one class reached through two import paths is one callee".

## Cases for the lead

1. F1: whether a package value that the tests pass inside a client
   container (B2) is reached by library code that walks the container
   (`copy.deepcopy`), or whether the container is opaque as in h11 (B5).
   I recommend the first answer: +2 edges.

## The README and the tools

- The README decided every other case, and the tools worked as described.
  I confirm the writer's remark that `check.py --report <name> --default
  <candidate>` also prints the explicit sites of the other defaults.
- B5's sentence "whatever it is built from" (via h11) and B2's test clause
  can disagree when a test passes a package value inside a client
  container. One sentence in B2 or B5 would settle F1 for later packages.
