
class C:
    def f(cls): pass
    def g(): pass
    def h(self): pass
C.f = classmethod(C.f)
C.g = staticmethod(C.g)
C.h = property(C.h)
C.f()
C.g()
C().h
