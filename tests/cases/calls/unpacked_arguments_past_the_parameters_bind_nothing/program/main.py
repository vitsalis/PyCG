def f(): pass
def g(): pass
def h(): pass

def take(a):
    a()
take(f, g, *(h,))
