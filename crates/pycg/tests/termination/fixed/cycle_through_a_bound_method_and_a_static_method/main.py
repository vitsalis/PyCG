class C:
    def f(*args): pass
C.f = classmethod(staticmethod(C.f))
C.f()
