import ctypes


class Point(ctypes.Structure):
    _fields_ = (("x", ctypes.c_int), ("y", ctypes.c_int))

    def describe(self):
        return "point"


class Rect(ctypes.Structure):
    _fields_ = (("origin", Point), ("width", ctypes.c_int))


rect = Rect()
rect.origin.describe()
rect.width.bit_length()
