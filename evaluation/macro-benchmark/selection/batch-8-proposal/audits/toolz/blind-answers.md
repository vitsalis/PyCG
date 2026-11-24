# toolz: blind answers (159 sites, seed 20261124)

Written from the source at `451af60`, its tests, docstrings and
`doc/source/*.rst`, the trace `dynamic/toolz.json`, the CPython and PyPy
sources in `deps/`, and the README's rules. No file of the writer was
opened, listed or searched before the commit of this file.

## The draw

`draw.py` over a skeleton made in a scratch copy without any ledger
(`check.py --benchmark-dir <scratch> --skeleton toolz`): 1256 sites, 599
explicit (`call`, `decorator`), 440 `getattr`, 217 other implicit, 96 value
sites. Attribute loads are 35% of the skeleton and have one candidate
(`toolz.__getattr__`, 462 sites), so the draw is split by kind:
`random.Random(20261124)`, `rng.sample` of 45 explicit, then 15 other
implicit, then 10 `getattr` sites; then the 89 value sites that the draw
did not take. 159 sites (`sample.txt`).

## Values that several sites share

| Role | Package values (source of the admission) |
|---|---|
| `factory` of the dicttoolz functions | only the default `dict` (`<builtin>.dict`); the tests' `defaultdict` lambdas and `CustomMapping` are client code |
| `key` of `groupby` | `getter` outputs (`getter.<lambda1>` for a one-element list, `getter.<lambda2>` for `[]`, `operator.itemgetter.__call__` otherwise: tests `groupby(0)`, `([0])`, `([0, 0])`), `first` and `second` forwarded by `join` (docs `streaming-analytics.rst:192`, `:281`, tests `test_join`), curried `get(3)` (`streaming-analytics.rst:87`, `:100`: `curry.__call__`) |
| `leftkey`/`rightkey` of `join` | `first`, `second` (docs, tests), `getter` outputs (tests `join(0, ...)`, `([0, 1], ...)`, `([0], ...)`); the tests' `identity` in `test_itertoolz.py` is test-defined |
| `key` of `reduceby` | `getter` outputs (tests and docstring `'state'`), curried `get(3)` (`streaming-analytics.rst:155`) |
| `key` of `EqualityHashKey` | `first` (`sandbox/tests/test_core.py:45`), `getter` outputs (`'firstname'`, `['firstname', 'age']`, `0`; a client list of one or no index) |
| `key` of `unique` | the curried `EqualityHashKey` (sandbox docstring and tests): `curry.__call__`, whose results are `EqualityHashKey` instances |
| `funcs` of `compose` (any position, the funcy precedent) | curry objects (docs `compose(sum, pluck(2))`, `compose(frequencies, map(stem), ...)`, the `do` docstring; tests `compose(g, curry(f))`), `Compose` objects (tests `compose(compose(g, f), ...)`, `complement(complement(iseven))`), `frequencies` (`curry.rst:28`, README, `parallelism.rst`), `concat` (`parallelism.rst`); and `operator.not_`, which `complement` passes as the outer function |
| `func` of `memoize` | curry objects (`test_memoize_curried`) |
| `funcs` of `pipe` | curried `filter`, `map`, `groupby`, `valmap` (`streaming-analytics.rst:37`, `:100`) |
| `func` of `merge_with` | `first` (its docstring, `dicttoolz.py:52`) |
| `func` of `keymap`, `valmap`, `itemmap` | `identity` (`test_dicttoolz.py:248-250`); `valmap` also `compose(sum, pluck(2))` |
| `func` of `update_in` | `assoc_in.<lambda1>` (`dicttoolz.py:242`) |
| `lamda` of `utils.raises` | `apply` (`test_functoolz.py:54`) |
| the function that a curry wraps | the 43 package callables that the package, the docs and the tests curry: the 39 of `toolz.curried` that are package functions or classes (`accumulate`, `assoc`, `assoc_in`, `cons`, `countby`, `dissoc`, `do`, `drop`, `excepts.__init__`, `get`, `get_in`, `groupby`, `interpose`, `itemfilter`, `itemmap`, `iterate`, `join`, `keyfilter`, `keymap`, `mapcat`, `nth`, `partition`, `partition_all`, `partitionby`, `peekn`, `pluck`, `random_sample`, `reduceby`, `remove`, `sliding_window`, `tail`, `take`, `take_nth`, `topk`, `unique`, `update_in`, `valfilter`, `valmap`), `memoize` and `flip` (decorated), `curried.exceptions.merge` and `merge_with`, and `EqualityHashKey.__init__` (sandbox docstring and tests); `curry.__init__` unpacks a curry, so `self.func` is never a curry |

Callbacks of a lazy object that the package returns to the client are no
edge (funcy, "Lazy objects with package callbacks"); a lazy object that one
function builds and consumes keeps its callback at the building call.

## The registry (`_signatures.py`)

`create_signature_registry` registers `getattr(module, name)` for each name
that the module has on the running interpreter. 290 lambdas: 97 are never
in the registry on an admitted runtime (Python 3.9 to 3.15, CPython and
PyPy): the 14 Python 2 builtins and 5 Python 2 itertools names, the 19
Python 2 operator names, `operator._compare_digest` (`from _operator import
*` skips underscore names; CPython `Lib/operator.py:408`, PyPy
`pypy/module/operator/moduledef.py:26`), the 45 operator dunder aliases
(`__add__ = add`, `Lib/operator.py:416-460`, and later entries of the same
object overwrite them: each non-dunder name follows its alias in
`module_info`), and `builtins.abs`, which `operator._abs` (`from builtins
import abs as _abs`, `Lib/operator.py:22`) overwrites. The trace agrees:
`abs` runs `<lambda215>` (`operator._abs`). 193 are registered.

On PyPy, `_check_sigspec` (`functoolz.py:942-947`) sends every registered
callable to the registry, so `is_valid_args(key, args, kwargs)` reaches
`check_valid` for every registered key; on CPython 3.15 `frozendict` has no
text signature (`Objects/dictobject.c:8537`), as `dict`. The keys are client
values of the public `is_valid_args` and of the curried builtins of the
package; their identity selects the entry (B5, client control flow). Six
keys are package objects (`curry`, `flip`, `juxt`, `memoize`, `Compose`,
`InstanceProperty`): no package call, test or document passes them to
`is_valid_args` or to `curry`, so by B3 they reach no lambda; `excepts`
does, through `toolz.curried.excepts` (PyPy). Result: 187 lambdas at
`_signatures.py:684:13`.

## The sites

Notation: `->` callee, `x` rejected candidate. Lambdas of `_signatures`
by their number (`toolz._signatures.<lambdaN>`).

### tlz._build_tlz

| # | Site | Callees and decisions |
|---|---|---|
| 3 | 18:54 `fullname.partition('.')` | `-> <builtin>.str.partition` (a module name); x `itertoolz.partition`: the receiver is a str |
| 5 | 20:34 `''.join([...])` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 9 | 25:34 `''.join([...])` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 14 | 34:54 `fullname.partition('.')` (`find_module`, private and uncalled: public fallback, a module name) | `-> <builtin>.str.partition`; x `itertoolz.partition` |
| 28 | 48:54 `fullname.partition('.')` (`find_spec`) | `-> <builtin>.str.partition`; x `itertoolz.partition` |
| 38 | 57:34 `toolz_mods.get('cytoolz')` | `-> <builtin>.dict.get` (the dict of `_load_toolz`); x `itertoolz.get` |
| 41 | 58:34 `toolz_mods.get('toolz')` | `-> <builtin>.dict.get`; x `itertoolz.get` |
| 52 | 62:57 `package.partition('.')` | `-> <builtin>.str.partition` (`__package__`, a str under the `is not None` test); x `itertoolz.partition` |
| 54 | 63:41 `''.join([...])` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 63 | 74:39 `slow_mod.__dict__.get(k)` | `-> <builtin>.dict.get`; x `itertoolz.get` |
| 76 | 85:64 `v.__name__.partition('.')` | `-> <builtin>.str.partition`; x `itertoolz.partition` |
| 77 | 86:34 getattr `''.join` | x `toolz.__getattr__`: the receiver is a str |
| 78 | 86:38 `''.join([...])` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 82 | 91:23 `TlzLoader()` | `-> tlz._build_tlz.TlzLoader.__init__` |

### toolz, toolz._signatures, toolz.compatibility, toolz.curried

| # | Site | Callees and decisions |
|---|---|---|
| 94 | `toolz/__init__.py` 29:21 `version("toolz")` | `-> importlib.metadata.version` |
| 131 | 612:29 op `x.kind == x.VAR_KEYWORD` | x the three `__eq__`: `inspect._ParameterKind` operands |
| 136 | 616:20 `list(sigspec.parameters.values())` | `-> <builtin>.list` |
| 159 | 668:37 `info.items()` | `-> <builtin>.dict.items` (the private function gets only the default `module_info`) |
| 169 | 684:13 `func(*args, **kwargs)` | `->` the 187 registered lambdas: 2-5, 9-11, 15-20, 23-33, 38-56, 58-65, 68-80, 86-103, 107-108, 112-145, 149-151, 154-162, 215, 217-224, 227-230, 232-235, 237-247, 249-251, 256-274, 276, 278, 280-283, 285; x `curry.func`: `func` is the lambda of the entry. Reason: see "The registry" |
| 179 | 708:27 `is_partial_args(func, args, kwargs, sigspec)` | `-> toolz.functoolz.is_partial_args` (binds) |
| 184 | 723:20 `is_arity(n, func, sigspec)` | `-> toolz.functoolz.is_arity` |
| 203 | 780:13 op `func not in signatures` | `-> curry.__hash__`: a curry is admitted at `num_required_args` (`test_inspect_args.py:358-385`); on PyPy `toolz.flip` and `toolz.memoize` are registered curries that reach `_num_required_args`, and on CPython a curry of a builtin without a signature makes `inspect.signature` raise `ValueError` through `curry.__signature__` (`functoolz.py:237`). `-> curry.__eq__`: `flip` and `memoize` are stored keys; a client callable whose `__signature__` raises `ValueError` (the tests' `RaisesValueError`) and whose hash equals one of theirs makes the dict call the stored key's `__eq__` (README "Call sites", the collision rule; client control flow, B5). x `Compose.__eq__`, `Compose.__hash__`, `EqualityHashKey.__eq__`, `__hash__`: no instance is admitted at the inspection functions (B3), and the registered `Compose` is the class |
| 208 | 785:14 op `x == val` | x the three `__eq__`: ints or `None` from `num_required_args` |
| 217 | `compatibility.py` 12:53 getitem `sys.version_info[1]` | x all six: `sys.version_info` and an int |
| 264 | `curried` 70:29 getattr `toolz.groupby` | x `toolz.__getattr__`: the module has the name (star import, `__init__.py:1`) |
| 270 | 72:32 getattr `toolz.itemfilter` | x `toolz.__getattr__`: as above (`__init__.py:5`) |
| 358 | `curried/exceptions.py` 9:28 `toolz.merge_with(...)` | `-> toolz.dicttoolz.merge_with`; x `curried.exceptions.merge_with`: `toolz.merge_with` is dicttoolz's |
| 362 | 14:23 `toolz.merge(...)` | `-> toolz.dicttoolz.merge`; x `curried.exceptions.merge` |
| 369 | `curried/operator.py` 12:16 `locals().update({...})` | `-> <builtin>.dict.update` (module `locals()` is the module dict) |

### toolz.dicttoolz

| # | Site | Callees and decisions |
|---|---|---|
| 387 | 33:42 `isinstance(dicts[0], Mapping)` | `-> <builtin>.isinstance` |
| 391, 407, 413, 422, 431, 437, 442, 447, 452, 457, 472, 477, 480 | `factory()` at 37:17, 67:21, 84:17, 100:17, 116:17, 134:17, 154:17, 177:17, 195:17, 215:17, 282:25, 288:28, 291:32 | `-> <builtin>.dict` (the package default; `assoc_in` forwards its own default); client factories are client callbacks |
| 406 | 65:22 `values[k](v)` | `-> <builtin>.list.append` (`defaultdict(lambda: [].append)`) |
| 409 | 68:29 `values.items()` | `-> collections.defaultdict.items` |
| 411 | 69:25 `func(v.__self__)` | `-> toolz.itertoolz.first` (docstring `merge_with(first, ...)`); x `curry.func` |
| 426 | 101:22 `map(func, d.keys())` | `-> <builtin>.map`, `-> toolz.functoolz.identity` (tests; `rv.update` consumes the map in this function) |
| 440 | 136:21 `predicate(v)` | none: the tests and docs pass `callable`, test functions and lambdas |
| 445 | 156:21 `predicate(k)` | none (as 440) |
| 450 | 179:21 `predicate(item)` | none (as 440) |
| 484 | 297:24 `func(d[k])` | `-> toolz.dicttoolz.assoc_in.<lambda1>`; x `curry.func` |
| 487 | 299:24 `func(default)` | `-> toolz.dicttoolz.assoc_in.<lambda1>`; x `curry.func` |

### toolz.functoolz

| # | Site | Callees and decisions |
|---|---|---|
| 494 | 43:49 getitem `func_and_args[1:]` | x all six: a tuple and a slice |
| 495 | 44:16 `func(*args, **kwargs)` (`apply`) | none: tests and docstring pass test functions; x `curry.func` |
| 497 | 73:24 `form(val)` | none (test and doctest functions) |
| 501 | 77:24 `func(*args)` | none; x `curry.func` |
| 504 | 112:24 `form(val)` | none |
| 508 | 116:24 `func(*args)` | none (`map`, `filter` of the docstring are client callbacks); x `curry.func` |
| 520 | 165:56 getattr `self.__doc__` | x all five: `property.__init__` stores the doc of a property subclass in the instance dict, and the class dict holds the docstring (a str) |
| 527 | 206:20 `hasattr(func, 'func')` | `-> <builtin>.hasattr`, `-> InstanceProperty.__get__` (a curry as `func`, from `bind`, `__get__`, `_restore_curry`); x `toolz.__getattr__` |
| 548 | 233:30 getattr `self._partial.func` | x all five: a `functools.partial` |
| 563 | 245:33 `len(args)` | `-> <builtin>.len` |
| 587 | 273:6 `@instanceproperty` | `-> toolz.functoolz.instanceproperty` |
| 597 | 289:20 `repr(self.func)` | `-> <builtin>.repr`; x `Compose.__repr__`, `curry.__repr__`, `EqualityHashKey.__repr__` (no admitted wrapped callable has them: `curry(EqualityHashKey, ...)` wraps the class), x `curry.func` |
| 614 | 298:50 getattr `self.keywords` | `-> InstanceProperty.__get__`; x `toolz.__getattr__`, `Compose.__get__`, `_InstanceAnnotations.__get__`, `curry.__get__` |
| 618 | 301:31 `self.__eq__(other)` | `-> toolz.functoolz.curry.__eq__`; x `Compose.__eq__`, `EqualityHashKey.__eq__` |
| 620 | 305:33 `self._partial(*args, **kwargs)` | `-> functools.partial.__call__` and the 43 wrapped package callables (table above) |
| 632 | 317:62 `_sigs.signature_or_spec(func)` | `-> toolz._signatures.signature_or_spec` |
| 639 | 338:26 `type(self)(self, ...)` | `-> toolz.functoolz.curry.__init__` (self is a curry; subclasses are test code) |
| 641 | 341:29 `self._partial(*args, **kwargs)` | as 620 |
| 660 | 368:36 `'.'.join(attrs)` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 666 | 372:64 `self.__dict__.items()` | `-> <builtin>.dict.items` |
| 679 | 388:14 `cls(func, ...)` | `-> toolz.functoolz.curry.__init__` (`__reduce__` passes `type(self)`) |
| 682 | 389:24 `obj.__dict__.update(userdict)` | `-> <builtin>.dict.update` |
| 690 | 456:16 `key(args, kwargs)` | `-> toolz.functoolz.memoize.key` (the three local `key`s are one node) |
| 691 | 458:25 getitem `cache[k]` | x all six: keys from client arguments; no test or document memoizes a call with a package object |
| 693 | 462:18 setitem `cache[k]` | x all six (as 691) |
| 694 | 462:37 `func(*args, **kwargs)` | `-> toolz.functoolz.curry.__call__`; x `curry.func` |
| 698 | 487:50 `self.fget(obj)` | `-> toolz.functoolz.Compose._combined_annotations` (`functoolz.py:628`) |
| 699 | 499:22 `tuple(reversed(funcs))` | `-> <builtin>.tuple` |
| 704 | 504:25 `self.first(...)` | `-> curry.__call__`, `-> Compose.__call__`, `-> toolz.itertoolz.frequencies`, `-> toolz.itertoolz.concat`; x `toolz.itertoolz.first`: no document or test composes it |
| 706 | 506:20 `f(ret)` | `-> curry.__call__`, `-> Compose.__call__`, `-> toolz.itertoolz.frequencies`, `-> toolz.itertoolz.concat`, `-> operator.not_` (`complement`, `functoolz.py:737`) |
| 709 | 515:6 `@instanceproperty(classval=__doc__)` | `-> functools.partial.__call__`, `-> toolz.functoolz.instanceproperty` (the decorator is the partial of `functoolz.py:143`) |
| 716 | 524:56 getitem `fs[1:]` | x all six: a tuple |
| 723 | 538:31 `'_of_'.join(...)` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 752 | 570:33 `inspect.signature(self.first)` | `-> inspect.signature`, `-> InstanceProperty.__get__` (`__signature__` of a curry or Compose first, `__wrapped__` of a Compose); x `toolz.itertoolz.first` |
| 785 | 620:21 getattr `self.funcs` | x `toolz.__getattr__`: a slot of Compose |
| 799 | 637:63 `annotationlib.annotations_to_string(...)` | `-> annotationlib.annotations_to_string` (3.14 and later) |
| 811 | 673:21 getitem `funcs[0]` | x all six: a tuple |
| 815 | 720:20 `func(data)` (`pipe`) | `-> toolz.functoolz.curry.__call__`; x `curry.func` |
| 824 | 764:26 `func(*args, **kwargs)` (`juxt`) | none: tests and docs pass client functions; x `curry.func` |
| 827 | 795:9 `func(x)` (`do`) | none (`log.append`, test functions); x `curry.func` |
| 828 | 799:2 `@curry` | `-> toolz.functoolz.curry.__init__` |
| 829 | 823:16 `func(b, a)` (`flip`) | none (test functions, `isinstance`); x `curry.func` |
| 831 | 868:29 `self.func(...)` (`excepts`) | none (test and docstring lambdas); x `curry.func` |
| 834 | 870:32 `self.handler(e)` | `-> toolz.functoolz.return_none` (the default) |
| 835 | 872:6 `@instanceproperty(classval=__doc__)` | `-> functools.partial.__call__`, `-> toolz.functoolz.instanceproperty` |
| 841 | 879:46 `', '.join(map(...))` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 848 | 902:24 `type(self)` | `-> <builtin>.type` |
| 854 | 909:39 `'_or_'.join(...)` | `-> <builtin>.str.join`; x `itertoolz.join` |
| 865 | 924:34 `builtin_func(*builtin_args)` | `->` the six `toolz._signatures` functions that the six callers pass: `_num_required_args`, `_has_varargs`, `_has_keywords`, `_is_valid_args`, `_is_partial_args`, `_is_arity` (a client callable whose `__signature__` raises `ValueError`, as in the tests, reaches it from each caller) |
| 873 | 933:31 `builtin_func(*builtin_args)` | none: no registered callable has a `__signature__` with `__get__` (no builtin of CPython 3.9 to 3.15 defines `__signature__`; on the classes `curry` and `Compose` the instance property gives `None`, on `flip` and `memoize` a `Signature`); the tests reach it only after adding a class to the registry (package internals) |
| 876 | 945:31 `builtin_func(*builtin_args)` (PyPy) | the six of 865 |
| 877 | 947:35 `_check_sigspec_orig(...)` | `-> toolz.functoolz._check_sigspec` (the first definition; both definitions are one node) |
| 887 | 965:27 op `p.kind in (...)` | x all six: enum members |
| 909 | 982:44 getattr `sigspec.parameters.values` | x `toolz.__getattr__` |

### toolz.itertoolz, toolz.recipes

| # | Site | Callees and decisions |
|---|---|---|
| 929 | 67:23 `binop(result, elem)` | none (`operator.add`, `mul`, test functions) |
| 936 | 100:14 `key(item)` | `-> getter.<lambda1>`, `-> getter.<lambda2>`, `-> operator.itemgetter.__call__`, `-> toolz.itertoolz.first`, `-> toolz.itertoolz.second`, `-> toolz.functoolz.curry.__call__`; x `memoize.key` |
| 937 | 100:21 `d[key(item)](item)` | `-> <builtin>.list.append` |
| 950 | 128:21 `kwargs.get('key', None)` | `-> <builtin>.dict.get`; x `itertoolz.get` |
| 977 | 184:20 `iter(L2[0])` | `-> <builtin>.iter` |
| 981, 982, 983 | 193:15, 196:19, 200:27 `key(...)` | none: `merge_sorted`'s key is a client callable in every test and example (the tests' `identity` is test-defined); x `memoize.key` |
| 997 | 260:25 `seen_add(item)` | `-> <builtin>.set.add` |
| 998 | 264:22 `key(item)` | `-> toolz.functoolz.curry.__call__` (curried `EqualityHashKey`); x `memoize.key` |
| 1000 | 266:25 `seen_add(val)` | `-> <builtin>.set.add`, `-> EqualityHashKey.__hash__`, `-> EqualityHashKey.__eq__` (the add hashes the key and compares it with stored keys of the same hash) |
| 1005 | 304:21 op `item in seen` | x all six: client items |
| 1006 | 306:21 `seen_add(item)` | `-> <builtin>.set.add` |
| 1018 | 351:28 `itertools.islice(seq, n, None)` | `-> itertools.islice` |
| 1022 | 369:21 `iter(seq)` | `-> <builtin>.iter` |
| 1041 | 453:53 `operator.itemgetter(*ind)(seq)` | `-> operator.itemgetter.__call__` |
| 1044 | 459:29 `tuple(... for i in ind)` | `-> <builtin>.tuple` |
| 1050 | 486:41 `itertools.chain.from_iterable(seqs)` | `-> itertools.chain.from_iterable` |
| 1064 | 548:10 getitem `d[item]` | x all six: client items (and `countby`'s key results) |
| 1071 | 621:16 `key(item)` | `-> getter.<lambda1>`, `-> getter.<lambda2>`, `-> operator.itemgetter.__call__`, `-> curry.__call__`; x `memoize.key` |
| 1075 | 627:28 `init()` | `-> toolz.itertoolz.reduceby.<lambda1>`; client callables (`set`) are callbacks |
| 1077 | 628:21 `binop(d[k], item)` | none |
| 1079 | 659:17 `func(x)` | none; x `curry.func` |
| 1087 | 676:52 `itertools.tee(seq, n)` | `-> itertools.tee` |
| 1110 | 799:22 `tuple(... for item in ind)` | `-> <builtin>.tuple` |
| 1129, 1134, 1141, 1145 | 887:27, 894:27, 907:31, 915:31 `rightkey(item)` | `-> toolz.itertoolz.first`, `-> toolz.itertoolz.second`, `-> getter.<lambda1>`, `-> getter.<lambda2>`, `-> operator.itemgetter.__call__` |
| 1130 | 888:20 op `key in d` | x all six |
| 1142, 1146 | 908:21, 916:21 `seen(key)` | `-> <builtin>.set.add` |
| 1151 | 924:20 op `key not in seen_keys` | x all six |
| 1156 | 948:20 getitem `seqs[0]` | x all six |
| 1160 | 952:25 `kwargs.get('default', no_default)` | `-> <builtin>.dict.get`; x `itertoolz.get` |
| 1162 | 954:20 `zip(*seqs)` | `-> <builtin>.zip` |
| 1165 | 957:21 `kwargs.get('key', None)` | `-> <builtin>.dict.get`; x `itertoolz.get` |
| 1185 | 1021:20 `iter(seq)` | `-> <builtin>.iter` |
| 1192 | 1061:30 `Random(random_state)` | `-> random.Random` |
| 1203 | `recipes.py` 46:49 `itertools.groupby(seq, key=func)` | `-> itertools.groupby`; the key runs only when the client iterates the returned map: no edge; x `toolz.itertoolz.groupby` |

### toolz.sandbox, toolz.utils

| # | Site | Callees and decisions |
|---|---|---|
| 1209 | `core.py` 74:29 getattr `self._default_hashkey` | x all five: a class attribute (str) |
| 1212 | 77:27 `self.key(self.item)` | `-> toolz.itertoolz.first`, `-> getter.<lambda1>`, `-> getter.<lambda2>`, `-> operator.itemgetter.__call__`; x `memoize.key` |
| 1220 | 83:40 getattr `other.item` | x `toolz.__getattr__`: for the module `other._default_hashkey` (line 82) raises first |
| 1222 | 88:31 `self.__eq__(other)` | `-> EqualityHashKey.__eq__`; x `Compose.__eq__`, `curry.__eq__` |
| 1233 | 130:17 `len(first)` | `-> <builtin>.len` |
| 1240 | `parallel.py` 8:32 `functools.reduce(func, seq)` | `-> functools.reduce`; `fold`'s binop and combine are client callables in every test and example |
| 1242 | 10:32 `functools.reduce(func, seq, initial)` | `-> functools.reduce` |
| 1245 | 70:22 `map(functools.partial(_reduce, binop), chunks)` | `-> <builtin>.map` (the default of `map`), `-> toolz.sandbox.parallel._reduce` (`list(results)` consumes it in `fold`); a client `map` (`pool.map`) is a client callback |
| 1247 | 71:30 `functools.partial(_reduce, binop)` | `-> functools.partial`; x `_reduce` (called at the map) |
| 1248 | 74:22 `map(functools.partial(..., initial=default), chunks)` | as 1245 |
| 1250 | 75:30 `functools.partial(_reduce, binop, initial=default)` | `-> functools.partial`; x `_reduce` |
| 1255 | 83:20 `fold(combine, results, map=map, chunksize=chunksize)` | `-> toolz.sandbox.parallel.fold` |
| 1256 | `utils.py` 3:14 `lamda()` | `-> toolz.functoolz.apply` (`test_functoolz.py:54`) |

## Judgement calls in these answers

1. `check_valid` (684:13): every lambda registered on an admitted runtime,
   except the six package-object keys that nothing passes (187 edges).
2. Hash collisions in the registry (780:13): a client callable with a
   chosen hash forces the comparison with a stored curry key
   (`curry.__eq__`).
3. Compose's role admits its documented and tested members at any
   position (funcy); `operator.not_` only where `complement` puts it.
4. A lazy object returned to the client (`partitionby`) gives no callback
   edge; a map built and consumed in one function keeps its callback at
   the map call.
