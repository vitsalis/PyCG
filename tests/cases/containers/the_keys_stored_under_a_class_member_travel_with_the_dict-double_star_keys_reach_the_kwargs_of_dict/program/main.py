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

table = dict(**{E.A: hit})
def read(kind):
    table["pre_" + kind]()
read("a")
