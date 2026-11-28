def f(): pass
def g(): pass
def h(): pass

table = {"pre_ax": f, "other": g}
def read(name):
    table["pre_" + f"a{name}"]()
read("x")
