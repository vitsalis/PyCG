from typing import NamedTuple


class Point(NamedTuple):
    x: int
    y: int

    def shifted(self):
        return Point(self.x + 1, self.y)

    def total(self):
        return self.x + self.y


Point(1, 2).shifted().total()
