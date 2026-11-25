# more-itertools: judgements of the ground truth

Release v11.2.1 (commit `4aeb433`). Analysed source: `more_itertools/`
(`__init__.py`, `more.py`, `recipes.py`): 3 modules, 291 functions (11
lambdas), 15 classes. The `*.pyi` stubs and `py.typed` are not analysed, but
the stubs count as annotations (README, B4). `pyproject.toml` sets
`requires-python = ">=3.11"`; the classifiers and the CI matrix
(`.github/workflows/python-app.yml:11`) name CPython 3.11 to 3.15 and PyPy
3.11. Normal, `-O` and `-OO` execution are included; the assertions of
`_shift_to_odd` and `_strong_probable_prime` (`recipes.py:1204`, `1209`) hold
no package call, so they change no edge.

The ledger is `more-itertools.ledger`; the graph `more-itertools.json` is
generated from it. 27 trace edges are rejected in
`more-itertools.rejected.json` (below).

The writer drafted the entries with scratch tools of its own: a guess of the
outside callee of each plain name call (an import, a builtin or a package
function), and a short form for the role callees below, expanded into
callee lines. Every entry was decided by hand against the source; the guess
was kept only where it was right.

## The iterable role (the main judgement)

Almost every public function takes an iterable, and the package defines ten
iterator and sequence classes. Which package objects can reach an iterable
parameter decides about three quarters of the graph: 2815 of the 3814 edges
go to `__iter__`, `__next__`, `__len__`, `__bool__` or `__getitem__` of
these classes. The writer asked the lead; an independent referee gave the
ruling, which the lead adopted (README, "Rulings for batch 6",
"Declared iterable types"; the referee's record is
`ruling-more-itertools-roles.md`, an audit record). A second ruling, on the narrower contracts, followed the blind
audit (`more-itertools.audit.md`, F1 and F2; the referee's record is
`ruling-more-itertools-contracts.md`, an audit record). The
ledger applies both as follows.

**One ordinary source-iterable role.** The documentation offers the
functions as building blocks that a client composes (`README.rst:7-10`;
`docs/api.rst:270`, wrapping; `more.py:5502-5503`, "Existing itertools and
more-itertools can be wrapped"); the package composes them itself
(`intersperse` passes `chunked` to `interleave`, `strip` passes `lstrip` to
`rstrip`, `replace` passes `windowed` to `consume`, `seekable.seek` passes
the `seekable` to `consume`, `more.py:3155`).

**Members.** For annotation matching, an explicit base in the shipped stubs
counts as a declared base (the ruling). `numeric_range` and `SequenceView`
subclass `collections.abc.Sequence` at run time (`more.py:2266`, `2943`).
The stubs declare `peekable`, `sized_iterator`, `islice_extended`,
`seekable`, `time_limited`, `callback_iter`, `countable` and `serialize` as
`Iterator[_T]` (`more.pyi:194`, `218`, `588`, `635`, `714`, `778`, `830`,
`1007`). The `_concurrent_tee` objects that the public `concurrent_tee`
returns are members too (factory outputs: the docstring passes them to
`serialize`, `more.py:5535-5537`); no other `_concurrent_tee` is
considered. `bucket` is not a member: its stub base is `Container`
(`more.pyi:259`), and the test that passes a bucket's value to `take` passes
a child iterator (`test_more.py:1084`, `take(3, D[1])`), a package
generator.

**Evidence of instances passed on** (documentation, docstrings, tests; the
lead asked for it):

| Class | Passed to another package function as an iterable |
|---|---|
| `numeric_range` | none found (a member by its run-time `Sequence` base; for numeric and index inputs by its documented purpose, `more.py:2266-2299`) |
| `SequenceView` | none found (a member by its run-time `Sequence` base); `matmul` forwards a `SequenceView` matrix to `transpose` (`recipes.py:1051`); `seekable.elements` returns one (`more.py:3149`) |
| `peekable` | `extract` (`test_more.py:6925-6926`); `seekable.__init__` wraps the source in one (`more.py:3102`) |
| `seekable` | `locate` (docstring, `more.py:2583-2585`); `take` (`test_more.py:3738`); `consume` (`more.py:3155`, the package itself) |
| `islice_extended` | `islice_extended` (`test_more.py:3505-3506`) |
| `sized_iterator`, `time_limited`, `callback_iter`, `countable`, `serialize` | none found; their docstrings and tests consume them with `len`, `list`, `next`, `for` or client threads (`more.py:587-591`, `3627-3631`, `4105-4110`, `4592-4600`; `test_more.py:756`, `4469`, `4991`, `5537`, `6960`) |
| `_concurrent_tee` | the docstring says to wrap one with `serialize` (`more.py:5535-5537`); the tests pass them to client threads (`test_more.py:7103-7110`) |
| `bucket` | none: its children go to `take` (`test_more.py:1084`) and `next` |

Where the documentation says these objects are meant to be passed on:
`README.rst:7-10` and `docs/api.rst:270` (composition and wrapping),
`more.py:3287-3291` (`peekable` and `seekable` as decorators of
iterator-returning functions, through `make_decorator`), `more.py:5535-5537`
(`concurrent_tee` outputs to `serialize`), `more.py:5502-5503`
(`synchronized` wraps more-itertools producers).

**What a member runs.** Admission fixes the possible values; each site
keeps only the calls that Python makes on them (the ledger header lists the
same):

| Operation on a role value `v` | Package callees |
|---|---|
| `iter(v)` (also inside `islice`, `zip`, `map`, `filter`, `enumerate`, `compress`, `takewhile`, `dropwhile`, `starmap`, `groupby`, `tee`, `cycle`, `zip_longest`, `accumulate`, `pairwise`, `itertools.batched`, `chain.from_iterable`, `deque.extend`) | the `__iter__` of the nine iterator classes (each returns `self`), `numeric_range.__iter__`; a `SequenceView` gets the library `Sequence.__iter__` generator, so obtaining its iterator calls no package code |
| `iter()` of an iterator that came from `iter(v)` | the nine `__iter__` only |
| advancing (`next`, `for`, `yield from`, `list`, `sum`, `deque`, ...) | the nine `__next__`, and `SequenceView.__getitem__` (through `Sequence.__iter__`); the `takewhile` of `numeric_range.__iter__` calls no package code |
| `len(v)`, and the length hint of `list()`, `tuple()`, `sorted()`, `str.join`, `f(*v)`, `[*v]`, `itertools.product` | `numeric_range.__len__`, `SequenceView.__len__`, `sized_iterator.__len__` |
| truth test | `numeric_range.__bool__`, `peekable.__bool__`, `seekable.__bool__`; `__len__` of `SequenceView` and `sized_iterator` |

## Contracts

Narrower contracts keep a separate purpose requirement (the second ruling):
specialising the item type of an outside `Iterable` annotation does not by
itself admit every member of the ordinary source-iterable role. Run-time and
stub-declared bases are treated alike. The writer sorted every iterable
parameter by its stub annotation (`more.pyi`, `recipes.pyi`) and gave each
kind this contract:

| Kind (stub annotation) | Parameters | Package classes admitted | Why |
|---|---|---|---|
| Ordinary source iterable: `Iterable[_T]`, `Iterator[_T]`, `Iterable[Any]`, `_T \| Iterable[_T]` | the data input of every other function (`iterable`, `seq` of `windowed`, `*iterables`, `element`, `substitutes`, `xs`, `ys`, `vec1`, `vec2`, `signal`, `kernel`, `iterator` of `consume`, `obj` of `zip_broadcast`, `args` of `value_chain`, the matrix of the tuple-shape `reshape`) | all eleven members | the first ruling; the items are unconstrained. `dotproduct`, `convolve` and `sum_of_squares` are documented as numeric, but their stubs say `Iterable[_T]`, and the annotation decides (B2) |
| Sequence: `Sequence[_T]`, `Sequence[complex]` | `substrings_indexes`, `SequenceView.__init__`, the items of `unzip`, `dft`, `idft`, `polynomial_from_roots`, `polynomial_eval`, `polynomial_derivative` | `numeric_range`, `SequenceView` | being a sequence is a property of both classes, which the first ruling names as the package's sequences; the numeric sequences take a compatible `numeric_range` |
| Matrix: `Sequence[_T]` of rows | `m1`, `m2` of `matmul` (`recipes.py:1039`, "Multiply two matrices") | `SequenceView` only | a `numeric_range` holds numbers, not rows; a `SequenceView` of a list of rows fits |
| Numbers or indices: `Iterable[int]`, `Iterable[int \| None]`, `Iterable[float]`, `Iterable[_NumberT]` | `sizes` (`split_into`), `key_list` (`sort_together`), `indices` (`extract`), `weights` and `counts` (`sample`, `_sample_weighted`, `_sample_counted`), `shape` (`reshape`), the data of `running_min`, `running_max`, `running_mean`, `running_median`, `running_statistics` | compatible `numeric_range` objects only | the purpose requirement: `numeric_range` is documented as a producer of numeric ranges (`more.py:2266-2299`), so it serves these roles (integer ranges for sizes, counts, indices and dimensions; numeric ranges for weights and data; a datetime range does not satisfy a numeric contract). `SequenceView` and the nine iterators can carry numbers, but nothing documents or passes them for these purposes |
| Outer iterable of iterables, tuples or mappings: `Iterable[Iterable[_T]]`, `Iterable[Sequence[_T]]`, `Iterable[tuple[_T, int]]`, `Iterable[Mapping[str, Any]]` | the outer iterable of `sort_together`, `longest_common_prefix`, `flatten`, the int-shape `reshape`, `unzip`, `run_length.decode`, `doublestarmap` | none | the purpose requirement: no documentation or test passes a member as such a container |
| The same, at `transpose` | `matrix` of `transpose` (`recipes.py:963`) | `SequenceView` | package forwarding counts in full (B2): `matmul` passes its matrix `m2`, which can be a `SequenceView` of rows, to `transpose` (`recipes.py:1051`); this passage admits the class at `transpose` only |
| Inner iterables of the outer kinds | the inner `Iterable[_T]` of the rows above; the inner `Sequence[_T]` of `unzip` | inner `Iterable[_T]`: all eleven members; inner `Sequence[_T]`: `numeric_range`, `SequenceView`; inner tuples and mappings: none (client values) | each inner iterable is consumed as an ordinary source (or a sequence); the annotation decides |
| `list[Iterable[_T]]` | `interleave_evenly` | the outer is a list; the inner iterables: all eleven members | a concrete outer type (B4) |
| Protocols: `SupportsGetItem[slice, _T]`, typeshed `Viewable` | `seq` of `sliced`, `offsets` of `stagger` and `zip_offset` | none | no package class declares these bases |
| `object`; `AbstractContextManager[Iterable[_T]]`; `Callable[..., Iterator[_T]]` | `always_iterable`'s `obj`; `with_iter`'s `context_manager`; `synchronized`'s `func` | none | `object` and a bare callable name no package value (B2); no package class declares `AbstractContextManager`, and what a client's `__enter__` returns is a client value (B5) |

So where a numeric or index iterable is consumed, the ledger names only
`numeric_range.__iter__` and, for a length hint, `numeric_range.__len__`;
advancing its iterator (a `takewhile`) calls no package code, so the sites
that only advance one keep a note and no package callee (`split_into`,
`more.py:1774`; `sort_together`, `2008`, `2012`; `sample`, `4039`, `4043`;
`_sample_weighted`, `3898`; `_sample_counted.feed`, `3943`; `extract`,
`5442`, `5447`; `_extract_monotonic`, `5385`; `reshape`, `recipes.py:1033`;
the `running_*` functions and their helpers, `recipes.py:1346-1589`). The
four `read()` sites of the `running_median` helpers keep
`itertools.takewhile.__next__` (the iterator of a `numeric_range`) and
`itertools._tee.__next__` (the tees of `running_statistics`). Where the outer
iterable of an iterable of iterables is unpacked, only `transpose` names
`SequenceView.__getitem__` and `SequenceView.__len__` (`recipes.py:972`);
`sort_together` (`more.py:2026`), `longest_common_prefix` (`2612`),
`doublestarmap` (`5272`) and `run_length.decode` (`3193`) name none.

## Applying the role

**Lazy objects.** A lazy library object that a function returns (an
`islice`, `zip`, `map`, `chain`, ...) is advanced by the client: only what
its construction calls is an edge of the function, and a package callback
stored in it is no edge there (`chunked -> take` at `more.py:237`;
`outer_product.<lambda1>` at `5115`; `tabulate`, `repeatfunc`). Where
package code advances it, the edge is the advancing function's:
`chunked.ret` and `side_effect` call `take` through `chunked`'s callable
iterator (`more.py:243`, `1524`); `_batched` (3.11 and 3.12) calls
`outer_product.<lambda1>` and, on 3.11, `dotproduct` through the starmaps
that `outer_product` and `matmul` pass (`recipes.py:946`). A generator
expression is code of its function: `longest_common_prefix -> all_equal`
(`more.py:2612`), `run_length.encode -> ilen` (`3189`), and the `@NEXT`
edges of `groupby_transform`, `duplicates_justseen` and
`substrings_indexes`. Where one function builds and advances a lazy object,
the ledger puts the construction callees at the building call and the
advancing callees at the consuming site; the edge set is the same.

**Items.** The items of a client iterable are client values (B3), unless the
annotation makes them iterables or sequences: `flatten`, `sort_together`,
`longest_common_prefix`, `transpose` and the `int` overload of `reshape`
take `Iterable[Iterable[_T]]`; `unzip` takes `Iterable[Sequence[_T]]`
(`more.pyi:431`), so `len(head)` (`more.py:2058`) and `iter_suppress`'s
advancing of `map(itemgetter(i), it)` (`5138`) reach `numeric_range` and
`SequenceView`.

**The package's own values count in full** (B2): `last` advances the
`islice` of `nth_or_last` and the `enumerate` of `combination_index`, so a
`SequenceView` reaches its `deque` branch (`more.py:295`); the
`running_median` helpers advance the `tee` objects of `running_statistics`
(`itertools._tee.__next__`, `recipes.py:1346`); `iter_index` gets the
`bytearray` of `sieve` (`<builtin>.bytearray.index`, `recipes.py:908`).

## Scope rules

**A.** Every function keeps the edges of its body. `dl_split`, `dl_mul`,
`_fsumprod` (`more.py:194-212`), `_batched` and
`_running_median_minheap_only` ran in no test (they are the functions of
older Python versions, below), and keep their edges.

**B1.** `peekable.__bool__` calls `peekable.peek`, not `seekable.peek`;
`seekable.peek` calls `self._source.peek` only when `_maxlen_zero`, where
`_source` is a `peekable` (`more.py:3102`, `3136`). `bucket.__contains__`
subscripts `self`, a `bucket` (`1195`). No package class subclasses another
package class except through `Sequence` and `BaseException`.

**B2, B4.** See the role. Other parameters:
- Callbacks (`pred`, `key`, `func`, `keyfunc`, `validator`, ...) are client
  callbacks: the documentation passes lambdas and builtins, which a client
  passes. Package values passed by the package's own code count:
  `nth_prime` passes `is_prime` to `first_true` (`first_true ->
  is_prime`, `recipes.py:585`); `distinct_combinations` passes
  `itemgetter(1)` to `unique_everseen` (`operator.itemgetter.__call__`,
  `recipes.py:502`); `strictly_n`'s default lambdas call `raise_`.
- `make_decorator`'s `wrapping_func` (`more.py:3314`): the docstring passes
  `chunked`, `filter` and `peekable` and names `seekable`
  (`3269`, `3279`, `3287-3291`); the tests pass `seekable`
  (`test_more.py:4087`). Callees: `chunked`, `peekable.__init__`,
  `seekable.__init__`; `filter` and `islice` are client callbacks from
  outside the package.
- `synchronized`'s `func` (`more.py:5522`) is annotated
  `Callable[..., Iterator[_T]]`; the docstring says "Existing itertools and
  more-itertools can be wrapped" but names no package function (its example
  is `itertools.count`). A bare callable names no package value: client
  callback.
- `always_iterable`'s `obj` is annotated `object` (`more.pyi:434`): it
  names no package value, so `iter(obj)` (`more.py:2172`) has no role
  callee.
- `sliced`'s `seq` is `SupportsGetItem[slice, _T]` (`more.pyi:301`), a
  typeshed Protocol: no package class subclasses it, so `seq[i : i + n]`
  (`more.py:1555`) has no callee. `stagger`'s and `zip_offset`'s `offsets`
  are `Viewable` (typeshed, a Protocol): no callee.
- `with_iter`'s `context_manager` (`more.py:579`):
  `AbstractContextManager[Iterable[_T]]`; `callback_iter` is a context
  manager, but its stub base is `Iterator` only, and no code, test or
  example passes one to `with_iter`. Rejected; what its `__enter__` returns
  is a client value (B5).
- `join_mappings`' mappings are `Mapping` (`more.pyi:983`): abstract, no
  callee for `mapping.items()` (`more.py:5190`).
- `numeric_range.__init__` calls the class of the client's numbers
  (`type(self._stop)(0)` and the like, `more.py:2325-2341`). The docstring
  names `int` (the default), `float`, `Decimal`, `Fraction`, and
  `datetime` start and stop with a `timedelta` step (`2273-2316`). B4 names
  these: `<builtin>.int`, `<builtin>.float`, `decimal.Decimal`,
  `fractions.Fraction`, and `datetime.timedelta` for the step's class at
  `2341` only. `datetime.datetime(0)` (one datetime argument) is outside
  the documented contract and has no edge. `polynomial_eval`'s
  `type(x)(0)` (`recipes.py:1124`) adds `<builtin>.complex` ("Supports all
  numeric types: int, float, complex, Decimal, Fraction").
- `powerset_of_sets`' `baseset` is annotated `type`: only the default
  `set` is a callee (`more.py:5172`).

**B3.** The items of client iterables are not considered as package objects:
this decides the defaults on `numeric_range.__eq__`, `__hash__` and the
`__repr__` of `numeric_range` and `SequenceView` at comparisons, `in` tests,
set and dict keys and formats of items.

**B5.** Client callbacks and the objects they return are opaque: `consumer`
and `iterate` (`more.py:514`, `563`), the client's `f` in
`make_decorator` (`3311`), `callback_iter`'s client function (run by a
`ThreadPoolExecutor` thread that the library starts; it calls the package
closure `_reader.callback`, a client call with no package edge). The
methods of client sequences in `iter_index` (`seq_index`, `recipes.py:908`)
and of client iterators in the `running_median` helpers (`read`,
`recipes.py:1346`) have no callee; the trace edges of the tests' lists and
strings are rejected.

**C.** Public: everything in the two `__all__` lists (re-exported by
`__init__.py`) and their methods. Private by name: `_islice_helper`,
`_sample_*`, `_extract_*`, `_concurrent_tee`, `_complex_sumprod`,
`_nth_prime_bounds`, `_full_period_lcg`, `_random_ordered_indices`, and the
recipe helpers that start with `_`; their parameters are what the package
passes.

## Judgement calls

1. **The iterable role and the contracts** (above): the referee's two
   rulings, adopted by the lead; the sorting of the parameters into kinds is
   the writer's application of them.
2. **Version branches** (supported: 3.11 and later).
   - `math.sumprod` is new in 3.12. On 3.11 `more.py:188-212` defines
     `dl_split`, `dl_mul` and `_fsumprod`, and `recipes.py:298` binds
     `_sumprod` to `dotproduct`. So `_complex_sumprod` calls `math.sumprod`
     and `more._fsumprod` (`more.py:5207`), and `convolve`,
     `polynomial_eval` and `sum_of_squares` call `math.sumprod` and
     `recipes.dotproduct` (`recipes.py:749`, `1126`, `1137`).
   - `itertools.batched` is used from 3.13.0a2 (`recipes.py:952`): every call
     of `batched` names `recipes.batched` and `recipes._batched`
     (`more.py:5114`, `5634`; `recipes.py:1032`, `1035`, `1051`).
   - The max-heap functions of `heapq` exist from 3.14 (`recipes.py:105`):
     `running_median` calls `_running_median_minheap_only` on 3.11 to 3.13
     and `_running_median_minheap_and_maxheap` from 3.14
     (`recipes.py:1420`, `1422`); the latter names `heapq.heappush_max` and
     `heapq.heappushpop_max`.
   - `__lazy_modules__` (`more.py:1`) only makes two imports lazy on 3.15;
     an import adds no edge.
3. **A call that cannot bind** (`recipes.py:908`): on the fast path of
   `iter_index`, `seq_index` is the `index` method of the iterable. For a
   `numeric_range`, `numeric_range.index(self, value)` gets three
   arguments and raises `TypeError` before it runs: no edge (an `exclude`
   line records it). For a `SequenceView` the method is the inherited
   `collections.abc.Sequence.index`, which calls `SequenceView.__getitem__`
   and, for a negative start or stop, `SequenceView.__len__`.
4. **`divide`** (`more.py:2106`): `iterable[:0]` works on `numeric_range`,
   `peekable`, `islice_extended`, a `SequenceView` whose target slices, and
   a `seekable` whose cache is a list (`maxlen` None). A `seekable` with
   `maxlen` keeps a `deque` (`3107`), which refuses the slice, and so does a
   `SequenceView` of a `deque`; they and the members without `__getitem__`
   raise `TypeError` and go to `tuple(iterable)` (`seekable.__iter__` and
   `__next__`, `SequenceView.__len__` and `__getitem__`; Codex audit round
   1). A `peekable`, list-cached `seekable` or `islice_extended` then fails
   at `len(seq)` (no `__len__`).
5. **`reversed()`** (`last`, `always_reversible`, `rlocate`): only
   `numeric_range` (its own `__reversed__`) and `SequenceView`
   (`Sequence.__reversed__`, a library generator) are reversible.
   `peekable`, `seekable` and `islice_extended` have `__getitem__` but no
   `__len__`, and `sized_iterator` has `__len__` but no `__getitem__`, so
   `reversed()` raises `TypeError` for them. `last` advances the library
   generator of a `SequenceView` itself (`SequenceView.__len__` and
   `__getitem__` at `more.py:294`); `always_reversible` returns it to the
   client (no edge); `rlocate`'s generator expression advances it through
   `locate` (`3439`).
6. **`serialize.send`, `throw`, `close`** (`more.py:5480-5496`): the
   iterator is a package generator (the docstring: "Raises AttributeError if
   not a generator"; named `types.GeneratorType.send`, which the trace's
   `builtins.generator.send` matches) or a `serialize` of the role
   (`serialize.send`, its `__iter__` returns self). A client generator is a
   client object.
7. **`read()` in the `running_median` helpers** (`recipes.py:1346`, `1349`,
   `1362`, `1365`): `read` is the bound `__next__` of `iter()` of numeric
   data (`Iterable[_NumberT]`, so a compatible `numeric_range`, see
   "Contracts"): `itertools.takewhile.__next__` (the iterator of a
   `numeric_range`), and
   `itertools._tee.__next__` (the tees of `running_statistics`,
   `recipes.py:1589`; named as the tracer names the type, which has no
   public path).
8. **Calls of library wrapper objects**: `functools.partial.__call__` for
   `algorithm(...)` in `distinct_permutations` (`more.py:895`, `899`, with
   `_partial` behind it), and for the `@wraps(func)` decorators
   (`512`, `5520`); `functools._lru_cache_wrapper.__call__` and
   `_shift_to_odd` for the `lru_cache` function (`recipes.py:1211`);
   `operator.itemgetter.__call__` (`more.py:2023`, `recipes.py:502`,
   `1617`); `random.Random.randrange` for `_private_randrange`
   (`recipes.py:1273`).
9. **Instantiation of `AbortThread`** (`more.py:4186`): it defines no
   `__init__`, so the call names `<builtin>.BaseException.__init__`.
10. **`numeric_range._len`** is a `functools.cached_property`
    (`more.py:2421`): each load of `self._len` is a site whose callee is
    `_len` (its first load in a fresh object runs it). The slice of a
    `numeric_range` calls `numeric_range.__init__` (`2389`).
11. **The `strict` branch of `chunked`** (`more.py:242`): `ret` advances the
    callable iterator `iter(partial(take, n, it), [])`, so `chunked.ret`
    calls `take` (`243`); `side_effect` iterates `chunked`'s result and
    calls `take` (`1524`).

## Default rejections

Seven default lines decide 36 candidates; counted as candidate-site pairs,
they decide 13,753 pairs (the report lists each with its explicit sites).

| Candidates | Sites each | Reason (short) |
|---|---|---|
| `__getitem__` of `SequenceView`, `bucket`, `islice_extended`, `numeric_range`, `peekable`, `seekable` | 555 to 698 | the operand is a builtin or library object, a generator, or a client value outside the roles |
| the nine `__next__` (with `_concurrent_tee`) | 415 to 569 | the site advances no role value in this function |
| the eleven `__iter__` (with `bucket`, `_concurrent_tee`) | 375 to 528 | the site calls `iter()` on no role value |
| `__len__` of `SequenceView`, `numeric_range`, `sized_iterator` | 260 to 269 | the site measures, truth-tests or converts no such object |
| `__bool__` of `numeric_range`, `peekable`, `seekable` | 122 | no such object is truth-tested |
| `numeric_range.__eq__`, `__hash__` | 250, 185 | compared and hashed values are numbers, strings, tuples or client items (B3) |
| `__repr__` of `SequenceView`, `numeric_range` | 34 | formatted values are numbers, strings or client items (B3) |

Every role site accepts its callees explicitly: 270 explicit sites and 72
implicit ones (iteration, subscript and format sites, taken from the full
skeleton), with package callees of these classes. The writer
checked, per function, that every function with an `__iter__` edge and no
`__next__` edge returns a lazy object or stores the iterator, and that
every function with a `__next__` edge also has `SequenceView.__getitem__`
unless a `SequenceView` cannot reach that site (`always_reversible` and
`tail` take the other branch for it).

## Rejected trace edges

27, in `more-itertools.rejected.json`: the builtins, methods and mocks that
the tests pass as callbacks (`key=str.lower`, `int`, `sum`, `list`, `len`,
`frozenset`, a `Mock`, `l.pop`, `f.close`, `itertools.islice` as
`wrapping_func`), the `index` methods of the tests' lists and strings in
`iter_index`, the `__next__` of a test's list iterator in a
`running_median` helper, and `powerset_of_sets -> frozenset`, a builtin
that `map` calls back (no edge by the README).

## The blind audit

`more-itertools.audit.md` re-derived 201 sites blind (188 agree; the
writer's errors are F1 to F3 below) and 40 function and role-class pairs (40
agree); it found no missed edge and no call that cannot bind besides
`recipes.py:908`. Applied:

- F1 and F2 (the numeric and index iterables; the outer iterables of
  iterables) by the referee's second ruling: 27 callee lines and 13 edges
  removed. The ruling keeps `numeric_range` for the numeric and index
  inputs, and `SequenceView` at `transpose` (F2 does not hold there).
- F3: `_concurrent_tee.__next__` does not call itself (`more.py:5572`):
  `self.iterator` is never a `_concurrent_tee` (`5555-5560`). 1 edge
  removed.

## PyPy

The release supports PyPy explicitly: the classifier
`Programming Language :: Python :: Implementation :: PyPy`
(`pyproject.toml:34`) and the CI job `pypy-3.11`
(`.github/workflows/python-app.yml:11`). With `requires-python = ">=3.11"`
(`pyproject.toml:9`), PyPy 3.11 (v7.3.20) is in scope and PyPy 3.10 is not.
The writer read PyPy 3.11's sources as text (`lib-python/3`, `lib_pypy`,
`pypy/module`, and, for Codex audit round 1, `pypy/interpreter` and
`pypy/objspace`). PyPy's `length_hint` asks `len()` first and then
`__length_hint__`, as CPython does (`pypy/interpreter/baseobjspace.py:1082-1110`).
`list()`, `tuple()`, `str.join`, `f(*v)`, `itertools.product`,
`combinations` and `permutations` take the hint as on CPython. PyPy also
takes it where CPython does not: in `set()` (`pypy/objspace/std/setobject.py:1645`;
no package code builds a set from a role value), in list comprehensions
(`BUILD_LIST_FROM_ARG`, `pypy/interpreter/pyopcode.py:965-972`; no
package comprehension iterates a role value directly), in `dict.fromkeys`
(`dictmultiobject.py:129`; the package passes a `map`), and in starred
unpacking (`UNPACK_EX` uses `fixedview`, `pyopcode.py:845-851`, which
reaches `_unpackiterable_unknown_length`, `baseobjspace.py:1002-1008`).
The last one adds one edge: `first_dim, *dims = shape` in `reshape`
(`recipes.py:1033`) calls `numeric_range.__len__` on PyPy. PyPy 3.11's
`math` has no `sumprod` (`pypy/module/math/moduledef.py`), so its version
branches stay those of CPython 3.11.

Checked: the 75 of the 153 outside callees whose class or module CPython implements in C or that a fallback can replace (the names of `itertools`, `collections`, `functools`, `operator`, `heapq`, `bisect`, `threading`, `queue`, `types`, `random`, `decimal`, `fractions`, `datetime`, `time`), 13 kinds of library call-back into the package, and 4 version branches:

- Version branches (`more.py:185`, `recipes.py:105`, `295`, `952`): PyPy
  3.11 is Python 3.11, so it takes the branches of CPython 3.11 (no
  `math.sumprod`, no `itertools.batched`, no max-heap functions); no
  package branch tests `sys.implementation` or `platform`.
- `itertools` objects (`pypy/module/itertools/interp_itertools.py`): the
  type names are CPython's (`itertools.takewhile` 217, `itertools._tee`
  1021, `itertools.chain` 594, `islice`, `groupby`, `compress`, `product`,
  `combinations`, `permutations`, `accumulate`, `pairwise`, ...);
  `tee` calls `iter()` at once and copies an iterator with `__copy__`
  (888-899), and `chain.from_iterable` calls `iter()` at once (585-592), as
  CPython does. No change.
- `collections.deque` (`pypy/module/_collections`, type name
  `collections.deque`), `collections.defaultdict` (`lib_pypy/_collections.py:391`,
  a subclass of `dict`), `operator.itemgetter` and `attrgetter`
  (`pypy/module/operator/app_operator.py`, exported as `operator.*`),
  `heapq` and `bisect` (Python fallbacks of `lib-python/3`, same paths, no
  call of a package object: they compare client values), `functools.partial`
  and `reduce` (Python fallbacks, `functools.py:282-308`, `243`: same
  paths, `partial.__call__` calls `_partial` as before), `threading.Lock`,
  `queue`, `concurrent.futures`, `random`, `decimal`, `fractions`,
  `datetime`, `dataclasses`, `contextlib`, `types.GeneratorType`,
  `collections.abc.Sequence` (the same Python code): no change.
- The library call-backs into the package (`Sequence.__iter__`,
  `__reversed__` and `index`, `cached_property`, `partial`, `reduce`,
  `map`, `filter`, `starmap`, `groupby`, `takewhile`, `sorted` keys,
  `reversed()`, `pypy/module/__builtin__/functional.py:355`): the same calls.
- One difference: PyPy 3.11 has no `_functools` module (none in
  `pypy/module` or `lib_pypy`), so `functools.lru_cache` returns the closure
  `wrapper` of the Python `_lru_cache_wrapper` (`functools.py:537`, `578`,
  the import at `654` fails). `_strong_probable_prime`'s call of
  `_shift_to_odd` (`recipes.py:1211`) therefore also names
  `functools._lru_cache_wrapper.wrapper` (+1 outside edge). On PyPy,
  `functools._lru_cache_wrapper` is a function, so CPython's
  `functools._lru_cache_wrapper.__call__` is no path to the callee there.

## Statistics

| | Count |
|---|---|
| Sites | 1866 (1192 call, 9 decorator, 14 with, 235 iter, 6 mapping, 96 op, 136 getitem, 33 setitem, 5 delitem, 9 getattr, 111 truth, 20 format); 1271 with candidates; 84 value sites, each with a note |
| Ledger entries | 1318 |
| Nodes | 294 |
| Edges | 3814: 2961 in the package, 853 outside |
| Edges that the trace confirms | 968 (25.4%); 2846 from reading only |
| Trace edges rejected | 27 |
| Functions that the tests run | 286 of 291 (not run: `dl_split`, `dl_mul`, `_fsumprod`, `_batched`, `_running_median_minheap_only`: older Python versions) |

The low share confirmed by the trace comes from the role: the tests pass
lists, strings, ranges and generators, which run no package code when
iterated.

## Codex audit round 1

Missing edges (16 claimed, 16 accepted):

- `raise_ -> <builtin>.BaseException` and `-> <builtin>.BaseException.__init__`
  (`more.py:674:20`): applied. `exception` is `BaseException |
  type[BaseException]` (`more.pyi:168`, `229`); `type[BaseException]` fixes
  `BaseException` (B4) and admits the package's `AbortThread`
  (`more.py:4082`), as `Type[Sentinel]` admits every sentinel class (h11).
- The nine `yield from` delegation edges (`collapse`, `more.py:1447:24`;
  `value_chain`, `4443:24`; `iter_suppress`, `5138:20` -> `serialize.send`,
  `.throw`, `.close`): applied. A client may call `send`, `throw` and
  `close` on the generator that these functions return; `yield from` then
  calls the delegate's method in the generator's frame, an implicit call of
  a package function (micro-benchmark: every invocation counts). Every
  `yield from` site of the package, checked for consistency:
  `more.py:580` (a client object, B5), `1101` (`map`), `1447`, `1526`
  (list), `1852` (`repeat`), `2654` (list), `2784` (`islice`), `2804`,
  `2830` (lists), `3504` (tuple), `3604`, `3609` (`filter`), `4216`
  (list), `4443`, `5138`, `5636` (list); `recipes.py:406` (`map`), `926`,
  `929` (generators of `iter_index`), `1103` (list). Only `1447`, `4443`
  and `5138` can delegate to a role value, and `serialize` is the only role
  class with `send`, `throw` and `close`; a generator delegate's methods are
  outside callees at an implicit site, which the conventions exclude, and
  library iterators have none. No other site changes.
- `divide -> seekable.__iter__`, `seekable.__next__` (`more.py:2108:20`):
  applied; a `seekable` with `maxlen` caches in a `deque` (`3107`), whose
  slice raises `TypeError`.
- `locate -> <builtin>.bool` (`more.py:2601:14`): applied; the default
  `pred=bool` is a package value, called in the generator expression.
- `serialize.send -> SequenceView.__getitem__` (`more.py:5480:39`):
  applied; `send(None)` advances the `Sequence.__iter__` generator of a
  `SequenceView`.
- `tail -> SequenceView.__getitem__` (`recipes.py:158:26`): applied; a
  client target whose `__len__` raises `TypeError` sends a `SequenceView`
  to the `deque` branch (B5: client control-flow effects count).

False edges: none claimed. Naming: none.

Ruling (outputs of public factories as inputs): the lead ruled as the
auditor proposed: the eleven members stay; another factory's library
object is admitted only by a documented or tested passage or by the
package's own forwarding. No change.

Unsure (PyPy length hints): decided from PyPy's `pypy/interpreter` and
`pypy/objspace`, which the lead fetched (section "PyPy"). One edge added:
`reshape -> numeric_range.__len__` (`recipes.py:1033:24`), PyPy's starred
unpacking. Not counted as an audit missing edge.

Metadata (4): applied. `divide` `2108:20` now also lists
`SequenceView.__getitem__` and `__len__` (a view of a `deque`), and the
notes at `2106:17`, `2108:20` and judgement 4 are corrected; the note at
`2119:24` names an admitted `numeric_range` target; `tail` `158:26` now
also lists `numeric_range.__iter__` (a `_len` that fails in `divmod`);
`triplewise` `783:9` no longer lists `SequenceView.__getitem__` (the pair
stays through `781:9` and `782:9`).

Edges: 3797 (2947 inside, 850 outside) before, 3814 (2961 inside, 853
outside) after: +16 from the audit, +1 from PyPy.
