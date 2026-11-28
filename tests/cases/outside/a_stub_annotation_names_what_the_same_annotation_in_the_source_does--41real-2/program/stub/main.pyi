
from typing import Generic, Optional, Protocol, Self, TypeVar
from shapes import Shape
T = TypeVar("T")
class Box(Generic[T]):
    def area(self): pass
class Areal(Protocol):
    def area(self): ...
class Plot(Areal):
    def area(self): pass

class Tool:
    def use(self, x: Areal): ...
