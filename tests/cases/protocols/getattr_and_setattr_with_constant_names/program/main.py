
def f(): pass
def g(): pass
def h(): pass
class C:
    def m(self): pass
    @property
    def p(self):
        return f
def use(c, unknown):
    getattr(c, "m")()
    name = "m"
    getattr(c, name)()
    getattr(c, "missing", g)()
    setattr(c, "stored", h)
    c.stored()
    getattr(c, "p")()
    getattr(c, unknown)()
use(C(), input())
