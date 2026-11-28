
import itertools
def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.repeat)
class C(metaclass=M):
    __new__ = Factory()

def use(factory):
    next(factory())()
use(C)
use(itertools.repeat)
