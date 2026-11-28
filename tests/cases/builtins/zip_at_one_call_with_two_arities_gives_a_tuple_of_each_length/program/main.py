
class M(type):
    def __iter__(cls): return iter([h])
class Factory:
    __call__ = staticmethod(zip)
class C(metaclass=M):
    __new__ = Factory()
def f(): pass
def g(): pass
def h(): pass
def make(factory, item):
    return factory([item])
for (one,) in make(zip, g):
    one()
for first, second in make(C, f):
    first()
    second()
