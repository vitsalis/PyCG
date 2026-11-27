
def f(): pass
def g(): pass
def h(): pass

a = f
b = g
del (a, b)
a()
b = g
del [b]
b()
