from programs import callees, main_graph


def test_calling_a_class_that_is_abstract_by_abc_runs_no_init(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Base(abc.ABC):
            def __init__(self): pass
            @abc.abstractmethod
            def run(self): pass
        class Middle(Base):
            def __init__(self): pass
        class Leaf(Middle):
            def __init__(self): pass
            def run(self): pass
        def make(kind):
            return kind()
        for kind in (Base, Middle, Leaf):
            make(kind).run()
        """,
    )

    assert callees(graph, "main.make") == ["main.Leaf.__init__"]
    assert callees(graph, "main") == [
        "abc.abstractmethod",
        "main.Leaf.run",
        "main.make",
    ]


def test_abstract_by_metaclass_keyword_and_property(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABCMeta, abstractmethod
        class Base(metaclass=ABCMeta):
            def __init__(self): pass
            @property
            @abstractmethod
            def size(self): pass
        Base()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.property", "abc.abstractmethod"]


def test_abstract_through_an_outside_abc(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from collections.abc import Mapping
        class Partial(Mapping):
            def __init__(self): pass
            def __getitem__(self, key): pass
        class Full(Partial):
            def __init__(self): pass
            def __iter__(self): pass
            def __len__(self): pass
        Partial()
        Full()
        """,
    )

    assert callees(graph, "main") == ["main.Full.__init__"]


def test_a_class_abstract_without_abcmeta_or_by_convention_is_instantiated(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import abstractmethod
        class Plain:
            def __init__(self): pass
            def run(self):
                self.step()
            @abstractmethod
            def step(self): pass
        class Conventional:
            def __init__(self): pass
            def step(self):
                raise NotImplementedError
        class Lone:
            def run(self):
                self.step()
            @abstractmethod
            def step(self): pass
        Plain()
        Conventional()
        """,
    )

    assert callees(graph, "main") == [
        "abc.abstractmethod",
        "main.Conventional.__init__",
        "main.Plain.__init__",
    ]
    assert callees(graph, "main.Plain.run") == ["main.Plain.step"]
    assert callees(graph, "main.Lone.run") == ["main.Lone.step"]


def test_a_protocol_class_is_refused_only_by_its_own_initializer(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from typing import Protocol
        class Sized(Protocol):
            def __init__(self): pass
        class Proto(Protocol):
            def run(self): pass
        class Box(Sized):
            def __init__(self): pass
        Sized()
        Proto().run()
        Box()
        """,
    )

    assert callees(graph, "main") == ["main.Box.__init__", "main.Sized.__init__"]


def test_an_abstract_class_with_another_allocator_is_instantiated(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Items(list, ABC):
            @abstractmethod
            def f(self): pass
            def __init__(self): pass
        Items()
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod", "main.Items.__init__"]


def test_abstractness_follows_the_final_binding(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Rebound(ABC):
            @abstractmethod
            def f(self): pass
            f = 1
            def __init__(self): pass
        class Base(ABC):
            @abstractmethod
            def f(self): pass
        Base.f = lambda self: None
        class Child(Base):
            def __init__(self): pass
        Rebound()
        Child()
        """,
    )

    assert callees(graph, "main") == [
        "abc.abstractmethod",
        "main.Child.__init__",
        "main.Rebound.__init__",
    ]


def test_an_abstract_method_of_a_mixin_without_abcmeta_does_not_count(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Mix:
            @abstractmethod
            def f(self): pass
        class C(Mix, ABC):
            def __init__(self): pass
        C()
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod", "main.C.__init__"]


def test_abstract_class_and_static_methods_count(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Maker(ABC):
            @classmethod
            @abstractmethod
            def make(cls): pass
            def __init__(self): pass
        class Helper(ABC):
            @staticmethod
            @abstractmethod
            def help(): pass
            def __init__(self): pass
        Maker()
        Helper()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "<builtin>.staticmethod",
        "abc.abstractmethod",
    ]


def test_a_metaclass_with_a_concrete_alternative_keeps_the_class_concrete(
    tmp_path,
):
    graph = main_graph(tmp_path, METACLASS_ALTERNATIVES)

    assert "main.C.__init__" in callees(graph, "main")


METACLASS_ALTERNATIVES = """
import abc, sys
class PlainMeta(type): pass
class AbstractMeta(abc.ABCMeta): pass
class Meta(PlainMeta if sys.argv else AbstractMeta): pass
class C(metaclass=Meta):
    @abc.abstractmethod
    def f(self): pass
    def __init__(self): pass
C()
"""


def test_object_new_makes_no_instance_of_an_abstract_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Base(abc.ABC):
            def __new__(cls):
                return super().__new__(cls)
            def __init__(self): pass
            @abc.abstractmethod
            def run(self): pass
        Base()
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod", "main.Base.__new__"]


def test_an_alternative_concrete_hierarchy_makes_an_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Abstract(abc.ABC):
            @abc.abstractmethod
            def run(self): pass
        class Concrete(abc.ABC):
            def run(self): pass
        def pick(flag):
            return Abstract if flag else Concrete
        class Thing(pick(True)):
            def __init__(self): pass
        Thing()
        """,
    )

    assert callees(graph, "main") == [
        "abc.abstractmethod",
        "main.Thing.__init__",
        "main.pick",
    ]


def test_a_mixin_concrete_method_resolves_the_abstract_one(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import abc
        class Base(abc.ABC):
            @abc.abstractmethod
            def run(self): pass
        class Mixin:
            def run(self): pass
        class Thing(Mixin, Base):
            def __init__(self): pass
        Thing()
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod", "main.Thing.__init__"]


def test_an_annotation_without_a_value_binds_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Annotated(ABC):
            @abstractmethod
            def f(self): pass
            f: object
            def __init__(self): pass
        class Nested(ABC):
            @abstractmethod
            def f(self): pass
            def helper(self):
                return (f := 1)
            def __init__(self): pass
        Annotated()
        Nested()
        """,
    )

    assert callees(graph, "main") == ["abc.abstractmethod"]


def test_a_body_that_uses_its_namespace_keeps_its_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import abstractmethod
        class C:
            @abstractmethod
            def f(self): pass
            def run(self):
                self.f()
            snapshot = locals()
        """,
    )

    assert callees(graph, "main.C.run") == ["main.C.f"]


def test_a_body_that_writes_its_namespace_may_replace_an_inherited_method(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class A(ABC):
            @abstractmethod
            def f(self): pass
        class C(A):
            locals()["f"] = lambda self: None
            def __init__(self): pass
        class D(C):
            def __init__(self): pass
        C()
        D()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.locals",
        "abc.abstractmethod",
        "main.C.__init__",
        "main.D.__init__",
    ]


def test_a_protocol_body_that_uses_its_namespace_may_define_init(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from typing import Protocol
        class P(Protocol):
            locals()["__init__"] = lambda self: None
            def run(self): pass
        class Q(P, Protocol):
            def go(self): pass
        class Plain(Protocol):
            def stop(self): pass
        P().run()
        Q().go()
        Plain().stop()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.locals",
        "main.P.run",
        "main.Q.go",
    ]


def test_an_abstract_method_below_a_namespace_body_still_refuses(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class C(ABC):
            snapshot = locals()
        class D(C):
            @abstractmethod
            def g(self): pass
            def __init__(self): pass
        D()
        """,
    )

    assert "main.D.__init__" not in callees(graph, "main")


def test_an_assignment_expression_in_a_default_under_a_compound_statement(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class C(ABC):
            @abstractmethod
            def f(self): pass
            if True:
                def helper(value=(f := 1)): pass
            def __init__(self): pass
        C()
        """,
    )

    assert "main.C.__init__" in callees(graph, "main")
