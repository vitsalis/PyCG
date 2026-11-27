
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from typing import Annotated, Generic, TypeVar
T = TypeVar("T")
class Box(Generic[T]):
    def open(self): pass
def annotated(s: Annotated[Strategy, "fast"]):
    s(1)
def boxed(box: Box[int]):
    box.open()
