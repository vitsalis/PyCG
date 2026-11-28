def f(): pass
def g(): pass
def h(): pass

table = {"other": f}
def put(name):
    table["ext.%s" % name] = g
put("a")
def read():
    table["other"]()
