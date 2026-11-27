
def f(): pass
def g(): pass
class C:
    pass
class D(C):
    def __getitem__(self, index): return f
a, b, d = C(), C(), D()
def use(x):
    x.run()
    x.tool()
    x.size
    len(x)
    for item in x:
        item()
    x.value = 1
    return x.cb
for x in (a, b, d):
    use(x)()
C.run = f
C.tool = staticmethod(g)
C.size = property(g)
C.__len__ = f
C.__setattr__ = g
setattr(a, "cb", g)
b.__dict__["cb"] = f
for name in vars(a):
    getattr(d, name)()
