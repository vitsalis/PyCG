def f(): pass
def g(): pass
def h(): pass

from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    A = "enum_" + suffix()
    def __radd__(self, prefix):
        return "hit"
    def __rmod__(self, fmt):
        return "hit"
table = {"hit": f, "pre_x": g}
def read():
    table["pre_" + E.A]()
