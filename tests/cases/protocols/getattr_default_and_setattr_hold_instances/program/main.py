
class C:
    def m(self): pass
class D:
    def m(self): pass
class Holder:
    pass
holder = Holder()
setattr(holder, "x", C())
holder.x.m()
getattr(holder, "missing", D()).m()
