"""Lists, tuples, sets and dicts; str and int constants; subscripts, slices,
unpacking, iteration over containers, and the methods of builtin types."""

import sys

import pytest
from programs import analysed, call_graph, callees, main_graph

from pycg.analysis import solver

FUNCTIONS = "def f(): pass\ndef g(): pass\ndef h(): pass\n"


def run(tmp_path, source):
    """The callees of `main` in a program that defines f, g and h first."""
    return callees(main_graph(tmp_path, FUNCTIONS + source), "main")


# Subscripts with constant keys


@pytest.mark.parametrize(
    "source, expected",
    [
        ("[f, g][1]()", ["main.g"]),
        ("(f, g, h)[-1]()", ["main.h"]),
        ("[f, g, h][-3]()", ["main.f"]),
        ("{'a': f, 'b': g}['a']()", ["main.f"]),
        ("{1: f, '1': g}[1]()", ["main.f"]),
        ("{1: f, '1': g}['1']()", ["main.g"]),
        ("[[f], g][0][0]()", ["main.f"]),
    ],
)
def test_constant_index_or_key_selects_one_element(tmp_path, source, expected):
    assert run(tmp_path, source) == expected


def test_two_containers_keep_their_own_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        FUNCTIONS
        + """
        first = {"key": f}
        second = {"key": g}
        def use():
            first["key"]()
        """.replace("\n        ", "\n"),
    )

    assert callees(graph, "main.use") == ["main.f"]


def test_key_that_is_not_a_constant_reads_every_element(tmp_path):
    source = """
def pick(i):
    return [f, g][i]
pick(int("1"))()
"""
    assert run(tmp_path, source) == ["<builtin>.int", "main.f", "main.g", "main.pick"]


def test_key_without_a_value_reads_every_element(tmp_path):
    # Nothing analysed calls item, and the key of last is arithmetic: code
    # outside the analysis or an untracked value provides the key.
    graph = main_graph(
        tmp_path,
        FUNCTIONS
        + """
TABLE = [f, g]
def item(i):
    TABLE[i]()
def last():
    TABLE[len(TABLE) - 1]()
def put(i):
    TABLE[i] = h
""",
    )

    assert callees(graph, "main.item") == ["main.f", "main.g", "main.h"]
    assert callees(graph, "main.last") == [
        "<builtin>.len",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_key_from_a_variable_with_constants(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "keys.py": "FIRST = 'a'\n",
            "main.py": FUNCTIONS
            + "from keys import FIRST\n"
            + "def call(key='b'):\n"
            + "    table[key]()\n"
            + "table = {'a': f, 'b': g, 'c': h}\n"
            + "table[FIRST]()\n"
            + "call()\n",
        },
    )

    assert callees(graph, "main") == ["main.call", "main.f"]
    assert callees(graph, "main.call") == ["main.g"]


def test_bool_and_none_keys_are_not_constants(tmp_path):
    # True == 1, so d[True] is d[1]: the analysis reads every element.
    assert run(tmp_path, "d = {1: f, 'x': g}\nd[True]()\n") == ["main.f", "main.g"]


# An int literal with more decimal digits than Python converts to a str by
# default (4300): hexadecimal literals have no such limit (final review of
# the engine, finding 3).
HUGE = "0x" + "f" * 4000


def test_a_key_too_long_for_a_decimal_str_selects_its_element(tmp_path):
    assert run(tmp_path, f"d = {{{HUGE}: f, 1: g}}\nd[{HUGE}]()\n") == ["main.f"]


# The fewest decimal digits that Python may be set to convert, the default,
# and no limit.
@pytest.mark.parametrize("limit", [640, 4300, 0])
def test_constants_are_named_the_same_whatever_the_conversion_limit(tmp_path, limit):
    previous = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(limit)
    try:
        generator = analysed(
            tmp_path,
            {
                "main.py": f"big = {HUGE}\nsmall = {'9' * 640}\n"
                f"d = {{{HUGE}: big, '\\U0001fae9': small}}\n"
            },
        )
        points_to = generator.output_points_to()
    finally:
        sys.set_int_max_str_digits(previous)

    # Every int that every Python converts to decimal is named in decimal;
    # a longer one in hexadecimal. A str is named with ascii(), so the name
    # does not depend on the Unicode version of the running Python either
    # (repr() shows U+1FAE9 from Python 3.14 on).
    big, small = hex(int(HUGE, 16)), "9" * 640
    assert points_to["main.big"] == [big]
    assert points_to["main.small"] == [small]
    assert points_to[f"dict@main:3:4[{big}]"] == [big]
    assert points_to["dict@main:3:4['\\U0001fae9']"] == [small]


def test_stores_with_constant_and_unknown_keys(tmp_path):
    source = """
d = {}
d["a"] = f
d["a"]()
xs = [None, None]
xs[1] = g
xs[1]()
def put(i):
    xs[i] = h
xs[0]()
"""
    assert run(tmp_path, source) == ["main.f", "main.g", "main.h"]


# Subscripts with pattern keys: a str with a constant prefix p and suffix s
# equals only the strs that start with p and end with s.


def own_callees(tmp_path, source, caller="main.read"):
    """The callees of `caller` that the program defines."""
    graph = main_graph(tmp_path, FUNCTIONS + source)
    return [c for c in callees(graph, caller) if c.startswith("main.")]


@pytest.mark.parametrize(
    "key",
    [
        '"ext.%s" % name',
        'f"ext.{name}"',
        '"ext." + name',
    ],
)
def test_a_pattern_key_reads_the_entries_whose_key_it_may_equal(tmp_path, key):
    # "ext." is "ext.%s" % "": the other value may be empty.
    source = f"""
table = {{"ext.a": f, "ext.": g, "ext": h, "other": h}}
def read(name):
    table[{key}]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


def test_limit_a_format_key_also_holds_the_str_that_the_stub_gives(tmp_path):
    # str.format returns a str of unknown value in the stubs. The key holds
    # it beside the pattern, and it may be any key.
    source = """
table = {"ext.a": f, "other": g}
def read(name):
    table["ext.{}".format(name)]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


@pytest.mark.parametrize("key", ['name + ".ext"', '"%s.ext" % name'])
def test_a_suffix_pattern_key(tmp_path, key):
    source = f"""
table = {{"a.ext": f, ".ext": g, "ext": h, "a.ext.b": h}}
def read(name):
    table[{key}]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


def test_a_pattern_key_is_never_shorter_than_its_prefix_and_suffix(tmp_path):
    # "aba" starts with "ab" and ends with "ba", but "ab" + x + "ba" has at
    # least four characters.
    source = """
table = {"aba": g, "abba": f}
def read(name):
    table[f"ab{name}ba"]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f"]


def test_a_pattern_key_reads_the_entries_stored_under_unknown_keys(tmp_path):
    source = """
table = {"ext.a": f, "other": g}
def put(key):
    table[key] = h
def read(name):
    table["ext.%s" % name]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.h"]


def test_a_pattern_key_never_equals_a_key_that_is_not_a_str(tmp_path):
    source = """
table = {b"ext.a": g, 1: g, "ext.a": f}
def read(name):
    table["ext.%s" % name]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f"]


@pytest.mark.parametrize(
    "key, expected",
    [
        # A constant selects its entry, the pattern those it may equal.
        ('"ext.%s" % name if name else "other"', ["main.f", "main.g"]),
        ('"ext.%s" % name if name else 1', ["main.f", "main.h"]),
        # A str of unknown value may be any key.
        ('"ext.%s" % name if name else str(name)', ["main.f", "main.g", "main.h"]),
    ],
)
def test_a_key_that_may_be_a_pattern_or_another_value_reads_the_union(
    tmp_path, key, expected
):
    source = f"""
table = {{"ext.a": f, "other": g, 1: h}}
def read(name):
    table[{key}]()
read("x")
"""
    assert own_callees(tmp_path, source) == expected


@pytest.mark.parametrize(
    "read, expected",
    [
        ("table.get(key)", ["main.f"]),
        ("table.get(key, h)", ["main.f", "main.h"]),
        ("table.pop(key)", ["main.f"]),
        ("table.setdefault(key, h)", ["main.f", "main.h"]),
    ],
)
def test_dict_methods_look_a_pattern_key_up_as_a_subscript_does(
    tmp_path, read, expected
):
    source = f"""
table = {{"ext.a": f, "other": g}}
def read(name):
    key = "ext.%s" % name
    {read}()
read("x")
"""
    assert own_callees(tmp_path, source) == expected


@pytest.mark.parametrize(
    "make",
    [
        "collections.OrderedDict(ext_a=f, other=g)",
        "collections.defaultdict(list, ext_a=f, other=g)",
    ],
)
def test_dicts_of_collections_read_a_pattern_key_as_a_dict(tmp_path, make):
    source = f"""
import collections
table = {make}
def read(name):
    table["ext_%s" % name]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f"]


def test_a_store_under_a_pattern_key_reaches_the_keys_it_may_equal(tmp_path):
    # Python reads g for name "a". The store goes to the unknown key.
    source = """
table = {"ext.a": f}
def put(name):
    table["ext.%s" % name] = g
def read():
    table["ext.a"]()
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


def test_a_case_pattern_key_reads_the_keys_that_the_case_method_may_give(tmp_path):
    # lower() never gives "A", but gives "é" for "É". The case of a
    # character that is not ASCII depends on the Unicode database of the
    # running Python, so the analysis does not decide it: a key with one
    # may always be equal ("ext_É" too).
    source = """
def k(): pass
table = {"ext_a": f, "ext_A": g, "ext_é": h, "ext_É": k}
def read(name):
    table[("EXT_" + name).lower()]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.h", "main.k"]


@pytest.mark.parametrize(
    "key", ['"pre_" + ext.value', 'ext.value + "_x"', '"pre_%s" % ext.value']
)
def test_an_outside_operand_may_give_any_key(tmp_path, key):
    # ext is outside code without stubs. Its value may be a str subclass
    # whose `__radd__`, `__add__` or `__rmod__` runs and returns "hit".
    source = f"""
import ext
table = {{"hit": f, "pre_x": g, "other": h}}
def read():
    table[{key}]()
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g", "main.h"]


@pytest.mark.parametrize("key", ['"pre_" + name', '"pre_%s" % name'])
def test_an_operand_that_holds_nothing_may_give_any_key(tmp_path, key):
    # No analysed code calls read: code outside the analysis gives name.
    source = f"""
table = {{"hit": f, "pre_x": g}}
def read(name):
    table[{key}]()
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


def test_an_operand_that_the_entry_points_fill_is_not_unknown(tmp_path):
    # Nothing calls use: its receiver is an entry point, which the
    # completion fills at a fixpoint; only then does `self.config` call
    # `__getattr__` with "config". The operand is decided after that.
    graph = main_graph(
        tmp_path,
        """
class App:
    def run(self):
        pass
class Request:
    def __init__(self, environ):
        self.environ = environ
    def __getattr__(self, name):
        return self.environ["ext.%s" % name]
    def use(self):
        self.config.run()
Request({"app": App()})
""",
    )

    assert "main.App.run" not in callees(graph, "main.Request.use")


@pytest.mark.parametrize(
    "key",
    [
        '"pre_" + Odd()',
        # The first `+` replaces the prefix (Codex review, round 2).
        '"pre_" + Odd() + "_tail"',
        # str.__mod__ runs first unless the class derives from str, which
        # the analysis does not decide here.
        '"pre_%s" % Odd()',
    ],
)
def test_an_instance_of_an_analysed_class_may_give_any_key(tmp_path, key):
    # The operator still calls its reflected method, whose result joins.
    source = f"""
class Odd:
    def __radd__(self, other):
        return "hit_tail"
    def __rmod__(self, other):
        return "hit_tail"
table = {{"hit_tail": f, "pre_x": g, "other": h}}
def read():
    table[{key}]()
"""
    found = own_callees(tmp_path, source)
    assert [c for c in found if not c.startswith("main.Odd")] == [
        "main.f",
        "main.g",
        "main.h",
    ]


def test_a_single_field_fstring_operand_may_give_any_key(tmp_path):
    # f"{x}" is what format() returns, which may be a str subclass whose
    # `__radd__` runs (Codex review, round 2).
    source = """
class Odd(str):
    def __radd__(self, other):
        return "hit"
class Wrap:
    def __format__(self, spec):
        return Odd("x")
table = {"hit": f, "pre_x": g}
def read():
    table["pre_" + f"{Wrap()}"]()
"""
    assert own_callees(tmp_path, source) == ["main.Wrap.__format__", "main.f", "main.g"]


@pytest.mark.parametrize(
    "operand", ['f"a{name}"', 'f"{name}{name}"', '"a%s" % name', '"a{}".format(name)']
)
def test_an_operand_that_is_an_exact_str_leaves_the_pattern(tmp_path, operand):
    # An f-string with a literal part or two fields, `%` and `str.format` of
    # a literal build a new str of exactly that class.
    source = f"""
table = {{"pre_ax": f, "other": g}}
def read(name):
    table["pre_" + {operand}]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f"]


@pytest.mark.parametrize("key", ['"pre_" + E.A', '"pre_%s" % E.A'])
def test_an_enum_member_whose_value_is_a_pattern_may_give_any_key(tmp_path, key):
    # The member is a str subclass instance whose `__radd__` or `__rmod__`
    # runs first; its value is a pattern (Codex review, round 4).
    source = f"""
from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    A = "enum_" + suffix()
    def __radd__(self, prefix):
        return "hit"
    def __rmod__(self, fmt):
        return "hit"
table = {{"hit": f, "pre_x": g}}
def read():
    table[{key}]()
"""
    found = own_callees(tmp_path, source)
    assert [c for c in found if c in ("main.f", "main.g")] == ["main.f", "main.g"]


def test_a_widened_result_of_an_empty_operand_is_not_a_plain_str(tmp_path):
    # No analysed code calls read: name holds nothing until step 4, which
    # makes k any value; the second `+` widens again.
    source = """
table = {"hit": f, "top_x": g}
def read(name):
    k = "pre_" + name
    table["top_" + k]()
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


def test_an_enum_member_operand_may_give_any_key(tmp_path):
    # A member is a constant that the class machinery may replace (an
    # inexact constant); this one's `__radd__` runs first.
    source = """
from enum import Enum
class Kind(str, Enum):
    A = "x"
    def __radd__(self, other):
        return "hit"
table = {"hit": f, "pre_x": g}
def read():
    table["pre_" + Kind.A]()
"""
    found = own_callees(tmp_path, source)
    assert [c for c in found if not c.startswith("main.Kind")] == ["main.f", "main.g"]


def test_a_tuple_right_operand_of_percent_leaves_the_pattern(tmp_path):
    # No tuple derives from str: str.__mod__ runs and formats it.
    source = """
table = {"pre_x": f, "other": g}
def read(name):
    table["pre_%s" % (name,)]()
read("x")
"""
    assert own_callees(tmp_path, source) == ["main.f"]


def test_an_inexact_container_operand_may_give_any_key(tmp_path):
    # An enum member whose value is a tuple is a container that the class
    # machinery replaces: here a str subclass whose `__rmod__` runs first
    # (Codex review, round 3).
    source = """
from enum import Enum
class E(str, Enum):
    A = ("x",)
    def __rmod__(self, fmt):
        return "hit"
table = {"hit": f, "pre_x": g}
def read():
    table["pre_%s" % E.A]()
"""
    found = own_callees(tmp_path, source)
    assert [c for c in found if not c.startswith("main.E")] == ["main.f", "main.g"]


@pytest.mark.parametrize(
    "first",
    [
        # Codex review, round 3: k is an Odd, whose `__radd__` gives "hit".
        """
class Odd(str):
    def __format__(self, spec):
        return self
    def __radd__(self, left):
        return self if left == "pre_" else "hit"
k = "pre_" + f"{Odd('x')}"
""",
        # k may be what ext.value's `__radd__` returns, of any class.
        """
import ext
k = "pre_" + ext.value
""",
    ],
)
def test_a_widened_result_is_not_taken_as_a_plain_str(tmp_path, first):
    # The result of the first `+` is not known: the second `+` may run its
    # reflected method too.
    source = (
        first
        + """
table = {"hit": f, "top_x": g}
def read():
    table["top_" + k]()
"""
    )
    found = own_callees(tmp_path, source)
    assert [c for c in found if not c.startswith("main.Odd")] == ["main.f", "main.g"]


def test_the_operands_wait_for_the_opened_files(tmp_path):
    # Codex review, round 2: the mode holds nothing until step 3 of the
    # fixpoint steps makes it unknown; then read() gives a str or bytes.
    source = """
table = {"pre_x": f, "other": g}
def read(mode):
    table["pre_" + open("p", mode).read()]()
"""
    assert own_callees(tmp_path, source) == ["main.f"]


def test_limit_an_operand_that_only_the_completion_fills_stays_unknown(tmp_path):
    # Python raises KeyError: no key starts with "pre_". k holds nothing
    # until step 4 widens the read, which gives "x" to v and to k. k then
    # holds a str constant only, but the unknown value stays: v keeps "x",
    # and getattr loads O.x, which only the widened read can reach.
    source = """
class O:
    def x(self): pass
table = {"other": "x"}
def read(k):
    v = table["pre_" + k]
    read(v)
    getattr(O(), v)()
"""
    assert "main.O.x" in own_callees(tmp_path, source)


def test_limit_a_typed_str_operand_is_of_its_declared_class(tmp_path):
    # A subclass of str that overrides `__radd__` may reach name, but a
    # typed value is taken to be of its declared class. (`"pre_%s" % name`
    # also holds the str of unknown value that the stubs give.)
    source = """
table = {"hit": f, "pre_x": g}
def read(name: str):
    table["pre_" + name]()
"""
    assert own_callees(tmp_path, source) == ["main.g"]


def test_limit_a_store_under_a_pattern_key_is_read_by_any_constant_key(tmp_path):
    # Python never reads g by "other": the stored key starts with "ext.".
    source = """
table = {"other": f}
def put(name):
    table["ext.%s" % name] = g
put("a")
def read():
    table["other"]()
"""
    assert own_callees(tmp_path, source) == ["main.f", "main.g"]


# Keys stored under a class member (an enum member): the member may equal
# any str, whatever its value, by its own equality, hashing or
# construction. A pattern read reads them all.

ALIAS_KEYS = {
    "a StrEnum member with its own __eq__ and __hash__": """
from enum import StrEnum
class E(StrEnum):
    A = "other"
    def __hash__(self):
        return hash("pre_a")
    def __eq__(self, other):
        return other == "pre_a"
""",
    "an IntEnum member with its own __eq__ and __hash__ (round 4)": """
from enum import IntEnum
class E(IntEnum):
    A = 1
    def __hash__(self):
        return hash("pre_a")
    def __eq__(self, other):
        return other == "pre_a"
""",
    "a str enum member that __new__ builds from its value (round 5)": """
from enum import Enum
class E(str, Enum):
    def __new__(cls, value):
        obj = str.__new__(cls, "pre_" + value)
        obj._value_ = value
        return obj
    A = "a"
""",
}


@pytest.mark.skipif(sys.version_info < (3, 11), reason="StrEnum")
@pytest.mark.parametrize("enum", ALIAS_KEYS, ids=list(ALIAS_KEYS))
@pytest.mark.parametrize("table", ["{E.A: hit}", "dict({E.A: hit})", "{**{E.A: hit}}"])
def test_a_pattern_read_reads_the_keys_stored_under_a_class_member(
    tmp_path, enum, table
):
    # Python calls hit for kind "a".
    source = (
        ALIAS_KEYS[enum]
        + f"""
def hit(): pass
table = {table}
def read(kind):
    table["pre_" + kind]()
read("a")
"""
    )
    assert own_callees(tmp_path, source) == ["main.hit"]


def test_a_constant_read_of_a_member_key_stays_as_it_was(tmp_path):
    # Not part of the pattern rule: a constant key reads its field and the
    # unknown field only.
    source = """
from enum import Enum
class E(Enum):
    A = "a"
table = {E.A: f, "b": g}
def read():
    table["b"]()
"""
    assert own_callees(tmp_path, source) == ["main.g"]


@pytest.mark.parametrize("method", ["lower", "upper", "casefold"])
@pytest.mark.parametrize("value", ['"enum_" + suffix()', '"x"'])
@pytest.mark.parametrize("key", ["E.A.{method}()", '"pre_" + E.A.{method}()'])
def test_a_case_method_of_a_member_may_give_any_key(tmp_path, method, value, key):
    # The member's class defines the method (Codex review, round 5). It
    # returns an Odd, which equals "hit", and whose `__radd__` gives "hit":
    # Python reads "hit" either way.
    source = f"""
from enum import Enum
def suffix():
    return "x"
class Odd(str):
    def __radd__(self, other):
        return "hit"
class E(str, Enum):
    A = {value}
    def {method}(self):
        return Odd("hit")
table = {{"hit": f, "pre_x": g, "other": h}}
def read():
    table[{key.format(method=method)}]()
"""
    assert "main.f" in own_callees(tmp_path, source)


def test_a_member_whose_value_is_a_pattern_is_not_a_str_to_a_class_test(tmp_path):
    # A plain Enum member is no str, whatever its value.
    generator = analysed(
        tmp_path,
        {
            "main.py": """
from enum import Enum
def suffix():
    return "x"
class E(Enum):
    A = "enum_" + suffix()
item = E.A
if not isinstance(item, str):
    kept = item
"""
        },
    )

    assert generator.output_points_to().get("main.kept")


NEW_MEMBER = """
from enum import Enum
class E(str, Enum):
    def __new__(cls, value):
        obj = str.__new__(cls, "pre_" + value)
        obj._value_ = value
        return obj
    A = "a"
def hit(): pass
"""


@pytest.mark.parametrize(
    "flow",
    [
        # Codex review, round 6: the keys of `**` reach the callee's
        # `**kwargs`, a model's `**kwargs` and from there a dict.
        """
def read(**table):
    kind = "a"
    table["pre_" + kind]()
read(**{E.A: hit})
""",
        """
table = dict(**{E.A: hit})
def read(kind):
    table["pre_" + kind]()
read("a")
""",
        """
table = {}
table.update(**{E.A: hit})
def read(kind):
    table["pre_" + kind]()
read("a")
""",
        # A dict that a class body binds is an alias of the dict.
        """
class Holder:
    table = {E.A: hit}
def read(kind):
    Holder.table["pre_" + kind]()
read("a")
""",
    ],
)
def test_the_keys_stored_under_a_class_member_travel_with_the_dict(tmp_path, flow):
    # Python calls hit: E.A equals "pre_a".
    source = NEW_MEMBER + flow
    graph = main_graph(tmp_path, FUNCTIONS + source)
    assert any("main.hit" in found for found in graph.values())


@pytest.mark.parametrize(
    "read", ["table[E.A]()", "table.get(E.A)()", "table.pop(E.A)()"]
)
def test_a_member_whose_value_is_a_pattern_as_the_key_reads_every_element(
    tmp_path, read
):
    # Codex review, round 6: the member's own `__eq__` and `__hash__` make
    # it equal to "hit"; Python calls f.
    source = f"""
from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    A = "pre_" + suffix()
    def __hash__(self):
        return hash("hit")
    def __eq__(self, other):
        return other == "hit"
table = {{"hit": f}}
def read():
    {read}
"""
    assert own_callees(tmp_path, source) == ["main.f"]


def test_a_case_method_of_a_member_keeps_the_str_it_gives(tmp_path):
    # Codex review, round 6: the any value is added, not put in place of the
    # str (or pattern) that str's own method gives.
    graph = main_graph(
        tmp_path,
        """
def suffix():
    return "a"
class C:
    value = "abc"
class Names:
    name = "Visit_" + suffix()
class V:
    def visit_a(self): pass
C.value.lower().upper()
getattr(V(), Names.name.lower())()
""",
    )

    found = callees(graph, "main")
    assert "<builtin>.str.upper" in found
    assert "main.V.visit_a" in found


def test_the_frozen_engine_program_calls_nothing_through_a_pattern_key(tmp_path):
    # Round 3, proposal B1: Python raises KeyError at `request.config`.
    graph = main_graph(
        tmp_path,
        """
class App:
    def run(self):
        pass
class Request:
    def __init__(self, environ):
        self.environ = environ
        environ["app"] = App()
    def __getattr__(self, name):
        return self.environ["ext.%s" % name]
request = Request({})
request.config.run()
""",
    )

    assert "main.App.run" not in callees(graph, "main")


# Slices and unpacking


@pytest.mark.parametrize(
    "source, expected",
    [
        ("[f, g, h][1:3][0]()", ["main.g"]),
        ("[f, g, h][:-1][1]()", ["main.g"]),
        ("[f, g, h][-2:][0]()", ["main.g"]),
        ("[f, g, h][::2][0]()", ["main.f", "main.g", "main.h"]),
    ],
)
def test_slices(tmp_path, source, expected):
    assert run(tmp_path, source) == expected


def test_unpacking_by_position(tmp_path):
    source = """
a, (b, c) = f, (g, h)
b()
def pair():
    return [g, f]
x, y = pair()
y()
"""
    assert run(tmp_path, source) == ["main.f", "main.g", "main.pair"]


def test_starred_unpacking(tmp_path):
    graph = main_graph(
        tmp_path,
        FUNCTIONS
        + "def k(): pass\n"
        + "first, *middle, last = f, g, h, k\n"
        + "def use():\n"
        + "    middle[0]()\n"
        + "    last()\n",
    )

    assert callees(graph, "main.use") == ["main.g", "main.k"]


def test_unpacking_a_dict_gives_its_keys(tmp_path):
    assert run(tmp_path, "a, b = {f: 1, g: 2}\na()\n") == ["main.f", "main.g"]


# Iteration over containers


def test_for_loops_over_containers(tmp_path):
    source = """
for x in [f]:
    x()
for key in {g: 1}:
    key()
d = {"a": h}
for name, value in d.items():
    value()
for value in d.values():
    value()
"""
    assert run(tmp_path, source) == [
        "<builtin>.dict.items",
        "<builtin>.dict.values",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_comprehensions_hold_their_elements(tmp_path):
    source = """
[x for x in (f,)][0]()
{k: v for k, v in [("a", g)]}["a"]()
for y in (x for x in [h]):
    y()
"""
    assert run(tmp_path, source) == ["main.f", "main.g", "main.h"]


# Methods and constructors


def test_methods_of_builtin_types_are_edges(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        " ".join(["a", "b"])
        words = "a b".split()
        count = 3
        count.bit_length()
        d = {}
        d.clear()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.dict.clear",
        "<builtin>.int.bit_length",
        "<builtin>.str.join",
        "<builtin>.str.split",
    ]


def test_methods_that_add_elements(tmp_path):
    source = """
xs = []
xs.append(f)
xs.insert(0, g)
xs.extend([h])
xs[0]()
"""
    assert run(tmp_path, source) == [
        "<builtin>.list.append",
        "<builtin>.list.extend",
        "<builtin>.list.insert",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_dict_methods(tmp_path):
    source = """
d = {"a": f}
d.update({"b": g}, c=h)
d["b"]()
d.get("c")()
d.setdefault("e", f)()
d.pop("a")()
"""
    assert run(tmp_path, source) == [
        "<builtin>.dict.get",
        "<builtin>.dict.pop",
        "<builtin>.dict.setdefault",
        "<builtin>.dict.update",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_dict_get_with_a_default(tmp_path):
    assert run(tmp_path, "{'a': f}.get('b', g)()\n") == [
        "<builtin>.dict.get",
        "main.g",
    ]


def test_set_methods(tmp_path):
    source = """
s = set()
s.add(f)
s.update([g])
s.pop()()
"""
    assert run(tmp_path, source) == [
        "<builtin>.set",
        "<builtin>.set.add",
        "<builtin>.set.pop",
        "<builtin>.set.update",
        "main.f",
        "main.g",
    ]


@pytest.mark.parametrize(
    "source, methods",
    [
        ("xs = []\nxs.insert(0, C())\nxs[0].m()", ["list.insert"]),
        ("[C()].pop().m()", ["list.pop"]),
        ("s = set()\ns.add(C())\ns.pop().m()", ["set", "set.add", "set.pop"]),
        ("{C()}.copy().pop().m()", ["set.copy", "set.pop"]),
        ("for x in frozenset((C(),)).copy(): x.m()", ["frozenset", "frozenset.copy"]),
        ('{}.setdefault("k", C()).m()', ["dict.setdefault"]),
        ("d = {}\nd.setdefault(C())\nfor k in d: k.m()", ["dict.setdefault"]),
        ('{"k": C()}.pop("k").m()', ["dict.pop"]),
        ('{"k": C()}.copy()["k"].m()', ["dict.copy"]),
        ("for k in {C(): 1}.keys(): k.m()", ["dict.keys"]),
        ("for v in {1: C()}.values(): v.m()", ["dict.values"]),
    ],
)
def test_modelled_methods_keep_the_instances_they_hold(tmp_path, source, methods):
    # An instance, not a function: external code calls back the functions
    # passed to it, which would hide a method that is not modelled.
    graph = main_graph(tmp_path, "class C:\n    def m(self): pass\n" + source)

    assert callees(graph, "main") == [
        *(f"<builtin>.{method}" for method in methods),
        "main.C.m",
    ]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("list((f,))[0]()", ["<builtin>.list", "main.f"]),
        ("tuple([g, h])[1]()", ["<builtin>.tuple", "main.h"]),
        ("set([f]).pop()()", ["<builtin>.set", "<builtin>.set.pop", "main.f"]),
        ("for x in frozenset((g,)): x()", ["<builtin>.frozenset", "main.g"]),
        ('dict({"a": f})["a"]()', ["<builtin>.dict", "main.f"]),
        ('dict(b=g)["b"]()', ["<builtin>.dict", "main.g"]),
        ('dict([("c", h)])["c"]()', ["<builtin>.dict", "main.h"]),
        ('dict(**{"d": f})["d"]()', ["<builtin>.dict", "main.f"]),
    ],
)
def test_constructors_copy_their_contents(tmp_path, source, expected):
    assert run(tmp_path, source) == expected


def test_copies_are_new_containers(tmp_path):
    source = """
xs = [f]
ys = xs.copy()
ys.append(g)
xs[0]()
"""
    assert run(tmp_path, source) == [
        "<builtin>.list.append",
        "<builtin>.list.copy",
        "main.f",
    ]


def test_concatenation_and_repetition(tmp_path):
    source = """
([f] + [g])[1]()
([h] * 2)[0]()
xs = [f]
xs += [g]
xs[0]()
"""
    assert run(tmp_path, source) == ["main.f", "main.g", "main.h"]


# Termination


def test_self_containing_containers_terminate(tmp_path):
    source = """
x = [f]
x.append(x)
x[1][1][0]()
d = {}
d["self"] = d
d["self"]["self"]["f"] = g
d["f"]()
xs = [h]
for item in xs:
    xs.append([item])
xs[0]()
"""
    assert run(tmp_path, source) == [
        "<builtin>.list.append",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_inplace_concatenation_changes_the_list_of_the_caller(tmp_path):
    source = """
def extend(items):
    items += [g]
xs = [f]
extend(xs)
xs[0]()
"""
    assert run(tmp_path, source) == ["main.extend", "main.f", "main.g"]


def test_items_gives_key_value_pairs(tmp_path):
    source = """
for key, value in {f: g}.items():
    value()
"""
    assert run(tmp_path, source) == ["<builtin>.dict.items", "main.g"]


def test_modelled_methods_bind_unpacked_and_keyword_arguments(tmp_path):
    source = """
xs = []
xs.append(*(f,))
xs[0]()
d = {}
d.setdefault(*("k", g))
d["k"]()
d.get(*("missing",), **{"default": h})
{}.get("x", *(h,))()
"""
    assert run(tmp_path, source) == [
        "<builtin>.dict.get",
        "<builtin>.dict.setdefault",
        "<builtin>.list.append",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_unpacked_arguments_may_supply_optional_parameters(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def m(self): pass
        def target(): pass
        xs = [C()]
        list(*(xs,))[0].m()
        for _ in iter(*(target, None)):
            pass
        """,
    )

    # The sentinel makes iter call its first argument.
    assert callees(graph, "main") == [
        "<builtin>.iter",
        "<builtin>.list",
        "main.C.m",
        "main.target",
    ]


def test_dict_keys_are_recorded_when_the_value_is_untracked(tmp_path):
    graph = main_graph(
        tmp_path,
        FUNCTIONS
        + """
class C:
    def m(self): pass
callbacks = {f: None}
for callback in callbacks:
    callback()
d = {}
d.setdefault(g)
for key in d:
    key()
def names(**kw):
    for name in kw:
        getattr(C, name)(C())
names(m=None)
""",
    )

    assert callees(graph, "main") == [
        "<builtin>.dict.setdefault",
        "main.f",
        "main.g",
        "main.names",
    ]
    assert callees(graph, "main.names") == ["<builtin>.getattr", "main.C.m"]


@pytest.mark.parametrize("order", [solver.Order(), solver.LastInFirstOut()])
def test_long_chain_of_concatenations_does_not_exhaust_the_stack(
    tmp_path, monkeypatch, order
):
    # Copying the fields of each `+` into the next must not nest calls, in
    # any order of the solve.
    monkeypatch.setattr(solver.Solver, "order", order)
    chain = " + ".join(f"['n{i}']" for i in range(700))
    graph = call_graph(tmp_path, {"main.py": f"__all__ = {chain}\n"})

    assert graph == {"main": []}


@pytest.mark.skipif(sys.version_info < (3, 15), reason="PEP 798 needs Python 3.15")
def test_unpacking_in_comprehensions(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def items(): return [f]
        def mapping(): return {"k": g}
        for h in [*make() for make in (items,)]:
            h()
        {**make() for make in (mapping,)}["k"]()
        """,
    )

    assert callees(graph, "main") == ["main.f", "main.g", "main.items", "main.mapping"]


@pytest.mark.skipif(sys.version_info < (3, 15), reason="PEP 798 needs Python 3.15")
def test_a_set_comprehension_hashes_what_it_unpacks_unless_a_set_holds_it(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Key:
            def __hash__(self): return 1
        def unpacked(source):
            return {*source for _ in (1,)}
        def from_list():
            unpacked([Key()])
        def from_set(keys):
            return {*keys for _ in (1,)}
        from_list()
        from_set({Key()})
        """,
    )

    assert "main.Key.__hash__" in callees(graph, "main.unpacked")
    assert "main.Key.__hash__" not in callees(graph, "main.from_set")


def test_dict_comprehension_with_a_lambda_value(tmp_path):
    # The scope pass visits the key and the value of a dict comprehension.
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        table = {name: (lambda: f()) for name in ("a",)}
        table["a"]()
        """,
    )

    assert callees(graph, "main") == ["main.<lambda1>"]
    assert callees(graph, "main.<lambda1>") == ["main.f"]


# The containers of collections


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "d = collections.OrderedDict()\nd['a'] = f\nd['a']()",
            ["collections.OrderedDict", "main.f"],
        ),
        (
            "collections.OrderedDict(a=g)['a']()",
            ["collections.OrderedDict", "main.g"],
        ),
        (
            "collections.OrderedDict([('a', h)])['a']()",
            ["collections.OrderedDict", "main.h"],
        ),
        (
            "for v in collections.OrderedDict({'a': f}).values(): v()",
            [
                "collections.OrderedDict",
                "collections.OrderedDict.values",
                "main.f",
            ],
        ),
        (
            "for k in collections.OrderedDict({g: 1}): k()",
            ["collections.OrderedDict", "main.g"],
        ),
        (
            "for k, v in collections.Counter([f]).items(): k()",
            ["collections.Counter", "collections.Counter.items", "main.f"],
        ),
        (
            "c = collections.Counter()\nc.update([g])\nfor k in c: k()",
            ["collections.Counter", "collections.Counter.update", "main.g"],
        ),
        (
            "q = collections.deque([f])\nq.appendleft(g)\nq.popleft()()",
            [
                "collections.deque",
                "collections.deque.appendleft",
                "collections.deque.popleft",
                "main.f",
                "main.g",
            ],
        ),
        (
            "q = collections.deque()\nq.extendleft([h])\nq.append(f)\nq[0]()",
            [
                "collections.deque",
                "collections.deque.append",
                "collections.deque.extendleft",
                "main.f",
                "main.h",
            ],
        ),
        (
            "from collections import OrderedDict\nOrderedDict(a=f).pop('a')()",
            ["collections.OrderedDict", "collections.OrderedDict.pop", "main.f"],
        ),
    ],
)
def test_containers_of_collections_hold_their_elements(tmp_path, source, expected):
    assert run(tmp_path, "import collections\n" + source) == expected


def test_a_deque_keeps_no_positions_also_for_an_index(tmp_path):
    # appendleft moves every element: an indexed store goes to the
    # elements, and an indexed read, negative or not, reads them all. A list
    # keeps its positions.
    source = """
import collections
def use():
    q = collections.deque([None])
    q[0] = f
    q.appendleft(None)
    q[1]()
    r = collections.deque()
    r.append(g)
    r[-1]()
    xs = [None, h]
    xs[0] = f
    xs[1]()
use()
"""
    graph = main_graph(tmp_path, FUNCTIONS + source)

    assert callees(graph, "main.use") == [
        "collections.deque",
        "collections.deque.append",
        "collections.deque.appendleft",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_containers_of_collections_are_dicts_and_lists_to_builtins(tmp_path):
    source = """
import collections
def call(a):
    a()
d = collections.OrderedDict(a=f)
dict(d)["a"]()
call(**collections.defaultdict(None, a=g))
for x in list(collections.deque([h])):
    x()
"""
    graph = main_graph(tmp_path, FUNCTIONS + source)

    assert callees(graph, "main") == [
        "<builtin>.dict",
        "<builtin>.list",
        "collections.OrderedDict",
        "collections.defaultdict",
        "collections.deque",
        "main.call",
        "main.f",
        "main.h",
    ]
    assert callees(graph, "main.call") == ["main.g"]


def test_a_copy_of_a_container_of_collections_keeps_its_class(tmp_path):
    source = """
import collections
d = collections.OrderedDict(a=f)
d.copy()["a"]()
d.copy().get("a")
"""
    assert run(tmp_path, source) == [
        "collections.OrderedDict",
        "collections.OrderedDict.copy",
        "collections.OrderedDict.get",
        "main.f",
    ]


def test_a_dict_of_collections_hashes_its_keys(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import collections
        class Key:
            def __hash__(self): return 1
        d = collections.OrderedDict()
        d[Key()] = 1
        """,
    )

    assert callees(graph, "main") == ["collections.OrderedDict", "main.Key.__hash__"]


def test_a_defaultdict_read_calls_its_factory(tmp_path):
    # `d[k]` calls `__missing__` for a missing key, which calls the factory
    # without arguments: an implicit call from the scope that reads, whose
    # result is the value (evaluation/micro-benchmark/README.md, "Callbacks").
    graph = main_graph(
        tmp_path,
        """
        import collections
        class Node:
            def __init__(self): pass
            def visit(self): pass
        class Factory:
            def __call__(self): return g
        def make():
            return f
        def f(): pass
        def g(): pass
        def use():
            lists = collections.defaultdict(list)
            lists["a"].append(g)
            for x in lists["a"]:
                x()
            collections.defaultdict(make)["b"]()
            collections.defaultdict(Node)["c"].visit()
            collections.defaultdict(lambda: g)["d"]()
            collections.defaultdict(Factory())["e"]()
        use()
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.list.append",
        "collections.defaultdict",
        "main.Factory.__call__",
        "main.Node.__init__",
        "main.Node.visit",
        "main.f",
        "main.g",
        "main.make",
        "main.use.<lambda1>",
    ]


def test_only_a_read_of_a_defaultdict_calls_its_factory(tmp_path):
    # A store, `get`, `in` and `del` never call `__missing__`.
    graph = main_graph(
        tmp_path,
        """
        import collections
        def make(): pass
        def use(table):
            table["a"] = 1
            table.get("b")
            "c" in table
            del table["a"]
        use(collections.defaultdict(make))
        """,
    )

    assert callees(graph, "main.use") == ["collections.defaultdict.get"]


def test_a_defaultdict_factory_gives_what_a_call_without_arguments_returns(tmp_path):
    # The factory's result is that of an ordinary call with no arguments:
    # a default that it returns, the receiver of a bound method that returns
    # itself. What other calls pass to it is not its result here.
    graph = main_graph(
        tmp_path,
        """
        import collections
        def f(): pass
        def g(): pass
        def make(cb=f):
            return cb
        class Node:
            def same(self):
                return self
            def visit(self): pass
        def use():
            collections.defaultdict(make)["a"]()
            collections.defaultdict(Node().same)["b"].visit()
        make(g)
        use()
        """,
    )

    assert callees(graph, "main.use") == [
        "collections.defaultdict",
        "main.Node.same",
        "main.Node.visit",
        "main.f",
        "main.make",
    ]


def test_annotations_of_collections_name_the_methods_by_their_class(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import collections
        import typing
        def f(): pass
        def use(
            ordered: typing.OrderedDict[str, int],
            queue: collections.deque,
            counts: collections.Counter[str],
        ):
            ordered.items()
            queue.append(f)
            counts.most_common()
        """,
    )

    assert callees(graph, "main.use") == [
        "collections.Counter.most_common",
        "collections.OrderedDict.items",
        "collections.deque.append",
    ]


def test_limit_a_chain_map_does_not_track_its_mappings(tmp_path):
    source = """
import collections
collections.ChainMap({"a": f})["a"]()
"""
    assert run(tmp_path, source) == ["collections.ChainMap"]


def test_an_operator_on_a_container_of_collections_gives_what_its_stub_says(tmp_path):
    source = """
import collections
counts = collections.Counter([f]) + collections.Counter()
counts.most_common()
ordered = collections.OrderedDict() | {}
ordered.move_to_end("a")
"""
    assert run(tmp_path, source) == [
        "collections.Counter",
        "collections.Counter.most_common",
        "collections.OrderedDict",
        "collections.OrderedDict.move_to_end",
    ]
