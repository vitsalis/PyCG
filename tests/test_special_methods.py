"""Implicit calls of special methods on instances: operators, subscripts,
conversions to str, len() and __getattr__."""

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

    # `__add__` runs only where no `__iadd__` is defined.
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

    # object.__ne__ calls __eq__; a class with its own __ne__ answers alone.
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
    # Instances, not functions: external code calls back the functions
    # passed to it, which would hide a builtin that is not modelled.
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

    # At most four string constants: a load of each. More: dynamic.
    assert callees(graph, "main.few") == [
        "<builtin>.getattr",
        "main.C.a",
        "main.C.b",
        "main.C.c",
        "main.C.d",
    ]
    assert callees(graph, "main.many") == ["<builtin>.getattr"]


def test_the_name_of_a_function_is_a_str_constant(tmp_path):
    # `__name__` of a def is its name, of a method too (through the class
    # or bound), of a lambda `<lambda>`; a name stored there is one too.
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

    # A str of unknown value or an outside value names nothing, and does not
    # hide the constants; more than four constants are still dynamic.
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
    # The second getattr's name gets "b" only after the first is decided.
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
    # An annotation without a value evaluates its target but stores nothing.
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

    # dict.__getitem__ calls __missing__; a class's own __getitem__ does not.
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

    # `%d` converts with __int__ or __index__, not __str__.
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

    # An instance's __mod__ decides; an int and bytes do not call __str__;
    # a format that the analysis does not know converts nothing.
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
    # list, tuple, set and dict have no __str__ or __format__: each
    # conversion gives repr(), which calls repr() of the elements.
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
    # A value that is no tuple is the one item of `%`, also a container: a
    # dict too, where the format names no key. A tuple gives its elements as
    # the items, and a dict gives its values to the named fields.
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
    # Python gives the one value to whatever the format takes first: a `*`
    # width or `%d` takes it and fails, and a field after the first one
    # lacks an argument, after the first is converted. `%%` takes nothing,
    # and a positional field before the named ones takes a dict whole.
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


PERCENT_SYNTAX = [
    # An empty precision is zero; a key may hold balanced parentheses.
    ('"%.s" % xs', "[Element()]", ["Element.__repr__"]),
    ('"%5.s %r" % xs', "(Element(), Inner())", ["Element.__str__", "Inner.__repr__"]),
    ('"%((a))s" % xs', '{"(a)": Element()}', ["Element.__str__"]),
    ('"%(a(b)c)r" % xs', '{"a(b)c": Element()}', ["Element.__repr__"]),
    ('"%ls %Ls" % xs', "(Element(), Inner())", ["Element.__str__", "Inner.__repr__"]),
    # Python rejects the first field it cannot take and converts nothing
    # from there: a named field with a `*`, a key whose parentheses do not
    # close, an unsupported conversion, a `%` that ends the format.
    ('"%(a)*s" % xs', '{"a": Element()}', []),
    ('"%(a).*s" % xs', '{"a": Element()}', []),
    ('"%(a)s%(b)*s%(c)r" % xs', '{"a": Element(), "c": Inner()}', ["Element.__str__"]),
    ('"%((a)s" % xs', '{"(a": Element()}', []),
    ('"%s %y %r" % xs', "(Element(), 1, Inner())", ["Element.__str__"]),
    ('"%s %5% %r" % xs', "(Element(), Inner())", ["Element.__str__"]),
    ('"%lls" % xs', "(Element(),)", []),
    ('"%r %" % xs', "(Element(),)", ["Element.__repr__"]),
    # A tuple has no keys, a positional field after a named one has no
    # argument, and a dict is no number.
    ('"%s %(a)s %r" % xs', "(Element(), 1, Inner())", ["Element.__str__"]),
    ('"%(a)s %r" % xs', '{"a": Element()}', ["Element.__str__"]),
    ('"%d%(a)s" % xs', '{"a": Element()}', []),
]


PERCENT_BYTES = [
    # A bytes format converts with repr() for `%r` and `%a`; `%s` and `%b`
    # take an item without converting it with str().
    ('b"%r" % xs', "(Element(),)", ["Element.__repr__"]),
    ('b"%a" % xs', "[Element()]", ["Element.__repr__"]),
    ('b"%s %r" % xs', '(b"x", Inner())', ["Inner.__repr__"]),
    ('b"%b %a" % xs', '(b"x", Inner())', ["Inner.__repr__"]),
    ('b"%(a)r" % xs', '{b"a": Element()}', ["Element.__repr__"]),
    ('b"%((a))r" % xs', '{b"(a)": Element()}', ["Element.__repr__"]),
    # Its keys are bytes, and it rejects fields as a str format does.
    ('b"%(a)r" % xs', '{"a": Element()}', []),
    ('b"%y %r" % xs', "(1, Inner())", []),
    ('b"%(a)*r" % xs', '{b"a": Element()}', []),
    ('b"%s" % xs', "(Element(),)", []),
]


@pytest.mark.parametrize("conversion, value, expected", PERCENT_BYTES)
def test_percent_of_bytes_converts_with_repr(tmp_path, conversion, value, expected):
    assert converted(tmp_path, conversion, value) == [
        f"main.{name}" for name in expected
    ]


# Python rejects a width above PY_SSIZE_T_MAX (taken as 2**63 - 1) and a
# precision above INT_MAX (2**31 - 1) before it converts the item. Each
# format: whether Python accepts it.
WIDTH, PRECISION = 2**63 - 1, 2**31 - 1
PERCENT_BOUNDS = [
    (f"%{WIDTH}s", True),
    (f"%{WIDTH + 1}s", False),
    (f"%.{PRECISION}s", True),
    (f"%.{PRECISION + 1}s", False),
    (f"%000{WIDTH}.000{PRECISION}s", True),
    (f"%{'9' * 5000}s", False),
    (f"%.{'9' * 5000}s", False),
    (f"%{WIDTH}r".encode(), True),
    (f"%{WIDTH + 1}r".encode(), False),
    (f"%.{PRECISION}r".encode(), True),
    (f"%.{PRECISION + 1}r".encode(), False),
]


class _Converted(Exception):
    pass


class _Raises:
    """An item whose conversion raises before Python writes any output."""

    def __str__(self):
        raise _Converted

    __repr__ = __str__


@pytest.mark.parametrize("fmt, accepted", PERCENT_BOUNDS)
def test_the_bounds_of_widths_and_precisions_are_those_of_python(fmt, accepted):
    if accepted and sys.maxsize != WIDTH and str(WIDTH) in str(fmt):
        # A 32-bit Python rejects this width; the analysis takes the bound
        # of a 64-bit one (see the design).
        pytest.skip("PY_SSIZE_T_MAX of this Python is not 2**63 - 1")
    error = _Converted if accepted else ValueError
    with pytest.raises(error):
        fmt % (_Raises(),)


@pytest.mark.parametrize("fmt, accepted", PERCENT_BOUNDS)
def test_percent_converts_nothing_from_a_width_or_precision_past_its_bound(
    tmp_path, fmt, accepted
):
    method = "__repr__" if fmt[-1:] in ("r", b"r") else "__str__"
    expected = [f"main.Element.{method}"] if accepted else []
    assert converted(tmp_path, f"{fmt!r} % xs", "(Element(),)") == expected
    # Python formats the fields before the rejected one, and none after it.
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
    # A list that holds itself is converted once.
    assert converted(
        tmp_path / "cycle", "xs.append(xs)\n    repr(xs)", "[Inner()]"
    ) == ["main.Inner.__repr__"]


def test_a_value_that_is_no_builtin_container_does_not_convert_its_elements(
    tmp_path,
):
    # A generator and an instance are converted by their own __repr__ only.
    for index, value in enumerate(["(x for x in [Inner()])", "Element()"]):
        found = converted(tmp_path / str(index), "repr(xs)", value)
        assert "main.Inner.__repr__" not in found, value


def test_an_iterator_of_a_container_does_not_convert_its_elements(tmp_path):
    # repr() of a list_iterator names its class, not its elements.
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

    # Each `*` takes an int item before the item that is converted.
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
    # int() of an index longer than 4300 digits fails (final review of the
    # engine, finding 3).
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

    # An index is a number, whatever its leading zeros; Python rejects an
    # index past sys.maxsize, which no call supplies.
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

    # A lookup compares the key with a stored key that is another object.
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
    # Python compares the stored key with the searched one where the hashes
    # are equal, whatever the searched object is: an int or a function.
    # Only the stored key's __eq__ is analysed; a stored key found by
    # identity, or one that is not an instance or class, gives no edge.
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

    # A list is searched without hashing.
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


# Keys that enter a set or a dict, or are looked up there, are hashed and
# compared with the stored keys; sequences, sets and dicts compared, and the
# items that sorted, min and max compare, compare their elements.

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
    # A set or dict stores the hash of each key: one made from it, or
    # extended with it, does not hash its keys again.
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
    # CPython reuses the hashes of a set and of a dict of exactly that
    # class when a set or `fromkeys` takes them, and of every dict that
    # iterates as `dict` does when a dict takes its items; an OrderedDict
    # iterates by its own `__iter__`, and a Counter counts the elements of
    # any iterable that is no mapping.
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

    # The stored hashes are compared, not computed again.
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

    # `==` compares with `__eq__`; an ordering finds the first elements that
    # differ with `__eq__` and orders them.
    assert callees(graph, "main.equal") == ["main.Item.__eq__"]
    assert callees(graph, "main.less") == ["main.Item.__eq__", "main.Item.__lt__"]
    # A limit: containers inside the operands compare nothing.
    assert callees(graph, "main.nested") == []
    # A tuple and an int compare no elements.
    assert callees(graph, "main.other") == []


def test_containers_compare_elements_only_with_containers_of_their_family(
    tmp_path,
):
    # The families of CPython: a list with a list, a tuple with a tuple, a
    # deque with a deque, a set with a set or frozenset, a dict with any
    # dict. An ordering compares two sets as subsets; two dicts it does not
    # order. A limit: containers inside the operands compare nothing, also
    # where Python compares their elements.
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
    # Python returns False on the sizes of two sets of one element each
    # before it compares a key; the analysis does not know the sizes.
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
    # Python hashes the keys of the dict again in `intersection` (and in
    # `issubset`, `issuperset`, `isdisjoint`); the analysis looks only at
    # the class of the source.
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
    # list() and list.extend() ask `__len__`, else `__length_hint__`, of an
    # iterable that is no list or tuple. tuple() asks nothing (Python 3.14
    # on; 3.12 and 3.13 ask too).
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
    assert callees(graph, "main.as_tuple") == ["<builtin>.tuple", "main.Sized.__iter__"]


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
    # The last operand of `and` gives the result; its truth is not tested.
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

    # Python tests the truth of `a < b` to decide whether to go on.
    assert callees(graph, "main.chain") == [
        "main.High.__lt__",
        "main.Low.__lt__",
        "main.Tested.__bool__",
    ]
    # The condition tests the value of the chain: either result.
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
