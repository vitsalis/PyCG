
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

class Seq:
    def __getitem__(self, index): return Item()
class Meta(type):
    def __iter__(cls): return Iter()
class ByMeta(metaclass=Meta):
    pass
def use(x, y):
    list(itertools.islice(x, 2))
    list(itertools.islice(y, 2))
use(Seq(), ByMeta)
