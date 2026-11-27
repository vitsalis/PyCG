
from typing import NamedTuple
class Point(NamedTuple):
    x: int
    def total(self):
        return self.x
Point(1).total()
Point(1).count(1)
