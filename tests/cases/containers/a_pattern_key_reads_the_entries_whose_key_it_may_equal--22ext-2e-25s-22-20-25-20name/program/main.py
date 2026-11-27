def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f, "ext.": g, "ext": h, "other": h}
def read(name):
    table["ext.%s" % name]()
read("x")
