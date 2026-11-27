
def f(): pass
def g(): pass
def h(): pass

def use():
    handler = f
    for following in (g, h):
        handler()
        handler = following
    handler()
