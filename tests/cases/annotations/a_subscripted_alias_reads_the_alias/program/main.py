
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from typing import Generic, Optional, TypeVar, Union
T = TypeVar("T")
class Box(Generic[T]):
    def run(self): pass
class Bag(Generic[T]):
    def run(self): pass
AnyBox = Union[Box[T], Bag[T]]
MaybeBox = Optional[Box[T]]
type Pair[X] = Box[X] | Bag[X]
Tree = Union[Box[T], list["Tree[T]"]]
Rec = Union[Bag[T], "Rec[T]"]
TABLE = [Box]
def either(box: AnyBox[int]):
    box.run()
def maybe(box: MaybeBox[str]):
    box.run()
def pair(box: Pair[int]):
    box.run()
def text(box: "AnyBox[int]"):
    box.run()
def nested(box: Optional[AnyBox[int]]):
    box.run()
def walk(tree: Tree[int], rec: Rec[int]):
    tree.run()
    rec.run()
def element(box: TABLE[0]):
    box.run()
