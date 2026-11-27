
def f(): pass
def g(): pass
def h(): pass
def k(): pass

def last(*args):
    return args[-1]
def option(**kwargs):
    return kwargs["key"]
def use():
    last(f)()
    option(key=h)()
last(g)
option(key=k)
