import ctypes

libc = ctypes.CDLL(None)
libc.getpid()
libc["abs"](-1)
