
import shapes
def report(shape):
    shape.area()
class Canvas:
    def draw(self, shape, *more, **named):
        shape.area()
        for each in more:
            each.size()
        named["x"].size()
