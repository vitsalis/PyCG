
import sys
class X:
    def f(self): pass
def make_base():
    return X
class D(make_base()):
    pass
class Y:
    def f(self): pass
class C(D if sys.argv else Y):
    def __getattr__(self, name): pass
C().f()
