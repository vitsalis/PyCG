def f(): pass
def g(): pass
def h(): pass

def pair(a, b):
    a()
    b()
def spread(values):
    pair(f, *values)
spread([g])
