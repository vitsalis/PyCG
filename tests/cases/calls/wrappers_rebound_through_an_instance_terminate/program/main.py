
class C:
    def f(cls): pass
    def g(self): pass
    def h(self): pass
c = C()
C.f = classmethod(c.f)
C.g = staticmethod(c.g)
C.h = property(c.h)
c.f()
c.g()
c.h
