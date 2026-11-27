def f(): pass
def g(): pass
def h(): pass

table = {b"ext.a": g, 1: g, "ext.a": f}
def read(name):
    table["ext.%s" % name]()
read("x")
