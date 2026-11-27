def f(): pass
def g(): pass
def h(): pass

a, (b, c) = f, (g, h)
b()
def pair():
    return [g, f]
x, y = pair()
y()
