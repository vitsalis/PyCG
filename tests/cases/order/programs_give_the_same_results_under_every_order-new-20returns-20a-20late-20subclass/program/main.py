
class Shape:
    def __new__(cls, kind):
        if kind:
            return object.__new__(Circle)
        return super().__new__(cls)
def a(): return b()
def b(): return Shape
class Circle(a()):
    def __init__(self, kind):
        pass
def make():
    Shape("circle")
