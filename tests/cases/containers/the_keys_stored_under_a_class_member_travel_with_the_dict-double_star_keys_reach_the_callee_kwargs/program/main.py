def f(): pass
def g(): pass
def h(): pass

from enum import Enum
class E(str, Enum):
    def __new__(cls, value):
        obj = str.__new__(cls, "pre_" + value)
        obj._value_ = value
        return obj
    A = "a"
def hit(): pass

def read(**table):
    kind = "a"
    table["pre_" + kind]()
read(**{E.A: hit})
