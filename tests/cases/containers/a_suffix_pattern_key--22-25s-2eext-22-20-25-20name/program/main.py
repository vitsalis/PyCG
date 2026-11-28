def f(): pass
def g(): pass
def h(): pass

table = {"a.ext": f, ".ext": g, "ext": h, "a.ext.b": h}
def read(name):
    table["%s.ext" % name]()
read("x")
