# more-itertools: blind audit of the ground truth

Release v11.2.1, commit `4aeb4338ae1407d8da9723e86da99efeb446f719` (batch 6). Audited files, as they were on 2026-11-22: `more-itertools.ledger`
(1318 entries, 7 default lines on 36 candidates), `more-itertools.json` (3810
edges: 2959 in the package, 851 outside; 294 nodes), `more-itertools.added.json`,
`more-itertools.rejected.json` (27 edges) and `more-itertools.md`.
`check.py more-itertools` reports no errors; the trace confirms 968 edges
(25.4 %), so 2842 come from reading only.

I judged the files by the README of the macro-benchmark (conventions, rules A
to C, the clarifications of 2026-11-15 and the rulings for batch 6; the
ruling "Declared iterable types" is binding and I did not re-open it). I read
the source, the `.pyi` stubs, the docstrings, `docs/api.rst`, `README.rst`,
`pyproject.toml` and the tests as data. I ran no analysis tool and did not run
or import the package. My blind answers were written before I opened any
writer file:
`$TMPDIR/audit-more-itertools/blind-answers.md` (contract table,
operation table, 201 sites). The scripts of the comparisons are in
`$TMPDIR/audit-more-itertools/work/`.

## Summary

- 201 sites re-derived blind: 13 disagree. 8 are my errors (missed or wrong
  callees), 4 are my reading of the inner iterables, which I withdraw (the
  writer follows the ruling), and 5 are writer callees that the rules do not
  support (finding F1; 4 of these sites also carry one of my errors).
- The second sample (40 function and role-class pairs): 40 agree, 0 disagree.
- Findings: F1 and F2 (medium, 19 + 5 edges, one rule decides both, the lead
  decides), F3 (minor, 1 edge that cannot happen). No missed edge found.
- The binding check finds no call that cannot bind besides the one the writer
  records (`recipes.py:908`).

## Findings

| Id | Severity | Kind | Edges | Evidence | Proposed decision |
|---|---|---|---|---|---|
| F1 | medium (needs the lead) | writer callees that the rules do not support | -19 (15 in the package, 4 outside); 40 callee lines at 24 sites | The ledger admits `numeric_range` and `SequenceView` for the numeric and index parameters: `sizes` (`more.py:1774`), `key_list` (`2008`, `2012`), `weights` and `counts` (`4039`, `4043`, `3898`, `3943`), `indices` (`5442`, `5447`, `5385`), `shape` (`recipes.py:1033`) and the data of `running_mean`, `running_median`, `running_min`, `running_max`, `running_statistics` and their six helpers (`recipes.py:1346-1589`). Its reason is the run-time `Sequence` base (`more-itertools.md`, "Contracts"). See "The flagged judgement" below: B2 admits a subclass of an outside abstract type "only for a role for which the package implements that type" (the marshmallow `OrderedSet` precedent), and no code, test or document passes either class in these roles. The ruling's first sentence also makes a stub-declared base equal to a declared base for annotation matching, so the run-time base gives `numeric_range` and `SequenceView` no advantage over the eight iterators. | remove the 19 edges (list below), or keep them by a ruling of the lead |
| F2 | medium (needs the lead; same rule as F1) | writer callees that the rules do not support | -4, and -1 more together with F1 (`sort_together -> SequenceView.__len__`); 7 callee lines at 4 sites | The outer iterable of `Iterable[Iterable[_T]]`, `Iterable[tuple]` and `Iterable[Mapping]` admits `SequenceView` by its run-time base: `sort_together` `*iterables` (`more.py:2026:22`), `longest_common_prefix` `*iterables` (`2612:52`), `transpose` `*matrix` (`recipes.py:972:16`), `doublestarmap` (`more.py:5272:17`). The same argument as F1: the ruling lists "an iterable of iterables" as a narrower contract, and nothing passes a `SequenceView` of iterables there. | remove `doublestarmap -> SequenceView.__getitem__`, `longest_common_prefix -> SequenceView.__len__`, `transpose -> SequenceView.__getitem__`, `transpose -> SequenceView.__len__`, and with F1 `sort_together -> SequenceView.__len__` |
| F3 | minor | edge that cannot happen | -1 | `more.py:5572:35` `next(self.iterator)` in `_concurrent_tee.__next__` lists `_concurrent_tee.__next__`. `self.iterator` is always `iter()` of a value that is not a `_concurrent_tee`: `__init__` copies `iterable.iterator` when it gets a `_concurrent_tee` (`5555-5558`) and calls `iter(iterable)` only otherwise (`5560`). The writer's own note at `5560` says so ("a `_concurrent_tee` takes the other branch"), and `_concurrent_tee.__init__` correctly lacks `_concurrent_tee.__iter__`. No package `__iter__` returns a `_concurrent_tee`. | remove `_concurrent_tee.__next__ -> _concurrent_tee.__next__` (an added edge, not traced) |
| R1 | remark (README) | the ruling is unclear | none | "Narrower input contracts still apply (a sequence-only input, numeric data, an iterable of indices, an iterable of iterables)" does not say which members a narrower contract keeps. The writer and I read it three ways for the numeric roles (below). One sentence in the ruling would close it. | add the lead's decision on F1 and F2 to the ruling |
| R2 | remark (README, tools) | limit of the site finder | none | The finder proposes role candidates only at calls of builtins. Role calls also happen at calls of `itertools` functions (`islice`, `tee`, `groupby`, `compress`, `product`, ...), of `deque`, `dict.fromkeys`, `math.sumprod`, and at length hints of `sorted`, `*x` and `[*x]`. 123 sites have package callees that are not candidates; the writer found them by hand, and I found no further one. "Limits of the site finder" names only the `map` and `filter` case. | add a sentence to "Limits of the site finder" |
| R3 | remark (count) | the lead's estimate | none | The brief estimates "about 60 edges" for the writer's flagged judgement. I count 19 graph edges (40 callee lines) for the numeric and index parameters, and 24 with F2. | none |

The 19 edges of F1: `extract -> SequenceView.__getitem__`;
`sort_together -> numeric_range.__len__`; `reshape -> SequenceView.__getitem__`,
`numeric_range.__iter__`; `running_max`, `running_mean`, `running_median`,
`running_min`, `running_statistics -> numeric_range.__iter__` (5);
`_running_median_windowed`, `_windowed_running_max`, `_windowed_running_mean`,
`_windowed_running_min -> SequenceView.__getitem__` (4);
`_running_median_minheap_and_maxheap` and `_running_median_minheap_only` each
`-> SequenceView.__getitem__`, `itertools.takewhile.__next__`,
`types.GeneratorType.__next__` (6). Every other numeric-role callee is also
given by an ordinary iterable of the same function, so it stays. All 25 edges of
F1 to F3 are added edges (reading only); none is traced.

## The flagged judgement (numeric and index iterables)

The writer admits `numeric_range` and `SequenceView` for `Iterable[int]`,
`Iterable[int | None]`, `Iterable[float]`, `Iterable[_NumberT]` and the
`Iterable[int]` shape, "by their run-time `Sequence` base". Three readings:

| Reading | Rule | Edges |
|---|---|---|
| A (my recommendation): no member | B2: an outside abstract type "names a package class only if the class subclasses it or is registered with it, ... and only for a role for which the package implements that type" (marshmallow: `OrderedSet` is a set, yet not for the `AbstractSet` arm of `partial` or `schemes`, where nothing passes one). The ruling established the ordinary role from the documentation and composition examples and says that narrower contracts still apply; for sizes, offsets, indices, weights, counts, shape and numeric data no code, test or document passes any member. | -19 (F1), and -5 with F2 |
| B (the writer): `numeric_range` and `SequenceView` | B2's subclass clause alone, with the run-time base counted above the stub base | as now |
| C: every member that can hold numbers (the eleven) | the ruling's first sentence: a stub-declared base counts as a declared base for annotation matching, so `peekable` (`Iterator[_T]`) matches `Iterable[int]` as well as `numeric_range` (`Sequence`) does | about +160 (my estimate: `__iter__` and `__next__` of the nine iterators in the five `running_*` functions, their six helpers, `extract` and `reshape`) |

Reading B is the one that no README sentence supports: the ruling's first
sentence makes stub bases and declared bases equal, so a rule that admits the
two sequences by their base must admit the eight stub-declared iterators too
(reading C). Reading A is the smaller extension of the existing rules (B2's
role clause, as for marshmallow). The ruling's parenthesis does not decide
between A and C in words (R1). Because about 20 to 160 edges of batch 6
depend on it, the lead may want the referee to rule; I recommend A for F1 and
F2.

The same question for the sequence-only parameters (`substrings_indexes`,
`SequenceView.__init__`, `dft`, `idft`, `polynomial_*`, the items of `unzip`,
`matmul`) has a clear answer: being a `Sequence` is a property of the class,
and the ruling names the two sequences as members, so a sequence-only input
keeps `numeric_range` and `SequenceView` (the writer; my blind table agrees).
Numeric or index content is a property of the client's items, which no member
fixes by its type.

## Step 1: blind re-derivation

**Sample.** Skeleton from a scratch benchmark directory (copy of
`projects.toml` and of the source), 1866 sites; numbered by module (skeleton
order), line, column and kind. 1105 sites have a role-class candidate, so I
drew by kind of site and by role candidate, with `random.Random(20261122)`, in
this order: role-candidate explicit 20, role-candidate implicit 30, explicit
without a role candidate 16, implicit without one 4 (70). Among the 50
role-candidate sites a role class can arrive at 16 only, so the same generator
then drew role-candidate sites in reserve (R1 to R47, kept in draw order) until
25 sites where a role class arrives were reached. Then all 84 value sites.
Total 201 sites: a role class arrives at 25 role-candidate sites (and at 2 sites
without a candidate, `more.py:3886:34` and `2931:15`); at 65 role-candidate sites
no role class can arrive; 7 depend on a contract reading.

| Group | Sites | Agree | Disagree |
|---|---|---|---|
| Role candidate, explicit and implicit (50) | 50 | 47 | 3 (#12, #17, #43) |
| Reserve role-candidate sites | 47 | 44 | 3 (R21, R30, R31) |
| Without a role candidate | 20 | 20 | 0 |
| Value sites | 84 | 77 | 7 |
| **Total** | **201** | **188** | **13** |

Classification of the 13:

- **I was wrong (8 sites).** `recipes.py:585:16` `next(filter(pred, iterable), default)`:
  I missed `recipes.is_prime`, which `nth_prime` passes as `pred`
  (`more.py:5318`). `more.py:2329:56` `type(self._stop - self._start)(1)`: I
  added `datetime.timedelta`, but the docstring admits datetimes only with a
  `timedelta` step (three arguments), so the two-argument form with datetimes is
  out of contract. `recipes.py:1126:20` `_sumprod(coefficients, powers)`: I
  missed `numeric_range.__iter__` and `SequenceView.__getitem__` (`math.sumprod`
  iterates the sequence-only coefficients). `recipes.py:1137:20`
  `_sumprod(*tee(iterable))`: I missed the nine `__next__` and
  `SequenceView.__getitem__` (`math.sumprod` advances the two tees). The four
  `read()` sites (`recipes.py:1346:50`, `1349:50`, `1362:47`, `1365:48`): I
  missed `itertools._tee.__next__`, the package's own tees of
  `running_statistics` (`recipes.py:1589`).
- **My reading of the inner iterables, withdrawn (4 sites).** `recipes.py:972:15`,
  `more.py:2612:51`, `2612:27`, `2027:23`. I had not admitted the members as the
  inner iterables of `Iterable[Iterable[_T]]`. The inner annotation is a generic
  `Iterable[_T]`, which the ruling makes the ordinary role ("fit generic iterable
  inputs"), and B2 lets the annotation decide. The writer is right. 73 edges
  depend on this reading (50 for `sort_together`, `longest_common_prefix`,
  `transpose`, `unzip` and `iter_suppress`'s `numeric_range.__getitem__`, 23 for
  the list items of `interleave_evenly`); I report them for completeness, not as a
  finding.
- **Writer callees that the rules do not support (5 sites; F1).**
  `more.py:5385:18` (`SequenceView.__getitem__` for `indices`), and the
  `SequenceView.__getitem__`, `itertools.takewhile.__next__` and
  `types.GeneratorType.__next__` callees of the four `read()` sites.
- **Naming only (0). The writer missed an edge (0).**

Placement only (same edges in the function, no disagreement counted): at
`more.py:4843:32` I placed the advancing of `enumerate(iterable)` at the loop;
the iteration of `enumerate()` is no site, and the writer places it at the call,
as the README says. At `recipes.py:604` the writer places the inner `tuple` calls
at the outer `tuple(...)` (604:18); I had allowed either.

## Item 1a: the contracts, compared

My table (blind file, section 1) against the writer's ("Contracts" in
`more-itertools.md`):

| Parameters | Writer | Me (blind) | Edges that depend on the difference | Final view |
|---|---|---|---|---|
| ordinary source iterables (about 150 parameters) | the eleven | the eleven | 0 | agree |
| `dotproduct`, `convolve`, `sum_of_squares` (numeric by use, `Iterable[_T]` in the stubs) | ordinary | ordinary (flagged) | 0 | agree: the annotation decides |
| sequence-only (`substrings_indexes`, `SequenceView.__init__`, `dft`, `idft`, `polynomial_from_roots`, `polynomial_eval`, `polynomial_derivative`) | `numeric_range`, `SequenceView` | the same | 0 | agree |
| `matmul` `m1`, `m2` | `SequenceView` only | both sequences | 3 (my reading would add `matmul -> numeric_range.__len__`, `__iter__`, `__getitem__`) | the writer is right: a `numeric_range` holds numbers, not rows (out of contract) |
| `sliced.seq` (`SupportsGetItem`), `stagger`/`zip_offset` `offsets` (`Viewable`) | none (Protocols) | none | 0 | agree |
| `always_iterable.obj` (`object`), `with_iter.context_manager`, `synchronized.func` | none | none | 0 | agree |
| numbers and indices: `split_into.sizes`, `sort_together.key_list`, `sample.weights`, `sample.counts`, `extract.indices`, `reshape.shape`, the data of the five `running_*` | `numeric_range`, `SequenceView` | none | 19 (F1) | F1 |
| `interleave_evenly.lengths` (`list[int]`) | none | none | 0 | agree |
| outer of an iterable of iterables, tuples or mappings (`sort_together`, `longest_common_prefix`, `flatten`, `transpose`, `reshape` with an int shape, `unzip`, `run_length.decode`, `doublestarmap`) | `SequenceView` | none | 4, and 1 shared with F1 (F2) | F2 |
| inner `Iterable[_T]` of those, inner `Sequence[_T]` of `unzip`, the list items of `interleave_evenly` | the eleven; the two sequences for `unzip` | none | 73 | the writer is right (withdrawn above) |
| `collapse` (`Iterable[Any]`: outer ordinary, nested nodes client values) | the same | the same | 0 | agree |

## Item 1b: operations and special methods, compared

My operation table (blind file, section 2) and the writer's (ledger header and
`more-itertools.md`) agree on every class: `iter()` reaches the nine
`__iter__` and `numeric_range.__iter__`, not `SequenceView` (the library
`Sequence.__iter__`); advancing reaches the nine `__next__` and
`SequenceView.__getitem__`, not `numeric_range`; length and length hints reach
the three `__len__`; truth reaches the three `__bool__` and the `__len__` of
`SequenceView` and `sized_iterator`; `reversed()` reaches only
`numeric_range.__reversed__` and, on advancing, `SequenceView.__len__` and
`__getitem__`; subscripts reach the five `__getitem__` (`divide`, judgement 4);
`iter()` of an iterator that came from `iter(v)` reaches the nine `__iter__`
only. One difference, my error without an edge effect: I wrote that
`chain.from_iterable(x)` calls nothing until it is advanced; CPython calls
`iter(x)` at once (the writer's table is right). No parameter of the ordinary
role goes to `chain.from_iterable` directly.

Checks of the application against the table:

- Sites where a role class cannot arrive: 65 of my sample, all decided as I did
  (the writer's default rejections or `reject *`).
- A consistency scan of every node of the graph: for each function, the nine
  iterators have the same `__iter__` and `__next__` callees unless a branch
  separates them, `SequenceView.__getitem__` comes with `__next__`,
  `numeric_range.__iter__` comes with the nine `__iter__`, and the three
  `__len__` come together. Every exception has a reason in the source: the
  iterator of an iterator (`_islice_helper`, `_sample_*`, `_extract_*`,
  `partition.gen`, `padded.slice_generator`, `zip_broadcast`,
  `bucket.__iter__`, `peekable.__getitem__`); the branches of
  `always_reversible`, `last`, `tail`, `divide` and `rlocate`; the length hint of
  `[item, *it]` and `list(it)` that reaches `sized_iterator.__len__` only
  (`split_before`, `split_when`, `split_into`); the sequence-only and matrix
  contracts; F1 and F2. The one inconsistency is F3.
- 33 functions call `__iter__` without `__next__`; each returns a lazy object,
  stores the iterator, or hands it to a function that advances it. 12 call
  `__next__` without `__iter__`; each advances a stored iterator.
- No package code truth-tests, compares, hashes or formats a role value of an
  ordinary parameter, so the `__bool__`, `__eq__` and `__hash__` of the members
  have no caller, as in the graph.

## Item 3: the second sample, 40 function and role-class pairs

The cross product of the 121 public functions that take an ordinary source
iterable (my section 1, module-level functions and `run_length.encode`) and the
eleven members (1331 pairs); `random.Random(20261122).sample(pairs, 40)`. For each
pair I derived the special-method callees of that class in that function from
the source, then compared with the graph.

Result: 40 agree, 0 disagree. The pairs: random_product/peekable,
pad_none/peekable (none: `chain` is lazy), circular_shifts/sized_iterator (no
`__len__`: `deque` takes no length hint), subslices/countable,
unique_in_window/countable, triplewise/numeric_range (`__iter__` only),
strictly_n/_concurrent_tee, windowed/countable, subslices/SequenceView
(`__getitem__`, `__len__`), duplicates_everseen/peekable, nth_or_last/islice_extended
(`__iter__` only; `last` advances), adjacent/numeric_range, iter_suppress/sized_iterator,
all_equal/serialize, nth/serialize, run_length.encode/islice_extended (the
generator expression advances: `__next__`), iter_index/countable,
combination_with_replacement_index/time_limited, map_except/serialize,
classify_unique/islice_extended, grouper/sized_iterator (`__iter__` only),
partitions/serialize, dotproduct/sized_iterator, concurrent_tee/_concurrent_tee
(`__init__` only), iequals/serialize, nth_permutation/serialize,
repeat_each/countable (`__iter__` only), duplicates_everseen/numeric_range,
dotproduct/countable, permutation_index/serialize, convolve/countable,
iter_suppress/islice_extended, prepend/time_limited (none),
difference/_concurrent_tee, iter_index/SequenceView (`__len__`, `__getitem__`
through `Sequence.index`), unique_justseen/islice_extended (`__iter__` only),
ichunked/_concurrent_tee, random_combination/callback_iter,
consecutive_groups/_concurrent_tee, all_equal/time_limited.

## Step 2: the other exhaustive checks

- **Dispatch sets (B1).** The only package hierarchies are `numeric_range` and
  `SequenceView` under `Sequence` and `AbortThread` under `BaseException`; no
  package class subclasses another. Self-wrapping is possible for every member
  (`peekable(peekable(x))`, ...) except `_concurrent_tee` (F3).
  `seekable.__next__ -> peekable.__next__` (the `maxlen=0` source, `more.py:3102`),
  `seekable.peek -> peekable.peek` (`3136`), `SequenceView.__getitem__`,
  `__len__`, `__repr__` to both sequences (sequence-only `target`),
  `serialize.send`, `throw`, `close` to themselves and to `types.GeneratorType`
  (judgement 6): correct.
- **Default rejections** (7 lines, 36 candidates, 13,737 candidate-site pairs).
  The sample's 65 role-candidate sites where no role class arrives, the 40 pairs
  and the consistency scan found no site where a default hides a real call.
- **Functions that no site calls** (158 of 294 nodes, mostly public API): each is
  public, a client callback (`callback_iter._reader.callback`), a property, or a
  special method that the package never triggers on its own values
  (`numeric_range.__bool__`, `__eq__`, `__hash__`, `__reduce__`, `count`;
  `peekable.__bool__`, `seekable.__bool__`; `callback_iter.__enter__`,
  `__exit__`). None should have a caller.
- **Special methods and properties.** `numeric_range._len` (a `cached_property`)
  at its three loads: correct (first load in a fresh object). `callback_iter.done`
  and `result` are never loaded by the package. `Stats(...)` through `map`
  (`recipes.py:1590`) runs the generated dataclass `__init__`: no node, no edge.
- **Callees outside the package** (153 names). I checked each against the
  micro-benchmark naming rules and the README: `collections.defaultdict.get`,
  `collections.abc.Sequence.index`, `itertools._tee.__next__`,
  `functools._lru_cache_wrapper.__call__`, `functools.partial.__call__`,
  `operator.itemgetter.__call__`, `dataclasses.dataclass.wrap`,
  `concurrent.futures.ThreadPoolExecutor.submit` and `.shutdown`,
  `heapq.heappush_max` and `heappushpop_max` (3.14 and later), `math.sumprod` (3.12
  and later) with `recipes.dotproduct` and `more._fsumprod` (3.11), and
  `recipes.batched` with `recipes._batched`: all correct. Builtins that `map`
  calls back (`frozenset`, `pow`, `pool.pop`) have no edge, as the README says.
  The documented types of `numeric_range.__init__` (`int`, `float`,
  `decimal.Decimal`, `fractions.Fraction`, `datetime.timedelta` for the step only)
  and of `polynomial_eval` (with `complex`): correct.
- **Rejected trace edges** (27): the builtins, bound methods and mocks that the
  tests pass as callbacks, the `index` of the tests' lists and strings in
  `iter_index`, the `list_iterator.__next__` of a test list, and
  `powerset_of_sets -> frozenset` (a builtin that `map` calls back). All correct.
- **Notes.** I read the notes of every value site and of every site in the
  sample; they state where the values come from and agree with the source.
- **Versions and implementations.** `requires-python >= 3.11`; CPython 3.11 to
  3.15 and PyPy. The version branches of judgement 2 are right. I know of no
  PyPy difference that changes an edge here (PyPy also calls the length hint in
  `list`, `tuple`, `sorted` and argument unpacking).

## The writer's judgement calls

1. **The role and the contracts.** The application of the ruling is right for
   the ordinary role, the sequence-only inputs, the matrix, the Protocols and
   the inner iterables. For the numeric and index inputs and the outer iterable
   of iterables, see F1, F2 and "The flagged judgement".
2. **Version branches.** Supported by "Judgements" (a version branch runs if a
   supported version takes it).
3. **The call that cannot bind** (`recipes.py:908`, `numeric_range.index` with
   three arguments). Supported by "Edges" (a call that cannot bind its
   arguments has no edge).
4. **`divide`.** Python semantics; agree.
5. **`reversed()`.** Python semantics (`reversed_new` needs `__reversed__`, or
   `__len__` with `__getitem__`); agree.
6. **`serialize.send`, `throw`, `close`.** A package generator reaches the role
   as the output of a package function (the factory-output clarification and the
   composition role); `types.GeneratorType.send` follows the micro-benchmark
   naming rule. Agree.
7. **`read()` in the `running_median` helpers.** `itertools._tee.__next__` is
   supported by B2 (the package's own values count in full) and the naming rule
   for types without a public path. `itertools.takewhile.__next__`,
   `types.GeneratorType.__next__` and `SequenceView.__getitem__` there depend on
   F1.
8. **Wrapper objects** (`functools.partial.__call__`, `_lru_cache_wrapper`,
   `itemgetter`, `random.Random.randrange`). Supported by the clarification "a
   callable wrapper object uses its concrete class's `__call__`".
9. **`AbortThread`.** Supported by the instantiation rule
   (`<builtin>.BaseException.__init__`).
10. **`numeric_range._len`.** Supported by "Edges" (the first load in a fresh
    process, the sqlparse precedent).
11. **`chunked.ret -> take`, `side_effect -> take`.** Supported by the callback
    rule (the callable iterator calls `take` in the advancing function).

## Step 3: binding check

I parsed every call site whose callee is a package function or class and
compared its positional and keyword arguments with the callee's signature
(110 direct calls), then checked by hand the calls through values: `algorithm`
(`_full`, `partial(_partial, r=r)`), `too_short`, `too_long`, `self._validator`,
`seq_index`, `wrapping_func`, `batched` (also as the function of `reduce`),
`_sumprod` (`dotproduct`), `_fsumprod`, the `starmap` callbacks
(`outer_product.<lambda1>`, `_sumprod` of `matmul`), `key_argument`,
`first_true`'s `is_prime`, `unique_everseen`'s `itemgetter(1)`,
`_shift_to_odd`, and `map(Stats, ...)` with five iterables. Every call binds,
except `seq_index(value, i + 1, stop)` for a `numeric_range`
(`recipes.py:908`), which the writer already excludes. No code after a failing
call has edges.

## Evidence (scratch, not committed)

`$TMPDIR/audit-more-itertools/blind-answers.md` (written before the
writer's files were opened); `work/sample.json` (the drawn sites and reserve);
`work/pairs.py` and `work/pairs_cmp.py` (the 40 pairs); `work/cf.py` (the edge
counts of F1, F2 and the inner-iterable reading); `work/consist.py` (the
consistency scan); `work/bind.py` (the binding check).
