
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

class MetaA(type):
    def __iter__(cls): return iter(())
class MetaB(type):
    def __iter__(cls): return iter(())
class Factory:
    __call__ = staticmethod(itertools.chain)
class One(metaclass=MetaA):
    __new__ = Factory()
class Two(metaclass=MetaB):
    __new__ = Factory()
def use(factory):
    return list(factory(()))
use(One)
use(Two)
