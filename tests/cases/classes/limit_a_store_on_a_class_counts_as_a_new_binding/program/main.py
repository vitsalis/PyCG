
from abc import ABC, abstractmethod
class Abstract(ABC):
    @abstractmethod
    def f(self): pass
    def __init__(self): pass
Abstract.f = Abstract.f
Abstract()
