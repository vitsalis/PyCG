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
def made():
    yield Other()
async def run():
    return Other()
class E(Mark, Enum):
    A = made()
    B = run()
    def __iter__(self):
        return self.value
def members():
    x = E.A
    if isinstance(x, Mark):
        for value in x:
            value.inside()
    y = E.B
    if isinstance(y, Mark):
        y.close()
def body():
    class C:
        G = made()
        if isinstance(G, tuple):
            for value in G:
                value.after()
