from programs import callees, main_graph


def test_three_argument_type_calls_the_metaclass_of_the_bases(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Meta(type):
            def __new__(mcs, name, bases, namespace):
                return super().__new__(mcs, name, bases, namespace)
            def __init__(cls, name, bases, namespace):
                pass
        class Base(metaclass=Meta):
            def __init_subclass__(cls):
                pass
        class Plain:
            def __init_subclass__(cls):
                pass
        def build(name):
            type(name, (Base,), {})
            type(name, (Plain,), {})
        build("C")
        """,
    )

    assert callees(graph, "main.build") == [
        "<builtin>.type",
        "main.Meta.__init__",
        "main.Meta.__new__",
    ]


def test_several_bases_give_no_calls(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def __init_subclass__(cls):
                super().__init_subclass__()
        class B:
            def __init_subclass__(cls): pass
        class FirstMeta(type):
            def __init__(cls, name, bases, namespace): pass
        class SecondMeta(FirstMeta):
            def __init__(cls, name, bases, namespace): pass
        class First(metaclass=FirstMeta): pass
        class Second(metaclass=SecondMeta): pass
        def make():
            type("C", (A, B), {})
        def meta():
            type("D", (First, Second), {})
        make()
        meta()
        """,
    )

    assert callees(graph, "main.make") == ["<builtin>.type"]
    assert callees(graph, "main.meta") == ["<builtin>.type"]


def test_limit_keywords_and_unpacked_arguments_make_no_calls(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def fallback(): pass
        def supplied(): pass
        class Base:
            def __init_subclass__(cls, *, hook=fallback):
                hook()
        def make():
            type("C", (Base,), {}, hook=supplied)
        def unpacked():
            type(*("C", (Base,), {}))
        def partly():
            type("C", (Base,), *())
        make()
        unpacked()
        partly()
        """,
    )

    assert callees(graph, "main.make") == ["<builtin>.type"]
    assert callees(graph, "main.unpacked") == ["<builtin>.type"]
    assert callees(graph, "main.partly") == ["<builtin>.type"]


def test_four_arguments_make_no_calls(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Meta(type):
            def __init__(cls, name, bases, namespace): pass
        class Base(metaclass=Meta):
            def __init_subclass__(cls): pass
        def make():
            type("C", (Base,), {}, None)
        make()
        """,
    )

    assert callees(graph, "main.make") == ["<builtin>.type"]


def test_limit_the_hook_of_the_new_class_is_not_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def wrong(): pass
        def real(): pass
        class Base:
            hook = staticmethod(wrong)
            def __init_subclass__(cls):
                cls.hook()
        class Existing(Base):
            hook = staticmethod(real)
        def make():
            type("Dynamic", (Base,), {"hook": staticmethod(real)})
        make()
        """,
    )

    assert callees(graph, "main.make") == ["<builtin>.staticmethod", "<builtin>.type"]
    assert callees(graph, "main.Base.__init_subclass__") == ["main.real"]
