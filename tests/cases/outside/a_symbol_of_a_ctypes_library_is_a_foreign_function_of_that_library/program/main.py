
import ctypes
def use():
    lib = ctypes.CDLL("libc.so.6")
    lib.free(0)
    lib["abs"](-1)
    ctypes.cdll.LoadLibrary("libc.so.6").getpid()
