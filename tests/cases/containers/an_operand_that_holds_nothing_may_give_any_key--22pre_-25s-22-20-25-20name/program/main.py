def f(): pass
def g(): pass
def h(): pass

table = {"hit": f, "pre_x": g}
def read(name):
    table["pre_%s" % name]()
