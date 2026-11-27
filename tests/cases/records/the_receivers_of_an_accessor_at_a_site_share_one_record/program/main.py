
class Getter:
    def __get__(self, instance, owner): return instance
class Shape:
    described = Getter()
    @property
    def area(self): return 1
def measure(shape):
    shape.area
    shape.described
measure(Shape()); measure(Shape()); measure(Shape())
