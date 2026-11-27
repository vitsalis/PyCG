
def f(): pass
f = staticmethod(f)
f()
def g(cls): pass
g = classmethod(g)
def h(self): return 1
h = property(h)
class C:
    m = g
    p = h
C.m()
C().p
