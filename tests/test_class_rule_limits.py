"""Limits of the class rules (Codex reviews of the class rules). Each rule
removes an edge only where Python certainly does without it; in the cases
below it keeps the edge although Python makes no such call. Each test pins
the kept edge, so that the edge is not "fixed" by a rule that would also
remove real calls."""

from programs import callees, main_graph


def test_limit_a_store_on_a_class_counts_as_a_new_binding(tmp_path):
    # N2: `C.f = C.f` keeps f abstract; the analysis does not read the
    # stored value.
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
    # N3: A obliges f; the selected Mix.f is abstract, so Python refuses C.
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
    # N5: the final binding is the setter; the property stays abstract.
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
    # N6: `__init__ = Protocol.__init__` keeps the refusing initializer.
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
    # N7: object.__new__(cls) refuses the abstract list subclass.
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
    # N8: EnumMeta.__call__ returns the existing member without __init__.
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
    # N10: `run = classmethod(Base.run)` passes the class, not an instance.
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
    # Python refuses the store of a name that is no slot.
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
    # Codex review, round 3, finding 6: `locals()` is only read, so Python
    # refuses C and `run` has no receiver. The analysis does not tell a read
    # of the namespace from a write: the body may bind any name.
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
