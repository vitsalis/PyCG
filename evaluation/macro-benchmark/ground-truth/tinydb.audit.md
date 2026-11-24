# tinydb: blind audit of the ground truth

**Status:** closed. The re-check of the committed ledger (commit `6a3fbb3`) is at the end. Blind sample, comparison, exhaustive checks
and findings are done; the referee upheld F1, and the writer applied F1 to F5.

Release v4.9.0, commit `1e39ad3a2d9eca57efd9019fd089b5a04676da95`. Audited
files: `tinydb.ledger` (417 entries), `tinydb.json` (410 edges: 231 in the
package, 179 outside), `tinydb.added.json`, `tinydb.md` (J1 to J12). No
`tinydb.rejected.json`. `check.py tinydb` reports no error. I read the
source, `docs/`, `README.rst`, `pyproject.toml`, the tests (as data), and
the dependency sources of the audit records, `deps/tinydb/` (PyYAML 6.0.3; mypy
2.1.0 `mypy/plugin.py`, which arrived during the audit). I ran no analysis
tool and nothing of the package.

**Result.** 109 sites re-derived blind; 107 agree, 2 differ (1 auditor
open question that J6 decides, 1 callee missing at a site whose edge the
graph already has). 5 findings: F1 (medium, +3 edges, needs a ruling of
the lead), F2 to F5 (low, no edge change). I support all twelve
judgement calls; J8's open question is now answered from the mypy source
(no change).

## Findings

| Id | Severity | Site or edge | Evidence | Edges | Confidence |
|---|---|---|---|---|---|
| F1 | medium; needs a ruling | `Query.any.test`, `Query.all.test`, `Query.fragment.test` -> `TinyDB.__iter__` (sites `queries.py` 425:68, 429:70 iter `value`; 458:68 iter `value`, 462:53 op `e in value`; 485:24 op `key not in value`), now decided by the default rejection of `TinyDB.__iter__` | J10 admits the `TinyDB` that `tests/test_tinydb.py:615-627` (line 623) puts in a client document (`_db.insert({'int': _db})`), by the test clause of B2 (json-repair ruling), and finds no edge because `JSONStorage.write` fails in `json.dumps`. But the value is admitted at `insert`'s `document`, and the storage is a separate admitted parameter: with `TinyDB(storage=MemoryStorage)` (or `CachingMiddleware(...)`, which keeps the data in `cache` until a flush) nothing fails and the document is stored (`table.py:170`, `storages.py:180-181`). The django-environ ruling combines admitted values; the README's fresh-process rule admits a sequence of public calls. Then `db.search(Query().int.any([1]))` reaches `any.test` with `value` = the TinyDB: `is_sequence` is true (`TinyDB.__iter__` exists, `database.py:270`), and `for e in value` calls `TinyDB.__iter__` (`queries.py:429`); `all(...)` iterates it (458) or tests `e in value` (462: TinyDB has no `__contains__`, so `in` iterates); `fragment` tests `key not in value` (485). The B2 exception for a value that a test passes "only to check that the package refuses it" needs an annotation that excludes it; `document: Mapping` does not constrain the values. Against: the docs say the JSON format "cannot handle ... custom classes" (`docs/usage.rst:15-18`), but that is a limit of the JSON storage, not of MemoryStorage. Ruling asked: does the test clause of B2 admit a package value at `insert`'s document for every admitted storage, or only in the tested combination? If every storage: add the 3 edges (accept `TinyDB.__iter__` at the 5 sites) and extend J10. | +3 (or 0) | likely |
| F2 | low (site completeness) | `utils.py` 111:35 `self.cache.popitem(last=False)`: add `-> tinydb.queries.QueryInstance.__eq__` | On CPython, `OrderedDict.popitem` pops the oldest node with its stored hash, but it still looks the key up in the dict (`_odict_popkey_hash` finds the node by a dict lookup, then `_PyDict_Pop_KnownHash`). A lookup compares every stored key of equal hash that lies earlier on the probe path. `move_to_end` reorders the linked list, not the dict slots, so the oldest key can sit after a colliding key: insert `A` and `B` of equal hash (`where('a') == -1`, `== -2`), `get(A)` moves `A` to the end, the next insertion pops `B` and compares `A == B` (`QueryInstance.__eq__`). The note says only that CPython uses the stored hash. The pair `LRUCache.set -> QueryInstance.__eq__` is already in the graph (101:16, 102:23, 103:35, 105:23). | 0 | likely (CPython C source read from memory) |
| F3 | low (evidence) | `tinydb.md` J2 and the note at 111:35: PyPy's `OrderedDict.popitem` | J2 cites `pypy/module/_collections/app_odict.py:64-77` (PyPy 3.10 v7.3.19) as if read; the deps of tinydb hold no PyPy source. I also remember PyPy's `popitem(last=False)` as `self.pop(k)` (so the key is hashed), but neither of us read it here. Say that it is from knowledge, or put the file in the deps. No edge rests on it alone: `LRUCache.set -> QueryInstance.__hash__` also comes from 101:16, 102:23, 103:35, 105:23. | 0 | certain (about the evidence) |
| F4 | low (record) | `tinydb.md` J8 | mypy 2.1.0's `mypy/plugin.py` is now in the deps (sdist SHA-256 `81e76ad1…9613633`, the pin of `uv.lock:603-614`). `Plugin.__init__` (`plugin.py:535-541`) only assigns `options`, `python_version` and `_modules`; `Plugin.lookup_fully_qualified` (546-548) asserts and calls the module function `mypy.lookup.lookup_fully_qualified`. Neither calls a method that `TinyDBPlugin` overrides (`__init__`, `get_dynamic_class_hook`), so the ledger's assumption holds. `DynamicClassDefContext` is a `NamedTuple` with `api: SemanticAnalyzerPluginInterface` (514-518); mypy is not installed, so the missing-module names stay (README: "also when a copy of the library can be read"). Close J8's open question and record the SHA-256, as the base-class exception asks. | 0 | certain |
| F5 | low (wording) | `tinydb.md` J6, the reason for admitting binary and write-only modes | J6 cites the path precedent (path J7), where `open`'s modes come from overloads that admit text and binary modes. Here `access_mode` is unannotated, so the contract comes from ruling (b) after Codex round 1: "the entry's documented contract, explicit type handling in the code and admitted package flows". The code names `'rb'` and `'rb+'` (`storages.py:108`), handles the `w` and `a` modes on purpose (the `touch` branch, 116-117), and accepts every other mode with a warning, not a refusal (`tests/test_storages.py:286-287` builds a `JSONStorage` with `'w'`). That supports the four classes. The 5 edges that rest on write-only binary modes (`io.BufferedWriter`: `close`, `seek` twice, `tell`, `write`) need this reason; state it. | 0 | likely |

## Step 1: blind re-derivation

**Skeleton and draw.** A scratch directory `$TMPDIR/b7-audit-tinydb/`
with a copy of `projects.toml` and of the source; `check.py --skeleton`
gave 862 sites. I numbered them module by module in (line, column) order.
Three kinds: explicit (call, decorator) 336; attribute loads 284, where the
three `__getattr__` candidates sit on every site; other implicit 242. So I
drew by kind with `random.Random(20261123)`: `rng.sample(explicit, 40)`,
`rng.sample(getattr, 15)`, `rng.sample(other, 15)`, and added the 43 value
sites (4 were in the explicit draw): 109 sites. The answers were written
(file `blind.md`, with the draw in `sample.tsv` and `draw.py`) before I
opened any file of the writer. They state five assumptions: A1 a bare
`Query` is not a `cond` (Protocol), A2 the storages and middlewares, A3
`__hash__` and `__eq__` call-backs of query keys, A4 the open modes
(write-only binary modes left open), A5 PyPy's `popitem`.

| Group | Sites | Agree | Differ |
|---|---|---|---|
| Explicit | 40 | 39 | 1 (D1) |
| Attribute loads | 15 | 15 | 0 |
| Other implicit | 15 | 15 | 0 |
| Value sites (39 not drawn above) | 39 | 38 | 1 (D2) |
| **Total** | **109** | **107** | **2** |

- **D1** `storages.py` 123:27 `self._handle.close()`: the ledger adds
  `io.BufferedWriter.close`; I had left write-only binary modes open (A4).
  Auditor's open question; J6 decides it, and I agree (F5 for the reason).
- **D2** `utils.py` 111:35 `self.cache.popitem(last=False)`: I had
  `QueryInstance.__eq__` (a CPython collision on the lookup) besides
  `OrderedDict.popitem` and the PyPy `__hash__`; the ledger lacks `__eq__`.
  Writer missed a callee whose edge the graph already has (F2).

Every other sampled site has the same callees and the same rejections,
including the 43 value sites (storages, middlewares, the six `_test`
functions, the fourteen `test` functions of `runner`, the six operation
transforms, the seven updaters, `document_class`, `document_id_class`,
`query_cache_class`).

## Step 2: exhaustive checks

**Dispatch sets.** Storages: JSONStorage, MemoryStorage (inherits
`Storage.close`), CachingMiddleware, plain Middleware (forwards through
`__getattr__`), nested middlewares; `Storage` abstract. Every load of
`read`, `write`, `close` on a storage accepts `Middleware.__getattr__`
(161:33, 170:22, 188:29, 202:22, 230:22, 99:39, 119:26, 127:22, 766:32,
795:32, 828:23), and the calls have the three package receivers. Query
receivers: QueryInstance and Query (both use `QueryInstance.__call__`).
Callback roles: `_test` (6), `runner`'s `test` (14), `updater` (7),
`fields` (6 operation transforms), `is_cacheable` (2), `part` and `func`
(client only). All agree with my reading.

**Default rejections** (17 defaults, 2544 pairs). I checked each reason
against the kinds of value at its sites (`--report --default`), and every
explicit site that a default decides. All hold, with one exception that
depends on F1: the five `queries.py` sites listed there. The explicit
accepts are right: `Middleware.__getattr__` at the eleven storage loads and
73:23; `Query.__getattr__` at 213:32; `Query.__getitem__` at 528:19; the
hash and equality call-backs at the query-cache sites (72:20, 91:31, 94:35,
101:16, 102:23, 103:35, 105:23, 111:35), at `hash` (77:21, 100:20),
`frozenset` (118:40, 128:39), 107:31, 125:20 and 188:32; `__iter__` and
`__len__` of TinyDB and Table at the six explicit sites. No other site
hashes or compares a query or a FrozenDict: the other dicts and sets hold
strs and ints, and `value == rhs` compares client data
(`docs/getting-started.rst:115-120` rules out field-to-field comparisons).
`insert_multiple`'s `Iterable[Mapping]` does not admit a TinyDB or Table:
an ABC match alone does not count (ruling on declared iterable types), and
no test or document passes one.

**Functions that no site calls** (71 of 168 nodes, the 10 modules among them):
the public API, the operator methods of queries, the operation factories,
the `LRUCache` mapping methods that only tests call, `Table.storage`
(shadowed by `TinyDB.storage`), the Protocol stubs, `Storage.read`/`write`
(abstract, always overridden) and the mypy plugin. All plausible; with F1,
`TinyDB.__iter__` gains three callers.

**Special methods and properties.** Properties: `TinyDB.storage` (six
loads), `Table.name` (four loads, and the forwarded load of J9),
`LRUCache.length` (two), `LRUCache.lru` and `Table.storage` (none). `with`:
only `touch`'s file. No package `__setattr__`, `__delattr__`,
`__set_name__` or `__init_subclass__`.

**Binding.** Every call of a package function binds its arguments (the
updaters and transforms take one argument, `perform_update` two or three,
`Document(value, doc_id)`, `LRUCache(capacity=...)`). `MemoryStorage()`
refuses the positional arguments of `TinyDB(path, storage=MemoryStorage)`,
but other calls of the same site bind, so the edge stays.

**Callees outside the package.** Names follow the micro-benchmark rules:
`collections.OrderedDict.*` by receiver class, `abc.ABC.__init__` for
`super().__init__()` of the storages (the README's example),
`<builtin>.dict.__init__` for `Document` and `FrozenDict`, class calls as
the class (`typing.TypeVar`, `<builtin>.ValueError`), the `io` classes of
J6, mypy by missing-module access paths. No error found.

**Notes and rejections.** I read every entry of the ledger; the reasons
match the source. **Trace:** every trace edge is in the graph; no edge is
rejected, so there is nothing to check there.

**Platforms and implementations (README, "Rulings for batch 7": a
platform is supported when the release declares it or tests on it).**
tinydb 4.9.0 declares `Operating System :: OS Independent`, which is a
classifier declaration of every platform. It also tests on
`ubuntu-latest`, `macos-latest` and `windows-latest`
(`.github/workflows/ci-workflow.yml:21`). For implementations it
declares `Implementation :: CPython` and `Implementation :: PyPy`
(`pyproject.toml`), with `requires-python = ">=3.10,<4"`. Its PyPy jobs
run PyPy 3.9 and 3.10 on Linux (`ci-workflow.yml:22-26`). 3.9 is below the
declared bound, so the PyPy versions are 3.10 and later. The
CI-combination ruling (path) then admits PyPy on the declared platforms.
So the writer's runtimes (CPython 3.10 to 3.14, PyPy 3.10 and later, every
platform) match the declaration. I checked the ledger against it:
- No package code branches on the platform or the implementation.
- J6 (open modes): the `io` class follows the mode, on every platform.
  Windows names no other receiver. A console path (`CON`) changes only the
  raw stream under the buffered or text wrapper, and `JSONStorage` never
  calls the raw stream (path J7 says the same). `os.fsync` and `os.path.*`
  keep their imported names. No edge depends on a platform.
- J3 (tuple hashes): CPython 3.10 to 3.13 give every edge, so no edge
  needs PyPy.
- J2: only the site entry `utils.py` 111:35 `-> QueryInstance.__hash__`
  depends on PyPy, and that pair is an edge at four other sites (F3).
- J7: PyPy is relevant only to show that there is no `_immutable` edge.

The new ruling therefore changes no edge of tinydb.

**mypy 2.1.0 (J8), with the four files now in the deps.** `plugin.py` is
as in F4. `build.py:701` calls the module's `plugin(__version__)` and
`:718` calls `plugin_type(options)`. These are calls that mypy makes into
the package, not edges of the package. `plugins/common.py` and
`plugins/default.py` are not reached from `TinyDBPlugin`. The ledger's
three mypy names stand.

## Judgement calls

| Call | Opinion |
|---|---|
| J1 bare `Query` at `cond` | Supported by the ruling on package Protocols: `QueryLike` declares no implementation, the docstring of `QueryInstance` makes it the evaluated query and `Query` the builder (`queries.py:59-63`), and no default, example, test or package call passes a `Query` to a table method. The 4 alternative edges are counted correctly. |
| J2 query-cache call-backs | Supported (README, "Call sites and candidates": equal hashes call `__eq__`; `hash(-1) == hash(-2)`). See F2 and F3. |
| J3 nested hashes | Supported by "Versions and configuration" (union over admitted versions): CPython 3.10 to 3.13 and PyPy recompute a tuple's hash, so the call-backs happen on some admitted version whatever 3.14 caches. `Query` in `any`/`all` fits the concrete annotation `QueryInstance` (subclass). No edge rests on PyPy alone. |
| J4 nested comparisons | Supported; the reflected `Query.__eq__` is right (a subclass that overrides `__eq__` is tried first). |
| J5 middlewares | Supported: a plain public class is a receiver of its own methods (B1), and the `__call__` docstring passes `Middleware(StorageClass)` as `storage`; nesting is documented (`docs/usage.rst:637-641`). |
| J6 open modes | Edges supported; the reason should be ruling (b), not path J7 (F5). |
| J7 `FrozenDict` construction | Supported. For PyPy the argument from upstream's PyPy CI (the freeze tests would fail) is sound evidence. |
| J8 mypy | Supported; open question answered from the source (F4). |
| J9 forwarded `name` | Supported by "Forwarded attribute names": `name` is tested on a `Table` (`tests/test_tables.py:153`). |
| J10 TinyDB in a document | Right for `JSONStorage`; incomplete for the other admitted storages (F1). The README does not decide whether the test clause admits the value only in the tested combination. The smaller extension of the existing rules is to admit it with every admitted storage: the json-repair ruling admits a value "at that parameter", without a condition on other parameters, and the django-environ ruling lets admitted values of parameters combine. |
| J11 client callables | Supported (bare `Callable`; B2). |
| J12 annotations | Supported (function-scope annotations of attribute targets are not evaluated). |

## Cases for the lead

1. F1: the test clause of B2 across storages (3 edges inside the package).

The README and the tools were clear for this package. One small gap: the
README says to draw "by kind where one kind dominates" but does not say
what counts as dominating; I split three ways because the attribute
loads, which carry only the three default-rejected `__getattr__`
candidates, are a third of the sites.

## Re-check (commit `6a3fbb3`, against the audited ledger `1bccd14`)

**Verdict: correct at 413 edges (234 inside, 179 outside); closed.** I
read the full diff `1bccd14..HEAD` of the tinydb files, and `check.py
tinydb` reports no error.

- **F1 (ruling `b7-ruling-tinydb.md`).** `TinyDB.__iter__` is accepted at
  exactly the five sites of the ruling and at no other: `queries.py`
  425:68, 429:70, 458:68, 462:53 and 485:24. 462:53 and 485:24 keep their
  `LRUCache.__contains__` rejection with a corrected reason. The graph
  gains exactly the 3 edges `Query.any.test`, `Query.all.test` and
  `Query.fragment.test` -> `TinyDB.__iter__`, and nothing else changes in
  `tinydb.json`. J10 quotes the ruling and gives a witness for each site.
  It also says, as the ruling does, that a failed JSON write leaves no
  reusable state.
- **F2.** `utils.py` 111:35 now has `-> QueryInstance.__eq__`, with a
  correct note. The pair was already in the graph, so no edge changes.
- **F3 was my error.** The PyPy sources are at `deps/_pypy/`, in
  the common deps directory; I had listed only `deps/tinydb/`. I read
  `pypy3.10-v7.3.19-src/pypy/module/_collections/app_odict.py:64-77`:
  `popitem(last=False)` takes the first key and returns
  `(k, self.pop(k))`, so the key is hashed. The 3.9 and 3.11 sources have
  the same line 77. J2 now cites the file; the claim was right.
- **F4 and F5.** J8 records the sdist SHA-256 and the reading of
  `plugin.py:535-548`; J6 gives ruling (b) as its reason. Both are right.
  The legacy `U` modes of 3.10 that J6 adds give a `TextIOWrapper`, so
  they add no receiver class.
- **J1 and J3** quote the referee's rule. The four J1 edges stay out and
  the eight J3 edges stay in. **J7** now cites PyPy 3.11's `update1_pairs`.
  The status paragraph and the statistics are updated: 420 entries, 2539
  default pairs, 76 edges from reading only.
- **One wording item left (0 edges).** The `default reject` line for
  `TinyDB.__iter__`, `Table.__iter__` and `LRUCache.__iter__`
  (`tinydb.ledger:20`) is unchanged. It is still true at every site it
  decides, because the five sites now decide `TinyDB.__iter__` themselves.
  But its last clause names only the explicit `iter()` accepts. The table
  in `tinydb.md` already adds "the five document-field sites of J10".
  The writer should add that clause to the ledger line too, then run
  `check.py --write` (the generated files do not hold default reasons).

Nothing else changed against the audited ledger.
