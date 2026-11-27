
class Index:
    def __index__(self): return 1
    def __iter__(self): return iter([])
    def __len__(self): return 0
class Convertible:
    def __bytes__(self): return b""
    def __iter__(self): return iter([])
    def __len__(self): return 0
def use(x):
    bytes(x)
use(Index())
use(Convertible())
