"""The analysis terminates, without an error, on every program: termination
must hold by construction (see *Termination* in docs/design.md). Seeded
random programs search for counterexamples in five families: callables
that are wrapped, bound and stored back in every order; special methods
that are assigned classes and functions while iteration, calls and
subscripts feed their results back into the values they came from;
classes whose bases are builtin and outside classes read from attributes
that get more values later, with attribute hooks, accessed every way;
typed outside values fed back into the variable they came from; and
classes whose `__new__`, `__call__` and `__init__` dispatch to each other
and to the builtins that call back. The programs that broke earlier
versions are fixed cases."""

import inspect
import random
import signal
import sys
from collections import deque
from contextlib import contextmanager

import pytest
from programs import analysed, no_rule_sees_what_is_opaque

from pycg.analysis import solver
from pycg.formats import dumps

SEED = 20261111
RANDOM_PROGRAMS = 500
SECONDS_PER_PROGRAM = 5
MAX_OBJECTS = 5_000

FIXED = [
    # Containers that hold themselves and each other, converted with repr()
    # (review of the cost of converting containers).
    "class E:\n    def __repr__(self): return ''\n"
    "a = [E()]\nb = {'k': a}\na.append(a)\na.append(b)\n"
    "for x in (a, b):\n    repr(x)\n    f'{x}'\n",
    # A container-valued stub attribute fed back into its receiver (final
    # review of stream T, finding 1).
    "from types import SimpleNamespace\n"
    "x = SimpleNamespace()\nfor _ in (0,):\n    x = x.__dict__\n",
    # An attribute whose stub type has type[T] (review of T2).
    "from dataclasses import dataclass, fields\n"
    "@dataclass\nclass R:\n    value: int\n"
    "fields(R)[0].type\n",
    # Stub tuple results of two lengths at one call site (review of T2).
    "import os.path\n"
    "for split in (os.path.split, os.path.splitroot):\n"
    "    split('/tmp/file')\n",
    # One call that reaches zip with one iterable and, through a `__new__`
    # that passes the class first, with two (final review, finding 1).
    "class M(type):\n    def __iter__(cls): return iter(())\n"
    "class Factory:\n    __call__ = staticmethod(zip)\n"
    "class C(metaclass=M):\n    __new__ = Factory()\n"
    "def make(factory): return factory(())\nmake(zip)\nmake(C)\n",
    # A class method stored back as the attribute it was loaded from.
    "class C:\n    def f(cls): pass\nC.f = classmethod(C.f)\nC.f()\n",
    "class C:\n    def f(cls): pass\nc = C()\nC.f = classmethod(c.f)\nc.f()\n",
    # A cycle through a bound method and a static method.
    "class C:\n    def f(*args): pass\nC.f = classmethod(staticmethod(C.f))\nC.f()\n",
    # A chain of class methods without a cycle.
    "class A:\n    @classmethod\n    def f(a, b, c):\n        c.run()\n"
    "class B:\n    f = classmethod(A.f)\n"
    "class C:\n    f = classmethod(B.f)\n    @staticmethod\n    def run(): pass\n"
    "C.f()\n",
    # An iterator class stored as its own __iter__, fed back into the list
    # that is iterated.
    "class It:\n    def __init__(self):\n        self.done = False\n"
    "    def __next__(self):\n        if self.done:\n            raise StopIteration\n"
    "        self.done = True\n        return self\n"
    "It.__iter__ = It\nxs = [It()]\nfor item in xs:\n    xs.extend(item)\n    break\n",
    # A class method of the class as its own __init__: each instantiation
    # binds the class again.
    "class It:\n    def __init__(self, *args): pass\n"
    "It.__init__ = classmethod(It)\nIt()\n",
    # A tuple of exception classes that contains itself.
    "class Error(Exception): pass\nkinds = ()\nkinds = (kinds, Error)\n"
    "try:\n    raise Error()\nexcept kinds as error:\n    pass\n",
    # *args unpacked at a shifted position into the function itself.
    "def g(): pass\ndef shift(*args):\n    args[0]()\n    shift(g, *args)\nshift(g)\n",
    # A base read from an attribute that gets builtin bases and, at the
    # completion, one more class: a missing attribute then walks an MRO with
    # external classes.
    "class Holder: pass\nclass A: pass\nclass Last: pass\nholder = Holder()\n"
    "for base in (int, str, list, tuple, dict, set, bytes, Exception, A):\n"
    "    holder.base = base\n"
    "class C(holder.base): pass\ngetattr(C(), 'missing', None)\n"
    "name = 'base'\nsetattr(holder, name, Last)\n",
    # A module named abc that defines abstractmethod and imports the frozen
    # abc: one name, modelled both as an analysed and as an outside function
    # (whole-branch review, round 2).
    {
        "abc.py": "import abc\n"
        "def abstractmethod(funcobj):\n    return funcobj\n"
        "def target():\n    pass\n"
        "abstractmethod(*(target,))\n"
        "abc.abstractmethod(*(target,))\n"
    },
    # An attribute of an external base fed back as the base.
    "import unittest\nbases = [unittest.TestCase]\nclass C(bases[0]): pass\n"
    "bases[0] = C.failureException\n",
    # Annotations that make a scope, quoted and not (review of the declared
    # types: crashed).
    'def f(x: "(lambda: None).__class__"): pass\n'
    "def g(x: (lambda: None).__class__): pass\n",
    # A format field whose digits int() does not read (crashed).
    '"{\u00b2}_handler".format(**{"\u00b2": "x"})\n',
    # An index and an int literal longer than the 4300 digits that int() and
    # repr() convert by default (final review, finding 3).
    '"{' + "0" * 4301 + '}".format("ok")\n',
    "def f(): pass\nd = {0x" + "f" * 4000 + ": f}\nd[0x" + "f" * 4000 + "]()\n",
    # Each class is the other's __new__: every call passes one more receiver,
    # up to the cap of receivers.
    "class C: pass\nclass D: pass\nC.__new__ = D\nD.__new__ = C\nC()\n",
    # Two such classes whose __new__ is also an instance that calls map: map
    # gets the receivers as iterables, and its call back, a new root, calls
    # the class again (final review, round 2, finding 1).
    "class Caller:\n    __call__ = map\n"
    "class X: pass\nclass Y: pass\n"
    "X.__new__ = Y\nY.__new__ = X\nY.__new__ = Caller()\nY([1])\n",
    # Two classes whose bases are calls that return each other: they wait for
    # each other until the fixpoint decides the cycle.
    "def left(): return Q\ndef right(): return P\n"
    "class P(left()): ...\nclass Q(right()): ...\n",
    # Aliases whose forms subscript themselves or each other, read through a
    # subscript (review of round 1, finding 1).
    "type Loop[T] = Loop[T]\ndef f(x: Loop[int]): pass\n",
    "type A[T] = B[T]\ntype B[T] = A[T]\ndef f(x: A[int], y: 'B[int]'): pass\n",
    "from typing import List, TypeAlias, TypeVar\nT = TypeVar('T')\n"
    "A = List[T]\nA = A[T]\nB: TypeAlias = A[T]\nA = B[T]\n"
    "class C:\n    D = List[T]\n    D = D[T]\n    def f(self, x: D[int]): pass\n"
    "def f(x: A[int], y: B[int]): pass\n",
    # A tuple of classes that contains itself, tested in both branches
    # (review of r1-isinstance, finding 1).
    "classes = (int,)\nfor _ in range(2):\n    classes = (classes,)\n"
    "x = 's'\nif isinstance(x, classes):\n    x.upper()\nelse:\n    x.lower()\n"
    "if issubclass(x, classes):\n    x.upper()\n",
    # Tuples of classes that share their elements, nested ten deep.
    "t0 = (int, str)\n"
    + "".join(f"t{i} = (t{i - 1}, t{i - 1}, t{i - 1})\n" for i in range(1, 10))
    + "def f(x=1):\n    if isinstance(x, t9):\n        x.bit_length()\n"
    "    if not isinstance(x, t9):\n        x.upper()\n",
    # A defaultdict whose factory copies it, read again and again (review
    # of r2-builtins, finding 1); nested factories; a factory that returns a
    # defaultdict of itself.
    "from collections import defaultdict\n"
    "def build(factory):\n    return defaultdict(factory)\n"
    "d = build(list)\nd = build(d.copy)\nfor _ in range(2):\n    d = d[0]\n",
    "from collections import defaultdict\n"
    "d = defaultdict(lambda: defaultdict(list))\n"
    "for _ in range(2):\n    d = d[0]\n    d = d.copy()\n",
    "from collections import defaultdict\n"
    "def tree():\n    return defaultdict(tree)\n"
    "t = tree()\nfor _ in range(2):\n    t = t['k'].copy()\n",
    *[
        # Class methods whose results are fed back through the explicit
        # `__get__`: bound to an outside owner, to the type of an instance
        # and to a metaclass; and a property subclass fed its own result.
        "class Meta(type): pass\nclass C(metaclass=Meta): pass\n"
        "def make(cls):\n    return classmethod(make)\n"
        "m = classmethod(make)\nfor _ in range(2):\n"
        "    m = m.__get__(None, int)()\n    m = m.__get__(C)()\n"
        "    m = m.__get__(C())()\n    m = m.__get__(None, m)()\n",
        "class P(property): pass\n"
        "def read(self):\n    return P(read)\n"
        "p = P(read)\nfor _ in range(2):\n"
        "    p = p.__get__(p)\n    p = P.__get__(p, p, type(p))\n"
        "    p = p.getter(p)\n",
    ],
]

# The programs of `FIXED` for the explicit `__get__`, solved without a cap.
GET_FEEDBACK = FIXED[-2:]

# Wrappers: staticmethod, classmethod, property and functools.partial around
# what loading an attribute gives, stored back, often to that attribute.

WRAPPER_HEADER = """\
import functools
class A:
    def f(*args): pass
    def g(self, *args): return self
    @classmethod
    def h(cls, *args): return cls
    @staticmethod
    def s(*args): pass
    @property
    def p(self): return self.f
class B(A):
    pass
a = A()
b = B()
"""
NAMES = ("f", "g", "h", "s", "p", "x")
OWNERS = ("A", "B", "a", "b", "A()", "B()")
WRAPPERS = (
    "staticmethod",
    "classmethod",
    "classmethod",
    "property",
    "functools.partial",
)


def _wrapped(rng, depth, target):
    if depth == 0 or rng.random() < 0.25:
        # Often the attribute that the result is stored to: flow-insensitively
        # it then wraps itself.
        if rng.random() < 0.5:
            return target
        return f"{rng.choice(OWNERS)}.{rng.choice(NAMES)}"
    return f"{rng.choice(WRAPPERS)}({_wrapped(rng, depth - 1, target)})"


def _wrapper_statements(rng):
    """One store, often followed by a call of what it stored, or one
    access."""
    roll = rng.random()
    name = rng.choice(NAMES)
    if roll < 0.6:
        target = f"{rng.choice(('A', 'B', 'a', 'b'))}.{name}"
        store = f"{target} = {_wrapped(rng, rng.randint(1, 4), target)}"
        if rng.random() < 0.7:
            call = target if rng.random() < 0.5 else f"{rng.choice(OWNERS)}.{name}"
            return [store, f"{call}()"]
        return [store]
    access = f"{rng.choice(OWNERS)}.{name}"
    if roll < 0.85:
        return [f"{access}({', '.join(['1'] * rng.randint(0, 2))})"]
    if roll < 0.95:
        return [f"{access}()()"]
    return [access]


def wrapper_program(rng):
    statements = []
    for _ in range(rng.randint(3, 8)):
        statements += _wrapper_statements(rng)
    return WRAPPER_HEADER + "\n".join(statements) + "\n"


# Feedback: special methods hold classes, functions and bound methods, and
# the results of iterating, calling and subscripting flow back into the
# containers, variables and attributes they came from.

FEEDBACK_HEADER = """\
class It:
    def __init__(self, *args):
        self.a = self
    def __next__(self):
        return self
    def __getitem__(self, index):
        return self
    def __call__(self, *args):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __eq__(self, other):
        return self
    def __add__(self, other):
        return self
    def __getattr__(self, name):
        return self
class Box:
    pass
class New(It):
    def __new__(cls, *args):
        return super().__new__(cls) if args else x
class Meta(type):
    def make(cls, *args):
        return super().__call__(*args)
class Made(It, metaclass=Meta):
    pass
def make(*args):
    return It()
def gen(value):
    yield from value
async def co(value):
    return await value
async def drive(value):
    global x
    x = await value
x = It()
xs = [It()]
d = {0: It()}
"""
SPECIALS = (
    "__iter__",
    "__next__",
    "__call__",
    "__getitem__",
    "__enter__",
    "__eq__",
    "__getattr__",
    "__init__",
    "__add__",
    "__contains__",
    "__getattribute__",
    "__setattr__",
    "__delattr__",
    "__await__",
    "__new__",
)
CALLABLES = (
    "It",
    "Box",
    "New",
    "Made",
    "Made.make",
    "make",
    "gen",
    "co",
    "iter",
    "next",
    "x",
    "xs.append",
    "xs.extend",
    "It.__next__",
    "x.__call__",
    "lambda *args: x",
    "lambda *args: It()",
    "classmethod(It)",
    "staticmethod(make)",
)
FEEDBACK = (
    "xs.extend(x)",
    "xs.append(xs)",
    "xs.append(x)",
    "d[0] = d",
    "d[x] = x",
    "x = x()",
    "x = iter(x)",
    "x = next(x)",
    "x = x[0]",
    "x = xs[0]",
    "x.a = x",
    "x = x.a",
    "x = x + x",
    "x = x == x",
    "x = gen(x)",
    "x = list(x)",
    "x = [y for y in x]",
    "x, *rest = x",
    "x = x in xs",
    "x = getattr(x, 'b')",
    "x = make(x)",
    "xs = xs + [x]",
    "del x.a",
    "x.b = x.a",
    "x = x in [None, x]",
    "x = co(x)",
    "drive(x)",
    "drive(co(x))",
)
LOOPS = (
    "for item in {}:\n    {}",
    "with x as item:\n    {1}",
    "while x:\n    {1}",
)


def _feedback_statement(rng):
    roll = rng.random()
    if roll < 0.3:
        owner = rng.choice(("It", "Box", "x"))
        return f"{owner}.{rng.choice(SPECIALS)} = {rng.choice(CALLABLES)}"
    statement = rng.choice(FEEDBACK)
    if roll < 0.5:
        loop = rng.choice(LOOPS)
        return loop.format(rng.choice(("x", "xs", "d", "gen(x)")), statement)
    return statement


def feedback_program(rng):
    statements = [_feedback_statement(rng) for _ in range(rng.randint(3, 10))]
    body = "\n".join(statements)
    if rng.random() < 0.3:
        # The same statements in a function that is called with them.
        indented = body.replace("\n", "\n    ")
        body += f"\ndef run(x, xs, d):\n    {indented}\n    return x\nx = run(x, xs, d)"
    return FEEDBACK_HEADER + body + "\n"


# Hierarchies: bases that are builtin or outside classes, read from an
# attribute that gets more values later (assigned, or set through setattr
# with a name in a variable), attribute hooks in class bodies or assigned,
# and loads, stores and deletions on the instances.

HIERARCHY_HEADER = """\
import lib
class Holder:
    pass
class A:
    def method(self):
        return self
class H:
    def __getattr__(self, name):
        return self
def fetch(self, name):
    return self
def put(self, name, value):
    value
holder = Holder()
holder.base = A
attribute = "base"
hook_name = "__getattr__"
"""
BASES = (
    "int",
    "str",
    "list",
    "tuple",
    "dict",
    "set",
    "bytes",
    "Exception",
    "object",
    "lib.Base",
    "A",
    "H",
    "holder.base",
)
HOOK_NAMES = ("__getattr__", "__getattribute__", "__setattr__", "__delattr__")
HOOK_VALUES = ("fetch", "put", "A().method", "lambda self, *args: self", "H()")
ACCESSES = (
    "{c}().missing",
    "{c}().method()",
    "{c}().attr = 1",
    "del {c}().attr",
    "getattr({c}(), 'missing', None)",
    "getattr({c}(), attribute, None)",
    "setattr({c}(), attribute, 1)",
    "delattr({c}(), 'attr')",
    "{c}().missing.method()",
)


def hierarchy_program(rng):
    lines = []
    if rng.random() < 0.5:
        # More candidate bases than a class keeps alternative MROs for.
        bases = rng.sample(BASES[:-1], rng.randint(6, len(BASES) - 1))
        lines.append(f"for base in ({', '.join(bases)},):\n    holder.base = base")
    classes = []
    for _ in range(rng.randint(4, 12)):
        roll = rng.random()
        if roll < 0.2:
            lines.append(f"holder.base = {rng.choice(BASES)}")
        elif roll < 0.3:
            lines.append(f"setattr(holder, attribute, {rng.choice(BASES)})")
        elif roll < 0.5 or not classes:
            name = f"C{len(classes)}"
            bases = [
                rng.choice(BASES + tuple(classes)) for _ in range(rng.randint(1, 2))
            ]
            if len(set(bases)) < len(bases):
                bases = bases[:1]
            body = "pass"
            if rng.random() < 0.3:
                hook = rng.choice(HOOK_NAMES)
                body = f"{hook} = {rng.choice(HOOK_VALUES)}"
            lines.append(f"class {name}({', '.join(bases)}):\n    {body}")
            classes.append(name)
        elif roll < 0.65:
            target = rng.choice(classes)
            hook, value = rng.choice(HOOK_NAMES), rng.choice(HOOK_VALUES)
            if rng.random() < 0.5:
                lines.append(f"{target}.{hook} = {value}")
            else:
                lines.append(f"hook_name = {hook!r}")
                lines.append(f"setattr({target}, hook_name, {value})")
        else:
            lines.append(rng.choice(ACCESSES).format(c=rng.choice(classes)))
    return HIERARCHY_HEADER + "\n".join(lines) + "\n"


def long_hierarchies(length):
    """A chain of `length` classes and one of as many metaclasses, each a
    subclass of the one before, used through every rule that walks a
    hierarchy: lookups, `type[...]` and class annotations, `except` and
    class patterns."""
    last = length - 1
    lines = [
        "class C0(Exception):",
        "    def run(self): pass",
        "    @staticmethod",
        "    def make(): pass",
        "class M0(type):",
        "    def describe(cls): pass",
    ]
    for i in range(1, last):
        lines += [f"class C{i}(C{i - 1}): pass", f"class M{i}(M{i - 1}): pass"]
    lines += [
        f"class C{last}(C{last - 1}):",
        "    @staticmethod",
        "    def make(): pass",
        f"class M{last}(M{last - 1}): pass",
        f"class K(metaclass=M{last}): pass",
        "K.describe()",
        f"C{last}().run()",
        "def declared(kind: type[C0], meta: type[M0], value: C0):",
        "    kind.make()",
        "    meta.describe(K)",
        "    value.run()",
        "def handle():",
        "    try:",
        f"        raise C{last}()",
        "    except C0 as error:",
        "        error.run()",
        "def check(value):",
        "    match value:",
        "        case C0():",
        "            value.run()",
        f"check(C{last}())",
    ]
    return "\n".join(lines) + "\n"


def wide_hierarchies(width):
    """A class with `width` subclasses, and a class with `width` bases, used
    as `long_hierarchies` uses its chains."""
    lines = ["class Root:", "    def run(self): pass"]
    for i in range(width):
        lines += [
            f"class Sub{i}(Root): pass",
            f"class Base{i}:",
            f"    def run{i}(self): pass",
        ]
    bases = ", ".join(f"Base{i}" for i in range(width))
    lines += [
        f"class Wide({bases}): pass",
        f"Wide().run{width - 1}()",
        f"Sub{width - 1}().run()",
        "def declared(kind: type[Root], value: Root):",
        "    kind.run(value)",
        "    value.run()",
    ]
    return "\n".join(lines) + "\n"


# The analysis needs a few dozen frames for these programs, whatever their
# size; each rule walks a hierarchy without a frame per class.
FRAMES = 200
CLASSES = 300


@contextmanager
def stack_limit(frames):
    """Allow `frames` more frames on the Python stack than the caller uses,
    so that a hierarchy of a few hundred classes is longer than the stack
    (the default allows a thousand)."""
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(len(inspect.stack(0)) + frames)
    try:
        yield
    finally:
        sys.setrecursionlimit(previous)


def test_a_hierarchy_longer_than_the_stack_is_analysed(tmp_path):
    # `type[C0]` once recursed per subclass (final review of the engine,
    # finding 2).
    with stack_limit(FRAMES):
        graph = analyse(tmp_path, long_hierarchies(CLASSES)).output()

    last = CLASSES - 1
    assert graph["main.declared"] == [
        "main.C0.make",
        "main.C0.run",
        f"main.C{last}.make",
        "main.M0.describe",
    ]
    assert {"main.C0.run", "main.M0.describe", "main.check"} <= set(graph["main"])
    assert graph["main.handle"] == ["<builtin>.Exception.__init__", "main.C0.run"]
    assert graph["main.check"] == ["main.C0.run"]


def test_a_hierarchy_wider_than_the_stack_is_analysed(tmp_path):
    with stack_limit(FRAMES):
        graph = analyse(tmp_path, wide_hierarchies(CLASSES)).output()

    last = CLASSES - 1
    assert graph["main"] == [f"main.Base{last}.run{last}", "main.Root.run"]
    assert graph["main.declared"] == ["main.Root.run"]


def test_a_chain_of_type_aliases_longer_than_the_stack_is_analysed(tmp_path):
    # Each alias is a union that names the alias before: the reading of
    # annotations attaches a constraint per alias, which the solver's
    # bound on nested attachments keeps off the stack.
    last = sys.getrecursionlimit() + 100
    aliases = "".join(f"T{i} = T{i - 1} | None\n" for i in range(1, last + 1))
    source = (
        "class C:\n    def f(self): pass\nT0 = C | None\n"
        + aliases
        + f"def value(x: T{last}):\n    x.f()\n"
        + f"def quoted(x: 'T{last}'):\n    x.f()\n"
        + f"def items(xs: list[T{last}]):\n    for x in xs:\n        x.f()\n"
    )
    graph = analyse(tmp_path, source).output()

    for function in ("value", "quoted", "items"):
        assert graph[f"main.{function}"] == ["main.C.f"], function


def analyse(root, program, **options):
    """Analyse `program`: the source of main.py, or files by name, the first
    of which is the entry point; `options` go to the generator."""
    files = {"main.py": program} if isinstance(program, str) else program
    return analysed(root, files, entry_points=(next(iter(files)),), **options)


# Typed values: instances of stub classes (generic ones among them), whose
# attributes, method results and elements feed back into the variable they
# came from, in loops.

TYPED_HEADER = """\
import collections
import contextlib
import datetime
import functools
import re
import types
def f(*args):
    return args
x = types.SimpleNamespace()
"""
TYPED_VALUES = (
    "types.SimpleNamespace()",
    "collections.OrderedDict()",
    "collections.OrderedDict(x)",
    "collections.deque([x])",
    "enumerate([x])",
    "zip([x], [x])",
    "map(f, [x])",
    "map(x, [x], *[[x]])",
    "filter(x, [x])",
    "sorted([x], key=x)",
    "reversed([x])",
    "contextlib.closing(x)",
    "functools.partial(f, x)",
    "datetime.datetime.now()",
    "re.compile('a').match('a')",
    "[x]",
    "(x, x)",
    "{'k': x}",
)
TYPED_STEPS = (
    "x = x.__dict__",
    "x = x.__class__",
    "x = x.copy()",
    "x = x.items()",
    "x = x.values()",
    "x = x.popitem()",
    "x = x.pop()",
    "x = x.group()",
    "x = x.replace()",
    "x = x.__enter__()",
    "x = x.func",
    "x = x.args",
    "x = x(x)",
    "x = next(iter(x))",
    "x = x[0]",
    "x['k'] = x",
    "x.append(x)",
    "x.attr = x",
    "x = x.attr",
    "for x in x:\n    pass",
    "with x as x:\n    pass",
)


def typed_program(rng):
    statements = [f"x = {rng.choice(TYPED_VALUES)}"]
    for _ in range(rng.randint(2, 8)):
        step = rng.choice(TYPED_STEPS)
        if rng.random() < 0.3:
            step = f"x = {rng.choice(TYPED_VALUES)}"
        if rng.random() < 0.5:
            step = "for _ in (0,):\n    " + step.replace("\n", "\n    ")
        statements.append(step)
    return TYPED_HEADER + "\n".join(statements) + "\n"


# Dispatch: classes whose `__new__`, `__call__` and `__init__` are other
# classes, callable instances, class methods and the builtins that call back
# (`map`, `filter`, `sorted` with a key) or make containers by arity (`zip`), so that
# receivers pile up before a builtin whose call back calls a class again.

DISPATCH_HEADER = """\
class A:
    def m(cls, *args):
        return args
class B:
    pass
class Caller:
    __call__ = map
class Zipper:
    __call__ = staticmethod(zip)
"""
DISPATCH_OWNERS = ("A", "B", "Caller", "Zipper")
DISPATCH_SLOTS = ("__new__", "__call__", "__init__")
DISPATCH_VALUES = (
    "A",
    "B",
    "Caller()",
    "Zipper()",
    "map",
    "zip",
    "filter",
    "staticmethod(map)",
    "classmethod(map)",
    "classmethod(A.m)",
    "A.m",
    "A().m",
    "lambda *args: sorted(args, key=A)",
)
DISPATCH_CALLS = (
    "A([1])",
    "B([1], [2])",
    "Caller()(A, [1])",
    "Caller()(B, [1], *[[2]])",
    "Zipper()([1], A)",
    "list(map(A, [1], [2]))",
    "sorted([A, B], key=B)",
)


def dispatch_program(rng):
    statements = []
    for _ in range(rng.randint(2, 7)):
        owner = rng.choice(DISPATCH_OWNERS)
        slot = rng.choice(DISPATCH_SLOTS)
        statements.append(f"{owner}.{slot} = {rng.choice(DISPATCH_VALUES)}")
    statements += rng.sample(DISPATCH_CALLS, rng.randint(1, 3))
    return DISPATCH_HEADER + "\n".join(statements) + "\n"


FAMILIES = 5


def random_programs():
    rng = random.Random(SEED)
    # Its own sequence, so that the other families keep their programs.
    dispatch = random.Random(SEED)
    for _ in range(RANDOM_PROGRAMS):
        yield wrapper_program(rng)
        yield feedback_program(rng)
        yield hierarchy_program(rng)
        yield typed_program(rng)
        yield dispatch_program(dispatch)


@contextmanager
def time_limit(seconds):
    def expire(signum, frame):
        raise TimeoutError(f"analysis took more than {seconds} s")

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def test_the_random_programs_are_valid_and_differ():
    programs = list(random_programs())
    for source in programs:
        compile(source, "main.py", "exec")
    assert len(set(programs)) > len(programs) * 0.9


# The tables of Analysis that hold what it makes on demand while it solves:
# objects, calls, nodes and the constraints made per key. Termination means
# they stay finite, so `object_count` counts them.
COUNTED = {
    "externals",
    "_class_filters",
    "_typed",
    "_instances",
    "_containers",
    "_bound_methods",
    "_builtin_methods",
    "_families",
    "_below_nodes",
    "_wrappers",
    "_supers",
    "_fallbacks",
    "_generators",
    "_coroutines",
    "_returning",
    "_consts",
    "_patterns",
    "_site_calls",
    "_dunder_calls",
    "_receiver_calls",
    "_callbacks",
    "_constants",
    "_callees",
    "_fallback_nodes",
    "_model_bindings",
    "_entry_receivers",
    "_super_pairs",
    "_super_accepted",
    "_unpacked",
    "_iterated",
    "_namespace_nodes",
    "named_nodes",
    "_open_arguments",
    "_open_modes",
    "_closures",
}

# The other tables: what the builder makes, one per definition or name in
# the source; the call graph; indexes of counted calls; records of
# constraints already attached to counted things; and the work lists of
# the completion.
NOT_COUNTED = {
    "_stub_definitions",
    "_typed_callbacks",
    "_unknown_modes",
    "modules",
    "_new_results",
    "_class_instances",
    "_statement_calls",
    "_statement_news",
    "_made_classes",
    "functions",
    "classes",
    "_receivers",
    "zero_argument_super",
    "_called",
    "literal_imports",
    "none_arguments",
    "_type_forms",
    "_annotated",
    "_tested_classes",
    "_stub_ancestors",
    "_dataclass_like_classes",
    "_classes_below",
    "_pattern_states",
    "_store_names",
    "_class_store_names",
    "_module_names",
    "_external_modules",
    "site_edges",
    "call_expressions",
    "iterated_expressions",
    "external_callees",
    "_roots",
    "_prefixes",
    "_name_sets",
    "_stub_signatures",
    "_callback_values",
    "_handlers",
    "_subscriptions",
    "_compared_keys",
    "_watches",
    "_field_readers",
    "_keyed",
    "_pattern_operands",
    "_dynamic_accesses",
    "_notices",
}

# A program that puts something in every counted table.
EVERY_TABLE = """\
import functools
import typing
import lib
async def coroutine(): pass
coroutine()
class Base:
    def __init__(self, first=None): pass
    def m(self): pass
class C(Base):
    def __getattr__(self, name): return name
    @property
    def p(self): return self
    def __iter__(self):
        yield 1
    def __call__(self, *args): pass
    def go(self):
        super().m()
class D:
    f = classmethod(C())
def gen():
    yield 1
@functools.wraps(gen)
def wrapped(): pass
@functools.lru_cache(maxsize=2)
def memo(): pass
c = C()
Base(*c)
c.p
c.missing
c.go()
D.f()
for x in c: pass
xs = [1, 2]
xs.append(3)
len(xs).bit_length()
sorted(c, key=gen)
open("f", opener=gen)
open("f", "rb", 0)
ys = list(xs)
xs.extend(ys)
lib.run(c)
staticmethod(gen)()
name = "p"
getattr(c, name)
getattr(c, ("P" + name).lower())
def typed(kind: type[Base]): pass
if not isinstance(c, (Base, D)):
    c.go()
def listed(items: typing.Sequence[int]): pass
super(Base, c).m()
class E:
    def idle(self): pass
E()
vars(C)
"""


def test_the_object_count_covers_every_table(tmp_path):
    analysis = analysed(tmp_path, {"main.py": EVERY_TABLE}).program.analysis
    tables = {
        name
        for name, value in vars(analysis).items()
        if isinstance(value, (dict, set, list, deque))
    }

    # A new table must be added to one of the two sets.
    assert tables == COUNTED | NOT_COUNTED
    assert not COUNTED & NOT_COUNTED
    assert [name for name in sorted(COUNTED) if not getattr(analysis, name)] == []
    counted = sum(len(getattr(analysis, name)) for name in COUNTED)
    assert analysis.object_count() == counted


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs SIGALRM")
def test_every_program_terminates(tmp_path):
    for index, source in enumerate([*FIXED, *random_programs()]):
        try:
            with time_limit(SECONDS_PER_PROGRAM):
                generator = analyse(tmp_path / str(index), source)
                generator.output()
        except Exception as error:
            pytest.fail(
                f"{type(error).__name__}: {error} on program {index}:\n{source}"
            )
        count = generator.program.analysis.object_count()
        assert count < MAX_OBJECTS, f"{count} objects for program {index}:\n{source}"


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs SIGALRM")
@pytest.mark.parametrize("index", range(len(GET_FEEDBACK)))
def test_fed_back_get_results_terminate_without_a_cap(tmp_path, index):
    with time_limit(SECONDS_PER_PROGRAM):
        generator = analyse(tmp_path, GET_FEEDBACK[index], cap=None)
        generator.output()
    assert generator.program.analysis.object_count() < MAX_OBJECTS


# How many random programs of each family are also solved in two orders.
ORDER_SAMPLE = 100


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs SIGALRM")
def test_random_programs_give_the_same_call_graph_in_any_order(tmp_path, monkeypatch):
    # Call graphs and MROs do not depend on the solver's order (see
    # tests/test_order_independence.py), also for these programs.
    programs = list(random_programs())[: FAMILIES * ORDER_SAMPLE]
    for index, source in enumerate([*FIXED, *programs]):
        graphs = []
        for order in (solver.Order(), solver.LastInFirstOut()):
            monkeypatch.setattr(solver.Solver, "order", order)
            root = tmp_path / f"{index}-{len(graphs)}"
            with time_limit(SECONDS_PER_PROGRAM):
                generator = analyse(root, source)
                graphs.append(dumps(generator.document()))
        assert graphs[0] == graphs[1], f"program {index}:\n{source}"


# With a small cap on the objects of a node, many nodes of these programs
# saturate: they still end, with few objects, and in any order. A
# regression check: on these programs a cap adds no edge (it may, through
# the steps at a fixpoint; see tests/test_saturation.py).
SATURATION_CAP = 3
SATURATION_SAMPLE = 40


def _edges(generator):
    return {(a, b) for a, callees in generator.output().items() for b in callees}


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs SIGALRM")
def test_random_programs_with_a_small_cap_end_the_same_in_any_order(
    tmp_path, monkeypatch
):
    programs = list(random_programs())[: FAMILIES * SATURATION_SAMPLE]
    for index, source in enumerate([*FIXED, *programs]):
        with time_limit(SECONDS_PER_PROGRAM):
            full = _edges(analyse(tmp_path / f"{index}", source))
        no_rule_sees_what_is_opaque(monkeypatch)
        documents = []
        for order in (solver.Order(), solver.LastInFirstOut()):
            monkeypatch.setattr(solver.Solver, "order", order)
            root = tmp_path / f"{index}-{len(documents)}"
            with time_limit(SECONDS_PER_PROGRAM):
                generator = analyse(root, source, cap=SATURATION_CAP)
                documents.append(dumps(generator.document()))
            count = generator.program.analysis.object_count()
            assert count < MAX_OBJECTS, f"{count} objects, program {index}:\n{source}"
            assert _edges(generator) <= full, f"program {index}:\n{source}"
        assert documents[0] == documents[1], f"program {index}:\n{source}"
        monkeypatch.undo()


# Codex review of the class fixes, N1: the default of an entry point calls a
# method with another receiver, so its receiver saturates at a small cap; a
# completion that inserts into it again is no progress.
SATURATED_ENTRY_RECEIVER = """
class C:
    def m(self): pass
class D: pass
def run(f=C.m):
    f(D())
"""


@pytest.mark.skipif(not hasattr(signal, "setitimer"), reason="needs SIGALRM")
@pytest.mark.parametrize("cap", [1, 2])
def test_a_saturated_entry_receiver_ends_the_completion(tmp_path, cap):
    with time_limit(SECONDS_PER_PROGRAM):
        analyse(tmp_path, SATURATED_ENTRY_RECEIVER, cap=cap).output()
