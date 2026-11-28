
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def first(*args):
    return args[0]
def second(a, *args):
    return args[1]
def use():
    first(f, g)()
    second(None, k, h)()
def other():
    first(g)()
    second(None, f, g)
