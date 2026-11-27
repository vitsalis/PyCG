class C:
    def f(cls): pass
C.f = classmethod(C.f)
C.f()
