
def f(): pass
def g(): pass
def h(): pass

def use():
    handler = f
    del handler
    handler = g
    handler()
