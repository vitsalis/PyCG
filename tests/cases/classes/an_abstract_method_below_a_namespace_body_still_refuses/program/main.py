
from abc import ABC, abstractmethod
class C(ABC):
    snapshot = locals()
class D(C):
    @abstractmethod
    def g(self): pass
    def __init__(self): pass
D()
