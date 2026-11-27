
from abc import ABC, abstractmethod
class C(list, ABC):
    @abstractmethod
    def f(self): pass
    def __new__(cls):
        return object.__new__(cls)
    def __init__(self): pass
C()
