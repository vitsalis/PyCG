
from shapes import Square
def report(shape: Square, other):
    shape.area()
    other.size()
class Canvas:
    shape: Square = Square()
    def draw(self):
        self.shape.size()
