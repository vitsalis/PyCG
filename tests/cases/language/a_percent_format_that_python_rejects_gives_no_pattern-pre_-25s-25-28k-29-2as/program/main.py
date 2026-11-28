
def f(): pass
def g(): pass
table = {"pre_x": f, "other": g}
def read(name):
    table['pre_%s%(k)*s' % name]()
read("x")
