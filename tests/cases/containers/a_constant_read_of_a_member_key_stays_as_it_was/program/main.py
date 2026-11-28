def f(): pass
def g(): pass
def h(): pass

from enum import Enum
class E(Enum):
    A = "a"
table = {E.A: f, "b": g}
def read():
    table["b"]()
