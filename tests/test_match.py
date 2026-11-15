"""`match` patterns: a capture binds what its position in the pattern holds
(see *Match patterns* in the design)."""

import textwrap

from programs import callees, main_graph

DEFINITIONS = """
import ext
def f(): pass
def g(): pass
def h(): pass
"""


def graph_of(tmp_path, source):
    return main_graph(tmp_path, DEFINITIONS + textwrap.dedent(source))


def test_a_sequence_pattern_binds_elements_and_the_rest(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def known():
            match (f, g, h):
                case [first, *rest]:
                    rest[0]()
        def positions(value):
            match value:
                case [first, _, last]:
                    first()
                    last()
        def ends():
            match [f, g, h]:
                case [*_, before, last]:
                    before()
        positions([f, ext.middle, h])
        """,
    )

    assert callees(graph, "main.known") == ["main.g"]
    assert callees(graph, "main.positions") == ["main.f", "main.h"]
    assert callees(graph, "main.ends") == ["main.g"]


def test_a_sequence_pattern_reads_a_sequence_by_length_and_index(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from collections.abc import Sequence
        class Pair(Sequence):
            def __getitem__(self, index):
                return (f, g)[index]
            def __len__(self):
                return 2
        def use(value):
            match value:
                case [first, second]:
                    second()
        use(Pair())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Pair.__getitem__",
        "main.Pair.__len__",
        "main.f",
        "main.g",
    ]


def test_a_mapping_pattern_binds_values_and_the_rest(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def values(config):
            match config:
                case {"on_stop": handler}:
                    handler()
        def rest():
            config = {"on_start": f, "on_stop": g}
            match config:
                case {"on_start": handler, **others}:
                    others["on_stop"]()
        values({"on_start": h, "on_stop": f})
        """,
    )

    assert callees(graph, "main.values") == ["main.f"]
    assert callees(graph, "main.rest") == ["main.g"]


def test_a_mapping_pattern_reads_a_mapping_by_length_and_key(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        from collections.abc import Mapping
        class Config(Mapping):
            def __getitem__(self, key):
                return f
            def __iter__(self):
                return iter(["run"])
            def __len__(self):
                return 1
        def use(value):
            match value:
                case {"run": handler}:
                    handler()
        use(Config())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Config.__getitem__",
        "main.Config.__len__",
        "main.f",
    ]


def test_a_class_pattern_binds_attributes(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Command:
            __match_args__ = ("action",)
            def __init__(self, action, fallback):
                self.action = action
                self.fallback = fallback
        class Lazy:
            __match_args__ = ("action",)
            @property
            def action(self):
                return h
        class Sub(Command):
            pass
        def positional():
            match Command(f, g):
                case Command(action, fallback=other):
                    action()
        def keyword():
            match Command(f, g):
                case Command(fallback=other):
                    other()
        def inherited():
            match Sub(f, g):
                case Sub(action):
                    action()
        def computed():
            match Lazy():
                case Lazy(action):
                    action()
        def builtin(value):
            match value:
                case str(text):
                    text.upper()
        builtin("name")
        """,
    )

    assert callees(graph, "main.positional") == ["main.Command.__init__", "main.f"]
    assert callees(graph, "main.keyword") == ["main.Command.__init__", "main.g"]
    assert callees(graph, "main.inherited") == ["main.Command.__init__", "main.f"]
    assert callees(graph, "main.computed") == ["main.Lazy.action", "main.h"]
    # `str(text)` binds the subject itself.
    assert callees(graph, "main.builtin") == ["<builtin>.str.upper"]


def test_a_class_pattern_calls_nothing(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Command:
            def __init__(self):
                pass
        def use(value):
            match value:
                case Command():
                    f()
        """,
    )

    assert callees(graph, "main.use") == ["main.f"]


def test_a_value_pattern_compares_with_eq(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Modes:
            FAST = 1
        class AlwaysEqual:
            def __eq__(self, other):
                return True
        def use():
            match AlwaysEqual():
                case Modes.FAST:
                    f()
        """,
    )

    assert callees(graph, "main.use") == ["main.AlwaysEqual.__eq__", "main.f"]


def test_value_and_literal_patterns_compare_whatever_is_tracked(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        class Falsy:
            def __bool__(self): return False
        class Compared:
            def __eq__(self, other): return Falsy()
        class Holder:
            compared = Compared()
        def literal(subject):
            match subject:
                case 0.5: pass
        def singletons(subject):
            match subject:
                case None: pass
                case True: pass
        def reflected():
            match 0.5:
                case Holder.compared: pass
        literal(Compared())
        singletons(Compared())
        """,
    )

    # `subject == 0.5` runs and its result is tested, though the float has
    # no object; a literal subject runs the value's reflected __eq__.
    compared = ["main.Compared.__eq__", "main.Falsy.__bool__"]
    assert callees(graph, "main.literal") == compared
    assert callees(graph, "main.reflected") == compared
    # None, True and False are compared by identity.
    assert callees(graph, "main.singletons") == []


def test_an_or_pattern_joins_its_alternatives(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def unknown(value):
            match value:
                case [handler] | [_, handler]:
                    handler()
        unknown([f, g])
        """,
    )

    assert callees(graph, "main.unknown") == ["main.f", "main.g"]


def test_a_guard_reads_the_captures_of_its_case(tmp_path):
    graph = graph_of(
        tmp_path,
        """
        def use(value):
            match value:
                case [handler, check] if check():
                    handler()
        use([f, g])
        """,
    )

    assert callees(graph, "main.use") == ["main.f", "main.g"]
