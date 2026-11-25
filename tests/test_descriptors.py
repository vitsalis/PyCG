"""Descriptors other than functions, `staticmethod`, `classmethod` and
`property`: instances whose class defines `__get__`, `__set__` or
`__delete__`, found as class attributes."""

import itertools
import json
import textwrap
from pathlib import Path

import pytest
from programs import callees, main_graph, no_rule_sees_what_is_opaque, write

from pycg.analysis import solver
from pycg.formats import dumps
from pycg.pycg import CallGraphGenerator

SNIPPETS = (
    Path(__file__).resolve().parent.parent
    / "evaluation"
    / "micro-benchmark"
    / "snippets"
    / "descriptors"
)

DEFINITIONS = """
def f(): pass
class Hook:
    def __get__(self, obj, owner=None):
        owner.made()
        obj.used()
        return f
class App:
    hook = Hook()
    @classmethod
    def made(cls): pass
    def used(self): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_load_through_an_instance_calls_get_with_the_instance_and_class(
    tmp_path,
):
    graph = graph_of(tmp_path, "App().hook()\n")

    # From the scope of the load; the load gives what `__get__` returns.
    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "main.Hook.__get__",
        "main.f",
    ]
    assert callees(graph, "main.Hook.__get__") == ["main.App.made", "main.App.used"]


def test_a_load_through_the_class_calls_get_without_an_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def load():
            App.hook()
        """,
    )

    assert callees(graph, "main.load") == ["main.Hook.__get__", "main.f"]
    # The instance is None: only the class is used.
    assert callees(graph, "main.Hook.__get__") == ["main.App.made"]


def test_an_instance_without_get_is_the_value_of_the_load(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Tool:
            def __call__(self): pass
        class Box:
            tool = Tool()
        def use():
            Box().tool()
        """,
    )

    assert callees(graph, "main.use") == ["main.Tool.__call__"]


def test_a_value_in_the_instance_is_no_descriptor(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Bare:
            pass
        def use():
            bare = Bare()
            bare.hook = Hook()
            bare.hook
        """,
    )

    # Python calls `__get__` only for what it finds on the class.
    assert callees(graph, "main.use") == []


def test_a_store_and_a_deletion_call_set_and_delete(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Field:
            def __set__(self, obj, value):
                value()
            def __delete__(self, obj):
                obj.used()
        class User:
            email = Field()
            def used(self): pass
        def use():
            user = User()
            user.email = f
            del user.email
        """,
    )

    assert callees(graph, "main.use") == ["main.Field.__delete__", "main.Field.__set__"]
    assert callees(graph, "main.Field.__set__") == ["main.f"]
    assert callees(graph, "main.Field.__delete__") == ["main.User.used"]


def test_the_class_hook_is_the_caller_of_get_and_super_is_not(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Hooked:
            hook = Hook()
            def __getattribute__(self, name):
                return object.__getattribute__(self, name)
        class Child(Hooked):
            def run(self):
                super().hook
        def use():
            Hooked().hook
        """,
    )

    # As for a property: the class's own hook runs the accessor.
    assert "main.Hook.__get__" in callees(graph, "main.Hooked.__getattribute__")
    assert "main.Hook.__get__" not in callees(graph, "main.use")
    assert callees(graph, "main.Child.run") == ["<builtin>.super", "main.Hook.__get__"]


def test_limit_object_hooks_by_name_run_no_descriptor(tmp_path):
    # Python's `object.__setattr__(self, "x", v)` and its siblings, also
    # through `super()`, run the data descriptor of the class. The analysis
    # does not: the stubs do not tell whose native slot a hook is, and a
    # star import may supply another `object` (a limit).
    graph = main_graph(
        tmp_path,
        """
class Field:
    def __get__(self, obj, owner=None): pass
    def __set__(self, obj, value): pass
    def __delete__(self, obj): pass
class User:
    email = Field()
    def by_object(self):
        object.__setattr__(self, "email", 1)
        object.__getattribute__(self, "email")
        object.__delattr__(self, "email")
    def by_super(self):
        super().__setattr__("email", 1)
        super().__delattr__("email")
User().by_object()
User().by_super()
""",
    )

    for method in ("by_object", "by_super"):
        found = callees(graph, f"main.User.{method}")
        assert not [c for c in found if c.startswith("main.Field")]


# Subclasses of the builtin `property`, and descriptors of outside bases.


def test_a_subclass_of_a_stubbed_outside_descriptor_is_itself_the_value(tmp_path):
    # Regression: the lookup of `__get__` gives a bound outside method that
    # the stubs describe (`functools.cached_property.__get__`), which is
    # called by its stub; the instance is also the value of the load, and the
    # wrapped method is not called (Python calls it).
    graph = main_graph(
        tmp_path,
        """
        import functools
        class lazy(functools.cached_property):
            def describe(self): pass
        class Report:
            @lazy
            def data(self): pass
        def use():
            Report().data.describe()
        use()
        """,
    )

    assert callees(graph, "main.use") == ["main.lazy.describe"]


def test_a_subclass_of_an_unstubbed_outside_base_is_itself_the_value(tmp_path):
    # Regression: an outside base without stubs gives a plain external for
    # `__get__`, which is not called; the instance is the value of the load.
    graph = main_graph(
        tmp_path,
        """
        import ext
        class lazy(ext.Descriptor):
            def describe(self): pass
        class Report:
            @lazy
            def data(self): pass
        def use():
            Report().data.describe()
        use()
        """,
    )

    assert callees(graph, "main.use") == ["main.lazy.describe"]


def test_a_property_subclass_in_an_exhaustive_order_runs_the_getter(tmp_path):
    # More hierarchies than the analysis enumerates: the exhaustive order
    # stands for all of them, so `property`'s `__get__` runs, and, as in an
    # order without `property`, the instance is also the value.
    graph = main_graph(
        tmp_path,
        """
        import sys
        class X1: pass
        class Y1: pass
        class X2: pass
        class Y2: pass
        class X3: pass
        class Y3: pass
        class Plain:
            def describe(self): pass
        class P(
            property if sys.argv else Plain,
            X1 if sys.argv else Y1,
            X2 if sys.argv else Y2,
            X3 if sys.argv else Y3,
        ):
            pass
        def read(self): pass
        class Item:
            value = P(read)
        def use():
            Item().value.describe()
        use()
        """,
    )

    assert callees(graph, "main.use") == ["main.Plain.describe", "main.read"]


def test_a_class_method_without_an_owner_binds_the_metaclass_of_a_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Meta(type):
            @staticmethod
            def kind(): pass
        class Model(metaclass=Meta):
            @staticmethod
            def kind(): pass
        def make(cls):
            cls.kind()
        classmethod(make).__get__(Model)()
        """,
    )

    # `type(Model)` is `Meta`: `Meta.kind`, not `Model.kind`.
    assert callees(graph, "main.make") == ["main.Meta.kind"]


def test_a_class_method_binds_an_outside_owner(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def make(cls):
            cls.from_bytes(b"\\x01", "big")
        classmethod(make).__get__(None, int)()
        """,
    )

    assert callees(graph, "main.make") == ["<builtin>.int.from_bytes"]


def test_an_explicit_owner_wins_over_the_class_of_the_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            @staticmethod
            def kind(): pass
        class Other:
            @staticmethod
            def kind(): pass
        def make(cls):
            cls.kind()
        classmethod(make).__get__(Base(), Other)()
        """,
    )

    assert callees(graph, "main.make") == ["main.Other.kind"]


# Saturation: a cap of 2 reached by the receiver of a descriptor method, by
# the accessor field of a property and by the base expression of a property
# subclass. Each program gives the same documents under every solver order
# and every order of its modules, and fewer edges than without a cap.
SATURATING = {
    "the receiver of __get__": {
        "main.py": """
class classproperty(property):
    def __get__(self, instance, owner=None):
        return self.fget.__get__(None, owner)()
class Path:
    @classproperty
    @classmethod
    def a(cls): return cls
    @classproperty
    @classmethod
    def b(cls): return cls
    @classproperty
    @classmethod
    def c(cls): return cls
    def use(self):
        return self.a, self.b, self.c
""",
        "other.py": "from main import Path\nPath().use()\n",
    },
    "the accessor field": {
        "main.py": """
class plain(property):
    pass
def f0(self): pass
def f1(self): pass
def f2(self): pass
class Item:
    value = plain(f0)
    value.getter(f1)
    value.getter(f2)
prop = property(f0)
prop.getter(f1)
prop.getter(f2)
def use(item):
    item.value
    prop.fget(item)
""",
        "other.py": "from main import Item, use\nuse(Item())\n",
    },
    "the base expression": {
        "main.py": """
from other import choose
def read(self): pass
import sys
class tracked(choose(len(sys.argv))):
    pass
class Item:
    value = tracked(read)
def use(item):
    item.value.method()
use(Item())
""",
        "other.py": """
class A:
    def method(self): pass
class B:
    def method(self): pass
def choose(i):
    return [property, A, B][i]
""",
    },
}


@pytest.mark.parametrize("program", SATURATING)
def test_saturated_descriptors_give_the_same_results_in_every_order(
    tmp_path, monkeypatch, program
):
    no_rule_sees_what_is_opaque(monkeypatch)
    files = SATURATING[program]
    write(tmp_path, files)
    expected = None
    for name, order in solver_orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        for entries in itertools.permutations(files):
            found = documents(tmp_path, entries, cap=2)
            if expected is None:
                expected = found
            assert found == expected, (name, entries)
    # The cap is reached: the graph is not the one without a cap.
    uncapped = documents(tmp_path, list(files), cap=None)
    assert edges(expected) < edges(uncapped)


def edges(document):
    calls = json.loads(document)["calls"]
    return {
        (caller, callee)
        for caller, sites in calls.items()
        for site in sites
        for callee in site["callees"]
    }


def solver_orders():
    return {
        "first in, first out": solver.Order(),
        "last in, first out": solver.LastInFirstOut(),
        "reversed": solver.Reversed(),
        "random 1": solver.Shuffled(1),
        "random 2": solver.Shuffled(2),
    }


def documents(root, entries, **options):
    generator = CallGraphGenerator(
        [str(root / entry) for entry in entries], str(root), **options
    )
    generator.analyze()
    return dumps(generator.document())


# The micro-benchmark cases of this rule give the same graph without a cap.
CASES = [
    "outside_descriptor_subclass",
    "own_class_named_property",
    "property_earlier_outside_base",
    "property_get_explicit",
    "property_get_forwards_none",
    "property_get_not_none",
    "property_get_without_instance",
    "property_in_instance_dict",
    "property_init_invalid",
    "property_init_not_called",
    "property_init_unrelated",
    "property_on_metaclass",
    "property_set_returns",
    "property_subclass_call_form",
    "property_subclass_classmethod",
    "property_subclass_copy",
    "property_subclass_copy_init",
    "property_subclass_decorator",
    "property_subclass_get_override",
    "property_subclass_late_base",
    "property_subclass_set_override",
    "property_subclass_super",
    "property_subclass_two_modules",
    "property_subclass_value_is_result",
    "wrapper_get_binds",
    "wrapper_get_double_star",
    "wrapper_get_invalid",
]


@pytest.mark.parametrize("case", CASES)
def test_a_descriptor_case_gives_the_same_graph_without_a_cap(case):
    snippet = SNIPPETS / case
    graphs = []
    for cap in ("default", None):
        options = {} if cap == "default" else {"cap": cap}
        generator = CallGraphGenerator(
            [str(snippet / "main.py")], str(snippet), **options
        )
        generator.analyze()
        graphs.append(generator.output())
    assert graphs[0] == graphs[1]


def test_the_descriptor_cases_are_listed():
    listed = {path.name for path in SNIPPETS.glob("*") if path.is_dir()}
    assert set(CASES) <= listed
