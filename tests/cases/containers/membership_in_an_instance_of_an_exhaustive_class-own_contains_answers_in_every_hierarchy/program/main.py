
import sys
class Needle:
    def __eq__(self, other): return True
class Bag:
    def __contains__(self, item): return False
class Plain:
    def __iter__(self):
        return iter([1])
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class C(
    Bag if sys.argv else Plain,
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
):
    def __contains__(self, item): return False
Needle() in C()
