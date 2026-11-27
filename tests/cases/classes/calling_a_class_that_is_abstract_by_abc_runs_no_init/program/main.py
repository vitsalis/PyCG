
import abc
class Base(abc.ABC):
    def __init__(self): pass
    @abc.abstractmethod
    def run(self): pass
class Middle(Base):
    def __init__(self): pass
class Leaf(Middle):
    def __init__(self): pass
    def run(self): pass
def make(kind):
    return kind()
for kind in (Base, Middle, Leaf):
    make(kind).run()
