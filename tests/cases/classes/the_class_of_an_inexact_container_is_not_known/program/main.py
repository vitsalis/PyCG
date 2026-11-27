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
def member():
    x = E.A
    y = x.__class__(x)
    if not isinstance(y, list):
        for value in y:
            value.inside()
def member_class():
    k = E.A.__class__
    if not issubclass(k, list):
        k([])
def tested(x: list):
    v = [Sub()]
    if not isinstance(v, x.__class__):
        v[0].after()
def exact():
    x = [B()]
    y = x.__class__(x)
    if not isinstance(y, list):
        y[0].other()
