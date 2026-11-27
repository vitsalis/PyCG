
import shapes
def base():
    return shapes.Shape
class Late(base()):
    def area(self): pass
def pick(item, *more):
    item.area()
    for each in more:
        each.area()
class Canvas:
    shape = None
    def draw(self):
        self.shape.area()
current = None
def run():
    current.area()
    pick(Late())
