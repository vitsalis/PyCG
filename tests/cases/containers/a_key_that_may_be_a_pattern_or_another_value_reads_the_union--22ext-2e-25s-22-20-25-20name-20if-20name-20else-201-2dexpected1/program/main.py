def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f, "other": g, 1: h}
def read(name):
    table["ext.%s" % name if name else 1]()
read("x")
