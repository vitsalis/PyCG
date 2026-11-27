def f(): pass
def g(): pass
def h(): pass

table = {"pre_ax": f, "other": g}
def read(name):
    table["pre_" + "a{}".format(name)]()
read("x")
