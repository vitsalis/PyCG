
from typing import List, TypeAlias, TypeVar, Union
T = TypeVar("T")
class Box:
    def run(self): pass
type Loop[X] = Loop[X] | Box
type Ping[X] = Pong[X] | Box
type Pong[X] = Ping[X]
Left = Union[Box, List[T]]
Right: TypeAlias = Left[T]
Left = Right[T]
def use(a: Loop[int], b: Pong[int], c: Left[int], d: "Right[int]"):
    a.run()
    b.run()
    c.run()
    d.run()
