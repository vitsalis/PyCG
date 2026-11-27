
import collections
import functools
import heapq
import itertools
import math
import operator
class Item:
    def ping(self): pass
class Other:
    def ping(self): pass
class Iter:
    def __iter__(self): return self
    def __next__(self): return Item()
class Able:
    def __iter__(self): return Iter()
    def __len__(self): return 0
class OtherIter:
    def __iter__(self): return self
    def __next__(self): return Other()
class OtherAble:
    def __iter__(self): return OtherIter()

def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.zip_longest)
class C(metaclass=M):
    __new__ = Factory()
class Delay:
    def __call__(self, x): return x
def use(factory):
    it = factory([b, b])
    first, *more = next(it)
    first()
    for pair in Delay()(it):
        pair[1]()
use(itertools.zip_longest)
use(C)
