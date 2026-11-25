import textwrap

import pytest
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


SHARED_NEW = """
{prelude}
class Base:
{new}
class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
Quiet().speak()
"""

ALLOCATING_NEWS = {
    "object.__new__": """
    def __new__(cls, *args):
        return object.__new__(cls)
""",
    "super()": """
    def __new__(cls, *args):
        return super().__new__(cls)
""",
    "super naming the class, through a local with stores": """
    def __new__(cls, *args, **kwargs):
        instance = super(Base, cls).__new__(cls)
        instance.ready = False
        return instance
""",
    "a static method": """
    @staticmethod
    def __new__(cls):
        return super().__new__(cls)
""",
}

OTHER_NEWS = {
    "another class": """
    def __new__(cls, *args):
        return object.__new__(Loud)
""",
    "cls rebound": """
    def __new__(cls, *args):
        cls = Loud
        return object.__new__(cls)
""",
    "a local bound to something else too": """
    def __new__(cls, *args):
        instance = object.__new__(cls)
        if args:
            instance = Loud()
        return instance
""",
    "a store of __class__": """
    def __new__(cls, *args):
        instance = object.__new__(cls)
        instance.__class__ = Loud
        return instance
""",
    "another decorator": """
    @keep
    def __new__(cls, *args):
        return object.__new__(cls)
""",
}

KEEP = """
def keep(function):
    return function
"""

SHADOWING_PRELUDES = {
    "a module object": "class object: pass",
    "a module super": """
class Maker:
    def __new__(cls, *rest):
        return object.__new__(Loud)
def super(*args):
    return Maker
""",
}


@pytest.mark.parametrize("new", ALLOCATING_NEWS)
def test_a_new_that_allocates_gives_a_class_call_only_its_class(tmp_path, new):
    source = SHARED_NEW.format(prelude="", new=ALLOCATING_NEWS[new])
    graph = graph_of(tmp_path, source)

    assert "main.Quiet.speak" in callees(graph, "main")
    assert "main.Loud.__getattr__" not in callees(graph, "main")


@pytest.mark.parametrize("new", OTHER_NEWS)
def test_a_new_that_may_give_another_object_keeps_what_it_returns(tmp_path, new):
    source = SHARED_NEW.format(prelude=KEEP, new=OTHER_NEWS[new])
    graph = graph_of(tmp_path, source)

    assert "main.Loud.__getattr__" in callees(graph, "main")


@pytest.mark.parametrize("prelude", SHADOWING_PRELUDES)
def test_a_new_allocates_only_through_the_builtin_names(tmp_path, prelude):
    new = ALLOCATING_NEWS["object.__new__" if "object" in prelude else "super()"]
    source = SHARED_NEW.format(prelude=SHADOWING_PRELUDES[prelude], new=new)
    graph = graph_of(tmp_path, source)

    assert "main.Loud.__getattr__" in callees(graph, "main")


def test_super_naming_a_rebound_class_name_does_not_allocate(tmp_path):
    source = SHARED_NEW.format(
        prelude="",
        new=ALLOCATING_NEWS["super naming the class, through a local with stores"],
    )
    graph = graph_of(tmp_path, source + "Base = Loud\n")

    assert "main.Loud.__getattr__" in callees(graph, "main")


def test_an_allocating_chain_allocates_through_every_new(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Root:
            def __new__(cls, *args):
                instance = super(Root, cls).__new__(cls)
                instance.flag = False
                return instance
        class Base(Root):
            def __new__(cls, *args, **kwargs):
                instance = super().__new__(cls, *args, **kwargs)
                instance.done = Done()
                return instance
            def finish(self):
                self.done.run()
        class Done:
            def run(self):
                pass
        class Loud(Base):
            def __getattr__(self, name):
                return f
        class Quiet(Base):
            def speak(self):
                pass
        Loud()
        quiet = Quiet()
        quiet.speak()
        quiet.finish()
        """,
    )

    assert callees(graph, "main") == [
        "main.Base.__new__",
        "main.Base.finish",
        "main.Quiet.speak",
    ]
    assert callees(graph, "main.Base.finish") == ["main.Done.run"]


def test_a_class_whose_mro_reaches_a_new_that_gives_another_keeps_it(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Allocating:
            def __new__(cls):
                return super().__new__(cls)
        class Factory(Allocating):
            def __new__(cls):
                return Real()
        class Real:
            def run(self):
                pass
        class Made(Factory):
            def run(self):
                pass
        class Plain(Allocating):
            def run(self):
                pass
        def made():
            Made().run()
        def plain():
            Plain().run()
        """,
    )

    assert callees(graph, "main.made") == ["main.Factory.__new__", "main.Real.run"]
    assert callees(graph, "main.plain") == ["main.Allocating.__new__", "main.Plain.run"]
