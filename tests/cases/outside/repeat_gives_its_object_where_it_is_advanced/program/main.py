
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

def make():
    return itertools.repeat(Item(), 2)
def use(items):
    for item in items:
        item.ping()
    for other in itertools.chain(itertools.repeat(Other())):
        other.ping()
use(make())
