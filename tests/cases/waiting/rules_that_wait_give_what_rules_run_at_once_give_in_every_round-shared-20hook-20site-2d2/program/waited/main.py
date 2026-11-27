
class D:
    x = "ok"
    def __format__(self, spec): return "d"
class C:
    def __getattribute__(self, name): return D()
answer = "{0.x.x}".format(C())
