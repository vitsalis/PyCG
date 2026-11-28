def f(): pass
def g(): pass
def h(): pass

xs = [f]
ys = xs.copy()
ys.append(g)
xs[0]()
