
from abc import ABC, abstractmethod
class Mix:
    @abstractmethod
    def f(self): pass
class C(Mix, ABC):
    def __init__(self): pass
C()
