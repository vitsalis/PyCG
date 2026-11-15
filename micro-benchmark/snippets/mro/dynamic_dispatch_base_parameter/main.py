class Shape:
    def area(self):
        pass


class Circle(Shape):
    def area(self):
        pass


class Square(Shape):
    def area(self):
        pass


def report(shape):
    shape.area()


report(Circle())
