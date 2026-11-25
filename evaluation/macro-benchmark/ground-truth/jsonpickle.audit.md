# jsonpickle: independent audit of the ground truth

Release v4.1.4, commit `6d5968c37735bb9365d354952de1f63d67670b13`, batch 6.
Audited files: `jsonpickle.ledger` (1028 entries),
`jsonpickle.json` (850 edges: 382 in the package, 468 outside),
`jsonpickle.added.json` (113 edges), `jsonpickle.rejected.json` (39 edges)
and `jsonpickle.md` (judgements J1 to J15), as they were on 2026-11-22.
`check.py jsonpickle` reports no errors. The trace is the run with 9 failing
numpy and pandas tests; the lead records it again with 9 tests deselected,
and no finding below depends on those 9 tests.

I read the package source, `docs/`, `README.rst`, `CHANGES.rst`, the
tests and the pinned pandas sources as data. I did not run or import the
package, and I ran no analysis, call-graph or type tool. The tools of the
benchmark (`check.py --skeleton`, `--report`) were the only commands run on
it.

**Result.** 184 sites re-derived blind; 4 disagreements (2 auditor errors,
2 sites of one scope question). 5 findings: F1 to F5. If all are applied,
the graph has 849 edges (-1) and the rejected file keeps 39 edges (one
leaves, one enters). Opinions on J4, J7 and J9 are in "Judgement calls".

## Findings

| Id | Severity | Kind | Edges | Evidence |
|---|---|---|---|---|
| F1 | medium, needs a ruling of the lead | writer missed edges (scope reading) | +2: `JSONBackend.backend_encode -> os.path.split` (traced as `posixpath.split`, now rejected: it leaves `rejected.json`), `JSONBackend.backend_decode -> os.path.join` (added) | The tests load `os.path` as a backend by name: `load_backend('os.path', 'split', 'join', AttributeError)` (`tests/jsonpickle_test.py:986`, `997`). The package itself imports the module (`backend.py:165`, `172`) and selects the functions with `getattr` (`:133`). The client passes names, not values. B2: "A string of the client that selects a method of an outside object that the package made names the methods that the package, its tests and its documented examples pass" (aiocache, `memory.py:92`). The tests pass `split` for `dumps` and `join` for `loads`. The ledger already applies this reading to a string that the client hands to `eval`: J10 keeps `loadrepr -> datetime.datetime.now` because a documented example passes that string. J3 rejects the tested backend with the sentence "an outside value that the client passes is a client callback", but no outside value is passed here, only its name. J3 also says that "no edge of this ledger depends on" the open question; this edge does. |
| F2 | medium | writer edges that the rules exclude | -4 (all added): `NumpyNDArrayHandlerBinary.flatten -> bz2.compress`, `.restore -> bz2.decompress`, `PandasProcessor.flatten_pandas -> bz2.compress`, `.restore_pandas -> bz2.decompress` | `compression` is a constructor argument with the default `zlib` (`ext/numpy.py:132`, `255`, `357`; `ext/pandas.py:63`). The docstrings list `{zlib, bz2, None}` (`ext/numpy.py:138-140`, `ext/pandas.py:69-71`), but no package code and no test passes `bz2`. B2: "A value from outside the package that the client passes is a client callback, whatever the documentation shows (`dict_cls=collections.OrderedDict`)". So `bz2` is a client object, and B5 makes the method calls on it opaque. `zlib.compress` and `zlib.decompress` stay: zlib is the package's default. The ledger lines are `ext/numpy.py:185:48`, `211:50` and `ext/pandas.py:79:48`, `97:50`. |
| F3 | medium (J9) | writer edges that the rules exclude | -1 added (`Unpickler._restore_reduce -> <builtin>.dict.update`); -1 traced, which moves to `rejected.json` (`Pickler._flatten_newstyle_with_slots -> <builtin>.type.mro`) | B5: "A method call on a client-supplied object, or on one of its attributes, has no outside callee", and "an object that a client callback returns" stays a client object. The cachetools audit (C2, `obj.__dict__.setdefault`) applied this to the `__dict__` of a client instance: "An attribute of a client object is as opaque as the object". `stage1` at `unpickler.py:594`, `605` is what the client's reconstructor `f(*args)` returns (`:583`). `obj` at `pickler.py:551` is a client object with `__slots__` and no `__dict__`; I found no value of a class that the package fixes that has both. A client class can override `__class__` and `__dict__`. The other 3 edges of J9 stay, on other grounds: see "J9" below. The notes at `pickler.py:305:62`, `551:41` and `unpickler.py:594:54`, `605:51` change; `594:54` loses its callee, but the edge `_restore_reduce -> dict.items` stays through `600:48` and `607:58`. |
| F4 | low | writer missed an edge (J6) | +1: `util.is_cython_function -> handlers.CloneFactory.__repr__` (`util.py:429:17`, `repr(obj)`) | The same reasoning as J6. A client encodes a defaultdict that `decode` restored with `include_properties=True`, a documented option (`pickler.py:126-131`). `_flatten_obj_instance` calls `_flatten_properties` (`pickler.py:604-605`). `inspect.getmembers(defaultdict)` lists `default_factory`, so `self._flatten(cloneFactory)` runs (`:537-541`). `_get_flattener` calls `util.is_module_function` (`:881`), which calls `is_cython_function` (`util.py:329`). A CloneFactory is callable and has `__repr__`, so `repr(obj)` calls `CloneFactory.__repr__` (`util.py:427-429`). The default rejection of `CloneFactory.__repr__` must name this site as an exception. |
| F5 | low | writer missed edges (J15) | +2: `Unpickler._restore_from_dict -> <builtin>.bool.__str__`, `Unpickler._restore_dict -> <builtin>.bool.__str__` | `isinstance(k, (int, float))` (`unpickler.py:715`, `929`, `954`) also admits a `bool`, and the ledger names `k.__str__()` by the class of the receiver (`<builtin>.int.__str__`). Bool keys arrive the same way as the int keys of J15: the yaml backend with `numeric_keys=True` keeps a `True` key (`pickler.py:492`, `797`), and `keys=True` restores one in a state dict (`unpickler.py:791-801`). |

Each finding is independent of the others. F1 and F3 depend on the
rulings below.

## Step 1: blind re-derivation

**Skeleton and sample.** Under `$TMPDIR/audit-jsonpickle/` I copied
`projects.toml` and `projects/jsonpickle` (a copy, not a link), and ran
`check.py --benchmark-dir <scratch> --skeleton jsonpickle`. It has 1046
sites: 1027 explicit (1026 call, 1 decorator) and 19 implicit (6 op, 13
format); 121 are value sites. Explicit sites dominate, so I drew by kind,
as the README's rulings for batch 6 say: the sites numbered in (line,
column) order module by module, `rng = random.Random(20261122)`,
`rng.sample(explicit, 51)`, and all 19 implicit sites (fewer than the 20 of
the tinytag split exist). I added every value site: 121, of which 7 were in
the explicit draw. That gives 184 sites. I read the whole package and
wrote my callees for each site
(`$TMPDIR/audit-jsonpickle/blind-answers.md`) before I opened any
file of the writer or the trace.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Random explicit (not value sites) | 44 | 44 | 0 |
| All implicit | 19 | 18 | 1 |
| Value sites | 121 | 118 | 3 |
| **Total** | **184** | **180** | **4 (2.2 %)** |

The 4 disagreements:

- **Writer missed an edge, if the lead rules as F1 proposes (2 sites of one
  question):** `backend.py:232:36` (I add `os.path.split`) and `238:36` (I
  add `os.path.join`).
- **I was wrong (2):** `handlers.py:245:58` `{self.exemplar}` and
  `pickler.py:447:32` `flatten_func(obj)`. I missed `CloneFactory.__repr__`
  at both. The exemplar of a restored CloneFactory can be a restored
  defaultdict whose own default_factory is a CloneFactory (a nested
  defaultdict of the package's output), and `repr()` of a restored
  defaultdict calls its CloneFactory's `__repr__`. The writer is right
  (J6).
- **Naming only (0).**

Two sites agreed with a condition that I wrote down blind. The first is
`handler(self)` at `pickler.py:597:29` and `unpickler.py:895:31`: the two
numpy `__init__` are callees only under J4's reading, which the ledger
takes. The second is `vars(subtype).get(name)` at `util.py:96:37`
(`types.MappingProxyType.get`), a J9-type site. It stays under my reading
of J9, because the MRO of a client class ends with builtin classes
(`object`).

## Step 2: exhaustive checks

**Dispatch sets.** I checked each of them against the class hierarchy and
the registrations:

- The handler dispatch (`pickler.py:597:43`, `unpickler.py:895:45`): the
  21 own `flatten` and the 22 own `restore` of the package's handler
  classes. NumpyDatetimeHandler inherits `NumpyGenericHandler.flatten`;
  PandasPeriodIndexHandler and PandasMultiIndexHandler inherit from
  PandasIndexHandler. The set is complete under J4. `handler(self)`:
  `BaseHandler.__init__` and `__call__`, and the `__init__` of
  `NumpyNDArrayHandlerBinary` and `NumpyNDArrayHandlerView`. Each binds
  the context as its first argument.
- The `super()` sites of the numpy handlers (`ext/numpy.py:82:60`,
  `159:35`, `202:34`, `268:25`, `276:35`, `304:63`, `321:35`, `330:34`):
  each has the one callee that the MRO gives. `82:60` reaches
  `BaseHandler.flatten`, which raises.
- `flatten_func` (`pickler.py:447`): `repr` and the 7 flatteners of
  `_get_flattener`. `restore(obj)` (`unpickler.py:430`): `_passthrough`
  and the 15 `_restore_` methods. `restore_key` (`:721`), `method`
  (`:420`), `_bytes_encoder` (`pickler.py:403`), the three local `flatten`
  (`:512`, `819`, `824`, `829`), `name_bundler` (`ext/pandas.py:346`) and
  `index_constructor` (`:360`): all complete.
- J5, the numpy scalar classes (`ext/numpy.py:58:45`): the 20 classes that
  `str(dtype)` of a numpy scalar can name. `datetime64` scalars get
  NumpyDatetimeHandler, because the registry looks up an exact entry
  first (`handlers.py:38`, `ext/numpy.py:378`).
- The proxies (`unpickler.py:201`, `206`, `884`): `_Proxy.get` and
  `_IDProxy.get`. An `_IDProxy` comes from a forward `py/id`, for example
  in `v1_decode` mode, where dicts get no reference (`:917-918`).
- The backends (`backend.py:232`, `238`): see F1.

**Default rejections (6 lines, 49 candidates).** I read every explicit
site that each default decides (`check.py --report jsonpickle`). The
`flatten` and `restore` defaults: at every listed site the receiver is the
Pickler or Unpickler that the handler holds as its context, or a local
bound method. The `get` defaults: every receiver is a dict or a
mappingproxy. The `CloneFactory.__repr__` default: correct except at
`util.py:429:17` (F4). `yaml.register` and `util.items`: correct.

**Functions that no site calls.** `enable_fallthrough`, `compat.iterator`,
`has_tag_dict`, `pd_encode`, `pd_decode` and the deprecated `util.is_*`
keep their bodies' edges (rule A). Each has the edges that I derive.

**Special methods and properties.** The package defines no property, no
`__getattr__`, `__getitem__` or `__hash__`. Its special methods are the
`__init__` methods, `BaseHandler.__call__`, `CloneFactory.__call__` and
`__repr__`, and `ClassNotFoundError.__init__(*args, **kwargs)`, which binds
any call. I found no other implicit site with a package callee.

**Binding check.** I checked every call whose callee is a package function
against the callee's signature. None fails to bind. The two numpy
`__init__` at the handler dispatch bind the context to `size_threshold`
or `mode`; the `flatten` after them raises inside the body. That still
counts.

**Notes and rejections.** I read all 207 notes and 81 rejection lines.
Apart from the lines that F2 and F3 change, they agree with the source. Two
counts in `jsonpickle.md` are too high:

- J6 says that 4 edges rest on it. `_restore_object_instance ->
  object.__new__` does not. The explicit `object.__new__(cls)` at
  `unpickler.py:859` runs whenever `is_oldstyle` is true. For a class
  that is not a type it raises inside the builtin, and the edge still
  counts. So 3 edges rest on J6.
- J9 says that 5 edges rest on it. 3 of them do not (see "J9").

**Callees outside the package.** I checked the names against the
micro-benchmark rules, and the pandas names against the pinned pandas
3.0.6 sources (read only):

- `pandas.Index` has no `__slots__` in its MRO (`core/indexes/base.py`,
  `core/base.py`, `core/accessor.py`, `core/arraylike.py`).
- `ExtensionDtype` and its subclasses have the metaclass `type`
  (`core/dtypes/base.py:46`, `110`), so `type.__subclasses__` is right.
- The lock names (J8) follow "Retain an older fallback name". On 3.13 and
  later, `threading.Lock` is the lock class. On 3.8 to 3.12, the class
  is `_thread.LockType`.
- The ledger names `numpy.dtype.newbyteorder` and `numpy.generic.tolist`
  through the documented type. In numpy 2, the receivers are subclasses of
  `numpy.dtypes` and the concrete scalar classes. No rule asks for one
  name per subclass when the concrete class is not known, so I make no
  finding.

**Rejected trace edges (39).** I agree with 38 of them. The test objects
that `encode` gets are client values (B2, B5): exceptions, `OrderedDict`,
`deque`, `Counter`, `Decimal`, `timedelta`, time zones, enum members,
str and tuple subclasses, struct sequences. So are the classes and
reconstructors that their payloads name. The Cython
`Timestamp.isoformat` is a naming artefact. The exception is
`backend_encode -> posixpath.split` (F1). F3 adds one rejection:
`_flatten_newstyle_with_slots -> <builtin>.type.mro`, the class of a test
object.

## Judgement calls

The lead asked for an opinion on J4, J7 and J9.

- **J4 (the handler role; 11 edges).** Supported by B2. `handlers.py:2-4`
  says that "each custom handler must derive from
  `jsonpickle.handlers.BaseHandler`", and `register` documents `handler`
  as "the custom handler class" (`:50-51`). The documentation names a
  base class that the package implements for the role. B2 admits a
  package value when "the parameter's annotation names its type or a base
  class that the package implements for that purpose", and for an
  annotation a base class admits its subclasses (`Type[Sentinel]` admits
  any sentinel class). Where no annotation exists, the README already
  lets documentation take the place of an annotation (B4: itables,
  dagster-pipes). Reading a documented base class in the same way is the
  smaller extension. BaseHandler itself is a plain public class (B1). The
  aiocache limit, "a check on another parameter does not decide a role",
  is about an `issubclass` check, not about documentation. So it does not
  apply. All 11 edges stay. The README does not state this case in
  words; if the lead wants a rule, I propose this one: "a base class that
  the documentation names for a role admits its package subclasses, as an
  annotation does".
- **J7 (`bytes(x)` for typecode `'c'`; 1 edge).** The README does not
  decide it directly. The nearest rules support the edge. `decode`
  documents old output as input: `v1_decode` (`unpickler.py:64-67`), and
  "Any objects encoded with versions prior to 2.2.0 should still decode
  properly" (`CHANGES.rst`, v2.2.0). ArrayHandler dates from v1.4
  (`CHANGES.rst`), when jsonpickle still ran on Python 2.7. Python 2.7
  support ended with v3.0.0 ("Drop support for CPython<3.7"). So releases
  of this package did write arrays with typecode `'c'`. The branch runs
  on a supported interpreter, because the decoding Python is 3.x. This
  is not the netaddr case, where only an unsupported interpreter takes
  the branch. Under B2, the documentation names old output for the
  role. B3 excludes only "a value that the package never produces", and
  the smaller extension reads "the package" as including the earlier
  releases whose output this release documents that it decodes. The
  builtin enters its body before it raises `TypeError` ("Concrete
  types"). The edge stays. `TextIOHandler.restore` at the dispatch
  (J4) rests on a similar payload, written under another registration.
- **J9 (`__dict__` and `__class__`; 5 edges).** Not supported as a rule.
  B5 decides the client-object cases: "a method call on a client-supplied
  object, or on one of its attributes, has no outside callee". The
  cachetools audit (C2) already applied this to `obj.__dict__` of a
  client instance. A ruling that the interpreter's `__dict__` is not a
  client attribute would contradict that earlier ruling. The README's
  rulings for batch 6 do not let the lead adopt such a ruling. The
  5 edges, one by one:
  - `_sort_attrs -> types.MappingProxyType.items` stays on another
    ground. `DatetimeHandler.flatten` passes the class of a datetime,
    date or time to `Pickler.flatten` (`handlers.py:184`). With a
    backend that sorts keys (documented at `pickler.py:91-92`),
    `_sort_attrs` calls `.items()` on that class's mappingproxy. The C
    classes have no `__slots__`, and the handler fixes the class.
  - `_sort_attrs -> <builtin>.dict.items` stays on another ground.
    `PandasSeriesHandler.flatten` passes `obj.index`, a pandas Index
    with an instance `__dict__` (`ext/pandas.py:326`).
  - `all_subclasses -> type.__subclasses__` stays. The receivers are
    pandas classes that the package itself enumerates
    (`tags_pd.py:202`), not client objects.
  - `_restore_reduce -> dict.update` and `_flatten_newstyle_with_slots
    -> type.mro` go (F3).

  The other judgements (J1 to J3, J5, J6, J8, J10 to J15) follow the
  nearest rules, except as F1, F2, F4 and F5 say.

## Cases for the lead

1. F1: whether the aiocache clause on client strings covers a backend
   module and functions that the tests select by name (2 edges). I
   recommend yes, for consistency with J10.
2. F3 and J9: confirm that B5 and cachetools C2 decide the `__dict__` and
   `__class__` of client objects (2 edges).
3. J4 and J7: I support the writer. If the lead wants rules for them, the
   wording is above (J4: 11 edges; J7: 1 edge). Neither decides many
   edges, so a referee is not needed.

## README and tools

- The tools worked as documented. The skeleton of the scratch copy was
  made without the ledger. `--report` listed every default-decided
  explicit site.
- The README's split for batch 6 ("50 explicit and 20 implicit
  sites") assumes at least 20 implicit sites. jsonpickle has 19, so I took
  all 19 and 51 explicit sites. A sentence for that case would help.
- The opacity of a client object's `__dict__` and `__class__` is stated
  only through B5's "one of its attributes" and in an audit file
  (cachetools C2). One sentence in B5 would prevent J9-type questions.
