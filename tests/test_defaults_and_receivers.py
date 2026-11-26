from programs import call_graph, callees, main_graph


def test_default_flows_only_where_the_call_omits_the_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def h(): pass
        def given(cb=g):
            cb()
        def by_keyword(cb=g):
            cb()
        def omitted(cb=g):
            cb()
        given(h)
        by_keyword(cb=h)
        omitted()
        """,
    )

    assert callees(graph, "main.given") == ["main.h"]
    assert callees(graph, "main.by_keyword") == ["main.h"]
    assert callees(graph, "main.omitted") == ["main.g"]


def test_default_flows_when_unpacking_may_omit_the_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        def g(): pass
        def star(a, cb=g):
            cb()
        def double_star(a, cb=g):
            cb()
        star(*ext.args)
        double_star(1, **ext.kwargs)
        """,
    )

    assert callees(graph, "main.star") == ["ext.args", "main.g"]
    assert callees(graph, "main.double_star") == ["main.g"]


def test_defaults_of_functions_that_no_analysed_code_calls_flow(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def api(cb=g, *, key=g):
            cb()
            key()
        class Service:
            def run(self, cb=g):
                cb()
        """,
    )

    assert callees(graph, "main.api") == ["main.g"]
    assert callees(graph, "main.Service.run") == ["main.g"]


def test_a_function_that_only_calls_itself_still_gets_its_defaults(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): pass
        def fold(items, combine=g):
            combine()
            if items:
                fold(items[1:], combine=combine)
        """,
    )

    assert callees(graph, "main.fold") == ["main.fold", "main.g"]


def test_method_with_a_real_receiver_gets_no_outside_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def handler(self): pass
            def run(self):
                self.handler()
        class Child(Base):
            def handler(self): pass
        Child().run()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Child.handler"]


def test_a_method_that_no_analysed_code_calls_gets_every_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            def step(self): pass
        Child()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.Child.step"]


def test_instances_of_a_subclass_in_another_module_reach_the_method(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "base.py": """
            class Base:
                def run(self):
                    self.step()
                def step(self): pass
            """,
            "child.py": """
            from base import Base
            class Child(Base):
                def step(self): pass
            def make():
                return Child()
            """,
            "main.py": "import child\n",
        },
    )

    assert callees(graph, "base.Base.run") == ["base.Base.step", "child.Child.step"]


def test_a_method_that_analysed_code_calls_keeps_its_real_receivers(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Base:
            def run(self):
                self.step()
            def step(self): pass
        class Child(Base):
            def step(self): pass
        Base().run()
        Child()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step"]


def test_receivers_of_library_classes_are_completed(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Parser:
            def parse(self):
                self.step()
            def step(self):
                self.finish()
            def finish(self): pass
        """,
    )

    assert callees(graph, "main.Parser.parse") == ["main.Parser.step"]
    assert callees(graph, "main.Parser.step") == ["main.Parser.finish"]


def test_completion_reaches_code_behind_completed_receivers(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "lib.py": """
            def g(): pass
            class Plugin:
                def setup(self):
                    self.register(make())
                def register(self, factory, hook=g):
                    factory()
                    hook()
            def make():
                return g
            """,
            "main.py": "import lib\n",
        },
    )

    assert callees(graph, "lib.Plugin.setup") == ["lib.Plugin.register", "lib.make"]
    assert callees(graph, "lib.Plugin.register") == ["lib.g"]


def test_identity_decorator_keeps_the_functions_it_decorates_apart(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        TABLE = []
        def register(f):
            TABLE.append(f)
            return f
        @register
        def first(): pass
        @register
        def second(): pass
        def use():
            first()
        """,
    )

    assert callees(graph, "main.use") == ["main.first"]


def test_a_choice_between_parameters_gives_each_call_its_own_arguments(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        UNSET = object()
        def first_set(first, second):
            return second if first is UNSET else first
        def either(a, b):
            return a or b
        def fallback(a):
            return a if a else make()
        def make():
            return g
        def f(): pass
        def g(): pass
        def h(): pass
        def k(): pass
        def use():
            first_set(UNSET, f)()
            either(h, None)()
            fallback(None)()
        first_set(k, UNSET)
        either(k, None)
        """,
    )

    assert callees(graph, "main.use") == [
        "main.either",
        "main.f",
        "main.fallback",
        "main.first_set",
        "main.g",
        "main.h",
    ]
    assert callees(graph, "main.fallback") == ["main.make"]


def test_decorator_that_may_return_another_value_merges_its_results(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def default(): pass
        def register(f):
            if f is None:
                f = default
            return f
        @register
        def first(): pass
        @register
        def second(): pass
        def use():
            first()
        """,
    )

    assert callees(graph, "main.use") == ["main.default", "main.first", "main.second"]


def test_decorator_that_rebinds_its_parameter_to_itself_returns_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def register(f):
            f = f or None
            return f
        @register
        def first(): pass
        @register
        def second(): pass
        def use():
            first()
        """,
    )

    assert callees(graph, "main.use") == ["main.first"]


def test_methods_that_return_self_keep_their_receivers_apart(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Fluent:
            def configure(self):
                return self
        class A(Fluent):
            def run(self): pass
        class B(Fluent):
            def run(self): pass
        def use():
            A().configure().run()
        B().configure().run()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.A.run",
        "main.Fluent.configure",
    ]


def test_returned_parameter_with_a_default_and_by_keyword(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def h(): pass
        def pick(value=h):
            return value
        def use():
            pick(f)()
            pick(value=g)()
            pick()()
        def other():
            pick(f)()
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g", "main.h", "main.pick"]
    assert callees(graph, "main.other") == ["main.f", "main.pick"]


def test_parameter_rebound_by_a_nested_nonlocal_merges_results(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def keep(f):
            def reset():
                nonlocal f
                f = None
            return f
        @keep
        def first(): pass
        @keep
        def second(): pass
        def use():
            first()
        """,
    )

    assert callees(graph, "main.use") == ["main.first", "main.second"]


def test_nonlocal_rebinding_from_a_nested_class_method_merges(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def a(): pass
        def b(): pass
        def choose(f):
            class C:
                f = None
                def reset(self):
                    nonlocal f
                    f = b
            C().reset()
            return f
        choose(a)()
        """,
    )

    assert callees(graph, "main") == ["main.a", "main.b", "main.choose"]


ARGS_FUNCTIONS = """
def f(): pass
def g(): pass
def h(): pass
def k(): pass
"""


def test_returned_element_of_args_gives_each_call_its_own_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def first(*args):
    return args[0]
def second(a, *args):
    return args[1]
def use():
    first(f, g)()
    second(None, k, h)()
def other():
    first(g)()
    second(None, f, g)
""",
    )

    assert callees(graph, "main.use") == [
        "main.f",
        "main.first",
        "main.h",
        "main.second",
    ]
    assert callees(graph, "main.other") == ["main.first", "main.g", "main.second"]


def test_returned_element_of_args_in_a_method_skips_the_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
class C:
    def pick(self, *args):
        return args[0]
    @classmethod
    def make(cls, *args):
        return args[0]
    @staticmethod
    def plain(*args):
        return args[0]
def use():
    C().pick(f)()
    C.make(g)()
    C().plain(h)()
C().pick(k)
C.make(k)
C.plain(k)
""",
    )

    assert callees(graph, "main.use") == [
        "main.C.make",
        "main.C.pick",
        "main.C.plain",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_method_that_returns_args_0_returns_its_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Fluent:
    def configure(*args):
        return args[0]
class A(Fluent):
    def run(self): pass
class B(Fluent):
    def run(self): pass
def use():
    A().configure().run()
B().configure().run()
""",
    )

    assert callees(graph, "main.use") == ["main.A.run", "main.Fluent.configure"]


def test_new_that_returns_args_0_keeps_the_calls_of_its_classes_apart(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Base:
    def __new__(cls, *args):
        return args[0]
class A(Base): pass
class B(Base): pass
class X:
    def m(self): pass
class Y:
    def m(self): pass
def use():
    A(X()).m()
B(Y()).m()
""",
    )

    assert callees(graph, "main.use") == ["main.Base.__new__", "main.X.m"]
    assert "main.X.m" not in callees(graph, "main")


def test_returned_element_of_args_with_too_few_arguments_gives_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def second(*args):
    return args[1]
def use():
    second(f)()
second(g, h)
""",
    )

    assert callees(graph, "main.use") == ["main.second"]


def test_unpacked_arguments_give_the_call_only_what_it_unpacks(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def first(*args):
    return args[0]
def second(*args):
    return args[1]
def use():
    first(*[f, g])()
    items = []
    items.append(h)
    first(*items)()
    second(*[g], h)()
def other():
    # After a positional argument, the list's positions are not kept.
    second(f, *[g])()
first(k)
second(k, k)
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.list.append",
        "main.f",
        "main.first",
        "main.h",
        "main.second",
    ]
    assert callees(graph, "main.other") == ["main.g", "main.second"]


def test_returned_element_of_args_from_one_of_several_returns(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def make():
    return h
def pick(flag, *args):
    if flag:
        return args[0]
    return make()
def use():
    pick(True, f)()
pick(True, g)
""",
    )

    assert callees(graph, "main.use") == ["main.f", "main.h", "main.pick"]


def test_args_passed_on_still_gives_each_call_its_own_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def log(*items):
    pass
def keep(items):
    pass
def first(*args):
    log(*args)
    keep(args)
    return args[0]
def use():
    first(f)()
first(g)
""",
    )

    assert callees(graph, "main.use") == ["main.f", "main.first"]


def test_rebound_args_merges_the_results_of_every_call(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def rest(*args):
    args = args[1:]
    return args[0]
def nested(*args):
    def reset():
        nonlocal args
        args = (h,)
    return args[0]
def use():
    rest(None, f)()
    nested(f)()
rest(None, g)
nested(g)
""",
    )

    assert callees(graph, "main.use") == [
        "main.f",
        "main.g",
        "main.h",
        "main.nested",
        "main.rest",
    ]


def test_limit_a_negative_index_or_kwargs_merges_the_results_of_every_call(tmp_path):
    graph = main_graph(
        tmp_path,
        ARGS_FUNCTIONS
        + """
def last(*args):
    return args[-1]
def option(**kwargs):
    return kwargs["key"]
def use():
    last(f)()
    option(key=h)()
last(g)
option(key=k)
""",
    )

    assert callees(graph, "main.use") == [
        "main.f",
        "main.g",
        "main.h",
        "main.k",
        "main.last",
        "main.option",
    ]


def test_limit_an_inner_choice_passes_a_parameter_the_outer_discards(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def first(): pass
def fallback(): pass
def choose(candidate, default):
    enabled = False
    return (candidate and enabled) or default
choose(first, fallback)()
""",
    )

    assert {"main.fallback", "main.first"} <= set(callees(graph, "main"))


def test_a_function_that_reads_its_locals_returns_each_call_its_argument(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def ident(value):
            locals()
            return value
        def first():
            ident(f)()
        def second():
            ident(g)()
        """,
    )

    assert callees(graph, "main.first") == ["main.f", "main.ident"]
    assert callees(graph, "main.second") == ["main.g", "main.ident"]
