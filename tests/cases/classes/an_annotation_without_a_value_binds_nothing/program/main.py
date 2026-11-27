
from abc import ABC, abstractmethod
class Annotated(ABC):
    @abstractmethod
    def f(self): pass
    f: object
    def __init__(self): pass
class Nested(ABC):
    @abstractmethod
    def f(self): pass
    def helper(self):
        return (f := 1)
    def __init__(self): pass
Annotated()
Nested()
