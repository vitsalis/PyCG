"""Builtin functions and operators of builtin types whose results the
analysis models beyond their stubs: enumerate, zip, reversed, map and
filter over the engine's containers."""

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

    # The stubs carry the elements: enumerate[T] gives tuple[int, T],
    # zip.__new__ gives zip[tuple[T1, T2]], reversed[T] gives T.
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

    # map(f, xs) calls f (a class is instantiated) and yields its results.
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

    # Python calls the function with each element and tests the truth of
    # what it returns; the iterator gives the elements, not the results.
    assert callees(graph, "main.use") == [
        "<builtin>.filter",
        "main.Item.keep",
        "main.Item.run",
        "main.Verdict.__bool__",
        "main.first",
    ]
    assert callees(graph, "main.first") == ["main.Item.keep"]


# One call that reaches zip with one iterable, and, through a `__new__` that
# passes the class first, with two (final review of the engine, finding 1).
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

    # zip([g]) gives (g,); C([f]) is zip(C, [f]), which iterates C through
    # its metaclass and gives (h, f).
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

    # Without unpacking, the tuple has a known length and positions; with
    # it, the elements of every iterable may be at any position.
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

    # An explicit iterable passes its elements at its position; the
    # iterables that an unpacked argument passes give theirs at any later
    # position. `second` returns its second argument: h and k, never g.
    assert callees(graph, "main.use") == [
        "<builtin>.map",
        "main.apply",
        "main.f",
        "main.h",
        "main.k",
        "main.second",
    ]
