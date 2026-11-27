
import ctypes, sys
class Plain:
    pass
class NotStructure(Plain):
    _fields_ = [("x", ctypes.c_int)]
Base = ctypes.Structure if sys.argv else ctypes.Union
class Either(Base):
    _fields_ = [("x", ctypes.c_int)]
class Array(ctypes.Structure):
    _fields_ = [("xs", ctypes.c_int * 4), ("y", ctypes.c_int)]
class Called(ctypes.Structure):
    _fields_ = make()
class Short(ctypes.Structure):
    _fields_ = [("x",)]
class Unnamed(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int)]
def use(n: NotStructure, e: Either, a: Array, c: Called, s: Short, u: Unnamed):
    n.x.bit_length()
    e.x.as_integer_ratio()
    a.xs.bit_length()
    a.y.conjugate()
    c.x.bit_length()
    s.x.bit_length()
    u.x.bit_length()
