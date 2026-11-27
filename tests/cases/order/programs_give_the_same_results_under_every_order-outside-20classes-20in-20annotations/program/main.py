
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
