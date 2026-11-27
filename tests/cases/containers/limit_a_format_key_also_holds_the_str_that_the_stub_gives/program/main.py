def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f, "other": g}
def read(name):
    table["ext.{}".format(name)]()
read("x")
