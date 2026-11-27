
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

import typing_extensions
def concrete(
    a: list[int],
    b: typing.List[int],
    c: typing.Dict[str, int],
    d: typing.Set[int],
    e: typing.FrozenSet[int],
    f: typing.Tuple[int, ...],
    g: tuple[()],
    h: typing.Deque[int],
    i: typing.DefaultDict[str, int],
    j: typing.OrderedDict[str, int],
    k: typing_extensions.OrderedDict,
    l: typing.Counter[str],
    m: typing.ChainMap[str, int],
    n: BaseException,
    o: typing.Any,
    p: types.ModuleType,
):
    for each in (a, b, c, d, e, f, g, h, i, j, k, l, m, n, o, p):
        each.ping()
def classes(
    a: type[list[int]],
    b: typing.Type[typing.List[int]],
    c: type[tuple[()]],
    d: type[dict],
):
    for each in (a, b, c, d):
        each.make()
def sequence(a: typing.Sequence[int], b: type[typing.Sequence[int]]):
    a.ping()
    b.make()
def sets(a: typing.AbstractSet[int], b: type[typing.AbstractSet[int]]):
    a.ping()
    b.make()
