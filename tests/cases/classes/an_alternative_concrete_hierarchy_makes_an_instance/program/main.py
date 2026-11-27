
import abc
class Abstract(abc.ABC):
    @abc.abstractmethod
    def run(self): pass
class Concrete(abc.ABC):
    def run(self): pass
def pick(flag):
    return Abstract if flag else Concrete
class Thing(pick(True)):
    def __init__(self): pass
Thing()
