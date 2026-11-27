
def f(): pass
def g(): pass
def h(): pass

a, b = f, g
a, b = b, a
a()
