
def f(): pass
def g(): pass
table = {"100%_x": f, "100#_x": g}
def read(name):
    table["100%%_%s" % name]()
read("x")
