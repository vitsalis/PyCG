
def f(): pass
def g(): pass
def h(): pass

def outer():
    handler = f
    def inner():
        handler()
    handler()
    handler = g
    return inner
