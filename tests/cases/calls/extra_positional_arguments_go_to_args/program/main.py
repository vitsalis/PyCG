def f(): pass
def g(): pass
def h(): pass

def first(a, *args):
    args[0]()
def every(*args):
    for arg in args:
        arg()
first(f, g, h)
every(f, g)
