class Meters:
    def __add__(self, other):
        return NotImplemented


class Feet:
    def __radd__(self, other):
        return self


total = Meters() + Feet()
count = 1 + Feet()
