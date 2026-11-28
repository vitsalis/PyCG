def f(): pass
def g(): pass
def h(): pass

([f] + [g])[1]()
([h] * 2)[0]()
xs = [f]
xs += [g]
xs[0]()
