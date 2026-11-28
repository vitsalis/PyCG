def f(): pass
def g(): pass
def h(): pass

def pair(a, b, c=None):
    b()
def rest(a, *more):
    more[0]()
pair(*[f, g])
pair(f, *(g,))
rest(*(f, g, h))
