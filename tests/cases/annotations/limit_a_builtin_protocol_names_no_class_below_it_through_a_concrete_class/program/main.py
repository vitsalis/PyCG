
import collections
import types
import typing
class Names(list):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Table(dict):
    def ping(self): pass
class Bag(set):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Frozen(frozenset):
    def ping(self): pass
class Pair(tuple):
    def ping(self): pass
    @classmethod
    def make(cls): pass
class Queue(collections.deque):
    def ping(self): pass
class Default(collections.defaultdict):
    def ping(self): pass
class Ordered(collections.OrderedDict):
    def ping(self): pass
class Tally(collections.Counter):
    def ping(self): pass
class Chain(collections.ChainMap):
    def ping(self): pass
class Failure(Exception):
    def ping(self): pass
class Mock(typing.Any):
    def ping(self): pass
class Lazy(types.ModuleType):
    def ping(self): pass

class Text(str):
    def ping(self): pass
class Row(typing.NamedTuple):
    x: int
    def ping(self): pass

def protocols(
    a: typing.Iterable[int],
    b: typing.Iterator[int],
    c: typing.Collection[int],
    d: typing.Container[int],
    e: typing.Sized,
    f: typing.Hashable,
    g: typing.Reversible[int],
):
    for each in (a, b, c, d, e, f, g):
        each.ping()

def sequence(s: typing.Sequence[int]):
    s.ping()
