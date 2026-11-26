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

    assert "main.Hook.__get__" in callees(graph, "main.Hooked.__getattribute__")
    assert "main.Hook.__get__" not in callees(graph, "main.use")
    assert callees(graph, "main.Child.run") == ["<builtin>.super", "main.Hook.__get__"]


def test_limit_object_hooks_by_name_run_no_descriptor(tmp_path):
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


def test_a_subclass_of_a_stubbed_outside_descriptor_is_itself_the_value(tmp_path):
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


STORED = """
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass
"""


def stored_graph(tmp_path, source):
    return main_graph(tmp_path, STORED + textwrap.dedent(source))


def index_callees(graph, caller):
    return [c for c in callees(graph, caller) if c.endswith(".index")]


def test_a_store_through_a_property_does_not_reach_a_load(tmp_path):
    graph = stored_graph(
        tmp_path,
        """
        class Table:
            def get(self): return Rows()
            def put(self, value): pass
            headers = property(get, put)
            @property
            def fixed(self): return Rows()
        def use(table):
            table.headers = Pairs()
            table.headers.index(1)
            table.fixed = Pairs()
            table.fixed.index(1)
        use(Table())
        """,
    )

    assert index_callees(graph, "main.use") == ["main.Rows.index"]
    assert "main.Table.put" in callees(graph, "main.use")


def test_a_store_through_a_data_descriptor_does_not_reach_a_load(tmp_path):
    graph = stored_graph(
        tmp_path,
        """
        class Field:
            def __get__(self, obj, owner=None): return Rows()
            def __set__(self, obj, value): pass
        class Removable:
            def __get__(self, obj, owner=None): return Rows()
            def __delete__(self, obj): pass
        class Model:
            field = Field()
            removable = Removable()
        def use(model):
            model.field = Pairs()
            model.field.index(1)
            model.removable = Pairs()
            model.removable.index(1)
        use(Model())
        """,
    )

    assert index_callees(graph, "main.use") == ["main.Rows.index"]


def test_a_store_of_a_name_that_no_data_descriptor_takes_reaches_a_load(tmp_path):
    graph = stored_graph(
        tmp_path,
        """
        class Lazy:
            def __get__(self, obj, owner=None): return Rows()
        class Model:
            __slots__ = ("slot",)
            lazy = Lazy()
            annotated: int
            def method(self): pass
        class Plain:
            pass
        def lazy(model):
            model.lazy = Pairs()
            model.lazy.index(1)
        def slot(model):
            model.slot = Pairs()
            model.slot.index(1)
        def annotated(model):
            model.annotated = Pairs()
            model.annotated.index(1)
        def method(model):
            model.method = Pairs()
            model.method.index(1)
        def plain(obj):
            obj.value = Pairs()
            obj.value.index(1)
        lazy(Model())
        slot(Model())
        annotated(Model())
        method(Model())
        plain(Plain())
        """,
    )

    assert index_callees(graph, "main.lazy") == ["main.Pairs.index", "main.Rows.index"]
    for caller in ("slot", "annotated", "method", "plain"):
        assert index_callees(graph, f"main.{caller}") == ["main.Pairs.index"]


def test_a_store_reaches_a_load_where_one_hierarchy_has_no_descriptor(tmp_path):
    graph = stored_graph(
        tmp_path,
        """
        import sys
        class WithProperty:
            @property
            def value(self): return Rows()
            @value.setter
            def value(self, v): pass
        class Without:
            pass
        Base = WithProperty if sys.argv else Without
        class Model(Base):
            pass
        def use(model):
            model.value = Pairs()
            model.value.index(1)
        use(Model())
        """,
    )

    assert index_callees(graph, "main.use") == ["main.Pairs.index", "main.Rows.index"]


def test_a_store_waits_for_a_base_that_a_call_gives(tmp_path):
    graph = stored_graph(
        tmp_path,
        """
        class WithProperty:
            @property
            def value(self): return Rows()
            @value.setter
            def value(self, v): pass
        def base():
            return WithProperty
        def use(model):
            model.value = Pairs()
            model.value.index(1)
        class Model(base()):
            pass
        use(Model())
        """,
    )

    assert index_callees(graph, "main.use") == ["main.Rows.index"]


def test_limit_a_member_whose_value_the_analysis_does_not_see_takes_the_store(
    tmp_path,
):
    graph = stored_graph(
        tmp_path,
        """
        def make(member):
            class Model:
                value = member
            model = Model()
            model.value = Pairs()
            model.value.index(1)
        """,
    )

    assert index_callees(graph, "main.make") == []


def test_limit_a_property_stored_on_the_class_after_its_body_lets_the_store_write(
    tmp_path,
):
    graph = stored_graph(
        tmp_path,
        """
        class Model:
            pass
        def get(self): return Rows()
        def put(self, value): pass
        Model.value = property(get, put)
        def use(model):
            model.value = Pairs()
            model.value.index(1)
        use(Model())
        """,
    )

    assert index_callees(graph, "main.use") == ["main.Pairs.index", "main.Rows.index"]


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
    "property_store_skips_dict",
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
