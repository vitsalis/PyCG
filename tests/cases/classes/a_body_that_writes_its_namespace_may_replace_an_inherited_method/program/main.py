
from abc import ABC, abstractmethod
class A(ABC):
    @abstractmethod
    def f(self): pass
class C(A):
    locals()["f"] = lambda self: None
    def __init__(self): pass
class D(C):
    def __init__(self): pass
C()
D()
