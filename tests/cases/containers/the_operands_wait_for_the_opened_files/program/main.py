def f(): pass
def g(): pass
def h(): pass

table = {"pre_x": f, "other": g}
def read(mode):
    table["pre_" + open("p", mode).read()]()
