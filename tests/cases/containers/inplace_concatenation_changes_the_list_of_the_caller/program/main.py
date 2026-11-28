def f(): pass
def g(): pass
def h(): pass

def extend(items):
    items += [g]
xs = [f]
extend(xs)
xs[0]()
