# marshmallow: independent audit of the ground truth

Historical audit. The global-rule audit of 2026-11-15 (audit record `2026-11-15/README.md`)
records the later corrections and current graph counts.

Release 4.4.0, commit `a38b7f6842042e65fd1a485ed152ca99f87880c0`, analysed
source `src/marshmallow/` (14 modules, 234 functions, 65 classes). Audited
files: `marshmallow.ledger` (830 entries), `marshmallow.json` (835 edges: 465
in the package, 370 outside), `marshmallow.rejected.json` (15 edges) and
`marshmallow.md`, as they are in the worktree `feat/heldout` before the
writer applies this audit. `check.py --benchmark-dir macro-benchmark-heldout
marshmallow` reports no errors. The trace (Python 3.14.9, 1192 tests passed)
has 702 edges and confirms 687 graph edges; 148 come from reading only. 54
nodes have no caller (14 modules, 40 functions).

I judged the files by the scope rules of `macro-benchmark/README.md` (A,
B1-B5, C) and the edge and name rules of `micro-benchmark/README.md`. I read
the source, the tests, the docs and `CHANGELOG.rst` as data. I did not run
the package or any analysis tool.

## Summary

The ledger is complete and precise. The blind sample found no writer error.
I found no missing edge and no edge that cannot happen under the current
rulings. Two findings change edges and need the lead: F1 (`raise` of a
package class, +1 edge) and F2 (the writer's judgement 2, -4 edges). Two
findings change names or notes only (N1, W1).

| Change | Edges |
|---|---|
| F1 accepted | +1 outside (`_resolve_field_instance -> <builtin>.TypeError.__init__`); 1 rejected trace edge less |
| F2 accepted | -4 in the package |
| Both | 832 edges (461 in the package, 371 outside); the trace then confirms 688 |

## Findings

| Id | Severity | Kind | Site or edge | Evidence | Edges | Recommendation |
|---|---|---|---|---|---|---|
| F1 | medium | needs a ruling (the two READMEs conflict); writer missed an edge if the micro rule holds | `fields.py:102` and `:105` `raise _FieldInstanceResolutionError` in `_resolve_field_instance` | The micro-benchmark README ("Instantiation of a snippet class") says that `raise Cls` without parentheses instantiates the class and that the edge goes to the first `__init__` of its MRO, named through the nearest class outside the snippet (`<builtin>.Exception.__init__` is its own example). The MRO is `_FieldInstanceResolutionError`, `MarshmallowError`, `TypeError`, ... (`exceptions.py:11, 69`), so the edge is `-> <builtin>.TypeError.__init__`. The trace has it (`<builtin>.BaseException.__init__`, alias `<builtin>.TypeError.__init__`; the tests make List raise it). The macro README says "An implicit site has only package callees", and the writer rejected the trace edge on that sentence (`marshmallow.rejected.json`, `marshmallow.md` "Ruling (b): lead, withdrawn"). The lead's audit brief states the micro rule: "a `raise` of a package class instantiates it". The two rules disagree only for a package class whose `__init__` is outside the package; `raise StopIteration` (an outside class) adds no edge under both. | +1 | Follow the micro rule: add the edge, drop the rejected entry. The tools cannot hold it now: `sites.py` makes a `raise` site only when the class has a package candidate, and `check.py` refuses an outside callee at an implicit site. Either let a `raise C` site of a package class carry its outside `__init__` (as for `call`, which the site table already says), or state in the macro README that this case adds no edge. marshmallow is the only held-out package with such a `raise`. |
| F2 | medium | scope (B2): edges outside the values that reach the sites | judgement 2: `OrderedSet` for the `types.StrSequenceOrSet` parameters. Edges `Schema._deserialize -> OrderedSet.__contains__` (`schema.py:655:61`) and `-> OrderedSet.__iter__` (`664:49`), `validate.URL.__init__ -> OrderedSet.__iter__` (`validate.py:209:44`) and `-> OrderedSet.__len__` (`209:56`) | `StrSequenceOrSet` is `Sequence[str] \| AbstractSet[str]` (`types.py:15`): two library ABCs, not a package base class. B2 admits a package value through "a base class that the package implements for that purpose", the documentation, the defaults, or the package's own code, tests or documented examples. The tenacity audit (`tenacity.audit.md:463-479`) read the base-class clause as the package's base class of the role and refused the literal "anything that fits the annotation" reading. B4 lists abstract types (`Mapping`, `Iterable`, a Protocol) as fixing no class, and the writer itself treats `Iterable` and `Sized` as naming no package value (judgement 2, last sentence) - `AbstractSet` is the same kind of type. No package code passes an `OrderedSet` as `partial`, `load_only`, `dump_only` or `schemes`: `Nested.schema` passes lists for `load_only`/`dump_only` (`fields.py:598-599`); the `partial` of `_deserialize` is the client's value or the list `sub_partial` (`schema.py:663-668`); `fields.Url` passes the client's `schemes` (`fields.py:1771`). The tests pass builtin sets as `schemes` (`tests/test_validate.py:208-269`, `tests/test_deserialization.py:989`) and no `OrderedSet` anywhere but `set_class` (`tests/test_fields.py:340`). The cachetools precedent that the writer cites rests on documented examples that pass caches as `cache`, not on the `MutableMapping` annotation alone. The `OrderedSet` edges of `only` and `exclude` stay: `Nested.schema` passes them (`fields.py:596-597`, after `schema.py:980`). | -4 | Remove the 4 edges. Reject `OrderedSet.__contains__` at 655:61 and `OrderedSet.__iter__` at 664:49, 209:44, 431:29, 432:29, and `OrderedSet.__len__` at 209:56 (the edge `Schema.__init__ -> OrderedSet.__iter__` stays through 430:16). Update the ledger header (lines 9-13), the reasons of the `__iter__` and `__contains__` defaults, the notes at 954:77, 431:29, 432:29, and `marshmallow.md` (B2 bullet 3, judgement 2, the `__iter__`/`__len__`/`__contains__` rows of "Default rejections"). |
| N1 | low | naming only | `schema.py:192:53` `hook_config.items()` and `schema.py:972:54` `nested_options.items()`: `-> <builtin>.dict.items` | Both receivers are always a `collections.defaultdict` (`decorators.py:248`, `schema.py:968`). The micro rule names a method through "the public import path of the class of the instance" (`collections.UserDict.update`, not the defining class), and cachetools uses `collections.OrderedDict.get`. The trace alias list of `<builtin>.dict.items` has `collections.defaultdict.items`, so the checker accepts either name. Where a site has both a `dict` and a `defaultdict` receiver (`error_store.py:33:71`: `copy_containers` of the `defaultdict` errors that `Mapping._deserialize` raises, `fields.py:1684, 1716`; `merge_errors` only sees the plain copies), one name for one function is the writer's rule of judgement 7; keep it there. | 0 (2 renamed) | Name the two edges `collections.defaultdict.items`, or record in `marshmallow.md` that the ledger names inherited `dict` methods by their defining class everywhere. |
| W1 | low | wrong note | `utils.py:36:66` note of `datetime.tzinfo.utcoffset(datetime) -> datetime.timezone.utcoffset` | The note lists "the `dt.UTC` of `utils.timestamp` (`utils.py:69`)" as an aware datetime that reaches `is_aware`. `timestamp` calls `is_aware(value)` before it replaces the tzinfo (`utils.py:67-69`); the UTC datetime goes only to `value.timestamp()`. The edge holds through the other sources of the note (`fromisoformat`, `parsedate_to_datetime`, `strptime` with `%z` in `_TemporalField._deserialize`, then `NaiveDateTime`/`AwareDateTime._deserialize`). | 0 | Drop that source from the note. |

### Remarks (no change to the ground truth)

- **R1 (README, B2).** F2 turns on whether an abstract library type in an
  annotation names a package class that implements it. Proposed line for B2:
  "An abstract type from outside the package (`AbstractSet`,
  `MutableMapping`, `Iterable`, `Sized`) names no package value by itself; a
  package class that implements it is in scope only through the
  documentation, the defaults, or the package's own code, tests or
  documented examples."
- **R2 (README, B2).** The rejected trace edge `Nested.schema ->
  Field.__init__` comes from a test that passes `fields.String` as `nested`
  only to check that `Nested.schema` refuses it (`tests/test_schema.py:1943`;
  `fields.py:587-591`). B2 counts what the tests pass; the annotation
  (`Callable[[], Schema | SchemaMeta | str | dict]`, `fields.py:525-531`)
  excludes a field class, and "the annotation decides". I agree with the
  rejection. Proposed line: "A value that a test passes only to check that
  the package refuses it is not in scope when the annotation excludes it."
- **R3 (tools).** I confirm the writer's tool notes: `check.py <name>` prints
  only totals, not the per-candidate counts that the README promises;
  `sites.py` drops a subscripted base (`class String(Field[str])`), so
  `String()` and `Raw()` (`fields.py:1945, 1952`) lack the candidate
  `Field.__init__` (the ledger adds it; no other site is affected: every
  other constructor that the package calls has its own `__init__`); the
  tracer records no caller for `OrderedSet.__iter__` (in `executed`, no
  in-edge), which explains 11 untraced edges; `sites.py` marks
  `validate.URL(...)`, `class_registry.register(...)` and
  `functools.partial(...)` as value sites.

## Step 1: blind re-derivation

I built the skeleton without the ledger (`$TMPDIR/heldout-audit-marshmallow`:
a copy of `projects.toml`, a `projects` symlink; 1337 sites, 71 value sites),
numbered its sites in file order and drew
`random.Random(20261111).sample(sites, 70)`. Five value sites fell in the
draw; I added the other 66: 136 sites. I wrote the callees of each from the
source and saved the file (`$TMPDIR/heldout-audit-marshmallow/blind.md`)
before I opened any writer file.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random draw (40 call or decorator, 30 implicit) | 70 | 70 | 0 |
| Value sites added | 66 | 65 | 1 |
| **Total** | **136** | **135** | **1 (0.7 %)** |

- **I was wrong (1):** `validate.py:426:46` `Length._format_error`. I missed
  `-> _Missing.__repr__`. `missing` reaches `Length` on purpose
  (`CHANGELOG.rst:127-128`; `tests/test_deserialization.py:1020-1025`), and a
  client error template with `{input}` (documented, `validate.py:394-395`)
  formats it. This is the writer's judgement 3, ruled by the lead.
- **Left open, resolved for the writer (1):** `fields.py:1984:33`
  `self.enum(val)`. I left open `enum.EnumType.__call__`. The naming rule
  names a call of a class by the class, here a client class, so there is no
  edge (judgement 6). I agree.
- **The writer missed an edge (0). The writer has an edge that cannot happen
  (0). Naming only (0).**

The value sites that decide the most edges agree in full: `cls_or_instance()`
(16 `__init__`, with the same exclusions), `accessor_func`, `getter_func`,
the 13 `set_class` calls, the `dict_class`/`dict_cls`/`OPTIONS_CLASS` calls,
`schema_class(...)`, the two temporal tables (6 callees each), the IP
constructors, `num_type`/`mapping_type`, `validator(value)` (12 `__call__`),
and the 20 client value sites with no callee.

## Step 2: exhaustive checks

1. **Dispatch sets.** Every row of "Dispatch sets" in `marshmallow.md` holds.
   I derived the field hierarchy (31 concrete classes; `Number`, `Mapping`,
   `_TemporalField` abstract), checked each override (`_serialize` 17 owners,
   `_deserialize` 20, `_bind_to_schema` 6, `_validate_missing` 2,
   `_format_num`/`_to_string` 2, `_validated` 3 at `fields.py:994`,
   `_make_object_from_format` 3, `_repr_args` 10), each `super()` target, and
   the receivers that override a caller (`ContainsOnly`/`ContainsNoneOf`
   never run `OneOf.__call__`/`NoneOf.__call__`; `Decimal` never runs
   `Number._format_num`).
2. **Roles (B2).** `validate`: the docs name the built-in validators for it
   (`docs/quickstart.rst:218-219`), so all 12 concrete `__call__`.
   `cls_or_instance`, `keys`, `values`, `by_value`, `tuple_fields`: `Field |
   type[Field]`, so every concrete field. Accessor: `utils.get_value` and the
   bound `Schema.get_attribute` (`schema.py:541`). `set_class`: `OrderedSet`;
   `dict_class`/`dict_cls`: `type[dict]`; `OPTIONS_CLASS`: `SchemaOpts`;
   `render_module`: `json` (simplejson is the tests' value). pre_load,
   post_load, the defaults, `nested`, `Function`/`Method` callables, hooks:
   client values only (I searched the tests and docs).
3. **Defaults (533 sites).** I read every site of the `__iter__` (126),
   `__len__` (186), `__contains__` (32) and `__repr__` (50) defaults and the
   non-truth sites of the `_Missing` defaults. Each holds. The operands that
   can be an `OrderedSet` are the `only`/`exclude` of a schema or a bound
   `Nested`, the locals of `_init_fields`, and `OrderedSet`'s own methods;
   each such site has an explicit entry. `missing` is compared with `is`
   everywhere, never tested for truth; it reaches `len()` only in `Length`.
   The formatted package objects are `Schema` and the `OrderedSet` at
   `schema.py:1009`, `missing` and validators in `Field.__repr__`, validators
   in `And._repr_args`, and `missing` at `fields.py:1962` and
   `validate.py:426`. All are accepted.
4. **Library callbacks.** The 13 `OrderedSet` operator entries match
   `collections.abc` (`Set.__and__`/`__sub__` make the generator over the
   right/left operand in the operator's scope; `_from_iterable` calls
   `OrderedSet(it)`; the generator's `in` tests and `Set.__or__`'s iteration
   run inside `OrderedSet.__init__`; `__iand__` calls `discard`). The trace
   confirms `OrderedSet.__init__ -> OrderedSet.__contains__`. `list()` of an
   `OrderedSet` calls `__len__` (length hint); `set()` does not. `copy.deepcopy`
   calls back `Field.__deepcopy__` only; `copy.copy` of a field or schema
   calls no package code. `type(name, (cls,), ...)` runs `SchemaMeta.__new__`
   and `__init__`.
5. **Functions with no caller.** All 40 are public API that only clients
   call, abstract or Protocol stubs, `OrderedSet.pop`/`__reversed__`, or
   `_Missing.__bool__`/`__copy__`/`__deepcopy__` (the package never copies or
   tests `missing`). Each keeps the edges of its body (rule A).
6. **Rejections and notes.** I read all 214 rejection lines, 4 exclusions
   and 177 notes. All hold except W1 and the lines that F2 changes.
7. **Outside callees.** All 114 names, by the micro rules or a trace alias.
   N1 is the only naming finding. The `<builtin>.X.__init__` names of the
   exception classes follow the nearest outside base (judgements 8, 9).
8. **Rejected trace edges (15).** All are client values or objects (B2, B5):
   `int`, `str`, `str.strip` as pre_load/post_load; `dict.items` of client
   mappings; `OrderedDict` as `dict_class`; simplejson as `render_module`;
   `ZoneInfo.utcoffset`; a field class as `nested` (R2); the lead's ruling on
   `abc.GeneratedSchema`. The exception is
   `_resolve_field_instance -> <builtin>.BaseException.__init__` (F1).
9. **Untraced edges (148).** 97 dispatch over the field classes (annotations
   `Field | type[Field]`), 12 `cls_or_instance()` constructors, 11
   `OrderedSet.__iter__` (tracer gap, R3; 2 of them are F2's), 4 built-in
   validators at `And.__call__`, 3 of the `__main__` block (lead ruling), 2
   `missing` formatted (judgements 3, 4), the other 2 edges of F2, and 17
   body edges of functions or branches that no test reaches
   (`OrderedSet.pop`, `OrderedSet.__eq__` on two `OrderedSet`s, the 4
   `ValueError` branches, `json.loads`, `attrgetter` and its call, the 3
   validator repr edges, `Constant._validate_missing`). All are possible
   under the rulings, except the 4 of F2.
10. **The writer's judgements.** 1 and 3 are lead rulings. I agree with 4
    (`by_value` admits `Method`, whose unbound `_serialize` returns
    `missing`), 5 (a call that fails to bind runs no callee; configargparse
    Q1 asks the same), 6, 7, 8, 9, 10 and 11. I disagree with 2 (F2). The
    `raise` ruling (b) needs the lead (F1).


## Round-four complete source audit (2026-11-16)

Re-read all 14 runtime modules before comparing the baseline. Reviewed all
832 baseline pairs, 2,723 source sites (1,337 explicit or candidate-bearing),
248 distinct module/function bodies, 830 ledger entries, defaults, exclusions
and the 16 rejected trace pairs. Found no false positive or missing edge.
The graph, ledger, added-edge register and rejected-edge register retain
their exact baseline bytes. One current interpreter/configuration scope
clarification was added to the judgement file; no metadata error was found.

The source-first freeze initially inferred current PyPy support from the
0.5.4 changelog. After freeze, the lead correctly rejected that inference:
historical testing alone does not establish 4.4.0 support. The frozen model
is preserved; current scope is CPython >=3.11, with no upper bound. Normal,
-O and -OO are included under the stated working assumption. There is no
runtime assert/__debug__/docstring branch. Static structural and origin
checks pass; no target/dependency/test/generated code or PyCG was run.
