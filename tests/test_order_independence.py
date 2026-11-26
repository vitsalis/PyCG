import itertools
import json
from pathlib import Path

import pytest
from programs import analysed, call_graph, callees, no_rule_sees_what_is_opaque, write
from test_scaling import hub

from pycg.analysis import solver
from pycg.analysis.hierarchy import HIERARCHIES_PER_CLASS_MAX
from pycg.analysis.model import BUILTIN_MODULE, Signature
from pycg.analysis.semantics import Analysis
from pycg.analysis.solver import Constraint, Each
from pycg.formats import dumps
from pycg.pycg import CallGraphGenerator

pytestmark = pytest.mark.slow


def orders():
    return {
        "first in, first out": solver.Order(),
        "last in, first out": solver.LastInFirstOut(),
        "reversed": solver.Reversed(),
        "random 1": solver.Shuffled(1),
        "random 2": solver.Shuffled(2),
    }


TWO_BASES = """
class A:
    def f(self): pass
class B:
    def f(self): pass
class C(A, B):
    pass
C().f()
"""

LATE_FACTORY_BASE = """
import sys
class Allocating:
    def __new__(cls):
        return super().__new__(cls)
class Factory:
    def __new__(cls):
        return Real()
class Real:
    def run(self): pass
def late():
    return Factory
Base = Allocating
if sys.argv:
    Base = late()
class Made(Base):
    def run(self): pass
class Loud(Allocating):
    def __getattr__(self, name): pass
class Quiet(Allocating):
    def run(self): pass
def made():
    Made().run()
def quiet():
    Loud()
    Quiet().run()
"""

LATE_DATA_DESCRIPTOR = """
class Rows:
    def index(self, value): pass
class Pairs:
    def index(self, value): pass
class Setter:
    def __set__(self, obj, value): pass
def setter_base():
    return Setter
class Field(setter_base()):
    def __get__(self, obj, owner=None): return Rows()
class WithField:
    value = Field()
def late():
    return WithField
class Model(late()):
    pass
def use(model):
    model.value = Pairs()
    model.value.index(1)
use(Model())
"""


BASE_FROM_A_CALL = """
class A:
    def f(self): pass
class B:
    def f(self): pass
def base():
    return A
class C(base(), B):
    pass
C().f()
"""

EXTERNAL_BASE_AND_GETATTR = """
import ext
class C(ext.Base):
    def __getattr__(self, name):
        pass
C().f
"""

BASES_ON_A_CYCLE = """
Left = Right = object
class P(Right):
    def p(self): pass
class Q(Left):
    pass
def swap():
    global Left, Right
    Left, Right = P, Q
Q().p()
"""

CYCLE_FORMED_LATE = """
class A:
    def f(self): pass
class B:
    def f(self): pass
Left, Right = A, B
class C(Left):
    pass
class D(Right):
    def f(self): pass
def late():
    global Left, Right
    Left, Right = D, C
D().f()
"""

CANDIDATE_THAT_WAITS = """
import sys
class X:
    def f(self): pass
def make_base():
    return X
class D(make_base()):
    pass
class Y:
    def f(self): pass
class C(D if sys.argv else Y):
    def __getattr__(self, name): pass
C().f()
"""

LONG_CHAIN_OF_CONCATENATIONS = (
    "__all__ = " + " + ".join(f"['n{i}']" for i in range(700)) + "\n"
)


LATE_HOOK_NAME = """
def target(): pass
def put(self, name, value):
    value()
class C: pass
name = f"__setattr__"
setattr(C, name, put)
C().anything = target
"""

HOOKS_AFTER_THE_CLASS = """
def helper(): pass
def target(): pass
def put(self, name, value):
    value()
def remove(self, name):
    helper()
class Hooked:
    def __getattribute__(self, name):
        pass
class Plain:
    pass
class Holder:
    pass
holder = Holder()
holder.base = Hooked
key = "base"
setattr(holder, key, Plain)
class C(holder.base):
    @property
    def value(self):
        helper()
    @value.setter
    def value(self, new):
        new()
    @value.deleter
    def value(self):
        helper()
C.__setattr__ = put
C.__delattr__ = remove
c = C()
c.value
c.value = target
del c.value
"""

BASE_WITHOUT_THE_HOOK = """
def helper(): pass
class Hooked:
    def __getattribute__(self, name):
        pass
class Plain:
    pass
def a(): return b()
def b(): return c()
def c(): return Plain
class Holder:
    pass
holder = Holder()
holder.base = Hooked
holder.base = a()
class C(holder.base):
    @property
    def value(self):
        helper()
def use():
    C().value
"""

MEMBERSHIP_WITH_LATE_CONTAINERS = """
import lib
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True
class Bag:
    def __contains__(self, item): return False
class Holder:
    items = [Item()]
    bag = Bag()
class Marker:
    def __init__(self):
        self.payload = [Item()]
def compare(self, other):
    Holder.late = self.payload
    return False
Marker.__eq__ = compare
def first(values):
    return Marker() in values
lib.run(first)
name = "items"
other = "bag"
Needle() in getattr(Holder, name)
Needle() in getattr(Holder, other)
Needle() in Holder.late
Needle() in []
Needle() in b"abc"
"""

CALLBACKS = """
import lib
class Registry(lib.Registry):
    pass
class Signal(lib.Signal):
    pass
class C:
    value = property(lib.get)
    def __call__(self): pass
class D:
    value = property(lib.a.b.c)
    def __call__(self): pass
class Task(lib.Future):
    pass
def handler(): pass
def listener(): pass
def use(flag):
    registry = Registry()
    registry["x"] = handler
    Signal() + listener
    obj = C() if flag else D()
    obj.value
    lib.register(Task())
    list(map(handler, [1]))
"""

REVIEWS = {
    "r4 iterator class as its own __iter__": """
class It:
    def __init__(self):
        self.done = False
    def __next__(self):
        if self.done:
            raise StopIteration
        self.done = True
        return self
It.__iter__ = It
xs = [It()]
for item in xs:
    xs.extend(item)
    break
""",
    "r4 untracked element": """
class Item:
    def __eq__(self, other):
        return False
Item() in [None]
""",
    "r4 assigned hook": """
def target(): pass
def put(self, name, value):
    value()
class C:
    __setattr__ = put
C().anything = target
""",
    "r5 sequence iterator converted": """
class Needle:
    def __eq__(self, other):
        return True
class Seq:
    def __getitem__(self, index):
        if index == 0:
            return 1
        raise IndexError
Needle() in list(iter(Seq()))
""",
    "r5 empty results": """
class Needle:
    def __eq__(self, other):
        return False
xs = []
xs.extend([])
Needle() in xs
Needle() in [1][:0]
first, *ys = [1]
Needle() in ys
""",
    "r6 late base and external classes": """
class Holder: pass
class A: pass
class Last: pass
holder = Holder()
for base in (int, str, list, tuple, dict, set, bytes, Exception, A):
    holder.base = base
class C(holder.base): pass
getattr(C(), "missing", None)
name = "base"
setattr(holder, name, Last)
""",
    "r6 untracked iterable": """
class Needle:
    def __eq__(self, other):
        return True
xs = []
xs.extend(b"abc")
Needle() in xs
""",
    "r7 partials": """
from functools import partial
def first(): pass
def second(): pass
def invoke(cb): cb()
base = partial(invoke)
for p in (partial(base, first), partial(base, second)):
    p()
class Handler:
    def __init__(self, cb):
        cb()
for p in (partial(Handler, first), partial(Handler, second)):
    p()
def key(value):
    return value
list(map(partial(sorted, key=key), [[1]]))
def f(a, b): a()
partial(f, first)(second)
def old(): pass
def new(): pass
def call(*, cb): cb()
partial(call, cb=old)(cb=new)
def target(): pass
partial(target).func()
""",
    "r7 membership from a late getattr": """
class Item:
    def touch(self): pass
class Needle:
    def __eq__(self, other):
        other.touch()
        return True
class Holder:
    items = [Item()]
name = "items"
Needle() in getattr(Holder, name)
""",
    "r8 analysed function with a model": {
        "typing.py": "def final(f):\n    return f\n",
        "main.py": "from typing import final\n"
        "def target(): pass\n"
        "list(map(final, [target]))\n",
    },
    "whole-branch review: two models extend at one call": """
def a(): pass
def b(): pass
def c(): pass
def run(action, *args):
    action(*args)
xs = []
ys = set()
run(xs.extend, [a])
run(ys.update, [b], [c])
for f in ys:
    f()
""",
    "whole-branch review: a tuple and an items pair at one call": """
def a(): pass
def b(): pass
def c(): pass
def make(factory, *args):
    return factory(*args)
d = {"key": a}
make(d.items)
items = make(tuple, (a, b, c))
items[-1]()
""",
    "final review: zip of two arities at one call": """
class M(type):
    def __iter__(cls): return iter(())
class Factory:
    __call__ = staticmethod(zip)
class C(metaclass=M):
    __new__ = Factory()
def make(factory): return factory(())
make(zip)
make(C)
""",
    "final review: protocols of classes and results tested for truth": """
class Truth:
    def __bool__(self): return True
class Low:
    def __lt__(self, other): return Truth()
    def __eq__(self, other): return Truth()
class Answers(type):
    def __contains__(cls, value): return Truth()
    def __bool__(cls): return False
    def __getitem__(cls, index): raise IndexError
    def __setitem__(cls, key, value): pass
    def __hash__(cls): return 0
class Iterates(type):
    def __iter__(cls): return iter([Low()])
    def __await__(cls):
        yield
def late():
    return Answers
class Asked(metaclass=late()): pass
class Searched(metaclass=Iterates): pass
class Holder:
    value = Low()
class Pending:
    def __await__(self):
        yield
class Manager:
    def __aenter__(self): return Pending()
    def __aexit__(self, *args): return Pending()
async def use(value):
    async with Manager():
        pass
    await Searched
    Low() < Low() < Low()
    Low() in Asked
    Low() in Searched
    if Asked:
        pass
    for _ in Asked:
        pass
    Asked[1] = 2
    {Asked: 1}[Searched]
    "%*s" % (1, Low())
    match value:
        case Holder.value:
            pass
        case 0.5:
            pass
    match 0.5:
        case Holder.value:
            pass
""",
}

MODELS_AT_ONE_SITE = """
import collections
def a(): pass
def b(): pass
def c(): pass
def make(factory, *args):
    return factory(*args)
xs = [a]
ys = {b}
fs = frozenset([c])
d = {"k": a}
q = collections.deque([b])
counts = collections.Counter([c])
made = [
    make(collections.OrderedDict, [("k", b)]),
    make(collections.defaultdict, list, {"k": c}),
    make(collections.defaultdict, make),
    make(collections.Counter, [a]),
    make(collections.deque, [c]),
    make(q.popleft),
    make(q.extendleft, [a]),
    make(counts.update, [b]),
    make(list, (a, b)),
    make(tuple, (a, b, c)),
    make(set, [b]),
    make(frozenset, [c]),
    make(dict, [("k", b)]),
    make(iter, [c]),
    make(iter, a, None),
    make(xs.copy),
    make(ys.copy),
    make(fs.copy),
    make(d.copy),
    make(d.keys),
    make(d.values),
    make(d.items),
    make(xs.extend, [b]),
    make(ys.update, [c], [a]),
    make(d.update, {"j": c}),
    make(xs.pop),
    make(next, iter([b])),
]
for result in made:
    result[0]()
    result[-1]()
    for f in result:
        f()
"""

TYPED_OUTSIDE_VALUES = """
import collections
import copy
import re
import sys
class Widget:
    def render(self): pass
def make():
    return Widget()
def pick(items):
    return sorted(items)[0]
handlers = [make]
pick(handlers)().render()
copy.copy(make()).render()
for match in re.finditer("a", "aa"):
    match.group().upper()
cache = collections.OrderedDict()
cache.copy().move_to_end("k")
text = " a ".strip()
(text + "b").split()
sys.stderr.write(text)
try:
    pass
except ValueError as error:
    error.with_traceback(None)
"""

OUTSIDE_BASES = """
import abc
import collections.abc
import typing
class Mixin:
    def helper(self): pass
class Task(abc.ABC, Mixin):
    def run(self):
        self.sleep()
        self.helper()
        return self.__class__()
class Store(collections.abc.MutableMapping):
    def __getitem__(self, key): pass
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __iter__(self): pass
    def __len__(self): pass
class Request(Task):
    def __init__(self):
        super().__init__()
class Options(typing.TypedDict):
    size: int
Options(size=1).get("size")
Store().popitem()
Request().run().helper()
"""

LIBRARY_CALLS = """
import contextlib
import heapq
import logging
import threading
class Worker(threading.Thread):
    def run(self):
        self.step()
    def step(self): pass
class Item:
    def __lt__(self, other): pass
class Handler(logging.Handler):
    def emit(self, record):
        record.getMessage()
class Resource:
    def __enter__(self): return self
    def __exit__(self, *args): pass
Worker().start()
heapq.heappush([], Item())
logging.getLogger("x").addHandler(Handler())
with contextlib.ExitStack() as stack:
    stack.enter_context(Resource())
"""

ANNOTATIONS = {
    "kinds.py": """
import typing
from dataclasses import dataclass as frozen_class
def use(x: "KindT", *more: "KindT", **named: "list[Kind]"):
    x.run()
    for each in more:
        each.run()
class Kind:
    def run(self): pass
    @classmethod
    def make(cls): pass
class Fast(Kind):
    def run(self): pass
KindT = Kind | typing.Callable[[], None]
Tree = typing.Union[Kind, list["Tree"]]
@frozen_class(frozen=True)
class Holder:
    kind: "KindT"
    tree: Tree
    def go(self):
        self.kind.run()
        self.tree.run()
""",
    "main.py": """
import typing
import kinds
if typing.TYPE_CHECKING:
    from kinds import KindT, Kind
def build(kind: "type[Kind]", items: "dict[str, KindT]") -> None:
    kind.make()
    items["a"].run()
class Record(typing.NamedTuple):
    kind: "KindT"
    def go(self):
        self.kind.run()
""",
}

OUTSIDE_CLASSES_IN_ANNOTATIONS = """
import collections.abc
import typing
def base():
    return BASE
class Late(base()):
    async def __anext__(self): pass
    def close(self): pass
    @classmethod
    def make(cls): pass
class Later(Late):
    def close(self): pass
class Bag(collections.abc.Set):
    def __contains__(self, x): pass
    def __iter__(self): return iter([])
    def __len__(self): return 0
    def close(self): pass
def use(
    it: typing.AsyncIterator[int],
    kind: type[typing.AsyncIterable],
    items: typing.AbstractSet[str],
):
    it.close()
    kind.make()
    items.close()
BASE = typing.AsyncIterator
"""

PROTOCOL_BASES = {
    "main.py": """
import collections.abc
import typing
import mod
def base():
    return BASE
class Late(base()):
    def __next__(self): pass
    def ping(self): pass
class Later(Late):
    def ping(self): pass
def use(items: typing.Iterable[str], sized: typing.Sized):
    items.ping()
    sized.ping()
BASE = collections.abc.Iterator
""",
    "mod.py": "class Peek:\n    def ping(self): pass\n"
    "class Measured:\n    def ping(self): pass\n",
    "mod.pyi": "from typing import Iterator, Sized\n"
    "class Peek(Iterator[int]): ...\nclass Measured(Sized): ...\n",
}

ANNOTATED_ASSIGNMENTS = """
import typing
class Holder:
    def __init__(self, given):
        self.items: "list[KindT]" = list(given)
        self.kind: type[Kind] = given
    def go(self):
        for item in self.items:
            item.run()
        self.kind.make()
        current.run()
def base():
    return BASE
class Kind(base()):
    def __getitem__(self, index): pass
    def __len__(self): return 0
    def run(self): pass
    @classmethod
    def make(cls): pass
class Fast(Kind):
    def run(self): pass
KindT = Kind | None
BASE = typing.Sequence
current: typing.Optional[typing.Sequence[int]] = None
"""

PATTERNS = {
    "handlers.py": """
def cmd_start(): pass
def cmd_stop(): pass
""",
    "main.py": """
import handlers
def base():
    return Base
class Base:
    def on_open(self): pass
class Handler(base()):
    def on_close(self): pass
    def __init__(self):
        self.on_extra = handlers.cmd_start
    def dispatch(self, event, kind):
        getattr(self, "on_" + event)()
        getattr(self, "on_%s" % kind)()
        getattr(handlers, f"cmd_{event}")()
        getattr(self, converted(event).lower())()
        getattr(handlers, converted(kind).upper().lower())()
def converted(kind):
    return "ON_" + kind
def late(self): pass
Handler.on_late = late
Handler.On_Mixed = late
def first():
    Handler().dispatch(second(), None)
def second():
    return "close"
""",
}
PATTERN_KEYS = """
def on_open(): pass
def on_close(): pass
def other(): pass
def fallback(): pass
def unknown(): pass
TABLE = {"on_open": on_open, "other": other}
def k1(): return k2()
def k2(): return k3()
def k3(): return "on_close"
def fill():
    TABLE[k1()] = on_close
def put(key):
    TABLE[key] = unknown
def dispatch(table, event):
    table["on_%s" % event]()
    table.get(f"{event}_x", fallback)()
def first():
    dispatch(second(), "x")
def second():
    return TABLE
first()
"""
DEFINITIONS = """
import ext
class Node:
    def __init__(self, parent=None):
        self.parent = parent
    def walk(self):
        return self.parent
def f(): pass
def g(): pass
def run(node, handler=f):
    while node:
        handler()
        try:
            node = node.walk()
            if ext.flag:
                handler = node
                continue
            handler = g
        except ValueError as error:
            handler = error
            break
        finally:
            done = handler
    else:
        done = None
    with ext.lock:
        node = Node(node)
    return node, done
class C:
    method = f
    for item in (f, g):
        method = item
    method = staticmethod(method)
result = run(Node(Node()))
result[0].walk()
C.method()
"""

JUMPS_THROUGH_FINALLY = """
import ext
def f(): pass
def g(): pass
def run():
    handler = f
    while True:
        try:
            try:
                if ext.flag:
                    continue
                break
            finally:
                handler = g
        finally:
            if ext.done:
                return handler
    handler()
run()()
"""

NAMESPACE_CLASS_BODY = """
class Base:
    def method(self): pass
class Field:
    def __set_name__(self, owner, name): pass
class Child(Base):
    locals()
    field = Field()
    def method(self): pass
    def __init_subclass__(cls): pass
    if False:
        def other(self): pass
class Grandchild(Child):
    pass
Grandchild().method()
"""

REFLECTION = """
import inspect
def action(): pass
def late(self): pass
class Base:
    def inherited(self): pass
def base():
    return Base
class Item(base()):
    def own(self): pass
    @property
    def computed(self):
        return action
def store(cls, obj):
    cls.late = late
    obj.callback = action
item = Item()
store(Item, item)
for name, member in inspect.getmembers(Item):
    member(item)
for name, member in inspect.getmembers(item):
    member()
for name, value in vars(Item).items():
    value(item)
for value in item.__dict__.values():
    value()
Item.__dict__["own"](item)
"""

DEAD_MODULE_NAMES = {
    "lib.py": """
from typing import TYPE_CHECKING
def actual(): pass
def __getattr__(name):
    return actual
if False:
    def absent(): pass
if TYPE_CHECKING:
    from typing import Sequence
""",
    "facade.py": """
from lib import *
def other(): pass
def __getattr__(name):
    return other
""",
    "main.py": """
import lib, facade
lib.absent()
lib.Sequence()
facade.absent()
facade.actual()
""",
}

MATCH_PATTERNS = """
import ext
def f(): pass
def g(): pass
class Point:
    __match_args__ = ("x", "y")
    def __init__(self, x, y):
        self.x = x
        self.y = y
    @property
    def both(self):
        return (self.x, self.y)
class Later(Point):
    pass
Later.__match_args__ = ("y", "x")
class Items:
    def __getitem__(self, key):
        return g
    def __len__(self):
        return 2
def run(value):
    match value:
        case Point(first, second, both=[left, right]) | Later(second, first):
            first()
            left()
        case [head, *tail] if head:
            tail[0]()
        case {"key": handler, **rest}:
            handler()
            rest["other"]()
run(Point(f, g))
run(Later(g, f))
run(Items())
run({"key": f, "other": g})
"""

NEW_RETURNS_A_LATE_SUBCLASS = """
class Shape:
    def __new__(cls, kind):
        if kind:
            return object.__new__(Circle)
        return super().__new__(cls)
def a(): return b()
def b(): return Shape
class Circle(a()):
    def __init__(self, kind):
        pass
def make():
    Shape("circle")
"""

METACLASSES = """
class BaseMeta(type):
    def create(cls):
        return cls()
    def describe(cls):
        cls.hook()
class SubMeta(BaseMeta):
    def describe(cls):
        super().describe()
def a(): return b()
def b(): return SubMeta
def base(): return Root
class Root(metaclass=BaseMeta):
    @staticmethod
    def hook(): pass
class Model(base(), metaclass=a()):
    def __init__(self): pass
Chosen = BaseMeta
def choose():
    global Chosen
    Chosen = SubMeta
class Picked(metaclass=Chosen):
    @staticmethod
    def hook(): pass
class Leaf(Model):
    def __init__(self): pass
SubMeta.describe(Model)
Leaf.create()
Picked.describe()
"""

THIRD_PARTY_STUBS = """
import requests
import yaml
from google.protobuf import json_format
class Client(requests.Session):
    def fetch(self, url):
        return self.get(url).json(object_hook=self.hook)
    def hook(self, pairs): pass
with Client() as client:
    client.fetch("u")
    client.get("u").headers.get("k")
yaml.add_constructor("!x", Client.hook)
yaml.SafeLoader("a").get_single_data()
json_format.MessageToJson(None).upper()
"""
ANALYSED_MODULE_NAMED_LIKE_A_STUB = {
    "toml.py": """
class Document:
    def run(self): pass
def loads(text):
    return Document()
""",
    "main.py": """
import toml
import requests
toml.loads("a = 1").run()
requests.get("u").json()
""",
}

OUTSIDE_CALL_RESULTS = """
import lib
import lib.sub
import re
def job(): pass
@lib.task
def decorated(): pass
@lib.task()
def made(): pass
app = lib.App()
deco = app.route("/")
@deco
@lib.first()
class View:
    def get(self): pass
@app.register
def registered(): pass
made()
View().get()
registered()
class Task(lib.Base):
    def run(self):
        return lib.make()
class Late(Task().run()):
    pass
async def fetch():
    value = await lib.fetch()
    value.run()
x = lib.make()
while x:
    x.visit()[0].run()
    x = x.next()()
with lib.open() as handle:
    handle.read()
lib.Cls().run(job)
lib.sub.helper(lib.ITEMS[0].close())
decorated().run()
Late().anything()
re.compile("a").match("a").group()
try:
    pass
except lib.Error as error:
    error.details()
"""

PROGRAMS = {
    "outside call results": OUTSIDE_CALL_RESULTS,
    "third-party stubs": THIRD_PARTY_STUBS,
    "analysed module named like a stub": ANALYSED_MODULE_NAMED_LIKE_A_STUB,
    "definitions": DEFINITIONS,
    "jumps through finally": JUMPS_THROUGH_FINALLY,
    "class body that uses its namespace": NAMESPACE_CLASS_BODY,
    "namespaces read by reflection": REFLECTION,
    "class body that uses its namespace reads the module": """
def f(): pass
def g(): pass
class C:
    locals()
    f()
    f = g
""",
    "names of a module in code that cannot run": DEAD_MODULE_NAMES,
    "metaclasses": METACLASSES,
    "new returns a late subclass": NEW_RETURNS_A_LATE_SUBCLASS,
    "match patterns": MATCH_PATTERNS,
    "late hook name": LATE_HOOK_NAME,
    "hooks after the class": HOOKS_AFTER_THE_CLASS,
    "base without the hook": BASE_WITHOUT_THE_HOOK,
    "membership with late containers": MEMBERSHIP_WITH_LATE_CONTAINERS,
    "callbacks": CALLBACKS,
    "map reached with receivers": """
def f(): pass
class Caller:
    __call__ = map
class X:
    pass
class Y:
    pass
X.__new__ = Y
Y.__new__ = X
Y.__new__ = Caller()
Y([f])
for g in Caller()(lambda h: h, [f]):
    g()
""",
    "map with an unpacked argument": """
def f(): pass
def g(): pass
def second(a, b): return b
def run(*rest):
    for x in map(second, [f], *rest):
        x()
run([g], [f])
""",
    "comparisons with and without a key": """
class Key:
    def __gt__(self, other): return False
class Item:
    def __lt__(self, other): return False
    def rank(self): return Key()
def key(item): return item.rank()
def order(items, *rest, **options):
    items.sort(key=key)
    sorted(*rest, **options)
    return max(items, *rest, key=Item)
order([Item()], [Item()], key=key)
order([Item()], [Item()])
class Meta(type):
    def __lt__(cls, other): return False
    def __reversed__(cls): return iter([])
class Ranked(metaclass=Meta): pass
sorted([Ranked, Item], key=lambda c: c)
reversed(Ranked)
""",
    "members of outside bases at the bound": """
import concurrent.futures
import multiprocessing
bases = [multiprocessing.reduction.AbstractReducer]
class Reducer(bases[0]): pass
bases[0] = Reducer.ForkingPickler
class Task(concurrent.futures._base.Future): pass
Task().done()
Reducer().dump(1)
""",
    **REVIEWS,
    "models at one site": MODELS_AT_ONE_SITE,
    "dict lookups": """
import collections
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
def look(table, key):
    table.get(key)
    table.pop(key, None)
    table.setdefault(key, 1)
    key in table
    return table
ordered = collections.OrderedDict()
ordered[Key()] = 1
look(ordered, Key()).move_to_end(Key())
look({Key(): 2}, Key())
""",
    "type variables that no argument binds": """
import argparse
class Parser(argparse.ArgumentParser):
    def run(self): pass
def parsers():
    return LATE
subparsers = parsers().add_subparsers()
subparsers.add_parser("info").add_argument("x")
subparsers.add_parser("run", parents=[Parser()]).run()
LATE = argparse.ArgumentParser()
""",
    "annotations": ANNOTATIONS,
    "outside classes in annotations": OUTSIDE_CLASSES_IN_ANNOTATIONS,
    "builtin protocols through late and stub bases": PROTOCOL_BASES,
    "library operations sharing an origin": "import itertools\n"
    "class MetaA(type):\n    def __iter__(cls): return iter(())\n"
    "class MetaB(type):\n    def __iter__(cls): return iter(())\n"
    "class Factory:\n    __call__ = staticmethod(itertools.chain)\n"
    "class One(metaclass=MetaA):\n    __new__ = Factory()\n"
    "class Two(metaclass=MetaB):\n    __new__ = Factory()\n"
    "def use(factory):\n    return list(factory(()))\nuse(One)\nuse(Two)\n",
    "annotated assignments": ANNOTATED_ASSIGNMENTS,
    "patterns": PATTERNS,
    "dict reads by pattern keys": PATTERN_KEYS,
    "class members in pattern reads": """
from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    def __new__(cls, value):
        obj = str.__new__(cls, "pre_" + value)
        obj._value_ = value
        return obj
    A = "a"
class F(str, Enum):
    B = "pre_" + suffix()
def hit(): pass
def other(): pass
def read(**table):
    kind = "a"
    table["pre_" + kind]()
read(**{E.A: hit})
class Holder:
    table = {E.A: hit, "zz": other}
def late(kind):
    Holder.table["pre_" + kind]()
    Holder.table[F.B]()
    Holder.table[F.B.lower()]()
late("a")
""",
    "pattern operands decided last": """
class App:
    def run(self): pass
class Request:
    def __init__(self, environ):
        self.environ = environ
    def __getattr__(self, name):
        return self.environ["ext.%s" % name]
    def use(self):
        self.config.run()
    def lone(self, key):
        self.environ["ext." + key].run()
Request({"app": App()})
""",
    "filter with late functions and elements": """
class Verdict:
    def __bool__(self): return True
class Item:
    def keep(self): return Verdict()
    def run(self): pass
def pick():
    return CHOSEN
def items():
    return ITEMS
def use():
    for item in filter(pick(), items()):
        item.run()
    filter(filter, [items()])
CHOSEN = Item.keep
ITEMS = [Item()]
use()
""",
    "re.sub with late replacements": """
import re
class Replacer:
    def method(self, m): return ""
def pick():
    return CHOSEN
def pattern():
    return PATTERN
def use():
    re.sub("a", pick(), "abc")
    pattern().subn(repl=pick(), string="abc")
    re.sub("a", re.sub, "abc")
CHOSEN = "x"
CHOSEN = Replacer().method
CHOSEN = lambda m: m
PATTERN = re.compile("a")
use()
""",
    "open with late modes": """
import pathlib
def mode():
    return MODE
def size():
    return SIZE
def nothing(given):
    return open("p", given)
def use():
    open("p", mode()).close()
    with open("p", mode(), size()) as f:
        f.read()
    pathlib.Path("p").open(mode=mode(), buffering=size()).write(b"")
    nothing(NOTHING).close()
MODE = "r"
MODE = "wb"
MODE = "r+b"
MODE = "rw"
SIZE = 0
SIZE = -1
SIZE = int()
use()
""",
    "open with modes from late defaults and aliases": """
class C:
    mode = "wb"
    def run(self, mode="rb", size=0):
        open("p", mode, size).close()
        open("p", C.mode).close()
def method():
    return "run"
def uncalled(mode="r+b"):
    open("p", mode).close()
def empty(mode):
    open("p", mode).flush()
getattr(C(), method())()
""",
    "containers converted with late elements": """
class Item:
    def __repr__(self): return "r"
class Key:
    def __repr__(self): return "k"
def late():
    return LATE
def show(xs):
    repr(xs)
    f"{xs}"
    "%s" % (xs,)
box = [late()]
box.append(box)
show(box)
show({Key(): (late(),)})
LATE = Item()
""",
    "formats that arrive late": """
class Item:
    def __str__(self): return "s"
    def __repr__(self): return "r"
def fmt():
    return LATE
def use(item):
    text = fmt()
    text % (item,)
    text %= {"k": item}
LATE = "%(k)s %r"
use(Item())
""",
    "library closures that arrive late": """
import contextlib, functools
def deco():
    return LATE
@deco()
def managed():
    yield
@functools.lru_cache(maxsize=SIZE)
def cached(n): pass
def use():
    with managed():
        cached(1)
SIZE = 3
LATE = contextlib.contextmanager
""",
    "computed names with other values": """
import ext
class C:
    def a(self): pass
    def b(self): pass
    selector = "b"
def late():
    return getattr(C, "selector")
def run(obj, option: str = "a"):
    getattr(obj, option)()
    getattr(obj, late() if ext.flag else ext.name)()
run(C(), late())
""",
    "receivers of methods that no analysed code calls": """
class Base:
    def run(self):
        self.step()
    def step(self): pass
    def helper(*args):
        args[0].step()
class Child(Base):
    def step(self): pass
class Other(Base):
    pass
Child()
Base().helper()
""",
    "two bases": TWO_BASES,
    "a late base whose new gives another object": LATE_FACTORY_BASE,
    "base from a call": BASE_FROM_A_CALL,
    "a store through a data descriptor that late bases give": LATE_DATA_DESCRIPTOR,
    "external base and __getattr__": EXTERNAL_BASE_AND_GETATTR,
    "bases on a cycle": BASES_ON_A_CYCLE,
    "cycle formed late": CYCLE_FORMED_LATE,
    "candidate that waits": CANDIDATE_THAT_WAITS,
    "long __all__": LONG_CHAIN_OF_CONCATENATIONS,
    "hub": hub(20),
    "typed outside values": TYPED_OUTSIDE_VALUES,
    "stub tuples of two lengths": """
import os.path
for split in (os.path.split, os.path.splitroot):
    head = split("/tmp/file")[0]
    head.upper()
""",
    "outside bases": OUTSIDE_BASES,
    "library calls": LIBRARY_CALLS,
    "type of an object": """
from typing import Sequence
class Meta(type):
    def describe(cls): pass
class Base(metaclass=Meta):
    def __init__(self): pass
    def copy(self):
        return type(self)()
class Child(Base):
    def __init__(self): pass
def late():
    return Child()
def run(fields: Sequence[Base | type[Base]], name="x"):
    type(late()).describe()
    type(name)().upper()
    type(name, (Base,), {})()
    for field in fields:
        type(field)()
late().copy()
""",
    "slots": """
from typing import Protocol
def work(): pass
class Wrapped(Protocol):
    @property
    def __wrapped__(self): pass
    def __getattr__(self, name): return work
def base():
    return Wrapped
class Wrapper(base()):
    __slots__ = ("__wrapped__", "__store")
    def __init__(self, f):
        self.__wrapped__ = f
        self.__store = f
    def run(self):
        self.__wrapped__()
        self.__store()
        self.missing()
Wrapper(work).run()
""",
    "abstract by a metaclass with two bases": """
import abc, sys
class PlainMeta(type): pass
class AbstractMeta(abc.ABCMeta): pass
class Meta(PlainMeta if sys.argv else AbstractMeta): pass
class C(metaclass=Meta):
    @abc.abstractmethod
    def f(self): pass
    def __init__(self): pass
C()
""",
    "abstract classes": """
import abc
from collections.abc import Mapping
def meta():
    return abc.ABCMeta
class Base(metaclass=meta()):
    def __new__(cls):
        return super().__new__(cls)
    def __init__(self): pass
    def run(self):
        self.step()
    @abc.abstractmethod
    def step(self): pass
class Middle(Base):
    pass
class Leaf(Middle):
    def step(self): pass
class Concrete(abc.ABC):
    def step(self): pass
def pick(flag):
    return Base if flag else Concrete
class Either(pick(True)):
    def __init__(self): pass
class Partial(Mapping):
    def __init__(self): pass
    def __getitem__(self, key): pass
for kind in (Base, Middle, Leaf, Either, Partial):
    kind().step()
""",
    "two-argument super": """
class Meta(type):
    def describe(cls): pass
class Base:
    def run(self): pass
def base():
    return Base
class Late(base()):
    def run(self): pass
class Model(metaclass=Meta):
    pass
class Other:
    def run(self): pass
def pick(cls, x):
    super(cls, x).run()
for x in (Late(), Other(), Late, Model):
    pick(Base, x)
    pick(Meta, x)
""",
    "call arity": """
class Needs:
    def __init__(self, value): pass
    def __call__(self, event): pass
class Empty:
    def __init__(self): pass
def one(a): pass
def keyword(*, key): pass
def late():
    return [Needs, Empty, one, keyword]
def run(kind, f):
    kind()(1)
    f(key=1)
    f(1)
for kind in late():
    run(kind, kind)
""",
    "override receivers": """
class Base:
    def run(self):
        self.step()
    def step(self): pass
    @classmethod
    def make(cls):
        cls.step(None)
class Child(Base):
    def run(self):
        super().run()
    def step(self): pass
def base():
    return Base
class Late(base()):
    def step(self): pass
    @classmethod
    def make(cls): pass
Child()
Late()
""",
    "typing aliases as bases": """
import typing
from typing import AbstractSet
class A(typing.Iterator[int]):
    def __next__(self): pass
class C(AbstractSet):
    def __contains__(self, x): return False
    def __iter__(self): yield from ()
    def __len__(self): return 0
class D(A, C):
    pass
D().__iter__()
D().isdisjoint(())
""",
    "subscripted aliases": """
from typing import Generic, Optional, TypeVar, Union
T = TypeVar("T")
class Box(Generic[T]):
    def run(self): pass
class Bag(Generic[T]):
    def run(self): pass
AnyBox = Union[Box[T], Bag[T]]
Rec = Union[Bag[T], "Rec[T]"]
def use(box: Optional[AnyBox[int]], rec: Rec[int]):
    box.run()
    rec.run()
""",
    "defaultdict factories": """
import collections
def f(): pass
def g(): pass
def make(cb=f):
    return cb
class Node:
    def same(self):
        return self
    def visit(self): pass
factories = [make]
d = collections.defaultdict(factories[0])
d["a"]()
factories.append(Node().same)
d["b"].visit()
make(g)
""",
    "hashing and comparing elements": """
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
    def __lt__(self, other): return False
class Sized:
    def __iter__(self): return iter([])
    def __len__(self): return 0
def use(items, keys, table, pairs):
    {*items}
    set(items).union(keys)
    keys.discard(Key())
    dict.fromkeys(items)
    table.update(pairs)
    sorted(pairs)
    list(LATE)
    return pairs == [(1, Key())] and table != {Key(): 2}
items = []
keys = set()
table = {}
pairs = []
use(items, keys, table, pairs)
items.append(Key())
keys.add(Key())
pairs.append((1, Key()))
table[Key()] = 1
LATE = Sized()
""",
    "unpacked keys and container families": """
import collections
class Key:
    def __hash__(self): return 0
    def __eq__(self, other): return False
    def __lt__(self, other): return False
sources = []
def copy():
    for source in sources:
        {*source, Key()}
def compare(a, b, outer):
    for inner in outer:
        [[a]] == [inner]
        collections.deque([a]) == inner
        sorted([[a], inner])
copy()
compare(Key(), Key(), LATE)
sources.extend([{Key()}, {Key(): 1}, [Key()]])
LATE = [(Key(),), [Key()], collections.deque([Key()])]
""",
    "defaultdict reads and function names": """
import collections
class Cache:
    def get(self): pass
    def clear(self): pass
def read(table):
    return table["k"]
def run(obj, command):
    getattr(obj, command.__name__)()
factories = []
first = collections.defaultdict(factories[0])
read(first)()
read(first.copy())()
read(collections.defaultdict(Cache)).get()
factories.append(Cache().clear)
commands = []
def use():
    for command in commands:
        run(LATE, command)
use()
commands.append(Cache.get)
def renamed(): pass
renamed.__name__ = "clear"
commands.append(renamed)
LATE = Cache()
""",
    "lookups by any key": """
def f(): pass
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
table = {}
table.get(1)
table[f] if f in table else None
keys = [1]
table.pop(keys[0], None)
table[Key()] = 0
keys.append(Key())
""",
    "deque indexes": """
import collections
def f(): pass
def g(): pass
q = collections.deque([None])
keys = [0]
q[keys[0]] = f
q.appendleft(None)
q[1]()
q[-1] = g
keys.append(1)
q[keys[-1]]()
""",
    "percent of a container": """
class Item:
    def __repr__(self): return "item"
    def __str__(self): return "s"
formats = []
items = []
table = {}
for fmt in formats:
    fmt % items
    fmt % table
formats.append("%s")
formats.append("%(a)s")
items.append(Item())
table["a"] = Item()
items.append(items)
""",
    "percent of one value by position": """
class Item:
    def __repr__(self): return "item"
    def __str__(self): return "s"
formats = []
values = []
for fmt in formats:
    for value in values:
        try:
            fmt % value
        except (TypeError, ValueError):
            pass
formats.extend(["%*s", "%d%s", "%s%s", "%s%(a)s", "%(a)s%s"])
values.extend([[Item()], Item(), {"a": Item()}])
""",
    "percent syntax": """
class Item:
    def __repr__(self): return "item"
    def __str__(self): return "s"
formats = []
values = []
for fmt in formats:
    for value in values:
        try:
            fmt % value
        except (TypeError, ValueError):
            pass
formats.extend(["%((a))s", "%.s %r", "%(a)*s", "%s %y %r", "%d%(a)s", "%ls %(a)s"])
formats.extend([b"%r %a", b"%((a))r", b"%s %r"])
formats.extend(["%r %.2147483648s %r", b"%r %9223372036854775808r %r"])
values.extend([(Item(), Item()), {"(a)": Item(), "a": Item()}, [Item()]])
values.append({b"(a)": Item()})
""",
    "aliases that subscript themselves": """
from typing import List, TypeAlias, TypeVar, Union
T = TypeVar("T")
class Box:
    def run(self): pass
type Loop[X] = Loop[X] | Box
type Ping[X] = Pong[X] | Box
type Pong[X] = Ping[X]
Left = Union[Box, List[T]]
Right: TypeAlias = Left[T]
Left = Right[T]
def use(a: Loop[int], b: Pong[int], c: Left[int], d: "Right[int]"):
    a.run()
    b.run()
    c.run()
    d.run()
""",
    "iterator bases": """
import collections.abc
def f(): pass
class Items(collections.abc.Iterator):
    def __next__(self): return f
class Stream(collections.abc.AsyncIterator):
    async def __anext__(self): return f
def items(source):
    for item in source:
        item()
async def stream(source):
    async for item in source.__aiter__():
        item()
items(Items())
items(Items().__iter__())
stream(Stream())
""",
    "async generators": """
def f(): pass
async def wait(x): return x
async def produce():
    yield f
async def use():
    for g in [produce(), (await wait(x) for x in [f]), (x async for x in produce())]:
        async for h in g.__aiter__():
            h()
        await g.aclose()
""",
    "returned elements of args": """
def f(): pass
def g(): pass
def h(): pass
class Base:
    def __new__(cls, *args):
        return args[0]
    def pick(self, *args):
        return args[1]
    def me(*args):
        return args[0]
class A(Base):
    def run(self): pass
class B(Base):
    def run(self): pass
def first(*args):
    return args[0]
def last(*args):
    return args[-1]
def use(items):
    first(f, g)()
    first(*items)()
    first(*[h], g)()
    A(B()).run()
    B(A()).me().run()
    Base.pick(None, f, g, h)()
    last(f)()
use([g, h])
last(h)
""",
    "call sites": """
import lib
class Lock:
    def __enter__(self): pass
    def __exit__(self, *args): pass
    def __iter__(self): return iter([])
    def __format__(self, spec): return ""
    @property
    def p(self): pass
def make(): return Lock()
def run(callback, name):
    with make() as lock:
        for x in make():
            callback(x)
    getattr(lock, name)()
    lib.a.b.c()
    return lock.p, f"{lock}", [y for y in list(Lock())]
""",
    "class tests": """
import collections, ext
class A:
    def f(self): pass
def base(): return A
class B(base()):
    def f(self): pass
class C(ext.Base, collections.OrderedDict):
    def f(self): pass
class D:
    def f(self): pass
def kinds(): return (later(), str)
def later(): return D
KINDS = (B, C)
def make(): return [A(), B(), C(), D(), "s", b"b", 1, A, B]
def use(flag, kind=None):
    late = kinds()
    for x in make():
        if isinstance(x, late):
            x.f()
        elif not isinstance(x, KINDS):
            x.f()
            x.upper()
        elif isinstance(x, (A, bytes)) and flag:
            x.decode()
        if not isinstance(x, (dict, kind)):
            continue
        x.f()
        if issubclass(x, A):
            x().f()
        while isinstance(x, collections.OrderedDict):
            x.f()
            x = x.next
        x.f()
""",
    "class tests with empty and late classes": """
import abc
def f(x, classes):
    if not isinstance(x, classes):
        x.lower()
    if isinstance(x, classes):
        x.upper()
f("s", ())
def target(): pass
def h(x, classes):
    if isinstance(x, classes):
        x()
h(target, ())
def meta(): return abc.ABCMeta
def base(): return abc.ABC
class Late(metaclass=meta()):
    def f(self): pass
class Later(base()):
    def f(self): pass
class Plain:
    def f(self): pass
def g(y=Plain(), z=Late()):
    for v in (y, z):
        if isinstance(v, Late):
            v.f()
        if not isinstance(v, (Later, Plain)):
            v.f()
""",
    "class tests of containers and generators": """
import collections
from collections.abc import Sequence
class A:
    def f(self): pass
class B:
    def f(self): pass
class Items(list):
    def f(self): pass
def made():
    yield A()
async def run():
    return B()
def kinds(): return (tuple, collections.OrderedDict)
def parse(arg, *args, declared: list[A] = None, **kwargs):
    classes = kinds()
    for x in (arg, args, kwargs, declared):
        if isinstance(x, classes):
            for v in x:
                v.f()
        elif not isinstance(x, (list, dict)):
            x.f()
        if isinstance(x, Sequence):
            x[0].f()
        first, *rest = x
        if isinstance(rest, tuple):
            rest[0].f()
parse([A()][0:], B())
parse((B(),) + (A(),), k=A())
parse(made())
parse(run())
parse(Items())
parse(dict([(A(), B())]).copy())
parse(collections.OrderedDict(a=A()))
parse(x for x in [B()])
for pair in zip([A()], [B()]):
    parse(pair)
""",
    "class tests of iterators, declared containers and enum members": """
from enum import Enum
def target(): pass
class L(list):
    def __getitem__(self, index): return tuple(self)
    def __add__(self, other): return tuple(self)
class D(dict):
    def items(self): return [[k, self[k]] for k in self]
def run():
    it = iter([target])
    if not isinstance(it, list):
        next(it)()
def use(x: list, d: dict):
    x.append(target)
    for y in (x[:], x + [], x * 2):
        if not isinstance(y, list):
            y[0]()
    d[target] = 0
    for pair in d.items():
        if isinstance(pair, list):
            pair[0]()
class E(Enum):
    A = [target]
    def __iter__(self): return iter(self.value)
def members(x=E.A):
    if not isinstance(x, list):
        for callback in x:
            callback()
run()
use(L(), D())
""",
    "class tests of classes of values and generator members": """
from enum import Enum
def target(): pass
class M: pass
def gen():
    yield target
class E(M, Enum):
    A = [target]
    B = gen()
    def __iter__(self):
        return iter(self.value)
z = E.A.__class__(E.A)
if not isinstance(z, list):
    for cb in z:
        cb()
g = E.B
if isinstance(g, M):
    for cb in g:
        cb()
def tested(v: list, w=[target]):
    if not isinstance(w, v.__class__):
        w[0]()
class S(str, M, Enum):
    T = "target"
class Holder:
    @staticmethod
    def target(): pass
def names(n=S.T, m="other"):
    for name in (n, m, n):
        if isinstance(name, M):
            getattr(Holder, name)()
class Box:
    value = []
Base = Box.value.__class__
class Left(Base):
    pass
class Right(list):
    def append(self, x):
        pass
class Both(Left, Right):
    pass
Both().append(0)
""",
    "the stub of a module": {
        "main.py": """
import shapes
def base():
    return shapes.Shape
class Late(base()):
    def area(self): pass
def pick(item, *more):
    item.area()
    for each in more:
        each.area()
class Canvas:
    shape = None
    def draw(self):
        self.shape.area()
current = None
def run():
    current.area()
    pick(Late())
""",
        "main.pyi": """
from collections.abc import Iterator
from typing import ClassVar, overload
from shapes import Shape, Square
@overload
def pick(item: Square) -> None: ...
@overload
def pick(item: Shape, *more: Iterator[Shape]) -> None: ...
class Canvas:
    shape: ClassVar[Shape | None]
current: "Square | Iterator[Late]"
""",
        "shapes.py": """
from collections.abc import Iterator
class Shape:
    def area(self): pass
class Square(Shape, Iterator):
    def area(self): pass
    def __next__(self): pass
""",
    },
    "import as reads the package attribute": {
        "a/__init__.py": "from . import b\nclass R:\n    def hit(self): pass\nb = R()",
        "a/b.py": "def hit(): pass\n",
        "main.py": "import a.b as c\nc.hit()\n",
    },
    "package attribute named by a submodule": {
        "pkg/__init__.py": "class T:\n    def run(self): pass\nX = T\n",
        "pkg/X.py": "",
        "main.py": """
import pkg
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from pkg import X
def use(value: "X"):
    value.run()
""",
    },
}

SNIPPETS = (
    Path(__file__).resolve().parent.parent
    / "evaluation"
    / "micro-benchmark"
    / "snippets"
)


def document_text_and_points_to(monkeypatch, order, entry, root):
    monkeypatch.setattr(solver.Solver, "order", order)
    generator = CallGraphGenerator([str(entry)], str(root))
    generator.analyze()
    return dumps(generator.document()), generator.output_points_to()


def assert_same_under_every_order(monkeypatch, entry, root, names=None):
    expected = None
    for name, order in orders().items():
        if names is not None and name not in names:
            continue
        found = document_text_and_points_to(monkeypatch, order, entry, root)
        if expected is None:
            expected = found
        assert found == expected, name


def test_the_reflection_program_reads_the_namespaces(tmp_path):
    graph = call_graph(tmp_path, {"main.py": REFLECTION})

    assert {"main.Item.own", "main.Base.inherited", "main.late"} <= set(
        callees(graph, "main")
    )


@pytest.mark.parametrize("program", PROGRAMS)
def test_programs_give_the_same_results_under_every_order(
    tmp_path, monkeypatch, program
):
    files = PROGRAMS[program]
    if isinstance(files, str):
        files = {"main.py": files}
    for name, source in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(source)
    assert_same_under_every_order(monkeypatch, tmp_path / "main.py", tmp_path)


EXPECTED_CALLEES = {
    "a store through a data descriptor that late bases give": (
        "main.use",
        "main.",
        ["main.Field.__get__", "main.Rows.index", "main.Setter.__set__"],
    ),
    "a late base whose new gives another object": (
        "main.made",
        "main.",
        [
            "main.Allocating.__new__",
            "main.Factory.__new__",
            "main.Loud.__getattr__",
            "main.Made.run",
            "main.Quiet.run",
            "main.Real.run",
        ],
    ),
    "library operations sharing an origin": (
        "main.use",
        "main.",
        ["main.MetaA.__iter__", "main.MetaB.__iter__"],
    ),
    "builtin protocols through late and stub bases": (
        "main.use",
        "",
        ["main.Late.ping", "main.Later.ping", "mod.Measured.ping", "mod.Peek.ping"],
    ),
    "library closures that arrive late": (
        "main.use",
        "",
        [
            "_functools._lru_cache_wrapper.__call__",
            "contextlib.contextmanager.helper",
            "main.cached",
            "main.managed",
        ],
    ),
    "dict reads by pattern keys": (
        "main.dispatch",
        "main.",
        ["main.fallback", "main.on_close", "main.on_open", "main.unknown"],
    ),
    "re.sub with late replacements": (
        "main.use",
        "main.",
        ["main.<lambda1>", "main.Replacer.method", "main.pattern", "main.pick"],
    ),
    "open with late modes": (
        "main.use",
        "io.",
        [
            "io.BufferedRandom.close",
            "io.BufferedRandom.read",
            "io.BufferedRandom.write",
            "io.BufferedReader.close",
            "io.BufferedWriter.close",
            "io.BufferedWriter.read",
            "io.BufferedWriter.write",
            "io.FileIO.read",
            "io.FileIO.write",
            "io.TextIOWrapper.close",
            "io.TextIOWrapper.read",
            "io.TextIOWrapper.write",
        ],
    ),
    "open with modes from late defaults and aliases": (
        "main.C.run",
        "io.",
        ["io.BufferedWriter.close", "io.FileIO.close"],
    ),
}


@pytest.mark.parametrize("program", EXPECTED_CALLEES)
def test_programs_call_what_their_rule_gives(tmp_path, program):
    caller, prefix, expected = EXPECTED_CALLEES[program]
    files = PROGRAMS[program]
    if isinstance(files, str):
        files = {"main.py": files}
    graph = call_graph(tmp_path, files)

    found = [c for c in callees(graph, caller) if c.startswith(prefix)]
    assert found == expected


@pytest.mark.parametrize(
    "snippet",
    sorted(path for path in SNIPPETS.glob("*/*") if path.is_dir()),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_benchmark_cases_give_the_same_results_under_every_order(monkeypatch, snippet):
    fast_subset_of_orders = ("first in, first out", "last in, first out", "random 1")
    assert_same_under_every_order(
        monkeypatch, snippet / "main.py", snippet, fast_subset_of_orders
    )


ENTRY_ORDERS = {
    "builtin protocols through late and stub bases": PROTOCOL_BASES,
    "bases from two modules": {
        "a.py": "class A: pass\n",
        "b.py": "class B: pass\n",
        "main.py": "from a import A\nfrom b import B\n"
        "def choose(flag):\n    if flag: return A\n    return B\n"
        "class C(choose(True)): pass\n",
    },
    "an exhaustive order across modules": {
        "a.py": "class A1: pass\nclass A2: pass\nclass A3: pass\n",
        "b.py": "class B1: pass\nclass B2: pass\nclass B3: pass\n",
        "main.py": "from a import A1, A2, A3\nfrom b import B1, B2, B3\n"
        "def pick(i):\n    return [A1, B1, A2, B2, A3, B3][i]\n"
        "class C(pick(0), pick(1)): pass\n",
    },
    "modules that fail": {
        "a.py": "def f(): pass\n",
        "broken.py": "def oops(:\n",
        "latin.py": b"x = '\xe9'\n",
        "main.py": "import broken, latin\nfrom a import f\nf()\n",
    },
    "a package and a module file of one name": {
        "a.py": "def f(): pass\nf()\n",
        "a/__init__.py": "def g(): pass\ng()\n",
        "main.py": "import a\n",
    },
    "a module file and binaries of one name": {
        "a.py": "def f(): pass\nf()\n",
        "a.so": b"",
        "a.abi3.so": b"",
        "main.py": "import a\na.f()\n",
    },
    "a stub beside a module file": {
        "a.py": "def f(): pass\nf()\n",
        "a.pyi": "def h() -> None: ...\nh()\n",
    },
    "a namespace package beside a module file": {
        "a.py": "def f(): pass\nf()\n",
        "a/x.py": "def g(): pass\ng()\n",
        "main.py": "import a.x\n",
    },
    "files that only an entry point names": {
        "a.pyw": "def f(): pass\nf()\n",
        "a": "def g(): pass\ng()\n",
        "main.py": "import a\n",
    },
    "a file name with a dot": {
        "a/__init__.py": "",
        "a/b.py": "def f(): pass\nf()\n",
        "a.b.py": "def g(): pass\ng()\n",
    },
    "__main__ files": {
        "__main__.py": "def f(): pass\nf()\n",
        "pkg/__init__.py": "",
        "pkg/__main__.py": "def g(): pass\ng()\n",
    },
    "classes of one name in two modules": {
        "a/__init__.py": "class b:\n    class C:\n        def f(self): pass\n",
        "a/b.py": "class C:\n    def g(self): pass\n",
        "main.py": "import a.b\n",
    },
}


def whole_output(root, entries, **options):
    generator = CallGraphGenerator(
        [str(root / entry) for entry in entries], str(root), **options
    )
    generator.analyze()
    return {
        "document": dumps(generator.document()),
        "assignment graph": generator.output_points_to(),
    }


def assert_same_for_every_order_of_entry_modules(root, orders_of_entries):
    first, *others = orders_of_entries
    expected = whole_output(root, first)
    for entries in others:
        assert whole_output(root, entries) == expected, entries


@pytest.mark.parametrize("program", ENTRY_ORDERS)
def test_programs_give_the_same_results_for_every_order_of_entry_modules(
    tmp_path, program
):
    files = ENTRY_ORDERS[program]
    write(tmp_path, files)
    orders_of_entries = list(itertools.permutations(files))
    assert_same_for_every_order_of_entry_modules(tmp_path, orders_of_entries)


@pytest.mark.parametrize(
    "snippet",
    sorted(
        path
        for path in SNIPPETS.glob("*/*")
        if path.is_dir() and len(list(path.rglob("*.py"))) > 1
    ),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_benchmark_cases_give_the_same_results_for_two_orders_of_entry_modules(
    snippet,
):
    entries = sorted(str(path.relative_to(snippet)) for path in snippet.rglob("*.py"))
    orders_of_entries = [entries, entries[::-1]]
    assert_same_for_every_order_of_entry_modules(snippet, orders_of_entries)


ONE_NAME = {
    "a module and a function of one name": {
        "p/__init__.py": "def helper(): pass\ndef retry():\n    helper()\n",
        "p/retry.py": "def g(): pass\ng()\n",
    },
    "two functions of one name in a package and a module": {
        "a/__init__.py": "def b():\n    def f(x):\n        x()\n",
        "a/b.py": 'import json; x = json.loads("null")\ndef f():\n        x()\n',
    },
    "two classes of one name": ENTRY_ORDERS["classes of one name in two modules"],
}


@pytest.mark.parametrize("program", ONE_NAME)
def test_definitions_of_one_name_give_one_document_under_every_order(
    tmp_path, monkeypatch, program
):
    files = ONE_NAME[program]
    write(tmp_path, files)
    texts = set()
    for entries in itertools.permutations(files):
        for order in orders().values():
            monkeypatch.setattr(solver.Solver, "order", order)
            paths = [str(tmp_path / entry) for entry in entries]
            generator = CallGraphGenerator(paths, str(tmp_path))
            generator.analyze()
            texts.add(dumps(generator.document()))

    assert len(texts) == 1


def test_one_file_given_several_ways_is_one_module_in_every_order(tmp_path):
    root = tmp_path / "root"
    write(root, {"a.py": "def f(): pass\nf()\n", "sub/b.py": "import a\n"})
    (root / "link.py").symlink_to(root / "a.py")
    (tmp_path / "outside.py").write_text("def h(): pass\nh()\n")
    entries = ["a.py", "a.py", "sub/../a.py", "link.py", "sub/b.py", "../outside.py"]

    assert_same_for_every_order_of_entry_modules(
        root, list(itertools.permutations(entries))
    )
    document = json.loads(whole_output(root, entries)["document"])
    assert sorted(document["modules"]) == ["a", "link", "sub.b"]


def test_directories_and_trailing_separators_give_one_document_in_every_order(
    tmp_path,
):
    write(
        tmp_path,
        {"__init__.py": "x = 1\n", "pkg/__init__.py": "", "pkg/mod.py": "f = 1\n"},
    )
    entries = ["pkg", "pkg/", "pkg/__init__.py", "pkg/mod.py/", "__init__.py"]

    assert_same_for_every_order_of_entry_modules(
        tmp_path, list(itertools.permutations(entries))
    )
    document = json.loads(whole_output(tmp_path, entries)["document"])
    assert sorted(document["modules"]) == ["pkg", "pkg.mod"]


def test_extension_modules_are_the_same_for_every_order_of_entry_modules(tmp_path):
    write(
        tmp_path,
        {
            "pkg/__init__.py": "from ._a import f\nfrom ._b import g\nf()\n",
            "pkg/mod.py": "from . import _b\n_b.h()\n",
            "pkg/_a.cpython-312-darwin.so": b"",
            "pkg/_a.so": b"",
            "pkg/_b.abi3.so": b"",
        },
    )
    sources = ["pkg/__init__.py", "pkg/mod.py"]

    assert_same_for_every_order_of_entry_modules(
        tmp_path, list(itertools.permutations(sources))
    )


def test_a_base_expression_orders_its_classes_by_module(tmp_path):
    write(tmp_path, ENTRY_ORDERS["bases from two modules"])
    document = whole_output(tmp_path, ["main.py", "b.py", "a.py"])["document"]
    classes = json.loads(document)["definitions"]

    assert classes["main.C"]["mro"] == ["main.C", "a.A", "b.B", "<builtin>.object"]


@pytest.fixture(params=["first in, first out", "last in, first out"])
def order(request, monkeypatch):
    monkeypatch.setattr(solver.Solver, "order", orders()[request.param])


def test_lookup_ignores_a_base_that_a_later_base_overrides(tmp_path, order):
    graph = call_graph(tmp_path, {"main.py": TWO_BASES})

    assert callees(graph, "main") == ["main.A.f"]


def test_lookup_waits_for_a_base_that_a_call_gives(tmp_path, order):
    graph = call_graph(tmp_path, {"main.py": BASE_FROM_A_CALL})

    assert callees(graph, "main") == ["main.A.f", "main.base"]


def test_getattr_is_not_called_when_an_external_base_may_define_the_name(
    tmp_path, order
):
    graph = call_graph(tmp_path, {"main.py": EXTERNAL_BASE_AND_GETATTR})

    assert callees(graph, "main") == ["ext.Base.__init__"]


def test_classes_on_a_cycle_of_bases_see_each_other(tmp_path, order):
    generator = analysed(tmp_path, {"main.py": BASES_ON_A_CYCLE})

    assert callees(generator.output(), "main") == ["main.P.p"]
    classes = generator.document()["definitions"]
    assert classes["main.P"]["mro"] == ["main.P", "main.Q", "<builtin>.object"]
    assert classes["main.Q"]["mro"] == ["main.Q", "main.P", "<builtin>.object"]


def test_cycle_that_forms_after_the_classes_are_ready_is_exhaustive(tmp_path, order):
    graph = call_graph(tmp_path, {"main.py": CYCLE_FORMED_LATE})

    assert callees(graph, "main") == ["main.A.f", "main.B.f", "main.D.f"]


def test_lookup_ignores_a_candidate_base_until_its_own_bases_are_known(tmp_path, order):
    graph = call_graph(tmp_path, {"main.py": CANDIDATE_THAT_WAITS})

    assert callees(graph, "main") == ["main.X.f", "main.Y.f", "main.make_base"]


def test_object_as_a_base_means_the_base_may_be_absent(tmp_path, order):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import sys
            class A:
                def f(self): pass
            class C(A if sys.argv else object):
                def __getattr__(self, name):
                    pass
            C().f()
            """
        },
    )

    assert callees(graph, "main") == ["main.A.f", "main.C.__getattr__"]


def test_base_that_never_gets_a_value_is_decided_absent(tmp_path, order):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class C(undefined):
                def f(self): pass
                def g(self):
                    self.f()
            C().g()
            """
        },
    )

    assert callees(graph, "main") == ["main.C.g"]
    assert callees(graph, "main.C.g") == ["main.C.f"]


def test_base_decided_absent_that_arrives_later_adds_a_hierarchy(tmp_path, order):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            class Base:
                def f(self): pass
            def make(base=Base):
                class C(base):
                    def __getattr__(self, name): pass
                    def g(self):
                        self.f()
                return C
            """
        },
    )

    assert callees(graph, "main.make.C.g") == [
        "main.Base.f",
        "main.make.C.__getattr__",
    ]


def test_exhaustive_order_finds_what_every_hierarchy_would(tmp_path, order):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
            import sys
            class X0:
                def __getattr__(self, name): pass
            class Y0:
                def f(self): pass
            class X1: pass
            class Y1: pass
            class X2: pass
            class Y2: pass
            class X3: pass
            class Y3: pass
            class C(
                X0 if sys.argv else Y0,
                X1 if sys.argv else Y1,
                X2 if sys.argv else Y2,
                X3 if sys.argv else Y3,
            ):
                pass
            C().f()
            """
        },
    )

    candidate_bases_count = 2
    base_expressions_count = 4
    hierarchies_count = candidate_bases_count**base_expressions_count
    assert hierarchies_count > HIERARCHIES_PER_CLASS_MAX
    assert callees(graph, "main") == ["main.X0.__getattr__", "main.Y0.f"]


def two_classes_defining_f(analysis):
    classes = []
    for name in ("A", "B"):
        cls = analysis.new_class(f"mod.{name}", "mod", ["f"], [])
        method = analysis.function(f"mod.{name}.f", "mod", Signature(["self"]), {})
        analysis.add_object(analysis.field(cls, "f"), method)
        classes.append(cls)
    return classes


def lookup_of_f(analysis, cls):
    return analysis.lookup(cls, "f", cls)


def names_of(analysis, node):
    return [obj.name for obj in analysis.solver.objects(node)]


class CallOnFirstObject(Constraint):
    def __init__(self, action):
        self.action = action

    def apply(self, obj):
        if self.action is not None:
            action, self.action = self.action, None
            action()


def collected_additions_scenario():
    analysis = Analysis()
    a, b = two_classes_defining_f(analysis)
    slot_a, slot_b = analysis.node(), analysis.node()
    c = analysis.new_class("mod.C", "mod", [], [slot_a, slot_b])
    found = lookup_of_f(analysis, c)
    source = analysis.node()
    analysis.add_object(source, b)

    def act():
        analysis.add_object(slot_a, a)
        analysis.add_edge(source, slot_b)

    trigger = analysis.node()
    analysis.solver.attach(trigger, CallOnFirstObject(act))
    for marker in (analysis.const("x"), analysis.const("y")):
        analysis.add_object(trigger, marker)
    analysis.solve()
    return names_of(analysis, found)


def constants_scenario():
    analysis = Analysis()
    a, b = two_classes_defining_f(analysis)
    slot_b = analysis.constant(b)
    slot_a = analysis.constant(a)
    c = analysis.new_class("mod.C", "mod", [], [slot_a, slot_b])
    found = lookup_of_f(analysis, c)
    analysis.solve()
    return names_of(analysis, found)


def numbering_scenario():
    analysis = Analysis()
    a, b = two_classes_defining_f(analysis)
    analysis.add_object(analysis.node(), a)
    slot_a, slot_b = analysis.node(), analysis.node()
    c = analysis.new_class("mod.C", "mod", [], [slot_a, slot_b])
    found = lookup_of_f(analysis, c)
    trigger = analysis.node()
    analysis.add_object(trigger, b)
    analysis.add_object(trigger, a)
    forward = Each(lambda obj: analysis.add_object(slot_a if obj is a else slot_b, obj))
    analysis.solver.attach(trigger, forward)
    analysis.solve()
    return names_of(analysis, found)


@pytest.mark.parametrize(
    "scenario", [collected_additions_scenario, constants_scenario, numbering_scenario]
)
def test_bases_that_arrive_in_any_order_give_the_lookup_of_the_whole_hierarchy(
    monkeypatch, scenario
):
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        assert scenario() == ["mod.A.f"], name


def test_python_hook_counts_once_any_hierarchy_leaves_it(tmp_path, order):
    graph = call_graph(tmp_path, {"main.py": BASE_WITHOUT_THE_HOOK})

    assert callees(graph, "main.use") == [
        "main.C.value",
        "main.Hooked.__getattribute__",
    ]
    assert callees(graph, "main.Hooked.__getattribute__") == ["main.C.value"]


def test_two_models_that_extend_at_one_call_each_iterate_their_input(tmp_path, order):
    program = REVIEWS["whole-branch review: two models extend at one call"]
    graph = call_graph(tmp_path, {"main.py": program})

    assert "main.c" in callees(graph, "main")


def test_a_tuple_and_an_items_pair_at_one_call_keep_their_lengths(tmp_path, order):
    program = REVIEWS["whole-branch review: a tuple and an items pair at one call"]
    graph = call_graph(tmp_path, {"main.py": program})

    assert "main.c" in callees(graph, "main")


def repeated_bases_scenario():
    analysis = Analysis()
    a = analysis.new_class("mod.A", "mod", [], [])
    b = analysis.new_class("mod.B", "mod", [], [])
    p, q, u, v = (analysis.node() for _ in range(4))
    c = analysis.new_class(
        "mod.C", "mod", [], [p, q, analysis.constant(a), analysis.constant(b)]
    )
    analysis.add_edge(u, p)
    analysis.add_edge(v, q)
    root = analysis.external(f"{BUILTIN_MODULE}.object")
    for node, obj in ((p, root), (q, b), (u, a), (v, root)):
        analysis.add_object(node, obj)
    analysis.solve()
    return [base.name for base in c.mro]


def test_hierarchies_that_arrive_in_any_order_give_the_same_mro(monkeypatch):
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        assert repeated_bases_scenario() == ["mod.C", "mod.A", "mod.B"], name


def test_exhaustive_lookup_after_a_class_ignores_what_that_class_defines():
    analysis = Analysis()
    b = analysis.new_class("mod.B", "mod", ["__repr__"], [])
    method = analysis.function("mod.B.__repr__", "mod", Signature(["self"]), {})
    analysis.add_object(analysis.field(b, "__repr__"), method)
    slot = analysis.node()
    for index in range(9):
        middle = analysis.new_class(f"mod.D{index}", "mod", [], [analysis.constant(b)])
        analysis.add_object(slot, middle)
    c = analysis.new_class("mod.C", "mod", ["__str__"], [slot])
    found = analysis.lookup(c, "__repr__", c, after=c, unless=("__str__",))
    analysis.solve()

    assert c.exhaustive
    assert names_of(analysis, found) == ["mod.B.__repr__"]


SATURATING = {
    "lazy library objects past the cap": {
        "main.py": "import itertools\n"
        + "".join(
            f"class S{i}:\n    def __iter__(self): return self\n"
            f"    def __next__(self): return self\n"
            for i in range(5)
        )
        + "def late():\n    return [S0(), S1(), S2(), S3(), S4()]\n"
        "def use(xs):\n    it = itertools.chain(*xs)\n    for x in it:\n        x()\n"
        "use([S0()])\nuse(late())\n",
    },
    "stub bases past the cap": {
        "main.py": PROTOCOL_BASES["main.py"]
        + "".join(f"def h{i}(): pass\n" for i in range(5))
        + "def run(handler):\n    handler()\n"
        + "for handler in [h0, h1, h2, h3, h4]:\n    run(handler)\n",
        "mod.py": PROTOCOL_BASES["mod.py"] + "class Wide:\n    def ping(self): pass\n",
        "mod.pyi": PROTOCOL_BASES["mod.pyi"]
        + "from typing import Container, Hashable\n"
        "class Wide(Iterator[int], Sized, Hashable, Container[int]): ...\n",
    },
    "a registry through one parameter": {
        "main.py": "".join(f"def h{i}(): pass\n" for i in range(5))
        + "HANDLERS = [h0, h1, h2, h3, h4]\n"
        "def run(handler):\n    handler()\n"
        "for handler in HANDLERS:\n    run(handler)\n",
    },
    "a hub fed from two modules": {
        "pkg/__init__.py": "",
        "pkg/funcs.py": "def f1(): pass\ndef f2(): pass\ndef f3(): pass\n"
        "def f4(): pass\nclass Item:\n    def act(self): pass\n",
        "pkg/hub.py": "def run(fn, item):\n    fn()\n    item.act()\n    return fn\n",
        "pkg/a.py": "from pkg.funcs import f1, f2, Item\nfrom pkg.hub import run\n"
        "def get1(): return f1\ndef get2(): return f2\n"
        "run(get1(), Item())\nx = run(get2(), Item())\n",
        "pkg/b.py": "from pkg.funcs import f3, f4, Item\nfrom pkg.hub import run\n"
        "def get3(): return f3\ndef get4(): return f4\n"
        "y = run(get3(), Item())\nrun(get4(), Item())\n",
    },
    "a cycle of fields": {
        "main.py": "def f0(): pass\ndef f1(): pass\ndef f2(): pass\ndef f3(): pass\n"
        "class Box: pass\na = Box()\nb = Box()\n"
        "def put(box, value):\n    box.v = value\n"
        "put(a, f0)\nput(a, f1)\nput(b, f2)\nput(b, f3)\n"
        "def swap():\n    a.v = b.v\n    b.v = a.v\n"
        "def use(box):\n    box.v()\n"
        "swap()\nuse(a)\nuse(b)\n",
        "other.py": "from main import use, Box\nuse(Box())\n",
    },
    "a setter called through the hook of each instance": {
        "main.py": "def f(): pass\n"
        + "".join(f"def g{i}(): pass\n" for i in range(3))
        + "def sink(x):\n    x()\n"
        "class Base:\n"
        "    def __init__(self):\n        self.value = f\n"
        "    def install(self):\n        Base.value = Field.data\n"
        "    def __getattr__(self, name):\n        pass\n"
        "class Maker:\n    def __call__(self):\n        Model()\n"
        "def use(maker: Maker):\n    maker()\n"
        "class Model(Base, Maker):\n"
        "    def __call__(self):\n        super().__init__()\n"
        "class Field:\n"
        "    @property\n    def data(self):\n        pass\n"
        "    @data.setter\n    def data(self, new):\n        sink(new)\n"
        + "".join(
            f"class A{i}:\n    def next(self):\n        return B{i}()\n"
            f"class B{i}:\n    def next(self):\n        return C{i}()\n"
            f"class C{i}:\n    def next(self):\n        return g{i}\n"
            for i in range(3)
        )
        + "".join(f"sink(A{i}().next().next().next())\n" for i in range(3))
        + "def run(handler):\n    handler()\n"
        "for handler in [f, g0, g1, g2]:\n    run(handler)\n",
    },
    "a sequence iterated through the lookup of each instance": {
        "main.py": "def f(): pass\ndef g(): pass\n"
        + "".join(f"def h{i}(): pass\n" for i in range(2))
        + "def sink(x):\n    x()\n"
        "class S:\n"
        "    def __init__(self, cb):\n        self.cb = cb\n"
        "    def __getitem__(self, i):\n        return self.cb\n"
        "a = S(f)\nb = S(g)\n"
        "for item in a:\n    pass\n"
        "class A0:\n    def next(self):\n        return A1()\n"
        "class A1:\n    def next(self):\n        return a\n"
        "class B0:\n    def next(self):\n        return B1()\n"
        "class B1:\n    def next(self):\n        return b\n"
        "def run(s):\n    for e in s:\n        sink(e)\n"
        "run(A0().next().next())\nrun(B0().next().next())\n"
        + "".join(
            f"class H{i}:\n    def next(self):\n        return I{i}()\n"
            f"class I{i}:\n    def next(self):\n        return J{i}()\n"
            f"class J{i}:\n    def next(self):\n        return h{i}\n"
            for i in range(2)
        )
        + "".join(f"sink(H{i}().next().next().next())\n" for i in range(2))
        + "def call(handler):\n    handler()\n"
        "for handler in [f, g, h0, h1]:\n    call(handler)\n",
    },
}


@pytest.mark.parametrize("program", SATURATING)
def test_programs_that_saturate_give_the_same_results_in_every_order(
    tmp_path, monkeypatch, program
):
    no_rule_sees_what_is_opaque(monkeypatch)
    files = SATURATING[program]
    write(tmp_path, files)
    entries = [name for name in files if not name.endswith("__init__.py")]
    expected = None
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        for entries_order in itertools.permutations(entries):
            found = whole_output(tmp_path, entries_order, cap=3)
            if expected is None:
                expected = found
            assert found == expected, (name, entries_order)
    calls = json.loads(expected["document"])["calls"]
    causes = {site.get("unresolved") for sites in calls.values() for site in sites}
    assert "saturated" in causes


@pytest.mark.parametrize("cap", [1, 3, None])
def test_stub_bases_give_the_same_results_under_every_order_and_cap(
    tmp_path, monkeypatch, cap
):
    write(tmp_path, SATURATING["stub bases past the cap"])
    expected = None
    for name, order in orders().items():
        monkeypatch.setattr(solver.Solver, "order", order)
        for entries in itertools.permutations(["main.py", "mod.py"]):
            found = whole_output(tmp_path, entries, cap=cap)
            if expected is None:
                expected = found
            assert found == expected, (name, entries)
