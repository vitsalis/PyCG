from typing import Any
class Base:
    pass
class C(Base):
    attr = None
    def m(self, a, b=1):
        return a
def g(x, *rest, **kw):
    return x
h = g
v = None
w: int = 2
z = y = 3
