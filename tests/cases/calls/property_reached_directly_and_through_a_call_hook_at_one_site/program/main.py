
import sys
def getter(self): return 1
class Maker:
    __call__ = property
make = property if sys.argv else Maker()
class C:
    p = make(getter)
