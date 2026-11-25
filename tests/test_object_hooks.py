import textwrap

from programs import callees, main_graph

DEFINITIONS = """
import ext
def f(): pass
def g(): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_call_of_a_class_calls_new_then_init_on_its_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Point:
            def __new__(cls, x):
                return super().__new__(cls)
            def __init__(self, x):
                pass
            def norm(self):
                pass
        Point(1).norm()
        """,
    )

    assert callees(graph, "main") == [
        "main.Point.__init__",
        "main.Point.__new__",
        "main.Point.norm",
    ]
    assert callees(graph, "main.Point.__new__") == [
        "<builtin>.object.__new__",
        "<builtin>.super",
    ]


def test_a_new_that_returns_another_object_runs_no_init(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Real:
            def __init__(self):
                pass
            def run(self):
                pass
        class Proxy:
            def __new__(cls):
                return Real()
            def __init__(self):
                pass
        Proxy().run()
        """,
    )

    assert callees(graph, "main") == ["main.Proxy.__new__", "main.Real.run"]
    assert callees(graph, "main.Proxy.__new__") == ["main.Real.__init__"]


def test_new_may_return_an_instance_of_a_subclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Shape:
            def __new__(cls, kind):
                if kind == "circle":
                    return object.__new__(Circle)
                return object.__new__(cls)
        class Circle(Shape):
            def __init__(self, kind):
                pass
        def make():
            Shape("circle")
        """,
    )

    assert callees(graph, "main.make") == ["main.Circle.__init__", "main.Shape.__new__"]


def test_a_subclass_inherits_new_and_its_own_init_runs(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Base:
            @staticmethod
            def __new__(cls):
                return super().__new__(cls)
        class Child(Base):
            def __init__(self):
                pass
        def make():
            Child()
        """,
    )

    assert callees(graph, "main.make") == ["main.Base.__new__", "main.Child.__init__"]


def test_new_gets_the_class_even_when_no_analysed_code_calls_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Library:
            def __new__(cls):
                return cls()
            def __call__(self):
                pass
        """,
    )

    assert callees(graph, "main.Library.__new__") == ["main.Library.__new__"]


def test_an_outside_base_creates_the_instance(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Failure(Exception):
            def __init__(self):
                pass
            def describe(self):
                pass
        Failure().describe()
        """,
    )

    assert callees(graph, "main") == ["main.Failure.__init__", "main.Failure.describe"]


def test_a_class_statement_calls_init_subclass_of_its_base(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Plugin:
            def __init_subclass__(cls, handler=None, **options):
                handler()
                cls.setup()
            @classmethod
            def setup(cls):
                pass
        class Audio(Plugin, handler=f, metaclass=type):
            @classmethod
            def setup(cls):
                pass
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "main.Plugin.__init_subclass__",
    ]
    assert callees(graph, "main.Plugin.__init_subclass__") == [
        "main.Audio.setup",
        "main.f",
    ]


def test_init_subclass_chains_through_super(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Base:
            @classmethod
            def __init_subclass__(cls, **options):
                super().__init_subclass__(**options)
                cls.ready()
        class Middle(Base):
            def __init_subclass__(cls, **options):
                super().__init_subclass__(**options)
        def declare():
            class Leaf(Middle):
                @classmethod
                def ready(cls):
                    pass
        """,
    )

    assert callees(graph, "main.declare") == [
        "<builtin>.classmethod",
        "main.Middle.__init_subclass__",
    ]
    assert callees(graph, "main.Middle.__init_subclass__") == [
        "<builtin>.super",
        "main.Base.__init_subclass__",
    ]
    assert callees(graph, "main.Base.__init_subclass__") == [
        "<builtin>.object.__init_subclass__",
        "<builtin>.super",
        "main.declare.Leaf.ready",
    ]


def test_an_outside_base_hook_gives_no_edge(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Model(ext.Base, table="users"):
            pass
        """,
    )

    assert callees(graph, "main") == []


def test_a_class_statement_calls_set_name_on_the_values_of_its_body(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Field:
            def __set_name__(self, owner, name):
                owner.declare()
        class Plain:
            pass
        def build():
            class Model:
                title = Field()
                other = Plain()
                @classmethod
                def declare(cls):
                    pass
        """,
    )

    assert callees(graph, "main.build") == [
        "<builtin>.classmethod",
        "main.Field.__set_name__",
    ]
    assert callees(graph, "main.Field.__set_name__") == ["main.build.Model.declare"]


def test_set_name_gets_the_name_of_the_attribute(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Alias:
            def __set_name__(self, owner, name):
                getattr(Registry, name)()
        class Registry:
            run = staticmethod(f)
            other = staticmethod(g)
        class Model:
            run = Alias()
        """,
    )

    assert callees(graph, "main.Alias.__set_name__") == ["<builtin>.getattr", "main.f"]


def test_a_subscript_of_a_class_calls_class_getitem_with_the_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Registry:
            def __init__(self):
                pass
            def __class_getitem__(cls, key):
                cls.lookup(key)
                return f
            @classmethod
            def lookup(cls, key):
                pass
        class Audio(Registry):
            @classmethod
            def lookup(cls, key):
                pass
        class Plain:
            pass
        def use():
            Audio["mp3"]()
            Plain[0]
            Registry[1:2]
        """,
    )

    assert callees(graph, "main.use") == ["main.Registry.__class_getitem__", "main.f"]
    assert callees(graph, "main.Registry.__class_getitem__") == [
        "main.Audio.lookup",
        "main.Registry.lookup",
    ]


def test_an_outside_class_getitem_gives_the_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from typing import Generic, TypeVar
        T = TypeVar("T")
        class Box(Generic[T]):
            def __init__(self):
                pass
            def get(self):
                pass
        class Stub(ext.Generic):
            def get(self):
                pass
        def use():
            Box[int]().get()
            Stub[int]().get()
        """,
    )

    assert callees(graph, "main.use") == [
        "ext.Generic.__init__",
        "main.Box.__init__",
        "main.Box.get",
        "main.Stub.get",
    ]


def test_class_hooks_that_no_analysed_code_calls_get_classes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Hooks:
            def __init__(self):
                pass
            def __call__(self):
                pass
            def __init_subclass__(cls):
                cls()
            def __class_getitem__(cls, key):
                cls()
        """,
    )

    assert callees(graph, "main.Hooks.__init_subclass__") == ["main.Hooks.__init__"]
    assert callees(graph, "main.Hooks.__class_getitem__") == ["main.Hooks.__init__"]


def test_super_finds_the_attributes_of_object_after_the_last_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Plain:
            def __init__(self):
                super().__init__()
                super().missing()
        Plain()
        """,
    )

    assert callees(graph, "main.Plain.__init__") == [
        "<builtin>.object.__init__",
        "<builtin>.super",
    ]
    assert callees(graph, "main") == ["main.Plain.__init__"]
