
from abc import ABC, abstractmethod
class C(ABC):
    @abstractmethod
    def f(self): pass
    if True:
        def helper(value=(f := 1)): pass
    def __init__(self): pass
C()
