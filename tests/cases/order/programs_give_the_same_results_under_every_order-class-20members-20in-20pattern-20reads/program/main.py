
from enum import Enum
def suffix():
    return "x"
class E(str, Enum):
    def __new__(cls, value):
        obj = str.__new__(cls, "pre_" + value)
        obj._value_ = value
        return obj
    A = "a"
class F(str, Enum):
    B = "pre_" + suffix()
def hit(): pass
def other(): pass
def read(**table):
    kind = "a"
    table["pre_" + kind]()
read(**{E.A: hit})
class Holder:
    table = {E.A: hit, "zz": other}
def late(kind):
    Holder.table["pre_" + kind]()
    Holder.table[F.B]()
    Holder.table[F.B.lower()]()
late("a")
