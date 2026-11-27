
from typing import ClassVar, Optional
from shapes import Shape
class Canvas:
    shape: ClassVar[Optional[Shape]]
    def draw(self) -> None: ...
