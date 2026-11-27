
from collections.abc import Iterator
from typing import ClassVar, overload
from shapes import Shape, Square
@overload
def pick(item: Square) -> None: ...
@overload
def pick(item: Shape, *more: Iterator[Shape]) -> None: ...
class Canvas:
    shape: ClassVar[Shape | None]
current: "Square | Iterator[Late]"
