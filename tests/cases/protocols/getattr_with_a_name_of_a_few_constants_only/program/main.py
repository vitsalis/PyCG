
class C:
    def a(self): pass
    def b(self): pass
    def c(self): pass
    def d(self): pass
    def e(self): pass
def few(obj):
    for name in ("a", "b", "c", "d"):
        getattr(obj, name)()
def many(obj):
    for name in ("a", "b", "c", "d", "e"):
        getattr(obj, name)()
few(C())
many(C())
