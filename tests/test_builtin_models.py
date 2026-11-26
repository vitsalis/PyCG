import pytest
from programs import callees, main_graph


def test_enumerate_zip_and_reversed_give_the_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def use():
    for _, a in enumerate([f]):
        a()
    for _, b in zip(["s"], [g]):
        b()
    for c in reversed([h]):
        c()
    next(iter(enumerate([k])))[1]()
use()
""",
    )

    assert {"main.f", "main.g", "main.h", "main.k"} <= set(callees(graph, "main.use"))


def test_map_gives_what_its_function_returns(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Point:
    def __init__(self, x): pass
    def run(self): pass
def inner(): pass
def make(x):
    return inner
def use():
    for r in map(make, [1]):
        r()
    for p in map(Point, [1, 2]):
        p.run()
use()
""",
    )

    assert {
        "main.inner",
        "main.make",
        "main.Point.__init__",
        "main.Point.run",
    } <= set(callees(graph, "main.use"))


def test_filter_calls_its_function_with_the_elements_and_gives_them(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Verdict:
    def __bool__(self): return True
class Item:
    def keep(self): return Verdict()
    def run(self): pass
class Other:
    def run(self): pass
def first(pair):
    return pair[0].keep()
def unused(): pass
def use():
    for item in filter(first, [(Item(), unused)]):
        item[0].run()
    for kept in filter(Item.keep, [Item()]):
        kept.run()
use()
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.filter",
        "main.Item.keep",
        "main.Item.run",
        "main.Verdict.__bool__",
        "main.first",
    ]
    assert callees(graph, "main.first") == ["main.Item.keep"]


ZIP_OF_TWO_ARITIES = """
class M(type):
    def __iter__(cls): return iter([h])
class Factory:
    __call__ = staticmethod(zip)
class C(metaclass=M):
    __new__ = Factory()
def f(): pass
def g(): pass
def h(): pass
def make(factory, item):
    return factory([item])
for (one,) in make(zip, g):
    one()
for first, second in make(C, f):
    first()
    second()
"""


def test_zip_at_one_call_with_two_arities_gives_a_tuple_of_each_length(tmp_path):
    graph = main_graph(tmp_path, ZIP_OF_TWO_ARITIES)

    assert callees(graph, "main.make") == ["<builtin>.zip", "main.M.__iter__"]
    assert callees(graph, "main") == [
        "<builtin>.staticmethod",
        "main.f",
        "main.g",
        "main.h",
        "main.make",
    ]


def test_zip_with_one_arity_keeps_the_positions_of_its_tuples(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def pair(*iterables):
    return zip(*iterables)
for first, second in zip([f], [g]):
    second()
for first, second in pair([h], [k]):
    first()
""",
    )

    found = callees(graph, "main")
    assert {"main.g", "main.h"} <= set(found)
    assert "main.f" not in found


def test_map_keeps_the_explicit_iterables_before_an_unpacked_one(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(): pass
def g(): pass
def h(): pass
def k(): pass
def apply(x): return x
def second(a, b): return b
def use():
    for x in map(apply, [f], *()):
        x()
    for y in map(second, [g], [h], *()):
        y()
    for z in map(second, [1], *[[k]]):
        z()
use()
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.map",
        "main.apply",
        "main.f",
        "main.h",
        "main.k",
        "main.second",
    ]


@pytest.mark.parametrize(
    "hook", ["typing.cast", "super", "type", "items.pop", "items.copy", "table.get"]
)
def test_a_modelled_builtin_called_as_an_inherited_hook_returns_nothing(tmp_path, hook):
    graph = main_graph(
        tmp_path,
        f"""
import typing
items = [1]
table = {{"a": 1}}
class Base:
    __init_subclass__ = {hook}
class Derived(Base):
    pass
""",
    )

    assert callees(graph, "main") == []


def test_an_implicit_method_wraps_each_function_bound_to_its_name(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import sys
def first(cls): pass
def second(cls): pass
class Base:
    __init_subclass__ = first if sys.argv else second
class Derived(Base):
    pass
""",
    )

    assert callees(graph, "main") == ["main.first", "main.second"]


def test_property_accessors_given_no_property_or_no_instance_run_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(self): pass
def g(self): pass
def run():
    property.getter(classmethod(f), g)
    p = property(f)
    p.__get__(None)
    p.__get__(None, None)
    property.__get__(p)
""",
    )

    assert callees(graph, "main.run") == [
        "<builtin>.classmethod",
        "<builtin>.property",
        "<builtin>.property.__get__",
        "<builtin>.property.getter",
    ]


def test_a_property_subclass_passes_its_getter_by_keyword(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(self): pass
class P(property):
    def __init__(self, getter):
        super().__init__(fget=getter)
class C:
    x = P(f)
def use(c: C):
    c.x
""",
    )

    assert callees(graph, "main.use") == ["main.f"]


def test_a_defaultdict_without_a_factory_keeps_its_items(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import collections
def f(): pass
def run():
    d = collections.defaultdict()
    d["a"] = f
    d["a"]()
""",
    )

    assert callees(graph, "main.run") == ["collections.defaultdict", "main.f"]


def test_super_of_a_class_outside_the_mro_or_of_no_class_finds_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class A:
    def m(self):
        return super(Exception, self).m()
    def n(self):
        super().n()
    def p(self):
        super(A.m, self).p()
A().m()
A.n(1)
A().p()
""",
    )

    assert callees(graph, "main.A.m") == ["<builtin>.super"]
    assert callees(graph, "main.A.n") == ["<builtin>.super"]
    assert callees(graph, "main.A.p") == ["<builtin>.super"]


def test_super_reached_through_two_callers_at_one_site_binds_once(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class P:
    def m(self): pass
class Q(P):
    pass
class A:
    __call__ = super
class B:
    __call__ = super
def run(q):
    for o in (A(), B()):
        o(Q, q).m()
run(Q())
""",
    )

    assert callees(graph, "main.run") == ["<builtin>.super", "main.P.m"]


def test_zip_and_map_skip_an_argument_without_a_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(*args): pass
class Caller:
    __call__ = map
class Y:
    pass
Y.__new__ = Caller()
def run(xs):
    zip(None, xs)
    map(f, None, xs)
    Y(f, None)
""",
    )

    assert callees(graph, "main.run") == ["<builtin>.map", "<builtin>.zip", "main.f"]


def test_reversed_of_a_class_or_of_a_sequence_with_two_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import sys
class A:
    pass
class B:
    if sys.argv:
        def __len__(self): return 1
        def __getitem__(self, i): pass
    else:
        def __len__(self): return 2
        def __getitem__(self, i): pass
def run():
    reversed(A)
    reversed(B())
""",
    )

    assert callees(graph, "main.run") == [
        "<builtin>.reversed",
        "main.B.__getitem__",
        "main.B.__len__",
    ]
