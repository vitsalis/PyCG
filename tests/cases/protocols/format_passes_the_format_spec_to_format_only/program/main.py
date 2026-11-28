
class C:
    def x(self): return ""
    def y(self): return ""
    def z(self): return ""
    def __format__(self, spec):
        return getattr(self, spec)()
class D:
    def x(self): return ""
    def z(self): return ""
    def __str__(self, spec="z"):
        return getattr(self, spec)()
format(C(), "x")
f"{C():y}"
f"{C()!r:z}"
format(D(), "x")
