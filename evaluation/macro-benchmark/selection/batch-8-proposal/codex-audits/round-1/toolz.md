Audited toolz, round 1: **17 missing edges and 2 ruling questions**.
No false or naming findings.

The audit team read all 462 function nodes and 16 module bodies, checking
all 828 existing edges: 803 function edges and 25 module edges. Counts
below are existing distinct outgoing edges, before proposed additions.
Repeated definitions sharing a graph name were all read.

Only source, dependency source, ground-truth records, and the permitted
checker were used. No package was run or imported; no files were changed.

The following function names have prefix `toolz.functoolz.`.

| Function | Edges checked |
|---|---:|
| `Compose.__call__` | 5 |
| `Compose.__doc__` | 2 |
| `Compose.__doc__.composed_doc` | 2 |
| `Compose.__eq__` | 3 |
| `Compose.__get__` | 1 |
| `Compose.__getstate__` | 0 |
| `Compose.__hash__` | 3 |
| `Compose.__init__` | 2 |
| `Compose.__name__` | 4 |
| `Compose.__ne__` | 1 |
| `Compose.__repr__` | 5 |
| `Compose.__setstate__` | 0 |
| `Compose.__signature__` | 3 |
| `Compose._combined_annotations` | 2 |
| `Compose._combined_annotations.annotations_of` | 5 |
| `Compose._get_annotate` | 0 |
| `Compose._get_annotate.annotate` | 3 |
| `InstanceProperty.__get__` | 10 |
| `InstanceProperty.__init__` | 1 |
| `InstanceProperty.__reduce__` | 0 |
| `_InstanceAnnotations.__get__` | 1 |
| `_InstanceAnnotations.__init__` | 0 |
| `_check_sigspec` — both definitions | 13 |
| `_restore_curry` | 9 |
| `apply` | 1 |
| `complement` | 1 |
| `compose` | 2 |
| `compose_left` | 2 |
| `curry.__call__` | 47 |
| `curry.__eq__` | 4 |
| `curry.__get__` | 1 |
| `curry.__hash__` | 6 |
| `curry.__init__` | 8 |
| `curry.__ne__` | 1 |
| `curry.__reduce__` | 11 |
| `curry.__repr__` | 2 |
| `curry.__signature__` | 10 |
| `curry.__str__` | 2 |
| `curry._should_curry` | 6 |
| `curry.args` | 0 |
| `curry.bind` | 2 |
| `curry.call` | 45 |
| `curry.func` | 0 |
| `curry.func_name` | 0 |
| `curry.keywords` | 0 |
| `do` | 0 |
| `excepts.__call__` | 1 |
| `excepts.__doc__` | 8 |
| `excepts.__init__` | 0 |
| `excepts.__name__` | 4 |
| `flip` | 0 |
| `has_keywords` | 3 |
| `has_varargs` | 3 |
| `identity` | 0 |
| `instanceproperty` | 2 |
| `is_arity` | 4 |
| `is_partial_args` | 2 |
| `is_valid_args` | 2 |
| `juxt.__call__` | 1 |
| `juxt.__getstate__` | 0 |
| `juxt.__init__` | 3 |
| `juxt.__setstate__` | 0 |
| `memoize` | 2 |
| `memoize.key` — all three definitions | 2 |
| `memoize.memof` | 3 |
| `num_required_args` | 3 |
| `pipe` | 2 |
| `return_none` | 0 |
| `thread_first` | 2 |
| `thread_first.evalform_front` | 2 |
| `thread_last` | 2 |
| `thread_last.evalform_back` | 2 |

The following table covers the other named functions and the seven lambdas
outside the signature registry.

| Function | Edges checked |
|---|---:|
| `tlz._build_tlz.TlzLoader.__init__` | 0 |
| `tlz._build_tlz.TlzLoader._load_toolz` | 5 |
| `tlz._build_tlz.TlzLoader.find_module` | 1 |
| `tlz._build_tlz.TlzLoader.load_module` | 3 |
| `tlz._build_tlz.TlzLoader.find_spec` | 2 |
| `tlz._build_tlz.TlzLoader.create_module` | 1 |
| `tlz._build_tlz.TlzLoader.exec_module` | 14 |
| `toolz.__getattr__` | 3 |
| `toolz._signatures.num_pos_args` | 2 |
| `toolz._signatures.get_exclude_keywords` | 4 |
| `toolz._signatures.signature_or_spec` | 1 |
| `toolz._signatures.expand_sig` | 5 |
| `toolz._signatures.create_signature_registry` | 8 |
| `toolz._signatures.check_valid` | 196 |
| `toolz._signatures._is_valid_args` | 4 |
| `toolz._signatures.check_partial` | 4 |
| `toolz._signatures._is_partial_args` | 4 |
| `toolz._signatures.check_arity` | 1 |
| `toolz._signatures._is_arity` | 5 |
| `toolz._signatures.check_varargs` | 1 |
| `toolz._signatures._has_varargs` | 5 |
| `toolz._signatures.check_keywords` | 1 |
| `toolz._signatures._has_keywords` | 5 |
| `toolz._signatures.check_required_args` | 1 |
| `toolz._signatures._num_required_args` | 4 |
| `toolz.curried.exceptions.merge_with` | 1 |
| `toolz.curried.exceptions.merge` | 1 |
| `toolz.dicttoolz._get_factory` | 4 |
| `toolz.dicttoolz.assoc` | 2 |
| `toolz.dicttoolz.assoc_in` | 1 |
| `toolz.dicttoolz.assoc_in.<lambda1>` | 0 |
| `toolz.dicttoolz.dissoc` | 6 |
| `toolz.dicttoolz.get_in` | 1 |
| `toolz.dicttoolz.itemfilter` | 2 |
| `toolz.dicttoolz.itemmap` | 5 |
| `toolz.dicttoolz.keyfilter` | 2 |
| `toolz.dicttoolz.keymap` | 7 |
| `toolz.dicttoolz.merge` | 5 |
| `toolz.dicttoolz.merge_with` | 10 |
| `toolz.dicttoolz.merge_with.<lambda1>` | 0 |
| `toolz.dicttoolz.update_in` | 5 |
| `toolz.dicttoolz.valfilter` | 2 |
| `toolz.dicttoolz.valmap` | 8 |
| `toolz.itertoolz._get` | 0 |
| `toolz.itertoolz._merge_sorted_binary` | 4 |
| `toolz.itertoolz._merge_sorted_binary_key` | 4 |
| `toolz.itertoolz.accumulate` | 2 |
| `toolz.itertoolz.concat` | 1 |
| `toolz.itertoolz.concatv` | 1 |
| `toolz.itertoolz.cons` | 1 |
| `toolz.itertoolz.count` | 3 |
| `toolz.itertoolz.diff` | 9 |
| `toolz.itertoolz.drop` | 1 |
| `toolz.itertoolz.first` | 2 |
| `toolz.itertoolz.frequencies` | 4 |
| `toolz.itertoolz.get` | 6 |
| `toolz.itertoolz.getter` | 3 |
| `toolz.itertoolz.getter.<lambda1>` | 0 |
| `toolz.itertoolz.getter.<lambda2>` | 0 |
| `toolz.itertoolz.groupby` | 13 |
| `toolz.itertoolz.groupby.<lambda1>` | 0 |
| `toolz.itertoolz.interleave` | 5 |
| `toolz.itertoolz.interpose` | 5 |
| `toolz.itertoolz.isdistinct` | 4 |
| `toolz.itertoolz.isiterable` | 1 |
| `toolz.itertoolz.iterate` | 0 |
| `toolz.itertoolz.join` | 13 |
| `toolz.itertoolz.last` | 1 |
| `toolz.itertoolz.mapcat` | 2 |
| `toolz.itertoolz.merge_sorted` | 5 |
| `toolz.itertoolz.nth` | 3 |
| `toolz.itertoolz.partition` | 3 |
| `toolz.itertoolz.partition_all` | 5 |
| `toolz.itertoolz.peek` | 3 |
| `toolz.itertoolz.peekn` | 4 |
| `toolz.itertoolz.pluck` | 5 |
| `toolz.itertoolz.random_sample` | 3 |
| `toolz.itertoolz.random_sample.<lambda1>` | 1 |
| `toolz.itertoolz.reduceby` | 7 |
| `toolz.itertoolz.reduceby.<lambda1>` | 0 |
| `toolz.itertoolz.remove` | 1 |
| `toolz.itertoolz.second` | 2 |
| `toolz.itertoolz.sliding_window` | 5 |
| `toolz.itertoolz.tail` | 2 |
| `toolz.itertoolz.take` | 1 |
| `toolz.itertoolz.take_nth` | 1 |
| `toolz.itertoolz.topk` | 6 |
| `toolz.itertoolz.unique` | 5 |
| `toolz.recipes.countby` | 4 |
| `toolz.recipes.partitionby` | 3 |
| `toolz.sandbox.core.EqualityHashKey.__eq__` | 0 |
| `toolz.sandbox.core.EqualityHashKey.__hash__` | 5 |
| `toolz.sandbox.core.EqualityHashKey.__init__` | 2 |
| `toolz.sandbox.core.EqualityHashKey.__ne__` | 1 |
| `toolz.sandbox.core.EqualityHashKey.__repr__` | 1 |
| `toolz.sandbox.core.EqualityHashKey.__str__` | 1 |
| `toolz.sandbox.core.unzip` | 9 |
| `toolz.sandbox.parallel._reduce` | 1 |
| `toolz.sandbox.parallel.fold` | 7 |
| `toolz.utils.raises` | 1 |

Every registry lambda below has prefix `toolz._signatures.`. Each body was
read; each returns literal `None` and has zero outgoing edges.

| Function | Edges | Function | Edges | Function | Edges | Function | Edges | Function | Edges |
|---|---:|---|---:|---|---:|---|---:|---|---:|
| `<lambda1>` | 0 | `<lambda2>` | 0 | `<lambda3>` | 0 | `<lambda4>` | 0 | `<lambda5>` | 0 |
| `<lambda6>` | 0 | `<lambda7>` | 0 | `<lambda8>` | 0 | `<lambda9>` | 0 | `<lambda10>` | 0 |
| `<lambda11>` | 0 | `<lambda12>` | 0 | `<lambda13>` | 0 | `<lambda14>` | 0 | `<lambda15>` | 0 |
| `<lambda16>` | 0 | `<lambda17>` | 0 | `<lambda18>` | 0 | `<lambda19>` | 0 | `<lambda20>` | 0 |
| `<lambda21>` | 0 | `<lambda22>` | 0 | `<lambda23>` | 0 | `<lambda24>` | 0 | `<lambda25>` | 0 |
| `<lambda26>` | 0 | `<lambda27>` | 0 | `<lambda28>` | 0 | `<lambda29>` | 0 | `<lambda30>` | 0 |
| `<lambda31>` | 0 | `<lambda32>` | 0 | `<lambda33>` | 0 | `<lambda34>` | 0 | `<lambda35>` | 0 |
| `<lambda36>` | 0 | `<lambda37>` | 0 | `<lambda38>` | 0 | `<lambda39>` | 0 | `<lambda40>` | 0 |
| `<lambda41>` | 0 | `<lambda42>` | 0 | `<lambda43>` | 0 | `<lambda44>` | 0 | `<lambda45>` | 0 |
| `<lambda46>` | 0 | `<lambda47>` | 0 | `<lambda48>` | 0 | `<lambda49>` | 0 | `<lambda50>` | 0 |
| `<lambda51>` | 0 | `<lambda52>` | 0 | `<lambda53>` | 0 | `<lambda54>` | 0 | `<lambda55>` | 0 |
| `<lambda56>` | 0 | `<lambda57>` | 0 | `<lambda58>` | 0 | `<lambda59>` | 0 | `<lambda60>` | 0 |
| `<lambda61>` | 0 | `<lambda62>` | 0 | `<lambda63>` | 0 | `<lambda64>` | 0 | `<lambda65>` | 0 |
| `<lambda66>` | 0 | `<lambda67>` | 0 | `<lambda68>` | 0 | `<lambda69>` | 0 | `<lambda70>` | 0 |
| `<lambda71>` | 0 | `<lambda72>` | 0 | `<lambda73>` | 0 | `<lambda74>` | 0 | `<lambda75>` | 0 |
| `<lambda76>` | 0 | `<lambda77>` | 0 | `<lambda78>` | 0 | `<lambda79>` | 0 | `<lambda80>` | 0 |
| `<lambda81>` | 0 | `<lambda82>` | 0 | `<lambda83>` | 0 | `<lambda84>` | 0 | `<lambda85>` | 0 |
| `<lambda86>` | 0 | `<lambda87>` | 0 | `<lambda88>` | 0 | `<lambda89>` | 0 | `<lambda90>` | 0 |
| `<lambda91>` | 0 | `<lambda92>` | 0 | `<lambda93>` | 0 | `<lambda94>` | 0 | `<lambda95>` | 0 |
| `<lambda96>` | 0 | `<lambda97>` | 0 | `<lambda98>` | 0 | `<lambda99>` | 0 | `<lambda100>` | 0 |
| `<lambda101>` | 0 | `<lambda102>` | 0 | `<lambda103>` | 0 | `<lambda104>` | 0 | `<lambda105>` | 0 |
| `<lambda106>` | 0 | `<lambda107>` | 0 | `<lambda108>` | 0 | `<lambda109>` | 0 | `<lambda110>` | 0 |
| `<lambda111>` | 0 | `<lambda112>` | 0 | `<lambda113>` | 0 | `<lambda114>` | 0 | `<lambda115>` | 0 |
| `<lambda116>` | 0 | `<lambda117>` | 0 | `<lambda118>` | 0 | `<lambda119>` | 0 | `<lambda120>` | 0 |
| `<lambda121>` | 0 | `<lambda122>` | 0 | `<lambda123>` | 0 | `<lambda124>` | 0 | `<lambda125>` | 0 |
| `<lambda126>` | 0 | `<lambda127>` | 0 | `<lambda128>` | 0 | `<lambda129>` | 0 | `<lambda130>` | 0 |
| `<lambda131>` | 0 | `<lambda132>` | 0 | `<lambda133>` | 0 | `<lambda134>` | 0 | `<lambda135>` | 0 |
| `<lambda136>` | 0 | `<lambda137>` | 0 | `<lambda138>` | 0 | `<lambda139>` | 0 | `<lambda140>` | 0 |
| `<lambda141>` | 0 | `<lambda142>` | 0 | `<lambda143>` | 0 | `<lambda144>` | 0 | `<lambda145>` | 0 |
| `<lambda146>` | 0 | `<lambda147>` | 0 | `<lambda148>` | 0 | `<lambda149>` | 0 | `<lambda150>` | 0 |
| `<lambda151>` | 0 | `<lambda152>` | 0 | `<lambda153>` | 0 | `<lambda154>` | 0 | `<lambda155>` | 0 |
| `<lambda156>` | 0 | `<lambda157>` | 0 | `<lambda158>` | 0 | `<lambda159>` | 0 | `<lambda160>` | 0 |
| `<lambda161>` | 0 | `<lambda162>` | 0 | `<lambda163>` | 0 | `<lambda164>` | 0 | `<lambda165>` | 0 |
| `<lambda166>` | 0 | `<lambda167>` | 0 | `<lambda168>` | 0 | `<lambda169>` | 0 | `<lambda170>` | 0 |
| `<lambda171>` | 0 | `<lambda172>` | 0 | `<lambda173>` | 0 | `<lambda174>` | 0 | `<lambda175>` | 0 |
| `<lambda176>` | 0 | `<lambda177>` | 0 | `<lambda178>` | 0 | `<lambda179>` | 0 | `<lambda180>` | 0 |
| `<lambda181>` | 0 | `<lambda182>` | 0 | `<lambda183>` | 0 | `<lambda184>` | 0 | `<lambda185>` | 0 |
| `<lambda186>` | 0 | `<lambda187>` | 0 | `<lambda188>` | 0 | `<lambda189>` | 0 | `<lambda190>` | 0 |
| `<lambda191>` | 0 | `<lambda192>` | 0 | `<lambda193>` | 0 | `<lambda194>` | 0 | `<lambda195>` | 0 |
| `<lambda196>` | 0 | `<lambda197>` | 0 | `<lambda198>` | 0 | `<lambda199>` | 0 | `<lambda200>` | 0 |
| `<lambda201>` | 0 | `<lambda202>` | 0 | `<lambda203>` | 0 | `<lambda204>` | 0 | `<lambda205>` | 0 |
| `<lambda206>` | 0 | `<lambda207>` | 0 | `<lambda208>` | 0 | `<lambda209>` | 0 | `<lambda210>` | 0 |
| `<lambda211>` | 0 | `<lambda212>` | 0 | `<lambda213>` | 0 | `<lambda214>` | 0 | `<lambda215>` | 0 |
| `<lambda216>` | 0 | `<lambda217>` | 0 | `<lambda218>` | 0 | `<lambda219>` | 0 | `<lambda220>` | 0 |
| `<lambda221>` | 0 | `<lambda222>` | 0 | `<lambda223>` | 0 | `<lambda224>` | 0 | `<lambda225>` | 0 |
| `<lambda226>` | 0 | `<lambda227>` | 0 | `<lambda228>` | 0 | `<lambda229>` | 0 | `<lambda230>` | 0 |
| `<lambda231>` | 0 | `<lambda232>` | 0 | `<lambda233>` | 0 | `<lambda234>` | 0 | `<lambda235>` | 0 |
| `<lambda236>` | 0 | `<lambda237>` | 0 | `<lambda238>` | 0 | `<lambda239>` | 0 | `<lambda240>` | 0 |
| `<lambda241>` | 0 | `<lambda242>` | 0 | `<lambda243>` | 0 | `<lambda244>` | 0 | `<lambda245>` | 0 |
| `<lambda246>` | 0 | `<lambda247>` | 0 | `<lambda248>` | 0 | `<lambda249>` | 0 | `<lambda250>` | 0 |
| `<lambda251>` | 0 | `<lambda252>` | 0 | `<lambda253>` | 0 | `<lambda254>` | 0 | `<lambda255>` | 0 |
| `<lambda256>` | 0 | `<lambda257>` | 0 | `<lambda258>` | 0 | `<lambda259>` | 0 | `<lambda260>` | 0 |
| `<lambda261>` | 0 | `<lambda262>` | 0 | `<lambda263>` | 0 | `<lambda264>` | 0 | `<lambda265>` | 0 |
| `<lambda266>` | 0 | `<lambda267>` | 0 | `<lambda268>` | 0 | `<lambda269>` | 0 | `<lambda270>` | 0 |
| `<lambda271>` | 0 | `<lambda272>` | 0 | `<lambda273>` | 0 | `<lambda274>` | 0 | `<lambda275>` | 0 |
| `<lambda276>` | 0 | `<lambda277>` | 0 | `<lambda278>` | 0 | `<lambda279>` | 0 | `<lambda280>` | 0 |
| `<lambda281>` | 0 | `<lambda282>` | 0 | `<lambda283>` | 0 | `<lambda284>` | 0 | `<lambda285>` | 0 |
| `<lambda286>` | 0 | `<lambda287>` | 0 | `<lambda288>` | 0 | `<lambda289>` | 0 | `<lambda290>` | 0 |

Module bodies were also checked.

| Module | Edges checked |
|---|---:|
| `tlz` | 0 |
| `tlz._build_tlz` | 3 |
| `toolz` | 1 |
| `toolz._signatures` | 2 |
| `toolz.compatibility` | 3 |
| `toolz.curried` | 1 |
| `toolz.curried.operator` | 6 |
| `toolz.curried.exceptions` | 1 |
| `toolz.dicttoolz` | 0 |
| `toolz.functoolz` | 7 |
| `toolz.itertoolz` | 1 |
| `toolz.recipes` | 0 |
| `toolz.sandbox` | 0 |
| `toolz.sandbox.core` | 0 |
| `toolz.sandbox.parallel` | 0 |
| `toolz.utils` | 0 |

For the findings, source paths are relative to
`macro-benchmark/projects/toolz/`. `cget`, `cmap`, `cpluck`, and `csorted`
denote the corresponding functions in `toolz.curried`. Witnesses were
derived from source and were not executed.

Rule abbreviations refer to `macro-benchmark/README.md`:

| Abbreviation | Rule |
|---|---|
| FO | “Factory outputs (B2)”: admitted factory outputs use public arguments; examples do not freeze their arguments; one-argument `compose` may return an admitted input. |
| LC | B5 and “Limits of the site finder”: a package-created lazy iterator calls its package callback at the package site consuming it. |
| HE | “Call sites and candidates”: dictionary/set operations hash keys and compare distinct keys with equal hashes. |
| GF | Ground-truth conventions: generator-function calls count even when their results are not consumed. |

Each missing row denotes the edge from its Caller to its Edge target.
None concerns an open path set or an open receiver set.

| Id | Kind | Caller | Site (file:line:col) | Edge | Evidence | Rule |
|---|---|---|---|---|---|---|
| M01 | missing | `toolz.dicttoolz.valmap` | `toolz/dicttoolz.py:85:14` | `toolz.functoolz.curry.__call__` | `doc/source/streaming-analytics.rst:91,101` passes a `compose` output as `func`. `valmap(compose(cpluck(0)), {"a": [(1,2)]})` uses the singleton return at `functoolz.py:673`; `dict.update` consumes the map and invokes that curry. | FO, LC |
| M02 | missing | `toolz.dicttoolz.valmap` | `toolz/dicttoolz.py:85:14` | `toolz.itertoolz.frequencies` | Same documented output role. `README.rst:67` admits `frequencies` as a compose input. `valmap(compose(frequencies), {"a": [1,1]})` invokes it through the singleton return at `functoolz.py:673`. | FO, LC |
| M03 | missing | `toolz.dicttoolz.valmap` | `toolz/dicttoolz.py:85:14` | `toolz.itertoolz.concat` | Same documented output role. `doc/source/parallelism.rst:53` admits `concat` as a compose input. `valmap(compose(concat), {"a": [[1],[2]]})` calls it, although the resulting generator is only stored. | FO, LC, GF |
| M04 | missing | `toolz.itertoolz.groupby` | `toolz/itertoolz.py:100:10` | `toolz.functoolz.curry.__hash__` | `streaming-analytics.rst:87` admits the curried-get output as key. In `groupby(cget(), [0,0])`, `key(item)` underapplies `get`; `functoolz.py:305–308,338` returns a new curry, which the dictionary hashes. | FO, B2, HE |
| M05 | missing | `toolz.itertoolz.groupby` | `toolz/itertoolz.py:100:10` | `toolz.functoolz.curry.__eq__` | M04 produces distinct curries with the same wrapped function, `(0,)` arguments, and empty keywords. Their hashes agree and the second lookup compares them; see `functoolz.py:291–298`. | FO, B2, HE |
| M06 | missing | `toolz.itertoolz.join` | `toolz/itertoolz.py:888:20` | `toolz.functoolz.curry.__hash__` | `bench/test_join.py:18` admits a curried-get key; the settled F2 decision joins the left/right key roles. `join(cget(), [0], cget(), [0])` produces curry keys. `key in d` hashes the right key. | B2, FO, HE; settled F2 |
| M07 | missing | `toolz.itertoolz.join` | `toolz/itertoolz.py:888:20` | `toolz.functoolz.curry.__eq__` | M06 produces distinct equal left/right curry keys. Dictionary lookup compares them by `functoolz.py:296–298`. | B2, FO, HE; settled F2 |
| M08 | missing | `toolz.itertoolz.reduceby` | `toolz/itertoolz.py:622:14` | `toolz.functoolz.curry.__hash__` | `streaming-analytics.rst:155` admits the curried-get key. `reduceby(cget(), lambda a,b: a+b, [0,0])` produces underapplied curries at `key(item)`; `k not in d` hashes them. | FO, B2, HE |
| M09 | missing | `toolz.itertoolz.reduceby` | `toolz/itertoolz.py:622:14` | `toolz.functoolz.curry.__eq__` | M08 successfully stores the first curry key; the second is distinct but equal and is compared during lookup. Equality follows `functoolz.py:296–298`. | FO, B2, HE |
| M10 | missing | `toolz.itertoolz.unique` | `toolz/itertoolz.py:265:20` | `toolz.functoolz.curry.__hash__` | `sandbox/core.py:13,39` documents a curry factory output as key. `unique([0,0], key=curry(EqualityHashKey))` leaves `item` unbound in `EqualityHashKey(key, item)` (`core.py:64`), so each key call returns a curry. Set membership hashes it. | FO, B2, HE |
| M11 | missing | `toolz.itertoolz.unique` | `toolz/itertoolz.py:265:20` | `toolz.functoolz.curry.__eq__` | M10 produces distinct equal curries wrapping `EqualityHashKey` with `(0,)`; the second membership check compares them. See `functoolz.py:291–298`. | FO, B2, HE |
| M12 | missing | `toolz.itertoolz.frequencies` | `toolz/itertoolz.py:547:17` | `toolz.functoolz.curry.__call__` | `README.rst:67` documents composition of `frequencies` with curried map; `streaming-analytics.rst:38` admits curried get as map callback. `compose(frequencies, cmap(cget(0)))([(1,2)])` forwards the package-created map to this consuming loop. | FO, B2, LC |
| M13 | missing | `toolz.itertoolz.frequencies` | `toolz/itertoolz.py:548:10` | `toolz.functoolz.curry.__hash__` | Vary M12’s admitted get factory arguments: `compose(frequencies, cmap(cget()))([0,0])`. Consumption produces underapplied curries (`functoolz.py:305–308,338`), which `d[item] += 1` hashes. | FO, B2, LC, HE |
| M14 | missing | `toolz.itertoolz.frequencies` | `toolz/itertoolz.py:548:10` | `toolz.functoolz.curry.__eq__` | M13 produces distinct equal curries; the second defaultdict lookup compares them using `functoolz.py:296–298`. | FO, B2, LC, HE |
| M15 | missing | `toolz.functoolz.curry.__call__` | `toolz/functoolz.py:305:33` | `toolz.functoolz.curry.__call__` | `compose(csorted, cmap(cget(0)))([(2,), (1,)])` makes a package-created map, then the package’s partial calls `sorted`, which consumes it and invokes the get curry. Curry outputs are admitted in compositions by `README.rst:67`; the map callback by `streaming-analytics.rst:38`; sorted is wrapped at `curried/__init__.py:92`. | FO, B2, LC |
| M16 | missing | `toolz.functoolz.curry.__call__` | `toolz/functoolz.py:305:33` | `toolz.itertoolz.getter.<lambda1>` | `compose(csorted, cpluck([0]))([[2],[1]])`. `streaming-analytics.rst:91` admits the pluck curry in compose. `itertoolz.py:796–797` builds the map; `[0]` selects the lambda at `808`. The sorted partial consumes it. | FO, B2, LC |
| M17 | missing | `toolz.functoolz.curry.__call__` | `toolz/functoolz.py:305:33` | `toolz.itertoolz.getter.<lambda2>` | M16 with `cpluck([])` selects the lambda at `itertoolz.py:812`. The sorted partial consumes the package-created map. | FO, B2, LC |
| R01 | ruling | `toolz.functoolz.Compose.__call__` | `toolz/functoolz.py:504:25` | Candidate: `toolz.functoolz.identity` | `toolz/tests/test_functoolz.py:702` passes compose outputs into compose. `compose()` returns identity at `functoolz.py:670–671`, so `compose(lambda x:x, compose())(1)` reaches this edge if tested factory outputs generalize. **Does FO extend to test-only factory evidence, including another output branch?** FO explicitly says “When documentation names”; B2 separately admits tested values. No documented nested-compose example was found. | B2, B3, FO |
| R02 | ruling | `toolz.functoolz.memoize.memof`; `toolz.functoolz.memoize.key` | `toolz/functoolz.py:458:25`; `toolz/functoolz.py:449:30` | Candidates: `memof → {curry, Compose}.{__hash__, __eq__}`; `memoize.key → {curry, Compose}.__hash__` | `test_functoolz.py:100–106` admits a curry as memoize’s wrapped function. Proposed witness: `m=memoize(toolz.curried.valmap)`, then repeated `m(compose(f,g))`, or `m(cget(0))`; keyword forms exercise `key`’s frozenset. `memof` forwards arguments at `functoolz.py:462`, and `streaming-analytics.rst:91` admits compose output at valmap’s `func`. **Do wrapper inputs inherit the wrapped callable’s package-value roles without wrapper-side admission evidence?** No test or document supplying these package-valued arguments to `memof` was found. Six candidate edges depend on that decision. | B2/B3/B5; pymysql ruling on parameter roles and forwarding |

The underapplication witnesses return successfully constructed curries.
They do not reuse objects left half-changed by a failed call.

For M15–M17, dependency source confirms the consumption chain:
CPython 3.14.10’s `_functoolsmodule.c:576` calls the wrapped function;
`Python/bltinmodule.c:2669` materializes the sorted input; its map iterator
calls the stored callback at `:1522`.

The permitted checker reported no undecided sites. The earlier audit’s
F1/F2 corrections and the ruled 193 registry targets remain accounted for.

| Kind | Total |
|---|---:|
| missing | **17** |
| false | **0** |
| naming | **0** |
| ruling | **2** |
| unsure | **0** |

All 17 missing edges are inside the package and outside open sets.
R01 and R02 are not included in the missing-edge total pending rulings.