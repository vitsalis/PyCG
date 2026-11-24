# tinydb: judgements of the ground truth

Status (writer, batch 7, 2026-11-23): complete. `check.py --write tinydb`
and `check.py tinydb` report no error; every site is decided; the trace
has no edge that the graph lacks. After the blind audit (`tinydb.audit.md`,
F1 to F5) and the referee's ruling (`b7-ruling-tinydb.md` in the
audit records; README, "Rulings for batch 7"), adopted by the lead:
F1 added 3 inside edges (J10); F2 added a callee at a site whose pair the
graph already had; F3 to F5 changed wording and evidence (J2, J6, J8).
Codex audit round 1 added 3 inside edges (J2: `LRUCache.__delitem__ ->
QueryInstance.__eq__`; J4: `Query.__eq__.<lambda1>` -> `Query.__eq__` and
`QueryInstance.__eq__`) and corrected the note on `-O`; its ruling
question R1 (a client encoder that returns bytes) went to the referee,
whose ruling added 6 outside edges (J6).

Release v4.9.0 (commit `1e39ad3`). Analysed source: `tinydb/` (10 modules,
158 functions with 20 lambdas, 14 classes), `tinydb/mypy_plugin.py`
included. `pyproject.toml` declares `requires-python = ">=3.10,<4"`, the
classifiers CPython and PyPy and "OS Independent"; CI runs CPython 3.10 to
3.14 on Linux, macOS and Windows and PyPy 3.9 and 3.10 on Linux
(`.github/workflows/ci-workflow.yml:13-24`). So the bound `>=3.10,<4`
applies to the existing CPython and PyPy versions (CPython 3.10 and later,
PyPy 3.10 and later), on every platform; the 3.14 classifier is not an
upper bound. The
package has no version or platform branch. The only `assert`s are in
`mypy_plugin.py`; one calls `isinstance` (`mypy_plugin.py:23`), which
`-O` removes, so normal execution has that edge and optimized execution
adds none (the graph is their union).

The ledger is `tinydb.ledger`; `tinydb.json` and `tinydb.added.json` are
generated from it. No trace edge is rejected, so there is no
`tinydb.rejected.json`.

## Values, as the ledger uses them

- **Storages.** `TinyDB(storage=...)` takes a storage class or a
  middleware instance (`database.py:92-95`). Package values: `JSONStorage`
  (the default, line 85), `MemoryStorage` (`docs/usage.rst:592-617`),
  `CachingMiddleware(...)` (`docs/usage.rst:635`, README) and a plain
  `Middleware(...)` (J5). `Storage` is abstract by `abc`. Client storages
  and client middlewares are client code. `TinyDB.storage` and
  `Table._storage` hold the instance that this call returns.
- **Queries.** The query objects that the package builds and documents
  for the `cond` of `search`, `get`, `contains`, `update`, `update_multiple`,
  `remove`, `count` and `upsert` are `QueryInstance` objects: the results of
  the comparisons, `exists`, `matches`, `search`, `test`, `any`, `all`,
  `one_of`, `fragment`, `noop`, `&`, `|` and `~`. A client callable
  (`db.search(lambda doc: ...)`, `docs/usage.rst:208`) is opaque. A bare
  `Query` is not admitted there (J1).
- **Documents.** The table data are dicts: JSON objects that `json.load`
  returns, or the dicts that `Table._update_table` writes to a package
  storage (`dict(document)`, `table.py:170`). Values inside documents are
  client data.
- **The query cache** is the `LRUCache` of `Table.__init__`
  (`query_cache_class`, `table.py:87, 108`). Its keys are the `cond`s that
  `Table.search` passes (`table.py:245, 275`).
- **Class attributes for customization** (`document_class`,
  `document_id_class`, `query_cache_class`, `table_class`,
  `default_storage_class`): their defaults are package values; a documented
  override (`docs/extend.rst:157-199`, the class docstrings) is a client
  class, so a value site keeps only the default.

## Judgement calls

**J1. A bare `Query` as the `cond` of a table method.** `cond` is annotated
with the package Protocol `QueryLike`. By the ruling on package Protocols
(README, "Rulings for batch 6") it admits the classes that the
package documents as implementations. The documentation calls `Query` a
"query builder" that "generates QueryInstance objects which will evaluate
their query against a given document when called" (`queries.py:59-63`,
`169-170`), and the documented conditions are all `QueryInstance`
objects. Evaluating a `Query` raises `RuntimeError('Empty query was
evaluated')`, and the test of that error is a test of a refusal
(`tests/test_queries.py:467-469`). No test or document passes a `Query` to a
table method. So the ledger does not admit `Query` at `cond`. If the lead
admits it (a `Query` is a `QueryInstance` by inheritance, and
`db.search(where('a'))` on an empty table returns `[]` and caches the
`Query`), four edges are added: `LRUCache.get` and `LRUCache.set` ->
`Query.__hash__` and `Query.__eq__`. The referee confirmed J1 with this
rule (adopted by the lead): "A package Protocol admits implementations
established for that parameter's role; structural compatibility or
inheritance from a documented implementation does not alone override
documentation distinguishing a builder from an evaluable condition. A
concrete package-base annotation admits its package subclasses, and a
later evaluation failure does not remove calls reached before that
failure." The four edges stay absent.

**J2. The query cache calls back the keys.** `LRUCache.get`, `set` and
`__contains__` use an `OrderedDict` keyed by queries. Each lookup hashes
the key (`QueryInstance.__hash__`), and a stored key of equal hash is
compared (`QueryInstance.__eq__`, stored key first). Equal hashes are
ordinary: two equal queries (`tests/test_tinydb.py:408-411` searches
`where('int') == 1` twice; the trace has `LRUCache.get ->
QueryInstance.__eq__`), and also unequal ones, because CPython gives
`hash(-1) == hash(-2)`, so `where('a') == -1` and `where('a') == -2` have
equal hashes: the first `get` of the second query misses after a
comparison, and `set` compares again (`101:16`, `105:23`). The tests pass
`QueryInstance`s to `LRUCache.__contains__` (`tests/test_tables.py:63`),
an admitted value by the test clause of B2. `OrderedDict.popitem(last=False)`
(`utils.py:111`) pops with the stored hash on CPython, but it still finds
the node by a dict lookup, which compares a stored key of equal hash met
earlier on the probe path (`move_to_end` reorders the linked list, not the
dict slots; audit F2, from knowledge of the C source). PyPy's
`OrderedDict.popitem(last=False)` calls `self.pop(k)`, which hashes the
oldest key: read in `deps/_pypy/pypy3.10-v7.3.19-src/pypy/module/_collections/app_odict.py:64-77`
(the same code in the 3.9 and 3.11 sources there). That site keeps
`QueryInstance.__hash__` and `QueryInstance.__eq__` (both pairs are also
edges at `101:16`; audit F3 asked for the path of this file).
`LRUCache.__delitem__` is never called by the package, but `LRUCache` is
public and a `QueryInstance` is an admitted key (`table.py:275`): deleting
a plain int whose hash equals a stored query's hash (an int has any hash
in its range, and a query's tuple hash falls in it for some field names
and hash seeds) compares the stored query before the `KeyError`, so
`LRUCache.__delitem__ -> QueryInstance.__eq__` at `78:23` (Codex round 1,
applied with this int witness instead of Codex's client key).

**J3. Hashes of nested queries.** `QueryInstance.__init__` hashes its
`hashval` (`queries.py:77`), and `__hash__` hashes `_hash` (line 100).
These tuples hold `FrozenDict`s (`freeze` of dict operands, nested
dicts), and `any`/`all` keep their `cond` unchanged in the tuple
(`freeze(cond)` returns a query as it is). `cond` is annotated
`Union[QueryInstance, list[Any]]`: a concrete package class, so its
subclass `Query` fits too (the h11 precedent: `Type[Sentinel]` admits any
sentinel class). `~` nests the negated query's hash. CPython before 3.14
and PyPy compute a tuple's hash at each call, so `hash(self._hash)` and the
`frozenset` of `&` and `|` (`118:40`, `128:39`) hash these items again:
`QueryInstance.__hash__`, `Query.__hash__` and `FrozenDict.__hash__`
there. The trace (CPython 3.14.10) has `QueryInstance.__init__ ->
QueryInstance.__hash__` and `-> FrozenDict.__hash__` but no
`QueryInstance.__hash__ -> QueryInstance.__hash__`, as 3.14's cached tuple
hash predicts (the tests hash each query again after its `__init__`). The
reading of CPython's tuple hash is from knowledge (the deps hold no
`Objects/` sources); for PyPy the referee cites
`deps/_pypy/pypy3.11-v7.3.20-src/pypy/objspace/std/tupleobject.py:392`,
which recomputes the element hashes. J3 was confirmed by the referee
(the rule quoted in J1); the eight edges stay. The edges that rest on a `Query` inside `any`/`all`
are 8: `QueryInstance.__init__`, `__hash__`, `__and__`, `__or__` ->
`Query.__hash__`; `__eq__`, `__and__`, `__or__` -> `Query.__eq__`;
`__repr__` -> `Query.__repr__`.

**J4. Comparisons of nested queries.** `QueryInstance.__eq__` compares the
hash tuples (`107:31`). Tuples and frozensets compare their items, so two
distinct nested queries are compared with their own `__eq__`:
`QueryInstance.__eq__`, or `Query.__eq__`, which builds a query (a
`QueryInstance` is true: it has no `__bool__` and no `__len__`; a `Query`
without a path raises `ValueError` there). The same comparisons run when
the frozenset of `&` or `|` meets two tuples of equal hash. Comparisons
of a query with a document field (`value == rhs` and the other lambdas)
compare client data: the documentation rules out field-to-field
comparisons (`docs/getting-started.rst:115-120`), so no client passes a
query as `rhs`. The package itself does: the comparison at `107:31`
calls `Query.__eq__` with the nested Query or QueryInstance as `rhs`
(witnesses: `Query().f.any(Query().x)` compared with an independently
built `Query().f.any(Query().x)`, or with `Query().f.any(Query().x ==
1)`), and the lambda made there captures it. That lambda never runs on a
document, but by rule A and the round-1 ruling (a) (an object that the
package makes need not escape before its body edges count) its body
`value == rhs` keeps its edges: a document field returns `NotImplemented`,
so Python calls the reflected `Query.__eq__` or `QueryInstance.__eq__`
(`260:33`; Codex round 1, applied). `__ne__` and the order comparisons
are never called with a query `rhs` by the package.

**J5. Middlewares.** `Middleware` (`tinydb.middlewares.Middleware`) is a
public, concrete, documented base class; the API documentation says that
"If read() or write() are not overloaded, they will be forwarded directly
to the storage instance" (`docs/api.rst:94-102`), and the docstring of
`Middleware.__call__` shows `TinyDB(storage=Middleware(StorageClass))`
(`middlewares.py:41-47`). By B1 a plain class
documented for subclassing is a receiver of its own methods, so a plain
`Middleware(JSONStorage)` is an admitted storage. Then every load of
`read`, `write` or `close` from the storage runs `Middleware.__getattr__`
(the trace has `TinyDB.close -> Middleware.__getattr__`, from a client
subclass, `tests/test_tinydb.py:671-676`). Nesting is documented
(`docs/usage.rst:637-641`; `middlewares.py:57-60`): an inner middleware
gives `Middleware.__call__ -> Middleware.__call__`, `Middleware.__getattr__
-> Middleware.__getattr__` (an inner `Middleware` lacks `read`; an inner
`CachingMiddleware` lacks a tested name such as `_handle`,
`tests/test_middlewares.py:99`), and `CachingMiddleware.read`, `flush`,
`close` -> the `CachingMiddleware` methods. A middleware class passed as
`storage=` (not an instance) is not documented and is not considered.

**J6. File objects of `JSONStorage`.** `self._handle = open(path,
mode=self._mode, encoding=encoding)` (`storages.py:120`). `access_mode`
is unannotated; its docstring says "(r, r+)", and the code accepts `'r'`,
`'rb'`, `'r+'`, `'rb+'` without a warning and every other mode with one
(lines 108-112). Its documented contract and the explicit handling in
the code decide (ruling (b) after Codex
audit round 1; audit F5): the code names the binary modes `'rb'` and
`'rb+'` (line 108), handles the `w` and `a` modes on purpose (the `touch`
branch, lines 116-117), and accepts every other mode with a warning, not
a refusal; a test builds a `JSONStorage` with `'w'`
(`tests/test_storages.py:286-287`). So the valid `open()` modes are
admitted, text and binary: `r`, `w`, `a`, `x`, with an optional `+`, and
the legacy `U` reading modes of the admitted 3.10 runtimes (the referee;
README, "Rulings for batch 7"); binary modes need `encoding=None`. Text
modes give an `io.TextIOWrapper`,
`'rb'` an `io.BufferedReader`, `'wb'`/`'ab'`/`'xb'` an
`io.BufferedWriter`, the `+` binary modes an `io.BufferedRandom`
(`buffering` is never passed, so no `FileIO`). `close`, `seek` and `tell`
have the four classes. `write(serialized)` gets a str: all four enter
`write` (the text stream writes it or, in `'r'`, raises
`io.UnsupportedOperation`; `BufferedReader.write` raises
`UnsupportedOperation`, caught and re-raised as `IOError`;
`BufferedWriter.write` and `BufferedRandom.write` raise `TypeError` for
the str of the default encoder, which is not caught). A client `cls`
encoder (a documented option, `docs/usage.rst:599-612`) can return bytes:
`json.dumps` returns the encoder's `encode` result unchecked, so a
`BufferedWriter` or `BufferedRandom` then writes it, and `flush`,
`fileno`, `os.fsync` and `truncate` (lines 156-161) run on it. The
referee's ruling on Codex R1 (`b7-ruling-round1-disputes.md`, case 2,
adopted by the lead), which revises its earlier exclusion: "An admitted
client callback's opaque result may determine whether a call on an
independently admitted receiver succeeds and later calls run; that
witness alone supplies no callee name for the callback or its result."
So `flush`, `fileno` and `truncate` have `io.TextIOWrapper`,
`io.BufferedWriter` and `io.BufferedRandom` (six pairs added); a
`BufferedReader` never writes, so it has none of them. `os.fsync` keeps its
one name, and `close` and `read` already have all four classes. 21 of the
outside edges rest on the binary modes.

**J7. `FrozenDict` construction.** `FrozenDict(...)` (`utils.py:150`) runs
`<builtin>.dict.__init__` (FrozenDict has no `__init__`). `dict.__init__`
inserts the pairs directly and never calls the subclass's `__setitem__`
(here `_immutable`): on CPython by `PyDict_MergeFromSeq2` (the trace
agrees: `freeze -> <builtin>.dict.__init__` and no `-> _immutable`). On
PyPy, `dict.__init__` with a sequence of pairs runs `update1_pairs`,
which stores each pair with the interpreter-level `w_dict.setitem`
(`deps/_pypy/pypy3.11-v7.3.20-src/pypy/objspace/std/dictmultiobject.py:1410-1416`,
via `init_or_update` and `update1`, lines 1378-1436); the objspace of the
3.10 source is not in the deps. Upstream also runs the suite on PyPy
3.10, whose `test_freeze` and `test_any` freeze dicts and would fail if
`dict.__init__` called the override. No `_immutable` edge.

**J8. `mypy_plugin.py`.** mypy is not installed in the test environment
and no test imports the module. Its calls are named as missing modules:
`super().__init__(options)` -> `mypy.plugin.Plugin.__init__`;
`self.lookup_fully_qualified(...)`, inherited from the stub base, ->
`mypy.plugin.Plugin.lookup_fully_qualified` (bottle's
`gunicorn.app.base.BaseApplication.run`); `ctx` is annotated with the stub
class `DynamicClassDefContext`, so `ctx.api.add_symbol_table_node(...)` ->
`mypy.plugin.DynamicClassDefContext.api.add_symbol_table_node`. The
README's exception for a definition made through a missing library (a
base class) asks to read the library's base: mypy 2.1.0, the pin of
`uv.lock:603-614` (`dev` group), read from its sdist `mypy-2.1.0.tar.gz`,
SHA-256 `81e76ad12c2d804512e9b13240d1588316531bfba07558286078bfbce9613633`
(`deps/tinydb/mypy-2.1.0/mypy/plugin.py`, never run). `Plugin.__init__`
(`plugin.py:535-541`) only assigns `options`, `python_version` and
`_modules`; `Plugin.lookup_fully_qualified` (546-548) asserts and calls
the module function `mypy.lookup.lookup_fully_qualified`. Neither calls a
method that `TinyDBPlugin` overrides (`__init__`,
`get_dynamic_class_hook`), so no call-back edge follows (audit F4).
mypy is not installed, so the missing-module names stay (README: "also
when a copy of the library can be read").

**J9. A forwarded property name.** `TinyDB.__getattr__` forwards unknown
names to the default table (`database.py:251-255`). `name` is a tested
name on a `Table` (`tests/test_tables.py:153`, `tests/test_tinydb.py:644`),
so by "Forwarded attribute names" (README, clarifications of the full
audit) `db.name` reaches the property: `TinyDB.__getattr__ ->
Table.name` at `getattr(...)`. `Table.storage` is never forwarded:
`TinyDB.storage` shadows it.

**J10. A package value inside a client document.**
`tests/test_tinydb.py:615-627` inserts `{'int': _db}`, a `TinyDB` inside a
client dict (line 623), to show that `JSONStorage` refuses it. The
referee's ruling, adopted by the lead (audit F1): "A package value used
in a refusal test remains admitted unless the parameter's annotation
excludes it; `Mapping` does not exclude a package object among the
mapping's values. That admission follows package forwarding through
successful public calls with other admitted settings, while B3 still
excludes reuse of state left by a failed call." With `JSONStorage` the
write fails (`json.dumps` finds no encoder, and the default encoder
raises after reading `o.__class__`, which the type supplies without
`TinyDB.__getattr__`), and that failed state is not reused. With
`MemoryStorage` or a `CachingMiddleware` the document is stored
(`table.py:170`, `storages.py:180-181`), and a search iterates the field:
`Query().int.any(Query().noop())` (`425:68`), `.any([0])` (`429:70`),
`.all(Query().noop())` (`458:68`), `.all([0])` (`462:53`: TinyDB has no
`__contains__`, so `in` iterates) and `.fragment({'x': 1})` (`485:24`).
So `Query.any.test`, `Query.all.test` and `Query.fragment.test` ->
`TinyDB.__iter__` (3 inside edges; source-derived witnesses, not run). By
the ruling, nothing else follows: TinyDB defines no comparison or hash;
query hashes hold the condition's operands, not the documents; `hasattr`
and subscripts find TinyDB's special methods without `__getattr__`;
copying the document and making a `Document` keep the reference; the
storages store it and the default JSON encoder rejects it without
iterating, hashing, testing or representing it.

**J11. Callables that clients pass.** `Query.map(fn)` (`part(value)`,
`queries.py:239`), `Query.test(func, *args)` (`queries.py:397`), the
transform functions of `update` that are not from `tinydb.operations`, the
`test` of a client's `QueryInstance` and the `json.dumps` options of
`JSONStorage` are bare callables of the client: no package callee. The
`update` transforms keep the six closures of `tinydb.operations`
(`docs/usage.rst:306-342`).

**J12. Annotations.** No module has `from __future__ import annotations`,
so module, class and signature annotations are sites (evaluated at
definition before 3.14). They subscript typing objects and builtin types
and call no package code (`typing`'s cache hashes classes, not
instances). Annotations of attributes and locals inside functions
(`self._query_cache: LRUCache[...]`, `table.py:107`) are never evaluated.
`with_typehint` returns `object` at run time (`TYPE_CHECKING` is false),
so `TinyDB` has no package base.

## Default rejections

| Candidates | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `TinyDB.__getattr__` | 286 | no attribute that the package loads on a TinyDB is missing | nowhere |
| `Middleware.__getattr__` | 274 | the receiver is no Middleware, or the class or instance has the name | the 11 storage loads of `read`, `write`, `close` (J5) and `getattr` in `Middleware.__getattr__` (73:23) |
| `Query.__getattr__` | 286 | every Query has the names that the package loads | `self.__getattr__(item)` (213:32) |
| `Query.__getitem__` | 196 | the subscripted object is no Query | `Query()[key]` in `where` (528:19) |
| `LRUCache.__getitem__` | 197 | the package never subscripts the query cache | nowhere |
| `Query.__hash__`, `QueryInstance.__hash__`, `QueryLike.__hash__`, `FrozenDict.__hash__` | 150, 146, 150, 149 | no query or FrozenDict is hashed; QueryLike has no instances | the query-cache sites (J2), `hash` and `frozenset` in queries (J3), `super().__hash__()` (188:32), nested FrozenDicts (125:20) |
| `Query.__eq__`, `QueryInstance.__eq__` | 152, 147 | no operand or key is a query | the query-cache sites and `LRUCache.__delitem__` (78:23) (J2), 107:31, the frozensets and the lambda of `Query.__eq__` (260:33) (J4) |
| `__iter__` of TinyDB, Table, LRUCache | 74, 79, 79 | no TinyDB, Table or LRUCache is iterated | `iter(...)` in `TinyDB.__iter__` and `Table.all` (Table.__iter__); the five document-field sites of J10 (TinyDB.__iter__) |
| `__len__` of TinyDB, Table, LRUCache | 57 each | none is measured or tested | `len(...)` and `__len__()` of TinyDB and Table (4 sites) |

17 defaults decide 2536 candidate-site pairs.

## Statistics

| | Count |
|---|---|
| Sites | 862 (321 call, 15 decorator, 1 with, 36 iter, 4 mapping, 28 op, 112 getitem, 13 setitem, 5 delitem, 284 getattr, 35 truth, 8 format); 717 with candidates; 43 value sites |
| Ledger entries | 421 (496 callee lines, 181 rejection lines of which 53 `reject *`, 93 notes, no exclusion) |
| Nodes | 168 (10 modules, 158 functions) |
| Edges | 422: 237 in the package, 185 outside |
| Confirmed by the trace | 337 of 422 (79.9%); the trace has 337 edges, all in the graph |
| From reading only | 85 |
| Rejected trace edges | 0 |
| Functions that the tests run | 148 of 158 (`mypy_plugin.py` is never imported; the Protocol stubs, `Storage.read`/`write`, `Table.storage` and the default lambda of `Table.search` do not run) |
