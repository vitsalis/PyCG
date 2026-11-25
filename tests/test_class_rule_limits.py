from programs import callees, main_graph


def test_limit_a_store_on_a_class_counts_as_a_new_binding(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class Abstract(ABC):
            @abstractmethod
            def f(self): pass
            def __init__(self): pass
        Abstract.f = Abstract.f
        Abstract()
        """,
    )

    assert "main.Abstract.__init__" in callees(graph, "main")


def test_limit_an_abstract_name_selected_from_a_mixin_without_abcmeta(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class A(ABC):
            @abstractmethod
            def f(self): pass
        class Mix:
            @abstractmethod
            def f(self): pass
        class C(Mix, A):
            def __init__(self): pass
        C()
        """,
    )

    assert "main.C.__init__" in callees(graph, "main")


def test_limit_an_abstract_property_with_a_concrete_setter(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class C(ABC):
            @property
            @abstractmethod
            def f(self): pass
            @f.setter
            def f(self, value): pass
            def __init__(self): pass
        C()
        """,
    )

    assert "main.C.__init__" in callees(graph, "main")


def test_limit_a_protocol_that_binds_protocols_own_initializer(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from typing import Protocol
        class P(Protocol):
            __init__ = Protocol.__init__
            def run(self): pass
        P().run()
        """,
    )

    assert "main.P.run" in callees(graph, "main")


def test_limit_a_builtin_base_with_an_explicit_object_new(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class C(list, ABC):
            @abstractmethod
            def f(self): pass
            def __new__(cls):
                return object.__new__(cls)
            def __init__(self): pass
        C()
        """,
    )

    assert "main.C.__init__" in callees(graph, "main")


def test_limit_an_enum_whose_metaclass_derives_from_abcmeta(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from enum import Enum, EnumMeta
        from abc import ABCMeta, abstractmethod
        class Meta(EnumMeta, ABCMeta): pass
        class C(Enum, metaclass=Meta):
            X = 1
            @abstractmethod
            def f(self): pass
            def __init__(self, value): pass
        def use():
            C(1)
        use()
        """,
    )

    assert "main.C.__init__" in callees(graph, "main.use")


def test_limit_a_class_method_alias_keeps_the_instances(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            run = classmethod(Base.run)
            def step(self): pass
        """,
    )

    assert "main.Child.step" in callees(graph, "main.Base.run")


def test_limit_stores_are_not_restricted_by_slots(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def work(): pass
        class C:
            __slots__ = ()
        c = C()
        c.x = work
        c.x()
        """,
    )

    assert "main.work" in callees(graph, "main")


def test_limit_a_body_that_only_reads_its_namespace_is_not_refused(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        from abc import ABC, abstractmethod
        class C(ABC):
            @abstractmethod
            def f(self): pass
            def run(self):
                self.f()
            snapshot = locals()
        """,
    )

    assert callees(graph, "main.C.run") == ["main.C.f"]


def test_limit_a_new_that_allocates_through_a_builtin_base_is_not_decided(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base(str):
            def __new__(cls, value):
                return super().__new__(cls, value)
        class Loud(Base):
            def __getattr__(self, name): pass
        class Quiet(Base):
            def speak(self): pass
        Loud("a")
        Quiet("b").speak()
        """,
    )

    assert "main.Loud.__getattr__" in callees(graph, "main")


def test_limit_a_store_of_class_outside_new_is_not_seen(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def __new__(cls):
                instance = super().__new__(cls)
                retag(instance)
                return instance
            def speak(self): pass
        class Other:
            def speak(self): pass
        def retag(obj):
            obj.__class__ = Other
        Base().speak()
        """,
    )

    assert callees(graph, "main") == ["main.Base.__new__", "main.Base.speak"]
