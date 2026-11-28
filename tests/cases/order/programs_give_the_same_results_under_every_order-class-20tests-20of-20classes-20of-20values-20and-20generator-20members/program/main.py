
from enum import Enum
def target(): pass
class M: pass
def gen():
    yield target
class E(M, Enum):
    A = [target]
    B = gen()
    def __iter__(self):
        return iter(self.value)
z = E.A.__class__(E.A)
if not isinstance(z, list):
    for cb in z:
        cb()
g = E.B
if isinstance(g, M):
    for cb in g:
        cb()
def tested(v: list, w=[target]):
    if not isinstance(w, v.__class__):
        w[0]()
class S(str, M, Enum):
    T = "target"
class Holder:
    @staticmethod
    def target(): pass
def names(n=S.T, m="other"):
    for name in (n, m, n):
        if isinstance(name, M):
            getattr(Holder, name)()
class Box:
    value = []
Base = Box.value.__class__
class Left(Base):
    pass
class Right(list):
    def append(self, x):
        pass
class Both(Left, Right):
    pass
Both().append(0)
