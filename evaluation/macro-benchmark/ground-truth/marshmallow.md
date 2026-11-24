# marshmallow: judgements of the ground truth

Global-rule audit, pass 1 (2026-11-15): 3 removed edges, 3 added
edges; 831 edges after correction. See the
complete audit (audit record `2026-11-15/README.md`).

Pass 2 (2026-11-16): 0 removed edges, 1 added edge; 832 current
edges. Source-site and provenance corrections are recorded in the
pass-2 audit (audit record `2026-11-15/pass-2/README.md`).

Release 4.4.0 (commit `a38b7f6`). Analysed source: `src/marshmallow/`
(`root = "src"`): 14 modules, 234 functions (no lambda), 65 classes.
`pyproject.toml:23` sets `requires-python = ">=3.11"`, so the supported
versions are 3.11 and later. The final classifier is not an upper bound. Current
4.4.0 metadata and CI establish CPython support; the 0.5.4 changelog
entry about PyPy testing does not establish current PyPy support. This
audit includes normal, `-O` and `-OO` modes under the round-four working
assumption (not an explicit user approval). Runtime source has no assertion,
`__debug__` or docstring-dependent branch, so these modes add no edge.

The ledger is `marshmallow.ledger`; the graph `marshmallow.json` is generated
from it. The trace edges that are not package edges are in
`marshmallow.rejected.json`.

## Architecture, as the ledger uses it

- **Fields** (`fields.py`). `Field` is the public base. The concrete classes
  are `Field`, `Raw`, `Nested`, `Pluck`, `List`, `Tuple`, `String`, `Url`,
  `Email`, `UUID`, `Integer`, `Float`, `Decimal`, `Boolean`, `DateTime`,
  `NaiveDateTime`, `AwareDateTime`, `Time`, `Date`, `TimeDelta`, `Dict`, `IP`,
  `IPv4`, `IPv6`, `IPInterface`, `IPv4Interface`, `IPv6Interface`, `Enum`,
  `Method`, `Function` and `Constant`. `Number` (abstract property
  `num_type`), `Mapping` (abstract property `mapping_type`) and the private
  `_TemporalField` (abstract `_make_object_from_format`) cannot be
  instantiated. `Integer`, `Float`, `Decimal` and `Dict` replace the abstract
  properties with class attributes (`int`, `float`, `decimal.Decimal`,
  `dict`), so the properties never run.
- **Schemas** (`schema.py`). `Schema` has the metaclass `SchemaMeta`
  (`ABCMeta`). `SchemaMeta.__new__` collects the declared fields and makes
  `opts` with `OPTIONS_CLASS` (`SchemaOpts`); `SchemaMeta.__init__` registers
  the class in `class_registry` and resolves the hooks. `Schema.from_dict`
  calls `type(name, (cls,), ...)`, which runs `SchemaMeta.__new__` and
  `SchemaMeta.__init__`.
- **Hooks** (`decorators.py`). `set_hook` puts a `defaultdict` in
  `__marshmallow_hook__`; `resolve_hooks` reads it. The package defines no
  hook method, so every processor and schema validator that `Schema` calls is
  client code.
- **OrderedSet** (`orderedset.py`) is `Schema.set_class`. It is a
  `collections.abc.MutableSet`: `|`, `&`, `-`, `|=` and `&=` run the mixins
  of `collections.abc`, which call back `OrderedSet.__init__` (through
  `_from_iterable`), `__iter__`, `__contains__`, `add` and `discard`.
- **`missing`** (`constants.py`) is the single `_Missing` instance. It is the
  default of `load_default`, `dump_default` and `get_value`, and
  `Method._serialize` returns it.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules. This section
shows how this ledger applies them.

**A. Edges are per function.** Every function keeps its body's edges. The
abstract stubs (`Validator.__call__`, `_TemporalField._make_object_from_format`,
`Number.num_type`, `Mapping.mapping_type`, the `types.RenderModule` and
`types.SchemaValidator` stubs) and `OrderedSet.pop` and `__reversed__` have
no package caller; only `OrderedSet.pop` has out-edges.

**B1. Receivers.** "Dispatch sets" below lists them. Public methods admit
constructible classes and concrete subclasses that inherit them. Private methods use
the package's actual call inputs; an uncalled private body uses the public-
parameter fallback. For example, `Number._format_num` receives Integer and
Float, while Decimal overrides it; `Number._validated` also receives
Decimal through its explicit `super()` call. Failed argument binding
enters no function. An initializer body that raises keeps the calls it
reaches, but failed construction supplies no completed receiver. Clients
do not reinitialize instances or reuse arbitrary half-changed objects.
`super()` calls go to the next class in the MRO (`Nested` for `Pluck`,
`Number` for `Integer`, `Float`, `Decimal`, `_TemporalField` for
`NaiveDateTime` and `AwareDateTime`, `Field` for the others).
`NoneOf.__call__` and `OneOf.__call__` never run on `ContainsNoneOf` and
`ContainsOnly`, which override `__call__`.

**B2. Arguments and stored values.** Broad `Any`, `object`, `type` and
`Callable` annotations do not admit arbitrary package objects. A client
assignment to a public attribute requires a documentation or test witness
for that role.

- A field receiver without a narrower type (`List.inner`, `Tuple`'s fields,
  `Dict`'s `key_field` and `value_field`, the `by_value` field of `Enum`, the
  declared fields of a schema) is any concrete field: the annotations are
  `Field | type[Field]`.
- Validators: `types.Validator` is a bare `Callable`. The package's own code
  puts `validate.URL` and `validate.Email` in a field's validators
  (`fields.py:1775, 1794`), and the docstrings pass `validate.Range`
  (`validate.py:58`) and document validators as `validate=`. So
  `And.__call__` calls every concrete validator's `__call__`.
- `OrderedSet` is a value of `only` and `exclude` only, because
  `Nested.schema` passes OrderedSets there (`fields.py:596-597`). It is not a
  value of `load_only`, `dump_only`, `partial` or URL `schemes`, although
  they share the annotation `types.StrSequenceOrSet` (judgement 2).
- `Nested(only=..., exclude=...)` refuses a set at construction
  (`fields.py:540-545`). The `only` and `exclude` of a bound `Nested` field
  become `OrderedSet`s only through `Schema.__apply_nested_option`
  (`schema.py:980`) and the copies of `List` and `Dict`. A bound public Field can be reused through `Schema.from_dict`; its shallow copy preserves these options. Thus `__apply_nested_option`'s `original_options` (`schema.py:975`) and `Nested.schema`'s `self.exclude` (`fields.py:578`) can both be `OrderedSet`s.
- The client callback return of `missing` stays opaque and does not admit it to `validate.Length` (judgement 3).
- The accessor of `Field.get_value` is `utils.get_value` or the bound
  `Schema.get_attribute` that `Schema._serialize` passes.

**B3. Not considered.** A field class passed as `Nested`'s `nested`; a
non-callable schema attribute named by a `Method` field; package objects as
enum values, client data, choices, comparables or validator inputs typed
`Any`, `Iterable` or `Sized`; the client callback return of `missing` does not create an exception for `Length`.

**B4. Concrete outside types.** `dict` for `Meta.include`, `Schema.fields`,
`dump_fields`, `load_fields`, the `fields` of `from_dict`, `set_value`'s
`dct`, and every value behind an `isinstance(..., dict)`; `datetime`, `date`
and `time` for the temporal fields (annotation `_D`); `re.Pattern`;
`decimal.Decimal`. An abstract `Mapping` (the value of a `Dict` field, the
data of `Schema._deserialize`) does not fix the class. Package-produced
values remain concrete: the default `json.loads` in `Schema.loads` builds
nested dicts, which flow through `Schema.load`, `_do_load`, `_deserialize`
and `Field.deserialize` to `Mapping._deserialize`. Its `value.items()`
calls at `fields.py:1700, 1704` therefore include `<builtin>.dict.items`
when a key or value field is configured. `Mapping._serialize` has no such
package-produced JSON input witness. Shipped stubs count as annotations;
this package ships none. Annotations take precedence over conflicting
documentation, and `Any` supplies no concrete type. An abstract annotation
does not fix a concrete outside class. `Schema.dict_class: type[dict]`
and its dict default justify dict methods; a configured outside constructor
remains client code. The default `json` renderer justifies `json.dumps` and
`json.loads`; client-selected render modules such as the tests' simplejson
and the upgrading guide's ujson remain opaque under B5.

**B5. Client objects are opaque.** The client's mappings, sequences, enum
classes, tzinfo objects, pre_load and post_load callables, default callables,
`Function` callables, `Method` methods, hook methods and render modules.

**C. Public.** `class_registry.py` and `error_store.py` say "This module is
treated as private API" (`class_registry.py:5-8`, `error_store.py:3-6`), so
their functions and `ErrorStore` are private. `_Missing`, `_TemporalField`,
`_resolve_field_instance` and `utils._get_value_for_key` are private by name.
Everything else that `__init__.py`, `fields.__all__` or a public module path
reaches is public.

## Judgement calls

These cases are not decided by the README. Each one is decided by the
nearest rule. "Lead" marks a ruling of the lead; the others stand for the
audit.

1. **`if __name__ == "__main__":` block** (`orderedset.py:84-89`). Lead:
   it counts. Rule A: a module keeps the edges of its body whether or not
   anything runs it, and the block runs when the module runs as a script
   (`python -m marshmallow.orderedset`), which is what it is there for (as a
   version branch that a supported version takes). The module node keeps the
   4 edges of the block: `OrderedSet.__init__`, `OrderedSet.__iter__`,
   `OrderedSet.__repr__` and `<builtin>.print`. No test runs it.
2. **`OrderedSet` for `types.StrSequenceOrSet` parameters.** Lead, B2: an
   abstract outside type names a package class only where the package
   implements it for that role (audit F2). `OrderedSet` implements
   `MutableSet` to be the package's `set_class` (the `only` and `exclude`
   sets); no code, test, documentation or example offers it for `partial`,
   `load_only`, `dump_only` or `schemes`, and the tests pass builtin sets
   there. So the `AbstractSet` arm of `Sequence[str] | AbstractSet[str]`
   does not bring it to those parameters. The writer's first decision
   (the annotation admits it) gave 4 more edges, now removed:
   `Schema._deserialize -> OrderedSet.__contains__` and `__iter__`
   (`schema.py:655, 664`) and `validate.URL.__init__ -> OrderedSet.__iter__`
   and `__len__` (`validate.py:209`). The OrderedSet edges of
   `Schema.__init__`, `_normalize_nested_options` and
   `__apply_nested_option` stay: `Nested.schema` passes OrderedSets as
   `only` and `exclude`. A bare `Iterable` or `Sized` (OneOf choices, NoneOf
   iterable, Boolean truthy) names no package value either; `Sized` with
   `missing` is not an exception: the test sends it through an opaque
   callback return (judgement 3).
3. **`missing` as the value of `validate.Length`.** The tests at
   `test_deserialization.py:1020-1025` return it from a client `Function`
   deserialize callback. Global B5 makes that result opaque; structural
   `Sized` compatibility alone does not supply a package value for B2.
   Remove `Length.__call__ -> _Missing.__len__` and
   `Length._format_error -> _Missing.__repr__`. The first was traced and
   now has a rejection reason; the second came only from reading.
4. **`Enum(by_value=fields.Method())`** (`fields.py:1962`). `by_value` is
   annotated `bool | Field | type[Field]`, so any field fits. An unbound
   `Method` field returns `missing` from `_serialize`, and `str()` of it runs
   `_Missing.__repr__`. The edge `Enum.__init__ -> _Missing.__repr__` comes
   from reading only.
5. **`_resolve_field_instance`'s `cls_or_instance()`** (`fields.py:103`).
   The callees are the `__init__` of every field class that can be called
   without arguments. `Nested`, `Pluck`, `List`, `Tuple`, `Enum` and
   `Constant` need positional arguments: the call raises `TypeError` before
   their `__init__` body runs, so they are excluded.
6. **Calls of classes outside the package.** A call of a class is named by
   the class (`uuid.UUID`, `decimal.Decimal`, `datetime.timedelta`,
   `ipaddress.IPv4Address`, `collections.defaultdict`). `self.enum(val)`
   (`fields.py:1984`) calls the client's `Enum` subclass: client code, no
   edge (the trace drops it too).
7. **Inherited outside methods use the concrete receiver.** At
   `fields.py:1278`, keep `datetime.datetime.strftime`,
   `datetime.date.strftime` and `datetime.time.strftime`. Sharing a method
   implementation does not merge different receiver classes. The same
   rule adds `collections.defaultdict.items` at `error_store.py:33`:
   `Mapping._deserialize` creates that error mapping at fields.py:1684
   before `copy_containers` normalizes it. Plain dicts remain possible.
8. **`super().__init__()` of `SchemaMeta`** (`schema.py:153`). `ABCMeta`
   defines no `__init__`; `type.__init__` runs. It is named
   `abc.ABCMeta.__init__`, through the nearest base outside the package.
9. **Exceptions without `__init__`.** `RegistryError(...)` is
   `<builtin>.NameError.__init__`; `StringNotCollectionError(...)` is
   `<builtin>.TypeError.__init__` (MRO: `MarshmallowError`, `TypeError`).
10. **Callbacks of `collections.abc` and `copy`.** The op sites of OrderedSet
   arithmetic get the package methods that the mixins call back (22 sites
   have package callees that are not candidates). `copy.deepcopy` of a field,
   or of the dict of declared fields, calls back `Field.__deepcopy__`.
   `iter()` of an OrderedSet in a generator expression that `Set.__and__` or
   `__sub__` builds runs in the scope that makes the generator (the operator
   site); the `in` tests of that generator run inside `OrderedSet.__init__`.
11. **`TYPE_CHECKING`.** The imports under `if typing.TYPE_CHECKING:`
    (`class_registry.py:18-21`, `context.py:37-38`, `fields.py:28-29`,
    `schema.py:42-43`, `validate.py:12-13`) do not run. `class_registry.py:21`
    subscripts `type[Schema]`: no package callee.

`Schema.__apply_nested_option` also calls `OrderedSet.__len__` at the
truth test of `original_options` (schema.py:975). A public bound Field can
be reused in another `Schema.from_dict`; `Field.__deepcopy__` shallow-copies
it (fields.py:244), preserving an OrderedSet in its only/exclude state.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `OrderedSet.__eq__` | 191 | `OrderedSet` is unhashable and no compared value is one | nowhere |
| `OrderedSet.__iter__` | 125 | the iterated value is not an OrderedSet | `schema.py:430, 954, 966, 1013`, `orderedset.py:76, 80` (2), `81` |
| `OrderedSet.__len__` | 186 | the tested value is not an OrderedSet | `fields.py:578`, `schema.py:975, 1002, 1008`, `orderedset.py:67, 74, 76, 80` (4) |
| `OrderedSet.__contains__` | 32 | the right operand of `in` is not an OrderedSet | nowhere (`schema.py:655` rejects it in its entry; the `in` tests of `collections.abc` reach it from `OrderedSet.__init__`) |
| `_Missing.__bool__` | 192 | the package never tests `missing` for truth | nowhere (`schema.py:527:40` rejects it: `x or missing` returns `missing` untested) |
| `_Missing.__len__` | 197 | no admitted value provenance supplies `missing` to `len()` | nowhere; `validate.py:431` explicitly rejects the callback return |
| the five `__repr__` (`_Missing`, `Field`, `OrderedSet`, `Schema`, `Validator`) | 50 each | the formatted value is no package object | `fields.py:235, 237, 239`, `schema.py:1009` (2), `validate.py:69`; the explicit `str()`, `print()` and `.format()` sites decide them in their own entries |

531 sites have at least one candidate decided by a default: 520 have no
ledger entry, and 11 have an entry that decides other candidates. Every
explicit site has its own entry; where a default candidate is a callee
there, the entry accepts it. The 1,893 sites without ledger entries comprise
those 520 sites and 1,373 implicit sites without package candidates. The
ledger also lists 13 implicit sites without candidates, including callbacks
through inherited set operations.
The op sites of OrderedSet arithmetic have no candidates; their callees are
in "Dispatch sets" and judgement 10.

## Exclusions

| Site | Excluded | Why |
|---|---|---|
| `fields.py:103:31` `cls_or_instance()` | the `__init__` of `Nested`, `Pluck`, `List`, `Tuple`, `Enum`, `Constant` | required positional arguments (judgement 5) |
| `fields.py:103:31` | `Number.__init__` | `Number` is abstract; it runs only through its subclasses |
| `validate.py:76:26` `validator(value)` | `Validator.__call__` | the abstract stub |
| `validate.py:76:26` | `URL.RegexMemoizer.__call__` | keyword-only arguments; never a validator |

## Dispatch sets

| Site | Callees | Size |
|---|---|---|
| `self._serialize(...)` in `Field.serialize`; `inner`, `field`, `key_field`, `value_field`, `self.field` `._serialize` (`fields.py:328, 768, 852, 1663, 1674, 1962, 1976`) | the `_serialize` of `Field`, `Nested`, `Pluck`, `List`, `Tuple`, `String`, `UUID`, `Number`, `_TemporalField`, `TimeDelta`, `Mapping`, `IP`, `IPInterface`, `Enum`, `Method`, `Function`, `Constant` | 17 |
| `self._deserialize(...)` in `Field.deserialize`; `self.field._deserialize` in `Enum` (`fields.py:380, 1981`) | the 17 classes above with `_deserialize`, plus `Boolean`, `NaiveDateTime`, `AwareDateTime` | 20 |
| `._bind_to_schema(...)` on any field (`fields.py:760, 840, 1644, 1650`, `schema.py:1073`) | `Field`, `List`, `Tuple`, `_TemporalField`, `Mapping`, `Method` | 6 |
| `self._validate_missing` (`fields.py:368`) | `Field`, `Constant` | 2 |
| `self._format_num`, `self._to_string` in `Number` (`fields.py:977, 990, 991`) | `Number`'s and `Decimal`'s | 2 each |
| `self._validated` in `Number._deserialize` (`fields.py:994`) | `Integer`, `Float`, `Decimal` | 3 |
| `self._make_object_from_format` (`fields.py:1289`) | `DateTime`, `Time`, `Date` | 3 |
| `format_func(value)`, `func(value)` (`fields.py:1277, 1288`) | the six values of each table of `DateTime`, `Time`, `Date` | 6 each |
| `self._repr_args()` (`validate.py:30`) | `And`, `URL`, `Validator` (for `Email`), `Range`, `Length`, `Equal`, `Regexp`, `Predicate`, `NoneOf`, `OneOf` | 10 |
| `validator(value)` in `And.__call__` (`validate.py:76`) | the `__call__` of the 12 concrete validators | 12 |
| `cls_or_instance()` (`fields.py:103`) | 16 `__init__` (judgement 5) | 16 |
| `accessor_func(...)` (`fields.py:264`) | `utils.get_value`, `Schema.get_attribute` | 2 |
| `getter_func(data)` (`schema.py:522`) | `Schema._deserialize.getter`, `functools.partial.__call__` | 2 |
| `set_class(...)` (9 sites), `self.dict_class()` (6 sites), `klass.OPTIONS_CLASS(meta)`, `dict_cls(...)`, `schema_class(...)` | `OrderedSet.__init__`, `<builtin>.dict`, `SchemaOpts.__init__`, `<builtin>.dict`, `Schema.__init__` | 1 each |
| `self.num_type(value)`, `self.mapping_type(...)` | `<builtin>.int`, `<builtin>.float`; `<builtin>.dict` | 2; 1 |
| the IP and interface constructors (`fields.py:1825, 1887`) | `ipaddress.ip_address`, `IPv4Address`, `IPv6Address`; `ip_interface`, `IPv4Interface`, `IPv6Interface` | 3 each |

The value sites without package callees are the client callables: default
and load_default callables, pre_load and post_load, `nested()`, the
`Method` and `Function` callables, the hook processors and schema
validators, `Predicate`'s method, the enum class.

## Trace

The trace (Python 3.14.9; 1192 tests passed) has 702 edges. After 16
rejections, its 686 raw edges confirm 688 graph edges through aliases.
The rejections in `marshmallow.rejected.json` are:

- client callback exceptions: `Schema._do_load` calls
  `err.normalized_messages()` at schema.py:885,938 on an exception from a
  client pre_load/post_load hook; B5 keeps it opaque;
- client callback returns: `Length.__call__ -> _Missing.__len__` comes
  from the client deserialize callback of judgement 3;
- client callbacks and objects: `int`, `str`, `str.strip` as pre_load and
  post_load; `Mapping._serialize -> <builtin>.dict.items` on the client's
  abstract mapping (`Mapping._deserialize` instead has the package JSON
  witness above);
  `collections.OrderedDict` as `dict_class`; `simplejson` as
  `render_module`; `zoneinfo.ZoneInfo.utcoffset` of a client datetime; a
  field class passed as `nested` (`Nested.schema -> Field.__init__`);
- `Nested.schema -> abc.GeneratedSchema`. Lead: a naming artefact of the
  trace, not a client callback. The tracer names a class that the package
  creates at run time with `type()`: `Schema.from_dict` makes it, and
  `type()` takes its `__module__` from the frame of `abc.ABCMeta.__new__`.
  The call is the instantiation of a `Schema` subclass; the graph has the
  `Schema.__init__` edge that it runs;
- `_resolve_field_instance -> <builtin>.BaseException.__init__`. Ruling
  (b): lead, withdrawn: macro README, implicit sites. `raise
  _FieldInstanceResolutionError` without a call (`fields.py:102, 105`) is an
  implicit site, which has only package callees (macro README, "Call sites
  and candidates"; the five development ground truths use the same rule).
  The class (`exceptions.py:69`) defines no `__init__`; the first `__init__`
  of its MRO (`MarshmallowError`, `TypeError`, `Exception`, `BaseException`,
  `object`) is `<builtin>.TypeError.__init__`, outside the package, so the
  site adds no edge. The other `raise` without a call in the package,
  `raise exc` (`schema.py:942`), raises an instance and instantiates
  nothing.

## Tools

1. `check.py <name>` printed only totals. The README says that the size
   report shows where a few candidates make many sites; it did not. The
   counts per candidate here come from the skeleton. Fixed: the size report
   now lists each candidate of 50 or more sites, with its number of sites.
2. `sites.py` (`_last_name`) dropped a subscripted base class, such as
   `class String(Field[str])`. So `String()` and `Raw()` (`fields.py:1945,
   1952`) got no candidate `Field.__init__`, and the ledger added it beyond
   names. Fixed: it is now a candidate there. The fix also proposes the
   inherited `Field.__init__` (and `Number.__init__`) where a standard-library
   class or a validator has the name of a field (`uuid.UUID`,
   `decimal.Decimal`, `validate.Email`: `fields.py:922, 923, 1113, 1121,
   1124, 1793`); the ledger rejects them with the reason of the field's own
   `__init__`.
3. The tracer records no caller for a generator function that `iter()`
   starts: `OrderedSet.__iter__` is in `executed` but has no in-edge in the
   trace. The 9 edges to it in the graph are from reading only.
4. `sites.py` marks some calls of module attributes as value sites:
   `fields.py:1768` (`validate.URL`), `schema.py:155`
   (`class_registry.register`) and `decorators.py:240`
   (`functools.partial`). Each has a note.

## Functions that no site calls

- Public API: the decorators, `Schema.validate`, `dumps`, `loads`,
  `ValidationError.messages_dict`, `Context`'s methods, `OneOf.options`, the
  constructors of fields and validators that only clients call,
  `Field.__repr__`, `OrderedSet.__eq__`, `_Missing.__bool__`, `__copy__`,
  `__deepcopy__`.
- Never run in the tests: the abstract stubs (`Validator.__call__`,
  `_TemporalField._make_object_from_format`, `Number.num_type`,
  `Mapping.mapping_type`), the Protocol stubs of `types.py`,
  `OrderedSet.pop` and `OrderedSet.__reversed__`, and `And._repr_args`.

## Statistics

| | Count |
|---|---|
| All AST sites | 2,723: the 1,337 sites below plus 1,386 implicit sites without package candidates |
| Explicit or candidate-bearing sites | 1337 (756 call, 25 decorator, 1 class, 98 iter, 56 op, 102 getitem, 33 setitem, 1 delitem, 14 getattr, 194 truth, 57 format) |
| Sites with candidates / value sites | 944 / 71 |
| Ledger entries | 830 (756 call, 25 decorator, 1 class, 14 getattr, 14 op, 8 truth, 7 format, 5 iter) |
| Callee lines / rejection lines (`reject *`) / exclusion lines / notes | 1072 / 223 (160) / 4 (9 nodes) / 175 |
| Default rejections | 7 lines, 11 candidates, deciding 531 sites |
| Edges | 832: 459 in the package, 373 to 116 callees outside |
| Edges that the trace confirms | 688 of 832 (82.7%) |
| Edges only from reading | 144 (133 in the package, 11 outside) |
| Trace edges rejected | 16 |
| Functions that the tests run | 224 of 234 |
