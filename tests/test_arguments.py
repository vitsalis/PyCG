import pytest
from programs import callees, main_graph

FUNCTIONS = "def f(): pass\ndef g(): pass\ndef h(): pass\n"


def graph_of(tmp_path, source):
    return main_graph(tmp_path, FUNCTIONS + source)


def test_extra_positional_arguments_go_to_args(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def first(a, *args):
    args[0]()
def every(*args):
    for arg in args:
        arg()
first(f, g, h)
every(f, g)
""",
    )

    assert callees(graph, "main.first") == ["main.g"]
    assert callees(graph, "main.every") == ["main.f", "main.g"]


def test_extra_keyword_arguments_go_to_kwargs(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def run(name, **options):
    options["callback"]()
    for key in options:
        pass
run("x", callback=f, other=g)
""",
    )

    assert callees(graph, "main.run") == ["main.f"]


def test_unpacked_positional_arguments_keep_their_positions(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def pair(a, b, c=None):
    b()
def rest(a, *more):
    more[0]()
pair(*[f, g])
pair(f, *(g,))
rest(*(f, g, h))
""",
    )

    assert callees(graph, "main.pair") == ["main.g"]
    assert callees(graph, "main.rest") == ["main.g"]


def test_unpacked_argument_of_unknown_length(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def pair(a, b):
    a()
    b()
def spread(values):
    pair(f, *values)
spread([g])
""",
    )

    assert callees(graph, "main.pair") == ["main.f", "main.g"]


def test_unpacked_keyword_arguments(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def named(a=None, b=None, **rest):
    b()
    rest["c"]()
named(**{"b": f, "c": g})
""",
    )

    assert callees(graph, "main.named") == ["main.f", "main.g"]


def test_forwarding_wrapper_keeps_arguments_apart(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def target(first, second, *, key=None):
    second()
    key()
def forward(*args, **kwargs):
    return target(*args, **kwargs)
forward(f, g, key=h)
""",
    )

    assert callees(graph, "main.target") == ["main.g", "main.h"]


def test_functions_unpacked_into_a_builtin_that_applies_them_are_called(tmp_path):
    graph = graph_of(
        tmp_path,
        """
import ext
map(*[f], [1])
sorted([1], **{"key": g})
ext.run(*[h], **{"done": h})
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.map",
        "<builtin>.sorted",
        "ext.run",
        "main.f",
        "main.g",
    ]


def test_args_unpacked_into_shifted_positions_terminate(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def shift(*args):
    args[0]()
    shift(g, *args)
def back(a, b, *args):
    back(*args)
shift(f)
back(f, g, h)
""",
    )

    assert callees(graph, "main.shift") == ["main.f", "main.g", "main.shift"]


def test_a_method_with_only_args_gets_its_receiver_first(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        class Base:
            def run(*args):
                args[0].step()
                args[1]()
            def step(self): pass
        class Child(Base):
            def step(self): pass
        Base().run(target)
        Child()
        """,
    )

    assert callees(graph, "main.Base.run") == ["main.Base.step", "main.target"]


def test_a_forwarding_wrapper_used_as_a_method_passes_the_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def forward(f):
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper
        class Base:
            @forward
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


def test_a_method_with_only_args_gets_an_outside_receiver(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def run(*args):
                args[0].helper()
            def helper(self): pass
        """,
    )

    assert callees(graph, "main.C.run") == ["main.C.helper"]


def test_an_unpacked_argument_is_iterated_once_per_call_site(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Item:
    action = staticmethod(g)
    def __iter__(self):
        return self
    def __next__(self):
        return self
class Source:
    __iter__ = Item
def set_action(x):
    x.action = f
def invoke(x):
    x.action()
def dispatch(fn, src):
    fn(*src)
dispatch(set_action, Source())
dispatch(invoke, Source())
""",
    )

    assert callees(graph, "main.invoke") == ["main.f", "main.g"]


def test_unpacking_a_value_without_objects_still_calls(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def take(*args, **kwargs): pass
take(*None)
take(**None)
""",
    )

    assert callees(graph, "main") == ["main.take"]


def test_metaclass_new_gets_the_class_statement_in_its_varargs(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class Base:
    @classmethod
    def hook(cls): pass
class Meta(type):
    def __new__(mcs, *args):
        args[1][0].hook()
        return super().__new__(mcs, *args)
class A(Base, metaclass=Meta): pass
""",
    )

    assert "main.Base.hook" in callees(graph, "main.Meta.__new__")


def test_unpacked_arguments_past_the_parameters_bind_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def take(a):
    a()
take(f, g, *(h,))
""",
    )

    assert callees(graph, "main.take") == ["main.f"]


def test_an_argument_after_an_unpacked_one_without_objects_binds_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def take(*args):
    args[0]()
take(*(f,), 1.5)
""",
    )

    assert callees(graph, "main.take") == ["main.f"]


def test_unpacking_a_list_binds_only_its_positions(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def take(a):
    a()
items = [f]
items["a"]
take(*items)
""",
    )

    assert callees(graph, "main.take") == ["main.f"]


def test_unpacking_a_dict_binds_only_its_string_keys(tmp_path):
    graph = graph_of(
        tmp_path,
        """
def take(a):
    a()
take(**{1: f, "a": g})
""",
    )

    assert callees(graph, "main.take") == ["main.g"]


def test_a_dict_unpacked_after_the_keywords_were_bound_gives_its_keys(tmp_path):
    graph = graph_of(
        tmp_path,
        """
class A:
    def run(self): pass
    def stop(self): pass
def take(**kwargs):
    for name in kwargs:
        getattr(A(), name)()
def forward(mapping):
    take(**mapping)
def i1(x): return x
def i2(x): return i1(x)
def i3(x): return i2(x)
forward({"run": 1})
forward(i3(i3({"stop": 1})))
""",
    )

    assert callees(graph, "main.take") == [
        "<builtin>.getattr",
        "main.A.run",
        "main.A.stop",
    ]


@pytest.mark.parametrize(
    "position, first_callees, far_callees",
    [
        pytest.param(
            "9345883071009581737",
            ["main.f", "main.first"],
            ["main.far", "main.g"],
            id="above 2 to the 63",
        ),
        pytest.param(
            "9223372036854775808",
            ["main.f", "main.first"],
            ["main.far", "main.g"],
            id="2 to the 63",
        ),
        pytest.param(
            "18446744073709551617",
            ["main.f", "main.first"],
            ["main.far", "main.g"],
            id="2 to the 64 and 1",
        ),
        pytest.param(
            "-9223372036854775809",
            ["main.f", "main.first", "main.g"],
            ["main.f", "main.far", "main.g"],
            id="below minus 2 to the 63",
        ),
    ],
)
def test_an_unpacked_position_beyond_a_machine_integer_binds_to_args(
    tmp_path, position, first_callees, far_callees
):
    graph = graph_of(
        tmp_path,
        f"""
def first(*args):
    return args[0]
def far(*args):
    return args[{position}]
items = [f]
items[{position}] = g
def call_first():
    first(*items)()
def call_far():
    far(*items)()
""",
    )

    assert callees(graph, "main.call_first") == first_callees
    assert callees(graph, "main.call_far") == far_callees
