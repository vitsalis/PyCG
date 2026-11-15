class Circle:
    def area(self):
        return 3


class Square:
    def area(self):
        return 4


def round_area(shapes):
    result = 0
    for shape in shapes:
        if isinstance(shape, Circle):
            result += shape.area()
    return result


round_area([Circle(), Square()])
