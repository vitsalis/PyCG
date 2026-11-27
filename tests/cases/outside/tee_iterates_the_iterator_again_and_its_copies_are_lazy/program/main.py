
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

def split(x):
    first, second = itertools.tee(x)
    return first
def use(it):
    list(it)
use(split(Able()))
