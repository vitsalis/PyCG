# Rewriting PyCG in Rust

PyCG becomes one Rust program. The Python engine of `pycg/` is the
oracle and `docs/design.md` is the spec: the port reproduces the engine's
algorithm, its records and hubs, and its document byte for byte. Only the
evaluation harness (`evaluation/`, `tools/`, CI scripts) stays in Python.
After parity, algorithmic work continues in Rust.

The work lands as pull requests against `base/rust-rewrite`.

| Part | Content |
|---|---|
| 1 | Crate layout and dependencies |
| 2 | How each module of `pycg/analysis` maps to Rust |
| 3 | The parity harness and its CI job |
| 4 | Stages, each with "done when", and what runs in parallel |
| 5 | Testing, command line, the pip package and distribution, risks |
| 6 | Timing and memory targets per scale package |

## What the oracle is

The oracle is `pycg/` on `base/rust-rewrite` at the commit that the parity
job names (section 3), run on Python 3.14 in the `pycg-eval-runner` image,
as `make eval` runs it. It was branched from `main` at `02bf447`. An engine
change on `main` after that reaches the port through a pull request that
merges `main` into `base/rust-rewrite` together with the Rust change that
reproduces it; the parity job fails on that pull request until both agree.
Such a merge is a pull request of its own, and every open Rust pull request
rebases on it and passes again before it merges.

Facts about the engine that size the port, counted on `02bf447`:

| Measure | Value |
|---|---|
| Lines of `pycg/analysis/*.py` | 14,586 (25 modules and an empty `__init__.py`) |
| Lines of `pycg/` in all | 15,153, plus `view/template.html` |
| `Constraint` subclasses | 16, plus subclasses of `_Access` and `_Site` |
| `Each(...)` sites, distinct rule functions | 139, 98 |
| Fields that `Analysis.__init__` sets (records, tables, queues) | 111 |
| Stub data | 282 JSON files of the standard library (4.0 MB) and 273 of third-party packages (18.0 MB) |
| Tests | 1,538 test functions in 41,547 lines; 696 micro cases; 170 known failures |

# 1. Crate layout and dependencies

One Cargo workspace at the root, `Cargo.toml` beside `pyproject.toml`,
crates under `crates/`. Each crate is a unit that one agent can own in a
stage; the arrows are the only dependencies. A crate's directory has the
short name (`crates/syntax`) and its package the prefixed one
(`pycg-syntax`), since crates.io names are global; its code paths are
`pycg_syntax::...`. The root `Cargo.toml` holds the shared package fields
(`[workspace.package]`) and the internal crates with their versions and
paths (`[workspace.dependencies]`); each crate takes them with
`.workspace = true`.

```
pycg-syntax ──┐
pycg-stubs  ──┼─► pycg-analysis ─► pycg-document ─► pycg (binary)
pycg-solver ──┘                                  └► pycg-dump (dev binary)
```

| Crate | Holds | Ported from |
|---|---|---|
| `pycg-syntax` | Reading a file (encoding cookie, BOM, decode errors), parsing through ruff's parser, the positions that CPython's `ast` gives (section 5, *Risks*), the scope pass, interned names | `program._read`, `_parse`, `scopes.py`, the AST facts of `builder.py` |
| `pycg-stubs` | The stub data, embedded, decoded lazily per top-level package; every stub query | `stubs.py`, `mro.py` (C3 is shared with the analysis) |
| `pycg-solver` | Object and set arenas, hash-consed sets, nodes, the worklist, rounds, cycle collapsing, saturation, the work counters; generic over the constraint type, so it is tested and replayed alone | `solver.py` |
| `pycg-analysis` | The model, module discovery, the builder, every rule, the fixpoint steps | every other module of `pycg/analysis` |
| `pycg-document` | The document of `docs/format.md` and its JSON writer | `formats/`, `formats/document.py` |
| `pycg` | The command line, and `pycg view` | `__main__.py`, `view/` |
| `pycg-dump` | Not shipped: writes the intermediate dumps of section 3 | new |

The toolchain is pinned in `rust-toolchain.toml` to Rust 1.100.0
(released 2026-11-12), edition 2024. `Cargo.lock` is committed; every
dependency is an exact version (`=x.y.z`), as `TIGER_STYLE.md` requires of
tools. The versions below are the latest stable ones published on
crates.io at least two weeks before 2026-11-26, looked up on that day.

| Crate | Version | Used by | Why it is needed |
|---|---|---|---|
| `ruff_python_parser` | 0.0.22 (2026-11-12) | `pycg-syntax` | A maintained parser of current Python syntax that reports the syntax of a newer version than its target as an error of its own, error-tolerant, with UTF-8 byte ranges like CPython's `ast` offsets. Writing a parser is months of work and a second source of syntax bugs. Published by Astral as an internal crate of ruff, versioned weekly without semver: pinned exactly, updated only by a pull request that passes parity |
| `ruff_python_ast` | 0.0.22 | `pycg-syntax`, `pycg-analysis`, `pycg-dump` | The tree that the parser gives; the same release as the parser |
| `ruff_text_size` | 0.0.22 | `pycg-syntax`, `pycg-analysis` | The `TextRange` of that tree |
| `ruff_source_file` | 0.0.22 | `pycg-syntax`, `pycg-analysis`, `pycg-dump` | Line index: offsets to lines, as CPython numbers them |
| `serde_json` | 1.0.154 (2026-10-11) | `pycg-stubs`, `pycg-dump`, the tests of `pycg-analysis` | Reads the stub data and the dumps. The document is written by our own writer (section 2, `formats/`), since Python's `json.dumps` escapes every non-ASCII character |
| `rustc-hash` | 2.1.3 (2026-07-02) | `pycg-syntax`, `pycg-stubs`, `pycg-solver`, `pycg-analysis`, `pycg-dump` | `FxHashMap`: a fixed hash with no random seed, fast on `u32` keys. The standard `HashMap` seeds itself at random; it is banned by `clippy::disallowed_types` |
| `indexmap` | 2.14.2 (2026-09-05) | `pycg-syntax`, `pycg-solver`, `pycg-analysis`, `pycg-dump` | Insertion-ordered maps and sets, for every Python `dict` whose order reaches a decision or the output (the firing nodes, the sites of a hub, `site_edges`) |
| `num-bigint` | 0.4.8 (2026-07-05) | `pycg-syntax`, `pycg-analysis`, `pycg-document`, `pycg`, `pycg-dump` | Python's `int` literals have no bound; their names (`ascii()`, `hex()` past 640 digits) and the values that select container fields must be exact. A value is a `BigInt` wherever the engine holds a Python `int` from the source |
| `libc` | 0.2.191 | `pycg-syntax`, on Unix only | The parse stack: `mmap` with `MAP_NORESERVE` and a guard page, and `pthread_attr_setstack` (section 5, *Risks*) |

Left out, with the reason:

- **No CLI crate** (`clap` 4.6.x, `lexopt`): the command line has six
  options; a hand-written parser of `std::env::args_os` is about 80 lines,
  and its error messages are ours to match.
- **No allocator crate** (`mimalloc`, `bumpalo`): the arenas are `Vec`s of
  plain structs; the system allocator is measured first (stage 7), and a
  change of allocator is a stage 7 pull request with its measurement.
- **No bitmap crate** (`roaring`): sets start as sorted slices of
  object numbers, which the earlier study measured; a bitmap form for
  large sets is a stage 7 change, written in the solver if a measurement
  asks for it, so that its union and difference are memoised like the
  others.
- **No random-number crate**: the seeded order of the simulation tests,
  `Order::Shuffled` of `pycg_solver::Order`, and the program generators
  of the fuzzing and termination tests are a SplitMix64 of a few lines;
  the analysis reads no randomness.
- **No fuzzing crate** (`libfuzzer-sys`, `arbitrary`): the generated
  programs come from a seeded generator, so a failing seed is the whole
  reproduction (section 5).
- **No PyO3, no maturin**: no Python extension and no wheel; the pip
  package is deprecated (section 5, *The pip package*).

# 2. How `pycg/analysis` maps to Rust

## Conventions of every table

- **Ids, not references.** Every object, node, call, scope and record
  lives in an arena owned by the analysis and is named by a `u32` newtype:
  `ObjId`, `NodeId`, `CallId`, `ScopeId`, `SetId`, `Sym` (an interned
  string: names, sites, callers, paths) and one id per record arena below.
  An engine `Object` and a `Node` compare by identity, so a Python dict
  keyed by them is an `FxHashMap` keyed by their id. A Python tuple key is
  a Rust tuple or a small `#[derive(Hash, Eq)]` struct of ids.
- **Order.** A Python `dict` or `dict.fromkeys` whose iteration reaches a
  node, an object, a constraint or the output is an `IndexMap`/`IndexSet`;
  one used only for membership is an `FxHashMap`/`FxHashSet`; a `list` is a
  `Vec`; a stack (`pending.pop()`) is a `Vec` pushed in the same order. A
  loop over a snapshot (`list(x)`, `x[i:]`) and a loop over a live list are
  ported as such: the tables say where it matters.
- **Mixins become modules.** `Analysis` inherits twelve mixins; in Rust it
  is one `struct Analysis` whose fields are grouped by the module that
  owns them (`analysis.containers.dict_hubs`), and each Python mixin is a
  Rust module of `impl Analysis` blocks that touches only its own group
  and the shared core. This keeps "one owner per piece of state".
- **Constraints are data.** `Each(function, *args, kinds, results)` is one
  variant of `enum Rule` per rule function (98 of them) with typed
  payload; a `Constraint` subclass is a variant of `enum Constraint` that
  points to its record in an arena. Every variant gives the four things
  the solver asks for: `apply(obj)`, `kinds` (a `u32` bitmask over the
  object kinds, tested like `isinstance`, so `UnknownExternal` passes
  `External`), `results()` (the nodes that `saturate` fills) and
  `captured()` (the objects that the opacity test looks at; only `ObjId`
  fields, never nodes or calls). The solver is generic over a trait with
  those four methods, so it does not depend on the analysis.
- **Order.** The port keeps the engine's order of work exactly until
  stage 7: the FIFO worklist, objects numbered by first arrival, sets
  iterated in that number's order, applications nested through `attach` up
  to `_ATTACH_NESTING_MAX` (50) and deferred past it, observers notified
  through the same queue. Order independence (Part 3 of `docs/design.md`)
  says another order gives the same document, but a hidden order
  dependence would then show as a parity failure far from its cause; with
  the same order, D3 compares the trace in order and the work counters
  exactly. Stage 7 may change the order once parity holds, with parity as
  its check.
- **Recursion.** The 50 nested applications are the only recursion of the
  solve, a few kilobytes of stack each. Every walk of input-shaped data
  (the AST, scopes, stub types, hierarchies) is an explicit stack, as
  `TIGER_STYLE.md` asks.

## `solver.py` → `pycg-solver`

| Python | Holds | Rust |
|---|---|---|
| `Node` (8 slots) | `label`, `representative`, `done`, `inbox`, `successors`, `constraints`, `fired`, `constraint_groups` | `struct Node { done: SetId, fired: SetId, representative: Option<NodeId>, inbox: Inbox, successors: Successors, constraints: Constraints }`, 24 bytes plus the out-of-line parts; the label lives in a side table `labels: FxHashMap<NodeId, Sym>` (only `named_nodes` and container fields have one) |
| `inbox` | `None`, one set, or `{id(set): set}` | `enum Inbox { Empty, One(SetId), Many(SmallVec<[SetId; 4]>) }`, deduplicated by `SetId` |
| `successors` | `None`, one node, or `{node: searched}` | `enum Successors { None, One(NodeId), Many(IndexMap<NodeId, bool>) }`: most nodes have one, as the design measures |
| `constraints`, `fired`, `constraint_groups` | the constraints of a node and the set they last saw; groups of `(constraints, seen)` when constraints attach at different moments | `enum Constraints { None, Fired(Vec<C>, SetId), Groups(Vec<(Vec<C>, SetId)>) }` |
| `Constant` | a node with one object and no edges | a flag bit of `Node` (`done` fixed, no inbox, no successors, no constraints); `add_object` on it is an assertion, as the `ValueError` is |
| `Witness`, `Watch` | a node that wakes waiting rules when an object or edge first reaches it; the rules grouped by rule, in first-wait order | `Node` flag plus `watches: FxHashMap<NodeId, WatchId>`; `struct Watch { waiting: Option<Vec<(RuleKey, ObjId)>> }`, woken in the order of `Watch.wake` (rules by first appearance, receivers in order) |
| `Order`, `LastInFirstOut`, `Reversed`, `Shuffled` | the test hook of the processing order | `trait Order { fn take(&mut self, &mut VecDeque<NodeId>) -> NodeId; fn arrange<T>(&mut self, &mut [T]); }` with `Fifo` in the program and the others only under `#[cfg(test)]` (a seeded SplitMix64) |
| `_worklist` | FIFO of nodes with an inbox | `VecDeque<NodeId>` |
| `_number_by_object` | object → number in order of first arrival | `numbers: Vec<Option<u32>>` by `ObjId` and `objects: Vec<ObjId>` by number: a set holds numbers, so a set stored sorted is in arrival order, as `_ordered` gives |
| sets (`frozenset`) and `_set_by_content` | every set exists once; the table maps content to the one copy | `SetArena`: a set is a sorted slice of object numbers in one `Vec<u32>` (offset, length); the table is `FxHashMap<u64 content hash, SmallVec<[SetId; 1]>>` with an exact comparison; the singleton of each number is a direct `Vec<SetId>`. A bitmap form for large sets is a stage 7 change, made only if a measurement asks for it |
| `_union_by_set_ids`, `_difference_by_set_ids` | memoised union and difference by `(id(a), id(b))` | `FxHashMap<(SetId, SetId), SetId>` each |
| `_ordered_by_set_id` | the objects of a set in arrival order | not needed: a set is stored sorted by arrival number |
| `_selection_by_set_id_and_kinds` | the objects of the given kinds of a set of at least 32 (`_KIND_SELECTION_OBJECTS_MIN`) | `FxHashMap<(SetId, KindMask), SetId>`, same threshold |
| `_set_holders`, `_sweep`, `_SWEEP_NEW_OBJECTS_MIN` | rebuild the table from the sets that nodes hold when new sets hold more objects than those that survived, at least 2^20 | the same rule: mark the sets that live nodes, inboxes and the absorbed list hold, compact the arena, renumber, clear the memo tables |
| `_cycle_suspects`, `_collapse_cycles`, `_cycle_components`, `_merge`, `_find_representative` | lazy cycle detection: edges between nodes with the same set wait; one iterative Tarjan over their successors; union-find with path compression; merge with catch-up of outside successors | the same: `Vec<NodeId>` of suspects, an iterative Tarjan with an explicit frame stack, union-find in `representative`, the search budget (`_last_search_walked`, `_propagated_nodes_and_edges`) unchanged |
| `_attach_deferred`, `_attach_nesting`, `_ATTACH_NESTING_MAX` | applications deferred past 50 nested attachments | the same counter, bound and `VecDeque<(C, SetId)>` |
| `_added_by_node`, `_applications_in_progress`, `_flush` | objects that constraints add during a round, collected and sent as one set per node | `IndexMap<NodeId, Vec<ObjId>>`, interned at the flush |
| `_firing_nodes` | nodes whose set grew, in order | `IndexSet<NodeId>` |
| `phase`, `between_rounds`, `opaque` | the round counter; the callback that decides unknown classes between rounds; the opacity test | `phase: u32`; the analysis is called through the trait (`Rules::between_rounds`, `Rules::opaque`) |
| `absorbed_sets`, `absorbed()` | sets that reached a saturated node | `Vec<SetId>` plus `FxHashSet<SetId>`; kept alive by the sweep |
| `follower(src, since)` | a parameter node made when a rule first reads it, in the state it would have had | the same, with `since: u32` |
| `work` | `copied`, `applied`, `edges`, `processed`, `merged`, `searched` | `struct Work` with the same counters |
| `Constraint`, `Each` | the interface; a function with arguments | `trait Constraint` (see *Conventions*); `Each` is `enum Rule` in `pycg-analysis` |
| `DEFAULT_CAP` | 5,000 | `const OBJECTS_PER_NODE_DEFAULT: u32 = 5000`; the cap is `Option<NonZeroU32>` |

## `model.py` → `pycg_analysis::model`

One `enum Object` with one variant per kind, in an arena; the payload of a
variant is what its Python class holds. The name of an object is computed
from its payload when the document or a dump asks, never stored, except
where the payload does not give it.

| Python | Holds | Rust |
|---|---|---|
| `Object.fields` | attribute → node | `fields: FxHashMap<(ObjId, Sym), NodeId>` in the analysis, not per object (most objects have none); the field order is the creation order of the nodes |
| `Module` | name, `defines` | `Module { name: Sym, defines: FxHashSet<Sym> }` |
| `External`, `UnknownExternal` | dotted name, steps past the root, `inexact` | `External { name: Sym, steps: u8, inexact: bool }`; the unknown external is one fixed `ObjId` |
| `Saturated` | one per analysis | `ObjId(0)` |
| `Typed` | stub class, public name, abstract | `Typed { class: Sym, name: Sym, abstract_: bool }` |
| `Signature` | positional, positional-only count, keyword-only, vararg, kwarg, `binds()` | `struct Signature { positional: Box<[Sym]>, positional_only: u8, keyword_only: Box<[Sym]>, vararg: Option<Sym>, kwarg: Option<Sym> }` in an arena (`SignatureId`), shared |
| `Function` (18 slots) | name, module, signature, parameters, defaults, return, yield and sent nodes, async, varargs and varkeywords containers, `passthrough`, annotations, decorated, optional, position | `Function { .. }` with the same fields; parameters as `Box<[NodeId]>` in signature order; `passthrough` an `FxHashSet<u32>` |
| `Class` (31 slots) | module, defines, bound, slots, base nodes per base expression, MROs, ancestors, exhaustive, ready, forced, index, subclasses, lookups, instances, metaclass state, protocol, abstract methods, namespace marks, concrete, instantiable, ancestry, unknown, allocator | `Class { .. }`; `mros: Vec<Box<[ClassRef]>>` with `ancestors` recomputed on every write as the Python setter does; `mro()` computed as `Class.mro` does (`base_order` for the exhaustive order) |
| `Instance` | class, site | `Instance { class: ObjId, site: Sym }`; the abstract instance has the site that `abstract_instance` gives |
| `BoundMethod`, `Super`, `BuiltinMethod`, `Fallback`, `Wrapper`, `ReturnsArgument`, `Closure`, `Generator`, `Coroutine`, `TypeForm`, `Pattern` | as in `docs/design.md`, *Objects* | one variant each, payload by id |
| `Const` | value, exact | `Const { value: ConstValue, exact: bool }` with `enum ConstValue { Str(Sym), Bytes(BytesId), Int(IntId) }`: only `str`, `bytes` and `int` occur, never `bool` or `float` |
| `Container` (10 slots) | kind, length, exact, `unknown`, `every_element`, `keys`, `factory`, `aliased`, `observers`, `repr_reach` | `Container { kind: Sym, site: Sym, length: Option<u32>, exact: bool, storage: StorageId, unknown, every, keys, factory, aliased, repr_reach: Option<NodeId> }`; the inexact alias shares `storage` (fields and observers) with its container, copies the four nodes that exist at its creation and not `factory` or `repr_reach`, as the Python code does |
| `constant_name` | `ascii(value)`, `hex()` from 10^640 | a port of CPython's `ascii()` for `str` (quote choice, `\x`, `\u`, `\U`) and `bytes`, and of `int.__repr__`/`hex` over `num-bigint`; unit-tested against vectors written by Python |
| `site_name`, `base_order` | the part of a site before `#`; the order of the exhaustive MRO | functions |

## `semantics.py` → `pycg_analysis::semantics`

| Python | Holds | Rust |
|---|---|---|
| object tables `modules`, `externals`, `_instances`, `_bound_methods`, `_builtin_methods`, `_wrappers`, `_supers`, `_fallbacks`, `_returning`, `_generators`, `_coroutines`, `_consts`, `_containers`, `_typed`, `_closures` | the interning of objects by their identity key | one `FxHashMap<Key, ObjId>` per kind, the key being the row of the *Termination* table of `docs/design.md`; `_wrappers` has two key forms (`(kind, origin)` and `(kind, field node)`): `enum WrapperOrigin` |
| `functions`, `classes` | in creation order | `Vec<ObjId>`; `_complete` walks `functions[completed:]` |
| `site_edges` | `(caller, site, construct) → {callee: None}` | `IndexMap<(Sym, Sym, Construct), IndexSet<Sym>>`; the document sorts them |
| `external_callees` | name → `"stub"`/`"name"`/`"extension"` | `FxHashMap<Sym, Known>` |
| `call_expressions`, `iterated_expressions`, `named_nodes` | for the document and for `output_points_to` | `Vec`, `FxHashSet`, `Vec` |
| `Call` (12 slots) | caller, args, keywords, dst, site, origin, star, double star, implicit, decorator, applies | `struct Call` in an arena: `args: Box<[Option<NodeId>]>`, `keywords: Box<[(Sym, NodeId)]>`, `origin: Origin` (`enum Origin { Itself, Site(Sym, Sym, Role, bool), Construct(..) }`: the key of `site_call` and the construct keys) |
| `_site_calls` | `(caller, site, role, implicit) → Call`, asserts one arity per key | `FxHashMap<(Sym, Sym, Role, bool), CallId>`; `Role` an interned enum of the role tuples (`("subscript", name)`, `("operator", method, is_left)`, ...) |
| `_callees` | call → its callee node | `FxHashMap<CallId, NodeId>` |
| `_dunder_calls`, `_dunder_owners`, `_roots` | the template call of a special method per `(class or None, name, root, unless)`; the owners it was attached for (one, or a set); the root of each template | `FxHashMap<(Option<ObjId>, Sym, CallId, UnlessId), CallId>`; `FxHashMap<CallId, Owners>` with `enum Owners { One(ObjId), Many(FxHashSet<ObjId>) }`; `FxHashMap<CallId, CallId>`. `unless` tuples are interned (`UnlessId`) because they are compared by value |
| `_receiver_calls`, `_prefixes` | the call with receivers prefixed, per `(base, receivers)`; for each such call its base and receivers or group | `FxHashMap<(CallId, Receivers3), CallId>` with `Receivers3 = SmallVec<[ObjId; 3]>` (`RECEIVERS_PER_CALL_MAX`); `FxHashMap<CallId, (CallId, Prefix)>`, `enum Prefix { Receivers(Receivers3), Group(GroupId) }` |
| `_bound_groups`, `_groups`, `_BoundGroup` | bound-call groups of a plain stub method: per `(base, callee, width, unknown)` a list of groups of at most the cap of receivers; the group of a group call; a group's receivers (ordered) and observers, replayed on observe | `FxHashMap<(CallId, ObjId, u8, bool), Vec<GroupId>>`; `FxHashMap<CallId, GroupId>`; `struct BoundGroup { base, callee, call, width, unknown, receivers: IndexSet<Receivers3>, observers: Vec<GroupObserver> }`, `enum GroupObserver { CallPrefixed{..}, CallBoundPrefixed{..}, AddResultsOf{..} }` |
| `_new_results`, `_class_instances`, `_Returned` | what a class call returns per `(call, class)`: the result node, the instances of the class, the instances held until `__new__` may give another, the `__init__` calls | `FxHashMap<(CallId, ObjId), ReturnedId>`; `struct Returned { call, class, returned: FxHashSet<ObjId>, instances: SetRef, sees, dst: Option<NodeId>, dsts: Vec<NodeId>, held: Vec<ObjId>, another: bool }` |
| `_statement_calls`, `_statement_news`, `_made_classes` | the metaclass calls of class statements | maps and sets of ids |
| `_callbacks`, `_callback_values` | the call back of an origin; the `(callback, value node)` pairs attached | `FxHashMap<Origin, CallId>`, `FxHashSet<(CallId, NodeId)>` |
| `none_arguments`, `none_keywords`, `literal_imports`, `zero_argument_super` | facts the builder records per call site | maps keyed by `(Sym, Sym)` |
| `_receivers`, `_entry_receivers`, `_called`, `_completed_receivers`, `_completed_functions` | the entry points of the completion step, with their cursors | `Vec` and `usize` cursors, the slices walked as Python walks them |
| `_watches`, `_waiting_rules`, `_field_readers` | the watches of the waiting rules and the loads of fields that no instance wrote yet (`read_field`) | see `hierarchy.py` and `attributes.py` below |
| `solve`, `_complete`, `_absorbed_functions`, `unresolved_calls` | the fixpoint steps and the causes | functions in `pycg_analysis::fixpoint`, in the order of Part 3 of `docs/design.md` |

## `attributes.py` → `pycg_analysis::attributes`

| Python | Holds | Rust |
|---|---|---|
| `EXTERNAL_STEPS_PAST_ROOT_MAX` | 2 | `const`, same name |
| `_Access` and `Load`, `Store`, `Delete` | attribute, caller, site, and lazily the site calls of the roles `("getattr", kind, attr)`, `("hook", kind, attr)`, `("accessor", kind, attr)` per caller and per result node; `Load` has `dst`, `Store` `src`; `Store` and `Delete` have no results | `struct Access { kind: AccessKind, attr: Sym, caller, site, accessor_calls: FxHashMap<Option<Sym>, CallId>, named_call: Option<CallId>, hook_calls: FxHashMap<Option<NodeId>, CallId> }` in an arena; `enum AccessKind { Load { dst }, Store { src }, Delete }`, whose name reaches the role and so `site_edges` |
| `_accessor_hooks` and `_AccessorHooks` | per `(class, hook)`, one constraint attached to `python_method(class, hook)` and to the lookup; it holds the receivers per `(accessor, access, kinds, width)` in order, the callers in order, the result nodes, a saturated flag | `FxHashMap<(ObjId, Sym), AccessorHooksId>`; `struct AccessorHooks { receivers: IndexMap<AccessorKey, Vec<ObjId>>, callers: IndexSet<Option<Sym>>, results: IndexSet<Option<NodeId>>, saturated: bool }`. Python adds the saturated value to a `None` result of a late `Store` entry (`attributes.py:335`): the port asserts that this does not happen and reports it on `main` if it does |
| `_accessor_receivers` and `_Accessors` | per `(accessor node, call, kinds, width)`: the call, its kinds (pre-selection too), width, receivers and methods in order; every method meets every receiver | `FxHashMap<(NodeId, CallId, KindMask, u8), AccessorsId>`; `struct Accessors { call, kinds, width, receivers: Vec<ObjId>, methods: Vec<ObjId> }` |
| `_field_writes` and `_FieldWrites` | the field writes per decision: per `written` marker node, the `(src, field)` pairs in order, added once when the marker gets its first object, or saturated | `FxHashMap<NodeId, FieldWritesId>`; `struct FieldWrites { writes: IndexSet<(NodeId, NodeId)>, written: bool, saturated: bool }` |
| `_hook_calls` and `_HookCalls` | per lookup node of an attribute hook: the calls, the hooks found, whether an opaque one was seen | `FxHashMap<NodeId, HookCallsId>`; `struct HookCalls { found, calls: Vec<CallId>, hooks: Vec<ObjId>, saw_opaque: bool }` |
| `_deliveries`, `_Deliveries`, `_Deliver` | the deliveries per lookup: per lookup node, one receiver and hook and the loads that ask through it, applied objects outer and loads inner over a snapshot; `_Deliver` applied once through `apply_now` | `FxHashMap<NodeId, DeliveriesId>`; `struct Deliveries { receiver: ObjId, hook: Option<Sym>, loads: Vec<AccessId> }` with its own `apply_each`; `Constraint::Deliver { receiver, load, hook }` |
| `_external_modules` | every dotted prefix of two or more parts of an outside module | `FxHashSet<Sym>` |
| `_subscriptions` (shared by many modules) | a set of tuples of many shapes that makes an attachment happen once | `FxHashSet<Subscription>`, `enum Subscription` with one variant per shape (about 20: `DescriptorItself`, `Metaclass`, `Fallback`, `Bind`, `Namespace`, `Vars`, `Getmembers`, `Members`, `ClassSubscript`, `CopyFields`, `CompareValue`, `HashValue`, `ConvertElements`, `LengthHint`, `IteratorLengthHint`, `ReverseSequence`, ...) |
| `Each` rules | `_itself`, `_class_get`, `_name_lookup`, `_defined_name`, `_module_getattr`, `_class_attribute`, `_super_metaclass`, `_store_past`, `_deliver_store`, `_deliver_delete` | `Rule` variants of the same names |
| `load`, `store`, `delete` | dispatch on the kind of the object, in a fixed order of steps | `match` on `Object`, same order |

## `hierarchy.py` and `mro.py` → `pycg_analysis::hierarchy`, `pycg_stubs::mro`

| Python | Holds | Rust |
|---|---|---|
| `HIERARCHIES_PER_CLASS_MAX` | 8 | `const`, same name |
| `unless` sentinels, `EXPLICIT`, `MAY_DERIVE`, `MAY_LACK`, `MAY_LACK_METHOD`, `NOT_NOMINAL` | one-element tuples compared by value; `EXPLICIT` is truthy where `()` is not | `enum Unless { Nothing, Explicit, PythonsOwn, DescriptorItself, DefaultMember, NewGivesTheClass, DescriptorDecides, DataDescriptor, MayDerive, MayLack, MayLackMethod, NotNominal, Names(UnlessId) }`, `Names` being the interned tuples of method names and markers that callers pass |
| `Class.lookups` | per `(attr, receiver, after, unless)` the lookup node, iterated in insertion order when MROs change or the class becomes unknown | `IndexMap<LookupKey, NodeId>` per class; `attr` is a name, or a class, an external or nothing for the relations: `enum LookupAttr` |
| `Class.bases`, `subclasses`, `metaclass_candidate_of`, `metaclass_users`, `metaclasses`, `keyword` | ordered sets of candidates per base expression and of related classes | `IndexSet`s of `enum Base { Nothing, Class(ObjId), External(ObjId) }` |
| `_watches`, `Watch`, `Witness` | per `(class, attr, after, unless)` the watch of the rules that wait for the class to answer; only the first instance receiver's lookup is a witness | `FxHashMap<(ObjId, LookupAttr, Base, Unless), WatchId>`; the witness flag on that one node |
| `_waiting_rules` | interns the `(rule, *args)` tuples so that a watch groups by rule | `enum WaitingRule { DeliverLoad(AccessId), CallHook(Sym, CallId), FoundStore(AccessId) }` with `Eq + Hash`: no table needed |
| `_fallback_nodes` | per `(receiver, dst)` the node that wraps a bound `__getattr__` into a `Fallback` | `FxHashMap<(ObjId, NodeId), NodeId>` |
| `_Bases`, `_Bind` | a base expression's candidates; binding a found attribute to a receiver | `Constraint::Bases { class, index }`, `Constraint::Bind { receiver, dst, instance }` |
| `unknown_classes` | `between_rounds`: classes, in index order, whose ancestry holds the saturated value or an unknown class become unknown; their waiting rules wake first, then their lookups saturate | the same loop; the lookups are walked from a snapshot |
| `_update_mros`, `_compute_mros`, `decide_hierarchies` | the MROs of a class and its subclasses, breadth first from a queue; slots sorted by `base_order`; exhaustive past the bound or on a cycle | `VecDeque<ObjId>` walk; `base_order` compares the module and external names as strings, not as interned ids |
| `class_attribute_stored` | depth first, last in first out, over subclasses | `Vec` stack, same push order |
| `@cache` helpers (`_outside_defines`, `_builtin_defines`, `_derives_from_tuple`, `_nominal_stub_class`, `_outside_defines_str`) and the module-global `_STUBS` | pure stub queries | memo tables in `pycg-stubs`, one stub database per process |
| `mro.linearize`, `_c3_merge`, `linearizations`, `exhaustive_order` | C3 with its fallback to first occurrences; the product of candidates in lexicographic order, deduplicated by equality, `None` past the limit | the same, iterative, generic over the base type so that `pycg-stubs` (paths) and the analysis (`Base`) share it; the product counted in `u64` with a saturating multiply |
| `for ... else` in `_may_give_itself`, `_may_write_field`, `_is_data_descriptor_class` | a result when the loop ends without `break` | an explicit flag |

## `arguments.py` → `pycg_analysis::arguments`

| Python | Holds | Rust |
|---|---|---|
| `bind_arguments` | receiver, positional, `*`, keywords, `**`, defaults, in that order; returns the names surely supplied | the same order; `FxHashSet<Sym>` |
| `_unpacked` and `_Spread` | what an unpacked argument passes, per `(call origin, part)` (`"*"`, an index, `("**", index)`): the source node, the fields in order, `unknown`, `keys`, the dicts it saw, `aliased`, observers, the binds that wait for its first object | `FxHashMap<(Origin, SpreadPart), SpreadId>`; `struct Spread { source, fields: IndexMap<FieldKey, NodeId>, unknown, keys: Option<NodeId>, dicts: Vec<ObjId>, aliased: Option<NodeId>, observers: Vec<Observer>, waiting: Option<Vec<PendingBind>> }`; a spread is observed like a container (one `Observable` storage type) |
| closures passed as observers and waiting binds | `bind_field`, `gather_field`, `_bind_anywhere`, `_bind_unknown_keywords` | `enum Observer` and `enum PendingBind` with their arguments |
| `Function.passthrough` | parameters, and `(vararg, index)` pairs, that a function returns | `enum Passthrough { Parameter(Sym), Vararg(Sym, u32) }` |

## `reflection.py` → `pycg_analysis::reflection`

| Python | Holds | Rust |
|---|---|---|
| `_namespace_nodes` | per `(object, "names" \| "subclasses" \| "members")` a node | `FxHashMap<(ObjId, NamespaceTag), NodeId>` |
| `_GetmembersAccess` | a `getmembers` call, its names and values nodes, a `Load` per name | arena `struct GetmembersAccess { call, names, values: Option<NodeId>, loaders: FxHashMap<Sym, AccessId> }` |
| `Each` rules | `_namespace_element`, `_when_default_member_on_type`, `_run_default_action`, `add_namespace`, `_members_of`, `_load_member`, `_member_field` | `Rule` variants; the action and argument of the default-member rules are enums |
| `_member_names` | last in first out over candidate bases sorted by `base_order` | `Vec` stack |

## `patterns.py` → `pycg_analysis::patterns`

| Python | Holds | Rust |
|---|---|---|
| `_patterns`, `_pattern_states`, `_PatternState` | patterns by `(prefix, suffix, case, exact)`; per pattern, in insertion order, the targets and their accesses, candidate names per target, the classes watched, names and instances per class | `FxHashMap<(Sym, Sym, Option<Case>, bool), ObjId>`; `IndexMap<ObjId, PatternStateId>`; `struct PatternState { targets: IndexMap<ObjId, Vec<DynamicAccessId>>, candidates: FxHashMap<ObjId, IndexSet<(Sym, bool)>>, watching: bool, class_names: FxHashMap<ObjId, Vec<Sym>>, class_seen: FxHashMap<ObjId, Vec<ObjId>> }` |
| `_store_names`, `_class_store_names`, `_module_names` | every stored attribute name, iterated sorted; per class; per module, frozen sorted at `solve()` | `FxHashSet<Sym>` sorted by string when walked; `FxHashMap<ObjId, FxHashSet<Sym>>`; `FxHashMap<ObjId, Vec<Sym>>` |
| `_pattern_operands`, cursor | operands that complete as any value at the fourth step | `Vec<(NodeId, NodeId)>`, `usize` |
| `pattern_affixes`, `_percent_parts`, `_format_parts` | the affixes of `+`, `%`, f-strings and `str.format`; `_format_parts` is `string.Formatter().parse` | a port of CPython's `formatter_parser` (literal, field, spec, conversion; `{{`, `}}`; its `ValueError`s) and of `percent_spans` (below); unit-tested against vectors that Python writes |
| `Pattern.matches`, `_rule_case` | prefix and suffix in code points; ASCII case only | `char` counts, `to_ascii_lowercase`/`uppercase` after the ASCII test |

## `narrowing.py` → `pycg_analysis::narrowing`

| Python | Holds | Rust |
|---|---|---|
| `ClassTestBuilder` state (per module) | per `ast.Call` its class test; per `(call, holds)` the narrowed node | `FxHashMap<AstId, ClassTest>`, `FxHashMap<(AstId, bool), NodeId>`; `AstId` is the node's index in the parsed module |
| `CALLABLE` | a sentinel compared by identity | `enum Tested { Classes(Option<NodeId>), Callable }` |
| `_Filter`, `_Alternative` | a class test's record: source, dst, holds, as-class, groups of values by class key in insertion order, the keys passed, its alternatives; an alternative's per-position classes, open positions, passes, coverage | arenas `Filter { groups: IndexMap<ClassKey, Vec<ObjId>>, passed: FxHashSet<ClassKey>, alternatives: Vec<AlternativeId>, .. }`, `Alternative { classes: Vec<IndexSet<ObjId>>, open: FxHashSet<u32>, passed: IndexMap<ClassKey, FxHashSet<u32>>, covered: FxHashMap<ClassKey, u32>, .. }`; `enum ClassKey { Unknown, Analysed(ObjId), Exactly(PathsId), Below(PathsId) }` |
| `_tested_classes`, `_class_filters` and cursor, `_stub_ancestors` | attachments made once; the subscriptions of filters, walked from the cursor at the completion step; a memo | `FxHashSet<(NodeId, NodeId, bool)>`; `IndexSet<(NodeId, FilterId, Option<AlternativeId>, Option<u32>)>` and `usize`; `FxHashMap<Sym, FxHashSet<Sym>>` |
| `narrow` | recursive over `not`, `and`, `or` | explicit stack, children pushed in reverse |
| `Each` rules | `_callable_value`, `_pass_callable`, `_tested_tuple`, `_alternative`, `_position_class`, `_metaclass`, `_not_nominal`, `_related`, `_value` | `Rule` variants |

## `containers.py` → `pycg_analysis::containers`

| Python | Holds | Rust |
|---|---|---|
| `_consts` | constants by value, and the inexact alias by `(value, "inexact")` | `FxHashMap<(ConstValue, bool), ObjId>`; big ints as `IntId` into an interned `BigInt` table |
| `_containers` | containers by `(kind, origin, rule, exact)`; origins are calls, construct records, `(caller, site, role)` keys or objects; rules are strings or tuples (`("zip", n)`, `("library", path)`, ...); a hit asserts the same length | `FxHashMap<ContainerKey, ObjId>`, `enum ContainerOrigin` and `enum ContainerRule` covering every shape the code makes |
| container storage | fields in insertion order (shared with the inexact alias), observers | `struct Storage { fields: IndexMap<FieldKey, NodeId>, observers: Vec<Observer> }`; `enum FieldKey { Int(IntId), Str(Sym), Bytes(BytesId) }`; node labels `name[ascii(key)]`, `name[?]`, `name.<keys>`, `name.<aliased>`, `name.<factory>` |
| `_notices`, `_notifying` | the queue of observer notifications, so a chain of copies does not nest | `VecDeque<(Observer, FieldKey, NodeId)>`, `bool` |
| `_keyed`, `_completed_keys` | keyed subscripts `(key, container, node, read)` and the completion cursor; the cursor is set to the length after a loop over a copy, so entries added during the loop are not completed in that step | `Vec<(NodeId, ObjId, NodeId, bool)>`, `usize`, same semantics |
| `_Keyed`, `_KeyedGroup` | one keyed subscript; the reads or writes of one subscript site over every container and key that reaches it | `Constraint::Keyed { read, container, node, result, other_key }`; `Constraint::KeyedGroup(KeyedGroupId)` with `containers: Vec<ObjId>`, `keys: Vec<ObjId>`, `other_keys: FxHashSet<ObjId>` |
| `_compared_keys`, `_subscript_keys`, `_KeyLookup` | the objects compared by one hash-and-equality call; per `(key node, caller, site)` the lookup that pairs keys with stored keys | `FxHashMap<CallId, FxHashSet<ObjId>>`; `FxHashMap<(NodeId, Sym, Sym), KeyLookupId>`; `struct KeyLookup { call, compared, first: Option<ObjId>, many: bool, stored_keys: Option<IndexSet<ObjId>>, first_stored: bool }` |
| `_iterated` | per construct the node it iterates, and for `("keys", construct)` the hashed and kept nodes; a hit asserts the same iterable | `FxHashMap<Construct, (NodeId, Iterated)>`, `enum Construct` over every key shape (`Slice`, `Operator`, `Bound`, `("enumerate", call)`, `("zip", call, i)`, `("map", call, i)`, `("filter", call)`, ...) |
| `_dict_hubs`, `_DictHub`, `_DictItems` | the dict hub per source node: the intermediate dict, its hashed node, the source dicts and the targets in order, the sites, whether active | `FxHashMap<NodeId, DictHubId>`; `struct DictHub { container: ObjId, hashed: NodeId, sources: IndexSet<ObjId>, targets: IndexSet<(ObjId, Sym, Sym)>, sites: FxHashSet<(Sym, Sym)>, active: bool }`; `Constraint::DictItems { target, hub, pairs: Option<IterationId>, caller, site }`, with no results, as in Python |
| `_sequences`, `_Sequences` | per `(class, instance or class, iteration, dst)` the iteration through `__getitem__` | `FxHashMap<(ObjId, bool, IterationId, NodeId), SequencesId>` |
| `_Subscript`, `_Slice`, `_Unpack`, `_Iterate` | the site constraints, with their lazy site calls and iterators | `Constraint::Subscript(SubscriptId)`, `Slice`, `Unpack`, `Iterate(IterationId)`; the role of an iteration is an interned `Role` |
| `copy_range` | `slice(*bounds).indices(length)` without the step | a port of `PySlice_AdjustIndices` |
| `Each` rules | `_add_inexact`, `_enter_keys`, `next_element`, `_iter`, `_yield_from`, `_copy_elements`, `_metaclass_subscript`, `_class_subscript`, `_class_getitem`, `_generic_alias`, `_sequence_type`, `_next_item`, `KeyLookup.key`, `KeyLookup.stored` | `Rule` variants |

## `protocols.py` → `pycg_analysis::protocols`

| Python | Holds | Rust |
|---|---|---|
| `CONVERSIONS`, `PERCENT_CONVERSIONS`, `_BYTES_PERCENT_CONVERSIONS`, `_PERCENT_DIGITS_MAX_BY_PART`, comparison tables | the plans of conversions and comparisons; the printf conversions; the bounds that Python's `%` gives width (2^63 - 1) and precision (2^31 - 1) | `static` slices and `match`; the two bounds keep their names |
| `percent_spans` | the printf parser over code points | a port over `char`s; bytes are decoded as Latin-1, as Python does |
| `_Operator`, `_Operand` | an operator site: operands, method, reflected method, in place, unary, its calls per side, its membership iteration, its compare calls, its element comparison; `_Operand` carries `kinds` by `(membership, constants)` | arena `struct Operator`; `Constraint::Operand { operator, is_left, kinds }` |
| `_ElementComparison` | per family of containers, the nodes and flags of a comparison of elements | arena struct, `FxHashMap<Family, ([NodeId; 2], [bool; 2])>` |
| `_handlers`, `Container.repr_reach` | exception handlers attached once; what `repr()` of a container reaches | `FxHashSet<(ObjId, NodeId)>`; the `repr_reach` slot |
| `Each` rules | `_searched_type`, `_call_eq`, `_python_contains`, `arrive`, `_convert_container`, `_reach_nested`, `_percent_format`, `_percent`, `_finished`, `_await`, `_await_type`, `_awaited_itself`, `_with`, `_raise`, `_handler`, `compare_member`, `_call_protocol` | `Rule` variants |

## `builtin_rules.py`, `builtin_models.py`, `library.py`

| Python | Holds | Rust |
|---|---|---|
| `builtin_models.py` tables | 33 functions, 53 methods (21 of them `__next__` of lazy iterators, added at import), 30 library operations, 20 hashed arguments, and about 25 smaller tables | hand-ported `match` functions and `static` slices in `pycg_analysis::models`; a unit test compares them with the Python tables entry by entry (dumped by `tools/parity/dump.py`) until stage 10 |
| `_signature(text)` | parses `def f{text}: pass` once per text; keeps `str` and `int` constant defaults | the parsed signatures as `static` data written by hand from the 80-odd texts, checked by the same test |
| `apply_rule`, `_rule_*` | dispatch on the rule name (about 40 rules) | `enum ModelRule`, `match` |
| `_model_bindings`, `_Bound`, `_LateBound`, `_name_sets` | the binding of a call to a model signature per `(call, entry)`; a late binding whose parameter nodes are made on first read (`Solver.follower`); interned name sets | `FxHashMap<(CallId, ModelEntryId), BindingId>`; `enum Binding { Bound { .. }, Late { since: u32, nodes: FxHashMap<Sym, NodeId>, .. } }`; `FxHashMap<Box<[Sym]>, NameSetId>` |
| `_DynamicAccess`, `_dynamic_accesses` | `getattr`/`setattr`/`hasattr`/`delattr` with computed names: the name node, object, dst, src, call, names done, whether dynamic, loads made; the completion walks the live list | arena, `Vec<DynamicAccessId>` walked by index up to its live length |
| `_super_pairs`, `_super_accepted`, `zero_argument_super`, `_wrappers` (field form) | `super()` bookkeeping; wrappers made for an implicit method by `(kind, field)` | sets and maps of ids |
| `_ConstructSite` | a `(caller, site)` value used as a call stand-in | `#[derive(Eq, Hash)] struct ConstructSite(Sym, Sym)` |
| `_library_calls`, `_library`, `_library_advances`, `_OperationState`, `_Activation` | per `(origin, path)` the state of a standard-library operation (its arguments, sources, items, arities, shapes, made container, group, activations), the state of each lazy result, the found node per advance site | `FxHashMap<(Origin, Sym), OperationId>`, `FxHashMap<ObjId, OperationId>`, `FxHashMap<(ObjId, Sym, Sym), NodeId>`; arenas `Operation` (its `sources` shared with the grouper's state through a `SourcesId`) and `Activation`; `enum Position { At(u32), Unknown }` |
| `Each` rules of the three modules | `_implicit_method`, `_property_receiver`, `_derived_property`, `_bind_class`, `_bind_type`, `_sequence_length`, `_iterator_of`, `load_by_pattern`, `_super_*`, `_type_bases`, `_type_base`, `_call_type_metaclass`, `_reversed`, `_reversed_sequence`, `_reverse_sequence`, `_consume_library` | `Rule` variants |

## `outside.py` and `stubs.py` → `pycg_analysis::outside`, `pycg-stubs`

| Python | Holds | Rust |
|---|---|---|
| stub data | 555 JSON files, `{"modules": {name: {"names": {...}, "all": [...]}}}`, written sorted by `tools/generate_stubs.py`; entries of kind `f`, `c`, `p`, `v`, `r`; reduced types as nested lists | embedded with `include_bytes!` from a table that `build.rs` writes; decoded with `serde` per top-level package on first request, standard library first, then `third_party/`; `enum Entry` tagged by `k`, `enum Type` with a hand-written `Deserialize`; the `RETURNS_SELF` patch applied after decoding `typing`. `tools/generate_stubs.py` stays in Python: it is a tool, not the engine |
| `Definition` | kind, path, entry, owner; equal by `(kind, path, owner)` | `struct Definition { kind, path: Sym, entry: EntryRef, owner: Option<Sym> }` with `Eq` on the three |
| `Stubs` memo tables | `_module_by_name`, `_definition_by_path`, `_members_by_class_and_name`, `_mro_by_class` (a placeholder written before recursing, which breaks cycles), `_abstract_by_class`, `_abstract_reach_by_class`, `_abc_name_by_typing_path` | `FxHashMap`s with the same keys; the MRO keeps the placeholder rule, with an explicit stack |
| `_stub_definitions`, `_typed`, `_closures` | definitions per external name; typed objects by class and by `(class, name)`; closures by `(name, result type)` | `FxHashMap<Sym, Option<Rc<[Definition]>>>`; two maps for the two key forms; `FxHashMap<(Sym, TypeId), ObjId>` with interned types |
| `_grouped_externals` | whether an outside function's calls are grouped (the plain stub methods) | `FxHashMap<ObjId, bool>` |
| `_open_arguments`, cursor, `_unknown_modes`, `_open_modes` | the open-file mode records: the mode and buffering nodes, those made unknown at the third step, per `(call, mode)` the classes added | `Vec<NodeId>`, `usize`, `FxHashSet<CallId>`, `FxHashSet<(CallId, Sym)>` |
| `_stub_signatures`, `_model_bindings` (stub form) | signatures by `(path, overload, parameter count)`; bindings by `(call, path, overload)` | `FxHashMap<(Sym, u32, u32), SignatureId>`, `FxHashMap<(CallId, Sym, u32), BindingId>` |
| `_Context` | the typed context of a stub result: call, receivers, binding, parameters, origin, deferred | `struct TypeContext`; its `site` formats `str(origin[1])` for an owner tuple exactly as Python's `str` of a tuple, where it reaches a site |
| `Each` rules | `_method_function`, `_bound_to`, `_call_protocol`, `_new_instance`, `_made_instance`, `_open_mode`, `_open_buffering`, `_metaclass_protocol`, `_add_constraint`, `_add_instances_of`; the group observer `_add_results_of` | `Rule` variants; `GroupObserver::AddResultsOf` |
| tables (`KIND_CLASSES`, `BUILTIN_CONTAINERS`, `ABSTRACT_ITERABLES`, `GROUP_EXCLUDED_PATHS`, ...) | static | `match` and `static` slices |

## `annotations.py` → `pycg_analysis::annotations`

| Python | Holds | Rust |
|---|---|---|
| `OwnStub` | the module's own `.pyi`: parameter annotations per `(function path, name, kind)` in order (function aliases copied to a fixpoint), variable annotations, names per `(path, name)` with how they are bound, class bases; walked last in first out | `struct OwnStub` with `IndexMap`s; `enum StubBinding { Class(PathId), Import(Sym), Alias(AstId), Other }`; a `Vec` stack |
| builder state | `type_only_names`, `own_stub`, `_stub_scope_path_being_read`, `_source_annotated_names_by_scope`, `_source_classes_by_stub_path`, `_stub_aliases` | fields of the module builder; the path being read saved and restored around each read |
| string annotations | `ast.parse(text.strip(), mode="eval")` with positions relative to the stripped text | ruff in expression mode on the text stripped of Python's whitespace set (which includes `\x1c` to `\x1f` and `\x85`) |
| `_type_forms`, `_annotated`, `_families`, `_dataclass_like_classes`, `_structure_classes`, `_classes_below`, `_below_nodes` | type forms by `(operator, site)`; attachments by `(node, dst, shape)`, the first owner winning; the node of a class and its subclasses; once-only marks; analysed classes below an outside class, in order; their nodes by `(path, as class)` | `FxHashMap<(Operator, Sym), ObjId>`; `FxHashSet<(NodeId, NodeId, Shape)>`; `FxHashMap<ObjId, NodeId>`; sets; `FxHashMap<Sym, IndexSet<ObjId>>`; `FxHashMap<(Sym, bool), NodeId>` |
| `Each` rules | `_annotated_object`, `_annotated_subscript`, `_stub_base`, `_type_operand`, `_dataclass_decorator`, `_dataclass_base`, `_structure_base`, `_native_field`, `_field_values` | `Rule` variants |

## The builder and its parts → `pycg_syntax::scopes`, `pycg_analysis::builder`

`scopes.py`, `flow.py`, `matching.py`, `builder.py`, `expressions.py`.

| Python | Holds | Rust |
|---|---|---|
| `Scope` | kind, node, parent, names, private class, bound and defined names in order, globals, nonlocals, generator and async marks, rebound, shared, star import, dynamic, imports, definitions, reads | `struct Scope` in an arena; `IndexSet<Sym>` for `bound` and `defined`, `FxHashSet` for the rest; `owner` and `caller` as loops up the parents |
| `ModuleScopes` | the module scope, scopes sorted by position, the scope of each AST node, the names each loop binds, resolutions and inline answers (memoised), unread lazy imports | `FxHashMap<AstId, ScopeId>`, `FxHashMap<AstId, IndexMap<Sym, bool>>`, `FxHashMap<(ScopeId, Sym), ScopeId>`, `FxHashMap<(ScopeId, ScopeId), bool>`, `FxHashSet<AstId>` |
| `_Collector` | an explicit stack in pre-order over CPython's child order (`ast.iter_child_nodes`) | the same stack over a child iterator that follows CPython's `_fields` order, not ruff's source-order visitor |
| `mangle`, `_assign_names` | private names; `<lambdaN>` numbered by position per owner; comprehension names | functions |
| `flow.State`, `_Loop`, `Flow` | the definitions of tracked names along paths: a chain of states with their changes in order, reachability, narrowings; loop heads, entries and breaks; pending `finally` blocks; recorders | arenas `State { parent, changes: IndexMap<Sym, DefinitionId>, reachable, narrowed }`, `Loop`, `Flow`; a definition is an id (Python compares narrowed definitions by identity) with `node`, `unbound`, `truth`, `values` |
| literals of flow | `(type, value)` pairs, so `True` and `1` differ; Python truthiness and `==` in `match` | `enum Literal { Str, Bytes, Int(IntId), Float(f64), Bool(bool), None }` with Python's equality |
| `ModuleBuilder` state | `_classes`, `_variables`, `_untracked_nodes_by_scope`, `_builtin_globals`, `_maybe_builtins`, `_builtin_values`, `_names_bound_to_importlib`, `_import_module_names`, `_flows`, `_facts_by_expression`, `_operand_nodes_by_binop`, `_type_checking_truth_by_test`, `_assigned_by_declared_binding`, star imports | fields of `struct ModuleBuilder`, keyed by `AstId`, `ScopeId` and `Sym` |
| `Expressions`, `Bounds`, the statement visitors | one `Temp` node per expression; left-nested chains walked in a loop | `match` on the ruff AST through the position layer; an explicit stack where Python loops |
| sites | `module:line:column#end_line:end_column` (`#n` suffixes where one place has two) | formatted from the CPython positions of the position layer |

## `imports.py` and `program.py` → `pycg_analysis::program`

| Python | Holds | Rust |
|---|---|---|
| `ImportManager` | the import graph (file and imports per module), extension modules, the current module, the root, listed directories | `IndexMap<Sym, ImportNode>`, `FxHashMap<Sym, PathBuf>`, `FxHashMap<PathBuf, Rc<FxHashSet<OsString>>>` |
| `BUILTIN_OR_FROZEN_MODULES` | a fixed list, not the running Python's | the same `static` list |
| `_find_modules`, `_candidates`, `extension_name` | parts checked with `str.isidentifier()`; candidates package, module file, extension binaries sorted by name | Python's identifier rule (XID with the NFKC check of CPython); names sorted as Python sorts `str`, by code point, which for UTF-8 names is byte order |
| `SourceModule`, `Program` | modules in build order, extension modules, entry module names, entry-only files, star imports inside and outside, exports in order, modules declaring `__all__` | `IndexMap`s and sets; the breadth-first build from a `VecDeque`, `_link_submodules` and `_link_star_imports` in the same order |
| paths | `os.path.abspath`, `relpath`, `commonpath`, `split`, `join` (posixpath, or ntpath on Windows), `isfile` and `isdir` (following links) | the lexical rules of posixpath and of ntpath written in `pycg_analysis::program::paths` (no crate), the platform's chosen at compile time, tested on Linux against Python 3.14's two modules (`tools/parity/paths.py`); checks through `std::fs::metadata` |
| `gc.disable()` | performance only in Python | nothing |

## `formats/` → `pycg-document`

| Python | Holds | Rust |
|---|---|---|
| `document.build` and its parts | the document of `docs/format.md`, every list sorted | `struct Document` built in the same order of parts; sorting by the same keys, strings compared as Python compares `str` |
| `dumps` | `json.dumps(sort_keys=True, separators=(",", ":"))` with `ensure_ascii`: every character past U+007F as `\uXXXX` (surrogate pairs past the BMP), lower-case hex, control characters as `\n`, `\r`, `\t`, `\b`, `\f` or `\u00XX` | a writer of about 100 lines over a `BTreeMap`-ordered value; tested on the D6 of every oracle document (parse with `serde_json`, write, compare bytes) |
| `edges` | the classic call graph | a function of `Document`, for the evaluation runner |
| `_typeshed_commit` | the commit in `stub_data/README.md` | read by `build.rs` |
| `pycg.view` | `pycg-view`: the document checked and embedded in `template.html` | `pycg view`, the template embedded with `include_str!` |

# 3. The parity harness

Parity is decided on documents: for every input, the SHA-256 of the Rust
document equals that of the oracle's, byte for byte. Before the documents
can agree, each stage is checked on an intermediate dump, so a difference
is found in the part that made it, not 40,000 edges later.

## Inputs

| Set | Inputs | Documents |
|---|---|---|
| Micro | the cases of `evaluation/micro-benchmark/snippets` that Python 3.14 runs: 688 of the 696 (the 8 that need 3.15 are left out) | 688 |
| Macro | the 60 projects of `evaluation/macro-benchmark/projects.toml`, as `make eval` analyses them | 60 |

The 20 packages of the scale set are not inputs of the parity job: stage 7
measures them with `make eval-scale` and `make eval-scale-rust` (section 6).

The oracle runs each input with `PYTHONHASHSEED` 0 and 1 and must give the
same dumps for both (the engine's determinism rule; a difference is an
oracle bug, reported and fixed on `main`). The Rust side has no seed: the
replays of D1 to D4 run twice, and each run is compared with the oracle.
One differing byte fails the input; one failed input fails the job.

The full document is compared, not the edges that `make eval` scores:
`modules`, `definitions` with lines and MROs, `exports`, `outside` with
`known`, every call site with its position, `implicit` and `unresolved`
cause. `tool.version` is the version of `pycg/__init__.py`, which the Rust
build reads (`build.rs`), and `tool.typeshed` the commit of
`stub_data/README.md`, which the embedded stub data carries; so the two
tools write the same `tool` part.

## Intermediate dumps

The oracle is not changed to emit them. `tools/parity/dump.py` (Python,
part of the harness) imports the oracle's `pycg.analysis`, runs it on one
input, and writes the dumps from the engine's own structures, wrapping
methods in that process where a dump needs a sequence of calls. The Rust
side is `pycg-dump`, which links the crates and writes the same dumps.
Each dump is JSON lines, one record per line, canonical: no addresses, no
Python `id()`, objects named by their identity key (the *Termination*
table of `docs/design.md`: a class by its definition site, an instance by
class and origin, a constant by `ascii()` of its value, and so on), nodes
by their label or, without one, by their creation number within the
module that the builder was walking.

| Dump | Records | Oracle side | Compared |
|---|---|---|---|
| D1 positions | every AST node that the builder reads a position of: kind, `lineno`, `col_offset`, `end_lineno`, `end_col_offset`, in `ast.walk` order of the kinds that the builder visits | `ast.parse` of the source that `program._read` gives | exactly, per module, in order |
| D1 scopes | every scope (kind, name, generator and async marks, position), its bindings by kind (local, parameter, global, nonlocal, imported, annotated only), the resolution of each name read, the loop bindings, the rebound names, the unread lazy imports; the read or parse failure and its cause | `scopes.analyse_scopes` on that tree | exactly, per module |
| D2 stub queries | every call of a `Stubs` method made during the analysis, with its arguments and its answer (definitions by kind, path and owner; MROs as lists of paths) | a wrapper of each public method of `Stubs` | the Rust stubs answer the recorded queries; every answer equal |
| D3 solver trace | the calls into `Solver` (`node`, `constant`, `add_object`, `add_edge`, `attach` with a constraint number, `apply_now`, `follower`, `objects`, `holds`, `is_saturated`, `solve`, the `between_rounds` answers), and, for each application of a constraint to an object, the calls that it made | a subclass of `Solver` that records | the Rust solver replays the trace, with recorded applications as its constraints; the sequence of operations, then per node the final set, saturation, the absorbed set, the number of rounds, the round in which each object first arrived at each labelled node (the measure of `tests/test_waiting_lookups.py`) and the work counters |
| D4 builder | per module, in emission order, every call that the builder makes into `Analysis` (`node`, `constant`, `function`, `new_class`, `add_edge`, `add_load`, `add_store`, `add_call`, `site_call`, the container, iteration, operator and annotation constructors, ...) with every argument by its parameter name, defaults applied, in canonical form, before solving, and its calls into the import manager (`handle_import`, `locate`) with their answers; at the end of each module, the entries the builder added to the analysis tables it writes (`iterated_expressions`, `literal_imports`, `none_arguments`, `none_keywords`, `read_namespaces`, `zero_argument_super`), then the fields it writes on the module and on each function and class made during the build (`BUILDER_FIELDS` of `dump.py`); under the module `<program>`, the same calls that `Program` makes outside the builds and before solving (the imports of the submodules a star import lists, the linking of submodules and star imports), then the `defines` of each module that the linking changed, by module name | a wrapper of those methods during `Program._build` and in `Program`'s context, a snapshot of the tables and the fields, and a guard that fails on a builder write to a field the dump does not record | exactly, per module, in order |
| D5 points-to | `output_points_to()`: every named node and the sorted names of what it holds | the oracle's `CallGraphGenerator.output_points_to` | exactly, per input; the first check of a rule family before the call graph agrees |
| D6in document inputs | what `formats/document.py` reads from the analysis: the functions and classes with their positions and MRO bases, the fields of each built module, the site edges with their constructs, the call and iterated expressions, the unresolved calls, the external callees and the cap | `document_inputs` of `dump.py` | exactly, per input |
| D6 document | the document | `CallGraphGenerator.document()` written by `pycg.formats.dumps` | SHA-256, per input and seed |

D1, D3 and D4 are compared in order: the builder is a translation that
walks the same tree in the same order, and the solver keeps the engine's
order of work until stage 7 (section 2, *Conventions*), so the first
differing record names the construct or the operation. D5 is compared as
sets of names. The work counters of `Solver.work` are part of D3 and must
be equal while the order is the same; from stage 7, when the Rust solver
may take another order, D3 compares only the final sets and the first
rounds, and the counters are printed for both sides. Order independence
(Part 3 of `docs/design.md`) says the result does not change; a difference
that then disappears under another order of the oracle (`Solver.order`)
is an order dependence of the oracle, a bug of `main`.

`tools/parity/diff.py` explains a failed comparison: for dumps the first
differing record with its context, for documents the edges, sites,
causes and definitions that one side has and the other lacks, in the
raw names of `loop.py compare`.

## Commands

| Command | Does |
|---|---|
| `make parity-oracle` | Runs the oracle on every input for both seeds in the sandbox of `make eval` (no network, read-only checkout), writing D1 to D6 and D6in for every input, into `$EVAL_OUT/parity-oracle-<key>`; `PARITY_SETS=micro` or `macro` limits it to one set |
| `make parity` | Builds `pycg` and `pycg-dump` (`cargo build --release --locked`), runs them on the same inputs in the same sandbox, and compares every dump that `tools/parity/required.txt` names, and every D6; renders every D6 of the oracle with `pycg-view` and with `pycg view` and compares the pages byte for byte (`tools/parity/view.py`); runs `pycg` on every input that `tools/parity/differences.txt` does not list for the engine, with the package root and entry points of the oracle's run and compares its document with D6 byte for byte (`tools/parity/program.py`) |

The key of an oracle run is the SHA-256 of the git tree of `pycg/`, the
inputs key (`tools/inputs_key.py`) and the digest of the Python image: the
oracle runs once per key, and its output is cached.

`tools/parity/required.txt` lists the dumps that must agree; each stage
that ends adds its own (section 4), and none is ever removed. A dump that
the Rust side does not write yet is reported as missing, not compared.
`tools/parity/differences.txt` lists the inputs of a run (`replay` for
the replays, `engine` for the engine) that are known not to agree yet, one
per line: run, dump, input, status (`different`, `partial` or `failed`)
and cause. Every other input must agree; a listed input must keep its
status and its differing dumps, and fails once it agrees, so a pull
request that makes an input agree removes its line. The list only
shrinks: given the base's list (`make parity BASE=<commit>`), an entry
the base lacks fails, so a newly differing input fails the job.

`make parity` also drives the Rust engine from the oracle's D4 (`pycg-dump
engine <D4.jsonl> OUT`): it makes each recorded builder call, checks its
answer against the recorded one, solves, and writes D3 and D5 of the
engine. The fields and tables that D4 records at the end of a module are
set when their object is made. A builder call or a rule that is not
ported stops the replay with `not ported: <what>`, and the trace written
up to there (`D3.partial.jsonl`) must begin the oracle's D3: compare.py
counts such an input as partial, and as different when the trace leaves
the oracle's first. D3, D5, D6in and D6 of the engine, the document
built by `pycg-dump document-build` from the engine's D6in, must agree on
every input that `tools/parity/differences.txt` does not list for the run
`engine`; each pull request of stage 5 removed the lines of the inputs it
made agree, and the list is empty.

## The CI job

`.github/workflows/parity.yml`, added by the stage 0 pull request that
names it (`.github/` is protected; that task names the file and its
content):

1. Runs on pull requests against `base/rust-rewrite` and on pushes to it.
2. Job `oracle`: computes the key; restores `$EVAL_OUT/parity-oracle-<key>`
   from the Actions cache; on a miss, pulls the inputs images
   (`make eval-inputs`) and runs `make parity-oracle`, the micro and macro
   sets in two parallel jobs. A pull request that does not touch `pycg/`
   hits the cache.
3. Job `rust`: `cargo fmt --check`, `cargo clippy --locked --all-targets
   -- -D warnings`, `cargo test --locked`, then `make parity BASE=HEAD^1`
   against the oracle's output, so that `differences.txt` only shrinks;
   the job summary has one line per set (inputs, identical, different,
   failed) and the explanation of the first ten differences.
4. The pull request is green only when both jobs pass. The existing CI
   (lint, the Python tests, the gate) runs as before: the Python engine is
   unchanged until stage 10.

Both jobs run on the standard runner. The scale set is left out of the
job: the oracle takes more than 72 minutes of analysis on it for the 18
packages that finish (section 6), plus numpy, which runs for more than an
hour, and two packages do not fit a standard runner of 16 GB (pandas peaks
at 13.8 GiB, sympy needs more than 14.5 GiB).

# 4. Stages

Each stage is a few pull requests against `base/rust-rewrite`, each one
change in one commit, as `AGENTS.md` asks. A stage is done when its "done
when" holds on the parity job, and then its dumps join
`tools/parity/required.txt`. The micro-benchmark categories below are the
directories of `evaluation/micro-benchmark/snippets`.

| Stage | Content | Pull requests | Done when |
|---|---|---|---|
| 0 Harness | The workspace with empty crates, `rust-toolchain.toml`, `Cargo.lock`, clippy configuration (`disallowed_types` for `std::collections::HashMap`/`HashSet`, `unwrap_used` outside tests); `tools/parity/` (`dump.py`, `compare.py`, `diff.py`, `required.txt`); `make parity-oracle`, `make parity`; `.github/workflows/parity.yml` | 3: workspace; oracle dumps D1 to D6 with their tests; the workflow | The oracle writes D1 to D6 for every input, both seeds give one D6, and the job runs green with nothing required |
| 1 Syntax and scopes | `pycg-syntax`: reading (cookie, BOM, newline translation, decode errors), ruff parse with the 3.14 grammar and CPython's acceptance (section 5, *Risks*), the CPython position layer, constant evaluation (big ints, floats, escapes, implicit concatenation), identifier NFKC, CPython child order, the scope pass | 4: reading and positions; constants; scopes; lambdas and names | D1 identical for every module of the micro and macro sets and the scale set |
| 2 Stubs and model | `pycg-stubs` (embedded data, lazy per top-level package, every query of `stubs.py`, C3 of `mro.py`); the object kinds and identity keys of `model.py`, `Signature`, constant names (`ascii()`, `hex()` past 640 digits); the static tables of `builtin_models.py` | 3: stub data and queries; MRO and abstractness; model and tables | D2 replays identically for the micro and macro sets |
| 3 Solver | `pycg-solver`: arenas, hash-consed sets of sorted object numbers, memoised union and difference, the sweep, nodes with the one-successor form, constant nodes, `follower`, rounds, the firing groups, cycle collapsing with the search budget, saturation and absorption, `Watch` and `Witness`, the work counters, the seeded orders for tests | 4: sets; propagation and rounds; cycles; saturation, watches, replay | D3 replays identically for the micro and macro sets, and the simulation tests of section 5 pass |
| 4 Builder | `ModuleBuilder` and its parts (`builder.py`, `expressions.py`, `flow.py`, `matching.py`, `patterns.py` builder half, `annotations.py` builder half, `narrowing.py` builder half), `imports.py`, `program.py` (discovery, linking, star imports, exports), with the analysis calls as stubs that record | 5: statements and flow; expressions and comprehensions; patterns, `match` and class tests; annotations and own stubs; discovery and linking | D4 identical per module for every input; `modules`, `definitions` and `exports` of D6 identical |
| 5a Rule core | `semantics.py` (objects, `Call`, `call`, site calls, implicit calls, dunder calls, prefixed calls, bound groups, `_Returned`), `arguments.py`, `attributes.py`, `hierarchy.py` | 4: calls and arguments; attributes and descriptors; hierarchies and lookups; waiting rules and deliveries | D5 and D6 identical for the categories `direct_calls`, `functions`, `args`, `kwargs`, `returns`, `lambdas`, `closures`, `assignments`, `decorators`, `classes`, `mro`, `descriptors`, `metaclasses` |
| 5b Containers | `containers.py`, `library.py` | 2 | D5 and D6 identical for `lists`, `tuples`, `sets`, `dicts`, `comprehensions`, `generators` |
| 5c Protocols | `protocols.py`, the rule half of `narrowing.py` and of `patterns.py` | 2 | identical for `operators`, `strings`, `context_managers`, `exceptions`, `async`, `match`, `control_flow`, `new_syntax` |
| 5d Builtins | `builtin_rules.py`, `reflection.py` | 2 | identical for `builtins`, `dynamic` |
| 5e Outside | `outside.py`, the rule half of `annotations.py` | 3 | identical for `external`, `stdlib`, `stdlib_classes`, `type_hints`, `imports` |
| 6 Fixpoint and output | `Analysis.solve` and the steps at a fixpoint, `unresolved_calls`, `pycg-document` and its writer | 2 | D6 identical for all 696 micro cases and all 60 macro projects, for both seeds |
| 7 Scale | Whatever the scale set finds; then the time and memory work of section 6 | as needed | D6 identical for the 20 scale packages, and every target of section 6 met |
| 8 Command line and distribution | `pycg` (options of `__main__.py`), `pycg view`, the evaluation flavour `rust` in `evaluation/common/analyse.py`, the release workflow (release binaries built by CI for every platform of section 5, a dry run of the publication of the crates on crates.io) | 4: command line; `pycg view`; evaluation flavour; release workflow | `make eval` with the Rust flavour gives the metrics of the Python engine exactly; a release from a test tag gives an archive per platform whose `pycg` runs the micro-benchmark, and `cargo install pycg --locked` from a `cargo package` of the workspace builds the same program |
| 9 Tests in Rust | The test approach of section 5 | about 8, one per test family | Every behaviour that a Python test pins is a Rust case or property, and the Rust suite passes |
| 10 Switch | The last release of the pip package, with the deprecation message (section 5); the first release of the Rust tool; then `make eval`, CI and the gate measure the Rust program, and the Python engine and its tests are removed | 3: the last pip release; the first Rust release; the removal | the pip release prints the message and analyses as before; `main` has no `pycg/` engine code and no Python packaging of it; the gate passes against the bests of `evaluation/metrics.json` unchanged |

After stage 10, algorithmic work continues in Rust under the rules of
`AGENTS.md`: each change measured by `make eval` and `make eval-scale`, its
output compared with its base.

## What runs in parallel

```
0 ─┬─ 1 ─────────┐
   ├─ 2 ─────────┼─ 4 ─ 5a ─┬─ 5b ─┐
   ├─ 3 ─────────┘          ├─ 5c ─┤
   └─ 8 (CLI, writer)       ├─ 5d ─┼─ 6 ─ 7 ─ 9 ─ 10
                            └─ 5e ─┘
```

- Stages 1, 2 and 3 share no code: three agents, one per crate, after
  stage 0. The solver needs only the trace format of stage 0.
- The writer of `pycg-document` (Python's `json.dumps` escaping, compared
  on the D6 of the oracle by re-encoding it) and the command line need
  nothing else: a fourth agent, from stage 0 on. The last pull request of
  stage 8 (the evaluation flavour and the release workflow) waits for
  stage 6.
- Stage 4 needs the syntax layer and the model; its five pull requests
  are split by construct and can go to two or three agents, since each
  writes its own part of the builder against the recording stubs.
- 5a is one agent, or two (calls and arguments; attributes and
  hierarchies), because every other family calls into it. 5b to 5e are
  four agents at once; a micro case that needs two families counts for
  the one of them that finishes last.
- Stage 9 splits by test family (section 5) across agents once stage 7
  is done.

Two agents never edit one module in the same stage: the table of
section 2 gives each Rust module one owner per stage.

# 5. Testing, distribution, risks

## Testing

The Python suite has 1,538 test functions in 41,547 lines. Most analyse a
small program and check edges through `tests/programs.py` (43 files); 19
files import `pycg.analysis` to reach the engine (`program.analysis`, the
solver, private tables) and check an invariant or a record; and
`tests/unit/test_solver.py` (1,368 lines) pins internals of the solver.
The Rust suite keeps what they state and drops how they state it.

The four kinds weighed:

| Kind | What it gives | What it costs | Weight |
|---|---|---|---|
| End to end: a program and its document | States what PyCG must give; survives any rewrite of the code under it; the same form as the micro-benchmark; the oracle can write the expected document while it exists | Says nothing about the many orders and states one program does not reach | The base: every behaviour |
| Deterministic simulation | Runs the solver and the whole analysis under many orders chosen by a seed and checks properties that must hold for every run: one document, termination, the bounds, the work bounds of `test_scaling.py`; one seed reproduces a failure | Needs the order as a parameter of the code under test (`pycg_solver::Order`, as Python's `Solver.order`) and the property checkers | The second pillar: the invariants of Part 3 of `docs/design.md` |
| Fuzzing | Finds the programs nobody wrote: crashes, hangs, a difference between two runs, a difference from the oracle | Needs a generator of valid programs | The third: robustness on every pull request, and once a difference from the oracle on 10,000 generated programs |
| Unit tests | Fast and precise | Pin internals; a rewrite breaks them without a bug | Only pure functions with a specification of their own |

**Recommendation: end-to-end cases as the base, deterministic simulation
for the invariants, fuzzing for robustness, and unit tests only for pure
functions that Python defines.** The reasons: parity makes the document
the specification, so a test of anything else tests the port's
structure, which stage 7 is meant to change; the order-independence and
termination arguments of `docs/design.md` are statements about every run,
which only a simulation over many seeded runs checks; and the existing
suite already shows the cost of the alternative, a 1,368-line unit test
of the solver that a change of its sets would rewrite.

How each becomes Rust (stage 9):

1. **Cases.** A case is a directory under `tests/cases/<family>/<name>/`:
   `program/`, the program's files; `case.json` (entry points and package
   root, relative to `program/`, the cap, the section of `docs/design.md`
   that the family pins, a one-line statement, the Python test it comes
   from, and `focus`, the callers that the test read); and
   `expected.json`, the oracle's output: the edges in the format of
   `pycg.formats.edges` (every caller, with an empty list for one that
   calls nothing), the unresolved sites as `[caller, site, cause]`
   (`Analysis.unresolved_calls`), the points-to sets of the named nodes
   that the test read (`output_points_to`), the warnings, and each
   document that the test read with the package name and version it
   asked for. The
   expected edges are exact, so a test's assertion that an edge is
   present or absent holds in the case; `focus` names what the test was
   about, and the harness prints the differences of those callers first.
   JSON, not TOML, so that the harness needs no crate beyond `serde_json`.
   The harness, `crates/pycg/tests/cases/main.rs` (`harness = false`), runs
   every case and every micro case through `Program`, `Engine` and
   `pycg_document::build`, and prints for each failure the edges, sites
   and points-to names gained and lost, or the first path at which a
   document differs. Every document that the harness builds must also be
   consistent in itself: each caller a definition, each callee a
   definition or outside, the callees of a site sorted and distinct, a
   site with no callee unresolved, the sites of a caller sorted and
   distinct, and no site naming its caller's own module (the property of
   `test_the_edges_of_the_document_are_consistent`, over every case and
   every micro case). A micro case is compared with its
   `callgraph.json`, a case of `tests/known_failures.txt` must differ from
   it, and a case that needs a newer Python than the parser's
   (`pycg_syntax::parse::TARGET_VERSION`) is left out, as the Python suite
   skips it. `tests/cases/pending.txt` lists, sorted, each case that the
   Rust engine does not give yet, with its cause (`<case>\t<cause>`); it
   is strict, as the known failures are: a listed case that passes fails
   the suite, and a pull request removes the lines of the cases it makes
   pass and never adds one. A Python test becomes cases by
   `tools/parity/cases.py <test file>`, which runs the file's tests under
   the oracle and writes one case per program a test analyses
   (`<test name>-2` for the second); `FAMILIES` of the script names each
   file's family and section. A test that monkeypatches an attribute is
   not converted but listed: it states an invariant, for the simulation
   below. So are a test that analyses no program in its own process and
   a test that analyses micro cases, which the harness runs anyway. A
   hypothesis property runs with seed 0, and each of its examples is a
   case. The 43 test files that use `tests/programs.py`
   convert this way; their families (`calls`, `classes`, `containers`,
   `outside`, ...) are the directories.
2. **Simulation.** `pycg-solver` and `pycg-analysis` take an `Order`
   (`pycg_solver::Order`: `Canonical`, the FIFO of the program;
   `LastInFirstOut`; `Reversed`; and `Shuffled`, a SplitMix64 with a
   seed). The properties, each a test that takes a seed range and prints
   the seed that fails:
   - every case and every micro case gives one document under 5 seeded
     orders and every order of its entry modules
     (`test_order_independence.py`);
   - with caps of 1, 2 and 3, the same, and a cap only removes edges
     where no fixpoint step applies (`test_saturation.py`);
   - waiting rules give what rules run at once give, round by round
     (`test_waiting_lookups.py`), using the order hook to run them at once;
   - the solver agrees with a brute-force reference of the rounds on
     random constraint systems (`test_solver_properties.py`, which uses
     hypothesis today; the Rust generator is seeded by hand);
   - the work counters grow linearly with the size of a hub
     (`test_scaling.py`), with no clock;
   - every table of what the analysis makes on demand stays under its
     bound on the termination families (`test_termination.py`): the
     tables are counted through one `Analysis::table_sizes` that lists
     every table, so a new table cannot be left out.
   Each property comes with a planted bug that it catches, as `AGENTS.md`
   requires: a `cfg(test)` switch that breaks the rounds, a waiting rule
   that runs late, a cache key that loses an argument; the test of the
   property asserts that the switch makes it fail.
3. **Fuzzing.** `crates/pycg/tests/fuzz/generator.rs` ports
   `tests/fuzz_programs.py`, and `crates/pycg/tests/termination/` the
   fixed programs and the five random families of
   `tests/test_termination.py`, each driven by a seeded SplitMix64, so a
   seed gives the same program in every run. Properties: no panic; one
   document, warnings included, in two runs and under two orders; and
   every table of `Engine::table_sizes` under its bound. A one-off
   comparison of 10,000 generated programs with the oracle (D6) stands in
   for a nightly job, and every program that fails becomes a case.
4. **Unit tests**, only for: `ascii()` and `hex()` of constants, the JSON
   writer, `percent_spans`, `formatter_parser`, `slice.indices`, C3 and
   `linearizations`, identifier rules, the reading of encodings and the
   position layer. Their expected values are vectors that a Python script
   writes once (`tools/parity/vectors.py`), committed as data. The Python
   unit tests of these functions run under the oracle to add their own
   inputs to the vectors: the hierarchies of `tests/unit/test_mro.py`
   (hypothesis with seed 0) go to `linearize.json`, the programs of
   `tests/unit/test_scopes.py` to the D1 programs of `pycg-syntax`
   (`d1/scopes_<n>.py`, by `tools/parity/syntax_vectors.py`), and the
   queries of `tests/unit/test_stubs.py` on the shipped data, with their
   answers, to `crates/dump/tests/vectors/stubs.jsonl`, which
   `pycg-dump stubs` replays. The import manager has its own vectors
   (`tools/parity/import_vectors.py`): for each manager that a test of
   `tests/unit/test_imports.py` makes, the files of the test and each call
   with its answer, which `crates/analysis/tests/imports.rs` replays in the
   same layout. The type-only names of `tests/unit/test_type_only_names.py`
   are builder vectors whose annotations read them (`type_only_names`,
   `dead_blocks`).

What is dropped as clutter: the tests that pin internals
(`tests/unit/test_solver.py`, the assertions of `test_records.py` on
private tables, where an end-to-end case states the same; `test_garbage.py`,
which is about Python's collector), the
tests of the Python tooling that leaves (`test_no_comments.py` stays for
the Python harness), and duplicates: where several Python tests analyse
one program and check different edges, they become one case.

The tests of the evaluation (`evaluation/tests/`) stay in Python with the
harness.

## Command line

`pycg` keeps the interface of `pycg/__main__.py`: entry points, `--package`,
`--package-name`, `--package-version`, `-o`, `--cap N|none`, the same
errors for a bad cap, the document on standard output or in the file,
with a final newline. `pycg-view` becomes `pycg view`. The
warnings of `program.py` go to standard error, one line each, in the
order of the analysis, with the same text: an entry point outside the
package root, a stub, a directory, the package root as an entry point, and
a module nested deeper than the bound. A module that cannot be read or
parsed is warned with the same words, but the reader's or parser's cause
of the document (`FileNotFoundError`, `SyntaxError (line 3)`) stands in
for CPython's message (section 5, *Risks*). The exit status is 0 on a document,
1 when the document cannot be written, 2 on a usage error, and 3 when the
analysis meets a part that is not ported yet, with the line `pycg: not
ported: <what>`. A broken assertion exits with 101 and one line, `pycg:
internal error at <file>:<line>:<column>: <message>`, the message's line
breaks written as `\n`.

## The pip package

| Option | For | Against |
|---|---|---|
| A: the last Python release prints a deprecation message that points to the Rust tool | No release work in this repository beyond one release; the Rust tool is distributed as release binaries and on crates.io | `pip install pycg` and `uvx pycg`, how most users meet PyCG, stop giving the current tool; users must find another install path, and a project that pins `pycg` in its tooling must change its setup |
| B: the pip package ships the Rust program: a binary wheel built by maturin with `bindings = "bin"` (the way ruff and uv ship), no Python code in it | `pip install pycg` keeps working and gives the fast tool; one artefact for pip, pipx and uv; PyPI's platform tags pick the binary | CI builds wheels for each platform (Linux x86-64 and arm64 for glibc and musl, macOS x86-64 and arm64, Windows x86-64), about 60 lines of workflow and a few minutes per release; the importable API (`from pycg.pycg import CallGraphGenerator`) ends, since the wheel holds no module |

**Decision: A** (the maintainer's). The pip package does not ship the
Rust program. Its last release, made in stage 10, is the Python engine of
the oracle unchanged, plus a deprecation message: `pycg` and `pycg-view`
print it to standard error before they run, and `import pycg` emits it as
a `DeprecationWarning`. The message names the Rust tool, its two install
paths (below) and the JSON document of `docs/format.md` as the interface
that replaces the importable API. After that release the pip package gets
no more releases; it is not removed from PyPI, so pinned installs keep
working.

The Rust tool is to be distributed in two ways. The release workflow
(`.github/workflows/release.yml`) builds both from a tag and publishes
nothing yet: the archives and their `SHA256SUMS` are workflow artefacts,
and the crates.io publication is a dry run (`cargo publish --workspace
--dry-run`) whose packages `tools/release/packaged.sh` installs and
compares with the workspace's program. The first release of stage 10
publishes them:

1. **Release binaries built by CI**: one archive per platform (Linux
   x86-64 and arm64, glibc and musl; macOS x86-64 and arm64; Windows
   x86-64), each with the `pycg` program and the licences, attached to the
   GitHub release of the tag with a SHA-256 file.
2. **crates.io**: `cargo install pycg --locked`. The program and the
   workspace crates it links (`pycg-syntax`, `pycg-stubs`, `pycg-solver`,
   `pycg-analysis`, `pycg-document`) are published at one version; the
   name `pycg` is free on crates.io (checked on 2026-11-26). `pycg-dump`
   is not published.

The stub data is embedded in the program uncompressed (22 MB of JSON), so
one file is the whole tool. A release archive compresses it to about
2.4 MB (measured: `zip -9` of `stub_data/`), and so does the `.crate`
of `pycg-stubs`, which carries the data as it is: under the 10 MB that
crates.io takes for a compressed crate.

The evaluation runner runs the binary built from the checkout as a
subprocess (flavour `rust` of `evaluation/common/analyse.py`), measuring
time and the peak resident set of the child as it does for Python.

## Risks

| Risk | How it shows | Bound |
|---|---|---|
| ruff's parser accepts or rejects other programs than CPython 3.14, or recovers from errors where CPython fails | A module `failed` in one document and analysed in the other | D1 compares the status and cause of every module of every input; a corpus of the syntax-error tests of CPython's `Lib/test/test_syntax.py` and `test_grammar.py` (data, read by a test) checks acceptance; where ruff reports an error, the Rust side fails the module as CPython would |
| A warning for a module that cannot be read or parsed carries CPython's exception message (`[Errno 2] No such file or directory: '…'`, `invalid syntax (x.py, line 1)`) | Another standard error than Python's for such a module | The Rust side prints the same words and file with the cause that the document records; the message of CPython's tokenizer and parser is not ported, as ruff's errors are not CPython's; the case harness compares such a warning up to its cause (`: cannot parse it: `, `: cannot read it: `), so its kind, file and order are checked and the cause's wording is not |
| The line of a `SyntaxError` differs | The cause `SyntaxError (line N)` differs | The same corpus checks lines; if a class of errors cannot be matched, the oracle's cause drops the line on `main` (a format change, decided by the maintainer) rather than the port approximating it |
| CPython's positions differ from ruff's ranges (decorated definitions, a generator expression that is a call's only argument, parenthesised expressions, implicit concatenation, f-string parts) | Different sites, different lambda numbers | D1 compares every position the builder reads, on every module of every input, before anything else is built |
| Identifiers that CPython normalises (NFKC) | Different names | D1 includes names; NFKC is applied with a table generated from Python's `unicodedata` by a tool script and committed as data, since no crate is pulled in for it |
| Encodings other than UTF-8 (PEP 263 cookies) | A module that one side cannot read | The Rust reader supports UTF-8, the BOM and the single-byte codecs (Latin-1 and the `cp125x`/`iso8859-x` tables, generated from Python's codecs as data); a cookie naming another codec is a read failure with Python's cause, and D1 shows whether any input uses one |
| Inputs beyond the limits of CPython's parser | A module `failed` with another cause, or analysed, on one side | The Rust reader has the tokenizer's exact limits (100 indents, 200 brackets, 149 nested f- and t-strings). For the parser's stack (`MemoryError`, rule depth past 6,000) it fails a statement with a chain of one construct past the count at which CPython 3.14.10 fails: 5,967 unary `-`, `+` or `~`, 5,968 `not` or conditional expressions, 5,963 `elif`, 2,984 lambdas or `**`, 200 nested `and`/`or`. For the C stack (`RecursionError`) it fails a statement deeper than 43,482 levels; CPython's own count moves by a few levels with the C stack already in use. A known divergence: a mixture of constructs, or a chain near the C-stack count, may fail on one side only. No benchmark input comes near: the deepest statement of micro, macro and scale is 31 levels. `crates/syntax/tests/vectors/bounds.txt` checks each measured flip |
| Input nested deeper than the Rust stack holds (ruff's parser and the drop of its tree recurse) | An abort where the oracle fails the module | `pycg_syntax::parse::with_parsed` runs the parse, the caller's work on the tree and its drop on a thread whose stack is 8 MiB (the default main thread's) plus twice the most stack per source byte measured over 17 nested constructs: 2,213 bytes, in a debug build (`[*` nesting; 992 in release), for every profile. Nesting cannot exceed the source length. On Linux and macOS the stack is reserved with `mmap(MAP_NORESERVE)` and a guard page, so it costs memory only as far as it is used (a plain thread stack is accounted, and one of 8 GiB does not start on an 8 GiB machine with the default overcommit policy), and the thread is made with `pthread_attr_setstack`; on Windows `std::thread::Builder` already only reserves its stack (`STACK_SIZE_PARAM_IS_A_RESERVATION`). The parity job runs the Linux path and lints the workspace with clippy for `aarch64-apple-darwin`, `x86_64-pc-windows-gnu` and `x86_64-pc-windows-msvc`; the release workflow builds the program for every platform of the release and runs it on the micro-benchmark (`tools/release/micro.py`) |
| `RecursionError` in the Python builder gives the status `partial`, which depends on the Python stack | A module `partial` on one side | Before stage 4, the oracle replaces this dependence by a named depth bound in the builder (a change on `main`, with its own pull request), which the Rust builder implements; if no input reaches it, the bound only needs a case |
| A hidden order dependence in the oracle | A parity failure that moves with the order | The port keeps the oracle's order until stage 7 (section 2); a difference found later is reproduced on the oracle with `Solver.order`, fixed on `main` and merged |
| `main` moves while the port runs | The oracle changes under a stage | Merges into `base/rust-rewrite` only between stages, each with the Rust change it needs; the oracle key of the parity job names the engine it compared |
| Python facts that are easy to get almost right: `ascii()`, `json.dumps` escaping, `str.format` and `%` parsing, `slice.indices`, `str.strip`, `isidentifier`, sorting of `str`, `int` without bound | A few names or sites differ | Each is one function with unit vectors written by Python, and D5 and D6 compare every name the document holds |
| File names that are not UTF-8 (Python's surrogate escapes) | A path in the document differs | Paths are handled as bytes and written as Python writes a surrogate-escaped `str` (`\udcXX` in the JSON); a case with such a file name |
| Memory of the port is not what the census promises (the records, not the edges, dominate on some packages) | A scale target missed | Stage 7 measures each package's peak and its largest tables (`table_sizes`), back to back with the oracle; the target is per package (section 6) |
| A dependency changes under us (ruff's crates are internal and weekly) | A build or parity break on update | Exact pins and `Cargo.lock`; an update is a pull request that must pass parity |
| On Windows, Python's ntpath goes beyond its lexical rules: `abspath` is `GetFullPathNameW` (it drops trailing dots and spaces, maps device names such as `NUL`, resolves `C:x` against that drive's own directory), `normcase` lowers with `LCMapStringEx` rather than `str.lower` | On Windows, another root or module name than Python's for such a path | The Rust side takes ntpath's lexical fallback (`normpath(join(cwd, path))`) and `str.lower`; parity is measured on Linux, where these paths do not occur. Paths on two drives, where `relpath` and `commonpath` raise `ValueError`, end `pycg` with Python's message and status 1 |
| Several agents in parallel conflict | Merge conflicts, two owners of one table | One owner per Rust module per stage (section 4); the crates follow the stages |

# 6. Timing and memory targets

The baseline is `make eval-scale` of `main` at `02bf447` in this sandbox:
4 CPUs, 16 GB, no swap, the container of `make eval` (Python 3.14.10,
`PYTHONHASHSEED=0`, no network), the runner's timeout of 1,800 s.
`SCALE_MEMORY_MIB` was raised from its default of 4,096 to 12,288, and to
14,848 for the packages measured alone, so that the peak is measured rather
than cut at the default. Seconds are the analysis time of the record
(`seconds`), MiB its peak resident set (`peak_rss_mib`). "Shared" packages
ran two or three at a time, each on its own CPU, so their times carry some
contention; the others ran alone. Stage 7 measures the oracle again, back
to back with the Rust program, as `make eval-scale BASE=...` does, and
gates on those numbers, not on these.

**The targets.** For every package of the scale set, the Rust program
gives the oracle's document (stage 7), and:

1. its analysis time is at most a quarter of the oracle's: the earlier
   study measured 4.0 times on hypothesis and 8.1 times on sphinx for the
   solver core alone, and a quarter is the lower of the two; the builder
   and the rules lose the same interpreter overhead per node and object;
2. its peak is at most a quarter of the oracle's: the census measured
   about ten times less for the copy edges of scikit-learn (750 MB as
   Python dicts against 70 MB as `u32` lists); a quarter leaves room for
   the records that the census did not count;
3. it finishes in the default container of `make eval-scale` (4,096 MiB)
   and within the runner's timeout. With target 2 this already holds for
   every package that the oracle finishes; it is stated for the two that
   the oracle does not finish here.

| Package | Files | Oracle outcome | Oracle seconds | Oracle MiB | Run | Rust seconds at most | Rust MiB at most |
|---|---|---|---|---|---|---|---|
| pydantic | 105 | finished | 73.2 | 1,198 | alone | 18.3 | 300 |
| numpy | 407 | timeout at 3,600 s (the timeout raised from 1,800) | more than 3,600 | 6,130 at the timeout | alone | 450 (a quarter of the runner's timeout) | 4,096 (target 3) |
| pandas | 1,440 | finished | 353.9 | 14,137 | alone | 88.5 | 3,534 |
| fsspec | 58 | finished | 34.1 | 408 | shared | 8.5 | 102 |
| rich | 100 | finished | 88.1 | 928 | shared | 22.0 | 232 |
| pip | 406 | finished | 323.5 | 3,521 | shared | 80.9 | 880 |
| sqlalchemy | 258 | finished | 438.0 | 11,419 | alone | 109.5 | 2,855 |
| pyparsing | 17 | finished | 26.8 | 439 | shared | 6.7 | 110 |
| scipy | 988 | finished | 350.4 | 5,845 | shared | 87.6 | 1,461 |
| openai | 2,057 | finished | 434.9 | 10,933 | shared | 108.7 | 2,733 |
| dask | 357 | finished | 120.6 | 3,141 | shared | 30.2 | 785 |
| matplotlib | 290 | finished | 87.9 | 2,033 | shared | 22.0 | 508 |
| scikit-learn | 619 | finished | 975.9 | 12,290 | alone | 244.0 | 3,072 |
| sphinx | 227 | finished | 33.0 | 763 | shared | 8.3 | 191 |
| sympy | 1,530 | killed by the cap at 14,848 MiB | – | more than 14,848 | alone | 450 (a quarter of the runner's timeout) | 4,096 (target 3) |
| xarray | 193 | finished | 238.5 | 3,885 | shared | 59.6 | 971 |
| cerberus | 48 | finished | 107.8 | 994 | shared | 27.0 | 249 |
| python-future | 229 | finished | 599.4 | 4,288 | shared | 149.9 | 1,072 |
| graphene | 118 | finished | 9.2 | 386 | shared | 2.3 | 96 |
| elasticsearch-dsl-py | 20 | finished | 47.1 | 796 | shared | 11.8 | 199 |

Eight packages need more than the default 4,096 MiB on the oracle (numpy,
pandas, sqlalchemy, scipy, openai, scikit-learn, sympy, python-future);
under the targets, none does on the Rust program.

For numpy and sympy the oracle gives no time to take a quarter of, so
their targets are those of target 3, with the time a quarter of the
runner's timeout.

What this measurement found, for `main` rather than for the port, and
reported here as `AGENTS.md` asks:

- numpy does not finish in an hour (6,130 MiB at the timeout), and sympy
  does not finish within 14.5 GiB. `docs/rust/scale-baseline.md` measures
  the oracle again on a 16 GB machine with a cap of 12,288 MiB, with the
  graph and D6 SHA-256 of every package that finishes: numpy finishes
  there in 618.6 s at 1,987 MiB, and sympy is killed by the cap.
- Eight packages exceed the default 4,096 MiB of `make eval-scale`, so with
  its defaults the scale set reports them as `killed by the cap`.
