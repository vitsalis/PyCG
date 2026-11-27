
from abc import ABC, abstractmethod
class Rebound(ABC):
    @abstractmethod
    def f(self): pass
    f = 1
    def __init__(self): pass
class Base(ABC):
    @abstractmethod
    def f(self): pass
Base.f = lambda self: None
class Child(Base):
    def __init__(self): pass
Rebound()
Child()
