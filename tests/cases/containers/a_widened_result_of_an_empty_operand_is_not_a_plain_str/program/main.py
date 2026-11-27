def f(): pass
def g(): pass
def h(): pass

table = {"hit": f, "top_x": g}
def read(name):
    k = "pre_" + name
    table["top_" + k]()
