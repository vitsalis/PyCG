def f(): pass
def g(): pass
def h(): pass

from enum import Enum
def suffix():
    return "x"
class Odd(str):
    def __radd__(self, other):
        return "hit"
class E(str, Enum):
    A = "enum_" + suffix()
    def lower(self):
        return Odd("hit")
table = {"hit": f, "pre_x": g, "other": h}
def read():
    table["pre_" + E.A.lower()]()
