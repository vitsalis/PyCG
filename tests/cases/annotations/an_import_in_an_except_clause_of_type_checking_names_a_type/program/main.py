
from typing import TYPE_CHECKING
import shapes
if TYPE_CHECKING:
    try:
        from shapes import Other
    except ImportError:
        from shapes import Shape
def use(shape: "Shape"):
    shape.area()
