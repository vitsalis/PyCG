"""The work of the solver grows about linearly with the size of a hub.

A hub is generic code that calls every callable with every argument, such
as `contextlib`'s `func(*args, **kwds)`: context-insensitively, each callable
gets each argument, so a solver that keeps a private copy of a set per node
and moves objects one by one does work quadratic in the size of the hub.
The measure is machine-independent: the objects written into sets, the
constraint applications and the subset edges that the solver counts.
"""

import pytest
from programs import analysed
from test_termination import long_hierarchies

from pycg.analysis import narrowing, solver
from pycg.analysis.model import Class


def hub(size):
    """`size` callables and `size` arguments that meet in one generic apply
    function. Each callable passes its argument on through the hub, which
    makes a cycle; arguments are instances that hold containers."""
    lines = [
        "def apply(func, *args, **kwargs):",
        "    return func(*args, **kwargs)",
    ]
    for i in range(size):
        lines += [
            f"class Value{i}:",
            "    def __init__(self, items):",
            "        self.items = items",
            f"def f{i}(value, key=None):",
            f"    apply(f{(i + 1) % size}, value, key='k{i}')",
            "    return value",
            f"apply(f{i}, Value{i}(({i}, 'v{i}')))",
        ]
    return "\n".join(lines) + "\n"


def unpacking_hub(size):
    """`size` callables and `size` tuples that meet where one generic
    function unpacks its tuple into its callable."""
    lines = ["def apply(func, args):", "    return func(*args)"]
    for i in range(size):
        lines += [
            f"def f{i}(first, second):",
            "    return first",
            f"apply(f{i}, (f{i}, 'v{i}'))",
        ]
    return "\n".join(lines) + "\n"


def hub_results(points_to, size):
    """Each callable of `hub` gets every argument and every key."""
    for i in (0, size - 1):
        values = points_to[f"main.f{i}.value"]
        # One instance of each Value class.
        assert sorted(value.split("@")[0] for value in values) == sorted(
            f"main.Value{j}" for j in range(size)
        )
        keys = points_to[f"main.f{i}.key"]
        assert keys == sorted(f"'k{j}'" for j in range(size))


def unpacking_hub_results(points_to, size):
    """Each callable of `unpacking_hub` gets every callable and string."""
    for i in (0, size - 1):
        assert points_to[f"main.f{i}.first"] == sorted(
            f"main.f{j}" for j in range(size)
        )
        assert points_to[f"main.f{i}.second"] == sorted(f"'v{j}'" for j in range(size))


RESULTS = {"hub": hub_results, "unpacking_hub": unpacking_hub_results}


def work(tmp_path, program, size):
    generator = analysed(tmp_path / str(size), {"main.py": program(size)})
    counts = generator.program.analysis.solver.work
    # The hub calls every callable, and each gets what it is passed.
    assert len(generator.output()["main.apply"]) == size
    RESULTS[program.__name__](generator.output_points_to(), size)
    return counts["copied"] + counts["applied"] + counts["edges"]


def assert_about_linear(tmp_path, program):
    small, medium, large = (work(tmp_path, program, size) for size in (40, 80, 160))

    # Linear growth doubles the work; quadratic growth would quadruple it.
    assert medium < 2.5 * small
    assert large < 2.5 * medium


def test_work_grows_about_linearly_with_the_size_of_a_hub(tmp_path):
    assert_about_linear(tmp_path, hub)


def test_unpacking_where_many_callables_meet_many_tuples_is_linear(tmp_path):
    assert_about_linear(tmp_path, unpacking_hub)


def meeting_paths(size):
    """Paths of every length from 1 to `size` from one function to one
    field, which leads on to a chain of `size` fields: a spine of fields,
    each of which also flows into the meeting field. No cycle."""
    lines = ["class Box:", "    pass", "def value():", "    pass", "box = Box()"]
    lines.append("box.s0 = value")
    for i in range(1, size):
        lines.append(f"box.s{i} = box.s{i - 1}")
    for i in range(size):
        lines.append(f"box.meet = box.s{i}")
    lines.append("box.c0 = box.meet")
    for i in range(1, size):
        lines.append(f"box.c{i} = box.c{i - 1}")
    lines.append(f"box.c{size - 1}()")
    return "\n".join(lines) + "\n"


ORDERS = {
    "first in, first out": solver.Order,
    "last in, first out": solver.LastInFirstOut,
    "reversed": solver.Reversed,
    "random 1": lambda: solver.Shuffled(1),
    "random 2": lambda: solver.Shuffled(2),
}


@pytest.mark.parametrize("order", ORDERS)
def test_searches_for_cycles_are_about_linear(tmp_path, monkeypatch, order):
    # Each path that reaches the meeting field after the first brings it
    # the set it already holds, so its edge may close a cycle. Searching the
    # chain after it once per such edge, as each arrived, was quadratic.
    monkeypatch.setattr(solver.Solver, "order", ORDERS[order]())

    def searched(size):
        generator = analysed(tmp_path / str(size), {"main.py": meeting_paths(size)})
        assert generator.output()["main"] == ["main.value"]
        return generator.program.analysis.solver.work["searched"]

    small, medium, large = (searched(size) for size in (100, 200, 400))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def metaclass_statements(size):
    """`size` class statements of one metaclass whose `__new__` calls
    `type.__new__`, which gives every class of the metaclass."""
    lines = [
        "class Meta(type):",
        "    def __new__(mcs, name, bases, namespace):",
        "        return super().__new__(mcs, name, bases, namespace)",
        "    def __init__(cls, name, bases, namespace):",
        "        cls.ready()",
    ]
    for i in range(size):
        lines += [
            f"class C{i}(metaclass=Meta):",
            "    @classmethod",
            "    def ready(cls): pass",
        ]
    return "\n".join(lines) + "\n"


def test_class_statements_of_one_metaclass_are_about_linear(tmp_path):
    def statements_work(size):
        program = metaclass_statements(size)
        generator = analysed(tmp_path / str(size), {"main.py": program})
        assert len(generator.output()["main.Meta.__init__"]) == size
        counts = generator.program.analysis.solver.work
        return counts["copied"] + counts["applied"] + counts["edges"]

    small, medium, large = (statements_work(size) for size in (40, 80, 160))

    # Each statement initialises its own class, not every class.
    assert medium < 2.5 * small
    assert large < 2.5 * medium


def class_comparisons(tmp_path, monkeypatch, size):
    """How often the analysis of `long_hierarchies(size)` and the report of
    its classes compare two classes: a search of a list of classes compares
    the class sought with each class before it, a set or dict does not."""
    count = 0

    def counting_eq(self, other):
        nonlocal count
        count += 1
        return self is other

    with monkeypatch.context() as patch:
        patch.setattr(Class, "__eq__", counting_eq)
        program = long_hierarchies(size)
        generator = analysed(tmp_path / str(size), {"main.py": program})
        generator.document()
    return count


def test_work_on_a_long_chain_of_classes_is_about_quadratic(tmp_path, monkeypatch):
    # Each of n classes looks a name up through its MRO of up to n classes,
    # n² steps in all. A step that searches the MRO (does the receiver
    # derive from this class?) made it cubic; so did the C3 merge and the
    # reported MRO, which searched the classes they had already placed.
    small, large = (
        class_comparisons(tmp_path, monkeypatch, size) for size in (100, 200)
    )

    # Quadratic growth quadruples the count; cubic growth would multiply it
    # by eight.
    assert large < 5 * small


# Builtin classes whose instance checks follow their MROs, as the tested
# classes of `class_tests`.
TESTED_OUTSIDE = (
    "str bytes int float list dict tuple set frozenset bytearray complex range "
    "ValueError KeyError TypeError OSError"
).split()


def class_tests(values, sites, tested, kinds=4):
    """`values` instances of `kinds` classes, each tested at `sites` sites:
    where it holds against a tuple of `tested` builtin classes, and where
    it fails against a tuple of `tested` analysed classes."""
    lines = []
    for i in range(kinds):
        lines += [f"class C{i}:", "    def m(self): pass"]
    for j in range(tested):
        lines += [f"class T{j}:", "    def m(self): pass"]
    lines += [f"v{i} = C{i % kinds}()" for i in range(values)]
    lines.append("items = [" + ", ".join(f"v{i}" for i in range(values)) + "]")
    outside = ", ".join(TESTED_OUTSIDE[:tested])
    analysed_classes = ", ".join(f"T{j}" for j in range(tested))
    for s in range(sites):
        lines += [
            f"def site{s}(x):",
            f"    if isinstance(x, ({outside},)):",
            "        x.n()",
            f"    if not isinstance(x, ({analysed_classes},)):",
            "        x.m()",
            "for item in items:",
            f"    site{s}(item)",
        ]
    return "\n".join(lines) + "\n"


def class_test_work(tmp_path, values, sites, tested):
    root = tmp_path / f"{values}-{sites}-{tested}"
    generator = analysed(root, {"main.py": class_tests(values, sites, tested)})
    graph = generator.output()
    for s in (0, sites - 1):
        # No instance passes the builtin classes; every one passes where
        # the analysed classes fail.
        assert graph[f"main.site{s}"] == ["<builtin>.isinstance"] + [
            f"main.C{i}.m" for i in range(4)
        ]
    counts = generator.program.analysis.solver.work
    return counts["copied"] + counts["applied"] + counts["edges"]


def test_class_tests_decide_per_class_of_the_values(tmp_path):
    # A filter decides each pair of a class of the values and a tested class
    # once, so a test of t classes on v values of c classes costs about
    # v + c*t: doubling the values, the sites and the tested classes about
    # quadruples the work (sites * values). A decision per value, site and
    # tested class grows like v*k*t, eight times.
    small = class_test_work(tmp_path, 48, 6, 8)
    large = class_test_work(tmp_path, 96, 12, 16)
    assert large < 4.5 * small


class CountingSet(set):
    """A set that counts the elements that its unions and updates touch,
    and its additions (see `test_a_tuple_of_classes_costs_its_length`)."""

    touched = 0

    def __or__(self, other):
        CountingSet.touched += len(self) + len(other)
        return CountingSet(set.__or__(self, other))

    def update(self, *others):
        for other in others:
            CountingSet.touched += len(other)
        set.update(self, *others)

    def add(self, element):
        CountingSet.touched += 1
        set.add(self, element)


def tuple_bookkeeping(tmp_path, monkeypatch, tested):
    lines = ["class V:", "    def m(self): pass"]
    lines += [f"class T{j}: pass" for j in range(tested)]
    classes = ", ".join(f"T{j}" for j in range(tested))
    lines += [
        "def f(x):",
        f"    if not isinstance(x, ({classes},)):",
        "        x.m()",
        "f(V())",
    ]
    monkeypatch.setattr(narrowing, "set", CountingSet, raising=False)
    CountingSet.touched = 0
    generator = analysed(tmp_path / str(tested), {"main.py": "\n".join(lines) + "\n"})
    assert "main.V.m" in generator.output()["main.f"]
    return CountingSet.touched


def test_a_tuple_of_classes_costs_its_length(tmp_path, monkeypatch):
    # One value against a tuple of t classes, where the test fails: the
    # value passes each position once, so the bookkeeping grows like t.
    # Rebuilding the union of the passed positions at each one grew like
    # t squared.
    small = tuple_bookkeeping(tmp_path, monkeypatch, 32)
    large = tuple_bookkeeping(tmp_path, monkeypatch, 64)
    assert large < 2.5 * small


def classes_at_one_position(tmp_path, monkeypatch, tested):
    """Comparisons between classes while `tested` classes reach the one
    position of a test: a function reads `kind`, which every one of them
    is bound to."""
    lines = ["class V:", "    def m(self): pass"]
    lines += [f"class T{j}: pass" for j in range(tested)]
    lines += [f"kind = T{j}" for j in range(tested)]
    lines += [
        "def f(x):",
        "    if not isinstance(x, (kind,)):",
        "        x.m()",
        "f(V())",
    ]
    compared = []

    def counting_eq(self, other):
        compared.append(None)
        return self is other

    monkeypatch.setattr(Class, "__eq__", counting_eq)
    files = {"main.py": "\n".join(lines) + "\n"}
    generator = analysed(tmp_path / f"one-{tested}", files)
    assert "main.V.m" in generator.output()["main.f"]
    return len(compared)


def test_classes_at_one_position_cost_their_number(tmp_path, monkeypatch):
    # A position keeps its classes as an ordered set, so a class that
    # arrives is looked up once; a list searched at each arrival grew like
    # t squared.
    small = classes_at_one_position(tmp_path, monkeypatch, 64)
    large = classes_at_one_position(tmp_path, monkeypatch, 128)
    assert large < 2.5 * small + 64


def converted_containers(size, elements=40):
    """`size` sites that convert, each, any of `size` lists of the same
    `elements` instances."""
    lines = ["class E:", "    def __repr__(self): return 'e'"]
    lines += [f"e{j} = E()" for j in range(elements)]
    items = ", ".join(f"e{j}" for j in range(elements))
    lines += [f"xs{i} = [{items}]" for i in range(size)]
    lines.append("for v in (" + ", ".join(f"xs{i}" for i in range(size)) + ",):")
    lines += ["    repr(v)"] * size
    return "\n".join(lines) + "\n"


def converted_work(tmp_path, size):
    """Constraint applications for `converted_containers(size)`."""
    program = converted_containers(size)
    generator = analysed(tmp_path / str(size), {"main.py": program})
    assert generator.output()["main"] == ["<builtin>.repr", "main.E.__repr__"]
    return generator.program.analysis.solver.work["applied"]


def test_converting_containers_at_many_sites_shares_the_walk_of_their_elements(
    tmp_path,
):
    # repr() of a list calls repr() of its elements. A walk of the elements
    # per (container, site) pair grows with sites times containers times
    # elements. With one walk per container and one per site, sites times
    # containers remains only in each site's own conversion of its value.
    small, medium, large = (converted_work(tmp_path, size) for size in (10, 20, 40))

    # Sites times containers times elements would quadruple the work at
    # each doubling; the shared walk keeps it under three times.
    assert medium < 3 * small
    assert large < 3 * medium


def compared_containers(size):
    """`size` lists and `size` tuples, each of an instance and a container
    of the other family, that all reach both operands of one comparison
    and the items of one `sorted`."""
    lines = [
        "class E:",
        "    def __eq__(self, other): return False",
        "    def __lt__(self, other): return False",
        "e = E()",
    ]
    lines += [f"xs{i} = [e, (e, {i})]" for i in range(size)]
    lines += [f"ys{i} = (e, [{i}, e])" for i in range(size)]
    names = ", ".join(f"xs{i}, ys{i}" for i in range(size))
    lines += [
        f"values = [{names}]",
        "def compare(a, b):",
        "    return a < b",
        "for a in values:",
        "    for b in values:",
        "        compare(a, b)",
        "sorted(values)",
    ]
    return "\n".join(lines) + "\n"


def compared_work(tmp_path, size):
    """Solver work for `compared_containers(size)`."""
    generator = analysed(tmp_path / str(size), {"main.py": compared_containers(size)})
    assert generator.output()["main.compare"] == ["main.E.__eq__", "main.E.__lt__"]
    counts = generator.program.analysis.solver.work
    return counts["copied"] + counts["applied"] + counts["edges"]


def test_containers_that_meet_at_one_comparison_cost_their_number(tmp_path):
    # Many containers of one family on both sides of one comparison: their
    # elements meet in a node per family, not per pair of containers, whose
    # number grows with the square of the containers.
    small, medium, large = (compared_work(tmp_path, size) for size in (40, 80, 160))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def reflected_members(size):
    """A class with `size` methods, half of them inherited, whose members
    `inspect.getmembers` (on the class and on an instance) and `vars` read
    in a loop."""
    inherited = size // 2
    lines = ["import inspect", "class Base:"]
    lines += [f"    def b{i}(self): pass" for i in range(inherited)]
    lines.append("class Big(Base):")
    lines += [f"    def m{i}(self): pass" for i in range(size - inherited)]
    lines += [
        "def run(rounds):",
        "    for _ in rounds:",
        "        for name, member in inspect.getmembers(Big):",
        "            member(Big())",
        "        for name, member in inspect.getmembers(Big()):",
        "            member()",
        "        for name, member in vars(Big).items():",
        "            member(Big())",
        "run(range(3))",
    ]
    return "\n".join(lines) + "\n"


def members_work(tmp_path, size):
    """Solver work for `reflected_members(size)`."""
    generator = analysed(tmp_path / str(size), {"main.py": reflected_members(size)})
    inherited = size // 2
    methods = [f"main.Base.b{i}" for i in range(inherited)]
    methods += [f"main.Big.m{i}" for i in range(size - inherited)]
    assert set(methods) <= set(generator.output()["main.run"])
    counts = generator.program.analysis.solver.work
    return counts["copied"] + counts["applied"] + counts["edges"]


def test_members_that_reflection_reads_cost_their_number(tmp_path):
    # Each member is loaded once per object that `getmembers` reaches and is
    # one field of one namespace dict, whatever the loops.
    small, medium, large = (members_work(tmp_path, size) for size in (40, 80, 160))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def reflection_sites(size):
    """`size` classes of two methods, each read by `getmembers` at a site
    of its own, and all their instances read at one more site."""
    lines = ["import inspect"]
    for i in range(size):
        lines += [
            f"class K{i}:",
            "    def a(self): pass",
            "    def b(self): pass",
            f"def site{i}():",
            f"    for name, member in inspect.getmembers(K{i}()):",
            "        member()",
            f"site{i}()",
        ]
    instances = ", ".join(f"K{i}()" for i in range(size))
    lines += [
        f"for item in [{instances}]:",
        "    for name, member in inspect.getmembers(item):",
        "        member()",
    ]
    return "\n".join(lines) + "\n"


def sites_work(tmp_path, size):
    """Solver work for `reflection_sites(size)`."""
    generator = analysed(tmp_path / str(size), {"main.py": reflection_sites(size)})
    graph = generator.output()
    assert {"main.K0.a", "main.K0.b"} <= set(graph["main.site0"])
    assert f"main.K{size - 1}.b" in graph["main"]
    counts = generator.program.analysis.solver.work
    return counts["copied"] + counts["applied"] + counts["edges"]


def test_receivers_and_sites_that_reflection_reads_cost_their_number(tmp_path):
    # Each receiver is read once per site that reaches it: many classes at
    # sites of their own and at one shared site cost their sum.
    small, medium, large = (sites_work(tmp_path, size) for size in (40, 80, 160))

    assert medium < 2.5 * small
    assert large < 2.5 * medium


def test_a_dict_copied_into_another_at_many_sites_is_copied_once(tmp_path):
    # `target.update(source)` copies the fields of `source` to `target` key
    # by key, also the keys that `source` gets later. Every site copies the
    # same fields to the same place: one copy per pair of dicts does it,
    # and a copy per site would cost sites times keys.
    sites = 20
    program = (
        "def f(): pass\n"
        "source = {'a': f}\n"
        "target = {}\n" + "target.update(source)\n" * sites + "source['b'] = f\n"
    )
    generator = analysed(tmp_path, {"main.py": program})
    analysis = generator.program.analysis
    points_to = generator.output_points_to()
    (target,) = points_to["main.target"]
    assert points_to[f"{target}['a']"] == ["main.f"]
    assert points_to[f"{target}['b']"] == ["main.f"]
    (node,) = [n for n in analysis.named_nodes if n.label == "main.source"]
    (source,) = analysis.solver.objects(node)
    assert len(source.observers) == 1
