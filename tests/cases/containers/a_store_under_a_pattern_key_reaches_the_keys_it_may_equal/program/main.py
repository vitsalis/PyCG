def f(): pass
def g(): pass
def h(): pass

table = {"ext.a": f}
def put(name):
    table["ext.%s" % name] = g
def read():
    table["ext.a"]()
