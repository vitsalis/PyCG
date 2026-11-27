
import collections.abc
import typing
class Box(collections.abc.Collection):
    def __contains__(self, x): pass
    def __iter__(self): pass
    def __len__(self): pass
    def tick(self): pass
class Countdown(collections.abc.Iterator):
    def __next__(self): pass
    def tick(self): pass
class Backwards(collections.abc.Reversible):
    def __iter__(self): pass
    def __reversed__(self): pass
    def tick(self): pass
class Key(collections.abc.Hashable):
    def __hash__(self): return 0
    def tick(self): pass
class Sized(collections.abc.Sized):
    def __len__(self): return 0
    def tick(self): pass
class Line(collections.abc.Sequence):
    def __getitem__(self, i): pass
    def __len__(self): return 0
    def tick(self): pass
def iterable(a: typing.Iterable[int]):
    a.tick()
def iterator(b: collections.abc.Iterator):
    b.tick()
def collection(c: typing.Collection[int]):
    c.tick()
def container(d: collections.abc.Container):
    d.tick()
def sized(e: typing.Sized):
    e.tick()
def hashable(f: collections.abc.Hashable):
    f.tick()
def reversible(g: typing.Reversible[int]):
    g.tick()
