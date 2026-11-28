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
class E(Enum):
    A = [Other()]
    def __iter__(self):
        return iter(self.value)
def make():
    return [Sub()]
class F(Enum):
    B = make()
def members():
    x = E.A
    if not isinstance(x, list):
        for value in x:
            value.inside()
    y = F.B
    if not isinstance(y, list):
        for value in y:
            value.after()
def body():
    class C:
        KINDS = [B()]
        if isinstance(KINDS, list):
            KINDS[0].other()
        if not isinstance(KINDS, list):
            KINDS[0].more()
