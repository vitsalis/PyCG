import itertools
class MetaA(type):
    def __iter__(cls): return iter(())
class MetaB(type):
    def __iter__(cls): return iter(())
class Factory:
    __call__ = staticmethod(itertools.chain)
class One(metaclass=MetaA):
    __new__ = Factory()
class Two(metaclass=MetaB):
    __new__ = Factory()
def use(factory):
    return list(factory(()))
use(One)
use(Two)
