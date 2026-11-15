"""The iteration protocol on instances, generator functions, next(), iter()
and yield from."""

import pytest
from programs import callees, main_graph

ITERATOR = """
def f(): pass
class Items:
    def __iter__(self):
        return self
    def __next__(self):
        return f
"""


def test_for_loop_over_an_instance_calls_iter_and_next(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATOR
        + """
def use(items):
    for item in items:
        item()
use(Items())
""",
    )

    assert callees(graph, "main.use") == [
        "main.Items.__iter__",
        "main.Items.__next__",
        "main.f",
    ]


def test_every_kind_of_iteration_over_an_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATOR
        + """
def comprehension(items):
    [x() for x in items]
def unpacking(items):
    first, *rest = items
    first()
def builtin(items):
    list(items)[0]()
comprehension(Items())
unpacking(Items())
builtin(Items())
""",
    )

    expected = ["main.Items.__iter__", "main.Items.__next__", "main.f"]
    assert callees(graph, "main.comprehension") == expected
    assert callees(graph, "main.unpacking") == expected
    assert callees(graph, "main.builtin") == ["<builtin>.list"] + expected


def test_iter_method_written_as_a_generator(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class Items:
            def __iter__(self):
                yield f
        for item in Items():
            item()
        """,
    )

    assert callees(graph, "main") == ["main.Items.__iter__", "main.f"]


def test_generator_function_edges_come_from_its_caller(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def produce():
            yield f
        def consume(values):
            for value in values:
                value()
        consume(produce())
        """,
    )

    assert callees(graph, "main") == ["main.consume", "main.produce"]
    assert callees(graph, "main.consume") == ["main.f"]


def test_next_send_and_the_value_of_yield(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def h(): pass
        def echo():
            received = yield f
            received()
            yield g
        def use():
            gen = echo()
            next(gen)()
            gen.send(h)()
            next(echo(), g)()
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.next",
        "main.echo",
        "main.f",
        "main.g",
        "types.GeneratorType.send",
    ]
    assert callees(graph, "main.echo") == ["main.h"]


def test_generator_methods_give_the_yielded_values(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def m(self): pass
        class D:
            def m(self): pass
        def first():
            yield C()
        def second():
            yield D()
        first().__next__().m()
        second().throw(ValueError).m()
        """,
    )

    assert callees(graph, "main") == [
        "main.C.m",
        "main.D.m",
        "main.first",
        "main.second",
        "types.GeneratorType.__next__",
        "types.GeneratorType.throw",
    ]


def test_yield_from_forwards_values_and_returns_the_result(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def inner():
            yield f
            return g
        def outer():
            result = yield from inner()
            result()
            yield from [g]
        for value in outer():
            value()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g", "main.outer"]
    assert callees(graph, "main.outer") == ["main.g", "main.inner"]


def test_iter_and_next_builtins(tmp_path):
    graph = main_graph(
        tmp_path,
        ITERATOR
        + """
def g(): pass
def use():
    next(iter(Items()))()
    next(iter([g]))()
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.iter",
        "<builtin>.next",
        "main.Items.__iter__",
        "main.Items.__next__",
        "main.f",
        "main.g",
    ]


def test_next_gives_its_default(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def m(self): pass
        next(iter(()), C()).m()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.iter", "<builtin>.next", "main.C.m"]


def test_async_iteration(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        class Stream:
            def __aiter__(self):
                return self
            async def __anext__(self):
                return f
        async def produce():
            yield g
        async def use():
            async for item in Stream():
                item()
            async for item in produce():
                item()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Stream.__aiter__",
        "main.Stream.__anext__",
        "main.f",
        "main.g",
        "main.produce",
    ]


def test_an_async_generator_has_the_methods_of_the_async_generator_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        async def produce():
            yield f
        async def use():
            g = produce()
            async for item in g.__aiter__():
                item()
            await g.__anext__()
            await g.asend(None)
            await g.athrow(ValueError)
            await g.aclose()
            g.__next__()
            g.send(None)
        """,
    )

    assert set(callees(graph, "main.use")) == {
        "main.produce",
        "main.f",
        "types.AsyncGeneratorType.__aiter__",
        "types.AsyncGeneratorType.__anext__",
        "types.AsyncGeneratorType.asend",
        "types.AsyncGeneratorType.athrow",
        "types.AsyncGeneratorType.aclose",
    }


def test_a_generator_function_keeps_the_generator_type(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def produce():
            yield f
        async def use():
            g = produce()
            for item in g.__iter__():
                item()
            g.close()
            g.aclose()
        """,
    )

    assert set(callees(graph, "main.use")) == {
        "main.produce",
        "main.f",
        "types.GeneratorType.__iter__",
        "types.GeneratorType.close",
    }


@pytest.mark.parametrize(
    ("expression", "kind"),
    [
        ("(x async for x in produce())", "types.AsyncGeneratorType"),
        ("(await wait(x) for x in [f])", "types.AsyncGeneratorType"),
        ("(x for x in [f] if await wait(x))", "types.AsyncGeneratorType"),
        ("(x for y in [1] for x in await wait([f]))", "types.AsyncGeneratorType"),
        ("([await wait(x) for x in [f]][0] for y in [1])", "types.AsyncGeneratorType"),
        ("([x async for x in produce()][0] for y in [1])", "types.AsyncGeneratorType"),
        # The first iterable runs in the enclosing scope.
        ("(x for x in await wait([f]))", "types.GeneratorType"),
        # A nested generator expression or lambda is a scope of its own.
        ("(f for y in [(await wait(x) for x in [1])])", "types.GeneratorType"),
        ("((lambda: f)() for y in [1])", "types.GeneratorType"),
        ("(x for x in [f])", "types.GeneratorType"),
    ],
)
def test_which_generator_expressions_are_async_generators(tmp_path, expression, kind):
    graph = main_graph(
        tmp_path,
        f"""
        def f(): pass
        async def wait(x):
            return x
        async def produce():
            yield f
        async def use():
            g = {expression}
            g.close()
            await g.aclose()
            g.__aiter__()
        """,
    )

    methods = {"types.GeneratorType": "close", "types.AsyncGeneratorType": "aclose"}
    called = {c for c in callees(graph, "main.use") if c.startswith("types.")}
    expected = {f"{kind}.{methods[kind]}"}
    if kind == "types.AsyncGeneratorType":
        expected.add(f"{kind}.__aiter__")
    assert called == expected


def test_an_async_generator_expression_gives_its_elements_to_async_for(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        async def wait(x):
            return x
        async def use():
            async for item in (await wait(x) for x in [f]).__aiter__():
                item()
        """,
    )

    assert set(callees(graph, "main.use")) == {
        "main.wait",
        "main.f",
        "types.AsyncGeneratorType.__aiter__",
    }


def test_elements_of_an_external_are_named_like_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        for item in ext.items:
            item.run()
        """,
    )

    assert callees(graph, "main") == ["ext.items.run"]


def test_recursive_generators_terminate(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def walk(node):
            yield node
            yield from walk(node)
            for child in walk(f):
                yield child
        for value in walk(f):
            value()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.walk"]
    assert callees(graph, "main.walk") == ["main.walk"]


def test_builtin_bases_that_are_not_classes_still_fall_back(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Odd(len):
            def __getitem__(self, index): pass
        def use(odd):
            for x in odd: pass
        use(Odd())
        """,
    )

    assert callees(graph, "main.use") == ["main.Odd.__getitem__"]


def test_iter_with_a_sentinel_calls_its_callable(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target():
            return f
        def f(): pass
        class Reader:
            def read(self): return ""
        def use():
            for value in iter(target, None):
                value()
            for chunk in iter(Reader().read, ""):
                pass
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.iter",
        "main.Reader.read",
        "main.f",
        "main.target",
    ]


def test_callable_iterator_calls_its_callable_where_it_is_consumed(tmp_path):
    # Making the iterator calls nothing; each next() calls the callable.
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        def callback():
            return target
        def create():
            return iter(callback, None)
        def consume(iterator):
            for value in iterator:
                value()
        def step(iterator):
            return next(iterator)
        consume(create())
        step(create())
        """,
    )

    assert callees(graph, "main.create") == ["<builtin>.iter"]
    assert callees(graph, "main.consume") == ["main.callback", "main.target"]
    assert callees(graph, "main.step") == ["<builtin>.next", "main.callback"]


def test_explicit_next_advances_every_iterator(tmp_path):
    # it.__next__() does what next(it) does, from the scope of the call.
    graph = main_graph(
        tmp_path,
        """
        def produce(): return 1
        class Seq:
            def __getitem__(self, index): pass
        def gen():
            yield 1
        def make():
            return iter(produce, 0), iter(Seq()), gen()
        def use(pair):
            first, second, third = pair
            first.__next__()
            second.__next__()
            third.__next__()
        use(make())
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.callable_iterator.__next__",
        "<builtin>.iterator.__next__",
        "main.Seq.__getitem__",
        "main.produce",
        "types.GeneratorType.__next__",
    ]


def test_sequence_protocol_and_membership_fallbacks(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        class Seq:
            def __getitem__(self, index):
                if index == 0:
                    return target
                raise IndexError
        class Both:
            def __iter__(self):
                return iter([])
            def __getitem__(self, index): pass
        class Searchable:
            def __iter__(self):
                return iter([target])
        class Contains:
            def __contains__(self, item): return True
            def __iter__(self): pass
        def use():
            for f in Seq():
                f()
            for x in Both():
                pass
            target in Searchable()
            target in Contains()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Both.__iter__",
        "main.Contains.__contains__",
        "main.Searchable.__iter__",
        "main.Seq.__getitem__",
        "main.target",
    ]


def test_iter_of_a_sequence_calls_getitem_where_it_is_consumed(tmp_path):
    # iter() makes an iterator whose next() calls __getitem__.
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        class Seq:
            def __getitem__(self, index):
                if index == 0:
                    return target
                raise IndexError
        def make():
            return iter(Seq())
        def use(iterator):
            for f in iterator:
                f()
        def first():
            return next(iter(Seq()))
        async def drain(seq):
            async for f in seq:
                pass
        use(make())
        first()()
        drain(Seq())
        """,
    )

    # async for has no sequence protocol.
    assert callees(graph, "main.drain") == []

    assert callees(graph, "main.make") == ["<builtin>.iter"]
    assert callees(graph, "main.use") == ["main.Seq.__getitem__", "main.target"]
    assert callees(graph, "main.first") == [
        "<builtin>.iter",
        "<builtin>.next",
        "main.Seq.__getitem__",
    ]
    assert "main.target" in callees(graph, "main")


def test_membership_compares_the_elements_with_eq(tmp_path):
    # Without __contains__, `x in y` compares x with each element that
    # iterating over y gives: both sides' __eq__ may run.
    graph = main_graph(
        tmp_path,
        """
        class Item:
            def __eq__(self, other):
                return True
        class Items:
            def __iter__(self):
                yield Item()
        class Searched:
            def __eq__(self, other):
                return False
        def use():
            1 in Items()
            1 not in [Item()]
            Searched() in (1, 2)
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Item.__eq__",
        "main.Items.__iter__",
        "main.Searched.__eq__",
    ]


def test_membership_through_contains_compares_nothing_else(tmp_path):
    # With __contains__ there is no fallback, so the searched value's
    # __eq__ does not run.
    graph = main_graph(
        tmp_path,
        """
        class Needle:
            def __eq__(self, other): return False
        class Bag:
            def __contains__(self, item): return False
        def bag():
            Needle() in Bag()
        def full():
            Needle() in [1]
        class Item:
            def __eq__(self, other): return True
        def untracked():
            None in [Item()]
        """,
    )

    assert callees(graph, "main.untracked") == ["main.Item.__eq__"]

    assert callees(graph, "main.bag") == ["main.Bag.__contains__"]
    assert callees(graph, "main.full") == ["main.Needle.__eq__"]


def test_membership_compares_untracked_elements_too(tmp_path):
    # None, bools and floats are not tracked, but a container that holds
    # them is not empty: the value's __eq__ runs.
    graph = main_graph(
        tmp_path,
        """
        class Item:
            def __eq__(self, other): return False
        class Needle:
            def __eq__(self, other): return False
        def displays():
            Item() in [None]
            Item() in (False, 1.5)
        def stored():
            xs = []
            xs.append(None)
            Item() in xs
        def copied():
            Item() in list([None])
        def converted():
            Item() in list({None})
        def yielding():
            yield None
        def generated():
            Item() in list(yielding())
        def keys():
            d = {}
            d[None] = 1
            Item() in d
        def unpacked(*rest):
            return Item() in rest
        unpacked(None)
        """,
    )

    names = ("displays", "stored", "copied", "converted", "generated", "keys")
    for name in (*names, "unpacked"):
        assert "main.Item.__eq__" in callees(graph, f"main.{name}"), name


@pytest.mark.parametrize(
    "body",
    [
        "xs = []\n    xs.extend([None])",
        "xs = []\n    xs.extend('ab')",
        "xs = {}\n    xs.update([(None, 1)])",
        "xs = {None}.copy()",
        "xs = {None: 1}.keys()",
        "xs = next(iter({None: None}.items()))",
        "xs = [None][:]",
        "xs = []\n    ys = xs[:]\n    xs.append(None)\n    xs = ys",
        "xs = []\n    xs[0:0] = [None]",
        "xs = [None] * 2",
        "xs = []\n    xs += [None]",
        "xs = [None] + []",
        "first, *xs = [1, None, None]",
        "xs = [y for y in [None]]",
        "xs = iter(Seq())",
        "xs = iter(nothing, 1)",
        "xs = Items()",
        "xs = generate()",
        "xs = unpacked(*[None])",
        "xs = keywords(a=None).values()",
        "xs = keywords(**{'a': None}).values()",
        "first, *xs = generate()",
    ],
)
def test_membership_in_containers_of_untracked_values(tmp_path, body):
    # Each container below holds None, which has no object: `in` must still
    # compare the value with it.
    graph = main_graph(
        tmp_path,
        f"""
class Item:
    def __eq__(self, other): return False
class Seq:
    def __getitem__(self, index): return None
class Items:
    def __iter__(self): return iter([None])
def generate():
    yield 1
    yield None
def unpacked(*rest):
    return rest
def nothing():
    return None
def keywords(**named):
    return named
def use():
    {body}
    Item() in xs
""",
    )

    assert "main.Item.__eq__" in callees(graph, "main.use")


COMPOSITIONS = """
class Needle:
    def __eq__(self, other): return True
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return 1
        raise IndexError
def make():
    return 1
class Blank:
    def __getitem__(self, index):
        return None
def blank():
    return None
"""


@pytest.mark.parametrize(
    "body",
    [
        # An iterator converted into a container: its elements fill it.
        "xs = list(iter(Seq()))",
        "xs = tuple(iter(make, 0))",
        "xs = set(iter(Seq()))",
        "xs = frozenset(iter(make, 0))",
        "xs = dict(enumerate(iter(Seq())))",
        # The elements are not tracked: what the iterator may give counts.
        "xs = list(iter(Blank()))",
        "xs = tuple(iter(blank, 0))",
        # ...and then copied, sliced, concatenated or extended.
        "xs = list(iter(Seq())).copy()",
        "xs = list(iter(Seq()))[:]",
        "xs = list(iter(Seq())) + []",
        "xs = []\n    xs.extend(iter(Seq()))",
        "xs = set()\n    xs.update(iter(make, 0))",
        "xs = []\n    xs += iter(Seq())",
        "xs = {}\n    xs.update(enumerate(iter(make, 0)))",
    ],
)
def test_containers_made_from_iterators_hold_their_elements(tmp_path, body):
    # A container holds an element as soon as any element reaches it, from
    # wherever it comes; `in` then compares the value.
    graph = main_graph(
        tmp_path, f"{COMPOSITIONS}def use():\n    {body}\n    Needle() in xs\n"
    )

    assert "main.Needle.__eq__" in callees(graph, "main.use")


@pytest.mark.parametrize(
    "body",
    [
        "xs = []",
        "xs = list()",
        "xs = {}",
        "xs = list([])",
        "xs = [][:]",
        "xs = [1][:0]",
        "first, *xs = [1]",
        "xs = list(iter([]))",
        "xs = []\n    xs.extend([])",
        "xs = []\n    xs.extend('')",
        "xs = set()\n    xs.update([])",
        "xs = {}\n    xs.update({})",
        "xs = []\n    xs += []",
        "xs = []\n    xs[0:0] = []",
    ],
)
def test_membership_limit_an_empty_container_still_compares(tmp_path, body):
    # A limit: the analysis cannot tell an empty container from one that
    # holds values it does not track (None, numbers, bytes), so `in` on a
    # builtin container always may call the searched value's __eq__.
    graph = main_graph(
        tmp_path, f"{COMPOSITIONS}def use():\n    {body}\n    Needle() in xs\n"
    )

    assert "main.Needle.__eq__" in callees(graph, "main.use")


@pytest.mark.parametrize(
    "body", ["xs = []\n    xs.extend(b'abc')", "xs = list(b'abc')"]
)
def test_membership_in_containers_of_untracked_bytes_compares(tmp_path, body):
    graph = main_graph(
        tmp_path,
        f"{COMPOSITIONS}def use():\n    {body}\n    Needle() in xs\n",
    )

    assert "main.Needle.__eq__" in callees(graph, "main.use")


@pytest.mark.parametrize("container", ['"abc"', 'b"abc"'])
def test_membership_in_a_str_or_bytes_constant_compares_nothing(tmp_path, container):
    # str.__contains__ and bytes.__contains__ test substrings and bytes; they
    # call no __eq__ of the value. The analysis does not search constants.
    use = f"def use():\n    Needle() in {container}\n"
    graph = main_graph(tmp_path, COMPOSITIONS + use)

    assert "main.Needle.__eq__" not in callees(graph, "main.use")


def test_limit_membership_in_a_value_without_objects_compares_nothing(tmp_path):
    # Nothing in the analysed code passes `values`, so the container never
    # holds an object and the value is not compared. Python compares it with
    # the elements of whatever a caller passes.
    use = "def use(values):\n    return Needle() in values\n"
    graph = main_graph(tmp_path, COMPOSITIONS + use)

    assert "main.Needle.__eq__" not in callees(graph, "main.use")


def test_membership_in_arguments_from_outside(tmp_path):
    # Nothing in the code calls f: code outside may pass anything.
    graph = main_graph(
        tmp_path,
        COMPOSITIONS
        + """
def f(*args, **named):
    Needle() in args
    Needle() in named.values()
""",
    )

    assert "main.Needle.__eq__" in callees(graph, "main.f")


NEEDLE_AND_ITEM = """
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True
"""


def test_membership_compares_a_container_from_a_late_getattr(tmp_path):
    # getattr's name is decided at a fixpoint: the list arrives after the
    # first one, and its element reaches Needle.__eq__.
    graph = main_graph(
        tmp_path,
        NEEDLE_AND_ITEM
        + """
class Holder:
    items = [Item()]
name = "items"
Needle() in getattr(Holder, name)
""",
    )

    assert callees(graph, "main.Needle.__eq__") == ["main.Item.touch"]


def test_membership_waits_for_a_contains_from_a_late_getattr(tmp_path):
    # Bag.__contains__ answers alone; the comparison must not be decided
    # before getattr supplies the Bag.
    graph = main_graph(
        tmp_path,
        NEEDLE_AND_ITEM
        + """
class Bag:
    def __contains__(self, item): return False
class Holder:
    items = Bag()
name = "items"
Needle() in getattr(Holder, name)
""",
    )

    assert "main.Bag.__contains__" in callees(graph, "main")
    assert "main.Needle.__eq__" not in callees(graph, "main")
    assert callees(graph, "main.Needle.__eq__") == []


# 16 hierarchies, more than the analysis enumerates: one exhaustive order.
EXHAUSTIVE_CONTAINER = """
import sys
class Needle:
    def __eq__(self, other): return True
class Bag:
    def __contains__(self, item): return False
class Plain:
    def __iter__(self):
        return iter([1])
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class C(
    Bag if sys.argv else Plain,
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
):
{body}
Needle() in C()
"""


@pytest.mark.parametrize(
    "body, compared",
    [
        # With Plain as a base, Python iterates and compares.
        ("    pass", True),
        # C's own __contains__ answers in every hierarchy.
        ("    def __contains__(self, item): return False", False),
    ],
)
def test_membership_in_an_instance_of_an_exhaustive_class(tmp_path, body, compared):
    graph = main_graph(tmp_path, EXHAUSTIVE_CONTAINER.format(body=body))

    assert ("main.Needle.__eq__" in callees(graph, "main")) is compared


def test_membership_decides_contains_again_when_bases_arrive_late(tmp_path):
    # `in` sees C with Bag's __contains__ when the completion calls use;
    # only a later completion round, which decides the name that setattr
    # gets, gives C the list subclass, which compares the elements.
    graph = main_graph(
        tmp_path,
        """
        class Needle:
            def __eq__(self, other): return True
        class Bag:
            def __contains__(self, item): return False
        class Items(list):
            def __init__(self):
                super().__init__([1])
        class Holder:
            pass
        class Names:
            second = "base"
        holder = Holder()
        holder.base = Bag
        first = "second"
        name = getattr(Names, first)
        setattr(holder, name, Items)
        class C(holder.base):
            pass
        def use():
            Needle() in C()
        class Box:
            run = use
        key = "run"
        getattr(Box, key)()
        """,
    )

    assert "main.Needle.__eq__" in callees(graph, "main.use")


def test_builtin_containers_rule_out_the_fallbacks(tmp_path):
    # list.__iter__ and list.__contains__ never call __getitem__ or __iter__
    # of a subclass; Exception has neither, and an external class may lack
    # both, so their subclasses still fall back. int.__format__ does call
    # __str__.
    graph = main_graph(
        tmp_path,
        """
        import lib
        class Items(list[int]):
            def __getitem__(self, index): pass
        class Members(list):
            def __iter__(self):
                return iter([])
        class Error(Exception):
            def __getitem__(self, index): pass
        class Unknown(lib.Base):
            def __getitem__(self, index): pass
        class Number(int):
            def __str__(self):
                return ""
        def use(items, members, error, unknown, number):
            for x in items: pass
            1 in members
            for x in error: pass
            for x in unknown: pass
            format(number)
        use(Items(), Members(), Error(), Unknown(), Number())
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.format",
        "main.Error.__getitem__",
        "main.Number.__str__",
        "main.Unknown.__getitem__",
    ]


def test_a_class_stored_as_its_own_iter_terminates(tmp_path):
    # Each iteration calls It to make an iterator, whose items flow back
    # into the list that is iterated: one instance per construct.
    graph = main_graph(
        tmp_path,
        """
        class It:
            def __init__(self):
                self.done = False
            def __next__(self):
                if self.done:
                    raise StopIteration
                self.done = True
                return self
        It.__iter__ = It
        xs = [It()]
        for item in xs:
            xs.extend(item)
            break
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.list.extend",
        "main.It.__init__",
        "main.It.__next__",
    ]


def test_one_construct_iterating_two_receivers_reaches_both(tmp_path):
    # One extend site with two lists: the __iter__ of It runs once for the
    # site, and its result reaches both lists.
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class It:
            def __iter__(self):
                return iter([f])
        a = []
        b = []
        for target in (a, b):
            target.extend(It())
        def use_a():
            a[0]()
        def use_b():
            b[0]()
        """,
    )

    assert callees(graph, "main.use_a") == ["main.f"]
    assert callees(graph, "main.use_b") == ["main.f"]
