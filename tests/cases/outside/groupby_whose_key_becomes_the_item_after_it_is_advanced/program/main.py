
import itertools
def b(): pass
class M(type):
    def __iter__(cls): return iter([b, b])
class Factory:
    __call__ = staticmethod(itertools.groupby)
class C(metaclass=M):
    __new__ = Factory()

class Both:
    def __iter__(self): return iter([b])
    def __call__(self, item): return item
def use(factory):
    for key, group in factory(Both()):
        key()
class Holder:
    def get(self):
        return self.deeper()
    def deeper(self):
        return [itertools.groupby][0]
use(C)
use(Holder().get())
