
import itertools
def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.product)
class C(metaclass=M):
    __new__ = Factory()

def use(factory):
    for t in factory([b]):
        t[0]()
use(C)
use(itertools.product)
