
import array
class Mutable(bytearray):
    def __len__(self): return 0
class Frozen(bytes):
    def __len__(self): return 0
class View(array.array):
    def __len__(self): return 0
class Exporter:
    def __buffer__(self, flags): return memoryview(b"x")
    def __iter__(self): return iter([65])
    def __len__(self): return 0
class Sized:
    def __iter__(self): return iter([65])
    def __len__(self): return 0
def use(x):
    bytes(x)
use(Mutable(b"x"))
use(Frozen(b"x"))
use(View("b", [1]))
use(Exporter())
use(Sized())
