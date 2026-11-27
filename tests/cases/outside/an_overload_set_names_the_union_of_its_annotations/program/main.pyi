
import sys
from typing import overload
from shapes import Circle, Shape, Square
@overload
def pick(item: Circle) -> Circle: ...
@overload
def pick(item: Square, extra: None = None) -> Square: ...
if sys.version_info >= (3, 99):
    def pick(item: int, extra: Square) -> None: ...
