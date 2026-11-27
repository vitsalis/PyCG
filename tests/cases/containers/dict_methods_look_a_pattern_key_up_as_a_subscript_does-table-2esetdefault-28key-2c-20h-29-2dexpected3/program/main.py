def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f, "other": g}
def read(name):
    key = "ext.%s" % name
    table.setdefault(key, h)()
read("x")
