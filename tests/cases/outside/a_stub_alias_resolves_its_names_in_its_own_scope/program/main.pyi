
import shapes
Pick = shapes.Square
class Canvas:
    Pick = shapes.Shape
    def draw(self, shape: Pick) -> None: ...
def paint(shape: Pick) -> None: ...
