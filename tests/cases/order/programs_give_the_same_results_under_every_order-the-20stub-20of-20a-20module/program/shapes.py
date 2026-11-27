
from collections.abc import Iterator
class Shape:
    def area(self): pass
class Square(Shape, Iterator):
    def area(self): pass
    def __next__(self): pass
