class Shape:
    def __init__(self, size):
        self.size = size

    @classmethod
    def unit(cls):
        return cls(1)


class Square(Shape):
    def __init__(self, size):
        self.side = size


square = Square.unit()
