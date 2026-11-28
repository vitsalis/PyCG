
class Strategy:
    def __call__(self, state): pass
class Fast(Strategy):
    def __call__(self, state): pass

from typing import List, TypeAlias, TypeVar, Union
T = TypeVar("T")
type Loop[X] = Loop[X] | Strategy
type Ping[X] = Pong[X] | Strategy
type Pong[X] = Ping[X]
Plain = Union[Strategy, List[T]]
Plain = Plain[T]
Left = Union[Strategy, List[T]]
Right: TypeAlias = Left[T]
Left = Right[T]
def loop(s: Loop[int], t: "Loop[int]"):
    s(1)
    t(1)
def ping(s: Pong[int]):
    s(1)
def plain(s: Plain[int], t: Left[int]):
    s(1)
    t(1)
