
import copy
class Point:
    def __init__(self, x):
        self.x = x
    def __replace__(self, **changes):
        return Point(**changes)
    def show(self): pass

def use():
    copy.replace(Point(1), x=2).show()
use()
