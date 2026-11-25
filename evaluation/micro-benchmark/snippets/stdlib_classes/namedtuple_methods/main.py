from collections import namedtuple


class Point(namedtuple("Point", "x y")):
    def norm(self):
        return abs(self.x) + abs(self.y)


Point(1, -2).norm()
