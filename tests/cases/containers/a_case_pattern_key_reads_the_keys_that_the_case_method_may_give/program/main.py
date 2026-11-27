def f(): pass
def g(): pass
def h(): pass

def k(): pass
table = {"ext_a": f, "ext_A": g, "ext_é": h, "ext_É": k}
def read(name):
    table[("EXT_" + name).lower()]()
read("x")
