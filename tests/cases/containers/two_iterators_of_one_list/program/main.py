def f(): pass
def g(): pass
def h(): pass

L = [f]
next(iter(L))()
next(iter(L))()
