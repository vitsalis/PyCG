def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f, "other": g}
def put(key):
    table[key] = h
def read(name):
    table["ext.%s" % name]()
read("x")
