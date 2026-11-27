
from typing import overload
from shapes import Shape, Square
third = second
@overload
def _first(shape: Shape) -> None: ...
@overload
def _first(shape: Square, *more: Square) -> None: ...
first = _first
second = first
class Canvas:
    def _draw(self, shape: Square) -> None: ...
    draw = _draw
