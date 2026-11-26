import ctypes

Prototype = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)


def double(number):
    return number * 2


callback = Prototype(double)
callback(3)
