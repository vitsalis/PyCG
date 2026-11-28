
import abc
from collections.abc import Mapping
def meta():
    return abc.ABCMeta
class Base(metaclass=meta()):
    def __new__(cls):
        return super().__new__(cls)
    def __init__(self): pass
    def run(self):
        self.step()
    @abc.abstractmethod
    def step(self): pass
class Middle(Base):
    pass
class Leaf(Middle):
    def step(self): pass
class Concrete(abc.ABC):
    def step(self): pass
def pick(flag):
    return Base if flag else Concrete
class Either(pick(True)):
    def __init__(self): pass
class Partial(Mapping):
    def __init__(self): pass
    def __getitem__(self, key): pass
for kind in (Base, Middle, Leaf, Either, Partial):
    kind().step()
