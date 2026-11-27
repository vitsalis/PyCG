
import collections.abc
import dataclasses
import typing
from typing import AsyncIterator
class Chain(collections.abc.AsyncIterator):
    async def __anext__(self): pass
    def close(self): pass
    @classmethod
    def make(cls): pass
class Borrowed(AsyncIterator[int]):
    async def __anext__(self): pass
    def close(self): pass
class Scoped(Borrowed):
    def close(self): pass
    @classmethod
    def make(cls): pass
class Peer:
    def __aiter__(self): return self
    async def __anext__(self): pass
    def close(self): pass
    @classmethod
    def make(cls): pass

T = typing.TypeVar("T")
AnyIterable = typing.Union[typing.AsyncIterable[T], typing.Iterable[T]]
def plain(it: AsyncIterator[int]):
    it.close()
def bare(it: collections.abc.AsyncIterator):
    it.close()
def wider(it: typing.AsyncIterable[int]):
    it.close()
def optional(it: typing.Optional[AsyncIterator[int]]):
    it.close()
def union(it: AsyncIterator[int] | int):
    it.close()
def aliased(it: AnyIterable[int]):
    it.close()
def quoted(it: "AsyncIterator[int]"):
    it.close()
def star(*its: AsyncIterator[int]):
    for it in its:
        it.close()
def named(**its: AsyncIterator[int]):
    for it in its.values():
        it.close()
def listed(its: list[AsyncIterator[int]]):
    for it in its:
        it.close()
@dataclasses.dataclass
class Holder:
    it: AsyncIterator[int]
    def go(self):
        self.it.close()
