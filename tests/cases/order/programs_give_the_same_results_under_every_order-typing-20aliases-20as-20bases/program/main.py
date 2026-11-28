
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
