def f(): pass
def g(): pass
def h(): pass

xs = []
xs.append(f)
xs.insert(0, g)
xs.extend([h])
xs[0]()
