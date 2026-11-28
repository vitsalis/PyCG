
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

class Holder:
    pass
def only(x):
    return itertools.islice(x, 2)
def store(holder, x):
    holder.it = itertools.dropwhile(bool, x)
def obtain(x):
    return iter(itertools.takewhile(bool, x))
only(Able())
store(Holder(), Able())
obtain(Able())
