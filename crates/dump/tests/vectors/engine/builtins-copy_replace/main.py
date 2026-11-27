from copy import replace
from datetime import date


class Point:
    def __init__(self, x):
        self.x = x

    def __replace__(self, **changes):
        return Point(**changes)

    def show(self):
        pass


moved = replace(Point(1), x=2)
moved.show()
day = replace(date(2024, 1, 2), day=3)
day.isoformat()
