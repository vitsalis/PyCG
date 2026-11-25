# jsonpickle: judgements of the ground truth

Release v4.1.4 (commit `6d5968c`), batch 6. Analysed source:
`jsonpickle/` (root `.`): 16 modules, 235 functions (4 lambdas), 35
classes. `pyproject.toml:19` sets `requires-python = ">=3.8"`; the
classifiers name Python 3 only and no other implementation, so the
supported versions are CPython 3.8 and later (the final classifier is not an
upper bound). `-O` and `-OO` change no edge: the one `assert`
(`ext/numpy.py:337`) calls nothing, and no code reads `__doc__`.

The ledger is `jsonpickle.ledger`; `jsonpickle.json` and
`jsonpickle.added.json` are generated from it. 34 trace edges are rejected
in `jsonpickle.rejected.json` (see "Rejected trace edges"). The blind
audit (`jsonpickle.audit.md`) led to the findings F1 to F5, which the lead
adopted and this ledger applies (850 to 849 edges); J4 and J7 stand. No tool output
was read. The trace (`dynamic/jsonpickle.json`) is the second recording,
with the 9 numpy and pandas tests that failed in the first one deselected
(379 passed, 19 skipped, 9 deselected; 755 edges). Step 4 was done again
against it: no edge was added or removed. 20 edges that only the deselected
tests ran are now edges from reading (737 to 717 confirmed by the trace),
and `restore_v3_3` and `make_read_csv_params` no longer run.

## Architecture, as the ledger uses it

- `encode` (`pickler.py:19`) makes a `Pickler` (or takes the client's
  `context`) and hands `Pickler.flatten` of the value to the backend.
  `Pickler._flatten_obj` dispatches through `flatten_func`, which
  `_get_flattener` chooses (`pickler.py:862-892`).
  `_flatten_obj_instance` looks a handler up in the registry and calls
  `handler(self).flatten(obj, data)` (`pickler.py:597`); otherwise it uses
  the pickle protocol of the object (`__reduce__`, `__reduce_ex__`,
  `__getnewargs__`, `__getstate__`) or its `__dict__` and slots.
- `decode` (`unpickler.py:15`) decodes the string with the backend and
  calls `Unpickler.restore`. `Unpickler._restore` dispatches through
  `restore`, which `_restore_tags` chooses by the tag of the JSON object
  (`unpickler.py:971-1012`). `_restore_object` loads the class named by
  `py/object` and calls `handler(self).restore(obj)` (`unpickler.py:895`)
  or builds the instance with `cls.__new__`.
- `JSONBackend` (`backend.py`) holds the dumps and loads functions of the
  loaded backend modules; `jsonpickle.backend.json` is the default one.
- `handlers.Registry` maps classes and class names to handler classes or
  handler instances. `handlers.get`, `handlers.register` and
  `handlers.unregister` are the bound methods of the module's registry
  (`handlers.py:85-88`).
- The extensions register their handlers when the client calls their
  `register_handlers` (documented in `docs/extensions.rst`).
- The package defines no property, no `__getattr__` and no `__getitem__`;
  its only special methods are `__init__`, `__call__` and
  `CloneFactory.__repr__`. So almost all sites are explicit calls.

## Scope rules

The rules A, B1 to B5 and C of `macro-benchmark/README.md` apply. This
section shows how the ledger applies them.

**A.** Every function keeps the edges of its body. `pd_encode`,
`pd_decode`, `compat.iterator`, `has_tag_dict`, the deprecated `util.is_*`
functions and `enable_fallthrough` have no package caller and keep their
edges.

**B1, receivers.** `self` is an instance of the class or of a package
subclass that inherits the method. The numpy handlers call `super()` along
fixed MROs (`NumpyNDArrayHandlerView` -> `NumpyNDArrayHandlerBinary` ->
`NumpyNDArrayHandler` -> `NumpyBaseHandler` -> `BaseHandler`); each
`super().flatten` and `super().restore` site has the one callee that the MRO
gives. `self.context` of a handler is the Pickler (in `flatten`) or the
Unpickler (in `restore`) that `BaseHandler.__init__` or `__call__` stores
(documented: "reference to pickler/unpickler").

**B2 and B5, the value being pickled.** `encode` accepts any object, so the
value and everything in it are client objects, and their pickle protocol
methods are client code. This holds for the standard-library objects that
the tests encode too (`OrderedDict`, `deque`, `Decimal`, `timedelta`,
time zones, enum members, exceptions): their calls are rejected trace
edges. The exceptions are the objects of the classes that a package handler
is registered for: the handler fixes the class (as an `isinstance` check
does), so `DatetimeHandler.flatten` calls `datetime.datetime.isoformat`
and `__reduce__`, `LockHandler.flatten` calls the lock's `locked`, and the
numpy and pandas handlers call the methods of `numpy.ndarray`,
`numpy.generic`, `numpy.dtype`, `pandas.DataFrame`, `pandas.Series`,
`pandas.Index` and `pandas.Timestamp`.

**B2 and B5, the data being decoded.** The JSON names classes and
functions. A class that the decoded data names is a client value when the
client's own object wrote it, so `cls.__new__`, `cls(*args)`,
`instance.__setstate__`, `instance.append` and the reduce callable
`f(*args)` have no callee for it. They have callees where the package's own
output names the class: `jsonpickle.handlers.CloneFactory` (judgement J6),
and the library values that the package's handlers forward to the generic
pickler (complex, timedelta, Timedelta, NaT, NA and, after a public
`unregister`, more numpy and pandas values: judgement J11, the Codex audit
rounds and "Open receiver sets").

**B3.** No package object other than a `CloneFactory` reaches the
pickler: a client that encodes a Pickler, a handler or a JSONBackend is not
considered.

**C.** Public: `jsonpickle.encode`, `decode`, `JSONBackend`, `Pickler`,
`Unpickler`, `register`, `unregister` and the backend functions of
`jsonpickle/__init__.py`; the modules `jsonpickle.pickler`,
`unpickler`, `handlers`, `util`, `backend`, `tags`, `tags_pd`, `ext.*`
and all their public classes and functions (the API documentation lists the
modules with `:members: :undoc-members:`). Private: the names with a
leading underscore (`_Proxy`, `_IDProxy`, `_trivialclassic`, `_loadmodule`,
`_passthrough`, the `_` methods).

## Judgement calls

1. **Optional imports and version branches.** `ext/gmpy.py:1-4`: both
   sides run; with gmpy2 the handler is registered (`gmpy2.mpz`, a missing
   module). `version.py:1-4`: `importlib.metadata` exists on 3.8 and
   later, so the `metadata = None` side does not run (it has no call).
   `tags_pd.py:160` (`except AttributeError`, numpy before 1.25): the
   fallback has no call. `ext/numpy.py:183` (`obj.tostring`, numpy before
   1.9): every numpy that runs on Python 3.8 has `tobytes`, so the branch
   does not run and the site has no callee. `ext/numpy.py:26`
   (`dtype.tostring()`): `numpy.dtype` has no `tostring`, so the
   `hasattr` test is false for the package's values; no callee.
2. **Missing modules.** ujson, PyYAML and gmpy2 are in the `testing` extra
   but are not installed in the test environment. Their calls are named as
   missing modules: `ujson.dumps`, `ujson.loads`, `yaml.dump`,
   `yaml.safe_load` (`backend.py:232`, `238`), `gmpy2.mpz`
   (`ext/gmpy.py:17`, imported as `gmpy`).
3. **The backends** (`backend.py:232`, `238`). The callees are the dumps and
   loads functions of the modules that the package itself loads:
   simplejson, json, ujson and yaml (`backend.py:95-103`, and
   `jsonpickle.ext.yaml.register`), and the functions of a module that the
   tests load by name: `load_backend('os.path', 'split', 'join', ...)`
   (`jsonpickle_test.py:986`, `997`) gives `os.path.split` and
   `os.path.join`. The client passes names, not values; the package imports
   the module and selects the functions (`backend.py:133`, `165`, `172`), so
   the B2 rule on a client string that selects a method of an outside object
   names what the tests pass (audit F1, adopted by the lead; the draft
   rejected the traced `posixpath.split`). The documented example `load_backend('django.util.simplejson', ...)`
   (`docs/api.rst:45`) names a module that no Django release has (Django
   had `django.utils.simplejson`), so its import fails and nothing is stored.
   The "experimental backends" of `docs/api.rst:55-58` are named without
   the names of their functions; a client loads them, as a client value.
4. **The handler role** (`pickler.py:597`, `unpickler.py:895`). The
   registry holds what the package and the client register. The module
   docstring says that "each custom handler must derive from
   BaseHandler", and `register` documents its `handler` argument as "the
   custom handler class": the documentation names BaseHandler as the base
   class of the role, so every package subclass of BaseHandler is a package
   value for it (B2), and BaseHandler itself is a plain public class (B1).
   The callees of `handler(self).flatten` and `.restore` are therefore the
   `flatten` and `restore` of all package handler classes, also
   `BaseHandler`, `NumpyNDArrayHandler` and `NumpyNDArrayHandlerBinary`,
   which the package itself registers only through subclasses, and
   `TextIOHandler.restore`, which only data written under another
   registration reaches. `handler(self)` instantiates a handler class
   (`BaseHandler.__init__`, or the own `__init__` of
   `NumpyNDArrayHandlerBinary` and `NumpyNDArrayHandlerView`, which bind
   the context as their first argument) or calls a handler instance
   (`BaseHandler.__call__`; `jsonpickle.ext.numpy.register_handlers`
   registers a `NumpyNDArrayHandlerView` instance). Client handlers are
   client code. A narrower reading (only the handlers that the package
   registers, and the documented example of judgement 12) would remove 11
   edges, all added: under `_flatten_obj_instance` the `flatten` of
   `BaseHandler`, `NumpyNDArrayHandler` and `NumpyNDArrayHandlerBinary`
   and the two numpy `__init__`; under `_restore_object` the same three
   `restore`, the two `__init__` and `TextIOHandler.restore`. The lead may
   rule.
5. **numpy scalar types** (`ext/numpy.py:58:45`,
   `self.restore_dtype(data).type(value)`). The dtype is rebuilt from the
   dtype string that `NumpyGenericHandler.flatten` wrote for a numpy scalar;
   its `type` is the scalar class, which the call instantiates. The callees
   are the classes that a dtype string can name: `numpy.bool_`, the eight
   integer classes, `float16`, `float32`, `float64`, `longdouble`,
   `complex64`, `complex128`, `clongdouble`, `str_`, `bytes_`, `void` and
   `timedelta64` (`datetime64` has its own handler, `NumpyDatetimeHandler`,
   whose two sites call `numpy.datetime64`). `longdouble` and
   `clongdouble` are named on the platforms where they are wider than
   float64 (a platform branch runs if a supported platform takes it). The
   trace has five of them (float64, int64, int32, complex128, str_).
6. **The CloneFactory round trip.** For a `defaultdict` whose
   `default_factory` is a callable that is not a type, the pickler calls the
   factory and flattens `CloneFactory(factory())` (`pickler.py:844`), so its
   output names `jsonpickle.handlers.CloneFactory`. `decode` of that output
   makes a CloneFactory with `cls.__new__(cls)` (`object.__new__`,
   `unpickler.py:857`, which the trace has) and puts it into the restored
   defaultdict (`unpickler.py:854-855`). Encoding that decoded object again,
   a program of the public API, calls the CloneFactory at
   `pickler.py:844` (`factory()` -> `CloneFactory.__call__`, added), and
   `repr()` of that defaultdict, which `_flatten_obj` uses when `max_depth`
   is reached or a repeated object is met with `make_refs=False`
   (`pickler.py:439`, `447`), calls the CloneFactory's `__repr__` back
   (added). `CloneFactory.__repr__` formats `{self.exemplar}`
   (`handlers.py:245:58`); an exemplar that is itself a restored
   defaultdict with a CloneFactory (a nested defaultdict of the package's
   output) calls that `__repr__` (added, a self edge). With
   `include_properties=True` (documented at `pickler.py:126-131`),
   `_flatten_properties` flattens the restored defaultdict's
   `default_factory`, and `util.is_cython_function` calls `repr()` of the
   callable CloneFactory (`util.py:429`; added, audit F4). Everywhere else
   the default rejection of `CloneFactory.__repr__` holds. 3 edges rest on
   the round trip alone: `_flatten_dict_obj -> CloneFactory.__call__`,
   `_flatten_obj -> CloneFactory.__repr__` and `CloneFactory.__repr__ ->
   CloneFactory.__repr__` (the audit's count; `_restore_object_instance ->
   object.__new__` also has the explicit `object.__new__(cls)` of
   `unpickler.py:859`, and `is_cython_function -> CloneFactory.__repr__` is
   F4). Lead's ruling: stands.
7. **Python 2 arrays** (`handlers.py:155-156`). The typecode `'c'` exists
   only in the array module of Python 2. The branch restores arrays that
   jsonpickle wrote under Python 2; decoding the output of an older
   jsonpickle is a documented use (the `v1_decode` and `safe` options, the
   compatibility functions of `util.py:516-550`), so `bytes(x)` keeps its
   edge (the builtin body raises `TypeError` for a str, which still counts).
   B3 ("a value that the package never produces") reads "the package" as
   including the earlier releases whose output this release documents that
   it decodes (`CHANGES.rst`: ArrayHandler dates from v1.4, when jsonpickle
   ran on Python 2.7). Lead's ruling: stands (1 edge).
8. **The lock class** (`handlers.py:266`, `272`). The handler is registered
   for the class of `threading.Lock()` (`handlers.py:276-277`). From Python
   3.13 that class is `threading.Lock`; on 3.8 to 3.12 `threading.Lock` is a
   factory function and the class is `_thread.LockType`. The methods have
   both names, by the rule on older fallback names ("Versions and
   configuration"): `threading.Lock.locked` and `.acquire` (traced) and
   `_thread.LockType.locked` and `.acquire` (added).
9. **`__dict__` and the class of an object.** The draft read the
   interpreter's `__dict__` and `__class__` of any object as outside B5.
   Lead's ruling (after the audit, F3): that reading does not stand. B5
   ("a method call on a client-supplied object, or on one of its
   attributes, has no outside callee") and the cachetools audit (C2) decide
   that the `__dict__` and the class of a client object are opaque. So
   `obj.__class__.mro()` (`pickler.py:551`) and `stage1.__dict__.items()`
   and `.update` (`unpickler.py:594`, `605`) have no callee; the traced
   `_flatten_newstyle_with_slots -> type.mro` was rejected (it is an edge
   again since Codex audit round 3, on its own ground: dateutil's slotted
   `weekday`, a library object that the package reaches), and
   `_restore_reduce -> dict.update` goes (`_restore_reduce -> dict.items`
   stays through `unpickler.py:600` and `607`). Three edges stay on other
   grounds: at `pickler.py:305` (`obj.__dict__.items()` in `_sort_attrs`)
   the package itself hands two values to `Pickler.flatten` with a backend
   that sorts keys (documented at `pickler.py:91-92`): the class of a
   datetime, date or time (`DatetimeHandler.flatten`, `handlers.py:184`),
   whose `__dict__` is a mappingproxy (`types.MappingProxyType.items`), and
   the pandas Index of a Series (`PandasSeriesHandler.flatten`,
   `ext/pandas.py:326`), whose instance `__dict__` is a dict
   (`dict.items`). At `tags_pd.py:121` the receivers of `__subclasses__`
   are pandas classes that the package itself enumerates, not client
   objects (`type.__subclasses__`). 2 edges went with this ruling.
10. **`eval` in `loadrepr`** (`unpickler.py:332`). The calls of the
    evaluated string belong to `loadrepr`. The string is the client's (the
    `py/repr` entry of old jsonpickle output, decoded only with
    `safe=False`), so its calls are client values, except the documented
    example of the docstring, `loadrepr('datetime/datetime.datetime.now()')`
    (`unpickler.py:321`), which calls `datetime.datetime.now` (added; the
    tracer misses calls in evaluated code).
11. **Reduce values** (`unpickler.py:576`, `583`, `587`, `613-620`). The
    pickler writes `py/reduce` from the `__reduce__` or `__reduce_ex__` of
    the object: for a client object the restored reconstructor `f`, the
    class of `py/newobj` and the methods of the object `f` makes are client
    values, with no callee, and the tests' reconstructors and objects are
    rejected trace edges. The package's own objects have no reduce
    (`util.has_reduce` is false for a CloneFactory). The library values that
    the package itself hands to flatten are not client values (ruling (c)
    of batch 6; Codex audit round 1, G2): the numpy handlers forward
    the Python values of `tolist()` (`ext/numpy.py:53`, `102`), and a
    timedelta64 of a unit up to microseconds gives `datetime.timedelta`
    values, which no default handler takes. So `timedelta.__reduce__`
    (`pickler.py:610`) and the reconstructor `datetime.timedelta`
    (`unpickler.py:583`) are edges, and so are `complex.__getnewargs__`
    (`pickler.py:688`) and `complex.__new__` (`unpickler.py:857`) for the
    Python complex values of a complex array or scalar. These 4 edges were
    rejected trace edges before. The pandas handlers forward pandas scalars
    in the same way, without any unregistration: `Timedelta` (from a
    `TimedeltaIndex`, a timedelta64 column or an Interval of timedeltas),
    `NaT` (from a datetime-like index or column) and `NA` (from a nullable
    column). Their reducers and reconstructors, read in the pandas 3.0.6
    `.pyx` sources, are edges: `pandas.Timedelta.__reduce__` and
    `pandas.api.typing.NAType.__reduce__` (`pickler.py:610`),
    `pandas.api.typing.NaTType.__reduce_ex__` (`622`),
    `pandas._libs.tslibs.timedeltas._timedelta_unpickle` and
    `pandas._libs.tslibs.nattype._nat_unpickle` (`unpickler.py:583`), and
    `pandas.api.typing.NAType.__new__` (`unpickler.py:857`: `NA.__reduce__`
    returns the str `"NA"`, so the pickler writes the class). These 6 are
    Codex audit round 1, Unsure 2.
12. **UnpickleableNumpyGenericHandler** (`ext/numpy.py:72-85`). The
    docstring of `encode` (`pickler.py:51-53`) shows it registered for
    `numpy.generic` (with the spelling `UnpicklableNumpyGenericHandler`), a
    documented example, so it is a callee of the handler dispatch even under
    the narrower reading of judgement 4. Its `flatten` calls
    `super(NumpyGenericHandler, self).flatten`, which skips
    `NumpyGenericHandler` and `NumpyBaseHandler` (no `flatten`) and
    reaches `BaseHandler.flatten`, which raises `NotImplementedError`.
13. **DatetimeHandler bound to other types** (`handlers.py:175-178`). The
    module docstring says that "a handler can be bound to other types by
    calling jsonpickle.handlers.register". For a datetime, date or time the
    `hasattr` test is true; for an object of another class that a client
    binds to the handler it is false and `str(obj)` runs, so `<builtin>.str`
    stays (added). The object's own methods stay client code.
14. **Receiver classes of outside methods.** One rule decides the names:
    "A method of an outside object is named by the class of the receiver,
    also when that class inherits it" (README, "Callees outside the
    package"). The draft named `MultiIndex` and the other index classes
    through `pandas.Index.tolist` because they inherit the method; that
    named the defining class and is corrected (Codex audit round 1, G1).
    The receivers are the classes that the package fixes or makes: at
    `ext/pandas.py:348` (`PandasIndexHandler.flatten`) `Index`,
    `RangeIndex`, the explicitly registered `PeriodIndex` and `MultiIndex`,
    and the `DatetimeIndex`, `TimedeltaIndex`, `IntervalIndex` and
    `CategoricalIndex` that `pd.Index(..., dtype=dtype)` makes in `restore`
    (pandas `core/indexes/base.py:614-637`, the `index_class` of the
    extension dtypes) and that a client encodes again; at `145` and `155`
    (`PandasDfHandler.flatten`) `Index`, `RangeIndex` and the
    `DatetimeIndex`, `TimedeltaIndex`, `PeriodIndex` and `IntervalIndex`
    that pandas infers from decoded labels and index values in `restore`
    (lines 262, 285). At `ext/numpy.py:53` `NumpyDatetimeHandler` fixes the
    receiver `numpy.datetime64` exactly. The referee's ruling (e) after
    Codex audit round 1 applies the same rule to the open sets: the numpy
    scalar classes and the `numpy.dtypes` classes that can arrive at a site
    are named one by one (the ruling's sets S, R, E, F and G):
    `ext/numpy.py:53` and `80` (`.tolist`) and `ext/pandas.py:21`
    (`.item`) name the classes of S, and `numpy.generic.tolist` and
    `.item` went (`generic` has no instances); the six `newbyteorder`
    sites name the classes of G, F or R beside `numpy.dtype.newbyteorder`,
    which stays as the name of the numpy releases before 1.25. The C integer
    names follow the referee's C-integer ruling: aliases are resolved within
    each runtime and the names are unioned across the supported runtimes.
    numpy's naming header (`_core/src/multiarray/arraytypes.h.src:99-139`)
    gives a sized name to the first family of each size in the order long,
    long long, int; so `numpy.longlong`/`ulonglong` (`LongLongDType`,
    `ULongLongDType`) are distinct classes on LP64 Linux and macOS, and
    `numpy.intc`/`uintc` (`IntDType`, `UIntDType`) on Windows, which the
    release's Azure CI runs; these are named (28 pairs). `numpy.long`,
    `ulong`, `LongDType` and `ULongDType` are always second names of a sized
    class and are not added. The reconstruction sites (`153:47`, `343:60`)
    get no C-family name: `str(dtype)` and `np.dtype(...)` normalise them to
    the sized classes. A column `obj[col]` is a `pandas.Series`
    (`Series.apply`, `.any`, `.tolist`, `.astype`). `compression` of
    `PandasProcessor` and of the numpy binary handler is zlib by default:
    `zlib.compress` and `zlib.decompress`. The docstrings also name `bz2`,
    but no package code and no test passes it, and a module that a client
    passes is a client value (B2, B5; audit F2, adopted by the lead: the
    draft's four `bz2` edges went). `pandas.Timestamp.isoformat` is the
    Cython method that the tracer names `_cython_3_3_0.cython_function_
    or_method.__call__` (a naming artefact, rejected).
15. **Numeric keys** (`unpickler.py:716`, `930`, `955`). JSON object keys
    are strings, but the yaml backend decodes numeric keys, and with
    `keys=True` a restored state dict can have them; `k.__str__()` is then
    `<builtin>.int.__str__`, `<builtin>.float.__str__` or, for a `bool` key
    (the `isinstance` test admits it; `numeric_keys=True` keeps one,
    `pickler.py:492`, `797`), `<builtin>.bool.__str__` (all added; the bool
    edges are audit F5).

## Outside names checked in the pinned sources

The lead unpacked the pinned wheels of the test environment as plain
sources (numpy 2.5.4, pandas 3.0.6, simplejson, python-dateutil, six,
tzdata). I read these files only. I did not run or import them. These names
were checked there:

- numpy (`numpy/__init__.pyi`): `numpy.dtype` defines `newbyteorder` and
  `type` and has no `tostring` (judgement 1, `ext/numpy.py:26`);
  `ndarray` defines `tolist`, `tobytes`, `reshape` and `copy`;
  `generic` defines `item` and inherits `tolist`. The 20 scalar classes of
  judgement 5 are all public names of the stub, and `numpy.bool_` is the
  alias of `numpy.bool`.
- pandas: `tolist` is defined in `core/base.py:892` (`IndexOpsMixin`,
  which `Index` and `Series` inherit) and again in
  `core/indexes/range.py:578` (`RangeIndex`); `MultiIndex` and the other
  index classes inherit it. The ledger names it by the receiver's class
  (judgement J14). `Index.__new__` chooses the subclass from the dtype in
  `core/indexes/base.py:614-637`. `Series.apply` and `.any` are in `core/series.py`;
  `astype` is in `core/generic.py`; `DataFrame.set_index` is in
  `core/frame.py`; `MultiIndex.from_tuples` is in `core/indexes/multi.py`;
  `Timestamp.isoformat` is in `_libs/tslibs/timestamps.pyi`. `Index`,
  `RangeIndex`, `MultiIndex`, `PeriodIndex`, `Series`, `DataFrame`,
  `Timestamp`, `Period`, `Interval`, `to_timedelta` and `read_csv` are
  exported by `pandas/__init__.py`.

The lock names of judgement 8 and the standard-library names come from the
CPython documentation, not from these files.

## Default rejections

| Candidates | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| the `flatten` of the 21 handler classes | 17 to 19 each (397 pairs) | at every `.flatten(` site but the dispatch the receiver is the Pickler, or a `super()` object whose MRO gives one method | `pickler.py:597:43` (all 21), the `super()` sites `ext/numpy.py:82:60`, `159:35`, `276:35`, `304:63`, `321:35` (one each) |
| the `restore` of the 22 handler classes | 13 or 14 each (306 pairs) | the same for `.restore(` | `unpickler.py:895:45` (all 22), `ext/numpy.py:202:34`, `330:34` |
| `Registry.get`, `_Proxy.get`, `_IDProxy.get` | 43, 45, 45 | the other `.get(` receivers are dicts and a mappingproxy | `pickler.py:593`, `unpickler.py:891` (Registry.get); `unpickler.py:201:33`, `206:25`, `884:68` (the proxies) |
| `CloneFactory.__repr__` | 29 | no formatted value is or holds a CloneFactory | `pickler.py:447:32`, `handlers.py:245:58`, `util.py:429:17` (judgement 6) |
| `jsonpickle.ext.yaml.register` | 19 | every `register(...)` is the registry's bound method | nowhere |
| `jsonpickle.util.items` | 10 | `util.items` is called only by its qualified name | its 7 calls in `pickler.py` and `unpickler.py` |

The explicit sites that a default decides were each checked: the receiver of
`self.context.flatten`, `flatten(...)` (the bound `pickler.flatten` or
a local bound method) and `context.flatten` is never a handler.

## Value sites

121 value sites. Most are value sites by name only: the package assigns
attributes or module names `warn` (`pickler.py:251`), `get`
(`handlers.py:88`), `register`, `load_backend`, `remove_backend`,
`dumps`, `loads` and `dtype`, so `warnings.warn(...)`, `data.get(...)`
and `np.dtype(...)` are value sites; each has a note and its plain callee.
The real dispatch sites:

| Site | Callees |
|---|---|
| `backend.py:232:36` `self._encoders[name](...)` | `simplejson.dumps`, `json.dumps`, `ujson.dumps`, `yaml.dump`, `os.path.split` (J3) |
| `backend.py:238:36` `self._decoders[name](...)` | `simplejson.loads`, `json.loads`, `ujson.loads`, `yaml.safe_load`, `os.path.join` (J3) |
| `pickler.py:403:53` `self._bytes_encoder(obj)` | `util.b85encode`, `util.b64encode` |
| `pickler.py:447:32` `flatten_func(obj)` | `repr`, `_list_recurse`, `_flatten_dict_obj`, `_getref`, the tuple/set lambda, `_flatten_function`, `_ref_obj_instance`, `_mktyperef`, `CloneFactory.__repr__` (J6) |
| `pickler.py:455:38` `self.fail_safe(e)` | none: a client callback |
| `pickler.py:512`, `819`, `824`, `829` `flatten(k, v, data)` | the local bound key-value method |
| `pickler.py:597:29` `handler(self)` | `BaseHandler.__init__`, `BaseHandler.__call__`, the two numpy `__init__` (J4) |
| `pickler.py:811:33` `obj.__class__()` | `dict` (only an exact dict gets no `data`) |
| `pickler.py:844:85` `factory()` | `CloneFactory.__call__` (J6) |
| `unpickler.py:420:19` `method(obj, attr, proxy)` | `_obj_setattr`, `_obj_setvalue` |
| `unpickler.py:430:23` `restore(obj)` | `_passthrough` and the fifteen `_restore_` methods of the tags |
| `unpickler.py:583:23` `f(*args)` | the 26 reconstructors of the library values that the package forwards (J11, "Open receiver sets"); a client reconstructor otherwise |
| `unpickler.py:672:28` `self.on_missing(class_name)` | none: a client callback |
| `unpickler.py:721:32` `restore_key(k)` | `_restore_pickled_key`, `_passthrough` |
| `unpickler.py:775:42` | none: client classes |
| `unpickler.py:865:31` | the 7 library classes whose no-data `__new__` raised ("Open receiver sets"); a client class otherwise |
| `unpickler.py:895:31` `handler(self)` | as `pickler.py:597:29` |
| `handlers.py:242:21` `clone(self.exemplar)` | `copy.copy`, the default |
| `ext/numpy.py:58:45`, `68:49`, `69:45` `.type(...)` | the numpy scalar classes (J5), `numpy.datetime64` |
| `ext/pandas.py:356:62` | `tuple`, the lambda of the same line |
| `ext/pandas.py:360:37` `self.index_constructor(...)` | `pandas.Index`, `pandas.PeriodIndex` |
| `util.py:618:22` `getter(obj)` | `operator.itemgetter.__call__`, the default |

## Rejected trace edges

34 edges, all calls of client values or a naming artefact:

- 13 under `Pickler._flatten_obj_instance`: the pickle protocol methods of
  objects that the tests encode (`BaseException.__reduce__`,
  `str` and `tuple` `__getnewargs__`, `namedtuple.__getnewargs__`,
  the `__reduce__` of `Counter`, `OrderedDict`, `deque`,
  `tzinfo`, `Decimal`, `ZoneInfo`, a str iterator, `Enum.__reduce_ex__`,
  and a naming artefact: the tracer's `_cython_3_3_0.cython_function_or_method.__call__`
  for `pandas.Timedelta.__reduce__`, which the graph has).
- 6 under `Unpickler._restore_object_instance`: the `__new__` of the tests'
  classes (`dict`, `list`, `set`, `str` subclasses,
  `os.stat_result`, `time.struct_time`).
- 11 under `Unpickler._restore_reduce`: the tests' reconstructors (`iter`,
  `Counter`, `OrderedDict`, `deque`, `timezone`, `Decimal`,
  `ZoneInfo._unpickle`, and the naming artefact `_cython_...__call__` for
  `_timedelta_unpickle`, which the graph has) and the methods of the objects
  they make (`OrderedDict.__setitem__`, `deque.extend`,
  `BaseException.__setstate__`).
- 2 under `_restore_object_instance_variables`: `list.append` and
  `set.add` of the tests' list and set subclasses.
- `util.items -> collections.OrderedDict.items` (the tests' OrderedDict) and
  `PandasTimestampHandler.flatten -> _cython_3_3_0.cython_function_or_method.__call__`
  (a naming artefact for `pandas.Timestamp.isoformat`, J14).

## Statistics

| | Count |
|---|---|
| Sites | 1046 (1026 call, 1 decorator, 6 op, 13 format); 504 with candidates; 121 value sites |
| Ledger entries | 1028 (1026 call, 1 decorator, 1 format) |
| Callee lines / rejection lines (`reject *`) / notes / exclusions | 1565 / 81 (1) / 214 / 0 |
| Default rejections | 6 lines, 49 candidates, 891 candidate-site pairs |
| Edges | 1277: 383 in the package, 894 outside (a lower bound at the sites of "Open receiver sets") |
| Edges that the trace confirms | 794 of 1277 (62.2%) |
| Edges only from reading | 483 (39 in the package, 444 outside) |
| Trace edges rejected | 34 |
| Functions that the tests run | 217 of 235 |

The 18 functions that no test runs: `enable_fallthrough`,
`compat.iterator`, `PandasDfHandler.restore_v3_3` and
`make_read_csv_params` (only the deselected tests ran them), the gmpy handler (gmpy2 is not installed), the
`UnpickleableNumpyGenericHandler` methods, `pd_encode`, `pd_decode`,
`BaseHandler.flatten` and `.restore`, `CloneFactory.__repr__`,
`TextIOHandler.restore`, `_restore_repr` (`safe=False`), `has_tag_dict`,
`make_blank_classic` and `util.is_unicode`.

## Codex audit round 1

27 missing edges, 0 false, 2 unsure. 15 accepted and applied (849 to 864
edges: 383 inside, 466 to 481 outside), 12 for the referee. Unsure 2 was
then decided from the pandas sources: 6 more edges (870: 383 inside, 487
outside). The referee's rulings (d) and (e) then added 12 and 196 pairs
net (1078: 383 inside, 695 outside).

- **G1, receiver classes of `tolist` (11 edges): applied.** The README rule
  "A method of an outside object is named by the class of the receiver,
  also when that class inherits it" decides it (judgement J14):
  `NumpyGenericHandler.flatten -> numpy.datetime64.tolist` (`ext/numpy.py:53:56`);
  `PandasIndexHandler.flatten -> pandas.PeriodIndex`, `MultiIndex`,
  `DatetimeIndex`, `TimedeltaIndex`, `IntervalIndex`, `CategoricalIndex`
  `.tolist` (`ext/pandas.py:348:32`); `PandasDfHandler.flatten ->
  pandas.DatetimeIndex`, `TimedeltaIndex`, `PeriodIndex`, `IntervalIndex`
  `.tolist` (`ext/pandas.py:155:44`, and at `145:41` for the columns,
  which adds no edge). Checked in pandas 3.0.6, `core/indexes/base.py:614-637`
  and `core/base.py:892`.
- **G2, library values that the numpy handlers forward (4 edges): applied.**
  `_flatten_obj_instance -> complex.__getnewargs__` (`pickler.py:688:70`)
  and `-> datetime.timedelta.__reduce__` (`610:48`);
  `_restore_object_instance -> complex.__new__` (`unpickler.py:857:43`);
  `_restore_reduce -> datetime.timedelta` (`583:23`). All 4 were rejected
  trace edges and are now traced edges of the graph (judgement J11).
- **G3, after a public `unregister` of a default handler (12 edges):
  applied after the referee's ruling (d)** (a default handler removed with
  the public `unregister` is an admitted state). Each note names the
  witness: the handler that stays registered and forwards the value
  (numpy.generic without the exact datetime64 registration; the numpy
  handlers without DatetimeHandler for date or datetime; the Series handler
  without the ndarray or Index handler). The Index and RangeIndex
  constructors raise inside their bodies, so both `__new__` at
  `unpickler.py:857` and the class call at `865` are edges.
- **Unsure 1 (receiver sets of numpy scalars and dtypes): applied after
  the referee's ruling (e)**, generated by script from the ruling's sets:
  -3 pairs (`numpy.generic.tolist` twice, `numpy.generic.item`), +65
  scalar pairs (21 at `ext/numpy.py:53:56`, 22 at `80:51`, 22 at
  `ext/pandas.py:21:24`) and +134 dtype pairs (G at `52:50`: 21; F at
  `100:50`, `188:54`, `293:54`: 23 each; R at `153:47`, `343:60`: 22
  each). Every name was checked in numpy 2.5.4 (`__init__.pyi`,
  `dtypes.pyi`). The C integer names were then settled by the C-integer
  ruling (judgement J14): +28 pairs, applied in round 2.
- **Unsure 2 (native reducers): decided from the pandas 3.0.6 `.pyx`
  sources, 6 edges applied (864 to 870).** Without any unregistration, the
  pandas handlers hand three pandas scalars to the generic pickler through
  `tolist()` (`ext/pandas.py:176-180`, `348`, `414-415`): `Timedelta`
  (`__reduce__` returns `(_timedelta_unpickle, (value, reso))`,
  `_libs/tslibs/timedeltas.pyx:1044`, `2320-2322`), `NaT` (`NaTType`
  defines `__reduce_ex__` and `__reduce__`, which returns
  `(_nat_unpickle, (None,))`, `nattype.pyx:79`, `391-398`) and `NA`
  (`NAType.__reduce__` returns `"NA"`, `_libs/missing.pyx:422`; the
  pickler then writes the class, and decoding calls `NAType.__new__`,
  `missing.pyx:400`). Names: the methods by the receiver class through its
  public path (`pandas.Timedelta`; `NaTType` and `NAType` set
  `__module__ = "pandas.api.typing"`); the reconstructors, module-level
  Cython functions without a public alias, by their module path (the
  micro-benchmark rule for functions of a module). The README reads
  `_cython_3_3_0.cython_function_or_method.__call__` as the tracer's name of
  a Cython function (itables, rejected as a naming artefact). So the two
  traced `_cython...__call__` edges stay in `jsonpickle.rejected.json`
  with a corrected reason, and the calls they stand for (the
  `TimedeltaIndex` round trip, `tests/pandas_test.py:144`) are in the
  graph under their real names. Not decided: the pandas ExtensionArrays
  that `PandasSeriesHandler.flatten` forwards as `obj.values`
  (`ext/pandas.py:327`; for example `Categorical`, `StringArray`, the
  masked arrays) reach the generic pickler too; `NDArrayBacked`
  (`_libs/arrays.pyx`) defines no `__reduce__`, so its reducer is the one
  that Cython generates at build time (auto-pickling), which no source file
  on disk holds. The numpy C files add nothing without unregistration:
  every numpy value that reaches the pickler goes to a numpy handler.

## Codex audit round 2

152 missing edges, 0 false, 3 unsure, 4 metadata items. All 152 accepted
and applied by script (1078 to 1230 edges; inside stays 383, outside 695
to 847). Each group's chain was checked in the numpy 2.5.4 and pandas 3.0.6
sources on disk (C and Cython included).

- **C, C-integer names (28): applied**, by the C-integer ruling; I checked
  `arraytypes.h.src:99-139` (the order long, long long, int, and the
  `*_not_size_named` conditions).
- **N, ndarray reconstruction (2): applied.** `array_reduce` returns
  `_reconstruct` and a five-item state (`methods.c:1785-1860`, protocol 2
  takes it, `2009`); `multiarray.py:54` sets its module. Callees
  `numpy._core.multiarray._reconstruct` (`unpickler.py:583`) and
  `numpy.ndarray.__setstate__` (`587`).
- **D, dtype reduction and state (49): applied.** `numpy.dtype` defines
  `__reduce__` and `__setstate__` (`descriptor.c:3485-3490`), whose
  reconstructor is `numpy.dtype` (`2768-2790`); a structured void with a
  subarray field gives an ndarray through `tolist()`
  (`arraytypes.c.src:877`). 26 `__reduce__` receivers, `numpy.dtype`, 22
  `__setstate__` receivers.
- **S, extended precision (3): applied.** `LONGDOUBLE_getitem` and
  `CLONGDOUBLE_getitem` return array scalars (`arraytypes.c.src:602`,
  `636`); `gentype_reduce` (`scalartypes.c.src:2406`) gives
  `numpy._core.multiarray.scalar`.
- **T, pandas scalars (6): applied.** `_Timestamp.__reduce_ex__` and
  `_unpickle_timestamp` (`timestamps.pyx:1355-1375`, `173`); the Period
  and Interval reducers (`period.pyx:2747`, `interval.pyx:508`). The
  auditor's site `pickler.py:622:50` is `622:51`.
- **I, index constructors (10): applied.** Each no-data `__new__` raises
  `TypeError` inside its body (`datetimes.py:668`, `timedeltas.py:169`,
  `category.py:202` through `_raise_scalar_data_error`; `multi.py:310-311`;
  `period.py:251` and `arrays/period.py:1271`, `list(None)`), so
  `unpickler.py:857` and `865` both have the class.
- **A, extension arrays and their dtypes (16): applied.** `external_values`
  keeps them (`blocks.py:2376-2403`); no class of their MRO defines a
  reducer or `__getstate__` (core/arrays and core/dtypes, checked), and none
  has `__slots__`; the receivers are named by their public class paths
  (`pandas.arrays.*`, `pandas.*Dtype`).
- **Q, sparse indexes (4): applied.** `IntIndex.__reduce__` and
  `BlockIndex.__reduce__` (`sparse.pyx:59`, `305`), exported by
  `pandas.core.arrays.sparse` (`__init__.py:12`).
- **F, Period frequencies (24): applied.** The twelve classes derive from
  `SingleConstructorOffset`, whose `__reduce__` (`offsets.pyx:1137`)
  returns the class and its attributes; they are exported by
  `pandas.tseries.offsets`.
- **E, numeric Interval endpoints (10): applied.** `IntervalArray` makes
  each Interval from the numpy elements of its sides (`interval.py:1791-1802`).
- **Unsure 1 to 3: not decided**; the sources are not on disk (see "Open
  receiver sets").
- **Metadata (4): fixed.** The decoded-data paragraph of "Scope rules"
  (B2 and B5) now names the library values; the note at
  `unpickler.py:587:36` names its receivers; four duplicated `note:`
  prefixes are removed; the CPython-only decision needs no change.

## Open receiver sets

By the lead's decision ("Open receiver sets of a generic serialisation
path", README rulings), the outside callees at these sites are a stated
lower bound. The receivers are whatever library objects reach the generic
pickler, or a receiver-name site, across every admitted numpy and pandas
release and supported platform, including reducers that Cython generates at
build time and native types. The ledger records every pair that was
verified in a source on disk (numpy 2.5.4, pandas 3.0.6, CPython); it does
not try to close the set.

| Site | Operation | Callees now |
|---|---|---|
| `jsonpickle/pickler.py:610:48` | `obj.__reduce__()` | 59 |
| `jsonpickle/pickler.py:622:51` | `obj.__reduce_ex__(2)` | 4 |
| `jsonpickle/pickler.py:688:70` | `obj.__getnewargs__()` | 1 |
| `jsonpickle/unpickler.py:583:23` | `f(*args)` (reconstructor) | 26 |
| `jsonpickle/unpickler.py:587:36` | `stage1.__setstate__(state)` | 23 |
| `jsonpickle/unpickler.py:857:43` | `cls.__new__(cls, *args, **kwargs)` | 26 |
| `jsonpickle/unpickler.py:865:31` | `cls(*args)` | 7 |
| `jsonpickle/ext/numpy.py:52:50` | `obj.dtype.newbyteorder('N')` | 26 |
| `jsonpickle/ext/numpy.py:53:56` | `obj.tolist()` (numpy scalar) | 26 |
| `jsonpickle/ext/numpy.py:58:45` | `self.restore_dtype(data).type(value)` | 21 |
| `jsonpickle/ext/numpy.py:80:51` | `obj.tolist()` (numpy scalar) | 26 |
| `jsonpickle/ext/numpy.py:100:50` | `obj.dtype.newbyteorder('N')` | 28 |
| `jsonpickle/ext/numpy.py:153:47` | `arr.dtype.newbyteorder(byteorder)` | 23 |
| `jsonpickle/ext/numpy.py:188:54` | `obj.dtype.newbyteorder('N')` | 28 |
| `jsonpickle/ext/numpy.py:293:54` | `obj.dtype.newbyteorder('N')` | 28 |
| `jsonpickle/ext/numpy.py:343:60` | `self.restore_dtype(data).newbyteorder(...)` | 23 |
| `jsonpickle/ext/pandas.py:21:24` | `obj.item()` (numpy scalar) | 26 |
| `jsonpickle/ext/pandas.py:145:41` | `obj.columns.tolist()` | 6 |
| `jsonpickle/ext/pandas.py:155:44` | `obj.index.tolist()` | 6 |
| `jsonpickle/ext/pandas.py:348:32` | `obj.tolist()` (pandas Index) | 8 |
| `jsonpickle/pickler.py:551:41` | `obj.__class__.mro()` | 1 |
| `jsonpickle/pickler.py:695:41` | `obj.__getstate__()` | 41 |
| `jsonpickle/unpickler.py:786:34` | `instance.__setstate__(state)` | 4 |
| `jsonpickle/unpickler.py:819:36` | `instance.append(...)` | 1 |

The last four sites were found by the Codex confirmation pass (round 3).
Further generic sites of the same kind exist: `_restore_state`,
`_restore_object_instance_variables` and `_flatten_newstyle_with_slots`
are the same generic path. I went once through every call site of
`pickler.py`, `unpickler.py` and `util.py` whose receiver is whatever object
is being flattened or restored, or a part of it. These are open receiver
sites too, also where the ledger records no library callee yet (their
callees are client code for client objects, and library values that the
package forwards can reach them):

| Site | Operation | Callees now |
|---|---|---|
| `jsonpickle/pickler.py:305:62` | `obj.__dict__.items()` (sorted keys) | 2 |
| `jsonpickle/pickler.py:684:72` | `obj.__getnewargs_ex__()` | 0 |
| `jsonpickle/pickler.py:691:72` | `obj.__getinitargs__()` | 0 |
| `jsonpickle/pickler.py:844:85` | `factory()` (a dict's default_factory) | 1 |
| `jsonpickle/util.py:626:26` | `obj.items()` (a dict or dict subclass) | 1 |
| `jsonpickle/unpickler.py:576:33` | `cls.__new__(cls, *args[1:])` (py/newobj) | 0 |
| `jsonpickle/unpickler.py:594:54` | `stage1.__dict__.items()` | 0 |
| `jsonpickle/unpickler.py:605:51` | `stage1.__dict__.update(dict_state)` | 0 |
| `jsonpickle/unpickler.py:613:30` | `stage1.extend(listitems)` | 0 |
| `jsonpickle/unpickler.py:616:34` | `stage1.append(x)` | 0 |
| `jsonpickle/unpickler.py:620:35` | `stage1.__setitem__(k, v)` | 0 |
| `jsonpickle/unpickler.py:775:42` | `instance.__class__(deferred)` | 0 |
| `jsonpickle/unpickler.py:822:33` | `instance.add(...)` | 0 |
| `jsonpickle/unpickler.py:854:43` | `cls.__new__(cls, factory, *args, **kwargs)` | 0 |

The builtin calls of the generic path (`repr`, `getattr`, `setattr`,
`list`, `iter`, `islice`) have fixed callees and are not listed; the library
code that they run on such an object is implicit and adds no edge.


The set is open for these reasons, which sources not on disk would decide
(Codex audit round 2, Unsure 1 to 3):

1. **Generated Cython reducers.** The reducer, reconstructor and state
   calls of `NDArrayBacked` and its subclasses (`Categorical`,
   `StringArray` and others that `ext/pandas.py:327` forwards) are code
   that Cython generates when pandas is built; `_libs/arrays.pyx:16` does
   not contain it. Needed: the generated C of the pinned pandas build.
2. **Older admitted releases.** Older pandas and numpy releases have other
   receiver classes and names (pandas' `Int64Index`, `UInt64Index`,
   `Float64Index`, `pandas/compat/pickle_compat.py:44`; numpy 1.x's
   `numpy.core.multiarray._reconstruct` and the `numpy.dtype` reducer and
   state names before `numpy.dtypes`, 1.25). Needed: the sources of those
   releases.
3. **Native values under `include_properties=True`.** `pickler.py:532`
   flattens the attribute values of library objects, for example the
   `ctypes.c_void_p` inside an ndarray's `ctypes` wrapper
   (numpy `_core/_internal.py:267`); its pickle protocol is in CPython's
   `_ctypes` C sources, which are not on disk.
4. **Historical names at the round-3 sites.** Older pandas releases may
   spell the classes differently, for example
   `pandas.core.indexes.frozen.FrozenList.append` at `unpickler.py:819:36`
   (Codex audit round 3, Unsure 1). Needed: older pandas sources.

## Codex audit round 3 (confirmation pass)

No wrong pair and nothing inside the package. 47 missing pairs at four
generic sites, all applied by script after the five witnesses were checked
in the pandas 3.0.6 and dateutil 2.9.0.post0 sources (1230 to 1277 edges;
inside stays 383):

- **Witness 1 (cached dtypes): 4 + 3 pairs.** `CategoricalDtype`,
  `DatetimeTZDtype`, `IntervalDtype` and `PeriodDtype` derive from
  `PandasExtensionDtype`, whose `__getstate__` is at `dtypes.py:146`;
  only `PeriodDtype` has a `__reduce__` (`1072`), skipped with
  `unpicklable=False`; the three `__setstate__` are at `396`, `965`,
  `1429`.
- **Witness 2 (frequency offsets): 36 pairs.** `BaseOffset.__getstate__`
  (`offsets.pyx:950`); all 36 classes are exported by
  `pandas.tseries.offsets`.
- **Witness 3 (dateutil `_ttinfo`): 2 pairs.** `_ttinfo` has slots and
  `__getstate__`/`__setstate__` (`tz/tz.py:328-345`); `tzfile` reduces to
  its `__dict__` (`866-870`).
- **Witness 4 (`weekday`): 1 pair.** `dateutil/_common.py:6-7`: slots, no
  state method. `_flatten_newstyle_with_slots -> <builtin>.type.mro` is an
  edge again on this ground and left `jsonpickle.rejected.json` (34 rejected
  now).
- **Witness 5 (`FrozenList.append`): 1 pair.** `pop = append = extend =
  _disabled` (`frozen.py:120`), which binds any arguments and raises;
  `FrozenList` is exported by `pandas.api.typing`.
- **Open receiver sites:** the auditor's three further `__new__` examples
  at `unpickler.py:857:43` are not counted (lower bound). Unsure 1 is
  listed under "Open receiver sets".
- **Metadata (2): fixed.** The ledger's header comment now names the
  library values beside the CloneFactory, and the "Value sites" table
  gives the current callees of `unpickler.py:583:23` and `865:31`.
