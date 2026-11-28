def f(): pass
def g(): pass
def h(): pass

d = {}
d["a"] = f
d["a"]()
xs = [None, None]
xs[1] = g
xs[1]()
def put(i):
    xs[i] = h
xs[0]()
