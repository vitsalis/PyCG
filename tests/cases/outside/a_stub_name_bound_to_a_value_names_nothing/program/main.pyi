
from typing import TypeVar
from shapes import Shape
A = "Shape"
B = TypeVar("B")
C = 1
current: Shape
D = current
def use(a: A, b: B, c: C, d: D) -> None: ...
