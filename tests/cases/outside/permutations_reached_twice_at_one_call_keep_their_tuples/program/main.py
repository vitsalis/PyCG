
import itertools
def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.permutations)
class C(metaclass=M):
    __new__ = Factory()

class N(int):
    def __iter__(self): return iter([b, b])
def use(factory):
    for x, y in factory(N(2)):
        x()
use(C)
use(itertools.permutations)
