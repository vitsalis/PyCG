def f(): pass
def g(): pass
def h(): pass

class O:
    def x(self): pass
table = {"other": "x"}
def read(k):
    v = table["pre_" + k]
    read(v)
    getattr(O(), v)()
