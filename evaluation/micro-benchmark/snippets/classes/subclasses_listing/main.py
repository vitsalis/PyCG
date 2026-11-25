class Shape:
    def area(self):
        return 0


class Square(Shape):
    def area(self):
        return 4


class Circle(Shape):
    def area(self):
        return 3


class Unit(Square):
    def area(self):
        return 1


def total(kind):
    return sum(cls().area() for cls in kind.__subclasses__())


total(Shape)
