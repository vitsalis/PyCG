
import collections.abc
import typing
class Bag(collections.abc.Set):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
class Pool(collections.abc.MutableSet):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def add(self, x): pass
    def discard(self, x): pass
    def tick(self): pass
class Names(list):
    def tick(self): pass
class Store(collections.abc.MutableMapping):
    def __getitem__(self, key): pass
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
def ordered(items: typing.Sequence[str]):
    items.tick()
def sets(items: typing.AbstractSet[str]):
    items.tick()
def mutable(items: typing.MutableSet[str]):
    items.tick()
def table(rows: typing.Mapping[str, int]):
    rows.tick()
