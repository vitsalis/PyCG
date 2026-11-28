
def f(): pass
def g(): pass
def h(): pass

def use():
    handler = f
    handler = None
    handler()
