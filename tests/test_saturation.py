"""Saturation: a node that would hold more objects than the cap (`cap`)
holds the saturated value instead, and so does every node it reaches.

The saturated value stands for objects that the analysis no longer tracks.
A call of it has no callee: the call expression is unresolved, with the
cause `saturated`. Loading an attribute of it, subscripting it, iterating
over it, awaiting it, entering it and calling it give it again; a store
into it is dropped. It causes no edge, no object and no constraint, so
the call graph with a cap is part of the call graph without one; and the
document never names it. The tests set a small cap.
"""

import ast
import json
from pathlib import Path

import pytest
from programs import analysed, no_rule_sees_what_is_opaque

from pycg.analysis import solver
from pycg.analysis.semantics import Analysis
from pycg.formats import dumps
from pycg.pycg import CallGraphGenerator

pytestmark = pytest.mark.slow

ORDERS = {
    "first in, first out": solver.Order,
    "last in, first out": solver.LastInFirstOut,
    "reversed": solver.Reversed,
    "random 1": lambda: solver.Shuffled(1),
    "random 2": lambda: solver.Shuffled(2),
}


def registry(count):
    """A program that calls each of `count` handlers through one parameter."""
    handlers = ", ".join(f"h{i}" for i in range(count))
    return (
        "".join(f"def h{i}(): pass\n" for i in range(count))
        + f"HANDLERS = [{handlers}]\n"
        + "def run(handler):\n"
        + "    handler()\n"
        + "for handler in HANDLERS:\n"
        + "    run(handler)\n"
    )


def line_of(source, text):
    """The line of the first occurrence of `text` in `source`."""
    return source[: source.index(text)].count("\n") + 1


def sites(tmp_path, source, caller, **options):
    """The call sites of `caller`: (line, callees, cause if unresolved)."""
    generator = analysed(tmp_path, {"main.py": source}, **options)
    return [
        (site["line"], site["callees"], site.get("unresolved"))
        for site in generator.document()["calls"].get(caller, [])
    ]


def test_a_registry_at_the_cap_is_called(tmp_path):
    source = registry(4)
    line = line_of(source, "handler()")

    assert sites(tmp_path, source, "main.run", cap=4) == [
        (line, ["main.h0", "main.h1", "main.h2", "main.h3"], None)
    ]


def test_a_registry_past_the_cap_is_unresolved(tmp_path):
    source = registry(5)
    line = line_of(source, "handler()")

    assert sites(tmp_path, source, "main.run", cap=4) == [(line, [], "saturated")]


def test_the_cap_is_5000_by_default_and_none_removes_it(tmp_path):
    source = registry(5001)
    line = line_of(source, "handler()")

    assert sites(tmp_path / "default", source, "main.run") == [(line, [], "saturated")]
    ((_, callees, cause),) = sites(tmp_path / "none", source, "main.run", cap=None)
    assert (len(callees), cause) == (5001, None)


@pytest.mark.parametrize("cap", [0, -1, True, False, 2.5, "5"])
def test_a_cap_is_a_positive_integer_or_none(cap):
    with pytest.raises(ValueError, match="a positive integer or None"):
        CallGraphGenerator(["main.py"], cap=cap)


def test_the_calls_around_a_saturated_value_stay(tmp_path):
    source = registry(5)
    line = line_of(source, "    run(handler)")

    assert (line, ["main.run"], None) in sites(tmp_path, source, "main", cap=4)


SATURATED_VALUE = (
    registry(5)
    + """
def use(handler, item):
    handler.attribute()
    handler[0]()
    for each in handler:
        each()
    handler.stored = item
    handler.stored()
    item()
def item(): pass
for handler in HANDLERS:
    use(handler, item)
"""
)


def test_what_a_saturated_value_gives_is_saturated(tmp_path):
    # A load, a subscript and an iteration give the saturated value, and a
    # store into it is dropped: a call of each is unresolved. The argument
    # that is not saturated is still called.
    source = SATURATED_VALUE
    found = sites(tmp_path, source, "main.use", cap=4)
    calls = ("handler.attribute()", "handler[0]()", "each()", "handler.stored()")

    assert found == [(line_of(source, call), [], "saturated") for call in calls] + [
        (line_of(source, "    item()"), ["main.item"], None)
    ]


# Saturation never adds an edge: for programs where a value of three
# objects meets each protocol, and for every case of the micro-benchmark,
# the call graph with a small cap is part of the call graph without one.

THREE = """
class A:
    def __eq__(self, other): return True
    def __lt__(self, other): return True
    def __contains__(self, value): return True
    def __iter__(self): return iter([])
    def __getitem__(self, key): return key
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __bool__(self): return True
    def __len__(self): return 0
    def __format__(self, spec): return ""
    def __str__(self): return ""
    def __repr__(self): return ""
    def __hash__(self): return 0
    def __add__(self, other): return self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __call__(self): pass
    def __await__(self): yield
    def __get__(self, obj, owner): return self
    def __set__(self, obj, value): pass
    def method(self): pass
class B(A): pass
class C(A): pass
def instances():
    for value in (A(), B(), C()):
        use(value)
def classes():
    for value in (A, B, C):
        use(value)
"""

PROTOCOLS = {
    # Final review, round 3, finding 2: Python calls only `__contains__`.
    "membership": """
class Needle:
    def __eq__(self, other): return False
class Bag:
    def __contains__(self, value): return False
def check(bag):
    return Needle() in bag
check(Bag()); check(Bag()); check(Bag())
""",
    "membership of a needle": """
class Box:
    def __contains__(self, value): return False
def use(value):
    return value in Box(), value in [1], value in (value,)
instances()
""",
    "iteration": """
def use(value):
    for x in value: x.method()
    [y for y in value]
    a, b = value
    list(value); tuple(value); set(value); dict(value); sorted(value)
    next(iter(value))
instances()
""",
    "comparison and sorting": """
def use(value):
    value == 1; value < 1; 1 < value; value != value
    sorted([value, value]); max(value, value); min([value])
    sorted([1], key=value)
instances()
""",
    "truth": """
def use(value):
    if value: pass
    not value; value and 1; value or 1; bool(value); len(value)
    assert value
instances()
""",
    "formatting": """
def use(value):
    f"{value}"; str(value); repr(value); "%s" % value; "{}".format(value)
instances()
""",
    "await": """
async def use(value):
    await value
    async with value: pass
    async for x in value: pass
instances()
""",
    "subscripts": """
def use(value):
    value[0]; value["k"] = 1; del value[0]; value[1:2]; value[0]()
    {value: 1}; {1: 2}[value]; hash(value)
instances()
""",
    "descriptors": """
class Holder: pass
def use(value):
    Holder.attribute = value
    Holder().attribute
    Holder().attribute = 1
instances()
""",
    "operators and calls": """
def use(value):
    value + 1; 1 + value; -value; value()
    value.method(); getattr(value, "method")(); setattr(value, "x", 1)
    with value as entered: entered.method()
    A.method(value + value)
instances()
""",
    "a saturated base": """
class Lazy:
    def __getattr__(self, name): return name
def use(value):
    class Derived(value, Lazy): pass
    Derived().method(); Derived.method; str(Derived())
    class Other(value): pass
    Other().missing; super(Other, Other()).method()
classes()
""",
    "a saturated metaclass": """
class Meta(type):
    def __call__(cls): pass
    def __getitem__(cls, key): pass
    def describe(cls): pass
class M2(Meta): pass
class M3(Meta): pass
def use(meta):
    class Made(metaclass=meta):
        def __init__(self): pass
    Made(); Made[0]; Made.describe()
for meta in (Meta, M2, M3):
    use(meta)
""",
    "classes as values": """
def use(value):
    value(); value.method(value()); isinstance(1, value); value[int]
    type(value()).method
    try:
        pass
    except value as error:
        error.method()
classes()
""",
    "code that only a saturated call reaches": """
def f(): pass
def g(): pass
def h0(cb=f): cb()
def h1(cb=f): cb()
def h2(cb=f): cb()
class Base:
    def run(self): self.step()
    def step(self): pass
class Sub(Base):
    def step(self): pass
def call(fn): fn(g)
for h in (h0, h1, h2, Base().run):
    call(h)
""",
}


# Final review, round 4, findings 3 to 5: the saturated value reached rule
# code, which took a branch for what it is not. No rule sees it now.
MARKER = {
    "a saturated dict key": """
def good(): pass
def bad(): pass
table = {"a": good, "b": good, "c": good, "extra": bad}
for key in ("a", "b", "c"):
    table[key]()
""",
    "a saturated pattern key": """
def good(): pass
def bad(): pass
table = {"a.x": good, "b.x": good, "c.x": good, "extra": bad}
def use(name):
    for key in ("a.%s" % name, "b.%s" % name, "c.%s" % name):
        table[key]()
use("x")
""",
    "in with a saturated metaclass": """
class Needle:
    def __eq__(self, other): return False
class M1(type):
    def __contains__(cls, other): return False
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta): pass
    return Needle() in Bag
for meta in (M1, M2, M3):
    use(meta)
""",
    "a subscript with a saturated metaclass": """
class M1(type):
    def __getitem__(cls, key): pass
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta):
        def __class_getitem__(cls, key): pass
    Bag[0]
for meta in (M1, M2, M3):
    use(meta)
""",
    "await with a saturated metaclass": """
class M1(type):
    def __await__(cls): yield
class M2(M1): pass
class M3(M1): pass
def use(meta):
    class Bag(metaclass=meta):
        def done(self): pass
    async def run():
        result = await Bag
        result.done(result)
    run()
for meta in (M1, M2, M3):
    use(meta)
""",
    "a saturated __getattribute__": """
def g1(self, name): return 1
def g2(self, name): return 1
def g3(self, name): return 1
class Holder:
    __getattribute__ = g1
    @property
    def value(self): return 1
def use(hook):
    Holder.__getattribute__ = hook
    Holder().value
for hook in (g2, g3):
    use(hook)
""",
    "saturated ancestry": """
import sys
class A(type): pass
class B(type): pass
class C(type): pass
base = A if sys.argv else B if sys.path else C
class Meta(base):
    def __call__(self): pass
def use(value: Meta):
    value()
""",
}


def graph_edges(generator):
    graph = generator.output()
    return {(caller, callee) for caller, callees in graph.items() for callee in callees}


def edges(root, source, **options):
    return graph_edges(analysed(root, {"main.py": source}, **options))


@pytest.fixture
def no_completion(monkeypatch):
    """The analysis without its steps at a fixpoint (see *The fixpoint
    steps* in the design): no entry points, no reads for keys that hold
    nothing, no bases decided absent. Without them every rule only adds,
    and the saturated value reaches none, so a cap can only take edges
    away."""
    monkeypatch.setattr(Analysis, "_complete", lambda self: False)
    monkeypatch.setattr(Analysis, "decide_hierarchies", lambda self: False)


@pytest.mark.parametrize("program", [*PROTOCOLS, *MARKER])
def test_without_completion_a_cap_only_takes_edges_away(
    tmp_path, no_completion, program
):
    source = THREE + {**PROTOCOLS, **MARKER}[program]
    full = edges(tmp_path / "full", source)
    for limit in (2, 3):
        assert edges(tmp_path / str(limit), source, cap=limit) <= full, limit


@pytest.mark.parametrize("program", MARKER)
def test_the_saturated_value_takes_no_branch_of_a_rule(tmp_path, program):
    source = MARKER[program]
    full = edges(tmp_path / "full", source)
    assert capped_edges(tmp_path / "capped", source) <= full


SNIPPETS = (
    Path(__file__).resolve().parent.parent
    / "evaluation"
    / "micro-benchmark"
    / "snippets"
)
CASES = sorted(path for path in SNIPPETS.glob("*/*") if path.is_dir())


def case_id(path):
    return f"{path.parent.name}/{path.name}"


@pytest.mark.parametrize("snippet", CASES, ids=case_id)
def test_without_completion_a_cap_only_takes_edges_away_from_a_benchmark_case(
    no_completion, snippet
):
    full = graph_edges(analysed(snippet, {}))
    for limit in (2, 3, 10):
        assert graph_edges(analysed(snippet, {}, cap=limit)) <= full, limit


@pytest.mark.parametrize("snippet", CASES, ids=case_id)
def test_regression_a_small_cap_adds_no_edge_to_a_benchmark_case(snippet):
    # With the steps at a fixpoint a cap may add edges (see the tests
    # below); on these programs it adds none.
    full = graph_edges(analysed(snippet, {}))
    for limit in (2, 3, 10):
        assert graph_edges(analysed(snippet, {}, cap=limit)) <= full, limit


# Final review, round 4, finding 2: code that only a suppressed call
# reaches is, for the analysis, code that no analysed code calls, or a value
# that holds nothing; the steps at a fixpoint apply to it. These tests pin
# what that gives at a cap of 2.

FACTORIES = (
    "def first(): return {name}\n"
    "def second(): return {name}\n"
    "def third(): return {name}\n"
)


def capped_edges(tmp_path, source):
    return edges(tmp_path, source, cap=2)


def test_a_function_that_a_suppressed_call_passed_an_argument_gets_its_default(
    tmp_path,
):
    source = (
        "def fallback(): pass\ndef real(): pass\n"
        "def leaf(cb=fallback):\n    cb()\n"
        + FACTORIES.format(name="leaf")
        + "for factory in (first, second, third):\n    factory()(real)\n"
    )
    full = edges(tmp_path / "full", source)
    capped = capped_edges(tmp_path / "capped", source)

    # Python calls leaf(real), then real.
    assert ("main.leaf", "main.real") in full
    assert ("main.leaf", "main.fallback") not in full
    assert ("main.leaf", "main.fallback") in capped


def test_a_key_that_a_suppressed_call_passed_reads_every_element(tmp_path):
    source = (
        "def good(): pass\ndef other(): pass\n"
        "TABLE = {'a': good, 'b': other}\n"
        "def pick(key):\n    TABLE[key]()\n"
        + FACTORIES.format(name="pick")
        + "for factory in (first, second, third):\n    factory()('a')\n"
    )
    full = edges(tmp_path / "full", source)
    capped = capped_edges(tmp_path / "capped", source)

    assert {e for e in full if e[0] == "main.pick"} == {("main.pick", "main.good")}
    assert ("main.pick", "main.other") in capped


def test_a_base_that_a_suppressed_call_passed_is_decided_absent(tmp_path):
    source = (
        "def helper(): pass\n"
        "class Lazy:\n    def __getattr__(self, name): return helper\n"
        "class Real:\n    def method(self): pass\n"
        "def make(base):\n"
        "    class Made(base, Lazy): pass\n"
        "    Made().method()\n"
        + FACTORIES.format(name="make")
        + "for factory in (first, second, third):\n    factory()(Real)\n"
    )
    full = edges(tmp_path / "full", source)
    capped = capped_edges(tmp_path / "capped", source)

    assert ("main.make", "main.Real.method") in full
    assert ("main.make", "main.Lazy.__getattr__") not in full
    assert ("main.make", "main.Lazy.__getattr__") in capped


def test_a_receiver_whose_annotation_saturated_holds_the_saturated_value(tmp_path):
    # Final review, round 8: the annotation gave nothing, so the receiver
    # was completed with an instance of its class (`K.run -> K.step`).
    source = (
        "import sys\n"
        "class A:\n    def step(self): pass\n"
        "class B(A): pass\nclass C(A): pass\n"
        "T = A if sys.argv else B if sys.path else C\n"
        "class K:\n"
        "    def step(self): pass\n"
        "    def run(self: T):\n        self.step()\n"
    )
    full = edges(tmp_path / "full", source)
    capped = sites(tmp_path / "capped", source, "main.K.run", cap=2)

    assert ("main.K.run", "main.A.step") in full
    assert ("main.K.run", "main.K.step") not in full
    assert capped == [(line_of(source, "self.step()"), [], "saturated")]


def test_the_static_and_class_methods_of_an_absorbed_instance_are_called(tmp_path):
    # A call of the saturated value may run them: they get no defaults.
    source = (
        "def f(): pass\ndef g(): pass\n"
        "class Tool:\n"
        "    @staticmethod\n    def run(cb=f): cb()\n"
        "    @classmethod\n    def make(cls, cb=f): cb()\n"
        "def call(tool):\n    tool.run(g)\n    tool.make(g)\n"
        "for tool in (Tool(), Tool(), Tool()):\n    call(tool)\n"
    )
    full = edges(tmp_path / "full", source)

    assert capped_edges(tmp_path / "capped", source) <= full


def test_the_document_never_names_the_saturated_value(tmp_path):
    # Final review, round 3, finding 3: an export target, like any other
    # part of the document, is a definition or an outside name.
    source = THREE + "def f(): pass\ndef g(): pass\ndef h(): pass\n"
    source += "for exported in (f, g, h):\n    pass\n"
    source += PROTOCOLS["a saturated base"] + PROTOCOLS["a saturated metaclass"]
    generator = analysed(tmp_path, {"main.py": source}, cap=2)
    document = generator.document()
    calls = document.pop("calls")
    sites = [site for records in calls.values() for site in records]
    causes = [site.pop("unresolved", None) for site in sites]

    assert "saturated" in causes
    assert "<saturated>" not in json.dumps([document, calls])
    assert "<saturated>" not in json.dumps(generator.output_points_to())


# A class is unknown when the set of a base expression or of its metaclass
# (written or inferred) holds the saturated value, or a base expression
# holds an unknown class. Nothing about it is known, its own members
# included: it and its instances are seen as the saturated value. Whether a
# class is unknown is decided between rounds (final review, rounds 5 and 6).

ANCESTRY = """
class Root:
    def __init_subclass__(cls): pass
    def method(self): pass
class Left(Root):
    def left(self): pass
class A(Root):
    def __init_subclass__(cls): pass
    def method(self): pass
class B(Root):
    def __init_subclass__(cls): pass
class C(Root):
    def __init_subclass__(cls): pass
def make(base):
    class Child(Left, base):
        def own(self): pass
        def calls_super(self):
            super().method()
    child = Child()
    child.own(); child.left(); child.method(); child.calls_super()
    Child.own(child)
for base in (A, B, C):
    make(base)
"""

# Final review, round 6, finding 1: whether `Made` is unknown was read in
# the round that decided it.
MADE = """
class A: pass
class B: pass
class C: pass
for base in (A, B, C):
    class Made(base):
        def __call__(self): pass
    instance = object.__new__(Made)
    instance()
"""

# Round 6, finding 2: every possible base supplies `__bool__`.
TRUTH = """
class M1(type):
    def __bool__(cls): return True
class M2(M1): pass
class M3(M1): pass
def pick(value): return value
base = M1
for candidate in (M2, M3):
    base = pick(candidate)
class Meta(base):
    def __len__(cls): return 0
class Value(metaclass=Meta): pass
if Value:
    pass
"""

# Round 6, finding 3: an inferred metaclass that saturates.
INFERRED = """
class M0(type): pass
class M1(M0): pass
class M2(M1): pass
for meta in (M0, M2):
    class A(metaclass=meta):
        def method(self): pass
for meta in (M0, M1):
    class B(metaclass=meta): pass
class C(A, B): pass
C.method(None)
"""

UNKNOWN = {"ancestry": ANCESTRY, "made": MADE, "truth": TRUTH, "inferred": INFERRED}


def everything(root, source, entries=("main.py",), **options):
    generator = analysed(root, {"main.py": source}, entry_points=entries, **options)
    return dumps(generator.document()), generator.output_points_to()


@pytest.mark.parametrize("program", UNKNOWN)
def test_unknown_classes_do_not_depend_on_the_order(tmp_path, monkeypatch, program):
    for limit in (2, None):
        found = set()
        for name, order in ORDERS.items():
            monkeypatch.setattr(solver.Solver, "order", order())
            root = tmp_path / f"{limit}-{name}"
            found.add(repr(everything(root, UNKNOWN[program], cap=limit)))
        assert len(found) == 1, limit


@pytest.mark.parametrize("program", UNKNOWN)
def test_an_unknown_class_adds_no_edge(tmp_path, program):
    full = edges(tmp_path / "full", UNKNOWN[program])
    assert capped_edges(tmp_path / "capped", UNKNOWN[program]) <= full


def test_nothing_about_an_unknown_class_is_known(tmp_path):
    full = edges(tmp_path / "full", ANCESTRY)
    capped = capped_edges(tmp_path / "capped", ANCESTRY)

    # Python orders Child, Left, the base, Root: the base's hook runs.
    assert ("main.make", "main.A.__init_subclass__") in full
    assert ("main.make", "main.make.Child.own") in full
    # Not even what Child's own body defines is known.
    assert not {e for e in capped if e[0] == "main.make"}
    assert not {
        e for e in capped if e[0].startswith("main.make.") and e[1].startswith("main.")
    }


def test_an_unknown_class_is_seen_as_the_saturated_value(tmp_path):
    # Called, a receiver, iterated, entered, a key, an operand, a base, an
    # except class, and through super(): each gives the saturated value,
    # and each call of what it gives is unresolved.
    source = (
        "class A:\n    def method(self): pass\n"
        "class B(A): pass\nclass C(A): pass\n"
        "def use(base):\n"
        "    class Unknown(base):\n"
        "        def method(self):\n"
        "            super().method()\n"
        "    class Derived(Unknown): pass\n"
        "    Unknown()\n"
        "    Unknown().method()\n"
        "    for item in Unknown():\n        item()\n"
        "    with Unknown() as entered:\n        entered()\n"
        "    {Unknown(): 1}[Unknown()]()\n"
        "    (Unknown() + 1)()\n"
        "    Derived().method()\n"
        "    try:\n        pass\n    except Unknown as error:\n        error()\n"
        "for base in (A, B, C):\n    use(base)\n"
    )
    generator = analysed(tmp_path, {"main.py": source}, cap=2)
    sites = generator.document()["calls"]

    assert {callee for site in sites["main.use"] for callee in site["callees"]} == set()
    # The instances that the except class catches were never made: its
    # name holds nothing.
    handler = line_of(source, "error()")
    assert {s.get("unresolved") for s in sites["main.use"] if s["line"] != handler} == {
        "saturated"
    }
    # super() in it: the method that it would find is not known.
    assert not {
        callee
        for site in sites.get("main.use.Unknown.method", [])
        for callee in site["callees"]
        if callee.startswith("main.")
    }
    definitions = generator.document()["definitions"]
    assert definitions["main.use.Unknown"]["mro"] == ["main.use.Unknown"]
    assert definitions["main.use.Derived"]["mro"] == ["main.use.Derived"]


def test_a_name_that_a_suppressed_call_set_is_within_the_bound_of_names(tmp_path):
    # Final review, round 5, finding 2: a set that a cap leaves smaller
    # but not empty can pass under another bound (four computed names).
    source = """
class C:
    def a(): pass
    def other(): pass
    b = c = d = e = other
name = "a"
def first(value):
    global name
    name = value
def second(value):
    global name
    name = value
def third(value):
    global name
    name = value
for setter in (first, second, third):
    setter("b")
    setter("c")
    setter("d")
    setter("e")
getattr(C, name)()
"""
    full = edges(tmp_path / "full", source)
    capped = capped_edges(tmp_path / "capped", source)

    # Five names: the call is unresolved without the cap.
    assert ("main", "main.C.a") not in full
    assert ("main", "main.C.a") in capped


# Final review, round 7: a rule that came back to an instance it remembered
# (here the instances that a pattern of attribute names reaches, when a
# matching name is assigned on their class later) loaded the attribute after
# the instance's class had become unknown.
PATTERN_REVISIT = """
from abc import ABC, abstractmethod
class A(ABC):
    @abstractmethod
    def visit_early(self): pass
class B: pass
class C: pass
base = A
class D(base):
    def visit_early(self): pass
obj = object.__new__(D)
def leaf(self): pass
def use(obj, name):
    getattr(obj, f"visit_{name}")()
def delay(flag=True):
    return lambda: lambda: lambda: lambda: lambda: B if flag else C
def update():
    global base
    base = delay()()()()()()
update()
def late():
    return lambda: lambda: lambda: lambda: lambda: lambda: lambda: lambda: A
def assign(cls):
    cls.visit_late = leaf
assign(late()()()()()()()()())
use(obj, "late")
"""

# Final review, round 8: a constraint that held an object (an `Each` that
# remembered the class of a class statement, the receiver of a binding) or a
# `__getattr__` that a lookup cached passed it to a rule after its class had
# become unknown.
HELD = {
    "statement class": """
class Meta(type):
    def __init__(cls, *args): pass
class A(metaclass=Meta): pass
class B: pass
class C: pass
base = A
class X(base): pass
def choose(flag=True):
    return B if flag else C
def update():
    global base
    base = choose()
update()
""",
    "receiver": PATTERN_REVISIT.replace('use(obj, "late")', "obj.visit_late()"),
    "bases": """
class A: pass
class B: pass
class C: pass
class E: pass
class F: pass
left = E
right = A
class X(left, right): pass
def choose(flag=True):
    return B if flag else C
def update():
    global right
    right = choose()
update()
def late():
    return lambda: lambda: lambda: lambda: lambda: lambda: F
def move():
    global left
    left = late()()()()()()()
move()
""",
    "fallback": """
class A: pass
class B: pass
class C: pass
base = A
class Hook(base):
    def __call__(self, name): pass
class Host:
    __getattr__ = object.__new__(Hook)
host = Host()
host.missing()
def delay(flag=True):
    return lambda: lambda: lambda: lambda: lambda: B if flag else C
def update():
    global base
    base = delay()()()()()()
update()
def late():
    return lambda: lambda: lambda: lambda: lambda: lambda: lambda: lambda: host
late()()()()()()()()().missing()
""",
}

GUARDED = {
    **{f"protocol: {name}": THREE + source for name, source in PROTOCOLS.items()},
    **{f"marker: {name}": source for name, source in MARKER.items()},
    **{f"unknown: {name}": source for name, source in UNKNOWN.items()},
    "pattern revisit": PATTERN_REVISIT,
    **{f"held: {name}": source for name, source in HELD.items()},
}


@pytest.mark.parametrize("program", GUARDED)
@pytest.mark.parametrize("order", ORDERS, ids=ORDERS)
def test_no_rule_sees_the_saturated_value_or_an_unknown_class(
    tmp_path, monkeypatch, program, order
):
    no_rule_sees_what_is_opaque(monkeypatch)
    monkeypatch.setattr(solver.Solver, "order", ORDERS[order]())
    analysed(tmp_path, {"main.py": GUARDED[program]}, cap=2)


# The audit itself: it sees the objects that the solver applies a constraint
# to in one call (`apply_each`), as it sees those of `apply`.


class _Records(solver.Constraint):
    """A constraint of its own class, which holds `held` in a slot."""

    __slots__ = ("held", "seen")

    def __init__(self, held, seen):
        self.held = held
        self.seen = seen

    def apply(self, obj):
        self.seen.append(obj)


def _audited_constraints(held, seen):
    """A constraint of each kind that reaches a rule in its own way: an
    `Each` (its own loop over the set), an `Each` of some kinds, an `Each`
    of a method (it keeps the function and its owner), and a constraint that
    the default loop applies object by object."""
    from pycg.analysis.model import Object

    def rule(obj, *args):
        seen.append(obj)

    class Rules:
        def rule(self, obj, *args):
            seen.append(obj)

    return {
        "each": solver.Each(rule, held),
        "each of kinds": solver.Each(rule, held, kinds=(Object,)),
        "each of a method": solver.Each(Rules().rule, held),
        "own apply": _Records(held, seen),
    }


@pytest.mark.parametrize(
    "kind", ["each", "each of kinds", "each of a method", "own apply"]
)
def test_the_audit_checks_each_object_of_a_set_that_reaches_a_rule(monkeypatch, kind):
    from pycg.analysis.model import Object, Saturated

    no_rule_sees_what_is_opaque(monkeypatch)
    first, second, opaque = Object("first"), Object("second"), Saturated("<saturated>")
    seen = []
    constraint = _audited_constraints(Object("held"), seen)[kind]

    constraint.apply_each([first, second])
    assert seen == [first, second]
    # Each object is checked when it arrives: the rule sees those before.
    with pytest.raises(AssertionError, match="saturated"):
        constraint.apply_each([first, opaque, second])
    assert seen == [first, second, first]


@pytest.mark.parametrize(
    "kind", ["each", "each of kinds", "each of a method", "own apply"]
)
def test_the_audit_checks_what_a_constraint_holds_when_it_gets_a_set(monkeypatch, kind):
    from pycg.analysis.model import Object, Saturated

    no_rule_sees_what_is_opaque(monkeypatch)
    seen = []
    constraint = _audited_constraints(Saturated("<saturated>"), seen)[kind]

    with pytest.raises(AssertionError, match="saturated"):
        constraint.apply_each([Object("first"), Object("second")])
    assert seen == []


def test_a_load_by_pattern_of_the_saturated_value_gives_it(tmp_path):
    # Final review, round 8, finding 2: the load dropped the saturated value,
    # and the call was unresolved as a computed name.
    source = """
class A:
    def visit_x(self): pass
class B(A): pass
class C(A): pass
def use(value, name):
    getattr(value, f"visit_{name}")()
for value in (A(), B(), C()):
    use(value, "x")
"""
    line = line_of(source, "getattr(")

    assert sites(tmp_path, source, "main.use", cap=2) == [
        (line, ["<builtin>.getattr"], None),
        (line, [], "saturated"),
    ]


ANALYSIS = Path(__file__).resolve().parent.parent / "pycg" / "analysis"

# The rules of `Each` constraints that put nothing in a node of their own,
# by name; every other `Each` names the nodes where its rule puts what it
# finds (`results`), which get the saturated value in its place.
WITHOUT_RESULTS = {
    # Calls whose result is not used (special methods that Python calls,
    # call backs, comparisons, conversions, the class statement's calls).
    "call_dunder",
    "_call_eq",
    "compare_member",
    "_searched_type",
    "_python_contains",
    "_percent_format",
    "_percent",
    "_call_protocol",
    # A builtin that consumes a lazy object of the standard library: the
    # activation joins its result node to the consuming iteration's.
    "_consume_library",
    "_sequence_length",
    "_raise",
    "_set_name",
    "_call_back_object",
    "_call_metaclass",
    "_init_statement_class",
    "_statement_new",
    "_statement_made",
    # What `type(name, bases, dict)` calls for the class that it makes.
    "_type_bases",
    "_type_base",
    "_call_type_metaclass",
    "by_new",
    "of_class",
    "key",
    "stored",
    # The pairing of compared containers, which joins their elements by
    # edges only.
    "arrive",
    # Stores and deletions.
    "_deliver_store",
    "_deliver_delete",
    "_field_values",
    # Decisions about a class: its metaclass and whether it is a dataclass.
    "_keyword_candidate",
    "_dataclass_decorator",
    "_dataclass_base",
    # The bases that a module's own stub declares: a class below an outside
    # class joins its nodes by edges. Past the cap the node admits nothing
    # more; what it admitted stays (design.md, "A module's own stub").
    "_stub_base",
    # What they find goes to the accesses that reach the object, which
    # name their results; a name that is not a str constant makes the
    # access a computed name (`MAX_DYNAMIC_NAMES`). `_pattern_class_instance`
    # watches the instances of a class for the accesses by pattern on them:
    # when that node saturates, the candidates of those accesses are lost
    # and their calls keep the cause `computed name` (final review, round
    # 9: decided as a stated limit, see docs/format.md, not a result node
    # that follows accesses registered later).
    "_pattern_class_instance",
    "load_by_pattern",
}


def test_every_rule_that_puts_objects_in_a_node_names_it():
    # Final review, round 8, finding 2: a load by pattern had a result and
    # did not name it, so it dropped the saturated value.
    unnamed = set()
    for path in sorted(ANALYSIS.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Each"
                and not any(keyword.arg == "results" for keyword in node.keywords)
            ):
                rule = node.args[0]
                unnamed.add(rule.attr if isinstance(rule, ast.Attribute) else rule.id)

    assert unnamed == WITHOUT_RESULTS


# The other constraints without results: a store, a deletion, the bases of
# a class, the items that `dict.update` stores.
CONSTRAINTS_WITHOUT_RESULTS = {"Store", "Delete", "_Bases", "_DictItems"}


def test_every_other_constraint_with_a_result_names_it():
    pending, without = solver.Constraint.__subclasses__(), set()
    while pending:
        kind = pending.pop()
        pending.extend(kind.__subclasses__())
        analysed = kind.__module__.startswith("pycg.")
        if (
            analysed
            and "apply" in vars(kind)
            and kind.results is solver.Constraint.results
        ):
            without.add(kind.__name__)

    assert without == CONSTRAINTS_WITHOUT_RESULTS


def test_limit_an_outside_operand_may_saturate_a_getattr_name(tmp_path):
    # Codex review, round 2: the name holds the pattern and the str of
    # unknown value that the outside operand adds. With a cap of 1 that
    # saturates the name, and the load of visit_a is lost; with a cap of 2
    # it stays. Python calls hit when ext.value is "a".
    source = """
import ext
def hit(): pass
class C: pass
c = C()
c.visit_a = hit
getattr(c, "visit_" + ext.value)()
"""
    for cap, found in ((1, False), (2, True)):
        graph = analysed(tmp_path / str(cap), {"main.py": source}, cap=cap).output()
        assert ("main.hit" in graph.get("main", [])) is found, cap


@pytest.mark.parametrize(
    "source",
    [
        # Codex review, round 7: lower() of a class member gives the str
        # and any value, two objects.
        "class C:\n    value = 'abc'\nC.value.lower().upper()\n",
        # Both values stored under class members go to the alias node of
        # the callee's **kw, two objects.
        "class Keys:\n    taken = 'taken'\n    keep = 'pre_a'\n"
        "def consumed(): pass\ndef target(): pass\n"
        "def use(taken, **kw):\n    kind = 'a'\n    kw['pre_' + kind]()\n"
        "use(**{Keys.taken: consumed, Keys.keep: target})\n",
    ],
)
def test_limit_a_widening_for_an_alias_may_saturate_a_node_at_cap_1(
    tmp_path, monkeypatch, source
):
    # The widening adds one object, so a node saturates one object sooner:
    # at a cap of 1 the call is lost, on every order; caps of 2 and more
    # keep it (a cap only takes edges away, see design, Bounds).
    for name, order in ORDERS.items():
        monkeypatch.setattr(solver.Solver, "order", order())
        for cap in (1, 2, 3, 5000):
            graph = analysed(
                tmp_path / f"{name}-{cap}".replace(" ", "_"),
                {"main.py": source},
                cap=cap,
            ).output()
            found = {c for found in graph.values() for c in found}
            hit = "<builtin>.str.upper" in found or "main.target" in found
            assert hit is (cap != 1), (name, cap)
