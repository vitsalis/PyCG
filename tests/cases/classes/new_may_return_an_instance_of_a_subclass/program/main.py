
import ext
def f(): pass
def g(): pass

class Shape:
    def __new__(cls, kind):
        if kind == "circle":
            return object.__new__(Circle)
        return object.__new__(cls)
class Circle(Shape):
    def __init__(self, kind):
        pass
def make():
    Shape("circle")
