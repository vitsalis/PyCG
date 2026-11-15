"""Metaclasses: a class is an instance of its metaclass."""

import textwrap

import pytest
from programs import analysed, callees, main_graph


def graph_of(tmp_path, source):
    return main_graph(tmp_path, textwrap.dedent(source))


def metaclasses(tmp_path, source):
    """The names of the metaclasses of each class of the program."""
    generator = analysed(tmp_path, {"main.py": textwrap.dedent(source)})
    analysis = generator.program.analysis
    return {
        cls.name: sorted(meta.name for meta in cls.metaclasses)
        for cls in analysis.classes
    }


def test_a_class_is_an_instance_of_its_metaclass_and_its_subclasses_too(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def create(cls):
                return cls()
            def run(cls):
                cls.hook()
        class Model(metaclass=Meta):
            def __init__(self): pass
            @staticmethod
            def hook(): pass
        class Child(Model):
            def __init__(self): pass
        """,
    )

    # The receiver of a method that no analysed code calls gets the classes
    # whose metaclass it is; a metaclass has no instance that is not a class.
    assert callees(graph, "main.Meta.create") == [
        "main.Child.__init__",
        "main.Model.__init__",
    ]
    assert callees(graph, "main.Meta.run") == ["main.Model.hook"]


def test_super_in_a_metaclass_method_binds_the_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Base(type):
            def describe(cls):
                cls.hook()
        class Meta(Base):
            def describe(cls):
                super().describe()
        class Model(metaclass=Meta):
            @staticmethod
            def hook(): pass
        class Other(metaclass=Base):
            @staticmethod
            def hook(): pass
        Meta.describe(Model)
        """,
    )

    assert callees(graph, "main.Meta.describe") == [
        "<builtin>.super",
        "main.Base.describe",
    ]
    # Called with Model only: Other is an instance of Base, not of Meta.
    assert callees(graph, "main.Base.describe") == ["main.Model.hook"]


def test_the_metaclass_is_the_most_derived_candidate(tmp_path):
    found = metaclasses(
        tmp_path,
        """
        import abc
        class BaseMeta(type): pass
        class SubMeta(BaseMeta): pass
        class A(metaclass=BaseMeta): pass
        class B(A, metaclass=SubMeta): pass
        class C(B, metaclass=BaseMeta): pass
        class D(A): pass
        class Plain: pass
        class Abstract(abc.ABC): pass
        """,
    )

    assert found["main.A"] == ["main.BaseMeta"]
    assert found["main.B"] == ["main.SubMeta"]
    # A base's metaclass that derives from the keyword's wins.
    assert found["main.C"] == ["main.SubMeta"]
    assert found["main.D"] == ["main.BaseMeta"]
    assert found["main.Plain"] == ["<builtin>.type"]
    assert found["main.Abstract"] == ["abc.ABCMeta"]
    assert found["main.SubMeta"] == ["<builtin>.type"]


def test_a_metaclass_named_through_a_variable_waits_for_its_value(tmp_path):
    found = metaclasses(
        tmp_path,
        """
        class Meta(type): pass
        def pick():
            return Meta
        class Model(metaclass=pick()): pass
        class Made(metaclass=lambda name, bases, namespace: None): pass
        def unknown(): pass
        class Odd(metaclass=unknown()): pass
        """,
    )

    assert found["main.Model"] == ["main.Meta"]
    # A metaclass that is no class makes the class with `type`, and so
    # does one that the analysis does not know.
    assert found["main.Made"] == ["<builtin>.type"]
    assert found["main.Odd"] == ["<builtin>.type"]


# Rule 1: loads through a class


def test_a_load_that_the_class_does_not_answer_finds_the_metaclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def create(cls):
                return cls()
            def describe(cls): pass
        class Model(metaclass=Meta):
            def __init__(self): pass
            def describe(self): pass
        class Plain:
            pass
        Model.create()
        Model().describe()
        def plain():
            Plain.mro()
            Plain.__name__.lower()
        """,
    )

    # The class's own attribute comes first; the metaclass's is bound to
    # the class.
    assert callees(graph, "main") == [
        "main.Meta.create",
        "main.Model.__init__",
        "main.Model.describe",
    ]
    assert callees(graph, "main.Meta.create") == ["main.Model.__init__"]
    # The metaclass of a class without one is `type`, as the stubs give it.
    assert callees(graph, "main.plain") == ["<builtin>.str.lower", "<builtin>.type.mro"]


# Rule 2: the metaclass's __getattr__


def test_a_load_that_neither_class_answers_calls_the_metaclass_getattr(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def handler(): pass
        class Meta(type):
            def __getattr__(cls, name):
                cls.known()
                return handler
            def known(cls): pass
        class Api(metaclass=Meta):
            @classmethod
            def present(cls): pass
        def use():
            Api.anything()
            Api.present()
            Api.known()
        """,
    )

    # From the scope of the load, bound to the class; not for a name that
    # the class or the metaclass defines.
    assert callees(graph, "main.use") == [
        "main.Api.present",
        "main.Meta.__getattr__",
        "main.Meta.known",
        "main.handler",
    ]
    assert callees(graph, "main.Meta.__getattr__") == ["main.Meta.known"]


# Rule 3: special methods of a class object


def test_special_methods_of_a_class_are_those_of_its_metaclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def f(): pass
        class Meta(type):
            def __len__(cls):
                return 0
            def __iter__(cls):
                cls.members()
                return iter([f])
            def __add__(cls, other):
                pass
            def __repr__(cls):
                return ""
            def __contains__(cls, item):
                return False
            def __enter__(cls):
                return cls
            def __exit__(cls, *exc):
                pass
        class Colors(metaclass=Meta):
            @classmethod
            def members(cls): pass
        class Plain:
            def __len__(self):
                return 0
        def use():
            len(Colors)
            for color in Colors:
                color()
            Colors + 1
            repr(Colors)
            1 in Colors
            with Colors:
                pass
            len(Plain)
        """,
    )

    # Plain's own __len__ is for its instances, not for the class.
    assert callees(graph, "main.use") == [
        "<builtin>.len",
        "<builtin>.repr",
        "main.Meta.__add__",
        "main.Meta.__contains__",
        "main.Meta.__enter__",
        "main.Meta.__exit__",
        "main.Meta.__iter__",
        "main.Meta.__len__",
        "main.Meta.__repr__",
        "main.f",
    ]
    assert callees(graph, "main.Meta.__iter__") == [
        "<builtin>.iter",
        "main.Colors.members",
    ]


# One construct each: the class C is the receiver, and Meta, its type,
# defines the special method that the construct calls.
CLASS_RECEIVER = """
import asyncio
class Meta(type):
    {methods}
class C(metaclass=Meta):
    def __bool__(self): return False
    @classmethod
    def run(cls): pass
class D(metaclass=Meta): pass
async def use():
    {use}
"""


@pytest.mark.parametrize(
    "methods, use, expected",
    [
        pytest.param(
            "def __bool__(cls): return True",
            "if C: pass",
            ["main.Meta.__bool__"],
            id="truth",
        ),
        pytest.param(
            "def __len__(cls): return 0", "not C", ["main.Meta.__len__"], id="len"
        ),
        # C's own __bool__ is for its instances.
        pytest.param("pass", "if C: pass", [], id="own method"),
        pytest.param(
            "def __str__(cls): return 'c'",
            '"%s" % C',
            ["main.Meta.__str__"],
            id="percent",
        ),
        pytest.param(
            "def __await__(cls): yield",
            "await C",
            ["main.Meta.__await__"],
            id="await",
        ),
        # sleep gives its result at the call; awaiting a class whose
        # metaclass defines no __await__ keeps it, as for an instance.
        pytest.param(
            "pass",
            "(await asyncio.sleep(0, C)).run()",
            ["asyncio.sleep", "main.C.run"],
            id="awaited itself",
        ),
        pytest.param(
            "def __hash__(cls): return 0",
            "{C: 1}",
            ["main.Meta.__hash__"],
            id="hash",
        ),
        pytest.param(
            "def __hash__(cls): return 0\n    def __eq__(cls, other): return True",
            "{D: 1}[C]",
            ["main.Meta.__eq__", "main.Meta.__hash__"],
            id="key comparison",
        ),
        pytest.param(
            "def __iter__(cls): return cls\n    def __next__(cls): raise StopIteration",
            "for _ in C: pass",
            ["main.Meta.__iter__", "main.Meta.__next__"],
            id="iterator",
        ),
        pytest.param(
            "def __getitem__(cls, index): raise IndexError",
            "for _ in C: pass",
            ["main.Meta.__getitem__"],
            id="sequence",
        ),
        pytest.param(
            "def __setitem__(cls, key, value): pass",
            "C[1] = 2",
            ["main.Meta.__setitem__"],
            id="setitem",
        ),
        pytest.param(
            "def __delitem__(cls, key): pass",
            "del C[1]",
            ["main.Meta.__delitem__"],
            id="delitem",
        ),
    ],
)
def test_special_methods_of_a_class_receiver_are_its_metaclass(
    tmp_path, methods, use, expected
):
    graph = main_graph(tmp_path, CLASS_RECEIVER.format(methods=methods, use=use))

    assert callees(graph, "main.use") == expected


def test_a_class_statement_sets_the_name_of_a_class_through_its_metaclass(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def __set_name__(cls, owner, name):
                pass
        class C(metaclass=Meta): pass
        class Owner:
            held = C
        """,
    )

    assert "main.Meta.__set_name__" in callees(graph, "main")


def test_membership_in_a_class_is_decided_by_its_metaclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Needle:
            def __eq__(self, other): return False
        class Answers(type):
            def __contains__(cls, value): return False
        class Iterates(type):
            def __iter__(cls): return iter([1])
        class Asked(metaclass=Answers): pass
        class Searched(metaclass=Iterates): pass
        def asked():
            Needle() in Asked
        def searched():
            Needle() in Searched
        """,
    )

    # The metaclass's __contains__ answers alone, as for an instance.
    assert callees(graph, "main.asked") == ["main.Answers.__contains__"]
    # Without it, Python iterates over the class and compares the value.
    assert callees(graph, "main.searched") == [
        "main.Iterates.__iter__",
        "main.Needle.__eq__",
    ]


# Rule 4: subscripts of a class


def test_a_subscript_of_a_class_calls_the_metaclass_getitem_first(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        class Meta(type):
            def __getitem__(cls, key):
                return f
        class Palette(metaclass=Meta):
            def __class_getitem__(cls, key):
                return g
        class Plain:
            def __class_getitem__(cls, key):
                return g
        def use():
            Palette["red"]()
        def plain():
            Plain["red"]()
        """,
    )

    assert callees(graph, "main.use") == ["main.Meta.__getitem__", "main.f"]
    # Without a metaclass's `__getitem__`, `__class_getitem__`.
    assert callees(graph, "main.plain") == ["main.Plain.__class_getitem__", "main.g"]


# Rule 6: a class statement is a call of its metaclass


def test_a_class_statement_calls_new_and_init_of_its_metaclass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def __new__(mcs, name, bases, namespace, **options):
                namespace["hook"]()
                return super().__new__(mcs, name, bases, namespace)
            def __init__(cls, name, bases, namespace, **options):
                super().__init__(name, bases, namespace)
                cls.ready()
        class Model(metaclass=Meta, flag=True):
            @staticmethod
            def hook(): pass
            @classmethod
            def ready(cls): pass
        def declare():
            class Plain:
                pass
        """,
    )

    # From the scope of the statement, with the name, the bases, the
    # namespace and the keywords; `__init__` runs on the class that
    # `type.__new__` makes.
    assert callees(graph, "main") == [
        "<builtin>.classmethod",
        "<builtin>.staticmethod",
        "main.Meta.__init__",
        "main.Meta.__new__",
    ]
    assert callees(graph, "main.Meta.__new__") == [
        "<builtin>.super",
        "<builtin>.type.__new__",
        "main.Model.hook",
    ]
    assert callees(graph, "main.Meta.__init__") == [
        "<builtin>.super",
        "<builtin>.type.__init__",
        "main.Model.ready",
    ]
    # A class without a metaclass of the analysed code calls nothing.
    assert callees(graph, "main.declare") == []


def test_a_metaclass_without_new_initialises_the_class_of_the_statement(
    tmp_path,
):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def __init__(cls, name, bases, namespace):
                cls.ready()
        class First(metaclass=Meta):
            @classmethod
            def ready(cls): pass
        def declare():
            class Second(First):
                @classmethod
                def ready(cls): pass
        """,
    )

    assert callees(graph, "main") == ["<builtin>.classmethod", "main.Meta.__init__"]
    assert callees(graph, "main.declare") == [
        "<builtin>.classmethod",
        "main.Meta.__init__",
    ]
    assert callees(graph, "main.Meta.__init__") == [
        "main.First.ready",
        "main.declare.Second.ready",
    ]


# Rule 7: __prepare__


def test_a_class_statement_first_calls_the_metaclass_prepare(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def make(): return {}
        class Meta(type):
            @classmethod
            def __prepare__(mcs, name, bases, **options):
                mcs.check()
                return make()
            @classmethod
            def check(mcs): pass
        class Model(metaclass=Meta, flag=True):
            pass
        """,
    )

    assert callees(graph, "main") == ["<builtin>.classmethod", "main.Meta.__prepare__"]
    assert callees(graph, "main.Meta.__prepare__") == ["main.Meta.check", "main.make"]
