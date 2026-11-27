
def f(): pass
class C:
    def g(self): pass
def write():
    d = C.__dict__
    d["x"] = f
    d["x"]()
    d["g"](C())
def load():
    C.x()
write()
load()
