import pytest
from programs import callees, main_graph

CLASSES = """
import collections
import functools
import heapq
import itertools
import math
import operator
class Item:
    def ping(self): pass
class Other:
    def ping(self): pass
class Iter:
    def __iter__(self): return self
    def __next__(self): return Item()
class Able:
    def __iter__(self): return Iter()
    def __len__(self): return 0
class OtherIter:
    def __iter__(self): return self
    def __next__(self): return Other()
class OtherAble:
    def __iter__(self): return OtherIter()
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, CLASSES + source)


def inside(graph, caller):
    return [c for c in callees(graph, caller) if c.startswith("main.")]


def test_a_lazy_object_is_advanced_where_an_analysed_scope_advances_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def make(x):
    return itertools.islice(x, 2)
def use(y):
    return list(y)
use(make(Able()))
""",
    )

    assert inside(graph, "main.make") == ["main.Able.__iter__"]
    assert inside(graph, "main.use") == ["main.Iter.__next__"]


def test_a_lazy_object_that_is_returned_or_stored_is_not_advanced(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Holder:
    pass
def only(x):
    return itertools.islice(x, 2)
def store(holder, x):
    holder.it = itertools.dropwhile(bool, x)
def obtain(x):
    return iter(itertools.takewhile(bool, x))
only(Able())
store(Holder(), Able())
obtain(Able())
""",
    )

    for caller in ("main.only", "main.store", "main.obtain"):
        assert inside(graph, caller) == ["main.Able.__iter__"], caller


@pytest.mark.parametrize(
    "advance",
    [
        "next(it)",
        "it.__next__()",
        "step = it.__next__\n    step()",
        "for each in it: pass",
        "first, *rest = it",
        "sorted(it)",
        "set(it)",
        "collections.deque(it)",
        '"".join(it)',
        "sum(it)",
        "functools.reduce(operator.add, it)",
    ],
)
def test_every_way_of_advancing_advances_the_lazy_object(tmp_path, advance):
    graph = graph_of(
        tmp_path,
        f"""
def make(x):
    return itertools.islice(x, 2)
def use(it):
    {advance}
use(make(Able()))
""",
    )

    assert "main.Iter.__next__" in callees(graph, "main.use")
    assert "main.Iter.__next__" not in callees(graph, "main.make")


def test_a_lazy_object_inside_another_is_advanced_when_the_outer_is(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def nest(x):
    return itertools.takewhile(bool, itertools.islice(x, 3))
def use(it):
    for item in it:
        item.ping()
use(nest(Able()))
""",
    )

    assert inside(graph, "main.nest") == ["main.Able.__iter__"]
    assert inside(graph, "main.use") == ["main.Item.ping", "main.Iter.__next__"]


@pytest.mark.parametrize(
    "make",
    [
        "itertools.islice(x, 2)",
        "itertools.dropwhile(bool, x)",
        "itertools.takewhile(bool, x)",
        "itertools.filterfalse(None, x)",
        "itertools.compress(x, [1])",
        "itertools.cycle(x)",
        "itertools.accumulate(x)",
        "itertools.chain(x, x)",
        "itertools.chain.from_iterable([x])",
        "itertools.tee(x)[0]",
        "heapq.merge(x)",
    ],
)
def test_items_pass_through_the_lazy_objects_that_keep_them(tmp_path, make):
    graph = graph_of(
        tmp_path,
        f"""
def use(x):
    for item in {make}:
        item.ping()
use(Able())
""",
    )

    assert "main.Item.ping" in callees(graph, "main.use")


@pytest.mark.parametrize("make", ["itertools.batched(x, 2)", "itertools.pairwise(x)"])
def test_tuples_of_items_pass_through_batched_and_pairwise(tmp_path, make):
    graph = graph_of(
        tmp_path,
        f"""
def use(x):
    for group in {make}:
        for item in group:
            item.ping()
use(Able())
""",
    )

    assert "main.Item.ping" in callees(graph, "main.use")


def test_zip_longest_keeps_each_position(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use(x, y):
    for a, b in itertools.zip_longest(x, y):
        a.ping()
use(Able(), OtherAble())
""",
    )

    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Item.ping",
        "main.Iter.__next__",
        "main.OtherAble.__iter__",
        "main.OtherIter.__next__",
    ]


@pytest.mark.parametrize(
    "operation",
    [
        "itertools.product(x)",
        "itertools.combinations(x, 1)",
        "itertools.combinations_with_replacement(x, 1)",
        "itertools.permutations(x)",
        "math.dist(x, x)",
    ],
)
def test_materializers_iterate_at_the_call_and_ask_the_length(tmp_path, operation):
    graph = graph_of(
        tmp_path,
        f"""
def make(x):
    return {operation}
def use(made):
    list(made)
use(make(Able()))
""",
    )

    assert inside(graph, "main.make") == [
        "main.Able.__iter__",
        "main.Able.__len__",
        "main.Iter.__next__",
    ]
    assert inside(graph, "main.use") == []


@pytest.mark.parametrize(
    "call",
    [
        "functools.reduce(operator.add, x)",
        "math.sumprod(x, x)",
        "math.fsum(x)",
        "math.prod(x)",
        "operator.countOf(x, 1)",
        "operator.indexOf(x, 1)",
    ],
)
def test_eager_operations_iterate_at_the_call(tmp_path, call):
    graph = graph_of(tmp_path, f"def use(x):\n    {call}\nuse(Able())\n")

    assert inside(graph, "main.use") == ["main.Able.__iter__", "main.Iter.__next__"]


@pytest.mark.parametrize("name", ["nlargest", "nsmallest"])
def test_nlargest_asks_the_length_and_iterates_its_iterator_again(tmp_path, name):
    graph = graph_of(
        tmp_path,
        f"""
class Long:
    def __iter__(self): return Iter()
    def __len__(self): return 5
def use(x):
    heapq.{name}(2, x)
use(Long())
""",
    )

    assert inside(graph, "main.use") == [
        "main.Iter.__iter__",
        "main.Iter.__next__",
        "main.Long.__iter__",
        "main.Long.__len__",
    ]


def test_chain_from_iterable_takes_the_inner_iterables_when_advanced(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Outer:
    def __iter__(self): return OuterIter()
class OuterIter:
    def __iter__(self): return self
    def __next__(self): return Able()
def flat(x):
    return itertools.chain.from_iterable(x)
def use(it):
    list(it)
use(flat(Outer()))
""",
    )

    assert inside(graph, "main.flat") == ["main.Outer.__iter__"]
    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Iter.__next__",
        "main.OuterIter.__next__",
    ]


def test_tee_iterates_the_iterator_again_and_its_copies_are_lazy(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def split(x):
    first, second = itertools.tee(x)
    return first
def use(it):
    list(it)
use(split(Able()))
""",
    )

    assert inside(graph, "main.split") == ["main.Able.__iter__", "main.Iter.__iter__"]
    assert inside(graph, "main.use") == ["main.Iter.__next__"]


def test_starmap_makes_a_tuple_of_each_argument_bundle_when_advanced(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Bundles:
    def __iter__(self): return self
    def __next__(self): return Able()
def f(*args): pass
def make(x):
    return itertools.starmap(f, x)
def use(it):
    list(it)
use(make(Bundles()))
""",
    )

    assert inside(graph, "main.make") == ["main.Bundles.__iter__"]
    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Able.__len__",
        "main.Bundles.__next__",
        "main.Iter.__next__",
    ]


def test_advancing_a_group_advances_the_source_of_groupby(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def first(x):
    key, group = next(itertools.groupby(x))
    return group
def use(group):
    for item in group:
        item.ping()
use(first(Able()))
""",
    )

    assert inside(graph, "main.first") == ["main.Able.__iter__", "main.Iter.__next__"]
    assert inside(graph, "main.use") == ["main.Item.ping", "main.Iter.__next__"]


def test_merge_and_chain_take_their_iterables_when_advanced(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def merged(x, y):
    return heapq.merge(x, y), itertools.chain(x, y)
def use(pair):
    for each in pair:
        list(each)
use(merged(Able(), OtherAble()))
""",
    )

    assert inside(graph, "main.merged") == []
    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Iter.__iter__",
        "main.Iter.__next__",
        "main.OtherAble.__iter__",
        "main.OtherIter.__iter__",
        "main.OtherIter.__next__",
    ]


def test_consuming_a_lazy_object_asks_no_length_of_its_source(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use(x):
    list(itertools.islice(x, 2))
use(Able())
""",
    )

    assert "main.Able.__len__" not in callees(graph, "main.use")


def test_an_alias_is_the_operation_and_a_package_function_of_its_name_is_not(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
from itertools import islice as cut
def islice(x, n):
    return x
def aliased(x):
    list(cut(x, 2))
def own(x):
    list(islice(x, 2))
aliased(Able())
own(Iter())
""",
    )

    assert inside(graph, "main.aliased") == ["main.Able.__iter__", "main.Iter.__next__"]
    assert inside(graph, "main.own") == [
        "main.Iter.__iter__",
        "main.Iter.__next__",
        "main.islice",
    ]


def test_the_sequence_protocol_and_metaclass_protocols_are_iterated(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Seq:
    def __getitem__(self, index): return Item()
class Meta(type):
    def __iter__(cls): return Iter()
class ByMeta(metaclass=Meta):
    pass
def use(x, y):
    list(itertools.islice(x, 2))
    list(itertools.islice(y, 2))
use(Seq(), ByMeta)
""",
    )

    assert inside(graph, "main.use") == [
        "main.Iter.__next__",
        "main.Meta.__iter__",
        "main.Seq.__getitem__",
    ]


@pytest.mark.parametrize(
    "call",
    [
        "itertools.repeat(x)",
        "itertools.repeat(x, 3)",
        "itertools.count(x)",
        "collections.ChainMap(x)",
        "heapq.heapify(names)",
    ],
)
def test_operations_that_do_not_iterate_their_argument(tmp_path, call):
    graph = graph_of(
        tmp_path,
        f"""
class Names(list):
    def __iter__(self): return Iter()
def use(x, names):
    {call}
use(Able(), Names())
""",
    )

    assert inside(graph, "main.use") == []


def test_repeat_gives_its_object_where_it_is_advanced(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def make():
    return itertools.repeat(Item(), 2)
def use(items):
    for item in items:
        item.ping()
    for other in itertools.chain(itertools.repeat(Other())):
        other.ping()
use(make())
""",
    )

    assert inside(graph, "main.make") == []
    assert inside(graph, "main.use") == ["main.Item.ping", "main.Other.ping"]


def test_limit_list_concatenation_iterates_a_list_subclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Names(list):
    def __iter__(self): return Iter()
def use(names):
    names + names
use(Names())
""",
    )

    assert "main.Names.__iter__" in callees(graph, "main.use")


def test_limit_a_count_of_zero_still_iterates(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use(x):
    itertools.tee(x, 0)
    itertools.product(x, repeat=0)
    list(itertools.islice(x, 0))
use(Able())
""",
    )

    assert "main.Iter.__next__" in callees(graph, "main.use")


def test_limit_nlargest_of_one_asks_the_length(tmp_path):
    graph = graph_of(tmp_path, "def use(x):\n    heapq.nlargest(1, x)\nuse(Able())\n")

    assert "main.Able.__len__" in callees(graph, "main.use")


def test_limit_merge_advances_by_the_special_method(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def other():
    return Item()
class Shadowed:
    def __init__(self):
        self.__next__ = other
    def __iter__(self): return self
    def __next__(self): return Item()
def use(x):
    list(heapq.merge(x))
use(Shadowed())
""",
    )

    assert "main.Shadowed.__next__" in callees(graph, "main.use")
    assert "main.other" not in callees(graph, "main.use")


def test_a_site_of_a_lazy_and_an_eager_operation_gives_both(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def pick(flag):
    return itertools.tee if flag else sorted
def use(x, flag):
    result = pick(flag)(x)
    return result
def later(result):
    for each in result:
        list(each)
later(use(Able(), True))
""",
    )

    assert "main.Iter.__next__" in callees(graph, "main.use")
    assert "main.Iter.__iter__" in callees(graph, "main.use")


CYCLES = {
    "main.py": """
import heapq
import itertools
import parts
class Holder:
    def __init__(self, it):
        self.it = it
    def step(self):
        self.it = itertools.islice(self.it, 1)
        for x in self.it:
            x.ping()
def base():
    return SOURCE
def loop(xs):
    acc = base()
    for x in xs:
        acc = itertools.chain(acc, x)
    return list(acc)
def tees(x):
    a, b = itertools.tee(x)
    c, d = itertools.tee(a)
    return list(c), list(d), list(b), list(b)
def merged(x):
    return list(heapq.merge(x, itertools.chain.from_iterable([x])))
Holder(parts.It()).step()
loop([parts.It(), parts.It()])
tees(parts.It())
merged(parts.It())
SOURCE = parts.It()
""",
    "parts.py": """
class It:
    def __iter__(self): return self
    def __next__(self): return It()
    def ping(self): pass
""",
}


def test_cycles_of_lazy_objects_end_and_give_their_edges(tmp_path):
    from programs import call_graph

    graph = call_graph(tmp_path, CYCLES)

    assert inside_of(graph, "main.loop") == ["parts.It.__iter__", "parts.It.__next__"]
    assert inside_of(graph, "main.Holder.step") == [
        "parts.It.__iter__",
        "parts.It.__next__",
        "parts.It.ping",
    ]
    assert inside_of(graph, "main.tees") == ["parts.It.__iter__", "parts.It.__next__"]
    assert inside_of(graph, "main.merged") == ["parts.It.__iter__", "parts.It.__next__"]


def inside_of(graph, caller):
    return [c for c in callees(graph, caller) if c.startswith("parts.")]


@pytest.mark.parametrize("cap", [1, 3, None])
def test_cycles_of_lazy_objects_give_one_result_in_every_order(
    tmp_path, monkeypatch, cap
):
    import itertools

    from programs import write
    from test_order_independence import orders, whole_output

    from pycg.analysis import solver

    write(tmp_path, CYCLES)
    expected = None
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        for entries in itertools.permutations(["main.py", "parts.py"]):
            found = whole_output(tmp_path, entries, cap=cap)
            if expected is None:
                expected = found
            assert found == expected, (name, entries)


@pytest.mark.parametrize(
    ("make", "first", "second"),
    [
        ("itertools.product(x, y)", ["main.Item.ping"], ["main.Other.ping"]),
        (
            "itertools.zip_longest(x, y, x, y, x, y)",
            ["main.Item.ping"],
            ["main.Other.ping"],
        ),
        (
            "itertools.product(x, y, repeat=2)",
            ["main.Item.ping", "main.Other.ping"],
            ["main.Item.ping", "main.Other.ping"],
        ),
        (
            "itertools.product(*[x, y])",
            ["main.Item.ping", "main.Other.ping"],
            ["main.Item.ping", "main.Other.ping"],
        ),
    ],
)
def test_the_tuples_of_product_and_zip_longest_keep_their_positions(
    tmp_path, make, first, second
):
    graph = graph_of(
        tmp_path,
        f"""
def use(x, y):
    for a, b, *rest in {make}:
        a.ping()
def other(x, y):
    for a, b, *rest in {make}:
        b.ping()
use(Able(), OtherAble())
other(Able(), OtherAble())
""",
    )

    assert [c for c in inside(graph, "main.use") if c.endswith("ping")] == first
    assert [c for c in inside(graph, "main.other") if c.endswith("ping")] == second


def test_dist_reads_a_tuple_subclass_without_iterating_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Point(tuple):
    def __iter__(self): return Iter()
    def __len__(self): return 2
def use(p, q):
    math.dist(p, p)
    math.dist(q, q)
use(Point(), Able())
""",
    )

    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Able.__len__",
        "main.Iter.__next__",
    ]


def test_merge_takes_the_iterator_again_for_the_last_source(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use(x):
    list(heapq.merge(x))
use(Able())
""",
    )

    assert inside(graph, "main.use") == [
        "main.Able.__iter__",
        "main.Iter.__iter__",
        "main.Iter.__next__",
    ]


def test_fillvalue_and_initial_are_values_of_the_result(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def filled():
    next(itertools.zip_longest([], [0], fillvalue=Item()))[0].ping()
def started():
    next(itertools.accumulate([], initial=Other())).ping()
filled()
started()
""",
    )

    assert inside(graph, "main.filled") == ["main.Item.ping"]
    assert inside(graph, "main.started") == ["main.Other.ping"]


@pytest.mark.parametrize(
    ("make", "keyed"),
    [
        ("itertools.groupby(x)", False),
        ("itertools.groupby(x, key=None)", False),
        ("itertools.groupby(x, None)", False),
        ("itertools.groupby(x, **options)", False),
        ("itertools.groupby(x, key=len)", True),
    ],
)
def test_groupby_without_a_key_function_gives_the_items_as_keys(tmp_path, make, keyed):
    graph = graph_of(
        tmp_path,
        f"""
def use(x, options):
    for key, group in {make}:
        key.ping()
use(Able(), {{}})
""",
    )

    pinged = "main.Item.ping" in callees(graph, "main.use")
    assert pinged is not keyed


def test_zip_longest_of_many_arguments_keeps_a_trailing_position(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use(x, y):
    for a, b, c, d, e, f, g in itertools.zip_longest(x, x, x, x, x, y, x):
        f.ping()
use(Able(), OtherAble())
""",
    )

    assert [c for c in inside(graph, "main.use") if c.endswith("ping")] == [
        "main.Other.ping"
    ]


ZIP_LONGEST_OF_TWO_ARITIES = """
def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.zip_longest)
class C(metaclass=M):
    __new__ = Factory()
class Delay:
    def __call__(self, x): return x
def use(factory):
    it = factory([b, b])
    first, *more = next(it)
    first()
    for pair in Delay()(it):
        pair[1]()
use(itertools.zip_longest)
use(C)
"""


def test_tuples_of_calls_of_two_arities_at_two_sites(tmp_path):
    graph = graph_of(tmp_path, ZIP_LONGEST_OF_TWO_ARITIES)

    assert inside(graph, "main.use") == [
        "main.Delay.__call__",
        "main.M.__iter__",
        "main.b",
    ]


@pytest.mark.parametrize("cap", [3, None])
def test_tuples_of_calls_of_two_arities_in_every_order(tmp_path, monkeypatch, cap):
    from programs import write
    from test_order_independence import orders, whole_output

    from pycg.analysis import solver

    write(tmp_path, {"main.py": CLASSES + ZIP_LONGEST_OF_TWO_ARITIES})
    expected = None
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        found = whole_output(tmp_path, ["main.py"], cap=cap)
        if expected is None:
            expected = found
        assert found == expected, name


def test_unpacked_compress_keeps_its_data_and_not_its_selectors(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def use():
    for item in itertools.compress(*([Item()], [Other()])):
        item.ping()
use()
""",
    )

    assert "main.Item.ping" in callees(graph, "main.use")
    assert "main.Other.ping" not in callees(graph, "main.use")


@pytest.mark.parametrize(
    "make", ["itertools.zip_longest([1, 2])", "itertools.groupby([1, 2])"]
)
def test_two_advances_of_one_object_give_the_same_results_in_every_order(
    tmp_path, monkeypatch, make
):
    from programs import write
    from test_order_independence import orders, whole_output

    from pycg.analysis import solver

    write(
        tmp_path,
        {
            "main.py": f"""
import itertools
def use(it):
    first = next(it)
    second = next(it)
    return first, second
use({make})
"""
        },
    )
    for cap in (3, None):
        expected = None
        for name, order in orders().items():
            monkeypatch.setattr(solver.Solver, "order", order)
            found = whole_output(tmp_path, ["main.py"], cap=cap)
            if expected is None:
                expected = found
            assert found == expected, (cap, name)


SHARED_ORIGIN = """
class MetaA(type):
    def __iter__(cls): return iter(())
class MetaB(type):
    def __iter__(cls): return iter(())
class Factory:
    __call__ = staticmethod(itertools.chain)
class One(metaclass=MetaA):
    __new__ = Factory()
class Two(metaclass=MetaB):
    __new__ = Factory()
def use(factory):
    return list(factory(()))
use(One)
use(Two)
"""


def test_calls_that_share_an_origin_give_every_argument(tmp_path):
    graph = graph_of(tmp_path, SHARED_ORIGIN)

    assert inside(graph, "main.use") == ["main.MetaA.__iter__", "main.MetaB.__iter__"]
