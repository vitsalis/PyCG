
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

class Meta(type):
    def make(cls): pass
def anything(x: object, k: type, c: type[object], m: typing.Type[type]):
    x.close()
    k.make()
    c.make()
    m.make()
def alias(t: typing.Type):
    t.make()
