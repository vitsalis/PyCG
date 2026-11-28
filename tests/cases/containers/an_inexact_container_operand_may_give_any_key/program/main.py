def f(): pass
def g(): pass
def h(): pass

from enum import Enum
class E(str, Enum):
    A = ("x",)
    def __rmod__(self, fmt):
        return "hit"
table = {"hit": f, "pre_x": g}
def read():
    table["pre_%s" % E.A]()
