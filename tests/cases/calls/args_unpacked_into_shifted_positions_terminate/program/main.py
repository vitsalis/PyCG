def f(): pass
def g(): pass
def h(): pass

def shift(*args):
    args[0]()
    shift(g, *args)
def back(a, b, *args):
    back(*args)
shift(f)
back(f, g, h)
