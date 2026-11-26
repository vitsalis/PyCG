import sys

import pytest
from programs import callees, main_graph

NUMBER = """
def f(): pass
class Number:
    def __add__(self, other):
        return self
    def __radd__(self, other):
        return f
    def __iadd__(self, other):
        return self
    def __neg__(self):
        return self
    def __lt__(self, other):
        return True
    def __gt__(self, other):
        return True
    def __eq__(self, other):
        return True
    def run(self): pass
"""


def test_binary_operators_call_the_special_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        NUMBER
        + """
def use(a, b):
    (a + b).run()
    (1 + a)()
    -a
use(Number(), Number())
""",
    )

    assert callees(graph, "main.use") == [
        "main.Number.__add__",
        "main.Number.__neg__",
        "main.Number.__radd__",
        "main.Number.run",
        "main.f",
    ]


POWER = """
def f(): pass
class Power:
    def __pow__(self, exp, mod=None):
        return self
    def __rpow__(self, base, mod=None):
        return f
    def run(self): pass
"""


def test_pow_calls_what_the_power_operator_calls(tmp_path):
    graph = main_graph(
        tmp_path,
        POWER
        + """
def two(a):
    pow(a, 2).run()
    pow(2, a)()
def three(a):
    pow(a, 2, 5).run()
    pow(2, a, 5)()
def keywords(a):
    pow(2, exp=a, mod=5)()
two(Power())
three(Power())
keywords(Power())
""",
    )

    for caller in ("two", "three"):
        assert callees(graph, f"main.{caller}") == [
            "<builtin>.pow",
            "main.Power.__pow__",
            "main.Power.__rpow__",
            "main.Power.run",
            "main.f",
        ]
    assert callees(graph, "main.keywords") == [
        "<builtin>.pow",
        "main.Power.__rpow__",
        "main.f",
    ]


def test_pow_passes_the_modulus_to_both_methods(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def g(): pass
class Mod:
    def __call__(self): g()
class Power:
    def __pow__(self, exp, mod=None):
        mod()
    def __rpow__(self, base, mod=None):
        mod()
pow(Power(), 2, Mod())
pow(2, Power(), Mod())
""",
    )

    assert callees(graph, "main.Power.__pow__") == ["main.Mod.__call__"]
    assert callees(graph, "main.Power.__rpow__") == ["main.Mod.__call__"]


def test_inplace_operator_falls_back_to_the_binary_one(tmp_path):
    graph = main_graph(
        tmp_path,
        NUMBER
        + """
class Plain:
    def __add__(self, other):
        return self
def use(a, b):
    a += 1
    b += 1
use(Number(), Plain())
""",
    )

    assert callees(graph, "main.use") == ["main.Number.__iadd__", "main.Plain.__add__"]


def test_not_equal_falls_back_to_eq(tmp_path):
    graph = main_graph(
        tmp_path,
        NUMBER
        + """
class Distinct:
    def __eq__(self, other):
        return False
    def __ne__(self, other):
        return True
def use(a, b):
    a != b
use(Number(), Distinct())
""",
    )

    assert callees(graph, "main.use") == [
        "main.Distinct.__ne__",
        "main.Number.__eq__",
    ]


def test_comparisons_call_both_operands(tmp_path):
    graph = main_graph(
        tmp_path,
        NUMBER
        + """
class Bag:
    def __contains__(self, item):
        return True
def use(a, b):
    a < b
    a == 1
    a in Bag()
    a is b
use(Number(), Number())
""",
    )

    assert callees(graph, "main.use") == [
        "main.Bag.__contains__",
        "main.Number.__eq__",
        "main.Number.__gt__",
        "main.Number.__lt__",
    ]


def test_operator_chains_that_return_self_terminate(tmp_path):
    graph = main_graph(
        tmp_path,
        NUMBER
        + """
n = Number()
for _ in range(3):
    n = n + n + n
n.run()
""",
    )

    assert "main.Number.run" in callees(graph, "main")


def test_subscripts_on_instances(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class Table:
            def __getitem__(self, key):
                return f
            def __setitem__(self, key, value): pass
            def __delitem__(self, key): pass
        def use(table):
            table["a"]()
            table[1:2]
            table["b"] = 1
            del table["c"]
        use(Table())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.Table.__delitem__",
        "main.Table.__getitem__",
        "main.Table.__setitem__",
        "main.f",
    ]


def test_special_methods_outside_the_analysed_code_give_no_edges(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Mapping(dict):
            pass
        def use(m):
            m["a"] = 1
            m["a"] + 1
            str(m)
        use(Mapping())
        """,
    )

    assert callees(graph, "main.use") == ["<builtin>.str"]


def test_conversions_to_str(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Both:
            def __str__(self): return ""
            def __repr__(self): return ""
        class OnlyRepr:
            def __repr__(self): return ""
        class Formatted:
            def __format__(self, spec): return ""
        def as_str(both, only):
            str(both)
            print(only)
        def as_repr(both, only):
            repr(both)
            f"{only!r}"
        def as_format(both, formatted):
            f"{both}"
            format(formatted, "")
        as_str(Both(), OnlyRepr())
        as_repr(Both(), OnlyRepr())
        as_format(Both(), Formatted())
        """,
    )

    assert callees(graph, "main.as_str") == [
        "<builtin>.print",
        "<builtin>.str",
        "main.Both.__str__",
        "main.OnlyRepr.__repr__",
    ]
    assert callees(graph, "main.as_repr") == [
        "<builtin>.repr",
        "main.Both.__repr__",
        "main.OnlyRepr.__repr__",
    ]
    assert callees(graph, "main.as_format") == [
        "<builtin>.format",
        "main.Both.__str__",
        "main.Formatted.__format__",
    ]


def test_conversions_fall_back_to_repr_only_past_every_outside_str(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Text(str):
            def __repr__(self): return ""
        class Data(bytes):
            def __repr__(self): return ""
        class Buffer(bytearray):
            def __repr__(self): return ""
        class Failure(Exception):
            def __repr__(self): return ""
        class Number(int):
            def __repr__(self): return ""
        def convert(value):
            str(value)
            f"{value}"
            "{}".format(value)
        convert(Text("a"))
        convert(Data(b"a"))
        convert(Buffer(b"a"))
        convert(Failure())
        convert(Number(1))
        """,
    )

    assert [c for c in callees(graph, "main.convert") if c.startswith("main.")] == [
        "main.Number.__repr__"
    ]


def test_format_passes_the_format_spec_to_format_only(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def x(self): return ""
            def y(self): return ""
            def z(self): return ""
            def __format__(self, spec):
                return getattr(self, spec)()
        class D:
            def x(self): return ""
            def z(self): return ""
            def __str__(self, spec="z"):
                return getattr(self, spec)()
        format(C(), "x")
        f"{C():y}"
        f"{C()!r:z}"
        format(D(), "x")
        """,
    )

    assert callees(graph, "main.C.__format__") == [
        "<builtin>.getattr",
        "main.C.x",
        "main.C.y",
    ]
    assert callees(graph, "main.D.__str__") == ["<builtin>.getattr", "main.D.z"]


def test_format_without_a_spec_passes_the_empty_string(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def __format__(self, spec):
                return spec.upper()
        class B:
            def __format__(self, spec):
                return spec.lower()
        format(A())
        f"{B()}"
        """,
    )

    assert callees(graph, "main.A.__format__") == ["<builtin>.str.upper"]
    assert callees(graph, "main.B.__format__") == ["<builtin>.str.lower"]


def test_fstring_without_values_is_a_str_constant(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def x(self): pass
        getattr(C(), f"x")()
        """,
    )

    assert "main.C.x" in callees(graph, "main")


def test_len_calls_the_special_method(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Sized:
            def __len__(self): return 0
        len(Sized())
        """,
    )

    assert callees(graph, "main") == ["<builtin>.len", "main.Sized.__len__"]


def test_getattr_is_called_for_attributes_that_classes_do_not_define(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        class Proxy:
            def __getattr__(self, name):
                return f
            def known(self): pass
        def use(proxy):
            proxy.missing()
        def defined(proxy):
            proxy.known()
        use(Proxy())
        defined(Proxy())
        """,
    )

    assert callees(graph, "main.use") == ["main.Proxy.__getattr__", "main.f"]
    assert callees(graph, "main.defined") == ["main.Proxy.known"]


def test_getattr_and_setattr_with_constant_names(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f(): pass
        def g(): pass
        def h(): pass
        class C:
            def m(self): pass
            @property
            def p(self):
                return f
        def use(c, unknown):
            getattr(c, "m")()
            name = "m"
            getattr(c, name)()
            getattr(c, "missing", g)()
            setattr(c, "stored", h)
            c.stored()
            getattr(c, "p")()
            getattr(c, unknown)()
        use(C(), input())
        """,
    )

    assert callees(graph, "main.use") == [
        "<builtin>.getattr",
        "<builtin>.setattr",
        "main.C.m",
        "main.C.p",
        "main.f",
        "main.g",
        "main.h",
    ]


def test_getattr_default_and_setattr_hold_instances(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def m(self): pass
        class D:
            def m(self): pass
        class Holder:
            pass
        holder = Holder()
        setattr(holder, "x", C())
        holder.x.m()
        getattr(holder, "missing", D()).m()
        """,
    )

    assert callees(graph, "main") == [
        "<builtin>.getattr",
        "<builtin>.setattr",
        "main.C.m",
        "main.D.m",
    ]


def test_getattr_with_a_name_of_a_few_constants_only(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def a(self): pass
            def b(self): pass
            def c(self): pass
            def d(self): pass
            def e(self): pass
        def few(obj):
            for name in ("a", "b", "c", "d"):
                getattr(obj, name)()
        def many(obj):
            for name in ("a", "b", "c", "d", "e"):
                getattr(obj, name)()
        few(C())
        many(C())
        """,
    )

    assert callees(graph, "main.few") == [
        "<builtin>.getattr",
        "main.C.a",
        "main.C.b",
        "main.C.c",
        "main.C.d",
    ]
    assert callees(graph, "main.many") == ["<builtin>.getattr"]


def test_the_name_of_a_function_is_a_str_constant(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Cache:
            def get(self): pass
            def set(self): pass
            def clear(self): pass
        class Proxy:
            def __init__(self, cache): self.cache = cache
            def run(self, name): getattr(self.cache, name)()
        def renamed(): pass
        renamed.__name__ = "clear"
        def use(proxy):
            for command in (Cache.set, Cache().get):
                proxy.run(command.__name__)
            proxy.run(renamed.__name__)
            (lambda: None).__name__.upper()
        use(Proxy(Cache()))
        """,
    )

    assert callees(graph, "main.Proxy.run") == [
        "<builtin>.getattr",
        "main.Cache.clear",
        "main.Cache.get",
        "main.Cache.set",
    ]
    assert "<builtin>.str.upper" in callees(graph, "main.use")


def test_getattr_loads_the_constants_of_a_name_whatever_else_it_holds(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        class C:
            def a(self): pass
            def b(self): pass
            def c(self): pass
            def d(self): pass
            def e(self): pass
        def annotated(obj, option: str = "a"):
            getattr(obj, option)()
        def mixed(obj, flag):
            name = "b" if flag else ext.choose()
            setattr(obj, name, None)
            getattr(obj, name)()
        def unknown(obj, option: str):
            getattr(obj, option)()
        def many(obj, flag):
            for name in ("a", "b", "c", "d", "e", ext.choose()):
                getattr(obj, name)()
        annotated(C())
        mixed(C(), True)
        unknown(C(), ext.option)
        many(C(), True)
        """,
    )

    assert callees(graph, "main.annotated") == ["<builtin>.getattr", "main.C.a"]
    assert callees(graph, "main.mixed") == [
        "<builtin>.getattr",
        "<builtin>.setattr",
        "ext.choose",
        "main.C.b",
    ]
    assert callees(graph, "main.unknown") == ["<builtin>.getattr"]
    assert callees(graph, "main.many") == ["<builtin>.getattr", "ext.choose"]


def test_hasattr_runs_the_load(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            @property
            def ready(self):
                return True
        def check(c):
            return hasattr(c, "ready")
        check(C())
        """,
    )

    assert callees(graph, "main.check") == ["<builtin>.hasattr", "main.C.ready"]


def test_getattr_names_found_by_a_later_completion_round(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import ext
        def first(): pass
        def second(): pass
        class C:
            a = first
            b = second
            selector = "b"
        key = "selector"
        name = "a" if ext.flag else getattr(C, key)
        getattr(C, name)()
        """,
    )

    assert callees(graph, "main") == ["<builtin>.getattr", "main.first", "main.second"]


def test_stores_of_untracked_values_still_call_setters(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class C:
            def __setitem__(self, key, value): pass
            def change(self, value): pass
            def other(self, value): pass
            item = property(fset=change)
            flag = property(fset=other)
            noted = property(fset=other)
        def use(c):
            c[0] = None
            c.item = None
            c.item, c.flag = 1.5, True
        def make():
            return C()
        def key():
            return 0
        def annotate(c):
            c.noted: int
            make().noted: int
            c[key()]: int
        use(C())
        annotate(C())
        """,
    )

    assert callees(graph, "main.use") == [
        "main.C.__setitem__",
        "main.C.change",
        "main.C.other",
    ]
    assert callees(graph, "main.annotate") == ["main.key", "main.make"]


def test_rich_comparisons_return_what_their_special_method_returns(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def target(): pass
        def other(): pass
        def reflected(): pass
        class C:
            def __eq__(self, o):
                return target
            def __lt__(self, o):
                return other
        class D:
            def __gt__(self, o):
                return reflected
        def use():
            (C() == 1)()
            (C() < C() < C())()
            (1 < D())()
        """,
    )

    assert callees(graph, "main.use") == [
        "main.C.__eq__",
        "main.C.__lt__",
        "main.D.__gt__",
        "main.other",
        "main.reflected",
        "main.target",
    ]


def test_a_dict_subclass_calls_missing_where_dict_getitem_runs(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Defaults(dict):
    def __missing__(self, key):
        return key
class Own(dict):
    def __getitem__(self, key):
        return key
    def __missing__(self, key):
        return key
def use(a, b):
    a["x"]
    a.get("y")
    b["x"]
use(Defaults(), Own())
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.dict.get",
        "main.Defaults.__missing__",
        "main.Own.__getitem__",
    ]


def test_percent_formatting_converts_its_items(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Value:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Named:
    def __str__(self): return "n"
class Number:
    def __str__(self): return "x"
def use(v, n, w):
    "%s and %r" % (v, v)
    "%(name)s" % {"name": n}
    "%d%%" % w
use(Value(), Named(), Number())
""",
    )

    assert callees(graph, "main.use") == [
        "main.Named.__str__",
        "main.Value.__repr__",
        "main.Value.__str__",
    ]


def test_percent_formatting_converts_by_the_formats_that_the_left_operand_holds(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
class Value:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Shown:
    def __repr__(self): return "r"
class Added:
    def __repr__(self): return "r"
MESSAGE = "%r is shown"
def use(v, s, a, flag):
    msg = "%s here" if flag else "%r there"
    msg % (v,)
    MESSAGE % s
    text = "%r"
    text %= (a,)
use(Value(), Shown(), Added(), True)
""",
    )

    assert callees(graph, "main.use") == [
        "main.Added.__repr__",
        "main.Shown.__repr__",
        "main.Value.__repr__",
        "main.Value.__str__",
    ]


def test_percent_of_a_value_that_is_no_str_constant_converts_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Item:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Formatter:
    def __mod__(self, other): return "m"
def use(item, unknown):
    Formatter() % item
    7 % item
    b"%s" % (item,)
    unknown % (item,)
    ("%" + unknown) % (item,)
use(Item(), None)
""",
    )

    assert callees(graph, "main.use") == ["main.Formatter.__mod__"]


CONTAINER_ELEMENTS = """
class Element:
    def __str__(self): return "s"
    def __repr__(self): return "r"
    def __format__(self, spec): return "f"
class Key:
    def __hash__(self): return 0
    def __repr__(self): return "k"
class Inner:
    def __repr__(self): return "i"
def convert(xs):
    {conversion}
convert({value})
"""


def converted(tmp_path, conversion, value):
    graph = main_graph(
        tmp_path, CONTAINER_ELEMENTS.format(conversion=conversion, value=value)
    )
    return [c for c in callees(graph, "main.convert") if c.startswith("main.")]


def test_a_conversion_of_a_builtin_container_converts_its_elements_with_repr(
    tmp_path,
):
    for index, (conversion, value) in enumerate(
        [
            ("repr(xs)", "[Element()]"),
            ("str(xs)", "(Element(),)"),
            ("print(xs)", "{Element()}"),
            ('f"{xs}"', "frozenset([Element()])"),
            ('f"{xs!s}"', "[Element()]"),
            ('format(xs, "")', "[Element()]"),
            ('"%s" % (xs,)', "[Element()]"),
        ]
    ):
        assert converted(tmp_path / str(index), conversion, value) == [
            "main.Element.__repr__"
        ], conversion


def test_percent_of_one_container_that_is_no_tuple_converts_it_whole(tmp_path):
    for index, (conversion, value, expected) in enumerate(
        [
            ('"%s" % xs', "[Element()]", "__repr__"),
            ('"%r" % xs', "{Element()}", "__repr__"),
            ('"%s" % xs', "frozenset([Element()])", "__repr__"),
            ('"%s" % xs', "{Element(): 1}", "__repr__"),
            ('"%s" % xs', "{1: Element()}", "__repr__"),
            ('"%s" % xs', "(Element(),)", "__str__"),
            ('"%(a)s" % xs', '{"a": Element()}', "__str__"),
        ]
    ):
        assert converted(tmp_path / str(index), conversion, value) == [
            f"main.Element.{expected}"
        ], (conversion, value)


def test_percent_gives_a_value_that_is_no_tuple_to_its_first_item_only(tmp_path):
    for index, (conversion, value, expected) in enumerate(
        [
            ('"%*s" % xs', "[Element()]", []),
            ('"%.*s" % xs', "[Element()]", []),
            ('"%d%s" % xs', "[Element()]", []),
            ('"%c" % xs', "[Element()]", []),
            ('"%d%s" % xs', "Element()", []),
            ('"%*s" % xs', "Element()", []),
            ('"%(a)s%s" % xs', '{"a": Element()}', ["__str__"]),
            ('"%s%s" % xs', "[Element()]", ["__repr__"]),
            ('"%s %d" % xs', "[Element()]", ["__repr__"]),
            ('"%%%s" % xs', "[Element()]", ["__repr__"]),
            ('"%s%s" % xs', "Element()", ["__str__"]),
            ('"%s%(a)s" % xs', '{"a": Element()}', ["__repr__", "__str__"]),
        ]
    ):
        assert converted(tmp_path / str(index), conversion, value) == [
            f"main.Element.{name}" for name in expected
        ], (conversion, value)


PERCENT_FIELDS_THAT_PYTHON_ACCEPTS = [
    ('"%.s" % xs', "[Element()]", ["Element.__repr__"]),
    ('"%5.s %r" % xs', "(Element(), Inner())", ["Element.__str__", "Inner.__repr__"]),
    ('"%((a))s" % xs', '{"(a)": Element()}', ["Element.__str__"]),
    ('"%(a(b)c)r" % xs', '{"a(b)c": Element()}', ["Element.__repr__"]),
    ('"%ls %Ls" % xs', "(Element(), Inner())", ["Element.__str__", "Inner.__repr__"]),
]
PERCENT_FIELDS_THAT_PYTHON_REJECTS_STOP_THE_CONVERSIONS = [
    ('"%(a)*s" % xs', '{"a": Element()}', []),
    ('"%(a).*s" % xs', '{"a": Element()}', []),
    ('"%(a)s%(b)*s%(c)r" % xs', '{"a": Element(), "c": Inner()}', ["Element.__str__"]),
    ('"%((a)s" % xs', '{"(a": Element()}', []),
    ('"%s %y %r" % xs', "(Element(), 1, Inner())", ["Element.__str__"]),
    ('"%s %5% %r" % xs', "(Element(), Inner())", ["Element.__str__"]),
    ('"%lls" % xs', "(Element(),)", []),
    ('"%r %" % xs', "(Element(),)", ["Element.__repr__"]),
]
PERCENT_FIELDS_WITHOUT_A_FITTING_ITEM_STOP_THE_CONVERSIONS = [
    ('"%s %(a)s %r" % xs', "(Element(), 1, Inner())", ["Element.__str__"]),
    ('"%(a)s %r" % xs', '{"a": Element()}', ["Element.__str__"]),
    ('"%d%(a)s" % xs', '{"a": Element()}', []),
]
PERCENT_SYNTAX = [
    *PERCENT_FIELDS_THAT_PYTHON_ACCEPTS,
    *PERCENT_FIELDS_THAT_PYTHON_REJECTS_STOP_THE_CONVERSIONS,
    *PERCENT_FIELDS_WITHOUT_A_FITTING_ITEM_STOP_THE_CONVERSIONS,
]


PERCENT_BYTES_CONVERSIONS = [
    ('b"%r" % xs', "(Element(),)", ["Element.__repr__"]),
    ('b"%a" % xs', "[Element()]", ["Element.__repr__"]),
    ('b"%s %r" % xs', '(b"x", Inner())', ["Inner.__repr__"]),
    ('b"%b %a" % xs', '(b"x", Inner())', ["Inner.__repr__"]),
    ('b"%(a)r" % xs', '{b"a": Element()}', ["Element.__repr__"]),
    ('b"%((a))r" % xs', '{b"(a)": Element()}', ["Element.__repr__"]),
]
PERCENT_BYTES_WITH_STR_KEYS_OR_REJECTED_FIELDS = [
    ('b"%(a)r" % xs', '{"a": Element()}', []),
    ('b"%y %r" % xs', "(1, Inner())", []),
    ('b"%(a)*r" % xs', '{b"a": Element()}', []),
    ('b"%s" % xs', "(Element(),)", []),
]
PERCENT_BYTES = [
    *PERCENT_BYTES_CONVERSIONS,
    *PERCENT_BYTES_WITH_STR_KEYS_OR_REJECTED_FIELDS,
]


@pytest.mark.parametrize("conversion, value, expected", PERCENT_BYTES)
def test_percent_of_bytes_converts_with_repr(tmp_path, conversion, value, expected):
    assert converted(tmp_path, conversion, value) == [
        f"main.{name}" for name in expected
    ]


WIDTH_MAX, PRECISION_MAX = 2**63 - 1, 2**31 - 1
PERCENT_BOUNDS = [
    (f"%{WIDTH_MAX}s", True),
    (f"%{WIDTH_MAX + 1}s", False),
    (f"%.{PRECISION_MAX}s", True),
    (f"%.{PRECISION_MAX + 1}s", False),
    (f"%000{WIDTH_MAX}.000{PRECISION_MAX}s", True),
    (f"%{'9' * 5000}s", False),
    (f"%.{'9' * 5000}s", False),
    (f"%{WIDTH_MAX}r".encode(), True),
    (f"%{WIDTH_MAX + 1}r".encode(), False),
    (f"%.{PRECISION_MAX}r".encode(), True),
    (f"%.{PRECISION_MAX + 1}r".encode(), False),
]


class _Converted(Exception):
    pass


class _ItemWhoseConversionRaises:
    def __str__(self):
        raise _Converted

    __repr__ = __str__


@pytest.mark.parametrize("fmt, accepted", PERCENT_BOUNDS)
def test_the_bounds_of_widths_and_precisions_are_those_of_python(fmt, accepted):
    if accepted and sys.maxsize != WIDTH_MAX and str(WIDTH_MAX) in str(fmt):
        pytest.skip("PY_SSIZE_T_MAX of this Python is not 2**63 - 1")
    error = _Converted if accepted else ValueError
    with pytest.raises(error):
        fmt % (_ItemWhoseConversionRaises(),)


@pytest.mark.parametrize("fmt, accepted", PERCENT_BOUNDS)
def test_percent_converts_nothing_from_a_width_or_precision_past_its_bound(
    tmp_path, fmt, accepted
):
    method = "__repr__" if fmt[-1:] in ("r", b"r") else "__str__"
    expected = [f"main.Element.{method}"] if accepted else []
    assert converted(tmp_path, f"{fmt!r} % xs", "(Element(),)") == expected
    text = fmt.decode() if isinstance(fmt, bytes) else fmt
    marked = f"%r {text} %r"
    if isinstance(fmt, bytes):
        marked = marked.encode()
    found = converted(
        tmp_path / "around", f"{marked!r} % xs", "(Inner(), Element(), Key())"
    )
    assert ("main.Key.__repr__" in found) == accepted
    assert "main.Inner.__repr__" in found


@pytest.mark.parametrize("conversion, value, expected", PERCENT_SYNTAX)
def test_percent_reads_the_format_as_python_does(tmp_path, conversion, value, expected):
    assert converted(tmp_path, conversion, value) == [
        f"main.{name}" for name in expected
    ]


def test_a_dict_converts_its_keys_and_values_and_nested_containers_theirs(
    tmp_path,
):
    assert converted(tmp_path / "dict", "repr(xs)", "{Key(): [(Inner(),)]}") == [
        "main.Inner.__repr__",
        "main.Key.__repr__",
    ]
    assert converted(
        tmp_path / "cycle", "xs.append(xs)\n    repr(xs)", "[Inner()]"
    ) == ["main.Inner.__repr__"]


def test_a_value_that_is_no_builtin_container_does_not_convert_its_elements(
    tmp_path,
):
    for index, value in enumerate(["(x for x in [Inner()])", "Element()"]):
        found = converted(tmp_path / str(index), "repr(xs)", value)
        assert "main.Inner.__repr__" not in found, value


def test_an_iterator_of_a_container_does_not_convert_its_elements(tmp_path):
    assert converted(tmp_path, "repr(iter(xs))", "[Inner()]") == []


def test_percent_formatting_skips_the_items_that_star_widths_take(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Shown:
    def __str__(self): return "s"
    def __repr__(self): return "r"
class Quoted:
    def __str__(self): return "s"
    def __repr__(self): return "r"
def width(s):
    "%*s" % (8, s)
def both(q):
    "%-*.*r" % (8, 2, q)
def mixed(s, q):
    "%.*s %r" % (2, s, q)
width(Shown())
both(Quoted())
mixed(Shown(), Quoted())
""",
    )

    assert callees(graph, "main.width") == ["main.Shown.__str__"]
    assert callees(graph, "main.both") == ["main.Quoted.__repr__"]
    assert callees(graph, "main.mixed") == [
        "main.Quoted.__repr__",
        "main.Shown.__str__",
    ]


def test_str_format_converts_and_loads_its_fields(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Money:
    def __format__(self, spec): return "1"
class User:
    @property
    def name(self): return "ada"
    def __repr__(self): return "u"
def use(m, u):
    "{:>8} {}".format(m, u.name)
    "{0.name} {who!r}".format(u, who=u)
use(Money(), User())
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.str.format",
        "main.Money.__format__",
        "main.User.__repr__",
        "main.User.name",
    ]


def test_str_format_reads_an_index_of_any_length(tmp_path):
    zeros, ones = "0" * 5000, "1" * 5000
    graph = main_graph(
        tmp_path,
        f"""
class First:
    def __format__(self, spec): return ""
class Second:
    def __format__(self, spec): return ""
class Never:
    def __format__(self, spec): return ""
def use(first, second, never):
    "{{{zeros}}}".format(first)
    "{{{zeros}1}}".format(never, second)
    "{{{ones}}}".format(never)
use(First(), Second(), Never())
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.str.format",
        "main.First.__format__",
        "main.Second.__format__",
    ]


def test_dict_keys_are_hashed_and_compared_with_other_keys(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
class Other:
    def __hash__(self): return 2
    def __eq__(self, other): return True
def same():
    key = Key()
    table = {key: 1}
    table[key]
def equal():
    table = {Key(): 1}
    table[Key()]
def stored():
    table = {}
    table[Other()] = 1
same()
equal()
stored()
""",
    )

    assert callees(graph, "main.same") == ["main.Key.__hash__"]
    assert callees(graph, "main.equal") == ["main.Key.__eq__", "main.Key.__hash__"]
    assert callees(graph, "main.stored") == ["main.Other.__hash__"]


@pytest.mark.parametrize(
    "lookup, methods",
    [
        ("table.get(Key())", ["<builtin>.dict.get"]),
        ("table.pop(Key(), None)", ["<builtin>.dict.pop"]),
        ("table.setdefault(Key(), 2)", ["<builtin>.dict.setdefault"]),
        (
            "ordered = collections.OrderedDict(table)\nordered.move_to_end(Key())",
            ["collections.OrderedDict", "collections.OrderedDict.move_to_end"],
        ),
    ],
)
def test_lookup_methods_of_a_dict_hash_and_compare_the_key(tmp_path, lookup, methods):
    graph = main_graph(
        tmp_path,
        """
import collections
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def look(table):
    """
        + lookup.replace("\n", "\n    ")
        + """
look({Key(): 1})
""",
    )

    assert callees(graph, "main.look") == [
        *methods,
        "main.Key.__eq__",
        "main.Key.__hash__",
    ]


def test_a_lookup_compares_a_stored_key_with_any_searched_object(tmp_path):
    graph = main_graph(
        tmp_path,
        """
def f(): pass
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
class FunctionKey:
    def __hash__(self): return hash(f)
    def __eq__(self, other): return True
class Plain:
    pass
def constant():
    table = {Key(): 0}
    table.get(1)
def subscript():
    table = {Key(): 0}
    table[1]
def function():
    table = {FunctionKey(): 0}
    table.pop(f, None)
def same():
    key = Key()
    table = {key: 0}
    table.get(key)
def no_eq():
    table = {Plain(): 0, 1: 0}
    table.get(1)
constant()
subscript()
function()
same()
no_eq()
""",
    )

    assert callees(graph, "main.constant") == [
        "<builtin>.dict.get",
        "main.Key.__eq__",
        "main.Key.__hash__",
    ]
    assert callees(graph, "main.subscript") == ["main.Key.__eq__", "main.Key.__hash__"]
    assert callees(graph, "main.function") == [
        "<builtin>.dict.pop",
        "main.FunctionKey.__eq__",
        "main.FunctionKey.__hash__",
    ]
    assert callees(graph, "main.same") == ["<builtin>.dict.get", "main.Key.__hash__"]
    assert callees(graph, "main.no_eq") == ["<builtin>.dict.get"]


def test_membership_in_a_dict_hashes_the_key(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Key:
    def __hash__(self): return 1
def member(key, table, items):
    return key in table, key in items
member(Key(), {}, [])
""",
    )

    assert callees(graph, "main.member") == ["main.Key.__hash__"]


def test_lookup_methods_of_other_objects_hash_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Key:
    def __hash__(self): return 1
class Table:
    def get(self, key): pass
[Key()].pop(0)
Table().get(Key())
""",
    )

    assert callees(graph, "main") == ["<builtin>.list.pop", "main.Table.get"]


KEYS = """
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
"""


@pytest.mark.parametrize(
    "use",
    [
        "{Key(), Key()}",
        "{key for key in (Key(), Key())}",
        "{key: 1 for key in (Key(), Key())}",
        "{Key(): 1, Key(): 2}",
        "set([Key(), Key()])",
        "frozenset([Key(), Key()])",
        "dict.fromkeys([Key(), Key()])",
        "dict([(Key(), 1), (Key(), 2)])",
        "collections.Counter([Key(), Key()])",
        "table = {Key(): 1}\ntable[Key()] = 2",
        "table = {Key(): 1}\ndel table[Key()]",
        "table = {Key(): 1}\ntable.update([(Key(), 2)])",
        "keys = {Key()}\nkeys.add(Key())",
        "keys = {Key()}\nkeys.update([Key()])",
        "keys = {Key()}\nkeys.remove(Key())",
        "keys = {Key()}\nkeys.discard(Key())",
        "keys = {Key()}\nkeys.union([Key()])",
        "keys = {Key()}\nkeys.intersection([Key()])",
        "keys = {Key()}\nkeys.difference_update([Key()])",
        "keys = {Key()}\nkeys.issubset([Key()])",
        "keys = frozenset([Key()])\nkeys.isdisjoint([Key()])",
        "keys = {Key()}\nKey() in keys",
    ],
)
def test_builtins_that_store_or_look_up_a_key_hash_and_compare_it(tmp_path, use):
    graph = main_graph(
        tmp_path,
        "import collections\n"
        + KEYS
        + "def use():\n    "
        + use.replace("\n", "\n    ")
        + "\nuse()\n",
    )

    assert {"main.Key.__eq__", "main.Key.__hash__"} <= set(callees(graph, "main.use"))


@pytest.mark.parametrize(
    "use",
    [
        "{Key()}",
        "set([Key()])",
        "table = {}\ntable[Key()] = 1",
        "keys = set()\nkeys.add(Key())",
    ],
)
def test_one_key_is_hashed_and_compared_with_no_other(tmp_path, use):
    graph = main_graph(
        tmp_path,
        KEYS + "def use():\n    " + use.replace("\n", "\n    ") + "\nuse()\n",
    )

    assert "main.Key.__hash__" in callees(graph, "main.use")
    assert "main.Key.__eq__" not in callees(graph, "main.use")


@pytest.mark.parametrize(
    "use",
    [
        "set(keys)",
        "frozenset(keys)",
        "set(table)",
        "dict(table)",
        "dict.fromkeys(table)",
        "{**table}",
    ],
)
def test_keys_from_a_set_or_dict_keep_their_hash(tmp_path, use):
    graph = main_graph(
        tmp_path,
        KEYS
        + "keys = {Key()}\ntable = {Key(): 1}\n"
        + "def use(keys, table):\n    "
        + use
        + "\nuse(keys, table)\n",
    )

    assert "main.Key.__hash__" not in callees(graph, "main.use")


def test_python_reuses_the_hashes_of_sets_and_of_dicts_that_iterate_as_dict(
    tmp_path,
):
    uses = {
        "kept": [
            "{*keys}",
            "{*table}",
            "keys.union(table)",
            "collections.Counter(table)",
            "{**counts}",
        ],
        "hashed": [
            "{*items}",
            "{*ordered}",
            "set(ordered)",
            "set(counts)",
            "dict.fromkeys(ordered)",
            "{**ordered}",
            "dict(ordered)",
            "{}.update(ordered)",
            "collections.Counter(keys)",
        ],
    }
    source = (
        "import collections\n"
        + KEYS
        + "items = [Key()]\nkeys = {Key()}\ntable = {Key(): 1}\n"
        + "ordered = collections.OrderedDict([(Key(), 1)])\n"
        + "counts = collections.Counter([Key()])\n"
    )
    for group, codes in uses.items():
        for index, code in enumerate(codes):
            source += f"def {group}{index}():\n    {code}\n{group}{index}()\n"
    graph = main_graph(tmp_path, source)

    for group, codes in uses.items():
        for index, code in enumerate(codes):
            hashes = "main.Key.__hash__" in callees(graph, f"main.{group}{index}")
            assert hashes == (group == "hashed"), code


def test_equal_dicts_and_sets_compare_their_keys_and_values(tmp_path):
    graph = main_graph(
        tmp_path,
        KEYS
        + """
class Value:
    def __eq__(self, other): return True
def dicts(a, b):
    return a == b
def sets(a, b):
    return a != b
dicts({Key(): Value()}, {Key(): Value()})
sets({Key()}, frozenset([Key()]))
""",
    )

    assert callees(graph, "main.dicts") == ["main.Key.__eq__", "main.Value.__eq__"]
    assert callees(graph, "main.sets") == ["main.Key.__eq__"]


def test_compared_sequences_compare_their_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Item:
    def __eq__(self, other): return False
    def __lt__(self, other): return False
    def __le__(self, other): return False
def equal(a, b):
    return a == b
def less(a, b):
    return a < b
def nested(a, b):
    return a <= b
def other(a):
    return a == 1
equal([Item()], [Item()])
less((1, Item()), (1, Item()))
nested(((Item(),),), ((Item(),),))
other((Item(),))
""",
    )

    assert callees(graph, "main.equal") == ["main.Item.__eq__"]
    assert callees(graph, "main.less") == ["main.Item.__eq__", "main.Item.__lt__"]
    assert callees(graph, "main.nested") == []
    assert callees(graph, "main.other") == []


def test_containers_compare_elements_only_with_containers_of_their_family(
    tmp_path,
):
    cases = [
        ("[a] == (b,)", []),
        ("collections.deque([a]) == [b]", []),
        ("[[a]] == [(b,)]", []),
        ("[a] < (b,)", []),
        ("{1: a} < {1: b}", []),
        ("[(a,)] == [(b,)]", []),
        ("collections.deque([a]) == collections.deque([b])", ["main.Item.__eq__"]),
        (
            "collections.deque([a]) < collections.deque([b])",
            ["main.Item.__eq__", "main.Item.__lt__"],
        ),
        ("[(a,)] < [(b,)]", []),
        ("[{1: a}] < [{1: b}]", []),
        ("({a},) < ({b},)", ["main.Item.__hash__"]),
        ("{a} <= frozenset([b])", ["main.Item.__eq__", "main.Item.__hash__"]),
        (
            "{a: 1} == collections.OrderedDict([(b, 1)])",
            ["main.Item.__eq__", "main.Item.__hash__"],
        ),
    ]
    source = """
import collections
class Item:
    def __hash__(self): return 1
    def __eq__(self, other): return False
    def __lt__(self, other): return False
"""
    for index, (compared, _) in enumerate(cases):
        source += (
            f"def compare{index}(a, b):\n"
            f"    try:\n        {compared}\n    except TypeError:\n        pass\n"
            f"compare{index}(Item(), Item())\n"
        )
    graph = main_graph(tmp_path, source)

    for index, (compared, methods) in enumerate(cases):
        called = callees(graph, f"main.compare{index}")
        assert [c for c in called if c.startswith("main.")] == methods, compared


@pytest.mark.parametrize("operator", ["<", ">"])
def test_limit_a_strict_subset_test_compares_keys_whatever_the_sizes(
    tmp_path, operator
):
    graph = main_graph(
        tmp_path,
        f"""
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return False
def compare(a, b):
    return {{a}} {operator} {{b}}
compare(Key(), Key())
""",
    )

    assert callees(graph, "main.compare") == ["main.Key.__eq__", "main.Key.__hash__"]


def test_limit_a_set_method_reuses_the_hashes_of_any_dict(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Key:
    def __hash__(self): return 0
source = {Key(): 1}
def use():
    set().intersection(source)
use()
""",
    )

    assert callees(graph, "main.use") == ["<builtin>.set", "<builtin>.set.intersection"]


def test_builtins_that_order_sequences_compare_their_elements(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Item:
    def __eq__(self, other): return False
    def __lt__(self, other): return False
    def __gt__(self, other): return False
def use(pairs):
    pairs.sort()
    sorted(pairs)
    min(pairs)
def largest(pairs):
    return max(pairs)
use([(1, Item()), (2, Item())])
largest([(1, Item()), (2, Item())])
""",
    )

    assert callees(graph, "main.use") == [
        "<builtin>.list.sort",
        "<builtin>.min",
        "<builtin>.sorted",
        "main.Item.__eq__",
        "main.Item.__lt__",
    ]
    assert callees(graph, "main.largest") == [
        "<builtin>.max",
        "main.Item.__eq__",
        "main.Item.__gt__",
    ]


def test_list_asks_the_length_of_what_it_copies(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
    def __length_hint__(self): return 0
class Hinted:
    def __iter__(self): return iter([])
    def __length_hint__(self): return 0
def copy(items):
    list(items)
def extend(items):
    [].extend(items)
def as_tuple(items):
    tuple(items)
copy(Sized())
copy(Hinted())
extend(Sized())
as_tuple(Sized())
""",
    )

    assert callees(graph, "main.copy") == [
        "<builtin>.list",
        "main.Hinted.__iter__",
        "main.Hinted.__length_hint__",
        "main.Sized.__iter__",
        "main.Sized.__len__",
    ]
    assert callees(graph, "main.extend") == [
        "<builtin>.list.extend",
        "main.Sized.__iter__",
        "main.Sized.__len__",
    ]
    assert callees(graph, "main.as_tuple") == [
        "<builtin>.tuple",
        "main.Sized.__iter__",
        "main.Sized.__len__",
    ]


LENGTH_HINTED = """
import ext
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
class Hinted:
    def __iter__(self): return iter([])
    def __length_hint__(self): return 0
def f(*args): pass
"""


def length_hints(graph, caller):
    return [c for c in callees(graph, caller) if c.endswith(("__len__", "_hint__"))]


@pytest.mark.parametrize(
    "call",
    [
        "sorted(x)",
        "[*x]",
        "(*x,)",
        "[0, *x]",
        "bytes(x)",
        "bytearray().extend(x)",
        "f(*x)",
        "f(1, *x)",
        "f(*x, *[])",
        "f(*x, 1)",
        "print(*x)",
        "missing(*x)",
        "ext.call(*x)",
    ],
)
def test_builtins_and_unpacking_ask_the_length_of_what_they_get(tmp_path, call):
    graph = main_graph(
        tmp_path,
        LENGTH_HINTED
        + f"""
def use(x):
    {call}
use(Sized())
use(Hinted())
""",
    )

    assert length_hints(graph, "main.use") == [
        "main.Hinted.__length_hint__",
        "main.Sized.__len__",
    ]


def test_a_list_extended_in_place_asks_the_length_of_what_it_gets(tmp_path):
    graph = main_graph(
        tmp_path,
        LENGTH_HINTED
        + """
def use(x):
    items = []
    items += x
use(Sized())
use(Hinted())
""",
    )

    assert length_hints(graph, "main.use") == [
        "main.Hinted.__length_hint__",
        "main.Sized.__len__",
    ]


@pytest.mark.parametrize(
    "call",
    [
        "set(x)",
        "frozenset(x)",
        "{*x}",
        "bytearray(x)",
        "collections.deque(x)",
        "dict.fromkeys(x)",
        "min(x)",
        "max(x)",
        "sum(x)",
        "zip(x)",
        "enumerate(x)",
        "map(str, x)",
        "for item in x: pass",
    ],
)
def test_iterating_alone_asks_no_length(tmp_path, call):
    graph = main_graph(
        tmp_path,
        "import collections\n"
        + LENGTH_HINTED
        + f"""
def use(x):
    {call}
use(Sized())
use(Hinted())
""",
    )

    assert length_hints(graph, "main.use") == []


def test_bytes_asks_no_length_of_what_converts_otherwise(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Index:
    def __index__(self): return 1
    def __iter__(self): return iter([])
    def __len__(self): return 0
class Convertible:
    def __bytes__(self): return b""
    def __iter__(self): return iter([])
    def __len__(self): return 0
def use(x):
    bytes(x)
use(Index())
use(Convertible())
""",
    )

    assert length_hints(graph, "main.use") == []


JOINED = """
class Itself:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __len__(self): return 0
class Hinted:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __length_hint__(self): return 0
class Inner:
    def __iter__(self): return self
    def __next__(self): raise StopIteration
    def __len__(self): return 0
class Outer:
    def __iter__(self): return Inner()
    def __len__(self): return 0
class Builtin:
    def __iter__(self): return iter([])
    def __len__(self): return 0
"""


@pytest.mark.parametrize("join", ['"".join', 'b"".join', "bytearray().join"])
def test_join_asks_the_length_of_the_iterator_of_its_argument(tmp_path, join):
    graph = main_graph(
        tmp_path,
        JOINED
        + f"""
def itself(x):
    {join}(x)
def other(x):
    {join}(x)
def builtin(x):
    {join}(x)
itself(Itself())
itself(Hinted())
other(Outer())
builtin(Builtin())
""",
    )

    assert length_hints(graph, "main.itself") == [
        "main.Hinted.__length_hint__",
        "main.Itself.__len__",
    ]
    assert length_hints(graph, "main.other") == ["main.Inner.__len__"]
    assert length_hints(graph, "main.builtin") == []


def test_conditions_test_truth_with_bool_else_len(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Flag:
    def __bool__(self): return False
    def __len__(self): return 1
class Queue:
    def __len__(self): return 0
def branch(f):
    if f:
        pass
def loop(q):
    while q:
        break
def negate(f):
    return not f
def operands(f, q):
    return f and q
def arm(q):
    return 1 if q else 2
def check(q):
    assert q
def keep(f):
    return [i for i in [1] if f]
for f, q in [(Flag(), Queue())]:
    branch(f)
    loop(q)
    negate(f)
    operands(f, q)
    arm(q)
    check(q)
    keep(f)
""",
    )

    flag, queue = ["main.Flag.__bool__"], ["main.Queue.__len__"]
    assert callees(graph, "main.branch") == flag
    assert callees(graph, "main.loop") == queue
    assert callees(graph, "main.negate") == flag
    assert callees(graph, "main.operands") == flag
    assert callees(graph, "main.arm") == queue
    assert callees(graph, "main.check") == queue
    assert callees(graph, "main.keep") == flag


def test_a_comparison_chain_tests_the_truth_of_each_result_but_the_last(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Tested:
    def __bool__(self): return True
class Untested:
    def __bool__(self): return True
class Low:
    def __lt__(self, other): return Tested()
class High:
    def __lt__(self, other): return Untested()
def chain(a, b, c):
    a < b < c
def condition(a, b, c):
    if a < b < c:
        pass
def contains(a, b, c):
    a < b in c
chain(Low(), High(), High())
condition(Low(), High(), High())
contains(Low(), High(), [1])
""",
    )

    assert callees(graph, "main.chain") == [
        "main.High.__lt__",
        "main.Low.__lt__",
        "main.Tested.__bool__",
    ]
    assert callees(graph, "main.condition") == [
        "main.High.__lt__",
        "main.Low.__lt__",
        "main.Tested.__bool__",
        "main.Untested.__bool__",
    ]
    assert callees(graph, "main.contains") == [
        "main.Low.__lt__",
        "main.Tested.__bool__",
    ]


def test_in_and_value_patterns_test_the_truth_of_what_they_compare(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Truth:
    def __bool__(self): return True
class Box:
    def __contains__(self, item): return Truth()
class Value:
    def __eq__(self, other): return Truth()
class Holder:
    value = Value()
def contains(box):
    1 not in box
def pattern(value):
    match value:
        case Holder.value:
            pass
contains(Box())
pattern(Value())
""",
    )

    assert callees(graph, "main.contains") == [
        "main.Box.__contains__",
        "main.Truth.__bool__",
    ]
    assert callees(graph, "main.pattern") == [
        "main.Truth.__bool__",
        "main.Value.__eq__",
    ]


@pytest.mark.parametrize("call", ["bytes(x)", "bytearray().extend(x)"])
def test_a_buffer_is_read_without_asking_its_length(tmp_path, call):
    graph = main_graph(
        tmp_path,
        f"""
import array
class Mutable(bytearray):
    def __len__(self): return 0
class Frozen(bytes):
    def __len__(self): return 0
class View(array.array):
    def __len__(self): return 0
class Exporter:
    def __buffer__(self, flags): return memoryview(b"x")
    def __iter__(self): return iter([65])
    def __len__(self): return 0
class Sized:
    def __iter__(self): return iter([65])
    def __len__(self): return 0
def use(x):
    {call}
use(Mutable(b"x"))
use(Frozen(b"x"))
use(View("b", [1]))
use(Exporter())
use(Sized())
""",
    )

    assert length_hints(graph, "main.use") == ["main.Sized.__len__"]


UNPACKED = """
class Itself:
    def __init__(self): self.left = 3
    def __iter__(self): return self
    def __next__(self):
        if self.left == 0:
            raise StopIteration
        self.left -= 1
        return 1
    def __len__(self): return self.left
class Outer:
    def __iter__(self): return Itself()
    def __len__(self): return 3
"""


@pytest.mark.parametrize("target", ["a, *b", "*a, b", "[a, *b]"])
def test_a_starred_target_asks_the_length_of_the_iterator(tmp_path, target):
    graph = main_graph(
        tmp_path,
        UNPACKED
        + f"""
def itself(x):
    {target} = x
def other(x):
    {target} = x
itself(Itself())
other(Outer())
""",
    )

    assert length_hints(graph, "main.itself") == ["main.Itself.__len__"]
    assert length_hints(graph, "main.other") == ["main.Itself.__len__"]


def test_ordinary_unpacking_asks_no_length(tmp_path):
    graph = main_graph(
        tmp_path,
        UNPACKED
        + """
def use(x):
    a, b, c = x
use(Itself())
use(Outer())
""",
    )

    assert "main.Itself.__next__" in callees(graph, "main.use")
    assert length_hints(graph, "main.use") == []


@pytest.mark.parametrize(
    ("call", "method"),
    [
        ("int(x)", "__int__"),
        ("float(x)", "__float__"),
        ("complex(x)", "__complex__"),
    ],
)
def test_a_buffer_subclass_still_converts_through_its_own_method(
    tmp_path, call, method
):
    graph = main_graph(
        tmp_path,
        f"""
class Data(bytearray):
    def __int__(self): return 1
    def __float__(self): return 1.0
    def __complex__(self): return 1j
    def __bytes__(self): return b""
    def __len__(self): return 0
def use(x):
    {call}
use(Data(b"1"))
""",
    )

    assert f"main.Data.{method}" in callees(graph, "main.use")
    assert length_hints(graph, "main.use") == []


SEQUENCES = """
class Seq:
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
class Hinted:
    def __getitem__(self, index):
        raise IndexError
    def __length_hint__(self): return 0
def f(*args): pass
"""


@pytest.mark.parametrize(
    "statement",
    [
        "*rest, = x",
        "a, *b = x",
        '"".join(x)',
        "list(iter(x))",
        "f(*iter(x))",
        "sorted(iter(x))",
    ],
)
def test_a_sequence_iterator_asks_the_length_of_its_sequence(tmp_path, statement):
    graph = main_graph(
        tmp_path,
        SEQUENCES
        + f"""
def use(x):
    {statement}
use(Seq())
use(Hinted())
""",
    )

    assert length_hints(graph, "main.use") == ["main.Seq.__len__"]


def test_limit_bytes_of_an_iterable_buffer_subclass_does_not_call_its_bytes(tmp_path):
    graph = main_graph(
        tmp_path,
        """
class Data(bytearray):
    def __bytes__(self): return b""
    def __len__(self): return 0
def use(x):
    bytes(x)
use(Data(b"1"))
""",
    )

    assert callees(graph, "main.use") == ["<builtin>.bytes"]


@pytest.mark.parametrize("statement", ["*rest, = x", '"".join(x)', "list(iter(x))"])
def test_the_iterator_of_an_outside_iterable_base_asks_no_length(tmp_path, statement):
    graph = main_graph(
        tmp_path,
        f"""
import collections.abc
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
def use(x):
    {statement}
def copy(x):
    list(x)
use(View())
copy(View())
""",
    )

    assert length_hints(graph, "main.use") == []
    assert length_hints(graph, "main.copy") == ["main.View.__len__"]


LENGTH_ROWS = """
import collections.abc
class Seq:
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
class SeqMeta(type):
    def __getitem__(cls, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(cls): return 2
class SeqClass(metaclass=SeqMeta): pass
class IterMeta(type):
    def __iter__(cls): return cls
    def __next__(cls): raise StopIteration
    def __len__(cls): return 0
class IterClass(metaclass=IterMeta): pass
class Back:
    def __getitem__(self, index):
        raise IndexError
    def __len__(self): return 0
    def __reversed__(self): return iter([])
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        raise IndexError
    def __len__(self): return 0
def make_iter(x):
    return iter(x)
def make_reversed(x):
    return reversed(x)
def gen(x):
    for item in x:
        yield item
"""
LENGTH_OF_A_CLASS_FROM_ITS_METACLASS = [("IterClass", "x", "main.IterMeta.__len__")]
LENGTH_OF_THE_SEQUENCE_PROTOCOL_ITERATOR_OF_AN_INSTANCE_OR_CLASS = [
    ("make_iter(Seq())", "x", "main.Seq.__len__"),
    ("make_iter(SeqClass)", "x", "main.SeqMeta.__len__"),
]
LENGTH_OF_A_REVERSED_SEQUENCE_UNLESS_IT_DEFINES_REVERSED = [
    ("make_reversed(Seq())", "x", "main.Seq.__len__"),
    ("make_reversed(Back())", "x", None),
]
LENGTH_OF_NOTHING_FOR_THE_GENERATOR_OF_THE_SEQUENCE_MIXIN_REVERSED = [
    ("make_reversed(View())", "x", None),
]
LENGTH_OF_NOTHING_FOR_BUILTIN_ITERATORS_AND_GENERATORS = [
    ("enumerate(Seq())", "x", None),
    ("zip(Seq())", "x", None),
    ("map(str, Seq())", "x", None),
    ("filter(None, Seq())", "x", None),
    ("gen(Seq())", "x", None),
    ("iter([Seq()])", "x", None),
]


@pytest.mark.parametrize(
    ("make", "argument", "asked"),
    [
        *LENGTH_OF_A_CLASS_FROM_ITS_METACLASS,
        *LENGTH_OF_THE_SEQUENCE_PROTOCOL_ITERATOR_OF_AN_INSTANCE_OR_CLASS,
        *LENGTH_OF_A_REVERSED_SEQUENCE_UNLESS_IT_DEFINES_REVERSED,
        *LENGTH_OF_NOTHING_FOR_THE_GENERATOR_OF_THE_SEQUENCE_MIXIN_REVERSED,
        *LENGTH_OF_NOTHING_FOR_BUILTIN_ITERATORS_AND_GENERATORS,
    ],
)
@pytest.mark.parametrize("site", ["list({})", '"".join({})', "*rest, = {}"])
def test_every_kind_of_value_whose_length_is_asked(
    tmp_path, make, argument, asked, site
):
    statement = site.format(argument)
    graph = main_graph(
        tmp_path,
        LENGTH_ROWS
        + f"""
def use(x):
    {statement}
use({make})
""",
    )

    assert length_hints(graph, "main.use") == ([asked] if asked else [])


@pytest.mark.parametrize("site", ['"".join(x)', "*rest, = x", "[*x]", "list(x)"])
def test_a_sequence_class_is_asked_its_metaclass_length(tmp_path, site):
    graph = main_graph(
        tmp_path,
        LENGTH_ROWS
        + f"""
def use(x):
    {site}
use(SeqClass)
""",
    )

    assert length_hints(graph, "main.use") == ["main.SeqMeta.__len__"]


def test_a_format_template_that_python_rejects_formats_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def __format__(self, spec): return ""
        "{".format(A())
        """,
    )

    assert callees(graph, "main") == ["<builtin>.str.format"]


def test_an_indexed_format_field_does_not_format_the_argument_itself(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class A:
            def __format__(self, spec): return ""
        "{0[k]}".format(A())
        """,
    )

    assert callees(graph, "main") == ["<builtin>.str.format"]


def test_a_format_template_that_is_not_a_literal_still_evaluates_its_receiver(
    tmp_path,
):
    graph = main_graph(
        tmp_path,
        """
        def template(): return "{0}"
        template().format(1)
        """,
    )

    assert callees(graph, "main") == ["<builtin>.str.format", "main.template"]


def test_an_fstring_value_without_objects_converts_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def g(): return 1
        s = f"{0.5}{g()}"
        """,
    )

    assert callees(graph, "main") == ["main.g"]


def test_an_operator_on_two_floats_calls_nothing(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        def f():
            return 1.5 * 2.0
        f()
        """,
    )

    assert callees(graph, "main.f") == []


def test_new_through_an_exhaustive_order_may_give_another_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import sys
        class X1: pass
        class Y1: pass
        class X2: pass
        class Y2: pass
        class X3: pass
        class Y3: pass
        class X4: pass
        class Y4: pass
        class Other:
            def m(self): pass
        class Factory:
            def __new__(cls): return Other()
        class E(
            Factory,
            X1 if sys.argv else Y1,
            X2 if sys.argv else Y2,
            X3 if sys.argv else Y3,
            X4 if sys.argv else Y4,
        ):
            pass
        E().m()
        """,
    )

    assert "main.Other.m" in callees(graph, "main")


def test_new_past_a_namespace_user_may_give_another_instance(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class Other:
            def m(self): pass
        class Factory:
            def __new__(cls): return Other()
        class Made(Factory):
            locals()
        Made().m()
        """,
    )

    assert "main.Other.m" in callees(graph, "main")


def test_str_of_an_instance_with_an_unknown_outside_base(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import somelib
        class C(somelib.Base): pass
        str(C())
        """,
    )

    assert callees(graph, "main") == ["<builtin>.str", "somelib.Base.__init__"]


def test_str_of_a_list_does_not_reach_into_an_iterator(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        class X:
            def __repr__(self): return "x"
        def run():
            str([iter([X()])])
        run()
        """,
    )

    assert callees(graph, "main.run") == ["<builtin>.iter", "<builtin>.str"]


def test_an_instance_from_new_is_initialised_once_its_class_derives(tmp_path):
    graph = main_graph(
        tmp_path,
        """
        import sys
        class X: pass
        def c0(): return c1
        def c1(): return c2
        def c2(): return c3
        def c3(): return c4
        def c4(): return c5
        def c5(): return c6
        def c6(): return A
        class A:
            def __new__(cls): return object.__new__(B)
            def __init__(self): pass
        class B(X if sys.argv else c0()()()()()()()):
            def __init__(self): pass
        A()
        """,
    )

    assert "main.B.__init__" in callees(graph, "main")
