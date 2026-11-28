def f(): pass
def g(): pass
def h(): pass

from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    A = "pre_" + suffix()
    def __hash__(self):
        return hash("hit")
    def __eq__(self, other):
        return other == "hit"
table = {"hit": f}
def read():
    table.pop(E.A)()
