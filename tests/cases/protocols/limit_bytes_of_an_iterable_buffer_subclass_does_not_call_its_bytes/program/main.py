
class Data(bytearray):
    def __bytes__(self): return b""
    def __len__(self): return 0
def use(x):
    bytes(x)
use(Data(b"1"))
