class C:
    def f(cls): pass
c = C()
C.f = classmethod(c.f)
c.f()
