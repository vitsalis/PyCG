
class Data(bytearray):
    def __int__(self): return 1
    def __float__(self): return 1.0
    def __complex__(self): return 1j
    def __bytes__(self): return b""
    def __len__(self): return 0
def use(x):
    complex(x)
use(Data(b"1"))
