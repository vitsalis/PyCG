class A:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Sub(A):
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class B:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass
class Other:
    def inside(self): pass
    def after(self): pass
    def other(self): pass
    def more(self): pass

from enum import Enum
class Mark:
    pass
class E(str, Mark, Enum):
    A = "inside"
def member():
    x = E.A
    if isinstance(x, Mark):
        getattr(A(), x)()
def body():
    class C:
        N = "after"
        if not isinstance(N, str):
            getattr(B(), N)()
