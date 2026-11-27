
class Shape:
    def __init__(self): pass
class Square(Shape):
    def __new__(cls): return Shape()
    def __init__(self): pass
def make():
    Shape(); Shape(); Shape()
    Square(); Square()
make()
