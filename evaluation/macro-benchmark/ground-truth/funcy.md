# funcy: judgements of the ground truth

Release 2.1 (commit `04aafae`). Analysed source: `funcy/` (root `.`): 16
modules, 289 functions (30 lambdas), 13 classes. The ledger is
`funcy.ledger`; the graph `funcy.json` is generated from it. The trace edges
that are not package edges are in `funcy.rejected.json` (52, all client
callbacks or client objects). The blind audit is `funcy.audit.md`; its
outcome and the lead's rulings are at the end of this file.

## Global-rule audit (2026-11-15)

The whole-benchmark audit (audit record `2026-11-15/README.md`) reviewed this
project under the same global rules as every other project. Its source-site
evidence is in funcy-review.json (audit record `2026-11-15/funcy-review.json`).

| Original edges | Removed | Added | Corrected edges |
|---:|---:|---:|---:|
| 869 | 0 | 57 | 926 |

- A wrapped property remains a property for `wrap_prop`, which adds four
  calls between nested `WrapperProp` objects.
- `Exception` is entered before rejecting keywords on admitted Python
  3.10; `raiser` therefore has this builtin edge.
- The documented dict argument of `compose` adds a direct `dict.__getitem__`
  call. Documented reuse of lazy factory results adds 48 callback edges;
  admitted factory arguments are not frozen to one documentation example.
- Three regex calls retain both modern and historical Python 3 names.

## Architecture, as the ledger uses it

- Almost every public function takes or returns functions. `make_func(f)`
  and `make_pred(f)` (`funcmakers.py:10`, `27`) turn a non-callable into a
  function: `None` gives `make_func.<lambda1>` (or `bool` for a predicate);
  a str, bytes or regex gives `re_finder.<lambda2>` (or
  `re_tester.<lambda1>`); an int or slice an `operator.itemgetter`; a mapping
  its `__getitem__`; a set its `__contains__`. These results are package
  values in every role that applies `make_func` or `make_pred`.
- In `seqs.py`, the module-level names `map` and `filter` are funcy's own
  functions (`seqs.py:129`, `134`); `_map` and `_filter` are the builtins
  (`seqs.py:26`). `colls.py` imports funcy's as `xmap` and `xfilter`, so
  `map` and `filter` there are builtins. In `colls.py`, `all` and `any` are
  funcy's (`colls.py:198`, `204`), and `_all`, `_any` the builtins. In
  `funcolls.py`, `all` and `any` are the builtins.
- `@decorator` (`decorators.py:11`) rebinds the decorated name to a
  `decorator_fab` (the package's seven `@decorator` functions have more than
  one positional parameter, so the second definition, `decorators.py:36`).
  A call such as `log_calls(print)` (`debug.py:50`) or
  `post_processing(list)` (`flow.py:197`) therefore runs
  `decorator.decorator_fab`; it returns `make_decorator._decorator`. The
  wrapper (`decorators.py:45`) builds a `Call` and calls the original
  function with it.
- `funcy.decorators.wraps` returns `functools.partial(update_wrapper, ...)`.
  A `@wraps(func)` decorator and `wraps(func)(wrapper)` call
  `functools.partial.__call__`, which calls funcy's `update_wrapper` back.
  In `funcs.py`, `wraps` is `functools.wraps` (`funcs.py:2`).
- The two definitions of `lzip` (`seqs.py:439`, `443`), of `decorator_fab`
  (`decorators.py:31`, `36`) and of `make_lookuper.wrapper` (`calc.py:124`,
  `131`) are one node each.

## Scope rules

`macro-benchmark/README.md` ("Scope rules") states the rules. This section
shows how the funcy ledger applies them.

**A.** Every function keeps the out-edges of its body. 30 functions do not
run in the tests (the primitives, `log_enters`, `log_exits`, `joining`,
`_zip_strict*`, `re_test`, the `nullcontext` fallback, among others); their
edges come from reading.

**B1.** `self.__class__(...)` in `LabeledContextDecorator.__call__`
(`debug.py:106`) is `log_errors`, `log_durations`, or `LabeledContextDecorator`
itself (J8). `cm` in `inner` (`debug.py:115`) has the class of `self`.

**B2 and B3.** A callback parameter has client callables (opaque) and the
package values that the package's code, the tests and the documented
examples pass for its role (J1). Passing an arbitrary package object where
any object is accepted is not considered: a `CacheMemory` from
`wrapper.memory`, a `LazyObject` or a `Call` handed to another function.

**B4.** A client collection is named by the concrete types that the
function's own docs entry or docstring lists, per entry (J6, ruling R2);
otherwise it is opaque. A str separator gives `str.join`; `joining`
documents str and bytes separators (`flow.rst`), `str_join` str.

**B5.** Client callables (lambdas, whatever's `_` expressions, builtins,
bound methods, functools partials, attrgetters) are opaque. A partial that
the client builds around a package function is opaque too (`rcompose(partial(remove, ...), ...)`, `funcs.rst`).

**C.** Public module-level definitions and class methods follow their
accessible paths, not `__all__`. Underscore helpers and private nested
callbacks receive values from their actual package callers. A function or
descriptor returned by a public factory, or exposed through a documented
instance attribute, is accessible in that returned or stored role; its
captured values still come from the factory. Lexical nested functions are
not all public entry points, and the helper list alone does not decide
accessibility. `LabeledContextDecorator` is not in `__all__` but its path
`funcy.debug.LabeledContextDecorator` has no underscore (J8).

## Judgement calls

1. **Roles of callback parameters (B2).** funcy documents a function and
   its list or iterator flavour in one docs entry (`map(f, seq)` and
   `lmap(f, seq)`; "List or iterator versions of same functions ... also
   support extended semantics", `extended_fns.rst`). The ledger takes one
   entry's parameter as one role. Its package values are those that the
   package's code, `tests/`, and the examples of `docs/*.rst` and
   `README.rst` (included by `overview.rst`) pass there. A value documented
   for another entry is not taken: `even` is documented for `select`,
   `all`, `lremove`, `complement` and `all_fn`, so it is a callee at those
   sites only. `extended_fns.rst` lists the functions with "extended
   function semantics"; the ledger does not read that list as one role for
   all predicates or all mappers. The narrow reading follows the aiocache
   ruling (a check on another parameter does not decide a role). Examples:
   `_lmap` (`seqs.py:29`) gets `first` and `second` (`seqs.rst`:
   `map(first, ...)`, `map(second, ...)`), `lcat` (`lmap(lcat, ...)`),
   `make_lookuper.wrapper` (`calc.rst`: `lmap(translate('ru'), ...)`),
   `autocurried` (`funcs.rst`: `map(rem(by=3), ...)`); `_lfilter`
   (`seqs.py:32`) gets `rcurry.<lambda1>.<lambda1>` (`funcs.rst`:
   `lfilter(has_suffix("ce"), ...)`). Three exclusions record values left
   out for this reason (`seqs.py:32`, `funcs.py:131`, `tree.py:35`).
   The global per-entry role rule fixes this boundary: values documented
   only for another entry do not become candidates at every listed API.
2. **Supported versions.** `setup.py` has no `python_requires`; its
   classifiers list Python 3.4 to 3.14, CPython and PyPy, and `README.rst`
   says "Works with Python 3.4+ and pypy3". So the pre-3.10 branch of
   `seqs.py:438` runs (`lzip` with `_zip_strict`, `_zip_strict_iters`,
   `_zip_strict_error`), and so does the 3.10 branch. The `nullcontext`
   fallback class (`flow.py:57`, for Python before 3.7) is defined on 3.4 to
   3.6; its methods make no call. The PyPy branch of `get_spec`
   (`_inspect.py:128`) and the `co_posonlyargcount` test
   (`decorators.py:121`) run on both sides; no branch has a call that the
   other lacks.
3. **`make_func` of a set or a mapping.** `extended_fns.rst` names "set"
   and "mapping". The ledger reads "set" as the builtin set (B4), so a direct
   call of the result names `<builtin>.set.__contains__` (`split_keys`,
   `iffy.<lambda1>` and `juxt.<lambda1>` make it in the trace). "Mapping" is
   abstract (and `make_func` checks the abstract `Mapping`), so a generic `f.__getitem__`
   has no named callee. However, `docs/funcs.rst:179` explicitly composes
   a concrete dict with a regex. The returned dict method is called
   directly by the composed lambda and adds `<builtin>.dict.__getitem__`. The lead kept this reading (ruling R1): where the
   documentation names a concrete type for a client value ("set",
   "property"), the value is named by that type, although the code tests an
   abstract class. 15 edges to `<builtin>.set.__contains__`.
4. **Lazy objects with package callbacks.** A lazy `map`, `filter`,
   `filterfalse`, `takewhile`, `dropwhile`, `chain` or `groupby` calls its
   function where it is consumed. The edge is placed at the package call
   that consumes it: `list()` in `_lmap`, `_lfilter`, `lremove`, `lkeep`,
   `lcat`, `lsplit_by`, `lwhere`, `re_all`; `set()` in `is_distinct`; the
   builtin `all`/`any` in `colls.all`/`colls.any`; `next()` in `some`; the
   collection factory in `walk`, `walk_values`, `select`; `reduce` and
   `list()` in `compose`, `ljuxt`, `juxt` (they call `make_func` back); the
   loop over `groupby` in `partition_by`. Two cases cross functions: `one`
   (`colls.py:218`) hands `take` a filter, so `take` calls the predicate
   (`seqs.py:54`: `re_tester.<lambda1>` for a str predicate); `lmapcat`
   hands `lcat` a map (`seqs.py:178`). This follows README "Limits of the
   site finder" and the callback rule of B5. A lazy object returned to the
   client calls nothing in the package. For map/filter built and consumed in
   one function, README ruling12 also permits the construction-site placement;
   this ledger chooses the consumer. The exception does not cover groupby.
5. **Lazy objects that the documentation hands back.** A documented
   factory-result role admits the package factory's possible states, not
   only the literal arguments of one example. The returned iterators of
   `where`, `keep`, `map`, `filter`, `remove` and `takewhile` can therefore
   carry their admitted package callbacks into consumers such as `first`,
   `group_values`, `some`, `lcat`, `_lfilter`, `lremove` and `ilen`. The
   consumer owns the callback edge. This adds 48 edges. The ledger gives
   each consuming site and the report records the documented reuse path.
   A library wrapper built by a client around a package object remains
   opaque under B5.

6. **Collection types (as ruled, R2: per entry).** A client collection is
   named by the types that the function's own docs entry or docstring lists,
   or that a function reaching it lists: `merge` (and `join`, "Same as
   merge"): dicts, sets, lists, tuples, iterators, strings; `walk`: sets,
   tuples, strings (`colls.rst:37-47`), and OrderedDict through `flip`
   (`colls.rst:174`) and `walk_keys` (dict, defaultdict, OrderedDict), which
   call `walk`; `walk_values`: mappings and collections of pairs, and
   defaultdicts; `select`: a set, a dict, a tuple (`colls.rst:87, 90`,
   `README.rst`); `split_keys`: "a dictionary"; `project`, `omit`: dicts;
   `iteritems`, `itervalues`: dictionaries. The types that `_factory`'s
   `isinstance` tests (defaultdict, iterator, str, bytes) and
   `FACTORY_REPLACE` (mappingproxy, dict views) fix are named where that
   caller's admitted inputs can reach those branches. The private helper
   does not widen dictionary-only roles (`split_keys`, `project`, `omit`)
   to every type handled for another caller. Package-created dicts are
   concrete too (`update_in`'s `{}`, the `**kwargs` of `get_arg`,
   `join_with`'s `lists`). Any other client collection is opaque. At `empty` (`colls.py:52`), a str gives
   `''.join()`, which cannot bind its arguments: no edge.
7. **`wrap_prop` and `cached_readonly`.** The tests wrap a builtin
   property and a `cached_property`; `objects.rst` wraps a
   `cached_property`. `objects.rst` documents `cached_readonly` as "a
   read-only property". The ledger takes it as a property for the role, so
   `WrapperProp.__set__` (`objects.py:52`) calls
   `cached_readonly.__set__` (1 edge). `cached_readonly` inherits
   `cached_property.__get__`, which `objects.py:47` names anyway. The
   returned `WrapperProp` is itself documented as a wrapped property, so
   nesting it adds its `__get__`, `__set__`, `__del__` and `__repr__` calls.
8. **`LabeledContextDecorator` is public.** It is not in `debug.__all__`, but
   its path has no underscore (C), and it is a plain class, so a client can
   make one. `self.__class__(...)` (`debug.py:106`) names its `__init__`
   (1 edge). A plain instance has no `__enter__`, so the `with` of `inner`
   fails before any call; `debug.py:115` names only the subclasses' methods.
9. **Documented keys and functions.** The docs signatures
   `distinct(seq, key=identity)` and `is_distinct(coll, key=identity)` name
   `identity` for the key role (the code's default is `EMPTY`), and
   `count_reps` is documented as an "alternative to `count_by(identity, ...)`"
   (`seqs.rst`). So `identity` is a callee at `seqs.py:246`, `342` and
   `colls.py:195`.
10. **`raiser` with its default.** `_raiser` calls
    `exception_or_class(*args, **kwargs)` (`flow.py:26`) only with arguments.
    On admitted Python 3.10 the default `Exception` constructor is entered
    before it rejects keyword arguments. A builtin-body `TypeError` does
    not erase that call, so `<builtin>.Exception` is a callee.

11. **Values that the package's recursion makes.** `rcurry` with `n >= 4`
    passes an `rpartial` lambda to `rpartial` (`funcs.py:66`), so
    `rpartial.<lambda1> -> rpartial.<lambda1>`. `curry` with `n >= 3` passes
    a `functools.partial` (`funcs.py:52`); with `curry(re_test)` (`funcs.rst`,
    `re_test` has three parameters) the partial calls `re_test` back, so
    `curry.<lambda1>.<lambda1> -> re_test`.
12. **Names.** `from operator import __not__` is named `operator.not_`
    (the same function; the trace's public alias; the dunder is not in
    `operator.__all__`). `timer` is `timeit.default_timer` (`debug.py:5`).
    `Spec(...)` calls a `collections.namedtuple` class: no edge
    (`_inspect.py:114`, `166`, `186`; `funcs.py:72`); `spec._replace` is
    `collections.namedtuple._replace`. `Signature.parameters` is a
    `types.MappingProxyType`.

The trace limit T1 does not affect funcy: the package runs no `exec`
and starts no thread, and its only `@contextmanager` function, `reraise`,
has no package caller.

## Default rejections

| Candidate | Sites decided | Reason (short) | Accepted explicitly at |
|---|---|---|---|
| `calc.CacheMemory.__getitem__` | 357 | only `cache()` makes a CacheMemory; its wrapper subscripts it | `calc.py:52` |
| `calc.CacheMemory.__setitem__` | 23 | the only CacheMemory store is in that wrapper | `calc.py:55` |
| `decorators.Call.__getattr__` | 337 | the package reads only attributes that a Call has | nowhere |
| `objects.LazyObject.__getattr__` | 337 | the package never makes a LazyObject | nowhere |
| `objects.LazyObject.__setattr__` | 50 | the package never makes a LazyObject | nowhere |
| `primitives.EmptyType.__repr__` | 37 | `EMPTY` is only tested with `is` | nowhere |
| `decorators.Call.__str__` | 34 | no Call is formatted | `decorators.py:85` |
| `decorators.Call.__repr__` | 36 | no Call is formatted | nowhere (`%s` at `decorators.py:85` runs `__str__`) |
| `objects.wrap_prop.decorator.WrapperProp.__repr__` | 36 | no other site formats a WrapperProp | `objects.py:40` (explicit `repr`, overriding the default) |

The three accepted sites are default-decided implicit sites; their entries
were added by hand from `check.py --report funcy --default <candidate>`.

## Value sites

112 value sites, each with a note. The hard ones:

| Site | Callees (package) | Where the values come from |
|---|---|---|
| `seqs.py:29` `list(map(f, *seqs))` in `_lmap` | 20 | J1, J4: make_func's lambdas and the map/lmap role's documented values |
| `funcs.py:110:47` / `110:49` `f(g(...))` | 13 / 12 (+ outside) | every `compose` caller: `all_fn` ... `some_fn`, `complement`, `_factory`, the compose role |
| `funcs.py:137` `juxt.<lambda1>` | 14 | juxt role and `all_fn`, `some_fn` documentation |
| `decorators.py:47` `deco(call, ...)` | 7 | the seven `@decorator` functions of `debug.py` and `flow.py` |
| `decorators.py:68`, `70` `self._func(...)` | 2 | stacked decorators (tests, `decorators.rst`, `debug.rst`) |
| `flow.py:42` `func(...)` in `ignore` | 4 | `raiser(...)`, stacked `log_calls`, `log_errors`, `limit_error_rate` (tests, docs) |
| `colls.py:131` walk factory | 15 + factories | `walk_keys.pair_f`, `flip.flip_pair`, make_func, `inc`, `compose(str, ord)` |
| `debug.py:177`, `193` `format_time` | 5 | `time_formatters` (`debug.py:152`) |

## Statistics

| | Count |
|---|---|
| Nodes | 305 (16 modules, 289 functions) |
| Edges | 986: 511 in the package, 475 to 124 callees outside |
| Confirmed by the trace | 674 of 986 (68.4%) |
| From reading only | 312 |
| Rejected trace edges | 52 (client callables and objects of the tests) |
| Functions run by the tests | 259 of 289 |
| Ledger entries | 813 |
| Value sites | 112 |
| Default rejections | 9, deciding 1247 site pairs |
| Exclusions | 3 lines (5 nodes at 3 sites) |

## Audit outcome and rulings (earlier audit)

The blind audit (`funcy.audit.md`) re-derived 173 sites (61 drawn, 112
value sites): 144 agree. Of the 29 differences, 5 were the auditor's
errors, 21 were judgement differences (J3, J6), 1 a missed edge and 2
ledger entries with callees that cannot reach their site. No edge of the
graph was impossible. The lead ruled:

- **F1 (accepted, +1).** `compose.<lambda1>.<lambda1> -> funcy.primitives.isnone`
  at `funcs.py:110:49`: `primitives.rst:19` calls `notnone` "a shortcut for
  `complement(isnone)`", and `complement(pred)` is `compose(__not__, pred)`.
  Ruling R3: an expression in the documentation that passes a package
  function in a role is a documented example, in prose as in a code block
  (as J9 reads `count_by(identity, ...)`).
- **F2 (applied, 0 edges).** `funcs.py:83:24` can call neither `lmap` nor
  `keep` (neither has `**kwargs`, so line 82 never holds when line 80
  failed); `funcs.py:86:28` can call only `keep` (`lmap` has
  `req_n == max_n`). Both entries and notes are corrected; the graph keeps
  `autocurried -> lmap` and `-> keep` through `81:24`.
- **R1 (J3 kept).** A concrete type that the documentation names for a
  client value ("set", "property") names the value, although the code tests
  an abstract class: the 15 edges to `<builtin>.set.__contains__` and
  `<builtin>.property.__get__`/`__set__` at `objects.py:47`, `52` stay.
- **R2 (J6 per entry, -22).** Each of the 22 edges was checked against the
  function's own docs entry and docstring, and against the values that
  funcy's own code makes; none is named there, so all 22 were removed:
  `empty` -> `set`, `tuple`, `OrderedDict` ("an empty collection of the
  same type"); `walk_values` -> `set`, `tuple`, `OrderedDict` ("mappings
  and collections of pairs", defaultdicts); `select` -> `OrderedDict`
  (a set, a dict, a tuple); `split_keys` -> `OrderedDict`,
  `OrderedDict.items`, `defaultdict.items` ("a dictionary"); `project`,
  `omit` -> `OrderedDict` (dicts); `itervalues` -> `defaultdict.values`,
  `OrderedDict.values` ("any dictionaries"); `join` -> `defaultdict.copy`,
  `OrderedDict.copy`, `defaultdict.update`, `OrderedDict.update` (merge's
  dicts); `update_in` -> `defaultdict.copy`, `OrderedDict.copy`,
  `defaultdict.get`, `OrderedDict.get` (no type; `update_in`'s own `{}`
  keeps `dict.copy` and `dict.get`). Kept: `walk`'s `set`, `tuple` and
  `OrderedDict`, `select`'s `set`, `tuple`, `dict`, `join`'s dict, set, list
  and tuple, `iteritems`'s `defaultdict.items` (the `walk_values` entry's
  defaultdict reaches it) and `OrderedDict.items` (`flip` and `walk_keys`
  reach it through `walk`), and every type that an `isinstance` test or
  `FACTORY_REPLACE` fixes. The trace edge `join -> collections.defaultdict.copy`
  (the tests' own defaultdict, `test_colls.py:70-72`) moved to
  `funcy.rejected.json`.
- J1, J2, J4, J5 and J7 to J12 stand.

Totals after the rulings: 869 edges (890 + 1 - 22): 400 inside, 469
outside; the trace confirms 674 (77.6%; 4 removed edges had matched trace
edges through an alias that `dict`'s method still matches); 52 rejected
trace edges.

## Third complete source audit (2026-11-16)

The independent model and full source inventory were frozen before comparison. All 16 runtime files (2392 lines), 289 function nodes, 1714 scanner sites, 812 baseline ledger entries, 902 omitted sites, every default rejection and all 926 baseline pairs were reviewed statically. This pass finds 0 false-positive pairs and 60 missing pairs.

Documented compose factory outputs include compose() (identity) and a singleton compose whose make_func result is returned unchanged. The applicable map/lmap, walk and some_fn/juxt roles therefore include those concrete outputs. Documented handoffs of the map iterator carry them into _lfilter, lremove, lcat and some. The variadic compose role does not constrain an admitted own function to its example position. Documented rcurry partial outputs also vary with public n, adding its two outer callable branches at _lfilter. Every added pair has a concrete source/role/binding witness in the round-3 report. No arbitrary package-callable universe is admitted.

The three make_func callback moves from map construction to reduce/list at funcs.py:111,130,136 are allowed same-function placement normalizations under README ruling12, not defect corrections. The groupby mapper move from seqs.py:411:28 to411:21 remains a site correction: the current exception names map/filter only, and the for loop invokes the groupby callback. All four groups preserve graph pairs. The audit also completes symmetric compose argument-site relations.

No target, test, dependency or generated code was imported or executed. The stored trace was used only by structural/origin gates. The historical audit text above is preserved byte-for-byte. Exact edits, git patch, six-file stage, all-site evidence, binding audit and input/artifact hashes accompany the round-3 report.


## Round 4 source-first audit (2026-11-16)

A fresh source model and inventory were frozen before reading this project's baseline. The audit read all 16 runtime files (2,392 lines), current support declarations, and relevant documentation and test roles as inert source. It checked all 986 existing pairs, 1,714 sites, 813 ledger entries, 901 omitted sites, 305 module/function scopes (including 53 zero-edge scopes), nine default candidates deciding 1,247 site pairs, five excluded candidate-site pairs (four distinct nodes) at three sites, and 52 rejected trace pairs. No false-positive or missing pair was found. The graph, ledger and edge registers are unchanged. This records a new audit, not a metadata-defect correction.

The scope is Python 3.4 and later, CPython plus the explicitly supported PyPy implementation. Funcy 2.0 explicitly dropped Python 2. The normal/-O/-OO union remains the shared working assumption; the optional preference was unanswered. Removing the two assertions or docstrings adds no admitted named edge. Retained raw inspect, functools and regex implementation sources support the existing external names.

The audit retained the per-entry role limits: CacheMemory's dict inheritance does not establish a mapper/general-collection role; its documented memory operations are cache storage. Nested wrapped properties retain their descriptor role, while client-built functools partials remain opaque. Only joining explicitly documents a bytes separator; str_join retains the str edge. Post-freeze clarifications are recorded separately without changing frozen evidence.

Evidence is staged in `/tmp/pycg-macro-audit-pass4/funcy-agent`: source freeze, full pair/site/body/default/exclusion coverage, input hashes and separate post-freeze corrections. No target code or tests were executed. Root performs structural/origin verification before acceptance. Static review cannot prove absence of every possible missed edge.
