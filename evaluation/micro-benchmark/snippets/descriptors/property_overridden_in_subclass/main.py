class Shape:
    @property
    def name(self):
        return "shape"


class Circle(Shape):
    @property
    def name(self):
        return "circle"


Circle().name
