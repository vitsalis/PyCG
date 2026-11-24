import textwrap

from programs import analysed, callees, main_graph


def test_super_without_arguments_follows_the_mro_of_the_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def run(self): pass
        class B(A):
            def run(self):
                super().run()
        class C(A):
            def run(self):
                super().run()
        class D(B, C):
            pass
        D().run()
        """,
    )

    assert callees(graph, "main.B.run") == ["<builtin>.super", "main.C.run"]
    assert callees(graph, "main.C.run") == ["<builtin>.super", "main.A.run"]


def test_super_with_explicit_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def __init__(self): pass
        class B(A):
            def __init__(self):
                super(B, self).__init__()
        B()
        """,
    )

    assert callees(graph, "main.B.__init__") == ["<builtin>.super", "main.A.__init__"]


def test_super_in_a_class_method(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            @classmethod
            def create(cls):
                return cls()
        class B(A):
            def __init__(self): pass
            @classmethod
            def create(cls):
                return super().create()
        B.create()
        """,
    )

    assert callees(graph, "main.B.create") == ["<builtin>.super", "main.A.create"]
    assert callees(graph, "main.A.create") == ["main.B.__init__"]


def test_super_reaches_an_external_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Failure(Exception):
            def __init__(self, message):
                super().__init__(message)
        Failure("x")
        """,
    )

    assert callees(graph, "main.Failure.__init__") == [
        "<builtin>.Exception.__init__",
        "<builtin>.super",
    ]


def test_super_reads_a_property_of_a_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class A:
            @property
            def handler(self):
                return f
        class B(A):
            @property
            def handler(self):
                return super().handler
        B().handler()
        """,
    )

    assert callees(graph, "main.B.handler") == ["<builtin>.super", "main.A.handler"]
    assert "main.f" in callees(graph, "main")


def test_super_with_alternative_hierarchies(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import sys
        class A:
            def run(self): pass
        class B:
            def run(self): pass
        class C(A if sys.argv else B):
            def run(self):
                super().run()
        C().run()
        """,
    )

    assert callees(graph, "main.C.run") == [
        "<builtin>.super",
        "main.A.run",
        "main.B.run",
    ]


def super_values(tmp_path, source, name):
    generator = analysed(tmp_path, {"main.py": textwrap.dedent(source)})
    values = generator.output_points_to().get(name, [])
    return [value for value in values if value.startswith("super(")]


def test_two_argument_super_pairs_the_class_only_with_an_accepted_receiver(
    tmp_path,
):
    source = """
    class Base:
        def run(self): pass
    class Child(Base):
        def run(self): pass
    class Other:
        def run(self): pass
    def pick(x):
        s = super(Base, x)
    for x in (Base(), Child(), Other(), Base, Child, Other):
        pick(x)
    """

    assert super_values(tmp_path, source, "main.pick.s") == [
        "super(main.Base, main.Base)",
        "super(main.Base, main.Base@main:10:10)",
        "super(main.Base, main.Child)",
        "super(main.Base, main.Child@main:10:18)",
    ]


def test_two_argument_super_accepts_a_class_whose_metaclass_derives_from_it(
    tmp_path,
):
    source = """
    class Meta(type):
        def describe(cls): pass
    class Model(metaclass=Meta):
        pass
    class Plain:
        pass
    def describe(cls):
        s = super(Meta, cls)
    describe(Model)
    describe(Plain)
    """

    assert super_values(tmp_path, source, "main.describe.s") == [
        "super(main.Meta, main.Model)"
    ]


def test_two_argument_super_waits_for_a_base_that_arrives_late(tmp_path):
    source = """
    class Base:
        def run(self): pass
    def base():
        return Base
    class Late(base()):
        def run(self):
            s = super(Base, self)
    Late().run()
    """

    assert super_values(tmp_path, source, "main.Late.run.s") == [
        "super(main.Base, main.Late@main:9:0)"
    ]


def test_two_argument_super_with_an_outside_receiver_gives_nothing(tmp_path):
    source = """
    import ext
    class Base:
        def run(self): pass
    def pick(x):
        s = super(Base, x)
    pick(ext.make())
    pick("text")
    """

    assert super_values(tmp_path, source, "main.pick.s") == []


def test_super_without_arguments_keeps_every_receiver(tmp_path):
    source = """
    class Base:
        def run(self):
            s = super()
    class Other:
        pass
    Base.run(Other())
    """

    assert super_values(tmp_path, source, "main.Base.run.s") == [
        "super(main.Base, main.Other@main:7:9)"
    ]
