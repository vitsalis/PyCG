
import sys
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class X4: pass
class Y4: pass
class K:
    def m(self): pass
class E(
    K,
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
    X4 if sys.argv else Y4,
):
    pass
def not_callable(x=E()):
    if not callable(x):
        x.m()
def not_itself(x=E()):
    if not isinstance(x, E):
        x.m()
not_callable()
not_itself()
