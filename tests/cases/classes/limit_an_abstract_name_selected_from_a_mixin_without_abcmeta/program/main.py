
from abc import ABC, abstractmethod
class A(ABC):
    @abstractmethod
    def f(self): pass
class Mix:
    @abstractmethod
    def f(self): pass
class C(Mix, A):
    def __init__(self): pass
C()
