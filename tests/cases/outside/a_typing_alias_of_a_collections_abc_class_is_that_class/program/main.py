
import typing
import typing_extensions
import collections.abc
from typing import AbstractSet, AsyncIterator
class A(typing.Iterator):
    def __next__(self): pass
class B(AsyncIterator):
    async def __anext__(self): pass
class C(AbstractSet):
    def __contains__(self, x): return False
    def __iter__(self): yield from ()
    def __len__(self): return 0
class D(typing.Iterator[int]):
    def __next__(self): pass
class E(typing_extensions.Mapping):
    def __getitem__(self, key): pass
    def __iter__(self): yield from ()
    def __len__(self): return 0
class F(collections.abc.Iterator):
    def __next__(self): pass
class G(typing.IO):
    pass
def iterator(): A().__iter__()
def async_iterator(): B().__aiter__()
def abstract_set(): C().isdisjoint(())
def subscripted(): D().__iter__()
def through_typing_extensions(): E().keys()
def collections_abc(): F().__iter__()
def typing_only(): G().close()
