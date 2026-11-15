"""Call backs: the builtins that apply a function (`map`, `sorted` with a
key) call it, from the scope that called the builtin (micro-benchmark/
README.md, "Callbacks"); other outside code calls nothing that the analysed
code passes it.
"""

import pytest
from programs import analysed, call_graph, callees, main_graph


def test_callables_passed_to_outside_code_are_not_called(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        def f(): pass
        def g(): pass
        class C:
            def m(self):
                self.helper()
            def helper(self): pass
            def __call__(self): pass
        def run():
            ext.register(f)
            ext.schedule(1, callback=C().m)
            ext.watch(C())
            ext.later(lambda: g())
        """,
    )

    assert callees(graph, "main.run") == [
        "ext.later",
        "ext.register",
        "ext.schedule",
        "ext.watch",
    ]


def test_callback_gets_its_defaults_and_no_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def h(): pass
        def handler(event=None, fallback=h):
            fallback()
        list(map(handler, [1]))
        """,
    )

    assert callees(graph, "main.handler") == ["main.h"]


def test_builtins_that_call_their_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def key(x): pass
        def double(x): pass
        sorted([3, 1], key=key)
        list(map(double, [1, 2]))
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.list",
        "<builtin>.map",
        "<builtin>.sorted",
        "main.double",
        "main.key",
    ]


def test_builtins_that_never_call_their_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def __call__(self): pass
        def f(): pass
        print(f, C())
        isinstance(f, C)
        callable(f)
        id(f)
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.callable",
        "<builtin>.id",
        "<builtin>.isinstance",
        "<builtin>.print",
    ]


def test_classes_passed_to_external_code_are_not_instantiated(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class C:
            def __init__(self): pass
        ext.register(C)
        """,
    )

    assert callees(graph, "main") == ["ext.register"]


def test_calls_through_external_names_past_the_bound_call_nothing(tmp_path):
    # add_done_callback is past the two steps that names keep: the call has
    # no named edge, and the function passed to it is not called.
    graph = main_graph(
        tmp_path,
        """
        import ext
        def done(): pass
        def use():
            ext.loop.task.add_done_callback(done)
        """,
    )

    assert callees(graph, "main.use") == []


def test_external_past_the_bound_is_no_base_and_no_callee(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class A(ext.a.b.c):
            def run(self):
                self.helper()
        A().run()
        """,
    )

    assert callees(graph, "main") == ["main.A.run"]
    assert callees(graph, "main.A.run") == []


ADVERSARIAL_EXTERNALS = {
    "base": """
        import unittest
        bases = [unittest.TestCase]
        class C(bases[0]): pass
        bases[0] = C.failureException
        """,
    "handler": """
        import ext
        E = ext.Error
        for _ in range(3):
            try:
                pass
            except E as e:
                E = e.cause.kind
        """,
    "calls": """
        import ext
        x = ext.a
        while x:
            x = x.b().c[0].d
            for y in x:
                x = y.e
            with x as z:
                x = z.f
        """,
}


@pytest.mark.parametrize("program", sorted(ADVERSARIAL_EXTERNALS))
def test_external_names_stay_within_the_bound(tmp_path, program):
    generator = analysed(tmp_path, {"main.py": ADVERSARIAL_EXTERNALS[program]})

    # Every root here (ext, unittest, <builtin>.name) has at most two parts,
    # and a name grows at most two steps past its root.
    for external in generator.program.analysis.externals.values():
        assert external.steps <= 2, external.name
        assert external.name.count(".") + 1 - external.steps <= 2, external.name


def test_callbacks_are_implicit_calls(tmp_path):
    # Outside code makes the calls back: an instance whose __call__ only an
    # external base may define gives no edge to it.
    graph = main_graph(
        tmp_path,
        """
        import lib
        class Task(lib.Future):
            pass
        def use():
            lib.register(Task())
        """,
    )

    assert "lib.Future.__call__" not in callees(graph, "main.use")
    assert "lib.register" in callees(graph, "main.use")


def test_implicit_calls_of_outside_methods_call_nothing(tmp_path):
    # Python calls lib.Registry.__setitem__ and lib.Signal.__add__ without a
    # call expression: no edge to them, and they call nothing.
    graph = main_graph(
        tmp_path,
        """
        import lib
        class Registry(lib.Registry):
            pass
        class Signal(lib.Signal):
            pass
        def handler(): pass
        def listener(): pass
        def use():
            registry = Registry()
            registry["x"] = handler
            Signal() + listener
        """,
    )

    assert callees(graph, "main.use") == [
        "lib.Registry.__init__",
        "lib.Signal.__init__",
    ]


@pytest.mark.parametrize("getter", ["lib.get", "lib.a.b.c"])
def test_an_outside_property_getter_calls_nothing(tmp_path, getter):
    # One property load calls the getter with either instance as its
    # argument; outside code does not call them. lib.a.b.c is past the
    # bound of external names.
    graph = main_graph(
        tmp_path,
        f"""
        import lib
        class C:
            value = property({getter})
            def __call__(self): pass
        class D:
            value = property({getter})
            def __call__(self): pass
        def use(flag):
            obj = C() if flag else D()
            obj.value
        """,
    )

    assert callees(graph, "main.use") == []


# typing.final is analysed here: the model of what it returns replaces its
# body, but it is not outside code.
ANALYSED_MODEL = {"typing.py": "def final(f):\n    return f\n"}


def test_an_analysed_function_with_a_model_keeps_its_edge_as_a_callback(tmp_path):
    # map calls final implicitly: the edge stays, as for any analysed function.
    files = {
        **ANALYSED_MODEL,
        "main.py": "from typing import final\n"
        "def target(): pass\n"
        "list(map(final, [target]))\n",
    }
    graph = call_graph(tmp_path, files)

    assert callees(graph, "main") == [
        "<builtin>.list",
        "<builtin>.map",
        "typing.final",
    ]


@pytest.mark.parametrize("is_analysed", [False, True])
def test_an_analysed_function_with_a_model_is_no_external_callee(tmp_path, is_analysed):
    files = {"main.py": "from typing import final\ndef target(): pass\nfinal(target)\n"}
    if is_analysed:
        files.update(ANALYSED_MODEL)
    generator = analysed(tmp_path, files)

    assert callees(generator.output(), "main") == ["typing.final"]
    assert ("typing.final" in generator.document()["outside"]) is not is_analysed
