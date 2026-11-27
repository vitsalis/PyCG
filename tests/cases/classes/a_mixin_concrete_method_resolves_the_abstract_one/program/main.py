
import abc
class Base(abc.ABC):
    @abc.abstractmethod
    def run(self): pass
class Mixin:
    def run(self): pass
class Thing(Mixin, Base):
    def __init__(self): pass
Thing()
