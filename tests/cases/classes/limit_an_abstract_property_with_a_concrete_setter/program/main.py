
from abc import ABC, abstractmethod
class C(ABC):
    @property
    @abstractmethod
    def f(self): pass
    @f.setter
    def f(self, value): pass
    def __init__(self): pass
C()
