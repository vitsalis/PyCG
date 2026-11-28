
class M(type):
    def __iter__(cls): return iter(())
class Factory:
    __call__ = staticmethod(zip)
class C(metaclass=M):
    __new__ = Factory()
def make(factory): return factory(())
make(zip)
make(C)
