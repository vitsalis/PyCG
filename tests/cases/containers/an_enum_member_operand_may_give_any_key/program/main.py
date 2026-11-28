def f(): pass
def g(): pass
def h(): pass

from enum import Enum
class Kind(str, Enum):
    A = "x"
    def __radd__(self, other):
        return "hit"
table = {"hit": f, "pre_x": g}
def read():
    table["pre_" + Kind.A]()
