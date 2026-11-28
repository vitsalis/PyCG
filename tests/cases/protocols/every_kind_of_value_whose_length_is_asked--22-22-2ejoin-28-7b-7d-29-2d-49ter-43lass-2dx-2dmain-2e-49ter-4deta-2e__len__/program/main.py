
import collections.abc
class Seq:
    def __getitem__(self, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(self): return 2
class SeqMeta(type):
    def __getitem__(cls, index):
        if index >= 2:
            raise IndexError
        return "a"
    def __len__(cls): return 2
class SeqClass(metaclass=SeqMeta): pass
class IterMeta(type):
    def __iter__(cls): return cls
    def __next__(cls): raise StopIteration
    def __len__(cls): return 0
class IterClass(metaclass=IterMeta): pass
class Back:
    def __getitem__(self, index):
        raise IndexError
    def __len__(self): return 0
    def __reversed__(self): return iter([])
class View(collections.abc.Sequence):
    def __getitem__(self, index):
        raise IndexError
    def __len__(self): return 0
def make_iter(x):
    return iter(x)
def make_reversed(x):
    return reversed(x)
def gen(x):
    for item in x:
        yield item

def use(x):
    "".join(x)
use(IterClass)
