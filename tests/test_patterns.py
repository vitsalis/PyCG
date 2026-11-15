"""Names built from a constant part and another value (patterns).

`"visit_" + t`, `"visit_%s" % t`, `"visit_{}".format(t)` and `f"visit_{t}"`
are patterns: the constant prefix and suffix. `getattr(x, pattern)` loads
every attribute of `x` whose name matches: the names that the class bodies
of its MRO define and the fields that stores assign on it.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from programs import call_graph, callees, main_graph

VISITOR = """
class Visitor:
    def visit(self, node, kind):
        method = getattr(self, {name}, self.default_visit)
        return method(node)
    def default_visit(self, node): pass
class Interpreter(Visitor):
    def visit_field(self, node): pass
    def visit_index(self, node): pass
    def field_handler(self, node): pass
    def other(self, node): pass
"""

ALL_VISITS = [
    "<builtin>.getattr",
    "main.Interpreter.visit_field",
    "main.Interpreter.visit_index",
    "main.Visitor.default_visit",
]


def visit_callees(tmp_path, name):
    graph = main_graph(tmp_path, VISITOR.format(name=name))
    return [
        c for c in callees(graph, "main.Visitor.visit") if c != "<builtin>.str.format"
    ]


def test_a_prefix_and_an_unknown_part_load_every_matching_method(tmp_path):
    # kind is a parameter that no analysed code passes: any string.
    for index, name in enumerate(
        [
            '"visit_" + kind',
            '"visit_%s" % kind',
            '"visit_{}".format(kind)',
            'f"visit_{kind}"',
        ]
    ):
        assert visit_callees(tmp_path / str(index), name) == ALL_VISITS, name


def test_a_suffix(tmp_path):
    for index, name in enumerate(['kind + "_handler"', '"%s_handler" % kind']):
        assert visit_callees(tmp_path / str(index), name) == [
            "<builtin>.getattr",
            "main.Interpreter.field_handler",
            "main.Visitor.default_visit",
        ], name


def test_every_matching_name_whatever_the_other_value_is(tmp_path):
    # One rule: the other value does not narrow the names, even when it is
    # a constant.
    graph = main_graph(
        tmp_path,
        """
class Handler:
    def on_open(self): pass
    def on_close(self): pass
    def other(self): pass
def dispatch(handler, event):
    getattr(handler, "on_" + event)()
dispatch(Handler(), "close")
""",
    )

    assert callees(graph, "main.dispatch") == [
        "<builtin>.getattr",
        "main.Handler.on_close",
        "main.Handler.on_open",
    ]


def test_a_pattern_needs_a_constant_part(tmp_path):
    for index, name in enumerate(['"" + kind', '"%s" % kind', 'f"{kind}"']):
        assert visit_callees(tmp_path / str(index), name) == [
            "<builtin>.getattr",
            "main.Visitor.default_visit",
        ], name


def test_hasattr_with_a_pattern_calls_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Visitor:
    def check(self, kind):
        return hasattr(self, "visit_" + kind)
    def visit_field(self): pass
""",
    )

    assert callees(graph, "main.Visitor.check") == ["<builtin>.hasattr"]


def test_a_name_that_appears_later_is_found(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Visitor:
    def __init__(self):
        self.visit_extra = extra
    def visit(self, kind):
        getattr(self, "visit_" + kind)()
def late(self): pass
def extra(): pass
class Child(Visitor):
    pass
Child.visit_late = late
""",
    )

    assert callees(graph, "main.Visitor.visit") == [
        "<builtin>.getattr",
        "main.extra",
        "main.late",
    ]


def test_only_names_that_the_target_defines_are_loaded(tmp_path):
    graph = main_graph(
        tmp_path,
        """
import ext
class Proxy:
    def __getattr__(self, name):
        return ext.lookup(name)
class Remote(ext.Base):
    def visit_local(self): pass
class Visitor:
    def visit_field(self): pass
def dispatch(kind):
    getattr(Proxy(), "visit_" + kind)()
    getattr(Remote(), "visit_" + kind)()
""",
    )

    # Proxy defines no visit_ name, so its __getattr__ is not called; a name
    # of Visitor is not loaded on a Remote.
    assert callees(graph, "main.dispatch") == [
        "<builtin>.getattr",
        "ext.Base.__init__",
        "main.Remote.visit_local",
    ]


def test_setattr_with_a_pattern_stores_to_no_known_name(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def handler(): pass
class Visitor:
    def visit_field(self): pass
    def install(self, kind):
        setattr(self, "visit_" + kind, handler)
    def run(self):
        self.visit_field()
""",
    )

    assert callees(graph, "main.Visitor.run") == ["main.Visitor.visit_field"]


def test_a_module_attribute_by_pattern(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "commands.py": """
def cmd_start(): pass
def cmd_stop(): pass
def helper(): pass
""",
            "main.py": """
import commands
def run(name):
    getattr(commands, "cmd_" + name)()
""",
        },
    )

    assert callees(graph, "main.run") == [
        "<builtin>.getattr",
        "commands.cmd_start",
        "commands.cmd_stop",
    ]


def test_a_format_field_is_any_value(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Handler:
    def on_handler(self): pass
def dispatch(handler):
    getattr(handler, "on{²}_handler".format(**{"²": "x"}))
    getattr(handler, "on_{0}".format("x"))()
dispatch(Handler())
""",
    )

    assert callees(graph, "main.dispatch") == [
        "<builtin>.getattr",
        "<builtin>.str.format",
        "main.Handler.on_handler",
    ]


CASES = """
class Visitor:
    def visit(self, kind):
        return getattr(self, {name}, self.default)()
    def default(self): pass
    def visit_field(self): pass
    def visit_Field(self): pass
    def VISIT_INDEX(self): pass
    def VISIT_Index(self): pass
    def visit_é(self): pass
"""


def case_callees(tmp_path, name):
    graph = main_graph(tmp_path, CASES.format(name=name))
    return [c for c in callees(graph, "main.Visitor.visit") if c.startswith("main.")]


def test_lower_of_a_pattern_loads_the_names_that_lower_case_gives(tmp_path):
    # Python looks up the converted name: visit_Field never is one.
    for index, name in enumerate(
        [
            'f"visit_{kind}".lower()',
            '("Visit_" + kind).lower()',
            '("VISIT_%s" % kind).casefold()',
            '("visit_" + kind).upper().lower()',
        ]
    ):
        assert case_callees(tmp_path / str(index), name) == [
            "main.Visitor.default",
            "main.Visitor.visit_field",
            "main.Visitor.visit_é",
        ], name


def test_upper_of_a_pattern_loads_the_names_that_upper_case_gives(tmp_path):
    for index, name in enumerate(
        ['("visit_" + kind).upper()', 'f"visit_{kind}".lower().upper()']
    ):
        assert case_callees(tmp_path / str(index), name) == [
            "main.Visitor.VISIT_INDEX",
            "main.Visitor.default",
        ], name


def test_the_case_method_is_an_edge(tmp_path):
    graph = main_graph(tmp_path, CASES.format(name='("visit_" + kind).lower()'))

    assert callees(graph, "main.Visitor.visit") == [
        "<builtin>.getattr",
        "<builtin>.str.lower",
        "main.Visitor.default",
        "main.Visitor.visit_field",
        "main.Visitor.visit_é",
    ]


def test_other_str_methods_give_no_pattern(tmp_path):
    for index, name in enumerate(
        [
            '("visit_" + kind).strip()',
            '("visit_" + kind).title()',
            '("visit_" + kind).swapcase()',
            '"VISIT_FIELD".lower()',
        ]
    ):
        assert case_callees(tmp_path / str(index), name) == ["main.Visitor.default"], (
            name
        )


def test_a_case_pattern_matches_every_name_with_a_character_that_is_not_ascii(
    tmp_path,
):
    # Python calls visit_é for kind "É". The case of a character that is not
    # ASCII depends on the Unicode database, so a name with one may be what
    # the method gives, and a constant part with one gives no pattern.
    assert case_callees(tmp_path / "name", 'f"visit_{kind}".lower()') == [
        "main.Visitor.default",
        "main.Visitor.visit_field",
        "main.Visitor.visit_é",
    ]
    assert case_callees(tmp_path / "prefix", '("visité_" + kind).lower()') == [
        "main.Visitor.default"
    ]


def test_limit_an_outside_operand_names_no_other_attribute(tmp_path):
    # ext is outside code without stubs: its value may be a str subclass
    # whose `__radd__` returns "hit", and Python calls hit. The name then
    # also holds a str of unknown value, which names no attribute (see
    # *Computed attribute names*), so only the matching names are loaded.
    graph = main_graph(
        tmp_path,
        """
import ext
class Visitor:
    def visit_a(self): pass
    def hit(self): pass
    def visit(self):
        getattr(self, "visit_" + ext.value)()
Visitor().visit()
""",
    )

    assert callees(graph, "main.Visitor.visit") == [
        "<builtin>.getattr",
        "main.Visitor.visit_a",
    ]


# The `%` grammar as CPython reads it (Codex review, round 7). A pattern
# restricts a dict read, so it must hold for every str that `fmt % args`
# gives; where the analysis cannot read a format with certainty, it makes
# no pattern and the read is unrestricted.

PERCENT_PROGRAM = """
def f(): pass
def g(): pass
table = {{{result!r}: f, "zz_other": g}}
table[{fmt!r} % {args!r}]()
"""


def percent_callees(tmp_path, fmt, args, result):
    source = PERCENT_PROGRAM.format(fmt=fmt, args=args, result=result)
    graph = main_graph(tmp_path, source)
    return [c for c in callees(graph, "main") if c.startswith("main.")]


@pytest.mark.parametrize(
    "fmt, args",
    [
        # A mapping key with nested parentheses.
        ("%(a(b)c)s_tail", {"a(b)c": "hit"}),
        ("pre_%(k)s", {"k": "v"}),
        # Flags, width and precision, in digits or `*`.
        ("pre_%-5s_x", ("a",)),
        ("pre_% s_x", ("a",)),
        ("pre_%#s_x", ("a",)),
        ("pre_%+s_x", ("a",)),
        ("pre_%05s_x", ("a",)),
        ("pre_%*s_x", (3, "a")),
        ("pre_%.1s_x", ("abc",)),
        ("pre_%.*s_x", (1, "abc")),
        ("pre_%.s_x", ("abc",)),
        # One length modifier.
        ("pre_%hs_x", ("a",)),
        ("pre_%ls_x", ("a",)),
        ("pre_%Ls_x", ("a",)),
        # Every conversion type.
        *[(f"pre_%{kind}_x", (65,)) for kind in "diouxXeEfFgGc"],
        *[(f"pre_%{kind}_x", ("a",)) for kind in "sra"],
        # A literal percent.
        ("pre_%%_%s_x", ("a",)),
    ],
)
def test_a_percent_format_gives_a_pattern_that_its_result_matches(tmp_path, fmt, args):
    result = fmt % args
    assert "main.f" in percent_callees(tmp_path, fmt, args, result)


@pytest.mark.parametrize(
    "fmt",
    [
        # Python rejects each of these; the analysis makes no pattern.
        "pre_%s%",
        "pre_%s%y",
        "pre_%s%5%",
        "pre_%s%(a)%",
        "pre_%s%lls",
        "pre_%s%(a",
        "pre_%s%(k)*s",
    ],
)
def test_a_percent_format_that_python_rejects_gives_no_pattern(tmp_path, fmt):
    source = f"""
def f(): pass
def g(): pass
table = {{"pre_x": f, "other": g}}
def read(name):
    table[{fmt!r} % name]()
read("x")
"""
    graph = main_graph(tmp_path, source)
    assert [c for c in callees(graph, "main.read") if c.startswith("main.")] == [
        "main.f",
        "main.g",
    ]


# A field: `%`, a key, flags, a width, a precision, a length modifier
# and a conversion, each sometimes absent; between fields, literal text.
FIELDS = st.tuples(
    st.sampled_from(["", "(k)", "(a(b)c)", "((x))"]),
    st.sampled_from(["", "-", "0", " ", "#", "+", "-0"]),
    st.sampled_from(["", "5", "*"]),
    st.sampled_from(["", ".", ".1", ".*"]),
    st.sampled_from(["", "h", "l", "L"]),
    st.sampled_from(list("sradxcf%")),
)
LITERALS = st.sampled_from(["", "a", "_", "(", ")", "pre_", "_tail", "x)"])


@settings(max_examples=300, deadline=None)
@given(segments=st.lists(st.tuples(LITERALS, FIELDS), min_size=1, max_size=4))
def test_a_percent_pattern_matches_what_python_gives(tmp_path_factory, segments):
    fmt = "".join(text + "%" + "".join(field) for text, field in segments)
    if any(field[0] for _, field in segments):
        args = {"k": 65, "a(b)c": 65, "(x)": 65}
    else:
        count = sum(
            (field[5] != "%") + field[2].count("*") + field[3].count("*")
            for _, field in segments
        )
        args = (65,) * count
    try:
        result = fmt % args
    except (TypeError, ValueError, OverflowError):
        return
    root = tmp_path_factory.mktemp("percent")
    assert "main.f" in percent_callees(root, fmt, args, result), (fmt, args)


def test_a_literal_percent_is_part_of_the_pattern(tmp_path):
    source = """
def f(): pass
def g(): pass
table = {"100%_x": f, "100#_x": g}
def read(name):
    table["100%%_%s" % name]()
read("x")
"""
    graph = main_graph(tmp_path, source)
    assert [c for c in callees(graph, "main.read") if c.startswith("main.")] == [
        "main.f"
    ]
