
import sys
class X0:
    def __getattr__(self, name): pass
class Y0:
    def f(self): pass
class X1: pass
class Y1: pass
class X2: pass
class Y2: pass
class X3: pass
class Y3: pass
class C(
    X0 if sys.argv else Y0,
    X1 if sys.argv else Y1,
    X2 if sys.argv else Y2,
    X3 if sys.argv else Y3,
):
    pass
C().f()
