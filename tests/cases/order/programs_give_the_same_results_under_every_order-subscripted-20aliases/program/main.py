
from typing import Generic, Optional, TypeVar, Union
T = TypeVar("T")
class Box(Generic[T]):
    def run(self): pass
class Bag(Generic[T]):
    def run(self): pass
AnyBox = Union[Box[T], Bag[T]]
Rec = Union[Bag[T], "Rec[T]"]
def use(box: Optional[AnyBox[int]], rec: Rec[int]):
    box.run()
    rec.run()
