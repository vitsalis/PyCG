import textwrap

from programs import callees, main_graph

METHODS = ("inside", "after", "other", "more")
CLASSES = "".join(
    f"class {name}{base}:\n"
    + "".join(f"    def {method}(self): pass\n" for method in METHODS)
    for name, base in (("A", ""), ("Sub", "(A)"), ("B", ""), ("Other", ""))
)


def graph_of(tmp_path, source):
    return main_graph(tmp_path, CLASSES + textwrap.dedent(source))


def classes_called(graph, caller, method):
    suffix = f".{method}"
    return sorted(
        callee.removeprefix("main.").removesuffix(suffix)
        for callee in callees(graph, caller)
        if callee.startswith("main.") and callee.endswith(suffix)
    )


def test_the_branch_reads_the_instances_of_the_class_and_its_subclasses(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            if isinstance(x, A):
                x.inside()
            x.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]


def test_the_value_does_not_leave_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            if isinstance(x, A):
                x.inside()
            x.after()
            for _ in range(2):
                if isinstance(x, B):
                    x.more()
                    continue
                x.other()
        def loop(x):
            while True:
                if isinstance(x, A):
                    x.inside()
                    break
            x.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "more") == ["B"]
    assert classes_called(graph, "main.loop", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "after") == []
    assert classes_called(graph, "main.use", "other") == []
    assert classes_called(graph, "main.loop", "after") == []


def test_what_the_name_holds_stays_in_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x=Other()):
            if isinstance(x, A):
                x.inside()
            x.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "after") == ["Other"]


def test_elif_and_else_branches(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            if isinstance(x, A):
                x.inside()
            elif isinstance(x, B):
                x.other()
            else:
                x.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "other") == ["B"]
    assert classes_called(graph, "main.use", "after") == []


def test_not_and_or(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def negated(x):
            if not isinstance(x, A):
                x.inside()
            else:
                x.after()
        def both(x, flag):
            if isinstance(x, A) and flag:
                x.inside()
            if isinstance(x, B) or flag:
                x.after()
        def neither(x):
            if not (isinstance(x, B) or isinstance(x, Other)):
                x.inside()
            if not isinstance(x, B) and not isinstance(x, Other):
                pass
            else:
                x.after()
        def operands(x):
            isinstance(x, A) and x.inside()
            not isinstance(x, B) or x.after()
            x.other() if isinstance(x, Other) else x.more()
        """,
    )

    assert classes_called(graph, "main.negated", "inside") == []
    assert classes_called(graph, "main.negated", "after") == ["A", "Sub"]
    assert classes_called(graph, "main.both", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.both", "after") == []
    assert classes_called(graph, "main.neither", "inside") == []
    assert classes_called(graph, "main.neither", "after") == []
    assert classes_called(graph, "main.operands", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.operands", "after") == ["B"]
    assert classes_called(graph, "main.operands", "other") == ["Other"]
    assert classes_called(graph, "main.operands", "more") == []


def test_after_a_guard_the_rest_of_the_block_is_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def returns(x):
            if not isinstance(x, A):
                return
            x.inside()
        def raises(x):
            if not isinstance(x, A):
                raise TypeError(x)
            x.inside()
        def loops(xs):
            for x in xs:
                if not isinstance(x, A):
                    continue
                x.inside()
            for x in xs:
                if not isinstance(x, B):
                    break
                x.other()
            x.after()
        def asserts(x):
            assert isinstance(x, A)
            x.inside()
        def block(x, flag):
            if flag:
                if not isinstance(x, A):
                    return
                x.inside()
            x.after()
        def waits(x):
            while not isinstance(x, A):
                x = x.parent
            x.inside()
        """,
    )

    for function in ("returns", "raises", "loops", "asserts", "block", "waits"):
        assert classes_called(graph, f"main.{function}", "inside") == ["A", "Sub"], (
            function
        )
    assert classes_called(graph, "main.loops", "other") == ["B"]
    assert classes_called(graph, "main.loops", "after") == []
    assert classes_called(graph, "main.block", "after") == []


def test_limit_an_assert_narrows_as_if_it_always_runs(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(name):
            name.strip()
            assert isinstance(name, bytes)
            name.lower()
            name.split()
        def caller():
            use("Content-Length")
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.bytes.lower",
        "<builtin>.bytes.split",
        "<builtin>.isinstance",
        "<builtin>.str.strip",
    ]


def test_nested_functions_read_the_variable_and_comprehensions_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            if isinstance(x, A):
                def inner():
                    x.after()
                inner()
                [x.inside() for _ in range(1)]
                list(x.other() for _ in range(1))
        """,
    )

    assert classes_called(graph, "main.use.inner", "after") == []
    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "other") == []


def test_a_rebinding_in_the_branch_ends_the_test(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def rebinds(x):
            if isinstance(x, A):
                x = Other()
                x.inside()
        def loops(x):
            while isinstance(x, A):
                x.inside()
                x = Other()
                x.after()
        def walrus(x):
            if isinstance(x, A) and (x := Other()):
                x.inside()
        def joins(x, flag):
            if isinstance(x, A):
                if flag:
                    x = Other()
                x.inside()
        """,
    )

    assert classes_called(graph, "main.rebinds", "inside") == ["Other"]
    assert classes_called(graph, "main.loops", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.loops", "after") == ["Other"]
    assert classes_called(graph, "main.walrus", "inside") == ["Other"]
    assert classes_called(graph, "main.joins", "inside") == ["Other"]


def test_a_tuple_of_classes_gives_each_of_them(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        KINDS = (B, Other)
        def display(x):
            if isinstance(x, (A, (B,))):
                x.inside()
        def named(x):
            if isinstance(x, KINDS):
                x.inside()
        """,
    )

    assert classes_called(graph, "main.display", "inside") == ["A", "B", "Sub"]
    assert classes_called(graph, "main.named", "inside") == ["B", "Other"]


def test_a_class_of_the_stubs_gives_a_typed_value(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import collections
        def decode(content):
            if isinstance(content, bytes):
                content = content.decode()
            return content
        def items(d):
            if not isinstance(d, dict):
                raise TypeError(d)
            return d.items()
        def ordered(d):
            if isinstance(d, collections.OrderedDict):
                d.move_to_end(1)
        """,
    )

    assert "<builtin>.bytes.decode" in callees(graph, "main.decode")
    assert "<builtin>.dict.items" in callees(graph, "main.items")
    assert "collections.OrderedDict.move_to_end" in callees(graph, "main.ordered")


def test_issubclass_gives_the_classes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def make(kind):
            if issubclass(kind, A):
                kind().inside()
        """,
    )

    assert classes_called(graph, "main.make", "inside") == ["A", "Sub"]


def test_a_class_that_the_analysis_does_not_know_gives_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        def outside(x):
            if isinstance(x, ext.Thing):
                x.inside()
        def unknown(x, kind):
            if isinstance(x, kind):
                x.inside()
        def kept(x=Other(), kind=None):
            if isinstance(x, kind):
                x.inside()
        """,
    )

    assert [c for c in callees(graph, "main.outside") if "Thing" in c] == []
    assert classes_called(graph, "main.unknown", "inside") == []
    assert classes_called(graph, "main.kept", "inside") == ["Other"]


def test_parameters_with_and_without_an_annotation(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def annotated(x: Other):
            if isinstance(x, A):
                x.inside()
            x.after()
        def bare(x):
            if isinstance(x, A):
                x.inside()
        """,
    )

    assert classes_called(graph, "main.annotated", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.annotated", "after") == ["Other"]
    assert classes_called(graph, "main.bare", "inside") == ["A", "Sub"]


def test_a_name_that_holds_nothing_gets_the_instances(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use():
            x = 0
            if isinstance(x, A):
                x.inside()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]


def test_only_a_local_name_tested_by_the_builtins_counts(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def attribute(self):
            if isinstance(self.x, A):
                self.x.inside()
        def rebound(x, isinstance):
            if isinstance(x, A):
                x.inside()
        def helper(x):
            if is_a(x):
                x.inside()
        def is_a(x):
            return isinstance(x, A)
        def computed(x):
            if isinstance(x, type(A())):
                x.inside()
        def global_name():
            global G
            if isinstance(G, A):
                G.inside()
        """,
    )

    for function in ("attribute", "rebound", "helper", "computed", "global_name"):
        assert classes_called(graph, f"main.{function}", "inside") == [], function


def test_module_code_and_class_bodies_keep_the_test_in_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def make():
            return Other()
        def read():
            module_value.after()
        module_value = make()
        if isinstance(module_value, A):
            module_value.inside()
        class K:
            value = make()
            if not isinstance(value, B):
                raise TypeError(value)
            value.other()
        K.value.more()
        """,
    )

    assert classes_called(graph, "main", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.read", "after") == ["Other"]
    assert classes_called(graph, "main", "other") == ["B"]
    assert classes_called(graph, "main", "more") == ["Other"]


def test_a_handler_in_the_branch_keeps_the_test(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x):
            if isinstance(x, A):
                try:
                    x.inside()
                except ValueError:
                    x.other()
                    x = Other()
                x.after()
        """,
    )

    assert classes_called(graph, "main.use", "other") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "after") == ["Other"]


def test_values_that_cannot_be_an_instance_do_not_reach_the_branch(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x=Other(), y=Sub()):
            if isinstance(x, A):
                x.inside()
            if isinstance(y, A):
                y.other()
        def strings(x="s", y=Other()):
            if isinstance(x, bytes):
                x.decode()
            if isinstance(y, str):
                y.inside()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.use", "other") == ["A", "Sub"]
    assert "<builtin>.bytes.decode" in callees(graph, "main.strings")
    assert "<builtin>.str.decode" not in callees(graph, "main.strings")
    assert classes_called(graph, "main.strings", "inside") == []


def test_where_the_test_fails_certain_instances_do_not_reach(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(x=A(), y=Sub(), z=Other()):
            for v in (x, y, z):
                if isinstance(v, A):
                    pass
                else:
                    v.inside()
                if not isinstance(v, (B, Other)):
                    v.after()
        def text(value=b"b", other="s"):
            for v in (value, other):
                if not isinstance(v, bytes):
                    v.upper()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["Other"]
    assert classes_called(graph, "main.use", "after") == ["A", "Sub"]
    assert "<builtin>.str.upper" in callees(graph, "main.text")
    assert "<builtin>.bytes.upper" not in callees(graph, "main.text")


def test_a_class_whose_bases_may_differ_passes_both_branches(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import random
        Base = A if random.random() else Other
        class M(Base):
            pass
        def use(x=M()):
            if isinstance(x, A):
                x.inside()
            else:
                x.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["A", "Other", "Sub"]
    assert classes_called(graph, "main.use", "after") == ["A", "Other"]


def test_outside_bases_decide_against_outside_classes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import ext
        class Mine(dict):
            def inside(self): pass
            def after(self): pass
        class Unknown(ext.Base):
            def inside(self): pass
            def after(self): pass
        def use(x=Mine(), y=Other(), z=Unknown()):
            for v in (x, y, z):
                if isinstance(v, dict):
                    v.inside()
                else:
                    v.after()
        """,
    )

    assert classes_called(graph, "main.use", "inside") == ["Mine", "Unknown"]
    assert classes_called(graph, "main.use", "after") == ["Other", "Unknown"]


def test_values_and_classes_that_the_analysis_does_not_know_pass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import abc
        import collections.abc
        import ext
        class Abstract(abc.ABC):
            def inside(self): pass
        def unknown_value(x=ext.value):
            if isinstance(x, A):
                x.inside()
            else:
                x.after()
        def unknown_class(x=Other()):
            if isinstance(x, ext.Thing):
                x.inside()
        def nothing(x=Other(), kind=None):
            if isinstance(x, kind):
                x.inside()
            else:
                x.after()
        def partly(x=Other(), kind=None):
            if not isinstance(x, (B, kind)):
                x.inside()
            if isinstance(x, (B, kind)):
                x.after()
        def abstract(x=Other(), y=Abstract()):
            for v in (x, y):
                if isinstance(v, Abstract):
                    v.inside()
                if isinstance(v, collections.abc.Sized):
                    v.after()
                else:
                    v.other()
        """,
    )

    assert "ext.value.after" in callees(graph, "main.unknown_value")
    assert classes_called(graph, "main.unknown_class", "inside") == ["Other"]
    assert classes_called(graph, "main.nothing", "inside") == ["Other"]
    assert classes_called(graph, "main.nothing", "after") == ["Other"]
    assert classes_called(graph, "main.partly", "inside") == ["Other"]
    assert classes_called(graph, "main.partly", "after") == ["B", "Other"]
    assert classes_called(graph, "main.abstract", "inside") == ["Abstract", "Other"]
    assert classes_called(graph, "main.abstract", "after") == ["Other"]
    assert classes_called(graph, "main.abstract", "other") == ["Other"]


def test_issubclass_filters_the_classes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def make(kind=Other, other=Sub):
            for k in (kind, other):
                if issubclass(k, A):
                    k().inside()
                else:
                    k().after()
        """,
    )

    assert classes_called(graph, "main.make", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.make", "after") == ["Other"]


def test_object_is_the_root_of_every_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def instances(x=A(), y="s"):
            for v in (x, y):
                if isinstance(v, object):
                    v.inside()
                else:
                    v.after()
                if not isinstance(v, (B, object)):
                    v.other()
        def classes(k=A):
            if issubclass(k, object):
                k().inside()
            else:
                k().after()
        """,
    )

    assert classes_called(graph, "main.instances", "inside") == ["A"]
    assert classes_called(graph, "main.instances", "after") == []
    assert classes_called(graph, "main.instances", "other") == []
    assert classes_called(graph, "main.classes", "inside") == ["A"]
    assert classes_called(graph, "main.classes", "after") == []


def test_type_and_bool_as_tested_classes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Meta(type):
            def inside(cls): pass
        def classes(k=A, m=Meta):
            for c in (k, m):
                if issubclass(c, type):
                    c.inside(c)
        def numbers(n=1):
            if isinstance(n, bool):
                n.bit_count()
            else:
                n.bit_length()
        """,
    )

    assert classes_called(graph, "main.classes", "inside") == ["Meta"]
    assert "<builtin>.int.bit_length" in callees(graph, "main.numbers")


def test_classes_that_may_answer_otherwise_let_every_value_pass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from collections.abc import Iterable, Sequence
        from typing import Generic, Protocol, TypeVar, runtime_checkable
        T = TypeVar("T")
        class Loops:
            def __iter__(self): return iter(())
            def inside(self): pass
            def after(self): pass
            def other(self): pass
            def more(self): pass
        class Registered:
            def inside(self): pass
            def after(self): pass
            def other(self): pass
            def more(self): pass
        Sequence.register(Registered)
        @runtime_checkable
        class Runs(Protocol):
            def inside(self): ...
        class Box(Generic[T]):
            def inside(self): pass
        def structural(x=Loops()):
            if isinstance(x, Iterable):
                x.inside()
        def registered(x=Registered()):
            if isinstance(x, Sequence):
                x.inside()
            else:
                x.after()
        def protocol(x=Other()):
            if isinstance(x, Runs):
                x.other()
        def generic(x=Other()):
            if isinstance(x, Box):
                x.more()
        """,
    )

    assert classes_called(graph, "main.structural", "inside") == ["Loops"]
    assert classes_called(graph, "main.registered", "inside") == ["Registered"]
    assert classes_called(graph, "main.protocol", "other") == ["Other"]
    assert classes_called(graph, "main.generic", "more") == []


def test_enums_let_every_value_pass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import enum
        def ints(x=Other()):
            if isinstance(x, enum.IntEnum):
                x.inside()
        def flags(x=Other()):
            if isinstance(x, enum.IntFlag):
                x.after()
        def strs(x=Other()):
            if isinstance(x, enum.StrEnum):
                x.other()
        """,
    )

    assert classes_called(graph, "main.ints", "inside") == ["Other"]
    assert classes_called(graph, "main.flags", "after") == ["Other"]
    assert classes_called(graph, "main.strs", "other") == ["Other"]


def test_stub_classes_with_plain_instance_checks_still_filter(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import json
        import uuid
        class Mine(json.JSONDecodeError):
            def inside(self): pass
        def errors(x=Other(), y=Mine("m", "d", 0)):
            for v in (x, y):
                if isinstance(v, ValueError):
                    v.inside()
        def ids(x=Other()):
            if isinstance(x, uuid.UUID):
                x.inside()
        """,
    )

    assert classes_called(graph, "main.errors", "inside") == ["Mine"]
    assert classes_called(graph, "main.ids", "inside") == []


def test_tuples_that_are_empty_or_not_known(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def empty(x=Other()):
            if not isinstance(x, ()):
                x.inside()
            if isinstance(x, ()):
                x.after()
        def unknown(x=Other(), kinds=None):
            if not isinstance(x, (kinds, kinds)):
                x.other()
        def target():
            pass
        def function(x=target):
            if isinstance(x, ()):
                x()
        def classes(x=target, kinds=()):
            if isinstance(x, kinds):
                x()
        def any_class(x=target):
            if isinstance(x, A):
                x()
        """,
    )

    assert classes_called(graph, "main.empty", "inside") == ["Other"]
    assert classes_called(graph, "main.empty", "after") == []
    assert classes_called(graph, "main.unknown", "other") == ["Other"]
    assert "main.target" not in callees(graph, "main.function")
    assert "main.target" not in callees(graph, "main.classes")
    assert "main.target" in callees(graph, "main.any_class")


def test_a_list_display_is_not_a_tuple(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if isinstance(arg, tuple):
                value, width = arg
                value.inside()
            else:
                value, width = arg
                value.after()
        parse([A(), 1])
        parse((B(), 1))
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["B"]
    assert classes_called(graph, "main.parse", "after") == ["A"]


def test_a_generator_is_not_a_tuple(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def made():
            yield A()
        async def made_async():
            yield Sub()
        def parse(arg):
            if isinstance(arg, tuple):
                for value in arg:
                    value.inside()
        async def parse_async(arg):
            if isinstance(arg, tuple):
                async for value in arg:
                    value.inside()
            elif isinstance(arg, list):
                async for value in arg:
                    value.after()
        parse(made())
        parse((B(),))
        parse_async(made_async())
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["B"]
    assert classes_called(graph, "main.parse_async", "inside") == []
    assert classes_called(graph, "main.parse_async", "after") == []


def test_a_coroutine_is_not_a_tuple(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        async def run():
            return A()
        def parse(arg):
            if isinstance(arg, tuple):
                arg.close()
            else:
                arg.send(None)
        parse(run())
        """,
    )

    found = callees(graph, "main.parse")
    assert not any(callee.endswith(".close") for callee in found)
    assert any(callee.endswith(".send") for callee in found)


def test_comprehensions_are_of_their_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if isinstance(arg, tuple):
                for value in arg:
                    value.inside()
            if isinstance(arg, (set, dict)):
                for value in arg:
                    value.after()
        parse([A() for _ in range(1)])
        parse(B() for _ in range(1))
        parse({Sub(): 1 for _ in range(1)})
        parse((Other(),))
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["Other"]
    assert classes_called(graph, "main.parse", "after") == ["Sub"]


def test_builtin_constructors_make_their_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if isinstance(arg, tuple):
                for value in arg:
                    value.inside()
            if isinstance(arg, list):
                for value in arg:
                    value.after()
        parse(list([A()]))
        parse(tuple([B()]))
        parse(dict([(Sub(), 1)]))
        parse(frozenset([Other()]))
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["B"]
    assert classes_called(graph, "main.parse", "after") == ["A"]


def test_slices_copies_pairs_and_rest_keep_the_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if isinstance(arg, tuple):
                for value in arg:
                    value.inside()
        parse([A()][0:])
        parse([Sub()].copy())
        parse((B(),)[0:])
        def pairs(mapping):
            for pair in mapping.items():
                if isinstance(pair, list):
                    pair[0].after()
                else:
                    pair[0].more()
        pairs({B(): 1})
        def rest(arg):
            first, *others = arg
            if isinstance(others, tuple):
                others[0].other()
        rest((A(), B()))
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["B"]
    assert classes_called(graph, "main.pairs", "after") == []
    assert classes_called(graph, "main.pairs", "more") == ["B"]
    assert classes_called(graph, "main.rest", "other") == []


def test_star_args_is_a_tuple_and_star_kwargs_a_dict(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def star(*args, **kwargs):
            if isinstance(args, list):
                args[0].inside()
            if isinstance(args, tuple):
                args[0].after()
            if isinstance(kwargs, tuple):
                kwargs["k"].other()
            if isinstance(kwargs, dict):
                kwargs["k"].more()
        star(A(), k=B())
        """,
    )

    assert classes_called(graph, "main.star", "inside") == []
    assert classes_called(graph, "main.star", "after") == ["A"]
    assert classes_called(graph, "main.star", "other") == []
    assert classes_called(graph, "main.star", "more") == ["B"]


def test_where_the_test_fails_a_container_of_the_class_does_not_pass(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if not isinstance(arg, list):
                arg[0].inside()
            if not isinstance(arg, object):
                arg[0].after()
        parse([A()])
        parse((B(),))
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["B"]
    assert classes_called(graph, "main.parse", "after") == []


def test_a_base_of_the_class_passes_the_container(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from collections.abc import Sequence
        def made():
            yield Other()
        def parse(arg):
            if isinstance(arg, (list, tuple)):
                for value in arg:
                    value.inside()
            if isinstance(arg, object):
                for value in arg:
                    value.after()
            if not isinstance(arg, Sequence):
                for value in arg:
                    value.other()
        parse([A()])
        parse((B(),))
        parse({Sub(): 1})
        parse(made())
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["A", "B"]
    assert classes_called(graph, "main.parse", "after") == ["A", "B", "Other", "Sub"]
    assert classes_called(graph, "main.parse", "other") == ["A", "B", "Other", "Sub"]


def test_a_container_of_an_annotation_stands_for_any_value_of_its_type(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def declared(arg: list[A]):
            if isinstance(arg, tuple):
                arg[0].inside()
        def written(arg: list[A] = [B()]):
            if isinstance(arg, tuple):
                arg[0].after()
        """,
    )

    assert classes_called(graph, "main.declared", "inside") == ["A", "Sub"]
    assert classes_called(graph, "main.written", "after") == ["A", "Sub"]


def test_a_subclass_of_a_builtin_container_is_tested_by_its_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Items(list):
            def inside(self): pass
            def after(self): pass
        def parse(arg):
            if isinstance(arg, tuple):
                arg.inside()
            if isinstance(arg, list):
                arg.after()
        parse(Items())
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == []
    assert classes_called(graph, "main.parse", "after") == ["Items"]


def test_an_iterator_of_a_container_is_not_the_container(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def run():
            items = [A()]
            it = iter(items)
            if not isinstance(it, list):
                next(it).inside()
            if not isinstance(items, list):
                items[0].after()
            for value in iter((B(),)):
                value.other()
        def parse(arg):
            if isinstance(arg, (list, tuple, dict)):
                for value in arg:
                    value.inside()
            if isinstance(arg, object):
                for value in arg:
                    value.after()
        parse(iter([Sub()]))
        parse(iter(iter({Other(): 1})))
        """,
    )

    assert classes_called(graph, "main.run", "inside") == ["A"]
    assert classes_called(graph, "main.run", "after") == []
    assert classes_called(graph, "main.run", "other") == ["B"]
    assert classes_called(graph, "main.parse", "inside") == []
    assert classes_called(graph, "main.parse", "after") == ["Other", "Sub"]


def test_what_a_declared_container_makes_is_not_exact(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Pairs(dict):
            def items(self):
                return [[k, self[k]] for k in self]
        class Items(list):
            def __getitem__(self, index):
                return tuple(self)
        def sliced(x: list):
            x.append(A())
            y = x[:]
            if not isinstance(y, list):
                y[0].inside()
        def added(x: list):
            x.append(A())
            y = x + []
            if not isinstance(y, list):
                y[0].after()
        def repeated(x: list):
            x.append(A())
            y = x * 2
            if not isinstance(y, list):
                y[0].other()
        def pairs(d: dict):
            d[A()] = 0
            for pair in d.items():
                if isinstance(pair, list):
                    pair[0].more()
        sliced(Items())
        added(Items())
        repeated(Items())
        pairs(Pairs())
        """,
    )

    assert classes_called(graph, "main.sliced", "inside") == ["A"]
    assert classes_called(graph, "main.added", "after") == ["A"]
    assert classes_called(graph, "main.repeated", "other") == ["A"]
    assert classes_called(graph, "main.pairs", "more") == ["A"]


def test_an_operator_on_containers_is_not_exact(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def parse(arg):
            if isinstance(arg, tuple):
                for value in arg:
                    value.inside()
        parse([A()] + [A()])
        parse([B()] * 2)
        """,
    )

    assert classes_called(graph, "main.parse", "inside") == ["A", "B"]


def test_a_class_attribute_is_not_exact(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from enum import Enum
        class E(Enum):
            A = [Other()]
            def __iter__(self):
                return iter(self.value)
        def make():
            return [Sub()]
        class F(Enum):
            B = make()
        def members():
            x = E.A
            if not isinstance(x, list):
                for value in x:
                    value.inside()
            y = F.B
            if not isinstance(y, list):
                for value in y:
                    value.after()
        def body():
            class C:
                KINDS = [B()]
                if isinstance(KINDS, list):
                    KINDS[0].other()
                if not isinstance(KINDS, list):
                    KINDS[0].more()
        """,
    )

    assert classes_called(graph, "main.members", "inside") == ["Other"]
    assert classes_called(graph, "main.members", "after") == ["Sub"]
    assert classes_called(graph, "main.body", "other") == ["B"]
    assert classes_called(graph, "main.body", "more") == []


def test_limit_what_a_stub_type_variable_gives_keeps_the_argument_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from copy import deepcopy
        from functools import reduce
        def folded():
            x = reduce(lambda acc, _: list(acc), [0], (A(),))
            if isinstance(x, list):
                x[0].inside()
        def copied():
            xs = [B()]
            x = deepcopy(xs, {id(xs): (B(),)})
            if isinstance(x, tuple):
                x[0].after()
        """,
    )

    assert classes_called(graph, "main.folded", "inside") == []
    assert classes_called(graph, "main.copied", "after") == []


def test_the_class_of_an_inexact_container_is_not_known(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from enum import Enum
        class E(Enum):
            A = [Other()]
            def __iter__(self):
                return iter(self.value)
        def member():
            x = E.A
            y = x.__class__(x)
            if not isinstance(y, list):
                for value in y:
                    value.inside()
        def member_class():
            k = E.A.__class__
            if not issubclass(k, list):
                k([])
        def tested(x: list):
            v = [Sub()]
            if not isinstance(v, x.__class__):
                v[0].after()
        def exact():
            x = [B()]
            y = x.__class__(x)
            if not isinstance(y, list):
                y[0].other()
        """,
    )

    assert classes_called(graph, "main.member", "inside") == ["Other"]
    assert "<builtin>.list" in callees(graph, "main.member_class")
    assert classes_called(graph, "main.tested", "after") == ["Sub"]
    assert classes_called(graph, "main.exact", "other") == []


def test_a_generator_or_coroutine_class_attribute_is_not_exact(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from enum import Enum
        class Mark:
            pass
        def made():
            yield Other()
        async def run():
            return Other()
        class E(Mark, Enum):
            A = made()
            B = run()
            def __iter__(self):
                return self.value
        def members():
            x = E.A
            if isinstance(x, Mark):
                for value in x:
                    value.inside()
            y = E.B
            if isinstance(y, Mark):
                y.close()
        def body():
            class C:
                G = made()
                if isinstance(G, tuple):
                    for value in G:
                        value.after()
        """,
    )

    assert classes_called(graph, "main.members", "inside") == ["Other"]
    assert any(callee.endswith(".close") for callee in callees(graph, "main.members"))
    assert classes_called(graph, "main.body", "after") == []


def test_a_constant_class_attribute_keeps_its_value_but_not_its_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from enum import Enum
        class Mark:
            pass
        class E(str, Mark, Enum):
            A = "inside"
        def member():
            x = E.A
            if isinstance(x, Mark):
                getattr(A(), x)()
        def body():
            class C:
                N = "after"
                if not isinstance(N, str):
                    getattr(B(), N)()
        """,
    )

    assert classes_called(graph, "main.member", "inside") == ["A"]
    assert classes_called(graph, "main.body", "after") == []


def test_a_base_taken_from_a_class_attribute_is_the_builtin_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Holder:
            value = []
        Base = Holder.value.__class__
        class Left(Base):
            pass
        class Right(list):
            def append(self, x):
                pass
        class Both(Left, Right):
            pass
        def run():
            Both().append(0)
        """,
    )

    assert "main.Right.append" in callees(graph, "main.run")


def test_inspect_iscoroutine_tests_the_coroutine_class(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import inspect
        from inspect import iscoroutine
        import inspect as introspection
        async def run():
            return 1
        def through_name(result):
            if iscoroutine(result):
                result.close()
            else:
                result.inside()
        def through_module(result):
            if not inspect.iscoroutine(result):
                result.inside()
        def through_alias(result):
            if introspection.iscoroutine(result):
                result.inside()
        def rebound(result, iscoroutine=bool):
            if iscoroutine(result):
                result.inside()
        for function in (through_name, through_module, through_alias, rebound):
            function(run())
            function(A())
        """,
    )

    assert callees(graph, "main.through_name") == [
        "inspect.iscoroutine",
        "main.A.inside",
        "types.CoroutineType.close",
    ]
    assert classes_called(graph, "main.through_module", "inside") == ["A"]
    assert classes_called(graph, "main.through_alias", "inside") == []
    assert classes_called(graph, "main.rebound", "inside") == ["A"]


def test_a_final_class_of_the_stubs_filters_whatever_its_protocol_bases(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        import types
        def items():
            yield A()
        def parse(arg):
            if isinstance(arg, types.GeneratorType):
                arg.inside()
            else:
                arg.close()
        parse(items())
        parse(A())
        """,
    )

    assert callees(graph, "main.parse") == ["<builtin>.isinstance"]
