
import ctypes
class Point(ctypes.Structure):
    _fields_ = (("x", ctypes.c_int),)
    def show(self): pass
class Rect(ctypes.Structure):
    _fields_ = [("origin", Point), ("count", ctypes.c_uint32)]
    def use(self):
        self.origin.show()
        self.count.bit_length()
